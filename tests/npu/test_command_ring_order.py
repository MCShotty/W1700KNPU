#!/usr/bin/env python3
"""Native queue ordering adapters plus pinned herd/RVWMO projections."""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import re
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r
from elftools.elf.elffile import ELFFile

import test_command_ring_layout as queue
import test_allocator_protocol as allocator
import test_allocator_startup as startup
import test_txdone_init as txdone
from test_barrier_core5 import jump
from test_barrier_protocol import Rv32
from test_firmware_memory_layout import NativeMemory, STACK_TOPS
from test_mt7996_bootstrap_sequence import exports
from test_bridge_startup import input_bindings
from emulation_layout import CODE, HEAP, HEAP_BYTES, SRAM, SRAM_BYTES

ROOT = allocator.ROOT
OUT = ROOT/'research/checkpoints/2026-09-09-npu-ring-order'
BUILD = ROOT/'.local/npu-ring-order'
ASM = ROOT/'tests/npu/command-ring-order-emulation.S'
LINKER = ASM.with_suffix('.ld')
HERD_SOURCE = ROOT/'.local/npu-herd/herdtools7'
MODEL = HERD_SOURCE/'herd/libdir'
HERD_COMMIT = '1ca343e16a2038e406d1ac674e7e3a1b722b36c7'
FENCE, NOP = 0x0ff0000f, 0x00000013
SITES = {0x8400c96c: ('publish', 0x8400c970),
         0x8400cc1e: ('consumer_acquire', 0x8400cc22),
         0x8400cc4e: ('consumer_release', 0x8400cc52)}
FENCES = ('producer_acquire', 'producer_release', 'consumer_acquire', 'consumer_release')
REGS = [getattr(r, 'UC_RISCV_REG_X'+str(i)) for i in range(1, 32)]
BASELINE = ROOT/'tests/npu/litmus/ring-publication-baseline.litmus'


def sha(data):
    return allocator.sha(data)


