# Original INODE Binding Contract

The portable owner and eleven store trampolines are now canonical normal-build
and test inputs; all older jobs are terminal. Current scoped qualification is
in ../2026-10-15-npu-owner-promotion/REPORT.md, without a separate feature mode.
Original owner/session guards are not
linked by the120-case ABI probe; no native admission is established by it.

## Original Stores And Frame

Every selected instruction is four bytes and is copied byte-for-byte into its
trampoline. Continuation is original PC+4; no following instruction is displaced.
The original helper frame is16 bytes with ra at12(sp) and s0 at8(sp).

| PC | Effect | Saved Frame State |
| --- | --- | --- |
|8400e178 | word3e9046ec=1 |ra/s0 remain saved. |
|8400e180 | word3e9046f0=1 |ra/s0 remain saved. |
|8400e18a | byte3e9046f8=3 |ra/s0 remain saved. |
|8400e196 | word at ICV cursor=0, repeated1026 times |ra/s0 remain saved. |
|8400e1b4 | byte3e9046f7=0, after full clear |ra/s0 already restored; stack frame remains allocated. |
|8400e0c4 | byte3e9046f5=0 |ra/s0 remain saved. |
|8400e0ce | word3e9046f0=1 |ra/s0 remain saved. |
|8400e0d8 | byte3e9046f9=3 |ra/s0 remain saved. |
|8400e0e0 | byte3e9046f8=3 |ra/s0 remain saved. |
|8400e0e8 | byte3e9046e1=1 |ra/s0 remain saved. |
|8400e0f0 | byte3e9046e0=1 |ra/s0 remain saved. |

Staged native-inode-stores.S/.ld at840f0000 implements temporary volatile save/
restore, reserve-before-store, exact original opcodes, fences, publish/readback
entry and frame-specific failure unwinds. The120 cases cover both argument
padding states, two register seeds, every site and first/middle/last clear
failures, before-store and after-store guard failure. Whole64KiB DATA/eightKiB
ICV-neighbor memory, code prefix, saved registers and original frames match.

The original callback returns1 in all120 cases, including inner failures. A
real outer wrapper must check owner reserved/committed/published/completed/live
state and all held context before accepting or advancing a reply.

## Required Real Guard Integration

1. Add exact authenticated selector2/API24/value0 then selector7/API24/value0
   order only after all three PCIe tail commands. Preserve80-byte wire framing
   and the existing24-byte INODE payload contract. Unsupported selectors remain
   denied; do not substitute MT7992's distinct profile or enable reset selector4.
2. Instantiate the4372-byte owner with188-byte plan; require completed matching
   PCIe/TX/RX/DESC10 owners, actual session/boot/nonce, exact prior histories and
   current held setup. Extend older prior checks through an explicit legitimate
   successor history; never forge SETUP back to an earlier command to pass them.
3. Verify actual paired-CODE fixed type109 at8401cfb8/base8401cfbc and the live
   metadata pointer3e902ac0. Its fixed address3e8bc470/full4104-byte extent is
   not a dynamic allocator record and must not alias earlier owned data.
4. Retain original lock/IRQ/exclusion, exact callback identity and safe stack
   bounds. Compiler frame4688 is not a full caller/reader/interrupt-chain bound;
   measure the actual complete native path before a stack-capacity claim.
5. Bound all metadata/flag/ICV reads. The dense clear has changing owned
   neighbors: prior published words are zero, later words retain captured
   preimages. Account for these exact coeffects, not a blanket unchanged-neighbor
   assertion. Mixed byte/word flags must preserve unrelated bytes/readiness.
6. Commit possible effects before each actual site, check exact width/address/
   value/readback and publish only under live matching owners/context. Some flags
   are idempotent; readback alone does not prove that their original instruction
   ran. Retain all prefixes after store, callback, unlock or reply failure.
7. Cover actual-caller success, per-phase first/middle/last faults, malformed
   metadata/count/address/width/value, neighbors, IRQ/lock/stack, nested late
   faults, lost/mutated replies and native mutants. Compare every protected byte
   against request-derived effects/sequence; keep restored-prefix fixtures
   separate from a fresh real allocator/caller proof.
8. Integrate normal source/Makefile/export/source lock, raw component/hook and
   provider/FIT checks, then mainline publication. The120 ABI cases and portable
   comparisons do not substitute for those real bindings or physical acceptance.

After this, final host IRQ handling is a separate provider/caller contract in
NEXT_IRQ.md. Worker/hot packet ownership, physical backing/cache/DMA/exclusion,
drains/reset/removal/rearm/recovery/boot/actual clients remain full-goal work.
