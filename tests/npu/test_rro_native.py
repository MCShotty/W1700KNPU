#!/usr/bin/env python3
"""Checked reconstructed RRO effects; no current transport or physical admission."""
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
from test_rro_lifetime_callers import validate_packets

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'firmware/npu'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(command, path, environment=None):
    completed = subprocess.run([str(value) for value in command], capture_output=True,
        text=True, timeout=900, env=environment)
    path.write_text(completed.stdout + completed.stderr)
    assert completed.returncode == 0, (completed.returncode, path.read_text()[-6000:])
    return completed


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def mutations(destination, command, environment):
    original = (SOURCE / 'rro-native.c').read_text()
    variants = (
        ('missing-block-clear',
         'if (okay && !command.selector) {\n        for (uint32_t offset = 0; offset < bytes; offset += 4)',
         'if (0) {\n        for (uint32_t offset = 0; offset < bytes; offset += 4)',
         'native publication must complete its verified stock projection'),
        ('ignored-store-result',
         'return owned(a) && a->write(a->opaque, address, bytes, value) && owned(a);',
         'return (a->write(a->opaque, address, bytes, value), 1);',
         'failed native publication retains exact possible prefix'),
        ('missing-final-table-readback', 'okay = okay && read_equal(&a, table, 4, base);',
         '(void)0;', 'failed native memory access or readback must not confirm publication'),
        ('wrong-reset-block', 'block_slot(p->profile, session / 8)', 'block_slot(p->profile, session / 16)',
         'native reset must match its exact table and session'),
    )
    records = []
    for name, before, after, diagnostic in variants:
        directory = destination / name
        directory.mkdir()
        assert original.count(before) == 1
        source = directory / 'rro-native.c'
        source.write_text(original.replace(before, after, 1))
        binary = directory / 'rro-native'
        replacements = {str(SOURCE / 'rro-native.c'):str(source), str(destination / 'rro-native'):str(binary)}
        changed = [replacements.get(str(value), str(value)) for value in command]
        run(changed, directory / 'build.log')
        completed = subprocess.run([str(binary),str(directory / 'frames.bin'),str(directory / 'states.bin')],
            capture_output=True,text=True,timeout=900,env=environment,preexec_fn=no_core)
        (directory / 'run.log').write_text(completed.stdout + completed.stderr)
        assert completed.returncode == -signal.SIGABRT and diagnostic in completed.stderr, (name,completed.returncode,completed.stderr)
        assert 'ERROR: AddressSanitizer' not in completed.stderr and 'runtime error:' not in completed.stderr
        records.append(dict(name=name,compiled=True,assertion_rejected=True,
            intended_assertion=diagnostic,returncode=completed.returncode,sanitizer_fault=False))
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--mutants', action='store_true')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    destination = ROOT / '.local/npu-rro-native-host-20261023' / args.name
    destination.mkdir(parents=True,exist_ok=False)
    files = [Path(__file__), ROOT / 'tests/npu/rro-native-harness.c',
        ROOT / 'tests/npu/rro-native-fixture.h',Path(q.__file__),
        ROOT / 'tests/npu/test_rro_lifetime_callers.py',
        ROOT / '.local/merge-nonoc-20260923/mt76-merged/mt7996/mt7996.h',
        SOURCE / 'rro-native.c', SOURCE / 'rro-lifetime.c',*SOURCE.glob('*.h')]
    inputs = {str(path.relative_to(ROOT)):sha(path) for path in files}
    header = files[5].read_text()
    macros = ('MT7996_RRO_MAX_SESSION','MT7996_RRO_WINDOW_MAX_LEN',
        'MT7996_RRO_ADDR_ELEM_LEN','MT7996_RRO_BA_BITMAP_SESSION_SIZE','MT7996_RRO_WINDOW_MAX_SIZE')
    (destination / 'rro-source-geometry.h').write_text('\n'.join(q.macro(header,name) for name in macros) + '\n')
    for path in files[1:3]:
        shutil.copyfile(path,destination / path.name)
    shutil.copyfile(__file__,destination / 'driver-at-run.py')
    command = [shutil.which('clang'),'-std=c11','-O1','-g','-Wall','-Wextra','-Werror',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',
        '-I',str(SOURCE),'-I',str(destination),str(SOURCE / 'rro-lifetime.c'),
        str(SOURCE / 'rro-native.c'),str(destination / 'rro-native-harness.c'),
        '-o',str(destination / 'rro-native')]
    run(command,destination / 'build.log')
    environment = dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
    completed = run([destination / 'rro-native',destination / 'frames.bin',destination / 'states.bin'],
        destination / 'run.log',environment)
    matrix = json.loads(completed.stdout)
    assert matrix['passed'] and matrix['frames'] == 134
    assert matrix['publication_failures'] == 129 * 20 * 3 and matrix['reset_failures'] == 5 * 3 * 3 * 3
    assert matrix['cases'] == 129 * 3 + 1025 * 2 * 3 + matrix['publication_failures'] + matrix['reset_failures']
    assert matrix['state_records'] == 3 * (1 + 129 + 1 + 1025 * 2) + 139 + 139 + 137
    assert (destination / 'states.bin').stat().st_size == matrix['state_records'] * (16 + matrix['state_bytes'])
    packets = validate_packets(destination / 'frames.bin')
    previous = ROOT / '.local/npu-rro-lifetime-callers/rro-provider-q2/caller-payloads.bin'
    inputs[str(previous.relative_to(ROOT))] = sha(previous)
    assert (destination / 'frames.bin').read_bytes() == previous.read_bytes()
    controls = mutations(destination,command,environment) if args.mutants else []
    assert all(sha(ROOT / name) == expected for name,expected in inputs.items()),'source-drift'
    artifacts = {str(path.relative_to(ROOT)):sha(path) for path in destination.rglob('*') if path.is_file()}
    result = dict(passed=True,matrix=matrix,mutants=controls,inputs=inputs,artifacts=artifacts,
        compile_command=command,sanitizers=['ASan','UBSan','leak'],frames=len(packets),
        reconstructed_native_effects=True,current_native_transport_admitted=False,hardware=False,
        limits=['Full native write/readback engine and retained journal execute as host C, not original RV32 instructions.',
            'All three profiles,129 publications,1025 IDs and two generations execute with mapped array backing.',
            'All20 selected I/O-failure boundaries per publication and nine per selected reset boundary are injected,not every instruction prefix.',
            'CPU exclusion,DMA/reference/backing and successful MCU completion are models;opaque synthetic identities acquire no resources.',
            'No wire completion authentication,native full cold startup,physical drain or operational RRO admission is inferred.'])
    with (destination / 'result.json').open('x') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps(dict(matrix,mutants=len(controls))),flush=True)


if __name__ == '__main__':
    main()
