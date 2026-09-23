#!/usr/bin/env python3
"""Cold-bootstrap V2 transport/binding policy and native callback integration."""
import ctypes
import itertools
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from unicorn import riscv_const as rv
from test_barrier_protocol import Rv32, STATE, STACK, END
import test_bootstrap_native as native
import test_control_v2 as control

ROOT = control.ROOT
BUILD = ROOT / '.local/npu-bootstrap-v2'
OUT = ROOT / 'research/checkpoints/2026-09-16-npu-bootstrap-control'
PATCH = OUT / '001-gate-v2-bind-for-bootstrap.patch'
SOURCE = ROOT / 'firmware/npu/bootstrap-v2.c'
PLATFORM = ROOT / 'tests/npu/bootstrap-v2-platform-emulation.c'
LINKER = ROOT / 'tests/npu/bootstrap-v2-emulation.ld'
SESSION, LOADER = control.SESSION, control.LOADER
BASE = ROOT / 'firmware/npu'
sha, execute = control.sha, control.execute
REGS = [getattr(rv, 'UC_RISCV_REG_A' + str(i)) for i in range(8)]


def stage_server():
    original = BASE / 'control-v2.c'
    assert 'int npu_control_v2_dispatch_gate(' in original.read_text()
    target = BUILD / 'staged/firmware/npu/control-v2.c'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(original.read_bytes())
    return target


def build(server, source=SOURCE, tag='bootstrap-v2'):
    BUILD.mkdir(parents=True, exist_ok=True)
    lld = shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'
    common = [shutil.which('clang'), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
              '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-I', BASE]
    host_sources = [BASE / 'control-client.c', BASE / 'control-v2-client.c']
    sources = [BASE / 'barrier.c', BASE / 'admission.c', BASE / 'bootstrap.c', server, source]
    paths = [BUILD / (tag + suffix) for suffix in ('.so', '-arm.elf', '-rv.elf')]
    execute([*common, *sources, *host_sources, '-shared', '-fPIC', '-o', paths[0]])
    execute([*common, *host_sources, '--target=aarch64-none-elf', '-mgeneral-regs-only', '-nostdlib',
             f'--ld-path={lld}', f'-Wl,-T,{control.v1.LINKER}', '-o', paths[1]])
    execute([*common, *sources, BASE / 'startup.c', '--target=riscv32', '-march=rv32imac_zicsr',
             '-mabi=ilp32', '-nostdlib', f'--ld-path={lld}', '-DNPU_EMULATION_BOOTSTRAP', PLATFORM,
             *[ROOT / 'tests/npu' / name for name in (
                 'startup-platform-emulation.c', 'bootstrap-platform-emulation.c',
                 'startup-emulation.S', 'bootstrap-emulation.S', 'admission-emulation.S',
                 'barrier-core5-emulation.S', 'barrier-workers-emulation.S')],
             f'-Wl,-T,{ROOT}/tests/npu/barrier-workers-emulation.ld,--no-relax',
             f'-Wl,-T,{LINKER}', '-Wl,--defsym=original_irq_30b6=0x840030b6',
             f'-Wl,--defsym=npu_emulation_control_v2_state={SESSION}',
             f'-Wl,--defsym=npu_emulation_control_v2_boot={LOADER}', '-o', paths[2]])
    return paths


