# W1700K V6.87 Corrective Engineering Release

Date: 2026-09-01

## Result

- Build: PASS
- Image verification: PASS
- Router `sysupgrade -T`: PASS
- Normal preserved-config sysupgrade: PASS
- Live installed-image synthetic validation: PASS, 38/38
- Current router state: V6.87, NPU mode 0, healthy
- Release class: live-validated engineering image; not stock-NPU parity

## Candidate

- Profile: `gemtek_w1700k-ubi`
- Supported device: `gemtek,w1700k-ubi`
- Image: `openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb`
- SHA256: `502745127cae575e6442ed373e12ae1047dde016d34c3fce98e76e7fd26e5c56`
- Size: 20,415,292 bytes
- FIT-volume headroom: 281,796 bytes
- Source HEAD: `73a8983e15f78c9d3f4102da074d8d484603a4d0`
- LuCI HEAD: `32ff41fc22271205fa245bcc6b2992603a91d675`
- Config SHA256: `e20b665727f06c79dfb6a7f128101db7bab42fe659569630a21b7185d6e1c2b2`

## Corrective Work

V6.86 exposed two independent MLO defects during live testing:

1. Hostapd's MLO country validation consumed `config.country`, while the
   normalized runtime object provides `config.country_code`. The alias could be
   removed before MLO setup and produce a false country mismatch. V6.87 accepts
   `country_code` first and retains `country` as a compatibility fallback.
2. A 2.4 GHz EHT40 MLO link can be forced to 20 MHz by mandatory 20/40
   coexistence. This hostapd/mt7996 stack cannot safely update an already
   assembling MLD through that fallback and can fail beacon setup. V6.87 keeps
   ordinary 2.4 GHz AP operation at EHT40 but requires EHT20 whenever radio0 is
   an MLO member.

The EHT20 rule is enforced consistently in hostapd ucode, LuCI defaults and
validation, the backend validator, and the boot-time sanity repair. Manual UCI
edits cannot bypass it. Canonical corrective patch SHA256:
`838d1f2524ec6efbe54b98b4824cc3f04fd73f61c64e40dbb122b4ea8576f016`.

The synthetic restore path was also hardened to bring WiFi fully down, remove
unexpected runtime interfaces, restore the exact saved config, and bring WiFi
back up. A failed hotfix attempt caused by a non-executable uploaded validator
is retained and labelled as a harness failure; it is not firmware evidence.

## Build And Offline Verification

- Clean affected-package rebuild completed with exactly one W1700K ITB.
- Rootfs contains 1,140 files and 187 packages.
- FIT kernel, W1700K DTB, rootfs, profile binding, and target checksums passed.
- Required WiFi 7/MLO, NPU, LuCI, SQM, adblock, and SoftEther assets passed.
- Required Airoha NPU firmware is present; forbidden stock WiFi/NPU binaries
  are absent.
- Static MLO/LuCI/backend/NPU contracts passed, including the country alias and
  2.4 GHz MLO coexistence cases.
- A first verifier run checked one marker at the wrong installed path. The
  corrected verifier passed completely; the failed run remains labelled.

## Live Flash And Acceptance

The target was identified over Ethernet as `Gemtek W1700K`, board
`gemtek,w1700k-ubi`. A fresh config backup and pre-flash UBI inventory were
captured. `sysupgrade -T` reported `Signature check OK`, then a normal
preserved-config `sysupgrade -v` was used without `-F` or `-n`.

The boot ID changed from `dd835200-6655-4368-aa7a-08637e158ce6` to
`553b814f-2a64-4d49-a3bd-4f4dddd86ebe`. The live `fit` volume prefix hashes
exactly to the candidate SHA256. `ubootenv`, `ubootenv2`, and `factory` remained
present and healthy; UBI reports zero bad physical eraseblocks. The wireless
config remained byte-identical at SHA256
`588a3e98ee05a0d8649c392c54c4e879ac74230c1ed34a2134f07649e2aa945c`.

The installed image, with no bind mounts or hotfixes, passed 38/38 tests:

- standalone 2.4 GHz EHT40 with standards-compliant coexistence behavior;
- 5 GHz EHT80 and DFS EHT160 after CAC;
- 6 GHz EHT320;
- 5+6 GHz MLO;
- tri-band MLO using 2.4 GHz EHT20, 5 GHz EHT80, and 6 GHz EHT320;
- member-radio scans with AP recovery;
- all backend impossible-configuration rejection cases;
- LuCI, DNS, SoftEther, adblock schedule, and kernel-fatal gates;
- byte-exact wireless configuration and runtime-interface restoration.

During ordered tri-band reconstruction, hostapd logged a transient failed
beacon attempt before recreating the shared MLD. All three links subsequently
reached `AP-ENABLED`, scans passed, no duplicate-interface residue remained,
and the final fatal/restore gates passed. This is retained in the raw log rather
than hidden.

## Boundaries

- These are guarded synthetic AP/scan tests, not client association, sustained
  client traffic, or throughput certification.
- NPU mode 0 is the production default. Modes 1-4 were not requalified in this
  V6.87 acceptance pass.
- Stock-parity TX ledger, completion, reset, and drain work represented by
  patches 52/79 remains `BLOCKED-DESIGN`. V6.87 does not claim dedicated
  host-adapter TX ownership parity with stock firmware.
- Independent Build B and release-authoritative provenance gates B-01/B-02/B-03
  remain open; V6.87 is a live-validated engineering image.

## Evidence

- Build receipt/log prefix:
  `/home/captain/w1700k-openwrt-build/v687-release-73a8983-20260901/build-a-evidence/20260901T172039Z`
- Successful verifier:
  `work/analysis/v687-build-a-20260901/verification-20260901T172656Z`
- Static gates:
  `work/tests/v687-hostapd-mlo-country-20260901/STATIC-GATE-2G-MLO.log`
- Live pre-build hotfix proof:
  `work/router-tests/v687-live-hotfix2-20260901T171208Z/LIVE-HOTFIX-PASS.out`
- Flash and installed-image acceptance:
  `work/router-tests/v687-preflash-20260901T172804Z`

Earlier guarded cleanup removed 18,110,191,884 bytes of exact duplicate image
and redundant WSL build data. Broader cleanup was deliberately rejected because
it overclassified retained certification evidence.
