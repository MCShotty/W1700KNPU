"""Separate relative-table controls; the existing31 absolute fixtures stay fixed."""
import hashlib
import json
from pathlib import Path
import struct
import unittest

from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import UC_PROT_READ, UC_PROT_EXEC
from unicorn import riscv_const as registers

import test_npu_switch_targets as targets
from test_npu_original_body_stack import local_body

PATH = Path(__file__).with_name('relative_switch_fixtures.json')
FIXTURE_SHA256 = '9f20e50ad8cd3cf1458c6640c2768e0c1381c7259288859327a6e04f3a570dcd'
assert hashlib.sha256(PATH.read_bytes()).hexdigest() == FIXTURE_SHA256
FIXTURES = json.loads(PATH.read_bytes())
assert FIXTURES['format'] == 'synthetic-rv32-relative-switch-fixtures-v1'
assert FIXTURES['synthetic_only'] is FIXTURES['no_router_firmware_bytes'] is True
assert len(FIXTURES['programs']) == 22
assert hashlib.sha256((PATH.parent / 'fixtures/relative_switch.S').read_bytes()).hexdigest() == FIXTURES['source_sha256']
GUEST_EVIDENCE = []


def reader(fixture, table=None):
    data = bytes.fromhex(fixture['table_hex']) if table is None else table

    def read(address, count):
        offset = address - fixture['table_address']
        assert offset >= 0 and offset + count * 4 <= len(data), 'unavailable-table'
        return data[offset:offset+count*4]

    return read


def inspect(name='basic', table=None, program=None):
    fixture = FIXTURES['programs'][name]
    code = bytes.fromhex(fixture['program_hex']) if program is None else program
    return targets.inspect_function(code, fixture['address'], reader(fixture, table))


def table_target(fixture, address):
    data = bytes.fromhex(fixture['table_hex'])
    return struct.pack('<I', (address-fixture['table_address']) & 0xffffffff) + data[4:]


def relocate_table(fixture, address):
    """Mutate only synthetic AUIPC/ADDI immediates, retaining their register fields."""
    code = bytearray.fromhex(fixture['program_hex'])
    pc = fixture['labels']['upper']
    delta = (address - pc) & 0xffffffff
    upper = ((delta + 0x800) >> 12) & 0xfffff
    lower = (delta - (upper << 12)) & 0xfff
    offset = pc - fixture['address']
    word, addition = struct.unpack_from('<II', code, offset)
    struct.pack_into('<II', code, offset, (word & 0xfff) | (upper << 12),
        (addition & 0xfffff) | (lower << 20))
    return bytes(code)


