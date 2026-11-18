#!/usr/bin/env python3
"""Rehearse and bind the successor's prepared sources without running a build."""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
from tempfile import TemporaryDirectory

from npu_replay_proof import SOURCE_LOCK, digest, is_digest, path_under, read_pinned, require
from npu_world_sources import linked_module_sources, mt76_source_file
import stage_npu_coherent_handoff as handoff

if not __debug__:
    raise RuntimeError("Successor source verification requires Python assertions enabled")

ROOT = handoff.ROOT
STORE = ".local/npu-successor-sources-20261118"
CONTRACT = ".local/npu-successor-sources/contract.json"
MERGED = ".local/merge-nonoc-20260923"
CONFIG = "firmware/build.config"
PREPARED = Path("build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581")
SCHEMA = "w1700k-successor-sources-v1"


def relative_name(name):
    require(isinstance(name, str) and "\\" not in name, "Invalid successor source path")
    path = PurePosixPath(name)
    require(path.parts and not path.is_absolute() and ".." not in path.parts and path.as_posix() == name,
            f"Invalid successor source path: {name}")
    return name


def overlays(lock):
    result = {}
    for key, prefix in (("openwrt", ""), ("luci", "feeds/luci/")):
        for row in lock[key]["changed_files"]:
            name = prefix + relative_name(row["path"])
            require(name not in result and is_digest(row["sha256"]), f"Unbound overlay entry: {name}")
            result[name] = row
    return result


