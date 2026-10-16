#!/usr/bin/env python3
"""Exact assembly SP references, not a call-chain or physical stack bound."""
import argparse
import json
from pathlib import Path
import re

import capstone
from capstone import Cs, CS_ARCH_RISCV, CS_MODE_RISCV32
from capstone.riscv import (RISCV_INS_ADDI, RISCV_OP_IMM, RISCV_OP_MEM,
                            RISCV_OP_REG, RISCV_REG_SP)

import native_prefix_snapshot
import npu_image
from npu_stack_usage import ROOT, digest

ASSEMBLY_ONLY = ('bridge', 'reset', 'order', 'egress')
WRAPPERS = {
    'base': ('npu_emulation_mailbox_register',),
    'bridge': ('npu_emulation_bridge_base_guard', 'npu_emulation_bridge_channel_guard'),
    'reset': ('npu_emulation_allocator_reset_prepare',),
    'allocator': ('npu_emulation_allocator_startup_dispatch',),
}


def scan(data, address):
    decoder = Cs(CS_ARCH_RISCV, CS_MODE_RISCV32)
    decoder.detail = True
    instructions = list(decoder.disasm(data, address))
    assert instructions and b''.join(bytes(i.bytes) for i in instructions) == data, 'incomplete-assembly-decode'
    assert all(i.size == 4 for i in instructions), 'unexpected-compressed-assembly'
    rows = []
    for instruction in instructions:
        operands = instruction.operands
        registers = [o.reg for o in operands if o.type == RISCV_OP_REG]
        memory = [o for o in operands if o.type == RISCV_OP_MEM and o.mem.base == RISCV_REG_SP]
        if RISCV_REG_SP not in registers and not memory:
            continue
        row = dict(address=instruction.address, bytes=bytes(instruction.bytes).hex(),
                   mnemonic=instruction.mnemonic, operands=instruction.op_str, kind='other-SP-reference')
        if (instruction.id == RISCV_INS_ADDI and len(operands) == 3 and
                all(o.type == RISCV_OP_REG and o.reg == RISCV_REG_SP for o in operands[:2]) and
                operands[2].type == RISCV_OP_IMM):
            row.update(kind='SP-adjustment', delta=operands[2].imm)
        elif memory and RISCV_REG_SP not in registers:
            assert len(memory) == 1
            row.update(kind='SP-based-memory', offset=memory[0].mem.disp,
                       register=decoder.reg_name(registers[0]) if len(registers) == 1 else None)
        rows.append(row)
    return dict(address=address, bytes=len(data), sha256=npu_image.sha(data),
                instructions=len(instructions), SP_references=rows)


def match_code(data, address, code, code_base):
    offset = address - code_base
    assert offset >= 0 and offset + len(data) <= len(code), 'assembly-outside-raw-CODE'
    assert code[offset:offset + len(data)] == data, 'assembly-raw-CODE-drift'


def check_contract(components, wrappers):
    assert set(components) == set(ASSEMBLY_ONLY), 'assembly-component-set'
    assert set(wrappers) == {name for names in WRAPPERS.values() for name in names}, 'assembly-wrapper-set'
    assert all(not row['SP_references'] for row in wrappers.values()), 'wrapper-SP-reference'
    for name in ('bridge', 'reset'):
        assert not components[name]['SP_references'], ('assembly-SP-reference', name)
    order = components['order']['SP_references']
    assert len(order) == 1 and (order[0]['kind'], order[0]['mnemonic'], order[0].get('offset'),
            order[0].get('register')) == ('SP-based-memory', 'lhu', 6, 'a4'), 'ring-caller-stack-read'
    expected = [('SP-adjustment', -16), ('SP-adjustment', -48)]
    expected += [('SP-based-memory', 'sw', index * 4, register) for index, register in
                 enumerate(('a0', 'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'ra', 't1', 't4', 'zero'))]
    observed = []
    for row in components['egress']['SP_references']:
        observed.append((row['kind'], row.get('delta')) if row['kind'] == 'SP-adjustment' else
                        (row['kind'], row['mnemonic'], row.get('offset'), row.get('register')))
    assert observed == expected, ('egress-local-stack-contract', observed)


def audit(reference):
    manifest_path = reference / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    inputs = dict(manifest['inputs'])
    payloads = {}
    for key, filename in (('code', 'CODE.bin'), ('data', 'DATA.bin')):
        path = reference / filename
        data = path.read_bytes()
        assert len(data) == manifest[key]['bytes'] and npu_image.sha(data) == manifest[key]['sha256']
        inputs[str(path.relative_to(ROOT))] = digest(path)
        payloads[key] = data
    components, wrappers = {}, {}
    for name in sorted(set(ASSEMBLY_ONLY) | set(WRAPPERS)):
        path = (ROOT / manifest['symbol_files'][name]).resolve()
        assert path.is_relative_to(reference)
        assert digest(path) == manifest['components'][name]['sha256']
        inputs[str(path.relative_to(ROOT))] = digest(path)
        binary = npu_image.elf(path)
        executable = [section for section in binary.iter_sections() if section['sh_flags'] & 4]
        if name in ASSEMBLY_ONLY:
            assert len(executable) == 1 and executable[0].name == '.text', 'assembly-executable-section-set'
            section = executable[0]
            match_code(section.data(), section['sh_addr'], payloads['code'], manifest['code']['base'])
            components[name] = scan(section.data(), section['sh_addr'])
        symbols = list(binary.get_section_by_name('.symtab').iter_symbols())
        for symbol_name in WRAPPERS.get(name, ()):
            found = [symbol for symbol in symbols if symbol.name == symbol_name]
            assert len(found) == 1
            symbol = found[0]
            assert symbol['st_info']['type'] == 'STT_FUNC' and symbol['st_size']
            section = binary.get_section(symbol['st_shndx'])
            assert section in executable
            offset = symbol['st_value'] - section['sh_addr']
            assert 0 <= offset and offset + symbol['st_size'] <= section['sh_size']
            data = section.data()[offset:offset + symbol['st_size']]
            match_code(data, symbol['st_value'], payloads['code'], manifest['code']['base'])
            wrappers[symbol_name] = dict(scan(data, symbol['st_value']), component=name)
    check_contract(components, wrappers)
    for path in (manifest_path, Path(__file__)):
        inputs[str(path.relative_to(ROOT))] = digest(path)
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(digest(ROOT / name) == expected for name, expected in inputs.items()), 'assembly-source-drift'
    return dict(passed=True, capstone_version=capstone.__version__, components=components, wrappers=wrappers,
        complete_scanned_ranges_match_raw_CODE=True, inputs=inputs,
        complete_call_chain_bound_proven=False, all_linked_assembly_covered=False, hardware=False,
        limits=['Four pure-assembly text sections and five explicitly typed wrappers are decoded completely.',
                'The component sections overlap three wrapper ranges; do not count them twice.',
                'Egress local SP changes and the caller-owned ring load are not complete permitted path bounds.',
                'C-bearing component assembly, original firmware, indirect calls, IRQ nesting and physical stacks remain separate.',
                'No guest execution, memory mutation, new native admission or physical performance measurement.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    reference = args.pair.resolve()
    assert reference.is_relative_to(ROOT / '.local')
    output = ROOT / '.local/npu-assembly-stack' / args.name / 'result.json'
    output.parent.mkdir(parents=True, exist_ok=False)
    result = audit(reference)
    with output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, assembly_components=len(result['components']),
        typed_wrappers=len(result['wrappers']), complete_call_chain_bound_proven=False,
        receipt=str(output.relative_to(ROOT)), sha256=digest(output))), flush=True)


if __name__ == '__main__': main()
