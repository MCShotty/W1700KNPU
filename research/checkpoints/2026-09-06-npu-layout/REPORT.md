# Bounded NPU Layout And Native GDMA Contract

Date: 2026-09-06. Status: **unpromoted instruction-test candidate**.
Both full goals remain open. No router contact, configuration/association change,
firmware image build, flash, or physical DMA operation occurred. Packaged
source/config, patch 926 and the protocol sources in `firmware/npu/` are unchanged
from `b9cff2bc40a67feafd1c94c522f8cbd81888d16c`. R1 remains the last router-tested
WLAN-NPU-disabled baseline, not full stock parity or new client acceptance.

## Layout Correction

The prior `0x3e920000` barrier state was an emulator-only address, outside a
conservative 32 KiB local data SRAM window. Previous receipts never authorized
deploying it, but the large emulated mapping would hide placement mistakes.

The test map now bounds local SRAM to `[0x3e900000, 0x3e908000)`. Barrier state is
at `0x3e906000`, admission at `0x3e906100`, and saved IRQ masks end at
`0x3e906158`. Poll scratch is `0x3e907000`. Synthetic rings, stats and ICV data
move to a separately mapped 480 KiB SRAM region, `[0x3e800000, 0x3e878000)`.
These are **test allocations**, not a production allocator reservation.

C and assembly bindings use linker symbols. Linker assertions reject native-BSS
overlap, misalignment and conservative-window overflow; C assertions constrain
structure extents, and the coordinator checks actual linked symbols before use.
Four negative controls reject `0x3e920000`, `0x3e904740`, `0x3e907ec0` and
`0x3e906001`. Testing exposed LLD accepting a late `--defsym` after its ASSERT
evaluation. The controlled builder puts overrides before the linker script and
checks resulting symbol values. This is not a claim about arbitrary LLD commands.

## Native Memory Evidence

- Pristine RV32 code/data SHA256 remain `e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643`
  and `61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1`.
- Sixteen reset cases execute the original stack selection and BSS clear loop.
  Only hart 0 with the mailbox word at `0x1ec0c140` unequal to all ones clears
  `[0x3e900c10, 0x3e904754)`. Both boundary sentinels and new state survive.
  Unicorn cannot set MHARTID, so eight byte-checked CSR read sites supply that
  value only. Tests stop at `0x840000f0`, before the rest of boot and trap setup.
- Native stack tops are `0x84021e00 + hart * 0x4000` for harts 0..7. The original
  code ends at `0x8401dde0`, below the first nominal stack bottom `0x8401de00`.
  The candidate text remains in `[0x84040000, 0x84048000)`, above all eight tops.
  This establishes static separation, not maximum stack depth or code-cache proof.
- Original allocator init `0x84005296` clears all 480 KiB of heap SRAM. Tests
  execute lookup `0x84005200` for all 36 entries in its four terminated tables,
  including native allocation rounding and duplicate lookup. Fixed entries point
  into `[0x3e880000, 0x3e8c0000)`, separate from local data SRAM. Fixed entries
  contain starts, not lengths; complete allocation order and caller closure are
  not established. The mutex owner result and printf return are modeled.
- Old virtual addresses and one-past-window addresses are unmapped, rather than
  silently supported by the test harness.

## Exact Board Evidence

The retained sysupgrade FIT SHA256 is
`0788f405337ceb030d873463bbf278497dcd9b86e8f75a1a3f57fd318eda195f`.
Its selected `config-1/fdt-1` has SHA1
`87f9deb7de897756f792628ff475d2451cd674de`, model
`Gemtek W1700K (OpenWrt U-Boot layout)` and compatible `gemtek,w1700k-ubi`.
The NPU node is enabled and references, in order, binary, packet, TX packet,
TX bufid and BA reservations. Binary memory is `[0x84000000, 0x84a00000)`.
The complete reserved-memory map and phandle-order check are recorded in JSON.
This is inspection of an existing exact image, not a new build or live readback.

