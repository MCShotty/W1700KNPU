# MT7996 TX-Check Reservation Correction

Date: 2026-09-06. Status: **source correction verified; no new image or flash**.
The full Wi-Fi and NPU goals remain open.

## Confirmed Contract Violation

The selected pristine MT7996 firmware initializes **0x7000 16-bit TX buffer-check
entries**, or **0xe000 / 57,344 bytes**, in core-0 function `0x84004e76`.
The retained W1700K R1 DTB instead reserves `0x6800 / 26,624 bytes` at
`0x90c00000`, with the separate `ba` reservation immediately following at
`0x90c06800`. Initialization therefore writes **30,720 bytes (30 KiB)** beyond
the declared TX-check region into that next reservation.

This is not inferred solely from decompiler types. Native RV32 tests execute
the original allocator and boot initializer. Core 0 first waits with a null
TX-check pointer. The real mailbox/IRQ/Wi-Fi callback chain accepts SET API 32
and writes the aliased pointer at `0x3e90469c`. After completing one modeled
environmental delay, the original main context performs exactly 28,672
consecutive halfword stores. The first out-of-reservation write is instruction
`0x84004f1e`; the first 30 KiB of the next region lose their sentinels.

The firmware code/data hashes are
`e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643` and
`61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1`.
Both also match the current staged root filesystem, not only an archived copy.
The retained R1 DTB SHA256 is
`565136de9144d0e366404d299933ebd8e58cedbfdb97c7b803749e0248eec596`.

This establishes a source/firmware memory-contract bug when the WLAN memory
initialization path is used. It does **not** establish that this overrun caused
the user's live client failures. The last verified R1 baseline has WLAN NPU
compiled out, so this path is not exercised by normal mt76 attachment there.

## Surgical Correction

Only `target/linux/airoha/dts/an7581-npu-mt7996.dtsi` changes in the packaged
source. Its TX-check reservation grows to `0xe000` bytes at the same base.
The BA region moves to `0x90c0e000`, retaining its size, label and memory-region
role. Deleting/recreating that node preserves a matching unit address and `reg`.
The generic include, MT7992-specific include, other memory regions, firmware
names, driver code, WLAN build policy and radio configuration are unchanged.

The correction is in the canonical cumulative OpenWrt patch and source lock;
the prepared source matches its SHA256
`83cd7d8b494399ec218ce65810d8e17d08b930b9d1156a1591fef56f04d5a89d`.
The new source snapshot is `post-Daybreak21-R1-NPU-txbuf-reservation-20260906`;
the last-router-tested snapshot remains R1.

## Verification

- Rebuilt W1700K, Nokia Valyrian and EVB eMMC Eagle DTBs. Complete decoded
  trees differ only in the intended TX size, BA address/node path and BA symbol.
  The generic EVB control DTB is byte-identical. This covers 742 nodes and 3,505
  properties across four profiles, including preserved phandle references.
- Replayed native initialization against the corrected W1700K DTB: all 57,344
  bytes remain inside TX-check storage; BA sentinels survive. Native SET API 7
  accepts the relocated BA address, which is supplied by the host rather than
  hardcoded in this callback.
- Two partial-fix controls fail: moving BA without enlarging TX leaves 30 KiB
  outside the TX reservation; enlarging TX without moving BA still overwrites
  30 KiB of BA. Both parts are required.
- Canonical source reconstruction passes for 35 OpenWrt and three LuCI changed
  files. The prior cumulative patch remains byte-identical behind the one new
  DTS diff. No generic NPU/barrier/copy source or kernel/module code changed.

Candidate W1700K DTB SHA256:
`dfe83e60933b9905712ebd1dc35f182cf943acbbd6f03902031be3856cf70344`.
This is a directly compiled DTB, not a new FIT/sysupgrade image. Baseline DTBs
can be reconstructed from the pinned public-base MT7996 include without
reverting the active source. Generated DTBs stay under `.local/npu-bootmem`.
Mutex owner readback, IRQ function invocation and one delay completion are
modeled. No hardware DMA, full reset-vector-to-ready boot or client traffic is
claimed by these tests.

## Startup Boundary

The test also confirms that the TX-check-address command must arrive before
core-0 main can finish. This matters to the still-unpromoted admission candidate:
closing all legacy bootstrap commands before that point would deadlock startup.
The extended barrier state still needs explicit contained initialization before
worker polling, and complete startup needs additional packet/host-adapter setup.
Neither that bootstrap protocol nor a physical drain/restart is implemented here.

A pinned Ethernet filesystem query found `/dev/mem` absent. No raw MMIO access,
diagnostic installation, kernel-policy workaround, module load, radio change,
association switch, reboot or flash was performed. The separate-client Wi-Fi
reproduction request remains pending.

## Replay

```sh
python3 tests/npu/test_txbuf_dtbs.py --baseline
python3 tests/npu/test_txbuf_dtbs.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_boot_txbuf_extent.py --candidate-dtb .local/npu-bootmem/candidate/an7581-w1700k-ubi.dtb
python3 tools/migration/verify_source_export.py --output research/checkpoints/2026-09-06-npu-bootmem/source-export-verification.json
python3 tests/npu/verify_bootmem_evidence.py
```

Full-image/FIT validation, active-NPU physical ownership/cache/drain proof,
Linux recovery/removal/restart, complete stock host-adapter/TXFREE/RRO parity,
services and actual-client Wi-Fi acceptance remain open. Do not promote the
WLAN-NPU-disabled baseline or this individual correction to completion of either
full project goal.
