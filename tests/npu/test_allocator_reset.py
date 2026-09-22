#!/usr/bin/env python3
"""Native reset-order correction, control-word isolation and cold boot replay."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE
from unicorn import riscv_const as r

import test_allocator_protocol as protocol
from test_allocator_native import CheckedBridge, Original, build_bridge, NATIVE_STATE
from test_barrier_core5 import jump
from test_barrier_protocol import Rv32
from test_boot_irq_installation import GHIDRA
from test_bridge_startup import input_bindings
from test_firmware_memory_layout import NativeMemory, CODE_SHA, DATA_SHA
from test_multihart_cold_boot import ELF, ELF_SHA
from emulation_layout import CODE, SRAM, SRAM_BYTES, HEAP, HEAP_BYTES, STATE

ROOT = protocol.ROOT
OUT = ROOT / 'research/checkpoints/2026-09-09-npu-allocator-reset'
BUILD = ROOT / '.local/npu-allocator-reset'
ASM = ROOT / 'tests/npu/allocator-reset-emulation.S'
LINKER = ASM.with_suffix('.ld')
FLAG_POINTER, POOL_POINTER = SRAM+0x1f10, SRAM+0x1b88
CALL, SKIP = 0x840052ca, 0x840052d4
PREIMAGES = {CALL: 'efa09004', SKIP: '97d78fba'}
COLD_TYPES = [0x89, 0x8a, 0x12, 0x1d, 1, 0x0b, 0x19]
POOL_BYTES = 0x8000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(defines=()):
    BUILD.mkdir(parents=True, exist_ok=True)
    name = '-'.join(defines) or 'retained-control'
    path = BUILD / (name+'.elf')
    lld = shutil.which('ld.lld') or str(ROOT/'.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld')
    command = [shutil.which('clang'), '--target=riscv32', '-march=rv32imac_zicsr',
               '-mabi=ilp32', '-nostdlib', f'--ld-path={lld}', '-Wl,--no-relax',
               '-Wl,-T,'+str(LINKER), *['-D'+item for item in defines], str(ASM), '-o', str(path)]
    done = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stdout+done.stderr
    return path, command


def install(h, path, omit=None):
    rv = Rv32(path, h.cpu)
    targets = {CALL: rv.symbols['npu_emulation_allocator_reset_prepare'], SKIP: 0x840052e4}
    patches = []
    for site, target in targets.items():
        before = bytes(h.cpu.mem_read(site, 4)).hex()
        assert before == PREIMAGES[site] == h.code[site-CODE:site-CODE+4].hex()
        if site == omit:
            continue
        word = int.from_bytes(jump(site, target), 'little') | (0x80 if site == CALL else 0)
        replacement = struct.pack('<I', word)
        h.cpu.mem_write(site, replacement)
        patches.append(dict(site=hex(site), before=before, after=replacement.hex(), target=hex(target)))
    h.cpu.ctl_remove_cache(0x84005296, 0x840052e8)
    h.cpu.ctl_remove_cache(0x8404c000, 0x8404d000)
    return rv, patches


def state(h):
    return bytes(h.cpu.mem_read(NATIVE_STATE, protocol.STATE_BYTES))


def expected_reset(seed):
    initial = bytearray(seed)
    struct.pack_into('<III', initial, 0, 18, 0, 0)
    struct.pack_into('<I', initial, 20, 0)
    initial[24:] = bytes(800)
    status, expected, _ = protocol.oracle(protocol.Case('control-word', protocol.definitions(),
                                                       0x89, 0, bytes(initial)))
    assert status == (protocol.OK, HEAP)
    return expected


def primitive(path=None, seed_kind='cold', omit=None, check=True):
    h = NativeMemory()
    patches = install(h, path, omit)[1] if path else []
    seed = bytearray(protocol.empty())
    if seed_kind == 'stale':
        seed[:] = protocol.state_for(protocol.definitions(), COLD_TYPES)
        struct.pack_into('<I', seed, 16, 99)
    elif seed_kind == 'corrupt':
        struct.pack_into('<I', seed, 8, 100)
        struct.pack_into('<I', seed, 20, HEAP_BYTES)
    elif seed_kind == 'counter-wrap':
        struct.pack_into('<I', seed, 16, 0xffffffff)
    else:
        assert seed_kind == 'cold'
    h.cpu.mem_write(NATIVE_STATE, bytes(seed))
    h.cpu.mem_write(HEAP, b'\xa5'*HEAP_BYTES)
    events = []
    def trace(cpu, pc, size, data):
        if pc in (0x8400fb12, 0x84005a28, 0x84005200, 0x840052d2, 0x840052e4):
            events.append(dict(pc=hex(pc), count=h.get32(SRAM+0x1bd4),
                               used=h.get32(SRAM+0x1be0), flag=hex(h.get32(FLAG_POINTER))))
    h.cpu.hook_add(UC_HOOK_CODE, trace)
    h.call(0x84005296)
    after_reset = state(h)
    expected = expected_reset(bytes(seed))
    if not path:
        assert seed_kind == 'cold'
        expected = bytearray(expected)
        struct.pack_into('<I', expected, 8, 0)
        struct.pack_into('<I', expected, 20, 0)
        expected = bytes(expected)
    if check:
        assert after_reset == expected, 'reset-metadata'
        assert h.get32(FLAG_POINTER) == HEAP, 'control-pointer'
        assert bytes(h.cpu.mem_read(HEAP, HEAP_BYTES)) == bytes(HEAP_BYTES), 'reset-heap'
    if not check:
        return dict(actual=sha(after_reset), expected=sha(expected), events=events,
                    count=h.get32(SRAM+0x1bd4), used=h.get32(SRAM+0x1be0),
                    flag=hex(h.get32(FLAG_POINTER)))
    if path:
        assert [(row['count'], row['used']) for row in events[:3]] == [(0, 0)]*3
        assert [(row['count'], row['used']) for row in events[3:]] == [(1, 4)]*2
    flag = h.get32(FLAG_POINTER)
    # Execute the original ID initializer through its complete first pool loop.
    h.cpu.emu_start(0x84004e76, 0x84004ede, count=300000, timeout=3000000)
    assert h.cpu.reg_read(r.UC_RISCV_REG_PC) == 0x84004ede
    pool = h.get32(POOL_POINTER)
    oracle_result, metadata, _ = protocol.oracle(protocol.Case('pool', protocol.definitions(), 0x8a, 0, after_reset))
    assert oracle_result == (protocol.OK, pool) and state(h) == metadata
    assert pool == HEAP+(32 if path else 0)
    pool_image = struct.pack('<16384H', *range(16384))
    assert bytes(h.cpu.mem_read(pool, POOL_BYTES)) == pool_image
    expected_heap = bytearray(HEAP_BYTES)
    expected_heap[pool-HEAP:pool-HEAP+POOL_BYTES] = pool_image
    assert bytes(h.cpu.mem_read(HEAP, HEAP_BYTES)) == bytes(expected_heap)
    before_heap = bytes(expected_heap)
    before_sram = bytes(h.cpu.mem_read(SRAM, SRAM_BYTES))
    flag_before = h.get32(flag)
    h.call(0x84005a42)
    assert h.call(0x84005a52) == flag
    struct.pack_into('<I', expected_heap, flag-HEAP, 1)
    after_heap = bytes(h.cpu.mem_read(HEAP, HEAP_BYTES))
    assert after_heap == bytes(expected_heap)
    assert bytes(h.cpu.mem_read(SRAM, SRAM_BYTES)) == before_sram
    pool_after = bytes(h.cpu.mem_read(pool, POOL_BYTES))
    assert (pool_after == pool_image) == bool(path)
    assert flag_before == (0 if path else 0x10000)
    return dict(corrected=bool(path), seed=seed_kind, patches=patches, native_reset_events=events,
                state_after_reset_sha256=sha(after_reset), state_after_pool_sha256=sha(state(h)),
                flag=hex(flag), pool=hex(pool), flag_before=flag_before, flag_after=h.get32(flag),
                pool_first8_before=pool_image[:8].hex(), pool_first8_after=pool_after[:8].hex(),
                pool_preserved=pool_after == pool_image, whole_pool_compared=POOL_BYTES,
                whole_heap_compared=HEAP_BYTES, setter_whole_sram_unchanged=SRAM_BYTES,
                heap_before_sha256=sha(before_heap), heap_after_sha256=sha(after_heap))


class ResetBridge(CheckedBridge):
    def __init__(self, reset_path, allocator_path, omit_start=True):
        self.reset_path = reset_path
        self.reset_patches = []
        super().__init__(allocator_path, omit_start)

    def coordinator(self):
        self.reset_rv, self.reset_patches = install(self, self.reset_path)
        return super().coordinator()


def native_writer(h):
    context, hart, active = h.cpu.context_save(), h.hart, h.bridge_active
    h.hart, h.bridge_active = 0, False
    h.call(0x84005a42)
    assert h.call(0x84005a52) == HEAP
    h.cpu.context_restore(context)
    h.hart, h.bridge_active = hart, active


def remaining_budget(metadata):
    case = protocol.Case('retained-control-postbridge-type2', protocol.definitions(), 2, 1, metadata)
    paths = protocol.build()
    checked = protocol.Pair(paths).case(case)
    assert checked['result'] == (protocol.CAPACITY, 0) and checked['metadata_unchanged']
    # Invoke only the typed allocator on a boot-derived state snapshot. This
    # does not admit an RX callback or resume a parked worker to consume it.
    original = Original()
    original.fresh(metadata)
    heap = bytes(original.cpu.mem_read(HEAP, HEAP_BYTES))
    address = original.call(0x84005200, 2)
    bytes_ = next(row[3] for row in case.defs[1] if row[0] == 2)
    end = address+bytes_
    assert address == 0x3e877700 and end == 0x3e878f18
    expected = bytearray(metadata)
    count = struct.unpack_from('<I', metadata, 8)[0]
    attempts = struct.unpack_from('<I', metadata, 16)[0]
    struct.pack_into('<I', expected, 8, count+1)
    struct.pack_into('<II', expected, 16, attempts+1, end-HEAP)
    struct.pack_into('<HHI', expected, 24+8*count, 2, 0, address)
    assert original.state() == bytes(expected)
    assert bytes(original.cpu.mem_read(HEAP, HEAP_BYTES)) == heap
    return dict(remaining_bytes=HEAP_BYTES-struct.unpack_from('<I', metadata, 20)[0],
                original_address=hex(address), original_end=hex(end), requested_bytes=bytes_,
                heap_end=hex(HEAP+HEAP_BYTES), excess_bytes=end-HEAP-HEAP_BYTES,
                checked=checked, native_test_sha256=sha(paths[0].read_bytes()),
                rv32_test_sha256=sha(paths[1].read_bytes()), commands=paths[2],
                original_state_after_sha256=sha(original.state()),
                scope='Typed allocation only on boot-derived metadata; no native RX callback or packet/DMA write.')


def boot(reset_path, allocator_path):
    h = ResetBridge(reset_path, allocator_path)
    metadata = state(h)
    assert h.base_count == 7 and h.base_used == 430320
    assert h.get32(FLAG_POINTER) == HEAP and h.get32(POOL_POINTER) == HEAP+32
    # Whole metadata follows the actual core0 allocation sequence, with its
    # diagnostic counter retaining the native reset-time allocation attempt.
    expected = bytearray(protocol.state_for(protocol.definitions(), COLD_TYPES))
    expected[4:8] = expected[12:16] = bytes(4)
    assert metadata == bytes(expected)
    cases = [h.run_checked('reset-retained-native-cold-state'),
             h.run_checked('reset-retained-denied-owner', deny=True),
             h.run_checked('reset-retained-corrupt-cursor', corrupt=True),
             h.run_checked('reset-retained-external-fault', fault_on_unlock=True)]
    # Reconstruct a successful bridge state before checking the later writer.
    h.run_checked('reset-retained-control-word-isolation')
    flag, pool = h.get32(FLAG_POINTER), h.get32(POOL_POINTER)
    before = bytes(h.cpu.mem_read(HEAP, HEAP_BYTES))
    before_sram = bytes(h.cpu.mem_read(SRAM, SRAM_BYTES))
    native_writer(h)
    expected_heap = bytearray(before)
    struct.pack_into('<I', expected_heap, flag-HEAP, 1)
    assert bytes(h.cpu.mem_read(HEAP, HEAP_BYTES)) == bytes(expected_heap)
    assert bytes(h.cpu.mem_read(SRAM, SRAM_BYTES)) == before_sram
    assert bytes(h.cpu.mem_read(pool, POOL_BYTES)) == before[pool-HEAP:pool-HEAP+POOL_BYTES]
    assert state(h)[8:12] == struct.pack('<I', 8) and h.get32(SRAM+0x1be0) == 489215
    return dict(core0_footprint=h.coordinator_footprint, core0_metadata_sha256=sha(metadata),
                core0_count=7, core0_used=430320, bridge_count=8, bridge_used=489215,
                bridge_base=hex(h.get32(SRAM+0x184c)), control_word=hex(flag), pool=hex(pool),
                checked_bridge_cases=cases, reset_patches=h.reset_patches,
                whole_heap_setter_compared=HEAP_BYTES, setter_pool_preserved=POOL_BYTES,
                setter_sram_unchanged=SRAM_BYTES, remaining_budget=remaining_budget(state(h)))


def retained_gate(reset_path, allocator_path):
    h = ResetBridge(reset_path, allocator_path, omit_start=False)
    h.prepare()
    poll = h.rv.symbols['npu_barrier_poll']
    assert h.run(0x84000b24, [poll]) == poll
    assert h.run(poll, [poll]) == poll
    h.contexts[7] = h.cpu.context_save()
    for hart in range(1, 7):
        h.worker(hart)
    for hart in range(8):
        h.repoll(hart)
    status = h.control(3)
    assert status[9:] == [0, 7, 255, 0, 0, 0, 0]
    assert not h.checked_results and not h.guard_entries
    assert not any(0x1ec12000 <= int(row['address'], 16) < 0x1ec13000 for row in h.mmio)
    return dict(installed_detours=len(h.patches)+len(h.installed_guards)+1+len(h.reset_patches),
                initial_gate_retained=True, all_parked=[1]*8, status=status,
                no_bridge_or_checked_allocator_execution=True, plic='banked storage hypothesis')


def mutations(path):
    rows = []
    for name, defines, omit, seed, count, used, flag in (
        ('omit-early-count-clear', ('OMIT_RESET_COUNT',), None, 'stale', 8, 4, HEAP),
        ('omit-early-cursor-clear', ('OMIT_RESET_CURSOR',), None, 'stale', 1, 430340, HEAP+430336),
        ('omit-reset-entry-hook', (), CALL, 'stale', 8, 430340, HEAP+430336),
        ('retain-late-counter-clears', (), SKIP, 'cold', 0, 0, HEAP),
    ):
        candidate = build(defines)[0] if defines else path
        result = primitive(candidate, seed, omit, check=False)
        assert result['actual'] != result['expected'], 'surviving reset-order mutant: '+name
        assert (result['count'], result['used'], result['flag']) == (count, used, hex(flag))
        rows.append(dict(name=name, detected=True, result=result, elf_sha256=sha(candidate.read_bytes())))
    return rows


def source_spans():
    source = GHIDRA.read_text()
    rows = []
    for address, execution in ((0x84005296, 'native'), (0x84005a28, 'native'),
                               (0x84005a42, 'native'), (0x84005a52, 'native'),
                               (0x84004e76, 'native'), (0x8400580e, 'static-only'),
                               (0x8400fd2e, 'static-only')):
        match = re.search(r'^FUNCTION [^\n]* @ ram:'+f'{address:08x}'+r'\n.*?(?=^FUNCTION |\Z)',
                          source, re.M | re.S)
        assert match and 'decompiled=true' in match[0]
        rows.append(dict(address=hex(address), first_line=source[:match.start()].count('\n')+1,
                         sha256=sha(match[0].encode()), execution=execution))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    inputs = input_bindings()
    inputs.update({str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in
                   (ASM, LINKER, Path(__file__), protocol.BINDING, protocol.LINKER)})
    assert sha(ELF.read_bytes()) == ELF_SHA
    reset_path, command = build()
    with reset_path.open('rb') as stream:
        elf = ELFFile(stream)
        sections = [(s.name, s['sh_addr'], s['sh_size']) for s in elf.iter_sections()
                    if s['sh_flags'] & 2 and s['sh_size']]
    assert sections == [('.text', 0x8404c000, 20)]
    allocator_path, _ = build_bridge()
    rows = [primitive(), *[primitive(reset_path, kind) for kind in ('cold', 'stale', 'corrupt', 'counter-wrap')]]
    mutant_rows = mutations(reset_path)
    integration = boot(reset_path, allocator_path)
    gate = retained_gate(reset_path, allocator_path)
    assert all(sha((ROOT/name).read_bytes()) == digest for name, digest in inputs.items())
    result = dict(schema=1, code_sha256=CODE_SHA, data_sha256=DATA_SHA, baseline_elf_sha256=ELF_SHA,
                  assembly_sha256=sha(ASM.read_bytes()), linker_sha256=sha(LINKER.read_bytes()),
                  elf_sha256=sha(reset_path.read_bytes()), command=command, sections=sections,
                  disassembly=subprocess.check_output(['riscv64-linux-gnu-objdump', '-d', str(reset_path)],
                                                      text=True, timeout=30),
                  source_spans=source_spans(),
                  primitives=rows, mutants=mutant_rows, integration=integration, retained_gate=gate,
                  inputs_before_after=inputs,
                  limits=['Cold isolated model only; repeated calls do not prove safe active reset or containment.',
                          'Native control writer and buffer-ID pool execute, not an actual device traffic failure.',
                          'Allocator ownership, other dynamic callers, full memory budget and hardware/cache contracts remain open.',
                          'No router contact, image, Wi-Fi change, INODE-provider or native DESC5/6/7/8 callback.'])
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT/'allocator-reset.json'
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    if args.check:
        assert output.read_bytes() == encoded, 'reset-order replay differs'
    else:
        output.write_bytes(encoded)
    print(json.dumps(dict(primitives=len(rows), mutants=len(mutant_rows),
                          bridge_cases=len(integration['checked_bridge_cases']),
                          installed_detours=gate['installed_detours'], evidence_sha256=sha(encoded))))


if __name__ == '__main__':
    main()
