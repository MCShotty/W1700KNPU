"""Conservative known bounds and complete unsigned safe-edge cuts,not waivers."""
import hashlib
import json
from pathlib import Path
import struct
import unittest

from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import UC_PROT_READ, UC_PROT_EXEC
from unicorn import riscv_const as registers

from test_npu_original_body_stack import local_body
from test_npu_constant_targets import returned
from test_npu_direct_stack import decode
from test_npu_relative_switch_contract import reader, table_target
from test_npu_switch_targets import inspect_function

PATH = Path(__file__).with_name('relative_guardset_fixtures.json')
FIXTURE_SHA256 = '7b476fa767c6a3ab119aa1c0eb9028713e0055ccc92b62c0278d8b8a1aaebdfb'
assert hashlib.sha256(PATH.read_bytes()).hexdigest() == FIXTURE_SHA256
FIXTURES = json.loads(PATH.read_bytes())
assert FIXTURES['format'] == 'synthetic-rv32-relative-guardset-fixtures-v1'
assert FIXTURES['synthetic_only'] is FIXTURES['no_router_firmware_bytes'] is True
assert len(FIXTURES['programs']) == 31
assert hashlib.sha256((PATH.parent / 'fixtures/relative_guard_sets.S').read_bytes()).hexdigest() == FIXTURES['source_sha256']
GUEST_EVIDENCE = []


def inspect(name='multi_guard', enabled=True, table=None, stack=False):
    fixture = FIXTURES['programs'][name]
    code = bytes.fromhex(fixture['program_hex'])
    if stack:
        return local_body(code, fixture['address'], read_table=reader(fixture, table), relative_guard_sets=enabled)
    return inspect_function(code, fixture['address'], reader(fixture, table), relative_guard_sets=enabled)


