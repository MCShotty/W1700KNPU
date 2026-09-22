#!/usr/bin/env python3
"""V2 host/RV32 identity protocol, retaining V1 as an unchanged baseline."""
import ctypes
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as arm
from unicorn import riscv_const as rv
import unicorn
import test_admission_native as firmware
import test_control_client as v1

ROOT = v1.ROOT
BUILD = ROOT / '.local/npu-control-v2'
OUT = ROOT / 'research/checkpoints/2026-09-14-npu-control-v2'
SOURCE = ROOT / 'firmware/npu'
HOST = SOURCE / 'control-v2-client.c'
SERVER = SOURCE / 'control-v2.c'
PLATFORM = ROOT / 'tests/npu/control-v2-platform-emulation.c'
BOOT = (0x12345678, 0x9abcdef0)
OTHER_BOOT = (0x10203040, 0x50607080)
STATE, WIRE, STACK, END = v1.STATE, v1.BUFFER, v1.STACK, v1.END
SESSION, LOADER = 0x3e906380, 0x3e9063a0
ACCEPTED, REJECTED, IGNORED = v1.ACCEPTED, v1.REJECTED, v1.IGNORED
DISCOVERED, BOUND, STOPPING, PARKED, FAILED = v1.DISCOVERED, v1.BOUND, v1.STOPPING, v1.PARKED, v1.FAILED
execute, sha = v1.execute, v1.sha


def build(host=HOST, server=SERVER, tag='v2'):
    BUILD.mkdir(parents=True, exist_ok=True)
    clang = shutil.which('clang')
    lld = shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'
    common = [clang, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-ffreestanding',
              '-fno-builtin', '-fno-stack-protector', '-I', SOURCE]
    client = [host, SOURCE / 'control-client.c']
    server_sources = [server, SOURCE / 'admission.c', SOURCE / 'barrier.c']
    native, aarch64, riscv = (BUILD / (tag + suffix) for suffix in ('.so', '-arm.elf', '-rv.elf'))
    execute([*common, *client, *server_sources, '-shared', '-fPIC', '-o', native])
    execute([*common, *client, '--target=aarch64-none-elf', '-mgeneral-regs-only', '-nostdlib',
             f'--ld-path={lld}', f'-Wl,-T,{v1.LINKER}', '-o', aarch64])
    execute([*common, *server_sources, '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
             '-nostdlib', f'--ld-path={lld}', PLATFORM,
             ROOT / 'tests/npu/barrier-core5-emulation.S', ROOT / 'tests/npu/barrier-workers-emulation.S',
             ROOT / 'tests/npu/admission-emulation.S',
             f'-Wl,-T,{ROOT}/tests/npu/barrier-workers-emulation.ld,--no-relax',
             '-Wl,--defsym=original_irq_30b6=0x840030b6',
             f'-Wl,--defsym=npu_emulation_control_v2_state={SESSION}',
             f'-Wl,--defsym=npu_emulation_control_v2_boot={LOADER}', '-o', riscv])
    return native, aarch64, riscv


