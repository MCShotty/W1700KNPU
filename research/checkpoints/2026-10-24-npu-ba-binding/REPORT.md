# W1700K Retained Host BA Association

Classification: progress toward the full NPU goal, not completion or hardware
acceptance. Base af4bb8b. Exact sources, artifacts and limits accompany this
report in EVIDENCE.json; private evidence stays local.

## Implementation

Status0 retains the actual RX creation serial, original active WLAN/TID and
primary WCID in a separately preallocated1025-entry table attached to the pinned
reset owner. Core association fields are written only for a previously unbound
entry. Exact duplicate status can succeed; a proposed conflicting identity never
overwrites the original and retains the first raw serial/tuple/error.

DELETE requires a matching retained association and snapshots its serial, without
consulting the currently published RX object. Work checks the snapshot and tuple
before issuing existing reset-generation/ticket operations. These identities
remain distinct. Missing/mismatched bindings fail closed and stay retained; no
provider-loss CPU fallback is introduced. Closed valid metadata is retained but
cannot grant new admission. Owned status is not silently discarded by mode changes.

Both objects allocate before publication. Failure unwinds both; published table,
owner and module/device pins remain retained. Compile-time bounds preserve the
64KiB owner and add a separate32KiB table bound. Event code performs no explicit
BA allocation, pin acquisition or sleeping provider/MCU operation. Framework
queueing/locking and concurrency remain outside this host proof.

## Verification

- Joint actual selected RX creation/shutdown/stop, AMPDU, per-link MCU BA loop,
  status, DELETE and complete retained-owner C:23 measured setups/14 compiled
  mutation controls under unchanged ASan/UBSan/leak detection. Original/primary
  identity, replacement/conflicts, first unseen late status, closed/missing/
  stopped/mode-changed status, invalid DELETE, serial corruption, all reset error
  stages and dual-allocation unwind are exercised. Every control reaches its
  intended assertion, not a sanitizer or compile failure.
- Separate current creation19/12 and BA18/six remain. Retained worker now passes
  23/eight: it adds second-allocation failure and explicitly models prior status
  enrollment, preserving previous worker/IRQ assertions. It is not relabeled
  actual creation/status execution. That composition is covered by the new suite.
- Current provider/client/broker/native host C passes6150 resets across three
  profiles/two reset-journal generations,12 negatives/three controls; broad456
  allocation/fault cases/four controls; linked callers1090/seven;142 observer/
  tooling/inventory/phase units,zero skips. These distinct host scopes do not
  constitute joint kernel, physical transport or MCU proof.
- Four AArch64 modules final-link with GCC14.4.0/Linux6.18.52, producer5182ec7d,
  lockcc998c1f,31 component mappings,5 kernel/330 mt76 sources and16 cumulative
  mt76 outputs reconstructed at fuzz0. Binding symbol and three typed edges
  resolve. Only mt7996e changes; original102685 kernel/516 prepared-mt76 entries
  remain unchanged. Private copied-cache build:236MiB cap/256MiB output ceiling,
  zero swap, same compiler configuration. No fresh world or current full image.

## Remaining Boundaries

The first unseen cookie-less status injected after replacement still binds the
new RX object. The retained table prevents overwriting an already known binding;
it does not authenticate that first association. Real current-firmware producer
reachability/order is not established. Qualify a current-build firmware cookie
or true late/reuse fence before admitting session reuse. One-shot host retention,
reset generation1 and generic MCU ACK are not substitutes.

Close rejects later binding admission but does not join an already accepted
status writer. The parser performs its final TID-protected ID write after the
binding helper releases owner lock; an already accepted writer may finish after
close. This is a static CPU-lifetime boundary, not a demonstrated physical race.
Full hot CPU join, transport admission, production retirement/rearm and physical
DMA drain remain. Framework/RCU/locks/references, provider RPC/backing, IRQ-abort
effect and physical MCU are models in the new joint test.

Both complete native replay verdicts, current full image, cold/fault/HIF2,
hardware/client/performance/stability gates remain. Existing parked guards stay
unchanged. No new hardware access, module load, image/flash, VM/global-policy
change, server signal or subagents occurred.

## Preflight Sequencing Correction

A Windows RAM check reported2255618048 available bytes, below the unchanged
2281701376-byte analysis threshold. The outer command sequence nevertheless
dispatched the small128MiB installer. Its native guest/storage guards passed;
the source install completed. This is a sequencing error, not a passing Windows
preflight or a permitted margin waiver. Fresh post-install headroom and installed
source/all16 cumulative outputs were revalidated; no earlier receipt was rewritten.

All subsequent native auxiliary dispatches require a passed, phase-matching
Windows receipt no older than60seconds in the controller itself, with the same
2GiB+128MiB threshold. Outer dispatch also stops on nonzero preflight. Four
intended-failure controls prove missing, mismatched, stale and insufficient
receipts cannot dispatch child work. Native full-cap/storage checks, both replay
caps/limits and reserved margins remain unchanged. Initial error data stay kept.

All earlier evidence/input versions and protected images remain hash-bound.
Both original replay PIDs/start ticks/invocations/input graphs stay unchanged;
CPU progress advances. Neither replay was restarted for an observation timeout.
Jev supplied bounded semantic checks, including uncertain results followed by
focused evidence review; tests and direct code inspection establish their own
limited proof scopes. Full NPU work remains active.
