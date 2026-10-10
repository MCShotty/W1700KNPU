from pathlib import Path
import json
import subprocess
import sys

root = Path('/home/captain/W1700KNPU')
here = root / '.local/npu-cold-tx-20261010'
provider = '.local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c'
jobs = [
    ('endpoint', ['tests/npu/test_endpoint_binding.py', '--source', provider, '--name', 'tx-endpoint-qualification']),
    ('lease', ['tests/npu/test_dma_lifetime.py', '--source', provider, '--name', 'tx-lease-qualification']),
    ('request', ['tests/npu/test_provider_request_plan.py', '--source', provider, '--name', 'tx-request-qualification']),
    ('probe', ['tests/npu/test_provider_dma_probe.py', '--source', provider, '--name', 'tx-probe-qualification']),
    ('memory', ['tests/npu/test_cold_memory_plan.py', '--name', 'tx-memory-qualification']),
    ('source', ['tools/migration/verify_source_export.py', '--output', str(here / 'source-replay-final.json')]),
]
rows = []
for name, arguments in jobs:
    log = here / ('regression-' + name + '.log')
    assert not log.exists()
    command = [sys.executable, *arguments]
    with log.open('w') as stream:
        done = subprocess.run(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT)
    print(json.dumps(dict(stage=name, exit_code=done.returncode)), flush=True)
    assert done.returncode == 0, log
    rows.append(dict(name=name, command=command, log=str(log.relative_to(root)), exit_code=done.returncode))
(here / 'regressions.json').write_text(json.dumps(dict(passed=True, jobs=rows), indent=2) + '\n')
