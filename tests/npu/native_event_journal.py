"""Lossless append-only observer events with lazy indexed reads and bounded RAM.

Identical JSON fields and an exact integer step progression form a run. SQLite
holds completed runs; only one tail per stream stays in Python. Nothing samples
or drops events. Storage exhaustion raises, rather than weakening observation.
Explicit compact chunks hold at most 64 runs/1MiB decoded per stream. Their
SHA256 covers every raw row; v3 omits redundant per-row digests. Older v1/v2
journals remain readable. Decompression and pending chunks are bounded.
"""
from collections.abc import Sequence
import hashlib
import json
import operator
import os
from pathlib import Path
import sqlite3
import struct
import threading
import zlib

MAX_INTEGER = (1 << 63) - 1
MAX_PAYLOAD = 65536
MAX_CHUNK_BYTES = 1024 * 1024


def integer(value):
    if type(value) is not int or not -MAX_INTEGER - 1 <= value <= MAX_INTEGER:
        raise ValueError('observer integer must fit signed64 exactly')
    return value


def checksum(first, count, start, delta, payload):
    return hashlib.sha256(struct.pack('<4q', first, count, start, delta) + payload.encode('ascii')).hexdigest()


class EventJournal:
    def __init__(self, path, *, max_bytes=64 * 1024 * 1024, read_only=False, compact=False):
        self.path = Path(path).absolute()
        if self.path.is_symlink(): raise ValueError('observer journal alias')
        self.read_only, self.thread, self.closed = read_only, threading.get_ident(), False
        self.failed = False
        self.streams, self.pending_runs = {}, 0
        self.version, self.chunks = 3 if compact else 1, {}
        if read_only:
            self.db = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
            versions = self.db.execute('SELECT format FROM metadata').fetchall()
            if versions not in ([(1,)], [(2,)], [(3,)]):
                raise ValueError('observer journal format')
            self.version = versions[0][0]
        else:
            if type(max_bytes) is not int or not 65536 <= max_bytes <= MAX_INTEGER:
                raise ValueError('observer journal byte budget')
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            self.db = sqlite3.connect(self.path)
            self.db.execute('PRAGMA journal_mode=DELETE')
            self.db.execute('PRAGMA synchronous=FULL')
            page_size, = self.db.execute('PRAGMA page_size').fetchone()
            self.db.execute('PRAGMA max_page_count=' + str(max_bytes // page_size))
            table = ('CREATE TABLE chunks(stream TEXT NOT NULL, first_index INTEGER NOT NULL,'
                ' logical_count INTEGER NOT NULL, run_count INTEGER NOT NULL, raw_bytes INTEGER NOT NULL,'
                ' payload BLOB NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(stream,first_index));') if compact else (
                'CREATE TABLE runs(stream TEXT NOT NULL, first_index INTEGER NOT NULL,'
                ' repeat_count INTEGER NOT NULL, start_step INTEGER NOT NULL, delta INTEGER NOT NULL,'
                ' payload TEXT NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(stream,first_index));')
            self.db.executescript('CREATE TABLE metadata(format INTEGER NOT NULL); INSERT INTO metadata VALUES('
                + str(self.version) + ');' + table)
            self.db.commit()
        self.db.execute('PRAGMA cache_size=-1024')
        self.db.execute('PRAGMA temp_store=FILE')
        self.compact = self.version >= 2

    def check(self, write=False):
        if self.closed: raise ValueError('observer journal closed')
        if self.failed: raise RuntimeError('observer journal storage failed')
        if threading.get_ident() != self.thread: raise RuntimeError('observer journal is single-threaded')
        if write and self.read_only: raise ValueError('observer journal is read-only')

    def sequence(self, name, initial=()):
        self.check()
        if not isinstance(name, str) or not name or len(name) > 80: raise ValueError('observer stream name')
        if name not in self.streams: self.streams[name] = EventSequence(self, name)
        result = self.streams[name]
        for event in initial: result.append(event)
        return result

    def stored_count(self, name):
        column, table = ('logical_count', 'chunks') if self.compact else ('repeat_count', 'runs')
        count = self.db.execute('SELECT COALESCE(SUM(' + column + '),0) FROM ' + table + ' WHERE stream=?', (name,)).fetchone()[0]
        return count + self.chunks.get(name, {}).get('count', 0)

    def commit_runs(self, count):
        self.pending_runs += count
        if self.pending_runs >= 64:
            self.db.commit()
            self.pending_runs = 0

    def append_run(self, name, row):
        self.check(write=True)
        try:
            if not self.compact:
                self.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?)', (name, *row, checksum(*row)))
                self.commit_runs(1)
                return
            encoded = json.dumps(row, separators=(',', ':'), ensure_ascii=True)
            if name in self.chunks and self.chunks[name]['bytes'] + len(encoded) + 1 > MAX_CHUNK_BYTES:
                self.flush_chunk(name)
            chunk = self.chunks.setdefault(name, dict(first=row[0], count=0, bytes=2, parts=[]))
            assert chunk['first'] + chunk['count'] == row[0]
            chunk['parts'].append(encoded)
            chunk['bytes'] += len(encoded) + int(len(chunk['parts']) > 1)
            chunk['count'] += row[1]
            assert chunk['bytes'] <= MAX_CHUNK_BYTES
            if len(chunk['parts']) >= 64:
                self.flush_chunk(name)
        except sqlite3.Error:
            self.failed = True
            raise

    def flush_chunk(self, name):
        chunk = self.chunks[name]
        raw = ('[' + ','.join(chunk['parts']) + ']').encode('ascii')
        assert len(raw) == chunk['bytes'] <= MAX_CHUNK_BYTES
        self.db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?,?)', (name, chunk['first'], chunk['count'],
            len(chunk['parts']), len(raw), zlib.compress(raw), hashlib.sha256(raw).hexdigest()))
        del self.chunks[name]
        self.commit_runs(len(chunk['parts']))

    @staticmethod
    def decode_chunk(row, version=3):
        first, logical, count, size, data, digest = row
        if any(type(value) is not int for value in (first, logical, count, size)) or not (
                0 <= first <= MAX_INTEGER and 1 <= logical <= MAX_INTEGER - first and
                1 <= count <= 64 and 2 <= size <= MAX_CHUNK_BYTES):
            raise ValueError('observer chunk metadata corruption')
        try:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(data, MAX_CHUNK_BYTES + 1)
            if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or len(raw) != size:
                raise ValueError('observer chunk encoding corruption')
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('observer chunk digest corruption')
            records = json.loads(raw)
            if not isinstance(records, list) or len(records) != count:
                raise ValueError('observer chunk run-count corruption')
            position = first
            decoded = []
            for record in records:
                if not isinstance(record, list) or len(record) != (6 if version == 2 else 5):
                    raise ValueError('observer chunk row corruption')
                if version == 3:
                    record = EventJournal.complete_row(record)
                begin, repeat, *_ = EventSequence.decode(record)
                if begin != position:
                    raise ValueError('observer chunk run gap')
                position += repeat
                decoded.append(record)
            if position != first + logical:
                raise ValueError('observer chunk extent corruption')
            return decoded
        except (zlib.error, TypeError, json.JSONDecodeError) as error:
            raise ValueError('observer chunk corruption') from error

    @staticmethod
    def complete_row(row):
        for value in row[:4]: integer(value)
        if not isinstance(row[4], str):
            raise ValueError('observer chunk payload corruption')
        return (*row, checksum(*row))

    def rows(self, name, begin, end):
        if not self.compact:
            yield from self.db.execute('SELECT first_index,repeat_count,start_step,delta,payload,digest'
                ' FROM runs WHERE stream=? AND first_index<? AND first_index+repeat_count>? ORDER BY first_index',
                (name, end, begin))
            return
        for row in self.db.execute('SELECT first_index,logical_count,run_count,raw_bytes,payload,digest'
                ' FROM chunks WHERE stream=? AND first_index<? AND first_index+logical_count>? ORDER BY first_index',
                (name, end, begin)):
            yield from self.decode_chunk(row, self.version)
        chunk = self.chunks.get(name)
        if chunk is not None and chunk['first'] < end and chunk['first'] + chunk['count'] > begin:
            yield from (self.complete_row(json.loads(part)) for part in chunk['parts'])

    def lookup(self, name, index):
        if not self.compact:
            return self.db.execute('SELECT first_index,repeat_count,start_step,delta,payload,digest'
                ' FROM runs WHERE stream=? AND first_index<=? ORDER BY first_index DESC LIMIT 1', (name, index)).fetchone()
        chunk = self.chunks.get(name)
        if chunk is not None and chunk['first'] <= index:
            records = (self.complete_row(json.loads(part)) for part in chunk['parts'])
        else:
            row = self.db.execute('SELECT first_index,logical_count,run_count,raw_bytes,payload,digest'
                ' FROM chunks WHERE stream=? AND first_index<=? ORDER BY first_index DESC LIMIT 1', (name, index)).fetchone()
            if row is None:
                return None
            records = self.decode_chunk(row, self.version)
        return next((row for row in reversed(list(records)) if row[0] <= index), None)

    def finish(self):
        self.check()
        if not self.read_only:
            for sequence in self.streams.values(): sequence.flush()
            try:
                for name in list(self.chunks): self.flush_chunk(name)
                self.db.commit()
            except sqlite3.Error:
                self.failed = True
                raise
            self.pending_runs = 0
        table = 'chunks' if self.compact else 'runs'
        names = [row[0] for row in self.db.execute('SELECT DISTINCT stream FROM ' + table + ' ORDER BY stream')]
        stats = {name: dict(events=len(self.sequence(name)), runs=self.db.execute(
            'SELECT ' + ('SUM(run_count)' if self.compact else 'COUNT(*)') + ' FROM ' + table + ' WHERE stream=?', (name,)).fetchone()[0]) for name in names}
        return dict(format='npu-native-event-journal-v' + str(self.version), file=str(self.path), bytes=self.path.stat().st_size,
            sha256=self.digest(), streams=stats, lossless=True, lazy_slices=True, guest_writes=False)

    def digest(self):
        with self.path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()

    def close(self):
        if not self.closed:
            try:
                if not self.failed: self.finish()
            finally:
                self.db.close(); self.closed = True


