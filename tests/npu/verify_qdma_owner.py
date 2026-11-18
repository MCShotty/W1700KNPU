#!/usr/bin/env python3
"""Check the staged Ethernet QDMA owner without running a device or kernel."""
import argparse
import hashlib
import json
import os
import re
import resource
import shlex
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from elftools.elf.elffile import ELFFile

import verify_ppe_table_owner as ppe
from verify_consumer_queue_owner import digest, function, ordered, require

ROOT = ppe.ROOT
HERE = Path(__file__).resolve().parent
CHECKPOINT = ROOT / "research/checkpoints/2026-11-18-npu-qdma-owner"
PATCH = CHECKPOINT / "airoha-qdma-owner.patch"
FILES = {"airoha_eth.c", "airoha_eth.h"}
EXTRACT = (
    "airoha_qdma_free_unexposed", "airoha_qdma_release_owner", "airoha_alloc_eth",
    "airoha_qdma_alloc_table", "airoha_qdma_alloc_entries", "airoha_qdma_publish_base",
    "airoha_qdma_stop_napi", "airoha_qdma_park", "airoha_hw_stop_napi", "airoha_qdma_cleanup",
    "airoha_qdma_admit", "airoha_qdma_detach_tx_dev", "airoha_qdma_start",
    "airoha_qdma_host_idle", "airoha_qdma_stop",
)
DEBUGFS_CMD = "725d854a96fa38324ce3edb5a1332dd29bbac9a53e666ac7af3d0db95f6c27dc"
DEBUGFS_SOURCE = "f1e2c6a66fb34f105b5b21f8a3b0f133fcb83965cb1d0aac00f2e4df2b41e40f"
LINKER = "ece7e3272f489f2fc72135d3214aff88353b3f811c125d8de7ac12c48871a67e"


def apply_stack(kernel, work):
    ppe.apply_patch(kernel, work)
    parent = json.loads((ppe.CHECKPOINT / "EVIDENCE.json").read_bytes())
    require(all(digest(work / ppe.ETH / f) == sha for f, sha in parent["patched"].items()),
            "PPE postimages differ before QDMA patch")
    stat = ppe.run(["git", "apply", "--numstat", "-z", PATCH], cwd=work).stdout
    paths = [part.split("\t", 2)[-1] for part in stat.split("\0") if part]
    require(sorted(paths) == sorted(str(ppe.ETH / f) for f in FILES), "QDMA patch scope differs")
    result = ppe.run(["patch", "--batch", "--forward", "--no-backup-if-mismatch",
                      "--fuzz=0", "-p1", "-i", PATCH], cwd=work)
    require(not re.search(r"\b(offset|fuzz|FAILED)\b", result.stdout + result.stderr),
            "QDMA patch needed an offset or did not apply")
    return {name: parent["patched"][name] for name in sorted(FILES)}


