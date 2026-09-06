# W1700K Stock-Port Logging Session

Last updated: 2026-09-04 08:03:00 +03:00

Purpose: dated logging session and future-reference copy tracking what has been patched, implemented, reconstructed, or cloned from the stock Quantum Fiber W1700K firmware into our OpenWrt builds, and what is still left. Read this before doing more stock/NPU/WiFi work. This is the future-reference tracker unless a newer file explicitly supersedes it.

## Current Live Anchor

- Running image: V6.87 corrective engineering build.
- Image SHA256:
  `502745127cae575e6442ed373e12ae1047dde016d34c3fce98e76e7fd26e5c56`.
- Board/revision: `gemtek,w1700k-ubi`, `r0-73a8983`.
- Boot ID: `553b814f-2a64-4d49-a3bd-4f4dddd86ebe`.
- NPU mode: 0.
- Live result: installed image passed 38/38 guarded radio/MLO/backend/service/
  restore checks.
- Report: `work\analysis\v687-build-a-20260901\REPORT.md`.
- NPU parity boundary: patches 52/79 remain `BLOCKED-DESIGN`.

Older source/build anchors below are historical unless a later dated section
explicitly makes them current.

## Current Build Anchor

- Source tree: `/home/captain/w1700k-openwrt-build/fanboy-source`
- Source commit: `5575e4a97f119f682223a090c4a78c0913f906f5`
- Branch: `main`
- Source status: dirty experimental worktree; exact V6.81 source/build
  provenance is captured by the V6.81 offline evidence set.
- Emitted OpenWrt target name: `gemtek_w1700k-ubi`
- Latest offline candidate:
  `work\w1700k-npu-type5-data-contract-v6.81-20260830-sysupgrade.itb`
- Latest offline candidate SHA256:
  `ae23a15d7a1029127f5e2b4efcba829172cd067b2d293d39ab58c2703e68bb66`
- Latest accepted live image: V6.70, SHA256
  `c076d8501f8f4cfce2442dee08effc7d57be49e18e7197355d77d1ff3ce08998`.
- Latest source patch artifact:
  `work\patches\9999zzzzzzzzzzzz46-mt76-observe-stock-type5-data-contract.patch`
- Proprietary stock kernel/userspace binaries shipped in this image: none intentionally.

## Logging Session Inputs

Checked during this logging session:

- Live WSL source patch stack.
- Latest FinalResult image and SHA256.
- Existing stock-port ledger, audit log, tracker, and patch inventory.
- Extracted stock rootfs.
- Headless Ghidra notes for stock `hostadpt.ko`, `mtk_pci.ko`, `mtk_hwifi.ko`, and NPU mode 3 checklist.

Stock firmware modules available for analysis:

| Stock file | Size |
|---|---:|
| `work\fw_extract\squashfs-root\lib\modules\5.4.55\npu.ko` | 33800 |
| `work\fw_extract\squashfs-root\lib\modules\5.4.55\hostadpt.ko` | 40216 |
| `work\fw_extract\squashfs-root\lib\modules\5.4.55\mtk_pci.ko` | 120920 |
| `work\fw_extract\squashfs-root\lib\modules\5.4.55\mtk_hwifi.ko` | 201552 |
| `work\fw_extract\squashfs-root\lib\modules\5.4.55\mt7990.ko` | 5295088 |
| `work\fw_extract\squashfs-root\lib\modules\5.4.55\mt7990_dbg.ko` | 106640 |
| `work\fw_extract\squashfs-root\lib\modules\5.4.55\mt7991.ko` | 17304 |

Ghidra/headless notes:

- `work\ghidra-headless-20260625\hostadpt.ko.token-string-functions.md`
- `work\ghidra-headless-20260625\mtk_pci.ko.token-string-functions.md`
- `work\ghidra-headless-20260625\mtk_hwifi.ko.token-string-functions.md`
- `work\ghidra-headless-20260625\stock-npu-mode3-port-checklist.md`

## Patch Inventory Snapshot

| Layer/category | Count |
|---|---:|
| `package/kernel/mt76/patches` | 205 |
| `target/linux/airoha/patches-6.18` | 169 |
| `package/firmware/wireless-regdb/patches` | 3 |
| `package/network/utils/iwinfo/patches` | 2 |
| Audited inventory rows | 379 |

Inventory categories:

| Category | Count |
|---|---:|
| `base-upstream` | 105 |
| `mt76-hostadpt-dma` | 97 |
| `ppe-fastpath-policy` | 76 |
| `custom-other` | 50 |
| `npu-firmware-mailbox` | 16 |
| `rro-ba` | 14 |
| `wifi7-eht-muru` | 6 |
| `radio-regdb-luci` | 6 |
| `platform-performance` | 5 |
| `mlo` | 4 |

Inventory status:

| Status | Count | Meaning |
|---|---:|---|
| `REFERENCE` | 155 | Base/upstream or context patches carried by the build. |
| `DONE/PARTIAL` | 31 | Shipped and useful, but not always full stock equivalence. |
| `PARTIAL` | 186 | Stock-derived behavior, guarded logic, or telemetry short of full equivalence. |
| `REFERENCE-IMAGE` | 7 | Stock-derived behavior promoted into completed full sysupgrade images. |

Important: telemetry is not a clone. It is proof of where to dig next. Yes, this distinction matters. A lot.

## Implemented Or Reconstructed From Stock

Status key:

- `DONE`: implemented and built into the custom image line.
- `REFERENCE-IMAGE`: present in the latest promoted image or a named completed full sysupgrade image.
- `DONE/PARTIAL`: useful and shipped, but not byte-equivalent.
- `PARTIAL`: safe subset, guarded behavior, reconstruction, or incomplete equivalence.
- `TELEMETRY`: observed/classified/logged only. Does not own packet fate.
- `LEFT`: not implemented or not proven.

| Area | Status | What stock does | What our builds currently do |
|---|---|---|---|
| NPU firmware loading | `DONE` | Makes NPU firmware available early enough for bring-up. | Uses OpenWrt/Airoha direct firmware loading behavior. |
| NPU monitor and LuCI/debugfs | `DONE` | Exposes firmware state, IRQ state, ring pressure, watchdog-ish state, MIB counters, and mode state. | Exposes PC/watchdog state, IRQ status, ring pressure, MIB summary, firmware counters, mode state, mailbox policy, and capture deltas in LuCI/debugfs. |
| CPU/NPU power and clocks | `DONE/PARTIAL` | Keeps relevant domains/clocks alive enough for offload. | PM-domain and cpufreq fallback patches reduce bring-up/performance-state failures. |
| PPE WLAN offload policy | `PARTIAL` | Models force ring, force QoS, WDMA queues, fast bind, keepalive, multicast, port aggregation, tuple policy. | PPE patches model or expose force ring/QoS, WDMA queue QoS, fast-bind validation, keepalive refresh, multicast-to-CPU, port aggregation, tuple classification, and summaries. |
| `foe_ext` sidecar | `PARTIAL` | Uses vendor `foe_ext` metadata in FastTX and ping-pong decisions. | Shadows word48/word54/type/ACTDP and exports it to mt76. FastTX and ping-pong classifiers use it, but final fate is not fully stock. |
| DstPort/static-rule mirror | `PARTIAL` | Uses DstPort/static-rule/netdev state for FastTX and ping-pong. | Exports DstPort ref/state and ACTDP-to-DstPort mapping. Gates FastTX and classifies ping-pong by that state. |
| FastTX handoff | `PARTIAL/EXPERIMENTAL` | Adjusts headers, resolves DstPort, uses static rules, may consume/drop/direct-xmit. | Guarded FastTX path exists with `foe_ext` gate, DstPort gate, queue map, header adjustment, direct-xmit option, drop/consume classification, and shape checks. |
| Force-to-CPU path | `PARTIAL` | Uses force rings, protocol `0x7275`, reasons `0x16/0x19`, and policy handling. | Classifies force-to-CPU paths, force rings, multicast-to-CPU, keepalive, and selected force-ring metadata. |
| Ping-pong path | `TELEMETRY` | `PpeExtIfPingPongHandler` checks `foe_ext`, DstPort, bridge, L2TP, speed-test, ECNT, and VirIfIdx state, then decides packet fate. | Classifies reason `0x19`, force-CPU overlap, `foe_ext`, ACTDP, DstPort, and vendor-only buckets. No stock-equivalent consume/redirect/drop yet. |
| Hostadpt ring layout | `PARTIAL` | Group0 handles 2.4/5 GHz, group1 handles 6 GHz; TX regs `0xa0..0xbc`, RX regs `0x180..0x19c`; 1024 TX descriptors; stride `0xd0`; cap `0xc0`. | mt76 models group selection, ring sizing, TXP length limits, descriptor ownership fences, doorbell cadence, free-space checks, and 6 GHz group1 mapping. |
| Hostadpt hook contract | `PARTIAL` | Publishes from/to packet hooks, enable/disable interrupt hooks, and WiFi task registration; `mtk_pci.ko` registers RX callbacks and unregisters them at teardown. | Records hook presence, RXDONE register/IRQ bit mapping, WiFi task register/unregister counters, NAPI add/enable counters, IRQ disable-before-schedule counters, hook unregister intent, and RX delivery calls. Packet ownership remains OpenWrt/mt76. |
| Hostadpt IRQ register ops | `REFERENCE-IMAGE` | Enable sets RXDONE0 bit16 or RXDONE1 bit17; disable clears those bits; status ack writes WLAN IRQ status bit16/bit17. | Airoha NPU ops perform the same writes. Current images record per-ring status/enable/disable counters and before/after RXDONE registers. |
| Hostadpt schedule prep | `REFERENCE-IMAGE` | Tasklets call `napi_schedule_prep()` then `__napi_schedule()` only on success. | Current images use stock-style schedule prep and expose success/busy counters. |
| Hostadpt complete-done-zero | `REFERENCE-IMAGE` | RX poll calls `napi_complete_done(napi, 0)` before re-enable behavior. | Current images default `mt76_npu_stock_rx_complete_done_zero = true` and autoload `npu_stock_rx_complete_done_zero=1`. |
| Hostadpt RX process-loop split | `REFERENCE-IMAGE` | `pci_dma_rx_poll_hostadpt_ring0()` repeatedly calls `pci_dma_rx_process_hostadpt()` until budget is consumed or no packet is returned. | Latest image splits NPU RX into `mt76_npu_stock_hostadpt_rx_process_batch()` plus a stock-shaped poll wrapper, with counters for process loops, empty batches, budget batches, and dequeue-null exits. |
| Hostadpt option-type/hook-arg selector | `REFERENCE-IMAGE` | Stock `g_npu_used_opt_type` selects secondary hostadpt qbyte and `_fromHostadptPktHandle_hook()` boolean behavior: option types `<2` use `0x04`, option type `5` uses `0x06`, unsupported types return no secondary bit. | Latest image adds `npu_stock_hostadpt_opt_type`, defaults to `5`, derives hook arg from the selected stock qbyte, exposes opt-type counters/last values, and stops hardcoding every RX process projection as option type 5. |
| Hostadpt TX descriptor lifecycle | `PARTIAL` | Stores SKB latch, maps DMA, writes owner last, reclaims by latch, frees SKB, clears latch, clears owner. | SKB latch tracking, owner fences, cleanup ordering, reclaim-before-burst, direct-xmit guardrails, token shadow accounting, and rollback cleanup exist. |
| Hostadpt RX/scatter/process | `REFERENCE-IMAGE/PARTIAL` | Validates scatter count/length, retries, checks q markers `0x01/0x04`, returns descriptor `data:+0x08` from `_fromHostadptPktHandle_hook()`, projects it into type-5 `local10/local8`, calls `mtk_bus_rx_process(..., 5, skb)`, writes RX CPU index to regs `0x18c/0x19c`, and owns RXDONE polling. Descriptor `info:+0x04` remains PPE/count/reason metadata. | RX scatter validation/reuse, retry accounting, geometry/copy checks, first-info PPE preservation, separate first-data snapshots, corrected observe-only Type-5 projection/decode counters, RX CPU-index accounting, owner-clear ordering, and ring1 option classification exist. Retired info-based Type-5 mutations remain inactive. Final delivery remains OpenWrt/mt76 style. |
| Corrected Type-5 data contract | `TELEMETRY` | Stock hostadpt returns descriptor `data:+0x08`; stock PCI maps it into local10/local8; stock HWiFi observes hook/fate bytes. | V6.81 compile-time asserts descriptor offsets and records raw/projected/decoded per-ring values behind the existing default-false packet-telemetry static key. It does not seed skb CB, alter packet headers, enforce fate, or change dispatch. |
| Historical type-5 RX CB seed | `RETIRED` | Earlier analysis incorrectly treated descriptor `info:+0x04` as the stock Type-5 source. | The old raw-info CB seed/projector/direct-write/fate paths are quarantined and inactive. `info` is retained only for PPE/count/reason handling; V6.81 observes `data` separately. |
| TXP/HIF TXP v3 | `DONE/PARTIAL` | `mtk_hwifi.ko` writes HIF TXP v3 with WM metadata, token IDs, ethertype, and priority fields. | Strict TXP v3 mode, buffer-count semantics, priority, WM metadata, ethertype, BC/MC clone flags, MLO first-link clone keying, priority-control packets, and full-payload TXP length exist. |
| TXFREE/token lifecycle | `PARTIAL` | Parses TX_FREE_DONE v0/v1/v4/v5-via-v4, two token IDs per word, and leak/error counters. | TXFREE v4 acceptance, v4 header priority, pair-word handling, free_tkid accounting, token shadow, rollback cleanup, out-of-range counters, TXFREE bridge readiness, and reclaim gates exist. |
| RRO/BA path | `PARTIAL` | Configures RRO PCIe bases, RXDESC base, ACK-SN mailbox, stop polling, and BA status. | RRO PCIe bases before RXDESC get, ACK-SN ifindex mirroring, RRO indication reassembly, RRO stop-poll status, BA retry lifecycle, and stock BA status handling exist. |
| NPU trans lifecycle | `TELEMETRY` | `npu_assign_trans()` fills `glb_npu_trans1/trans2`; `npu_unassign_trans()` unregisters hostadpt hooks. | Records ACK-SN mailbox state, stock source line `0x5c8`, trans slot assignment, overflow, unassign counters, hook unregister intent, and hook-contract mapping. Does not clone vendor global pointer ownership. |
| Mode 3 readiness | `PARTIAL` | Depends on TX queues, RXDESC, TXDONE/event queue, RX data queues, TXFREE bridge, force-to-CPU mailbox readiness, and trans setup. | Gated on prerequisite bits. TXFREE readiness, force-to-CPU readiness, TX ring publication, TX buffer-space mailboxes, RXDESC returns, TXDONE event setup, RX data queue mailbox state, and trans lifecycle telemetry are exposed. |
| WiFi 7 EHT/MURU | `PARTIAL` | Advertises richer EHT/MURU/NSEP behavior. | EHT puncturing BSS TLV, Multi-RU/OFDMA AP caps, NSEP priority, MURU UL switches, MURU DL/UL config, and MU-MIMO config exist. Runtime depends on firmware/hostapd/driver acceptance. |
| MLO handling | `PARTIAL` | Has link-aware TX/WCID assumptions and BA/MLO tuning. | MLO WCID selection, queue-band mismatch accounting, EAPOL guard, all-active-link routing, BA boundaries, LuCI MLO builder fixes, and radio validation exist. |
| Radio/regdb/LuCI validation | `DONE/PARTIAL` | Avoids invalid radio/channel/width/security combinations. | Radio index mapping, width/channel validation, US/SA regdb-aligned logic, hidden-invalid-field fixes, MLO builder, radio labels, and backend validators exist. |
| Live stock-port capture | `DONE` | Not a stock feature; needed to prove deltas. | `w1700k-wlan-npu-capture` records baseline/final/delta counters from mt76 NPU stats, firmware counters, hostadpt registers, mailbox policy, per-interface `/proc/net/dev`, softirqs, and debugfs. |
| Extra OpenWrt services | `DONE` | Not stock-derived. | LuCI, SQM, adblock + LuCI, SoftEther + LuCI, and W1700K NPU LuCI app are baked into the custom build line. |

## Not Shipped From Stock

Current policy in the audited image line: stock binaries are analysis inputs, not shipped outputs.

Not intentionally shipped:

- stock `npu.ko`
- stock `hostadpt.ko`
- stock `mtk_pci.ko`
- stock `mtk_hwifi.ko`
- stock `mt7990.ko`
- stock `wpad`
- stock `hostapd`
- vendor `wapp`
- vendor `mapd`
- vendor cloud/provisioning stack

This is behavior reconstruction, not smuggling the vendor folder in a trench coat.

## What Is Left Exactly

### 1. Full `mtk_pci.ko` Queue Publication Equivalence

Still missing or not proven:

- Exact PCIe TX queue selection and option-type validation.
- Physical TX queue base publication equivalence under load.
- All TX buffer-space mailbox values and failure handling equivalence.
- NPU-visible TX register/base mapping equivalence.
- RX event/TXDONE ring ownership semantics.
- RX data queue type `6/7` storage and ownership equivalence.
- True stock-equivalent `glb_npu_trans1/trans2` global pointer behavior.
- True stock-equivalent hostadpt hook ownership.

### 2. Full Hostadpt RX Ownership

Still missing:

- Byte-equivalent `pci_dma_rx_process_hostadpt()` behavior.
- Byte-equivalent `pci_dma_rx_poll_hostadpt_ring0()` behavior.
- Real `_fromHostadptPktHandle_hook()` equivalent packet handoff.
- Exact RXDONE interrupt disable/poll/re-enable ownership loop.
- Returned SKBs handed into WiFi RX exactly like stock.

Current boundary: schedule prep, complete-done-zero, RX process-loop split,
RX owner-clear, RX CPU-index accounting, scatter-buffer reuse, and corrected
`data:+0x08` Type-5 observability are present. The old `info:+0x04` Type-5 CB
seed/projector/fate paths are retired and inactive. Packet fate stays with
OpenWrt/mt76.

### 3. Full Ping-Pong Packet Fate

Still missing:

- Bridge checks.
- L2TP checks.
- Speed-test checks.
- ECNT hook state.
- VirIfIdx/DstPort final resolution.
- Final consume/redirect/drop decision.

Current boundary: classify only. No stock-equivalent packet fate yet.

### 4. Full FastTX Equivalence

Still missing:

- Byte-equivalent DstPort/static-rule/RPS internals.
- Full ECNT static-rule side effects.
- Every vendor failure/consume branch.
- Proof under 5 GHz 80 MHz, 5 GHz 160 MHz, MLO, non-MLO, client-client, and routed traffic.

### 5. Full TXFREE/Token Equivalence

Still missing:

- Complete vendor token table model.
- Exact callback/completion ordering in every error path.
- Every v0/v1/v4/v5 free-notify edge case.
- Stress proof that token leak counters match expected behavior.

### 6. Full RRO/BA Equivalence

Still missing:

- Complete RRO indication command queue model.
- All prelink/address-element update paths.
- Stop/start sequencing corner cases.
- Stock-equivalent BA behavior across MLO links.

### 7. Advanced WiFi 7/MLO Feature Policy

Still not confidently exposed as toggles:

- STR-MLMR.
- EMLMR.
- SRS.
- Dynamic reconfiguration.
- TID-to-link mapping controls.
- AFC/standard-power 6 GHz behavior.

### 8. Vendor Userspace WiFi Services

Not cloned:

- vendor `wapp`
- vendor `mapd`
- vendor hostapd/wpad behavior
- vendor cloud/provisioning scripts

Reason: OpenWrt `wpad` plus custom LuCI/backend validation is the current path. Pulling vendor userspace into this stack would add ABI roulette, which is a charming way to waste a weekend.

### 9. Proprietary Module Shipment Policy

Not done:

- Shipping stock `npu.ko`, `hostadpt.ko`, `mtk_pci.ko`, `mtk_hwifi.ko`, or `mt7990.ko`.

If this policy changes later, update this file loudly.

## Latest Image Lineage

Most recent stock-port lineage:

| Image | SHA256 | Purpose |
|---|---|---|
| `w1700k-mode3-gate-20260625-sysupgrade.itb` | `35c0a95f58df85bee298272c363b460b255993e723f346d48e5ac02db5b70019` | Mode 3 gating base. |
| `w1700k-mode3-prereq-state-20260625-sysupgrade.itb` | `ab581eeb36ea40e24d539d1cf3d5ee1f90276759bed5eebc2bde6456d19d6c40` | Prerequisite state telemetry. |
| `w1700k-mode3-txfree-ready-20260625-sysupgrade.itb` | `c96b82e46cbaea60cbdd36a5645fbb6770ecdd4fda89a1637349a7688b2890ce` | TXFREE readiness. |
| `w1700k-mode3-forcecpu-mailbox-ready-20260625-sysupgrade.itb` | `cc85c3bf95f57ce89461f2a2f7708064e83d796bec81b86bff3904da585ba133` | Force-to-CPU mailbox readiness. |
| `w1700k-fasttx-foeext-gated-20260625-sysupgrade.itb` | `72194a6d4160b78a07f1d2861e3cbfa390fa6e563d23aed07a18ec8b2e7d2205` | FastTX gated on `foe_ext`. |
| `w1700k-fasttx-dstport-state-20260625-sysupgrade.itb` | `d74aea7b14dd4a97e25ea6f003bf3d016dcde6ee572c46944369031d48f6ff7e` | FastTX DstPort state. |
| `w1700k-pingpong-dstport-classifier-20260625-sysupgrade.itb` | `fd2e406d8d8e06801e9570a945e67c5844e73f2a0e0848f02a2ed3c4bcf4d260` | Ping-pong DstPort classifier. |
| `w1700k-hostadpt-schedule-prep-20260625-sysupgrade.itb` | `5c0d78e7d03fb60846d9421fe0f4355fa09cb327cd5de5144170b1b33c9ebba6` | Stock-style schedule prep. |
| `w1700k-hostadpt-complete-done-zero-default-20260625-sysupgrade.itb` | `2bfd9105dce00013c1589399951de3f3fe6464551dd845e858f27f6706984c92` | Stock-style `napi_complete_done(napi, 0)`. |
| `w1700k-hostadpt-rx-process-contract-20260625-sysupgrade.itb` | `17e052779404a27bf8f7e76be4460b9247c813005d87fc84ddba22b0a6fc33aa` | Hostadpt RX process q-marker/hook/type-5 telemetry. |
| `w1700k-stock-irq-hooks-20260625-sysupgrade.itb` | `e9cd8202bf14c7c379dda346bd7d5e42eb2ef69946b787da32998446e711e67f` | Hostadpt IRQ register accounting. |
| `w1700k-stock-rx-consume-20260625-sysupgrade.itb` | `4b94ee268848655abc757734dd573af33efcc1a13328ab73745c47e967fef3a2` | RX CPU-index writeback and ring1 option-path accounting. |
| `w1700k-rx-owner-clear-20260625-sysupgrade.itb` | `55fad5468770857d1691061fa642d540f4819ea09f9a6f1687f90f6e84e0d105` | Stock hostadpt RX owner-clear ordering. |
| `w1700k-type5-meta-20260625-sysupgrade.itb` | `626ec77de02f0fed7daf52fd7bb94d92ac56ba4f097d68aa07f1fd59043552e6` | Type-5 RX metadata projection. |
| `w1700k-type5-cb-seed-20260625-sysupgrade.itb` | `10f71ce9d1c915c5e02b2e5b2ac63fa4b612dbab9f035e9f1eb0d03347958073` | Type-5 RX CB clear/rebuild with raw DMA info seed. |
| `w1700k-stock-rx-process-loop-20260625-sysupgrade.itb` | `f315cfc6282768009de84fe506db3a28e1a116f499bcca5ddb1e18b9e2070e04` | Stock-shaped hostadpt RX poll/process loop split. |
| `w1700k-hostadpt-opt-type-hookarg-20260625-sysupgrade.itb` | `b68a40671359c9f0cc7a82225f0e93566a913f2a0c0f3de357c11c980441aba3` | Current reference. Stock `g_npu_used_opt_type` hostadpt qbyte/hook-arg selector model. |

## Future Reference Rules

1. Read this file first.
2. Then read `work\W1700K_STOCK_PORT_LEDGER.md`.
3. Then read `work\W1700K_STOCK_PORT_AUDIT_LOG.md` only if exact patch/image history is needed.
4. Do not promote telemetry to "done" unless it changes packet ownership or behavior and is built into an image.
5. For each new patch, record:
   - stock evidence source
   - patch path
   - status: `DONE`, `PARTIAL`, `TELEMETRY`, `LEFT`, or `REFERENCE-IMAGE`
   - image filename if built
   - SHA256 if promoted
   - what remains after the patch
6. Keep mirrored copies in:
   - `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work`
   - `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult`
   - `/home/captain/w1700k-openwrt-build/fanboy-source`

## Commands/Evidence From This Session

Core checks:

```sh
cd /home/captain/w1700k-openwrt-build/fanboy-source
git rev-parse HEAD
git status --short | wc -l
find package/kernel/mt76/patches -maxdepth 1 -type f -name '*.patch' | wc -l
find target/linux/airoha/patches-6.18 -maxdepth 1 -type f -name '*.patch' | wc -l
find package/firmware/wireless-regdb/patches -maxdepth 1 -type f -name '*.patch' | wc -l
find package/network/utils/iwinfo/patches -maxdepth 1 -type f -name '*.patch' | wc -l
```

PowerShell checks:

```powershell
Get-FileHash -Algorithm SHA256 C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\w1700k-hostadpt-opt-type-hookarg-20260625-sysupgrade.itb
Import-Csv -Delimiter "`t" .\work\W1700K_STOCK_PORT_PATCH_INVENTORY.tsv | Group-Object category
Import-Csv -Delimiter "`t" .\work\W1700K_STOCK_PORT_PATCH_INVENTORY.tsv | Group-Object status
```

## 2026-07-05 Addendum - Stock Token Stress Window Source-Compiled

- WSL source now has `9999zzzzzzzzzzzz10-mt76-npu-add-stock-token-stress-window.patch`.
- Patch SHA256: `ae66e72c8d73b48fef6e6147107facfb3929ed7edb2f39f5db970cc12c3c3593`.
- Added deferred-token pending-current/max/underflow counters, release-latency buckets, and `stock_txfree_defer_token_stress_contract`.
- `make package/kernel/mt76/prepare V=s`: pass.
- `make package/kernel/mt76/compile V=s -j1`: pass.
- Report: `work\W1700K_STOCK_TOKEN_STRESS_SOURCE_COMPILED_20260705.md`.
- Report SHA256: `9dcbf56b53f13e01b3f07b9e8e8092a4e813c9751c652d79d44194cc376f54a7`.
- Later superseded by the sysupgrade image build below.

## 2026-07-05 Addendum - Stock Token Stress LuCI Sysupgrade Image Built

- Image: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\TokenStressLuCI-20260705\w1700k-token-stress-luci-20260705-sysupgrade.itb`.
- Image SHA256: `ad0a51bc72066bd25df50ab4bcaf190853060714e304ba8fc1e16f39bfc8acb4`.
- Source commit: `5575e4a97f119f682223a090c4a78c0913f906f5`.
- Full `make -j$(nproc) V=s`: pass.
- FIT parse: pass, with kernel, FDT, and rootfs present.
- `stock_token_stress` helper JSON and LuCI deferred-token rows are present in rootfs staging.
- `strings mt76.ko` found `stock_txfree_defer_token_stress_contract` and all pending/latency counters.
- Negative proprietary-module check passed for stock `hostadpt.ko`, `mtk_pci.ko`, `mtk_hwifi.ko`, `mt7990*.ko`, and stock `npu.ko`.
- Report: `work\W1700K_STOCK_TOKEN_STRESS_LUCI_IMAGE_REPORT_20260705.md`.
- No router flash or router config change happened.

## 2026-07-05 Addendum - Superseding Image Coverage Audit

- Audit report: `work\W1700K_STOCK_SUPERSEDING_IMAGE_COVERAGE_AUDIT_20260705.md`.
- Copied audit artifact: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\TokenStressLuCI-20260705\w1700k-token-stress-luci-20260705-coverage-audit.md`.
- Copied audit SHA256: `05dd9080118448c64a125d52c83892b16501a40214a9dd9eb9570717f1882bf6`.
- Confirmed the token-stress image also contains `npu-stock-token-layout-map` and `npu-stock-hostadpt-ring-lifecycle`.
- Helper/LuCI source and rootfs staging expose `stock_hostadpt_ring_lifecycle` and `stock_contract_debugfs.token_layout`.
- Read-only live capture attempt: `work\live-captures\readonly-20260705-063903\session-summary.txt`.
- Live capture summary SHA256: `a1fb4946259ac0244db55721091e4ccbffe0bf088f7183f86e9cbe150d4d7714`.
- Live transport result: ping reachable, SSH closed, no visible serial ports, COM3 absent.

## 2026-07-05 Addendum - NPU LuCI Snapshot Export Sysupgrade Image Built

- Image: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\SnapshotExport-20260705\w1700k-npu-snapshot-export-20260705-sysupgrade.itb`.
- Image SHA256: `ecc32a2309834dd69f956c8767151f22945383eb65b1c8b94b01f10c32feebac`.
- Source commit: `5575e4a97f119f682223a090c4a78c0913f906f5`.
- Added helper read-only `snapshot`/`diagnostic-snapshot` command aliases and LuCI `Download snapshot` action on `System > W1700K NPU`.
- Snapshot captures board/kernel state, wireless/network UCI, `wifi status`, `iw` output, station dumps, helper JSON/status/health, module parameters, mt76/mt7996 debugfs, and filtered logs.
- `make package/feeds/luci/luci-app-w1700k-npu/compile V=s -j1`: pass.
- Full `make -j$(nproc) V=s`: pass, `build_end 2026-07-05T06:56:58+03:00 rc=0`.
- FIT parse: pass, with kernel, FDT, rootfs, and `config-1`.
- Negative proprietary-module check passed for stock `hostadpt.ko`, `mtk_pci.ko`, `mtk_hwifi.ko`, `mt7990*.ko`, and stock `npu.ko`.
- Report: `work\W1700K_NPU_LUCI_SNAPSHOT_EXPORT_IMAGE_REPORT_20260705.md`.
- No router flash or router config change happened.
- Boundary remains unchanged: this is an evidence-path image, not a claim that hostadpt packet ownership, TXFREE/token byte-equivalence, ping-pong fate, RRO byte-equivalence, FastTX all-traffic equivalence, or live parity proof is complete.

## 2026-07-05 Addendum - Stock TXFREE Token Parity Source-Compiled

- WSL source now has `9999zzzzzzzzzzzz11-mt76-npu-split-stock-txfree-release-errors.patch`.
- Patch SHA256: `972d14dd68a44f56a1a2552f1808b3fde46d35597cbe20cc5a2cdf5f2988c60c`.
- Added `tx_stock_txfree_defer_token_preclaim_err` for no-pending/not-found/owner-mismatch failures before the stock post-claim release path.
- Kept post-claim release failures under `tx_stock_txfree_defer_token_release_err` and added sub-counters for not-ready, invalid-phy, unregistered-phy, and TXQ NULL.
- Added `MT76_NPU_STOCK_TOKEN_QUARANTINE_TXQ_NULL`, `tx_stock_txfree_defer_token_quarantine_txq_null`, and `stock_txfree_get_tx_q_contract`.
- `make package/kernel/mt76/clean V=s`: pass.
- `make package/kernel/mt76/compile -j1 V=s`: pass.
- Built `mt76.ko` SHA256: `0175012ba52e612d9cc10228fee50b0263709ec9262e8e4728c9d9d4bd0186a9`.
- Built `mt7996e.ko` SHA256: `f5fe1fa1b0acf4c03b6c1c5feeb5aa25ef9ced6f01f627844b1dea8440474890`.
- Report: `work\W1700K_STOCK_TXFREE_TOKEN_PARITY_SOURCE_COMPILED_20260705.md`.
- Report SHA256: `8688cecc9f3b04392d486661bbdd7f8966752ae658b3fb5b53e520754c2e158a`.
- No sysupgrade image, router flash, or router config change happened.

## 2026-07-05 Addendum - Stock TXFREE Token Parity Sysupgrade Image Built

- Image: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\TXFreeTokenParity-20260705\w1700k-txfree-token-parity-20260705-sysupgrade.itb`.
- Image SHA256: `d86bf7644642f687c920a652bec9e959a2e9bcf50955751cc39f05eb9e0bc869`.
- Source commit: `5575e4a97f119f682223a090c4a78c0913f906f5`.
- Full `make -j$(nproc) V=s`: pass, `build_end 2026-07-05T07:48:45+03:00 rc=0`.
- FIT parse: pass, with kernel, FDT, rootfs, and `config-1`.
- Rootfs `mt76.ko` strings found `tx_stock_txfree_defer_token_preclaim_err`, `tx_stock_txfree_defer_token_release_err_txq_null`, and `stock_txfree_get_tx_q_contract`.
- Negative proprietary-module check passed for stock `hostadpt.ko`, `mtk_pci.ko`, `mtk_hwifi.ko`, `mt7990*.ko`, and stock `npu.ko`.
- Image report: `work\W1700K_STOCK_TXFREE_TOKEN_PARITY_IMAGE_REPORT_20260705.md`.
- Image report SHA256: `b2039e2ae7881b5ab3a69ff6561ed985a5a07e8504375bdc81f01ee02dc7ebc2`.
- No router flash or router config change happened.

## 2026-07-05 Addendum - Stock Hostadpt Equivalence Detail Sysupgrade Image Built

- Image: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\HostadptEquivDetail-20260705\w1700k-hostadpt-equiv-detail-20260705-sysupgrade.itb`.
- Image SHA256: `d9613013c7adad309b89a617c535d4fd357cf69680a4b875d5eaf5decb5ff01a`.
- Source commit: `5575e4a97f119f682223a090c4a78c0913f906f5`.
- Added helper JSON `stock_hostadpt_equivalence_detail`.
- Added LuCI rows for hostadpt equivalence detail, non-zero reason buckets, and the last packet-identity sample.
- `sh -n` on helper: pass.
- Windows `node --check` on copied LuCI JS snapshot: pass.
- Helper `json` parse: pass.
- Sequential `package/base-files` and `luci-app-w1700k-npu` compile: pass.
- Full image build with clean Linux PATH: pass.
- FIT parse: pass, with kernel, FDT, rootfs, and `config-1`.
- Rootfs `mt76.ko` strings found `stock_equivalent_tx_path`, `stock_txfree_get_tx_q_contract`, and `tx_stock_hostadpt_equiv_group*`.
- Negative proprietary-module check passed for stock `hostadpt.ko`, `mtk_pci.ko`, `mtk_hwifi.ko`, `mt7990*.ko`, and stock `npu.ko`.
- Image report: `work\W1700K_STOCK_HOSTADPT_EQUIV_DETAIL_IMAGE_REPORT_20260705.md`.
- Copied report SHA256: `08ed5ec5a3ff0e352d1b6f828e82a1800fdc7c80e21875368ca608637129a252`.
- No router flash or router config change happened.
- Boundary unchanged: this is observability only, not live proof of stock hostadpt ownership, TXFREE/token callback equivalence, RRO equivalence, or ping-pong packet fate.

## 2026-07-12 Addendum - MLO Atomic Apply and Fixed Channels

- Captured hostapd ACS contention caused by `radio0.channel=auto` in a tri-band
  MLD and proved partner-link scans repeatedly returned `Resource busy`.
- Proved a member-only reload could leave the MLD with one runtime link.
- Added fixed-channel MLO defaults, backend/boot enforcement, MLO-modal
  channel/width removal, and coordinated netifd partner reloads.
- Live member-only reload now restarts all three radios and restores logical
  links `0,1,2`; browser QA and static/package builds pass.
- Updated report: `work\W1700K_MLO_CLIENT_ASSOC_DIAG_20260712.md`.
- Report SHA256:
  `68ea96e73f2168e1cad01e2d63ac8aefc0cc24427f665eb703e2f56aa820654b`.
- No sysupgrade image was built or flashed. External client association is the
  remaining test boundary.

## 2026-07-13 Addendum - Mode-3 Scan Management Completion Fixed Live

- Two instrumented intermediate images separated queue-reclaim delay from
  management-token completion delay.
- Live mode-3 evidence proved the NPU TX queue was empty while one valid PSD
  token remained pending for normal TXFREE. All tokens eventually balanced.
- Added three ordered patches:
  - `9999ze-mt76-npu-reclaim-before-channel-switch.patch`
  - `9999zf-mt76-npu-reconcile-stale-mgmt-pending.patch`
  - `9999zg-mt76-npu-defer-mgmt-token-completion-on-channel-switch.patch`
- The final patch changes only an active NPU channel-drain decision. It does
  not free a token, unmap payload DMA, release a TXWI/SKB, or bypass TXFREE.
- Built and flashed
  `FinalResult\Experimental\NpuMgmtDefer-20260713\w1700k-npu-mgmt-defer-20260713-sysupgrade.itb`.
- Image SHA256:
  `4a818551b7a70ca8b08a7e4aa01ae1e1854e975b20eff7b61a8be6a93b1d277c`.
- Exact live module hashes match the extracted rootfs.
- Mode-3 validation passed on physical radios 0, 1, and 2. Five 5 GHz
  reload/scan cycles completed in 3-4 seconds with balanced payload/TXFREE
  accounting after every cycle.
- Final mode-3 state: 454 TXFREE token words, zero missing tokens, zero count
  mismatch, zero channel wait timeout, 181 deferred management completions,
  healthy memory, and no captured kernel fault signature.
- The router remains on this experimental image in mode 3.
- Report: `work\W1700K_NPU_MODE3_SCAN_MGMT_DEFER_20260713.md`.
- Full stock hostadpt ring, SKB/bufid, TX doorbell, TXFREE byte-equivalence,
  RRO ownership, and ping-pong packet-fate parity remain unfinished.

## 2026-07-13 Addendum - Host-Adapter Reprobe Ring State Fixed Live

- Ghidra analysis of exact live firmware SHA256
  `51f3583c45b2c356866ee53bd79dac93e10ad069bc75ff516019ea7edb929b79`
  proved its refresh path reloads ring bases but retains private consumers.
- Failed live reprobe evidence captured consumer `53` against new hardware
  DMA index `0`, zero scan lines, `13/0` payload/TXFREE, and `29` channel
  wait timeouts without a provider mailbox timeout.
- Added:
  - `999-65-net-airoha-sync-wlan-hostadpt-rings.patch`
  - `9999zh-mt7996-sync-npu-hostadpt-rings-before-start.patch`
- Strict checkpatch, clean kernel, clean mt76, full image, FIT, firmware,
  symbol-linkage, and forbidden-module gates pass.
- Flashed image:
  `FinalResult\Experimental\NpuHostadptRingSync-20260713\w1700k-npu-hostadpt-ring-sync-20260713-sysupgrade.itb`.
- Image SHA256:
  `96099bb31963b3774c725e67ea98767801188db4f5382468be42f8413364bf96`.
- Three quiesced plus three active-scan zero-delay reprobes passed. Final
  provider synchronization calls/errors: `7/0`.
- Tri-band mode-3 scan smoke passed with zero channel, TXFREE, mailbox,
  synchronization, or critical-kernel-fault deltas.
- Router restored to persistent mode 0 with temporary APs disabled.
- Reproduced the forced-teardown ucode exception at `wdev.uc:182`; moved its
  null check before the `phydev.phy` dereference and passed direct plus actual
  mode-3 reprobe regression tests.
- Integrated current image:
  `FinalResult\Experimental\NpuHostadptRingSyncWdevGuard-20260713\w1700k-npu-hostadpt-ring-sync-wdev-guard-20260713-sysupgrade.itb`.
- Integrated image SHA256:
  `e008a0210ce5755b165087e471fa45cb1f382a4b1598690e2aa68f60dca16e3b`.
- Fresh-rootfs and no-overlay proof passed. Integrated reprobe returned 300
  scan lines, `13/13` payload/TXFREE, sync `2/0`, and no stale-PHY exception.
- Router final state: integrated image, persistent mode 0, temporary APs
  disabled.
- Report:
  `work\W1700K_NPU_HOSTADPT_REPROBE_RING_SYNC_20260713.md`.
- Report SHA256:
  `4966d5fa180de1d4313a82206516c108903ebcbbef43b1d980a664491a7f0e80`.
- Remaining boundaries: sustained wireless throughput/aggregation, full
  hostadpt/TXFREE/RRO ownership, ping-pong packet fate, and the separate
  jailed hostapd control-directory `rmdir` warning.

## 2026-07-13 Addendum - MLO Beacon Root Cause

- Reverted the incorrect contiguous MLD link-ID mapping. Physical radio IDs
  are required by the current mt7996 multi-radio stack.
- Corrected 5+6 GHz links `1,2` became visible to Windows as Wi-Fi 7/WPA3 at
  95 percent signal and were independently visible on the user's iPhone.
- Reverted the coordinated netifd MLD reload after it caused mac80211 teardown
  warnings and an unrecoverable PCIe completion timeout.
- Separated an unresolved warm-reset/RF latch from the MLO generator defect;
  hostapd enabled state alone is not accepted as beacon proof.
- Quarantined the v31-only TX-shape patch and passed an mt76 build without it.
- Updated synthetic and image checks to require physical MLD link IDs.
- Report: `work\W1700K_MLO_BEACON_ROOT_CAUSE_20260713.md`.
- Report SHA256:
  `276835ff40b4a609a3b50a956577ca38ac7667e6ec01dec38bc14bbb142cccad`.
- No sysupgrade image was built or flashed.

## 2026-07-15 Addendum - Full-Reset MMIO Boundary

- Built and live-tested ordered candidates `9999zj` through `9999zp`.
- Deferred selector 6 until reinit, skipped unsafe mode-3 coredump, and proved
  WDT plus HIF2/PCIe interrupt-mask accesses complete before the failure.
- Replaced the MT7990-derived five-bit WFDMA busy mask with documented MT7996
  bits `0x7`; clean prepare, compile, disassembly, FIT, rootfs, firmware,
  package, and forbidden-module checks pass.
- Flashed image SHA256:
  `0beae7c3143e84caabc6787145be9f0db4a7c4e4599928f8da60e4c3e2a43193`.
- Mode 0 full reset passes. Mode 3 boot is healthy, but full reset still
  reaches AER about 190 ms after a successful WFDMA idle marker.
- The next probe targets NPU TX queue flush/sync and its direct PCIe WFDMA
  shadow writes. Router was returned to persistent mode 0 with three APs.
- Report: `work\W1700K_NPU_FULL_RESET_MMIO_NARROWING_20260715.md`.

## 2026-07-16 Addendum - Direct MCU Timeout Handoff

- V6.7 added W1700K CBInfra/core-reload diagnostics and a selectable
  WM/WA/DSP reload mask. Image SHA256:
  `2b1abec0facf8af96c0e39bf5cda81ce20c87755ea7bfc7adde43f33990577d6`.
- Live fault injection proved command `0x00130022` timeout queues
  `reset_work` directly and bypasses the coredump-only NPU handoff.
- V6.8 patch
  `9999zy-mt7996-defer-npu-reset-marking-on-mcu-timeout.patch` moves the
  sleeping handoff into `reset_work` and leaves inactive-NPU behavior intact.
- Strict checkpatch, clean prepare, mt76 compile, full image, FIT, rootfs,
  embedded-module strings, packages, and forbidden-module gates pass.
- Flashed V6.8 SHA256:
  `54ef417fb0a0ee36a96f640e55f734b855ae810acdf59c71e145142061213852`.
- Mode 0 boot/reload and mode 3 initialization pass. The new direct-timeout
  path runs, but graceful WM preparation returns `-5` after a second MCU
  timeout. The safety fallback reproduces the known subsystem-reset AER.
- Router recovered to persistent mode 0 with all three APs online.
- Evidence: `work\live-v6.8-direct-timeout-20260716`.
- Report: `work\W1700K_NPU_DIRECT_TIMEOUT_HANDOFF_20260716.md`.

## 2026-07-16 Addendum - Quiesced CBInfra And Stock SER Dispatch

- Added and built default-off diagnostic patch
  `9999zz-mt7996-allow-quiesced-cbinfra-diagnostic.patch`, SHA256
  `2e00e0cc4550ee25b5285e2a8b77f0e0ac10712aabd9694fe9e3732b61957e72`.
- Flashed V6.9 image SHA256:
  `2c3cdf3f6bbbdb6bee9f0807de421e230c6221cde9330dd7e19a1dcfb65af59f`.
- The direct-timeout handoff completed NPU quiesce and selected the
  unprepared CBInfra diagnostic path.
- Captured stream totals: 10 completed CBInfra pulses, 10 firmware-not-ready
  failures, zero core-reload markers, and zero PCIe AER signatures.
- The router recovered after a manual reboot into persistent mode 0 with all
  three APs online.
- Copied and imported stock `connac_if.ko` and `mtk_hwifi.ko` into Ghidra.
  SHA256 values are respectively
  `52f5c19cacf0febddc73a72247250a7c067039c80b8bbd744f5283a5492e0d28`
  and
  `6d82ba02d96d638da9e80592a63e31c09d2f8603620066b604c1702d1171c8f7`.
- Materialized `connac_if_ser_dispatch` at Ghidra `0x00100ca0` and resolved
  every action through relocation-backed hdev slots.
- Stock action `2` is a full bus/token-manager teardown and rebuild; actions
  `5`, `7`, `8`, and `9` are WFSYS reset, traffic gate, NPU stop, and NPU
  start.
- Stock `mt7990_ser_1_0_v1()` relies on firmware event/ack choreography and
  does not directly invoke action `5` in the analyzed path.
- Evidence: `work\live-v6.9-quiesced-cbinfra-20260716`.
- Report: `work\W1700K_NPU_STOCK_SER_ACTION_MAP_20260716.md`.

## 2026-07-16 Addendum - WM SER ABI And Live-Decrypted Firmware

- Resolved stock `UniCmdSER` command `0x13` down to all four TLV callback
  layouts. Current mt76 matches tag, length, field offset, mask, method, and
  response behavior exactly.
- This reclassifies all prior L1 command tests as valid packets and moves the
  open boundary into firmware runtime gating rather than host serialization.
- Compared current WM build `20260311120504` with stock build
  `20240726161530`; both use nine encrypted regions with shifted text/data
  placement.
- Added a read-only mapped-WM dumper and captured the nine hardware-decrypted
  current regions. Archive SHA256:
  `96e6f372e78ca9aef27424db5daffea203957cbe9da21f30afffaf5fe56c4f30`.
- Created RV32 project `work\ghidra-projects\W1700K_WM_LIVE_20260716` and
  completed full Ghidra autoanalysis. Decrypted text proves L1-L4 SER and all
  host recovery event states exist in the current WM.
- Full region-3 mask samples and a six-pass alternating focused probe found no
  deterministic mask variable. The 19 narrowed addresses are changing
  scheduler, timer, allocator, or queue state.
- Rebooted the router to clear diagnostic mask state. New boot ID is
  `d20d3ef9-f14b-40f2-8b24-bc35bff18d79`; mode 0, tri-radio AP state, memory,
  and error checks pass.
- Next work is firmware function-graph/dispatcher recovery. No V6.10 source
  change or image was created in this pass.
- Report:
  `work\W1700K_WM_SER_ABI_LIVE_DECRYPTION_20260716.md`, SHA256
  `8859973e3288a4670b4d6a92e6d6cb049a08d2430e76d41110f6dce7400a7660`.

## 2026-07-16 Addendum - WM Gate And Native L1

- Recovered the real unified SER dispatcher and handler from the decrypted WM
  function graph.
- Resolved the synthetic trigger predicate to gate word `0x00401484`, magic
  `0x1510`, and `BIT(method)`. The clean gate is zero; exhaustive analysis
  found no loaded-WM writer.
- A fail-safe mode-0 test with `0x15100002` caused stock-staged sequence 104
  to complete native L1 recovery in about 41 ms with all interfaces unchanged.
- Rebooted to clear all RAM-only state; current boot ID is
  `3695fd25-aab8-4d50-b3da-6cc56f658313`, mode 0, gate zero, tri-radio healthy.
- Added guarded patch `9999zzz-mt7996-arm-w1700k-wm-ser-trigger-gate.patch`,
  SHA256
  `cc84e810edbb7340d432c3ff68e605fffa523357d4423202cfdcc4eb7d07a4d7`.
  Clean prepare and mt76 compile pass; full V6.10 image and mode 1-3 L1 tests
  remain pending.
- Evidence archive SHA256:
  `e7a759e70741b6b656d486114a4733bbd55f5b98f67794e29b2b10a825fec21b`.

## 2026-07-16 Addendum - V6.10/V6.11 Native L1 Validation

- Built and flashed V6.10, SHA256
  `8694f21203ed491e2aeeb454a9fbb12308aeeb7dbd5252d735f4fcecdb3e45fa`.
- Native L1 passed once in mode 0 and eleven times in mode 3. The ten-cycle
  mode-3 stress run retained the same boot ID and exact radio state, restored
  the gate after every cycle, and showed no NPU-health or memory regression.
- Confirmed the driver exposes only two real ownership modes: 0 and 3. Modes
  1/2/4 are blocked capability gaps; the earlier list text was misleading.
- Updated the shared helper metadata and verified live JSON exposes only 0/3
  as selectable. Attempts to apply 1/2/4 fail before the modules file changes.
- Built and flashed V6.11, SHA256
  `f08a74cec9c026e7f88f53cd476e72b905c235b08de240088e142f59e1bcba84`.
- Promoted and checksum-verified bundle:
  `FinalResult\Experimental\WmSerGateNativeL1V611-20260716`;
  `SHA256SUMS.txt` SHA256
  `f1a0a86d2dcef627e5db71997bbebe75925d9588f416e7779c4d12111ec95932`.
- FIT, rootfs, package, firmware, forbidden-stock-module, embedded helper,
  module-string, sysupgrade-test, and live hash gates passed.
- V6.11 mode-0 native L1 passed in about 37 ms. Current boot ID is
  `675f8707-32b9-4605-864c-de86d2404bbd`; mode 0 and all three APs are
  healthy with no post-test critical error signature.
- Evidence archive SHA256:
  `527593fe283f0951fd15c065565f40f2aa71d9217c8b2c510d9ac32a2013a9cb`.
- Report:
  `work\W1700K_WM_SER_GATE_NATIVE_L1_V611_20260716.md`, SHA256
  `b7fa273a21bac1000d31db2dd50de6f93c05ff0ed1c84b71209a9d222cc16419`.
- Fatal-assert/download-state recovery and full hostadpt/TXFREE/RRO ownership
  parity remain unfinished.

## 2026-07-16 Addendum - Method-8 And NPU RX Descriptor Hardening

- Completed the stock SER ACK and caller audit. ACK values traverse stock
  WiFi and transport modules to PCI BAR0 `0x2108`, matching current mt76.
- Exhaustive stock references show the FE/WiFi private notifier ABI is not
  wired into the shipped image. The assert TLV handler only logs diagnostics.
- Stock level-100 escalation is reached on PCI RX DMA-address mismatch and
  sends method 8. Current decrypted WM method 8 directly enters native L1 and
  bypasses the method-1 runtime gate.
- Found and fixed an overlapping NPU RX packet-count mask. Packet count is
  bits `31:29`; packet ID remains bits `28:26`.
- Added full scatter-chain preflight and bounded severe-fault handling. The
  host now validates count, completion, length, buffer ownership, and DMA
  address before mutating the SKB or queue tail; persistent faults quiesce RX
  and request method-8 recovery from a delayed worker.
- Patch SHA256 values:
  `7b02b365c767fe13daf9ef9cd4c2c3c72844eee53462388837985f69846a9f5e`
  and
  `842f458c80a588eba8ba98090769557366eb3214ab2d9df4de970d09ccb21c26`.
- Strict checkpatch, synthetic descriptor fixtures, clean mt76 prepare, full
  experimental-NPU compile, and complete image build pass. An initial compile
  exposed a `READ_ONCE()` misuse on a bit-field; it was fixed and the final
  build ran with `pipefail` so logging cannot hide make failures.
- V6.12 candidate SHA256:
  `f258a53282ef1649748d79e05665b77c1114a33d7391d4115f85af1e20231c1b`.
- Candidate is unflashed. Router remains on live-verified V6.11 mode 0 with
  boot ID `675f8707-32b9-4605-864c-de86d2404bbd`.
- Report:
  `work\W1700K_STOCK_SER_ACK_FE_NOTIFIER_20260716.md`, SHA256
  `dd9d9947d6ab8b31d2ad0c4fd99c90b48c50bd3a4cffa46d2bae5c09ccd5b48f`.
- Dead-WM download-state entry and full hostadpt/TXFREE/RRO ownership parity
  remain unfinished.

## 2026-07-16 Addendum - Stock MT7990 DRX Reset Parity

- Recovered the stock MT7990 callback table and the `mtk_pci.ko` bus
  lifecycle that replays it during L1 SER teardown/rebuild.
- Stock hardware init resets primary WFDMA global DTX `0xd420c` and DRX
  `0xd4280`; independent MT7991 code resets secondary `0xd820c` and
  `0xd8280`.
- Current mt7996 reset already quiesces DMA/NPU and resets/refills RX queues,
  but lacked the global DRX write.
- Added MT7990-only primary and HIF2 DRX resets in
  `9999zzzc-mt76-mt7990-reset-rx-dma-indices.patch`, SHA256
  `7642ada8970b1c6ddc2ba2bfdd2d3b06d3514041ad6db3901d6df402594f7950`.
- Static checks and clean mt76 clean/prepare/compile pass. Objdump and a full
  Ghidra analysis of rebuilt `mt7996e.ko` recover both DRX writes in the
  compiled function.
- Full image build initially stopped on an inherited Windows `PATH` entry
  rejected by GNU `find -execdir`; a Linux-only build `PATH` completed the
  same source successfully.
- V6.13 candidate SHA256:
  `2d394402f0a3500bc8256092669680678ae385bee8e5feefb71472edccbb35e4`.
- FIT hashes, rootfs package/firmware inventory, module `.text` identity, and
  forbidden stock-module scans pass. Candidate is unflashed and unpromoted.
- Router remains on V6.11 mode 0 with boot ID
  `675f8707-32b9-4605-864c-de86d2404bbd`.
- Report: `work\W1700K_STOCK_SER_TRANSPORT_PARITY_20260716.md`, SHA256
  `86e9db6e0228d8a06914149a07dd5f7b907f25134b6eaff6cd4c8d074725b6ff`.
- Checked artifact set:
  `work\w1700k-mt7990-drx-reset-v6.13-20260716-SHA256SUMS.txt`, SHA256
  `f15e5722b57d833f9db95e4956a22c6a041b0d5728fd4a167907785eabd36221`.

## 2026-07-16 Addendum - V6.13 Live Validation

- Verified V6.13 image SHA256
  `2d394402f0a3500bc8256092669680678ae385bee8e5feefb71472edccbb35e4`
  on-router, passed `sysupgrade -T`, saved the configuration backup, and
  flashed the identified `gemtek,w1700k-ubi` target.
- Live module SHA256 is
  `b03afaa900fc1423421b4063ba3a013d8e7520e22f00aa78f4afa9bfb7f07de7`.
- Mode 0 passed cold boot, six reload/5 GHz scan iterations, and one native
  L1 recovery with unchanged tri-band state.
- Mode 3 reached ready/balanced NPU lifecycle state and passed three complete
  tri-band scan sweeps, three reload/5 GHz scan iterations, one native L1
  recovery, and ten consecutive native L1 stress cycles.
- Final mode-3 counters show no blocked IRQ, channel wait timeout, missing
  TXFREE token, TXFREE count mismatch, provider timeout, hostadpt sync error,
  or fatal kernel/firmware signature.
- Router remains in persistent mode 3 with boot ID
  `e663e153-7428-47b4-a981-f82ab83db65d` and all three APs online.
- Evidence directory: `work\live-v6.13-mt7990-drx-20260716`.
- Report: `work\W1700K_V613_LIVE_VALIDATION_20260716.md`, SHA256
  `910dee8cc59865a301429921722129505c9dbdaf12988461660a3704de320e01`.
- Live checksum set SHA256:
  `dc5f7f36bb006f16c2db12c3550ef446593e27f608d4edb37b94cf025c1a3e9e`.
- No external-client throughput or MLO association test was run. Dead-WM and
  complete hostadpt/TXFREE/RRO/ping-pong parity remain unresolved.

## 2026-07-16 Addendum - V6.14 Helper Verification Profiles

- Running the installed V6.13 CLI `verify` found a duplicated stale verifier
  profile: CLI treated 42 unfinished full/legacy markers as required while
  JSON correctly used the compact-current profile and passed with zero
  required failures.
- Refactored the helper so CLI and JSON share one compact evaluator. Default
  `verify` now checks the current 13 required markers; `verify-full` keeps the
  old exhaustive list as an explicit diagnostic.
- Live dry-run on V6.13 mode 3 passed all compact markers and runtime surfaces.
  The full diagnostic still reports 42 gaps by design.
- Patch SHA256:
  `533b2ba176c4194ccf5d08a4e861f4b629e7374366c8261ef41f4c77480157b8`.
- Built V6.14 image SHA256:
  `440972a9c7e1ddd213b8a77a5bb0053a6aa21886efc901c84e019e7555e0e149`.
- Image audit proved byte-identical V6.13 kernel, DTB, `mt7996e.ko`,
  `mt76.ko`, and package manifest. NPU firmware inventory and forbidden-stock
  module gates passed.
- Corrected embedded helper SHA256:
  `015bf4911ae4a82865a67866a516710f40e4e306e0724ecc8745d706c1409d41`.
- Report SHA256:
  `8950105a98d4ccd57dea8b7ca03a41d66cb5c87abae2b0221f6895da9fae606c`.
- Checked V6.14 artifact-set SHA256:
  `784c8b19301d7596ba1cf745e1bac565e0b03b70420b061c031da468a276b508`.
- V6.14 remains unflashed at this checkpoint; V6.13 mode 3 remains live.

## 2026-07-16 Addendum - V6.14 Live Validation

- Board, backup, uploaded hash, and `sysupgrade -T` gates passed before V6.14
  was flashed with preserved configuration.
- The installed helper hash matches the audit. Kernel and mt76 module payloads
  remain byte-identical to V6.13.
- Installed compact CLI verification and JSON pass; explicit full verification
  retains the expected 42-gap diagnostic result.
- Mode 0 passed three reload/scan cycles and native L1 after a clean reboot.
  A prior post-reload gate read returned `0xdead2117`; the harness refused the
  trigger and no unsafe recovery request was sent.
- Mode 3 passed ready/balanced NPU health, two complete tri-band scan sweeps,
  three reload/scan cycles, and native L1 with zero channel/TXFREE/provider/
  hostadpt error deltas.
- Router remains in persistent loaded mode 3, boot ID
  `a5b25b61-0a87-4ee1-83d9-9823d93c4614`, with all three APs online and
  1,667,512 KiB available memory.
- Source inspection confirmed the initial mode-0 boot is the deliberate
  per-image production-baseline policy in `95-w1700k-npu-mode`; ordinary
  reboot persistence works after mode 3 is selected.
- Live report SHA256:
  `eae39aa4e9415ca1ce8252791cae49c3f8975946a9ffd8101cfb9ba65061462e`.
- Live checksum-set SHA256:
  `6a128b253112a4569befd99e6598ee5225a650aa91825fbbe8869e19fd7f54ee`.

## 2026-07-16 Addendum - PCI Shutdown Warm-Reboot Teardown

- The V6.14 `0xdead2117` state affected direct BAR and remapped reads while
  WM still answered a read-only SER query. WiFi down/up did not repair it;
  one plain reboot did.
- Hardened the native-L1 preflight to require an idle gate and two exact WM
  predicates. The harness now archives and refuses an unreadable-MMIO state.
- Confirmed Linux reboot invokes only `pci_driver.shutdown`; mt7996 had none.
  Added a shutdown callback following mt7921/mt7925 which runs the normal
  mt7996 PCI remove path and therefore NPU/WFDMA/RRO/token/DMA teardown.
- Strict checkpatch, clean mt76 build, full image build, and packaged-binary
  audit passed. V6.15 image SHA256 is
  `9107077012fd8b3af708f0a6c5e5e1f19c37339625a2d6536a77cda59f642144`.
- Flashed after board/hash/`sysupgrade -T` gates. The exact mode-3 to mode-0
  first boot passed without the sentinel, then three additional complete
  transition cycles passed all MMIO, predicate, AP, scan, and NPU-lifecycle
  assertions.
- Router remains in loaded/persistent mode 3, boot ID
  `7490cf53-4452-4d71-bab3-744e9576061d`. Final native L1 and resource/error
  checks passed.
- Report SHA256:
  `c8076350343648cfa370035f7b15f5146f998a4671a60d2529cd58d2ecebf550`.
- Verified 34-entry checksum set SHA256:
  `b01bdbbde16f0ad0739215e15d55e6764c8b9d135003afd6bdefa4015789f010`.
- Promoted 19 checked payload files to
  `FinalResult\Experimental\PciShutdownWarmRebootV615-20260716`.
  Promotion `SHA256SUMS.txt` SHA256:
  `1542f404e059b2a2d7bbfa084825becdc5593e499687829feb637bb4ba762775`.
- This closes warm-reboot PCI/NPU teardown. It does not close dead-WM or full
  hostadpt/TXFREE/RRO/ping-pong ownership parity.

## 2026-07-17 Addendum - Stock NPU Host-Token Fate Closure

- Continued the offline Goal-2 reverse-engineering pass while serial access is
  unavailable. No router, flash, network, or runtime configuration action was
  taken.
- Imported and saved stock `mtk_hwifi.ko` in Ghidra project
  `W1700KHostadpt20260704` beside stock `mtk_pci.ko` and `hostadpt.ko`.
- Recovered and documented the unnamed 440-byte `mtk_pci.ko` function at
  `00104ce0` as `npu_inline_token_release_to_fifo`.
- Proved stable token IDs, active-ready lookup gating, FIFO head checkout/tail
  release, pre-hostadpt token release, and later hostadpt SKB/DMA reclaim. No
  generation/epoch check exists in the inspected stock token path.
- Closed the v27 late-TXFREE decision: inactive-state rejection and FIFO delay
  are stock safeguards, but the NPU-local completion-token namespace is the
  stronger protection. The active guarded `9999z` copy/remap path already
  preserves that namespace split.
- No source behavior change or image rebuild was justified. Direct-DMA host
  tokens remain TXFREE-owned; only confirmed stock-copy/remap packets complete
  their high host token at consumer advance.
- Report SHA256:
  `019e75325683e8f4999f8ee590258eba469b5d07417f8aa5e04973cf48a8c242`.
- Next offline work: exact hostadpt descriptor publication/doorbell ordering,
  followed by in-flight copy/remap teardown and SER behavior.

## 2026-07-17 Addendum - V6.18 Hostadpt Mapping And Teardown Hardening

- Continued offline while COM3/serial remains unavailable. No router, flash,
  network, or runtime configuration action was taken.
- Closed the stock option-type-5 transport identity from Ghidra profile and
  relocation evidence: group 1 is MT7991 slave `band2 TXD`/6 GHz; group 0 is
  the primary MT7990 2.4/5 GHz transport.
- Reused the already proven stock/OpenWrt descriptor-before-doorbell ordering
  result; no TX hot-path behavior changed.
- Found and fixed a full-device teardown IRQ use-after-free window caused by
  devm NPU RX handlers outliving queue teardown. Also parked the generic TX
  worker before provider stop and made the final bounded stop failure visible.
- Added patch `9999zzzf`, SHA256
  `9296142af132dbb8c3b8eb98b94f9846e43de26c88f39e94a95bf49a64e934a4`.
  Strict checkpatch, clean prepare/compile, and full image build pass.
- Full Ghidra auto-analysis/save of exact final `mt76.ko` and `mt7996e.ko`
  confirms the intended teardown call order. Archive SHA256:
  `ca29bbdabc6717712ddb3d52de4fdd3ffceac3d5f27f34a020556586532cb355`.
- Built V6.18 image SHA256:
  `c5fbe3b6d1eff9a6af7b555aa6f20f1a2e8c2e83dbc55885a8c3e8f34cbe87b1`.
- Report SHA256:
  `f961a96e3dd498f61520837b3824eef9e8eaae5f547cf9c713696d2d9e742ce4`.
- Checked bundle:
  `FinalResult\Experimental\NpuTeardownHardenedV618-20260717-UNFLASHED`.
  All 12 entries verify; checksum-set SHA256 is
  `32ec4399af31d41a73bb8603e9c7cba973fea62ee3d76d9e78ed7ce389b33a64`.
- V6.18 remains unflashed/unpromoted. Tomorrow's sequence is COM3 recovery,
  mode-0 validation, then bounded mode-3 retained-ring and teardown gates.

## 2026-07-17 Addendum - V6.19 Failed-Stop And RRO Ownership

- Continued entirely offline after the user deferred serial access until
  tomorrow. No router, flash, Ethernet, Wi-Fi, or runtime action occurred.
- Recovered stock stop semantics: SET failure does not authorize cleanup;
  stock continues querying until the NPU reports zero. Later complete RV32
  analysis proves this is a fast-path/refill-worker stop state, not global RRO
  pointer-forget or DMA-release authority.
- Corrected the stock timeout units from an earlier interpretation. Ghidra
  proves 100-microsecond polling, making `60000` a 6-second SET timeout and
  `1000` a 100-millisecond GET timeout. The correction preceded the final
  kernel and image builds; no wrong-timeout image was built or flashed.
- Added and compiled `9999zzzg` shutdown/remove separation, `9999zzzh` RRO
  owner wait, and `999-66` provider timeout patches. All pass strict
  checkpatch and clean focused builds.
- Completed full Ghidra analysis/save for the final modules and the complete
  77.5 MB `vmlinux`; kernel analysis took 2,285 seconds and recovered 36,845
  functions. Targeted decompilation confirms every intended ownership edge.
- Complete OpenWrt build and fail-closed FIT/rootfs audit pass. V6.19 image
  SHA256 is
  `0842e6158134cf2e1ac1b3945fa6e1afc3683bf437f2842926d5202eb5277f3e`.
- Report SHA256:
  `6e58248025efe7dab5696098ede07f2808b806677a155fb5e9c2d011b8841040`.
- Checked bundle:
  `FinalResult\Experimental\NpuStopRroOwnershipV619-20260717-UNFLASHED`.
  All 30 entries verify; checksum-set SHA256 is
  `aacfc9ce79050b1b99a8adf1c8bd177e5f12e3b4695b3b9538ff66e5ab9ec9fc`.
- Next live sequence remains serial recovery, mode-0 baseline gates, V6.19
  mode-0 gates, then bounded mode-3 ownership and recovery gates. Broader
  scatter/free-pool/TXFREE/dead-WM/ping-pong parity remains open.

## 2026-07-17 Addendum - V6.20 Host Scatter And RRO Packet Fate

- Continued entirely offline after serial access was deferred until tomorrow.
  No router, flash, Ethernet, Wi-Fi, or runtime action occurred.
- Source/generated-code review found that host NPU scatter was passed as a
  nonlinear SKB into mt7996 paths with contiguous `skb->data` assumptions.
  Stock instead creates one fresh linear SKB. The review also found a
  post-validation descriptor-length reread race.
- Added `9999zzzi` to validate/snapshot complete host scatter metadata,
  preserve first-descriptor classification, copy multi-buffer packets into a
  linear SKB, recycle every source page, clear queue entries, and expose live
  failure/linearization counters.
- Added `9999zzzj` to retain RRO continuation pages as SKB fragments and close
  build-SKB, RX-check, repeat/old, token/page miss, overflow, and length-drop
  page leaks. The existing V6.19 owner reread remains active.
- Both patches pass strict checkpatch. Clean mt76 compile, complete image
  build, generated-code audit, FIT/rootfs/package audit, and exact-module
  Ghidra verification pass.
- Full Ghidra analysis recovered 437 functions from final `mt76.ko` and 603
  from final `mt7996e.ko`. Decompilation confirms the intended packet and page
  ownership edges. Current `vmlinux` is byte-identical to the already fully
  analyzed V6.19 kernel hash.
- V6.20 image SHA256:
  `6ecb1f85ab8d234511298e35571f2b1d083fca44c970915a302d08e907837be7`.
- Report SHA256:
  `d0beccdd2979bcda0e9d0a8949870604e8483564718b2cf4ce52c083ae5a256f`.
- Checked bundle:
  `FinalResult\Experimental\NpuScatterRroV620-20260717-UNFLASHED`.
  All 46 entries verify; checksum-set SHA256 is
  `efcf43846e074f32cf0f20b8929c82c0fd7079b4b791664dca4ba30f058f93e5`.
- V6.20 remains unflashed. Next live sequence is serial recovery, known
  mode-0 baseline gates, V6.20 mode-0 gates, then bounded mode-3 ownership,
  recovery, scatter/RRO, memory, and radio gates.
- Remaining Goal-2 work is TX hostadpt object ownership, residual TXFREE/token
  edges, RRO free-pool/BA byte equivalence, dead-WM recovery, and final
  ping-pong/FastTX behavior.

## 2026-07-17 Addendum - V6.21 TX Token Sweep Convergence

- Continued entirely offline after serial access was deferred until tomorrow.
  No router, flash, Ethernet, Wi-Fi, or runtime action occurred.
- Full TX ownership review found that bulk reset/unregister token reclamation
  bypassed normal diagnostic/accounting, queue-unblock, and waiter-wakeup
  transitions. Token exhaustion followed by reset could leave data queues
  blocked even after the token IDR became empty.
- Added `9999zzzk` to exhaustively reclaim every IDR entry, record reset-owned
  releases, converge token and WED counts, clear queue blocking, reset all
  management counters, and wake waiters last. Patch SHA256:
  `f0cc4a2bc64df9ec1b9cb8ba81b54b2011f3246961074872e6dc2dd9db6bd3a6`.
- Rejected pre-final early-break, AArch64 warning-trap, and wake-order
  variants. None was packaged or flashed.
- Strict checkpatch, 21-file ownership audit, host model, clean focused and
  full builds, image audit, objdump, and independent verifier pass. Full
  Ghidra analysis recovered 603 functions from exact final `mt7996e.ko` and
  confirms the intended reclaim and convergence sequence.
- V6.21 image SHA256:
  `43a9bdaa1f440d56954372e65c9556d52909b20983ec6d0e7de300a911d12b83`.
- Report SHA256:
  `e5ddb917d03cc5c6e90fc9616067f0b6f2c64c7529db6509ea312276b9700900`.
- Checked 53-entry bundle:
  `FinalResult\Experimental\NpuTokenSweepV621-20260717-UNFLASHED`.
  Checksum-set SHA256 is
  `09c123b6cfa1588b289b716184d4d4a47914372fefe37e556d59f4cc4f43447d`.
- V6.21 remains unflashed. Serial return begins with recovery and a known
  mode-0 baseline, followed by V6.21 mode-0 token/reset gates and only then
  bounded mode-3 validation.

## 2026-07-17 Addendum - V6.22 Fail-Closed NPU Recovery

- Continued entirely offline while serial access is deferred until tomorrow.
  No router, flash, Ethernet, Wi-Fi, or runtime action occurred.
- Found destructive continuation after an unconfirmed NPU stop in full reset,
  mac80211 restart after terminal reset failure, diagnostic start after stop
  failure, and stale diagnostic NAPI state flags.
- Added `9999zzzl` to query ownership after SET failure, gate destructive
  cleanup on ownership zero, isolate terminal failures, suppress failed-stop
  recycle start/resume, synchronize NAPI state, and expose
  `npu-reset-isolation`. Patch SHA256:
  `d985eaef36e9fbb6fae6aa54a3e28d889a28c939fbe2c8652c8c890dff4284e8`.
- Corrected one compile-only telemetry mistake: `READ_ONCE()` cannot address a
  C bit-field. The final patch uses direct debugfs reads for five bit-fields;
  strict checkpatch and compile then pass with no new warning relative to
  V6.21.
- Source audit, host failure model, focused/full builds, exact-image audit,
  objdump branch checks, and independent verifier pass. Full Ghidra analysis
  recovered 607 functions and confirms every intended stop/reset/recycle
  control-flow gate.
- V6.22 image SHA256:
  `f3e42a3efb5c2252a6ea800783152493f1f80c90ef9067e186583db6ead7488d`.
- Report SHA256:
  `6b0d2109dcad072e35c6e3ca501d8d95d7268daa24d8191602627f4c014cc1d3`.
- Checked 62-entry bundle:
  `FinalResult\Experimental\NpuFailedStopV622-20260717-UNFLASHED`.
  Checksum-set SHA256 is
  `af62df574c1c613e1dc482159a2dd171d75cdd7a16c0e6b1af8cd4cf82e33eae`.
- V6.22 remains unflashed. Tomorrow starts with COM3 recovery and a known
  V6.15 mode-0 baseline; no V6.22 live assumption is recorded yet.

## 2026-07-17 Addendum - V6.23 Stock TXFREE Envelope

- Continued entirely offline while serial access is deferred until tomorrow.
  No router, flash, Ethernet, Wi-Fi, or runtime action occurred.
- Reconciled the current cumulative TXFREE parser against the prior stock
  Ghidra evidence and found missing RX-byte bounds, missing NPU-active
  wrong-version rejection, and incorrect `count != total` mismatch semantics.
- Live V6.15 trace evidence contains a 64-byte skb with a 32-byte v5 TXFREE
  envelope and unrelated tail data, proving this is not merely theoretical.
- Added `9999zzzm` to enforce stock v4/v5 RX-byte bounds, fail closed on
  malformed/unaligned envelopes and unknown NPU versions, bounds-check every
  dword/lookahead, and restore `freed < expected` accounting. Patch SHA256:
  `2b1f14a223d90cebc5c3a254cf8a3ae30edda1d69f477cf9c82ae57cda129d94`.
- Kept the current guarded token ownership model intact and did not restore
  old token-shadow/qentry/FIFO experiments or unobserved v0/v1/v2 parsing.
- Strict checkpatch, host model, clean focused/full builds, exact-image audit,
  warning comparison, and verifier pass. Full exact-module Ghidra analysis
  recovered 608 functions and confirms the intended control flow.
- V6.23 image SHA256:
  `acb4eed32ce1d596f210663ee72ceae29577f96d66bc5a5abdeb2627012ebabf`.
- Report SHA256:
  `845a69967d3fb6309c601338e053e8d15c927be7b401c0d1d9e9a81c6ab4280a`.
- Checked 64-entry bundle:
  `FinalResult\Experimental\NpuTxfreeEnvelopeV623-20260717-UNFLASHED`.
  Checksum-set SHA256 is
  `d09b467a629a7eb976021bbbf857880a0a12451e67a8ba0d31e4bbeabf906b1a`.
- V6.23 remains unflashed. TXFREE is now closed on paper for observed v5
  firmware/current token ownership; next offline work moves to RRO free-pool
  and BA behavior, followed by dead-WM and FastTX/ping-pong fate.

## 2026-07-17 Addendum - V6.24 RRO Token And BA Integrity

- Continued entirely offline while serial access is deferred until tomorrow.
  No router, flash, Ethernet, Wi-Fi, or runtime action occurred.
- Stock Ghidra comparison recovered descriptor-PA validation before token
  handoff in `mtk_pci.ko`, status-0-only BA session publication and status-3
  retry semantics in `mt_wifi.ko`, and bounded owner polling which continues
  after timeout.
- Rejected V6.24 draft 1 after review found it removed the RX token from IDR
  before validating DMA/null/queue invariants and recycled on failure. The
  rejected image SHA256 is
  `09c559fbd78a8447891463cfc1afe316b1de5d3a2211e5288ae44602c94e4a48`
  and it must never be flashed.
- Added `9999zzzn`, SHA256
  `f5e4c13a7f489b861a8492ad9fd12967388b5801195155ad4a7947ede31f0ce9`,
  for 36-bit descriptor DMA reconstruction, bounded RRO TLVs, status-gated
  BA publication, delete-ID validation, and diagnostics.
- Added corrective `9999zzzo`, SHA256
  `3fa08d380a6d7140b8e0eff3e6ead9e46734ab069ad2209b932c8bba1d958cd8`,
  so lookup, null/queue/DMA validation, and IDR removal occur under one lock.
  Failed claims retain ownership for reset; ambiguous partial heads drop.
- Strict checkpatch, host ownership model, prepared-source audit, clean mt76
  prepare/compile, complete image build, exact FIT/rootfs/module audit,
  warning comparison, and independent verifier all pass.
- Full exact-module Ghidra analysis recovered 610 functions from
  `mt7996e.ko` and 439 from `mt76.ko`. Decompilation proves 36-bit address
  reconstruction, locked validate-before-remove, bounded TLV iteration,
  status-0-only publication, and inclusive `0..1024` delete validation.
- V6.24 image SHA256:
  `ef68f3a032782274ee5cd64975950416139e3624e3f2510e4a4475b89402acd2`.
- Report SHA256:
  `a2e1670c9d81506ed9e832dda8c8df1a3b81fc3054691e2c3034859c6db48dc0`.
- Checked 81-entry bundle:
  `FinalResult\Experimental\NpuRroIntegrityV624-20260717-UNFLASHED`.
  `SHA256SUMS.txt` SHA256 is
  `7ec42919a5090b1311dbe50bb7a083c21bcd9aceccd0080aae5ac01d378b8925`;
  `FILE-MANIFEST.txt` SHA256 is
  `ba3b9d9f758926790cc1af581bd2b04556552bd19f3bf33cdb1231eb3d8af4d8`.
- V6.24 remains unflashed. RRO token/BA integrity is closed on paper for the
  observed stock contracts. Next offline work is dead-WM/fatal-download
  recovery, then final FastTX/ping-pong packet fate.

## 2026-07-17 Addendum - V6.25 Stock Raw-BAR WFSYS Reset

- Continued entirely offline after serial access was deferred until tomorrow.
  No router, flash, Ethernet, Wi-Fi, or runtime action occurred.
- Full stock Ghidra export closed the reset callback chain. Stock
  `mtk_ge_hw_reset()` uses chip-ops slot `+0x28`; MT7990 callback
  `FUN_00100160` toggles `0x1f8600` around a delay; PCI callback
  `FUN_001005c0` writes to `BAR0 + (offset & 0xffffffff)`.
- Found that the existing local reset patch passed `0x1f8600` through
  `mt76_wr()`. On the W1700K's MT7996 map this selected L2 BAR window
  `0x1600` with remap value `0x1f8`, not the stock literal BAR0 offset.
- Added `9999zzzp`, SHA256
  `3f5110ef1e5e7e3ac66db97a974f2a7606d0267cdd484fd32e791bb90711b41f`,
  to issue the `1 -> 1000..1100 us -> 0` pulse through saved original bus-ops
  slot `+8`. Ordinary MT7996 subsystem reset remains unchanged.
- The first mechanical draft contained a stray literal `+` and was rejected
  by compile before any image existed. Two audit-harness text/symbol mistakes
  and one PowerShell stderr-handling mistake were corrected in fresh runs;
  none changed source or candidate bytes.
- Strict checkpatch, clean mt76 prepare/compile, full image build, zero-new-
  warning comparison, source/address fixture, exact FIT/rootfs/module audit,
  and independent verifier pass.
- Full Ghidra analysis recovered 610 functions from the exact final unstripped
  `mt7996e.ko`, SHA256
  `36615647286a66267d2e707ccbe653b5a196678a61895671f396c9c8e52048ee`.
  Decompilation proves both raw writes, delay ordering, both helper call sites,
  unchanged ordinary reset, and the separate `mt7996_wr()` remap path.
- V6.25 image SHA256:
  `6bc32205e00ace586acc59696061ae65a190c639587cb14877c0fe2d3ee99f72`.
- Report SHA256:
  `70db110824e2aad002adf83193dacf5bc4af30ed0db3379e37b4e87dee1c21f5`.
- Checked 99-entry bundle:
  `FinalResult\Experimental\NpuRawBarResetV625-20260717-UNFLASHED`.
  `SHA256SUMS.txt` SHA256 is
  `bb6923ac2b0d277713141f431cf68344b8a12f7e97bfa2127927d6ee94cb7fa8`;
  `FILE-MANIFEST.txt` SHA256 is
  `0543c351b5ed3099d997e645a3f68c7f8a0136ee7017e170f4b581f8b8e16429`.
- V6.25 remains unflashed. The corrected address path is closed offline, but
  dead-WM recovery remains unproven. Tomorrow starts with V6.15 mode-0
  recovery/baseline checks, then V6.25 mode 0, then one bounded mode-3/dead-WM
  serial test. FastTX/ping-pong packet fate remains the next offline phase.

## 2026-07-18 Addendum - V6.26 FastTX Reason-22 Observer and LuCI Cleanup

- Continued entirely offline because serial access is deferred until tomorrow.
  No router, flash, Ethernet, Wi-Fi, browser, or runtime action occurred.
- Recovered the stock FastTX ownership boundary from analyzed `hw_nat.ko` and
  `qdma_lan.ko`: QDMA CPU reason `0x16` calls the exported FastTX hook before
  `eth_type_trans()` and returns immediately when the hook consumes the SKB.
  This proves a consuming handoff belongs before mt76 token/DMA/TXWI/TXFREE
  ownership, not in the disabled post-token mt76 experiments.
- Added target patch `999-57`, SHA256
  `014289ae25ee68068b14729d170899be9a1fbc9ae7eef89e2499891ac832d60f`,
  to observe reason `0x16` with classifier tag `0x7274` while preserving normal
  GRO ownership. The observer does not mutate, redirect, queue, transmit,
  consume, or free packets.
- Reduced the helper's public custom mt76 controls to compiled parameter
  `npu_stock_copy_mode`; retired arguments are scrubbed safely. Removed the
  retired ownership controls from LuCI's keys, refresh, rendered inputs, and
  save jobs while retaining stock parity evidence as read-only diagnostics.
- The source ownership/control verifier passes `21/21`; helper mock tests,
  syntax checks, actionable ShellCheck, strict kernel checkpatch, focused/full
  builds, LuCI clean/compile, warning gate, and exact FIT/rootfs/module/LuCI
  audit pass.
- Full Ghidra auto-analysis of exact `vmlinux.unstripped` SHA256
  `e04b5a4b44db1a77b61d7813b324ad873aef902ade81aabb746a18bac3aa4bb5`
  completed in 2,488 seconds with analysis/save/import success. Named
  decompilation independently shows reason `0x16`, tag `0x7274`, the
  read-only classifier call, and subsequent GRO handoff.
- V6.26 image SHA256:
  `6574b26a54a31c7ad7bd5639f50aa0bdb6f303029d73731386ef1d61f30fe1cc`.
- Report SHA256:
  `09facae869ffb104de4a1df8716d5896300f525187e996d679a02bebbba422d9`.
- Checked 59-file bundle:
  `FinalResult\Experimental\NpuFastTXReason22V626-20260718-UNFLASHED`.
  `SHA256SUMS.txt` SHA256 is
  `58cf717eedf17ea3960c17c77395c23311f53bfde22aed055ca08ab0f9c0e0d4`;
  `FILE-MANIFEST.txt` SHA256 is
  `cc11e944dd3e724c8dd30d2261c9fb9d3e1d8121cf7ff95dccbc25f23775c29d`.
- Draft 1 (`189664...`) and Draft 2 (`22a857...`) are retained only as
  superseded, unflashed provenance. V6.26 is offline verified and not promoted.
- Tomorrow starts from serial-backed mode-0 recovery and the accepted V6.15
  baseline. Then test the cumulative candidate chain deliberately, validate
  reason-`0x16` telemetry, and compare mode 0 versus mode 3 throughput/loss.
  Consuming QDMA-to-WiFi FastTX, dedicated hostadpt rings, SKB/bufid/scatter/
  doorbell ownership, exact TXFREE/RRO final fate, and ping-pong ownership
  remain unimplemented or unproven.

## 2026-07-18 Addendum - V6.27 Stock RX-Info and Tri-Band Metadata

- Continued entirely offline. No router, flash, Ethernet, Wi-Fi, browser, or
  runtime action occurred; serial-backed testing remains deferred until
  tomorrow.
- Corrected the stock observer taxonomy: QDMA reason `0x16` now classifies
  with RX-info tag `0x7275`; tag `0x7274` remains the independent WiFi/NPU TX
  observer. Counters are separate and both paths remain non-consuming.
- Restored physical tri-band metadata at the mt7996/Airoha handoff. mt76 emits
  `band_idx` 0/1/2 in the WDMA queue field. The Airoha PPE preserves that
  physical-band hint and converts it to boolean only for the one-bit WED
  selector.
- Removed stale helper JSON claims that a consuming handoff exists and turned
  the obsolete MT7990 firmware test into a compatibility wrapper around the
  authoritative MT7996/W1700K test.
- Added a 42-check source invariant verifier. It passes `42/42`; strict
  checkpatch, fixture tests, shell/JS syntax, ShellCheck error severity,
  target/kernel and mt76 compilation, and a complete image build pass. The
  first full build failure was traced only to WSL's imported relative Windows
  PATH fragment `Files/Common`; a sanitized Linux PATH completes successfully.
- Exact image audit proves FIT kernel/DTB/rootfs presence, embedded source and
  package equivalence, reason `0x16` plus immediate `0x7275`, WDMA queue
  metadata at offset 17, required OpenWrt packages/firmware, and absence of
  prohibited stock binaries.
- Built immutable unflashed image
  `work\w1700k-stock-rxinfo-triband-v6.27-20260718-sysupgrade.itb`, size
  20,603,708 bytes, SHA256
  `a8485ee4c3477b0833189b76acdfdb24b6458a975883a43dd956f8d7485559be`.
- Report SHA256 is
  `9bfb7f421cf4653c3c7df75da384616067897186aa503bffd0bb6990b7950112`.
  The checked 98-file bundle is
  `FinalResult\Experimental\NpuStockRxInfoTriBandV627-20260718-UNFLASHED`;
  all 97 checksum entries and 96 manifest entries pass. Their file hashes are
  `c7298a18f75da1e8eaf419ffbc22648310d628a3717fe76ea04cc4c763274283`
  and `eb683d29065839ccaad03bffa7438c8933617ae17b011db7f24365d984e9ff03`.
- V6.27 remains unflashed and unpromoted. V6.15 remains the accepted live
  synthetic baseline. Mode 3 does not silently enable the stock ACTDP policy;
  that remains an explicit bounded test action.
- Next offline phase is a precise consuming-QDMA FastTX ownership design. No
  consuming implementation should be enabled until scatter/page-pool,
  direct-XMIT return ownership, fallback, DSA/VLAN, TXFREE/token, and RRO
  contracts have executable tests and serial-backed counters.

## 2026-07-18 Addendum - V6.28 Dormant QDMA-to-WiFi FastTX Consumer

- Continued entirely offline because serial access remains deferred until
  tomorrow. No router, flash, Ethernet, Wi-Fi, browser, or runtime state was
  changed.
- Converted the V6.27 reason-`0x16`/RX-info-`0x7275` observer into a narrowly
  gated optional consumer at the stock QDMA ownership boundary. The built-in
  parameter `stock_wifi_fasttx_consume` is BSS-backed and disabled by default.
- Consumption requires a complete 52..2000-byte linear, unique, uncloned,
  unicast plain IPv4/IPv6 frame, exact stock classification, matching
  FOE-extension type/ACTDP, clear stock reject bits, enabled IRQs, and a live
  same-netns cfg80211 AP/AP-VLAN/STA target. No skb field changes before every
  gate passes.
- Commit clears QDMA ownership, normalizes RX metadata, and invokes exactly
  one `dev_queue_xmit()`. There is no fallback after qdisc ownership transfer.
  Every rejection takes exactly one normal `eth_type_trans()`/PPE-unbind/GRO
  path, preserving page-pool ownership for scatter/nonlinear frames.
- Added detailed disabled/candidate/reject/commit/byte/xmit/fallback debugfs
  counters. Direct ndo, nonlinear/scatter, VLAN, multicast, MVAL, vendor
  rate-limit/RPS, dedicated hostadpt rings, and broader ping-pong ownership
  remain deferred.
- Patch `999-67` SHA256 is
  `b4c14b113eb1cc27aad3e645f6e28add54f905110a9069110412d5c94a665102`.
  Strict checkpatch reports zero errors, warnings, and checks.
- The V6.28 source verifier passes `52/52`. The executable ownership model
  passes 262,144 cases and 262,150 traces with single-owner, balanced-netdev-
  reference, no-precommit-mutation, scatter-decline, and no-post-xmit-fallback
  invariants.
- A clean serial `target/linux/compile -j1` reached its 20-minute wrapper
  limit while still compiling generic kernel code. The same clean partial tree
  completed under `-j4` with no new source warning/error, and the full
  sanitized-PATH OpenWrt image build passed.
- A fresh exact-image audit passed after archiving earlier successful/failed
  audit directories. It byte-compared the decompressed FIT kernel with the
  built `Image`, matched rootfs helpers/LuCI/mt76 modules to package outputs,
  proved the compiled default-off parameter and single qdisc handoff, and
  found required OpenWrt firmware with no stock hostadpt/vendor NPU/WiFi
  binaries. The only message was the expected unprivileged `/dev/console`
  extraction warning.
- Built immutable unflashed image
  `work\w1700k-stock-fasttx-consumer-v6.28-20260718-sysupgrade.itb`, size
  20,607,804 bytes, SHA256
  `d6d5ae7ff73db6b230fb5c8f2438c4c2749fb5457a0931e8f8f076ad941cc584`.
- Report `work\W1700K_STOCK_FASTTX_CONSUMER_V628_20260718.md` SHA256 is
  `adcc02ad50a0fb45fa5f2b3d1f5f300bcc8943a3aaa95bb01a3e6f51f1ccc4f3`;
  design SHA256 is
  `961229325bd1971930dbaf80487c92cb31f7508cba23cf559dfdb65f0c05523f`.
- Staged checked bundle under
  `FinalResult\Experimental\NpuStockFastTxConsumerV628-20260718-UNFLASHED`.
  Linux `sha256sum -c` verifies all 59 entries and the manifest has 58
  payload entries. `SHA256SUMS.txt` SHA256 is
  `c538e6d22d928a0de58280d4f856aa24dbc1696df579141273391105b7c10200`;
  `FILE-MANIFEST.txt` SHA256 is
  `730588520b1e9dc3dc9137f98570854e08173dad759091819a2f0d3a46fd693d`.
- The first package pass was checksum-valid but emitted literal `` `t ``
  text between manifest columns. It is preserved with suffix
  `PRE-MANIFEST-FORMAT-FIX`; the canonical bundle uses real tab separators
  and was regenerated and reverified without changing the image.
- A second valid pre-harness bundle is preserved with suffix
  `PRE-LIVE-GATE-HARNESS`. The canonical bundle adds the live gate, fixture,
  and runbook without changing candidate bytes.
- Added `work\w1700k_v628_fasttx_live_gate.sh`, SHA256
  `37b6bae15358ee0d8a599a66af83c5a3a0733d25d056359b3fad255ffdb6e524`,
  plus fixture SHA256
  `85256580b8b46f33efa4fc6f744b75ca3df86dff7dfa453fb2a37eb905e5ca6f`
  and serial runbook SHA256
  `4c789e2bd3dd07c9ce1cdba6be97f58bca7d864d9d068dd8ad43e692eca9015c`.
  Syntax and ShellCheck error gates pass. The fixture executes snapshot,
  bounded enable, independent auto-disable, ownership/xmit reconciliation,
  archive creation, and final parameter `N` with zero failures.
- V6.28 remains unflashed, unpromoted, and default-off. V6.15 remains the
  accepted live synthetic baseline. Tomorrow begins with a serial-backed
  default-off boot/radio/memory/NPU/traffic gate, followed only then by one
  bounded opt-in counter and throughput test with immediate rollback.
- Full stock parity is not claimed. Dedicated hostadpt TX rings, SKB/bufid and
  TX-doorbell ownership, TXFREE/token and RRO final interaction, MVAL behavior,
  and final NPU ping-pong packet fate remain open or require live proof.

## 2026-07-18 Addendum - V6.29 Guarded FastTX Direct Mode

- Continued offline because COM3 serial access is deferred until tomorrow.
  No router, flash, Ethernet, WiFi, browser, or runtime configuration action
  occurred.
- Completed the stock FastTX runtime-policy pass. All 134 stock modules were
  scanned; no provider installs the optional soft-rate, RPS, or queue-allocation
  hooks. Full stock-kernel cross-reference found only two writes to
  `TCSUPPORT_WIFI_COMMON_MVAL`, and Ghidra confirms the final value is `0x3b`.
  Bit 8 is clear, RPS hooks are null, and `TxShortFlag` is zero, leaving the
  active post-classification path as target selection followed by raw WLAN
  transmit and consumed return.
- Added `999-68-net-airoha-add-guarded-stock-wifi-fasttx-direct.patch`, SHA256
  `79262e4775a3734108261493167fc94a96bc6013f8afb4b61b4dc074d2327cf8`.
  Independent parameter `stock_wifi_fasttx_direct` is BSS-backed, defaults
  off, and cannot act unless the V6.28 consumer also passes every safety gate.
- Direct mode mirrors netdev-core queue selection and uses the public
  `dev_direct_xmit()` wrapper after `q->skb = NULL`. The wrapper retains
  validation and queue locking and consumes incomplete/BUSY returns; there is
  no post-commit fallback. Qdisc/direct/BUSY/per-queue/overflow counters were
  added.
- The V6.29 focused gate passes 25/25, the final-state V6.28 regression gate
  passes 52/52, strict checkpatch passes, and the executable ownership model
  passes 5,242,938 checks over 19 gates and 5 transmit returns.
- Full Ghidra analysis of the exact rebuilt kernel and Airoha object completed
  in 2,404.6 seconds. It recovered 36,847 kernel functions and independently
  confirmed both getters, commit ordering, queue selection, one direct call,
  one qdisc call, inlined BUSY cleanup, terminal post-commit flow, and balanced
  netdev references. Exact hashes are
  `3791ac61edef423cc3649b73cb417215dc5546d275e172e945ed14d1499c4f7c`
  for `vmlinux` and
  `40314361a7475811b26ae10034b0c048049e8e125b04327e56a9527f38eea74f`
  for `airoha_eth.o`.
- Target kernel compilation and the sanitized full OpenWrt build passed. The
  unsanitized attempt failed only at rootfs installation because WSL imported
  relative Windows PATH entry `Files/Common`; its log is preserved.
- Final extraction audit passed: FIT kernel/DTB/rootfs, exact embedded kernel,
  both default-off controls, one direct and one qdisc call, required OpenWrt
  NPU/MT7996 firmware, package/source identity, and no proprietary stock
  binaries.
- Built immutable unflashed image
  `work\w1700k-stock-fasttx-direct-v6.29-20260718-sysupgrade.itb`, size
  20,607,804 bytes, SHA256
  `9b951aef30e36a8049f9031e5242a9a24103a6f30b4a8b0e3d9dbc6155c98e60`.
- Checked canonical bundle:
  `FinalResult\Experimental\NpuStockFastTxDirectV629-20260718-UNFLASHED`.
  It has 81 payload files and 82 verified checksum entries.
  `SHA256SUMS.txt` SHA256 is
  `65145e68e1fd283d6a0b7f612aeccc944c11bddd86f5656412f8e1f41a4e7b30`;
  `FILE-MANIFEST.txt` SHA256 is
  `08cd648854cedcabfc1b0356d35d9cb2f2acc3965fe85ffc2185ac6cf6f8c153`.
- Added a fixture-tested serial gate with snapshot, bounded qdisc, bounded
  direct, watchdog rollback, ownership reconciliation, and reboot proof.
- V6.29 is unflashed and unpromoted. V6.15 remains the accepted live baseline.
  Tomorrow's order is COM3 board/recovery gate, default-off mode-0 health,
  qdisc gate, direct gate, then reboot proof.
- Remaining boundary: exact dedicated hostadpt TX rings, SKB/bufid and scatter
  lifecycle, doorbell ownership, TXFREE/token/RRO interaction under FastTX,
  dead-WM live recovery, final ping-pong fate, and serial performance proof.

## 2026-07-18 Addendum - V6.30 Stock Option-Type-5 TX Topology

- Continued offline because COM3 serial access is deferred until tomorrow.
  No router, flash, Ethernet, WiFi, browser, or runtime state was changed.
- Completed the stock option-type-5 topology pass across `hostadpt.ko`,
  `mt7990.ko`, `mt7991.ko`, and `mtk_pci.ko`. Stock maps 2.4/5 GHz to shared
  group 0/register `0xd4420` and 6 GHz to independent group 1/register
  `0xd8450`.
- Reconciled that topology against the exact prepared mt76 source. The active
  OpenWrt mode-3 map differed in queue identity, physical PCIe window, alias,
  and group assignment. Disabled patch 971 remains retired because it changed
  only a subset of those coupled decisions.
- Added package patch
  `9999zzzz-mt7996-gate-stock-option5-tx-topology.patch`, SHA256
  `ac747a2c209ca6324c0bf4e9b499335deed6d3b6f647b140f785746d91374724`.
  New read-only parameter `w1700k_stock_npu_tx_topology` defaults off and is
  gated by W1700K identity, MT7996, HIF2, and active WLAN NPU state.
- Updated `w1700k-wlan-npu-mode` to validate, persist, and report the new
  probe-time parameter. Its complete LF-only helper patch SHA256 is
  `9d01e3e3d8fb272427a12c53d251605b718ddb97550f7c77550cad58a48f4633`.
  Fixture testing confirms it saves `w1700k_stock_npu_tx_topology=1` and
  returns success with an explicit reboot-required message.
- Clean NPU-enabled mt76 compile and sanitized full image build passed. The
  first full build failed only because Windows injected relative
  `Files/Common` into WSL PATH; no code/build defect was involved.
- Imported and fully analyzed the rebuilt unstripped `mt7996e.ko` and
  `mt76.ko` in Ghidra 12.1. Decompiled probe, DMA-init, queue-init, PHY
  registration, inlined NPU TXD init, and debugfs parity paths independently
  confirm all intended topology branches and the `0xd4420`/`0xd8450` checks.
- Exact FIT/rootfs audit passed. The image ships mode/topology off by default,
  contains the required OpenWrt Airoha NPU firmware, preserves the W1700K UBI
  partition/volume layout, and contains no prohibited stock kernel payloads.
- Built immutable unflashed image
  `work\w1700k-stock-option5-topology-v6.30-20260718-sysupgrade.itb`, size
  20,615,996 bytes, SHA256
  `5d786a855b946d82ddcf2d5ff873e6adf6475631679915e1ca19ab3744af18a6`.
- Offline verification report:
  `work\W1700K_V630_OFFLINE_VERIFICATION_20260718.md`, SHA256
  `2c15144cfe3f096d4bc5629d2fcb322a89f4061df9fe12f1ec4f6a7f6183d270`.
  Topology-closure report:
  `work\W1700K_STOCK_OPTION5_TX_TOPOLOGY_CLOSURE_20260718.md`, SHA256
  `4c1c6f2c826667ed741f0700c18a80edf3aa683279dedec7e83a9fa3c64f8c7c`.
- Checked 22-entry canonical bundle:
  `FinalResult\Experimental\NpuStockOption5TopologyV630-20260718-UNFLASHED`.
  An independent `sha256sum -c` pass succeeds for all entries.
- V6.30 remains unflashed, unpromoted, and default-off. V6.15 remains the
  accepted live baseline; V6.16 remains rejected; V6.17 through V6.30 remain
  offline candidates.
- Tomorrow starts with serial identity/recovery and a default-off mode-0
  health gate. Topology 1 is tested only after a topology-0 mode-3 baseline
  and requires reboot plus debugfs group/register/alias proof.
- Static option-type-5 topology is closed on paper. Full hostadpt packet
  ownership, SKB/bufid/DMA and scatter lifetimes, TXFREE/token/RRO equivalence,
  end-to-end doorbell ownership, ping-pong fate, and performance remain open.

## 2026-07-18 Addendum - V6.30 Host-Adapter Ownership Reconciliation

- Continued offline while serial access remains deferred. No router or live
  network state was touched.
- Loaded the exact packaged V6.30 RV32 blob in Ghidra 12.1 as
  `RISCV:LE:32:RV32IMC` at `ram:84000000`. Analysis recovered 381 functions.
- Assigned evidence-backed names/prototypes to the group poll at `0x8400f638`,
  common worker at `0x8400f0c4`, trampoline at `0x8401de30`, local-token
  allocator/release at `0x84004c16/0x84004b96`, and DMA copy at `0x840053a6`.
- Exact xrefs show group-0 call `0x8400f6cc` and group-1 call `0x8400f788`
  both enter the common worker. The worker alone dispatches through
  `0x8400f0f6` to the appended trampoline, whose three exits return to the
  original continuation at `0x8400f0fa`.
- Decompiled `npu_dma_copy_sync()` proves synchronous payload transfer: source,
  destination, length, and command are programmed, the completion bit is
  polled, and the bit is acknowledged before return.
- Reconciled exact stock descriptor ownership against exact prepared mt76.
  Stock owns the `skb` through descriptor offset `0x08` after early token
  release. V6.30 keeps that slot non-owning and retains host token/TXWI/DMA/
  `skb` ownership until a fully validated copy signature reaches the NPU
  consumer; fallback remains ordinary TXFREE-owned.
- Verified the token partition from prepared source: NPU-local IDs are below
  `MT7996_HW_TOKEN_SIZE=8192`, while active-NPU mt76 host allocation starts at
  8192. Low local TXFREE cannot collide with a host IDR token.
- Re-ran `work\w1700k_v630_hostadpt_ownership_model_20260718.py`, SHA256
  `8d6f807662d995bf485e7e4f278ffb942a09c5130677a8f03ee8fe44e9a65f0c`.
  It passes 756,850 checks across 97,655 event sequences.
- Report:
  `work\W1700K_V630_HOSTADPT_TX_OWNERSHIP_RECONCILIATION_20260718.md`, SHA256
  `1a92d3797c84dba979e58ff7ac817b711ebbdc0f0c9d0ab43f18d85fab399ddc`.
- No source/image mutation followed. The canonical V6.30 bundle was not
  changed after checksum freeze. Serial identity, recovery, boot, topology,
  bounded traffic, reset, and reboot gates remain mandatory.

## 2026-07-18 Addendum - V6.30 Host-Adapter Index and Doorbell Closure

- Continued offline while serial access remains deferred. No router or live
  network state was touched.
- Reconciled exact provider register formulas with stock hostadpt and the
  exact packaged RV32 consumer. Provider `qid + 2` maps group 0/1 to stock
  banks `0xa0/0xb0`; queue offsets `+0/+4/+8/+c` map to base, count, host
  producer `0xa8/0xb8`, and NPU consumer `0xac/0xbc`.
- Exact stock handler writes producer `0xa8/0xb8` and reclaims against
  consumer `0xac/0xbc`. Exact V6.30 RV32 poll has two `0xd0` paths, calls the
  common worker from both, and writes consumer progress to `0xac/0xbc`.
- Exact prepared mt76 sets `q->wed_regs` from the Airoha provider, publishes
  ring geometry, seeds head/tail from `dma_idx`, writes `cpu_idx` after
  `wmb()`, and reclaims to `dma_idx`. Exact module disassembly confirms
  `dsb st`, regmap offsets `+0x08/+0x0c`, `0xd0` stride, and owner-last
  descriptor publication.
- Re-ran the corrected active TX-shape verifier. V6.30 has a one-address TX
  descriptor and linearizes only nonlinear SKBs before DMA mapping while
  rejecting descriptor lengths above 8191. TX scatter/shape is statically
  closed for this ring; RX scatter/RRO is separate.
- Added `tools\verify_w1700k_v630_hostadpt_indices.sh`, SHA256
  `dfee98959006cab645186e07521c3a9d15da7d0b0749f16f2cea762198fc7871`.
  Exact verification passes; a one-byte module mutation is rejected by the
  hash gate.
- Updated `tools\verify_w1700k_doorbell_ordering.sh`, SHA256
  `9590b44f9f69e4ce3750e29f1c4dc8c968eb0c653c332babc2766c629f6a293a`,
  so its verdict reflects host producer ownership while preserving the
  runtime-unproven boundary.
- Report
  `work\W1700K_V630_HOSTADPT_INDEX_DOORBELL_RECONCILIATION_20260718.md`
  SHA256 is
  `2edd11388422baa20ad4e583dbd7f6e3cbc3a1de76c10eae62da8d5ec7bc849c`;
  verification transcript SHA256 is
  `ed57453fa78b69a8dda54eeafbd9e32fda90244a49b492561ff6c9033c0ee13f`.
- No source/image mutation and no V6.31 build followed. V6.30 remains
  checksum-frozen, unflashed, unpromoted, and default-off. Runtime queue
  progress, reset/recovery, loaded TXFREE interaction, packet lifetime,
  RX/RRO, FastTX/ping-pong, and performance remain serial-gated.

## 2026-07-18 Addendum - V6.30 TXFREE and Reset Ownership Closure

- Continued offline while COM3 remains deferred. No router or live network
  state was touched.
- Exact packaged RV32 Ghidra analysis now has 382 recovered functions. Added
  evidence-backed names for selector/GET dispatchers, stop status, worker idle
  handshakes, TXFREE processing, general/RRO/local pools, and ring rebuild.
  Saved project metadata only; packaged firmware remained byte-identical.
- Proved selector 4 plus GET index 3 is a three-member ownership barrier:
  fastpath and TXdone/TXFREE must report idle while RRO refill reports
  ownership released. Raw worker instructions close the stores that the
  decompiler simplified away.
- TXdone clears idle before entering `npu_txfree_process_v630`; both valid
  low-token paths call `npu_local_token_release`, and a full firmware fence
  precedes completion-ring rearm.
- Selector 6 resets the separate general and RRO pools only after idle waits.
  GET index 10 later invokes TXdone ring initialization and reconstructs the
  local-token queue from two 1,024-entry internal rings.
- Reconciled prepared Linux ordering: selector 4/GET3 zero, host token sweep
  and DMA scrub, selector 6, offload/RX setup, GET10 reconstruction, host ring
  sync, selectors 2/7, IRQ enable. A failed stop exits before reclamation.
- Added executable model
  `work\w1700k_v630_txfree_reset_ownership_model_20260718.py`, SHA256
  `c1a704154e659119cdd15d1d6636d473ee575e31b6696cc56001c1fc8b9350b9`.
  It passes 84,683 checks and proves release-before-reuse for the concrete
  8,192-token, 2,048-resident circular pool.
- Added exact verifier
  `tools\verify_w1700k_v630_txfree_reset_ownership.sh`, SHA256
  `c98500ad590b31f50cea908d93335899bc74684d8fc0ff091daf3c57f0552c1c`.
  It passes source, exact module hashes/disassembly, raw RV32, and model output.
- Consolidated Ghidra evidence SHA256 is
  `2e2fdb870ecc4fcd3f3fb2071d8efe5380b4eb5ec66f034662dd8edbdbb2f095`.
  Report SHA256 is
  `ff52b7f3a9780a8e1842a8040ca00a820db424ff726aa473a4bdebe312670994`;
  verification transcript SHA256 is
  `0291bb100a3bac6fa7ffef7c6dedd5de8989db48540df8550d96e1809dd19d47`.
- No behavior patch and no V6.31 image were justified. V6.30 remains frozen,
  unflashed, unpromoted, and default-off. RX/RRO packet equivalence, live
  reset/reboot/traffic progress, FastTX/ping-pong fate, dead-WM recovery, and
  performance remain explicit serial-gated work.

## 2026-07-18 Addendum - V6.31 RRO Fragment Ownership Candidate

- Continued offline after serial access was deferred until tomorrow. No router
  identity check, flash, Ethernet, WiFi, browser, or runtime state changed.
- Found four generated old-path counterexamples where an RRO fault can leave a
  truncated partial chain available to a later descriptor. Added strict
  partial-head teardown and queue poison-until-LS recovery.
- Behavior patch SHA256 is
  `c633e5ebe3ac86b17f4751ff9477e85172a0f2559e67a573f4af5e7ccd7f22d5`.
  The executable model SHA256 is
  `edb792642fc887b1ee2b1c8ad7bf088a28d27085fb67fcbeb0ecc750e1b15fce`;
  it passes 19,530 fixed chains and 12 queue/isolation edge cases.
- Hardened length, reason, allocation, and fragment-overflow failures. Token
  or page integrity failure drops all partial heads, leaves ambiguous token
  ownership in the IDR for reset recovery, ACKs, and stops parsing. Method 8
  works with or without an active NPU object; reset clears poison/fault state.
- Upstream mt76 and exact stock RV32 analysis support treating one address
  element as a self-contained descriptor list. The stock `0xff` signature
  mismatch path retries, then skips and ACKs the entire element. Queue-local
  poison therefore remains the chosen policy, with the nonpublic contract
  recorded as a live-test assumption.
- Focused build and full Ghidra analysis passed. Exact unstripped hashes are
  `0e51f5ce861f70284773b91fce97faf0cb1e60bdb54ea45f7df26610bb83d81e`
  for mt76 and
  `eb1e3e5a82a1229c12ce5db66add608d43a4fa4b060530a2504bfa6c6d67621b`
  for mt7996e; Ghidra recovered 445 and 610 functions respectively.
- Exact verification passes and a one-byte-mutated module is rejected.
  Verifier SHA256 is
  `e45c4e3027c2a46c6a146e804217b964de6679738123e1b8722fc7591ef8690b`;
  transcript SHA256 is
  `9202b04a87e7413381e55d0cc6513c9253a4f137ac714630e7fbf529505d444a`.
- Full build completed in 122.6 seconds. Log SHA256 is
  `670b96516772ffb2e77e0104fd83f24179d6e5e38cbb9591159e77d73202d11b`.
  The only noted warning was an unselected `sdl3` feed dependency on absent
  `libwayland`.
- Frozen image
  `work\w1700k-rro-fragment-ownership-v6.31-20260718-sysupgrade.itb`
  is 20,620,092 bytes and SHA256
  `6756f2d57e0184f362e81b93c0af17fcc67e8b23a96d0cdaaadd3b756f481ee0`.
  FIT metadata and rootfs extraction pass. The internal target identity is
  `gemtek_w1700k-ubi`, matching the only profile in this source tree.
- The first rootfs audit attempt correctly failed because it compared stripped
  image modules with unstripped package-staging modules. The corrected audit
  compares exact stripped APK payloads, passes both module hashes, inventories
  1,146 files, confirms four OpenWrt NPU blobs, and rejects forbidden stock
  kernel/userspace payloads.
- Report SHA256 is
  `d16cb35febb6bd4986eb20c8d55925f05d45c33991b9f8d3f262c19fdf9dcf7f`.
  The separate `NpuRroFragmentOwnershipV631-20260718-UNFLASHED` bundle has
  39 total files and 29,607,794 bytes. Independent checksum replay passes all
  37 payload entries.
- V6.31 remains unflashed, unpromoted, and default-off; V6.15 remains the live
  baseline. COM3 identity, recovery, boot/memory, WiFi, bounded mode-0 traffic,
  opt-in mode-3 traffic, reset, reboot, and fault-counter gates remain pending.

## 2026-07-18 Addendum - Stock Ping-Pong Production-Fate Closure

- Continued offline after COM3 was deferred until tomorrow. No router was
  contacted and the frozen V6.31 image was not changed.
- Imported and fully analyzed exact stock `speedtest.ko` in the existing
  Ghidra 12.1 project, then captured and saved exact decompiles for its init,
  cleanup, ping-pong callback, and terminal send/free function; stock
  `hw_nat.ko` ping-pong/RX handlers; and stock-kernel `GET_HIR()`.
- Recovered kernel export addresses from PREL32 tables. The left-to-right mode
  lives in `.bss`, defaults to zero, has one module importer, six `LDR W`
  references, no module store, no userspace reference, and no recovered
  built-in kernel xref. The value-1/value-2 branches are therefore recorded as
  dormant test behavior rather than production parity work.
- Verified that stock `speedtest.ko` publishes and clears its three callbacks
  atomically and consumes only synthetic VirIf `0x130`/`0x160` traffic by
  send-or-free. It is not the ordinary Ethernet-to-WiFi FastTX path.
- Reconciled the active source: ordinary FastTX remains correctly placed at
  QDMA reason `0x16` before `eth_type_trans()`, with default-off consumer and
  direct-transmit gates. Nineteen retired post-token mt76 ping-pong patches
  remain quarantined and no active patch has that ownership model.
- Executable verifier result: 62 pass, 0 fail,
  `PASS_STOCK_PINGPONG_PRODUCTION_FATE`. Transcript SHA256 is
  `8810dd65a3683137219ba3d0def76b5bc500aafbf5d11c027ee23298ca7338ef`;
  report SHA256 is
  `90566fa504460cfdb521e6ebba7b38df0bd5278365ae95338151fe1b5b199ee3`;
  Ghidra capture manifest SHA256 is
  `6641e8c0ee38d15b3e42e2ca024a9d7448710ff57c858021202a92026acf90ab`.
- Decision: no source mutation, build, V6.32 image, promotion, or router action.
  Static production branch fate is closed; only guarded live FastTX behavior
  and performance remain for serial validation.
- Frozen a separate analysis-only bundle at
  `FinalResult\Analysis\NpuStockPingPongProductionFate-20260718-OFFLINE`.
  It has 36 payloads plus checksum and file manifests, 38 files and 993,629
  bytes. Bundle SHA256-list hash is
  `f840bd56ff79cba9379910e96bda1c074c5c9e30c9bd17be1754eba3cf3a80e0`;
  all outer, evidence-set, and nested Ghidra checksum replays pass.

## 2026-07-18 Addendum - Stock Dead-WM / Action-5 Reset Closure

- Continued offline after the user deferred serial until tomorrow. No router
  identity check, flash, Ethernet, WiFi, browser, UCI, or runtime action was
  performed.
- Verified Ghidra MCP health (Ghidra 12.1, plugin 5.13.1, 204 endpoints), then
  captured 23 critical stock SER/reset functions. Capture checksum-list
  SHA256 is
  `def7692cd70fc67856edb01c01f0115f68858d75252f51194ba55832f193e50f`.
- Because HTTP script execution is disabled, cloned the saved Ghidra project
  and used headless analysis for an exhaustive `mt_wifi.ko` call audit. All
  8,534 functions decompiled with zero failures. Thirteen calls reach
  `asic_ser_handler`; action 5 has zero callers. Audit SHA256 is
  `9613bd94dd3d0f4668ddff45c42c131c7205b219e328d99e8728f9934fec9840`;
  headless log SHA256 is
  `a7e5da966b765d2de9cdff53c2f4473b77786c6d05c4b70b7d923b17472854d8`.
- A fresh complete `connac_if.ko` project independently proves the dormant
  action-5 primitive: dispatcher slot `+0xa8`, chip callback `+0x28`, and a
  1/0 pulse through the PCI BAR0 writer at offset `0x1f8600`. Decompile SHA256
  is `b1416550fb759b1904e11c592f2e69cc6859b41ef7fdff701d6c99e986209538`;
  full-analysis log SHA256 is
  `5982dee1fc0a6090f6ab3049776272403f5738ba0f4a16ef727c436274d45e80`.
- Recovered production SER levels are 0, 5, 10, 50, 51, and 100. None invokes
  action 5. Level 100 sends method 8 to WM, `ser_sys_reset()` is a no-op with
  no references, and the assert event handler is diagnostic only. Stock thus
  contains the hardware primitive but no production dead-WM state machine
  that safely owns and invokes it.
- Compared this boundary against exact V6.31 source and modules. Current order
  closes producers, quiesces NPU ownership, sweeps tokens, scrubs DMA, resets,
  reloads firmware, and reinitializes. The unprepared raw BAR path requires an
  explicit default-false diagnostic gate; failed preconditions leave IRQ,
  NAPI, and worker state isolated.
- Added
  `work\w1700k_dead_wm_reset_state_model_20260718.py`, SHA256
  `06e665d7827fcdcb9720b95891fb22f112c61686e4ad0514f717147104d5a535`,
  and `tools\verify_w1700k_stock_dead_wm_reset.py`, SHA256
  `c4a300450694f05e868fe7e393fb8883a0442ca591da084804cfe1913eb140d9`.
  Verification result is 108 pass, 0 fail; transcript SHA256 is
  `4703021529b765b968b57602fe4f7b66767cda316dcae2b8f38c93c08dbbe2fb`.
- Report SHA256 is
  `27cff11cc03f40221d3289054f33b7e1a20c5919564c575aaa6e68fb78eaa6d5`;
  outer evidence-list SHA256 is
  `dfc9dc6cf2deaa97d2ef14a141ca457fcae4cdf5e05a028d909a1cb12035a877`.
- Frozen analysis bundle:
  `FinalResult\Analysis\NpuStockDeadWmResetBoundary-20260718-OFFLINE`, 67
  payloads plus two manifests, 69 files and 617,927 bytes. Bundle checksum
  SHA256 is
  `9a26a4fafd1120278755af527836c30053b092d8ddfee2b5b5bd4f7cd982d615`;
  file-manifest SHA256 is
  `3e52b8a18701ca154ea7ef78bf53c29699289fe566ecfc09b9cb417ddf866353`.
  Independent three-level checksum replay passes.
- Decision: no source/image mutation and no V6.32 build. V6.31 remains
  byte-identical at SHA256
  `6756f2d57e0184f362e81b93c0af17fcc67e8b23a96d0cdaaadd3b756f481ee0`,
  unflashed, unpromoted, and default-off. Corrected raw-reset entry into
  firmware-download state remains a guarded COM3 test after tomorrow's safer
  identity, boot, WiFi, mode-0, and mode-3 gates.

## 2026-08-05 Addendum - COM3 Recovery And Preflash Gate

- Re-established COM3 at 115200 and positively identified the connected target
  as the W1700K from board identity, DT model, NAND geometry, UBI layout, and
  MT7990/MT7991 PCI endpoints.
- Captured a deterministic installed-image crash: `cfg80211` notifier
  registration faults in `queued_spin_lock_slowpath()`, producing a fatal
  kernel panic before normal service startup. Capture SHA256 is
  `ac4de1ee7ecaaa1c8f70cdccd7dcda877915cd5e2ffcae23d59e05098daa5189`.
- Entered the modern chainloader and successfully transferred, FIT-verified,
  and RAM-booted the known recovery image. The 18,350,080-byte image SHA256 is
  `c121b33c14f83f59f95483905d98e4639a9275da19384e299c80b92c5baa3fda`;
  recovery boot capture SHA256 is
  `9546fe7bcf5db1c9ddd28d0b064d9040352d5de33cfc367ee1d235255651358d`.
- Added and exercised `tools\serve_w1700k_tftp.py` (SHA256
  `4d86fe4201ec38a80e82e949fe7b76b7072f2c2f53d5e55eebc2e6207f57c0fd`).
  The modern client transferred at about 553.7 KiB/s; the legacy ECNT client
  still failed repeatedly and is not the chosen recovery path.
- The recovery session was lost before backups and sysupgrade validation.
  Warm panic reboots wedge the first-stage loader at USXGMII initialization.
  A physical reset returned to normal boot, but the catcher attached after
  default boot; a corrected catcher later timed out after 900 seconds without
  another reset.
- No NAND write happened. V6.31 remains unflashed/unpromoted with SHA256
  `6756f2d57e0184f362e81b93c0af17fcc67e8b23a96d0cdaaadd3b756f481ee0`.
  Resume from a fresh physical reset, RAM recovery, full immutable backup,
  remote SHA256 match, `sysupgrade -T`, and then clean `sysupgrade -n`.

## 2026-08-05 Addendum - cfg80211 ABI Root Cause And Prevention Gate

- Reconciled the live FIT fingerprint to rejected V6.16 R2 netconsole
  diagnostic image SHA256
  `41ef432a944e8155a6b3f1a6ea9d8e66ccaa6ceb13ebe447bd4e43698ee72be1`.
- Disassembled exact cfg80211 and mapped its `+0x10` load to
  `dev->ieee80211_ptr` at offset 976. Built target-kernel layout probes with
  and without NETPOLL; results are 976 and 984 respectively. This confirms an
  eight-byte kernel/module layout mismatch behind the live cfg80211 panic.
- Added and executed a permanent image-level ABI gate. It extracts the exact
  candidate FIT kernel/rootfs, requires the kernel payload to match the probed
  source build, decodes cfg80211's AArch64 field load, compares it with the
  compiled kernel layout, and proves its deliberate NETPOLL sensitivity.
- V6.31 passes: exact candidate and source kernel SHA256 are both
  `690016fa7ca3277db033e5be4536f4367314bc0b8a8524b4abd5b3608e50401e`;
  cfg80211 and kernel both report offset 976; NETPOLL and NETCONSOLE are off.
  The existing RRO verifier and its mutated-module rejection also pass after
  ABI-gate integration.
- Root-cause report SHA256 is
  `785c2a908c4a02950d658086190b5bc04d0193574f6936eac95acc284ce31a0a`;
  full integrated transcript SHA256 is
  `4c612eff9d9b10884f00ca25a6669f56ba102867561db9d293be7011767ebc6f`.
- No image bytes changed and no NAND write occurred. Frozen V6.31 remains
  SHA256
  `6756f2d57e0184f362e81b93c0af17fcc67e8b23a96d0cdaaadd3b756f481ee0`,
  unflashed and unpromoted. A cold cycle and RAM recovery are still required
  for backup, `sysupgrade -T`, `sysupgrade -n`, and live radio/NPU gates.

## 2026-08-05 Addendum - V6.32 Reconciliation Build And Offline Gate

- Source helper cleanup removes active write support for retired mt76 NPU
  controls, keeps stale module-argument scrubbing, and leaves
  `npu_stock_copy_mode` as the supported mt76 policy. Helper and fixture
  SHA256 values are
  `955cab542f239399f2f2ff6ebf2c81b4199c3511bcaf7c3a4d5838e182bd2ac5`
  and
  `49c9085073e6805f2659ea1bc3ff14f1e2dc67faafec44bc73626642c7b107cb`.
- Found and fixed a baseline-build regression in the final RRO patch: two
  unconditional mt7996 call sites had declarations only under
  `CONFIG_MT76_NPU`. Added false/no-op disabled-build stubs. Final patch
  SHA256 is
  `01eb14c4494a03b773dff46d4803491b210a14ebe595dc46cc052ff4f3deb3c4`;
  strict checkpatch is clean. Clean baseline and explicit experimental-NPU
  module builds both pass.
- Full image build passed after removing an inherited malformed Windows PATH
  component from the WSL build environment. Passing build log SHA256 is
  `f5ccdff6b251030218b8c06f9c86ac988946cbf33179af696af0056a4c8fb99a`.
  Frozen candidate is
  `work\w1700k-rro-fragment-ownership-v6.32-20260805-sysupgrade.itb`,
  20,615,996 bytes, SHA256
  `30352f9a8aa84c4447352c87c89346f6bc8b553a82fb49c36eb56bc76f091cb1`.
- Exact image audit passes with required OpenWrt WiFi/NPU firmware and
  packages, no forbidden stock binaries, and 81,092 bytes of fit-volume
  headroom. The permanent cfg80211 ABI gate passes at offset 976 with NETPOLL
  and NETCONSOLE disabled.
- Candidate kernel and shipped mt76/mt7996e modules are byte-identical to
  V6.31. A new ELF comparator proves every allocated runtime section in the
  current unstripped modules equals the archived full-Ghidra V6.31 input;
  only `.note.gnu.build-id` differs. The only rootfs content changes are the
  helper and APK database metadata.
- Reusable audit script SHA256 is
  `656c603d4d0f848bc46932b38b5b070877d121a6480a2e22d5b58ef141573804`;
  ELF comparator SHA256 is
  `601329be42b283b46ed6a6e29d0ef6e500e9f65f6419147cd43db4331b85facc`;
  V6.32 gate SHA256 is
  `da9c47dbfe4fd9c501c0b73414b2cd9a5b3da3c6aae853c06d5b39ce8a0aa764`.
  Frozen verification passes; transcript SHA256 is
  `bf16554e80e47cac113520f93ae17634dd725a7aa8c123d6199ecc728963a911`.
- Patch-corpus replay covers 6,364 patches with no active/local or disabled
  experimental structural issues. The 111 remaining findings are confined to
  upstream patches.
- Live recovery did not advance. Armed COM3 catchers ran for 300 and 600
  seconds with zero bytes; Ethernet never dropped, proving no new cold cycle
  happened during either window. DTR/RTS pulses also had no effect. V6.32 was
  not flashed or promoted to FinalResult, and no NAND, UBI, bootloader,
  environment, factory, or calibration write occurred. Resume from a true
  cold power cycle with the catcher already open, then RAM recovery, backup,
  `sysupgrade -T`, and clean `sysupgrade -n`.

## 2026-08-05 Addendum - V6.33 Upstream mt76 Build, Audit, And Armed Catcher

- Rebased all 74 local mt76 patches from
  `59676919ea408b0b13a9d23f2e2e1a1ab407fba1` onto official upstream
  `b2704cf5a4068b672bf47ad5bf6b4802b6770a90`. Range comparison maps every
  patch one-to-one with no additions or drops. Strict git application is
  clean, but OpenWrt's `patch` replay still emits line-offset relocation
  messages; the corrected count is recorded in the V6.34 addendum below.
- Rejected three intermediate images after independent audits found,
  respectively, disabled WLAN NPU support, missing W1700K WLAN NPU firmware
  from stale generated metadata, and stale readline compatibility libraries.
- Final clean build produced
  `work\w1700k-mt76-upstream-v6.33-20260805-sysupgrade.itb`, 20,615,996
  bytes, SHA256
  `8363ca764cd14a749a1731235df6d6b012d725063fd148ac6d7834c410122c52`.
  The exact FIT/rootfs, firmware/package, forbidden-binary, cfg80211 ABI,
  patch, LuCI, radio-width, wireless-validator, NPU-mode, and JavaScript gates
  pass. Final verifier summary SHA256 is
  `e5c056661322398255a6ccf89360de04f4ca3121d7de5c867107156cb6d31f14`.
- Full Ghidra auto-analysis completed for both exact unstripped modules. mt76
  yielded 443 functions and mt7996e yielded 614; report SHA256 values are
  `7bdb505286c1fc11ee52577ba368c61373c4f1ca31b5658179c5ec55f5bde9cc`
  and
  `47fbfd69fcbf2f117135e62c6084ad1cdf9ab8166ce44a60f4d36598956c6c92`.
- Promoted the real mt76 mirror hash, all rebased patches, and refreshed
  Airoha target patches into the canonical source. A clean canonical compile
  passes, and every allocated runtime section matches the candidate build
  except build-id metadata.
- Stopped the obsolete V6.32 catcher before arming
  `work\w1700k-com3-recover-v633.ps1`. The active run is
  `work\live-captures\v633-recovery-20260805-081849`; exact image/recovery
  preflight passed, read-only TFTP is bound to Ethernet link-local, and COM3
  is open at 115200 8N1. The subsequent reported reboot generated zero serial
  bytes. The automated chain therefore performed no flash or backup action.
  V6.15 remains the accepted live baseline; no NAND, UBI, bootloader,
  environment, factory, or calibration write occurred.

## 2026-08-05 Addendum - V6.34 MLO Active-Link And CA Idempotence Gate

- Found a custom MLO TX selection bug: policies 1 and 2 could choose a
  station-valid link that was inactive in the VIF or had a disabled WCID.
  Added a strict active-link intersection and fail-closed selection patch,
  SHA256
  `1fe09f410c922391a793b715135ae6d147b0e7866e5f62254c705f568b68184f`.
  Upstream policy 0 remains unchanged. Exhaustive model verification passes
  884,736 cases.
- Full Ghidra analysis of exact final mt76 and mt7996e inputs completed with
  443 and 615 functions. Report SHA256 values are
  `200861e671722d0c765e1b011152a713742a94a118ab192af4b4666325b967f8`
  and
  `59f9647a1a2a1affa9757999b4b3373d5f6f4dbbe04d5d7fa7c25d5783aae44c`.
- Rejected the first image because repeated CA generation produced 241 PEM
  blocks with only 121 unique hashes. Added package compile guard SHA256
  `42cc1072dfe880439b199fe2b525d73551310ee48c97c83d7f0852ef6dc29ced`;
  forced re-entry now remains at 121 unique certificates.
- Final candidate:
  `work\w1700k-mlo-active-link-v6.34-20260805-sysupgrade.itb`, 20,615,996
  bytes, SHA256
  `45b00fd31cb91492678091bb768abf1d47833eb7e0b149b262b16a7998cc3a21`.
  Exact verification reports `PASS_V634_CANDIDATE`; verifier SHA256 is
  `434ac04d55862b230cf0d462502b03e70126ce054832de91f53f2e012da568d6`.
  Kernel code normalizes byte-identical to V6.33, DTB is identical, rootfs
  shape is unchanged, cfg80211 ABI passes at 976, selected APK signatures
  verify, and the final CA bundle contains 121 certificates.
- Corrected replay wording: the final 75-patch OpenWrt replay has zero fuzz,
  zero rejects, and 205 line-offset messages. Earlier language claiming no
  offsets was too broad; strict git mapping/application remains clean.
- Offline evidence bundle has 36 files and 39,132,095 bytes at
  `work\candidate-bundles\W1700K-V6.34-MLO-Active-Link-20260805-OFFLINE`.
  Payload-list and manifest SHA256 values are
  `680d10ac157c12af2edff6fb94ef6cfb80b7fa036f67c973bea4baecfd23e7a9`
  and
  `02f8b6d2da4f9871707ef65ec13501a5fd46d602889576565ebd54a4114758ed`.
- COM3 catcher state remains zero bytes after the reported reboot. V6.34 was
  not flashed or promoted, and no NAND, UBI, bootloader, environment,
  factory, or calibration write occurred. V6.15 remains the accepted live
  baseline.

## 2026-08-05 Addendum - V6.34 Catcher Refresh And Physical UART Boundary

- Stopped the stale V6.33 catcher. A direct COM3 probe at 115200 8N1, with
  DTR and RTS disabled, received zero bytes despite Windows enumerating the
  PL2303GC adapter as healthy. The completed cold cycle also produced no bytes
  in the prior armed capture.
- Ethernet remained linked at 1 Gbps but had no ARP or IPv6 peer. A blind
  sequence restricted to boot interruption, the known read-only chainloader
  command, RAM TFTP load, and RAM boot generated no request at the read-only
  TFTP server. No persistent command was sent.
- Created `work\w1700k-com3-recover-v634.ps1`, SHA256
  `fb7bd49db8e9faa6fc28347218833d5e5ad9af0c30cb09caee2ee178e7c4c56c`.
  It pins V6.34 SHA256
  `45b00fd31cb91492678091bb768abf1d47833eb7e0b149b262b16a7998cc3a21`
  and verifier-result SHA256
  `07d7f26ff1c1834f1335ffdc065acb405e405b498d638759b3cff1ffaee7cb3d`;
  standalone preflight passes.
- Armed `work\live-captures\v634-recovery-20260805-100740`. COM3 is open at
  115200 8N1 and read-only TFTP is listening on `169.254.66.29:69`, but the
  capture remains zero bytes. No recovery, backup, `sysupgrade -T`, flash, or
  postboot gate has run. V6.34 remains unflashed; V6.15 remains the accepted
  live baseline, and no NAND, UBI, bootloader, environment, factory, or
  calibration write occurred.

## 2026-08-05 Addendum - Post-Reboot COM3 Reopen

- Retired the first V6.34 catcher after it captured no reboot output. A fresh
  direct COM3 open at 115200 8N1, with DTR/RTS disabled, sent only Enter for
  eight seconds and received zero bytes. Evidence is
  `work\live-captures\v634-recovery-20260805-100740\direct-probe-after-reboot.raw`.
- Ethernet retained carrier, but source-bound link-local probes found no
  W1700K peer. The new guarded run is
  `work\live-captures\v634-recovery-20260805-102122`; exact preflight passed,
  read-only TFTP and COM3 are open, and the serial capture remains zero bytes.
- The live state has not advanced: no U-Boot prompt, RAM recovery, raw backup,
  `sysupgrade -T`, flash, or postboot validation occurred. V6.34 remains
  unflashed, V6.15 remains the accepted live baseline, and no NAND, UBI,
  bootloader, environment, factory, or calibration write occurred.

## 2026-08-05 Addendum - V6.35 MLO TX Ownership Alignment

- Audited the remaining MLO transmit pipeline and found policy 0 could derive
  the queue/PHY from the setup WCID before mt7996 changed the TXWI WCID. This
  violated one-owner bookkeeping across queue entry, non-AQL accounting, NPU
  completion, and TXFREE. Added all-policy early WCID alignment patch SHA256
  `c39aae62009a05bee4c261f656dfe610b6969b4ace776580ffc1957c4a9015e3`.
  No-eligible teardown races now return `-ENOLINK` before token allocation;
  policy 2 prefers 5/6 GHz and is the default.
- Stock/Ghidra field-copy evidence showed the complete peer EML capability is
  passed to STA_REC_EHT_MLD. Replaced the prior mask with direct 16-bit
  forwarding in patch SHA256
  `dc7048b7fae4c05c319cb22fe3275dd0d1f7a293c8a92e6f69c16819689911ec`.
  This is ABI parity only, not an EMLMR runtime claim.
- Exhaustive verifier SHA256
  `3d57da0bbb8cdcda7f8d593782cafb259b818b843d6f4fd6df2695ee2b570f4e`
  reports `PASS_V635_MLO_TX_ALIGNMENT` after 5,308,416 checks. Strict
  checkpatch and all component/fixture gates pass.
- Offline inspection rejected the first image, SHA256
  `b744a342d25be57d422f2726b3713c3b09f5406710d57ae830d59dba42e9c9ae`,
  because the build omitted `W1700K_EXPERIMENTAL_MT76_NPU=1` and therefore
  dropped the Airoha NPU transport from mt76. It was quarantined and never
  flashed. Added pinned build runner `work\run_v635_build.sh`; the clean
  NPU-enabled build passed.
- Accepted candidate is
  `work\w1700k-mlo-tx-aligned-v6.35-20260805-sysupgrade.itb`, 20,615,996
  bytes, SHA256
  `2e0ff1abd37cc0a971ca3e89b4f38c5fc79e3245e8b801452f74619219625da1`.
  Exact verifier SHA256
  `1277fd206fdfc6b1e0fd25352d662307a219071803aa76310cf2c13f1d840934`
  reports `PASS_V635_CANDIDATE`; result SHA256 is
  `e0e68cb1dffef2beb93e095bddadf19b046aa05f5a9d24fe99a39dbc85ea6152`.
  Kernel, DTB, NPU-enabled mt76, package contracts, and rootfs shape match
  V6.34. Only mt7996e, helper, LuCI, and APK bookkeeping changed.
- Fresh Ghidra 12.1.2 full analyses passed for both exact unstripped modules.
  Report SHA256 values are
  `78b8719f43811834bdba9b1e75b7425ee689cfe23608bfb37356048809883a6a`
  and
  `32bc58137772786d4333917674face7ebdd1ea01f6af83f2277701dccfc5bb9a`.
  The decompile confirms active-link filtering before queue ownership,
  fail-closed TX preparation, and the full EML-cap copy.
- Frozen bundle path is
  `work\candidate-bundles\W1700K-V6.35-MLO-TX-Alignment-20260805-OFFLINE`.
  It contains 28 files and 27,448,190 bytes. Payload-list and manifest SHA256
  values are
  `03002326a2734005f4c2837099f0155a21f0b3028acf77c70bd69c08814f0267`
  and
  `ff11ed88e8be8b4ea6bf5f5795dd54e228bfbc5658f1bfd3dec3efa882fc7f35`;
  checksum replay passes. FinalResult has the accepted image, manifest,
  report, and checksum list only.
- V6.35 recovery harness SHA256
  `44be37cb2ca5097a1619e5de4b38d6691129aa09e5911b5e2d63b00213ae92a6`
  passes exact non-writing preflight. A post-reboot COM3 probe still received
  zero bytes; Ethernet retained 1 Gbps carrier but exposed no IPv4 or IPv6
  peer. No bootloader, RAM recovery, backup, `sysupgrade -T`, flash, or
  postboot validation ran. V6.35 is unflashed, V6.15 remains the accepted live
  baseline, and no NAND, UBI, bootloader, environment, factory, or
  calibration write occurred.

## 2026-08-05 Addendum - V6.36 NPU Hot-Path Hardening

- Audited the production mt76 NPU TX/RX path after V6.35. Found one concrete
  TX descriptor-length boundary: validation ran before two-byte header-pad
  insertion even though the NPU descriptor encodes only 13 length bits. The
  V6.36 patch validates final post-pad length before payload DMA mapping and
  uses the existing TXWI cleanup path.
- Matched the NPU RX poll structure to generic mt76 by moving completion to
  one call after queue refill per NAPI poll. First descriptor fragments now
  require four bytes; short continuation fragments remain valid. Descriptor
  history sampling now runs only for the first fragment of TX/RX notification
  packets, not every data packet.
- Added runtime-writable `npu_deep_trace`, default `0`, to gate detailed
  token, ordering, and TXFREE histories. Aggregate counters, ownership
  bitmaps, classification, and fail-closed guards remain always enabled. The
  helper fixture and LuCI control pass and preserve the default-off value.
- Pinned full build with `W1700K_EXPERIMENTAL_MT76_NPU=1` exited 0. Accepted
  image is `work\w1700k-npu-hotpath-v6.36-20260805-sysupgrade.itb`, SHA256
  `c7a3120d8a20816b58fa5011a8032ed654dff45540b18876ee61a8bcbe7a5eb9`.
  It is 20,615,996 bytes and leaves 81,092 bytes FIT headroom.
- Exact verifier SHA256
  `1436ae171cfef18e4d72e6746426252ce92d6edf5b88a9406c53c0e0835f06e9`
  reports `PASS_V636_CANDIDATE`. Kernel and DTB are byte-identical to V6.35;
  rootfs shape, package contracts, and maintainer scripts remain equivalent.
  Only mt76, mt7996e, NPU helper/LuCI, and APK bookkeeping differ.
- Full Ghidra analysis completed for exact rebuilt unstripped mt76 and
  mt7996e. Reports contain 445 and 614 functions and have SHA256 values
  `4a468209480cee4e9d586f46ed5a9b34289597484d073a4f9bee1abffba1ca04`
  and
  `4d8ae42364846161c8ebcde3c4df1c1e756846a08d0e05c38b1ff6d29319972e`.
  Decompile evidence includes the post-pad TX guard, 8,191-byte limit,
  runtime deep-trace gate, TXFREE-side consumer, and NPU RX poll.
- Frozen bundle is
  `work\candidate-bundles\W1700K-V6.36-NPU-Hotpath-20260805-OFFLINE`, 27
  files and 29,450,568 bytes. Payload and manifest SHA256 values are
  `cd4653694db40d068545d02a8253f5ba3eb764f136496e5ea7553f6414599cf1`
  and
  `7af8d59410c3e281e5d12b6dfc20bd559a152092fa848ec02e9ba88ed6684a95`;
  checksum replay passes.
- Live status remains blocked below the firmware layer: COM3 enumerates but
  produced zero bytes at 115200 8N1 after reboot/Enter, while Ethernet has
  1 Gbps carrier but no DHCP, ARP peer, or management path. V6.36 was not
  flashed. No persistent router write occurred and V6.15 remains the accepted
  live baseline.
- Remaining Goal 2 boundary is unchanged: dedicated host-adapter TX rings,
  SKB/bufid lifecycle, scatter recycle, doorbell ownership, TXFREE/token
  release, RRO ownership, and final packet fate still require stock/OpenWrt
  evidence reconciliation and staged live validation.

## 2026-08-05 Addendum - V6.37 NPU MAC-TXP DMA Pairing

- Continued the V6.36 TX producer/token/DMA/SKB audit and found a concrete
  cross-device DMA cleanup bug. Payloads on NPU queues are mapped through the
  Airoha NPU platform device and record that device in the TXWI cache. The
  special MAC-TXP path used for AddBA frames nevertheless unmapped through the
  PCI device, unlike the normal firmware-TXP path.
- Added one-line functional patch SHA256
  `7b5a404a2d7823b8a439af01a0d93cde1a86f5dcfe60947afea2db2493f33c5e`
  to use `mt76_txwi_payload_dma_dev(mdev, t)`. All ordinary TXFREE, NPU
  consumer, and token-sweep paths converge on the corrected cleanup.
- Added executable verifier SHA256
  `983f85269de1bf1ec7c0d129fc70829b2287cf36c8bc0c7559ee1e4f678875fb`.
  Source, ownership model, compiled AArch64, and Ghidra checks report
  `PASS_V637_DMA_DEVICE_PAIRING checks=48`. Strict checkpatch has zero
  findings and clean mt76 compile passes.
- Full Ghidra 12.1.2 analyses completed for exact rebuilt mt76 and mt7996e.
  The final mt7996e input SHA256 is
  `93d0eaf81d3bb5f1a42699382a180561316c16637b3f8a16565ae6c42da654db`.
  Decompile shows the recorded pointer load from `t + 0x18`, default fallback
  from `dev + 0x858`, then DMA unmap through the selected pointer.
- Pinned NPU-enabled full build passed. Accepted image is
  `work\w1700k-dma-pairing-v6.37-20260805-sysupgrade.itb`, SHA256
  `760b203ef1fdc9921a2d75670da3a298df38b014d137710b12f679f5ef3b1ff0`.
  It is 20,615,996 bytes with 81,092 bytes FIT headroom.
- Exact verifier SHA256
  `1617d2f8a210cbb6244504eec89e13f66ab1e503f2ed142edcb7e166d76b58dd`
  reports `PASS_V637_CANDIDATE`. Kernel and DTB match V6.36 byte-for-byte;
  rootfs shape and package contracts are unchanged. The only functional
  rootfs delta is mt7996e; APK metadata containers change but their semantic
  package/script content remains equivalent.
- Frozen bundle is
  `work\candidate-bundles\W1700K-V6.37-DMA-Pairing-20260805-OFFLINE`, with
  28 payload files and 28,739,417 bytes. Payload-list and bundle-manifest
  SHA256 values are
  `494458ab7891d11becf58f75241625b3638e596b6e76b8adb206d6bcac902dde`
  and
  `6c030b920b76b197ad427529f0472f06c97acc15416fd1551930dee805d19075`;
  replay passes. FinalResult mirror is marked `UNFLASHED`.
- Rechecked access after the reported reboot. COM3 enumerates and opens but
  returned zero bytes during an eight-second 115200 8N1 Enter probe with
  DTR/RTS disabled. Ethernet has 1 Gbps carrier, host address
  `169.254.66.29/16`, and no DHCP/ARP peer. No router write or validation ran;
  V6.37 remains unflashed and V6.15 remains the accepted live baseline.
- The finding narrows the open TX-lifetime boundary but does not close full
  hostadpt parity. Dedicated rings, SKB/bufid ownership, scatter recycle,
  doorbells, TXFREE/token teardown under load, RRO, and final packet fate
  remain for the next static/live phases.

## 2026-08-05 Addendum - V6.38 NPU Descriptor DMA Ordering

- Audited the coherent NPU TX descriptor owner handoff. Replaced CPU-only
  `smp_wmb()` with `dma_wmb()` before DONE, added `dma_rmb()` before returned
  descriptor reads, and guarded CTRL/ADDR/recycle accesses with
  `READ_ONCE()`/`WRITE_ONCE()`. Patch SHA256 is
  `03770cb972d0c8077f8e4243c0ca65635134b162537d7bf01b2c6f8e7bf2b2d3`.
- Executable source/model/AArch64/Ghidra verifier SHA256
  `6f993374833dacc68fccf67d57dc2a9e2a6412c691d19e788c2482a523e2582a`
  reports `PASS_V638_NPU_DESCRIPTOR_ORDERING checks=28`. The old model admits
  seven stale producer states and three stale completion states; the corrected
  DMA ordering admits zero.
- Exact full Ghidra inputs survived the final build byte-for-byte. mt76 SHA256
  is `93179da797fc8a02f907636e2c9ff4207ca110a499e8697bc99d089156df0b86`.
  Disassembly proves `dmb oshst` before owner publication and `dmb oshld`
  before completion reads; Ghidra independently shows
  `DataMemoryBarrier(0,2)` and `DataMemoryBarrier(0,1)` in those positions.
- Pinned NPU-enabled full build passed. Accepted offline image is
  `work\w1700k-npu-desc-ordering-v6.38-20260805-sysupgrade.itb`, SHA256
  `066b6e017fc103cea4428f6f127a6468055d979bc8842f46d4ba17364b4c4a19`.
  It is 20,615,996 bytes with 81,092 bytes FIT headroom.
- Exact verifier SHA256
  `ff2fe6a872578282297858e133d188b5d7c37b808d743e72b1c54cc56e0c3194`
  reports `PASS_V638_CANDIDATE`. Kernel and DTB match V6.37 byte-for-byte;
  rootfs shape and package contracts are unchanged. The only functional
  rootfs delta is mt76 plus equivalent APK bookkeeping.
- Frozen bundle is
  `work\candidate-bundles\W1700K-V6.38-NPU-Desc-Ordering-20260805-OFFLINE`,
  with 30 payload files and 28,756,562 payload bytes. Payload-list and
  bundle-manifest SHA256 values are
  `639ec7a6376a3f88075310a2e331a24a4d2495f49fb6c26e32f8ab18c77373c5`
  and
  `57e41f27f12be1a6e9691fa0892c053bc13727e8ab7c8af349dd5f58d271426e`;
  replay passes. FinalResult is marked `UNFLASHED`.
- The latest live retry still produced zero COM3 bytes at 115200 8N1;
  Ethernet has carrier but no W1700K peer. No router write occurred. V6.15
  remains the prior accepted live baseline, and the unresolved stock-parity
  boundary remains dedicated ring/SKB/scatter/doorbell/TXFREE/RRO ownership
  plus final packet fate under load.

## 2026-08-05 Addendum - Source Invariant Contract Reconciliation

- Retried the post-reboot live gate. COM3 is a healthy PL2303GC binding and
  opens at 115200 8N1, but a twelve-second periodic-Enter probe received zero
  bytes. Ethernet remains at 1 Gbps with host link-local
  `169.254.66.29/16`; DHCP, ARP, IPv6, and management probes found no W1700K
  peer. WiFi `192.168.1.1` is unrelated and was left untouched.
- Corrected a stale invariant/helper claim. Active mt76 patches have no
  packet-owning FastTX controls, but Airoha patches 999-67/999-68 compile
  optional `stock_wifi_fasttx_consume` and `stock_wifi_fasttx_direct` paths.
  Both default to false and the NPU mode helper neither exposes nor enables
  them.
- Updated helper status JSON to report that distinction, and expanded the
  source checker to enforce it. Checker SHA256 is
  `bf3727d0e20e4d2b63d64d48688a28220665d278e7aeb4c642904900cf5e09d7`.
  Exact result SHA256 is
  `428d3357ec1d52b2764e9691bb8b1a29f8201b422c4aede8b73730b1beab6a46`
  and reports 44 passed, 0 failed at source commit
  `5575e4a97f119f682223a090c4a78c0913f906f5`.
- No firmware behavior was promoted and no image was rebuilt. V6.38 remains
  byte-identical and unflashed. Work continues on the executable ownership
  model; a V6.39 change will be made only if that model exposes a concrete
  lifecycle defect.

## 2026-08-05 Addendum - V6.39 FW-TXP Token Ownership

- The executable ownership model exposed a concrete ABA defect. The RV32
  trampoline writes offset `0x32`, which is FW-TXP `token` but MAC-TXP
  `msdu_id[1]`; MAC-TXP `msdu_id[0]` at `0x30` remains the live high token.
  Early cleanup plus token reuse plus a late old TXFREE can release a new
  packet. Three current-policy witnesses reproduce; the hardened policy has
  zero witnesses across 3,215,756 checks and 470,592 sequences.
- Implemented patch
  `9999zzzzzzzg-mt76-harden-npu-stock-copy-txp-token.patch`, SHA256
  `aa49a56d1d24742101325f7192bff7bc0ed5526bea813f27d17d8ce5eea813ee`.
  Stock-copy early completion now requires a genuine FW-TXP, original token
  equality, existing copy/remap status gates, and a rewritten low local token.
  MAC-TXP and invalid FW-TXP remain on ordinary high-token completion.
- Source invariants pass 48/48; strict checkpatch is clean. Exact source,
  model, AArch64, and Ghidra verifier output is
  `PASS_V639_NPU_TXP_TOKEN_OWNERSHIP checks=35`. Full Ghidra exits are zero on
  byte-identical final mt76 and mt7996e build modules.
- Pinned full build passed. Accepted offline image:
  `work\w1700k-npu-txp-token-v6.39-20260805-sysupgrade.itb`, SHA256
  `3a51268ec7341d45441c53c60ed5e2789a5bfd1fc552ed71223a5545ef4ddb8c`,
  20,615,996 bytes, with 81,092 bytes FIT headroom.
- `PASS_V639_CANDIDATE` proves byte-identical kernel/DTB, unchanged 1,146-path
  rootfs shape and package contracts, expected linked mt76/helper delta,
  required NPU firmware and packages, selected APK signatures, and forbidden
  stock-binary absence.
- Frozen bundle:
  `work\candidate-bundles\W1700K-V6.39-NPU-TXP-Token-20260805-OFFLINE`,
  41 payload files and 28,560,489 bytes. Payload-list and bundle-manifest
  SHA256 values are
  `ca93ca98fda592ec05119c08b9d840430da306bce72273fdaf41d6ad6f700c2e`
  and
  `68c01088e0bae31a56a6e0d7c369adc89dc17afa4d311d1f14f2c611f7e4b76d`.
  Workspace and FinalResult checksum replays pass; FinalResult is explicitly
  marked `UNFLASHED`.
- Live access still did not advance after the reported reboot. COM3 opens as
  the PL2303GC at 115200 8N1 but received zero bytes over 15 seconds of Enter
  probes. Ethernet negotiated 1 Gbps yet exposed no DHCP, ARP, IPv6,
  management peer, or packet activity. WiFi `192.168.1.1` is unrelated and
  was untouched.
- No router command or persistent write occurred. V6.39 remains unflashed and
  V6.15 remains the prior accepted live baseline. Next live work starts with
  verified identity/recovery, mode-0 synthetic validation, and only then
  guarded mode-3 FW-TXP/MAC-TXP testing.

## 2026-08-05 Addendum - COM3 Recovery Reached, Cold-Cycle Boundary

- COM3 is no longer an unverified path. It returned vendor `ECNT>` and
  read-only U-Boot/AN7581/DRAM/Ethernet identity. The vendor chainloader then
  reached modern U-Boot without an environment write.
- The pinned recovery FIT transferred exactly, passed modern U-Boot FIT hash
  checks, and booted from RAM. Serial proved board `gemtek,w1700k-ubi`, the
  expected MTD boundaries, successful UBI attachment, and NPU firmware 0.1111.
- Three live-only harness defects were exposed before any persistent gate and
  fixed: UART command truncation, PowerShell terminating on expected SSH probe
  failure, and stale Linux-prompt acceptance during reboot. Recovery addressing
  is now source-bound to the isolated Ethernet adapter, and adapter preflight
  tolerates switch-reset link flaps. Current harness SHA256 is
  `75a4a331b4c4b8f16402272296911d194523aa8c6add3eb037b49f568859edc6`.
- The final retry reached vendor U-Boot initialization but stopped emitting
  serial after `usxgmii_pcs_int en 1`, before a shell prompt. The harness and
  its TFTP child were stopped and COM3 released; a physical cold power cycle
  is the remaining prerequisite.
- No backup, candidate transfer, compatibility test, sysupgrade, NAND/UBI,
  environment, bootloader, factory, calibration, or runtime WiFi write took
  place. V6.39 remains unflashed; V6.15 remains the prior live baseline.

## 2026-08-05 Addendum - V6.40 PPE RCU Snapshot

- Ran a clean sparse audit against the V6.39 canonical mt76 build. Sparse
  found the `__rcu ppe_dev` callback argument violation; AArch64 confirmed the
  callback loaded that pointer twice. The baseline sparse log SHA256 is
  `6df1a19b6058b41e4175db9c9596a77c9de37614da739bcd63c3408a46831101`.
- Added `9999zzzzzzzh-mt76-fix-ppe-rcu-access.patch`, SHA256
  `62a51019903d22ac7fb2f82d6cc2520809690ab85a879dd3c9bfe19f9630519a`.
  It keeps the MMIO gate and uses one `rcu_access_pointer()` snapshot under
  the existing flow-callback teardown contract. Strict checkpatch and exact
  upstream apply-check pass.
- Final sparse has no C source diagnostics; source invariants pass 51/51.
  Focused source/AArch64/Ghidra verifier output is
  `PASS_V640_PPE_RCU checks=72`. Exact unstripped mt76 SHA256 is
  `e61520a0a2637236f7d119a96fd8fd36862835171648481cde733e3c5fbd8897`;
  mt7996e is unchanged from V6.39.
- Clean full build and every inherited V6.36-V6.39 NPU gate pass. Accepted
  offline image is
  `work\w1700k-npu-ppe-rcu-v6.40-20260805-sysupgrade.itb`, 20,615,996 bytes,
  SHA256
  `29a9ac8c2e3e488146c719c1c53c5fdb9ba1c9a88a70b39dbf469b0c067a441c`.
- `PASS_V640_CANDIDATE` proves byte-identical kernel/DTB, unchanged 1,146-file
  rootfs shape/package contracts, exact mt76-only functional delta, APK
  signatures, required firmware/packages, and forbidden-stock-binary absence.
  Verification JSON SHA256 is
  `18913d175f143da6cf7a0fd63a29b23992e1223be3111a922bd21b2218bebebd`.
- Frozen bundle:
  `work\candidate-bundles\W1700K-V6.40-PPE-RCU-20260805-OFFLINE`, 53 payload
  files and 31,219,233 bytes. Payload-list and bundle-manifest SHA256 values
  are
  `c186c7cd19ca8319890b24cf32ee4284797aa5b51ae7c54649ca2b72b9a0451c`
  and
  `70929e86aa489c5f67ed6fcac5a64bc8a5b1b36290ffef79e45691269e980a9f`.
  Workspace and FinalResult checksum replay pass; the mirror is explicitly
  marked `UNFLASHED`.
- Pinned V6.40 recovery harness SHA256 is
  `a83fd6310c694ec645edf1c8cf3b4a1dc9820e4dff4909079be11f3b3dcbb233`.
  Exact preflight passes over the existing APIPA Ethernet `/16` without
  changing the WiFi route.
- Live state did not advance: COM3 enumerates but returned zero RX bytes after
  interrupt/Enter and serial reboot/catcher probes. Ethernet has 1 Gbps carrier
  and the known W1700K MAC; IPv6 link-local probing found no management peer.
  No persistent router write occurred. V6.40 is unflashed and V6.15 remains
  the prior live baseline.

## 2026-08-05 Addendum - V6.41 Airoha Ownership Hardening

- Audited the built-in Airoha NPU/Ethernet ownership paths and added four
  focused patches for watchdog-work lifetime, TX DMA unwind ownership, L2
  subflow allocation ownership, and exact mapped-entry tracking. Strict
  checkpatch is clean. Focused source/generated-code gates report
  `PASS_V641_AIROHA_OWNERSHIP checks=21` and
  `PASS_V641_GENERATED_CODE checks=26`.
- Sparse and Clang `W=1` report zero Airoha diagnostics. Clang Static Analyzer
  produced zero Airoha source reports after filtering unrelated kernel/header
  analyzer noise.
- The first full build omitted `W1700K_EXPERIMENTAL_MT76_NPU=1` and is
  quarantined as rejected. The corrected NPU-enabled clean build exits 0;
  build-log SHA256 is
  `4bb83d9c71633b778881e3eb34ece18525ecac288ec22246086a54dbf45167a9`.
- At the user's request, Ghidra 12.1.2 completed full auto-analysis of the
  exact 77,581,656-byte vmlinux plus mt76 and mt7996e. It decompiled all
  294, 74, and 58 selected functions, respectively, without a selected
  decompile failure. Report SHA256 values are
  `c9688cc4673b6c1d0208743f18718a09c9d0432c43effcb08052d97b6b2f63df`,
  `1985601173c7c91307d4937ca489d3a0475f34c7a5056928ba31c1273094ba52`,
  and `0cbad2b6fd68891882706ca5a38203b5d8800a93a8964513fe2f4743cb5e882d`.
- Accepted offline image is
  `work\w1700k-airoha-ownership-v6.41-20260805-sysupgrade.itb`, 20,615,996
  bytes, SHA256
  `41d6c207dfe46dd3b103de0361b4665564547278fa7eca9e731e7f9284add05c`.
  `PASS_V641_CANDIDATE` covers inherited V6.40 gates, FIT/fwtool metadata,
  package contracts, APK signatures, NPU firmware, and stock-binary absence.
- Frozen bundle is
  `work\candidate-bundles\W1700K-V6.41-Airoha-Ownership-20260805-OFFLINE`,
  with 82 payload files and 111,831,984 payload bytes. Payload-list and
  bundle-manifest SHA256 values are
  `339191b3c63c458828799d0c3d27148c7df948d3906255eecc708a8a09f8172b`
  and
  `5d0ddf9766bb976da19d76fa1dd6fe38e8ed282f79cce6f54e14bb0f7807211c`.
  Workspace and FinalResult checksum replays pass; FinalResult is explicitly
  `Experimental\AirohaOwnershipV641-20260805-UNFLASHED`.
- The V6.41 recovery harness passes exact artifact preflight and preserves the
  Windows WiFi route. COM3 still received zero characters during a 20-second
  115200 8N1 prompt probe, so the live identity gate did not open and the
  harness was not launched past preflight.
- No flash, backup, candidate transfer, sysupgrade, U-Boot command, NAND/UBI,
  environment, bootloader, factory/calibration, or runtime WiFi write occurred.
  V6.41 remains unflashed and V6.15 remains the prior live baseline.
- Armed `v641-recovery-20260805-201005` before a requested cold power edge.
  It received zero serial bytes and never left the bootloader-prompt wait. The
  exact TFTP child was stopped after command-line verification, UDP/69 was
  clear, and COM3 release check passed. Status/cleanup SHA256 values are
  `7daad315e053bdc9318addde3008e76f3e9a2b829b8505ab27c46728827c95cd`
  and
  `6742048668b9aa91ba15bad87871aad1ce086ed6381c1834b7bfcdc714ddd91d`.
  No router command or persistent write stage was reached.
- Armed a later exact-harness catcher in
  `work\live-captures\v641-recovery-20260805-202900`. Exact V6.41 and host
  preflight passed; COM3 opened at 115200 8N1 and Ethernet remained up at
  1 Gbps. The session nevertheless received zero serial bytes, saw no
  bootloader prompt, and found no APIPA or IPv6 link-local management peer.
  Without a boot signature, a requested cold power edge is not independently
  proven by the capture.
- Terminated only the host wait, verified and stopped harness TFTP PID 9592,
  confirmed zero UDP/69 listeners, and reopened COM3. Status, result, and
  cleanup SHA256 values are
  `595d724f6cfe9e988335ead6bbd9cf5a47b9334ee744f36583acdc79be223ed6`,
  `46f71910640ad2ccc51664423d75496bc92af1550cda433721039e1d08c9a679`,
  and
  `8a159afb4fa905551623d270066c1e553c93b601f83e45ecb2d90365cdc59ffd`.
  No backup, image transfer, compatibility test, sysupgrade, or persistent
  router write occurred. V6.41 remains unflashed.

## 2026-08-05 Addendum - V6.42 Stock Hostadpt TX Headroom

- Exact stock-to-current register reconciliation proves two 1024-entry,
  `0xd0`-stride hostadpt TX rings. Group0 serves 2.4/5 GHz at
  `0x30d0a0/0xa4/0xa8/0xac`; group1 serves 6 GHz at
  `0x30d0b0/0xb4/0xb8/0xbc`. Stock admits only when full free distance is
  greater than five.
- Found and fixed a three-slot admission mismatch: V6.41 allowed 1022
  outstanding NPU descriptors versus stock's 1019. Also corrected the
  read-only stock free-distance verdict without changing generic DMA telemetry.
- Added mt76 and Airoha patches with SHA256 values
  `edeae4b5e84b81cd6db61a0b1a3fb1d856735a7b6ee992b2b0e056abfa8162b1`
  and
  `80bcfd22e35b785fced8b2a6e18391a07eeed5b72a5d70a5ddd48732679da968`.
  Strict checkpatch is clean; the executable ring model passes 1573 checks.
- Rejected preflash candidate
  `c02472cb3af07ada1c4aa83e534cd1e0e645d191402ce4e2465493cfa31384ea`
  because it omitted the reproducible NPU build flag. Corrected clean build
  records `W1700K_EXPERIMENTAL_MT76_NPU=1`, proves NPU objects/functions, and
  exits 0.
- Full Ghidra analysis exits 0 for the exact final vmlinux and accepted
  NPU-enabled mt76. Decompiled code proves stock free-distance handling,
  `free > 5`, actual NPU enqueue/cleanup functions, and NPU-only
  `queued + needed <= ndesc - 5` admission.
- Accepted offline image:
  `work\w1700k-hostadpt-tx-headroom-v6.42-20260805-sysupgrade.itb`, 20,615,996
  bytes, SHA256
  `8e695154559134701aed51c64b436f6e17b0a4b161c31db837f0879ede33482d`.
  `PASS_V642_CANDIDATE` covers FIT/fwtool identity, exact rootfs delta, package
  equivalence, APK signatures, NPU firmware, and forbidden-binary absence.
- Frozen bundle:
  `work\candidate-bundles\W1700K-V6.42-Hostadpt-TX-Headroom-20260805-OFFLINE`,
  35 payload files and 105,883,556 bytes. Payload and bundle manifest SHA256
  values are
  `b9cefc5dd0b995d112b9219cc4b32fe4d7339e2ed617cbe4451cf75765270c84`
  and
  `9a245ed0084d18e88712d8e4ccaa06f9915b6e866d3eb958b2da15ad684b04fa`.
  FinalResult checksum replay passes.
- COM3 opened at 115200 8N1 but the 180-second read-only boot capture received
  zero bytes. No flash or router write occurred. V6.42 remains offline only;
  V6.15 remains the prior accepted live baseline.
- Remaining boundaries: live stress, TXFREE ordering under load, ping-pong
  packet fate, RRO equivalence, exact stock callback/error paths, and final
  hardware parity.

## 2026-08-05 Addendum - V6.42 Live Recovery Precheck

- COM3 produced a fresh installed-image boot and the same fatal cfg80211
  notifier trace previously root-caused to the rejected NETPOLL/non-NETPOLL
  `struct net_device` ABI mismatch.
- The exact V6.42 image now has a fresh direct ABI-gate result:
  `PASS_NETDEV_ABI_IMAGE_GATE`, cfg80211/kernel offset 976,
  NETPOLL/NETCONSOLE disabled, deliberate NETPOLL offset 984. Verification
  JSON SHA256 is
  `62a85c6a124e988b8752c64ab39ab5ceb46e152ae417c986dc4bd6da154f103f`.
- Added and preflighted `work\w1700k-com3-recover-v642.ps1`, SHA256
  `3a3815086d564472a1c14a63370ce0de787c7298ce7ee904e3cffd63230cd41e`.
  The catcher was later stopped after receiving no post-arm cold-boot bytes;
  TFTP and COM3 were released cleanly.
- No router write or flash occurred. Report
  `work\W1700K_V642_LIVE_RECOVERY_PRECHECK_20260805.md` SHA256 is
  `ea5a724bc90c2f67d7bbd94587061488012dcd0f553b1e30c99b9d3920343552`.

## 2026-08-05 Addendum - V6.42 NPU TX Reclaim Liveness

- Closed the suspected reclaim-trigger gap without changing source. mt76
  cleans at queue occupancy 960, before ordinary scheduling stops at 992;
  TXFREE also cleans and reschedules the worker. One consumer advance recovers
  the only reachable stopped boundary on the next scheduler pass.
- The exhaustive model passes 534,734 checks. Model and frozen-output SHA256
  values are
  `392459338b6e8f332dc2aa5ed03f84cd6060b9cdb37255102919ba1f2d606936`
  and
  `4624044b97fcbe618ad61b7f8b08111a9df0d2dd387459f6563f1cbc2f6ac647`.
- V6.42 is unchanged. Report
  `work\W1700K_V642_NPU_TX_RECLAIM_LIVENESS_20260805.md` SHA256 is
  `63c3a605042253a3187a062b742e76461d0e1aeea422e818529f8fa9db35dec0`.

## 2026-08-05 Addendum - V6.42 COM3 Recovery Attempt 22:42

- The exact recovery harness passed preflight and opened COM3, but received no
  UART bytes during the post-arm window. Ethernet carrier stayed at 1 Gbps and
  the expected APIPA recovery peer did not answer.
- The exact TFTP child was stopped, UDP/69 was clear, and COM3 reopened. No
  router command or write occurred. V6.42 remains unflashed.
- Attempt report
  `work\W1700K_V642_COM3_RECOVERY_ATTEMPT_20260805_224223.md` SHA256 is
  `58904af230fae1a5646f86adddfcdf75ea80ecb21590bed0c8d1e1d888babb70`.

## 2026-08-05 Addendum - V6.43 NPU Default-Off Order Gate

- Measured the exact target ABI and separated memory accounting from the NPU
  TX regression. Diagnostic structures add about 36.2 KiB; known coherent NPU
  TX and RRO allocations are approximately 1.5 MiB and 9 MiB, respectively.
- Found shared diagnostic `order_lock` acquisition in token allocation,
  enqueue, release/TXFREE, and consumer reclaim while deep tracing was off.
  Added patch SHA256
  `20c0b1a2b55001a7153e01d078620cddcbc37273a3e57f9e7996505737e18339`.
  Quiet mode retains aggregate counters and bypasses detailed state/locking;
  opt-in deep tracing retains the prior ownership history.
- Corrected clean build pins the experimental NPU flag and exits 0. Focused
  source/model/generated-code verification reports
  `PASS_V643_NPU_ORDER_GATE`. Full Ghidra auto-analysis exits 0 for exact mt76
  and mt7996e and independently decompiles the expected runtime gates.
- Accepted offline image SHA256 is
  `a5516f47fa5984094c2405b7ac9cd986b373d19769020c47f2128c0464aa3351`.
  `PASS_V643_CANDIDATE` proves exact UBI FIT identity, signed packages, NPU
  objects/firmware, forbidden-binary absence, and byte-identical
  kernel/DTB/cfg80211 inheritance from V6.42. Verification JSON SHA256 is
  `24e2672b7186fc7c6346b8ca4c0c722de128b20d03a7bdc4a5cb19c551b7310b`.
- Report `work\W1700K_V643_NPU_ORDER_GATE_20260805.md` SHA256 is
  `87690316498e7ca5ee9866355584a45cd67aab63d70acf259b07290737c4fc45`.
- The exact V6.43 recovery harness passed preflight and is armed at
  `work\live-captures\v643-recovery-20260805-235617`. COM3 and 1 Gbps Ethernet
  carrier are present, but UART RX remains zero and no router management peer
  is visible. No router command or write has occurred; live validation remains
  pending and V6.15 remains the prior accepted live baseline.
- Frozen 15-file workspace bundle and FinalResult mirror are both named
  `W1700K-V6.43-NPU-Order-Gate-20260805-OFFLINE`. They contain 24,603,624
  bytes, replay all payload hashes with zero failures, and are byte-identical.
  SHA256 values for `SHA256SUMS.txt` and `FILE_MANIFEST.tsv` are
  `2604cfcc6c1bcfe8a0b3d0ab8c090237be1014ea058e594ffb6d49ed457323bd`
  and
  `3f2f32f6aa427ddb1639ea40baa1a3802dc74a4f65be10bf7b9115fa57f2fd04`.

## 2026-08-06 Addendum - V6.43 COM3 Recovery Attempt Closed

- The exact V6.43 catcher passed preflight and opened COM3, but received zero
  UART bytes. Ethernet remained continuously connected at 1 Gbps during a
  separate 60-second transition watch, so no cold-power edge was observed.
- Closed only the host wait. Exact TFTP PID 15572 was command-line verified
  and stopped; UDP/69 is clear and COM3 release passed. Result and cleanup
  SHA256 values are
  `c2d3e1c8e6adacaf9eb6ef88fffbac204f02868231831f71d3145bd941ac02a6`
  and
  `219ce1d696270722d1ed3df9997664e2ccb0122e86534af997df49abb47785c1`.
- No router command or write occurred. Attempt report SHA256 is
  `0eb99ae3da06f3af348bfc106bd98da6efdbeba7a51b21856a6a655e97fd542c`.
  V6.43 remains unflashed and V6.15 remains the prior accepted live baseline.

## 2026-08-06 Addendum - V6.44 Default-Off Packet Telemetry

- Audited the V6.43 generated packet paths and found diagnostic `atomic64`
  operations still compiling to exclusive-store retry loops in routine NPU,
  token, hostadpt-shadow, MLO, TXFREE, and cleanup paths.
- Added a default-false exported static key and
  `w1700k_packet_telemetry` parameter. Deep trace shares the effective key;
  error and abnormal-condition counters remain ungated. Patch SHA256 is
  `ec1b45845b3fe03ce3760e30329a9385a5242fbfbc292e829d7b03b19499cf8e`.
- Updated the NPU helper, LuCI page, and fixture. Default-off status is
  `telemetry-off`; hardware core/IRQ/ring/MIB monitoring is unaffected. The
  fixture proves explicit on/off and deep-trace-implied behavior.
- `PASS_V644_PACKET_TELEMETRY_GATE` records nine mt76 and seven mt7996
  jump-table entries and proves default-path exclusive-store reductions. The
  cached mt7996 TX-prepare site is `0x15df8 -> 0x160d4`.
- Clean full build exits 0. Full Ghidra 12.1.2 analysis exits 0 for exact final
  mt76 and mt7996e; report SHA256 values are
  `1aae75980b70a7689221e4e6cc35b1917ef159966f86c686a2fd49e2ee1d6eba`
  and
  `3669cdb8b5b9a5b4d3b84401ca838112174afcd9ef4f07a2652f3d029cb85c23`.
- Accepted offline image SHA256 is
  `6fd3c540938212856cca9abeb523041739ffbb942befd901806798e1eed4f1c8`.
  `PASS_V644_CANDIDATE` covers FIT/fwtool identity, exact rootfs delta,
  unchanged kernel/DTB/cfg80211, package equivalence, APK signatures, NPU
  firmware, and forbidden-stock-binary absence.
- Report SHA256 is
  `aa363c7bb076767e0af03af6c6d79f44f64836926f3503f0c88f04f8e931a334`.
  Frozen workspace and FinalResult bundles named
  `W1700K-V6.44-Packet-Telemetry-20260806-OFFLINE` replay all payload hashes
  and are byte-identical.
- The V6.44 recovery harness passes exact preflight, but COM3 still provides
  zero RX bytes and no Ethernet peer answers. No router command, backup,
  transfer, compatibility test, sysupgrade, or persistent write occurred.
  V6.44 remains unflashed; V6.15 remains the accepted live baseline.

## 2026-08-06 Addendum - Stock Ping-Pong Current-Source Replay

- Replayed the July 18 stock production-fate verifier against current source
  commit `5575e4a97f119f682223a090c4a78c0913f906f5`.
  `PASS_STOCK_PINGPONG_PRODUCTION_FATE` remains valid with 62 passes and zero
  failures.
- No post-token ping-pong patch is active; all 19 retired variants remain
  quarantined. Stock left-to-right mode and speedtest hooks remain synthetic
  test facilities with no demonstrated production enable path.
- Static production ping-pong control flow and terminal ownership are closed.
  The open boundaries are live FastTX/QDMA load validation, exact vendor
  callbacks/error paths, TXFREE/RRO concurrency, dead-WM recovery, and final
  WiFi/NPU performance.
- Replay transcript SHA256 is
  `cbd6bdde53e19ba78605b033a317ec1d443b7c067400fbf64e128294823ab16f`.
  No source, image, or router state changed.

## 2026-08-06 Addendum - V6.45 NPU Token Release-Last

- Stock Ghidra output and exact V6.44 generated code exposed a real ownership
  mismatch: stock retains the TX token until DMA unmap, SKB consumption, and
  callback completion; V6.44 removed its IDR entry before those operations.
- Added claim/finalize ownership with an owner byte in existing TXWI padding.
  Cleanup remains outside `token_lock`, while IDR ownership stays live until
  validated finalization. Mismatch fails closed and quarantines the TXWI;
  generic non-NPU release remains unchanged. Patch SHA256 is
  `77eb9f89ab3326d5f1aaf176ec413609a7c6ff2eaf766708aba9e2545eda1e0e`.
- The model passes 19 checks. Clean NPU-enabled package/full builds pass and
  link `npu.o`. Full Ghidra analysis exits 0 for exact final mt76/mt7996e,
  recovering 452/622 functions and confirming release-last instruction order.
- Accepted offline image SHA256 is
  `e12e04ab4231a29bf0f430dfbc9dfe66d6404eebbc0bbc986c7e8676cc935e23`.
  `PASS_V645_CANDIDATE` pins the exact source/build/Ghidra/FIT/rootfs evidence;
  verification JSON SHA256 is
  `987e53c25b4e0893c75e410a23e84c3546fc2c04cc570cea37ccf55ab870a736`.
- Report SHA256 is
  `131fcdee61f005d8b725037f3c81c8c94cc328405e703ebc9927ab1b8e4d9fc7`.
  Frozen 25-file workspace and FinalResult bundles named
  `W1700K-V6.45-NPU-Token-Release-Last-20260806-OFFLINE` replay 24 hashes and
  are byte-identical. `SHA256SUMS.txt` SHA256 is
  `e95453ff2963d287500bb122be58a7df627220ed6f4fe36b61bbd0d4643d6a26`.
- The exact V6.45 recovery harness passes preflight and is armed at
  `work\live-captures\v645-recovery-20260806-024257`. COM3 and isolated TFTP
  are ready, but UART RX is still zero. No router identity, command, backup,
  transfer, compatibility test, sysupgrade, or persistent write has occurred.
  V6.45 remains unflashed; V6.15 remains the prior live baseline.

## 2026-08-06 Addendum - Exact Stock TXFREE Callback Target

- Recomputed the registered callback slot from ELF evidence instead of the
  earlier relative-table assumption. `.data+0x110 + 8 + 0x58` selects
  `.data+0x170`, whose `R_AARCH64_ABS64` relocation targets `.text+0xe74`,
  Ghidra `0x00100e94`. The discarded `0x001010d4` target is
  `connac_if_tx_queue`.
- Fresh Ghidra decompilation proves that the callback extracts band 0-2,
  checks the registered PHY and active-token count `<10`, then invokes
  `mtk_mac_dequeue_by_token()`. The provider takes its per-band BH lock,
  checks queued work, calls the vendor dequeue op, and unlocks.
- `tools\verify_w1700k_stock_txfree_callback.py` reports
  `PASS_STOCK_TXFREE_CALLBACK_PARITY_V645`, 48 passes and zero failures.
  Verifier and JSON SHA256 values are
  `582aefe441762f361941f13dd3bf95a86ca7c4ce5f82f5609a880c0fe207e4e5`
  and
  `a5c1d70d3d246102f6913db22e353bf12532542f84e8e5d401187f6f1380de23`.
- V6.45 already provides functional queue progress after release-last
  finalization through the normal all-PHY mt76 TX worker. The exact stock
  synchronous `<10` policy remains an explicit live-test boundary, not an
  assumed missing port. No source or candidate image changed.
- Report SHA256 is
  `459be008aa048725ef4b986d0eba34216712b8d8160e1a99d0229c3b8c9974ad`.
- The 12-file evidence set replays cleanly. `SHA256SUMS.txt` and
  `FILE_MANIFEST.tsv` SHA256 values are
  `ff9da3647a31ca14424abb56de11b7934d2ecaa273a84d2cad0fd6727b39da22`
  and
  `f63bc12cf90308641108d6926d76e73b4ff919d0756f195edb290301948af187`.
- COM3 is no longer silent: 4,388 bytes identify the expected W1700K boot.
  It stops before any prompt at `usxgmii_pcs_int en 1`, and the Ethernet link
  is down. The harness remains armed. No router command or persistent write
  occurred; V6.45 remains unflashed.

## 2026-08-06 Addendum - V6.46 RRO Session Teardown and Firmware ABI

- Added the current-firmware equivalent of stock synchronous RRO session
  invalidation: interface-3 inode TX/RX operations use a six-second timeout,
  mt7996 reports failure before MCU reset, and teardown remains fail-open.
- Proved that numeric command identity differs across firmware generations.
  Stock inode TX/RX is `0x17`; current `0x17` is TX packet-buffer setup and
  current inode TX/RX is `0x18`. Changing the current enum to the stock value
  would be an off-by-one ABI defect, not a parity fix.
- Deterministic ABI verification passes 45 checks; integrated stock semantic
  RRO verification passes 107 checks. Full Ghidra analysis completes for the
  exact kernel and both WiFi modules with 36,849/452/619 recovered functions.
- V6.46 image SHA256 is
  `28d3ef4f3405731e4fae4506aa9e0731a273111e7673abeb6ae38cdc250307bc`.
  `PASS_V646_OFFLINE_CANDIDATE` verification JSON SHA256 is
  `748ba83e70152c6ccc7140f9c37ffc5f62dd78e8ebd35167721f66900f7b5ec5`.
- Report SHA256 is
  `0dabd6694f1b97ee9c54ea3cdd2720192728240464b84accae0cf21b94bafd59`.
  The 44-file frozen workspace bundle and FinalResult mirror replay all 43
  payload/manifest hashes and are byte-identical. `SHA256SUMS.txt` SHA256 is
  `6dec3adb6ca913bc944950e24fbfb79d4c4fdc725890765c1c4d47f20f702972`.
- A fresh exact-V6.45 recovery harness is armed on COM3, but has received zero
  bytes since opening and Ethernet has no carrier. No live state changed;
  V6.46 and V6.45 remain unflashed and V6.15 remains the prior live baseline.

## 2026-08-06 Addendum - V6.47 Source Audit Cleanup and Recovery Gate

- Final-source patch audit counted 6,386 files: 5,893 upstream, 170
  active/local, and 323 disabled experimental. The only 111 findings are in
  inherited upstream patches. Audit JSON SHA256 is
  `35089ac6eea770b996ed7bde634d0eab8f0317eaf7450577b496cd0831dc72a1`.
- Removed two retired mt7996 MLO counters and corrected the diagnostic scope;
  cleanup patch SHA256 is
  `cc3fbe9c648784fd9d5cc001087922599d0d5dd3b8dcc5c9d4624a75e6056fc8`.
  Corrected two NPU-helper shell status assignments. No power, regulatory,
  firmware ABI, NAND layout, or packet-ownership policy changed.
- Exact candidate SHA256 is
  `114395c77e958c74d21b34e4b22649d96715e540b6c8c3075ee3c575bc69f668`.
  Kernel/DTB equal V6.46. Rootfs changes are exactly APK installed/scripts,
  `mt7996e.ko`, and the helper; package contracts and script contents match.
- All current source/model/binary gates pass. The V6.38 verifier now consumes
  Ghidra semantics rather than unstable autogenerated local names. Exact V6.47
  mt7996 full analysis exits 0 with 618 functions/5,195 symbols; report SHA256
  is `67ad0a56d90a1c0493aa57d64e395fcfd68e0e3caca8746d42206f142cc558e2`.
- `PASS_V647_OFFLINE_CANDIDATE` result SHA256 is
  `601454c80ed2fd9a6d5d498493f7dda8f9302a5c76a89ba21985c9472e503760`.
- Frozen FinalResult contains 15 payload files and 24,129,037 payload bytes.
  Checksum replay has zero failures; SHA256SUMS/manifest hashes are
  `8219d2d7a1f2585f5d486be3bea189f88af6120f211896e8a49e9589e699652b`
  and `1c2aedc7fddc696e0eb8ca3650ac25cc75dc048933be44a1406e42b9c552f79c`.
- The stale V6.45 live process was stopped before exact V6.47 harness SHA256
  `b2db44199ac1477a786d4a04ac456148fca58b2e7e7637de86c71e395611049e`
  was armed at `v647-recovery-20260806-065923`. COM3 is open but UART RX is
  zero bytes; Ethernet reports disconnected. No router command or persistent
  write occurred. V6.47 remains unflashed.


## V6.48 mt7996 PCIe AER Recovery and Guarded Flash - 2026-08-06

- Root-caused the recurring WiFi/LuCI lockup to a PCIe completion timeout
  followed by Linux AER permanently disconnecting mt7996 because neither the
  primary nor HIF2 PCI driver registered an `error_detected` callback. The
  stock kernel avoids this path because `CONFIG_PCIEPORTBUS` is disabled,
  while the OpenWrt kernel enables `CONFIG_PCIEPORTBUS=y` and
  `CONFIG_PCIEAER=y`.
- Added `9999zzzzzzzzo-mt7996-handle-nonfatal-pcie-aer.patch`, SHA256
  `8f5dc98cba54e4fc10e08cd733a73ea4948e95a3e1215e4c07b064b964793e36`.
  Normal-channel notifications return `PCI_ERS_RESULT_RECOVERED` without
  MMIO so the existing mt7996 MCU-timeout/full-reset worker can run. Frozen or
  permanently failed channels remain fail-closed with
  `PCI_ERS_RESULT_DISCONNECT`. Strict checkpatch is clean.
- `tools\verify_w1700k_mt7996_pcie_aer.py` reports
  `PASS_MT7996_PCIE_AER_RECOVERY: 39 checks`. ABI and ELF proof places
  `pci_driver.err_handler` at byte 80 and resolves both driver objects to the
  same handler table. The callback calls only rate-limit/warn/error helpers.
- Rebuilt under WSL ext4 from source HEAD
  `5575e4a97f119f682223a090c4a78c0913f906f5` with a Linux-only PATH and
  `W1700K_EXPERIMENTAL_MT76_NPU=1`. Exact V6.48 image SHA256 is
  `f94ea464f35d7b0e2ad17245dd1f711305cf0c90342eebb0ee24ea5d9fa0c86e`;
  size is 20,620,092 bytes and FIT headroom is 76,996 bytes.
- Kernel and DTB are byte-identical to V6.47. Rootfs shape remains 1,146 files;
  only APK installed/scripts metadata and `mt7996e.ko` differ. Package
  contracts and maintainer-script contents are unchanged. Embedded
  `mt7996e.ko` SHA256 is
  `241e5921a3609e9b6ad84574e7fd74a6fc7c98cfd3f364938b8c88dc9069142f`.
- Full exact-module Ghidra 12.1.2 analysis exits 0 with 618 functions, 5,208
  symbols, and 38 selected decompiles. Report SHA256 is
  `d1dba8dd51319ad11a01a981c5976cb61c1e8fc84d8be8624065988a62a5ebd3`.
  The decompiler recovers normal state -> 5 and other states -> 4 with no
  hidden device access.
- `tools\verify_w1700k_v648_candidate.py` SHA256
  `5d81ece8374d234f6f718825e52829e5729dadc4d72b429055d138b1aaab254d`
  reports `PASS_V648_OFFLINE_CANDIDATE`. Result SHA256 is
  `b9f9be2411420217a7ec559ff488bd958ee557aac322931a2b349522ffd0cd51`.
  It replays V634/V635/V636/V637(48)/V638(28)/V641(21), mailbox ABI (45),
  stock RRO semantics (107), FIT/rootfs delta, signed APK, required package,
  and forbidden proprietary-binary gates.
- Frozen workspace and FinalResult bundle
  `W1700K-V6.48-MT7996-PCIE-AER-Recovery-20260806-OFFLINE` contains 17
  payload files and 20,891,936 payload bytes. Checksum replay and mirror
  comparison pass. `SHA256SUMS.txt` and `FILE_MANIFEST.txt` SHA256 values
  are `6f576f8eeb83aa481052ec447cb2743f730da9462df445be66ebb99fe19896e4`
  and `880cade5fb7c326fd79943a23da7a11d236e607f55e92d4376a41e323ee1535e`.
- Exact V6.48 guarded harness
  `work\w1700k-com3-recover-v648.ps1`, SHA256
  `47bfcf922f5b73fd72d726f48b3c3ed38caaa0d85349281580d68309fddb1a0e`,
  passes preflight and is armed as PID 17516 at
  `work\live-captures\v648-recovery-20260806-075618`. COM3 is open at
  115200 8N1, but UART RX remains zero bytes and Ethernet has no carrier.
  No target identity, router command, TFTP service, backup, transfer,
  sysupgrade, NAND/UBI write, bootloader/environment/factory/calibration
  access, or persistent state change occurred. V6.48 remains unflashed;
  V6.15 remains the prior accepted live baseline.

## V6.48 Hostadpt Error-Policy Reconciliation - 2026-08-06

- Pinned the 872,781-byte stock full Ghidra report and the exact current mt76
  Ghidra report. Current V6.48 prepared `mt76.ko` is byte-identical to the
  V6.46 analyzed input, SHA256
  `c783f85d54df8905b8ea74271a69bbdee66b0d77aa865dc7fb526d9b4f3f03f8`.
- Added verifier SHA256
  `befcf47b349805e166b7fa0f7e73ade7081a9f85a8d21de5118456a8ae603795`.
  Result is `PASS_STOCK_HOSTADPT_ERROR_POLICY`, 41/41; JSON SHA256 is
  `123852628be603f6d15c8310b10c255a10859c2141d20401e7ee8c962f6dec5a`.
- Closed exact vendor TX error-policy analysis without source mutation. The
  current native DMA/mac80211 ownership is safer than stock's nullable-device
  leak, missing-unmap callback branch, raw rejection frees, and global
  direct-unmap fallback.
- Reconciliation report SHA256 is
  `1241d1c2fc65d84c2300eb2f7b45a094350e1555986f548b47eb53655be41b52`;
  completion-matrix SHA256 is
  `378b1c899813e14ca5b11b3727991759a260cc35a0e90be297dbf93adbd18512`.
- Live catcher transition: stopped PID 17516; a direct four-Enter COM3 probe
  returned zero bytes; armed fresh exact V6.48 PID 15932 at
  `v648-recovery-20260806-080658`. COM3 is healthy/open, UART RX is zero, and
  Ethernet is disconnected. No router command or persistent/protected-state
  access occurred.

## V6.48 NPU Topology And Sparse Audit - 2026-08-06

- Added a single-instance lock to the exact mt76 Sparse harness after two
  host launches briefly overlapped in the ancillary `mt76-test` build. The
  uncontaminated rerun passed with 29 Sparse checks, zero diagnostics, build
  exit 0, and exact expected unstripped module hashes. Harness/summary/log
  SHA256 values are
  `34d56885f90095fce4bf12dce6f99ecee7114b75289af6eccf9841fb20d4edd2`,
  `d37bc52b38872b8f8e4931ceba7923671d14cd62a8f1c69c17635d9fc7112161`,
  and `b5e5ac0d108aa8c1a78bc9a9bc7be049cf96c085c86b13fa3c6d3309b1a7e2ff`.
- Added topology/alias/reset verifier SHA256
  `dd8d472ea8869c73509b06b1d01c84f35ea71b029027f6ab7ac6df021d3ca3c1`.
  Result is `PASS_V648_NPU_TOPOLOGY checks=38`; JSON SHA256 is
  `25e240c7696245f5f9b199b4c702d5db84c01830edaf842be79247a3e7454745`.
- Static proof confirms group-0 radio0/radio1 queue aliasing, separate HIF2
  group-1 ownership for radio2, fail-closed TXD owner lookup, serialized and
  idempotent alias cleanup, and callback/token/DMA quiescence before full
  ring reset. No source/image mutation was justified.
- Report SHA256 is
  `4e4094a7e644068aa27bfe5a2c424528c85b8c117a0edf932728566cd709d951`.
- Stopped stale catcher PID 15932 after the USB adapter reconnect and armed
  exact preflighted PID 20900 at `v648-recovery-20260806-082820`. UART RX is
  zero and Ethernet has no carrier. No router command or persistent/protected
  state change occurred; V6.48 remains unflashed.

## V6.49 Clang Static Audit And Hardening - 2026-08-06

- Installed and ran Clang 21.1.8 tooling over an exact 29-entry production
  mt76/mt7996 compilation database. The structured filter strips unsupported
  GCC-only flags, pins the AArch64 musl target, and excludes tools and
  generated module translation units.
- Fixed the confirmed optional DTS power-limit length initialization defect.
  Added fail-closed required-context guards and explicit HIF2 IRQ ownership;
  no regulatory, transmit-power, firmware ABI, NPU topology, NAND layout, or
  protected-data policy changed.
- Clean module build exits 0 with `mt76.ko`
  `f54b9300a63350bfde177d0ef8724012817edc134239cec86deca3111e7e1ecd`
  and `mt7996e.ko`
  `dd3f5e3aa3f111bec55a266542144772c2e45b7bd80450bcfdbee6d355a87c11`.
  Sparse checks 29 units with zero diagnostics.
- Clang analyzer exits 0 with zero failure files. Structured reconciliation
  proves baseline 27, candidate 17, removed expected 10, new 0, and exact
  residuals of 12 dead stores plus 5 inspected Linux list-model reports.
  Result is `PASS_W1700K_CLANG_V649_RECONCILIATION`.
- Full report SHA256 is
  `ac8a92856693597a9c77932f2246fae999e31d7f91eab4d12b04569322ade06b`.
  SARIF verifier SHA256 is
  `e7169f6c948b62d18917d8948cefb78d16d147abfbe3201ba1b08cfa4b3cbf11`.
- Stopped superseded V6.48 harness PID 15004 before source mutation. Capture
  `v648-recovery-20260806-085238` has zero UART RX and no Ethernet carrier.
  No target identity, command, TFTP, backup, transfer, sysupgrade, NAND/UBI,
  bootloader, environment, factory, or calibration action occurred.

## V6.49 Full Build, Ghidra, Freeze, And Live Catcher - 2026-08-06

- Built source HEAD `5575e4a97f119f682223a090c4a78c0913f906f5` successfully. Candidate
  `w1700k-clang-hardened-v6.49-20260806-sysupgrade.itb` is 20,620,092 bytes,
  SHA256
  `d40223cfb9b289510d0e002cf5f0ac85bd64a424063e7ba43766db5d32e3a0ac`,
  with 76,996 bytes FIT headroom. Kernel/DTB are unchanged from V6.48 and the
  only rootfs content changes are APK metadata plus the rebuilt mt76,
  mt76-connac, and mt7996 modules.
- Embedded module hashes are
  `8ce4613e720d62366325f2e0d715f4f020c0319fbe679ecbd7467eb863a7404b`,
  `78b114c931721ae6cf20a50473b83a82852ef54449423d692871d01f48dfb37c`,
  and `b4c5632aaadc5affcc8586469ef3f6f1248b4b8beba39029d2a437ed1e4519af`.
  Comprehensive Ghidra analysis exits 0 at 452/4,282, 180/1,603, and
  619/5,213 functions/symbols for the unstripped modules.
- Offline verifier result is `PASS_V649_OFFLINE_CANDIDATE`, SHA256
  `2c4ddf8398f8a480e2173b7630e87256514f30495d5ef42de56c6d6d2e322613`.
  Candidate report SHA256 is
  `962dac8cde982e47b730dc28d4e505d897336cb650e830f3e0b86d9ca3c4a3b6`.
- Froze and mirrored 36 payload files totaling 23,140,074 bytes under
  `W1700K-V6.49-Clang-Hardened-20260806-OFFLINE`. Checksum replay passes;
  `SHA256SUMS.txt` SHA256 is
  `58db67924b52655efbf0cec95512536d3f082fdb8574862855f9df82e2085b51`
  and `FILE_MANIFEST.txt` SHA256 is
  `8d75b66397f4bc9e5fa1edfb08f146f7f2b12270b407249f1462bb2a1c4d1de7`.
- V6.49 harness SHA256
  `c7f655d0445d5e8dfde70c64ae6c52f0d7b6be5b2d7533dcb6e1ee1b89f2a102`
  passed preflight and is armed as PID 11348 at
  `v649-recovery-20260806-102700`. COM3 is open at 115200 8N1, but it has
  received zero bytes and Ethernet is disconnected. No target action or
  persistent/protected-state change has occurred; V6.49 remains unflashed.

## V6.49 Unattended Live-Test Preparation - 2026-08-06

- Added exact LuCI `iwinfo.scan` calls to every hidden temporary radio/MLO
  case in the synthetic suite, with 60-second process watchdogs, JSON result
  checks, AP/MLD recovery checks, and post-marker kernel/firmware screening.
  Updated script SHA256 is
  `bad6ac444b4cf6ed20406e33dbc48f33474bebd23008aac230721e03f64bf30d`.
- Added explicit Ethernet source binding to the mode-0 and mode-3 runners;
  SHA256 values are
  `f3529b97a787647208ce9232192515c5fbdab67c054d3dde0d2d22b275d41f8c`
  and `66b0b78d9ab69b40ded1581e575daaed7b329bc989e6b66ba6c451ac71dbb172`.
- Added orchestration wrapper SHA256
  `b76e527e2c2951f5bdc94110b0261bdedfe3acb283ad9caa5c050dfc25323c6c`.
  Its exact preflight passes and PID 2096 is waiting in
  `v649-live-gate-20260806-104005` for the guarded COM3 recovery to complete.
  It will checksum-replay protected backups, establish an Ethernet-only host
  route after identity proof, test modes 0 and 3, run synthetic TX and PCI
  lifecycle checks, restore mode 0, and capture final memory/radio/NPU logs.
- No live test has started: serial RX remains zero and Ethernet has no carrier.

## V6.49 Compiled iwinfo Scan Proof - 2026-08-06

- Analyzed unstripped `libiwinfo.so.20230701` SHA256
  `96b48c40c330c06e1490ad9694ab7d5f684a1c52de079acabd941481d34fbbfe`
  with Ghidra. The 235-function/1,664-symbol report directly recovers the
  radio-mask, temporary-interface, cleanup, and band-filtering control flow;
  report SHA256 is
  `4ac558fe0a7b3dcec0e1828ec6767cf1b674cec3c418b957c4f36fafd5bd0379`.
- Focused verifier SHA256
  `696d0d1d7581c7c988a05b488bf7f99929fa08a41e3c934552ac9eb7979b76c3`
  passes 14 checks and proves the candidate-embedded library SHA256
  `d7830db57239b71d0a7bab0d194166791f85b57d1b1e915dffec73f4350da676`
  is byte-identical to the staged package. JSON SHA256 is
  `4a0a5a3042fa9e87b30975639237e8c8b3a1b43580e45a629a6661569eb347ff`.
- Audit report SHA256 is
  `1db138a6c2ac4f612a52013f724f2beeb1dcd0928a99e155cd49832f77553302`.
  Restarted follow-on PID 11520 with wrapper SHA256
  `28ba069140989a0d32ff71d3bd4c49b99e8eeb1dccd9bbfadd5ebd8781bea183`.
  It remains gated behind recovery PID 11348; no live target action occurred.

## V6.49 Fresh COM3 Recovery Attempt - 2026-08-06 10:53 +03:00

- Confirmed the PL2303GC serial adapter is started and enumerated as COM3.
  Replaced stale waiting PIDs 11348/11520 with recovery PID 7636 and follow-on
  PID 24324.
- New captures are `v649-recovery-20260806-105327` and
  `v649-live-gate-20260806-105328`. Both exact preflights pass.
- The fresh serial handle opened at 115200 8N1 but received zero bytes while
  polling with Enter/Ctrl-C; Ethernet remains disconnected. No router command,
  backup, transfer, flash, NAND/UBI write, or protected-state access occurred.

## V6.50 NPU Status Reconciliation And Offline Freeze - 2026-08-06 12:02 +03:00

- Reconciled nine stale NPU debugfs parity labels with the completed static
  conclusions. Patch SHA256 is
  `9720961604807a642614d7715ec7136b8800e9754c1193d43a5816623ccaac9b`.
  This changes status text only; it does not modify packet ownership or the
  NPU data path.
- Caught one build invocation that omitted
  `W1700K_EXPERIMENTAL_MT76_NPU=1` by comparing symbols against V6.49. Added
  fail-closed package/full-build wrappers that require NPU symbols and the new
  status strings. Correct wrapper SHA256 values are
  `3449534a6b9aae732f3c647fbe4cd42abd8e53f0d6d0cb9d77563780d69543fb`
  and `53c293bc0ecb3ee61c93cd51b9ec27b447f0a18dfeb2e6a9fe905d3e20273eda`.
  The no-NPU build was rejected before image promotion and never flashed.
- Full build exits 0. Candidate is 20,620,092 bytes, SHA256
  `dc2fe6efaa28d0783e6a63225b0d357ff1b045807b5eeb087b9bed68b47c272a`,
  with 76,996 bytes FIT headroom. Kernel and DTB equal V6.49; rootfs changes
  are `lib/apk/db/installed`, `lib/apk/db/scripts.tar.gz`, and
  `lib/modules/6.18.34/mt76.ko`.
- Exact embedded mt76/connac/mt7996 hashes are
  `4e31bb81f82c74ce22e56b093b4f926fc1da69c22dcfd1349b35666068dd5b9c`,
  `78b114c931721ae6cf20a50473b83a82852ef54449423d692871d01f48dfb37c`,
  and `b4c5632aaadc5affcc8586469ef3f6f1248b4b8beba39029d2a437ed1e4519af`.
- Ghidra fully analyzed exact V6.50 mt76 at 452 functions, 4,282 symbols, and
  45 selected functions. Report SHA256 is
  `5ad733b123c9e2c1690c53abdec09ce361c8c8e1184c9c17759bf928ecd08bd6`.
  Connac/mt7996 are byte-identical to exact V6.49 analyzed inputs.
  `PASS_V650_NPU_STATUS_RECONCILIATION checks=95` and
  `PASS_V650_OFFLINE_CANDIDATE` pass; exact candidate verification JSON
  SHA256 is
  `8cac8541cc9505b5a2848f152078bf993674c33db8a4e0a703ed9acedd7ff79c`.
- Module-delta archive records equal 92,152-byte text sections, 17 changed
  bytes limited to `seq_write()` string-length immediates, and byte-identical
  companion modules. Its checksum manifest SHA256 is
  `44bbb291be6e74585b9c4f4861a0691716513a3a0edca35ce7f881d74863e0ab`.
- Corrected workspace/FinalResult bundle
  `W1700K-V6.50-NPU-Status-Reconciliation-20260806-OFFLINE` has 97 payload
  files/33,174,899 bytes, 98 successful checksum replays, and 99 matching
  mirror files. Top checksum and file-manifest SHA256 values are
  `a34c6591793806d2e9d8dcae57cdd2dcdd2d80f00c220a03bdd80ca50745a19b`
  and `f79b258647a772b61e042da979282e3c8cf7afd58628501c2df6a2c524e0b011`.
  The first bundle is retained only as `REJECTED-NESTED-CHECKSUM`; its
  top-level checksum omitted the nested checksum file.
- Exact recovery and follow-on scripts pass preflight with SHA256 values
  `2928f71689b65559308fc514f9ac5906877e9e40cecb075808ff6c71975f6e06`
  and `f5303c3f5c97919fb85aaed83aa7fed9707cb0d5381289289965aabe023f21f8`.
  Recovery PID 6624 owns COM3 at 115200 8N1 in
  `v650-recovery-20260806-115401`; follow-on PID 20624 waits for completion.
  UART RX remains zero and Ethernet has no carrier. No target command or
  persistent/protected-state action occurred; V6.50 remains unflashed.

## Exact Hostadpt Ghidra-MCP Cross-Check And COM3 Rearm - 2026-08-06 12:31 +03:00

- Imported and fully analyzed exact stock `hostadpt.ko` in Ghidra 12.1, then
  captured MCP analysis/decompile outputs for all six packet/ring lifecycle
  functions under `work\ghidra-mcp-hostadpt-v650-audit-20260806`.
- Added a pinned prepared-source reconciliation verifier. It passes 96 checks
  with zero failures. Report, verifier, verification JSON, and 16-entry
  manifest SHA256 values are
  `7ba84c2fbd503006d1cd4d9d9872eea4e610c67b4982ab46276b0b5cf39ac3c4`,
  `f31ffb91d9e042d50e6e051eb06b3578fd4ccb6ddb90e97f18fb71fca41ecd58`,
  `e37ec008d8fcb6ec5c28cdab1007c186a4173bec9556e084d0044a63854f95c0`,
  and
  `77847588d434df600802efad2c151a48ab941578781681e3921404d15aa6abdc`.
- Exact stock evidence confirms the current static conclusions and exposes no
  new source defect. In particular, stock teardown clears hooks without a
  visible ring/DMA free path, so the more complete V6.50 teardown remains an
  intentional safety improvement.
- Stopped stale PIDs 6624/20624. Fresh PID 13248 owns COM3 in
  `v650-recovery-20260806-121948`; PID 12512 waits in
  `v650-live-gate-20260806-122047`. Both preflights pass. UART RX is still zero
  and Ethernet has no carrier, so no target or persistent-state operation has
  occurred.

## Clean COM3 Reopen - 2026-08-06 12:42 +03:00

- Windows enumerated the expected PL2303GC adapter on COM3. Retired stale PIDs
  13248/12512 and launched exact V6.50 recovery PID 23084 at
  `work\live-captures\v650-recovery-20260806-123954`.
- Preflight passed; COM3 opened at 115200 8N1. Despite periodic Enter/Ctrl-C,
  the raw capture stayed at exactly zero bytes during a 60-second watch.
  Ethernet stayed `Disconnected` with zero carrier.
- No target identity, router command, TFTP, RAM recovery, backup, transfer,
  sysupgrade, NAND/UBI write, or protected-state access occurred. The session
  remains armed and V6.50 remains unflashed pending a physical UART/power edge.

## V6.51 WiFi Boot Root Cause, Build, And Recovery Gate - 2026-08-06 13:34 +03:00

- Exact historical live lines show validation under country `00` rejected
  radio2's 6 GHz EHT320 configuration and then aborted setup for every logical
  radio. Source ordering confirmed validation preceded netifd's `iw reg set`.
  The repeated `-95` setup noise was separately linked to applying the one
  wiphy's global antenna masks once per logical radio.
- Implemented shared-country normalization and `--prepare-regdomain`, moved
  that gate before `setup_phy()` in ucode and legacy netifd, synchronized
  radio0/1/2 through sanity and LuCI, hid country `00`, and restricted antenna
  mask programming to radio0. No transmit-power behavior changed.
- Static syntax, width/validator fixtures, recursive native ucode parse, and
  focused package compiles all pass. Full build exits 0 in 92 seconds with the
  experimental NPU implementation explicitly enabled.
- Candidate `w1700k-wifi-bootfix-v6.51-20260806-sysupgrade.itb` is 20,620,092
  bytes, SHA256
  `176496e7f05953867119ad3ca9af9d0fc850399db7a30db01bab9cb9f7532218`.
  Kernel/DTB and the three WiFi modules are byte-identical to V6.50; rootfs has
  only seven expected changed files. V6.50 is retired from flashing.
- `PASS_V651_WIFI_BOOT_ORDER_CANDIDATE` passes. Verifier and result SHA256
  values are
  `8982af3239fe150190737a6214e657972bba9697f1bf392daff80e43e9fe5171`
  and
  `b27ff6452afe5159f048ce43c89171c906a974a162c3b674406d013f16c7563b`.
- V6.51 recovery harness SHA256
  `e7f528c4cd826cad2eca3af378ff3fa00dc80439edf61f4bb60c707dac6e1ac7`
  passes preflight and now fails closed on exact installed WiFi hashes,
  regdomain ordering, radio mapping, and retired boot-error signatures.
- COM3 is present. Probe captures
  `work\live-captures\v651-identify-20260806-132744` and
  `work\live-captures\v651-identify-20260806-132807` each contain zero UART
  bytes. Ethernet is disconnected. No target or persistent/protected-state
  operation has occurred; live identification, backup, flash, and WiFi/NPU
  validation remain pending.
- Armed V6.51 recovery PID 17228 at
  `work\live-captures\v651-recovery-20260806-133622`. It is waiting at the
  boot-prompt catcher with zero UART RX and no Ethernet carrier.
- V6.51 follow-on wrapper SHA256
  `684687fdde06fd38634e0ca6356d5cc5109ad5d26d2cbdde0fae436c98afffb5`
  passes preflight. PID 23524 waits at
  `work\router-tests\v651-live-gate-20260806-134118` and is gated on exact
  recovery completion, protected-backup checksum replay, W1700K identity,
  mode-0/mode-3 tests, radio-pinned LuCI scans, synthetic TX, and restoration
  to persistent mode 0.
- Stopped recovery/follow-on PIDs 17228/23524 after no physical edge arrived.
  COM3 immediately reopened, but a direct Enter/read probe observed zero bytes
  with CTS, DSR, and carrier detect all false; Ethernet remained disconnected.
  No process now owns COM3 and no target or persistent/protected state changed.

## V6.52 Unregister Token-Quiescence Gate - 2026-08-06 14:11 +03:00

- Compared normal unregister with reset/shutdown and found that the normal path
  swept token/TXWI state before tasklet drain and never disabled RX/TX NAPI.
  This left a concrete TXFREE claim-versus-sweep UAF/double-completion race.
- Added patch
  `9999zzzzzzzzu-mt7996-quiesce-unregister-token-sweep.patch`, SHA256
  `28e7b993a1668755e5aa5288f7399d7e40fb00a552f0de8beb8b2b10a1525b54`.
  Strict checkpatch is clean. Patch was independently dry-run, applied to a
  frozen after-snapshot, and then installed last in the OpenWrt mt76 stack.
- Added verifier
  `tools\verify_w1700k_v652_unregister_token_quiesce.py`, SHA256
  `9bd6dba1a5c92a8425c96ed5e61dda397b84d97df02d903ad4d752c1c228c94d`.
  Result: old 63 states/96 transitions/2 unsafe, hardened 49 states/69
  transitions/0 unsafe, 9 static checks pass, final marker
  `PASS_V652_UNREGISTER_TOKEN_QUIESCE`. JSON SHA256 is
  `5007b19a36fc7d57a50879453b3bd9b831ca785045e10b961658f7755b4c6a39`.
- Forced mt76 clean and prepare completed. Prepared `init.c` SHA256
  `50224999b32443a547edae7b60b2feeb4730d74c563b72edbfacd4fdc7723c08`
  and `mac.c` SHA256
  `1064fb582e5367153e28a44e6bbb1226f2ccf8163c83a91ed5d7942eae8943a2`
  exactly match the verified after-snapshot.
- Focused mt76 compile with `W1700K_EXPERIMENTAL_MT76_NPU=1` exits 0 in 106
  seconds. Expected NPU/unregister symbols remain present. Module hashes are
  mt76 `0c02cbf0f72db3a2e79c5271aef8db0b17388d9e19ad01c38d48aad085de6ffa`,
  mt76-connac
  `52296c935a8d82d7efe855a5253ebac40ee187882e60806e0e8fa329697ad08b`,
  and mt7996e
  `ecd08369485e37eac233ee8bb8e54e3d7a2c69e37a30e60f13261bfdcc0db18a`.
- COM3 enumerates and opens, but the fresh probe returned zero bytes and false
  CTS/DSR/carrier; Ethernet remains disconnected. No target identity, command,
  recovery, backup, flash, NAND/UBI, or protected-state access occurred.
- Next boundary: full V6.52 image build and exact FIT/rootfs/module verification,
  followed by guarded COM3 recovery only after positive W1700K identification.

## V6.52 Full Build, FIT Audit, And Ghidra Gate - 2026-08-06 14:25 +03:00

- `run_v652_full_build.sh` SHA256
  `bbc4f6d175a42fdc6d7407e6f078b36e90a4c3b6349795d938d8d6cf504fc5d0`
  passes syntax/shellcheck and exits 0 in 96 seconds. Build status pins source
  HEAD, both NPU patches, the interleaving verifier, and prepared source hashes.
- Produced `w1700k-wifi-npu-v6.52-20260806-sysupgrade.itb`, 20,620,092 bytes,
  SHA256
  `166bf5ddb9ff3311868b931346150ff11a9fc3cbf7827ee6fda59e1518611db5`.
  FIT kernel/DTB match V6.51 exactly; only APK metadata and embedded mt7996e
  differ in an otherwise shape-identical 1,146-file rootfs.
- Embedded module hashes: mt76
  `4e31bb81f82c74ce22e56b093b4f926fc1da69c22dcfd1349b35666068dd5b9c`,
  mt76-connac
  `78b114c931721ae6cf20a50473b83a82852ef54449423d692871d01f48dfb37c`,
  mt7996e
  `10df7615d5ca3532fce118ac5066f1be2601bb2b1a948fd82bcea2f08937c075`.
  Forbidden proprietary stock kernel modules are absent.
- Ghidra runner SHA256
  `45b4ca3f0295675fe72f85501384780cdd539698be1b996771688d7abe8a3f50`
  exits 0 after full analysis. Report SHA256
  `668537e2aaf9a32b56fd204090bd1976b6f38fe24f3aa154c783d47bebf19b4b`
  independently shows completion drains and both NPU IRQ masks before NPU stop
  and token sweep. A corrupt user `_code_browser.tcd` warning was nonfatal;
  auto-analysis, post-script, save, and both recorded exit files succeeded.
- `verify_w1700k_v652_candidate.py` SHA256
  `875f913c85707cc2d49c3784ae318450f57c2031c2f185f8b23f0f6e3ea1fe33`
  returns `PASS_V652_OFFLINE_CANDIDATE`. Result JSON SHA256 is
  `d3a882c276ddb4d9ac97ba1c486e20ad6e8f32e6f5c856147d24baf5dba8114c`.
- V6.51 is superseded; V6.52 is promoted offline but unflashed. COM3 is now
  absent after a prior zero-byte open, and Ethernet remains disconnected. No
  target/protected/persistent operation occurred.
- Created exact V6.52 recovery harness SHA256
  `353ea6584b976b31f02df84bac0b84b9acbc6c099e9216f7e4720fa8d3dac8f9`.
  PowerShell parsing and preflight pass. It pins the candidate and frozen proof
  chain and adds a post-flash mt7996e unregister/reload smoke gate.
- Launched hidden recovery PID 23352 at
  `work\live-captures\v652-recovery-20260806-143034`. COM3 opened at 115200
  8N1 and the catcher is armed, but serial remains 0 bytes and Ethernet remains
  disconnected. No command or target state change has occurred.
- Added second-stage wrapper SHA256
  `64a0c0e0d652b14612003010156344ac3d2ddad0145b07eba1b118f94fe5caa4`;
  syntax and preflight pass. PID 21784 waits at
  `work\router-tests\v652-live-gate-20260806-143255` for exact recovery and
  protected-backup completion before synthetic mode/radio/NPU validation.

## V6.53 Teardown Audit, Build, And Live Handoff - 2026-08-06 15:54 +03:00

- Canceled the unflashed V6.52 handoff after finding a producer-after-cancel
  race across reset, coredump, RRO, RC, NPU-fault, and watchdog paths. V6.52
  must not be flashed; its serial and validation PIDs were stopped before any
  target input or persistent operation.
- Implemented teardown/requeue gate patch SHA256
  `b0a5a4ad0841b41778fb46f4c2d110e431fd5285a5e12911a29817caa629daa6`
  and HIF2 lifetime patch SHA256
  `246df490ee5c30c0ab397c0ea6b49317d5769c129bdde038f5ad62443aaf1581`.
  Strict checkpatch reports zero errors, warnings, or checks for both.
- Teardown state model moves from 33 states/41 transitions/5 unsafe to
  21/24/0. HIF2 has 5 static checks, and the inherited unregister/token model
  remains 49 states/69 transitions/0 unsafe. All three behavioral verifiers
  pass against the prepared and full-build sources.
- Clean `-j1` normal and Sparse builds produce identical mt76, mt76-connac,
  and mt7996e modules. Sparse reports 29 checks and zero scoped diagnostics.
  Clang analyzer reconciliation reports 39 raw/29 scoped CDB commands, zero
  analyzer failure, 17 known residual findings, zero new findings, and PASS.
- `run_v653_full_build.sh` SHA256
  `a716064248f8e3d9c15919f8d69788f842cee803f70be512b92c20f678ea780e`
  exits 0 in 87 seconds at HEAD
  `5575e4a97f119f682223a090c4a78c0913f906f5`.
- Produced `w1700k-wifi-npu-v6.53-20260806-sysupgrade.itb`, 20,620,092 bytes,
  SHA256
  `1024d1354a4eeef6bb8bc9535a898b54312c9b8dd4be2943d49b162550f5ee19`.
  FIT contains Linux 6.18.34, the W1700K UBI DTB, and squashfs rootfs with
  76,996 bytes headroom. Relative to V6.52, kernel/DTB are byte-identical and
  only APK metadata plus mt7996e change in the 1,146-file rootfs.
- Embedded module hashes are mt76
  `4e31bb81f82c74ce22e56b093b4f926fc1da69c22dcfd1349b35666068dd5b9c`,
  mt76-connac
  `78b114c931721ae6cf20a50473b83a82852ef54449423d692871d01f48dfb37c`,
  and mt7996e
  `941acc3df314fc747610900e3cb76fcae5e5a7eea05de1d638f677a3e39d748f`.
  No proprietary stock NPU/WiFi module is shipped.
- Full Ghidra analysis report SHA256
  `5d783af63b96d0b13609da10f26ceef681966d7789c2b8db277786ef0f226ec5`
  covers 626 functions, 5,346 symbols, and 18 selected teardown/HIF2 functions.
  Binary control flow independently confirms producer gating, two-stage work
  cancellation, completion drains, RRO cleanup, NPU stop, token/DMA teardown,
  and delayed HIF2 release.
- Exact offline verifier SHA256
  `d4b0d823671ba35f66fb6e1951e0a4615048e8f707ccb9e2e51b1335df6bfb7`
  returns `PASS_V653_OFFLINE_CANDIDATE`; frozen JSON SHA256 is
  `9f7bf669665ebe4e87fe4aedcc31a31def518e3142f9b947837502b3b3793b4f`.
- Frozen bundle and FinalResult mirror contain 47 payload files totaling
  25,101,384 bytes and replay 48 checksums. Bundle SHA256SUMS and manifest file
  hashes are
  `5f3e76b8d55f5f24c914ceadd9b3d5ca0b330caa6585b3a2d12ceee4d0d55826`
  and `ffc6b0dd7ddd2a7cb91d547efaa37eeca6123ce85099bb43102eac6d2a3c5c5c`.
- Launched V6.53 guarded recovery PID 1324 at
  `work\live-captures\v653-recovery-20260806-155254`; exact preflight passes
  and COM3 opens at 115200 8N1, but RX is still zero bytes. Launched follow-on
  validation PID 22136 at
  `work\router-tests\v653-live-gate-20260806-155343`; it waits up to six hours
  for exact recovery, protected-backup replay, and W1700K identity.
- No router identity, serial command, backup, TFTP, recovery boot, image
  transfer, sysupgrade, NAND/UBI write, or protected-state access has occurred.
  Live proof still requires a physical boot edge and positive serial identity.
  Static stock hostadpt ownership, descriptor/ring/doorbell, SKB/bufid/scatter,
  TXFREE/token, ping-pong, and RRO parity remain closed by the V6.48/V6.50
  evidence. Remaining work is live concurrency, reset/fault/AER behavior,
  mode 0/3 recovery and throughput, and final WiFi/MLO performance.

## V6.54 Shared-Wiphy WiFi Audit, Build, And Live Handoff - 2026-08-06 16:34 +03:00

- Stopped the unflashed V6.53 gates before target input. Historical live
  evidence shows 5 GHz radio1 creating a wdev before radio0's later global
  antenna setter failed with `(-95)`. Since radio0/radio1/radio2 share one
  mt7996 wiphy, the previous radio0-only guard was unsafe under four of six
  setup permutations.
- Implemented an exact-W1700K guard in both ucode and legacy netifd WiFi
  scripts. Patch SHA256 is
  `41641459a396c77a687e7225a2a4faebe456fff836dd377b96e9b119ffb37524`.
  The fixed integrated antenna topology now uses the driver full-chain default;
  all non-W1700K behavior and TX power are unchanged.
- Shared-wiphy verifier SHA256
  `b48ccfcc9fd5b4ccf8fd843dd8e01372fb7779a2738a04b2fc3b1bcef9e74fe3`
  passes 13 checks and reduces modeled unsafe orders from 4 to 0. Patch replay,
  shell syntax, package compile, and native ucode bytecode compile all pass.
- Reran the exact Ghidra/MCP stock `hostadpt.ko` reconciliation against the
  current prepared mt76 tree: 96 passed, 0 failed. Frozen replay SHA256 is
  `f0e8c1d6375f0a9783b6ee6942464b3057a6a369f3064a17ba9c298882eb5b55`.
  Offline stock parity remains closed for tracked ring/descriptor/doorbell,
  SKB/bufid/scatter, TXFREE/token, ping-pong, and RRO behavior; remaining NPU
  proof is live-only.
- `run_v654_full_build.sh` SHA256
  `2dc07d5c0fc073968aa37ac9858a63f50ecfff67981b004b4b66d51d63d8e011`
  exits 0 in 88 seconds. Candidate
  `w1700k-wifi-npu-v6.54-20260806-sysupgrade.itb` is 20,620,092 bytes, SHA256
  `9b0c04db61ca16a9d2b9c60cc5e69402ad48a5f027f5fe7155e27779fdd682dc`.
- Kernel, DTB, mt76, mt76-connac, and mt7996e are byte-identical to V6.53.
  Rootfs shape remains 1,146 files and changes only APK metadata plus
  `lib/netifd/wireless/mac80211.sh`. The unchanged mt7996e inherits the full
  626-function/5,346-symbol Ghidra proof.
- Candidate verifier SHA256
  `43bd152ba7bb668a6112a4a46ccd6efad708ca8016652d226482fb4c1af5085d`
  returns `PASS_V654_OFFLINE_CANDIDATE`; result JSON SHA256 is
  `08bf9ee11ddaae300723c4e47cd9bbd0eccf630eb29afd01fb37ef28ddcfe4ff`.
- Frozen FinalResult bundle
  `W1700K-V6.54-Shared-Wiphy-WiFi-Fix-20260806-OFFLINE` has 86 files,
  40,833,062 bytes, and 84 passing checksum entries. `SHA256SUMS.txt` SHA256 is
  `337dd155d5ec55ae06025e0afb4a24822391efbee1880daf21d4afce6f1ff4ac`.
- Guarded recovery PID 19616 owns COM3 at
  `work\live-captures\v654-recovery-20260806-162944`; validation PID 15172
  waits at `work\router-tests\v654-live-gate-20260806-163109`. Both exact
  preflights pass. UART RX remains zero bytes and Ethernet is disconnected, so
  no identity, command, backup, TFTP, recovery boot, flash, NAND/UBI write, or
  protected-state access has occurred.

## V6.54 Cold-Boot And Passive-UART Triage - 2026-08-06 16:58 +03:00

- The V6.54 catcher captured two early vendor boot sequences totaling 8,748
  bytes (SHA256
  `29b6fb6c5c43a7919470a491e1a3811ba5d510e98d69a0a586519ad0da8c45e4`).
  Both prove the expected AXON 2.0/AN7581GT/2 GiB/W25N04K hardware identity.
- Both boots emitted `FDT_MAGIC or IH_MAGIC check fail`,
  `Parse main image fail`, and stopped at `usxgmii_pcs_int en 1`, before a
  vendor or modern U-Boot prompt. No Linux boot or fatal kernel signature was
  observed. Ethernet negotiated at 1 Gbps on the isolated link.
- PIDs 19616 and 15172 were stopped to remove the catcher's repeated UART
  interrupts as a variable. Neither process reached a target command, backup,
  transfer, recovery boot, image test, or persistent write.
- Passive receive-only logger PID 2540 opened COM3 successfully at
  `work\live-captures\v654-passive-boot-20260806-165419`. It remains at zero
  bytes because a new physical cold boot has not yet occurred. V6.54 remains
  unflashed; bootloader, environment, NAND/UBI, factory, and calibration state
  are untouched.

## V6.54 Access-Gate Follow-up - 2026-08-06 19:55 +03:00

- Recovery input is now bounded to a detected U-Boot autoboot window instead
  of transmitting throughout early platform initialization. Recovery harness
  SHA256 is
  `331e02fd3edede46204d187ef3a29eb12751ab16b3eddf4bc4f17dc7c8a2792b`;
  validator SHA256 is
  `8468bc2383f4c2befbdf9427869d4eddd7421dc649075327ffbaa2f55af6193f`.
  Both parse and recovery preflight passes.
- The new catcher, direct COM3 probes, PuTTY `plink`, and WSL COM aliases all
  received zero bytes. Ethernet remains at 1 Gbps but exposes no target
  neighbor. `192.168.1.1` belongs to the active Huawei Wi-Fi path and was
  intentionally not contacted.
- All live processes were stopped before target input. The candidate remains
  offline-only and no persistent router operation occurred.

## Live Access Pause - 2026-08-06 20:00 +03:00

- A final lightweight refresh found COM3 free but with no RX and isolated
  Ethernet at 1 Gbps with no target neighbor. No PuTTY process is active.
  Flashing and live WiFi/NPU validation are paused pending the exact working
  PuTTY connection or restored serial RX. No router state changed.

## V6.55/V6.56 Terminal Teardown Session - 2026-08-07 03:40 +03:00

- Restored exact target access through Ethernet source `192.168.1.224` and
  positive board identity `gemtek,w1700k-ubi`. This avoided the simultaneous
  non-W1700K WiFi gateway at the same destination address.
- V6.55 live module removal hung after the TX-worker fix. D-state inspection
  and a COM3 SysRq task dump narrowed it to a second terminal
  `napi_disable(&dev->tx_napi)` in common mt76 DMA cleanup after mt7996 had
  already disabled that NAPI instance for completion draining.
- Recovered the half-unloaded V6.55 state with direct SysRq reboot. Healthy
  U-Boot, FIT, Linux, mt7996 firmware, Ethernet, and 2 GiB memory returned;
  protected NAND data and environment were untouched.
- Implemented a device-lifetime `tx_napi_disabled` flag and exported
  `mt76_dma_disable_tx_napi()` helper. Both mt7996 terminal paths and common
  DMA cleanup now share the helper. First-call ordering is unchanged; later
  terminal calls are no-ops.
- Clean patch preparation, strict checkpatch, focused mt76 build, and full
  image build pass at source commit
  `5575e4a97f119f682223a090c4a78c0913f906f5`. V6.56 image SHA256 is
  `53f42e5a72baa22107cd4c9a1aac551018f7383ff0b9f17b3d5bf9e7a9da9ce5`;
  exact verifier reports `PASS_V656_OFFLINE_CANDIDATE`.
- Saved the current sysupgrade configuration, verified the remote image hash,
  passed router-side `sysupgrade -T`, and performed preserved-config
  sysupgrade. Installed mt76, mt76-connac, and mt7996e hashes match the exact
  verified image.
- Ran three guarded teardown cycles. Every `rmmod mt7996e` returned, every
  `modprobe` reloaded WM/DSP/WA firmware, and every `wifi up` restored all
  three logical radios. The 120-second SysRq watchdog never activated.
- Ran a normal reboot after the cycles. New boot ID is
  `bded06e1-08eb-4382-abea-8e7e4ee03d79`; current NPU mode is 0, logical
  radios are up, no SSID interfaces are enabled, and available memory is about
  1.68 GiB.
- COM3 trace SHA256
  `2d99280f4871df28d8553672e199d04246dcb58250d8dac83202d7eb6f64f668`
  records two full boots and all reloads without panic, Oops,
  `napi_disable_locked`, or watchdog-expiry marker. Full evidence and boundary
  statement are in `work\W1700K_V6.56_IDEMPOTENT_TX_NAPI_LIVE_REPORT.md`.

## V6.56 Mode-0 Synthetic And Boot-Loop Triage - 2026-08-07 03:51 +03:00

- The unattended radio harness exercised hidden 2.4/5/6 GHz APs and 5+6 GHz
  MLO. Its repeated WiFi reloads caused visible link and LED cycling, but the
  boot ID never changed and uptime advanced normally past 1,084 seconds.
- COM3 capture
  `work\live-captures\v656-mode0-synthetic-20260807-034431\serial.raw` is
  3,529 bytes, SHA256
  `3fee29114b690cd9275356fef00cef1caf1ecd1c56bffc640e7ef2b1c9680c5b`,
  with no reset or fatal signature.
- The 5/30 result is not a firmware boot failure: four single-band AP checks
  incorrectly required an MLO link-ID line, and the tri-band fixture violated
  the enforced `radio1 radio2 radio0` ordering. Original wireless UCI data was
  restored byte-for-byte and synthetic interfaces were removed.

## Corrected Mode-0 And Mode-3 Validation - 2026-08-07 04:10 +03:00

- Corrected the two harness defects and added focused fixtures. Mode 0 then
  passed 37/37 and mode 3 passed 40/40 across all single-radio widths, two-link
  and tri-band MLO, LuCI scans, backend negatives, services, NPU lifecycle,
  hostadpt rings, firmware handshake, TXFREE bounds, and restore checks.
- Two mode-3 PCI unbind/rebind cycles passed with balanced transport teardown.
  COM3 SHA256
  `384917b8d27573c6a25db940e7079a2ab1aae599217bc06db093bf68f877dd5b`
  contains both intentional reboots and the reloads without a fatal signature.
- Production mode 0 was restored at boot ID
  `84940bcb-446c-4c0b-8e59-72e74f6b48e8`; the fallback is removed and the
  original wireless configuration hash is unchanged. No image or protected
  persistent state changed.

## Mode-3 VIF Deletion Stress - 2026-08-07 04:18 +03:00

- `work\router-tests\npu-mode3-20260807-041412` passed the 40/40 synthetic
  suite, 20 VIF create/scan/delete cycles, and two PCI unbind/rebind cycles.
  Synthetic, extra-probe, and reload exits were all zero.
- Synthetic, VIF-stress, and reload log SHA256 values are
  `d720758cf7a78349af268fbfaff347dab3ce5820cb92be66be9e2de74f033c02`,
  `ef4fd025ca3f74dc9e0f14ed6746373154497e900242ec9b8c87af06ba5c86ce`,
  and `a4315b4cb077b3bdb893bf0e1308be2bd0e2b45fb4deee2e5446cb00969d1b32`.
- The extra probe completed a 682-line verification scan with unchanged
  generation 1, zero missing/mismatch/channel-timeout deltas, 44 deferred
  channel-management events, and zero payload/TXFREE movement.
- COM3 SHA256 is
  `72e7b24b5e74bf673a89f84b6256db6bd14c904c012296d2196f9913b3bd4aad`;
  no fatal kernel signature or recovery-watchdog activation occurred.
- The reload helper now distinguishes unavailable `CmaFree` and records
  `MemAvailable`; helper SHA256 is
  `5bc5554187a1e640c5edf820704f4e2f76ae73e7c91533e4cf7c3d7df0223311`.
- This is management-churn proof only. Zero payload/TXFREE movement leaves
  traffic-path ownership and TXFREE/token stress explicitly unresolved.

## Reported Boot-Loop Capture - 2026-08-07 04:30 +03:00

- Initial live state was healthy and reachable at boot ID
  `15bd7ec5-f0df-42f0-971b-50ee1621fabe` with about 393 seconds uptime.
- A local Windows-to-SSH quoting failure converted grep alternatives into
  executable remote pipeline stages. It invoked one `wifi` reload followed by
  one explicit `reboot`; the resulting reset is diagnostic operator error,
  not spontaneous V6.56 behavior.
- COM3 capture
  `work\live-captures\bootloop-report-20260807\serial.raw` is 38,062 bytes,
  SHA256
  `d5f51e0e781afd53c22964a36e9fadc06f4a98a9d8897418e48f63f72d396bd9`.
  It has exactly one clean `reboot: Restarting system` and no panic, Oops,
  BUG, lockup, or watchdog-expiry marker.
- The router returned as boot ID
  `6267382e-d25f-42c2-b05b-1723e6690825`, stayed reachable beyond 175 seconds,
  loaded NPU firmware `0.1111` and mt7996 WM/DSP/WA firmware normally, and had
  about 1.68 GiB available memory.
- No flash or persistent target write occurred. Router log filtering is now
  constrained to local filtering or SSH-stdin scripts to prevent recurrence.

## Boot-Loop Recheck - 2026-08-07 04:48 +03:00

- The reported repeat reset did not reproduce. Boot ID
  `6267382e-d25f-42c2-b05b-1723e6690825` remained constant while uptime moved
  from 1,095 to at least 1,311 seconds; Ethernet ping, SSH, and LuCI HTTP/HTTPS
  checks all passed.
- Mode 0 was loaded and no mode-3 fallback or unattended test process remained.
  Memory, uhttpd, mt7996 firmware state, radio state, and UBI volume health were
  normal. Fatal current-boot log scans were empty.
- Passive COM3 capture
  `work\live-captures\bootloop-live-20260807-044353\serial.raw` remained empty
  for 180 seconds, SHA256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
  The unchanged boot ID is the authoritative no-reboot evidence.
- No flash, fix, or persistent target write was performed because there was no
  live failure source to correct.

## Exact Stock TX Topology And Packet-Gate Session - 2026-08-07 05:12 +03:00

- Added a deliberate `-EnableStockTopology` runner gate and stricter deep-trace
  packet assertions while retaining fail-safe restoration to plain mode 0.
- Live mode 3 exactly matched recovered stock topology: bands 0/1 share group
  0, hardware index 18, register `0xd4420`; band 2 uses group 1, hardware index
  21, register `0xd8450`. Group, alias, register, and overall topology checks
  all returned 1.
- Under this mapping, V6.56 passed the complete 40/40 synthetic radio/MLO,
  LuCI/backend, NPU-lifecycle, and byte-identical-restore matrix. COM3 SHA256
  is `66645667a2056ab6276f4f87a28274d7337a21049f4271774ff5c9f097875d3b`
  and contains no fatal signature.
- The no-client AP broadcast probe moved the AP netdev TX counter by 128 but
  did not reach NPU payload/enqueue/consumer/shadow/TXFREE telemetry. This
  leaves a source-level mac80211 no-station boundary and router-only injection
  path to resolve; it does not invalidate the now-live-proven topology.
- The router was restored to NPU mode 0 with plain `/etc/modules.d/mt7996e`,
  unchanged wireless SHA256, no fallback process, and healthy memory.

## Post-Test Boot-Loop Investigation - 2026-08-07 05:25 +03:00

- Ethernet-bound board access and COM3 were observed after the user reported a
  loop. The current boot ID exactly matched the preceding runner's restored
  boot. Sixty-four of sixty-four five-second ping/SSH samples passed while
  uptime advanced from 512.10 to 840.32 seconds without reset.
- Current logs, memory, LuCI, NPU mode, and UBI health were normal. Passive
  COM3 captured zero bytes, consistent with the unchanged boot ID.
- The apparent repeated boot text came from the runner's two deliberate
  reboots plus the vendor and chainloader U-Boot stages. Prior serial evidence
  has exactly two orderly restart markers, not an uncontrolled loop.
- Both UBI environment volumes are erased and `fw_printenv` therefore reports
  bad CRC; no causal relationship to the current stable boot was observed and
  no environment write was made.
- Evidence and hashes are recorded in
  `work\live-captures\bootloop-investigation-20260807-051744\SUMMARY.md`.

## Router-Only NPU TX Lifecycle Session - 2026-08-07 05:52 +03:00

- Proved from mac80211 source and live `num_mcast_sta=0` that the previous
  bridge broadcast was intentionally discarded before driver submission.
- Built and uploaded a static AArch64 monitor injector. Injected frames carry
  the standard mac80211 injected flag, select the real AP VIF by transmitter
  address, and enter the ordinary mt7996/mt76 DMA path with the VIF/global WCID.
- The initial injector pass advanced all NPU TX stages by 128 but captured only
  107 TXFREE completions because the harness stopped at the first positive
  completion. It safely restored mode 0 and motivated a full-convergence gate.
- Corrected run `work\router-tests\npu-mode3-20260807-054601` passed all three
  stages: 40/40 radio/MLO synthetic checks, 0-failure packet lifecycle probe,
  and two guarded module reload cycles.
- Exact packet deltas were 128 for payload, token allocation, enqueue,
  consumer, SKB-shadow publish/cleanup, classified TXFREE, and token release.
  Token count returned to baseline and every ownership-error invariant stayed
  unchanged at zero.
- Serial SHA256 is
  `813b4104b1027f1055e7cb7ef00888ad67cafb321a05e33ff0f515fab7378bf3`;
  no fatal marker occurred. Production mode 0, topology N, plain module config,
  and byte-identical wireless UCI were restored.
- Normal bounded TX lifecycle is now live-proven. Faulted TXFREE, sustained
  pressure, RRO churn, provider trans-pointer ownership, external MLO clients,
  and throughput remain the active boundaries.

## Reported Boot-Loop Recheck Session - 2026-08-07 06:05 +03:00

- Captured COM3 passively for 150 seconds after the user reported a loop and
  sampled the target over bound Ethernet SSH. The serial file remained empty;
  20/20 SSH checks returned one boot ID and monotonic uptime.
- Current dmesg/logread and pstore contained no fatal reset signature. The one
  startup UBIFS recovery completed successfully and is evidence only of a
  prior unclean reset.
- The router was left running V6.56 in its restored production state. No
  flash, environment write, configuration change, or service mutation was
  made. Evidence and checksums are in
  `work\live-captures\bootloop-live-20260807-060123\SUMMARY.md`.

## Controlled Dual-Stage Boot Session - 2026-08-07 06:30 +03:00

- Reproduced one complete reboot under COM3 instead of inferring from a quiet
  post-boot console. The vendor loader verified and started the OpenWrt U-Boot
  chainloader FIT; U-Boot 2026.01 then verified and started the Linux FIT.
  Those stages account for the two `Starting kernel ...` messages.
- No autonomous reset followed. Twelve pre-reboot and twelve post-reboot SSH
  samples each retained a single boot ID with monotonic uptime. LuCI HTTP and
  HTTPS, core services, memory, and all three radio devices were healthy.
- The serial stream contains one requested restart and no panic, Oops, BUG,
  watchdog expiry, OOM, or repeated U-Boot cycle. The known bad-CRC environment
  fallback was left untouched because the default FIT boot succeeded.
- Evidence and hashes are recorded in
  `work\live-captures\bootloop-live-20260807-062220\SUMMARY.md`.

## Provider-Context Lifetime Session - 2026-08-07 07:10 +03:00

- Headless Ghidra recovered the sole writes to stock
  `glb_npu_trans1/trans2`, their IRQ/ring readers, and the assign/unassign
  lifetime. The stock pointers are probe-order provider aliases and remain
  uncleared on teardown.
- Added explicit primary/HIF2 parity reporting and a managed device link that
  orders primary consumer teardown before HIF2 supplier devm release.
  Primary-probe failures now balance the retained HIF2 reference.
- The first compile exposed a dead cleanup label. After its removal, strict
  checkpatch passed for both patches and mt76 compiled successfully. Final
  patch SHA256 values are
  `6ac5fc6a452624e6b863dc4a77bd5a155e7fbefaf59c7a923b44d6e0626e2be0`
  and
  `5ce071d0b77fe7862a2258ebab5923e1f512f3ba4afda3dbbebda42595db23bb`.
- The compiled module is not installed on the router. Full-image inspection
  and COM3-guarded provider-unbind testing remain pending. Report SHA256 is
  `4822c761c2924d35ee82f032ba32f90f9d3d41c4c3be6323789507f45a2136df`.

## Reported Boot-Loop Follow-up - 2026-08-07 07:13 +03:00

- Observed one real boot-ID change after the old boot reached 1178.17 seconds.
  The event occurred in a gap between passive COM3 captures, leaving requested
  reboot, power interruption, watchdog, and silent hardware reset unresolved.
- The replacement boot remained stable past 1553 seconds. Two bound HTTP/SSH
  samplers recorded one boot ID and 291 total HTTP 200 responses; continuous
  COM3, `logread`, `ubus`, and NPU-status capture recorded no second event.
- Reset GPIO/IRQ, NPU progress, NPU watchdog IRQs, thermal state, memory, core
  services, and radios were normal. No persistent target state was changed.
- Summary SHA256:
  `506fae1885953a5f9529f4c5add0e9ddecbbc08355ab8f18374b80d562c193c9`.

## V6.57 Provider-Context Live Session - 2026-08-07 07:47 +03:00

- Built V6.57 from source revision
  `5575e4a97f119f682223a090c4a78c0913f906f5` with the explicit provider map
  and device-link teardown ordering. The sanitized full build passed; image
  SHA256 is
  `c4004d89704046e18528f9679f1db9b24189cffd24d5d2b20afa26cbbe20870f`.
- Offline verification returned `PASS_V657_OFFLINE_CANDIDATE`. The live flash
  passed 37/37 mode-0 checks. Mode 3 then passed 40/40 synthetic checks, the
  exact 128-frame router-only lifecycle probe, and two guarded module reloads.
- Sysfs proved the managed link from primary consumer `0000:01:00.0` to HIF2
  supplier `0002:01:00.0`. Both devices remained bound to their expected
  drivers after the reload sequence.
- The reported boot loop coincided with the deliberate module-reload portion
  of the harness; boot ID did not change. The runner intentionally left mode
  3 persistent. Restoring `/etc/modules.d/mt7996e` to plain `mt7996e` and one
  controlled reboot returned the router to stable mode 0/topology N at boot
  ID `fc60db21-bcc7-49cf-bcf3-71a48e237051`.
- The serial stream records three requested physical boots and no Linux fatal
  signature. SHA256 is
  `7be536b34c63bde7a51f8116d273c0e06d809d3000517aae447c0cfe12e1f619`.
- Supplier-first HIF2 unbind was not attempted in this session. Full report:
  `work\W1700K_V6.57_PROVIDER_CONTEXT_LIVE_REPORT_20260807.md`.
- Promoted bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.57-Provider-Context-Live-20260807`.
  Its 18 checksum entries passed; `SHA256SUMS.txt` SHA256 is
  `67bf753893f7c5fefb8b5d1e5dd399c6a1e6ea06db2b93d91df9b991df1e4491`.

## V6.57 Supplier-First Provider Teardown Session - 2026-08-07 08:14 +03:00

- Completed the deferred supplier-first gate in mode 0 and mode 3. HIF2
  unbind automatically detached the linked primary consumer; both devices
  rebound in the correct order and both watchdog guards remained quiet.
- Mode 3 cleared a balanced generation (`assign=2 unassign=2 hooks=2/2`),
  recreated stock topology N, and loaded NPU firmware 0.1111.
- The runner intentionally rebooted into mode 3 and then restored a plain
  mode-0 boot. Final boot ID is
  `540ec1c7-4bc7-4899-b005-9585ec479a83`; wireless UCI stayed byte-identical.
- Evidence summary SHA256 is
  `8f2b5c1f254f58d6256f72cd6451fb5f3729eca571d3e0192c4b54a47ade43fe`;
  serial SHA256 is
  `81878825582b97c75f6eee55969286a0887d1fd120a965f38defa1f9eb509128`
  with zero fatal markers. Full report:
  `work\W1700K_V6.57_SUPPLIER_FIRST_UNBIND_LIVE_REPORT_20260807.md`.

## Post-Teardown Boot-Loop Recheck - 2026-08-07 08:23 +03:00

- Rechecked the router after another reported loop. One boot ID remained
  stable from uptime 403 through 569 seconds, 20/20 bound-Ethernet pings
  passed, and LuCI HTTP/HTTPS each returned 200.
- Services, memory, mode 0, and all physical radios were healthy. No lingering
  test/reboot hook or fatal current-boot/pstore record was present.
- COM3 enumerated but emitted zero bytes during the 120-second passive window.
  No router state was changed. Evidence:
  `work\live-captures\bootloop-current-20260807-081922\SUMMARY.md`.

## Urgent Boot-Loop Recheck Session - 2026-08-07 08:44 +03:00

- Opened COM3 continuously for five minutes and independently sampled the
  router over Ethernet. All 134 SSH reads returned boot ID
  `540ec1c7-4bc7-4899-b005-9585ec479a83`; uptime advanced monotonically from
  1464.95 to 1774.59 seconds. The corrected ping loop passed 127/127.
- COM3 captured zero bytes, LuCI returned HTTP/HTTPS 200, and memory, status
  LED, reset-button IRQ, mode-0 NPU state, physical radios, and current logs
  were healthy.
- Startup UBIFS recovery is evidence of an earlier abrupt shutdown only. No
  reset occurred under capture and this image exposes no persistent cause, so
  the source remains unresolved. No router state was changed. Evidence:
  `work\live-captures\bootloop-urgent-20260807-083703\SUMMARY.md`.

## Controlled Boot Classification Session - 2026-08-29 04:58 +03:00

- Saved the live configuration, opened COM3 at 115200 8N1, and issued one
  controlled `sync; reboot` over Ethernet-bound SSH.
- COM3 captured one vendor U-Boot 2014 stage, one OpenWrt U-Boot 2026 stage,
  and one Linux 6.18.34 start. Both FIT verification paths passed and no fatal
  marker or autonomous restart followed.
- The post-reboot sampler returned 24/24 successful SSH reads on boot ID
  `86a1304c-bc28-474f-83b2-194c479b473c`, with uptime rising from 111.32 to
  231.43 seconds. LuCI and its backend services were healthy.
- No flash or boot-environment write occurred. The V6.58 image remains held
  offline because its clean mt76 build lost `CONFIG_MT76_NPU` and `npu.o`.
  Evidence and hashes:
  `work\live-captures\bootloop-live-20260829\SUMMARY.md`.

## V6.58r1 Build and Live Acceptance Session - 2026-08-29 05:59 +03:00

- Fixed the rejected V6.58 profile-selection regression and completed a clean
  mt76 compile plus full image build with both NPU Kconfig symbols and `npu.o`.
- Accepted and flashed image SHA256:
  `a44307d24583e874a4987fb357adc85d95961d2e9315b7f06ab7dc6d819ea3ed`.
- Offline verification passed. Exact-module and symbol-rich Ghidra analyses
  completed, with all 17 shared loadable sections matching byte-for-byte.
- Post-flash WiFi tests passed 37/37. The corrected mode-3 TXFREE run passed
  40/40, exercised seven malformed descriptor cases without token leakage,
  and completed two module reloads without a kernel fatal marker.
- Restored plain mode 0/topology N and the original wireless UCI. Full report:
  `work\W1700K_V6.58R1_TXFREE_LIVE_ACCEPTANCE_20260829.md`.

## V6.58r1 Immediate Boot-Loop Recheck - 2026-08-29 06:05 +03:00

- Monitored the user-reported loop over both Ethernet and COM3. All 18 SSH/ICMP
  samples stayed on boot ID `eb8b9b8f-2b23-4915-aad2-adc031d32831`; uptime
  increased from 459.05 to 547.97 seconds.
- Passive UART remained empty for 120 seconds. Sending Enter afterward returned
  the normal root shell prompt. No current-boot fatal marker or pstore record
  existed, and memory/load were healthy.
- No flash, reboot, service restart, module reload, or configuration change was
  made. Evidence:
  `work\router-tests\bootloop-check-20260829-060251\SUMMARY.md`.

## V6.58r1 Duplicate-Address Recheck - 2026-08-29 06:22 +03:00

- Repeated the reported boot-loop check with 24 Ethernet-bound SSH samples.
  One boot ID remained active, uptime increased from 1362.76 to 1484.62
  seconds, and `uhttpd` stayed running.
- The COM3 shell returned the same boot ID at uptime 1510.22. Fatal-log and
  pstore checks were empty, and available memory exceeded 1.68 GB.
- Recorded a host-side address collision: Ethernet and Wi-Fi each have a
  different device at `192.168.1.1`. Bound Ethernet reaches the W1700K; Wi-Fi
  reaches another router. This explains unreliable unbound browser results
  without any board reset.
- Left firmware and router state untouched. Evidence:
  `work\router-tests\bootloop-live-20260829\SUMMARY.md`.

## V6.59r2 ACK-SN and Helper-ABI Live Session - 2026-08-29 07:50 +03:00

- Reconciled the helper and LuCI against the exact shipped `mt7996e.ko` ABI,
  retained superseded controls as explicit status-only entries, and added
  root/non-root regression fixtures.
- Reverse engineered the remaining stock ACK-SN mailbox choice in Ghidra and
  implemented a guarded W1700K selector-1 send after OpenWrt's normal
  selector-3 send. Strict checkpatch, clean mt76 compile, full image build,
  exact FIT/rootfs/module inspection, and 83/83 offline checks passed.
- V6.59r1 live testing exposed a helper permission-classification defect:
  root made `[ -w ]` true for a `0444` sysfs node. V6.59r2 checks owner-write
  mode bits, and both fixtures plus live status now correctly report the
  ACK-SN selector and stock topology as reboot-only.
- Flashed V6.59r2 SHA256
  `efabd59f09de0aeda8a258b7927aeb1c63b901823e49664cde54165e7d253957`.
  Mode 0 independent-radio and tri-band MLO fixtures passed. Mode 3 reported
  ACK-SN attempts/successes/failures `1/1/0`, two balanced transport slots,
  active valid IRQs, and tri-band MLO `AP-ENABLED` on all links.
- Restored the exact wireless baseline and plain mode 0. Final boot ID is
  `9b98c378-e4db-46b6-926d-d9a58a7eb878`; LuCI HTTP/HTTPS return 200, pstore
  is empty, memory is healthy, and all fatal scans are empty.
- Report:
  `work\W1700K_V6.59R2_ACK_SN_LIVE_ACCEPTANCE_20260829.md`.
- Promoted bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.59r2-ACKSN-Live-20260829`.

## V6.59r2 Boot-Loop Recheck - 2026-08-29 08:08 +03:00

- The reported loop did not reproduce. COM3 returned the existing OpenWrt
  shell, and 12 Ethernet-bound SSH samples stayed on boot ID
  `9b98c378-e4db-46b6-926d-d9a58a7eb878` with monotonically increasing uptime.
- Pstore and fatal-log scans were empty. UBI, overlay, memory, LuCI, networking,
  SSH, and all three physical radios were healthy.
- Reconfirmed the Windows address collision: Ethernet and Wi-Fi reach distinct
  MAC addresses at `192.168.1.1`. The W1700K was tested only through bound
  Ethernet source address `192.168.1.224`.
- No flash, reboot, module/service operation, or persistent mutation occurred.
  Evidence: `work\router-tests\bootloop-20260829-080205\SUMMARY.md`.

## V6.59r2 Current Packet-Path Session - 2026-08-29 08:19 +03:00

- Entered guarded mode 3 with stock topology, ran the 40-test radio/MLO suite,
  and passed all checks.
- Injected 128 monitor frames through the real TX/NPU path. Every ownership
  stage advanced by 128, all checked error invariants remained unchanged, and
  the token count returned to baseline.
- Passed two mode-3 module reload cycles. COM3 captured exactly the requested
  mode-3 and restore boots with no fatal signature.
- Restored plain mode 0, topology N, wireless SHA
  `588a3e98ee05a0d8649c392c54c4e879ac74230c1ed34a2134f07649e2aa945c`,
  zero recovery hooks/test interfaces, empty pstore, and working LuCI.
- No source or image change was made. Report:
  `work\W1700K_V6.59R2_CURRENT_PACKET_PATH_ACCEPTANCE_20260829.md`.

## V6.59r2 Hardened Stock-Copy Session - 2026-08-29 08:46 +03:00

- Added missing remap/TXP-token and bounded-lag assertions to the host-side
  stock-copy stress probe; static checks passed.
- The exact V6.59r2 image then passed three 40-test workloads. All 54 requests
  produced confirmed firmware remaps and consumer completions; the expected
  asynchronous local-TXFREE lag stayed at one, host ownership returned to zero,
  and every hardened error counter remained zero.
- Two module reloads and two requested COM3-captured physical boots completed
  without a fatal marker.
- Restored mode 0/topology N/stock-copy N, the exact wireless baseline, zero
  fallback/test/pstore artifacts, healthy memory, and LuCI HTTP/HTTPS 200.
- No image rebuild was needed. Report:
  `work\W1700K_V6.59R2_STOCK_COPY_HARDENED_ACCEPTANCE_20260829.md`.

## V6.59r2 TXFREE Fault Session - 2026-08-29 09:00 +03:00

- Ran the exact V6.59r2 image through the guarded mode-3 malformed-TXFREE
  harness with COM3 capture and automatic mode-0 restoration.
- Passed 40/40 radio/MLO checks, all seven malformed descriptor cases, token
  count invariance, and two module reload cycles. No kernel, DMA, UBI, I/O, or
  root-mount fatal marker appeared.
- COM3 recorded only the two requested physical boots. Final state is plain
  mode 0/topology N/stock-copy N, byte-identical wireless UCI, no fallback or
  test interface, empty pstore, healthy memory, and LuCI 200.
- No source/image edit was justified. Genuine duplicate, suppressed, and
  reordered TXFREE completion fate remains open. Report:
  `work\W1700K_V6.59R2_TXFREE_FAULT_ACCEPTANCE_20260829.md`.

## V6.59r2 Genuine TXFREE Replay Session - 2026-08-29 09:13 +03:00

- Added explicit opt-in replay support and fail-closed assertions to the
  host-side mode-3 runner and packet probe; static checks passed.
- The exact image passed 40/40 radio/MLO checks and 128-frame NPU packet-path
  convergence. One genuine TXFREE replay yielded the expected single
  post-release missing-token observation, with no duplicate release,
  finalization mismatch, ownership error, token leak, or fatal diagnostic.
- COM3 captured only the two requested boots; two module reloads passed. Final
  state is boot `5c5c0cdc-9d61-4927-bb68-b32b44636c9f`, plain mode 0,
  topology/copy off, exact wireless baseline, clean pstore, healthy memory, and
  LuCI 200.
- No firmware change was justified. Suppressed/reordered completion and
  sustained RRO/BA stress remain open. Report:
  `work\W1700K_V6.59R2_TXFREE_REPLAY_ACCEPTANCE_20260829.md`.

## V6.59r2 Controlled Boot-Loop Session - 2026-08-29 09:31 +03:00

- Confirmed the existing boot remained stable from 756 through 943 seconds on
  boot ID `5c5c0cdc-9d61-4927-bb68-b32b44636c9f`.
- Captured one requested `sync; reboot` for 150 seconds on COM3. The trace has
  one reset, one stock U-Boot, one OpenWrt U-Boot, one Linux initialization,
  valid FIT hashes, and no fatal or repeated reset marker.
- The apparent duplicate kernel start is the board's normal chainloader path.
  Post-boot ID is `096fa1ad-d44c-4d96-8513-9258cf96a8d9`; LuCI HTTPS is 200.
- No flash, source change, persistent UCI mutation, or bootloader write was
  made. Evidence:
  `work\live-captures\bootloop-check-20260829-092732\SUMMARY.md`.

## V6.60 Build, Flash, and Boot Session - 2026-08-29 10:29 +03:00

- Extended the exact-image TXFREE harness with guarded one-shot suppression and
  successor-before-held reordering. Checkpatch, clean mt76 compile, full image
  build, full Ghidra analysis, and 95/95 offline checks passed.
- Flashed V6.60 SHA256
  `d0b98ea2cedae43df73d3378386dc639288ec8e39b0f49789e4ed66f9dfa4bec`
  after a board check, backup, upload hash check, and `sysupgrade -T`.
- Baseline post-flash tests passed 37/37. COM3 captured one requested
  sysupgrade restart and one normal stock-U-Boot -> OpenWrt-U-Boot -> Linux
  sequence without a fatal marker.
- Nineteen bound-Ethernet samples retained boot ID
  `70b96f74-41af-4a98-9a98-180ffbeaf3d6` while uptime advanced monotonically;
  an additional 120-second passive UART capture remained empty. LuCI,
  networking, memory, pstore, and all physical radios are healthy.
- V6.60 is not promoted yet. Genuine suppression/reordering and RRO/BA pressure
  remain pending. Report:
  `work\W1700K_V6.60_TXFREE_ORDERING_BOOT_ACCEPTANCE_20260829.md`.

## V6.60 TXFREE Ordering Live Session - 2026-08-29 10:45 +03:00

- Ran guarded suppression and reordering separately on the exact flashed
  V6.60 module with stock topology enabled only for each test.
- Suppression withheld one of 128 genuine completions; all shortfalls were
  exactly one and the first PCI teardown reclaimed the outstanding token.
- Reordering held one descriptor, completed its successor first, and returned
  every ownership and token counter to baseline across all 128 frames.
- Each run passed 40/40 radio/MLO checks, the extra probe, and two module reload
  cycles. Both COM3 captures contain only requested mode-entry/restore boots
  and no fatal diagnostic.
- Final state is boot ID `00d32cf8-5a71-4412-af17-c05721daee87`, plain mode 0,
  topology N, exact wireless UCI, no fallback/test artifact, empty pstore, and
  healthy LuCI/network/memory. Report:
  `work\W1700K_V6.60_TXFREE_ORDERING_LIVE_ACCEPTANCE_20260829.md`.

## V6.61 Sustained-Pressure Session - 2026-08-29 11:48 +03:00

- Flashed V6.61 SHA256
  `b2a1004136150258b9a7d9c4ceab18a02b79ecaa0421146972a1c631ebd2ef3b`
  and passed the 37/37 baseline suite.
- The 512-frame guarded mode-3 workload reached 499 genuine TXFREE
  completions. Repeated `GET_MIB_INFO` timeouts then preceded a required
  `BSS_INFO_UPDATE` timeout and terminal WFDMA-busy containment. Linux and SSH
  remained up.
- Reset reclaimed the 13 missing workload tokens plus one pre-existing token.
  The trace also proved ring-pending telemetry and token-recovery attribution
  needed correction. Evidence: `work\router-tests\npu-mode3-20260829-114830`.

## V6.62 Source/Build Session - 2026-08-29 13:14 +03:00

- Implemented MIB survey backoff, timeout snapshots, explicit token-sweep
  accounting, idempotent worker lifecycle handling, corrected ring occupancy,
  and an exported Airoha WLAN snapshot API.
- Both patches pass strict checkpatch. The target, clean mt76, and complete
  image builds pass. Frozen candidate SHA256 is
  `b2227f11c163469460443461a01a0c72c1c9de167c77158d9d3d3b26f79eb300`.
- Exact rootfs comparison found only apk database metadata and the three
  expected mt76 modules changed. Full headless Ghidra kernel/module analysis is
  active; the final pinned offline verifier and all V6.62 live tests remain
  pending. The candidate has not been flashed.

## Boot-Loop Triage Session - 2026-08-29 13:02 +03:00

- Bound all checks to Ethernet source `192.168.1.224`, identifying model
  `Gemtek W1700K (OpenWrt U-Boot layout)` and boot ID
  `20c852bb-605d-48b5-8306-bf86f73fb752`.
- Uptime advanced from 5,049 through 5,355 seconds on that boot ID. SSH, memory,
  load, and pstore were healthy; a 65-second passive COM3 capture was empty.
- No active boot loop was present. No flash, reboot, service, module, or
  persistent configuration mutation was performed. Evidence:
  `work\router-tests\bootloop-triage-20260829-1258\SUMMARY.md`.

## V6.64 Boot-Loop Recheck Session - 2026-08-29 16:13 +03:00

- Rechecked the reported loop through COM3 and the Ethernet-bound W1700K
  endpoint. Boot ID `f9c91626-c0bf-4803-8e5d-d30ea072469f` stayed constant
  through five 15-second samples and the wider 585.41-778.08 second window.
- Passive COM3 remained silent for 60 seconds. Ping, SSH, UBI, LuCI, memory,
  and all three physical radios were healthy; no fatal/reset marker appeared.
- The restored config has no enabled `wifi-iface`, explaining the lack of an
  SSID without implying a boot loop. No router state was changed. Report:
  `work\W1700K_V6.64_BOOTLOOP_RECHECK_20260829.md`.

## V6.66 Management Queue Build/Flash/Live Session - 2026-08-29 18:18 +03:00

- Added a shared normal-DMA PSD management queue on ring 19 and queue-owned
  NPU selection. Strict checks, clean compilation, full image build, FIT/DTB
  audit, contract verification, and full Ghidra module analysis passed.
- Flashed exact image SHA256
  `b021c4fa469ccb983d0fcc3e5a82aa0b936cc478b035224becb5c9019c9d379d`
  after backup and preflight verification.
- Mode 0 and the 40-test mode-3 radio/MLO suite passed. The 512-frame mode-3
  probe achieved exact ownership/TXFREE/token convergence, closing the earlier
  BSS/PSD management-frame routing defect in the operational path.
- Exit cleanup then timed out sending SNIFFER and BAND_CONFIG MCU commands;
  WFDMA containment quiesced the transport before module reload began. The
  harness restored mode 0 with one requested reboot.
- The reported boot loop did not persist. Boot ID
  `2eb46d24-04da-4950-8306-541b2a89f0f6` remained stable, LuCI returned 200,
  about 1.68 GB memory was available, and pstore/current logs were clean.
  Report: `work\W1700K_V6.66_MANAGEMENT_QUEUE_LIVE_STATUS_20260829.md`.

## V6.67 Ring-Depth Build/Flash/Correction Session - 2026-08-29 21:02 +03:00 (Retracted Geometry)

- Built and flashed the mt76 512/1024 ring-depth image, exact SHA256
  `13614e43343dab01c2546cbff58586f4a9a2010c42d9f968a1714c79c8795d73`.
  The guarded flash and 37-test mode-0 baseline completed with zero failures.
- A guarded 511-frame mode-3 control stopped before injection. Airoha rejected
  group 0's 512 descriptors because its synchronization patch still required
  `0x400` for both groups; mt7996 probe failed with `-22` and no AP appeared.
- The runner safely returned the router to persistent mode 0 on boot ID
  `4f7d31b1-7f64-4822-b62c-646630d35727`.
- The temporary Airoha `0x200/0x400` host-adapter edit and its first verifier
  are retracted. The later stock-table proof and replacement verifier are the
  authoritative state. No rebuilt FIT or second flash is claimed. Report:
  `work\W1700K_V6.67_RING_DEPTH_LIVE_STATUS_20260829.md`.

## V6.67 Ring-Domain Correction Session - 2026-08-29 22:28 +03:00

- Reconciled the failed V6.67 probe against stock `hostadpt.ko`, NPU firmware,
  Airoha provider registers, and the exact 512-frame live snapshot. The former
  `512/1024` host-adapter interpretation is retracted.
- Stock host-adapter TX descriptor geometry is `1024/1024`. The separate 512
  wrap occurs in the firmware-private/downstream WFDMA group-0 producer path;
  the failing capture had host-adapter `cpu=dma=512` and pending 0, but
  downstream WFDMA `cpu=0`, `dma=512`, and max count 1024 immediately before
  MCU transport timeout.
- Headless Ghidra exported stock `set_tx_max_cnt`,
  `chip_init_hw_ring_setting`, and `hwifi_init_hw_ring_setting`, plus xrefs for
  `set_tx_max_cnt` and the `mtk_pci.ko` raw BAR writer. `set_tx_max_cnt`
  defaults to 1024 but is a proc/configuration-field setter, not yet proof of
  the downstream MMIO initialization value.
- The attempted Airoha `512/1024` source edit, interrupted rebuild, and first
  verifier are quarantined from promotion. No build or flash occurred in this
  correction session.

## Stock Downstream Ring Proof and Source Patch - 2026-08-29 23:22 +03:00

- Corrected ELF address handling for stock `mt7990.ko`: the large `.rodata`
  section begins at Ghidra `0x101d60`, so section-relative symbols must be
  added to that block start. Earlier dumps at image-base-plus-symbol landed in
  embedded firmware bytes and were discarded.
- Decoded `txq_wa_layout` at `0x6083c0` and
  `txq_wa_layout_pcie1` at `0x607ef0`. The exact stock entries are:
  `band0 TXD`, base `0xd4420`, `q_size=0x200`; and `band2 TXD`, base
  `0xd8450`, `q_size=0x400`.
- Reconciled those entries with `mtk_pci.ko`: its generic queue initializer
  takes `q_size` from chip-config offset `+0x1c` and writes it to
  `ring_base + 4`. The downstream WFDMA `512/1024` geometry is therefore
  proven independently of host-adapter `1024/1024`.
- Added
  `work\9999zzzzzzzzzzzz32-mt76-match-stock-downstream-wfdma-ring-depth.patch`
  and mirrored it into the WSL source. It adds a W1700K group-0-only marker
  and changes only the direct WFDMA max-count write.
- Found that OpenWrt's patch helper had continued applying patch 31 despite
  the `.patch.rejected` suffix. Moved it outside the active patch directory,
  cleaned mt76, and proved a fresh prepare applies patch 32 without patch 31.
- Updated `tools\verify_w1700k_ring_depth_contract.py`; all four tests and the
  JSON contract gate pass. Compile and live work remain pending. No image or
  router state changed in this session.

## V6.68 Downstream WFDMA Build Session - 2026-08-29 (Post-Proof Build)

- Rebuilt the target kernel to restore a valid module-enabled generated
  configuration, then compiled mt76 with patch 32. `mt76.ko` and
  `mt7996e.ko` linked successfully.
- Audited the produced objects and the copies embedded in the squashfs. The
  mt76 code contains the guarded `512` WFDMA max-count write behind bit 10;
  mt7996 group 0 carries the combined `0x600` queue flags only on the proven
  W1700K stock-topology path.
- The initial full build failed at package install because WSL inherited a
  relative Windows PATH fragment (`Files/Common`). The Linux-only PATH retry
  passed and generated the W1700K sysupgrade FIT.
- Image SHA256:
  `d2861fe1a208a4de681bf0fe028b5fe581c9bbf09bd2550c7a28b7428f2b19e8`.
  FIT and extracted-rootfs checks passed; stock proprietary kernel modules are
  absent and the expected OpenWrt WiFi/NPU firmware and packages are present.
- No router mutation is claimed in this build session. Live mode and boundary
  tests remain pending. Report:
  `work\W1700K_V6.68_DOWNSTREAM_WFDMA_BUILD_STATUS_20260829.md`.

## V6.68 Downstream WFDMA Flash and Live Session - 2026-08-29 23:54 +03:00

- Flashed exact V6.68 image SHA256
  `d2861fe1a208a4de681bf0fe028b5fe581c9bbf09bd2550c7a28b7428f2b19e8`;
  live mt76 and mt7996e hashes match the audited image.
- Corrected the EHT160 test contract so a legal DFS/radar move between full
  US 160 MHz blocks remains valid. Mode 0 then passed 37/37 checks.
- Added guarded fail-closed runners for unsupported modes. Modes 1 and 2 each
  loaded only for diagnostics, kept the NPU transport `inactive-clean`, passed
  36/36 WiFi/MLO checks, and restored exact mode 0.
- Generalized the mode-3 runner to execute multiple distinct frame counts in
  one guarded boot. PowerShell parsing, array serialization, and shell syntax
  passed before use.
- Two complete mode-3 runs passed 40/40 checks, exact 511/512/1024 frame
  ownership/TXFREE/token convergence, and two module reload cycles. Every
  critical per-burst delta exactly equaled the requested count; all checked
  invalid/missing/duplicate/mismatch counters remained zero.
- The second run had continuous COM3 coverage. It captured exactly two
  requested boots, correct W1700K identity, mode-3 topology activation, NPU
  firmware `0.1111`, and no fatal marker. COM3 released cleanly afterward.
- Final state is boot ID `b49a2865-982b-4b57-b1f5-75d1627ca765`, mode 0,
  topology N, exact wireless hash, healthy LuCI/rpcd/memory, and no fallback.
- V6.68 is accepted for the split-domain WFDMA scope. Report:
  `work\W1700K_V6.68_DOWNSTREAM_WFDMA_LIVE_ACCEPTANCE_20260829.md`.

## V6.69 Live WFDMA Observability Build Session - 2026-08-30 00:20 +03:00

- Added patch 33 as a diagnostics-only follow-up to V6.68. The parity map now
  reads downstream WFDMA `ring_size` live and reports exact expected/live
  512/1024 values. Token telemetry now states its observed-window versus
  global-IDR scope and exports the unobserved net contribution.
- `checkpatch`, patch application, 8 focused tests, clean mt76 compile, and the
  full image build passed.
- Full Ghidra analysis of the unstripped `mt76.ko` confirmed the compiled MMIO
  load at queue-register offset `+4`, the read barrier, expected-value compare,
  and new token fields.
- Candidate image SHA256 is
  `f319e067b9d1fa1d8a0b79dcd83e14df7821ddc8c18d2cb9da65c36fcd8fade9`.
  Offline FIT/rootfs comparison found no payload change outside `mt76.ko` and
  generated APK database metadata. Live work is not yet claimed. Report:
  `work\W1700K_V6.69_LIVE_WFDMA_OBSERVABILITY_BUILD_STATUS_20260830.md`.

## V6.69 Flash, Mode-3 Readback, And Promotion Session - 2026-08-30 00:38 +03:00

- Guarded preflight identified the Ethernet-bound target as
  `gemtek,w1700k-ubi`, pinned its existing host key, backed up configuration,
  verified the upload, passed `sysupgrade -T`, and flashed exact image SHA256
  `f319e067b9d1fa1d8a0b79dcd83e14df7821ddc8c18d2cb9da65c36fcd8fade9`.
- Post-flash mode 0 passed 37/37 synthetic checks. The original wireless UCI
  file was restored byte-for-byte and the live module hashes match the image.
- Guarded mode 3 passed 42/42 checks. Live queue-register reads returned
  group-0 `512` for bands 0/1 and group-1 `1024` for band 2, with all validity
  and match fields set and the aggregate topology verdict equal to 1.
- Distinct 511/512/1024-frame probes each produced exact requested deltas for
  payload, token allocation, enqueue, consumer, SKB-shadow publish/cleanup,
  token release, and classified TXFREE. Invalid, missing, duplicate, mismatch,
  and stale paths remained zero; every probe reported zero failures.
- Explicit token-scope output identified the legacy telemetry window versus
  global IDR population. The observed window remained balanced at zero while
  one pre-existing unobserved token remained stable through every probe; the
  first clean module reload reduced the global count to zero and the second
  left it at zero.
- COM3 capture recorded exactly three requested W1700K Linux boots: V6.69
  flash, mode-3 entry, and mode-0 restoration. The middle boot and both module
  reloads completed stock-topology NPU `0.1111` handshakes. No panic, Oops,
  sanitizer, DMA-API, watchdog-expiry, corruption, or OOM marker was found.
- Added `tools\verify_w1700k_v669_live.py`; its hash-pinned replay reports
  `PASS_V669_LIVE_ACCEPTANCE` and writes the retained result JSON under the
  mode-3 test directory.
- Fresh final health remained on boot ID
  `9648041b-804f-43a8-96ba-e04cabc8934e`, mode 0/topology N, exact wireless
  hash, 1,685,148 kB available memory, running LuCI/rpcd, validator exit 0,
  and an empty fatal scan.
- V6.69 is promoted as the live-accepted observability image. Report:
  `work\W1700K_V6.69_LIVE_WFDMA_OBSERVABILITY_LIVE_ACCEPTANCE_20260830.md`.

## V6.69 Release Freeze Session - 2026-08-30 00:43 +03:00

- Created the verified FinalResult bundle at
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.69-Live-WFDMA-Observability-20260830`.
- The retained 49-file payload totals 26,337,071 bytes and includes the exact
  image, patch, reports, trackers, build/Ghidra evidence, live mode-0/mode-3
  evidence, serial capture, and reproduction tools.
- Replayed both generated hash inventories with zero failures. Excluded the
  potentially sensitive sysupgrade backup and found no credential payload
  marker in retained content.

## V6.70 Negotiated EHT NSEP Build Session - 2026-08-30 01:45 +03:00

- Completed the stock EHT NSEP/EPCS comparison and implemented patch 34 with a
  local-and-peer capability gate, default-on read-only module policy, and
  debugfs negotiation accounting. Full Ghidra analysis of the rebuilt
  symbol-rich `mt7996e.ko` succeeded and selected decompilation confirmed the
  intended gate and counters.
- Added diagnostics-only patch 35 and kernel patch 76 to remove stale status
  contradictions without relabeling any genuinely unresolved scatter,
  SKB/bufid, or RRO boundary.
- Fixed helper persistence of explicit mode-0 `stock_eht_nsep=0`; the LuCI
  wording now states that NSEP requires peer EPCS and the probe-time option
  requires reboot.
- Clean kernel and mt76 builds passed. The versioned full-image build exited
  `0`; `tools\verify_w1700k_v670_source.py` reports
  `PASS_V670_SOURCE_CONTRACT` and
  `tools\verify_w1700k_v670_candidate.py` reports
  `PASS_V670_CANDIDATE`.
- Exact candidate SHA256 is
  `c076d8501f8f4cfce2442dee08effc7d57be49e18e7197355d77d1ff3ce08998`.
  Its DTB, rootfs shape, 189-package manifest, and four OpenWrt NPU firmware
  blobs match the accepted contract. The V6.69-to-V6.70 rootfs delta is only
  APK bookkeeping, `mt76.ko`, `mt7996e.ko`, the NPU helper, and its LuCI view.
- No router mutation is claimed by this session. V6.69 remains live accepted;
  V6.70 requires guarded mode 0/mode 3 validation after flashing. Report:
  `work\W1700K_V6.70_EHT_NSEP_NEGOTIATION_OFFLINE_CANDIDATE_20260830.md`.

## V6.70 Flash And Live Acceptance Session - 2026-08-30 02:08 +03:00

- Confirmed the Ethernet-bound endpoint was the W1700K on accepted V6.69 mode
  0, preserved its configuration, verified exact image SHA256, passed the
  router's image test, and flashed V6.70.
- The mode-0 unattended suite passed 37/37 WiFi/MLO/validation/service checks
  and restored the original wireless file byte-for-byte.
- Verified the new live ABI: read-only enabled `stock_eht_nsep`, nine EPCS
  capability advertisements, local-and-peer negotiation policy, and complete
  zero-peer accounting while no station was associated.
- Guarded stock-topology mode 3 passed 42/42, exact 511/512/1024-frame
  lifecycle probes, live 512/512/1024 downstream-WFDMA readback, and two PCI
  module reload cycles. Automatic restoration returned to bare mode 0.
- COM3 recorded exactly the three requested boots and all expected NPU
  handshakes with no fatal marker. Final health pinned exact live payload
  hashes, 1,684,516 KiB available memory, all expected services, zero bad UBI
  PEBs, clean validation, and an empty fatal scan.
- Added `tools\capture_w1700k_v670_final_health.py` and
  `tools\verify_w1700k_v670_live.py`; the hash-pinned replay reports
  `PASS_V670_LIVE_ACCEPTANCE`.
- V6.70 is promoted for the tested router-only scope. Real peer-supported NSEP
  and comparative client MLO throughput remain user-attended boundaries.
  Report:
  `work\W1700K_V6.70_EHT_NSEP_NEGOTIATION_LIVE_ACCEPTANCE_20260830.md`.

## V6.70 Release Freeze Session - 2026-08-30 02:12 +03:00

- Added `tools\package_w1700k_v670_release.ps1` and froze the accepted release
  under `FinalResult\W1700K-V6.70-EHT-NSEP-Negotiation-20260830`.
- The first packaging run correctly failed manifest replay because a
  single-quoted format string emitted a literal backtick-t. The generator was
  fixed, the malformed attempt was moved to `work\rejected-bundles`, and the
  clean bundle was generated from unchanged evidence.
- The accepted bundle has 71 payload files totaling 27,027,393 bytes. Both
  71-line inventories replay with zero failures; the credential-payload scan
  has zero matches and the configuration backup is absent.
- A direct FinalResult image and one-line SHA256 file were also generated. The
  accepted image hash remains
  `c076d8501f8f4cfce2442dee08effc7d57be49e18e7197355d77d1ff3ce08998`.

## V6.71 RRO Lifecycle Observability Build Session - 2026-08-30 03:31 +03:00

- Implemented patch 36 as a constrained observability and reset-coordination
  follow-up. It maps the existing OpenWrt scatter, SKB/BufID, token, page-pool,
  refill, BA-window, and session lifecycles into explicit counters without
  changing packet ownership or clamping RRO processing.
- Added dedicated locking for the session map, a bounded five-interval RRO
  drain wait before session reset, restored `wed-rro-status`, and made the NPU
  helper fail closed unless all 45 required debugfs fields are present.
- Strict checkpatch passed with zero findings. Clean mt76 compilation, seven
  JavaScript checks, seven JSON parses, 23 shell syntax checks, warning-level
  ShellCheck, NPU fixtures, and the negative capture test passed.
- The 6,415-file patch audit found zero structural issues in all 199
  active/local and 323 disabled experimental W1700K patches. The 111 findings
  are confined to untouched upstream patches.
- Full Ghidra ELF/DWARF analysis processed 453 mt76 and 660 mt7996e functions.
  Selected decompilation confirmed the checked token, fault, reset-wait, MCU,
  session-map, and status-output paths. `PASS_V671_GHIDRA` and
  `PASS_V671_SOURCE_CONTRACT` both pass.
- The full image build exited `0`. Exact candidate SHA256 is
  `70556ba3ae8dd9c19bfbcabd5575015e17745e24da4826ec92153968e8a56197`;
  `tools\verify_w1700k_v671_candidate.py` reports
  `PASS_V671_CANDIDATE`.
- The candidate is 20,632,380 bytes with 64,708 bytes of real FIT headroom.
  It is 4,096 bytes larger than V6.70 and below the old 64-KiB warning margin
  by 828 bytes, but still fits the actual fixed volume.
- The kernel and DTB are unchanged. Rootfs shape is unchanged and exactly six
  files differ: two APK database files, three mt76/mt7996 modules, and the NPU
  helper. LuCI, packages, NPU firmware, and forbidden-module policy remain
  unchanged.
- No router command, upload, reboot, or flash was issued. V6.70 remains the
  live-accepted baseline; V6.71 remains offline pending explicit authorization
  and guarded mode 0/mode 3 validation. Report:
  `work\W1700K_V6.71_RRO_OBSERVABILITY_OFFLINE_CANDIDATE_20260830.md`.

## V6.71 Offline Candidate Freeze Session - 2026-08-30 03:37 +03:00

- Added `tools\package_w1700k_v671_offline.ps1` and froze V6.71 under a
  deliberately explicit `OFFLINE-UNFLASHED` bundle and image name.
- The retained 37-file payload totals 33,409,247 bytes and includes the exact
  candidate, patch, full build and compile logs, source/candidate/Ghidra
  contracts, patch audit, analyzed modules, decompilation reports, verifiers,
  packaging tool, report, and tracker snapshots.
- Replayed both 37-record inventories with zero failures. The retained-text
  credential scan has zero matches and no configuration backup is present.
- The bundle marker states that live mode 0/mode 3 testing has not happened.
  This freeze does not promote V6.71 or change the live V6.70 router state.

## V6.72 RXDMAD-C Ownership Analysis/Build Session - 2026-08-30 04:38 +03:00

- Re-decompiled stock `mtk_pci.ko` RRO functions and the stock `mt_wifi.ko`
  token-provider helpers. The recovered RXDMAD-C consumer validates provider
  state and physical address before moving token ownership; invalid reports
  leave ownership unchanged.
- Added an ownership invariant matrix and 16-case executable model. It
  identifies seven V6.71 divergence cases and proves zero V6.72 divergence,
  36-bit descriptor-DMA reconstruction, retained stale reports, accepted
  later-correct reports, and missing duplicate reports after consumption.
- Authored patch 37 with strict no-fuzz application and checkpatch result
  `0 errors, 0 warnings, 0 checks` over 140 lines. The patch uses the native
  mt76 IDR/page-pool model and deliberately does not transplant stock's
  incompatible explicit free-list or DMA-unmap sequence.
- Clean mt76 clean/prepare/compile stages all exited 0 with zero compiler
  diagnostics. The source contract pins the exact rebuilt unstripped modules
  and verifies validation/removal ordering plus all debugfs counters.
- Full Ghidra ELF/DWARF analysis covered 452 mt76 and 653 mt7996e functions.
  All 13 selected functions decompiled. Ghidra confirms four descriptor DMA
  high bits, a 21-queue checked-release call, invalid-result branching before
  queue dereference, and DMA comparison before `idr_remove`.
- Static tests passed. The 6,416-patch audit reports zero structural findings
  in all 200 active/local and 323 disabled experimental W1700K patches; all
  111 findings are in untouched upstream patches.
- Full image build and exact candidate verifier passed. Candidate SHA256 is
  `1697e07d44267e0562bb2aa0ba20d305734b6da8addaf6aeefd06cff21868ce6`,
  size is `20,632,380`, and fixed-volume headroom is `64,708` bytes.
- WSL ext4 rootfs comparison found identical shape and exactly five changed
  files: two APK database files and the three mt76-family modules. Kernel,
  DTB, LuCI, helper, packages, and four NPU firmware blobs are unchanged; no
  stock proprietary module is present.
- Frozen a 66-payload `OFFLINE-UNFLASHED` bundle with replayed inventories and
  no credential payload or configuration backup. No router operation occurred;
  V6.70 remains live accepted and V6.72 requires explicit flash authorization
  plus guarded live tests.
- Report:
  `work\W1700K_V6.72_RXDMAD_C_OWNERSHIP_OFFLINE_CANDIDATE_20260830.md`.

## V6.73 RRO Teardown Regression Analysis/Build Session - 2026-08-30 15:45 +03:00

- Audited patch 36 against stock decompilation and the V6.46 verifier. The
  bounded active drain was a behavioral TOCTOU guard, not passive telemetry,
  and contradicted the earlier evidence-backed boundary.
- Generated fresh Ghidra decompiles for stock `uni_event_rro_del_chk`,
  `hc_init_rro_addr_elem_by_seid`, `RTMP_FREE_RRO_SETBL`, and the NPU provider.
  Stock invalidates synchronously and then performs session cleanup; it has no
  equivalent host-side active-counter wait.
- Added an executable interleaving model. It finds three late NAPI-entry traces
  after a zero observation and seven timeout paths that reset while processing
  remains active. The proposed stock-order/passive-accounting model matches
  the stock core trace set exactly.
- Authored patch 38 and the helper/LuCI delta. Strict checkpatch reports
  `0 errors, 0 warnings, 0 checks`; mt76 clean, prepare, and compile all exit
  zero with no compiler diagnostics.
- Full Ghidra ELF/DWARF auto-analysis processed all 654 recovered mt7996e
  functions. Selected decompilation proves both invalidation alternatives
  precede synchronous MCU reset and that no retired wait survives in machine
  code. `PASS_V673_GHIDRA` and `PASS_V673_SOURCE_CONTRACT` pass.
- The full image build and independent exact candidate verifier pass. Image
  SHA256 is
  `e39fc2a5df5a4b8e5e6b725f71c4f05337823a19c67774799e1510911ee51b5b`,
  size is `20,632,380`, and fixed-volume headroom is `64,708` bytes.
- Side-by-side WSL extraction shows an unchanged kernel, DTB, package set,
  firmware set, and rootfs shape. The five-file delta is APK bookkeeping,
  `mt7996e.ko`, helper, and LuCI. No stock proprietary module is present.
- No live-router operation occurred. V6.70 remains accepted; V6.73 is an
  offline candidate pending explicitly authorized mode 0/mode 3 and radio/MLO
  revalidation.
- Report:
  `work\W1700K_V6.73_RRO_TEARDOWN_REGRESSION_FIX_OFFLINE_CANDIDATE_20260830.md`.

## V6.73 Offline Candidate Freeze Session - 2026-08-30 15:50 +03:00

- Added `tools\package_w1700k_v673_offline.ps1` and froze the exact candidate
  under an explicit `OFFLINE-UNFLASHED` name in `FinalResult`.
- The 54 payload files total 28,769,062 bytes and include the image, source
  deltas, stock and rebuilt Ghidra evidence, model, build logs, verifiers,
  audit inventory, report, and tracker snapshots.
- Independent replay found zero size and hash failures across both 54-record
  inventories. The credential-pattern scan found zero retained matches and no
  router configuration backup is present.
- No router operation occurred and the freeze does not alter acceptance:
  V6.70 remains live accepted; V6.73 remains offline and unflashed.

## V6.74 RRO MSDU-Page DMA Handoff Session - 2026-08-30 16:25 +03:00

- Traced `mt76_create_page_pool()`, `mt76_dma_rx_fill_buf()`,
  `mt7996_rro_msdu_page_add()`, Linux page-pool internals, and local DMA API
  documentation. The RRO callback receives the exact 128-byte fragment span.
- Confirmed the old path wrote the owner bit through a `DMA_FROM_DEVICE`
  persistent mapping after page-pool's device sync. Patch 39 confines
  `DMA_BIDIRECTIONAL` to RRO MSDU page pools and adds CPU/device sync around
  owner publication after successful host bookkeeping allocation.
- Stock Ghidra evidence pins the analogous contract: CPU page population,
  device synchronization, then RRO hash publication. The implementation keeps
  OpenWrt's native page-pool model rather than transplanting stock allocation.
- Clean build and strict source verifier pass. Sparse checks 29 translation
  units with zero diagnostics. The executable non-coherent model shows stale
  owner `0` in the old handoff and visible owner `1` in the fixed handoff.
- Full Ghidra auto-analysis processed 450 mt76 and 654 mt7996e functions.
  Decompilation and exact instruction reports pass `PASS_V674_GHIDRA`.
- Full image build and fresh FIT/rootfs verification pass. SHA256 is
  `057f183aa6389676d08298c5653daaa6a40aefd5f81172e8377d71c9ac2ffb7c`;
  size is `20,632,380`, with `64,708` bytes of fixed-volume headroom.
- Kernel/DTB and rootfs shape are unchanged from V6.73. The four changed files
  are two APK database files, `mt76.ko`, and `mt7996e.ko`. No router command,
  upload, reboot, or flash occurred; V6.70 remains live accepted.
- Report:
  `work\W1700K_V6.74_RRO_MSDU_PAGE_DMA_HANDOFF_OFFLINE_CANDIDATE_20260830.md`.

## V6.74 Offline Candidate Freeze Session - 2026-08-30 16:30 +03:00

- Added `tools\package_w1700k_v674_offline.ps1` and froze the exact candidate
  under an explicit `OFFLINE-UNFLASHED` name in `FinalResult`.
- The retained 62-file payload totals 31,497,021 bytes and includes the image,
  patch/prepared source, stock and rebuilt Ghidra evidence, model, Sparse and
  build logs, verifiers, audit inventory, report, and tracker snapshots.
- Independent replay found zero size and hash failures across both 62-record
  inventories. Credential-pattern scanning found zero retained matches and no
  router configuration backup is present.
- No router operation occurred and the freeze does not alter acceptance:
  V6.70 remains live accepted; V6.74 remains offline and unflashed.

## V6.75 RRO Producer-Session Bound Session - 2026-08-30 17:06 +03:00

- Re-read the active scatter, TX SKB/BufID, RRO ownership, and BA paths against
  current stock decompilation. No safe justification emerged for restoring the
  old explicit stock RX free-list lifecycle or changing the intentional BA
  sentinel and bounded owner-read behavior.
- Isolated a stronger host robustness gap: the wire carries 12 session bits,
  while only normal sessions `0..1023` and sentinel `1024` are legal. The old
  address helper could compute 3071 out-of-bounds group selections for IDs
  `1025..4095` before later integrity checks.
- Authored patch 40 with an early consumer bound, a defensive helper bound,
  invalid-session counters, last-ID capture, and existing integrity/fault
  recovery. Stock trusts this producer field too, so the fix intentionally
  improves on vendor behavior rather than copying its missing check.
- The exhaustive model passes all 4,096 IDs. Strict checkpatch, source/build
  verifier, clean module build, and 29-unit Sparse pass without diagnostics.
- Full Ghidra ELF/DWARF analysis completed for 450 mt76 and 654 mt7996e
  functions. Exact AArch64 reports and stripped embedded-module disassembly
  confirm sentinel-preserving unsigned `b.hi`, invalid counter/ID writes,
  RRO head drop, reason-6 fault report, and direct exit before table lookup.
- Full image build and exact candidate audit pass. SHA256 is
  `86509ed0fbec340c0219283afa533d864e7cd7287a24be223ee5a36303481475`;
  size is `20,632,380`, with `64,708` bytes of fixed-volume headroom.
- Kernel/DTB and rootfs shape are unchanged from V6.74. Only APK bookkeeping
  and `mt7996e.ko` changed; package set, LuCI, helpers, generic mt76 modules,
  and NPU firmware are unchanged. No router operation occurred.
- V6.70 remains live accepted. V6.75 is offline and unflashed; unresolved
  provider-RRO, scatter, SKB/BufID, and runtime validation boundaries remain
  evidence-gated.
- Report:
  `work\W1700K_V6.75_RRO_SESSION_BOUND_OFFLINE_CANDIDATE_20260830.md`.

## V6.75 Offline Candidate Freeze Session - 2026-08-30 17:08 +03:00

- Added `tools\package_w1700k_v675_offline.ps1` and froze the exact candidate
  under an explicit `OFFLINE-UNFLASHED` name in `FinalResult`.
- The 65 retained payload files total 31,866,163 bytes and include the image,
  patch/prepared source, stock and rebuilt Ghidra evidence, exhaustive model,
  Sparse/build logs, verifiers, audit inventory, report, and tracker snapshots.
- Independent replay found zero size and hash failures across both 65-record
  inventories. Credential-pattern scanning found zero retained matches and no
  router configuration backup is present.
- No router operation occurred and the freeze does not alter acceptance:
  V6.70 remains live accepted; V6.75 remains offline and unflashed.

## V6.76 NPU TX Consumer-Bounds Session - 2026-08-30 18:07 +03:00

- Completed the producer-trust audit for host indexes, lengths, queues, tokens,
  and ownership transitions. Non-flush NPU TX cleanup previously converted an
  out-of-range consumer to full-flush sentinel `-1`; an in-range consumer past
  `q->queued` also drained the complete queued prefix.
- Stock Ghidra evidence pins the relevant host-adapter contract to two
  1,024-entry rings, 208-byte stride, and consumer registers `0xac`/`0xbc`.
  Patch 41 applies the wrap-aware `distance <= queued` invariant before host
  ownership changes and leaves empty queues, ordinary queues, and deliberate
  flushes unchanged.
- Patch SHA256 is
  `2a065458b926a0d158ef385922e943c8ca3a0c3c42ef8f7007c78a3a22b0e92c`.
  It adds fault counters/last-state telemetry and routes reason 7 to the
  existing method-8 ownership recovery worker after cleanup unlock.
- The model executes 14,675,196 checks. Source, strict checkpatch, clean and
  prepared mt76, compile, 29-unit Sparse, 450-function mt76 Ghidra,
  654-function mt7996e Ghidra, full image, FIT/rootfs, and aggregate inventory
  gates pass. Status includes `PASS_V676_CANDIDATE` and
  `PASS_V676_AUDIT_INVENTORY`.
- Exact image SHA256 is
  `8d74019a3aa3fdf0db5f8c605662cbdd7851773359872b0bb22a259f76567f82`;
  size `20,632,380`, FIT headroom `64,708`, package count `189`.
- Kernel, DTB, firmware, LuCI, helpers, services, configuration, and rootfs
  shape are unchanged from V6.75. APK bookkeeping plus `mt76.ko`,
  `mt76-connac-lib.ko`, and `mt7996e.ko` differ. The connac change is the
  expected shared-header ABI rebuild: 48 changed bytes in 46 executable ranges
  for a 48-byte `mt76_dev` tail-field shift.
- No router operation occurred. V6.70 remains live accepted and V6.76 remains
  offline/unflashed pending separately authorized exact-image live gates.
- Report:
  `work\W1700K_V6.76_NPU_TX_CONSUMER_BOUNDS_OFFLINE_CANDIDATE_20260830.md`.

## V6.76 Offline Candidate Freeze Session - 2026-08-30 18:10 +03:00

- Prepared the explicit offline bundle and direct image under `FinalResult`.
- The 70 retained payload files total 31,244,056 bytes and include the exact
  image, patch, source snapshots, model, stock and rebuilt Ghidra evidence,
  compile/Sparse/image logs, verifiers, report, and tracker snapshots.
- Independent replay found zero failures in both generated inventories.
  Credential-pattern scanning returned zero retained matches, and no router
  configuration backup is included.
- No router operation occurred and the freeze does not alter acceptance:
  V6.70 remains live accepted; V6.76 remains offline and unflashed.

## V6.77 NPU TX Owner-Gate Session - 2026-08-30 18:52 +03:00

- Compared the current producer path, the earlier live-tested owner-gated
  implementation, and stock `hostadpt_tx_handler`. Patch rebasing had retained
  stock's five-entry headroom but dropped the current-descriptor owner test.
- Patch 42 restores that test before payload mapping and token allocation,
  returns `-EBUSY` for NPU-owned descriptors, and exposes the rejection count
  in both NPU debugfs views and the abnormal-TX aggregate.
- The 2,097,152-check model reduces old owner-overwrite admissions from
  1,043,456 to zero with zero stock-model mismatches. Source, inherited V6.76,
  checkpatch, compile, 29-unit Sparse, full image, exact FIT/rootfs, and audit
  inventory gates pass.
- Full Ghidra analysis processed 1,288 exact-build functions across mt76,
  connac, and mt7996e. Instruction evidence confirms owner-bit rejection and
  `-EBUSY` unwind occur before payload DMA mapping while the publication
  barrier and method-8 recovery remain.
- Exact image SHA256 is
  `d96507117d22629b6e2447b2b55062ec080556d76ecfde0839df9edac218aeed`;
  size `20,632,380`, FIT headroom `64,708`, package count `189`.
- No router operation occurred. V6.70 remains live accepted; V6.77 remains
  offline/unflashed and closes only the descriptor-owner admission boundary.
- Report:
  `work\W1700K_V6.77_NPU_TX_OWNER_GATE_OFFLINE_CANDIDATE_20260830.md`.

## V6.77 Offline Candidate Freeze Session - 2026-08-30 18:58 +03:00

- Added `tools\package_w1700k_v677_offline.ps1` and the canonical explicit
  `OFFLINE-UNFLASHED` bundle/direct-image names under `FinalResult`.
- The 72-record payload includes the image, both relevant patches, prepared
  source, exhaustive model, build/Sparse/Ghidra evidence, verifiers, report,
  and all three tracker snapshots.
- Packaging pins the exact image hash, replays generated size/hash inventories,
  rejects output overwrites, scans retained text for credential patterns, and
  includes no router backup.
- No router operation occurred and acceptance is unchanged: V6.70 remains live
  accepted; V6.77 remains offline and unflashed.

## V6.78 NPU TXWI DMA Handoff Session - 2026-08-30 20:44 +03:00

- Closed a native NPU TX streaming-DMA ownership defect: CPU inline-TXWI copy
  and token inspection previously happened after the reusable `DMA_TO_DEVICE`
  mapping had been returned to device ownership on a non-coherent platform.
- Patch 43 moves only the NPU success-path sync into the enqueue helper after
  all CPU reads and before the existing publication barrier/owner store. The
  ordinary queue and prepare-failure sync behavior remains intact.
- The complete order model, source verifier, inherited V6.77/V6.76 contracts,
  strict checkpatch, clean build, 29-unit Sparse, full image build, exact
  FIT/rootfs verifier, and aggregate audit inventory pass.
- Full Ghidra analysis processed 1,288 exact-build functions. Machine and
  decompile checks prove the non-coherent sync branch rejoins before `dmb
  OSHST` and owner publication, with prior ownership and recovery fixes intact.
- Exact image SHA256 is
  `da2c79874d6ba074d37f9dd6401ebbcecaf446a8a6adbd053160467b6959541c`;
  size `20,632,380`, FIT headroom `64,708`, package count `189`.
- Kernel/DTB and rootfs shape are unchanged from V6.77. Exactly three files
  differ: APK `installed`, APK `scripts.tar.gz`, and `mt76.ko`. Connac,
  mt7996e, LuCI/configuration, and NPU firmware remain unchanged.
- No router command, upload, reboot, or flash occurred. V6.70 remains live
  accepted; V6.78 is offline/unflashed pending separately authorized runtime
  validation.
- Report:
  `work\W1700K_V6.78_NPU_TXWI_DMA_HANDOFF_OFFLINE_CANDIDATE_20260830.md`.

## V6.78 Offline Candidate Freeze Session - 2026-08-30 20:49 +03:00

- Added `tools\package_w1700k_v678_offline.ps1` and froze the canonical
  explicit `OFFLINE-UNFLASHED` bundle and direct image under `FinalResult`.
- The 78 retained payload files total 33,024,156 bytes and include the image,
  patch lineage, prepared source, model, build/Sparse/Ghidra evidence,
  verifiers, report, and all three tracker snapshots.
- Independent size and SHA256 replay passed all 78 records in both inventories.
  Credential-pattern scanning returned zero matches and no router backup is
  included.
- No router operation occurred and acceptance is unchanged: V6.70 remains live
  accepted; V6.78 remains offline and unflashed.

## V6.79 NPU RX Refill Publication Session - 2026-08-30 21:20 +03:00

- Found a native NPU RX ownership defect: all dequeue exits published the host
  consumer before the poll path refilled consumed descriptors. The rotating
  reserve could therefore become NPU-visible without a rebuilt replacement
  buffer.
- Stock Ghidra evidence establishes replacement allocation/map, address update,
  owner clear, SKB bookkeeping, barrier, consumer advance, then register write.
  Patch 44 now follows the same ownership order and uses `head + 1` to support
  safe partial refill without publishing when allocation returns zero.
- The 67,239,424-state model, strict checkpatch, current and inherited source
  contracts, clean compile, all 29 Sparse units, full image, exact FIT/rootfs,
  and aggregate static tests pass. Ghidra fully analyzed 1,287 exact-build
  functions and passed 33 source-correlated decompile/instruction checks.
- Exact image SHA256 is
  `6d9d831bdd38d42a9028f10e9851cc39f93ca10ebca9f78cc4b4489d9c104457`;
  size `20,632,380`, FIT headroom `64,708`, package count `189`.
- Compared with V6.78, only APK bookkeeping and `mt76.ko` differ. Kernel, DTB,
  connac, mt7996e, LuCI/configuration, services, and NPU firmware are unchanged.
- No router command, upload, reboot, or flash occurred. V6.70 remains live
  accepted; V6.79 is offline/unflashed pending separately authorized runtime
  validation.
- Report:
  `work\W1700K_V6.79_NPU_RX_REFILL_PUBLICATION_OFFLINE_CANDIDATE_20260830.md`.

## V6.79 Offline Candidate Freeze Session - 2026-08-30 21:24 +03:00

- Added `work\package_w1700k_v679_offline.ps1` and froze the canonical
  explicit `OFFLINE-UNFLASHED` bundle and direct image under `FinalResult`.
- The 82 retained payload files total 33,226,548 bytes and include the image,
  patch lineage, prepared source, model, build/Sparse/Ghidra evidence,
  verifiers, report, and all three tracker snapshots.
- Independent size and SHA256 replay passed all 82 records in both inventories.
  Credential-pattern scanning returned zero matches and no router backup is
  included.
- No router operation occurred and acceptance is unchanged: V6.70 remains live
  accepted; V6.79 remains offline and unflashed.

## V6.79 Independent Bundle Replay Session - 2026-08-30 21:27 +03:00

- Added `work\verify_w1700k_v679_bundle.py` and independently replayed the
  frozen bundle into `work\build-v6.79-20260830\bundle-verification.json`.
- `PASS_V679_BUNDLE_REPLAY` covers 82 manifest records, 82 SHA256 records,
  all 84 physical files, the direct image, bundled image, top-level checksum,
  and offline marker with zero failures.
- No router access or mutation occurred. V6.70 remains live accepted and V6.79
  remains an offline/unflashed candidate.

## V6.80 NPU RX Scatter-Reuse Session - 2026-08-30 22:04 +03:00

- Compared the current NPU RX scatter path with stock `hostadpt_rx_handler`.
  Stock copies scatter payloads into a fresh linear SKB while retaining the
  original DMA-backed fragment buffers; V6.79 released and replaced them.
- Patch 45 adds validated rotating-reserve reuse, device-sync-before-rearm,
  source descriptor clearing, preserved queue occupancy, allocation-drop
  reuse, explicit RX-ring fault telemetry, and three reuse counters. Its SHA256
  is `3a05d387a38f33d89b93363b10b1036c9f08717c46bbec62b2cef2cde72064eb`.
- The model executes 76,567,321 states and reports zero invariant failures.
  Old allocation churn is 43,485,184 modeled fragments; fixed churn is zero.
- Source, inherited contracts, strict checkpatch, clean prepare/compile,
  29-unit Sparse, full Ghidra, full image, FIT/rootfs, and aggregate static
  gates pass. Ghidra processed 1,283 exact-build functions and passed 39
  source-correlated machine/decompile checks.
- Exact image SHA256 is
  `000c1e1d1f7111141f33e65feaabf384eb4a9b54d517b589f9d12922659c0a4b`;
  size `20,632,380`, FIT headroom `64,708`, package count `189`.
- Kernel, DTB, firmware, LuCI, helpers, services, configuration, and rootfs
  shape are unchanged from V6.79. APK bookkeeping plus the three mt76-family
  modules differ as expected.
- No router operation occurred. V6.70 remains live accepted and V6.80 remains
  offline/unflashed pending separately authorized exact-image live gates.
- Report:
  `work\W1700K_V6.80_NPU_RX_SCATTER_REUSE_OFFLINE_CANDIDATE_20260830.md`.

## V6.80 Offline Candidate Freeze Session - 2026-08-30 22:07 +03:00

- Added `work\package_w1700k_v680_offline.ps1` and froze the canonical
  explicit `OFFLINE-UNFLASHED` bundle and direct image under `FinalResult`.
- The 84 retained payload files total 33,194,461 bytes and include the image,
  patch lineage, prepared source, model, build/Sparse/Ghidra evidence,
  verifiers, report, and all three tracker snapshots.
- Packager size and SHA256 replay passed all records. Credential-pattern
  scanning returned zero matches and no router backup is included.
- No router operation occurred and acceptance is unchanged: V6.70 remains live
  accepted; V6.80 remains offline and unflashed.

## V6.80 Independent Bundle Replay Session - 2026-08-30 22:07 +03:00

- Added `work\verify_w1700k_v680_bundle.py` and independently replayed the
  frozen bundle into `work\build-v6.80-20260830\bundle-verification.json`.
- `PASS_V680_BUNDLE_REPLAY` covers 84 manifest records, 84 SHA256 records,
  all 86 physical files, the direct image, bundled image, top-level checksum,
  and offline marker with zero failures.
- No router access or mutation occurred. V6.70 remains live accepted and V6.80
  remains an offline/unflashed candidate.

## V6.81 Corrected Type-5 Data Contract Session - 2026-08-30 23:00 +03:00

- Reopened the stock RX Type-5 chain end to end instead of inheriting the old
  `info:+0x04` assumption. Full Ghidra analysis proves
  `hostadpt_rx_handler()` returns descriptor qword 1 (`data:+0x08`), stock PCI
  projects it into local10/local8, and stock HWiFi reads the projected hook and
  fate bytes. Descriptor `info:+0x04` remains PPE/count/id/reason metadata.
- Patch 46 adds only default-off observability: complete descriptor layout
  assertions, first/second data snapshots, scatter-data mismatch accounting,
  exact stock projector/decode counters, and coherent per-ring samples. It
  makes no skb, skb-CB, packet, descriptor, ownership, dispatch, firmware,
  userspace, or configuration mutation.
- The projector model exhausts 16,777,216 lower-24-bit equivalence states and
  covers all 4,294,967,296 32-bit inputs. Fate 0/1 split evenly; fate 2/3,
  optional hook bit 25, mismatches, mask violations, and mutations are zero.
- Current source contract passes 55/55 and inherited contracts pass 69/69.
  Strict checkpatch, clean build, 29-unit Sparse, full image build, exact FIT/
  rootfs candidate verification, and aggregate static suite all pass.
- Fresh full Ghidra 12.1 analysis covers stock hostadpt, stock PCI, stock
  HWiFi, rebuilt mt76, connac, and mt7996e: 1,976 functions. The 45-check
  Ghidra/ELF gate pins the static-key NOP/site/target, `ldr w30,[x1,#8]`, exact
  projector instructions/mask, decoded fields, generation barriers, and
  unchanged packet-path resume.
- Exact image SHA256 is
  `ae23a15d7a1029127f5e2b4efcba829172cd067b2d293d39ab58c2703e68bb66`;
  size `20,636,476`, FIT headroom `60,612`, package count `189`.
- Kernel/DTB are byte-identical to V6.80 and rootfs shape remains 1,146 files.
  Only APK bookkeeping plus mt76/connac/mt7996e differ. LuCI, helpers,
  services, configuration, and all four Airoha NPU firmware blobs are
  unchanged. No stock vendor module is shipped.
- No router command, upload, reboot, or flash occurred. V6.70 remains live
  accepted; V6.81 is offline/unflashed pending separately authorized mode 0/
  mode 3, Type-5 telemetry, MLO/radio, sustained RX/TX/RRO, recovery, memory,
  throughput, and fatal-log gates.
- Report:
  `work\W1700K_V6.81_NPU_TYPE5_DATA_CONTRACT_OFFLINE_CANDIDATE_20260830.md`.

## V6.81 Offline Candidate Freeze Session - 2026-08-30 23:08 +03:00

- Added `work\package_w1700k_v681_offline.py` and froze the canonical
  `OFFLINE-UNFLASHED` bundle plus direct image under `FinalResult`.
- The 119 retained payload files total 36,776,732 bytes and include the image,
  patch lineage, prepared source, model, build/Sparse/Ghidra/ELF evidence,
  stock decompiles, verifiers, report, and all three pre-freeze tracker
  snapshots.
- Packager size and SHA256 replay passed every record. Credential-pattern
  scanning returned zero matches and no router backup is included.
- The initial atomic output independently verified as complete, but a
  post-rename summary attempted to stat stale staging paths. The first output
  was preserved in the V6.81 build evidence, the summary calculation was
  repaired, the audit inventory refreshed, and the canonical output rebuilt
  cleanly. The firmware image did not change.
- No router operation occurred. V6.70 remains live accepted and V6.81 remains
  offline/unflashed pending separately authorized runtime validation.

## V6.81 Independent Bundle Replay Session - 2026-08-30 23:08 +03:00

- Added `work\verify_w1700k_v681_bundle.py` and independently replayed the
  canonical bundle into
  `work\build-v6.81-20260830\bundle-verification.json`.
- `PASS_V681_BUNDLE_REPLAY` covers 119 manifest records, 119 SHA256 records,
  all 121 physical files, the direct image, bundled image, top-level checksum,
  and offline marker with zero failures.
- The bundle snapshots precede these post-freeze tracker entries by design.
  No router access or mutation occurred; V6.70 remains live accepted and
  V6.81 remains an offline/unflashed candidate.

## Patch 50/51 NPU Lifecycle Audit Session - 2026-08-31 10:41 +03:00

- Built a clean predecessor replay from the pinned mt76 archive, then applied
  canonical patches 50/51 at zero fuzz. No neighboring patch was edited.
- Source audit found dead, undefined feature gates around RRO address
  publication; the provider call was unreachable. The repaired path uses the
  real sleepable GFP_KERNEL API under the mt76 mutex and models provider-entered
  failures as unknown ownership.
- Teardown now parks generic TX before revoke, drains work before and after
  IRQ/NAPI shutdown, and drains callbacks once more after mac80211 unregister.
  Stop polling has one compile-time bound with no zero/unbounded mode.
- Partial MCU startup no longer proceeds to DMA free after an ignored shutdown
  failure. MCU exit returns proof, the running bit remains set on failure, and
  unwind/remove quarantine before RRO or DMA free.
- The transactional PPE callback has exact mt76-local result names and an
  explicit synchronous borrowed-SKB lifetime. Unexpected positive returns are
  protocol errors; no caller ownership unwind occurs.
- Two real compile discoveries were repaired: production uses the kernel
  provider header rather than mt76's fallback copy, and `if (THIS_MODULE)` is a
  W=1 tautology. Final W=1 and all 29 Sparse checks pass.
- Focused source/model tests pass 9/9, strict checkpatch is clean, and all 386
  aggregate patches parse. Final module hashes and full changed-path inventory
  are in
  `work\W1700K_PATCH50_51_NPU_LIFECYCLE_AUDIT_20260831.md`.
- No full image or router operation occurred. Runtime NPU ownership and
  quarantine/module-unload behavior remain open.

## V6.84 PPE Ownership Boundary Session - 2026-08-31 12:15 +03:00

- Ghidra sidecar evidence separates stock native PPE packet-fate handlers from
  the Airoha provider callback. Stock can consume/forward/free SKBs; there is
  no recovered proof that those handlers implement `airoha_ppe_dev_check_skb`.
- Live prepared provider source confirms `airoha_ppe_check_skb()` is a
  bind-only function returning `1`, `0`, or negative errno. Its caller performs
  GRO on the same SKB after the callback, so Patch51 correctly remains borrowed
  and synchronous.
- Patch51 gained a local typed decoder and explicit `ERROR` result; unexpected
  positive values are fail-closed as `-EPROTO`. Canonical and mirror SHA256:
  `1d89d6698817ab1071a18b06fb4879f5e08b64bec58bff17574d516294ee08fc`.
- Five new ownership tests and the established 9-case lifecycle regression
  suite pass. Patch syntax, `git diff --check`, and strict checkpatch pass.
  No compilation, image build, router operation, or stock-binary modification
  occurred.
- The full P47-51 series is still not promoted as replay-clean because Patch48
  has an independent Patch34 conflict. The V6.84 evidence records this rather
  than making a full-parity claim.

## V6.84 mt76 Series Repair Session - 2026-08-31 12:30 +03:00

- Reconstructed exact predecessor fixtures for the HIF2, WFDMA-depth, and
  Patch48 findings. The HIF2 and DMA hunks now apply without discarded
  context, and Patch48 preserves the post-Patch34 four-argument EHT call while
  returning MLD setup failures transactionally.
- Experimental EPCS capability advertisement is now default-off through the
  normal static-storage false default. Its `0444` module-load policy remains.
- A pinned run-02 snapshot applied all 132 mt76 patches with `--fuzz=0` and
  zero rejects. The aggregate 386-patch parser, source/mirror contracts,
  strict checkpatch, Patch48/Patch49/Patch50-51 models, and focused mt76
  package compile all pass.
- Final repaired patch SHA256 values are
  `c6a72858eea46f678643b2ae277797d1bb9ae295b3ff2651254281b9ac5b48f9`,
  `f86cc48679cfe6615c5672e2121b17bdabac4eaf7cec4c6cd221bc50bb62141e`,
  `dcdd095a238154eefa5cb9c5bc49954f297260e445ffc4a674104b7c4665007a`,
  and `455f359882d8720916caca337d0bd5327ccdb71946d69ffe67519771b30a1838`.
- Patches49-51 and target patches77/78 were excluded from edits. No image or
  router operation occurred. The previous static replay boundary is closed;
  hardware acceptance remains unclaimed.
- Report:
  `work\analysis\mt76-series-repair-v684-20260831\REPORT.md`.

## Live V6.70 Mode 0 Radio Session - 2026-09-01 17:07 +03:00

- Bound all management traffic to Ethernet source `192.168.1.224` and
  re-identified `192.168.1.1` as the W1700K before running tests. The target
  reported `gemtek,w1700k-ubi`, kernel `6.18.34`, release `r0-5575e4a`, and
  boot ID `1d385777-bef3-4512-a557-ef2b1097d428`.
- The initial matrix produced one false negative because a valid 2.4 GHz
  20/40 coexistence fallback was treated as failure. Updated
  `tools/w1700k_unattended_synthetic_test.sh` to accept 20 or 40 MHz for that
  case, then reran the entire guarded matrix.
- The rerun passed 37/37. It covered 2.4 GHz, 5 GHz EHT80 and EHT160 with CAC,
  6 GHz EHT320, two-link and tri-band MLO, LuCI-style scans and recovery,
  impossible-config rejection, service health, fatal kernel diagnostics, and
  byte-exact wireless restoration.
- The router remained on V6.70 and NPU mode 0. Its NPU lifecycle returned
  inactive-clean, the boot ID remained unchanged, approximately 1.58 GiB of
  memory remained available, and no flash, reboot, or persistent final radio
  mutation occurred.
- Evidence report:
  `work\router-tests\v670-mode0-recheck-pass-20260901-170743\REPORT.md`;
  SHA256
  `b823c577bf068f24a6bc4bfce65515d7dde597a76e9323df6c13d8223d521417`.
  Its 38-entry manifest verifies with zero mismatches and has SHA256
  `54851e900387c1d1c7a788f327bd4497fb73cc456a327ce4d305afe56f2f03a9`.
- This session supplies a clean live baseline only. It does not promote V6.85
  or V6.86 and does not close the NPU TX-ledger design boundary.

## V6.86 Audit, Cleanup, And Build Session - 2026-09-01 17:57 +03:00

- Completed the full patch-hygiene replay. Primary source applied 917/917 and
  the corrective source 921/921 patches with zero fuzz or rejects. Verdict is
  pass with hygiene debt: mt76 has 68 offset-dependent patches/261 hunks, and
  the legacy inventory is stale by 371 active paths. Evidence:
  `work\analysis\v685-v686-full-patch-hygiene-audit-20260901\REPORT.md`.
- Hardened the release certifier and passed 106/106 Windows checks with four
  expected skips. Immutable wrapper/candidate/source-state/approval anchors are
  now enforced, but B-01/B-02/B-03 keep release-authoritative promotion closed.
  Evidence: `work\tests\release-cert-v686-hardening-20260901\REPORT.md`.
- Normalized MLO TX policy across patch, helper, and LuCI: upstream policy 0 is
  the only selectable behavior, while legacy values 1/2 are deprecated aliases
  repaired to 0. Scheduling contracts, patch replay, and AArch64 object builds
  passed.
- Cleanup Stage 1 deleted 77 exact duplicate ITBs for `1,587,513,612` bytes.
  Cleanup Stage 4 verified the V6.84 A5 and retained B6 trees at identical HEAD,
  config, 89 target files, and 115 package files, then deleted only A5 with zero
  live process references and recovered `16,522,678,272` filesystem bytes.
  Stage 2 was not executed because its read-only candidate set overclassified
  retained certification evidence. Receipts are under
  `work\analysis\v686-cleanup-audit-20260901`.
- Started V6.86 engineering/provenance Build A at `20260901T145753Z` from the
  reviewed overlay snapshot using 12 jobs after targeted package invalidation.
  Exact root and LuCI heads, dirty state, config, `git diff --check`, Bash, and
  ShellCheck gates passed before compilation. No build result or promotion is
  claimed yet.
- The W1700K remains on accepted V6.70. No upload, flash, reboot, or persistent
  router mutation occurred during this session.

## V6.86/V6.87 Corrective And Live Session - 2026-09-01 20:40 +03:00

- V6.86 Build A passed with image SHA256
  `a4b65a92db861f5e74b6c0b6005b2fdb758472e1eb0d83c8ec530b7f54746325`.
  Its engineering verifier passed, then the image was flashed for live WiFi
  testing.
- Live testing found two defects: hostapd MLO country validation read the old
  `country` alias instead of normalized `country_code`, and mandatory 2.4 GHz
  20/40 coexistence fallback could break an assembling EHT40 MLD.
- V6.87 uses `country_code ?? country` and requires EHT20 only for radio0 MLO
  membership. Standalone 2.4 GHz EHT40 is unchanged. The policy is mirrored in
  hostapd ucode, LuCI, backend validation, and boot-time sanity repair.
- Corrective patch SHA256:
  `838d1f2524ec6efbe54b98b4824cc3f04fd73f61c64e40dbb122b4ea8576f016`.
- Static gates passed. The successful V6.86 hotfix proof passed 38/38. A first
  attempt with a non-executable uploaded validator is retained and labelled as
  a harness-only failure.
- V6.87 clean affected-package build passed with exactly one image. Offline
  verification passed: exact W1700K FIT/DTB/profile, 187 packages, 1,140
  rootfs files, expected NPU firmware/assets, and no forbidden stock modules.
- V6.87 image SHA256:
  `502745127cae575e6442ed373e12ae1047dde016d34c3fce98e76e7fd26e5c56`;
  size `20,415,292`; FIT headroom `281,796`.
- The normal preserved-config flash passed `sysupgrade -T` and used neither
  `-F` nor `-n`. The live FIT prefix matches the candidate. UBI is healthy with
  zero bad PEBs; boot environment and factory volumes remain present.
- The installed V6.87 image passed 38/38 in mode 0 without overlays. Coverage:
  standalone 2.4/5/6 GHz, DFS EHT160, EHT320, two-link and tri-band MLO,
  member scans, impossible-config rejection, services, fatal log scan, and
  byte-exact state restoration. Original/final wireless SHA256:
  `588a3e98ee05a0d8649c392c54c4e879ac74230c1ed34a2134f07649e2aa945c`.
- Evidence:
  `work\router-tests\v687-preflash-20260901T172804Z`.
- V6.87 is live-validated engineering work, not client throughput or stock NPU
  TX-ownership parity. Modes 1-4 and independent Build B were not requalified.
  Patches 52/79 remain `BLOCKED-DESIGN`.
- Guarded cleanup recovered `18,110,191,884` bytes. Broad evidence cleanup was
  not run because its candidate inventory was overinclusive.
- Final bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.87-Corrective-Engineering-20260901`.
  All 82 payload hashes/sizes replayed independently with zero failures. No
  router backup or chainloader is included.
- Final cleanup removed two byte-identical staging copies totaling 26,164 bytes
  and the exact router `/tmp` artifacts created by this run. The post-cleanup
  test/watchdog inventory is empty. Receipt:
  `work\analysis\v687-build-a-20260901\CLEANUP-REPORT.md`.

## NPU Ledger-To-Source Session - 2026-09-01 22:54 +03:00

- Reworked the lifecycle reference model into R3 and independently reviewed
  it. Windows and WSL each pass 83/83 tests; exhaustive coverage includes 781
  valid schedules and 60 provider mutations. QA-01 through QA-11 all pass.
- Provider patch 79 v4 is staged with checked queue register access, classified
  doorbell commit state, checked IRQ and DMA-device access, and a stable
  three-sample drain certificate. Patch SHA256:
  `2a4a73221e3b0b6ab02c8d49c1c0024bef2a5d5f5e75008531582f3b38de11f9`.
  Provider object compile log SHA256:
  `f1f84b3b06983e0eae4bbc4633dcfa9ddabf25eaf66af33488be7ad1c57b7b6f`.
- mt76 patch 51b mirrors the provider ABI and compiles. Physical patch 53a,
  SHA256
  `e3f7c9c8f14426bc14621ea8a349a5a1bd9e9a8d4db92e20f9c6d1f27f95c7f6`,
  adds canonical per-TXWI transaction storage, a default-off ledger static
  key, locked token claim/release helpers, and post-lock side-effect actions.
  Its full package build passed; mt76, connac, and mt7996e module SHA256 values
  are `49e14c37f7b7370ae66bb9b4b93fdabdcaf855aa9d0aaabc2555268d92ee8557`,
  `9511ff160db3186101f591aa612508167ec9da50f0222936901bc4ce08af2c4a`,
  and `164e25ad7b5582b7b10118d2adfb2030bdde4b24ce3b2d12941a5b7b074497a8`.
- Added kernel patch 80 and mt76 mirror patch 51c for checked provider
  identity. Their SHA256 values are
  `28370f322c77e34fcce6d3f631f886cc570eb9d575ec21b348026061e4892671`
  and
  `1dad1dd2cfa45e848c39fbf28482a5f39049db80e12c47fa7ae6e8621c4951e9`.
  Strict checkpatch reports 0/0/0 for both. Provider object compile log SHA256
  is `246ebcfb01526fc95c6f7395ab6a8762676c3d582d9cf917e56636c964a0616d`;
  `nm` confirms the exported getter. mt76 clean/prepare/compile logs hash to
  `061fb68a9cbd0f24dbd408312441c520503ae2b554251ce7d9cef41eaf99ff59`,
  `b83f99c84976055ad7cc41203c9333870624fa2e7d314d78e573d427b2ec0010`,
  and `8b4c50cd74083d1466ee45c6ff93c38dc3189bc4e35ceac563b19733597bb9c`.
  The build exited 0 with only baseline missing-description warnings.
- Patch 51c is declaration-only and therefore leaves the three mt76 module
  hashes identical to 53a. No image build, upload, flash, reboot, or persistent
  router operation occurred. The next source tranche is physical patch 53b;
  53c and 53d remain required before any candidate can be considered for live
  NPU testing.

## NPU Checked-Publication Session - 2026-09-02 00:02 +03:00

- Completed physical mt76 patch 53b. Patch SHA256 is
  `662a321c95d7d11e9ef0989376dbb8edef0b7382325d723b3e7ab2c6c24a5e1c`;
  strict checkpatch is 0/0/0 across 826 lines.
- Added checked provider queue reads/writes, classified doorbell publication,
  checked IRQ control, checked DMA-device lifetime, provider-instance binding,
  serialized owner publication, readback verification, and fail-closed queue
  quarantine. Fixed a discovered RX-refill error-path self-deadlock by moving
  fault dispatch outside `ownership_publish_lock`, and made first provider
  failure metadata truly first-writer-only.
- The first mt76 compile correctly exposed that the expanded kernel tree was
  stale and lacked patch 80. Regenerated it with `target/linux/clean` and
  `target/linux/prepare`; the full target kernel then compiled successfully,
  including `airoha_npu.o` with provider patches 79 and 80.
- A clean OpenWrt mt76 package build then exited 0. Clean, prepare, and compile
  log SHA256 values are
  `1c4d380f557e4123957971576be89f08d67999b7341256d78ee93918ff805a90`,
  `bb9d8ec9331ae3fce8d549a0cc5d46592ef3c313fd506b4b45dc435c35a18222`,
  and `14557a0ec78e069385114e4250196c1cc10ecec117cae3b0540f09e8dcf38992`.
  There are no patch-specific compiler warnings.
- Rebuilt module SHA256 values are
  `2c20d200ce86d801977cc0bb8872d09203429dc041c92aa21dee229ba96c6b8c`,
  `98401c2875a15743615d1050139141b00515117e1278e1482c08e71b39208508`,
  and `83a2d61f01fd980b31422e01ce6754ff4c2ba36e91f459a224a1539c1bbf8b70`.
- No image or router operation was performed. Patch 53b remains an intermediate
  source tranche; 53c completion/finalization and 53d stop/drain/permit work
  are mandatory before building or flashing an NPU lifecycle candidate.

## NPU Canonical-Completion Session - 2026-09-02 00:29 +03:00

- Completed physical mt76 patch 53c. Patch SHA256 is
  `f68f03b4a33764b55424311907ba5b35ba7c8385f73794529d90c07ba12724cc`;
  strict checkpatch is 0/0/0 across 919 lines.
- Added explicit descriptor-consumer, queue-detach, TXFREE, stock-copy, and
  flush-request events. The normal finalizer predicate is consumer plus queue
  detached plus either TXFREE or stock-copy. Finalizer tickets bind TXWI,
  token, transaction sequence/incarnation/epoch, provider instance, and a
  unique nonce.
- Ring cleanup records evidence before clearing the slot, advances the queue,
  then records detachment. TXFREE-first and consumer-first schedules converge
  on one finalizer. Ledger-mode flush no longer clears descriptors, mappings,
  tokens, SKBs, or TXWIs and does not kick the ring.
- Driver payload unmap and SKB completion now precede exact token removal;
  successful generic finalization precedes TXWI cache insertion. Ambiguous,
  duplicate, stale, provider-mismatched, or reused numeric TXFREE events fail
  closed and quarantine publication.
- Clean/prepare/compile log SHA256 values are
  `89d65bf77f1ef62254d1c3eba582194c23cce135dedc60e2fec947a33d85d882`,
  `b652aabeaff0124321328181c7ef13579cb5ba54b7fedc4dc4a4f1e510aa54d8`,
  and `35c6796b8e18db6452d4d69573385ccbdb923028098ae87be7fdf898652d91b5`.
  The package build exited 0 with only baseline missing-description warnings.
- Module SHA256 values are
  `0b8f367635b75109214c7891a469a06ec0717a685eb5d38ef81dec6a4fef3348`,
  `9fdab6965f62d3c168d118b384f34db7e18799599eb4826b3d4e8dd5fa361a50`,
  and `a57346f6a9c5c154aa15b6ddfcc647a7d52b6ce09eff372b0cc885122434f607`.
- No image or router operation occurred. Patch 53d stop/drain/certified-reclaim
  work remains required before any lifecycle candidate may be flashed.

## NPU Certified-Drain Session - 2026-09-02 01:12 +03:00

- Completed physical mt76 patch 53d1. Patch SHA256 is
  `adbc54155d1b0c2519e6391a49423cd750b735fa18a6ae6c1e1865e6a721f53d`;
  strict checkpatch is 0/0/0 across 969 lines.
- Added serialized operation identity, producer freeze, STOP acknowledgement,
  bounded ordinary drain, explicit completion-source shutdown, fresh provider
  certificate binding, device-wide validate-before-mutate queue detachment,
  exact certified finalization, host-zero verification, and fail-closed abort.
- A clean compile found one wrong queue-cleanup wrapper at `npu.c:889`. The
  direct `queue_ops->tx_cleanup` path with a missing-callback guard replaced
  it. A second clean/prepare/compile completed with exit 0 and only baseline
  missing-module-description warnings.
- Clean, prepare, and compile log SHA256 values are
  `e4c647d9f326f0ecbef38a1d23d78836c83d53291a00f75e09233c8734a3370d`,
  `c7803b3108e66e000cbf100365033e4b5b758b392c591f3aed179acb569cfe0d`,
  and `01733ed00d4acc018ec4e17541fb0d0566e8cbcbc93785142a6e6cbd9348cafc`.
  Module hashes are
  `2617da3dc32f6756f8420019b8d79120b4282ca96d3936868e2998aa9f7e56a8`,
  `b09cc0dc3429603dbe8f0d0ae0e00c290cd8477522bbf1266b8f8a9af0eae395`,
  and `86c9e7fbbe2a4fe5adb6b05b1985f37985c3d89300c94e879b09ca1e7c5494f1`.
- No image or router operation occurred. Typed one-shot permits and complete
  caller routing remain in 53d2; the ledger stays default-off until that work
  and the generationless-TXFREE production boundary are resolved.

## Disk Cleanup And 53d2 Audit Session - 2026-09-02 01:35 +03:00

- Executed the previously gated cleanup set and removed `54,501,519,085`
  bytes (`50.76 GiB`) without deleting active source, build, release, stock,
  Ghidra, or recovery artifacts. WSL now reports about `48 GiB` used and C:
  reports `43.77 GiB` free.
- An attempted detached-VHD `diskpart` compact made no measurable change in
  the unelevated process. WSL rejected sparse conversion without an explicit
  unsafe override, so that override was not used. The freed ext4 blocks remain
  available for active build reuse.
- Independent read-only caller and destructive-leaf audits found zero current
  users of `mt76_npu_tx_operation_*`, TX-only certificate coverage, missing
  RX/RRO/provider ownership manifests, and no typed permit/consumption layer.
  They also identified the current source-disable-before-STOP inversion in
  init unwind, shutdown, unregister, restart, L1 reset, and debugfs recycle.
- No image was built or flashed and no router contact occurred. Cleanup details
  are in `work/analysis/npu-53d-cleanup-20260902/CLEANUP-REPORT.md`.

## NPU 53d2a Completion Session - 2026-09-02 01:55 +03:00

- Added and compile-proved the two-stage completion boundary: terminal
  authority is now authorized before mt7996 performs DMA unmap/SKB completion,
  and token release commits afterward. Patch SHA256 is
  `d6eba88f18304ced9f9b1f31a3486fa941c4b6c536ea9f96265655e93ed9da56`.
- Strict checkpatch passed 0/0/0 across 136 lines. Fresh package clean,
  prepare, and compile exited 0 with only the existing missing-description
  warnings. `mt76.ko` exports both completion symbols and `mt7996e.ko`
  resolves both as imports.
- Adversarial review kept the tranche narrow: queue/descriptor mutation still
  precedes an all-transaction batch seal, token commit can still reject after
  side effects, and the provider reference is not retained for the operation.
- A direct-RX audit confirmed existing certificate fields can cover NPU RX0/1
  after the provider actually samples them. It also proved RRO cannot be folded
  into that certificate because RRO ownership is published through a separate
  mt7996 firmware-mailbox path.
- Full findings and hashes are in
  `work/analysis/npu-53d2-boundary-audit-20260902/REPORT.md`. No image, flash,
  or router operation occurred.

## NPU 53d2b Review Session - 2026-09-02 02:52 +03:00

- R4 extended the executable model to `93/93` passing tests on both Windows
  and WSL, with 793 schedule instances and 60 certificate mutations.
- 53d2b-v1 was rejected for declarative source quiescence, fallible
  post-detach closure, provider-reference leakage, aggregate counter risks,
  queue wakeup omissions, lock-order inversion, and mutation during prepare.
- v2 corrected the batch design but failed compilation because
  `spin_lock_bh_nested()` does not exist. v3 uses one BH-disabled region with
  canonical nested spin locks and then passes strict checkpatch and a fresh
  mt76 package compile. Its patch SHA256 is
  `546585b8d57e998ac175306524f26501711255fb612e6b4185aec4ba63f8d740`.
- A second independent review rejected v3 for three remaining defects:
  provider teardown/reopen serialization, reinit quarantine poisoning, and
  unsafe disposal of a release-contract violation. These are now hard gates,
  not deferred polish.
- A direct RX/RRO audit found the provider certificate samples TX only,
  direct RX cleanup has no permit, and RRO publication/release belongs to a
  separate mt7996 firmware-mailbox domain. Current lifecycle ordering disables
  completion consumers before STOP and must be reversed by one common caller
  coordinator.
- No image, flash, reboot, or router contact occurred.

## NPU 53d2b-v5 Failure-Atomic Session - 2026-09-02 03:25 +03:00

- A fresh independent audit rejected compiled v4 for unsafe orphan lifetime,
  a fallible post-detach release contract, destructive live-reinit failure,
  and incomplete residual ownership validation.
- v5 removes orphan retention and uses two phases: validate every release
  without mutation, then detach the complete batch and run an infallible
  driver release. Live reinit is rejected before old-provider teardown;
  generation reuse requires zero token counters, an empty IDR, and empty NPU
  TX queues.
- Patch SHA256 is
  `dadc610dac1c52dfe3b92562f3697f776581944fcaf83c142e94dd6072ed183a`.
  Checkpatch is 0/0/0. Clean/prepare/compile logs hash to
  `c2abe467ee68abcefa13c251ba584a27a75341d21e9daac59a111fa8165deaa8`,
  `8ddec91a0d43e32ab66d0ee3524abc3993a484407e0903617041fdc6693bdae9`,
  and `9532092c764f500dc37951ad161ca4eed9c8ae86c63464df933bf7445a5ec39c`.
  Source equality checks pass for all six touched mt76 files.
- R5 passed 102 Windows tests but modeled the now-rejected retained-orphan
  design, so R6 is replacing those cases with all-or-nothing release preflight
  and non-destructive reinit schedules.
- Separate audits mapped direct RX0/RX1 and RRO. Direct RX pages are currently
  freed without a generation-bound provider certificate; RRO global tables
  and page maps have no demonstrated firmware-forget authority. The common
  coordinator and typed completion-source permit remain mandatory.
- No image, flash, reboot, or router contact occurred.

## NPU 53d2b-v7 Compile, Review, and RRO Correction - 2026-09-02 03:44 +03:00

- v5 was rejected after source review because provider programming preceded
  the first residual preflight and queue residue coverage was incomplete. v6
  moved and expanded those checks but released the init claim before its old
  activation unwind finished.
- v7 keeps `init_in_progress` held until unpublish, RCU synchronization,
  lifecycle deinit, and DMA/PPE/NPU reference release all complete. Its patch
  SHA256 is
  `50e14f1ac8d4245d5e85388bcc038386ee9958cadaaa55b771794cd113225009`.
  Strict checkpatch is 0/0/0 over 1157 lines and a fresh mt76
  clean/prepare/compile exits 0.
- Module hashes are
  `fad8cf237a91c94382f63bd9c1a24d960026a89d7c58bdaee1a0635717b616ae`
  for `mt76.ko`,
  `0947539c055e2d048c86928cf0df945b1e9d0bcbe93cac7bc121e5a97d98b34b`
  for `mt76-connac-lib.ko`, and
  `12157e4e743e65035bb6eaf7dc843961901ac599a8234af1caed1967ecea04be`
  for `mt7996e.ko`.
- Independent review accepts v7 HEAD
  `fb5e80788fb946166fbd0316d11154752773783d`. Final R6 passes 115 tests and
  844 schedule instances on Windows and WSL. Five successor-at-unwind
  boundaries remain blocked until old cleanup completes, and a negative
  early-clear mutation reproduces the v6 state corruption. A hardcoded
  single-host report bug was corrected; the final dual-host report SHA256 is
  `cda8e5f7f742adbafa7407f034feaf82eab0aca8b7a1d3575707bf72bdacd997`.
- Stock host and complete RV32 evidence correct the prior RRO wording. STOP
  plus GET zero proves quiescence only. `RRO_STOPPED_PRESERVE` cannot authorize
  DMA unmap/free/reuse; a true release requires firmware forget evidence or a
  proved new NPU boot epoch.
- No image, flash, reboot, or router contact occurred.

## NPU v7/RX81/53d2c Cross-Audit Session - 2026-09-02 04:20 +03:00

- Re-ran the source boundary against the complete R6 claims instead of only
  the activation-failure race. The five-boundary init-claim proof still holds,
  but v7 is rejected as integrated infrastructure: administrative deinit can
  race unpublished init, descriptor cleanup can destroy residue evidence,
  source shutdown is declarative rather than physically synchronized, and the
  mt7996 release validator does not establish an infallible post-detach leaf.
- Independent provider review rejects RX81 because it couples legacy TX
  certification to RX ring availability and one terminal shared gate/STOP
  epoch. A scoped RX certificate, independent serial consumption, typed rearm,
  and host page/descriptor inventory authority are required.
- Local 53d2c review found that a synthetic held TXFREE payload escapes the
  lease ledger and can cross quiesce/restart. Logical typed leases therefore do
  not yet prove that all physical completion sources are drained.
- Recorded the findings and exact raw diff hashes in
  `work/analysis/npu-v7-rx81-53d2c-cross-audit-20260902/REPORT.md`, SHA256
  `20c26b6325a88778baef3fd7dc6776403cc45efc1b1c91f188b055933d83e2b2`.
  No source was promoted, no image was built, and no router operation occurred.

## NPU 53d2f, Power Recovery, and Nightly Delta Session - 2026-09-02 05:08 +03:00

- Recovered after host power loss. WSL, the interrupted mt76 build, isolated
  source trees, executable model, and official OpenWrt references survived.
  The mt76 compile session terminated successfully with exit code 0.
- Completion-Source Model R1 finalized at 82/82 tests on Windows and 82/82 on
  WSL, 72,072 schedules, 12,012 held-reorder schedules, 60,060 nested-cleanup
  schedules, 4,665 completed restarts, 323,181 rejected unsafe operations, and
  23/23 killed mutations. The model explicitly keeps held reorder payloads as
  independent TXFREE obligations after parser-lease return.
- Independent re-audit accepted the corrected 53d2f component. The source now
  claims init before lifecycle preflight, serializes administrative init and
  deinit, synchronizes TXWI DMA for CPU inspection, binds decoded payload DMA
  to the CPU-owned queue entry, and performs validate-all before its infallible
  post-detach release commit.
- Snapshotted the accepted component on branch
  `w1700k-npu-53d2f-admin-release` at commit
  `c1e4f827ec57bba2252c6b20b0809f8819c6a27e`. Exported patch SHA256 is
  `099aa4d6fcb597b16837cbe030e96dd44d1fcda0e8dd7bdfb3cf62d7e589af2b`.
  Strict checkpatch and `git diff --check` pass.
- Compile-v3 log SHA256 is
  `48f51dec0879fbace1a55f6284d588ff4ba918f79b091ede7c41067380abe588`.
  It contains no compiler error or patch-specific warning; the only actionable
  diagnostics are 13 unrelated dependency warnings and three longstanding
  missing-module-description modpost warnings. Raw module hashes are recorded
  in `work/analysis/npu-53d2f-nightly-recovery-20260902/REPORT.md`.
- Refreshed the actual official OpenWrt Airoha `an7581` snapshot at
  `r36024-065a9b9abc`, OpenWrt commit `065a9b9abc...`, and mt76 pin
  `be5ce791...`. The current W1700K build uses mt76 `b2704cf5...` and kernel
  6.18.34; official nightlies remain the active comparison/port source.
- Downloaded and inspected the actual official ITB. Its SHA256 matches
  `profiles.json`; FIT metadata reports `gemtek_w1700k-ubi` and Linux 6.18.44.
  Rootfs inspection reports mt76 `be5ce791`, NPU firmware `20260810-r1`,
  `wpad-basic-mbedtls`, and no LuCI. It is comparison-only, not flashable as
  our custom `ubi2` image.
- Audited all 67 mt76 commits in that range. High-priority ports are WED-attach
  NPU/HWRRO state commit, failed-scan off-channel cleanup, per-peer MLO AQL,
  updated RRO BA-delete ABI, retained-link reprogramming, connection monitor,
  ROC ownership, TWT cleanup, ALTX, and a remap guard. The dedicated 11-patch
  lane now passes ordered apply checks, stable upstream patch-ID comparisons,
  telemetry-preservation assertions, aggregate diff checks, and strict
  checkpatch 0/0/0. It remains uncompiled and unintegrated; incompatible NAPI
  and mac80211-7.2-only changes are excluded.
- Independent review rejects the 53d2d production coordinator. Its source-sync
  callback omits generic PCI/HIF2/WED IRQ/tasklet and TXFREE/RX/TX NAPI/work
  sources, then promotes partial success to a global certificate. It also
  destroys a held reorder payload that the model requires to remain an
  independent outstanding obligation. Producer resume precedes consumer
  restore, and residual proof follows partial coordination teardown.
- Preserved the exact ten-file WIP as
  `work/source-stage/npu-mt76-lifecycle-patches-20260901/53d2d-wip-current-20260902.patch`,
  SHA256
  `ba45295c01cf08f42314fe96e9590dc7723b621623a31cfaa8f24c69e4f3abc4`.
  Reverse apply-check succeeds. The older `53d2d-wip.patch` is stale and is
  retained only as historical evidence. A new 53d2g implementation lane is
  replacing the false global certificate with typed per-source authority.
- 53d2f remains component-only because production lifecycle callers can still
  bypass it. No image, upload, flash, reboot, or router operation occurred.
  Evidence report SHA256 is
  `9f68123f164da4a9d99d690fac9946b2806f4153bf99ee0ecf4d67d9a2a1851c`.

## Codex Session Cleanup Session - 2026-09-02 05:46 +03:00

- Audited C:, D:, WSL, the project workspace, Windows Temp, Downloads, and
  `.codex`. The W1700K workspace is about 22.2 GB; `.codex/sessions` was the
  dominant avoidable pressure at 123.5 GB.
- Generated an exact TSV manifest, then deleted 144 completed subagent JSONL
  files from only `sessions/2026/08/31` and `sessions/2026/09/01`. Validated
  every path and length before mutation and confirmed zero manifest entries
  remain afterward. Recovered 89,381,826,621 bytes; C: free is 105.27 GiB.
- Preserved the main task, all current-day sessions and active agents, memories,
  application state, project source, evidence, Ghidra databases, recovery and
  release artifacts, and canonical trackers.
- Stopped an impractical NanaZip attempt, terminated its detached child, and
  removed only the incomplete archive. A transient WSL client failure was
  recovered by controlled shutdown/restart; kernel 6.18.33.1 and the V6.89
  worktree were verified afterward.
- Exact evidence is in `work/analysis/codex-session-cleanup-20260902`.
  `REPORT.md` SHA256 is
  `1977cd7682926d6fada9cd779a808cd10c233f1cb8fa02ff726d38207a2ea32d`.
  No firmware build, router contact, or persistent device change occurred.

## V6.89 Upstream WiFi Build-Gate Session - 2026-09-02 06:26 +03:00

- Integrated the independently reviewed 11-patch official mt76 compatibility
  lane into the isolated V6.89 build tree. The fresh package prepare initially
  exposed CRLF-only context in the two TWT patches; both were replaced with
  exact LF upstream mail patches while preserving stable patch IDs.
- Fresh mt76 prepare and compile exit 0. Explicit mac80211 and full
  `wpad-mbedtls`/hostapd compile gates also exit 0. Hard-error scans are zero
  for all three compile logs; no W1700K, mt76, mac80211, MLO, or hostapd source
  warning was emitted.
- The rebuilt AArch64 `mt7996e.ko` contains the expected NPU/RRO/TXFREE,
  ownership, recovery, and host-adapter ring symbols. Raw module SHA256 values
  are
  `2d34e7c81345c4d66a1626619e2a3e261321f1734d35a75e3328236b18732a02`,
  `f688f5f0433586f5d00d0fcd92ca484ef425757ae377f5b486b09ed342858ec3`,
  and `5983c4a527e58623e306b3f73787aaabebfc0bf056a5e7d732674383dc3954d7`.
- The W1700K MLO source lane passes strict ucode, shell, C, package-patch, and
  backend adversarial checks. The complete source delta remains unflashed and
  is not promoted ahead of NPU coordinator completion and full FIT/rootfs
  verification.
- The 53d2g lane recovered from the outage. Its earlier CRLF explosion has
  been reduced to a focused semantic diff with clean `git diff --check`, but it
  is still under implementation and independent review. No image, upload,
  reboot, flash, or router operation occurred.
- The first durable-tree fixture pass caught stale expectations for 2.4 GHz
  MLO `EHT40`, legacy custom MLO TX policies, and the host `jshn` library path.
  Corrected fixture patches hash to
  `732daa7392f61a02341aeb2ecbaeed0baf61b82ca1c8573f4e02de7f96325781`
  and `ce30c453fe610c10c204450aa18c53c82c414425aba3162f95455003de6709bf`.
  All backend, width, validator, NPU-mode, coredump, firmware, patch-order,
  sysupgrade, LuCI syntax, and shell syntax gates now pass. All 19 modified
  files match between source and build trees.
- Detailed report:
  `work/analysis/v689-upstream-wifi-build-gates-20260902/REPORT.md`, SHA256
  `0c269dbd9023dd316bee01475f9d131a556a59c9bd398d97c590e417e61d385a`.

## 53d2g Recovery And Source-Gate Session - 2026-09-02 07:03 +03:00

- Recovered WSL2 after the power loss, verified about 894 GiB free, and found
  no orphaned build process. The existing mt76/mac80211/hostapd artifacts and
  WiFi fixture evidence remain intact.
- Independent strict checkpatch of the live 53d2g diff reports 0 errors, 0
  warnings, and 0 checks across 2,494 lines. Whitespace and reviewed line-ending
  checks pass, but this is style evidence only.
- Created `work/tests/npu-53d2g-source-gate-20260902/verify-source.sh` to check
  typed ingress coverage, physical IRQ/NAPI/tasklet/worker shutdown, held
  reorder ownership, exact permit binding, lifecycle routing, and
  consumer-before-producer restore. Shell syntax, shellcheck, and manifest
  verification pass.
- The gate correctly rejects the current tree on four points: no TXFREE-parent
  restriction for nested cleanup, nested CONSUMER acquisition, DEBUGFS as a
  nested parent, and unsupported production lifecycle parking. The first three
  expose a false-certificate race because nested activity can start after its
  source already recorded synchronization evidence.
- Source review also found unmodeled completion-capable work: `init_work`,
  `reset_work`, `dump_work`, `wed_rro.work`, `rc_work`, per-PHY `mac_work`, and
  `npu_rx_fault_work`. Event-aware coverage is required because some lifecycle
  transitions execute from those works and cannot synchronously cancel
  themselves.
- Direct-RX authority, RRO boot-epoch authority, semantic review, compile, and
  runtime-safe validation remain open. Nothing was integrated, built, flashed,
  uploaded, rebooted, or changed on the router.

## 53d2g Independent Review And Compile Session - 2026-09-02 07:42 +03:00

- Power recovery completed with the coordinator agents and WSL evidence intact.
  The coordinator worker finalized commits `240c50d` and `d4d7c1f`; the tree was
  clean before local compile validation began.
- The final source gate fixes cross-source nested leases, restricts nested
  cleanup to TXFREE-parent/TXFREE-child authority, rejects DEBUGFS as a nested
  parent, and makes double release stale. It passes 55 automated checks. The
  sole remaining failure is deliberate production-event parking.
- Independent semantic review found five immediate P0 classes: incomplete
  event-aware work coverage, live/unproved direct-RX and WED/RRO ownership,
  unconsumed DMA/NPU destructive actions, unchecked IRQ-disable failure, and
  incomplete terminal PCI lifetime. Independent direct-RX/RRO review requires:

  ```text
  DirectRxFree = Qsource AND ProviderRxReleaseCert AND HostRxInventory
  RroFree      = Qsource AND ExactRroGraph AND
                 (GraphBoundForgetAck OR ProvedLaterNpuBootEpoch)
  ```

- The first disposable compile attempt stopped before compilation because the
  coordinator repository is a source slice with no mt76 `Makefile`. The second
  assembled the complete matching V6.88/provider79 mt76 base and exposed three
  source integration errors. Added `../dma.h` to `mt7996/npu.c` and guarded WED
  IRQ member access with the same kernel configuration that exposes the member.
  The correction is commit
  `d36bde51c56188326b80ab2d8209a2fe17fe35b3`.
- The third disposable build exits 0 for AArch64/Linux 6.18.34. The only
  diagnostics are three existing missing-`MODULE_DESCRIPTION()` modpost
  warnings. Module SHA256 values are
  `9e74869a1bb440cd75e040f1fd97ae1714dfe5c4a1d1171d8192c90c8933c499`,
  `7a4fd263e97df81d622dd0ae607c5b5542c5aa08159c8ed2e136fbdc790f06f2`,
  and `7057e963a7a0f61e8f749cc2a23ebd56b2b921b701797e5fc7a2a67539fbf335`.
- Source-only strict checkpatch is 0 errors, 0 warnings, 0 checks over 3,095
  lines. The build evidence manifest hashes to
  `f59af3494488216bdf1eba746f4788444c7462110a43d298b2ac7c2206243c6d`;
  report SHA256 is
  `73dc5cccecb392a347299bbd3eab34fb09f43f241bdd1a96d948889ed61bbcfc`.
- Exported a focused source patch and a seven-commit recovery mbox. Reverse
  apply passes, and a clean replay from `fb5e807` produces tree
  `104772e6ba02df8ee8f616f01c6d495e86f9823a`. Current patch manifest SHA256 is
  `ce161faa84ad03815d2d3c925fb8465d8e2af5c78a20b1969d106c7303097956`.
- Wrote the durable review map to
  `work/analysis/npu-53d2g-independent-review-20260902`; its manifest hashes to
  `957f00dfd8b882336beb3ed5084e2984a484fc71ea04824c501382f354d176a4`.
- The V6.89 WiFi/nightly lane remains separate and valid. No NPU source was
  integrated there, no full image was built, and no router operation occurred.

## 53d2h Checked Provider-IRQ Session - 2026-09-02 07:52 +03:00

- Added `mt76_npu_disable_irqs_checked()` without changing legacy best-effort
  callers. It attempts both NPU RX rings, retains the first provider error, and
  reports provider disappearance instead of silently certifying it.
- Changed the coordinator physical-disable step to return an error and record
  its certificate only after the final checked disable and IRQ synchronization.
  Partial failure remains intentionally offline/fail-closed.
- Added source-gate assertions for checked disable and certificate ordering.
  The gate is shellcheck-clean and reports 57 pass, 1 intentional failure.
- Commit `cd485a5a63d073eb5be9c4d3d1155b4de7d944ac`, tree
  `a02a4829e90b45019d8276e34a53ce622ccd7f47`, passes diff/checkpatch and a fresh
  AArch64/Linux 6.18.34 component build. Compile-log SHA256 is
  `477e403e999baa1c387e04f920ef12be6421635d720b162673816b1c6ca28d46`.
- Recovery replay from `fb5e807` applies eight commits and reproduces the exact
  tree. Artifact-manifest SHA256 is
  `cb1eac55fffbbb3954b792603a19715a780c9d5c806db31b58cb6ae3ea90f73d`.
- No V6.89 integration, image build, module load, router contact, or flash was
  performed.

## 53d2i Debugfs Admission Session - 2026-09-02 08:06 +03:00

- Recovered after power loss with WSL kernel
  `6.18.33.1-microsoft-standard-WSL2`, about 894 GiB free, no orphaned
  compiler/linker, and a clean source tree at `cd485a5`.
- Routed TXFREE `reset-counters` and `clear-faults` through a shared helper
  that acquires typed DEBUGFS admission, checks `debugfs_blocked` before and
  after acquisition, performs the mutation, and returns the exact lease-release
  status. Committed as `274295235766d710e12a1c39b15e3faf0deb6d84`.
- Extended the static gate to reject direct calls from either command. It now
  reports 58 PASS lines and one intentional production-parking failure.
  Strict checkpatch reports 0 errors, 0 warnings, and 0 checks over 44 lines.
- A fresh isolated AArch64/Linux 6.18.34 build exits 0. Compiled module SHA256
  values are
  `0794c10adf0e07272ecd91984d9744f6d76b03c2e3fe85db1637a4ec397877d8`,
  `d2a2108667ac8da8455332d1f020d02147376548bbc642c0389686457803bf4f`,
  and `1754e67e10a9b04a0bc71ee48b6ae965669c02d53be003a68bbeecde2b70873b`.
- The first clean-room recovery replay stopped before patch application because
  the disposable clone lacked a committer identity. That log was retained; a
  second clone with a local test-only identity replayed all nine commits from
  `fb5e807` and matched tree
  `f380d3186a23d346ae0eda2f8355989073422695` exactly.
- Durable report:
  `work/build-logs/npu-53d2i-debugfs-admission-20260902/REPORT.md`, SHA256
  `1841a52b2fd80bf882e9e1adbd5d707448424acb9fd5515dbd5d5eca1cf96e53`.
  No image or router state changed.

## Direct-RX/RRO Authority Model R2 Session - 2026-09-02 08:11 +03:00

- Built a deterministic safety model for independent direct-RX and RRO release
  authorities plus their aggregate DMA/NPU destructive-action completion.
- The scheduler enumerates 29,400 actor interleavings: 12,600 graph-forget,
  12,600 later-boot, and 4,200 unknown-publication-epoch schedules. Both Windows
  and WSL independently pass 121/121 tests; 38/38 negative mutations are
  killed.
- The model requires validate-all, immutable-snapshot-all, revalidate-all, and
  commit-all direct-RX inventory handling. RRO requires a complete node/edge/
  DMA/session graph and either an exact graph-bound forget acknowledgment or a
  strictly later proven NPU boot epoch. Unknown publication epochs cannot use
  the boot-epoch release path.
- Current report SHA256 is
  `625ca4753d7f62728a54671701e5d86f7e6a5545c621633d1d7284b60230ce84`;
  current evidence-manifest SHA256 after independent rerun/finalization is
  `590bc2701a1fd5c101b1403fb0dfbf871c67353ed98957cb1252d3ca7a43da17`.
- No C source, build tree, firmware image, or router state changed in this
  modeling lane.

## 53d2j Staged Reopen And Terminal Audit Session - 2026-09-02 08:19 +03:00

- Split resume into completion reopen and final TX thaw. Completion leases may
  be admitted only after a new generation is installed, while
  `tx_producer_frozen` and lifecycle admission stay closed until physical
  producers are restored.
- Source gate now enforces both call ordering and the absence of TX unfreeze in
  the completion-reopen phase. It reports 59 pass, 1 intentional fail.
- Commit `6b372d1d35bae8fa3171735dccaac382ea1af57c` compiles all three mt76
  modules for AArch64/Linux 6.18.34. Focused patch SHA256 is
  `8760e31e6d2150c00f0714e217dfd441eaf6fc706a172e33024f7cc2c6b6b9e6`;
  ten-commit recovery SHA256 is
  `2f49862623d0be2e6a6facd0e4d05a920f54149ae50a4a89c08e86874e8a1e6f`.
- Reconciled the independent terminal-work audit against the current tree.
  `cd485a5` closes its checked-IRQ finding and `6b372d1` closes its staged
  reopen finding. Four P0 and four P1 terminal/work/PCI findings remain.
- Durable audit:
  `work/analysis/npu-53d2h-work-terminal-authority-20260902/REPORT.md`,
  SHA256
  `cc071b16f729b30f25bddc8f6ad40abae2a6e80d7f5fd4a674c28db5427fe8a2`.
  No V6.89 integration or router operation occurred.

## 53d2k Permit Replay And Patch82 Compile Session - 2026-09-02 09:05 +03:00

- Recovered WSL and both active source lanes after the power loss. The Ghidra
  HTTP bridge at `127.0.0.1:8089` was down; no analysis was discarded, and
  headless Ghidra remains available.
- Reviewed the completed 53d2k lane. Commit
  `52de75f8c7fcdd3b67055781722c485df548c96b` replaces mutable exported permit
  slots with immutable values and atomically consumes destructive-action
  claims. Source gates, replay/mutation models, strict checkpatch, exact-tree
  replay, and AArch64 build all pass.
- 53d2k report and manifest SHA256 values are
  `2463e39a4a2c1532d17fcf8a019d0e5cf547a206402ee2a7b381ce46606540f8`
  and `cde20acaace0690102eada5fe54906c2d7efe4da8a2310bbd96abb7c58020d40`.
- Made patch82 strict-checkpatch clean, then staged its provider/header into
  the disposable V6.88/provider79 kernel tree. The first command attempt failed
  before compilation because PowerShell consumed the Linux PATH; the next
  compiler pass exposed a `current` macro collision, which was renamed by role.
- Final direct object build exits 0. `airoha_npu.o` SHA256 is
  `e1aa1ef4a1c1798ad31d1373ae56e13f066791d6ebd21877c87ebfa8a88d605f`;
  all twelve new live/identity/RX lifetime exports are present.
- Patch82 remains fail-closed with identity flags zero and is not committed or
  integrated. Independent source/mutation, R2 semantic, stock STOP protocol,
  and official-nightly provider-delta audits were launched. No image, router
  operation, reboot, or flash occurred.

## Patch83 Seal, Nightly Reconciliation, And Exact RRO Map - 2026-09-02 11:28 +03:00

- Recovered WSL after the power loss. Both patch83 source hashes and the exact
  AArch64 object hash matched the pre-loss checkpoint; about 891 GiB remained
  free on the WSL filesystem. No router path was used.
- Final stock RX STOP analysis disproves DMA-silent/frozen/forgotten semantics
  for selector 4 plus GET=0. Post-STOP descriptor, buffer-map, ownership, and
  index mutation remains reachable. Report SHA256 is
  `e4213d8123499f067b11b8aefdf48c361f00d6fb9c5ca9b1a7106d131139cba6`.
- The OpenWrt nightly comparison retained our stronger checked-mailbox/provider
  architecture while identifying five mandatory stable fixes in current
  official code. Eleven selected official mt76 fixes remain compiled in the
  separate V6.89 WiFi lane. The live snapshot was rechecked as
  `r36025-c1992346fc`; no nightly image or package was installed.
- Removed release/rearm authority from patch83, removed raw queue-address and
  void IRQ mutators, limited START to stock selector 2, made STOP flags purely
  observational, added per-ring commit exclusion, rejected DMA overlap and
  32-bit ABI overflow, leased legacy SET/GET/bridge mutations, restored
  IRQ-safe regmap locking, fixed all-eight mailbox lock order, and pinned
  debugfs/provider lifetime.
- Final patch83 commit is `b47ea29c011c91239c6da523879ed596434e7b09`;
  tree is `42701255263f8216ed04088e71074d99f3e4e80b`. Strict checkpatch is
  0/0/0, Windows and WSL each pass 30/30 checks and 43/43 mutation kills,
  AArch64/Linux 6.18.34 compile exits 0, and targeted sparse is warning-free.
  Report SHA256 is
  `56c999ca6cc37b3601faf557d1abd210fcdc6fefff9ad6532c2705ff7ce02a26`.
- Independent audit verdict: acceptable only as a dormant capability-zero
  checkpoint; production remains NO-SHIP/NO-FLASH. Four P0 classes remain:
  absent R2 child authority, disproven silent-STOP capability, no clean origin
  after legacy publication, and no exact supplier/consumer removal authority.
  P1 also requires checked mt7996 IRQ integration, stale-commit rejection,
  host-event quiescence, and separate treatment of the older TX certificate.
- The exact V6.89 ownership/publication/retirement map covered the 524-file
  prepared mt76 tree. RRO-01 through RRO-09 affect the active/shared W1700K
  path; RRO-10 through RRO-12 are alternate-WED hazards. The minimum production
  schema is append-only CaptureHeader, NodeRecord, EdgeRecord, and SessionRecord
  with boot/probe/firmware/transport/queue/map/token/session generations.
  Report SHA256 is
  `41733525172be0c84482a4370d568ede1b8bb0ca1296a59c19b7d9d1511091fd`.
- The next implementation gate is generation-qualified RRO publication and
  retirement modeling, followed by fail-closed fixes for the nine active
  findings and event-aware terminal ownership. No V6.89 rebase, full image,
  router operation, reboot, or flash occurred.

## Patch84 RRO Quarantine And Stock-Authority Session - 2026-09-02 13:15 +03:00

- Built the durable cross-host RRO quarantine model under
  `work/tests/npu-rro-p0-quarantine-model-r1-20260902`. Windows and WSL agree
  semantically: 11/11 tests, 10,092 schedules, 10,062 unsafe/out-of-order
  rejections, 2,282 invariant checks, zero unsafe releases, 9/9 behavioral
  mutations killed, 26/26 source checks, and 21/21 source mutations killed.
- Used headless Ghidra after the HTTP bridge failed to return after power loss.
  The stock session audit proves neither a generation/cookie nor a
  no-reuse-until-release/reset allocator contract. It therefore rejects scalar
  SeID invalidation as R3 retirement authority. Report SHA256 is
  `63b0ea0427acf668d97a14d49bc2e7817694194a97dbdf8051f1ea8ea15df57f`.
- Implemented the fail-closed RRO checkpoint in the isolated branch
  `w1700k-npu-patch84-rro-p0`. Commit
  `af7b349c1981583c383038d3d1dedc58a45363e2`, parent
  `52de75f8c7fcdd3b67055781722c485df548c96b`, and tree
  `46d3d1ca713f6d7e95c12bebef0e401f339036ce` are sealed with a clean
  checkout. The source returns still-owned pages to device DMA ownership,
  quarantines timed-out pages before fault publication, blocks HIF/token/free
  fallthrough, treats ACK-SN as progress only, and permanently quarantines all
  NPU-owned DELETE records lacking generation/no-reuse authority.
- Cycle 4 correctly failed under `-Werror` on a dead label after targeted
  retirement removal. After fixing that label and anchoring the gate to the
  real MCU-reset statement, authoritative cycle 5 exits 0 for AArch64/Linux
  6.18.34. Strict checkpatch is 0/0/0 over 514 lines; targeted sparse exits 0
  without diagnostics on touched translation units.
- Final module SHA256 values are
  `46c6648bb3fdec52c59ec5fc5b1b4a00be52aea49d96909a6c9089eaf806372e`
  (`mt7996e.ko`),
  `e9cecb1db2b2ab94ea07dbb8278e508ad3ba5732aa82e9e9a03af99ef2f98ab5`
  (`mt76.ko`), and
  `e0a8d948729ce84a8b7421284dd7e02f145e155a3e3c88e5ae3b8bda65b1f7aa`
  (`mt76-connac-lib.ko`).
- The stored replay patch hashes to
  `8b20ac28fa032f10ddcb4a5f9fb21df889af23f4f0589c0e2b9789fd810a3de1`.
  The independent full-index/binary stream hashes to
  `64799b10b81c69760ba1e5a19bdc4aead8dd26c0d8d5d2905bcfc25aed611264`;
  both reproduce tree `46d3d1ca713f6d7e95c12bebef0e401f339036ce`.
  Checkpoint and post-commit report SHA256 values are
  `3d9f418696301ef03fd2b0b0d0b283659878e16d1ecc9f370338153e509a1592`
  and `d201f4db2474c6378d530843ab4900e6d859a5291725c707233d210f30aad129`.
- Independent audit remains REJECT/NO-SHIP/NO-IMAGE/NO-FLASH; report SHA256 is
  `02c6200a7c936d57f9192aeef1473fd580c8894b1e8e1e7d9d7170f90cfaa130`.
  The next P0 is terminal quarantine ownership plus return-valued cleanup
  refusal across init unwind, remove, shutdown, and provider disappearance.
  Quarantined DMA identity must not retain embedded pointers into a freed
  `mt7996_dev`/PCI/devres graph.
- The official stable five-fix lane and the patch84 BA/checked-IRQ lane remain
  isolated. No V6.89 integration, image assembly, module load, router contact,
  configuration change, reboot, or flash occurred.

## Patch85 Terminal-Lifetime Recovery Session - 2026-09-04

- Recovered the active goal, WSL build environment, six concurrent audit
  lanes, and the uncommitted Patch85 terminal-owner source after power loss.
  Ghidra HTTP at `127.0.0.1:8089` remained down; headless Ghidra 12.1.2 is the
  active reverse-engineering path.
- Revalidated the cleanup-results rejection and completed independent owner
  and full async-source audits. Their SHA256 values are
  `d491d7af54a2fa2218292a69ba1f26b181a3248ab34c1766a3e246de4efbb9dc`,
  `eff0067b18ea2d2b222d6ba057d1f846665eda24bd706d9f6b131fb17d3be46e`,
  and `8a33c92c5d2db6a75e9c9c3dc3e248ec6032af1a0c15e18d9e4d10341c059b96`.
- Added unsealed source corrections for retained provider reachability,
  checked prepare/prepared free, role-specific DMA-provider references,
  early drvdata, actual bus-IRQ tracking, bound terminal probe success,
  live-checked module pinning, bind/unbind suppression, and non-returning
  terminal remove containment.
- The corrected cumulative diff passes strict checkpatch 0/0/0 over 617 lines
  and compiles as AArch64 modules against the exact V6.89 Linux 6.18.34 tree.
  `mt76-connac-lib.ko`, `mt7996e.ko`, and `mt76.ko` SHA256 values are
  `dd95214811dc57a28f18144afd50d6cf85f55dee74bf2b76de480611b4c0c4ed`,
  `06803349de5f762d0793164c5e3b3950e1f340af118ce848a9588cc932780885`,
  and `87057d16f490133fec9395139093317d68e193a046f3901f7acdb576f69154ab`.
- The checkpoint is not committed or accepted. Full async admission/drain,
  WED/WO terminal quiescence, AER, mutation/source gates, sparse, independent
  re-audit, and integration remain open. No image, router operation, reboot,
  configuration change, upload, or flash occurred.
- Refreshed official nightly evidence to `r36045-aa66786f38`, Linux `6.18.44`,
  mt76 `be5ce791`; report SHA256 is
  `82e24c2de4cdd052349fc0ea5b567f2c208be7e6335417ee43a1478ab028e662`.

## Patch85 Daybreak Terminal-Quiesce Session - 2026-09-04 07:22 +03:00

- Recovered the exact WSL source/build lane after power loss and retained the
  unsealed baseline commit
  `eb9bb562bb54ad740e396072c84603dc36c5b000`. The current replay checkpoint
  SHA256 is
  `49e0eb8b014208ab81081a6b27cc2d09b1b0ecce73ad5dde6ff99e8a838b7274`.
- Extended the terminal coordinator across IRQ admission and exact IRQ-action
  retirement, tasklet/NAPI and delayed-work drains, queue stop, RRO stop,
  polling-based NPU STOP, physical completion-source disable, mac80211 callback
  retirement, destructive-cleanup separation, pending RRO/RC-state handling,
  idempotent thermal/coredump unregister, quarantine containment, and AER-safe
  MMIO suppression.
- The generic model now passes 20/20 tests over 309 schedules and kills
  100/100 mutations. Report SHA256:
  `5daa1aec6a6373e860c5043b24a5514b94aa48e5f4bc31d16eebbe0773f2b97e`.
  Cross-driver BA verification passes every requested compile/sparse/modpost/
  disassembly gate; report SHA256:
  `7a709db700696b5052f3059d039d6a19a7ec84ccff3a341e3330470cd1443272`.
- Headless/source authority work confirms that the EN7581 eight-core reset
  (`0x1fb00830`, mask `0x200`) is useful fail-closed containment but does not
  prove DMA release. Report SHA256:
  `f983bcb0325ee97ef83a9d26183d3b068b7a1ebf9cd65ec94c86d278b0fab596`.
  The stock terminal audit likewise found no proof of terminal silence after
  STOP/GET; fail-closed quarantine remains required.
- Staged an exact-applying mac80211 patch to kill `wake_txqs_tasklet` during
  hardware unregister; SHA256:
  `a3fc6058f9033027ce81faf904926bd33f34c039377e62ec0181c194cbfc35ca`.
- The latest exact AArch64/Linux 6.18.34 component build exits 0. Module SHA256
  values are
  `62189e5df095153269cbfe214520c7147523145cd076c46eb49a3d25ed419190`,
  `d2d29cdef5a1e6eae6b7afb30ebf723a7e55c15308f98789bd55b600b015d9c5`,
  and `0ef9a2cc2504b7249dfb71f2dcd99d463a6db1d527a3c0c86c89d0b98bf06c9b`
  for `mt76-connac-lib.ko`, `mt7996e.ko`, and `mt76.ko`; compile-log SHA256 is
  `8347a12d671b2d9559b1d519ce79687054517a4f53443dbff092d5c0ea9035ea`.
- An intermediate AER compile failed on `READ_ONCE()` against a bitfield and
  was corrected before accepting output. The last pre-final checkpatch run is
  0 errors, 1 warning, 18 checks; latest-AER checkpatch, sparse, NPU-disabled
  compile, WED-r2, source/callback audit, coordinator model, and Ghidra binary
  audit remain open.
- No full target/image build, router contact, module load, configuration
  change, upload, reboot, or flash occurred. V6.87 remains authoritative.

## Patch85 Terminal Lifetime-Order Audit - 2026-09-04 08:03 +03:00

- Performed a read-only ownership/order audit of
  `work/source-stage/npu-mt76-patch85-full-terminal-20260904/patchwork`
  against the exact OpenWrt backports source at
  `/home/captain/w1700k-openwrt-build/v689-build-full-20260902/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/mac80211-regular/backports-6.18.26`.
- **Verdict: FAIL / DO-NOT-BUILD / DO-NOT-FLASH.** Five P0 lifetime failures
  remain: station private storage, vif/link private storage, post-unregister
  WCID/TX-status cleanup, incomplete tasklet retirement, and unsanitized
  NPU-retained TXWI/SKB metadata.
- The minimal safe order is: serialize terminal ownership; drain all producers
  while mac80211 objects remain valid; freeze/STOP the NPU; partition host and
  NPU SKBs; complete host-owned status; detach and scrub NPU-owned metadata;
  run host-only station/vif/stop callbacks; bracket all relevant mac80211
  tasklets; unregister exactly once; then perform hardware-only cleanup.
- An ordering-only fix is impossible. New detach/scrub and host-only terminal
  callback paths are required before unregister. RX/RRO resources without a
  release certificate must remain sanitized and quarantined until reboot.
- The authoritative lane remained unedited by the audit. A state transition
  from opening diff SHA256
  `3e971633cc947be7e810c58f5a1e580d56c760b876ed542e4adffc118157f93b`
  to final diff SHA256
  `f4c31e2acdb1c7addf3b13e23ea0f7cc3f800f258db88f18357ea91504b0f9bd`
  was detected and recorded; all final `mt7996/init.c` citations were re-read
  against final SHA256
  `6fd6325633bf211ad6a42a9fd7627d0405e6cb6881a381623abd5e50a8f4bb0c`.
- Report:
  `work/analysis/patch85-terminal-lifetime-order-daybreak-20260904/REPORT.md`,
  SHA256
  `222ecfb0c852d122367894f6ec80a233cc6531b58b8e18f7e8cd254d97183d26`.
  Evidence and source fingerprints are in the same directory. No build, image,
  router contact, configuration change, upload, reboot, or flash occurred.

## Patch85 Daybreak P0 Lifecycle Repair Session - 2026-09-04 09:05 +03:00

- Resumed the active goal after power loss and revalidated the authoritative
  dirty source lane, exact WSL build tree, and tracker boundary.
- Consumed the independent adversarial audit at
  `work/analysis/patch85-current-terminal-adversarial-daybreak2-20260904/REPORT.md`.
  Its verdict is NO-GO: four P0 ordering/admission failures and one P1
  host-graph cleanup failure remain independently actionable.
- Added an explicit ADD-drain gate state, delayed RETIRE admission until ADD
  reaches zero, leased whole scan/ROC worker invocations, moved terminal
  scan/ROC drain before completion teardown, and moved MCU shutdown before
  WFDMA/MCU queue destruction.
- The first resumed exact build correctly failed modpost on direct
  `lockdep_is_held` references. After removing those non-exported runtime
  dependencies, the exact AArch64/Linux 6.18.34 component build exits 0.
  SHA256 values are
  `9cf009563f0f278a1d10372d80c9aa05e4b11d6cdf4c7849656098ba0860e369`,
  `a1854f50bfbc777273dd0cfcf4185fd3b353dfeb26005328056b9f9d7bc887a0`,
  and `ab92c310e97d510525232e1fc51523eadc0533bd4583841b0508fad69436d9fe`
  for `mt76-connac-lib.ko`, `mt7996e.ko`, and `mt76.ko`.
- Six independent Daybreak lanes are running for final ELF/Ghidra proof,
  callback coverage, a corrected gate model, NPU RX ownership, RRO ownership,
  and stock host-adapter parity. Source integration remains local to the main
  lane.
- No full image was built, no router was contacted, and nothing was flashed.
  Callback/VIF, owner/AER, RX/RRO, strict latest-diff, and independent re-audit
  gates remain open; V6.87 remains authoritative.

## Patch85 Explicit-Lease, RX, and Ghidra Session - 2026-09-04 09:58 +03:00

- Propagated explicit ADD/RETIRE lease class through nested channel, scan/ROC,
  vif-link, callback, worker, reset/dump, watchdog, reorder, TX, and NPU-fault
  paths. Existing ADD admission is now authoritative for the entire protected
  synchronous call; inner code no longer changes class after ADD_DRAIN begins.
- Added full-slot clearing for direct NPU RX ownership transfer, drop, scatter
  source reuse, and destination reuse. This closes a concrete stale queue/
  descriptor alias and double-recycle risk while preserving the fail-closed
  RX/RRO release boundary.
- Exact AArch64/Linux 6.18.34 build exits 0. SHA256 values are
  `d17c82fcd7067efc310c56696347f97cf0e2c9c64c10ea3b71ce5025df11064f`,
  `a1c14904d951869c210e8edd4de1df02439e1221185cdb526c6493faa640bdaf`,
  and `03765191bcf27bfc7d5632f99942caa755d5edfbe3644c6c0345b9b5f00516b2`
  for `mt76-connac-lib.ko`, `mt7996e.ko`, and `mt76.ko` respectively. Build IDs
  are `0d35024168ee0138720f09f1ff481d63eccd0bb1` for mt7996e and
  `df3b13722fca1ee16f89ab00e47030da291b4dde` for mt76.
- The refreshed source model passes 326 assertions, 40/40 mutants, and 10/10
  interleavings with zero deadlocks. Source and terminal fingerprints are
  `a44a44d516afcd3c4712f8b6598188870d2a5d8cac6ac1a9a201a2001f06f55e`
  and `917ffcce9de9c6184d3e53ec31ea407c43d0e24927415d74a134b8532fcd8ccf`.
- Full Ghidra/headless stock analysis exported 1,040/1,040 functions and
  checksummed 1,383 artifacts. Stock validates the two-ring topology,
  five-descriptor reserve, per-ring TX lock, owner-last descriptor publication,
  physical-address RRO lookup, and bounded observations. Its unsafe scatter,
  token, and RRO reclamation behavior remains negative evidence only.
- The explicit-token design audit accepts a slot-table/generation/nonce ABI and
  atomic ADD-to-OWNER promotion, but rejects the current aggregate-count source.
  This is the next implementation gate. Completion propagation, provider
  lifetimes, and RX/RRO provider certificates remain open.
- No full image, router contact, configuration change, module load, upload,
  reboot, or flash occurred. V6.87 remains authoritative.

## Patch85 Explicit Owner-Token Session - 2026-09-04 10:35 +03:00

- Implemented exact stack-token identity, device/cookie/generation/nonce slot
  validation, atomic owner promotion/adoption, bounded ADD/RETIRE drains, and
  owner-only phase transitions. Terminal requests now execute inline or on an
  ordered `WQ_MEM_RECLAIM` queue and publish a single completion to joiners.
- Added fail-closed owner/device/module lifetime roots, phase-checked mac80211
  retirement, saturating cookie allocation, registration-failure rollback, and
  a prepared-free latch. Scan/ROC terminal cleanup borrows the elected owner
  token instead of acquiring an unrelated nested lease.
- Exact Linux 6.18.34 AArch64 `-Werror` build exits 0. SHA256 values are
  `85f0741227a13b8d1d36fe181c93e50ed46efb53f10b7b039f37118b136ded42`,
  `519799295412b7e46fb78229cbce691609dd1d97e7974eebc9a6bd284f1155e5`,
  and `14d0520d9e3c7e139421e4f0d6699f377abef55f7835444fb0f7b61f6e81ed0a`
  for `mt76-connac-lib.ko`, `mt7996e.ko`, and `mt76.ko` respectively.
- Sidecars reject release at this snapshot: official TWT/MLO/monitoring
  backports need rebasing; completion/IRQ authority still needs explicit
  propagation; provider detach ordering is not yet terminal-safe; RX/RRO must
  retain the graph and require reboot. No full image or router operation was
  performed; V6.87 remains authoritative.

## Patch85 Generic Receipt/Free Model Session - 2026-09-04 11:20 +03:00

- Scoped the current P1 free-transaction audit to generic `mt76.h` and
  `mac80211.c` semantics without editing either source file.
- Designed a separately allocated receipt that survives `mt76_dev`, exact
  graph-proof receipt minting, persistent parked/broken owner authority,
  pre-NPU prepare claim, absorbing NPU failure, atomic array detachment, and
  exact-once final free.
- Executed six exhaustive schedules totaling 194,829 unique states and 414,536
  transitions with zero reference-model violations. All 8 functional checks
  passed and all 12 deliberately unsafe mutants were detected. Two independent
  JSON replays were byte-identical; the recorded text result matched a final
  replay exactly.
- Confirmed seven current-source gaps: boolean free authority; absent receipt,
  free-state, and `PARKED` types; no graph callback at owner completion; NPU
  deinit before claim; and array free after gate unlock.
- Evidence:
  `work/analysis/patch85-free-transaction-daybreak7-20260904/REPORT.md`, SHA256
  `e0e63a783e204ae1e173c666ca2d449aacb9262345501c16a9c385ca61272dba`.
  `SHA256SUMS.txt` verifies all four substantive artifacts. No kernel source,
  build, image, router, configuration, upload, reboot, or flash was changed.
  The release gate remains closed and V6.87 remains authoritative.

## Patch85 Daybreak Power-Loss Resume Session - 2026-09-04 12:05 +03:00

- Recovered the active unlimited goal, source branch
  `w1700k-npu-patch85-full-terminal`, four sidecar audits, exact WSL build
  environment, and all prior Ghidra evidence after the host power loss.
- Rebuilt the untouched resumed source first. The exact OpenWrt AArch64 GCC
  14.3.0/Linux 6.18.34 `-Werror` component gate exited 0 with only the three
  pre-existing `MODULE_DESCRIPTION()` warnings.
- Applied two narrow authoritative DMA repairs in `dma.c`: an RRO page-add
  failure now removes the just-consumed RX token, validates the exact txwi,
  clears and returns it only on exact ownership, and fail-closes/leaks rather
  than recycling ambiguity; completion refill now checks `emi_cpu_idx` before
  use. Current `dma.c` SHA256 is
  `73b4cdf2873667a8b4a1a53e391bf1f4f6871f83b8f1453d50fc02d171c243a1`.
  The post-edit component build exited 0. Module SHA256 values are
  `9bcd0e7bd546b8a289ed7e9be2ff6116ee2f070aed7d8c0d0e83340d0cd00082`,
  `e0af076200e5ee9dc97c7299f71b8895a81aa74479ca5d72c11a7fa88c293ec9`,
  and `0cf2a96bb7329a36f1c0cef81abca16a265cc93a5b82350c931c7fab1c78d3d1`
  for `mt76.ko`, `mt76-connac-lib.ko`, and `mt7996e.ko`.
- Rebuilt the corrected isolated completion-P0 patch successfully. It closes
  the modeled fatal-epoch and stack-registry defects, but a parent review found
  `mt7996_poll_tx()` still performs IRQ rearm between guard begin/end without
  the atomic publication callback. The sidecar therefore remains unmerged.
- Current-source coordinator re-audit selected the split architecture: the
  ordered worker publishes only a proven QUIESCED handoff and the exact elected
  caller performs operation-specific cleanup, graph commit, receipt prepare,
  and final publication. The unsafe outer timeout must be removed; inner
  ADD/RETIRE drains stay bounded. Followers wait for final publication and can
  never acquire cleanup authority.
- Current-source receipt re-audit verified the typed mt7996 happy-path kref
  ledger but found a P0 `void mt76_free_device()` caller boundary plus four P1
  defects: legacy timeout receipt leak, non-absorbing identity failures,
  teardown-time allocation, and unbounded NPU init/deinit waits. Isolated
  implementation/build/model work is in progress.
- The typed DMA-publication sidecar covers every audited address-class provider
  send with sticky `MAYBE_EXPOSED` state and changes Airoha device links to
  consumer autoremove. The WiFi drift audit identifies eight missing official
  mt76 fixes, three cross-layer MLO validation defects, and four missing
  official AP-MLD hostapd fixes. Both lanes remain candidates until clean
  compile/rebase tests finish.
- Ghidra MCP HTTP was refused after power restoration. Headless Ghidra 12.1.2
  remains installed at `C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat`;
  no Ghidra project or evidence was lost. No image, upload, router contact,
  configuration, reboot, or flash occurred. Release remains NO-GO and V6.87 is
  the authoritative recovery image.

## Patch85 Three-Way Isolated Integration Session - 2026-09-04 12:37 +03:00

- Recovered and independently reviewed the publication, generic receipt/free,
  and mt7996 coordinator sidecars after the power loss. Their portable patch
  SHA256 values are `19933e2dfd73e9bd15e1be2a7a6c77f45c766c51e1d41a8513b07864c2d981b1`,
  `739fd00a5352a96ce4d689e268f850c6f35e24fb100303d97fd3e980136fd17d`,
  and `8612ddbcea32e68fb81c0378201c7078ef6c06a9bca8e71133af8c401ed33f19`.
- Composed all three in a disposable mt76 tree. Their overlapping `mt76.h`,
  `npu.c`, and mt7996 hunks applied cleanly; the publication, receipt/free, and
  coordinator executable models all pass against the composition.
- The exact AArch64 `-Werror` build exits 0. Module SHA256 values are
  `b59280b51282cea90bf1f4efe40edb13409068e5b5612de3b555ae18efd8322c`
  (`mt76.ko`),
  `ff8476c29880ec027d86f7590700959def5a406bf67cb2de093e2bcb9959ad2e`
  (`mt76-connac-lib.ko`), and
  `bee65335e591aa8a266c0f9b043846e7b4944ea6cc66a0018484504419c6bbf3`
  (`mt7996e.ko`). Only the existing missing-`MODULE_DESCRIPTION()` diagnostics
  remain.
- Evidence reports are bound by SHA256
  `6045fe5a26d295b13c07308159ab91487f626f8b3f0402b3a364d74b2df4f3c8`,
  `bc21fdc7f1186c55567e99b884c1c0877e95c299246897934bf7184d0d93a63b`,
  and `8580a601e2fdbb4017bc16d76e86450d27c2d4d5a06f72e1a4d5b1537ad24d0a`.
  Reset/restore authority and refill/fatal design reports are additionally
  bound by `6f66cc6dfc33c4cbeadc8536d25904c91cee53d0b67ed647a5cc138f5dac9e95`
  and `c58baf35362bca084205413059a425ba8f97d08359d7d76d960cd68399b10d49`.
- This is an isolated compile/model checkpoint, not promotion. Hostile
  coordinator review, completion IRQ closure, WiFi restoration, provider fault
  injection, and runtime validation remain open. No authoritative source,
  image, upload, module load, router configuration, reboot, or flash changed.

## Patch85 Four-Way Integration Session - 2026-09-04 13:16 +03:00

- Recovered after power loss, verified WSL health, and removed only 13 completed
  disposable WSL builds after realpath allowlist checks. The completed WiFi
  worker removed its own verified 15 GiB disposable tree. Five later
  coordinator/four-way build trees were similarly removed after preserving
  logs and one exact module set. Authoritative source, exact V6.89, active agent
  trees, images, and V6.87 were excluded from cleanup.
- Hostile coordinator review reproduced three defects and supplied correction
  patch SHA256
  `9bf51bed91f29305046a5ad02f5a84e5acd8e44aea2f144d4181f1cedb54aa83`.
  Completion hardening patch SHA256 is
  `fba1b65362c58057f524673d396b47b0df04efa568b50cd507676b3cebc1d171`.
  Both apply cleanly after the prior three-way composition.
- The six-model combined run passes publication 77+15, receipt/free
  32 callsites/71 races/8 mutants, coordinator complete phase coverage,
  coordinator hostile 3-to-0 defect reduction, completion 48,048 schedules plus
  seven faults and eight mutants, and 51/51 completion source assertions.
- The first two clean builds exposed only destination-path debug/build-ID drift;
  stripped loadable content was identical. The harness now maps source,
  debug, and macro paths. Two subsequent clean exact AArch64 builds are fully
  byte-identical with hashes `5495536c...`, `9a62e4ef...`, and `46889a65...`.
- Daybreak13 evidence has a 242-file source hash manifest, 50-file evidence
  manifest, preserved modules, build/model logs, and report SHA256
  `a3126902cd0763adead5bf9a543b11c96625c87e2411eaafcbae26e0c91384a1`.
  No full image or router action occurred. Independent completion interaction,
  reset/RESTORE, refill debt, WiFi follow-up, Ghidra parity, provider/runtime,
  and FIT/DTB gates remain open; release stays NO-GO.

## Patch85 Ghidra And Stock-Parity Session - 2026-09-04 13:41 +03:00

- Ran full Ghidra 12.1.2 auto-analysis over the reproducible Daybreak13
  `mt76.ko`, `mt76-connac-lib.ko`, and `mt7996e.ko`, then exported focused
  decompilation/call graphs for completion, terminal owner, quarantine,
  probe/remove, NPU IRQ/refill, initialization, deinitialization, and
  prepared-free paths. All resolved targets decompiled successfully; absent
  standalone helper names were verified as optimized into retained parent
  symbols.
- Compiled-object review confirms the queue-rejection completion and unload
  REMOVE lifetime corrections, guarded TX/RX completion publication, complete
  physical Airoha/WFDMA/dual-HIF masking calls, RCU provider teardown, and
  prepared-receipt free ordering. It also confirms that an RX allocation
  shortfall can be forgotten when no refill is published; this is now assigned
  to a separate Daybreak14 closure lane.
- The independent stock-provider audit verified all six stock input hashes,
  fully analyzed five binaries, inventoried 1,233 functions, and resolved
  54/54 parity targets. Its matrix is 9 implemented, 2 modeled-only, 3 missing,
  and 5 intentionally non-portable. It corrects two historical assumptions:
  stock releases the generationless WiFi token before hostadpt handoff, and the
  RV32 dispatcher has only selectors 0 through 4, not selector 7.
- Restored the original 242-file Daybreak13 source-manifest identity after a
  local manifest-regeneration scope mistake. Source files never changed.
  Current source-list SHA256 is `8076dba64f181e7092659ce8064ec7a910aa14ed9d18d35480755fdbf9a36d42`;
  77 evidence hashes and 78 manifest entries verify with zero mismatches.
  Ghidra review SHA256 is
  `fdbb2d63fd1e401caf5cb1015b8b01d4b566e0be0b7615805f5ebf7c5ed42c05`;
  evidence-list SHA256 is
  `2c0e6c31915bc18539a7117f8c19752ee6c1363d184474d131015a36e4986c5d`;
  manifest SHA256 is
  `415dedfb9d4389b663dc5b27a56a3126d50796f366555e9de088d88ec05e8d99`.
- Stock audit report SHA256 is
  `afb5cac349996b04feaec0f39a2c91324a47860ea82d52dae72c78208617cbff`;
  its parity-matrix SHA256 is
  `07cc7f909f2e0ce3c982d0ab969b5d8bf7aba254b19b0056f35f14282b65fcb7`.
  No source integration, image, upload, router contact, reboot, or flash
  occurred. Reset/RESTORE, RRO release, provider detach runtime proof, refill
  debt, WiFi integration, full-image, and target gates keep release NO-GO.

## Patch85 Reset And Upstream-Drift Session - 2026-09-04 14:01 +03:00

- Completed the isolated reset/restore finalization lane: 125/125 source
  assertions pass, 256/256 hostile combinations reject partial physical reset,
  and two exact AArch64 `-Werror` builds are byte-identical. Reset while NPU is
  active remains deliberately blocked with `-EOPNOTSUPP` before physical
  writes; the provider exposes no restart receipt, boot epoch, or complete
  buffer reconstruction. Patch SHA256 is
  `75d068f59f352ac796e9880a473ccefd08208b66d416c4850efde13771429277`.
- Audited current official source instead of treating filenames as provenance.
  OpenWrt HEAD `28ba2708f1f609bfd134975808b2bc6ed9dc9742` selects mt76
  `be5ce7910521492d4a2e4ce7ee3843680a46c047` and backports `7.2`; the exact
  V6.89 tree uses mt76 `b2704cf5a4068b672bf47ad5bf6b4802b6770a90`
  and backports `6.18.26`.
- Found nine compatible official mt76 fixes dropped from active Daybreak13
  sources and retained only in `.orig` files. Restored them in isolated
  `patch85-upstream-nightly-refresh-daybreak14-20260904`. Its 20/20 contract
  checks and exact Linux 6.18.34 AArch64 `-Werror` build pass. Module hashes are
  `394bf0f398744034156b0ed759ef90da2cb4c562eb592e1e4551c3b432f9aac5`,
  `eb35c91429fafa120965417d94c800bb5233961c6945605906cfd82b82027864`,
  and `704b91a89d30a2b5ee314b93f95e4794b42b47c51fa5481047d65f314ef32532`.
  Restoration patch SHA256 is
  `8ba6cbf749ff3e3026b1b4747a1a5dd41bfde89b5fc904c1d1c426d8d1b9d02b`.
- New 7.2-only action/FILS changes are not being forced into 6.18.26; an
  explicit compatibility audit is active. Completion integration,
  refill/fatal-debt closure, and WiFi gap closure are active in separate lanes.
  C: has about 5.3 GiB free, so redundant builds and destructive cleanup are
  paused. No authoritative-source, image, upload, router, reboot, or flash
  action occurred. Release remains NO-GO / NO-IMAGE / NO-FLASH.

## Patch85 WiFi Gap-Closure Session - 2026-09-04 14:09 +03:00

- Reviewed and hash-verified the completed three-patch WiFi gap sidecar. It
  replaces radio-0 MLD MAC anchoring with first-participant anchoring, separates
  LuCI radio-local facts from one aggregate MLD owner card, and restores the
  official ucode `iwinfo` scan-wrapper ownership split in `wifi-scripts`.
- Exact hostapd/wpad, wifi-scripts, and both affected LuCI package builds pass,
  along with adversarial MLD ordering, malformed input, radio-value mismatch,
  reversed runtime order, null/fallback, ownership, payload, syntax, and prior
  MLO/radio fixtures. `SHA256SUMS.txt` verifies with zero mismatches.
- Report SHA256 is
  `ced46cdf1e211980eac4784ed5e6904ad9bccacd3fba8e803a35a07619a4e418`;
  patch hashes are `5e14bb46903a0068c3a953ad265826e8fd6983fb4d2beec01459d8c2e251ab5c`,
  `5719cfdc7668a8ee46ee6895f3b2132e85971d715643b186ab42fe000f350400`,
  and `bad9ddb20497bee0a4711ecc859e8855a958a2763cb9be23b91f389f6dfaa432`.
- Runtime association, scan/join, live LuCI, memory, throughput, regulatory,
  and full-image/profile gates remain open. An independent adversarial review
  is active. No authoritative source, image, router, reboot, upload, or flash
  action occurred; release remains NO-GO / NO-IMAGE / NO-FLASH.

## Patch85 RX Refill/Fatal-Debt Session - 2026-09-04 14:22 +03:00

- Closed the isolated RX underfill/debt lane in `dma.c`, `npu.c`, and
  `mt7996/init.c`. Both generic and dedicated NPU refill now require exact
  depth before publication; inherited/allocation/publication/scatter debt is
  durable and blocks IRQ scheduling/rearm; fatal closure stops physical
  consumption; teardown clears debt only after ring resources are absent.
- The correction passes 1,200 modeled schedules versus 1,079 baseline
  failures, 45/45 source contracts, 22/22 mutants, and two byte-identical exact
  AArch64 `-Werror` builds. Hashes are `8bb5c65a...`, `9a62e4ef...`, and
  `a963819b...` for the three modules.
- The patch applies cleanly to the nightly-restored Daybreak14 tree. Report
  SHA256 is `c680f8f9a7f72c82e8ca0602890515cd2d8d8095e867b200d8121e68fa00a1f1`;
  patch SHA256 is `f99af95e52811bd1bacaac12f061d34cd68a5fc50ed9b6cfcf988ac025497d9c`.
  Disposable WSL builds were removed. No authoritative-source, image, router,
  upload, reboot, or flash action occurred. This is composition-GO only;
  overall release remains NO-GO / NO-IMAGE / NO-FLASH.

## Patch85 Daybreak15 Semantic-Composition Session - 2026-09-04 14:41 +03:00

- Resumed after host power loss with WSL and Ghidra MCP health restored. The
  isolated Daybreak15 mt76 candidate composes nightly restoration, completion
  P0 correction, reset/restore finalization, and refill/fatal-debt closure.
  Three reset/refill conflicts in `npu.c` were resolved semantically: preserve
  ownership-before-gate serialization, use the locked publication helper from
  the NPU refill critical section, and retain exact-depth durable debt plus
  IRQ/NAPI refusal while debt is live.
- Source/model results: nightly 20/20, completion 57/57, refill 45/45 and
  12/12 source mutants, refill 0/1,200 corrected schedule failures, reset
  127/127, reset 255/255 partial capability sets blocked with zero physical
  writes, and completion 168 modeled cases with no corrected violation.
- Integration-specific copies of two old harnesses now inspect named structs
  and the composed lock/call topology. This replaced stale exact-count/string
  assumptions; no semantic gate was removed. The original evidence harnesses
  and all protected inputs remain unchanged.
- A separate compatibility audit staged paired mac80211/mt7996 per-link
  discovery-template patches and exact-build evidence. Runtime MLO remains
  required, and the 7.2-only action-layout consumer is intentionally deferred.
- No authoritative-source, image, upload, router, reboot, or flash action
  occurred. Exact cross-build, reproducibility, final-binary Ghidra, full-image
  identity, and hardware gates remain open. Release remains
  NO-GO / NO-IMAGE / NO-FLASH.

## Patch85 Daybreak15 Binary/Ghidra Session - 2026-09-04 15:04 +03:00

- Completed two exact AArch64 `-Werror` builds of the composed candidate.
  Module hashes are byte-identical across runs: `415070c2...` for `mt76.ko`,
  `eb13a0e4...` for `mt76-connac-lib.ko`, and `3b901096...` for `mt7996e.ko`.
- Ran full Ghidra 12.1.2 auto-analysis over the exact first-build modules.
  Recovered 2,258 functions total and completed all 31 requested target
  decompilations. A deterministic verifier passes 29/29 checks. It confirms
  the ownership-lock/inner-gate publish path, exact refill depth before
  doorbell publication, refill-debt gating, provider/host fatal masking,
  provider-before-host restore ordering, and `-EOPNOTSUPP` before active-NPU
  physical DMA reset. Four reset/restore APIs remain intentionally unwired.
- Sealed 72 portable Ghidra evidence hashes. Report SHA256 is
  `b8319f794bdee766566c4ebd3aa0e9783baca9a40ded506416945802ed33a7f2`;
  verification JSON SHA256 is
  `ba08bf2d3e1ff97ee8fd06a3ff1cd1f21a98ede3171ba8c0002fe085a3125083`.
  The malformed user UI-template XML and DWARF variable-expression diagnostics
  were non-fatal; no analysis/import/post-script timeout or failure occurred.
- Generated an LF-only, eight-file portable patch and proved clean apply plus
  byte-for-byte normalized reproduction. Patch SHA256 is `9b0e22b8...`.
  Strict checkpatch reports zero errors, 14 memory-order-comment warnings, and
  59 formatting checks; cleanup is isolated and active rather than altering the
  proven candidate mid-review.
- The independent WiFi review reproduced four gaps and produced correction
  commit `b380a1fd2ff06911caa4a2877f58ded69d515eab`: shared per-PHY MLD MAC
  reservations, configured-owner LuCI MLO retention, physical-band-validated
  channel/frequency reporting, and optional/scalar normalization hardening.
  Corrective report and patch hashes are `79d65f4a...` and `7b028333...`.
- No authoritative-source, image, router, reboot, upload, or flash action
  occurred. Independent NPU lifecycle and 345-patch semantic reviews remain
  active. Release remains NO-GO / NO-IMAGE / NO-FLASH.

## Patch85 Daybreak18 Corrections And Full-Series Audit - 2026-09-04 16:48 +03:00

- Re-ran and independently verified the refill-close sidecar aggregate gate:
  309 policy states, 146/146 candidate schedules, 23 compiled Ghidra checks,
  and 40 aggregate checks pass. Baseline has 42 debt outcomes and the negative
  final-mask mutation has 36 unsafe outcomes. Two exact AArch64 builds are
  reproducible (`mt76.ko=de9f13aa...`). Report and patch SHA256 values are
  `8d3c2a2f...` and `1bd8fac5...`.
- Re-ran the lifecycle P2/P3 sidecar: 22 source assertions, 65 fatal schedules,
  769 resume schedules, 13 recycle schedules, 11 compiled Ghidra checks, and
  1,192 retained hashes pass. Two exact builds are reproducible
  (`mt76.ko=419c136a...`, `mt7996e.ko=79278735...`). Strict checkpatch has zero
  errors/warnings and three formatting checks reserved for final composition.
  Report and patch SHA256 values are `3a7a6a8f...` and `36037b35...`.
- Completed packet-telemetry gating: successful/empty RRO, TX publication,
  IRQ, RX, scatter, and preflight writes use the existing static key; integrity
  failures and context remain unconditional. Strict checkpatch is clean, two
  exact builds reproduce (`mt76.ko=abd67ec0...`), full Ghidra identifies 848
  functions and verifies the empty-kick return before exclusive bookkeeping,
  and all 1,097 hashes pass. Report/patch hashes are `c8391c45...` and
  `8bc1c112...`.
- Corrected nine false/overstated debugfs evidence values. Source-delta checks,
  portable replay, strict checkpatch, two exact reproducible builds
  (`mt76.ko=7a75022c...`), embedded-string verification, and 24 hashes pass.
  Report/patch hashes are `9e50a042...` and `938ee5c2...`.
- Finished the exact 113-path complement audit, closing semantic coverage of
  all 345 patches with zero overlap against the prior 232. All 1,157 hashes
  pass. Three P0 current-nightly hazards require semantic migration: split
  kernel/mt76 NPU ABI, old LRO/custom FastTX versus HW-GRO, and rewritten
  920-12 RCU QDMA/QoS ownership. Report SHA256 is `3bf369d3...`; focused
  migration reviews are running in isolated sidecars.
- Space recovery was exact and logged: 41 WSL generated directories totaling
  9,772,818,432 bytes (`WSL_CLEANUP_20260904.log` SHA256 `25ff81d1...`) and
  2,444 RDP auto-trace ETLs totaling 15,726,018,560 bytes
  (`RDP_AUTOTRACE_CLEANUP_20260904.log` SHA256 `334074b4...`) were removed.
  Protected source/evidence/release/image/backup paths were unchanged.
- Daybreak19 semantic composition is the next local action. No authoritative
  source, image, router, reboot, upload, or flash action occurred; release
  remains NO-GO / NO-IMAGE / NO-FLASH.

## Patch85 Daybreak19 Composition And Migration Session - 2026-09-04 17:18 +03:00

- Composed refill-close, lifecycle P2/P3, telemetry gating, and evidence-wording
  corrections in an isolated mt76 repository. The semantic head is
  `e4af35856bbcc7cf9cf95da10d8167cc9acf11cd`; final style-clean head is
  `03680307cb0f2586af9e56f5b2f994e5288105f8`. The ten-file patch hashes to
  `f4f83cf09000917a33c29618661b4c1c615fdbfdb1bcca3216dd7fbe29cfb1d5`.
- Re-ran 14 aggregate gates. All source contracts, hostile schedules, fault
  injections, exact-refill mutants, completion mutants, and 256 reset
  capability combinations pass. Strict checkpatch is completely clean.
- Built twice against the pinned Linux 6.18.34 tree with AArch64 GCC 14.3.0 and
  `-Werror`; all three modules are byte-identical between runs. Exact hashes are
  `270f9f6f...`, `eb13a0e4...`, and `cea0696c...`.
- Ran full Ghidra 12.1.2 auto-analysis on all three exact modules. Function
  counts are 847/240/1170; 49/49 requested decompilations complete and 35/35
  verifier checks pass. Added direct ELF-symbol proof for both default-off
  static keys. The only diagnostics remain the known malformed user tool XML
  and partial DWARF expressions. Report/verification hashes are
  `9f354443...` and `d86093ef...`; all 129 retained hashes verify.
- Independently reran the three Daybreak19 migration audits. WiFi/MLO passes 17
  WSL gates and 548 hashes; GRO/FastTX passes 51 source checks, 60 ownership
  cases, and 189 hashes; QDMA/QoS passes 32 aggregate checks and 207 hashes.
  Only isolated WiFi composition and the one-line GRO_HW advertisement are GO.
  Dormant FastTX and the QDMA provider/NPU teardown migration remain NO-GO.
- No full source candidate, image, router contact, upload, reboot, or flash was
  performed in this session. Current device profile identity remains
  `gemtek_w1700k-ubi`. Overall release remains NO-GO / NO-IMAGE / NO-FLASH.

## Patch85 Daybreak20 Recovery And Storage Session - 2026-09-04 18:18 +03:00

- Recovered after host power loss. WSL starts normally; the OpenWrt worktree is
  clean at `8e813125739179533fb2a59ded89bd8cb879b344` and mt76 is clean at
  `be5ce7910521492d4a2e4ce7ee3843680a46c047`. Full `git fsck --full
  --no-dangling` passes for both repositories.
- Stopped and closed five concurrent agents when `C:` fell to 0.32 GiB free.
  Their requested reports were incomplete. Removed only seven explicitly named
  reproducible source/fixture copies from the two incomplete Daybreak20 audit
  folders, plus five stale Temp folders: old Visual Studio extraction,
  diagnostics, WSL crash cache, stock-RRO scratch, and official-OpenWrt scratch.
- Retained all 92 closed child-agent JSONL transcripts via lossless NTFS
  compression: 67,445,181,473 logical bytes now use 57,578,033,152 bytes.
  Current-parent and unrelated session logs were excluded by parsed JSON header.
- Trimmed and compacted only `D:\WSL\Ubuntu\ext4.vhdx`; it reduced from 97.14
  GiB to 71.12 GiB and `D:` free space rose from 3.77 GiB to 29.80 GiB.
  `D:\W1700K-Recovery\Ubuntu-pre-recovery-20260831-123823\ext4.vhdx` remained
  read-only at 63.93 GiB with its timestamp unchanged. Post-restart checks show
  no ext4/I/O error and both Git object stores verify.
- No source integration beyond the existing one-line GRO commit, no build,
  image, router contact, upload, reboot, or flash occurred. Incomplete agent
  conclusions are not promoted. Release remains NO-GO / NO-IMAGE / NO-FLASH.

## Patch85 Daybreak21 Resume Session - 2026-09-04 21:53 +03:00

- Resumed the isolated source corrections after pause. Rechecked current WSL
  HEAD `f3173f41940ab15d63a205f6d618e145d49ee58a`; the Daybreak20 WiFi/MLO
  composition is committed, while profile/local package/NPU diagnostic edits
  are uncommitted. Current mt76 does not contain Daybreak19 host-adapter parity.
- Three scoped workers completed LuCI, shell validation, and MLD MAC fixes.
  Main merged the MAC-only patch, preserving their inputs/evidence. Main
  additionally fixed raw-versus-normalized MLO configuration comparison and
  added early/late setup validation using a deep raw snapshot.
- Preserved then removed only the unfinished counter design. It would mark
  unchanged radio configurations changed and was not wired through hostapd.
  No complete transaction-generation protocol is claimed.
- Main executed 43 generator and 38 merged service/allocator tests plus full
  ucode syntax checks. The old generator fails the hidden-field regression.
  Worker reports: 161 LuCI checks; 535 focused shell assertions plus width
  and adversarial suites. These are offline fixtures, not association proof.
- A separate read-only Windows preflight found the Ethernet adapter disconnected.
  No router command was sent through the WiFi route to 192.168.1.1. Live state
  remains unverified despite the user's renewed test/flash authorization.
- No image build completed or router state changed in this continuation yet.
  Full integration, component rebuilds, artifact inspection, and live synthetic
  acceptance remain pending. References and ledger updated with those limits.

## Daybreak21 Build And Serial Identity Session - 2026-09-04 22:20 +03:00

- Integrated the eight preimage-guarded corrections and reran 165 LuCI, 43
  generator, 38 service/allocator, and 535 shell tests successfully.
- All ten selected component builds passed, including mt76. Retained the
  NPU-enabled modules as comparison artifacts, not a firmware release.
- Added/tested the explicit WLAN NPU build gate after confirming upstream
  stop/reinitialization errors are ignored during L1 recovery. Expanded config
  is disabled and baseline compilation is active. Ethernet/DTS/power unchanged.
- Corrected NPU status fallback wording, added explicit compiled_support
  evidence and LuCI display, and passed semantic/polling fixtures. Full Ghidra
  analysis of comparison modules is active; no completed binary audit claimed.
- COM3 wakeup yielded a verified Linux root prompt and matching W1700K ubus/DT
  identity (6.18.34, r0-73a8983). Health capture was incomplete. No flash or
  configuration change; Ethernet is still disconnected on this computer.
- Ledger/reference updated with integration, build, identity and open gates.

## Daybreak21 Binary And Health Checkpoint - 2026-09-04 22:51 +03:00

- Both WLAN-NPU variants compile. Full six-ELF Ghidra analysis and exact binary
  checks pass; external symbols are excluded from 27/27 and 8/8 decompilation
  counts. Baseline NPU init/stop code is absent. Active recovery remains unsafe.
- Full-image build recovered from Windows PATH quoting and an interrupted
  Meson cache. Failed logs and the generated cache were preserved. Retry active.
- Recovered our incomplete serial shell entry and captured 25 short read-only
  commands. Linux W1700K identity, 1.584 GiB available memory, LAN4 1000 Mbps,
  and 40-path keep inventory are recorded. Virtual eth0 speed error is explicit.
- Existing-network pinned SSH timed out; no host key or authentication reached.
  No host association/routes, router configuration, reboot, or flash changes.
- Ledger/reference updated. Full image and hardware acceptance remain open.

## Daybreak21 Offline Image Completion - 2026-09-04 22:58 +03:00

- Full source build succeeded after PATH and interrupted-cache recovery.
  ITB SHA256 be5257cbd34547f316b471f2064f0ac5ff25c9ae3a0d0f0051d0d303aa85a123,
  size 20,439,877 bytes.
- FIT/DTB/metadata, official firmware contents, package/helper/JS and audited
  module executable-section gates pass. Corrected verifier's legacy metadata
  field selection from the current fwtool.sh implementation, without weakening
  or editing the image/device compatibility policy.
- FinalResult engineering bundle created; all 27 checksum entries pass.
  It is WLAN-NPU-disabled, not flashed, not runtime accepted, and not stock parity.
- Serial identity/health evidence and network SSH timeout remain the latest
  connectivity evidence. No flash, upload, reboot, router config or PC network
  changes. Ledger/reference now distinguish this candidate from historical V6.87.

## Daybreak21 R1 Live Session - 2026-09-05 03:55 +03:00

- Wired access recovered. Verified identity, layout, rollback, private backup
  and sysupgrade -T before normal preserved-config flashes; serial captured both.
  First wrapper aborted before flashing on informational stderr; old FIT was
  verified unchanged before the corrected retry.
- Initial live jshn/nounset failure was fixed in source and proven with real
  jshn, a negative control and actual router execution. Corrected built-in
  airoha_eth detection. Both fixes are baked into R1, not just overlaid live.
- R1 FIT hash 0788f405337ceb030d873463bbf278497dcd9b86e8f75a1a3f57fd318eda195f,
  size 20,439,877, kernel 6.18.44. Factory, original wireless and module hashes
  are verified. 3-band AP, 2/3-link MLO, scan calls, five invalid cases and
  full teardown/config restoration pass. Shared scan caches and no-client/no-
  throughput limitations remain explicit.
- Actual LuCI page/refresh/MLO-dialog smoke passes at desktop viewport, no JS
  errors. Original settings restored, no test networks or global UCI deltas.
  Serial captures, tunnels and workers closed; no host network setting changed.
- CPU SMC frequency readback is unavailable; no guessed clock or governor was
  applied. WLAN NPU remains compiled out; full stock parity/recovery is unfinished.
- R1 live-report bundle resealed, all 30 hashes verified. Canonical ledger and
  reference updated to R1 as the current live engineering baseline.

### R1 GUI Save Addendum - 2026-09-05

The actual tri-band creation dialog passed single-click Save and page reload
with correct staged 1/2/0 link order, SAE and PMF=2. No GUI Apply was issued.
Test session logged out; original config and zero global UCI deltas verified.
GUI evidence added to FinalResult, 31 checksum entries replay. Tunnel closed.

## Workspace Migration and Cleanup - 2026-09-05

Canonical working repository moved to private `MCShotty/W1700KNPU`, local WSL
`/home/captain/W1700KNPU`. Current build and upstream Git backing moved inside
its ignored `.build/` and `.local/` directories; old paths are compatibility
symlinks. Old Windows locations now carry migration pointers, not new source.

Source/release import `4a5a3fe0589d34849fc8b8c53559a06db01238e6` and research
import `2b4a1a5210ac1b3b860b782d52f8226e5c2b174e` passed remote/local tree checks.
35 changed source files reconstruct correctly. The historical archive contains
49,891 verified files; 1,224 prefiltered entries and 152 scanner-flagged files
remain local. Original stock and selected release inputs are included, using
checksummed parts where required by the GitHub API.

Completed: retired 597 obsolete FIT images (11,744,507,404 bytes); replaced eight
old Ghidra directories and two old prepared build directories with losslessly
verified local archives. No protected recovery VHD, private keys/backups,
factory/calibration, current build, retained v689 source, or selected rollback
was removed. Temporary historical staging was removed after verified upload.

Windows VHD compaction succeeded through the documented CompactVirtualDisk API
after full WSL shutdown; sparse mode was not enabled. Reclaimed 27,792,506,880
physical bytes from the VHD; WSL restarted and systemd reports running. Final
measurement: C: 29.04 GiB free; D: 30.24 GiB free. Git integrity and both retained
release checksum files pass. Exact receipts: `docs/migration/`.

No router access/configuration/flash or firmware behavior changes in this task.
Stock parity and real-client/throughput acceptance remain unfinished.

## NPU Provider Guard - 2026-09-05

Resumed in the canonical workspace. Implemented patch 003 to skip six coherent
allocations when no Airoha provider attached. Twenty compiled-C cases and an
unpatched negative control pass; enabled and disabled real module builds pass.
Normal config and baseline executable sections remain unchanged. No image or
live configuration/module update was made.

Headless Ghidra analyzed the stock host-adapter/NPU and rebuilt enabled driver,
with 53 SHA-bound lifecycle exports. Source/ELF analysis confirms the unresolved
L1 error-discard path and full-reset token release before NPU quiescence. Stock
exit hooks do not prove a complete drain contract. The next implementation must
cover L1, full reset and removal, not just two unchecked returns.

Pinned Ethernet-only router readback confirms the W1700K on 6.18.44, WLAN NPU
compiled out and healthy memory. Detailed evidence, warnings, scope boundaries
and next gates: `research/checkpoints/2026-09-05-npu-attach/REPORT.md`. Ledger and
current reference updated; both goals remain unfinished.

## Remaining-Work Note and Storage Cleanup - 2026-09-05

Created the canonical remaining-work checklist and durable routing note at the
user's request. Reviewed Windows user-profile and WSL storage. Preserved all
histories via verified compression, cleared regenerable caches, removed only
SHA-matching duplicate installers, and archived the complete inactive v689 build
before removing its expanded copy. Private inventories stay local.

Normal VHD compaction succeeded and WSL restarted. Final host free space:
C: 59.96 GiB, D: 38.34 GiB, approximately 39.68 GiB gained in this pass.
Source reconstruction, release checksums and Git integrity still pass. No router
or firmware changes. Recovery/calibration/credentials/current build and rollback
remain protected. Exact receipts: `docs/maintenance/cleanup-20260905/`.

Resume from `docs/REMAINING_WORK.md`; NPU quiescence/lifetime work and real-client
WiFi/MLO throughput/stability acceptance are still open.

## Mailbox Ownership And Quiescence Checkpoint - 2026-09-05

Added provider patch 926 for command-before-counter publication and timed-out
mailbox buffer retention. Actual-function model: 143 assertions; both independent
unpatched negative controls reproduce the defects. Real kernel and both mt76
variants compile, ARM64 layout is unchanged, and executable module sections match
the previous provider-guard checkpoint. Original build configuration is retained.

Full Ghidra stock-kernel/provider analysis and corrected pristine RISC-V firmware
analysis confirm the transport order but disprove STOP/GET as a whole-worker
barrier. Two workers continue ring/buffer actions without steady-state stop gates.
An older comparison used our V28-patched blob; the provenance correction and
independent pristine revalidation are recorded in the report and ledger.

No router contact, flash or runtime changes. Shared recovery/removal ownership,
full NPU host-adapter parity and actual-client WiFi acceptance remain unfinished.
Evidence: `research/checkpoints/2026-09-05-npu-quiescence/REPORT.md`.

## Executable Reset Counterexample - 2026-09-05

Recovered the stock reset path through connac_if, arch/GE/PCI callback tables and
registration. Original AArch64 code confirms status masking in 16 controlled
cases with two mutation controls. Original RV32 hart dispatch and core-5 worker
code reproduce descriptor consumption after STOP callback completion and GET3
zero; empty-ring and stopped-before-startup controls pass.

Corrected Ghidra shared-SRAM volatility and non-returning worker metadata. Earlier
C output hid cross-core acknowledgement stores and merged adjacent wrappers;
raw assembly was retained. Standalone page-loop reachability is unproven and
must not be counted as a second active ungated worker. Core-5 reachability and
the counterexample stand independently.

These are static/emulator results, not hardware DMA or live-binding proof. No
firmware source/router/image change. The actual generation-aware barrier and
shared recovery/removal ownership policy remain open. Full evidence and replay:
`research/checkpoints/2026-09-05-npu-reset/REPORT.md`. Ledger/reference updated.

## Generation Barrier Candidate - 2026-09-05

Implemented an unpromoted eight-hart generation protocol with separate drain
witnesses and refresh-before-arm. Actual C passes 9,351 native/RV32 call pairs,
100 cycles and three check-removal controls. Four core-5 instruction detours in
emulator memory pass startup/empty/steady/in-flight stop, new-ring refresh and
ten register/MIE preservation cases. No production memory reservation or
deployable patched blob is claimed; other harts and drain witnesses are modeled.

New Ghidra import resolves a missed UART handler (425 discovered functions).
Native IRQ registration/dispatch shows UART writes can re-enable RX and the PPE
handler can reach bufid release after STOP/GET0. These require coordinator IRQ
and control-command admission, not just worker polling. Hardware drain semantics,
all-hart hooks and shared Linux recovery/removal retention remain unfinished.

Packaged source/config and patch 926 are unchanged. No router contact, image
build or flash. R1 remains the last router-tested WLAN-NPU-disabled baseline,
not full parity or fresh client acceptance. Report, hashes and replay commands:
`research/checkpoints/2026-09-05-npu-barrier/REPORT.md`. Ledger/reference updated.

## Seven-Worker Barrier Extension - 2026-09-05

Combined emulator ELF has 20 detours covering seven worker contexts. New refill
and fast-RX caches are refreshed before READY, including fast startup's already
zeroed indices. Sixteen new stop/resume, 96 differential register/MSTATUS,
17 missing-startup, six in-flight and six interrupted-refresh cases pass.
Three randomized shared-SRAM cycles alternate ring locations across seven saved
RV32 worker contexts; 19 negative controls are rejected. Prior regressions pass.

This is serialized instruction emulation with modeled helpers, coordinator 0
and hardware drains. Full boot/helper/IRQ closure, versioned host ABI, physical
completion/cache/placement and common Linux recovery retention remain open.
Packaged source/config and patch 926 are unchanged. No router access, image or
flash; R1 remains last router-tested, not stock parity or fresh client evidence.
Report: `research/checkpoints/2026-09-05-npu-workers/REPORT.md`.
Ledger/reference/remaining-work updated; both full project goals remain active.

## Coordinator Admission Candidate - 2026-09-05

Added active-handler retention, deferred coordinator IRQs and versioned control
messages. Native UART/PPE stop counterexamples are blocked by emulator adapters,
with mailbox status still available. All eight saved contexts acknowledge via
RV32 code; 1,667 differential calls, six mutation controls, mask failures,
in-flight/ABI/transport cases and combined worker regressions pass.

Ghidra now recovers the two missed Wi-Fi/tunnel mailbox callbacks, exporting 427
discovered functions. Native dispatch confirms ignored length, early no-wait
DONE and static-index callback overwrite. These are protocol findings, not
proved causes of live client failures. Physical reclaim/restart capabilities
remain clear; hardware drains, complete boot/placement/cache proof, production
host recovery, full parity and client Wi-Fi acceptance remain open.

No packaged source/config, router, image, flash or association change. Evidence:
`research/checkpoints/2026-09-05-npu-admission/REPORT.md` and
`firmware/npu/ADMISSION_ABI.md`. Ledger/reference/remaining-work updated.

## Bounded Layout And Native GDMA Contract - 2026-09-06

The candidate now uses a conservative 32 KiB local SRAM map, linker-bound state
at `0x3e906000`, and synthetic rings in separate 480 KiB SRAM. Sixteen native reset
cases, 36 fixed/dynamic table entries, retained R1 FIT/DTB identity and reservations,
ten regression suites and four linker negative controls pass. This does not prove
production placement, full boot, atomic/cache support or physical containment.

Stock kernel exports recover 63 GDMA/HSDMA functions, 67 with known referrers.
Native ARM64 WAIT observes CT0.ENABLE clear; RV32 copy observes only DONE.
Conditional stale-DONE tests require a hardware start-clear fact still unverified;
they are not a live Wi-Fi failure diagnosis. No physical drain witness is emitted.

Packaged source/config and protocol sources remain unchanged; no image, router,
flash or association action. Linux recovery/removal, full NPU parity and actual
client acceptance remain open. Evidence and replay:
`research/checkpoints/2026-09-06-npu-layout/REPORT.md`. Ledger/reference/remaining
work updated; R1 is still last router-tested, not freshly revalidated here.

## Guarded Copy Candidate - 2026-09-06

The unpromoted copy guard checks known hart/channel ownership, preexisting busy
work, stale-DONE clear, DONE plus ENABLE-clear completion and final ACK readback.
The legacy void caller is held on failure with only a shared atomic fault write;
coordinator admission state remains coordinator-owned. All three native caller
paths, late completion, eight mutants and twelve combined suites pass. Both
poll-budget ELFs reproduce; default 65,536-observation holds and Ghidra's three
selected exports from 50 extension functions verify. No physical drain or
working restart is claimed.

Fresh pinned Ethernet readback confirms W1700K/kernel6.18.44, WLAN NPU compiled
out and all radios reported up, not actual-client acceptance. No MMIO access
(`devmem` absent), helper installation, config, association, module, image or
flash change. Packaged source/config remain unchanged; full boot/cache/drains,
Linux retention/restart, full parity and client proof remain open. Evidence:
`research/checkpoints/2026-09-06-npu-copy/REPORT.md`. Ledger/reference/remaining
work updated; both full goals remain active.

## MT7996 TX-Check Reservation Fix - 2026-09-06

Native boot plus the original mailbox address callback confirms56KiB of TX
check-table writes against the old26KiB reservation, with30KiB entering BA.
The MT7996-specific DTS include now reserves the full table and relocates BA.
Three affected DTBs preserve all other properties, genericEVB is byte-identical,
and native replay plus two partial-fix controls pass. Source reconstruction
verifies35OpenWrt/3LuCifiles; this is a source fix, not a new image or live
Wi-Fi failure diagnosis. Current staged NPU blobs match the tested pristine hashes.

Core0 waits for the host's address command before finishing initialization, so
bootstrap admission and contained barrier-state setup remain unresolved alongside
physical drains/cache, Linux recovery/restart and full parity. `/dev/mem` absent;
no MMIO workaround, install, radio/config/association/module change or flash.
R1 remains last router-tested; actual-client proof is pending. Evidence:
`research/checkpoints/2026-09-06-npu-bootmem/REPORT.md`. Ledger/reference/remaining
work updated; both full goals remain active.

## Provider Reserved-Memory Preflight - 2026-09-06

Patch 927 now validates/snapshots WLAN regions before the first WLAN init send
and checks binary code/backup capacity before firmware mapping/loading. Loaded
profile and binary bounds are provider-private; successful wire order and the
public consumer structure are unchanged. Actual-C tests cover 109 cases plus
eight actual-DTB fixtures, six mutation controls and three preimage defects.
The existing mailbox suite retains 143 passing assertions. Source reconstruction
verifies36OpenWrt/3LuCifiles; kernel preparation matches the candidate exactly.
Full kernel compile exits0; ARM64 probes preserve all public sizes/offsets.
Ghidra exports24/24functions and confirms preflight-before-send in the object;
the combined evidence verifier passes. Tool/DWARF limits are recorded separately.

This is startup layout validation, not contained initialization, physical drains,
recovery/removal ownership or rollback after a partially accepted sequence. Full
NPU datapath parity and actual-client acceptance remain unfinished. No router
contact, full image, config, loaded-module, association or flash change; R1 remains last
router-tested with WLAN NPU compiled out. Evidence:
`research/checkpoints/2026-09-06-npu-preflight/REPORT.md`. Ledger/reference/remaining
work updated; both project goals remain unfinished.

## Cold-Start Candidate And Snapshot Audit - 2026-09-06

Official snapshot r36060-d6933d6aed has unchanged relevant Airoha/mt76/NPU
inputs, still with the old short reservation. Source and packaged payload/FIT
comparisons verify; no useful new NPU correction was found to import.

Unpromoted reset-entry gates now initialize candidate state via the native reset
path, using a fresh loader header.32 start orders,32 register cases,30 rejection
cases,173 C/RV32 cases and twelve combined suites pass. Independent review found
a phase/fault publication race; phase-first ordering and a post-READY fault
check fix it, with two instruction-paused counterexamples. Six final Ghidra
exports verify startup instructions; external continuation limitations remain.

218 native bootstrap callback cases identify API32/API23 release dependencies,
API18 no-op and warning-only invalid setters. Complete bootstrap admission and
physical loader containment/cache remain open, together with Linux recovery,
full datapath parity and client Wi-Fi acceptance. No packaged source/config,
router, flash or release change. Ledger/reference/remaining-work updated; see
`research/checkpoints/2026-09-06-npu-startup/REPORT.md`.

## Early Bootstrap Admission Candidate - 2026-09-06

Corrected the late-cold-hart marker check and added unpromoted MT7996 provider
bootstrap admission. A compiled source-8 registration detour precedes enable;
the handler validates a declared request buffer and private snapshot, allows
only version and six ordered memory commands, and retains failures. Sixteen
late-hart schedules, 228 policy cases, 5,935 native/RV32 pairs, 14 mutants and 13
original IRQ cases pass. Integrated native tests cover 35 invalid requests and
seven controls. Startup/race and twelve existing suites replay; Ghidra exports
11 selected functions from 62.

Full Wi-Fi main/mt76 attachment is not implemented. Native L2 write `0x1ec0f200` is
the next explicitly unmodeled boundary; version `0x457` is fallback, not readiness.
Structural range checks do not prove all packet footprints or hardware owners.
No packaged source/config, router, image, release or flash change. R1 remains
last router-tested with WLAN NPU compiled out. Ledger/reference/remaining-work
updated; full goals remain unfinished. Evidence:
`research/checkpoints/2026-09-06-npu-bootstrap/REPORT.md`.

## Native Core-0 Wi-Fi Bootstrap And Host Sequence - 2026-09-06

Original reset now reaches native Wi-Fi return and candidate coordinator idle
ACK. Five schedules check the full 256 KiB L2 image, RX/TX descriptors and ID
table; three missing-register controls reject unmodeled access. Delayed API23
and host ring bases exercise native waits. Other worker and drain ACKs stay zero.
Explicit register storage, hart/printf/delay substitutions and synthetic host
inputs do not prove physical L2/cache/DMA/IRQ behavior or complete all-hart boot.

Forced SKB exhaustion and malformed host-ring inputs still return native success.
Separate snapshot-host tests pass 164 compiled C cases, 149 bounded callbacks and
three mutants, with thirteen callback paths honestly pending. The 38-command
tail includes active initialization/publication, not merely passive setters.
Single-HIF TX1 publication, INODE read length, descriptor fallback and complete
consumer/partial-init ownership require closure before opening mt76 admission.

No firmware/config, router, image, flash or release change. R1 remains last
router-tested with WLAN NPU compiled out; full Wi-Fi/NPU goals remain open.
Ledger/reference/remaining-work updated. Evidence:
`research/checkpoints/2026-09-06-npu-nativewifi/REPORT.md`.

## Cold-Start Hart Parking And Native RX Callbacks - 2026-09-06

Actual resets now reach all eight first startup gates with all 26 existing
detours installed. Fourteen model scenarios, seven missing-gate controls and
six input controls pass. Each owner writes its own parked slot with IRQs off;
early contexts and stacks survive, and only core0 initializes candidate state.
Strict STOP remains idempotent at unreleased epoch1. Ready/drain/release/arm stay
zero. Flat/banked PLIC and chip inputs are explicit hypotheses, not hardware
identity, interrupt delivery, physical containment or post-gate initialization.

Two direct native DESC callbacks complete all helpers and initialize 2,560 RX
descriptors/IDs. Whole-memory/footprint checks, 21 negatives and two strict
denials pass; parent replay is byte-identical. Native wrapper success masks
partial allocation failure. Eleven previous cases and two separately modeled
allocator cases remain; general mt76 admission stays closed.

Independent all-hart review and current-source evidence binding pass. No
firmware/config, router, image, flash or release change. R1 remains the last
router-tested baseline with WLAN NPU compiled out. Ledger/reference/remaining
work updated; full goals remain open. Evidence:
`research/checkpoints/2026-09-06-npu-allhart/REPORT.md`.

## Native TX Attachment Callbacks - 2026-09-06

SET19 selectors0/2, DESC10 and API21 selectors5/7/10/12 now execute their full
reached helper bodies on native core0 snapshots. Combined 17 valid calls, 73
controls and seven strict denials pass. Source-table oracles check whole RAM,
write footprints, 512 TXFREE descriptors, 8192 SKB-state/queue entries, 1536 records
and 1024 linked descriptors. Partial allocation and absent host-capacity checks
still permit native success; no readiness or hardware quiescence is inferred.

Seven of the 11 prior pending labels and both separate allocator-substituted
cases are closed. Four DESC5/6/7/8 cases remain unresolved after a tool restriction;
the blocked lane was not retried or rerouted. General admission remains closed.
Complete host sequence/worker boot, production loader/cache/containment,
Linux recovery/removal and full hardware/client acceptance remain open.

No firmware/config, router, image, flash or release change. R1 remains last
router-tested with WLAN NPU compiled out; protected recovery/private inputs
untouched. Ledger/reference/remaining-work updated. Evidence:
`research/checkpoints/2026-09-06-npu-attachtx/TX_CALLBACKS.md` and
`research/checkpoints/2026-09-06-npu-attachtxbuf/TXBUF_CALLBACKS.md`.

## Native INODE Contract - 2026-09-06

Six original selector2/7/4 calls complete after native core0 initialization;
16 entry footprints, four controls and three strict denials pass. Five wrapper
loads span24 bytes. A12-byte request consumes stale undeclared tail within the
actual256-byte bounce allocation; these selectors ignore those arguments, so
synthetic padding does not change their full-memory results. Run flags precede
ICV clear and persist on modeled failure. No live failure causality is claimed.

The provider-framing subagent was interrupted by a tool restriction. Unfinished
patch/test/scratch files were preserved under ignored local storage outside
the firmware overlay. No framing fix, compiled provider/native bridge or kernel
build is claimed, and the blocked operation was not retried or rerouted.

Ledger/reference/remaining-work updated. Firmware/config, strict admission,
router, images and release remain unchanged. R1 remains last router-tested
with WLAN NPU compiled out. Both full goals remain open. Evidence:
`research/checkpoints/2026-09-06-npu-inode/INODE_CONTRACT.md`.
