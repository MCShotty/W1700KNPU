#!/usr/bin/env python3
"""Native cold startup with V2 control and all 50 retained candidate detours."""
import argparse
from collections import Counter
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
from unicorn import riscv_const as r
import unicorn

import test_bootstrap_control_v2 as boot
import test_tunnel_packet_extents as packets
import test_allocator_startup as allocator
import test_allocator_reset as reset
import test_bridge_startup as bridge
from test_multihart_cold_boot import AllHarts, STARTUPS
from test_barrier_protocol import Rv32
from test_barrier_core5 import jump
from test_native_wifi_boot import footprints, host_publish, L2, L2_BYTES
from test_firmware_memory_layout import STACK_TOPS
from emulation_layout import CODE, SRAM, STATE, HEAP, HEAP_BYTES

ROOT, BASE, TESTS = boot.ROOT, boot.BASE, boot.ROOT / 'tests/npu'
BUILD = ROOT / '.local/npu-bootstrap-v2-composition'
OUT = ROOT / 'research/checkpoints/2026-09-16-npu-bootstrap-composition'
CODE_INPUT = ROOT / '.local/npu-quiescence/firmware/en7581_MT7996_npu_rv32.bin'
control, native = boot.control, boot.native
headers, egress = packets.headers, packets.egress
txdone, order, layout = headers.txdone, headers.order, headers.layout
sha, execute = boot.sha, boot.execute
COMMANDS = []


def run(command):
    COMMANDS.append(list(map(str, command)))
    return execute(command)


def elf(path):
    return ELFFile(io.BytesIO(path.read_bytes()))


def symbols(path):
    return {s.name: s['st_value'] for s in elf(path).get_section_by_name('.symtab').iter_symbols()
            if s.name and s['st_shndx'] != 'SHN_UNDEF'}


def check_imports(path, imports):
    expected, actual = symbols(imports), symbols(path)
    differences = {name: dict(expected=hex(value), actual=hex(actual[name]))
                   for name, value in expected.items()
                   if name in actual and not name.startswith('$') and actual[name] != value}
    assert not differences, ('stale-imported-symbol', differences)