def inspect(src, regs):
    def body(name):
        return function(src, name)

    rules = {
        "probe_owns_before_reset": ordered(body("airoha_probe"), "eth=airoha_alloc_eth(",
                                          "if(IS_ERR(eth))return", "airoha_ppe_prepare_dma(",
                                          "dma_set_mask_and_coherent(", "airoha_hw_init("),
        "probe_unwinds_with_owner": ordered(body("airoha_hw_init"), "airoha_qdma_init(",
                                            "airoha_ppe_init(", "error:for(", "airoha_qdma_cleanup(")
        and ordered(body("airoha_probe"), "error_napi_stop:airoha_hw_stop_napi(eth);",
                    "unregister_netdev(", "airoha_hw_cleanup(eth);", "free_netdev("),
        "remove_parks_before_unregister": ordered(body("airoha_remove"), "airoha_hw_stop_napi(eth);",
                                                  "unregister_netdev(", "airoha_hw_cleanup(eth);"),
        "publish_before_queue_access": all(
            ordered(body(name), "airoha_qdma_alloc_table(", "airoha_qdma_publish_base(qdma," + reg)
            for name, reg in (("airoha_qdma_init_rx_queue", "REG_RX_RING_BASE(qid)"),
                              ("airoha_qdma_init_tx_queue", "REG_TX_RING_BASE(qid)"),
                              ("airoha_qdma_tx_irq_init", "REG_TX_IRQ_BASE(id)"),
                              ("airoha_qdma_init_hfwd_queues", "REG_FWD_DSCP_BASE"))),
        "published_port_pages_owned": ordered(body("airoha_qdma_init_rx_queue"),
                                               "page_pool_create(", "netif_napi_add(",
                                               "airoha_qdma_publish_base(", "airoha_qdma_fill_rx_queue(")
        and ordered(body("airoha_qdma_cleanup"), "airoha_qdma_park(qdma);",
                    "if(qdma->dma_exposed)page_pool_disable_direct_recycling(",
                    "netif_napi_del(", "if(qdma->dma_exposed)continue;",
                    "airoha_qdma_cleanup_rx_queue(", "page_pool_destroy(",
                    "if(qdma->dma_exposed)return;", "airoha_qdma_cleanup_tx_queue("),
        "hardware_forwarding_has_own_base": ordered(body("airoha_qdma_init_hfwd_queues"),
                                                   "of_reserved_mem_lookup(", "dma_addr=rmem->base;",
                                                   "airoha_qdma_publish_base(qdma,REG_FWD_BUF_BASE,",
                                                   "airoha_qdma_publish_base(qdma,REG_FWD_DSCP_BASE,",
                                                   "LMGR_INIT_START")
        and src.count("dmam_alloc_coherent(") == 1
        and not re.search(r"\bairoha_qdma_wr\(\s*qdma,\s*REG_(?:[RT]X_(?:RING|IRQ)_BASE|FWD_.*BASE)", src),
        "bounded_host_idle_before_forced_cleanup": ordered(body("airoha_qdma_stop"),
                                                           "if(--qdma->users)return;",
                                                           "if(airoha_qdma_admit(qdma))return;",
                                                           "AIROHA_QDMA_HOST_EN",
                                                           "airoha_qdma_host_idle(qdma,status)",
                                                           "airoha_qdma_park(qdma);return;",
                                                           "airoha_qdma_cleanup_tx_queue("),
        "no_zero_register_as_idle": all(re.search(r"^#define " + mask + r"\s+BIT\(" + str(bit) + r"\)", regs, re.M)
                                        for mask, bit in (("GLOBAL_CFG_TX_DMA_EN_MASK", 0),
                                                          ("GLOBAL_CFG_RX_DMA_EN_MASK", 2),
                                                          ("GLOBAL_CFG_TX_DMA_BUSY_MASK", 1),
                                                          ("GLOBAL_CFG_RX_DMA_BUSY_MASK", 3),
                                                          ("GLOBAL_CFG_TX_WB_DONE_MASK", 6)))
        and "GLOBAL_CFG_TX_WB_DONE_MASK" in body("airoha_qdma_hw_init"),
        "close_keeps_packet_data_and_disarms_bql": ordered(body("airoha_dev_stop"),
                                                          "tx_quiescing,true", "netif_tx_disable(",
                                                          "airoha_qdma_detach_tx_dev(",
                                                          "netdev_tx_reset_subqueue(",
                                                          "airoha_qdma_stop(")
        and not re.search(r"free_|kfree|dma_unmap", body("airoha_qdma_detach_tx_dev"))
        and ordered(body("airoha_qdma_tx_napi_poll"), "if(!e->dma_addr)gotounlock;",
                    "dma_unmap_single(", "if(e->tx_dev){", "skb_get_tx_queue(e->tx_dev,skb)"),
        "parked_engine_cannot_restart_or_accept_tx": src.count("airoha_qdma_start(") == 3
        and ordered(body("airoha_dev_open"), "airoha_qdma_admit(", "phylink_of_phy_connect(", "airoha_qdma_start(")
        and ordered(body("airoha_dev_set_qdma"), "airoha_qdma_admit(qdma);if(err)returnerr;",
                    "airoha_qdma_start(", "rcu_assign_pointer(")
        and ordered(body("airoha_dev_xmit"), "tx_quiescing)||airoha_qdma_admit(qdma)", "dma_map_single("),
        "migration_joins_old_tx_before_bql_reset": ordered(body("airoha_dev_set_qdma"),
                                                          "tx_quiescing,true", "netif_tx_disable(",
                                                          "rcu_assign_pointer(", "synchronize_rcu(",
                                                          "airoha_qdma_detach_tx_dev(",
                                                          "netdev_tx_reset_subqueue(",
                                                          "tx_quiescing,false", "netif_tx_wake_all_queues(")
        and "READ_ONCE(dev->tx_quiescing)" in body("airoha_qdma_wake_netdev_txqs"),
        "exclusive_skb_header_at_map": ordered(body("airoha_dev_xmit"), "returnNETDEV_TX_BUSY;",
                                             "skb_share_check(", "dma_map_single(",
                                             "e->tx_dev=e->skb?netdev:NULL;"),
    }
    require(all(rules.values()), "failed source contracts: " + ", ".join(n for n in rules if not rules[n]))
    return sorted(rules)


