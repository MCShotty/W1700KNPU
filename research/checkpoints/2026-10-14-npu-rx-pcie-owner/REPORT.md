# RX-event PCIe Owner - 2026-10-14

## Scope

Full NPU reverse engineering and implementation remains the goal. This step
adds a normal portable owner and final DESC10 memory verifier for the actual
selector10/API0 tail. It does not bind that command to native instructions yet.
No native admission, full sender acceptance, world, image promotion, physical
execution, router action, subagents, commit or push is claimed in this step.

## Implementation

`firmware/npu/cold-rx-pcie.c/.h` is the20th normal portable Makefile object.
The136-byte plan includes the full prior DESC10/RX/TX/boot/BAR plan. Its168-byte
one-shot owner derives the pointer from the retained BAR plus0xd4590, bounds
the complete12-byte register extent, and requires completed matching DESC10,
RX and PKT ownership plus ready1 at each entry. Reservation checks the exact
metadata3e902a90, width4, value and captured preimage; it records reserved and
committed1 before the caller store. Readback gates publication. Failures latch
a fault without resetting counts. There is no reset or retirement API.

`npu_cold_txdone_memory_live` checks final memory, not all25606 transient stores.
Its bounded reader covers20998 cells: all512 final descriptors and IDs,
2048 temporary IDs,8192 SKB states,8192 ordered queue entries and six final
metadata fields. Free queue IDs are checked in a single linear scan. Completed
owner liveness is checked before and after reading. Original locks, actual
typed allocations, mapped spans, session/nonce and neighbors still belong to
the future native binding; a supplied reader is not physical proof.

Cold server/client/provider ordering is deliberately unchanged: selector10/API0
remains unsupported until it has its actual effect binding. The full extracted
RX-event sender still sends API22, DESC10 and the PCIe tail; it is not shortened.

## Verification

- Exact normal-Os objects plus host C:226 compared calls,213 controls, eight
  rejected mutants and ASan/UBSan/leak. Prior owners are constructed using
  their real portable APIs. The20998-cell address/width/value read trace agrees
  with an independent literal final projection of the original store oracle;
  whole prior logical memory and owner state match host/RV32 and stay unchanged.
- Controls cover all34 stored/incoming plan words, malformed owner headers,
  missing prerequisites, wrong epoch/BAR/operand/preimage/address/width/readback,
  repetition, late prior faults, missing publication, read failure/corruption,
  end-of-read owner mutation and beginning/middle/end corruption of every array.
  Read-only liveness does not fault or modify the pointer owner. All three
  modeled RX DMA aliases retain the same derived PCIe value.
- Current DESC10 regression:3656 compared calls/3541 controls/nine mutants/
  sanitizers, using the newly compiled normal cold-txdone.o. Twenty-four
  observer/capture/memory-recorder/transaction-oracle units pass.
- Two fresh raw builds repeat exactly:17 components/145 hooks/private388,
  CODE907380 bytes SHA256
  ab78628bd74bd8a4504db032712fe49825986e029c4a939ce6244594484023a0;
  DATA25728 bytes SHA256
  6bc539e756a2d691cba33150b5d5f812df5b4d8c0d8c21efb713d8a7afb38f39.
  All17 image groups pass without skips. The new pointer owner is not a native
  component yet; the existing DESC10 component contains the new memory helper.
- Checked loader60 cases/eight mutants pass for this pair. Six receipt input
  maps and compiled binaries were hash-checked against228 current files, with
  no conflicts or mismatches. This is local input closure, not canonical export
  or a packaged world-source lock.
- Fresh original API0 observation:64 vectors,54 returned,10 unmapped-access
  faults and nine index sequences. Selector10 still accepts unchecked0/1/
  UINT_MAX with one metadata pointer store. The modeled original runs are not
  ownership acceptance, and the non-returning cases are not passes.

