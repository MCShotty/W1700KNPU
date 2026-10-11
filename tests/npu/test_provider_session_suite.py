#!/usr/bin/env python3
"""Collect exact-input native cases without rerunning their peers serially."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
CASES = ('nominal', 'wrong-boot', 'packet-fault', 'page-fault',
         'indication-fault', 'tx-fault', 'token-fault', 'descriptor-fault',
         'descriptor7-fault')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--header', type=Path, required=True)
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--publication', type=Path, required=True)
    parser.add_argument('--host-sender-receipt', type=Path, required=True)
    parser.add_argument('--nominal-receipt', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,27}', args.name)
    assert 1 <= args.jobs <= 8
    base = ROOT / '.local/npu-provider-session-20261010'
    destination = base / args.name
    assert not destination.exists()
    destination.mkdir()
    common = [sys.executable, str(ROOT / 'tests/npu/test_provider_session.py'),
              '--source', str(args.source.resolve()), '--header', str(args.header.resolve()),
              '--pair', str(args.pair.resolve()), '--publication', str(args.publication.resolve()),
              '--host-sender-receipt', str(args.host_sender_receipt.resolve()), '--cold-commands']
    results = {}
    artifacts = {}

    def run(case):
        name = 'descriptor-suite-' + case
        command = common + ['--native-case', case, '--name', name]
        log = destination / (case + '.log')
        with log.open('x') as stream:
            done = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                                  stdout=stream, stderr=subprocess.STDOUT)
        assert done.returncode == 0, (case, done.returncode, log)
        receipt = base / name / 'result.json'
        evidence = json.loads(receipt.read_bytes())
        assert evidence['passed'] and evidence['native_case'] == case
        assert not evidence['complete_cold_native_suite'] and len(evidence['native']) == 1
        return case, evidence, receipt

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run, case) for case in CASES[1:]]
        for future in as_completed(futures):
            case, evidence, receipt = future.result()
            results[case] = evidence
            artifacts[case] = receipt
            print(json.dumps(dict(stage='native-case', case=case, passed=True)), flush=True)

    nominal_path = args.nominal_receipt.resolve()
    deadline = time.monotonic() + 3600
    while not nominal_path.exists():
        assert time.monotonic() < deadline, 'Missing completed nominal receipt'
        time.sleep(5)
    nominal = json.loads(nominal_path.read_bytes())
    assert nominal['passed'] and nominal['case'] == 'nominal'
    results['nominal'] = nominal
    artifacts['nominal'] = nominal_path
    reference = results['wrong-boot']
    inputs = {}

    def check(path, digest):
        target = (ROOT / path).resolve()
        assert not Path(path).is_absolute() and target.is_relative_to(ROOT)
        assert sha(target) == digest, ('changed-input', path)
        assert path not in inputs or inputs[path] == digest, ('conflicting-input', path)
        inputs[path] = digest

    native = []
    rows = []
    for case in CASES:
        evidence = results[case]
        for path, digest in evidence['inputs'].items():
            check(path, digest)
        value = evidence['result'] if case == 'nominal' else evidence['native'][0]
        assert value['passed']
        for path, digest in value['inputs'].items():
            check(path, digest)
        if case != 'nominal':
            assert evidence['matrix'] == reference['matrix']
            assert [row['name'] for row in evidence['mutants']] == [row['name'] for row in reference['mutants']]
        native.append(value)
        receipt = artifacts[case]
        relative = str(receipt.relative_to(ROOT))
        check(relative, sha(receipt))
        rows.append(dict(case=case, receipt=relative, sha256=sha(receipt)))
    check(str(Path(__file__).resolve().relative_to(ROOT)), sha(Path(__file__).resolve()))
    result = dict(passed=True, matrix=reference['matrix'], mutants=reference['mutants'],
                  native=native, inputs=inputs, native_case='all', complete_cold_native_suite=True,
                  execution='Nine independently completed exact-input cases; not one serial parent invocation.',
                  case_receipts=rows, sanitizers=reference['sanitizers'], limits=reference['limits'])
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, native_cases=len(native), inputs=len(inputs))), flush=True)


if __name__ == '__main__':
    main()
