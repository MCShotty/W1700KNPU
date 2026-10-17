"""Pure fault-projection checks; never native fault execution evidence."""
import struct
import unittest

import test_inode_trace as nominal
from test_inode_native_controls import (CASES, counts, expected_owner, expected_setup,
                                       expected_memory, expected_code, FaultTrace, CODE, ADM, STATE, r)
from inode_trace import InodeTrace


class InodeFaultContractTests(unittest.TestCase):
    def fixture(self, stage):
        h, request, put, read, registers = nominal.InodeTraceTests().fixture(stage, 1)
        trace = InodeTrace(h, request)
        before = {base: bytes(h.cpu.mem_read(base, len(data))) for base, data in trace.memory.items()}
        return trace, before, bytes(h.cpu.mem_read(trace.owner, 4372)), bytes(h.cpu.mem_read(CODE, 0x200000)), read

    def test_all_twelve_cases_are_explicit_and_required_for_both_stages(self):
        self.assertEqual(len(CASES), 12)
        self.assertEqual(len({case.name for case in CASES}), 12)
        self.assertEqual({case.boundary for case in CASES}, {'entry', 'reserve', 'publish', 'release'})
        for stage in (0, 1):
            trace, _, _, _, _ = self.fixture(stage)
            for case in CASES:
                wanted = len(trace.events) if case.boundary == 'release' else case.stores
                self.assertEqual(counts(trace, case)[0], wanted)

    def test_entry_fault_only_marks_the_preexisting_owner(self):
        for stage in (0, 1):
            trace, _, before, _, _ = self.fixture(stage)
            for case in CASES[:2]:
                wanted = bytearray(before)
                struct.pack_into('<I', wanted, 8, 1)
                self.assertEqual(expected_owner(trace, before, case), wanted)

    def test_partial_fault_retains_captured_preimages_and_exact_progress(self):
        for stage in (0, 1):
            trace, _, before, _, _ = self.fixture(stage)
            for case in CASES[2:]:
                owner = expected_owner(trace, before, case)
                words = struct.unpack_from('<10I', owner)
                committed, published = counts(trace, case)
                self.assertEqual(words[2], 1)
                self.assertEqual(words[3], int(case.boundary != 'release'))
                self.assertEqual(words[4], stage)
                self.assertEqual(words[6], (1 << (stage + int(case.boundary == 'release'))) - 1)
                self.assertEqual(words[7:10], (trace.first + committed, trace.first + published, trace.last))
                self.assertEqual(owner[40:], trace.owner_expected[40:])

    def test_failed_setup_never_advances_constructor_history(self):
        for stage in (0, 1):
            trace, _, _, _, _ = self.fixture(stage)
            setup = expected_setup(trace, [])
            self.assertEqual(struct.unpack_from('<2I', setup), (1, 1))
            self.assertEqual(struct.unpack_from('<I', setup, 404)[0], stage)
            altered = expected_setup(trace, [dict(address=hex(trace.setup + 24), bytes=4, after='05000000')])
            self.assertEqual(struct.unpack_from('<I', altered, 24)[0], 5)

    def test_memory_uses_original_prefix_and_one_explicit_injection(self):
        for stage in (0, 1):
            trace, before, _, _, _ = self.fixture(stage)
            case = next(case for case in CASES if case.name == 'store-readback')
            _, address, width, value = trace.events[0]
            injection = dict(address=hex(address), bytes=4, after=struct.pack('<I', value ^ 1).hex())
            memory = expected_memory(trace, before, case, [injection])
            def read(location, size):
                base = next(base for base, data in memory.items() if base <= location and location + size <= base + len(data))
                return bytes(memory[base][location - base:location - base + size])
            self.assertEqual(read(address, 4), bytes.fromhex(injection['after']))
            for location in (ADM, ADM + 4, ADM + 8, STATE + 16): self.assertEqual(read(location, 4), b'\x01\0\0\0')
            self.assertEqual(read(trace.h.rv.symbols['npu_emulation_control_v2_state'] + 16, 4),
                             struct.pack('<I', trace.request[6]))

    def test_entry_private_projection_does_not_invent_neighbor_capture(self):
        for stage in (0, 1):
            trace, _, owner_before, code_before, _ = self.fixture(stage)
            case = CASES[0]
            owner, setup = expected_owner(trace, owner_before, case), expected_setup(trace, [])
            code = expected_code(trace, code_before, owner, setup, case, [])
            self.assertEqual(code[trace.owner - CODE:trace.owner - CODE + 4372], owner)
            table = trace.h.inode.elf.get_section_by_name('.symtab')
            for name in ('neighbors_captured', 'flag_neighbors', 'icv_neighbors.0', 'icv_neighbors.1'):
                entry = table.get_symbol_by_name(name)[0]
                offset, size = entry['st_value'] - CODE, entry['st_size']
                self.assertEqual(code[offset:offset + size], code_before[offset:offset + size])

    def test_release_checks_exact_case_specific_interrupt_state(self):
        for stage in (0, 1):
            for case in CASES[2:]:
                h, request, _, _, registers = nominal.InodeTraceTests().fixture(stage, 1)
                trace = FaultTrace(h, request, case)
                expected = 8 if case.name == 'late-IRQ' else 0
                registers[r.UC_RISCV_REG_MSTATUS] = expected
                trace.code(h.cpu, 0x8400651c, 4, None)
                self.assertEqual(trace.release_interrupts, [dict(mstatus=expected, interrupt=trace.interrupt_before)])
                for register in (r.UC_RISCV_REG_MSTATUS, r.UC_RISCV_REG_MIE, r.UC_RISCV_REG_MTVEC):
                    before = registers[register]
                    registers[register] ^= 8
                    with self.assertRaises(AssertionError): trace.code(h.cpu, 0x8400651c, 4, None)
                    registers[register] = before
                h.cpu.mem_write.assert_not_called()
                h.cpu.reg_write.assert_not_called()


if __name__ == '__main__': unittest.main()
