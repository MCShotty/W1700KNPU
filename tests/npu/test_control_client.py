#!/usr/bin/env python3
"""Actual x86/AArch64 client code and RV32 mailbox/worker round trips."""
import ctypes
import hashlib
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
from unicorn import arm64_const as a64
from unicorn import riscv_const as r
import unicorn
import test_admission_native as firmware
from test_firmware_mailbox_dispatch import Mailbox

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / '.local/npu-control-client'
OUT = ROOT / 'research/checkpoints/2026-09-14-npu-control-client'
SOURCE = ROOT / 'firmware/npu/control-client.c'
LINKER = ROOT / 'tests/npu/control-client-emulation.ld'
SANITIZER = ROOT / 'tests/npu/control-client-sanitize.c'
STATE, BUFFER, STACK, END = 0x200000, 0x201001, 0x210000, 0x300000
NONCE = (0x31415926, 0x27182818)
NEW, DISCOVERED, BOUND, STOPPING, PARKED, FAILED = range(6)
IGNORED, ACCEPTED, REJECTED = range(3)
ARGUMENT, TRANSPORT, ENVELOPE, CAPABILITY, REMOTE, GENERATION, SNAPSHOT, EXHAUSTED = range(1, 9)
ABORTED = 9


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command):
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr, result.stderr
    return result.stdout


def build(source=SOURCE, tag='client'):
    BUILD.mkdir(parents=True, exist_ok=True)
    common = [shutil.which('clang'), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
              '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-I', SOURCE.parent, source]
    native, arm = BUILD / (tag + '.so'), BUILD / (tag + '.elf')
    execute([*common, '-shared', '-fPIC', '-o', native])
    lld = shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'
    execute([*common, '--target=aarch64-none-elf', '-mgeneral-regs-only', '-nostdlib',
             f'--ld-path={lld}', f'-Wl,-T,{LINKER}', '-o', arm])
    return native, arm


class Pair:
    """Same helper on x86 and AArch64, with byte-identical state and wire I/O."""
    total = 0

    def __init__(self, paths, nonce=NONCE):
        self.lib = ctypes.CDLL(str(paths[0]))
        self.state = (ctypes.c_uint32 * 14)()
        self.wire = (ctypes.c_ubyte * 66)()
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
        self.invoke('init', [*nonce], [*nonce], void=True)

    def snapshot(self):
        return tuple(self.state)

    def force(self, index, value):
        self.state[index] = value
        self.cpu.mem_write(STATE + index * 4, struct.pack('<I', value))

    def invoke(self, name, native, arm, void=False):
        fn = getattr(self.lib, 'npu_client_' + name)
        fn.restype = None if void else ctypes.c_uint32
        result = fn(self.state, *native)
        self.cpu.reg_write(a64.UC_ARM64_REG_SP, STACK)
        self.cpu.reg_write(a64.UC_ARM64_REG_LR, END)
        saved = {register: 0x1234567800000000 + i for i, register in enumerate(
                 [getattr(a64, 'UC_ARM64_REG_X' + str(i)) for i in range(19, 30)])}
        for register, value in saved.items():
            self.cpu.reg_write(register, value)
        for i, value in enumerate([STATE, *arm]):
            self.cpu.reg_write(getattr(a64, 'UC_ARM64_REG_X' + str(i)), value & 0xffffffffffffffff)
        self.cpu.emu_start(self.symbols['npu_client_' + name], END, timeout=1000000, count=20000)
        assert self.cpu.reg_read(a64.UC_ARM64_REG_PC) == END, name
        assert self.cpu.reg_read(a64.UC_ARM64_REG_SP) == STACK, name
        assert all(self.cpu.reg_read(reg) == value for reg, value in saved.items()), name
        actual = None if void else self.cpu.reg_read(a64.UC_ARM64_REG_W0)
        assert actual == result, (name, actual, result)
        assert self.cpu.mem_read(STATE, 56) == bytes(self.state), name
        assert self.cpu.mem_read(BUFFER - 1, 66) == bytes(self.wire), name
        Pair.total += 1
        return result

    def request(self, length=64, pointer=True):
        self.wire[:] = [0xa5] * 66
        self.cpu.mem_write(BUFFER - 1, bytes(self.wire))
        ticket = self.invoke('request', [ctypes.byref(self.wire, 1) if pointer else None, length],
                             [BUFFER if pointer else 0, length])
        assert self.wire[0] == self.wire[65] == 0xa5
        return ticket, list(struct.unpack('<16I', bytes(self.wire)[1:65]))

    def complete(self, ticket, words=None, error=0, length=64, poison=False):
        if words is not None:
            self.wire[:] = b'\xa5' + struct.pack('<16I', *words) + b'\xa5'
            self.cpu.mem_write(BUFFER - 1, bytes(self.wire))
        pointer = ctypes.c_void_p(1) if poison else (ctypes.byref(self.wire, 1) if words is not None else None)
        address = 1 if poison else (BUFFER if words is not None else 0)
        before = bytes(self.wire)
        result = self.invoke('complete', [ticket, error, pointer, length],
                             [ticket, error, address, length])
        assert bytes(self.wire) == before, 'completion modified transport storage'
        return result


