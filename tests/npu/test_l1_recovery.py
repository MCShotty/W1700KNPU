#!/usr/bin/env python3
"""Actual host L1/stop/setup/IRQ/start control, with explicit API models."""
import argparse
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
import test_host_txfree as txfree

q = txfree.q
ROOT = q.ROOT
BUILD = ROOT/'.local/npu-l1-recovery'
OUT = ROOT/'research/checkpoints/2026-09-14-npu-l1-recovery'
PATCH = OUT/'006-mt7996-npu-l1-failure-state.patch'
HARNESS = ROOT/'tests/npu/l1-recovery-harness.c'
FILES = ['mt7996/mac.c', 'mt7996/dma.c', 'mt7996/init.c', 'mt7996/npu.c',
         'mt7996/mt7996.h', 'mt7996/debugfs.c', 'mt76.h', 'npu.c', 'airoha_offload.h']
FUNCTIONS = [('mt76.h', 'mt76_queue_is_wed_rro'), ('mt76.h', 'mt76_queue_is_npu_txfree'),
             ('mt7996/dma.c', 'mt7996_dma_start'), ('mt7996/npu.c', 'mt7996_npu_hw_stop'),
             ('mt7996/npu.c', '__mt7996_npu_hw_init'), ('npu.c', 'mt76_npu_disable_irqs'),
             ('mt7996/mac.c', 'mt7996_mac_reset_work')]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inputs():
    paths = [Path(__file__), HARNESS, PATCH, Path(txfree.__file__), Path(txfree.host.__file__),
             Path(q.__file__), q.ARCHIVE, txfree.PATCH, txfree.host.PATCH,
             ROOT/'firmware/source-lock.json', ROOT/'firmware/patches/openwrt.patch',
             ROOT/'firmware/patches/luci.patch', ROOT/'firmware/build.config']
    paths += sorted((ROOT/'firmware/overlay/openwrt/package/kernel/mt76/patches').glob('*.patch'))
    return {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in paths}


def sources():
    assert sha(q.ARCHIVE.read_bytes()) == q.ARCHIVE_SHA
    zstd = ROOT/'.build/openwrt/staging_dir/host/bin/zstd'
    raw = subprocess.check_output([str(zstd), '-dc', str(q.ARCHIVE)], timeout=30)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        original = {name: archive.extractfile('mt76-2026.09.01~be5ce791/'+name).read().decode() for name in FILES}
    destination = BUILD/'baseline'
    for name, value in original.items():
        path = destination/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    promoted = sorted((ROOT/'firmware/overlay/openwrt/package/kernel/mt76/patches').glob('*.patch'))
    lock = json.loads((ROOT/'firmware/source-lock.json').read_text())
    for patch in promoted:
        key = str(patch.relative_to(ROOT/'firmware/overlay/openwrt'))
        recorded = next(entry for entry in lock['openwrt']['changed_files'] if entry['path'] == key)
        assert sha(patch.read_bytes()) == recorded['sha256']
    logs = []
    for patch in [*promoted, txfree.host.PATCH, txfree.PATCH]:
        result = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)],
                                cwd=destination, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout+result.stderr
        logs.append(dict(patch=str(patch.relative_to(ROOT)), output=result.stdout))
    return {name: (destination/name).read_text() for name in FILES}, logs


def patched(before):
    destination = BUILD/'candidate'
    for name, value in before.items():
        path = destination/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    result = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(PATCH)],
                            cwd=destination, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    assert 'offset' not in result.stdout and 'fuzz' not in result.stdout, result.stdout
    return {name: (destination/name).read_text() for name in FILES}, result.stdout


