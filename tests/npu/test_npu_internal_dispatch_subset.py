#!/usr/bin/env python3
"""Remove only proved internal dispatches from a fresh restricted stack view."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re

from npu_stack_usage import ROOT, digest
from test_npu_direct_stack import candidates
from test_npu_resolved_stack_subset import read_record, validate_functions


def integrate(functions, sites):
    validate_functions(functions)
    assert isinstance(sites,list) and sites
    combined = deepcopy(functions)
    used = set()
    for site in sites:
        assert site['control_flow_qualified'] is site['same_function_only'] is True
        assert site['guard_safe_edge_dominates_load_and_jump'] is site['target_CFA_matches_dispatch'] is True
        assert site['interfunction_edge'] is False
        caller,pc = site['caller'],site['address']
        assert type(caller) is type(pc) is int and caller in combined
        assert (caller,pc) not in used, 'duplicate-internal-dispatch'
        used.add((caller,pc))
        function = combined[caller]
        assert site['caller_name'] == function['name'] and site['component'] == function['component']
        assert type(site['entry_count']) is int and site['entry_count'] > 0
        assert isinstance(site['table_targets'],list) and len(site['table_targets']) == site['entry_count']
        for target in [*site['table_targets'],site['default_target']]:
            assert type(target) is int and target % 2 == 0 and caller < target < caller+function['bytes'], 'noninternal-target'
        matches = [edge for edge in function['transfers'] if edge['address'] == pc]
        assert len(matches) == 1 and matches[0]['target'] is None, 'not-a-prior-unknown'
        edge = matches[0]
        assert edge['kind'].startswith('unresolved-register-')
        assert type(site['caller_CFA']) is int and site['caller_CFA'] == edge['caller_CFA'], 'dispatch-CFA-drift'
        function['transfers'].remove(edge)
        function.setdefault('internal_dispatches',[]).append(deepcopy(site))
    chains,cycles = candidates(combined)
    ranked = sorted((dict(root=address,**row) for address,row in chains.items() if row is not None),
                    key=lambda row:(-row['bytes'],row['root']))
    unresolved = [dict(caller=address,**edge) for address,row in combined.items()
                  for edge in row['transfers'] if edge['target'] not in combined]
    resolved = sum(edge['target'] in combined for row in combined.values() for edge in row['transfers'])
    return dict(functions=combined,qualified_internal_dispatches=len(used),resolved_transfers=resolved,
                unresolved_transfers=unresolved,cycles=cycles,ranked_subset_candidates=ranked)


def audit(graph_path,switches_path,native_path):
    graph,switches,native = [read_record(path) for path in (graph_path,switches_path,native_path)]
    assert switches['prior_graph_sha256'] == digest(graph_path)
    assert graph['CODE_identity_sha256'] == switches['CODE_identity_sha256'] == native['paired_CODE_sha256']
    assert native['inputs'][str(switches_path.relative_to(ROOT))] == digest(switches_path)
    assert graph['complete_call_chain_bound_proven'] is switches['graph_extended'] is False
    assert native['cold_caller_qualified'] is native['full_setup'] is native['hardware'] is False
    assert native['post_start_host_register_and_memory_writes_forbidden'] is True
    selected = switches['tables']
    assert len(selected) == switches['qualified_internal_dispatches']
    assert native['dispatches'] == len(selected)
    assert native['compiled_prefix_executions'] == sum(row['entry_count']+3 for row in selected)
    records = native['records']
    assert len(records) == native['compiled_prefix_executions']
    for site in selected:
        cases = [row for row in records if int(row['dispatch'],16) == site['address']]
        assert [row['index'] for row in cases] == [*range(site['entry_count']),site['entry_count'],0x80000000,0xffffffff]
        assert all(row['observed_before_any_context_restore'] is row['protected_CODE_and_stack_unchanged'] is
                   row['stopped_before_case_or_default_body'] is True for row in cases)
    functions = {row['address']:row for row in graph['functions']}
    assert len(functions) == len(graph['functions'])
    result = integrate(functions,selected)
    assert result['resolved_transfers'] == graph['resolved_transfers'], 'invented-interfunction-edge'
    assert result['ranked_subset_candidates'] == graph['ranked_subset_candidates'] and result['cycles'] == graph['cycles']
    keys = {(row['caller'],row['address']) for row in selected}
    expected = [row for row in graph['unresolved_transfers'] if (row['caller'],row['address']) not in keys]
    assert result['unresolved_transfers'] == expected
    assert len(expected) == len(graph['unresolved_transfers'])-len(selected)
    inputs = {}
    for record in (graph,switches,native):
        for name,expected_sha in record['inputs'].items():
            assert name not in inputs or inputs[name] == expected_sha, 'mixed-input-cohorts'
            inputs[name] = expected_sha
    for path in (graph_path,switches_path,native_path,Path(__file__),
                 ROOT / 'tests/npu/test_npu_internal_dispatch_subset_contract.py'):
        inputs[str(path.relative_to(ROOT))] = digest(path)
    for name,expected_sha in inputs.items():
        assert digest(ROOT / name) == expected_sha
    result['functions'] = list(result['functions'].values())
    result.update(passed=True,prior_graph_sha256=digest(graph_path),prior_graph_rewritten=False,
        CODE_identity_sha256=graph['CODE_identity_sha256'],interfunction_edges_added=0,
        remaining_register_unknown=sum(row['target'] is None for row in expected),
        remaining_known_outside_subset=sum(row['target'] is not None for row in expected),
        compiled_prefix_diagnostics=native['compiled_prefix_executions'],all_frames_CFI_proved=False,
        complete_call_chain_bound_proven=False,current_main_native_qualified=False,full_setup=False,
        hardware=False,inputs=inputs,limits=[
            'Four internal jumps are classified separately,not as new calls,self-recursion or zero-frame callees.',
            'Restricted inter-function edge/frame/candidate counts remain unchanged;all other unknowns remain recorded.',
            'Exact function entry,ordinary ABI,no asynchronous IRQ/external mutation and immutable tables remain assumptions.',
            'Prefix diagnostics begin from synthetic CPU contexts and stop before case/default bodies,not constructors.',
            'No complete permitted-path,IRQ,per-hart,physical stack,current-main cold or client qualification follows.'])
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ('graph','switches','native'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--name',required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    paths = [getattr(args,name).resolve() for name in ('graph','switches','native')]
    assert all(path.is_relative_to(ROOT / '.local') for path in paths)
    result = audit(*paths)
    output = ROOT / '.local/npu-internal-dispatch-subset' / args.name / 'result.json'
    output.parent.mkdir(parents=True,exist_ok=False)
    with output.open('x') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,functions=len(result['functions']),resolved_edges=result['resolved_transfers'],
        internal_dispatches=result['qualified_internal_dispatches'],unresolved=len(result['unresolved_transfers']),
        register_unknown=result['remaining_register_unknown'],sha256=digest(output))),flush=True)


if __name__ == '__main__':
    main()
