# Size the staged W1700K coherent pool

Keep the [staged 16 MiB reservation](../2026-11-18-npu-coherent-window/REPORT.md).
For one fresh, successful checked MT7996 cold probe on the pinned 4 KiB-page
kernel, the conservative ceiling is **14,131,200 bytes (13.48 MiB)**,
leaving **2,646,016 bytes (2.52 MiB)**. This deliberately charges the
full 48-ring ledger, not the ring count expected on a particular board.
It is not a boot-time consumption measurement.

| Checked RRO path | Rounded ceiling | Headroom in 16 MiB |
| --- | ---: | ---: |
| V3 | 14,131,200 | 2,646,016 |
| V3.1, no WED | 14,008,320 | 2,768,896 |

The verifier rehashes the frozen producer, applies the exact staged
provider and mt76 patches outside the repository, and checks their
postimages and DMA-device and ownership routes. The unchanged linked
`mt76_dma_alloc_queue` has 8-, 16-, 24- and 208-byte descriptor cases.
The radio registers one TX ring per PHY; the per-AC entries alias it.
The bound charges three maximum checked TX rings, 45 other maximum-size
rings, eight mailbox pages, all six TX descriptor buffers, and the full
RRO extent list for each checked profile. The RX event backing is charged
once. CPU queue entries, streaming packet mappings, and fixed firmware
or WLAN carveouts use different storage. The staged checked probe skips
both WED attach paths.

## Rounding and scope

The pinned Linux allocator checks the aligned bitmap regions in ascending
address order. It rounds *each* coherent request up to a power-of-two
number of pages; even a 16-byte EMI record takes a page. If the pool is
attached, an unsatisfied request returns failure through `dma_alloc_attrs`
without trying unrestricted coherent memory.

In an initially empty power-of-two pool with no frees, the maximal free
aligned blocks start as one block. First-fit either takes the first
adequate block or splits it from the left; the remaining free blocks still
have strictly increasing power-of-two sizes in address order. The sum of
all blocks smaller than a request is less than that request. Thus the
rounded sum suffices in this scope, even when probe order changes. The
model checks the staged profiles in several orders and rejects an 8 MiB
pool. Tests also reproduce the opposite case after frees: enough pages
in total, but no available aligned region. All 65 focused host regressions
passed.

```sh
python3 -B tests/npu/verify_coherent_budget.py \
  --producer .local/npu-build-scratch/native-c2/fw-txp-20261118-modules-a/modules/result.json \
  --producer-sha256 b5af9591d0f6116547a08749fe733a98ac4d89b6088f8d1465950b052e4f69bd \
  --dtb .local/npu-coherent-window-20261118/next.dtb \
  --check research/checkpoints/2026-11-18-npu-coherent-budget/EVIDENCE.json
```

The [receipt](EVIDENCE.json) binds this ceiling to the producer, staged
DTB, patches, and allocator sources. Refresh it after changes to those
inputs. No new module or image was built. Validate actual boot placement,
headroom, and exhaustion after linking the candidate. The pinned config
disables ftrace and DMA API debugging, so collect allocation data in a
qualification build with instrumentation. This check does not cover
fragmentation after failures or teardown, additional consumers, or physical
DMA retirement.

The [original replay observation](REPLAY-LIVE.json) still showed profile 2
live with 2,773 positive trace records, all 345 input bindings matched,
and no whole-run verdict.
