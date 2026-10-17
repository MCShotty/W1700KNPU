"""Synthetic RV32 decoder/guest contracts,not router or whole-stack tests."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import unittest

from unicorn import Uc,UC_ARCH_RISCV,UC_MODE_RISCV32,UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r
import npu_image
import test_npu_displaced_prefix_stack as prefix

FIXTURE_PATH = Path(__file__).with_name('displaced_prefix_fixtures.json')
_fixture_bytes = FIXTURE_PATH.read_bytes()
FIXTURE_SHA256 = hashlib.sha256(_fixture_bytes).hexdigest()
FIXTURES = json.loads(_fixture_bytes)
assert FIXTURES['format'] == 'synthetic-rv32-prefix-programs-v1' and FIXTURES['synthetic_only'] is True
GOOD = dict(plain=(12,0,0),frame=(12,16,-16),token=(12,16,-16),mixed=(8,0,0),multiple=(20,48,-32))
GUEST_EVIDENCE = []


def program(name):
    data = bytes.fromhex(FIXTURES['programs'][name]['text_hex'])
    assert len(data) == 68
    return data


def contract_fixture():
    return {name:dict(bytes=length,local_prefix_peak_bytes=peak,exit_SP_delta=-peak,
        complete_callee_frame_proven=False,stack_stores=[dict(entry_SP_offset=-8,bytes=4,register='s0')]
        if stores else []) for name,(_,length,peak,stores) in prefix.PREFIXES.items()}


class DisplacedPrefixStackTests(unittest.TestCase):
    def reject(self,*names):
        for name in names:
            with self.subTest(name=name),self.assertRaises(AssertionError):
                prefix.scan_prefix(program(name),FIXTURES['address'])

    def test_plain_frame_token_and_compressed_prefixes(self):
        for name,(length,peak,delta) in GOOD.items():
            with self.subTest(name=name):
                row = prefix.scan_prefix(program(name),FIXTURES['address'])
                self.assertEqual((row['bytes'],row['local_prefix_peak_bytes'],row['exit_SP_delta']),(length,peak,delta))
                self.assertEqual(row['continuation_target'],FIXTURES['continuation'])
                self.assertFalse(row['complete_callee_frame_proven'])

    def test_real_synthetic_guest_SP_registers_and_writes(self):
        values = [0x11111111 * (index+1) for index in range(6)]
        for name in (*GOOD,'backward'):
            with self.subTest(name=name):
                data = program(name) if name != 'backward' else program('plain')[:8] + \
                    npu_image.jal(FIXTURES['address']+8,FIXTURES['address']-128)
                continuation = FIXTURES['continuation'] if name != 'backward' else FIXTURES['address']-128
                row = prefix.scan_prefix(data,FIXTURES['address'])
                self.assertEqual(row['continuation_target'],continuation)
                cpu = Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
                cpu.mem_map(0x10000,4096)
                cpu.mem_write(0x10000,data)
                if name == 'backward': cpu.mem_map(continuation & ~0xfff,4096)
                cpu.mem_map(0x20000,4096)
                cpu.mem_write(0x20000,struct.pack('<6I',*values))
                cpu.mem_map(0x30000,8192)
                registers = [getattr(r,'UC_RISCV_REG_X' + str(index)) for index in range(32)]
                for index,register in enumerate(registers[1:],1): cpu.reg_write(register,0xa0000000 + index)
                cpu.reg_write(r.UC_RISCV_REG_SP,0x31000)
                cpu.reg_write(r.UC_RISCV_REG_A0,0x20000)
                cpu.reg_write(r.UC_RISCV_REG_S0,0xa5b6c7d8)
                expected = [cpu.reg_read(register) for register in registers]
                expected[2] += row['exit_SP_delta']
                if name in ('plain','backward'): expected[10],expected[11] = values[2],values[0]
                elif name == 'token': expected[11] = values[2]
                elif name == 'mixed': expected[14],expected[15] = values[5],values[0]
                writes = []
                def observe(engine,access,address,width,value,unused): writes.append((address,width,value))
                hook = cpu.hook_add(UC_HOOK_MEM_WRITE,observe)
                cpu.emu_start(FIXTURES['address'],continuation,count=100)
                cpu.hook_del(hook)
                self.assertEqual(cpu.reg_read(r.UC_RISCV_REG_PC),continuation)
                observed = [cpu.reg_read(register) for register in registers]
                self.assertEqual(observed,expected)
                self.assertEqual(writes,[(0x31000+item['entry_SP_offset'],4,0xa5b6c7d8) for item in row['stack_stores']])
                GUEST_EVIDENCE.append(dict(fixture=name,program_sha256=hashlib.sha256(data).hexdigest(),
                    PC=cpu.reg_read(r.UC_RISCV_REG_PC),SP=observed[2],
                    registers_sha256=hashlib.sha256(struct.pack('<32I',*observed)).hexdigest(),
                    writes=writes,synthetic_program_only=True,router_firmware_executed=False))

    def test_missing_or_truncated_tail_is_rejected(self):
        for data in (b'',program('plain')[:8],program('plain')[:10]):
            with self.subTest(data=data.hex()),self.assertRaises(AssertionError): prefix.scan_prefix(data,0x10000)

    def test_dynamic_or_loaded_SP_is_rejected(self): self.reject('dynamic_SP','loaded_SP','stack_load')

    def test_unaligned_or_above_entry_SP_is_rejected(self): self.reject('unaligned_SP','above_SP')

    def test_outside_frame_and_foreign_stores_are_rejected(self):
        self.reject('outside_frame','negative_slot','no_frame','foreign_store')

    def test_conditionals_calls_and_indirect_flow_are_rejected(self): self.reject('conditional','call','indirect')

    def test_self_and_fallthrough_jumps_are_rejected(self): self.reject('self','fallthrough')

    def test_unknown_instructions_and_traps_are_rejected(self): self.reject('trap','unsupported','invalid')

    def test_prefix_byte_limit_is_enforced(self):
        with self.assertRaises(AssertionError): prefix.scan_prefix(program('multiple'),0x10000,max_bytes=8)

    def test_exact_nine_prefix_contract(self): prefix.check_contract(contract_fixture())

    def test_contract_rejects_missing_extra_and_altered_metadata(self):
        for mutation in ('missing','extra','length','peak','delta','slot','whole_frame'):
            with self.subTest(mutation=mutation),self.assertRaises(AssertionError):
                rows = copy.deepcopy(contract_fixture())
                name = 'npu_original_irq_trampoline'
                if mutation == 'missing': del rows[name]
                elif mutation == 'extra': rows['unknown'] = rows[name]
                elif mutation == 'length': rows[name]['bytes'] += 4
                elif mutation == 'peak': rows[name]['local_prefix_peak_bytes'] = 0
                elif mutation == 'delta': rows[name]['exit_SP_delta'] = 0
                elif mutation == 'slot': rows[name]['stack_stores'][0]['entry_SP_offset'] = 0
                else: rows[name]['complete_callee_frame_proven'] = True
                prefix.check_contract(rows)


if __name__ == '__main__': unittest.main()
