#!/usr/bin/env python3
"""Fixed extents with native metadata, same-C RV32 checks and legacy regression."""
import argparse
from dataclasses import dataclass, replace
import json
from pathlib import Path
import random
import struct
import sys

sys.dont_write_bytecode = True
import test_allocator_protocol as p

ROOT = p.ROOT
OUT = ROOT/'research/checkpoints/2026-09-09-npu-command-ring'
RING, RING_BYTES = 0x84060000, 0x8010


@dataclass
class Case(p.Case):
    placements: tuple = ((0x19, 0, RING),)
    placement_count: int | None = None
    missing: bool = False


def oracle(c):
    # The existing oracle owns common argument/definition validation, with an
    # empty state and unlimited primary capacity to keep placement policy here.
    base_case = replace(c, size=p.U32-c.base if c.base else c.size,
                        state=p.empty(), after_lock=None, deny=0)
    status = p.oracle(base_case)[0][0]
    if status in (p.ARGUMENT, p.LAYOUT):
        return (status, 0), c.state, (0, 0)
    if not c.size or c.base+c.size > p.U32:
        return (p.LAYOUT, 0), c.state, (0, 0)
    known = {kind: (16 if tag else 32, size) for group in c.defs
             for kind, tag, _, size in group}
    count = len(c.placements) if c.placement_count is None else c.placement_count
    if count > 100 or (count and c.missing):
        return (p.LAYOUT, 0), c.state, (0, 0)
    fixed, spans = {}, [(c.base, c.base+c.size)]
    for kind, reserved, address in (c.placements+((0, 0, 0),)*100)[:count]:
        if kind not in known or reserved or not address or kind in fixed:
            return (p.LAYOUT, 0), c.state, (0, 0)
        alignment, size = known[kind]
        end = address+size
        if address % alignment or end > p.U32 or any(address < b and a < end for a, b in spans):
            return (p.LAYOUT, 0), c.state, (0, 0)
        fixed[kind] = address
        spans.append((address, end))
    if c.type not in known:
        return (p.UNKNOWN, 0), c.state, (0, 0)
    if c.deny:
        return (p.DENIED, 0), c.state, (1, 0)
    current = c.after_lock if c.after_lock is not None else c.state
    count, attempts, used = (struct.unpack_from('<I', current, n)[0] for n in (8, 16, 20))
    if count > 100 or used > c.size:
        return (p.CORRUPT, 0), current, (1, 1)
    cursor, cached = 0, {}
    for index in range(count):
        kind, reserved, address = struct.unpack_from('<HHI', current, 24+index*8)
        if kind not in known or reserved or kind in cached:
            return (p.CORRUPT, 0), current, (1, 1)
        alignment, size = known[kind]
        wanted = fixed.get(kind)
        if wanted is None:
            start = ((cursor+alignment-1)//alignment)*alignment
            cursor = start+size
            wanted = c.base+start
        if cursor > c.size or wanted != address:
            return (p.CORRUPT, 0), current, (1, 1)
        cached[kind] = address
    if cursor != used:
        return (p.CORRUPT, 0), current, (1, 1)
    if c.type in cached:
        return (p.OK, cached[c.type]), current, (1, 1)
    alignment, size = known[c.type]
    address = fixed.get(c.type)
    if address is None:
        start = ((cursor+alignment-1)//alignment)*alignment
        cursor = start+size
        address = c.base+start
    if count == 100 or cursor > c.size:
        return (p.CAPACITY, 0), current, (1, 1)
    result = bytearray(current)
    struct.pack_into('<HHI', result, 24+count*8, c.type, 0, address)
    struct.pack_into('<I', result, 8, count+1)
    struct.pack_into('<II', result, 16, (attempts+1) & p.U32, cursor)
    return (p.OK, address), bytes(result), (1, 1)


def state_for(defs, order, placements):
    state = p.empty()
    for kind in order:
        result, state, _ = oracle(Case('state-builder', defs, kind, int(kind < 129),
                                      state, placements=placements))
        assert result[0] == p.OK
    return state


class Pair(p.Pair):
    def placed_case(self, case, differential=True):
        def configure():
            values = bytearray(800)
            for index, row in enumerate(case.placements):
                struct.pack_into('<HHI', values, index*8, *row)
            self.put('placements', values)
            count = len(case.placements) if case.placement_count is None else case.placement_count
            self.lib.npu_allocator_test_place(count, int(case.missing))
            self.rv_call('place', count, int(case.missing))
        return self.case(case, differential, configure, oracle(case))


def cases():
    defs = p.definitions()
    fixed = ((0x19, 0, RING),)
    one = state_for(defs, [0x19], fixed)
    rows = [Case('fixed-new', defs, 0x19, 1), Case('fixed-cache', defs, 0x19, 1, one),
            Case('heap-after-fixed', defs, 0x89, 0, one),
            Case('fixed-denied', defs, 0x19, 1, deny=1),
            Case('fixed-at-lock', defs, 0x19, 1, after_lock=one),
            Case('fixed-bad-after-lock', defs, 0x19, 1,
                 after_lock=p.changed(one, 28, 'I', RING+32)),
            Case('fixed-counter-wrap', defs, 0x19, 1, p.changed(p.empty(), 16, 'I', p.U32)),
            Case('missing-placements', defs, 0x19, 1, missing=True),
            Case('too-many-placements', defs, 0x19, 1, placement_count=101),
            Case('empty-declared-placement', defs, 0x19, 1, placement_count=2),
            Case('ignored-empty-pointer', defs, 0x19, 1, placement_count=0)]
    for label, placements in (
        ('zero', ((25, 0, 0),)), ('unaligned', ((25, 0, RING+16),)),
        ('wrapped', ((25, 0, 0xffffffe0),)), ('reserved', ((25, 1, RING),)),
        ('unknown', ((0x80, 0, RING),)), ('wide-type', ((0x100, 0, RING),)),
        ('duplicate-type', ((25, 0, RING), (25, 0, RING+0x10000))),
        ('same-address', ((25, 0, RING), (2, 0, RING))),
        ('overlap-left', ((25, 0, RING), (2, 0, RING-32))),
        ('overlap-right', ((25, 0, RING), (2, 0, RING+RING_BYTES-16))),
        ('heap-inside', ((25, 0, p.BASE),)),
        ('heap-left', ((25, 0, p.BASE-32),)),
        ('heap-right', ((25, 0, p.BASE+p.BYTES-32),)),
        ('heap-contained', ((1, 0, p.BASE-32),)),
        ('touch-before', ((0x89, 0, p.BASE-32),)),
        ('touch-after', ((25, 0, p.BASE+p.BYTES),)),
    ):
        rows.append(Case(label, defs, 25, 1, placements=placements))
    rows[-3].size = 64
    for label, offset, fmt, value in (
        ('fixed-null-cache', 28, 'I', 0), ('fixed-wrong-cache', 28, 'I', RING+32),
        ('fixed-used-counted', 20, 'I', RING_BYTES), ('fixed-entry-reserved', 26, 'H', 1),
        ('fixed-count-overflow', 8, 'I', 101),
    ):
        rows.append(Case(label, defs, 25, 1, p.changed(one, offset, fmt, value)))
    small = [[], [(1, 0, 0, 32), (25, 0, 0, RING_BYTES)]]
    rows.append(Case('full-heap-fixed-new', small, 25, 1,
                     state_for(small, [1], fixed), size=32))
    many = [[], [(kind, 0, 0, 32) for kind in range(1, 103)]]
    placements = tuple((kind, 0, RING+kind*32) for kind in range(1, 101))
    full = state_for(many, list(range(1, 101)), placements)
    rows += [Case('full-cache-fixed-reuse', many, 100, 1, full, placements=placements),
             Case('full-cache-new-reject', many, 101, 1, full, placements=placements)]
    rng = random.Random(0x170019)
    for iteration in range(60):
        defs = [[], [(kind, rng.randrange(2), 0, rng.randrange(1, 2048)) for kind in range(1, 16)]]
        order = list(range(1, 16))
        rng.shuffle(order)
        placements = tuple((kind, 0, RING+kind*4096) for kind in rng.sample(order, rng.randrange(1, 15)))
        for index in range(16):
            current = state_for(defs, order[:index], placements)
            rows.append(Case(f'mixed-{iteration}-{index}', defs, order[index % 15], 1,
                             current, placements=placements))
    return rows


def mutations(scenarios):
    source = p.SOURCE.read_text()
    variants = [
        ('ignore-placement-layout', ' && valid_placements(layout)',
         ' && (valid_placements(layout), 1)', 'heap-inside'),
        ('skip-fixed-cache-check', ' || entry->address != address', '', 'fixed-wrong-cache'),
        ('charge-fixed-to-heap', '*end = used;', '*end = used + d->bytes;', 'fixed-new'),
        ('skip-fixed-count-limit', 'count == NPU_ALLOCATOR_ENTRIES || ', '', 'full-cache-new-reject'),
        ('skip-fixed-metadata-used', 'return cursor == state->used;', 'return 1;', 'fixed-used-counted'),
        ('skip-placement-duplicate', 'p->type == other->type ||', '0 ||', 'duplicate-type'),
        ('skip-placement-overlap', 'p->address < other->address + other_d->bytes',
         '((void)other_d->bytes, 0)', 'same-address'),
        ('skip-placement-alignment', '(p->address & (alignment - 1))',
         '((void)alignment, 0)', 'unaligned'),
    ]
    results = []
    for name, old, new, case_name in variants:
        assert source.count(old) == 1, name
        path = p.BUILD/(name+'.c')
        path.write_text(source.replace(old, new, 1))
        build = p.build(path, name)
        pair = Pair(build)
        try:
            pair.placed_case(scenarios[case_name], differential=False)
        except AssertionError as error:
            assert case_name in str(error), str(error)
            results.append(dict(name=name, detected=True, source_sha256=p.sha(path.read_bytes())))
        else:
            raise AssertionError('surviving placement mutant: '+name)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    inputs = {str(path.relative_to(ROOT)): p.sha(path.read_bytes()) for path in
              (Path(__file__), p.SOURCE, p.HEADER, p.BINDING, p.LINKER, Path(p.__file__),
               ROOT/'tests/npu/allocator-concurrency.c')}
    paths = p.build(tag='placement')
    pair = Pair(paths)
    baseline = p.cases()
    old = [pair.case(case) for case in baseline]
    print(json.dumps(dict(legacy_pairs=len(old))), flush=True)
    scenarios = cases()
    rows = [pair.placed_case(case) for case in scenarios]
    print(json.dumps(dict(placement_pairs=len(rows))), flush=True)
    mutants = mutations({case.name: case for case in scenarios})
    old_mutants = p.mutations({case.name: case for case in baseline})
    concurrency = p.concurrency()
    placement_concurrency = p.concurrency(placements=True)
    assert all(p.sha((ROOT/name).read_bytes()) == value for name, value in inputs.items())
    result = dict(schema=1, inputs_before_after=inputs, commands=paths[2],
                  compiled_sha256=[p.sha(path.read_bytes()) for path in paths[:2]],
                  legacy_cases=old, placement_cases=rows, mutants=mutants,
                  legacy_mutants=old_mutants, concurrency=concurrency,
                  placement_concurrency=placement_concurrency,
                  limits=['Optional immutable placements retain native metadata and consume no primary-heap bytes.',
                          'Backing, object initialization and one non-aliasing physical address namespace are caller contracts.',
                          'No firmware image, cache-coherence, loader containment or hardware lock proof.'])
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT/'allocator-placement.json'
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    if args.check:
        assert output.read_bytes() == encoded
    else:
        output.write_bytes(encoded)
    print(json.dumps(dict(legacy_pairs=len(old), placement_pairs=len(rows),
                          mutants=len(mutants)+len(old_mutants), evidence_sha256=p.sha(encoded))))


if __name__ == '__main__':
    main()
