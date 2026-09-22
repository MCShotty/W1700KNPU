# MT7996 NPU Host TX Topology Candidate

2026-09-09. Status: implemented source candidate, host-C tested, bridged into
native core-0 bootstrap, and compiled as eight AArch64 objects. Unpromoted and
outside the firmware overlay. Not a complete NPU implementation or hardware fix.

## Scope

The active request is now NPU-only codebase work. Physical testing is deferred;
no router contact, Wi-Fi change, subagent, firmware image or flash operation was
performed. The earlier INODE-provider and native DESC5/6/7/8 restrictions were
not retried or rerouted. This checkpoint concerns separate host queue ownership,
queue-address calculation and core-0 startup publication.

Canonical HEAD at verification: `666b63245d3c13921cb4cdedeef4d7e3f418bd1e`, with
the existing uncommitted Wi-Fi/source-export work preserved. mt76 source pin:
`be5ce7910521492d4a2e4ce7ee3843680a46c047`. Archive SHA256:
`d1d0f7588c5b9ceafcac341ce19dd206ed9ec106847e672ab77e48bacb57f81a`.

## Finding And Correction

The pinned `mt7996/dma.c` selects NPU-specific TX IDs only inside its HIF2
branch. Independently, `mt7996_register_phy()` aliases band1 onto band0 when
HIF2 is absent, then aliases band2 onto band1 for NPU operation. Thus all three
bands share TX0, TX1 is never allocated/published, and band1 has no assigned
physical queue ID.

The actual `mt7996_npu_txd_init()` body then writes the GET4/selector5 result
through PHY1's physical descriptor-base register and GET4/selector7 through
PHY0's register. In the single-HIF baseline these are the same register. The
host-C replay demonstrates the second write overwriting the first under
distinct synthetic replies. Neither the reply values nor the physical device
were emulated by this host-C test.

The candidate makes two coupled changes:

- Select the NPU TX mapping before branching on HIF2.
- Share band1 with band0 only for single-HIF, non-NPU operation; active NPU
  owns TX0 and TX1 separately, while band2 continues sharing TX1.

Changing only one branch is insufficient. The tests reject both partial fixes.
The patch does not change descriptor allocation, publication order, packet
processing, native callbacks, lifecycle management or recovery.

| MT7996 case | Band queue owners | Physical queue IDs used | TX1 publication |
| --- | --- | --- | --- |
| Original, single HIF, NPU active | 0 / 0 / 0 | 18 only | absent |
| Candidate, single HIF, NPU active | 0 / 1 / 1 | TX0=21, TX1=18 | 512 entries |
| Either, dual HIF, NPU active | 0 / 1 / 1 | TX0=21, TX1=18 | 512 entries |
| Either, single HIF, NPU inactive | 0 / 0 / 2 | 18 / 19 | no NPU writes |
| Either, dual HIF, NPU inactive | 0 / 1 / 2 | 18 / 19 / 21 | no NPU writes |

Active NPU allocates TX0 as 1024 x 208 bytes and TX1 as 512 x 208 bytes.
The queue table carries the original interrupt masks: physical18=bit30,
19=bit31 and21=bit15. Actual `Q_CONFIG`/`TXQ_CONFIG` macros execute; this is
software interrupt-table validation, not IRQ-delivery proof.

The two TXD destinations are now `0xd4420` and `0xd4450`, with the latter
using the existing `+0x4000` HIF2 offset when present. These match the pinned
host source's two `SET_WAIT_TX_RING_PCIE_ADDR` expressions. That whole
offload function is source-bound, not executed here. Actual single-HIF chip
routing through physical ring21 remains a hardware acceptance requirement.

## Host And Native Evidence

`test_host_tx_topology.py` passes:

- 60 nominal before/after traces covering MT7996 with NPU compiled in/out and
  MT7992 controls, both HIF topologies and stopping after each band.
- 63 controls: four preseeded-register cases, 27 modeled queue/allocation
  failures, 16 modeled PHY/framework failures and 16 TXD transport failures.
- Four detected mutants: mapping-only, ownership-only, duplicate descriptor
  target and wrong interrupt mapping.
- Exact queue aliases, allocation sizes, ordered register writes, physical
  destinations and TXD request order. Unaffected configurations compare equal
  before/after, including all exercised MT7992 paths.

The baseline host harness is reused without modifying it. Twenty-two complete
functions execute, including the original provider address calculation and its
function-pointer wrapper, plus the complete original TXD initializer. Two TX
source blocks execute with original configuration macros. The connac bridge,
framework, allocations, locks/RCU, WED-inactive boundary and register storage
remain explicit models. TXD replies are synthetic, not native attachment proof.
Compiled-out cases use the reachable null-provider state; no impossible
compiled-out/live-provider combination is counted as ordinary behavior.

`test_host_tx_boot.py` derives the NPU register base `0x1e900000` from the
compiled DTB's resource and identity address translation. Provider source binds
regmap to resource0. Combining this with executed provider queue-address C
resolves TX0 at `0x1ec0d0a0` and TX1 at `0x1ec0d0b0`; no guessed address map is
used for this replay. The DTB is the existing unpromoted memory-layout candidate,
not a new hardware readback.

