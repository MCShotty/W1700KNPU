# Current OpenWrt Snapshot Comparison

Captured/rechecked 2026-09-06, approximately 02:18 UTC. Report-only sidecar.

## Conclusion

**No new NPU/provider/recovery/bootstrap fix is reusable from this snapshot relative to our pins.**
The current image is newer at the OpenWrt top level, but all 14 intervening commits
(22 paths) concern other targets, Linux 6.12, or uboot-tools. The relevant Airoha,
Linux 6.18, mt76 and linux-firmware inputs are unchanged. Eighteen downloaded
OpenWrt source/patch files match the pinned Git archive byte-for-byte.

Keep our detached-provider guard, patches 926/927 and MT7996 DTS correction.
The snapshot does not close all-worker quiescence, startup/negotiation,
partial-init rollback, L1/full-reset/removal ownership, or hardware drain gates.
There is no justification here to rebase or replace the current NPU payload.

## Exact Identity

The rolling [official index](https://downloads.openwrt.org/snapshots/targets/airoha/an7581/) had already advanced from the supplied
September 5 sysupgrade SHA256 `9b1f93f78eeac42a2b3a033af91f7c49738d09fd68810244de3982b8df222f24`.
That old image was not fetched or assigned a revision in this audit.

| Item | Current September 6 snapshot |
| --- | --- |
| Revision | `r36060-d6933d6aed` |
| OpenWrt commit | `d6933d6aedc8a8d5aff646ed3fe71135d5a46fcd` |
| Kernel / ABI | `6.18.44 / bed7e2dec73efb4c3050bc8a8373af30` |
| mt76 commit | `be5ce7910521492d4a2e4ce7ee3843680a46c047`, unchanged from our pin |
| mt76 / MT7996 firmware packages | `6.18.44.2026.09.01~be5ce791-r1` |
| NPU package | `airoha-en7581-mt7996-npu-firmware 20260810-r1` |
| Sysupgrade size / profile | 13,513,539 bytes / `gemtek_w1700k-ubi` |
| Sysupgrade SHA256 | `990f955cfee3622752848ee1b737f89856763c67edf4765e92bab1e0eec994fc` |

[version.buildinfo](https://downloads.openwrt.org/snapshots/targets/airoha/an7581/version.buildinfo),
[profiles.json](https://downloads.openwrt.org/snapshots/targets/airoha/an7581/profiles.json), and the extracted image's
`lib/apk/db/installed` agree. The target-wide manifest alone omits W1700K
device additions; retained old kmod filenames must not be mistaken for its packages.
Final version/profile downloads are byte-identical to the initial capture.

Both MT7996 NPU blobs match our canonical `linux-firmware-20260810` input:
- RV32, 122,336 bytes: `e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643`.
- Data, 3,084 bytes: `61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1`.

The generic EN7581 blobs also match. These are package/payload identities;
no runtime firmware GET/version query was made.

## Contract Comparison

Paths and line numbers below are relative to
`/home/captain/W1700KNPU/.local/npu-startup/snapshot-audit`. All file hashes and immutable source URLs are in
[snapshot-comparison.json](snapshot-comparison.json).

| Contract | Exact evidence and remaining difference |
| --- | --- |
| Mailbox publication/timeout | `kernel/drivers/net/ethernet/airoha/airoha_npu.c:191-215`: overwrite coherent buffer, publish counter before flags, no pending-owner gate after timeout. Patch 926 remains required. |
| Memory preflight | Same provider `:535-590`: cast reservation start to u32 and send commands before validating every reservation. No 927 profile/size/overlap preflight. |
| TX-check / BA | `openwrt/target/linux/airoha/dts/an7581-npu-wlan.dtsi:25-33` and actual extracted DTB retain TX-check `0x90c00000+0x6800`, BA `0x90c06800+0x200000`. Canonical MT7996 include uses `+0xe000` and moves BA to `0x90c0e000`. Applying 927 without that DTS correction intentionally rejects the short snapshot reservation. |
| Startup | Provider `:808-836` still boots eight cores using mask `0xff`, fixed waits and nonfatal version query. `mt76/mt7996/npu.c:516-556` still sequences offload/RXD/TXD/event/PCIe/TXDONE setup before IRQ enable. No new barrier/negotiation protocol. |
| Stop | `mt76/mt7996/npu.c:594-630`: selector 4, at most ten GET3 polls, then selector 6. No all-worker generation/drain contract added. |
| L1 | `mt76/mt7996/mac.c:2575,2647-2667`: both stop and reinit returns ignored; reset/NAPI restored afterward. |
| Full reset / removal | `mt76/mt7996/mac.c:2329-2333`: token release precedes forced DMA reset, without an NPU stop in that path. `mt76/mt7996/init.c:1828-1848` similarly frees tokens before cleanup. Provider `:839-845` only cancels watchdog work; `mt76/npu.c:500-520` drops references/cleans queues without a stop handshake. |
| Absent provider | `mt76/mt7996/npu.c:559-591` allocates six MT7996 coherent buffers before the inner provider test at `:521-523`. Local patch 003 remains absent upstream. |

The packaged DTB identifies Gemtek W1700K (OpenWrt U-Boot layout). Binary/pkt/tx-pkt
reservations remain `0x84000000+0xa00000`, `0x8a000000+0x2c00000`,
and `0x8cc00000+0x4000000`. The TX-check observation is packaged-DTB proof,
not a newly executed firmware-overwrite or live failure test.

The official package enables both NPU compile flags at
`openwrt/package/kernel/mt76/Makefile:502-508`; its extracted module contains
`mt7996_npu_hw_init`, `__mt7996_npu_hw_init`, and `mt7996_npu_hw_stop`.
Our pinned build policy remains WLAN NPU compiled out. Compiled symbol presence
does not establish runtime activation or safe recovery.

## Existing Upstream Work

These useful changes are already present in both bases; none is a new cherry-pick:
- OpenWrt `9059c31bf5d245827574f6df24aa7ba797ba544b`: coherent mailbox DMA (patch 924); latest patch-path commit `da5a0577f5b86cb11654303b82bb9f51c605a2ea`. Keep 926 layered on it.
- Linux `3847173525e307ebcd23bd4863da943ea78b0057`: DTS firmware names (123); `875a59c9a9e584d99d8e9e5aa8435ec9300bfe91`: optional BA address (121).
- Linux `a085e68b13906a6a4d8b16e3b763e13f05904cc8`: direct firmware load/deferred probe (181); `62f1347fa5bf6e6c9c054aedb9e87e7205fa12ac`: generic NPU header ABI (111).
- OpenWrt `ab2dc6ab166a97d4e610ce6d1850ab8e66eabdd2`: Wi-Fi-only reservations; `a46721f04d7af3379d8142d5e9b8967c5a386bb3`: current mt76 pin; `452ec3a423c6c733299fccf503af0eeee33d56b1`: linux-firmware 20260810.

The immutable [OpenWrt comparison](https://github.com/openwrt/openwrt/compare/28ba2708f1f609bfd134975808b2bc6ed9dc9742...d6933d6aedc8a8d5aff646ed3fe71135d5a46fcd)
and downloaded API response enumerate all 14 newer commits.

## Verification And Scope

The existing Linux 6.18.44 archive matched its pinned SHA256. Only provider C/header
were extracted; official patches were applied in scratch, then 926/927 to a second
scratch copy. Both resulting files match the prepared canonical source exactly:
- Snapshot provider: `c16c2fe02253a29c2ac7f7e2d6a6bae2f75a04fce950d2fb6e33281469f6cc1c`.
- Canonical provider: `8eed02dd963c9d80fcaf4f15368506f4a4720dd7be4f080c394a21bba7e1fe8f`.

Six metadata SHA256SUMS checks, image SHA256, extracted DTB/rootfs FIT SHA1 checks,
18 source comparisons, four firmware comparisons and source-lock patch checks pass.
Detached signatures were not verified; transport used official HTTPS with normal TLS.
No SDK, toolchain, imagebuilder or kernel-debug archive was downloaded.

No kernel build, bootstrap implementation, source-lock/build-tree edit, staging,
commit, subagent, router, network-interface or hardware action occurred.
Only this report and its JSON are tracked-write outputs; evidence is under the
permitted audit directory. Ledger unchanged under the explicit report-only scope.
No new hardware proof or stock-parity claim is made.
