"""Exact journal controls; no native, firmware, hardware or caller qualification."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from native_event_journal import EventJournal, MAX_INTEGER


class EventJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'events.sqlite'
        self.log = EventJournal(self.path)
        self.addCleanup(self.log.close)

    def test_exact_fields_steps_repeats_and_independent_streams(self):
        events = [dict(step=i * 2, kind='paused', pc='0x8404308c', hart=0) for i in range(200)]
        events += [dict(step=400, kind='mmio-read', address='0x1ec03048', value=65536)]
        events += [dict(step=501 + i * 3, kind='paused', pc='0x8404308c', hart=0) for i in range(31)]
        sequence = self.log.sequence('events', events)
        self.log.sequence('mmio', events[200:201])
        self.assertEqual(list(sequence), events)
        self.assertEqual(self.log.finish()['streams'], {'events': {'events': 232, 'runs': 3}, 'mmio': {'events': 1, 'runs': 1}})
        self.assertEqual(list(sequence), events)

    def test_indexes_lazy_slices_negative_steps_and_views_of_views(self):
        events = [dict(step=i * 2, kind='paused', pc='x') for i in range(30)]
        sequence = self.log.sequence('events', events)
        for index in range(-30, 30): self.assertEqual(sequence[index], events[index])
        for selection in (slice(None), slice(4, 15), slice(None, None, -1), slice(29, 1, -3), slice(4, 4), slice(-9, -2)):
            self.assertEqual(list(sequence[selection]), events[selection])
        self.assertEqual(list(sequence[2:28:2][::-1]), events[2:28:2][::-1])
        with self.assertRaises(IndexError): sequence[30]
        with self.assertRaises(ValueError): sequence[::0]

    def test_mixed_types_progression_changes_and_extreme_steps_are_exact(self):
        events = [dict(step=step, value=value) for step, value in
            ((1, True), (2, 1), (3, 1.0), (4, '1'), (4, '1'), (6, '1'), (-9, '1'), (-10, None),
             (-MAX_INTEGER - 1, 0), (MAX_INTEGER, 0))]
        sequence = self.log.sequence('events', events)
        self.assertEqual(json.dumps(list(sequence), sort_keys=True), json.dumps(events, sort_keys=True))

    def test_append_snapshots_fields_and_does_not_retain_mutable_aliases(self):
        event = dict(step=1, payload={'x': [1]})
        sequence = self.log.sequence('events', [event])
        event['payload']['x'].append(2)
        returned = sequence[0]; returned['payload']['x'].append(3)
        self.assertEqual(sequence[0], dict(step=1, payload={'x': [1]}))

    def test_existing_file_and_symlink_are_never_overwritten(self):
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError): EventJournal(self.path)
        self.assertEqual(self.path.read_bytes(), before)
        link = self.path.with_name('link'); link.symlink_to(self.path)
        with self.assertRaises(ValueError): EventJournal(link)

    def test_reopen_reads_every_record_and_refuses_writes(self):
        events = [dict(step=i, kind='paused') for i in range(100)]
        self.log.sequence('events', events); self.log.close()
        reader = EventJournal(self.path, read_only=True)
        self.addCleanup(reader.close)
        self.assertEqual(list(reader.sequence('events')), events)
        with self.assertRaises(ValueError): reader.sequence('events').append(events[0])

    def test_corrupt_missing_or_modified_run_is_rejected(self):
        sequence = self.log.sequence('events', [dict(step=i, kind='p') for i in range(10)])
        self.log.finish()
        self.log.db.execute("UPDATE runs SET payload='{}' WHERE stream='events'")
        with self.assertRaisesRegex(ValueError, 'corruption'): list(sequence)

    def test_deleted_run_cannot_silently_shorten_active_sequence(self):
        sequence = self.log.sequence('events', [dict(step=i, kind=str(i)) for i in range(3)])
        self.log.finish()
        self.log.db.execute("DELETE FROM runs WHERE stream='events' AND first_index=1")
        with self.assertRaisesRegex(ValueError, 'gap'): list(sequence)

    def test_storage_limit_raises_without_lossy_fallback(self):
        path = self.path.with_name('small.sqlite')
        small = EventJournal(path, max_bytes=65536)
        sequence = small.sequence('events')
        with self.assertRaises(sqlite3.OperationalError):
            for i in range(1000): sequence.append(dict(step=i, content=str(i) * 1000))
        self.assertTrue(small.failed)
        with self.assertRaisesRegex(RuntimeError, 'storage failed'): small.finish()
        with self.assertRaisesRegex(RuntimeError, 'storage failed'): sequence[0]
        small.close()
        self.assertTrue(small.closed)

    def test_invalid_or_nonfinite_records_fail_before_append(self):
        sequence = self.log.sequence('events')
        for event in ({}, dict(step=True), dict(step=MAX_INTEGER + 1), dict(step=0, x=float('nan'))):
            with self.assertRaises(ValueError): sequence.append(event)
        self.assertEqual(len(sequence), 0)

    def test_million_event_run_is_lossless_and_uses_one_tail(self):
        sequence = self.log.sequence('events')
        want = hashlib.sha256()
        for i in range(1000000):
            event = dict(step=2 * i + 7, kind='paused', pc='0x8404308c', hart=0)
            sequence.append(event)
            want.update(json.dumps(event, sort_keys=True).encode() + b'\n')
        self.assertEqual(sequence.tail[:4], (0, 1000000, 7, 2))
        actual = hashlib.sha256()
        for event in sequence: actual.update(json.dumps(event, sort_keys=True).encode() + b'\n')
        self.assertEqual(actual.digest(), want.digest())
        self.assertEqual(self.log.finish()['streams']['events'], {'events': 1000000, 'runs': 1})
        self.assertLess(self.path.stat().st_size, 65536)


if __name__ == '__main__': unittest.main()