def compile_harness(source, tag):
    destination = BUILD/tag
    destination.mkdir(parents=True, exist_ok=True)
    constants = [q.macro(source['mt76.h'], name) for name in
                 ('MT_QFLAG_WED', 'MT_QFLAG_WED_RRO', 'MT_QFLAG_WED_TYPE')]
    constants += [q.declaration(source['mt76.h'], 'enum', 'mt76_wed_type')]
    constants += [q.declaration(source['airoha_offload.h'], 'enum', name) for name in
                  ('airoha_npu_wlan_set_cmd', 'airoha_npu_wlan_get_cmd')]
    (destination/'l1-constants.inc').write_text('\n'.join(constants)+'\n')
    functions = {name: q.function(source[file], name) for file, name in FUNCTIONS}
    (destination/'l1-driver.inc').write_text('\n\n'.join(functions.values())+'\n')
    output = destination/'l1'
    command = [shutil.which('gcc'), '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-I', str(destination),
               str(HARNESS), '-o', str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout+result.stderr
    return output, dict(command=command, binary_sha256=sha(output.read_bytes()),
                        function_sha256={name: sha(value.encode()) for name, value in functions.items()},
                        constants_sha256=sha((destination/'l1-constants.inc').read_bytes()))


def run(binary, *, chip=7996, active=1, phys=7, wed=0, stop=0, setup=0,
        waits=7, repeat=0, bus_live=0, detach=0):
    values = [chip, active, phys, wed, stop, setup, waits, repeat, bus_live, detach]
    command = [str(binary), *map(str, values)]
    env = {**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1'}
    result = subprocess.run(command, capture_output=True, text=True, timeout=10, env=env)
    assert result.returncode == 0, result.stdout+result.stderr
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert rows[-1].get('summary') and not result.stderr
    return dict(args=values, summary=rows[-1], events=rows[:-1])


def failed(row, code, cleanup):
    s = row['summary']
    assert s['error'] == s['first_error'] == code, 'failure-latch'
    assert not s['queue_wakes'] and not s['completed'] and s['failed'] == 1, 'failed-resume'
    assert not s['tx_worker'] and not s['tx_napi'] and s['reset_state'] & 3 == 3, 'failed-host-state'
    assert s['cleanup'] == cleanup, 'failure-cleanup-boundary'
    assert not s['data_starts'] and not s['irq_enables'], 'failed-restart'
    assert not s['second_events'] and not s['full_resets'], 'failed-reentry'
    assert not any(event['op'] in ('wed_start', 'wed_rro_start', 'mac_reschedule', 'napi_enable', 'worker_enable')
                   for event in row['events']), 'failed-reactivation'
    assert s['token_sum'] == (0 if cleanup else 64*0xa5)
    assert s['ring_sum'] == (0 if cleanup else 64*0x5a)


def cases(old, new):
    nominal, failures, unchanged = [], [], []
    for chip, phys, wed, active in itertools.product((7996, 7992), (1, 3, 7), range(4), (0, 1)):
        args = dict(chip=chip, phys=phys, wed=wed, active=active)
        before, after = run(old, **args), run(new, **args)
        s = after['summary']
        assert not s['error'] and s['completed'] == s['queue_wakes'] == 1 and not s['failed']
        assert s['tx_worker'] and s['tx_napi'] and s['reset_state'] == 0
        assert s['cleanup'] == 2 and s['napi'] == [1]*5
        if active:
            events = after['events']
            setup_done = max(i for i, event in enumerate(events) if event['op'] == 'setup_model')
            first_start = next(i for i, event in enumerate(events) if event['op'] == 'set' and event['a'] == 0x50)
            assert setup_done < first_start, 'setup-before-dma'
            assert all(i > setup_done for i, event in enumerate(events) if event['op'] in ('wed_start', 'wed_rro_start'))
        else:
            assert before == after, 'inactive-regression'
        nominal.append(dict(before=before, after=after))
    for chip, wed in itertools.product((7996, 7992), range(4)):
        for repeat in (1, 2):
            for stop, error in ((1, -5), (2, -110), (3, -110), (4, -5)):
                args = dict(chip=chip, wed=wed, stop=stop, repeat=repeat, bus_live=1)
                before, after = run(old, **args), run(new, **args)
                assert before['summary']['queue_wakes'] and before['summary']['unsafe_cleanup_model']
                failed(after, error, 0)
                failures.append(dict(kind='stop', before=before, after=after))
            for setup in range(1, 8):
                args = dict(chip=chip, wed=wed, setup=setup, repeat=repeat)
                before, after = run(old, **args), run(new, **args)
                assert before['summary']['queue_wakes'] and before['summary']['data_starts']
                failed(after, -12, 2)
                failures.append(dict(kind='setup', before=before, after=after))
            for waits, cleanup in ((6, 0), (5, 2), (3, 2)):
                args = dict(chip=chip, wed=wed, waits=waits, repeat=repeat)
                before, after = run(old, **args), run(new, **args)
                assert before['summary']['queue_wakes']
                failed(after, -110, cleanup)
                failures.append(dict(kind='mcu-wait', before=before, after=after))
            before = run(old, chip=chip, wed=wed, detach=1, repeat=repeat)
            after = run(new, chip=chip, wed=wed, detach=1, repeat=repeat)
            assert before['summary']['queue_wakes']
            failed(after, -19, 0)
            failures.append(dict(kind='detachment', before=before, after=after))
    for wed, waits in itertools.product(range(4), (0, 3, 5, 6, 7)):
        before, after = run(old, active=0, wed=wed, waits=waits), run(new, active=0, wed=wed, waits=waits)
        assert before == after, 'non-npu-wait-regression'
        unchanged.append(after)
    return nominal, failures, unchanged


def mutations(source):
    original = source['mt7996/mac.c']
    checks = [
        ('stop-result', '\tif (ret)\n\t\tgoto npu_recovery_failed;',
         '\tif (ret && 0)\n\t\tgoto npu_recovery_failed;', dict(stop=1, repeat=2), -5, 0),
        ('init-result', '\tret = __mt7996_npu_hw_init(dev);\n\tif (ret)',
         '\tret = __mt7996_npu_hw_init(dev);\n\tif (ret && 0)', dict(setup=3, repeat=2), -12, 2),
        ('sticky-error', '\tWRITE_ONCE(dev->recovery.npu_error, ret);',
         '\t(void)ret;', dict(stop=1), -5, 0),
        ('reentry', '\tif (READ_ONCE(dev->recovery.npu_error))\n\t\treturn;',
         '', dict(stop=1, repeat=2), -5, 0),
        ('detachment', '\tif (!ret && npu_active && !mt76_npu_device_active(&dev->mt76))\n\t\tret = -ENODEV;\n',
         '', dict(detach=1, repeat=2), -19, 0),
    ]
    rows = []
    for name, before, after, args, error, cleanup in checks:
        assert before in original
        changed = {**source, 'mt7996/mac.c': original.replace(before, after, 1)}
        binary, info = compile_harness(changed, 'mutant-'+name)
        try:
            failed(run(binary, **args), error, cleanup)
        except AssertionError as problem:
            assert str(problem) in ('failure-latch', 'failed-reentry', 'failed-resume'), str(problem)
            rows.append(dict(name=name, detected=True, assertion=str(problem), binary=info))
        else:
            raise AssertionError('undetected '+name)
    changed = {**source, 'mt7996/dma.c': source['mt7996/dma.c'].replace(
        ' &&\n\t    (!reset || !mt76_npu_device_active(&dev->mt76))', '', 1)}
    assert changed['mt7996/dma.c'] != source['mt7996/dma.c']
    binary, info = compile_harness(changed, 'mutant-early-wed')
    try:
        failed(run(binary, setup=3, wed=1), -12, 2)
    except AssertionError as problem:
        assert str(problem) == 'failed-reactivation'
        rows.append(dict(name='early-wed', detected=True, assertion=str(problem), binary=info))
    else:
        raise AssertionError('undetected early WED start')
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--compile-only', action='store_true')
    args = parser.parse_args()
    before_inputs = inputs()
    old_source, patch_logs = sources()
    new_source, patch_log = patched(old_source)
    old, old_info = compile_harness(old_source, 'before')
    new, new_info = compile_harness(new_source, 'after')
    if args.compile_only:
        print(json.dumps(dict(compiled=2, application=patch_log)))
        return
    nominal, failures, unchanged = cases(old, new)
    mutants = mutations(new_source)
    incomplete = run(new, bus_live=1)
    assert incomplete['summary']['completed'] == 1 and incomplete['summary']['unsafe_cleanup_model'] == 2
    assert inputs() == before_inputs
    result = dict(schema=1, inputs_before_after=before_inputs, baseline_patch_application=patch_logs,
                  candidate_patch_application=patch_log, binaries=[old_info, new_info], nominal=nominal,
                  failures=failures, inactive_controls=unchanged, mutants=mutants,
                  successful_reply_without_drain_control=incomplete,
                  limits=['Linux/framework/provider functions outside the seven extracted functions are explicit models; register identifiers in the harness are symbolic.',
                          'DMA reset, token cleanup and individual NPU setup calls are boundaries, not their full implementations.',
                          'STOP/GET is exercised only with host-side message stubs. No firmware selector, INODE framing change or hardware command executes.',
                          'Successful legacy STOP/GET still permits modeled cleanup without an independent-NPU drain witness; full quiescence is unresolved.',
                          'Provider replacement/lifetime, already-inflight callbacks, physical containment, full reset/removal and recovery rearming remain open.',
                          'No source-lock/overlay, image, router, Wi-Fi or subagent change.'])
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    (OUT/'l1-control-flow.json').write_bytes(encoded)
    print(json.dumps(dict(nominal_pairs=len(nominal), failure_pairs=len(failures), inactive_controls=len(unchanged),
                          mutants=len(mutants), evidence_sha256=sha(encoded))))


if __name__ == '__main__':
    main()