def reply(words, epoch=None, parked=0, ready=0, drained=0, released=0, armed=0):
    output = words.copy()
    output[2] = 0x3152514e
    output[6] = epoch if epoch is not None else (words[6] or 1)
    output[9:] = [0, 7, parked, ready, drained, released, armed]
    return output


def advance(pair, phase=STOPPING, running=False, epoch=1):
    for _ in range(3):
        if pair.state[0] == phase:
            break
        ticket, words = pair.request()
        assert ticket and words[:6] == [0x3f, 0, 0x3143514e, 1, 64, ticket - 1]
        assert words[7:9] == list(NONCE) and words[9:] == [0] * 7
        stop = words[5] == 2
        response = reply(words, epoch=epoch + int(stop and running),
                         released=epoch if running else 0, armed=epoch if running else 0,
                         parked=0xff if running and not stop else 0,
                         ready=0xff if running and not stop else 0,
                         drained=0x1f if running and not stop else 0)
        assert pair.complete(ticket, response) == ACCEPTED
    assert pair.state[0] == phase


def assert_failed(pair, error):
    assert pair.state[0] == FAILED and pair.state[1] == error and pair.state[5] == 0
    old = pair.snapshot()
    assert pair.request()[0] == 0
    assert pair.complete(old[4], poison=True) == IGNORED
    pair.invoke('abort', [], [], void=True)
    assert pair.snapshot() == old, 'failure was not sticky'


