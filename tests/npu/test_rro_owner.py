#!/usr/bin/env python3
"""Full-geometry RRO ownership journal; no operational or physical admission."""
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

import test_host_queue_publication as q

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'firmware/npu'
MT76_HEADER = ROOT / '.local/merge-nonoc-20260923/mt76-merged/mt7996/mt7996.h'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def no_core_dump():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def mutation_controls(destination, command, environment):
    original = (destination / 'rro-lifetime.c').read_text()
    variants = (
        ('missing-publication-latch', '    s->exposure[slot] |= NPU_RRO_NPU_POSSIBLE;\n',
         'publication exposure must precede command output'),
        ('wrong-reset-ticket', 's->resets[session].ticket == ticket && ',
         'reset completion requires exact transport ticket'),
        ('missing-retirement-join', '    if (!s->cpu_joined)\n        return NPU_RRO_ORDER;\n',
         'retirement observations require CPU join'),
    )
    controls = []
    for name, removed, diagnostic in variants:
        assert original.count(removed) == 1, ('mutant-anchor', name)
        directory = destination / name
        directory.mkdir()
        source = directory / 'rro-lifetime.c'
        source.write_text(original.replace(removed, '', 1))
        binary = directory / 'rro-owner'
        replacements = {str(destination / source.name): str(source),
                        str(destination / binary.name): str(binary)}
        compile_command = [replacements.get(argument, argument) for argument in command]
        compiled = subprocess.run(compile_command, capture_output=True, text=True, timeout=120)
        (directory / 'compile.log').write_text(compiled.stdout + compiled.stderr)
        assert compiled.returncode == 0, ('mutant-must-compile', name, compiled.stderr)
        completed = subprocess.run([str(binary), str(directory / 'frames.bin')], env=environment,
            capture_output=True, text=True, timeout=300, preexec_fn=no_core_dump)
        (directory / 'run.jsonl').write_text(completed.stdout)
        (directory / 'run.stderr').write_text(completed.stderr)
        assert completed.returncode == -signal.SIGABRT, ('mutant-not-assertion-rejected', name, completed.returncode)
        assert diagnostic in completed.stderr, ('mutant-wrong-assertion', name, completed.stderr)
        assert 'ERROR: AddressSanitizer' not in completed.stderr and 'runtime error:' not in completed.stderr
        controls.append(dict(name=name, compiled=True, compile_returncode=compiled.returncode,
            run_returncode=completed.returncode, intended_assertion=diagnostic,
            assertion_rejected=True, sanitizer_fault=False, source_sha256=sha(source)))
    return controls


