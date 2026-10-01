# MT7996 INODE Provider Framing - 2026-10-01

## Result

Integrated the INODE framing correction into the canonical production kernel
patch and source lock, continuing from main `a6105f3`. The full Linux 6.18.52
image builds and passes offline checks. Actual provider C, the packaged
AArch64 sender and the original RV32 wrapper entries validate the covered
wire extent. No router operation or flash occurred. Full NPU implementation
and hardware/client acceptance remain unfinished.

The canonical ledger, session log, current reference, remaining-work list,
root README, NPU README and AGENTS.md are updated with this checkpoint.
Historical reports retain their original scope; the old unresolved provider
framing status is superseded, not the separate selector/readiness work.

## Finding And Correction

The mt76 one-word INODE request formerly declared 12 bytes: an eight-byte
WLAN header and four-byte value. Original MT7996 wrapper `0x8400fc2c` reads
four-byte words at offsets 0, 20, 16, 12 and 8 before helper `0x8400e084`.
Those reads require 24 declared bytes. The retained bounce allocation is
256 bytes: this is undeclared stale-tail consumption, not a demonstrated
physical allocation overflow. Earlier selector 2/7/4 receipts show that those
selectors ignore the extra arguments; padding is not proved to cause or fix
the observed hardware Wi-Fi failure.

`airoha_npu_wlan_msg_send()` now:

- Rejects negative/oversize lengths and positive-length NULL data before
  allocating or copying. The maximum caller payload remains 248 bytes.
- Zero-extends short command-24 payloads to 16 bytes only for the selected
  MT7996 profile (`txbuf_min_size == 0xe000`), producing at least 24 wire bytes.
- Copies only the supplied caller extent, preserving its bytes and zero tail.
- Preserves valid other profile/command lengths, full payloads and allocation/
  transport error returns. GET and native selector helper bodies are unchanged.

Only the sender and one size constant change in the reconstructed provider.
Other integrated patch sections are byte-identical. Unified-diff context was
regrouped mechanically; exact before/after replay verifies the runtime delta.
See `provider-frame.patch` and `integration.json`.

## Verification

| Layer | Evidence |
| --- | --- |
| Actual provider C | 1,056 frames: three profiles, commands 19/24, 16 selectors, 11 payload lengths; 30 input/allocation/transport controls; ASan/UBSan/LeakSanitizer enabled |
| Original short controls | All 16 old one-word frames fail the declared read check at `20+4 > 12` |
| Original RV32 wrapper | All 16 corrected one-word frames cover reads at offsets 0/20/16/12/8 and reach helper entry with `[selector, 0x74737271, 0, 0, 0]` |
| Mutations | Five rejected: short native span, omit padding, pad other commands, pad other profiles, copy beyond caller extent |
| Packaged AArch64 sender | Actual shipped 296-byte function at section offset `0x8c0` passes 1,056 byte-identical frames and 30 controls |
| Existing host regression | 273 loader/165 added load cases, three original controls, nine mutants, 6,174 retries and 44 V2 executor cases; leak checks enabled |
| Locked source | All 60 pinned OpenWrt/LuCI files replay from fresh fixture worktrees |
| Full image | World build exit 0; FIT/board/firmware identity, 218 packages and 78 module ABI checks pass; ten RV32 components compile |
| Checkpatch | Strict corrective-delta check: zero errors/warnings/checks; `--no-signoff` used, no user DCO signoff fabricated |

The AArch64 replay resolves the actual sender symbol and CALL26 relocations
from the shipped ELF. Allocation, memcpy, free, fortify and internal mailbox
transport are explicit models. Profile load offset 728 is observed in this
binary, not a general private-structure ABI proof. RV32 runs consume the
compiled provider's actual frame bytes and stop before selector helper bodies;
they do not establish full setup or readiness.

The new runner is `tests/npu/test_inode_provider_frame.py`, with host harness
`inode-frame-harness.c` and target replay `inode_frame_target.py`. With the
pinned Python ELF/Unicorn tooling and native inputs available, use fresh names:

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu \
  python3 tests/npu/test_inode_provider_frame.py --name inode-frame-repeat \
  --target-module .local/merge-nonoc-20260923/inode-frame-verified-20261001/rootfs/lib/modules/6.18.52/airoha_npu.ko
python3 tests/npu/test_cold_memory_plan.py --name inode-memory-repeat
python3 tests/test_prepared_sources.py --name inode-source-repeat
```

The target module argument is optional; omitting it does not claim packaged
instruction coverage. Fresh builds/rootfs exports may have different paths.

## Artifact Identity

| Artifact | SHA256 |
| --- | --- |
| Current FIT, 26,932,042 bytes | `031f7bd2b28e0507ddfe810602a7edef71c63900244935e7d460ab58ab35a0cc` |
| Packaged `airoha_npu.ko` | `e6dd312bbc13b5f9842a652e4e79078bb819fef1578f2bd610ea6857222dd325` |
| Reconstructed provider | `fed1f7c40bd38e51ecc34e27d8256469c41b95479bf38a0adc5e944a40154ead` |
| Canonical kernel patch | `1f8f8a099433361c223821922a9a16f1dd8985c5133e113fd571228e1e0f6aaf` |
| Source lock | `a653ebbc9dc518369d5ef3397d3b80315146a7d1ff7f9965594ac91e629db1d4` |
| Preserved preceding local FIT | `277abd0b754200a0b330a35d4c759f264f918ec182cddc6c650fb734f46b4e4b` |
| Protected R1 rollback | `0788f405337ceb030d873463bbf278497dcd9b86e8f75a1a3f57fd318eda195f` |

Current FIT path:
`.build/merged-openwrt/bin/targets/airoha/an7581/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb`.
The preceding FIT is retained at
`.local/npu-inode-frame-20261001/pre-framing-sysupgrade.itb`. The current version
label remains `r36536-merged-288d79449f`; identify these distinct images by SHA,
not that shared label. The earlier physically flashed image is `132a35c7...`.
No firmware/module/image binary or private device data is added to this
checkpoint; it publishes source and text receipts only.

Independent current-file readback verifies 252 referenced files (80,883,241
bytes), including both test input/artifact collections, all 60 reconstructed
source files, the prepared provider, current FIT, preserved preceding FIT and
R1. See `independent-readback.json`; `file-manifest.json` fingerprints the
published checkpoint files and excludes itself.

## Semantic Review And Remaining Work

The supplied evidence was checked with TypeSafe `jev-1.13.0` using five bounded
questions. Choice results select declared extent fixed, valid other lengths
unchanged and actual binary with modeled dependencies (confidence 1.0 each).
Native selector completion receives Noul 0.04; offline-only project acceptance
has Choice confidence 0.99. Raw probabilities and request state are retained.
These judgments check the claim boundaries, not replace test/runtime proof.
Request syntax/model availability were checked against the official
[API](https://docs.typesafe.ai/api) and [models](https://docs.typesafe.ai/models).

Continue contained cold-provider/reset lifetime, complete engine ownership,
fresh loader identity and reserved/coherently published storage, real
DISCOVER/setup/BIND callers, remaining native postgate consumers, physical DMA
drains/teardown/rearm and actual-client Wi-Fi/MLO acceptance. The native hart7
phase correction remains separate replay-binding progress. No complete
bootable replacement firmware or physical recovery is claimed here.