def protocol_cases(paths):
    counts = dict(mask_snapshots=0, malformed=0, transport=0, ordering=0, boundaries=0, aborts=0)
    for running in (False, True):
        for parked in range(256):
            p = Pair(paths)
            advance(p, running=running)
            t, w = p.request()
            assert p.complete(t, reply(w, parked=parked, released=int(running),
                                        armed=int(running))) == ACCEPTED
            assert p.state[0] == (PARKED if parked == 255 else STOPPING)
            counts['mask_snapshots'] += 1
    for drained in range(32):
        p = Pair(paths)
        advance(p)
        t, w = p.request()
        assert p.complete(t, reply(w, parked=255, drained=drained)) == ACCEPTED
        assert p.state[0] == PARKED and p.state[13] == 7
        counts['mask_snapshots'] += 1

    fields = {0: (0, 0x3e, 0xffffffff), 1: (1, 0xffffffff),
              2: (0, 0x3143514e, 0xffffffff), 3: (0, 2, 0xffffffff),
              4: (0, 63, 65, 256), 5: (0, 1, 2, 4, 0xffffffff),
              6: (0, 2, 0xffffffff), 7: (0, NONCE[0] ^ 1), 8: (0, NONCE[1] ^ 1),
              9: (1, 2, 3, 4, 5, 6, 0xffffffff),
              10: (0, 1, 3, 6, 15, 23, 31, 0xffffffff),
              11: (256, 0xffffffff), 12: (1, 255, 256, 0xffffffff),
              13: (1, 31, 32, 0xffffffff), 14: (1, 2, 0xffffffff), 15: (1, 2, 0xffffffff)}
    for field, values in fields.items():
        for value in values:
            p = Pair(paths)
            advance(p)
            t, w = p.request()
            out = reply(w)
            out[field] = value
            expected = (ENVELOPE if field in (0, 1, 2, 3, 4, 5, 7, 8) else
                        REMOTE if field == 9 else CAPABILITY if field == 10 else
                        GENERATION if field == 6 else SNAPSHOT)
            assert p.complete(t, out) == REJECTED, ('field', field, value)
            assert_failed(p, expected)
            counts['malformed'] += 1

    for phase in (NEW, DISCOVERED, BOUND, STOPPING, PARKED):
        for error in (-110, -19, -5, 1, 7):
            p = Pair(paths)
            advance(p, min(phase, STOPPING))
            if phase == PARKED:
                t, w = p.request()
                assert p.complete(t, reply(w, parked=255)) == ACCEPTED
            t, w = p.request()
            assert p.complete(t, poison=True, error=error) == REJECTED
            assert_failed(p, TRANSPORT)
            counts['transport'] += 1
        p = Pair(paths)
        advance(p, min(phase, STOPPING))
        if phase == PARKED:
            t, w = p.request()
            assert p.complete(t, reply(w, parked=255)) == ACCEPTED
        t, w = p.request()
        before = p.snapshot()
        assert p.request()[0] == 0 and p.snapshot() == before
        for old in (0, t + 1, 0xffffffff):
            assert p.complete(old, reply(w)) == IGNORED
            assert p.snapshot() == before
            counts['ordering'] += 1
        assert p.complete(t, reply(w, parked=255 if phase == PARKED else 0)) == ACCEPTED
        before = p.snapshot()
        assert p.complete(t, poison=True) == IGNORED and p.snapshot() == before

        for pending in (False, True):
            p = Pair(paths)
            advance(p, min(phase, STOPPING))
            if phase == PARKED:
                t, w = p.request()
                assert p.complete(t, reply(w, parked=255)) == ACCEPTED
            if pending:
                p.request()
            p.invoke('abort', [], [], void=True)
            assert_failed(p, ABORTED)
            counts['aborts'] += 1

    for length in (0, 1, 4, 8, 60, 63, 65, 256, 0xffffffff):
        p = Pair(paths)
        assert p.request(length=length)[0] == 0
        assert_failed(p, ARGUMENT)
        p = Pair(paths)
        t, _ = p.request()
        assert p.complete(t, poison=True, length=length) == REJECTED
        assert_failed(p, ARGUMENT)
        counts['boundaries'] += 2
    p = Pair(paths, nonce=(0, 0))
    assert_failed(p, ARGUMENT)
    p = Pair(paths)
    p.force(4, 0xffffffff)
    assert p.request()[0] == 0
    assert_failed(p, EXHAUSTED)
    p = Pair(paths)
    advance(p, BOUND, running=True, epoch=0xffffffff)
    assert p.request()[0] == 0
    assert_failed(p, EXHAUSTED)
    p = Pair(paths)
    advance(p, epoch=0xffffffff)
    assert p.state[7] == 0xffffffff and p.state[0] == STOPPING
    counts['boundaries'] += 4
    p = Pair(paths)
    assert p.request(pointer=False)[0] == 0
    assert_failed(p, ARGUMENT)
    p = Pair(paths)
    t, _ = p.request()
    assert p.complete(t) == REJECTED
    assert_failed(p, ARGUMENT)
    counts['boundaries'] += 2

    # Snapshots cannot lose same-generation ACKs, drains or release history.
    for field, initial, changed in ((11, 3, 1), (13, 3, 1), (14, 1, 0), (15, 1, 0)):
        p = Pair(paths)
        advance(p, running=True)
        t, w = p.request()
        initial_reply = reply(w, parked=255 if field == 13 else 3,
                              drained=initial if field == 13 else 0, released=1, armed=1)
        assert p.complete(t, initial_reply) == ACCEPTED
        t, w = p.request()
        bad = reply(w, parked=initial_reply[11], drained=initial_reply[13], released=1, armed=1)
        bad[field] = changed
        assert p.complete(t, bad) == REJECTED
        assert_failed(p, SNAPSHOT)
        counts['ordering'] += 1
    return counts


