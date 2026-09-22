# MLO Security Defaults And OWE Admission

Date: 2026-09-09. Both full project goals remain open. This checkpoint corrects
verified configuration defects; it does not establish the cause of a particular
client's authentication failure or establish full NPU parity.

## Findings And Corrections

The actual generator enabled GCMP-256 and SAE-EXT-KEY automatically only for
`sae-compat` on EHT radios. It omitted them for ordinary SAE MLO, including
three-band configurations. Native hostapd GET_CONFIG confirms that both suites
were absent on all three links in the predecessor's default stages, while
explicit enablement loaded both. The actual nl80211 wiphy response advertises
GCMP-256 support, so this was not a missing driver capability.

MLO now enables the enhanced defaults. Existing non-MLO behavior, explicit
`gcmp256`/`sae_ext_key` settings and forced cipher selections are preserved.
The generator still capability-gates automatic GCMP-256 advertisement. LuCI
uses the unsaved MLO value for its checkbox defaults and exposes the GCMP-256
option for OWE and WPA3 Enterprise as well as SAE. Schema descriptions agree.

An OWE transition profile was also admitted on MLO/6GHz. Automatic transition
generated an extra open BSS; on MLO its transformed SSID/marker placement did
not satisfy the existing receiver admission contract. The correction rejects
automatic and manual transition peers in both the shell validator and the
ucode setup preflight, before configuration-file mutation. The receiver guards
were not relaxed, and ordinary 2.4/5GHz transition generation is unchanged.

