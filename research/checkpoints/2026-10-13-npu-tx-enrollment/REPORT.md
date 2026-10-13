# Native TX Enrollment And Portable API21 Owner

Qualified offline on 2026-10-13. The full NPU objective remains open.
No subagents, router contact, flash, reset, Wi-Fi reassociation or power changes.

## Implementation

The actual retained allocator enrolls eight mailbox addresses and six fixed-size
TX DMA records before returning handles. Fourteen authenticated metadata
exchanges reuse the boot/nonce/epoch and 80-byte cold envelope. Native state
pins BOOT/BAR, record order, geometry and pending candidate before acknowledgment.
The Linux executor independently pins order and retains its accepted prefix.

Native private history grows from 120 to 360 bytes, zero-filled in raw CODE.
The wire ABI is unchanged. Mailbox0 is exactly the published bootstrap request;
other mailbox and TX ranges are checked against external BAR/BOOT/DMA aliases.
Equal low bits of raw SRAM/L2 and transformed DDR do not prove physical alias
equivalence or independence. Native destination ownership is separate.

Mailbox/TX identities are captured, STATUS is required before and after
enrollment, and endpoint/boot/nonce/bound-serial/plan/records are rechecked before
publication. A lost reply can leave native progress ahead of the CPU cache;
both prefixes and exposed resources remain retained, without replay or retirement.

The 17th RV32 archive object implements the complete portable six-selector
store owner: 53,260 stores, arbitrary preimages, reserve-before-store and
mixed-width/full-span readback. Its 213,200-byte state is not instantiated or
bound to original native API21 hooks. Raw composition remains14 components and
77 hook sites. API21 still denies; metadata enrollment is not callback admission.

## Evidence

- `packaged-owner.json`: actual packaged RV32 object/host C,106640 calls,
  all53260 stores,80 controls/seven mutants. Independent original-derived oracle;
  caller backing and writes are modeled, not native callback/store-hook execution.
- `wire.json`:1203 cases/25 mutants, including record order, pending-plan
  tampering, output preservation and every enrollment lost-reply position.
- `lifetime.json`: actual allocator/caller C,113 cases/nine mutants. Partial
  allocation, late identity drift, all STATUS/enrollment fault positions and
  one-shot output are covered. Exposed frees remain zero.
- `native.json`: six actual-C allocations and all14 records matched executed
  raw RV32 state before initialization. Exact40 lease pairs, offload/RX prefix,
  eight descriptor GETs and35 indication/28 TX/28 descriptor controls pass.
  Actual TX still stops at API21. Later sender handles remain synthetic.
- `publisher.json`:60 parser/publisher cases/eight mutants. `regressions.json`:
  endpoint/request/probe/boot/memory/provider checks, provider609/nine,21 nonzero
  unit tests and image/pair checks pass. Pair suite has15 active passes and one
  explicit repeat-build skip; no unrun repeat-build proof is claimed.
- `original-records.json`: eight original helper cases,512 records per band,
  4/4/4/1-byte stores, untouched tail bytes and partial metadata faults.
  This is not a six-selector original callback-hook replay.
- Source68 and nested kernel delta replay byte-equally. Strict driver
  checkpatch checks94 lines with zero errors/warnings/checks.
- `ghidra.json`:58 decompiled functions/zero failures; all42 named executable
  ELF symbols covered in the exact provider. This is static, not kernel execution.

## Artifacts

Current offline-qualified, unflashed FIT,26977098 bytes:
`69257a6bd5637e850198b0099a8413e2e1063d3055a388ab87ecab8dbbd67522`.
Gemtek W1700K FIT/DTB,218 packages,78 module ABI checks and17 RV32 objects pass.

CODE: `531dd36740c68db699992db7a4f6afbf64a731b63a536898a564ee54421393d7`.
DATA: `08630e0ed0661aa110d1fcce7db8841009ba0c5ee6c36c5a1dfb4da09959f9eb`.
Provider: `4127c399b2b04ffec02d6cb9d181c8f44b56dea303e2254455af670c8ea760f1`.
Source lock: `924b87f00c1610f2e234c8837a382e041728d7565289d62d59824d54771c537b`.

Prior6efaa878 and intermediateffbd4344 images plus seven companions each are
checksum-protected. Older/R1, calibration, bootloader, recovery and private
device backups are untouched. Preliminary failed attempts remain local and are
not counted as qualified receipts.

Jev supplied four real source-order/scope judgments. Its physical-alias answer
was not-established, not proof of separate backing. Raw probabilities are
retained; Codex wrote code and deterministic tools establish covered tests.

## Next

Bind the portable owner to original API21 callbacks/stores, preserving
GET5/SET0/SET5/SET10/GET7/SET2/SET7/SET12. Pin prior owners, exact typed tables,
metadata neighbors, full internal/L2 spans, TXPKT prerequisite, session and
original allocator lock/IRQ state. Do not whitelist callbacks from enrollment.

Then finish PCIe/INODE/TXDONE/final IRQ, remaining owners/workers/hot/postgate,
physical backing/exclusion/coherency/drains/retirement/removal/rearm/recovery,
exact-image boot and real clients. No receipt here proves physical containment,
DMA drain or full stock parity. Full goal remains active.

Reproduce using the retained test runners with fresh absent output names.
Use `PYTHONPATH=.local/npu-reset/python-lib:tests/npu` and freeze consumed inputs
during tests/builds. From this checkpoint directory, run
`sha256sum --check --strict CHECKSUMS.sha256`.