def exchange(pair, coordinator):
    t, words = pair.request()
    assert t and words[0:2] == [0x3f, 0] and words[5] in range(4)
    before = coordinator.barrier.snapshot()
    row = coordinator.message(words)
    assert row['flags'] == 7
    result = pair.complete(t, row['words'])
    assert coordinator.barrier.snapshot()[1:5] == before[1:5], 'wire operation changed release/arm/fault'
    return result, row['words']


def shared_workers(paths, firmware_path):
    coordinator = firmware.Coordinator(firmware_path)
    workers = firmware.Worker(firmware_path, 1)
    workers.cpu, workers.barrier = coordinator.cpu, coordinator.barrier
    workers.fixture()
    coordinator.phase = workers.phase = 'host-client-eight-contexts'
    for address, (hart, kind, preimage, *_) in firmware.WORKER_SITES.items():
        assert bytes(coordinator.cpu.mem_read(address, 4)).hex() == preimage
        coordinator.cpu.mem_write(address, firmware.jump(address, coordinator.barrier.symbols[f'gate_core{hart}_{kind}']))
    for address, (symbol, preimage) in firmware.CORE5_SITES.items():
        assert bytes(coordinator.cpu.mem_read(address, 4)).hex() == preimage
        coordinator.cpu.mem_write(address, firmware.jump(address, coordinator.barrier.symbols[symbol]))
    for address in {*firmware.WORKER_SITES, *firmware.CORE5_SITES, *firmware.HELPERS}:
        coordinator.cpu.hook_add(UC_HOOK_CODE, workers.worker_hook, begin=address, end=address)
    initial, contexts = coordinator.cpu.context_save(), {}
    for hart in range(1, 8):
        coordinator.cpu.context_restore(initial)
        coordinator.hart = workers.hart = hart
        coordinator.cpu.reg_write(r.UC_RISCV_REG_SP, 0x84021e00 + hart * 0x4000)
        coordinator.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
        workers.execute({**firmware.ENTRIES, 5: 0x8400cb0e}[hart], count=60000)
        contexts[hart] = coordinator.cpu.context_save()
    coordinator.hart = 0
    coordinator.run_idle()
    # These are explicitly modeled platform witnesses for the initial run only.
    for domain in range(5):
        assert coordinator.call('b:record_drain', domain, 1) == 1
    assert coordinator.call('b:prepare', 1) == 1
    assert coordinator.call('b:release', 1) == 1
    for hart in range(1, 8):
        coordinator.hart = workers.hart = hart
        coordinator.cpu.context_restore(contexts[hart])
        workers.execute()
        contexts[hart] = coordinator.cpu.context_save()
    coordinator.hart = 0
    coordinator.run_idle()
    assert coordinator.call('b:arm', 1) == 1
    assert coordinator.call('e:open') == 1
    for hart in range(1, 8):
        coordinator.hart = workers.hart = hart
        coordinator.cpu.context_restore(contexts[hart])
        workers.until({**firmware.OUTER, 5: 0x8400cbbe}[hart])
        contexts[hart] = coordinator.cpu.context_save()
    coordinator.hart = 0
    host = Pair(paths)
    rows = []
    for _ in range(3):
        result, row = exchange(host, coordinator)
        assert result == ACCEPTED
        rows.append(row)
    assert host.state[7] == 2 and host.state[0] == STOPPING
    order = [5, 2, 7, 1, 6, 4, 3]
    for index, hart in enumerate(order):
        coordinator.hart = workers.hart = hart
        coordinator.cpu.context_restore(contexts[hart])
        workers.execute()
        contexts[hart] = coordinator.cpu.context_save()
        assert not coordinator.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        coordinator.hart = 0
        result, row = exchange(host, coordinator)
        assert result == ACCEPTED and host.state[0] == STOPPING
        assert row[11] == sum(1 << h for h in order[:index + 1])
        rows.append(row)
    coordinator.run_idle()
    result, row = exchange(host, coordinator)
    assert result == ACCEPTED and host.state[0] == PARKED
    assert row[11:14] == [255, 0, 0]
    assert coordinator.call('b:reclaimable', 2) == 0
    rows.append(row)
    return dict(round_trips=len(rows), worker_order=order, replies=rows,
                final_client=list(host.snapshot()), physical_drain_witnesses=0,
                reclaimable=False, saved_rv32_contexts=8)


