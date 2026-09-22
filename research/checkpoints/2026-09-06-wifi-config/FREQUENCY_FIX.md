# Bounded LuCI Frequency Loader Corrections

Date: 2026-09-06. Canonical root: `/home/captain/W1700KNPU`.
Scope: FREQ01/FREQ02 from `FREQUENCY_AUDIT.md`; offline source execution only.

## Changes

- FREQ01: `w1700kApChannelsFromFrequencyList()` normalizes RPC flag case, so
  lowercase `no_ir`, uppercase `NO_IR`, mixed case and explicit `no_ir` reject
  non-initiating rows. The producer-shaped failing row is band5/channel161/
  5805MHz, `restricted: true`, `flags: ["no_ir"]`.
- FREQ02: both that map loader and `CBIWifiFrequencyValue.load()` use the new
  `w1700kRuntimeChannelAllowed()` shape check, not the static fallback lookup.
  Mapped radio identity/ownership, band filtering, positive integer channel
  bounds, 5 GHz primary-channel spacing and 6 GHz spacing/channel2 remain
  guarded. Runtime 2 GHz authorization is not intersected with fallback country
  limits. Synthetic advertised unrestricted channel169/5845MHz now survives;
  this is not evidence that any live regulatory domain permits that channel.
- Static fallback lists and `w1700kChannelAllowed()` are unchanged. No static
  allowlist was expanded. Generic non-W1700K mapping behavior is unchanged.
- Disabled/NO_IR/DFS predicates are preserved: MLO rejects any reported NO_IR;
  the ordinary widget retains `disabled || (restricted && no_ir)`. An explicitly
  inconsistent unrestricted-NO_IR control documents this preexisting distinction.
  Producer-shaped DFS rows have no NO_IR flag and remain available. Indoor
  metadata, TX power, country policy and all-subchannel width checks are unchanged.
- `modules/luci-base/htdocs/luci-static/resources/tools/widgets.js` was inspected;
  it contains no frequency loader and required no change.

Prepared source changed only in
`.build/openwrt/feeds/luci/modules/luci-mod-network/htdocs/luci-static/resources/view/network/wireless.js`:
one 25-line helper and three line replacements. Reversing just those edits in
memory exactly matches the captured pre-edit source; all other code is unchanged.
The other changed paths are `firmware/patches/luci.patch`,
`tests/wifi/test_frequency_consumers.py`, and this receipt.

## Verification

```sh
python3 -B tests/wifi/test_frequency_consumers.py
node --check .build/openwrt/feeds/luci/modules/luci-mod-network/htdocs/luci-static/resources/view/network/wireless.js
git diff --check -- firmware/patches/luci.patch tests/wifi/test_frequency_consumers.py research/checkpoints/2026-09-06-wifi-config/FREQUENCY_FIX.md
git -C .build/openwrt/feeds/luci diff --check -- modules/luci-mod-network/htdocs/luci-static/resources/view/network/wireless.js
```

- Before edits: original audit suite reproduced **4 passes, 2 expected failures**.
  Lowercase NO_IR was accepted by MLO; runtime169 was rejected by both loaders.
- After edits: **11 tests pass, no expected failures**, including 49 row cases
  and 109 modeled RPC calls per source-fixture run. Three independently reverted
  source conditions reproduce the old failures; each correction is necessary.
- Actual extracted JS executes both RPC consumer loaders and the existing
  channel/width helpers. No copied availability predicate or stubbed width
  validator is used. UCI, RPC, form extension, translation, capabilities and
  device discovery are framework fixtures, not live or rendered evidence.
- Controls cover case variants, explicit flags, disabled rows, DFS, indoor
  metadata, wrong/unknown bands, invalid channel shapes, duplicate/unmapped/
  renamed sections, 2/5/6 GHz rows, ACS metadata, and decimal status/scan values.