class Bootstrap(native.Bootstrap):
    comparisons = 0

    def __init__(self, paths, boot=control.BOOT, session=None):
        super().__init__(paths[2])
        image = bytearray(LOADER + 8 - native.SRAM)
        original = native.bootstrap_data()
        image[:len(original)] = original
        struct.pack_into('<2I', image, LOADER - native.SRAM, *boot)
        if session is not None:
            struct.pack_into('<5I', image, SESSION - native.SRAM, *session)
        self.cpu.mem_write(native.SRAM, bytes(image))
        self.lib = ctypes.CDLL(str(paths[0]))
        assert self.rv.symbols['npu_emulation_control_v2_state'] == SESSION
        assert self.rv.symbols['npu_emulation_control_v2_boot'] == LOADER

    def reset(self, stop=0x8400420a):
        self.cpu.reg_write(rv.UC_RISCV_REG_MSTATUS, 8)
        stops = [stop, self.rv.symbols['npu_emulation_startup_fault'],
                 self.rv.symbols['npu_emulation_startup_precheck_fault']]
        return self.run(native.CODE, stops)

    def message(self, words, **kwargs):
        boot = (ctypes.c_uint32 * 20).from_buffer_copy(self.cpu.mem_read(native.BOOT, 80))
        session = (ctypes.c_uint32 * 5).from_buffer_copy(self.cpu.mem_read(SESSION, 20))
        admission = (ctypes.c_uint32 * 11).from_buffer_copy(self.cpu.mem_read(native.ADM, 44))
        barrier = (ctypes.c_uint32 * 26).from_buffer_copy(self.cpu.mem_read(STATE, 104))
        packet = (ctypes.c_uint32 * 20)(*words)
        length = kwargs.get('length', len(words) * 4)
        transport = self.lib.npu_bootstrap_v2_transport
        transport.restype = ctypes.c_int
        admitted = transport(boot, ctypes.c_uint32(kwargs.get('address', native.REQUEST)),
                             ctypes.c_uint32(length), ctypes.c_uint32(kwargs.get('flags', 1)))
        handled = 0
        if (admitted and len(words) == 20 and
                kwargs.get('address', native.REQUEST) == native.REQUEST and
                kwargs.get('flags', 1) == 1):
            function = self.lib.npu_bootstrap_v2_control
            function.restype = ctypes.c_int
            handled = function(boot, session, admission, barrier, packet, ctypes.c_uint32(length))
        response = super().message(words, **kwargs)
        if handled:
            assert response['flags'] == 7 and response['words'] == list(packet)
            for address, data in ((native.BOOT, boot), (SESSION, session),
                                  (native.ADM, admission), (STATE, barrier)):
                assert self.cpu.mem_read(address, ctypes.sizeof(data)) == bytes(data)
            Bootstrap.comparisons += 1
        return response


def setup(h, start=0, stop=6, run_clear=False):
    replies = []
    for step in range(start, stop):
        request = native.sequence()[step]
        response = h.message(request)
        assert response['flags'] == 7 and response['words'] == request
        assert response['callbacks'] == [hex(native.CALLBACKS[request[1]])]
        assert h.get32(native.BOOT + 8) == step + 1
        assert h.get32(native.BOOT + 12) == h.get32(native.ADM + 4) == 0
        replies.append(response)
        if step == 1 and run_clear:
            assert h.run(h.cpu.reg_read(rv.UC_RISCV_REG_PC), [0x8400e330]) == 0x8400e330
            assert h.clear_count == 0x7000
            assert h.cpu.mem_read(native.TX, 0xe000) == bytes(0xe000)
    return replies


def integrated(paths, boot=control.BOOT):
    h, host = Bootstrap(paths, boot=boot), control.Host(paths)
    assert h.reset(0x84003f32) == 0x84003f32
    assert h.get32(native.IRQ8) == h.rv.symbols['npu_emulation_mailbox']
    assert h.get32(native.WIFI_SLOT) == 0
    assert h.get32(native.STARTUP + 12) == 2
    assert h.get32(SESSION) == boot[0] and h.get32(SESSION + 4) == boot[1]
    assert control.exchange(host, h)[0] == control.ACCEPTED
    assert host.state[0] == control.DISCOVERED
    version = h.message([0x30, 10, 0])
    assert version['flags'] == 7 and version['words'][2] == 0x457
    assert h.run(0x84003f32, [0x8400420a]) == 0x8400420a
    replies = setup(h, run_clear=True)
    assert h.get32(native.BOOT + 16) == 0x1e
    before = h.boot_snapshot()
    control.advance(host, h)
    assert control.exchange(host, h)[0] == control.ACCEPTED
    assert h.boot_snapshot() == before
    assert host.state[0] == control.STOPPING and host.state[7] == 1
    assert host.state[12] == 0 and h.get32(STATE + 4) == h.get32(STATE + 8) == 0
    assert h.message([0x30, 10, 0])['flags'] == 3
    return dict(boot=list(boot), version=version['words'][2], setup_replies=replies,
                cleared_bytes=h.clear_count * 2, client=list(host.state),
                core0_boundary='0x8400e330', release=0, arm=0, drains=0)


