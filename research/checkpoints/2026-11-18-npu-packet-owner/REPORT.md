# Keep the checked consumer's DMA backing through host detach

The [coherent window stack](../2026-11-18-npu-coherent-window/REPORT.md)
supersedes the provider patch below. Its mt76 half is unchanged.

The exact [older queue-owner patch](../2026-11-18-npu-consumer-queue-owner/REPORT.md)
reacquires `dev->mutex` inside the queue allocator. The bound
`mt76_npu_rx_queue_init` holds that same mutex across `queue_ops->alloc`.
That recursion is not safe. The old patch was never selected for a build.
Use this [provider](airoha-checked-dma-owner.patch) and
[mt76](mt76-checked-dma-owner.patch) pair **instead of** the previous staged
queue-owner and hot-reset patches. Both reapply directly to the same locked
producer preimages and already include their intended behavior.

## Checked consumer ownership

- The provider exposes its checked-pair selection. With the driver pinned,
  mt76 latches ownership before attempting the BAR bind, not after receiving
  a successful reply. A failed checked binding unwinds the CPU side rather
  than continuing into a generic queue setup. Plain and legacy paths do not
  acquire this hold; checked owners cannot take managed queue, TX or RRO
  fallbacks. WED attach cannot change the checked owner's DMA device.
- The core holds separately allocated TX/MCU queue objects and extra PHY
  objects outside devres. The provider holds descriptors and queue entries,
  including the original RX-event owner. Its exposure flag preserves those
  allocations. The consumer lifetime mutex serializes allocator lookup with
  pointer install/clear. The order is device mutex then lifetime mutex when
  both are needed. The queue allocator itself does not take the device mutex.
- Teardown still unregisters the network interface, joins workers and both
  IRQ domains, disables NAPI, removes its registrations and releases IRQ
  vectors. For held pools the Linux 6.18.52 recycling helper detaches the
  disabled NAPI context without destroying the pools. It skips the MCU
  restart and forced release of TX tokens, the two NPU RX queues, ring
  resources and RRO page mappings. After clearing provider CPU pointers and
  waiting for RCU, it leaves the checked hardware context and the objects
  still reachable from it allocated. Normal pre-teardown completions can
  still retire individual packets via the existing path.
- The radio stores the primary and any HIF2 PCI identity and BAR0 range
  in its retained context, with device references. A later matching probe
  under this driver is rejected before PCI enable and bus mastering. One
  checked attempt consumes this retention lane until an actual retirement
  mechanism can release it; unloading the pinned module is not a substitute.

This is a conservative hold, not an implementation of hardware drain.
The managed supplier [device link](https://docs.kernel.org/driver-api/device_link.html)
orders driver lifetimes, not physical DMA. The hold does not preserve an IOMMU
attachment, stop independently running firmware, or cover arbitrary remapping
or a different PCI driver. It retains the resources left at the inspected
teardown boundary, not everything previously touched by the stack. No compiled
probe/teardown or physical retire/reuse evidence exists for this pair.

## Reproduce and integrate

The verifier applies both patches to 12 exact source files, reproduces the
old nested-lock contract, checks the new source, and rejects 12 deliberate
bypasses. It binds the qualified baseline's linked queue-allocation calls
and rechecks the earlier hot-reset contract. Both patches passed checkpatch.
[Exact hashes and rejected controls](EVIDENCE.json).

```sh
python3 -B tests/npu/verify_checked_packet_owner.py \
  --producer .local/npu-build-scratch/native-c2/fw-txp-20261118-modules-a/modules/result.json \
  --producer-sha256 b5af9591d0f6116547a08749fe733a98ac4d89b6088f8d1465950b052e4f69bd \
  --check research/checkpoints/2026-11-18-npu-packet-owner/EVIDENCE.json
```

Keep the active source lock unchanged until the original replay and its
frozen image qualification are accounted for. Then use the two replacement
patches from their exact preimages, export both build overlays, and qualify
matching linked kernel/provider and mt76 modules. Required cases include
allocation with the device mutex already held, provider/probe errors before
and after bind, registered/unregistered remove, pool recycling and payload
mapping fate, HIF2/rebind, and legacy/offload-disabled controls. Verify that
the normal path still releases only its own allocations. Do not treat a
source ordering check or host CPU join as a hardware retirement witness.

## Original replay

Invocation `61e2d7b8` still runs on the original handle. The earlier pause in
visible publication records matched the recipe's flush every 16 publications;
the next visible jump confirmed progress. Profile 2 advanced from 33 to 81
publications (219 total ordered operations at this snapshot). All 345 input
bindings verified, driver CPU ticks advanced, and no profile 2 summary or
whole-run verdict exists. [Read-only observation](REPLAY-LIVE.json).
No compiler, image build, target contact or flash ran for this checkpoint.
