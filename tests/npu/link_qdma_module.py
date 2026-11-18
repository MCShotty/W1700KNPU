#!/usr/bin/env python3
"""Rehearse real modpost and final Ethernet linking with retained kernel inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
from tempfile import TemporaryDirectory

import verify_qdma_owner as qdma
from verify_consumer_queue_owner import digest, require
from npu_ethernet_fit import ETH_MODULE, inspect_linked, normalize

ROOT = qdma.ROOT
PPE = qdma.ppe
MODULE = PPE.ETH / "airoha-eth"
OUTPUT = ROOT / ".local/npu-ethernet-fit-20261118"
INPUTS = {
    "Module.symvers": "636e38237ff569a00f7db0a780fb0c00cdb366ead0a385387d877c78eb88817f",
    ".module-common.o": "cfa8ef3e5508e9312691d675384c930956d0b345db71d1da1a8fec9088fd929a",
    "scripts/module.lds": "5833d140a6132d0615e6273049d4b8dc09530575854b8dfd92015e2fd82becb8",
    "scripts/mod/modpost": "577ccf41eefe3edae9ea88a9af86ba66c790f68c33f8d8aa3b6e9b72d7572296",
    f"{MODULE}.o": "1bf85ae5bf629096fea1703b9b09aa82f2d31c0e6fa27a10810689427f0edcf8",
    f"{MODULE}.ko": "dc9e5cdcd738811160725ba049cc44e24f674d5b59e08be1b772332dd551c12c",
    f"{MODULE}.mod.c": "9654ef1833bb4bdce579936287f3256e0419c8569b6b879d068294a1a02ec22c",
}
MOD_CC = "179a7fc7bc1336677d739654acf7f8de05b54f2ac0bd9815c8770910a30872eb"
MOD_LINK = "3ff8e890ad0afb1e6ef9c18551da2b2f9ee8fe3136abf65a8ec534bc603b6e38"
OBJCOPY = "607d5f9d8ec4903cc4bf859e6f4daa425c2d238aae38cb74acca1c87451bf418"


def imports(kernel):
    """Use preceding kernel/peer exports, never this module's old exports."""
    retained, own = [], []
    for line in (kernel / "Module.symvers").read_bytes().splitlines(keepends=True):
        parts = line.rstrip(b"\r\n").split(b"\t")
        require(len(parts) == 5, "Unexpected export manifest format")
        if parts[2].decode("ascii") == str(MODULE):
            own.append(parts[1])
        else:
            retained.append(line)
    require(sorted(own) == [b"airoha_ppe_get_dev", b"airoha_ppe_put_dev"], "Unexpected old Ethernet exports")
    return b"".join(retained), len(retained)


def saved_command(kernel, name, pin):
    path = kernel / name.parent / ("." + name.name + ".cmd")
    raw = path.read_bytes().splitlines(keepends=True)[0]
    require(hashlib.sha256(raw).hexdigest() == pin, f"Retained module command drift: {name}")
    return shlex.split(raw.decode("ascii").split(":=", 1)[1])


def qualify(kernel, work, aggregate, exports, gcc, ld, *, patched):
    stem = work / MODULE
    stem.parent.mkdir(parents=True, exist_ok=True)
    obj, mod_source, mod_object, ko = (Path(f"{stem}{ext}") for ext in (".o", ".mod.c", ".mod.o", ".ko"))
    shutil.copyfile(aggregate, obj)
    (work / "imports.symvers").write_bytes(exports)
    modpost = PPE.run([kernel / "scripts/mod/modpost", "-M", "-i", "imports.symvers",
                      "-o", "exports.symvers", f"{MODULE}.o"], cwd=work)
    warnings = modpost.stderr.splitlines()
    require(all(line == f"WARNING: modpost: missing MODULE_DESCRIPTION() in {MODULE}.o" for line in warnings),
            "Unexpected modpost diagnostic")
    cmd = saved_command(kernel, Path(str(MODULE) + ".mod.o"), MOD_CC)
    dep = "-Wp,-MMD," + str(MODULE.parent / ".airoha-eth.mod.o.d")
    require(cmd[:3] == ["ccache", gcc.name, dep] and
            cmd[-4:] == ["-c", "-o", f"{MODULE}.mod.o", f"{MODULE}.mod.c"],
            "Unexpected retained module compile command")
    PPE.run(["nice", "-n", "19", "prlimit", "--as=402653184", "--", gcc, *cmd[3:-4],
             "-ffile-prefix-map=" + str(work) + "=.ethernet-modpost-check",
             "-c", "-o", mod_object, mod_source], cwd=kernel)
    cmd = saved_command(kernel, Path(str(MODULE) + ".ko"), MOD_LINK)
    require(cmd[0] == ld.name and cmd[-5:] == ["-o", f"{MODULE}.ko", f"{MODULE}.o",
                                              f"{MODULE}.mod.o", ".module-common.o"],
            "Unexpected retained module link command")
    PPE.run([ld, *cmd[1:-5], "-o", ko, obj, mod_object, kernel / ".module-common.o"], cwd=kernel)
    metadata = inspect_linked(ko.read_bytes(), "6.18.52", require_owner=patched, with_qdma=patched)
    return ko, dict(sha256=digest(ko), bytes=ko.stat().st_size, modpost_output_sha256=digest(mod_source),
                    metadata=metadata, warnings=warnings)


