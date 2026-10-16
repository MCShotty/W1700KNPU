"""Strict artifact/source validation before any captured CPU state is restored."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32
from unicorn import riscv_const as r

from native_prefix_snapshot import capture
import restore_native_prefix as restored
import test_desc10_native_controls as desc10


class RestorePrefixTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='strict-prefix-unit-', dir=restored.ROOT / '.local')
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.pair = self.directory / 'pair'
        self.pair.mkdir()
        for name in ('CODE.bin', 'DATA.bin', 'component.elf', 'host.so'):
            (self.pair / name).write_bytes(name.encode())
        component, host = [(self.pair / name).relative_to(restored.ROOT).as_posix()
                           for name in ('component.elf', 'host.so')]
        self.manifest = {'inputs': {}, 'code': {'sha256': restored.digest(self.pair / 'CODE.bin')},
            'data': {'sha256': restored.digest(self.pair / 'DATA.bin')},
            'components': {'example': {'sha256': restored.digest(self.pair / 'component.elf')}},
            'symbol_files': {'example': component}, 'host_files': [host],
            'host_inputs': {host: restored.digest(self.pair / 'host.so')}}
        (self.pair / 'manifest.json').write_text(json.dumps(self.manifest))
        inputs = {}
        for name in ('CODE-copied.bin', 'DATA-published.bin'):
            path = self.directory / name
            path.write_bytes(name.encode())
            inputs[path.relative_to(restored.ROOT).as_posix()] = restored.digest(path)
        cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        cpu.mem_map(0x1000, 0x1000)
        cpu.mem_write(0x1000, b'\xa5' * 0x1000)
        cpu.reg_write(r.UC_RISCV_REG_A0, 123)
        cpu.reg_write(r.UC_RISCV_REG_SP, 0x2000)
        self.h = SimpleNamespace(cpu=cpu, request_address=0x1100, hart=0, clear_count=77,
            l2_clear_active=False, l2_writes=19, last_csr=(1, 2), unmodeled=None, check_hooks=Mock())
        self.origin = 'actual-provider-allocator-caller-before-DESC10'
        self.snapshot = capture(self.h, self.directory / 'capture', [1, 2, 3], inputs, origin=self.origin)
        self.record = json.loads(self.snapshot.read_text())
        self.load = patch.object(restored.raw, 'load', return_value=(self.h, [], {}, self.manifest))
        self.loader = self.load.start()
        self.addCleanup(self.load.stop)

    def write_record(self):
        self.snapshot.write_text(json.dumps(self.record))

    def invoke(self):
        return restored.fixture(self.pair, self.snapshot, origin=self.origin)

    def test_exact_capture_restores_and_remains_diagnostic(self):
        self.h.cpu.mem_write(0x1000, bytes(0x1000))
        self.h.cpu.reg_write(r.UC_RISCV_REG_A0, 456)
        self.h.hart, self.h.clear_count = 7, 0
        h, restore, record, inputs = self.invoke()
        self.assertIs(h, self.h)
        self.assertEqual(bytes(h.cpu.mem_read(0x1000, 0x1000)), b'\xa5' * 0x1000)
        self.assertEqual(h.cpu.reg_read(r.UC_RISCV_REG_A0), 123)
        self.assertEqual((h.hart, h.clear_count, h.last_csr), (0, 77, (1, 2)))
        self.assertFalse(record['fresh_loader_allocator_caller_proof'])
        self.assertTrue(all(restored.digest(restored.ROOT / n) == d for n, d in inputs.items()))
        for name in ('manifest.json', 'CODE.bin', 'DATA.bin', 'component.elf', 'host.so'):
            self.assertEqual(inputs[(self.pair / name).relative_to(restored.ROOT).as_posix()],
                             restored.digest(self.pair / name))
        h.cpu.reg_write(r.UC_RISCV_REG_A0, 789)
        restore()
        self.assertEqual(h.cpu.reg_read(r.UC_RISCV_REG_A0), 123)

    def test_former_observer_exceptions_fail_before_loading(self):
        for name in ('tests/npu/test_boot_irq_installation.py', 'tests/npu/cold_wire_native.py'):
            with self.subTest(name=name):
                self.record['inputs'][name] = '0' * 64
                self.write_record()
                with self.assertRaisesRegex(AssertionError, 'captured-input-drift'):
                    self.invoke()
                del self.record['inputs'][name]
        self.loader.assert_not_called()

    def test_pair_binary_and_symbol_drift_fail_before_restoring(self):
        for name in ('CODE.bin', 'DATA.bin', 'component.elf', 'host.so'):
            with self.subTest(name=name):
                path = self.pair / name
                original = path.read_bytes()
                try:
                    path.write_bytes(b'corrupt-artifact')
                    with self.assertRaisesRegex(AssertionError, 'pair-artifact-drift'):
                        self.invoke()
                finally:
                    path.write_bytes(original)
        self.h.check_hooks.assert_not_called()

    def test_manifest_descriptor_and_external_component_paths_are_rejected(self):
        changed = dict(self.manifest, code={'sha256': '0' * 64})
        with self.assertRaisesRegex(AssertionError, 'pair-manifest-descriptor-drift'):
            restored.pair_artifact_inputs(self.pair, changed)
        outside = self.directory / 'outside.elf'
        outside.write_bytes(b'outside')
        self.manifest['symbol_files']['example'] = outside.relative_to(restored.ROOT).as_posix()
        self.manifest['components']['example']['sha256'] = restored.digest(outside)
        (self.pair / 'manifest.json').write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(AssertionError, 'pair-artifact-path'):
            restored.pair_artifact_inputs(self.pair, self.manifest)

    def test_input_path_escape_is_rejected_before_loading(self):
        self.record['inputs']['../outside'] = '0' * 64
        self.write_record()
        with self.assertRaises(AssertionError):
            self.invoke()
        self.loader.assert_not_called()

    def test_pair_source_disagreement_is_rejected(self):
        name = next(iter(self.record['inputs']))
        self.loader.return_value = (self.h, [], {}, {'inputs': {name: '0' * 64}})
        with self.assertRaisesRegex(AssertionError, 'pair-input-drift'):
            self.invoke()
        self.h.check_hooks.assert_not_called()

    def test_corrupt_region_is_rejected_without_restore(self):
        region = self.snapshot.parent / self.record['regions'][0]['file']
        region.write_bytes(bytes(0x1000))
        with self.assertRaises(AssertionError):
            self.invoke()
        self.h.check_hooks.assert_not_called()

    def test_context_architecture_mismatch_is_rejected(self):
        self.record['context']['arch'] ^= 1
        self.write_record()
        with self.assertRaises(AssertionError):
            self.invoke()
        self.h.check_hooks.assert_not_called()

    def test_unknown_observer_field_is_rejected_before_restore(self):
        self.record['observer']['cold_request'] = True
        self.write_record()
        self.h.cpu.reg_write(r.UC_RISCV_REG_A0, 456)
        with self.assertRaisesRegex(AssertionError, 'unknown-observer-field'):
            self.invoke()
        self.assertEqual(self.h.cpu.reg_read(r.UC_RISCV_REG_A0), 456)
        self.h.check_hooks.assert_not_called()

    def test_desc10_wrapper_uses_strict_origin_and_no_drift(self):
        marker = (self.h, Mock(), self.record, {})
        with patch.object(desc10.captured, 'fixture', return_value=marker) as fixture:
            h, restore, record, inputs, drift = desc10.fixture(self.pair, self.snapshot)
        fixture.assert_called_once_with(self.pair, self.snapshot, origin=self.origin)
        self.assertEqual(drift, {})
        self.assertIs(h, self.h)
        self.assertIn('tests/npu/test_desc10_native_controls.py', inputs)


if __name__ == '__main__':
    unittest.main()
