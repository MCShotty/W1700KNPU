#!/usr/bin/env python3
"""Checked active RX statistics allocation with original native clear/RX code."""
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
from test_barrier_core5 import jump
from test_barrier_protocol import Rv32
from test_bootstrap_native import ADM, BOOT, Bootstrap
from test_firmware_mailbox_dispatch import PAYLOAD
from test_firmware_memory_layout import STACK_TOPS
from test_firmware_stop_counterexample import END
from emulation_layout import STATE, HEAP, HEAP_BYTES

ROOT, TESTS = pages.ROOT, pages.TESTS
META, META_BYTES = 0x3e901bcc, 824
FLAGS, SLOTS = {0: 0x3e902a84, 2: 0x3e904588}, {0: 0x3e901f04, 2: 0x3e901f18}
SITES = {0x8400fe34: 'npu_emulation_rx_stats_callback',
         0x8400a3ae: 'npu_emulation_rx_stats0', 0x8400a39a: 'npu_emulation_rx_stats2',
         0x8400ddc0: 'npu_emulation_rx_dispatch0', 0x8400ddd6: 'npu_emulation_rx_dispatch2',
         0x8400b7c8: 'npu_emulation_rx_ready0', 0x8400b8f6: 'npu_emulation_rx_ready2'}


def build(dest, parts, page_path, source=None, assembly=None):
    path = dest / 'rx-stats.elf'
    page_symbol = composition.symbols(page_path)['npu_emulation_page_callback']
    command = ['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
               '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
               '-fno-stack-protector', '-nostdlib', '-I' + str(ROOT / 'firmware/npu'),
               source or TESTS / 'rx-stats-emulation.c', assembly or TESTS / 'rx-stats-emulation.S',
               '--ld-path=' + str(shutil.which('ld.lld') or
                                  ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
               '-Wl,-T,' + str(TESTS / 'rx-stats-emulation.ld') + ',--no-relax',
               '-Wl,--just-symbols=' + str(parts['allocator']),
               '-Wl,--defsym=npu_emulation_page_callback=' + hex(page_symbol), '-o', path]
    done = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
    (dest / 'build.stdout').write_text(done.stdout)
    (dest / 'build.stderr').write_text(done.stderr)
    assert done.returncode == 0, done.stderr
    composition.check_imports(path, parts['allocator'])
    return path


class RxStats(pages.NativePages):
    def __init__(self, paths, parts):
        self.rx = None
        self.rx_tracking = False
        self.mode = None
        self.changed = False
        self.rx_writes = []
        self.at_allocator = None
        super().__init__(paths, parts)

    def install_rx(self, path):
        self.cpu.mem_write(0x8407c000, bytes(0x4000))
        self.rx = Rv32(path, self.cpu)
        for site, name in SITES.items():
            previous = next((row for row in self.patches if int(row['site'], 16) == site), None)
            target = self.rx.symbols[name]
            after = jump(site, target)
            if previous:
                assert bytes(self.cpu.mem_read(site, 4)).hex() == previous['after']
                previous.update(after=after.hex(), target=hex(target))
                self.cpu.mem_write(site, after)
            else:
                self.install_site(site, target, self.code[site - composition.CODE:site - composition.CODE + 4].hex())
        self.cpu.ctl_remove_cache(composition.CODE, composition.CODE + 0x201000)
        self.check_hooks()
        assert len(self.patches) == 62

    def code_hook(self, cpu, pc, size, data):
        if self.rx_tracking:
            if pc == 0x84005200 and cpu.reg_read(r.UC_RISCV_REG_A0) in (9, 10):
                if self.mode == 'denied':
                    self.put32(0x1ec03048, 0x10100)
                elif self.mode == 'corrupt-count':
                    self.put32(META + 8, 101)
                elif self.mode == 'bad-lock':
                    self.put32(META, 19)
                elif self.mode == 'wrong-type':
                    cpu.reg_write(r.UC_RISCV_REG_A0, 8)
                elif self.mode == 'epoch-at-getter':
                    self.put32(STATE, 2)
                self.at_allocator = dict(metadata=bytes(self.cpu.mem_read(META, META_BYTES)),
                                         heap=bytes(self.cpu.mem_read(HEAP, HEAP_BYTES)))
            elif self.mode == 'release-fault' and self.at_allocator and not self.changed and pc == 0x8400651c:
                self.put32(STATE + 16, 1)
                self.changed = True
            if not self.changed and self.mode == 'corrupt-result' and pc in (
                    self.rx.symbols['npu_emulation_rx_stats0'], self.rx.symbols['npu_emulation_rx_stats2']):
                cpu.reg_write(r.UC_RISCV_REG_A0, cpu.reg_read(r.UC_RISCV_REG_A0) + 32)
                self.changed = True
            if not self.changed and self.mode == 'before-clear' and pc in (
                    self.rx.symbols['npu_emulation_rx_stats0'], self.rx.symbols['npu_emulation_rx_stats2']):
                self.put32(STATE + 16, 1)
                self.changed = True
            if not self.changed and self.mode == 'before-ready' and pc in (
                    self.rx.symbols['npu_emulation_rx_ready0'], self.rx.symbols['npu_emulation_rx_ready2']):
                self.put32(STATE + 16, 1)
                self.changed = True
        super().code_hook(cpu, pc, size, data)

    def write_hook(self, cpu, access, address, size, value, data):
        if self.rx_tracking:
            pc = cpu.reg_read(r.UC_RISCV_REG_PC)
            self.rx_writes.append((pc, address, size, value))
            if not self.changed and self.mode == 'during-clear' and pc == 0x8400a384:
                self.put32(STATE + 16, 1)
                self.changed = True
        super().write_hook(cpu, access, address, size, value, data)

    def cleared_heap(self, address):
        heap = bytearray(self.at_allocator['heap'])
        heap[address - HEAP:address - HEAP + 1000] = bytes(1000)
        return heap

    def invoke_rx(self, selector, count, mode=None):
        self.mode, self.changed = mode, False
        self.at_allocator = None
        self.rx_writes = []
        self.getters, self.fallbacks = [], []
        self.put32(0x1ec03048, 0x10000)
        self.unmodeled = None
        count_before = self.get32(META + 8)
        self.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x10 | selector, 1, count))
        for register, value in ((r.UC_RISCV_REG_SP, STACK_TOPS[0]),
                                (r.UC_RISCV_REG_RA, END), (r.UC_RISCV_REG_A0, PAYLOAD),
                                (r.UC_RISCV_REG_MSTATUS, 0)):
            self.cpu.reg_write(register, value)
        self.rx_tracking = self.probing = True
        hold = self.allocator_rv.symbols['npu_emulation_allocator_startup_hold']
        try:
            stop = self.run(0x8400fe34, [hold])
            assert stop == END, ('unexpected-statistics-hold', hex(stop))
            returned = self.cpu.reg_read(r.UC_RISCV_REG_A0)
        finally:
            self.rx_tracking = self.probing = False
        address = self.get32(SLOTS[selector])
        clears = [row for row in self.rx_writes if row[0] == 0x8400a384]
        descriptors = [row for row in self.rx_writes if row[0] in (0x8400b75c, 0x8400b88a)]
        ready = [row for row in self.rx_writes if row[1] == FLAGS[selector] and row[3] == 1]
        metadata = bytes(self.cpu.mem_read(META, META_BYTES))
        if clears:
            assert len(clears) == 250 and all(row[1:] == (address + 4 * i, 4, 0)
                                            for i, row in enumerate(clears)), ('statistics-clear-extent', mode)
        if descriptors:
            ring = self.get32(0x3e902ce0 if selector else 0x3e902ab0)
            ids = 0x3e903100 if selector else 0x3e90397c
            packet = self.get32(0x3e90396c)
            for i in range(len(descriptors)):
                ident = int.from_bytes(self.cpu.mem_read(ids + 2 * i, 2), 'little')
                words = struct.unpack('<4I', self.cpu.mem_read(ring + i * 16, 16))
                assert words == (packet + ident * 2048 + 128, 0x7000100, ident << 16, 0), ('descriptor-bytes', mode, i)
        if self.at_allocator:
            prediction = bytearray(self.at_allocator['metadata'])
            if mode not in ('denied', 'corrupt-count', 'bad-lock', 'wrong-type', 'epoch-at-getter'):
                records, attempts, used = (struct.unpack_from('<I', prediction, offset)[0]
                                           for offset in (8, 16, 20))
                begin = (used + 31) & ~31
                struct.pack_into('<HHI', prediction, 24 + records * 8, 9 if selector else 10, 0, HEAP + begin)
                struct.pack_into('<I', prediction, 8, records + 1)
                struct.pack_into('<II', prediction, 16, attempts + 1, begin + 1000)
            assert metadata == prediction, ('metadata-oracle', mode)
        if self.at_allocator and not clears:
            assert bytes(self.cpu.mem_read(HEAP, HEAP_BYTES)) == self.at_allocator['heap'], 'failed-statistics-caller-wrote-heap'
        if self.at_allocator and clears and not descriptors:
            assert bytes(self.cpu.mem_read(HEAP, HEAP_BYTES)) == self.cleared_heap(address), ('statistics-only-heap-footprint', mode)
        self.check_hooks()
        return dict(selector=selector, count=count, mode=mode, returned=returned,
                    record_count=self.get32(META + 8), records_before=count_before,
                    records_added=self.get32(META + 8) - count_before,
                    statistics_address=address, clear_stores=len(clears),
                    descriptor_stores=len(descriptors), ready=self.get32(FLAGS[selector]),
                    ready_one_stores=len(ready), active=self.get32(ADM + 4),
                    admission_fault=self.get32(ADM + 8), barrier_fault=self.get32(STATE + 16),
                    buffer_head=int.from_bytes(self.cpu.mem_read(0x3e901ba4, 2), 'little'),
                    guarded=self.get32(self.allocator_rv.symbols['npu_emulation_callback_guarded']),
                    metadata_sha256=composition.packets.headers.sha(metadata),
                    checked_getter_entries=self.getters, unchecked_fallback_entries=self.fallbacks,
                    first_last_clear=[list(row) for row in clears[:1] + clears[-1:]])