def extract(src):
    boundary = "static void airoha_qdma_free_unexposed"
    prefix, = re.findall(r"^#define AIROHA_QDMA_HOST_EN\b.*?^" + boundary, src, re.M | re.S)
    bodies = []
    for name in EXTRACT:
        start = re.search(r"^[^\n]*\b" + name + r"\([^;{}]*?\)\n\{", src, re.M)
        require(start, "function missing: " + name)
        bodies.append(src[start.start():src.index("\n}", start.end()) + 2])
    bits = ("\n#define GLOBAL_CFG_TX_DMA_EN_MASK (1U << 0)\n"
            "#define GLOBAL_CFG_RX_DMA_EN_MASK (1U << 2)\n"
            "#define GLOBAL_CFG_TX_DMA_BUSY_MASK (1U << 1)\n"
            "#define GLOBAL_CFG_RX_DMA_BUSY_MASK (1U << 3)\n")
    return bits + prefix.removesuffix(boundary) + "\n\n".join(bodies) + "\n"


def verify_native(work, code):
    header = work / "qdma-owner-under-test.inc"
    executable = work / "qdma-owner-harness"

    def run(candidate, succeeds):
        header.write_text(candidate, encoding="ascii")
        ppe.run(["cc", "-O2", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-Wno-sign-compare",
                 "-I", work, HERE / "qdma-owner-harness.c", "-o", executable], cwd=work)
        result = subprocess.run([executable], cwd=work, timeout=10, capture_output=True, text=True,
                                env=dict(os.environ, LC_ALL="C"))
        if succeeds:
            require(result.returncode == 0 and result.stdout.strip() == "11 QDMA owner cases passed",
                    f"native cases exited {result.returncode}: {result.stderr}")
        else:
            require(result.returncode == -6 and "Assertion" in result.stderr,
                    f"negative control exited {result.returncode}: {result.stderr}")

    run(code, True)
    controls = (
        ("release-published-engine", "if (eth->qdma[i].dma_exposed)", "if (false && eth->qdma[i].dma_exposed)"),
        ("bypass-owner-guard", "if (w1700k_qdma_owner) {", "if (false && w1700k_qdma_owner) {"),
        ("publish-before-mark", "qdma->dma_exposed = true;", "qdma->dma_exposed = false;"),
        ("allow-unknown-readback", "(status & GLOBAL_CFG_TX_WB_DONE_MASK));", "true);"),
        ("forced-cleanup-after-timeout", "airoha_qdma_park(qdma);\n\t\t\treturn;", "airoha_qdma_park(qdma);"),
        ("release-published-rx-pages", "if (qdma->dma_exposed)\n\t\t\tcontinue;",
         "if (false && qdma->dma_exposed)\n\t\t\tcontinue;"),
        ("stale-bql-owner", "skb->dev = NULL;\n\t\t\te->tx_dev = NULL;", "skb->dev = NULL;"),
    )
    for name, old, new in controls:
        require(code.count(old) == 1, "ambiguous mutation: " + name)
        run(code.replace(old, new), False)
    return dict(cases=11, controls=[n for n, _, _ in controls],
                extracted_sha256=hashlib.sha256(code.encode("ascii")).hexdigest())