def build():
    BUILD.mkdir(parents=True, exist_ok=True)
    target = BUILD / 'staged/firmware/npu/control-v2.c'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(control.SERVER.read_bytes())
    done = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(boot.PATCH)],
                          cwd=BUILD / 'staged', capture_output=True, text=True, timeout=30)
    assert done.returncode == 0 and 'offset' not in done.stdout and 'fuzz' not in done.stdout, done.stdout + done.stderr
    common = [shutil.which('clang'), '-O2', '-g', '-Wall', '-Wextra', '-Werror',
              '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-I', BASE]
    lld = shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'
    rv = ['--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32', '-nostdlib', f'--ld-path={lld}']
    sources = [BASE / name for name in ('barrier.c', 'admission.c', 'bootstrap.c', 'bootstrap-v2.c')]
    host = [BASE / 'control-client.c', BASE / 'control-v2-client.c']
    paths = [BUILD / name for name in ('control.so', 'host-arm.elf', 'base-rv.elf')]
    run([*common, '-std=c11', *sources, target, *host, '-shared', '-fPIC', '-o', paths[0]])
    run([*common, '-std=c11', *host, '--target=aarch64-none-elf', '-mgeneral-regs-only', '-nostdlib',
         f'--ld-path={lld}', f'-Wl,-T,{control.v1.LINKER}', '-o', paths[1]])
    run([*common, *rv, *sources, target, BASE / 'startup.c', BASE / 'gdma.c',
         '-DNPU_EMULATION_BOOTSTRAP', '-DNPU_GDMA_POLL_LIMIT=65536', boot.PLATFORM,
         *[TESTS / name for name in ('startup-platform-emulation.c', 'bootstrap-platform-emulation.c',
             'gdma-platform-emulation.c', 'startup-emulation.S', 'bootstrap-emulation.S',
             'admission-emulation.S', 'barrier-core5-emulation.S', 'barrier-workers-emulation.S')],
         f'-Wl,-T,{TESTS}/barrier-workers-emulation.ld,--no-relax', f'-Wl,-T,{boot.LINKER}',
         '-Wl,--defsym=original_irq_30b6=0x840030b6',
         f'-Wl,--defsym=npu_emulation_control_v2_state={boot.SESSION}',
         f'-Wl,--defsym=npu_emulation_control_v2_boot={boot.LOADER}', '-o', paths[2]])

    def component(name, sources, linker, imports=None, defines=()):
        path = BUILD / (name + '.elf')
        run([*common, *rv, *sources, *['-D' + x for x in defines],
             f'-Wl,-T,{linker},--no-relax',
             *([f'-Wl,--just-symbols={imports}'] if imports else []), '-o', path])
        if imports:
            check_imports(path, imports)
        return path

    parts = dict(base=paths[2])
    parts['bridge'] = component('bridge', [bridge.ASM], bridge.LINKER, paths[2])
    parts['reset'] = component('reset', [reset.ASM], reset.LINKER)
    parts['allocator'] = component('allocator', [BASE / 'allocator.c', allocator.SOURCE, allocator.ASM],
                                   layout.LINKER, paths[2], ['NPU_EMULATION_COMMAND_RING=0x84060000'])
    parts['txdone'] = component('txdone', [txdone.SOURCE, txdone.ASM], txdone.LINKER, paths[2])
    parts['order'] = component('order', [order.ASM], order.LINKER)
    parts['headers'] = component('headers', [headers.SOURCE, headers.ASM], headers.LINKER)
    parts['egress'] = component('egress', [egress.ASM], egress.LINKER, paths[2])
    parts['packets'] = component('packets', [packets.SOURCE, packets.ASM], packets.LINKER, parts['egress'])
    stale = component('stale-v1-bridge-control', [bridge.ASM], bridge.LINKER, bridge.ELF)
    try:
        check_imports(stale, paths[2])
    except AssertionError as error:
        assert error.args[0][0] == 'stale-imported-symbol'
    else:
        raise AssertionError('stale-link-control-not-rejected')
    return paths, parts


def memory_layout(parts):
    sections = []
    for name, path in parts.items():
        for s in elf(path).iter_sections():
            if s['sh_flags'] & 2 and s['sh_size']:
                sections.append(dict(component=name, section=s.name, start=s['sh_addr'],
                                     end=s['sh_addr'] + s['sh_size'], sha256=packets.headers.sha(s.data())))
    occupied = sections + [dict(component=name, start=start, end=end) for name, start, end in (
        ('original-code', CODE, CODE + CODE_INPUT.stat().st_size),
        ('native-stacks', STACK_TOPS[0] - 0x4000, STACK_TOPS[-1]),
        ('provider-backup', 0x84200000, 0x84240000),
        ('native-sram', SRAM, SRAM + 0x4754),
        ('barrier', STATE, STATE + 104), ('admission', native.ADM, native.ADM + 44),
        ('saved-mask', STATE + 0x140, STATE + 0x158),
        ('startup', native.STARTUP, native.STARTUP + 64),
        ('bootstrap', native.BOOT, native.BOOT + 80), ('plan', native.PLAN, native.PLAN + 48),
        ('session', boot.SESSION, boot.SESSION + 20), ('loader-identity', boot.LOADER, boot.LOADER + 8))]
    for i, a in enumerate(occupied):
        for b in occupied[i + 1:]:
            assert a['end'] <= b['start'] or b['end'] <= a['start'], ('composition-overlap', a, b)
    assert all(CODE + 0x40000 <= s['start'] < s['end'] <= CODE + 0x200000 for s in sections)
    ring = next(s for s in sections if s['section'] == '.command_ring')
    assert ring['start'] == layout.RING and ring['end'] - ring['start'] == layout.RING_BYTES
    old, new = symbols(bridge.ELF), symbols(parts['base'])
    changed = {name: dict(old=hex(old[name]), new=hex(new[name])) for name in
               ('npu_barrier_fail', 'npu_admission_fail', 'npu_emulation_mailbox', 'npu_emulation_idle')
               if old[name] != new[name]}
    assert changed, 'old-symbol-control-did-not-differ'
    return dict(occupied=occupied, stale_v1_import_control=changed,
                production_loader_or_physical_backing_proved=False)


