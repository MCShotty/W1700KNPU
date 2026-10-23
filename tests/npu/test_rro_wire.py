#!/usr/bin/env python3
"""Host-only RRO wire codec checks; no transport, RV32, or hardware execution."""

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
CODEC = SOURCE / 'rro-wire.c'
HARNESS = ROOT / 'tests/npu/rro-wire-harness.c'
OUTPUT = ROOT / '.local/npu-rro-wire-host-20261023'


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def no_core_dump():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def invoke(command, log, environment=None, timeout=120):
    completed = subprocess.run([str(part) for part in command], capture_output=True,
        text=True, timeout=timeout, env=environment, preexec_fn=no_core_dump)
    log.write_text(completed.stdout + completed.stderr)
    return completed


def compiler_command(clang, codec, binary):
    return [clang, '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        '-ffreestanding', '-fno-builtin', '-fsanitize=address,undefined',
        '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
        '-I', SOURCE, codec, HARNESS, '-o', binary]


def mutation_controls(destination, clang, environment):
    original = CODEC.read_text()
    variants = (
        ('identity-omission',
         'if (left[i] != right[i])',
         'if (i != 32u && left[i] != right[i])',
         'echo must compare every non-status byte'),
        ('reserved-padding-omission',
         'word < NPU_RRO_WIRE_SIZE / 4u - 8u; word++',
         'word < NPU_RRO_WIRE_SIZE / 4u - 9u; word++',
         'reserved body word must reject'),
        ('publish-payload-omission',
         'write_word(bytes, BODY_WORD(13u + i), message->command.words[i]);',
         'write_word(bytes, BODY_WORD(13u + i), 0u);',
         'wire oracle must match'),
    )
    controls = []
    for name, before, after, diagnostic in variants:
        assert original.count(before) == 1, ('mutation anchor', name)
        directory = destination / name
        directory.mkdir()
        source = directory / CODEC.name
        source.write_text(original.replace(before, after, 1))
        binary = directory / 'rro-wire'
        command = compiler_command(clang, source, binary)
        built = invoke(command, directory / 'compile.log')
        assert built.returncode == 0, (name, built.returncode, built.stderr[-4000:])
        ran = invoke([binary], directory / 'run.log', environment, timeout=300)
        assert ran.returncode == -signal.SIGABRT, (name, ran.returncode, ran.stderr[-4000:])
        assert diagnostic in ran.stderr, (name, ran.stderr[-4000:])
        assert 'ERROR: AddressSanitizer' not in ran.stderr and 'runtime error:' not in ran.stderr
        controls.append(dict(name=name, source_sha256=sha256(source),
            compiled=True, intended_assertion=diagnostic, assertion_rejected=True,
            sanitizer_fault=False))
    return controls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    arguments = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', arguments.name):
        parser.error('--name must be a short lowercase slug')

    destination = OUTPUT / arguments.name
    destination.mkdir(parents=True, exist_ok=False)
    inputs = [Path(__file__), HARNESS, CODEC, *sorted(SOURCE.glob('*.h'))]
    input_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in inputs}
    clang = shutil.which('clang')
    assert clang, 'clang is required for the sanitizer host test'
    binary = destination / 'rro-wire'
    command = compiler_command(clang, CODEC, binary)
    built = invoke(command, destination / 'compile.log')
    assert built.returncode == 0, (built.returncode, built.stderr[-6000:])

    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
        UBSAN_OPTIONS='halt_on_error=1')
    ran = invoke([binary], destination / 'run.log', environment, timeout=300)
    assert ran.returncode == 0, (ran.returncode, ran.stderr[-6000:])
    matrix = json.loads(ran.stdout)
    assert matrix['passed'] and matrix['profiles'] == 3 and matrix['operations'] == 8
    assert matrix['roundtrips'] == 30
    assert matrix['echo_corruptions'] == 30 * (256 - 4)
    assert matrix['reserved_rejections'] > 1000 and matrix['rejected_inputs'] > 1000

    controls = mutation_controls(destination, clang, environment)
    assert all(sha256(ROOT / name) == digest for name, digest in input_hashes.items()), 'source input drift during host run'
    artifacts = {str(path.relative_to(ROOT)): sha256(path)
        for path in sorted(destination.rglob('*')) if path.is_file()}
    result = dict(passed=True, matrix=matrix, mutation_controls=controls,
        inputs=input_hashes, artifacts=artifacts, compile_command=[str(part) for part in command],
        sanitizers=['ASan', 'UBSan', 'leak-detection'], hardware=False,
        limits=['Host C wire shape/correlation only; no client session, transport, RV32 execution or hardware.',
            'Identity correlation is exact byte comparison, not cryptographic authentication.',
            'Remote nonzero status is decoded and echoed but does not constitute successful completion.'])
    with (destination / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, cases=matrix['cases'], roundtrips=matrix['roundtrips'],
        mutation_controls=len(controls), receipt=str((destination / 'result.json').relative_to(ROOT)),
        receipt_sha256=sha256(destination / 'result.json'))), flush=True)


if __name__ == '__main__':
    main()