def build():
    BUILD.mkdir(parents=True, exist_ok=True)
    path = BUILD/'ring-order.elf'
    lld = shutil.which('ld.lld') or str(ROOT/'.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld')
    command = [shutil.which('clang'), '--target=riscv32', '-march=rv32imac_zicsr',
               '-mabi=ilp32', '-nostdlib', '-g', f'--ld-path={lld}', str(ASM),
               '-Wl,-T,'+str(LINKER)+',--no-relax', '-o', str(path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout+result.stderr
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        sections = [dict(name=s.name, address=s['sh_addr'], bytes=s['sh_size'])
                    for s in elf.iter_sections() if s['sh_flags'] & 2 and s['sh_size']]
    assert sections == [dict(name='.text', address=0x84054000, bytes=44)]
    return path, command, sections


def install(h, path, mask=15):
    rv = Rv32(path, h.cpu)
    patches = []
    for pc, (name, resume) in SITES.items():
        before = bytes(h.cpu.mem_read(pc, 4))
        assert before == h.code[pc-CODE:pc-CODE+4]
        target = rv.symbols['npu_emulation_ring_'+name]
        replacement = jump(pc, target)
        h.cpu.mem_write(pc, replacement)
        patches.append(dict(site=hex(pc), name=name, before=before.hex(), after=replacement.hex(),
                            target=hex(target), resume=hex(resume)))
    for bit, name in enumerate(FENCES):
        pc = rv.symbols['npu_emulation_ring_'+name]
        assert h.get32(pc) == FENCE
        if not mask & (1 << bit):
            h.put32(pc, NOP)
    h.cpu.ctl_remove_cache(CODE, CODE+0x201000)
    return rv, patches


class OrderedSlice(queue.RingSlice):
    def __init__(self, h, address, path, mask=15):
        super().__init__(h, address)
        self.order_rv, self.order_patches = install(self, path, mask)
        self.boundaries = {self.order_rv.symbols['npu_emulation_ring_'+name]: name for name in FENCES}
        self.replayed = {self.order_rv.symbols['npu_emulation_ring_'+name]: original for name, original in
                         (('store_token', 0x8400c96c), ('store_command', 0x8400c96e),
                          ('store_read_index', 0x8400cc4e))}
        self.operations = []
        self.cpu.hook_add(UC_HOOK_CODE, self.code_hook)

    def code_hook(self, cpu, pc, size, data):
        if self.phase and pc in self.boundaries and self.get32(pc) == FENCE:
            self.operations.append(dict(kind='fence', phase=self.phase, pc=hex(pc),
                                        name=self.boundaries[pc], word=FENCE))

    def read(self, cpu, access, address, size, value, data):
        if self.phase and self.address <= address < self.address+0x8000:
            self.operations.append(dict(kind='read', phase=self.phase, address=address, size=size,
                                        value=self.get32(address), pc=hex(cpu.reg_read(r.UC_RISCV_REG_PC))))
        super().read(cpu, access, address, size, value, data)

    def write(self, cpu, access, address, size, value, data):
        if self.phase and self.address <= address < self.address+0x8000:
            self.operations.append(dict(kind='write', phase=self.phase, address=address, size=size,
                                        value=value, pc=hex(cpu.reg_read(r.UC_RISCV_REG_PC))))
        previous = len(self.events)
        super().write(cpu, access, address, size, value, data)
        if len(self.events) > previous:
            event = self.events[-1]
            self.events[-1] = (*event[:4], self.replayed.get(event[4], event[4]))


def projection(h, path, mask):
    q = OrderedSlice(h, queue.RING, path, mask)
    q.producer(17, 136)
    q.consumer()
    operations = {}
    for phase in ('producer', 'consumer'):
        values = []
        for op in q.operations:
            if op['phase'] != phase:
                continue
            if op['kind'] == 'fence':
                values.append(('fence', op['name']))
            else:
                assert op['size'] == 4 and 0 <= op['address']-queue.RING <= 8
                values.append((op['kind'], op['address']-queue.RING, op['value']))
        operations[phase] = values
    expected_p = [('read', 0, 254)]
    if mask & 1:
        expected_p += [('fence', FENCES[0])]
    expected_p += [('write', 4, 17), ('write', 8, 136)]
    if mask & 2:
        expected_p += [('fence', FENCES[1])]
    expected_p += [('write', 0, 4)]
    expected_c = [('read', 0, 4)]
    if mask & 4:
        expected_c += [('fence', FENCES[2])]
    expected_c += [('read', 0, 4), ('read', 4, 17), ('read', 8, 136)]
    if mask & 8:
        expected_c += [('fence', FENCES[3])]
    expected_c += [('write', 0, 254)]
    assert operations == dict(producer=expected_p, consumer=expected_c)
    return dict(mask=mask, operations=operations, trace=q.operations, patches=q.order_patches)


def isolated_detours(path):
    original, corrected = NativeMemory(), NativeMemory()
    rv, patches = install(corrected, path)
    reads, writes, fences = {}, {}, []
    for label, h in (('original', original), ('corrected', corrected)):
        reads[label], writes[label] = [], []
        def read(cpu, access, address, size, value, data, label=label):
            reads[label].append((address, size))
        def write(cpu, access, address, size, value, data, label=label):
            writes[label].append((address, size, value))
        h.cpu.hook_add(UC_HOOK_MEM_READ, read)
        h.cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    def code(cpu, pc, size, data):
        if 0x84054000 <= pc < 0x84056000 and corrected.get32(pc) == FENCE:
            fences.append(pc)
    corrected.cpu.hook_add(UC_HOOK_CODE, code)
    rng = random.Random(0x1700f00)
    stack = STACK_TOPS[6]-0x100
    spaces = ((HEAP, HEAP_BYTES), (SRAM, SRAM_BYTES), (queue.RING, queue.RING_BYTES), (stack, 256))
    rows = []
    for site, (name, resume) in SITES.items():
        for sample in range(64):
            for mstatus in (0, 8):
                registers = [rng.getrandbits(32) for _ in REGS]
                registers[1] = stack
                if name == 'publish':
                    registers[13] = queue.RING+rng.randrange(2048)*16
                elif name == 'consumer_release':
                    registers[9] = queue.READ_INDEX+0x568
                images = [(base, bytes(rng.randrange(256) for _ in range(size)) if size == 256
                           else bytes([sample])*size) for base, size in spaces]
                states = []
                fences.clear()
                for label, h in (('original', original), ('corrected', corrected)):
                    for base, data in images:
                        h.cpu.mem_write(base, data)
                    for reg, value in zip(REGS, registers):
                        h.cpu.reg_write(reg, value)
                    h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, mstatus)
                    h.cpu.reg_write(r.UC_RISCV_REG_MIE, 0x800)
                    reads[label].clear()
                    writes[label].clear()
                    h.cpu.emu_start(site, resume, count=100, timeout=1000000)
                    assert h.cpu.reg_read(r.UC_RISCV_REG_PC) == resume
                    states.append(([h.cpu.reg_read(reg) for reg in REGS],
                                   h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS), h.cpu.reg_read(r.UC_RISCV_REG_MIE),
                                   [bytes(h.cpu.mem_read(base, size)) for base, size in spaces]))
                assert states[0] == states[1], name
                assert reads['original'] == reads['corrected'] and writes['original'] == writes['corrected'], name
                assert len(fences) == (2 if name == 'publish' else 1), name
                rows.append(dict(site=hex(site), sample=sample, mstatus=mstatus,
                                 register_sha256=sha(struct.pack('<31I', *states[0][0])),
                                 data_writes=writes['corrected'].copy(), fences=[hex(pc) for pc in fences]))
    return dict(cases=rows, patches=patches, same_gpr_and_mstatus_mie=True,
                compared_regions=[dict(address=hex(base), bytes=size) for base, size in spaces])