class Composed(boot.Bootstrap, AllHarts):
    """The V2 loader/message binding composes with the original all-hart model."""
    def __init__(self, paths, parts, *, plic='banked', boot_id=control.BOOT, session=None,
                 deny_type=None):
        self.executions = Counter()
        self.deny_type, self.denied = deny_type, None
        super().__init__(paths, boot=boot_id, session=session)
        self.plic = plic
        self.reset_rv, more = reset.install(self, parts['reset'])
        self.patches.extend(more)
        self.allocator_rv, patch = allocator.install(self, parts['allocator'])
        self.patches.append(patch)
        self.guard_rv = Rv32(parts['bridge'], self.cpu)
        for site, (kind, before) in bridge.GUARDS.items():
            self.install_site(site, self.guard_rv.symbols['npu_emulation_bridge_' + kind + '_guard'], before)
        self.txdone_rv = Rv32(parts['txdone'], self.cpu)
        for site, (name, before) in txdone.SITES.items():
            self.install_site(site, self.txdone_rv.symbols[name], before)
        self.order_rv, more = order.install(self, parts['order'])
        self.patches.extend(more)
        self.header_rv, more = headers.install(self, parts['headers'])
        self.patches.extend(more)
        self.egress_rv, more = egress.install(self, parts['egress'])
        self.patches.extend(more)
        self.packet_rv, more = packets.install(self, parts['packets'])
        self.patches.extend(more)
        assert self.get32(0x8401b230) == 58879
        self.put32(0x8401b230, layout.LAYOUT_HYPOTHESIS)
        self.cpu.ctl_remove_cache(CODE, CODE + 0x201000)
        sites = [int(row['site'], 16) for row in self.patches]
        assert len(sites) == len(set(sites)) == 50, 'all50-before-reset'
        self.check_hooks()

    def install_site(self, site, target, before):
        assert bytes(self.cpu.mem_read(site, 4)).hex() == before == self.code[site-CODE:site-CODE+4].hex()
        after = jump(site, target)
        self.cpu.mem_write(site, after)
        self.patches.append(dict(site=hex(site), before=before, after=after.hex(), target=hex(target)))

    def check_hooks(self):
        for row in self.patches:
            assert bytes(self.cpu.mem_read(int(row['site'], 16), 4)).hex() == row['after'], 'retained-hook-changed'

    def code_hook(self, cpu, pc, size, data):
        self.executions[pc] += 1
        if pc == allocator.GETTER and self.denied is None and cpu.reg_read(r.UC_RISCV_REG_A0) == self.deny_type:
            self.put32(0x1ec03048, 0x10100)
            self.denied = dict(caller=cpu.reg_read(r.UC_RISCV_REG_RA),
                               heap=bytes(self.cpu.mem_read(HEAP, HEAP_BYTES)),
                               l2=bytes(self.cpu.mem_read(L2, L2_BYTES)),
                               bootstrap=self.boot_snapshot(),
                               metadata=bytes(self.cpu.mem_read(allocator.NATIVE_STATE, allocator.protocol.STATE_BYTES)))
        # No direct DESC callback is needed to reach the initial parking gates.
        assert pc != 0x8400dd82, 'unexpected-desc-dispatch'
        super().code_hook(cpu, pc, size, data)

    def message(self, words, **kwargs):
        assert (len(words) == 20 and words[:2] == [0x3f, 0] or
                words in native.sequence() or words == [0x30, 10, 0]), 'unexpected-request-lane'
        response = super().message(words, **kwargs)
        if len(words) == 20 and response['flags'] == 7:
            assert response['words'][10] == 0x27, 'wire-capabilities-changed'
        return response

    def finish_coordinator(self):
        assert self.run(self.cpu.reg_read(r.UC_RISCV_REG_PC), [0x8400d1d4]) == 0x8400d1d4
        assert self.l2_writes * 4 == L2_BYTES
        assert bytes(self.cpu.mem_read(L2, L2_BYTES)) == bytes(L2_BYTES)
        self.l2_clear_active = False
        assert self.run(0x8400d1d4, [0x8400f836]) == 0x8400f836
        footprint = footprints(self)
        host_publish(self, staggered=False)
        self.contexts[0] = self.cpu.context_save()
        return footprint

    def on_core0(self):
        self.hart = 0
        self.cpu.context_restore(self.contexts[0])


