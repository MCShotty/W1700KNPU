"""Snapshot capture mechanics, not a production ownership/initialization proof."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.dont_write_bytecode = True
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32
from unicorn import riscv_const as r
from native_prefix_snapshot import ROOT, capture, source_inputs


class NativePrefixSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='prefix-capture-unit-', dir=ROOT / '.local')
        self.addCleanup(self.temp.cleanup)
        self.destination = Path(self.temp.name) / 'snapshot'
        cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        cpu.mem_map(0x1000, 0x2000)
        cpu.mem_write(0x1000, b'\xa5' * 0x2000)
        cpu.reg_write(r.UC_RISCV_REG_A0, 123)
        cpu.reg_write(r.UC_RISCV_REG_SP, 0x2000)
        self.h = SimpleNamespace(cpu=cpu, request_address=0x1100, hart=0,
                                 clear_count=0, l2_clear_active=False, l2_writes=0)

    def test_capture_does_not_modify_native_memory_or_registers(self):
        before = bytes(self.h.cpu.mem_read(0x1000, 0x2000))
        context = bytes(self.h.cpu.context_save())
        path = capture(self.h, self.destination, [1, 2, 3], {}, origin='synthetic-unit-only')
        self.assertEqual(bytes(self.h.cpu.mem_read(0x1000, 0x2000)), before)
        self.assertEqual(bytes(self.h.cpu.context_save()), context)
        record = json.loads(path.read_bytes())
        self.assertEqual(record['origin'], 'synthetic-unit-only')
        self.assertFalse(record['fresh_loader_allocator_caller_proof'])
        self.assertEqual(len(record['regions']), 1)
        for item in [record['context'], *record['regions']]:
            data = (self.destination / item['file']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), item['sha256'])
        self.assertEqual(record['context']['size'], len(context))

    def test_existing_destination_is_not_overwritten(self):
        self.destination.mkdir()
        marker = self.destination / 'protected.txt'
        marker.write_text('keep')
        with self.assertRaises(FileExistsError):
            capture(self.h, self.destination, [], {}, origin='synthetic-unit-only')
        self.assertEqual(marker.read_text(), 'keep')

    def test_imported_replay_sources_are_bound_without_rebasing_old_hashes(self):
        import native_prefix_snapshot as module
        name = str(Path(module.__file__).relative_to(ROOT))
        inputs = source_inputs({}, [module, SimpleNamespace(), SimpleNamespace(__file__='/not/project.py')])
        self.assertEqual(set(inputs), {name})
        self.assertEqual(inputs[name], hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest())
        with self.assertRaisesRegex(AssertionError, 'producer-source-drift'):
            source_inputs({name: '0' * 64}, [module])

    def test_producer_drift_is_rejected_before_capture_creates_files(self):
        import native_prefix_snapshot as module
        name = str(Path(module.__file__).relative_to(ROOT))
        with self.assertRaisesRegex(AssertionError, 'producer-source-drift'):
            capture(self.h, self.destination, [], {name: '0' * 64}, origin='synthetic-unit-only')
        self.assertFalse(self.destination.exists())

    def test_output_outside_build_storage_is_rejected(self):
        destination = ROOT / 'docs' / self.destination.parent.name
        self.assertFalse(destination.exists())
        with self.assertRaises(AssertionError):
            capture(self.h, destination, [], {}, origin='synthetic-unit-only')
        self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
