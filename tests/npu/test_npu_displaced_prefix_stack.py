#!/usr/bin/env python3
"""Exact displaced-prefix SP contracts,not complete function or stack bounds."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import capstone
from capstone import Cs,CS_ARCH_RISCV,CS_MODE_RISCV32,CS_MODE_RISCVC
from capstone.riscv import RISCV_OP_IMM,RISCV_OP_MEM,RISCV_OP_REG,RISCV_REG_SP
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
PREFIXES = {
    'npu_original_irq_trampoline':('base',12,16,1),
    'npu_original_desc_callback':('txdone',12,0,0),
    'npu_original_tx_callback':('cold-tx',12,0,0),
    'npu_original_token_callback':('cold-tx',12,16,0),
    'npu_original_descriptor_callback':('cold-descriptor',12,16,1),
    'npu_original_txbuf_callback':('cold-tx-buffer',12,0,0),
    'npu_original_rx_event_callback':('cold-rx-event',12,0,0),
    'npu_original_rx_pcie_callback':('cold-rx-pcie',12,0,0),
    'npu_original_inode_callback':('cold-inode',8,0,0),
}


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def scan_prefix(data,address,max_bytes=32):
    assert 0 <= address <= 0xffffffff and address % 2 == 0 and max_bytes > 0
    decoder = Cs(CS_ARCH_RISCV,CS_MODE_RISCV32|CS_MODE_RISCVC)
    decoder.detail = True
    delta,peak,consumed,steps,stores = 0,0,0,[],[]
    for instruction in decoder.disasm(data[:max_bytes],address):
        assert instruction.address == address + consumed
        consumed += instruction.size
        name,ops = instruction.mnemonic,instruction.operands
        step = dict(address=instruction.address,bytes=bytes(instruction.bytes).hex(),
            mnemonic=name,operands=instruction.op_str)
        if name in ('j','c.j'):
            assert len(ops) == 1 and ops[0].type == RISCV_OP_IMM
            target = (instruction.address + ops[0].imm) & 0xffffffff
            assert not address <= target <= address + consumed, 'prefix-interior-or-fallthrough-jump'
            steps.append(dict(step,SP_delta_after=delta))
            return dict(address=address,bytes=consumed,raw_bytes=data[:consumed].hex(),
                local_prefix_peak_bytes=peak,exit_SP_delta=delta,stack_stores=stores,
                continuation_target=target,instructions=steps,complete_callee_frame_proven=False)
        if name == 'addi':
            assert len(ops) == 3 and all(op.type == RISCV_OP_REG and op.reg == RISCV_REG_SP for op in ops[:2])
            assert ops[2].type == RISCV_OP_IMM and ops[2].imm % 16 == 0, 'unaligned-prefix-SP'
            delta += ops[2].imm
            assert delta <= 0, 'prefix-SP-above-entry'
            peak = max(peak,-delta)
        elif name == 'lw':
            assert len(ops) == 2 and ops[0].type == RISCV_OP_REG and ops[0].reg != RISCV_REG_SP
            assert ops[1].type == RISCV_OP_MEM and ops[1].mem.base != RISCV_REG_SP, 'unmodeled-prefix-stack-load'
        elif name == 'c.lw':
            # Capstone exposes the compressed load as destination,offset,base.
            assert len(ops) == 3 and ops[0].type == RISCV_OP_REG and ops[0].reg != RISCV_REG_SP
            assert ops[1].type == RISCV_OP_IMM and ops[1].imm >= 0 and ops[1].imm % 4 == 0
            assert ops[2].type == RISCV_OP_REG and ops[2].reg != RISCV_REG_SP, 'unmodeled-compressed-stack-load'
        elif name == 'sw':
            assert len(ops) == 2 and ops[0].type == RISCV_OP_REG and ops[0].reg != RISCV_REG_SP
            assert ops[1].type == RISCV_OP_MEM and ops[1].mem.base == RISCV_REG_SP, 'unmodeled-prefix-store'
            offset = delta + ops[1].mem.disp
            assert delta <= offset and offset + 4 <= 0 and offset % 4 == 0, 'prefix-store-outside-reservation'
            stores.append(dict(address=instruction.address,entry_SP_offset=offset,bytes=4,
                register=decoder.reg_name(ops[0].reg)))
        else:
            raise AssertionError(('unsupported-prefix-instruction',name,instruction.op_str))
        steps.append(dict(step,SP_delta_after=delta))
    raise AssertionError('no-complete-prefix-tail-within-byte-limit')


def check_contract(rows):
    assert rows.keys() == PREFIXES.keys(), 'displaced-prefix-set'
    for name,(_,length,peak,store_count) in PREFIXES.items():
        row = rows[name]
        assert row['bytes'] == length and row['local_prefix_peak_bytes'] == peak
        assert row['exit_SP_delta'] == -peak and row['complete_callee_frame_proven'] is False
        assert len(row['stack_stores']) == store_count
        if store_count:
            assert [(item['entry_SP_offset'],item['bytes'],item['register']) for item in row['stack_stores']] == [(-8,4,'s0')]


def audit(pair):
    manifest_path = pair / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    code = (pair / 'CODE.bin').read_bytes()
    assert len(code) == manifest['code']['bytes'] and hashlib.sha256(code).hexdigest() == manifest['code']['sha256']
    data = (pair / 'DATA.bin').read_bytes()
    assert len(data) == manifest['data']['bytes'] and hashlib.sha256(data).hexdigest() == manifest['data']['sha256']
    inputs = {str(path.relative_to(ROOT)):digest(path) for path in
        (Path(__file__),manifest_path,pair / 'CODE.bin',pair / 'DATA.bin')}
    rows = {}
    for name,(component,_,_,_) in PREFIXES.items():
        path = ROOT / manifest['symbol_files'][component]
        assert not path.is_symlink() and path.resolve().is_relative_to(pair)
        assert digest(path) == manifest['components'][component]['sha256']
        inputs[str(path.relative_to(ROOT))] = digest(path)
        with path.open('rb') as stream:
            binary = ELFFile(stream)
            assert binary.elfclass == 32 and binary['e_machine'] == 'EM_RISCV'
            symbols = [symbol for symbol in binary.get_section_by_name('.symtab').iter_symbols()
                if symbol.name == name and isinstance(symbol['st_shndx'],int)]
            assert len(symbols) == 1, ('ambiguous-displaced-symbol',name)
            symbol = symbols[0]
            section = binary.get_section(symbol['st_shndx'])
            assert section['sh_flags'] & 4
            offset = symbol['st_value'] - section['sh_addr']
            assert 0 <= offset < section['sh_size']
            data = section.data()[offset:offset+32]
            row = scan_prefix(data,symbol['st_value'])
            raw_offset = row['address'] - manifest['code']['base']
            assert raw_offset >= 0 and code[raw_offset:raw_offset+row['bytes']] == bytes.fromhex(row['raw_bytes'])
            assert manifest['code']['base'] <= row['continuation_target'] < manifest['code']['base'] + len(code)
            assert not symbol['st_size'] or symbol['st_size'] == row['bytes'], ('declared-prefix-extent-drift',name)
            rows[name] = dict(row,component=component)
    check_contract(rows)
    assert all(digest(ROOT / name) == expected for name,expected in inputs.items())
    return dict(passed=True,prefixes=rows,inputs=inputs,capstone_version=capstone.__version__,
        raw_CODE_sha256=manifest['code']['sha256'],raw_DATA_sha256=manifest['data']['sha256'],
        component_count=len(manifest['components']),all_nine_selected_prefixes_match_raw_CODE=True,
        earlier_C_graph_replayed=False,complete_call_chain_bound_proven=False,guest_execution=False,hardware=False,
        limits=['Only nine named entry prefixes through their first unconditional direct jump are measured,not complete callees.',
            'Three prefixes reserve16 local bytes before their continuation;this must not be added blindly to original frames.',
            'Original continuations,indirect targets,IRQ nesting,per-hart/physical placement and any whole-stack bound remain open.',
            'No source/guard/image/native-admission change or physical performance measurement.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair',type=Path,required=True)
    parser.add_argument('--name',required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    pair = args.pair.resolve()
    assert pair.is_relative_to(ROOT / '.local')
    result = audit(pair)
    output = ROOT / '.local/npu-displaced-prefix-stack' / args.name / 'result.json'
    output.parent.mkdir(parents=True,exist_ok=False)
    with output.open('x') as stream: stream.write(json.dumps(result,indent=2) + '\n')
    print(json.dumps(dict(passed=True,selected_prefixes=len(result['prefixes']),whole_bound=False,
        sha256=digest(output))),flush=True)


if __name__ == '__main__': main()
