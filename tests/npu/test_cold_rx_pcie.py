#!/usr/bin/env python3
"""One-shot RX PCIe owner and final DESC10 memory, exact host-C/RV32 objects."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys

sys.dont_write_bytecode = True
import test_cold_txdone as done

ROOT, CORE, TESTS = done.ROOT, done.CORE, done.TESTS
METADATA, VALUE, BEFORE, READS = 0x3e902a90, 0x200d4590, 0xdeadbeef, 20998
FIELDS = ('pcie_state', 'pcie_plan', 'pcie_metadata', 'pcie_effects', 'pcie_reads',
          'pcie_read_count', 'pcie_fault_address', 'pcie_read_mode')


class Pair(done.Pair):
    def __init__(self, shared, elf):
        super().__init__(shared, elf)
        symbols = {s.name: s for s in self.rv.elf.get_section_by_name('.symtab').iter_symbols()}
        for name in FIELDS:
            symbol = symbols['npu_test_' + name]
            assert symbol['st_size'] and symbol['st_info']['type'] == 'STT_OBJECT'
            self.fields[name] = (symbol['st_value'], symbol['st_size'],
                (ctypes.c_uint8 * symbol['st_size']).in_dll(self.host, symbol.name))
        assert self.fields['pcie_state'][1] == 168 and self.fields['pcie_plan'][1] == 136

    def compare(self, names=None):
        super().compare(self.fields if names is None else names)

    def invoke(self, *args, **kwargs):
        result = super().invoke(*args, **kwargs)
        self.compare()
        return result

    def pcie(self, name, *values):
        return self.invoke('npu_test_pcie_' + name,
            [ctypes.c_uint32(v) for v in values], values)


def expected_reads(plan):
    """Literal final values, independently derived from the existing event oracle."""
    final = {}
    for address, width, value in done.expected_events(plan):
        final[(address, width)] = value
    ring = (plan[29] & 0x3fffffff) | 0x40000000
    check = (plan[19] & 0x3fffffff) | 0x40000000
    locations = []
    for i in range(512):
        locations.extend([(ring + i * 16 + offset, 4) for offset in (0, 4, 8, 12)])
        locations.append((plan[31] + i * 2, 2))
    locations.extend((plan[32] + i * 2, 2) for i in range(2048))
    for i in range(8192):
        locations.extend(((check + i * 2, 2), (plan[33] + i * 2, 2)))
    locations.extend(((0x3e902a7c, 2), (0x3e902cf4, 4), (0x3e901bb4, 2),
                      (0x3e901b94, 2), (0x3e903974, 4), (0x3e9046fa, 1)))
    assert len(locations) == READS and set(locations) == set(final)
    return [(address, width, final[(address, width)]) for address, width in locations]


def assert_reader(pair, plan):
    assert pair.values('pcie_read_count') == (READS,)
    actual = pair.values('pcie_reads')
    assert list(zip(actual[::3], actual[1::3], actual[2::3])) == expected_reads(plan)


def exercise(pair, exhaustive=True):
    assert pair.pcie('prepare', 0) == 0
    plan = pair.values('plan')
    events = done.expected_events(plan)
    done.assert_trace(pair, events, done.STORES)
    done.assert_memory(pair, plan, events)
    fresh = pair.snapshot()
    assert pair.pcie('memory_live', 1) == 1
    assert_reader(pair, plan)
    assert pair.pcie('begin', 1, 0) == 0
    assert_reader(pair, plan)
    begun = pair.snapshot()
    assert pair.pcie('finish', 1) != 0
    assert pair.values('pcie_state')[2:7] == (1, 1, 0, 0, 0)
    pair.restore(begun)
    assert pair.pcie('reserve', METADATA, 4, VALUE, BEFORE, 1) == 0
    assert_reader(pair, plan)
    reserved = pair.snapshot()
    assert pair.values('pcie_state')[3:7] == (1, 1, 1, 0)
    assert pair.pcie('effect', VALUE) == 0
    written = pair.snapshot()
    assert pair.pcie('publish', METADATA, 4, VALUE, 1) == 0
    assert_reader(pair, plan)
    published = pair.snapshot()
    assert pair.pcie('finish', 1) == 0 and pair.pcie('live', 1) == 1
    assert_reader(pair, plan)
    finished = pair.snapshot()
    assert pair.values('pcie_metadata') == (0x12345678, VALUE, 0x87654321)
    assert pair.values('pcie_effects') == (1,)
    assert pair.values('pcie_state')[:8] == (0x31455052, 1, 0, 0, 1, 1, 1, BEFORE)
    # All completed prior owners and logical target memory remain byte-identical.
    for name in done.NAMES:
        assert finished[name] == fresh[name], ('prior-changed', name)
    controls = []

    def denied(label, saved, name, args, mutation=None, committed=0, published_count=0):
        pair.restore(saved)
        if mutation:
            field, offset, value = mutation
            pair.setword(field, offset, value)
        before_prior = {name: bytes(pair.fields[name][2]) for name in done.NAMES}
        metadata = pair.values('pcie_metadata')
        effects = pair.values('pcie_effects')
        assert pair.pcie(name, *args) != 0, label
        state = pair.values('pcie_state')
        assert state[2] == 1 and state[5:7] == (committed, published_count), label
        assert pair.values('pcie_metadata') == metadata and pair.values('pcie_effects') == effects, label
        assert all(bytes(pair.fields[k][2]) == v for k, v in before_prior.items()), label
        controls.append(label)

    denied('reinitialize-finished', finished, 'begin', (1, 0), committed=1, published_count=1)
    denied('wrong-store-value', begun, 'reserve', (METADATA, 4, VALUE ^ 1, BEFORE, 1))
    denied('wrong-store-preimage', begun, 'reserve', (METADATA, 4, VALUE, BEFORE ^ 1, 1))
    denied('wrong-store-address', begun, 'reserve', (METADATA + 4, 4, VALUE, BEFORE, 1))
    denied('wrong-readback', written, 'publish', (METADATA, 4, VALUE ^ 1, 1), committed=1)
    denied('finish-without-publication', written, 'finish', (1,), committed=1)
    denied('reserve-twice', reserved, 'reserve', (METADATA, 4, VALUE, BEFORE, 1), committed=1)
    denied('publish-twice', published, 'publish', (METADATA, 4, VALUE, 1), committed=1, published_count=1)
    denied('late-prior-fault', written, 'publish', (METADATA, 4, VALUE, 1),
           ('state', 8, 1), committed=1)
    denied('begin-wrong-bar', fresh, 'begin', (1, 0), ('pcie_plan', 4, 0x20100000))
    denied('begin-no-ready', fresh, 'begin', (1, 256))
    denied('begin-no-reader', fresh, 'begin', (1, 8))
    if exhaustive:
        pair.restore(fresh)
        assert pair.pcie('begin', 1, 1) != 0
        assert bytes(pair.fields['pcie_state'][2]) == fresh['pcie_state']
        assert pair.values('pcie_metadata') == (0x12345678, BEFORE, 0x87654321)
        controls.append('begin-null-state-no-write')
        for offset, value in ((0, 0), (4, 2), (8, 1), (12, 2),
                              (16, 2), (20, 2), (24, 2), (28, BEFORE ^ 1)):
            denied(f'owner-header-{offset}', begun, 'reserve',
                   (METADATA, 4, VALUE, BEFORE, 1), ('pcie_state', offset, value),
                   committed=2 if offset == 20 else 0, published_count=2 if offset == 24 else 0)
        for offset in range(0, 136, 4):
            original = struct.unpack_from('<I', fresh['pcie_plan'], offset)[0]
            denied(f'owner-plan-{offset}', begun, 'reserve',
                   (METADATA, 4, VALUE, BEFORE, 1), ('pcie_state', 32 + offset, original ^ 1))
            denied(f'incoming-plan-{offset}', written, 'publish',
                   (METADATA, 4, VALUE, 1), ('pcie_plan', offset, original ^ 1), committed=1)
        for field, offset, value in (('pcie_metadata', 4, VALUE ^ 1),
                                     ('state', 8, 1), ('packet', 16, 3071),
                                     ('rx', 24, 0), ('ready', 0, 0), ('queue', 0, 0)):
            pair.restore(finished)
            pair.setword(field, offset, value)
            before_owner = bytes(pair.fields['pcie_state'][2])
            assert pair.pcie('live', 1) == 0, field
            assert bytes(pair.fields['pcie_state'][2]) == before_owner, ('live-write', field)
            controls.append(f'live-read-only-{field}')
        for epoch in (0, 2, 0xffffffff):
            denied(f'begin-epoch-{epoch}', fresh, 'begin', (epoch, 0))
        for missing in (2, 4, 16, 32, 64, 128):
            denied(f'begin-missing-{missing}', fresh, 'begin', (1, missing))
        for width in (0, 1, 2, 3, 8, 0xffffffff):
            denied(f'store-width-{width}', begun, 'reserve', (METADATA, width, VALUE, BEFORE, 1))
        for address in (0, METADATA - 4, METADATA + 1, 0xffffffff):
            denied(f'store-address-{address}', begun, 'reserve', (address, 4, VALUE, BEFORE, 1))
        for value in (0, 1, 0xffffffff, VALUE - 4, VALUE + 4):
            denied(f'store-value-{value}', begun, 'reserve', (METADATA, 4, value, BEFORE, 1))
        for stage, saved, command, args, c, p in (
            ('begin', fresh, 'begin', (1, 0), 0, 0),
            ('reserve', begun, 'reserve', (METADATA, 4, VALUE, BEFORE, 1), 0, 0),
            ('publish', written, 'publish', (METADATA, 4, VALUE, 1), 1, 0),
            ('finish', published, 'finish', (1,), 1, 1)):
            for field, offset, value in (
                ('state', 12, 1), ('state', 24, done.STORES - 1),
                ('state', 36, 511), ('state', 44, 0),
                ('state', done.OWNER_BITMAP, pair.values('state')[done.OWNER_BITMAP // 4] ^ 1),
                ('rx', 24, 0), ('packet', 16, 3071), ('packet', 28, 0),
                ('ready', 0, 0xa5a5a500), ('ring', 0, 0), ('ids', 0, 0),
                ('temp', 0, 0), ('check', 0, 0xffffffff), ('queue', 0, 0),
                ('count', 0, 0), ('pointer', 0, 0), ('skb_head', 0, 0),
                ('skb_tail', 0, 1), ('counter', 0, 1)):
                denied(f'{stage}-{field}-{offset}', saved, command, args,
                       (field, offset, value), c, p)
        # Read failure/corruption at the beginning, middle and end of every array.
        for field, size in (('ring', 8192), ('ids', 1024), ('temp', 4096),
                            ('check', 16384), ('queue', 16384)):
            for offset in (0, size // 2, size - 4):
                pair.restore(fresh)
                old = struct.unpack_from('<I', fresh[field], offset)[0]
                pair.setword(field, offset, old ^ 1)
                prior = {name: bytes(pair.fields[name][2]) for name in done.NAMES}
                assert pair.pcie('memory_live', 1) == 0, (field, offset)
                assert all(bytes(pair.fields[k][2]) == v for k, v in prior.items())
                controls.append(f'projection-{field}-{offset}')
        for mode in (1, 2, 3):
            pair.restore(fresh)
            pair.setword('pcie_fault_address', 0, 0x3e9046fa)
            pair.setword('pcie_read_mode', 0, mode)
            assert pair.pcie('memory_live', 1) == 0
            controls.append(f'reader-final-{mode}')
        for alias in (1, 2):
            assert pair.pcie('prepare', alias) == 0
            assert pair.pcie('memory_live', 1) == 1
            assert_reader(pair, pair.values('plan'))
    return dict(passed=True, calls=pair.calls, controls=controls,
        final_read_cells=READS, owner_bytes=168, plan_bytes=136,
        modeled_tail_effects=1, prior_constructor_effects=done.STORES)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--core-directory', type=Path, required=True)
    parser.add_argument('--skip-mutants', action='store_true')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-pcie-tail-20261014' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    core = args.core_directory.resolve()
    assert core.is_relative_to(ROOT) and core.is_dir()
    names = ('cold-rx-pcie', 'cold-txdone', 'cold-rx-event', 'cold-tx-buffer', 'cold-packet')
    sources = [CORE / (name + '.c') for name in names]
    objects = [core / (name + '.o') for name in names]
    fixtures = [TESTS / 'cold-txdone-fixture.c', TESTS / 'cold-rx-pcie-fixture.c']
    ld = TESTS / 'cold-txdone-probe.ld'
    inputs = {str(p.relative_to(ROOT)): done.tx.loader.sha(p) for p in
        sources + objects + fixtures + list(CORE.glob('*.h')) + [ld, Path(__file__),
        Path(done.__file__), Path(done.tx.__file__), Path(done.tx.loader.__file__),
        Path(done.tx.loader.extract.__file__), TESTS / 'test_barrier_protocol.py',
        CORE / 'cold-page.c', CORE / 'Makefile', core / 'libw1700k-npu.a']}
    command = [shutil.which('clang'), '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-I' + str(CORE)]
    linker = shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'
    flags = ['--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32', '-nostdlib',
        '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '--ld-path=' + str(linker), '-Wl,-T,' + str(ld)]
    host, elf = dest / 'host.so', dest / 'owner.elf'
    run = done.tx.loader.run
    run(command + ['-shared', '-fPIC', *sources, *fixtures, '-o', host], dest / 'host-build.log')
    run(command + [*flags, *objects, *fixtures, '-o', elf], dest / 'rv-build.log')
    result = exercise(Pair(host, elf))
    print(json.dumps(dict(nominal_and_controls=True, calls=result['calls'], controls=len(result['controls']))), flush=True)
    sanitizer = dest / 'sanitize'
    run(command + ['-DNPU_PCIE_SANITIZER', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
        *sources, *fixtures, '-o', sanitizer], dest / 'sanitize-build.log')
    run([sanitizer], dest / 'sanitize.log', env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1'))
    changes = {
        'ignore-prior-memory': (0, 'npu_cold_txdone_memory_live(c->done, &p->prior, epoch, c->rx,\n               c->rx_readback, c->packets, c->ready, c->read, c->opaque)', '((void)epoch, 1)'),
        'ignore-store-value': (0, 'value != npu_cold_rx_pcie_value(p))', '(0 && value != npu_cold_rx_pcie_value(p)))'),
        'ignore-preimage': (0, 'before != s->before ||', '(0 && before != s->before) ||'),
        'ignore-readback': (0, 'if (readback != npu_cold_rx_pcie_value(p))', 'if (0 && readback != npu_cold_rx_pcie_value(p))'),
        'omit-possible-effect': (0, 's->reserved = s->committed = 1;', 's->reserved = 1;'),
        'allow-reinitialize': (0, 'if (words[i])', 'if (0 && words[i])'),
        'wrong-final-control': (1, 'descriptor + 4, 4, 0x07000100u', 'descriptor + 4, 4, 0'),
        'omit-final-memory': (1, '!matches(read, opaque, p->temporary + i * 2, 2, s->occupied[i])', '0'),
    }
    mutants = []
    if not args.skip_mutants:
        for name, (index, old, new) in changes.items():
            original = sources[index].read_text()
            assert original.count(old) == 1, name
            out = dest / 'mutants' / name
            out.mkdir(parents=True)
            mutated = out / (names[index] + '.c')
            mutated.write_text(original.replace(old, new))
            selected = list(sources)
            selected[index] = mutated
            mhost, melf = out / 'host.so', out / 'owner.elf'
            run(command + ['-shared', '-fPIC', *selected, *fixtures, '-o', mhost], out / 'host-build.log')
            run(command + [*flags, *selected, *fixtures, '-o', melf], out / 'rv-build.log')
            try:
                exercise(Pair(mhost, melf), exhaustive=False)
            except AssertionError:
                mutants.append(dict(name=name, host_sha256=done.tx.loader.sha(mhost), rv_sha256=done.tx.loader.sha(melf)))
            else:
                raise AssertionError(('mutant-survived', name))
            print(json.dumps(dict(mutant=name, rejected=True)), flush=True)
    assert all(done.tx.loader.sha(ROOT / p) == digest for p, digest in inputs.items())
    result.update(inputs=inputs, mutants=mutants, sanitizers=['address', 'undefined', 'leak'],
        exact_objects=[str(p.relative_to(ROOT)) for p in objects],
        binaries={str(p.relative_to(ROOT)): done.tx.loader.sha(p) for p in (host, elf, sanitizer)},
        limits=['Portable objects with completed prior owners constructed by their actual portable APIs.',
                'Final read trace matches an independent literal store oracle; entire logical prior memory is compared.',
                'No original PCIe store, native allocator/session/locks, full sender, physical or device execution.',
                'API0 admission remains closed until the actual native binding is implemented.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, calls=result['calls'], controls=len(result['controls']), mutants=len(mutants))))


if __name__ == '__main__':
    main()
