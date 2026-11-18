#!/usr/bin/env python3
"""Run the frozen offline world with streaming host-side integrity checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import stat
from types import SimpleNamespace

import npu_isolated_world as frozen_world
from npu_replay_proof import SUCCESSOR_CONTRACT, bind_world_replay, verify_replay
from npu_world_sources import digest, relative_file


def fail_walk(error):
    raise error


def record(root, path):
    name = path.relative_to(root).as_posix()
    info = path.lstat()
    row = dict(mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, gid=info.st_gid)
    if stat.S_ISLNK(info.st_mode):
        row.update(kind="link", target=os.readlink(path))
    elif stat.S_ISREG(info.st_mode):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            actual = os.fstat(stream.fileno())
            assert (actual.st_dev, actual.st_ino, actual.st_mode, actual.st_uid, actual.st_gid) == (
                info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid
            ), ("inventory-input-replaced", name)
            row.update(kind="file", sha256=hashlib.file_digest(stream, "sha256").hexdigest())
    elif stat.S_ISDIR(info.st_mode):
        row.update(kind="directory")
    else:
        raise AssertionError(("special-build-input", name, info.st_mode))
    return name, row


def records(root):
    assert root.is_dir() and not root.is_symlink(), ("inventory-root", str(root))
    yield record(root, root)
    for base, dirs, files in os.walk(root, followlinks=False, onerror=fail_walk):
        dirs.sort()
        for name in sorted(dirs + files):
            yield record(root, Path(base) / name)


def inventory(root, writer=None):
    """Keep the same record fields as tree_state without retaining them."""
    checksum = hashlib.sha256()
    count = 0
    for count, item in enumerate(records(root), 1):
        line = (json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")
        checksum.update(line)
        if writer is not None:
            writer.write(line)
    return dict(format="w1700k-tree-jsonl-v1", entries=count, sha256=checksum.hexdigest())


def capture(root, dest):
    with dest.open("xb") as stream:
        return inventory(root, stream)


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def self_peak_bytes():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def run(args):
    world = frozen_world
    assert re.fullmatch("[a-z][a-z0-9-]{0,39}", args.name) and os.getuid() == 1000
    host_pin = digest(Path(__file__))
    selected = world.output_root(args)
    directory = selected / args.name
    assert not os.path.lexists(directory)
    assert digest(args.snapshot) == args.snapshot_sha256, "wrong capsule pin"
    frozen, source = world.snapshot(args.snapshot)
    assert args.module_receipt.absolute() == args.module_receipt.resolve(), "producer receipt alias"
    producer_name = args.module_receipt.absolute().relative_to(world.ROOT).as_posix()
    assert source["files"][producer_name] == args.producer_sha256, "wrong combined producer pin"
    assert digest(relative_file(frozen, producer_name)) == args.producer_sha256
    replay = verify_replay(world.ROOT, args.start, args.start_sha256, args.terminal, args.terminal_sha256,
                           frozen, source["files"])
    lock = digest(frozen / "firmware/source-lock.json")
    from npu_world_sources import has_late_module_patches
    source_lock = json.loads((frozen / "firmware/source-lock.json").read_bytes())
    contract = source["files"].get(SUCCESSOR_CONTRACT, "") if has_late_module_patches(source_lock) else None
    bind_world_replay(replay, lock, args.producer_sha256, contract)
    context = dict(uid=os.getuid(), parent_namespaces=world.namespaces(),
                   frozen_root_identity=world.identity(frozen), source_lock_sha256=lock)
    context["linker"] = world.linker_input(frozen, source)
    context["download_cache"] = world.download_cache_input(frozen, source)
    combined = SimpleNamespace(module_receipt=args.module_receipt, provider_receipt=None, mt76_receipt=None)
    world.producer_context(frozen, source, combined, context)
    bubblewrap, bubblewrap_metadata = world.bubblewrap_input(args, frozen, source)

    directory.mkdir(parents=True)
    for name in ("build-upper", "build-work", "log-upper", "log-work", "tmp"):
        (directory / name).mkdir()
    print(json.dumps(dict(phase="inventory-protected-lower-build", streamed=True,
                          name=args.name, replay_invocation=replay["invocation"])), flush=True)
    cache_before = capture(world.CACHE, directory / "cache-before.jsonl")
    before = capture(world.BUILD, directory / "lower-before.jsonl")
    argv = world.command(frozen, directory, args.name, context, False, bubblewrap)
    envelope = dict(command=argv, snapshot_receipt_sha256=args.snapshot_sha256,
                    snapshot_source_commit=source["source_commit"], source_lock_sha256=lock,
                    parent_namespaces=context["parent_namespaces"], protected_lower_build=str(world.BUILD),
                    physical_output_root=str(directory), bwrap_sha256=bubblewrap_metadata["sha256"],
                    bubblewrap=bubblewrap_metadata, selected_output_root=str(selected), network_isolated=True,
                    producer_sha256=args.producer_sha256, host_launcher_sha256=host_pin,
                    frozen_inner_sha256=source["files"]["tools/npu_isolated_world.py"],
                    original_replay=replay, streamed_inventories=dict(lower=before, cache=cache_before),
                    parent_inventory_peak_rss_bytes=self_peak_bytes())
    save(directory / "launch.json", envelope)
    print(json.dumps(dict(phase="launch-private-offline-world", name=args.name,
                          lower_entries=before["entries"], parent_peak_rss_bytes=self_peak_bytes())), flush=True)
    execution = world.run_logged(argv, directory / "run.log")

    assert digest(bubblewrap) == bubblewrap_metadata["sha256"], "bubblewrap executable changed"
    after = inventory(world.BUILD)
    cache_after = inventory(world.CACHE)
    unchanged, cache_unchanged = before == after, cache_before == cache_after
    assert digest(args.snapshot) == args.snapshot_sha256 and digest(Path(__file__)) == host_pin
    world.snapshot(args.snapshot)
    assert world.namespaces() == context["parent_namespaces"]
    child_path = directory / "build-upper/bin" / ("isolated-world-" + args.name) / "result.json"
    child = json.loads(child_path.read_bytes()) if child_path.exists() else None
    passed = (execution["returncode"] == 0 and unchanged and cache_unchanged and child is not None
              and child["passed"] is True and child["world_build"] is True)
    result = dict(passed=passed, **execution, original_build_content_modes_ownership_links_unchanged=unchanged,
                  original_inventory_entries=before["entries"], snapshot_unchanged=True,
                  parent_namespaces_unchanged=True,
                  original_download_cache_content_modes_ownership_links_unchanged=cache_unchanged,
                  original_download_cache_entries=cache_before["entries"], envelope=envelope, child=child,
                  streamed_inventories_after=dict(lower=after, cache=cache_after),
                  parent_final_peak_rss_bytes=self_peak_bytes(),
                  world_build=bool(child and child["world_build"]), probe_only=False, module_loaded=False,
                  native_cold_qualified=False, full_setup=False, hardware=False,
                  limits=["Frozen inner command, code, cache and producer are unchanged.",
                          "Before/after path, kind, numeric ownership/mode and regular-file bytes or literal links.",
                          "Before/after agreement is not a complete history of intervening writes.",
                          "Offline artifact verification only, not board boot or DMA retirement."])
    if passed:
        relative = Path(child["image_verification"]["image"]).relative_to(world.BUILD.relative_to(world.ROOT))
        physical = directory / "build-upper" / relative
        assert not physical.is_symlink() and digest(physical) == child["image_verification"]["sha256"]
        result.update(physical_image=str(physical), physical_image_sha256=digest(physical))
    save(directory / "result.json", result)
    print(json.dumps(dict(passed=passed, result_sha256=digest(directory / "result.json"),
                          parent_peak_rss_bytes=self_peak_bytes())), flush=True)
    assert passed, ("isolated-world-unqualified", directory / "run.log")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    for name in ("snapshot", "module-receipt", "start", "terminal", "output-root", "bubblewrap"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("snapshot", "producer", "start", "terminal"):
        parser.add_argument("--" + name + "-sha256", required=True)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
