#!/usr/bin/env python3
"""Host C client/codec/broker/journal/native integration; no physical execution."""

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
SOURCE = ROOT / 'firmware/npu'
HARNESS = ROOT / 'tests/npu/rro-session-harness.c'
FIXTURE = ROOT / 'tests/npu/rro-native-fixture.h'
OUTPUT = ROOT / '.local/npu-rro-session-host-20261023'
PRODUCTION = (
    'admission.c', 'barrier.c', 'bootstrap.c', 'bootstrap-v2.c',
    'control-client.c', 'control-v2-client.c', 'control-v2.c',
    'cold-tx-buffer.c', 'rro-lifetime.c', 'rro-native.c',
    'rro-wire.c', 'rro-client.c', 'rro-session.c',
)


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def no_core_dump():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def invoke(command, log, environment=None, timeout=300):
    completed = subprocess.run([str(part) for part in command], capture_output=True,
        text=True, timeout=timeout, env=environment, preexec_fn=no_core_dump)
    log.write_text(completed.stdout + completed.stderr)
    return completed


def compiler_command(clang, binary, replacements=None):
    replacements = replacements or {}
    sources = [replacements.get(name, SOURCE / name) for name in PRODUCTION]
    return [clang, '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
        '-fno-omit-frame-pointer', '-I', SOURCE, '-I', HARNESS.parent,
        *sources, HARNESS, '-o', binary]


def mutation_controls(destination, clang, environment):
    variants = (
        ('high-identity', 'rro-session.c',
         'sizeof(struct npu_rro_identity) + 4', '4',
         'adversarial reply must preserve exact request and expected status'),
        ('bad-ticket', 'rro-session.c',
         'm->ticket != s->owner.last_ticket + 1', '0',
         'unexpected native I/O'),
        ('bad-mailbox', 'rro-session.c',
         '!plan_matches(&message.plan, boot, cold)', '0',
         'adversarial reply must preserve exact request and expected status'),
        ('client-identity', 'rro-client.c',
         '!parked(s) || !identity(s, message) ||', '!parked(s) || 0 ||',
         'client identity rejection leaves separate packet unchanged'),
        ('reply-echo', 'rro-client.c',
         '!npu_rro_wire_echo(request, reply, bytes)', '0',
         'client echo must reject corrupted but parseable reply'),
    )
    controls = []
    for name, filename, before, after, diagnostic in variants:
        directory = destination / name
        directory.mkdir()
        original = (SOURCE / filename).read_text()
        assert original.count(before) == 1, ('mutation anchor drift', name)
        mutant = directory / filename
        mutant.write_text(original.replace(before, after, 1))
        binary = directory / 'rro-session'
        command = compiler_command(clang, binary, {filename: mutant})
        built = invoke(command, directory / 'build.log', timeout=300)
        assert built.returncode == 0, (name, built.returncode, built.stderr[-6000:])
        ran = invoke([binary, name], directory / 'run.log', environment, timeout=900)
        assert ran.returncode == -signal.SIGABRT, (name, ran.returncode, ran.stderr[-6000:])
        assert diagnostic in ran.stderr, (name, ran.stderr[-6000:])
        assert 'ERROR: AddressSanitizer' not in ran.stderr and 'runtime error:' not in ran.stderr
        controls.append(dict(name=name, compiled=True, assertion_rejected=True,
            intended_assertion=diagnostic, sanitizer_fault=False,
            source_sha256=sha256(mutant), returncode=ran.returncode))
    return controls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', args.name):
        parser.error('--name must be a fresh short lowercase slug')
    destination = OUTPUT / args.name
    destination.mkdir(parents=True, exist_ok=False)

    source_paths = [SOURCE / filename for filename in PRODUCTION]
    inputs = [Path(__file__), HARNESS, FIXTURE, *source_paths,
              *sorted(SOURCE.glob('*.h'))]
    input_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in inputs}
    clang = shutil.which('clang')
    assert clang, 'clang is required for ASan/UBSan host integration'
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
                       UBSAN_OPTIONS='halt_on_error=1')
    binary = destination / 'rro-session'
    command = compiler_command(clang, binary)
    built = invoke(command, destination / 'build.log', timeout=300)
    assert built.returncode == 0, (built.returncode, built.stderr[-6000:])
    ran = invoke([binary], destination / 'run.log', environment, timeout=1800)
    assert ran.returncode == 0, (ran.returncode, ran.stderr[-6000:])
    matrix = json.loads(ran.stdout)
    assert matrix['passed'] and matrix['profiles'] == 3 and not matrix['hardware']
    assert matrix['enrollments'] == 139 + 139 + 137
    assert matrix['publications'] == 3 * 129
    assert matrix['reset_npu'] == 3 * 2 * 1025
    assert matrix['mcu_begin'] == matrix['mcu_complete'] == 3 * 2 * 1025
    assert matrix['positive_rpc'] == 19261 and matrix['journal_compares'] == 19261
    assert matrix['memory_checks'] == 3 * (129 + 2 * 1025)
    assert matrix['full_memory_checks'] == 6
    assert matrix['negative_cases'] == 34 and matrix['direct_negative'] == 19
    assert matrix['io_faults'] == 6
    controls = mutation_controls(destination, clang, environment)
    assert len(controls) == 5 and all(control['assertion_rejected'] for control in controls)
    assert all(sha256(ROOT / name) == digest for name, digest in input_hashes.items()), \
        'source inputs drifted during host run'

    artifacts = {str(path.relative_to(destination)): sha256(path)
                 for path in sorted(destination.rglob('*')) if path.is_file()}
    result = dict(passed=True, matrix=matrix, mutation_controls=controls,
        inputs=input_hashes, artifacts=artifacts,
        compile_command=[str(part) for part in command],
        sanitizers=['ASan', 'UBSan', 'leak-detection'],
        scope=['Actual portable C client, codec, broker, retained journal, native effect engine, '
               'V2 control and boot gates execute together on host mapped arrays.',
               'Cold DMA inventory, bootstrap callback success, worker parking, MCU result, '
               'reference pinning and CPU exclusion are explicitly modeled boundaries.',
               'Two reset generations are supplied by the test loop; no production current-generation '
               'source or physical transport is inferred.',
               'No RV32 instruction execution, kernel caller integration, hardware admission, '
               'physical DMA drain, CPU join, or free authority is established.'],
        hardware=False, physical_retirement=False, kernel_integration=False)
    result_path = destination / 'result.json'
    with result_path.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    # A manifest cannot contain its own digest. This final file covers every
    # other artifact, including the result receipt; its digest is printed below.
    manifest = destination / 'SHA256SUMS.txt'
    with manifest.open('x') as stream:
        for path in sorted(destination.rglob('*')):
            if path.is_file() and path != manifest:
                stream.write(f'{sha256(path)}  {path.relative_to(destination)}\n')
    print(json.dumps(dict(passed=True, matrix=matrix, mutation_controls=len(controls),
        receipt=str(result_path.relative_to(ROOT)), receipt_sha256=sha256(result_path),
        manifest=str(manifest.relative_to(ROOT)), manifest_sha256=sha256(manifest))),
        flush=True)


if __name__ == '__main__':
    main()
