# Wi-Fi Configuration Corrections And Router Matrix

Date: 2026-09-06. Canonical source: `/home/captain/W1700KNPU`.
Starting Git HEAD: `666b63245d3c13921cb4cdedeef4d7e3f418bd1e`.

## Reproduced Corrections

1. R1 `iw phy` prints decimal MHz values. The regulatory helper accepted only
   integer tokens, silently substituting static fallback channels. The actual
   SA driver disables 5 GHz channel 161, but the old helper accepted it. Both token
   regexes now accept decimals. No allowlist, country or TX-power policy was
   expanded. Eighty actual-shell cases pass, 18 old failures reproduce, and
   two partial-fix mutations fail. Nine BusyBox checks use actual driver rows.
2. The first MLD failed with `Reject MLD config: cannot enumerate live MAC
   addresses`. Current ucode-nl80211 returns null, without an error, after a
   successful empty multipart interface dump. Direct router probes confirm
   this and distinguish an invalid-argument error. Hostapd now clears stale
   error state, checks the new error, and accepts only arrays or successful
   null. The native decoder follow-up below is required to make that distinction
   reliable on allocation failure. Twenty-five actual-ucode cases pass, nine
   old hostapd failures reproduce, and three mutations fail. The full script
   also compiles on R1; existing/live MAC reservations remain intact.
3. LuCI's MLO loader now recognizes lowercase RPC `no_ir` flags. Disabled and
   DFS handling are preserved; see the producer/consumer detail in
   `FREQUENCY_AUDIT.md` and `FREQUENCY_FIX.md`.
4. Both LuCI runtime loaders now check mapped channel shape separately from
   static fallback membership, retaining valid driver-advertised rows.
   Static lists are unchanged. Eleven tests pass with 49 row fixtures and
   three regression mutations. Synthetic channel 169 is a contract control,
   not an allowed-channel claim for this router or regulatory domain.

Source reconstruction verifies 38 OpenWrt and 3 LuCI changed files. The source
snapshot also includes earlier unflashed NPU corrections; these script hotfixes
do not imply those kernel/provider changes reached the router.

## Live Coverage

Pinned Ethernet SSH rechecked W1700K board/layout and kernel 6.18.44. The last
flashed image is Daybreak21 R1, with WLAN NPU compiled out. Private random WPA
credentials, required PMF and unchanged country/TX-power settings were used.
The computer's Wi-Fi association was not changed.

Twenty-nine distinct configurations reached hostapd ENABLED without pending
configuration. `live-matrix.json` retains sanitized daemon/kernel facts:

- All seven nonempty independent-AP band combinations.
- All four two-/three-band MLO combinations, including the failing cold start.
- WPA2 legacy/HT/VHT, WPA2/WPA3 mixed HE, a 2.4 GHz EHT40 request, 5 GHz
  VHT20/40/80 and EHT160, 6 GHz HE20/40/80/160, EHT320 and EHT80 ACS.
- Six simultaneous BSS objects, 5+6 GHz MLO plus a separate 2.4 GHz AP, and
  tri-band MLO with its 6 GHz link at 320 MHz. These three cases each pass two
  further unchanged-configuration reloads with stable global addresses.
  The six-BSS and mixed MLO/ordinary cases have six and two unique global
  addresses respectively. Actual addresses are not exported.

The 5 GHz 160 MHz case required about one minute before ENABLED. 6 GHz ACS
selected channel 1 at 80 MHz. The 2.4 GHz EHT40 request operated at 20 MHz,
not 40 MHz. Tested 5/6 GHz widths match kernel readback, including 320 MHz.

The first post-fix MLO run reached ENABLED and restored configuration, but a
PowerShell pipe appended a carriage return after the script, producing exit 127.
An explicit script exit corrected the runner; a clean rerun exits 0. This is
not counted as a router failure or substituted for the clean rerun.

## Browser And Package Checks

