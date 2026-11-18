# Explicit ownership for checked-session queue memory

The [allocation-domain audit](../2026-10-27-npu-consumer-dma-lifetime/REPORT.md)
found that ordinary NPU-backed rings still used the DMA provider's devres and
their entries used the PCI endpoint's devres. The qualified `mt76.ko` confirms
calls to `dmam_alloc_attrs` and `devm_kmalloc` in `mt76_dma_alloc_queue`.
[Linux devres](https://docs.kernel.org/driver-api/driver-model/devres.html)
releases those allocations on their owning driver's detach. A device reference
or a CPU join cannot keep them alive.

The paired [provider](airoha-consumer-queue-owner.patch) and
[mt76](mt76-consumer-queue-owner.patch) changes are staged on main for the
next producer. They apply to pinned source; no existing module, overlay or
source lock was changed. The [hot-reset patch](../2026-11-18-npu-hot-reset-retention/REPORT.md)
also reapplies alongside them.

## Allocation and failure behavior

- The paired provider accepts only the checked boot's bound endpoint and
  DMA device. It allocates ordinary coherent descriptors with
  `dma_alloc_coherent` and allocates host-only entries with `kvzalloc`. It
  records both in the existing retained DMA lifetime before returning either
  pointer. The exposed lifetime's devres callback keeps the entire record
  instead of freeing it.
- The checked RX-event ring still uses its original firmware-enrolled
  descriptor. Adding a record for its entries does not transfer descriptor
  ownership or free it a second time. If entry allocation fails after
  firmware enrollment, the descriptor stays in the original owner. The
  consumer receives no pointers from the failed call.
- Requests are bounded to 48 recorded queues and 8 MiB of requested queue
  bytes per checked session, with checked multiplication and addition. No
  charged live record is recycled on uncertain retirement. These bounds
  are admission limits, not measurements of resident memory.
- Only no-provider or explicitly recognized legacy firmware selects managed
  queue memory. Checked allocation errors, even `-EOPNOTSUPP`, cannot select
  it. Incomplete queues fail before register publication and clear their
  descriptor count, so ordinary unwind cannot walk them as live rings.

The change keeps the **allocation**, not an immutable copy of its contents.
The existing teardown may still modify rings or entries and can release
packet payloads, streaming DMA mappings, page pools, token/RXWI state and
context. Retaining a ring by itself does not prevent those operations,
preserve an IOMMU attachment, block a later radio bind, or establish that
hardware has stopped. Legacy-NPU allocations keep their prior policy.

## Verification and integration

The [receipt](EVIDENCE.json) binds the qualified current ELF, five source
preimages and the resulting patch bytes. Both patches passed checkpatch and
applied with Git whitespace checks. The source verifier rejects seven
deliberate bypasses, including skipping the endpoint match, putting the
pointer before enrollment, freeing a borrowed ring and falling back on a
checked error. This is not a compiled kernel or physical unbind test.

```sh
python3 -B tests/npu/verify_consumer_queue_owner.py \
  --producer .local/npu-build-scratch/native-c2/fw-txp-20261118-modules-a/modules/result.json \
  --producer-sha256 b5af9591d0f6116547a08749fe733a98ac4d89b6088f8d1465950b052e4f69bd \
  --check research/checkpoints/2026-11-18-npu-consumer-queue-owner/EVIDENCE.json
```

After the original replay and frozen image work are verified, re-export both
overlays together, rebuild linked modules, and test successful allocation,
wrong endpoint/device/boot, size and capacity boundaries, no provider, legacy
and disabled configuration, both allocator failures, RX-event partial
publication, remove and failed probe. The older RX-event fixture extracts
`mt76_npu_alloc_rx_event` from the original driver. Preserve it against that
preimage and qualify the new `mt76_npu_alloc_queue_mem` route with the new
producer. Do not load the new mt76 module with an old provider.

## Original replay

Profile 1 of invocation `61e2d7b8` was independently rechecked after it
closed: 6,421 ordered RPC records, the four full-memory checkpoints, final
broker/journal and transcript hashes, plus the recorded comparison counts.
[Profile receipt](PROFILE-1.json). The original driver advanced 228 CPU ticks
at audit and all 345 input bindings rehashed. Profile 2 had 155 passing records
and 17 publications at that observation, with no summary. There is no terminal
three-profile pass yet. Nothing here qualifies an image or physical device.