def run(destination):
    paths = [Path(__file__), Path(__file__).with_name('rro-owner-harness.c'), Path(q.__file__), MT76_HEADER]
    paths += list(SOURCE.glob('*.h')) + [SOURCE / 'rro-lifetime.c']
    inputs = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    header = MT76_HEADER.read_text()
    macros = ('MT7996_RRO_MAX_SESSION', 'MT7996_RRO_WINDOW_MAX_LEN', 'MT7996_RRO_ADDR_ELEM_LEN',
        'MT7996_RRO_BA_BITMAP_LEN', 'MT7996_RRO_BA_BITMAP_CR_SIZE', 'MT7996_RRO_BA_BITMAP_SESSION_SIZE',
        'MT7996_RRO_WINDOW_MAX_SIZE', 'MT7996_RRO_MSDU_PG_CR_CNT',
        'MT7996_RRO_MSDU_PG_SIZE_PER_CR', 'MT7996_MAX_RRO_RRS_RING')
    geometry = 'typedef uint32_t __le32;\ntypedef uint16_t __le16;\n'
    geometry += '\n'.join(q.macro(header, name) for name in macros) + '\n'
    geometry += '\n'.join(q.declaration(header, 'struct', name) for name in
        ('mt7996_wed_rro_addr', 'mt7996_rro_queue_regs_emi')) + '\n'
    with (destination / 'rro-source-geometry.h').open('x') as stream:
        stream.write(geometry)
    harness = paths[1]
    shutil.copyfile(harness, destination / harness.name)
    shutil.copyfile(__file__, destination / 'driver-at-run.py')
    for name in ('rro-lifetime.c', 'rro-lifetime.h'):
        shutil.copyfile(SOURCE / name, destination / name)
    command = [shutil.which('clang'), '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I', str(SOURCE), '-I', str(destination),
        str(destination / 'rro-lifetime.c'), str(destination / harness.name), '-o', str(destination / 'rro-owner')]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=120)
    (destination / 'compile.log').write_text(compiled.stdout + compiled.stderr)
    assert compiled.returncode == 0, compiled.stderr
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    completed = subprocess.run([str(destination / 'rro-owner'), str(destination / 'frames.bin')],
        env=environment, capture_output=True, text=True, timeout=300)
    (destination / 'run.jsonl').write_text(completed.stdout)
    (destination / 'run.stderr').write_text(completed.stderr)
    assert completed.returncode == 0, (completed.returncode, completed.stderr)
    rows = [json.loads(line) for line in completed.stdout.splitlines()]
    assert rows[-1]['passed'] and rows[-1]['captured_frames'] == 134
    assert sum(row['cases'] for row in rows[:-1]) == rows[-1]['total_cases']
    assert len(rows) == 23 and rows[-1]['total_cases'] == 5279
    for profile in range(3):
        group = {row['group']: row for row in rows[:-1] if row['profile'] == profile}
        assert group['every-allocation-prefix']['cases'] == (138 if profile == 2 else 140)
        assert group['every-ambiguous-publication-prefix']['cases'] == 129 * 2 * 2
        assert group['every-session-reset-generation-and-duplicates']['cases'] == 1026
        assert group['single-NPU-and-MCU-inflight-credit']['cases'] == 1
        assert group['reset-NPU-MCU-errors-late-and-retirement']['cases'] == 40
        assert group['every-retirement-domain-subset-retains-extents']['cases'] == 32
    previous = ROOT / '.local/npu-rro-lifetime-callers/teardown-q2/caller-payloads.bin'
    assert (destination / 'frames.bin').read_bytes() == previous.read_bytes()
    inputs[str(previous.relative_to(ROOT))] = sha(previous)
    controls = mutation_controls(destination, command, environment)
    assert all(sha(ROOT / name) == value for name, value in inputs.items()), 'source-input-drift'
    artifacts = {str(path.relative_to(ROOT)): sha(path) for path in destination.rglob('*') if path.is_file()}
    return dict(passed=True, software_journal_only=True, cases=rows[-1]['total_cases'], groups=rows[:-1],
        captured_frames=134, captured_actual_caller_bytes_match=True, inputs=inputs, artifacts=artifacts,
        mutation_controls=controls,
        sanitizers=['ASan', 'UBSan', 'leak-detection'], compile_command=command,
        operational_RRO_admitted=False, provider_native_wiring_complete=False,
        retirement_authority=False, hardware=False, full_npu_goal_complete=False,
        limits=['Full current mt7996 geometry is compiled from the selected source header.',
            'CPU/device identities and DMA addresses are synthetic metadata, not actual pinned resources.',
            'Reset generations and exact transport tickets must be supplied by real integration.',
            'A near-exhaustion state is injected for the counter-boundary test, not executed billions of times.',
            'Every retirement domain subset retains the full allocation metadata and grants no free authority.',
            'The journal does not perform transport, reference acquisition, IRQ/DMA exclusion or physical retirement.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    destination = ROOT / '.local/npu-rro-owner-20261023' / args.name
    destination.mkdir(parents=True, exist_ok=False)
    result = run(destination)
    with (destination / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, cases=result['cases'], frames=134,
        receipt=str((destination / 'result.json').relative_to(ROOT)), sha256=sha(destination / 'result.json'))), flush=True)


if __name__ == '__main__':
    main()
