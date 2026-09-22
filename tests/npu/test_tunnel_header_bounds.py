#!/usr/bin/env python3
"""Tunnel header slot bounds and native callback/egress instruction checks."""
import argparse
from collections import Counter
import ctypes as ct
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UcError
from unicorn import riscv_const as r

import test_allocator_protocol as allocator
import test_command_ring_layout as layout
import test_command_ring_order as order
import test_txdone_init as txdone
from test_barrier_protocol import Rv32
from test_barrier_core5 import jump
from test_bridge_startup import BRIDGE, input_bindings
from test_boot_irq_installation import UnmodeledAccess
from test_firmware_mailbox_dispatch import PAYLOAD, MBOX
from test_firmware_memory_layout import STACK_TOPS
from emulation_layout import CODE, HEAP, HEAP_BYTES, SRAM, SRAM_BYTES

ROOT = allocator.ROOT
OUT = ROOT/'research/checkpoints/2026-09-10-npu-tunnel-headers'
BUILD = ROOT/'.local/npu-tunnel-headers'
SOURCE = ROOT/'firmware/npu/tunnel-header.c'
HEADER = SOURCE.with_suffix('.h')
ASM = ROOT/'tests/npu/tunnel-header-emulation.S'
LINKER = ASM.with_suffix('.ld')
BAD = 0xffffffff
DESC, DESC_BYTES = 0x58000000, 4096
LENGTHS = SRAM+0x4650
SITES = {0x84005c30: 'vxlan_header', 0x84005c82: 'srv6_header',
         0x84001e78: 'srv6_consumer', 0x84001eea: 'srv6_size_a5', 0x84001f00: 'srv6_size_a2'}


def sha(data):
    return allocator.sha(data)


def build(source=SOURCE, assembly=ASM, tag='header'):
    BUILD.mkdir(parents=True, exist_ok=True)
    native, rv = BUILD/(tag+'.so'), BUILD/(tag+'.elf')
    common = ['-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
              '-I', str(SOURCE.parent), str(source)]
    lld = shutil.which('ld.lld') or str(ROOT/'.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld')
    commands = [[shutil.which('gcc'), *common, '-shared', '-fPIC', '-fsanitize=undefined',
                 '-fno-sanitize-recover=all', '-o', str(native)],
                [shutil.which('clang'), *common, '--target=riscv32', '-march=rv32imac_zicsr',
                 '-mabi=ilp32', '-nostdlib', '-fno-stack-protector', f'--ld-path={lld}', str(assembly),
                 '-Wl,-T,'+str(LINKER)+',--no-relax', '-o', str(rv)]]
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout+result.stderr
    return native, rv, commands


def install(h, path, omit=None):
    rv = Rv32(path, h.cpu)
    patches = []
    for site, name in SITES.items():
        before = bytes(h.cpu.mem_read(site, 4))
        assert before == h.code[site-CODE:site-CODE+4]
        if site == omit:
            continue
        target = rv.symbols['npu_emulation_'+name]
        after = jump(site, target)
        h.cpu.mem_write(site, after)
        patches.append(dict(site=hex(site), name=name, before=before.hex(), after=after.hex(), target=hex(target)))
    h.cpu.ctl_remove_cache(CODE, CODE+0x201000)
    return rv, patches


class Result(ct.Structure):
    _fields_ = [('index', ct.c_uint32), ('bytes', ct.c_uint32)]


