#!/usr/bin/env python3
"""Candidate host BA event checks. No kernel, firmware, or hardware execution.

Pass --source-root as the candidate mt76-merged tree containing mt7996/{main.c,
mcu.c,mt7996.h}. The unchanged wire headers are read from that tree when present,
otherwise from the paired canonical merge tree. All generated files and receipts
stay under .local/npu-rro-reset-ba-events-20261023/<name>/.
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


ROOT = Path(__file__).resolve().parents[2]
BASE_MT76 = ROOT / ".local/merge-nonoc-20260923/mt76-merged"
OUTPUT = ROOT / ".local/npu-rro-reset-ba-events-20261023"
HERE = Path(__file__).resolve().parent
HARNESS = HERE / "rro-reset-ba-harness.c"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def masked(source):
    pattern = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)
    return pattern.sub(lambda match: ''.join('\n' if char == '\n' else ' '
                                              for char in match.group()), source)


def braced(source, start, needs_semicolon):
    view = masked(source)
    opening = view.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        assert end < len(view), "unclosed C declaration"
        depth += (view[end] == '{') - (view[end] == '}')
        end += 1
    if needs_semicolon:
        tail = re.match(r'\s*(?:__packed\s*)?;', view[end:])
        assert tail, "missing declaration terminator"
        end += tail.end()
    return source[start:end]


def function(source, name):
    view = masked(source)
    pattern = re.compile(r'(?m)^static\s+(?:int|void)\s+' + re.escape(name) +
                         r'\s*\([^;{}]*\)\s*\{')
    matches = list(pattern.finditer(view))
    assert len(matches) == 1, (name, len(matches))
    return braced(source, matches[0].start(), False)


def structure(source, name):
    view = masked(source)
    pattern = re.compile(r'(?m)^struct\s+' + re.escape(name) + r'\s*\{')
    matches = list(pattern.finditer(view))
    assert len(matches) == 1, (name, len(matches))
    return braced(source, matches[0].start(), True)


def event_enum(source):
    view = masked(source)
    pattern = re.compile(r'(?m)^enum\s*\{\s*UNI_WED_RRO_BA_SESSION_STATUS\b')
    matches = list(pattern.finditer(view))
    assert len(matches) == 1, ("RRO event enum", len(matches))
    return braced(source, matches[0].start(), True)


def once(source, old, new, label):
    assert source.count(old) == 1, ("mutation anchor", label, source.count(old))
    return source.replace(old, new, 1)


def no_core_dump():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def compile_and_run(directory, compiler, environment):
    binary = directory / "rro-ba-events"
    command = [compiler, "-std=gnu11", "-O1", "-g", "-Wall", "-Wextra",
               "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
               "-fno-omit-frame-pointer", str(directory / HARNESS.name),
               "-o", str(binary)]
    built = subprocess.run(command, cwd=directory, capture_output=True,
                           text=True, timeout=120)
    (directory / "compile.log").write_text(built.stdout + built.stderr)
    assert built.returncode == 0, ("compile", directory.name, built.stderr)
    executed = subprocess.run([str(binary)], cwd=directory, env=environment,
                              capture_output=True, text=True, timeout=120,
                              preexec_fn=no_core_dump)
    (directory / "run.stdout").write_text(executed.stdout)
    (directory / "run.stderr").write_text(executed.stderr)
    return command, binary, executed


def run(destination, source_root):
    source_root = source_root.resolve(strict=True)
    candidate = source_root / "mt7996"
    main = candidate / "main.c"
    if not main.is_file():
        main = BASE_MT76 / "mt7996/main.c"
    mcu = candidate / "mcu.c"
    header = candidate / "mt7996.h"
    wire = candidate / "mcu.h"
    tlv_header = source_root / "mt76_connac_mcu.h"
    if not wire.is_file():
        wire = BASE_MT76 / "mt7996/mcu.h"
    if not tlv_header.is_file():
        tlv_header = BASE_MT76 / "mt76_connac_mcu.h"
    paths = [main, mcu, header, wire, tlv_header, HARNESS, Path(__file__)]
    assert all(path.is_file() for path in paths), "missing candidate or paired wire source"
    inputs = {str(path.resolve()): sha(path) for path in paths}

    main_body = function(main.read_text(), "mt7996_ampdu_action")
    mcu_body = function(mcu.read_text(), "mt7996_mcu_wed_rro_event")
    wire_text = wire.read_text()
    struct_names = ("mt7996_mcu_rxd", "mt7996_mcu_wed_rro_event",
                    "mt7996_mcu_wed_rro_ba_event",
                    "mt7996_mcu_wed_rro_ba_delete_event")
    structs = [structure(wire_text, name) for name in struct_names]
    structs.append(structure(tlv_header.read_text(), "tlv"))
    structs.append(event_enum(wire_text))
    structs.append(structure(header.read_text(), "mt7996_wed_rro_session_id"))
    selected = {"selected-structs.inc": "\n\n".join(structs) + "\n",
                "selected-main.inc": main_body + "\n",
                "selected-mcu.inc": mcu_body + "\n"}
    for name, content in selected.items():
        with (destination / name).open("x") as stream:
            stream.write(content)
    shutil.copyfile(HARNESS, destination / HARNESS.name)

    compiler = shutil.which("clang") or shutil.which("gcc")
    assert compiler, "no C compiler found"
    environment = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    command, binary, executed = compile_and_run(destination, compiler, environment)
    assert executed.returncode == 0, ("host harness", executed.returncode,
                                      executed.stderr)
    rows = [json.loads(line) for line in executed.stdout.splitlines() if line.strip()]
    assert len(rows) == 1 and rows[0] == {
        "passed": True, "host_model_only": True, "cases": 15,
    }, rows

    mutations = (
        ("missing-host-allocation-guard", "selected-main.inc",
         "\t\tif (ret)\n\t\t\tbreak;\n", "",
         "no-mcu-on-host-allocation-failure"),
        ("lost-delete-tid", "selected-mcu.inc",
         "session->tid = e->tid;", "session->tid = 0;",
         "queued-wlan-tid-from-event"),
        ("missing-status-rcu", "selected-mcu.inc",
         "\t\t\trcu_read_lock();\n", "",
         "wcid-lookup-without-RCU"),
    )
    controls = []
    for name, target, old, replacement, assertion in mutations:
        child = destination / name
        child.mkdir(exist_ok=False)
        for filename, content in selected.items():
            if filename == target:
                content = once(content, old, replacement, name)
            (child / filename).write_text(content)
        shutil.copyfile(HARNESS, child / HARNESS.name)
        variant_command, variant_binary, rejected = compile_and_run(
            child, compiler, environment)
        assert rejected.returncode == -signal.SIGABRT, (
            "control did not assert", name, rejected.returncode, rejected.stderr)
        assert assertion in rejected.stderr, (
            "wrong assertion", name, rejected.stderr)
        assert "AddressSanitizer" not in rejected.stderr and "runtime error:" not in rejected.stderr, (
            "sanitizer fault instead of intended assertion", name, rejected.stderr)
        controls.append({"name": name, "compiled": True, "reached_assertion": assertion,
                         "returncode": rejected.returncode,
                         "source_sha256": sha(child / target),
                         "binary_sha256": sha(variant_binary),
                         "compile_command": variant_command})

    assert all(sha(Path(path)) == value for path, value in inputs.items()), "input drift"
    artifacts = {str(path.relative_to(destination)): sha(path)
                 for path in sorted(destination.rglob("*")) if path.is_file()}
    return {"passed": True, "cases": rows[0]["cases"],
            "source_root": str(source_root), "wire_header": str(wire),
            "inputs_sha256": inputs,
            "extracted_sha256": {name: hashlib.sha256(content.encode()).hexdigest()
                                 for name, content in selected.items()},
            "artifacts_sha256": artifacts, "binary_sha256": sha(binary),
            "compile_command": command, "mutation_controls": controls,
            "sanitizers": ["ASan", "UBSan", "leak-detection"],
            "modeled_boundaries": ["skb linearization", "allocator failure",
                                   "RCU read sections", "queue lock/work",
                                   "host BA allocation", "MCU BA calls"],
            "limits": ["Extracted selected C bodies and wire/queue structs execute in a host fixture.",
                       "The unchanged wire headers are paired with the supplied candidate tree.",
                       "No kernel concurrency, firmware, device, hardware, DMA, or lifetime authentication.",
                       "No MCU-failure rollback or RRO generation/epoch guarantee is inferred."]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    assert re.fullmatch(r"[a-z][a-z0-9-]{0,39}", args.name), "invalid receipt name"
    destination = OUTPUT / args.name
    destination.mkdir(parents=True, exist_ok=False)
    try:
        result = run(destination, args.source_root)
    except BaseException as exc:
        (destination / "failure.json").write_text(json.dumps({
            "passed": False, "error_type": type(exc).__name__, "error": str(exc),
        }, indent=2) + "\n")
        raise
    with (destination / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"passed": True, "cases": result["cases"],
                      "controls": len(result["mutation_controls"]),
                      "receipt": str(destination / "result.json"),
                      "sha256": sha(destination / "result.json")}), flush=True)


if __name__ == "__main__":
    main()
