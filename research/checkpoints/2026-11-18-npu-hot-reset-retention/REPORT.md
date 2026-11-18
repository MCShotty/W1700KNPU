# Retain live NPU owners when hot reset cannot prove a drain

> The [replacement checked-DMA pair](../2026-11-18-npu-packet-owner/REPORT.md)
> already includes this hot-reset change. Do not apply this patch on top of it.

The qualified mt7996 driver releases TX token mappings in
`mt7996_mac_restart` before calling `mt7996_dma_reset`. IRQ/NAPI and worker
shutdown stop CPU access, but are not a device DMA fence. The L1 helper also
interprets zero from GET3 as permission to send SET6. The
[stock/RV32 reset trace](../2026-09-05-npu-reset/REPORT.md) showed that zero can
be observed while deferred work remains. A preceding sleep and a failed
attempt to recover do not make the old owners safe to recycle.

A [three-file driver patch](mt76-hot-reset-retention.patch) is ready for
integration and qualification. It is **not selected by the locked production
overlay** while invocation `61e2d7b8` and the frozen image inputs still depend
on those source bytes. It modifies no current binary or hardware.

| Path | Patched behavior |
| --- | --- |
| L1 with an attached NPU | Keep the existing park request and bounded info query. Zero no longer permits SET6; return `-EOPNOTSUPP`. The existing error latch stops the path before the MCU DMA-stopped event, ring cleanup or host restart. Other park/query errors still stop recovery. |
| Watchdog/full reset with an attached NPU | IRQ disable remains checked. Without a shared retirement witness, `mt7996_dma_reset` returns `-EOPNOTSUPP` before token, page or queue cleanup. The full-reset caller latches the error and exits instead of retrying or waking queues. |
| Reset without an attached NPU | Keep the existing primary and optional HIF2 TX/RX disable and settle delay. Require the existing radio BAR `0xd7044` bit 0 to clear before cleanup. Full reset moves TX token retirement after that check and before the usual queue cleanup. L1 keeps its post-reset token ordering. |

This deliberately leaves the affected running interface stopped on failure.
A successful radio observation cannot override the attached-NPU guard or
prove coverage of WED, HIF2 or independent SoC DMA requesters. The new poll
can reject a busy/timeout observation; it does not establish how every
inaccessible register read is reported by the physical bus. Existing
firmware handshake and radio-only recovery semantics outside the added check
are not a new hardware guarantee.

This patch changes only the two in-place recovery paths. It does not solve
cold-probe or PCI remove retention: managed rings can still be freed by
devres, and page-pool unmaps, token release and other teardown callbacks
need an independent, non-devres owner. See the
[consumer allocation-domain audit](../2026-10-27-npu-consumer-dma-lifetime/REPORT.md).

## Verification

The verifier rehashes the original combined producer and its input tree,
copies the three bound source files into a scratch directory, and checks
and applies the patch with Git. It confirms that its baseline still has
the early token release, no reset-time poll and the GET3-to-SET6 transition.
The candidate satisfies five source control-flow checks; all seven deliberate
bypasses are rejected. OpenWrt checkpatch reports zero errors and warnings.
These are patch and source checks, not compiled-driver test cases.
[Hashes and controls](EVIDENCE.json).

```sh
python3 -B tests/npu/verify_hot_reset_retention.py \
  --producer .local/npu-build-scratch/native-c2/fw-txp-20261118-modules-a/modules/result.json \
  --producer-sha256 b5af9591d0f6116547a08749fe733a98ac4d89b6088f8d1465950b052e4f69bd \
  --check research/checkpoints/2026-11-18-npu-hot-reset-retention/EVIDENCE.json
```

## Integration gate

1. Keep the original replay and its image producer unchanged. Finish the
   terminal and exact world-input checks on those original bytes before
   changing their canonical source authority.
2. Merge the patch into the integrated mt76 patch and source lock. Build a
   fresh qualified producer under the existing reserve and writer-lock
   requirements. Verify compiled L1 and watchdog branches before accepting
   the update. Include GET3-zero with live buffers, attached and detached
   provider scope, IRQ error, busy/failed radio read, normal non-NPU reset,
   HIF2, repeated requests and both NPU configuration states. Require no
   token or ring release and no queue wake on the early error paths.
3. Implement explicit consumer retention across unbind and a real shared
   retirement witness so NPU-enabled recovery can eventually proceed.
   Retest on the board only after the user reconnects it.

At this checkpoint invocation `61e2d7b8` was live, profile 0 complete, and
profile 1 at 5,652 positive records, 129 publications and no summary.
The driver advanced 212 CPU ticks and all 345 bound inputs rehashed. No
competing build, image qualification or hardware operation occurred.
