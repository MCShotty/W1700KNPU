#!/usr/bin/env python3
"""Resolved direct-call frame candidates; unresolved calls prevent a full bound."""
import argparse
from bisect import bisect_right
from collections import Counter
import json
from pathlib import Path
import re

import capstone
from capstone import Cs, CS_ARCH_RISCV, CS_MODE_RISCV32, CS_MODE_RISCVC
from capstone.riscv import RISCV_OP_IMM, RISCV_OP_REG, RISCV_REG_RA
from elftools.dwarf.callframe import FDE

import native_prefix_snapshot
import npu_image
from npu_stack_usage import ROOT, digest
from test_npu_assembly_stack_usage import match_code


def decode(data, address):
    decoder = Cs(CS_ARCH_RISCV, CS_MODE_RISCV32 | CS_MODE_RISCVC)
    decoder.detail = True
    result = list(decoder.disasm(data, address))
    assert result and b''.join(bytes(i.bytes) for i in result) == data, 'incomplete-C-function-decode'
    return result


def transfer(instruction, previous):
    name, operands = instruction.mnemonic, instruction.operands
    # This backend labels some returns and tail jumps as CALL; use actual operands.
    if name == 'ret' or (name in ('jr', 'c.jr') and len(operands) == 1 and
                        operands[0].type == RISCV_OP_REG and operands[0].reg == RISCV_REG_RA):
        return None
    if name in ('j', 'c.j', 'jal', 'c.jal'):
        assert operands[-1].type == RISCV_OP_IMM
        return dict(target=(instruction.address + operands[-1].imm) & 0xffffffff,
                    kind='direct-tail' if name in ('j', 'c.j') else 'direct-call')
    if name in ('beq', 'bne', 'blt', 'bge', 'bltu', 'bgeu', 'beqz', 'bnez',
                'blez', 'bgez', 'bltz', 'bgtz', 'bgt', 'ble', 'bgtu', 'bleu', 'c.beqz', 'c.bnez'):
        assert operands[-1].type == RISCV_OP_IMM
        return dict(target=(instruction.address + operands[-1].imm) & 0xffffffff,
                    kind='conditional-direct-transfer')
    if name == 'jalr':
        assert len(operands) == 3 and all(o.type == RISCV_OP_REG for o in operands[:2])
        assert operands[2].type == RISCV_OP_IMM
        if (previous is not None and previous.address + previous.size == instruction.address and
                previous.mnemonic == 'auipc' and previous.operands[0].reg == operands[1].reg and
                previous.operands[1].type == RISCV_OP_IMM):
            target = previous.address + (previous.operands[1].imm << 12) + operands[2].imm
            return dict(target=target & 0xfffffffe, kind='AUIPC-direct-call' if
                        operands[0].reg == RISCV_REG_RA else 'AUIPC-direct-tail')
        return dict(target=None, kind='unresolved-register-call')
    if name in ('jr', 'c.jr', 'c.jalr'):
        return dict(target=None, kind='unresolved-register-transfer')
    return None


def internal_transfer(edge, address, length):
    if edge['target'] is None or not address <= edge['target'] < address + length:
        return False
    if 'call' in edge['kind']:
        return False
    return edge['target'] != address


def cfa_table(entry):
    table = entry.get_decoded().table
    assert table and table[0]['pc'] == entry['initial_location']
    assert [point['pc'] for point in table] == sorted({point['pc'] for point in table})
    assert all(point['cfa'].reg == 2 and point['cfa'].expr is None and
               point['cfa'].offset >= 0 and point['cfa'].offset % 16 == 0 for point in table), 'unbounded-CFA'
    return [(point['pc'], point['cfa'].offset) for point in table]


def candidates(functions):
    cache, active, cycles = {}, [], []

    def visit(address):
        if address in active:
            cycles.append(active[active.index(address):] + [address])
            return None
        if address in cache:
            return cache[address]
        active.append(address)
        function = functions[address]
        result = dict(bytes=function['frame'], chain=[address], callsites=[])
        cyclic = False
        for edge in function['transfers']:
            target = edge['target']
            if target not in functions:
                continue
            child = visit(target)
            if child is None:
                cyclic = True
                continue
            size = edge['caller_CFA'] + child['bytes']
            if size > result['bytes']:
                result = dict(bytes=size, chain=[address, *child['chain']],
                              callsites=[edge['address'], *child['callsites']])
        active.pop()
        cache[address] = None if cyclic else result
        return cache[address]

    for address in functions:
        visit(address)
    return cache, cycles


