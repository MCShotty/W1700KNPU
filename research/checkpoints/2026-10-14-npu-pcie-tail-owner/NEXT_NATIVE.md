# PCIe Tail Native Binding Contract

The portable owner and store assembly now live in the canonical source/tests
and the normal22-object build. The older native jobs are terminal and their
producing cohort is preserved. Current qualification is in
../2026-10-15-npu-owner-promotion/REPORT.md; no permanent alternate mode exists.
This contract does not authorize release, worker startup or physical acceptance.

## Verified Store Boundaries

The42-case original-callback/assembly probe executes the exact original store
opcodes. Six-byte detours cover compressed stores followed by a complete
four-byte AUIPC; four-byte detours cover the complete original instruction pair
or full store. Never split the following AUIPC or replay it at the new PC.

| Store PC | Detour Bytes | Displaced Continuation | Original16-byte Frame At Store |
| --- | --- | --- | --- |
|8400ba0c |4 |8400ba10 |ra/s0/s1 remain saved. |
|8400ba18 |4 |8400ba1c; replay saved-s1 load |ra/s0 restored, s1 still saved. |
|8400ba24 |4 |8400ba28 |ra/s0/s1 remain saved. |
|8400ba30 |4 |8400ba34; replay saved-s1 load |ra/s0 restored, s1 still saved. |
|8400b9ae |6 |8400b9b4; reproduce AUIPC result3e9029b0 |s0 restored; ra/s1 still saved. |
|8400b9c0 |6 |8400b9c6; reproduce AUIPC result3e9049c2 |ra/s0 restored; s1 still saved. |
|8400b9d2 |6 |8400b9d8; reproduce AUIPC result3e9029d4 |ra/s0/s1 restored. |
|8400b9ea |6 |8400b9f0; reproduce AUIPC result3e9029ec |ra/s0/s1 restored. |
|8400ba00 |4 |8400ba04; replay original16-byte stack pop |ra/s0/s1 restored. |

The staged native-tail-stores.S implements these paths, full volatile-register
save/restore around guards, fences, original store opcodes and frame-specific
failure unwinds. The original callback can return1 even after the inner helper
failed. Its return alone must never advance an outer owner.

## Admission And Live Prior State

1. Extend the actual server/client/prepared-provider history for the exact
   three-command order: header10/API0 TX0+0x160, header12/API0 TX2+0x110, then
   header1f/API0 zero. Require the completed RX-event/DESC10/PCIe10 prefix,
   independent finished TX owner, held BAR/nonce/boot identity and exact plan.
2. The current npu_emulation_desc10_prior_live is deliberately restricted to
   selector10/API0 with RXsteps2. It cannot validate these later commands.
   Factor/reuse its immutable prior-state checks with an explicit authenticated
   successor history. Do not temporarily forge SETUP back to an older command
   or broaden the existing helper into an unchecked selector whitelist.
3. Preserve callback-slot identity, original lock18, masked IRQs and the whole
   held setup snapshot. Keep existing callback routing for selector10 and
   unrelated previously supported page/indication callbacks. No recursive
   wrapper fallback and no clearing another callback's lock/running marker.
4. The new reader must bound all nine target cells, five pointer metadata cells
   and DESC10's two-byte count. Revalidate original typed allocation definitions,
   complete BAR extents, completed owners and exact before/after snapshots.
5. Capture neighbors for every target; aliases/overlaps must be explicitly
   reconciled, not excluded. Commit each possible effect before its store;
   publish only after exact value/width/address/readback checks. Retain partial
   captures, reservations and writes on all failures, including unlock/reply.
6. Instantiate the owner and link the real reserve/publish guards into a new
   component. The current ABI probe links explicit guard stubs and proves no
   ownership admission. Integrate image component/hook width/source closures,
   normal archive, exports/source lock and exact pair/provider/FIT checks.
7. Cover original full-caller success and early/late faults, wrong HIF operands,
   IRQ/neighbor/store/readback mutations, lost/mutated replies and native mutants.
   Compare all protected memory against pre-state plus request-derived effects
   and sequence. Keep the fresh caller distinct from restored-prefix fixtures.

## Following INODE Contract

The new original-prefixes-q1 fixture executes the original type109 lookup and
gets fixed L2 address3e8bc470 with no memory writes. This is not a dynamic heap
allocation record. A native binding must verify the actual paired-CODE fixed
definition and metadata pointer3e902ac0, full4104-byte extent and retained
storage/exclusion; a nonzero pointer is insufficient.

Selector2 makes1030 effects: two four-byte run flags, one byte flag,1026
four-byte ICV clears, then the final byte at3e9046f7. Selector7 makes six flag
stores. Four nominal12/24-byte frames and all1036 interrupted-write prefixes
match whole DATA/ICV-neighbor memory. Interruptions are synthetic pre-instruction
cuts, not actual bus/concurrency faults. Run flags precede the clear, and no
flag/callback reply is a hardware ready/drain witness. Final IRQ, workers/hot
paths, lifecycle/physical/recovery/boot/clients remain separate open requirements.
