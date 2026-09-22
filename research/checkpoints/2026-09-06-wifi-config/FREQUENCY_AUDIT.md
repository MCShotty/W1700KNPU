# Bounded Wi-Fi Frequency Consumer Audit

Date: 2026-09-06. Canonical root: `/home/captain/W1700KNPU`.
Git HEAD read back as `666b63245d3c13921cb4cdedeef4d7e3f418bd1e`.

## Result

- No second integer-only MHz parser was found in the five requested consumers.
  Decimal values pass the executed LuCI status/scan source controls.
- Two distinct input-contract candidates were reproduced in unchanged LuCI
  source: lowercase `no_ir` is missed by the MLO AP-channel loader; runtime
  channel lists are prematurely intersected with the static fallback allowlist.
- No demonstrated shared-wiphy cross-band channel/frequency assignment error
  in the exercised status/scan paths. Capabilities remain PHY-wide, not a
  per-radio capability receipt.

These are static/source-execution results, not UI, router, regulatory-domain,
AP startup, association, throughput or installed-package verification. The R1
decimal `iw phy` observation is supplied by the parent; it was not reacquired.

## FREQ-01: MLO Loader Misses RPC Lowercase NO_IR (P2)

Consumer: `W:325-339`, especially `W:331-337`. The MLO map only recognizes
`freq.no_ir` or exactly uppercase `NO_IR`. Its actual RPC request is declared
at `W:57-61` and called per logical device at `W:343-357`.

Supporting producer source: `RPC:144-172` lowercases flag names when requested;
`RPC:678-687` emits `band`, `channel`, `mhz`, `restricted` and lowercase `flags`,
without a standalone `no_ir` field. `Names:105-115` defines the original flag
spelling as `NO_IR`. `IW:3269-3276` sets the NO_IR flag and
`restricted` for a non-radar NO_IR frequency. The prepared configuration selects
`CONFIG_PACKAGE_rpcd-mod-iwinfo=y` at `.build/openwrt/.config:1774`; this does
not establish which module is loaded on R1.

Exact synthetic producer-shaped input for mapped 5 GHz radio1:

```json
{"band":5,"channel":161,"mhz":5805,"restricted":true,"flags":["no_ir"]}
```

Observed source execution: `w1700kApChannelsFromFrequencyList()` returns
`5g[161] = true`. Uppercase `NO_IR` and explicit `no_ir: true` controls reject
the row. The normal frequency widget rejects the lowercase row because
`W:1547-1549` already normalizes case. Consequently MLO's map disagrees with
the normal frequency widget for the same RPC input. That map feeds MLO default
selection (`W:942-974`) and validation (`W:1050-1130`, particularly
`W:1116-1122`). Acceptance in that map is proved; successful AP transmission
on a restricted channel is not claimed, and downstream enforcement may reject it.

Actionable correction candidate: make the MLO consumer normalize flag names
like the ordinary frequency widget and share the same AP-usable-row predicate.
Preserve the producer's DFS distinction; do not blanket-treat all DFS rows as
NO_IR. Add a producer-shaped lowercase control before promotion.

Cumulative source: `firmware/patches/luci.patch:749-763`, especially line 756.
This is separate from the parent's shell regulatory-helper decimal fix.

## FREQ-02: Runtime Rows Are Filtered Through Static Fallback (P2, Conditional)

Both runtime loaders call `w1700kChannelAllowed(section_id, freq.channel)`
without a runtime map (`W:336`, `W:1549-1550`). This enters the fallback branch
at `W:628-660`; the 5 GHz fallback list ends at 165 (`W:29-37`). The runtime
map is therefore already missing higher channels before the map-aware branch
at `W:645-646` can use it.

Exact synthetic advertised, unrestricted input for mapped 5 GHz radio1:

```json
{"band":5,"channel":169,"mhz":5845,"restricted":false,"flags":[]}
```

Observed source execution: both the MLO map and normal frequency widget omit
169. An otherwise identical allowed channel 161 control is retained. The
source already models 169/173/177 in its width/channel-run table (`W:23-27`)
and status checker (`S:76-79`). This candidate is conditional on the selected
driver and actual regulatory domain supplying such an AP-usable row; no claim
is made that R1 currently permits it, or that country US permits this fixture.

Actionable correction candidate: for a successfully obtained runtime list,
validate radio/band/channel shape and runtime restrictions without first using
the static fallback allowlist. Retain conservative fallback behavior only for
the explicit no-runtime-data path. Do not simply expand the static list as a
substitute for runtime authorization.

Cumulative source: `firmware/patches/luci.patch:453-461`, `:760`,
`:1052-1083`, `:1790-1791`.

## Other Consumer Contracts

- `R:3-4,209-217`: radio sanity sources the parent-owned helper and delegates
  `channel_valid`/`htmode_valid`; it does not parse `iw` frequencies itself.
  Its W1700K mapping is explicitly radio0/0/2g, radio1/1/5g, radio2/2/6g
  (`R:82-103,181-194,255-257`). Renamed sections or extra radios are not
  certified by this bounded audit.
- `C:10-25,27-53`: capabilities reads the whole selected PHY, or all PHYs
  when no argument is supplied. It searches feature text, not MHz numbers.
  `W:64-69` calls it without arguments and caches one result; `W:2440-2459`
  displays that aggregate in a device panel, while puncturing consumers also
  use it (`W:2461-2495`). Treat it as board/PHY-wide evidence. Per-band equality
  of EHT feature bits was not established; no specific false capability on R1
  was demonstrated, so this is a scope caveat rather than another finding.
