#!/usr/bin/env python3
"""Original INODE2/7 effects and interrupted prefixes; synthetic RAM, no admission."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".local/npu-quiescence/firmware/en7581_MT7996_npu_rv32.bin"
CODE, DATA, ICV = 0x84000000, 0x3e900000, 0x3e8bc470
ICV_BASE, ICV_BYTES, WINDOW_BYTES = 0x3e8bc000, 4104, 8192
STACK, END, PAYLOAD = 0x841e0000, 0x841ffff0, DATA + 0x7000
EXPECTED_CODE = "e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def recipe(selector):
    if selector == 2:
        return [(DATA + 0x46ec, 4, 1), (DATA + 0x46f0, 4, 1), (DATA + 0x46f8, 1, 3)] + [
            (ICV + i * 4, 4, 0) for i in range(1026)] + [(DATA + 0x46f7, 1, 0)]
    assert selector == 7
    return [(DATA + offset, size, value) for offset, size, value in
            ((0x46f5, 1, 0), (0x46f0, 4, 1), (0x46f9, 1, 3),
             (0x46f8, 1, 3), (0x46e1, 1, 1), (0x46e0, 1, 1))]


class Fixture:
    def __init__(self, code):
        self.code = code
        self.cpu = cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        cpu.mem_map(CODE, 0x200000)
        cpu.mem_write(CODE, code)
        cpu.mem_map(DATA, 0x10000)
        cpu.mem_map(ICV_BASE, WINDOW_BYTES)
        self.data = bytes((i * 31 + 41) % 251 + 1 for i in range(0x10000))
        self.window = bytes((i * 17 + 3) % 251 + 1 for i in range(WINDOW_BYTES))
        self.events, self.stop_at, self.stopped, self.sites = [], None, False, set()
        cpu.hook_add(UC_HOOK_CODE, self.printf, begin=0x840048f4, end=0x840048f4)
        cpu.hook_add(UC_HOOK_MEM_WRITE, self.write)

    def printf(self, cpu, pc, size, unused):
        cpu.reg_write(r.UC_RISCV_REG_A0, 0)
        cpu.reg_write(r.UC_RISCV_REG_PC, cpu.reg_read(r.UC_RISCV_REG_RA))

    def write(self, cpu, access, address, size, value, unused):
        if DATA <= address < DATA + 0x10000 or ICV_BASE <= address < ICV_BASE + WINDOW_BYTES:
            self.events.append((cpu.reg_read(r.UC_RISCV_REG_PC), address, size,
                                value & ((1 << (size * 8)) - 1)))

    def cut(self, cpu, pc, size, unused):
        if self.stop_at is not None and len(self.events) == self.stop_at:
            self.stopped = True
            cpu.emu_stop()

    def call(self, pc, args):
        cpu = self.cpu
        cpu.reg_write(r.UC_RISCV_REG_GP, DATA + 0x13a8)
        cpu.reg_write(r.UC_RISCV_REG_SP, STACK)
        cpu.reg_write(r.UC_RISCV_REG_RA, END)
        for i, value in enumerate(args):
            cpu.reg_write(getattr(r, "UC_RISCV_REG_A" + str(i)), value)
        cpu.emu_start(pc, END, count=200000, timeout=1000000)

    def run(self, selector, cut=None, padded=True):
        cpu = self.cpu
        data, window = bytearray(self.data), bytearray(self.window)
        # Pointer comes from a separately executed original static lookup, not
        # a dynamic allocator entry or a claim of physical backing ownership.
        struct.pack_into("<I", data, 0x2ac0, ICV)
        data[0x7000:0x7100] = b"\xa5" * 256
        frame = struct.pack("<3I", 0x10 | selector, 24, 0) + (bytes(12) if padded else b"")
        data[0x7000:0x7000 + len(frame)] = frame
        cpu.mem_write(DATA, bytes(data))
        cpu.mem_write(ICV_BASE, bytes(window))
        for i in range(12):
            cpu.reg_write(getattr(r, "UC_RISCV_REG_S" + str(i)), 0x51010000 + i * 0x101)
        self.events, self.stop_at, self.stopped = [], cut, False
        self.call(0x8400fc2c, [PAYLOAD])
        expected = recipe(selector)
        prefix = expected if cut is None else expected[:cut]
        assert [(a, n, v) for _, a, n, v in self.events] == prefix, (selector, cut, self.events[:4])
        for address, size, value in prefix:
            target, base = (data, DATA) if DATA <= address < DATA + 0x10000 else (window, ICV_BASE)
            target[address - base:address - base + size] = value.to_bytes(size, "little")
        assert bytes(cpu.mem_read(DATA, len(data))) == data, (selector, cut, "whole-DATA")
        assert bytes(cpu.mem_read(ICV_BASE, len(window))) == window, (selector, cut, "whole-ICV-neighbors")
        assert bytes(cpu.mem_read(CODE, len(self.code))) == self.code
        if cut is None:
            assert cpu.reg_read(r.UC_RISCV_REG_PC) == END and cpu.reg_read(r.UC_RISCV_REG_A0) == 1
            assert cpu.reg_read(r.UC_RISCV_REG_SP) == STACK
            assert [cpu.reg_read(getattr(r, "UC_RISCV_REG_S" + str(i))) for i in range(12)] == [
                0x51010000 + i * 0x101 for i in range(12)]
        else:
            assert self.stopped and cpu.reg_read(r.UC_RISCV_REG_PC) != END
        return {"selector": selector, "cut_before_effect": cut, "effects": len(prefix),
                "returned": cut is None, "whole_data_sha256": sha(data), "whole_icv_window_sha256": sha(window)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert not output.exists()
    output.parent.mkdir(parents=True, exist_ok=True)
    inputs = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in (SOURCE, Path(__file__))}
    code = SOURCE.read_bytes()
    assert sha(code) == EXPECTED_CODE
    fixture = Fixture(code)
    cpu = fixture.cpu
    cpu.mem_write(DATA, fixture.data)
    cpu.mem_write(ICV_BASE, fixture.window)
    fixture.call(0x84005200, [0x109])
    assert cpu.reg_read(r.UC_RISCV_REG_PC) == END and cpu.reg_read(r.UC_RISCV_REG_A0) == ICV
    assert not fixture.events and bytes(cpu.mem_read(DATA, 0x10000)) == fixture.data
    assert bytes(cpu.mem_read(ICV_BASE, WINDOW_BYTES)) == fixture.window
    assert bytes(cpu.mem_read(CODE, len(code))) == code
    nominal, controls = [], []
    for selector in (2, 7):
        row = fixture.run(selector)
        sites = sorted({pc for pc, *_ in fixture.events})
        for pc in sites:
            if pc not in fixture.sites:
                cpu.hook_add(UC_HOOK_CODE, fixture.cut, begin=pc, end=pc)
                fixture.sites.add(pc)
        row["store_sites"] = [hex(pc) for pc in sites]
        nominal.append(row)
        nominal.append(fixture.run(selector, padded=False))
        for cut in range(len(recipe(selector))):
            controls.append(fixture.run(selector, cut=cut))
    assert all(sha((ROOT / name).read_bytes()) == digest for name, digest in inputs.items())
    record = {"passed": True, "fixed_lookup": {"type": "0x109", "address": hex(ICV),
              "dynamic_allocation": False, "memory_writes": 0}, "icv_bytes": ICV_BYTES,
              "clear_words": 1026, "nominal": nominal, "controls": controls,
              "counts": {"nominal": len(nominal), "interrupted_prefixes": len(controls)},
              "inputs": inputs,
              "original_instructions": True, "only_stub": "printf0x840048f4",
              "native_candidate_admission": False, "physical_or_drain_proof": False,
              "limits": ["Synthetic patterned DATA/ICV RAM; pointer metadata is published by this fixture.",
                         "Cuts stop before an original store instruction; not a real concurrent fault or bus error.",
                         "Prior candidate owners/session/caller/locks and actual IRQ enabling are not exercised.",
                         "Early run flags and callback return do not establish hardware readiness or drains."]}
    output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"passed": True, "counts": record["counts"], "store_sites": [
        row.get("store_sites") for row in nominal if "store_sites" in row], "output": str(output)}), flush=True)


if __name__ == "__main__":
    main()
