# Checked cold page ownership core — 2026-10-01

Continued from remote-verified main `eabfedbfb39fd387677a71fd71d6747d55aaed87`.
Preserved and completed the existing pending cold-page implementation. No flash,
router/radio/security change, physical reset or merge occurred.

## Implemented scope

`firmware/npu/cold-page.c/.h` provides a shared host/RV32 cold ownership core
for 8,192 IDs of 128 bytes, with an immutable backing plan and a retained claim
bitmap. Fresh zeroed storage and nonzero epoch are required; an existing lifetime
cannot be reinitialized. Invalid backing bounds, corrupt metadata, exhausted
queue, invalid ID and duplicate claims fault the lifetime without releasing
ownership. Stale epochs cannot claim or disturb the current lifetime.

Added a cursor-history invariant: matching caller/private cursors must also
equal the retained claim count modulo 8,192. A corrupted cursor copied into both
snapshots previously passed the head-match check. The new regression and mutant
exercise this distinct case. A late fault after commit retains ID, address,
next-head and claim state with `committed=1`; the caller must retain ownership,
deny readiness and finish native-head handling under its serialization contract.

The core builds with the other ten RV32 components. It is not installed in the
vendor firmware or substituted into native callbacks. Queue snapshot validation,
exclusive serialization, coherent fresh storage, actual backing reservation,
native head commit and barrier/lifetime publication remain caller obligations.
Geometry validation is not containment or safe reset/reclamation.

## Validation

- Actual host C and RV32 instruction execution match an independent state/set
  oracle for 5,702 calls, including 5,376 nominal claims and 294 controls.
- ASan, UBSan and LeakSanitizer pass. Ten deliberate mutants are rejected,
  including omission of cursor history, bounds, duplicate/epoch checks, retained
  claim metadata and fault closure. RV32 late-fault injection retains ownership.
- Current 50-hook native boot parks all eight harts with modeled platform inputs.
  Direct RX0/RX2 invocations under a modeled callback lease return success and
  publish readiness; their statistics allocations reach the original unchecked
  type-10/type-9 fallback, adding two allocator records. Strict transport denies
  setup. The new ownership core is not used in that caller probe.
- Existing loader-memory suite passes 273 loader cases, 165 added load cases,
  three original controls, nine mutants, 6,174 retry and 44 V2 cases with leak
  checks. Eleven RV32 components compile with warnings treated as errors.
- Offline image verification passes FIT/board/firmware, 218 packages and 78 module
  ABI checks. The FIT remains
  `230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe`.
  The archive is a separate compiled artifact, not a new flashed implementation.

Initial bare-system Python invocations lacked Unicorn; corrected invocations use
the existing pinned `.local/npu-reset/python-lib` directory. An earlier pending
caller assertion incorrectly expected a checked allocator hold: original
statistics callers actually route to the unchecked fallback. The corrected
native replay records that behavior instead of treating the old assertion as
proof of a firmware blocker. Prior exploratory receipts remain local.

The earlier draft described TypeSafe egress as blocked. That status is now
superseded by a successful official local helper call using `jev-1.13.0` and
five bounded semantic checks. Reinitialization refusal receives Noul0.97 and
duplicate retention0.95. Choice checks select retained core commit, original
allocator fallback and component-pending-callers, each with confidence1.0.
The actual request, result and raw probabilities are retained as `jev-request.json`
and `jev-result.json`. This session initially received an automatic approval rejection for its scoped
claim-review egress. After the user explicitly approved that payload/destination,
the helper successfully returned `jev-1.13.0`: core scope supported (0.93), caller
scope supported (0.90), and complete setup/safe physical reclamation contradicted
(0.94). Request and response are `jev-claims-request.json` and
`jev-claims-result.json`, with 14,364 input/135 output tokens and 799 ms API latency.
That request contains earlier same-behavior receipts/header commentary; current
core/caller source hashes are separately verified in the final receipts. Syntax and
model availability were checked against the official
[API](https://docs.typesafe.ai/api) and [models](https://docs.typesafe.ai/models).
These judgments check scope; tests and runtime evidence remain the proof.

## Replay and next gates

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_cold_page.py --name fresh-core
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_cold_page_caller.py --name fresh-caller
make -C firmware/npu
```

Next compose checked page claims with validated native queue snapshots and
ownership-preserving native publication/error handling; review the statistics
fallback rather than assuming it is already covered by the startup allocator.
Full strict DISCOVER/setup/BIND, fresh loader identity/storage publication,
postgate consumers and physical DMA drain/teardown/rearm/client acceptance remain
open. Existing cloud `6abd366c...`, WSL `277abd0b...`, later FITs and protected R1
remain distinct. Generated binaries, credentials and private backups are excluded.
Publication is authorized on a new draft PR branch, without merge or flash.
Verify the remote commit and CI after publication; local checks are not CI or
physical proof. Eight build-runner tests pass. Raw API JSON retains its original
CRLF bytes; whitespace validation uses Git's cr-at-eol setting for those receipts.