def invariant(h, host, mask, session):
    words = list(struct.unpack('<26I', h.cpu.mem_read(STATE, 104)))
    assert words == [1, 0, 0, 0, 0] + [int(bool(mask & (1 << i))) for i in range(8)] + [0] * 13
    assert h.get32(native.ADM) == 1 and h.get32(native.ADM + 4) == h.get32(native.ADM + 8) == 0
    # The V2 client normalizes validated capabilities for its private V1 core.
    assert host.state[7] == 1 and host.state[13] == 7 and host.state[10] == mask, list(host.state)
    assert host.state[8] == host.state[9] == host.state[11] == host.state[12] == 0
    assert host.state[0] == (control.PARKED if mask == 255 else control.STOPPING)
    assert bytes(h.cpu.mem_read(boot.SESSION, 16)) == session
    assert h.get32(native.BOOT + 8) == 6 and h.get32(native.BOOT + 16) == 0x1e
    assert h.cpu.mem_read(SRAM + 0x46fa, 1) == b'\0'
    assert not any(row['type'] == 0x81 for row in h.allocations)
    h.check_hooks()


def scenario(paths, parts, schedule, *, late_bind=False, plic='banked'):
    h, host = Composed(paths, parts, plic=plic), control.Host(paths)
    early, workers, statuses = [], [], []
    mask, session = 0, None
    for hart in schedule:
        if hart == 0:
            h.hart = 0
            h.cpu.context_restore(h.fresh)
            assert h.reset(0x84003f32) == 0x84003f32
            assert h.get32(native.WIFI_SLOT) == 0
            assert control.exchange(host, h)[0] == control.ACCEPTED
            assert h.message([0x30, 10, 0])['words'][2] == 0x457
            assert h.run(0x84003f32, [0x8400420a]) == 0x8400420a
            boot.setup(h, run_clear=True)
            if not late_bind:
                control.advance(host, h)
                session = bytes(h.cpu.mem_read(boot.SESSION, 16))
                invariant(h, host, 0, session)
            footprint = h.finish_coordinator()
            mask |= 1
        elif 0 not in h.contexts:
            h.early_worker(hart)
            early.append(hart)
            assert h.cpu.mem_read(boot.SESSION, 20) == bytes(20)
            continue
        else:
            workers.append(h.worker(hart))
            mask |= 1 << hart
        if not late_bind:
            h.on_core0()
            _, _, response = control.exchange(host, h)
            invariant(h, host, mask, session)
            statuses.append(dict(hart=hart, mask=mask, sequence=response[16]))
    for hart in reversed(early):
        workers.append(h.worker(hart))
        mask |= 1 << hart
        if not late_bind:
            h.on_core0()
            _, _, response = control.exchange(host, h)
            invariant(h, host, mask, session)
            statuses.append(dict(hart=hart, mask=mask, sequence=response[16]))
    assert len(workers) == 7 and mask == 255
    h.on_core0()
    if late_bind:
        assert h.get32(native.ADM + 12) == h.get32(native.ADM + 16) == 0
        control.advance(host, h, control.BOUND)
        assert control.exchange(host, h)[0] == control.ACCEPTED
        session = bytes(h.cpu.mem_read(boot.SESSION, 16))
    for hart in reversed(schedule):
        h.repoll(hart)
        h.on_core0()
        assert control.exchange(host, h)[0] == control.ACCEPTED
        invariant(h, host, 255, session)
    initialized = [e for e in h.events if e['kind'] == 'candidate-initializer']
    assert len(initialized) == 2 and all(e['hart'] == 0 for e in initialized)
    assert [h.get32(native.STARTUP + 20 + i * 4) for i in range(8)] == [1] * 8
    assert bytes(h.cpu.mem_read(layout.RING, layout.RING_BYTES)) == layout.ring_template()
    assert h.get32(reset.FLAG_POINTER) == HEAP and h.get32(reset.POOL_POINTER) == HEAP + 32
    assert h.clear_count * 2 == 0xe000 and not h.executions[h.rv.symbols['npu_emulation_gdma_copy']]
    assert not any(h.executions[pc] for pc in h.executions if 0x84048000 <= pc < 0x84049000 or 0x84052000 <= pc < 0x8405c000)
    assert [a['type'] for a in h.allocations if a['type'] < 0x100] == reset.COLD_TYPES
    assert sha_bytes(h.cpu.mem_read(L2, L2_BYTES)) == footprint['l2_sha256']
    owners = Counter(e['hart'] for e in h.events if e['kind'] == 'parked-owner-write')
    assert owners == {hart: 2 for hart in range(8)}
    irq_enabled = bool(int(h.plic_snapshot()[0], 16) & (1 << 9))
    assert irq_enabled == (plic == 'banked')
    return dict(schedule=schedule, early_harts=early, bind_after_all_harts=late_bind,
                plic_model=plic, plic_enable=h.plic_snapshot(), irq8_enable_in_model=irq_enabled, workers=workers,
                status_progress=statuses, client=list(host.state), initialization_events=initialized,
                parked_owner_writes=dict(owners), native_allocations=h.allocations,
                coordinator_footprint=footprint, hooks=h.patches,
                no_sidecar_packet_execution=True, release=0, arm=0, drain_mask=0)


