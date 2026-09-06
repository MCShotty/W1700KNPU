#!/usr/bin/env python3
"""Retain prior receipts while replaying the startup and non-bootstrap modes."""
import contextlib
import hashlib
import importlib
import io
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-06-npu-bootstrap/regressions'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for name in ('test_startup_native', 'test_startup_protocol', 'test_startup_race',
                 'run_startup_regressions'):
        module = importlib.import_module(name)
        module.OUT = OUT / name
        module.OUT.mkdir(parents=True, exist_ok=True)
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            module.main()
        (module.OUT / 'replay.log').write_text(stdout.getvalue())
        outputs = sorted(module.OUT.rglob('*.json'))
        assert outputs
        results.append({'name': name, 'passed': True,
                        'evidence': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in outputs}})
        print(name + ': PASS', flush=True)
    (OUT / 'bootstrap-regressions.json').write_text(json.dumps({
        'passed': True, 'runs': results,
        'scope': 'Startup and prior non-bootstrap adapter modes. The strict-bootstrap ELF is tested separately; these replays do not prove its future running-state datapath.'}, indent=2)+'\n')


if __name__ == '__main__':
    main()
