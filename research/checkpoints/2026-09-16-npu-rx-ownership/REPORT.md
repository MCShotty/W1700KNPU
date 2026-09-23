# Host NPU RX Packet Ownership

Validated 2026-09-23. This directory began as an interrupted 2026-09-16 draft.
Candidate patch 008 is unpromoted and applies after the host-lifetime checkpoint
and its mt76 patch 007, including the preceding host TX/TXFREE/L1 candidates.
Neither the packaged source lock nor firmware images were changed.

## Findings And Correction

The predecessor `mt76_npu_dequeue()` starts building an skb before it has checked
all advertised fragments. If a later fragment is not DONE, it frees the skb
but leaves the queue tail, queued count and buffer entries unchanged. Host-C
execution reproduces this logical prefix release and duplicate release during
queue cleanup. Whether that partial publication is reachable on the physical
NPU remains an unproven producer contract, not an observed router failure.

The same selected path uses descriptor lengths without checking the recorded
DMA span. With an artificially reduced skb fragment capacity, it can skip
attaching excess fragments but consume their queue entries, losing ownership.
The original RX-only poll also refills page-pool buffers with budget zero,
contrary to the pinned kernel's documented NAPI rule.

The candidate changes only dequeue and its poll caller:

- Check queue bookkeeping and positive buffer size before descriptor access.
- Read DONE with `READ_ONCE`, then use `dma_rmb` before metadata. Preflight every
  advertised fragment and snapshot lengths/last-fragment info before any skb
  ownership transfer. Incomplete packets and unusable host entries remain held.
- Validate each length against that entry's mapped DMA span, with the DMA span
  itself bounded by the allocation's skb payload capacity.
- Build/attach an skb only after preflight. A failed first skb allocation keeps
  every buffer and queue counter for retry; the first CPU DMA sync can already
  have occurred. Successful ownership transfers clear consumed entry pointers.
- Recycle complete packets with excessive lengths or insufficient fragment
  capacity, consume the packet once and return `ERR_PTR(-EINVAL)`. Poll counts
  this consumed packet against its budget without delivering the error pointer.
- Return immediately for zero-budget RX polls, without page-pool operations.

The fresh source check corrected two errors in the unfinished draft: its
eight-entry snapshot array did not cover the actual four-bit host packet-count
mask, and its signed buffer-size check needed an explicit nonpositive guard.
Sixteen snapshot slots cover all current count encodings; zero retains the
predecessor's one-fragment interpretation. The host mask is preserved, not
claimed to be newly verified against native firmware.

## Executed Evidence

`test_npu_rx_ownership.py` extracts the actual before/after dequeue, poll, refill
and cleanup C. It also extracts the pinned queue structures, RX queue enum,
descriptor structure and masks. The harness models skb/page-pool, DMA, locking,
RCU and NAPI helpers; it does not load a kernel driver or execute NPU firmware.

| Check | Result |
| --- | --- |
| Before host profiles | 3,228 cases, including expected counterexamples |
| Corrected host profiles | 3,376 cases |
| Named compiled mutants | 11 rejected by their designated oracles |
| AArch64 kernel objects | 6 before/after objects with NPU enabled/disabled |
| Strict checkpatch | 0 errors, 0 warnings, 0 checks |
| Independent hash readback | 127 unique files matched, none missing |

Profiles cover both actual RX queue IDs, all advertised counts, every start
position in 16/17/18-entry rings, and representative wrap positions in the
actual 512-entry geometry. Capacity 17 is the normal profile; capacity four is
an artificial stress model, not the target kernel configuration.

Checks include every later-fragment incomplete position, allocation-failure
retry, complete overlength drops, invalid host bookkeeping, mapped-length
versus allocation-capacity bounds, zero/one/exact-capacity lengths, missing
publication barriers, synthetic metadata mutation during skb construction,
budgeted drops, provider absence, refill allocation failure and repeated wrap/
refill/cleanup. Buffer identities and fragment offsets/lengths are checked,
including separate buffers sharing one modeled page.

The baseline retains backing storage so logical duplicate releases and length
violations can be counted without intentionally executing a real UAF or buffer
overflow. ASan/UBSan cover the extracted C and harness execution, not the actual
kernel allocator. The metadata publication/mutation controls are explicit
models, not physical weak-memory or device-cache experiments.

Kernel builds use the predecessor's exact prepared source/header context in
separate ignored copies. Both common caller configurations and enabled NPU
objects compile without diagnostics. AArch64 disassembly has two `dmb oshld`
instructions in the corrected RX poll and none there before. These are object
builds, not linked/loaded modules. Public headers remain byte-identical.

The readback covers 54 input fingerprints, 47 derived source/include files,
15 sanitized executables, six kernel objects, four build logs and the patch.
Jev `jev-1.13.0` additionally checked five narrow evidence claims; its raw
probabilities are retained locally. It did not establish physical DMA proof
or full payload validation. Its non-decisive semantic judgments were reviewed
against the source and executed oracles, not used as acceptance authority.

## Receipts And Replay

- `rx-ownership.json`: SHA256
  `69645a636566569409b86049942b8f1c66f79fa1e5302c812d9cbdf09e6d5ed0`.
- `008-mt76-npu-rx-packet-ownership.patch`: SHA256
  `81f0b97536ff7242b9c5f58e12043b546afbd2c08f20796627d8e96242a23157`.
- Input authority: `research/checkpoints/2026-09-16-npu-host-lifetime/host-lifetime.json`.

```sh
cd /home/captain/W1700KNPU
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_npu_rx_ownership.py
```

`--skip-kernel` writes `rx-ownership-models.json` separately and cannot replace
the kernel-validated receipt. Generated builds remain in `.local/npu-rx-ownership`.
No protected device input is uploaded, and no native INODE/DESC operation is run.

## Remaining Contracts

This fixes the selected host ownership path, not complete RX acceptance.
Zero/short payload lengths preserve prior buffer-bound behavior; the downstream
MT7996 RXD/header/group parser still needs complete length and nonlinear-view
validation. Packet bytes and protocol validity are not certified by these tests.

Real producer count/DONE publication, stable descriptor/backing identity,
cache/PMA/coherency, recycling and doorbell ordering remain physical/integration
contracts. Concurrent refill/removal, NAPI/IRQ shutdown, provider lifetime,
physical DMA drains, full reset/recovery and ownership-safe rearming also remain
open. Unusable host metadata is held, not automatically repaired. No full boot,
stock parity, safe complete teardown, firmware release or hardware acceptance
is claimed. No router, Wi-Fi configuration, source-lock/overlay, image, flash,
subagent, restricted-lane, protected-data or commit/push action occurred.
