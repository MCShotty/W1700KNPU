#!/usr/bin/env python3
"""Verify cold-reset code alongside the existing worker/admission/copy candidate."""
import json
import sys

sys.dont_write_bytecode = True
import run_layout_regressions as existing
import test_gdma_copy_guard as copy
from test_admission_native import build_platform
from test_barrier_protocol import digest
from test_startup_native import ROOT, OUT


def main():
    path = build_platform(startup=True, gdma_source=copy.SOURCE, poll_limit=64)
    first = path.read_bytes()
    assert build_platform(startup=True, gdma_source=copy.SOURCE, poll_limit=64).read_bytes() == first
    suites = existing.SUITES + ('test_gdma_owner_routes', 'test_gdma_copy_guard')
    existing.main(output=OUT / 'regressions', suites=suites, adapter_path=path)
    assert path.read_bytes() == first
    combined = {'passed': True, 'elf_sha256': digest(first),
                'normal': copy.normal_cases(path),
                'rejected': copy.owner_and_limit_cases(path),
                'failures': copy.failure_cases(path),
                'caller': copy.caller_counterexample(path),
                'inflight': copy.stop_inflight(path),
                'abi': copy.abi_cases(path),
                'coordinator': copy.coordinator_observes_fault(path),
                'other_callers': copy.other_callers(path)}
    (OUT / 'combined-copy-tests.json').write_text(json.dumps(combined, indent=2) + '\n')
    default = build_platform(startup=True, gdma_source=copy.SOURCE)
    default_bytes = default.read_bytes()
    assert build_platform(startup=True, gdma_source=copy.SOURCE).read_bytes() == default_bytes
    for model in ({'busy_before': -1}, {'early_done': True, 'idle_at': None}):
        caller = copy.CopyCaller(default, **model)
        caller.execute(0x8400f0c4, (0, copy.DATA), count=2000000, timeout=30000000)
        caller.assert_retained()
        caller.late_completion()
        assert (caller.device.pre_reads if 'busy_before' in model else caller.device.post_reads) == 65536
    result = {'passed': True, 'suites': list(suites),
              'combined_elf': str(path.relative_to(ROOT)), 'combined_elf_sha256': digest(first),
              'default_elf': str(default.relative_to(ROOT)), 'default_elf_sha256': digest(default_bytes),
              'default_poll_limit': 65536, 'test_poll_limit': 64,
              'reproducible_both_builds': True, 'default_late_completion_holds': 2,
              'scope': 'Combined software-instruction regressions; cold reset is tested separately. No physical drain/cache or complete bootstrap proof.'}
    (OUT / 'startup-regressions.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS twelve suites, combined copy paths, two default-poll late-completion holds')


if __name__ == '__main__':
    main()