The actual LuCI frequency widget, DOM and event handlers were exercised in
Playwright/Edge at `http://w1700k-fixture.test/`, with explicitly modeled RPC,
UCI, capability and form-framework inputs. At 1280x800 and 390x844, channel 169
and EHT80 selections persist and validate. Lowercase NO_IR removes a blocked
secondary channel and invalid 80 MHz choice. All-blocked maps expose no channel
or ACS. Identity, nonblank controls, console and overflow checks pass;
screenshots were visually inspected. See `browser-fixture.json`.

The Browser plugin/skill was absent; regular Playwright was used. Live LuCI's
Wireless route presents a password field. Authenticated save/apply remains
unverified; no authentication or TLS boundary was bypassed.

The exact `luci-mod-network` package target compiled successfully, including
its required host/runtime prerequisites. Optional-feed dependency warnings and
existing CSS3-parser warnings were emitted; this was not a warning-free build.
Only the changed minified wireless-page JavaScript was deployed, not the full
package or prerequisites. Exact old/new source minification matches the prior
installed and new packaged scripts. Syntax passes; HTTP returns 200 and the
expected new file hash. See `luci-package.json` and `final-router-state.json`.

## Final State And Limits

Independent review found that the native decoder could also return null
without an error after an allocation failure. This was reproduced, not waived.
Patch 112 now records NLE_NOMEM before returning false; the error remains visible
even if other records in the dump decode successfully. Six original and six
corrected native ARM64 cases execute the actual converter, reply/completion
callbacks and public error API. Failures are injected only into this process's
decoder calloc callsite, not router memory pressure or live netlink traffic.
Actual returned objects/errors feed the ucode guard tests. All three incomplete
original results evade the new guard without the companion patch; all three
corrected results are rejected. See `decoder-build.json`, `decoder-runtime.json`
and `mld-enumeration-tests.json`.

The ucode package release is advanced to 2 and its exact package target builds.
Only the stripped userspace `nl80211.so` is additionally deployed; candidate
loading and read-only netlink calls were checked before replacing the file,
then wpad was restarted. Original library bytes are retained on router and host.
The hostapd script and decoder error patch must be deployed together. Seven
post-library AP/MLO smoke checks pass, including all four MLO band combinations,
three independent APs, six BSS objects and mixed MLO/ordinary operation. Two
cases additionally pass two further reloads each. See `post-decoder-matrix.json`.
Final readback verifies the new library's inode in the actual hostapd process
mappings, all four file hashes, restored configuration and zero APs. Independent
review closes the low-memory finding with no remaining concrete closure gap;
that review inspected source/receipts and did not independently rerun hardware.

- R1 now has three persistent script hotfixes plus the companion nl80211
  userspace library fix. No image flash or kernel-module replacement occurred.
  Original scripts are retained privately on the router and under ignored
  `.local/wifi-config/`. Router `/tmp` backups are volatile across reboot;
  host-side originals are separately preserved.
  These are file-level hotfixes; package-manager inventory still reflects R1.
  Package upgrades or sysupgrade can replace them. A fully rebuilt/flashed
  release carrying all canonical changes has not been produced by this work.
- Every temporary AP was removed and the radio-only wireless file restored
  byte-for-byte, with zero pending UCI changes and zero hostapd interfaces.
  Its SHA256 is `a87e59eb9c6314be153d8af85f88ebbe0438a1cfb6e0e0ee92ee1b5f200c416d`.
  The parked SA/5 GHz channel 161 is not a valid active AP choice. The corrected
  global validator rejects it unless that unused radio is disabled or assigned
  a currently permitted channel; it was not silently rewritten.
- Calibration, factory/recovery data, image/rollback files, regulatory/TX
  policy and the computer's Wi-Fi association are untouched. WLAN NPU stays
  compiled out. Restricted NPU operations were not retried/rerouted and the
  optional unsigned PowerShell collector was not executed.
- Client authentication/traffic, long-run stability, STA/mesh/WDS, enterprise/
  OWE, every legal channel/width, changed-configuration MLO transitions and
  full release acceptance remain open. These results do not establish that
  every possible configuration works or that full stock/NPU parity is complete.

The ledger, current reference, logging session and remaining-work checklist
record these substantive source and runtime changes.