- `N:158-253`: runtime channel facts numerically coerce frequency, normalize
  GHz/MHz, and reject wrong-band or inconsistent channel/frequency samples.
  MLO selects `dev` telemetry rather than shared `net` telemetry.
- `N:3935-3962,4118-4145`: radio-local config uses the wrapped runtime radio;
  the logical first-device MLO owner is a separate identity. This is consistent
  with the selected consumers' runtime-radio wrappers.
- `W:157-216,679-767` and `S:21-96,213-275`: numeric decimal frequencies are
  accepted; wrong-band samples are discarded. Runtime frequency and configured
  fallback frequency are separate facts. Channel integer validation is not an
  integer-only MHz parser.
- The frequency widget consumes structured RPC fields, not `iw` text.
  `W:1557` uses integer formatting only for the displayed MHz label.
  `IW:3247-3253` omits disabled frequencies and reads the numeric netlink MHz
  attribute; a textual `.0` rendering cannot trigger the parent's awk bug here.

## Reproduction And Evidence

Only new audit files were created: this checkpoint and
`tests/wifi/test_frequency_consumers.py`. No scratch was needed.
Harness SHA256: `572871c8b67448cb06d6bcb6413d267bf8023ffbed68255af067b986f6d49c86`.

```sh
cd /home/captain/W1700KNPU
python3 -B tests/wifi/test_frequency_consumers.py
```

Observed: six tests, four passing and two expected failures. Expected failures
are intentionally uncorrected candidates, not passing production acceptance.
An unexpected success after a fix requires reviewing/removing its marker.

The harness executes extracted original JavaScript functions and the original
frequency-widget load method with modeled UCI/RPC/form inputs. It also executes
the status object's original methods. No browser, RPC request or shell helper
is executed. Its controls cover `5805`, `"5805.0"`, `5.805`, wrong-band MLO/status
samples, disabled rows, unrestricted rows, and uppercase/explicit NO_IR.
It verifies all five requested file hashes against source-lock and verifies
all their cumulative patch new/context hunk lines against prepared source.
It does not reconstruct upstream base files or test the parent's helper.

## Source Identity

Aliases below are paths relative to the canonical root. All SHA256 values were
read during this audit. Five selected hashes match `firmware/source-lock.json`.
The OpenWrt cumulative patch is an in-flight parent-edited snapshot; its hash
is provenance only and does not claim the parent's edits are committed.

| ID | Path | SHA256 |
| --- | --- | --- |
| Lock | `firmware/source-lock.json` | `418ab419507c3f49eebfe14818dd19772a9ed402f31cfc993bdc861c38afdeae` |
| OpenWrt patch | `firmware/patches/openwrt.patch` | `319c648c0e9343ceaa295e3b3d2443d883e794aa4a08a0366a3baf7ad07b7b59` |
| LuCI patch | `firmware/patches/luci.patch` | `8a9edb3558f6ba05e7a626bb8b16d6f95ed6fa3cab4097b250a956c79a3d368c` |
| R | `.build/openwrt/target/linux/airoha/an7581/base-files/usr/sbin/w1700k-radio-sanity` | `cab4ae7d502c71c3b4dc8644aafb1a97cd3f825cb1fa737ee5be1d68205004b2` |
| C | `.build/openwrt/target/linux/airoha/an7581/base-files/usr/sbin/w1700k-wifi-capabilities` | `5c7a3878530a7cfee659578630a4103558c8ba7900a5deb050c7d647c0685c8a` |
| N | `.build/openwrt/feeds/luci/modules/luci-base/htdocs/luci-static/resources/network.js` | `b2414d4ad6b7c4d1d78b437cead1c1bed12200c0d88a3f6475997fe5fa15e5fa` |
| W | `.build/openwrt/feeds/luci/modules/luci-mod-network/htdocs/luci-static/resources/view/network/wireless.js` | `9c644f19eb0aa15469343e53a92c09ee7b1a3f2bff3cd21ddd939f917512ffa5` |
| S | `.build/openwrt/feeds/luci/modules/luci-mod-status/htdocs/luci-static/resources/view/status/include/60_wifi.js` | `d6a676f950b4ffc2700d6b6c3da8e119becc38835c838a1c3fc6a915a2be3cad` |
| RPC | `.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/rpcd-2026.07.19~e37ed9d8/iwinfo.c` | `0fd26292e4239831c08dd042b4322833c04d3334bec07f24fdb9722c0ceafede` |
| IW | `.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/libiwinfo-2026.05.26~66bdd1a0/iwinfo_nl80211.c` | `ea34953ae107949a7980bd550b8a74e55fe3236761a4b238dbc5526d8377636b` |
| Names | `.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/libiwinfo-2026.05.26~66bdd1a0/iwinfo_lib.c` | `da29c16720ca2437481edfbb927c48c1409f52080953199265349ab49c1c52c7` |

The shell patch sections begin at OpenWrt patch lines 2530 and 2864. LuCI
sections begin at lines 1, 433 and 2959. Source-lock selects OpenWrt base
`28ba2708f1f609bfd134975808b2bc6ed9dc9742` and LuCI base
`506ca606d379dd69e9826b2a5e7e2ab90e6b89a5`.

No production source, source-lock, shared build, documentation tracker or Git
state was modified. Ledger unchanged by this bounded read-only audit, as
explicitly required by its scope. No router, network, browser, AP/config,
radio-association, image/flash, NPU firmware/INODE/DESC operation or unsigned
PowerShell-script workaround was performed.
