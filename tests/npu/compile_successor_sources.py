#!/usr/bin/env python3
"""Compile three successor translation units, not a production module build."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
from tempfile import TemporaryDirectory

from elftools.elf.elffile import ELFFile

import verify_ppe_table_owner as ppe
from npu_replay_proof import digest, path_under, require
import npu_successor_sources as sources

ROOT = sources.ROOT
PARENT_OUTPUT = ".local/npu-build-scratch/native-c2/fw-txp-20261118-modules-a/modules/mt76"
OLD_MT76_INCLUDE = ROOT / ".local/npu-checked-irq-modules/rro-reset-q4/mt76"
PINNED = {
    "provider-main": "c7e4723fe474d11426b2d9286da6a8786cd2e7581bc3250413565132e619f5f1",
    "dma": "31a4aa8f70ad1600846da02d9cd563e89a82130709e721f088908b2b285bc24e",
    "npu": "1690c7413124cea6d6bb807c45e1c66c0a1eab6a05e1c05fbace10be69deb2a0",
}
LIMIT = 402653184


def saved_command(path, name):
    line = path.read_bytes().splitlines(keepends=True)[0]
    require(hashlib.sha256(line).hexdigest() == PINNED[name], f"Retained compile flags drift: {name}")
    return shlex.split(line.decode("ascii").split(":=", 1)[1])


def compile_one(compiler, flags, source, dest, kernel, private, authority, name):
    require(not dest.exists(), f"Existing scratch object: {name}")
    ppe.run(["nice", "-n", "19", "prlimit", f"--as={LIMIT}", "--",
             compiler, f"-I{private / 'include'}", *flags,
             f"-ffile-prefix-map={private}=.successor-kernel",
             f"-ffile-prefix-map={authority}=.successor-authority",
             "-c", "-o", dest, source], cwd=kernel)
    with dest.open("rb") as stream:
        elf = ELFFile(stream)
        require(elf.little_endian and elf.elfclass == 64 and elf["e_machine"] == "EM_AARCH64"
                and elf["e_type"] == "ET_REL", f"Unexpected compiled architecture: {name}")
        text = elf.get_section_by_name(".text")
        require(text is not None and text["sh_size"] > 0, f"Missing compiled text: {name}")
        text_pin = hashlib.sha256(text.data()).hexdigest()
    return dict(sha256=digest(dest), bytes=dest.stat().st_size,
                text_sha256=text_pin, flags_sha256=PINNED[name])


def run(authority, pin, private):
    contract, _, lock = sources.verify_authority(authority, pin)
    kernel = sources.kernel_path(ppe.BUILD, lock["kernel"])
    compiler, = ppe.BUILD.glob("staging_dir/toolchain-*/bin/aarch64-openwrt-linux-musl-gcc")
    require(digest(compiler) == ppe.COMPILER_SHA and digest(kernel / ".config") == ppe.CONFIG,
            "Retained compiler or kernel configuration differs")
    kernel_base = authority / sources.MERGED / "kernel-merged"
    for name in contract["sources"]["kernel"]:
        sources.handoff.copy_source(path_under(kernel_base, name), private / name)
    for name, row in sources.component_paths(lock).items():
        src = path_under(authority, row["source"])
        require(digest(src) == row["sha256"], f"Component drift: {name}")
        to = private / name
        if to.exists():
            require(digest(to) == row["sha256"], f"Conflicting component: {name}")
        else:
            sources.handoff.copy_source(src, to)

    objects = {}
    name = "provider-main"
    driver = ppe.ETH / "w1700k"
    c_path, o_path = driver / f"{name}.c", driver / f"{name}.o"
    argv = saved_command(kernel / driver / f".{name}.o.cmd", name)
    require(argv[:3] == ["ccache", compiler.name, f"-Wp,-MMD,{driver}/.{name}.o.d"] and
            argv[-4:] == ["-c", "-o", str(o_path), str(c_path)], "Provider compile command differs")
    old, new = f"-I./{driver}/kernel-include", f"-I{private / driver / 'kernel-include'}"
    flags = [new if x == old else x for x in argv[3:-4]]
    require(flags.count(new) == 1, "Provider kernel include was not redirected")
    objects[name] = compile_one(compiler, flags, private / c_path, private / o_path,
                                kernel, private, authority, name)
    mt76 = authority / sources.MERGED / "mt76-merged"
    for name in ("dma", "npu"):
        argv = saved_command(ROOT / PARENT_OUTPUT / f".{name}.o.cmd", name)
        require(argv[:2] == [str(compiler), f"-Wp,-MMD,./.{name}.o.d"] and
                argv[-4:] == ["-c", "-o", f"{name}.o", f"{name}.c"], f"Unexpected mt76 command: {name}")
        flags = [f"-I{mt76}" if x == f"-I{OLD_MT76_INCLUDE}" else x for x in argv[2:-4]]
        require(flags.count(f"-I{mt76}") == 1, f"mt76 source include was not redirected: {name}")
        objects[name] = compile_one(compiler, flags, path_under(mt76, f"{name}.c"), private / f"{name}.o",
                                    kernel, private, authority, name)
    sources.verify_authority(authority, pin)
    return dict(source_contract_sha256=pin, compiler_sha256=ppe.COMPILER_SHA,
                retained_kernel_config_sha256=ppe.CONFIG, address_space_limit_bytes=LIMIT,
                objects=objects, full_module_producer=False, world_built=False, module_loaded=False, hardware=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    args = parser.parse_args()
    authority = path_under(ROOT / ".local", ROOT / args.authority, directory=True)
    try:
        with TemporaryDirectory(prefix="successor-objects-") as folder:
            result = run(authority, args.contract_sha256, Path(folder))
    except (ValueError, AssertionError, KeyError, OSError) as error:
        parser.exit(1, f"successor object check: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
