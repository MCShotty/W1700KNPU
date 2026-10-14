#!/usr/bin/env python3
"""Original INODE plus exact eleven store sites; guards explicitly stubbed."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_CODE
from unicorn import riscv_const as r
from elftools.elf.elffile import ELFFile
import test_inode_original_prefixes as original
import test_npu_firmware_loader as loader
import npu_image as image

ROOT, HERE = original.ROOT, Path(__file__).resolve().parent
SITES = (0xe0c4, 0xe0ce, 0xe0d8, 0xe0e0, 0xe0e8, 0xe0f0, 0xe178, 0xe180, 0xe18a, 0xe196, 0xe1b4)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    assert args.name.replace("-", "").isalnum()
    dest = ROOT / ".local/npu-inode-store-abi" / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    elf = dest / "stores.elf"
    assembly = [HERE / "cold-inode-native-stores.S", HERE / "cold-inode-abi-stubs.S"]
    ld = HERE / "cold-inode-native-stores.ld"
    paths = [*assembly, ld, Path(__file__), Path(original.__file__), original.SOURCE,
             Path(loader.__file__), Path(loader.extract.__file__), Path(image.__file__)]
    inputs = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    linker = ROOT / ".local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld"
    loader.run([shutil.which("clang"), "--target=riscv32", "-march=rv32imac_zicsr", "-mabi=ilp32",
        "-nostdlib", *assembly, "--ld-path=" + str(linker), "-Wl,-T," + str(ld) + ",--no-relax",
        "-o", elf], dest / "build.log")
    code = original.SOURCE.read_bytes()
    assert sha(original.SOURCE) == image.CODE_SHA
    with elf.open("rb") as stream:
        binary = ELFFile(stream)
        symbols = {s.name: s["st_value"] for s in binary.get_section_by_name(".symtab").iter_symbols()}
        sections = [(s["sh_addr"], s.data()) for s in binary.iter_sections() if s["sh_flags"] & 2]
    patched = bytearray(code)
    for site in SITES:
        image.boundary(code[site:site + 4], original.CODE + site)
        patched[site:site + 4] = image.jal(original.CODE + site, symbols[f"npu_emulation_inode_{site:x}"])
        store = symbols[f"npu_emulation_inode_{site:x}_store"]
        assert next(data[store - address:store - address + 4] for address, data in sections
                    if address <= store < address + len(data)) == code[site:site + 4]
    rows = []
    for selector in (2, 7):
        expected = original.recipe(selector)
        indices = (0, 1, 2, 3, 17, 512, 1028, 1029) if selector == 2 else range(6)
        for failure in (None, *((i, action) for i in indices for action in ("reserve", "publish"))):
            for seed in (0x51010000, 0x90203040):
                for padded in (False, True):
                    fixture = original.Fixture(bytes(patched))
                    cpu = fixture.cpu
                    for address, data in sections:
                        cpu.mem_write(address, data)
                    data, window = bytearray(fixture.data), bytearray(fixture.window)
                    struct.pack_into("<I", data, 0x2ac0, original.ICV)
                    data[0x7000:0x7100] = b"\xa5" * 256
                    frame = struct.pack("<3I", 0x10 | selector, 24, 0) + (bytes(12) if padded else b"")
                    data[0x7000:0x7000 + len(frame)] = frame
                    cpu.mem_write(original.DATA, bytes(data))
                    cpu.mem_write(original.ICV_BASE, bytes(window))
                    saved = {getattr(r, "UC_RISCV_REG_" + name): (seed + i * 0x101) & 0xffffffff for i, name in
                        enumerate(("TP", *("S" + str(i) for i in range(12))))}
                    for reg, value in saved.items(): cpu.reg_write(reg, value)
                    calls, current = [], 0

                    def instruction(uc, pc, size, unused):
                        nonlocal current
                        action = "reserve" if pc == symbols["npu_emulation_inode_reserve"] else (
                            "publish" if pc == symbols["npu_emulation_inode_publish"] else None)
                        if action is None: return
                        address, width, value = expected[current]
                        actual = [uc.reg_read(getattr(r, "UC_RISCV_REG_A" + str(i))) for i in range(3)]
                        assert actual[:3 if action == "reserve" else 2] == (
                            [address, value, width] if action == "reserve" else [address, width])
                        calls.append((current, action))
                        ok = failure != (current, action)
                        if action == "publish" and ok: current += 1
                        resume = uc.reg_read(r.UC_RISCV_REG_RA)
                        for i, name in enumerate((*("T" + str(i) for i in range(7)), *("A" + str(i) for i in range(8)))):
                            uc.reg_write(getattr(r, "UC_RISCV_REG_" + name), 0xcc000000 + i)
                        uc.reg_write(r.UC_RISCV_REG_A0, int(ok))
                        uc.reg_write(r.UC_RISCV_REG_PC, resume)

                    cpu.hook_add(UC_HOOK_CODE, instruction)
                    fixture.call(0x8400fc2c, [original.PAYLOAD])
                    assert cpu.reg_read(r.UC_RISCV_REG_PC) == original.END
                    assert cpu.reg_read(r.UC_RISCV_REG_SP) == original.STACK
                    assert cpu.reg_read(r.UC_RISCV_REG_GP) == original.DATA + 0x13a8
                    assert all(cpu.reg_read(reg) == value for reg, value in saved.items()), (selector, failure, "saved")
                    count = len(expected) if failure is None else failure[0] + (failure[1] == "publish")
                    wanted = expected[:count]
                    assert [(a, w, v) for _, a, w, v in fixture.events] == wanted, (selector, failure)
                    for address, width, value in wanted:
                        target, base = (data, original.DATA) if original.DATA <= address < original.DATA + len(data) else (
                            window, original.ICV_BASE)
                        target[address - base:address - base + width] = value.to_bytes(width, "little")
                    assert bytes(cpu.mem_read(original.DATA, len(data))) == data
                    assert bytes(cpu.mem_read(original.ICV_BASE, len(window))) == window
                    assert bytes(cpu.mem_read(original.CODE, len(patched))) == patched
                    assert calls == ([(i, op) for i in range(len(expected)) for op in ("reserve", "publish")]
                        if failure is None else [(i, op) for i in range(failure[0]) for op in ("reserve", "publish")] +
                        [(failure[0], "reserve")] + ([(failure[0], "publish")] if failure[1] == "publish" else []))
                    rows.append({"selector": selector, "failure": failure, "seed": seed, "padded": padded,
                                 "effects": count, "guard_calls": len(calls), "saved_registers": True,
                                 "frame_restored": True, "outer_return": cpu.reg_read(r.UC_RISCV_REG_A0),
                                 "data_sha256": hashlib.sha256(data).hexdigest(),
                                 "icv_window_sha256": hashlib.sha256(window).hexdigest()})
    assert all(sha(ROOT / name) == digest for name, digest in inputs.items())
    record = {"passed": True, "cases": rows, "store_sites": [hex(original.CODE + p) for p in SITES],
              "exact_original_store_opcodes": True, "original_frame_bytes": 16,
              "inputs": inputs, "binary_sha256": sha(elf),
              "real_ownership_guards": False, "hardware": False,
              "limits": ["Actual original callback/helper/eleven store opcodes with explicit guard stubs and only printf skipped.",
                         "Original frame, callee-saved registers, byte/word effects and whole synthetic DATA/ICV-neighbor memory match.",
                         "No native owner/session/IRQ integration, physical backing/drains or actual client proof."]}
    (dest / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"passed": True, "cases": len(rows), "sites": len(SITES),
                      "outer_returns": sorted({row["outer_return"] for row in rows}), "output": str(dest / "result.json")}), flush=True)


if __name__ == "__main__":
    main()