def helper_cases(paths):
    lib = ct.CDLL(str(paths[0]))
    lib.npu_tunnel_header_decode.argtypes = [ct.c_void_p, ct.c_uint32, ct.c_uint32]
    lib.npu_tunnel_header_decode.restype = Result
    lib.npu_tunnel_srv6_read_length.argtypes = [ct.c_uint32, ct.c_void_p]
    lib.npu_tunnel_srv6_read_length.restype = ct.c_uint32
    rv = Rv32(paths[1])
    pointer, lengths = SRAM+0x7000, SRAM+0x7800
    def call(name, *args):
        for register, value in zip(allocator.REGS, args):
            rv.cpu.reg_write(register, value)
        rv.cpu.reg_write(r.UC_RISCV_REG_RA, allocator.END)
        rv.cpu.reg_write(r.UC_RISCV_REG_SP, allocator.STACK)
        rv.cpu.emu_start(rv.symbols[name], allocator.END, count=10000, timeout=1000000)
        assert rv.cpu.reg_read(r.UC_RISCV_REG_PC) == allocator.END
        return tuple(rv.cpu.reg_read(reg) for reg in allocator.REGS[:2])
    cases = set()
    for index in range(256):
        for available in (58, 59, 60):
            cases.add((0, index, 0, available))
        for size in (0, 128, 129):
            for available in (9+size, 10+size):
                cases.add((1, index, size, available))
    for index in (0, 7):
        for size in range(256):
            for available in (9+size, 10+size):
                cases.add((1, index, size, available))
    for kind in (0, 1, 2, BAD):
        for available in (0, 1, 8, 9, 10):
            cases.add((kind, 0, 0, available))
    results = []
    for kind, index, size, available in sorted(cases):
        data = bytearray(512)
        data[8:10] = bytes((index, size))
        host = ct.create_string_buffer(bytes(data))
        rv.cpu.mem_write(pointer, bytes(data))
        expected = (BAD, 0)
        if kind == 0 and available >= 59 and index < 20:
            expected = (index, 50)
        if kind == 1 and available >= 10+size and index < 8 and size <= 128:
            expected = (index, size)
        actual = lib.npu_tunnel_header_decode(host, available, kind)
        assert (actual.index, actual.bytes) == call('npu_tunnel_header_decode', pointer, available, kind) == expected
        assert bytes(host.raw[:512]) == bytes(data) == bytes(rv.cpu.mem_read(pointer, 512))
        results.append((kind, index, size, available, *expected))
    reader_cases = {(udf, size) for udf in range(256) for size in (0, 11, 12, 128, 129, 255)}
    reader_cases.update((udf, size) for udf in (41, 48) for size in range(256))
    readers = []
    for udf, size in sorted(reader_cases):
        data = bytes([size])*8
        host = ct.create_string_buffer(data)
        rv.cpu.mem_write(lengths, data)
        expected = size if 41 <= udf < 49 and 13 <= size <= 128 else BAD
        assert lib.npu_tunnel_srv6_read_length(udf, host) == expected
        assert call('npu_tunnel_srv6_read_length', udf, lengths)[0] == expected
        readers.append((udf, size, expected))
    pointer_cases = []
    for address, available, kind in ((0, 59, 0), (0xfffffff0, 59, 0),
                                      (0xfffffff8, 10, 1), (pointer, BAD, 1)):
        assert call('npu_tunnel_header_decode', address, available, kind) == (BAD, 0)
        pointer_cases.append((address, available, kind))
    assert lib.npu_tunnel_header_decode(None, 59, 0).index == BAD
    assert lib.npu_tunnel_srv6_read_length(41, None) == BAD
    assert call('npu_tunnel_srv6_read_length', 41, 0)[0] == BAD
    return dict(decode_pairs=results, reader_pairs=readers, rv32_pointer_controls=pointer_cases)