All jobs above are terminal. First owner test stopped before execution on a
fixture-only memcpy link dependency; retaining normal-Os firmware objects and
using the established O2 fixture settings resolved it. The expanded q3 run
found an overstrict test expectation for deliberately corrupted counters; q4
correctly checks that rejection retains those corrupt values. Neither failed
attempt is relabeled a pass. Existing older native receipts retain their
producer identities; source changes are not retroactively relabeled current.

## Jev

Actual Jev1.13.0 ran five design and three verification judgments; requests and
raw probabilities are retained locally. Metadata-pointer routing had0.99
probability; unchecked-return ownership was contradicted with confidence1.
One unwind judgment returned0.22 and was not adopted: original Ghidra assembly
explicitly shows ra/s0 restored before ba88, then s1 and SP+16 afterward. The
instruction contract, not that semantic judgment, determines the future unwind.
Post-change retention support was0.73/confidence0.59 and is not proof; the
compiled transition tests establish their scoped software behavior. Native/full
sender and physical claims were contradicted with confidences0.97/0.94.
Credentials stayed in memory. No alternate provider or subagent was used.

## Next Native Binding

1. Expose completed DESC10 liveness separately from running API1 context. Pin
   its actual captured plan, typed allocations, metadata and final memory.
2. Extend prior-owner helpers so3072 claims for API0 derive from completed
   DESC10, not a mutable count or API0 whitelist. Earlier commands keep their
   existing2560 checks. Avoid circular liveness calls or forward-symbol guesses.
3. Instantiate the168-byte owner in a verified free component window. Original
   callback8400fdc4 and store8400ba88 must be bound; preserve the partly-restored
   16-byte frame and restore s1/SP correctly on failed reservation/publication.
   The wrapper's unconditional return1 must not bypass owned completion.
4. Extend server/client/provider history together, then replay the actual full
   three-command sender with whole protected memory and native pre/late faults,
   ABI, neighbor and mutation controls. Capture a fresh current-input prefix;
   older captures cannot silently bypass changed-source identity checks.
5. Other PCIe selectors0/2/15, INODE/finalIRQ, owners/workers/hot, physical
   backing/exclusion/coherency/drains/retirement/removal/rearm/recovery, exact
   image boot and actual clients remain required. Then protect the current FIT
   and seven companions before export/world/provider/FIT/Ghidra/publish work.

FIT82b1563a/providerf163e26e are unchanged and unflashed. Canonical source export,
world and mainline publication remain pending. Source edits are uncommitted.

## Local Receipts

- .local/npu-pcie-tail-20261014/owner-q4/result.json
  SHA2565d6227f53f9ce1527e5d3596dcafe4cacb311fd40a5df3ad5a78d39218fffa7d
- .local/npu-desc10-owner-20261013/pcie-memory-q1/result.json
  SHA256a9d91d8b8d32a7e02021fd5b837e99225b80c033e2e33a5a48adb78bea6a83e7
- .local/npu-loader-publish-20261010/pcie-owner-q1/result.json
  SHA256c0409e50f598b34783aba17fdefb086b7b12a1ee6bd54720c78e8021ba1f808a
- .local/npu-pcie-tail-20261014/image-q1.json
- .local/npu-pcie-tail-20261014/pair-q1/manifest.json
  SHA256311b46df212bb4faea2a3c4aecc11e3f800302c011e6d3d9935e30e311fb5b04
- .local/npu-pcie-tail-20261014/pair-q2/manifest.json
  SHA256074c13e80c2ef1a707f15c301d30534555ec9a5fc09c892b13d5e726423b3310
- .local/npu-pcie-tail-20261014/original-api0-q1.json
  SHA2569da7000de94a666162591879aab0ae35f587721ceec1944f768e882125e6980c
- .local/npu-pcie-tail-20261014/jev-design-request.json and jev-design-result.json
- .local/npu-pcie-tail-20261014/jev-verification-request.json and jev-verification-result.json
