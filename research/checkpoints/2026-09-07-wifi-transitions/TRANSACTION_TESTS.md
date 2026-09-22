# Bounded Actual-Ucode Transaction Tests

## Result

32 scenarios / 1,195 assertions pass in the existing native host ucode runtime.
Seven deliberate helper mutations are detected. The final prepared hostapd
source matches its source-lock entry. No additional production defect was
established within this modeled transaction boundary.
Fixture assertion failures remain fatal even when production catches exceptions.

The parent's cached-radio membership failure and correction are independent
of these results. This suite neither duplicates membership policy tests nor
claims that a host-only pass fixes the live reload timeout.

## Executed Code And Models

The integrated harness extracts twelve functions verbatim from prepared hostapd.uc:
`mld_ssid_matches`, `iface_pending_complete`, `iface_set_config`, `mld_find_matching_config`,
`mld_reload_interface`, `mld_reload_interfaces`, `mld_transaction_finish`,
`mld_reject_concurrent_mutation`, `mld_transaction_rollback`,
`mld_transaction_activate`, `mld_set_config`, and `mld_set_request`.

Driver/PHY returns, asynchronous delivery, hostapd/pending maps, request
defer/reply, address preparation, rename/equality dependencies and wdev removal
are explicit models. Reload-target projection is modeled independently of
radio masks; a distinct-target fixture tests the transaction rollback union.
The runtime receives the extracted program using `ucode -e`; no scratch files
are created. The runtime's piped source path requires seeking, so it is not used.

Coverage includes serial asynchronous, synchronous and mixed reloads; empty or
missing interfaces; first/last detach and activation failures; rollback failure
reporting; initial/replacement/unchanged/removal requests; preparation rejection;
failed request defer; concurrent mutation refusal while pending; completion
ownership; and wdev cleanup order. Maximum queued modeled reloads is one.

## Caller Contract

- `iface_set_config()` may return `false` and still owe an asynchronous callback.
  The fixture executes that actual branch and waits for its callback before
  rollback. It does not invent a missing callback and call the resulting wait
  a production bug. Synchronous false-return branches are also executed.
- An invalid configuration can complete with `null`, not literal `false`, when
  `allow_mld_filter` is absent. The tests retain the exact callback value and
  verify that request completion treats it as failure.
- In-flight duplicate delivery passes through actual `iface_pending_complete`,
  which removes its callback before invoking it. Raw callback redelivery is
  tested only after the reload series is finished. Arbitrary in-flight raw
  callback duplication bypassing that documented implementation contract is
  not treated as a supported schedule or a defect.
- An old pending object's completion cannot delete replacement pending storage;
  its own callback still runs once. Stale transaction identities cannot finish,
  activate or roll back the current transaction.
- Concurrent tests execute the common guard for eight operation labels and the
  actual MLD request/set-config refusal. They do not execute the ubus method
  dispatchers for the other operation labels.

## Integration And Identity

Run from `/home/captain/W1700KNPU`:

```sh
python3 -B tests/wifi/test_mld_transaction.py --require-source-lock --expect-source-sha c5db50945a641ab94a31ff11de143fa28d187b046fd4adb7bdb15ea3c0086212 --write-receipt
```

Without `--write-receipt`, execution is read-only. Default runs record lock
agreement without requiring it, permitting the parent's in-progress source
edits. Final integration must use `--require-source-lock`; update the optional
expected hash only after reviewing any later source change. Every run rejects
source or source-lock changes occurring during execution.

Prepared source SHA256:
`c5db50945a641ab94a31ff11de143fa28d187b046fd4adb7bdb15ea3c0086212`

Harness SHA256:
`6f3e5ba28dbf259ac62c0d378cb60f313859f21fa1d262d0944ffad95d08f5fd`

`transaction-tests.json` pins the full source, source lock, runtime, harness,
generated runner and each extracted helper, with per-case traces and mutant
failures. Counts exclude failed mutant executions.

The original worker wrote only this report, that receipt and `tests/wifi/test_mld_transaction.py`.
Parent integration subsequently added the actual SSID helper dependency,
replayed all scenarios against the SSID/load-error corrections and updated these identities.
These existing transaction fixtures do not declare SSIDs; the separate
`test_mld_ssid.py` suite covers SSID policy and preservation on stale rejection.

During the original worker pass, only those three files were
written. Production source, patches, source lock, membership tests and canonical
ledger are unchanged by this worker; parent owns integration/ledger updates.
No router, remote, browser, build, image, flash, NPU, commit or blocked-operation
retry occurred. Full hostapd/ubus/netifd lifetimes, missing-delivery timeouts,
driver behavior, regulatory behavior and actual-client operation remain outside
this proof.
