#!/usr/bin/env python3
"""Original callback plus nine store trampolines, guards explicitly stubbed."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r
from elftools.elf.elffile import ELFFile
import test_cold_pcie_tail as owner
import npu_image as image

HERE, ROOT = owner.HERE, owner.ROOT
SOURCE = ROOT / ".local/npu-quiescence/firmware/en7581_MT7996_npu_rv32.bin"
CODE, DATA, BAR, SP, END = 0x84000000, 0x3e900000, owner.BASE, 0x841e0000, 0x841ffff0
SITES = {0xb9ae: 6, 0xb9c0: 6, 0xb9d2: 6, 0xb9ea: 6, 0xba00: 4,
         0xba0c: 4, 0xba18: 4, 0xba24: 4, 0xba30: 4}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    assert args.name.replace("-", "").isalnum()
    dest = ROOT / ".local/npu-pcie-tail-store-abi" / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    elf = dest / "stores.elf"
    assembly = [HERE / "cold-pcie-tail-native-stores.S", HERE / "cold-pcie-tail-abi-stubs.S"]
    ld = HERE / "cold-pcie-tail-native-stores.ld"
    paths = [*assembly, ld, Path(__file__), Path(owner.__file__), Path(image.__file__),
             Path(owner.pcie.done.tx.loader.__file__), SOURCE]
    inputs = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    linker = ROOT / ".local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld"
    owner.pcie.done.tx.loader.run([shutil.which("clang"), "--target=riscv32", "-march=rv32imac_zicsr",
        "-mabi=ilp32", "-nostdlib", *assembly, "--ld-path=" + str(linker),
        "-Wl,-T," + str(ld) + ",--no-relax", "-o", elf], dest / "build.log")
    original = SOURCE.read_bytes()
    assert sha(SOURCE) == image.CODE_SHA
    with elf.open("rb") as stream:
        binary = ELFFile(stream)
        symbols = {s.name: s["st_value"] for s in binary.get_section_by_name(".symtab").iter_symbols()}
        sections = [(s["sh_addr"], s.data()) for s in binary.iter_sections() if s["sh_flags"] & 2]
    patched = bytearray(original)
    for site, width in SITES.items():
        image.boundary(original[site:site + width], CODE + site)
        patch = image.jal(CODE + site, symbols[f"npu_emulation_pcie_tail_{site:x}"])
        patched[site:site + width] = patch + (b"\x01\x00" if width == 6 else b"")
        store = symbols[f"npu_emulation_pcie_tail_{site:x}_store"]
        emitted = next(data[store - address:store - address + (4 if site in (0xba0c, 0xba24) else 2)]
                       for address, data in sections if address <= store < address + len(data))
        assert emitted == original[site:site + len(emitted)], ("original-store-bytes", hex(site))
    cases = []
    selectors = {0: range(0, 2), 2: range(2, 4), 15: range(4, 9)}
    for hif2 in (0, 1):
        expected = owner.stores(hif2)
        for selector, indices in selectors.items():
            for failed in (None, *((i, action) for i in indices for action in ("reserve", "publish"))):
                cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
                cpu.mem_map(CODE, 0x200000)
                cpu.mem_write(CODE, bytes(patched))
                for address, data in sections:
                    cpu.mem_write(address, data)
                cpu.mem_map(DATA, 0x10000)
                cpu.mem_map(BAR, 0x100000)
                before_data = bytearray(b"\xa5" * 0x10000)
                before_bar = bytearray(b"\x96" * 0x100000)
                for offset, value in zip((0x395c, 0x2a80, 0x4630, 0x2a9c, 0x2a90),
                                        (0xd45a0, 0xd45b0, 0xd45c0, 0xa040, 0xd4590)):
                    struct.pack_into("<I", before_data, offset, BAR + value)
                struct.pack_into("<H", before_data, 0x2a7c, 512)
                operand = expected[indices.start][2] if selector != 15 else 0
                struct.pack_into("<3I", before_data, 0x7000, 0x10 | selector, 0, operand)
                cpu.mem_write(DATA, bytes(before_data))
                cpu.mem_write(BAR, bytes(before_bar))
                saved = {getattr(r, "UC_RISCV_REG_" + name): 0x51000000 + i * 0x101 for i, name in
                         enumerate(("GP", "TP", *("S" + str(i) for i in range(12))))}
                saved[r.UC_RISCV_REG_GP] = DATA + 0x13a8
                for reg, value in saved.items():
                    cpu.reg_write(reg, value)
                cpu.reg_write(r.UC_RISCV_REG_SP, SP)
                cpu.reg_write(r.UC_RISCV_REG_RA, END)
                cpu.reg_write(r.UC_RISCV_REG_A0, DATA + 0x7000)
                events, calls = [], []
                current = indices.start

                def instruction(uc, pc, size, unused):
                    nonlocal current
                    if pc == 0x840048f4:
                        uc.reg_write(r.UC_RISCV_REG_A0, 0)
                        uc.reg_write(r.UC_RISCV_REG_PC, uc.reg_read(r.UC_RISCV_REG_RA))
                        return
                    action = "reserve" if pc == symbols["npu_emulation_pcie_tail_reserve"] else (
                        "publish" if pc == symbols["npu_emulation_pcie_tail_publish"] else None)
                    if action is None:
                        return
                    address, width, value = expected[current]
                    actual = [uc.reg_read(getattr(r, "UC_RISCV_REG_A" + str(i))) for i in range(3)]
                    assert actual[:3 if action == "reserve" else 2] == (
                        [address, value, width] if action == "reserve" else [address, width])
                    calls.append((current, action))
                    ok = failed != (current, action)
                    if action == "publish" and ok:
                        current += 1
                    resume = uc.reg_read(r.UC_RISCV_REG_RA)
                    for i, name in enumerate((*("T" + str(i) for i in range(7)), *("A" + str(i) for i in range(8)))):
                        uc.reg_write(getattr(r, "UC_RISCV_REG_" + name), 0xcc000000 + i)
                    uc.reg_write(r.UC_RISCV_REG_A0, int(ok))
                    uc.reg_write(r.UC_RISCV_REG_PC, resume)

                def write(uc, access, address, width, value, unused):
                    if DATA <= address < DATA + 0x10000 or BAR <= address < BAR + 0x100000:
                        events.append((address, width, value & ((1 << (width * 8)) - 1)))

                cpu.hook_add(UC_HOOK_CODE, instruction)
                cpu.hook_add(UC_HOOK_MEM_WRITE, write)
                cpu.emu_start(0x8400fdc4, END, count=100000, timeout=1000000)
                assert cpu.reg_read(r.UC_RISCV_REG_PC) == END and cpu.reg_read(r.UC_RISCV_REG_SP) == SP
                assert all(cpu.reg_read(reg) == value for reg, value in saved.items()), (selector, failed, "callee-saved")
                end = indices.stop if failed is None else failed[0] + (failed[1] == "publish")
                wanted = expected[indices.start:end]
                assert events == wanted, (selector, failed, events, wanted)
                for address, width, value in wanted:
                    target, base = (before_data, DATA) if DATA <= address < DATA + 0x10000 else (before_bar, BAR)
                    struct.pack_into("<I", target, address - base, value)
                assert bytes(cpu.mem_read(DATA, len(before_data))) == before_data
                assert bytes(cpu.mem_read(BAR, len(before_bar))) == before_bar
                assert bytes(cpu.mem_read(CODE, len(patched))) == patched
                cases.append({"hif2": hif2, "selector": selector, "failed_guard": failed,
                              "calls": calls, "effects": events, "callee_saved": True,
                              "frame_restored": True, "outer_callback_return": cpu.reg_read(r.UC_RISCV_REG_A0)})
    assert all(sha(ROOT / name) == digest for name, digest in inputs.items())
    record = {"passed": True, "cases": cases, "store_sites": {hex(CODE + k): v for k, v in SITES.items()},
              "exact_original_store_opcodes": True, "inputs": inputs,
              "binary_sha256": sha(elf), "native_ownership_guards": False, "hardware": False,
              "limits": ["All ownership guards are explicit test stubs; original callback and original store opcodes execute.",
                         "Restored frames and relocated displaced instructions are verified for all nine sites.",
                         "Outer original callback can return1 after inner failure; real outer-owner acceptance must gate it."]}
    (dest / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"passed": True, "cases": len(cases), "sites": len(SITES), "result": str(dest / "result.json")}), flush=True)


if __name__ == "__main__":
    main()
