#!/usr/bin/env python3
"""Execute selected actual NAPI controls/polls with explicit pthread models."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess

import test_rro_reset_ba_events as ba

ROOT = ba.ROOT
HERE = Path(__file__).resolve().parent


def selected_function(text, name):
    match = re.search(r'(?m)^(?:static\s+)?(?:struct napi_struct\s*\*|int|void|bool)\s*\n?' +
        re.escape(name) + r'\([^;{]*?\)\s*\{', text)
    assert match, name
    return ba.braced(text, match.start(), False)


def run(destination, source, thread_sanitizer):
    paths = {name: source / name for name in ('mt76.h', 'mac80211.c', 'dma.c', 'npu.c',
        'mt7996/dma.c', 'mt7996/mac.c', 'mt7996/init.c', 'mt7996/pci.c', 'mt7996/mmio.c')}
    harness = HERE / 'napi-lifetime-harness.c'
    inputs = {str(path.resolve()): ba.sha(path) for path in [*paths.values(), harness,
        Path(__file__), Path(ba.__file__)]}
    texts = {name: path.read_text() for name, path in paths.items()}
    header = texts['mt76.h']
    enum_at = header.index('enum mt76_rxq_id {')
    types = ba.braced(header, enum_at, True) + '\n'
    types += '\n'.join(ba.macro(header, name) for name in
        ('MT76_NAPI_TX', 'MT76_NAPI_MAX', 'MT_DRV_NAPI_LIFETIME', 'mt76_for_each_q_rx'))
    types += '\n' + ba.structure(header, 'mt76_napi_lifetime')
    controls = '\n\n'.join(selected_function(texts['mac80211.c'], name) for name in
        ('mt76_napi_get', 'mt76_napi_add', 'mt76_napi_enable', 'mt76_napi_disable', 'mt76_napi_cleanup'))
    selected = {'selected-types.inc': types, 'selected-control.inc': controls,
        'selected-rx-poll.inc': selected_function(texts['dma.c'], 'mt76_dma_rx_poll'),
        'selected-npu-poll.inc': selected_function(texts['npu.c'], 'mt76_npu_rx_poll'),
        'selected-tx-poll.inc': selected_function(texts['mt7996/dma.c'], 'mt7996_poll_tx')}
    for symbol, name in (('mt7996_mac_restart', 'selected-restart-enable.inc'),
        ('mt7996_mac_reset_work', 'selected-L1-enable.inc')):
        body = selected_function(texts['mt7996/mac.c'], symbol)
        loops = [ba.braced(body, match.start(), False) for match in re.finditer(
            r'(?m)^\tmt76_for_each_q_rx\([^\n]+\)\s*\{', body)]
        loops = [loop for loop in loops if 'mt76_napi_enable' in loop]
        assert len(loops) == 1, symbol
        selected[name] = loops[0]
    caller_checks = {}
    for filename, symbol, calls in (
        ('mt7996/init.c', 'mt7996_cleanup_device', ('mt7996_mcu_exit(dev);',
            'mt7996_pci_shutdown_irqs(dev);', 'mt76_npu_shutdown_irqs(&dev->mt76);',
            'mt76_napi_cleanup(&dev->mt76);', 'mt7996_tx_token_put(dev);', 'mt7996_dma_cleanup(dev);')),
        ('mac80211.c', 'mt76_free_device', ('mt76_npu_shutdown_irqs(dev);',
            'mt76_napi_cleanup(dev);', 'mt76_npu_deinit(dev);', 'ieee80211_free_hw(dev->hw);')),
        ('npu.c', 'mt76_npu_deinit', ('mt76_npu_shutdown_irqs(dev);', 'mt76_napi_cleanup(dev);',
            'npu = rcu_replace_pointer', 'mt76_npu_queue_cleanup(dev,'))):
        body = selected_function(texts[filename], symbol)
        offsets = [body.index(call) for call in calls]
        assert offsets == sorted(offsets), (symbol, offsets)
        caller_checks[symbol] = dict(source=filename, ordered_calls=calls,
            offsets=offsets, body_sha256=hashlib.sha256(body.encode()).hexdigest(), executed=False)
    for filename, symbol, calls in (
        ('mt7996/init.c', 'mt7996_unregister_device', ('mt7996_cleanup_device(dev);',
            'mt76_free_device(&dev->mt76);')),
        ('mt7996/pci.c', 'mt7996_pci_probe', ('free_device:', 'mt7996_cleanup_device(dev);',
            'mt76_free_device(&dev->mt76);'))):
        body = selected_function(texts[filename], symbol)
        offsets = [body.index(call) for call in calls]
        assert offsets == sorted(offsets), (symbol, offsets)
        caller_checks[symbol] = dict(source=filename, ordered_calls=calls, offsets=offsets,
            body_sha256=hashlib.sha256(body.encode()).hexdigest(), executed=False)
    assert 'MT_DRV_NAPI_LIFETIME' in texts['mt7996/mmio.c']
    for symbol in ('mt7996_mac_restart', 'mt7996_mac_reset_work'):
        body = selected_function(texts['mt7996/mac.c'], symbol)
        assert not re.search(r'(?<![\w])napi_(?:disable|enable)\(', body)
        end = body.index('synchronize_rcu();')
        assert 'mt76_napi_disable' in body[:end]
        if symbol == 'mt7996_mac_restart':
            assert end < body.index('mt7996_tx_token_put(dev);')
        caller_checks[symbol] = dict(full_registered_slot_sweep=True,
            explicit_tail_grace_period=True, body_sha256=hashlib.sha256(body.encode()).hexdigest(), executed=False)
    compiler = shutil.which('clang') or shutil.which('gcc')
    assert compiler
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1', TSAN_OPTIONS='halt_on_error=1')

    def variant(folder, mutation=None, mode='all', tsan=False):
        folder.mkdir(parents=True, exist_ok=False)
        for name, value in selected.items():
            if mutation and name == mutation[0]:
                value = ba.once(value, mutation[1], mutation[2], folder.name)
            (folder / name).write_text(value + '\n')
        shutil.copyfile(harness, folder / harness.name)
        binary = folder / 'napi-lifetime'
        command = [(shutil.which('gcc') or compiler) if tsan else compiler,
            '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
            '-Wno-sign-compare', '-pthread', '-fno-omit-frame-pointer', '-fno-sanitize-recover=all',
            '-fsanitize=thread' if tsan else '-fsanitize=address,undefined',
            str(folder / harness.name), '-o', str(binary)]
        built = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (folder / 'compile.log').write_text(built.stdout + built.stderr)
        assert built.returncode == 0, ('compile', folder.name, built.stderr)
        executed = subprocess.run([str(binary), mode], cwd=folder, env=environment,
            capture_output=True, text=True, timeout=120, preexec_fn=ba.no_core_dump)
        (folder / 'run.stdout').write_text(executed.stdout)
        (folder / 'run.stderr').write_text(executed.stderr)
        return command, binary, executed

    command, binary, executed = variant(destination)
    assert executed.returncode == 0, ('NAPI lifetime', executed.returncode, executed.stderr)
    row = json.loads(executed.stdout)
    assert row['passed'] and not row['kernel_concurrency'] and not row['physical_drain'] and not row['hardware']
    mutations = (
        ('missing-tail-grace-period', 'selected-control.inc', '\t\tsynchronize_rcu();\n', '\t\tif (false) synchronize_rcu();\n',
            'rx-tail', 'poll-tail-must-finish-before-NAPI-delete'),
        ('RX-tail-outside-RCU', 'selected-rx-poll.inc',
            '\tif (done < budget && napi_complete(napi))\n\t\tdev->drv->rx_poll_complete(dev, qid);\nout:\n\trcu_read_unlock();',
            '\trcu_read_unlock();\n\tif (done < budget && napi_complete(napi))\n\t\tdev->drv->rx_poll_complete(dev, qid);\nout:\n\t;',
            'rx-tail', 'completion-and-rearm-tail-must-share-RCU'),
        ('NPU-tail-outside-RCU', 'selected-npu-poll.inc',
            '\tif (done < budget && napi_complete(napi))\n\t\tdev->drv->rx_poll_complete(dev, qid);\n\nunlock:\n\trcu_read_unlock();',
            '\trcu_read_unlock();\n\tif (done < budget && napi_complete(napi))\n\t\tdev->drv->rx_poll_complete(dev, qid);\n\nunlock:\n\t;',
            'npu-tail', 'completion-and-rearm-tail-must-share-RCU'),
        ('missing-TX-RCU', 'selected-tx-poll.inc', '\trcu_read_lock();\n', '',
            'tx-tail', 'TX-cleanup-within-RCU'),
        ('TX-zero-budget-completion', 'selected-tx-poll.inc', 'if (budget && napi_complete_done(napi, 0))',
            'if (napi_complete_done(napi, 0))', 'budgets', 'zero-budget-no-completion-or-RX-APIs'),
        ('RX-zero-budget-processing', 'selected-rx-poll.inc', '\tif (!budget)\n\t\tgoto out;\n', '\tif (false) goto out;\n',
            'budgets', 'zero-budget-must-not-run-RX-page-pool-APIs'),
        ('NPU-zero-budget-fill', 'selected-npu-poll.inc', '\tif (!budget)\n\t\tgoto unlock;\n', '\tif (false) goto unlock;\n',
            'budgets', 'zero-budget-no-completion-or-RX-APIs'),
        ('double-disable-after-recovery', 'selected-control.inc', 'if (test_bit(qid, state->enabled))',
            'if (test_bit(qid, state->added))', 'serial', 'disable-only-enabled-NAPI-once'),
        ('disable-added-not-enabled-at-cleanup', 'selected-control.inc',
            'for_each_set_bit(qid, state->enabled, MT76_NAPI_MAX)',
            'for_each_set_bit(qid, state->added, MT76_NAPI_MAX)', 'serial', 'disable-only-enabled-NAPI-once'),
        ('missing-permanent-close', 'selected-control.inc', '\tstate->closing = true;\n', '',
            'serial', 'permanent-close-denies-new-registration'),
        ('missing-registration-ownership', 'selected-control.inc', '\t\tset_bit(qid, state->added);\n', '\t\t(void)0;\n',
            'serial', 'partial-prefix-deletes-only-added-instances'),
        ('registered-but-unallocated-RX-scheduled', 'selected-types.inc', 'if ((dev)->q_rx[i].ndesc)',
            'if (true)', 'readiness', 'reset-must-not-schedule-unallocated-RX'))
    measured = []
    for name, target, old, replacement, mode, assertion in mutations:
        child_command, child_binary, rejected = variant(destination / name,
            (target, old, replacement), mode)
        assert rejected.returncode == -signal.SIGABRT and assertion in rejected.stderr, (
            'control missed intended assertion', name, rejected.returncode, rejected.stderr)
        assert 'AddressSanitizer' not in rejected.stderr and 'runtime error:' not in rejected.stderr
        measured.append(dict(name=name, compiled=True, intended_assertion=assertion,
            mode=mode, returncode=rejected.returncode, compile_command=child_command,
            binary_sha256=ba.sha(child_binary)))
    tsan = dict(requested=thread_sanitizer, passed=False)
    if thread_sanitizer:
        tsan_command, tsan_binary, checked = variant(destination / 'thread-sanitizer', tsan=True)
        unavailable = 'FATAL: ThreadSanitizer: unexpected memory mapping' in checked.stderr
        assert checked.returncode == 0 or unavailable, ('TSan', checked.returncode, checked.stderr)
        if checked.returncode == 0:
            assert json.loads(checked.stdout) == row
        tsan.update(passed=checked.returncode == 0, runtime_unavailable=unavailable,
            returncode=checked.returncode, compile_command=tsan_command, binary_sha256=ba.sha(tsan_binary))
    assert all(ba.sha(Path(name)) == digest for name, digest in inputs.items()), 'input drift'
    return dict(passed=True, cases=row['cases'], inputs_sha256=inputs,
        selected_sha256={name: hashlib.sha256(value.encode()).hexdigest() for name, value in selected.items()},
        artifacts_sha256={str(path.relative_to(destination)): ba.sha(path)
            for path in sorted(destination.rglob('*')) if path.is_file()},
        compile_command=command, binary_sha256=ba.sha(binary), mutation_controls=measured,
        sanitizers=['ASan', 'UBSan', 'leak-detection'], thread_sanitizer=tsan,
        actual_selected_NAPI_controls_RX_NPU_TX_poll_C=True, actual_selected_reset_RX_enable_loops=True,
        outer_source_checks=caller_checks,
        modeled_boundaries=['pthread NAPI control/ownership/RCU semantics, not Linux scheduler behavior',
            'RX/TX/page-pool/provider/IRQ processing side effects', 'dummy netdev allocations',
            'outer caller checks bind source order but do not execute the whole teardown/reset'],
        kernel_concurrency=False, full_cold_prefix_unwind=False,
        physical_drain=False, hardware=False, firmware_reuse_fence=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--thread-sanitizer', action='store_true')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    destination = ROOT / '.local/npu-napi-lifetime-fixture-20261024' / args.name
    assert not destination.exists()
    try:
        result = run(destination, args.source_root.resolve(), args.thread_sanitizer)
    except BaseException as error:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'failure.json').write_text(json.dumps(dict(passed=False,
            error_type=type(error).__name__, error=str(error)), indent=2) + '\n')
        raise
    with (destination / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, cases=result['cases'], controls=len(result['mutation_controls']),
        thread_sanitizer=result['thread_sanitizer'], receipt=str(destination / 'result.json'),
        sha256=ba.sha(destination / 'result.json'))), flush=True)


if __name__ == '__main__':
    main()