def early_bind(paths, step):
    h, host = Bootstrap(paths), control.Host(paths)
    assert h.reset() == 0x8400420a
    setup(h, stop=step)
    control.advance(host, h, control.DISCOVERED)
    before = h.boot_snapshot()
    result, request, response = control.exchange(host, h)
    assert result == control.REJECTED and response[9] == 5, 'early-bind-must-be-busy'
    assert h.boot_snapshot() == before and h.get32(native.ADM + 12) == h.get32(native.ADM + 16) == 0
    assert h.get32(SESSION + 16) == request[16]
    setup(h, start=step)
    before = h.boot_snapshot()
    replay = h.message(request)
    assert replay['flags'] == 7 and replay['words'][9] == 8, 'early-bind-replay'
    assert h.boot_snapshot() == before and h.get32(native.ADM + 12) == h.get32(native.ADM + 16) == 0
    control.held(host)
    return dict(step=step, status=response[9], replay_status=replay['words'][9],
                setup_completed=True, bound=False)


def rejected_transport(paths):
    h, host = Bootstrap(paths), control.Host(paths)
    assert h.reset() == 0x8400420a
    _, request = host.request()
    cases = [dict(length=n) for n in (0, 4, 8, 11, 13, 63, 64, 65, 79, 81, 256, 257, 0xffffffff)]
    cases += [dict(flags=n) for n in (0, 3, 0x21, 0x801, 0x6001, 0x8001, 0xffffffff)]
    cases += [dict(address=n) for n in (0, native.REQUEST + 1, native.REQUEST + 4,
                                       native.REQUEST - 4, native.REQUEST & 0x3fffffff,
                                       native.REQUEST | 0x40000000, 0x84000000, 0xffffffff)]
    for case in cases:
        before = bytes(h.cpu.mem_read(STATE, 0x3a8))
        response = h.message(request, **case)
        assert not response['flags'] & 0x1c, 'invalid-transport-dispatched'
        assert not response['reads'] and not response['callbacks'], 'payload-before-transport-admission'
        assert h.cpu.mem_read(STATE, 0x3a8) == before
    old = native.control_packet(0, nonce=control.v1.NONCE)
    assert h.message(old)['flags'] == 3 and not h.payload_reads
    return cases


def cold_failures(paths):
    rows = []
    configurations = [((0, 0), [0] * 5)]
    for word in range(5):
        session = [0] * 5
        session[word] = 0x12340000 + word
        configurations.append((control.BOOT, session))
    for boot, session in configurations:
        h = Bootstrap(paths, boot=boot, session=session)
        result = h.reset()
        assert result == h.rv.symbols['npu_emulation_startup_fault'], 'cold-identity-fault'
        assert h.get32(native.STARTUP + 12) == 3 and h.get32(STATE + 16) == 1
        assert h.get32(native.ADM + 8) == 1
        assert h.cpu.mem_read(SESSION, 20) == struct.pack('<5I', *session), 'stale-session-erased'
        assert h.get32(native.IRQ8) != h.rv.symbols['npu_emulation_mailbox']
        assert not h.cpu.reg_read(rv.UC_RISCV_REG_MSTATUS) & 8
        rows.append(dict(boot=list(boot), prior_session=session, phase=3, common_fault=True))
    return rows


def immutable_identity(paths):
    h, host = Bootstrap(paths), control.Host(paths)
    assert h.reset() == 0x8400420a
    h.cpu.mem_write(LOADER, struct.pack('<2I', *control.OTHER_BOOT))
    result, _, reply = control.exchange(host, h)
    assert result == control.ACCEPTED and reply[17:19] == list(control.BOOT)
    return dict(loader_changed_after_init=True, reported_boot=reply[17:19])


