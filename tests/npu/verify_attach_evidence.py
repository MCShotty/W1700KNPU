#!/usr/bin/env python3
"""Bind separate native TX consumer receipts to current inputs, not readiness."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
from test_bootstrap_native import ROOT, sha
from test_mt7996_bootstrap_sequence import exports

OUT = ROOT/'research/checkpoints/2026-09-06-npu-attachtx'
BUF = ROOT/'research/checkpoints/2026-09-06-npu-attachtxbuf'
BASE = 'd41ac7ba1987f2d47a5e95146f8127cd7f7d49e4'


def main():
    tx = json.loads((OUT/'tx-callbacks.json').read_text())
    buf = json.loads((BUF/'txbuf-callbacks.json').read_text())
    rx = json.loads((ROOT/'research/checkpoints/2026-09-06-npu-attachrx/rx-callbacks.json').read_text())
    functions = exports()
    sources = {}
    for receipt in (tx, buf, rx):
        for name, value in receipt['sources'].items():
            path = (ROOT/name).resolve()
            assert path.is_relative_to(ROOT) and sha(path) == value, name
            assert name not in sources or sources[name] == value
            sources[name] = value
        for address, row in receipt['ghidra_functions'].items():
            function = functions[int(address, 16)]
            assert row['name'] == function['name'] and row['line'] == function['line']
            assert row['export_sha256'] == hashlib.sha256((function['text']+function['assembly']).encode()).hexdigest()
    assert tx['base_commit'] == buf['base_commit'] == BASE
    assert tx['counts'] == dict(new_original_pending_closures=3, valid_callbacks=13,
                               negative_controls=38, strict_denials=3)
    assert len(tx['valid_callbacks']) == 12 and len(tx['valid_txdone']) == 1
    assert len(tx['negative_controls']) == 22 and len(tx['txdone_controls']) == 16
    for row in tx['valid_callbacks']+tx['valid_txdone']:
        assert row['callback_return'] == row['mailbox_flags_untouched'] == 1
        assert row['stopped_access'] is None and row['exact_memory_and_register_write_footprints']
    done = tx['valid_txdone'][0]
    assert done['ready_flag'] == 1 and done['whole_ram_compared_bytes'] == 856064
    assert done['footprint']['allocated'] == 512 and done['footprint']['ids_first_last'] == [2560, 3071]
    assert done['footprint']['skb_reset']['capacity'] == 8192
    assert done['footprint']['skb_reset']['unconditional_temporary_read_bytes'] == 16384
    assert buf['passed'] and buf['counts']['native_callback_selectors_closed'] == 4
    assert len(buf['valid_sequence']) == 4 and len(buf['negative_controls']) == 35
    assert buf['counts']['separately_allocator_modeled_cases_remaining'] == 0
    assert [(row['selector'], row['callback_return']) for row in buf['valid_sequence']] == [(5, 1), (10, 1), (7, 1), (12, 1)]
    assert sum(row['footprint']['entries'] for row in buf['valid_sequence'][:1]+buf['valid_sequence'][2:3]) == 1536
    for row in buf['valid_sequence']:
        assert row['whole_ram_compared_bytes'] == 1048576 and row['stopped_access'] is None
        assert row['exact_ordered_ram_writes'] and row['exact_nonstack_read_footprint_and_values']
        assert not row['dedicated_ready_flag_written']
    denials = tx['strict_replies']+[tx['strict_txdone']]+buf['strict_bootstrap']['replies']
    assert len(denials) == 7 and all(row['flags'] == 3 and not row['callbacks'] for row in denials)
    assert not buf['strict_bootstrap']['api21_admitted']
    previous = set(rx['remaining_original_pending_cases'])
    assert len(previous) == 11
    closed_tx = {'api19_if0_native_entry_only', 'api19_if2_native_entry_only', 'api1_if10_native_entry_only'}
    closed_buf = {f'txbuf_if{i}_txpkt_{value:x}_wait_boundary' for i in (10, 12) for value in (0, 0x8a000000)}
    assert closed_tx | closed_buf <= previous and not closed_tx & closed_buf
    remaining = sorted(previous-closed_tx-closed_buf)
    assert remaining == [f'api1_if{i}_native_entry_only' for i in (5, 6, 7, 8)]
    assert set(buf['remaining_original_pending_cases'])-closed_tx == set(remaining)
    protected = ['firmware', 'tests/npu/test_attach_rx_callbacks.py',
                 'tests/npu/test_native_wifi_boot.py', 'tests/npu/test_mt7996_bootstrap_sequence.py',
                 'tests/npu/admission-platform-emulation.c', 'tests/npu/bootstrap-platform-emulation.c']
    subprocess.run(['git', 'diff', '--quiet', BASE, '--', *protected], cwd=ROOT, check=True)
    assert not subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', *protected], cwd=ROOT)
    for name in (OUT/'TX_CALLBACKS.md', BUF/'TXBUF_CALLBACKS.md', OUT/'REVIEW.md'):
        assert name.is_file(), str(name)
    review = (OUT/'REVIEW.md').read_text()
    assert 'No actionable findings' in review
    for path in (OUT/'TX_CALLBACKS.md', OUT/'tx-callbacks.json', BUF/'TXBUF_CALLBACKS.md',
                 BUF/'txbuf-callbacks.json', ROOT/'tests/npu/test_attach_tx_callbacks.py',
                 ROOT/'tests/npu/test_attach_txbuf_callbacks.py'):
        assert sha(path) in review, f'review binding differs: {path}'
    result = dict(passed=True, base_commit=BASE, unique_source_bindings=len(sources),
        native_callback_selectors_closed=7, valid_calls=17, negative_controls=73, strict_denials=7,
        remaining_original_pending_cases=remaining, allocator_substitutions_remaining=0,
        blocked_lane_retried=False, firmware_and_helpers_unchanged=True,
        complete_host_attachment=False, post_gate_workers=False, physical_quiescence=False,
        hardware_or_client_acceptance=False, verifier_sha256=sha(Path(__file__)))
    files = [path for directory in (OUT, BUF) for path in sorted(directory.iterdir())
             if path.is_file() and path.name not in ('file-manifest.json', 'evidence-verification.json')]
    files += [ROOT/'tests/npu'/name for name in ('test_attach_tx_callbacks.py',
              'test_attach_txbuf_callbacks.py', 'verify_attach_evidence.py')]
    (OUT/'file-manifest.json').write_text(json.dumps({str(path.relative_to(ROOT)): sha(path)
                                                   for path in files}, indent=2)+'\n')
    (OUT/'evidence-verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
