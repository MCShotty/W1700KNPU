#!/usr/bin/env python3
"""Whole selected RRO callers and kernel managed-DMA bookkeeping characterization.

No production body is rewritten. DMA/devres/framework/concurrency boundaries are
explicit models. A passing result describes current behavior, NOT target RRO
ownership qualification. Output is exclusive and retained, including failures.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import struct
import subprocess
import sys
import tarfile

import test_host_queue_publication as q
from test_memory_preflight import block

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from npu_world_sources import linked_module_sources

MT76 = ROOT / '.local/merge-nonoc-20260923/mt76-merged'
KERNEL = ROOT / '.local/merge-nonoc-20260923/kernel-merged'
BUILT_KERNEL = ROOT / ('.local/npu-build-scratch/native-c2/world-checked-irq-q6/build-upper/'
    'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.52')
ARCHIVE = ROOT / '.local/npu-validation-capsules/world-checked-irq-v5/root/.build/openwrt/dl/linux-6.18.52.tar.xz'
ARCHIVE_SHA = '2b69564f7d4fea0c859b1959ba33709ee6e9139bd100e30a853b57159a8221b8'
MODULE = ROOT / '.local/npu-checked-irq-modules/checked-q2/result.json'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''): h.update(data)
    return h.hexdigest()


def prepare(destination, module_receipt=MODULE):
    producer = linked_module_sources(ROOT, module_receipt)
    inputs = {producer['receipt']: producer['receipt_sha256'], **producer['inputs'], **producer['artifacts']}
    for path in (Path(__file__), Path(__file__).with_name('rro-reset-callers-harness.c'),
                 Path(q.__file__), Path(sys.modules[block.__module__].__file__),
                 ROOT / 'tools/npu_world_sources.py'):
        inputs[str(path.relative_to(ROOT))] = sha(path)
    assert sha(ARCHIVE) == ARCHIVE_SHA, 'kernel-archive-identity'
    inputs[str(ARCHIVE.relative_to(ROOT))] = ARCHIVE_SHA
    needed = ('kernel/dma/mapping.c', 'include/linux/dma-mapping.h')
    with tarfile.open(ARCHIVE, 'r:xz') as archive:
        kernel = {name: archive.extractfile('linux-6.18.52/' + name).read() for name in needed}
    for name, data in kernel.items():
        path = BUILT_KERNEL / name
        assert path.read_bytes() == data, ('managed-DMA-prepared-source-drift', name)
        inputs[str(path.relative_to(ROOT))] = sha(path)
    header = (MT76 / 'mt7996/mt7996.h').read_text()
    mt76 = (MT76 / 'mt76.h').read_text()
    offload = (KERNEL / 'include/linux/soc/airoha/airoha_offload.h').read_text()
    provider = (KERNEL / 'drivers/net/ethernet/airoha/airoha_npu.c').read_text()
    init = (MT76 / 'mt7996/init.c').read_text()
    npu = (MT76 / 'npu.c').read_text()
    mac80211 = (MT76 / 'mac80211.c').read_text()
    # The selected source cohort explicitly changes DMA ownership on attach.
    assert re.search(r'dev->dma_dev\s*=\s*npu->dev;', npu)
    macros = ('MT7996_RRO_MAX_SESSION', 'MT7996_RRO_WINDOW_MAX_LEN', 'MT7996_RRO_ADDR_ELEM_LEN',
              'MT7996_RRO_BA_BITMAP_LEN', 'MT7996_RRO_BA_BITMAP_CR_SIZE',
              'MT7996_RRO_BA_BITMAP_SESSION_SIZE', 'MT7996_RRO_WINDOW_MAX_SIZE',
              'MT7996_RRO_MSDU_PG_CR_CNT', 'MT7996_RRO_MSDU_PG_SIZE_PER_CR',
              'MT7996_MAX_RRO_RRS_RING', 'MT7996_RRO_MSDU_PG_HASH_SIZE', 'WED_RRO_ADDR_SIGNATURE_MASK')
    geometry = '\n'.join(q.macro(header, name) for name in macros) + '\n'
    geometry += '\n'.join(q.declaration(header, 'struct', name) for name in
        ('mt7996_wed_rro_addr', 'mt7996_wed_rro_session_id', 'mt7996_rro_queue_regs_emi')) + '\n'
    geometry += q.declaration(mt76, 'enum', 'mt76_hwrro_mode') + '\n'
    geometry += q.declaration(mt76, 'enum', 'mt76_rxq_id') + '\n'
    geometry += '\n'.join(q.declaration(mt76, 'enum', name) for name in
        ('mt76_npu_rro_profile', 'mt76_npu_rro_role')) + '\n'
    geometry += block(mt76, r'(?m)^enum \{(?=\n\s+MT76_STATE_INITIALIZED,)') + ';\n'
    geometry += q.declaration(offload, 'enum', 'airoha_npu_wlan_set_cmd') + '\n'
    member = block(header, r'(?m)^\tstruct \{(?=\n\t\tstruct \{\n\t\t\tvoid \*ptr;\n\t\t\tdma_addr_t phy_addr;\n\t\t\} ba_bitmap)')
    assert header[header.index(member) + len(member):].startswith(' wed_rro;')
    member += ' wed_rro;\n'
    mapping, dma_header = (kernel[name].decode() for name in needed)
    managed = q.declaration(mapping, 'struct', 'dma_devres') + '\n'
    managed += q.function(dma_header, 'dma_free_coherent') + '\n'
    managed += '\n'.join(q.function(mapping, name) for name in ('dmam_release', 'dmam_match', 'dmam_free_coherent')) + '\n'
    managed += block(mapping, r'(?m)^void \*dmam_alloc_attrs\(') + '\n'
    managed += block(dma_header, r'(?m)^static inline void \*dmam_alloc_coherent\(') + '\n'
    callers = ('mt7996_wed_rro_alloc', 'mt7996_wed_rro_init', 'mt7996_wed_rro_free', 'mt7996_wed_rro_work',
               'mt7996_init_hardware', 'mt7996_cleanup_device', 'mt7996_unregister_device')
    generated = {
        'geometry.h': geometry, 'rro-member.h': member,
        'active.h': q.function(header, 'mt7996_has_hwrro') + '\n' + q.function(mt76, 'mt76_npu_device_active'),
        'managed-dma.h': managed,
        'provider.h': q.function(provider, 'airoha_npu_wlan_msg_send_session'),
        'raw-framing.h': '\n'.join(q.macro(provider, name) for name in
            ('AIROHA_NPU_MBOX_SIZE', 'NPU_EN7581_7996_TX_CHECK_SIZE', 'NPU_EN7581_7996_INODE_DATA_SIZE')) + '\n' +
            q.declaration(provider, 'struct', 'wlan_mbox_data') + '\n' + q.function(provider, 'airoha_npu_wlan_msg_send'),
        'sender.h': q.function(offload, 'airoha_npu_wlan_send_msg') + '\n' + q.function(npu, 'mt76_npu_send_txrx_addr'),
        'rro-bridges.h': '\n'.join(q.function(offload, 'airoha_npu_wlan_rro_' + name) for name in
            ('open', 'alloc', 'publish', 'close')) + '\n' +
            '\n'.join(q.function(npu, 'mt76_npu_rro_' + name) for name in ('open', 'alloc', 'publish', 'close')),
        'callers.h': '\n\n'.join(q.function(init, name) for name in callers),
        'teardown.h': q.function(npu, 'mt76_npu_deinit') + '\n' +
            '\n'.join(q.function(mac80211, name) for name in ('mt76_unregister_device', 'mt76_free_device')),
    }
    for name, source in generated.items():
        with (destination / name).open('x') as stream: stream.write(source + '\n')
    return dict(producer=producer, inputs=inputs, selected_complete_callers=list(callers),
                selected_complete_teardown=['mt76_unregister_device', 'mt76_free_device', 'mt76_npu_deinit'],
                generated={name: sha(destination / name) for name in generated})


def validate_packets(path):
    raw = path.read_bytes()
    assert len(raw) == 134 * 24, 'captured-sequence-size'
    rows = list(struct.iter_unpack('<6I', raw))
    expected = [(0x10, 24, i, 0x88000000 + i * 65536, 0, 0) for i in range(128)]
    expected += [(0x11, 24, 0, 0x88801000, 0, 0)]
    expected += [(0x13, 24, i, 0, 0, 0) for i in (0, 7, 8, 1023, 1024)]
    assert rows == expected, 'actual-caller-payload-order'
    return rows


def no_core_dump():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def teardown_controls(destination, command, environment):
    original = (destination / 'teardown.h').read_text()
    variants = (
        ('missing-rcu-join', 'mt76_npu_deinit', 'synchronize_rcu();',
         'provider detach must join prior RCU readers'),
        ('missing-provider-detach', 'mt76_free_device', 'mt76_npu_deinit(dev);',
         'provider pointers must be unpublished'),
        ('missing-npu-reference-release', 'mt76_npu_deinit', 'airoha_npu_put(npu);',
         'NPU detach must release borrowed reference'),
        ('missing-rro-detach-handoff', 'mt76_npu_deinit', 'airoha_npu_wlan_rro_close(npu, dev->dev);',
         'lower detach must hand off RRO before unpublishing provider'),
    )
    controls = []
    for name, function, call, diagnostic in variants:
        directory = destination / name
        directory.mkdir()
        for path in destination.glob('*.h'):
            shutil.copyfile(path, directory / path.name)
        body = q.function(original, function)
        assert body.count(call) == 1, ('mutant-anchor', function, call)
        changed = original.replace(body, body.replace(call, '(void)0;'), 1)
        (directory / 'teardown.h').write_text(changed)
        harness = directory / 'rro-reset-callers-harness.c'
        shutil.copyfile(destination / harness.name, harness)
        binary = directory / 'rro-lifetime'
        replacements = {str(destination): str(directory),
            str(destination / harness.name): str(harness), str(destination / binary.name): str(binary)}
        compile_command = [replacements.get(argument, argument) for argument in command]
        compiled = subprocess.run(compile_command, capture_output=True, text=True, timeout=120)
        (directory / 'compile.log').write_text(compiled.stdout + compiled.stderr)
        assert compiled.returncode == 0, ('mutant-must-compile', name, compiled.stderr)
        completed = subprocess.run([str(binary), str(directory / 'caller-payloads.bin')],
            env=environment, capture_output=True, text=True, timeout=300, preexec_fn=no_core_dump)
        (directory / 'run.jsonl').write_text(completed.stdout)
        (directory / 'run.stderr').write_text(completed.stderr)
        assert completed.returncode == -signal.SIGABRT, ('mutant-not-assertion-rejected', name, completed.returncode)
        assert diagnostic in completed.stderr, ('mutant-wrong-assertion', name, completed.stderr)
        assert 'ERROR: AddressSanitizer' not in completed.stderr and 'runtime error:' not in completed.stderr
        controls.append(dict(name=name, function=function, removed_call=call, compiled=True,
            compile_returncode=compiled.returncode, run_returncode=completed.returncode,
            intended_assertion=diagnostic, assertion_rejected=True, sanitizer_fault=False,
            changed_header_sha256=sha(directory / 'teardown.h')))
    return controls


def caller_control(destination, command, environment, name, before, after, diagnostic):
    original = (destination / 'callers.h').read_text()
    assert original.count(before) == 1, ('caller-control-anchor', name)
    directory = destination / name
    directory.mkdir()
    for path in destination.glob('*.h'):
        shutil.copyfile(path, directory / path.name)
    (directory / 'callers.h').write_text(original.replace(before, after, 1))
    harness = directory / 'rro-reset-callers-harness.c'
    shutil.copyfile(destination / harness.name, harness)
    binary = directory / 'rro-lifetime'
    replacements = {str(destination): str(directory), str(destination / harness.name): str(harness),
                    str(destination / binary.name): str(binary)}
    compile_command = [replacements.get(argument, argument) for argument in command]
    compiled = subprocess.run(compile_command, capture_output=True, text=True, timeout=120)
    (directory / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, ('preparation-mutant-must-compile', compiled.stderr)
    completed = subprocess.run([str(binary), str(directory / 'caller-payloads.bin')], env=environment,
        capture_output=True, text=True, timeout=300, preexec_fn=no_core_dump)
    (directory / 'run.jsonl').write_text(completed.stdout)
    (directory / 'run.stderr').write_text(completed.stderr)
    assert completed.returncode == -signal.SIGABRT and diagnostic in completed.stderr
    assert 'ERROR: AddressSanitizer' not in completed.stderr and 'runtime error:' not in completed.stderr
    return dict(name=name, compiled=True, compile_returncode=compiled.returncode,
        run_returncode=completed.returncode, intended_assertion=diagnostic,
        assertion_rejected=True, sanitizer_fault=False, changed_header_sha256=sha(directory / 'callers.h'))


def run(destination, module_receipt=MODULE):
    metadata = prepare(destination, module_receipt)
    harness = Path(__file__).with_name('rro-reset-callers-harness.c')
    shutil.copyfile(harness, destination / harness.name)
    shutil.copyfile(__file__, destination / 'driver-at-run.py')
    binary = destination / 'rro-lifetime'
    command = [shutil.which('clang'), '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-sign-compare',
               '-Wno-missing-field-initializers', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
               '-I', str(destination), str(destination / harness.name), '-o', str(binary)]
    done = subprocess.run(command, capture_output=True, text=True, timeout=120)
    (destination / 'compile.log').write_text(done.stdout + done.stderr)
    assert done.returncode == 0, done.stderr
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    completed = subprocess.run([str(binary), str(destination / 'caller-payloads.bin')],
        env=environment, capture_output=True, text=True, timeout=300)
    (destination / 'run.jsonl').write_text(completed.stdout)
    (destination / 'run.stderr').write_text(completed.stderr)
    assert completed.returncode == 0, (completed.returncode, completed.stderr)
    cases = [json.loads(line) for line in completed.stdout.splitlines()]
    assert len(cases) == 1090, ('unexpected-characterization-case-count', len(cases))
    packets = validate_packets(destination / 'caller-payloads.bin')
    controls = teardown_controls(destination, command, environment)
    early_control = caller_control(destination, command, environment, 'missing-early-TX-preparation',
        'ret = mt7996_npu_prepare_tx_buffers(dev);', 'ret = 0;',
        'TX preparation must precede first RRO allocation')
    owned_controls = [caller_control(destination, command, environment, *variant) for variant in (
        ('ignored-owned-publication-error',
         'ret = mt76_npu_rro_publish(&dev->mt76, i);\n\t\t\tif (ret)\n\t\t\t\treturn ret;',
         'ret = mt76_npu_rro_publish(&dev->mt76, i);\n\t\t\t(void)ret;',
         'owned publication error stops higher init before hardware setup'),
        ('owned-free-falls-through',
         'mt76_npu_rro_close(&dev->mt76);\n\t\treturn;',
         'mt76_npu_rro_close(&dev->mt76);\n\t\t(void)0;',
         'devres_destroy(dev, dmam_release, dmam_match, &match_data)'),
    )]
    assert all(sha(ROOT / name) == value for name, value in metadata['inputs'].items()), 'input-drift'
    artifacts = {str(path.relative_to(ROOT)): sha(path) for path in destination.rglob('*') if path.is_file()}
    return dict(format='w1700k-rro-reset-callers-characterization-v1', passed=True, characterization_only=True,
        cases=len(cases), observations=cases, captured_caller_payloads=len(packets), command=command,
        metadata=metadata, artifacts=artifacts, sanitizers=['ASan', 'UBSan', 'leak-detection'],
        teardown_negative_controls=controls,
        early_preparation_negative_control=early_control,
        owned_caller_negative_controls=owned_controls,
        legacy_optional_provider_cases=1040, owned_provider_model_cases=50,
        checked_RRO_admitted=False, target_RRO_lifetime_qualified=False, hardware=False,
        limits=['Complete selected init/free/worker/higher-init/unregister bodies run verbatim with actual sender/dispatcher/raw framing.',
                'The PCI IRQ shutdown boundary is modeled here; its selected actual probe/remove/IRQ/cleanup C executes in the separate PCI lifetime suite.',
                'Tracked NAPI cleanup and permanent NPU IRQ shutdown are modeled here; their actual selected C executes in the independent NAPI/IRQ fixtures.',
                'Actual kernel dmam allocation/match/free/release bodies execute, not the kernel devres framework.',
                'Separate endpoint/provider devres registries and low-level DMA allocation/free are explicit models.',
                'Actual lower mt76 unregister/free/NPU detach bodies execute; early TX preparation is an observable modeled boundary in this harness, exercised as actual C separately.',
                'The 1040 legacy cases explicitly return EOPNOTSUPP for optional RRO ownership, not current checked-provider behavior.',
                'The 50 owned cases run actual initializer/free/mt76 bridges against modeled provider callbacks with nonzero publication errors; actual provider/core execute separately.',
                'mac80211/worker/queue cleanup/MCU/DMA internals and RCU scheduling are modeled.',
        'Independent reset-owner init/close/join/work are modeled here; its actual C has a separate suite.',
                'Captured records are actual 24-byte raw frames from caller/sender/dispatcher/framing at the modeled mailbox boundary.',
                'Raw model publication/free observations are not physical publication, use-after-free or drain proof.',
                'Injected IDs/high DMA addresses/disconnect ordering do not establish producer or allocator reachability.',
                'Characterization passes expose existing error/lifetime gaps; they do not qualify or implement retained RRO.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--module-receipt', type=Path, default=MODULE)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    destination = ROOT / '.local/npu-rro-reset-callers-20261023' / args.name
    destination.mkdir(parents=True, exist_ok=False)
    result = run(destination, args.module_receipt)
    with (destination / 'result.json').open('x') as stream: stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=result['cases'], receipt=str((destination / 'result.json').relative_to(ROOT)),
        sha256=sha(destination / 'result.json'), target_RRO_lifetime_qualified=False, hardware=False)), flush=True)


if __name__ == '__main__': main()
