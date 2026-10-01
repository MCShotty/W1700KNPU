# Native Page Rings And Production Count Guard - 2026-10-01

## Result

Continued from main `f4db59f`. The four formerly entry-only DESC5/6/7/8 paths
now execute every reached original helper after native core0 and RX0/RX2
initialization. Independent whole-RAM and ordered-write checks establish the
covered initialization and failure state. A malformed DESC6 count of 513
corrupts the published arena pointer despite the successful mailbox reply.

The selected MT7996 production provider now rejects short, zero and oversize
page/indication requests before allocation or transport. This is integrated in
the canonical kernel patch/source lock and fully rebuilt image. Full NPU
implementation remains open: valid-count native failure handling, actual
ownership, complete host/native setup, loader/postgate and physical/client
acceptance are not solved by this guard. No flash or router operation occurred.

## Native Contract

Inputs are the hash-pinned original MT7996 CODE/DATA, retained Ghidra export
and native initialization ELF. Current Linux 6.18.52/mt76 host setup C is
compiled to retrieve the actual four commands for both HIF profiles. Native
core0 initialization and the established RX0(1536)/RX2(1024) consumers execute
before the four selected page callbacks, in their current host order.

| DESC | Native Ring Base | Entries / Stride | Consumed Page IDs | Final Ready |
| --- | --- | --- | --- | --- |
| 5 | `0x3e82f020` | 256 / 16 bytes | 0..255 | `0x3e901f44 = 1` |
| 6 | `0x3e830020` | 512 / 16 bytes | 256..767 | `0x3e903954 = 1` |
| 7 | `0x3e832020` | 1024 / 16 bytes | 768..1791 | `0x3e902ce8 = 1` |
| 8 | `0x3e836020` | 1536 / 8 bytes | None | No page ready flag |

The native fixed offsets independently confirm all four descriptor capacities:
type7->8 is 4096 bytes, type8->9 is 8192, type9->6 is 16384 and type6->2 is
12288. The separate 8192-entry page-ID pool is initialized by the native
`0x8400a3bc` path at fixed table type `0x106`. `0x8400bb9c` consumes signed
halfword IDs, advances the ring head and updates success/failure statistics.
It is not the earlier packet buffer-ID allocator.

Dispatcher `0x8400dd82` publishes a table-derived pointer before initialization.
For DESC5/6/7, `0x8400bc02` consumes an ID, writes its software-ID slot and
builds each four-word descriptor. It writes the final ready/counter state only
after the requested loop. For DESC8, `0x8400bae6` preserves the first word and
ORs `0xe0000000` into each second word, then resets its counter/byte. Nonzero
poisoned indication records test preservation of the low bits and first words.
No packet backing memory is read by these initializers.

The oracle predicts every successful `(pc,address,size,value)` store from the
source/table contract, including pool/statistics changes and partial prefixes;
all 786,432 compared SRAM/heap/L2 bytes and exact unique write sets match.
All lookup, page-ID and initializer bodies run, without helper return injection.
Callback printf is the sole substituted callback function. Earlier native
boot retains its explicit platform/hart/timer models, listed in the receipt.

## Failure Findings

- Size diagnostics do not reject work. Zero counts for DESC5/6/7 still set
  ready without filling any descriptor. Counts above the selected ring spans
  write into neighboring regions; all three page profiles accept count1537.
- DESC6(513) writes a software ID at SRAM `+0x30fc`, changing the arena pointer
  from `0x3e817000` to `0x3e810300`. Larger controls also corrupt the arena or
  page-packet base. These are native emulator counterexamples with malformed
  requests, not a demonstrated normal-client hardware failure.
- Injected exhaustion after 17 IDs preserves those IDs/partial descriptors and
  leaves the selected ready flag clear. The inner helper returns1, but outer
  wrapper `0x8400fe34` still returns1 unconditionally. No rollback is performed.
- Page IDs 8192 and -32768 (raw `0x8000`), and zero/out-of-range packet bases,
  are accepted by unchecked pointer arithmetic. Physical page backing and
  exclusive ownership are not established by the resulting masked address.
- One-descriptor-short backing controls stop at explicit emulator access
  contracts. Their exact partial prefixes match; they are not firmware bounds
  checks, native error propagation or physical containment witnesses.

Four nominal cases, 48 distinct controls, five native instruction mutants and
four unchanged strict denials pass. Mutants omit ID-head advance, descriptor
status, page readiness or indication marking, or discard its low bits. Each
fails the whole-memory oracle, not merely a code-identity assertion. Mutations
are in-memory test controls only; original code is restored, and no patched
vendor blob or replacement firmware is emitted.

## Production Correction