def native_cycles(h, legacy, path):
    rows = []
    for source, address in ((h, queue.RING), (legacy, legacy.get32(queue.POINTER))):
        for full in (False, True):
            instances = []
            def factory(h, address):
                q = OrderedSlice(h, address, path)
                instances.append(q)
                return q
            function = queue.full_queue if full else queue.ring_cycle
            actual = function(source, address, slice_factory=factory)
            q = instances[0]
            counts = Counter(op['name'] for op in q.operations if op['kind'] == 'fence')
            assert counts == {name: actual['producer_consumer_pairs'] for name in FENCES}
            rows.append(dict(full_queue=full, original_footprint_checks=actual,
                             fence_counts=dict(counts), actual_trace_sha256=sha(json.dumps(q.operations).encode()),
                             write_pc_translation={hex(a): hex(b) for a, b in q.replayed.items()}))
    return rows


def gate(path, profile, reset):
    executed, patches = [], []
    def install_extra(h):
        _, rows = install(h, path)
        patches.extend(rows)
        def code(cpu, pc, size, data):
            if 0x84054000 <= pc < 0x84056000:
                executed.append(pc)
        h.cpu.hook_add(UC_HOOK_CODE, code)
        return rows
    tx, _ = txdone.build()
    result = txdone.retained_gate(tx, profile, reset, bridge_bytes=queue.LAYOUT_HYPOTHESIS,
                                  install_extra=install_extra)
    assert result['name'] == 'all40-detours-installed-before-reset'
    assert not executed
    return dict(control=result, new_patches=patches, no_new_adapter_execution=True)


