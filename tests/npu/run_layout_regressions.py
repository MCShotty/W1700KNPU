#!/usr/bin/env python3
"""Replay bounded-map regressions without rewriting historical checkpoint receipts."""
import contextlib
import hashlib
import importlib
import io
import json
from pathlib import Path
import subprocess

from emulation_layout import STATE, SRAM_BYTES, HEAP, HEAP_BYTES

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-06-npu-layout'
SUITES = ('test_firmware_memory_layout', 'test_firmware_gdma', 'test_firmware_stop_counterexample',
          'test_firmware_stop_irqs', 'test_firmware_mailbox_dispatch',
          'test_barrier_protocol', 'test_barrier_core5', 'test_barrier_workers',
          'test_admission_protocol', 'test_admission_native')


def main(output=OUT, suites=SUITES, adapter_path=None):
    output.mkdir(parents=True, exist_ok=True)
    runs = []
    for name in suites:
        module = importlib.import_module(name)
        module.OUT = output / name
        module.OUT.mkdir(parents=True, exist_ok=True)
        with contextlib.redirect_stdout(io.StringIO()):
            if name == 'test_admission_native' and adapter_path is not None:
                module.main(adapter_path)
            else:
                module.main()
        evidence = sorted(module.OUT.glob('*.json'))
        assert evidence, name
        runs.append({'suite': name, 'passed': True,
                     'evidence': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in evidence}})
        print(name + ': PASS', flush=True)
    from test_admission_native import build_platform, Coordinator
    rejected = []
    for address in (0x3e920000, 0x3e904740, 0x3e907ec0, 0x3e906001):
        try:
            build_platform(address)
        except subprocess.CalledProcessError as error:
            assert 'candidate state outside conservative local SRAM' in error.stderr, error.stderr
            rejected.append(hex(address))
        else:
            raise AssertionError('invalid linker state accepted: ' + hex(address))
    path = adapter_path or build_platform()
    coordinator = Coordinator(path)
    assert coordinator.barrier.symbols['npu_emulation_barrier_state'] == STATE
    assert coordinator.barrier.symbols['npu_emulation_admission_state'] == STATE + 0x100
    assert coordinator.barrier.symbols['npu_emulation_masked_state'] == STATE + 0x140
    source_files = sorted(set((ROOT / 'tests/npu').glob('*.py')) |
                          set((ROOT / 'tests/npu').glob('*.S')) |
                          set((ROOT / 'tests/npu').glob('*.ld')) |
                          set((ROOT / 'tests/npu').glob('*.c')) |
                          set((ROOT / 'firmware/npu').glob('*.c')) |
                          set((ROOT / 'firmware/npu').glob('*.h')))
    report = {'passed': True, 'runs': runs, 'rejected_linker_addresses': rejected,
              'state': hex(STATE), 'local_sram_test_bytes': SRAM_BYTES,
              'separate_synthetic_ring_region': [hex(HEAP), hex(HEAP + HEAP_BYTES)],
              'combined_elf_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files},
              'scope': 'Bounded emulation and retained FIT inspection, not full boot, device cache, physical drain or production reservation.'}
    (output / 'layout-regressions.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {len(suites)} suites, four linker negative controls, three linked state symbols')


if __name__ == '__main__':
    main()