def sha_bytes(data):
    return headers.sha(bytes(data))


def cold_failures(paths, parts):
    rows = []
    configurations = [((0, 0), [0] * 5)]
    for word in range(5):
        session = [0] * 5
        session[word] = 0x12340000 + word
        configurations.append((control.BOOT, session))
    for identity, session in configurations:
        h = Composed(paths, parts, boot_id=identity, session=session)
        assert h.reset() == h.rv.symbols['npu_emulation_startup_fault']
        assert h.get32(native.STARTUP + 12) == 3
        assert h.get32(STATE + 16) == h.get32(native.ADM + 8) == 1
        assert h.cpu.mem_read(boot.SESSION, 20) == struct.pack('<5I', *session)
        assert h.get32(native.IRQ8) != h.rv.symbols['npu_emulation_mailbox']
        assert not h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        assert not h.allocations and not h.callback_entries
        h.check_hooks()
        rows.append(dict(identity=list(identity), prior_session=session, common_fault=True,
                         source8_installed=False, native_allocations=0, retained_hooks=50))
    return rows


def allocator_failures(paths, parts):
    rows = []
    for kind in (0x8a, 1, 0x19):
        h, host = Composed(paths, parts, deny_type=kind), control.Host(paths)
        window = h.rv.symbols['npu_emulation_idle_irq_window']
        hold = h.allocator_rv.symbols['npu_emulation_allocator_startup_hold']
        h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
        stopped = h.run(CODE, [0x8400420a, window, hold])
        if stopped == 0x8400420a:
            boot.setup(h)
            control.advance(host, h)
            for boundary in (0x8400d1d4, 0x8400f836):
                stopped = h.run(h.cpu.reg_read(r.UC_RISCV_REG_PC), [boundary, window, hold])
                if stopped != boundary:
                    break
                if boundary == 0x8400d1d4:
                    assert h.cpu.mem_read(L2, L2_BYTES) == bytes(L2_BYTES)
                    h.l2_clear_active = False
        assert stopped == window and h.denied is not None, 'allocator-failure-service-boundary'
        assert not h.executions[h.denied['caller']], 'allocator-failure-returned-to-native-caller'
        assert h.cpu.mem_read(HEAP, HEAP_BYTES) == h.denied['heap'], 'allocator-failure-changed-heap'
        assert h.cpu.mem_read(L2, L2_BYTES) == h.denied['l2'], 'allocator-failure-changed-l2'
        assert h.cpu.mem_read(allocator.NATIVE_STATE, allocator.protocol.STATE_BYTES) == h.denied['metadata']
        assert h.boot_snapshot() == h.denied['bootstrap']
        assert h.get32(STATE + 16) == h.get32(native.ADM + 8) == 1
        assert h.get32(STATE + 4) == h.get32(STATE + 8) == h.get32(STATE + 12) == 0
        result, _, response = control.exchange(host, h)
        assert result == control.REJECTED and response[9] == 6 and response[13] == 0
        assert h.boot_snapshot() == h.denied['bootstrap'] and host.state[12] == 0
        control.held(host)
        h.check_hooks()
        rows.append(dict(type=kind, status=response[9], native_caller=hex(h.denied['caller']),
                         no_return=True, heap_and_allocator_metadata_retained=True,
                         setup_step=h.get32(native.BOOT + 8), diagnostic_operation=response[5],
                         source8_direct_dispatch_serviced=True, drain_mask=0, released=0, armed=0))
        print(json.dumps(dict(stage='allocator-failure', type=kind)), flush=True)
    return rows