class Host:
    calls = 0

    def __init__(self, paths, nonce=v1.NONCE):
        self.lib = ctypes.CDLL(str(paths[0]))
        self.state = (ctypes.c_uint32 * 17)()
        self.wire = (ctypes.c_ubyte * 82)()
        self.cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.cpu.mem_map(0x100000, 0x10000)
        self.cpu.mem_map(0x200000, 0x10000)
        self.cpu.mem_map(END, 0x1000)
        elf = ELFFile(io.BytesIO(paths[1].read_bytes()))
        assert elf['e_machine'] == 'EM_AARCH64'
        self.symbols = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
        for section in elf.iter_sections():
            if section['sh_flags'] & 2 and section['sh_type'] != 'SHT_NOBITS':
                self.cpu.mem_write(section['sh_addr'], section.data())
        self.call('init', [*nonce], [*nonce], void=True)

    def call(self, name, native, target, void=False):
        function = getattr(self.lib, 'npu_client_v2_' + name)
        function.restype = None if void else ctypes.c_uint32
        result = function(self.state, *native)
        saved = {getattr(arm, 'UC_ARM64_REG_X' + str(i)): 0x1234567800000000 + i for i in range(19, 30)}
        for reg, value in saved.items():
            self.cpu.reg_write(reg, value)
        self.cpu.reg_write(arm.UC_ARM64_REG_SP, STACK)
        self.cpu.reg_write(arm.UC_ARM64_REG_LR, END)
        for i, value in enumerate([STATE, *target]):
            self.cpu.reg_write(getattr(arm, 'UC_ARM64_REG_X' + str(i)), value & 0xffffffffffffffff)
        self.cpu.emu_start(self.symbols['npu_client_v2_' + name], END, count=30000, timeout=1000000)
        assert self.cpu.reg_read(arm.UC_ARM64_REG_PC) == END
        assert self.cpu.reg_read(arm.UC_ARM64_REG_SP) == STACK
        assert all(self.cpu.reg_read(reg) == value for reg, value in saved.items())
        assert (None if void else self.cpu.reg_read(arm.UC_ARM64_REG_W0)) == result
        assert self.cpu.mem_read(STATE, 68) == bytes(self.state)
        assert self.cpu.mem_read(WIRE - 1, 82) == bytes(self.wire)
        Host.calls += 1
        return result

    def request(self, length=80, pointer=True):
        self.wire[:] = [0xa5] * 82
        self.cpu.mem_write(WIRE - 1, bytes(self.wire))
        ticket = self.call('request', [ctypes.byref(self.wire, 1) if pointer else None, length],
                           [WIRE if pointer else 0, length])
        assert self.wire[0] == self.wire[81] == 0xa5
        return ticket, list(struct.unpack('<20I', bytes(self.wire)[1:81]))

    def complete(self, ticket, words=None, error=0, length=80, poison=False):
        if words is not None:
            self.wire[:] = b'\xa5' + struct.pack('<20I', *words) + b'\xa5'
            self.cpu.mem_write(WIRE - 1, bytes(self.wire))
        pointer = ctypes.c_void_p(1) if poison else (ctypes.byref(self.wire, 1) if words is not None else None)
        address = 1 if poison else (WIRE if words is not None else 0)
        before = bytes(self.wire)
        result = self.call('complete', [ticket, error, pointer, length], [ticket, error, address, length])
        assert bytes(self.wire) == before
        return result

    def abort(self):
        self.call('abort', [], [], void=True)

    def force_serial(self, value):
        self.state[4] = value
        self.cpu.mem_write(STATE + 16, struct.pack('<I', value))


class Coordinator(firmware.Coordinator):
    calls = 0

    def __init__(self, paths, boot=BOOT):
        super().__init__(paths[2])
        self.lib = ctypes.CDLL(str(paths[0]))
        assert self.barrier.symbols['npu_emulation_control_v2_state'] == SESSION
        assert self.barrier.symbols['npu_emulation_control_v2_boot'] == LOADER
        self.cpu.mem_write(LOADER, struct.pack('<2I', *boot))
        # Test loader seed before any message or modeled worker activity.
        self.call('e:admission_init')

    def message(self, words, **kwargs):
        session = (ctypes.c_uint32 * 5).from_buffer_copy(self.cpu.mem_read(SESSION, 20))
        admission = (ctypes.c_uint32 * 11).from_buffer_copy(self.cpu.mem_read(firmware.ADM, 44))
        barrier = (ctypes.c_uint32 * 26).from_buffer_copy(self.cpu.mem_read(firmware.STATE, 104))
        packet = (ctypes.c_uint32 * 20)(*words)
        function = self.lib.npu_control_v2_dispatch
        function.restype = ctypes.c_int
        handled = function(session, admission, barrier, packet, kwargs.get('length', len(words) * 4))
        result = super().message(words, **kwargs)
        if handled:
            assert result['flags'] == 7
            assert result['words'] == list(packet)
            assert self.cpu.mem_read(SESSION, 20) == bytes(session)
            assert self.cpu.mem_read(firmware.ADM, 44) == bytes(admission)
            assert self.cpu.mem_read(firmware.STATE, 104) == bytes(barrier)
            Coordinator.calls += 1
        return result


