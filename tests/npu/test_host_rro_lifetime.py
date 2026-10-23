#!/usr/bin/env python3
"""Host C provider/client/broker/native RRO chain; no physical admission."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import test_provider_session as parent
import test_host_rx_event_lifetime as rx


def controls(destination, command, environment):
    environment = dict(environment, ASAN_OPTIONS='detect_leaks=0:detect_stack_use_after_return=1')
    variants = (
        ('missing-enrollment', 'npu_rro_enroll(&owner->journal, &owner->plan, &extent)',
         'NPU_RRO_OK', 'journal enrollment precedes caller CPU and full DMA outputs'),
        ('missing-CPU-protection', '!airoha_npu_rro_cpu_valid(owner, owner->allocations[slot].buf, extent.bytes)',
         'false', 'invalid CPU/DMA backing is retained without narrowing or caller exposure'),
        ('missing-retirement-handoff',
         'npu_rro_retirement_begin(&owner->journal, &owner->plan,\n\t\t\t\t\t owner->plan.identity.epoch, &ticket)',
         '((ticket = owner->journal.last_ticket + 1), NPU_RRO_OK)',
         'close records handoff, not CPU or physical retirement'),
        ('missing-owner-retention', 'life->exposed || life->rro', 'life->exposed',
         'actual cleanup retains RRO, RX, TX, mailboxes and reference ownership'),
    )
    original = (destination / 'provider-session.inc').read_text()
    records = []
    for name, before, after, diagnostic in variants:
        directory = destination / name
        directory.mkdir()
        for path in destination.iterdir():
            if path.suffix in ('.inc', '.c'):
                shutil.copyfile(path, directory / path.name)
        shutil.copytree(destination / 'shims', directory / 'shims')
        (directory / 'provider-session.inc').write_text(parent.loader.once(original, before, after))
        changed = [str(value).replace(str(destination), str(directory)) for value in command]
        parent.loader.run(changed, directory / 'build.log', timeout=300)
        completed = subprocess.run([directory / 'test'], env=environment, capture_output=True, text=True, timeout=1800)
        (directory / 'run.log').write_text(completed.stdout + completed.stderr)
        assert completed.returncode == 11 and diagnostic in completed.stderr, (name, completed.returncode, completed.stderr)
        assert 'ERROR: AddressSanitizer' not in completed.stderr and 'runtime error:' not in completed.stderr
        records.append(dict(name=name, compiled=True, intended_assertion=diagnostic,
            assertion_rejected=True, returncode=completed.returncode, sanitizer_fault=False,
            leak_check=False, leak_check_reason='Intended assertion exits before fixture-only disposal of retained allocations.'))
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--header', type=Path, required=True)
    parser.add_argument('--mt76', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    root, q = parent.ROOT, parent.loader.extract
    destination = root / '.local/npu-host-rro-lifetime-20261023' / args.name
    assert not destination.exists()
    source, header, mt76 = args.source.resolve(), args.header.resolve(), args.mt76.resolve()
    paths = [source, header, mt76 / 'npu.c', mt76 / 'mt76.h', Path(__file__),
        root / 'tests/npu/host-rro-lifetime-harness.c', parent.HARNESS,
        Path(parent.__file__), Path(parent.loader.__file__), Path(q.__file__), Path(rx.__file__)]
    paths += [path for path in parent.SOURCE.rglob('*') if path.is_file()]
    inputs = {str(path.relative_to(root)): parent.loader.sha(path) for path in paths}
    text, htext = source.read_text(), header.read_text()
    command = parent.prepare(destination, text, htext)
    names = ('airoha_npu_dma_retained', 'airoha_npu_dma_cleanup',
        'airoha_npu_wlan_alloc_rx_event_session', 'airoha_npu_wlan_alloc_tx_buffers_session',
        'airoha_npu_wlan_validate_tx_buffers_locked', 'airoha_npu_wlan_validate_tx_buffers_session',
        'airoha_npu_rro_status', 'airoha_npu_rro_hold', 'airoha_npu_rro_plan',
        'airoha_npu_rro_guard', 'airoha_npu_rro_exchange',
        'airoha_npu_wlan_rro_open_session', 'airoha_npu_rro_cpu_valid',
        'airoha_npu_wlan_rro_alloc_session', 'airoha_npu_wlan_rro_publish_session',
        'airoha_npu_wlan_rro_close_session')
    functions = '\n\n'.join(q.function(text, name) for name in names if name not in parent.FUNCTIONS)
    wrappers = ('airoha_npu_wlan_alloc_rx_event', 'airoha_npu_wlan_alloc_tx_buffers',
        'airoha_npu_wlan_validate_tx_buffers',
        'airoha_npu_wlan_rro_open', 'airoha_npu_wlan_rro_alloc',
        'airoha_npu_wlan_rro_publish', 'airoha_npu_wlan_rro_close')
    with (destination / 'provider-session.inc').open('a') as stream:
        stream.write(functions + '\n' + '\n'.join(q.function(htext, name) for name in wrappers) + '\n')
    ops = '''struct airoha_npu { struct device *dev; struct {
int (*wlan_alloc_rx_event)(struct airoha_npu *,struct device *,struct device *,u32,u32,void **,dma_addr_t *);
int (*wlan_alloc_tx_buffers)(struct airoha_npu *,struct device *,struct device *,const u32 *,dma_addr_t *,unsigned);
int (*wlan_validate_tx_buffers)(struct airoha_npu *,struct device *,struct device *,const u32 *,const dma_addr_t *,unsigned);
int (*wlan_rro_open)(struct airoha_npu *,struct device *,struct device *,u32,const dma_addr_t *,unsigned);
int (*wlan_rro_alloc)(struct airoha_npu *,struct device *,struct device *,u32,u32,u32,void **,dma_addr_t *);
int (*wlan_rro_publish)(struct airoha_npu *,struct device *,u32);
int (*wlan_rro_close)(struct airoha_npu *,struct device *);
} ops; };'''
    model = parent.loader.once(parent.HARNESS.read_text(), 'struct airoha_npu { struct device *dev; };', ops)
    platform = '''
#include <endian.h>
typedef uint32_t __le32;
#define cpu_to_le32(value) htole32(value)
''' + rx.PLATFORM.replace('addresses[7]', 'addresses[147]').replace('objects[7]', 'objects[147]')
    platform = parent.loader.once(platform, 'check(index<7,"one RX-event and six TX allocation attempts");',
        'check(index<147,"full RX/TX/RRO allocation geometry");')
    platform = parent.loader.once(platform, 'static dma_addr_t addresses[147];', '''
static pthread_mutex_t *consumer_mutex;
static bool fail_metadata;
static unsigned metadata_allocations;
static void *bad_rro_cpu;
static void *kzalloc(size_t bytes,int flags) {
    check(flags==GFP_KERNEL && consumer_mutex && pthread_mutex_trylock(consumer_mutex)==EBUSY,
          "RRO owner creation holds the process caller mutex");
    check(pthread_mutex_trylock(&priv.wlan_session_lock.native)==EBUSY,"RRO owner creation holds provider mutex");
    metadata_allocations++;
    return fail_metadata?NULL:calloc(1,bytes);
}
static dma_addr_t addresses[147];''')
    platform = parent.loader.once(platform, '    *addr=addresses[index];', '''
    if(index>=7)check(consumer_mutex && pthread_mutex_trylock(consumer_mutex)==EBUSY,
                      "RRO DMA allocation holds the process caller mutex");
    *addr=addresses[index];
    if(index>=7 && bad_rro_cpu)return bad_rro_cpu;''')
    model = parent.loader.once(model, '#include "provider-session.inc"', platform + '\n#include "provider-session.inc"')
    model = parent.loader.once(model,
        'if (external_transport) {\n        error = external_transport(packet, bytes);',
        'if (external_transport && bytes == NPU_RRO_WIRE_SIZE) {\n        error = external_transport(packet, bytes);')
    model = parent.loader.once(model,
        'check(npu == &priv.npu && bytes == 80, "control provider");',
        'check(npu == &priv.npu && (bytes == 80 || bytes == NPU_RRO_WIRE_SIZE), "control provider");')
    common = (mt76 / 'mt76.h').read_text()
    bridge = '\n'.join(q.declaration(common, 'enum', name) for name in
        ('mt76_npu_rro_profile', 'mt76_npu_rro_role')) + '\n'
    bridge += '\n'.join(q.function((mt76 / 'npu.c').read_text(), name) for name in
        ('mt76_npu_rro_open', 'mt76_npu_rro_alloc', 'mt76_npu_rro_publish', 'mt76_npu_rro_close'))
    (destination / 'consumer.inc').write_text(bridge + '\n')
    generated = destination / 'test.c'
    generated.write_text('#define main provider_matrix_main\n' + model + '\n#undef main\n#include "harness-at-run.c"\n')
    shutil.copyfile(__file__, destination / 'driver-at-run.py')
    shutil.copyfile(root / 'tests/npu/host-rro-lifetime-harness.c', destination / 'harness-at-run.c')
    command = [generated if path == parent.HARNESS else path for path in command]
    command += [*[parent.SOURCE / name for name in ('rro-lifetime.c','rro-native.c','rro-session.c')],
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
        '-Wno-unused-function', '-Wno-unused-variable', '-Wno-sign-compare', '-o', destination / 'test']
    parent.loader.run(command, destination / 'build.log', timeout=300)
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1:halt_on_error=1',
        UBSAN_OPTIONS='halt_on_error=1')
    completed = parent.loader.run([destination / 'test'], destination / 'run.log', env=environment, timeout=1800)
    matrix = json.loads(completed.stdout)
    assert matrix['passed'] and matrix['cases']==456 and matrix['profiles']==3
    assert matrix['publications']==3*129 and matrix['native_effects']==3*129
    assert matrix['negative_joint']==11 and matrix['late_tx_checks']==12 and not matrix['hardware']
    mutants = controls(destination, command, environment)
    assert all(parent.loader.sha(root / name) == expected for name, expected in inputs.items()), 'source-input-drift'
    artifacts = {str(path.relative_to(root)):parent.loader.sha(path) for path in destination.rglob('*') if path.is_file()}
    result = dict(passed=True, matrix=matrix, mutants=mutants, inputs=inputs, artifacts=artifacts,
        compile_command=[str(value) for value in command], sanitizers=['address', 'undefined', 'leak'],
        actual_provider_client_broker_native_host_c=True, native_effect_engine=True,
        operational_RRO_admitted=False, physical_retirement=False, hardware=False,
        limits=['Actual provider-owned allocation, mt76 bridge, portable client, codec, broker, journal and native effect C execute together.',
            'DMA backing/device references, mailbox transport, framework, CPU exclusion and cold platform effects remain host models.',
            'All three profiles enroll complete geometry and publish 129 native block/session effects with full mapped-array checks.',
            'No kernel module execution, RV32 instruction replay, physical drain, CPU join, reclamation or hardware admission is inferred.',
            'Fixture-only frees of retained buffers and owner metadata are not production retirement.'])
    with (destination / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(matrix), flush=True)


if __name__ == '__main__':
    main()