class RelativeSwitchContracts(unittest.TestCase):
    def test_unsigned_bounds_with_base_alias_and_biased_index(self):
        for name in ('basic', 'bound_alias', 'biased', 'framed'):
            with self.subTest(name=name):
                fixture = FIXTURES['programs'][name]
                result = inspect(name)
                self.assertEqual(len(result['tables']), 1)
                row = result['tables'][0]
                self.assertEqual(row['table_address'], fixture['table_address'])
                self.assertEqual(row['entry_count'], 4)
                self.assertEqual(row['table_entry_encoding'], 'base-relative-u32')
                self.assertEqual(row['table_targets'], [fixture['labels']['case'+str(i)] for i in range(4)])
                self.assertTrue(row['guard_safe_edge_dominates_load_and_jump'])
                self.assertFalse(row['interfunction_edge'])

    def test_unsupported_grammar_and_bounds_fail_closed(self):
        for name in ('signed_guard', 'negative_max', 'oversized_max', 'wrong_shift',
                     'wrong_base', 'wrong_load', 'wrong_post_add', 'call_not_internal'):
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, 'no-recognized-table'):
                inspect(name)

    def test_table_extent_and_alignment_are_checked_before_read(self):
        fixture = FIXTURES['programs']['basic']
        for address in (fixture['table_address'] + 2, 0xfffffff8, 0xfffffffc):
            with self.subTest(address=address), self.assertRaisesRegex(AssertionError, 'no-recognized-table'):
                inspect(program=relocate_table(fixture, address))

    def test_relative_targets_must_be_internal_even_instruction_starts(self):
        fixture = FIXTURES['programs']['basic']
        for address in (fixture['address'], fixture['address'] + 1,
                        fixture['labels']['upper'] + 2, 0x30000):
            with self.subTest(address=address), self.assertRaisesRegex(AssertionError, 'noninternal-table-target'):
                inspect(table=table_target(fixture, address))

    def test_each_table_prefix_entry_is_denied(self):
        fixture = FIXTURES['programs']['basic']
        for address in inspect()['tables'][0]['prefix_addresses']:
            with self.subTest(address=address), self.assertRaisesRegex(AssertionError, 'table-target-enters-prefix'):
                inspect(table=table_target(fixture, address))

    def test_a_direct_entry_cannot_bypass_the_complete_definition(self):
        with self.assertRaisesRegex(AssertionError, 'prefix-can-bypass-definition'):
            inspect('bypass')

    def test_unreachable_definition_is_not_qualified(self):
        with self.assertRaisesRegex(AssertionError, 'unreachable-table-definition'):
            inspect('unreachable')

    def test_default_is_internal_distinct_and_outside_prefix(self):
        for name, reason in (('identical_guard_edges', 'table-target-enters-prefix'),
                             ('external_default', 'noninternal-default-target'),
                             ('prefix_default', 'table-target-enters-prefix')):
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, reason):
                inspect(name)

    def test_other_unknown_flows_and_traps_remain_rejected(self):
        for name in ('unknown_tail', 'unknown_call', 'trap'):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                inspect(name)

    def test_missing_and_short_tables_do_not_get_inferred(self):
        with self.assertRaisesRegex(AssertionError, 'unavailable-table'):
            inspect(table=b'\0' * 12)
        fixture = FIXTURES['programs']['basic']
        with self.assertRaisesRegex(AssertionError, 'table-length-drift'):
            targets.inspect_function(bytes.fromhex(fixture['program_hex']), fixture['address'],
                lambda address, count: b'\0' * 12)

    def test_old_metadata_label_contract_is_not_weakened(self):
        row = inspect()['tables'][0]
        metadata = dict(switch_address=hex(row['address']), label_values=row['table_targets'],
            case_targets=[hex(pc) for pc in row['table_targets']], load_tables=[])
        with self.assertRaisesRegex(AssertionError, 'metadata-label-drift'):
            targets.metadata_matches(row, metadata)

    def test_local_stack_requires_its_own_complete_table_check(self):
        for name in ('basic', 'bound_alias', 'biased', 'framed'):
            with self.subTest(name=name):
                fixture = FIXTURES['programs'][name]
                code = bytes.fromhex(fixture['program_hex'])
                with self.assertRaisesRegex(AssertionError, 'unknown-noncall-register-flow'):
                    local_body(code, fixture['address'])
                row = local_body(code, fixture['address'], read_table=reader(fixture))
                self.assertEqual(row['local_max_stack_bytes'], 16 if name == 'framed' else 0)
                self.assertTrue(row['all_body_instructions_reached_by_conservative_CFG'])
                self.assertTrue(row['table_snapshot_immutability_assumed'])
                self.assertFalse(row['physical_table_permissions_proved'])
                self.assertFalse(row['complete_call_chain_bound_proven'])

    def test_internal_tables_cannot_hide_stack_leaks_or_caller_storage(self):
        for name in ('stack_leak', 'stack_overrun'):
            with self.subTest(name=name):
                fixture = FIXTURES['programs'][name]
                with self.assertRaises(AssertionError):
                    local_body(bytes.fromhex(fixture['program_hex']), fixture['address'], read_table=reader(fixture))

    def test_local_stack_cannot_use_unqualified_or_short_tables(self):
        for name in ('bypass', 'unknown_tail', 'unknown_call', 'trap', 'unreachable'):
            with self.subTest(name=name):
                fixture = FIXTURES['programs'][name]
                with self.assertRaises(AssertionError):
                    local_body(bytes.fromhex(fixture['program_hex']), fixture['address'], read_table=reader(fixture))
        fixture = FIXTURES['programs']['basic']
        with self.assertRaisesRegex(AssertionError, 'unavailable-table'):
            local_body(bytes.fromhex(fixture['program_hex']), fixture['address'], read_table=reader(fixture, b''))

    def test_real_synthetic_prefixes_stop_before_cases_with_exact_state(self):
        ids = [getattr(registers, 'UC_RISCV_REG_X' + str(i)) for i in range(32)]
        for name in ('basic', 'bound_alias', 'biased', 'framed'):
            for value in (0, 1, 2, 3, 4, 0xffffffff):
                with self.subTest(name=name, value=value):
                    fixture = FIXTURES['programs'][name]
                    row = inspect(name)['tables'][0]
                    argument = (value + 32) & 0xffffffff if name == 'biased' else value
                    allowed = value < 4
                    target = row['table_targets'][value] if allowed else row['default_target']
                    code, table = bytes.fromhex(fixture['program_hex']), bytes.fromhex(fixture['table_hex'])
                    cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
                    cpu.mem_map(0x10000, 4096)
                    cpu.mem_map(0x20000, 4096)
                    cpu.mem_write(fixture['address'], code)
                    cpu.mem_write(fixture['table_address'], table)
                    cpu.mem_protect(0x10000, 4096, UC_PROT_READ | UC_PROT_EXEC)
                    cpu.mem_protect(0x20000, 4096, UC_PROT_READ)
                    for number, register in enumerate(ids[1:], 1):
                        cpu.reg_write(register, 0xa0000000 + number)
                    cpu.reg_write(registers.UC_RISCV_REG_SP, 0x31000)
                    cpu.reg_write(registers.UC_RISCV_REG_A0, argument)
                    cpu.reg_write(registers.UC_RISCV_REG_MSTATUS, 0x1880)
                    status = cpu.reg_read(registers.UC_RISCV_REG_MSTATUS)
                    expected = [cpu.reg_read(register) for register in ids]
                    expected[15] = target if allowed else value
                    if allowed:
                        expected[13] = fixture['table_address']
                    elif name == 'bound_alias':
                        expected[13] = 3
                    if name != 'bound_alias':
                        expected[14] = 3
                    if name == 'framed':
                        expected[2] -= 16
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
                    self.assertEqual(reads, [(fixture['table_address'] + value*4, 4)] if allowed else [])
                    self.assertEqual(writes, [])
                    self.assertEqual([bytes(cpu.mem_read(base, 4096)) for base in (0x10000, 0x20000)], protected)
                    GUEST_EVIDENCE.append(dict(fixture=name, argument=argument, index=value, in_range=allowed,
                        PC=target, MSTATUS=status, registers=actual, reads=reads, writes=writes,
                        synthetic_only=True, stopped_before_case=True, observed_before_restoration=True,
                        whole_protected_memory_unchanged=True, router_firmware_executed=False))


if __name__ == '__main__':
    unittest.main()