def exchange(host, coordinator):
    ticket, words = host.request()
    assert ticket and words[:5] == [0x3f, 0, 0x3243514e, 2, 80]
    assert words[16] == ticket and words[19] == 0
    row = coordinator.message(words)
    result = host.complete(ticket, row['words'], error=0 if row['flags'] == 7 else -22)
    return result, words, row['words']


def advance(host, coordinator, phase=STOPPING):
    while host.state[0] != phase:
        assert host.state[0] < phase
        assert exchange(host, coordinator)[0] == ACCEPTED


def parked(coordinator):
    for hart in range(1, 8):
        assert coordinator.call('b:poll', hart) == 0
    coordinator.run_idle()


def released(coordinator, partial=False):
    parked(coordinator)
    epoch = coordinator.barrier.snapshot()[0]
    for domain in range(5):
        assert coordinator.call('b:record_drain', domain, epoch) == 1
    assert coordinator.call('b:prepare', epoch) == 1
    assert coordinator.call('b:release', epoch) == 1
    if not partial:
        for hart in range(1, 8):
            assert coordinator.call('b:refreshed', hart, epoch) == 1
        coordinator.run_idle()
        assert coordinator.call('b:arm', epoch) == 1
        assert coordinator.call('e:open') == 1


def held(host):
    assert host.state[0] == FAILED and host.state[5] == 0
    before = tuple(host.state)
    assert host.complete(host.state[4], poison=True) == IGNORED
    assert host.request()[0] == 0
    host.abort()
    assert tuple(host.state) == before