def missing_gates(paths, parts):
    h = Composed(paths, parts)
    assert h.reset() == 0x8400420a
    boot.setup(h)
    h.finish_coordinator()
    saved = [(lo, bytes(h.cpu.mem_read(lo, hi - lo + 1))) for lo, hi, _ in h.cpu.mem_regions()]
    banks = deepcopy(h.plic_banks)
    rows = []
    # Each negative control restores the same core0-cold prefix, not a live hart.
    for hart, (site, _, next_, alternate) in sorted(STARTUPS.items()):
        for address, data in saved:
            h.cpu.mem_write(address, data)
        h.plic_banks = deepcopy(banks)
        h.cpu.mem_write(site, h.code[site-CODE:site-CODE+4])
        h.cpu.ctl_remove_cache(CODE, CODE + 0x201000)
        try:
            h.check_hooks()
        except AssertionError as error:
            assert str(error) == 'retained-hook-changed'
        else:
            raise AssertionError('missing-hook-installation-oracle')
        h.hart = hart
        h.cpu.context_restore(h.fresh)
        assert h.reset(site) == site
        poll = h.rv.symbols['npu_barrier_poll']
        stop = h.run(site, [poll, next_, *([alternate] if alternate else [])])
        assert stop != poll and h.get32(STATE + 20 + hart * 4) == 0
        assert [h.get32(STATE + 20 + i * 4) for i in range(8)] == [1] + [0] * 7
        rows.append(dict(hart=hart, removed_hook=hex(site), boundary=hex(stop),
                         installation_oracle_rejected=True, missing_ack=True,
                         postgate_body_executed=False))
    return rows


