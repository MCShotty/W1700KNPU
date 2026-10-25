#!/usr/bin/env python3
"""Actual selected cold registration/cleanup C with modeled kernel/platform effects."""
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
HARNESS = Path(__file__).with_name('cold-probe-lifetime-harness.c')


def function(source, name):
    pattern = r'(?m)^(?:static\s+)?(?:int|void|bool|struct [a-z0-9_]+ \*)\s*' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{'
    matches = list(re.finditer(pattern, ba.masked(source)))
    assert len(matches) == 1, (name, len(matches))
    return ba.braced(source, matches[0].start(), False)


def run(destination, source, baseline=False, thread_sanitizer=False):
    original = ROOT / '.local/merge-nonoc-20260923/mt76-merged'
    paths = {name: source / name for name in ('mt7996/init.c', 'mt7996/pci.c', 'mt7996/mmio.c',
        'mt7996/mt7996.h', 'mt7996/mcu.c', 'mt7996/mac.c', 'mt7996/coredump.c', 'mac80211.c')}
    paths['mt76.h'] = source / 'mt76.h' if (source / 'mt76.h').exists() else original / 'mt76.h'
    inputs = {str(p.resolve()): ba.sha(p) for p in (*paths.values(), HARNESS, Path(__file__), Path(ba.__file__))}
    text = {name:p.read_text() for name,p in paths.items()}
    selected = {}
    for filename, name, symbol in (
        ('mt7996/init.c', 'init-work', 'mt7996_init_work'),
        ('mt7996/init.c', 'hardware', 'mt7996_init_hardware'),
        ('mt7996/init.c', 'register', 'mt7996_register_device'),
        ('mt7996/init.c', 'unregister', 'mt7996_unregister_device'),
        ('mt7996/coredump.c', 'coredump-register', 'mt7996_coredump_register'),
        ('mt7996/coredump.c', 'coredump-unregister', 'mt7996_coredump_unregister'),
        ('mt7996/mcu.c', 'mcu-exit', 'mt7996_mcu_exit'),
        ('mac80211.c', 'core-register', 'mt76_register_device'),
        ('mac80211.c', 'core-unregister', 'mt76_unregister_device'),
        ('mac80211.c', 'core-free', 'mt76_free_device'),
        ('mac80211.c', 'led-cleanup', 'mt76_led_cleanup')):
        selected['selected-' + name + '.inc'] = function(text[filename], symbol)
    if not baseline:
        assert re.search(r'\bbool\s+hw_init_done\s*;', ba.masked(text['mt7996/mt7996.h'])), 'readiness must not be a bitfield'
        reset = function(text['mt7996/mac.c'], 'mt7996_reset')
        assert 'READ_ONCE(dev->recovery.hw_init_done)' in reset
        selected['selected-constructor.inc'] = function(text['mt7996/init.c'], 'mt7996_init_device')
        selected['selected-cleanup.inc'] = function(text['mt7996/init.c'], 'mt7996_cleanup_device')
        probe = function(text['mt7996/mmio.c'], 'mt7996_mmio_probe')
        assert probe.count('mt7996_init_device(dev);') == 1
        assert probe.index('mt7996_init_device(dev);') < probe.index('tasklet_setup(') < probe.index('return dev;')
    body = function(text['mt7996/pci.c'], 'mt7996_pci_probe')
    selected['selected-pci-tail.inc'] = body[body.index('\tret = mt7996_register_device(dev);'):]
    parser = function(text['mt7996/mcu.c'], 'mt7996_mcu_parse_response')
    anchor = '\tif (!skb) {'
    assert parser.count(anchor) == 1
    selected['selected-timeout-branch.inc'] = ba.braced(parser, parser.index(anchor), False)
    enum = re.search(r'(?m)^enum\s*\{\s*MT76_STATE_INITIALIZED\b', ba.masked(text['mt76.h']))
    assert enum
    selected['selected-state.inc'] = ba.braced(text['mt76.h'], enum.start(), True)
    selected['selected-driver-flag.inc'] = ba.macro(text['mt76.h'], 'MT_DRV_NAPI_LIFETIME')
    selected['selected-pci-irq.inc'] = ba.structure(text['mt7996/mt7996.h'], 'mt7996_pci_irq')
    compiler = shutil.which('clang') or shutil.which('gcc')
    assert compiler
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')

    def variant(folder, leds=1, change=None, tsan=False):
        folder.mkdir(parents=True, exist_ok=False)
        for name, contents in selected.items():
            if change and name == change[0]: contents = ba.once(contents, change[1], change[2], folder.name)
            (folder / name).write_text(contents + '\n')
        shutil.copyfile(HARNESS, folder / HARNESS.name)
        binary = folder / 'cold-probe-lifetime'
        cc = shutil.which('gcc') if tsan else compiler
        assert cc
        command = [cc, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-pthread',
            '-DBASELINE=' + str(int(baseline)), '-DCONFIG_MT76_LEDS=' + str(leds),
            '-fno-omit-frame-pointer', '-fsanitize=' + ('thread' if tsan else 'address,undefined'),
            '-fno-sanitize-recover=all', str(folder / HARNESS.name), '-o', str(binary)]
        if tsan: command.insert(1, '-no-pie')
        built = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (folder / 'compile.log').write_text(built.stdout + built.stderr)
        assert built.returncode == 0, ('compile', folder.name, built.stderr)
        executed = subprocess.run([str(binary)], cwd=folder, env=environment,
            capture_output=True, text=True, timeout=120, preexec_fn=ba.no_core_dump)
        (folder / 'run.stdout').write_text(executed.stdout)
        (folder / 'run.stderr').write_text(executed.stderr)
        return command, binary, executed

    variants = []
    for leds in ((1,) if baseline else (0, 1)):
        command, binary, executed = variant(destination / ('leds-' + str(leds)), leds)
        assert executed.returncode == 0, ('cold-prefix', executed.returncode, executed.stderr)
        row = json.loads(executed.stdout)
        if baseline:
            assert row == dict(characterization_complete=True, cases=4, missing_unregister=True,
                conditional_dangling_coredump=True, unready_recovery_queued=True,
                ignored_worker_error_null_scheduler=True, hardware=False)
        else:
            assert row['passed'] and row['cases'] == row['profiles'] * row['fault_stages'] + row['early_prefixes'] + row['concurrency_cases']
            assert not row['physical_drain'] and not row['hardware']
        variants.append(dict(leds=leds, actual=row, compile_command=command, binary_sha256=ba.sha(binary)))
    controls = []
    mutations = (
        ('missing-mac80211-unregister', 'selected-cleanup.inc', '\tmt76_unregister_device(&dev->mt76);\n', '',
         'mac80211-and-LED-ownership-released-before-context-free'),
        ('cancel-not-disable-init', 'selected-cleanup.inc', 'disable_work_sync(&dev->init_work)', 'cancel_work_sync(&dev->init_work)',
         'permanent-work-admission-closed-before-context-free'),
        ('missing-rate-control-disable', 'selected-cleanup.inc', '\tdisable_work_sync(&dev->rc_work);\n', '',
         'permanent-work-admission-closed-before-context-free'),
        ('missing-scan-disable', 'selected-cleanup.inc', '\tdisable_delayed_work_sync(&dev->mt76.scan_work);\n', '',
         'permanent-work-admission-closed-before-context-free'),
        ('missing-ROC-disable', 'selected-cleanup.inc', 'if (test_bit(MT76_STATE_REGISTERED, &phy->mt76->state))', 'if (false)',
         'permanent-work-admission-closed-before-context-free'),
        ('recovery-enabled-before-readiness', 'selected-register.inc', '\tret = mt7996_init_hardware(dev);',
         '\tenable_work(&dev->reset_work);\n\tret = mt7996_init_hardware(dev);',
         'recovery-enabled-only-after-coredump-and-registration'),
        ('MCU-exit-before-ops', 'selected-cleanup.inc', 'if (dev->mt76.mcu_ops)', 'if (true)',
         'MCU-exit-only-after-MCU-and-DMA-attempt'),
        ('DMA-cleanup-before-attach', 'selected-cleanup.inc', '\tif (dma_attached)\n\t\tmt7996_dma_cleanup(dev);',
         '\tif (true)\n\t\tmt7996_dma_cleanup(dev);', 'DMA-cleanup-requires-attached-queue-operations'),
        ('missing-late-MCU-purge', 'selected-cleanup.inc', '\tskb_queue_purge(&dev->mt76.mcu.res_q);\n', '',
         'late-MCU-responses-purged-after-ingress-join'),
        ('missing-TX-worker-park', 'selected-cleanup.inc', '\tmt76_worker_disable(&dev->mt76.tx_worker);\n', '',
         'MCU-exit-keeps-response-ingress-after-TX-worker-join'),
        ('early-coredump-publication', 'selected-coredump-register.inc', '\tif (coredump_memdump) {',
         '\tdev->coredump.crash_data = crash_data;\n\tif (coredump_memdump) {', 'coredump-allocation-released-once'),
        ('missing-LED-failure-rollback', 'selected-core-register.inc',
         '\tif (IS_ENABLED(CONFIG_MT76_LEDS))\n\t\tmt76_led_cleanup(phy);\n', '',
         'mac80211-and-LED-ownership-released-before-context-free'),
        ('ignored-TX-worker-creation-error', 'selected-core-register.inc', '\tif (ret)\n\t\tgoto unregister_hw;',
         '\tif (false)\n\t\tgoto unregister_hw;', 'worker-start-error-cannot-reach-null-scheduler-task'),
        ('RRO-release-before-CPU-join', 'selected-cleanup.inc', '\tmt7996_pci_shutdown_irqs(dev);',
         '\tmt7996_wed_rro_free(dev);\n\tmt7996_pci_shutdown_irqs(dev);', 'RRO-cleanup-follows-CPU-and-DMA-cleanup'))
    if not baseline:
        for name, target, old, replacement, assertion in mutations:
            command, binary, rejected = variant(destination / name, change=(target, old, replacement))
            assert rejected.returncode == -signal.SIGABRT and assertion in rejected.stderr, (
                'control missed intended assertion', name, rejected.returncode, rejected.stderr)
            assert 'AddressSanitizer' not in rejected.stderr and 'runtime error:' not in rejected.stderr
            controls.append(dict(name=name, compiled=True, intended_assertion=assertion,
                returncode=rejected.returncode, binary_sha256=ba.sha(binary), compile_command=command))
    thread = dict(requested=thread_sanitizer, passed=False)
    if thread_sanitizer and not baseline:
        command, binary, checked = variant(destination / 'thread-sanitizer', tsan=True)
        unavailable = checked.returncode != 0 and 'FATAL: ThreadSanitizer: unexpected memory mapping' in checked.stderr
        assert checked.returncode == 0 or unavailable, ('TSan', checked.returncode, checked.stderr)
        thread.update(passed=not unavailable, runtime_unavailable=unavailable, returncode=checked.returncode,
            compile_command=command, binary_sha256=ba.sha(binary))
    assert all(ba.sha(Path(name)) == digest for name,digest in inputs.items()), 'input drift'
    return dict(passed=True, baseline_characterization=baseline, variants=variants,
        cases=sum(row['actual']['cases'] for row in variants), mutation_controls=controls,
        thread_sanitizer=thread, inputs_sha256=inputs,
        selected_sha256={name:hashlib.sha256(value.encode()).hexdigest() for name,value in selected.items()},
        artifacts_sha256={str(p.relative_to(destination)):ba.sha(p) for p in destination.rglob('*') if p.is_file()},
        actual_selected_registration_hardware_core_and_coredump_C=True,
        actual_selected_constructor_and_cleanup_C=not baseline,
        actual_selected_PCI_registration_error_tail=True, actual_selected_MCU_timeout_branch=True,
        modeled_boundaries=['kernel work-disable and callback scheduler effects, not actual Linux workqueues',
            'PCI/WED/IRQ/NAPI and TX worker control', 'radio registration and low-level hardware/MCU operations',
            'coredump allocator ownership and modeled family-dependent memory size', 'framework mac80211/LED registration'],
        limits=['Debugfs failure is injected: the current actual debugfs initializer always returns zero.',
            'The memdump-buffer allocation failure requires the modeled MT7996 family/nonzero layout; current MT7990 layout returns zero.',
            'Vfree retains test-only tombstone storage until fixture disposal; live ownership is checked independently.',
            'Only the source registration/error tail executes, not the full PCI probe or Linux PCI core.',
            'The separate source-bound PCI and HIF2 fixtures execute their corresponding actual helpers.',
            'No firmware, kernel module execution, physical DMA drain, image or hardware acceptance.'],
        kernel_concurrency=False, physical_drain=False, hardware=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--baseline', action='store_true')
    p.add_argument('--thread-sanitizer', action='store_true')
    args = p.parse_args()
    destination = args.output.resolve()
    assert not destination.exists()
    destination.mkdir(parents=True)
    try:
        result = run(destination, args.source_root.resolve(), args.baseline, args.thread_sanitizer)
    except BaseException as error:
        (destination / 'failure.json').write_text(json.dumps(dict(passed=False,
            error_type=type(error).__name__, error=str(error)), indent=2) + '\n')
        raise
    with (destination / 'result.json').open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(dict(passed=True, baseline=args.baseline, cases=result['cases'],
        controls=len(result['mutation_controls']), thread_sanitizer=result['thread_sanitizer']['passed'],
        result_sha256=ba.sha(destination / 'result.json'))), flush=True)


if __name__ == '__main__':
    main()
