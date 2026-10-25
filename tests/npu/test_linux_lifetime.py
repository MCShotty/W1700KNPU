#!/usr/bin/env python3
"""Stage selected C for Linux/KUnit and validate its KTAP; never load a host module."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import test_cold_probe_lifetime as cold
import test_hif2_binding as hif
import test_rro_reset_ba_events as ba

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CASES = {
    'w1700k-linux-work': ('k_ctor_admission', 'k_init_joins', 'k_rc_joins', 'k_dump_joins',
        'k_reset_joins', 'k_wed_joins', 'k_scan_joins', 'k_mac_joins', 'k_roc_joins',
        'k_extra_mac_joins', 'k_extra_roc_joins'),
    'w1700k-linux-hif': ('k_probe_and_remove_join', 'k_already_unbinding_defers', 'k_failed_probe_drops_link')}
CONTROLS = {
    'cancel-init': ('work_mutation', 1, 'w1700k-linux-work', 'k_init_joins',
        ('work must reject queue after cleanup',)),
    'missing-rc': ('work_mutation', 2, 'w1700k-linux-work', 'k_rc_joins',
        ('cleanup must wait for held callback',)),
    'cancel-scan': ('work_mutation', 3, 'w1700k-linux-work', 'k_scan_joins',
        ('work must reject queue after cleanup',)),
    'early-recovery': ('work_mutation', 4, 'w1700k-linux-work', 'k_ctor_admission',
        ('cold reset admission must be closed',)),
    'no-managed-link': ('hif_mutation', 1, 'w1700k-linux-hif', 'k_probe_and_remove_join',
        ('supplier devres must outlive probing consumer', 'managed dependency must trigger consumer remove')),
    'unbinding-accepted': ('hif_mutation', 2, 'w1700k-linux-hif', 'k_already_unbinding_defers',
        ('an already-unbinding supplier must be rejected',))}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def renamed(text, old, new):
    anchor = 'void ' + old + '('
    assert text.count(anchor) == 1
    return text.replace(anchor, 'static void ' + new + '(', 1)


def stage(destination, source):
    assert not destination.exists()
    destination.mkdir(parents=True)
    paths = {name:source / name for name in ('mt7996/init.c', 'mt7996/pci.c',
        'mt7996/mt7996.h', 'mt7996/regs.h', 'mt76.h')}
    files = ('linux-lifetime-work.c', 'linux-lifetime-hif.c', 'linux-lifetime.Kconfig',
        'linux-lifetime.Makefile', 'linux-lifetime.config')
    inputs = {str(path.resolve()):sha(path) for path in [*paths.values(),
        *[HERE / name for name in files], Path(__file__), Path(cold.__file__),
        Path(hif.__file__), Path(ba.__file__)]}
    texts = {name:path.read_text() for name,path in paths.items()}
    init = texts['mt7996/init.c']
    constructor = cold.function(init, 'mt7996_init_device')
    cleanup = cold.function(init, 'mt7996_cleanup_device')
    selected = {
        'selected-work-init.inc': cold.function(init, 'mt7996_init_work'),
        'selected-work-constructor.inc': constructor,
        'selected-work-cleanup.inc': cleanup}
    enum = re.search(r'(?m)^enum\s*\{\s*MT76_STATE_INITIALIZED\b', ba.masked(texts['mt76.h']))
    assert enum
    selected['selected-work-state.inc'] = ba.braced(texts['mt76.h'], enum.start(), True)
    for name, old, replacement, symbol in (
        ('cancel', 'disable_work_sync(&dev->init_work);', 'cancel_work_sync(&dev->init_work);', 'mt7996_cleanup_cancel'),
        ('missing-rc', '\tdisable_work_sync(&dev->rc_work);\n', '', 'mt7996_cleanup_missing_rc'),
        ('cancel-scan', 'disable_delayed_work_sync(&dev->mt76.scan_work);',
         'cancel_delayed_work_sync(&dev->mt76.scan_work);', 'mt7996_cleanup_cancel_scan')):
        body = ba.once(cleanup, old, replacement, name)
        selected['selected-work-cleanup-' + name + '.inc'] = renamed(body, 'mt7996_cleanup_device', symbol)
    early = ba.once(constructor, '\tdisable_work(&dev->reset_work);\n', '', 'early-reset')
    early = ba.once(early, '\tdisable_work(&dev->dump_work);\n', '', 'early-dump')
    selected['selected-work-constructor-early.inc'] = renamed(early, 'mt7996_init_device', 'mt7996_init_device_early')
    pci = texts['mt7996/pci.c']
    for name, symbol in (('lookup', 'mt7996_pci_get_hif2'), ('init', 'mt7996_pci_init_hif2'),
        ('probe', 'mt7996_pci_hif2_probe'), ('remove', 'mt7996_hif_remove')):
        selected['selected-HIF-' + name + '.inc'] = hif.selected_function(pci, symbol)
    selected['selected-HIF-types.inc'] = ba.structure(texts['mt7996/mt7996.h'], 'mt7996_hif') + '\n'
    selected['selected-HIF-types.inc'] += '\n'.join(ba.macro(texts['mt7996/regs.h'], name)
        for name in ('MT_PCIE_RECOG_ID', 'MT_PCIE_RECOG_ID_MASK', 'MT_PCIE_RECOG_ID_SEM'))
    original = selected['selected-HIF-init.inc']
    begin = original.index('\tlink = device_link_add(')
    end = original.index('\thif = dev_get_drvdata(supplier);', begin)
    no_link = original[:begin] + '\tif (READ_ONCE(supplier->driver) != &mt7996_hif_driver.driver)\n\t\tgoto put_supplier;\n\n' + original[end:]
    no_link = ba.once(no_link, '\tstruct device_link *link;\n', '', 'no-link-declaration')
    selected['selected-HIF-init-no-link.inc'] = ba.once(no_link, 'mt7996_pci_init_hif2(',
        'mt7996_pci_init_hif2_no_link(', 'no-link-name')
    no_state = ba.once(original, 'READ_ONCE(link->status) != DL_STATE_CONSUMER_PROBE ||',
        'false ||', 'accept-unbinding')
    selected['selected-HIF-init-no-state.inc'] = ba.once(no_state, 'mt7996_pci_init_hif2(',
        'mt7996_pci_init_hif2_no_state(', 'no-state-name')
    for name, body in selected.items():
        with (destination / name).open('x') as stream:
            stream.write(body + '\n')
    for name in files:
        target = {'linux-lifetime.Kconfig':'Kconfig', 'linux-lifetime.Makefile':'Makefile'}.get(name, name)
        shutil.copyfile(HERE / name, destination / target)
    assert all(sha(Path(name)) == digest for name,digest in inputs.items())
    record = dict(passed=True, staged_only=True, kernel_built=False, kernel_executed=False,
        inputs_sha256=inputs, generated_sha256={path.name:sha(path) for path in destination.iterdir() if path.is_file()},
        cases=CASES, controls=CONTROLS, selected_actual_C=True, kernel_API_execution_proven=False,
        modeled_boundaries=['PCI presence, register map, MMIO and bandwidth',
            'radio/mac80211, NAPI/IRQ, TX worker, MCU/DMA and RRO owner effects',
            'primary synthetic bus wrappers around actual HIF helper/probe/remove'], physical_hardware=False)
    save(destination / 'stage.json', record)
    return record


def check_log(destination, log, kunit, mutation=None):
    assert not destination.exists()
    destination.mkdir(parents=True)
    raw = log.read_text()
    assert re.search(r'Linux version 6\.18\.52\b', raw), 'wrong-or-missing-kernel-release'
    assert not re.search(r'BUG:|WARNING: CPU:|Kernel panic', raw), 'unexpected-kernel-diagnostic'
    command = [sys.executable, '-u', '-B', str(kunit), 'parse', str(log),
        '--json=' + str(destination / 'parsed.json')]
    checked = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (destination / 'parse.log').write_text(checked.stdout + checked.stderr)
    parsed = json.loads((destination / 'parsed.json').read_bytes())
    assert len({group['name'] for group in parsed['sub_groups']}) == len(parsed['sub_groups']), 'duplicate-suite'
    assert all(len({case['name'] for case in group['test_cases']}) == len(group['test_cases'])
        for group in parsed['sub_groups']), 'duplicate-case'
    groups = {group['name']:{case['name']:case['status'] for case in group['test_cases']}
        for group in parsed['sub_groups']}
    counts = parsed['misc']
    if mutation is None:
        assert checked.returncode == 0
        assert groups == {suite:{name:'PASS' for name in names} for suite,names in CASES.items()}, groups
        assert counts == dict(tests=14, passed=14, failed=0, crashed=0, skipped=0, errors=0), counts
    else:
        parameter, value, suite, name, messages = CONTROLS[mutation]
        assert 'w1700k_linux_lifetime.' + parameter + '=' + str(value) in raw, 'mutation-parameter-not-observed'
        assert checked.returncode != 0
        assert groups == {suite:{name:'FAIL'}}, groups
        assert any(message in raw for message in messages), ('wrong-control-assertion', mutation)
        assert counts == dict(tests=1, passed=0, failed=1, crashed=0, skipped=0, errors=0), counts
    record = dict(passed=True, expected_failure=mutation is not None, mutation=mutation, counts=counts,
        groups=groups, command=command, parser_returncode=checked.returncode,
        raw_log_sha256=sha(log), parser_sha256=sha(kunit), parsed_json_sha256=sha(destination / 'parsed.json'),
        runner_sha256=sha(Path(__file__)), KTAP_interpreted=True,
        kernel_execution_must_be_bound_by_outer_runner=True, physical_hardware=False)
    save(destination / 'result.json', record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    staging = commands.add_parser('stage')
    staging.add_argument('--source-root', type=Path, required=True)
    staging.add_argument('--output', type=Path, required=True)
    checking = commands.add_parser('check')
    checking.add_argument('--log', type=Path, required=True)
    checking.add_argument('--kunit', type=Path, required=True)
    checking.add_argument('--output', type=Path, required=True)
    checking.add_argument('--mutation', choices=sorted(CONTROLS))
    args = parser.parse_args()
    if args.command == 'stage':
        result = stage(args.output.resolve(), args.source_root.resolve())
    else:
        result = check_log(args.output.resolve(), args.log.resolve(), args.kunit.resolve(), args.mutation)
    print(json.dumps(dict(passed=result['passed'], command=args.command)), flush=True)


if __name__ == '__main__':
    main()