- A nonempty rejected runtime list stays an empty authoritative map; it does
  not reactivate static channels or ACS. MLO empty/missing/error paths retain
  null-map fallback; the ordinary widget retains empty choices/error behavior.
  US/CA/MX, DE and JP static country controls retain their prior results.
- EHT80 on the synthetic 165/169/173/177 block requires all four runtime
  subchannels; missing or NO_IR secondary rows keep that width unavailable.
- Syntax and scoped whitespace checks pass. A whole-tree `git diff --check`
  also observed trailing whitespace at parent-owned `openwrt.patch:1624` during
  verification; that unrelated in-flight patch was not edited here.

Only the wireless patch section was mechanically regenerated with
`git diff --no-ext-diff --full-index --binary` from LuCI base
`506ca606d379dd69e9826b2a5e7e2ab90e6b89a5`. Other patch sections are byte-identical;
their concatenated SHA256 is
`bc66d976364c2f6bb3a720897f2ee5cc7c09dc2ba48c70b312820d28c97a33ef`.
The test applies that selected patch with GNU patch, zero fuzz, to the exact
base Git blob through an anonymous memory file and compares every output byte
with prepared wireless.js. `git apply --reverse --check` also passes.

## Browser And Integration Handoff

The flow for parent QA is: Network/Wireless -> edit a mapped radio -> load
runtime frequency rows -> inspect channel/ACS availability and select width.
The frontend testing skill was read. Browser plugin/skill is absent; no browser
or Playwright setup/run was performed under this bounded delegation. Page
identity, nonblank rendering, overlays, console, screenshots and DOM interaction
are **not verified here**. Rendered browser QA remains the parent's responsibility.

```sh
python3 -B tests/wifi/test_frequency_consumers.py --emit-js
```

`source_program()` emits a browser-usable JS function body assembled from current
source, with no Node imports. Evaluate `new Function('assert', body)(browserAssert)`
in an isolated fixture page; it returns a Promise of row/fallback/width facts.
The framework assertion object needs `equal`, `deepEqual`, and asynchronous
`rejects` methods that throw on failure. This executes actual loaders; rendering
a real form remains separate. The default runner uses Node's strict assertions.

Parent owns `source-lock.json` refresh. Default tests check the other four
selected consumer hashes but deliberately defer the changed wireless hash;
wireless identity is instead checked by exact cumulative reconstruction.
After integration, require all five selected lock hashes with:

```sh
python3 -B tests/wifi/test_frequency_consumers.py --require-source-lock
```

No source-lock, four trackers (including the ledger), OpenWrt helper/hostapd/
regulatory source, other tests, or widgets file was modified by this work.
Ledger unchanged by explicit parent ownership, not a missing follow-up here.
No router contact, association, browser setup, NPU operation/retry, build,
image, flash or commit. Parent-reported live MLO startup progress is outside
this evidence; no live result is attributed to these uninstalled LuCI changes.

## Final Input Hashes

| Path | SHA256 |
| --- | --- |
| Prepared `wireless.js` above | `71dc161d0b6b3d90e8a48abe1bedc644b309fcca2360c1d2fa9d8653ccea0dfb` |
| `firmware/patches/luci.patch` | `03708d31f5c3bbc75f5fba5a5c6d6979232a3a8e426d6567da25eaaec0763c8c` |
| `tests/wifi/test_frequency_consumers.py` | `059082bb72d046afe74f0ae542e4f06dea6d4b8c4a131245ff4388b4f4e4c8d3` |
| Unchanged `tools/widgets.js` above | `b344cc52e99881d34bf08e214ab58434855e8f586b1650d6a9af0fc355bdcb86` |

Pre-edit wireless SHA256 was
`9c644f19eb0aa15469343e53a92c09ee7b1a3f2bff3cd21ddd939f917512ffa5`;
pre-edit cumulative LuCI patch SHA256 was
`8a9edb3558f6ba05e7a626bb8b16d6f95ed6fa3cab4097b250a956c79a3d368c`.
This receipt's own final SHA256 is returned in the handoff, not embedded in itself.
