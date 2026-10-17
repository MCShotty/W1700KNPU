"""Synthetic constant-flow controls,including ABI clobbers and a real tiny loop."""
import hashlib
import json
from pathlib import Path
import struct
import unittest

from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import UC_PROT_READ, UC_PROT_EXEC
from unicorn import riscv_const as registers

import test_npu_reaching_targets as targets

FIXTURE_PATH = Path(__file__).with_name('reaching_target_fixtures.json')
FIXTURE_SHA256 = '06e17340819666d97a62fe8e589c292b406af5c0a5bdcce99d01c9843555b160'
assert hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() == FIXTURE_SHA256
FIXTURES = json.loads(FIXTURE_PATH.read_bytes())
assert FIXTURES['format'] == 'synthetic-rv32-reaching-target-fixtures-v1'
assert FIXTURES['synthetic_only'] is FIXTURES['no_router_firmware_bytes'] is True
assert len(FIXTURES['programs']) == 17
GUEST_EVIDENCE = []


def program(name):
    return bytes.fromhex(FIXTURES['programs'][name]['program_hex'])


def inspect(name):
    return targets.inspect_function(program(name),0x10000)


class ReachingTargetsContracts(unittest.TestCase):
    def test_adjacent_and_nonadjacent_cross_register_definitions(self):
        for name in ('adjacent','separate_registers','arithmetic'):
            with self.subTest(name=name):
                row = inspect(name)['calls'][0]
                self.assertEqual(row['target'],0x30040)
                self.assertTrue(row['all_reachable_predecessors_joined'])

    def test_saved_register_survives_direct_ABI_call(self):
        row = inspect('saved_across_direct')['calls'][0]
        self.assertEqual((row['target_register'],row['target']),('s6',0x30040))

    def test_caller_saved_register_does_not_survive_an_ABI_call(self):
        with self.assertRaisesRegex(AssertionError,'register-call-not-singleton'):
            inspect('caller_saved_clobber')

    def test_loads_and_argument_callbacks_remain_unknown(self):
        for name in ('load_clobber','argument_target'):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,'register-call-not-singleton'):
                inspect(name)

    def test_conflicting_or_missing_reaching_definitions_fail(self):
        for name in ('different_join','bypass_definition'):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,'register-call-not-singleton'):
                inspect(name)

    def test_equal_constants_from_different_paths_are_retained(self):
        self.assertEqual(inspect('same_join')['calls'][0]['target'],0x30040)

    def test_loop_backedge_keeps_only_stable_saved_target(self):
        result = inspect('saved_loop')
        self.assertEqual(result['calls'][0]['target'],0x30040)
        self.assertLessEqual(result['state_updates'],66*result['instruction_count'])
        self.assertTrue(result['callee_saved_registers_assumed_preserved'])

    def test_unknown_tails_traps_and_unreachable_calls_fail_closed(self):
        for name,reason in (('unknown_tail','unknown-noncall-register-flow'),('trap','unsupported-control-flow'),
                            ('unreachable','unreachable-register-call')):
            with self.subTest(name=name),self.assertRaisesRegex(AssertionError,reason):
                inspect(name)

    def test_unsupported_register_effects_are_not_silently_ignored(self):
        with self.assertRaisesRegex(AssertionError,'unsupported-register-effects'):
            inspect('unsupported')

    def test_low_bit_mask_and_word_wrap_are_exact(self):
        low,wrap = inspect('low_bit')['calls'][0],inspect('wrap')['calls'][0]
        self.assertEqual((low['raw_target'],low['target']),(0x30041,0x30040))
        self.assertEqual((wrap['raw_target'],wrap['target']),(0xffffffff,0xfffffffe))

    def test_flat_join_never_turns_unknown_or_conflict_into_a_constant(self):
        left = tuple([0]+[None]*31)
        right = list(left)
        right[11] = 0x30040
        self.assertEqual(targets.merge(left,tuple(right)),left)
        self.assertEqual(targets.merge(tuple(right),tuple(right)),tuple(right))
        other = list(right)
        other[11] = 0x40040
        self.assertIsNone(targets.merge(tuple(right),tuple(other))[11])

    def test_arithmetic_signed_unsigned_wrap_and_shift_semantics(self):
        for name,left,right,expected in (
            ('add',0xffffffff,2,1),('sub',0,1,0xffffffff),('sra',0x80000000,1,0xc0000000),
            ('srl',0x80000000,1,0x40000000),('sll',1,33,2),('slt',0xffffffff,0,1),
            ('sltu',0xffffffff,0,0),('and',0xffffffff,-16,0xfffffff0),('xor',0xff,0xf,0xf0)):
            with self.subTest(name=name):
                self.assertEqual(targets.operation(name,left,right),expected)
        self.assertIsNone(targets.operation('add',None,1))
        self.assertIsNone(targets.operation('add',1,None))

    def test_scalar_zero_and_ABI_clobber_sets(self):
        self.assertEqual(len(targets.NAMES),32)
        self.assertEqual(targets.REGISTERS['s6'],22)
        instructions = targets.decode(program('adjacent'),0x10000)
        state = tuple([0]+list(range(1,32)))
        after = targets.effects(instructions[2],state,dict(target=None,kind='ordinary-ABI-unresolved-call'))
        self.assertEqual(after[0],0)
        self.assertEqual(after[22],22)
        self.assertIsNone(after[11])
        self.assertEqual(after[1],instructions[2].address+instructions[2].size)

    def test_invalid_bytes_are_rejected(self):
        with self.assertRaises(AssertionError):
            targets.inspect_function(b'\0\0',0x10000)

    def test_tiny_synthetic_guests_observe_prefix_targets_and_links(self):
        ids = [getattr(registers,'UC_RISCV_REG_X'+str(index)) for index in range(32)]
        for name in ('adjacent','separate_registers','arithmetic','low_bit','wrap'):
            with self.subTest(name=name):
                data = program(name)
                row = inspect(name)['calls'][0]
                target = row['target']
                cpu = Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
                cpu.mem_map(0x10000,4096)
                cpu.mem_map(target & ~4095,4096)
                cpu.mem_write(0x10000,data)
                cpu.mem_protect(0x10000,4096,UC_PROT_READ|UC_PROT_EXEC)
                for number,register in enumerate(ids[1:],1):
                    cpu.reg_write(register,0xa0000000+number)
                expected = [cpu.reg_read(register) for register in ids]
                expected[1],expected[11] = row['address']+2,row['raw_target']
                if name == 'separate_registers': expected[10],expected[12] = 0x30000,7
                elif name == 'arithmetic': expected[10],expected[12] = 0x30000,0x40
                writes = []
                def written(engine,access,address,width,value,unused):
                    writes.append((address,width,value))
                cpu.hook_add(UC_HOOK_MEM_WRITE,written)
                cpu.emu_start(0x10000,target,count=50)
                actual = [cpu.reg_read(register) for register in ids]
                self.assertEqual(cpu.reg_read(registers.UC_RISCV_REG_PC),target)
                self.assertEqual(actual,expected)
                self.assertEqual(writes,[])
                self.assertEqual(bytes(cpu.mem_read(0x10000,len(data))),data)
                GUEST_EVIDENCE.append(dict(fixture=name,PC=target,RA=actual[1],SP=actual[2],writes=writes,
                    registers_sha256=hashlib.sha256(struct.pack('<32I',*actual)).hexdigest(),
                    program_sha256=hashlib.sha256(data).hexdigest(),observed_before_restoration=True,
                    synthetic_program_only=True,router_firmware_executed=False))

    def test_real_synthetic_loop_executes_two_calls_and_restores_saved_state(self):
        data = program('saved_loop')
        row = inspect('saved_loop')['calls'][0]
        target,stack,top,end = row['target'],0x60000,0x61000,0x50000
        ids = [getattr(registers,'UC_RISCV_REG_X'+str(index)) for index in range(32)]
        cpu = Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
        for address in (0x10000,target & ~4095,stack,end):
            cpu.mem_map(address,4096)
        helper = program('adjacent')[-4:]
        self.assertTrue(targets.returned(targets.decode(helper,target)[0]))
        cpu.mem_write(0x10000,data)
        cpu.mem_write(target,helper)
        initial_stack = bytearray(b'\xa5'*4096)
        cpu.mem_write(stack,bytes(initial_stack))
        cpu.mem_protect(0x10000,4096,UC_PROT_READ|UC_PROT_EXEC)
        cpu.mem_protect(target & ~4095,4096,UC_PROT_READ|UC_PROT_EXEC)
        for number,register in enumerate(ids[1:],1):
            cpu.reg_write(register,0xa0000000+number)
        cpu.reg_write(registers.UC_RISCV_REG_SP,top)
        cpu.reg_write(registers.UC_RISCV_REG_RA,end)
        expected = [cpu.reg_read(register) for register in ids]
        expected[11] = 2
        visits,reads,writes = [],[],[]
        def instruction(engine,address,width,unused):
            if address == target:
                visits.append((engine.reg_read(registers.UC_RISCV_REG_S0),engine.reg_read(registers.UC_RISCV_REG_S6)))
        def read(engine,access,address,width,value,unused):
            reads.append((address,width))
        def written(engine,access,address,width,value,unused):
            writes.append((address,width,value))
        cpu.hook_add(UC_HOOK_CODE,instruction)
        cpu.hook_add(UC_HOOK_MEM_READ,read)
        cpu.hook_add(UC_HOOK_MEM_WRITE,written)
        cpu.emu_start(0x10000,end,count=100)
        actual = [cpu.reg_read(register) for register in ids]
        self.assertEqual(cpu.reg_read(registers.UC_RISCV_REG_PC),end)
        self.assertEqual(actual,expected)
        self.assertEqual(visits,[(0,target),(1,target)])
        self.assertEqual(writes,[(top-4,4,end),(top-8,4,0xa0000008),(top-12,4,0xa0000016)])
        self.assertEqual(reads,[(top-12,4),(top-8,4),(top-4,4)])
        struct.pack_into('<III',initial_stack,4096-12,0xa0000016,0xa0000008,end)
        self.assertEqual(bytes(cpu.mem_read(stack,4096)),bytes(initial_stack))
        self.assertEqual(bytes(cpu.mem_read(0x10000,len(data))),data)
        self.assertEqual(bytes(cpu.mem_read(target,len(helper))),helper)
        GUEST_EVIDENCE.append(dict(fixture='saved_loop',PC=end,RA=actual[1],SP=actual[2],
            call_visits=visits,reads=reads,writes=writes,
            registers_sha256=hashlib.sha256(struct.pack('<32I',*actual)).hexdigest(),
            program_sha256=hashlib.sha256(data).hexdigest(),observed_before_restoration=True,
            synthetic_program_only=True,router_firmware_executed=False))


if __name__ == '__main__':
    unittest.main()