def firmware_cases(paths, fwpath):
    rows = []
    for running in (False, True):
        c = firmware.Coordinator(fwpath)
        if running:
            c.running()
        p = Pair(paths)
        for _ in range(3):
            assert exchange(p, c)[0] == ACCEPTED
        expected = 2 if running else 1
        assert p.state[7] == expected
        # Actual barrier C, but worker boundaries are modeled in these cases.
        for hart in range(1, 8):
            assert c.call('b:poll', hart) == 0
        assert exchange(p, c)[0] == ACCEPTED and p.state[0] == STOPPING
        c.run_idle()
        assert exchange(p, c)[0] == ACCEPTED and p.state[0] == PARKED
        for domain in range(5):
            assert c.call('b:record_drain', domain, expected) == 1
        assert exchange(p, c)[0] == ACCEPTED and p.state[12:14] == [31, 7]
        # Even synthetic full drain reports cannot enable host reclamation.
        rows.append(dict(case='running' if running else 'cold', final_client=list(p.snapshot())))

    for when in (0, 1, 2, 3):
        c, p = firmware.Coordinator(fwpath), Pair(paths)
        for _ in range(when):
            assert exchange(p, c)[0] == ACCEPTED
        c.call('a:fail')
        result, row = exchange(p, c)
        if when == 0:  # V1 discovery deliberately remains diagnostic while faulted.
            assert result == ACCEPTED
            result, row = exchange(p, c)
        assert result == REJECTED and row[9] == 6
        assert_failed(p, REMOTE)
        rows.append(dict(case='remote-fault', stage=when, status=row[9]))

    c, p = firmware.Coordinator(fwpath), Pair(paths)
    c.control_message(1, 1, (9, 8))
    assert exchange(p, c)[0] == ACCEPTED
    result, row = exchange(p, c)
    assert result == REJECTED and row[9] == 2
    assert_failed(p, REMOTE)
    rows.append(dict(case='another-session', status=row[9]))

    c, p = firmware.Coordinator(fwpath), Pair(paths)
    c.running()
    assert c.call('a:begin_legacy') == 1
    assert exchange(p, c)[0] == ACCEPTED
    result, row = exchange(p, c)
    assert result == REJECTED and row[9] == 5
    assert_failed(p, REMOTE)
    rows.append(dict(case='active-handler-bind', status=row[9]))

    c, p = firmware.Coordinator(fwpath), Pair(paths)
    c.running()
    for _ in range(2):
        assert exchange(p, c)[0] == ACCEPTED
    assert c.call('a:close') == 2
    result, row = exchange(p, c)
    assert result == REJECTED and row[9] == 3
    assert_failed(p, REMOTE)
    rows.append(dict(case='external-epoch-change', status=row[9]))

    # Timeout may be before or after real firmware processing. Both retain.
    for delivered in (False, True):
        c, p = firmware.Coordinator(fwpath), Pair(paths)
        c.running()
        for _ in range(2):
            assert exchange(p, c)[0] == ACCEPTED
        t, words = p.request()
        early = c.message(words) if delivered else None
        assert p.complete(t, poison=True, error=-110) == REJECTED
        before = p.snapshot()
        late = early or c.message(words)
        assert c.barrier.snapshot()[0] == 2
        assert p.complete(t, late['words']) == IGNORED and p.snapshot() == before
        assert_failed(p, TRANSPORT)
        rows.append(dict(case='timeout', delivered_before_timeout=delivered,
                         firmware_epoch=2, host_phase=FAILED))

    p = Pair(paths)
    t, words = p.request()
    legacy = Mailbox().message(words)
    assert legacy['flags'] == 7 and legacy['words'][2] == 0
    assert p.complete(t, legacy['words']) == REJECTED
    assert_failed(p, ENVELOPE)
    rows.append(dict(case='unmodified-firmware-probe', mailbox_flags=7, reply_magic=0))
    return rows