def run(work):
    kernel, = PPE.BUILD.glob("build_dir/target-*/linux-airoha*/linux-6.18.52")
    require(digest(kernel / ".config") == PPE.CONFIG and
            all(digest(kernel / k) == h for k, h in INPUTS.items()), "Retained module context drift")
    gcc, = PPE.BUILD.glob("staging_dir/toolchain-*/bin/aarch64-openwrt-linux-musl-gcc")
    ld = gcc.with_name("aarch64-openwrt-linux-musl-ld")
    objcopy = gcc.with_name("aarch64-openwrt-linux-musl-objcopy")
    require(digest(gcc) == PPE.COMPILER_SHA and digest(ld) == qdma.LINKER,
            "Unexpected retained module toolchain")
    exports, export_count = imports(kernel)

    base, control = qualify(kernel, work / "control", kernel / f"{MODULE}.o", exports, gcc, ld, patched=False)
    prepared_raw = (kernel / f"{MODULE}.ko").read_bytes()
    prepared = normalize(prepared_raw, objcopy, OBJCOPY, work)
    control["normalized_sha256"] = normalize(base.read_bytes(), objcopy, OBJCOPY, work)
    require(control["modpost_output_sha256"] == INPUTS[f"{MODULE}.mod.c"] and control["normalized_sha256"] == prepared,
            "Retained module control did not reproduce its metadata and packaged bytes")

    source = work / "candidate-source"
    source.mkdir()
    qdma.apply_stack(kernel, source)
    evidence_path = qdma.CHECKPOINT / "EVIDENCE.json"
    evidence = json.loads(evidence_path.read_bytes())
    require(digest(qdma.PATCH) == evidence["patch_sha256"] and all(
            digest(source / PPE.ETH / name) == sha for name, sha in evidence["patched"].items()),
            "Unexpected staged QDMA source")
    units = qdma.cross(kernel, source)
    require(units == evidence["cross_compile"], "Different staged Ethernet object inputs")
    aggregate = source / PPE.ETH / "airoha-eth.aggregate.o"
    candidate, linked = qualify(kernel, work / "link", aggregate, exports, gcc, ld, patched=True)
    linked["normalized_sha256"] = normalize(candidate.read_bytes(), objcopy, OBJCOPY, work)
    require(linked["normalized_sha256"] != prepared and
            all(digest(kernel / k) == h for k, h in INPUTS.items()), "Link output or protected kernel context differs")
    return candidate, dict(schema="w1700k-retained-ethernet-kbuild-link-v1", raw_module=ETH_MODULE,
                           kernel_config_sha256=PPE.CONFIG, retained_inputs=INPUTS,
                           normalized_retained_sha256=prepared, control_reproduced=True, control=control,
                           cross_objects_sha256=units["relocatable_aggregate"]["sha256"],
                           qdma_checkpoint_sha256=digest(evidence_path),
                           old_module_exports_removed=2, peer_exports_checked=export_count,
                           imports_sha256=hashlib.sha256(exports).hexdigest(),
                           mod_compile_command_sha256=MOD_CC, mod_link_command_sha256=MOD_LINK,
                           objcopy_sha256=OBJCOPY, linked=linked, full_module_linked=True,
                           whole_world=False, fit_built=False, module_loaded=False, hardware=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="new private output directory name")
    args = parser.parse_args()
    require(re.fullmatch(r"[a-z][a-z0-9-]{0,39}", args.name), "Invalid link receipt name")
    out = OUTPUT / args.name
    require(OUTPUT.resolve(strict=True) == OUTPUT and not out.exists() and not out.is_symlink(),
            "Unexpected link output path")
    with TemporaryDirectory(prefix="w1700k-ethernet-kbuild-") as tmp:
        candidate, proof = run(Path(tmp))
        out.mkdir(mode=0o700)
        shutil.copyfile(candidate, out / ETH_MODULE)
        (out / ETH_MODULE).chmod(0o444)
        require(digest(out / ETH_MODULE) == proof["linked"]["sha256"], "Linked artifact copy differs")
        receipt = out / "receipt.json"
        with receipt.open("x") as stream:
            json.dump(proof, stream, sort_keys=True, indent=2)
            stream.write("\n")
        receipt.chmod(0o444)
    print(json.dumps(dict(path=str(receipt), sha256=digest(receipt), linked=proof["linked"])))


if __name__ == "__main__":
    main()