Four native bridge cases and two controls pass. Original single-HIF host writes
leave the native core0 poll at `0x8400f836`, with no completion or idle ACK.
Corrected single-HIF writes and both dual-HIF variants progress through native
return to the candidate core0 idle ACK. Removing TX1 base recreates the stall.
Independent synthetic RX registers remain required; their absence is also
observed as the later wait at `0x8400f880` before publication.

Each successful run compares the whole 256 KiB L2 descriptor/table image and
all six copied host fields. Original reset/bootstrap and original core0 Wi-Fi
initialization execute with the existing candidate detours and explicit
hardware models. Seven other worker ACKs, physical drains, release and arm stay
zero. General attachment admission is not opened.

The zero-TX1-size control still returns from native initialization. This is
evidence against treating completion as readiness, not a valid-ring result.
No INODE or DESC5/6/7/8 callback executes. This test does not run the TXD native
GET/SET callbacks or establish actual descriptor-return values, packet fate,
cache visibility, concurrency, ownership barriers or all-hart startup.

## Build Verification

`build_host_tx_topology.py` applies the three current, source-lock-verified mt76
overlay patches and, for the corrected variants, this candidate. Both changed
translation units, `mt7996/init.c` and `mt7996/dma.c`, compile before/after with
NPU support enabled/disabled against the real Linux6.18.44 and staged
mac80211/backport headers. All eight outputs are AArch64 relocatable objects.
The OpenWrt GCC14.4.0 cross-toolchain is used; host models use GCC15.2.0 with
ASan/UBSan, leak detection and nonrecovering sanitizer failures.

This is not a module-link, package, whole-image or runtime acceptance check.
The current prepared tree lacks mac80211 module symvers, so no module-link
success is claimed. Kernel/release configuration, generated kernel identity,
source lock and cumulative patch hashes match before/after. Builds write only
the candidate scratch tree and this checkpoint's logs. Strict checkpatch with
`--no-tree --strict --no-signoff` reports zero errors/warnings/checks.
Scoped tracker `git diff --check` also passes. The repository-wide check flags
context whitespace inside the preceding cumulative patch edits; those files
were not changed by this NPU work and their source-export reconstruction passes.

During harness development, patch hunk counts, the expected IRQ bits and an
unreachable compiled-out/provider-present test case were corrected. A transient
WSL-share timeout interrupted one edit before it applied; the resumed edit and
complete reruns succeeded. None of those setup failures is a driver finding.

## Why It Is Unpromoted

New single-HIF TX1 publication can let already-running native initialization
proceed before the later framework registration succeeds. A registration or
TXD transport failure can therefore leave published queues or partial physical
base replacement. The tests retain and report those effects; they do not prove
DMA has stopped or resources can be freed. Promoting this patch into the legacy
NPU path before containment/lifecycle integration would expose that unresolved
boundary. The known-good WLAN-NPU-disabled release remains untouched.

Next requirements are complete post-gate worker initialization, callback/failure
closure, checked host integration, physical quiescence or containment, timeout/
late-completion ownership and safe reset/removal. Native descriptor fallback
validation and real single-HIF physical routing also remain open. The existing
restricted operations still require resolution; this work does not replace them.

## Baseline Handoff

The current source lock already records the preceding SAE-file-reload userspace
follow-up, snapshot `post-Daybreak21-R1-WiFi-SAE-file-reload-20260909`, with
hostapd receiver SHA256
`e9bdbed02f2072121083130d1de0dc91996c95217550fd5604fcc641d96e6338`.
That follow-up preceded the NPU-only/code-only request. No Wi-Fi work or fresh
physical validation was performed in this checkpoint. The earlier security
report describes its predecessor; neither report is a new firmware-image claim.

Source-lock SHA256, unchanged by NPU work:
`eaa7b7119ec7fdd7ab60a01ff3d3603946db1e72e66174725a2d59bb4f1d0e4b`.
All40 OpenWrt and3 LuCI exported entries reconstruct in `source-export.json`.

## Reproduction And Receipts

Run from the canonical WSL repository:

```sh
python3 tests/npu/test_host_tx_topology.py
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_host_tx_boot.py
python3 tests/npu/build_host_tx_topology.py
```

SHA256:

```text
candidate patch  8651a6905e84a8604177f992286f8b39039458f3176c7ea60a73229ecda6067a
host evidence    c6cde53615df04e484940916621232ee76c8256be43a2b2ea92fb2f5ea6c2eb7
native bridge    c5570e354dc781532d8f39fdf055f999a4963324c89d05090defeeb2535686d6
kernel objects   9e7a172114b97c0cd75d08dbcb325737ebe2cad9fa11bc3507c1129e32af9123
```

Exact source/fragment/object hashes and commands are in the three JSON receipts.
No protected recovery/calibration/private material was changed or published.
All four canonical trackers record this candidate. Full NPU parity is incomplete.
