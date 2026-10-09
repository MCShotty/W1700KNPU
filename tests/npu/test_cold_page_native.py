#!/usr/bin/env python3
"""Actual cold ownership C composed with selected original native page callers."""
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
from test_cold_page_caller import Caller
from test_barrier_core5 import jump
from test_barrier_protocol import Rv32
from test_bootstrap_native import ADM, BOOT, Bootstrap
from test_firmware_mailbox_dispatch import PAYLOAD
from test_firmware_memory_layout import STACK_TOPS
from test_firmware_stop_counterexample import END
from test_attach_rx_callbacks import IMAGES
from emulation_layout import STATE

ROOT = Path(__file__).resolve().parents[2]
TESTS, CORE = ROOT / 'tests/npu', ROOT / 'firmware/npu'
HEAD, TAIL, POOL = 0x3e903950, 0x3e901f40, 0x3e8a9c70
GETTER = 0x8400bb9c
FLAGS = {5: 0x3e901f44, 6: 0x3e903954, 7: 0x3e902ce8}
COUNTS = {5: 256, 6: 512, 7: 1024}
SLOTS = {5: 0x3e902a94, 6: 0x3e902aa4, 7: 0x3e904638}
SITES = {0x8400fe34: 'npu_emulation_page_callback', GETTER: 'npu_emulation_page_get_dispatch',
         0x8400bd62: 'npu_emulation_page_ready5', 0x8400bd86: 'npu_emulation_page_ready6',
         0x8400bd48: 'npu_emulation_page_ready7'}
EXTRA_START, EXTRA_BYTES = 0x84078000, 0x4000


