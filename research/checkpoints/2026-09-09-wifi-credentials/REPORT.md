# MLO Shared-Interface Credential Reconfiguration

Date: 2026-09-09. The campaign's private router directories retain their
20260907 identifier. This checkpoint closes a reproduced stale-key admission
defect, not all Wi-Fi configurations, client reliability or NPU parity.

## Reproduced Defect

- On R1, configure a three-link SAE MLD with key A, then the same SSID with
  key B. Privately saved generated files are checked against each expected
  key. Public output contains only counts, not keys or real addresses.
- Add a test-only native `config_id` to each saved file and submit it through
  the existing hostapd `config_set` path. The matching built ARM hostapd_cli
  reads each link's `GET_CONFIG` into private files. Current-key positive
  controls prove the native marker is observable on all three links.
- With predecessor hostapd.uc `c5db5094...`, replaying A after B loads A's
  native marker on all three links while UCI still holds B. Source inspection
  of `uc_hostapd_bss_set_config()` confirms whole-BSS config replacement,
  including the checked passphrase, not an independent marker-only update.
- The first probe returned 127 from trailing shell input after the assertions;
  all three old markers and successful exact cleanup were already recorded.
  `cred01.log` is a reproduced counterexample, not a passing test. An explicit
  final exit corrects the harness issue in subsequent runs.

The SSID-only guard could not distinguish these configurations. Cached
activation and late-worker admission both used that insufficient comparison.
The controlled replay demonstrates a real daemon configuration rollback; it
does not establish how often an organic race occurs or prove client admission.

## Correction

Three userspace source files are changed in the cumulative OpenWrt patch:

- `wifi-scripts/files/usr/share/ucode/wifi/mld-config.uc`: a shared SHA256
  fingerprint with recursively stable object ordering and ordered arrays.
- `wifi-scripts/files-ucode/usr/share/ucode/wifi/hostapd.uc`: emits a per-BSS
  `#mld_config_id` from the immutable pre-default/pre-interface-mutation
  netifd snapshot. Direct setup calls take a snapshot before mutations too.
- `hostapd/files/hostapd.uc`: prepares the expected descriptor fingerprint,
  preserves the marker while parsing, and checks it for BSS admission, cached
  activation and incoming configuration before mutation. Existing SSID,
  membership, failed-open and transaction protections remain in force.

The common fingerprint excludes only descriptor additions `phy`,
`radio_config`, `4addr`, and fan-out-specific `ifname`/`macaddr`. The actual
`mlo_vif_create()` and `mlo_vif_macaddr()` functions verify agreement across
all three generated link inputs. Owner name, PHY/radio membership and address
handling retain their separate existing checks. Every successfully prepared
MLD descriptor receives a fingerprint, so missing file markers fail closed.

The fingerprint covers the shared wifi-iface input, including key, encryption,
security options and external-file path changes. It is not a whole radio or
transaction identifier. Per-station/VLAN collections and contents changed at
unchanged external-file paths are outside this fingerprint's coverage.
OWE transition synthesis changes SSID and emits another BSS; its interaction
with MLD descriptor admission has not been validated by this SAE checkpoint.

## Evidence

| Gate | Result |
|---|---|
| Target ucode / real digest.so | 49 checks pass; predecessor fails 13 |
| Mutation sensitivity | Missing ID guard, omitted key and ignored marker fail 12, 5 and 1 checks |
| SSID/load/dispatcher regression | 90 checks, 41 baseline failures, 8 mutants |
| Membership regression | 24 checks, 12 baseline failures, 3 mutants |
| Enumeration regression | 25 checks, 9 baseline failures, 3 mutants |
| Transaction regression | 32 scenarios, 1,195 assertions, 7 mutants |
| Full source reconstruction | 39 OpenWrt and 3 LuCI changed files verify |
| Candidate compilation | Receiver script and generator module compile on R1 |
| Package build | wifi-scripts compile target exits 0; staged helper/generator match source |
| Live key replay | Two corrected runs retain all three current-key native markers |
| Missing generation marker | Three requests rejected; current markers retained |
| Rapid and settled sequences | 13 + 13 stages pass with exact channel/width/center readback |
| Stale SSID and missing files | Six of each per sequence preserve daemon/kernel state |
| Final restoration | Exact original UCI file, zero pending, zero daemon/kernel interfaces |

The source-extracted credential checks use modeled framework I/O and a modeled
MLO-presence predicate for the actual snapshot function. Some field mutations
are deliberate identity controls, not validator-approved AP profiles. Actual
target crypto and producer/parser/admission/cache functions execute. These
are not client-authentication tests or full native-driver rollback tests.

`cred03.log` verifies old-key and missing-marker rejection, then compares full
hostapd/iw snapshots across three two-second observations. The transition
receipts include independent APs, mixed ordinary/MLO, topology/anchor changes,
channel changes, widths through 6 GHz 320 MHz and SSID reversal.

The wifi-scripts APK SHA256 is
`35160f9f7ac63e6e7a361ad54d04edd1702def8a453f440aad6b448687d4e374`.
The full hostapd package and firmware image were not rebuilt for this hotfix.
The package receipt verifies build success and packaging input hashes, not
fresh firmware-image boot acceptance.

## Multi-MLD Boundary

Two distinct three-band MLDs are rejected by the existing validator's physical
radio ownership rule. `multi04.log` proves rejection before config commit or
radio reload, followed by exact restoration. The guard was not bypassed or
relaxed. Earlier setup mistakes and rejected profiles are not AP test passes.

The July 12 ledger attributes the rule to cleanup of duplicate MLO owners for
one SSID. That history does not establish a hardware prohibition on distinct
MLDs. Multi-MLD support and cross-owner behavior remain open work.

## Installed State And Limits

R1 remains `gemtek,w1700k-ubi`, kernel 6.18.44, WLAN NPU compiled out. Installed
source SHA256 values:

| File | SHA256 |
|---|---|
| hostapd receiver | `deab7d45c2866548b2c6dda99168d4e78c2d927e08a657faef6e2f4644729bae` |
| wifi generator | `e0bbdf764f06f775912831794ba81ea64bf47dc25a3b29731fc1db4945ffaa41` |
| common fingerprint helper | `16db8c275cd64607845ae9b7a6093d05e260dcad5266e3cd8b61d8918d1df1f2` |

Only wpad was restarted, with no AP active. Network service, image, kernel
modules, NPU mode, country/transmit-power policy, PC Wi-Fi association,
calibration and recovery data were unchanged. Predecessor receiver/generator
copies remain privately retained on router and host. The earlier nl80211 fix
is still verified in the daemon's mapped inode; other hotfix hashes match.

All temporary AP configurations were removed after testing. Final state is in
`final-router-state.json`. Public receipts exclude keys and raw private captures.
No subagents were used for this correction. Both full goals remain open:
additional security/per-station/file-content transitions, real clients,
authenticated LuCI save/apply, multi-MLD support, NPU recovery/parity and final
release acceptance are not completed by this checkpoint.
