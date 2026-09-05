#!/usr/bin/env python3
"""Exercise the combined copy/worker/admission ELF and preserve earlier receipts."""
import json

import run_layout_regressions
from test_admission_native import build_platform
from test_barrier_protocol import digest
from test_gdma_copy_guard import SOURCE, OUT, CopyCaller, DATA


def main():
    path = build_platform(gdma_source=SOURCE, poll_limit=64)
    before = path.read_bytes()
    assert build_platform(gdma_source=SOURCE, poll_limit=64).read_bytes() == before
    suites = run_layout_regressions.SUITES + ('test_gdma_owner_routes', 'test_gdma_copy_guard')
    run_layout_regressions.main(output=OUT, suites=suites, adapter_path=path)
    assert path.read_bytes() == before
    default = build_platform(gdma_source=SOURCE)
    default_before = default.read_bytes()
    assert build_platform(gdma_source=SOURCE).read_bytes() == default_before
    default_cases = []
    for model in ({'busy_before': -1}, {'early_done': True, 'idle_at': None}):
        caller = CopyCaller(default, **model)
        caller.execute(0x8400f0c4, (0, DATA), count=2000000, timeout=30000000)
        caller.assert_retained()
        caller.late_completion()
        if 'busy_before' in model:
            assert caller.device.pre_reads == 65536
        else:
            assert caller.device.post_reads == 65536
        default_cases.append({'model': model, 'retained_after_late_completion': True,
                              'device': caller.device.summary()})
    report = {'passed': True, 'suites': list(suites), 'combined_test_elf': str(path.relative_to(SOURCE.parents[2])),
              'combined_test_elf_sha256': digest(before), 'test_poll_limit': 64,
              'default_elf': str(default.relative_to(SOURCE.parents[2])),
              'default_elf_sha256': digest(default_before), 'default_poll_limit': 65536,
              'both_compiles_reproduced_byte_for_byte': True,
              'default_poll_fault_cases': default_cases,
              'scope': 'Actual combined software instructions and fault models; not hardware completion/cache/boot or host lifecycle proof.'}
    (OUT / 'copy-regressions.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: combined copy/admission/worker regression and two reproducible poll-limit builds')


if __name__ == '__main__':
    main()