class Headers(layout.Profile):
    def __init__(self, profile, reset):
        self.header_tracking = False
        self.header_reads, self.header_writes, self.commands = [], [], []
        self.length_reads = []
        self.header_entries = Counter()
        self.source_limit = 4096
        self.header_mutation = None
        super().__init__(profile, reset)
        self.probe()
        self.cpu.mem_map(DESC, DESC_BYTES)
        self.header_base = self.get32(SRAM+0x184c)+0x10000
        self.hart = 0
        self.bridge_active = False
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        self.spaces = ((HEAP, HEAP_BYTES), (SRAM, SRAM_BYTES), (layout.RING, layout.RING_BYTES),
                       (layout.L2, layout.L2_BYTES), (DESC, DESC_BYTES), (BRIDGE, 4096), (PAYLOAD, 4096))
        self.snapshot = [(base, bytes(self.cpu.mem_read(base, size))) for base, size in self.spaces]

    def is_memory(self, address, size):
        return DESC <= address and address+size <= DESC+DESC_BYTES or super().is_memory(address, size)

    def register_model(self, address, write):
        if address in range(BRIDGE+0x50, BRIDGE+0x70, 4) and not write:
            return 'explicit egress command-slot availability; no DMA completion model'
        if BRIDGE+0x100 <= address < BRIDGE+0x200 and (address-BRIDGE) % 32 in range(0, 28, 4) and write:
            return 'native egress command-register writes; no DMA execution model'
        return super().register_model(address, write)

    def read_hook(self, cpu, access, address, size, value, data):
        if self.header_tracking and LENGTHS <= address < LENGTHS+8:
            self.length_reads.append((address, size, cpu.reg_read(r.UC_RISCV_REG_PC)))
        if self.header_tracking and PAYLOAD <= address < PAYLOAD+4096:
            self.header_reads.append((address, size, cpu.reg_read(r.UC_RISCV_REG_PC)))
            if address+size > PAYLOAD+self.source_limit:
                raise UnmodeledAccess('header source exceeds fixture backing')
        super().read_hook(cpu, access, address, size, value, data)

    def write_hook(self, cpu, access, address, size, value, data):
        if self.header_tracking:
            self.header_writes.append((address, size, value, cpu.reg_read(r.UC_RISCV_REG_PC)))
        super().write_hook(cpu, access, address, size, value, data)

    def code_hook(self, cpu, pc, size, data):
        if self.header_tracking:
            self.header_entries[pc] += 1
            if pc == 0x84001582:
                self.commands.append(tuple(cpu.reg_read(reg) for reg in allocator.REGS))
            if self.header_mutation and pc == self.header_mutation[0]:
                for address, value in self.header_mutation[1]:
                    cpu.mem_write(address, bytes([value]))
                self.header_mutation = None
        super().code_hook(cpu, pc, size, data)

    def prepare(self, *args, **kwargs):
        if not hasattr(self, 'snapshot'):
            return super().prepare(*args, **kwargs)
        self.header_tracking = False
        for base, data in self.snapshot:
            self.cpu.mem_write(base, data)
        self.cpu.mem_write(self.header_base, b'\xa5'*4096)
        self.cpu.mem_write(LENGTHS, b'\x5a'*8)
        self.cpu.mem_write(DESC, b'\xa5'*DESC_BYTES)
        self.source_limit = 4096
        self.header_mutation = None
        self.header_reads, self.header_writes, self.commands = [], [], []
        self.length_reads = []
        self.header_entries.clear()
        self.mmio.clear()
        self.logs.clear()
        self.unmodeled = None
        self.hart = 0
        self.bridge_active = False
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        for channel in range(8):
            self.put32(BRIDGE+0x50+channel*4, 0x100)

    def callback(self, kind, index, size, available=None):
        prefix, opcode = (9, 0) if kind == 0 else (10, 3)
        length = 50 if kind == 0 else size
        message = bytearray(prefix+length)
        struct.pack_into('<I', message, 0, opcode)
        message[8] = index
        if kind:
            message[9] = size
        message[prefix:] = bytes((i*17+7) % 256 for i in range(length))
        self.cpu.mem_write(PAYLOAD, bytes(message))
        self.header_tracking = True
        value = self.call(0x84005c30 if kind == 0 else 0x84005c82,
                          PAYLOAD, len(message) if available is None else available)
        self.header_tracking = False
        return value, bytes(message), prefix


def memory(h):
    return {base: bytes(h.cpu.mem_read(base, size)) for base, size in h.spaces if base != PAYLOAD}