The board's NPU `reg` length includes SRAM **and registers**, so it does not
establish RAM capacity. The conservative 32 KiB limit comes from a separately
pinned [EN7581 reference DTS](https://github.com/merbanan/airoha_ml/blob/92f7959aa1750e428d10efbeb21360e0955c1895/en7581-base.dtsi),
whose hash is recorded. It is not the Gemtek board DTB or a hardware measurement.
Likewise, the provider's firmware-data size limit is a loader limit, not proof of
physical SRAM extent. Production placement and cross-hart SRAM/atomic/cache
behavior remain unproved.

## EN7581 GDMA Evidence

Read-only exports from the previously fully analyzed stock kernel recover 63
GDMA/HSDMA-named functions, then 67 functions including one level of known
referrers. Both exports have zero decompile failures out of 33,676 discovered
kernel functions. These are not exhaustive indirect-call/module closure. The
existing unrelated Ghidra tool-template XML warning remains; both runs exit 0.

The kernel SHA256 is
`a51e6d0a6deee620a5f715c9469f193906cdf3fcea28b97ce01cf88383aa704e`.
Native ARM64 tests relocate two text pages while preserving PC-relative
displacements and provide only the device object/register model. They confirm:

- `SET_GDMA_CONFIG` writes source, destination, CT1, then CT0, with store barriers.
- `WAIT_GDMA_DONE` at `ffffffc0100cc120` polls **CT0 bit 1 clear**, not DONE.
  `set_GDMA_enable_bit` preserves other CT0 bits and sets bit 1. The native
  accessors return source/destination/CT0/CT1 through W0, despite the decompiler's
  incomplete void prototypes for some leaf functions.
- `IS_GDMA_DONE` separately reads `base + 0x204`; `CLEAR_GDMA_DONE` writes the
  selected bit there. Four channel cases preserve unrelated DONE/control bits.
  A held ENABLE does not return within the 2,000-instruction observation bound.

The original RV32 copy helper `0x840053a6` instead writes source, destination and
`(length << 16) | 0x23` at `0x1fb30000 + channel * 16`, then polls only DONE at
`0x1fb30204` and clears that bit after observing it. It does not read CT0, preclear
DONE, or implement a software timeout. Twelve normal cases cover channels 0/1/3
and four lengths; a stuck case remains polling within the observation bound.

Two explicit device hypotheses differ: if start preserves an old DONE, the
helper returns after one read while modeled ENABLE remains set; if start clears
DONE, it waits for the new completion. **The actual EN7581 start-clear behavior is
not yet verified. This conditional result is not a proven hardware fault or a
root cause of the live Wi-Fi failures.** No drain witness is recorded by this work.

GDMA here is the copy block, distinct from HSDMA and FE packet-GDMA naming.
The three identified RV32 call sites are in `0x8400e87a` (channel 1),
`0x8400f0c4` (channel 0) and `0x8400f528` (channel 3). All CPU/NPU/module owners,
indirect references, late writes, aliases and cache effects still need closure
before CT0 idle can become part of a physical generation-bound drain contract.

## Replay And Boundaries

```sh
curl --fail --location -o .local/npu-barrier/en7581-base-92f7959.dtsi \
  https://raw.githubusercontent.com/merbanan/airoha_ml/92f7959aa1750e428d10efbeb21360e0955c1895/en7581-base.dtsi
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/run_layout_regressions.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/verify_layout_evidence.py
```

The runner redirects all ten suites into this checkpoint, preserving historical
receipts. It retains the prior 9,351 barrier and 1,667 admission differential-call
cases, mutation controls, worker/IRQ/in-flight/refresh/transport tests and all
eight shared contexts. `layout-regressions.json` binds exact sources/results;
`evidence-verification.json` and `file-manifest.json` seal the checkpoint. Existing
historical verifiers bind historical source hashes and are not current-layout gates.

Next: close GDMA owner/copy-completion semantics and full coordinator boot,
memory reservation, atomic/cache and physical-drain paths. Implement the common
Linux L1/full-reset/probe-unwind/removal retention policy and validated restart.
Do not interpret this placement correction or a software all-hart ACK as safe
reclaim, full NPU parity, a production image, or real-client Wi-Fi acceptance.