def litmus(proof, kind, field, good=False):
    mask = proof['mask']
    name = f'Ring{kind.title()}{"Success" if good else field.title()}M{mask}'
    producer = ['lw x4,0(x1)', 'li x5,254', 'bne x4,x5,P0done']
    consumer = ['lw x4,0(x1)', 'li x5,254', 'beq x4,x5,P1done']
    registers = {0: 'x1', 4: 'x2', 8: 'x3'}
    for phase, output in (('producer', producer), ('consumer', consumer)):
        # Keep the real first-status branch and the traced duplicate consumer
        # status load. Other per-hart index/statistic accesses are projected out.
        for op in proof['operations'][phase][1:]:
            if op[0] == 'fence':
                output.append('fence rw,rw')
            elif op[0] == 'read':
                destination = {0: 'x8', 4: 'x6', 8: 'x7'}[op[1]]
                output.append(f'lw {destination},0({registers[op[1]]})')
            else:
                output += [f'li x9,{op[2]}', f'sw x9,0({registers[op[1]]})']
        output += [('P0done:' if phase == 'producer' else 'P1done:'), 'nop']
    if kind == 'publication':
        initial = 'flag=254; token=0; command=0;'
        wanted = f'1:x4=4 /\\ 1:x8=4 /\\ 1:{"x6" if field == "token" else "x7"}=0'
        if good:
            wanted = '0:x4=254 /\\ 1:x4=4 /\\ 1:x8=4 /\\ 1:x6=17 /\\ 1:x7=136 /\\ flag=254'
    else:
        assert kind == 'reclamation'
        initial = 'flag=4; token=51; command=68;'
        value = 17 if field == 'token' else 136
        wanted = f'0:x4=254 /\\ 1:x4=4 /\\ 1:x8=4 /\\ 1:{"x6" if field == "token" else "x7"}={value}'
        if good:
            wanted = '0:x4=254 /\\ 1:x4=4 /\\ 1:x8=4 /\\ 1:x6=51 /\\ 1:x7=68 /\\ flag=4 /\\ token=17 /\\ command=136'
    lines = [f'RISCV {name}', '{', initial,
             '0:x1=flag; 0:x2=token; 0:x3=command;',
             '1:x1=flag; 1:x2=token; 1:x3=command;', '}', 'P0 | P1 ;']
    for index in range(max(len(producer), len(consumer))):
        left = producer[index] if index < len(producer) else ''
        right = consumer[index] if index < len(consumer) else ''
        lines.append(f'{left:<26} | {right:<26} ;')
    lines += [f'exists ({wanted})', '']
    return name, '\n'.join(lines)


def herd(proofs, check):
    assert subprocess.check_output(['git', '-C', str(HERD_SOURCE), 'rev-parse', 'HEAD'], text=True).strip() == HERD_COMMIT
    assert not subprocess.check_output(['git', '-C', str(HERD_SOURCE), 'status', '--porcelain'], text=True)
    version = subprocess.check_output(['herd7', '-version'], text=True).strip()
    assert version == '7.58, Rev: exported'
    models = {str(path.relative_to(MODEL)): sha(path.read_bytes()) for path in sorted(MODEL.glob('*.cat'))}
    rows = []
    baseline = subprocess.run(['herd7', '-I', str(MODEL), '-model', 'riscv.cat', str(BASELINE)],
                              capture_output=True, text=True, timeout=30)
    assert baseline.returncode == 0 and not baseline.stderr
    assert 'Observation RingPublicationBaseline Sometimes 2 3' in baseline.stdout
    directory = OUT/'litmus'
    directory.mkdir(parents=True, exist_ok=True)
    for proof in proofs:
        for kind in ('publication', 'reclamation'):
            for field in ('token', 'command', 'success'):
                good = field == 'success'
                name, source = litmus(proof, kind, field, good)
                path = directory/(name+'.litmus')
                if check:
                    assert path.read_text() == source
                else:
                    path.write_text(source)
                command = ['herd7', '-I', str(MODEL), '-model', 'riscv.cat', str(path)]
                result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                assert result.returncode == 0 and not result.stderr, result.stdout+result.stderr
                match = re.search(r'^Observation '+name+r' (\w+) (\d+) (\d+)$', result.stdout, re.M)
                assert match, result.stdout
                observation, positive, negative = match.groups()
                mask = proof['mask']
                protected = bool(mask & 2 and mask & 4) if kind == 'publication' else bool(mask & 8)
                assert observation == ('Never' if protected and not good else 'Sometimes'), (name, result.stdout)
                normalized = re.sub(r'^Time .*\n', '', result.stdout, flags=re.M)
                rows.append(dict(name=name, mask=mask, kind=kind, field=field,
                                 success_witness=good, observation=observation, positive=int(positive), negative=int(negative),
                                 input_sha256=sha(source.encode()), output=normalized))
    assert all(sha((MODEL/name).read_bytes()) == value for name, value in models.items())
    return dict(version=version, binary_sha256=sha(Path(shutil.which('herd7')).read_bytes()),
                baseline_output=re.sub(r'^Time .*\n', '', baseline.stdout, flags=re.M),
                model_commit=HERD_COMMIT, models=models, cases=rows,
                r_w_projection='Native fence iorw,iorw is projected to its R/W ordering; no device-I/O or cache/PMA model.',
                scope='One aligned slot, immutable base, owned indices, two harts and ordinary coherent memory. Not complete firmware executions.')


