#!/usr/bin/env python3
"""Verify the staged W1700K coherent pool in a pinned DTB or its FIT."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from verify_merged_image import prop, run, select_fit_configuration

BOARD = "gemtek,w1700k-ubi"
NPU = "/soc/npu@1e900000"
RESERVED = "/reserved-memory"
REGION_NAMES = ("binary", "pkt", "tx-pkt", "tx-bufid", "ba", "dma")
DRAM_START = 0x80000000
DRAM_END = 0xC0000000
POOL_SIZE = 16 << 20


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def listing(path, node, flag):
    return run(["fdtget", flag, path, node]).decode("ascii").splitlines()


def raw(path, node, name):
    return bytes(int(x, 16) for x in prop(path, node, name, "bx").split())


def strings(path, node, name):
    entries = raw(path, node, name).decode("ascii").split("\0")
    require(len(entries) > 1 and not entries[-1] and all(entries[:-1]),
            f"{node}/{name}: invalid string list")
    return tuple(entries[:-1])


def cells(path, node, name, count):
    values = tuple(int(x, 16) for x in prop(path, node, name, "x").split())
    require(len(values) == count, f"{node}/{name}: expected {count} cells")
    return values


def extent(path, node, name):
    high, low, size_high, size_low = cells(path, node, name, 4)
    start = (high << 32) | low
    size = (size_high << 32) | size_low
    require(size and start + size <= 1 << 64, f"{node}/{name}: invalid extent")
    return start, size


def enabled(path, node, properties):
    return "status" not in properties or strings(path, node, "status") in (("okay",), ("ok",))


def verify_dtb(path):
    require(__debug__, "optimized Python disables FDT parser checks")
    require(BOARD in strings(path, "/", "compatible"), "not a W1700K UBI DTB")
    require(strings(path, NPU, "compatible") == ("airoha,en7581-npu",), "wrong NPU")
    require(enabled(path, NPU, listing(path, NPU, "-p")), "NPU is disabled")
    names = strings(path, NPU, "memory-region-names")
    require("dma" in names, "missing NPU coherent DMA pool")
    require(names == REGION_NAMES, "NPU region names changed order or cardinality")
    refs = cells(path, NPU, "memory-region", len(names))
    require(all(refs) and len(set(refs)) == len(refs), "duplicate or zero NPU phandle")
    for node in ("/", "/soc", NPU):
        remap = {"dma-ranges", "iommus", "iommu-map", "interconnects"}
        require(remap.isdisjoint(listing(path, node, "-p")),
                f"{node}: unexpected DMA routing property")

    for name in ("#address-cells", "#size-cells"):
        require(cells(path, RESERVED, name, 1) == (2,), "unexpected reserved-memory cells")
    require(raw(path, RESERVED, "ranges") == b"", "reserved-memory has translated addresses")

    by_phandle = {}
    for child in listing(path, RESERVED, "-l"):
        node = f"{RESERVED}/{child}"
        properties = set(listing(path, node, "-p"))
        if "phandle" not in properties:
            continue
        handle, = cells(path, node, "phandle", 1)
        require(handle not in by_phandle, f"{node}: duplicate reservation phandle")
        by_phandle[handle] = node, properties
    require(all(handle in by_phandle for handle in refs), "NPU phandle is not a reservation")

    fixed = {}
    for name, handle in zip(names[:-1], refs[:-1]):
        node, properties = by_phandle[handle]
        require(enabled(path, node, properties), f"{node}: disabled reservation")
        start, size = extent(path, node, "reg")
        require(DRAM_START <= start < start + size <= DRAM_END, f"{node}: outside NPU DRAM")
        require(all(start + size <= lo or lo + length <= start for lo, length in fixed.values()),
                f"{node}: overlaps another fixed NPU reservation")
        fixed[name] = (start, size)

    pool, properties = by_phandle[refs[-1]]
    require(enabled(path, pool, properties), "NPU coherent DMA pool is disabled")
    require(strings(path, pool, "compatible") == ("shared-dma-pool",), "not a coherent pool")
    require("no-map" in properties and raw(path, pool, "no-map") == b"", "pool needs no-map")
    require({"reusable", "linux,cma-default", "linux,dma-default"}.isdisjoint(properties),
            "pool must be dedicated to coherent NPU allocations")
    require("reg" not in properties, "pool must be dynamically placed around fixed reservations")
    require(cells(path, pool, "size", 2) == (0, POOL_SIZE), "wrong NPU pool size")
    require(cells(path, pool, "alignment", 2) == (0, POOL_SIZE), "wrong NPU pool alignment")
    require(extent(path, pool, "alloc-ranges") == (DRAM_START, DRAM_END - DRAM_START),
            "pool allocation range differs from the NPU DRAM window")
    return {
        "dtb_sha256": sha256(path),
        "npu_path": NPU,
        "pool_path": pool,
        "pool_size": POOL_SIZE,
        "pool_alignment": POOL_SIZE,
        "pool_window": [DRAM_START, DRAM_END],
        "fixed_npu_regions": fixed,
    }


def verify_fit(path, image_sha256):
    require(__debug__, "optimized Python disables FIT parser checks")
    require(sha256(path) == image_sha256.lower(), "input SHA-256 mismatch")
    names = listing(path, "/images", "-l")
    image_types = {name: prop(path, "/images/" + name, "type") for name in names}
    selected = select_fit_configuration(path, image_types)
    index = names.index(selected["fdt"])
    with tempfile.TemporaryDirectory(prefix="w1700k-npu-fdt-") as directory:
        dtb = Path(directory) / "selected.dtb"
        run(["dumpimage", "-T", "flat_dt", "-p", index, "-o", dtb, path])
        result = verify_dtb(dtb)
    require(sha256(path) == image_sha256.lower(), "FIT changed during verification")
    return dict(result, fit_sha256=image_sha256.lower(), fit_configuration=selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--dtb", type=Path)
    selection.add_argument("--fit", type=Path)
    parser.add_argument("--sha256", required=True, help="expected SHA-256 of the input file")
    args = parser.parse_args()
    try:
        if args.dtb:
            result = verify_dtb(args.dtb)
            require(args.sha256.lower() == result["dtb_sha256"], "input SHA-256 mismatch")
        else:
            result = verify_fit(args.fit, args.sha256)
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"NPU coherent window: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
