#!/usr/bin/env python3
"""Portable INODE state/whole-memory comparison; no native store admission."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
import test_cold_pcie_tail as tail
import test_inode_original_prefixes as original

ROOT, CORE, TESTS = tail.ROOT, tail.CORE, tail.TESTS
HERE = Path(__file__).resolve().parent
FIELDS = ("inode_state", "inode_plan", "inode_window", "inode_flags", "inode_events",
          "inode_effects", "inode_metadata", "inode_reads", "inode_read_failure",
          "inode_mutation", "inode_mutated")
DIAGNOSTICS = ("tail_reads", "tail_mutated", "inode_reads", "inode_mutated")


class Pair(tail.Pair):
    def __init__(self, host, elf, native):
        super().__init__(host, elf, native)
        symbols = {s.name: s for s in self.rv.elf.get_section_by_name(".symtab").iter_symbols()}
        for name in FIELDS:
            symbol = symbols["npu_test_" + name]
            size = symbol["st_size"]
            assert size and symbol["st_info"]["type"] == "STT_OBJECT"
            self.fields[name] = (symbol["st_value"], size,
                (ctypes.c_uint8 * size).in_dll(self.host, symbol.name))
        assert self.fields["inode_state"][1] == 4372 and self.fields["inode_plan"][1] == 188

    def inode(self, name, *values):
        return self.invoke("npu_test_inode_" + name, [ctypes.c_uint32(v) for v in values], values)


def assert_memory(pair, initial, expected, count):
    window, flags = bytearray(initial["inode_window"]), bytearray(initial["inode_flags"])
    for address, size, value in expected[:count]:
        target, base = (window, original.ICV_BASE) if address >= original.ICV and address < original.ICV + 4104 else (
            flags, 0x3e9046e0)
        target[address - base:address - base + size] = value.to_bytes(size, "little")
    assert bytes(pair.fields["inode_window"][2]) == window
    assert bytes(pair.fields["inode_flags"][2]) == flags
    assert pair.values("inode_effects") == (count,)
    events = pair.values("inode_events")
    assert list(zip(events[:count * 3:3], events[1:count * 3:3], events[2:count * 3:3])) == expected[:count]
    assert events[count * 3:] == (0,) * ((1036 - count) * 3)
    for name, data in initial.items():
        if name not in FIELDS and name not in DIAGNOSTICS:
            assert bytes(pair.fields[name][2]) == data, ("changed-prior", name)


def exercise(pair):
    expected = original.recipe(2) + original.recipe(7)
    assert len(expected) == 1036
    controls, nominal, phases = [], [], {}
    for hif2 in (0, 1):
        assert pair.tail("prepare", hif2) == 0
        prior_stores = tail.stores(hif2)
        for stage, selector in enumerate((0, 2, 15)):
            start, stop = stage * 2, stage * 2 + 2 if stage < 2 else 9
            assert pair.tail("begin", selector, prior_stores[start][2] if stage < 2 else 0, 1) == 0
            for i in range(start, stop):
                address, size, value = prior_stores[i]
                assert pair.tail("reserve", address, size, value, pair.values("tail_cells")[i]) == 0
                assert pair.tail("effect", i, value) == 0
                assert pair.tail("publish", address, size, value) == 0
            assert pair.tail("finish") == 0
        assert pair.inode("prepare", hif2) == 0
        for stage in (0, 1, 2, 0xffffffff):
            assert pair.inode("stage_live", stage) == 0
        fresh = pair.snapshot()
        snapshots = {"fresh": fresh}
        for stage, selector, limit in ((0, 2, 1030), (1, 7, 1036)):
            snapshots[f"pre-{stage}"] = pair.snapshot()
            assert pair.inode("begin", selector, 0, 1) == 0
            assert pair.values("inode_state")[:10] == (0x31444e49, 1, 0, 1, stage,
                (1 << (stage + 1)) - 1, (1 << stage) - 1, 1030 if stage else 0,
                1030 if stage else 0, limit)
            snapshots[f"begun-{stage}"] = pair.snapshot()
            assert pair.inode("stage_live", stage) == 0
            count = 1030 if stage else 0
            checkpoints = (1, 2, 3, 17, 512, 1029, 1030) if not stage else (1031, 1036)
            for target in checkpoints:
                while count < target:
                    batch = min(1 if pair.native else 16, target - count)
                    assert pair.inode("run", batch, 0) == 0
                    count += batch
                assert pair.values("inode_state")[7:9] == (count, count)
                assert_memory(pair, fresh, expected, count)
                snapshots[f"prefix-{count}"] = pair.snapshot()
            assert pair.inode("finish") == 0
            assert pair.values("inode_state")[3:9] == (
                0, stage, (1 << (stage + 1)) - 1, (1 << (stage + 1)) - 1, limit, limit)
            snapshots[f"finished-{stage}"] = pair.snapshot()
            assert pair.inode("stage_live", stage) == 1
            assert pair.inode("stage_live", stage ^ 1) == 0
            assert pair.inode("stage_live", 2) == 0
        assert pair.inode("live") == 1
        assert_memory(pair, fresh, expected, 1036)
        nominal.append({"hif2": hif2, "ordered_stores": 1036, "icv_bytes": 4104,
                        "window_sha256": hashlib.sha256(bytes(pair.fields["inode_window"][2])).hexdigest()})
        if hif2 == 0:
            phases = snapshots

    def denied(label, saved, command, args=(), mutation=None, readonly=False):
        pair.restore(saved)
        if mutation:
            pair.setword(*mutation)
        before = pair.snapshot()
        result = pair.inode(command, *args)
        assert (result == 0 if readonly else result != 0), (label, result)
        for name, data in before.items():
            wanted = bytearray(data)
            if name == "inode_state" and not readonly:
                struct.pack_into("<I", wanted, 8, 1)
            if name not in DIAGNOSTICS:
                assert bytes(pair.fields[name][2]) == wanted, (label, "unexpected-write", name)
        controls.append(label)

    fresh, begun, finished = phases["fresh"], phases["begun-0"], phases["finished-1"]
    for stage in (0, 1):
        saved = phases[f"finished-{stage}"]
        for offset, value in ((4, 2), (8, 1), (12, 1), (16, stage ^ 1), (28, 0), (32, 0)):
            denied(f"stage-{stage}-owner-{offset}", saved, "stage_live", (stage,),
                   ("inode_state", offset, value), readonly=True)
    for selector in (0, 1, 4, 7, 15, 0xffffffff):
        denied(f"initial-selector-{selector}", fresh, "begin", (selector, 0, 1))
    for value, epoch in ((1, 1), (0xffffffff, 1), (0, 0), (0, 2)):
        denied(f"value-{value}-epoch-{epoch}", fresh, "begin", (2, value, epoch))
    denied("finish-without-stores", begun, "finish")
    denied("replay-selector2", phases["finished-0"], "begin", (2, 0, 1))
    denied("replay-selector7", finished, "begin", (7, 0, 1))
    first = (*expected[0], 0xa5a5a5a5)
    for field, offset, value in (("inode_metadata", 0, 0x108), ("inode_metadata", 4, original.ICV + 4),
                                 ("inode_metadata", 8, original.ICV + 4), ("inode_plan", 180, original.ICV + 4),
                                 ("inode_plan", 184, 4100), ("tail_state", 8, 1), ("tail_tx", 8, 1),
                                 ("pcie_state", 8, 1), ("state", 8, 1), ("ready", 0, 0)):
        denied(f"bad-{field}-{offset}", begun, "reserve", first, (field, offset, value))
    for prefix in (0, 1, 2, 3, 17, 512, 1029, 1030, 1031):
        saved = begun if not prefix else phases["begun-1"] if prefix == 1030 else phases[f"prefix-{prefix}"]
        address, size, value = expected[prefix]
        target, base = (saved["inode_window"], original.ICV_BASE) if original.ICV <= address < original.ICV + 4104 else (
            saved["inode_flags"], 0x3e9046e0)
        before = int.from_bytes(target[address - base:address - base + size], "little")
        for label, args in (("address", (address + 4, size, value, before)),
                            ("width", (address, 4 if size == 1 else 1, value, before)),
                            ("value", (address, size, value ^ 1, before)),
                            ("preimage", (address, size, value, before ^ 1))):
            denied(f"prefix-{prefix}-{label}", saved, "reserve", args)
        pair.restore(saved)
        assert pair.inode("run", 1, 1) == 3
        reserved = pair.snapshot()
        denied(f"prefix-{prefix}-possible-retained", reserved, "finish")
        if before != value:
            denied(f"prefix-{prefix}-no-store", reserved, "publish", expected[prefix])
        pair.restore(saved)
        assert pair.inode("run", 1, 2) == 5
        written = pair.snapshot()
        denied(f"prefix-{prefix}-readback", written, "publish", (address, size, value ^ 1))
        if not prefix:
            phases["reserved"] = reserved
            phases["written"] = written
    for index in (0, 512, 1025):
        denied(f"live-corrupt-icv-{index}", finished, "live",
               mutation=("inode_window", original.ICV - original.ICV_BASE + index * 4, 1), readonly=True)
    for offset in (0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 220, 224, 228, 4368):
        denied(f"dirty-initial-{offset}", fresh, "begin", (2, 0, 1), ("inode_state", offset, 1))
    for address in (0x8401cfb8, 0x8401cfbc, 0x3e902ac0):
        denied(f"missing-definition-{address:x}", fresh, "begin", (2, 0, 1), ("inode_read_failure", 0, address))
    for captured in (3, 515, 1028, 1029):
        address = original.ICV + (captured - 3) * 4 if captured < 1029 else 0x3e9046f7
        pair.restore(fresh)
        pair.setword("inode_read_failure", 0, address)
        initial = pair.snapshot()
        assert pair.inode("begin", 2, 0, 1) != 0
        wanted = bytearray(4372)
        struct.pack_into("<10I", wanted, 0, 0x31444e49, 1, 1, 1, 0, 1, 0, 0, 0, captured)
        wanted[40:228] = fresh["inode_plan"]
        for i in range(captured):
            struct.pack_into("<I", wanted, 228 + i * 4,
                (0xa5a5a5a5, 0xa5a5a5a5, 0xa5)[i] if i < 3 else 0x96969696)
        assert bytes(pair.fields["inode_state"][2]) == wanted
        for name, data in initial.items():
            if name not in DIAGNOSTICS and name != "inode_state":
                assert bytes(pair.fields[name][2]) == data, ("partial-capture", captured, name)
        controls.append(f"partial-preimage-{captured}")
    for label, saved, command, args in (("begin", fresh, "begin", (2, 0, 1)),
        ("reserve", begun, "reserve", first), ("publish", phases["written"], "publish", expected[0]),
        ("finish", phases["prefix-1030"], "finish", ())):
        for mode in range(1, 9):
            pair.restore(saved)
            pair.setword("inode_mutation", 0, mode)
            wanted = {n: bytearray(v) for n, v in pair.snapshot().items()}
            assert pair.inode(command, *args) != 0, (label, mode)
            assert pair.values("inode_mutated") == (1,)
            struct.pack_into("<I", wanted["inode_state"], 8, 1)
            field, offset = ("inode_state", 32) if mode == 2 else ("tail_state", 8 if mode == 3 else 220)
            if mode == 2:
                struct.pack_into("<I", wanted[field], offset, struct.unpack_from("<I", wanted[field], offset)[0] + 1)
            elif mode == 3:
                struct.pack_into("<I", wanted[field], offset, 1)
            elif mode == 4:
                struct.pack_into("<I", wanted[field], offset, struct.unpack_from("<I", wanted[field], offset)[0] ^ 1)
            elif mode in (5, 6, 7, 8):
                struct.pack_into("<I", wanted[{5: "tail_tx", 6: "pcie_state", 7: "state", 8: "rx"}[mode]], 8, 1)
            for name, data in wanted.items():
                if name not in DIAGNOSTICS:
                    assert bytes(pair.fields[name][2]) == data, (label, mode, name)
            controls.append(f"reader-{label}-{mode}")
    return {"passed": True, "calls": pair.calls, "controls": controls, "nominal": nominal,
            "native_compared": pair.native, "owner_bytes": 4372, "plan_bytes": 188,
            "original_store_binding": False, "hardware": False,
            "limits": ["Original store sites/authenticated caller are not bound.",
                       "Identical preimage/value flags need native site execution proof; readback alone cannot distinguish a write.",
                       "Compiler frame sizes are not a full native call-chain or physical stack bound."]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--core-directory", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    args = parser.parse_args()
    assert args.name.replace("-", "").isalnum()
    dest = ROOT / ".local/npu-inode-owner" / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    names = ("cold-rx-pcie", "cold-txdone", "cold-rx-event", "cold-tx-buffer",
             "cold-packet", "cold-tx", "cold-pcie-tail", "cold-inode")
    sources = [CORE / (n + ".c") for n in names]
    objects = [args.core_directory.resolve() / (n + ".o") for n in names]
    fixtures = [TESTS / name for name in
                ("cold-txdone-fixture.c", "cold-rx-pcie-fixture.c",
                 "cold-pcie-tail-fixture.c", "cold-inode-fixture.c")]
    ld = TESTS / "cold-txdone-probe.ld"
    paths = sources + objects + fixtures + list(CORE.glob("*.h")) + [CORE / "Makefile",
        Path(__file__), Path(original.__file__), Path(tail.__file__),
        Path(tail.pcie.__file__), Path(tail.pcie.done.__file__), Path(tail.pcie.done.tx.__file__),
        Path(tail.pcie.done.tx.loader.__file__), TESTS / "test_barrier_protocol.py", ld]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    command = [shutil.which("clang"), "-std=c11", "-Wall", "-Wextra", "-Werror",
               "-I" + str(CORE), "-I" + str(TESTS)]
    flags = ["--target=riscv32", "-march=rv32imac_zicsr", "-mabi=ilp32", "-ffreestanding", "-fno-builtin", "-fno-stack-protector"]
    obj, host, elf = dest / "cold-inode.o", dest / "host.so", dest / "owner.elf"
    run = tail.pcie.done.tx.loader.run
    shutil.copyfile(objects[-1], obj)
    stack_obj = dest / "stack.o"
    run(command + ["-Os", *flags, "-fstack-usage", "-c", CORE / "cold-inode.c", "-o", stack_obj],
        dest / "stack-build.log")
    allocated = []
    for path in (obj, stack_obj):
        with path.open("rb") as stream:
            binary = ELFFile(stream)
            allocated.append([(s.name, s["sh_type"], s["sh_flags"], s["sh_size"], s.data())
                              for s in binary.iter_sections()
                              if s["sh_flags"] & 2 or s["sh_type"] in ("SHT_REL", "SHT_RELA")])
    assert allocated[0] == allocated[1], "stack probe differs from normal allocated/relocation sections"
    run(command + ["-O2", "-g", "-shared", "-fPIC", *sources, *fixtures, "-o", host], dest / "host-build.log")
    linker = ROOT / ".local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld"
    run(command + ["-O2", *flags, "-nostdlib", "--ld-path=" + str(linker), "-Wl,-T," + str(ld),
        *objects, *fixtures, "-o", elf], dest / "rv-build.log")
    result = exercise(Pair(host, elf, args.native))
    assert all(hashlib.sha256((ROOT / n).read_bytes()).hexdigest() == h for n, h in hashes.items())
    result["inputs"] = hashes
    result["binaries"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (obj, stack_obj, host, elf)}
    result["normal_build_objects"] = {str(p.relative_to(ROOT)): hashes[str(p.relative_to(ROOT))]
                                      for p in objects}
    result["stack_usage"] = (dest / "stack.su").read_text()
    result["stack_probe_matches_normal_allocated_and_relocation_sections"] = True
    result["native_instruction_budget_per_invocation"] = 500000000
    result["native_wall_microseconds_per_invocation"] = 30000000
    result["nominal_effects_per_invocation"] = 1 if args.native else 16
    (dest / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "calls": result["calls"], "controls": len(result["controls"]),
                      "native": args.native, "result": str(dest / "result.json")}), flush=True)


if __name__ == "__main__":
    main()