def build(dest, parts, *, core=None, binding=None, assembly=None):
    path = dest / 'native-page.elf'
    command = ['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
               '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
               '-fno-stack-protector', '-nostdlib', '-I' + str(CORE),
               core or CORE / 'cold-page.c', binding or TESTS / 'cold-page-native-emulation.c',
               assembly or TESTS / 'cold-page-native-emulation.S',
               '--ld-path=' + str(shutil.which('ld.lld') or
                                  ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
               '-Wl,-T,' + str(TESTS / 'cold-page-native-emulation.ld') + ',--no-relax',
               '-Wl,--just-symbols=' + str(parts['base']),
               '-Wl,--defsym=npu_emulation_txdone_callback=' +
               hex(composition.symbols(parts['txdone'])['npu_emulation_txdone_callback']),
               '-o', path]
    done = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
    (dest / 'build.stdout').write_text(done.stdout)
    (dest / 'build.stderr').write_text(done.stderr)
    assert done.returncode == 0, done.stderr
    composition.check_imports(path, parts['base'])
    return path


class NativePages(Caller):
    def __init__(self, paths, parts):
        self.tracking = False
        self.inject = None
        self.injected = False
        self.writes = []
        self.binding = None
        super().__init__(paths, parts)

    def install(self, path):
        self.cpu.mem_write(EXTRA_START, bytes(EXTRA_BYTES))
        self.binding = Rv32(path, self.cpu)
        for site, name in SITES.items():
            previous = next((row for row in self.patches if int(row['site'], 16) == site), None)
            target = self.binding.symbols[name]
            after = jump(site, target)
            if previous:
                assert bytes(self.cpu.mem_read(site, 4)).hex() == previous['after']
                previous.update(after=after.hex(), target=hex(target))
                self.cpu.mem_write(site, after)
            else:
                self.install_site(site, target, self.code[site - composition.CODE:site - composition.CODE + 4].hex())
        self.cpu.ctl_remove_cache(composition.CODE, composition.CODE + 0x201000)
        self.check_hooks()
        assert len(self.patches) == 54

    def code_hook(self, cpu, pc, size, data):
        if self.tracking and self.inject == 'before-ready' and not self.injected and pc in (
                self.binding.symbols['npu_emulation_page_ready5'],
                self.binding.symbols['npu_emulation_page_ready6'],
                self.binding.symbols['npu_emulation_page_ready7']):
            self.put32(STATE + 16, 1)
            self.injected = True
        if self.probing and pc == 0x8400dd82 and cpu.reg_read(r.UC_RISCV_REG_A1) in FLAGS:
            self.executions[pc] += 1
            super(composition.Composed, self).code_hook(cpu, pc, size, data)
            return
        super().code_hook(cpu, pc, size, data)

    def write_hook(self, cpu, access, address, size, value, data):
        if self.tracking:
            self.writes.append((cpu.reg_read(r.UC_RISCV_REG_PC), address, size, value))
            core = self.binding.symbols['npu_emulation_page_state']
            if not self.injected and address == core + 16 and value == self.claim_trigger:
                if self.inject == 'claim-fault':
                    self.put32(core + 8, 1)
                elif self.inject == 'head-changed':
                    self.cpu.mem_write(HEAD, struct.pack('<H', 37))
                elif self.inject == 'tail-changed':
                    self.cpu.mem_write(TAIL, struct.pack('<H', 3))
                elif self.inject == 'id-changed':
                    self.cpu.mem_write(POOL + 2 * self.head_before, struct.pack('<H', 42))
                else:
                    super().write_hook(cpu, access, address, size, value, data)
                    return
                self.injected = True
            if not self.injected and address == HEAD and size == 2:
                if self.inject == 'published-barrier-fault':
                    self.put32(STATE + 16, 1)
                    self.injected = True
                elif self.inject == 'published-core-fault':
                    self.put32(core + 8, 1)
                    self.injected = True
        super().write_hook(cpu, access, address, size, value, data)

    def snapshot(self):
        return [(base, bytes(self.cpu.mem_read(base, size))) for base, size in
                (*IMAGES, (EXTRA_START, EXTRA_BYTES))]

    def restore(self, saved):
        self.tracking = self.probing = False
        for base, image in saved:
            self.cpu.mem_write(base, image)
        self.cpu.ctl_remove_cache(EXTRA_START, EXTRA_START + EXTRA_BYTES)

    def direct(self, target, *arguments):
        for i, value in enumerate(arguments):
            self.cpu.reg_write(getattr(r, 'UC_RISCV_REG_A' + str(i)), value)
        self.cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[0])
        self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        assert self.run(target, []) == END
        return self.cpu.reg_read(r.UC_RISCV_REG_A0)

    def invoke(self, selector, count, *, inject=None):
        self.inject, self.injected = inject, False
        core = self.binding.symbols['npu_emulation_page_state']
        self.claim_trigger = self.get32(core + 16) + 1
        self.head_before = int.from_bytes(self.cpu.mem_read(HEAD, 2), 'little')
        self.writes = []
        stats = self.get32(0x3e901f08)
        stats_before = self.get32(stats + 0x48) if stats else 0
        self.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x10 | selector, 1, count))
        for register, value in ((r.UC_RISCV_REG_SP, STACK_TOPS[0]),
                                (r.UC_RISCV_REG_RA, END), (r.UC_RISCV_REG_A0, PAYLOAD),
                                (r.UC_RISCV_REG_MSTATUS, 0)):
            self.cpu.reg_write(register, value)
        self.probing = self.tracking = True
        try:
            pc, steps = 0x8400fe34, 0
            while pc != END:
                pc = self.run(pc, [GETTER])
                steps += 1
                assert steps <= count + 2
            value = self.cpu.reg_read(r.UC_RISCV_REG_A0)
        finally:
            self.probing = self.tracking = False
        state = struct.unpack('<263I', self.cpu.mem_read(core, 1052))
        last = struct.unpack('<6I', self.cpu.mem_read(self.binding.symbols['npu_emulation_page_last'], 24))
        ring = self.get32(SLOTS[selector])
        descriptors = [(pc, address, size, value) for pc, address, size, value in self.writes
                       if pc == 0x8400bc9c]
        ready = [(pc, address, value) for pc, address, size, value in self.writes
                 if address == FLAGS[selector] and value == 1]
        self.check_hooks()
        return dict(selector=selector, requested=count, returned=value,
                    claimed=state[4], private_head=state[3], fault=state[2],
                    native_head=int.from_bytes(self.cpu.mem_read(HEAD, 2), 'little'),
                    bitmap_population=sum(word.bit_count() for word in state[7:]),
                    success_statistics_delta=(self.get32(stats + 0x48) - stats_before) & 0xffffffff if stats else 0,
                    descriptors=len(descriptors), ready=int(self.get32(FLAGS[selector])),
                    ready_one_writes=len(ready), last=list(last),
                    barrier_fault=self.get32(STATE + 16), active=self.get32(ADM + 4),
                    admission_fault=self.get32(ADM + 8), ring=ring, injected=self.injected,
                    descriptor_first_last=[list(row) for row in descriptors[:1] + descriptors[-1:]])