def failed_setup(paths, step):
    h, host = Bootstrap(paths), control.Host(paths)
    assert h.reset() == 0x8400420a
    control.advance(host, h, control.DISCOVERED)
    setup(h, stop=step)
    request = native.sequence()[step]
    h.fail_api = request[1]
    failed = h.message(request)
    assert failed['flags'] == 3 and failed['callbacks'] == [hex(native.CALLBACKS[request[1]])]
    assert h.get32(native.BOOT + 4) == 1 and h.get32(native.BOOT + 8) == step
    assert h.get32(native.BOOT + 12) == h.get32(native.ADM + 4) == 1
    before = h.boot_snapshot()
    result, _, response = control.exchange(host, h)
    assert result == control.REJECTED and response[9] == 6
    assert h.boot_snapshot() == before and h.get32(native.ADM + 12) == 0
    assert h.message(request)['flags'] == 3 and h.boot_snapshot() == before
    control.held(host)
    return dict(step=step, callback_return_modeled=0, fault_status=6,
                retained_mask=h.get32(native.BOOT + 16), inflight_retained=True)


def existing_error(paths):
    h, host = Bootstrap(paths), control.Host(paths)
    assert h.reset() == 0x8400420a
    setup(h)
    control.advance(host, h, control.DISCOVERED)
    _, request = host.request()
    rows = []
    for field, value, expected in ((17, control.BOOT[0] ^ 1, 7), (3, 1, 1),
                                   (4, 64, 1), (16, 0, 1), (19, 1, 1)):
        bad = request.copy()
        bad[field] = value
        before = bytes(h.cpu.mem_read(STATE, 0x3a8))
        response = h.message(bad)
        assert response['flags'] == 7 and response['words'][9] == expected, 'existing-error-overridden'
        assert h.cpu.mem_read(STATE, 0x3a8) == before
        rows.append(dict(field=field, status=expected))
    return rows