class EventSequence(Sequence):
    def __init__(self, journal, name):
        self.journal, self.name = journal, name
        self.count = journal.stored_count(name)
        self.tail = None

    def __len__(self):
        self.journal.check()
        return self.count

    def append(self, event):
        self.journal.check(write=True)
        if not isinstance(event, dict) or 'step' not in event: raise ValueError('observer event requires step')
        start = integer(event['step'])
        payload = json.dumps({k: v for k, v in event.items() if k != 'step'},
            sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
        if len(payload) > MAX_PAYLOAD: raise ValueError('observer event too large')
        if self.count == MAX_INTEGER: raise OverflowError('observer event count')
        if self.tail is not None:
            first, count, old, delta, contents = self.tail
            proposed = start - old if count == 1 else delta
            if contents == payload and -MAX_INTEGER - 1 <= proposed <= MAX_INTEGER and start == old + proposed * count:
                self.tail = (first, count + 1, old, proposed, contents)
                self.count += 1
                return
            self.flush()
        self.tail = (self.count, 1, start, 0, payload)
        self.count += 1

    def flush(self):
        self.journal.check(write=True)
        if self.tail is None: return
        row = self.tail
        self.journal.append_run(self.name, row)
        self.tail = None

    @staticmethod
    def decode(row):
        if len(row) != 6:
            raise ValueError('observer run corruption')
        first, count, start, delta, payload, digest = row
        for value in (first, count, start, delta): integer(value)
        if count < 1 or first < 0 or not isinstance(payload, str) or not isinstance(digest, str):
            raise ValueError('observer run corruption')
        integer(start + (count - 1) * delta)
        if checksum(first, count, start, delta, payload) != digest:
            raise ValueError('observer run corruption')
        fields = json.loads(payload)
        if not isinstance(fields, dict) or 'step' in fields:
            raise ValueError('observer run fields corruption')
        return first, count, start, delta, fields

    def __getitem__(self, index):
        self.journal.check()
        if isinstance(index, slice): return EventView(self, range(*index.indices(self.count)))
        index = operator.index(index)
        if index < 0: index += self.count
        if not 0 <= index < self.count: raise IndexError(index)
        if self.tail is not None and index >= self.tail[0]:
            first, count, start, delta, payload = self.tail
            fields = json.loads(payload)
        else:
            row = self.journal.lookup(self.name, index)
            if row is None: raise ValueError('observer run missing')
            first, count, start, delta, fields = self.decode(row)
        if index >= first + count: raise ValueError('observer run gap')
        return dict(fields, step=start + (index - first) * delta)

    def __iter__(self): return self.iter_range(0, self.count)

    def iter_range(self, begin, end):
        self.journal.check()
        if begin >= end: return
        tail = self.tail
        cursor = self.journal.rows(self.name, begin, end)
        position = begin
        for row in cursor:
            first, count, start, delta, fields = self.decode(row)
            for index in range(max(begin, first), min(end, first + count)):
                if index != position: raise ValueError('observer run gap')
                position += 1
                yield dict(fields, step=start + (index - first) * delta)
        if tail is not None:
            first, count, start, delta, payload = tail
            fields = json.loads(payload)
            for index in range(max(begin, first), min(end, first + count)):
                if index != position: raise ValueError('observer tail gap')
                position += 1
                yield dict(fields, step=start + (index - first) * delta)
        if position != end: raise ValueError('observer truncated stream')


class EventView(Sequence):
    def __init__(self, sequence, indexes): self.sequence, self.indexes = sequence, indexes
    def __len__(self): return len(self.indexes)
    def __getitem__(self, index):
        if isinstance(index, slice): return EventView(self.sequence, self.indexes[index])
        return self.sequence[self.indexes[index]]
    def __iter__(self):
        if self.indexes.step == 1: return self.sequence.iter_range(self.indexes.start, self.indexes.stop)
        return (self.sequence[index] for index in self.indexes)