class RelativeGuardSetContracts(unittest.TestCase):
    def test_new_profile_is_explicit_and_old_strict_denials_remain(self):
        for name in ('multi_guard', 'guard_reentry', 'bias_reentry', 'call_restored', 'framed'):
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, 'prefix-can-bypass-definition'):
                inspect(name, enabled=False)

    def test_multiple_unsigned_safe_edges_require_the_same_known_bound(self):
        result = inspect()
        self.assertEqual(len(result['tables']), 1)
        row = result['tables'][0]
        self.assertEqual(row['guard_bound_constant'], 3)
        self.assertEqual(row['guard_bound_register'], 'a4')
        self.assertEqual(row['qualification_profile'], 'relative-unsigned-safe-edge-set-v1')
        self.assertEqual(len(row['qualified_safe_edges']), 2)
        self.assertTrue(row['guard_safe_edge_set_dominates_load_and_jump'])
        self.assertFalse(row['guard_safe_edge_dominates_load_and_jump'])
        self.assertTrue(result['entry_registers_unknown_except_zero'])
        self.assertTrue(result['calls_clobber_caller_saved'])

    def test_reentries_before_guard_are_not_unchecked_safe_edges(self):
        for name in ('guard_reentry', 'bias_reentry'):
            with self.subTest(name=name):
                row = inspect(name)['tables'][0]
                self.assertEqual(len(row['qualified_safe_edges']), 1)
                self.assertTrue(row['guard_safe_edge_dominates_load_and_jump'])
                self.assertTrue(row['guard_safe_edge_set_dominates_load_and_jump'])

    def test_changed_unknown_and_inconsistent_bounds_are_not_constants(self):
        for name in ('bound_changed', 'bound_unknown', 'bound_join', 'uninitialized_bound', 'changed_loop'):
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, 'guard-bound-not-proved-constant'):
                inspect(name)

    def test_call_clobbers_are_retained_and_an_explicit_redefinition_is_required(self):
        with self.assertRaisesRegex(AssertionError, 'guard-bound-not-proved-constant'):
            inspect('call_clobbered')
        self.assertEqual(inspect('call_restored')['tables'][0]['guard_bound_constant'], 3)
        row = inspect('call_restored', stack=True)
        self.assertEqual(len(row['external_transfers']), 1)
        self.assertFalse(row['external_transfers'][0]['child_frame_proved'])

    def test_signed_wrong_register_and_incomplete_default_guards_are_rejected(self):
        for name in ('signed_alternate', 'wrong_bound', 'wrong_index', 'default_gap'):
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, 'unqualified-alternate-safe-entry'):
                inspect(name)

    def test_unconditional_safe_entry_or_post_check_index_change_is_rejected(self):
        for name in ('jump_upper', 'index_after_guard'):
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, 'unqualified-alternate-safe-entry'):
                inspect(name)

    def test_every_later_prefix_entry_still_rejects(self):
        for name in ('jump_addition', 'jump_shift', 'jump_combine', 'jump_load', 'jump_post', 'jump_dispatch'):
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, 'prefix-can-bypass-safe-edge-set'):
                inspect(name)

    def test_unknown_flows_traps_and_non_ABI_links_cannot_hide_in_the_body(self):
        for name in ('unknown_tail', 'unknown_call', 'trap', 'non_ABI_call', 'SP_write'):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                inspect(name)

    def test_table_targets_and_short_reads_are_not_relaxed(self):
        fixture = FIXTURES['programs']['multi_guard']
        for address in (fixture['address'], fixture['labels']['upper'], fixture['labels']['upper']+2, 0x30000):
            with self.subTest(address=address), self.assertRaises(AssertionError):
                inspect(table=table_target(fixture, address))
        with self.assertRaisesRegex(AssertionError, 'unavailable-table'):
            inspect(table=b'\0'*12)

    def test_local_stack_checks_every_case_and_keeps_child_costs_unproved(self):
        for name in ('multi_guard', 'guard_reentry', 'bias_reentry', 'framed'):
            with self.subTest(name=name):
                row = inspect(name, stack=True)
                self.assertEqual(row['local_max_stack_bytes'], 16 if name == 'framed' else 0)
                self.assertTrue(row['all_body_instructions_reached_by_conservative_CFG'])
                self.assertTrue(row['reviewed_returns_and_tail_SP_balanced'])
                self.assertFalse(row['child_frames_proved'])
                self.assertFalse(row['complete_call_chain_bound_proven'])
                self.assertFalse(row['physical_table_permissions_proved'])

    def test_stack_leaks_and_caller_storage_remain_errors(self):
        for name in ('stack_leak', 'stack_overrun'):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                inspect(name, stack=True)

    def test_guard_sets_without_a_reader_cannot_supply_targets(self):
        fixture = FIXTURES['programs']['multi_guard']
        with self.assertRaisesRegex(AssertionError, 'guard-sets-require-table-reader'):
            local_body(bytes.fromhex(fixture['program_hex']), fixture['address'], relative_guard_sets=True)

    def test_first_edge_dominance_does_not_replace_later_loop_bound_proof(self):
        row = inspect('guarded_loop')['tables'][0]
        self.assertTrue(row['guard_safe_edge_dominates_load_and_jump'])
        self.assertTrue(row['guard_safe_edge_set_dominates_load_and_jump'])
        self.assertEqual(len(row['qualified_safe_edges']), 2)
        self.assertEqual(inspect('guarded_loop', stack=True)['local_max_stack_bytes'], 0)
        with self.assertRaisesRegex(AssertionError, 'guard-bound-not-proved-constant'):
            inspect('changed_loop')

    def test_real_guarded_loop_stops_before_return_after_fresh_index_check(self):
        fixture = FIXTURES['programs']['guarded_loop']
        row = inspect('guarded_loop')['tables'][0]
        last = decode(bytes.fromhex(fixture['program_hex']), fixture['address'])[-1]
        self.assertTrue(returned(last))
        stop = last.address
        ids = [getattr(registers, 'UC_RISCV_REG_X'+str(i)) for i in range(32)]
        for index in (0, 1, 2, 3, 4, 0xffffffff):
            with self.subTest(index=index):
                cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
                cpu.mem_map(0x10000, 4096)
                cpu.mem_map(0x20000, 4096)
                cpu.mem_write(fixture['address'], bytes.fromhex(fixture['program_hex']))
                cpu.mem_write(fixture['table_address'], bytes.fromhex(fixture['table_hex']))
                cpu.mem_protect(0x10000, 4096, UC_PROT_READ | UC_PROT_EXEC)
                cpu.mem_protect(0x20000, 4096, UC_PROT_READ)
                for number, register in enumerate(ids[1:], 1):
                    cpu.reg_write(register, 0xa0000000+number)
                cpu.reg_write(registers.UC_RISCV_REG_SP, 0x31000)
                cpu.reg_write(registers.UC_RISCV_REG_A0, index)
                cpu.reg_write(registers.UC_RISCV_REG_MSTATUS, 0x1880)
                expected = [cpu.reg_read(register) for register in ids]
                expected[14] = 3
                expected[15] = row['table_targets'][index] if index < 4 else index
                if index < 4:
                    expected[13] = fixture['table_address']
                if index == 3:
                    expected[10] = expected[15] = 4
                status = cpu.reg_read(registers.UC_RISCV_REG_MSTATUS)
                protected = [bytes(cpu.mem_read(base, 4096)) for base in (0x10000, 0x20000)]
                reads, writes = [], []
                cpu.hook_add(UC_HOOK_MEM_READ, lambda engine, access, address, width, value, unused:
                    reads.append((address, width)))
                cpu.hook_add(UC_HOOK_MEM_WRITE, lambda engine, access, address, width, value, unused:
                    writes.append((address, width, value)))
                cpu.emu_start(fixture['address'], stop, count=100)
                actual = [cpu.reg_read(register) for register in ids]
                self.assertEqual(actual, expected)
                self.assertEqual(cpu.reg_read(registers.UC_RISCV_REG_PC), stop)
                self.assertEqual(cpu.reg_read(registers.UC_RISCV_REG_MSTATUS), status)
                self.assertEqual(reads, [(fixture['table_address']+4*index, 4)] if index < 4 else [])
                self.assertEqual(writes, [])
                self.assertEqual([bytes(cpu.mem_read(base, 4096)) for base in (0x10000, 0x20000)], protected)
                GUEST_EVIDENCE.append(dict(fixture='guarded_loop', index=index, PC=stop,
                    registers=actual, MSTATUS=status, reads=reads, writes=writes,
                    second_index_rejected=index == 3, protected_memory_unchanged=True,
                    stopped_before_return=True, observed_before_restoration=True,
                    synthetic_only=True, router_firmware_executed=False))

    def test_real_synthetic_guests_check_both_routes_and_unsigned_boundaries(self):
        ids = [getattr(registers, 'UC_RISCV_REG_X'+str(i)) for i in range(32)]
        for name in ('multi_guard', 'guard_reentry', 'bias_reentry', 'framed'):
            for route in (0, 1):
                for index in (0, 1, 2, 3, 4, 0xffffffff):
                    with self.subTest(name=name, route=route, index=index):
                        fixture = FIXTURES['programs'][name]
                        row = inspect(name)['tables'][0]
                        argument = (index+32) & 0xffffffff if name == 'bias_reentry' else index
                        allowed = index < 4
                        target = row['table_targets'][index] if allowed else row['default_target']
                        cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
                        cpu.mem_map(0x10000, 4096)
                        cpu.mem_map(0x20000, 4096)
                        cpu.mem_write(fixture['address'], bytes.fromhex(fixture['program_hex']))
                        cpu.mem_write(fixture['table_address'], bytes.fromhex(fixture['table_hex']))
                        cpu.mem_protect(0x10000, 4096, UC_PROT_READ | UC_PROT_EXEC)
                        cpu.mem_protect(0x20000, 4096, UC_PROT_READ)
                        for number, register in enumerate(ids[1:], 1):
                            cpu.reg_write(register, 0xa0000000+number)
                        cpu.reg_write(registers.UC_RISCV_REG_SP, 0x31000)
                        cpu.reg_write(registers.UC_RISCV_REG_A0, argument)
                        cpu.reg_write(registers.UC_RISCV_REG_A1, route)
                        cpu.reg_write(registers.UC_RISCV_REG_MSTATUS, 0x1880)
                        expected = [cpu.reg_read(register) for register in ids]
                        expected[14], expected[15] = 3, target if allowed else index
                        if allowed:
                            expected[13] = fixture['table_address']
                        if name == 'framed':
                            expected[2] -= 16
                        status = cpu.reg_read(registers.UC_RISCV_REG_MSTATUS)
                        protected = [bytes(cpu.mem_read(base, 4096)) for base in (0x10000, 0x20000)]
                        reads, writes = [], []
                        cpu.hook_add(UC_HOOK_MEM_READ, lambda engine, access, address, width, value, unused:
                            reads.append((address, width)))
                        cpu.hook_add(UC_HOOK_MEM_WRITE, lambda engine, access, address, width, value, unused:
                            writes.append((address, width, value)))
                        cpu.emu_start(fixture['address'], target, count=50)
                        actual = [cpu.reg_read(register) for register in ids]
                        self.assertEqual(actual, expected)
                        self.assertEqual(cpu.reg_read(registers.UC_RISCV_REG_PC), target)
                        self.assertEqual(cpu.reg_read(registers.UC_RISCV_REG_MSTATUS), status)
                        self.assertEqual(reads, [(fixture['table_address']+4*index, 4)] if allowed else [])
                        self.assertEqual(writes, [])
                        self.assertEqual([bytes(cpu.mem_read(base, 4096)) for base in (0x10000, 0x20000)], protected)
                        GUEST_EVIDENCE.append(dict(fixture=name, route=route, index=index, argument=argument,
                            PC=target, registers=actual, MSTATUS=status, reads=reads, writes=writes,
                            protected_memory_unchanged=True, stopped_before_case=True,
                            observed_before_restoration=True, synthetic_only=True,
                            router_firmware_executed=False))


if __name__ == '__main__':
    unittest.main()
