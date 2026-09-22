#!/usr/bin/env python3
"""Run actual hostapd transaction helpers in native ucode, with modeled I/O.

No temporary files, builds, router access, or production writes. The only output
file is the opt-in receipt. Reload target selection is deliberately modeled;
test_mld_radio_membership.py owns the membership policy.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
RELATIVE = 'package/network/services/hostapd/files/hostapd.uc'
SOURCE = ROOT / '.build/openwrt' / RELATIVE
UCODE = ROOT / '.build/openwrt/staging_dir/hostpkg/bin/ucode'
LOCK = ROOT / 'firmware/source-lock.json'
OUT = ROOT / 'research/checkpoints/2026-09-07-wifi-transitions/transaction-tests.json'
FUNCTIONS = (
    'mld_ssid_matches', 'mld_config_matches', 'iface_pending_complete', 'iface_set_config', 'mld_find_matching_config',
    'mld_reload_interface', 'mld_reload_interfaces', 'mld_transaction_finish',
    'mld_reject_concurrent_mutation', 'mld_transaction_rollback',
    'mld_transaction_activate', 'mld_set_config', 'mld_set_request',
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def extract(source, name):
    start = source.index(f'function {name}(')
    end = re.search(r'^function |^const ', source[start + 1:], re.MULTILINE)
    assert end, f'No boundary after {name}'
    text = source[start:start + 1 + end.start()].rstrip()
    assert text.endswith('}'), name
    return text + '\n'


def step(kind='async', result=True, valid=True):
    return dict(kind=kind, result=result, valid=valid)


def case(name, mode='request', plan=None, expected=True, **kwargs):
    return dict(name=name, mode=mode, plan=plan or [], expected=expected,
                completion=kwargs.pop('completion', expected), **kwargs)


A = step()
S = step('sync')
F = step(result=False)
CASES = [
    case('reload-empty', 'reload', targets=[]),
    case('reload-missing-config', 'reload', targets=['absent']),
    case('reload-three-serial-async', 'reload', [A, A, A], radios=3,
         names=['phy0.0', 'phy0.1', 'phy0.2']),
    case('reload-three-sync', 'reload', [S, S, S], radios=3),
    case('reload-mixed-sync-async', 'reload', [S, A, S], radios=3,
         names=['phy0.0', 'phy0.1', 'phy0.2']),
    case('reload-sync-false-no-phy', 'reload', [step('no_phy')], expected=False),
    case('reload-sync-false-invalid', 'reload', [step('sync', valid=False)], expected=False,
         completion=None),
    case('reload-false-return-still-awaits-callback', 'reload', [step(valid=False)],
         expected=False, completion=None, direct=True, expect_return=False),
    case('reload-missing-direct-return', 'reload', targets=['absent'], direct=True,
         expect_return=True),
    case('reload-empty-filter-refused', 'reload', [step('empty', valid=False)], expected=False,
         completion=None),
    case('reload-empty-filter-allowed', 'reload', [step('empty', valid=False), S], allow=True),
    case('reload-exception-stops-series', 'reload', [step('throw')], expected=False),
    case('reload-async-failure-stops-series', 'reload', [F], expected=False),
    case('request-initial-async', plan=[A, A], initial=True, phases=['new', 'new']),
    case('request-replace-serial-async', plan=[A] * 4,
         phases=['detach', 'detach', 'new', 'new']),
    case('request-replace-all-sync', plan=[S] * 4, synchronous=True,
         phases=['detach', 'detach', 'new', 'new']),
    case('request-detach-first-failure-rollback', plan=[F, A, A], expected=False,
         phases=['detach', 'old', 'old']),
    case('request-detach-last-failure-rollback', plan=[A, F, A, A], expected=False,
         phases=['detach', 'detach', 'old', 'old']),
    case('request-activation-first-failure-rollback', plan=[A, A, F, A, A], expected=False,
         phases=['detach', 'detach', 'new', 'old', 'old']),
    case('request-activation-last-failure-rollback', plan=[A, A, A, F, A, A], expected=False,
         phases=['detach', 'detach', 'new', 'new', 'old', 'old']),
    case('request-rollback-union-distinct-targets', plan=[A, F, A, A], expected=False,
         remove_targets=['phy0.0'], add_targets=['phy0.1'],
         phases=['detach', 'new', 'old', 'old'],
         names=['phy0.0', 'phy0.1', 'phy0.0', 'phy0.1']),
    case('request-rollback-failure-reported', plan=[A, A, F, F], expected=False,
         phases=['detach', 'detach', 'new', 'old'], restore_failed=True),
    case('request-detach-sync-false-rollback', plan=[step('no_phy'), S, S], expected=False,
         synchronous=True, phases=['detach', 'old', 'old']),
    case('request-activation-false-return-awaits-rollback', plan=[A, A, step(valid=False), A, A],
         expected=False, phases=['detach', 'detach', 'new', 'old', 'old']),
    case('request-initial-activation-failure-rollback', plan=[F, A, A], initial=True,
         expected=False, phases=['new', 'detach', 'detach']),
    case('request-prepare-enumeration-rejected', prepare_error=True, expected=False,
         synchronous=True),
    case('request-prepare-entry-rejected', entry_error=True, expected=False, synchronous=True),
    case('request-unchanged-no-reload', unchanged=True, synchronous=True),
    case('request-remove-all', plan=[A, A], remove=True, phases=['detach', 'detach']),
    case('request-defer-failure-no-unsolicited-reply', plan=[A] * 4, defer_fail=True,
         phases=['detach', 'detach', 'new', 'new']),
    case('transaction-stale-and-duplicate-finish', 'identity'),
    case('pending-old-completion-preserves-replacement', 'pending'),
]

MODEL = r'''
let f, trace, queue, saved, replies, results, logs, removals, plan_index;
let current, old_mld, prepared, defer_count, checks, max_pending, violations;
let libubus = { STATUS_UNKNOWN_ERROR: 9 };
let hostapd = {
  data: {}, bss: {},
  printf: function(message) { push(logs, message); },
  getpid: function() { return 4242; }
};
function check(ok, message) {
  checks++;
  if (!ok) {
    push(violations, message);
    die(message);
  }
}
function same(a, b) { return sprintf('%J', a) == sprintf('%J', b); }
function phase() {
  if (hostapd.data.mld == old_mld && length(old_mld)) return 'old';
  if (hostapd.data.mld.mld0?.config.version == 2) return 'new';
  return 'detach';
}
function log_exception(prefix, error) { push(logs, prefix + error); }
function phy_open(phy, radio) {
  let name = phy + '.' + radio;
  check(plan_index < length(f.plan), 'Unexpected driver call ' + name);
  current = f.plan[plan_index++];
  push(trace, { name, phase: phase(), kind: current.kind });
  if (current.kind == 'throw') die('modeled phy_open exception');
  if (current.kind == 'no_phy') return null;
  return { name, phy, radio };
}
function iface_check_mld(phydev, name, config) {
  check(config.bss[0].tag == 'original', 'orig_bss was not restored');
  check(config.orig_bss != config.bss, 'orig_bss array aliases bss array');
  if (current.kind == 'empty') config.bss = [];
  return current.valid;
}
function iface_config_remove(name, config) { return null; }
function iface_reload_config(name, phydev, config, old_config) {
  return current.kind == 'sync';
}
function iface_update_supplicant_macaddr(phydev) {}
function iface_restart(phydev, config, old_config, complete) {
  let pending = { phy: phydev.name, complete, result: current.result };
  check(!hostapd.data.pending_config[phydev.name], 'Overlapping same-phy work');
  hostapd.data.pending_config[phydev.name] = pending;
  push(queue, pending);
  push(saved, { pending, complete });
  max_pending = max(max_pending, length(queue));
  check(length(queue) == 1, 'Reloads are not serial');
  let mld = hostapd.data.mld.mld0;
  if (mld) {
    mld.has_wdev = true;
    mld.iface[phydev.name] = true;
  }
  return true;
}
function wdev_remove(name) { push(removals, { name, phase: phase() }); }
function is_equal(a, b) { return same(a, b); }
function mld_macaddr_state(old) { return f.prepare_error ? null : {}; }
function mld_macaddr_canonical(addr) { return addr; }
function mld_macaddr_available(state, addr, name) { return true; }
function mld_macaddr_reserve(state, addr, name) {}
function mld_rename_bss(data, name) { return true; }
function mld_add_bss(name, data, phy_list, mac_state, old) {
  if (f.entry_error) return false;
  data.ifname = name;
  data.macaddr = '02:00:00:00:00:02';
  prepared = data;
  return true;
}
// Policy-free target projection: the parent's membership suite owns selection.
function mld_collect_reload(targets, name, data, include_config) {
  let selected = include_config ? f.add_targets : f.remove_targets;
  for (let iface in selected ?? keys(hostapd.data.config)) targets[iface] = true;
}
'''

DRIVER = r'''
function reset(fixture) {
  f = fixture;
  trace = []; queue = []; saved = []; replies = []; results = [];
  logs = []; removals = []; plan_index = 0; defer_count = 0;
  checks = 0; max_pending = 0; prepared = null; violations = [];
  old_mld = f.initial ? {} : {
    mld0: { config: { version: 1 }, ifname: 'mld0',
            macaddr: '02:00:00:00:00:01', has_wdev: true, iface: {} }
  };
  hostapd.data = { config: {}, pending_config: {}, mld: old_mld };
  for (let i = 0; i < (f.radios ?? 2); i++) {
    let name = 'phy0.' + i;
    hostapd.data.config[name] = {
      phy: 'phy0', radio_idx: i, bss: [{ tag: 'filtered' }],
      orig_bss: [{ tag: 'original', mld_ap: true, ifname: 'mld0' }]
    };
  }
}
function request() {
  return {
    defer: function() { defer_count++; return !f.defer_fail; },
    reply: function(data, status) { push(replies, { data, status: status ?? 0 }); }
  };
}
function guard_concurrency() {
  let transaction = hostapd.data.mld_transaction;
  if (!transaction) return;
  let before = length(trace);
  for (let operation in ['MLD config', 'hostapd reload', 'AP/STA state change',
                        'channel switch', 'hostapd config reset', 'hostapd config set',
                        'hostapd config add', 'hostapd config remove'])
    check(mld_reject_concurrent_mutation(operation), 'Concurrent guard accepted ' + operation);
  let rejected = mld_set_request(request(), {});
  check(rejected == libubus.STATUS_UNKNOWN_ERROR, 'Concurrent request accepted');
  check(hostapd.data.mld_transaction == transaction, 'Concurrent request changed ownership');
  check(length(trace) == before && !length(replies), 'Concurrent request caused I/O');
}
function drain() {
  let budget = 16;
  while (length(queue)) {
    check(budget-- > 0, 'Unbounded callback schedule');
    guard_concurrency();
    let pending = shift(queue);
    iface_pending_complete(pending);
    let before = { calls: length(trace), replies: length(replies), results: length(results),
                   queue: length(queue), active: keys(hostapd.data.pending_config) };
    // Re-delivery goes through the actual one-shot framework helper.
    iface_pending_complete(pending);
    check(same(before, { calls: length(trace), replies: length(replies), results: length(results),
                        queue: length(queue), active: keys(hostapd.data.pending_config) }),
          'Duplicate pending completion had effects');
  }
}
function run_reload() {
  let targets = {};
  for (let name in f.targets ?? keys(hostapd.data.config)) targets[name] = true;
  if (f.direct) {
    let ret = mld_reload_interface(keys(targets)[0], (valid) => push(results, valid), f.allow);
    check(ret == f.expect_return, 'Wrong direct reload return');
  } else {
    mld_reload_interfaces(targets, (valid) => push(results, valid), f.allow);
  }
  if (length(queue)) {
    check(length(queue) == 1, 'Async start issued multiple reloads');
    check(!length(results), 'Completed before pending callback');
  }
  drain();
  check(same(results, [f.completion]), 'Wrong series completion');
  if (!f.direct) {
    let before = length(trace);
    for (let item in saved) { item.complete(true); item.complete(false); }
    check(same(results, [f.completion]) && length(trace) == before,
          'Late callback changed finished series');
  }
}
function run_request() {
  let config = f.remove ? {} : { mld0: { version: f.unchanged ? 1 : 2 } };
  let ret = mld_set_request(request(), config);
  let owner = hostapd.data.mld_transaction;
  if (f.synchronous) {
    check(!length(queue), 'Unexpected asynchronous completion');
    check(!defer_count, 'Synchronous result deferred');
    check(same(ret, f.expected ? { pid: 4242 } : libubus.STATUS_UNKNOWN_ERROR),
          'Wrong synchronous request return');
  } else {
    check(length(queue) == 1 && owner != null, 'Missing pending transaction');
    check(defer_count == 1, 'Request not deferred exactly once');
    check(ret == (f.defer_fail ? libubus.STATUS_UNKNOWN_ERROR : null), 'Wrong async return');
    check(!length(replies), 'Premature reply');
  }
  drain();
  check(hostapd.data.mld_transaction == null, 'Transaction retained after completion');
  check(!length(hostapd.data.pending_config), 'Pending configuration leaked');
  check(!mld_reject_concurrent_mutation('post-completion'), 'Guard remains locked');
  if (!f.synchronous && !f.defer_fail)
    check(same(replies, [{ data: f.expected ? { pid: 4242 } : {},
                          status: f.expected ? 0 : libubus.STATUS_UNKNOWN_ERROR }]),
          'Wrong deferred reply');
  else
    check(!length(replies), 'Unexpected deferred reply');
  if (!f.expected) {
    check(hostapd.data.mld == old_mld, 'Rollback did not restore old map identity');
    if (prepared) check(!prepared.has_wdev && !length(prepared.iface),
                        'New entry retained wdev/iface after rollback');
  } else if (f.remove) {
    check(!length(hostapd.data.mld), 'Removed MLD retained');
  } else {
    check(hostapd.data.mld.mld0.config.version == (f.unchanged ? 1 : 2),
          'Wrong committed configuration');
  }
  if (f.restore_failed)
    check(index(join('\n', logs), 'Failed to restore previous MLD config') >= 0,
          'Rollback restoration failure not reported');
  if (f.phases) check(same(map(trace, (row) => row.phase), f.phases), 'Wrong phase ordering');
  if (f.phases) {
    let reached_new = index(f.phases, 'new') >= 0;
    let expected_removed = [];
    if (!f.initial && (reached_new || f.remove))
      push(expected_removed, { name: 'mld0', phase: 'detach' });
    if (!f.expected && reached_new)
      push(expected_removed, { name: 'mld0', phase: 'new' });
    check(same(removals, expected_removed), 'Wrong wdev cleanup order');
  }
  let before = { calls: length(trace), replies: length(replies), removed: length(removals) };
  for (let item in saved) { item.complete(true); item.complete(false); }
  if (owner) {
    mld_transaction_finish(owner, true);
    mld_transaction_activate(owner);
    mld_transaction_rollback(owner, {});
  }
  check(same(before, { calls: length(trace), replies: length(replies), removed: length(removals) }),
        'Stale/late transaction callback caused effects');
}
function run_identity() {
  let stale = { complete: (valid) => push(results, 'stale') };
  let active = { complete: (valid) => {
    check(hostapd.data.mld_transaction == null, 'Owner not cleared before completion');
    push(results, valid);
  } };
  hostapd.data.mld_transaction = active;
  mld_transaction_finish(stale, true);
  mld_transaction_activate(stale);
  mld_transaction_rollback(stale, {});
  check(hostapd.data.mld_transaction == active && !length(results), 'Stale owner accepted');
  mld_transaction_finish(active, false);
  mld_transaction_finish(active, true);
  check(same(results, [false]), 'Finish not one-shot');
}
function run_pending() {
  let old = { phy: 'phy0.0', result: true, complete: (valid) => push(results, valid) };
  let replacement = { phy: 'phy0.0', result: false,
                      complete: (valid) => push(results, valid) };
  hostapd.data.pending_config['phy0.0'] = replacement;
  iface_pending_complete(old);
  iface_pending_complete(old);
  check(hostapd.data.pending_config['phy0.0'] == replacement, 'Old callback erased replacement');
  iface_pending_complete(replacement);
  iface_pending_complete(replacement);
  check(same(results, [true, false]), 'Pending completion not one-shot');
}
for (let fixture in fixtures) {
  reset(fixture);
  let failure = null;
  try {
    if (f.mode == 'reload') run_reload();
    else if (f.mode == 'request') run_request();
    else if (f.mode == 'identity') run_identity();
    else if (f.mode == 'pending') run_pending();
    if (f.names) check(same(map(trace, (row) => row.name), f.names), 'Wrong reload target order');
    check(plan_index == length(f.plan), 'Unused driver plan entries');
  } catch (error) { failure = error.message ?? sprintf('%s', error); }
  // Production catch blocks must not turn a fixture violation into a pass.
  failure ??= violations[0];
  printf('%J\n', { name: f.name, passed: failure == null, failure, checks,
                   trace, replies, results, removals, max_pending });
}
'''


def execute(functions, cases=CASES):
    runner = MODEL + '\n' + '\n'.join(functions.values())
    runner += '\nlet fixtures = ' + json.dumps(cases) + ';\n' + DRIVER
    run = subprocess.run([str(UCODE), '-e', runner],
                         text=True, capture_output=True, timeout=20)
    assert run.returncode == 0, run.stderr
    rows = [json.loads(line) for line in run.stdout.splitlines()]
    assert [row['name'] for row in rows] == [case['name'] for case in cases]
    return rows, sha(runner.encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-receipt', action='store_true')
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--require-source-lock', action='store_true')
    parser.add_argument('--expect-source-sha')
    args = parser.parse_args()
    source_bytes = SOURCE.read_bytes()
    source_hash = sha(source_bytes)
    source = source_bytes.decode()
    lock_bytes = LOCK.read_bytes()
    lock = json.loads(lock_bytes)
    matches = [row['sha256'] for row in lock['openwrt']['changed_files'] if row['path'] == RELATIVE]
    assert len(matches) == 1, 'Missing/duplicate source-lock entry'
    lock_matches = source_hash == matches[0]
    if args.require_source_lock:
        assert lock_matches, f'Source-lock mismatch: prepared={source_hash}, locked={matches[0]}'
    if args.expect_source_sha:
        assert source_hash == args.expect_source_sha, 'Pinned source hash mismatch'
    functions = {name: extract(source, name) for name in FUNCTIONS}
    rows, runner_sha = execute(functions)
    failures = [row for row in rows if not row['passed']]
    if failures:
        print(json.dumps(failures, indent=2))
        raise SystemExit(1)
    mutations = {
        'remove-pending-one-shot': ('iface_pending_complete', '\tdelete pending.complete;', ''),
        'ignore-pending-failure': ('iface_pending_complete', 'pending.result == true', 'true'),
        'remove-finish-owner-check': ('mld_transaction_finish',
            '\tif (hostapd.data.mld_transaction != transaction)\n\t\treturn;\n', ''),
        'forget-series-finished': ('mld_reload_interfaces', 'finished = true;', 'finished = false;'),
        'allow-concurrent-mutation': ('mld_reject_concurrent_mutation', 'return true;', 'return false;'),
        'omit-rollback-old-map': ('mld_transaction_rollback',
            '\thostapd.data.mld = transaction.old_mld;', ''),
        'omit-rollback-detach-targets': ('mld_transaction_activate',
            '\t\t\t...transaction.remove_reload,', ''),
    }
    killed = {}
    for name, (function, old, new) in mutations.items():
        assert functions[function].count(old) == 1, name
        mutant = dict(functions)
        mutant[function] = mutant[function].replace(old, new)
        mutant_rows, _ = execute(mutant)
        killed[name] = [row['name'] for row in mutant_rows if not row['passed']]
        assert killed[name], f'Surviving mutant: {name}'
    # A changing parent checkout is not silently certified against an old lock.
    assert SOURCE.read_bytes() == source_bytes, 'Source changed during run; rerun after parent edit'
    assert LOCK.read_bytes() == lock_bytes, 'Source lock changed during run; rerun after parent edit'
    receipt = dict(
        scope='Actual native-ucode helper execution with modeled framework/driver I/O; no router/client proof',
        source_path=RELATIVE, source_sha256=source_hash,
        source_lock_sha256=sha(lock_bytes), source_lock_expected_sha256=matches[0],
        source_lock_matches=lock_matches, source_lock_required=args.require_source_lock,
        harness_sha256=sha(Path(__file__).read_bytes()), ucode_sha256=sha(UCODE.read_bytes()),
        generated_runner_sha256=runner_sha,
        functions={name: sha(text.encode()) for name, text in functions.items()},
        passed=len(rows), assertions=sum(row['checks'] for row in rows),
        killed_mutants=killed, cases=rows,
        modeled=['driver/PHY results and asynchronous schedule', 'framework maps and request reply/defer',
                 'MLD address preparation and unchanged-config matching dependencies',
                 'reload target projection (membership policy intentionally excluded)',
                 'wdev removal storage effect, not kernel destruction'],
        boundaries=['No complete hostapd/ubus/netifd integration or runtime timeout proof',
                    'No missing callback injected after false return: caller still owes completion',
                    'In-flight duplicate callbacks enter actual iface_pending_complete one-shot guard',
                    'Raw callback redelivery tested only after series completion',
                    'No membership, driver, regulatory, client, router, image, build, flash or NPU work'],
    )
    if args.write_receipt:
        assert args.out.parent.is_dir(), 'Create the scoped report directory before receipt output'
        args.out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({key: receipt[key] for key in
                      ('passed', 'assertions', 'source_sha256', 'source_lock_matches', 'harness_sha256')}))
    print(json.dumps({'killed_mutants': len(killed), 'receipt_written': args.write_receipt}))


if __name__ == '__main__':
    main()
