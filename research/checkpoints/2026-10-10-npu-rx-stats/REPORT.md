# Checked RX Statistics Callers - 2026-10-10

Continued from main `5816c6daebfa757ecbc889edeab1116975a3c826` toward the
full NPU implementation. No flash, router access or physical changes.

## Implementation

The canonical native allocator dispatch now routes the reviewed RX0/type10
return site `0x8400a3ae` and RX2/type9 site `0x8400a39a` through the actual
checked allocator in a held, first-epoch coordinator callback. The original
tables define both statistics blocks as 1,000 bytes. Successful/cached allocation
retains existing core metadata rules; a late fault does not erase a committed
record. Startup and unrelated native callers retain their existing routes.

The new native binding verifies allocation identity and guards the statistics
continuation before its pointer store and 250-word clear. Failure unwinds the
statistics and dispatcher frames before RX descriptor initialization. A held
callback may return NULL only while its installed unwind guards are in use;
otherwise allocation failure stops in the existing fault hold instead of
returning NULL to the unguarded original clear. Two readiness guards and the
outer callback propagate failure while retaining the active lease/resources.
Other selectors delegate to the page/TXDONE binding.

The active callback context accepts the already-bound V2 coordinator nonce;
it is not the unbound idle reservation phase. Coordinator identity, cold epoch,
closed admission, one active lease, complete reservation bootstrap and all eight
parked/unrefreshed workers remain required. Actual transport/session authority,
backing, locking and cache coherency remain platform contracts.

## Evidence

- `rx-result.json`: 60-site composition executes original RX0/RX2 initializers,
  producing 1,536/1,024 descriptors and exactly 250 clear stores per statistics
  block. Every descriptor pointer/status/ID and clear address/size/value matches.
  An independent full-824-byte metadata prediction verifies both allocation
  records. Neither reviewed statistics call reaches the unchecked fallback.
- Twenty-six isolated controls cover denied locks, corrupt metadata/lock ID,
  wrong type, changed epoch, post-commit release fault, pre/mid-clear and
  pre-readiness faults, partial packet pools, wrong returned allocation identity,
  and zero/oversize counts. Late release preserves one record without pointer
  publication, clear, descriptors or readiness. Mid-clear changes only the
  retained statistics block before stopping RX. Partial pools retain their
  consumed IDs/descriptors/head and return failure; no release/reclaim is added.
- Six mutants are rejected: missing statistics unwind (native NULL-clear trap),
  dispatcher/ready guards, unconditional outer success, omitted allocation
  identity and omitted count limit. The NULL trap is a negative emulator
  control, not a successful execution or hardware test.
- `caller-result.json` confirms the default 50-site nominal caller trace now
  uses checked statistics allocation and adds the same two records.
- `page-result.json` preserves the 54-site page composition: 1,792 claims,
  48 controls and six page-binding mutants pass.
- `startup-result.json`: seven cold allocations, 18 faults, 36 unrelated
  fallback cases, five bridge cases and eight mutants pass. The verifier accounts
  for the new four-byte guard state; startup mutants are scoped to their handler.
- `postgate-result.json`: 19 guards/nine mutants pass; hart7 still reaches its
  original outer boundary, while harts1-6 await later host setup. The historical
  `eb31bae` baseline uses its paired C/assembly, not newer callback assembly.
  Eight build-runner tests pass.

The first callback guard incorrectly required an unbound nonce; the current
V2 flow binds before these callbacks, and that phase assumption was corrected.
Fault injection originally selected an earlier lock release, then exposed a
denied-owner readback leaking between controls; the final run isolates and
targets each case. Failed exploratory outputs are not final acceptance receipts.

Only native binding/test code and documentation change. The shared allocator,
provider/kernel source lock, vendor CODE/DATA and built FIT are unchanged; no
new world build or physical boot is claimed. Final inputs/artifacts and copied
receipts are independently hashed in `verification.json`/`file-manifest.json`.

Official Jev pre/post checks classify the active callback/native unwind boundary.
Post-checks select checked-active allocation with confidence1.0 and native
statistics composition with confidence0.99; retained-record Noul0.90,
mid-clear boundary0.87 and NULL-unwind0.78. The post payload retains the earlier
successful same-binding receipts; final extent assertions and source hashes are
in the final replay receipt. These are scope judgments, not deterministic or
physical proof. API/model syntax was checked against official
[API](https://docs.typesafe.ai/api) and [models](https://docs.typesafe.ai/models).

## Remaining

Strict DISCOVER/setup/BIND and real loader/storage integration remain open.
Complete packet-ID exclusive ownership, hot lifecycle and the other worker/
postgate paths, then physical backing/exclusion/coherency, DMA drains/recovery
and real-client acceptance. Native instruction composition with modeled locks,
parking and a direct held lease is not a patched vendor blob or stock parity.
Protected/private inputs and generated binaries stay local.

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_rx_stats.py --name fresh-rx-stats
```
