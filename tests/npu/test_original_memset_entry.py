#!/usr/bin/env python3
"""Conditional original computed-entry/zero-SP proof; never physical acceptance."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import traceback
from unittest.mock import patch

import capstone
from elftools.elf.elffile import ELFFile
import z3

import native_prefix_snapshot
import original_memset_entry as entry
from test_original_memset_native import ROOT, CODE, ENTRY, STOP, digest, load_code


def loaded_solver_paths():
    mapped = set()
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields = line.split(None,5)
        if len(fields) == 6 and Path(fields[5]).name.startswith('libz3.so'):
            path = Path(fields[5])
            assert path.is_absolute() and path.is_file(), 'invalid-mapped-solver-path'
            mapped.add(path.resolve())
    assert len(mapped) == 1, 'missing-or-multiple-mapped-solvers'
    return [Path(z3.__file__).resolve(),*mapped]


def solver_inputs(receipt_path):
    receipt = json.loads(receipt_path.read_bytes())
    assert receipt['passed'] and receipt['package'] == 'z3-solver'
    assert receipt['version'] == z3.get_full_version()
    inputs = dict(receipt['files'])
    assert receipt['input_count'] == len(inputs)
    for name, expected in inputs.items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT / '.local'), 'solver-path-outside-local'
        assert digest(path) == expected, ('solver-input-drift',name)
    loaded = loaded_solver_paths()
    assert all(str(path.relative_to(ROOT)) in inputs for path in loaded), 'unbound-loaded-solver'
    inputs[str(receipt_path.relative_to(ROOT))] = digest(receipt_path)
    return inputs


def public_function(path):
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        assert elf.elfclass == 32 and elf.little_endian and elf['e_machine'] == 'EM_RISCV'
        assert elf['e_entry'] == ENTRY
        symbols = [symbol for symbol in elf.get_section_by_name('.symtab').iter_symbols()
                   if symbol.name == 'memset']
        assert len(symbols) == 1
        symbol = symbols[0]
        assert symbol['st_value'] == ENTRY and symbol['st_size'] == STOP-ENTRY
        section = elf.get_section(symbol['st_shndx'])
        offset = symbol['st_value']-section['sh_addr']
        assert 0 <= offset < offset+symbol['st_size'] <= section['sh_size']
        result = section.data()[offset:offset+symbol['st_size']]
    assert len(result) == STOP-ENTRY
    return result


def bit_controls(data):
    records, reasons = [], Counter()
    for offset in range(len(data)):
        for bit in range(8):
            changed = bytearray(data)
            changed[offset] ^= 1<<bit
            try:
                entry.inspect_entry(bytes(changed))
            except AssertionError as error:
                reason = error.args[0]
                reason = reason[0] if isinstance(reason,tuple) else reason
                assert reason in ('instruction-contract-drift','instruction-boundary-drift',
                                  'incomplete-C-function-decode'), ('unexpected-bit-rejection',reason)
                reasons[reason] += 1
                records.append(dict(offset=offset,bit=bit,rejected=True,reason=reason))
            else:
                raise AssertionError(('single-bit-mutant-survived',offset,bit))
    assert len(records) == 1344
    return dict(controls=records,total=len(records),reasons=dict(reasons),
                core_called_directly_without_outer_hash_rejection=True,original_bytes_not_modified=True)


def proof_controls(data):
    """Corrupt one proof intermediate at a time,not firmware or original coverage."""
    records = []
    original_flow, original_registers = entry.flow,entry.register_flow
    changes = [('unknown-tail-limit-'+str(offset),'constants',offset,6,None,'tail-limit-not-known')
               for offset in (4,38,162)]
    changes += [('lost-tail-mask','definitions',38,12,frozenset({ENTRY}),'tail-mask-not-reaching-definition'),
        ('lost-alignment-mask','definitions',12,15,frozenset({ENTRY}),'alignment-mask-not-reaching-definition'),
        ('incoming-RA-overwritten','definitions',148,1,frozenset({ENTRY}),'incoming-RA-not-preserved-before-save'),
        ('saved-RA-overwritten','definitions',154,5,frozenset({ENTRY}),'saved-RA-not-preserved-by-suffix'),
        ('unknown-linked-return','definitions',154,1,frozenset({ENTRY}),'link-return-not-known')]
    for name,kind,offset,register,value,expected in changes:
        def corrupt(*args):
            constants,definitions,updates = original_registers(*args)
            table = constants if kind == 'constants' else definitions
            changed = list(table[ENTRY+offset])
            changed[register] = value
            table[ENTRY+offset] = tuple(changed)
            return constants,definitions,updates
        with patch.object(entry,'register_flow',side_effect=corrupt):
            rejected(records,name,expected,lambda: entry.inspect_entry(data))
    for offset,expected in ((42,'unchecked-tail-entry'),(138,'unchecked-alignment-entry'),
                            (46,'computed-prefix-bypass'),(142,'computed-prefix-bypass'),
                            (154,'unreviewed-postcall-entry')):
        def corrupt(*args):
            positions,successors,edges,predecessors = original_flow(*args)
            predecessors[ENTRY+offset].add(ENTRY)
            return positions,successors,edges,predecessors
        with patch.object(entry,'flow',side_effect=corrupt):
            rejected(records,'extra-entry-'+str(offset),expected,lambda: entry.inspect_entry(data))
    original_reachable = entry.reachable
    for target,expected in ((42,'tail-safe-edges-do-not-dominate'),
                            (138,'alignment-safe-edge-does-not-dominate')):
        def corrupt(*args,**kwargs):
            result = original_reachable(*args,**kwargs)
            result.add(ENTRY+target)
            return result
        with patch.object(entry,'reachable',side_effect=corrupt):
            rejected(records,'cutset-bypass-'+str(target),expected,lambda: entry.inspect_entry(data))
    assert len(records) == 15
    return records


def rejected(records,name,expected,operation):
    try:
        operation()
    except AssertionError as error:
        assert expected in str(error), ('unexpected-proof-control-rejection',name,str(error))
        records.append(dict(name=name,rejected=True,reason=str(error),synthetic_proof_intermediate_only=True))
    else:
        raise AssertionError(('proof-control-survived',name))


def main():
    parser = argparse.ArgumentParser()
    for name in ('pair','original','export','public-elf','solver-receipt'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--name',required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    paths = [path.resolve() for path in (args.pair,args.original,args.export,args.public_elf,args.solver_receipt)]
    assert all(path.is_relative_to(ROOT / '.local') for path in paths)
    code,inputs = load_code(*paths[:3])
    inputs.update(solver_inputs(paths[4]))
    inputs[str(paths[3].relative_to(ROOT))] = digest(paths[3])
    inputs = native_prefix_snapshot.source_inputs(inputs)
    carrier = code[ENTRY-CODE:STOP-CODE]
    assert public_function(paths[3]) == carrier, 'compiled-public-function-does-not-match'
    output = ROOT / '.local/npu-original-memset-entry' / args.name
    output.mkdir(parents=True,exist_ok=False)
    stage = 'original-entry-proof'
    try:
        proof = entry.inspect_entry(carrier)
        stage = 'single-bit-controls'
        bits = bit_controls(carrier)
        stage = 'proof-intermediate-controls'
        controls = proof_controls(carrier)
        stage = 'input-recheck'
        assert all(digest(ROOT / name) == expected for name,expected in inputs.items())
    except Exception as error:
        preserved = {}
        for source in (Path(__file__),Path(entry.__file__)):
            target = output / ('failed-'+source.name)
            shutil.copy2(source,target)
            target.chmod(stat.S_IMODE(target.stat().st_mode)&~0o222)
            preserved[str(source.relative_to(ROOT))] = dict(path=str(target.relative_to(ROOT)),sha256=digest(target))
        with (output / 'failure.json').open('x') as stream:
            stream.write(json.dumps(dict(passed=False,stage=stage,error=str(error),traceback=traceback.format_exc(),
                inputs=inputs,exact_failed_sources=preserved,hardware=False),indent=2)+'\n')
        raise
    record = dict(passed=True,scope='conditional-original-computed-code-entry-and-zero-local-SP-only',
        proof=proof,single_bit_controls=bits,proof_intermediate_controls=controls,inputs=inputs,
        carrier_sha256=hashlib.sha256(carrier).hexdigest(),compiled_public_function_exactly_equal=True,
        Ghidra_ranges_unchanged_and_gap_separately_decoded=True,capstone_version=capstone.__version__,
        Z3_version=z3.get_full_version(),strict_default_checker_changed=False,
        actual_firmware_executed_by_this_audit=False,newlib_vendor_build_date_or_toolchain_proved=False,
        NPU_global_graph_requalified=False,ECALL_contract_qualified=False,
        native_constructor_budgets_or_checkpoints_changed=False,hardware=False)
    target = output / 'result.json'
    with target.open('x') as stream:
        stream.write(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(passed=True,single_bit_controls=bits['total'],proof_controls=len(controls),
        local_SP_bytes=proof['local_SP_bytes'],sha256=digest(target))),flush=True)


if __name__ == '__main__':
    main()
