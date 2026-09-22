#!/usr/bin/env python3
"""SRv6 extent checks through native ingress, dispatch and command encoding."""
import ctypes as ct
import itertools
import json
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_CODE
from unicorn import riscv_const as r
from elftools.elf.elffile import ELFFile

import test_egress_guards as egress
from test_barrier_protocol import Rv32
from test_barrier_core5 import jump
from test_bridge_startup import input_bindings, UnmodeledAccess
from emulation_layout import CODE, SRAM, STATE

headers = egress.headers
ROOT = headers.ROOT
BUILD = ROOT/'.local/npu-tunnel-packets'
OUT = ROOT/'research/checkpoints/2026-09-10-npu-tunnel-packets'
SOURCE = ROOT/'firmware/npu/tunnel-packet.c'
HEADER = SOURCE.with_suffix('.h')
ASM = ROOT/'tests/npu/tunnel-packet-emulation.S'
LINKER = ASM.with_suffix('.ld')
SITES = {0x84001e92: 'preflight', 0x84001f3a: 'tail'}
PACKET, PACKET_BYTES = 0x38000000, 0x11000
FIFO = egress.BRIDGE+0x80+7*16
CACHED = SRAM+0x13a8-0x718+7*4
START, OUTER = 0x84000b3e, 0x84000b36


def build(egress_path, source=SOURCE, assembly=ASM, tag='packet'):
    BUILD.mkdir(parents=True, exist_ok=True)
    native, rv = BUILD/(tag+'.so'), BUILD/(tag+'.elf')
    common = ['-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
              '-I', str(SOURCE.parent), str(source)]
    lld = shutil.which('ld.lld') or str(ROOT/'.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld')
    commands = [[shutil.which('gcc'), *common, '-shared', '-fPIC', '-fsanitize=undefined',
                 '-fno-sanitize-recover=all', '-o', str(native)],
                [shutil.which('clang'), *common, '--target=riscv32', '-march=rv32imac_zicsr',
                 '-mabi=ilp32', '-nostdlib', '-fno-stack-protector', f'--ld-path={lld}', str(assembly),
                 '-Wl,-T,'+str(LINKER)+',--no-relax', '-Wl,--just-symbols='+str(egress_path), '-o', str(rv)]]
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout+result.stderr
    with rv.open('rb') as stream:
        elf = ELFFile(stream)
        sections = [dict(name=s.name, address=s['sh_addr'], bytes=s['sh_size'])
                    for s in elf.iter_sections() if s['sh_flags'] & 2 and s['sh_size']]
    assert sections and all(0x8405a000 <= s['address'] < s['address']+s['bytes'] <= 0x8405c000 for s in sections)
    return native, rv, dict(commands=commands, sections=sections,
                            sha256=[headers.sha(p.read_bytes()) for p in (native, rv)])


def install(h, path, omit=None):
    for site in SITES:
        h.cpu.mem_write(site, h.code[site-CODE:site-CODE+4])
    rv = Rv32(path, h.cpu)
    assert rv.symbols['npu_emulation_egress_fault'] == h.egress_rv.symbols['npu_emulation_egress_fault']
    patches = []
    for site, name in SITES.items():
        if site == omit:
            continue
        before = bytes(h.cpu.mem_read(site, 4))
        target = rv.symbols['npu_emulation_srv6_'+name]
        replacement = jump(site, target)
        h.cpu.mem_write(site, replacement)
        patches.append(dict(site=hex(site), target=hex(target), name=name,
                            before=before.hex(), after=replacement.hex()))
    h.cpu.ctl_remove_cache(CODE, CODE+0x201000)
    return rv, patches


def expected(args):
    channel, total, packet, udf, l3, size, base = args
    tail = total-32-l3
    return int(0 <= channel < 8 and 41 <= udf <= 48 and packet != 0 and 32 <= total <= 65567
               and 14 <= l3 <= 127 and tail > 0 and 54 <= size <= 128
               and 0 <= tail+size-54 <= 65535
               and packet+total <= 0xffffffff and (packet & 0x1fffffff)+total <= 0x20000000
               and base+(udf-21)*128+size <= 0xffffffff
               and (base & 0x1fffffff)+(udf-21)*128+size <= 0x20000000)


