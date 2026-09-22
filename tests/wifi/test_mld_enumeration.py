#!/usr/bin/env python3
"""Execute the packaged MLD address guards with modeled nl80211 return values."""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
RELATIVE = 'package/network/services/hostapd/files/hostapd.uc'
SOURCE = ROOT / '.build/openwrt' / RELATIVE
UCODE = ROOT / '.build/openwrt/staging_dir/hostpkg/bin/ucode'
OUT = ROOT / 'research/checkpoints/2026-09-06-wifi-config/mld-enumeration-tests.json'
OLD_SHA = '1100002b6b1a4764e32bc3c87e75e8f63c79a08f1bb7e2691e1d6f516f164d9f'
OLD_FUNCTIONS_SHA = '1f7570f870925276926c6109408be53fce31318f16d9a1b7e4bb755992a006dd'
NEW_CHECK = 'nl80211.error() != null || (wdevs != null && type(wdevs) != "array")'
NORMALIZE = '\t// A successful empty multipart dump has no result value in ucode-nl80211.\n\twdevs ??= [];\n'
MAC = '02:00:00:00:00:10'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def case(name, result=None, error=None, stale=None, old=None, config=None,
         accepted=True, reserved=False, available=True, address=MAC):
    return dict(name=name, result=result, error=error, stale=stale, old=old or {},
                config=config or {}, accepted=accepted, reserved=reserved,
                available=available, address=address)


CASES = [
    case('empty-null'),
    case('empty-array', []),
    case('empty-after-stale-error', stale='Earlier unrelated error'),
    case('null-with-error', error='Netlink permission denied', accepted=False),
    case('partial-array-with-error', [], 'Interrupted reply', accepted=False),
    *[case(f'invalid-result-{i}', value, accepted=False)
      for i, value in enumerate([False, True, 0, 1, '', 'bad', {}])],
    case('external-live-owner', [{'ifname': 'other', 'mac': MAC}], reserved=True,
         available=False),
    case('same-mld-live-owner', [{'ifname': 'mld0', 'mac': MAC}],
         old={'mld0': {'macaddr': MAC}}, reserved=True),
    case('case-normalized-collision', [{'ifname': 'other', 'mac': MAC.upper()}],
         old={'mld0': {'macaddr': MAC}}, reserved=True, available=False),
    case('old-owner-empty-dump', old={'other': {'macaddr': MAC}},
         reserved=True, available=False),
    case('configured-ordinary-bss', config={'phy0': {'bss': [
        {'ifname': 'ap0', 'bssid': MAC}]}}, reserved=True, available=False),
    case('configured-same-mld-bss', old={'mld0': {'macaddr': MAC}},
         config={'phy0': {'bss': [{'ifname': 'mld0', 'bssid': MAC, 'mld_ap': True}]}},
         reserved=True),
    case('duplicate-external-live-address', [
        {'ifname': 'other0', 'mac': MAC}, {'ifname': 'other1', 'mac': MAC}],
        reserved=True, available=False),
]


