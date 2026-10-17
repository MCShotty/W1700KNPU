#!/usr/bin/env python3
"""Portable PCIe0/2/15 owner using exact normal-build RV32 objects."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

sys.dont_write_bytecode = True
import test_cold_rx_pcie as pcie

ROOT, CORE, TESTS = pcie.ROOT, pcie.CORE, pcie.TESTS
HERE = Path(__file__).resolve().parent
BASE, MAGIC = 0x20000000, 0x31545043
FIELDS = ("tail_state", "tail_plan", "tail_tx", "tail_cells", "tail_addresses",
          "tail_events", "tail_effects", "tail_reads", "tail_mutation",
          "tail_mutated", "tail_read_failure", "tail_late_owner", "tail_late_address")


class Pair(pcie.Pair):
    def __init__(self, shared, elf, native):
        self.native = native
        super().__init__(shared, elf)
        symbols = {s.name: s for s in self.rv.elf.get_section_by_name(".symtab").iter_symbols()}
        for name in FIELDS:
            symbol = symbols["npu_test_" + name]
            size = symbol["st_size"]
            assert size and symbol["st_info"]["type"] == "STT_OBJECT"
            self.fields[name] = (symbol["st_value"], size,
                (ctypes.c_uint8 * size).in_dll(self.host, symbol.name))
        assert self.fields["tail_state"][1] == 256
        assert self.fields["tail_plan"][1] == 180 and self.fields["tail_tx"][1] == 80

    def compare(self, names=None):
        if self.native:
            super().compare(names)

    def invoke(self, name, host, native, **kwargs):
        if self.native:
            return super().invoke(name, host, native, **kwargs)
        function = getattr(self.host, name)
        function.restype = ctypes.c_uint32
        self.calls += 1
        return function(*host)

    def tail(self, name, *values):
        return self.invoke("npu_test_tail_" + name,
            [ctypes.c_uint32(v) for v in values], values)


def stores(hif2):
    """Literal original order and actual caller operands, independent of C recipe."""
    return [(0x3e902cf0, 4, BASE + 0xd4580),
            (BASE + 0xd4588, 4, 1535),
            (0x3e903904, 4, BASE + 0xd4560 + hif2 * 0x4000),
            (BASE + 0xd4568 + hif2 * 0x4000, 4, 1023),
            (BASE + 0xd45a8, 4, 255), (BASE + 0xd45b8, 4, 511),
            (BASE + 0xd45c8, 4, 1023), (BASE + 0xa048, 4, 1535),
            (BASE + 0xd4598, 4, 511)]


def exercise(pair, exhaustive):
    controls, nominal = [], []
    phases = None

    def late_fault(label, saved, command, args, owner, address, read_only):
        pair.restore(saved)
        pair.setword('tail_late_owner', 0, owner)
        pair.setword('tail_late_address', 0, address)
        before = pair.snapshot()
        result = pair.tail(command, *args)
        assert (result == 0 if read_only else result != 0), (label, 'late-owner-accepted', result)
        assert pair.values('tail_mutated') == (1,), (label, 'late-owner-not-injected')
        wanted = {name: bytearray(data) for name, data in before.items()}
        if owner <= 6:
            field = ('packet', 'state', 'rx', 'tail_tx', 'pcie_state', 'tail_state')[owner - 1]
            struct.pack_into('<I', wanted[field], 8, 1)
        else:
            field, offset = (('packet', 16), ('state', 36), ('rx', 24))[owner - 7]
            value = struct.unpack_from('<I', wanted[field], offset)[0]
            struct.pack_into('<I', wanted[field], offset, value - 1 if owner < 9 else 0)
        if not read_only: struct.pack_into('<I', wanted['tail_state'], 8, 1)
        for name, data in wanted.items():
            if name not in ('tail_reads', 'tail_mutated'):
                assert bytes(pair.fields[name][2]) == data, (label, 'late-owner-unexpected-write', name)
        controls.append(label)

    for hif2 in (0, 1):
        assert pair.tail("prepare", hif2) == 0
        expected = stores(hif2)
        assert pair.values("tail_addresses") == tuple(s[0] for s in expected)
        assert pair.values("tail_plan")[34:40] == (
            0x3e810000, 303168, BASE, 0x100000, BASE + 0xd4420,
            BASE + 0xd4450 + hif2 * 0x4000)
        fresh = pair.snapshot()
        prior = {name: data for name, data in fresh.items() if name not in FIELDS}
        cells = list(pair.values("tail_cells"))
        initial_cells = tuple(cells)
        states = {"fresh": fresh}
        for stage, selector in enumerate((0, 2, 15)):
            first, last = stage * 2, (stage + 1) * 2 if stage < 2 else 9
            states[f"pre-{stage}"] = pair.snapshot()
            assert pair.tail("begin", selector, expected[first][2] if stage < 2 else 0, 1) == 0
            state = pair.values("tail_state")
            assert state[:10] == (MAGIC, 1, 0, 1, stage, (1 << (stage + 1)) - 1,
                                 (1 << stage) - 1, first, first, (1 << last) - 1)
            assert state[55:last + 55] == initial_cells[:last]
            assert state[last + 55:] == (0,) * (9 - last)
            states[f"begun-{stage}"] = pair.snapshot()
            for i in range(first, last):
                address, width, value = expected[i]
                states[f"before-{i}"] = pair.snapshot()
                assert pair.tail("reserve", address, width, value, cells[i]) == 0
                assert pair.values("tail_state")[7:9] == (i + 1, i)
                assert pair.values("tail_cells") == tuple(cells)
                states[f"reserved-{i}"] = pair.snapshot()
                assert pair.tail("effect", i, value) == 0
                cells[i] = value
                states[f"written-{i}"] = pair.snapshot()
                assert pair.tail("publish", address, width, value) == 0
                assert pair.values("tail_state")[7:9] == (i + 1, i + 1)
                assert pair.values("tail_cells") == tuple(cells)
                states[f"published-{i}"] = pair.snapshot()
            assert pair.tail("finish") == 0
            assert pair.values("tail_state")[3:9] == (
                0, stage, (1 << (stage + 1)) - 1, (1 << (stage + 1)) - 1, last, last)
            states[f"finished-{stage}"] = pair.snapshot()
            assert pair.tail("stage_live", stage) == 1
            assert pair.tail("stage_live", (stage + 1) % 3) == 0
            assert pair.tail("stage_live", 3) == 0
        assert pair.tail("live") == 1
        assert pair.values("tail_effects") == (9,)
        events = pair.values("tail_events")
        assert list(zip(events[::3], events[1::3], events[2::3])) == expected
        assert all(bytes(pair.fields[k][2]) == v for k, v in prior.items())
        nominal.append({"hif2": hif2, "ordered_effects": expected, "stores": 9})
        if not hif2:
            phases = states

        for stage in range(3):
            last = (stage + 1) * 2 if stage < 2 else 9
            for boundary, address in (('metadata', 0x3e902a7c), ('prefix', expected[last - 1][0])):
                for owner in range(1, 10):
                    late_fault(f'hif{hif2}-stage{stage}-late-{boundary}-owner{owner}',
                        states[f'finished-{stage}'], 'stage_live', (stage,), owner, address, True)
        for command, state, args in (
            ('begin', 'fresh', (0, BASE + 0xd4580, 1)),
            ('reserve', 'begun-0', (*expected[0], initial_cells[0])),
            ('publish', 'written-0', expected[0]),
            ('finish', 'published-1', ())):
            for owner in range(1, 10):
                late_fault(f'hif{hif2}-late-{command}-owner{owner}', states[state],
                    command, args, owner, 0x3e902a7c, False)

    def denied(label, saved, command, args=(), mutation=None, read_only=False):
        pair.restore(saved)
        if mutation:
            field, offset, value = mutation
            pair.setword(field, offset, value)
        before = pair.snapshot()
        result = pair.tail(command, *args)
        assert (result == 0 if read_only else result != 0), (label, result)
        allowed = {"tail_reads", "tail_mutated"}
        for name, data in before.items():
            actual = bytes(pair.fields[name][2])
            if name == "tail_state" and not read_only:
                wanted = bytearray(data)
                struct.pack_into("<I", wanted, 8, 1)
                assert actual == wanted, (label, "retained-owner")
            elif name not in allowed:
                assert actual == data, (label, "unexpected-write", name)
        controls.append(label)

    expected = stores(0)
    for stage, selector in enumerate((0, 2, 15)):
        first, last = stage * 2, (stage + 1) * 2 if stage < 2 else 9
        operand = expected[first][2] if stage < 2 else 0
        for wrong in (1, 10, 16, 0xffffffff):
            denied(f"stage-{stage}-selector-{wrong}", phases[f"pre-{stage}"],
                   "begin", (wrong, operand, 1))
        denied(f"stage-{stage}-operand", phases[f"pre-{stage}"], "begin", (selector, operand ^ 1, 1))
        denied(f"stage-{stage}-finish-before-stores", phases[f"begun-{stage}"], "finish")
        denied(f"stage-{stage}-active-not-live", phases[f"begun-{stage}"],
               "stage_live", (stage,), read_only=True)
        denied(f"stage-{stage}-replay", phases[f"finished-{stage}"], "begin", (selector, operand, 1))
        for i in range(first, last):
            address, width, value = expected[i]
            original = struct.unpack_from("<I", phases[f"before-{i}"]["tail_cells"], i * 4)[0]
            denied(f"store-{i}-unpublished", phases[f"reserved-{i}"], "finish")
            denied(f"store-{i}-no-effect", phases[f"reserved-{i}"], "publish", (address, width, value))
            denied(f"store-{i}-readback", phases[f"written-{i}"], "publish", (address, width, value ^ 1))
            if exhaustive or i in (0, 3, 8):
                denied(f"store-{i}-wrong-address", phases[f"before-{i}"], "reserve",
                       (address + 4, width, value, original))
                denied(f"store-{i}-wrong-width", phases[f"before-{i}"], "reserve",
                       (address, 2, value, original))
                denied(f"store-{i}-wrong-value", phases[f"before-{i}"], "reserve",
                       (address, width, value ^ 1, original))
                denied(f"store-{i}-wrong-preimage", phases[f"before-{i}"], "reserve",
                       (address, width, value, original ^ 1))
                denied(f"store-{i}-reserve-twice", phases[f"reserved-{i}"], "reserve",
                       (address, width, value, original))
                denied(f"store-{i}-publish-twice", phases[f"published-{i}"], "publish",
                       (address, width, value))

    begun, written, finished = phases["begun-0"], phases["written-0"], phases["finished-2"]
    reserve = (*expected[0], 0xa5a50100)
    for epoch in (0, 2, 0xffffffff):
        denied(f"wrong-epoch-{epoch}", phases["fresh"], "begin", (0, BASE + 0xd4580, epoch))
    for field, offset, value in (("tail_tx", 8, 1), ("pcie_state", 8, 1),
                                 ("state", 8, 1), ("rx", 24, 0), ("packet", 16, 3071),
                                 ("count", 0, 0), ("ready", 0, 0)):
        denied(f"prior-{field}-{offset}", begun, "reserve", reserve, (field, offset, value))
        denied(f"live-{field}", finished, "live", mutation=(field, offset, value), read_only=True)
    for address in (0x3e90395c, 0x3e902a80, 0x3e904630, 0x3e902a9c, 0x3e902a90, 0x3e902a7c):
        denied(f"missing-prior-{address:x}", begun, "reserve", reserve,
               ("tail_read_failure", 0, address))
    denied("late-prefix-corruption", finished, "live", mutation=("tail_cells", 16, 0), read_only=True)

    if exhaustive:
        for offset in range(0, 256, 4):
            denied(f"dirty-initial-word-{offset}", phases["fresh"], "begin", (0, BASE + 0xd4580, 1),
                   ("tail_state", offset, 1))
        for field, start, size in (("tail_state", 0, 220), ("tail_plan", 0, 180),
                                   ("tail_tx", 0, 80), ("pcie_state", 0, 168)):
            for offset in range(start, size, 4):
                # Captured preimages and previous PCIe preimage are opaque history,
                # not a second authority for the geometry/finished-owner checks.
                if field == "pcie_state" and offset == 28:
                    continue
                saved = begun
                old = struct.unpack_from("<I", saved[field], offset)[0]
                denied(f"corrupt-{field}-{offset}", saved, "reserve", reserve,
                       (field, offset, old ^ 1))
        for i, (address, width, value) in enumerate(expected):
            stage = 0 if i < 2 else 1 if i < 4 else 2
            first = stage * 2
            pair.restore(phases[f"pre-{stage}"])
            pair.setword("tail_read_failure", 0, address)
            before = pair.snapshot()
            assert pair.tail("begin", (0, 2, 15)[stage],
                BASE + 0xd4580 if stage == 0 else BASE + 0xd4560 if stage == 1 else 0, 1) != 0
            owner = pair.values("tail_state")
            assert owner[:10] == (MAGIC, 1, 1, 1, stage, (1 << (stage + 1)) - 1,
                (1 << stage) - 1, first, first, (1 << i) - 1)
            assert owner[55:55 + i] == tuple(0xa5a50100 + n * 17 for n in range(i))
            assert owner[55 + i:] == (0,) * (9 - i)
            assert bytes(pair.fields["tail_cells"][2]) == before["tail_cells"]
            assert bytes(pair.fields["tail_events"][2]) == before["tail_events"]
            controls.append(f"preimage-read-failure-{i}")

    # A reader may expose a concurrent fault or mutation. Only its named effect
    # and the owner's fail-closed bit may differ; no device store is fabricated.
    for label, saved, command, args in (
        ("begin", phases["fresh"], "begin", (0, BASE + 0xd4580, 1)),
        ("reserve", begun, "reserve", reserve),
        ("publish", written, "publish", expected[0]),
        ("finish", phases["published-1"], "finish", ())):
        for mode in (1, 2, 3, 4):
            pair.restore(saved)
            pair.setword("tail_mutation", 0, mode)
            before = pair.snapshot()
            assert pair.tail(command, *args) != 0, (label, "reader-mutation", mode)
            assert pair.values("tail_mutated") == (1,)
            assert pair.values("tail_state")[2] == 1
            wanted = {name: bytearray(data) for name, data in before.items()}
            struct.pack_into("<I", wanted["tail_state"], 8, 1)
            if mode == 2:
                old = struct.unpack_from("<I", wanted["tail_state"], 32)[0]
                struct.pack_into("<I", wanted["tail_state"], 32, old + 1)
            if mode == 3:
                struct.pack_into("<I", wanted["tail_tx"], 8, 1)
            if mode == 4:
                old = struct.unpack_from("<I", wanted["pcie_state"], 28)[0]
                struct.pack_into("<I", wanted["pcie_state"], 28, old ^ 1)
            for name, data in wanted.items():
                if name not in ("tail_reads", "tail_mutated"):
                    assert bytes(pair.fields[name][2]) == data, (label, mode, "unexpected-write", name)
            controls.append(f"reader-mutation-{label}-{mode}")
    return {"passed": True, "native_compared": pair.native, "calls": pair.calls,
            "owner_bytes": 256, "plan_bytes": 180, "nominal": nominal,
            "controls": controls, "native_binding": False, "hardware": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--core-directory", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    assert args.name.replace("-", "").isalnum()
    dest = ROOT / ".local/npu-pcie-tail-owner" / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    names = ("cold-rx-pcie", "cold-txdone", "cold-rx-event", "cold-tx-buffer",
             "cold-packet", "cold-tx", "cold-pcie-tail")
    sources = [CORE / (name + ".c") for name in names]
    objects = [args.core_directory.resolve() / (name + ".o") for name in names]
    fixtures = [TESTS / name for name in
                ("cold-txdone-fixture.c", "cold-rx-pcie-fixture.c", "cold-pcie-tail-fixture.c")]
    ld = TESTS / "cold-txdone-probe.ld"
    run = pcie.done.tx.loader.run
    clang = shutil.which("clang")
    common = [clang, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I" + str(CORE), "-I" + str(HERE)]
    linker = ROOT / ".local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld"
    native = ["--target=riscv32", "-march=rv32imac_zicsr", "-mabi=ilp32", "-ffreestanding", "-fno-builtin"]
    obj = dest / "cold-pcie-tail.o"
    host, elf = dest / "host.so", dest / "owner.elf"
    inputs = sources + fixtures + objects + list(CORE.glob("*.h")) + [CORE / "Makefile",
        Path(__file__), ld, Path(pcie.__file__), Path(pcie.done.__file__), Path(pcie.done.tx.__file__),
        Path(pcie.done.tx.loader.__file__), TESTS / "test_barrier_protocol.py"]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    shutil.copyfile(objects[-1], obj)
    run(common + ["-O2", "-g", "-shared", "-fPIC", *sources, *fixtures, "-o", host], dest / "host-build.log")
    run(common + ["-O2", *native, "-nostdlib", "-fno-stack-protector", "--ld-path=" + str(linker),
        "-Wl,-T," + str(ld), *objects, *fixtures, "-o", elf], dest / "rv-build.log")
    result = exercise(Pair(host, elf, args.native), exhaustive=args.full or not args.native)
    assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    result["inputs"] = hashes
    result["normal_build_objects"] = {str(p.relative_to(ROOT)): hashes[str(p.relative_to(ROOT))]
                                      for p in objects}
    result["binaries"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (obj, host, elf)}
    (dest / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "native": args.native, "calls": result["calls"],
        "controls": len(result["controls"]), "result": str(dest / "result.json")}), flush=True)


if __name__ == "__main__":
    main()