def store_case(h, kind, index, length, available=None, enabled=False, mutate=False, backing=None,
               mutation_index=255):
    h.prepare()
    before = memory(h)
    message_bytes = (59 if kind == 0 else 10+length) if available is None else available
    accepted = index < (20 if kind == 0 else 8) and message_bytes >= (59 if kind == 0 else 10+length)
    accepted &= kind == 0 or length <= 128
    native_accepted = kind == 0 or index < 8
    if mutate:
        assert accepted and enabled
        name = 'npu_emulation_vxlan_decoded' if kind == 0 else 'npu_emulation_srv6_decoded'
        h.header_mutation = (h.header_rv.symbols[name],
                             [(PAYLOAD+8, mutation_index), *([(PAYLOAD+9, 255)] if kind else [])])
    if backing is not None:
        h.source_limit = backing
    try:
        result, message, prefix = h.callback(kind, index, length, available)
    except UnmodeledAccess as error:
        assert backing is not None and str(error) == 'header source exceeds fixture backing'
        return dict(kind=kind, index=index, length=length, enabled=enabled,
                    backing=backing, caught_only_by_fixture=str(error), actual_backing_guard=False)
    did_copy = accepted if enabled else native_accepted
    assert result == (int(accepted) if enabled else 1), 'callback-result'
    wanted = {base: bytearray(data) for base, data in before.items()}
    count = 50 if kind == 0 else length
    destination = h.header_base+(index+(20 if kind else 0))*128
    if did_copy:
        wanted[HEAP][destination-HEAP:destination-HEAP+count] = message[prefix:]
        if kind:
            wanted[SRAM][LENGTHS-SRAM+index] = length
    assert memory(h) == {base: bytes(data) for base, data in wanted.items()}, 'store-memory-footprint'
    actual_writes = {byte for address, size, _, _ in h.header_writes
                     if any(base <= address < base+len(data) for base, data in before.items())
                     for byte in range(address, address+size)}
    expected_writes = set(range(destination, destination+count)) if did_copy else set()
    if did_copy and kind:
        expected_writes.add(LENGTHS+index)
    assert actual_writes == expected_writes
    if enabled:
        assert all(a+s <= PAYLOAD+message_bytes for a, s, _ in h.header_reads)
        if did_copy:
            assert {byte-PAYLOAD for a, size, _ in h.header_reads for byte in range(a, a+size)} == set(range(8, prefix+count))
            assert sum(a <= PAYLOAD+8 < a+s for a, s, _ in h.header_reads) == 1
            if kind:
                assert sum(a <= PAYLOAD+9 < a+s for a, s, _ in h.header_reads) == 1
        assert h.header_entries[0x84001466] == int(did_copy)
    assert not h.commands
    return dict(kind=kind, index=index, length=length, available=message_bytes,
                enabled=enabled, result=result, accepted=accepted, original_wrote=native_accepted,
                mutation_after_capture=mutate, destination=hex(destination),
                bytes_written=len(actual_writes), payload_read_bytes=sum(s for _, s, _ in h.header_reads),
                whole_memory_compared=sum(len(data) for data in before.values()),
                heap_sha256=sha(bytes(h.cpu.mem_read(HEAP, HEAP_BYTES))))


