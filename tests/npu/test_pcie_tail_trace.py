"""Synthetic memory/ELF/CPU fixtures test the read-only oracle, not admission."""
from types import SimpleNamespace
from unittest.mock import Mock
import struct
import tempfile
import unittest

from unicorn import riscv_const as r
from pcie_tail_trace import PcieTailTrace, SPACES, MODEL_BAR_PAGES, SITES, LOCKS


class TailTraceTests(unittest.TestCase):
    def fixture(self, stage=0, hif2=0, code_bytes=0x100000):
        memory = {base: bytearray(size) for base, size in (*SPACES,
            *((base, 4096) for base in MODEL_BAR_PAGES), (0x84000000, code_bytes))}

        def read(address, size):
            base = next(base for base, data in memory.items() if base <= address and address + size <= base + len(data))
            return bytes(memory[base][address - base:address - base + size])

        def put(address, data):
            base = next(base for base, block in memory.items() if base <= address and address + len(data) <= base + len(block))
            memory[base][address - base:address - base + len(data)] = data

        def component(name, address, size):
            table = SimpleNamespace(get_symbol_by_name=lambda key: [{'st_size': size}])
            return SimpleNamespace(symbols={name: address}, elf=SimpleNamespace(get_section_by_name=lambda key: table))

        setup, session, admission, owner, running = 0x84046000, 0x3e906380, 0x3e906100, 0x840e9000, 0x840e9100
        tx2 = 0x200d4450 + hif2 * 0x4000
        h = SimpleNamespace(cpu=Mock(), rv=SimpleNamespace(symbols={
            'npu_emulation_cold_setup_state': setup, 'npu_emulation_control_v2_state': session,
            'npu_emulation_admission_state': admission}),
            packet=component('npu_emulation_packet_state', 0x84081000, 2076),
            tx=component('npu_emulation_tx_state', 0x84084000, 80),
            rx_pcie=component('npu_emulation_rx_pcie_state', 0x840e4000, 168),
            desc10=component('npu_emulation_desc10_state', 0x840d4000, 13512),
            rx_event=component('npu_emulation_rx_event_state', 0x840d0000, 16),
            txbuf=component('npu_emulation_txbuf_state', 0x84090000, 16),
            descriptor=component('npu_emulation_descriptor_state', 0x84088000, 16),
            binding=component('npu_emulation_page_state', 0x84080000, 16),
            inode=component('npu_emulation_inode_state', 0x840f3000, 4372),
            pcie_tail=SimpleNamespace(symbols={'npu_emulation_pcie_tail_state': owner,
                'npu_emulation_pcie_tail_running': running} | {
                f'npu_emulation_pcie_tail_{site:x}_store': 0x840ea000 + i * 16 for i, site in enumerate(SITES)}))
        h.cpu.mem_read.side_effect = read
        h.get32 = lambda address: struct.unpack('<I', read(address, 4))[0]
        words = [0] * 103
        words[:8] = [0, 0, 131071, 79, 1, 2, 3, 4]
        words[12:16] = [0x20000000, 0x100000] * 2
        words[26:32] = [8, 0x3e810000, 8, 0x3e810000, 14, 14]
        words[90:101] = [6, 6, 0x97000000, 0x97000000, 0x97000000, 3, 3, tx2, tx2, stage, stage]
        put(setup, struct.pack('<103I', *words))
        put(session, struct.pack('<5I', 1, 2, 3, 4, 79))
        tx_plan = struct.pack('<11I', 0x3e810000, 303168, 0x20000000, 0x100000,
                              0x200d4420, tx2, 0, 1, 2, 3, 4)
        pcie_plan = bytes(136)
        put(0x84084000, struct.pack('<9I', 0x31585443, 1, 0, 0, 7, 7, 11, 11, 2) + tx_plan)
        put(0x840e4000, struct.pack('<8I', 0x31455052, 1, 0, 0, 1, 1, 1, 0) + pcie_plan)
        if stage:
            end, mask = stage * 2, (1 << stage) - 1
            put(owner, struct.pack('<10I', 0x31545043, 1, 0, 0, stage - 1, mask, mask, end, end, (1 << end) - 1)
                + pcie_plan + tx_plan + bytes(36))
        request = [0x3f, 1, 0x3253434e, 2, 80, 1, 80, 3, 4, 1, 2,
                   (0x10, 0x12, 0x1f)[stage], 0, (0x200d4580, tx2 + 0x110, 0)[stage], *([0] * 6)]
        return h, request, put, read

    def finish_fixture(self, trace, put):
        for base, contents in trace.memory.items():
            put(base, contents)
        put(trace.owner, trace.owner_expected)
        put(trace.setup, trace.setup_expected)
        trace.stores = [(0x84000000 + site, *event) for site, event in
                        zip(SITES[trace.first:trace.last], trace.events)]
        trace.locks = [(LOCKS[0], 4, 0x40), (LOCKS[1], 4, 0)]

    def test_projection_both_profiles_all_stages_never_writes_cpu(self):
        for stage in range(3):
            for hif2 in (0, 1):
                h, request, put, _ = self.fixture(stage, hif2)
                trace = PcieTailTrace(h, request)
                self.assertEqual(len(trace.events), 5 if stage == 2 else 2)
                self.assertEqual(sum(len(data) for data in trace.memory.values()), 868352)
                self.finish_fixture(trace, put)
                trace.validate()
                h.cpu.mem_write.assert_not_called()
                h.cpu.reg_write.assert_not_called()

    def test_wrong_request_or_identity_is_not_a_projection(self):
        for index, value in ((0, 0), (4, 79), (6, 79), (7, 5), (9, 5), (11, 0x1a), (12, 1), (13, 0), (14, 1)):
            h, request, _, _ = self.fixture()
            request[index] = value
            with self.assertRaises(AssertionError):
                PcieTailTrace(h, request)
            h.cpu.mem_write.assert_not_called()

    def test_inode_history_cannot_be_smuggled_into_a_tail_prefix(self):
        for offset in (404, 408):
            h, request, put, _ = self.fixture()
            put(h.rv.symbols['npu_emulation_cold_setup_state'] + offset, struct.pack('<I', 1))
            with self.assertRaisesRegex(AssertionError, 'tail-before-INODE'):
                PcieTailTrace(h, request)
            h.cpu.mem_write.assert_not_called()

    def test_inexact_stores_locks_private_or_protected_memory_fail(self):
        for fault in range(8):
            h, request, put, read = self.fixture(2, 1)
            trace = PcieTailTrace(h, request)
            self.finish_fixture(trace, put)
            if fault == 0: trace.stores.pop()
            if fault == 1: trace.stores[0] = (0, *trace.stores[0][1:])
            if fault == 2: trace.stores[0] = (*trace.stores[0][:2], 2, trace.stores[0][3])
            if fault == 3: trace.locks.reverse()
            if fault == 4: put(trace.owner + 32, struct.pack('<I', 8))
            if fault == 5: put(trace.setup + 20, struct.pack('<I', 99))
            if fault == 6: put(0x200d45ac, struct.pack('<I', 99))
            if fault == 7:
                address, contents = next(iter(trace.prior.values()))
                put(address, bytes([contents[0] ^ 1]) + read(address + 1, len(contents) - 1))
            with self.assertRaises(AssertionError):
                trace.validate()

    def test_hook_requires_commit_irq_and_held_journal(self):
        for fault in range(5):
            h, request, put, _ = self.fixture()
            trace = PcieTailTrace(h, request)
            owner = [0x31545043, 1, 0, 1, 0, 1, 0, 1, 0, 3]
            if fault == 1: owner[7] = 0
            put(trace.owner, struct.pack('<10I', *owner))
            put(trace.setup + 4, struct.pack('<I', 0 if fault == 3 else 1))
            put(h.rv.symbols['npu_emulation_admission_state'] + 4, struct.pack('<I', 1))
            put(h.pcie_tail.symbols['npu_emulation_pcie_tail_running'], struct.pack('<I', 0 if fault == 4 else 1))
            h.cpu.reg_read.side_effect = {r.UC_RISCV_REG_PC: next(iter(trace.sites)),
                                         r.UC_RISCV_REG_MSTATUS: 8 if fault == 2 else 0}.__getitem__
            if fault:
                with self.assertRaises(AssertionError):
                    trace.write(h.cpu, None, *trace.events[0], None)
            else:
                trace.write(h.cpu, None, *trace.events[0], None)
                self.assertEqual(len(trace.stores), 1)
            h.cpu.mem_write.assert_not_called()
            h.cpu.reg_write.assert_not_called()

    def test_exception_removes_hook_and_save_is_not_validation(self):
        h, request, put, _ = self.fixture()
        trace = PcieTailTrace(h, request)
        h.cpu.hook_add.return_value = 71
        with self.assertRaisesRegex(RuntimeError, 'fixture'):
            with trace:
                raise RuntimeError('fixture')
        h.cpu.hook_del.assert_called_once_with(71)
        self.finish_fixture(trace, put)
        with tempfile.TemporaryDirectory() as directory:
            from pathlib import Path
            row = trace.save(Path(directory) / 'trace')
        self.assertTrue(row['validation_is_separate'])
        self.assertFalse(row['guest_writes_by_observer'])
        self.assertNotIn('passed', row)


if __name__ == '__main__':
    unittest.main()