def kernel_path(build, release):
    require(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", release), "Unsupported prepared kernel version")
    return path_under(build, PREPARED / f"linux-{release}", directory=True)


def mt76_path(build, revision):
    require(re.fullmatch(r"[0-9a-f]{40}", revision), "Unsupported prepared mt76 revision")
    area = path_under(build, PREPARED, directory=True)
    candidates = [p for p in area.glob("mt76-*") if p.name.endswith("~" + revision[:8])]
    require(len(candidates) == 1, "Expected one prepared tree for the locked mt76 revision")
    return path_under(area, candidates[0], directory=True)


def component_paths(lock):
    prefix = "target/linux/airoha/files-" + lock["kernel"].rsplit(".", 1)[0] + "/"
    outputs = {}
    for row in lock["component_sources"]:
        require(row["tree"] == "openwrt" and row["destination"].startswith(prefix),
                "Unexpected successor component tree")
        name = relative_name(row["destination"].removeprefix(prefix))
        require(name not in outputs and is_digest(row["sha256"]), f"Unbound component: {name}")
        relative_name(row["source"])
        outputs[name] = row
    return outputs


def read_lock(authority, contract):
    lock, pin = read_pinned(path_under(authority, SOURCE_LOCK), contract["source_lock_sha256"])
    require(pin != contract["parent_lock_sha256"] and digest(path_under(authority, CONFIG)) ==
            contract["config_sha256"], "Staged source lock or build config differs")
    return lock


def verify_authority(authority, contract_pin):
    contract, pin = read_pinned(path_under(authority, CONTRACT), contract_pin)
    require(contract["schema"] == SCHEMA and contract["source_only"] is True
            and contract["compiler_ran"] is False, "Not a successor source-only contract")
    lock = read_lock(authority, contract)
    files = contract["files"]
    require(files[SOURCE_LOCK] == contract["source_lock_sha256"] and
            files[CONFIG] == contract["config_sha256"] and
            set(contract["sources"]) == set(contract["patches"]) == {"kernel", "mt76"},
            "Incomplete successor authority")
    for name, expected in files.items():
        require(is_digest(expected) and digest(path_under(authority, relative_name(name))) == expected,
                f"Successor source authority differs: {name}")
    for group, sources in contract["sources"].items():
        require(group in ("kernel", "mt76") and sources and all(
            files.get(f"{MERGED}/{group}-merged/{name}") == h for name, h in sources.items()),
            f"Missing checked {group} authority files")
    return contract, pin, lock


def verify_tail(build, group, series):
    directory = path_under(build, relative_name(series["directory"]), directory=True)
    entries = list(directory.iterdir())
    require(all(p.is_file() and not p.is_symlink() and p.name.endswith(".patch") for p in entries),
            f"Unsupported prepared {group} patch series")
    names = sorted(p.name for p in entries)
    order = series["order"]
    require(order and order[0] in names and names[names.index(order[0]):] == order,
            f"Prepared {group} patch tail differs from the checked order")
    for name in order:
        require(digest(path_under(directory, relative_name(name))) == series["sha256"][name],
                f"Prepared {group} patch differs: {name}")


def verify_prepared(build, contract, lock):
    for name, row in overlays(lock).items():
        path = path_under(build, name)
        require(digest(path) == row["sha256"] and stat.S_IMODE(path.stat().st_mode) == int(row["mode"], 8),
                f"Prepared locked overlay differs: {name}")
    require(digest(path_under(build, ".config")) == contract["config_sha256"],
            "Prepared build config differs from successor")
    kernel = kernel_path(build, lock["kernel"])
    mt76 = mt76_path(build, lock["mt76"])
    for group, tree in (("kernel", kernel), ("mt76", mt76)):
        verify_tail(build, group, contract["patches"][group])
        for name, expected in contract["sources"][group].items():
            name = relative_name(name)
            selected = path_under(tree, name) if group == "kernel" else mt76_source_file(tree, name, lock["mt76"])
            require(digest(selected) == expected, f"Prepared {group} source differs: {name}")
    components = component_paths(lock)
    for name, row in components.items():
        require(digest(path_under(kernel, name)) == row["sha256"], f"Prepared component differs: {name}")
    return dict(kernel_files=len(contract["sources"]["kernel"]), mt76_files=len(contract["sources"]["mt76"]),
                component_files=len(components), source_lock_sha256=contract["source_lock_sha256"],
                patch_orders={group: row["order"] for group, row in contract["patches"].items()})


def verify_producer(authority, contract, contract_pin, receipt, receipt_pin):
    receipt = path_under(authority, authority / receipt)
    require(is_digest(receipt_pin) and digest(receipt) == receipt_pin and
            receipt_pin != contract["parent_producer_sha256"], "Expected an independently pinned successor producer")
    checked = linked_module_sources(authority, receipt)
    require(checked["receipt_sha256"] == receipt_pin, "Successor producer changed")
    check_producer_contract(checked, contract, contract_pin)
    return checked


def check_producer_contract(checked, contract, contract_pin):
    require(checked["receipt_sha256"] != contract["parent_producer_sha256"] and
            checked["source_lock_sha256"] == contract["source_lock_sha256"] and
            checked["inputs"].get(CONTRACT) == contract_pin and checked["inputs"].get(CONFIG) == contract["config_sha256"],
            "Producer does not bind the successor source contract and build config")
    for group in ("kernel", "mt76"):
        require(checked[group] == contract["sources"][group], f"Producer {group} prepared inputs differ")
    artifacts = {Path(name).name: pin for name, pin in checked["artifacts"].items()}
    require(artifacts.keys() == contract["parent_artifacts"].keys() and artifacts != contract["parent_artifacts"],
            "Successor producer reuses the parent's complete module set")


def world_contract(authority, lock, checked):
    pin = checked["inputs"].get(CONTRACT)
    require(is_digest(pin), "Late module patches require the successor source contract")
    contract, _, expected = verify_authority(authority, pin)
    require(expected == lock, "Successor contract does not match the effective world lock")
    check_producer_contract(checked, contract, pin)
    proof = dict(kernel_patch_files=len(contract["sources"]["kernel"]),
                 component_sources=len(component_paths(lock)),
                 mt76_source_files=len(contract["sources"]["mt76"]),
                 source_contract_sha256=pin,
                 patch_orders={group: row["order"] for group, row in contract["patches"].items()})
    return contract, proof


def bind_series(authority, bundle, parent, scratch):
    lock, _ = read_pinned(path_under(authority, SOURCE_LOCK), bundle["files"][SOURCE_LOCK])
    locked = overlays(lock)
    series, sources = {}, {}
    for group, old in handoff.OLD_PATCHES.items():
        info = bundle["source_stack"][group]
        order = info["patch_order"]
        directory = Path(old).parent
        require(order and order[0] == Path(old).name and order == sorted(set(order)),
                f"Invalid checked {group} patch order")
        patches = {name: locked[(directory / relative_name(name)).as_posix()]["sha256"] for name in order}
        targets = set()
        for name in order:
            patch = path_under(authority, Path(handoff.OV) / directory / name)
            require(digest(patch) == patches[name], f"Wrong locked source patch: {name}")
            names = handoff.patch_paths(patch, scratch)
            if name == order[0]:
                require(len(names) == info["baseline_outputs_checked"] and names <= parent[group].keys() and
                        (group != "kernel" or names == parent[group].keys()), "Wrong parent patch output set")
            targets.update(names)
        require(targets == info["postimages"].keys(), f"Missing or extra checked {group} postimages")
        sources[group] = parent[group] | info["postimages"]
        series[group] = dict(directory=directory.as_posix(), order=order, sha256=patches)
    return lock, series, sources


def materialize(authority, bundle_file, bundle_pin, producer, producer_pin):
    bundle, _ = read_pinned(bundle_file, bundle_pin)
    require(bundle_file.name == "receipt.json" and bundle["producer_sha256"] == producer_pin,
            "Wrong staged successor bundle")

    def inspect(parent, scratch, prepared, files, receipt):
        handoff.check_published(bundle_file.parent, files, receipt)
        require(receipt == bundle and digest(bundle_file) == bundle_pin, "Successor bundle changed")
        shutil.copytree(scratch / "authority", authority)
        lock, series, sources = bind_series(authority, bundle, parent, scratch)
        kernel = prepared / PREPARED / f"linux-{lock['kernel']}"
        mt76 = prepared / PREPARED / f"mt76-source-fixture~{lock['mt76'][:8]}"
        for group, tree in (("kernel", kernel), ("mt76", mt76)):
            generated = bundle["source_stack"][group]["postimages"]
            for name, expected in sources[group].items():
                source = (path_under(scratch / group, name) if name in generated
                          else path_under(ROOT / MERGED / (group + "-merged"), name))
                require(digest(source) == expected, f"Rehearsed {group} source differs: {name}")
                target = authority / MERGED / (group + "-merged") / name
                handoff.copy_source(source, target)
                handoff.copy_source(target, tree / name)
        for name, row in component_paths(lock).items():
            origin = path_under(authority, row["source"])
            require(digest(origin) == row["sha256"], f"Wrong component source: {name}")
            target = kernel / name
            if target.exists():
                require(digest(target) == row["sha256"], f"Component overlaps a different patched source: {name}")
            else:
                handoff.copy_source(origin, target)
        watched = {p.relative_to(authority).as_posix(): digest(p) for p in sorted(authority.rglob("*"))
                   if p.is_file()}
        contract = dict(schema=SCHEMA, source_only=True, compiler_ran=False,
                        parent_lock_sha256=bundle["parent_lock_sha256"], parent_producer_sha256=producer_pin,
                        parent_artifacts={Path(name).name: pin for name, pin in parent["artifacts"].items()},
                        staged_bundle_sha256=bundle_pin, source_lock_sha256=bundle["files"][SOURCE_LOCK],
                        config_sha256=watched[CONFIG], files=watched, patches=series, sources=sources)
        contract["prepared_fixture"] = verify_prepared(prepared, contract, lock)
        handoff.write_source(authority / CONTRACT, handoff.as_json(contract))

    frame = handoff.FRAME_PATCH_NAME in bundle["source_stack"]["kernel"]["patch_order"]
    handoff.prepare(producer, producer_pin, with_qdma=True, with_frame_fix=frame, inspect_rehearsal=inspect)
    pin = digest(path_under(authority, CONTRACT))
    contract, _, _ = verify_authority(authority, pin)
    return contract, pin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--name", required=True)
    for name in ("bundle", "parent-producer"):
        prepare.add_argument("--" + name, required=True, type=Path)
        prepare.add_argument("--" + name + "-sha256", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--authority", required=True, type=Path)
    verify.add_argument("--contract-sha256", required=True)
    verify.add_argument("--prepared", type=Path)
    verify.add_argument("--producer", type=Path)
    verify.add_argument("--producer-sha256")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            require(re.fullmatch(r"[a-z][a-z0-9-]{0,39}", args.name), "Invalid successor source pack name")
            store = path_under(ROOT / ".local", ROOT / STORE, directory=True)
            output = store / args.name
            require(not output.exists() and not output.is_symlink(), "Successor source pack already exists")
            bundle = path_under(handoff.OUT, ROOT / args.bundle)
            producer = path_under(ROOT / ".local", ROOT / args.parent_producer)
            with TemporaryDirectory(prefix=".successor-", dir=store) as temporary:
                authority = Path(temporary) / "root"
                contract, pin = materialize(authority, bundle, args.bundle_sha256,
                                            producer, args.parent_producer_sha256)
                shutil.copytree(authority, output)
                verify_authority(output, pin)
            result = dict(authority=str(output), contract_sha256=pin,
                          source_only=True, prepared_fixture=contract["prepared_fixture"])
        else:
            authority = path_under(ROOT, ROOT / args.authority, directory=True)
            contract, pin, lock = verify_authority(authority, args.contract_sha256)
            result = dict(authority_verified=True, contract_sha256=pin, source_only=True)
            if args.prepared is not None:
                result["prepared"] = verify_prepared(path_under(ROOT, ROOT / args.prepared, directory=True),
                                                     contract, lock)
            require((args.producer is None) == (args.producer_sha256 is None), "Supply both producer path and pin")
            if args.producer is not None:
                checked = verify_producer(authority, contract, pin, args.producer, args.producer_sha256)
                result["linked_producer_sha256"] = checked["receipt_sha256"]
    except (AssertionError, KeyError, OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"successor sources: {error}\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