def cases(paths):
    rows = []
    for mode in ('cold', 'running', 'partial-release'):
        c, h = Coordinator(paths), Host(paths)
        if mode != 'cold':
            released(c, partial=mode == 'partial-release')
        advance(h, c)
        assert h.state[7] == (1 if mode == 'cold' else 2)
        parked(c)
        assert exchange(h, c)[0] == ACCEPTED and h.state[0] == PARKED
        assert h.state[12] == 0 and c.call('b:reclaimable', h.state[7]) == 0
        rows.append(dict(case=mode, client=list(h.state)))

    c, h = Coordinator(paths), Host(paths)
    advance(h, c)
    parked(c)
    _, _, old_reply = exchange(h, c)
    ticket, _ = h.request()
    c.call('a:fail')
    assert h.complete(ticket, old_reply) == REJECTED and h.state[16] == 3
    held(h)
    rows.append(dict(case='stale-wire-reply-new-ticket', rejected=True))

    for same_identity in (False, True):
        c, h = Coordinator(paths), Host(paths)
        advance(h, c)
        replacement = Coordinator(paths, boot=BOOT if same_identity else OTHER_BOOT)
        result, _, response = exchange(h, replacement)
        assert result == REJECTED and response[9] == (2 if same_identity else 7)
        assert replacement.get32(firmware.ADM + 12) == 0
        held(h)
        rows.append(dict(case='replacement-provider', same_boot_identity=same_identity,
                         status=response[9]))

    c, h = Coordinator(paths), Host(paths)
    advance(h, c, DISCOVERED)
    _, old_bind, _ = exchange(h, c)
    replacement = Coordinator(paths, OTHER_BOOT)
    before = bytes(replacement.cpu.mem_read(SESSION, 20))
    response = replacement.message(old_bind)['words']
    assert response[9] == 7 and replacement.cpu.mem_read(SESSION, 20) == before
    rows.append(dict(case='old-bind-new-boot', status=response[9]))

    c, h = Coordinator(paths), Host(paths)
    released(c)
    assert c.call('a:begin_legacy') == 1
    advance(h, c, DISCOVERED)
    result, failed_bind, response = exchange(h, c)
    assert result == REJECTED and response[9] == 5
    c.call('a:leave')
    replay = c.message(failed_bind)['words']
    assert replay[9] == 8 and c.get32(firmware.ADM + 12) == 0
    held(h)
    rows.append(dict(case='abandoned-busy-bind', duplicate_status=replay[9], bound=False))

    c, h = Coordinator(paths), Host(paths)
    advance(h, c)
    _, _, response = exchange(h, c)
    ticket, status = h.request()
    for sequence in (1, 2, status[16] - 1):
        request = status.copy()
        request[16] = sequence
        assert c.message(request)['words'][9] == 8
    assert h.complete(ticket, c.message(status)['words']) == ACCEPTED
    h.force_serial(0xfffffffe)
    assert exchange(h, c)[0] == ACCEPTED
    assert c.get32(SESSION + 16) == 0xffffffff
    assert h.request()[0] == 0 and h.state[1] == v1.EXHAUSTED
    held(h)
    rows.append(dict(case='sequence-order-and-exhaustion', last_sequence=0xffffffff))

    for phase in (v1.NEW, DISCOVERED, BOUND, STOPPING):
        for deliver in (False, True):
            c, h = Coordinator(paths), Host(paths)
            advance(h, c, phase)
            ticket, request = h.request()
            early = c.message(request) if deliver else None
            assert h.complete(ticket, poison=True, error=-110) == REJECTED
            response = early or c.message(request)
            assert h.complete(ticket, response['words']) == IGNORED
            held(h)
            rows.append(dict(case='timeout', phase=phase, delivered=deliver))

    c, h = Coordinator(paths, (0, 0)), Host(paths)
    assert exchange(h, c)[0] == REJECTED
    held(h)
    rows.append(dict(case='no-loader-identity', rejected=True))

    h = Host(paths)
    ticket, request = h.request()
    original = firmware.Mailbox().message(request)
    assert original['flags'] == 7 and original['words'][2] == 0
    assert original['words'][3:] == request[3:]
    assert h.complete(ticket, original['words']) == REJECTED
    held(h)
    rows.append(dict(case='original-firmware-v2-probe', mailbox_flags=7, reply_magic=0))

    v1_path = firmware.build_platform()
    for running in (False, True):
        older, h = firmware.Coordinator(v1_path), Host(paths)
        if running:
            older.running()
        ticket, request = h.request()
        before = older.barrier.snapshot()
        response = older.message(request)
        assert older.barrier.snapshot() == before
        assert response['flags'] == (7 if running else 3)
        if running:
            assert response['words'][2] == 0 and response['words'][3:] == request[3:]
        else:
            assert response['words'] == request
        assert h.complete(ticket, response['words'], error=0 if running else -22) == REJECTED
        held(h)
        rows.append(dict(case='v1-endpoint-v2-probe', running=running,
                         mailbox_flags=response['flags'], barrier_unchanged=True))
    return rows


def malformed(paths):
    rows = []
    mutations = {0: (0, 0xffffffff), 1: (1,), 2: (0, 0x3152514e), 3: (1, 3),
                 4: (64, 81), 5: (0, 2, 4), 6: (0, 2), 7: (0,), 8: (0,),
                 9: (1, 6, 8), 10: (7, 47, 55, 63), 11: (256,), 12: (1,),
                 13: (1, 32), 14: (1,), 15: (1,), 16: (0, 1, 0xffffffff),
                 17: (0, BOOT[0] ^ 1), 18: (0, BOOT[1] ^ 1), 19: (1, 0xffffffff)}
    for field, values in mutations.items():
        for value in values:
            c, h = Coordinator(paths), Host(paths)
            advance(h, c)
            ticket, request = h.request()
            response = c.message(request)['words']
            response[field] = value
            assert h.complete(ticket, response) == REJECTED, (field, value)
            held(h)
            rows.append(dict(kind='reply', field=field, value=value))
    for field, value in ((3, 1), (4, 64), (16, 0), (19, 1), (7, 0)):
        c, h = Coordinator(paths), Host(paths)
        _, request = h.request()
        request[field] = value
        if field == 7:
            request[8] = 0
        before = bytes(c.cpu.mem_read(SESSION, 20))
        response = c.message(request)['words']
        assert response[9] == 1
        assert c.cpu.mem_read(SESSION, 20) == before
        rows.append(dict(kind='request', field=field, value=value))
    for length in (0, 1, 63, 64, 79, 81, 256, 0xffffffff):
        h = Host(paths)
        assert h.request(length=length)[0] == 0
        held(h)
        h = Host(paths)
        t, _ = h.request()
        assert h.complete(t, poison=True, length=length) == REJECTED
        held(h)
        rows.append(dict(kind='length', bytes=length))
    return rows