class Helpers:
    def __init__(self, paths):
        self.lib = ct.CDLL(str(paths[0]))
        self.fn = self.lib.npu_tunnel_srv6_extent_valid
        self.fn.argtypes = [ct.c_uint32]*7
        self.fn.restype = ct.c_uint32
        self.rv = Rv32(paths[1])

    def check(self, args):
        for reg, value in zip(egress.ARGS, args):
            self.rv.cpu.reg_write(reg, value)
        self.rv.cpu.reg_write(r.UC_RISCV_REG_RA, egress.END)
        self.rv.cpu.reg_write(r.UC_RISCV_REG_SP, headers.allocator.STACK)
        self.rv.cpu.emu_start(self.rv.symbols['npu_tunnel_srv6_extent_valid'], egress.END,
                             count=10000, timeout=1000000)
        assert self.rv.cpu.reg_read(r.UC_RISCV_REG_PC) == egress.END
        actual = self.rv.cpu.reg_read(r.UC_RISCV_REG_A0)
        assert self.fn(*args) == actual == expected(args), 'extent-predicate'
        return (*args, actual)


def helper_cases(paths):
    base = (7, 256, PACKET, 41, 14, 78, 0x3e870000)
    cases = {base}
    sweeps = [list(range(10))+[0xffffffff],
              [0, 31, 32, 45, 46, 47, 50, 51, 54, 55, 256, 65521, 65535, 65567, 65568, 0xffffffff],
              [0, 1, 0x1fffff00, 0x20000000, PACKET, 0x3fffff00, 0xfffff000, 0xfffffff0],
              list(range(58))+[0xffffffff], list(range(160))+[0xffffffff],
              list(range(256))+[0xffffffff], [0, 0x1fffff00, 0x20000000, 0x3e870000, 0xfffff000, 0xfffffff0]]
    for index, values in enumerate(sweeps):
        for value in values:
            row = list(base)
            row[index] = value
            cases.add(tuple(row))
    for channel, udf, total, l3, size in itertools.product((0, 7), (41, 48),
            (47, 50, 51, 54, 55, 96, 256, 65521, 65535, 65567), (14, 18, 22, 127), (54, 78, 94, 110, 126, 128)):
        cases.add((channel, total, PACKET, udf, l3, size, base[-1]))
    for alias, udf, size, delta in itertools.product((0, 0x20000000, 0xe0000000), (41, 48), (54, 128), (-1, 0, 1)):
        end = (udf-21)*128+size
        cases.add((7, 256, PACKET, udf, 14, size, (0x20000000-end+delta) | alias))
        cases.add((7, 256, (0x20000000-256+delta) | alias, udf, 14, size, base[-1]))
    rng = random.Random(0x5a6)
    for _ in range(512):
        cases.add((rng.randrange(10), rng.randrange(65580), rng.choice(sweeps[2]),
                   rng.randrange(39, 51), rng.randrange(130), rng.randrange(50, 133), rng.choice(sweeps[-1])))
    helper = Helpers(paths)
    return [helper.check(args) for args in sorted(cases)]


