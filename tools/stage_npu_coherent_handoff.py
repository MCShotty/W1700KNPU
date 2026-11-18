#!/usr/bin/env python3
"""Rehearse the staged W1700K stack and publish a private source-only delta."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

from npu_world_sources import digest, linked_module_sources, relative_file, stage_locked_overlays
from verify_npu_coherent_window import verify_dtb

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".local/merge-nonoc-20260923"
BUILD = ROOT / ".build/merged-openwrt"
OUT = ROOT / ".local/npu-coherent-handoff-20261118/bundles"
CHECKPOINTS = ROOT / "research/checkpoints"
WINDOW = CHECKPOINTS / "2026-11-18-npu-coherent-window"
PACKET = CHECKPOINTS / "2026-11-18-npu-packet-owner"
PPE_OWNER = CHECKPOINTS / "2026-11-18-npu-ppe-table-owner"
QDMA_OWNER = CHECKPOINTS / "2026-11-18-npu-qdma-owner"
KDIR = "target/linux/airoha/patches-6.18"
MDIR = "package/kernel/mt76/patches"
DT = "target/linux/airoha/dts/an7581-w1700k-ubi.dts"
BINDING = "Documentation/devicetree/bindings/net/airoha,en7581-npu.yaml"
PROVIDER = "drivers/net/ethernet/airoha/airoha_npu.c"
HEADER = "include/linux/soc/airoha/airoha_offload.h"
SOURCE_LOCK = "firmware/source-lock.json"
OV = "firmware/overlay/openwrt"
OLD_PATCHES = {
    "kernel": f"{KDIR}/999-w1700k-integrated-npu.patch",
    "mt76": f"{MDIR}/900-w1700k-integrated-npu.patch",
}
NEW_PATCHES = {
    "kernel": {
        f"{KDIR}/9999-w1700k-npu-coherent-pool-binding.patch": WINDOW / "airoha-npu-coherent-pool-binding.patch",
        f"{KDIR}/9999-w1700k-npu-coherent-provider.patch": WINDOW / "airoha-checked-coherent-window.patch",
    },
    "mt76": {f"{MDIR}/901-w1700k-checked-dma-owner.patch": PACKET / "mt76-checked-dma-owner.patch"},
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def as_json(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def read_json(path):
    return json.loads(path.read_bytes())


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def copy_source(source, target):
    require(source.is_file() and not source.is_symlink(), f"not a plain source file: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def write_source(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o644)


def run(argv, cwd, **kwargs):
    done = subprocess.run(argv, cwd=cwd, timeout=90, capture_output=True, **kwargs)
    if done.returncode:
        detail = (done.stderr or done.stdout).decode(errors="replace").strip()[-1500:]
        raise ValueError(f"{Path(argv[0]).name} exited {done.returncode}: {detail}")
    return done.stdout


def patch_paths(patch, scratch):
    rows = run(["git", "apply", "--numstat", "-z", patch], scratch).split(b"\0")
    paths = set()
    for row in filter(None, rows):
        added, removed, name = row.decode("ascii").split("\t", 2)
        require(added.isdecimal() and removed.isdecimal() and
                re.fullmatch(r"[a-zA-Z0-9_./,-]+", name) and name not in paths,
                "expected only distinct text patch targets")
        relative_file(scratch, name)
        paths.add(name)
    require(paths, f"empty patch: {patch.name}")
    return paths


def check_order(lower, old, additions):
    candidates = list(lower.iterdir())
    require(all(p.is_file() and not p.is_symlink() and p.name.endswith(".patch") for p in candidates),
            f"patch series convention changed: {lower}")
    names = sorted(p.name for p in candidates)
    require(names and names[-1] == old and additions and len(set(additions)) == len(additions)
            and not set(names) & set(additions),
            "integrated patch is no longer the last existing patch")
    order = [old, *sorted(additions)]
    require(order == sorted(order), "new patch does not follow its integrated preimage")
    return order


def apply_series(target, patch_dir, selected):
    patch = shutil.which("patch")
    require(patch is not None, "GNU patch is required")
    env = dict(os.environ, LC_ALL="C", PATCH=f"{patch} --fuzz=0 --no-backup-if-mismatch")
    text = run(["sh", BUILD / "scripts/patch-kernel.sh", target, patch_dir, selected],
               target, env=env).decode("ascii")
    require(not re.search(r"\b(offset|fuzz)\b", text), "patch application was not exact")
    return re.findall(r"^Applying .*/([^/ ]+) using plaintext: ", text, re.M)


def rehearse(component, source, order, expected_pre, expected_post, scratch, upstream_overrides,
             prerequisites):
    target = scratch / component
    legacy = scratch / (component + "-integrated-patch")
    series = scratch / (component + "-patches")
    target.mkdir()
    legacy.mkdir()
    series.mkdir()
    old = source[order[0]]
    legacy_paths = patch_paths(old, target)
    late_paths = set().union(*(patch_paths(source[name], target) for name in order[1:]))
    require(late_paths == set(expected_post) and legacy_paths <= expected_pre.keys(),
            f"unexpected {component} patch target set")
    for name in sorted(legacy_paths | late_paths):
        upstream = upstream_overrides.get(name)
        if upstream is None:
            upstream = relative_file(WORK / (component + "-upstream"), name)
        if upstream.exists():
            copy_source(upstream, target / name)
    copy_source(old, legacy / order[0])
    for name in order[1:]:
        copy_source(source[name], series / name)

    require(apply_series(target, legacy, "*") == order[:1], "wrong integrated patch applied")
    for name in sorted(legacy_paths | late_paths):
        require(digest(target / name) == expected_pre[name], f"integrated {component} preimage differs: {name}")
    applied = []
    for patch in order[1:]:
        require(all(digest(target / name) == sha for name, sha in prerequisites.get(patch, {}).items()),
                "wrong intermediate preimage for " + patch)
        applied.extend(apply_series(target, series, patch))
    require(applied == order[1:], "wrong late patch order")
    post = {name: digest(target / name) for name in sorted(legacy_paths | late_paths)}
    require(post == {name: expected_post.get(name, expected_pre[name]) for name in post},
            f"final {component} postimages differ")
    return dict(patch_order=order, baseline_outputs_checked=len(legacy_paths), postimages=post)


def derive_lock(lock, additions, *, with_ppe=False, with_qdma=False):
    result = copy.deepcopy(lock)
    rows = result["openwrt"]["changed_files"]
    existing = {row["path"] for row in rows}
    require(len(existing) == len(rows) and not existing & additions.keys(),
            "prepared lock already owns a candidate path")
    rows.extend(dict(path=name, sha256=sha_bytes(data), mode="0o644") for name, data in additions.items())
    rows.sort(key=lambda row: row["path"])
    variant = "ppe-qdma" if with_qdma else "ppe" if with_ppe else "window"
    result["snapshot"] = f"nonoc-merged-coherent-{variant}-20261118"
    return result


def check_staging(parent_lock, new_lock, additions, scratch):
    """Exercise the actual private-world stage API on sparse sealed inputs."""
    authority, prepared = scratch / "authority", scratch / "prepared"
    authority.mkdir()
    prepared.mkdir()
    for label, prefix in (("openwrt", Path()), ("luci", Path("feeds/luci"))):
        for row in parent_lock[label]["changed_files"]:
            name = row["path"]
            overlay = f"firmware/overlay/{label}/{name}"
            source = relative_file(ROOT, overlay)
            if source.is_file():
                copy_source(source, authority / overlay)
            lower = relative_file(BUILD, str(prefix / name))
            if lower.is_file():
                copy_source(lower, prepared / prefix / name)
    for row in parent_lock["component_sources"]:
        copy_source(relative_file(ROOT, row["source"]), authority / row["source"])
    copy_source(ROOT / "firmware/build.config", authority / "firmware/build.config")
    write_source(authority / SOURCE_LOCK, as_json(new_lock))
    for name, content in additions.items():
        write_source(authority / OV / name, content)
    stale = sorted(name for name in OLD_PATCHES.values()
                   if digest(BUILD / name) != digest(ROOT / OV / name))
    proof = stage_locked_overlays(prepared, authority, new_lock, shutil.copyfile)
    require(set(stale) | set(additions) <= set(proof["copied"]),
            "stale aggregate or candidate source was not refreshed")
    return prepared, {**proof, "copied": sorted(proof["copied"]), "stale_aggregates_refreshed": stale}


def prepare(producer, pin, *, with_ppe=False, with_qdma=False):
    require(__debug__ and digest(producer) == pin, "unverified producer")
    checked = linked_module_sources(ROOT, producer)
    window = read_json(WINDOW / "EVIDENCE.json")
    packet = read_json(PACKET / "EVIDENCE.json")
    budget = read_json(CHECKPOINTS / "2026-11-18-npu-coherent-budget/EVIDENCE.json")
    baseline = read_json(ROOT / SOURCE_LOCK)
    require(checked["source_lock_sha256"] == window["source_lock_sha256"] and
            checked["receipt_sha256"] == window["producer_sha256"] == budget["producer_sha256"] and
            window["patch_sha256"] == budget["patch_sha256"], "no matching locked stack and capacity evidence")
    kernel, = (BUILD / "build_dir").glob(f"target-*/linux-airoha*/linux-{baseline['kernel']}")
    protected = {ROOT / SOURCE_LOCK, BUILD / DT, kernel / BINDING, BUILD / "scripts/patch-kernel.sh"}
    protected.update(p / name for name in OLD_PATCHES.values() for p in (ROOT / OV, BUILD))
    ppe = read_json(PPE_OWNER / "EVIDENCE.json") if with_ppe or with_qdma else None
    qdma = read_json(QDMA_OWNER / "EVIDENCE.json") if with_qdma else None
    ppe_patch = PPE_OWNER / "airoha-ppe-table-owner.patch"
    qdma_patch = QDMA_OWNER / "airoha-qdma-owner.patch"
    ppe_dir = "drivers/net/ethernet/airoha"
    if ppe is not None:
        require(set(ppe["original"]) == set(ppe["patched"]) ==
                {"airoha_eth.c", "airoha_eth.h", "airoha_ppe.c"}, "unexpected PPE owner paths")
        protected.update(relative_file(kernel, f"{ppe_dir}/{n}") for n in ppe["original"])
        protected.update((kernel / ".config", ppe_patch))
    if qdma is not None:
        require(set(qdma["original"]) == set(qdma["patched"]) == {"airoha_eth.c", "airoha_eth.h"}
                and all(sha == ppe["patched"][name] for name, sha in qdma["original"].items())
                and qdma["baseline_config_sha256"] == ppe["baseline_configuration"]["config_sha256"],
                "QDMA patch is not based on the staged PPE sources")
        protected.add(qdma_patch)
    protected_before = {p: digest(p) for p in protected}
    expect = {row["path"]: row["sha256"] for row in baseline["openwrt"]["changed_files"]}
    require(digest(BUILD / DT) == window["preimages"][DT] and
            digest(kernel / BINDING) == window["preimages"][BINDING], "DTS or binding base changed")

    with TemporaryDirectory(prefix="w1700k-handoff-") as directory:
        scratch = Path(directory)
        proof, additions = {}, {}
        for group, old in OLD_PATCHES.items():
            old_file = ROOT / OV / old
            require(digest(old_file) == expect[old], f"{group} aggregate drift")
            late = dict(NEW_PATCHES[group])
            pins = dict(window["patch_sha256"])
            overrides = {}
            prerequisites = {}
            if group == "kernel" and ppe is not None:
                late[f"{KDIR}/9999-w1700k-ppe-table-owner.patch"] = ppe_patch
                pins[ppe_patch.name] = ppe["patch_sha256"]
                require(protected_before[kernel / ".config"] ==
                        ppe["baseline_configuration"]["config_sha256"], "unverified PPE configuration")
                if qdma is not None:
                    qdma_name = "9999-w1700k-qdma-owner.patch"
                    late[f"{KDIR}/{qdma_name}"] = qdma_patch
                    pins[qdma_patch.name] = qdma["patch_sha256"]
                    prerequisites[qdma_name] = {f"{ppe_dir}/{f}": sha for f, sha in qdma["original"].items()}
            order = check_order(BUILD / Path(old).parent, Path(old).name, [Path(p).name for p in late])
            paths = {Path(n).name: p for n, p in {old: old_file, **late}.items()}
            require(all(digest(p) == pins[p.name] for p in late.values()), "staged patch drift")
            pre = dict(checked[group])
            if group == "kernel":
                overrides[BINDING] = kernel / BINDING
                pre[BINDING] = window["preimages"][BINDING]
                post = {name: window["postimages"][name] for name in (PROVIDER, HEADER, BINDING)}
                if ppe is not None:
                    for file, sha in ppe["original"].items():
                        name = f"{ppe_dir}/{file}"
                        require(name not in pre and name not in post, "overlapping PPE owner preimage")
                        overrides[name] = relative_file(kernel, name)
                        pre[name] = sha
                        post[name] = ppe["patched"][file]
                if qdma is not None:
                    post.update((f"{ppe_dir}/{f}", sha) for f, sha in qdma["patched"].items())
            else:
                post = packet["postimages"]["mt76"]
            proof[group] = rehearse(group, paths, order, pre, post, scratch, overrides, prerequisites)
            additions.update((n, p.read_bytes()) for n, p in late.items())

        dtree = scratch / "dts"
        updated = dtree / DT
        copy_source(BUILD / DT, updated)
        dt_patch = WINDOW / "openwrt-w1700k-coherent-window.patch"
        require(digest(dt_patch) == window["patch_sha256"][dt_patch.name] and
                patch_paths(dt_patch, dtree) == {DT}, "unexpected W1700K DTS patch")
        run(["git", "apply", "--whitespace=error-all", dt_patch], dtree)
        require(digest(updated) == window["postimages"][DT], "DTS postimage differs")
        additions[DT] = updated.read_bytes()
        derived = derive_lock(baseline, additions, with_ppe=with_ppe, with_qdma=with_qdma)
        prepared, staging = check_staging(baseline, derived, additions, scratch)
        dts_dir = Path(DT).parent
        overlay_dts = run(["cpp", "-x", "assembler-with-cpp", "-nostdinc", "-undef", "-D__DTS__",
                           "-I", kernel / "include", "-I", prepared / dts_dir, "-I", BUILD / dts_dir,
                           prepared / DT], dtree)
        dtb = scratch / "next.dtb"
        run(["dtc", "-I", "dts", "-O", "dtb", "-p", "1024", "-o", dtb, "-"], dtree, input=overlay_dts)
        layout = json.loads(as_json(verify_dtb(dtb)))
        require(layout == window["standalone_dtb"] and layout["dtb_sha256"] == budget["staged_dtb_sha256"],
                "generated DTB is not the budgeted staged tree")
        require(all(digest(p) == sha for p, sha in protected_before.items()) and
                digest(ROOT / SOURCE_LOCK) == checked["source_lock_sha256"], "protected source changed")

    files = {SOURCE_LOCK: as_json(derived), **{f"{OV}/{k}": v for k, v in additions.items()}}
    return files, dict(
        schema=1, source_preflight_passed=True, source_delta_only=True,
        parent_lock_sha256=checked["source_lock_sha256"], producer_sha256=pin,
        patch_driver_sha256=protected_before[BUILD / "scripts/patch-kernel.sh"],
        source_stack=proof, prepared_overlay_staging=staging, standalone_dtb_sha256=layout["dtb_sha256"],
        files={name: sha_bytes(data) for name, data in files.items()}, active_sources_unchanged=True,
        linux_modules_built=False, fit_built=False, board_contact=False,
    )


def bundle_path(name):
    require(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}", name), "invalid bundle name")
    require(not any(p.is_symlink() for p in (ROOT / ".local", OUT.parent, OUT, OUT / name)),
            "bundle path contains a symlink")
    return OUT / name


def publish(out, files, receipt):
    out.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        write_source(relative_file(out, name), data)
    write_source(out / "receipt.json", as_json(receipt))


def check_published(out, files, receipt):
    require(out.is_dir() and not out.is_symlink(), "bundle not found")
    expected = {"receipt.json", *files}
    entries = list(out.rglob("*"))
    require(not any(p.is_symlink() for p in entries) and
            {p.relative_to(out).as_posix() for p in entries if not p.is_dir()} == expected,
            "unexpected bundle contents")
    require(read_json(out / "receipt.json") == receipt and
            all(digest(out / name) == sha_bytes(data) and (out / name).stat().st_mode & 0o777 == 0o644
                for name, data in files.items()),
            "published bundle differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    names = parser.add_mutually_exclusive_group(required=True)
    names.add_argument("--name")
    names.add_argument("--check")
    parser.add_argument("--producer", type=Path, required=True)
    parser.add_argument("--producer-sha256", required=True)
    parser.add_argument("--ppe-table-owner", action="store_true", help="include the staged W1700K PPE owner")
    parser.add_argument("--qdma-owner", action="store_true", help="include the staged PPE and QDMA owners")
    args = parser.parse_args()
    try:
        out = bundle_path(args.name or args.check)
        require(not args.name or not out.exists(), "bundle already exists")
        files, receipt = prepare(args.producer, args.producer_sha256,
                                 with_ppe=args.ppe_table_owner, with_qdma=args.qdma_owner)
        if args.name:
            publish(out, files, receipt)
        check_published(out, files, receipt)
    except (AssertionError, KeyError, OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"coherent handoff: {error}\n")
    print(json.dumps(dict(bundle=str(out), receipt_sha256=digest(out / "receipt.json"),
                          source_preflight_passed=True, fit_built=False)), flush=True)


if __name__ == "__main__":
    main()