def fingerprints():
    receipts = [boot.OUT / 'bootstrap-control-v2.json', packets.OUT / 'packet-extents.json']
    inputs = {}
    for path in receipts:
        receipt = json.loads(path.read_text())
        bindings = receipt.get('inputs', receipt.get('inputs_before_after'))
        assert isinstance(bindings, dict)
        for name, digest in bindings.items():
            assert sha(ROOT / name) == digest, ('prior-evidence-input-drift', name)
            inputs[name] = digest
        inputs[str(path.relative_to(ROOT))] = sha(path)
    for module in tuple(sys.modules.values()):
        path = getattr(module, '__file__', None)
        if path and Path(path).resolve().parent == TESTS:
            p = Path(path).resolve()
            inputs[str(p.relative_to(ROOT))] = sha(p)
    sources = [*BASE.glob('*.c'), *BASE.glob('*.h'), *TESTS.glob('*emulation.S'),
               *TESTS.glob('*emulation.c'), *TESTS.glob('*emulation.ld')]
    for p in (boot.PATCH, boot.PLATFORM, boot.LINKER, native.DTB, bridge.GHIDRA, CODE_INPUT,
              ROOT / 'firmware/source-lock.json', ROOT / 'firmware/patches/openwrt.patch',
              ROOT / 'firmware/patches/luci.patch', *sources):
        inputs[str(p.relative_to(ROOT))] = sha(p)
    return inputs


def main():
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--smoke', action='store_true')
    selection.add_argument('--checks-only', action='store_true')
    args = parser.parse_args()
    before = fingerprints()
    paths, parts = build()
    memory = memory_layout(parts)
    if args.checks_only:
        cold_failures(paths, parts)
        allocator_failures(paths, parts)
        controls = missing_gates(paths, parts)
        assert all(sha(ROOT / name) == digest for name, digest in before.items())
        print(json.dumps(dict(stage='checks-only', missing_gates=len(controls))), flush=True)
        return
    schedules = [list(range(8)), list(reversed(range(8))), [7, 3, 1, 0, 6, 2, 5, 4]]
    rows = []
    for schedule in schedules[:1] if args.smoke else schedules:
        rows.append(scenario(paths, parts, schedule))
        print(json.dumps(dict(stage='native-composition', schedule=schedule)), flush=True)
    if args.smoke:
        return
    rows.append(scenario(paths, parts, list(range(8)), late_bind=True))
    print(json.dumps(dict(stage='late-bind')), flush=True)
    rows.append(scenario(paths, parts, list(range(8)), plic='flat'))
    print(json.dumps(dict(stage='flat-plic-limit-control')), flush=True)
    cold = cold_failures(paths, parts)
    print(json.dumps(dict(stage='cold-failures', cases=len(cold))), flush=True)
    failed = allocator_failures(paths, parts)
    omitted = missing_gates(paths, parts)
    print(json.dumps(dict(stage='missing-gates', cases=len(omitted))), flush=True)
    assert all(sha(ROOT / name) == digest for name, digest in before.items())
    result = dict(schema=1, inputs_before_after=before, compiler=execute(['clang', '--version']).splitlines()[0],
                  unicorn=unicorn.__version__, commands=COMMANDS,
                  binaries={str(p.relative_to(ROOT)): sha(p) for p in
                            [*paths, *parts.values(), BUILD / 'stale-v1-bridge-control.elf']},
                  derived={str((BUILD / 'staged/firmware/npu/control-v2.c').relative_to(ROOT)):
                           sha(BUILD / 'staged/firmware/npu/control-v2.c')},
                  memory_layout=memory, scenarios=rows, cold_failures=cold, allocator_failures=failed,
                  missing_gate_controls=omitted, host_comparisons=control.Host.calls,
                  server_comparisons=boot.Bootstrap.comparisons,
                  limits=['All 50 detours installed before native cold reset; only initial parking paths execute.',
                          'Host register publication, MMIO storage, hart-ID CSR and interrupt invocation are explicit models.',
                          'The flat PLIC control loses source8 enable despite direct-dispatch success; physical banking/delivery is unproved.',
                          'Missing-hook controls restore one core0 prefix and stop at the next native gate boundary, without postgate execution.',
                          'No physical PLIC/cache/ownership/drains, production loader, image, router or restricted-selector tests.'])
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / 'bootstrap-composition.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(scenarios=len(rows), host_calls=control.Host.calls,
                          server_calls=boot.Bootstrap.comparisons, receipt_sha256=sha(output))))


if __name__ == '__main__':
    main()
