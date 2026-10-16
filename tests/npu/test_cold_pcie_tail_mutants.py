#!/usr/bin/env python3
"""Compile each deliberate owner fault and require a behavioral test failure."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
import test_cold_pcie_tail as owner

HERE, ROOT, CORE, TESTS = owner.HERE, owner.ROOT, owner.CORE, owner.TESTS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    assert args.name.replace("-", "").isalnum()
    dest = ROOT / ".local/npu-pcie-tail-owner" / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    baseline = args.baseline.resolve()
    source_path = CORE / "cold-pcie-tail.c"
    source = source_path.read_text()
    mutations = {
        "stage-live-active": ("!s->active && s->stage == stage;", "s->stage == stage;"),
        "stage-live-wrong-stage": ("!s->active && s->stage == stage;", "!s->active && stage < 3;"),
        "prior-reader-change": (
            "equal(c->pcie, &held_pcie, sizeof(held_pcie)) &&",
            "1 &&"),
        "unfinished-tx": ("tx->active || tx->stage != 2 ||", "tx->stage != 2 ||"),
        "wrong-store-value": (
            "address != store.address || bytes != store.bytes || value != store.value ||",
            "address != store.address || bytes != store.bytes || ((void)value, 0) ||"),
        "forget-possible-effect": (
            "    npu_cold_pcie_tail_fault(s);\n    return status;",
            "    npu_cold_pcie_tail_fault(s);\n    if (s) s->committed = s->published;\n    return status;"),
        "wrong-hif2-register": ("p->tx.host2 + 0x110u : 0;", "p->tx.host2 + 0x10u : 0;"),
        "count-underflow": ("{255, 511, 1023, 1535, 511}", "{255, 511, 1023, 1535, UINT32_MAX}"),
        "premature-finish": (
            "if (!context(s, p, epoch, c) || !s->active ||\n        s->committed != end(s->stage) || s->published != s->committed)",
            "if (!context(s, p, epoch, c) || !s->active)")}
    sources = [CORE / (name + ".c") for name in
        ("cold-rx-pcie", "cold-txdone", "cold-rx-event", "cold-tx-buffer", "cold-packet", "cold-tx")]
    fixtures = [TESTS / name for name in
                ("cold-txdone-fixture.c", "cold-rx-pcie-fixture.c", "cold-pcie-tail-fixture.c")]
    sanitizer_source = TESTS / "cold-pcie-tail-sanitize.c"
    inputs = [source_path, Path(owner.__file__), Path(__file__), baseline, sanitizer_source,
              *sources, *fixtures, *CORE.glob("*.h")]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    command = [shutil.which("clang"), "-std=c11", "-Wall", "-Wextra", "-Werror",
               "-I" + str(CORE), "-I" + str(TESTS)]
    sanitizer = dest / "sanitize"
    owner.pcie.done.tx.loader.run(command + ["-O1", "-g", "-fno-omit-frame-pointer",
        "-fsanitize=address,undefined", *sources, source_path, *fixtures, sanitizer_source,
        "-o", sanitizer], dest / "sanitize-build.log")
    completed = subprocess.run([str(sanitizer)], text=True, capture_output=True, timeout=120,
        env=dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))
    (dest / "sanitize-run.log").write_text(completed.stdout + completed.stderr)
    assert completed.returncode == 0, completed.stderr
    results = []
    for name, (before, after) in mutations.items():
        assert source.count(before) == 1, name
        mutant = dest / (name + ".c")
        mutant.write_text(source.replace(before, after))
        shared = dest / (name + ".so")
        owner.pcie.done.tx.loader.run(command + ["-O2", "-shared", "-fPIC", *sources,
            *fixtures, mutant, "-o", shared], dest / (name + "-build.log"))
        pair = owner.Pair(shared, baseline, False)
        try:
            owner.exercise(pair, exhaustive=True)
        except AssertionError as error:
            result = {"name": name, "compiled": True, "killed": True,
                      "assertion": repr(error), "calls_before_detection": pair.calls,
                      "source_sha256": hashlib.sha256(mutant.read_bytes()).hexdigest(),
                      "binary_sha256": hashlib.sha256(shared.read_bytes()).hexdigest()}
            results.append(result)
            print(json.dumps(result), flush=True)
        else:
            raise AssertionError(("surviving-mutant", name))
    assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    (dest / "result.json").write_text(json.dumps({"passed": True, "mutants": results,
        "inputs": hashes, "sanitizer": {"exit_code": 0, "address": True, "undefined": True,
        "leak": True, "binary_sha256": hashlib.sha256(sanitizer.read_bytes()).hexdigest()},
        "scope": "compiled host-C faults; no original instructions/hardware"}, indent=2) + "\n")


if __name__ == "__main__":
    main()
