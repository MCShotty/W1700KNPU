#!/usr/bin/env python3
"""Execute selected actual HIF2 and Linux link-state C in a modeled framework."""
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
HARNESS = Path(__file__).with_name('hif2-binding-harness.c')


def selected_function(source, name):
    pattern = r'(?m)^(?:static )?(?:struct [a-z0-9_]+ \*|void |int )' + re.escape(name) + r'\('
    matches = list(re.finditer(pattern, ba.masked(source)))
    assert len(matches) == 1, (name, len(matches))
    return ba.braced(source, matches[0].start(), False)


def run(destination, source, kernel_core):
    pci_path = source / 'mt7996/pci.c'
    inputs = {str(p.resolve()): ba.sha(p) for p in (pci_path, kernel_core,
        HARNESS, Path(__file__), Path(ba.__file__))}
    pci, core = pci_path.read_text(), kernel_core.read_text()
    selected = {f'selected-HIF-{key}.inc': selected_function(pci, name) for key, name in (
        ('lookup', 'mt7996_pci_get_hif2'), ('init', 'mt7996_pci_init_hif2'),
        ('probe', 'mt7996_pci_hif2_probe'), ('remove', 'mt7996_hif_remove'))}
    selected.update({f'selected-link-{key}.inc': selected_function(core, name) for key, name in (
        ('init', 'device_link_init_status'), ('unbind', 'device_links_unbind_consumers'))})
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
        binary = folder / 'hif2-binding'
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
    assert executed.returncode == 0, ('HIF binding', executed.returncode, executed.stderr)
    row = json.loads(executed.stdout)
    assert row == dict(passed=True, cases=26, framework_modeled=True,
        kernel_concurrency=False, physical_drain=False, hardware=False), row
    mutations = (
        ('no-device-pin', 'selected-HIF-lookup.inc', 'supplier = get_device(hif->dev);',
         'supplier = hif->dev;', 'lookup-keeps-device-through-link-creation'),
        ('stateless-link', 'selected-HIF-init.inc', 'DL_FLAG_AUTOREMOVE_CONSUMER);',
         'DL_FLAG_STATELESS);', 'supplier-data-read-only-after-qualified-managed-link'),
        ('unbinding-link-accepted', 'selected-HIF-init.inc',
         'READ_ONCE(link->status) != DL_STATE_CONSUMER_PROBE ||', 'false ||',
         'supplier-data-read-only-after-qualified-managed-link'),
        ('wrong-driver-accepted', 'selected-HIF-init.inc',
         'READ_ONCE(supplier->driver) != &mt7996_hif_driver.driver', 'false',
         'supplier-driver-identity-checked-before-drvdata'),
        ('missing-fresh-owner-check', 'selected-HIF-init.inc', 'hif->dev != supplier ||', '',
         'unsafe-selected-supplier-defers-not-optional-or-success'),
        ('stale-recognition-accepted', 'selected-HIF-init.inc',
         '(readl(hif->regs + MT_PCIE_RECOG_ID) & MT_PCIE_RECOG_ID_MASK) != idx', 'false',
         'unsafe-selected-supplier-defers-not-optional-or-success'),
        ('selected-unsafe-becomes-optional', 'selected-HIF-init.inc', 'return ERR_PTR(ret);',
         'return NULL;', 'unsafe-selected-supplier-defers-not-optional-or-success'),
        ('failed-link-pin-leak', 'selected-HIF-init.inc', '\tput_device(supplier);\n', '',
         'rejected-binding-drops-explicit-pin-keeps-core-link'),
        ('unlocked-list-remove', 'selected-HIF-remove.inc', '\tspin_lock_bh(&hif_lock);\n', '',
         'HIF-list-removal-uses-lookup-lock'),
        ('drvdata-published-too-late', 'selected-HIF-probe.inc', '\tpci_set_drvdata(pdev, hif);\n', '',
         'HIF-drvdata-and-resources-ready-before-list-publication'),
        ('uncleared-removed-drvdata', 'selected-HIF-remove.inc', '\tpci_set_drvdata(pdev, NULL);\n', '',
         'HIF-unpublished-before-modeled-devres-free'),
        ('recognition-reuse', 'selected-HIF-init.inc', 'if (hif_idx == MT_PCIE_RECOG_ID_MASK)', 'if (false)',
         'recognition-ID-never-wraps-or-reuses'),
        ('core-skips-probe-wait', 'selected-link-unbind.inc', 'if (status == DL_STATE_CONSUMER_PROBE)',
         'if (false)', 'actual-core-waits-or-removes-consumer-before-supplier-teardown'),
        ('core-skips-consumer-release', 'selected-link-unbind.inc',
         '\t\t\tdevice_release_driver_internal(consumer, NULL,\n\t\t\t\t\t\t       consumer->parent);', '',
         'actual-core-waits-or-removes-consumer-before-supplier-teardown'))
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
        artifacts_sha256={str(p.relative_to(destination)): ba.sha(p)
            for p in sorted(destination.rglob('*')) if p.is_file()}, compile_command=command,
        binary_sha256=ba.sha(binary), mutation_controls=controls, sanitizers=['ASan', 'UBSan', 'leak-detection'],
        actual_selected_HIF_lookup_init_probe_remove_C=True,
        actual_selected_kernel_link_init_status_and_unbind_consumers_C=True,
        modeled_boundaries=['device references/devres and PCI identity', 'locks and injected interleavings',
            'MMIO recognition protocol', 'device_link_add/purge and consumer probe/remove callbacks'],
        kernel_concurrency=False, physical_drain=False, hardware=False,
        limits=['Only the selected two kernel functions execute, not the whole Linux driver core.',
            'Deterministic interleavings do not prove Linux thread scheduling or physical HIF2 teardown.',
            'The separate PCI fixture executes the primary probe/error/remove path with HIF selection modeled.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--kernel-core', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    destination = args.output.resolve()
    assert not destination.exists()
    try:
        result = run(destination, args.source_root.resolve(), args.kernel_core.resolve())
    except BaseException as error:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'failure.json').write_text(json.dumps(dict(passed=False,
            error_type=type(error).__name__, error=str(error)), indent=2) + '\n')
        raise
    with (destination / 'result.json').open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(dict(passed=True, cases=result['cases'], controls=len(result['mutation_controls']),
        receipt=str(destination / 'result.json'), sha256=ba.sha(destination / 'result.json'))), flush=True)


if __name__ == '__main__':
    main()
