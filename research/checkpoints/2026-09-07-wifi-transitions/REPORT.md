# MLO Membership, SSID And Config-Load Corrections

Date: 2026-09-07 local / 2026-09-06 UTC. This checkpoint is not final acceptance.

## Implemented Membership Correction

Rapid successive MLO changes reproduced a network reload timeout when returning
from radios2+0 to1+0. Hostapd created the new MLD with mask3, then reactivated
cached phy0.2 BSS settings outside that mask. Beacon setup failed. Original
configuration was restored after capture. This is distinct from client traffic.

The hostapd script now checks physical PHY/radio membership before reusing or
creating a BSS and filters every reactivation candidate source by the new MLD's
membership. Detachment still visits all old references. Membership-only SHA256:
`dd0635723b08a549814b884d3a3b4f46c85fd139c7eb644094204d561dfd456f`.
That intermediate revision is superseded by the combined script below.
No image, kernel module, NPU setting or regulatory/TX-power policy changed.

Verification passes24 actual-ucode membership cases, reproduces12
old failures and rejects3 mutants. Enumeration regression passes25 cases.
Separate transaction tests pass32 scenarios/1,195 assertions and7 mutations,
with explicit driver/framework models; they are not native-driver rollback
proof. Source reconstruction verifies38 OpenWrt and3 LuCI changed files.

## SSID Consistency And File-Open Failures

The MLD descriptor already carries the desired common SSID. The script now
retains parsed BSS SSID bytes, rejects a stale incoming radio configuration
before changing active state, and filters cached reactivation by SSID as well
as radio membership. Old-reference detachment remains unfiltered. Descriptors
without a declared string SSID retain their prior compatibility behavior.

Parsing follows the actual wifi-scripts encoder: printable strings are quoted,
other bytes are hexadecimal. Raw `ssid=` is also supported. Original config
lines remain intact for hostapd's C parser. This is not a replacement for C
configuration validation or every hand-written `ssid2=P"..."` escape syntax.

A failed nonempty config-file open is now an explicit error, not an empty
configuration that removes the working interface. The config_set dispatcher
reports invalid argument; internal admission also preserves previous state.
The existing empty-path removal operation is unchanged. Ordinary stale-SSID
requests retain the existing PID reply contract; their rejection is verified
from the guard log and unchanged running state, not inferred from CLI success.

Combined installed/prepared hostapd.uc SHA256:
`c5db50945a641ab94a31ff11de143fa28d187b046fd4adb7bdb15ea3c0086212`.
Full script compilation on R1 passed before atomic installation and wpad restart
with no AP active. Membership-only, initial SSID candidate, corrected SSID and
preexisting scripts remain privately backed up. No firmware image was flashed.

The new suite executes original parser/admission/cache functions, the actual
config_set dispatcher and actual wifi-scripts encoder in host ucode with
explicit framework models:90 checks pass,41 old-function failures reproduce,
and8 mutants are rejected. Cases cover raw/quoted/hex, embedded quotes and
backslashes, UTF-8, binary NUL, missing/stale SSIDs, retained data lines,
pre-mutation preservation and failed-open versus explicit-remove semantics.
Source, encoder, harness, generated runner, runtime and baseline identities
are pinned in `ssid-tests.json`. Existing membership/enumeration/transaction
tests were replayed against the combined source.

## Live Results

- Run01's exact primary-channel check stopped at requested5GHz44 versus actual
  48. The unchanged, hash-matched R1 wpad source deliberately swaps the HT40
  primary/secondary pair after its coexistence scan. Width and center remained
  correct. This is not a stale-configuration defect or an exact channel44
  success claim. The revised oracle only permits the same5GHz pair with equal
  width/center and a fresh per-stage coexistence message;16 controls pass.
- Run02, before the membership fix, timed out at step07 as described above.
  Its previous radio2 setup was still pending, so this is rapid-update coverage.
- Run03, with the fix, passes the original failing step07 and continues through
  independent APs, mixed AP/MLO, tri-band320MHz and an SSID change. Step13's
  rapid SSID reversal still times out with another beacon-setup failure while
  radio1/2 setup is pending. This historical run is not a sequence success.
- Run04 waits for netifd pending=false and every active radio up before each
  next change. All13 stages pass, including SSID change and reversal. Cleanup
  restores the original wireless file and confirms zero hostapd/kernel interfaces
  for three consecutive observations. No real-client traffic was exercised.
- Run05 rejected cold startup in the first SSID candidate because it decoded
  printable quoted SSIDs as hex. That candidate is not promoted. The encoder
  round-trip tests now reproduce this regression and protect the correction.
- Run06, with corrected SSID handling, passes all13 rapid stages. No explicit
  netifd-settled wait was added; phases05/06 still show pending setup. SSID
  changes now wait for matching fresh BSS configurations instead of reusing
  stale caches. These phases were already settled when the ready gate passed.
- Run07's negative replay files were root-private and unreadable to hostapd's
  network user. This invalidated its intended SSID replay, but reproduced the
  separate failed-open-as-removal defect. It reached12 settled stages, not13.
- Run08, on the combined correction, passes all13 settled stages. At each SSID
  direction it replays three service-readable old radio configs, then submits
  three missing files. All six old-SSID configs are logged as rejected; all six
  missing-file requests report invalid argument. Hostapd status and iw output
  stay byte-identical across three two-second observations in each direction.
  Test copies are private to the service account; no jail policy was weakened.
- Run09 repeats all13 rapid stages on the final combined script and passes,
  with exit0 and verified restoration. `final-router-state.json` verifies the
  exact installed script/library/JS/regulatory hashes, the library inode mapped
  by hostapd, zero netifd pending, zero AP/kernel interfaces and original config.

Each full sequence is13 configured states including cold startup, or12
transitions between populated states. It is not13 distinct transition edges.
Channel/width/center, interface/link counts, enabled state, SSID and same-anchor
MLD address stability are checked. The successful new runs have exact primary
matches; earlier coexistence adjustments remain reported separately.

Public control logs are included here. Private raw wireless/hostapd captures
and synthetic credentials remain in private router test directories;
the original wireless file is additionally backed up under ignored host-side
`.local/wifi-transitions/`. No private configuration or credentials are exported.

`tests/wifi/router_mld_transitions.sh` is the retained guarded runner, with
`rapid`/`settled` and optional `stale` replay modes. It requires explicit
temporary-AP authorization, pinned Ethernet access, the matching channel
oracle, exact source/config hashes and no preexisting AP or pending UCI change.
It restores the original configuration, refusing overwrite on concurrent edits.
`router_transition_readback.sh` verifies restoration and the loaded library inode.

The earlier2026-09-06 manifest is historical: source, tests and trackers have
advanced since its snapshot. This checkpoint's `SHA256SUMS` pins the new state.
Full NPU/parity work, actual clients, authenticated LuCI save/apply and the
remaining release gates are not closed by these results.

Next configuration coverage includes multiple simultaneous MLD groups, rapid
credential/security changes and UI-driven save/apply. Cross-owner cached BSS
consistency has not been covered by these single-MLD hardware sequences.
No claim of all configurations or actual-client reliability is made.