Cisco's July 2026 guide documents Wi-Fi 7 certification requirements for
GCMP-256, personal-security SAE-EXT-KEY, PMF and beacon protection, and excludes
OWE transition from Wi-Fi 7/6GHz. Certification requirements are not proof that
every nonconforming configuration is rejected by native hostapd: its hwsim MLO
tests also exercise legacy cipher/AKM combinations. This patch improves defaults
without silently overriding explicit compatibility choices. Those choices may
still prevent particular clients from using MLO. [Cisco requirements](https://www.cisco.com/c/en/us/support/docs/wireless/catalyst-9800-series-wireless-controllers/223061-migrate-to-wi-fi-7-and-6ghz.html).

## Execution Evidence

| Check | Result | Boundary |
|---|---|---|
| Actual-source generation/admission | 284 checks across 57 profiles; 54 predecessor failures; three mutants detected | Target ucode; ubus inventory, radio capabilities, filesystem and MAC allocation modeled |
| Complete shell validator | 63 cases; 12 predecessor failures | Synthetic read-only UCI, board and iw data; actual regulatory helper |
| LuCI defaults | Before/current fixtures at 1280x800 and 390x844 pass | Actual option definitions and both default handlers; UCI/form/DOM adapters modeled |
| Live SAE security transitions | Five predecessor stages and two five-stage corrected runs pass their respective oracles | Native configuration, not association or traffic |
| Live OWE negative control | Rejected before commit/reload; daemon and iw snapshots unchanged | No OWE/open AP was activated |
| Rapid and settled MLD transitions | 13 stages each; six stale-SSID and six missing-file rejections per run | Daemon/kernel state; no client proof |
| Shared-key replay regression | Three old-key and three missing-marker files rejected; current native markers retained | Configuration generation, not authentication |
| Prior model suites | Credentials49, SSID90, membership24, enumeration25, transaction32/1195 assertions, LuCI11/49 rows | Preserve each suite's existing modeled boundaries |
| Builds and export | wifi-scripts and luci-mod-network build; all40 OpenWrt and3 LuCI entries reconstruct | No full hostapd/image build or flash |

The generation suite covers SAE, OWE, WPA3 Enterprise/192-bit, Fast Transition,
explicit disable/enable and forced-cipher controls, missing driver capability,
ordinary SAE/Compatibility modes, automatic transition and both manual peer
forms. It runs the actual AP/security functions, full MLO setup validation,
configuration orchestration and receiver parser/admission. Schema defaults and
actual radio generation are not executed by this model.

The three mutations omit MLO defaults, omit OWE preflight, or overwrite explicit
settings; they produce30,24 and12 failed checks respectively. Frozen baseline
generation and predecessor-only source copies support independent replay.

`native-before-after.json` checks AKM and cipher independently for30 retained
GET_CONFIG captures, rather than interpreting one combined boolean as absence
of both. `after02.log` independently checks generated and native AKM/cipher
counts during each live stage. Explicit-off remains off; explicit-on and
explicit FT-SAE-EXT-KEY work; removing overrides restores the corrected defaults.

The rapid sequence records three5GHz44-to48 primary swaps under the unchanged,
previously tested coexistence oracle. Width/center and the paired HT40 channel
remain correct, with a current-stage coexistence log event. The settled sequence
matches requested primaries exactly. Regulatory/TX policy was not weakened.

The first live probe stopped before any AP/configuration change because its
human-readable iw cipher-list check was unsuitable for this iw build. The
replacement uses the generator's actual nl80211 capability query. That aborted
preflight is not counted as a live AP pass.

## Frontend QA

Flow: SAE form -> toggle MLO -> both default checkboxes enabled -> preserve a
manual/saved override -> switch to OWE/Enterprise -> show GCMP-256 only.
Non-MLO SAE and EHT/HE Compatibility controls retain their earlier defaults.

Environment: `http://w1700k-security.test/`, intercepted locally in existing
Playwright/Microsoft Edge. Browser plugin unavailable. No external site request
or authenticated LuCI operation is represented by this fixture.

| Required Check | Result |
|---|---|
| Page identity and meaningful content | Pass |
| Runtime errors/framework overlay | None observed |
| Console errors/warnings | None |
| Interaction and override preservation | Pass |
| Desktop/mobile screenshots | Inspected; no clipping or horizontal overflow |

Screenshot paths/hashes are in `browser.json`/`artifacts.json`; images remain in
the local visualization directory. The real router's publicly served minified
wireless.js matches the built payload. Authenticated LuCI save/apply is still
unverified.

## Installed Files

| Runtime File | SHA256 |
|---|---|
| `/usr/share/ucode/wifi/iface.uc` | `ef91cb5cb1e1c6c99d07c67d9dccdc4d846ed05a2c1f36afde9f49b2e9a79deb` |
| `/usr/share/ucode/wifi/hostapd.uc` | `79004ebbb01a637a824806c7254170d55ba7a418bb137f370a305b9b4c2a4a86` |
| `/usr/sbin/w1700k-wireless-validate` | `8ad893d582ad04e3b93923747cf7aa52cf9a8a14ea5d8dd0d479cf6452a73604` |
| `/www/luci-static/resources/view/network/wireless.js` | `92897bf26ad78dd3833418552f288460730baede09cc9aff152b05ef933a8e43` |
| `/usr/share/schema/wireless.wifi-iface.json` | `a3291ac102b0b97cee5e57f128fc2b9b34b428f052b52f16c849e310b79866d0` |

LuCI source SHA256 is
`d6f8c7b9e6a227ea23ebc5cbb2303244805e22ece50b0c2bb8bf569021a8f238`;
the deployed file is the byte-verified jsmin output. Receiver and fingerprint
helper remain at the credential checkpoint's `deab7d45...` and `16db8c27...`.
Only five selected userspace files were installed, with root-private predecessor
copies retained and rollback-on-install-failure. Only wpad restarted, at zero APs.
Existing receiver, regulatory and mapped nl80211 hotfixes verify unchanged.

## Reproduction And Limits

`tests/wifi/owe_generation_program.py` emits the target-ucode generation checks
and optional mutants. `test_security_validation.py` accepts the preserved
predecessor validator with `--before`. `security_ui_fixture.py` and
`test_security_ui.cjs` reproduce the browser fixtures. Router runners enforce
the model/kernel/script/config hashes and preserve the original configuration;
do not bypass their preconditions. `SHA256SUMS` pins this checkpoint, source
authority and the exercised harnesses. Older checkpoint manifests remain
historical and were not rewritten to match later source changes.

Final state: R1/W1700K/kernel6.18.44, original radio-only configuration,
zero pending UCI/netifd changes, zero daemon/kernel AP interfaces, WLAN NPU
compiled out. No image, kernel module, country/TX policy, computer association,
calibration or recovery change. Raw captures/keys remain private. No subagents.

Real-client authentication, negotiated MLO/ciphers and throughput remain open,
including iPhone/laptop reproduction. OWE/Enterprise have generation proof,
not live AP/client proof. Explicit cipher overrides and incapable hardware are
not certified by passing negative/compatibility controls. Multi-MLD ownership,
per-station/VLAN and unchanged-path external-file content transitions remain
open. Restricted NPU INODE/DESC operations and the blocked PowerShell collector
were not retried or rerouted; full NPU recovery/parity and release acceptance
remain unresolved. All four canonical trackers are updated.
