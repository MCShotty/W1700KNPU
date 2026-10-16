"""Synthetic fault-oracle contracts; not a native fault-matrix verdict."""
import struct
import unittest

from unicorn import riscv_const as r
from test_bootstrap_native import ADM
from emulation_layout import STATE
from pcie_tail_trace import PcieTailTrace
import test_pcie_tail_trace as tail_fixture
from test_pcie_tail_native_controls import CASES, Injection, counts, expected_owner, expected_images


class TailFaultContractTests(unittest.TestCase):
    def fixture(self, stage=0, hif2=0):
        h, request, put, read = tail_fixture.TailTraceTests().fixture(stage, hif2)
        trace = PcieTailTrace(h, request)
        before = {base: read(base, len(data)) for base, data in trace.memory.items()}
        return h, trace, before, read, put

    def test_complete_distinct_matrix_and_original_prefix_counts(self):
        self.assertEqual(len(CASES), 12)
        self.assertEqual(len({case.name for case in CASES}), 12)
        for stage in range(3):
            _, trace, _, _, _ = self.fixture(stage)
            for case in CASES:
                want = (5 if stage == 2 else 2) if case.name in ('release-fault', 'unlock-neighbor') else (
                    1 if case.name in ('store-readback', 'late-packet-fault') else 0)
                published = want if case.name in ('release-fault', 'unlock-neighbor') else 0
                self.assertEqual(counts(trace, case), (want, published))

    def test_owner_retains_exact_stage_prefix_and_all_preimages(self):
        for stage in range(3):
            for hif2 in (0, 1):
                _, trace, _, read, _ = self.fixture(stage, hif2)
                before = read(trace.owner, 256)
                for case in CASES:
                    result = expected_owner(trace, before, case)
                    words = struct.unpack_from('<10I', result)
                    self.assertEqual(len(result), 256)
                    self.assertEqual(words[2], 1)
                    if case.boundary == 'entry':
                        want = bytearray(before)
                        want[8:12] = bytes([1, 0, 0, 0])
                        self.assertEqual(result, want)
                    else:
                        self.assertEqual(result[40:], trace.owner_expected[40:])
                        self.assertEqual(words[4:6], (stage, (1 << (stage + 1)) - 1))
                        if case.boundary == 'release':
                            self.assertEqual(words[3], 0)
                            self.assertEqual(words[6:9], ((1 << (stage + 1)) - 1, trace.last, trace.last))
                        else:
                            count = 1 if case.boundary == 'publish' else 0
                            self.assertEqual(words[3], 1)
                            self.assertEqual(words[6:9], ((1 << stage) - 1, trace.first + count, trace.first))
                    self.assertEqual(read(trace.owner, 256), before)

    def test_full_memory_is_only_original_prefix_sequence_faults_and_injection(self):
        for stage in range(3):
            for hif2 in (0, 1):
                _, trace, before, _, _ = self.fixture(stage, hif2)
                for case in CASES:
                    injection = dict(address='0x200d45ac', bytes=4, after='01000000')
                    actual = expected_images(trace, before, case, [injection])
                    want = {base: bytearray(data) for base, data in before.items()}
                    count = len(trace.events) if case.boundary == 'release' else (1 if case.boundary == 'publish' else 0)
                    changes = list(trace.events[:count]) + [(int(trace.changes[-1]['address'], 16), 4, 80)]
                    changes += [(address, 4, 1) for address in (ADM, ADM + 4, ADM + 8, STATE + 16)]
                    changes += [(0x200d45ac, 4, 1)]
                    for address, width, value in changes:
                        base = next(base for base, data in want.items() if base <= address < base + len(data))
                        want[base][address - base:address - base + width] = value.to_bytes(width, 'little')
                    self.assertEqual(actual, want)
                    self.assertTrue(all(isinstance(data, bytes) for data in before.values()))
                    self.assertEqual(sum(map(len, actual.values())), 868352)

    def test_each_injection_is_exactly_one_explicit_fixture_mutation(self):
        for case in CASES:
            h, trace, _, _, _ = self.fixture()
            h.cpu.reg_read.side_effect = {r.UC_RISCV_REG_A0: 0x3e902cf0,
                r.UC_RISCV_REG_A1: 0x200d4580, r.UC_RISCV_REG_A2: 4,
                r.UC_RISCV_REG_MSTATUS: 0}.__getitem__
            injection = Injection(h, trace, case)
            injection.instruction(h.cpu, 0, 0, None)
            injection.instruction(h.cpu, 0, 0, None)
            self.assertTrue(injection.injected)
            self.assertEqual(len(injection.memory) + len(injection.registers), 1)
            self.assertEqual(h.cpu.mem_write.call_count + h.cpu.reg_write.call_count, 1)
            for row in injection.memory:
                self.assertEqual(row['bytes'], 4)
                self.assertEqual(len(bytes.fromhex(row['before'])), 4)
                self.assertEqual(len(bytes.fromhex(row['after'])), 4)


if __name__ == '__main__': unittest.main()
