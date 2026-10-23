#!/usr/bin/env python3
"""Joint selected actual RX creation/event/retained BA owner; framework is modeled."""
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
        path = source / name
        return path if path.is_file() else ba.BASE_MT76 / name

    paths = {name: paired(name) for name in ('agg-rx.c', 'mt76.h', 'mt7996/main.c',
        'mt7996/mcu.c', 'mt7996/mcu.h', 'mt7996/mt7996.h', 'mt76_connac_mcu.h',
        'mt7996/npu-rro-reset.c')}
    files = {name: harness_root / name for name in ('rro-reset-ba-harness.c', 'rro-ba-link-harness.c')}
    files.update({name: HERE / name for name in ('rro-ba-link-platform.h',
        'rro-ba-owner-harness.c', 'rro-ba-owner-platform.h')})
    inputs = {str(path.resolve()): ba.sha(path) for path in [*paths.values(), *files.values(),
        Path(__file__), Path(ba.__file__), HERE / 'test_host_queue_publication.py']}
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
        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')

    def variant(folder, changes=None):
        folder.mkdir(parents=True, exist_ok=False)
        for name, text in selected.items():
            if changes and name == changes[0]:
                text = ba.once(text, changes[1], changes[2], folder.name)
            (folder / name).write_text(text)
        for name, path in files.items():
            shutil.copyfile(path, folder / name)
        original = ba.HARNESS
        ba.HARNESS = HERE / 'rro-ba-owner-harness.c'
        try:
            return ba.compile_and_run(folder, compiler, environment)
        finally:
            ba.HARNESS = original

    command, binary, executed = variant(destination)
    assert executed.returncode == 0, ('joint BA owner', executed.returncode, executed.stderr)
    row = json.loads(executed.stdout)
    assert row == dict(passed=True, cases=23, retained_host_BA_identity=True,
        firmware_reuse_fence=False, hardware=False), row
    mutations = (
        ('missing-owned-status-binding', 'selected-mcu.inc',
         'if (owned)\n\t\t\t\t\t\t\terr = mt7996_npu_rro_ba_bind',
         'if (false)\n\t\t\t\t\t\t\terr = mt7996_npu_rro_ba_bind',
         'actual-serial-original-active-and-primary-mapping-retained'),
        ('ignored-binding-error', 'selected-mcu.inc',
         'if (!err)\n\t\t\t\t\t\t\tWRITE_ONCE(tid->id',
         'if (true)\n\t\t\t\t\t\t\tWRITE_ONCE(tid->id',
         'conflicting-status-never-rebinds-first-association-or-new-TID'),
        ('wrong-primary-identity', 'selected-mcu.inc', 'idx, wcid->idx, e->tid, tid->serial',
         'idx, idx, e->tid, tid->serial', 'actual-serial-original-active-and-primary-mapping-retained'),
        ('accepted-status-conflict', 'selected-owner.inc',
         'if (ba->serial != serial || ba->wlan_id != wlan_id ||\n\t\t    ba->primary_wlan_id != primary_wlan_id || ba->tid != tid)',
         'if (false)', 'conflicting-status-never-rebinds-first-association-or-new-TID'),
        ('missing-DELETE-snapshot', 'selected-owner.inc', '\tba->reset_serial = ba->serial;\n', '',
         'DELETE-snapshots-original-BA-not-current-slot'),
        ('missing-DELETE-binding-check', 'selected-owner.inc', 'if (!ba->serial) {', 'if (false) {',
         'unbound-or-mismatched-DELETE-refused-before-record-publication'),
        ('missing-DELETE-tuple-check', 'selected-owner.inc',
         'if (ba->wlan_id != wlan_id || ba->tid != tid)', 'if (false)',
         'unbound-or-mismatched-DELETE-refused-before-record-publication'),
        ('missing-worker-snapshot-check', 'selected-owner.inc',
         'if (!ba->serial || ba->reset_serial != ba->serial ||\n\t\t    ba->wlan_id != record->wlan_id || ba->tid != record->tid)',
         'if (false)', 'provider-callback-needs-original-retained-identity'),
        ('lost-unusable-status-fault', 'selected-mcu.inc', 'if (owned && !seen)', 'if (false)',
         'missing-or-stopped-owned-status-retains-first-fault-tuple'),
        ('status-queues-after-close', 'selected-owner.inc',
         '\tif (!owner->closing)\n\t\tieee80211_queue_work', '\tif (true)\n\t\tieee80211_queue_work',
         'BA-owner-no-queue-after-close'),
        ('mode-drops-owned-status', 'selected-mcu.inc',
         '\t\t\tif (!mt7996_has_hwrro(dev) && !owned)', '\t\t\tif (!mt7996_has_hwrro(dev))',
         'owned-status-metadata-retained-after-mode-change'),
        ('unpublished-BA-table-leak', 'selected-owner.inc',
         '\tif (!try_module_get(THIS_MODULE)) {\n\t\tkfree(owner->bindings);',
         '\tif (!try_module_get(THIS_MODULE)) {', 'unpublished-BA-table-and-owner-unwind'),
        ('BA-serial-as-journal-generation', 'selected-owner.inc', 'record->generation, &record->ticket)',
         '(u32)ba->reset_serial, &record->ticket)', 'reset-journal-generation-not-host-BA-serial'),
        ('zero-serial-accepted', 'selected-owner.inc',
         'id >= ARRAY_SIZE(owner->records) || !serial || tid >= IEEE80211_NUM_TIDS',
         'id >= ARRAY_SIZE(owner->records) || tid >= IEEE80211_NUM_TIDS',
         'missing-or-stopped-owned-status-retains-first-fault-tuple'))
    controls = []
    for name, target, old, replacement, assertion in mutations:
        child_command, child_binary, rejected = variant(destination / name, (target, old, replacement))
        assert rejected.returncode == -signal.SIGABRT and assertion in rejected.stderr, (
            'control missed intended assertion', name, rejected.returncode, rejected.stderr)
        assert 'AddressSanitizer' not in rejected.stderr and 'runtime error:' not in rejected.stderr
        controls.append(dict(name=name, compiled=True, intended_assertion=assertion,
            returncode=rejected.returncode, binary_sha256=ba.sha(child_binary), compile_command=child_command))
    assert all(ba.sha(Path(name)) == value for name, value in inputs.items()), 'input drift'
    result = dict(passed=True, cases=row['cases'], inputs_sha256=inputs,
        artifacts_sha256={str(path.relative_to(destination)): ba.sha(path)
            for path in sorted(destination.rglob('*')) if path.is_file()},
        selected_sha256={name: hashlib.sha256(text.encode()).hexdigest() for name, text in selected.items()},
        compile_command=command, binary_sha256=ba.sha(binary), mutation_controls=controls,
        sanitizers=['ASan', 'UBSan', 'leak-detection'], actual_RX_creation_and_AMPDU_and_per_link_BA_C=True,
        actual_status_DELETE_and_full_retained_owner_C=True, retained_host_BA_binding=True,
        DELETE_avoids_current_RX_slot_lookup=True, reset_journal_generation_distinct_from_BA_serial=True,
        first_unseen_cookie_less_status_gap_characterized=True, firmware_reuse_fence_qualified=False,
        physical_MCU=False, kernel_concurrency=False, physical_retirement=False, hardware=False,
        modeled_boundaries=['kernel RCU/locks/work scheduling', 'kernel allocator/module/device references',
            'active-link iteration and station/vif lookup', 'provider transport/journal effects',
            'IRQ quarantine effect of abort', 'physical MCU and acknowledgment', 'DMA backing/drain'],
        limits=['Selected actual RX/AMPDU/per-link/status/DELETE C and full retained owner execute jointly in a single-threaded host fixture.',
            'Binding metadata is host creation identity, not an authenticated firmware association or a qualified session reuse fence.',
            'First unseen cookie-less status can still associate a replacement; current firmware reachability/order is not proved.',
            'No hot transport admission, production retirement/rearm, module loading or hardware acceptance follows.'])
    with (destination / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--harness-root', type=Path, default=HERE)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    destination = ROOT / '.local/npu-rro-ba-owner-20261024' / args.name
    assert not destination.exists()
    try:
        result = run(destination, args.source_root.resolve(), args.harness_root.resolve())
    except BaseException as error:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'failure.json').write_text(json.dumps(dict(passed=False,
            error_type=type(error).__name__, error=str(error)), indent=2) + '\n')
        raise
    print(json.dumps(dict(passed=True, cases=result['cases'], controls=len(result['mutation_controls']),
        receipt=str(destination / 'result.json'), sha256=ba.sha(destination / 'result.json'),
        firmware_reuse_fence_qualified=False)), flush=True)


if __name__ == '__main__':
    main()