def shared_workers(paths):
    c, host = Coordinator(paths), Host(paths)
    worker = firmware.Worker(paths[2], 1)
    worker.cpu, worker.barrier = c.cpu, c.barrier
    worker.fixture()
    c.phase = worker.phase = 'v2-cold-stop'
    for address, (hart, kind, preimage, *_) in firmware.WORKER_SITES.items():
        assert bytes(c.cpu.mem_read(address, 4)).hex() == preimage
        c.cpu.mem_write(address, firmware.jump(address, c.barrier.symbols[f'gate_core{hart}_{kind}']))
    for address, (symbol, preimage) in firmware.CORE5_SITES.items():
        assert bytes(c.cpu.mem_read(address, 4)).hex() == preimage
        c.cpu.mem_write(address, firmware.jump(address, c.barrier.symbols[symbol]))
    for address in {*firmware.WORKER_SITES, *firmware.CORE5_SITES, *firmware.HELPERS}:
        c.cpu.hook_add(UC_HOOK_CODE, worker.worker_hook, begin=address, end=address)
    advance(host, c)
    initial, contexts, masks = c.cpu.context_save(), {}, []
    order = (5, 2, 7, 1, 6, 4, 3)
    for index, hart in enumerate(order):
        c.cpu.context_restore(initial)
        c.hart = worker.hart = hart
        c.cpu.reg_write(rv.UC_RISCV_REG_SP, 0x84021e00 + hart * 0x4000)
        c.cpu.reg_write(rv.UC_RISCV_REG_MSTATUS, 8)
        worker.execute({**firmware.ENTRIES, 5: 0x8400cb0e}[hart], count=60000)
        contexts[hart] = c.cpu.context_save()
        assert not c.cpu.reg_read(rv.UC_RISCV_REG_MSTATUS) & 8
        c.hart = 0
        result, _, response = exchange(host, c)
        assert result == ACCEPTED and host.state[0] == STOPPING
        assert response[11] == sum(1 << owner for owner in order[:index + 1])
        masks.append(response[11])
    c.run_idle()
    assert exchange(host, c)[0] == ACCEPTED and host.state[0] == PARKED
    assert c.call('b:reclaimable', 1) == 0
    return dict(saved_contexts=len(contexts) + 1, round_trips=11, masks=masks + [255],
                epoch=1, drain_mask=host.state[12], host=list(host.state),
                scope='Cold worker entry/IRQ adapters on shared modeled SRAM; helper returns/MMIO/IRQ invocation are modeled, not full reset-to-postgate boot or physical quiescence.')


