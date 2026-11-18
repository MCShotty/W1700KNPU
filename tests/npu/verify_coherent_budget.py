#!/usr/bin/env python3
"""Check an offline cold-probe coherent-pool ceiling for the staged stack."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from verify_checked_packet_owner import (
    FILES, HEADER, PROVIDER, ROOT, captures, check, digest, function,
    linked_module_sources, ordered, patch_into, require,
)
from verify_npu_coherent_window import verify_dtb

CHECKPOINTS = ROOT / "research/checkpoints"
STACK = CHECKPOINTS / "2026-11-18-npu-coherent-window"
PACKET = CHECKPOINTS / "2026-11-18-npu-packet-owner"
BUILD = ROOT / ".build/merged-openwrt"
PAGE_SHIFT = 12


def order_pages(size, page_size):
    require(size > 0 and page_size > 0 and not page_size & (page_size - 1),
            "invalid coherent allocation or page size")
    return 1 << (((size + page_size - 1) // page_size) - 1).bit_length()


def first_fit(bitmap, capacity, block):
    """Model Linux bitmap_find_free_region, with capacity in pages."""
    require(capacity > 0 and block > 0 and not block & (block - 1),
            "bad bitmap geometry")
    mask = (1 << block) - 1
    for start in range(0, capacity - block + 1, block):
        region = mask << start
        if not bitmap & region:
            return start, bitmap | region
    raise ValueError("coherent pool exhausted")


def ceiling(groups, pool_size, page_size):
    """Use the no-free, initially empty, power-of-two pool invariant."""
    require(pool_size >= page_size > 0 and not pool_size & (pool_size - 1)
            and not page_size & (page_size - 1),
            "cold pool and page size must be powers of two")
    breakdown = {
        label: {
            "requests": len(sizes),
            "requested_bytes": sum(sizes),
            "reserved_bytes": sum(order_pages(size, page_size) * page_size for size in sizes),
        }
        for label, sizes in groups.items()
    }
    used = sum(row["reserved_bytes"] for row in breakdown.values())
    require(used <= pool_size, "cold allocation ceiling exceeds coherent pool")
    return dict(groups=breakdown, reserved_bytes=used, headroom_bytes=pool_size - used)


def constant(source, name):
    match = re.search(r"^#define\s+" + re.escape(name) + r"\s+(0x[0-9a-fA-F]+|[0-9]+)[uUlL]*[ \t]*$",
                      source, re.M)
    require(match is not None, "changed constant: " + name)
    return int(match[1], 0)


def linked_ring_widths(production):
    tool, = BUILD.glob("staging_dir/toolchain-*/bin/aarch64-openwrt-linux-musl-objdump")
    module, = (p for p in production["artifacts"] if p.endswith("/mt76.ko"))
    result = subprocess.run([tool, "-d", "--disassemble=mt76_dma_alloc_queue", ROOT / module],
                            check=True, capture_output=True, text=True, timeout=25).stdout
    widths = sorted({int(n, 16) for n in re.findall(r"\bmov\s+w22, #0x([0-9a-f]+)\b", result)})
    require(widths == [8, 16, 24, 208] and re.search(r"\bmul\s+w1, w22, w1\b", result),
            "linked descriptor geometry differs")
    return widths, production["artifacts"][module]


def allocator_sources(kernel):
    files = {
        "kernel/dma/coherent.c": {
            "__dma_alloc_from_coherent": (
                "order=get_order(size);", "bitmap_find_free_region(mem->bitmap,mem->size,order);",
                "if(unlikely(pageno<0))gotoerr;", "returnNULL;",
            ),
            "dma_alloc_from_dev_coherent": (
                "if(!mem)return0;", "*ret=__dma_alloc_from_coherent(dev,mem,size,dma_handle);", "return1;",
            ),
        },
        "kernel/dma/mapping.c": {
            "dma_alloc_attrs": (
                "if(dma_alloc_from_dev_coherent(dev,size,dma_handle,&cpu_addr)){", "returncpu_addr;}",
                "if(dma_alloc_direct(dev,ops))",
            ),
        },
        "include/linux/bitmap.h": {
            "bitmap_find_free_region": (
                "for(pos=0;(end=pos+BIT(order))<=bits;pos=end)",
                "if(!bitmap_allocate_region(bitmap,pos,order))returnpos;",
            ),
        },
        "include/asm-generic/getorder.h": {
            "get_order": ("ilog2((size)-1)-PAGE_SHIFT+1;", "size--;size>>=PAGE_SHIFT;", "returnfls64(size);"),
        },
    }
    result = {}
    for name, shapes in files.items():
        path = kernel / name
        source = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
        for symbol, args in shapes.items():
            require(ordered(function(source, symbol), *args), "kernel allocator shape drift: " + symbol)
        result[name] = digest(path)
    return result


def budget_inputs(provider, header, radio, producer):
    mh = radio["mt7996/mt7996.h"]
    d = function(radio["dma.c"], "mt76_dma_alloc_queue")
    require(ordered(d, "sizeof(structmt76_wed_rro_desc)", "sizeof(structairoha_npu_tx_dma_desc)",
                    "sizeof(structairoha_npu_rx_dma_desc)", "sizeof(structmt76_desc)",
                    "mt76_npu_alloc_queue_mem(dev,q,size)"), "descriptor route changed")
    a = function(provider, "airoha_npu_wlan_alloc_queue_mem")
    require(ordered(a, "if(rx_event){", "airoha_npu_wlan_alloc_rx_event_session(",
                    "life->queue_mem_count>=ARRAY_SIZE(life->queue_mem)", "kvzalloc(entry_bytes,",
                    "if(!rx_event){mem.desc=dma_alloc_coherent(", "life->queue_mem[life->queue_mem_count++]="),
            "ring cap, CPU entries, or borrowed event allocation changed")
    # The pinned primary TX allocation is followed by at most two PHY registrations.
    register = function(radio["mt7996/init.c"], "mt7996_register_device")
    require(ordered(register, "mt7996_register_phy(dev,MT_BAND1)", "mt7996_register_phy(dev,MT_BAND2)",
                    "mt7996_npu_hw_init(dev)"), "radio registration edges changed")
    tx = function(radio["mt7996/init.c"], "mt7996_register_phy")
    require("MT7996_NPU_TX_RING_SIZE/2:MT7996_TX_RING_SIZE" in tx and
            tx.count("mt7996_init_tx_queues(") == 1, "additional PHY TX geometry changed")
    connac = (ROOT / ".local/merge-nonoc-20260923/mt76-merged/mt76_connac_mac.c").read_text()
    require("mt76_connac_mac.c" in producer["mt76"] and
            function(connac, "mt76_connac_init_tx_queues").count("mt76_init_tx_queue(") == 1,
            "per-AC queue alias assumption changed")
    pci = function(radio["mt7996/pci.c"], "mt7996_pci_probe")
    require(pci.count("ret=mdev->npu_dma.hold?0:mt7996_mmio_wed_init(") == 2,
            "checked NPU can use WED DMA")
    npu = function(radio["npu.c"], "mt76_npu_init")
    require("dev->dma_dev=npu->dev;" in npu, "radio DMA device changed")

    require(provider.count("dma_alloc_coherent(") == 5, "coherent allocation sites changed")
    rro_path = function(provider, "airoha_npu_wlan_rro_alloc_session")
    require(ordered(rro_path, "extent.bytes!=bytes", "dma_alloc_coherent(dma_dev,extent.bytes,"),
            "RRO allocation geometry no longer enforced")
    tx_path = function(radio["mt7996/npu.c"], "mt7996_npu_tx_buffer_sizes")
    require(ordered(tx_path, "i+=3", "MT7996_NPU_TX_RING_SIZE:MT7996_NPU_RX_RING_SIZE/2",
                    "bytes[i]=256*size;", "bytes[i+1]=bytes[i];", "bytes[i+2]=256*1024;"),
            "TX descriptor buffer geometry changed")
    require(constant(mh, "MT7996_NPU_TXD_SIZE") == 3, "TX group count changed")
    standard_counts = [constant(mh, name) for name in (
        "MT7996_TX_RING_SIZE", "MT7996_RX_RING_SIZE", "MT7996_RX_MCU_RING_SIZE",
        "MT7996_RX_MCU_RING_SIZE_WA", "MT7996_TX_MCU_RING_SIZE", "MT7996_TX_FWDL_RING_SIZE",
    )]
    standard_counts.extend(constant(header, f"NPU_RX{ring}_DESC_NUM") for ring in (0, 1))
    return (
        constant(header, "NPU_NUM_CORES"),
        constant(provider, "AIROHA_NPU_MBOX_SIZE"),
        constant(provider, "NPU_WLAN_MAX_QUEUE_MEM"),
        constant(mh, "MT7996_NPU_TX_RING_SIZE"),
        constant(mh, "MT7996_NPU_RX_RING_SIZE"),
        max(standard_counts),
    )


def verify(producer, expected_sha256, dtb):
    require(__debug__ and digest(producer) == expected_sha256, "unverified producer")
    prod = linked_module_sources(ROOT, producer)
    known = json.loads((STACK / "EVIDENCE.json").read_bytes())
    packet = json.loads((PACKET / "EVIDENCE.json").read_bytes())
    require(known["producer_sha256"] == prod["receipt_sha256"] and
            known["source_lock_sha256"] == prod["source_lock_sha256"], "producer no longer matches stack")
    layout = verify_dtb(dtb)
    require(known["standalone_dtb"] == json.loads(json.dumps(layout)), "different staged DTB")
    kernel_tree, = (BUILD / "build_dir").glob("target-*/linux-airoha*/linux-6.18.52")
    config = kernel_tree / ".config"
    require(digest(config) == known["kernel_config_sha256"] and
            f"CONFIG_PAGE_SHIFT={PAGE_SHIFT}" in config.read_text().splitlines(), "kernel page size drift")
    allocator = allocator_sources(kernel_tree)
    page = 1 << PAGE_SHIFT
    paths = (STACK / "airoha-checked-coherent-window.patch", PACKET / FILES["mt76"][0])
    require(all(digest(p) == known["patch_sha256"][p.name] for p in paths), "stack patch drift")
    with TemporaryDirectory(prefix="w1700k-coherent-budget-") as directory:
        d = Path(directory)
        kt = patch_into(d / "kernel", "kernel", prod, (PROVIDER, HEADER), paths[0])
        rt = patch_into(d / "mt76", "mt76", prod, FILES["mt76"][1], paths[1])
        require(all(digest(d / "kernel" / p) == known["postimages"][p] for p in kt) and
                all(digest(d / "mt76" / p) == packet["postimages"]["mt76"][p] for p in rt),
                "staged source drift")
        check(captures(dict(kernel=kt, mt76=rt)))
        cores, mailbox, slots, tx_n, rx_n, generic_max = budget_inputs(kt[PROVIDER], kt[HEADER], rt, prod)
        radio_header = rt["mt7996/mt7996.h"]

    widths, mt76_sha = linked_ring_widths(prod)
    tx_count = 3
    require(slots >= tx_count and tx_n <= generic_max and rx_n <= generic_max, "bad ring bounds")
    # Charge every ledger slot, including the single borrowed RX event slot.
    common = {
        "mailboxes": [mailbox] * cores,
        "tx_dma_rings": [tx_n * widths[-1]] * tx_count,
        "other_dma_rings": [generic_max * widths[-2]] * (slots - tx_count),
        "tx_descriptor_buffers": [256 * (rx_n // 2)] * 2 + [256 * 1024] * 2 + [256 * tx_n] * 2,
    }
    rro_header = "firmware/npu/rro-lifetime.h"
    require(rro_header in prod["inputs"], "RRO geometry is not a producer input")
    rro = (ROOT / rro_header).read_text()
    expected_block = constant(rro, "NPU_RRO_BLOCK_BYTES")
    expected_session = constant(rro, "NPU_RRO_SESSION_BYTES")
    elements = constant(radio_header, "MT7996_RRO_ADDR_ELEM_LEN")
    msdu = constant(radio_header, "MT7996_RRO_MSDU_PG_CR_CNT")
    window = constant(radio_header, "MT7996_RRO_WINDOW_MAX_LEN")
    sessions = constant(radio_header, "MT7996_RRO_MAX_SESSION")
    ba = constant(radio_header, "MT7996_RRO_BA_BITMAP_LEN")
    require(constant(rro, "NPU_RRO_BLOCKS") == elements and window * 8 == expected_session and
            window * (sessions // elements) * 8 == expected_block and
            constant(radio_header, "MT7996_RRO_MSDU_PG_SIZE_PER_CR") == expected_block and
            sessions * 128 // ba == expected_block, "radio and provider RRO map differ")
    emi = 4 * constant(radio_header, "MT7996_MAX_RRO_RRS_RING")
    cases = {
        "v3": {**common, "rro_blocks": [expected_block] * (elements + msdu + ba),
               "rro_session": [expected_session]},
        "v3_1": {**common, "rro_blocks": [expected_block] * (elements + msdu),
                 "rro_emi": [emi] * 2, "rro_session": [expected_session]},
    }
    require(all(sum(len(group) for key, group in groups.items() if key.startswith("rro_")) ==
                constant(rro, "NPU_RRO_MAX_EXTENTS") for groups in cases.values()), "RRO count drift")
    pool = layout["pool_size"]
    results = {name: ceiling(groups, pool, page) for name, groups in cases.items()}
    for name, groups in cases.items():
        sizes = [n for group in groups.values() for n in group]
        for sequence in (sizes, sorted(sizes), sorted(sizes, reverse=True)):
            bitmap = 0
            for size in sequence:
                _, bitmap = first_fit(bitmap, pool // page, order_pages(size, page))
            require(bitmap.bit_count() * page == results[name]["reserved_bytes"], "bitmap budget mismatch")
        try:
            ceiling(groups, pool // 2, page)
        except ValueError as exc:
            require(str(exc) == "cold allocation ceiling exceeds coherent pool", "wrong capacity refusal")
        else:
            raise ValueError("accepted deliberately undersized pool")
    return dict(schema=1, producer_sha256=expected_sha256, pool_bytes=pool, page_bytes=page,
                staged_dtb_sha256=layout["dtb_sha256"], patch_sha256=known["patch_sha256"],
                allocator_source_sha256=allocator,
                linked_mt76_sha256=mt76_sha, linked_descriptor_sizes=widths, ring_slots=slots,
                modeled_max_tx_rings=tx_count, max_other_ring_descriptors=generic_max,
                checked_fresh_no_free_only=True, profiles=results, half_pool_rejected=True,
                new_modules_compiled=False, board_contact=False, physical_retirement_proven=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer", type=Path, required=True)
    parser.add_argument("--producer-sha256", required=True)
    parser.add_argument("--dtb", type=Path, required=True)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.producer, args.producer_sha256, args.dtb)
        if args.check:
            require(json.loads(args.check.read_bytes()) == result, "budget receipt differs")
        else:
            print(json.dumps(result, indent=2, sort_keys=True))
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