def prepare(paths, parts):
    h = RxStats(paths, parts)
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
    return h, denied


def expected(row, success, descriptors, records, clears):
    assert row['returned'] == success, ('outer-status', row)
    assert row['ready'] == row['ready_one_stores'] == success, ('ready-status', row)
    assert row['descriptor_stores'] == descriptors and row['clear_stores'] == clears, ('native-writes', row)
    assert row['records_added'] == records, ('allocation-retention', row)
    assert row['active'] == 1 and row['guarded'] == 0, ('lease-retention', row)
    assert (row['admission_fault'], row['barrier_fault']) == ((0, 0) if success else (1, 1))
    assert not any(entry['caller'] in ('0x8400a3ae', '0x8400a39a')
                   for entry in row['unchecked_fallback_entries']), ('unchecked-statistics-fallback', row)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-rx-stats-20261010' / args.name
    assert not dest.exists(), 'Choose a fresh result name'
    dest.mkdir(parents=True)
    paths, parts = composition.build()
    page_dir = dest / 'page-component'
    page_dir.mkdir()
    page_path = pages.build(page_dir, parts)
    path = build(dest, parts, page_path)
    composition.memory_layout(parts | {'cold-pages': page_path, 'rx-stats': path})
    h, denied = prepare(paths, parts)
    h.install(page_path)
    h.install_rx(path)
    initial = h.snapshot()
    valid, controls = [], []
    for selector, count in ((0, 1536), (2, 1024)):
        row = h.invoke_rx(selector, count)
        expected(row, 1, count, 1, 250)
        assert bytes(h.cpu.mem_read(row['statistics_address'], 1000)) == bytes(1000)
        valid.append(row)
        print(json.dumps(dict(nominal_selector=selector, descriptors=count, checked_statistics=True)), flush=True)
    for selector in (0, 2):
        for mode in ('denied', 'corrupt-count', 'bad-lock', 'wrong-type', 'epoch-at-getter',
                     'release-fault', 'before-clear', 'during-clear', 'before-ready', 'partial-pool',
                     'corrupt-result', 'zero-count', 'oversize-count'):
            h.restore(initial)
            # The guard flag is callback-local state outside the native SRAM snapshot.
            h.put32(h.allocator_rv.symbols['npu_emulation_callback_guarded'], 0)
            if mode == 'partial-pool':
                h.cpu.mem_write(0x3e901b80, struct.pack('<H', 18))
            count = 0 if mode == 'zero-count' else (1025 if selector else 1537) if mode == 'oversize-count' else 32
            row = h.invoke_rx(selector, count, mode)
            added = 0 if mode in ('denied', 'bad-lock', 'wrong-type', 'epoch-at-getter',
                                 'zero-count', 'oversize-count') else 1
            if mode == 'corrupt-count':
                assert row['record_count'] == 101 and not row['clear_stores'] and not row['descriptor_stores']
                assert row['returned'] == row['ready'] == 0 and row['active'] == 1
            else:
                expected(row, 0, 32 if mode == 'before-ready' else 17 if mode == 'partial-pool' else 0,
                         added, 250 if mode in ('during-clear', 'before-ready', 'partial-pool') else 0)
            controls.append(row)
        print(json.dumps(dict(control_selector=selector, cases=13)), flush=True)
    source_text = (TESTS / 'rx-stats-emulation.c').read_text()
    assembly_text = (TESTS / 'rx-stats-emulation.S').read_text()
    mutations = (
        ('omit-statistics-unwind', 'assembly', 'beqz t0, .Lstats_fail\\@', 'nop', 'denied'),
        ('omit-dispatcher-lifetime-guard', 'assembly', 'beqz t0, .Ldispatch_fail\\@', 'nop', 'during-clear'),
        ('omit-ready-lifetime-guard', 'assembly', 'beqz a0, .Lready_fail\\@', 'nop', 'before-ready'),
        ('always-success-wrapper', 'source', 'return result;', 'return 1;', 'denied'),
        ('omit-allocation-identity', 'source',
         'if (state->entries[i].type == type && !state->entries[i].reserved &&\n            state->entries[i].address == address)',
         'if (i == 0)', 'corrupt-result'),
        ('omit-count-limit', 'source', 'snapshot.value > (selector ? 1024u : 1536u)', '0', 'oversize-count'),
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
        alternative = build(directory, parts, page_path, **{kind: mutated})
        h.restore(initial)
        h.put32(h.allocator_rv.symbols['npu_emulation_callback_guarded'], 0)
        h.install_rx(alternative)
        selector, count = (2, 1025) if mode == 'oversize-count' else (0, 16)
        try:
            row = h.invoke_rx(selector, count, mode)
            expected(row, 0, count if mode == 'before-ready' else 0,
                     0 if mode in ('denied', 'oversize-count') else 1,
                     250 if mode in ('during-clear', 'before-ready') else 0)
        except UnmodeledAccess as exc:
            assert name == 'omit-statistics-unwind' and '0x0/' in str(exc), exc
            mutants.append(dict(name=name, rejected_by='native-null-clear'))
        except AssertionError as exc:
            reason = exc.args[0][0] if isinstance(exc.args[0], tuple) else exc.args[0]
            assert reason in ('outer-status', 'ready-status', 'native-writes', 'allocation-retention',
                              'lease-retention', 'metadata-oracle', 'failed-statistics-caller-wrote-heap'), exc
            mutants.append(dict(name=name, rejected_by=reason))
        else:
            raise AssertionError(('surviving-statistics-mutant', name))
    sources = [ROOT / 'firmware/npu/allocator.c', ROOT / 'firmware/npu/allocator.h',
               TESTS / 'allocator-startup-emulation.c', TESTS / 'allocator-startup-emulation.S',
               TESTS / 'rx-stats-emulation.c', TESTS / 'rx-stats-emulation.S',
               TESTS / 'rx-stats-emulation.ld', Path(__file__)]
    result = dict(passed=True, hooks=62, nominal=valid, controls=controls,
                  rejected_mutants=mutants, strict_denial=denied,
                  inputs={str(p.relative_to(ROOT)): composition.sha(p) for p in sources},
                  binaries={str(p.relative_to(ROOT)): composition.sha(p) for p in [*paths, *parts.values(), page_path, path]},
                  limits=['Original statistics clear and RX initializer instructions with checked active allocation and unwind/readiness guards.',
                          'Explicit held direct callback lease and modeled storage/parked workers;strict full setup remains closed.',
                          'Packet-ID exclusive ownership,hot lifecycle,physical backing/coherency/drains and client acceptance remain open.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, hooks=62, nominal=2, controls=len(controls), receipt=str(dest / 'result.json'))))


if __name__ == '__main__':
    main()