def wire_limit_controls(paths, fwpath):
    c, p = firmware.Coordinator(fwpath), Pair(paths)
    for _ in range(3):
        assert exchange(p, c)[0] == ACCEPTED
    for hart in range(1, 8):
        assert c.call('b:poll', hart) == 0
    c.run_idle()
    assert exchange(p, c)[0] == ACCEPTED and p.state[0] == PARKED
    t, w = p.request()
    saved = c.message(w)['words']
    assert p.complete(t, saved) == ACCEPTED
    t, _ = p.request()
    c.call('a:fail')
    # Supplying the current local ticket with old wire bytes is a transport
    # contract violation that V1's echoed operation/nonce cannot detect.
    assert p.complete(t, saved) == ACCEPTED and p.state[0] == PARKED
    assert c.call('b:reclaimable', 1) == 0

    old, host = firmware.Coordinator(fwpath), Pair(paths)
    for _ in range(3):
        assert exchange(host, old)[0] == ACCEPTED
    replacement = firmware.Coordinator(fwpath)
    assert replacement.get32(firmware.ADM + 12) == 0
    assert replacement.get32(firmware.ADM + 16) == 0
    assert exchange(host, replacement)[0] == ACCEPTED
    for hart in range(1, 8):
        assert replacement.call('b:poll', hart) == 0
    replacement.run_idle()
    assert exchange(host, replacement)[0] == ACCEPTED and host.state[0] == PARKED
    assert replacement.get32(firmware.ADM + 12) == 0
    assert replacement.get32(firmware.ADM + 16) == 0
    assert host.state[13] == 7
    return dict(same_epoch_wire_replay_with_new_local_ticket_detected=False,
                replacement_provider_from_status_echo_detected=False,
                safe_reclaim_capability=False, restart_capability=False,
                scope='Deliberate contract-violation controls, not observed provider behavior. Client tickets require exact provider/transfer association; V1 STATUS echoes the request nonce without validating a bound session.')


def mutation_cases():
    text = SOURCE.read_text()
    mutations = [
        ('ticket', 'ticket != s->pending', '0'),
        ('transport', 'if (transport_error)', 'if (0 && transport_error)'),
        ('magic', 'read_word(reply, 2) != NPU_CONTROL_REPLY', '0'),
        ('nonce', 'read_word(reply, 7) != s->nonce_lo', '0'),
        ('epoch', 'epoch != expected', '0'),
        ('capability', 'read_word(reply, 10) != NPU_CONTROL_CAPS', '0'),
        ('parked', 'parked == 0xffu ? NPU_CLIENT_PARKED', 'parked != 0 ? NPU_CLIENT_PARKED'),
        ('released', 'released == epoch || ready || armed == epoch', 'ready || armed == epoch'),
        ('mask', '(parked & ~0xffu) || ', ''),
        ('monotonic', '(parked & s->parked_mask) != s->parked_mask', '0'),
    ]
    rows = []
    for name, old, new in mutations:
        assert text.count(old) == 1, name
        path = BUILD / ('mutant-' + name + '.c')
        path.write_text(text.replace(old, new))
        paths = build(path, 'mutant-' + name)
        p = Pair(paths)
        advance(p, BOUND if name == 'released' else STOPPING)
        if name == 'monotonic':
            t, w = p.request()
            assert p.complete(t, reply(w, parked=3)) == ACCEPTED
        t, w = p.request()
        out = reply(w)
        if name == 'ticket':
            caught = p.complete(t + 1, out) != IGNORED
        elif name == 'transport':
            caught = p.complete(t, out, error=-110) != REJECTED
        elif name == 'parked':
            p.complete(t, reply(w, parked=1))
            caught = p.state[0] != STOPPING
        else:
            field, value = {'magic': (2, 0), 'nonce': (7, 0), 'epoch': (6, 2),
                            'capability': (10, 31), 'released': (14, 1),
                            'mask': (11, 256), 'monotonic': (11, 1)}[name]
            out[field] = value
            caught = p.complete(t, out) != REJECTED
        assert caught, ('mutant survived', name)
        rows.append(dict(name=name, rejected_by_oracle=True, source_sha256=sha(path),
                         native_sha256=sha(paths[0]), aarch64_sha256=sha(paths[1])))
    return rows