def consumer_case(h, udf, length, enabled=False, mutate=False):
    h.prepare()
    if 41 <= udf < 49:
        h.cpu.mem_write(LENGTHS+udf-41, bytes([length]))
    if mutate:
        assert enabled and 41 <= udf < 49 and 13 <= length <= 128
        h.header_mutation = (0x84001edc, [(LENGTHS+udf-41, 255)])
    before = memory(h)
    h.header_tracking = True
    result = h.call(0x84001e78, 0, 256, DESC, udf, 14)
    h.header_tracking = False
    allowed = 41 <= udf < 49 and 13 <= length <= 128
    if enabled and not allowed:
        assert result == BAD and not h.commands, 'consumer-result'
        assert memory(h) == before
        assert h.header_entries[0x84001466] == h.header_entries[0x8400178e] == 0
    else:
        assert 41 <= udf < 49
        assert result == 0 and len(h.commands) == 3
        encoded_length = (length-12) & 0xffff
        source = h.header_base+(udf-21)*128
        assert [row[1:4] for row in h.commands] == [
            (DESC & 0x1fffffff, 44 << 16, 0x81000000),
            (source & 0x1fffffff, encoded_length << 16 | 12, 0x05000000),
            (DESC & 0x1fffffff, 210 << 16 | 46, 0x40000000)], 'consumer-command-spans'
        patch_length = (256-14-86+length) & 0xffff
        swapped = (patch_length >> 8) | ((patch_length & 255) << 8)
        assert h.commands[1][4] == 0xc0120000 | swapped, 'consumer-patch-length'
        expected_io = [(BRIDGE+offset, 4, value) for row in h.commands for offset, value in
                       zip((0x104, 0x108, 0x10c, 0x110, 0x114, 0x118, 0x100), (*row[2:], row[1]))]
        actual_io = [(a, size, value) for a, size, value, _ in h.header_writes if BRIDGE <= a < BRIDGE+4096]
        assert actual_io == expected_io
        wanted = {base: bytearray(data) for base, data in before.items()}
        struct.pack_into('<I', wanted[DESC], 0, 0)
        struct.pack_into('<III', wanted[DESC], 16, udf << 14 | 0x3800, 0x7f4007ff, 0xffff)
        for row in h.commands:
            for offset, value in zip((0x100, 0x104, 0x108, 0x10c, 0x110, 0x114, 0x118), row[1:]):
                struct.pack_into('<I', wanted[BRIDGE], offset, value)
        if mutate:
            wanted[SRAM][LENGTHS-SRAM+udf-41] = 255
        assert memory(h) == {base: bytes(data) for base, data in wanted.items()}
    if enabled:
        assert len(h.length_reads) == int(41 <= udf < 49)
    return dict(udf=udf, stored_length=length, enabled=enabled, result=result,
                mutation_after_capture=mutate, length_reads=h.length_reads,
                encoded_commands=h.commands, encoded_header_bytes=(h.commands[1][2] >> 16) if h.commands else None,
                empty_header_command=bool(h.commands and not (h.commands[1][2] >> 16)),
                physical_dma_executed=False,
                whole_memory_compared=sum(len(data) for data in before.values()))


def mailbox_case(h, kind, index, length, available):
    h.prepare()
    message = bytearray(59 if kind == 0 else 10+length)
    struct.pack_into('<I', message, 0, 0 if kind == 0 else 3)
    message[8] = index
    if kind:
        message[9] = length
    h.cpu.mem_write(PAYLOAD, bytes(message))
    assert h.get32(SRAM+0xd30) == 0x84003a86
    h.put32(MBOX+0x30, PAYLOAD)
    h.put32(MBOX+0x34, available)
    h.put32(MBOX+0x3c, 0x801)
    before = bytes(h.cpu.mem_read(HEAP, HEAP_BYTES))
    h.header_tracking = True
    h.call(0x84003cd6, 8)
    h.header_tracking = False
    bytes_seen = available & 0xffff
    accepted = index < (20 if kind == 0 else 8) and bytes_seen >= len(message) and (kind == 0 or length <= 128)
    assert h.get32(MBOX+0x3c) == (0x807 if accepted else 0x803)
    assert h.header_entries[0x84003a86] == 1
    assert h.header_entries[0x84005c30 if kind == 0 else 0x84005c82] == 1
    if not accepted:
        assert bytes(h.cpu.mem_read(HEAP, HEAP_BYTES)) == before
    return dict(kind=kind, index=index, length=length, advertised_length=available,
                callback_length=bytes_seen, flags=hex(h.get32(MBOX+0x3c)), accepted=accepted,
                route='original ISR and tunnel dispatcher called directly; strict candidate admission is unchanged',
                payload_address='explicit already-addressable alias, not host DMA mapping proof')


def reset_code(h):
    for site in SITES:
        h.cpu.mem_write(site, h.code[site-CODE:site-CODE+4])
    h.cpu.ctl_remove_cache(CODE, CODE+0x201000)