def audit(pair, frames_path):
    manifest = json.loads((pair / 'manifest.json').read_bytes())
    frames = json.loads(frames_path.read_bytes())
    assert frames['passed'] and frames['complete_CODE_DATA_byte_identical']
    assert frames['component_count'] == len(manifest['components'])
    inputs = dict(frames['inputs'])
    code = (pair / 'CODE.bin').read_bytes()
    assert npu_image.sha(code) == manifest['code']['sha256'] and len(code) == manifest['code']['bytes']
    data = (pair / 'DATA.bin').read_bytes()
    assert npu_image.sha(data) == manifest['data']['sha256'] and len(data) == manifest['data']['bytes']
    functions = {}
    for row in frames['components']:
        component = row['component']
        path = (ROOT / manifest['symbol_files'][component]).resolve()
        assert path.is_relative_to(pair) and digest(path) == manifest['components'][component]['sha256']
        binary = npu_image.elf(path)
        symbols = {s['st_value']: s for s in binary.get_section_by_name('.symtab').iter_symbols()
                   if s['st_info']['type'] == 'STT_FUNC' and s['st_size'] and isinstance(s['st_shndx'], int)}
        expected = Counter((frame['function'], frame['bytes']) for frame in row['frames'])
        observed = Counter()
        dwarf = binary.get_dwarf_info()
        for entry in dwarf.CFI_entries() if dwarf.has_CFI() else ():
            if not isinstance(entry, FDE): continue
            address = entry['initial_location']
            assert address in symbols and address not in functions, 'ambiguous-CFI-function'
            symbol = symbols[address]
            assert entry['address_range'] == symbol['st_size'], 'CFI-symbol-extent-drift'
            table = cfa_table(entry)
            frame = max(offset for _, offset in table)
            observed[(symbol.name, frame)] += 1
            section = binary.get_section(symbol['st_shndx'])
            offset = address - section['sh_addr']
            data = section.data()[offset:offset + symbol['st_size']]
            match_code(data, address, code, manifest['code']['base'])
            instructions, transfers = decode(data, address), []
            points = [pc for pc, _ in table]
            for index, instruction in enumerate(instructions):
                edge = transfer(instruction, instructions[index - 1] if index else None)
                if edge is None or internal_transfer(edge, address, len(data)):
                    continue
                if edge['target'] is not None and address < edge['target'] < address + len(data):
                    edge.update(interior_target=edge['target'], target=address, kind='self-interior-call')
                edge.update(address=instruction.address, caller_CFA=table[bisect_right(points, instruction.address) - 1][1],
                            instruction=instruction.mnemonic + ' ' + instruction.op_str)
                transfers.append(edge)
            functions[address] = dict(component=component, name=symbol.name, address=address,
                bytes=len(data), frame=frame, instructions=len(instructions), transfers=transfers)
        assert observed == expected, ('CFI-compiler-frame-drift', component, observed - expected, expected - observed)
    unresolved = [dict(caller=address, **edge) for address, function in functions.items()
                  for edge in function['transfers'] if edge['target'] not in functions]
    chains, cycles = candidates(functions)
    ranked = sorted((dict(root=address, **chain) for address, chain in chains.items() if chain is not None),
                    key=lambda row: (-row['bytes'], row['root']))
    for path in (pair / 'manifest.json', pair / 'CODE.bin', pair / 'DATA.bin', frames_path, Path(__file__)):
        inputs[str(path.relative_to(ROOT))] = digest(path)
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(digest(ROOT / name) == expected for name, expected in inputs.items()), 'direct-stack-source-drift'
    return dict(passed=True, CFI_compiler_frames_matched=len(functions), functions=list(functions.values()),
        resolved_direct_transfers=sum(edge['target'] in functions for f in functions.values() for edge in f['transfers']),
        unresolved_transfers=unresolved, cycles=cycles, ranked_direct_chain_candidates=ranked,
        complete_call_chain_bound_proven=False, original_assembly_included=False, hardware=False,
        capstone_version=capstone.__version__, inputs=inputs, limits=[
            'Every C frame is independently matched to an exact linked symbol extent and SP-based DWARF CFA records.',
            'Candidates follow only resolved direct edges and account for the CFA at each call or tail-transfer site.',
            'Direct graph paths may be infeasible; missing indirect/assembly/original edges prevent any whole-stack bound.',
            'Cycles are reported without assigning a finite candidate to cycle-reaching roots.',
            'This does not establish allowed reader/callback targets, IRQ nesting, per-hart placement or physical acceptance.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--frames', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    pair, frames = args.pair.resolve(), args.frames.resolve()
    assert pair.is_relative_to(ROOT / '.local') and frames.is_relative_to(ROOT / '.local')
    output = ROOT / '.local/npu-direct-stack' / args.name / 'result.json'
    output.parent.mkdir(parents=True, exist_ok=False)
    result = audit(pair, frames)
    with output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, frames=result['CFI_compiler_frames_matched'],
        direct_transfers=result['resolved_direct_transfers'], unresolved=len(result['unresolved_transfers']),
        cycles=len(result['cycles']), largest_direct_candidate=result['ranked_direct_chain_candidates'][0]['bytes'],
        complete_call_chain_bound_proven=False, receipt=str(output.relative_to(ROOT)), sha256=digest(output))), flush=True)


if __name__ == '__main__': main()