def inputs():
    paths = [SOURCE, SOURCE.with_suffix('.h'), LINKER, SANITIZER, Path(__file__),
             ROOT / 'firmware/source-lock.json', ROOT / 'firmware/patches/openwrt.patch',
             ROOT / 'firmware/patches/luci.patch', ROOT / 'firmware/build.config']
    paths += [ROOT / 'firmware/npu' / name for name in ('barrier.c', 'barrier.h', 'admission.c', 'admission.h')]
    paths += [ROOT / 'firmware/npu' / name for name in ('ADMISSION_ABI.md', 'CONTROL_CLIENT_CONTRACT.md')]
    paths += [ROOT / 'tests/npu' / name for name in (
        'test_admission_native.py', 'test_admission_protocol.py', 'test_barrier_protocol.py',
        'test_barrier_core5.py', 'test_barrier_workers.py', 'test_firmware_mailbox_dispatch.py',
        'test_firmware_stop_irqs.py', 'test_firmware_stop_counterexample.py', 'emulation_layout.py',
        'admission-platform-emulation.c', 'admission-emulation.S', 'barrier-core5-emulation.S',
        'barrier-workers-emulation.S', 'barrier-workers-emulation.ld', 'barrier-emulation.ld')]
    return {str(path.relative_to(ROOT)): sha(path) for path in paths}


def main():
    before = inputs()
    paths = build()
    counts = protocol_cases(paths)
    fwpath = firmware.build_platform()
    shared = shared_workers(paths, fwpath)
    fw_cases = firmware_cases(paths, fwpath)
    limits = wire_limit_controls(paths, fwpath)
    mutants = mutation_cases()
    sanitizer = BUILD / 'client-sanitize'
    execute([shutil.which('clang'), '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
             '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-I', SOURCE.parent,
             SOURCE, SOURCE.parent / 'admission.c', SOURCE.parent / 'barrier.c', SANITIZER,
             '-o', sanitizer])
    sanitized = json.loads(execute([sanitizer]))
    execute([shutil.which('clang'), '--analyze', '-std=c11', '-Wall', '-Wextra', '-Werror',
             '-I', SOURCE.parent, SOURCE, '-o', BUILD / 'client-analyze.plist'])
    assert inputs() == before, 'inputs changed during verification'
    report = dict(passed=True, protocol_cases=counts, differential_calls=Pair.total,
                  shared_eight_contexts=shared, firmware_cases=fw_cases, mutations=mutants,
                  wire_limit_controls=limits, sanitizer=sanitized, inputs=before,
                  binaries={str(path.relative_to(ROOT)): sha(path) for path in (*paths, fwpath, sanitizer)},
                  stock_firmware_sha256=firmware.CODE_SHA, stock_data_sha256=firmware.DATA_SHA,
                  compiler=execute([shutil.which('clang'), '--version']).splitlines()[0],
                  unicorn_version=unicorn.__version__, clang_static_analyzer='passed without diagnostics',
                  scope='Unpromoted byte-codec/state client on native x86 and AArch64 instructions; actual RV32 admission/mailbox and eight serialized saved worker contexts. Existing modeled MMIO/IRQ invocation, helper returns, coherent storage, initial drain witnesses and transport delivery. No Linux provider binding, DMA lifetime/cache/physical drain certificate, full boot, image, restricted selector execution or router test.')
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / 'control-client.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=True, protocol_cases=counts, differential_calls=Pair.total,
                         shared_round_trips=shared['round_trips'], firmware_cases=len(fw_cases),
                         mutations=len(mutants), sanitizer=sanitized, evidence_sha256=sha(output))))


if __name__ == '__main__':
    main()