def mutations(h, paths):
    text, assembly = SOURCE.read_text(), ASM.read_text()
    variants = [
        ('allow-vxlan-overlap', text, 'if (index >= slots)', 'if (index >= slots && 0)',
         lambda: store_case(h, 0, 20, 50, enabled=True), 'callback-result', False),
        ('allow-srv6-overlap', text, 'bytes > NPU_TUNNEL_HEADER_BYTES || bytes > available - 10',
         'bytes > available - 10', lambda: store_case(h, 1, 0, 129, enabled=True), 'callback-result', False),
        ('short-vxlan-message', text, 'available < 59', 'available < 9',
         lambda: store_case(h, 0, 0, 50, available=58, enabled=True), 'callback-result', False),
        ('short-srv6-message', text, ' || bytes > available - 10', '',
         lambda: store_case(h, 1, 0, 128, available=10, enabled=True), 'callback-result', False),
        ('empty-consumer-copy', text, 'bytes <= 12', 'bytes < 12',
         lambda: consumer_case(h, 41, 12, enabled=True), 'consumer-result', False),
        ('wide-consumer-copy', text, 'if (bytes <= 12 || bytes > NPU_TUNNEL_HEADER_BYTES)',
         'if (bytes <= 12)', lambda: consumer_case(h, 41, 129, enabled=True), 'consumer-result', False),
        ('reload-vxlan-index', assembly, 'slli s0, a0, 7', 'lbu s0, 8(s1)\n    slli s0, s0, 7',
         lambda: store_case(h, 0, 0, 50, enabled=True, mutate=True, mutation_index=20),
         'store-memory-footprint', True),
        ('reload-srv6-length', assembly, 'mv s2, a1', 'lbu s2, 9(s1)',
         lambda: store_case(h, 1, 0, 128, enabled=True, mutate=True), 'store-memory-footprint', True),
    ]
    rows = []
    for name, original, old, new, test, expected, is_assembly in variants:
        assert original.count(old) == 1, name
        file = BUILD/(name+('.S' if is_assembly else '.c'))
        file.write_text(original.replace(old, new, 1))
        compiled = build(assembly=file, tag=name) if is_assembly else build(source=file, tag=name)
        reset_code(h)
        h.header_rv, _ = install(h, compiled[1])
        try:
            test()
        except AssertionError as error:
            assert str(error) == expected, (name, str(error))
            rows.append(dict(name=name, detected=True, assertion=expected, source_sha256=sha(file.read_bytes())))
        else:
            raise AssertionError('surviving header mutant: '+name)
    for site, expected in ((0x84001eea, 'consumer-patch-length'), (0x84001f00, 'consumer-command-spans')):
        reset_code(h)
        h.header_rv, _ = install(h, paths[1], omit=site)
        try:
            consumer_case(h, 41, 128, enabled=True, mutate=True)
        except AssertionError as error:
            assert str(error) == expected, str(error)
            rows.append(dict(name='missing-snapshot-'+hex(site), detected=True, assertion=expected))
        else:
            raise AssertionError('missing snapshot was not detected')
    reset_code(h)
    h.header_rv, _ = install(h, paths[1])
    return rows


def retained_gate(paths, profile, reset):
    ring, _, _ = order.build()
    tx, _ = txdone.build()
    executions = []
    def extra(h):
        _, first = order.install(h, ring)
        _, second = install(h, paths[1])
        def code(cpu, pc, size, data):
            if 0x84054000 <= pc < 0x84058000:
                executions.append(pc)
        from unicorn import UC_HOOK_CODE
        h.cpu.hook_add(UC_HOOK_CODE, code)
        return first+second
    result = txdone.retained_gate(tx, profile, reset, bridge_bytes=layout.LAYOUT_HYPOTHESIS, install_extra=extra)
    assert result['name'] == 'all45-detours-installed-before-reset' and not executions
    return result


