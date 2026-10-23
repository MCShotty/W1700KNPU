#!/usr/bin/env python3
"""Execute selected real RX-TID creation/stop, per-link BA and event C together."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal

import test_rro_reset_ba_events as ba
from test_host_queue_publication import function

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def run(destination, source, harness_root):
    def paired(name):
        candidate = source / name
        return candidate if candidate.is_file() else ba.BASE_MT76 / name

    paths = {name: paired(name) for name in ('agg-rx.c', 'mt76.h', 'mt7996/main.c',
        'mt7996/mcu.c', 'mt7996/mcu.h', 'mt7996/mt7996.h', 'mt76_connac_mcu.h')}
    shared = harness_root / 'rro-reset-ba-harness.c'
    inputs = {str(path.resolve()): ba.sha(path) for path in [*paths.values(), shared,
        HERE / 'rro-ba-link-harness.c', HERE / 'rro-ba-link-platform.h', Path(__file__),
        Path(ba.__file__), HERE / 'test_host_queue_publication.py']}
    wire = paths['mt7996/mcu.h'].read_text()
    structs = [ba.structure(wire, name) for name in ('mt7996_mcu_rxd',
        'mt7996_mcu_wed_rro_event', 'mt7996_mcu_wed_rro_ba_event',
        'mt7996_mcu_wed_rro_ba_delete_event')]
    structs += [ba.structure(paths['mt76_connac_mcu.h'].read_text(), 'tlv'), ba.event_enum(wire),
        ba.structure(paths['mt7996/mt7996.h'].read_text(), 'mt7996_wed_rro_session_id'),
        ba.macro(paths['mt7996/mt7996.h'].read_text(), 'MT7996_RRO_MAX_SESSION')]
    selected = {'selected-structs.inc': '\n\n'.join(structs) + '\n',
        'selected-rx-tid.inc': ba.structure(paths['mt76.h'].read_text(), 'mt76_rx_tid') + '\n',
        'selected-aggr.inc': '\n\n'.join(function(paths['agg-rx.c'].read_text(), name) for name in
            ('mt76_rx_aggr_shutdown', 'mt76_rx_aggr_stop', 'mt76_rx_aggr_start')) + '\n',
        'selected-main.inc': ba.function(paths['mt7996/main.c'].read_text(), 'mt7996_ampdu_action') + '\n',
        'selected-mcu.inc': ba.function(paths['mt7996/mcu.c'].read_text(), 'mt7996_mcu_wed_rro_event') + '\n',
        'selected-add-rx-ba.inc': function(paths['mt7996/mcu.c'].read_text(), 'mt7996_mcu_add_rx_ba') + '\n'}
    compiler = shutil.which('clang') or shutil.which('gcc')
    assert compiler
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    files = {'rro-reset-ba-harness.c': shared,
        'rro-ba-link-harness.c': HERE / 'rro-ba-link-harness.c',
        'rro-ba-link-platform.h': HERE / 'rro-ba-link-platform.h'}

    def variant(folder, changes=None):
        folder.mkdir(parents=True, exist_ok=False)
        for name, content in selected.items():
            if changes and name == changes[0]:
                content = ba.once(content, changes[1], changes[2], folder.name)
            (folder / name).write_text(content)
        for name, path in files.items():
            shutil.copyfile(path, folder / name)
        old = ba.HARNESS
        ba.HARNESS = HERE / 'rro-ba-link-harness.c'
        try:
            return ba.compile_and_run(folder, compiler, environment)
        finally:
            ba.HARNESS = old

    command, binary, executed = variant(destination)
    assert executed.returncode == 0, ('real RX-TID/link harness', executed.returncode, executed.stderr)
    row = json.loads(executed.stdout)
    assert row == dict(passed=True, cases=19, late_cookie_less_rebind_characterized=True,
        MCU_error_context_retained_characterized=True, hardware=False), row
    mutants = (
        ('missing-primary-mapping', 'selected-mcu.inc',
         '\t\t\t\tif (wcid->def_wcid)\n\t\t\t\t\twcid = wcid->def_wcid;\n', '',
         'secondary-status-resolves-primary-reorder-object'),
        ('missing-stopped-check', 'selected-mcu.inc', 'if (!tid->stopped)', 'if (true)',
         'status-write-to-stopped-TID'),
        ('missing-TID-lock', 'selected-mcu.inc', '\t\t\t\t\tspin_lock_bh(&tid->lock);\n', '',
         'status-write-without-TID-lock'),
        ('missing-old-stop', 'selected-aggr.inc', '\tmt76_rx_aggr_stop(dev, wcid, tidno);\n', '',
         'RX-TID-initialized-before-publication'),
        ('missing-stop-latch', 'selected-aggr.inc', '\ttid->stopped = true;\n', '',
         'RX-TID-stopped-and-work-cancelled-before-RCU-retirement'),
        ('missing-allocation-guard', 'selected-main.inc', '\t\tif (ret)\n\t\t\tbreak;\n', '',
         'MCU-enable-requires-published-RX-TID'),
        ('missing-per-link-error-break', 'selected-add-rx-ba.inc', '\t\tif (ret)\n\t\t\tbreak;\n', '',
         'MCU-error-leaves-published-context-characterization-not-rollback-proof'),
        ('missing-creation-serial', 'selected-aggr.inc',
         '\ttid->serial = ++dev->rx_tid_serial;\n', '',
         'RX-TID-serial-assigned-before-publication'),
        ('reused-creation-serial', 'selected-aggr.inc',
         '\ttid->serial = ++dev->rx_tid_serial;\n', '\ttid->serial = dev->rx_tid_serial = 1;\n',
         'serial-replacement-never-reuses-identity'),
        ('missing-exhaustion-check', 'selected-aggr.inc',
         '\tif (dev->rx_tid_serial == U64_MAX)\n\t\treturn -EOVERFLOW;\n', '',
         'RX-TID-serial-assigned-before-publication'),
        ('late-exhaustion-check', 'selected-aggr.inc',
         '\tif (dev->rx_tid_serial == U64_MAX)\n\t\treturn -EOVERFLOW;\n\n\tmt76_rx_aggr_stop(dev, wcid, tidno);',
         '\tmt76_rx_aggr_stop(dev, wcid, tidno);\n\n\tif (dev->rx_tid_serial == U64_MAX)\n\t\treturn -EOVERFLOW;',
         'serial-exhaustion-keeps-current-object-and-blocks-MCU'),
        ('failed-allocation-consumes-serial', 'selected-aggr.inc',
         '\ttid = kzalloc(struct_size(tid, reorder_buf, size), GFP_KERNEL);\n\tif (!tid)\n\t\treturn -ENOMEM;\n\n\ttid->serial = ++dev->rx_tid_serial;',
         '\tdev->rx_tid_serial++;\n\ttid = kzalloc(struct_size(tid, reorder_buf, size), GFP_KERNEL);\n\tif (!tid)\n\t\treturn -ENOMEM;\n\n\ttid->serial = dev->rx_tid_serial;',
         'failed-allocation-does-not-consume-serial'))
    controls = []
    for name, target, old, replacement, assertion in mutants:
        child = destination / name
        child_command, child_binary, rejected = variant(child, (target, old, replacement))
        assert rejected.returncode == -signal.SIGABRT and assertion in rejected.stderr, (
            'control missed intended assertion', name, rejected.returncode, rejected.stderr)
        assert 'AddressSanitizer' not in rejected.stderr and 'runtime error:' not in rejected.stderr
        controls.append(dict(name=name, compiled=True, intended_assertion=assertion,
            returncode=rejected.returncode, binary_sha256=ba.sha(child_binary), compile_command=child_command))
    assert all(ba.sha(Path(name)) == value for name, value in inputs.items()), 'input drift'
    result = dict(passed=True, cases=row['cases'], inputs_sha256=inputs,
        artifacts_sha256={str(path.relative_to(destination)): ba.sha(path)
            for path in sorted(destination.rglob('*')) if path.is_file()},
        extracted_sha256={name: hashlib.sha256(content.encode()).hexdigest() for name, content in selected.items()},
        compile_command=command, binary_sha256=ba.sha(binary), mutation_controls=controls,
        sanitizers=['ASan', 'UBSan', 'leak-detection'],
        actual_RX_TID_start_shutdown_stop=True, actual_AMPDU_and_per_link_MCU_loop=True,
        actual_status_parser=True, physical_MCU=False, kernel_concurrency=False,
        late_cookie_less_rebind_characterized=True, MCU_error_context_retained_characterized=True,
        BA_generation_authenticated=False, physical_retirement=False, hardware=False,
        device_local_creation_serial=True, serial_nonwrapping=True,
        retained_BA_binding_propagation=False,
        modeled_boundaries=['RCU grace periods', 'device/TID locks', 'allocator failure',
            'active-link iteration and station/vif lookup', 'work initialization/cancellation',
            'physical MCU BA command', 'skb framing'],
        limits=['Verbatim selected production C and RX-TID/wire structs execute in a single-threaded host fixture.',
            'One controlled lookup/stop interleaving is modeled; this is not kernel concurrency qualification.',
            'Real RX-TID allocation assigns a non-wrapping device-local serial before publication. A cookie-less late status still binds the replacement slot; no firmware cookie, reuse fence or retained BA binding propagation is established.',
            'MCU failure retains the published host context, including partial per-link enable: no physical rollback is established.',
            'Fixture deferred frees model RCU disposal, not physical NPU/DMA drain or production RRO owner retirement.'])
    with (destination / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--harness-root', type=Path, default=HERE)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    destination = ROOT / '.local/npu-rro-ba-link-20261024' / args.name
    assert not destination.exists()
    try:
        result = run(destination, args.source_root.resolve(), args.harness_root.resolve())
    except BaseException as exc:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'failure.json').write_text(json.dumps(dict(passed=False,
            error_type=type(exc).__name__, error=str(exc)), indent=2) + '\n')
        raise
    print(json.dumps(dict(passed=True, cases=result['cases'], controls=len(result['mutation_controls']),
        receipt=str(destination / 'result.json'), sha256=ba.sha(destination / 'result.json'),
        late_reuse_fence_qualified=False)), flush=True)


if __name__ == '__main__':
    main()
