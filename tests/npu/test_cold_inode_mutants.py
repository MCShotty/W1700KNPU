#!/usr/bin/env python3
"""Compiled host mutant sensitivity and sanitizers for the portable INODE owner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
import test_cold_inode as owner

HERE, ROOT, CORE, TESTS = owner.HERE, owner.ROOT, owner.CORE, owner.TESTS


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    assert args.name.replace("-", "").isalnum()
    dest = ROOT / ".local/npu-inode-owner" / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    baseline = args.baseline.resolve()
    source_path = CORE / "cold-inode.c"
    source = source_path.read_text()
    mutants = {
        "reader-prior-change": ("equal(c->pcie, &prior, sizeof(prior)) && equal(p, &plan, sizeof(plan));",
                                "equal(p, &plan, sizeof(plan));"),
        "unfinished-pcie-tail": ("npu_cold_pcie_tail_live(c->pcie, &p->prior, epoch, &c->prior)", "1"),
        "late-nested-prior-fault": ("           npu_cold_pcie_tail_live(c->pcie, &p->prior, epoch, &c->prior) &&",
                                    "           1 &&"),
        "ignore-type109-definition": ("read_equal(c, 0x8401cfb8, 4, 0x109) &&", "1 &&"),
        "short-icv-clear": ("p->icv + (index - 3) * 4, 4, 0", "p->icv + ((index - 3) % 1025) * 4, 4, 0"),
        "wrong-store-address": ("npu_cold_inode_recipe(p, s->committed, &store) || address != store.address ||",
                                 "npu_cold_inode_recipe(p, s->committed, &store) || ((void)address, 0) ||"),
        "ignore-readback": ("bytes != store.bytes || readback != store.value || !read_equal(c, address, bytes, readback))",
                             "bytes != store.bytes || ((void)readback, 0))"),
        "forget-possible-effect": ("    npu_cold_inode_fault(s);\n    return status;",
                                   "    npu_cold_inode_fault(s);\n    if (s) s->committed = s->published;\n    return status;")}
    sources = [CORE / (n + ".c") for n in
        ("cold-rx-pcie", "cold-txdone", "cold-rx-event", "cold-tx-buffer", "cold-packet", "cold-tx")]
    sources += [CORE / "cold-pcie-tail.c"]
    fixtures = [TESTS / name for name in ("cold-txdone-fixture.c", "cold-rx-pcie-fixture.c",
                "cold-pcie-tail-fixture.c", "cold-inode-fixture.c")]
    sanitizer_source = TESTS / "cold-inode-sanitize.c"
    paths = [*sources, *fixtures, source_path, Path(owner.__file__), Path(owner.tail.__file__),
             Path(__file__), sanitizer_source, *CORE.glob("*.h"), baseline]
    inputs = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    command = [shutil.which("clang"), "-std=c11", "-Wall", "-Wextra", "-Werror",
               "-I" + str(CORE), "-I" + str(TESTS)]
    run = owner.tail.pcie.done.tx.loader.run
    sanitizer = dest / "sanitize"
    build = command + ["-O1", "-g", "-fno-omit-frame-pointer", "-fsanitize=address,undefined",
                        *sources, source_path, *fixtures, sanitizer_source, "-o", sanitizer]
    run(build, dest / "sanitize-build.log")
    environment = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1")
    completed = subprocess.run([str(sanitizer)], env=environment, text=True, capture_output=True, timeout=120)
    (dest / "sanitize-run.log").write_text(completed.stdout + completed.stderr)
    assert completed.returncode == 0, completed.stderr
    print(json.dumps({"sanitizer": True, "address": True, "undefined": True, "leak": True}), flush=True)
    results = []
    for name, (before, after) in mutants.items():
        assert source.count(before) == (2 if name == "unfinished-pcie-tail" else 1), name
        path, shared = dest / (name + ".c"), dest / (name + ".so")
        path.write_text(source.replace(before, after))
        run(command + ["-O2", "-shared", "-fPIC", *sources, path, *fixtures, "-o", shared], dest / (name + "-build.log"))
        pair = owner.Pair(shared, baseline, False)
        try:
            owner.exercise(pair)
        except AssertionError as error:
            result = {"name": name, "compiled": True, "killed": True, "assertion": repr(error),
                      "calls_before_detection": pair.calls, "source_sha256": sha(path), "binary_sha256": sha(shared)}
            results.append(result)
            print(json.dumps(result), flush=True)
        else:
            raise AssertionError(("surviving-mutant", name))
    assert all(sha(ROOT / n) == h for n, h in inputs.items())
    record = {"passed": True, "mutants": results, "inputs": inputs,
              "sanitizer": {"exit_code": 0, "address": True, "undefined": True, "leak": True,
                            "binary_sha256": sha(sanitizer)}, "scope": "compiled host faults, not native admission"}
    (dest / "result.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