def direct_call_chains(functions):
    rows = []
    for target in (0x8400c284, 0x8400cd1a, 0x8400e800, 0x84000aca,
                   0x8400cb0e, 0x8400e7f8, 0x84000aa6):
        calls = []
        for entry, function in functions.items():
            pattern = r'ram:([0-9a-f]+) (?:c\.)?(?:jal|j) (?:ra,)?0x'+f'{target:x}'+r'\b'
            for site in re.findall(pattern, function['assembly']):
                calls.append(dict(pc='0x'+site, owner=hex(entry), line=function['line']))
        assert len(calls) == 1, (hex(target), calls)
        rows.append(dict(target=hex(target), callers=calls))
    assert '"core6_main"' in functions[0x84000aca]['text']
    assert '"core5_main"' in functions[0x84000aa6]['text']
    return dict(direct_callers=rows, producer_hart=6, consumer_hart=5,
                indirect_alias_or_reentry_closure=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    inputs = input_bindings()
    inputs.update({str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in
                   (Path(__file__), ASM, LINKER, queue.LINKER, txdone.LINKER, BASELINE)})
    path, command, sections = build()
    profile, _ = queue.build()
    reset, _ = queue.build_reset()
    h = queue.Profile(profile, reset)
    normal, _ = startup.build()
    legacy = startup.StartupBridge(normal, reset)
    functions = exports()
    for owner, line in ((0x8400c284, 'ram:8400c784 beq a3,a0,0x8400c96c'),
                        (0x8400cb0e, 'ram:8400cbd8 bne a4,s1,0x8400cc1e')):
        assert line in functions[owner]['assembly']
    proofs = [projection(h, path, mask) for mask in range(16)]
    formal = herd(proofs, args.check)
    print(json.dumps(dict(formal_cases=len(formal['cases']), full_fence_bad_outcomes=0)), flush=True)
    registers = isolated_detours(path)
    cycles = native_cycles(h, legacy, path)
    retained = gate(path, profile, reset)
    assert all(sha((ROOT/name).read_bytes()) == value for name, value in inputs.items())
    result = dict(schema=1, inputs_before_after=inputs, command=command, sections=sections,
                  elf_sha256=sha(path.read_bytes()), projections=proofs, formal=formal,
                  isolated_detours=registers, native_cycles=cycles, retained_gate=retained,
                  direct_call_chains=direct_call_chains(functions),
                  limits=['Four full I/O-memory fences in three detours preserve the native data/status/index operations.',
                          'Formal witnesses concern one aligned slot and two harts under ordinary coherent-memory RVWMO assumptions.',
                          'Producer acquire is redundant in these litmus cases because the native status branch orders later stores; it is retained conservatively.',
                          'Unicorn checks actual instructions and data/register footprints but does not implement the weak-memory model.',
                          'Cache/PMA/alias, loader backing, full pointer/consumer closure, physical drains and full NPU boot/recovery remain open.'])
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT/'ring-order.json'
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    if args.check:
        assert output.read_bytes() == encoded
    else:
        output.write_bytes(encoded)
    print(json.dumps(dict(native_projections=len(proofs), formal_cases=len(formal['cases']),
                          register_pairs=len(registers['cases']), native_queue_pairs=sum(
                              row['original_footprint_checks']['producer_consumer_pairs'] for row in cycles),
                          evidence_sha256=sha(encoded))))


if __name__ == '__main__':
    main()
