import hashlib
import json
from pathlib import Path
import test_cold_txdone as test

ROOT = test.ROOT
HERE = Path(__file__).resolve().parent
host, elf = HERE / 'owner-q6/host.so', HERE / 'owner-q6/owner.elf'
pair = test.Pair(host, elf)
cases = {}
assert pair.call('fresh', 0) == 0
pair.setword('rx', 12, 1)
cases['active_RX_owner'] = dict(begin_status=pair.call('begin'), owner=list(pair.values('state')[:7]))
assert cases['active_RX_owner']['begin_status'] != 0
assert pair.call('fresh', 0) == pair.call('begin') == 0
pair.setword('ready', 0, 1)
cases['ready_without_effects'] = dict(finish_status=pair.call('finish'), owner=list(pair.values('state')[:7]))
assert cases['ready_without_effects']['finish_status'] != 0
assert pair.call('fresh', 0) == pair.call('begin') == 0
assert pair.core('reserve', 0x3e902a7c, 2, 512, 0xa5a5) == 0
cases['reservation_before_store'] = dict(owner=list(pair.values('state')[:7]),
    logical_count=pair.values('count')[0])
assert cases['reservation_before_store']['owner'][4:7] == [1, 1, 0]
assert cases['reservation_before_store']['logical_count'] == 0xa5a5a5a5
cases['bad_readback'] = dict(publish_status=pair.core('publish', 0x3e902a7c, 2, 513),
    owner=list(pair.values('state')[:7]))
assert cases['bad_readback']['publish_status'] != 0
assert cases['bad_readback']['owner'][4:7] == [1, 1, 0]
assert pair.call('fresh', 0) == pair.call('begin') == pair.call('run', 2, 0) == 0
cases['committed_unpublished_claim'] = dict(take_status=pair.call('take_late', 0),
    claims=list(pair.values('state')[7:10]), shared_count=pair.values('packet')[4])
assert cases['committed_unpublished_claim']['claims'] == [1, 1, 0]
assert cases['committed_unpublished_claim']['shared_count'] == 2561
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
result = dict(passed=True, cases=cases, calls=pair.calls,
    inputs={str(path.relative_to(ROOT)): sha(path) for path in (Path(__file__), Path(test.__file__),
        ROOT / 'firmware/npu/cold-txdone.c', ROOT / 'firmware/npu/cold-rx-event.c')},
    binaries={str(path.relative_to(ROOT)): sha(path) for path in (host, elf)},
    limits=['Focused portable compiled-C/RV32 counterexamples, not original native execution or hardware.'])
(HERE / 'focused.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result['cases']))
