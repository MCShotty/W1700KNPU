"""Synthetic oracle controls only; no native owner or caller admission."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import io
import struct
import subprocess
import tempfile
import unittest

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, riscv_const as r
from inode_trace import InodeTrace, original_events, CODE, LOCKS, SAVED, END, STACK_TOPS
import test_pcie_tail_trace as tail_fixture
from pcie_tail_trace import PcieTailTrace


class InodeTraceTests(unittest.TestCase):
    def fixture(self, stage=0, hif2=0):
        parent = tail_fixture.TailTraceTests()
        h, request, put, read = parent.fixture(2, hif2, code_bytes=0x200000)
        tail = PcieTailTrace(h, request)
        parent.finish_fixture(tail, put)
        owner, next_address = 0x840f3000, 0x840f3000 + 4372
        fields = {'npu_emulation_inode_state': (owner, 4372)}
        for name, size in (('npu_emulation_inode_running', 4), ('phase', 4), ('lock_owned', 1),
            ('neighbors_captured', 1), ('icv_neighbors.0', 4), ('icv_neighbors.1', 4),
            ('flag_neighbors', 36), ('plan', 188), ('held_setup', 412)):
            next_address = (next_address + 3) & ~3
            fields[name] = (next_address, size)
            next_address += size
        sites = (0xe0c4, 0xe0ce, 0xe0d8, 0xe0e0, 0xe0e8, 0xe0f0, 0xe178, 0xe180, 0xe18a, 0xe196, 0xe1b4)
        symbols = {name: address for name, (address, _) in fields.items()}
        symbols |= {f'npu_emulation_inode_{site:x}_store': 0x840f2000 + index * 16 for index, site in enumerate(sites)}
        symbols |= {'npu_emulation_inode_callback': 0x840f1000, 'npu_original_inode_callback': 0x840f1100}
        table = SimpleNamespace(get_symbol_by_name=lambda name: [{'st_value': fields[name][0], 'st_size': fields[name][1]}]
                                if name in fields else None)
        section = {'sh_flags': 3, 'sh_addr': owner, 'sh_size': 0x1800}
        h.inode = SimpleNamespace(symbols=symbols, elf=SimpleNamespace(
            get_section_by_name=lambda name: table, iter_sections=lambda: iter([section])))
        put(0x8401cfb8, struct.pack('<2I', 0x109, 0x3e8bc470))
        put(0x3e902ac0, struct.pack('<I', 0x3e8bc470))
        registers = {register: 0x51010000 + index * 0x101 for index, register in enumerate(SAVED)}
        registers |= {r.UC_RISCV_REG_PC: END, r.UC_RISCV_REG_SP: STACK_TOPS[0] - 0x1000,
            r.UC_RISCV_REG_MSTATUS: 0, r.UC_RISCV_REG_MIE: 0x800, r.UC_RISCV_REG_MTVEC: 0x84004100}
        h.cpu.reg_read.side_effect = registers.__getitem__
        h.cpu.hook_add.side_effect = range(1, 100)
        h.run = Mock(return_value=END)
        request[6] += 1
        request[11:14] = [0x12, 24, 0]
        if stage:
            first = InodeTrace(h, request)
            self.finish_fixture(first, put)
            request[6] += 1
            request[11] = 0x17
        return h, request, put, read, registers

    def finish_fixture(self, trace, put):
        for base, contents in trace.memory.items(): put(base, contents)
        put(CODE, bytes(trace.code_expected[CODE]))
        trace.stores = list(trace.events)
        trace.locks = [(LOCKS[0], 4, 0x40), (LOCKS[1], 4, 0)]
        trace.entries = ['callback', 'wrapper', 'helper', 'release']
        trace.returns = [dict(pc=END, saved=trace.saved_before, sp=STACK_TOPS[0] - 0x1000,
            mstatus=0, interrupt=trace.interrupt_before)]

    def test_literal_original_site_and_dynamic_counts(self):
        first, second = original_events(0), original_events(1)
        self.assertEqual(len(first), 1030)
        self.assertEqual(len(second), 6)
        self.assertEqual([event[0] for event in first[:3]], [0x8400e178, 0x8400e180, 0x8400e18a])
        self.assertEqual(first[3], (0x8400e196, 0x3e8bc470, 4, 0))
        self.assertEqual(first[-2], (0x8400e196, 0x3e8bd474, 4, 0))
        self.assertEqual(first[-1], (0x8400e1b4, 0x3e9046f7, 1, 0))
        self.assertEqual(second[-1], (0x8400e0f0, 0x3e9046e0, 1, 1))

    def test_both_stages_and_profiles_project_without_guest_writes(self):
        for stage in (0, 1):
            for hif2 in (0, 1):
                h, request, put, _, _ = self.fixture(stage, hif2)
                trace = InodeTrace(h, request)
                self.assertEqual(sum(len(data) for data in trace.memory.values()), 868352)
                self.assertEqual(len(trace.owner_expected), 4372)
                self.finish_fixture(trace, put)
                trace.validate()
                h.cpu.mem_write.assert_not_called()
                h.cpu.reg_write.assert_not_called()

    def test_bad_identity_history_and_scalar_cannot_project(self):
        for index, value in ((0, 0), (4, 79), (6, 80), (7, 5), (9, 5), (11, 0x10), (12, 0), (13, 1), (14, 1)):
            h, request, _, _, _ = self.fixture()
            request[index] = value
            with self.assertRaises(AssertionError): InodeTrace(h, request)
        for offset, value in ((4, 1), (8, 65535), (104, 7), (120, 13), (360, 5),
                              (380, 2), (396, 2), (404, 1), (408, 1)):
            h, request, put, _, _ = self.fixture()
            put(h.rv.symbols['npu_emulation_cold_setup_state'] + offset, struct.pack('<I', value))
            with self.assertRaises(AssertionError): InodeTrace(h, request)

    def test_wrong_fixed_lookup_or_prior_owner_cannot_project(self):
        for address in (0x8401cfb8, 0x8401cfbc, 0x3e902ac0):
            h, request, put, _, _ = self.fixture()
            put(address, struct.pack('<I', 0))
            with self.assertRaises(AssertionError): InodeTrace(h, request)
        for stage in (0, 1):
            h, request, put, _, _ = self.fixture(stage)
            put(h.inode.symbols['npu_emulation_inode_state'] + 8, struct.pack('<I', 1))
            with self.assertRaises(AssertionError): InodeTrace(h, request)

    def test_missing_reordered_or_wrong_site_stores_fail(self):
        for fault in range(4):
            h, request, put, _, _ = self.fixture()
            trace = InodeTrace(h, request)
            self.finish_fixture(trace, put)
            if fault == 0: trace.stores.pop()
            if fault == 1: trace.stores[:2] = reversed(trace.stores[:2])
            if fault == 2: trace.stores[3] = (0x8400e178, *trace.stores[3][1:])
            if fault == 3: trace.stores[3] = (*trace.stores[3][:3], 1)
            with self.assertRaises(AssertionError): trace.validate()

    def test_private_code_protected_and_abi_mutations_fail(self):
        for fault in range(10):
            h, request, put, read, _ = self.fixture(1, 1)
            trace = InodeTrace(h, request)
            self.finish_fixture(trace, put)
            if fault == 0: trace.locks.reverse()
            if fault == 1: trace.entries.pop()
            if fault == 2: trace.returns[0]['saved'] = (0,) * len(SAVED)
            if fault == 3: trace.returns[0]['mstatus'] = 8
            address = {4: trace.owner + 32, 5: trace.setup + 404, 6: 0x3e8bc46c,
                7: 0x84001000, 8: h.inode.symbols['plan'], 9: h.pcie_tail.symbols['npu_emulation_pcie_tail_state']}.get(fault)
            if address is not None: put(address, bytes([read(address, 1)[0] ^ 1]))
            with self.assertRaises(AssertionError): trace.validate()
            h.cpu.mem_write.assert_not_called()
            h.cpu.reg_write.assert_not_called()

    def test_store_hook_requires_reserved_owner_irq_and_held_lease(self):
        for fault in range(6):
            h, request, put, _, registers = self.fixture()
            trace = InodeTrace(h, request)
            words = [0x31444e49, 1, 0, 1, 0, 1, 0, 1, 0, 1030]
            if fault == 1: words[7] = 0
            put(trace.owner, struct.pack('<10I', *words))
            put(h.inode.symbols['npu_emulation_inode_running'], struct.pack('<I', 0 if fault == 4 else 1))
            put(trace.setup + 4, struct.pack('<I', 0 if fault == 3 else 1))
            put(trace.setup + 404, struct.pack('<I', 1 if fault == 5 else 0))
            put(h.rv.symbols['npu_emulation_admission_state'] + 4, struct.pack('<I', 1))
            registers[r.UC_RISCV_REG_PC] = h.inode.symbols['npu_emulation_inode_e178_store']
            registers[r.UC_RISCV_REG_MSTATUS] = 8 if fault == 2 else 0
            if fault:
                with self.assertRaises(AssertionError): trace.write(h.cpu, None, *trace.events[0][1:], None)
            else:
                trace.write(h.cpu, None, *trace.events[0][1:], None)
                self.assertEqual(trace.stores, [trace.events[0]])

    def test_original_wrapper_padding_and_helper_arguments_are_checked(self):
        for fault in range(3):
            h, request, put, _, registers = self.fixture()
            trace = InodeTrace(h, request)
            pointer = STACK_TOPS[0] - 0x1100
            put(pointer, struct.pack('<6I', *request[11:14], 0, 0, int(fault == 1)))
            registers[r.UC_RISCV_REG_A0] = pointer
            if fault == 1:
                with self.assertRaises(AssertionError):
                    trace.code(h.cpu, h.inode.symbols['npu_original_inode_callback'], 2, None)
                continue
            trace.code(h.cpu, h.inode.symbols['npu_original_inode_callback'], 2, None)
            for index in range(5): registers[getattr(r, 'UC_RISCV_REG_A' + str(index))] = 0
            registers[r.UC_RISCV_REG_A0] = 2
            registers[r.UC_RISCV_REG_A4] = int(fault == 2)
            if fault == 2:
                with self.assertRaises(AssertionError): trace.code(h.cpu, 0x8400e084, 2, None)
            else: trace.code(h.cpu, 0x8400e084, 2, None)

    def test_return_is_captured_before_provider_context_restoration(self):
        h, request, _, _, registers = self.fixture()
        trace = InodeTrace(h, request)
        self.assertEqual(trace.observe_return(0x84000100, []), END)
        registers[SAVED[0]] ^= 1
        self.assertEqual(trace.returns[0]['saved'], trace.saved_before)
        self.assertNotEqual(trace.returns[0]['saved'][0], registers[SAVED[0]])

    def test_actual_mailbox_context_restore_cannot_hide_a_guest_ABI_clobber(self):
        from test_provider_plan_native import ProviderRequest, MBOX, DISPATCH
        built = subprocess.run(['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
            '-x', 'assembler', '-c', '-o', '-', '-'], input=b'.option norvc\n.text\nli s0,0x1234\nret\n',
            capture_output=True, timeout=30)
        self.assertEqual(built.returncode, 0, built.stderr)
        code = ELFFile(io.BytesIO(built.stdout)).get_section_by_name('.text').data()
        h = object.__new__(ProviderRequest)
        h.cpu = cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        cpu.mem_map(CODE, 0x201000)
        cpu.mem_write(DISPATCH, code)
        cpu.mem_map(MBOX & ~0xfff, 4096)
        h.request_address, h.request_alias = 0x83000000, 0x43000000
        cpu.mem_map(h.request_alias, 4096)
        h.callback_entries, h.request_reads, h.wire_frames = [], [], []
        h.get32 = lambda address: int.from_bytes(cpu.mem_read(address, 4), 'little')
        h.put32 = lambda address, value: cpu.mem_write(address, struct.pack('<I', value))
        cpu.reg_write(r.UC_RISCV_REG_S0, 0xa1000101)

        def run(start, stops):
            self.assertEqual(stops, [])
            cpu.emu_start(start, END, count=100, timeout=1000000)
            return cpu.reg_read(r.UC_RISCV_REG_PC)

        h.run = run
        trace = object.__new__(InodeTrace)
        trace.h, trace._run, trace.returns = h, h.run, []
        with patch.object(h, 'run', trace.observe_return):
            ProviderRequest.message(h, [0x12, 24, 0])
        self.assertEqual(cpu.reg_read(r.UC_RISCV_REG_S0), 0xa1000101)
        self.assertEqual(trace.returns[0]['saved'][0], 0x1234)
        self.assertNotEqual(trace.returns[0]['saved'][0], cpu.reg_read(r.UC_RISCV_REG_S0))

    def test_exception_cleans_hooks_and_saving_is_not_validation(self):
        h, request, put, _, _ = self.fixture()
        trace = InodeTrace(h, request)
        original = h.run
        with self.assertRaisesRegex(RuntimeError, 'fixture'):
            with trace: raise RuntimeError('fixture')
        self.assertIs(h.run, original)
        self.assertEqual(h.cpu.hook_del.call_count, 5)
        self.finish_fixture(trace, put)
        with tempfile.TemporaryDirectory() as directory:
            row = trace.save(Path(directory) / 'trace')
        self.assertNotIn('passed', row)
        self.assertTrue(row['validation_is_separate'])
        self.assertTrue(row['abi_observed_before_context_restore'])
        self.assertFalse(row['guest_writes_by_observer'])


if __name__ == '__main__': unittest.main()
