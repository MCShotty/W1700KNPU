#!/usr/bin/env python3
"""Retained packet claims composed with original lock and RX instructions."""
import argparse
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from unicorn import riscv_const as r
import test_bootstrap_v2_composition as composition
import test_cold_page_native as pages
import test_rx_stats as stats
from test_barrier_core5 import jump
from test_barrier_protocol import Rv32
from test_bootstrap_native import ADM, Bootstrap
from emulation_layout import STATE, HEAP

ROOT, TESTS = pages.ROOT, pages.TESTS
HEAD, TAIL, POOL = 0x3e901ba4, 0x3e901b80, HEAP + 32
GETTER, EXTRA, EXTRA_BYTES = 0x84004d80, 0x84080000, 0x4000
SITES = {GETTER: 'npu_emulation_packet_entry',
         0x84004d92: 'npu_emulation_packet_guard',
         0x8400b7c8: 'npu_emulation_packet_ready0',
         0x8400b8f6: 'npu_emulation_packet_ready2',
         0x8400fe34: 'npu_emulation_packet_callback',
         0x8400b546: 'npu_emulation_packet_txdone_publish'}


def build(dest, parts, rx_path, *, source=None, assembly=None):
    path = dest / 'native-packet.elf'
    command = ['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
               '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
               '-fno-stack-protector', '-nostdlib', '-I' + str(ROOT / 'firmware/npu'),
               ROOT / 'firmware/npu/cold-packet.c',
               source or TESTS / 'cold-packet-native-emulation.c',
               assembly or TESTS / 'cold-packet-native-emulation.S',
               '--ld-path=' + str(shutil.which('ld.lld') or
                                  ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
               '-Wl,-T,' + str(TESTS / 'cold-packet-native-emulation.ld') + ',--no-relax',
               '-Wl,--just-symbols=' + str(parts['allocator']),
               '-Wl,--defsym=npu_emulation_rx_dispatch_live=' +
               hex(composition.symbols(rx_path)['npu_emulation_rx_dispatch_live']),
               '-Wl,--defsym=npu_emulation_rx_stats_callback=' +
               hex(composition.symbols(rx_path)['npu_emulation_rx_stats_callback']),
               '-Wl,--defsym=npu_previous_txdone_callback=' +
               hex(composition.symbols(parts['txdone'])['npu_emulation_txdone_callback']),
               '-Wl,--defsym=npu_previous_txdone_publish_guard=' +
               hex(composition.symbols(parts['txdone'])['npu_emulation_txdone_publish_guard']),
               '-Wl,--defsym=npu_previous_txdone_bufid_guard=' +
               hex(composition.symbols(parts['txdone'])['npu_emulation_txdone_bufid_guard']),
               '-o', path]
    done = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
    (dest / 'build.stdout').write_text(done.stdout)
    (dest / 'build.stderr').write_text(done.stderr)
    assert done.returncode == 0, done.stderr
    composition.check_imports(path, parts['allocator'])
    return path


class NativePackets(stats.RxStats):
    def __init__(self, paths, parts):
        self.packet = None
        self.packet_tracking = False
        self.packet_mode = None
        self.packet_changed = False
        self.packet_writes = []
        self.getter_calls = 0
        super().__init__(paths, parts)

    def check_hooks(self):
        for row in self.patches:
            expected = bytes.fromhex(row['after'])
            assert bytes(self.cpu.mem_read(int(row['site'], 16), len(expected))) == expected, 'retained-hook-changed'

    def install_packet(self, path):
        self.cpu.mem_write(EXTRA, bytes(EXTRA_BYTES))
        self.packet = Rv32(path, self.cpu)
        for site, name in SITES.items():
            length = 6 if site == GETTER else 4
            previous = next((row for row in self.patches if int(row['site'], 16) == site), None)
            target = self.packet.symbols[name]
            after = jump(site, target) + (b'\x01\x00' if length == 6 else b'')
            if previous:
                assert bytes(self.cpu.mem_read(site, length)).hex() == previous['after']
                previous.update(after=after.hex(), target=hex(target))
            else:
                before = self.code[site - composition.CODE:site - composition.CODE + length]
                assert bytes(self.cpu.mem_read(site, length)) == before
                self.patches.append(dict(site=hex(site), before=before.hex(), after=after.hex(), target=hex(target)))
            self.cpu.mem_write(site, after)
        self.cpu.ctl_remove_cache(composition.CODE, composition.CODE + 0x201000)
        self.check_hooks()
        assert len(self.patches) == 63

    def snapshot(self):
        return super().snapshot() + [(EXTRA, bytes(self.cpu.mem_read(EXTRA, EXTRA_BYTES)))]

    def restore(self, saved):
        self.packet_tracking = False
        super().restore(saved)
        self.cpu.ctl_remove_cache(EXTRA, EXTRA + EXTRA_BYTES)
        self.put32(self.allocator_rv.symbols['npu_emulation_callback_guarded'], 0)
        self.put32(0x1ec03070, 0x10000)

    def run(self, start, stops):
        if not self.packet_tracking or start != 0x8400fe34:
            return super().run(start, stops)
        # Resume at each real getter boundary, retaining the existing instruction
        # and wall budgets rather than relaxing them for the larger bitmap.
        pc, chunks = start, 0
        while True:
            pc = super().run(pc, list(stops) + [GETTER])
            chunks += 1
            assert chunks <= self.requested + 3, 'packet-getter-progress'
            if pc != GETTER:
                return pc

    def code_hook(self, cpu, pc, size, data):
        if self.packet_tracking:
            if pc == self.packet.symbols['npu_emulation_packet_entry']:
                self.getter_calls += 1
                if self.packet_mode == 'denied':
                    self.put32(0x1ec03070, 0x10100)
                elif self.packet_mode == 'bad-lock':
                    self.put32(0x3e901b9c, 27)
                elif self.packet_mode == 'bad-pool':
                    self.put32(0x3e901b88, POOL + 2)
                elif self.packet_mode == 'bad-packet-base':
                    self.put32(0x3e90396c, self.get32(0x3e90396c) + 2048)
                elif self.packet_mode == 'worker-unparked':
                    self.put32(STATE + 20 + 4 * 5, 0)
                elif self.packet_mode == 'epoch-at-entry':
                    self.put32(STATE, 2)
                elif self.packet_mode == 'guard-cleared':
                    self.put32(self.allocator_rv.symbols['npu_emulation_callback_guarded'], 0)
                elif self.packet_mode == 'pool-record-changed':
                    self.cpu.mem_write(stats.META + 32, struct.pack('<H', 0x8b))
                    metadata = bytearray(self.at_allocator['metadata'])
                    struct.pack_into('<H', metadata, 32, 0x8b)
                    self.at_allocator['metadata'] = bytes(metadata)
            if not self.packet_changed:
                if self.packet_mode == 'release-fault' and self.getter_calls and pc == 0x8400651c:
                    self.put32(STATE + 16, 1)
                    self.packet_changed = True
                elif self.packet_mode == 'lock-changed-after-grant' and pc == self.packet.symbols['npu_emulation_packet_guard']:
                    self.put32(0x3e901b9c, 27)
                    self.packet_changed = True
                elif self.packet_mode == 'before-ready' and pc in (
                        self.packet.symbols['npu_emulation_packet_ready0'],
                        self.packet.symbols['npu_emulation_packet_ready2']):
                    self.put32(STATE + 16, 1)
                    self.packet_changed = True
        super().code_hook(cpu, pc, size, data)

    def write_hook(self, cpu, access, address, size, value, data):
        if self.packet_tracking:
            self.packet_writes.append((cpu.reg_read(r.UC_RISCV_REG_PC), address, size, value))
            core = self.packet.symbols['npu_emulation_packet_state']
            if not self.packet_changed and address == core + 16 and value == self.claim_trigger:
                if self.packet_mode == 'claim-fault':
                    self.put32(core + 8, 1)
                elif self.packet_mode == 'head-changed':
                    self.cpu.mem_write(HEAD, struct.pack('<H', 37))
                elif self.packet_mode == 'tail-changed':
                    self.cpu.mem_write(TAIL, struct.pack('<H', 3))
                elif self.packet_mode == 'id-changed':
                    self.cpu.mem_write(POOL + 2 * self.head_before, struct.pack('<H', 42))
                    # The whole-heap oracle includes this explicit external fault
                    # injection, not an additional write by the native consumer.
                    if self.at_allocator:
                        heap = bytearray(self.at_allocator['heap'])
                        struct.pack_into('<H', heap, POOL - HEAP + 2 * self.head_before, 42)
                        self.at_allocator['heap'] = bytes(heap)
                else:
                    super().write_hook(cpu, access, address, size, value, data)
                    return
                self.packet_changed = True
            if not self.packet_changed and address == HEAD and size == 2:
                if self.packet_mode == 'published-fault':
                    self.put32(STATE + 16, 1)
                    self.packet_changed = True
        super().write_hook(cpu, access, address, size, value, data)

    def cleared_heap(self, address):
        heap = super().cleared_heap(address)
        mode = self.packet_mode or ''
        success = int(mode in ('claim-fault', 'published-fault', 'release-fault'))
        failure = int(mode.startswith('bad-id-') or mode in (
            'claim-fault', 'head-changed', 'tail-changed', 'id-changed', 'published-fault',
            'bad-native-head', 'bad-native-tail'))
        statistic = self.get32(0x3e901f08)
        for offset, increment in ((0x1c, success), (0x20, failure)):
            if increment:
                position = statistic - HEAP + offset
                old = struct.unpack_from('<I', heap, position)[0]
                struct.pack_into('<I', heap, position, (old + increment) & 0xffffffff)
        return heap

    def invoke_packet(self, selector, count, mode=None):
        self.requested, self.packet_mode, self.packet_changed = count, mode, False
        self.packet_writes, self.getter_calls = [], 0
        core = self.packet.symbols['npu_emulation_packet_state']
        self.claim_trigger = self.get32(core + 16) + 1
        self.head_before = int.from_bytes(self.cpu.mem_read(HEAD, 2), 'little')
        self.put32(0x1ec03070, 0x10000)
        counter = self.get32(0x3e901b90)
        statistic = self.get32(0x3e901f08)
        before = [self.get32(statistic + offset) if statistic else 0 for offset in (0x1c, 0x20)]
        self.packet_tracking = True
        try:
            row = self.invoke_rx(selector, count)
        finally:
            self.packet_tracking = False
        state = struct.unpack('<519I', self.cpu.mem_read(core, 2076))
        release = [w for w in self.packet_writes if w[1] == 0x1ec03270]
        acquire = [w for w in self.packet_writes if w[1] == 0x1ec031f0]
        assert all(w[2:] == (4, 0x40) for w in acquire), 'lock-request-value'
        assert all(w[2:] == (4, 0) for w in release), 'lock-release-value'
        head_writes = [w for w in self.packet_writes if w[1] == HEAD]
        row.update(claimed=state[4], private_head=state[3], packet_fault=state[2],
                   population=sum(w.bit_count() for w in state[7:]),
                   last=list(struct.unpack('<6I', self.cpu.mem_read(self.packet.symbols['npu_emulation_packet_last'], 24))),
                   packet_counter_delta=(self.get32(0x3e901b90) - counter) & 0xffffffff,
                   success_delta=(self.get32(statistic + 0x1c) - before[0]) & 0xffffffff if statistic else 0,
                   failure_delta=(self.get32(statistic + 0x20) - before[1]) & 0xffffffff if statistic else 0,
                   acquire_requests=len(acquire), release_requests=len(release),
                   head_publications=len(head_writes), getter_calls=self.getter_calls,
                   injected=self.packet_changed, packet_mode=mode,
                   head_write_first_last=[list(w) for w in head_writes[:1] + head_writes[-1:]])
        return row


def prepare(paths, parts, page_path, rx_path, packet_path):
    h = NativePackets(paths, parts)
    h.hart = 0
    h.cpu.context_restore(h.fresh)
    assert h.reset() == 0x8400420a
    host = composition.control.Host(paths)
    assert composition.control.exchange(host, h)[0] == composition.control.ACCEPTED
    composition.boot.setup(h, run_clear=True)
    composition.control.advance(host, h)
    h.finish_coordinator()
    for hart in range(1, 8):
        h.worker(hart)
    h.on_core0()
    denied = Bootstrap.message(h, [0x10, 1, 1536])
    assert denied['flags'] == 3 and not denied['callbacks']
    h.put32(ADM + 4, 1)
    h.install(page_path)
    h.install_rx(rx_path)
    h.install_packet(packet_path)
    assert h.get32(0x3e901b88) == POOL
    assert bytes(h.cpu.mem_read(POOL, 32768)) == struct.pack('<16384H', *range(16384))
    status = h.direct(h.packet.symbols['npu_emulation_packet_init'])
    assert status == 0, dict(status=status, head=bytes(h.cpu.mem_read(HEAD, 2)).hex(),
                             tail=bytes(h.cpu.mem_read(TAIL, 2)).hex(),
                             pkt_base=hex(h.get32(0x3e90396c)),
                             plan=list(struct.unpack('<20I', h.cpu.mem_read(stats.BOOT, 80))),
                             records=list(struct.unpack('<62I', h.cpu.mem_read(stats.META, 248))))
    return h, denied


def expected(row, success, claims, descriptors, head, acquires, releases):
    stats.expected(row, success, descriptors, 1, 250)
    assert row['claimed'] == row['population'] == claims, ('packet-retention', row)
    assert row['buffer_head'] == head, ('packet-head', row)
    assert row['acquire_requests'] == acquires and row['release_requests'] == releases, ('packet-lock', row)
    assert row['packet_fault'] == (0 if success else 1), ('packet-fault', row)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--quick', action='store_true', help='Exploratory small rings; receipt is not full-size acceptance')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-cold-packet-native-20261010' / args.name
    assert not dest.exists(), 'Choose a fresh result name'
    dest.mkdir(parents=True)
    paths, parts = composition.build()
    page_dir, rx_dir = dest / 'page-component', dest / 'rx-component'
    page_dir.mkdir()
    rx_dir.mkdir()
    page_path = pages.build(page_dir, parts)
    rx_path = stats.build(rx_dir, parts, page_path)
    packet_path = build(dest, parts, rx_path)
    layout = composition.memory_layout(parts | {'cold-pages': page_path, 'rx-stats': rx_path, 'cold-packets': packet_path})
    h, denied = prepare(paths, parts, page_path, rx_path, packet_path)
    initial = h.snapshot()
    # An unrelated getter still executes its original body, not the RX claim
    # path. Mixed users are not admitted into the claimed cold lifetime.
    other = h.direct(GETTER)
    assert other == 0 and int.from_bytes(h.cpu.mem_read(HEAD, 2), 'little') == 1
    assert h.get32(h.packet.symbols['npu_emulation_packet_state'] + 16) == 0
    assert h.get32(h.packet.symbols['npu_emulation_packet_state'] + 8) == 0
    h.restore(initial)
    valid, controls = [], []
    total = 0
    for selector, count in ((0, 32), (2, 32)) if args.quick else ((0, 1536), (2, 1024)):
        total += count
        row = h.invoke_packet(selector, count)
        expected(row, 1, total, count, total, count, count)
        assert row['packet_counter_delta'] == row['success_delta'] == row['head_publications'] == count
        assert row['failure_delta'] == 0
        valid.append(row)
        print(json.dumps(dict(nominal_selector=selector, descriptors=count, retained_packets=total)), flush=True)
    page_rows = []
    packet_before_pages = bytes(h.cpu.mem_read(h.packet.symbols['npu_emulation_packet_state'], 2076))
    assert h.direct(h.binding.symbols['npu_emulation_page_init']) == 0
    page_total = 0
    for selector, count in pages.COUNTS.items():
        if args.quick:
            count = 16
        page_total += count
        row = h.invoke(selector, count)
        pages.check(row, 1, page_total, count, page_total)
        page_rows.append(row)
    assert bytes(h.cpu.mem_read(h.packet.symbols['npu_emulation_packet_state'], 2076)) == packet_before_pages
    print(json.dumps(dict(independent_ba_claims=page_total, packet_state_unchanged=True)), flush=True)
    modes = ('denied', 'bad-lock', 'bad-pool', 'bad-packet-base',
             'bad-id-16384', 'bad-id-32768', 'bad-id-65535', 'duplicate', 'partial-pool',
             'claim-fault', 'head-changed', 'tail-changed', 'id-changed',
             'published-fault', 'release-fault', 'lock-changed-after-grant', 'before-ready',
             'bad-native-head', 'bad-native-tail', 'bad-private-plan', 'bad-magic',
             'worker-unparked', 'epoch-at-entry', 'guard-cleared', 'pool-record-changed')
    for selector in (0, 2):
        for mode in modes:
            h.restore(initial)
            if mode == 'partial-pool':
                h.cpu.mem_write(TAIL, struct.pack('<H', 18))
            elif mode.startswith('bad-id-'):
                h.cpu.mem_write(POOL, struct.pack('<H', int(mode[7:])))
            elif mode == 'duplicate':
                h.cpu.mem_write(POOL + 2, struct.pack('<H', 0))
            elif mode == 'bad-native-head':
                h.cpu.mem_write(HEAD, struct.pack('<H', 16384))
            elif mode == 'bad-native-tail':
                h.cpu.mem_write(TAIL, struct.pack('<H', 16384))
            elif mode == 'bad-private-plan':
                plan = h.packet.symbols['npu_emulation_packet_plan']
                h.put32(plan, h.get32(plan) + 2048)
            elif mode == 'bad-magic':
                h.put32(h.packet.symbols['npu_emulation_packet_state'], 0)
            row = h.invoke_packet(selector, 32, mode)
            claims = 32 if mode == 'before-ready' else 17 if mode == 'partial-pool' else 1 if mode in (
                'duplicate', 'claim-fault', 'head-changed', 'tail-changed', 'id-changed',
                'published-fault', 'release-fault') else 0
            descriptors = 32 if mode == 'before-ready' else 17 if mode == 'partial-pool' else 1 if mode == 'duplicate' else 0
            head = 16384 if mode == 'bad-native-head' else 37 if mode == 'head-changed' else 0 if mode in ('tail-changed', 'id-changed') else claims
            requests = 0 if mode in ('bad-lock', 'bad-pool', 'bad-packet-base', 'bad-magic',
                                     'worker-unparked', 'epoch-at-entry', 'guard-cleared', 'pool-record-changed') else 32 if mode == 'before-ready' else 18 if mode == 'partial-pool' else 2 if mode == 'duplicate' else 1
            expected(row, 0, claims, descriptors, head, requests, 0 if mode == 'denied' else requests)
            assert row['head_publications'] == row['packet_counter_delta'] == row['success_delta'] == (
                0 if mode in ('head-changed', 'tail-changed', 'id-changed') else claims), ('packet-counter', row)
            controls.append(row)
            print(json.dumps(dict(selector=selector, packet_control=mode, passed=True)), flush=True)
        print(json.dumps(dict(control_selector=selector, cases=len(modes))), flush=True)
    source_text = (TESTS / 'cold-packet-native-emulation.c').read_text()
    assembly_text = (TESTS / 'cold-packet-native-emulation.S').read_text()
    mutations = (
        ('omit-lock-denial', 'source', 'if (acquired) {', 'if ((void)acquired, 0) {', 'denied'),
        ('omit-pool-identity', 'source', 'valid_pool(pool) && (!pool_snapshot || pool == pool_snapshot)',
         '(valid_pool(pool), 1)', 'bad-pool'),
        ('omit-post-release-fault', 'source', 'load(&npu_emulation_packet_state.fault) || !context()', '0', 'release-fault'),
        ('omit-ready-gate', 'assembly', 'beqz a0, .Lready_fail\\@', 'nop', 'before-ready'),
        ('omit-entry-gate', 'assembly', 'beqz a0, .Lentry_failed', 'nop', 'bad-lock'),
        ('release-mutable-lock', 'source', '&npu_emulation_packet_lock_id);', '(const uint32_t *)(uintptr_t)LOCK);', 'lock-changed-after-grant'),
    )
    mutants = []
    from test_boot_irq_installation import UnmodeledAccess
    for name, kind, old, new, mode in mutations:
        directory = dest / name
        directory.mkdir()
        text = source_text if kind == 'source' else assembly_text
        assert old in text
        mutated = directory / ('mutant.c' if kind == 'source' else 'mutant.S')
        mutated.write_text(text.replace(old, new))
        alternative = build(directory, parts, rx_path, **{kind: mutated})
        h.restore(initial)
        h.install_packet(alternative)
        # Installation zeroes the new module's BSS. Initialize the mutant's
        # own state, or an unrelated missing-magic guard can hide the defect.
        assert h.direct(h.packet.symbols['npu_emulation_packet_init']) == 0
        assert h.get32(h.packet.symbols['npu_emulation_packet_state']) == 0x314b5043
        assert h.get32(h.packet.symbols['npu_emulation_packet_state'] + 16) == 0
        try:
            row = h.invoke_packet(0, 16, mode)
            requests = 0 if mode in ('bad-lock', 'bad-pool') else 16 if mode == 'before-ready' else 1
            expected(row, 0, 16 if mode == 'before-ready' else 1 if mode == 'release-fault' else 0,
                     16 if mode == 'before-ready' else 0, 16 if mode == 'before-ready' else 1 if mode == 'release-fault' else 0,
                     requests, 0 if mode == 'denied' else requests)
        except UnmodeledAccess as exc:
            assert name == 'release-mutable-lock' and '0x1ec0326c/' in str(exc), exc
            mutants.append(dict(name=name, rejected_by='wrong-lock-release-mmio'))
        except AssertionError as exc:
            reason = exc.args[0][0] if isinstance(exc.args[0], tuple) else exc.args[0]
            assert reason in ('outer-status', 'ready-status', 'native-writes', 'packet-retention',
                              'packet-head', 'packet-lock', 'packet-fault'), exc
            mutants.append(dict(name=name, rejected_by=reason))
        else:
            raise AssertionError(('surviving-packet-mutant', name))
    sources = [ROOT / 'firmware/npu/cold-page.c', ROOT / 'firmware/npu/cold-packet.c',
               ROOT / 'firmware/npu/cold-packet.h', TESTS / 'cold-packet-native-emulation.c',
               TESTS / 'cold-packet-native-emulation.S', TESTS / 'cold-packet-native-emulation.ld',
               TESTS / 'test_rx_stats.py', Path(__file__)]
    result = dict(passed=True, full_nominal=not args.quick, hooks=63, nominal=valid, controls=controls, rejected_mutants=mutants,
                  independent_pages=page_rows, unrelated_getter_return=other,
                  strict_denial=denied, composition_layout=layout,
                  inputs={str(p.relative_to(ROOT)): composition.sha(p) for p in sources},
                  binaries={str(p.relative_to(ROOT)): composition.sha(p) for p in [*paths, *parts.values(), page_path, rx_path, packet_path]},
                  limits=['Original RX/lock instructions with retained cold packet claims; explicit modeled grant/storage and held lease.',
                          'No hot release/recycle,real loader/vendor-blob installation,physical backing/coherency/drain or client proof.',
                          'Full strict setup is still denied; other packet users retain the existing TXDONE route.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, hooks=63, nominal=2, controls=len(controls), mutants=len(mutants), receipt=str(dest / 'result.json'))))


if __name__ == '__main__':
    main()
