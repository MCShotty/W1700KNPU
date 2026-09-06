# Independent Review: NPU Provider Memory Preflight

Date: 2026-09-06. Verdict: **No actionable regression found in the reviewed
before/after delta.** This is a bounded static review, not hardware acceptance
or certification of the parent implementation/tests.

## Scope And Source Identity

Canonical root: `/home/captain/W1700KNPU`.
Only this report was written. No prepared/canonical source edits, builds,
router contact, staging, commits, or additional agents. The historical ledger
was not read and remains unchanged by this review.

Source aliases below are relative to the canonical root; numbers are exact
one-based source lines:

- `A`: `.local/npu-preflight/airoha_npu_after.c`
- `B`: `.local/npu-preflight/airoha_npu_before.c`
- `K`: `.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.44`
- `M`: `.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/mt76-2026.09.01~be5ce791/npu.c`
- `D`: `.build/openwrt/target/linux/airoha/dts`

SHA-256:

```text
B  51cd396f8c141bbf6d425088ddbf39e8a59d4874fa529980332509ba3b52e1fa
A  4ed450814e021a519cb68072bbb129576b570c3432b58b7d1e6053f6da074b88
M  a156bad3b9cc8a4422444272c5247b1d17042f495a1698f2799d1d79434d0e6b
K/include/linux/soc/airoha/airoha_offload.h
   9359009a4161de572e7f44b41b172860bb6414b56332f16ed6ff8df972126364
```

## Checked Behavior

- **Layout/lifetime:** `A:129-133,804-815,907` embeds the unchanged public
  object in a devm-allocated wrapper and publishes its original public pointer.
  `A:599` recovers that same allocation. The public structure has no trailing
  flexible array (`K/include/linux/soc/airoha/airoha_offload.h:166-214`), and
  its inline dispatcher forwards the pointer without copying (`220-223`).
  The actual consumer gets this pointer (`M:448-457`) and calls that dispatcher
  (`M:470`). No new allocation/free or public-layout mismatch was found.
- **Firmware selection:** `A:339-354` resets private state and chooses the
  same DTS-first/fallback branch used for loading. `A:304-320` classifies
  `fw_names[0]`, the exact string passed to the RV32 loader, not a subsequently
  reread property. Load errors return before publication (`A:881-883,907`).
  The fallback classification is consistent with `A:753-778`; currently neither
  fallback name is the MT7996-specific name.
- **Binary bounds:** `A:135-140,335-343` rejects zero, inverted, unaligned,
  and above-32-bit ranges before mapping the binary or copying either blob.
  The OF helper produces inclusive ends (`K/drivers/of/of_reserved_mem.c:795-805`;
  `K/include/linux/ioport.h:268-291`). After these checks, the `0x240000`
  minimum guarantees that both the 2 MiB code limit and the following 256 KiB
  backup fit without truncating the backup address (`A:885-887`). This applies
  to both current SoC profiles: both code limits are 2 MiB (`A:753-772`) and
  both shipped binary reservations are 10 MiB (`D/an7581.dtsi:28-31`,
  `D/an7583.dtsi:27-30`). Binary-only probe does not require WLAN reservations.
- **WLAN preflight:** all applicable helper lookups, structural checks, interval
  overlap checks and the selected TX-check floor precede cmd18 (`A:615-648`).
  Only cached binary endpoints are needed: `resource_overlaps()` ignores flags
  and names (`K/include/linux/ioport.h:312-315`). Adjacent intervals pass;
  intersecting intervals fail. MT7996 WLAN intervals must remain entirely in
  `[0x80000000,0xc0000000)` (`A:630-634`), so their publication to `u32`
  does not silently truncate (`A:652`).
- **Valid profiles/optional BA:** the corrected MT7996 layout is selected by
  the expected filename and supplies `0xe000` TX-check bytes
  (`D/an7581-npu-mt7996.dtsi:5-21`). The generic/MT7992 filename retains its
  `0x6800` reservation without the MT7996 floor
  (`D/an7581-npu-mt7992.dtsi:3-7`, `D/an7581-npu-wlan.dtsi:25-32`). Missing
  BA omits only the last resource; a named but unresolved/disabled BA fails
  before sends (`A:617-626`; `K/drivers/of/of_reserved_mem.c:795-801,831-835`).
- **Wire/caller semantics:** the successful sequence remains cmd18 on ifindex
  1, then cmd32/8/23/optional7/12 on ifindex 0 (`A:605-609,647-661`,
  `B:585-621`; enum values in `K/include/linux/soc/airoha/airoha_offload.h:115-149`).
  The final zero is restored explicitly. Send replies do not modify that local
  input: the helper copies it to a separate request (`A:551-571`). On preflight
  error, `M:470-492` releases references before changing the DMA device or
  publishing NPU/PPE pointers (`M:474-483`).

## Residual Limits, Not New Regressions

- **Not hardware containment or an atomic transaction.** Probe has already
  booted the cores and queried firmware before exposing the provider
  (`A:892-907`). Zero initialization sends on validation failure therefore
  does not mean zero prior device activity. After cmd18 succeeds, an allocation
  failure on cmd32 returns with a partial sequence (`A:559-561,647-656`). A
  timeout after mailbox publication can also follow device action
  (`A:236-254`); the caller only drops references (`M:489-496`). These paths
  already existed in `B:585-621`; there is no newly added drain, rollback,
  stop/restart, or physical reclamation proof.
- **Identity is a trusted filename contract, not blob authentication.** Loading
  identical MT7996 bytes under a different DTS filename leaves the floor and
  WLAN window checks disabled (`A:310-314,341,630,644`). For example, a renamed
  image with the old `0x6800` TX-check reservation passes these new predicates.
  No such renamed selection exists in the inspected profiles. Unknown images
  and replacement bytes under known names require separate contract validation.
- **Structural validity is not every firmware access bound.** Only TX-check
  receives a profile-specific size minimum (`A:644-645`). A one-byte aligned,
  in-window `pkt` reservation disjoint from the other ranges passes
  `A:627-645`. Binary placement is not tied to a linked load address or the
  WLAN DRAM window (`A:335-343`). These checks do not prove physical aliasing,
  installed RAM, cache visibility, all other buffer footprints, or exclusive
  ownership relative to unrelated reservations/device accesses.
- **Malformed optional-name tail is still treated as absence.** If the required
  names are valid but a trailing `ba` string lacks its terminator, the BA lookup
  returns `-EILSEQ`, while required-name searches can return earlier matches
  (`K/drivers/of/property.c:542-550`). `A:617-618` skips BA in that case. This
  preserves `B:611-617`, but is not full malformed-DT rejection.

## Verification Limit

Reviewed complete snapshots/diff, the actual consumer initialization/error
path, public header, OF/resource/mapping helper bodies, and relevant shipped
DTS profiles. Thirteen source-derived BigInt predicate cases were evaluated
without filesystem writes: corrected/old/generic layouts, BA absence/overlap,
binary overlap, window endpoints/crossing, zero size, high/unaligned addresses,
one-byte packet memory, and renamed-profile behavior. All matched the source
predicates. This is arithmetic cross-checking only, not execution of compiled C,
kernel helpers, firmware, or the parent's tests. No full parity review was done.
