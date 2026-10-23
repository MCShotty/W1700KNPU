#!/usr/bin/env python3
"""Source-bound host C reset-retention regression, with modeled boundaries only.

The selected candidate helper is compiled after removing only its #include
lines. The lower abort/IRQ fault bodies and the complete WED work body are
compiled from the supplied source root. This does not admit checked selector 3,
authenticate BA generations, execute kernel concurrency, or prove DMA drain.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess

from test_host_queue_publication import function, macro
from test_rro_reset_ba_events import structure


ROOT = Path(__file__).resolve().parents[2]
BASE_MT76 = ROOT / ".local/merge-nonoc-20260923/mt76-merged"
OUTPUT = ROOT / ".local/npu-rro-reset-retention-20261023"
HARNESS = Path(__file__).with_name("rro-reset-retention-harness.c")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paired(source_root, relative):
    candidate = source_root / relative
    return candidate if candidate.is_file() else BASE_MT76 / relative


def replace_once(source, old, new, name):
    assert source.count(old) == 1, ("mutation anchor", name, source.count(old))
    return source.replace(old, new, 1)


def no_core_dump():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def compile_and_run(directory, compiler, case=None):
    binary = directory / "rro-reset-retention"
    command = [compiler, "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra",
               "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
               "-fno-omit-frame-pointer", str(directory / HARNESS.name),
               "-o", str(binary)]
    built = subprocess.run(command, cwd=directory, capture_output=True,
                           text=True, timeout=120)
    (directory / "compile.log").open("x").write(built.stdout + built.stderr)
    assert built.returncode == 0, ("compile", directory.name, built.stderr)

    environment = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    invocation = [str(binary)] + ([case] if case else [])
    executed = subprocess.run(invocation, cwd=directory, env=environment,
                              capture_output=True, text=True, timeout=120,
                              preexec_fn=no_core_dump)
    (directory / "run.stdout").open("x").write(executed.stdout)
    (directory / "run.stderr").open("x").write(executed.stderr)
    return command, invocation, binary, executed


def selected_sources(source_root):
    paths = {
        "helper": source_root / "mt7996/npu-rro-reset.c",
        "npu": source_root / "npu.c",
        "worker": source_root / "mt7996/init.c",
        "reset_callers": source_root / "mt7996/mac.c",
        "event_parser": source_root / "mt7996/mcu.c",
        "kbuild": source_root / "mt7996/Makefile",
        "mt7996_header": paired(source_root, "mt7996/mt7996.h"),
        "mt76_header": paired(source_root, "mt76.h"),
        "harness": HARNESS,
        "runner": Path(__file__),
        "extract_function": ROOT / "tests/npu/test_host_queue_publication.py",
        "extract_structure": ROOT / "tests/npu/test_rro_reset_ba_events.py",
    }
    assert all(path.is_file() for path in paths.values()), "missing candidate or paired header"
    source = {name: path.read_text() for name, path in paths.items()}
    for text, name in ((source["worker"], "mt7996_unregister_device"),
                       (source["reset_callers"], "mt7996_mac_full_reset"),
                       (source["reset_callers"], "mt7996_mac_reset_work")):
        body = function(text, name)
        hooks = ("mt7996_npu_rro_reset_close(dev);",
                 "cancel_work_sync(&dev->wed_rro.work);",
                 "mt7996_npu_rro_reset_join(dev);")
        assert all(body.count(hook) == 1 for hook in hooks), name
        positions = [body.index(hook) for hook in hooks]
        assert positions == sorted(positions), ("close-cancel-join", name)
    body = function(source["worker"], "mt7996_wed_rro_free")
    assert body.index("mt7996_npu_rro_reset_close(dev);") < body.index(
        "mt76_npu_rro_close(&dev->mt76);") < body.index("dmam_free_coherent(")
    body = function(source["worker"], "mt7996_wed_rro_init")
    assert body.index("dev->npu_rro_owned = true;") < body.index(
        "mt7996_npu_rro_reset_init(dev)") < body.index("mt7996_wed_rro_alloc(")
    assert "ret = mt7996_npu_rro_reset_init(dev);\n\t\t\tif (ret)\n\t\t\t\treturn ret;" in body
    assert source["event_parser"].index("mt7996_npu_rro_reset_enqueue(dev,") < \
        source["event_parser"].index("session = kzalloc(sizeof(*session), GFP_ATOMIC);")
    assert "mt7996e-$(CONFIG_MT7996_NPU) += npu.o npu-rro-reset.o" in source["kbuild"]
    helper = re.sub(r"(?m)^[ \t]*#include[^\n]*(?:\n|$)", "", source["helper"])
    assert "#include" not in helper, "unexpected helper include"

    npu = "\n\n".join(function(source["npu"], name) for name in
                       ("mt76_npu_irq_fault_locked", "mt76_npu_rro_abort"))
    worker = function(source["worker"], "mt7996_wed_rro_work")
    h7996 = source["mt7996_header"]
    h76 = source["mt76_header"]
    selected_types = "\n".join(macro(h7996, name) for name in (
        "MT7996_RRO_MAX_SESSION", "MT7996_RRO_WINDOW_MAX_LEN",
        "MT7996_RRO_ADDR_ELEM_LEN", "MT7996_RRO_BA_BITMAP_SESSION_SIZE",
        "WED_RRO_ADDR_SIGNATURE_MASK"))
    selected_types += "\n\n" + "\n\n".join((
        structure(h76, "mt76_npu_irq"),
        structure(h7996, "mt7996_wed_rro_addr"),
        structure(h7996, "mt7996_wed_rro_session_id")))
    selected = {
        "selected-types.inc": selected_types + "\n",
        "selected-npu.inc": npu + "\n",
        "selected-helper.inc": helper,
        "selected-worker.inc": worker + "\n",
    }
    return paths, selected


MUTATIONS = (
    ("ignored-typed-mcu-begin-error", "selected-helper.inc",
     "\t\trecord->bridge_error = result;\n\t\tif (result) {",
     "\t\trecord->bridge_error = result;\n\t\tif (false) {",
     "typed", "typed-begin-error-blocks-physical-MCU"),
    ("missing-typed-begin-close-recheck", "selected-helper.inc",
     "\t\tif (owner->closing || owner->error)\n\t\t\tgoto retain;\n\t\t/* Close may join",
     "\t\tif (false)\n\t\t\tgoto retain;\n\t\t/* Close may join",
     "typed", "close-during-typed-begin-does-not-admit-physical-MCU"),
    ("missed-npu-failure", "selected-helper.inc",
     "\t\trecord->npu_error = result;\n\t\tif (result) {",
     "\t\trecord->npu_error = result;\n\t\tif (false) {",
     "npu", "npu-error-blocks-mcu"),
    ("queue-after-close", "selected-helper.inc",
     "\tqueue = !owner->closing;", "\tqueue = true;",
     "queue", "queue-after-close"),
    ("missing-module-pin", "selected-helper.inc",
     "\tif (!try_module_get(THIS_MODULE)) {",
     "\tif (false) {", "pin", "module-pin-retained"),
    ("omitted-irq-quarantine", "selected-npu.inc",
     "\terr = mt76_npu_irq_fault_locked(dev, npu, error);",
     "\terr = error;", "irq", "irq-quarantine-on-abort"),
    ("missed-construction-error", "selected-helper.inc",
     "\t\terr = READ_ONCE(dev->recovery.npu_error);", "\t\terr = 0;",
     "construction", "constructor-latches-missing-owner-error"),
    ("missed-publication-recheck", "selected-helper.inc",
     "\t\tspin_lock_bh(&dev->wed_rro.lock);\n\t\towner = smp_load_acquire(&dev->wed_rro.reset_owner);",
     "\t\tspin_lock_bh(&dev->wed_rro.lock);\n\t\towner = NULL;",
     "publication", "publication-recheck-retains-arrival"),
)


def run(destination, source_root, mutants):
    source_root = source_root.resolve(strict=True)
    paths, selected = selected_sources(source_root)
    inputs = {str(path.resolve()): sha(path) for path in paths.values()}
    with (destination / "inputs.json").open("x") as stream:
        json.dump({"source_root": str(source_root), "sha256": inputs},
                  stream, indent=2)
        stream.write("\n")
    for name, content in selected.items():
        (destination / name).open("x").write(content)
    shutil.copyfile(HARNESS, destination / HARNESS.name)

    compiler = shutil.which("clang") or shutil.which("gcc")
    assert compiler, "no host C compiler"
    command, invocation, binary, executed = compile_and_run(destination, compiler)
    assert executed.returncode == 0, ("baseline", executed.returncode,
                                      executed.stderr)
    rows = [json.loads(line) for line in executed.stdout.splitlines() if line.strip()]
    assert len(rows) == 1 and rows[0] == {
        "passed": True, "host_model_only": True, "cases": 23,
    }, rows

    controls = []
    if mutants:
        for name, target, old, new, case, expected in MUTATIONS:
            child = destination / name
            child.mkdir(exist_ok=False)
            for filename, content in selected.items():
                if filename == target:
                    content = replace_once(content, old, new, name)
                (child / filename).open("x").write(content)
            shutil.copyfile(HARNESS, child / HARNESS.name)
            variant_command, variant_invocation, variant_binary, rejected = (
                compile_and_run(child, compiler, case))
            assert rejected.returncode == -signal.SIGABRT, (
                "control did not assert", name, rejected.returncode,
                rejected.stderr)
            assert expected in rejected.stderr, (
                "wrong assertion", name, rejected.stderr)
            assert "AddressSanitizer" not in rejected.stderr and \
                   "runtime error:" not in rejected.stderr, (
                       "sanitizer failure rather than intended assertion",
                       name, rejected.stderr)
            controls.append({
                "name": name, "target_case": case, "assertion": expected,
                "returncode": rejected.returncode,
                "source_sha256": sha(child / target),
                "binary_sha256": sha(variant_binary),
                "compile_command": variant_command,
                "invocation": variant_invocation,
            })

    assert all(sha(Path(path)) == value for path, value in inputs.items()), "input drift"
    artifacts = {str(path.relative_to(destination)): sha(path)
                 for path in sorted(destination.rglob("*")) if path.is_file()}
    return {
        "passed": True, "cases": rows[0]["cases"],
        "source_root": str(source_root),
        "paired_headers": {name: str(paths[name]) for name in
                           ("mt7996_header", "mt76_header")},
        "inputs_sha256": inputs,
        "selected_sha256": {name: hashlib.sha256(text.encode()).hexdigest()
                            for name, text in selected.items()},
        "artifacts_sha256": artifacts,
        "binary_sha256": sha(binary),
        "compile_command": command,
        "invocation": invocation,
        "mutation_controls": controls,
        "sanitizers": ["ASan", "UBSan", "leak-detection"],
        "structural_hooks": ["unregister close-cancel-join",
                             "full reset close-cancel-join", "L1 reset close-cancel-join",
                             "owned free closes before provider and managed frees",
                             "owner initialization precedes RRO extent allocation",
                             "owned DELETE precedes legacy allocation", "CONFIG object linkage"],
        "modeled_boundaries": [
            "prior BA status enrollment with synthetic creation serials",
            "owner allocation and constructor failure", "endpoint/device reference",
            "module reference", "spinlocks and mutex", "RCU-protected provider lookup",
            "IRQ disable and NPU mask", "work queue admission and cancellation",
            "typed reset generation/ticket provider operations", "MCU reset command", "consumer release",
        ],
        "limits": [
            "Selected actual C bodies run against single-threaded host models.",
            "Prior BA enrollment is explicitly modeled here; the separate BA-owner fixture executes actual RX creation/status/DELETE jointly.",
            "Modeled NPU success is not checked-provider legacy selector 3 admission.",
            "MCU ACK is not a BA-generation or physical DMA-drain witness.",
            "Only the fixture performs final owner disposal after retention checks; production has no retirement authority.",
            "No kernel, firmware, device, hardware, or live service execution.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path,
                        help="candidate mt76-merged tree")
    parser.add_argument("--name", required=True)
    parser.add_argument("--mutants", action=argparse.BooleanOptionalAction,
                        default=True, help="compile eight targeted mutation controls")
    args = parser.parse_args()
    assert re.fullmatch(r"[a-z][a-z0-9-]{0,39}", args.name), "invalid receipt name"
    destination = OUTPUT / args.name
    destination.mkdir(parents=True, exist_ok=False)
    try:
        result = run(destination, args.source_root, args.mutants)
    except BaseException as exc:
        (destination / "failure.json").open("x").write(json.dumps({
            "passed": False, "error_type": type(exc).__name__, "error": str(exc),
        }, indent=2) + "\n")
        raise
    with (destination / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({
        "passed": True, "cases": result["cases"],
        "controls": len(result["mutation_controls"]),
        "receipt": str(destination / "result.json"),
        "sha256": sha(destination / "result.json"),
    }), flush=True)


if __name__ == "__main__":
    main()
