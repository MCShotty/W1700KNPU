#!/usr/bin/env python3
"""Compiled logical-owner mutants; no original firmware or physical authority."""
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

ROOT, CORE, TESTS = owner.ROOT, owner.CORE, owner.TESTS


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    baseline = args.baseline.resolve()
    assert baseline.is_relative_to(ROOT / '.local') and baseline.is_file()
    dest = ROOT / '.local/npu-pcie-tail-owner' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    source_path = CORE / 'cold-pcie-tail.c'
    source = source_path.read_text()
    check = (' &&\n           npu_cold_txdone_live(c->prior.done, &p->prior.prior, epoch,\n'
             '               c->prior.rx, c->prior.rx_readback, c->prior.packets, c->prior.ready)')
    assert source.count(check) == 2
    first, last = source.index(check), source.rindex(check)
    late_mutants = {
        'remove-both-rechecks': source.replace(check, ''),
        'remove-metadata-recheck': source[:first] + source[first:].replace(check, '', 1),
        'remove-prefix-recheck': source[:last] + source[last:].replace(check, '', 1),
        'fault-bits-only': source.replace(check,
            ' && !c->prior.done->fault && !c->prior.rx->fault && !c->prior.packets->fault'),
    }
    legacy = {
        'stage-live-active': ('!s->active && s->stage == stage;', 's->stage == stage;'),
        'stage-live-wrong-stage': ('!s->active && s->stage == stage;', '!s->active && stage < 3;'),
        'prior-reader-change': ('equal(c->pcie, &held_pcie, sizeof(held_pcie)) &&', '1 &&'),
        'unfinished-tx': ('tx->active || tx->stage != 2 ||', 'tx->stage != 2 ||'),
        'wrong-store-value': (
            'address != store.address || bytes != store.bytes || value != store.value ||',
            'address != store.address || bytes != store.bytes || ((void)value, 0) ||'),
        'forget-possible-effect': (
            '    npu_cold_pcie_tail_fault(s);\n    return status;',
            '    npu_cold_pcie_tail_fault(s);\n    if (s) s->committed = s->published;\n    return status;'),
        'wrong-hif2-register': ('p->tx.host2 + 0x110u : 0;', 'p->tx.host2 + 0x10u : 0;'),
        'count-underflow': ('{255, 511, 1023, 1535, 511}', '{255, 511, 1023, 1535, UINT32_MAX}'),
        'premature-finish': (
            'if (!context(s, p, epoch, c) || !s->active ||\n        s->committed != end(s->stage) || s->published != s->committed)',
            'if (!context(s, p, epoch, c) || !s->active)')}
    mutants = {}
    for name, (before, after) in legacy.items():
        assert source.count(before) == 1, name
        mutants[name] = source.replace(before, after)
    mutants.update(late_mutants)
    assert len(legacy) == 9 and len(late_mutants) == 4 and len(mutants) == 13
    sources = [CORE / (name + '.c') for name in
        ('cold-rx-pcie', 'cold-txdone', 'cold-rx-event', 'cold-tx-buffer', 'cold-packet', 'cold-tx')]
    fixtures = [TESTS / (name + '.c') for name in
        ('cold-txdone-fixture', 'cold-rx-pcie-fixture', 'cold-pcie-tail-fixture')]
    sanitizer_source = TESTS / 'cold-pcie-tail-sanitize.c'
    paths = [*sources, *fixtures, source_path, sanitizer_source, Path(__file__), Path(owner.__file__),
        Path(owner.pcie.__file__), Path(owner.pcie.done.__file__), Path(owner.pcie.done.tx.__file__),
        Path(owner.pcie.done.tx.loader.__file__), *CORE.glob('*.h'), baseline]
    inputs = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    common = [shutil.which('clang'), '-std=c11', '-Wall', '-Wextra', '-Werror',
        '-I' + str(CORE), '-I' + str(TESTS)]
    command = common + ['-O2', '-shared', '-fPIC']
    run = owner.pcie.done.tx.loader.run
    sanitizer = dest / 'sanitize'
    run(common + ['-O1', '-g', '-fno-omit-frame-pointer', '-fsanitize=address,undefined',
        *sources, source_path, *fixtures, sanitizer_source, '-o', sanitizer], dest / 'sanitize-build.log')
    completed = subprocess.run([str(sanitizer)], text=True, capture_output=True, timeout=120,
        env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1'))
    with (dest / 'sanitize-run.log').open('x') as stream:
        stream.write(completed.stdout + completed.stderr)
    assert completed.returncode == 0, completed.stderr
    shared = dest / 'baseline.so'
    run(command + [*sources, source_path, *fixtures, '-o', shared], dest / 'baseline-build.log')
    reference = owner.exercise(owner.Pair(shared, baseline, False), exhaustive=True)
    assert reference['passed'] and reference['native_compared'] is False
    results = []
    for name, text in mutants.items():
        path, shared = dest / (name + '.c'), dest / (name + '.so')
        with path.open('x') as stream:
            stream.write(text)
        run(command + [*sources, path, *fixtures, '-o', shared], dest / (name + '-build.log'))
        pair = owner.Pair(shared, baseline, False)
        try:
            owner.exercise(pair, exhaustive=True)
        except AssertionError as error:
            result = dict(name=name, compiled=True, killed=True, assertion=repr(error),
                calls_before_detection=pair.calls, source_sha256=sha(path), binary_sha256=sha(shared))
            if name in late_mutants:
                assert 'late-owner-accepted' in repr(error) or 'late-owner-unexpected-write' in repr(error), result
            results.append(result)
            print(json.dumps(result), flush=True)
        else:
            raise AssertionError(('surviving-late-owner-mutant', name))
    assert all(sha(ROOT / name) == expected for name, expected in inputs.items())
    result = dict(passed=True, reference_calls=reference['calls'], reference_controls=reference['controls'],
        mutants=results, inputs=inputs,
        legacy_mutant_ids=list(legacy), late_owner_mutant_ids=list(late_mutants),
        sanitizer=dict(exit_code=0, address=True, undefined=True, leak=True,
            binary_sha256=sha(sanitizer), host_timeout_seconds=120),
        artifacts={str(path.relative_to(ROOT)): sha(path) for path in dest.iterdir() if path.is_file()},
        compiled_host_logic=True, native_compared=False, original_native_firmware_executed=False,
        full_setup=False, hardware=False,
        limits=['Actual source plus individually compiled alternate C,using logical earlier-owner fixtures.',
            'The reference ELF supplies symbol sizes only;no original or normal RV32 instruction executes in this host-only mutant runner.',
            'Killed mutants establish the named late-reader regressions,not physical exclusion or complete constructor qualification.'])
    with (dest / 'result.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, mutants=len(results), reference_calls=reference['calls'],
        controls=len(reference['controls']), sha256=sha(dest / 'result.json'))), flush=True)


if __name__ == '__main__':
    main()