def template(size):
    data = bytearray((i*11+3) & 255 for i in range(size))
    if size >= 54:
        data[12:14] = b'\x86\xdd'
        data[14:22] = bytes([0x60, 0, 0, 0, 0, 0, 4 if size == 54 else 43, 64])
        data[22:38] = bytes.fromhex('20010db8000000000000000000000001')
        data[38:54] = bytes.fromhex('20010db8000000000000000000000002')
    if size in (78, 94, 110, 126):
        segments = (size-62)//16
        data[54:62] = bytes([4, (size-54)//8-1, 4, segments-1, segments-1, 0, 0, 0])
    return bytes(data)


class Packets(egress.Egress):
    def __init__(self, profile, reset, header_path, egress_path, packet_path=None):
        self.packet_rv = None
        self.packet_pending = None
        self.packet_missing = None
        super().__init__(profile, reset, header_path, egress_path)
        self.cpu.mem_map(PACKET, PACKET_BYTES)
        self.spaces = (*self.spaces, (PACKET, PACKET_BYTES))
        self.snapshot = [(base, bytes(self.cpu.mem_read(base, size))) for base, size in self.spaces]
        if packet_path:
            self.packet_rv, self.packet_patches = install(self, packet_path)

    def is_memory(self, address, size):
        return PACKET <= address and address+size <= PACKET+PACKET_BYTES or super().is_memory(address, size)

    def register_model(self, address, write):
        if self.egress_tracking and address == self.packet_missing:
            return None
        if address == FIFO and not write:
            return 'explicit ingress FIFO address hypothesis; CPU alias and descriptor read execute, no physical ownership proof'
        return super().register_model(address, write)

    def code_hook(self, cpu, pc, size, data):
        if self.egress_tracking and self.packet_pending:
            if pc == 0x84000b48:
                sp = cpu.reg_read(r.UC_RISCV_REG_SP)
                self.ingress = dict(result=cpu.reg_read(r.UC_RISCV_REG_A0), total=self.get32(sp+8),
                                    pointer=self.get32(sp+12), cached=self.get32(CACHED))
            if self.packet_rv and pc == self.packet_rv.symbols['npu_tunnel_srv6_extent_valid']:
                self.validated = [cpu.reg_read(reg) for reg in egress.ARGS[:7]]
        super().code_hook(cpu, pc, size, data)

    def run(self, start, stops):
        if start == START and self.packet_pending:
            wire, l3, size, udf, mutate = self.packet_pending
            self.return_pc = OUTER
            stops = [OUTER, *stops[1:]]
            self.ingress = self.validated = None
            self.put32(CACHED, 0)
            self.put32(FIFO, PACKET & 0x1fffffff)
            self.cpu.reg_write(r.UC_RISCV_REG_S1, 0xffffffff)
            data = bytearray((i*17+5) & 255 for i in range(wire))
            if l3 in (14, 18, 22) and wire >= l3:
                l2 = bytes(range(12))+b'\x81\x00\x00\x01'*((l3-14)//4)+b'\x08\x00'
                data[:l3] = l2
                if wire-l3 >= 20:
                    data[l3:l3+4] = b'\x45\x00'+struct.pack('>H', wire-l3)
            self.input_wire = bytes(data)
            descriptor = bytearray(32)
            struct.pack_into('<I', descriptor, 0, wire | l3 << 20)
            struct.pack_into('<I', descriptor, 20, udf)
            self.cpu.mem_write(PACKET, bytes(descriptor)+bytes(data))
            self.initial_packet = bytes(descriptor)+bytes(data)
            self.template = template(size)
            self.cpu.mem_write(self.header_base+(udf-21)*128, self.template)
            if mutate:
                assert self.packet_rv
                fields = [(headers.LENGTHS+udf-41, 255)]
                fields += [(PACKET+i, byte) for i, byte in enumerate(struct.pack('<I', 127 << 20 | 1))]
                fields += [(SRAM+0x184c+i, 0) for i in range(4)]
                self.header_mutation = (self.packet_rv.symbols['npu_emulation_srv6_preflight_checked'], fields)
            self.before = egress.memory(self)
        return super().run(start, stops)

    def packet(self, wire, l3=14, size=78, udf=41, fail_at=None, mutate=False):
        assert 0 <= wire <= 65535 and 0 <= l3 <= 127 and 41 <= udf <= 48 and 13 <= size <= 128
        self.packet_pending = (wire, l3, size, udf, mutate)
        statuses = [0x101, 0x100, 0x100, 0x100]
        if fail_at is not None:
            statuses[1+fail_at] = 0
        result = self.execute(START, [], statuses=statuses, header_length=size)
        assert self.ingress == dict(result=0, total=wire+32, pointer=PACKET, cached=0), 'native-ingress'
        assert self.get32(CACHED) == 0
        if self.packet_rv:
            assert self.validated == [7, wire+32, PACKET, udf, l3, size, self.header_base], 'captured-preflight-inputs'
        return result


def materialize(h):
    """Explicit byte-assembly model of these commands, not an executed DMA engine."""
    chunks = []
    for channel, source, span, flags, *patches in h.commands:
        assert channel == 7
        length, offset = span >> 16, span & 0xffff
        if source == (PACKET & 0x1fffffff):
            address = PACKET
        else:
            address = h.header_base+(h.packet_pending[3]-21)*128
            assert source == address & 0x1fffffff
        chunk = bytearray(h.cpu.mem_read(address+offset, length))
        for patch in patches:
            if not patch:
                continue
            assert patch >> 16 == 0xc012
            struct.pack_into('<H', chunk, 18-offset, patch & 0xffff)
        chunks.append(bytes(chunk))
    return b''.join(chunks)[32:]


def successful(h, wire, l3=14, size=78, udf=41, mutate=False):
    assert h.packet(wire, l3, size, udf, mutate=mutate) == 0 and h.stop_pc == OUTER
    assert not h.failure and len(h.commands) == 3 and h.io_writes == egress.io(h.commands)
    assert h.commands[-1][2] == (wire-l3) << 16 | (32+l3), 'tail-source-extent'
    assert bytes(h.cpu.mem_read(PACKET+32, wire)) == h.input_wire
    assert len(h.length_reads) == 1
    expected_header = bytearray(h.template)
    struct.pack_into('>H', expected_header, 18, wire-l3+size-54)
    wanted = h.input_wire[:12]+bytes(expected_header[12:])+h.input_wire[l3:]
    output = materialize(h)
    assert output == wanted, 'assembled-packet'
    assert struct.unpack_from('>H', output, 18)[0] == len(output)-54, 'ipv6-payload-length'
    assert h.cpu.reg_read(r.UC_RISCV_REG_SP) == egress.STACK-64
    assert [h.cpu.reg_read(reg) for reg in egress.SAVED if reg != r.UC_RISCV_REG_S1] == [
        h.abi_before[i] for i, reg in enumerate(egress.SAVED) if reg != r.UC_RISCV_REG_S1]
    assert h.cpu.reg_read(r.UC_RISCV_REG_S1) == 0xffffffff
    assert [h.cpu.reg_read(reg) for reg in (r.UC_RISCV_REG_GP, r.UC_RISCV_REG_TP)] == h.abi_before[-2:]
    assert h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) == h.input_status
    return dict(wire_bytes=wire, l3=l3, header_bytes=size, udf=udf, mutation_after_check=mutate,
                ingress=h.ingress, commands=h.commands, modeled_output_bytes=len(output),
                modeled_output_sha256=headers.sha(output), physical_dma_executed=False)


def native_cases(original, checked):
    rows = []
    for l3, size, udf in itertools.product((14, 18, 22), (54, 78, 94, 110, 126), (41, 48)):
        row = successful(checked, 256, l3, size, udf)
        assert original.packet(256, l3, size, udf) == 0
        old_output = materialize(original)
        assert len(old_output)-54-struct.unpack_from('>H', old_output, 18)[0] == l3-14
        if l3 == 14:
            assert old_output == materialize(checked)
            for base in (headers.HEAP, SRAM, headers.layout.RING, headers.layout.L2, PACKET, egress.BRIDGE):
                assert original.after[base] == checked.after[base], 'untagged-native-memory'
        row['original_extra_inner_bytes'] = l3-14
        rows.append(row)
    rows.append(successful(checked, 65525, 14, 78))
    rows.append(successful(checked, 65535, 14, 54))
    rows.append(successful(checked, 256, 18, 78, mutate=True))
    return rows


def rejected_cases(original, h):
    rows = []
    for wire, l3, size in ((0, 14, 78), (13, 14, 78), (14, 14, 78), (17, 18, 78),
                           (18, 18, 78), (21, 22, 78), (22, 22, 78), (126, 127, 78),
                           (256, 0, 78), (256, 13, 78), (256, 14, 13), (256, 14, 53),
                           (65526, 14, 78), (65535, 14, 128)):
        h.packet(wire, l3, size)
        row = egress.assert_hold(h, 4, [])
        assert not h.commands and len(h.availability) == 1, 'preflight-before-egress'
        assert bytes(h.cpu.mem_read(PACKET, wire+32)) == h.initial_packet, 'preflight-before-packet-write'
        assert h.header_entries[0x840017da] == 0
        rows.append(dict(wire_bytes=wire, l3=l3, header_bytes=size, **row))
    original.packet(13, 14, 78)
    assert original.failure['reason'] == 3 and len(original.commands) == 2
    rows[1]['preceding_checkpoint_submitted_prefix'] = 2
    return rows


def controls(h):
    rows = []
    h.packet(256, 18, 78)
    baseline = list(h.commands)
    for index in range(3):
        h.packet(256, 18, 78, fail_at=index)
        row = egress.assert_hold(h, 2, baseline[:index])
        assert len(h.availability) == index+2
        rows.append(dict(failed_command=index, **row))
    h.packet_missing = FIFO
    try:
        h.packet(256)
    except UnmodeledAccess as error:
        assert hex(FIFO) in str(error) and not h.commands and not h.failure
        rows.append(dict(missing_ingress_model=str(error)))
    else:
        raise AssertionError('missing ingress model accepted')
    finally:
        h.packet_missing = None
    return rows


def mutations(h, egress_path, paths):
    text = SOURCE.read_text()
    normal = [7, 256, PACKET, 41, 14, 78, h.header_base]
    changes = [
        ('wire-count', 'total - 32 > UINT16_MAX', '0', [7, 65568, PACKET, 41, 127, 54, h.header_base]),
        ('empty-tail', 'total <= 32 + l3', 'total < 32 + l3', [7, 46, PACKET, 41, 14, 54, h.header_base]),
        ('short-ipv6', 'header_bytes < 54', '0', [7, 256, PACKET, 41, 14, 53, h.header_base]),
        ('payload-wrap', 'tail_bytes > UINT16_MAX - (header_bytes - 54)', '0',
         [7, 65567, PACKET, 41, 14, 128, h.header_base]),
        ('packet-aperture', 'source_extent(packet, total) && ', '', [7, 256, 0x3ffffff0, 41, 14, 78, h.header_base]),
        ('header-aperture', 'source_extent(header_base, header_end)', '1', [*normal[:-1], 0x3fffff00]),
    ]
    rows = []
    for name, before, after, args in changes:
        assert text.count(before) == 1 and not expected(args)
        changed = text.replace(before, after)
        if name == 'payload-wrap':
            changed = changed.replace('uint32_t tail_bytes, header_end;', 'uint32_t header_end;').replace('    tail_bytes = total - 32 - l3;\n', '')
        if name == 'header-aperture':
            changed = changed.replace('uint32_t tail_bytes, header_end;', 'uint32_t tail_bytes;').replace('    header_end = (udf - 21) * 128 + header_bytes;\n', '')
            changed = changed.replace('    uint32_t tail_bytes;\n', '    uint32_t tail_bytes;\n\n    (void)header_base;\n')
        file = BUILD/(name+'.c')
        file.write_text(changed)
        altered = build(egress_path, source=file, tag=name)
        try:
            Helpers(altered).check(args)
        except AssertionError as error:
            assert str(error) == 'extent-predicate'
            rows.append(dict(name=name, detected=True, assertion=str(error), binary=altered[2]))
        else:
            raise AssertionError('undetected predicate mutant '+name)
    for site, name, test in ((0x84001e92, 'missing-preflight', lambda: rejected_cases_single(h)),
                             (0x84001f3a, 'fixed-tail-offset', lambda: successful(h, 256, 18, 78))):
        h.packet_rv, _ = install(h, paths[1], omit=site)
        if site == 0x84001e92:
            h.packet_rv = None
        try:
            test()
        except AssertionError as error:
            assert str(error) in ('captured-preflight-inputs', 'fault-reason', 'tail-source-extent')
            rows.append(dict(name=name, detected=True, assertion=str(error)))
        else:
            raise AssertionError('undetected native mutant '+name)
    h.packet_rv, _ = install(h, paths[1])
    return rows


def rejected_cases_single(h):
    h.packet(13, 14, 78)
    egress.assert_hold(h, 4, [])


def retained_gate(packet_path, egress_path, header_path, profile, reset):
    ring, _, _ = headers.order.build()
    tx, _ = headers.txdone.build()
    executions = []
    def extra(h):
        _, first = headers.order.install(h, ring)
        _, second = headers.install(h, header_path)
        h.egress_rv, third = egress.install(h, egress_path)
        _, fourth = install(h, packet_path)
        def code(cpu, pc, size, data):
            if 0x84054000 <= pc < 0x8405c000:
                executions.append(pc)
        h.cpu.hook_add(UC_HOOK_CODE, code)
        return first+second+third+fourth
    result = headers.txdone.retained_gate(tx, profile, reset, bridge_bytes=headers.layout.LAYOUT_HYPOTHESIS,
                                         install_extra=extra)
    assert result['name'] == 'all50-detours-installed-before-reset' and not executions
    return result


def main():
    inputs = input_bindings()
    bound = [Path(__file__), SOURCE, HEADER, ASM, LINKER, egress.ASM, egress.LINKER,
             headers.SOURCE, headers.HEADER, headers.ASM, headers.LINKER,
             headers.layout.LINKER, headers.order.LINKER, headers.txdone.LINKER]
    inputs.update({str(p.relative_to(ROOT)): headers.sha(p.read_bytes()) for p in bound})
    eg, _ = egress.build()
    paths = build(eg)
    helpers = helper_cases(paths)
    header_path = headers.build()[1]
    profile, _ = headers.layout.build()
    reset, _ = headers.layout.build_reset()
    original = Packets(profile, reset, header_path, eg)
    checked = Packets(profile, reset, header_path, eg, paths[1])
    accepted = native_cases(original, checked)
    rejected = rejected_cases(original, checked)
    engine = controls(checked)
    mutants = mutations(checked, eg, paths)
    gate = retained_gate(paths[1], eg, header_path, profile, reset)
    assert all(headers.sha((ROOT/name).read_bytes()) == value for name, value in inputs.items())
    result = dict(schema=1, inputs_before_after=inputs, binary=paths[2], patches=checked.packet_patches,
                  helper_pairs=helpers, accepted_native=accepted, rejected_native=rejected,
                  controls=engine, mutants=mutants, retained_gate=gate,
                  format_references=['https://www.rfc-editor.org/rfc/rfc8200.html#section-3',
                                     'https://www.rfc-editor.org/rfc/rfc8754.html#section-2'],
                  limits=['Native ingress count/address/descriptor instructions execute against explicit FIFO/storage models, not physical ownership.',
                          'Packet byte assembly and 16-bit overwrite interpretation are explicit models, not an executed DMA engine.',
                          'The helper validates extents and ordinary IPv6 payload arithmetic, not L2/IP/SRH contents, jumbograms, MTU or configuration atomicity.',
                          'Backing/alias/cache, normal backpressure/reservation, all other tunnel paths and complete NPU boot/recovery/parity remain open.',
                          'No admission expansion, package/source-lock/overlay, image, router, Wi-Fi, subagent or protected-data change.'])
    OUT.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    (OUT/'packet-extents.json').write_bytes(encoded)
    print(json.dumps(dict(helper_pairs=len(helpers), accepted_native=len(accepted), rejected_native=len(rejected),
                          controls=len(engine), mutants=len(mutants), evidence_sha256=headers.sha(encoded))))


if __name__ == '__main__':
    main()