def mutation_cases():
    rows = []
    specifications = [
        ('host-sequence', HOST, 'read_word(reply, 16) != ticket', '0'),
        ('host-boot', HOST, 'boot_lo != s->boot_lo || boot_hi != s->boot_hi', '0'),
        ('host-capability', HOST, 'read_word(reply, 10) != NPU_CONTROL_V2_CAPS', '0'),
        ('server-sequence', SERVER, 'p->sequence <= s->last_sequence', '0'),
        ('server-boot', SERVER, 'p->boot_lo != s->boot_lo || p->boot_hi != s->boot_hi', '0'),
        ('status-binding', SERVER, 'a->nonce_lo != s->nonce_lo || a->nonce_hi != s->nonce_hi', '0'),
    ]
    for name, source, old, new in specifications:
        text = source.read_text()
        assert text.count(old) == 1
        mutant = BUILD / (name + '.c')
        mutant.write_text(text.replace(old, new))
        paths = build(host=mutant if source == HOST else HOST,
                      server=mutant if source == SERVER else SERVER, tag=name)
        c, h = Coordinator(paths), Host(paths)
        if name == 'server-sequence':
            released(c)
            c.call('a:begin_legacy')
            advance(h, c, DISCOVERED)
            _, request, _ = exchange(h, c)
            c.call('a:leave')
            response = c.message(request)['words']
            caught = response[9] != 8 and c.get32(firmware.ADM + 12) != 0
        elif name == 'server-boot':
            advance(h, c, DISCOVERED)
            _, request = h.request()
            request[17] ^= 1
            response = c.message(request)['words']
            caught = response[9] == 0
        else:
            advance(h, c)
            if name == 'status-binding':
                c.put32(firmware.ADM + 12, 0)
                c.put32(firmware.ADM + 16, 0)
                caught = exchange(h, c)[0] == ACCEPTED
            else:
                ticket, request = h.request()
                response = c.message(request)['words']
                if name == 'host-sequence':
                    response[16] -= 1
                elif name == 'host-boot':
                    response[17] ^= 1
                else:
                    response[10] |= 8
                caught = h.complete(ticket, response) == ACCEPTED
        assert caught, ('undetected mutant', name)
        rows.append(dict(name=name, detected=True, source_sha256=sha(mutant),
                         binaries={str(p.relative_to(ROOT)): sha(p) for p in paths}))
    return rows


def reused_identity_control(paths):
    c, h = Coordinator(paths), Host(paths)
    advance(h, c, DISCOVERED)
    _, old_bind, _ = exchange(h, c)
    assert exchange(h, c)[0] == ACCEPTED
    # The platform violates the fresh-boot contract and also replays an old BIND.
    replacement = Coordinator(paths, BOOT)
    assert replacement.message(old_bind)['words'][9] == 0
    parked(replacement)
    assert exchange(h, replacement)[0] == ACCEPTED and h.state[0] == PARKED
    return dict(reused_boot_plus_replayed_bind_detected=False,
                scope='Deliberate loader/transport contract violation: boot identities must never repeat; not proof of a fresh loader or physical provider identity.')


def main():
    original = v1.inputs()
    tracked = [HOST, SERVER, SOURCE / 'control-v2.h', PLATFORM, Path(__file__),
               SOURCE / 'CONTROL_V2_CONTRACT.md']
    before = {str(p.relative_to(ROOT)): sha(p) for p in tracked}
    paths = build()
    normal = cases(paths)
    invalid = malformed(paths)
    shared = shared_workers(paths)
    limits = reused_identity_control(paths)
    mutants = mutation_cases()
    for source in (HOST, SERVER):
        execute([shutil.which('clang'), '--analyze', '-std=c11', '-Wall', '-Wextra', '-Werror',
                 '-I', SOURCE, source, '-o', BUILD / (source.stem + '-analyze.plist')])
    assert original == v1.inputs(), 'V1/source-lock inputs changed'
    assert before == {str(p.relative_to(ROOT)): sha(p) for p in tracked}
    report = dict(passed=True, host_differential_calls=Host.calls, server_differential_calls=Coordinator.calls,
                  cases=normal, malformed=invalid, shared_workers=shared, limit_control=limits,
                  mutations=mutants, inputs={**original, **before},
                  binaries={str(p.relative_to(ROOT)): sha(p) for p in paths},
                  compiler=execute([shutil.which('clang'), '--version']).splitlines()[0],
                  unicorn_version=unicorn.__version__, static_analyzer='passed without diagnostics',
                  stock_firmware_sha256=firmware.CODE_SHA, stock_data_sha256=firmware.DATA_SHA,
                  scope='Unpromoted V2 identity protocol on x86/AArch64 host code and x86/RV32 server code with actual strict mailbox and eight saved worker contexts. Loader identity/MMIO/cache/interrupt invocation/scheduling/drains are modeled. No complete loader/Linux recovery/physical containment or router validation.')
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / 'control-v2.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=True, host_calls=Host.calls, server_calls=Coordinator.calls,
                         cases=len(normal), malformed=len(invalid), shared=shared['saved_contexts'],
                         mutations=len(mutants), evidence_sha256=sha(output))))


if __name__ == '__main__':
    main()
