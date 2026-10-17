#!/usr/bin/env python3
"""Compose a fresh restricted graph from prior C frames and exact callee proofs."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re

from npu_stack_usage import ROOT,digest
from test_npu_direct_stack import candidates


def code_identity(graph,native,export):
    hashes = {value for name,value in graph['inputs'].items() if Path(name).name == 'CODE.bin'}
    assert len(hashes) == 1, 'ambiguous-or-missing-graph-CODE'
    value = next(iter(hashes))
    assert type(value) is str and re.fullmatch('[0-9a-f]{64}',value), 'invalid-CODE-identity'
    assert native['paired_CODE_sha256'] == value == export['mapped_CODE_sha256'], 'mixed-CODE-proof-cohorts'
    return value


def validate_functions(functions):
    assert isinstance(functions,dict) and functions
    extents = []
    for address,row in functions.items():
        assert type(address) is int and address == row['address'] and address >= 0
        assert type(row['bytes']) is int and row['bytes'] > 0
        assert type(row['frame']) is int and row['frame'] >= 0 and row['frame'] % 16 == 0
        assert isinstance(row['name'],str) and row['name']
        assert isinstance(row['transfers'],list)
        extents.append((address,address+row['bytes']))
        sites = set()
        for edge in row['transfers']:
            assert type(edge['address']) is int and address <= edge['address'] < address+row['bytes']
            assert edge['address'] not in sites
            sites.add(edge['address'])
            assert edge['target'] is None or type(edge['target']) is int
            assert type(edge['caller_CFA']) is int and 0 <= edge['caller_CFA'] <= row['frame']
            assert edge['caller_CFA'] % 16 == 0
    extents.sort()
    assert all(left[1] <= right[0] for left,right in zip(extents,extents[1:])), 'overlapping-function-extents'


def integrate(functions,sites,additions):
    validate_functions(functions)
    assert isinstance(additions,dict) and additions and not set(functions).intersection(additions)
    validate_functions(additions)
    combined = deepcopy(functions)
    combined.update(deepcopy(additions))
    validate_functions(combined)
    for row in additions.values():
        assert all(edge['target'] in combined for edge in row['transfers']), 'unresolved-added-callee'
    assert isinstance(sites,list) and sites
    used = set()
    for site in sites:
        assert site['control_flow_qualified'] is True
        caller,address = site['caller'],site['address']
        assert type(caller) is type(address) is int
        assert (caller,address) not in used, 'duplicate-qualified-site'
        used.add((caller,address))
        assert caller in functions and site['caller_name'] == functions[caller]['name']
        assert type(site['target']) is int and site['target'] in combined, 'target-frame-not-proved'
        assert site['kind'] in ('literal-register-call','literal-register-tail')
        matches = [edge for edge in combined[caller]['transfers'] if edge['address'] == address]
        assert len(matches) == 1 and matches[0]['target'] is None, 'not-a-prior-unknown-site'
        edge = matches[0]
        assert edge['kind'].startswith('unresolved-register-')
        assert type(site['caller_CFA']) is int and site['caller_CFA'] == edge['caller_CFA'], 'callsite-CFA-drift'
        edge.update(target=site['target'],kind=site['kind'],prior_unknown_kind=edge['kind'])
    chains,cycles = candidates(combined)
    ranked = sorted((dict(root=address,**row) for address,row in chains.items() if row is not None),
                    key=lambda row:(-row['bytes'],row['root']))
    unresolved = [dict(caller=address,**edge) for address,row in combined.items()
                  for edge in row['transfers'] if edge['target'] not in combined]
    resolved = sum(edge['target'] in combined for row in combined.values() for edge in row['transfers'])
    return dict(functions=combined,qualified_literal_sites=len(used),resolved_transfers=resolved,
                unresolved_transfers=unresolved,cycles=cycles,ranked_subset_candidates=ranked)


def read_record(path):
    path = path.resolve()
    assert path.is_relative_to(ROOT / '.local') and path.is_file()
    record = json.loads(path.read_bytes())
    assert record['passed'] is True and record['inputs']
    for name,expected in record['inputs'].items():
        source = (ROOT / name).resolve()
        assert source.is_relative_to(ROOT) and source.is_file() and digest(source) == expected, name
    return record


def audit(graph_path,literals_path,originals_path,export_path,native_path):
    graph,literals,originals,native = [read_record(path) for path in
        (graph_path,literals_path,originals_path,native_path)]
    export = json.loads(export_path.read_bytes())
    assert export['passed'] is True
    common_CODE = code_identity(graph,native,export)
    assert originals['inputs'][str(export_path.relative_to(ROOT))] == digest(export_path)
    assert originals['inputs'][str(native_path.relative_to(ROOT))] == digest(native_path)
    assert literals['original_graph_sha256'] == digest(graph_path)
    assert originals['all_branches_checked'] is originals['all_returns_SP_balanced'] is True
    assert originals['complete_C_graph_extended'] is originals['complete_permitted_path_bound'] is False
    assert native['hart_ids_executed'] == [0] and native['hardware'] is native['full_setup'] is False
    assert graph['complete_call_chain_bound_proven'] is literals['graph_extended'] is False
    functions = {row['address']:row for row in graph['functions']}
    assert len(functions) == len(graph['functions']) == graph['CFI_compiler_frames_matched']
    selected = [row for row in literals['sequences'] if row['control_flow_qualified'] is True]
    assert len(selected) == literals['control_flow_qualified_literal_sites']
    static = {int(row['entry'],16):row for row in originals['functions']}
    expected = {0x84004212:0,0x840064b4:16,0x8400651c:16}
    assert set(static) == set(expected) and len(export['functions']) == 3
    additions = {}
    for row in export['functions']:
        address = int(row['entry'],16)
        assert address in expected and address not in additions
        proof = static[address]
        assert proof['local_max_stack_bytes'] == expected[address]
        assert row['body_bytes'] == proof['body_bytes']
        calls = []
        for edge in proof['direct_calls']:
            pc,target = int(edge['address'],16),int(edge['target'],16)
            matches = [item for item in row['instructions'] if int(item['address'],16) == pc]
            assert len(matches) == 1 and matches[0]['direct_flows'] == [hex(target)]
            assert 'CALL' in matches[0]['flow_type']
            assert proof['entry_SP_deltas'][hex(pc)] == -edge['caller_CFA']
            calls.append(dict(address=pc,target=target,caller_CFA=edge['caller_CFA'],kind='original-body-direct-call'))
        additions[address] = dict(component='original-reviewed-body',name=row['analyst_seeded_name'],
            address=address,bytes=row['body_bytes'],frame=proof['local_max_stack_bytes'],
            instructions=proof['instructions'],transfers=calls,name_provenance='analyst-seeded-address')
    result = integrate(functions,selected,additions)
    assert result['qualified_literal_sites'] == len(selected)
    assert len(result['unresolved_transfers']) == len(graph['unresolved_transfers'])-len(selected)
    assert result['resolved_transfers'] == graph['resolved_direct_transfers']+len(selected)+sum(
        len(row['transfers']) for row in additions.values())
    inputs = {}
    for record in (graph,literals,originals,native):
        for name,expected_sha in record['inputs'].items():
            assert name not in inputs or inputs[name] == expected_sha, ('proof-cohort-conflict',name)
            inputs[name] = expected_sha
    for path in (graph_path,literals_path,originals_path,export_path,native_path,Path(__file__),
                 ROOT / 'tests/npu/test_npu_resolved_stack_subset_contract.py'):
        inputs[str(path.relative_to(ROOT))] = digest(path)
    for name,expected_sha in inputs.items():
        assert digest(ROOT / name) == expected_sha
    result['functions'] = list(result['functions'].values())
    result.update(passed=True,prior_measured_C_functions=len(functions),added_original_body_functions=len(additions),
        prior_resolved_direct_edges=graph['resolved_direct_transfers'],new_literal_register_edges=len(selected),
        added_original_direct_edges=sum(len(row['transfers']) for row in additions.values()),
        prior_graph_sha256=digest(graph_path),prior_graph_rewritten=False,CODE_identity_sha256=common_CODE,
        prior_unresolved_count=len(graph['unresolved_transfers']),
        complete_call_chain_bound_proven=False,all_frames_CFI_proved=False,
        original_diagnostic_harts=[0],original_diagnostic_cases=native['original_routine_executions'],
        current_main_native_qualified=False,full_setup=False,hardware=False,inputs=inputs,
        limits=['A new restricted static view composes existing CFI C frames with three exact original-body SP proofs.',
            'Literal register edges remain syntactically indirect;resolved total must not be called all-direct or all-CFI.',
            'Unresolved edges are retained;cycles do not receive finite candidates. No complete permitted-path bound follows.',
            'Exact function entry/ordinary call-return/no IRQ or external stack mutation remain assumptions.',
            'Original runtime comparisons cover hart0 on synthetic RAM/MMIO,not other harts,full cold or physical ownership.',
            'The prior graph is unchanged;this does not qualify newer host integration,full NPU setup,physical stacks or clients.'])
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ('graph','literals','originals','export','native'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--name',required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    paths = [getattr(args,name).resolve() for name in ('graph','literals','originals','export','native')]
    assert all(path.is_relative_to(ROOT / '.local') for path in paths)
    result = audit(*paths)
    output = ROOT / '.local/npu-resolved-stack-subset' / args.name / 'result.json'
    output.parent.mkdir(parents=True,exist_ok=False)
    with output.open('x') as stream:
        stream.write(json.dumps(result,indent=2) + '\n')
    print(json.dumps(dict(passed=True,functions=len(result['functions']),resolved_edges=result['resolved_transfers'],
        unresolved_edges=len(result['unresolved_transfers']),cycles=len(result['cycles']),
        largest_subset_candidate=result['ranked_subset_candidates'][0]['bytes'] if result['ranked_subset_candidates'] else None,
        complete_bound=False,sha256=digest(output))),flush=True)


if __name__ == '__main__':
    main()
