#!/usr/bin/env python3
"""Selected actual PCI/IRQ/remove/unregister C; kernel and hardware models."""
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
HARNESS = HERE / 'pci-irq-lifetime-harness.c'


def run(destination, source):
    paths = {name: source / ('mt7996/' + name) for name in ('pci.c', 'init.c', 'mmio.c', 'mt7996.h')}
    inputs = {str(path.resolve()): ba.sha(path) for path in [*paths.values(), HARNESS,
        Path(__file__), HERE / 'test_host_queue_publication.py', Path(ba.__file__)]}
    pci, init, mmio, header = (paths[name].read_text() for name in ('pci.c', 'init.c', 'mmio.c', 'mt7996.h'))
    anchor = 'irqreturn_t mt7996_irq_handler('
    assert mmio.count(anchor) == 1
    selected = {
        'selected-pci-irq.inc': ba.structure(header, 'mt7996_pci_irq'),
        'selected-irq-enable.inc': function(header, 'mt7996_irq_enable'),
        'selected-irq-handler.inc': ba.braced(mmio, mmio.index(anchor), False),
        'selected-pci-shutdown.inc': function(pci, 'mt7996_pci_shutdown_irqs'),
        'selected-pci-probe.inc': function(pci, 'mt7996_pci_probe'),
        'selected-pci-remove.inc': function(pci, 'mt7996_pci_remove'),
        'selected-unregister.inc': function(init, 'mt7996_unregister_device')}
    compiler = shutil.which('clang') or shutil.which('gcc')
    assert compiler
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')

    def variant(folder, change=None):
        folder.mkdir(parents=True, exist_ok=False)
        for name, text in selected.items():
            if change and name == change[0]:
                text = ba.once(text, change[1], change[2], folder.name)
            (folder / name).write_text(text + '\n')
        shutil.copyfile(HARNESS, folder / HARNESS.name)
        binary = folder / 'pci-irq-lifetime'
        command = [compiler, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra',
            '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
            str(folder / HARNESS.name), '-o', str(binary)]
        built = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (folder / 'compile.log').write_text(built.stdout + built.stderr)
        assert built.returncode == 0, ('compile', folder.name, built.stderr)
        executed = subprocess.run([str(binary)], cwd=folder, env=environment,
            capture_output=True, text=True, timeout=120, preexec_fn=ba.no_core_dump)
        (folder / 'run.stdout').write_text(executed.stdout)
        (folder / 'run.stderr').write_text(executed.stderr)
        return command, binary, executed

    command, binary, executed = variant(destination)
    assert executed.returncode == 0, ('PCI lifetime', executed.returncode, executed.stderr)
    row = json.loads(executed.stdout)
    assert row == dict(passed=True, cases=234, kernel_framework_modeled=True,
        complete_RX_NAPI_join=False, physical_drain=False, hardware=False), row
    mutations = (
        ('missing-unregister-IRQ-join', 'selected-unregister.inc', '\tmt7996_pci_shutdown_irqs(dev);\n', '',
         'IRQ-and-tasklet-join-before-modeled-DMA-cleanup'),
        ('primary-IRQ-left-live', 'selected-pci-shutdown.inc', 'if (!dev->pci_irq[i].requested)',
         'if (i == 0 || !dev->pci_irq[i].requested)', 'IRQ-actions-removed-before-tasklet-join'),
        ('HIF2-IRQ-left-live', 'selected-pci-shutdown.inc', 'if (!dev->pci_irq[i].requested)',
         'if (i == 1 || !dev->pci_irq[i].requested)', 'IRQ-actions-removed-before-tasklet-join'),
        ('assumed-physical-primary-IRQ', 'selected-pci-probe.inc', 'dev->pci_irq[0].irq = irq;',
         'dev->pci_irq[0].irq = pdev->irq;', 'only-successfully-requested-exact-IRQ-freed-once'),
        ('assumed-physical-HIF2-IRQ', 'selected-pci-probe.inc', 'dev->pci_irq[1].irq = hif2_irq;',
         'dev->pci_irq[1].irq = hif2_dev->irq;', 'only-successfully-requested-exact-IRQ-freed-once'),
        ('double-managed-IRQ-release', 'selected-pci-shutdown.inc', '\t\tdev->pci_irq[i].requested = false;\n', '',
         'only-successfully-requested-exact-IRQ-freed-once'),
        ('disabled-not-joined-tasklet', 'selected-pci-shutdown.inc', 'tasklet_kill(&mdev->irq_tasklet);',
         'tasklet_disable(&mdev->irq_tasklet);', 'IRQ-and-tasklet-join-before-modeled-DMA-cleanup'),
        ('late-enable-not-closed', 'selected-irq-enable.inc', 'if (!dev->irq_shutdown)', 'if (true)',
         'repeated-close-and-late-enable-cannot-rearm-or-touch-released-HIF2'),
        ('schedule-outside-admission-lock', 'selected-irq-enable.inc',
         '\t\ttasklet_schedule(&dev->mt76.irq_tasklet);\n\t}\n\tspin_unlock_irqrestore(&dev->mt76.mmio.irq_lock, flags);',
         '\t}\n\tspin_unlock_irqrestore(&dev->mt76.mmio.irq_lock, flags);\n\ttasklet_schedule(&dev->mt76.irq_tasklet);',
         'poll-completion-scheduling-shares-shutdown-admission-lock'),
        ('missing-monotonic-shutdown-latch', 'selected-pci-shutdown.inc', '\t\tdev->irq_shutdown = true;\n', '',
         'repeated-close-and-late-enable-cannot-rearm-or-touch-released-HIF2'),
        ('free-unallocated-primary-vectors', 'selected-pci-probe.inc', 'else if (dev->pci_irq[0].vectors)', 'else',
         'only-owned-vectors-freed-after-IRQ-removal'),
        ('early-HIF2-pin-release', 'selected-pci-remove.inc', '\tmt7996_unregister_device(dev);',
         '\tif (hif2_dev)\n\t\tput_device(&hif2_dev->dev);\n\tmt7996_unregister_device(dev);',
         'HIF2-resources-stop-before-last-pin-put'),
        ('IRQ-ignores-uninitialized-consumer', 'selected-irq-handler.inc',
         '\tif (!test_bit(MT76_STATE_INITIALIZED, &dev->mphy.state))\n\t\treturn IRQ_NONE;\n', '',
         'IRQ-registration-is-live-before-probe-completes'))
    controls = []
    for name, target, old, replacement, assertion in mutations:
        child_command, child_binary, rejected = variant(destination / name, (target, old, replacement))
        assert rejected.returncode == -signal.SIGABRT and assertion in rejected.stderr, (
            'control missed intended assertion', name, rejected.returncode, rejected.stderr)
        assert 'AddressSanitizer' not in rejected.stderr and 'runtime error:' not in rejected.stderr
        controls.append(dict(name=name, compiled=True, intended_assertion=assertion,
            returncode=rejected.returncode, binary_sha256=ba.sha(child_binary), compile_command=child_command))
    assert all(ba.sha(Path(name)) == digest for name, digest in inputs.items()), 'input drift'
    return dict(passed=True, cases=row['cases'], inputs_sha256=inputs,
        selected_sha256={name: hashlib.sha256(text.encode()).hexdigest() for name, text in selected.items()},
        artifacts_sha256={str(path.relative_to(destination)): ba.sha(path)
            for path in sorted(destination.rglob('*')) if path.is_file()},
        compile_command=command, binary_sha256=ba.sha(binary), mutation_controls=controls,
        sanitizers=['ASan', 'UBSan', 'leak-detection'],
        actual_selected_PCI_probe_remove_IRQ_enable_handler_and_unregister_C=True,
        actual_selected_PCI_shutdown_C=True, complete_RX_NAPI_join=False,
        kernel_concurrency=False, physical_drain=False, hardware=False,
        modeled_boundaries=['PCI/WED/IRQ/vector allocation and devres actions',
            'IRQ masks, register IDs and hardware side effects', 'tasklet execution/join and locks',
            'NPU/mac80211 registration and complete DMA/MCU cleanup', 'HIF2 device references'],
        limits=['The IRQ handler itself executes before normal remove in the selected-C fixture.',
            'Successful managed IRQ registration also invokes the actual handler before probe returns, while initialization is incomplete.',
            '234 measured setup combinations cover single/HIF2, mixed WED/vector ownership, ports/IRQ0 and12 injected stages.',
            'Framework resource accounting is not Linux concurrency, physical NPU/PCIe drain or complete RX/NAPI lifetime proof.',
            'HIF2 device references do not alone pin a concurrently unbound HIF2 driver/devres object.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    destination = ROOT / '.local/npu-pci-irq-lifetime-20261024' / args.name
    assert not destination.exists()
    try:
        result = run(destination, args.source_root.resolve())
    except BaseException as error:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'failure.json').write_text(json.dumps(dict(passed=False,
            error_type=type(error).__name__, error=str(error)), indent=2) + '\n')
        raise
    with (destination / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, cases=result['cases'], controls=len(result['mutation_controls']),
        receipt=str(destination / 'result.json'), sha256=ba.sha(destination / 'result.json'))), flush=True)


if __name__ == '__main__':
    main()
