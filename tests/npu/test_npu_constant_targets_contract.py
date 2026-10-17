"""Synthetic contracts for bounded literal-target and local control-flow checks."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as registers

import npu_image
import test_npu_constant_targets as targets

FIXTURE_PATH = Path(__file__).with_name('constant_target_fixtures.json')
FIXTURE_SHA256 = 'fcab677111e580e6745e1190023a9dae17a0a83943af70eaaad21276bf649c34'
assert hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() == FIXTURE_SHA256
FIXTURES = json.loads(FIXTURE_PATH.read_bytes())
assert FIXTURES['format'] == 'synthetic-rv32-literal-target-fixtures-v1'
assert FIXTURES['synthetic_only'] is FIXTURES['no_router_firmware_bytes'] is True
assert len(FIXTURES['programs']) == 18
GUEST_EVIDENCE = []


def program(name):
    return bytes.fromhex(FIXTURES['programs'][name]['program_hex'])


def observed(name):
    return targets.inspect_function(program(name),FIXTURES['address'])


class ConstantTargetsContracts(unittest.TestCase):
    def test_call_and_different_register_tail(self):
        for name,expected,kind in (('call',0x10040,'literal-register-call'),
                                   ('tail',0x8400651c,'literal-register-tail')):
            with self.subTest(name=name):
                rows = observed(name)['sequences']
                self.assertEqual(len(rows),1)
                self.assertTrue(rows[0]['control_flow_qualified'])
                self.assertEqual((rows[0]['target'],rows[0]['kind']),(expected,kind))

    def test_backward_low_bit_and_word_wrap(self):
        for name,expected in (('backward',0xff80),('low_bit',0x10040),('wrap',0xfffffffe)):
            with self.subTest(name=name):
                row = observed(name)['sequences'][0]
                self.assertTrue(row['control_flow_qualified'])
                self.assertEqual(row['target'],expected)

    def test_branch_to_complete_definition_is_allowed(self):
        row = observed('branch_to_upper')['sequences'][0]
        self.assertTrue(row['control_flow_qualified'])
        self.assertEqual(row['definition_start'],0x10008)

    def test_branches_cannot_bypass_either_definition(self):
        for name,reason in (('branch_to_addition','addition-can-bypass-upper-definition'),
                            ('branch_to_jump','transfer-can-bypass-addition')):
            with self.subTest(name=name):
                row = observed(name)['sequences'][0]
                self.assertFalse(row['control_flow_qualified'])
                self.assertIn(reason,row['rejection_reasons'])

    def test_unknown_call_or_jump_blocks_function_qualification(self):
        for name in ('unknown_call','unknown_tail'):
            with self.subTest(name=name):
                result = observed(name)
                self.assertEqual(result['unresolved_register_sites'],[0x10000])
                row = result['sequences'][0]
                self.assertFalse(row['control_flow_qualified'])
                self.assertIn('function-has-unresolved-register-flow',row['rejection_reasons'])

    def test_unreachable_sequence_is_not_qualified(self):
        row = observed('unreachable')['sequences'][0]
        self.assertFalse(row['control_flow_qualified'])
        self.assertIn('definition-not-reachable-from-function-entry',row['rejection_reasons'])

    def test_nonadjacent_or_mismatched_registers_are_not_sequences(self):
        for name in ('split','split_jump','wrong_base','wrong_jump','zero_upper'):
            with self.subTest(name=name):
                self.assertEqual(observed(name)['sequences'],[])

    def test_trap_and_mid_instruction_target_block_qualification(self):
        trap = observed('trap')
        self.assertEqual(trap['invalid_control_flow'][0]['reason'],'unsupported-control-flow')
        self.assertFalse(trap['sequences'][0]['control_flow_qualified'])
        data = npu_image.jal(0x10000,0x1000a) + program('branch_to_addition')[4:]
        result = targets.inspect_function(data,0x10000)
        self.assertEqual(result['invalid_control_flow'][0]['reason'],'mid-instruction-target')
        self.assertFalse(result['sequences'][0]['control_flow_qualified'])

    def test_internal_literal_target_cannot_enter_its_own_transfer(self):
        row = observed('self_target')['sequences'][0]
        self.assertFalse(row['control_flow_qualified'])
        self.assertIn('transfer-can-bypass-addition',row['rejection_reasons'])

    def test_return_is_not_unknown_flow_and_short_sequence_is_absent(self):
        data = program('call')[-4:]
        result = targets.inspect_function(data,0x10000)
        self.assertEqual(result['unresolved_register_sites'],[])
        self.assertEqual(result['sequences'],[])
        instructions = targets.decode(program('call'),0x10000)
        self.assertIsNone(targets.literal_sequence(instructions,0))
        self.assertIsNone(targets.literal_sequence(instructions,1))

    def test_invalid_encoding_and_input_drift_fail_closed(self):
        with self.assertRaises(AssertionError):
            targets.inspect_function(b'\0\0\0\0',0x10000)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'input'
            path.write_bytes(b'synthetic input')
            with patch.object(targets,'ROOT',root):
                targets.verify_inputs({'input':hashlib.sha256(path.read_bytes()).hexdigest()})
                for inputs in ({'input':'0'*64},{'missing':'0'*64},{'../outside':'0'*64},{}):
                    with self.subTest(inputs=inputs),self.assertRaises(AssertionError):
                        targets.verify_inputs(inputs)

    def test_real_synthetic_guests_observe_targets_RA_and_registers(self):
        specs = [('call',0x10040,0x1000a,{11:0x10040},None),
                 ('tail',0x8400651c,None,{11:0x84006000,15:0x8400651c},None),
                 ('backward',0xff80,None,{11:0xff80},None),
                 ('low_bit',0x10040,0x1000a,{11:0x10041},None),
                 ('wrap',0xfffffffe,0x1000a,{11:0xffffffff},None),
                 ('branch_to_upper',0x10040,0x10012,{11:0x10040},0),
                 ('branch_to_upper',0x10040,0x10012,{11:0x10040},1)]
        for name,target,link,changes,condition in specs:
            with self.subTest(name=name,condition=condition):
                data = program(name)
                row = targets.inspect_function(data,0x10000)['sequences'][0]
                self.assertEqual(row['target'],target)
                self.assertTrue(row['control_flow_qualified'])
                cpu = Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
                cpu.mem_map(0x10000,4096)
                cpu.mem_write(0x10000,data)
                if target & ~0xfff != 0x10000:
                    cpu.mem_map(target & ~0xfff,4096)
                ids = [getattr(registers,'UC_RISCV_REG_X' + str(index)) for index in range(32)]
                for index,register in enumerate(ids[1:],1):
                    cpu.reg_write(register,0xa0000000+index)
                cpu.reg_write(registers.UC_RISCV_REG_SP,0x31000)
                if condition is not None:
                    cpu.reg_write(registers.UC_RISCV_REG_A0,condition)
                expected = [cpu.reg_read(register) for register in ids]
                for index,value in changes.items():
                    expected[index] = value
                if link is not None:
                    expected[1] = link
                writes = []
                def observe(engine,access,address,width,value,unused):
                    writes.append((address,width,value))
                hook = cpu.hook_add(UC_HOOK_MEM_WRITE,observe)
                cpu.emu_start(0x10000,target,count=100)
                cpu.hook_del(hook)
                self.assertEqual(cpu.reg_read(registers.UC_RISCV_REG_PC),target)
                values = [cpu.reg_read(register) for register in ids]
                self.assertEqual(values,expected)
                self.assertEqual(writes,[])
                GUEST_EVIDENCE.append(dict(fixture=name,branch_condition=condition,
                    program_sha256=hashlib.sha256(data).hexdigest(),PC=target,RA=values[1],SP=values[2],
                    registers_sha256=hashlib.sha256(struct.pack('<32I',*values)).hexdigest(),
                    writes=writes,observed_before_register_restoration=True,
                    synthetic_program_only=True,router_firmware_executed=False))


if __name__ == '__main__':
    unittest.main()
