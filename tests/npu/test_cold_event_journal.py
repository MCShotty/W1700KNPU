"""Synthetic factory wiring controls, not original native or caller execution."""
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest

import cold_wire_native as cold
from native_event_journal import EventJournal


class ColdEventJournalTests(unittest.TestCase):
    @staticmethod
    def fake_parent(instance, *args, **kwargs):
        instance.cpu = object()
        instance.events = [dict(step=1, kind='entry')]
        instance.mmio = [dict(step=2, kind='mmio-read', address='x')]
        instance.csr_events = []

    def test_default_keeps_existing_list_observer_and_factory_arguments(self):
        with patch.object(cold.ProviderRequest, '__init__', self.fake_parent), patch.object(cold, 'CsrSampler'):
            h = cold.ColdProviderRequest('paths', 'parts', request=123)
        self.assertIsInstance(h.events, list)
        self.assertIsInstance(h.mmio, list)
        self.assertEqual(h.events, [dict(step=1, kind='entry')])

    def test_explicit_journal_preserves_initial_streams_and_new_events(self):
        with tempfile.TemporaryDirectory() as directory:
            log = EventJournal(Path(directory) / 'events.sqlite')
            try:
                with patch.object(cold.ProviderRequest, '__init__', self.fake_parent), patch.object(cold, 'CsrSampler'):
                    h = cold.ColdProviderRequest('paths', 'parts', request=123, event_journal=log)
                h.events.append(dict(step=3, kind='paused', pc='x'))
                self.assertEqual(list(h.events), [dict(step=1, kind='entry'), dict(step=3, kind='paused', pc='x')])
                self.assertEqual(list(h.mmio), [dict(step=2, kind='mmio-read', address='x')])
                self.assertEqual(len(h.csr_events), 0)
                self.assertEqual(log.finish()['streams']['events']['events'], 2)
            finally: log.close()


if __name__ == '__main__': unittest.main()
