# Retained RX-Event Descriptor Backing

Status: integrated into canonical source and a complete, unflashed image.
Actual-C and current raw-native qualification pass. Full NPU implementation
and physical/router/client acceptance remain incomplete.

## Implementation

The actual mt76 queue allocator now requests provider-owned backing for the
specific NPU TXFREE/RX-event queue before queue address publication. The checked
provider retains its CPU pointer, full DMA handle and 8,192-byte extent in the
already exposed lifetime. Allocation requires 512 descriptors of 16 bytes,
the bound endpoint, NPU DMA device and matching held boot/nonce/BAR/history.
Fresh STATUS and complete allocation/plan/mailbox rechecks precede outputs.
Only EOPNOTSUPP retains the original managed-allocation fallback; other errors
never allocate managed replacement backing. Lost provider and duplicate queues
reject. Partial allocation, lost STATUS, later queue failures and detach retain
the backing and references. No physical retirement permission is added.

Later TX allocations reject RX DMA-alias and CPU-backing overlaps, follow the
accepted RX serial, and recheck the captured RX record and flags before outputs.
The original BAR serial remains pinned. Early malformed arguments preserve
outputs; an already latched failure precedes device-state validation under the
session lock. Wire/private cold history and raw CODE/DATA are unchanged.
This does not yet enroll the RX-event record in the native API22 contract.

## Qualification

- Actual provider/wrappers, mt76 hook/queue allocator and mt7996 TX caller C:
  115 cases, seven rejected mutants and address/undefined/leak sanitizers pass.
  Queue reset/register, entries, page pool, WED, DMA backing/references and
  transport are modeled. The mocked hardware initializer returns EIO by design.
- Fresh endpoint/request/probe/boot/memory/provider/TX-lifetime regressions and
  21 nonzero unit tests pass. The boot test now accepts a pinned prepared header
  instead of depending on a build directory during reconstruction.
- Canonical source replay verifies 63 OpenWrt plus five LuCI files. Full world,
  FIT/model/board/firmware, 218 packages and 78 module ABI checks pass. Identical
  raw builds with the same original-input paths pass all 16 image groups.
- Strict source delta: 367 lines, zero errors/warnings/checks. Headless Ghidra
  decompiles all 60 executable functions with zero failures, static only.
  All 43 named executable ELF functions are covered.
  REA analyzes the packaged allocator's complete 1,136-byte body. Its complete
  local evidence and snapshot are preserved; no original module bytes changed.
- Actual pair loader passes 273 matrix cases and seven exact-pair cases.
- Actual allocator/STATUS/client C with the raw RV32 peer passes with one retained
  RX-event allocation and six TX allocations. Both TX bands complete all six
  API21 phases/53,260 protected-byte effects and 76 guard/fault controls; earlier
  35 indication/28 TX/28 GET controls pass. Fourteen native mailbox/TX records
  are enrolled; the RX-event record is not yet enrolled for native API22.
- Final verification checks eight primary receipts and 266 current input hashes,
  plus the same-input raw comparison. No documentation-only exception is needed.

Jev contributed routing/guard and claim checks. Its final STATUS-before-output,
fallback and exposed-cleanup judgments were Noul0.93/0.91/0.94. The finite partial
index claim was supported with confidence0.89; full implementation/physical
acceptance was not established with confidence1. Raw distributions are retained;
deterministic tests and byte/input checks establish the scoped acceptance.

## Original PCIe Effects

The fingerprinted original API0 callback was observed over 64 vectors:
54 returned, ten faulted, with nine store sites. Selectors 0/2 publish DATA
pointers and immediately write host pointer+8 with 1,535/1,023. Selectors
5/6/7/8/10 publish the five pointers used by selector 15. The wrapper can return
success for unsupported selectors without stores; invalid pointer cases can
mutate metadata before faulting. These are counterexamples, not admission.

Nine sequenced index probes execute the original pointer callbacks and then
selector 15. It writes pointer+8 for selectors 5/6/7/8/10 in order with
255/511/1,023/1,535/(DESC10_count-1). Only the existing DESC10 count is modeled;
0/1/512/65,535 and each missing pointer are covered. A missing pointer retains
the preceding zero-to-four register writes; no rollback occurs. All declared
other DATA/host bytes and original CODE remain unchanged. This establishes
additional ownership dependencies, not candidate/hardware success.

## Artifacts And Remaining Work

```text
FIT f185a7319fdc65230240d3b120450b2e3093d89270df751370f762fd3b25a87e
PROVIDER d2ec1b562fb1f5418e0789fab2592666602057b5bb4e9cb421401b4a7870db8f
CODE 32b3506a67e498a1049b37a51cb5caa0ca2f1b7eeb87762028017fa81f5372df
DATA 402cce5fe187b9d29d2f3d03e467af671527fdc75c2f120c5e96383877f96866
SOURCE LOCK adcfc0a2227d843e9d8456732538b3323a19c0694aa9497c3f46a62894d513f0
```

The prior 9d1fa30d image plus seven companions are hash-verified under
.local/npu-rx-event-20261013/pre-rx-event-image. Older images, calibration,
bootloader/recovery data and private device backups are untouched. No router
contact, flash/reset, Wi-Fi/power change or subagents occurred.

Enroll the real RX-event record and own API22 metadata, authenticated
DESC10/shared TXDONE/PKT/SKB paths, PCIe pointer/
index effects and INODE/final IRQ activation. Complete the remaining owners,
workers/hot/postgate, independent backing/exclusion/coherency, drains/retirement/
removal/rearm/recovery, exact-image boot and real clients. The full goal stays open.