Only `airoha_npu_wlan_msg_send()` changes in the reconstructed provider. For
the selected MT7996 tag (`txbuf_min_size == 0xe000`), API1 selectors5/6/7/8
require at least four payload bytes and counts in1..256/512/1024/1536 respectively.
The selector uses the same low four bits as the emitted header, so aliases do
not bypass admission. `memcpy` reads the scalar without requiring caller
alignment. Invalid requests return `-EINVAL` before frame allocation, caller-
payload copy or transport; count validation necessarily reads its scalar first.
Other valid selectors/profiles/commands and the INODE extent fix are preserved.

`provider-request.json` checks actual sender C under ASan/UBSan/LeakSanitizer:
12,096 cases cover all16 selectors, aliases, three profiles, commands1/19,
seven scalar boundaries and nine lengths including0..3 and248. There are384
pretransport rejections. Six provider mutants fail. This gate prevents the
covered malformed requests through the production sender, not arbitrary
direct native invocation or valid-count allocation exhaustion.

The actual packaged 376-byte AArch64 sender at section offset `0x8c0` passes
the same12,096 cases/384 rejections with unaligned input. Its1040-byte ELF
`.rodata` section is loaded unchanged; the compiled count table executes.
The test supports this sender's readonly ADRP/ADD relocations using the
official [AArch64 ELF relocation definitions](https://github.com/ARM-software/abi-aa/blob/main/aaelf64/aaelf64.rst#576-static-aarch64-relocations).
Allocation/memcpy/transport/free remain explicit models. Input-read extent and
execution outside the selected function/model hooks are checked.

## Build And Regression Evidence

- Full Linux6.18.52 world build exits0; FIT/model/compatibility2.0/firmware
  identity,218 packages and78 module ABI checks pass. Ten RV32 components
  remain a component archive, not bootable replacement firmware.
- Fresh source replay checks all60 locked OpenWrt/LuCI files. Exact kernel
  replay matches the tested provider; other patch sections are unchanged.
- INODE regression passes1056 actual-C and packaged-instruction frames/30
  controls,16 original wrapper entries/short controls and five mutants.
- Memory-plan regression passes273 loader/165 added load cases, three original
  controls, nine mutants,6174 retries and44 V2 executor cases with leak checks.
- Strict corrective-delta checkpatch: zero errors/warnings/checks,40 lines;
  `--no-signoff` used, no user DCO signoff fabricated.

| Artifact | SHA256 |
| --- | --- |
| Current FIT,26,932,042 bytes | `230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe` |
| Packaged provider | `f5fad954b96db5c4fb932969359d2019de3b966c53cfb52ef725fa99af494ce6` |
| Reconstructed provider | `94dd99b750c047cf0ee14d12b3cd97ad397821e0e01936ca223c3c68cd46b2f6` |
| Canonical kernel patch | `af6444c3573a8fddb7515f8b5678d24796d420946c496fb64489fba91f8b040d` |
| Source lock | `638e91b47ed75eb1241066e74b6da0e7d6b671cf10af0eb1402c4fefb8646cd9` |
| Preserved INODE-only FIT | `031f7bd2b28e0507ddfe810602a7edef71c63900244935e7d460ab58ab35a0cc` |

Current FIT remains under `.build/merged-openwrt/bin/targets/airoha/an7581/`.
The preceding image is preserved at
`.local/npu-page-rings-20261001/pre-page-guard-sysupgrade.itb`; earlier277/FIT,
flashed132/FIT and protected R1 are untouched. The shared version label is not
an image identity. Published checkpoint files are text only; no private backups,
credentials, raw firmware/modules or image binaries are added.

Independent readback verifies352 files totaling109,159,312 bytes: all four
test input/artifact collections,60 reconstructed sources,the prepared provider,
current FIT,preserved031/277 FITs and R1. `independent-readback.json` records
the covered checks; `file-manifest.json` fingerprints this checkpoint's text
files, excluding the manifest itself.

## Replay And Next Work

With the pinned native inputs and Python ELF/Unicorn tooling, use fresh names:

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu \
  python3 tests/npu/test_page_ring_callbacks.py --name page-native-repeat
PYTHONPATH=.local/npu-reset/python-lib:tests/npu \
  python3 tests/npu/test_page_request.py --name page-provider-repeat \
  --target-module .local/merge-nonoc-20260923/page-count-verified-20261001/rootfs/lib/modules/6.18.52/airoha_npu.ko
```

Omitting the target argument does not claim packaged instruction coverage.
Native setup runs selected fragments, not all38 host messages/strict transport.
Both Jev source and post-validation batches retain raw probabilities and the
`jev-1.13.0` model. They confirm claim boundaries; test/runtime proof remains
separate. The source/result receipts and independent readback/manifest are
retained alongside this report.

Next implement checked native page-pool/index/ID/backing validation and reliable
failure propagation with retained partial ownership, then compose complete
host setup through strict transport. Full loader identity/storage/publication,
other postgate consumers, physical DMA drains/teardown/rearm and actual-client
Wi-Fi/MLO acceptance remain required. The ledger, session log, current reference,
remaining-work list, both READMEs and AGENTS.md are updated accordingly.
