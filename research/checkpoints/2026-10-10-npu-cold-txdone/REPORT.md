# Shared Cold RX And TXDONE Packet Ownership

Date: 2026-10-10. Base main: `510b7b7c2688d220ab9a960b53cc5a07681b69c4`.

## Implemented

The selected native packet binding now recognizes TXDONE return PC`0x8400b4e4`
alongside RX0/RX2 and uses the same retained PKT state. The guarded callback
delegates other selectors through the established statistics/page routes. Original
packet lock, TXDONE initializer, SKB reset and earlier SKB lock/temp guards still
execute; no successful helper return is injected. Failed takes/SKB steps keep
committed claims and leases while denying false outer success/readiness.

The TXDONE publication detour rechecks ownership before the original ready store,
not only after it. Shared liveness checks immutable state/private/BOOT plan,
native/private head, count/history and full bitmap population. Corrupted history,
an extra bit or changed plan cannot publish readiness-one and then hide it by
clearing the flag afterward. The original guard supplies its fault unwind.
There are still61 installed sites; callback/getter/publication targets are replaced,
not stacked. No portable core, state ABI, normal archive or kernel/provider change.

## Verified

- `txdone-result.json` is the final full-size run. Actual native RX0/RX2 prefix
  retains2,560 PKT IDs. Independent count1 and count512 TXDONE cases retain2,561
  and3,072 total IDs, respectively. Complete native SRAM/heap/L2/TXFREE/SKB contents
  match the independent original-code oracle. The complete2,076-byte packet state
  matches predicted retained bits/history, including the prior RX claims.
- Descriptor count/bytes, packet/head/statistics changes, actual lock28/19/20
  request/release ordering and native readiness-last are checked. Stack remains
  inside its bounded16KiB area; the guarded callback-local flag clears and the
  held active lease remains. Separate TXPKT SKB reset is not PKT reclamation.
- Twenty-five controls cover grant denial, bad/duplicate IDs, partial pool,
  committed claim/snapshot/publication/release faults, public lock mutation,
  both SKB lock failures, invalid SKB capacity, a fault during reset and before
  publication, corrupted count/head/bitmap/plan and malformed counts/framing.
  Partial exhaustion retains17 new claims/descriptors/head progress. Later SKB
  failures retain all32 new PKT claims/descriptors without readiness. Late single
  packet faults retain their claim and allowed head progress without descriptors.
  Whole native memory and exact private state are compared, including injected
  corruption rather than silently repairing or deleting it.
- Six mutants fail covered behavior: missing TXDONE owner route, publication
  guard, head/count consistency, bitmap population, plan identity and forced outer
  success. Each mutant restores named writable ELF objects across relocated
  layouts, preserving the RX ownership prefix rather than resetting or losing it.
- `rx-page-regression.json` passes both full RX rings/2,560 packet claims,
  1,792 independent BA claims with unchanged packet state,50 controls/six mutants
  and unrelated-getter routing. The new wrapper/publication checks preserve those
  earlier selected paths. `--quick` receipts are exploratory, not final evidence.
- Fresh offline FIT/board/218-package/78-module checks and eight build-runner
  tests pass. Twelve normal archive objects and archive identity read back
  unchanged. No new world build is claimed because this pass changes the native
  binding/test composition, not core/kernel/vendor build inputs.

FIT remains `230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe`.
`verification.json` seals current proof input/binary hashes and copied text
receipts. The initial descriptor-store observer used an arithmetic instruction
PC rather than the actual storePC`0x8400b4ba`; corrected before final proof.
Exploratory outputs remain local and are not substituted for final receipts.

Jev pre-checks select one shared PKT state and the retain-on-SKB-failure contract.
The initial post batch was uncertain about history/plan and is retained in full.
Focused source/injection/mutant checks give Noul0.85 for shared state,0.91 for
head/history,0.92 for bitmap and0.94 for plan publication denial. The installation
scope Choice is compiled/emulated, confidence0.94. All actual results use official
`jev-1.13.0`; probabilities/model/usage remain in the raw records. Deterministic
tests/source review establish their covered behavior, not a universal threshold.

## Real Installation

`INSTALL_TRACE.md` and `install-trace.json` identify the actual package/provider
copy path, sizes, startup ordering and modeled storage offsets. The recipe still
copies the vendor pair directly and does not install the component archive.
The3,084-byte DATA image does not cover modeled session/identity offsets0x6380/
0x63a0. Candidate CODE range fit within2MiB is not physical reservation/exclusion.

Next implement and replay the complete paired raw image, real cold-provider
containment/storage/fresh-identity publication and Linux strict caller wiring.
Other owners/hot lifecycle, remaining postgate consumers, physical grants/cache/
DMA drains, teardown/recovery/rearm and actual clients remain incomplete. No new
CODE/DATA installation, flash or hardware operation occurred; protected data
and rollback images were untouched. The full NPU goal remains active.