def cross(kernel, work):
    result = ppe.cross(kernel, work)
    gcc, = ppe.BUILD.glob("staging_dir/toolchain-*/bin/aarch64-openwrt-linux-musl-gcc")
    ld = gcc.with_name("aarch64-openwrt-linux-musl-ld")
    require(digest(ld) == LINKER, "unexpected linker")
    driver = kernel / ppe.ETH
    src = driver / "airoha_ppe_debugfs.c"
    require(digest(src) == DEBUGFS_SOURCE, "debugfs source drift")
    copied = work / ppe.ETH / src.name
    shutil.copyfile(src, copied)
    cmd = (driver / ".airoha_ppe_debugfs.o.cmd").read_bytes().splitlines(keepends=True)[0]
    require(hashlib.sha256(cmd).hexdigest() == DEBUGFS_CMD, "debugfs flags drift")
    argv = shlex.split(cmd.decode().split(":=", 1)[1])
    obj = work / ppe.ETH / "airoha_ppe_debugfs.o"
    ppe.run(["nice", "-n", "19", "prlimit", "--as=402653184", "--", gcc, *argv[3:-4],
             "-iquote", driver, "-ffile-prefix-map=" + str(work) + "=.ppe-table-owner-check",
             "-c", "-o", obj, copied], cwd=kernel)
    path = work / ppe.ETH
    linked = path / "airoha-eth.aggregate.o"
    ppe.run([ld, "-EL", "-maarch64elf", "--fatal-warnings", "-z", "noexecstack",
             "--no-warn-rwx-segments", "-r", "-o", linked,
             path / "airoha_eth.o", path / "airoha_ppe.o", obj], cwd=work)
    with linked.open("rb") as file:
        elf = ELFFile(file)
        require(elf["e_machine"] == "EM_AARCH64" and elf["e_type"] == "ET_REL", "bad aggregate architecture")
        table = elf.get_section_by_name(".symtab")
        names = ("airoha_ppe_prepare_dma", "airoha_ppe_debugfs_init", "airoha_dev_xmit",
                 "airoha_qdma_release_owner", "airoha_remove", "airoha_probe")
        for name in names:
            symbol, = table.get_symbol_by_name(name)
            require(symbol["st_shndx"] != "SHN_UNDEF", "unresolved Ethernet symbol: " + name)
    result["debugfs"] = dict(command_sha256=DEBUGFS_CMD, sha256=digest(obj))
    result["relocatable_aggregate"] = dict(sha256=digest(linked), linker_sha256=LINKER, resolved=list(names))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cross", action="store_true", help="compile and aggregate three AArch64 objects")
    parser.add_argument("--check", action="store_true", help="compare against the saved receipt")
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    kernel, = ppe.BUILD.glob("build_dir/target-*/linux-airoha*/linux-6.18.52")
    require(digest(kernel / ".config") == ppe.CONFIG, "not the pinned W1700K config")
    with TemporaryDirectory(prefix="w1700k-qdma-owner-") as name:
        work = Path(name)
        original = apply_stack(kernel, work)
        eth = (work / ppe.ETH / "airoha_eth.c").read_text()
        regs = (kernel / ppe.ETH / "airoha_regs.h").read_text()
        result = dict(schema="w1700k-qdma-owner-v1", original=original, patch_sha256=digest(PATCH),
                      patched={f: digest(work / ppe.ETH / f) for f in sorted(FILES)},
                      baseline_config_sha256=ppe.CONFIG, source_contracts=inspect(eth, regs),
                      native=verify_native(work, extract(eth)), full_module_built=False,
                      fit_built=False, board_run=False, physical_retirement_proven=False)
        if args.cross:
            result["cross_compile"] = cross(kernel, work)
    if args.check:
        expected = json.loads((CHECKPOINT / "EVIDENCE.json").read_bytes())
        if not args.cross:
            expected.pop("cross_compile")
        require(result == expected, "result differs from saved QDMA owner receipt")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