def prepared(paths, parts):
    h = NativePages(paths, parts)
    h.hart = 0
    h.cpu.context_restore(h.fresh)
    assert h.reset() == 0x8400420a
    host = composition.control.Host(paths)
    assert composition.control.exchange(host, h)[0] == composition.control.ACCEPTED
    composition.boot.setup(h, run_clear=True)
    composition.control.advance(host, h)
    h.finish_coordinator()
    workers = [h.worker(hart) for hart in range(1, 8)]
    h.on_core0()
    denied = Bootstrap.message(h, [0x15, 1, 256])
    assert denied['flags'] == 3 and not denied['callbacks']
    h.put32(ADM + 4, 1)
    for selector, count in ((0, 1536), (2, 1024)):
        h.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x10 | selector, 1, count))
        h.probing = True
        assert h.direct(0x8400fe34, PAYLOAD) == 1
        h.probing = False
    assert h.get32(0x3e904634) == POOL
    assert bytes(h.cpu.mem_read(POOL, 16384)) == struct.pack('<8192H', *range(8192))
    return h, workers, denied


def check(row, returned, claims, descriptors, head, *, injected=False):
    assert row['returned'] == returned, ('callback-result', row)
    assert row['claimed'] == row['bitmap_population'] == claims, ('retained-claims', row)
    assert row['descriptors'] == descriptors and row['native_head'] == head, ('publication', row)
    assert row['ready'] == returned and row['ready_one_writes'] == returned, ('ready-gate', row)
    assert row['active'] == 1 and row['injected'] == injected, ('caller-lease', row)
    assert (row['fault'], row['barrier_fault'], row['admission_fault']) == ((0, 0, 0) if returned else (1, 1, 1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-cold-page-native-20261010' / args.name
    assert not dest.exists(), 'Choose a fresh result name'
    dest.mkdir(parents=True)
    paths, parts = composition.build()
    path = build(dest, parts)
    composition.memory_layout(parts | {'cold-pages': path})
    h, workers, denied = prepared(paths, parts)
    h.install(path)
    assert h.direct(h.binding.symbols['npu_emulation_page_init']) == 0
    initial = h.snapshot()
    valid, controls = [], []
    total = 0
    for selector, count in COUNTS.items():
        total += count
        row = h.invoke(selector, count)
        check(row, 1, total, count, total)
        assert row['success_statistics_delta'] == count
        for index in range(count):
            ident = total - count + index
            words = struct.unpack('<4I', h.cpu.mem_read(row['ring'] + index * 16, 16))
            assert words == (0x90c0e000 + ident * 128, 0x800100, ident << 16, 0)
        valid.append(row)
        print(json.dumps(dict(nominal_selector=selector, claims=total)), flush=True)
    for selector in COUNTS:
        for kind in ('empty', 'partial', 'duplicate', 'invalid-id', 'bad-count', 'claim-fault',
                     'head-changed', 'tail-changed', 'id-changed', 'published-core-fault',
                     'published-barrier-fault', 'before-ready', 'changed-arena', 'changed-backing',
                     'missing-parked-worker', 'stale-epoch'):
            h.restore(initial)
            count, claims, descriptors, head = 32, 0, 0, 0
            injection = None
            if kind == 'empty':
                h.cpu.mem_write(TAIL, struct.pack('<H', 1))
            elif kind == 'partial':
                h.cpu.mem_write(TAIL, struct.pack('<H', 18))
                claims = descriptors = head = 17
            elif kind == 'duplicate':
                h.cpu.mem_write(POOL + 2, struct.pack('<H', 0))
                claims = descriptors = head = 1
            elif kind == 'invalid-id':
                h.cpu.mem_write(POOL, struct.pack('<H', 8192))
            elif kind == 'bad-count':
                count = COUNTS[selector] + 1
            elif kind == 'changed-arena':
                h.put32(0x3e9030fc, h.get32(0x3e9030fc) + 32)
            elif kind == 'changed-backing':
                h.put32(0x3e902ce4, h.get32(0x3e902ce4) + 128)
            elif kind == 'missing-parked-worker':
                h.put32(STATE + 20 + 7 * 4, 0)
            elif kind == 'stale-epoch':
                h.put32(STATE, 2)
            else:
                injection = kind
                claims = 1
                head = 37 if kind == 'head-changed' else 0 if kind in ('tail-changed', 'id-changed') else 1
                if kind == 'before-ready':
                    claims = descriptors = head = count
            row = h.invoke(selector, count, inject=injection)
            check(row, 0, claims, descriptors, head, injected=bool(injection))
            controls.append(dict(name=kind, **row))
        print(json.dumps(dict(control_selector=selector, cases=16)), flush=True)
    core_text = (CORE / 'cold-page.c').read_text()
    binding_text = (TESTS / 'cold-page-native-emulation.c').read_text()
    assembly_text = (TESTS / 'cold-page-native-emulation.S').read_text()
    mutants = []
    cases = (
        ('omit-head-store', 'core', '*q->head = (uint16_t)result.page.next_head;',
         '(void)result.page.next_head;', None),
        ('omit-snapshot-recheck', 'core',
         'if (*q->head != head || *q->tail != tail || q->ids[head] != id)',
         'if (0)', 'head-changed'),
        ('omit-late-fault-check', 'core', 'if (faulted(s))\n        result.page.status',
         'if (0)\n        result.page.status', 'published-core-fault'),
        ('omit-getter-lifetime-recheck', 'binding', '|| !live())', ')', 'published-barrier-fault'),
        ('always-success-wrapper', 'binding', 'return result;', 'return 1;', 'partial'),
        ('omit-ready-fault-branch', 'assembly', 'beqz a0, .Lready_fail\\@',
         'nop', 'before-ready'),
    )
    for name, kind, old, new, injection in cases:
        directory = dest / name
        directory.mkdir()
        text = dict(core=core_text, binding=binding_text, assembly=assembly_text)[kind]
        assert old in text
        source = directory / ('mutant.S' if kind == 'assembly' else 'mutant.c')
        source.write_text(text.replace(old, new))
        alternative = build(directory, parts, **{kind: source})
        h.restore(initial)
        h.install(alternative)
        assert h.direct(h.binding.symbols['npu_emulation_page_init']) == 0
        if injection == 'partial':
            h.cpu.mem_write(TAIL, struct.pack('<H', 18))
        try:
            row = h.invoke(5, 32 if injection == 'partial' else 1,
                           inject=None if injection == 'partial' else injection)
            if injection is None:
                check(row, 1, 1, 1, 1)
            else:
                check(row, 0, 17 if injection == 'partial' else 1,
                      17 if injection == 'partial' else 1 if injection == 'before-ready' else 0,
                      37 if injection == 'head-changed' else 17 if injection == 'partial' else 1,
                      injected=injection != 'partial')
        except AssertionError as exc:
            assert exc.args and exc.args[0][0] in (
                'callback-result', 'retained-claims', 'publication', 'ready-gate', 'caller-lease'), exc
            mutants.append(dict(name=name, rejected_by=exc.args[0][0]))
        else:
            raise AssertionError(('surviving-native-binding-mutant', name))
    sources = [CORE / 'cold-page.c', CORE / 'cold-page.h', TESTS / 'cold-page-native-emulation.c',
               TESTS / 'cold-page-native-emulation.S', TESTS / 'cold-page-native-emulation.ld', Path(__file__)]
    result = dict(passed=True, hooks=54, nominal=valid, controls=controls, rejected_mutants=mutants, workers=workers,
                  strict_denial=denied, total_nominal_claims=total,
                  inputs={str(p.relative_to(ROOT)): composition.sha(p) for p in sources},
                  binaries={str(p.relative_to(ROOT)): composition.sha(p) for p in [*paths, *parts.values(), path]},
                  limits=['Original selected native initializer/dispatcher instructions plus checked C binding,not a modified vendor blob.',
                          'Explicit held direct callback lease and modeled all-hart parking;strict mailbox setup remains closed.',
                          'Emulator pool/backing/storage/exclusion contracts are not physical containment,coherency,drain or client acceptance.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, hooks=54, claims=total, controls=len(controls), receipt=str(dest / 'result.json'))))


if __name__ == '__main__':
    main()
