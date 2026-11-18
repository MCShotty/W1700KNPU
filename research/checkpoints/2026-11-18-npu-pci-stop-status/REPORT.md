# Radio DMA idle status is not a teardown gate

The [September stock reset trace](../2026-09-05-npu-reset/REPORT.md) identified
the MT7990 PDMA idle poll and the empty traffic-control slots. This check
closes the static PCI registration and follows the outcome of the poll through
both shutdown callers. It also checks the same register against the linked
current radio module. [Verified inputs and call offsets](EVIDENCE.json).

## Where the stock result goes

| Operation | Verified behavior for the shipped MT7990 PCI configuration |
| --- | --- |
| Register and allocate the transport | The chip selects bus type 1. The matching PCI registration passes `pci_mmio_ops` and `pci_dma_ops` to transport allocation. The PCI driver's optional alternate-operations hook at `.data+0x28` has no relocation or value. |
| Stop traffic | `mtk_bus_stop_traffic` looks up DMA slot `+0x80`. The static PCI slot at `.data+0x138` has zero bytes and no relocation, so this operation returns `-EOPNOTSUPP` without an endpoint callback. |
| Stop device | The wrapper clears the software started bit before calling DMA slot `+0x70`. The PCI stub at `.text+0x1c14` calls chip slot `+0x10`. The registered MT7990 chip table at `.data+0x70` resolves that slot to `mt7990_pdma_disable` at `.text+0xcc4`. |
| Poll the endpoint | Following writes at BAR0 offsets `0xd4208` and `0xd413c`, the callback polls bit 0 at BAR0 `0xd7044`. There can be 101 busy samples. An idle sample returns 0. A missing read accessor can also reach the zero-result path without sampling. A timeout logs an error, sets result 1 and continues through the common interrupt shutdown and state clear. |
| Exit the device and tokens | After the chip callback, the bus wrapper advances to the next transport without checking its result. The device-stop path and the off branch of `mtk_ge_set_dma_tk` both call bus stop, bus exit and token exit in sequence without a branch on the radio stop result. Both caller paths set their own result to zero. |

The PCI read/write operations use the BAR0 pointer saved at transport
`+0xb78`. The NPU mailbox stop uses a different DMA table slot, `+0x128`;
the [earlier reset trace](../2026-09-05-npu-reset/REPORT.md) covers it. Neither
the radio poll nor the software started bit attests to that NPU's state.
These are static bindings for the examined modules; no live objects or
transactions were inspected. This does not exclude synchronization elsewhere.

## What the current module does

- The pinned `mt7996e.ko` from producer `b5af9591` reads the same offset and
  mask in `mt7996_dma_enable`, using the `MT_WFDMA_EXT_CSR_HIF_MISC_BUSY`
  register definition. The value returned by that poll is not a control-flow
  gate in the examined enable path.
- In `mt7996_dma_reset`, successful NPU IRQ shutdown is checked, then the radio
  clears TX/RX DMA enables on its primary HIF and on HIF2 when present. The
  linked code calls a 1-2 ms sleep and then the queue TX cleanup callback. It
  does not sample the radio idle field between those actions.
- `mt7996_dma_cleanup` calls `mt7996_dma_disable` and then `mt76_dma_cleanup`
  without a checked radio stop result.

A scoped radio check should distinguish idle, busy/timeout and unobservable
status, with a failed or missing observation preventing release of resources
that the radio could still reference. Do not treat a successful sample of
this one field as authority to free all shared memory. The reset/remove
callers still need a checked result for each requester or complete ownership
retention, including HIF2, SoC NPU/WED, pages, rings and devres. Which requesters
are covered by an individual idle indication still needs hardware evidence.

## Reproduce

Run from the canonical repository with the original local stock inputs and
the pinned linked build. The verifier hashes the inputs and checks ELF
relocations and AArch64 instructions. Nothing is loaded or executed on a
router. Four in-memory controls change the slot relocation, slot data, idle
bit and shutdown branch respectively; the checks reject all four.

```sh
python3 -B tests/npu/verify_pci_stop_status.py \
  --producer .local/npu-build-scratch/native-c2/fw-txp-20261118-modules-a/modules/result.json \
  --producer-sha256 b5af9591d0f6116547a08749fe733a98ac4d89b6088f8d1465950b052e4f69bd \
  --check research/checkpoints/2026-11-18-npu-pci-stop-status/EVIDENCE.json
python3 -B tests/npu/test_pci_stop_status_checks.py
```

At this checkpoint the original RV32 invocation `61e2d7b8` was still live:
profile 0 had 6,421 positive records and a summary; profile 1 had 4,215
positive records, 129 publications and no summary. The driver advanced
221 CPU ticks and all 345 inputs rehashed. This is a prefix, not an image
qualification. No bound input, firmware, driver, image or router was changed.
