"""Only bounded, nonclobbering pure ADDI/XOR setup is admitted before a guard."""
import hashlib
import json
from pathlib import Path
import unittest

from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import UC_PROT_READ, UC_PROT_EXEC
from unicorn import riscv_const as registers

from test_npu_original_body_stack import local_body
from test_npu_relative_switch_contract import reader, table_target
from test_npu_switch_targets import inspect_function

PATH = Path(__file__).with_name('relative_guard_setup_fixtures.json')
FIXTURE_SHA256 = '7618a4d9ba9926fec9d15fb03e90cde30b2607b8ae7e66fe887d26b19d3552a3'
assert hashlib.sha256(PATH.read_bytes()).hexdigest() == FIXTURE_SHA256
FIXTURES = json.loads(PATH.read_bytes())
assert FIXTURES['format'] == 'synthetic-rv32-relative-guard-setup-fixtures-v1'
assert FIXTURES['synthetic_only'] is FIXTURES['no_router_firmware_bytes'] is True
assert len(FIXTURES['programs']) == 13
assert hashlib.sha256((PATH.parent / 'fixtures/relative_guard_setup.S').read_bytes()).hexdigest() == FIXTURES['source_sha256']
GUEST_EVIDENCE = []


def inspect(name='two_setup', enabled=True, table=None, stack=False):
    fixture = FIXTURES['programs'][name]
    code = bytes.fromhex(fixture['program_hex'])
    if stack:
        return local_body(code,fixture['address'],read_table=reader(fixture,table),relative_guard_sets=enabled)
    return inspect_function(code,fixture['address'],reader(fixture,table),relative_guard_sets=enabled)


class RelativeGuardSetupContracts(unittest.TestCase):
    def test_strict_default_still_denies_the_new_prefix_shape(self):
        for name in ('two_setup','one_setup','biased_setup'):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,'no-recognized-table'):
                inspect(name,enabled=False)

    def test_only_the_bounded_nonclobbering_setup_is_recognized(self):
        for name,count in (('two_setup',2),('one_setup',1),('biased_setup',2)):
            with self.subTest(name=name):
                row = inspect(name)['tables'][0]
                self.assertEqual(len(row['pre_guard_setup_instructions']),count)
                self.assertEqual(row['guard_bound_constant'],3)
                self.assertTrue(row['guard_safe_edge_set_dominates_load_and_jump'])
                self.assertTrue(row['same_function_only'])

    def test_protected_register_writes_are_not_harmless(self):
        for name in ('bound_clobber','index_clobber','base_clobber','SP_clobber','RA_clobber','zero_write'):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,'no-recognized-table'):
                inspect(name)

    def test_no_third_setup_memory_effect_or_call_is_skipped(self):
        for name in ('third_setup','memory_read','memory_write','call'):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,'no-recognized-table'):
                inspect(name)

    def test_target_and_table_byte_checks_still_apply(self):
        fixture = FIXTURES['programs']['two_setup']
        with self.assertRaisesRegex(AssertionError,'unavailable-table'):
            inspect(table=b'\0'*12)
        for target in (fixture['address'],0x30000):
            with self.subTest(target=target),self.assertRaisesRegex(AssertionError,'noninternal-table-target'):
                inspect(table=table_target(fixture,target))

    def test_local_stack_rechecks_the_extended_prefix_and_all_body_paths(self):
        for name in ('two_setup','one_setup','biased_setup'):
            with self.subTest(name=name):
                row = inspect(name,stack=True)
                self.assertEqual(row['local_max_stack_bytes'],0)
                self.assertTrue(row['all_body_instructions_reached_by_conservative_CFG'])
                self.assertFalse(row['complete_call_chain_bound_proven'])
                self.assertFalse(row['physical_table_permissions_proved'])

    def test_real_synthetic_setup_guests_keep_exact_state_and_reads(self):
        ids = [getattr(registers,'UC_RISCV_REG_X'+str(i)) for i in range(32)]
        for name in ('two_setup','one_setup','biased_setup'):
            for index in (0,1,2,3,4,0xffffffff):
                with self.subTest(name=name,index=index):
                    fixture = FIXTURES['programs'][name]
                    row = inspect(name)['tables'][0]
                    argument = (index+32)&0xffffffff if name == 'biased_setup' else index
                    allowed = index < 4
                    target = row['table_targets'][index] if allowed else row['default_target']
                    cpu = Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
                    cpu.mem_map(0x10000,4096)
                    cpu.mem_map(0x20000,4096)
                    cpu.mem_write(fixture['address'],bytes.fromhex(fixture['program_hex']))
                    cpu.mem_write(fixture['table_address'],bytes.fromhex(fixture['table_hex']))
                    cpu.mem_protect(0x10000,4096,UC_PROT_READ|UC_PROT_EXEC)
                    cpu.mem_protect(0x20000,4096,UC_PROT_READ)
                    for number,register in enumerate(ids[1:],1):
                        cpu.reg_write(register,0xa0000000+number)
                    cpu.reg_write(registers.UC_RISCV_REG_SP,0x31000)
                    cpu.reg_write(registers.UC_RISCV_REG_A0,argument)
                    cpu.reg_write(registers.UC_RISCV_REG_MSTATUS,0x1880)
                    expected = [cpu.reg_read(register) for register in ids]
                    expected[14],expected[15],expected[16] = 3,target if allowed else index,(argument+1)&0xffffffff
                    if name != 'one_setup':
                        expected[12] = expected[20]^expected[21]
                    if allowed:
                        expected[13] = fixture['table_address']
                    status = cpu.reg_read(registers.UC_RISCV_REG_MSTATUS)
                    protected = [bytes(cpu.mem_read(base,4096)) for base in (0x10000,0x20000)]
                    reads,writes = [],[]
                    cpu.hook_add(UC_HOOK_MEM_READ,lambda engine,access,address,width,value,unused:reads.append((address,width)))
                    cpu.hook_add(UC_HOOK_MEM_WRITE,lambda engine,access,address,width,value,unused:writes.append((address,width,value)))
                    cpu.emu_start(fixture['address'],target,count=50)
                    actual = [cpu.reg_read(register) for register in ids]
                    self.assertEqual(actual,expected)
                    self.assertEqual(cpu.reg_read(registers.UC_RISCV_REG_PC),target)
                    self.assertEqual(cpu.reg_read(registers.UC_RISCV_REG_MSTATUS),status)
                    self.assertEqual(reads,[(fixture['table_address']+4*index,4)] if allowed else [])
                    self.assertEqual(writes,[])
                    self.assertEqual([bytes(cpu.mem_read(base,4096)) for base in (0x10000,0x20000)],protected)
                    GUEST_EVIDENCE.append(dict(fixture=name,index=index,argument=argument,PC=target,registers=actual,
                        MSTATUS=status,reads=reads,writes=writes,whole_protected_memory_unchanged=True,
                        stopped_before_case=True,observed_before_restoration=True,synthetic_only=True,
                        original_firmware_executed=False))


if __name__ == '__main__':
    unittest.main()
