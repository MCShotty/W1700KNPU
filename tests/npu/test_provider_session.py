#!/usr/bin/env python3
"""Actual provider setup/executor C, fault oracles and optional raw RV32 peer.

Kernel dependencies, provider transport delivery and DMA backing are modeled.
No physical containment, release/rearm, router access or flash is performed.
"""
import argparse
import ctypes
from functools import partial
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import traceback

sys.dont_write_bytecode = True
import test_npu_firmware_loader as loader

ROOT = loader.ROOT
SOURCE = ROOT / 'firmware/npu'
HARNESS = ROOT / 'tests/npu/provider-session-harness.c'
FUNCTIONS = ('airoha_npu_wlan_cmd_with_retry', 'airoha_npu_wlan_init_memory',
             'airoha_npu_wlan_session_snapshot', 'airoha_npu_wlan_session_close',
             'airoha_npu_wlan_init_session', 'airoha_npu_wlan_cold_command',
             'airoha_npu_wlan_bind_endpoint_session',
             'airoha_npu_wlan_msg_send_session', 'airoha_npu_wlan_msg_get_session')
CLIENTS = ('linux-control.c', 'control-client.c', 'control-v2-client.c', 'cold-client.c')
SERVERS = ('bootstrap.c', 'bootstrap-v2.c', 'control-v2.c', 'admission.c', 'barrier.c', 'cold-setup.c')


def prepare(directory, text, header):
    directory.mkdir(parents=True)
    shims = {
        'linux/types.h': '#ifndef TEST_TYPES_H\n#define TEST_TYPES_H\n#include <stdint.h>\n#include <stdbool.h>\n#include <stddef.h>\ntypedef uint8_t u8;\ntypedef uint32_t u32;\ntypedef uint64_t u64;\n#endif\n',
        'linux/mutex.h': '#ifndef TEST_MUTEX_H\n#define TEST_MUTEX_H\n#include <pthread.h>\n#include <assert.h>\nstruct mutex { pthread_mutex_t native; };\nstatic inline void mutex_init(struct mutex *m) { assert(!pthread_mutex_init(&m->native, 0)); }\nstatic inline void mutex_lock(struct mutex *m) { assert(!pthread_mutex_lock(&m->native)); }\nstatic inline void mutex_unlock(struct mutex *m) { assert(!pthread_mutex_unlock(&m->native)); }\n#endif\n',
        'linux/soc/airoha/airoha_offload.h': 'struct airoha_npu;\nint airoha_npu_wlan_control(struct airoha_npu *, void *, int);\n',
    }
    for name, contents in shims.items():
        path = directory / 'shims' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    q = loader.extract
    declarations = [q.declaration(header, 'enum', name) for name in
                    ('airoha_npu_wlan_set_cmd', 'airoha_npu_wlan_get_cmd')]
    declarations += [q.declaration(text, 'struct', name) for name in ('airoha_npu_dma_lifetime', 'airoha_npu_priv')]
    (directory / 'provider-session-types.inc').write_text('\n'.join(declarations) + '\n')
    (directory / 'provider-session.inc').write_text('\n\n'.join(q.function(text, name) for name in FUNCTIONS) + '\n')
    return [shutil.which('clang'), '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
            '-pthread', '-I' + str(directory), '-I' + str(directory / 'shims'), '-I' + str(SOURCE),
            HARNESS, *[SOURCE / name for name in (*CLIENTS, *SERVERS)]]