class Policy:
    calls = 0

    def __init__(self, paths):
        self.lib = ctypes.CDLL(str(paths[0]))
        self.arena = (ctypes.c_uint32 * (0x800 // 4))()
        self.rv = Rv32(paths[2])
        self.reset()

    def reset(self):
        self.set(0, [0] * len(self.arena))
        self.set(0, [1])
        self.set(0x100, [1])
        self.set(0x200, [0x31505342])
        self.set(0x248, [native.REQUEST, 256])

    def set(self, offset, values):
        self.arena[offset // 4:offset // 4 + len(values)] = values
        self.rv.cpu.mem_write(STATE + offset, struct.pack('<' + 'I' * len(values), *values))

    def snapshot(self):
        return list(self.arena)

    def call(self, name, *args):
        offsets = {'session_init': [0x380, 0x100, 0], 'transport': [0x200],
                   'control': [0x200, 0x380, 0x100, 0, 0x400]}[name]
        fn = getattr(self.lib, 'npu_bootstrap_v2_' + name)
        fn.restype = ctypes.c_uint32
        expected = fn(*[ctypes.byref(self.arena, offset) for offset in offsets],
                      *[ctypes.c_uint32(value) for value in args])
        cpu = self.rv.cpu
        saved = {getattr(rv, 'UC_RISCV_REG_X' + str(i)): 0x12340000 + i
                 for i in (8, 9, *range(18, 28))}
        for register, value in saved.items():
            cpu.reg_write(register, value)
        for register, value in zip(REGS, [*[STATE + offset for offset in offsets], *args]):
            cpu.reg_write(register, value)
        cpu.reg_write(rv.UC_RISCV_REG_SP, STACK)
        cpu.reg_write(rv.UC_RISCV_REG_RA, END)
        cpu.emu_start(self.rv.symbols['npu_bootstrap_v2_' + name], END, count=30000, timeout=1000000)
        assert cpu.reg_read(rv.UC_RISCV_REG_PC) == END
        assert cpu.reg_read(rv.UC_RISCV_REG_A0) == expected
        assert cpu.reg_read(rv.UC_RISCV_REG_SP) == STACK
        assert all(cpu.reg_read(register) == value for register, value in saved.items())
        assert cpu.mem_read(STATE, 0x800) == bytes(self.arena)
        Policy.calls += 1
        return expected

    def bind(self, sequence=2):
        self.set(0x400, [0x3f, 0, 0x3243514e, 2, 80, 1, 1, *control.v1.NONCE,
                         *([0] * 7), sequence, *control.BOOT, 0])
        assert self.call('control', 80) == 1
        return self.arena[0x400 // 4 + 9]


def policy_cases(paths):
    counts = dict(initialization=0, transport=0, binding=0)
    p = Policy(paths)
    for boot in (control.BOOT, (1, 0), (0, 1), (0, 0)):
        p.reset()
        before = p.snapshot()
        result = p.call('session_init', *boot)
        expected = before.copy()
        if any(boot):
            expected[0x380 // 4:0x380 // 4 + 2] = boot
            assert result == 1
        else:
            expected[0x100 // 4] = expected[0x108 // 4] = expected[4] = 1
            assert result == 0
        assert p.snapshot() == expected
        counts['initialization'] += 1
    dirty = [(offset + word * 4) for offset, words in ((0, 26), (0x100, 11), (0x380, 5))
             for word in range(words)]
    for offset in dirty:
        p.reset()
        p.set(offset, [2 if offset in (0, 0x100) else 1])
        before = p.snapshot()
        assert p.call('session_init', *control.BOOT) == 0, 'dirty-init-accepted'
        before[0x100 // 4] = before[0x108 // 4] = before[4] = 1
        assert p.snapshot() == before
        counts['initialization'] += 1

    for address, length, flags in itertools.product(
            (native.REQUEST, native.REQUEST + 4, 0, 0x42000000, 0xc0000000),
            (0, 11, 12, 13, 63, 64, 79, 80, 81, 256, 0xffffffff), (0, 1, 3, 0x801)):
        p.reset()
        before = p.snapshot()
        expected = int(address == native.REQUEST and length in (12, 80) and flags == 1)
        assert p.call('transport', address, length, flags) == expected, 'transport-contract'
        assert p.snapshot() == before
        counts['transport'] += 1
    for base, capacity, accepted in ((0x80000000, 256, True), (0xbfffff00, 256, True),
                                     (0x7ffffffc, 256, False), (0xbfffff04, 256, False),
                                     (0x82000001, 256, False), (native.REQUEST, 80, False),
                                     (native.REQUEST, 255, False), (native.REQUEST, 257, False)):
        p.reset()
        p.set(0x248, [base, capacity])
        assert p.call('transport', base, 80, 1) == int(accepted), 'request-region-boundary'
        counts['transport'] += 1

    for magic, failed, step, inflight, retained, active in itertools.product(
            (0, 0x31505342), (0, 1), range(8), (0, 1), (0, 0xe, 0x1e, 0x1f), (0, 1)):
        p.reset()
        assert p.call('session_init', *control.BOOT) == 1
        p.set(0x200, [magic, failed, step, inflight, retained])
        p.set(0x104, [active])
        expected = 6 if not magic or failed else (5 if step != 6 or inflight or retained != 0x1e or active else 0)
        before = p.snapshot()
        assert p.bind() == expected, 'bootstrap-bind-policy'
        before[0x380 // 4:0x394 // 4] = [*control.BOOT, *control.v1.NONCE, 2]
        if not expected:
            before[0x10c // 4:0x114 // 4] = control.v1.NONCE
        before[0x400 // 4:0x450 // 4] = [0x3f, 0, 0x3252514e, 2, 80, 1, 1,
                                        *control.v1.NONCE, expected, 0x27, *([0] * 5),
                                        2, *control.BOOT, 0]
        assert p.snapshot() == before, 'binding-side-effects'
        counts['binding'] += 1
    return counts


def mutations(server):
    rows = []
    changes = [
        ('defer-bind', server, 'status = bind_status;', 'status = (unsigned int)bind_status & 0u;', 'early'),
        ('preserve-error', server, 'status == NPU_CONTROL_OK && operation == NPU_CONTROL_BIND',
         'operation == NPU_CONTROL_BIND', 'error'),
        ('step', SOURCE, 's->step != NPU_BOOTSTRAP_STEPS || ', '', 'early'),
        ('retained', SOURCE, 's->retained_mask != BOOT_RETAINED_MASK', '0', 'policy'),
        ('pinned-address', SOURCE, 'address == request->base && ', '', 'transport'),
        ('frame-size', SOURCE, 'bytes == NPU_CONTROL_V2_SIZE',
         '(bytes == NPU_CONTROL_V2_SIZE || bytes == NPU_CONTROL_SIZE)', 'policy'),
        ('boot-identity', SOURCE, '!(boot_lo || boot_hi) || ', '', 'cold'),
        ('stale-session', SOURCE, 's->nonce_hi || s->last_sequence || ', 's->nonce_hi || ', 'cold'),
    ]
    for name, path, old, new, target in changes:
        original = path.read_text()
        assert original.count(old) == 1, name
        changed = BUILD / ('mutant-' + name + '.c')
        changed.write_text(original.replace(old, new))
        paths = build(changed if path == server else server,
                      source=changed if path == SOURCE else SOURCE, tag='mutant-' + name)
        try:
            if target == 'early':
                early_bind(paths, 5)
            elif target == 'error':
                existing_error(paths)
            elif target == 'transport':
                rejected_transport(paths)
            elif target == 'cold':
                cold_failures(paths)
            else:
                policy_cases(paths)
        except AssertionError as error:
            labels = {'policy': ('transport-contract', 'bootstrap-bind-policy'),
                      'early': ('early-bind-must-be-busy',),
                      'error': ('existing-error-overridden',),
                      'transport': ('payload-before-transport-admission',),
                      'cold': ('cold-identity-fault', 'stale-session-erased')}
            assert str(error) in labels[target], str(error)
            rows.append(dict(name=name, detected=True, oracle=str(error), source_sha256=sha(changed),
                             binaries={str(p.relative_to(ROOT)): sha(p) for p in paths}))
        else:
            raise AssertionError('Mutant survived: ' + name)
    return rows


def fingerprints():
    paths = [SOURCE, SOURCE.with_suffix('.h'), PLATFORM, LINKER, PATCH, Path(__file__),
             ROOT / 'tests/npu/bootstrap-v2-sanitize.c',
             Path(control.__file__), Path(native.__file__), native.DTB,
             *[BASE / name for name in ('barrier.c', 'barrier.h', 'admission.c', 'admission.h',
                                       'bootstrap.c', 'bootstrap.h', 'startup.c', 'startup.h',
                                       'control-client.c', 'control-client.h', 'control-v2.c',
                                       'control-v2.h', 'control-v2-client.c')],
             *[ROOT / 'tests/npu' / name for name in (
                 'admission-platform-emulation.c', 'control-v2-platform-emulation.c',
                 'startup-platform-emulation.c', 'bootstrap-platform-emulation.c',
                 'startup-emulation.S', 'bootstrap-emulation.S', 'admission-emulation.S',
                 'barrier-core5-emulation.S', 'barrier-workers-emulation.S', 'barrier-workers-emulation.ld',
                 'test_boot_irq_installation.py', 'test_startup_native.py', 'test_firmware_memory_layout.py',
                 'test_admission_native.py', 'test_barrier_protocol.py', 'preflight_dtb_cases.py')],
             ROOT / 'firmware/source-lock.json', ROOT / 'firmware/patches/openwrt.patch',
             ROOT / 'firmware/patches/luci.patch', ROOT / 'firmware/build.config']
    paths += [control.OUT / 'control-v2.json', sys.modules['test_boot_irq_installation'].GHIDRA]
    for module in list(sys.modules.values()):
        file = getattr(module, '__file__', None)
        if file:
            path = Path(file).resolve()
            if path.is_relative_to(ROOT / 'tests/npu') and path.suffix == '.py':
                paths.append(path)
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(set(paths))}


def sanitizer(server):
    plan = ',\n'.join('    {0x%xu, 0x%xu}' % row for row in native.plan())
    (BUILD / 'bootstrap-v2-plan.inc').write_text(plan + '\n')
    binary = BUILD / 'bootstrap-v2-sanitize'
    command = [shutil.which('clang'), '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-I', BASE, '-I', BUILD,
               ROOT / 'tests/npu/bootstrap-v2-sanitize.c', server, SOURCE]
    command += [BASE / name for name in ('barrier.c', 'admission.c', 'bootstrap.c',
                                        'control-client.c', 'control-v2-client.c')]
    execute([*command, '-o', binary])
    return dict(result=json.loads(execute([binary])), binary=str(binary.relative_to(ROOT)),
                sha256=sha(binary), generated_plan_sha256=sha(BUILD / 'bootstrap-v2-plan.inc'))


def main():
    before = fingerprints()
    server = stage_server()
    paths = build(server)
    positive = [integrated(paths, boot) for boot in (control.BOOT, (1, 0), (0, 1))]
    early = [early_bind(paths, step) for step in range(6)]
    rejected = rejected_transport(paths)
    cold = cold_failures(paths)
    immutable = immutable_identity(paths)
    failures = [failed_setup(paths, step) for step in range(6)]
    errors = existing_error(paths)
    print(json.dumps(dict(phase='native_bootstrap', passed=True)), flush=True)
    policies = policy_cases(paths)
    print(json.dumps(dict(phase='policy', passed=True, cases=policies)), flush=True)
    mutants = mutations(server)
    print(json.dumps(dict(phase='mutations', passed=True, detected=len(mutants))), flush=True)
    regression_paths = control.build(server=server, tag='bootstrap-gate-regression')
    regressions = dict(cases=len(control.cases(regression_paths)),
                       malformed=len(control.malformed(regression_paths)),
                       shared=control.shared_workers(regression_paths),
                       identity_limit=control.reused_identity_control(regression_paths))
    sanitized = sanitizer(server)
    for source in (SOURCE, server):
        execute([shutil.which('clang'), '--analyze', '-std=c11', '-Wall', '-Wextra', '-Werror',
                 '-I', BASE, source, '-o', BUILD / (source.stem + '-analyze.plist')])
    assert before == fingerprints(), 'inputs changed during run'
    report = dict(passed=True, integrated=positive, early_bind=early, rejected_transport=rejected,
                  cold_failures=cold, immutable_identity=immutable,
                  setup_failures=failures, existing_errors=errors, policy_cases=policies,
                  mutations=mutants, standalone_v2_regressions=regressions,
                  sanitizer=sanitized,
                  host_comparisons=control.Host.calls, control_comparisons=Bootstrap.comparisons,
                  policy_comparisons=Policy.calls,
                  standalone_control_comparisons=control.Coordinator.calls,
                  inputs=before, patched_server_sha256=sha(server),
                  binaries={str(path.relative_to(ROOT)): sha(path) for path in (*paths, *regression_paths)},
                  stock_firmware_sha256=native.CODE_SHA, stock_data_sha256=native.DATA_SHA,
                  compiler=execute([shutil.which('clang'), '--version']).splitlines()[0],
                  unicorn_version=control.unicorn.__version__, static_analysis='passed without diagnostics',
                  emulator_wall_budget_us=int(os.environ.get('NPU_EMULATION_TIMEOUT_US', '10000000')),
                  scope='Unpromoted V2 bootstrap adapter through actual reset/IRQ registration and six original memory callbacks to the existing core0 boundary. Host x86/AArch64 and control x86/RV32 comparisons. Loader containment/identity generation, MMIO/IRQ delivery/cache, full postgate boot and physical drains remain unproved.')
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / 'bootstrap-control-v2.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=True, integrated=len(positive), early_bind=len(early),
                         rejected_transport=len(rejected), cold_failures=len(cold),
                         policies=policies, mutations=len(mutants),
                         host_calls=control.Host.calls, control_calls=Bootstrap.comparisons,
                         evidence_sha256=sha(output))))


if __name__ == '__main__':
    main()
