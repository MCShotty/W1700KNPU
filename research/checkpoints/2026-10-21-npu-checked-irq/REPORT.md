# Checked NPU IRQ Software Contract

Date: 2026-10-21. The full NPU goal remains incomplete. No hardware, flash,
radio, VM restart, permanent-policy change or subagents were used.

## Implementation

Canonical kernel/mt76 integrated patches now expose checked read/ack/mask/arm
callbacks. Failed reads clear status; successful reads expose only the requested
queue bit. Mask/arm preserve other bits and check readback. Legacy void/u32
callbacks remain for compatibility, but the target requires all four checked
callbacks without unsafe fallback. Provider and consumer must be rebuilt together;
old module-layout compatibility is not claimed. The two RX lines must be distinct
and exclusively acquired with `IRQF_NO_AUTOEN`. NAPI/setup precede host enables;
watchdog/mailbox ownership is unchanged.

The irq-lock-protected controller masks before acknowledgement, and schedules
NAPI only after both succeed. First errors latch sticky quarantine and a separate
host disable-depth hold. Pending normal startup enables cannot release that fault
hold. `enable_irq` runs outside the spinlock/RCU section. Stop/rearm return errors;
re-entry neither clears quarantine nor repeats setup. Reset callers propagate
failure before their subsequent cleanup/restart work.

New RX-batch/TX-entry admission closes on stop/fault. TX rejection precedes
linearization, txwi allocation, DMA mapping and token preparation. Successful
admission preserves the existing `-ENOMEM` fallback. Already-admitted work may
remain in flight. IRQ suppression, W1C writes and mask readback are not handler
synchronization, DMA drain or permission to retire storage. Remove/teardown stays
separate and unqualified.

## Verification

- `CHECKED_IRQ.json`: 353 cases execute selected actual provider/header,
  handler/controller/registration and init/poll-completion C with explicit
  regmap/IRQ-depth/NAPI/RCU/setup fixtures. Covers partial effects, readback
  mismatches, both late-enable fault points, capability/registration failures
  and 19 ordinary poll routes. Six mutants rejected; ASan/UBSan/leak checks.
- `TX.json`: complete actual TX queue-entry C passes 18 host-fixture cases.
  Reintroducing the success-clobbers-error regression is rejected as a mutant.
  DMA/cache/SKB/token APIs remain explicit fixtures, not physical operations.
- `MODULES.json`: actual final AArch64 links pass for `airoha_npu.ko`,
  `mt76.ko`, `mt76-connac-lib.ko`, `mt7996e.ko`, Linux6.18.52/GCC14.4.0.
  Exports, real dependency indices, imports, checked edges and vermagic agree.
  All 22 current provider components are staged privately. Pre-existing missing
  `MODULE_DESCRIPTION` warnings remain; unresolved imports are not accepted.
  Another 24 build-contract unit tests pass, zero skips.
- Private read-only-workspace/kernel-overlay/source-copy build output is
  88,014,878 bytes. Complete original kernel/mt76 inventories and protected
  inputs compare unchanged afterward. No module load, fresh dependencies,
  vmlinux, world or image build occurred.
- `SOURCE.json`: both integrated patches apply at zero fuzz and match references.
  Lock `cb035741`; cumulative export checks pass 70 OpenWrt/five LuCI entries.
  Root patches, config, existing images, UI/WiFi and unrelated authority stay
  unchanged. The protected `01fc0ef0` image predates this IRQ change.

Private evidence index `02b58276` binds 609 paths; public receipts record exact
hashes/scopes. Extracted-C fixtures and unloaded module links do not establish
complete kernel concurrency, physical IRQ/DMA drain or packet-lifecycle acceptance.

## Preserved Failures

Old actual-C characterization reproduces 148 handler schedules after errors,
5,624 silent bulk errors, 12 startup losses and eight hot losses. Old source and
generated tests remain explicitly mapped/preserved. All three target tests
passed, but their original aggregate wrapper failed on relative-path binding
afterward; its audit is not a retroactive wrapper pass. These are old-code counts,
not outstanding failures of the new checked fixture.

Initial capacity observations and incomplete mappings were refused before target
work. First checked-IRQ extraction failed on an unsupported `bool` return type;
first module preflight rejected stale prepared component sources before compile;
first TX fixture collided with libc's `puts` identifier. Failed outputs remain.
The corrected overlay stages current components without changing prepared sources.
Tests, native limits and checkpoints were not weakened.

## Live Replays And Remaining Work

`PROGRESS.json` separately rehashes all 2,473 frozen inputs and retains log
prefixes: both original default/HIF2 jobs are live, pass six TXBUF phases/RX-event,
and have entered DESC10. No terminal verdict. Their frozen source is `73ce969`;
they do not qualify this IRQ code. Sizes, 3M-instruction/60M-us limits/checkpoints
are unchanged. Do not restart them just because current source has advanced.

Continue both full cold callers/fault/setup matrices; build a fresh checked-IRQ
image; qualify kernel IRQ concurrency/routing and in-flight ownership/drain/
recovery/retirement. Hot TX/RX/event/token/TXFREE/free-pool/PPE/FastTX, RRO context,
DMA/cache/PMA/exclusion, teardown, whole-stack/per-hart, Gemtek boot/services/
radios/MLO, clients, performance and stability remain. Stock parity is incomplete.

Actual Jev reviews are retained. Late-enable wording had support0.75/confidence
0.62; the in-flight claim was uncertain between contradicted/not-established.
Neither becomes proof: exact host interleavings are tested; physical and
in-flight scope stays open.