def native_peer(binary, pair, publication, *, wrong_identity=False, cold_commands=False,
                cold_failure=False, page_failure=False, host_sender=None):
    import test_npu_raw_pair as raw
    from test_provider_plan_native import ProviderRequest
    from test_bootstrap_native import BOOT, ADM
    from emulation_layout import STATE
    from unicorn import riscv_const as r
    from unicorn import UC_HOOK_MEM_WRITE

    code_path, data_path = publication / 'CODE-copied.bin', publication / 'DATA-published.bin'
    code, data = code_path.read_bytes(), data_path.read_bytes()
    plan = list(struct.iter_unpack('<2I', data[0x6300:0x6330]))
    identity = struct.unpack('<Q', data[0x63a0:0x63a8])[0]
    request, size = plan[-1]
    assert size == 256 and identity
    factory = ProviderRequest
    if cold_commands:
        from cold_wire_native import ColdProviderRequest
        factory = ColdProviderRequest
    h, _, _, manifest = raw.load(pair, factory=partial(factory, request=request), published=(code, data))
    h.hart = 0
    h.cpu.context_restore(h.fresh)
    assert h.reset() == 0x8400420a
    early = h.message([0x30, 10, 0])
    assert early['flags'] == 7 and early['words'][2] == 0x457
    lib = ctypes.CDLL(str(binary))
    lib.npu_test_reset.argtypes = [ctypes.c_uint64, ctypes.c_uint32]
    lib.npu_test_memory.argtypes = [ctypes.c_uint, ctypes.c_uint32, ctypes.c_uint32]
    lib.npu_test_reset(identity ^ int(wrong_identity), request)
    for i in range(4):
        lib.npu_test_memory(i, *plan[i + 1])
    frames, failures, workers = [], [], []
    wire = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_uint)
    tick = ctypes.CFUNCTYPE(None)

    @wire
    def transport(pointer, length):
        try:
            words = list(struct.unpack('<' + 'I' * (length // 4), ctypes.string_at(pointer, length)))
            reply = h.message(words)
            frames.append(dict(request=words, reply=reply))
            if reply['flags'] != 7:
                return -22
            ctypes.memmove(pointer, struct.pack('<' + 'I' * len(words), *reply['words']), length)
            if length == 12 and words[1] == 32:
                assert h.run(h.cpu.reg_read(r.UC_RISCV_REG_PC), [0x8400e330]) == 0x8400e330
                assert h.clear_count == 0x7000
            return 0
        except Exception as error:
            failures.append(traceback.format_exc())
            return -5

    @tick
    def advance_workers():
        try:
            if not workers:
                # Existing observer supplies explicitly modeled host publication
                # and scheduling. None of this is a physical drain certificate.
                h.finish_coordinator()
                workers.extend(h.worker(hart) for hart in range(1, 8))
                h.on_core0()
        except Exception as error:
            failures.append(traceback.format_exc())

    lib.npu_test_callbacks.argtypes = [wire, tick]
    lib.npu_test_callbacks(transport, advance_workers)
    result = lib.npu_test_run()
    assert not failures, failures
    expected = -71 if wrong_identity else 0
    assert result == expected, (result, frames[-1:])
    old_calls = lib.npu_test_calls()
    assert lib.npu_test_run() == (expected if expected else -16)
    assert lib.npu_test_calls() == old_calls and lib.npu_test_rng_calls() == 1
    cold = []
    if wrong_identity:
        assert len(frames) == 1 and h.get32(BOOT + 8) == 0
        strict = []
    else:
        assert [f['request'][5] for f in frames if len(f['request']) == 20] == [0, 1, 2, 3]
        assert [f['request'][1] for f in frames if len(f['request']) == 3] == [18, 32, 8, 23, 7, 12]
        assert h.get32(BOOT + 8) == 6 and h.get32(ADM + 4) == 0
        assert [h.get32(STATE + 20 + 4 * hart) for hart in range(8)] == [1] * 8
        assert [h.get32(STATE + 4 * index) for index in (1, 2, 3)] == [0, 0, 0]
        if cold_commands:
            packet_state = h.packet.symbols['npu_emulation_packet_state']
            page_state = h.binding.symbols['npu_emulation_page_state']
            cold_state = h.rv.symbols['npu_emulation_cold_setup_state']
            assert h.get32(packet_state) == h.get32(page_state) == h.get32(ADM + 4) == 0
            leases = []
            def observe_lease(cpu, access, address, size, value, data):
                assert size == 4
                leases.append(value)
            h.cpu.hook_add(UC_HOOK_MEM_WRITE, observe_lease, begin=ADM + 4, end=ADM + 7)
            lib.npu_test_endpoint.argtypes = [ctypes.c_uint64, ctypes.c_uint64, ctypes.c_int]
            assert lib.npu_test_endpoint(0x20000000, 0x100000, 2) == 0 and not failures, failures
            assert h.get32(cold_state + 8) == 24
            assert h.get32(cold_state + 48) == 0x20000000 and h.get32(cold_state + 52) == 0x100000
            lib.npu_test_command.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
                                            ctypes.POINTER(ctypes.c_uint32)]
            sequence = [(0x30, 10, 0), (0x10, 14, 2)]
            sequence += [(0x10, 1, 16)] if cold_failure else [(0x10, 1, 1536), (0x12, 1, 1024)]
            if not cold_failure:
                sequence += [(0x15, 0, 0x200d45a0), (0x15, 1, 16)] if page_failure else [
                    (0x15, 0, 0x200d45a0), (0x15, 1, 256),
                    (0x16, 0, 0x200d45b0), (0x16, 1, 512),
                    (0x17, 0, 0x200d45c0), (0x17, 1, 1024)]
            page_total, packet_before_pages = 0, None
            def issue(header, api, value):
                nonlocal page_total, packet_before_pages
                if header == 0x15 and api == 0:
                    packet_before_pages = bytes(h.cpu.mem_read(packet_state, 2076))
                if page_failure and header == 0x15 and api == 1:
                    h.tracking, h.inject, h.injected = True, 'claim-fault', False
                    h.claim_trigger, h.head_before, h.writes = 1, 0, []
                if cold_failure and api == 1:
                    h.packet_tracking = True
                    h.packet_mode = 'claim-fault'
                    h.packet_changed = False
                    h.packet_writes = []
                    h.getter_calls = 0
                    h.claim_trigger = 1
                    h.requested = value
                    h.head_before = 0
                output = ctypes.c_uint32(0xabcdef01)
                error = lib.npu_test_command(header, api, value, ctypes.byref(output))
                assert not failures, failures
                if header == 0x18:
                    assert api == 0 and error == -22
                    assert frames[-1]['reply']['flags'] == 3 and not frames[-1]['reply']['callbacks']
                    assert h.get32(cold_state + 8) == 2047 and h.get32(ADM + 4) == 0
                    cold.append(dict(header=header, api=api, value=value, error=error,
                                     next_unsupported=True, reply=frames[-1]))
                    return error
                if page_failure and header == 0x15 and api == 1:
                    h.tracking = False
                    assert h.injected and error == -71 and h.get32(page_state + 16) == 1
                    assert h.get32(packet_state + 16) == 2560
                    assert h.get32(ADM + 4) == h.get32(cold_state + 4) == 1
                    assert h.get32(ADM + 8) == h.get32(STATE + 16) == h.get32(cold_state) == 1
                    assert h.get32(0x3e901f44) == 0 and frames[-1]['reply']['words'][14] == 7
                    assert bytes(h.cpu.mem_read(packet_state, 2076)) == packet_before_pages
                    cold.append(dict(header=header, api=api, value=value, error=error,
                                     retained_ba_claims=1, retained_packet_claims=2560,
                                     retained_active=1, retained_inflight=1,
                                     fault_injection='BA owner fault after first committed claim', reply=frames[-1]))
                    return error
                if cold_failure and api == 1:
                    h.packet_tracking = False
                    assert error == -71 and h.get32(packet_state + 16) == 1
                    assert h.get32(ADM + 4) == h.get32(cold_state + 4) == 1
                    assert h.get32(ADM + 8) == h.get32(STATE + 16) == h.get32(cold_state) == 1
                    assert h.get32(0x3e902a84) == 0 and frames[-1]['reply']['words'][14] == 7
                    cold.append(dict(header=header, api=api, value=value, error=error,
                                     retained_claims=1, retained_active=1, retained_inflight=1,
                                     fault_injection='packet owner fault after first committed claim',
                                     reply=frames[-1]))
                    return error
                assert error == 0, (header, api, value, error, frames[-1:])
                assert output.value == (0x457 if header == 0x30 else value)
                assert h.get32(ADM + 4) == h.get32(cold_state + 4) == 0
                if header in (0x15, 0x16, 0x17):
                    selector = header & 15
                    if api == 0:
                        assert h.get32({5: 0x3e90395c, 6: 0x3e902a80, 7: 0x3e904630}[selector]) == value
                    else:
                        ring = h.get32({5: 0x3e902a94, 6: 0x3e902aa4, 7: 0x3e904638}[selector])
                        for index in range(value):
                            ident = page_total + index
                            assert struct.unpack('<4I', h.cpu.mem_read(ring + index * 16, 16)) == (
                                plan[4][0] + ident * 128, 0x800100, ident << 16, 0)
                        page_total += value
                        assert h.get32(page_state + 16) == page_total
                        assert h.get32({5: 0x3e901f44, 6: 0x3e903954, 7: 0x3e902ce8}[selector]) == 1
                    assert bytes(h.cpu.mem_read(packet_state, 2076)) == packet_before_pages
                cold.append(dict(header=header, api=api, value=value, output=output.value,
                                 packet_claims=h.get32(packet_state + 16),
                                 page_claims=h.get32(page_state + 16),
                                 completed=h.get32(cold_state + 8), reply=frames[-1]))
                print(json.dumps(dict(native_command=[header, api, value],
                    packet_claims=h.get32(packet_state + 16), ba_claims=h.get32(page_state + 16))), flush=True)
                return 0
            if host_sender and not cold_failure and not page_failure:
                for command in sequence[:2]:
                    assert issue(*command) == 0
                peer_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint)
                @peer_type
                def send(header, api, value):
                    try:
                        return issue(header, api, value)
                    except Exception:
                        failures.append(traceback.format_exc())
                        return -5
                sender = ctypes.CDLL(str(host_sender))
                sender.npu_host_txrx.argtypes = [ctypes.c_uint64, ctypes.c_uint, ctypes.c_uint, peer_type]
                assert sender.npu_host_txrx(0x20000000, 0, 0, send) == -22 and not failures, failures
                assert [(row['header'], row['api'], row['value']) for row in cold[:-1]] == sequence
            else:
                for command in sequence:
                    if issue(*command):
                        break
            assert leases == ([1, 0] * 4 + [1] if cold_failure else [1, 0] * 7 + [1] if page_failure else [1, 0] * 12)
            assert h.get32(packet_state + 16) == (1 if cold_failure else 2560)
            assert h.get32(cold_state + 8) == (25 if cold_failure else 63 if page_failure else 2047)
            assert h.get32(page_state + 16) == (0 if cold_failure else 1 if page_failure else 1792)
            assert h.get32(STATE + 4) == h.get32(STATE + 8) == 0
            cold.append(dict(native_lease_writes=leases, test_active_writes=False,
                             test_packet_init=False, test_page_init=False,
                             retained_claims=1 if cold_failure else 2560,
                             retained_ba_claims=0 if cold_failure else 1 if page_failure else 1792))
            old_calls = lib.npu_test_calls()
        strict = [h.message(words) for words in ([0x10, 1, 1536], [0x12, 1, 1024], [0x1a, 1, 512])]
        assert all(row['flags'] == 3 and not row['callbacks'] for row in strict)
    h.check_hooks()
    lib.npu_test_close()
    assert lib.npu_test_run() == (expected if expected else -71 if cold_failure or page_failure else -108) and lib.npu_test_calls() == old_calls
    return dict(passed=True, wrong_identity=wrong_identity, cold_failure=cold_failure, page_failure=page_failure,
                result=result, frames=frames, cold=cold,
                workers=workers, strict_denials=strict, initial_held=True,
                actual_c_linux_setup=True, actual_c_publication_readback=True,
                actual_c_txrx_sender=bool(host_sender and not wrong_identity and not cold_failure and not page_failure),
                synthetic_plan_identity_writes=False, post_load_elf_injection=False,
                inputs=manifest['inputs'] | {str(p.relative_to(ROOT)): loader.sha(p) for p in
                    (code_path, data_path, pair / 'manifest.json', binary)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--header', type=Path,
                        help='Immutable current provider header for replay while world replaces its prepared tree')
    parser.add_argument('--name', required=True)
    parser.add_argument('--pair', type=Path)
    parser.add_argument('--publication', type=Path)
    parser.add_argument('--cold-commands', action='store_true')
    parser.add_argument('--host-sender-receipt', type=Path)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    assert bool(args.pair) == bool(args.publication)
    source = args.source.resolve()
    dest = ROOT / '.local/npu-provider-session-20261010' / args.name
    assert source.is_relative_to(ROOT) and not dest.exists()
    dest.mkdir(parents=True)
    header = ROOT / '.build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.52/include/linux/soc/airoha/airoha_offload.h'
    if args.header:
        header = args.header.resolve()
        assert header.is_relative_to(ROOT)
    inputs = {str(path.relative_to(ROOT)): loader.sha(path) for path in
              (source, header, HARNESS, Path(__file__), Path(loader.__file__), Path(loader.extract.__file__))}
    inputs |= {str(path.relative_to(ROOT)): loader.sha(path) for path in SOURCE.rglob('*') if path.is_file()}
    host_sender = None
    if args.host_sender_receipt:
        receipt = args.host_sender_receipt.resolve()
        evidence = json.loads(receipt.read_text())
        assert receipt.is_relative_to(ROOT) and evidence['passed']
        host_sender = (ROOT / evidence['shared']).resolve()
        assert host_sender.is_relative_to(ROOT) and loader.sha(host_sender) == evidence['shared_sha256']
        assert all(loader.sha(ROOT / path) == digest for path, digest in evidence['inputs'].items())
        inputs |= evidence['inputs'] | {str(p.relative_to(ROOT)): loader.sha(p) for p in (receipt, host_sender)}
    text, htext = source.read_text(), header.read_text()
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    flags = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all']
    command = prepare(dest / 'host', text, htext)
    binary = dest / 'host/test'
    loader.run(command + flags + ['-o', binary], dest / 'host/build.log')
    matrix = json.loads(loader.run([binary], dest / 'host/run.log', env=env).stdout)
    print(json.dumps(dict(stage='host', **matrix)), flush=True)
    mutations = {
        'allow-second-attempt': loader.once(text, 'if (priv->wlan_session_attempted) {', 'if (false) {'),
        'accept-wrong-boot-lo': loader.once(text, 'snapshot.client.boot_lo != lower_32_bits(priv->boot_identity)', 'false'),
        'accept-wrong-boot-hi': loader.once(text, 'snapshot.client.boot_hi != upper_32_bits(priv->boot_identity)', 'false'),
        'accept-unheld-release': loader.once(text, 'client->epoch != 1 || client->released || client->armed ||',
                                          'client->epoch != 1 || client->armed ||'),
        'skip-bootstrap': loader.once(text, '\terr = airoha_npu_wlan_init_memory(npu);\n', '\terr = 0;\n'),
        'ignore-discover-error': loader.once(text, '\terr = npu_linux_control_exchange(&priv->wlan_control, NPU_CONTROL_DISCOVER);\n\tif (err)\n\t\tgoto hold;',
                                             '\terr = npu_linux_control_exchange(&priv->wlan_control, NPU_CONTROL_DISCOVER);\n\t(void)err;'),
        'accept-partial-parking': loader.once(text, '\t\treturn -EAGAIN;\n', '\t\treturn 0;\n'),
        'omit-close-consumption': loader.once(text, '\tpriv->wlan_session_attempted = true;\n\tif (!priv->wlan_session_error)',
                                              '\tif (!priv->wlan_session_error)'),
        'omit-final-poll-check': loader.once(text, '\terr = airoha_npu_wlan_session_snapshot(priv, true);\n\tif (err == -EAGAIN)',
                                            '\terr = -EAGAIN;\n\tif (err == -EAGAIN)'),
    }
    rejected = []
    for name, contents in mutations.items():
        directory = dest / 'mutants' / name
        command = prepare(directory, contents, htext)
        mutant = directory / 'test'
        loader.run(command + flags + ['-o', mutant], directory / 'build.log')
        done = loader.run([mutant], directory / 'run.log', env=env, accepted=11)
        assert 'FAIL[session]' in done.stderr and 'AddressSanitizer' not in done.stderr
        rejected.append(dict(name=name, binary_sha256=loader.sha(mutant), failed_oracle=done.stderr.strip()))
    print(json.dumps(dict(stage='mutants', rejected=len(rejected))), flush=True)
    native = []
    if args.pair:
        shared = dest / 'host/provider-session.so'
        command = prepare(dest / 'native', text, htext)
        loader.run(command + ['-shared', '-fPIC', '-o', shared], dest / 'native/build.log')
        native = [native_peer(shared, args.pair.resolve(), args.publication.resolve(), wrong_identity=wrong,
                              cold_commands=args.cold_commands, host_sender=host_sender)
                  for wrong in (False, True)]
        if args.cold_commands:
            native.append(native_peer(shared, args.pair.resolve(), args.publication.resolve(),
                                      cold_commands=True, cold_failure=True))
            native.append(native_peer(shared, args.pair.resolve(), args.publication.resolve(),
                                      cold_commands=True, page_failure=True))
        print(json.dumps(dict(stage='native', cases=len(native), passed=True)), flush=True)
    assert all(loader.sha(ROOT / path) == digest for path, digest in inputs.items())
    probe = loader.extract.function(text, 'airoha_npu_probe')
    assert 'npu->ops.wlan_init_reserved_memory = airoha_npu_wlan_init_session;' in probe
    assert 'npu->ops.wlan_bind_endpoint = airoha_npu_wlan_bind_endpoint_session;' in probe
    assert probe.index('airoha_npu_start_firmware') < probe.index('devm_add_action_or_reset(dev, airoha_npu_wlan_session_close') < probe.index('platform_set_drvdata')
    result = dict(passed=True, matrix=matrix, mutants=rejected, native=native, inputs=inputs,
                  sanitizers=['address', 'undefined', 'leak'],
                  limits=['Real provider once-owned setup, Linux executor/client and native portable bootstrap server C; pthread/kernel/RNG/OF/transport dependencies modeled.',
                          'Optional raw RV32 peer uses actual-C publication bytes and Linux requests, but models backing, delivery, host pointer publication and worker scheduling.',
                          'Initial epoch stays held. Page5/6/7 prefix is covered, not indication/INODE/TXDONE complete setup, physical containment/drains, reclaim/rearm, recovery or clients.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=matrix['cases'], mutants=len(rejected), native_cases=len(native))))


if __name__ == '__main__':
    main()
