#!/usr/bin/env python3
"""Actual selected BA/owner C; pthread models of work cancellation and RCU."""
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
from test_host_queue_publication import function

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def run(destination, source, harness_root, thread_sanitizer=False):
    def paired(name):
        path = source / name
        return path if path.is_file() else ba.BASE_MT76 / name

    paths = {name: paired(name) for name in ('agg-rx.c', 'mt76.h', 'mt7996/main.c',
        'mt7996/mcu.c', 'mt7996/mcu.h', 'mt7996/mt7996.h', 'mt76_connac_mcu.h',
        'mt7996/npu-rro-reset.c', 'mt7996/init.c', 'mt7996/mac.c')}
    names = ('rro-reset-ba-harness.c', 'rro-ba-link-harness.c', 'rro-ba-link-platform.h',
        'rro-ba-owner-harness.c', 'rro-ba-owner-platform.h', 'rro-ba-join-harness.c',
        'rro-ba-join-threading.h')
    files = {name: harness_root / name if (harness_root / name).is_file() else HERE / name
        for name in names}
    inputs = {str(path.resolve()): ba.sha(path) for path in [*paths.values(), *files.values(),
        Path(__file__), Path(ba.__file__), HERE / 'test_host_queue_publication.py']}
    callers = {}
    for filename, name in (('mt7996/init.c', 'mt7996_cleanup_device'),
                           ('mt7996/mac.c', 'mt7996_mac_full_reset'),
                           ('mt7996/mac.c', 'mt7996_mac_reset_work')):
        body = function(paths[filename].read_text(), name)
        cancel = 'disable_work_sync' if name == 'mt7996_cleanup_device' else 'cancel_work_sync'
        calls = ['mt7996_npu_rro_reset_close(dev);', cancel + '(&dev->wed_rro.work);',
                 'mt7996_npu_rro_reset_join(dev);']
        offsets = [body.index(call) for call in calls]
        assert offsets == sorted(offsets), ('close/cancel/join order', name)
        assert 'mutex_lock(&dev->mt76.mutex)' not in body[:offsets[-1]], (
            'join under device mutex', name)
        callers[name] = dict(source=filename, body_sha256=hashlib.sha256(body.encode()).hexdigest(),
            close_cancel_join_offsets=offsets, join_before_device_mutex=True,
            entire_outer_function_executed=False)
    init = paths['mt7996/init.c'].read_text()
    outer = function(init, 'mt7996_unregister_device')
    assert outer.index('mt7996_cleanup_device(dev);') < outer.index('mt76_free_device(&dev->mt76);')
    wire = paths['mt7996/mcu.h'].read_text()
    structs = [ba.structure(wire, name) for name in ('mt7996_mcu_rxd',
        'mt7996_mcu_wed_rro_event', 'mt7996_mcu_wed_rro_ba_event', 'mt7996_mcu_wed_rro_ba_delete_event')]
    structs += [ba.structure(paths['mt76_connac_mcu.h'].read_text(), 'tlv'), ba.event_enum(wire),
        ba.structure(paths['mt7996/mt7996.h'].read_text(), 'mt7996_wed_rro_session_id'),
        ba.macro(paths['mt7996/mt7996.h'].read_text(), 'MT7996_RRO_MAX_SESSION')]
    helper = re.sub(r'(?m)^[ \t]*#include[^\n]*(?:\n|$)', '', paths['mt7996/npu-rro-reset.c'].read_text())
    assert '#include' not in helper
    selected = {'selected-structs.inc': '\n\n'.join(structs) + '\n',
        'selected-rx-tid.inc': ba.structure(paths['mt76.h'].read_text(), 'mt76_rx_tid') + '\n',
        'selected-aggr.inc': '\n\n'.join(function(paths['agg-rx.c'].read_text(), name) for name in
            ('mt76_rx_aggr_shutdown', 'mt76_rx_aggr_stop', 'mt76_rx_aggr_start')) + '\n',
        'selected-main.inc': ba.function(paths['mt7996/main.c'].read_text(), 'mt7996_ampdu_action') + '\n',
        'selected-mcu.inc': ba.function(paths['mt7996/mcu.c'].read_text(), 'mt7996_mcu_wed_rro_event') + '\n',
        'selected-add-rx-ba.inc': function(paths['mt7996/mcu.c'].read_text(), 'mt7996_mcu_add_rx_ba') + '\n',
        'selected-owner.inc': helper}
    compiler = shutil.which('clang') or shutil.which('gcc')
    assert compiler
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1', TSAN_OPTIONS='halt_on_error=1')

    def variant(folder, changes=None, mode='all', tsan=False):
        folder.mkdir(parents=True, exist_ok=False)
        for name, text in selected.items():
            if changes and name == changes[0]:
                text = ba.once(text, changes[1], changes[2], folder.name)
            (folder / name).write_text(text)
        for name, path in files.items():
            shutil.copyfile(path, folder / name)
        binary = folder / 'rro-ba-join'
        chosen = (shutil.which('gcc') or compiler) if tsan else compiler
        command = [chosen, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-pthread',
            '-fsanitize=thread' if tsan else '-fsanitize=address,undefined',
            '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
            str(folder / 'rro-ba-join-harness.c'), '-o', str(binary)]
        built = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (folder / 'compile.log').write_text(built.stdout + built.stderr)
        assert built.returncode == 0, ('compile', folder.name, built.stderr)
        executed = subprocess.run([str(binary), mode], cwd=folder, env=environment,
            capture_output=True, text=True, timeout=120, preexec_fn=ba.no_core_dump)
        (folder / 'run.stdout').write_text(executed.stdout)
        (folder / 'run.stderr').write_text(executed.stderr)
        return command, binary, executed

    command, binary, executed = variant(destination)
    assert executed.returncode == 0, ('BA join fixture', executed.returncode, executed.stderr)
    row = json.loads(executed.stdout)
    assert row == dict(passed=True, cases=37, pthread_framework=True,
        kernel_concurrency=False, physical_retirement=False, hardware=False), row
    mutations = (
        ('missing-status-grace-period', 'selected-owner.inc', '\tsynchronize_rcu();\n', '',
         'status', 'accepted-status-writer-must-finish-before-joined'),
        ('missing-work-cancellation', 'selected-owner.inc', '\tcancel_work_sync(&dev->wed_rro.work);\n', '',
         'worker', 'work-callback-cancellation-must-precede-status-grace-period'),
        ('grace-period-before-work-cancel', 'selected-owner.inc',
         '\tcancel_work_sync(&dev->wed_rro.work);\n\tsynchronize_rcu();',
         '\tsynchronize_rcu();\n\tcancel_work_sync(&dev->wed_rro.work);',
         'worker', 'work-callback-cancellation-must-precede-status-grace-period'),
        ('premature-joined-publication', 'selected-owner.inc',
         '\t/* Keep caller cancellation for legacy WED.',
         '\tspin_lock_bh(&owner->lock);\n\towner->joined = true;\n\tspin_unlock_bh(&owner->lock);\n'
         '\t/* Keep caller cancellation for legacy WED.',
         'status', 'accepted-status-writer-must-finish-before-joined'),
        ('missing-closed-admission-guard', 'selected-owner.inc', '\tif (!owner->closing) {\n',
         '\tif (false) {\n', 'open', 'owned-close-before-process-cancellation'),
        ('inflight-corruption-promoted', 'selected-owner.inc',
         'if (owner->closing && !owner->inflight)', 'if (owner->closing)',
         'inflight', 'corrupt-inflight-state-cannot-be-promoted-to-joined'),
        ('missing-event-RCU', 'selected-mcu.inc', '\t\t\trcu_read_lock();\n', '',
         'status', 'wcid-lookup-without-RCU'),
        ('post-close-status-admitted', 'selected-owner.inc',
         'err = owner->closing ? -ESHUTDOWN : owner->error;', 'err = owner->error;',
         'late', 'post-join-metadata-retention-is-not-new-ID-admission-or-free-authority'))
    controls = []
    for name, target, old, replacement, mode, assertion in mutations:
        child_command, child_binary, rejected = variant(destination / name,
            (target, old, replacement), mode)
        assert rejected.returncode == -signal.SIGABRT and assertion in rejected.stderr, (
            'control missed intended assertion', name, rejected.returncode, rejected.stderr)
        assert 'AddressSanitizer' not in rejected.stderr and 'runtime error:' not in rejected.stderr
        controls.append(dict(name=name, compiled=True, intended_assertion=assertion,
            mode=mode, returncode=rejected.returncode, binary_sha256=ba.sha(child_binary),
            compile_command=child_command))
    thread_result = dict(requested=thread_sanitizer, passed=False)
    if thread_sanitizer:
        tsan_command, tsan_binary, checked = variant(destination / 'thread-sanitizer', tsan=True)
        unavailable = checked.returncode != 0 and (
            'FATAL: ThreadSanitizer: unexpected memory mapping' in checked.stderr)
        assert checked.returncode == 0 or unavailable, ('TSan', checked.returncode, checked.stderr)
        if not unavailable:
            assert json.loads(checked.stdout) == row
        thread_result.update(passed=not unavailable, runtime_unavailable=unavailable,
            returncode=checked.returncode, compile_command=tsan_command,
            binary_sha256=ba.sha(tsan_binary))
    assert all(ba.sha(Path(name)) == value for name, value in inputs.items()), 'input drift'
    return dict(passed=True, cases=row['cases'], scheduled_status_writer_cases=32,
        inputs_sha256=inputs, artifacts_sha256={str(path.relative_to(destination)): ba.sha(path)
            for path in sorted(destination.rglob('*')) if path.is_file()},
        selected_sha256={name: hashlib.sha256(text.encode()).hexdigest() for name, text in selected.items()},
        compile_command=command, binary_sha256=ba.sha(binary), mutation_controls=controls,
        sanitizers=['ASan', 'UBSan', 'leak-detection'], thread_sanitizer=thread_result,
        actual_RX_creation_AMPDU_per_link_event_and_full_owner_C=True,
        outer_close_cancel_join_source_checks=callers,
        accepted_owned_status_ID_writers_joined_in_framework=True,
        callback_tail_after_helper_inflight_clear_joined_in_framework=True,
        kernel_concurrency=False, full_RX_ingress_join=False, firmware_reuse_fence=False,
        physical_retirement=False, hardware=False,
        modeled_boundaries=['POSIX locks/RCU/work cancellation, not Linux scheduling',
            'outer WED callback epilogue after the actual reset helper returns',
            'active-link iteration and kernel allocation/references', 'provider/MCU/journal/IRQ/DMA effects'],
        limits=['Only the selected C bodies and retained owner execute in this host fixture.',
            'The outer teardown/reset bodies are source-bound order checks, not kernel execution.',
            'Late metadata remains possible; this is not all RX ingress or device/owner retirement.',
            'No firmware association/reuse authentication or physical drain/rearm is qualified.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--harness-root', type=Path, default=HERE)
    parser.add_argument('--name', required=True)
    parser.add_argument('--thread-sanitizer', action='store_true')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    destination = ROOT / '.local/npu-rro-ba-join-20261024' / args.name
    assert not destination.exists()
    try:
        result = run(destination, args.source_root.resolve(), args.harness_root.resolve(), args.thread_sanitizer)
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
