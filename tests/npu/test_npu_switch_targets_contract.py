"""Synthetic contracts for absolute, bounded intra-function jump tables."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import unittest

from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import UC_PROT_READ, UC_PROT_EXEC
from unicorn import riscv_const as registers

import npu_image
import test_npu_switch_targets as targets

FIXTURE_PATH = Path(__file__).with_name('switch_target_fixtures.json')
FIXTURE_SHA256 = '8f0d092230652e105e8a8f416d3fad09b7ecdf4523c4ed798e21c078b0dbe7ae'
assert hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() == FIXTURE_SHA256
FIXTURES = json.loads(FIXTURE_PATH.read_bytes())
assert FIXTURES['format'] == 'synthetic-rv32-switch-fixtures-v1'
assert FIXTURES['synthetic_only'] is FIXTURES['no_router_firmware_bytes'] is True
assert len(FIXTURES['programs']) == 31
GUEST_EVIDENCE = []


def inspect(name='basic', table_data=None, program_data=None):
    fixture = FIXTURES['programs'][name]
    data = bytes.fromhex(fixture['table_hex']) if table_data is None else table_data
    code = bytes.fromhex(fixture['program_hex']) if program_data is None else program_data

    def read(address, count):
        offset = address - fixture['table_address']
        assert offset >= 0 and offset + count * 4 <= len(data), 'unavailable-table'
        return data[offset:offset+count*4]

    return targets.inspect_function(code,FIXTURES['address'],read)


def metadata(row):
    return dict(switch_address=hex(row['address']), label_values=list(range(row['entry_count'])),
                case_targets=[hex(target) for target in row['table_targets']], load_tables=[])


class SwitchTargetsContracts(unittest.TestCase):
    def test_basic_and_benign_delays(self):
        for name in ('basic','delayed_one','delayed_eight'):
            with self.subTest(name=name):
                result = inspect(name)
                self.assertEqual(len(result['tables']),1)
                row = result['tables'][0]
                self.assertTrue(row['control_flow_qualified'])
                self.assertTrue(row['guard_safe_edge_dominates_load_and_jump'])
                self.assertEqual((row['table_address'],row['entry_count']),(0x20040,4))
                self.assertFalse(row['interfunction_edge'])

    def test_complete_definition_may_have_multiple_predecessors(self):
        self.assertTrue(inspect('branch_to_definition')['tables'][0]['control_flow_qualified'])

    def test_multiple_tables_are_resolved_together_for_cfg(self):
        rows = inspect('two_tables')['tables']
        self.assertEqual([row['table_address'] for row in rows],[0x20040,0x20050])
        self.assertTrue(all(row['control_flow_qualified'] for row in rows))

    def test_every_later_prefix_entry_is_rejected(self):
        for label in ('guard','shift','upper','addition','combine','load','dispatch'):
            with self.subTest(label=label), self.assertRaisesRegex(AssertionError,'prefix-can-bypass-definition'):
                inspect('bypass_'+label)

    def test_unreachable_definition_is_rejected(self):
        with self.assertRaisesRegex(AssertionError,'unreachable-table-definition'):
            inspect('unreachable')

    def test_other_unknown_calls_and_tails_block_qualification(self):
        for name in ('other_call','other_tail'):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,'other-unresolved-register-flow'):
                inspect(name)

    def test_traps_block_qualification(self):
        with self.assertRaisesRegex(AssertionError,'unsupported-control-flow'):
            inspect('trap')

    def test_guard_shift_and_register_dependencies_are_exact(self):
        for name in ('signed_guard','wrong_shift','wrong_index','wrong_base','wrong_load_offset','wrong_target'):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,'no-recognized-table'):
                inspect(name)

    def test_bounds_and_table_arithmetic_fail_closed(self):
        for name in ('negative_bound','oversized_bound','unaligned_base','wrapping_table'):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,'no-recognized-table'):
                inspect(name)

    def test_delays_cannot_clobber_target_stack_or_return_registers(self):
        for name in ('target_clobber','sp_clobber','ra_clobber','too_many_delays'):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,'no-recognized-table'):
                inspect(name)

    def test_linking_register_calls_are_not_internal_jumps(self):
        with self.assertRaisesRegex(AssertionError,'no-recognized-table'):
            inspect('call_not_internal')

    def test_table_targets_must_be_even_instruction_starts_inside_function(self):
        fixture = FIXTURES['programs']['basic']
        table = bytes.fromhex(fixture['table_hex'])
        for target in (0x10000,0x10001,0x10004,0x30000):
            with self.subTest(target=target),self.assertRaisesRegex(AssertionError,'noninternal-table-target'):
                inspect(table_data=struct.pack('<I',target)+table[4:])

    def test_table_targets_cannot_enter_their_own_definition(self):
        fixture = FIXTURES['programs']['branch_to_definition']
        table = bytes.fromhex(fixture['table_hex'])
        with self.assertRaisesRegex(AssertionError,'table-target-enters-prefix'):
            inspect('branch_to_definition',struct.pack('<I',fixture['labels']['limit'])+table[4:])

    def test_one_table_cannot_bypass_another_tables_guard(self):
        fixture = FIXTURES['programs']['two_tables']
        table = bytes.fromhex(fixture['table_hex'])
        changed = struct.pack('<I',fixture['labels']['second_load'])+table[4:]
        with self.assertRaisesRegex(AssertionError,'prefix-can-bypass-definition'):
            inspect('two_tables',changed)

    def test_short_or_unavailable_tables_are_rejected(self):
        with self.assertRaisesRegex(AssertionError,'unavailable-table'):
            inspect(table_data=b'\0'*12)
        data = bytes.fromhex(FIXTURES['programs']['basic']['program_hex'])
        with self.assertRaisesRegex(AssertionError,'table-length-drift'):
            targets.inspect_function(data,0x10000,lambda address,count:b'\0'*12)

    def test_invalid_instruction_and_mid_instruction_branch_fail_closed(self):
        with self.assertRaises(AssertionError):
            targets.inspect_function(b'\0\0',0x10000,lambda address,count:b'')
        code = bytes.fromhex(FIXTURES['programs']['branch_to_definition']['program_hex'])
        changed = npu_image.jal(0x10000,0x1000c)+code[4:]
        with self.assertRaisesRegex(AssertionError,'mid-instruction-direct-target'):
            inspect('branch_to_definition',program_data=changed)

    def test_ghidra_may_include_an_unlabelled_default(self):
        row = inspect()['tables'][0]
        record = metadata(row)
        self.assertEqual(targets.metadata_matches(row,record)['metadata_unlabelled_default_count'],0)
        record['case_targets'].append(hex(row['default_target']))
        result = targets.metadata_matches(row,record)
        self.assertEqual(result['metadata_unlabelled_default_count'],1)
        self.assertFalse(result['metadata_load_tables_available'])

    def test_ghidra_case_order_and_labels_cannot_drift(self):
        row = inspect()['tables'][0]
        record = metadata(row)
        for field,value,reason in (
            ('switch_address',hex(row['address']+2),'metadata-switch-address-drift'),
            ('label_values',[0,1,3,2],'metadata-label-drift'),
            ('case_targets',list(reversed(record['case_targets'])),'metadata-table-order-drift'),
            ('case_targets',record['case_targets']+[hex(row['table_targets'][0])],'unexplained-metadata-case')):
            changed = deepcopy(record)
            changed[field] = value
            with self.subTest(field=field),self.assertRaisesRegex(AssertionError,reason):
                targets.metadata_matches(row,changed)

    def test_real_synthetic_guests_check_both_guard_paths_before_case_bodies(self):
        specs = [('basic',0,None,None),('basic',3,None,None),('basic',4,None,None),
            ('basic',0xffffffff,None,None),('delayed_one',2,None,None),('delayed_one',4,None,None),
            ('delayed_eight',1,None,None),('delayed_eight',0xffffffff,None,None),
            ('branch_to_definition',1,0,None),('branch_to_definition',1,1,None),
            ('two_tables',2,None,'second_limit'),('two_tables',0xffffffff,None,'second_limit')]
        ids = [getattr(registers,'UC_RISCV_REG_X'+str(index)) for index in range(32)]
        for name,index,condition,start_label in specs:
            with self.subTest(name=name,index=index,condition=condition):
                fixture = FIXTURES['programs'][name]
                data,table = bytes.fromhex(fixture['program_hex']),bytes.fromhex(fixture['table_hex'])
                rows = inspect(name)['tables']
                row = rows[1] if start_label else rows[0]
                allowed = index < row['entry_count']
                target = row['table_targets'][index] if allowed else row['default_target']
                cpu = Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
                cpu.mem_map(0x10000,4096)
                cpu.mem_map(0x20000,4096)
                cpu.mem_write(0x10000,data)
                cpu.mem_write(fixture['table_address'],table)
                cpu.mem_protect(0x10000,4096,UC_PROT_READ|UC_PROT_EXEC)
                cpu.mem_protect(0x20000,4096,UC_PROT_READ)
                for number,register in enumerate(ids[1:],1):
                    cpu.reg_write(register,0xa0000000+number)
                cpu.reg_write(registers.UC_RISCV_REG_SP,0x31000)
                cpu.reg_write(registers.UC_RISCV_REG_A0,index)
                if condition is not None:
                    cpu.reg_write(registers.UC_RISCV_REG_A4,condition)
                expected = [cpu.reg_read(register) for register in ids]
                expected[11] = target if allowed else 3
                if allowed:
                    expected[12] = row['table_address']
                    if name == 'delayed_one':
                        expected[10] = 0
                    elif name == 'delayed_eight':
                        for register,value in {23:2,25:6,8:14,19:3,16:index,26:index,17:index,5:index}.items():
                            expected[register] = value
                reads,writes = [],[]
                def observe_read(engine,access,address,width,value,unused):
                    reads.append((address,width))
                def observe_write(engine,access,address,width,value,unused):
                    writes.append((address,width,value))
                cpu.hook_add(UC_HOOK_MEM_READ,observe_read)
                cpu.hook_add(UC_HOOK_MEM_WRITE,observe_write)
                start = fixture['labels'][start_label] if start_label else 0x10000
                cpu.emu_start(start,target,count=50)
                actual = [cpu.reg_read(register) for register in ids]
                self.assertEqual(cpu.reg_read(registers.UC_RISCV_REG_PC),target)
                self.assertEqual(actual,expected)
                self.assertEqual(reads,[(row['table_address']+4*index,4)] if allowed else [])
                self.assertEqual(writes,[])
                self.assertEqual(bytes(cpu.mem_read(0x10000,len(data))),data)
                self.assertEqual(bytes(cpu.mem_read(fixture['table_address'],len(table))),table)
                GUEST_EVIDENCE.append(dict(fixture=name,index=index,branch_condition=condition,start=start,
                    in_range=allowed,PC=target,RA=actual[1],SP=actual[2],reads=reads,writes=writes,
                    registers_sha256=hashlib.sha256(struct.pack('<32I',*actual)).hexdigest(),
                    program_sha256=hashlib.sha256(data).hexdigest(),stopped_before_case_body=True,
                    observed_before_restoration=True,synthetic_program_only=True,router_firmware_executed=False))


if __name__ == '__main__':
    unittest.main()