def smoke(h, path):
    rows = []
    for enabled in (False, True):
        if enabled:
            h.header_rv, h.header_patches = install(h, path)
        for kind, index, length in ((0, 0, 50), (0, 20, 50), (1, 0, 128), (1, 7, 129)):
            h.prepare()
            result, message, prefix = h.callback(kind, index, length)
            rows.append(dict(enabled=enabled, kind=kind, index=index, length=length, result=result,
                             payload_reads=h.header_reads, header_writes=[row for row in h.header_writes
                               if h.header_base <= row[0] < h.header_base+4096]))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    inputs = input_bindings()
    inputs.update({str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in
                   (Path(__file__), SOURCE, HEADER, ASM, LINKER, layout.LINKER, order.LINKER, txdone.LINKER)})
    paths = build()
    profile, _ = layout.build()
    reset, _ = layout.build_reset()
    h = Headers(profile, reset)
    if args.smoke:
        cases = smoke(h, paths[1])
        print(json.dumps(dict(smoke_cases=len(cases))))
        return
    original = [store_case(h, *case) for case in ((0, 20, 50), (0, 28, 50), (0, 29, 50),
                                                (1, 0, 129), (1, 7, 129), (1, 7, 255))]
    original += [consumer_case(h, 41, size) for size in (0, 11, 12, 13, 128, 129, 255)]
    h.header_rv, h.header_patches = install(h, paths[1])
    stores = [store_case(h, *case, enabled=True) for case in
              ((0, 0, 50), (0, 19, 50), (0, 20, 50), (0, 255, 50),
               (1, 0, 0), (1, 0, 128), (1, 7, 128), (1, 8, 128), (1, 0, 129), (1, 7, 255))]
    stores += [store_case(h, kind, index, length, available=available, enabled=True) for
               kind, index, length, available in ((0, 0, 50, 0), (0, 19, 50, 58),
                                                  (1, 0, 128, 9), (1, 7, 128, 137))]
    stores += [store_case(h, kind, 0, length, enabled=True, mutate=True) for kind, length in ((0, 50), (1, 128))]
    consumers = [consumer_case(h, udf, length, enabled=True) for udf, length in
                 ((40, 128), (49, 128), (41, 0), (41, 11), (41, 12), (41, 13), (41, 128),
                  (48, 128), (48, 129), (48, 255))]
    consumers += [consumer_case(h, 41, 128, enabled=True, mutate=True)]
    mailboxes = [mailbox_case(h, *case) for case in ((0, 0, 50, 59), (0, 20, 50, 59),
                 (1, 7, 128, 138), (1, 7, 129, 139), (1, 0, 128, 0), (0, 0, 50, 0x1003b))]
    backing = store_case(h, 1, 0, 128, enabled=True, backing=20)
    helpers = helper_cases(paths)
    mutants = mutations(h, paths)
    gate = retained_gate(paths, profile, reset)
    assert all(sha((ROOT/name).read_bytes()) == value for name, value in inputs.items())
    result = dict(schema=1, inputs_before_after=inputs, commands=paths[2],
                  binary_sha256=[sha(p.read_bytes()) for p in paths[:2]],
                  original_cases=original, store_cases=stores, consumer_cases=consumers,
                  mailbox_cases=mailboxes, backing_control=backing, helpers=helpers,
                  mutants=mutants, retained_gate=gate,
                  limits=['Header indices/lengths are captured once; payload contents are not claimed to be an atomic configuration snapshot.',
                          'Input backing, bridge allocation ownership and quiescent configuration remain caller contracts.',
                          'The original ISR route is isolated; strict candidate admission is not expanded.',
                          'Only command words and explicit available-slot register models execute, not physical DMA.',
                          'General packet format/length checks, MTU/translation source bounds and engine failure propagation remain open.',
                          'No image/router/Wi-Fi/subagent change; full NPU boot, cache/PMA, lifecycle and parity are incomplete.'])
    OUT.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    (OUT/'header-bounds.json').write_bytes(encoded)
    print(json.dumps(dict(original_cases=len(original), store_cases=len(stores), consumer_cases=len(consumers),
                          mailbox_cases=len(mailboxes), backing_control=backing,
                          decode_pairs=len(helpers['decode_pairs']), reader_pairs=len(helpers['reader_pairs']),
                          mutants=len(mutants), evidence_sha256=sha(encoded))))


if __name__ == '__main__':
    main()