def execute(source, label, cases=None):
    cases = CASES if cases is None else cases
    functions = source[source.index('function mld_macaddr_canonical('):
                       source.index('function mld_add_bss(')]
    runner = '''
let hostapd = { data: { config: {} } };
let fixture, last_error;
let nl80211 = {
  const: { NL80211_CMD_GET_INTERFACE: 5, NLM_F_DUMP: 768 },
  error: function() { let value = last_error; last_error = null; return value; },
  request: function(cmd, flags, payload) {
    if (cmd != 5 || flags != 768 || type(payload) != 'object')
      die('Incorrect enumeration request');
    if (fixture.error != null) last_error = fixture.error;
    return fixture.result;
  }
};
''' + functions + '\nlet cases = ' + json.dumps(cases) + ''';
for (fixture in cases) {
  last_error = fixture.stale;
  hostapd.data.config = fixture.config;
  let state = mld_macaddr_state(fixture.old);
  printf('%J\\n', {
    name: fixture.name,
    accepted: state != null,
    reserved: state != null && state.macaddr_list[fixture.address] == -1,
    available: state != null && mld_macaddr_available(state, fixture.address, 'mld0')
  });
}
'''
    with tempfile.TemporaryDirectory(prefix='mld-enum-', dir=ROOT / '.local/wifi-config') as temp:
        path = Path(temp) / f'{label}.uc'
        path.write_text(runner)
        run = subprocess.run([str(UCODE), str(path)], capture_output=True, text=True, timeout=15)
    assert run.returncode == 0, (label, run.stderr)
    rows = [json.loads(row) for row in run.stdout.splitlines()]
    assert len(rows) == len(cases)
    failures = []
    for fixture, result in zip(cases, rows):
        assert result['name'] == fixture['name']
        expected = {key: fixture[key] for key in ('accepted', 'reserved', 'available')}
        if not expected['accepted']:
            expected.update(reserved=False, available=False)
        if any(result[key] != value for key, value in expected.items()):
            failures.append(fixture['name'])
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    source = SOURCE.read_text()
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    expected = next(row['sha256'] for row in lock['openwrt']['changed_files']
                    if row['path'] == RELATIVE)
    assert sha(source.encode()) == expected
    assert source.count(NEW_CHECK) == 1 and source.count(NORMALIZE) == 1
    old = source.replace('\tnl80211.error();\n\tlet wdevs', '\tlet wdevs', 1)
    old = old.replace(NEW_CHECK, 'type(wdevs) != "array"').replace(NORMALIZE, '')
    old_functions = old[old.index('function mld_macaddr_canonical('):old.index('function mld_add_bss(')]
    assert sha(old_functions.encode()) == OLD_FUNCTIONS_SHA, 'Unexpected changes in the original enumeration function span'
    native_path = OUT.with_name('decoder-runtime.json')
    native = json.loads(native_path.read_text(encoding='utf-8-sig'))
    def native_cases(variant):
        result = []
        for row in native[variant]:
            complete = row['decoded'] == row['messages']
            assert row['error_cleared'] and row['result_is_null'] == (row['result'] is None)
            if variant == 'corrected':
                assert bool(row['error']) == (not complete)
            result.append(case('native-' + row['name'], row['result'], row['error'],
                accepted=complete, reserved=bool(row['decoded']), available=not row['decoded'],
                address='02:00:00:00:00:42'))
        assert len(result) == 6
        return result
    CASES.extend(native_cases('corrected'))
    failures = execute(source, 'candidate')
    assert not failures, failures
    old_failures = execute(old, 'old')
    assert 'empty-null' in old_failures
    mutants = {
        'discard-enumeration-error': source.replace('nl80211.error() != null || ', ''),
        'retain-stale-error': source.replace('\tnl80211.error();\n\tlet wdevs', '\tlet wdevs', 1),
        'skip-live-address-reservation': source.replace('mld_macaddr_reserve(state, addr, owner);',
                                                        '/* mutation: omit reservation */'),
    }
    mutation_results = {name: execute(value, name) for name, value in mutants.items()}
    assert all(mutation_results.values()), mutation_results
    unpatched_decoder_failures = execute(source, 'unpatched-decoder', native_cases('old'))
    assert set(unpatched_decoder_failures) == {'native-single_oom', 'native-first_oom', 'native-last_oom'}
    report = dict(scope='Actual ucode guard functions; modeled nl80211 responses, not radio/client proof',
                  source_sha256=sha(source.encode()), old_source_sha256=OLD_SHA,
                  original_enumeration_functions_sha256=OLD_FUNCTIONS_SHA,
                  harness_sha256=sha(Path(__file__).read_bytes()),
                  native_receipt_sha256=sha(native_path.read_bytes()),
                  unpatched_decoder_failures=unpatched_decoder_failures,
                  ucode_sha256=sha(UCODE.read_bytes()), passed=len(CASES),
                  cases=[row['name'] for row in CASES], reproduced_old_failures=old_failures,
                  killed_mutants=mutation_results)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=len(CASES), old_failures=len(old_failures),
                          killed_mutants=len(mutation_results))))


if __name__ == '__main__':
    main()
