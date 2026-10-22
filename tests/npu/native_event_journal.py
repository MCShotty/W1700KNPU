"""Lossless append-only observer events with lazy indexed reads and bounded RAM.

Identical JSON fields and an exact integer step progression form a run. SQLite
holds completed runs; only one tail per stream stays in Python. Nothing samples
or drops events. Storage exhaustion raises, rather than weakening observation.
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

MAX_INTEGER = (1 << 63) - 1
MAX_PAYLOAD = 65536


def integer(value):
    if type(value) is not int or not -MAX_INTEGER - 1 <= value <= MAX_INTEGER:
        raise ValueError('observer integer must fit signed64 exactly')
    return value


def checksum(first, count, start, delta, payload):
    return hashlib.sha256(struct.pack('<4q', first, count, start, delta) + payload.encode('ascii')).hexdigest()


class EventJournal:
    def __init__(self, path, *, max_bytes=64 * 1024 * 1024, read_only=False):
        self.path = Path(path).absolute()
        if self.path.is_symlink(): raise ValueError('observer journal alias')
        self.read_only, self.thread, self.closed = read_only, threading.get_ident(), False
        self.failed = False
        self.streams, self.pending_runs = {}, 0
        if read_only:
            self.db = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
            if self.db.execute('SELECT format FROM metadata').fetchall() != [(1,)]:
                raise ValueError('observer journal format')
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
            self.db.executescript('CREATE TABLE metadata(format INTEGER NOT NULL); INSERT INTO metadata VALUES(1);'
                'CREATE TABLE runs(stream TEXT NOT NULL, first_index INTEGER NOT NULL,'
                ' repeat_count INTEGER NOT NULL, start_step INTEGER NOT NULL, delta INTEGER NOT NULL,'
                ' payload TEXT NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(stream,first_index));')
            self.db.commit()
        self.db.execute('PRAGMA cache_size=-1024')
        self.db.execute('PRAGMA temp_store=FILE')

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

    def finish(self):
        self.check()
        if not self.read_only:
            for sequence in self.streams.values(): sequence.flush()
            try: self.db.commit()
            except sqlite3.Error:
                self.failed = True
                raise
            self.pending_runs = 0
        names = [row[0] for row in self.db.execute('SELECT DISTINCT stream FROM runs ORDER BY stream')]
        stats = {name: dict(events=len(self.sequence(name)), runs=self.db.execute(
            'SELECT COUNT(*) FROM runs WHERE stream=?', (name,)).fetchone()[0]) for name in names}
        return dict(format='npu-native-event-journal-v1', file=str(self.path), bytes=self.path.stat().st_size,
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
        self.count = journal.db.execute('SELECT COALESCE(SUM(repeat_count),0) FROM runs WHERE stream=?', (name,)).fetchone()[0]
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
        try:
            self.journal.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?)',
                (self.name, *row, checksum(*row)))
        except sqlite3.Error:
            self.journal.failed = True
            raise
        self.tail = None
        self.journal.pending_runs += 1
        if self.journal.pending_runs >= 64:
            try: self.journal.db.commit()
            except sqlite3.Error:
                self.journal.failed = True
                raise
            self.journal.pending_runs = 0

    @staticmethod
    def decode(row):
        first, count, start, delta, payload, digest = row
        if count < 1 or first < 0 or checksum(first, count, start, delta, payload) != digest:
            raise ValueError('observer run corruption')
        return first, count, start, delta, json.loads(payload)

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
            row = self.journal.db.execute('SELECT first_index,repeat_count,start_step,delta,payload,digest'
                ' FROM runs WHERE stream=? AND first_index<=? ORDER BY first_index DESC LIMIT 1',
                (self.name, index)).fetchone()
            if row is None: raise ValueError('observer run missing')
            first, count, start, delta, fields = self.decode(row)
        if index >= first + count: raise ValueError('observer run gap')
        return dict(fields, step=start + (index - first) * delta)

    def __iter__(self): return self.iter_range(0, self.count)

    def iter_range(self, begin, end):
        self.journal.check()
        if begin >= end: return
        tail = self.tail
        cursor = self.journal.db.execute('SELECT first_index,repeat_count,start_step,delta,payload,digest'
            ' FROM runs WHERE stream=? AND first_index<? AND first_index+repeat_count>? ORDER BY first_index',
            (self.name, end, begin))
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
