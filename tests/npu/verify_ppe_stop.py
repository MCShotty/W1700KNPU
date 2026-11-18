#!/usr/bin/env python3
"""Relate PPE mailbox completion and Ethernet stop to their actual code."""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

from verify_consumer_queue_owner import ROOT, digest, function, ordered, require

REPLAY = ROOT / ".local/npu-rv32-fresh-20261118/plan.json"
PAIR = ROOT / ".local/npu-build-scratch/native-c2/native-memory-hook-pair-q9/pair"
PRISTINE = ROOT / ".local/npu-quiescence/firmware"
HISTORICAL = ROOT / "research/checkpoints/2026-09-05-npu-quiescence"
BUILD = ROOT / ".build/merged-openwrt"
BASE = 0x84000000
DATA_BASE = 0x3E900000
ISR = (0x84003CD6, 0x84003E46)
REGISTER = (0x84003F00, 0x84003FB8)
DISPATCH = (0x840060A8, 0x84006170)
STOP = {
    0x84005EAE: (0x84005EBE, {0x84008C94}),
    0x84008C94: (0x84008F6E, {0x84007C08, 0x840075D6}),
    0x84007C08: (0x84007E6C, set()),
    0x840075D6: (0x8400762C, set()),
}
CONDITIONAL = {"beq", "bne", "bge", "bgeu", "blt", "bltu", "c.beqz", "c.bnez"}


@dataclass(frozen=True)
class Instruction:
    pc: int
    width: int
    op: str
    args: str = ""


def dump(argv):
    return subprocess.run(argv, check=True, capture_output=True, text=True, timeout=30).stdout


def instructions(text):
    pattern = r"^\s*([0-9a-f]+):[ \t]+([0-9a-f]{8}|[0-9a-f]{4})[ \t]+(\S+)(?:[ \t]+([^\r\n]*))?$"
    result = {}
    for match in re.finditer(pattern, text, re.M):
        pc, encoding, op, args = match.groups()
        pc = int(pc, 16)
        require(pc not in result, "duplicate instruction position")
        args = (args or "").split("# ", 1)[0].split("//", 1)[0].split("<", 1)[0].strip()
        result[pc] = Instruction(pc, len(encoding) // 2, op, args)
    return result


def target(args):
    field = args.rsplit(",", 1)[-1].strip()
    require(re.fullmatch(r"(?:0x)?[0-9a-f]+", field), "non-constant branch target")
    return int(field, 16)


def no_polling_loop(rows, start, permitted_calls):
    """Check a bounded decoded RV32 function, not MMIO or timing behavior."""
    visiting, visited, calls, returns = set(), set(), set(), set()

    def visit(pc):
        require(pc in rows, f"control flow escapes at {pc:#x}")
        require(pc not in visiting, f"loop at {pc:#x}")
        if pc in visited:
            return
        visiting.add(pc)
        row = rows[pc]
        fallthrough = pc + row.width
        if (row.op, row.args) in {("c.jr", "ra"), ("jalr", "zero,0(ra)"), ("ret", "")}:
            returns.add(pc)
            edges = ()
        elif row.op in CONDITIONAL:
            edges = (fallthrough, target(row.args))
        elif row.op == "c.j" or (row.op == "jal" and row.args.startswith("zero,")):
            edges = (target(row.args),)
        elif row.op == "c.jal" or (row.op == "jal" and row.args.startswith("ra,")):
            callee = target(row.args)
            require(callee in permitted_calls, f"uninspected call to {callee:#x}")
            calls.add(callee)
            edges = (fallthrough,)
        else:
            require(row.op not in {"jal", "jalr", "c.jalr", "c.jr", "wfi", "ecall", "ebreak",
                                   "c.ebreak", "mret", "sret", "uret", "dret", "unimp"}
                    and not row.op.startswith("."), f"unresolved instruction at {pc:#x}")
            edges = (fallthrough,)
        for successor in edges:
            visit(successor)
        visiting.remove(pc)
        visited.add(pc)

    visit(start)
    require(returns and calls == permitted_calls, "missing return or expected direct call")
    return dict(reachable_instructions=len(visited), calls=[hex(n) for n in sorted(calls)],
                returns=[hex(n) for n in sorted(returns)])


def rv32(path, limits):
    lo, hi = limits
    result = instructions(dump(["riscv64-linux-gnu-objdump", "-D", "-z", "-b", "binary",
                                "-m", "riscv:rv32", "-M", "no-aliases", f"--adjust-vma={BASE:#x}",
                                f"--start-address={lo:#x}", f"--stop-address={hi:#x}", path]))
    cursor = lo
    for row in result.values():
        require(row.pc == cursor, "incomplete disassembly")
        cursor += row.width
    require(cursor == hi, "disassembly does not cover pinned code range")
    return result


def instruction(rows, pc, op, args):
    actual = rows[pc]
    require(actual.op == op and actual.args.replace(" ", "") == args.replace(" ", ""),
            f"unexpected instruction at {pc:#x}: {actual.op} {actual.args}")


def verify_guest():
    pristine_code = PRISTINE / "en7581_MT7996_npu_rv32.bin"
    pristine_data = PRISTINE / "en7581_MT7996_npu_data.bin"
    code, data, manifest = (PAIR / n for n in ("CODE.bin", "DATA.bin", "manifest.json"))
    plan_sha = digest(REPLAY)
    require(plan_sha == "8739afe217d75e010d91a5d9fbde0170ecb096a6879ccc26069ab60406fdaec0",
            "not the investigated replay plan")
    plan = json.loads(REPLAY.read_bytes())
    pins = {p: digest(p) for p in (pristine_code, pristine_data, code, data, manifest)}
    require(all(plan["inputs"][str(p.relative_to(ROOT))] == sha for p, sha in pins.items()),
            "replay input hash changed")
    meta = json.loads(manifest.read_bytes())
    require(meta["code"]["base"] == BASE and meta["data"]["base"] == DATA_BASE and
            meta["original"] == dict(code_sha256=pins[pristine_code], data_sha256=pins[pristine_data]) and
            meta["code"]["sha256"] == pins[code] and meta["data"]["sha256"] == pins[data],
            "firmware layout or provenance differs")
    export_rel = "ghidra-current-rv32-decoded/en7581_MT7996_npu_rv32.bin.txt"
    export = HISTORICAL / export_rel
    historical = json.loads((HISTORICAL / "evidence-verification.json").read_bytes())
    export_sha = digest(export)
    require(export_sha == historical["ghidra"]["ghidra-current-rv32-decoded"]["sha256"],
            "Ghidra export changed")
    labels = {int(n, 16) for n in re.findall(r"^FUNCTION .+ @ ram:([0-9a-f]{8})$", export.read_text(), re.M)}
    require(set(STOP) | {REGISTER[0], ISR[0], DISPATCH[0]} <= labels, "missing Ghidra anchors")

    old_bytes, new_bytes = pristine_code.read_bytes(), code.read_bytes()
    pairs = [ISR, DISPATCH, *((start, end) for start, (end, _) in STOP.items())]
    spans = {}
    for lo, hi in pairs:
        before, after = old_bytes[lo - BASE:hi - BASE], new_bytes[lo - BASE:hi - BASE]
        require(len(after) == hi - lo and before == after, f"replay modified inspected code at {lo:#x}")
        spans[hex(lo)] = dict(end=hex(hi), sha256=hashlib.sha256(after).hexdigest())

    s = slice(0x12C, 0x140)
    data_old, data_new = pristine_data.read_bytes(), data.read_bytes()
    require(data_old[s] == data_new[s], "replay modified initial PPE table")
    ppe_table = struct.unpack("<5I", data_new[s])
    require(ppe_table == (0, 0x84005EBE, 0x84005EAE, 0x84005F28, 0x84005DF2),
            "different PPE handler table")
    dispatch = rv32(code, DISPATCH)
    for pc, op, args in (
        (0x840060C2, "c.li", "a5,1"), (0x840060C8, "c.lw", "a2,4(s1)"),
        (0x840060D4, "auipc", "a5,0xba8fa"), (0x840060D8, "addi", "a5,a5,72"),
        (0x840060DC, "c.slli", "a2,0x2"), (0x840060DE, "c.add", "a2,a5"),
        (0x840060E0, "c.lw", "a5,16(a2)"), (0x840060E6, "c.jalr", "a5"),
    ):
        instruction(dispatch, pc, op, args)

    lo, hi = (n - BASE for n in REGISTER)
    require([i + BASE for i in range(lo, hi) if old_bytes[i] != new_bytes[i]] ==
            list(range(0x84003F2E, 0x84003F32)), "different replay registration edit")
    setup = rv32(code, REGISTER)
    instruction(setup, 0x84003F2E, "jal", "zero,0x84044f70")
    instruction(setup, 0x84003FA0, "auipc", "a5,0x2")
    instruction(setup, 0x84003FA4, "addi", "a5,a5,264")
    instruction(setup, 0x84003FA8, "sw", "a5,-1640(gp)")
    hook = rv32(code, (0x84044F70, 0x84044F8C))
    instruction(hook, 0x84044F80, "lui", "ra,0x84004")
    instruction(hook, 0x84044F84, "addi", "ra,ra,-206")
    instruction(hook, 0x84044F88, "jal", "zero,0x84003254")

    cfg = {}
    for start, (end, allowed) in STOP.items():
        rows = rv32(code, (start, end))
        cfg[hex(start)] = dict(end=hex(end), **no_polling_loop(rows, start, allowed))
    handler = rv32(code, (ppe_table[2], STOP[ppe_table[2]][0]))
    instruction(handler, 0x84005EB2, "jal", "ra,0x84008c94")
    instruction(handler, 0x84005EB8, "c.li", "a0,1")
    instruction(handler, 0x84005EBC, "c.jr", "ra")
    return dict(inputs={str(p.relative_to(ROOT)): sha for p, sha in pins.items()},
                replay_plan_sha256=plan_sha, ghidra_export_sha256=export_sha,
                operation=[5, 1, 2], initial_deinit_slot="0x3e900134", deinit_handler=hex(ppe_table[2]),
                checked_cfg=cfg, unchanged_spans=spans, reply_constant=1, registration_hook_resume="0x84003f32",
                executed_on_board=False)


def verify_host():
    directory, = (BUILD / "build_dir").glob("target-*/linux-airoha*/linux-6.18.52/drivers/net/ethernet/airoha")
    objdump, = BUILD.glob("staging_dir/toolchain-*/bin/aarch64-openwrt-linux-musl-objdump")
    module = directory / "airoha-eth.ko"
    expected = "dc9e5cdcd738811160725ba049cc44e24f674d5b59e08be1b772332dd551c12c"
    require(digest(module) == expected, "different prepared Ethernet module")

    ppe = dump([objdump, "-dr", "--disassemble=airoha_ppe_deinit", module])
    rows = instructions(ppe)
    instruction(rows, 0xC368, "blr", "x1")
    instruction(rows, 0xC36C, "mov", "x0,x21")
    require(re.search(r"c370: R_AARCH64_CALL26\s+airoha_npu_put\b", ppe), "PPE reference path differs")
    qdma = dump([objdump, "-dr", "--disassemble=airoha_qdma_stop.part.0", module])
    rows = instructions(qdma)
    for pc, op, args in (
        (0x1854, "mov", "w21, #0xa"), (0x187C, "b.lt", "18f4"),
        (0x18B4, "tst", "w1, w21"), (0x18B8, "b.ne", "1878"),
        (0x1908, "b", "18bc"), (0x18D4, "bl", "15c4"),
    ):
        instruction(rows, pc, op, args)
    cleanup = dump([objdump, "-dr", "--disassemble=airoha_qdma_cleanup_tx_queue", module])
    require(re.search(r"1904: R_AARCH64_CALL26\s+_dev_warn\b", qdma) and
            re.search(r"1688: R_AARCH64_CALL26\s+dma_unmap_page_attrs\b", cleanup),
            "QDMA timeout or cleanup path differs")
    source = directory / "airoha_ppe.c"
    release = function(source.read_text(), "airoha_ppe_deinit")
    require(ordered(release, "rcu_replace_pointer(", "synchronize_rcu();", "npu->ops.ppe_deinit(npu);",
                    "airoha_npu_put(npu);", "rhashtable_destroy("), "PPE source does not match release ordering")
    tx_stop = function((directory / "airoha_eth.c").read_text(), "airoha_qdma_stop")
    require(ordered(tx_stop, "airoha_qdma_clear(", "read_poll_timeout(", "dev_warn(",
                    "airoha_qdma_cleanup_tx_queue("), "QDMA source does not match timeout ordering")
    npu = ROOT / ".local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c"
    provider_sha = digest(npu)
    require(provider_sha == "7162cec0d0483d5f2228aed5fc794b389fd68b8451b325b0c4b25d04e67c8544",
            "different locked provider")
    provider_stop = function(npu.read_text(), "airoha_npu_ppe_deinit")
    require(ordered(provider_stop, "ppe_data->func_type=NPU_OP_SET;",
                    "ppe_data->func_id=PPE_FUNC_SET_WAIT_HWNAT_DEINIT;",
                    "err=airoha_npu_send_msg(npu,NPU_FUNC_PPE,ppe_data,sizeof(*ppe_data));", "returnerr;"),
            "provider operation or return path changed")
    return dict(prepared_ethernet_sha256=expected, ppe_source_sha256=digest(source),
                eth_source_sha256=digest(directory / "airoha_eth.c"), ppe_result_discarded=True,
                locked_npu_provider_sha256=provider_sha, qdma_timeout_reaches_tx_cleanup=True, qdma_busy_mask="0xa",
                same_as_newly_linked_candidate_proven=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    try:
        require(__debug__, "optimized Python cannot verify inputs")
        result = dict(schema=1, firmware=verify_guest(), host=verify_host(),
                      physical_ppe_tunnel_drain_proven=False, physical_qdma_retirement_proven=False)
        if args.check:
            require(json.loads(args.check.read_bytes()) == result, "PPE stop evidence changed")
        else:
            print(json.dumps(result, indent=2, sort_keys=True))
    except (KeyError, OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"PPE stop: {error}\n")


if __name__ == "__main__":
    main()
