# W1700K Stock-Port Current Reference

Last updated: 2026-09-06 (bounded layout and native GDMA contract; packaged firmware/router unchanged)

Resume checklist: `docs/REMAINING_WORK.md` lists all currently open implementation,
validation, service and release gates. Update it along with the ledger.

Storage maintenance completed 2026-09-05: C: 59.96 GiB free, D: 38.34 GiB free.
Inactive v689 prepared source/binaries are now in a verified local archive;
current source/build and all protected recovery data remain intact. See
`docs/maintenance/cleanup-20260905/REPORT.md`. Resume firmware work from the
provider-guard/recovery checkpoint below; cleanup made no router changes.

## Current Work - Bounded Layout And GDMA Contract - 2026-09-06

- Corrected emulator placement: local SRAM is bounded to a conservative 32 KiB;
  state is at `0x3e906000`, with synthetic ring data in separate 480 KiB SRAM.
  Linker/structure/symbol checks reject old out-of-window and overlapping state.
- Sixteen native reset cases verify exact BSS clear bounds and eight stack tops;
  36 allocator/table entries and the retained R1 FIT/board reservations verify.
  Ten suites, existing worker/admission regressions and four linker controls pass.
  This is not full boot, hardware SRAM/cache proof or a production reservation.
- Stock kernel GDMA/HSDMA exports recover 63 functions, 67 with referrers.
  Native ARM64 confirms WAIT polls CT0.ENABLE clear; RV32 copy polls only DONE.
  Stale-DONE early return is conditional on unverified hardware start behavior,
  not a proved live Wi-Fi fault. No physical drain witness is claimed.
- Packaged source/config and protocol sources are unchanged. No router contact,
  image, flash or association change. Real drains, boot/placement/cache closure,
  Linux recovery/removal, full parity and actual-client acceptance remain open.
- Evidence: `research/checkpoints/2026-09-06-npu-layout/REPORT.md`.

## Previous Work - Coordinator Admission Candidate - 2026-09-05

- Added unpromoted coordinator admission with active-handler retention,
  deferred IRQs, fault propagation and a versioned 64-byte control envelope.
  Original UART/PPE stop counterexamples are blocked by emulator adapters while
  mailbox status remains available. Physical reclaim/restart capability bits
  remain clear; no fake-drain wire operation or production host integration.
- 1,667 native/RV32 call pairs and six mutation controls pass. Two native
  core-0/IRQ detours plus mailbox-table rebinding pass in-flight, mask-failure,
  ABI and strict-transport checks. All eight saved contexts acknowledge through
  actual code; wire mask `0xff` without physical witnesses still cannot reclaim.
  The combined ELF also passes the prior 20 worker-detour regressions.
- New Ghidra seeding recovers missed Wi-Fi/tunnel mailbox callbacks: 427
  discovered functions export without failure. Native tests confirm unchecked
  payload length, early no-wait DONE and static-index callback-table overwrite.
  These are protocol findings, not proved triggers of live client failures.
- Packaged source/config and patch 926 are unchanged. No router, image or flash
  action. Hardware drains, full boot/placement/cache proof, Linux recovery,
  full NPU parity and actual-client Wi-Fi acceptance remain unfinished.
- Evidence: `research/checkpoints/2026-09-05-npu-admission/REPORT.md` and
  `firmware/npu/ADMISSION_ABI.md`.

## Previous Work - Seven-Worker Barrier Extension - 2026-09-05

- Combined emulator ELF now contains 20 detours for seven worker contexts:
  refill, fast/slow RX, TX done, both indirect parts and tunnel. It adds refill's
  five cached-pointer refreshes and fast RX's two cached indices, including
  startup. No deployable firmware binary is emitted.
- 16 new stop/resume cases, 96 register/MSTATUS differential cases, 17 missing
  startup dependencies, six in-flight and six interrupted-refresh cases pass.
  Three cycles execute seven saved worker contexts against shared SRAM with
  randomized ordering and alternating ring regions; 19 negative controls fail
  as expected. Existing core-5/protocol/IRQ regressions pass unchanged.
- These are serialized instruction tests with modeled helper returns,
  coordinator-0 participation and physical drain witnesses. Full boot/helper/
  IRQ path closure, coordinator admission, hardware drain and production memory
  placement are not proved. Legacy STOP/GET3 does not implement this protocol.
- Packaged source/config, patch 926 and router state are unchanged. No image,
  router contact or flash. Linux L1/full-reset/removal retention, full NPU
  ownership parity and actual-client Wi-Fi acceptance remain open.
- Evidence: `research/checkpoints/2026-09-05-npu-workers/REPORT.md`.

## Previous Work - Generation Barrier Candidate - 2026-09-05

- Added unpromoted eight-hart generation protocol with separate drain witnesses,
  stale-epoch rejection and all-hart refresh before restart. 9,351 compiled
  native/RV32 call pairs, 100 cycles and three mutation controls pass.
- Four actual RV32 core-5 detours pass startup/outer/empty-loop stop and new-ring
  resume tests in emulator memory. In-flight ACK withholding and ten register/MIE
  preservation cases pass. Other harts/drain witnesses remain modeled; no
  deployable blob or production memory reservation is claimed.
- Resolved a missing UART IRQ entry in Ghidra: 425 discovered functions export.
  Original IRQ registration/dispatch tests show UART can re-enable RX and PPE can
  reach bufid release after STOP/GET0. Coordinator IRQ/control admission is a
  required part of the full barrier, not covered by worker polling alone.
- Candidate lives in `firmware/npu/`, outside packaged source. Source lock/config,
  patch 926, last router-tested R1 and hardware state are unchanged. No router
  access, image build or flash. All-hart hooks, hardware drain/containment and
  common Linux recovery/removal ownership policy remain incomplete.
- Evidence and exact next gates:
  `research/checkpoints/2026-09-05-npu-barrier/REPORT.md`.

## Previous Work - Executable Stop Counterexample - 2026-09-05

- Resolved stock SER dispatch through the previously missing connac_if layer,
  arch/GE/PCI callback tables and registration. Original AArch64 wrapper code
  passes 16 controlled cases and two mutation controls, confirming masked status.
- Original RV32 instructions reproduce core-5 descriptor consumption after STOP4
  completes and GET3 returns zero. All eight hart selections and the core-5 entry
  route execute; empty-ring and stopped-before-startup controls pass.
- Corrected Ghidra shared-SRAM volatility and non-returning worker annotations;
  prior C output hid acknowledgement writes and merged adjacent wrappers. Final
  424-function export succeeds. The standalone page loop's reachability remains
  unproven; do not count it as a second active ungated worker.
- Five stock modules fully analyzed, all 19 selected reset targets export, and
  12 table bindings verify. Later PCI reset/PDMA operations do not establish
  independent SoC NPU containment. Hardware/cache/bus behavior is not emulated.
- No firmware source change, new image, router contact or flash. Patch 926 remains
  the source checkpoint; R1 remains last router-tested. The actual barrier and
  common L1/full-reset/removal retention policy are still unimplemented.
- Evidence, corrections and next implementation requirements:
  `research/checkpoints/2026-09-05-npu-reset/REPORT.md`.

## Previous Work - Mailbox Ownership And Stop Contract - 2026-09-05

- Added provider patch 926: command flags before producer-counter publication;
  preserve timed-out coherent request ownership until observed DONE. 143 compiled
  actual-function assertions and both preimage negative controls pass.
- Kernel prepare/compile and NPU-enabled/disabled mt76 builds pass. All six mt76
  module executable-section sets match the prior provider-guard checkpoint; active
  config is unchanged. Real ARM64 before/after structure layouts match.
- Stock kernel fully analyzed (33,676 functions; 18 mailbox/NPU exports), current
  provider object (24 functions; 2 exports), and current pristine NPU firmware
  (424/424 exports, zero failures) with a separate cache-operation decoder.
- STOP selector 4 and GET3 zero do not stop two steady-state ring/buffer workers.
  The old comparison blob was our July V28 patched input, not pristine vendor;
  this provenance error is corrected and current pristine bytes revalidated.
- No router contact or flash in this pass. R1 is still the last router-tested
  baseline. Shared L1/full-reset/removal policy and full stock parity remain open.
- Next: stock SER/reset dispatch and full-worker barrier or verified hardware
  containment before reclaiming tokens/rings. See
  `research/checkpoints/2026-09-05-npu-quiescence/REPORT.md` and remaining-work list.

## Previous Work - NPU Provider Guard and Recovery - 2026-09-05

- Implemented the absent-provider guard before six coherent NPU allocations:
  1.25 MiB avoided on the MT7996 path; attached-provider semantics unchanged.
- 20 compiled-C fault cases and the unpatched negative control pass. Real
  NPU-enabled and disabled package builds pass; all normal-DMA executable
  module sections match the retained baseline. Build config remains unchanged.
- Ghidra fully analyzed 27 + 21 stock functions and 314 current initialized
  executable functions; 53 selected exports pass and are SHA-bound to ELFs.
- Confirmed both L1 unchecked errors and the full-reset token release before
  NPU quiescence. These remain unresolved; no active-NPU image is approved.
- New source checkpoint is ahead of the last router-tested R1 release. No new
  image/flash or runtime configuration change. Fresh pinned Ethernet readback
  confirms W1700K, kernel 6.18.44, WLAN NPU compiled out, healthy memory.
- Continue with provider/stock reset-coordinator drain semantics, then a shared
  L1/full-reset/removal ownership policy. Do not only add L1 return checks.
- Evidence and exact next gates:
  `research/checkpoints/2026-09-05-npu-attach/REPORT.md`.

## Canonical Workspace Migration - 2026-09-05

The canonical repository is https://github.com/MCShotty/W1700KNPU (private), with
local checkout `/home/captain/W1700KNPU`. Start future work here. The previous
Windows task directory is archival input, not the working source authority.
Current firmware source is represented by `firmware/source-lock.json`, complete
public-base-to-working patches, overlays, and build configuration. All 35 changed
files passed reconstruction/hash checks. Initial import commit:
`4a5a3fe0589d34849fc8b8c53559a06db01238e6` (175 files; remote/local tree identical).
See `docs/migration/REPORT.md` for final migration/cleanup receipts and retained
private/local artifacts. Historical paths below remain original evidence.
No router configuration, flash, radio, NPU behavior, or live acceptance state is
changed by this migration. The live authority below is the last verified state,
not a fresh router check during cleanup.

Use this file as the first stop for future W1700K stock-firmware-port work. It points to the canonical comparison/logging file and keeps the current state short enough to be usable.

## Current Live Authority - Daybreak21 R1 - 2026-09-05 03:55 +03:00

- R1 is flashed and responding, kernel 6.18.44, exact running FIT SHA256
  `0788f405337ceb030d873463bbf278497dcd9b86e8f75a1a3f57fd318eda195f`,
  20,439,877 bytes. The installed module hashes match verified artifacts.
- This is an explicitly WLAN-NPU-compiled-out engineering baseline. Ethernet
  offload is separate. It is not legacy numeric mode 0, active-NPU recovery
  repair, completed stock parity, or production/throughput certification.
- Live tests pass: three standalone bands; 5+6 and tri-band MLO (ordered
  radio1, radio2, radio0); scan API calls for all three; five invalid-config
  rejections; teardown and exact original-config restoration. Scan results are
  shared-wiphy caches, not proof of fresh discoveries on each physical band.
- Factory SHA256 remains c4f85d5f4abd6c65619c06612ce41861e5a819f89a190c632ef29366ecd3cbfd.
  Wireless SHA256 remains a87e59eb9c6314be153d8af85f88ebbe0438a1cfb6e0e0ee92ee1b5f200c416d.
  No permanent test SSIDs/interfaces or pending global UCI changes remain.
- R1 fixes the real jshn/nounset status-helper failure and recognizes the
  built-in airoha_eth driver path. The real-jshn clean-environment mutation
  regression is now part of the default integration verifier.
- LuCI Wireless/NPU render on the actual router; Refresh and MLO open/dismiss
  pass at 1365x900 in headless Edge/Playwright over a pinned SSH tunnel. No JS
  page errors or post-auth console warnings/errors. The tunnel is closed.
- Additional GUI proof: tri-band MLO saved with one click and survived reload;
  staged radio order 1/2/0, SAE and PMF=2 verified. No hidden-invalid-field or
  TypeError failure. This used temporary legal channel36, did not apply the
  staged network, logged out its session and restored original config bytes.
- Current bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-Daybreak21-WLAN-DMA-R1-20260905`.
  LIVE-REPORT, LIVE-VERIFICATION and GUI-SAVE-VERIFICATION record scope.
  All 31 checksum entries pass after the GUI addendum.
- Evidence: `work/router-tests/daybreak21-preflash-20260905-033019`.
  Private backups are ACL-protected there, outside FinalResult.
- Remaining: actual client/throughput tests; CPU-frequency SMC readback and
  missing cpufreq policies; safe active-NPU recovery and full stock hostadpt
  parity. Do not restore the old assumed 1.2 GHz clock fallback.
- Original inactive 5 GHz config is SA/channel 161; it is not AP-usable in the
  current regdb. Tests used channel 36 temporarily. Do not mistake preserved
  configured intent for an active valid AP or bypass validation to apply it.

This section supersedes older current/live/offline/no-flash statements below.
V6.87 remains a verified rollback artifact, not the currently running image.

## Current Work - Daybreak21 WiFi Corrections - 2026-09-04 21:53 +03:00

## Latest Offline Candidate - 2026-09-04 22:58 +03:00

- Full WLAN-DMA image build succeeded. Sysupgrade ITB is 20,439,877 bytes,
  SHA256 `be5257cbd34547f316b471f2064f0ac5ff25c9ae3a0d0f0051d0d303aa85a123`.
- Final bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-Daybreak21-WLAN-DMA-Engineering-20260904`.
  All 27 checksum entries replay successfully. Includes image, report, source
  diffs/overlay, config, build log, package/rootfs manifests and verification.
- FIT hashes, exact DT model, compatibility 2.0/new_supported_devices metadata,
  official NPU firmware bytes, packaged LuCI syntax, and executable sections
  matching the Ghidra-audited modules all pass. No stock modules/bootloader/
  chainloader/private keys or router backups are included in the bundle.
- This is explicitly WLAN NPU compiled out, Ethernet offload unchanged. It is
  not the old numeric mode 0, not active-NPU recovery repair, and not stock parity.
- NOT FLASHED. Router-side sysupgrade -T, migration content review/backup,
  boot, scan/reload, MLO/client, memory, and throughput acceptance are pending.
  Serial Linux identity is verified; pinned network SSH timed out. Existing
  live V6.87 acceptance remains historical, not proof of this candidate.

The completed offline candidate above supersedes the in-progress build notes
below. Do not erase their failure/recovery evidence or promote offline checks
into runtime acceptance.

Update at 22:51: both driver variants compile and the binary verifier passes.
Full Ghidra analysis completed for six ELFs; 27 selected defined functions in
the upstream comparison and 8 in the WLAN-DMA baseline decompile successfully.
The baseline has no WLAN NPU init/stop symbols or calls. The full image is still
building after correcting build-local Windows PATH inheritance and preserving
one interrupted Meson cache. Neither recovery required firmware source changes.

The serial shell is restored and 25 short diagnostic commands were captured.
MemAvailable was 1,660,876 kB of 1,867,960 kB; LAN4 negotiated 1000 Mbps, with
br-lan at 192.168.1.1/24. Captured logs matched no fatal/OOM patterns. Reading
the virtual eth0 speed returned Invalid argument and is not treated as a
physical-port fault. Preservation inventory contains 40 paths, with no listed
module/init/hotplug files; retained rc.local/sysctl/config still need review.
Strict pinned SSH via the existing PC WiFi route timed out before authentication.
No WiFi association/route change, configuration write, reboot, or flash.

Update at 22:20: the eight corrected files are now integrated and all ten
selected components compile successfully, including mt76/mt7996. Parent reran
165 LuCI, 43 generator, 38 merged MAC/allocator, and 535 shell assertions. A
separate audit confirmed unchecked active-NPU recovery failures. The explicit
WLAN-NPU-disabled diagnostic build is now rebuilding from the added package
gate; Ethernet/offload/DTS are unchanged. Full Ghidra auto-analysis of preserved
NPU-enabled comparison modules is running. No complete firmware image yet.

Fresh serial evidence at 22:14-22:15 confirms Linux root access on
`gemtek,w1700k-ubi`, model `Gemtek W1700K (OpenWrt U-Boot layout)`, kernel
6.18.34, revision r0-73a8983. This corrects the earlier unknown-boot-state
statement below. The first health capture was incomplete; Ethernet remains
disconnected on this PC. No configuration changes, upload, reboot, or flash.
See `patch85-router-preflight-daybreak21-20260904/serial-active-probe-REPORT.md`.

- Current-nightly source is the isolated WSL tree
  `/home/captain/w1700k-openwrt-build/openwrt-w1700k-daybreak20-20260904`,
  OpenWrt `f3173f41940ab15d63a205f6d618e145d49ee58a`, LuCI
  `83073becd3e0e217a7e55f04ad71b32cfefaf26c`, mt76
  `be5ce7910521492d4a2e4ce7ee3843680a46c047`. The committed WiFi composition
  supersedes the older statement that only GRO_HW was integrated.
- Profile/local-package and current NPU debugfs changes remain uncommitted.
  Prior kernel/package build logs are component evidence, not a complete image.
  Daybreak19 host-adapter lifecycle is NOT migrated into current mt76.
- Daybreak21 isolated corrections and tests live under
  `work/analysis/patch85-wifi-regression-fixes-daybreak21-20260904`.
  Main reran 43 actual generator tests plus 38 merged service/allocator tests;
  full generator/mac80211/service syntax passes. Workers report 161 LuCI and
  535 focused shell assertions passing. Integration/build gates remain open.
- The unfinished cross-service generation-counter design is quarantined in
  `deferred-generation`, not shipped. It defeats unchanged-config equality
  and was not wired through the service API. The replacement preserves raw
  per-run MLO settings before schema normalization and validates early/late.
- User reauthorized router testing and newly compiled image flashing. Fresh
  read-only preflight found Ethernet disconnected (0 bps), no historical
  `192.168.1.224` source, and `192.168.1.1` routed through this PC's WiFi.
  No router connection was attempted. Do not treat V6.87's historical state
  below as fresh verification, and do not change this PC's WiFi or routing.
- No new sysupgrade image, upload, reboot, or flash in this continuation.
  Next: review/integrate the isolated fixes, rebuild changed packages and the
  exact profile, inspect FIT/DTB and contents, then verify Ethernet identity
  and perform guarded synthetic tests. Stock NPU parity remains incomplete.

This section is current work authority; the V6.87 section below records the
last accepted live image, not a fresh connectivity or runtime observation.

## Current Authority - V6.87 Live Acceptance - 2026-09-01 20:40 +03:00

- V6.87 is currently flashed and is the authoritative live engineering image.
  Image SHA256 is
  `502745127cae575e6442ed373e12ae1047dde016d34c3fce98e76e7fd26e5c56`;
  size is `20,415,292` bytes. The live `fit` prefix matches this hash exactly.
- The running target reports `gemtek,w1700k-ubi`, model
  `Gemtek W1700K (OpenWrt U-Boot layout)`, revision `r0-73a8983`, and boot ID
  `553b814f-2a64-4d49-a3bd-4f4dddd86ebe`.
- V6.87 corrects the normalized MLO country field and requires EHT20 only when
  2.4 GHz radio0 participates in MLO. Standalone radio0 EHT40 remains valid.
  LuCI, hostapd ucode, backend validation, and boot sanity enforce one policy.
- The installed image passed 38/38 guarded mode-0 synthetic tests with no
  stderr: 2.4 GHz, 5 GHz EHT80/EHT160 with CAC, 6 GHz EHT320, 5+6 MLO,
  tri-band MLO, radio scans, impossible-config rejection, services, fatal-log
  gate, and byte-exact restoration. Wireless config SHA256 remained
  `588a3e98ee05a0d8649c392c54c4e879ac74230c1ed34a2134f07649e2aa945c`.
- UBI is healthy with zero bad PEBs. `ubootenv`, `ubootenv2`, and `factory`
  remain present. The flash used normal preserved-config `sysupgrade -v`, not
  `-F` or `-n`; bootloader and factory/calibration data were not targeted.
- This is live-validated engineering evidence, not client/throughput or stock
  NPU parity certification. Patches 52/79 TX ledger/completion/reset/drain
  remain `BLOCKED-DESIGN`; modes 1-4 were not requalified in this pass.
- Authoritative report:
  `work/analysis/v687-build-a-20260901/REPORT.md`.
- Flash/live evidence:
  `work/router-tests/v687-preflash-20260901T172804Z`.
- Final bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.87-Corrective-Engineering-20260901`.
  Its 82 payload hashes and sizes replay independently with zero failures; no
  router backup or chainloader is included.
- Earlier guarded cleanup recovered `18,110,191,884` bytes. Broader deletion
  remains prohibited because the withdrawn Stage 2 inventory includes retained
  certification evidence.

This section supersedes every older `current`, `latest`, live-handoff, and
non-promotion statement below wherever they conflict.

## Current Release State - 2026-09-01 14:14 +03:00

- V6.70 remains the current live-accepted image.
- V6.84 is reproducible and passed its original offline certifier and
  router-side `sysupgrade -T`, but subsequent review found an EPCS
  helper/driver mismatch and a synthetic restoration false-pass. It is
  quarantined and must not be flashed or promoted. Historical V6.84
  certification sections below remain evidence, not current promotion status.
- Current clean source is root commit
  `73a8983e15f78c9d3f4102da074d8d484603a4d0` with nested LuCI commit
  `32ff41fc22271205fa245bcc6b2992603a91d675`.
- Focused corrective tests, affected package rebuilds, and a full V6.85
  engineering build pass. The baseline ITB is `20415301` bytes with SHA256
  `afef7f35ff18c050f441ec55d5637f7af11beaf7f0a517f263184c3399577a9d`.
  The hardened r6-final engineering audit passes 46 adversarial contract tests
  and 11 artifact gates, but does not bind the image to build provenance; r4
  and r5 are smoke evidence only. Independent Build A and certifier hardening
  are active. V6.85 is not reproducibly certified or promoted until Build A,
  hardened release certification, a separate Build B, and exact paired
  comparison all pass. Newly confirmed NPU lifetime defects also prevent V6.85
  from being treated as a flash candidate even if those provenance gates pass.
- Dedicated host-adapter ring geometry and publication ordering are
  implemented. TXFREE carries only a generationless 15-bit token; stale
  completion after reuse remains ABA-ambiguous. Fresh full-image RV32 Ghidra
  analysis confirms stock has no hidden generation, epoch, retired-state, or
  duplicate-suppression check; duplicate completions can enqueue and later
  allocate the same token twice, and stock stop is not a TXFREE drain. Global
  packet identity, teardown/drain, reset-generation, scatter, PPE/FastTX fate,
  and runtime parity remain open. The first executable ledger model also failed
  adversarial review on twelve lifecycle, identity, certificate, and
  concurrency gaps. Patches 52/79 are `BLOCKED-DESIGN`.

The older sections use historical labels such as "current", "latest", and
"canonical". Where they conflict with this top section or the final
"Current-State Authority And Retractions" section, those two sections are
authoritative as of the `Last updated` timestamp.

## Source Reconstruction Status

- The former source checkout at
  `/home/captain/w1700k-openwrt-build/fanboy-source` was deleted during the
  2026-08-31 WSL incident and must not be used or described as current.
- Reconstruction used for V6.85 is at
  `/home/captain/w1700k-openwrt-build/fanboy-source-recovered-20260831`.
  Its OpenWrt base and five feeds are pinned to the captured commits, 501
  manifest actions were hash-replayed, and the later 386-file patch snapshot
  has zero filename or hash mismatches. The final `.config`, LuCI, hostapd,
  Airoha, and core source gates needed for the V6.85 engineering build are
  closed at OpenWrt commit `73a8983e15f78c9d3f4102da074d8d484603a4d0`
  and LuCI commit `32ff41fc22271205fa245bcc6b2992603a91d675`.
- Fresh compile and immutable engineering-image evidence exist. Independent
  paired-build certification, promotion, and hardware acceptance remain open;
  no reconstructed image is flash-approved yet.
- Recovery evidence starts at
  `work\recovery\incident-20260831`; the append-only current-state entry is in
  `work\W1700K_STOCK_PORT_LEDGER.md` under "WSL Source Reconstruction Gate".
- This source incident did not contact or change the router. The runtime/image
  statements below remain the last recorded hardware state, not validation of
  the reconstructed checkout.

## Live Handoff

- V6.70 is the currently flashed and live-accepted image. Image SHA256 is
  `c076d8501f8f4cfce2442dee08effc7d57be49e18e7197355d77d1ff3ce08998`.
  Mode 0 passed 37/37 and stock-topology mode 3 passed 42/42. The exact
  511/512/1024-frame lifecycle matrix, two reload cycles, negotiated EHT NSEP
  policy, COM3 boot evidence, and final mode-0 restore all passed.
- V6.81 is the latest offline-passed candidate. Image SHA256 is
  `ae23a15d7a1029127f5e2b4efcba829172cd067b2d293d39ab58c2703e68bb66`.
  It retains V6.80 and corrects the stock Type-5 source-word interpretation:
  stock uses RX descriptor `data` at `+0x08`, while `info` at `+0x04` remains
  PPE/count/reason metadata. V6.81 adds default-off, observe-only data/fate/
  hook telemetry and makes no packet or skb-control mutation. The 32-bit
  exhaustive-equivalence model, 55 source checks, 29-unit Sparse audit, six
  full Ghidra analyses covering 1,976 functions, 45 Ghidra/ELF checks, full
  image build, and exact FIT/rootfs candidate gate passed. It is not flashed
  or live accepted; V6.70 remains authoritative.
- V6.80 is the previous offline-passed scatter-reuse candidate, SHA256
  `000c1e1d1f7111141f33e65feaabf384eb4a9b54d517b589f9d12922659c0a4b`.
  Its independent 84-record bundle replay remains valid.
- V6.59r2 remains the previous fully accepted and promoted bundle. Its image
  SHA256 is
  `efabd59f09de0aeda8a258b7927aeb1c63b901823e49664cde54165e7d253957`;
  offline status is `PASS_V659R2_OFFLINE_CANDIDATE` and live status is
  `PASS_V659R2_LIVE_ACCEPTANCE`.
- The router is safely restored to production mode 0 with module line exactly
  `mt7996e` and V6.70 boot ID `1d385777-bef3-4512-a557-ef2b1097d428`. LuCI, SSH,
  UBI, pstore, and memory are healthy. The three default AP interfaces are
  disabled, so no SSID is expected until a WiFi interface is enabled.
- Current V6.68 report:
  `work\W1700K_V6.68_DOWNSTREAM_WFDMA_LIVE_ACCEPTANCE_20260829.md`.
- Ethernet-bound SSH source `192.168.1.224` and COM3 at 115200 8N1 both
  identify `Gemtek W1700K (OpenWrt U-Boot layout)`. Keep host Wi-Fi on the
  Internet router; unbound `192.168.1.1` traffic remains ambiguous because a
  different Wi-Fi peer uses the same address.
- In prior V6.59r2 testing, mode 0 independent radios and tri-band MLO passed.
  Mode 3 also formed tri-band MLO and the stock ACK-SN selector reported 1
  attempt, 1 success, 0 failures, and last ifindex 1. Mode 3 remains
  experimental; use mode 0 as the production default.
- Prior V6.59r2 full report:
  `work\W1700K_V6.59R2_ACK_SN_LIVE_ACCEPTANCE_20260829.md`.
- Promoted bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.59r2-ACKSN-Live-20260829`.
- Recovery FIT SHA256:
  `c121b33c14f83f59f95483905d98e4639a9275da19384e299c80b92c5baa3fda`.
  Restore image SHA256:
  `d0c02e77d5168ded74e03bfbf662ee417400f645287259071f700bf91f6d7e66`.
- V6.16 R2 is recovery-safe only in mode 0 at this checkpoint. Two exact
  mode-3 native-L1 tests rebuilt NPU/SER ownership and then reproducibly hit
  an ARM64 write translation fault. Do not select mode 3 or promote V6.16 R2
  until the stale ownership/lifecycle defect is fixed.
- V6.54 is a historical offline candidate and remains unflashed. Image
  `work\w1700k-wifi-npu-v6.54-20260806-sysupgrade.itb`, SHA256
  `9b0c04db61ca16a9d2b9c60cc5e69402ad48a5f027f5fe7155e27779fdd682dc`;
  exact verification reports `PASS_V654_OFFLINE_CANDIDATE`.
- Historical V6.54 inherits V6.53's Ghidra-verified teardown/HIF2 hardening and the
  cumulative NPU work. Its only payload-source delta is a W1700K-only netifd
  guard that skips an order-dependent global antenna-mask write on the shared
  mt7996 wiphy; kernel, DTB, and all three mt76 modules are byte-identical.
- V6.28 remains a historical candidate. It adds a conservative QDMA
  reason-`0x16` RX-to-WiFi consumer controlled
  by `stock_wifi_fasttx_consume`. The compiled BSS default is disabled. It
  commits only fully gated linear unicast IPv4/IPv6 frames to one
  `dev_queue_xmit()` handoff; every decline retains the normal GRO path.
- V6.27 separated stock RX-info tags `0x7274` and `0x7275`, exported physical
  mt7996 band index 0/1/2 to the Airoha WDMA path, and corrects stale helper
  and firmware-test claims. V6.28 retains that work, V6.25's reset correction,
  and the cumulative ownership/TXFREE/RRO work. V6.15 remains the accepted
  live synthetic baseline until serial-backed gates pass.
- V6.25 retains the cumulative V6.20 through V6.24 ownership/TXFREE/RRO work
  and corrects the stock WFSYS reset pulse to use literal BAR0 offset
  `0x1f8600`. V6.15 remains the accepted live synthetic baseline until V6.25
  passes staged hardware gates.
- The netconsole diagnostic image
  `work\w1700k-v616-r2-netconsole-diagnostic-20260716-sysupgrade.itb` is
  rejected and must not be flashed again.
- V6.15 is a historical accepted synthetic baseline. Its image SHA256 is
  `9107077012fd8b3af708f0a6c5e5e1f19c37339625a2d6536a77cda59f642144`.
- Layout remains `gemtek,w1700k-ubi`. Preserve the bootloader, factory data,
  calibration data, and Windows Wi-Fi route. Bind future router traffic to a
  confirmed Ethernet source only after the W1700K management address is
  positively identified.
- Exact Oops evidence:
  `work\live-v6.16-r2-exact-mode3-20260716` and
  `work\live-v6.16-r2-exact-mode3-oops-20260716`.
- External-client throughput/MLO, live fatal-WM download-state recovery, and
  consuming FastTX/ping-pong packet fate remain open. V6.28 implements only a
  dormant, narrow linear FastTX boundary. The historical claim that observed
  TXFREE was closed on paper is retracted: stale completion after 15-bit token
  reuse remains ABA-ambiguous. Hostadpt TX/scatter and RRO token/BA integrity
  still require staged live validation. Byte-identical global allocator parity
  is deliberately not required.

## Latest Offline V6.28 Dormant FastTX Consumer Candidate

- Report: `work\W1700K_STOCK_FASTTX_CONSUMER_V628_20260718.md`, SHA256
  `adcc02ad50a0fb45fa5f2b3d1f5f300bcc8943a3aaa95bb01a3e6f51f1ccc4f3`.
- Design: `work\W1700K_QDMA_FASTTX_CONSUMING_HANDOFF_DESIGN_20260718.md`,
  SHA256
  `961229325bd1971930dbaf80487c92cb31f7508cba23cf559dfdb65f0c05523f`.
- Image:
  `work\w1700k-stock-fasttx-consumer-v6.28-20260718-sysupgrade.itb`,
  20,607,804 bytes, SHA256
  `d6d5ae7ff73db6b230fb5c8f2438c4c2749fb5457a0931e8f8f076ad941cc584`.
- Patch: `999-67-net-airoha-add-dormant-stock-wifi-fasttx-consumer.patch`,
  SHA256
  `b4c14b113eb1cc27aad3e645f6e28add54f905110a9069110412d5c94a665102`.
- Checked bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\Experimental\NpuStockFastTxConsumerV628-20260718-UNFLASHED`.
  All 59 checksum entries and all 58 manifest entries pass.
  `SHA256SUMS.txt` SHA256 is
  `c538e6d22d928a0de58280d4f856aa24dbc1696df579141273391105b7c10200`;
  `FILE-MANIFEST.txt` SHA256 is
  `730588520b1e9dc3dc9137f98570854e08173dad759091819a2f0d3a46fd693d`.
- Source invariants pass `52/52`; the ownership model passes 262,144 cases;
  strict checkpatch, clean kernel completion, full image build, exact FIT/
  rootfs/module audit, compiled symbol/disassembly proof, and bundle checksum
  verification pass.
- The consumer is disabled by default. Tomorrow must establish unchanged
  default-off behavior first, then enable it only for a bounded serial-backed
  test with reason/commit/xmit/fallback counters and immediate rollback.
- Runbook: `work\W1700K_V628_SERIAL_LIVE_GATE_RUNBOOK_20260718.md`. The
  bundled router-side gate is read-only by default and its offline fixture
  proves bounded enable, watchdog disable, counter reconciliation, archive
  creation, and final parameter `N`.
- Direct ndo, nonlinear/scatter, VLAN, multicast, MVAL, vendor RPS/rate-limit,
  dedicated hostadpt rings, TXFREE/token/RRO final interaction, and full
  ping-pong packet fate remain deferred or unproven.

## Previous Offline V6.27 RX-Info and Tri-Band Metadata Candidate

- Report:
  `work\W1700K_STOCK_FASTTX_RXINFO_AND_TRIBAND_METADATA_20260718.md`, SHA256
  `9bfb7f421cf4653c3c7df75da384616067897186aa503bffd0bb6990b7950112`.
- Image:
  `work\w1700k-stock-rxinfo-triband-v6.27-20260718-sysupgrade.itb`, SHA256
  `a8485ee4c3477b0833189b76acdfdb24b6458a975883a43dd956f8d7485559be`.
- Checked 98-file bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\Experimental\NpuStockRxInfoTriBandV627-20260718-UNFLASHED`.
  All 97 checksum entries and 96 manifest entries pass. The checksum-set
  SHA256 is
  `c7298a18f75da1e8eaf419ffbc22648310d628a3717fe76ea04cc4c763274283`;
  the manifest SHA256 is
  `eb683d29065839ccaad03bffa7438c8933617ae17b011db7f24365d984e9ff03`.
- Source invariant verification passes `42/42`; strict checkpatch, shell
  syntax, ShellCheck error severity, source fixtures, target/kernel and mt76
  compilation, full sanitized-PATH image build, and exact-image audit pass.
- The reason-`0x16` observer now uses stock RX-info tag `0x7275`; `0x7274`
  remains the separate WiFi/NPU TX observer. This is still read-only and
  non-consuming. The physical band index reaches the Airoha WDMA queue field,
  while the one-bit WED selector is clamped only at its hardware boundary.
- Mode 3 does not implicitly apply stock ACTDP policy. Use the explicit
  `apply-stock-txrx-policy` action only during a bounded serial-backed test.
  V6.27 is superseded offline by V6.28; it remains unflashed and unpromoted.

## Previous Offline V6.26 FastTX Reason-22 Candidate

- Report:
  `work\W1700K_FASTTX_PINGPONG_OWNERSHIP_AUDIT_20260718.md`, SHA256
  `09facae869ffb104de4a1df8716d5896300f525187e996d679a02bebbba422d9`.
- Patch:
  `target/linux/airoha/patches-6.18/999-57-net-airoha-ppe-observe-stock-fasttx-reason22.patch`,
  SHA256
  `014289ae25ee68068b14729d170899be9a1fbc9ae7eef89e2499891ac832d60f`.
- Checked 59-file bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\Experimental\NpuFastTXReason22V626-20260718-UNFLASHED`.
  `SHA256SUMS.txt` SHA256 is
  `58cf717eedf17ea3960c17c77395c23311f53bfde22aed055ca08ab0f9c0e0d4`;
  `FILE-MANIFEST.txt` SHA256 is
  `cc11e944dd3e724c8dd30d2261c9fb9d3e1d8121cf7ff95dccbc25f23775c29d`.
- Stock Ghidra proves the consuming hook belongs at Ethernet QDMA RX before
  `eth_type_trans()` and before mt76 token/DMA/TXWI/TXFREE ownership. V6.26
  observes the stock reason/tag and leaves packet ownership unchanged.
- The helper and LuCI expose only compiled writable controls. Retired
  hostadpt/FastTX/ping-pong ownership work remains diagnostics, not policy.
- Full exact-kernel Ghidra analysis, strict checkpatch, focused/full builds,
  `21/21` source verifier, zero-new-warning gate, and exact embedded LuCI/
  helper/module/firmware/forbidden-binary audit pass.
- V6.26 is offline verified, unflashed, and not promoted. Tomorrow's first
  gate is serial-backed mode-0 recovery/baseline; only then run bounded
  reason-`0x16` and mode 0 versus mode 3 tests.

## Latest Offline V6.25 Raw-BAR Reset Candidate

- Report:
  `work\W1700K_DEAD_WM_RAW_BAR_RESET_V625_REPORT_20260717.md`, SHA256
  `70db110824e2aad002adf83193dacf5bc4af30ed0db3379e37b4e87dee1c21f5`.
- Patch:
  `work\patches\9999zzzp-mt7996-address-stock-wfsys-pulse-through-bar0.patch`,
  SHA256
  `3f5110ef1e5e7e3ac66db97a974f2a7606d0267cdd484fd32e791bb90711b41f`.
- Checked 99-entry bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\Experimental\NpuRawBarResetV625-20260717-UNFLASHED`.
  `SHA256SUMS.txt` SHA256 is
  `bb6923ac2b0d277713141f431cf68344b8a12f7e97bfa2127927d6ee94cb7fa8`;
  `FILE-MANIFEST.txt` SHA256 is
  `0543c351b5ed3099d997e645a3f68c7f8a0136ee7017e170f4b581f8b8e16429`.
- Stock Ghidra proves action-5 chip-ops slot `+0x28`, the MT7990
  `0x1f8600` assert/delay/deassert callback, and PCI raw
  `BAR0 + (offset & 0xffffffff)` writes.
- The old `mt76_wr(0x1f8600)` path used MT7996 L2 BAR window `0x1600` and
  remap value `0x1f8`; V6.25 bypasses translation through saved bus-ops slot
  `+8` and writes the literal raw BAR offset.
- Strict checkpatch, clean focused/full builds, zero-new-warning comparison,
  source/address model, exact FIT/rootfs/module audit, stock/current Ghidra,
  and independent verification pass.
- This is an offline correction, not a dead-WM recovery claim. Tomorrow's
  gate is V6.15 mode 0, V6.25 mode 0, then one bounded mode-3/dead-WM serial
  attempt with V6.15 rollback ready.

## Latest Offline Teardown-Hardened Candidate

- Report:
  `work\W1700K_STOCK_HOSTADPT_DESCRIPTOR_TEARDOWN_CLOSURE_20260717.md`,
  SHA256
  `f961a96e3dd498f61520837b3824eef9e8eaae5f547cf9c713696d2d9e742ce4`.
- Patch:
  `work\patches\9999zzzf-mt76-quiesce-npu-producers-before-teardown.patch`,
  SHA256
  `9296142af132dbb8c3b8eb98b94f9846e43de26c88f39e94a95bf49a64e934a4`.
- Checked bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\Experimental\NpuTeardownHardenedV618-20260717-UNFLASHED`.
  All 12 checksum entries verify. `SHA256SUMS.txt` SHA256 is
  `32ec4399af31d41a73bb8603e9c7cba973fea62ee3d76d9e78ed7ce389b33a64`;
  `FILE-MANIFEST.txt` SHA256 is
  `9988a51cc86b9eeacaa71fb6e58749f2bce94a3377b6fdbbe01962e92e8fd988`.
- Full Ghidra 12.1 analysis and save succeeded for the exact final unstripped
  `mt76.ko` and `mt7996e.ko`. The archive SHA256 is
  `ca29bbdabc6717712ddb3d52de4fdd3ffceac3d5f27f34a020556586532cb355`.
- The teardown audit found a concrete devm-IRQ queue use-after-free window and
  a TX-worker publication race. V6.18 explicitly removes/synchronizes NPU RX
  handlers, drains NAPI, parks the worker, and reports a final bounded NPU
  stop failure before releasing resources.
- Stock Ghidra relocation/profile evidence now proves group 1 is the MT7991
  slave `band2 TXD`/6 GHz transport; group 0 is the primary MT7990 2.4/5 GHz
  transport. This is an identity proof, not a claim of byte-identical vendor
  object ownership.
- Strict checkpatch, clean package preparation, focused mt76 compile, full
  image build, FIT/component audit, firmware inventory, module identity, and
  forbidden-stock-module gates pass. No router operation occurred.
- After COM3 recovery, test V6.18 rather than V6.17: mode 0 first, then a
  bounded mode-3 retained-ring/native-L1 lifecycle gate. Do not promote it or
  leave mode 3 persistent before those checks pass.

## Predecessor Offline Retained-Ring SER Candidate

- Report: `work\W1700K_NPU_RETAINED_RING_SER_V617_20260717.md`, SHA256
  `8f396d8d8b74c791565b19c4f9d797f8584b2e653b579962708ddbb85e9e6379`.
- Patch: `work\patches\9999zzze-mt7996-preserve-npu-hostadpt-rings-across-ser.patch`,
  SHA256
  `6d729d2e4b30238b8ca80d97769f6a9a4582b92beef8d482b9e0ac546f5ab292`.
- Checked bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\Experimental\NpuRetainedRingsV617-20260717-UNFLASHED`.
  Its 15-entry `SHA256SUMS.txt` verifies clean and has SHA256
  `58fe096ae47e0f904cce50e28036a0b7565ca81892633b7189e3d21956e69ddf`.
- Full Ghidra auto-analysis and save succeeded for unstripped `mt76.ko` and
  `mt7996e.ko`. The archived project/decompilation bundle is
  `w1700k-npu-retained-rings-v6.17-20260717-ghidra-analysis.zip`, SHA256
  `a980c6173ab83ccc2db5ed0ba3f8568eacf767f02912f87ed1919809e8e70bcf`.
- Strict checkpatch, clean package preparation, focused mt76 compile, full
  image build, FIT parse, embedded-module identity, firmware inventory, and
  forbidden-stock-module gates pass. Kernel and DTB payloads are byte-identical
  to V6.15 and V6.16.
- Repeated native image generation varies only in APK signed-package size and
  checksum metadata plus the LuCI script archive identity. Runtime payload
  files, modules, normalized APK records, package manifest, kernel, and DTB are
  identical. The already extracted/audited immutable ITB above is canonical.
- Next gate after COM3 recovery: mode-0 cold boot/scans/reloads/native-L1, then
  mode-3 lifecycle/ring-address checks and a bounded repeated native-L1 loop.
  V6.18 supersedes this candidate for the next hardware gate.

## Latest Offline Stock Token-Fate Closure

- Report: `work\W1700K_STOCK_NPU_TOKEN_FATE_GHIDRA_CLOSURE_20260717.md`,
  SHA256
  `019e75325683e8f4999f8ee590258eba469b5d07417f8aa5e04973cf48a8c242`.
- Ghidra 12.1 auto-analysis is saved for stock `hostadpt.ko`, `mtk_pci.ko`,
  and newly imported `mtk_hwifi.ko` in project `W1700KHostadpt20260704`.
  The unnamed 440-byte `mtk_pci.ko` token routine at `00104ce0` is recovered
  and documented as `npu_inline_token_release_to_fifo`.
- Stock token IDs are registered once and remain stable. Checkout removes the
  free-list head; release appends to the tail; TXFREE lookup requires the
  active-ready bit. There is no inspected generation/epoch comparison.
- Stock NPU handoff releases the Wi-Fi token before transferring the queued
  SKB to `hostadpt`; hostadpt later unmaps/frees the SKB at TX-ring consumer
  reclaim. Token and SKB/DMA lifetimes are intentionally separate.
- The active guarded stock-copy path already preserves the stronger vendor
  safety property: a confirmed firmware copy completes the high host token at
  consumer advance, while later low NPU-local TXFREE IDs cannot touch the host
  IDR. Direct-DMA fallback remains ordinary high-token TXFREE-owned.
- Decision: do not replace mt76's global IDR allocator with FIFO reuse and do
  not early-release direct-path host tokens. The next offline boundary is exact
  hostadpt descriptor publication/doorbell ordering and teardown treatment of
  in-flight copied payloads.

## Latest Offline NPU Hostadpt Ring Contract

- Image/source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_NPU_HOSTADPT_RING_CONTRACT_IMAGE_REPORT_20260706.md`, SHA256 `36aeb0b39db45e6788e4153b3b75716901f798eea0656c6f1193ef8e166b66a8`.
- FinalResult folder: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\NpuHostadptRingContract-20260706`; image `w1700k-npu-hostadpt-ring-contract-20260706-sysupgrade.itb`, SHA256 `d583f12e8262efee5451403227246f94237e6ee51c651d9e355da302e594089b`.
- Result: added target kernel patch `999-59-net-airoha-npu-expose-stock-hostadpt-ring-contract.patch`, SHA256 `6a680c85a6331717f19380cbcbca2e2112077ef46fb03cf82a3af29442129a17`.
- Behavior: extends the read-only Airoha NPU debugfs file `stock_hostadpt_irq_index` with stock-derived hostadpt TX/RX descriptor-depth, stride, index-range, pending/free-space, and enqueue-threshold checks.
- Verification: patch dry-run passed; `make target/linux/clean` passed; clean-PATH full image build passed; FIT parse passed; `vmlinux` string proof found the ring-contract source/policy, descriptor layout, doorbell policy, TX free descriptor, stock enqueue threshold, and RX index-range strings; forbidden stock-module scan found none; artifact `SHA256SUMS.txt` verified clean with SHA256 `4f0b6482df900143469da325b85f6bfd875ba8b73f31f55012c07fe86f4cce43`.
- Boundary: offline-only and not flashed. It does not enable WLAN NPU mode, write TX doorbells, change descriptor ownership, alter NAPI scheduling, mutate packet buffers, or clone stock hostadpt packet ownership.
- Live status: `NpuRroCounterMap-20260706` remains the current live-tested flashed baseline.

## Latest Offline NPU Queue/Aggregation Live Mirror

- Image/source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_NPU_QUEUE_AGG_LIVE_MIRROR_IMAGE_REPORT_20260706.md`, SHA256 `3890402407bda62826c9bebef55149d5c56d0948bed96dcd1fc7aefc8805bbbc`.
- FinalResult folder: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\NpuQueueAggLiveMirror-20260706`; image `w1700k-npu-queue-agg-live-20260706-sysupgrade.itb`, SHA256 `b150b5f527a198213cc8a42fa127b28448999f785c89b557e5d7ef132ecbd845`.
- Result: added mt76 patch `9999o-mt76-add-w1700k-stock-queue-agg-live-mirrors.patch`, SHA256 `d56302f6a837146e48f7c7591b910e56dff08c6c8c0f0e324e010206678c442f`.
- Behavior: adds read-only debugfs files `npu-stock-queue-pressure` and `npu-stock-agg-ba-limits`, mirroring stock mt7990_dbg PSE/PLE queue-pressure passive registers and aggregation/BA limit passive registers.
- Verification: promoted-patch safety scan found no `__mt76_wr`, `mt76_wr`, `0x81b0`, or `0x81b4`; mt76 clean/compile passed; clean-PATH full image build passed; FIT parse passed; `mt76.ko` string proof found the new queue/aggregation files, policy keys, `queue_selector_writes=0`, `packet_mutation=0`, `ba_session_mutation=0`, and `prephy_npu_activation=0`; forbidden stock-module scan found none; artifact `SHA256SUMS.txt` verified clean.
- Boundary: offline-only and not flashed. It does not enable WLAN NPU mode, write queue selectors, mutate packets, change BA sessions, or implement stock-equivalent hostadpt/RRO/TXFREE ownership.
- Live status: `NpuRroCounterMap-20260706` remains the current live-tested flashed baseline.

## Latest Offline NPU RRO MIB Live Mirror

- Image/source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_NPU_RRO_MIB_LIVE_MIRROR_IMAGE_REPORT_20260706.md`, SHA256 `0448a6d6c4536022f6cd652529131916da8410bec92b610a9ddd404ce1a7813f`.
- FinalResult folder: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\NpuRroMibLiveMirror-20260706`; image `w1700k-npu-rro-mib-live-20260706-sysupgrade.itb`, SHA256 `fd8bd702d86ecf7014d385d67263f7997ada789e55580e483ef6d8718a0bc321`.
- Result: added mt76 patch `9999n-mt76-add-w1700k-stock-rro-mib-live-mirror.patch`, SHA256 `b6cdd07bbf1f6b2215fe884f0938a11deb12d235d474e96684fd29c9226660b2`.
- Behavior: adds read-only debugfs file `npu-stock-rro-mib` mirroring the stock mt7990 `rro_mib` register block `0xa180..0xa1ac`, with helper-compatible `stock_rro_mib_*` keys for LuCI `W1700K NPU` RRO rows.
- Verification: mt76 clean/prepare passed; mt76 compile passed; clean-PATH full image build passed; FIT parse passed; `mt76.ko` string proof found `npu-stock-rro-mib`, all `stock_rro_mib_*` keys, `stock_rro_mib_policy=read-only; no rro_dbg selector writes`, `packet_mutation=0`, `rro_ownership_mutation=0`, and `prephy_npu_activation=0`; forbidden stock-module scan found none.
- Boundary: offline-only and not flashed. It does not enable WLAN NPU mode, change packet/RRO/BA ownership, or implement stock-equivalent hostadpt TX rings, SKB/bufid lifecycle, scatter handling, TXFREE/token equivalence, RRO free-pool ownership, ping-pong packet fate, or mode-3 datapath activation.
- Live status: `NpuRroCounterMap-20260706` remains the current live-tested flashed baseline.

## Current Live Wi-Fi/NPU Recovery Baseline

- Live-flashed image: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\NpuRroCounterMap-20260706\w1700k-npu-rro-counter-map-20260706-sysupgrade.itb`, SHA256 `53075481ea48a63344931023b719efe7c0478e879150985277f78bfabb6d58a8`.
- Report and evidence: `work\W1700K_NPU_RRO_COUNTER_MAP_IMAGE_REPORT_20260706.md`, `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\NpuRroCounterMap-20260706\SHA256SUMS.txt`, `file-manifest.csv`, `fit-metadata.txt`, `npu-rro-counter-map-proof.txt`, `forbidden-stock-module-scan.txt`, `9999m-mt76-add-w1700k-npu-rro-counter-map.patch`, `w1700k-offline-npu-rro-map-20260706-build.log`, `postflash-diagnostics-20260706-145139.txt`, `live-radio-service-test-20260706-145409.txt`, `luci-reachability-20260706-145409.txt`, `windows-wifi-scan-20260706-145410.txt`, `live-iwinfo-scan-no-timeout-20260706-145433.txt`, and `temporary-all-radio-ap-test-20260706-145508.txt`.
- Source boundary: source commit `5575e4a97f119f682223a090c4a78c0913f906f5`; 322 experimental stock-port/NPU mt76 patches are disabled under `package\kernel\mt76\patches.disabled-npu-20260706`; active mt76 patches are limited to Wi-Fi/MLO-focused patches plus read-only NPU/MLO diagnostic layers, and now include the scan-pinning `iwinfo` patch plus `9999f-mt7996-keep-mlo-txwi-link-aligned-with-selected-wcid.patch`, `9999g-mt76-add-w1700k-stock-npu-parity-map.patch`, `9999h-mt76-add-w1700k-npu-token-queue-counters.patch`, `9999i-mt7996-add-w1700k-mlo-txwi-link-counters.patch`, `9999j-mt7996-make-mlo-eapol-rewrite-token-safe.patch`, `9999k-mt7996-prefer-high-throughput-mlo-links.patch`, `9999l-mt76-add-w1700k-npu-scatter-counter-map.patch`, `9999m-mt76-add-w1700k-npu-rro-counter-map.patch`, `9999n-mt76-add-w1700k-stock-rro-mib-live-mirror.patch`, and the newest offline-only `9999o-mt76-add-w1700k-stock-queue-agg-live-mirrors.patch`.
- Boot-safety changes: normal images no longer force `CONFIG_MT76_NPU`/`CONFIG_MT7996_NPU`; first boot resets `/etc/modules.d/mt7996e` to `mt7996e` and `/etc/modules.d/20-mt76-core` to `mt76`; the NPU helper refuses nonzero WLAN NPU modes when module parameter strings are absent; helper JSON marks unsupported NPU modes unavailable for LuCI; default firewall hardware flow offload is disabled while packet steering remains enabled.
- Offline verification: mt76 clean/prepare passed; mt76 compile passed; full image build passed; FIT has kernel/FDT/rootfs; package manifest includes LuCI, adblock, SQM, SoftEther, OpenWrt Airoha NPU firmware, `kmod-mt7996e`, and `wpad-mbedtls`; `mt7996e.ko` contains `mlo_tx_policy=prefer-active-non-band0` plus the new `txwi_select_*` counters; existing LuCI radio-status and MLO builder fixes remain in source; `mt76.ko` contains the read-only `w1700k-stock-npu-parity-map` debugfs strings, token/RX-queue counter strings, stock TX/RX hostadpt ring-contract constants, `npu-stock-hostadpt-scatter-counter-map`, and the new `npu-stock-rro-counter-map` zero-mutation/unavailable-counter markers; `vmlinux` contains the Airoha NPU read-only `stock_hostadpt_irq_index` debugfs path and live TX/RX register labels; no stock `hostadpt.ko`, `mt7990*.ko`, stock `npu.ko`, `mtk_wifi*.ko`, or `mtk_pci.ko` modules are staged.
- Live status: flashed and booted on the W1700K over Ethernet-bound SSH. LuCI was reachable, the 5 GHz AP was visible to Windows as `802.11be`, temporary 2.4/5/6 GHz AP creation passed, and the original wireless config was restored after testing.
- Supersedes offline candidates through `NpuScatterCounterMap-20260706` as the current live-tested W1700K baseline for this branch.

## Latest Live NPU RRO Counter-Map

- Image/source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_NPU_RRO_COUNTER_MAP_IMAGE_REPORT_20260706.md`, SHA256 `3f0394cbe05a0b54652ea6e6161997d2cdbeca7c4c70d6f9a03e0fda07c7f457`.
- Result: added mt76 patch `9999m-mt76-add-w1700k-npu-rro-counter-map.patch`, SHA256 `758f6f1cbc2d131400e1e3cd8aff779e12f46df6181b95c2f446423a3f564ece`.
- Behavior: adds read-only debugfs file `npu-stock-rro-counter-map` with stock-derived RRO counter names marked unavailable. It explicitly avoids the older behavior-changing RRO patches that mutate BA/session state or clamp indication processing.
- Verification: mt76 clean/prepare passed; mt76 compile passed; full image build passed; FIT parse passed; `mt76.ko` string proof found the new debugfs file, RRO zero-mutation markers, unavailable stock RRO counters, the scatter map, and the existing parity map; forbidden stock-module scan found none; WiFi recovery invariant gate passed with `failed_count=0`; live flash and radio smoke test passed on the W1700K.
- Boundary: this is documentation and observability only. It does not implement stock-equivalent RRO token ownership, RRO free-pool ownership, BA window/session mutation, RRO reset behavior, RX packet ownership, or pre-PHY NPU activation.
- Live status: live-flashed. Current restored user config has one 5 GHz AP on `radio1` channel 100 `EHT160`; `radio0` and `radio2` are up with no persistent AP interfaces. Temporary smoke test proved `radio0` 2.4 GHz AP, `radio1` 5 GHz `EHT160` AP, and `radio2` 6 GHz `EHT320` AP can all reach `AP-ENABLED`.

## Latest Live NPU Mode Sweep

- Report: `work\W1700K_NPU_MODE_SWEEP_LIVE_REPORT_20260706.md`, SHA256 `4401e5142d6894dd7a54687cdb51b1e132c058c2b42cf44b78ac94214c0a060c`.
- Artifact folder: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\NpuModeSweepLive-20260706`; artifact `SHA256SUMS.txt` SHA256 `5b926f27fef398013bce1d6431229fa3b096c22bc8d2394c4c2aa64f7662ef74`.
- Safe-image helper test: current `NpuRroCounterMap-20260706` image rejects helper-level modes `2`, `3`, and `4` because experimental mt76 WLAN NPU module parameters are absent; mode `1` is unsupported.
- Diagnostic mode `3`: `FailOpenMode3Diagnostic-20260706` booted with `wlan_npu_mode=3`; Wi-Fi came up on 5 GHz `EHT160`; Airoha NPU firmware and mailbox/memory debugfs were visible. Captured NPU queues stayed zeroed and the diagnostic image did not expose the newer mt76 NPU ownership debugfs files.
- Diagnostic mode `2`: forced `mt7996e wlan_npu_mode=2`; dmesg reported `unsupported deferred wlan_npu_mode=2; keeping WLAN NPU disabled`; Wi-Fi came up and NPU queues stayed zeroed.
- Diagnostic mode `4`: forced `mt7996e wlan_npu_mode=4`; dmesg reported `unsupported deferred wlan_npu_mode=4; keeping WLAN NPU disabled`; Wi-Fi came up and NPU queues stayed zeroed.
- Final state was restored to `NpuRroCounterMap-20260706`: plain `mt7996e`, no runtime `wlan_npu_mode`, `npu_active=0`, and preserved `radio1` channel 100 `EHT160` AP.
- Boundary: no association, throughput, MLO, routed traffic, or stress test was run. Mode `3` parameter boot is not stock-equivalent hostadpt/TXFREE/RRO ownership parity; modes `2` and `4` currently fail open to disabled WLAN NPU.

## Latest Offline NPU Scatter Counter-Map

- Image/source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_NPU_SCATTER_COUNTER_MAP_IMAGE_REPORT_20260706.md`, SHA256 `3a49711609656193569029258697d2e6a8ff863744daaae730828b941d16b163`.
- Result: added mt76 patch `9999l-mt76-add-w1700k-npu-scatter-counter-map.patch`, SHA256 `9635a6ab48f0a57a5a27cd0a1a7da63a299d9be33f4cba7263c3fffc155e505d`.
- Behavior: adds read-only debugfs file `npu-stock-hostadpt-scatter-counter-map` with stock-derived scatter/SKB/bufid counter names marked unavailable. It makes the remaining stock parity gaps explicit without changing the datapath.
- Verification: mt76 clean/prepare passed; mt76 compile passed; full image build passed; FIT parse passed; `mt76.ko` string proof found the new debugfs file, zero-mutation markers, unavailable stock scatter/SKB/bufid counters, and the existing parity map; forbidden stock-module scan found none; WiFi recovery invariant gate passed with `failed_count=0`.
- Boundary: this is documentation and observability only. It does not implement stock-equivalent hostadpt packet ownership, scatter lifecycle, SKB/bufid lifecycle, TXFREE/token equivalence, RRO ownership, or pre-PHY NPU activation.
- Live status: no router access was used because the W1700K is disconnected and stored.

## Latest Offline MLO High-Band Policy Fix

- Image/source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_MLO_HIGHBAND_POLICY_IMAGE_REPORT_20260706.md`.
- Result: added mt76 patch `9999k-mt7996-prefer-high-throughput-mlo-links.patch`, SHA256 `92cf67477f2082f3b25fc1f04890f1b283b1efc79af4bc48f83ab4a5c291016e`.
- Behavior: keeps MLO deterministic per TID, but when one or more active non-BAND0 per-link WCIDs exist, normal data selection uses that non-BAND0 subset. On W1700K this avoids pinning ordinary TID 0 MLO traffic to the 2.4 GHz link when 5/6 GHz links are active.
- Verification: mt76 clean/prepare passed; mt76 compile passed; full image build passed; FIT parse passed; `mt7996e.ko` string proof found `mlo_tx_policy=prefer-active-non-band0` and the `txwi_select_*` counters; forbidden stock-module scan found none.
- Boundary: this is a Wi-Fi MLO link-selection fix plus diagnostic counters. It does not implement stock-equivalent hostadpt/TXFREE/RRO behavior or pre-PHY NPU activation.
- Live status: no router access was used because the W1700K is disconnected and stored.

## Latest Offline MLO EAPOL Token-Safe Fix

- Image/source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_MLO_EAPOL_TOKEN_SAFE_IMAGE_REPORT_20260706.md`.
- Result: added mt76 patch `9999j-mt7996-make-mlo-eapol-rewrite-token-safe.patch`, SHA256 `4a9266a39ec4eb62eeed6363e19a01bf9274e9cd03a7f93f52fbde80f147ec71`.
- Behavior: bounds-checks MLO retarget link IDs and changes the local MLO EAPOL address rewrite from post-token `return -EINVAL` on missing per-link state into fail-open rewrite-skip plus normal transmit.
- Verification: patch dry-run passed; mt76 clean/compile passed; full image build passed; FIT parse passed; `mt7996e.ko` string proof found `mlo_eapol_rewrite_policy=fail-open`, `post_token_error_returns=0`, `link_id_bounds_checked=1`, `eapol_missing_link_state_drops=0`, and the new rewrite-skip counters; forbidden stock-module scan found none.
- Boundary: this is a Wi-Fi association reliability fix and diagnostic layer. It does not implement stock-equivalent hostadpt/TXFREE/RRO behavior or pre-PHY NPU activation.
- Live status: no router access was used because the W1700K is disconnected and stored.

## Latest Offline MLO TXWI Link Counters

- Image/source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_MLO_TXWI_LINK_COUNTERS_IMAGE_REPORT_20260706.md`, SHA256 `30c429b6555572720f043d2ebd5ea4ddfa69457d3868f5356b93feb290cffac2`.
- Result: added mt76 patch `9999i-mt7996-add-w1700k-mlo-txwi-link-counters.patch`, SHA256 `69c0e352af729c1c056ccf3f27ea52c804edf038c731694cdf60eff042fa7686`.
- Behavior: adds one read-only mt7996 debugfs file, `w1700k-mlo-txwi-link`, which records MLO data-frame branch selection, WCID-link reuse, priority fallback, explicit control/EAPOL link use, and TXWI WCID retarget outcomes from `mt7996_tx_prepare_skb()`.
- Verification: mt76 clean/compile passed; full image build passed; FIT parse passed; `mt7996e.ko` string proof found the new debugfs file, scope marker, all counter labels, `packet_mutation=0`, and `prephy_npu_activation=0`; forbidden stock-module scan found none; WiFi recovery invariant gate passed with output SHA256 `066746f0b3d2c0ba86a19825f29dd4666a7b9e69b182858cfcf63f6498b335a8`.
- Boundary: this improves runtime visibility only. It does not change link selection, packet ownership, skb metadata, DMA ownership, TXFREE parsing, RRO ownership, queue selection, or pre-PHY NPU activation.
- Live status: no router access was used because the W1700K is disconnected and stored.

## Latest Offline NPU Token/Queue Counters

- Image/source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_NPU_TOKEN_QUEUE_COUNTERS_IMAGE_REPORT_20260706.md`, SHA256 `d1004d45fcd3ba082629458dc2a6ea89d2a83e4e24df9903491a2dc69a81db67`.
- Result: added mt76 patch `9999h-mt76-add-w1700k-npu-token-queue-counters.patch`, SHA256 `2d1c5ae9a7d3d2274129c682102bbb12223a242ef551f3e2e4e08d1ca977dbf9`.
- Behavior: extends the existing read-only `w1700k-stock-npu-parity-map` debugfs output with compact counters for current mt76 token allocation/release and RX queue polling paths. It changes the status marker to `map-plus-readonly-counters` and reports `live_counter_scope=current mt76 token/RX-queue path only`.
- Verification: mt76 clean/compile passed; full image build passed; FIT parse passed; `mt76.ko` string proof found the counter strings plus `packet_mutation=0` and `prephy_npu_activation=0`; forbidden stock-module scan found none.
- Boundary: this improves runtime visibility only. It does not claim stock-equivalent hostadpt ownership, TX ring lifecycle, TXFREE token release, scatter/SKB/bufid lifecycle, or RRO free-pool behavior.
- Live status: no router access was used because the W1700K is disconnected and stored.

## Latest Offline NPU Parity Map

- Image/source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_NPU_PARITY_MAP_IMAGE_REPORT_20260706.md`.
- Result: added mt76 patch `9999g-mt76-add-w1700k-stock-npu-parity-map.patch`, SHA256 `95ebfdbfd04acb7e2a3da74ff128db9149be8f2dac27ce66368ea881a43b9f35`.
- Behavior: adds one read-only debugfs file, `w1700k-stock-npu-parity-map`, that documents stock hostadpt/TXFREE/RRO contracts as observed but not ported. It is intentionally map-only: `packet_mutation=0`, `skb_cb_mutation=0`, `dma_ownership_mutation=0`, `tx_ownership_mutation=0`, `rro_ownership_mutation=0`, and `prephy_npu_activation=0`.
- Verification: mt76 clean/compile passed; full image build passed; FIT parse passed; `mt76.ko` string proof found the parity-map path, zero-mutation markers, MLO WCID/TXWI alignment marker, and unported stock contract markers; forbidden stock-module scan found none.
- Boundary: this improves traceability and runtime visibility only. It does not claim stock-equivalent hostadpt ownership, TX ring lifecycle, TXFREE token release, scatter/SKB/bufid lifecycle, or RRO free-pool behavior.
- Live status: no router access was used because the W1700K is disconnected and stored.

## Latest Offline MLO TX Alignment Fix

- Image/source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_MLO_WCID_TXWI_ALIGN_IMAGE_REPORT_20260706.md`.
- Result: added mt76 patch `9999f-mt7996-keep-mlo-txwi-link-aligned-with-selected-wcid.patch`, SHA256 `9e589338e4eea5facba671add30623cd1185fa6056d630b6c743b52f79f3beaf`.
- Static finding: scheduled TX already selects a per-link MLO WCID from `txq->tid` before phy/queue selection, but `mt7996_tx_prepare_skb()` recomputed the TXWI link from `skb->priority`. For 802.3/offload frames that can make DMA/NPU queue/radio selection disagree with the descriptor link.
- Fix behavior: normal MLO data now keeps the TXWI link aligned to the already-selected per-link station WCID when valid; the previous `skb->priority` selector remains as fallback.
- Verification: mt76 clean/compile passed; full image build passed; FIT parse passed; forbidden stock-module scan was empty.
- Boundary: no live router access was used because the W1700K is disconnected and stored.

## Latest Offline MLO Discovery Hardening Fix

- Image/source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_MLO_RNR_SAEPWE_HARDENING_IMAGE_REPORT_20260706.md`, SHA256 `9c5410e6a85c3382b31b0954ffffdb6e7903f53342590d2245a812b491e01759`.
- Result: patched LuCI, first-boot radio sanity, and apply-time backend validation so W1700K MLO/6GHz AP configs are discovery-safe by default: `rnr=1`, PMF required, WPA3/OWE-compatible security, and SAE `sae_pwe=2` where SAE is used.
- Verification: Windows `node --check` passed for `wireless.js`; `sh -n` passed for `w1700k-wireless-validate` and `98-w1700k-radio-sanity`; `make package/feeds/luci/luci-mod-network/compile V=s -j1` passed; full clean-PATH image build passed; FIT parse passed; staged rootfs proof contains the LuCI/backend/sanity strings; forbidden stock-module scan is empty.
- Boundary: no live router access was used because the W1700K is disconnected and stored.

## Latest Offline LuCI MLO Source Fix

- Source-only report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_LUCI_MLO_DROPDOWN_HARDENING_SOURCE_20260706.md`, SHA256 `f1ea7a9d5232492d7fa82cb01736f4ad559907d2201f4401b2da6130baf66699`
- Image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_LUCI_MLO_DROPDOWN_HARDENING_IMAGE_REPORT_20260706.md`, SHA256 `ec5e72216acb361ad5425790eb881562d7e94425c993f570c053b2b7de1214f4`
- Result: patched `feeds/luci/modules/luci-mod-network/htdocs/luci-static/resources/view/network/wireless.js` so the MLO radio selector normalizes selected devices into a de-duplicated array, keeps the current radio pinned, pushes the normalized value back into the live LuCI dropdown, always writes list-valued `device` while MLO is active, and unsets stale `mlo` when the selector is removed.
- Verification: Windows `node --check` passed for `wireless.js`; `sh -n` passed for `w1700k-wireless-validate` and `98-w1700k-radio-sanity`; `make package/feeds/luci/luci-mod-network/compile V=s -j1` passed; the WiFi recovery invariant checker now covers the MLO list-normalization path and passed; the pre-PHY NPU boundary check passed.
- Boundary: source fix is now included in offline candidate `LuciMloDropdownHardening-20260706`.
- Live status: no router flash, SSH command, serial command, browser test, wireless scan, client association, MLO association, throughput test, or NPU runtime test happened.

## Current Live Wi-Fi Recovery Baseline

- Live-tested recovery image: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\NoNPU-Diagnostic-20260614\w1700k-no-mt76-npu-diagnostic-sysupgrade.itb`, SHA256 `1b529f7d15faac0108ab5c1b5d208a43c4b815747627c91023cfa3dc7fb34018`
- Live transport note: use Ethernet IPv6 link-local `fe80::e458:9ff:fe33:39a7%11`; IPv4 `192.168.1.1` is ambiguous because another router is present on Wi-Fi.
- Recovery result: `mt7996e` probes successfully, all three radios report `up: true`, and the current single AP is `radio1` channel 100 / EHT160.
- Broken boundary: `HostadptScatterSkbLifecycle-20260705` and `TokenShadowTrace-20260705` both failed mt7996 firmware initialization before PHY creation. Treat later mt76/NPU patch-train images as Wi-Fi-untrusted until rebuilt and live-verified.
- This is a Wi-Fi recovery baseline only; it is not stock hostadpt/NPU parity proof.

## Latest Offline NPU Source Boundary

- Offline NPU/Wi-Fi audit after radio-status build: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_OFFLINE_NPU_WIFI_AUDIT_20260706.md`, SHA256 `a38f40ede071301753f394126b536b7556ba15e7b5a287571d6f5648f858bb6d`
- Hostadpt TX token-fate offline check: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_NPU_HOSTADPT_TX_TOKEN_FATE_OFFLINE_20260706.md`, SHA256 `419ac2549463b49855366c7f5fb009df293d89435a68312232b245cccfe2bc0a`
- Result: no new NPU datapath patch was justified. Ghidra/source evidence still says stock hostadpt is a packet-owning 0x400-entry/0xd0-byte TX ring endpoint that frees SKBs after NPU CPU-index advancement, while the current recovery image intentionally keeps stock hostadpt/TXFREE/RRO behavior as read-only diagnostics. Next NPU step remains live/stress evidence after flashing the current offline candidate.
- Patch21 hostadpt scatter counter-map source check: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_PATCH21_HOSTADPT_SCATTER_COUNTER_MAP_SOURCE_20260706.md`, SHA256 `572f427023ada4778ca5b26fe96cea113591289cdc020955a9de48b11fdbe922`
- Result: source-only patch `work\9999zzzzzzzzzzzz21-mt76-npu-add-stock-hostadpt-scatter-counter-map.patch`, SHA256 `e4142cfbd139b3744db2412614d8eee5c28aa949075383570d89c530c4b8e228`, compile-checks against the current recovery branch. It adds only a read-only `npu-stock-hostadpt-scatter-counter-map` debugfs file that reports stock hostadpt scatter/SKB/bufid counter names as `unavailable`.
- Boundary: Patch21 was removed after compile testing; normal mt76 clean/compile passed, active normal mt76 patch count returned to 9, `npu-stock-hostadpt-scatter-counter-map` is absent from restored `mt76.ko`, and both pre-PHY and WiFi recovery invariant checks passed. Treat Patch21 as a future diagnostic helper, not stock parity.
- Minimal passive hostadpt scatter counter extraction map: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_MINIMAL_PASSIVE_HOSTADPT_SCATTER_COUNTER_EXTRACTION_MAP_20260706.md`, SHA256 `c9c43219c334a96de576e425fcaebc9a76bccfb96455daa2f5034d466168e080`
- Result: source-only mapping pass. The current recovery branch has compact mt76 debugfs/NPU source and no active `struct mt76_npu_stats`; old scatter/SKB/bufid counters were mapped from 14 disabled patches, then classified into passive labels versus packet-mutating or ownership-mutating behavior.
- Decision: do not import the old counters wholesale and do not revive the broad disabled NPU patch train. The next safe implementation step is a tiny read-only current-boundary debugfs map that reports exact stock counter names as `unavailable` unless a current safe increment site exists; packet mutation, `skb->cb` mutation, buffer reuse, direct sideband writes, and TX ownership changes stay out of normal WiFi recovery images.
- Patch20 hostadpt scatter/SKB contract source check: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_PATCH20_HOSTADPT_SCATTER_CONTRACT_SOURCE_20260706.md`, SHA256 `19c815777a831f81ba42ef8ca638dd3750053ecbd8a12bca45441587a7ffbaaa`
- Result: source-only candidate patch `work\9999zzzzzzzzzzzz20-mt76-npu-add-current-boundary-hostadpt-scatter-contract.patch`, SHA256 `4f43cbc4ff1c72a97a710e2de1df7517e4002bc8ada8809de7ec571b9375691e`, compile-checks against the current recovery branch. It adds only a read-only debugfs contract marker, not a packet mutation or NPU ownership change.
- Boundary: patch20 was removed after compile testing; active normal mt76 patch count returned to 9 and both pre-PHY and WiFi recovery invariants passed. Treat patch20 as a future diagnostic helper, not as stock parity.
- Patch19 current-boundary probe: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_PATCH19_CURRENT_BOUNDARY_PROBE_20260706.md`, SHA256 `da6b78f41e6c6a50ab4b0d6caf77f4e9b791d79efaa9a1fa34e47b6be4550aa2`
- Result: the old `9999zzzzzzzzzzzz19-mt76-npu-add-stock-hostadpt-scatter-skb-lifecycle.patch` does not apply to the current WiFi recovery boundary. It expects the older broad stock-port debugfs/NPU stats surface; the current recovery line has a compact mt76 debugfs surface and intentionally keeps that old NPU patch train disabled.
- Decision: do not promote patch19 as-is. The passive hostadpt scatter/SKB/bufid counter extraction map above is now the source of truth for the next implementation step.
- Experimental deferred WLAN-NPU fail-open source check: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_EXPERIMENTAL_DEFERRED_NPU_FAILOPEN_SOURCE_20260706.md`, SHA256 `5ce6412f9427e8a662db9e4035eac43d2d09e32a0e8c0af35259cf0bdbc00e53`
- Result: compile-tested source scaffold only. It keeps `mt76_npu_init()` out of pre-PHY probe flow, adds fail-open behavior for deferred activation and deferred hardware-init failure, and restores the normal image line afterward.
- Active normal source boundary after restore: active mt76 patch count is 9; `903-mt7996-add-post-firmware-wlan-npu-activation.patch` is absent; pre-PHY NPU boundary and WiFi recovery invariant checks passed.
- Boundary: no sysupgrade image, no live router test, and no claim of stock-equivalent hostadpt/TXFREE/RRO parity.

## Latest Offline NPU Diagnostic Image

- Experimental mode-3 diagnostic image: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\FailOpenMode3Diagnostic-20260706\w1700k-failopen-mode3-diagnostic-20260706-sysupgrade.itb`, SHA256 `3d5dd35ad8b872f83ce50b337315e8ffbdc712f9a935b10009abf0add5f448a8`.
- Report and evidence: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\FailOpenMode3Diagnostic-20260706\BUILD_REPORT.md`, `SHA256SUMS.txt`, `FILE_MANIFEST.txt`, `fit-metadata.txt`, `mt7996e-strings-check.txt`, `mt76-strings-check.txt`, `stock-binary-scan.txt`, `prephy-boundary-check-after-mode3-normal-restore.txt`, and `wifi-recovery-invariant-check-after-mode3-normal-restore.txt`.
- Build behavior: temporarily activated `903-mt7996-add-post-firmware-wlan-npu-activation.patch` and built with `W1700K_EXPERIMENTAL_MT76_NPU=1 W1700K_EXPERIMENTAL_MT76_NPU_MODE3=1`; final diagnostic rootfs autoload is exactly `mt7996e wlan_npu_mode=3`.
- Verification: diagnostic full build passed; FIT parse passed; module string checks found `wlan_npu_mode` and NPU symbols; rootfs scan found no staged stock/vendor WiFi/NPU modules.
- Restore boundary: after copying the image, active `903` was removed, mt76 Makefile was restored, normal mt76 clean/compile passed, normal full build regenerated staging, and both pre-PHY and WiFi recovery invariant checks passed with plain `mt7996e` autoload.
- Boundary: this is an experimental NPU diagnostic image, not the current offline WiFi recovery candidate and not a live-tested baseline. No router access was used because the W1700K is disconnected and stored.

## Canonical Files

- NPU ring-contract RX-label image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_NPU_RING_CONTRACT_RXLABEL_IMAGE_REPORT_20260706.md`, SHA256 `838c63b7a48ac0838cbe690ce09a82920c5c58857010950dc2392af2d4183ef0`
- NPU token/queue counters image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_NPU_TOKEN_QUEUE_COUNTERS_IMAGE_REPORT_20260706.md`, SHA256 `d1004d45fcd3ba082629458dc2a6ea89d2a83e4e24df9903491a2dc69a81db67`
- NPU parity-map image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_NPU_PARITY_MAP_IMAGE_REPORT_20260706.md`, SHA256 `d431650f8fd2e007617106beec3e00da89b621dbf82589164050b79266567868`
- MLO RNR/SAE-PWE hardening image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_MLO_RNR_SAEPWE_HARDENING_IMAGE_REPORT_20260706.md`, SHA256 `9c5410e6a85c3382b31b0954ffffdb6e7903f53342590d2245a812b491e01759`
- WiFi recovery invariant checker: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\w1700k_wifi_recovery_invariant_check_20260706.ps1`, SHA256 `5cd4b1661ef646367fbb9888d773414b8822fede881e185ece129d69d0e8b078`
- Patch21 hostadpt scatter counter-map source check: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_PATCH21_HOSTADPT_SCATTER_COUNTER_MAP_SOURCE_20260706.md`, SHA256 `572f427023ada4778ca5b26fe96cea113591289cdc020955a9de48b11fdbe922`
- Patch21 source-only counter-map patch: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\9999zzzzzzzzzzzz21-mt76-npu-add-stock-hostadpt-scatter-counter-map.patch`, SHA256 `e4142cfbd139b3744db2412614d8eee5c28aa949075383570d89c530c4b8e228`
- Minimal passive hostadpt scatter counter extraction map: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_MINIMAL_PASSIVE_HOSTADPT_SCATTER_COUNTER_EXTRACTION_MAP_20260706.md`, SHA256 `c9c43219c334a96de576e425fcaebc9a76bccfb96455daa2f5034d466168e080`
- Patch20 hostadpt scatter/SKB contract source check: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_PATCH20_HOSTADPT_SCATTER_CONTRACT_SOURCE_20260706.md`, SHA256 `19c815777a831f81ba42ef8ca638dd3750053ecbd8a12bca45441587a7ffbaaa`
- Patch20 source-only contract patch: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\9999zzzzzzzzzzzz20-mt76-npu-add-current-boundary-hostadpt-scatter-contract.patch`, SHA256 `4f43cbc4ff1c72a97a710e2de1df7517e4002bc8ada8809de7ec571b9375691e`
- Patch19 current-boundary probe: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_PATCH19_CURRENT_BOUNDARY_PROBE_20260706.md`, SHA256 `da6b78f41e6c6a50ab4b0d6caf77f4e9b791d79efaa9a1fa34e47b6be4550aa2`
- Experimental mode-3 NPU diagnostic image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_FAILOPEN_MODE3_DIAGNOSTIC_IMAGE_REPORT_20260706.md`, SHA256 `825bcb4f04a5a0139635cacb5f4dc4220c5bfd07cf175d576103b011fd941407`
- Experimental deferred WLAN-NPU fail-open source check: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_EXPERIMENTAL_DEFERRED_NPU_FAILOPEN_SOURCE_20260706.md`, SHA256 `5ce6412f9427e8a662db9e4035eac43d2d09e32a0e8c0af35259cf0bdbc00e53`
- WiFi recovery MLO form-sync image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_WIFI_RECOVERY_MLO_FORM_SYNC_IMAGE_REPORT_20260706.md`, SHA256 `7f25078f1c677184d7d2cd92c45f1bde6de8a294509e0a8e338f0c61cc9484d2`
- WiFi recovery invariant gate: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_WIFI_RECOVERY_INVARIANT_GATE_20260706.md`, SHA256 `424cdc5c18e6104cce6aef223f697eed7474da41aeddeae99a26a99b3c87f60b`
- LuCI MLO dropdown hardening source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_LUCI_MLO_DROPDOWN_HARDENING_SOURCE_20260706.md`, SHA256 `f1ea7a9d5232492d7fa82cb01736f4ad559907d2201f4401b2da6130baf66699`
- LuCI MLO dropdown hardening image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_LUCI_MLO_DROPDOWN_HARDENING_IMAGE_REPORT_20260706.md`, SHA256 `ec5e72216acb361ad5425790eb881562d7e94425c993f570c053b2b7de1214f4`
- Disabled NPU patch re-entry map: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_DISABLED_NPU_PATCH_REENTRY_MAP_20260706.md`, SHA256 `c057a4134349f3174e95b7ce65bb63ba1ccc3156b11d929f31bce69d868eed58`
- Disabled NPU patch classifier script: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\w1700k_classify_disabled_npu_patches_20260706.ps1`, SHA256 `61fd65ba9509393ae6ce07d998dbaa9b0b81b20e4e46bbe059e13d7ffabae22e`
- RRO/BA re-entry stack check: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_RRO_BA_REENTRY_STACK_CHECK_20260706.md`, SHA256 `3b2c388d9e3b9bc9beb4c633c1d3084e6274a0102aa80f9fac18b2d59810ca90`
- NPU reverse-engineering roadmap and ETA: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_NPU_REVERSE_ENGINEERING_ROADMAP_ETA_20260705.md`, SHA256 `5961CAC503A2E1DAB2EB06899A0623005BBF1BFE8AC5E3AB0E94CD3E5912F865`
- Latest source-compiled stock hostadpt scatter/SKB lifecycle report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_SCATTER_SKB_LIFECYCLE_SOURCE_20260705.md`, SHA256 `80F7876BA9C603708652009F3D9C1845B0399F77133F2DBAE6FEE1986C385FB2`
- Latest stock hostadpt scatter/SKB lifecycle image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_SCATTER_SKB_LIFECYCLE_IMAGE_REPORT_20260705.md`, SHA256 `BBC19F84884B909B894DBE96F0145E71D57F1D36086623E8F3ED78929B129BC5`
- Latest stock hostadpt scatter/SKB lifecycle live harness report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_HOSTADPT_SCATTER_SKB_LIFECYCLE_LIVE_HARNESS_20260705.md`, SHA256 `0E62A185BADDFB0967FA242CC410C9D2E90B11D4501E8DE84AD0957940C2AB7B`
- Target-collision correction: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_TARGET_COLLISION_CORRECTION_20260705.md`, SHA256 `13F989558E919BD60F1D4F07032740E6E6F8372E8564363304026289144259D3`
- Static stock updater audit: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STATIC_STOCK_UPDATER_AUDIT_20260705.md`, SHA256 `ABEF5D4C67318962BEBEB8EFB55BA797BC39B82120C6B5BFBAE06C847C158D55`
- Post-target-correction rebuild report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_POST_TARGET_CORRECTION_REBUILD_20260705.md`
- Stock TX queue offline coverage: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXQUEUE_OFFLINE_COVERAGE_20260705.md`, SHA256 `32BCC39D9E81772FC5C45511E075EBA8E5DD59D2BF00ECA38B73043537AACC69`
- Stock TX queue source-gate aliases: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXQUEUE_SOURCE_GATE_ALIASES_20260705.md`, SHA256 `A7EF3059A6D5EF6ECCC1708B05ECBA5B17F0E5ABC932750C3D7806F4EBDDDA2D`
- Stock TX queue gate classifier: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXQUEUE_GATE_CLASSIFIER_20260705.md`, SHA256 `AAC2A53DD684EACD88B378CA355C00704490F915B064074077E82D51DC3CEBE7`
- Stock TX queue gate classifier image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXQUEUE_GATE_CLASSIFIER_IMAGE_REPORT_20260705.md`, SHA256 `7C78E4EE673E6D748810E54D979081DC1701E3A6801B940DF270F3CE94F7B260`
- Stock token/freelist coverage source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TOKEN_FREELIST_COVERAGE_SOURCE_20260705.md`
- Stock token entry shadow source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TOKEN_ENTRY_SHADOW_SOURCE_20260705.md`, SHA256 `8EEC878F8B59A9D14C897C839189235CDF54F58520C4A8156019F2B8E65FA361`
- Stock token entry shadow image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TOKEN_ENTRY_SHADOW_IMAGE_REPORT_20260705.md`, SHA256 `B8CCC047DE3C7310CAAC3F0656DD9BE08D800EE2762EC32B2EED5E909CC9F45D`
- Stock token/freelist coverage image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TOKEN_FREELIST_COVERAGE_IMAGE_REPORT_20260705.md`, SHA256 `15D981C08EFBD913494430CAB8559B44C54A05606E0F8AF1DBD75E3C260E1064`
- Stock bridge/bus/MT7990 offline coverage: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_BRIDGE_BUS_OFFLINE_COVERAGE_20260705.md`, SHA256 `ac4c32a415fe11985ed9caa5625ab26d78f69d4630b213d48f65f7ff8ea73aea`
- Latest stock HTTPS surface probe: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HTTPS_SURFACE_PROBE_20260705.md`
- Latest hostadpt hook arg-length verifier image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_ARG_LEN_VERIFIER_20260705.md`
- Latest NPU LuCI snapshot export image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_NPU_LUCI_SNAPSHOT_EXPORT_IMAGE_REPORT_20260705.md`
- Latest stock hostadpt lifecycle image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_LIFECYCLE_IMAGE_REPORT_20260705.md`
- Previous stock token layout map image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TOKEN_LAYOUT_MAP_IMAGE_REPORT_20260705.md`
- Current dated logging session: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PORT_LOGGING_SESSION_20260630.md`
- Current TX path paper plan: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TX_PATH_PARITY_PAPER_PLAN_20260701.md`
- Current TX verifier implementation spec: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TX_VERIFIER_IMPLEMENTATION_SPEC_20260701.md`
- Current Patch 3+ TX verifier/test roadmap: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TX_VERIFIER_PATCH3_TEST_ROADMAP_20260701.md`
- Current remaining stock-port paper closure from item 3: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_REMAINING_WORK_FROM_3_PAPER_CLOSURE_20260701.md`
- Current remaining stock-port paper roadmap from item 3: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_REMAINING_WORK_FROM_3_PAPER_ROADMAP_20260701.md`
- Current Patch 6/test roadmap: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PATCH6_TEST_ROADMAP_20260701.md`
- Latest TX parity verdict helper/LuCI source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TX_PARITY_VERDICT_REPORT_20260703.md`
- Latest Patch 1-6 verifier image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TX_PARITY_VERIFIER_IMAGE_REPORT_20260703.md`
- Latest RRO/BA verdict image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RRO_BA_VERDICT_IMAGE_REPORT_20260703.md`
- Latest RRO reset guard image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RRO_RESET_GUARD_IMAGE_REPORT_20260703.md`
- Latest MLO BA-link verifier image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_MLO_BA_LINK_VERIFIER_IMAGE_REPORT_20260703.md`
- Latest RRO free-pool live watermark source/module report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RRO_FREEPOOL_LIVE_WATERMARK_REPORT_20260703.md`
- Latest RRO free-pool live watermark image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RRO_FREEPOOL_LIVE_WATERMARK_IMAGE_REPORT_20260703.md`
- Latest RRO free-pool LuCI/helper image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RRO_FREEPOOL_LUCI_IMAGE_REPORT_20260704.md`
- Latest RRO free-pool verdict gate image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RRO_FREEPOOL_VERDICT_GATE_IMAGE_REPORT_20260704.md`
- Latest RRO free-pool hit classification image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RRO_FREEPOOL_HIT_IMAGE_REPORT_20260704.md`
- Latest stock mtk_pci provider parity refresh: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_MTKPCI_PROVIDER_PARITY_REFRESH_20260704.md`
- Latest source-staged stock mtk_pci provider contract patch report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_MTKPCI_PROVIDER_CONTRACT_PATCH_STAGED_20260704.md`
- Latest source-staged stock token/freelist contract patch report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TOKEN_FREELIST_CONTRACT_PATCH_STAGED_20260704.md`
- Latest stock mailbox provider visibility image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_MAILBOX_PROVIDER_IMAGE_REPORT_20260704.md`
- Latest stock hostadpt/NPU provider Ghidra refresh: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_NPU_PROVIDER_REFRESH_20260704.md`
- Latest stock runtime parity gate image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RUNTIME_PARITY_GATE_IMAGE_REPORT_20260704.md`
- Latest stock trans-slot clean-root image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TRANS_SLOT_CLEANROOT_IMAGE_REPORT_20260704.md`
- Latest stock hostadpt TX queue + RRO MIB build report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_TXQUEUE_RROMIB_IMAGE_REPORT_20260704.md`
- Latest non-promoted hostadpt TX queue surface report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_TXQUEUE_SURFACE_STAGED_20260704.md`
- Latest non-promoted hostadpt TX queue anchor analysis: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_TXQUEUE_ANCHOR_ANALYSIS_20260704.md`
- Latest focused stock TX queue Ghidra report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXQUEUE_FOCUSED_GHIDRA_REPORT_20260704.md`
- Latest stock TX queue source gate spec: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXQUEUE_SOURCE_GATE_SPEC_20260704.md`
- Latest stock TX queue source-gate alias source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXQUEUE_SOURCE_GATE_ALIASES_20260705.md`
- Latest stock TX queue gate-classifier source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXQUEUE_GATE_CLASSIFIER_20260705.md`
- Latest stock full decompile export report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_FULL_DECOMPILE_EXPORT_20260704.md`
- Latest stock bridge/bus/MT7990 anchor report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_BRIDGE_BUS_MT7990_ANCHOR_REPORT_20260704.md`
- Previous stock trans-slot runtime gate image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TRANS_SLOT_RUNTIME_GATE_IMAGE_REPORT_20260704.md`
- Latest TX shape guard source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TX_SHAPE_GUARD_REPORT_20260701.md`
- Latest TX doorbell/verifier gate source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TX_DOORBELL_GATE_VERIFIER_REPORT_20260701.md`
- Latest TX equivalence verifier source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TX_EQUIV_VERIFIER_REPORT_20260701.md`
- Latest TX descriptor byte verifier source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TX_DESC_BYTE_VERIFIER_REPORT_20260701.md`
- Latest TX state-machine verifier source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TX_STATE_MACHINE_VERIFIER_REPORT_20260701.md`
- Previous dated logging session: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PORT_LOGGING_SESSION_20260629.md`
- Future-reference tracker: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PORT_FUTURE_REFERENCE.md`
- Canonical comparison and future-reference file: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PORT_CANONICAL_COMPARISON.md`
- Previous full dated logging session: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PORT_LOGGING_SESSION_20260625.md`
- Stock-port ledger: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PORT_LEDGER.md`
- Patch inventory: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PORT_PATCH_INVENTORY.tsv`
- Audit log: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PORT_AUDIT_LOG.md`
- Progress tracker: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PORT_TRACKER.md`
- Latest hostadpt CB layout proof report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_CB_LAYOUT_PROOF_REPORT_20260626.md`
- Latest hostadpt local8 decode report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_LOCAL8_DECODE_REPORT_20260626.md`
- Latest hostadpt local8/status correlation report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_LOCAL8_CORRELATION_REPORT_20260627.md`
- Latest hostadpt type-5 bus-fate report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_BUS_FATE_REPORT_20260627.md`
- Latest hostadpt type-5 RX fate enforcement report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RX_FATE_ENFORCE_REPORT_20260628.md`
- Latest hostadpt registration/scheduler analysis report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_REGISTRATION_SCHEDULER_REPORT_20260628.md`
- Latest hostadpt scheduler contract report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_SCHEDULER_CONTRACT_REPORT_20260628.md`
- Latest hostadpt scheduler fail-closed source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_SCHED_BLOCK_REPORT_20260629.md`
- Latest hostadpt scheduler fail-closed image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_SCHED_BLOCK_IMAGE_REPORT_20260629.md`
- Latest hostadpt RX IRQ poll-owner source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_IRQ_OWNER_REPORT_20260629.md`
- Latest hostadpt RX IRQ poll-owner image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_IRQ_OWNER_IMAGE_REPORT_20260629.md`
- Latest hostadpt RX IRQ poll-owner monitor image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_POLL_OWNER_MONITOR_REPORT_20260629.md`
- Latest hostadpt rxinfo hook report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_RXINFO_HOOK_REPORT_20260628.md`
- Latest hostadpt nonlinear RX check report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_NONLINEAR_RXCHECK_REPORT_20260628.md`
- Latest hostadpt hook-bit25 NULL-callback report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_HOOK25_NULL_REPORT_20260628.md`
- Latest hostadpt local24 repack report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_LOCAL24_REPACK_REPORT_20260628.md`
- Latest hostadpt scatter buffer reuse report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_SCATTER_REUSE_REPORT_20260628.md`
- Latest hostadpt incomplete scatter recycle report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_INCOMPLETE_SCATTER_RECYCLE_REPORT_20260628.md`
- Latest hostadpt scatter failure sample report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_SCATTER_FAIL_SAMPLES_REPORT_20260629.md`
- Latest hostadpt scatter first-info image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_SCATTER_FIRST_INFO_REPORT_20260629.md`
- Latest hostadpt type-5 bus-fate auto-arm report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TYPE5_AUTO_FATE_REPORT_20260629.md`
- Latest hostadpt type-5 LuCI/control-surface report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_TYPE5_LUCI_CONTROLS_REPORT_20260629.md`
- Latest ping-pong DstPort handoff report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_DSTPORT_HANDOFF_REPORT_20260628.md`
- Latest ping-pong VirIfIdx classifier report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_VIRIF_CLASSIFIER_REPORT_20260628.md`
- Latest ping-pong branch-fate report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_BRANCH_FATE_REPORT_20260628.md`
- Latest ping-pong rxhandler return report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_RXHANDLER_RETURN_REPORT_20260628.md`
- Latest ping-pong return-gated handoff report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_RETURNGATE_REPORT_20260628.md`
- Latest ping-pong bridge gap report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_BRIDGE_GAP_REPORT_20260628.md`
- Latest ping-pong bridge handoff report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_BRIDGE_HANDOFF_REPORT_20260628.md`
- Latest ping-pong left-to-right gate report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_LTR_GATE_REPORT_20260628.md`
- Latest ping-pong left-to-right mode-2 report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_LTR_MODE2_REPORT_20260628.md`
- Latest ping-pong mode-2 sk_buff layout report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_MODE2_SKB_LAYOUT_REPORT_20260628.md`
- Latest ping-pong mode-2 dst-output contract report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_MODE2_DST_OUTPUT_REPORT_20260628.md`
- Latest ping-pong mode-2 dst-output handoff report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_MODE2_DST_OUTPUT_HANDOFF_REPORT_20260628.md`
- Latest ping-pong mode-2 source-port-0 netif-rx report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_MODE2_SRC0_NETIF_RX_REPORT_20260629.md`
- Latest ping-pong mode-2 source-port-0 original netif-rx source checkpoint report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_MODE2_SRC0_ORIGINAL_NETIF_RX_REPORT_20260629.md`
- Latest ping-pong mode-2 source-port-0 original netif-rx image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_MODE2_SRC0_ORIGINAL_NETIF_RX_IMAGE_REPORT_20260629.md`
- Latest ping-pong GET_HIR gate image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_GETHIR_GATE_REPORT_20260629.md`
- Latest stock GET_HIR provider recovery report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_GETHIR_PROVIDER_REPORT_20260629.md`
- Latest stock GET_HIR modeled identity source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_GETHIR_MODEL_REPORT_20260629.md`
- Latest stock GET_HIR live SCU source report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_GETHIR_LIVE_SCU_REPORT_20260629.md`
- Latest ACK-SN control helper/rootfs report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_ACKSN_CONTROL_REPORT_20260629.md`
- Latest hostadpt TX descriptor publish report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_TXDESC_PUBLISH_REPORT_20260626.md`
- Latest hostadpt TX descriptor reclaim report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_TXDESC_RECLAIM_REPORT_20260626.md`
- Latest TXFREE parse-shape report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXFREE_PARSE_SHAPE_REPORT_20260626.md`
- Latest TXFREE legacy report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXFREE_LEGACY_REPORT_20260626.md`
- Latest fromHostadpt delivery-boundary report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_FROMHOSTADPT_BOUNDARY_REPORT_20260626.md`
- Latest fromHostadpt provider audit: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_FROMHOSTADPT_PROVIDER_AUDIT_20260630.md`
- Latest hostadpt type-5 RX status projection report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TYPE5_STATUS_PROJECT_REPORT_20260630.md`
- Latest hostadpt type-5 802.3 predecode projection report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TYPE5_8023_PREDECODE_REPORT_20260630.md`
- Latest hostadpt RXINFO bit21 rewrite report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RXINFO_BIT21_REPORT_20260630.md`
- Latest hostadpt type-5 sideband length proof report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TYPE5_SIDEBAND_LEN_REPORT_20260630.md`
- Latest hostadpt scatter copy clamp report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_SCATTER_COPY_CLAMP_REPORT_20260630.md`
- Latest hostadpt type-5 status auto-arm report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TYPE5_STATUS_AUTO_REPORT_20260630.md`
- Latest hostadpt type-5 sideband direct-write report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TYPE5_SIDEBAND_DIRECT_REPORT_20260630.md`
- Latest hostadpt type-5 sideband preclear report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TYPE5_SIDEBAND_PRECLEAR_REPORT_20260630.md`
- Latest hostadpt type-5 sideband helper/LuCI controls report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TYPE5_SIDEBAND_CONTROLS_REPORT_20260630.md`
- Latest hostadpt scheduler trans-slot gate report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TRANS_SLOT_SCHED_GATE_REPORT_20260630.md`
- Latest hostadpt scheduler trans-slot LuCI controls report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TRANS_SLOT_LUCI_REPORT_20260630.md`
- Latest ping-pong helper/LuCI controls report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_LUCI_REPORT_20260630.md`
- Latest ping-pong helper/LuCI visibility report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PINGPONG_VISIBLE_REPORT_20260630.md`
- Latest toHostadpt TX hook-boundary report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TOHOSTADPT_BOUNDARY_REPORT_20260626.md`
- Latest hostadpt TX SKB ownership report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_SKB_OWNERSHIP_REPORT_20260626.md`
- Latest hostadpt TX owner health rootfs/LuCI report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TX_OWNER_HEALTH_REPORT_20260629.md`
- Latest RRO counter map report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RRO_COUNTER_MAP_REPORT_20260629.md`
- Latest RRO refill/page-cache counter report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RRO_REFILL_COUNTERS_REPORT_20260629.md`
- Latest RRO window counter image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RRO_WINDOW_COUNTERS_REPORT_20260629.md`
- Latest RRO owner-read counter image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RRO_OWNER_READ_COUNTERS_REPORT_20260629.md`
- Latest RRO free-pool proxy image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RRO_FREEPOOL_PROXY_REPORT_20260629.md`
- Latest capture risk-assessment image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_CAPTURE_RISK_ASSESSMENT_REPORT_20260629.md`
- Latest LuCI hostadpt owner-controls image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_LUCI_HOSTADPT_OWNER_CONTROLS_REPORT_20260629.md`
- Latest hostadpt doorbell readback image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_DOORBELL_READBACK_REPORT_20260629.md`
- Latest hostadpt doorbell auto-gate image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_DOORBELL_AUTOGATE_REPORT_20260629.md`
- Latest hostadpt enqueue failure-path report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_ENQUEUE_FAIL_REPORT_20260626.md`
- Latest hostadpt doorbell publish report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_DOORBELL_REPORT_20260626.md`
- Latest hostadpt token/descriptor handshake report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_TOKEN_HANDSHAKE_REPORT_20260626.md`
- Latest hostadpt auto-owner report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_AUTO_OWNER_REPORT_20260626.md`
- Latest hostadpt auto-tripwire report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_AUTO_TRIPWIRE_REPORT_20260626.md`
- Latest hostadpt descriptor/SKB tripwire report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_DESC_SKB_TRIPWIRE_REPORT_20260626.md`
- Latest hostadpt auto-owner token quarantine report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_AUTO_TOKEN_QUARANTINE_REPORT_20260627.md`
- Latest hostadpt manual-owner token quarantine report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_MANUAL_OWNER_QUARANTINE_REPORT_20260627.md`
- Latest TXFREE deferred token release report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXFREE_DEFERRED_TOKEN_RELEASE_REPORT_20260626.md`
- Latest TXFREE deferred token quarantine report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXFREE_DEFERRED_TOKEN_QUARANTINE_REPORT_20260626.md`
- Latest TXFREE not-ready token quarantine report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXFREE_NOT_READY_QUARANTINE_REPORT_20260627.md`
- Latest TXFREE callback-order image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXFREE_CALLBACK_ORDER_REPORT_20260629.md`
- Latest TXFREE not-ready precheck image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXFREE_NOTREADY_PRECHECK_REPORT_20260629.md`
- Latest TXFREE DMA cleanup-order image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXFREE_CLEANUP_ORDER_REPORT_20260629.md`
- Latest TXFREE v5 version-policy image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXFREE_V5_POLICY_REPORT_20260629.md`
- Latest TXFREE unmap semantics audit: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXFREE_UNMAP_SEMANTICS_AUDIT_20260629.md`
- Latest TXFREE unmap/TXQ edge audit: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXFREE_UNMAP_TXQ_AUDIT_20260630.md`
- Latest stock token per-phy counter report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TOKEN_PER_PHY_REPORT_20260627.md`
- Latest stock token invalid-phy quarantine report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TOKEN_INVALID_PHY_REPORT_20260627.md`
- Latest hostadpt qentry token quarantine report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_QENTRY_QUARANTINE_REPORT_20260627.md`
- Latest no-pending qentry quarantine report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_NO_PENDING_QENTRY_REPORT_20260627.md`
- Latest duplicate deferred token quarantine report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_DUPLICATE_TOKEN_QUARANTINE_REPORT_20260627.md`
- Latest deferred token NULL classification report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_DEFERRED_NULL_CLASS_REPORT_20260627.md`
- Latest deferred TXWI quarantine flush report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_DEFERRED_TXWI_QUARANTINE_REPORT_20260627.md`
- Latest TXFREE qentry-retention image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXFREE_QENTRY_RETAIN_REPORT_20260629.md`
- Latest TXFREE cache-reset quarantine image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TXFREE_CACHE_RESET_QUARANTINE_REPORT_20260629.md`
- Latest TXFREE stock token freelist shadow image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TOKEN_FREELIST_REPORT_20260629.md`
- Latest stock hostadpt TX lifecycle gate image report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_TX_LIFECYCLE_GATE_REPORT_20260629.md`
- Latest hostadpt qentry quarantine reason report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_QENTRY_QUARANTINE_REASON_REPORT_20260627.md`
- Latest hostadpt qentry reason LuCI report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_QENTRY_REASON_LUCI_REPORT_20260627.md`
- Latest hostadpt auto-owner reason gate report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_AUTO_OWNER_REASON_GATE_REPORT_20260627.md`
- Latest hostadpt per-group auto-owner gate report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PER_GROUP_AUTO_OWNER_REPORT_20260627.md`
- Latest stock return-0 cleanup accounting report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_RETURN0_CLEANUP_REPORT_20260627.md`
- Latest stock pre-token active-release report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_PRETOKEN_ACTIVE_REPORT_20260627.md`
- Latest hostadpt owner-control defaults report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_OWNER_CONTROL_REPORT_20260627.md`
- Latest hostadpt option-type/hook-arg report: `C:\Users\captain\Documents\Codex\2026-06-12\i-need-help-wiping-the-nand\work\W1700K_STOCK_HOSTADPT_OPT_TYPE_HOOKARG_REPORT_20260625.md`

Mirrors are copied to:

- `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult`
- `/home/captain/w1700k-openwrt-build/fanboy-source`

## Current Build Anchor

- Source tree: `/home/captain/w1700k-openwrt-build/fanboy-source`
- Source commit: `5575e4a97f119f682223a090c4a78c0913f906f5`
- Target artifact name emitted by tree: `gemtek_w1700k-ubi`
- current_promoted_sysupgrade_artifact: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\HostadptScatterSkbLifecycle-20260705\w1700k-hostadpt-scatter-skb-lifecycle-20260705-sysupgrade.itb`
- current_promoted_sysupgrade_sha256: `2adf58166b15cd569f3b5d61fa4ec77d990f1acf900003b17e8a974aff84ed5d`
- current_source_vetting_artifact: `work\W1700K_STOCK_HOSTADPT_SCATTER_SKB_LIFECYCLE_SOURCE_20260705.md`
- current_image_vetting_artifact: `work\W1700K_STOCK_HOSTADPT_SCATTER_SKB_LIFECYCLE_IMAGE_REPORT_20260705.md`
- current_offline_coverage_artifact: `work\W1700K_STOCK_OFFLINE_PARITY_AUDIT_20260705.md`
- current_live_datapath_status: `unproven`
- invalidated_evidence_rule: `WrongTarget-192.168.1.1 entries are historical only and excluded from active W1700K parity until a later session independently verifies W1700K target identity.`
- status_terms: `PASS_OFFLINE_COVERAGE means offline/source/image coverage only; it does not mean live datapath parity.`
- Latest promoted image: `HostadptScatterSkbLifecycle-20260705\w1700k-hostadpt-scatter-skb-lifecycle-20260705-sysupgrade.itb`
- SHA256: `2adf58166b15cd569f3b5d61fa4ec77d990f1acf900003b17e8a974aff84ed5d`
- Latest successful WSL build copied to FinalResult: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\HostadptScatterSkbLifecycle-20260705\w1700k-hostadpt-scatter-skb-lifecycle-20260705-sysupgrade.itb`
- Latest successful WSL build SHA256: `2adf58166b15cd569f3b5d61fa4ec77d990f1acf900003b17e8a974aff84ed5d`
- Latest post-target-correction rebuild: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\PostTargetCorrection-20260705\w1700k-post-target-correction-20260705-sysupgrade.itb`
- Latest post-target-correction rebuild SHA256: `1b674146b0e0c82a8d47c2234123264a5c4429fc6ae64e8579d09ebc2ac0e315`
- Latest successful WSL build report: `work\W1700K_STOCK_HOSTADPT_SCATTER_SKB_LIFECYCLE_IMAGE_REPORT_20260705.md`
- Latest successful WSL build report SHA256: `BBC19F84884B909B894DBE96F0145E71D57F1D36086623E8F3ED78929B129BC5`
- Latest successful WSL build `mt76.ko` SHA256: `8bd51c65b0da54517aa52156fdb744a3e9ce800a8e3c86c3f756aed0b45745a4`
- Copy/promotion blocker: none for this image; WSL works through exact `wsl -d Ubuntu --exec /bin/bash --noprofile --norc -lc ...`.
- Latest promoted stock-derived patch: `package/kernel/mt76/patches/9999zzzzzzzzzzzz19-mt76-npu-add-stock-hostadpt-scatter-skb-lifecycle.patch`
- Latest promoted stock-derived patch SHA256: `1102D399BB8D8414BFF4EF1A5999131918F331E9E837F0698D7F77B1A61F5317`
- Latest promoted stock-derived report: `work\W1700K_STOCK_HOSTADPT_SCATTER_SKB_LIFECYCLE_IMAGE_REPORT_20260705.md`, SHA256 `BBC19F84884B909B894DBE96F0145E71D57F1D36086623E8F3ED78929B129BC5`
- Latest source-only stock-derived patch: none newer than promoted patch19
- Latest source-only stock-derived patch SHA256: n/a
- Latest source-only stock-derived report: n/a
- Latest source-only TX verifier patch: `package/kernel/mt76/patches/9999zzzzzzzzzzuuuuu-mt76-npu-block-auto-owner-on-unproven-tx-shapes.patch`
- Latest source-only TX verifier patch SHA256: `fccac2df3d348e8c3072fa889c68eed8a4439e05f4fa5720f0d446310918b314`
- Latest source-only TX verifier report: `work\W1700K_STOCK_TX_PARITY_VERDICT_REPORT_20260703.md`
- Latest promoted TX queue gate classifier patch: `package/kernel/mt76/patches/9999zzzzzzzzzzzz14-mt76-npu-add-stock-txqueue-gate-classifier.patch`
- Latest promoted TX queue gate classifier patch SHA256: `07d20e4620169f21c4c85d683728c22d20bcd48382648809f60b829cb013b4c8`
- Latest promoted TX queue gate classifier source report: `work\W1700K_STOCK_TXQUEUE_GATE_CLASSIFIER_20260705.md`, SHA256 `AAC2A53DD684EACD88B378CA355C00704490F915B064074077E82D51DC3CEBE7`
- Latest promoted TX queue gate classifier image report: `work\W1700K_STOCK_TXQUEUE_GATE_CLASSIFIER_IMAGE_REPORT_20260705.md`, SHA256 `7C78E4EE673E6D748810E54D979081DC1701E3A6801B940DF270F3CE94F7B260`
- Latest promoted TX queue gate classifier rootfs `mt76.ko` SHA256: `2db735778e32f9eb9e5e87f99fa90ef4a6a7c4a7b6c59097e0939e8e30f4c3ec`
- Latest promoted helper SHA256: `e478b719413e905f1cd322b35f1c088ba6e47f0ae1db03e75442a054e6454b3f`
- Latest promoted LuCI JS SHA256: `2e1a62fb6f808979db51e29122f24fd446141f46d18925151af0a10bf9c829c7`
- Latest promoted LuCI APK SHA256: `80a74957361caebf02bb51a5ec2dbf689104190cef215ede76c9b66caa20d734`
- Latest promoted LuCI compile log SHA256: `ff4e4aba9c2a396b4fac2468f9113512507d3b79af872b3e8182079d85470d4f`
- Latest no-image paper closure: `work\W1700K_STOCK_REMAINING_WORK_FROM_3_PAPER_CLOSURE_20260701.md`
- Latest no-image paper closure SHA256: `c1c89db2144f1225f9d91c75873b961d06f995def17957dcfe4480b2e9b4e89b`
- Updated no-image paper roadmap: `work\W1700K_STOCK_REMAINING_WORK_FROM_3_PAPER_ROADMAP_20260701.md`
- Updated no-image paper roadmap SHA256: `0a33e0cae7fecf6a30c4e4afa92b03b79f02405c7f232093ef9d8a1be98a711c`
- Latest no-image Patch 6/test roadmap: `work\W1700K_STOCK_PATCH6_TEST_ROADMAP_20260701.md`
- Latest no-image Patch 6/test roadmap SHA256: `cc3c52880a590f968cd8b5f23f19e666d88455eaabec57ddb4c4f3410dcce34f`
- Latest promoted image report: `work\W1700K_STOCK_HOSTADPT_SCATTER_SKB_LIFECYCLE_IMAGE_REPORT_20260705.md`, SHA256 `BBC19F84884B909B894DBE96F0145E71D57F1D36086623E8F3ED78929B129BC5`
- Latest promoted rootfs proof: `npu-stock-hostadpt-scatter-skb-lifecycle`, stock lifecycle policy, stock/openwrt lifecycle contracts, required live proof text, and all lifecycle status strings are present in built/staged `mt76.ko`; FIT parse passes; manifest contains LuCI/SQM/adblock/SoftEther/NPU packages; manifest and rootfs staging forbidden stock module scans are clean.
- Latest promoted build log: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\HostadptScatterSkbLifecycle-20260705\w1700k-hostadpt-scatter-skb-lifecycle-image-build-20260705.log`
- Latest token entry shadow source report: `work\W1700K_STOCK_TOKEN_ENTRY_SHADOW_SOURCE_20260705.md`, SHA256 `8EEC878F8B59A9D14C897C839189235CDF54F58520C4A8156019F2B8E65FA361`
- Latest token entry shadow patch: `package/kernel/mt76/patches/9999zzzzzzzzzzzz16-mt76-npu-add-stock-token-entry-shadow.patch`, SHA256 `D0D59EE4D8DFC95714CDEEFA3BD2B06665FA93A133F904818368D421F6F220BD`
- Latest token entry shadow proof: WSL mt76 prepare, mt76 compile, and full image build passed; prepared source contains the `npu.c` qentry link, `tx.c` allocation/release/cache-reset hooks, `mt76.h` layout/prototype/stat additions, and `debugfs.c` shadow rows; promoted sysupgrade SHA256 is `2297763c74d5f41260bec56d375d384628745b1997d510d143f993eaee0ff777`.
- Latest promoted stock token shadow verifier report: `work\W1700K_STOCK_TOKEN_SHADOW_VERIFIER_IMAGE_REPORT_20260705.md`, SHA256 `1856E625D6F6C6B2CDB504DC91E62AC6E85A72BF1CED2936DC0D727BA9C9F81B`
- Latest promoted stock token shadow verifier patch: `package/kernel/mt76/patches/9999zzzzzzzzzzzz17-mt76-npu-add-stock-token-shadow-verifier.patch`, SHA256 `B620F136075E8CFC8E2043E23ACFC71A3FE6F8676D059B3775DE9C05C7A8E3EC`
- Latest promoted stock token shadow verifier proof: WSL full image build passed; rebuilt `mt76.ko` SHA256 is `6FE3F8B28B1417C021DA1B5F326D8A38E1CFC093C639E68DA64D52A1E592B347`; module strings include `npu-stock-token-shadow-verifier`, `runtime-mismatch`, `clean-shadow-idr-consistent`, `stock_token_shadow_verifier_status`, and `stock_token_shadow_verifier_errors`.
- Latest promoted stock token shadow trace report: `work\W1700K_STOCK_TOKEN_SHADOW_TRACE_IMAGE_REPORT_20260705.md`, SHA256 `34BE737EB6F29A914E5E174107714A34B2314623813CFCD778BC8FDB120480D2`
- Latest promoted stock token shadow trace source report: `work\W1700K_STOCK_TOKEN_SHADOW_TRACE_SOURCE_20260705.md`, SHA256 `9732DB9745961BA89AB37CA5E09128EE8C55E62ECC7003E1EBB8339F1BD0F72B`
- Latest promoted stock token shadow trace patch: `package/kernel/mt76/patches/9999zzzzzzzzzzzz18-mt76-npu-add-stock-token-shadow-trace.patch`, SHA256 `E3D130E365B9BCA104E48AF9E7CE6B321218A470BEF37003BF921191F54056C2`
- Latest promoted stock token shadow trace proof: WSL mt76 clean, prepare, compile, and full image build passed; rebuilt `mt76.ko` SHA256 is `CFAC4E8A9D933FBBCAA38F7ED0ED852A3A1693D89A729D6E58F39571A9B59818`; sysupgrade SHA256 is `3D3B5741066DA6D1C84622C9E413C271F4F5496921157E052BE76F1F543BCD17`; module strings include `npu-stock-token-shadow-trace`, `stock_token_shadow_trace_policy`, `stock_token_shadow_trace_event_legend`, and `stock_token_shadow_trace_required_live_proof`.
- Latest token shadow verifier live harness report: `work\W1700K_TOKEN_SHADOW_VERIFIER_LIVE_HARNESS_20260705.md`, SHA256 `621E67EFE5E6FD93451A8C97D536DF63853D8F3917881E7EE03AAA2186951EEA`
- Latest token shadow verifier flash/capture harness: `work\w1700k_flash_capture_token_shadow_verifier_20260705.ps1`, SHA256 `3153E03D7F178368C52D8190C84F57BFA51982785D0A6A4C052819C9E3007414`; defaults to no router IP, verifies the sysupgrade SHA256, and refuses `-Flash` unless SSH and W1700K identity are verified unless explicitly overridden.
- Latest token shadow verifier capture analyzer: `work\w1700k_analyze_token_shadow_capture_20260705.ps1`, SHA256 `4D016C41802176D607433FF9BAA6EC81BD4EC87969884B33EC81191B9C9BCDD4`; fixture validation passed with expected exit codes `0` clean, `2` mismatch, and `3` missing.
- Latest token shadow verifier dry-run summary: `work\live-captures\token-shadow-verifier-dryrun-20260705\session-summary.txt`, SHA256 `76F212E414E31E04C5C5D615B64C0A60C923B10FF378F0A8D923243E02B909C0`; no router command transport was used and no flash was attempted.
- Latest token shadow trace live harness report: `work\W1700K_TOKEN_SHADOW_TRACE_LIVE_HARNESS_20260705.md`, SHA256 `4A7D0664B6FF4D1F2E0243201DC28D90774E220096DEAEB31264ECDF51457D25`
- Latest token shadow trace flash/capture harness: `work\w1700k_flash_capture_token_shadow_trace_20260705.ps1`, SHA256 `067461653946DF394D66D4605457640952339932E683D732D17709FDA7040095`; defaults to no router IP, verifies the trace sysupgrade SHA256, captures verifier and trace debugfs together, and refuses `-Flash` unless SSH and W1700K identity are verified unless explicitly overridden.
- Latest token shadow trace capture analyzer: `work\w1700k_analyze_token_shadow_trace_capture_20260705.ps1`, SHA256 `41671EB80BC2D50CC95632C2F4B223974DFC0761C17574D67680D0C2A3D8B5A2`
- Latest token shadow trace dry-run summary: `work\live-captures\token-shadow-trace-20260705-232050\session-summary.txt`, SHA256 `678D9CBCEA79310DDCA307B2EE3F40428E2BB48CBB8C4A9E89CA13DAF0605134`; no router command transport was used and no flash was attempted.
- Latest offline parity audit: `work\W1700K_STOCK_OFFLINE_PARITY_AUDIT_20260705.md`, SHA256 `D9F24A61CCDFB98787E9138B0503634CACEA10482C67BA4C0964B9191A2BFA49`
- Latest offline parity audit script: `work\w1700k_offline_stock_parity_audit_20260705.sh`, SHA256 `51BF5B7BEF55728BFC4BE1602F69538AD37A707C7B7735FC6C80CA40943C0079`
- Latest offline parity audit result: `PASS_OFFLINE_COVERAGE`, 299 pass, 0 fail, verified against the current WSL source tree, rootfs staging, built modules, post-target-correction reproducible artifact, current token-shadow-trace promoted artifact, stock hostadpt TX queue visibility surface, stock TX queue source-gate aliases, stock TX queue gate-classifier counters, stock token/freelist coverage, stock token-entry shadow, stock token-shadow verifier, stock token-shadow trace, stock bridge-control anchors, `mtk_hwifi` bus-fate/start-stop contract markers, and passive MT7990 RRO-MIB safety policy.
- Latest historical hostadpt arg-length flash/capture harness: `work\w1700k_flash_capture_hostadpt_arglen_20260705.ps1`, SHA256 `A4044819FF2EA6389FBCB2430F075E57C162D40679137FC4D8861C5D6E518ECD`; its image target is superseded by the current promoted token-shadow-verifier sysupgrade artifact.
- Latest read-only host probe summary: `work\live-captures\hostadpt-arglen-20260705-112631\session-summary.txt`, SHA256 `FBD33CAB2BCFD297EF87B289647BBB35C45FD550595751AB2DD14C0781BA9788`
- Target-collision correction: the user confirmed on 2026-07-05 that the current router at `192.168.1.1` is not the W1700K. All live ping/port/HTTPS/web observations against that address are wrong-target evidence unless a later session re-verifies W1700K identity first.
- Latest stock web flash-flow mapper: `work\w1700k_stock_web_flash_flow_map_20260705.ps1`, SHA256 `1270EA4E03C84187B9E3355FCCFA81B541E87B7FE26ED5AB6AC0702C156D781D`
- Latest stock web flash-flow report: `work\W1700K_STOCK_WEB_FLASH_FLOW_MAP_20260705.md`, SHA256 `39F9E3E2E374376AFB1FD7FF4613579FD62FDFA5C9047BC79A0CB586CCFD70FA`
- Latest stock web flash-flow capture: `work\live-captures\stock-web-flow-20260705-114050`
- Latest stock web flash-flow verdict: invalidated for W1700K live use because it probed the wrong router at `192.168.1.1`. Keep only as wrong-target evidence; do not use it for W1700K stock-web flashing or updater conclusions.
- Latest static stock updater audit: `work\W1700K_STATIC_STOCK_UPDATER_AUDIT_20260705.md`, SHA256 `ABEF5D4C67318962BEBEB8EFB55BA797BC39B82120C6B5BFBAE06C847C158D55`. Verdict: extracted W1700K rootfs uses Axon/lighttpd FastCGI `/tmp/fcgi` and `/cgi/...` routes, not the wrong-target root-level `*_web_app.cgi` surface; stock `platform.sh` accepts stock magic/header checks and writes MTD `firmware`/`tclinux`/`tclinux_slave`, while NAND helpers exist but are not called. Do not treat stock web/sysupgrade as safe for the custom OpenWrt ITB.
- Latest promoted SHA bundle: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\TokenShadowVerifier-20260705\SHA256SUMS.txt`
- Latest non-FinalResult continuation: none; the 2026-07-05 WSL build was copied to `FinalResult`.
- Latest source-staged stock mtk_pci provider contract patch: `work\9999zzzzzzzzzzuuuuuuuuuy-mt76-npu-add-stock-mtkpci-provider-contract.patch`
- Latest source-staged stock mtk_pci provider contract patch SHA256: `ebfd40d13325a42026a579fdd42998aca58359fbafed0e8bf1ea5c0644672745`
- Latest source-staged stock mtk_pci provider contract report: `work\W1700K_STOCK_MTKPCI_PROVIDER_CONTRACT_PATCH_STAGED_20260704.md`
- Latest source-staged stock mtk_pci provider contract report SHA256: `aecc8c44f86a054979d51d247f365f798a30c442bfe1664493d3fb82f2b8d296`
- Latest source-staged stock mtk_pci provider contract proof source SHA256: `16d58c8d827cf050955a6b785db1fe2256de12e03a652dff94414b0681d1c04d`
- Latest source-staged stock token/freelist contract patch: `work\9999zzzzzzzzzzuuuuuuuuuz-mt76-npu-add-stock-token-freelist-contract.patch`
- Latest source-staged stock token/freelist contract patch SHA256: `29d79845d175241353cff835bfda0d21189969ff67dde28ad4686f078d373c88`
- Latest source-staged stock token/freelist contract report: `work\W1700K_STOCK_TOKEN_FREELIST_CONTRACT_PATCH_STAGED_20260704.md`
- Latest source-staged stock token/freelist contract report SHA256: `9f359401da06057ceec4f4930d5722545bb8fb79d348e08dbcefa65b525f918b`
- Latest source-staged stock token/freelist contract proof source SHA256: `33db830ad0e60bf5abdb9f95e4074f04abfc9c53fac31f9f10ac1eb56f6e155b`
- Latest non-promoted stock TX queue anchor analysis: `work\W1700K_STOCK_HOSTADPT_TXQUEUE_ANCHOR_ANALYSIS_20260704.md`
- Latest focused stock TX queue Ghidra report: `work\W1700K_STOCK_TXQUEUE_FOCUSED_GHIDRA_REPORT_20260704.md`
- Latest focused stock TX queue Ghidra report SHA256: `e75f93ea903262107594d6f5c32242e1d0259cd1863c62d3ce7c5ef71885102a`
- Latest focused `mtk_pci.ko` TX queue output SHA256: `ee2d567f5c7ac3e280fc3784a66955f7f480aab62eedf341bcbf435563e09a7a`
- Latest focused `hostadpt.ko` TX queue output SHA256: `e8fdc14365ce5fca0d1d91c9d76e1ff94306833c9d4793ba2191cb89f1eb66e6`
- Latest stock TX queue source gate spec: `work\W1700K_STOCK_TXQUEUE_SOURCE_GATE_SPEC_20260704.md`
- Latest stock TX queue source gate spec SHA256: `be24e41c19d3f0795edae22d032708bdb7d78b5124b88a94554df9e7708c7cf9`
- Latest stock full decompile export report: `work\W1700K_STOCK_FULL_DECOMPILE_EXPORT_20260704.md`
- Latest stock full decompile export report SHA256: `c646c9d73cb664859f8261cac19e5e558e0a6a44b3a00e20bb007b8bdc8f41ac`
- Latest stock bridge/bus/MT7990 anchor report: `work\W1700K_STOCK_BRIDGE_BUS_MT7990_ANCHOR_REPORT_20260704.md`
- Latest stock bridge/bus/MT7990 anchor report SHA256: `2cb2c32f7c16ad561ba64908ad28197dc59dbd9aec522654c99045083709a743`
- Latest stock hostadpt ring lifecycle source gate: `work\W1700K_STOCK_HOSTADPT_RING_LIFECYCLE_SOURCE_GATE_20260704.md`
- Latest stock hostadpt ring lifecycle source gate SHA256: `a61e47af39982277a33bc8df0a43271524d6715319063eb71242fee7e63d21c7`
- Latest stock MT7990 debug/RRO monitor source gate: `work\W1700K_STOCK_MT7990DBG_RRO_MONITOR_SOURCE_GATE_20260704.md`
- Latest stock MT7990 debug/RRO monitor source gate SHA256: `6de809a345ae700e9ec71602b0f488bbe40234b41d815ea581aba98fb3d94441`
- Latest no-image stock-derived audit: `work\W1700K_STOCK_HOSTADPT_NPU_PROVIDER_REFRESH_20260704.md`
- Latest no-image audit SHA256: `9daa9f54fc259c0199636652ed475a3167996af039aa1b0a74c10de1501f3b87`
- Latest no-image audit verdict: fresh Ghidra audits of stock `hostadpt.ko`, stock `npu.ko`, and stock `npu_bridge_cmd` found no safe source mutation for this pass; the current source already exposes/models stock hostadpt register contracts, ring counters, NPU debug counters, firmware/provider readiness, and the stock bridge-control command surface.
- Previous no-image stock-derived audit: `work\W1700K_STOCK_MTKPCI_PROVIDER_PARITY_REFRESH_20260704.md`
- Previous no-image audit SHA256: `46409e40e86559953eaa09c1e32bb3dc4542aa606a2fda1e6640d39f7e269498`
- Previous no-image audit verdict: stock `mtk_pci.ko` provider Ghidra refresh found no safe source mutation; the current image already models or exposes TX enqueue/headroom/vendor cap, scheduler/trans-slot gate, mailbox policy, ACK-SN state, mode-3 readiness, and RRO free-pool-hit diagnostics.
- Previous promoted image: `w1700k-stock-pingpong-luci-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `97a0f9cdc881d07270343b1145e1a01286cf2ab6d1c3e735fd66120c5aeff710`
- Previous promoted image report: `work\W1700K_STOCK_PINGPONG_LUCI_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-trans-slot-luci-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `ab5a5b1d10dfd05276bb812f2ba642d5624df61e785f5e555fe98ca8476165dc`
- Previous promoted image report: `work\W1700K_STOCK_TRANS_SLOT_LUCI_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-trans-slot-gate-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `93641da238a3fbb6b8aa3827ca4dbf023857a13f76d06ad29804a8dd0f33bc3a`
- Previous promoted kernel image report: `work\W1700K_STOCK_TRANS_SLOT_SCHED_GATE_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-type5-sideband-preclear-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `b5881e429d7d50bc2aa49a7ac1702feb590fc472163b3ce88d60c5be8bd2c6ea`
- Previous promoted kernel image report: `work\W1700K_STOCK_TYPE5_SIDEBAND_PRECLEAR_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-type5-sideband-direct-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `2e9ee33b616142877ec14924447d75b7648525e12df48c0af142ddfe6888ae7f`
- Previous promoted kernel image report: `work\W1700K_STOCK_TYPE5_SIDEBAND_DIRECT_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-type5-status-auto-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `9edd2d2deaacd2f7b7e043e0b9f6ab6b78e54df2f1296976705c9f7d9b2272a3`
- Previous promoted kernel image report: `work\W1700K_STOCK_TYPE5_STATUS_AUTO_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-scatter-copy-clamp-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `14b38625362feab8c9444e5d638d475fb82f01aa94344302d521ca380839be96`
- Previous promoted kernel image report: `work\W1700K_STOCK_SCATTER_COPY_CLAMP_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-type5-sideband-len-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `655aad09ae692fa1679679f30c9c017e711e40955968ff15be4a4b3bcf8068ab`
- Previous promoted kernel image report: `work\W1700K_STOCK_TYPE5_SIDEBAND_LEN_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-rxinfo-bit21-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `1b545fa93d94fde3f4b203e567855052888794519fc33a453e227627a2765c69`
- Previous promoted kernel image report: `work\W1700K_STOCK_RXINFO_BIT21_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-type5-8023-predecode-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `c3096200be97d540c414519334bea4029bbb82df44ea5083ec0508ae3e188692`
- Previous promoted kernel image report: `work\W1700K_STOCK_TYPE5_8023_PREDECODE_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-type5-status-project-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `3b32c3a6de94a93f0b0e5ca7a88737bb35363b8005a1be142647058ff7aed9a5`
- Previous promoted kernel image report: `work\W1700K_STOCK_TYPE5_STATUS_PROJECT_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-txfree-release-error-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `222aa3e49d1688392e4f3635d2a62f5f6f98cf8ea35e0dbdb389954814bc619c`
- Previous promoted kernel image report: `work\W1700K_STOCK_TXFREE_RELEASE_ERROR_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-txfree-token-status-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `e7314dd8d7187b57c93be2a86b90852655dfd267360cff979d57c0f47c74430c`
- Previous promoted kernel image report: `work\W1700K_STOCK_TXFREE_TOKEN_STATUS_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-txfree-byte-bound-short-20260630-sysupgrade.itb`
- Previous promoted image SHA256: `f8bb12fdbcc8a4827c537a31c4eed24bf763ec31a84cd975ec14ea872a1d6fec`
- Previous promoted kernel image report: `work\W1700K_STOCK_TXFREE_BYTE_BOUND_SHORT_REPORT_20260630.md`
- Previous promoted image: `w1700k-stock-txfree-v5-policy-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `c3ad40ce051b591155692e07405838170dc493263beb213b7cc29036af8f95b3`
- Previous promoted kernel image report: `work\W1700K_STOCK_TXFREE_V5_POLICY_REPORT_20260629.md`
- Previous promoted image: `w1700k-stock-txfree-notready-precheck-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `a6e791ff4e97505c38db4e2263d504573213d2b9facf53aedf8f71a112778502`
- Previous promoted kernel image report: `work\W1700K_STOCK_TXFREE_NOTREADY_PRECHECK_REPORT_20260629.md`
- Previous promoted image: `w1700k-stock-txfree-callback-order-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `989449556ce641121599ddd76f6e7768efd376af245f73eafe9b4c3f12d935e1`
- Previous promoted kernel image report: `work\W1700K_STOCK_TXFREE_CALLBACK_ORDER_REPORT_20260629.md`
- Previous promoted image: `w1700k-stock-scatter-first-info-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `5129ab09ab9af2c510029ebb734a5024861f2720b4afae192c32373780884db6`
- Previous promoted kernel image report: `work\W1700K_STOCK_SCATTER_FIRST_INFO_REPORT_20260629.md`
- Previous promoted image: `w1700k-stock-type5-luci-controls-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `e6e2c8542a165a256c483d21d2bbd87632dae75119ff28db1f0523cb02ea9785`
- Previous promoted image report: `work\W1700K_TYPE5_LUCI_CONTROLS_REPORT_20260629.md`
- Previous promoted image: `w1700k-stock-type5-auto-fate-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `9b00eedbccbeee53e0e0ff18c57c70d1f35abafe41b83dbb691190f47e73e119`
- Previous promoted kernel image report: `work\W1700K_STOCK_TYPE5_AUTO_FATE_REPORT_20260629.md`
- Previous promoted image: `w1700k-stock-tx-lifecycle-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `219b0bb1584b992df71f4aacdecb1b24e228f27a462225535e929aafccbc25fb`
- Previous promoted kernel image report: `work\W1700K_STOCK_TX_LIFECYCLE_GATE_REPORT_20260629.md`
- Previous promoted image: `w1700k-stock-skb-bufid-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `8fbf7bfbfd43fd02b73333a161de54682913a1a04a613730fd826896b630d37a`
- Previous promoted kernel image report: `work\W1700K_STOCK_SKB_BUFID_REPORT_20260629.md`
- Previous promoted image: `w1700k-stock-token-freelist-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `49e208f55ac07979b0724302d0168ede3618bd4ac5f3de73ebbadb28ab03c216`
- Previous promoted kernel image report: `work\W1700K_STOCK_TOKEN_FREELIST_REPORT_20260629.md`
- Previous promoted image: `w1700k-doorbell-autogate-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `f216843fdaa8d4df6bbaf208938135b02d13f2c4ed1454ee5219c7cadc303393`
- Previous promoted kernel image report: `work\W1700K_STOCK_DOORBELL_AUTOGATE_REPORT_20260629.md`
- Previous promoted image: `w1700k-luci-hostadpt-owner-controls-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `cf432c4002f93a048c3a215bc8f8009e3d25ed667bb778bacb6859ada59a505c`
- Previous promoted LuCI/rootfs image report: `work\W1700K_LUCI_HOSTADPT_OWNER_CONTROLS_REPORT_20260629.md`
- Latest promoted LuCI source: `work\w1700k-npu.js`
- Latest promoted LuCI source SHA256: `e4ea25d9477b2fec3b060d24434fa309ff2804d6c51821f59a04793a118b5c3b`
- Previous promoted image: `w1700k-stock-capture-risk-assessment-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `934201323e10800d442122876d5f8972e0bcd31da76f24190ed1b72cd972b899`
- Previous promoted rootfs image report: `work\W1700K_STOCK_CAPTURE_RISK_ASSESSMENT_REPORT_20260629.md`
- Previous promoted image: `w1700k-stock-rro-freepool-proxy-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `a634fe5eb8c9db0ca5ab2e3a13d05d5a825216c19b89818aa0a6295df7d3aff1`
- Previous promoted kernel image report: `work\W1700K_STOCK_RRO_FREEPOOL_PROXY_REPORT_20260629.md`
- Previous promoted image: `w1700k-stock-cache-reset-quarantine-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `fe36a075edabbdbd05ed1153f7be67fef35d3d31c46017b2bf61cefd2836daee`
- Previous promoted kernel image report: `work\W1700K_STOCK_TXFREE_CACHE_RESET_QUARANTINE_REPORT_20260629.md`
- Latest repaired prerequisite patch: `package/kernel/mt76/patches/9999zzzzzzzzzo-mt76-npu-map-stock-rro-refill-counters.patch`
- Latest repaired prerequisite patch SHA256: `3c03619df65bd15599cda0d0b323ae6bea0c8f27e49546109b67ba1621ed4f`
- Previous promoted image: `w1700k-stock-rro-refill-counters-20260629-sysupgrade.itb`
- Previous promoted image SHA256: `f3ed19f53125fe0df579065314eed5406ca5aa7a4813857b67bb377919cfd45f`
- Previous promoted kernel image report: `work\W1700K_STOCK_RRO_REFILL_COUNTERS_REPORT_20260629.md`
- Previous poll-owner kernel image report: `work\W1700K_STOCK_HOSTADPT_IRQ_OWNER_IMAGE_REPORT_20260629.md`
- Previous scheduler image report: `work\W1700K_STOCK_HOSTADPT_SCHED_BLOCK_IMAGE_REPORT_20260629.md`
- Previous promoted helper/rootfs report: `work\W1700K_STOCK_ACKSN_CONTROL_REPORT_20260629.md`
- Latest evidence-only recovery report: `work\W1700K_STOCK_GETHIR_PROVIDER_REPORT_20260629.md`
- Latest GET_HIR model report: `work\W1700K_STOCK_GETHIR_MODEL_REPORT_20260629.md`
- Latest live SCU GET_HIR image report: `work\W1700K_STOCK_GETHIR_LIVE_SCU_REPORT_20260629.md`
- Latest GET_HIR provider finding: stock kernel export at runtime/load guess `0x800c9380`; reads register/base offset `0x64` and returns bits `31:16`.
- Latest GET_HIR implementation state: full image verified with live `airoha,en7581-scu` offset `0x64` read enabled by default, fallback `npu_stock_get_hir_model=0xe`, and LTR packet-owning branches still requiring HIR `0xa` or the legacy explicit test override.
- Latest promoted patches:
  - `target/linux/airoha/patches-6.18/999-59-net-bridge-export-rcu-held-fdb-port-lookup.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzza-mt76-npu-add-stock-pingpong-bridge-handoff.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzb-mt76-npu-gate-pingpong-bridge-by-left-to-right-mode.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzc-mt76-npu-classify-pingpong-left-to-right-mode2.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzd-mt76-npu-expose-pingpong-mode2-skb-layout.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzze-mt76-npu-expose-pingpong-mode2-dst-output-contract.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzf-mt76-npu-add-pingpong-mode2-dst-output-handoff.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzg-mt76-npu-add-pingpong-mode2-src0-netif-rx-handoff.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzh-mt76-npu-add-pingpong-mode2-src0-original-netif-rx-handoff.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzi-mt76-npu-require-explicit-get-hir10-assumption-for-ltr-handoffs.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzj-mt76-npu-model-stock-get-hir-as-soc-identity.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzk-mt76-npu-read-stock-get-hir-from-scu.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzl-mt76-npu-block-invalid-hostadpt-scheduler.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzm-mt76-npu-own-hostadpt-rx-irq-reenable.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzn-mt76-npu-expose-stock-rro-counter-map.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzo-mt76-npu-map-stock-rro-refill-counters.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzp-mt76-npu-map-stock-rro-window-counters.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzq-mt76-npu-map-stock-rro-owner-read-counters.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzr-mt76-npu-retain-hostadpt-qentry-until-deferred-token-finish.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzs-mt76-npu-mark-cache-reset-token-quarantine.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzt-mt76-npu-map-stock-rro-free-pool-proxy.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzu-mt76-npu-record-hostadpt-doorbell-readback.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzv-mt76-npu-gate-hostadpt-owner-by-doorbell-readback.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzw-mt76-npu-shadow-stock-token-freelist.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzx-mt76-npu-map-stock-skb-bufid-lifecycle.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzy-mt76-npu-gate-hostadpt-owner-by-stock-tx-lifecycle.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzz-mt76-npu-record-stock-scatter-fail-samples.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzza-mt76-npu-auto-arm-stock-type5-bus-fate.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzb-mt76-npu-preserve-stock-scatter-first-info.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzc-mt76-npu-order-txfree-callback-after-consume.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzd-mt76-npu-precheck-not-ready-token-before-txfree-consume.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzze-mt76-npu-order-dma-cleanup-after-txfree-token-finish.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzf-mt76-npu-match-stock-txfree-v5-version-policy.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzg-mt76-npu-match-stock-txfree-byte-bound-short-accounting.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzh-mt76-npu-expose-stock-txfree-token-status-counters.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzi-mt76-npu-expose-stock-txfree-release-error-counter.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzj-mt76-npu-add-stock-type5-rx-status-projection.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzk-mt76-npu-add-stock-type5-8023-predecode-projection.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzl-mt76-npu-expose-stock-rxinfo-bit21-rewrite.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzm-mt76-npu-expose-stock-type5-sideband-len-proof.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzn-mt76-npu-match-stock-scatter-copy-clamp.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzo-mt76-npu-auto-arm-stock-type5-status-projection.patch`
  - `package/kernel/mt76/patches/9999zzzzzzzzzzp-mt76-npu-add-manual-stock-type5-sideband-direct-write.patch`
- Latest promoted kernel delta: stock type-5 sideband writes at stock SKB offsets `0x38/0x40` now have an exact, guarded, default-off manual test path mapped to current OpenWrt `skb->cb + 0x10/+0x18`, with length/headlen/clobber proof counters. The older scatter clamp, RXINFO bit21 visibility, fail-closed auto status projector, and `RX_FLAG_8023` predecode projector remain present.
- Latest promoted/source TX verifier delta: Patches 1-6 add the stock hostadpt TX state-machine verifier, descriptor byte verifier, SKB/BufID/token/qentry/descriptor equivalence verifier, doorbell/verifier fail-closed auto-owner gate, TX nonlinear/scatter shape guard, and helper/LuCI TX parity verdict. Patch 14 adds read-only stock TX queue gate classifier counters for every `mt76_npu_dma_add_buf()` exit before/at hostadpt enqueue. Patch 15 adds read-only token/freelist coverage matrix debugfs plus helper/LuCI reporting. Patch 16 adds a non-owning stock-offset token-entry shadow with qentry linkage and debugfs coverage. Patch 17 adds `npu-stock-token-shadow-verifier` to compare that shadow against mt76 token IDR/TXWI pointers under `token_lock`. Patch 18 adds token shadow trace observability and is promoted in `TokenShadowTrace-20260705`. Patch 19 adds read-only `npu-stock-hostadpt-scatter-skb-lifecycle` coverage and is promoted in `HostadptScatterSkbLifecycle-20260705`. Packet fate is unchanged.
- Latest no-patch audits: TXFREE payload DMA unmap ownership is behavior-aligned and the unmap-callback/TXQ-NULL edge branches are stock-unreachable/no-op deltas. fromHostadpt provider registration, NULL-return, metadata source, RXINFO hook/cache, stock RXINFO bit21 rewrite visibility, scatter failure attribution/copy-clamp behavior, type-5 bus fate, guarded consume, and guarded sideband-to-status projection are modeled.
- Latest promoted helper/default delta: LuCI now exposes the existing stock hostadpt token pre-release, manual SKB ownership, auto SKB ownership, auto ownership proof-threshold, type-5 bus-fate auto-arm, and type-5 proof-threshold controls in `feeds/luci/applications/luci-app-w1700k-npu/htdocs/luci-static/resources/view/system/w1700k-npu.js`; the helper persists and reports the same type-5 controls through `target/linux/airoha/an7581/base-files/usr/sbin/w1700k-wlan-npu-mode`.

## Implemented Or Reconstructed

- NPU firmware direct loading using the OpenWrt/Airoha firmware path.
- NPU LuCI/debugfs monitoring for mode, PC/watchdog state, IRQ state, ring pressure, counters, and firmware deltas.
- ACK-SN mailbox selector control: rootfs defaults now seed and preserve `npu_stock_ack_sn_ifindex=1`, `w1700k-wlan-npu-mode` exposes `ack-sn-ifindex`, and capture output reports the loaded selector plus the OpenWrt-ifindex-3 / stock-ifindex-1 mailbox contract.
- Capture risk assessment: `w1700k-wlan-npu-capture` now parses stock-shaped debugfs lines such as `fp_full_cnt = N` and classifies positive counter deltas into hostadpt/TXFREE ownership, RRO token pressure, token-release fail-closed, netdev drop/error, and queue-pressure buckets.
- CPU/NPU PM-domain and cpufreq fallback behavior to reduce bring-up weirdness.
- PPE policy reconstruction for force ring, QoS, WDMA queues, fast-bind validation, keepalive, multicast-to-CPU, port aggregation, and tuple classification.
- `foe_ext` shadow metadata and mt76/PPE handoff gates.
- Partial FastTX handoff with shape checks, DstPort gates, queue map, header adjustment, direct-xmit option, and drop/consume classification.
- Ping-pong DstPort handoff: optional `npu_stock_pingpong_dstport_handoff=1` copies eligible reason-`0x19` packets to the mirrored DstPort netdev and consumes the original through the existing RX drop path. It defaults off.
- Ping-pong VirIfIdx classifier: stock `PpeExtIfPingPongHandler` VirIfIdx branch families are classified, normalized DstPort candidates are recorded, and DstPort validity/WiFi-family counters are exposed without changing default packet fate.
- Ping-pong branch-fate classifier: stock branch side effects are now classified as return-1 flags, speed callbacks, PPP/L2TP device handling, TSO callbacks, `netif_rx`, black-IP handling, dev-xmit, fallback dev, kfree/error, ECNT hook, or bridge handoff. Default packet fate is unchanged unless an explicit handoff gate owns it.
- Ping-pong bridge handoff: the image exports `br_fdb_find_port_hold_rcu()` and adds default-off `npu_stock_pingpong_bridge_handoff=1` support for a stock-modeled `br-lan` FDB branch. It copies eligible source-port-zero packets to the resolved bridge egress netdev and consumes the original only when explicitly enabled.
- Ping-pong left-to-right bridge gate: optional bridge FDB handoff now also requires `npu_stock_pingpong_left_to_right_mode=1`, matching the stock `_left_to_right_test_mode == 1` condition for the bridge branch. Mode `2` is blocked because stock uses it for a different left-to-right/netif_rx path.
- Ping-pong left-to-right mode-2 classifier: `npu_stock_pingpong_left_to_right_mode=2` now classifies the stock source-port-5 callback path, source-port-0 `netif_rx` path, and fallthrough source-port path without changing packet ownership. It records that `GET_HIR` remains unmapped.
- Ping-pong mode-2 sk_buff layout proof: debugfs exposes stock mode-2 skb offsets and current OpenWrt 6.18 `struct sk_buff` offsets. Direct mode-2 original-skb mutation remains blocked because stock offsets `0x268/0x270` are outside the current `sk_buff` size `0xe0`.
- Ping-pong mode-2 source-port-5 dst-output contract proof: debugfs exposes live dst/refdst/output/sk prerequisite counters and the stock `dst->output(NULL, skb->sk, skb)` contract string. Packet ownership remains unchanged.
- Ping-pong mode-2 source-port-5 dst-output handoff: optional `npu_stock_pingpong_mode2_dst_output_handoff=1` copies eligible source-port-5 mode-2 skbs, forces a refcounted dst, calls current-kernel `dst_output(dev_net(dst->dev), skb->sk, skb)` on the copy, and consumes the original only after the copy is handed to `dst_output`. It defaults off.
- Ping-pong mode-2 source-port-0 original netif-rx handoff: optional `npu_stock_pingpong_mode2_src0_original_netif_rx_handoff=1` hands the original skb to `netif_rx()` for the stock-modeled source-port-0 mode-2 path and uses an explicit pass/drop/consumed ownership result so mt7996 does not free an already consumed skb. It defaults off.
- Ping-pong rxhandler return contract: stock `PpeRxHandler` immediate-return behavior at callsite `00145038` is now exposed through `last_rxhandler_return` plus return-0/return-1/other counters for decoded local ping-pong handler branches.
- Ping-pong return-gated handoff: optional `npu_stock_pingpong_dstport_handoff=1` now refuses stock-return1 branches and only owns stock-return0 candidates.
- Hostadpt group/ring mapping, descriptor sizing, TXP length limits, ownership fences, doorbell cadence, free-space checks, and 6 GHz group1 mapping.
- Hostadpt TX descriptor publish probe: per-stock-group debugfs snapshots now record the last TX descriptor control word before/after publish, vendor length, payload length, DMA address, SKB pointer, ring/head/next-head, consumer index, queue depth, and stock free-space value.
- Hostadpt TX descriptor reclaim probe: per-stock-group debugfs snapshots now record the last TX cleanup tail, next tail, consumer index, queue depth before cleanup, descriptor word0 before/after owner clear, decoded vendor/payload lengths, DMA address, descriptor SKB pointer, and mt76 queue-entry SKB pointer.
- TXFREE parse-shape probe: debugfs now records stock-derived v4 status-entry counts, v4 pair-skip counts, v4 token-word counts, v5+ counts, expected/freed/missing counters, and the last TXFREE version/context/info/token sample.
- TXFREE legacy parser: mt7996 now accepts stock TXFREE v0/v1/v2 messages, releases v0 two-slot 16-bit tokens and v1/v2 one-slot 15-bit tokens through the normal mt76 token table, and records v0/v1 counters.
- TXFREE delayed TXWI cache return: NPU-active TXFREE paths defer `mt76_put_txwi()` until after completed SKBs are consumed.
- TXFREE deferred token release: NPU-active TXFREE paths now claim token entries without IDR removal, consume completed SKBs, then remove/release the mt76 token entry before TXWI cache reuse, matching stock `mtk_hwifi_free_tx()` ordering more closely.
- Stock token-entry shadow image promotion: patch `9999zzzzzzzzzzzz16-mt76-npu-add-stock-token-entry-shadow.patch` adds a non-owning 0x98-byte stock-offset token-entry shadow, mirrors token checkout/release/cache-reset/qentry linkage, and exposes shadow counters in token layout and token/freelist coverage debugfs. This is promoted in `TokenEntryShadow-20260705`.
- Stock token shadow verifier image promotion: patch `9999zzzzzzzzzzzz17-mt76-npu-add-stock-token-shadow-verifier.patch` adds read-only debugfs `npu-stock-token-shadow-verifier` to compare the non-owning shadow against mt76 token IDR/TXWI state. This is promoted in `TokenShadowVerifier-20260705`.
- TXFREE deferred token quarantine: failed deferred token release now keeps the TXWI out of the reuse cache, matching stock `mtk_tk_release_entry()` failure behavior that does not return invalid/not-ready token entries to the freelist.
- TXFREE not-ready token quarantine: a deferred release that finds a TXWI without stock-active token state now quarantines the TXWI instead of removing the token and returning the TXWI cache entry to reuse, matching stock `mtk_tk_release_entry()` fail-closed behavior for token-not-ready.
- Stock token per-phy active counters: debugfs now tracks active/max token shadow counts per `phy0/phy1/phy2` plus underflow, matching stock's per-band outstanding-token accounting shape for stress validation.
- TXFREE v5 version policy: NPU-active TXFREE v5 now follows stock `bmac_tx_free_notify_v4()` layout rules, while NPU-active versions above 5 increment wrong-version counters and skip token parsing. Non-NPU upstream v5+ behavior remains unchanged.
- TXFREE invalid-phy token quarantine: deferred release now quarantines TXWIs whose stock token PHY is outside the valid range or whose PHY is not registered, matching stock `mtk_tk_release_entry()` invalid-band/unregistered-PHY failure behavior.
- Hostadpt qentry token quarantine marking: deferred token release quarantine now marks the linked hostadpt queue entry and records whether descriptor reclaim later observes that quarantined token state.
- TXFREE cache-reset qentry quarantine: `mt76_put_txwi()` now marks and clears any retained hostadpt qentry before erasing pending/active stock-token cache state, preserving descriptor-reclaim visibility for reset-side packet lifetime loss.
- No-pending qentry quarantine marking: the no-pending/invalid pending-id deferred release failure branch now also marks the linked hostadpt qentry when one is still attached.
- Duplicate deferred token quarantine marking: duplicate deferred TXFREE token claims now increment global quarantine, mark the linked hostadpt qentry if still attached, and expose a dedicated duplicate-quarantine counter.
- Deferred token NULL classification: mt7996 TXFREE parsing no longer counts duplicate or out-of-range deferred token NULL returns as missing tokens; those paths now have dedicated parser counters.
- Deferred TXWI quarantine flush accounting: deferred TXWI cache entries whose deferred token release fails are counted separately from successfully flushed/reused TXWIs.
- Hostadpt qentry quarantine reason preservation: deferred-token quarantine reason is staged on TXWI, copied to the linked hostadpt qentry, and exposed as per-group mark/reclaim reason buckets.
- Hostadpt qentry quarantine reason LuCI integration: helper JSON now exposes `host_token_reason_stats`, and the LuCI NPU page renders mark/reclaim/last reason summaries.
- Hostadpt auto-owner reason gate: auto/manual hostadpt SKB ownership gates now snapshot qentry quarantine reason buckets, block/disarm with per-reason attribution, and expose owner-gate reason state through debugfs/helper JSON.
- Hostadpt per-group auto-owner gate: auto hostadpt SKB ownership now arms independently for group0 and group1, blocks unproven groups from detaching SKBs, and refuses pre-arm if descriptor/SKB missing or mismatch counters are already nonzero.
- Stock NAT hook return-0 cleanup accounting: the optional `npu_stock_txhook_return0_consume` path now records entry, token rollback/no-token, DMA unmap, TXWI put, and SKB consume/missing-SKB counters, plus a debugfs/helper contract string. The consume gate is still not enabled by default.
- Stock hostadpt pre-token release: optional `npu_stock_hostadpt_pre_release_token=1` now mirrors the stock ordering that releases the token before `_toHostadptPktHandle_hook(group, skb, txp, 0x4c)`, while returning the TXWI cache entry only during descriptor reclaim.
- Stock pre-token active-release ordering: local descriptor token-active state is set before optional pre-hostadpt token release, then local descriptor-token accounting is released immediately on successful pre-release so descriptor cleanup does not report a false missing release.
- Hostadpt owner-control defaults: the current image explicitly persists and reports `npu_stock_hostadpt_tx_skb_ownership=0`, `npu_stock_hostadpt_tx_skb_ownership_auto=1`, and `npu_stock_hostadpt_tx_skb_ownership_auto_threshold=4096` through rootfs module defaults, first-boot defaults, and helper JSON/status.
- LuCI hostadpt ownership controls: the NPU page now exposes stock hostadpt token pre-release, manual SKB ownership, auto SKB ownership, and auto ownership proof-threshold controls through the existing `w1700k-wlan-npu-mode mt76-param` backend.
- Hostadpt hook/IRQ telemetry including RXDONE status/enable/disable counters and register snapshots.
- Stock-style hostadpt NAPI schedule-prep behavior.
- Hostadpt RX IRQ poll-owner loop: latest promoted image records per-ring RXDONE owner state, clears it on NPU poll completion, re-enables the hostadpt RXDONE bit from the NPU poll path, and exposes missing-owner fail-safe counters.
- Stock-style `napi_complete_done(napi, 0)` option, enabled in the promoted image line.
- Hostadpt RX consume accounting: q markers, option-type-5 counters, bus RX type-5 counters, RX CPU-index writeback counters, tail/head/queued snapshots, and ring1 option-path classification.
- Hostadpt RX owner-clear ordering: consumed RX descriptors clear `NPU_RX_DMA_DESC_DONE_MASK`, run a DMA write barrier, then publish the host CPU index.
- Historical correction (2026-08-30): the Type-5 projection bullets below
  describe retired `info:+0x04` experiments and are not the current stock
  contract. Full stock hostadpt/PCI/HWiFi reconciliation proves that Type-5
  uses descriptor `data:+0x08`; `info:+0x04` remains PPE/count/reason metadata.
  The retired projectors, direct writes, and fate enforcement remain inactive.
- Hostadpt type-5 RX metadata projection: stock-derived `rxinfo`, projected `local_24[0]`, raw-vs-normalized delta, `local10`, `local8`, decoded local8 bytes, and length bits are recorded per hostadpt group before normal mt76 RX delivery.
- Historical/retired Type-5 RX CB seed: this path seeded raw descriptor `info`
  into `skb->cb[0]`; it does not match the corrected stock Type-5 source and
  must remain inactive. V6.81 observes `data` separately and does not seed skb
  control data.
- Hostadpt RX process-loop split: NPU RX poll now calls a stock-shaped process-batch helper until budget is consumed or the helper returns zero, matching the `pci_dma_rx_poll_hostadpt_ring0()` / `pci_dma_rx_process_hostadpt()` boundary.
- Hostadpt option-type/hook-arg selector: `npu_stock_hostadpt_opt_type` now models stock `g_npu_used_opt_type`; option types `0/1` use secondary qbyte `0x04`, option type `5` uses `0x06`, and unsupported types are counted without pretending they are type 5.
- Hostadpt RX type-check gate: linear NPU hostadpt skbs now run the driver `rx_check()` gate before mt7996 RX delivery, with per-ring ok/drop/no-hook/nonlinear-skip counters.
- Hostadpt CB layout proof and post-fill status probe: build now proves `skb->cb` offset/size and `struct mt76_rx_status` size, exposes direct-write safety as false, and probes stock-derived type-5 length/local8 metadata after mt7996 RX status fill.
- Hostadpt type-5 local8 decode telemetry: stock `rxinfo` bits are now decoded into explicit debugfs counters for the gather/continuation bit, local8 high-bit fields, low7 flags, and last observed rxinfo/local8 values.
- Hostadpt type-5 local8/status correlation telemetry: debugfs now compares stock-derived local8 candidates against post-`mt7996_mac_fill_rx()` mt76 status fields and records match/mismatch buckets without mutating RX status.
- Hostadpt type-5 RX status projection: default-off `npu_stock_hostadpt_rx_type5_status_project=1` can now project validated stock local8 candidates into mt76 RX QoS/aggr/AMSDU/checksum metadata. Default-off mode records exact would-change counters and last before/stock/after snapshots.
- Hostadpt type-5 RX 802.3 predecode projection: default-off `npu_stock_hostadpt_rx_type5_8023_predecode_project=1` can now project validated stock local8 bit30 into `RX_FLAG_8023` before mt7996 radiotap decode. Default-off mode records would-change, would-set, and would-clear counters.
- Hostadpt type-5 exact sideband direct-write test mode: default-off `npu_stock_hostadpt_rx_type5_sideband_direct_write=1` can apply the stock `_fromHostadptPktHandle_hook()` writes by mapping stock `skb+0x38` to OpenWrt `skb->cb+0x10` and stock `skb+0x40` to `skb->cb+0x18`; it requires valid group state, non-null SKB, stock length bits matching `skb->len`, and stock length bits matching `skb_headlen()`, and records applied/disabled/no-skb/length/headlen/clobber proof counters.
- Hostadpt type-5 bus-fate telemetry: debugfs now mirrors the stock `mtk_bus_rx_process(..., 5, skb)` local8 fate gates, counting bmac delivery, hook-bit25, selector-2 consume, selector-3 consume, and generic nonzero consume candidates without dropping or mutating packets.
- Hostadpt type-5 RX fate enforcement: optional `npu_stock_hostadpt_rx_type5_bus_fate_enforce=1` now consumes nonzero stock type-5 bus selectors before mt7996 RX delivery, while default-off mode only records counters.
- Hostadpt type-5 bus-fate auto-arm: the current image defaults `npu_stock_hostadpt_rx_type5_bus_fate_auto=1` and only arms stock nonzero selector consume after clean type-5 proof; debugfs records armed/disarmed state and exact block reasons.
- Hostadpt type-5 LuCI/helper controls: the current image exposes `npu_stock_hostadpt_rx_type5_bus_fate_auto` and `npu_stock_hostadpt_rx_type5_bus_fate_auto_threshold` through helper status/JSON, boot persistence, and the LuCI NPU page.
- Hostadpt registration/scheduler contract: Ghidra pins ring0/ring1 wifitask registration, interrupt bit ownership, ring0 queue type `0x800`, ring1 option-type-5 queue type `0x800000`, ring1 option-type-0 queue type `0x2000`, and unsupported option-type rejection. The current image exposes matching `npu-hostadpt-debug` fields for queue type, trans slot, ifindex bit, valid/reject count, last option type, and invalid scheduler-contract fail-closed counters before NAPI scheduling.
- Hostadpt RXINFO hook precache: stock-normalized RXINFO is recorded before mt7996 RX delivery, modeling the stock `_ra_sw_nat_hook_rxinfo(skb, 0x7275, &rxinfo, 4)` checkpoint with debugfs counters for hook calls, no-PPE, FOE-valid/invalid, cache updates, last raw/normalized RXINFO, raw-vs-normalized delta, bit21 raw/present state, bit21 added state, last hash, and reason buckets.
- Hostadpt nonlinear RX check gate: nonlinear/scatter hostadpt SKBs no longer bypass the stock-style packet-type boundary. The current image reads nonlinear RXD DW0 when present, applies mt7996 MAP-frame normalization, drops side-effect packet types before mt7996 RX delivery, and fails closed on too-short nonlinear heads without running side-effectful full driver parsing on partial data.
- Hostadpt hook-bit25 NULL-callback proof: stock W1700K `mtk_pci.ko` has `pci_dma_ops + 0x90` as a NULL slot, so the type-5 bit25 branch does not call a vendor callback on this device; debugfs now records hook-bit25 as an explicit no-op callback path.
- Hostadpt scatter buffer reuse: successful stock-linearized scatter RX now keeps descriptor backing buffers mapped and reuses them on refill instead of returning them to the page pool, matching stock hostadpt's copy-into-new-skb / keep-descriptor-buffer lifecycle more closely.
- Hostadpt incomplete scatter recycle: after scatter retry exhaustion, completed DONE fragments are recycled, descriptor ownership is cleared, `dma_idx` is published, and recycle counters are exposed instead of leaving a dead scatter head at the RX tail.
- Hostadpt scatter failure sampling: debugfs now exposes stock-shaped scatter failure reason counters and the last failing descriptor sample, including reason, qid/ring, descriptor index, fragment index, advertised count/id, lengths, last-bit state, raw ctrl, and raw info.
- Hostadpt scatter first-fragment metadata preservation: successful scatter RX
  returns first-fragment `info` for PPE/count/reason handling. This does not
  represent stock Type-5 `local_24[0]`; V6.81 preserves first-fragment `data`
  independently for observe-only Type-5 telemetry and mismatch accounting.
- Hostadpt fromHostadpt/type-5 delivery boundary telemetry: debugfs now records returned-SKB vs no-packet from-hook outcomes, type-5 deliver/drop-before-deliver counters, and last delivery/drop info words per hostadpt group.
- Hostadpt toHostadpt TX hook boundary telemetry: debugfs now records the OpenWrt boundary equivalent of stock `_toHostadptPktHandle_hook(group, skb, txp, 0x4c)`, including call/free-space/would-return counters and last ring/head/index/length/SKB snapshots per stock group.
- Hostadpt TX SKB ownership mode: opt-in `npu_stock_hostadpt_tx_skb_ownership=1` detaches the SKB from the TXWI token after stock-shaped hostadpt enqueue and frees the descriptor SKB from hostadpt cleanup, while firmware TX-free still releases the token.
- Hostadpt TX owner health reporting: helper JSON and LuCI now summarize stock TX ownership readiness per radio/group, including armed/waiting/blocked state and TXFREE, descriptor/SKB, token quarantine, and invalid per-phy token blockers. This is diagnostic/readiness plumbing; packet ownership behavior is unchanged from the previous kernel image.
- Hostadpt toHostadpt auto-owner fail-closed gate: stock `mtk_pci.ko` ignores `_toHostadptPktHandle_hook()` return, while stock `hostadpt.ko` frees the SKB and returns error on full/error. The promoted image line records the ignored-return boundary and blocks or disarms hostadpt SKB auto ownership when stock TX-hook would-error counters advance.
- Stock RRO counter map: `wed_rro_status` now exposes stock-shaped `FUN_00107594` debug counters using verified live OpenWrt equivalents, including RX token outstanding/max, segment/drop/error counts, indication/signature counts, MSDU count buckets, last session/SN/reason, last token id, and last ACK SN/session. Older free-pool/window placeholders have been progressively replaced where live equivalents were proven.
- Stock RRO refill/page-cache counters: `wed_rro_status` now maps stock `refill_cnt` from `FUN_00107c80` to live OpenWrt refill attempts and exposes OpenWrt page-cache/page-map hit/miss/free diagnostics. Stock token free-pool start/end remain unavailable.
- Stock RRO window counters: `wed_rro_status` now maps stock `larger_winsize_cnt` from `FUN_001087e0` to live RRO indication processing. The implementation caches RX-BA window size per accepted RRO session id and caps indication processing only when a valid mapped session window exists.
- Stock RRO owner-read counters: `wed_rro_status` now maps stock owner-bit reread accounting to live mt76 RRO page consumption through `addition_read_cnt`, `max_read_cnt`, `openwrt_owner_wait_timeout`, and `last_owner_reads`.
- Stock RRO free-pool proxy/verdict/hit classification: `wed_rro_status` now exposes stock-shaped `fp_full_cnt`, `fp_tkid_start`, and `fp_tkid_end` by mapping to OpenWrt RX token allocation failures and RX token IDR range, with explicit `stock_rro_free_pool_proxy` labeling. The current image also gates the RRO/BA verdict on free-pool availability, allocation failures, sample readiness, zero-minimum-watermark degradation, and stock-shaped free-pool-hit events where RRO returns a token OpenWrt already considers free. LuCI surfaces those free-pool blockers, hit counts, and last hit token in the RRO/BA and free-pool rows.
- Stock mailbox provider visibility: the current image adds helper JSON object `stock_mailbox_provider` and LuCI Current State rows for stock-mode3 prerequisite readiness, TX PCIE publication, TX RXDESC base negotiation, TX buffer-space mailboxes, RX/TXDONE ring setup, ACK-SN selectors, error counts, and the next live-capture action. This is visibility only; kernel datapath, NPU mode defaults, and packet ownership are unchanged from the previous image.
- Stock `mtk_pci.ko` provider contract source stage: read-only patch `work\9999zzzzzzzzzzuuuuuuuuuy-mt76-npu-add-stock-mtkpci-provider-contract.patch` adds future debugfs producer `npu-stock-mtkpci-provider-contract`, documenting stock TX PCIE address publication, TX buffer-space mailboxes, RXDESC query, BA-node/PCIE-port/RRO opcodes, `glb_npu_trans1/trans2`, ACK-SN publication, allowed-ring/PCIE-index mappings, queue-bus CPU-index gate, and IRQ/NAPI ownership. Local patch check and clean proof apply passed; mt76 compile, image build, and live capture remain pending WSL/source restoration.
- Stock hostadpt/NPU provider refresh: fresh Ghidra audits now pin stock `hostadpt_rx_handler` at `001009a0`, stock `hostadpt_tx_handler` at `00101944`, hostadpt TX group registers `0xa0-0xbc`, RX group registers `0x180-0x19c`, TX/RX descriptor stride/depth, stock `npu.ko` provider symbol requirements, and stock `npu_bridge_cmd` selector/control surface. This produced a no-source-mutation verdict because the current source already exposes the comparable register/debug/control surfaces; live equivalence remains open.
- Stock MLO BA-link verifier: reference image `w1700k-stock-mlo-ba-link-verifier-20260703-sysupgrade.itb` includes mt76 patch `9999zzzzzzzzzzuuuuuuu-mt7996-npu-add-mlo-ba-link-verifier.patch`, helper JSON `stock_rro_ba_link_verifier`, and LuCI Current State rows for BA-link summary/mapping/last-event/next-action. It records BA setup/status/retry/delete ownership by WLAN ID, TID, RRO session, MLO link ID, and mt76 PHY index through `stock-ba-link-*` debugfs rows.
- Historical live flash/capture harness: `work\w1700k_flash_capture_mlo_ba_link_20260703.ps1` verifies image SHA256 `666e1b9c0b05155c6a5fb1c6bbe84cd0793aa9fdee7e5096e4cac2078cb1e05f`, optionally flashes its historical target image over SSH, waits for reboot, and captures board/kernel/wireless/helper/debugfs/log evidence. No-flash prep on 2026-07-03 found no COM ports, no `192.168.1.1` ping, no `192.168.1.1:22`, Wi-Fi on `192.168.100.97`, and Ethernet disconnected, so no flash was attempted.
- Read-only live capture harness: `work\w1700k_readonly_live_capture_20260704.ps1` SHA256 `45f38e6a2336b7c75bcca7c13a777ecb862888db2c5d6cf39435ea45c5d01f49` tries SSH first, then explicit `COM3` serial, and saves helper/debugfs/wireless/log evidence without flashing or changing router config. Latest session `work\live-captures\readonly-20260704-155519\session-summary.txt` SHA256 `b94a642ff4c1bd648b7ecfac4344d9c4dc35d7f91811ff87d69791c957a690c1` found `192.168.1.1` ping reachable, SSH unavailable, no visible serial ports, and `COM3` open failure because the port does not exist.
- Hostadpt enqueue failure-path accounting: debugfs now records when failed hostadpt enqueue returns to OpenWrt with an SKB that will be freed through the normal TX status/free path, matching stock's "return error and free SKB" outcome without double-freeing inside `mt76_npu_dma_add_buf()`.
- Hostadpt doorbell publish/readback telemetry: debugfs now records the existing stock-style immediate TX host DMA-index publish to `0xa8/0xb8`, including per-group write count, target register, software previous value, new value, descriptor index, and queued depth. The latest image also reads live `0xa8/0xb8` only when `npu-hostadpt-debug` is read and compares it against the last software value and mapped queue indices.
- Hostadpt doorbell auto-gate: stock hostadpt SKB ownership auto-arm now requires clean TXFREE-before-reclaim proof, clean descriptor/SKB proof, no deferred-token/qentry quarantine reason, and at least one matching doorbell readback for the hostadpt group. Later doorbell mismatch observations disarm auto ownership for future packets.
- Hostadpt token/descriptor handshake telemetry: debugfs now links queued hostadpt TX descriptors to mt76 TXWI tokens, marks TXFREE release against the descriptor entry, and records whether descriptor cleanup saw TXFREE first or missed it under load.
- Hostadpt SKB/BufID lifecycle mapping: debugfs now exposes stock-shaped `TX_SKB_ALLOC_BUFID_COUNT`, `TX_SKB_FREE_BUFID_COUNT`, `TX_SKB_BUFID_ALLOC_FAIL`, and `SKB_BUFID_STATE_ABNORMAL` counters by treating hostadpt TXWI tokens as the OpenWrt equivalent of stock TX SKB BufIDs. Auto hostadpt SKB ownership refuses to arm, or disarms later, when BufID abnormal counters are present.
- Hostadpt TX lifecycle gate: debugfs now tracks stock-shaped enqueue, descriptor publish, doorbell, TXFREE/pre-release, descriptor reclaim, and clean lifecycle counts per hostadpt group. Auto hostadpt SKB ownership requires clean lifecycle samples and fails closed if sequence errors appear.
- Hostadpt stock SKB ownership auto-arm: debugfs and module parameters now allow stock hostadpt SKB ownership to auto-arm after clean full-lifecycle and TXFREE-before-reclaim proof; descriptor cleanup frees only SKBs explicitly marked detached at enqueue.
- Hostadpt stock SKB ownership auto-tripwire: auto ownership now disarms for future packets if TXFREE/descriptor proof breaks after auto-arm.
- Hostadpt descriptor/SKB auto-tripwire: auto ownership now snapshots descriptor reclaim SKB missing/mismatch counters at arm and disarms for future packets if those counters advance after arm.
- Hostadpt doorbell/verifier auto-owner gate: source-only Patch 4 blocks auto ownership on doorbell mismatch, doorbell lifecycle state errors, descriptor-byte verifier mismatches, or SKB/BufID/token/qentry/descriptor equivalence verifier mismatches; after arm it disarms future auto-owned packets if any of those counters advance. Packet fate is unchanged.
- Hostadpt TX shape guard: source-only Patch 5 records nonlinear, page-frag, `frag_list`, GSO/TSO, short-headlen, payload-too-large, and last-shape fields at the NPU hostadpt TX boundary, then blocks or disarms automatic hostadpt SKB ownership if those unproven TX shapes appear. Packet fate is unchanged.
- Hostadpt auto-owner token quarantine tripwire: auto ownership now refuses to arm, or disarms future auto-owned packets, when deferred-token release quarantine appears.
- Hostadpt manual-owner token quarantine fail-closed: manual stock hostadpt SKB ownership now refuses to detach SKBs after deferred-token release quarantine appears.
- Stock token/freelist contract source stage: read-only patch `work\9999zzzzzzzzzzuuuuuuuuuz-mt76-npu-add-stock-token-freelist-contract.patch` adds future debugfs producer `npu-stock-token-freelist-contract`, documenting stock `mtk_hwifi.ko` TXFREE version parsing, token lookup/release, freelist head/tail/poison/list-count fields, per-band active counters, token init layout, per-entry debugfs, and `mtk_ge_tx_data()` token handoff. Local patch check passed against the `mtk_pci` provider-contract staged base; mt76 compile, image build, and live stress equality remain pending WSL/source restoration.
- Stock HWiFi bus contract source stage: read-only patch `work\9999zzzzzzzzzzuuuuuuuuuaa-mt76-npu-add-stock-hwifi-bus-contract.patch`, SHA256 `f62fad97ecda9e7a8b782329094ba5365c3f4d819745d668775f2fac71cf5581`, adds debugfs producer `npu-stock-hwifi-bus-contract`. It documents stock `mtk_hwifi.ko` `mtk_bus_rx_process()` packet-type acceptance, type-5/8/9 selector fate, NPU start/stop callback offsets, DMA-token enable/disable sequencing, and bus lifecycle callback offsets. Source replay and targeted mt76 compile passed in WSL; image build and live proof remain pending.
- Stock contract debugfs LuCI source compile: WSL source now exposes `stock_contract_debugfs` helper JSON and LuCI Current State rows for `npu-stock-hostadpt-ring-contract`, `npu-stock-mtkpci-provider-contract`, `npu-stock-token-freelist-contract`, and `npu-stock-hwifi-bus-contract`. `make package/feeds/luci/luci-app-w1700k-npu/compile V=s` passed on 2026-07-05. Report: `work\W1700K_STOCK_CONTRACT_DEBUGFS_LUCI_SOURCE_COMPILED_20260705.md`. No sysupgrade image or router flash happened.
- Stock passive contract producer source compile: WSL source tree `/home/captain/w1700k-openwrt-build/fanboy-source` now has source-replay mt76 patches `9999zzzzzzzzzzzz01` through `9999zzzzzzzzzzzz07` for `npu-stock-rro-mib`, `npu-stock-queue-pressure`, `npu-stock-agg-ba-limits`, `npu-stock-trans-map`, `npu-stock-hostadpt-ring-contract`, `npu-stock-mtkpci-provider-contract`, `npu-stock-token-freelist-contract`, and `npu-stock-hwifi-bus-contract`. `make package/kernel/mt76/clean`, `prepare`, and `compile -j1` passed on 2026-07-05; built `mt76.ko` SHA256 is `27ceacd3287b20be15fda8c0426687af2c1e39292d35301cc0a0823d166411a4`. No sysupgrade image or router flash happened.
- Stock token stress window source compile: WSL source tree now has mt76 patch `9999zzzzzzzzzzzz10-mt76-npu-add-stock-token-stress-window.patch`, SHA256 `ae66e72c8d73b48fef6e6147107facfb3929ed7edb2f39f5db970cc12c3c3593`, adding deferred-token pending-current/max/underflow counters and release-latency buckets plus `stock_txfree_defer_token_stress_contract`. `make package/kernel/mt76/prepare V=s` and `make package/kernel/mt76/compile V=s -j1` passed on 2026-07-05; built `mt76.ko` SHA256 is `da98dc79be12495232ba1b07c4f4970fad3c4fd32cc65e6e4756ad5da01955d2`.
- Stock token stress LuCI image build: promoted image `w1700k-token-stress-luci-20260705-sysupgrade.itb` in `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\TokenStressLuCI-20260705`, SHA256 `ad0a51bc72066bd25df50ab4bcaf190853060714e304ba8fc1e16f39bfc8acb4`. Full `make -j$(nproc) V=s` passed from source commit `5575e4a97f119f682223a090c4a78c0913f906f5`; FIT parse passed; helper JSON exposes `stock_token_stress`; LuCI exposes deferred token pending-window, release-latency, and next-action rows; `strings mt76.ko` found the token-stress contract and all pending/latency counters; proprietary-module negative check passed for stock `hostadpt.ko`, `mtk_pci.ko`, `mtk_hwifi.ko`, `mt7990*.ko`, and stock `npu.ko`. Report: `work\W1700K_STOCK_TOKEN_STRESS_LUCI_IMAGE_REPORT_20260705.md`. No router flash or router config change happened.
- Stock TXFREE token parity source compile: WSL source now has mt76 patch `9999zzzzzzzzzzzz11-mt76-npu-split-stock-txfree-release-errors.patch`, SHA256 `972d14dd68a44f56a1a2552f1808b3fde46d35597cbe20cc5a2cdf5f2988c60c`. It splits deferred-token failures into pre-claim and post-claim buckets, adds a stock `mtk_tk_get_tx_q()` equivalent TX queue NULL quarantine, and exposes `stock_txfree_get_tx_q_contract`. `make package/kernel/mt76/clean V=s` and `make package/kernel/mt76/compile -j1 V=s` passed; built `mt76.ko` SHA256 is `0175012ba52e612d9cc10228fee50b0263709ec9262e8e4728c9d9d4bd0186a9`. No sysupgrade image or router flash happened.
- Stock TXFREE token parity image build: promoted image `w1700k-txfree-token-parity-20260705-sysupgrade.itb` in `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\TXFreeTokenParity-20260705`, SHA256 `d86bf7644642f687c920a652bec9e959a2e9bcf50955751cc39f05eb9e0bc869`. Full `make -j$(nproc) V=s` passed; FIT parse passed; rootfs `mt76.ko` strings found the preclaim/TXQ NULL counters and `stock_txfree_get_tx_q_contract`; proprietary-module negative check passed. Report: `work\W1700K_STOCK_TXFREE_TOKEN_PARITY_IMAGE_REPORT_20260705.md`. No router flash or router config change happened.
- Stock hostadpt equivalence detail image build: promoted image `w1700k-hostadpt-equiv-detail-20260705-sysupgrade.itb` in `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\HostadptEquivDetail-20260705`, SHA256 `d9613013c7adad309b89a617c535d4fd357cf69680a4b875d5eaf5decb5ff01a`. Helper JSON now exposes `stock_hostadpt_equivalence_detail`; LuCI shows hostadpt equivalence detail, reason buckets, and last packet-identity sample. `sh -n`, Windows `node --check`, helper JSON parse, sequential package compiles, clean-PATH full image build, FIT parse, rootfs helper/LuCI checks, rootfs module string checks, and proprietary-module negative checks passed. Report: `work\W1700K_STOCK_HOSTADPT_EQUIV_DETAIL_IMAGE_REPORT_20260705.md`. No router flash or router config change happened.
- WSL revalidated and ACK-SN LuCI control fixed: WSL2 Ubuntu is currently installed, runnable, and has the OpenWrt source tree at `/home/captain/w1700k-openwrt-build/fanboy-source`; the old no-installed-distribution note is stale. LuCI now exposes backend-supported `npu_stock_ack_sn_ifindex` as a status row, numeric input, and `mt7996e-param` save path. `node --check`, helper `sh -n`, helper JSON smoke, clean LuCI package rebuild, packaged/minified JS proof, clean-PATH full image build, FIT parse, rootfs-staging ACK-SN proof, manifest package check, and proprietary stock-module negative scan passed. Promoted image `w1700k-ack-sn-luci-20260705-sysupgrade.itb` in `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\ACKSNLuCI-20260705`, SHA256 `f2e63398f20b430dc6500fa4f2d64fe4eb0a49c3d8845f0b1dfcce9e25d00e4b`. Rebuilt `luci-app-w1700k-npu-0.apk` SHA256 `8565f17c7455e36b31316821f578bd32e35f0725d8120642157904d1e8eab39e`. Report: `work\W1700K_STOCK_ACK_SN_LUCI_WSL_AUDIT_20260705.md`. No router flash or router config change happened.
- Superseded ACK-SN live harness: `work\w1700k_flash_capture_ack_sn_20260705.ps1`, SHA256 `47b0f71091afdcf3385252ef60356f6c59697c016d1ddf8162076b2617cbb429`, targeted the older ACK-SN image and is superseded by the hostadpt arg-length harness. Its read-only `192.168.1.1` network probe is now wrong-target evidence and must not be used for W1700K conclusions. No flash, router config change, or router-side command capture happened.
- Historical hostadpt arg-length live harness: `work\w1700k_flash_capture_hostadpt_arglen_20260705.ps1`, SHA256 `A4044819FF2EA6389FBCB2430F075E57C162D40679137FC4D8861C5D6E518ECD`, targets `w1700k-hostadpt-arglen-verifier-20260705-sysupgrade.itb` and is read-only unless `-Flash` is passed. Parser check passed. Read-only run `work\live-captures\hostadpt-arglen-20260705-112631\session-summary.txt`, SHA256 `FBD33CAB2BCFD297EF87B289647BBB35C45FD550595751AB2DD14C0781BA9788`, probed the wrong router at `192.168.1.1`; do not use its network/HTTPS result as W1700K evidence. No flash, router config change, or router-side command capture happened.
- Stock HTTPS surface probe: `work\w1700k_stock_https_surface_probe_20260705.ps1`, SHA256 `647f65b900f77fd6e4febe7058cb3df0c991700f2ad385b7ee5830927e6d845c`, ran read-only GET-only capture at `work\live-captures\stock-https-surface-20260705-101644` against the wrong router at `192.168.1.1`. Report `work\W1700K_STOCK_HTTPS_SURFACE_PROBE_20260705.md` is retained only as invalidated wrong-target evidence.
- Stock web flash-flow map: `work\w1700k_stock_web_flash_flow_map_20260705.ps1`, SHA256 `1270EA4E03C84187B9E3355FCCFA81B541E87B7FE26ED5AB6AC0702C156D781D`, ran read-only flow extraction at `work\live-captures\stock-web-flow-20260705-114050` against the wrong router at `192.168.1.1`. Report `work\W1700K_STOCK_WEB_FLASH_FLOW_MAP_20260705.md`, SHA256 `39F9E3E2E374376AFB1FD7FF4613579FD62FDFA5C9047BC79A0CB586CCFD70FA`, must not be used for W1700K stock-web updater conclusions.
- Static stock updater audit: `work\W1700K_STATIC_STOCK_UPDATER_AUDIT_20260705.md`, SHA256 `ABEF5D4C67318962BEBEB8EFB55BA797BC39B82120C6B5BFBAE06C847C158D55`, records that the extracted rootfs upgrade path is stock MTD/header oriented: `platform_check_image()` accepts `32524448`/`48445232` magic with optional `blapi_cmd system check_secure_tclinux`, `platform_do_upgrade()` writes `firmware` or `tclinux`/`tclinux_slave`, and normal NAND helpers are present but not wired by `platform.sh`. This audit is static only and does not change the OpenWrt image.
- Post-target-correction rebuild: `work\W1700K_POST_TARGET_CORRECTION_REBUILD_20260705.md` records clean WSL mt76 rebuild, helper syntax, LuCI JS syntax, LuCI package compile, sanitized image build, FIT parse, manifest package proof, and rebuilt stock-NPU strings. Rebuilt sysupgrade hash is unchanged from the previous promoted image: `1b674146b0e0c82a8d47c2234123264a5c4429fc6ae64e8579d09ebc2ac0e315`.
- Offline stock NPU parity audit: `work\w1700k_offline_stock_parity_audit_20260705.sh`, SHA256 `64dbc5abaf4577c087c8fec2af4a893e5b4eb8cafecbc64cb6cf3d4d165d0c1d`, produced `work\W1700K_STOCK_OFFLINE_PARITY_AUDIT_20260705.md`, SHA256 `656080b30f27ffb4fb3fceacca2f47e9667f8d1c35682d8eacc73dfdf34e188a`. Result: `PASS_OFFLINE_COVERAGE`, 275 pass, 0 fail. It verifies required stock-NPU patch files through `9999zzzzzzzzzzzz16`, debugfs contract tokens, mode3 prerequisite policy, fast-TX handoff, ping-pong policy, RRO/free-pool/BA-link helper and LuCI surfaces, stock hostadpt TX queue visibility, stock TX queue source-gate aliases, stock TX queue gate-classifier counters, stock token/freelist coverage, stock token-entry shadow, stock bridge-control command anchors, `mtk_hwifi` selector/start-stop contract markers, passive MT7990 RRO-MIB safety policy, module defaults, rootfs staging copies, built `mt76.ko`/`mt7996e.ko` strings, final manifest packages, current token-entry-shadow artifact image SHA256, checksum file image entries, forbidden stock-module absence, and hostadpt hook arg-length tokens. The audit explicitly refuses to use `192.168.1.1` evidence because the current router at that address is not the W1700K. This is offline coverage only; live datapath equivalence remains unproven.
- Superseding image coverage audit: the same `w1700k-token-stress-luci-20260705-sysupgrade.itb` also contains the earlier promoted `npu-stock-token-layout-map` and `npu-stock-hostadpt-ring-lifecycle` verifier work. Coverage audit report: `work\W1700K_STOCK_SUPERSEDING_IMAGE_COVERAGE_AUDIT_20260705.md`; copied artifact SHA256 `05dd9080118448c64a125d52c83892b16501a40214a9dd9eb9570717f1882bf6`. Read-only live capture attempt `work\live-captures\readonly-20260705-063903\session-summary.txt` found ping reachable at `192.168.1.1`, SSH closed, no visible serial ports, and COM3 absent, so live proof remains pending.
- Ping-pong mode-2 source-port-0 netif-rx handoff: the promoted image line records stock source-port-0 L2 classification and provides both the earlier default-off copied-skb `netif_rx()` handoff via `npu_stock_pingpong_mode2_src0_netif_rx_handoff` and the newer default-off original-skb handoff via `npu_stock_pingpong_mode2_src0_original_netif_rx_handoff`; mt76 compile, package install, target install, FIT metadata, extracted image-rootfs module proof, and SHA256 verification passed.
- Ping-pong GET_HIR gate: packet-owning LTR handoffs now require explicit `npu_stock_pingpong_assume_get_hir10=1`, since true stock `GET_HIR()==10` remains unmapped. Classification still records enabled/disabled/block counters.
- WiFi/LuCI regulatory width validation aligned to the current OpenWrt regdb and live AP channel map.
- MLO UI and validation fixes for multi-radio selection, hidden-invalid-field failures, and radio index labeling.
- Stock RRO MIB source stage: workspace source snapshots expose helper JSON `stock_rro_mib`, optional verify/status handling for `npu-stock-rro-mib` debugfs, and LuCI Current State rows for passive stock RRO reorder/exception/timeout counters from register range `0xa180..0xa1ac`. The current active WSL source line now carries this as `package/kernel/mt76/patches/9999n-mt76-add-w1700k-stock-rro-mib-live-mirror.patch`; it is included only in the offline `NpuRroMibLiveMirror-20260706` candidate, not the flashed baseline. LuCI/helper report: `work\W1700K_STOCK_RRO_MIB_LUCI_SOURCE_STAGED_20260704.md`, SHA256 `e11a6570c3fe4c1096b15b9b38e7f75eb04b708f921c0fecd058a0dddb825e8e`. Kernel source-gate spec: `work\W1700K_STOCK_RRO_MIB_KERNEL_SOURCE_GATE_SPEC_20260704.md`, SHA256 `d94c4bb660de635b52810f9f57b571ea34cb22dd5414bfecdbe1558d11708c2b`.
- Stock RRO MIB kernel patch stage: workspace patch `work\9999zzzzzzzzzzuuuuuuuuu-mt76-npu-add-stock-rro-mib-debugfs.patch`, SHA256 `6f313f614eb510c164d0c1c98487bce40194062f50f79a8f5d88ec88fcc75733`, is the historical staged source behind the current trimmed active patch `package\kernel\mt76\patches\9999n-mt76-add-w1700k-stock-rro-mib-live-mirror.patch`; the current active form keeps only the passive read-only register mirror.
- Stock PSE/PLE/aggregation monitor source-gate: `work\W1700K_STOCK_PSE_PLE_AGG_MONITOR_SOURCE_GATE_SPEC_20260704.md`, SHA256 `3296c5f2181b4cb73fe29ede97ebec70386968f2562f94e50c7f1edfdbc183ad`, staged passive debugfs producers `npu-stock-queue-pressure` and `npu-stock-agg-ba-limits` from stock `mt7990_dbg.ko`; this has since been replayed into the current active WSL source as `package\kernel\mt76\patches\9999o-mt76-add-w1700k-stock-queue-agg-live-mirrors.patch`. Selector-backed queue walks, WTBL, BA session selectors, and address-element selectors remain excluded.
- Stock PSE/PLE/aggregation kernel patch stage: workspace patch `work\9999zzzzzzzzzzuuuuuuuuuv-mt76-npu-add-stock-queue-agg-monitors.patch`, SHA256 `7a5f0bd7ad23cc4d2683f73d754902bec91250c48e610dcfcf1c5fece6e84e30`, is the historical staged source behind the current trimmed active patch `package\kernel\mt76\patches\9999o-mt76-add-w1700k-stock-queue-agg-live-mirrors.patch`; the current active form keeps only passive read-only queue and aggregation mirrors.
- Stock trans-map debugfs patch stage: workspace patch `work\9999zzzzzzzzzzuuuuuuuuuw-mt76-npu-add-stock-trans-map-debugfs.patch`, SHA256 `fc4ee039d86ecf2a5307f2665519d385de5c98b0159a61a8dad2fb34d7002958`, is the historical staged source for active source patch `package/kernel/mt76/patches/9999zzzzzzzzzzzz03-mt76-npu-add-stock-trans-map-debugfs.patch`. It remains documentation/debugfs visibility only, not runtime transport assignment.
- Stock passive monitor LuCI/helper source stage: workspace snapshots `work\w1700k-wlan-npu-mode`, SHA256 `3ce6864e744c0a194863e4335c68de96d7f5529f0411f7e7e65cfce1cefb5640`, and `work\w1700k-npu.js`, SHA256 `aff9369a5c332e1637849236ba1bb630ef0596694f84e1c804e281d63fc893c2`, were historical staging copies for monitor consumers. The active WSL helper/LuCI sources have since been promoted into the TXQueueGateClassifier image line.
- Stock hostadpt TX/RX ring contract: latest saved Ghidra output pins stock `hostadpt.ko` TX rings to two `0x400`-entry rings with `0xd0` descriptor stride, bases `0xa0/0xb0`, producer doorbells `0xa8/0xb8`, consumer readbacks `0xac/0xbc`, and a strict enqueue gate requiring descriptor bit0 clear plus more than five free slots. RX rings are two `0x200`-entry rings with `0x18` descriptor stride, bases `0x180/0x190`, and host consumer registers `0x18c/0x19c`. Report `work\W1700K_STOCK_HOSTADPT_TX_RING_CONTRACT_20260704.md`, SHA256 `b9fea5ec3bf7d43b1b86bf1824c37b5d9868a84d1db97bcf999a84a1fb8710fe`, recommends a future read-only `npu-stock-hostadpt-ring-contract` verifier before any additional packet-ownership change.
- Stock hostadpt ring-contract verifier patch stage: workspace patch `work\9999zzzzzzzzzzuuuuuuuuux-mt76-npu-add-stock-hostadpt-ring-contract.patch`, SHA256 `dba357a000b0c7489ca4375086c5402ba98889e0df21e4607164d47fd8f308e2`, is the historical staged source for active source patch `package/kernel/mt76/patches/9999zzzzzzzzzzzz04-mt76-npu-add-stock-hostadpt-ring-contract.patch`. The promoted TXQueueGateClassifier image includes the corresponding read-only `npu-stock-hostadpt-ring-contract` verifier.
- Post-power-loss Ghidra refresh: Windows-side headless Ghidra was revalidated with workspace-local appdata and full auto-analysis for stock `hostadpt.ko`, `npu.ko`, `mtk_pci.ko`, and `npu_bridge_cmd`. Report `work\W1700K_STOCK_POST_POWERLOSS_GHIDRA_REFRESH_20260704.md` records stable hashes and a no-new-delta verdict; WSL source replay remains blocked by the missing distribution.

## Detailed Offline Wi-Fi Recovery MLO Form-Sync Candidate Note

- Latest offline candidate while the router is disconnected: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\WiFiRecoveryMloFormSync-20260706\w1700k-wifi-recovery-mlo-form-sync-20260706-sysupgrade.itb`
- Sysupgrade SHA256: `0ab397509e47ff9f21ecc6c322b1a78bca09e29a2204d92b2fb05e31d5981f75`
- Workspace build report: `work\W1700K_WIFI_RECOVERY_MLO_FORM_SYNC_IMAGE_REPORT_20260706.md`, SHA256 `7f25078f1c677184d7d2cd92c45f1bde6de8a294509e0a8e338f0c61cc9484d2`
- FinalResult build report: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\WiFiRecoveryMloFormSync-20260706\BUILD_REPORT.md`, SHA256 `7f25078f1c677184d7d2cd92c45f1bde6de8a294509e0a8e338f0c61cc9484d2`
- Source fix: `feeds/luci/modules/luci-mod-network/htdocs/luci-static/resources/view/network/wireless.js` now has `w1700kSetFormValue()` and uses it when MLO/6GHz defaulting forces `encryption='sae'`, `ieee80211w='2'`, and `network='lan'`, preventing stale active form widgets from contradicting UCI and causing hidden invalid fields or repeated-save behavior.
- Verification: bundled Node syntax check passed; `make package/feeds/luci/luci-mod-network/compile V=s -j1` passed; full clean-PATH image build passed; FIT parse found kernel/FDT/rootfs; staged minified LuCI JS contains the form-sync helper; current-image invariant checker passed; package manifest includes LuCI/adblock/SQM/SoftEther/wpad/mt76 packages; rootfs staging contains no forbidden stock/vendor modules.
- Evidence hashes: current-image invariant check `4a9640e14a2822d5016c1eb0e313c5cc05f5a631492c35441dff7505c035fbad`; LuCI compile log `4d98133aa7accb213d912fa69779238ef87439ca6edeffab4364b927fed93e2f`; full clean-PATH build log `779a30a3b610cf9f98ca2c0683d9db00b2532fb57b20b773fa7510e424ba9e5f`; FIT metadata `9a467368968c0f78a0750ff38722beeb328f0d4f4ec88e2ce5d0e5c2d609e6e9`; `SHA256SUMS.txt` `c42d823bf160303f3489cdfa7438268c728c314917f4d36331c46c7508d8615a`.
- Boundary: offline build and static verification only. The live-tested Wi-Fi baseline remains `NoNPU-Diagnostic-20260614` until this candidate is flashed and proves mt7996 firmware init, PHY creation, all radio status, AP operation, MLO/LuCI behavior, and throughput.

## Detailed Previous Deferred-NPU-Probe Wi-Fi Recovery Candidate Note

- Previous offline candidate while the router is disconnected: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\WiFiRecoveryDeferredNpuProbe-20260706\w1700k-wifi-recovery-deferred-npu-probe-20260706-sysupgrade.itb`
- Sysupgrade SHA256: `ce91789ce02fb96b3f6077eef1ed9f5aad87c7f9147c14c5ea4dc1ed82f61b30`
- Current build report: `work\W1700K_WIFI_RECOVERY_DEFERRED_PROBE_IMAGE_REPORT_20260706.md`, SHA256 `23b8217b4c8fdb36b30c54286da66d974d60265082bcebe403af74b88f53ce20`
- FinalResult build report: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\WiFiRecoveryDeferredNpuProbe-20260706\BUILD_REPORT.md`, SHA256 `23b8217b4c8fdb36b30c54286da66d974d60265082bcebe403af74b88f53ce20`
- Superseded offline candidate: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\WiFiRecoveryNoMt76NpuCapabilityFix-20260706\w1700k-wifi-recovery-no-mt76-npu-capabilityfix-20260706-sysupgrade.itb`, SHA256 `198d7d249179371f70e58115f522e7dde92c6aa723de7547ee5ccc5b1f862ca4`
- Report: `work\W1700K_WIFI_NPU_FAILURE_OFFLINE_ROOT_CAUSE_20260706.md`, SHA256 `1ab98f5fae9be93a5524a6ee2a8068dabf5c9499c9ad191d304d399f063fb551`
- Offline source finding: the broken NPU image line initialized and threaded the experimental mt76 WLAN NPU path through PCI probe, DMA device ownership, DMA config/enable, and TX queue allocation before normal mt7996 firmware/PHY bring-up. The new normal-image path gates that code behind explicit `W1700K_EXPERIMENTAL_MT76_NPU=1`.
- Additional fix over the prior `WiFiRecoveryNoMt76Npu-20260706` candidate: the NPU helper JSON now reports `npu_module_params_supported=false` and marks modes 2/3/4 unavailable when the image lacks the experimental module parameters, so LuCI does not present unsupported NPU modes as selectable.
- Additional fix over the prior `WiFiRecoveryNoMt76NpuCapabilityFix-20260706` candidate: active patch `902-mt7996-defer-wlan-npu-init-out-of-pci-probe.patch` removes the probe-time `mt76_npu_init()` call from `mt7996_pci.c`, so even an experimental NPU compile cannot accidentally make pre-WED/pre-firmware NPU activation real through PCI probe.
- Current artifact verification: full clean-PATH image build passed, FIT parse passed, pre-PHY boundary checker passed, module autoload is plain `mt76` plus `mt7996e`, restored `mt76.ko`/`mt7996e.ko` strings contain none of the forbidden NPU mode symbols, and rootfs staging contains no stock vendor modules.
- Boundary: superseded by `WiFiRecoveryMloFormSync-20260706`; retained as prior recovery history.

## Detailed WiFi Recovery Invariant Gate Note

- Report: `work\W1700K_WIFI_RECOVERY_INVARIANT_GATE_20260706.md`, SHA256 `424cdc5c18e6104cce6aef223f697eed7474da41aeddeae99a26a99b3c87f60b`
- Checker: `work\w1700k_wifi_recovery_invariant_check_20260706.ps1`, SHA256 `aa3027e50a7468174623104e55a403992dc665470ed8dcf7193c4d8a53e6db4d`
- Checker output: `work\build-logs-20260706-wifi-recovery-invariants\wifi-recovery-invariant-check.txt`, SHA256 `cee0a8b676bfe0afa14385e004675cd5a72730d035debad06ac18bc61e0dcfe8`
- Compile logs: `wifi-scripts-compile.log`, SHA256 `51d02c523d198b98fa596b0f3766651fd39afa39215a6c747c782cd860eda485`; `iwinfo-compile.log`, SHA256 `81b1f1930fdc7245c2df917de40181b0f081993c63cc1997e95da7bd70b9bf9b`
- Result: `PASS`; the current gate verifies the MLO-form-sync image hash, exact nine-patch mt76 recovery boundary, absence of high-risk NPU patches `903`/`904`/`906`/`907`/`911`, plain `mt76`/`mt7996e` autoload, apply-time wireless validator wiring, LuCI MLO form-sync defaults, radio defaults, regdb policy, rootfs forbidden-module absence, shell syntax, and pre-PHY NPU boundary pass.
- Boundary: offline invariant and package-compile evidence only. No router flash, SSH, serial, LuCI, scan, association, MLO, throughput, or NPU runtime test happened because the W1700K is disconnected and in storage.

## Detailed Offline RRO/BA Experiment Note

- Offline experiment artifact while the router is disconnected: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\RroBaExperiment-20260706\w1700k-rro-ba-experiment-20260706-sysupgrade.itb`
- Sysupgrade SHA256: `70864996df82cfcd2e47193f5425aeaadfb8fa838f8ec36e765a929068b29a80`
- Report: `work\W1700K_RRO_BA_EXPERIMENT_IMAGE_REPORT_20260706.md`, SHA256 `275faa45f64a9fd321f9739fbd80455c5bbc921a5e1fb62872af8d564a34b967`
- Patch stack: `930-mt7996-honor-stock-rro-ba-status.patch`, `937-mt7996-retry-stock-rro-ba-status3.patch`, `938-mt7996-clean-rro-ba-status-style.patch`, and `939-mt7996-bound-rro-ba-retry-lifecycle.patch`.
- Offline verification: targeted mt76 compile passed, full clean-PATH image build passed, FIT parse found kernel/FDT/rootfs, module autoload files stayed plain `mt76` and `mt7996e`, expected `ba-status-*`/`wed-rro-status` markers were present, and forbidden stock modules/experimental WLAN-NPU parameter strings were absent.
- Source boundary after build: the four temporary RRO/BA patch files were removed again from the active mt76 patch directory, `make package/kernel/mt76/clean V=s` passed, and the active source patch set returned to the eight-patch no-mt76-NPU recovery boundary.
- Boundary: this is a future experimental image only. It is not the next flash candidate until the capability-fix recovery image proves live Wi-Fi boot. No router flash, SSH, serial, LuCI, MLO, client association, or throughput test happened.

## Detailed Pre-PHY NPU Boundary Gate Note

- Report: `work\W1700K_PREPHY_NPU_BOUNDARY_GATE_20260706.md`, SHA256 `9578a3e61f10d90f1782c8e5788608c68f9f662dd914978eb98b2faf914c825c`
- Checker: `work\w1700k_prephy_npu_boundary_check_20260706.ps1`, latest SHA256 `d755bcd444b6bfd8bf352e8afa8b1331e1d7c3fe195f39b1c3b4b14134ec14c9`
- Checker result on current WSL source: `PASS`.
- Current source evidence: active mt76 patch count is 9; no active `903`, `904`, `906`, `907`, or `911`; no active patch contains `wlan_npu_mode`, `mt76_npu_tx_active`, `npu_dma_dev`, `mt76_queue_dma_dev`, direct `dev->dma_dev = npu->dev`, or `MT7996_NPU_TX_RING_SIZE`; the mt76 Makefile keeps NPU compile flags behind `W1700K_EXPERIMENTAL_MT76_NPU=1`; prepared `mt7996/pci.c` has no probe-time `mt76_npu_init()` call; and rootfs autoload is plain `mt76` plus `mt7996e`.
- Root-cause refinement: the previous recovery source still had a source-level `mt76_npu_init()` call in `mt7996_pci_probe()`, but with `CONFIG_MT76_NPU` off it resolved to the inline no-op stub. The current source removes that probe-time call entirely. The failure boundary is making NPU activation real before WED init, firmware download, and PHY creation, then letting the same NPU-active state alter DMA/ring/page-pool behavior.
- Broken pre-PHY surfaces pinned from disabled patches: `903` adds `wlan_npu_mode` and makes pre-WED `mt76_npu_init()` real; `904` changes NPU ring/coherent allocation sizing; `906` spreads `mt76_npu_tx_active()` into DMA/queue/wiphy/forward-path logic; `907` changes DMA device selection and can swap `dev->dma_dev`; `911` adds stock RX-only mode but still depends on real pre-PHY NPU init.
- Re-entry policy: do not re-enable `903`, `904`, `906`, `907`, or `911` in a normal image. Any future NPU datapath implementation must separate non-invasive NPU discovery from post-firmware datapath activation so normal mt7996 PCI/WED/firmware/PHY bring-up is not altered.
- Ghidra state for this pass: MCP reported no running instances; headless fallback exists at `C:\Tools\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat`; prior headless stock mode-3 checklist was used for consistency, not as new live proof.

## Detailed Deferred NPU Probe Removal Source Note

- Report: `work\W1700K_DEFERRED_NPU_PROBE_REMOVAL_SOURCE_20260706.md`, SHA256 `fb06d19af48811c6f218bb96151516be5fde096ecc508fa07a7bd472960678fe`
- Workspace patch: `work\902-mt7996-defer-wlan-npu-init-out-of-pci-probe.patch`, SHA256 `d3d56a38f7f88d875bfe492f0f2498ff491d529a4a4b201d566fe57b2ed49d63`
- Active source patch: `/home/captain/w1700k-openwrt-build/fanboy-source/package/kernel/mt76/patches/902-mt7996-defer-wlan-npu-init-out-of-pci-probe.patch`
- Source behavior: deletes the unconditional `mt76_npu_init()` call from `mt7996_pci_probe()` and does not add any replacement NPU activation path. This prevents future experimental `CONFIG_MT76_NPU=y` builds from making pre-WED NPU activation real by accident.
- Verification: normal mt76 clean+compile passed; experimental `make package/kernel/mt76/compile W1700K_EXPERIMENTAL_MT76_NPU=1 V=s -j1` passed; then normal non-NPU mt76 clean+compile was rerun to restore staging/package state.
- Logs: `work\build-logs-20260706-deferred-npu\mt76-exp-compile.log` SHA256 `ae4ea4f5aa742fc5e68f3f84486a11058518b1a0214b415abb96606c59e0d213`; `work\build-logs-20260706-deferred-npu\mt76-normal-restore-compile.log` SHA256 `70e3d35e2ef087bd66d94c4db61334df4ea3d7db460bcbc2f3fea51355fb939a`.
- Post-restore proof: updated pre-PHY boundary checker passed; prepared `mt7996/pci.c` has no `mt76_npu_init` hit; restored `mt76.ko` and `mt7996e.ko` strings have no `wlan_npu_mode`, `npu_stock_txp_v3`, `npu_stock_fasttx_handoff`, `mt76_npu_init`, or `npu_dma_dev` hits.
- Boundary: no sysupgrade image was built from this new source patch yet. The next live candidate remains the already-built capability-fix recovery image unless a new image is intentionally built.

## Detailed Experimental Deferred NPU Activation Source Note

- Report: `work\W1700K_EXPERIMENTAL_DEFERRED_NPU_ACTIVATION_SOURCE_20260706.md`, SHA256 `725fc3038d676969a920335d2c8b22637e5adc60ba49108f835c02d620cf15ee`
- Experimental patch: `work\experimental-deferred-npu-20260706\903-mt7996-add-post-firmware-wlan-npu-activation.patch`, SHA256 `811b9814d7f80db3a6e85742b6f03f399f6879fb72a78a057865d25586d71d7f`
- Result: the experimental deferred WLAN-NPU activation scaffold applies and compile-checks with `W1700K_EXPERIMENTAL_MT76_NPU=1`.
- Restore proof: the temporary `903` patch was removed from the active mt76 patch directory, normal non-NPU mt76 clean+compile passed, and the pre-PHY boundary checker passed again.
- Active mt76 patch count after restore: 9.
- Current active normal-source patch set: `003`, `900`, `901`, `902`, `926`, `9997`, `9999`, `9999a`, `9999e`.
- Build logs: `work\build-logs-20260706-deferred-npu-activation\mt76-exp-compile-3.log` SHA256 `b500d25fa8520189e04f9588d1c53d0ef5ebd0c35ea7d7cc68aede4f07dade50`; `work\build-logs-20260706-deferred-npu-activation\mt76-normal-compile-after-exp.log` SHA256 `a09abc9b2e5ce7482dc2fc2a085811401f8fff5f71f5b68886b7966f6acccd53`.
- Boundary: this is source-only evidence while the W1700K is disconnected and in storage. No sysupgrade image was built from this scaffold, no flash happened, and no live Wi-Fi/NPU behavior was tested.
- Re-entry rule: normal recovery images must keep `CONFIG_MT76_NPU` and `CONFIG_MT7996_NPU` disabled unless an explicit test image is requested. The deferred scaffold is useful for later mode-3 experiments, not for claiming stock-equivalent hostadpt/TXFREE/RRO parity.

## Detailed WiFi Scan-Pinned Offline Image Note

- Report: `work\W1700K_WIFI_SCAN_PINNED_IMAGE_REPORT_20260706.md`, SHA256 `e26525465cb83b3aa3c6ab8ac198fc141a45930b6e4591a8a5374d7498f15b74`
- FinalResult folder: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\WifiScanPinned-20260706`
- Image: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\WifiScanPinned-20260706\w1700k-wifi-scan-pinned-20260706-sysupgrade.itb`
- Image SHA256: `3fa2703ea1247d5eddd4debec9f8ec45b22a7830b60e175f283fb6ca997e516b`
- Source root: `/home/captain/w1700k-openwrt-build/fanboy-source`
- Source commit: `5575e4a97f119f682223a090c4a78c0913f906f5`
- OpenWrt profile: `gemtek_w1700k-ubi`; source config has `CONFIG_TARGET_airoha_an7581_DEVICE_gemtek_w1700k-ubi=y`.
- Scope: `package/network/utils/iwinfo/patches/101-nl80211-pin-temp-scan-iface-to-radio.patch` now skips existing-interface reuse for UCI-backed `radioX` scans and forces the temporary STA scan interface to be pinned with `NL80211_ATTR_VIF_RADIO_MASK`. This targets the observed scan/offline failures after AP/MLO SSIDs are present.
- Verification: `iwinfo` clean/compile passed; full OpenWrt image build passed with sanitized Linux PATH; LuCI JS `node --check` passed; backend validator `sh -n` passed; `work\test_w1700k_validator_fixture.sh` passed all width/MLO fixture cases; FIT metadata parsed and contains kernel, W1700K DTB, rootfs, and `config-1`.
- Build note: the first full image build failed only because WSL inherited a Windows PATH entry containing parentheses and broke the image `mkimage` shell command. The rerun with Linux-only PATH passed.
- Boundary: this supersedes `MloEapolTokenSafe-20260706` as the newest offline candidate, but not the live-tested `NoNPU-Diagnostic-20260614` baseline until flashed and tested. The W1700K is disconnected and stored; no live router work happened.
- Flash caution: this image is `gemtek_w1700k-ubi`, not `ubi2`; recheck actual device UBI layout before flashing.

## Detailed WiFi Scan + NPU TX-Map Offline Image Note

- Report: `work\W1700K_WIFI_SCAN_NPU_TXMAP_IMAGE_REPORT_20260706.md`, SHA256 `c9a9b811fa009e9ab3bf1d0668fecf4cb2fecce6b1558acfa9256cf834bd1bb4`
- FinalResult folder: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\WifiScanNpuTxMap-20260706`
- Image: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\WifiScanNpuTxMap-20260706\w1700k-wifi-scan-npu-txmap-20260706-sysupgrade.itb`
- Image SHA256: `6b5f952bfb2b4d755aaf1af97095120af7dbb236c8d74298c0a7e0a5071e96b1`
- Source root: `/home/captain/w1700k-openwrt-build/fanboy-source`
- Source commit: `5575e4a97f119f682223a090c4a78c0913f906f5`
- OpenWrt profile: `gemtek_w1700k-ubi`; source config has `CONFIG_TARGET_airoha_an7581_DEVICE_gemtek_w1700k-ubi=y`.
- Scope: carries the `iwinfo` radio-pinned scan fix plus expanded read-only stock NPU TX/hostadpt parity markers in `w1700k-stock-npu-parity-map`.
- Stock evidence added to debugfs strings: `stock_toHostadpt_tx_descriptor_len=0x4c`, `stock_hostadpt_tx_ring_depth=0x400`, `stock_hostadpt_tx_desc_stride=0xd0`, `stock_hostadpt_low_water_free_desc=5`, `stock_ra_sw_nat_hook_tx_proto=0x7274`, `stock_ppe_wifi_fasttx_actdp_ranges=6-13,15-22,0x86-0x8d`, `stock_tx_token_release_before_hostadpt=observed_not_ported`, and `stock_hostadpt_reclaim_dma_unmap_and_kfree=observed_not_ported`.
- Verification: `iwinfo` clean/compile passed; mt76 clean/compile passed; full OpenWrt image build passed with Linux-only PATH; FIT metadata parsed and contains kernel, W1700K DTB, rootfs, and `config-1`; `mt76.ko` string proof found all new NPU TX-map markers.
- Boundary: this supersedes `WifiScanPinned-20260706` as the newest offline candidate, but not the live-tested `NoNPU-Diagnostic-20260614` baseline until flashed and tested. The W1700K is disconnected and stored; no live router work happened.
- Flash caution: this image is `gemtek_w1700k-ubi`, not `ubi2`; recheck actual device UBI layout before flashing.
- Handoff: `work\W1700K_OFFLINE_HANDOFF_20260706.md`, current SHA256 `5d5fa2d16f303750275efcb7db8a51e8ae70c7aba7a1c2e6adea8df9395888ec`.

## Detailed NPU Ring-Contract Offline Image Note

- Report: `work\W1700K_NPU_RING_CONTRACT_IMAGE_REPORT_20260706.md`, SHA256 `fd265bc20498fdf63e3cb3a00d73202bf8e9f7cf11695ceed2d728b0e76dbbf4`
- FinalResult folder: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\NpuRingContract-20260706`
- Image: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\NpuRingContract-20260706\w1700k-npu-ring-contract-20260706-sysupgrade.itb`
- Image SHA256: `dddfcc07927a44f816fda5c8172412277d398369327df868c905cbd700563501`
- Source root: `/home/captain/w1700k-openwrt-build/fanboy-source`
- Source commit: `5575e4a97f119f682223a090c4a78c0913f906f5`
- OpenWrt profile: `gemtek_w1700k-ubi`; source config has `CONFIG_TARGET_airoha_an7581_DEVICE_gemtek_w1700k-ubi=y`.
- Scope: carries the Wi-Fi scan-pinned recovery line and expands `w1700k-stock-npu-parity-map` with stock hostadpt TX/RX ring-contract constants from the Ghidra-backed hostadpt report.
- Added stock evidence: TX ring count `2`, depth `0x400`, stride `0xd0`, base regs `0xa0/0xb0`, producer regs `0xa8/0xb8`, consumer readback regs `0xac/0xbc`; RX ring count `2`, depth `0x200`, stride `0x18`, base regs `0x180/0x190`, NPU producer reset regs `0x188/0x198`, host consumer regs `0x18c/0x19c`.
- Verification: mt76 clean/compile passed; full OpenWrt image build passed with Linux-only PATH; FIT metadata parsed; updated Wi-Fi recovery invariant gate passed with `33` checks; LuCI JS syntax check passed; backend validator syntax and fixture tests passed; rebuilt `mt76.ko` string proof found all new ring-contract markers; `vmlinux` string proof found `stock_hostadpt_irq_index` and live TX/RX register labels.
- Boundary: this supersedes `WifiScanNpuTxMap-20260706` as the newest offline candidate, but not the live-tested `NoNPU-Diagnostic-20260614` baseline until flashed and tested. It is read-only visibility, not stock packet-ownership parity. The W1700K is disconnected and stored; no live router work happened.
- Flash caution: this image is `gemtek_w1700k-ubi`, not `ubi2`; recheck actual device UBI layout before flashing.

## Not Fully Cloned Yet

- No stock `npu.ko`, `hostadpt.ko`, vendor `wpad`, vendor hostapd, `wapp`, `mapd`, or cloud/provisioning binaries are intentionally shipped.
- Full host-adapter TX rings are not byte-equivalent yet; descriptor publish, reclaim, toHostadpt hook-boundary state, immediate doorbell publish/readback telemetry, doorbell-readback-gated auto ownership, lifecycle-sequence-gated auto ownership, an opt-in hostadpt SKB ownership mode, per-group auto-arm ownership gating, pre-hostadpt token release with active-first local accounting, return-0 cleanup accounting, TXFREE, descriptor/SKB, token-quarantine auto-disarm tripwires, qentry token-quarantine marking including no-pending, duplicate-token, reason-preserving branches, cache-reset quarantine marking, reason-aware owner gating, enqueue failure-path accounting, source-only compiled TX state-machine/descriptor-byte/equivalence/doorbell-verifier auto-owner gates, source-only TX nonlinear/scatter shape guard, stock TX queue source-gate aliases, and source-only TX queue gate classifier counters are now present, but ownership mode and verifier behavior still need image build plus live stress proof.
- Stock mailbox/provider parity is not fully proven live. The current image exposes stock-mode3 mailbox/provider readiness through helper/LuCI, and the latest Ghidra refresh documents stock hostadpt/NPU provider symbol and register contracts, but exact PCIe TX queue selection, physical hostadpt base publication under load, TX buffer-space mailbox value/failure equivalence, RX event/TXDONE ownership, and true `glb_npu_trans1/trans2` pointer ownership still need live capture.
- Full SKB/bufid lifecycle and token table behavior is not byte-equivalent yet; stock-shaped SKB/BufID allocation/free/fail/abnormal counters are now present and tied into auto-owner fail-closed gating, but byte-identical stock token-entry memory layout and live stress proof remain open.
- Full RRO equivalence is not complete. The current image maps stock-shaped RRO indication counters, stock `refill_cnt`, stock `larger_winsize_cnt`, owner-read `addition_read_cnt`/`max_read_cnt`, proxy `fp_*` fields, RRO/BA verdict visibility, a bounded RRO reset guard, and MLO BA-link setup/status/retry/delete ownership visibility to live OpenWrt equivalents. Byte-equivalent stock free-pool ring ownership/semantics and live load validation remain open.
- Full scatter handling is not byte-equivalent yet; successful stock-linearized scatter RX now reuses descriptor backing buffers like stock instead of freeing/remapping them, incomplete over-retry cleanup now recycles completed DONE fragments and publishes the host CPU index, stock-shaped scatter failure samples are recorded, first-fragment info is preserved for downstream classification, scatter linearization uses stock's remaining-length copy clamp with contract counters, and source-compiled patch19 consolidates those proofs in `npu-stock-hostadpt-scatter-skb-lifecycle`. Full nonlinear scatter byte parity, every `_fromHostadptPktHandle_hook()` branch, image promotion, and live proof are still open.
- Full TX doorbell ownership and descriptor bookkeeping around the NPU is not byte-equivalent yet; immediate publish, debugfs live readback comparison, auto-owner doorbell safety gating, and source-only doorbell/verifier fail-closed auto-owner integration are implemented, but live load proof and any required byte-equivalent ownership changes remain open.
- Full `pci_dma_rx_process_hostadpt()` and `_fromHostadptPktHandle_hook()` behavior is not cloned; the poll/process boundary is now mirrored, type-5 metadata projection is recorded including projected `local_24[0]` and raw-vs-normalized deltas, mt76 `skb->cb[0]` is rebuilt, linear RX type-check/drop is gated before mt7996 delivery, stock-normalized RXINFO is pre-cached before delivery with explicit bit21 raw/present/added counters, nonlinear RXD DW0 packet-type gating is present, successful stock-linearized scatter RX reuses descriptor backing buffers on refill, incomplete scatter over-retry cleanup recycles completed DONE fragments, scatter failure branches preserve stock-shaped samples, scatter RX returns the first-fragment info word like stock, scatter linearization uses stock's remaining-length copy clamp with contract counters, post-fill local8 decode/correlation probes, default-off type-5 RX status projection, default-off `RX_FLAG_8023` predecode projection, default-off exact sideband direct-write, and stock bus-fate gate counters are present, optional/manual and conservative auto-armed nonzero bus-fate consume are built, the W1700K hook-bit25 callback slot is proven NULL, and the from-hook/type-5 delivery boundary is counted, but the exact sideband direct-write path is not live-proven or default-on, full nonlinear scatter byte parity is still open, and live proof for enabling projection/direct-write behavior is still not cloned.
- Full RXDONE interrupt disable/poll/re-enable ownership is now in the latest image with per-ring poll-owner state and NPU poll-completion re-enable, but it is not yet live-validated. Schedule-prep, complete-done-zero, RX owner-clear ordering, RX CPU-index accounting, stock ring0/ring1 scheduler diagnostics, invalid scheduler-contract fail-closed behavior, and stock trans-slot presence/missing/enforced scheduler counters are aligned or logged. The missing-trans return path remains default-off behind `npu_stock_hostadpt_sched_require_trans` until live ring1 opt5/trans2 mapping is proven.
- Full ping-pong packet fate is not cloned; a default-off DstPort copied-skb handoff exists for the proven reason-`0x19`/`foe_ext`/ACTDP/DstPort subset and is gated to stock-return0 branches, stock VirIfIdx branch classification/DstPort normalization is built, stock expected branch-fate side effects are recorded, stock `PpeRxHandler` immediate-return telemetry is exposed, and a default-off stock-modeled `br-lan` FDB bridge handoff now exists. The bridge handoff enforces the stock `_left_to_right_test_mode == 1` branch through explicit `npu_stock_pingpong_left_to_right_mode=1`; mode `2` branch buckets, stock/current `sk_buff` layout mismatch, source-port-5 dst/refdst/output/sk prerequisites, an opt-in copied-skb source-port-5 `dst_output` handoff, a default-off copied-skb source-port-0 `netif_rx` handoff, and a default-off original-skb source-port-0 `netif_rx` handoff are exposed. The bridge and mode-2 source-port-5 handoffs still copy rather than transfer the original skb, the source-port-0 original handoff uses current-kernel `DstPort[0xe2]` and L2 classification, and true `GET_HIR()==10` equivalence remains unproven. L2TP, speed-test, ECNT, TSO callback, black-IP, final DstPort side effects, and full byte-equivalent consume/redirect/drop behavior remain open.
- Full FastTX equivalence is not proven under all traffic modes.
- Full TXFREE/token equivalence is not proven under stress; v0/v1/v2 and v4/v5 parse paths, NPU-only v5 stock-layout dispatch, RX-byte-bounded stock v4/v5 parsing, wrong-version handling, short/leak-only mismatch accounting, descriptor/TXWI token handshake telemetry, return-0 cleanup accounting, delayed TXWI cache return, deferred token IDR removal after SKB consumption, fail-closed TXWI quarantine on deferred release failure, explicit not-ready token quarantine, per-phy active token counters, hostadpt qentry quarantine marking, cache-reset qentry marking, no-pending qentry marking, duplicate deferred token quarantine marking, qentry quarantine reason preservation, deferred token NULL result classification, deferred TXWI quarantine flush accounting, stock-shaped token freelist shadow counters, freelist-error auto-owner gating, deferred-token pending/latency stress counters, pre-claim vs post-claim release-error split, TXQ NULL quarantine equivalent to stock `mtk_tk_get_tx_q()` failure, packet-identity equivalence verifier, token/freelist coverage matrix reporting, and non-owning stock-offset token-entry shadow/qentry linkage are now present in the promoted image line. This still does not prove byte-identical live ownership/callback equivalence under stress.
- Full RRO equivalence is not byte-equivalent or live validated; MLO BA-link session ownership proof is image-built but still needs flash/live validation.
- Advanced WiFi 7 controls such as STR-MLMR, EMLMR, SRS, dynamic reconfiguration, TID-to-link mapping, and AFC/standard-power 6 GHz are not exposed as confident toggles.

## Patch Inventory Snapshot

- `package/kernel/mt76/patches`: 325
- `target/linux/airoha/patches-6.18`: 170
- `package/firmware/wireless-regdb/patches`: 3
- `package/network/utils/iwinfo/patches`: 2
- Total audited rows seen in source checkout: 553
- `mt76-hostadpt-dma` rows: 184
- `mt76-rro` rows: 13
- `mt76-txfree-token` rows: 27
- `mt76-pingpong` rows: 16
- `npu-capture-helper` rows: 1
- `npu-control-surface` rows: 18
- `rro-ba` rows: 20

## Future Session Rules

1. Read this file first.
2. Then read `W1700K_STOCK_PORT_LOGGING_SESSION_20260630.md`.
3. Then read `W1700K_STOCK_PORT_FUTURE_REFERENCE.md`.
4. Then read `W1700K_STOCK_PORT_CANONICAL_COMPARISON.md`.
5. Then read `W1700K_STOCK_PORT_LOGGING_SESSION_20260625.md` and `W1700K_STOCK_PORT_LEDGER.md` when exact patch/image history is needed.
4. Do not call telemetry a clone. Telemetry proves where to dig; it is not packet ownership.
5. Mark behavior as `DONE` only when it is in a completed image or the report explains why source-only is enough.
6. Record image filename, SHA256, source commit, patch counts, and live router counter deltas.
7. Promote the next smallest stock-equivalent behavior with evidence. Grand rewrites are where sanity goes to die.

## Current Production Baseline - 2026-07-11

- Current live-tested image: `w1700k-production-20260710-sysupgrade.itb`.
- FinalResult folder: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\ProductionCleanupLive-20260711`.
- SHA256: `910880eed3b4289186cdccd6e4d3ba739984423d300c964201845407a91b127c`.
- Source commit/profile: `5575e4a97f119f682223a090c4a78c0913f906f5`, `gemtek_w1700k-ubi`.
- Full report: `work\W1700K_PRODUCTION_CLEANUP_LIVE_REPORT_20260711.md`.
- Production verifier: `work\W1700K_PRODUCTION_IMAGE_VERIFICATION_20260710.txt`.
- Full patch audit: `6295` files; active/local `79` with zero structural issues; disabled experimental `322` with zero structural issues.
- Full Ghidra analysis completed on the final unstripped kernel and `mt7996e.ko`: kernel `36843` functions / `394620` symbols; module `532` functions / `4230` symbols.
- Exact-board-gated flash passed and boot ID changed.
- Final state-aware synthetic run: `21/21` passed. It proved physical radio 0 at 2.4 GHz, radio 1 at 5 GHz EHT80 and EHT160, radio 2 at 6 GHz EHT320, 5+6 GHz MLO, tri-band MLO, backend rejection rules, production NPU/PPE baseline, service health, and no fatal kernel signature.
- Original wireless configuration restored after testing; live AP returned to `The Internet Of All Time`, radio 1, channel 100, 160 MHz.
- This baseline supersedes prior offline/live image candidates for normal use.
- No external client, throughput, routed-load, VPN-tunnel, SQM-load, or long-duration stress test was performed in this unattended pass.
- Do not treat this as stock hostadpt datapath parity. Dedicated packet/ring ownership, TX lifecycle, SKB/bufid/scatter ownership, doorbell/TXFREE/token equivalence, RRO/free-pool ownership, BA mutation, and ping-pong packet fate remain open.

## Current Experimental Split-DMA Baseline - 2026-07-11

- Current live-validated experimental image: `w1700k-experimental-splitdma-mode3-v14-mailbox-trace-20260711-sysupgrade.itb`.
- SHA256: `855ae5559d59b40eb215226501ebaac7856b6e7e6b3f31716ff8cdf80db1f0df`.
- FinalResult: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\SplitDmaMode3V14MailboxLive-20260711`; `SHA256SUMS.txt` SHA256 `c630460fc27e295fc16c7778692c2b71c492ecd2fb9372b3ba3425dc95cf74d8`.
- Source commit/profile: `5575e4a97f119f682223a090c4a78c0913f906f5`, `gemtek_w1700k-ubi`.
- Full report: `work\W1700K_SPLITDMA_V14_MAILBOX_TRACE_REPORT_20260711.md`.
- Default router state remains mode `0`; split-DMA mode `3` is explicit and experimental.
- v10's NAPI-before-IRQ fix and v13's hostapd sentinel/token-balance fixes remain present. v14 adds read-only live WLAN mailbox tracing in the Airoha NPU driver.
- Mode 0 passed `22/22`; mode 3 passed `23/23`; the extra TX probe and two module reload cycles passed.
- Token alloc/release balance `1` matched current token count `1`; producer/consumer pairs matched and TX pending was zero.
- Provider mailbox proof passed with zero set/get errors: TX ring mask `0x000d`, TX buffer mask `0x14a5`, RX/TXDONE mask `0x0001`, RXDESC mask `0x1da5`, and combined sequence verdict `1`.
- Full corpus audit covered `6299` patches with zero active/local or disabled-experimental structural issues. Strict checkpatch has no active errors or warnings; one inherited PCS `udelay(100)` advisory remains.
- Final router state: board `gemtek,w1700k-ubi`, autoload `mt7996e`, runtime mode `0`, validator exit `0`.
- All final acceptance testing was synthetic and router-local. Broadcast TX did not traverse NPU TX rings; eligible unicast load proof remains open.
- The normal production baseline remains `ProductionCleanupLive-20260711`; use this v14 line only when explicitly testing split-DMA mode 3.
- Do not claim exact stock hostadpt/TXFREE/RRO parity. Packet/SKB/bufid/scatter ownership, descriptor/doorbell mutation, unicast token/TXFREE load equivalence, exact stock `trans1/trans2` pointer ownership, RRO free-pool/BA mutation, and ping-pong packet fate remain open.

## Current Live NPU Development Baseline - 2026-07-11 v20b

- Current live/promoted NPU candidate: `w1700k-stock-v5-txfree-v20b-20260711-sysupgrade.itb`.
- SHA256: `f8ed35010863b03c75c00cc2173d4f52ab460644edd4ef8f62d18a9af4f7af66`.
- FinalResult: `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\StockNpuTransTxfreeV20B-20260711`.
- Full report: `work\W1700K_STOCK_NPU_TRANS_TXFREE_V20B_LIVE_REPORT_20260711.md`.
- Source/profile: `5575e4a97f119f682223a090c4a78c0913f906f5`, mt76 `59676919ea408b0b13a9d23f2e2e1a1ab407fba1`, `gemtek_w1700k-ubi`.
- v20b adds primary/secondary transport-slot lifecycle enforcement and bounded stock-layout TXFREE parsing for NPU-active version-5 notifications.
- Mode 0 passed live; mode 3 passed `29/29` plus two PCI reload cycles. Final runtime is restored to mode `0`.
- No kernel warning/fatal signature occurred on the accepted v20b run.
- Residual TXFREE evidence is explicit: `128` stock messages, `185` token words, `3` bounded short/count-mismatch notifications, and `38` missing-token observations.
- The user separately observed gigabit-link saturation on pre-v19 v17 mode 3. Do not present that as an exact v20b throughput benchmark.
- v20b supersedes v17/v19 as the current live NPU development baseline, but exact stock packet-path parity remains open.
- The promoted FinalResult bundle contains 61 checksum-verified evidence files.

## Current v21 Throughput Evidence - 2026-07-11

- On the currently flashed v21 TXFREE diagnostic build, the user observed throughput saturating the gigabit LAN link.
- Immediate router readback showed mode `0`: lifecycle `inactive-clean`, `npu_active=0`, `820` standard TXFREE notifications, and zero missing-token/truncation/count-mismatch counters.
- Treat this as strong mode-0 datapath capability evidence, not a controlled benchmark and not mode-3 proof.
- The active mode-3 correctness target remains the deterministic short TXFREE receive: header `RX_BYTE=128`, descriptor/SKB length `64`, expected token count `41`, freed count `18`, queue `19`. Descriptor scatter metadata must be captured and reconciled before changing dequeue ownership.

## Current v26 TXFREE/Token Evidence - 2026-07-11

- v23 descriptor continuation tracing closed the scatter hypothesis: the short
  TXFREE messages were standalone descriptors, and following descriptors were
  unrelated packets.
- Ghidra proved the OpenWrt firmware descriptor writer uses total bits 28:15,
  current bits 14:1, and LAST bit 29. Do not apply stock hostadpt masks.
- The guarded common-enqueue firmware patch produces complete TXFREE lengths;
  exact firmware SHA256 is
  `609415cec9237f0434df35606d3f4d5d12bea145b831797d0fefea9620278ef8`.
- v26 token classification proved all `122` missing lookups came from the
  first three foreign/bootstrap batches (`51 + 30 + 41`). There were zero
  duplicate and zero unexplained missing releases.
- Normal runtime completions matched host allocations and released cleanly.
  Mode-3 balance was `18` allocations, `17` releases, current count `1`.
- v26 image SHA256 is
  `be177ab1bb329ac8c2f57dc9ff6bf85d2b887884ebccd9183955c68c3c14b6f1`;
  mode 0 and mode 3 passed, and the router was restored to mode 0.
- Do not promote v26 yet. It is an instrumented candidate. The remaining gate
  is eligible unicast client traffic with a controlled mode-0/mode-3
  throughput comparison.
- Detailed report:
  `work\W1700K_NPU_TXFREE_FIRMWARE_TOKEN_LIFECYCLE_V26_REPORT_20260711.md`.

## Current NPU Roadmap and ETA - Post-v26

- Roadmap: `work\W1700K_NPU_ROADMAP_ETA_POST_V26_20260711.md`.
- SHA256: `3b24844c797f0d941dc6ce147969520fd4df1738fb8b4fd91d97ea3e3e329bdc`.
- Next gate: same-topology eligible-unicast mode-0 versus mode-3 throughput,
  with three runs per mode and simultaneous token/TXFREE/ring/CPU/NPU capture.
- Verdict ETA after client availability: `2-4 hours`.
- Practical production ETA: `1-2 focused days` if mode 3 already passes;
  `3-6 focused days` if one performance fix is required; `7-12 focused days`
  for multiple ownership boundaries.
- Optional full stock-equivalence work adds `5-10 focused days` and is not
  required if the upstream datapath plus narrow verified fixes meets the
  throughput and reliability gates.

## Current Bootstrap Token Ordering Evidence - 2026-07-11

- Phase 2 bootstrap completion safety is closed for the observed v26
  firmware/build. Detailed report:
  `work\W1700K_NPU_BOOTSTRAP_TOKEN_ORDERING_REPORT_20260711.md`, SHA256
  `8dc91b3dc9b3242374ba12c4d37b7efcf576580ea18cf2bd59d78cf06ca88f6d`.
- Three accepted persistent-tri-band boots passed. The two settled captures
  both recorded `122` foreign never-allocated completions, zero duplicates,
  zero unexplained missing releases, and zero active host-token collisions.
- Exact first-event ordering is not fixed: host token `8192` allocated first
  in one settled boot, while the first 51 foreign completions arrived first in
  the repeat. Do not claim that all bootstrap batches always drain before any
  host allocation.
- The observed safety property is narrower and reproducible: the foreign set
  never completed active host token `8192`, and host token `8193` was not
  allocated until after the final foreign event.
- Do not alter the upstream token range or add startup quarantine without
  contradictory live evidence. Keep failed lookup non-mutating and retain only
  aggregate foreign accounting in a production image.
- Updated roadmap SHA256 is
  `046eddb501c2566c907102d4a7e0cb6ffb9622155c102e51b1de0e3fe56f1686`.
- Next gate remains client-assisted same-topology eligible-unicast mode-0
  versus mode-3 throughput.

## Current Hostadpt Ownership Boundary and ETA - 2026-07-11

- Stock `hostadpt.ko` transfers SKB/payload DMA ownership into a dedicated
  `0xd0`-stride host-adapter descriptor after detaching the vendor token entry,
  then reclaims/unmaps/frees it from the firmware consumer index.
- The OpenWrt MT7996 NPU firmware contains the matching host-adapter poll and
  `0x4c` TX-metadata copy machinery.
- Current mt76 uses split ownership: descriptor lifetime follows the NPU
  consumer index, while SKB/payload/TXWI lifetime remains token/TXFREE-owned.
- Treat that mismatch as a hypothesis, not a defect. The next implementation is
  a bounded, read-only consumer-versus-TXFREE ordering probe.
- The user has again observed mode-0 saturation of the gigabit Ethernet link.
  General Wi-Fi forwarding is therefore not the current blocker; mode-3
  eligible-unicast equivalence remains the decisive gate.
- Current roadmap:
  `work\W1700K_NPU_ROADMAP_ETA_AFTER_GIGABIT_CONTROL_20260711.md`.
- Roadmap SHA256:
  `f24d0857f5985754b5e3b0610115bc920c58374f30a1be24124adf5853392a27`.
- Read-only live confirmation: board `gemtek,w1700k-ubi`, boot ID
  `6bdc48d1-d433-4812-aca5-c8cbb27887fd`, and `wlan_npu_mode=0`.
- ETA: `0.5-1 day` for the next diagnostic image, `2-3 focused days` best case
  to a practical image, `4-7 days` with one causal ownership fix, and `8-12`
  days if multiple packet-path boundaries are involved.

## Current v27 Consumer/TXFREE Evidence and Roadmap - 2026-07-11

- v27 image: `work\w1700k-npu-order-v27-20260711-sysupgrade.itb`, SHA256
  `0870402299746240ea2485ea0d3398e516340a3e5d74a9c882c8928a7d19fbf7`.
- Detailed report:
  `work\W1700K_NPU_CONSUMER_TXFREE_ORDER_V27_REPORT_20260711.md`.
- Report SHA256: `97cc80b488633563953f17f5eb2b54e35179ed603a178435d09521e08d82ab6c`.
- Mode 0 passed 26 tests; mode 3 passed 29 tests, the extra probe, and two PCI
  reload cycles. The router was restored to mode 0 with exact wireless state.
- Mode 3 recorded 19 NPU enqueues and consumer-index observations. All 19
  consumers preceded TXFREE; 18 later received matching TXFREE and token 8192
  on PHY 0 remained outstanding. Invalid, untracked, duplicate, and mismatch
  counters were zero.
- The result is partly structural because mt7996 cleans the NPU consumer index
  before parsing TXFREE in the same callback. It is correlation evidence, not
  by itself proof that early token release is correct or faster.
- Stock Ghidra decompilation shows FIFO token allocation/release: request from
  free-list head and append released entries at the tail. Current mt76 can
  immediately reuse the lowest free ID. Do not release OpenWrt tokens at
  consumer advance until late TXFREE aliasing is resolved.
- Updated roadmap:
  `work\W1700K_NPU_ROADMAP_ETA_POST_V27_20260711.md`.
- Roadmap SHA256: `d002ca47ba6c15ffee99c369121bffc1c02900ad008315d20bbfc8122c87c3e3`.
- Current ETA: `1-2 focused days` best case, `3-6 days` with one causal
  token/ownership fix, and `7-12 days` if multiple packet-path boundaries are
  causal. Optional exhaustive stock parity adds `7-15 focused days`.

## Current Stock-Copy/Remap Finding and v28 Roadmap - 2026-07-11

- Full Ghidra analysis of the stock RV32 NPU firmware and normalized function
  fingerprints mapped `248/258` stock functions to exact-shape OpenWrt
  homologs.
- Stock copies eligible payloads into an NPU-local 0x800-byte buffer and
  replaces the detached host token with an NPU-local token. OpenWrt instead
  forwards the host DMA address and host token directly.
- OpenWrt's live token split (`token_start=8192`) provides disjoint host and
  NPU-local namespaces for a guarded experiment. This supports a default-off
  v28 copy/remap mode; it does not justify early release on the existing direct
  path.
- New roadmap:
  `work\W1700K_NPU_ROADMAP_ETA_V28_STOCK_COPY_20260711.md`.
- Roadmap SHA256:
  `411aaf960ca628b03109125ea52895da0c0d517f25e856d750824b39d98976d8`.
- Best-case production candidate ETA is `2-3 focused working days`; one
  additional correction is `4-6 days`; multiple boundaries remain `7-12
  days`. Exhaustive parity is a separate `10-20 focused day` research track.

## Current v28 Stock-Copy State and ETA - 2026-07-12

- v28 image: `work\w1700k-npu-stock-copy-v28-20260711-sysupgrade.itb`, SHA256
  `9bb8d7d849ab73cc1b33d1c18ef30bf9f97bf191e003f70a8584f514af4963c2`.
- v28 implements a default-off, fail-open stock-style copy/remap path for
  eligible mode-3 packets. It separates low NPU-local TXFREE status from high
  host-token ownership and completes confirmed remaps at consumer advance.
- Offline build/FIT/rootfs/firmware/Ghidra verification passed. Default-off,
  ordinary mode 3, stock-copy mode 3, repeated stock-copy stress, tri-band/MLO,
  exact restoration, and two-cycle PCI reload tests passed.
- Repeated stock-copy stress reached 54 requests and 54 consumer completions,
  with 53 low-token TXFREE observations, a bounded local outstanding count of
  one, zero host-token balance/current, and zero fallback or missing callback.
- The latest user-observed transfer saturated gigabit LAN, but its NPU submode
  was not captured. Controlled three-mode A/B classification remains open.
- Detailed report:
  `work\W1700K_NPU_STOCK_COPY_V28_REPORT_20260712.md`, SHA256
  `6159a2c7993025e6f1bb4f7b721e80e7065384e3a856adce984c9e3f24c38ac5`.
- Current roadmap:
  `work\W1700K_NPU_ROADMAP_ETA_POST_V28_20260712.md`, SHA256
  `ceee21e64e49c45c8ca0020190841ad7e785a0d4a28b9782faa578c9699f9a9e`.
- Practical candidate ETA: about one focused day. Polished promotion ETA:
  1.5-2.5 focused days. v28 is validated but not yet promoted.

## Current v29c Production-Control State - 2026-07-12

- Promoted image:
  `work\w1700k-npu-production-control-v29c-20260712-sysupgrade.itb`, SHA256
  `0a92ce0d06be0286bc59b57ef69b2d320d0d0ab03d2434e5a5a957ed73b04b54`.
- FinalResult bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\NpuProductionControlV29C-20260712`.
- Report:
  `work\W1700K_NPU_PRODUCTION_CONTROL_V29C_REPORT_20260712.md`, SHA256
  `11c9dc3b8b292f395ea83a95ae06db57e86264d6b829e6f4b2fb794f01562201`.
- v29c adds persistent mode-3-only stock-copy control, serialized LuCI policy
  writes, production ownership telemetry, and an approximately 5x faster NPU
  JSON status path.
- Final flash evidence `work\router-tests\20260712-040907` passed all 29 mode-3
  radio/MLO/NPU tests. The clean repeated stock-copy run also passed twice with
  36/36 consumer completions and zero host-token balance/current.
- Router is currently mode 3 with stock-copy disabled, boot ID
  `c805c24a-5296-4479-bf17-5e0bc9d0e318`, clean wireless baseline, no fallback
  watchdog, and no fatal kernel diagnostic.
- Stock-copy is validated but remains default-off pending controlled
  client-assisted throughput proof. Exhaustive hostadpt/scatter/RRO/FastTX
  parity is still outside the production-control claim.

## Current v30 Doorbell Ordering State - 2026-07-12

- Installed image:
  `work\w1700k-npu-doorbell-ordering-v30-20260712-sysupgrade.itb`, SHA256
  `43f15b824467236e4a7c34ef92ea968a0315d9f91f406804c7679bd22a5658f0`.
- Stock kernel `set_npu_hostadpt_reg()` uses `dmb oshst` before MMIO.
- Rebuilt OpenWrt `mt76_dma_kick_queue()` uses `dsb st` before the NPU
  `regmap_write()` path. Ordering is proven stronger than stock.
- Live debugfs exposes the proof and continues to report
  `tx_doorbell_ownership=not_ported`; do not collapse ordering proof into an
  ownership-parity claim.
- Live evidence `work\router-tests\20260712-044550` passed 29/29 tests and
  restored the exact disabled-radio baseline.
- Router is mode 3, stock-copy disabled, boot ID
  `0de0174e-e0d0-4584-a38f-67d1926b2517`, with LuCI running and no fatal log.
- Report: `work\W1700K_NPU_DOORBELL_ORDERING_V30_REPORT_20260712.md`, SHA256
  `cda21f1e2634d36751b616ee638120f1a42dea76e2e0123d67286c20b49d7e63`.
- Roadmap: `work\W1700K_NPU_ROADMAP_ETA_POST_V30_20260712.md`, SHA256
  `aeb4bc146bf8af6c21d811644c140a14eaf39bf945b695b1497acb3e733d61fb`.
- FinalResult bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\NpuDoorbellOrderingV30-20260712`.
- Next phase: scatter and SKB/bufid lifecycle beyond the 2048-byte copy
  envelope, followed by teardown/late TXFREE, RRO/BA, and ping-pong/FastTX.

## Current Live Gigabit Evidence - 2026-07-12

- User-observed throughput reached the gigabit Ethernet ceiling on v30.
- Captured path: mode 3, stock-copy disabled, 6 GHz radio 2, client EHT160,
  2161/2402 Mbit/s negotiated rates, LAN3 to Wi-Fi transmit.
- NPU enqueue, consumer, TXFREE, and token ownership stayed balanced with zero
  invalid, missing, duplicate, mismatch, queue-pressure, RRO, or netdev risk
  deltas.
- PPE bound/WLAN entries stayed zero; direct mt76 WLAN-NPU transport carried
  the flow. Direct mode 3 is therefore not the demonstrated 1 GbE bottleneck.
- Live/source capture helper SHA256:
  `cbf636fe3bf36c6c8cdc1fe7e98ccb3795dee756019f17fd321dfd5d75209108`.
  It uses bounded debugfs reads, wall-clock windows, read-only deep mode 1,
  explicit-write deep mode 2, v30 counter deltas, and automatic rates.
- v30 squashfs predates this helper; the live overlay has it and the next image
  verifier requires it.
- Report: `work\W1700K_NPU_LIVE_GIGABIT_CAPTURE_REPORT_20260712.md`, SHA256
  `14913c5af3a9f0047f4a14234531e15f52fdf1a9e7e039c7fc8ef48509a41ce1`.
- Roadmap:
  `work\W1700K_NPU_ROADMAP_ETA_POST_GIGABIT_CAPTURE_20260712.md`, SHA256
  `c5956ea2337f67682b8173cca723aa7603cea146283e81a2bbb8db5f1b0a79f9`.
- Next work remains scatter/SKB/bufid and teardown correctness; stock-copy
  stays disabled unless testing above the 1 GbE ceiling justifies it.

## Repeat Gigabit Evidence - 2026-07-12

- The user repeated the v30 throughput test and again reported saturating the
  gigabit Ethernet link.
- The router was re-identified as the W1700K over Ethernet IPv6 link-local and
  remained in direct mode 3 with stock-copy disabled.
- Post-transfer cumulative state showed approximately 32.6 GB of Wi-Fi TX,
  matching `21,556,833` NPU enqueue/consumer events, balanced live ownership,
  and zero invalid, untracked, duplicate, ordering, or mismatch counters.
- The transfer ended before the helper baseline, so the capture corroborates
  path and ownership but does not independently measure that run's peak rate.
- Report: `work\W1700K_NPU_REPEAT_GIGABIT_EVIDENCE_20260712.md`, SHA256
  `8f0aff39df5abb35cc893adccdfb48e7f409d6e914dd2d6ba4b9c42bd3b66787`.
- Capture:
  `work\router-tests\throughput-live-20260712\capture-gigabit-repeat.log`,
  SHA256
  `1c205466d2858a2d7f7bb604d782a525e54aa42b048134310ce4bd8f54722f01`.

## Current v31 NPU TX Shape State - 2026-07-12

- Installed image:
  `work\w1700k-npu-tx-shape-v31-20260712-sysupgrade.itb`, SHA256
  `ef57d1bf7822d5a708e427312eb0313f60515984386aaf7f79ad5d58a1b66724`.
- Stock hostadpt uses one `skb->data`/`skb->len` DMA span and masks length into
  13 bits. It has no explicit nonlinear or upper-length guard.
- v31 linearizes nonlinear NPU TX SKBs, validates a contiguous span, rejects
  lengths above 8191, and rejects a still-owned descriptor before DMA mapping
  and mt7996 token allocation.
- Patch `9999zb-mt76-validate-w1700k-npu-tx-shape.patch` SHA256:
  `e6ed47ef78916fa910107bd717c0763686640f47281dd2adbbfb745374c973b3`.
- Live test `work\router-tests\20260712-181158` passed 29/29 tests. Boot ID
  `8616c76a-9a34-4a08-b9b6-22f926ec34ac`, mode 3, stock-copy disabled, no
  fatal kernel diagnostic.
- Synthetic TX state: 18 checks, 18 clean, zero nonlinear/GSO/linearization
  failure/oversize/descriptor-busy events, matching enqueue/consumer totals,
  and clean token/order accounting.
- Report: `work\W1700K_NPU_TX_SHAPE_V31_REPORT_20260712.md`, SHA256
  `51f82c85597a8a282062f7dcb1e7ab3248f95a75aa99fe4a0f5aedb8c637fcd6`.
- FinalResult bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\NpuTxShapeV31-20260712`.
- Current boundary: real-data nonlinear/GSO frequency on v31 is not yet
  measured. Next reverse-engineering phase is late TXFREE during teardown.

## Current Memory and Portal Diagnosis - 2026-07-12

- The router is not memory constrained: the observed 88 percent is available
  memory. The failed boot still had about 1.65 GiB available and no OOM or
  tmpfs/overlay pressure.
- One live boot suffered an unrecovered MT7996 PCIe `CmpltTO` after MCU
  `GET_MIB_INFO` timed out. `rpcd`, hostapd, netifd, and cfg80211/mac80211 work
  then blocked in survey/RTNL/restart paths, which made LuCI stop responding.
- Current boot ID `cc2c080e-85a2-4cb9-b7c9-2432dfe00129` is healthy after an
  18-minute soak, five Wi-Fi reloads, and 60 survey reads. Mode 3 and the
  user's tri-band MLO configuration remain unchanged.
- The endpoint failure is temporally associated with the preceding real-data
  run but is not yet attributed to mode 3 or v31. Required next evidence is a
  controlled client-assisted mode-3 versus mode-0 transfer with AER, MCU,
  token, TXFREE, and descriptor-shape capture.
- Report: `work\W1700K_MEMORY_PORTAL_LOCKUP_DIAG_20260712.md`, SHA256
  `2f69ce5a59ec6df613c267d837fd69f0a23e00369e8bc96bf39b54acd0f25c83`.

## Current MLO Configuration and UI State - 2026-07-12

- The intended tri-band network is now represented by one `wifi-iface`,
  `default_radio0`, with `mlo=1` and devices `radio0`, `radio1`, and `radio2`.
- Runtime contains one `ap-mld0`; the prior overlapping `ap-mld1` and
  `ap-mld2` definitions were removed after preserving
  `/root/wireless.before-mlo-dedupe-20260712-195327`.
- Current links are 2.4 GHz channel 6/40 MHz, 5 GHz channel 36/80 MHz, and
  6 GHz channel 37/320 MHz. Country, transmit power policy, NPU mode 3, and
  stock-copy state were not changed.
- Source and the live overlay now reject physical-radio ownership overlap and
  expose a dedicated LuCI MLO builder/tab with ownership-aware `Add MLO` and
  `Edit MLO` actions. New MLO creation enables selected disabled radios and
  opens on the required WPA3 key field.
- No new image exists for this fix yet. The next sysupgrade build must contain
  LuCI SHA256
  `c22005d10e161fe63e88224b175f70a9185c0bd7cf8da87c01895dc4f82db048`
  and validator SHA256
  `510a87726ef92764002ea0dadd47765017566e48df87d856cc047272c5855353`,
  or justified successors, and pass the updated full-image verifiers.
- Report: `work\W1700K_MLO_DEDUP_LUCI_BUILDER_FIX_20260712.md`, SHA256
  `cdbd77705c4f9735bdbf40c99fd4bbe9b7fc5f1a971c3d6a9fe6b0c53bdcf29d`.
- Next test: retry iPhone 16 Pro Max association. If it still fails, collect
  hostapd logs during a 5+6 GHz, 6 GHz EHT160 compatibility test.

## Current MLO Client Diagnostic State - 2026-07-12

- Live test profile is one 5+6 GHz MLD: radio1 channel 36/EHT80 and radio2
  channel 37/EHT160, SAE, PMF required, RNR enabled, debug logging active.
- Corrected the wifi-scripts internal `radios` schema from string items to
  numeric items and changed hostapd generation from physical link IDs to
  contiguous logical IDs.
- Live `ap-mld0` now reports link ID 0 on physical radio1 and link ID 1 on
  physical radio2. Backend validation passes.
- Source/live hashes: `ap.uc`
  `40d99d64fccc5da5efa2fc4296c5d4ec470a4fce99d4783cbe4f4f1fe2487d24`;
  wifi-iface schema
  `429311adb6d7054865326b4939aa51fbe4b8ff734e5b23eb71b6fab09462ea1a`.
- No client authentication frame was captured before this checkpoint, so the
  link-ID correction is confirmed but client association is not. Capture:
  `work\router-tests\20260712-mlo-client-debug\logread-live.log`.
- No image build or flash contains this fix yet. Next step is one BE201 and one
  iPhone retry; absent auth frames require over-the-air MLD beacon/probe
  analysis.
- Report: `work\W1700K_MLO_CLIENT_ASSOC_DIAG_20260712.md`, SHA256
  `9758bc3ab917372c69cd81be8fc71c6e0e171f724ae4bd68d16afb13ba63478c`.

## Current MLO Atomic Apply State - 2026-07-12

- MLO member radios must use fixed channels. LuCI selects channel 6/EHT40,
  channel 36/EHT80, and channel 37/EHT160 when radio0/1/2 were automatic or
  unset; backend validation blocks automatic MLO channels.
- The MLO network modal no longer exposes channel or width selectors. Physical
  radio settings remain independently validated against the regulatory map.
- Netifd propagates any changed MLD member configuration to every partner
  radio. Live proof changed only radio1 and observed radio1, radio0, and radio2
  all restart before the complete `ap-mld0` returned.
- Runtime currently has logical links `0,1,2`: 2.4 GHz channel 6 (20/40 MHz
  coexistence), 5 GHz channel 36/80 MHz, and 6 GHz channel 37/160 MHz.
- Package builds, browser QA, fixture tests, and the full static suite pass.
- No image contains these final fixes yet; they are source-backed live overlays.
- External BE201/iPhone association after this restart remains unproven.
- Report: `work\W1700K_MLO_CLIENT_ASSOC_DIAG_20260712.md`, SHA256
  `68ea96e73f2168e1cad01e2d63ac8aefc0cc24427f665eb703e2f56aa820654b`.

## Current MLO Beacon State - 2026-07-13

- Supersedes the prior contiguous-link-ID and coordinated-reload claims.
- This mt7996 stack requires MLD link IDs to retain physical radio indexes.
  A 5+6 GHz MLD uses link IDs `1,2`, not remapped IDs `0,1`.
- Windows listed the corrected `OpenWrt MLO` beacon as Wi-Fi 7/WPA3 at 95
  percent signal; the user independently confirmed iPhone 16 Pro Max
  visibility.
- The coordinated netifd member-reload experiment was reverted after causing
  mac80211 teardown faults and an unrecoverable MT7996 PCIe timeout.
- Warm reboot can leave hostapd enabled while RF is not externally observable.
  One PCIe function reset recovered an ordinary AP, but repeat recovery is not
  yet reliable enough to ship as an automatic boot workaround.
- Current live state is tri-band physical links `0,1,2`, exact v30 modules,
  and NPU mode 0. No image was built or flashed in this pass.
- The v31-only TX-shape patch is quarantined pending cold-boot external-client
  regression testing. The remaining active mt76 patch stack compiles.
- Report: `work\W1700K_MLO_BEACON_ROOT_CAUSE_20260713.md`.
- Report SHA256:
  `276835ff40b4a609a3b50a956577ca38ac7667e6ec01dec38bc14bbb142cccad`.

## Live Mode 3 Tri-Band MLO - 2026-07-13

- Current loaded/persisted WLAN NPU mode is 3.
- Current `OpenWrt MLO` uses physical links `0,1,2` on channels 6, 36, and
  37 with runtime widths 20, 80, and 160 MHz.
- Hostapd reports all links enabled and the boot log has no fatal MT7996/PCIe
  diagnostic.
- Independent iPhone visibility after this mode-3 reboot is still pending;
  the local connected-state Windows scan is not accepted as proof either way.
- No image was built or flashed.

## Live Mode 3 Regression Rollback - 2026-07-13

- Mode 3 allowed the laptop to complete SAE and associate, but user-measured
  throughput topped out at approximately 15.7 MB/s.
- The iPhone emitted no authentication frame, so its failure was before
  hostapd password/security processing.
- Current live mode is restored to 0 with the otherwise unchanged tri-band
  `OpenWrt MLO` configuration and physical links `0,1,2`.
- Laptop throughput and iPhone association must be retested on this mode-0
  baseline before any further compatibility change.

## Current Mode-0 MLO Throughput Diagnostic - 2026-07-13

- Mode 0 also reproduces approximately 15 MB/s, so mode 3/NPU activation is
  not the primary throughput limiter.
- Live and source MLO device ordering is now 5 GHz, 6 GHz, then 2.4 GHz.
  LuCI canonicalizes this order, boot sanity repairs it, and backend
  validation blocks noncanonical manual UCI order.
- Reordering moved hostapd's reported MLD frequency away from 2.4 GHz but did
  not by itself improve the user's measured throughput.
- A bounded live station/counter capture is active at
  `/tmp/w1700k-mlo-throughput-watch.log`.
- The current A/B profile uses `sae+ccmp`, producing `wpa_pairwise=CCMP` on
  all three MLO links while retaining SAE-EXT-KEY, PMF required, RNR, and NPU
  mode 0. Transfer and iPhone results are pending.
- The stock hostapd generator and stock 6 GHz defaults use CCMP for plain SAE;
  SAE-EXT-KEY is a separate explicit stock mode. This makes CCMP the current
  vendor-backed compatibility baseline, pending live results.
- Targeted LuCI/base-files builds and static fixtures pass. No image was
  built or flashed for these changes yet.
- Matching LuCI, sanity, and validator overlays are active on the router;
  backend validation passes. LuCI SHA256 is
  `76d159bfdc5c17ea6ac9149c39c73443e103899b951ea82222173cc66ec48635`.

## MT7990 Radio Firmware Correction - 2026-07-13

- The W1700K radio PCI functions identify as MT7990/MT7991, while the prior
  image profile incorrectly installed the MT7996 radio firmware bundle.
- NPU modes 0 and 3 both measured approximately 15 MB/s, so the firmware
  mismatch is the current primary WiFi throughput/reliability suspect.
- Source now selects `kmod-mt7990-firmware`; a new verifier blocks profile or
  rootfs regression back to `kmod-mt7996-firmware`.
- Targeted mt76 and full image builds pass. The embedded rootfs independently
  verifies with only the four expected MT7990 firmware files.
- Candidate image SHA256:
  `c86b69642006c8c79e6582ef10a9e1bf76e94e8ea25156c363de1ca835e5531c`.
- Runtime proof after flash is still required: confirm MT7990 firmware build
  strings, all three radios, MLO association, and throughput.
- Report: `work\W1700K_MT7990_FIRMWARE_CORRECTION_20260713.md`.

### Correction To This Section

- The MT7990 package hypothesis is rejected. In mt76, PCI `0x7990` maps to
  MT7996; MT7990 uses `0x7993/0x799b`.
- The MT7990-only image left every radio offline because mt7996e correctly
  requested `mt7996_rom_patch.bin`.
- The source profile is restored to `kmod-mt7996-firmware`, guarded by a new
  PCI-ID/profile/rootfs consistency test.
- Corrected candidate SHA256:
  `aac8d65585f5e3c9cd3747a977b213e714dbd1609dcad35e046b5fecf32ae46f`.
- All three radios and the tri-band MLD recovered after restoring MT7996
  firmware live. Clean corrected-image flash is pending.
- Authoritative report:
  `work\W1700K_RADIO_FIRMWARE_ID_AUDIT_20260713.md`.

## Mode-0 MLO Prequeue A/B - 2026-07-13

- The current throughput suspect is custom per-link WCID selection before
  mt76 queue choice while WLAN NPU mode 0 is active.
- New patch limits prequeue WCID selection to an active NPU. Mode 0 retains
  normal queue selection and chooses the high-band MLO link at TXWI time.
- Full build and embedded image/module checks pass.
- Candidate SHA256:
  `cb464d90c5a2bfc1776d366aa366e6de2c087640a00af95e814ffae5f7aacb9e`.
- Runtime throughput proof remains pending.
- Report: `work\W1700K_MLO_MODE0_PREQUEUE_AB_20260713.md`.

- Live status: candidate is flashed and healthy in mode 0. The automatic
  20-minute throughput capture is active, but no station has associated yet.

## Current Non-MLO Throughput Control - 2026-07-13

- The user measured approximately 15 MB/s on the mode-0 prequeue-bypass image,
  so that A/B did not improve MLO throughput and is rejected as a fix.
- The live router remains in mode 0. Its MLO interface is temporarily disabled
  under a saved backup, while ordinary 5 GHz EHT80 and 6 GHz EHT160 control APs
  are active as `W1700K 5G Test` and `W1700K 6G Test`.
- The all-interface capture is active at
  `/tmp/w1700k-throughput-control.log`; no client has associated yet.
- Source now restores all-mode per-link queue/TXWI WCID alignment and places the
  non-owning host-adapter skb shadow after the active NPU patch stack.
- Clean mt76 and full image builds pass. Experimental image SHA256:
  `7b363ab04140f821abca69dedcbc24bd6d16849c7e976dd2266b96533363bc6c`.
- The image is not flashed or promoted pending matching non-MLO control data.
- Report: `work\W1700K_MLO_NONMLO_CONTROL_AND_ALIGNMENT_20260713.md`.

## Mode-0 Throughput And Aggregation Gate - 2026-07-13

- Mode 0 also measures approximately 15 MB/s, matching mode 3. Live NPU TX
  counters remain zero, so the throughput ceiling is now classified as a WiFi
  path issue rather than an NPU-mode issue.
- An ordinary 5 GHz EHT80 association demonstrated healthy 1200.9 Mbit/s PHY
  rates, strong signal, and 1% TX PER. Sustained-load A-MPDU evidence is still
  required; idle traffic showed only one MPDU per aggregate.
- The base driver is current official mt76 commit
  `59676919ea408b0b13a9d23f2e2e1a1ab407fba1`, including its present mt7996 BA
  implementation. Local MLO queue/link patches remain the principal source
  delta under review.
- The router is restored to the ordinary 5 GHz EHT80 and 6 GHz EHT160 control
  APs on `lan`. Capture path: `/tmp/w1700k-throughput-active.log`.
- Required next evidence: repeat the same WiFi-client to Ethernet-endpoint
  transfer on each control SSID. Do not flash another image before this gate.

## NPU Descriptor Bit 31 Correction - 2026-07-13

- Stock RV32 disassembly proves TX descriptor bit 31 is not a firmware
  payload-copy completion acknowledgment. Ownership is tested with bit 0;
  payload length uses bits 18 through 30; bit 31 is neither consumed nor
  rewritten before consumer advancement.
- Source now fail-closes the old `npu_stock_copy_mode` experiment and never
  releases a token from bit 31.
- New patch:
  `9999zc-mt76-quarantine-host-owned-npu-sched-bit.patch`.
- NPU-enabled mt76 compile and binary gates pass. No image is built or flashed.
- Report: `work\W1700K_NPU_DESCRIPTOR_BIT31_QUARANTINE_20260713.md`.

## Ethernet Baseline - 2026-07-13

- A bidirectional four-stream TCP control bound to host Ethernet
  `192.168.1.224` measured `929.1-929.5 Mbit/s` toward the router and
  `937.4 Mbit/s` from the router.
- Per-adapter counters confirm the test used Ethernet while the host WiFi
  remained on its Internet AP.
- Treat the gigabit LAN/bridge/TCP baseline as healthy. The unresolved
  approximately `15 MB/s` ceiling remains a WiFi-path problem.
- No W1700K WiFi client was associated during the control; sustained-load
  station aggregation evidence is still pending.

## NPU Copy/Remap Contract Correction - 2026-07-13

- Native stock and Linux-firmware NPU blobs are different; their host payload
  lifetime behavior is not interchangeable.
- Native stock copies payload plus metadata into an allocated local buffer.
  Untouched Linux-firmware retains the host payload DMA address and copies only
  metadata.
- The W1700K package's custom trampoline implements a separate request/remap
  protocol. Source now authorizes consumer-side host-token completion only
  when bit 31 remains set and the payload address changed into the NPU-local
  `0x80000000` alias.
- This fails closed with native stock or unpatched OpenWrt firmware, which does
  not perform that address rewrite.
- Patch: `9999zc-mt76-validate-custom-npu-copy-remap.patch`.
- Strict checkpatch, NPU-enabled compile, and binary disassembly gates pass.
- Default remains off; no image is built or flashed pending controlled live
  remap/token-lifecycle validation.
- Report:
  `work\W1700K_NPU_FIRMWARE_CONTRACT_AND_REMAP_VALIDATION_20260713.md`.

## Runtime MLO TX Policy Gate - 2026-07-13

- Local pre-queue MLO link selection is now runtime-gated by
  `w1700k_mlo_tx_policy` instead of being unconditional.
- Policy `0` restores upstream scheduling and is the default. Policy `1`
  selects among all active links; policy `2` prefers 5/6 GHz links.
- LuCI, persistent helper state, fixture tests, mt76 compile, and LuCI package
  compile pass. Invalid values are rejected.
- A fresh Ethernet-only control measured `926.7 Mbit/s` to the router and
  `937.2 Mbit/s` from it with four streams. Single-stream results were
  `822.8/859.4 Mbit/s`.
- Experimental image:
  `FinalResult\Experimental\MloRuntimePolicy-20260713\w1700k-mlo-runtime-policy0-20260713-sysupgrade.itb`.
  SHA256:
  `e5361d13ad9532e83a97dbabc29a970603c2636fbe37aa50340edafad583d2f4`.
- FIT and embedded-rootfs verification pass. The image is not flashed or
  promoted. The next live gate is a policy `0/1/2` wireless aggregation
  comparison using an Ethernet benchmark endpoint.
- Report: `work\W1700K_MLO_RUNTIME_TX_POLICY_20260713.md`.

## NPU TX Lifecycle and Linearization - 2026-07-13

- Fresh Ghidra/source reconciliation proves stock TX has three lifetimes:
  vendor token release before hostadpt, host SKB/DMA lifetime through NPU
  consumer-side synchronous copy, and firmware-local token lifetime through
  WiFi TXDONE.
- OpenWrt unload, forced restart, and SER cleanup all release outstanding
  token-owned TXWI/SKB/DMA state. A flush-time token callback would create
  double-release risk and was not added.
- Stock TX is a single contiguous payload DMA contract; hostadpt scatter logic
  is RX-only. Added
  `9999zd-mt76-harden-npu-tx-linearization.patch`, SHA256
  `3bcc48882318da37745a3a09c03cefd491d47758a086c77aa1770b61b8c1e37c`.
- The patch skips `skb_linearize()` for already-linear NPU packets, rejects
  payloads above the descriptor's 8191-byte limit before token/DMA ownership,
  and adds live TX shape/linearization counters.
- Strict patch check, clean prepare, mt76 compile, disassembly, full image
  build, FIT, rootfs, package, firmware, and forbidden-module gates pass.
- Experimental image SHA256:
  `92c6bdc4a592979f1e3e9e0ca0bc58200d10cf98dc11b9e13d7146c5c4d2f8be`.
  It is not flashed or promoted; sustained wireless aggregation/NPU counter
  validation remains required.
- Report: `work\W1700K_NPU_TX_LIFECYCLE_LINEARIZATION_20260713.md`.

## Current Live Ethernet Boundary - 2026-07-13

- A fresh 30-second, four-stream native iperf control after the host WiFi
  change measured `931/927 Mbit/s` PC-to-router and `939/938 Mbit/s`
  router-to-PC over the directly connected `lan3` Ethernet path.
- Physical router counters proved the radios carried none of the benchmark
  payload. Post-load memory and kernel logs remained healthy.
- The currently flashed image has `npu_active=0` and lacks the new NPU module
  markers; this result is an Ethernet baseline only, not validation of the
  unflashed TX-linearization image.
- No WiFi client was associated. Wireless aggregation, MLO policy A/B, and
  live NPU TX-shape counter validation are still required.

## NPU TX Real-Time Telemetry Candidate - 2026-07-13

- The TX contiguous-payload/linearization counters are now exposed through a
  coherent `npu_tx_shape` helper snapshot and the existing polled LuCI NPU
  page.
- LuCI reports contract health, payload shape, linearization results and
  bytes, descriptor oversize rejects, and the `8191`-byte maximum.
- Counter imbalance, descriptor mismatch, linearization failure, or oversize
  rejection reports `degraded`; the fixture verifies both healthy and injected
  degraded paths.
- Full image and embedded-payload verification pass. Experimental bundle:
  `FinalResult\Experimental\NpuTxTelemetry-20260713`.
- Candidate SHA256:
  `6c495e2a4ff20f06a8ee3dce5fd8baee6b94bd2bc29b747685a22845b14c3a3e`.
- The candidate is unflashed and unpromoted. The currently running router is
  still the older mode-0/NPU-disabled module set.
- Report: `work\W1700K_NPU_TX_TELEMETRY_IMAGE_20260713.md`.

## Current Live Mode-3 Scan Fix - 2026-07-13

- Current flashed image:
  `FinalResult\Experimental\NpuMgmtDefer-20260713\w1700k-npu-mgmt-defer-20260713-sysupgrade.itb`.
- SHA256:
  `4a818551b7a70ca8b08a7e4aa01ae1e1854e975b20eff7b61a8be6a93b1d277c`.
- Current loaded and persisted WLAN NPU mode is 3.
- Root cause: the NPU had consumed each management TX descriptor, but mt76
  blocked every scan channel transition for a later TXFREE-owned PSD token.
  The queue was empty and token accounting was valid, so this produced a
  200 ms delay per channel and a 5-second `iwinfo` timeout.
- The active NPU path now treats descriptor consumption as channel-drain
  completion while preserving token, TXWI, DMA, SKB, and TXFREE ownership.
  Non-NPU mode retains upstream wait semantics.
- Mode-3 validation:
  - 5 GHz first pass: 4 seconds, 314 lines, `15/15` payload/TXFREE;
  - five reload/scan cycles: all pass in 3-4 seconds, 314-342 lines;
  - 2.4 GHz temporary-interface scan: pass, `5/5` payload/TXFREE;
  - 6 GHz scan: 5 seconds, `62/62` payload/TXFREE;
  - final TXFREE: 454 token words, zero missing/count mismatch;
  - channel wait timeouts: zero;
  - deferred real management completions: 181.
- Exact live rootfs module hashes match the extracted sysupgrade image.
- This is a verified fix for the reproduced mode-3 scan/offline failure, not
  a claim of full vendor hostadpt or RRO parity and not sustained-throughput
  proof.
- Report: `work\W1700K_NPU_MODE3_SCAN_MGMT_DEFER_20260713.md`.

## Current Live NPU Reprobe Ring Fix - 2026-07-13

- Current flashed image:
  `FinalResult\Experimental\NpuHostadptRingSyncWdevGuard-20260713\w1700k-npu-hostadpt-ring-sync-wdev-guard-20260713-sysupgrade.itb`.
- SHA256:
  `e008a0210ce5755b165087e471fa45cb1f382a4b1598690e2aa68f60dca16e3b`.
- Root cause: exact EN7581 MT7996 firmware refreshes host-adapter ring bases
  but retains private consumer indices across newly allocated mt7996 rings.
- Source now seeds firmware bases, 1024-entry sizes, and consumers from the
  live hardware DMA state before selector 2 starts the firmware consumer.
- Six zero-delay unload/reprobe cycles passed, including three with an active
  scan during teardown. Synchronization calls/errors ended at `7/0` with
  matched payload/TXFREE and zero channel/mailbox/critical-kernel deltas.
- 2.4, 5, and 6 GHz mode-3 AP scan smoke passed at 20, 80, and 320 MHz.
- The integrated rootfs also guards `wdev.uc` against dereferencing a missing
  PHY during forced driver teardown. Direct and actual reprobe tests pass;
  embedded-rootfs and source hashes match with no overlay copy.
- Current router runtime is persistent mode 0 with temporary APs disabled.
- Next work: obtain sustained associated-client throughput/aggregation
  evidence and continue hostadpt/TXFREE/RRO ownership parity. The benign
  jailed hostapd control-directory `rmdir` denial remains tracked separately.
- Report:
  `work\W1700K_NPU_HOSTADPT_REPROBE_RING_SYNC_20260713.md`.

## Current Live Full-Reset Boundary - 2026-07-15

- Current flashed diagnostic image:
  `FinalResult\Experimental\NpuDocumentedWfdmaBusyMask-20260715\w1700k-npu-documented-wfdma-busy-mask-20260715-sysupgrade.itb`.
- SHA256:
  `0beae7c3143e84caabc6787145be9f0db4a7c4e4599928f8da60e4c3e2a43193`.
- Router runtime is persistent mode 0 with three APs online. Mode 0 full reset
  passes in 20 seconds.
- Mode 3 initializes cleanly, but full SER recovery is not safe yet.
- Live probes exclude firmware selector 6, coredump, WDT interrupt-enable
  access, HIF2/PCIe interrupt-mask writes, WFDMA busy-mask programming, and
  WFDMA idle polling as the immediate trigger.
- With the documented MT7996 mask `0x7`, WFDMA reports idle and the first AER
  follows about 190 ms later in the TX queue flush/sync stage.
- Next boundary: distinguish NPU host-adapter regmap sync from direct PCIe
  WFDMA shadow `ring_size`/`desc_base` writes before changing ownership logic.
- Report: `work\W1700K_NPU_FULL_RESET_MMIO_NARROWING_20260715.md`.

## Current Live Direct-Timeout Boundary - 2026-07-16

- Current flashed diagnostic image:
  `work\w1700k-direct-timeout-handoff-v6.8-20260716-sysupgrade.itb`.
- SHA256:
  `54ef417fb0a0ee36a96f640e55f734b855ae810acdf59c71e145142061213852`.
- Router is persistently back in mode 0, boot ID
  `1b492640-c519-4bb6-af26-67af6ba20ea5`, with all three APs online.
- V6.7 proved the fault-injection path bypasses coredump preparation and
  queues full reset directly from `mt7996_mcu_parse_response()`.
- V6.8 covers that path without sleeping in the parser. Live logs prove the
  worker now stops the active NPU path before setting MCU/PHY reset state.
- The asserted WM core cannot acknowledge `mt7996_mcu_prepare_reset()`; its
  second `0x00130022` request times out and firmware preparation returns `-5`.
  The safety fallback then uses the subsystem pulse and reproduces PCIe AER.
- The CBInfra WM-only candidate remains untested because V6.8 intentionally
  requires successful graceful firmware preparation before selecting it.
- Next test: add a runtime-disabled diagnostic override allowing CBInfra after
  a completed NPU quiesce even when WM is unresponsive, select reload mask 1,
  and preserve the mode-0 next-boot fallback.
- Full stock reset ownership, hostadpt TX lifecycle, TXFREE byte equivalence,
  RRO equivalence, and ping-pong packet fate remain open.
- Report: `work\W1700K_NPU_DIRECT_TIMEOUT_HANDOFF_20260716.md`.

## Current Live Quiesced-CBInfra Boundary - 2026-07-16

- Current flashed diagnostic image:
  `work\w1700k-quiesced-cbinfra-v6.9-20260716-sysupgrade.itb`.
- SHA256:
  `2c3cdf3f6bbbdb6bee9f0807de421e230c6221cde9330dd7e19a1dcfb65af59f`.
- Router is persistently back in mode 0, boot ID
  `91b1b3dd-4fa5-48b1-b31a-3ad3164fd02d`, with all three APs online.
- A RAM-only diagnostic override allowed the W1700K CBInfra pulse after
  completed NPU quiesce even though graceful WM preparation returned `-5`.
- Ten pulses completed with no PCIe AER, but all ten attempts failed with
  `Firmware is not ready for download`; the core-reload path was never
  reached.
- Ghidra plus ELF relocations now resolve the stock vendor action map:
  action `2` rebuilds bus/token DMA, `5` resets WFSYS, `7` gates traffic,
  `8` stops NPU, and `9` starts NPU.
- The stock L1 SER state machine surrounds firmware event/ack transitions
  with NPU stop/start and DMA/token teardown/rebuild. A standalone CBInfra
  pulse is therefore not stock recovery parity.
- Next boundary: identify and safely reproduce the firmware/download-state
  transition before designing V6.10.
- Report: `work\W1700K_NPU_STOCK_SER_ACTION_MAP_20260716.md`.

## Current WM SER Firmware Boundary - 2026-07-16

- Stock host-side `UniCmdSER` is fully resolved. Command ID `0x13`, all four
  TLV tags/lengths/payload offsets, stock mask `1`, L1 method `1`, and no-ack
  trigger policy match current mt76 exactly.
- Earlier stock-staged, upstream-exact, and modern trigger tests were valid;
  the firmware accepted them but did not enter STOP-DMA recovery. The host
  wire ABI is no longer an open explanation.
- Current WM build `20260311120504` was read from live mapped MCU memory after
  hardware decryption. The verified nine-region archive is
  `work\wm-ser-analysis-20260716\wm-live-20260311.tar.gz`, SHA256
  `96e6f372e78ca9aef27424db5daffea203957cbe9da21f30afffaf5fe56c4f30`.
- Full RV32 Ghidra analysis confirms current WM contains complete SER L1-L4
  state-machine diagnostics and host event/ack states. SER is present, but
  its log text is an unreferenced dictionary rather than direct code xrefs.
- A full mask trace plus six alternating focused samples did not find a stable
  mask global; all 19 candidates were changing runtime structures.
- Router baseline after the trace is boot ID
  `d20d3ef9-f14b-40f2-8b24-bc35bff18d79`, persistent NPU mode 0, with 2.4,
  5, and 6 GHz APs online and no firmware or PCIe error signature.
- Current next step: recover the decrypted WM function graph and unified SER
  dispatcher, then identify the runtime trigger gate or stock download-state
  transition. Do not build V6.10 from speculation.
- Detailed report:
  `work\W1700K_WM_SER_ABI_LIVE_DECRYPTION_20260716.md`, SHA256
  `8859973e3288a4670b4d6a92e6d6cb049a08d2430e76d41110f6dce7400a7660`.

## Current WM Native-L1 Boundary - 2026-07-16

- The decrypted unified-command table is resolved at `0x0221df5c`; command
  `0x13` dispatches to SER handler `0xe008d8a8`.
- Synthetic methods are gated by predicate `0xe0120350`, which reads
  `0x00401484` and requires `(gate >> 16) == 0x1510` plus `BIT(method)`.
  The clean runtime word is zero, explaining all earlier no-op triggers.
- Exhaustive executable-region disassembly and Ghidra show one gate read and
  no loaded-WM writer.
- A bounded mode-0 write of `0x15100002` made stock-staged sequence 104 enter
  native L1. Recovery completed in about 41 ms without reboot, radio loss, or
  interface/channel change; the gate was restored and the router rebooted.
- Active patch
  `package/kernel/mt76/patches/9999zzz-mt7996-arm-w1700k-wm-ser-trigger-gate.patch`,
  SHA256
  `cc84e810edbb7340d432c3ff68e605fffa523357d4423202cfdcc4eb7d07a4d7`,
  guards the build-specific write with device and predicate checks. Clean
  prepare and mt76 compile pass.
- Current router baseline is boot ID
  `3695fd25-aab8-4d50-b3da-6cc56f658313`, mode 0, gate zero, tri-radio APs
  online, and clean error checks.
- Next: build V6.10 and run native-L1 recovery in modes 0, 1, 2, and 3. Fatal
  assert/download-state recovery remains open and must not be conflated with
  this now-resolved synthetic trigger gate.

## Current Live V6.11 Native-L1 Checkpoint - 2026-07-16

- Current flashed image:
  `work\w1700k-wm-ser-gate-v6.11-20260716-sysupgrade.itb`.
- SHA256:
  `f08a74cec9c026e7f88f53cd476e72b905c235b08de240088e142f59e1bcba84`.
- Verified promotion directory:
  `FinalResult\Experimental\WmSerGateNativeL1V611-20260716`.
- Checked `SHA256SUMS.txt` SHA256:
  `f1a0a86d2dcef627e5db71997bbebe75925d9588f416e7779c4d12111ec95932`.
- V6.10 proved native L1 in both implemented modes: one mode-0 pass and
  eleven total mode-3 passes. Mode-3 stress showed stable boot, radios, NPU
  health, and memory with no PCIe, firmware, or kernel-fault signature.
- Modes 1, 2, and 4 are not implemented by this split-DMA driver. V6.11 makes
  that explicit: only modes 0 and 3 are selectable in LuCI, and unsupported
  modes are rejected before configuration changes.
- Live helper and `mt7996e.ko` hashes match the extracted image exactly.
- V6.11 post-flash native L1 passed in about 37 ms with boot ID unchanged,
  gate zero, and tri-radio state unchanged.
- Current state: boot ID `675f8707-32b9-4605-864c-de86d2404bbd`, persistent
  mode 0, 2.4 GHz channel 6/20 MHz, 5 GHz channel 36/80 MHz, and 6 GHz
  channel 37/320 MHz online.
- Detailed report:
  `work\W1700K_WM_SER_GATE_NATIVE_L1_V611_20260716.md`, SHA256
  `b7fa273a21bac1000d31db2dd50de6f93c05ff0ed1c84b71209a9d222cc16419`.
- Next boundary: recover the stock fatal-assert/download-state transition and
  continue hostadpt/TXFREE/RRO ownership parity. Native L1 does not rescue a
  WM core that is already unable to execute its SER handler.

## Current Unflashed V6.12 NPU RX Hardening Candidate - 2026-07-16

- Current live router remains on V6.11, SHA256
  `f08a74cec9c026e7f88f53cd476e72b905c235b08de240088e142f59e1bcba84`,
  persistent mode 0, boot ID `675f8707-32b9-4605-864c-de86d2404bbd`.
- The stock L1 ACK path is host-wire equivalent to current mt76. The private
  FE/WiFi notifier protocol is compiled but unwired in stock and is not a
  production dependency.
- Stock SER level 100 handles severe PCI RX descriptor ownership mismatch.
  Current WM method 8 is the matching forced native-L1 path and bypasses the
  synthetic method-1 gate while still requiring responsive WM firmware.
- Corrected `NPU_RX_DMA_PKT_COUNT_MASK` from overlapping bits `31:28` to the
  stock/kernel/upstream layout `31:29`.
- Added bounded complete-chain preflight, stock-style continuation retry,
  count/length/DMA validation, fault latching, IRQ quiesce, method-8 recovery,
  safe allocation-failure recycle, and debugfs fault telemetry.
- Both patches pass strict checkpatch, synthetic tests, clean prepare, and
  full NPU mt76 compilation.
- Candidate image:
  `work\w1700k-npu-rx-hardening-v6.12-20260716-sysupgrade.itb`.
- Candidate SHA256:
  `f258a53282ef1649748d79e05665b77c1114a33d7391d4115f85af1e20231c1b`.
- FIT, package, firmware, module, and forbidden-stock-module verification
  passes. The candidate is built but unflashed and unpromoted.
- Detailed report:
  `work\W1700K_STOCK_SER_ACK_FE_NOTIFIER_20260716.md`, SHA256
  `dd9d9947d6ab8b31d2ad0c4fd99c90b48c50bd3a4cffa46d2bae5c09ccd5b48f`.
- Next live gate: mode-0 and mode-3 boot/scan/reload/throughput/native-L1
  validation. Fatal-assert download-state entry remains unresolved.


## Current Live V6.15 PCI Shutdown Baseline - 2026-07-16

- Current flashed image:
  `work\w1700k-pci-shutdown-v6.15-20260716-sysupgrade.itb`.
- Image SHA256:
  `9107077012fd8b3af708f0a6c5e5e1f19c37339625a2d6536a77cda59f642144`.
- Embedded/live `mt7996e.ko` SHA256:
  `4a1ad2cdc35e3c933c54ca5491f350af38dd8fe831016f89dd44fb91abc72298`.
- Patch:
  `work\patches\9999zzzd-mt7996-run-device-teardown-on-pci-shutdown.patch`,
  SHA256
  `2208786d21be5627845583809e81e59b61218812b4e25d48072d56c979a464ef`.
- Root cause closed: Linux reboot did not call mt7996 remove and mt7996 lacked
  a PCI shutdown callback. V6.15 runs normal device teardown from shutdown,
  stopping NPU/DMA ownership before warm reboot.
- The direct mode-3 to mode-0 first-boot regression and three additional full
  transition cycles passed with valid BAR/remap reads, exact WM predicates,
  three APs, and successful tri-radio scans. No `0xdead2117` repair reboot was
  required.
- Native L1 passed in initial mode 0, initial mode 3, direct-regression mode
  0, and final mode 3. The hardened harness refuses unreadable MMIO instead
  of issuing an unsafe trigger.
- Current router state: persistent/loaded mode 3, boot ID
  `7490cf53-4452-4d71-bab3-744e9576061d`, NPU lifecycle ready with two
  balanced slots and zero blocked IRQs, all three APs online, and 1,665,020
  KiB available memory.
- Detailed report:
  `work\W1700K_PCI_SHUTDOWN_WARM_REBOOT_V615_20260716.md`, SHA256
  `c8076350343648cfa370035f7b15f5146f998a4671a60d2529cd58d2ecebf550`.
- Verified promotion:
  `FinalResult\Experimental\PciShutdownWarmRebootV615-20260716`;
  `SHA256SUMS.txt` SHA256
  `1542f404e059b2a2d7bbfa084825becdc5593e499687829feb637bb4ba762775`.
- V6.15 is the current live synthetic baseline. Next boundaries are external
  client throughput/MLO, deliberate RX fault injection, dead-WM recovery,
  complete hostadpt TX ownership, TXFREE/token equivalence, RRO ownership,
  and final ping-pong packet fate.

## Current Offline V6.19 Ownership Candidate - 2026-07-17

- Current live baseline remains V6.15; no router operation occurred in the
  V6.19 pass. V6.16 is rejected for mode 3. V6.17, V6.18, and V6.19 are
  unflashed candidates awaiting COM3 recovery and staged live gates.
- V6.19 image:
  `work\w1700k-npu-stop-rro-ownership-v6.19-20260717-sysupgrade.itb`.
- SHA256:
  `0842e6158134cf2e1ac1b3945fa6e1afc3683bf437f2842926d5202eb5277f3e`.
- Checked bundle:
  `FinalResult\Experimental\NpuStopRroOwnershipV619-20260717-UNFLASHED`.
- Stock timeout literals are poll counts over 100-microsecond delays: WLAN
  stop SET is 6 seconds and the stop-state GET is 100 milliseconds. The
  corrected constants are compiled into the candidate; no wrong-timeout image
  exists.
- PCI shutdown now uses a non-destructive quiesce path. Later complete RV32
  analysis corrects the earlier interpretation of GET zero: it proves the RRO
  fast path and refill worker stopped, but does not prove that global RRO DMA
  pointers were forgotten and cannot authorize their free or reuse.
- RRO CPU consumption now performs the recovered ten-read/1-microsecond owner
  handoff and exposes read-only `npu-rro-owner` telemetry.
- Full Ghidra analysis/save passed for final `mt76.ko`, `mt7996e.ko`, and the
  entire 77.5 MB kernel ELF. The saved project remains under
  `work\ghidra-v619-ownership-20260717`.
- Detailed report:
  `work\W1700K_NPU_FAILED_STOP_RRO_OWNERSHIP_V619_20260717.md`, SHA256
  `6e58248025efe7dab5696098ede07f2808b806677a155fb5e9c2d011b8841040`.
- Tomorrow's order is COM3 recovery, stable mode-0 radio/reload/native-L1
  validation, V6.19 mode-0 validation, then bounded mode-3 retained-ring,
  IRQ, mailbox, RRO-owner, memory, and fatal-log checks.
- Still open: complete scatter/multi-SKB/free-pool/BA fate, remaining
  TXFREE/token equivalence, dead-WM recovery, and final ping-pong/FastTX.

## Current Offline V6.20 Host Scatter And RRO Candidate - 2026-07-17

- Current live baseline remains V6.15. No router operation occurred in the
  V6.20 pass. V6.16 remains rejected for mode 3; V6.17 through V6.20 remain
  unflashed candidates awaiting serial recovery and staged live gates.
- Latest candidate:
  `work\w1700k-npu-scatter-rro-v6.20-20260717-sysupgrade.itb`.
- Image SHA256:
  `6ecb1f85ab8d234511298e35571f2b1d083fca44c970915a302d08e907837be7`.
- Checked bundle:
  `FinalResult\Experimental\NpuScatterRroV620-20260717-UNFLASHED`.
- Host NPU multi-descriptor RX now validates and snapshots the full chain,
  preserves the first classification word, copies into one stock-shaped
  linear SKB, and recycles every source page. The previous nonlinear host SKB
  conflicted with mt7996 contiguous-data parsing.
- RRO multi-buffer RX now gathers continuation pages into page-pool-backed SKB
  fragments and recycles current/pending pages on all inspected rejection
  paths. OpenWrt's RX-token IDR remains a semantic free-pool mapping, not
  byte-identical vendor list parity.
- Clean package/image builds, strict checkpatch, generated-code checks,
  fail-closed FIT/rootfs audit, and full Ghidra analysis of the exact rebuilt
  modules pass. The kernel ELF exactly matches the V6.19 fully analyzed hash,
  so its saved 36,845-function Ghidra analysis remains authoritative.
- Detailed report:
  `work\W1700K_NPU_SCATTER_RRO_V620_REPORT_20260717.md`, SHA256
  `d0beccdd2979bcda0e9d0a8949870604e8483564718b2cf4ce52c083ae5a256f`.
- Tomorrow's order remains COM3 recovery, known mode-0 baseline validation,
  V6.20 mode-0 validation, then bounded mode-3 ring/IRQ/mailbox/scatter/RRO/
  memory/native-L1 checks. The image must remain unpromoted until those pass.
- Still open: exact TX hostadpt object ownership, remaining TXFREE/token edge
  cases, RRO free-pool/BA byte equivalence, dead-WM recovery, and final
  ping-pong/FastTX packet fate.

## Current Offline V6.21 Token Sweep Candidate - 2026-07-17

- Current live baseline remains V6.15. No router operation occurred in the
  V6.21 pass. V6.16 remains rejected for mode 3; V6.17 through V6.21 remain
  unflashed candidates awaiting serial recovery and staged live gates.
- Latest candidate:
  `work\w1700k-npu-token-sweep-v6.21-20260717-sysupgrade.itb`.
- Image SHA256:
  `43a9bdaa1f440d56954372e65c9556d52909b20983ec6d0e7de300a911d12b83`.
- Checked bundle:
  `FinalResult\Experimental\NpuTokenSweepV621-20260717-UNFLASHED`.
- The reset/unregister token sweep now reclaims every IDR-owned TXWI/SKB/DMA
  object even if accounting is inconsistent, records reset-owned releases,
  converges token/WED counts, clears token-pressure queue blocking, resets all
  three management counters, and wakes waiters only after convergence.
- The final patch contains no `WARN_ON` trap. Three unsafe or racy
  intermediate variants are explicitly rejected and excluded from packaging.
- Strict checkpatch, clean package/full builds, source ownership audit, host
  fault-injection model, FIT/rootfs audit, exact generated-code checks, and
  full Ghidra analysis of the exact rebuilt `mt7996e.ko` pass.
- Detailed report:
  `work\W1700K_NPU_TOKEN_SWEEP_V621_REPORT_20260717.md`, SHA256
  `e5ddb917d03cc5c6e90fc9616067f0b6f2c64c7529db6509ea312276b9700900`.
- Tomorrow's order is COM3 recovery, a known mode-0 radio/reload/native-L1
  baseline, hash and `sysupgrade -T` gates, V6.21 mode-0 reset/token tests,
  then bounded mode-3 ownership, radio, memory, and recovery checks.
- Still open: failed-stop hardware isolation, residual TXFREE/token edges,
  RRO free-pool/BA equivalence, dead-WM recovery, and FastTX/ping-pong fate.

## Current Offline V6.22 Fail-Closed Recovery Candidate - 2026-07-17

- Current live baseline remains V6.15. No router operation occurred in the
  V6.22 pass. V6.16 remains rejected for mode 3; V6.17 through V6.22 remain
  unflashed candidates awaiting serial recovery and staged live gates.
- Latest candidate:
  `work\w1700k-npu-failed-stop-v6.22-20260717-sysupgrade.itb`.
- Image SHA256:
  `f3e42a3efb5c2252a6ea800783152493f1f80c90ef9067e186583db6ead7488d`.
- Checked bundle:
  `FinalResult\Experimental\NpuFailedStopV622-20260717-UNFLASHED`.
- Full reset and diagnostic recycle now treat NPU ownership as an invariant.
  A failed or unconfirmed stop cannot reach token/DMA destruction, station/VIF
  reset, mac80211 restart, or transport start. Terminal failure leaves WLAN
  quiesced, records isolation, and requires reboot.
- Stop SET failure still performs the recovered stock ownership GET loop.
  Diagnostic NAPI state is synchronized, and read-only
  `npu-reset-isolation` reports the terminal state and counters.
- Strict checkpatch, host failure model, clean focused/full builds, exact-image
  audit, generated-code branch checks, and full Ghidra analysis of the exact
  607-function module pass. The unchanged kernel ELF reuses the exact V6.19
  36,845-function analysis by SHA256.
- Detailed report:
  `work\W1700K_NPU_FAILED_STOP_V622_REPORT_20260717.md`, SHA256
  `6b0d2109dcad072e35c6e3ca501d8d95d7268daa24d8191602627f4c014cc1d3`.
- Tomorrow's order is COM3 recovery, known V6.15 mode-0 board/radio/reload/
  memory/native-L1 gates, hash and `sysupgrade -T` checks, V6.22 mode-0 reset
  isolation tests, then bounded mode-3 ownership and recovery tests.
- Still open: residual TXFREE/token edges outside copy/remap, exact RRO
  free-pool/BA behavior, dead-WM recovery, FastTX/ping-pong packet fate, and
  live synthetic validation.

## Current Offline V6.23 TXFREE Envelope Candidate - 2026-07-17

- Current live baseline remains V6.15. No router operation occurred; V6.16
  remains rejected for mode 3 and V6.17 through V6.23 remain unflashed.
- Latest candidate:
  `work\w1700k-npu-txfree-envelope-v6.23-20260717-sysupgrade.itb`.
- Image SHA256:
  `acb4eed32ce1d596f210663ee72ceae29577f96d66bc5a5abdeb2627012ebabf`.
- Checked bundle:
  `FinalResult\Experimental\NpuTxfreeEnvelopeV623-20260717-UNFLASHED`.
- The cumulative source had lost three prior stock-derived parser contracts.
  V6.23 restores RX-byte bounding for stock v4/v5, rejects NPU-active
  versions above 5 and malformed envelopes, uses complete-dword bounds, and
  counts only `freed < expected` as short.
- A captured live v5 notification proves why this matters: skb `len=64`,
  firmware `rx_bytes=32`, with unrelated tail words beyond the envelope.
- Existing low-local/high-host token ownership remains unchanged. No old
  qentry/token-shadow/FIFO experiment or unobserved legacy parser was restored.
- Strict checkpatch, host model, clean focused/full builds, exact-image audit,
  zero-new-warning comparison, and full exact-module Ghidra analysis pass.
  Ghidra recovered 608 functions and confirms the intended parser and token
  control flow.
- Detailed report:
  `work\W1700K_NPU_TXFREE_ENVELOPE_V623_REPORT_20260717.md`, SHA256
  `845a69967d3fb6309c601338e053e8d15c927be7b401c0d1d9e9a81c6ab4280a`.
- Tomorrow's order remains COM3 recovery, known V6.15 mode-0 board/radio/
  memory/native-L1 gates, hash and `sysupgrade -T` checks, V6.23 mode-0
  validation, then bounded mode-3 TXFREE/token/reset tests.
- Historical TXFREE closure claim retracted on 2026-09-01: the observed v5
  format carries no generation, and a stale completion after numeric token
  reuse cannot be distinguished from a current completion. Also open: exact
  RRO free-pool/BA behavior, dead-WM recovery, FastTX/ping-pong packet fate,
  and live synthetic validation.

## Current Offline V6.24 RRO Integrity Candidate - 2026-07-17

- Current live baseline remains V6.15. No router operation occurred; V6.16
  remains rejected for mode 3 and V6.17 through V6.24 remain unflashed.
- Latest candidate:
  `work\w1700k-npu-rro-integrity-v6.24-20260717-sysupgrade.itb`.
- Image SHA256:
  `ef68f3a032782274ee5cd64975950416139e3624e3f2510e4a4475b89402acd2`.
- Checked 81-entry bundle:
  `FinalResult\Experimental\NpuRroIntegrityV624-20260717-UNFLASHED`.
- The corrected implementation reconstructs the complete 36-bit RRO DMA
  address and holds the RX-token lock across lookup, null/queue/DMA checks,
  and conditional IDR removal. Failed claims remain IDR-owned for reset.
- RRO MCU notifications are bounded TLVs. BA session IDs publish only after
  status 0; status 3 is observable but does not replay a cached pointer; BA
  delete IDs are limited to the inclusive hardware range `0..1024`.
- Draft 1 removed ownership before validation and recycled on integrity
  failure. It was rejected before packaging or flashing and is retained only
  under `work\build-v6.24-draft1-release-before-validation-20260717`.
- Strict checkpatch, ownership model, prepared-source audit, clean focused and
  full builds, exact-image audit, zero-new-warning comparison, and independent
  verifier pass. Full Ghidra analysis recovered 610 `mt7996e.ko` functions
  and 439 `mt76.ko` functions and confirms validate-before-remove ordering.
- Detailed report:
  `work\W1700K_NPU_RRO_INTEGRITY_V624_REPORT_20260717.md`, SHA256
  `a2e1670c9d81506ed9e832dda8c8df1a3b81fc3054691e2c3034859c6db48dc0`.
- Tomorrow's order remains COM3 recovery, known V6.15 mode-0 board/radio/
  memory/native-L1 gates, hash and `sysupgrade -T` checks, V6.24 mode-0
  validation, then bounded mode-3 ownership/RRO/reset tests.
- RRO token/BA integrity is closed on paper for the observed stock contracts.
  Still open: dead-WM/fatal-download recovery, FastTX/ping-pong packet fate,
  and live synthetic validation.

## Current Offline V6.29 Guarded FastTX Direct Candidate - 2026-07-18

- **Accepted live baseline remains V6.15.** V6.16 remains rejected for mode 3.
  V6.17 through V6.29 are offline candidates and must not be described as
  live-accepted or promoted.
- Cumulative offline lineage after V6.24:
  - V6.25 corrected stock WFSYS reset from logical `mt76_wr()` remapping to
    the recovered raw BAR0 `0x1f8600` callback semantics.
  - V6.26 placed a non-consuming reason-22 observer at the stock QDMA hook
    boundary and retired unsafe public mt76 ownership controls.
  - V6.27 corrected reason-22 to RX-info tag `0x7275` and restored physical
    mt7996 band index `0/1/2` in WDMA metadata.
  - V6.28 added a narrowly gated, default-off QDMA-to-WiFi qdisc consumer.
  - V6.29 adds an independently default-off qdisc-bypass mode behind the
    V6.28 consumer.
- Latest image:
  `work\w1700k-stock-fasttx-direct-v6.29-20260718-sysupgrade.itb`.
- Image size: 20,607,804 bytes.
- Image SHA256:
  `9b951aef30e36a8049f9031e5242a9a24103a6f30b4a8b0e3d9dbc6155c98e60`.
- Checked bundle:
  `FinalResult\Experimental\NpuStockFastTxDirectV629-20260718-UNFLASHED`.
- Both kernel controls default off:
  - `stock_wifi_fasttx_consume`
  - `stock_wifi_fasttx_direct`
- Exact stock runtime analysis found no provider for optional soft-rate/RPS/
  queue-allocation hooks. Stock `TCSUPPORT_WIFI_COMMON_MVAL` is `0x3b`, bit 8
  is clear, RPS hooks are null, and active stock flow calls the selected WLAN
  transmit callback after classification/target checks.
- V6.29 mirrors netdev-core queue selection and uses public
  `dev_direct_xmit()` after the one-way `q->skb = NULL` commit. It does not
  copy the stock raw callback invocation. The wrapper preserves validation,
  TX queue locking, and BUSY/incomplete cleanup.
- Broad source regression gate passes 52/52. Focused V6.29 gate passes 25/25.
  Ownership model passes 5,242,938 checks. Strict checkpatch, target compile,
  sanitized full build, exact FIT/rootfs/kernel/package audit, live-gate
  fixture, and independent bundle checksum pass.
- Full Ghidra 12.1 exact-binary analysis recovered 36,847 kernel functions.
  `vmlinux` SHA256 is
  `3791ac61edef423cc3649b73cb417215dc5546d275e172e945ed14d1499c4f7c`;
  `airoha_eth.o` SHA256 is
  `40314361a7475811b26ae10034b0c048049e8e125b04327e56a9527f38eea74f`.
  Decompilation confirms both default-global getters, commit ordering,
  mutually exclusive direct/qdisc paths, inlined BUSY cleanup, terminal
  ownership, and balanced target references.
- Tomorrow's mandatory serial order is board identity and recovery readiness,
  V6.15/default-off mode-0 health, V6.29 default-off boot, bounded qdisc gate,
  bounded direct gate, then reboot proof. Do not jump directly to direct mode.
- Current open boundary is exact hostadpt TX ring, SKB/bufid, scatter and
  doorbell ownership; TXFREE/token/RRO interaction under FastTX; dead-WM live
  recovery; final ping-pong fate; and serial-backed performance evidence.

## Current Offline V6.30 Stock Option-Type-5 TX Topology Candidate - 2026-07-18

- **Accepted live baseline remains V6.15.** V6.16 remains rejected for mode 3.
  V6.17 through V6.30 are offline candidates and must not be described as
  live-accepted or promoted. V6.29 remains immutable and unflashed.
- Ghidra closed the stock option-type-5 static TX topology:
  - band 0 / 2.4 GHz uses group 0 at register `0xd4420`;
  - band 1 / 5 GHz aliases band 0 and group 0 at `0xd4420`;
  - band 2 / 6 GHz uses independent group 1 at register `0xd8450`.
- The active pre-V6.30 mt76 topology instead placed band 0 on HIF2/group 0,
  band 1 on the primary ring/group 1, and band 2 as a band-1 alias. The old
  disabled patch 971 corrected only labels/destinations and remains disabled
  because it did not coordinate physical DMA register windows and PHY aliases.
- V6.30 adds read-only probe-time parameter
  `w1700k_stock_npu_tx_topology`, default `0`. It acts only on a W1700K MT7996
  with HIF2 and an active WLAN NPU, and changes queue IDs, physical ring
  windows, PHY aliases, NPU group flags, and descriptor-base destinations as
  one gated operation.
- Latest image:
  `work\w1700k-stock-option5-topology-v6.30-20260718-sysupgrade.itb`.
- Image size: 20,615,996 bytes.
- Image SHA256:
  `5d786a855b946d82ddcf2d5ff873e6adf6475631679915e1ca19ab3744af18a6`.
- Checked canonical bundle:
  `FinalResult\Experimental\NpuStockOption5TopologyV630-20260718-UNFLASHED`.
  It has 22 payload/checksum entries. `SHA256SUMS.txt` SHA256 is
  `3457dddd4618257b59fc77d3e4903414f9ebd57eaa400781f737485a2b524ed3`;
  `FILE_MANIFEST.txt` SHA256 is
  `824f274029c33816bd8bf376b214036fda01bf9bfa9cc2be9215aff64dbb6c6f`.
- The sanitized NPU-enabled mt76 and full OpenWrt builds pass. Exact FIT and
  extracted-rootfs checks prove default-off autoload, both module parameters,
  required OpenWrt NPU firmware, helper syntax/persistence, and no stock
  `npu.ko`, `hostadpt.ko`, or `mt7990*.ko` payload.
- Full Ghidra analysis of the rebuilt unstripped modules independently proves
  the gate in probe, DMA allocation, PHY alias, NPU group, same-band
  descriptor-base, and debugfs register-check paths. Reproducible decompiles
  are retained under `work\ghidra-v630`.
- The internal profile remains `gemtek_w1700k-ubi`. Its fixed NAND map and
  UBI volumes match the known W1700K layout and the V6.29 FIT identity; it must
  not be renamed internally to `ubi2`.
- Tomorrow's mandatory order is COM3 board/recovery identity, V6.30
  default-off mode-0 boot/radio/traffic health, mode-3 topology-0 baseline,
  then topology-1 reboot and debugfs proof before bounded synthetic traffic.
- V6.30 closes the static ring/group/register/alias mismatch only. Hostadpt
  packet ownership, SKB/bufid and DMA lifetime, scatter lifecycle,
  TXFREE/token equivalence, end-to-end doorbell ownership, ping-pong fate,
  RRO equivalence, and serial-backed performance proof remain open.

## V6.30 Guarded Copy/Remap Ownership Reconciliation - 2026-07-18

- Continued offline. No router, flash, Ethernet, WiFi, browser, or runtime
  configuration action occurred.
- Imported the exact 122,580-byte packaged V6.30 RV32 firmware into Ghidra at
  `ram:84000000`; SHA256 is
  `51f3583c45b2c356866ee53bd79dac93e10ad069bc75ff516019ea7edb929b79`.
- Typed and decompiled the exact group poll, common descriptor worker,
  appended copy/remap trampoline, local-token allocator/release, and DMA-copy
  routine. Both group 0 and group 1 call the same worker and therefore the
  same trampoline.
- The custom firmware copy is synchronous: it programs the RV32 DMA channel,
  waits for its completion bit, acknowledges it, then resumes descriptor
  processing. This closes the static concern that Linux could unmap host DMA
  before the payload copy completes.
- Stock pre-releases its WLAN token and transfers real `skb`/DMA ownership to
  descriptor offset `0x08`. Its missing-device and invalid-argument branches
  do not consume the packet even though the caller assumes transfer; those
  branches must not be cloned.
- V6.30 instead keeps the high host token/TXWI/DMA/`skb` authoritative in the
  mt76 IDR. Descriptor offset `0x08` remains a non-owning shadow. Consumer
  release is allowed only after request-bit, changed-address, and exact
  `0x80000000` local-alias confirmation; every partial/fallback signature
  remains high-token TXFREE-owned.
- Local RV32 tokens are `0..8191`; mt76 host tokens start at 8192 while the
  NPU is active. Low TXFREE IDs are status-only and cannot remove host IDR
  entries.
- The executable model passes 756,850 checks across 97,655 event sequences,
  five firmware outcomes, and five consumer/TXFREE/flush/sweep event types.
  It proves at most one host release/unmap/free and complete teardown
  settlement for the modeled path.
- Detailed report:
  `work\W1700K_V630_HOSTADPT_TX_OWNERSHIP_RECONCILIATION_20260718.md`, SHA256
  `1a92d3797c84dba979e58ff7ac817b711ebbdc0f0c9d0ab43f18d85fab399ddc`.
- Decision: no new packet-owning patch and no V6.31 build from this pass.
  V6.30 and its canonical bundle remain immutable, unflashed, unpromoted, and
  default-off.
- The guarded V6.30 copy/remap host-resource lifetime is closed on paper.
  Exact stock pre-release parity, TX doorbell ownership, TX scatter, loaded
  TXFREE ordering, ping-pong fate, RRO, dead-WM recovery, and live performance
  remain separate unfinished claims.

## V6.30 Host-Adapter Index, Doorbell, and TX Shape Reconciliation - 2026-07-18

- Continued offline. No router, flash, Ethernet, WiFi, browser, or runtime
  configuration action occurred; COM3 remains deferred until tomorrow.
- Reconciled the Airoha provider formulas, exact prepared mt76 source, exact
  V6.30 `mt76.ko`, stock `hostadpt_tx_handler`, and exact V6.30 RV32 poll.
- Provider `qid + 2` maps mt76 groups 0/1 to stock TX banks 2/3:
  descriptor base `0xa0/0xb0`, count `0xa4/0xb4`, host producer
  `0xa8/0xb8`, and NPU consumer `0xac/0xbc`.
- `struct mt76_queue_regs` preserves offsets `+0/+4/+8/+c` for base, count,
  `cpu_idx`, and `dma_idx`. `mt76_npu_queue_setup()` installs the provider
  base; sync publishes geometry and seeds host head/tail from NPU consume;
  kick writes host producer after `wmb()`; cleanup follows NPU consume.
- Exact compiled arm64 proof finds `dsb st` before the NPU `regmap_write()`
  to offset `+0x08`, `regmap_read()` from offset `+0x0c`, descriptor stride
  `0xd0`, address at `+0x04`, shadow at `+0x08`, and owner publication after
  `dmb ishst`.
- Exact RV32 proof finds both `0xd0` group paths, both calls to the common
  worker, and consumer writes to `0xac/0xbc`. Static producer/consumer
  register ownership and ordering are therefore equivalent in V6.30.
- TX scatter is not a second descriptor protocol. The ring exposes one
  payload address. Active V6.30 preflight leaves linear SKBs alone, linearizes
  nonlinear SKBs, and rejects lengths above 8191 before DMA mapping. This is
  stricter than the observed stock one-address mapping.
- New verifier:
  `tools\verify_w1700k_v630_hostadpt_indices.sh`, SHA256
  `dfee98959006cab645186e07521c3a9d15da7d0b0749f16f2cea762198fc7871`.
  It passes exact V6.30 and rejects a one-byte-mutated module by SHA256.
- Updated doorbell verifier SHA256:
  `9590b44f9f69e4ce3750e29f1c4dc8c968eb0c653c332babc2766c629f6a293a`.
  Current TX-shape verifier SHA256:
  `bf8fdf6a54a61098724f3fbf88fdbc1e6db194d74ced51ab9bb6a2fa4dd67b14`.
- Report:
  `work\W1700K_V630_HOSTADPT_INDEX_DOORBELL_RECONCILIATION_20260718.md`,
  SHA256
  `2edd11388422baa20ad4e583dbd7f6e3cbc3a1de76c10eae62da8d5ec7bc849c`.
  Verification transcript SHA256:
  `ed57453fa78b69a8dda54eeafbd9e32fda90244a49b492561ff6c9033c0ee13f`.
- No packet-path source mutation and no V6.31 image followed. The frozen
  V6.30 bundle remains unchanged, unflashed, unpromoted, and default-off.
- Remaining TX gate is runtime queue progress, reset/recovery, loaded TXFREE
  interaction, and packet lifetime under serial traffic. RX scatter/RRO,
  FastTX/ping-pong fate, dead-WM recovery, and live performance remain
  separate. Do not revive the older blanket `tx_doorbell_ownership=not_ported`
  wording; use the narrower runtime-unproven boundary above.

## V6.30 TXFREE, Reset, and Local-Token Ownership Reconciliation - 2026-07-18

- Continued offline. No router identity, flash, Ethernet, WiFi, browser, or
  runtime configuration action occurred; COM3 remains deferred until
  tomorrow.
- Expanded exact packaged RV32 Ghidra coverage to 382 recovered functions and
  named the selector dispatcher, GET dispatcher, stop-status getter, worker
  handshakes, TXFREE parser, three pool reset/rebuild paths, and relevant
  TXdone/RRO workers. Only Ghidra project metadata changed; firmware bytes did
  not.
- Selector 4 requests fastpath, TXdone/TXFREE, and RRO refill stop. GET index
  3 reaches zero only when fastpath acknowledgement `0x3e9046f7` and
  TXdone/TXFREE acknowledgement `0x3e9046f6` are nonzero and RRO active state
  `0x3e9046e8` is zero.
- Raw RV32 instructions prove each worker clears its idle acknowledgement
  before packet/ring ownership. TXdone cannot reassert idle until the TXFREE
  parser returns; the parser releases both valid low-token branches through
  one primitive and executes `fence iorw,iorw` before ring rearm.
- Linux marks deferred reset ownership only after the zero barrier. A failed
  stop branches away before host token sweep, DMA scrub/reset, selector 6,
  local-token reconstruction, or restart.
- Selector 6 waits for TXdone/refill idle and resets distinct 16,384-entry
  general and 8,192-entry RRO pools. GET index 10 later initializes the
  external TXdone ring and rebuilds the separate local-token pool from two
  internal 1,024-entry rings.
- The local-token rebuild puts all 2,048 ring-resident IDs before allocator
  head, appends nonresident IDs, and preserves one circular-queue sentinel.
  Ring IDs cannot be allocated until TXFREE appends them at tail.
- Executable model
  `work\w1700k_v630_txfree_reset_ownership_model_20260718.py`, SHA256
  `c1a704154e659119cdd15d1d6636d473ee575e31b6696cc56001c1fc8b9350b9`,
  passes 84,683 checks over 44 reset states, 572 reset edges, and 9,840 pool
  sequences.
- Exact fail-closed verifier
  `tools\verify_w1700k_v630_txfree_reset_ownership.sh`, SHA256
  `c98500ad590b31f50cea908d93335899bc74684d8fc0ff091daf3c57f0552c1c`,
  passes prepared source, AArch64 module, raw RV32, hash, and model gates.
- Report
  `work\W1700K_V630_TXFREE_RESET_OWNERSHIP_RECONCILIATION_20260718.md`
  SHA256 is
  `ff52b7f3a9780a8e1842a8040ca00a820db424ff726aa473a4bdebe312670994`;
  transcript SHA256 is
  `0291bb100a3bac6fa7ffef7c6dedd5de8989db48540df8550d96e1809dd19d47`.
- No packet-path source mutation and no V6.31 build followed. Frozen V6.30
  still hashes to
  `5d786a855b946d82ddcf2d5ff873e6adf6475631679915e1ca19ab3744af18a6`
  and remains unflashed, unpromoted, and default-off.
- Paper closure now includes TXFREE/local-token/reset ownership. Still open:
  live reset/reboot/traffic progress, RX/RRO packet equivalence beyond its
  stop acknowledgement, FastTX/ping-pong fate, dead-WM live recovery,
  performance, and the historic mode-0 WiFi throughput ceiling.

## V6.31 RRO Fragment Ownership Hardening - 2026-07-18

- Work remained completely offline. No router identity check, flash, Ethernet,
  WiFi, browser, or runtime configuration action occurred; COM3 is deferred
  until tomorrow.
- Root cause: a malformed or truncated RRO descriptor tail could leave a
  partial fragmented SKB attached to a queue and allow a later descriptor to
  complete it. The old behavior has four generated counterexamples.
- Added
  `work\patches\9999zzzzz-mt76-harden-rro-fragment-fault-boundaries.patch`,
  SHA256
  `c633e5ebe3ac86b17f4751ff9477e85172a0f2559e67a573f4af5e7ccd7f22d5`.
  It introduces integrity fault reason 6, per-queue fragment poisoning,
  partial-head teardown, poison-until-LS recovery, common fault reporting,
  method-8 recovery without requiring an active NPU object, reset cleanup,
  and debugfs integrity/poison counters.
- Token/page integrity faults drop every partial head but retain an ambiguous
  token in the IDR until reset recovery. The descriptor element is ACKed and
  parsing stops, avoiding speculative token ownership changes.
- Executable model
  `work\w1700k_v631_rro_fragment_ownership_model_20260718.py`, SHA256
  `edb792642fc887b1ee2b1c8ad7bf088a28d27085fb67fcbeb0ecc750e1b15fce`,
  passes 19,530 fixed chains plus six cross-queue and six unknown-gap cases.
- Exact upstream mt76 and stock RV32 evidence indicate that each RRO address
  element is a self-contained head-plus-count descriptor list. Stock retries
  signature `0xff` once, then skips and ACKs the whole element. This supports
  queue-local poisoning, but it remains an evidence-backed inference rather
  than a published MediaTek descriptor contract and must be watched live.
- Focused package build passed. Exact unstripped module SHA256 values are
  `0e51f5ce861f70284773b91fce97faf0cb1e60bdb54ea45f7df26610bb83d81e`
  for `mt76.ko` and
  `eb1e3e5a82a1229c12ce5db66add608d43a4fa4b060530a2504bfa6c6d67621b`
  for `mt7996e.ko`.
- Full Ghidra analysis/import/save/decompile verification passed with 445
  recovered mt76 functions and 610 mt7996 functions. It confirms the overflow
  path, reason-6 fault route, ACK/latch stop, mode-0/no-NPU recovery,
  method-3/action-8 dispatch, and reset poison cleanup.
- Exact verifier
  `tools\verify_w1700k_v631_rro_fragment_ownership.sh`, SHA256
  `e45c4e3027c2a46c6a146e804217b964de6679738123e1b8722fc7591ef8690b`,
  passes the exact source/modules/Ghidra/model set and rejects a one-byte module
  mutation. Reproducible transcript SHA256 is
  `9202b04a87e7413381e55d0cc6513c9253a4f137ac714630e7fbf529505d444a`.
- Full source build completed successfully. Build log SHA256 is
  `670b96516772ffb2e77e0104fd83f24179d6e5e38cbb9591159e77d73202d11b`;
  the unrelated unselected `sdl3`/`libwayland` feed warning is nonfatal.
- Frozen candidate:
  `work\w1700k-rro-fragment-ownership-v6.31-20260718-sysupgrade.itb`,
  20,620,092 bytes, SHA256
  `6756f2d57e0184f362e81b93c0af17fcc67e8b23a96d0cdaaadd3b756f481ee0`.
  FIT contains Linux 6.18.34, the W1700K DTB, rootfs, and `config-1`.
  Its internal profile remains `gemtek_w1700k-ubi`; the source tree has no
  separate `ubi2` profile, so the artifact was not deceptively renamed.
- Corrected rootfs audit compares image modules against final stripped APK
  payloads and passes exact hashes. It finds 1,146 files, all four OpenWrt
  Airoha NPU firmware blobs, expected LuCI/adblock/SQM/SoftEther/wpad content,
  and no stock `npu.ko`, `hostadpt.ko`, `mt7990*.ko`, stock wpad, or stock
  hostapd payload.
- Analysis report
  `work\W1700K_V631_RRO_FRAGMENT_OWNERSHIP_REPORT_20260718.md` SHA256 is
  `d16cb35febb6bd4986eb20c8d55925f05d45c33991b9f8d3f262c19fdf9dcf7f`.
- Frozen bundle:
  `FinalResult\Experimental\NpuRroFragmentOwnershipV631-20260718-UNFLASHED`.
  It contains 37 payloads plus checksum and manifest files; independent
  checksum replay passes all 37 entries. `SHA256SUMS.txt` SHA256 is
  `1ccddb6edd8bd4e70d1ab679b2d6bff80015e82bbd52a7bda16b04a7426c4fb8`.
- V6.31 is unflashed, unpromoted, and default-off. V6.15 remains the accepted
  live baseline. Tomorrow's mandatory serial gates are identity/recovery,
  boot and memory, radio bring-up, mode-0 fault-free bounded traffic, then
  opt-in mode-3 topology/traffic/reset/reboot with integrity counters watched.
- Remaining boundaries are live concurrency and malformed-descriptor recovery,
  mode-3 queue/topology progress, full hostadpt/FastTX/ping-pong equivalence,
  dead-WM recovery, performance, and the historic mode-0 WiFi throughput
  ceiling.

## Stock Ping-Pong Production-Fate Closure - 2026-07-18

- Work remained completely offline after the user deferred serial access until
  tomorrow. No router identity check, flash, Ethernet, WiFi, browser, or
  runtime configuration action occurred.
- Added reproducible Ghidra capture for stock `hw_nat.ko`, `speedtest.ko`, and
  the fully analyzed 29,042-function stock kernel. The project was saved with
  all 14 open programs; the capture manifest SHA256 is
  `6641e8c0ee38d15b3e42e2ca024a9d7448710ff57c858021202a92026acf90ab`.
- Recovered stripped-kernel PREL32 exports. `left_to_right_test_mode` is at
  `0xffffffc010d580c0` in zero-initialized `.bss`. Across 134 modules only
  `hw_nat.ko` imports it, all six low relocations are `LDR W` reads, no stock
  userspace reference exists, and Ghidra finds no built-in kernel xref.
- Production conclusion: value-1 bridge and value-2 WLAN/netif paths are
  dormant vendor test facilities. Old post-token mt76 ping-pong patches remain
  quarantined; no control for these modes should be exposed or revived.
- Ghidra confirms `GET_HIR()` reads the upper 16 bits of the SoC register at
  offset `0x64`. Exact HIR identity is not a production ping-pong blocker when
  the companion test-mode global remains zero.
- Stock preinit does load `speedtest.ko`. Its init publishes three callbacks
  with `STLR`, cleanup clears them with `STR XZR`, and its ping-pong callback
  sends through `wan_dev` or frees the SKB. `hw_nat.ko` invokes this facility
  only for synthetic VirIf values `0x130` and `0x160`, not ordinary FastTX.
- The production-relevant ordinary packet boundary remains QDMA RX reason
  `0x16`, RX-info tag `0x7275`, before `eth_type_trans()`. Active V6.31 patches
  `999-57`, `999-60`, `999-67`, and `999-68` model it in the correct subsystem;
  the consumer and direct path remain independent default-false gates.
- Added executable fate model SHA256
  `b70a0b4cf7544ebb8deefeb94d77a2f69efd3ae2247cc9b90fc371707c25c586`
  and exact verifier SHA256
  `94a30fc209a567b39855a5d1c44d795d7d2b058345f95b680b0b76075c7988e3`.
  Verification passes 62 checks with zero failures; transcript SHA256 is
  `8810dd65a3683137219ba3d0def76b5bc500aafbf5d11c027ee23298ca7338ef`.
- Report
  `work\W1700K_STOCK_PINGPONG_PRODUCTION_FATE_RECONCILIATION_20260718.md`
  SHA256 is
  `90566fa504460cfdb521e6ebba7b38df0bd5278365ae95338151fe1b5b199ee3`.
  Independent checksum replay passes every listed evidence artifact.
- No packet-path source mutation, build, V6.32 image, promotion, or router
  action followed. V6.31 remains byte-identical at SHA256
  `6756f2d57e0184f362e81b93c0af17fcc67e8b23a96d0cdaaadd3b756f481ee0`,
  unflashed, unpromoted, and default-off. V6.15 remains the accepted live
  baseline.
- Static ping-pong branch fate is now closed. Live FastTX consumer/direct
  behavior, counters, ownership faults, memory, and throughput remain serial
  gates, together with RRO recovery, mode-3 topology, dead-WM recovery, and
  the historic WiFi throughput ceiling.
- Frozen analysis-only bundle:
  `FinalResult\Analysis\NpuStockPingPongProductionFate-20260718-OFFLINE`.
  It contains 36 evidence payloads plus two bundle manifests, 38 files and
  993,629 bytes. Three-level checksum replay passes. Bundle checksum SHA256 is
  `f840bd56ff79cba9379910e96bda1c074c5c9e30c9bd17be1754eba3cf3a80e0`;
  file-manifest SHA256 is
  `b64f8aa7e1d84019eb2ccf31eb8d7db113ff891caa171ec9dfe4859f775cfe45`.

## Stock Dead-WM / Action-5 Reset Boundary - 2026-07-18

- Work remained completely offline. No router identity check, flash,
  Ethernet, WiFi, browser, or runtime configuration action occurred; COM3 is
  deferred until tomorrow.
- Ghidra MCP health passed with Ghidra 12.1, plugin 5.13.1, and 204 endpoints.
  A reproducible capture saved 23 critical stock SER/reset functions from
  `mt_wifi.ko`, `mtk_hwifi.ko`, `mt7990.ko`, and `mtk_pci.ko`; the nested
  capture checksum-list SHA256 is
  `def7692cd70fc67856edb01c01f0115f68858d75252f51194ba55832f193e50f`.
- Headless Ghidra exhaustively decompiled all 8,534 stock `mt_wifi.ko`
  functions with zero failures. It found 13 calls to `asic_ser_handler` with
  action counts 0=2, 1=1, 2=4, 6=2, 7=2, 8=1, and 9=1. Action 5 has zero
  callers. The audit SHA256 is
  `9613bd94dd3d0f4668ddff45c42c131c7205b219e328d99e8728f9934fec9840`.
- A separate fresh full Ghidra import of `connac_if.ko` proves that action 5 is
  implemented and dispatches through the hardware-device callback at `+0xa8`.
  The downstream chain reaches the chip callback at `+0x28`, then writes 1
  and 0 to BAR0 offset `0x1f8600` through the PCI callback. The decompile
  SHA256 is
  `b1416550fb759b1904e11c592f2e69cc6859b41ef7fdff701d6c99e986209538`.
- Production stock control flow does not wire that primitive to dead-WM
  recovery. Recovered manager levels are 0, 5, 10, 50, 51, and 100; none
  selects action 5. Level 100 sends WM method 8 and therefore still needs a
  responsive WM. `ser_sys_reset()` is an unreferenced no-op, and the firmware
  assert event handler only parses and logs diagnostics.
- V6.31 already has the safer order: close producers, stop/quiesce NPU, sweep
  tokens, scrub/reset DMA, load firmware, and reinitialize NPU. Its raw BAR
  pulse is allowed only after firmware preparation, or after NPU quiescence
  plus the explicit `w1700k_recovery_allow_unprepared_cbinfra` diagnostic
  gate. The gate is static, defaults false, and failure remains isolated.
- Added executable reset-state model SHA256
  `06e665d7827fcdcb9720b95891fb22f112c61686e4ad0514f717147104d5a535`
  and exact verifier SHA256
  `c4a300450694f05e868fe7e393fb8883a0442ca591da084804cfe1913eb140d9`.
  Result: 108 passed, 0 failed,
  `PASS_STOCK_DEAD_WM_RESET_BOUNDARY_DEFAULT_OFF`; transcript SHA256 is
  `4703021529b765b968b57602fe4f7b66767cda316dcae2b8f38c93c08dbbe2fb`.
- Report
  `work\W1700K_STOCK_DEAD_WM_RESET_RECONCILIATION_20260718.md` SHA256 is
  `27cff11cc03f40221d3289054f33b7e1a20c5919564c575aaa6e68fb78eaa6d5`;
  outer evidence-list SHA256 is
  `dfc9dc6cf2deaa97d2ef14a141ca457fcae4cdf5e05a028d909a1cb12035a877`.
- Frozen analysis-only bundle:
  `FinalResult\Analysis\NpuStockDeadWmResetBoundary-20260718-OFFLINE`, with
  67 evidence payloads plus two manifests, 69 files and 617,927 bytes.
  `BUNDLE_SHA256SUMS.txt` SHA256 is
  `9a26a4fafd1120278755af527836c30053b092d8ddfee2b5b5bd4f7cd982d615`;
  `BUNDLE_FILE_MANIFEST.txt` SHA256 is
  `3e52b8a18701ca154ea7ef78bf53c29699289fe566ecfc09b9cb417ddf866353`.
  Independent outer, bundle, and nested-capture checksum replays pass.
- Decision: no source mutation, rebuild, V6.32 image, promotion, or router
  action. V6.31 remains byte-identical at SHA256
  `6756f2d57e0184f362e81b93c0af17fcc67e8b23a96d0cdaaadd3b756f481ee0`,
  unflashed, unpromoted, and default-off. V6.15 remains the accepted live
  baseline.
- Remaining live boundary: after identity, boot, memory, radio, mode-0, and
  guarded mode-3 baselines, COM3 may test the existing RAM-only diagnostic
  gate and confirm that the corrected BAR pulse reaches firmware-download
  state. Until that proof exists, unprepared raw reset stays default-off.

## COM3 Preflash Recovery Boundary - 2026-08-05

- COM3 is present as a Prolific PL2303GC adapter at 115200 baud. Live serial,
  NAND geometry, UBI inventory, PCI IDs, and Linux DT identify the target as a
  Gemtek W1700K with Winbond 512 MiB SPI NAND, MT7990, and MT7991.
- The installed image is not a usable live baseline. It reproducibly panics
  while loading `cfg80211`, at `cfg80211_register_netdevice()` through
  `register_netdevice_notifier()`, then warm-reboots. Its FIT contains Linux
  6.18.34, a 5,846,176-byte kernel, and a 14,745,600-byte rootfs.
- The modern OpenWrt chainloader was entered explicitly and verified the
  installed FIT hashes. It then TFTP-loaded and hash-verified the 18,350,080
  byte initramfs recovery image (SHA256
  `c121b33c14f83f59f95483905d98e4639a9275da19384e299c80b92c5baa3fda`).
  Recovery booted successfully in RAM and identified `gemtek,w1700k-ubi`.
- Recovery subsequently exited before the NAND backup and sysupgrade gates
  completed. Warm reboot consistently wedges the vendor loader after
  `usxgmii_pcs_int en 1`; a physical reset reaches the normal chainloader, but
  the first reset was intercepted too late and booted the bad FIT again. A
  fresh catcher then waited 900 seconds without another reset.
- No NAND write, UBI volume mutation, factory/calibration write, sysupgrade
  test, or V6.31 flash occurred. V6.31 remains byte-identical at SHA256
  `6756f2d57e0184f362e81b93c0af17fcc67e8b23a96d0cdaaadd3b756f481ee0`,
  unflashed and unpromoted. Next action is one physical reset with the fresh
  COM3 catcher already running, followed by backup, `sysupgrade -T`, and
  clean `sysupgrade -n`.

- Live evidence is under
  `work\live-captures\serial-preflash-20260805-003113`. Key SHA256 values are
  `ac4de1ee7ecaaa1c8f70cdccd7dcda877915cd5e2ffcae23d59e05098daa5189`
  for the complete bad-image boot/panic capture and
  `9546fe7bcf5db1c9ddd28d0b064d9040352d5de33cfc367ee1d235255651358d`
  for the successful RAM-recovery boot capture.

## cfg80211/net_device ABI Root Cause And V6.31 Gate - 2026-08-05

- Exact FIT fingerprints identify the installed crashing image as rejected
  V6.16 R2 netconsole diagnostic SHA256
  `41ef432a944e8155a6b3f1a6ea9d8e66ccaa6ceb13ebe447bd4e43698ee72be1`,
  not V6.31.
- Exact `cfg80211.ko` disassembly shows
  `cfg80211_register_netdevice()` loading `dev->ieee80211_ptr` from byte offset
  976. A kernel-built layout probe reports 976 without NETPOLL and 984 with
  NETPOLL. The rejected kernel contains the netpoll symbol set, so its module
  reads one pointer early and feeds a bogus wireless-device/wiphy mutex to
  `queued_spin_lock_slowpath()`.
- Added an exact image-level promotion gate under
  `tools\w1700k-netdev-abi-probe`,
  `tools\verify_w1700k_netdev_abi.py`, and
  `tools\run_w1700k_netdev_abi_gate.sh`. The V6.31 verification runner now
  invokes it before the RRO ownership checks.
- The gate extracted V6.31's exact kernel and rootfs. Candidate kernel SHA256
  `690016fa7ca3277db033e5be4536f4367314bc0b8a8524b4abd5b3608e50401e`
  is byte-identical to the probed source-tree `Image`; candidate cfg80211 and
  kernel both use offset 976; NETPOLL and NETCONSOLE are disabled. Result:
  `PASS_NETDEV_ABI_IMAGE_GATE`.
- Full V6.31 verification and deliberate module mutation rejection pass.
  Transcript SHA256 is
  `4c612eff9d9b10884f00ca25a6669f56ba102867561db9d293be7011767ebc6f`.
  Root-cause report SHA256 is
  `785c2a908c4a02950d658086190b5bc04d0193574f6936eac95acc284ce31a0a`.
- V6.31 remains byte-identical at SHA256
  `6756f2d57e0184f362e81b93c0af17fcc67e8b23a96d0cdaaadd3b756f481ee0`,
  unflashed and unpromoted. The ABI failure mode is cleared statically; live
  boot, radio, mode-0, and guarded mode-3 gates still require RAM recovery.
  No NAND or UBI write occurred.

## V6.32 Source Reconciliation Candidate - 2026-08-05

- Reconciled the current source at OpenWrt commit
  `5575e4a97f119f682223a090c4a78c0913f906f5`. The NPU mode helper now keeps
  only the supported `npu_stock_copy_mode` write path, rejects retired mt76
  controls, and scrubs stale module arguments. Helper SHA256 is
  `955cab542f239399f2f2ff6ebf2c81b4199c3511bcaf7c3a4d5838e182bd2ac5`;
  fixture SHA256 is
  `49c9085073e6805f2659ea1bc3ff14f1e2dc67faafec44bc73626642c7b107cb`.
  The exact helper extracted from the candidate passes its fixture.
- Fixed a real dual-configuration mt76 build bug in
  `9999zzzzz-mt76-harden-rro-fragment-fault-boundaries.patch`: unconditional
  RRO call sites lacked no-NPU stubs for `mt76_npu_rx_fault_latched()` and
  `mt76_npu_rx_fault_report()`. The disabled path now returns false/no-ops,
  while `CONFIG_MT76_NPU` still resolves the real exported implementation.
  Patch SHA256 is
  `01eb14c4494a03b773dff46d4803491b210a14ebe595dc46cc052ff4f3deb3c4`.
  Strict checkpatch is 0 errors, 0 warnings, 0 checks.
- Clean baseline and experimental mt76 compiles both pass. The experimental
  log proves `CONFIG_MT76_NPU=y`, `CONFIG_MT7996_NPU=y`, and both CPP defines.
  Log SHA256 values are
  `946e77c31ecf1d61e54674c67a78d3f03678b6d359218e93212af5574f34cd49`
  and
  `1faeabd14a9d9d6e2a60c58857be4d7df3accdfb86881aa86cdf48514179a555`.
  The complete clean-PATH image build passes; log SHA256 is
  `f5ccdff6b251030218b8c06f9c86ac988946cbf33179af696af0056a4c8fb99a`.
- Frozen offline candidate:
  `work\w1700k-rro-fragment-ownership-v6.32-20260805-sysupgrade.itb`,
  20,615,996 bytes, SHA256
  `30352f9a8aa84c4447352c87c89346f6bc8b553a82fb49c36eb56bc76f091cb1`.
  It is the `gemtek_w1700k-ubi` FIT and leaves 81,092 bytes in the recorded
  20,697,088-byte fit volume.
- Exact FIT/rootfs audit and cfg80211 ABI gate pass. Kernel SHA256 remains
  `690016fa7ca3277db033e5be4536f4367314bc0b8a8524b4abd5b3608e50401e`;
  cfg80211 and kernel both use `net_device.ieee80211_ptr` offset 976 with
  NETPOLL/NETCONSOLE disabled. Shipped mt76 and mt7996e SHA256 values are
  `a08d3661c4228ca015415ff529946f105abd2b9f3b78a12325f0ac7420e923a0`
  and
  `b5b29f46b92da0f1582ec50c8df2ce489c6a837b03f3bbbb8a7e6098464c7ad2`;
  both are byte-identical to V6.31. Every allocated runtime ELF section in
  the unstripped modules also matches the fully analyzed V6.31 Ghidra inputs;
  only `.note.gnu.build-id` differs.
- Rootfs tree shape is unchanged. The only content differences from V6.31 are
  `/usr/sbin/w1700k-wlan-npu-mode` and APK database metadata
  (`installed`, `scripts.tar.gz`). Patch-corpus audit covers 6,364 patches;
  all 148 active/local and 323 disabled experimental patches are structurally
  clean, with the 111 remaining findings confined to upstream patches.
- Frozen-candidate verification passes. Transcript SHA256 is
  `bf16554e80e47cac113520f93ae17634dd725a7aa8c123d6199ecc728963a911`;
  checksum manifest SHA256 is
  `5e114eb539845f388ebf5fc405b376da0892d8a5238d475e5a07205271e70ec9`.
  The reusable ELF comparator and V6.32 gate SHA256 values are
  `601329be42b283b46ed6a6e29d0ef6e500e9f65f6419147cd43db4331b85facc`
  and
  `da9c47dbfe4fd9c501c0b73414b2cd9a5b3da3c6aae853c06d5b39ce8a0aa764`.
- Live state is unchanged. Two armed cold-capture windows (300 and 600
  seconds) received zero COM3 bytes, Ethernet never dropped, and PL2303
  DTR/RTS pulses did not reset the target. V6.32 is frozen as the preferred
  next flash candidate but is not an accepted live baseline or FinalResult
  promotion. No NAND, UBI, bootloader, environment, factory, or calibration
  write occurred. Resume with a true cold power cycle while the catcher is
  already armed, then RAM recovery, immutable backup, `sysupgrade -T`, and
  clean `sysupgrade -n`.

## V6.33 Upstream mt76 Rebase And Armed Recovery - 2026-08-05

- The mt76 source was advanced from
  `59676919ea408b0b13a9d23f2e2e1a1ab407fba1` to official upstream
  `b2704cf5a4068b672bf47ad5bf6b4802b6770a90` (2026-08-01). All 74 local
  mt76 patches map one-to-one across the rebase with no additions or drops.
  The old replay produced 101 fuzz/offset messages. The git-based rebase maps
  every patch one-to-one and applies strictly without additions or drops, but
  the OpenWrt `patch` replay still emits line-offset relocation messages. The
  corrected replay boundary is recorded in the V6.34 section below.
  Range-diff SHA256 is
  `f007e85bc0035bb9b529a704834ad1e75a37fa3dfeb217dc78e3da5ed8fa884a`.
- Three intermediate artifacts are explicitly rejected and retained only as
  negative evidence: one omitted WLAN NPU support, one omitted W1700K WLAN
  NPU firmware through stale profile metadata, and one retained stale
  readline compatibility libraries. None is eligible for flashing.
- Frozen V6.33 candidate:
  `work\w1700k-mt76-upstream-v6.33-20260805-sysupgrade.itb`, 20,615,996
  bytes, SHA256
  `8363ca764cd14a749a1731235df6d6b012d725063fd148ac6d7834c410122c52`.
  It is the `gemtek_w1700k-ubi` FIT and leaves 81,092 bytes in the recorded
  fit volume. The rootfs contains 1,146 files and no stock `npu.ko`,
  `hostadpt.ko`, or `mt7990*.ko` binaries.
- Shipped mt76 and mt7996e SHA256 values are
  `52ebe133644c30c40a2021d1629fbfefdfbe8601d203ebc05c9f81ce4ef03a83`
  and
  `a605d1a57a4f89b70bc1ae627d90d59398cb24757e3b70f21531a3e8ea3635c1`.
  Exact FIT/rootfs, firmware/package, forbidden-binary, cfg80211 ABI,
  patch-corpus, Ghidra, LuCI, width, wireless-validator, and NPU-mode gates
  pass. Final verifier summary SHA256 is
  `e5c056661322398255a6ccf89360de04f4ca3121d7de5c867107156cb6d31f14`.
- Full Ghidra analysis completed for the exact unstripped mt76 and mt7996e
  build inputs: 443 and 614 functions respectively. Report SHA256 values are
  `7bdb505286c1fc11ee52577ba368c61373c4f1ca31b5658179c5ec55f5bde9cc`
  and
  `47fbfd69fcbf2f117135e62c6084ad1cdf9ab8166ce44a60f4d36598956c6c92`.
- The canonical source tree now carries the real mt76 mirror hash
  `479f2f24bca79ba5364f17a15b856cfd9414efaeed025d04bfde14d0c96e4fd4`,
  all 74 rebased patches, and the three refreshed Airoha target patches. A
  clean canonical compile passes; every allocated runtime section matches the
  candidate build, excluding only `.note.gnu.build-id` metadata.
- The V6.33 recovery catcher is armed at
  `work\live-captures\v633-recovery-20260805-081849`. Its exact-artifact and
  host preflight passed, COM3 is open at 115200 8N1, and the read-only TFTP
  service is bound to the Ethernet link-local address. The reported reboot
  produced zero serial bytes, so RAM recovery, backup, validation, and flash
  gates did not run. No NAND, UBI, bootloader, environment, factory, or
  calibration write occurred. V6.15 remains the accepted live baseline.

## V6.34 MLO Active-Link And Idempotent CA Candidate - 2026-08-05

- Root-caused a custom MLO TX selection defect. Policies 1 and 2 considered
  `sta->valid_links` without requiring the selected link to remain in
  `vif->active_links`, so they could queue to an inactive or `sta_disabled`
  WCID that the scheduler would skip. Patch
  `9999zzzzzz-mt7996-filter-custom-mlo-active-links.patch`, SHA256
  `1fe09f410c922391a793b715135ae6d147b0e7866e5f62254c705f568b68184f`,
  intersects valid and active masks, rejects unavailable WCIDs, and preserves
  the current WCID when no eligible custom-policy target exists. Upstream
  policy 0 is unchanged.
- Exhaustive model verification passes 884,736 cases, including 589,824
  custom-policy cases and 486,000 no-eligible cases. Full Ghidra analysis of
  the exact unstripped mt76 and mt7996e modules reports 443 and 615 functions.
  Report SHA256 values are
  `200861e671722d0c765e1b011152a713742a94a118ab192af4b4666325b967f8`
  and
  `59f9647a1a2a1affa9757999b4b3373d5f6f4dbbe04d5d7fa7c25d5783aae44c`.
  The decompile proves the active-link intersection and fail-closed result.
- Rejected the first V6.34 image after finding 241 CA PEM blocks but only 121
  unique certificate hashes. Added an idempotent package compile guard,
  SHA256
  `42cc1072dfe880439b199fe2b525d73551310ee48c97c83d7f0852ef6dc29ced`,
  which removes generated Mozilla certificates before regeneration. Forced
  package re-entry now yields 121 files, 121 unique hashes, and 121 PEM
  blocks. The final bundle is 182,140 bytes, SHA256
  `9481fcd95f41b221f02f14d896535fe500bec539bc563c4cdca1acee483a8bdd`.
- Frozen V6.34 candidate:
  `work\w1700k-mlo-active-link-v6.34-20260805-sysupgrade.itb`, 20,615,996
  bytes, SHA256
  `45b00fd31cb91492678091bb768abf1d47833eb7e0b149b262b16a7998cc3a21`.
  It uses `gemtek_w1700k-ubi` and leaves 81,092 bytes of fit-volume headroom.
  The duplicate-CA image SHA256
  `992c58f930e2df47adc185f4196cb2012ceb3324c379fd479b7f1a80c242e517`
  is explicitly rejected; clean pre-source-fix evidence SHA256 is
  `63cfa1d5362d23353f610a38681059bc532996a20631c53d4602a42fe5dace30`.
- Exact candidate verification reports `PASS_V634_CANDIDATE`. Rootfs shape
  matches V6.33 with 1,146 files; only the canonical APK key, APK database
  metadata, scripts archive metadata, and `mt7996e.ko` differ. The kernels
  differ by exactly two 20-byte GNU build IDs and are byte-identical after
  normalization. DTB is identical. cfg80211 ABI passes at offset 976 with
  NETPOLL/NETCONSOLE disabled. Selected APK signatures, production assets,
  forbidden-binary checks, fixtures, and the runtime-gated default-off NPU
  mode contract pass. Verifier SHA256 is
  `434ac04d55862b230cf0d462502b03e70126ce054832de91f53f2e012da568d6`.
- Replay wording correction: strict git-based patch mapping/application is
  clean, while the final 75-patch OpenWrt replay has zero fuzz, zero rejects,
  and 205 line-offset messages. Previous V6.33 wording that said there were
  no offset messages was too broad.
- Frozen offline evidence bundle:
  `work\candidate-bundles\W1700K-V6.34-MLO-Active-Link-20260805-OFFLINE`,
  36 files and 39,132,095 bytes. Payload checksum-list SHA256 is
  `680d10ac157c12af2edff6fb94ef6cfb80b7fa036f67c973bea4baecfd23e7a9`;
  manifest SHA256 is
  `02f8b6d2da4f9871707ef65ec13501a5fd46d602889576565ebd54a4114758ed`.
  Both checksum replays pass. Report SHA256 is
  `2bae7cd13dc03f60e3c2ca96df9ef8a4065f75a30b3dad1f3f8bb22e8424aeaa`.
- Live state did not advance. The active COM3/TFTP catcher remains healthy,
  but `serial.raw` is still zero bytes after the reported reboot. V6.34 is
  unflashed and is not a live baseline or FinalResult promotion. No NAND,
  UBI, bootloader, environment, factory, or calibration write occurred.

## V6.34 Live Recovery Harness Refresh - 2026-08-05

- Retired the stale V6.33 catcher and created
  `work\w1700k-com3-recover-v634.ps1`, SHA256
  `fb7bd49db8e9faa6fc28347218833d5e5ad9af0c30cb09caee2ee178e7c4c56c`.
  It pins the exact V6.34 image and frozen verifier result, checks the final
  mt76/mt7996e hashes, and preserves the RAM-recovery, raw-backup,
  `sysupgrade -T`, and postboot gates. Its standalone preflight passes.
- The completed cold-cycle diagnostic yielded zero COM3 bytes. Windows still
  reports the PL2303GC adapter on COM3 as present and healthy; an independent
  115200 8N1 probe with DTR/RTS disabled also received zero bytes. Ethernet
  retained 1 Gbps carrier but exposed no IPv4/IPv6 peer, and a blind sequence
  limited to bootloader interruption, flash read, RAM TFTP load, and boot
  commands produced no TFTP request.
- The active exact V6.34 catcher is
  `work\live-captures\v634-recovery-20260805-100740`. Preflight passed,
  read-only TFTP is bound to `169.254.66.29:69`, and COM3 is open at 115200
  8N1. `serial.raw` remains zero bytes. No U-Boot, RAM recovery, backup,
  `sysupgrade -T`, flash, or postboot gate has run; V6.15 remains the accepted
  live baseline and no NAND, UBI, bootloader, environment, factory, or
  calibration write occurred.

## V6.34 Post-Reboot Serial Reopen - 2026-08-05

- Retired the zero-byte `v634-recovery-20260805-100740` process after the
  reported reboot, then reopened COM3 independently at 115200 8N1 with DTR
  and RTS disabled. An eight-second probe that sent only Enter received zero
  bytes; the capture is
  `work\live-captures\v634-recovery-20260805-100740\direct-probe-after-reboot.raw`.
- Link-local source-bound probes still found no Ethernet peer. A fresh exact
  catcher is armed at
  `work\live-captures\v634-recovery-20260805-102122`; preflight passed,
  read-only TFTP is listening on `169.254.66.29:69`, COM3 is open, and
  `serial.raw` remains zero bytes. This is a physical UART/peer-visibility
  boundary, not firmware validation. No U-Boot, recovery, backup,
  `sysupgrade -T`, flash, or postboot gate has run; V6.34 remains unflashed,
  V6.15 remains the accepted live baseline, and no NAND, UBI, bootloader,
  environment, factory, or calibration write occurred.

## V6.35 MLO TX Ownership Alignment - 2026-08-05

- Root-caused a remaining policy-0 MLO ownership split. mt76 could derive the
  PHY/queue from the setup WCID before mt7996 retargeted the TXWI, so queue,
  non-AQL, NPU completion, and TXFREE identities could diverge. Patch
  `9999zzzzzzz-mt7996-align-all-mlo-tx-policies.patch`, SHA256
  `c39aae62009a05bee4c261f656dfe610b6969b4ace776580ffc1957c4a9015e3`,
  selects an eligible station-valid, VIF-active, enabled WCID before queue
  derivation for policies 0, 1, and 2. Teardown races now return `-ENOLINK`
  before token allocation. Policy 2, prefer 5/6 GHz, is the default.
- Patch `9999zzzzzzza-mt7996-forward-full-eml-cap.patch`, SHA256
  `dc7048b7fae4c05c319cb22fe3275dd0d1f7a293c8a92e6f69c16819689911ec`,
  forwards the complete negotiated 16-bit peer EML capability to
  STA_REC_EHT_MLD. This matches the stock field-copy boundary but does not
  claim EMLMR runtime support.
- Exhaustive ownership verification reports `PASS_V635_MLO_TX_ALIGNMENT`
  across 5,308,416 checks, three radios, eight TIDs, all valid/active/disabled
  masks, link-to-band permutations, and teardown races. All WiFi, width,
  validator, NPU-helper, and JavaScript fixtures pass. Both patches pass
  strict checkpatch with zero findings.
- Rejected and quarantined the first build, SHA256
  `b744a342d25be57d422f2726b3713c3b09f5406710d57ae830d59dba42e9c9ae`,
  because the build command omitted `W1700K_EXPERIMENTAL_MT76_NPU=1` and the
  embedded mt76 module lacked the Airoha NPU transport. No rejected image was
  flashed. `work\run_v635_build.sh` now pins the NPU gate and a Linux-only
  build PATH.
- Accepted offline image:
  `work\w1700k-mlo-tx-aligned-v6.35-20260805-sysupgrade.itb`, 20,615,996
  bytes, SHA256
  `2e0ff1abd37cc0a971ca3e89b4f38c5fc79e3245e8b801452f74619219625da1`.
  FIT profile is `gemtek_w1700k-ubi` with 81,092 bytes of headroom. Kernel and
  DTB are byte-identical to V6.34; the NPU-enabled mt76 module is also
  byte-identical. Rootfs shape and package contracts are unchanged. Only
  mt7996e, the NPU helper, LuCI page, and their APK bookkeeping differ.
- Exact verification reports `PASS_V635_CANDIDATE`; verifier SHA256 is
  `1277fd206fdfc6b1e0fd25352d662307a219071803aa76310cf2c13f1d840934`
  and result SHA256 is
  `e0e68cb1dffef2beb93e095bddadf19b046aa05f5a9d24fe99a39dbc85ea6152`.
  Fresh Ghidra 12.1.2 full analyses of exact unstripped mt76 and mt7996e
  passed. Report SHA256 values are
  `78b8719f43811834bdba9b1e75b7425ee689cfe23608bfb37356048809883a6a`
  and
  `32bc58137772786d4333917674face7ebdd1ea01f6af83f2277701dccfc5bb9a`.
- Frozen bundle:
  `work\candidate-bundles\W1700K-V6.35-MLO-TX-Alignment-20260805-OFFLINE`,
  28 files and 27,448,190 bytes. Payload checksum-list SHA256 is
  `03002326a2734005f4c2837099f0155a21f0b3028acf77c70bd69c08814f0267`;
  manifest SHA256 is
  `ff11ed88e8be8b4ea6bf5f5795dd54e228bfbc5658f1bfd3dec3efa882fc7f35`.
  Replay passes. FinalResult contains the accepted image, manifest, report,
  and SHA256 list; it does not contain the rejected build.
- Recovery harness `work\w1700k-com3-recover-v635.ps1`, SHA256
  `44be37cb2ca5097a1619e5de4b38d6691129aa09e5911b5e2d63b00213ae92a6`,
  passes non-writing preflight and pins exact image/verifier/module hashes plus
  MLO policy/ownership postboot gates. COM3 still returned zero bytes after
  the reported reboot and a six-second Enter probe. Ethernet has 1 Gbps
  carrier but no IPv4/IPv6 peer. V6.35 remains unflashed, V6.15 remains the
  accepted live baseline, and no NAND, UBI, bootloader, environment, factory,
  or calibration write occurred.

## V6.36 NPU Hot-Path Hardening - 2026-08-05

- Added three mt76 patches with strict checkpatch and clean prepare/compile
  results: post-padding TX length validation, one-completion-per-poll RX
  batching plus first-fragment hardening, and a default-off detailed NPU
  trace gate. Patch SHA256 values are
  `d8709564e57fc6a43c208680c10108c9ba2f44d686175d52870b23cca7c2df88`,
  `f88090a14c67abae7b44f5edcdba4900c27351eb6d50d42a885240bd6ef66992`,
  and
  `1c209599df624772686fc6db0c6c897bace4aa546725e2123d1ea393698bd623`.
- Pinned full build passed with `W1700K_EXPERIMENTAL_MT76_NPU=1`. Accepted
  offline image is
  `work\w1700k-npu-hotpath-v6.36-20260805-sysupgrade.itb`, 20,615,996 bytes,
  SHA256
  `c7a3120d8a20816b58fa5011a8032ed654dff45540b18876ee61a8bcbe7a5eb9`.
  FIT profile is `gemtek_w1700k-ubi` with 81,092 bytes of headroom.
- Exact gate `PASS_V636_CANDIDATE` binds source commit, patches, build log,
  module ABI, Ghidra reports, FIT/rootfs delta, package contracts and
  signatures, firmware, and forbidden-binary checks. Kernel and DTB are
  byte-identical to V6.35. Rootfs shape remains 1,146 files; only mt76,
  mt7996e, the NPU helper/LuCI page, and APK bookkeeping changed.
- Full Ghidra analysis passed for exact unstripped mt76 and mt7996e inputs.
  Reports contain 445 and 614 functions with SHA256 values
  `4a468209480cee4e9d586f46ed5a9b34289597484d073a4f9bee1abffba1ca04`
  and
  `4d8ae42364846161c8ebcde3c4df1c1e756846a08d0e05c38b1ff6d29319972e`.
- Frozen bundle:
  `work\candidate-bundles\W1700K-V6.36-NPU-Hotpath-20260805-OFFLINE`, 27
  files and 29,450,568 bytes. Payload and manifest SHA256 values are
  `cd4653694db40d068545d02a8253f5ba3eb764f136496e5ea7553f6414599cf1`
  and
  `7af8d59410c3e281e5d12b6dfc20bd559a152092fa848ec02e9ba88ed6684a95`;
  checksum replay passes.
- Live state did not advance. COM3 remains zero-byte after the reboot probe;
  Ethernet has 1 Gbps carrier but no peer or management address. V6.36 is
  unflashed, V6.15 remains the accepted live baseline, and no NAND, UBI,
  bootloader, environment, factory, or calibration write occurred.

## V6.37 NPU MAC-TXP DMA Device Pairing - 2026-08-05

- The post-V6.36 TX lifetime audit found a concrete NPU-specific DMA API
  violation in mt7996 AddBA/MAC-TXP cleanup. NPU queues map payloads through
  the Airoha NPU platform device and record it in `t->payload_dma_dev`, but
  `mt7996_txp_skb_unmap()` hardcoded the PCI `mdev->dma_dev` for MAC-TXP.
  AddBA action frames can use NPU queues, so the old path could map through
  the NPU device and unmap through PCI.
- Patch `9999zzzzzzze-mt7996-fix-mac-txp-payload-dma-unmap.patch`, SHA256
  `7b5a404a2d7823b8a439af01a0d93cde1a86f5dcfe60947afea2db2493f33c5e`,
  uses `mt76_txwi_payload_dma_dev(mdev, t)`. This preserves the PCI fallback
  but pairs every MAC-TXP unmap with the device recorded before mapping.
- Executable source/ownership verification reports
  `PASS_V637_DMA_DEVICE_PAIRING checks=48` across PCI/NPU queues,
  NPU-device-present/fallback states, firmware/MAC TXP, and TXFREE,
  NPU-consumer, and token-sweep completion paths. Strict checkpatch reports
  zero findings; clean prepare and compile pass.
- Fresh full Ghidra 12.1.2 analysis passed on exact rebuilt mt76 and mt7996e.
  The analyzed/final unstripped mt7996e SHA256 is
  `93d0eaf81d3bb5f1a42699382a180561316c16637b3f8a16565ae6c42da654db`.
  Decompilation resolves the recorded device at `t + 0x18`, null fallback at
  `dev + 0x858`, and selected pointer passed to the DMA unmap. mt76/mt7996e
  report SHA256 values are
  `491fb11a4d17151bf2ff204fedd7addae1aededdfc93ff0ce6bbeb4a96ed6892`
  and
  `e7f844a853bb83d35885f1ef6de7f6609f1cd7f479ca7c6426306d2ea4e52d2b`.
- Accepted offline candidate:
  `work\w1700k-dma-pairing-v6.37-20260805-sysupgrade.itb`, 20,615,996 bytes,
  SHA256
  `760b203ef1fdc9921a2d75670da3a298df38b014d137710b12f679f5ef3b1ff0`.
  `PASS_V637_CANDIDATE` confirms `gemtek_w1700k-ubi`, 81,092 bytes FIT
  headroom, byte-identical kernel/DTB, unchanged 1,146-file rootfs shape and
  package contracts, required NPU firmware, selected APK signatures, and no
  forbidden stock binaries. Only embedded mt7996e plus equivalent APK
  bookkeeping differs from V6.36.
- Frozen bundle:
  `work\candidate-bundles\W1700K-V6.37-DMA-Pairing-20260805-OFFLINE`, 28
  payload files and 28,739,417 bytes. Payload-list and bundle-manifest SHA256
  values are
  `494458ab7891d11becf58f75241625b3638e596b6e76b8adb206d6bcac902dde`
  and
  `6c030b920b76b197ad427529f0472f06c97acc15416fd1551930dee805d19075`;
  checksum replay passes. FinalResult mirror is
  `Experimental\DmaPairingV637-20260805-UNFLASHED`.
- The latest reported reboot did not restore a recovery path. COM3 opens as a
  healthy PL2303GC at 115200 8N1 with DTR/RTS disabled but returned zero bytes
  during an eight-second Enter probe. Ethernet has 1 Gbps carrier and host
  address `169.254.66.29/16`, but no DHCP lease, ARP peer, or management path.
  WiFi `192.168.1.1` is a different router and was untouched. V6.37 remains
  unflashed, V6.15 remains the accepted live baseline, and no persistent
  router write occurred.

## V6.38 NPU TX Descriptor DMA Ordering - 2026-08-05

- Audited the coherent NPU TX descriptor publication and completion boundary.
  The old producer used `smp_wmb()` before publishing DONE, which compiles to
  ARM64 `dmb ishst` and does not order a DMA observer. Completion also read
  firmware-updated descriptor fields without an explicit DMA acquire barrier.
- Patch `9999zzzzzzzf-mt76-fix-npu-tx-descriptor-publication.patch`, SHA256
  `03770cb972d0c8077f8e4243c0ca65635134b162537d7bf01b2c6f8e7bf2b2d3`,
  uses `dma_wmb()` before `WRITE_ONCE(DONE)`, `dma_rmb()` before completion
  reads, single `READ_ONCE()` snapshots, and `WRITE_ONCE()` on recycle.
  Verifier SHA256
  `6f993374833dacc68fccf67d57dc2a9e2a6412c691d19e788c2482a523e2582a`
  reports `PASS_V638_NPU_DESCRIPTOR_ORDERING checks=28`; its model reduces
  seven stale producer states and three stale completion states to zero.
- Exact compiled/Ghidra proof passed. Unstripped mt76 SHA256 is
  `93179da797fc8a02f907636e2c9ff4207ca110a499e8697bc99d089156df0b86`.
  AArch64 contains one `dmb oshst` before ownership publication and one
  `dmb oshld` before completion reads. Ghidra report SHA256 values are
  `311b722a45822b187d320d0ede3b0974205cd8d7fbb7013e0e9613a49189c4da`
  and
  `9bcf3f6b7bcd0958f98456e2b2b71d520ebb4dadc10ad3725fc4ba114e12ce0f`.
- Accepted offline candidate:
  `work\w1700k-npu-desc-ordering-v6.38-20260805-sysupgrade.itb`, 20,615,996
  bytes, SHA256
  `066b6e017fc103cea4428f6f127a6468055d979bc8842f46d4ba17364b4c4a19`.
  `PASS_V638_CANDIDATE` proves `gemtek_w1700k-ubi`, 81,092 bytes FIT
  headroom, byte-identical kernel/DTB, unchanged 1,146-file rootfs shape and
  package contracts, exact mt76-only functional delta, required NPU firmware,
  selected APK signatures, and no forbidden stock binaries. Verification JSON
  SHA256 is
  `5617ce4efd01ff89731033a1d522266a17afa7d3aefc354d8a037927f0db666d`.
- Frozen bundle:
  `work\candidate-bundles\W1700K-V6.38-NPU-Desc-Ordering-20260805-OFFLINE`,
  30 payload files and 28,756,562 payload bytes. Payload-list and bundle-
  manifest SHA256 values are
  `639ec7a6376a3f88075310a2e331a24a4d2495f49fb6c26e32f8ab18c77373c5`
  and
  `57e41f27f12be1a6e9691fa0892c053bc13727e8ab7c8af349dd5f58d271426e`;
  checksum replay passes. FinalResult mirror is
  `Experimental\NpuDescriptorOrderingV638-20260805-UNFLASHED`.
- The latest access retry did not advance live state. COM3 opens at 115200
  8N1 but returned zero bytes with DTR/RTS both disabled and enabled. Ethernet
  has 1 Gbps carrier and host address `169.254.66.29/16`, but no DHCP, ARP,
  IPv6 peer, or management path. The WiFi `192.168.1.1` device is unrelated
  and was untouched. No flash or persistent router write occurred; V6.15
  remains the previously accepted live baseline, not a fresh validation.

## Source Invariant Contract And Live Retry - 2026-08-05

- The post-reboot live gate remains unavailable. Windows reports a healthy
  PL2303GC binding at COM3 and opens it at 115200 8N1, but a twelve-second
  periodic-Enter probe received zero bytes. Ethernet still has 1 Gbps carrier
  and host link-local `169.254.66.29/16`, with no DHCP lease, ARP peer, IPv6
  peer, or management route. WiFi `192.168.1.1` remains an unrelated router.
  No flash, router command, or persistent write occurred.
- Reconciled a stale source-gate claim with the current Airoha FastTX source.
  Active mt76 patches contain no packet-owning FastTX controls, while Airoha
  patches 999-67 and 999-68 do contain optional consume/direct-xmit controls
  that default to false and are not exposed by `w1700k-wlan-npu-mode`.
- Updated the helper's JSON wording to distinguish that default policy from
  the compiled default-off controls. Updated the invariant checker to enforce
  all three boundaries explicitly. The current checker SHA256 is
  `bf3727d0e20e4d2b63d64d48688a28220665d278e7aeb4c642904900cf5e09d7`.
- Exact result
  `work\source-invariants-20260805\w1700k-source-invariants-20260805.json`,
  SHA256
  `428d3357ec1d52b2764e9691bb8b1a29f8201b422c4aede8b73730b1beab6a46`,
  reports 44 passed and 0 failed at source commit
  `5575e4a97f119f682223a090c4a78c0913f906f5`.
- This changes source diagnostics and verification only. No image was rebuilt
  or promoted, V6.38 remains byte-identical and unflashed, and the ownership
  model remains the active offline workstream.

## V6.39 NPU FW-TXP Token Ownership - 2026-08-05

- Proved an ABA ownership hazard in the prior experimental stock-copy cleanup.
  The RV32 trampoline always rewrites descriptor offset `0x32`, which is the
  FW-TXP token but only MAC-TXP `msdu_id[1]`; the live MAC-TXP token remains in
  `msdu_id[0]` at `0x30`. Early host-token completion could therefore allow a
  late old high-token TXFREE to release a newly reused token.
- Added executable model
  `work\w1700k_npu_tx_ownership_model_20260805.py`, SHA256
  `9a48f6f1fa75a1294119b832a320e6662c1eb6afe09e693b6340fa06491923e3`.
  It enumerates 470,592 sequences and 3,215,756 checks, reproduces three old
  ABA witnesses, and reports `HARDENED_ABA_WITNESSES=0` for the new policy.
- Patch `9999zzzzzzzg-mt76-harden-npu-stock-copy-txp-token.patch`, SHA256
  `aa49a56d1d24742101325f7192bff7bc0ed5526bea813f27d17d8ce5eea813ee`,
  adds a driver FW-TXP parser. Enqueue now requires a genuine FW-TXP whose
  embedded token matches the host IDR token. Cleanup additionally requires a
  valid rewritten FW-TXP token below `token_start`. MAC-TXP and malformed or
  unrewritten FW-TXP remain on ordinary high-token completion.
- Source invariants pass 48/48. Strict checkpatch is clean. Focused verification
  reports `PASS_V639_NPU_TXP_TOKEN_OWNERSHIP checks=35`; the bounded model,
  AArch64 disassembly, and full Ghidra decompilation agree on the parser,
  low-token gate, and retained V6.38 DMA barriers.
- Canonical unstripped/Ghidra inputs are mt76 SHA256
  `63d0e9392b6dca5e1ee19d2b9021040fa9503e3e3cc48be35e631ee539f02b9c`
  and mt7996e SHA256
  `12a4bc219065f21ed8a59c559f738ec68e7af4783788951cd59adb2af8e6cc4c`.
  Full Ghidra exit markers are zero; report SHA256 values are
  `8f0958ab2721e9fd772b2aeeb47874d750eb045f7de4f5467b891e754fb7eec2`
  and
  `dd51ca3b55890c57a722f098a0009317c94e52f49b443658e2bf641552669e24`.
- Accepted offline candidate:
  `work\w1700k-npu-txp-token-v6.39-20260805-sysupgrade.itb`, 20,615,996
  bytes, SHA256
  `3a51268ec7341d45441c53c60ed5e2789a5bfd1fc552ed71223a5545ef4ddb8c`.
  `PASS_V639_CANDIDATE` proves 81,092 bytes FIT headroom, byte-identical
  kernel/DTB, unchanged 1,146-path rootfs shape and package contracts,
  required NPU firmware, selected APK signatures, and no forbidden stock
  binaries. The linked mt76 family, helper, and equivalent APK bookkeeping
  are the only rootfs changes from V6.38.
- Analysis report:
  `work\W1700K_V639_NPU_TXP_TOKEN_OWNERSHIP_REPORT_20260805.md`.
  Frozen bundle:
  `work\candidate-bundles\W1700K-V6.39-NPU-TXP-Token-20260805-OFFLINE`,
  41 payload files and 28,560,489 bytes. Payload-list and bundle-manifest
  SHA256 values are
  `ca93ca98fda592ec05119c08b9d840430da306bce72273fdaf41d6ad6f700c2e`
  and
  `68c01088e0bae31a56a6e0d7c369adc89dc17afa4d311d1f14f2c611f7e4b76d`;
  source and FinalResult checksum replays pass. FinalResult mirror is
  `Experimental\NpuTxpTokenV639-20260805-UNFLASHED`.
- The latest live retry did not establish a router path. COM3 opens as the
  PL2303GC at 115200 8N1 but a 15-second periodic-Enter probe received zero
  bytes. Ethernet negotiated 1 Gbps and remained `169.254.66.29/16`, with no
  DHCP, ARP, IPv6 neighbor, management route, or observed packet activity.
  WiFi `192.168.1.1` is unrelated and was untouched.
- V6.39 remains unflashed. No U-Boot command, NAND/UBI write, runtime config,
  bootloader/environment write, or factory/calibration write occurred. V6.15
  remains the prior accepted live baseline. The next gate is verified UART or
  management identity, mode-0 synthetic validation, then guarded mode-3
  FW-TXP/MAC-TXP testing.

## V6.39 Live Recovery Boundary - 2026-08-05 16:25 +03:00

- COM3 is now proven live at 115200 8N1. Read-only identification returned
  vendor `ECNT>`, U-Boot 2014.04-rc1 built 2024-06-12, AXON 2.0, AN7581,
  2 GiB DRAM, `ecnt_eth`, and the expected read-only chainloader boot command.
- The exact recovery FIT, 18,350,080 bytes and SHA256
  `c121b33c14f83f59f95483905d98e4639a9275da19384e299c80b92c5baa3fda`,
  transferred over TFTP. Modern U-Boot validated all embedded hashes and
  booted it entirely from RAM. Serial identified `gemtek,w1700k-ubi`, the
  expected vendor/chainloader/ubi/reserved_bmt MTD layout, and NPU firmware
  version 0.1111.
- Recovery harness defects found live were repaired: paced CR-only serial
  command transmission, bounded non-terminating SSH probes, pre-SSH Ethernet
  alias setup, source-bound SSH/SCP, existing-Linux reboot handling, a required
  cold-boot signature, and link-reset-tolerant adapter preflight. Current
  harness `work\w1700k-com3-recover-v639.ps1` SHA256 is
  `75a4a331b4c4b8f16402272296911d194523aa8c6add3eb037b49f568859edc6`.
- No run crossed the backup or `sysupgrade -T` gate. The latest vendor U-Boot
  stopped producing output after `usxgmii_pcs_int en 1` before its command
  loop. The catcher and its exact TFTP child were stopped and COM3 was
  released. A physical cold power cycle is required before retrying.
- V6.39 remains unflashed. No NAND/UBI, environment, bootloader, factory, or
  calibration write occurred. WiFi `192.168.1.1` was not contacted. V6.15
  remains the prior accepted live baseline.

## V6.40 mt76 PPE RCU Snapshot - 2026-08-05

- A clean sparse audit of the canonical V6.39 mt76 module found one real
  source defect in `mt76_npu_setup_tc_block_cb()`: the `__rcu ppe_dev` member
  was loaded once for the null gate and a second time for the callback. The
  baseline log SHA256
  `6df1a19b6058b41e4175db9c9596a77c9de37614da739bcd63c3408a46831101`
  contains the exact different-address-space warning and is tied to the
  byte-identical V6.39 module.
- Patch `9999zzzzzzzh-mt76-fix-ppe-rcu-access.patch`, SHA256
  `62a51019903d22ac7fb2f82d6cc2520809690ab85a879dd3c9bfe19f9630519a`,
  preserves the MMIO guard and takes one `rcu_access_pointer()` snapshot under
  the existing callback teardown/lifetime contract. Strict checkpatch is
  clean and the patch applies without fuzz to exact mt76 commit
  `b2704cf5a4068b672bf47ad5bf6b4802b6770a90`.
- Final sparse log SHA256
  `67a4359ae32f088b0233e5539204d6cfca016b59a08b68a5a87efc60b68def78`
  has no C source diagnostics. Source invariants report 51 passed, 0 failed;
  exact JSON SHA256 is
  `bbeebb9cdfb2cbc0c4c67807e70af4c659a29f2c09b64228aa2347bb5bf7fd49`.
  Focused proof reports `PASS_V640_PPE_RCU checks=72`.
- Exact unstripped mt76 SHA256 is
  `e61520a0a2637236f7d119a96fd8fd36862835171648481cde733e3c5fbd8897`;
  mt7996e remains
  `12a4bc219065f21ed8a59c559f738ec68e7af4783788951cd59adb2af8e6cc4c`.
  Full Ghidra analyses exit 0. Ghidra and AArch64 independently show the MMIO
  gate, one PPE load, one null gate, and the callback through the same local
  pointer; V6.39 disassembly shows the old two-load sequence.
- Accepted offline image:
  `work\w1700k-npu-ppe-rcu-v6.40-20260805-sysupgrade.itb`, 20,615,996 bytes,
  SHA256
  `29a9ac8c2e3e488146c719c1c53c5fdb9ba1c9a88a70b39dbf469b0c067a441c`.
  `PASS_V640_CANDIDATE` proves 81,092 bytes FIT headroom, byte-identical
  kernel/DTB, unchanged 1,146-file rootfs shape and package contracts,
  selected APK signatures, required firmware/packages, and no forbidden stock
  binaries. Only embedded mt76 plus equivalent APK bookkeeping differs from
  V6.39. Verification JSON SHA256 is
  `18913d175f143da6cf7a0fd63a29b23992e1223be3111a922bd21b2218bebebd`.
- Report:
  `work\W1700K_V640_PPE_RCU_SNAPSHOT_REPORT_20260805.md`, SHA256
  `39604ed2993322091b8857bb76c365c058434dd5ac2b362bc44ac4d5b0580bab`.
  Frozen bundle:
  `work\candidate-bundles\W1700K-V6.40-PPE-RCU-20260805-OFFLINE`, 53 payload
  files and 31,219,233 payload bytes. Payload-list and bundle-manifest SHA256
  values are
  `c186c7cd19ca8319890b24cf32ee4284797aa5b51ae7c54649ca2b72b9a0451c`
  and
  `70929e86aa489c5f67ed6fcac5a64bc8a5b1b36290ffef79e45691269e980a9f`;
  workspace and FinalResult checksum replays pass. FinalResult mirror is
  `Experimental\NpuPpeRcuV640-20260805-UNFLASHED`.
- V6.40 recovery harness
  `work\w1700k-com3-recover-v640.ps1`, SHA256
  `a83fd6310c694ec645edf1c8cf3b4a1dc9820e4dff4909079be11f3b3dcbb233`,
  is pinned to the exact image, verifier result, recovery FIT, and embedded
  module hashes. Its preflight passes on the existing isolated Ethernet APIPA
  link (`169.254.66.29/16` host, derived `169.254.66.30/16` router) without
  changing the Windows WiFi route.
- Current live state did not advance. COM3 enumerates and opens at 115200 8N1
  but returned zero bytes through periodic interrupt/Enter probes and a
  bounded serial reboot/catcher attempt. Ethernet has 1 Gbps carrier and the
  W1700K MAC `00:AA:BB:01:23:40`; IPv6 link-local probing found no peer. No
  backup, candidate copy, compatibility test, sysupgrade, or persistent write
  occurred. V6.40 is unflashed and V6.15 remains the prior live baseline.
- This closes one pointer-consistency defect, not full stock host-adapter
  parity. Dedicated ring ownership, SKB/bufid/scatter lifecycle, doorbell
  ownership, TXFREE/token behavior under load, RRO equivalence, and final
  packet fate remain open for staged live evidence.

## V6.41 Airoha Ownership Hardening - 2026-08-05

- Added four Airoha kernel patches: watchdog work lifetime and devm/IRQ
  teardown ordering, explicit TX DMA unwind ownership, explicit L2 subflow
  allocation ownership, and exact mapped-entry unwind tracking. Their SHA256
  values are `f871f48558e188acf107501f6737f38cb8d4dc2d9a4e64e368480eea67096c43`,
  `17cf41a8fe2d98c3deb66d745a9abe3e0f7e671a50fbb2ef1f1225ec0307cda4`,
  `b690c199342073025332fa1b216b99a6b780e23ad58a0485b7272f01495e85b8`,
  and `b700b9371c566a0b37819a3f795f678f4083858d52cc46954e8e91379fe4cd8d`.
- Strict checkpatch passes all four patches. Focused source and generated-code
  gates report `PASS_V641_AIROHA_OWNERSHIP checks=21` and
  `PASS_V641_GENERATED_CODE checks=26`. Sparse and Clang `W=1` report zero
  Airoha diagnostics; Clang Static Analyzer produced zero Airoha source
  reports.
- Full Ghidra 12.1.2 analysis completed on the exact final `vmlinux`, mt76,
  and mt7996e inputs. It decompiled 294/294, 74/74, and 58/58 selected
  functions with no selected decompile failures. Report SHA256 values are
  `c9688cc4673b6c1d0208743f18718a09c9d0432c43effcb08052d97b6b2f63df`,
  `1985601173c7c91307d4937ca489d3a0475f34c7a5056928ba31c1273094ba52`,
  and `0cbad2b6fd68891882706ca5a38203b5d8800a93a8964513fe2f4743cb5e882d`.
- The first full-build attempt omitted `W1700K_EXPERIMENTAL_MT76_NPU=1` and is
  quarantined under
  `work\build-v6.41-20260805\attempt1-missing-experimental-mt76-npu`. It is
  rejected and must not be promoted or flashed. The corrected clean build
  records the flag and exits 0; build-log SHA256 is
  `4bb83d9c71633b778881e3eb34ece18525ecac288ec22246086a54dbf45167a9`.
- Accepted offline image:
  `work\w1700k-airoha-ownership-v6.41-20260805-sysupgrade.itb`, 20,615,996
  bytes, SHA256
  `41d6c207dfe46dd3b103de0361b4665564547278fa7eca9e731e7f9284add05c`.
  `PASS_V641_CANDIDATE` proves 81,092 bytes FIT headroom, correct board/fwtool
  metadata, unchanged 1,146-file rootfs shape and package contracts, selected
  APK signatures, required NPU firmware/packages, and no forbidden stock
  binaries. Verification JSON SHA256 is
  `c2caad39711c58e88ee2a9aac7fc516cc458753fed397633f62139e1acf57a80`.
- Kernel changed as intended; DTB, mt76, mt76-connac, mt7996e, NPU helper,
  LuCI, and NPU firmware remain byte-identical to V6.40. Only equivalent APK
  database bookkeeping differs in rootfs.
- Report:
  `work\W1700K_V641_AIROHA_OWNERSHIP_REPORT_20260805.md`, SHA256
  `db5ca3b24df31300f96e00b5d1d6167cd5f32f3a81a094d037514bf3cb7a8120`.
  Frozen bundle:
  `work\candidate-bundles\W1700K-V6.41-Airoha-Ownership-20260805-OFFLINE`,
  82 payload files and 111,831,984 payload bytes. Payload-list and
  bundle-manifest SHA256 values are
  `339191b3c63c458828799d0c3d27148c7df948d3906255eecc708a8a09f8172b`
  and
  `5d0ddf9766bb976da19d76fa1dd6fe38e8ed282f79cce6f54e14bb0f7807211c`.
  Workspace and FinalResult checksum replays pass with zero failures and no
  mirror differences. FinalResult is
  `Experimental\AirohaOwnershipV641-20260805-UNFLASHED`.
- Recovery harness `work\w1700k-com3-recover-v641.ps1`, SHA256
  `776db16a7272313a36acf3886618ecacff872fb2789a99a7cc6c31362dd8c1fd`,
  passes exact candidate/verifier/recovery preflight over isolated APIPA
  Ethernet without changing the Windows WiFi route.
- Current live state did not cross the identity gate. COM3 opens at 115200
  8N1, but the latest 20-second carriage-return probe received zero characters.
  No flash, backup, candidate transfer, compatibility test, sysupgrade,
  U-Boot command, NAND/UBI, environment, bootloader, factory/calibration, or
  runtime WiFi write occurred. V6.41 is unflashed and V6.15 remains the prior
  accepted live baseline.
- V6.41 closes four concrete Airoha ownership defects, not full stock
  host-adapter parity. Dedicated ring ownership, SKB/bufid/scatter lifecycle,
  doorbell ownership, TXFREE/token behavior under load, RRO equivalence, and
  final packet fate remain open for staged live evidence.
- A final V6.41 catcher retry was armed before the requested cold power edge
  in `work\live-captures\v641-recovery-20260805-201005`. It still received
  zero raw serial bytes and never detected a bootloader prompt. The host then
  stopped only the exact harness TFTP child, confirmed zero UDP/69 listeners,
  and reopened COM3 successfully. Status and cleanup SHA256 values are
  `7daad315e053bdc9318addde3008e76f3e9a2b829b8505ab27c46728827c95cd`
  and
  `6742048668b9aa91ba15bad87871aad1ce086ed6381c1834b7bfcdc714ddd91d`.
  No router command or persistent write stage was reached.
- A new exact-harness retry is preserved under
  `work\live-captures\v641-recovery-20260805-202900`. The V6.41 artifact and
  isolated-host preflight passed, COM3 opened at 115200 8N1, and Ethernet
  retained 1 Gbps carrier, but the catcher received zero bytes and detected
  no bootloader prompt. The known APIPA target and IPv6 all-nodes probe also
  produced no router response. Because no serial boot signature appeared, the
  host cannot prove that a cold power edge occurred.
- The bounded host wait was terminated before any router operation. The exact
  harness-owned TFTP PID 9592 was verified and stopped, UDP/69 returned to zero
  listeners, and COM3 reopened successfully. `status.log`,
  `capture-result.txt`, and `cleanup.txt` SHA256 values are
  `595d724f6cfe9e988335ead6bbd9cf5a47b9334ee744f36583acdc79be223ed6`,
  `46f71910640ad2ccc51664423d75496bc92af1550cda433721039e1d08c9a679`,
  and
  `8a159afb4fa905551623d270066c1e553c93b601f83e45ecb2d90365cdc59ffd`.
  Backup, candidate transfer, compatibility testing, sysupgrade, and all
  persistent-write stages remained unstarted. V6.41 is still unflashed and
  V6.15 remains the prior accepted live baseline.

## V6.42 Stock Hostadpt TX Headroom - 2026-08-05

- Reconciled the saved stock `hostadpt_tx_handler` decompile against current
  Airoha/mt76 code. Stock group0 maps 2.4/5 GHz to
  `0x30d0a0/0xa4/0xa8/0xac`; group1 maps 6 GHz to
  `0x30d0b0/0xb4/0xb8/0xbc`. Both TX rings have 1024 entries and `0xd0`
  descriptor stride. Stock publishes only when the full free distance is
  greater than five, for 1019 maximum outstanding descriptors.
- The V6.41 generic mt76 gate permitted 1022 outstanding NPU descriptors. The
  exact pre-enqueue mismatches were occupancies 1019, 1020, and 1021. Its
  read-only stock verdict also used a sentinel-subtracted free count and was
  one slot too strict at occupancy 1018.
- Added NPU-only headroom patch
  `work\9999zzzzzzzi-mt76-match-stock-hostadpt-tx-headroom.patch`, SHA256
  `edeae4b5e84b81cd6db61a0b1a3fb1d856735a7b6ee992b2b0e056abfa8162b1`,
  and Airoha telemetry patch
  `work\999-73-net-airoha-report-stock-hostadpt-free-distance.patch`, SHA256
  `80bcfd22e35b785fced8b2a6e18391a07eeed5b72a5d70a5ddd48732679da968`.
  Ordinary mt76 DMA queue admission is unchanged. Strict checkpatch is clean.
- Executable model
  `work\w1700k_v642_hostadpt_tx_ring_model_20260805.py`, SHA256
  `05836853d187eb38a1819fe9beccc3e9087f38df82d046d1c6db013be605ee5d`,
  passes 1573 checks over both register groups, all occupancies, wraparound,
  owner/doorbell order, stale snapshots, duplicate cleanup, reset, token
  completion, and shared-band topology.
- The first V6.42 image attempt, SHA256
  `c02472cb3af07ada1c4aa83e534cd1e0e645d191402ce4e2465493cfa31384ea`,
  was rejected before flash because its build omitted the reproducible
  `W1700K_EXPERIMENTAL_MT76_NPU=1` gate. It is quarantined under
  `work\rejected\v642-attempt1-missing-experimental-mt76-npu`.
- The corrected clean build records the sanitized Linux PATH and explicit NPU
  flag, proves `npu.o` plus defined NPU transport functions before and after
  the full build, and exits 0. Build-log SHA256 is
  `8bd6f81976cf727b987e4eb821150ea55c8cdf7d5892317baf0640ae8cca750b`.
- Accepted offline image:
  `work\w1700k-hostadpt-tx-headroom-v6.42-20260805-sysupgrade.itb`, 20,615,996
  bytes, SHA256
  `8e695154559134701aed51c64b436f6e17b0a4b161c31db837f0879ede33482d`.
  FIT headroom is 81,092 bytes; source HEAD remains
  `5575e4a97f119f682223a090c4a78c0913f906f5`.
- Full Ghidra 12.1.2 auto-analysis exits 0 for the exact rebuilt kernel and
  accepted NPU-enabled mt76. Kernel and mt76 report SHA256 values are
  `a878f25f339fb60f9f079d20095880490295bf2ef8c592ff247ab4aa5499f585`
  and
  `a1addea868ddaa649cc171cf35043e93b1f2b7df402866e4a9575e966b44ccb9`.
  Decompiled code proves full stock free distance, `free > 5`, actual NPU
  enqueue/cleanup functions, and `queued + needed <= ndesc - 5`.
- `tools\verify_w1700k_v642_candidate.py`, SHA256
  `2a6cf4a4b09c3267f0bebd1548bfc6d6c7c1b94d5212f3fee360b00611036b08`,
  reports `PASS_V642_CANDIDATE`. DTB and rootfs shape remain unchanged; package
  contracts and maintainer scripts are equivalent. The exact rootfs delta is
  mt76 plus APK bookkeeping. APK signatures pass, all four OpenWrt Airoha NPU
  firmware files are present, and forbidden stock binaries are absent.
- Report:
  `work\W1700K_V642_HOSTADPT_TX_RING_RECONCILIATION_20260805.md`, SHA256
  `7a2f29bc46056b993bbcbe510d556b6ce9b0a0944bceb2909546f498f90b60e6`.
  Verification JSON SHA256 is
  `75753a5ad0ed84affe20d6adb44a0fe5023c18ccf93ee291b30cfaf35f68f180`.
- Frozen bundle:
  `work\candidate-bundles\W1700K-V6.42-Hostadpt-TX-Headroom-20260805-OFFLINE`,
  35 payload files and 105,883,556 bytes. Payload-list and bundle-manifest
  SHA256 values are
  `b9cefc5dd0b995d112b9219cc4b32fe4d7339e2ed617cbe4451cf75765270c84`
  and
  `9a245ed0084d18e88712d8e4ccaa06f9915b6e866d3eb958b2da15ad684b04fa`.
  Payload and image checksum replay pass. The corrected FinalResult mirror is
  `W1700K-V6.42-Hostadpt-TX-Headroom-20260805-OFFLINE`.
- COM3 enumerated and opened at 115200 8N1, but
  `work\live-captures\v642-com3-20260805-212728` received zero bytes during a
  180-second read-only boot capture. Ethernet retained 1 Gbps carrier but had
  only APIPA and no trusted W1700K management response. The unrelated WiFi
  router at `192.168.1.1` was not contacted.
- V6.42 is offline verified and unflashed. No router command, backup, transfer,
  compatibility test, sysupgrade, U-Boot command, NAND/UBI, bootloader,
  environment, factory/calibration, or runtime WiFi write occurred. V6.15
  remains the prior accepted live baseline.
- The headroom mismatch is closed on paper and in generated code. Live stress,
  TXFREE ordering under load, ping-pong packet fate, RRO equivalence, exact
  stock callback/error paths, and final hardware parity remain open.

### V6.42 live recovery precheck - 2026-08-05

- COM3 became electrically active after a user-triggered reboot and captured
  the installed image panicking in `cfg80211_register_netdevice()` through
  `queued_spin_lock_slowpath()`. This reconfirms the previously proved rejected
  NETPOLL/non-NETPOLL `net_device.ieee80211_ptr` ABI failure, not a radio UCI
  failure.
- The exact V6.42 image was re-run through the permanent image-level ABI gate.
  Result: `PASS_NETDEV_ABI_IMAGE_GATE`; kernel and cfg80211 both use offset 976,
  NETPOLL/NETCONSOLE are disabled, and the deliberate NETPOLL probe moves the
  offset to 984. Verification JSON SHA256 is
  `62a85c6a124e988b8752c64ab39ab5ceb46e152ae417c986dc4bd6da154f103f`.
- Added `work\w1700k-com3-recover-v642.ps1`, SHA256
  `3a3815086d564472a1c14a63370ce0de787c7298ce7ee904e3cffd63230cd41e`.
  Its exact-artifact, ABI, RAM-recovery, APIPA, backup, sysupgrade-test, clean
  flash, module-hash, no-panic/OOM, NPU-mode, ownership, and radio gates pass
  offline preflight.
- The catcher was armed, but no subsequent cold-boot bytes arrived. It was
  stopped cleanly, UDP/69 was released, and COM3 reopened successfully. No
  flash or router write occurred. Report
  `work\W1700K_V642_LIVE_RECOVERY_PRECHECK_20260805.md` SHA256 is
  `ea5a724bc90c2f67d7bbd94587061488012dcd0f553b1e30c99b9d3920343552`.

### V6.42 NPU TX reclaim liveness closure - 2026-08-05

- Reconciled stock per-handler consumer reclaim with the prepared mt76 call
  graph. Ordinary mt76 scheduling cleans at 960 queued descriptors, stops at
  992, and TXFREE cleanup reschedules the worker. From the reachable stopped
  boundary, one consumer advance makes the next scheduler pass runnable.
- `work\w1700k_v642_npu_tx_reclaim_liveness_model_20260805.py`, SHA256
  `392459338b6e8f332dc2aa5ed03f84cd6060b9cdb37255102919ba1f2d606936`,
  passes 534,734 occupancy, consumer-progress, delayed-TXFREE, and stock
  comparison checks. Frozen output SHA256 is
  `4624044b97fcbe618ad61b7f8b08111a9df0d2dd387459f6563f1cbc2f6ac647`.
- Result: no enqueue-hot-path source mutation is justified. V6.42 remains
  byte-for-byte unchanged. Report
  `work\W1700K_V642_NPU_TX_RECLAIM_LIVENESS_20260805.md` SHA256 is
  `63c3a605042253a3187a062b742e76461d0e1aeea422e818529f8fa9db35dec0`.

### V6.42 COM3 recovery attempt - 2026-08-05 22:42 +03:00

- Exact harness preflight passed and COM3 opened at 115200 8N1, but the
  extended post-arm window received zero UART bytes. Ethernet had 1 Gbps
  carrier; the expected APIPA recovery peer did not answer ARP or ICMP.
- The exact read-only TFTP child was stopped, UDP/69 was clear, and COM3 passed
  a direct release open/close test. No router command or flash stage was
  reached; V6.42 remains unflashed.
- Report
  `work\W1700K_V642_COM3_RECOVERY_ATTEMPT_20260805_224223.md` SHA256 is
  `58904af230fae1a5646f86adddfcdf75ea80ecb21590bed0c8d1e1d888babb70`.

## V6.43 NPU Default-Off Order Gate - 2026-08-05

- Root-caused a production-path regression in V6.42 diagnostics: token
  allocation, NPU enqueue, token/TXFREE release, and consumer reclaim all
  acquired one shared `order_lock` even when `npu_deep_trace=0`. The guarded
  bitmaps and ordering histories are diagnostic-only and do not drive packet
  ownership decisions.
- Added
  `work\patches\9999zzzzzzzzj-mt76-gate-npu-token-order-trace.patch`, SHA256
  `20c0b1a2b55001a7153e01d078620cddcbc37273a3e57f9e7996505737e18339`.
  Aggregate counters remain active; default-off mode skips bitmap/event work,
  IRQ masking, and the shared lock. Deep trace retains the previous behavior.
  Strict checkpatch is clean.
- Target-ABI measurements bound the added diagnostics at about 36.2 KiB:
  `mt76_dev=63648`, `mt76_w1700k_npu_diag=31416`,
  `mt76_w1700k_npu_trans_lifecycle=4832`, and `mt7996_dev=79984` bytes.
  This does not explain the reported 88 percent RAM display. Intentional NPU
  TX coherent buffers are 1.5 MiB and RRO coherent state is roughly 9 MiB.
- A first focused compile without `W1700K_EXPERIMENTAL_MT76_NPU=1` is retained
  only as rejected diagnostic evidence in
  `work\build-v6.43-20260805-mt76.log`. The corrected focused and full builds
  pin the flag, contain both NPU objects, and exit 0.
- `tools\verify_w1700k_v643_npu_order_gate.py` reports
  `PASS_V643_NPU_ORDER_GATE`. Exact AArch64 disassembly proves the default-off
  branch precedes serialization in token consume, token release, DMA cleanup,
  and NPU enqueue.
- Full Ghidra 12.1.2 analysis exits 0 for exact final mt76 and mt7996e.
  Report SHA256 values are
  `6467e900f874c4a906049463521a7e6e618950cb27962e28cfcbb45831e8a8da`
  and
  `364642a976cb8580e3f82cdac106a1be9b5d7173c1692806024dba192029be01`.
- Accepted offline image:
  `work\w1700k-npu-order-gate-v6.43-20260805-sysupgrade.itb`, 20,615,996
  bytes, SHA256
  `a5516f47fa5984094c2405b7ac9cd986b373d19769020c47f2128c0464aa3351`.
  FIT headroom remains 81,092 bytes; source HEAD remains
  `5575e4a97f119f682223a090c4a78c0913f906f5`.
- `PASS_V643_CANDIDATE` proves the kernel, DTB, and cfg80211 are byte-identical
  to ABI-proven V6.42. The only regular-file rootfs deltas are APK bookkeeping,
  mt76, and mt7996e; package contracts and scripts remain equivalent.
  Verification JSON SHA256 is
  `24e2672b7186fc7c6346b8ca4c0c722de128b20d03a7bdc4a5cb19c551b7310b`.
- Report `work\W1700K_V643_NPU_ORDER_GATE_20260805.md` SHA256 is
  `87690316498e7ca5ee9866355584a45cd67aab63d70acf259b07290737c4fc45`.
- Exact recovery harness `work\w1700k-com3-recover-v643.ps1`, SHA256
  `0e3f033b906f089b067587a99f48bb1953e113db30d340095b8f55f4da00df17`,
  passes preflight and is armed under
  `work\live-captures\v643-recovery-20260805-235617`. COM3 opens at 115200
  8N1, but UART RX is currently zero bytes and the APIPA peer is unreachable.
  No router command or write stage has occurred. V6.43 is unflashed; V6.15
  remains the prior accepted live baseline.
- Frozen workspace bundle and FinalResult mirror:
  `W1700K-V6.43-NPU-Order-Gate-20260805-OFFLINE`, 15 files and 24,603,624
  bytes. `SHA256SUMS.txt` and `FILE_MANIFEST.tsv` SHA256 values are
  `2604cfcc6c1bcfe8a0b3d0ab8c090237be1014ea058e594ffb6d49ed457323bd`
  and
  `3f2f32f6aa427ddb1639ea40baa1a3802dc74a4f65be10bf7b9115fa57f2fd04`.
  Checksum replay has zero failures and the two trees are byte-identical.

### V6.43 COM3 recovery attempt closed - 2026-08-06

- The armed run `work\live-captures\v643-recovery-20260805-235617`
  received zero UART bytes. A separate 60-second monitor saw Ethernet remain
  continuously up at 1 Gbps, so no cold-power link transition was observed.
- The wait was closed at the host-only boundary. Exact TFTP PID 15572 was
  command-line verified before stop; UDP/69 returned to zero listeners and
  COM3 release passed. Capture-result and cleanup SHA256 values are
  `c2d3e1c8e6adacaf9eb6ef88fffbac204f02868231831f71d3145bd941ac02a6`
  and
  `219ce1d696270722d1ed3df9997664e2ccb0122e86534af997df49abb47785c1`.
- No router command, identity gate, TFTP request, recovery boot, backup,
  transfer, compatibility test, sysupgrade, or persistent write occurred.
  Attempt report SHA256 is
  `0eb99ae3da06f3af348bfc106bd98da6efdbeba7a51b21856a6a655e97fd542c`.
  V6.43 remains unflashed.

## V6.44 Default-Off Packet Telemetry Gate - 2026-08-06

- Current accepted offline candidate is
  `work\w1700k-packet-telemetry-gate-v6.44-20260806-sysupgrade.itb`,
  20,620,092 bytes, SHA256
  `6fd3c540938212856cca9abeb523041739ffbb942befd901806798e1eed4f1c8`.
  FIT volume headroom is 76,996 bytes; source HEAD remains
  `5575e4a97f119f682223a090c4a78c0913f906f5`.
- Root cause: after V6.43 removed shared diagnostic locking, routine mt76,
  NPU, TXFREE, hostadpt-shadow, and MLO packet counters still compiled to
  Cortex-A53 exclusive-load/store loops on production paths. Those aggregates
  are diagnostic-only and do not control packet ownership or forwarding.
- Added
  `work\patches\9999zzzzzzzzk-mt76-gate-w1700k-packet-telemetry.patch`,
  SHA256
  `ec1b45845b3fe03ce3760e30329a9385a5242fbfbc292e829d7b03b19499cf8e`.
  A default-false static key gates routine packet telemetry. Deep trace
  automatically enables the effective key. Error and abnormal-condition
  counters remain active, and ownership behavior is unchanged. Strict
  checkpatch is clean.
- `PASS_V644_PACKET_TELEMETRY_GATE` proves nine mt76 and seven mt7996 jump
  entries. Reachable exclusive stores fall from 7 to 2 in token consume, 16
  to 2 in token release, 18 to 2 in DMA cleanup, and similarly across NPU TX
  and MLO selection. The cached mt7996 TX-prepare gate is pinned at
  `0x15df8 -> 0x160d4` with a default NOP site.
- The helper and LuCI NPU view expose packet telemetry. Default-off state is
  reported as `telemetry-off`; hardware core, IRQ, ring, and MIB monitoring
  remains available. The fixture passes explicit on, off, and
  deep-trace-implies-telemetry cases.
- Clean NPU-enabled build exits 0. Full Ghidra 12.1.2 analysis exits 0 for the
  exact final mt76 and mt7996e, with 448 and 618 recovered functions. Report
  SHA256 values are
  `1aae75980b70a7689221e4e6cc35b1917ef159966f86c686a2fd49e2ee1d6eba`
  and
  `3669cdb8b5b9a5b4d3b84401ca838112174afcd9ef4f07a2652f3d029cb85c23`.
- `PASS_V644_CANDIDATE` proves kernel, DTB, and cfg80211 are byte-identical to
  V6.43. Rootfs shape remains 1,146 files; only APK bookkeeping, mt76,
  mt7996e, the helper, and LuCI view differ. Package contracts and maintainer
  scripts remain equivalent; signed APKs and required NPU firmware pass, and
  forbidden stock binaries are absent. Verification JSON SHA256 is
  `79d308a0b885da5435ecfc0342c428163b741dc0a05cdf251be50795a0767ce9`.
- Report `work\W1700K_V644_PACKET_TELEMETRY_GATE_20260806.md` SHA256 is
  `aa363c7bb076767e0af03af6c6d79f44f64836926f3503f0c88f04f8e931a334`.
- Frozen workspace bundle and FinalResult mirror are both named
  `W1700K-V6.44-Packet-Telemetry-20260806-OFFLINE`, with 24 files and
  33,028,639 bytes. `SHA256SUMS.txt` and `FILE_MANIFEST.tsv` SHA256 values are
  `8db4b50ad233643e03b54cc054a1c05a07371c8364cb887445e76644056e5f06`
  and
  `91f425343326db9e10bbb7573ef39e116a8b3f95f21a68bce4817244ff68d0a2`.
  Checksum replay passes and the two trees are byte-identical.
- `work\w1700k-com3-recover-v644.ps1`, SHA256
  `061841d0b8f21d09a74c1aaae50bd1ca7d78d38490ba6ff2ff07b1bd36d93cdc`,
  passes exact preflight and verifies telemetry is off after installation.
  COM3 opens at 115200 8N1 but repeated passive and Enter probes receive zero
  bytes. Ethernet has 1 Gbps carrier and no responding APIPA peer. No router
  identity, command, backup, transfer, compatibility test, sysupgrade, or
  persistent write occurred.
- V6.44 is offline verified and unflashed. V6.15 remains the prior accepted
  live baseline. Open work remains live mode-0/mode-3 stress, TXFREE ordering
  under load, ping-pong packet fate, RRO equivalence, exact vendor
  callback/error paths, and final stock host-adapter parity.

### Stock ping-pong current-source replay - 2026-08-06 01:27 +03:00

- Replayed the exhaustive July 18 stock production-fate verifier against
  current source commit `5575e4a97f119f682223a090c4a78c0913f906f5`.
  Result: `PASS_STOCK_PINGPONG_PRODUCTION_FATE`, 62 passes and 0 failures.
- Current source has no active post-token ping-pong patch; all 19 retired
  variants remain quarantined. Stock left-to-right mode and speedtest hooks
  remain dormant synthetic test facilities, not ordinary production packet
  paths.
- This supersedes the generic open "ping-pong packet fate" wording above.
  Static production ping-pong control flow and terminal ownership are closed.
  Live FastTX/QDMA behavior under load, exact callback/error paths,
  TXFREE/RRO concurrency, dead-WM recovery, and performance remain open.
- Replay transcript SHA256 is
  `cbd6bdde53e19ba78605b033a317ec1d443b7c067400fbf64e128294823ab16f`;
  report is `work\W1700K_STOCK_PINGPONG_CURRENT_SOURCE_REPLAY_20260806.md`.
  No source, image, or router state changed.

## V6.45 NPU Token Release-Last - 2026-08-06

- Stock Ghidra analysis proved that `hostadpt.ko` retains a TX token through
  DMA unmap, SKB consumption, and the TXFREE callback, then releases it last.
  Exact V6.44 machine code instead removed the IDR entry before cleanup,
  allowing the TXWI/token to become reusable while completion still owned it.
- Added
  `work\9999zzzzzzzzl-mt76-release-npu-tokens-after-callback.patch`, SHA256
  `77eb9f89ab3326d5f1aaf176ec413609a7c6ff2eaf766708aba9e2545eda1e0e`.
  TXFREE and consumer paths now claim a live IDR entry, perform completion
  outside `token_lock`, validate pointer/token/owner, release the token, and
  only then return the TXWI. Mismatch quarantines the TXWI. Generic non-NPU
  release behavior is unchanged. Strict checkpatch is clean.
- `tools\verify_w1700k_token_release_last.py`, SHA256
  `151bdba5b225ddaef904fdb21f7a6b9b78fdfd22aeee0487187a360621f34b10`,
  reports `PASS_W1700K_TOKEN_RELEASE_LAST` with 19 passes and zero failures.
- Clean NPU-enabled package and full-image builds exit 0. Full Ghidra 12.1.2
  analyses recover 452 mt76 and 622 mt7996e functions. Exact report SHA256
  values are
  `ffd81ae6e02dbba5b7e20ee5045a76118b18adb39f7c99edd1fae5efb1f4d68e`
  and
  `730ea8743dbd36645830dcbe4a51f9ec339def8b08dd2a11c04f9923d8a928d5`.
- Current accepted offline candidate:
  `work\w1700k-npu-token-release-last-v6.45-20260806-sysupgrade.itb`,
  20,620,092 bytes, SHA256
  `e12e04ab4231a29bf0f430dfbc9dfe66d6404eebbc0bbc986c7e8676cc935e23`.
  FIT headroom is 76,996 bytes; source HEAD remains
  `5575e4a97f119f682223a090c4a78c0913f906f5`.
- `PASS_V645_CANDIDATE` pins the exact image, patch, model, builds, Ghidra
  reports, FIT metadata, package signatures, and rootfs delta. Kernel and DTB
  are byte-identical to V6.44; package contracts are equivalent; forbidden
  stock binaries are absent. Verification JSON SHA256 is
  `987e53c25b4e0893c75e410a23e84c3546fc2c04cc570cea37ccf55ab870a736`.
- Report `work\W1700K_NPU_TOKEN_RELEASE_LAST_V645_20260806.md` SHA256 is
  `131fcdee61f005d8b725037f3c81c8c94cc328405e703ebc9927ab1b8e4d9fc7`.
- Frozen workspace bundle
  `W1700K-V6.45-NPU-Token-Release-Last-20260806-OFFLINE` and FinalResult
  mirror contain 25 files and 28,166,711 bytes. `SHA256SUMS.txt` and
  `FILE_MANIFEST.txt` SHA256 values are
  `e95453ff2963d287500bb122be58a7df627220ed6f4fe36b61bbd0d4643d6a26`
  and
  `d84bdb462971eec7781c14d42523493e3f03b627d82077200128c46e0db33843`;
  checksum replay passes and both trees are byte-identical.
- Exact recovery harness `work\w1700k-com3-recover-v645.ps1`, SHA256
  `d9fddf5d3455befcf7a02bbdb0efb1f0695716e12d2c9d3a89668ef8600dcad1`,
  passes preflight and is armed at
  `work\live-captures\v645-recovery-20260806-024257`. COM3 is open at
  115200 8N1 and read-only TFTP is bound only to `169.254.66.29`, but UART RX
  is still zero bytes. No router identity, command, backup, transfer,
  sysupgrade, or persistent write has occurred. V6.45 remains unflashed and
  V6.15 remains the prior accepted live baseline.
- Static TX token callback ordering is closed. Remaining boundaries are live
  mode-0/mode-3 stress, TXFREE/RRO concurrency under load, exact vendor
  callback/error behavior, dead-WM recovery, and final WiFi/NPU performance.

### Stock TXFREE callback target correction - 2026-08-06 03:25 +03:00

- Corrected the registered-interface offset base. `connac_if.ko` registers
  `.data+0x110`; `mtk_interface_alloc_device()` stores that object plus 8 at
  device `+0x80`; `mtk_hwifi_free_tx()` invokes slot `+0x58`. The resulting
  relocation is `.data+0x170 -> .text+0xe74`, Ghidra `0x00100e94`.
  `0x001010d4` is `connac_if_tx_queue` and was an offset-base trap, not the
  TXFREE callback.
- The true callback extracts band 0-2 from token metadata, requires a
  registered PHY, and calls `mtk_mac_dequeue_by_token()` when that PHY's
  active-token count is below 10. The provider locks per band, checks pending
  work, dispatches the dequeue operation, and unlocks.
- `tools\verify_w1700k_stock_txfree_callback.py`, SHA256
  `582aefe441762f361941f13dd3bf95a86ca7c4ce5f82f5609a880c0fe207e4e5`,
  reports `PASS_STOCK_TXFREE_CALLBACK_PARITY_V645`: 48 passes, 0 failures.
  Verification JSON SHA256 is
  `a5c1d70d3d246102f6913db22e353bf12532542f84e8e5d401187f6f1380de23`.
- V6.45 has functional queue-progress parity: it consumes SKBs, polls station
  state, finalizes token ownership before TXWI reuse, optionally unblocks TX,
  and schedules the all-PHY mt76 worker. It intentionally does not clone
  stock's synchronous per-PHY `<10` gate without live starvation evidence.
- Report `work\W1700K_STOCK_TXFREE_CALLBACK_TARGET_V645_20260806.md` SHA256 is
  `459be008aa048725ef4b986d0eba34216712b8d8160e1a99d0229c3b8c9974ad`.
  No source, package, candidate, or frozen bundle changed.
- The 12-file evidence set replays with zero checksum failures.
  `SHA256SUMS.txt` and `FILE_MANIFEST.tsv` SHA256 values are
  `ff9da3647a31ca14424abb56de11b7934d2ecaa273a84d2cad0fd6727b39da22`
  and
  `f63bc12cf90308641108d6926d76e73b4ff919d0756f195edb290301948af187`.
- The armed V6.45 recovery capture now receives real UART data and identifies
  the expected AXON 2.0 W1700K path, AN7581GT, 2 GiB DRAM, and Winbond 512 MiB
  NAND. Boot currently stops before a prompt at `usxgmii_pcs_int en 1` with
  Ethernet link down. No command, backup, TFTP transfer, sysupgrade, or
  persistent write occurred. V6.45 remains unflashed; V6.15 remains the prior
  accepted live baseline.

## V6.46 NPU RRO Session Teardown - 2026-08-06

- Added a six-second timeout for the current firmware's interface-3 inode
  TX/RX mailbox operation and a concrete mt7996 warning before fail-open MCU
  session reset. Host signature poisoning, synchronous RRO indication
  processing, token validation, and V6.45 release-last ownership remain intact.
- Firmware ABI reconciliation is closed. Stock firmware maps inode TX/RX to
  command `0x17`; current OpenWrt firmware inserted TX packet-buffer setup at
  `0x17` and maps inode TX/RX to `0x18`. Full Ghidra decompilation proves both
  dispatch tables and the exact rebuilt kernel compares against `0x18`.
- `tools\verify_w1700k_npu_firmware_mailbox_abi.py`, SHA256
  `831fcdffd0e30b82ad68191f0f0c43431f652c396277b9124fc6e1c0249d0ead`,
  reports `PASS_W1700K_NPU_FIRMWARE_MAILBOX_ABI`: 45 passes, 0 failures.
  The integrated stock semantic RRO verifier reports 107 passes, 0 failures.
- Full Ghidra 12.1.2 analysis exits 0 for exact V6.46 `vmlinux`, `mt76.ko`,
  and `mt7996e.ko`, recovering 36,849, 452, and 619 functions. Report SHA256
  values are
  `74c51e5050b93c32dbf4ec88a0c6133cce5d08f83f84eef432998b9819caa6b3`,
  `49b623629bad4db585d2bf6ecef7ee3ee394d42673752076dc31a789f99374da`,
  and
  `66df252c5bccd22fa00641a8a319ac4bb7a7dab580be9f91b3982d6c077a3363`.
- Offline candidate:
  `work\w1700k-npu-rro-invalidate-timeout-v6.46-20260806-sysupgrade.itb`,
  20,620,092 bytes, SHA256
  `28d3ef4f3405731e4fae4506aa9e0731a273111e7673abeb6ae38cdc250307bc`.
  `PASS_V646_OFFLINE_CANDIDATE` verifies FIT/rootfs metadata, exact V6.45
  delta, package contracts, maintainer scripts, signed APKs, NPU firmware,
  forbidden-binary absence, ABI evidence, and full Ghidra reports.
  Verification JSON SHA256 is
  `748ba83e70152c6ccc7140f9c37ffc5f62dd78e8ebd35167721f66900f7b5ec5`.
- Report `work\W1700K_NPU_RRO_SESSION_TEARDOWN_V646_20260806.md` SHA256 is
  `0dabd6694f1b97ee9c54ea3cdd2720192728240464b84accae0cf21b94bafd59`.
- Frozen workspace bundle
  `W1700K-V6.46-NPU-RRO-Session-Teardown-20260806-OFFLINE` and FinalResult
  mirror `W1700K-V6.46-NPU-RRO-Session-Teardown-20260806` contain 44 files
  and 104,807,174 bytes. `SHA256SUMS.txt` and `FILE_MANIFEST.txt` SHA256
  values are
  `6dec3adb6ca913bc944950e24fbfb79d4c4fdc725890765c1c4d47f20f702972`
  and
  `37dea867dd8f11d6bc459e8f87388762174ec53c23c2a26f8274ed6d057cee1f`.
  Checksum replay passes and both trees are byte-identical.
- Live recovery remains staged on exact V6.45. Fresh harness PID 23080 is
  armed at `work\live-captures\v645-recovery-20260806-043036`; COM3 and
  isolated read-only TFTP are healthy, but the run has received zero boot
  bytes and Ethernet has no carrier. No command or persistent write occurred.
  V6.46 is unflashed, V6.45 is unflashed, and V6.15 remains the prior accepted
  live baseline.

## V6.47 Source Audit Cleanup and Guarded Recovery - 2026-08-06

- Audited all 6,386 patch files in the exact final source tree: 5,893 upstream,
  170 active/local, and 323 disabled experimental. All 111 detected issues are
  inherited upstream-only; active/local and disabled-experimental scopes have
  zero issues. Audit JSON and Markdown SHA256 values are
  `35089ac6eea770b996ed7bde634d0eab8f0317eaf7450577b496cd0831dc72a1`
  and `be2368d6e3a076349a22a9a7b53a1941c37ee97f59c6e0b074dc5ba5396d8f21`.
- Added `9999zzzzzzzzn-mt7996-remove-retired-mlo-counters.patch`, SHA256
  `cc3fbe9c648784fd9d5cc001087922599d0d5dd3b8dcc5c9d4624a75e6056fc8`.
  It removes two never-incremented diagnostic fields and names the actual
  selection/preparation enforcement scope. Strict checkpatch reports zero
  errors, warnings, and checks. The NPU helper now quotes `telemetry-off` status
  values; no runtime policy or transmit-power setting changed.
- Rebuilt from exact source HEAD `5575e4a97f119f682223a090c4a78c0913f906f5`
  under WSL ext4 with a Linux-only PATH and `W1700K_EXPERIMENTAL_MT76_NPU=1`.
  Exact candidate `work\w1700k-source-audit-cleanup-v6.47-20260806-sysupgrade.itb`
  is 20,620,092 bytes, SHA256
  `114395c77e958c74d21b34e4b22649d96715e540b6c8c3075ee3c575bc69f668`.
- Kernel and DTB are byte-identical to V6.46. Exactly four regular rootfs files
  differ: APK installed/scripts containers, `mt7996e.ko`, and
  `w1700k-wlan-npu-mode`. Package contracts and maintainer-script contents are
  unchanged. No stock `hostadpt.ko`, `npu.ko`, `mt_wifi.ko`, `mt7990*.ko`, or
  related proprietary module is shipped.
- The current gates pass: V6.34 MLO active links, V6.35 MLO TX alignment,
  V6.36 NPU hotpath, V6.37 DMA pairing (48), V6.38 descriptor ordering (28),
  V6.41 Airoha ownership (21), mailbox ABI (45), and stock RRO semantics (107).
  The V6.38 Ghidra assertion was made independent of autogenerated local names;
  it now proves SKB shadow -> `oshst` -> ownership publish and `oshld` -> read
  -> ownership clear ordering.
- Exact V6.47 `mt7996e.ko` full Ghidra 12.1.2 analysis exits 0 with 618
  functions and 5,195 symbols. Byte-identical V6.46 kernel/mt76 reports remain
  valid with 36,849 and 452 functions. New mt7996 report SHA256 is
  `67ad0a56d90a1c0493aa57d64e395fcfd68e0e3caca8746d42206f142cc558e2`.
- `tools\verify_w1700k_v647_candidate.py`, SHA256
  `940d31e4a4a853f633ff66e55ffc2327e7984ab819a04c9a6d2c60291f35f14b`,
  reports `PASS_V647_OFFLINE_CANDIDATE`. Verification JSON SHA256 is
  `601454c80ed2fd9a6d5d498493f7dda8f9302a5c76a89ba21985c9472e503760`.
- Frozen FinalResult folder
  `W1700K-V6.47-Source-Audit-Cleanup-20260806-OFFLINE` contains 15 payload
  files totaling 24,129,037 bytes plus checksum/manifest files. Checksum replay
  has zero failures. `SHA256SUMS.txt`, `FILE_MANIFEST.txt`, and the release
  report SHA256 values are
  `8219d2d7a1f2585f5d486be3bea189f88af6120f211896e8a49e9589e699652b`,
  `1c2aedc7fddc696e0eb8ca3650ac25cc75dc048933be44a1406e42b9c552f79c`,
  and `bce4afb7bc17541bd89f9c3ee76e6b84c3fed401b52a15ddecb308c0931f3e68`.
- Obsolete V6.45 catcher/TFTP processes were disarmed before arming exact V6.47.
  `work\w1700k-com3-recover-v647.ps1`, SHA256
  `b2db44199ac1477a786d4a04ac456148fca58b2e7e7637de86c71e395611049e`,
  passes preflight and is armed at
  `work\live-captures\v647-recovery-20260806-065923`. COM3 is open at 115200
  8N1, but UART RX remains zero bytes and Ethernet has no carrier. No router
  identity, command, backup, transfer, sysupgrade, or persistent write has
  occurred. V6.47 remains unflashed; V6.15 remains the prior accepted live
  baseline.




## V6.48 mt7996 PCIe AER Recovery and Guarded Flash - 2026-08-06

- Root-caused the recurring WiFi/LuCI lockup to a PCIe completion timeout
  followed by Linux AER permanently disconnecting mt7996 because neither the
  primary nor HIF2 PCI driver registered an `error_detected` callback. The
  stock kernel avoids this path because `CONFIG_PCIEPORTBUS` is disabled,
  while the OpenWrt kernel enables `CONFIG_PCIEPORTBUS=y` and
  `CONFIG_PCIEAER=y`.
- Added `9999zzzzzzzzo-mt7996-handle-nonfatal-pcie-aer.patch`, SHA256
  `8f5dc98cba54e4fc10e08cd733a73ea4948e95a3e1215e4c07b064b964793e36`.
  Normal-channel notifications return `PCI_ERS_RESULT_RECOVERED` without
  MMIO so the existing mt7996 MCU-timeout/full-reset worker can run. Frozen or
  permanently failed channels remain fail-closed with
  `PCI_ERS_RESULT_DISCONNECT`. Strict checkpatch is clean.
- `tools\verify_w1700k_mt7996_pcie_aer.py` reports
  `PASS_MT7996_PCIE_AER_RECOVERY: 39 checks`. ABI and ELF proof places
  `pci_driver.err_handler` at byte 80 and resolves both driver objects to the
  same handler table. The callback calls only rate-limit/warn/error helpers.
- Rebuilt under WSL ext4 from source HEAD
  `5575e4a97f119f682223a090c4a78c0913f906f5` with a Linux-only PATH and
  `W1700K_EXPERIMENTAL_MT76_NPU=1`. Exact V6.48 image SHA256 is
  `f94ea464f35d7b0e2ad17245dd1f711305cf0c90342eebb0ee24ea5d9fa0c86e`;
  size is 20,620,092 bytes and FIT headroom is 76,996 bytes.
- Kernel and DTB are byte-identical to V6.47. Rootfs shape remains 1,146 files;
  only APK installed/scripts metadata and `mt7996e.ko` differ. Package
  contracts and maintainer-script contents are unchanged. Embedded
  `mt7996e.ko` SHA256 is
  `241e5921a3609e9b6ad84574e7fd74a6fc7c98cfd3f364938b8c88dc9069142f`.
- Full exact-module Ghidra 12.1.2 analysis exits 0 with 618 functions, 5,208
  symbols, and 38 selected decompiles. Report SHA256 is
  `d1dba8dd51319ad11a01a981c5976cb61c1e8fc84d8be8624065988a62a5ebd3`.
  The decompiler recovers normal state -> 5 and other states -> 4 with no
  hidden device access.
- `tools\verify_w1700k_v648_candidate.py` SHA256
  `5d81ece8374d234f6f718825e52829e5729dadc4d72b429055d138b1aaab254d`
  reports `PASS_V648_OFFLINE_CANDIDATE`. Result SHA256 is
  `b9f9be2411420217a7ec559ff488bd958ee557aac322931a2b349522ffd0cd51`.
  It replays V634/V635/V636/V637(48)/V638(28)/V641(21), mailbox ABI (45),
  stock RRO semantics (107), FIT/rootfs delta, signed APK, required package,
  and forbidden proprietary-binary gates.
- Frozen workspace and FinalResult bundle
  `W1700K-V6.48-MT7996-PCIE-AER-Recovery-20260806-OFFLINE` contains 17
  payload files and 20,891,936 payload bytes. Checksum replay and mirror
  comparison pass. `SHA256SUMS.txt` and `FILE_MANIFEST.txt` SHA256 values
  are `6f576f8eeb83aa481052ec447cb2743f730da9462df445be66ebb99fe19896e4`
  and `880cade5fb7c326fd79943a23da7a11d236e607f55e92d4376a41e323ee1535e`.
- Exact V6.48 guarded harness
  `work\w1700k-com3-recover-v648.ps1`, SHA256
  `47bfcf922f5b73fd72d726f48b3c3ed38caaa0d85349281580d68309fddb1a0e`,
  passes preflight and is armed as PID 17516 at
  `work\live-captures\v648-recovery-20260806-075618`. COM3 is open at
  115200 8N1, but UART RX remains zero bytes and Ethernet has no carrier.
  No target identity, router command, TFTP service, backup, transfer,
  sysupgrade, NAND/UBI write, bootloader/environment/factory/calibration
  access, or persistent state change occurred. V6.48 remains unflashed;
  V6.15 remains the prior accepted live baseline.

## V6.48 NPU Completion Reconciliation And Fresh COM3 Catcher - 2026-08-06

- Reconciled the exact stock `hostadpt.ko` TX callback and error policy against
  the current V6.48 prepared mt76 source and Ghidra-analyzed machine code.
  `tools\verify_w1700k_stock_hostadpt_error_policy.py`, SHA256
  `befcf47b349805e166b7fa0f7e73ade7081a9f85a8d21de5118456a8ae603795`,
  reports `PASS_STOCK_HOSTADPT_ERROR_POLICY`: 41 passed, 0 failed. Result JSON
  SHA256 is
  `123852628be603f6d15c8310b10c255a10859c2141d20401e7ee8c962f6dec5a`.
- Useful stock semantics are already present: two-group radio topology,
  five-descriptor headroom, 192-byte metadata cap, body-before-owner
  publication, explicit DMA/SKB ownership, and release-last token lifetime.
  Stock's nullable-device SKB leak, missing-unmap callback branch, raw SKB
  rejection frees, and global direct-unmap fallback are intentionally not
  cloned. No source or image mutation is justified.
- Report
  `work\W1700K_STOCK_HOSTADPT_ERROR_POLICY_RECONCILIATION_20260806.md`
  SHA256 is
  `1241d1c2fc65d84c2300eb2f7b45a094350e1555986f548b47eb53655be41b52`.
  Current completion matrix
  `work\W1700K_NPU_COMPLETION_MATRIX_20260806.md` SHA256 is
  `378b1c899813e14ca5b11b3727991759a260cc35a0e90be297dbf93adbd18512`.
- Static ping-pong fate, descriptor/doorbell order, DMA pairing, ring
  headroom, release-last token ownership, TXFREE callback progress, scatter,
  RRO integrity/session teardown, and vendor error-policy analysis are closed.
  Remaining NPU work is live FastTX/TXFREE/RRO concurrency, reset overlap,
  mode 0/3 throughput/recovery, PCIe AER recovery, and final WiFi/MLO tests.
- Stopped stale catcher PID 17516, opened COM3 directly, sent four harmless
  Enter probes, and received zero bytes. A fresh exact V6.48 catcher passed
  preflight and is armed as PID 15932 at
  `work\live-captures\v648-recovery-20260806-080658`. COM3 enumerates as the
  PL2303GC and is open at 115200 8N1, but UART RX remains zero and Ethernet is
  disconnected. No identity, router command, TFTP, backup, transfer,
  sysupgrade, NAND/UBI write, or protected-region access occurred. V6.48 is
  still unflashed; V6.15 remains the prior accepted live baseline.

## V6.48 NPU Topology And Sparse Audit - 2026-08-06

- Exact-source Sparse rebuild passed with 29 checked translation units, zero
  scoped diagnostics, build exit 0, and byte-identical unstripped `mt76.ko`
  and `mt7996e.ko` hashes. The audit harness now uses an exclusive lock;
  harness SHA256 is
  `34d56885f90095fce4bf12dce6f99ecee7114b75289af6eccf9841fb20d4edd2`.
- `tools\verify_w1700k_v648_npu_topology.py`, SHA256
  `dd8d472ea8869c73509b06b1d01c84f35ea71b029027f6ab7ac6df021d3ca3c1`,
  reports `PASS_V648_NPU_TOPOLOGY checks=38`; result JSON SHA256 is
  `25e240c7696245f5f9b199b4c702d5db84c01830edaf842be79247a3e7454745`.
- The source proof closes the static two-group alias/reset boundary: radios
  0/1 share group 0 and one queue object, radio 2 owns group 1 on HIF2,
  descriptor cleanup is idempotent, and full restart quiesces callbacks and
  sweeps token/DMA ownership before ring reset. No source/image mutation was
  justified.
- Report `work\W1700K_V648_NPU_TOPOLOGY_SPARSE_AUDIT_20260806.md` SHA256 is
  `4e4094a7e644068aa27bfe5a2c424528c85b8c117a0edf932728566cd709d951`.
  Remaining NPU proof is live-only concurrency, reset/AER recovery, mode 0/3
  throughput, and final WiFi/MLO behavior.
- After the USB serial reconnect, stale PID 15932 was stopped and exact
  guarded catcher PID 20900 was armed at
  `work\live-captures\v648-recovery-20260806-082820`. Preflight passes and
  COM3 is open, but UART RX is still zero bytes and Ethernet has no carrier.
  No target command or persistent/protected-state access occurred; V6.48 is
  unflashed and V6.15 remains the prior accepted live baseline.

## V6.49 Clang Static Audit And Source Hardening - 2026-08-06

- Added four behavior-preserving hardening patches after an exact 29-unit
  mt76/mt7996 Clang audit: initialize optional DTS power-limit length; guard
  required TX, BA, and off-channel context; harden mt7996 VOW, MLO station,
  channel-switch, reverse-fragment, and TWT contracts; and track HIF2 IRQ
  unwind ownership explicitly. Patch SHA256 values are
  `26271a127576576137def030ec7559522a1561a7506a6042e4c741a9d023ee71`,
  `3faac459b6c5cdf7c34b78e068cb5298fe88ad063bfe1d555153e2932307d5a2`,
  `26392070d64d3746fd18c19a32f4b6ab42bd0cedece468085ee95577ef961187`,
  and `30004469bd35dd3ecf8eac8cd78adfcc6a61cc21a43477c0749262d17bb46385`.
- Clean mt76 build exits 0. Unstripped `mt76.ko` and `mt7996e.ko` SHA256
  values are `f54b9300a63350bfde177d0ef8724012817edc134239cec86deca3111e7e1ecd`
  and `dd3f5e3aa3f111bec55a266542144772c2e45b7bd80450bcfdbee6d355a87c11`.
- Sparse passes 29 checks with zero scoped diagnostics. Clang 21.1.8 exits 0
  with zero analyzer failures. The fail-closed SARIF reconciliation removes
  exactly 10 expected findings from the frozen 27-finding V6.48 baseline,
  introduces zero findings, and accepts only 12 dead-store plus 5 known Linux
  list-model residuals. Result is
  `PASS_W1700K_CLANG_V649_RECONCILIATION`.
- Verifier and report SHA256 values are
  `e7169f6c948b62d18917d8948cefb78d16d147abfbe3201ba1b08cfa4b3cbf11`
  and `ac8a92856693597a9c77932f2246fae999e31d7f91eab4d12b04569322ade06b`.
- The last superseded V6.48 harness at
  `work\live-captures\v648-recovery-20260806-085238` was stopped before the
  source changes. It received zero UART bytes and saw no Ethernet carrier.
  No target identity, router command, TFTP, backup, transfer, sysupgrade,
  NAND/UBI write, or protected-region access occurred. V6.49 is not yet built,
  promoted, or flashed.

## V6.49 Offline Candidate Frozen And COM3 Catcher Armed - 2026-08-06

- Full source build at HEAD
  `5575e4a97f119f682223a090c4a78c0913f906f5` exits 0. Candidate
  `work\w1700k-clang-hardened-v6.49-20260806-sysupgrade.itb` is 20,620,092
  bytes, SHA256
  `d40223cfb9b289510d0e002cf5f0ac85bd64a424063e7ba43766db5d32e3a0ac`,
  with 76,996 bytes FIT headroom. Kernel and DTB are byte-identical to V6.48;
  the rootfs delta is limited to APK metadata and the rebuilt `mt76.ko`,
  `mt76-connac-lib.ko`, and `mt7996e.ko` modules.
- Embedded module SHA256 values are
  `8ce4613e720d62366325f2e0d715f4f020c0319fbe679ecbd7467eb863a7404b`,
  `78b114c931721ae6cf20a50473b83a82852ef54449423d692871d01f48dfb37c`,
  and `b4c5632aaadc5affcc8586469ef3f6f1248b4b8beba39029d2a437ed1e4519af`.
  Comprehensive Ghidra analysis exits 0 for all three unstripped modules:
  452/4,282, 180/1,603, and 619/5,213 functions/symbols respectively.
- `tools\verify_w1700k_v649_candidate.py` reports
  `PASS_V649_OFFLINE_CANDIDATE`; result SHA256 is
  `2c4ddf8398f8a480e2173b7630e87256514f30495d5ef42de56c6d6d2e322613`.
  Candidate report SHA256 is
  `962dac8cde982e47b730dc28d4e505d897336cb650e830f3e0b86d9ca3c4a3b6`.
- Frozen workspace and FinalResult bundle
  `W1700K-V6.49-Clang-Hardened-20260806-OFFLINE` contains 36 payload files
  and 23,140,074 payload bytes. Checksum replay and mirror comparison pass.
  `SHA256SUMS.txt` and `FILE_MANIFEST.txt` SHA256 values are
  `58db67924b52655efbf0cec95512536d3f082fdb8574862855f9df82e2085b51`
  and `8d75b66397f4bc9e5fa1edfb08f146f7f2b12270b407249f1462bb2a1c4d1de7`.
- Exact guarded V6.49 harness SHA256 is
  `c7f655d0445d5e8dfde70c64ae6c52f0d7b6be5b2d7533dcb6e1ee1b89f2a102`.
  It passed preflight and is armed as PID 11348 at
  `work\live-captures\v649-recovery-20260806-102700`. COM3 is open at
  115200 8N1, but UART RX remains zero bytes and Ethernet has no carrier.
  No target identity, command, TFTP, backup, transfer, sysupgrade, NAND/UBI
  write, or protected-region access has occurred. V6.49 remains unflashed;
  V6.15 remains the last accepted live baseline.

## V6.49 Unattended WiFi/NPU Live Gate Armed - 2026-08-06

- Extended the router-local synthetic suite to invoke the exact LuCI scan
  pipeline, `ubus call iwinfo scan {"device":"radioX"}`, while each 2.4 GHz,
  5 GHz EHT80/EHT160, 6 GHz EHT320, 5+6 GHz MLO, and tri-band MLO case is
  active. Every scan is bounded, JSON-checked, followed by AP/MLD recovery
  verification, and screened for firmware, reset, channel-switch, and fatal
  kernel signatures. Script SHA256 is
  `bad6ac444b4cf6ed20406e33dbc48f33474bebd23008aac230721e03f64bf30d`.
- Mode-0 and mode-3 host runners now accept an explicit source address so
  their SSH sessions remain pinned to the isolated W1700K Ethernet segment
  across reboot. SHA256 values are
  `f3529b97a787647208ce9232192515c5fbdab67c054d3dde0d2d22b275d41f8c`
  and `66b0b78d9ab69b40ded1581e575daaed7b329bc989e6b66ba6c451ac71dbb172`.
- Exact orchestration wrapper
  `work\run_w1700k_v649_live_validation.ps1`, SHA256
  `b76e527e2c2951f5bdc94110b0261bdedfe3acb283ad9caa5c050dfc25323c6c`,
  passed preflight and is armed as PID 2096 at
  `work\router-tests\v649-live-gate-20260806-104005`. It waits for the
  guarded recovery marker, replays every protected-backup checksum, verifies
  exact board/module identity, runs mode 0 and mode 3 plus synthetic TX and
  PCI lifecycle checks, and requires final persistent mode 0.
- The wrapper cannot route to the stable test address before exact COM3
  recovery completion. COM3 UART RX remains zero and Ethernet has no carrier,
  so neither wrapper has issued a target command or changed router state.

## V6.49 Compiled iwinfo Scan Contract Closed - 2026-08-06

- Full Ghidra analysis of the exact unstripped V6.49 `libiwinfo` completed at
  235 functions, 1,664 symbols, and eight selected scan-path functions. It
  recovers UCI radio-index validation, `1U << radio_idx` publication through
  compiled netlink attribute `0x14d`, bypass of existing AP/MLD interface
  reuse, temporary STA creation/deletion, and post-scan band filtering.
- `tools\verify_w1700k_v649_iwinfo_scan.py`, SHA256
  `696d0d1d7581c7c988a05b488bf7f99929fa08a41e3c934552ac9eb7979b76c3`,
  reports `PASS_V649_IWINFO_RADIO_PINNED_SCAN checks=14`. Result JSON SHA256
  is `4a0a5a3042fa9e87b30975639237e8c8b3a1b43580e45a629a6661569eb347ff`;
  Ghidra report SHA256 is
  `4ac558fe0a7b3dcec0e1828ec6767cf1b674cec3c418b957c4f36fafd5bd0379`.
- Audit report `work\W1700K_V649_IWINFO_SCAN_AUDIT_20260806.md` SHA256 is
  `1db138a6c2ac4f612a52013f724f2beeb1dcd0928a99e155cd49832f77553302`.
  This closes source-to-embedded-binary proof; live RF/RPC execution remains
  pending.
- Follow-on gate was restarted with this proof mandatory. Wrapper SHA256 is
  `28ba069140989a0d32ff71d3bd4c49b99e8eeb1dccd9bbfadd5ebd8781bea183`;
  PID 11520 waits at `work\router-tests\v649-live-gate-20260806-104844`.
  Recovery PID 11348 remains armed with zero UART RX and no Ethernet carrier.

## V6.49 COM3 Catcher Reopened - 2026-08-06 10:53 +03:00

- Windows enumerates the started Prolific PL2303GC adapter as COM3. The stale
  waiting recovery/validation processes were stopped and replaced so the
  physical reconnect uses a fresh serial handle.
- Exact recovery harness PID 7636 is armed at
  `work\live-captures\v649-recovery-20260806-105327`; exact follow-on PID
  24324 is waiting at
  `work\router-tests\v649-live-gate-20260806-105328`.
- COM3 opened at 115200 8N1, but repeated Enter/Ctrl-C polling still received
  zero UART bytes. Windows Ethernet remains `Disconnected` with no carrier.
  No target identity, command, TFTP, backup, flash, NAND/UBI write, or
  protected-state access occurred. Both gates remain fail-closed and V6.49
  remains unflashed.

## V6.50 NPU Status Reconciliation Frozen - 2026-08-06 12:02 +03:00

- Source patch `9999zzzzzzzzt-mt76-reconcile-npu-parity-status.patch`,
  SHA256
  `9720961604807a642614d7715ec7136b8800e9754c1193d43a5816623ccaac9b`,
  replaces nine stale debugfs parity labels with the conclusions supported by
  the completed static stock analysis. It changes no ownership or data-path
  implementation.
- The first package compile omitted `W1700K_EXPERIMENTAL_MT76_NPU=1`. The new
  fail-closed wrapper caught missing NPU symbols before promotion. The rejected
  modules were never packaged into a candidate or flashed. Correct build
  wrapper SHA256 values are
  `3449534a6b9aae732f3c647fbe4cd42abd8e53f0d6d0cb9d77563780d69543fb`
  and `53c293bc0ecb3ee61c93cd51b9ec27b447f0a18dfeb2e6a9fe905d3e20273eda`.
- Exact candidate is 20,620,092 bytes with 76,996 bytes FIT headroom. Kernel
  and DTB are byte-identical to V6.49; rootfs changes are limited to APK
  metadata and `mt76.ko`. Embedded `mt76.ko`, `mt76-connac-lib.ko`, and
  `mt7996e.ko` SHA256 values are
  `4e31bb81f82c74ce22e56b093b4f926fc1da69c22dcfd1349b35666068dd5b9c`,
  `78b114c931721ae6cf20a50473b83a82852ef54449423d692871d01f48dfb37c`,
  and `b4c5632aaadc5affcc8586469ef3f6f1248b4b8beba39029d2a437ed1e4519af`.
- Exact mt76 Ghidra analysis exits 0 at 452 functions, 4,282 symbols, and 45
  selected functions. Report SHA256 is
  `5ad733b123c9e2c1690c53abdec09ce361c8c8e1184c9c17759bf928ecd08bd6`.
  Connac and mt7996 inputs are byte-identical to their V6.49 analyses.
  `PASS_V650_NPU_STATUS_RECONCILIATION checks=95` and
  `PASS_V650_OFFLINE_CANDIDATE` both pass. Candidate verification JSON
  SHA256 is
  `8cac8541cc9505b5a2848f152078bf993674c33db8a4e0a703ed9acedd7ff79c`.
- Exact module-delta evidence is frozen under
  `work\build-v6.50-20260806\module-delta`; its nested checksum manifest
  SHA256 is
  `44bbb291be6e74585b9c4f4861a0691716513a3a0edca35ce7f881d74863e0ab`.
  Both mt76 `.text` sections are 92,152 bytes; only 17 bytes differ, all
  `seq_write()` string-length immediates. Connac and mt7996 are byte-identical.
- Corrected immutable workspace and FinalResult bundle
  `W1700K-V6.50-NPU-Status-Reconciliation-20260806-OFFLINE` has 97 payload
  files and 33,174,899 payload bytes. It passes 98 top-level checksum replays,
  including the nested module-delta checksum, and all 99 mirrored files match.
  `SHA256SUMS.txt` and `FILE_MANIFEST.txt` SHA256 values are
  `a34c6591793806d2e9d8dcae57cdd2dcdd2d80f00c220a03bdd80ca50745a19b`
  and `f79b258647a772b61e042da979282e3c8cf7afd58628501c2df6a2c524e0b011`.
  The first bundle attempt is explicitly renamed
  `REJECTED-NESTED-CHECKSUM`; its image was valid, but its top-level checksum
  omitted the nested checksum file.
- Recovery harness SHA256
  `2928f71689b65559308fc514f9ac5906877e9e40cecb075808ff6c71975f6e06`
  and follow-on SHA256
  `f5303c3f5c97919fb85aaed83aa7fed9707cb0d5381289289965aabe023f21f8`
  pass preflight. PIDs 6624/20624 remain armed. COM3 UART RX is zero bytes and
  Ethernet has no carrier, so target identity, TFTP, backups, sysupgrade,
  NAND/UBI writes, and protected-state access have not occurred. V6.15 remains
  the last accepted live baseline.

## V6.50 Ghidra-MCP Hostadpt Reconciliation - 2026-08-06 12:31 +03:00

- Ghidra 12.1 fully analyzed exact stock `hostadpt.ko`, SHA256
  `eef9e68ff3c7ef603ac36506dfdd0db832ad55cd3e17b709f46087ab9deba261`,
  as `/stock-vendor/hostadpt.ko`. MCP exported complete decompiles and
  function analyses for TX enqueue/consumer, RX/scatter consumer,
  `init_module`, `rxdone_cb`, and `cleanup_module`.
- New report `work\ghidra-mcp-hostadpt-v650-audit-20260806\README.md` and
  verifier `tools\verify_w1700k_v650_ghidra_mcp_hostadpt.py` have SHA256
  values
  `7ba84c2fbd503006d1cd4d9d9872eea4e610c67b4982ab46276b0b5cf39ac3c4`
  and
  `f31ffb91d9e042d50e6e051eb06b3578fd4ccb6ddb90e97f18fb71fca41ecd58`.
  `PASS_V650_GHIDRA_MCP_HOSTADPT_RECONCILIATION checks=96`; verification
  JSON SHA256 is
  `e37ec008d8fcb6ec5c28cdab1007c186a4173bec9556e084d0044a63854f95c0`.
  The 16-entry evidence checksum manifest replays with zero failures and has
  SHA256
  `77847588d434df600802efad2c151a48ab941578781681e3921404d15aa6abdc`.
- Fresh evidence independently confirms two 1024-entry/`0xd0` TX rings,
  five-descriptor admission reserve, metadata/SKB/DMA body-before-owner
  publication, consumer DMA-unmap/SKB-free/owner-clear order, two
  512-entry/`0x18` RX rings, bounded scatter gather, and `0x18c/0x19c` RX
  consumer doorbells. It also confirms stock cleanup only unregisters hooks;
  V6.50's explicit IRQ/NAPI/RCU/buffer/descriptor teardown is intentionally
  stronger. No additional source change is justified.
- Stale recovery/follow-on PIDs 6624/20624 were retired. Fresh recovery PID
  13248 owns COM3 in `v650-recovery-20260806-121948`; follow-on PID 12512
  waits in `v650-live-gate-20260806-122047`. Both preflights pass, but UART RX
  remains zero bytes and Ethernet has no carrier. No target identity, command,
  TFTP, backup, transfer, flash, NAND/UBI write, or protected-state access has
  occurred. V6.50 remains unflashed.

## V6.50 Clean COM3 Reopen - 2026-08-06 12:42 +03:00

- Windows positively enumerates `Prolific PL2303GC USB Serial COM Port (COM3)`.
  Retired stale recovery/follow-on PIDs 13248/12512 and opened a fresh exact
  V6.50 guarded recovery session as PID 23084 under
  `work\live-captures\v650-recovery-20260806-123954`.
- Exact artifact/host preflight passes and COM3 is open at 115200 8N1. The
  catcher repeatedly sends Enter/Ctrl-C, but a 60-second edge watch captured
  exactly zero UART bytes. `Ethernet` simultaneously reports `Disconnected`
  with zero carrier.
- No W1700K identity, command response, TFTP, RAM recovery, protected backup,
  image transfer, sysupgrade, NAND/UBI write, or protected-state access has
  occurred. V6.50 remains unflashed. The catcher remains armed; the current
  boundary is physical router power/UART RX-TX-GND connectivity, not an
  artifact or preflight failure.

## V6.51 WiFi Boot-Order Candidate - 2026-08-06 13:34 +03:00

- Historical live capture `work\router-tests\20260711-032237\synthetic-test.log`
  proves the boot failure: validation ran under world regdomain `00`, rejected
  `radio2 6g EHT320` before netifd could apply `US`, and consequently refused
  all three logical radios. Repeated `command failed: Not supported (-95)` was
  also traced to reapplying a global antenna mask for radio1/radio2 on the one
  shared wiphy.
- Source now normalizes empty/`00` country to `US`, prepares and verifies the
  regdomain before ordinary validation/setup, synchronizes all three logical
  radios to one shared country, and limits the global antenna-mask operation to
  radio0. LuCI hides `00` and propagates the selected country to radio0/1/2.
  Shell fixtures, JS syntax, native ucode parsing, and focused base-files,
  wifi-scripts, and LuCI package builds all pass.
- V6.50 is retired from live use because it contains this boot-order defect.
  Replacement candidate
  `work\w1700k-wifi-bootfix-v6.51-20260806-sysupgrade.itb` is 20,620,092
  bytes, SHA256
  `176496e7f05953867119ad3ca9af9d0fc850399db7a30db01bab9cb9f7532218`.
  Kernel, DTB, and all three mt76 modules are byte-identical to V6.50; only
  seven expected rootfs files differ.
- `tools\verify_w1700k_v651_wifi_boot.py`, SHA256
  `8982af3239fe150190737a6214e657972bba9697f1bf392daff80e43e9fe5171`,
  reports `PASS_V651_WIFI_BOOT_ORDER_CANDIDATE`. Verification JSON SHA256 is
  `b27ff6452afe5159f048ce43c89171c906a974a162c3b674406d013f16c7563b`.
- Exact V6.51 recovery harness SHA256 is
  `e7f528c4cd826cad2eca3af378ff3fa00dc80439edf61f4bb60c707dac6e1ac7`.
  It passes preflight and additionally requires exact installed WiFi hashes,
  US regdomain preparation, exact `0/2g 1/5g 2/6g` mapping, and absence of the
  retired country-00, validator, and `-95` signatures. COM3 is enumerated, but
  two direct probes captured zero UART bytes and Ethernet remains disconnected.
  No target command, backup, flash, NAND/UBI write, or protected-state access
  has occurred; V6.51 is not yet flashed.
- Recovery PID 17228 now owns COM3 in
  `work\live-captures\v651-recovery-20260806-133622`. Second-stage wrapper
  SHA256 `684687fdde06fd38634e0ca6356d5cc5109ad5d26d2cbdde0fae436c98afffb5`
  passes preflight; PID 23524 waits in
  `work\router-tests\v651-live-gate-20260806-134118` for the exact recovery
  marker, protected-backup replay, mode-0/mode-3 suites, LuCI scans, synthetic
  TX, and final persistent mode 0.
- After several minutes with zero UART RX and no Ethernet carrier, recovery
  PID 17228 and follow-on PID 23524 were cleanly stopped. A post-stop probe
  reopened COM3 successfully but reported `RX=0`, `CTS=false`, `DSR=false`,
  and `carrier=false`; Ethernet remained disconnected. No process is now
  holding COM3, and no target/protected/persistent state changed.

## V6.52 Unregister Token-Quiescence Source Gate - 2026-08-06 14:11 +03:00

- Source review found a concrete race not represented by the previous parity
  matrix. Reset and shutdown drained WiFi IRQ/tasklet, TX worker, RX NAPI, TX
  NAPI, and NPU IRQs before `mt7996_tx_token_put()`, but normal
  `mt7996_unregister_device()` swept and freed token/TXWI state before
  disabling its tasklet and without draining RX/TX NAPI. An already scheduled
  TXFREE poll could claim a token between unregister quiescence and the sweep,
  producing a use-after-free or double-completion boundary.
- Added source patch
  `work\9999zzzzzzzzu-mt7996-quiesce-unregister-token-sweep.patch`, SHA256
  `28e7b993a1668755e5aa5288f7399d7e40fb00a552f0de8beb8b2b10a1525b54`.
  It masks primary/HIF2 WiFi IRQs, drains tasklet, TX worker, enabled RX NAPI,
  and TX NAPI, then repeats the NPU provider IRQ mask before the existing NPU
  idle wait and token sweep. `checkpatch.pl --strict` reports 0 errors and 0
  warnings.
- Added exhaustive interleaving/static verifier
  `tools\verify_w1700k_v652_unregister_token_quiesce.py`, SHA256
  `9bd6dba1a5c92a8425c96ed5e61dda397b84d97df02d903ad4d752c1c228c94d`.
  The old model explores 63 states and finds 2 unsafe states; its shortest
  witness is TXFREE schedule/start/claim followed by unregister sweep
  remove/free. The hardened model explores 49 states and finds 0 unsafe
  states. Frozen JSON SHA256 is
  `5007b19a36fc7d57a50879453b3bd9b831ca785045e10b961658f7755b4c6a39`;
  verdict is `PASS_V652_UNREGISTER_TOKEN_QUIESCE`.
- Clean mt76 prepare applies the new patch exactly and prepared `init.c` and
  `mac.c` match the verified after-snapshot byte for byte. Focused mt76 compile
  with `W1700K_EXPERIMENTAL_MT76_NPU=1` exits 0 in 106 seconds. It emits only
  the existing unrelated `libwayland` dependency warning and the three
  pre-existing missing `MODULE_DESCRIPTION()` modpost warnings.
- Unstripped module SHA256 values are mt76
  `0c02cbf0f72db3a2e79c5271aef8db0b17388d9e19ad01c38d48aad085de6ffa`,
  mt76-connac
  `52296c935a8d82d7efe855a5253ebac40ee187882e60806e0e8fa329697ad08b`,
  and mt7996e
  `ecd08369485e37eac233ee8bb8e54e3d7a2c69e37a30e60f13261bfdcc0db18a`.
  Required `mt7996_unregister_device`, `mt7996_tx_token_put`, and
  `mt7996_wlan_npu_mode` symbols remain present.
- COM3 re-enumerated as the expected PL2303GC and opened at 115200 8N1, but a
  fresh two-Enter probe still received zero bytes with CTS/DSR/carrier false;
  Ethernet remains disconnected. No W1700K identity or target command was
  obtained. No flash, NAND/UBI, backup, or protected-state action occurred.
- V6.52 is source-gated only. A full FIT candidate, exact candidate verifier,
  guarded recovery harness, flash, and live WiFi/NPU validation remain pending.

## V6.52 Offline Candidate Promoted - 2026-08-06 14:25 +03:00

- Pinned full-build wrapper `work\run_v652_full_build.sh`, SHA256
  `bbc4f6d175a42fdc6d7407e6f078b36e90a4c3b6349795d938d8d6cf504fc5d0`,
  passes `bash -n` and shellcheck. It exits 0 in 96 seconds at source HEAD
  `5575e4a97f119f682223a090c4a78c0913f906f5` with experimental NPU enabled,
  exact source/verifier hashes, exact prepared source, and a passing prepared
  interleaving proof.
- Promoted offline candidate
  `work\w1700k-wifi-npu-v6.52-20260806-sysupgrade.itb` is 20,620,092 bytes,
  SHA256
  `166bf5ddb9ff3311868b931346150ff11a9fc3cbf7827ee6fda59e1518611db5`.
  FIT contains the expected ARM64 Linux 6.18.34 kernel, W1700K UBI DTB, and
  squashfs rootfs with 76,996 bytes of profile headroom.
- Against V6.51, kernel and DTB are byte-identical, rootfs shape and 1,146-file
  count are identical, and only APK installed/scripts metadata plus
  `lib/modules/6.18.34/mt7996e.ko` changed. Embedded mt76 and mt76-connac are
  byte-identical. Embedded mt7996e SHA256 is
  `10df7615d5ca3532fce118ac5066f1be2601bb2b1a948fd82bcea2f08937c075`.
  No stock `npu.ko`, `hostadpt.ko`, or `mt7990*` module is present.
- Full Ghidra 12.1 analysis of the changed unstripped mt7996e input completed
  with exit 0: 619 functions, 5,218 symbols, and 8 selected teardown functions.
  Report SHA256 is
  `668537e2aaf9a32b56fd204090bd1976b6f38fe24f3aa154c783d47bebf19b4b`.
  Its `mt7996_unregister_device()` decompile independently preserves tasklet
  drain, TX-worker park, RX/TX NAPI drain, repeated NPU IRQ masking, NPU stop,
  and only then `mt7996_tx_token_put()`.
- Exact candidate verifier
  `tools\verify_w1700k_v652_candidate.py`, SHA256
  `875f913c85707cc2d49c3784ae318450f57c2031c2f185f8b23f0f6e3ea1fe33`,
  reports `PASS_V652_OFFLINE_CANDIDATE`. Frozen verification JSON SHA256 is
  `d3a882c276ddb4d9ac97ba1c486e20ad6e8f32e6f5c856147d24baf5dba8114c`.
- V6.51 is now superseded and must not be flashed. V6.52 is the sole promoted
  offline candidate, but remains unflashed and unproven live.
- COM3 briefly enumerated and opened earlier in this pass but delivered zero
  bytes; after offline verification it disappeared from Windows again.
  Ethernet remains disconnected. No target identity, command, backup,
  recovery, flash, NAND/UBI write, or protected-state access occurred.
- V6.52-only recovery harness SHA256 is
  `353ea6584b976b31f02df84bac0b84b9acbc6c099e9216f7e4720fa8d3dac8f9`.
  It parses and passes exact preflight, pins the new FIT/verifier/module hashes,
  retains protected backups and positive W1700K identity gates, and adds a
  post-flash mt7996e unregister/reload smoke test with UAF/refcount/fatal-log
  rejection. PID 23352 is armed in
  `work\live-captures\v652-recovery-20260806-143034`; COM3 is open, but its raw
  capture remains zero bytes and Ethernet has no carrier. No target action has
  occurred.
- Second-stage wrapper `work\run_w1700k_v652_live_validation.ps1`, SHA256
  `64a0c0e0d652b14612003010156344ac3d2ddad0145b07eba1b118f94fe5caa4`,
  parses and passes preflight. PID 21784 waits in
  `work\router-tests\v652-live-gate-20260806-143255` for the exact recovery
  marker and backup checksums before mode-0/mode-3, LuCI scan, module reload,
  and synthetic-TX suites. It restores persistent mode 0. Both live processes
  remain gated at zero UART bytes.

## V6.53 Teardown-Hardening Candidate - 2026-08-06 15:54 +03:00

- V6.52 was retired before any target write after a second teardown audit found
  that mt7996 producers could requeue reset, coredump, RRO, RC, NPU-fault, or
  watchdog work after cancellation and race DMA/token/device destruction. Its
  recovery and validation PIDs were stopped; V6.52 must not be flashed.
- Added serialized teardown/requeue gating patch
  `9999zzzzzzzzv-mt7996-gate-teardown-work-requeue.patch`, SHA256
  `b0a5a4ad0841b41778fb46f4c2d110e431fd5285a5e12911a29817caa629daa6`,
  and HIF2 PCI-reference/list-lifetime patch
  `9999zzzzzzzzw-mt7996-fix-hif2-reference-lifetime.patch`, SHA256
  `246df490ee5c30c0ab397c0ea6b49317d5769c129bdde038f5ad62443aaf1581`.
  Both pass strict checkpatch with zero diagnostics.
- Behavioral verifiers report `PASS_V653_TEARDOWN_WORK_QUIESCE` with old
  33 states/41 transitions/5 unsafe and hardened 21/24/0, plus
  `PASS_V653_HIF2_LIFETIME`. The inherited V6.52 unregister/token proof still
  passes with old 63/96/2 unsafe and hardened 49/69/0.
- Deterministic clean normal and Sparse builds are byte-identical for all three
  mt76 modules. Sparse reports 29 checks and zero scoped diagnostics. Clang
  reconciliation reports 17 known residual findings, zero new findings, and
  `PASS_W1700K_CLANG_V653_RECONCILIATION`.
- Pinned full-build wrapper SHA256
  `a716064248f8e3d9c15919f8d69788f842cee803f70be512b92c20f678ea780e`
  exits 0 in 87 seconds at source HEAD
  `5575e4a97f119f682223a090c4a78c0913f906f5`.
- Sole offline candidate
  `work\w1700k-wifi-npu-v6.53-20260806-sysupgrade.itb` is 20,620,092 bytes,
  SHA256
  `1024d1354a4eeef6bb8bc9535a898b54312c9b8dd4be2943d49b162550f5ee19`,
  with 76,996 bytes FIT headroom. Kernel and DTB remain byte-identical to
  V6.52; the 1,146-file rootfs changes only APK metadata and mt7996e. Embedded
  mt7996e SHA256 is
  `941acc3df314fc747610900e3cb76fcae5e5a7eea05de1d638f677a3e39d748f`.
  No stock `npu.ko`, `hostadpt.ko`, or `mt7990*` module is present.
- Full Ghidra 12.1 analysis exits 0 with 626 functions, 5,346 symbols, and 18
  selected functions. Report SHA256
  `5d783af63b96d0b13609da10f26ceef681966d7789c2b8db277786ef0f226ec5`
  independently preserves gate publication, producer drain, second cancel,
  NPU stop, RRO drain, token/DMA cleanup, and balanced HIF2 release ordering.
- Candidate verifier SHA256
  `d4b0d823671ba35f66fb6e1951e0a4615048e8f707ccb9e2e51b1335df6bfb7`
  reports `PASS_V653_OFFLINE_CANDIDATE`; frozen result JSON SHA256 is
  `9f7bf669665ebe4e87fe4aedcc31a31def518e3142f9b947837502b3b3793b4f`.
- Immutable offline bundle is mirrored to
  `FinalResult\W1700K-V6.53-Teardown-Hardening-20260806-OFFLINE`: 47 payload
  files, 25,101,384 bytes, 48 replayed checksum entries. Bundle checksum and
  manifest SHA256 values are
  `5f3e76b8d55f5f24c914ceadd9b3d5ca0b330caa6585b3a2d12ceee4d0d55826`
  and `ffc6b0dd7ddd2a7cb91d547efaa37eeca6123ce85099bb43102eac6d2a3c5c5c`.
- Guarded recovery harness SHA256
  `86fc04fb66b77d648a3368ec4c755fbc8f805cc418715db4743be2dd38a2b022`
  is armed as PID 1324 at
  `work\live-captures\v653-recovery-20260806-155254`. COM3 opened at 115200
  8N1, but `serial.raw` remains zero bytes. Follow-on validator SHA256
  `134f72792d234b2312ac991d88b45a0ecc1010da0c631acff2597e764c77043b`
  is PID 22136 at `work\router-tests\v653-live-gate-20260806-155343` and waits
  for exact recovery, backup, and identity markers. No target command, backup,
  TFTP, recovery boot, flash, NAND/UBI write, or protected-state access has
  occurred.
- V6.48/V6.50 already closed the static stock hostadpt packet-ownership,
  descriptor/ring/doorbell, SKB/bufid/scatter, TXFREE/token, ping-pong, and RRO
  reconciliation. V6.53 adds teardown hardening without reopening that proof.
  Remaining Goal-2 work is live-only: FastTX/QDMA and TXFREE/RRO concurrency,
  reset overlap, malformed/fault behavior, actual PCIe AER recovery, mode 0/3
  throughput/recovery, and final WiFi/MLO performance.

## V6.54 Shared-Wiphy WiFi Fix - 2026-08-06 16:34 +03:00

- V6.53 was retired before target input. Its recovery and validation processes
  were stopped with zero UART bytes after a deeper WiFi audit found that its
  radio0-only antenna guard remained order-dependent; V6.53 must not be
  flashed.
- Historical capture `work\router-tests\20260710-235411\synthetic-test.log`,
  SHA256
  `f576eb1d36137ed9532f1d0c03369a686b50c1cb59263d2440bcab651c32f38f`,
  proves radio1 created a 5 GHz wdev before radio0 later hit
  `command failed: Not supported (-95)`. All three logical radios share one
  mt7996 wiphy, so four of six setup orders were unsafe under the old gate.
- Added exact-board patch
  `work\9999-wifi-scripts-w1700k-skip-shared-wiphy-antenna-write.patch`,
  SHA256
  `41641459a396c77a687e7225a2a4faebe456fff836dd377b96e9b119ffb37524`.
  It leaves the W1700K's fixed integrated antenna topology at the driver's
  full-chain default and preserves normal OpenWrt antenna writes elsewhere.
  Transmit-power behavior is unchanged.
- Ucode/legacy source hashes are
  `f89740da580c9477991b1fe15f4f316ffe10582a028083e73eb0f9c289a3da3d`
  and `cee97ea155fa8c692b24778845291de8c594e04f19624d05fa34a35e850ed4b0`.
  Dedicated verifier SHA256
  `b48ccfcc9fd5b4ccf8fd843dd8e01372fb7779a2738a04b2fc3b1bcef9e74fe3`
  reports 13 checks PASS, old unsafe orders 4, new unsafe orders 0. Legacy
  `sh -n`, focused package compilation, and native embedded-ucode compilation
  all pass; generated bytecode is 131,941 bytes.
- Replayed the exact current prepared mt76 tree against the frozen stock
  `hostadpt.ko` Ghidra/MCP audit. Result
  `work\build-v6.54-20260806\npu-static-hostadpt-replay.json`, SHA256
  `f0e8c1d6375f0a9783b6ee6942464b3057a6a369f3064a17ba9c298882eb5b55`,
  reports 96 passed and 0 failed. No additional offline NPU port is justified;
  the remaining NPU boundary is live concurrency, reset/fault/AER, and
  throughput/recovery testing.
- Pinned build wrapper SHA256
  `2dc07d5c0fc073968aa37ac9858a63f50ecfff67981b004b4b66d51d63d8e011`
  exits 0 in 88 seconds. V6.54 candidate is 20,620,092 bytes, SHA256
  `9b0c04db61ca16a9d2b9c60cc5e69402ad48a5f027f5fe7155e27779fdd682dc`,
  with 76,996 bytes FIT headroom.
- Exact V6.53 comparison proves byte-identical kernel, DTB, mt76,
  mt76-connac, and mt7996e. Rootfs remains 1,146 files and changes only APK
  metadata plus `lib/netifd/wireless/mac80211.sh`. No stock `npu.ko`,
  `hostadpt.ko`, or `mt7990*` module is present. Unchanged module binaries
  inherit the V6.53 Ghidra report covering 626 functions, 5,346 symbols, and
  18 selected functions.
- Candidate verifier SHA256
  `43bd152ba7bb668a6112a4a46ccd6efad708ca8016652d226482fb4c1af5085d`
  reports `PASS_V654_OFFLINE_CANDIDATE`; result JSON SHA256 is
  `08bf9ee11ddaae300723c4e47cd9bbd0eccf630eb29afd01fb37ef28ddcfe4ff`.
- Frozen FinalResult bundle
  `W1700K-V6.54-Shared-Wiphy-WiFi-Fix-20260806-OFFLINE` contains 86 files and
  40,833,062 bytes. All 84 checksum entries replay. `SHA256SUMS.txt` and
  `FILE_MANIFEST.txt` SHA256 values are
  `337dd155d5ec55ae06025e0afb4a24822391efbee1880daf21d4afce6f1ff4ac`
  and `3f7882fef0ed362bac0dd386e713b0dcef45ff661f89d7fe4863ea30f801b16a`.
- Guarded recovery harness SHA256
  `c4b7cde57867faac955d3aab5ca1e1445e55f50513f611657623c3400164793d`
  and follow-on validation SHA256
  `579ce5b0e84f0d3c5febf35c1ad8c867a64a8a07423b6577ebeec329dbb6488c`
  parse and pass exact preflight. PIDs 19616 and 15172 are armed at the paths
  in Live Handoff. UART RX is zero bytes and Ethernet is disconnected; no
  identity, command, backup, TFTP, recovery boot, flash, NAND/UBI write, or
  protected-state access has occurred.

## V6.54 Passive Boot Triage - 2026-08-06 16:58 +03:00

- COM3 captured two complete early vendor-boot sequences, 8,748 bytes total,
  SHA256
  `29b6fb6c5c43a7919470a491e1a3811ba5d510e98d69a0a586519ad0da8c45e4`.
  Both positively identify the W1700K platform as AXON 2.0 U-Boot,
  `AN7581GT`, 2 GiB DRAM, and Winbond `W25N04K` 512 MiB NAND.
- Both sequences reported `FDT_MAGIC or IH_MAGIC check fail` and
  `Parse main image fail`, then stopped before any prompt at
  `usxgmii_pcs_int en 1`. No panic, Oops, watchdog report, Linux boot, or
  bootloader prompt followed. Ethernet nevertheless negotiated at 1 Gbps on
  the isolated host link.
- Recovery PID 19616 and validation PID 15172 were disarmed. They issued no
  target command and performed no backup, TFTP transfer, recovery boot,
  sysupgrade, NAND/UBI write, environment update, or protected-state access.
- To eliminate transmit timing as a variable, COM3 is now owned by passive,
  receive-only logger PID 2540 at
  `work\live-captures\v654-passive-boot-20260806-165419`. It has received zero
  bytes because no later cold-boot edge has occurred. The next step is one
  cold power cycle under passive capture; flashing remains blocked until a
  prompt, positive identity, exact backup, remote hash, and `sysupgrade -T`
  all pass.

## V6.54 Live Access Reconciliation - 2026-08-06 19:55 +03:00

- Corrected the recovery prompt catcher so it sends no repeated input during
  DRAM or PHY initialization. UART interruption is now armed only after an
  explicit U-Boot autoboot window. Harness SHA256 is
  `331e02fd3edede46204d187ef3a29eb12751ab16b3eddf4bc4f17dc7c8a2792b`;
  its exact preflight passes. The paired validator SHA256 is
  `8468bc2383f4c2befbdf9427869d4eddd7421dc649075327ffbaa2f55af6193f`.
- A fresh live attempt at
  `work\live-captures\v654-recovery-20260806-194954` received zero UART bytes
  and was stopped before target input. Direct .NET serial, PuTTY `plink`, and
  WSL COM probes also received no data. Ethernet remains physically linked at
  1 Gbps but has no W1700K IPv4 or IPv6 neighbor.
- Windows Wi-Fi is positively identified as `Huawei-FjWf_5G`; therefore its
  `192.168.1.1` gateway is not the W1700K and was not contacted. V6.54 remains
  unflashed and no router state was changed.

## Live Gate Paused - 2026-08-06 20:00 +03:00

- Repeated access refresh remains unchanged: COM3 is free but returns no RX,
  isolated Ethernet has 1 Gbps carrier but no target neighbor, and no PuTTY
  process exposes the previously working connection. Static V6.54 WiFi/NPU
  work is exhausted; flash and live validation require the exact PuTTY mode/IP
  or restoration of the serial RX path. No router write occurred.

## V6.55 Diagnosis And V6.56 Live Promotion - 2026-08-07 03:40 +03:00

- The exact W1700K was reached by binding SSH/SCP to Ethernet source
  `192.168.1.224`; the host WiFi route to another `192.168.1.1` remains
  unrelated. Positive board identity was `gemtek,w1700k-ubi` before every
  persistent operation.
- V6.55 live `rmmod mt7996e` reproduced a deterministic D-state hang. COM3
  SysRq task evidence proved `napi_disable_locked -> mt76_dma_cleanup ->
  mt7996_dma_cleanup -> mt7996_unregister_device`. The mt7996 terminal path
  disabled TX NAPI once to drain completions and common mt76 cleanup disabled
  the same instance again. `napi_disable()` is not idempotent, so the second
  call waited forever.
- Added `9999zzzzzzzzz-mt76-make-terminal-tx-napi-disable-idempotent.patch`,
  SHA256
  `cee3d1d6fda713d3196880ef58ad17d87494a7d6bc1aab97a12337bb5265f7a6`.
  One `tx_napi_disabled` state bit and shared
  `mt76_dma_disable_tx_napi()` helper preserve terminal completion-drain order
  while making later cleanup a no-op. Strict checkpatch reports zero errors
  and zero warnings.
- Promoted V6.56 image
  `work\w1700k-wifi-npu-v6.56-20260807-sysupgrade.itb`, 20,624,188 bytes,
  SHA256
  `53f42e5a72baa22107cd4c9a1aac551018f7383ff0b9f17b3d5bf9e7a9da9ce5`.
  Exact verifier SHA256
  `de9ef7fc1d82aa77ac729cea57b52a194743cce9eada4094ec30e77c6fa74ba2`
  returns `PASS_V656_OFFLINE_CANDIDATE`; result JSON SHA256 is
  `ea274ab0275e5198e89324cde482f4d67538295a943f10053b94c4b895755456`.
- Router-side `sysupgrade -T`, matching upload hash, and preserved-config
  sysupgrade passed. Three watchdog-guarded unload/reload cycles passed and
  restored all three logical radios. A subsequent normal reboot returned with
  new boot ID `bded06e1-08eb-4382-abea-8e7e4ee03d79`.
- COM3 evidence
  `work\live-captures\v656-flash-20260807-032808\flash-serial.raw` is 75,232
  bytes, SHA256
  `2d99280f4871df28d8553672e199d04246dcb58250d8dac83202d7eb6f64f668`.
  It contains two complete Linux boots and five mt7996 WM starts, with no
  panic, Oops, `napi_disable_locked`, or recovery-watchdog marker.
- Current live state is V6.56, NPU mode 0, three radios `up=true`, no enabled
  SSID interfaces, and about 1.68 GiB memory available. The exact report is
  `work\W1700K_V6.56_IDEMPOTENT_TX_NAPI_LIVE_REPORT.md`.
- This closes the observed terminal TX-NAPI deadlock. Full stock-equivalent
  hostadpt packet ownership, TX/SKB/bufid/scatter/doorbell lifecycle,
  TXFREE/token equivalence, ping-pong packet fate, and RRO equivalence remain
  explicit NPU parity boundaries.

## Mode-0 Synthetic Stability Addendum - 2026-08-07 03:51 +03:00

- A full hidden-AP/MLO synthetic pass visibly cycled the WiFi stack but did
  not boot-loop V6.56. Boot ID stayed
  `bded06e1-08eb-4382-abea-8e7e4ee03d79`, uptime advanced normally, and COM3
  contained no reset or fatal marker.
- The harness restored `/etc/config/wireless` byte-for-byte. Current state is
  three radios up, no enabled SSID interface, no synthetic process/watchdog,
  and about 1.69 GiB free memory.
- The reported 5/30 failures were harness defects: ordinary APs were wrongly
  required to expose MLO link IDs, and the tri-band fixture did not use the
  canonical `radio1 radio2 radio0` UCI ordering.

## Corrected Synthetic Baseline - 2026-08-07 04:10 +03:00

- After correcting both fixtures, V6.56 passed 37/37 in production mode 0 and
  40/40 in experimental mode 3. Coverage includes 2.4 GHz EHT40, 5 GHz EHT80
  and EHT160, 6 GHz EHT320, 5+6 and tri-band MLO, all LuCI radio scans,
  validation negatives, service health, mode-3 NPU lifecycle/rings/handshake,
  TXFREE bounds, and byte-identical wireless restoration.
- Two mode-3 PCI unbind/rebind cycles passed. The mode-3 serial capture has no
  panic, Oops, BUG, duplicate-NAPI wait, or watchdog-expiry marker.
- Current router state is V6.56 production mode 0, boot ID
  `84940bcb-446c-4c0b-8e59-72e74f6b48e8`, three radios up, no enabled SSID,
  no fallback process, unchanged wireless hash, and about 1.68 GiB available.
- This establishes a clean synthetic WiFi/NPU baseline. It does not prove
  client compatibility, sustained throughput, packet ownership under traffic,
  TXFREE/token equivalence, ping-pong packet fate, or RRO parity.

## Mode-3 Management-Churn Boundary - 2026-08-07 04:18 +03:00

- `work\router-tests\npu-mode3-20260807-041412` passed the corrected 40/40
  synthetic matrix, 20 temporary VIF create/scan/delete cycles, and two PCI
  unbind/rebind cycles. Serial SHA256 is
  `72e7b24b5e74bf673a89f84b6256db6bd14c904c012296d2196f9913b3bd4aad`.
- Transport generation stayed 1; missing/mismatch/channel-timeout deltas were
  zero; channel management deferred 44 times; payload and TXFREE counters did
  not move. Module reload memory remained healthy above 1.63 GiB available.
- This closes the current synthetic VIF-management churn gate, not the live
  packet-path gate. Sustained payload ownership, concurrent reset/traffic,
  TXFREE/token equivalence, RRO traffic/session churn, AER, and throughput
  remain open.

## Boot-Loop Report Boundary - 2026-08-07 04:30 +03:00

- V6.56 did not autonomously boot-loop in the observed window. The pre-event
  boot ID `15bd7ec5-f0df-42f0-971b-50ee1621fabe` had reached about 393 seconds
  before a malformed Windows-to-SSH diagnostic invoked `wifi` and `reboot` as
  unintended shell pipeline stages.
- COM3 file
  `work\live-captures\bootloop-report-20260807\serial.raw`, SHA256
  `d5f51e0e781afd53c22964a36e9fadc06f4a98a9d8897418e48f63f72d396bd9`,
  proves one clean userspace reboot and no kernel panic, Oops, BUG, lockup, or
  watchdog expiry.
- Current observed boot ID is
  `6267382e-d25f-42c2-b05b-1723e6690825`; Ethernet, LuCI services, NPU
  firmware `0.1111`, and mt7996 WM/DSP/WA firmware returned normally with
  about 1.68 GiB available memory.
- This capture changes no firmware parity claim. No image, bootloader,
  environment, NAND/UBI, factory/calibration data, or persistent UCI state was
  written. Use SSH stdin scripts or local output filtering for future router
  diagnostics; do not send quoted alternation regexes through the Windows SSH
  command line.

## Live Boot-Loop Recheck - 2026-08-07 04:48 +03:00

- A second reported boot loop was not observed. V6.56 remained on boot ID
  `6267382e-d25f-42c2-b05b-1723e6690825` from at least 1,095 through 1,311
  seconds uptime with passing Ethernet, SSH, and LuCI probes.
- Production NPU mode 0 is loaded; no mode-3 fallback or test process exists.
  Current-boot fatal scans are clean, memory has about 1.68 GiB available, and
  UBI reports five healthy volumes with zero bad physical erase blocks.
- The 180-second passive COM3 file
  `work\live-captures\bootloop-live-20260807-044353\serial.raw` is empty with
  SHA256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
  it is supporting absence evidence only. No flash or persistent write was
  justified or performed.

## Exact Stock TX-Topology Live Gate - 2026-08-07 05:12 +03:00

- The unattended runner now supports an explicit default-off
  `-EnableStockTopology` gate and verifies the loaded module parameter. The
  runner and strict packet-probe SHA256 values are
  `3303e66ce7197c2a2481d0e7ea9758ab91dde7a2472cd5eb25c8c15bc4692095`
  and
  `36fc4bed94caa39c4f0e83d9c9d6d1dad4baefe973e8392caaf8562b8095e805`.
- V6.56 booted mode 3 with the exact statically recovered stock mapping:
  bands 0/1 share group 0, hardware index 18, register `0xd4420`, while band
  2 uses group 1, hardware index 21, register `0xd8450`. Group, alias, and
  register match checks all returned 1.
- The full synthetic matrix passed 40/40 under that topology, including 2.4
  GHz EHT40, 5 GHz EHT80/EHT160, 6 GHz EHT320, 5+6 MLO, tri-band MLO,
  backend/LuCI validation, and byte-identical restore. Serial SHA256 is
  `66645667a2056ab6276f4f87a28274d7337a21049f4271774ff5c9f097875d3b`;
  it records only the two intentional mode-entry/restore reboots and no fatal
  kernel signature.
- A no-client AP broadcast probe moved the AP netdev TX count from 0 to 128,
  but payload, enqueue, consumer, SKB-shadow, and classified-TXFREE counters
  stayed zero. This does not establish a broken NPU path: no station was
  associated, and source-level mac80211 gating plus a router-only frame path
  still need to be resolved. Packet ownership and TXFREE/token parity remain
  open.

## Post-Test Boot-Loop Reconciliation - 2026-08-07 05:25 +03:00

- The current boot ID
  `3fb922b4-c8a8-4112-9d54-0e543fc07c00` exactly matches `BootRestored` from
  the stock-topology runner. Across 64 five-second Ethernet-bound samples,
  ping and SSH passed 64/64 and uptime advanced from 512.10 to 840.32 seconds
  without a boot-ID change.
- Passive COM3 emitted no bytes. Current logs have no panic, Oops, BUG,
  watchdog, OOM, UBI, I/O, or ECC failure marker; all five UBI volumes are OK
  with zero bad PEBs. The previous serial stream's two resets were both
  orderly, intentional mode-entry/restore reboots; dual U-Boot stages make
  those two physical boots print four `Starting kernel` lines.
- `fw_printenv` reports bad CRC because both small UBI environment volumes are
  erased. The current chainloader/FIT boot is unaffected, and no environment
  write was attempted. Full evidence is in
  `work\live-captures\bootloop-investigation-20260807-051744\SUMMARY.md`.
- No flash or persistent router write was justified or performed. Production
  NPU mode 0, plain `mt7996e` module configuration, and the original wireless
  configuration remain restored.

## Router-Only NPU TX Lifecycle Gate - 2026-08-07 05:52 +03:00

- Source inspection proved the earlier bridge broadcast was dropped by
  mac80211 before mt76 because the temporary AP had `num_mcast_sta=0`.
  Standard monitor injection bypasses that no-association check while still
  selecting the real AP VIF and ordinary mt7996/mt76 DMA queue.
- Added a 67,080-byte static AArch64 injector, SHA256
  `75302bb4b94b69ef733fc7b770441ce5046f29e0b97e05dc94663b3531c3e707`,
  and hardened the runner/probe around explicit payload upload, exact topology
  verification, full completion convergence, and unchanged error invariants.
- `work\router-tests\npu-mode3-20260807-054601` passed: synthetic WiFi/MLO
  40/40, packet probe 0 failures, and two mode-3 module reload cycles. All 128
  injected frames reached payload, token allocation, NPU enqueue/consumer,
  SKB-shadow publish/cleanup, classified TXFREE, and token release. The live
  token count returned from 1 to 1; every checked mismatch counter stayed 0.
- COM3 SHA256
  `813b4104b1027f1055e7cb7ef00888ad67cafb321a05e33ff0f515fab7378bf3`
  records only the intentional mode-entry/restore boots and no fatal marker.
  Production mode 0 and the original wireless hash were restored.
- This closes the bounded normal no-client TX ownership lifecycle gate under
  exact stock topology. Sustained/multi-band pressure, malformed or missing
  TXFREE recovery, RRO session churn, provider trans-pointer ownership,
  external-client MLO, and throughput parity remain open. Full report:
  `work\W1700K_V6.56_ROUTER_ONLY_NPU_TX_LIFECYCLE_REPORT.md`.

## Reported Boot Loop Recheck - 2026-08-07 06:05 +03:00

- V6.56 is currently stable at boot ID
  `5a762115-0104-45f7-909d-10c7b7a6b04f`. Twenty of twenty clean SSH samples
  passed while uptime moved from 832.81 to 855.55 seconds.
- A 150-second passive COM3 capture was empty and current logs/pstore contain
  no fatal reset source. UBIFS completed one startup recovery after an earlier
  unclean reset; it did not recur.
- No reflash or persistent correction was warranted. The capture started
  after the report, so it establishes current stability rather than proving
  that no transient loop occurred beforehand. Full evidence:
  `work\live-captures\bootloop-live-20260807-060123\SUMMARY.md`.

## Controlled Dual-Stage Boot Reproduction - 2026-08-07 06:30 +03:00

- A controlled `sync; reboot` was captured end to end on COM3. One physical
  boot produced the expected two `Starting kernel ...` lines: the vendor
  loader first starts the OpenWrt U-Boot FIT from `chainloader`, then U-Boot
  2026.01 starts Linux 6.18.34 from the UBI `fit` volume. There was one
  intentional restart marker, one OpenWrt U-Boot banner, and no third pass.
- Before reboot, 12/12 Ethernet-bound samples retained boot ID
  `5a762115-0104-45f7-909d-10c7b7a6b04f` with uptime 1975.69 -> 2032.93.
  After reboot, 12/12 retained boot ID
  `6b86262a-5b7e-4055-b868-12d471cb55d5` with uptime 96.50 -> 153.73;
  the final service check reached 209.72 seconds.
- LuCI HTTP/HTTPS returned 200, `uhttpd`, `network`, and `wpad` were running,
  and all three physical radios reported up. Serial contained no panic, Oops,
  BUG, watchdog expiry, OOM, PCIe fatal error, mt7996 fatal error, or repeated
  reset.
- The erased/bad-CRC U-Boot environment remains non-causal and untouched.
  Missing `/etc/fw_env.config`, unavailable NVMEM, and the short completed
  UBIFS recovery are separate cleanup warnings. No flash or persistent
  configuration change was made. Evidence:
  `work\live-captures\bootloop-live-20260807-062220\SUMMARY.md`.

## Stock Provider-Context Lifetime Closure - 2026-08-07 07:10 +03:00

- Fresh Ghidra xrefs prove that stock `glb_npu_trans1` and
  `glb_npu_trans2` are assigned only by `npu_assign_trans`, in first/second
  successful transport-probe order. Stock teardown unregisters hooks but
  leaves the globals uncleared; they are provider-lifetime aliases, not
  packet objects.
- Patch A maps that ordering to explicit mt7996 primary/HIF2 ownership and
  adds read-only provider-context reporting. Patch B adds a managed primary
  consumer -> HIF2 supplier device link and balances the HIF2 reference on
  every primary-probe failure path.
- Final patch SHA256 values are
  `6ac5fc6a452624e6b863dc4a77bd5a155e7fbefaf59c7a923b44d6e0626e2be0`
  and
  `5ce071d0b77fe7862a2258ebab5923e1f512f3ba4afda3dbbebda42595db23bb`.
  Both pass strict checkpatch. The final mt76 compile exited 0; built
  `mt7996e.ko` SHA256 is
  `588adbc675a0eb05ee621625b2a4ee54597df3fd990a98fb92efb7d829aaef51`.
- No image containing these patches has been built, promoted, or flashed.
  COM3-guarded supplier-first unbind remains the required live gate. Report:
  `work\W1700K_STOCK_PROVIDER_CONTEXT_LIFETIME_REPORT_20260807.md`.

## One-Off Restart Capture - 2026-08-07 07:13 +03:00

- A real restart occurred after boot ID
  `6b86262a-5b7e-4055-b868-12d471cb55d5` was observed at 1178.17 seconds.
  The next reachable boot was
  `d7d87bdf-7e43-4d79-b6dd-e6ef04d7824b` at 49.51 seconds.
- The reset instant fell between passive COM3 windows, so its cause is not
  proven. The new boot then passed 45/45 plus 246/246 HTTP samples, reached
  1553.05 seconds on one boot ID, and emitted no serial reboot output.
- Reset GPIO/IRQ, NPU mode-0 watchdog IRQs, NPU core progress, temperatures,
  memory, services, and all three physical radios were healthy. No panic,
  Oops, BUG, OOM, AER fatal, thermal, or watchdog-expiry record appeared.
- A continuing boot loop did not reproduce. No flash or persistent router
  change was made. Evidence summary SHA256 is
  `506fae1885953a5f9529f4c5add0e9ddecbbc08355ab8f18374b80d562c193c9`:
  `work\live-captures\bootloop-followup-20260807-064410\SUMMARY.md`.

## V6.57 Provider-Context Live Baseline - 2026-08-07 07:47 +03:00

- Current installed image:
  `work\w1700k-wifi-npu-v6.57-20260807-sysupgrade.itb`, SHA256
  `c4004d89704046e18528f9679f1db9b24189cffd24d5d2b20afa26cbbe20870f`.
- Offline candidate verification passed. Mode 0 passed 37/37 synthetic tests;
  mode 3 passed 40/40, the exact 128-frame NPU TX lifecycle probe, and two
  deliberate module reload cycles with zero ownership-error deltas.
- The managed primary-consumer to HIF2-supplier device link exists live at
  `0000:01:00.0 -> 0002:01:00.0`; both provider contexts are present and
  distinct. Supplier-first unbind remains untested.
- The reported boot loop was the visible effect of the two deliberate WiFi
  module reloads, not a kernel reboot. Mode 3 was then returned to persistent
  mode 0 with one controlled reboot. Current boot ID is
  `fc60db21-bcc7-49cf-bcf3-71a48e237051`, module config is plain `mt7996e`,
  topology is `N`, and LuCI HTTP/HTTPS return 200.
- COM3 captured the three deliberate physical boots in this sequence and no
  Linux fatal signature. Serial SHA256 is
  `7be536b34c63bde7a51f8116d273c0e06d809d3000517aae447c0cfe12e1f619`.
- Full report:
  `work\W1700K_V6.57_PROVIDER_CONTEXT_LIVE_REPORT_20260807.md`.
- Promoted evidence bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.57-Provider-Context-Live-20260807`.
  Its 18-entry checksum set verifies cleanly; `SHA256SUMS.txt` SHA256 is
  `67bf753893f7c5fefb8b5d1e5dd399c6a1e6ea06db2b93d91df9b991df1e4491`.

## V6.57 Supplier-First Unbind Closure - 2026-08-07 08:14 +03:00

- Supplier-first HIF2 unbind passed in both mode 0 and mode 3. Unbinding
  `0002:01:00.0` automatically unbound its primary consumer
  `0000:01:00.0`; supplier and consumer then rebound successfully without a
  watchdog or fatal serial signature.
- Mode 3 balanced the complete transport lifecycle at
  `assign=2 unassign=2 hooks=2/2 blocked=0`, then restored stock topology N
  and NPU firmware 0.1111.
- The guarded runner intentionally booted mode 3 and then booted back to mode
  0. Final boot ID is `540ec1c7-4bc7-4899-b005-9585ec479a83`, persistent
  module config is plain `mt7996e`, and wireless UCI remained byte-identical.
- Evidence summary SHA256 is
  `8f2b5c1f254f58d6256f72cd6451fb5f3729eca571d3e0192c4b54a47ade43fe`.
  Full report:
  `work\W1700K_V6.57_SUPPLIER_FIRST_UNBIND_LIVE_REPORT_20260807.md`.

## Reported Boot Loop Recheck - 2026-08-07 08:23 +03:00

- No active loop reproduced after the supplier-first runner. The restored
  boot ID stayed `540ec1c7-4bc7-4899-b005-9585ec479a83` while uptime advanced
  from 403 to 569 seconds; Ethernet passed 20/20 pings and LuCI HTTP/HTTPS
  returned 200.
- Mode 0, core services, memory, and all three physical radios were healthy.
  Current logs and pstore contained no reset source or fatal signature, and
  no test/reboot hook remained enabled.
- COM3 enumerated but the 120-second passive stream was empty. No persistent
  state was changed. Evidence:
  `work\live-captures\bootloop-current-20260807-081922\SUMMARY.md`.

## Urgent Boot Loop Recheck - 2026-08-07 08:44 +03:00

- A second immediate recheck found no active loop. All 134 bound-Ethernet SSH
  samples returned boot ID `540ec1c7-4bc7-4899-b005-9585ec479a83`; uptime
  advanced monotonically from 1464.95 to 1774.59 seconds and LuCI returned
  HTTP/HTTPS 200.
- COM3 stayed open for five minutes and captured zero bytes. The green status
  LED was solid, reset-button IRQ count was zero, memory was healthy, and no
  current-boot fatal or reboot signature existed.
- UBIFS recovery on this boot confirms an earlier unclean shutdown, but no
  reset occurred inside the capture window, so power loss versus watchdog or
  another abrupt reset remains unclassified. No persistent state was changed.
  Evidence:
  `work\live-captures\bootloop-urgent-20260807-083703\SUMMARY.md`.

## Controlled Boot-Loop Classification - 2026-08-29 04:58 +03:00

- The reported loop did not reproduce. The pre-reboot boot remained stable for
  48/48 SSH samples. A subsequent controlled reboot was captured end to end on
  COM3: vendor U-Boot 2014 loaded OpenWrt U-Boot 2026, which verified the
  current W1700K FIT and started Linux. The two U-Boot banners are expected
  stages of one physical boot.
- The new Linux boot ID
  `86a1304c-bc28-474f-83b2-194c479b473c` passed 24/24 Ethernet-bound SSH
  samples while uptime advanced from 111.32 to 231.43 seconds. LuCI, `uhttpd`,
  and `rpcd` were reachable; memory was healthy; no fatal serial or kernel
  signature occurred.
- OpenWrt U-Boot used its default environment after reporting a bad redundant
  UBI environment CRC, but the default FIT boot completed. No environment
  write or firmware flash was performed.
- V6.58 remains unaccepted and must not be flashed until the clean-build loss
  of `CONFIG_MT76_NPU` is fixed and the image is rebuilt and reverified.
  Evidence: `work\live-captures\bootloop-live-20260829\SUMMARY.md`.

## V6.58r1 TXFREE Candidate Accepted - 2026-08-29 05:59 +03:00

- The rejected V6.58 clean-build regression is fixed. mt76 NPU selection is
  now scoped to the W1700K profile, and a clean compile proves
  `CONFIG_MT76_NPU=y`, `CONFIG_MT7996_NPU=y`, and inclusion of `npu.o`.
- Accepted image:
  `work\w1700k-wifi-npu-v6.58r1-20260829-sysupgrade.itb`, SHA256
  `a44307d24583e874a4987fb357adc85d95961d2e9315b7f06ab7dc6d819ea3ed`.
  Offline verification returned `PASS_V658R1_OFFLINE_CANDIDATE`.
- Full Ghidra analysis covered the exact shipped stripped module and the exact
  symbol-rich build object. All 17 shared loadable sections are byte-identical;
  selected TXFREE/NPU functions decompiled with zero failures.
- Post-flash WiFi acceptance passed 37/37. Corrected mode-3 TXFREE acceptance
  passed 40/40, all seven malformed cases, token-count invariance, and two
  complete module reload cycles without a fatal marker.
- Final mode is 0, module configuration is plain `mt7996e`, topology is N,
  wireless UCI is restored byte-identically, and live verification returned
  `PASS_V658R1_LIVE_ACCEPTANCE`.
- Full report:
  `work\W1700K_V6.58R1_TXFREE_LIVE_ACCEPTANCE_20260829.md`.

## V6.58r1 Boot-Loop Recheck - 2026-08-29 06:05 +03:00

- A newly reported boot loop did not reproduce. All 18 Ethernet-bound samples
  retained boot ID `eb8b9b8f-2b23-4915-aad2-adc031d32831` while uptime rose
  monotonically from 459.05 to 547.97 seconds.
- COM3 captured zero bytes for 120 seconds; a subsequent Enter probe returned
  the normal `root@OpenWrt:~#` prompt. Kernel fatal count and pstore were empty,
  memory was healthy, and the board remained `gemtek,w1700k-ubi`.
- No flash, reboot, module reload, service change, or persistent configuration
  mutation was performed. Evidence:
  `work\router-tests\bootloop-check-20260829-060251\SUMMARY.md`.

## V6.58r1 Duplicate-Address Boot-Loop Recheck - 2026-08-29 06:22 +03:00

- A second reported boot loop did not reproduce. Twenty-four Ethernet-bound
  SSH samples retained boot ID `eb8b9b8f-2b23-4915-aad2-adc031d32831` while
  uptime advanced from 1362.76 through 1484.62 seconds; `uhttpd` stayed
  running in every sample.
- COM3 returned the same boot ID at uptime 1510.22 and a normal root prompt.
  Current logs, memory, and pstore remained healthy.
- Windows has two distinct devices at `192.168.1.1`: Ethernet reaches the
  W1700K at `e6-58-09-33-39-a7`, while Wi-Fi reaches
  `80-ae-3c-fd-65-d0`. Unbound browser traffic is therefore ambiguous and can
  mimic page cycling without a router reboot.
- No runtime or persistent router state was changed. Evidence:
  `work\router-tests\bootloop-live-20260829\SUMMARY.md`.

## V6.59r2 Boot-Loop Recheck - 2026-08-29 08:08 +03:00

- No active boot loop reproduced. COM3 reached the existing root shell, and 12
  Ethernet-bound checks kept boot ID
  `9b98c378-e4db-46b6-926d-d9a58a7eb878` while uptime rose monotonically from
  1203.91 through 1363.57 seconds and then beyond 23 minutes.
- Pstore and fatal scans were empty. UBI, overlay, memory, services, LuCI, and
  all three physical radios were healthy. No router state was changed.
- The host still has distinct W1700K/Ethernet and other-router/Wi-Fi neighbors
  at `192.168.1.1`; bind all live W1700K checks to `192.168.1.224`.
- Evidence: `work\router-tests\bootloop-20260829-080205\SUMMARY.md`.

## V6.59r2 Current Packet-Path Acceptance - 2026-08-29 08:19 +03:00

- Exact-image mode-3 radio/MLO acceptance passed 40/40. A 128-frame router-only
  burst advanced payload, token, enqueue, consumer, SKB-shadow cleanup,
  classified TXFREE, and release counters by exactly 128, with no checked
  ownership error and no token leak.
- Two mode-3 module reloads passed. COM3 captured two requested physical boots
  with no fatal marker.
- Restored state is boot ID `248e7b71-f6c7-4e35-b69a-ac929c7c938d`, plain
  mode 0/topology N, byte-identical wireless UCI, no fallback or test interface,
  empty pstore, healthy memory, and LuCI HTTP/HTTPS 200.
- This closes bounded current-image TX lifecycle evidence. Sustained pressure,
  exact-image faulted TXFREE, RRO churn, and external-client parity remain.
  Report: `work\W1700K_V6.59R2_CURRENT_PACKET_PATH_ACCEPTANCE_20260829.md`.

## V6.59r2 Hardened Stock-Copy Acceptance - 2026-08-29 08:46 +03:00

- The exact flashed image uses custom NPU firmware SHA256
  `51f3583c45b2c356866ee53bd79dac93e10ad069bc75ff516019ea7edb929b79`.
- A strengthened live probe proved 54/54 requests had confirmed payload/token
  remaps and consumer completions. Local TXFREE lag remained one, host token
  balance/current returned to 0/0, and all newer TXP/remap error gates stayed
  zero. Three 40-test radio/MLO workloads and two module reloads passed.
- Restored state is boot ID `11e01712-84ba-43df-90c4-4ebd55873af5`, plain mode
  0, topology N, stock-copy N, byte-identical wireless UCI, no fallback/test
  interface, empty pstore, healthy memory, and LuCI 200.
- Keep stock-copy default-off until controlled performance evidence justifies
  it. Report:
  `work\W1700K_V6.59R2_STOCK_COPY_HARDENED_ACCEPTANCE_20260829.md`.

## V6.59r2 TXFREE Fault Acceptance - 2026-08-29 09:00 +03:00

- The exact flashed V6.59r2 image passed its default-off, root-only malformed
  TXFREE harness in mode 3 with stock topology enabled. All 40 radio/MLO checks
  and all seven malformed descriptor cases passed; token count stayed 1, two
  module reloads passed, and COM3 showed only the two requested boots.
- The router restored to boot ID `4a21d4c7-0ea0-4132-9a19-c9994925878f`,
  plain mode 0, topology N, stock-copy N, the exact wireless baseline, no
  fallback/test artifacts, empty pstore, healthy memory, and LuCI 200.
- Genuine duplicate, suppressed, and reordered TXFREE completion behavior is
  still an open live boundary. Report:
  `work\W1700K_V6.59R2_TXFREE_FAULT_ACCEPTANCE_20260829.md`.

## V6.59r2 Genuine TXFREE Replay - 2026-08-29 09:13 +03:00

- Extended only the host-side runner/probe with an explicit one-shot replay
  gate; defaults remain unchanged and no image rebuild was needed.
- On the exact V6.59r2 image, 128 genuine injected frames completed through the
  full NPU path. Exactly one hardware TXFREE descriptor was replayed after its
  normal release-last completion. The duplicate produced one expected missing
  claim/parser miss, no duplicate release or finalization mismatch, no token
  leak, and no fatal diagnostic. All 40 radio/MLO checks and two reloads passed.
- Router restored to boot ID `5c5c0cdc-9d61-4927-bb68-b32b44636c9f`, plain
  mode 0, topology/copy off, exact wireless baseline, clean pstore, healthy
  memory, and LuCI 200. Suppression and reordering remain open. Report:
  `work\W1700K_V6.59R2_TXFREE_REPLAY_ACCEPTANCE_20260829.md`.

## V6.59r2 Controlled Boot-Loop Recheck - 2026-08-29 09:31 +03:00

- The router stayed on boot ID `5c5c0cdc-9d61-4927-bb68-b32b44636c9f`
  through the initial watch, with healthy UBI, memory, SSH, and LuCI.
- A controlled reboot under COM3 produced one physical reset and one Linux
  boot. The two visible `Starting kernel` messages are the expected stock
  U-Boot and OpenWrt U-Boot chainloader stages. FIT verification passed and no
  fatal/reset marker followed.
- Current boot ID is `096fa1ad-d44c-4d96-8513-9258cf96a8d9`; LuCI HTTPS is
  HTTP 200. No flash or persistent state change was made. Evidence:
  `work\live-captures\bootloop-check-20260829-092732\SUMMARY.md`.

## V6.60 TXFREE Ordering Candidate and Boot Gate - 2026-08-29 10:29 +03:00

- Added the guarded, default-off genuine TXFREE suppression/reordering harness.
  Strict checkpatch, clean mt76 compile, full image build, full Ghidra analysis,
  and 95/95 offline checks passed. Candidate SHA256 is
  `d0b98ea2cedae43df73d3378386dc639288ec8e39b0f49789e4ed66f9dfa4bec`.
- Flashed V6.60 while preserving config. The baseline live suite passed 37/37,
  and the exact live `mt7996e.ko` hash is
  `05e61eb302e5261ff0a799872b42279dd6fd1c55140c509d17ad6f81ec8ac59e`.
- A reported boot loop did not reproduce. COM3 shows one requested sysupgrade
  restart and the normal two-stage U-Boot chain. Nineteen bound-Ethernet
  samples kept boot ID `70b96f74-41af-4a98-9a98-180ffbeaf3d6` while uptime
  rose from 286.29 to 602.99 seconds; a separate 120-second passive COM3
  capture was empty. No fatal marker or pstore record exists.
- V6.60 remains a candidate until guarded suppression/reordering and RRO/BA
  pressure pass. Report:
  `work\W1700K_V6.60_TXFREE_ORDERING_BOOT_ACCEPTANCE_20260829.md`.

## V6.60 Genuine TXFREE Ordering Accepted - 2026-08-29 10:45 +03:00

- Exact-image suppression injected 128 frames, withheld one genuine TXFREE,
  and produced exact release/TXFREE/token shortfalls of one. The first PCI
  teardown reclaimed the outstanding token and both reload cycles passed.
- Exact-image reordering held one descriptor, processed its successor first,
  then completed all 128 ownership lifecycles. Every checked counter converged,
  token count returned to baseline, and both reload cycles passed.
- Each run passed the 40-test radio/MLO suite and restored plain mode 0,
  topology N, wireless SHA256
  `588a3e98ee05a0d8649c392c54c4e879ac74230c1ed34a2134f07649e2aa945c`,
  empty pstore, healthy services/memory, and no fallback/test artifact.
- V6.60 is accepted for TXFREE duplicate/suppression/reordering scope. RRO/BA
  churn remains separate. Report:
  `work\W1700K_V6.60_TXFREE_ORDERING_LIVE_ACCEPTANCE_20260829.md`.

## V6.61 Sustained-Pressure Failure Boundary - 2026-08-29 11:48 +03:00

- V6.61 SHA256
  `b2a1004136150258b9a7d9c4ceab18a02b79ecaa0421146972a1c631ebd2ef3b`
  flashed successfully and passed the 37/37 baseline suite.
- A guarded 512-frame mode-3 run produced 499 genuine TXFREE completions,
  followed by repeated `GET_MIB_INFO` timeouts, a `BSS_INFO_UPDATE` timeout,
  WFDMA-busy containment, and terminal fail-closed transport quiescing. Linux,
  SSH, storage, and the boot remained alive.
- Reset recovery reclaimed the 13 missing test tokens plus one older token.
  The run exposed two diagnostic defects: ring occupancy used a reversed
  subtraction, and reset token reclamation was conflated with TXFREE progress.
- Evidence: `work\router-tests\npu-mode3-20260829-114830`.

## V6.62 Accounting/Backoff Candidate - 2026-08-29 13:14 +03:00

- Added bounded 5/10/20/30-second MIB survey backoff, first-timeout NPU ring/IRQ
  capture, explicit token-sweep accounting, and idempotent worker parking.
- Corrected provider ring occupancy to
  `(producer - consumer + ring_size) % ring_size` and exported a typed WLAN
  snapshot API for mt7996 diagnostics. Both patches pass strict checkpatch;
  target compile, clean mt76 compile, and full image build pass.
- Frozen `ubi2` image SHA256 is
  `b2227f11c163469460443461a01a0c72c1c9de167c77158d9d3d3b26f79eb300`;
  size is 20,628,284 bytes with 68,804 bytes FIT headroom. The candidate is not
  flashed or live-accepted. Full kernel/module Ghidra analysis and the pinned
  offline verifier are still running.

## Current Boot-Loop Triage - 2026-08-29 13:02 +03:00

- The reported boot loop did not reproduce on the Ethernet-bound W1700K.
  Boot ID `20c852bb-605d-48b5-8306-bf86f73fb752` stayed constant while uptime
  advanced from 5,049 through 5,355 seconds. SSH was responsive, load was
  idle, 1.68 GB remained available, pstore was empty, and a 65-second passive
  COM3 capture contained no characters.
- The router remains deliberately untouched on stable V6.61, plain mode 0.
  Evidence:
  `work\router-tests\bootloop-triage-20260829-1258\SUMMARY.md`.

## V6.64 Boot-Loop Recheck - 2026-08-29 16:13 +03:00

- The Ethernet-bound W1700K retained boot ID
  `f9c91626-c0bf-4803-8e5d-d30ea072469f` while uptime advanced from 585.41 to
  778.08 seconds; 12/12 pings, SSH, UBI, memory, and LuCI were healthy.
- A passive 60-second COM3 capture was silent and no fatal/reset marker was
  present. All physical radios were up, but the restored config intentionally
  had zero enabled `wifi-iface` sections, so no SSID was expected.
- No active boot loop reproduced and no flash, reboot, UCI change, or storage
  mutation was performed. Report:
  `work\W1700K_V6.64_BOOTLOOP_RECHECK_20260829.md`.

## V6.66 Management Queue Fix and Live Boundary - 2026-08-29 18:18 +03:00

- V6.66 SHA256
  `b021c4fa469ccb983d0fcc3e5a82aa0b936cc478b035224becb5c9019c9d379d`
  reserves ring 19 for shared normal-DMA PSD management traffic and derives
  NPU selection from queue ownership. Full build, image audit, contract checks,
  and headless Ghidra analysis passed.
- Mode 0 passed the complete radio/MLO suite. Mode 3 with stock topology also
  passed 40/40 checks, and a 512-frame guarded run converged every checked
  enqueue, consumer, shadow, TXFREE, release, and token counter.
- The original V6.65 management-token routing failure is closed in the tested
  operational path. A separate exit-cleanup boundary remains: monitor deletion
  and WiFi restoration triggered SNIFFER/BAND_CONFIG MCU timeouts, WFDMA-busy
  containment, and a downstream module-reload timeout.
- Recovery rebooted once as designed and restored plain mode 0. Boot ID
  `2eb46d24-04da-4950-8306-541b2a89f0f6` remained stable past 470 seconds;
  SSH, LuCI, UBI, memory, and pstore were healthy. This was not an active boot
  loop. Report:
  `work\W1700K_V6.66_MANAGEMENT_QUEUE_LIVE_STATUS_20260829.md`.

## V6.67 Ring-Depth Cross-Driver Failure - 2026-08-29 21:02 +03:00

- V6.67 SHA256
  `13614e43343dab01c2546cbff58586f4a9a2010c42d9f968a1714c79c8795d73`
  flashed successfully and passed the 37/37 mode-0 radio/MLO baseline with
  exact audited module hashes.
- The first 511-frame mode-3 control failed before injection because V6.67
  changed the actual host-adapter group-0 descriptor ring to 512 while the
  Airoha provider correctly required the stock `1024/1024` host-ring contract.
  Driver probe returned `-EINVAL` before WiFi initialization.
- The guarded runner restored persistent mode 0 on boot ID
  `4f7d31b1-7f64-4822-b62c-646630d35727`; V6.67 is not mode-3 accepted.
- Post-failure Ghidra and live-counter reconciliation supersedes the attempted
  Airoha `512/1024` edit. Stock `hostadpt.ko`, the NPU provider registers, and
  the successful pre-V6.67 topology all require `1024/1024` host-adapter TX
  rings. The independent group-0 512 boundary belongs to the firmware-private
  staging/downstream WFDMA producer path. The interrupted replacement build is
  invalid and no replacement FIT claim exists. Report:
  `work\W1700K_V6.67_RING_DEPTH_LIVE_STATUS_20260829.md`.
- The first verifier encoded the same conflation and is not a promotion gate.
  It must enforce `1024/1024` host-adapter rings while separately checking the
  proven downstream WFDMA geometry before another image is built.

## Stock Downstream WFDMA Ring Proof - 2026-08-29 23:22 +03:00

- Ghidra resolved the stock `mt7990.ko` queue tables after applying ELF
  section-relative symbol addresses. `txq_wa_layout` is at Ghidra
  `0x6083c0`, with `0x38`-byte entries. Its `band0 TXD` entry at `0x608430`
  specifies ring base `0xd4420`, descriptor size `0x10`, queue size `0x200`,
  and band mask `1`.
- `txq_wa_layout_pcie1` is at `0x607ef0`. Its `band2 TXD` entry specifies
  ring base `0xd8450`, descriptor size `0x10`, queue size `0x400`, and band
  mask `4`. The relocated queue-name pointers resolve to the literal stock
  strings `band0 TXD` and `band2 TXD`.
- Stock `mtk_pci.ko` copies each chip table's `q_size` field at entry offset
  `+0x1c` into the runtime queue object and writes it to `ring_base + 4`.
  This proves the stock downstream WFDMA max-count values are group 0 = 512
  and group 1 = 1024; they are independent from the `1024/1024`
  host-adapter descriptor rings.
- `mt7990_pci_wa_profile` at Ghidra `0x609c30` points to the decoded
  `txq_wa_layout`; `AN7581` is option-table entry 5 in
  `mt7990_chip_opt_tbl`. This ties the queue geometry to the selected stock
  MT7990/AN7581 profile rather than an unrelated embedded firmware blob.
- Active source patch
  `9999zzzzzzzzzzzz32-mt76-match-stock-downstream-wfdma-ring-depth.patch`
  keeps `q->ndesc`, host-adapter registers, software indices, and TX buffer
  allocations at 1024, while setting only stock-topology group 0's raw WFDMA
  max-count write to 512. Group 1 remains 1024.
- OpenWrt applies every regular file in a package patch directory. The
  `.patch.rejected` suffix did not quarantine V6.67 patch 31; a clean prepare
  proved it was still being applied. It now lives outside the active directory
  under `package/kernel/mt76/quarantined-patches/`.
- The corrected verifier passes four tests and reports host-adapter
  `1024/1024` plus downstream WFDMA `512/1024`. A clean mt76 prepare applies
  patch 32 and no retired ring-depth patch. Compile, image build, flash, and
  live `511/512/1024` acceptance remain pending.

## V6.68 Build-Verified Candidate - 2026-08-29 (Post-Proof Build)

- Patch 32 compiled against a freshly rebuilt Linux `6.18.34` target. The
  corrected contract verifier and all four unit tests pass.
- Full W1700K image build passed after removing inherited Windows PATH entries
  from the WSL build environment. Candidate SHA256:
  `d2861fe1a208a4de681bf0fe028b5fe581c9bbf09bd2550c7a28b7428f2b19e8`.
- FIT metadata is the established custom-firmware target:
  `gemtek_w1700k-ubi`, with kernel, W1700K DTB, and squashfs rootfs present.
- Embedded module disassembly proves the built image carries the intended
  split-domain behavior: host queue depth remains 1024, while marked W1700K
  NPU group 0 programs downstream WFDMA max count 512. Group 1 remains 1024.
- At this checkpoint it was build-verified only; the completed live gate is
  recorded immediately below. Build report:
  `work\W1700K_V6.68_DOWNSTREAM_WFDMA_BUILD_STATUS_20260829.md`.

## V6.68 Split-Domain Live Acceptance - 2026-08-29 23:54 +03:00

- The exact candidate above is now flashed and live accepted for the corrected
  host-adapter `1024/1024` plus downstream WFDMA `512/1024` scope.
- Mode 0 passed 37/37 tests. Modes 1 and 2 rejected through the helper and
  remained fail-closed under forced diagnostic boots, each passing 36/36 WiFi
  checks with no NPU transport slots or hooks.
- Two mode-3 runs each passed 40/40 tests, exact 511/512/1024-frame lifecycle
  reconciliation, two module reload cycles, and exact wireless restoration.
- Serial-backed evidence is under
  `work\live-captures\v668-mode3-ring-boundary-20260829-2347`; it contains
  exactly the two requested boots and no fatal signature.
- Final state is mode 0, topology N, boot ID
  `b49a2865-982b-4b57-b1f5-75d1627ca765`, wireless SHA256
  `588a3e98ee05a0d8649c392c54c4e879ac74230c1ed34a2134f07649e2aa945c`,
  healthy services/memory, and no fallback.
- External-client MLO/throughput and a direct read-only export of the private
  downstream WFDMA max-count register remain follow-up evidence, not failures
  of this synthetic gate.
- Live report:
  `work\W1700K_V6.68_DOWNSTREAM_WFDMA_LIVE_ACCEPTANCE_20260829.md`.

## Current Live-Accepted Image: V6.69 - 2026-08-30 00:38 +03:00

- V6.69 patch 33 closes the remaining diagnostics boundary without changing
  datapath behavior. Live private WFDMA max-count reads are `512/512/1024`
  for bands 0/1/2, all match flags are 1, and token output now states the
  packet-window versus global-IDR scope explicitly.
- Exact flashed image SHA256:
  `f319e067b9d1fa1d8a0b79dcd83e14df7821ddc8c18d2cb9da65c36fcd8fade9`.
- Mode 0 passed 37/37 checks. Guarded mode 3 passed 42/42 checks, exact
  511/512/1024-frame lifecycle reconciliation, and two module reload cycles.
- COM3 recorded exactly three deliberate W1700K boots and no fatal signature.
  The hash-pinned verifier reports `PASS_V669_LIVE_ACCEPTANCE`.
- Final router state is boot ID
  `9648041b-804f-43a8-96ba-e04cabc8934e`, mode 0/topology N, exact original
  wireless hash, healthy LuCI/rpcd/memory/validator, and no fatal kernel marker.
- The firmware is live accepted for the V6.69 observability scope. Mode 3
  remains guarded and opt-in. External-client MLO association and comparative
  throughput remain separate user-attended evidence.
- Reports:
  `work\W1700K_V6.69_LIVE_WFDMA_OBSERVABILITY_BUILD_STATUS_20260830.md` and
  `work\W1700K_V6.69_LIVE_WFDMA_OBSERVABILITY_LIVE_ACCEPTANCE_20260830.md`.

## Current Frozen Bundle - 2026-08-30 00:43 +03:00

- Path:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.69-Live-WFDMA-Observability-20260830`.
- Its 49 retained payload files total 26,337,071 bytes. Both
  `SHA256SUMS.txt` and `FILE-MANIFEST.txt` replay with zero failures.
- The router configuration backup is not included; retained evidence passed a
  credential-payload marker scan.

## Next Offline-Passed Candidate: V6.70 - 2026-08-30 01:45 +03:00

- Exact image SHA256:
  `c076d8501f8f4cfce2442dee08effc7d57be49e18e7197355d77d1ff3ce08998`.
- V6.70 adds negotiated EHT NSEP parity: EPCS advertisement follows the local
  read-only probe policy, while NSEP is enabled only when both local policy and
  peer EPCS are present. `w1700k-eht-nsep` reports the resulting accounting.
- It also fixes explicit mode-0 `stock_eht_nsep=0` persistence, updates the
  LuCI contract text, and reconciles stale V6.69/doorbell diagnostic claims.
- Strict patch checks, clean kernel/mt76 compilation, full Ghidra analysis,
  source verification, image build, FIT/rootfs audit, and exact candidate
  verification pass. Status is `PASS_V670_CANDIDATE`.
- The W1700K DTB and NAND/UBI partition layout are byte-identical to V6.69.
  No stock proprietary kernel module is shipped and all OpenWrt NPU firmware
  blobs retain their accepted hashes.
- V6.70 is not live accepted yet. The current live-accepted/frozen reference
  remains V6.69 until V6.70 passes guarded mode 0 and mode 3 synthetic tests.
  Report:
  `work\W1700K_V6.70_EHT_NSEP_NEGOTIATION_OFFLINE_CANDIDATE_20260830.md`.

## Current Live-Accepted Image: V6.70 - 2026-08-30 02:08 +03:00

- Exact flashed image SHA256:
  `c076d8501f8f4cfce2442dee08effc7d57be49e18e7197355d77d1ff3ce08998`.
- Live EHT behavior advertises EPCS while the read-only local policy is enabled
  and gates NSEP on both local policy and peer EPCS. Nine wiphy capability sets
  advertise EPCS; debugfs exposes complete local-and-peer accounting.
- Mode 0 passed 37/37 and stock-topology mode 3 passed 42/42. The exact
  511/512/1024-frame lifecycle matrix and two reload cycles passed, with live
  downstream WFDMA `512/512/1024` and no checked ownership failure.
- COM3 recorded exactly three deliberate W1700K boots and no fatal signature.
  The hash-pinned replay reports `PASS_V670_LIVE_ACCEPTANCE`.
- Final router state: boot ID `1d385777-bef3-4512-a557-ef2b1097d428`, mode 0,
  topology N, exact original wireless hash, 1,684,516 KiB available memory,
  healthy services/UBI/validator, and no fatal kernel marker.
- V6.70 supersedes V6.69 for the tested router-only scope. A real capable peer
  is still required to increment negotiated-NSEP counters; client throughput
  remains separate user-attended evidence.
- Reports:
  `work\W1700K_V6.70_EHT_NSEP_NEGOTIATION_OFFLINE_CANDIDATE_20260830.md` and
  `work\W1700K_V6.70_EHT_NSEP_NEGOTIATION_LIVE_ACCEPTANCE_20260830.md`.

## Current Frozen Bundle - 2026-08-30 02:12 +03:00

- Path:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.70-EHT-NSEP-Negotiation-20260830`.
- Direct image:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\w1700k-eht-nsep-negotiation-v6.70-20260830-sysupgrade.itb`.
- The bundle retains 71 payload files totaling 27,027,393 bytes. Both generated
  inventories replay with zero failures; the exact image hash is
  `c076d8501f8f4cfce2442dee08effc7d57be49e18e7197355d77d1ff3ce08998`.
- The configuration backup is excluded and retained evidence passed the
  credential-payload marker scan.

## Next Offline-Passed Candidate: V6.71 - 2026-08-30 03:31 +03:00

- Exact image SHA256:
  `70556ba3ae8dd9c19bfbcabd5575015e17745e24da4826ec92153968e8a56197`.
- V6.71 adds passive lifecycle observability for RX scatter, TX SKB/BufID,
  token/free-pool, RRO page/refill, BA window, and WCID/link/PHY/MLO session
  state. It also adds a bounded reset drain wait and dedicated session-map
  locking. It does not rewrite packet ownership or clamp reorder processing.
- Source, static, patch-corpus, compile, full-image, FIT/rootfs, and Ghidra
  gates pass. The exact status markers are `PASS_V671_SOURCE_CONTRACT`,
  `PASS_V671_GHIDRA`, and `PASS_V671_CANDIDATE`.
- Size is `20,632,380` bytes with `64,708` bytes of actual FIT headroom. This
  remains within the fixed volume but is 828 bytes below the prior conservative
  64-KiB margin, so later image growth requires explicit space revalidation.
- Kernel and DTB are byte-identical to V6.70. Only two APK database files,
  three mt76/mt7996 modules, and the NPU helper differ in the rootfs. LuCI,
  package count, OpenWrt NPU firmware, and forbidden-module absence remain
  unchanged.
- V6.71 has not been flashed. The current live-accepted and frozen reference
  remains V6.70 in mode 0. Guarded mode 0/mode 3 testing and real traffic are
  unresolved runtime boundaries.
- Explicit offline bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.71-RRO-Observability-OFFLINE-UNFLASHED-20260830`.
- Direct offline image:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\w1700k-rro-observability-v6.71-20260830-OFFLINE-UNFLASHED-sysupgrade.itb`.
- Its 37 payload files total 33,409,247 bytes; both inventories replay with
  zero failures. `OFFLINE-UNFLASHED.txt` is the authoritative promotion marker.
- Report:
  `work\W1700K_V6.71_RRO_OBSERVABILITY_OFFLINE_CANDIDATE_20260830.md`.

## Next Offline-Passed Candidate: V6.72 - 2026-08-30 04:38 +03:00

- Exact image SHA256:
  `1697e07d44267e0562bb2aa0ba20d305734b6da8addaf6aeefd06cff21868ce6`.
- V6.72 closes one stock-recovered RXDMAD-C ownership gap. Token presence,
  page-pool buffer, queue range, and the descriptor's reconstructed 36-bit DMA
  identity must now all validate under `rx_token_lock` before IDR removal.
- The 16-case state model demonstrates seven V6.71 divergences and zero V6.72
  divergences. Full Ghidra decompilation of the rebuilt modules confirms the
  DMA compare precedes `idr_remove` and queue dereference follows acceptance.
- Source, model, checkpatch, clean build, static, 6,416-patch corpus, full
  image, FIT/rootfs, and Ghidra gates pass. Exact status markers are
  `PASS_V672_SOURCE_CONTRACT`, `PASS_V672_GHIDRA`, and
  `PASS_V672_CANDIDATE`.
- Size remains `20,632,380` bytes with `64,708` bytes FIT headroom. Kernel,
  DTB, rootfs shape, LuCI, NPU helper, package set, and firmware remain
  unchanged; the payload delta is limited to APK bookkeeping and three
  mt76-family modules.
- V6.72 is not flashed or live accepted. V6.70 remains the current
  live-accepted/frozen reference in mode 0. Live mode 0/mode 3 and sustained
  RXDMAD-C counter validation remain promotion gates.
- Explicit offline bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.72-RXDMAD-C-Ownership-OFFLINE-UNFLASHED-20260830`.
- Direct offline image:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\w1700k-rxdmad-c-ownership-v6.72-20260830-OFFLINE-UNFLASHED-sysupgrade.itb`.
- Report:
  `work\W1700K_V6.72_RXDMAD_C_OWNERSHIP_OFFLINE_CANDIDATE_20260830.md`.

## Next Offline-Passed Candidate: V6.73 - 2026-08-30 15:45 +03:00

- Exact image SHA256:
  `e39fc2a5df5a4b8e5e6b725f71c4f05337823a19c67774799e1510911ee51b5b`.
- V6.73 retains V6.72's checked RXDMAD-C ownership fix and removes the
  ineffective RRO reset wait introduced by V6.71. The resulting contract is
  synchronous provider invalidation before MCU reset with passive activity
  accounting only.
- Stock Ghidra evidence, the V6.46 boundary, and an executable model agree.
  The model exposes three zero-observation late-entry traces and seven
  timeout/reset overlap traces in V6.72; V6.73 matches stock's core order.
- Source, model, strict checkpatch, clean mt76 build, helper fixture, full
  image, FIT/rootfs, exact candidate, and 654-function Ghidra gates pass.
  Exact markers are `PASS_V673_RRO_TEARDOWN_MODEL`,
  `PASS_V673_SOURCE_CONTRACT`, `PASS_V673_GHIDRA`, and
  `PASS_V673_CANDIDATE`.
- Size remains `20,632,380` bytes with `64,708` bytes FIT headroom. Kernel,
  DTB, generic mt76 modules, package set, and NPU firmware are unchanged from
  V6.72; only APK bookkeeping, `mt7996e.ko`, helper, and LuCI differ.
- V6.73 is not flashed or live accepted. V6.70 remains the current
  live-accepted/frozen reference in mode 0. Exact-image mode 0/mode 3,
  tri-radio/MLO, BA teardown stress, and zero MCU-reset failures remain
  promotion gates.
- Report:
  `work\W1700K_V6.73_RRO_TEARDOWN_REGRESSION_FIX_OFFLINE_CANDIDATE_20260830.md`.

## V6.73 Offline Bundle - 2026-08-30 15:50 +03:00

- Bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.73-RRO-Teardown-Regression-Fix-OFFLINE-UNFLASHED-20260830`.
- Direct image:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\w1700k-rro-teardown-regression-fix-v6.73-20260830-OFFLINE-UNFLASHED-sysupgrade.itb`.
- Exact SHA256:
  `e39fc2a5df5a4b8e5e6b725f71c4f05337823a19c67774799e1510911ee51b5b`.
- Both 54-record bundle inventories replay with zero failures. No backup or
  credential-pattern match is retained. `OFFLINE-UNFLASHED.txt` is the
  authoritative promotion boundary.

## Next Offline-Passed Candidate: V6.74 - 2026-08-30 16:25 +03:00

- Exact image SHA256:
  `057f183aa6389676d08298c5653daaa6a40aefd5f81172e8377d71c9ac2ffb7c`.
- V6.74 retains V6.73 and closes the RRO MSDU-page initial DMA publication
  gap. Ordinary RX page pools remain `DMA_FROM_DEVICE`; only CPU-written RRO
  page headers use `DMA_BIDIRECTIONAL` with explicit CPU and device sync.
- Owner publication occurs only after host page-map bookkeeping allocation
  succeeds and before descriptor/page-map publication. The implementation
  follows stock's populate, synchronize, publish contract through native
  OpenWrt page-pool ownership.
- Strict checkpatch, clean mt76 build, 29-unit Sparse, executable model,
  source contract, full image, FIT/rootfs, embedded disassembly, and full
  Ghidra gates pass. Exact markers are `PASS_V674_RRO_PAGE_DMA_MODEL`,
  `PASS_V674_SOURCE_CONTRACT`, `PASS_V674_GHIDRA`, and
  `PASS_V674_CANDIDATE`.
- Size remains `20,632,380` bytes with `64,708` bytes FIT headroom. Kernel,
  DTB, rootfs shape, packages, NPU firmware, `mt76-connac-lib.ko`, LuCI, and
  configuration are unchanged from V6.73. Only APK bookkeeping, `mt76.ko`,
  and `mt7996e.ko` differ.
- V6.74 is not flashed or live accepted. V6.70 remains the current
  live-accepted/frozen reference in mode 0. Exact-image mode 0/mode 3,
  tri-radio/MLO, sustained RRO/BA traffic, owner/refill telemetry, and fatal
  scan remain promotion gates.
- Report:
  `work\W1700K_V6.74_RRO_MSDU_PAGE_DMA_HANDOFF_OFFLINE_CANDIDATE_20260830.md`.

## V6.74 Offline Bundle - 2026-08-30 16:30 +03:00

- Bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.74-RRO-MSDU-Page-DMA-Handoff-OFFLINE-UNFLASHED-20260830`.
- Direct image:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\w1700k-rro-msdu-page-dma-handoff-v6.74-20260830-OFFLINE-UNFLASHED-sysupgrade.itb`.
- Exact SHA256:
  `057f183aa6389676d08298c5653daaa6a40aefd5f81172e8377d71c9ac2ffb7c`.
- Both 62-record bundle inventories replay with zero failures. No backup or
  credential-pattern match is retained. `OFFLINE-UNFLASHED.txt` is the
  authoritative promotion boundary.

## Next Offline-Passed Candidate: V6.75 - 2026-08-30 17:06 +03:00

- Exact image SHA256:
  `86509ed0fbec340c0219283afa533d864e7cd7287a24be223ee5a36303481475`.
- V6.75 retains V6.74 and rejects invalid 12-bit RRO producer-session IDs
  before address-element lookup. Normal sessions `0..1023` and particular
  sentinel `1024` remain valid; `1025..4095` now enter existing integrity and
  NPU RX recovery with dedicated counter/last-ID telemetry.
- The exhaustive model covers all 4,096 values. Strict checkpatch, clean mt76
  build, 29-unit Sparse, source contract, full image, FIT/rootfs, stripped
  embedded disassembly, and full Ghidra gates pass. Exact markers are
  `PASS_V675_RRO_SESSION_BOUND_MODEL`, `PASS_V675_SOURCE_CONTRACT`,
  `PASS_V675_GHIDRA`, and `PASS_V675_CANDIDATE`.
- Size remains `20,632,380` bytes with `64,708` bytes FIT headroom. Kernel,
  DTB, rootfs shape, packages, generic mt76 modules, LuCI, configuration, and
  NPU firmware are unchanged from V6.74. Only APK bookkeeping and
  `mt7996e.ko` differ.
- V6.75 is not flashed or live accepted. V6.70 remains the current
  live-accepted/frozen reference in mode 0. Exact-image mode 0/mode 3,
  tri-radio/MLO, sustained RRO/BA, zero unexpected invalid-session growth,
  and fatal-log scans remain promotion gates.
- Remaining provider-specific RRO, scatter, SKB/BufID, and full NPU parity
  boundaries are still unresolved.
- Report:
  `work\W1700K_V6.75_RRO_SESSION_BOUND_OFFLINE_CANDIDATE_20260830.md`.

## V6.75 Offline Bundle - 2026-08-30 17:08 +03:00

- Bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.75-RRO-Producer-Session-Bound-OFFLINE-UNFLASHED-20260830`.
- Direct image:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\w1700k-rro-producer-session-bound-v6.75-20260830-OFFLINE-UNFLASHED-sysupgrade.itb`.
- Exact SHA256:
  `86509ed0fbec340c0219283afa533d864e7cd7287a24be223ee5a36303481475`.
- Both 65-record bundle inventories replay with zero failures. No backup or
  credential-pattern match is retained. `OFFLINE-UNFLASHED.txt` is the
  authoritative promotion boundary.

## Next Offline-Passed Candidate: V6.76 - 2026-08-30 18:07 +03:00

- Exact image SHA256:
  `8d74019a3aa3fdf0db5f8c605662cbdd7851773359872b0bb22a259f76567f82`.
- V6.76 retains V6.75 and closes a producer-index ownership defect in NPU TX
  cleanup. An out-of-range consumer no longer becomes full-flush sentinel
  `-1`, and an in-range consumer cannot advance beyond the host's current
  `q->queued` window.
- Stock `hostadpt.ko` establishes two 1,024-entry rings with consumer registers
  `0xac`/`0xbc`. The new helper validates the wrap-aware distance before any
  reclaim, records fault state, and schedules existing method-8 recovery only
  after releasing the cleanup lock. Ordinary DMA queues and deliberate flushes
  retain their prior behavior.
- The 14,675,196-check model, strict checkpatch, source contract, clean mt76
  build, 29-unit Sparse, full image, FIT/rootfs, 450-function mt76 Ghidra,
  654-function mt7996e Ghidra, and aggregate inventory gates pass. Exact status
  includes `PASS_V676_GHIDRA`, `PASS_V676_CANDIDATE`, and
  `PASS_V676_AUDIT_INVENTORY`.
- Size remains `20,632,380` bytes with `64,708` bytes FIT headroom. Kernel,
  DTB, rootfs shape, packages, LuCI, helpers, services, configuration, and all
  four NPU firmware blobs are unchanged from V6.75. Only APK bookkeeping and
  all three mt76-family modules differ.
- The connac module change is expected shared-ABI propagation: the aligned
  diagnostic struct grows 48 bytes inside `mt76_dev`, and exactly 48 connac
  binary bytes change across 46 executable instruction ranges to update later
  field offsets.
- V6.76 is not flashed or live accepted. V6.70 remains the current
  live-accepted/frozen reference in mode 0. Promotion requires exact-image mode
  0/mode 3, tri-radio/MLO, sustained TX/RRO, new-counter, recovery, throughput,
  and fatal-log validation.
- Full provider-specific NPU parity remains unresolved beyond this concrete
  producer-index ownership boundary.
- Report:
  `work\W1700K_V6.76_NPU_TX_CONSUMER_BOUNDS_OFFLINE_CANDIDATE_20260830.md`.

## V6.76 Offline Bundle - 2026-08-30 18:10 +03:00

- Bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.76-NPU-TX-Consumer-Bounds-OFFLINE-UNFLASHED-20260830`.
- Direct image:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\w1700k-npu-tx-consumer-bounds-v6.76-20260830-OFFLINE-UNFLASHED-sysupgrade.itb`.
- Exact SHA256:
  `8d74019a3aa3fdf0db5f8c605662cbdd7851773359872b0bb22a259f76567f82`.
- The 70 retained payload files total 31,244,056 bytes. Both bundle inventories
  replayed with zero failures. No backup or credential-pattern
  match is retained. `OFFLINE-UNFLASHED.txt` is the authoritative promotion
  boundary.

## Next Offline-Passed Candidate: V6.77 - 2026-08-30 18:52 +03:00

- Exact image SHA256:
  `d96507117d22629b6e2447b2b55062ec080556d76ecfde0839df9edac218aeed`.
- V6.77 retains V6.76 and restores the NPU TX descriptor-owner admission gate
  lost during patch-stack rebasing. It rejects an NPU-owned descriptor at the
  producer head with `-EBUSY` before payload DMA mapping or mt7996 token
  allocation, while preserving ordinary queues and the five-entry headroom.
- The exhaustive model covers 2,097,152 ring states: old owner-overwrite
  admissions are 1,043,456, fixed admissions are zero, and stock-model
  mismatches are zero.
- Strict checkpatch, V6.77 and inherited V6.76 source contracts, clean mt76
  build, 29-unit Sparse, full image, exact FIT/rootfs, and aggregate inventory
  pass. Full Ghidra analysis covers 448 mt76, 180 connac, and 660 mt7996e
  functions; its 24 checks confirm the machine-level owner gate and unwind.
- Size remains `20,632,380` bytes with `64,708` bytes FIT headroom. Kernel,
  DTB, packages, LuCI, configuration, and all four NPU blobs are unchanged from
  V6.76. Exactly APK bookkeeping and the three mt76-family modules differ.
- V6.77 is offline and unflashed. V6.70 remains live accepted. Promotion still
  requires separately authorized exact-image mode 0/mode 3, tri-radio/MLO,
  sustained TX/RRO, new-counter, memory, throughput, and fatal-log gates.
- Full provider NPU and performance parity remain unresolved beyond this
  concrete owner-admission boundary.
- Report:
  `work\W1700K_V6.77_NPU_TX_OWNER_GATE_OFFLINE_CANDIDATE_20260830.md`.

## V6.77 Offline Bundle - 2026-08-30 18:58 +03:00

- Bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.77-NPU-TX-Owner-Gate-OFFLINE-UNFLASHED-20260830`.
- Direct image:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\w1700k-npu-tx-owner-gate-v6.77-20260830-OFFLINE-UNFLASHED-sysupgrade.itb`.
- Exact SHA256:
  `d96507117d22629b6e2447b2b55062ec080556d76ecfde0839df9edac218aeed`.
- The 72-record package retains the exact image and complete scoped evidence.
  The packager replays every size/hash entry, rejects output overwrites and
  retained credential patterns, and includes no router backup.
  `OFFLINE-UNFLASHED.txt` is the authoritative promotion boundary.

## Next Offline-Passed Candidate: V6.78 - 2026-08-30 20:44 +03:00

- Exact image SHA256:
  `da2c79874d6ba074d37f9dd6401ebbcecaf446a8a6adbd053160467b6959541c`.
- V6.78 retains V6.77 and fixes the NPU TXWI streaming-DMA handoff. Inline
  TXWI copy/token inspection now completes while CPU-owned, followed by device
  sync, the retained DMA barrier, and owner publication.
- The six-order model, strict checkpatch, V6.78 plus inherited V6.77/V6.76
  source contracts, clean mt76 build, 29-unit Sparse, full image, exact
  FIT/rootfs, and audit inventory pass. Full Ghidra covers 1,288 functions and
  passes 31 machine/decompile checks.
- Size remains `20,632,380` bytes with `64,708` bytes FIT headroom. Kernel,
  DTB, rootfs shape, package set, connac, mt7996e, LuCI/configuration, and all
  NPU firmware are unchanged from V6.77. Only APK bookkeeping and `mt76.ko`
  differ.
- V6.78 is offline and unflashed. V6.70 remains live accepted. Promotion still
  requires separately authorized exact-image mode 0/mode 3, tri-radio/MLO,
  sustained TX/RRO, memory, telemetry, throughput, and fatal-log gates.
- Full provider NPU and sustained-performance parity remain unresolved beyond
  this concrete DMA ownership/order boundary.
- Report:
  `work\W1700K_V6.78_NPU_TXWI_DMA_HANDOFF_OFFLINE_CANDIDATE_20260830.md`.

## V6.78 Offline Bundle - 2026-08-30 20:49 +03:00

- Bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.78-NPU-TXWI-DMA-Handoff-OFFLINE-UNFLASHED-20260830`.
- Direct image:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\w1700k-npu-txwi-dma-handoff-v6.78-20260830-OFFLINE-UNFLASHED-sysupgrade.itb`.
- Exact SHA256:
  `da2c79874d6ba074d37f9dd6401ebbcecaf446a8a6adbd053160467b6959541c`.
- Both 78-record inventories replay with zero failures. No backup or retained
  credential-pattern match is present. `OFFLINE-UNFLASHED.txt` remains the
  authoritative promotion boundary.

## Next Offline-Passed Candidate: V6.79 - 2026-08-30 21:20 +03:00

- Exact image SHA256:
  `6d9d831bdd38d42a9028f10e9851cc39f93ca10ebca9f78cc4b4489d9c104457`.
- V6.79 retains V6.78 and moves NPU RX consumer publication after descriptor
  refill. It publishes only successful refill credits using the rotating
  reserve cursor `(head + 1) % ndesc`, with `dma_wmb()` before the consumer
  write and no publication when refill returns zero.
- The exhaustive model checks 67,239,424 states and reduces old unprepared
  credits from 66,977,792 to zero. Strict checkpatch, current/inherited source
  contracts, clean compile, 29-unit Sparse, full image, exact FIT/rootfs, and
  full Ghidra gates pass. Exact markers include `PASS_V679_SOURCE_CONTRACT`,
  `PASS_V679_GHIDRA`, and `PASS_V679_CANDIDATE`.
- Size remains `20,632,380` bytes with `64,708` bytes FIT headroom. Kernel,
  DTB, rootfs shape, package set, connac, mt7996e, LuCI/configuration, services,
  and all NPU firmware are unchanged from V6.78. Only APK bookkeeping and
  `mt76.ko` differ.
- V6.79 is offline and unflashed. V6.70 remains live accepted. Promotion still
  requires separately authorized exact-image mode 0/mode 3, tri-radio/MLO,
  sustained RX/TX/RRO, memory, allocation-pressure, recovery, throughput,
  telemetry, and fatal-log gates.
- Full provider NPU and sustained-performance parity remain unresolved beyond
  this concrete RX descriptor ownership boundary.
- Report:
  `work\W1700K_V6.79_NPU_RX_REFILL_PUBLICATION_OFFLINE_CANDIDATE_20260830.md`.

## V6.79 Offline Bundle - 2026-08-30 21:24 +03:00

- Bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.79-NPU-RX-Refill-Publish-OFFLINE-UNFLASHED-20260830`.
- Direct image:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\w1700k-npu-rx-refill-publish-v6.79-20260830-OFFLINE-UNFLASHED-sysupgrade.itb`.
- Exact SHA256:
  `6d9d831bdd38d42a9028f10e9851cc39f93ca10ebca9f78cc4b4489d9c104457`.
- Both 82-record inventories replay with zero failures. No backup or retained
  credential-pattern match is present. `OFFLINE-UNFLASHED.txt` remains the
  authoritative promotion boundary.

## V6.79 Independent Replay Evidence - 2026-08-30 21:27 +03:00

- `work\verify_w1700k_v679_bundle.py` independently produced
  `work\build-v6.79-20260830\bundle-verification.json` with
  `PASS_V679_BUNDLE_REPLAY`, zero failures across 82 manifest and 82 SHA256
  records, 84 exact physical files, and matching direct/bundled/top-level image
  SHA256 `6d9d831bdd38d42a9028f10e9851cc39f93ca10ebca9f78cc4b4489d9c104457`.
- This evidence changes no promotion state: V6.70 is live accepted; V6.79 is
  offline and unflashed.

## Next Offline-Passed Candidate: V6.80 - 2026-08-30 22:04 +03:00

- Exact image SHA256:
  `000c1e1d1f7111141f33e65feaabf384eb4a9b54d517b589f9d12922659c0a4b`.
- V6.80 retains V6.79 and removes avoidable NPU RX scatter allocation/DMA-map
  churn. It linearizes the packet, then device-syncs and rearms the rotating
  reserve with the original DMA-backed fragment mappings. Allocation failure
  drops the packet but preserves those ring mappings.
- The 76,567,321-state model reduces 43,485,184 old release/reallocate
  fragments to zero with zero topology, publication, preparation, identity, or
  destination-overwrite failures. Strict checkpatch, current/inherited source
  contracts, clean compile, 29-unit Sparse, full image, exact FIT/rootfs, and
  full Ghidra gates pass. Exact markers include `PASS_V680_SOURCE_CONTRACT`,
  `PASS_V680_GHIDRA`, and `PASS_V680_CANDIDATE`.
- Size remains `20,632,380` bytes with `64,708` bytes FIT headroom. Kernel,
  DTB, rootfs shape, package set, LuCI/configuration, services, and all NPU
  firmware are unchanged from V6.79. Exactly APK bookkeeping and the three
  mt76-family modules differ due to the new shared diagnostics and logic.
- V6.80 is offline and unflashed. V6.70 remains live accepted. Promotion still
  requires separately authorized exact-image mode 0/mode 3, tri-radio/MLO,
  sustained scatter-heavy RX/TX/RRO, allocation-pressure, memory, throughput,
  telemetry, recovery, and fatal-log gates.
- Full provider NPU and sustained-performance parity remain unresolved beyond
  this concrete scatter-buffer lifecycle boundary.
- Report:
  `work\W1700K_V6.80_NPU_RX_SCATTER_REUSE_OFFLINE_CANDIDATE_20260830.md`.

## V6.80 Offline Bundle - 2026-08-30 22:07 +03:00

- Bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.80-NPU-RX-Scatter-Reuse-OFFLINE-UNFLASHED-20260830`.
- Direct image:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\w1700k-npu-rx-scatter-reuse-v6.80-20260830-OFFLINE-UNFLASHED-sysupgrade.itb`.
- Exact SHA256:
  `000c1e1d1f7111141f33e65feaabf384eb4a9b54d517b589f9d12922659c0a4b`.
- Both 84-record inventories replay with zero failures. No backup or retained
  credential-pattern match is present. `OFFLINE-UNFLASHED.txt` remains the
  authoritative promotion boundary.

## V6.80 Independent Replay Evidence - 2026-08-30 22:07 +03:00

- `work\verify_w1700k_v680_bundle.py` independently produced
  `work\build-v6.80-20260830\bundle-verification.json` with
  `PASS_V680_BUNDLE_REPLAY`, zero failures across 84 manifest and 84 SHA256
  records, 86 exact physical files, and matching direct/bundled/top-level image
  SHA256 `000c1e1d1f7111141f33e65feaabf384eb4a9b54d517b589f9d12922659c0a4b`.
- This evidence changes no promotion state: V6.70 is live accepted; V6.80 is
  offline and unflashed.

## Next Offline-Passed Candidate: V6.81 - 2026-08-30 23:00 +03:00

- Exact image SHA256:
  `ae23a15d7a1029127f5e2b4efcba829172cd067b2d293d39ab58c2703e68bb66`.
- V6.81 retains V6.80 and closes the stock Type-5 source ambiguity. Stock
  `hostadpt_rx_handler` returns descriptor qword 1 (`data:+0x08`), stock PCI
  projects it into local10/local8, and stock HWiFi consumes the projected hook
  and fate bytes. Descriptor `info:+0x04` is not the Type-5 source.
- The new patch is default-off and observe-only. It compile-time asserts the
  descriptor layout; snapshots first/second `data`; records scatter mismatch;
  reproduces the exact stock projector; and exposes per-ring raw/projected/
  decoded values under the existing packet-telemetry static key. It makes zero
  skb, skb-CB, descriptor, ownership, or dispatch mutations.
- The exhaustive-equivalence model covers all 4,294,967,296 32-bit source
  values. Fate 0 and 1 each cover 2,147,483,648 values; fate 2, fate 3, optional
  hook bit 25, projection mismatches, and mask violations are all zero.
- Strict checkpatch, 55 current and 69 inherited source checks, clean mt76
  build, 29-unit Sparse with zero diagnostics, full image build, exact FIT/
  rootfs verification, and aggregate static suite pass. Full Ghidra analysis
  covers six stock/rebuilt modules and 1,976 functions; all 45 Ghidra/ELF
  checks pass, including the static-key `ldr w30,[x1,#8]` path and exact
  projector instructions.
- Size is `20,636,476` bytes with `60,612` bytes FIT headroom. Kernel and DTB
  are byte-identical to V6.80. Rootfs shape remains 1,146 regular files; only
  APK bookkeeping and the three mt76-family modules differ. LuCI, services,
  configuration, packages, and all four NPU firmware blobs are unchanged.
- V6.81 is offline and unflashed. V6.70 remains live accepted. Promotion still
  requires separately authorized exact-image mode 0/mode 3, Type-5 telemetry,
  tri-radio/MLO, sustained scatter-heavy RX/TX/RRO, recovery, memory,
  throughput, and fatal-log gates.
- Report:
  `work\W1700K_V6.81_NPU_TYPE5_DATA_CONTRACT_OFFLINE_CANDIDATE_20260830.md`.

## V6.81 Offline Bundle - 2026-08-30 23:08 +03:00

- Bundle:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.81-NPU-Type5-Data-Contract-OFFLINE-UNFLASHED-20260830`.
- Direct image:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\w1700k-npu-type5-data-contract-v6.81-20260830-OFFLINE-UNFLASHED-sysupgrade.itb`.
- Exact SHA256:
  `ae23a15d7a1029127f5e2b4efcba829172cd067b2d293d39ab58c2703e68bb66`.
- The 119-record payload totals 36,776,732 bytes. Packager replay reports
  zero size/hash failures, zero retained credential-pattern matches, and no
  router backup. `OFFLINE-UNFLASHED.txt` remains authoritative.

## V6.81 Independent Replay Evidence - 2026-08-30 23:08 +03:00

- `work\verify_w1700k_v681_bundle.py` independently produced
  `work\build-v6.81-20260830\bundle-verification.json` with
  `PASS_V681_BUNDLE_REPLAY`, zero failures across 119 manifest and 119 SHA256
  records, 121 exact physical files, and matching direct/bundled/top-level
  image SHA256 `ae23a15d7a1029127f5e2b4efcba829172cd067b2d293d39ab58c2703e68bb66`.
- The tracker copies inside the immutable bundle are the pre-freeze snapshots;
  these two entries are the post-replay record. No router operation occurred,
  V6.70 remains live accepted, and V6.81 remains offline and unflashed.

## Current Patch 50/51 Lifecycle State - 2026-08-31 10:41 +03:00

- Canonical patch 50 SHA256:
  `68c2e5db2f4fb26c4a6a79086cf7e3f1f85a8e8ee21f31ebba81d9176e0049a3`.
- Canonical patch 51 SHA256:
  `deb14884d51b3ac7a8088f499d39b1ae471d98b682a2c222421509a91068c139`.
- Both `work/patches` mirrors are byte-identical. Patches 47-49 and 77-78
  were not edited.
- Address publication now reaches the real sleepable provider API under a
  mutex-pinned provider lifetime. Success proves `PUBLISHED`; any provider-
  entered error remains `UNKNOWN` and forces fail-closed ownership handling.
- Teardown parks TX before NPU revoke, disables/synchronizes IRQ and NAPI
  completion sources, drains work twice, and drains again after mac80211
  unregister before resource free.
- Stop polling is bounded. Partial MCU startup and normal remove must prove MCU
  shutdown before RRO/DMA free; failure leaves the MCU running bit and DMA graph
  quarantined.
- PPE binding is a synchronous borrowed-SKB transaction with exact results:
  `0=no-op`, `1=committed`, otherwise error. mt76 retains skb, mapping, and
  token ownership for every result.
- Zero-fuzz replay, 9/9 focused tests, strict checkpatch, 386-patch parsing,
  W=1, and 29-unit Sparse pass. No image/runtime promotion follows from these
  offline gates.
- Open boundaries: errno-only provider publication cannot distinguish
  pre-doorbell from post-doorbell failure; NPU idle has no exposed generation
  fence; module unload after quarantine is not proven safe; no live failure
  injection or mode-3 traffic test has run.
- Full report:
  `work\W1700K_PATCH50_51_NPU_LIFECYCLE_AUDIT_20260831.md`.

## Current V6.84 PPE Ownership Boundary - 2026-08-31 12:15 +03:00

- Patch51 is now
  `1d89d6698817ab1071a18b06fb4879f5e08b64bec58bff17574d516294ee08fc`,
  with an exact `work/patches` mirror. It decodes the target provider's raw
  `1/0/negative errno` binding result into a typed local outcome and rejects
  any unknown positive result as `-EPROTO`.
- This is deliberately an Airoha borrowed-SKB binding contract. The Ghidra
  stock PPE packet-fate handlers are not proven to be this callback and are not
  imported. mt76 retains packet, DMA, and token ownership for every outcome.
- Patch49 and target patches77/78 were not changed. No build/image/router or
  stock-binary mutation occurred. The Patch48 full-series replay boundary,
  hardware validation, and stock packet-fate parity remain open.
- Evidence:
  `work\analysis\mt76-npu-ppe-ownership-v684-20260831\REPORT.md`.

## Current mt76 Series Consistency State - 2026-08-31 12:30 +03:00

- The former Patch48/Patch34 full-series replay blocker is closed. All 132
  canonical mt76 patches apply from the pinned archive with `--fuzz=0`, with
  zero fuzzy applications or rejects, and all 386 scoped patches parse.
- Final repaired patch SHA256 values:
  - HIF2 provider unbind:
    `c6a72858eea46f678643b2ae277797d1bb9ae295b3ff2651254281b9ac5b48f9`.
  - WFDMA ring depth:
    `f86cc48679cfe6615c5672e2121b17bdabac4eaf7cec4c6cd221bc50bb62141e`.
  - default-off EPCS gate:
    `dcdd095a238154eefa5cb9c5bc49954f297260e445ffc4a674104b7c4665007a`.
  - transactional WiFi link lifecycle:
    `455f359882d8720916caca337d0bd5327ccdb71946d69ffe67519771b30a1838`.
- Strict checkpatch, focused lifecycle/rollback models, source contracts, and
  `package/kernel/mt76/compile V=s -j1` pass. The compiled mt76, connac, and
  mt7996e sources match the pinned replay fixture.
- This is static/build acceptance only. No image was built or promoted and no
  router state changed. Live WiFi/MLO, NPU ownership, recovery, memory, and
  throughput gates remain required.
- Authoritative report and evidence:
  `work\analysis\mt76-series-repair-v684-20260831\REPORT.md` and
  `work\tests\mt76-series-repair-v684-20260831\run-02`.

## Historical Offline-Certified Candidate: V6.84 - 2026-09-01 +03:00

- Canonical source HEAD is
  `d0d7ac45ccc39b0efc09f185e7baeea0daf822e2`; source fingerprint is
  `880fb06308c8bb953e509a042c83a4a1030c58004f9a1df50a3a8af71252a156`.
- Independent A5/B6 full builds have identical `89`-record target maps,
  identical `115`-record package-repository maps, identical rootfs/FIT output,
  and exact image SHA256
  `cdb5670a73ae21f92b3a59564adad713c6b932f30f251586ea1a4e08a8d7152d`.
  Image size is `20411196` bytes.
- Paired status is `CERTIFIED-OFFLINE-UNFLASHED` with zero errors and zero
  warnings. Final release seal SHA256 is
  `052ffaaa5da1dd311e63bcf5ff43955ff077ed916e68fd840b29e6be400933e9`.
- Published immutable release:
  `C:\Users\captain\Downloads\FW\MessingWstuff\FinalResult\W1700K-V6.84-Reproducible-Certified-OFFLINE-UNFLASHED-20260901`.
  Its normal `/mnt/c` replay passes and the bundle includes payload SHA256,
  manifest, certification, build/source receipts, FIT/DTB/rootfs metadata,
  and the ITB.
- Release report:
  `work\W1700K_V6.84_REPRODUCIBLE_RELEASE_REPORT_20260901.md`, SHA256
  `686bd38143f1b0bb4fd80094a1690fa63dfae0f337b628b1e12e53ed55b5ae39`.
  Detailed session log:
  `work\W1700K_STOCK_PORT_LOGGING_SESSION_20260901.md`.
- No router contact, command, upload, reboot, flash, configuration change,
  NAND/UBI write, bootloader write, or factory/calibration-data change
  occurred. V6.84 remains offline and unflashed. V6.70 remains the current
  live-accepted image.
- Hardware acceptance and full stock NPU parity remain open, including live
  tri-radio/MLO, mode-0/mode-3 ownership, sustained throughput/memory/recovery,
  dedicated stock host-adapter TX rings, global SKB/bufid lifetime, scatter
  ABI, doorbell/descriptor ownership, TXFREE/RRO lifetime, and final
  PPE/FastTX packet fate.

## Historical V6.84 Read-Only Preflash State - 2026-09-01 10:29 +03:00

- Ethernet `192.168.1.1` is positively identified as the W1700K running the
  live-accepted V6.70 boot ID `1d385777-bef3-4512-a557-ef2b1097d428`.
- The exact certified V6.84 ITB is staged only in `/tmp`; router-side size and
  SHA256 match the immutable release, and `sysupgrade -T` returns `0`.
- The current runtime is healthy. All three physical radios probe correctly,
  but every default AP interface is disabled, so no SSID or runtime wlan
  interface currently exists. This is configuration state, not evidence of a
  driver failure.
- COM3 was absent. No persistent router state, NAND/UBI, bootloader, or
  factory/calibration data changed. V6.84 was later quarantined and is not a
  flash candidate.
- Evidence:
  `work\W1700K_V6.84_PREFLASH_READONLY_GATE_20260901.md`, SHA256
  `cd735223a2f412bfd1757b0c6612007ef9c561921889edc6cfbd8607c915cb0d`.

## Current V6.85 Audit And NPU Design Boundary - 2026-09-01 14:07 +03:00

- V6.84 remains quarantined and unflashed. V6.70 remains the live-accepted
  router image.
- V6.85 engineering ITB SHA256
  `afef7f35ff18c050f441ec55d5637f7af11beaf7f0a517f263184c3399577a9d`
  passes the expanded r5 engineering smoke audit: 21 adversarial contract tests
  and 11 artifact gates. Neither r4 nor r5 proves build provenance or release
  fitness.
- Independent offline Build A is still compiling from source fingerprint
  `ae293dfec7e75c389a5385d39300d0a8eec5982445e285f38ed17e8d4118007c`.
  Build B, hardened certification, reproducibility comparison, and promotion
  remain pending.
- Stock Ghidra and upstream source analysis found no TXFREE generation,
  tombstone, hard reuse barrier, quarantine interval, or proven event drain.
  Raw 15-bit token reuse therefore remains ABA-ambiguous.
- `work/W1700K_NPU_TX_LEDGER_DRAIN_CERTIFICATE_ROADMAP_20260901.md` records
  Decision B for diagnostic-only research. Patches 52/79 remain
  `BLOCKED-DESIGN`; production NPU TX requires a later Decision A proof.
- No router or persistent flash state changed during this checkpoint.

## Current V6.85 Non-Promotion Boundary - 2026-09-01 14:56 +03:00

- V6.70 remains live and untouched. V6.84 remains quarantined. V6.85 remains
  an engineering artifact and is not a flash candidate.
- Authoritative engineering audit is
  `work/tests/v685-baseline-audit-20260901-r6-final`; its 46/46 contract suite,
  11 audit gates, 86-entry evidence manifest, and external local anchor pass.
  The ITB remains exactly `20415301` bytes with SHA256
  `afef7f35ff18c050f441ec55d5637f7af11beaf7f0a517f263184c3399577a9d`.
- Canonical-source configuration review found that the NPU options are paired
  Kbuild variables/macros rather than the documented tristates, the artificial
  provider-disabled mt7996 path is compile-broken, NPU doorbell errors are
  discarded, TXWI lifetime can end before descriptor-consumer evidence, and
  multiple teardown paths disable completion sources before stop/drain.
- Adversarial review invalidated the claim that the original 57-test executable
  model closed its first gate. Twelve concrete lifecycle, identity,
  certificate, and concurrency gaps are recorded in
  `work/analysis/npu-tx-ledger-model-adversarial-review-20260901/REPORT.md`.
  A corrected model is in progress. Patches 52/79 remain `BLOCKED-DESIGN`.
- Independent Build A remains healthy in `toolchain/gcc/final` and will finish
  only as reproducible baseline evidence. Build B, release certification,
  promotion, and flashing have not started.
- No router command, upload, reboot, flash, persistent configuration change,
  NAND/UBI write, bootloader write, or factory/calibration-data change occurred.

## Current-State Authority And Retractions - 2026-09-01 14:14 +03:00

- This checkpoint supersedes older sections labelled current, latest, or
  authoritative wherever their status conflicts with this checkpoint.
- V6.84 is quarantined, unflashed, and prohibited from flash or promotion.
- V6.85 engineering ITB SHA256 is
  `afef7f35ff18c050f441ec55d5637f7af11beaf7f0a517f263184c3399577a9d`.
  The r4 audit is smoke evidence only. Adversarial review also downgraded r5 to
  expanded engineering smoke evidence because it does not bind build
  provenance and under-validates FIT/package/radio-helper policy. Neither is
  release certification.
- Independent Build A and certifier hardening remain active. Build B,
  hardened certification, exact paired-build comparison, and promotion remain
  pending.
- Prior claims that TXFREE or its current token model was closed on paper are
  retracted. TXFREE carries only a generationless 15-bit token, so a stale
  completion after token reuse is ABA-ambiguous.
- Patches 52/79 remain `BLOCKED-DESIGN`.
- Upstream report SHA256:
  `078e223e5318eb5f07492a42a639019056987dac456174a82e19fd0ebae93669`.
- Stock report SHA256:
  `7690ba393204fec78c062dd7e7b7eff006ae7b89c725117f21d9c4442a3ff457`.
- Offline TX-ledger model `work/tests/npu-tx-ledger-model-v685-20260901`
  passes 57 tests, 340 deterministic event linearizations, and 22 provider
  certificate fault mutations identically on Windows and WSL. It enforces
  Decision B as default-off, diagnostic-only, and production-prohibited. This
  closes an executable design-model gate only; patches 52/79 remain blocked.
- No router or persistent flash state changed during this checkpoint.

## Latest Authority - 2026-09-01 14:56 +03:00

- The 14:56 non-promotion boundary and this footer supersede the older 14:14
  authority block wherever they conflict.
- The original 57-test model result is smoke evidence only; its gate-closure
  claim is retracted. Adversarial review report SHA256 is
  `c864ab9d9ba0d9149a0a247129bff2f5e3e65d40f20ffc66bed5833fcf05aed0`.
- V6.70 remains live-accepted and untouched. V6.84 remains quarantined. V6.85
  remains engineering-only and is prohibited from flash or promotion while
  the corrected model, source fixes, independent builds, and certification
  remain open.

## Stock RV32 TXFREE Boundary - 2026-09-01 15:20 +03:00

- Full Ghidra 12.1.2 analysis recovered and exported 305/305 RV32 functions.
  Ghidra and independent GNU disassembly agree on all six token-release and
  four token-allocation call sites. The required stock input hash matched.
- Stock RV32 strips completions to raw 15-bit token IDs and appends them to a
  16-bit FIFO. Normal release/allocation does not consult generation, epoch,
  descriptor/ring identity, retired state, or duplicate suppression. Duplicate
  completions can therefore enqueue and later allocate the same token twice.
- The stock stop handshake stops selected workers but leaves the TXFREE worker
  enabled and does not prove queue drain, producer/consumer equality, epoch
  transition, or residual partial-CIDX publication.
- Authoritative report:
  `work/analysis/stock-rv32-txfree-deep-20260901/REPORT.md`, SHA256
  `5f6a5009143388d9c7a611e60b5a094b79cbcdc274d6ec689ff6e03ee0cbbf6`.
  All package hashes and all 25 final validation checks were independently
  reverified.
- This resolves the hidden-firmware uncertainty but does not provide Decision
  A. Decision B remains default-off, diagnostic-only, and
  production-prohibited; patches 52/79 remain `BLOCKED-DESIGN` and V6.85
  remains prohibited from flash or promotion.
- No router, source, active build, NAND/UBI, bootloader, factory/calibration,
  or `FinalResult` state changed during this analysis.

## V6.86 Foundation And Active Build Boundary - 2026-09-01 15:47 +03:00

- The isolated V6.86 clone contains an uncommitted NPU configuration/fallback
  foundation: one condition now controls both host selectors and C defines,
  and a new 51a patch completes the fail-closed provider-disabled ring
  snapshot ABI. Local contracts pass 4/4; shipping-on and all-host-off builds
  both link three AArch64 modules through modpost.
- The all-off modules contain zero Airoha provider references. The shipping
  modules retain exactly the expected NPU/PPE references. The report is
  `work/tests/v686-npu-config-fallback-20260901/REPORT.md`, SHA256
  `fb73ce743827f47dc346840e5eb8515bc49a8dee104f98f53b2a22ee716343ce`.
- This foundation does not implement TX ledger, completion, reset, drain,
  teardown, or Decision A. Artificial host-on/provider-off remains blocked by
  provider-private field access. Patches 52/79 remain `BLOCKED-DESIGN`.
- Independent V6.85 Build A is in package compilation and has not produced a
  result or seal. Build B is prohibited until A is certified and the exact
  storage transition gate passes. The storage report SHA256 is
  `7f5243e74662ef2322f334c40ca230b33a1bbb9ea3d6f012b27472162913a242`.
- V6.70 remains live-accepted and untouched. V6.84 remains quarantined. V6.85
  remains engineering-only and prohibited from flash or promotion. No router,
  NAND/UBI, bootloader, factory/calibration, or FinalResult state changed.

## WiFi Audit Fail Boundary - 2026-09-01 15:58 +03:00

- The exact V6.85 source fails the full read-only WiFi audit with 13 findings:
  3 high, 5 medium, and 5 low. Report SHA256:
  `632465415036505877060a68e4c1c5c69fa9a6ab25c884e477640fab3e2f7b7e`.
- Release blockers are the asynchronous MLO apply/config-set race, static
  per-TID link pinning that prevents a bulk flow from using multiple links,
  and stale-device normalization that can pass undefined radio configuration
  into netifd before backend validation.
- Additional required fixes cover MLO default repair, puncturing parity, scan
  interface lifetime, shared-wiphy controls, active-link transition handling,
  client binding repair, live DFS/CSA reporting, recovery exception safety,
  bounded quarantine handling, and active-link choice in ancillary mac80211
  paths.
- Existing syntax and fixture tests pass and all 433 patches apply/inventory
  cleanly; passing compilation therefore does not clear these runtime defects.
  V6.85 remains prohibited from flash or promotion. V6.86 fixes are active
  only in the isolated corrective source. Router state remains untouched.

## Live V6.70 Mode 0 Synthetic Recheck - 2026-09-01 17:07 +03:00

- The Ethernet-bound target was re-identified before testing as Gemtek W1700K
  board `gemtek,w1700k-ubi`, kernel `6.18.34`, release
  `OpenWrt SNAPSHOT r0-5575e4a`, boot ID
  `1d385777-bef3-4512-a557-ef2b1097d428`. This is the frozen/live-accepted
  V6.70 image, not a V6.86 candidate.
- The corrected unattended matrix passed 37/37 in NPU mode 0: standalone
  2.4 GHz EHT40 request with standards-compliant 20 MHz coexistence fallback,
  5 GHz EHT80, 5 GHz EHT160 after successful 60-second CAC, 6 GHz EHT320,
  5+6 GHz MLO, tri-band MLO, member-radio scans with AP recovery, backend
  rejection cases, service health, fatal-log gate, and exact restoration.
- The first pass was 35/36 only because the old test required exact 40 MHz on
  2.4 GHz. The corrected `2437:20,40` contract reran the complete matrix with
  zero failures. Runner SHA256:
  `10d34e14e31d7f880239b3a7ca35a255da9876ea54328db608466958e0868fc3`.
- Final wireless configuration matched the original SHA256
  `588a3e98ee05a0d8649c392c54c4e879ac74230c1ed34a2134f07649e2aa945c`;
  no synthetic section, runtime interface, or watchdog remained. NPU lifecycle
  returned `inactive-clean`, mode remained 0, the boot ID did not change, and
  no flash, reboot, or NAND/UBI/bootloader/factory/calibration mutation
  occurred.
- Evidence:
  `work/router-tests/v670-mode0-recheck-pass-20260901-170743/REPORT.md`.
  Report SHA256:
  `b823c577bf068f24a6bc4bfce65515d7dde597a76e9323df6c13d8223d521417`.
  The 38-entry manifest verifies with zero mismatches; manifest SHA256:
  `54851e900387c1d1c7a788f327bd4497fb73cc456a327ce4d305afe56f2f03a9`.
- This result does not certify client association or throughput, modes 1-3,
  V6.86 changes, or a new flash candidate. Patches 52/79 remain
  `BLOCKED-DESIGN`.

## V6.86 Audit, Cleanup, And Build-A Boundary - 2026-09-01 17:57 +03:00

- The exhaustive patch-hygiene replay passes all 917 primary and 921 V6.86
  corrective patches with zero fuzz, rejects, residual failures, or invalid
  paths. It also records real hygiene debt: 68 mt76 patches depend on offsets,
  the legacy inventory omits 371 currently active paths, and the mt76 count is
  now 134 rather than the tracked 133. Report SHA256:
  `ea367c5267d6bec3ed7e0201e8d31ff7e645c2c235e01970cb76c4949765ccaa`.
- Release-certifier hardening passes 106/106 Windows checks with four expected
  skips and now binds immutable wrapper, staged candidate, source-state replay,
  and approval-anchor evidence. B-01/B-02/B-03 remain open, so this permits an
  engineering/provenance Build A only, not release promotion. Report SHA256:
  `98fd0ec0a87a532513fa60f2f1ec433f74cc72702ceaf00ab1ccc593fa4ab1b1`.
- V6.86 now normalizes legacy MLO TX policies 1/2 to upstream policy 0 in the
  helper and LuCI. The active patch likewise defaults to upstream scheduling;
  no custom per-TID pinning is presented as production behavior.
- Guarded cleanup removed 77 byte-identical ITB duplicates
  (`1,587,513,612` bytes), obvious command-output debris, and the exact
  redundant V6.84 A5 WSL build. A5 matched retained B6 at HEAD, config, 89
  target artifacts, and 115 package artifacts, had zero process references,
  and recovered `16,522,678,272` filesystem bytes. Stage 2 was deliberately
  not run because its broad classification includes certification evidence.
- V6.86 Build A began at `20260901T145753Z` in a cache-aware overlay after
  exact root/LuCI head, dirty-state, `git diff --check`, Bash, and ShellCheck
  gates passed. It is engineering/provenance work only; no candidate is
  flashable or promoted until build, FIT/package verification, and independent
  certification complete.
- V6.70 remains live-accepted and untouched. No router flash, reboot, NAND/UBI,
  bootloader, factory/calibration, or persistent configuration change occurred
  in this checkpoint.

## NPU Lifecycle Implementation Checkpoint - 2026-09-01 22:54 +03:00

- V6.87 is the current live validated engineering image. Its image SHA256 is
  `502745127cae575e6442ed373e12ae1047dde016d34c3fce98e76e7fd26e5c56`;
  the installed image passed the guarded 38/38 mode-0 WiFi matrix with exact
  configuration restoration. This does not certify stock NPU TX ownership.
- The R3 executable lifecycle model passes 83/83 on Windows and WSL across
  781 valid schedules and 60 provider-mutation cases. Independent QA-01
  through QA-11 all pass. This closes the model defects found in R2; it does
  not by itself certify kernel behavior.
- Kernel provider patch 79 v4 now supplies checked queue register, doorbell,
  IRQ, DMA-device, and drain-certificate APIs. Its patch SHA256 is
  `2a4a73221e3b0b6ab02c8d49c1c0024bef2a5d5f5e75008531582f3b38de11f9`;
  its provider object compiled successfully.
- mt76 mirror patch 51b and physical lifecycle patch 53a compile successfully.
  Patch 53a adds the default-off canonical transaction ledger, locked token
  helpers, deferred side-effect actions, and TXWI cache assertions. It does
  not activate a new runtime completion policy.
- Kernel patch 80 and mt76 mirror patch 51c add a checked provider-instance
  getter so transactions and later drain certificates can bind to an exact
  probe lifetime. Patch SHA256 values are
  `28370f322c77e34fcce6d3f631f886cc570eb9d575ec21b348026061e4892671`
  and
  `1dad1dd2cfa45e848c39fbf28482a5f39049db80e12c47fa7ae6e8621c4951e9`.
  Both pass strict checkpatch with zero errors, warnings, or checks. The
  provider object exports `airoha_npu_provider_instance_get`; the full mt76
  package build exits 0.
- Remaining implementation is physical patch 53b for checked queue
  read/kick/publication plus checked IRQ/DMA routing, 53c for explicit
  completion events and the canonical finalizer, and 53d for stop/drain
  certification and reclaim permits. Ambiguous doorbells must quarantine,
  never retry or roll back published ownership.
- No new image was built or flashed at this checkpoint. NAND/UBI, bootloader,
  factory/calibration, and persistent router configuration were untouched.

## NPU Checked-Publication Checkpoint - 2026-09-02 00:02 +03:00

- Physical mt76 patch 53b is now staged and compile-proven. Patch SHA256 is
  `662a321c95d7d11e9ef0989376dbb8edef0b7382325d723b3e7ab2c6c24a5e1c`;
  strict checkpatch reports zero errors, warnings, or checks across 826 lines.
- The patch routes provider identity, queue register access, doorbell commit,
  IRQ control, and DMA-device ownership through checked interfaces. Producer
  publication is serialized and readback-verified; ambiguous publication or
  provider loss quarantines the queue without retrying or rolling ownership
  back. First provider-failure metadata is immutable.
- A full `target/linux/clean`, `target/linux/prepare`, and
  `target/linux/compile` was required because the previously expanded kernel
  tree predated provider-instance patch 80. The regenerated kernel applied
  patches 79 and 80 and compiled the Airoha NPU objects successfully.
- The subsequent clean/prepare/compile of the OpenWrt mt76 package exited 0.
  Log SHA256 values are
  `1c4d380f557e4123957971576be89f08d67999b7341256d78ee93918ff805a90`,
  `bb9d8ec9331ae3fce8d549a0cc5d46592ef3c313fd506b4b45dc435c35a18222`,
  and `14557a0ec78e069385114e4250196c1cc10ecec117cae3b0540f09e8dcf38992`.
  Only baseline package and missing-module-description warnings remain.
- Rebuilt module SHA256 values are
  `2c20d200ce86d801977cc0bb8872d09203429dc041c92aa21dee229ba96c6b8c`
  (`mt76.ko`),
  `98401c2875a15743615d1050139141b00515117e1278e1482c08e71b39208508`
  (`mt76-connac-lib.ko`), and
  `83a2d61f01fd980b31422e01ce6754ff4c2ba36e91f459a224a1539c1bbf8b70`
  (`mt7996e.ko`). Symbol inspection confirms the checked queue/quarantine path
  and provider-instance/DMA ownership references.
- Patch 53b is not flashable by itself. Completion still follows the legacy
  path while the ledger is default-off. Patch 53c must install explicit
  consumer/TXFREE/stock-copy events and one canonical finalizer; 53d must add
  completion-source shutdown, identity-bound drain certification, permits,
  and exact reclaim.
- V6.87 remains the live engineering image. No image, upload, flash, reboot,
  NAND/UBI, bootloader, factory/calibration, or persistent router state changed
  in this checkpoint.

## NPU Canonical-Completion Checkpoint - 2026-09-02 00:29 +03:00

- Physical mt76 patch 53c is staged and compile-proven. Patch SHA256 is
  `f68f03b4a33764b55424311907ba5b35ba7c8385f73794529d90c07ba12724cc`;
  strict checkpatch reports zero errors, warnings, or checks across 919 lines.
- The patch replaces independent ring-consumer and TXFREE reclamation with
  explicit consumer, queue-detached, TXFREE, and stock-copy evidence. A single
  nonce-bound finalizer may claim ownership only after the queue slot is
  detached and either TXFREE or confirmed stock-copy evidence exists.
- Ledger-mode flush is now non-destructive, driver payload/SKB completion runs
  before exact token release, and TXWI cache insertion occurs only after the
  transaction is reset to idle. A permanent per-device token-history bitmap
  rejects generationless TXFREE after numeric token reuse; that conservative
  boundary keeps the ledger diagnostic-only and default-off.
- Clean mt76 prepare and compile completed successfully. Clean, prepare, and
  compile log SHA256 values are
  `89d65bf77f1ef62254d1c3eba582194c23cce135dedc60e2fec947a33d85d882`,
  `b652aabeaff0124321328181c7ef13579cb5ba54b7fedc4dc4a4f1e510aa54d8`,
  and `35c6796b8e18db6452d4d69573385ccbdb923028098ae87be7fdf898652d91b5`.
- Rebuilt module SHA256 values are
  `0b8f367635b75109214c7891a469a06ec0717a685eb5d38ef81dec6a4fef3348`
  (`mt76.ko`),
  `9fdab6965f62d3c168d118b384f34db7e18799599eb4826b3d4e8dd5fa361a50`
  (`mt76-connac-lib.ko`), and
  `a57346f6a9c5c154aa15b6ddfcc647a7d52b6ce09eff372b0cc885122434f607`
  (`mt7996e.ko`). Symbol inspection confirms all three mt7996 references bind
  to the exported mt76 completion implementation.
- Patch 53d remains mandatory: stop completion ingress, certify provider/ring
  drain against the bound provider instance, distinguish unpublished rollback
  from published reclaim, and consume bounded exact reclaim permits. No image
  was built or flashed; V6.87 and all persistent router state remain untouched.

## NPU Certified-Drain Checkpoint - 2026-09-02 01:12 +03:00

- Physical mt76 patch 53d1 is staged and compile-proven. Patch SHA256 is
  `adbc54155d1b0c2519e6391a49423cd750b735fa18a6ae6c1e1865e6a721f53d`;
  strict checkpatch reports zero errors, warnings, or checks across 969 lines.
- The patch adds serialized disruptive-operation authority, producer freeze,
  STOP/drain/source-disable state transitions, provider-instance-bound drain
  certificate validation, and exact certified reclaim. It validates every NPU
  queue before mutating any queue, so a late ring mismatch cannot leave a
  partially reclaimed device.
- The first clean compile exposed use of a container-driver cleanup wrapper
  with `struct mt76_dev *`. The implementation now invokes the checked
  `queue_ops->tx_cleanup` callback directly and rejects a missing callback;
  the subsequent clean prepare/compile exits 0.
- Final clean, prepare, and compile log SHA256 values are
  `e4c647d9f326f0ecbef38a1d23d78836c83d53291a00f75e09233c8734a3370d`,
  `c7803b3108e66e000cbf100365033e4b5b758b392c591f3aed179acb569cfe0d`,
  and `01733ed00d4acc018ec4e17541fb0d0566e8cbcbc93785142a6e6cbd9348cafc`.
  Rebuilt `mt76.ko`, `mt76-connac-lib.ko`, and `mt7996e.ko` hash to
  `2617da3dc32f6756f8420019b8d79120b4282ca96d3936868e2998aa9f7e56a8`,
  `b09cc0dc3429603dbe8f0d0ae0e00c290cd8477522bbf1266b8f8a9af0eae395`,
  and `86c9e7fbbe2a4fe5adb6b05b1985f37985c3d89300c94e879b09ca1e7c5494f1`.
- Patch 53d2 remains mandatory for typed one-shot permits and routing every
  reset, restart, teardown, shutdown, unregister, init-unwind, and coredump
  caller through the proven order. The generationless TXFREE boundary keeps
  the ledger diagnostic-only and default-off. No image was built or flashed;
  V6.87 and persistent router state remain untouched.

## Disk-Space Recovery Checkpoint - 2026-09-02 01:35 +03:00

- Removed `50.76 GiB` of exact-path data previously classified safe by the
  V6.86 cleanup audit: `49.19 GiB` from WSL build trees and `1.57 GiB` from
  generated Windows replay/test trees.
- WSL used space fell from about `97 GiB` to `48 GiB`; C: free space is now
  `43.77 GiB`. The detached `98.36 GiB` VHD did not compact without elevation,
  and the WSL unsafe sparse override was deliberately not used. Freed ext4
  blocks remain reusable by the active build.
- Active V6.88 build/source roots, V6.87 recovery artifacts, stock inputs,
  Ghidra projects, receipts, and trackers were preserved. Exact evidence is in
  `work/analysis/npu-53d-cleanup-20260902/CLEANUP-REPORT.md`.
- Two read-only audits also confirmed 53d1 has no real mt7996 callers yet and
  its certificate covers TX rings only. Typed one-shot leaf permits, RX/RRO
  ownership coverage, and complete caller routing remain mandatory before an
  image is built or flashed. Live router state remains untouched.

## NPU Completion Authorization Checkpoint - 2026-09-02 01:55 +03:00

- Patch 53d2a is compile-proven. It validates exact transaction, provider,
  operation, certificate, token, and resource authority before mt7996 unmaps
  payload DMA or completes the SKB. Patch SHA256 is
  `d6eba88f18304ced9f9b1f31a3486fa941c4b6c536ea9f96265655e93ed9da56`;
  strict checkpatch is 0/0/0 across 136 lines.
- Clean/prepare/compile log hashes are
  `043c0a0a51a0a69ecaae199d08a97c8501fbbad203eefedd060935583c81c351`,
  `09dce7a9bb32172917fc5cf063f9503ec0e562dcd442a4c13a39e4cdab0cb982`,
  and `68524a2ed6ecde95036a643303246be513ab969418641c0563cbe967898f370b`.
  Rebuilt module hashes are recorded in
  `work/analysis/npu-53d2-boundary-audit-20260902/REPORT.md`.
- This does not close certified reclaim: queue mutation is not yet an atomic
  all-ring batch, TXWI lifetime is not batch-pinned, and the provider live
  reference is not retained through operation completion. Those are 53d2b.
- Direct NPU RX certification is implementable using existing public RX ring
  fields, but the current provider sampler never populates them. RRO is a
  separate firmware-mailbox ownership domain with no current release
  certificate and remains excluded/quarantined.
- No image was built or flashed. V6.87 and persistent router state remain
  unchanged.

## NPU Batch-Reclaim Audit Checkpoint - 2026-09-02 02:52 +03:00

- The R4 lifecycle model passes `93/93` tests on Windows Python 3.14.5 and
  WSL Python 3.14.4. It covers 793 valid schedules and 60 certificate
  mutations with identical input hashes. This is design evidence, not live
  runtime certification.
- Patch 53d2b-v3, SHA256
  `546585b8d57e998ac175306524f26501711255fb612e6b4185aec4ba63f8d740`,
  passes strict checkpatch and a fresh mt76 clean/prepare/compile. The final
  compile log hashes to
  `9b570d4bed305b44f46739672b7e27452fa0270a820279741c7518d468fdc939`.
- Independent review rejects v3 as an integration candidate. Lifecycle
  init/deinit can reopen operations around provider removal, reinit can retain
  a poisoned completion-quarantine flag, and a violated post-detach release
  invariant is discarded instead of retained. Completion-source shutdown is
  still a declarative boolean, and all operation APIs still have zero real
  mt7996 callers.
- Direct RX0/RX1 destruction is outside the current TX-only certificate.
  Published RRO objects are a separate firmware-mailbox ownership domain and
  remain quarantined until explicit firmware forget/reset evidence exists.
- No image was built or flashed. V6.87 and all persistent router state remain
  unchanged.

## NPU Failure-Atomic Reclaim Checkpoint - 2026-09-02 03:25 +03:00

- Independent review rejected 53d2b-v4 after compilation. Retained TXWI
  orphans had no device-lifetime-safe owner, the release callback was not
  failure-atomic, live reinitialization could destructively unwind the old
  generation, and residual ownership checks did not cover the complete IDR,
  token counters, and NPU queues.
- 53d2b-v5 replaces post-detach failure handling with a side-effect-free
  validate-all phase followed by an explicitly infallible release commit. It
  rejects live reinit before provider mutation and requires zero token/WED
  counters, an empty IDR, and empty NPU TX queues before generation reuse.
- v5 SHA256 is
  `dadc610dac1c52dfe3b92562f3697f776581944fcaf83c142e94dd6072ed183a`.
  Strict checkpatch is 0/0/0 over 1059 lines; fresh clean/prepare/compile
  completed successfully. Rebuilt `mt76.ko`, `mt76-connac-lib.ko`, and
  `mt7996e.ko` hash to
  `dc10e19ceffa65f4c0c0fdfc3bc5c1cd1de2b55780706acb755ad2ca54b7f7f9`,
  `3adce35f9487d2903b38e0f35840818e32f81dc024decee0e0f05902fd75a16e`,
  and `38053e1605ca922e76da8e699c78b254f82072d216eaba9418d88b85ecebc29e`.
- At this checkpoint v5 was provisional pending independent re-review and R6;
  the later v7 checkpoint below records its rejection. Direct RX0/RX1 is still
  uncertified because provider sampling
  populates TX fields only; RRO remains a separate WM/WED/NPU mailbox
  publication domain. All operation APIs still need real caller routing and a
  typed completion-source permit.
- No image was built or flashed. V6.87, NAND/UBI, bootloader,
  factory/calibration data, and persistent router state remain untouched.

## NPU 53d2b-v7 Compiled Review Checkpoint - 2026-09-02 03:44 +03:00

- v5 is superseded and rejected: its first residual preflight still followed
  provider mailbox/reserved-memory programming and did not inspect every queue
  entry shadow plus descriptor `rsv`/`DONE`. v6 repaired those defects but
  cleared `init_in_progress` before its activation-failure reference unwind
  completed, allowing a successor claim to be erased by the old unwind.
- v7 holds the init claim across unpublish, RCU synchronization, lifecycle
  deinit, and DMA/PPE/NPU reference release, then clears it exactly once under
  `dev->mutex`. Patch SHA256 is
  `50e14f1ac8d4245d5e85388bcc038386ee9958cadaaa55b771794cd113225009`;
  strict checkpatch is 0/0/0 over 1157 lines.
- Fresh mt76 clean/prepare/compile exits 0. Rebuilt `mt76.ko`,
  `mt76-connac-lib.ko`, and `mt7996e.ko` hash to
  `fad8cf237a91c94382f63bd9c1a24d960026a89d7c58bdaee1a0635717b616ae`,
  `0947539c055e2d048c86928cf0df945b1e9d0bcbe93cac7bc121e5a97d98b34b`,
  and `12157e4e743e65035bb6eaf7dc843961901ac599a8234af1caed1967ecea04be`.
  Exact evidence is in `work/build-logs/npu-53d2b-v7-20260902/evidence.log`.
- Independent source review accepts v7 HEAD
  `fb5e80788fb946166fbd0316d11154752773783d` with no blocking finding. The
  final R6 executable model passes 115/115 tests and 844 schedules on both
  Windows and WSL. It tests successor attempts at all five unwind boundaries
  and includes a negative early-clear mutation that reproduces successor
  reference erasure and claim contamination. The evidence runner now rejects
  stale cross-host results and emits one dual-host manifest; final `REPORT.md`
  hashes to
  `cda8e5f7f742adbafa7407f034feaf82eab0aca8b7a1d3575707bf72bdacd997`.
- Complete stock/RV32 re-audit proves command `0x14` plus GET `0x33 == 0` is
  only an RRO STOP/quiescence fact. The honest certificate is
  `RRO_STOPPED_PRESERVE`: published RRO allocations remain pinned or
  quarantined. `RRO_RELEASED` requires a new firmware forget command or a
  proved NPU boot-epoch change.
- v7 is accepted as compiled infrastructure only. Typed completion-source
  leases, production coordinator callers, composite direct-RX certification,
  and the independent RRO publication ledger remain release gates.
- No image was built or flashed. V6.87, NAND/UBI, bootloader,
  factory/calibration data, and persistent router state remain untouched.

## NPU Cross-Audit Rejection Checkpoint - 2026-09-02 04:20 +03:00

- A broader source-to-model audit supersedes the prior broad v7 acceptance.
  The narrow activation-failure result remains valid: the init claim is held
  through all five tested unwind boundaries. V7 is nevertheless rejected as
  integrated infrastructure because administrative deinit does not serialize
  against an unpublished init, deinit can erase descriptor residue before a
  later preflight, physical completion ingress is not synchronized, and the
  mt7996 post-detach release validator is too weak to prove infallibility.
- The provider RX81 prototype is rejected. It makes the legacy TX certificate
  depend on both RX rings, closes a shared RX gate during TX certification,
  consumes one STOP/certificate domain for both TX and RX, and has no
  recoverable typed rearm. Direct RX needs a separate provider authority plus
  a one-shot mt76 page/descriptor inventory transaction.
- The isolated 53d2c typed-source draft is also not stageable. Its synchronous
  TXFREE/consumer/debugfs leases are useful, but the synthetic reorder path
  retains a TXFREE payload after releasing its lease, and no complete physical
  IRQ/NAPI/work synchronization precedes permit minting. Current raw diff
  SHA256 values are
  `3b463e216333c7df56a9eb335fd4378cd937af5177186476159db80d353c604d`
  for RX81 and
  `e021ac7d51828a68b9a5833a1b4c65b7374261a49c56259c8a14852eebc553f1`
  for 53d2c.
- Exact findings and the correction order are in
  `work/analysis/npu-v7-rx81-53d2c-cross-audit-20260902/REPORT.md`, SHA256
  `20c26b6325a88778baef3fd7dc6776403cc45efc1b1c91f188b055933d83e2b2`.
  No image was built or flashed; V6.87 and persistent router state remain
  untouched.

## NPU 53d2f and Official-Nightly Recovery Checkpoint - 2026-09-02 05:08 +03:00

- Power-loss recovery completed without losing the active WSL build, isolated
  source worktrees, model evidence, or official snapshot references. The
  interrupted mt76 package build reached exit code 0.
- Completion-Source Model R1 passes 82/82 tests on both Windows and WSL across
  72,072 schedules, including 12,012 held-reorder and 60,060 nested-cleanup
  schedules. It rejects 323,181 unsafe operations and kills all 23 mutations.
  The shared input manifest hashes to
  `f80cfe21457c32e6118d78d54a132f1bbb6b3eeff4291d597903961f01646acd`.
- Independent review accepts the corrected 53d2f typed release-completion
  component. It is committed as
  `c1e4f827ec57bba2252c6b20b0809f8819c6a27e`; the exported patch hashes to
  `099aa4d6fcb597b16837cbe030e96dd44d1fcda0e8dd7bdfb3cf62d7e589af2b`.
  Strict checkpatch and `git diff --check` are clean.
- Fresh mt76 compilation exits 0 with no C compiler error or patch-specific
  warning. The compile log hashes to
  `48f51dec0879fbace1a55f6284d588ff4ba918f79b091ede7c41067380abe588`;
  raw `mt76.ko`, `mt76-connac-lib.ko`, and `mt7996e.ko` hash to
  `740c4ad799b5b841b4863039d8acc8dc59ff9bae38e8c3f7fa4cbbcad27b7a0e`,
  `ed5becb0ed817d2994689293e177c1c0981709739a36907e89e51c80c47e05d5`,
  and `374c17b76c01025fea3e9ad0eef5a666f39d8a693f744ecb9144e6c4896e8058`.
- The active upstream reference is the actual official OpenWrt Airoha
  `an7581` snapshot `r36024-065a9b9abc`, with mt76 pin `be5ce7910521...`.
  The W1700K-specific fanboy source remains the build base; official nightly
  mt76/mac80211/hostapd changes are being compatibility-ported into isolated
  lanes rather than blindly rebased.
- Downloaded the actual 13,513,539-byte official ITB and verified profile hash
  `c4d12f458c641abc6f19842fdb34db7baf05128ec7e565016da0f02352dc694c`.
  Its FIT is `gemtek_w1700k-ubi` with Linux 6.18.44. It ships mt76
  `be5ce791`, Airoha NPU firmware `20260810-r1`, `wpad-basic-mbedtls`, and no
  LuCI, so it remains comparison evidence and is prohibited from replacing the
  custom `ubi2` release.
- The 67-commit mt76 delta audit identified three immediate functional fixes:
  WED-attach state commit (`2d6d69e`), failed-scan off-channel cleanup
  (`90f731f`), and per-peer MLO AQL accounting (`2c84469`). RRO event ABI,
  retained-link, connection-monitoring, ROC, TWT, ALTX, and remap-guard fixes
  are included in a validated 11-patch lane. Ordered apply, stable patch-ID,
  telemetry preservation, aggregate diff, and strict checkpatch gates pass.
  `SERIES.md` hashes to
  `ec3129fd8f7bacb591d67bb5404073fe6b824c6e280840bd1559aec841df9f02`.
  It is not yet integrated or compiled. The generic NAPI revert and
  mac80211-7.2-only changes remain excluded pending a coordinated stack upgrade.
- Independent review rejects the 53d2d coordinator WIP. It can mint a global
  quiescence fact while generic PCI/HIF2/WED IRQ, tasklet, TXFREE/RX/TX NAPI,
  and work sources remain live; it also clears a held reorder payload instead
  of retaining its completion obligation. Resume and teardown ordering have
  additional fail-closed functional defects. The exact ten-file recovery patch
  hashes to
  `ba45295c01cf08f42314fe96e9590dc7723b621623a31cfaa8f24c69e4f3abc4`;
  a new 53d2g lane is replacing the false global certificate.
- 53d2f remains component-only. Production caller routing, physical
  IRQ/NAPI/work/parser shutdown, direct-RX certification, and RRO boot-epoch
  authority are still mandatory. Exact evidence is in
  `work/analysis/npu-53d2f-nightly-recovery-20260902/REPORT.md`, SHA256
  `9f68123f164da4a9d99d690fac9946b2806f4153bf99ee0ecf4d67d9a2a1851c`.
  No image was built or flashed; V6.87 and all persistent router state remain
  untouched.

## Codex Session Cleanup Checkpoint - 2026-09-02 05:46 +03:00

- A disk audit found 123.5 GB of Codex session JSONL, mostly completed
  subagents that inherited this task's long history. Deleted only the 144
  completed subagent logs from 2026-08-31 and 2026-09-01, totaling
  89,381,826,621 bytes. C: free space rose from about 24 GiB to 105.27 GiB.
- Preserved the main W1700K session, all 41 sessions from 2026-09-02 including
  the four active agents, memories, plugins, source, Ghidra projects, build and
  router evidence, backups, release artifacts, and all three canonical
  trackers.
- The exact deleted-path manifest hashes to
  `15abd3ca7dcce134b765f17e47a632c3338ee08308f34c1f311340b9e8f1c3d3`.
  Cleanup report SHA256 is
  `1977cd7682926d6fada9cd779a808cd10c233f1cb8fa02ff726d38207a2ea32d`.
- An attempted archive was stopped when its compression ratio would have
  exhausted D:. The incomplete archive was deleted without deleting source
  sessions. WSL was then cleanly restarted and verified healthy. No firmware,
  image, router, NAND/UBI, bootloader, factory/calibration, or configuration
  state changed.

## V6.89 Upstream WiFi Compile Checkpoint - 2026-09-02 06:26 +03:00

- The selected 11-patch official mt76 lane passed independent semantic review
  with no P0/P1 finding. It addresses failed WED attach, failed scan/ROC
  cleanup, per-peer MLO AQL, RRO delete ABI, retained links, connection
  monitoring, ROC ownership, TWT, ALTX, and zero-address remap handling.
- The two TWT package patches were replaced with exact LF upstream
  `git format-patch` output after a fresh prepare exposed a CRLF-only mismatch.
  Their stable patch IDs remain unchanged. Fresh full-series prepare now exits
  0; log SHA256 is
  `7879582d6949c0b068e9d4d3206c0401d3a8582a5d61b513d37e597a1af132d3`.
- The W1700K MLO compatibility lane ports 14 justified upstream behaviors and
  passes strict ucode, shell, AArch64 C, hostapd/mac80211 patch, and backend
  adversarial validation. Its report SHA256 is
  `38375c87bab6cda935350f338dd68dbda4db10f20307a03fdf96a53f3236ce46`.
- Explicit mt76, mac80211, and full `wpad-mbedtls`/hostapd compile gates all
  exit 0 with zero hard errors. Their logs hash to
  `87d87e5e0fa0e6272749503a66c7f015f3e7f9bdeee28ea1769be54c6ec3be86`,
  `db1a3c0bd4ba405789376cb02dfd136aea9c396f55225542c0a1e5d3e2380a12`,
  and `4341f7bc97d85138226e628345cf6283128fcd80cdd7f2c13c7f1b81680ca499`.
  Raw `mt76.ko`, `mt76-connac-lib.ko`, and `mt7996e.ko` hash to
  `2d34e7c81345c4d66a1626619e2a3e261321f1734d35a75e3328236b18732a02`,
  `f688f5f0433586f5d00d0fcd92ca484ef425757ae377f5b486b09ed342858ec3`,
  and `5983c4a527e58623e306b3f73787aaabebfc0bf056a5e7d732674383dc3954d7`.
- The 53d2g NPU production coordinator remains isolated and unintegrated. Its
  prior line-ending rewrite is gone and `git diff --check` is clean, but source
  review, compile proof, direct-RX authority, and RRO release authority remain
  hard gates. No image was built or flashed; V6.87 and all persistent router
  state remain unchanged.
- A complete build-tree fixture run found and corrected two stale test
  assumptions: 2.4 GHz MLO now uses the enforced `EHT20` contract, and legacy
  MLO TX policies normalize to upstream policy 0. The coredump harness now sets
  its staged host-library path. All 19 reviewed source files match the durable
  build tree and all wireless/NPU/coredump/upgrade/syntax fixtures pass.
  Synthetic-test log SHA256 is
  `a788da2f65b304f433e64e5d793a8fb6ff9e5d1ab87b994ffba57eb5a602fe4d`.
- Detailed evidence is in
  `work/analysis/v689-upstream-wifi-build-gates-20260902/REPORT.md`, SHA256
  `0c269dbd9023dd316bee01475f9d131a556a59c9bd398d97c590e417e61d385a`.

## 53d2g Power-Loss Recovery Checkpoint - 2026-09-02 07:03 +03:00

- WSL2 recovered healthy with about 894 GiB free on its ext4 volume and no
  orphaned compiler or linker process. The WiFi package-build evidence and all
  three canonical trackers survived unchanged.
- The isolated 53d2g tree currently has a focused 13-file semantic diff and
  clean `git diff --check`. Strict Linux 6.18.34 `checkpatch.pl` reports zero
  errors, warnings, or checks across 2,494 changed lines. It remains
  uncommitted, unintegrated, and under independent review.
- Added the repeatable source gate at
  `work/tests/npu-53d2g-source-gate-20260902`. Its script SHA256 is
  `42191d749a529e1949cd76c3d1a7dfe1f0d20e66c053c3cc21ba9803db6140c2`;
  its manifest SHA256 is
  `24dcb4619bb572008ca57d97f81029498946844bf7c5a5b92d6275a4feab3d1c`.
- The current source fails four intentional release gates: nested cleanup does
  not require a TXFREE parent, call sites request cross-source nested
  CONSUMER authority, DEBUGFS is used as a nested parent, and production
  lifecycle events are still parked unsupported. Cross-source admissions can
  occur after a source was marked synchronized, invalidating the all-source
  quiescence certificate.
- Physical quiescence currently disables only `tx_worker`; `init_work`,
  `reset_work`, `dump_work`, `wed_rro.work`, `rc_work`, per-PHY `mac_work`, and
  `npu_rx_fault_work` still lack event-aware typed authority or cancellation
  proof. Direct-RX release authority and RRO boot-epoch release proof also
  remain manual P0 gates.
- No source was copied into the durable build tree, no image was built, and no
  router, firmware, NAND/UBI, bootloader, factory/calibration, or configuration
  state changed.

## 53d2g Review And Component-Build Checkpoint - 2026-09-02 07:42 +03:00

- This checkpoint supersedes the incomplete 07:03 source state. The three
  false nested-authority paths are fixed, and the isolated coordinator tree is
  clean at commit `d36bde51c56188326b80ab2d8209a2fe17fe35b3`, tree
  `104772e6ba02df8ee8f616f01c6d495e86f9823a`.
- The repeatable source gate now passes 55 checks and retains one intentional
  failure: production lifecycle events remain parked fail-closed. The corrected
  gate manifest SHA256 is
  `6b48211630f5d2c8730ba28623d138f542f739f8f61cbce85384cbf1d0922d23`;
  the raw result hashes to
  `d2e9c8bc0495fd96697691b2369a649bba785e977bc3af3dfee371456fb15374`.
- Two independent reviews accept compilation only. They reject production
  integration because work-source quiescence is incomplete, direct RX has no
  provider certificate plus exact host inventory, RRO has no exact graph plus
  forget/boot-epoch proof, destructive-action permits are not consumed by their
  leaves, IRQ-disable failure can be promoted to success, and terminal PCI
  lifetime is unproved. Permit replay, held-reorder retirement, two debugfs
  mutations, and staged thaw are additional P1 findings.
- Exact findings and implementation order are in
  `work/analysis/npu-53d2g-independent-review-20260902/REPORT.md`, SHA256
  `a509af3f320dd93454c6fb0485588808be354dfd04f50cafa73566204cadaae6`.
- A disposable AArch64/Linux 6.18.34 component build exposed and corrected two
  invalid conditional WED IRQ accesses and one missing DMA helper include.
  Commit `d36bde5` now compiles and links `mt76.ko`, `mt76-connac-lib.ko`, and
  `mt7996e.ko` with zero compiler errors. Source-only strict checkpatch is
  0/0/0 over 3,095 lines. Compile-log SHA256 is
  `01d105f630a70cafb502c3c73bd30b0ad9f3615ad25ce858c9ea0f68bb8b9959`.
- Current focused and recovery patches hash to
  `e33281f4044763e6272071312d47ac5280f3afbaa3ae859d066cb921c5b2762f`
  and `ab7dc35d3d43ea4bbd69cc54aaf640c38e694d51d37beafcec9ddbf58dee5ecd`.
  Reverse apply succeeds, and all seven recovery commits replay to the exact
  expected tree. Their manifest SHA256 is
  `ce161faa84ad03815d2d3c925fb8465d8e2af5c78a20b1969d106c7303097956`.
- This is still a non-production, fail-closed component. It has not been rebased
  into V6.89, built into a sysupgrade image, loaded on hardware, or flashed.
  V6.87 and all router persistent state remain unchanged.

## 53d2h Checked IRQ Certificate Checkpoint - 2026-09-02 07:52 +03:00

- Commit `cd485a5a63d073eb5be9c4d3d1155b4de7d944ac` closes the false-success
  provider-IRQ finding. The final provider disable pass now returns checked
  status, and `physical_sources_disabled` is recorded only after that status is
  successful and the IRQ handlers are synchronized.
- Strict checkpatch is 0/0/0 over 97 lines. The exact AArch64/Linux 6.18.34
  component recompiles with exit 0 and exports the checked helper. Build report
  SHA256 is
  `88c7efdc2ecc69c80c79f90be23b7195338fdfeed8eb003139f7b08d704bcd86`;
  evidence-manifest SHA256 is
  `8b157567987effb45f990d239e7535bf7615fcae0d88510185e01748de601ebc`.
- The source gate now permanently checks this ordering: 57 checks pass and the
  only failure remains deliberate production parking. Updated gate-manifest
  SHA256 is
  `c541b06d8702afe5648b8651d5695e682d9f0bfa1a6d78bf16fd56ed6009316d`.
- The focused patch and eight-commit recovery mbox reverse/replay cleanly;
  their manifest hashes to
  `cb1eac55fffbbb3954b792603a19715a780c9d5c806db31b58cb6ae3ea90f73d`.
- Work-source, direct-RX, RRO, destructive-action, thaw, and terminal-lifetime
  P0/P1 findings remain open. Nothing was integrated or flashed.

## 53d2i Debugfs Admission Checkpoint - 2026-09-02 08:06 +03:00

- Commit `274295235766d710e12a1c39b15e3faf0deb6d84`, tree
  `f380d3186a23d346ae0eda2f8355989073422695`, closes the P1 debugfs
  mutation bypass. TXFREE `reset-counters` and `clear-faults` now hold an
  exact typed DEBUGFS lease, recheck the shutdown barrier, and release the
  exact admission on every path.
- Strict checkpatch is 0/0/0 over 44 lines. The source gate now passes 58
  positive checks and retains one deliberate failure for parked production
  lifecycle events. Gate-manifest SHA256 is
  `ed6115414c737ef516d4f7c08b9a7e3e1e3e417ee1a204632aca2fcd5ccee56c`.
- The exact AArch64/Linux 6.18.34 component builds and links with exit 0.
  Report SHA256 is
  `1841a52b2fd80bf882e9e1adbd5d707448424acb9fd5515dbd5d5eca1cf96e53`;
  evidence-manifest SHA256 is
  `4f4be0d7352f20d1d5288b9b105b221475b3e3951c681debe1f2a0d0e1cce36b`.
- The focused patch and nine-commit recovery series hash to
  `6652e0b08432da62b4982a4761e9c4142c9db4869f32dc0b63b2a6dee1a4c0ac`
  and `adf44ff914a7b7e440e12e4a462f916e5daef04db6eadbc609a85e3521f7f381`.
  Replay from `fb5e807` reproduces the exact expected tree.
- Direct-RX/RRO authority, event-aware work quiescence, destructive-leaf
  consumption, staged reopen, and terminal PCI lifetime remain open. No V6.89
  integration, image, module load, router contact, or flash occurred.

## Direct-RX/RRO Authority Model R2 - 2026-09-02 08:11 +03:00

- Added the isolated executable model at
  `work/tests/npu-direct-rx-rro-authority-model-r2-20260902`. Its required
  production composition is:

  ```text
  DirectRxFree = Qsource AND ProviderRxReleaseCert AND immutable HostRxInventory
  RroFree      = Qsource AND ExactRroGraph AND
                 (GraphBoundForgetAck OR ProvedLaterNpuBootEpoch)
  ```

- Independent reruns pass 121/121 tests on both Windows and WSL, cover 29,400
  schedules, preserve all 4,200 unknown-epoch cases, reject 202,350 unsafe or
  out-of-order operations, and kill 38/38 weakened-contract mutations.
- Every authority is exact-object and binds provider instance/generation, gate
  generation, operation, action, serial, and nonce. Aggregate DMA/NPU actions
  require both direct-RX and RRO child completions for the same Qsource.
- Report SHA256 is
  `625ca4753d7f62728a54671701e5d86f7e6a5545c621633d1d7284b60230ce84`;
  the current independently regenerated manifest SHA256 is
  `590bc2701a1fd5c101b1403fb0dfbf871c67353ed98957cb1252d3ca7a43da17`.
- This closes the abstract-model gate only. Provider certificates, exact host
  inventory/graph construction, locking/memory ordering, event-aware source
  leases, terminal lifetime, C compilation, and hardware behavior remain open.

## 53d2j Staged Reopen Checkpoint - 2026-09-02 08:19 +03:00

- Commit `6b372d1d35bae8fa3171735dccaac382ea1af57c`, tree
  `4d052a49aa7ac52b9ec8300c09e9d0afc33c1195`, closes the P1 early-TX
  reopen ordering bug.
- Resume now restores consumers, reopens typed completion authority while TX
  remains frozen, restores physical completion producers, and only then
  commits TX publication/lifecycle admission.
- Strict checkpatch is 0/0/0 over 135 lines; 59 source checks pass and one
  deliberate production-parking failure remains. AArch64/Linux 6.18.34 build
  exits 0 and exports both staged-reopen symbols.
- Build report SHA256 is
  `d930fd442cb7457f27f37675b967f9d3520eef8f157a1d2c7fd01f11d6a29090`;
  build-manifest SHA256 is
  `f1c41a9df7a07d62fd52fd9f7d4418796fac949057bfad05c19cc85123c70e6b`.
  Ten-commit recovery replay reproduces the exact tree.

## Work And Terminal Authority Audit - 2026-09-02 08:19 +03:00

- The read-only audit pinned to `d36bde5` identifies four still-open P0
  classes: executable works survive failed parking, quarantine can outlive
  PCI/devres without software detach, direct work-to-coordinator calls make
  complete synchronous drain self-deadlock, and terminal tasklets are disabled
  but not killed.
- Its fifth P0, unchecked provider IRQ disable, is closed by `cd485a5`. Its
  early-publication P1 is closed by `6b372d1`.
- Still-open P1 classes are PCI AER admission closure, explicit bus-master
  unwind, provider-reference quarantine ownership, and terminal ownership for
  generic scan/ROC/reorder plus `wake_txqs_tasklet`.
- The smallest production direction is terminal-only first: publish events to
  one coordinator worker, close enqueue/execution admission, detach all
  software regardless of DMA reclaim outcome, and retain only certified DMA
  ownership in quarantine.
- Audit report SHA256 is
  `cc071b16f729b30f25bddc8f6ad40abae2a6e80d7f5fd4a674c28db5427fe8a2`;
  manifest SHA256 is
  `9fef3bce382d6332473bd945f40c82ee97e32f5190a0d568f2b3235f4902b99f`.
  No image or router state changed.

## 53d2k Replay-Safe Permit Checkpoint - 2026-09-02 09:05 +03:00

- Commit `52de75f8c7fcdd3b67055781722c485df548c96b`, tree
  `1c3113cf479bc19233ae92f3651e32f87cee5fd1`, closes the mutable-slot ABA
  replay and check-then-use destructive-action P0s.
- Permits are immutable by-value identities. A private gate atomically claims
  destructive action masks, makes failure terminal for that permit, and
  requires exact completed authority before reopen.
- Strict checkpatch is 0/0/0 over 877 lines. Corrected-source gates pass 14/14,
  the vulnerable parent is rejected, Windows and WSL pass 27/27 each, all 120
  replay schedules reject stale claims/completions, and 2/2 mutations are
  killed.
- AArch64/Linux 6.18.34 component build exits 0. Report SHA256 is
  `2463e39a4a2c1532d17fcf8a019d0e5cf547a206402ee2a7b381ce46606540f8`;
  evidence-manifest SHA256 is
  `cde20acaace0690102eada5fe54906c2d7efe4da8a2310bbd96abb7c58020d40`.
- Direct-RX/RRO authority, terminal work/PCI lifetime, and production event
  parking remain open. Nothing was integrated into V6.89 or flashed.

## Provider Patch82 Compile Checkpoint - 2026-09-02 09:05 +03:00

- Power recovery preserved the isolated patch82 branch and both intended
  modified files. WSL is healthy; Ghidra MCP did not survive the power loss, so
  headless Ghidra remains the analysis fallback.
- Patch82 keeps TX and RX certificates independent and adds value-bound RX
  identity/gate/STOP/certificate/release/rearm types. All NPU identity flags
  remain zero, so typed RX admission is deliberately `-EOPNOTSUPP` until stock
  firmware proves DMA-silent STOP semantics. It grants no RRO release.
- Fixed a Linux `current` macro collision found by the first real compiler
  pass. The exact source diff is now strict-checkpatch 0/0/0 and
  `git diff --check` clean.
- The staged Airoha provider object compiles for AArch64/Linux 6.18.34 with
  SHA256 `e1aa1ef4a1c1798ad31d1373ae56e13f066791d6ebd21877c87ebfa8a88d605f`.
  Source/header SHA256 values are
  `9f649982728ded5fe1e8b7397f6e17b50fee16d46ebd4513e31e4602c5eb1f08`
  and `7bfc65bd82f9a636f91d8ec089ae19c079ac8faf56cc6b6fa7725a51e32199ba`.
- This is a compile checkpoint, not production readiness. Independent R2,
  mutation/source-gate, stock STOP-proof, and official-nightly delta audits are
  still running. No commit, full image, router contact, or flash occurred.

## Patch83 And Exact RRO Authority Reference - 2026-09-02 11:28 +03:00

- The earlier patch82 review gates have completed. Stock selector-4 STOP plus
  selector-3 GET=0 proves only the observed command/idle result. It does not
  prove RX DMA silence, firmware-worker drain, descriptor stability, graph
  forget, or safe address reuse. Stock-proof report SHA256 is
  `e4213d8123499f067b11b8aefdf48c361f00d6fb9c5ca9b1a7106d131139cba6`;
  manifest SHA256 is
  `c59fc5aa8e9487b662136e1cafa436e2574741bd6658ad62457c8042433721cd`.
- The official-nightly provider comparison is pinned to OpenWrt snapshot
  `r36024-065a9b9abc`; a same-day refresh confirmed current snapshot
  `r36025-c1992346fc`. Five stable provider/PPE fixes remain mandatory before
  integration: correct `foe_check_time` allocation, PPE-deinit
  `synchronize_rcu`, metadata-dst `dst_release`, GRO `pskb_may_pull`, and
  rejection of flush-marked skb reaggregation. Report/manifest SHA256 values
  are `2f2f73ae57e0edb7f7371935e69c175fe20df66011303010e5d26be4f337bfa5`
  and `fd1259211efa3d468879a0f5fe6b81619dc7476d394248cfc459b9043fbd3373`.
- Patch83 is sealed only as a dormant capability-zero checkpoint: commit
  `b47ea29c011c91239c6da523879ed596434e7b09`, tree
  `42701255263f8216ed04088e71074d99f3e4e80b`. Provider/header/object SHA256
  values are `042ea1f0b2972ec1ae2c7a2eec39a2b17437f87db734d1a3d710ded4408e449c`,
  `467a2a03766736c7953c1a6b696a986cfa45c8c37d4b8f371cdb51cb22629351`,
  and `8e52002c404996c3f8eb49987afb1042e6c72a4da3c29999c45cb1509646c0fa`.
  Windows/WSL gates pass 30/30 and kill 43/43 mutations; strict checkpatch,
  AArch64 compile, and sparse pass. Build report/manifest SHA256 values are
  `56c999ca6cc37b3601faf557d1abd210fcdc6fefff9ad6532c2705ff7ce02a26`
  and `74274320ff0e8b7f64e328fca423fcc5dfe275128eff1db7449d222929aab4ff`.
- The final independent audit accepts those exact bytes only while all identity
  flags remain zero and no certificate authorizes destruction. Production is
  NO-SHIP/NO-FLASH: direct-RX/RRO child authority, clean-origin proof,
  cross-owner removal, stale-commit sequencing, event Qsource, and integrated
  mt7996 checked-IRQ compilation remain open. Audit report/manifest SHA256
  values are `ec1e48ad2af08f8c6d9d4ec2ecdf434d6b69806524e91edd00052810a0341816`
  and `c62ba91c0f6456c29f880e4322438455fcfc5acc60973bf11e626c28768a48eb`.
- The exact V6.89 RRO map covers all 524 prepared mt76 files and the matching
  Linux 6.18.34 tree. It identifies nine active/shared findings: unchecked BA
  host allocation, generationless delete records, page-owner timeout consume,
  dropped retirement allocation failure, discarded invalidation failure,
  ACK-SN misuse risk, host/effective descriptor identity confusion,
  non-transactional topology publication, and reusable identities without
  generations. Report/manifest SHA256 values are
  `41733525172be0c84482a4370d568ede1b8bb0ca1296a59c19b7d9d1511091fd`
  and `9859360e5300638f0b8f685f663b0d1d16ceabe71d126e2283513a675ca77f8d`.
- No full target/image build, module load, router contact, configuration change,
  reboot, or flash occurred. V6.87 remains the authoritative known-good image.

## Patch84 RRO Fail-Closed Checkpoint - 2026-09-02 13:15 +03:00

- The bounded R3/RRO model and source gate now pass independently on Windows
  and WSL: 11/11 tests, 10,092 schedules, 10,062 unsafe/out-of-order cases
  rejected, 2,282 invariant checks, zero unsafe releases, 9/9 behavioral
  mutations killed, 26/26 source checks, and 21/21 source mutations killed.
- Headless Ghidra stock analysis proved neither a generation/cookie authority
  nor a no-reuse-until-release/reset rule for scalar RRO session IDs. A
  successful stock mailbox operation proves only that the 1,024 address
  elements for that scalar SeID were invalidated; it does not prove that the
  encrypted WiFi MCU allocator has not reused or will not reuse the SeID.
  Stock report SHA256 is
  `63b0ea0427acf668d97a14d49bc2e7817694194a97dbdf8051f1ea8ea15df57f`.
- The isolated fail-closed source checkpoint is commit
  `af7b349c1981583c383038d3d1dedc58a45363e2`, parent
  `52de75f8c7fcdd3b67055781722c485df548c96b`, tree
  `46d3d1ca713f6d7e95c12bebef0e401f339036ce`; the checkout is clean.
  It prevents page-owner timeout fallthrough, treats ACK-SN only as progress,
  latches any possible NPU topology publication, and permanently quarantines
  every NPU-owned DELETE because no safe scalar-session retirement authority
  exists.
- Strict checkpatch is 0/0/0 over 514 lines. The authoritative AArch64/Linux
  6.18.34 cycle-5 component build exits 0; targeted sparse exits 0 with no
  touched-unit diagnostics. `mt7996e.ko`, `mt76.ko`, and
  `mt76-connac-lib.ko` SHA256 values are
  `46c6648bb3fdec52c59ec5fc5b1b4a00be52aea49d96909a6c9089eaf806372e`,
  `e9cecb1db2b2ab94ea07dbb8278e508ad3ba5732aa82e9e9a03af99ef2f98ab5`,
  and `e0a8d948729ce84a8b7421284dd7e02f145e155a3e3c88e5ae3b8bda65b1f7aa`.
- The stored 189,087-byte replay patch SHA256 is
  `8b20ac28fa032f10ddcb4a5f9fb21df889af23f4f0589c0e2b9789fd810a3de1`.
  An independent 189,473-byte `--full-index --binary` format-patch stream is
  deterministic with SHA256
  `64799b10b81c69760ba1e5a19bdc4aead8dd26c0d8d5d2905bcfc25aed611264`.
  Both replay the exact committed tree. Build report SHA256 is
  `3d9f418696301ef03fd2b0b0d0b283659878e16d1ecc9f370338153e509a1592`;
  post-commit identity report SHA256 is
  `d201f4db2474c6378d530843ab4900e6d859a5291725c707233d210f30aad129`.
- Independent audit verdict remains REJECT/NO-SHIP/NO-IMAGE/NO-FLASH. Its
  report SHA256 is
  `02c6200a7c936d57f9192aeef1473fd580c8894b1e8e1e7d9d7170f90cfaa130`.
  The immediate P0 is aggregate terminal lifetime: provider disappearance can
  still let init unwind dismantle tokens, DMA, queues, page pools, devres, and
  the containing device after local cleanup merely refuses to free. Embedded
  quarantine records can then outlive their owner and become UAFs.
- The five official OpenWrt stable/nightly-derived provider/PPE fixes and the
  independent BA rollback/checked-IRQ patches remain separately compiled and
  verified, not integrated. No image was assembled, no router path was used,
  and V6.87 remains the authoritative known-good image.

## Patch85 Terminal-Lifetime Recovery - 2026-09-04

- Patch85 cleanup-results commit
  `e55c841f46f6a35ddd335001f9fb7d0caec98ddb` remains rejected: its checked
  mt7996 helpers still reach the void `mt76_free_device()`, which can swallow
  NPU-deinit refusal after the caller has released its lifetime owner. The
  independent report SHA256 is
  `d491d7af54a2fa2218292a69ba1f26b181a3248ab34c1766a3e246de4efbb9dc`.
- Independent terminal-owner audit remains REJECT/DO-NOT-FLASH. It confirmed
  failed-probe devres teardown, returning `.remove()`, late module pinning,
  incomplete WED/NPU DMA-device capture, and a non-operative state protocol.
  Report SHA256 is
  `eff0067b18ea2d2b222d6ba057d1f846665eda24bd706d9f6b131fb17d3be46e`.
- The complete terminal source inventory identifies unclosed scan, ROC,
  reorder, TX-worker, IRQ, tasklet, NAPI, restore, WED-WO, AER, and framework
  paths. Its report SHA256 is
  `8a33c92c5d2db6a75e9c9c3dc3e248ec6032af1a0c15e18d9e4d10341c059b96`.
  The WED/WO preserve-DMA design report SHA256 is
  `47896c49f9c340b0799bf0f87a79c4a61756763e6264b2415e441cf5e8ed791b`.
- Headless-Ghidra stock analysis found no terminal release certificate,
  generation/no-reuse authority, or provider-loss reclamation authority.
  Fail-closed retention therefore remains mandatory; report SHA256 is
  `ad884373feec25b8740864c79e62408836171072579e2b45a526db1cdd497c06`.
- The active Patch85 terminal-owner lane is uncommitted and unsealed. It now
  retains role-specific primary, HIF2, WED, WED-HIF2, and NPU device
  identities; republishes provider references after failed init unwind;
  separates checked prepare from infallible device free; records actual bus
  IRQs; keeps terminal probe failures bound; suppresses manual bind/unbind;
  and makes terminal remove non-returning through reboot/panic containment.
  Strict checkpatch is 0/0/0 over 617 lines and the AArch64/Linux 6.18.34
  component build exits 0. Current module SHA256 values are
  `dd95214811dc57a28f18144afd50d6cf85f55dee74bf2b76de480611b4c0c4ed`,
  `06803349de5f762d0793164c5e3b3950e1f340af118ce848a9588cc932780885`,
  and `87057d16f490133fec9395139093317d68e193a046f3901f7acdb576f69154ab`.
- This is a build checkpoint only. Async terminal admission/drain, WED/WO
  preserve-DMA integration, AER handling, new mutation gates, sparse, and an
  independent re-audit remain open. No image was integrated or assembled, no
  router was contacted, and nothing was flashed.
- Official snapshot reconciliation is now pinned to `r36045-aa66786f38`,
  Linux `6.18.44`, and mt76 `be5ce791`. It adds four exact-applying hostapd
  MLO candidates but no new Airoha/mt76 delta; the five stable provider/PPE
  fixes remain mandatory. Report SHA256 is
  `82e24c2de4cdd052349fc0ea5b567f2c208be7e6335417ee43a1478ab028e662`.

## Patch85 Daybreak Terminal-Quiesce Checkpoint - 2026-09-04 07:22 +03:00

- The authoritative unsealed lane remains branch
  `w1700k-npu-patch85-full-terminal`, based on commit
  `eb9bb562bb54ad740e396072c84603dc36c5b000`. Its current checkpoint diff
  SHA256 is
  `49e0eb8b014208ab81081a6b27cc2d09b1b0ecce73ad5dde6ff99e8a838b7274`.
- The coordinator now closes terminal admission, stops queues, retires
  mac80211 callbacks separately from destructive mt76 cleanup, synchronizes
  persisted bus IRQs, frees their actions, drains tasklets/NAPI, stops RRO,
  sends and polls the provider STOP transaction, disables NPU completion
  sources, and quarantines on any unresolved NPU/RRO ownership. It also adds
  idempotent thermal/coredump retirement, terminal callback guards, exact
  delayed-work admission accounting, pending-session/RC-list retirement, and
  an AER `mmio_safe` gate so a dead PCI fabric is never touched.
- The generic packed terminal model passes 20/20 tests over 309 schedules and
  kills 100/100 mutations. Its report SHA256 is
  `5daa1aec6a6373e860c5043b24a5514b94aa48e5f4bc31d16eebbe0773f2b97e`.
  The remaining generic source-gate miss is 27 unguarded worker sites in
  unrelated mt76 drivers, not an accepted W1700K exception.
- Cross-driver BA verification passes all requested AArch64 `-Werror`, sparse,
  modpost, and disassembly checks; only six continuation-alignment edits remain
  cosmetic. Report SHA256 is
  `7a709db700696b5052f3059d039d6a19a7ec84ccff3a341e3330470cd1443272`.
- EN7581 hard reset authority is confirmed at `0x1fb00830`, mask `0x200`, for
  all eight RV32 cores, but it is not a DMA-release certificate because PCI,
  WFDMA, and RRO remain independent. Report SHA256 is
  `f983bcb0325ee97ef83a9d26183d3b068b7a1ebf9cd65ec94c86d278b0fab596`.
- A mac80211 package patch that kills `wake_txqs_tasklet` during
  `ieee80211_unregister_hw()` is staged and exact-tree dry-run clean; SHA256 is
  `a3fc6058f9033027ce81faf904926bd33f34c039377e62ec0181c194cbfc35ca`.
- The latest exact AArch64/Linux 6.18.34 component build exits 0. SHA256 values
  are `d2d29cdef5a1e6eae6b7afb30ebf723a7e55c15308f98789bd55b600b015d9c5`
  (`mt7996e.ko`),
  `0ef9a2cc2504b7249dfb71f2dcd99d463a6db1d527a3c0c86c89d0b98bf06c9b`
  (`mt76.ko`), and
  `62189e5df095153269cbfe214520c7147523145cd076c46eb49a3d25ed419190`
  (`mt76-connac-lib.ko`). Compile-log SHA256 is
  `8347a12d671b2d9559b1d519ce79687054517a4f53443dbff092d5c0ea9035ea`.
- One intermediate AER build correctly failed because `READ_ONCE()` addressed
  a bitfield; `mmio_safe` was converted to a standalone boolean and the failed
  object was rejected. The most recent pre-final strict checkpatch result is
  0 errors, 1 warning, and 18 checks; a fresh run after the AER edits remains
  mandatory, as do sparse and the NPU-disabled build.
- This remains NO-IMAGE/NO-FLASH. No full image was built, no module was loaded,
  and no router contact, configuration change, upload, reboot, or flash
  occurred. V6.87 remains the authoritative known-good image. Open P0 gates
  are WED-r2 provider integration, package integration of the mac80211 tasklet
  fix, callback/source and coordinator-model closure, compiled-module Ghidra
  audit, sparse/NPU-disabled builds, independent re-audit, and actual RX/RRO
  release authority.

## Patch85 Terminal Lifetime-Order Audit - 2026-09-04 08:03 +03:00

- Release gate is **FAIL / DO-NOT-BUILD / DO-NOT-FLASH**. The terminal gate
  suppresses `sta_state`, `remove_interface`, vif-link removal, and stop work
  before mac80211 synchronously destroys station/vif private storage. Embedded
  WCIDs and driver link publications can therefore outlive their owners.
- `mt76_cleanup_retired_device()` then walks WCIDs and can report/free TX SKBs
  after `ieee80211_unregister_hw()`. The exact backports unregister path also
  leaves `wake_txqs_tasklet` schedulable across RCU-unaware interface-list
  mutation; the previously staged one-shot kill is insufficient.
- There is no ordering-only repair for NPU-retained TXWI/SKB state. A new
  pre-unregister host-lifetime detach/scrub operation is required. It must
  remove retained SKBs from all status/WCID queues and erase mac80211 pointers
  while preserving only sanitized DMA ownership records. Full RX/RRO DMA
  reclamation remains impossible without provider release authority.
- Final audited state is baseline
  `eb9bb562bb54ad740e396072c84603dc36c5b000`, tree
  `25d208a66dc709018c12d4706c733fe12888eb90`, and uncommitted diff SHA256
  `f4c31e2acdb1c7addf3b13e23ea0f7cc3f800f258db88f18357ea91504b0f9bd`.
  A provenance transition during the read-only audit is recorded in
  `SOURCE_STATE.txt`; all final citations were revalidated against that state.
- Authoritative report:
  `work/analysis/patch85-terminal-lifetime-order-daybreak-20260904/REPORT.md`,
  SHA256
  `222ecfb0c852d122367894f6ec80a233cc6531b58b8e18f7e8cd254d97183d26`.
  No authoritative source, image, router state, or flash target was changed.

## Patch85 Daybreak P0 Lifecycle Repair Checkpoint - 2026-09-04 09:05 +03:00

- The resumed adversarial audit is NO-GO and found four P0 defects plus one
  P1 defect: RETIRE opened before existing ADD leases drained, scan/ROC work
  survived the first hardware barrier, most mac80211 hardware callbacks were
  outside the counted gate, MCU shutdown was sent after its WFDMA queues were
  destroyed, and terminal VIF cleanup could discard unresolved ownership.
  Evidence is in
  `work/analysis/patch85-current-terminal-adversarial-daybreak2-20260904/REPORT.md`.
- The unsealed source now has a five-state packed gate with a distinct
  `ADD_DRAIN` phase. RETIRE admission opens only after the prior ADD count is
  zero. Scan and ROC workers hold ADD for their whole invocation, terminal
  scan/ROC cancellation runs before IRQ/NAPI/WFDMA retirement, and MCU release
  runs while its transport and completions are still live.
- A first exact rebuild exposed a real `lockdep_is_held` modpost dependency in
  three direct runtime uses; those uses were removed in favor of structurally
  protected RCU dereferences. The corrected AArch64/Linux 6.18.34 build exits
  0. Current SHA256 values are
  `a1854f50bfbc777273dd0cfcf4185fd3b353dfeb26005328056b9f9d7bc887a0`
  (`mt7996e.ko`),
  `ab92c310e97d510525232e1fc51523eadc0533bd4583841b0508fad69436d9fe`
  (`mt76.ko`), and
  `9cf009563f0f278a1d10372d80c9aa05e4b11d6cdf4c7849656098ba0860e369`
  (`mt76-connac-lib.ko`).
- This remains NO-IMAGE/NO-FLASH. Callback coverage, VIF/WCID preflight,
  terminal-owner/AER lifetime, final Ghidra verification, C-level concurrency
  tests, and actual RX/RRO release certificates remain open. V6.87 remains the
  authoritative known-good image; no router was contacted or changed.

## Patch85 Daybreak Explicit-Lease, RX, and Ghidra Checkpoint - 2026-09-04 09:58 +03:00

- Nested lifecycle calls now inherit an explicit ADD or RETIRE lease class.
  Scan/ROC, vif-link removal, channel teardown, mt7996 callbacks, reset/dump,
  watchdog, reorder, TX-worker, and NPU-fault work are guarded for their full
  synchronous execution. This removes the prior nested reacquire path that
  could reject a valid pre-drain caller after the gate entered ADD_DRAIN.
- Direct NPU RX dequeue now clears the complete queue entry and descriptor as
  soon as ownership transfers or a slot is dropped/reused, closing the stale
  alias/double-recycle hazard. This is not an RX/RRO provider release
  certificate; those paths remain fail-closed.
- The exact AArch64/Linux 6.18.34 component build exits 0. Current SHA256 values
  are `a1c14904d951869c210e8edd4de1df02439e1221185cdb526c6493faa640bdaf`
  (`mt7996e.ko`),
  `03765191bcf27bfc7d5632f99942caa755d5edfbe3644c6c0345b9b5f00516b2`
  (`mt76.ko`), and
  `d17c82fcd7067efc310c56696347f97cf0e2c9c64c10ea3b71ce5025df11064f`
  (`mt76-connac-lib.ko`). Only pre-existing MODULE_DESCRIPTION warnings remain.
- The source-conformance model passes 326 assertions, all 40 mutants, and all
  10 modeled interleavings with zero deadlocks. Source fingerprint is
  `a44a44d516afcd3c4712f8b6598188870d2a5d8cac6ac1a9a201a2001f06f55e`.
- Ghidra 12.1.2 recovered and exported 1,040/1,040 stock functions across
  `hostadpt.ko`, `mtk_hwifi.ko`, `mtk_pci.ko`, `npu.ko`, and the RV32 firmware;
  1,383 evidence files are checksummed. Stock confirms useful topology and
  bounded-owner invariants, but contains unsafe RX scatter globals, premature
  token release, and time-bounded RRO unmap behavior that must not be cloned.
- Release remains **NO-GO / NO-IMAGE / NO-FLASH**. The current enum lease
  carries class but not stack-owner identity. The accepted next design uses a
  device-side slot table plus generation/nonce validation and atomic ADD-to-
  OWNER promotion. Completion-token propagation, provider callback lifetime,
  and RX/RRO release authority also remain open. No router was contacted or
  changed; V6.87 remains the authoritative known-good image.

## Patch85 Explicit Owner-Token Build Checkpoint - 2026-09-04 10:35 +03:00

- The aggregate terminal coordinator is replaced by device-bound, exact-address
  ADD/RETIRE tokens and a one-shot ADD-to-OWNER promotion. A dedicated
  reclaimable terminal workqueue prevents worker/self-cancel deadlock; joiners
  observe one published completion and owner/device/module lifetimes are held.
- Core fail-closed repairs add 30-second bounded drains with active-slot
  diagnostics, phase-coupled retirement authority, saturating gate cookies,
  failed-registration unpublication, and a prepared-free proof latch. A failed
  gate/NPU proof can no longer fall through to `ieee80211_free_hw()`.
- The exact AArch64/Linux 6.18.34 `-Werror` component build exits 0. SHA256 is
  `519799295412b7e46fb78229cbce691609dd1d97e7974eebc9a6bd284f1155e5`
  for `mt7996e.ko`,
  `14d0520d9e3c7e139421e4f0d6699f377abef55f7835444fb0f7b61f6e81ed0a`
  for `mt76.ko`, and
  `85f0741227a13b8d1d36fe181c93e50ed46efb53f10b7b039f37118b136ded42`
  for `mt76-connac-lib.ko`.
- Release remains **NO-GO / NO-IMAGE / NO-FLASH**. Independent drift review
  found eight missing official backports, including release-blocking TWT
  rejection cleanup. RX/RRO destructive release remains prohibited without a
  provider-backed silence/release certificate. Completion-source authority,
  provider detach ordering, formal token tests, and upstream rebases remain
  open. No router was contacted; V6.87 remains authoritative.

## Patch85 Generic Receipt/Free Transaction Model - 2026-09-04 11:20 +03:00

- A read-only generic `mt76.h`/`mac80211.c` design now specifies a device-bound,
  refcounted receipt and exact one-shot
  `READY -> CLAIMED -> PREPARED -> DESTROYING -> FREED` transaction. Driver
  graph-proof failure retains the exact owner token in absorbing
  `PARKED/BROKEN`; NPU deinit failure is absorbing and cannot be retried.
- The executable adversarial model explored 194,829 states and 414,536
  transitions with zero violations. Eight functional checks passed and all
  12 unsafe mutants were killed, including duplicate NPU deinit/free and token
  validation racing array destruction.
- The bound source hashes are
  `4cbe2cc1662ba64537dc36f4dbebf5ff7a5c585742de13a9047e52a6d8704802`
  (`mt76.h`) and
  `7827cb4b7687576d83efff902e89bf24cfd67ab09941ecf106f2a883766ebc76`
  (`mac80211.c`). Seven expected implementation gaps remain, so the model is a
  specification pass, not current-source conformance.
- Evidence is in
  `work/analysis/patch85-free-transaction-daybreak7-20260904/REPORT.md` with
  SHA256
  `e0e63a783e204ae1e173c666ca2d449aacb9262345501c16a9c385ca61272dba`.
  Kernel source, build state, image, and router were untouched. Release remains
  **NO-GO / NO-IMAGE / NO-FLASH**; V6.87 remains authoritative.

## Patch85 Power-Loss Resume And Ownership Re-audit - 2026-09-04 12:05 +03:00

- The post-power-loss authoritative working tree is intact and again passes the
  exact Linux 6.18.34 AArch64 `-Werror` component build. A direct RX repair now
  rolls back a consumed token/txwi when RRO page publication fails and refuses
  to recycle ambiguous ownership; the EMI completion refill path rejects a
  missing CPU-index pointer before dereference.
- Current module SHA256 values are
  `9bcd0e7bd546b8a289ed7e9be2ff6116ee2f070aed7d8c0d0e83340d0cd00082`
  (`mt76.ko`),
  `e0af076200e5ee9dc97c7299f71b8895a81aa74479ca5d72c11a7fa88c293ec9`
  (`mt76-connac-lib.ko`), and
  `0cf2a96bb7329a36f1c0cef81abca16a265cc93a5b82350c931c7fab1c78d3d1`
  (`mt7996e.ko`). Only the existing missing-`MODULE_DESCRIPTION()` modpost
  warnings remain.
- Independent current-source audits keep release closed. The mt7996
  coordinator still has an outer-timeout race, follower cleanup authority,
  split final publication, and rediscovered receipt ownership. The generic
  receipt path still exposes failures through a `void mt76_free_device()`
  wrapper, leaks a legacy receipt on ADD-drain timeout, accepts retry after
  invariant failures, allocates during teardown, and has unbounded NPU admin
  waits.
- The corrected completion P0 sidecar now compiles, but review found an omitted
  guarded TX-NAPI IRQ-rearm publication, so it is not merged. Typed NPU DMA
  exposure/device-link, coordinator, generic-free, and WiFi/nightly restoration
  candidates are being independently built and modeled before integration.
- Ghidra HTTP at `127.0.0.1:8089` did not return after the power loss; the
  supported Ghidra 12.1.2 headless path and all prior projects/evidence remain
  available. No image was assembled and no router was contacted or changed.
  Release remains **NO-GO / NO-IMAGE / NO-FLASH**; V6.87 remains authoritative.

## Patch85 Three-Way Isolated Integration Checkpoint - 2026-09-04 12:37 +03:00

- Corrected typed NPU DMA publication, preallocated terminal receipt/free, and
  split mt7996 terminal coordinator candidates were composed in the disposable
  `work/analysis/patch85-integration-daybreak11-20260904/mt76` tree. The
  authoritative source remains unchanged by this integration checkpoint.
- The exact OpenWrt Linux 6.18.34 AArch64 GCC 14.3.0 `-Werror` component build
  exits 0. SHA256 is
  `b59280b51282cea90bf1f4efe40edb13409068e5b5612de3b555ae18efd8322c`
  for `mt76.ko`,
  `ff8476c29880ec027d86f7590700959def5a406bf67cb2de093e2bcb9959ad2e`
  for `mt76-connac-lib.ko`, and
  `bee65335e591aa8a266c0f9b043846e7b4944ea6cc66a0018484504419c6bbf3`
  for `mt7996e.ko`.
- Publication checks pass 77 source assertions plus 15 modeled faults;
  receipt/free checks pass 32/32 legacy callsites, 71 modeled races, and all
  8 unsafe mutants; the coordinator model covers every join phase with zero
  outer timeout actions. The matching standalone Airoha device-link objects
  also compile with consumer-side autoremove semantics.
- Promotion remains **NO-GO / NO-IMAGE / NO-FLASH**. Independent adversarial
  coordinator review and completion fatal-close/physical IRQ masking are still
  active, WiFi restoration has not completed, and provider/runtime fault gates
  remain. No image was assembled and no router was contacted; V6.87 remains
  authoritative.

## Patch85 Four-Way Lifecycle Integration Checkpoint - 2026-09-04 13:16 +03:00

- Hostile review found and corrected three coordinator defects: queue-rejection
  deadlock, normal module-unload pin failure, and transient failed-probe
  success. Completion hardening closes guarded TX-NAPI rearm, provider RCU,
  nested-token false success, WED shadow-only masking, and same-lock fatal
  publication gaps.
- Corrected publication, preallocated receipt/free, corrected coordinator, and
  completion fatal-close now coexist in the isolated Daybreak13 tree. The full
  verification matrix passes: publication 77+15, receipt/free 32+71+8,
  coordinator phase and hostile models, completion 48,048+7+8, and 51/51
  completion source-contract assertions.
- Two path-normalized exact Linux 6.18.34 AArch64 GCC 14.3.0 `-Werror` builds
  produced byte-identical full modules. SHA256 is
  `5495536c6356b997048a09ef90fa3ffcf97b059151954d2e1b16e2ec5bec7a48`
  for `mt76.ko`,
  `9a62e4ef99c83088b2c0f9e9178edcfc8b0ebfbd2d7c465037fd2b93ef7966ef`
  for `mt76-connac-lib.ko`, and
  `46889a65ed69914a684af2d7183220744c305d3773e3fd280aabd6d868a18348`
  for `mt7996e.ko`.
- WiFi restoration separately passes eight mt76, four hostapd, MLO validator,
  and exact component/package builds. MLD MAC selection, per-radio status, and
  iwinfo wrapper ownership are under follow-up review.
- Evidence is rooted at
  `work/analysis/patch85-integration-daybreak13-20260904/REPORT.md`, SHA256
  `a3126902cd0763adead5bf9a543b11c96625c87e2411eaafcbae26e0c91384a1`.
  The authoritative source, exact V6.89 build, images, and router remain
  unchanged. Reset/RESTORE, refill debt, independent composition/Ghidra review,
  full-image, and runtime gates keep release **NO-GO / NO-IMAGE / NO-FLASH**;
  V6.87 remains authoritative.

## Patch85 Ghidra And Stock-Parity Checkpoint - 2026-09-04 13:41 +03:00

- Ghidra 12.1.2 fully auto-analyzed the three reproducible Daybreak13 modules
  and focused decompilation covered terminal ownership, queue dispatch,
  physical fatal close, NPU IRQ/refill, provider lifetime, probe, remove, and
  prepared-free paths. Optimized source-local helpers were traced through their
  compiled parent functions rather than treated as missing code.
- The compiled mt7996 object contains both hostile-review coordinator fixes:
  REMOVE can proceed under module-core unload lifetime, and failed
  `queue_work()` signals synthetic work completion before retained-state
  publication. Physical Airoha/WFDMA/dual-HIF fatal masking and guarded
  TX/RX completion publication are also present in machine code.
- Binary/source comparison exposed one remaining P0 boundary: RX page-pool
  allocation can leave a ring underfilled while `completion_refill_needed`
  records only publication failure. Isolated refill-debt/fatal-closure work is
  active; Daybreak13 is not promoted.
- Independent stock Ghidra review resolved and decompiled 54/54 focused targets
  across 1,233 functions. It confirms dedicated two-group TX rings and
  descriptor/SKB/DMA contracts, but also confirms that stock returns the WiFi
  token before host-adapter handoff, implements no RV32 selector 7, and has no
  safe generation-bound reset/RRO release or provider-detach certificate.
  Exact unsafe stock unload/restart behavior remains intentionally non-portable.
- Daybreak13 source identity remains
  `8076dba64f181e7092659ce8064ec7a910aa14ed9d18d35480755fdbf9a36d42`.
  The expanded 77-file evidence list and 78-file manifest verify with zero
  mismatches. `GHIDRA_REVIEW.md` SHA256 is
  `fdbb2d63fd1e401caf5cb1015b8b01d4b566e0be0b7615805f5ebf7c5ed42c05`;
  the independent stock report SHA256 is
  `afb5cac349996b04feaec0f39a2c91324a47860ea82d52dae72c78208617cbff`.
  No image or router action occurred. Release remains
  **NO-GO / NO-IMAGE / NO-FLASH**; V6.87 remains authoritative.

## Patch85 Reset And Upstream-Drift Checkpoint - 2026-09-04 14:01 +03:00

- Reset/restore finalization passes 125/125 source assertions, rejects all 256
  hostile partial-reset combinations, and produces byte-identical exact
  AArch64 `-Werror` modules. Active-NPU reset intentionally returns
  `-EOPNOTSUPP` before physical writes because no provider restart receipt,
  boot epoch, or complete buffer-reconstruction contract exists. Evidence:
  `work/analysis/patch85-reset-restore-finalization-daybreak13-20260904`, patch
  SHA256 `75d068f59f352ac796e9880a473ccefd08208b66d416c4850efde13771429277`.
- The exact V6.89 build uses mt76
  `b2704cf5a4068b672bf47ad5bf6b4802b6770a90` and mac80211/backports
  `6.18.26`; current official OpenWrt HEAD
  `28ba2708f1f609bfd134975808b2bc6ed9dc9742` selects mt76
  `be5ce7910521492d4a2e4ce7ee3843680a46c047` and backports `7.2`.
- Daybreak13 had nine compatible official mt76 corrections present only in
  reference `.orig` files. They are restored in the isolated
  `work/analysis/patch85-upstream-nightly-refresh-daybreak14-20260904` tree:
  MLO link reprogramming, connection monitoring, peer-wide non-AQL accounting,
  successful-WED-attach ownership, MLD iTWT rejection, register-zero sentinel,
  ALTX/disassociation handling, failed-TWT cleanup, and the mt7996 LED flag.
  Source contracts pass 20/20 and the exact Linux 6.18.34 AArch64 `-Werror`
  build passes. Module SHA256 values are `394bf0f398744034156b0ed759ef90da2cb4c562eb592e1e4551c3b432f9aac5`,
  `eb35c91429fafa120965417d94c800bb5233961c6945605906cfd82b82027864`,
  and `704b91a89d30a2b5ee314b93f95e4794b42b47c51fa5481047d65f314ef32532`.
- Backports-7.2-only action/FILS changes remain deferred pending the active
  compatibility audit. Completion integration, refill/fatal closure, and WiFi
  gap reviews are also active. The C: volume has about 5.3 GiB free, so no
  redundant builds or unsafe cleanup are permitted while agent builds run.
  Authoritative source, exact build, V6.87 fallback, images, and router remain
  untouched. Release remains **NO-GO / NO-IMAGE / NO-FLASH**.

## Patch85 WiFi Gap-Closure Checkpoint - 2026-09-04 14:09 +03:00

- The isolated WiFi gap lane closes three source/package gaps: hostapd now
  anchors an MLD MAC to the first participating radio instead of hardcoded
  radio 0; LuCI reports radio-local channel/frequency/bitrate facts while
  showing aggregate MLD state once; and `wifi-scripts` owns the ucode
  `/usr/bin/iwinfo` scan wrapper when the native `iwinfo` package intentionally
  installs none.
- Hostapd, `wpad-mbedtls`, `wifi-scripts`, `luci-mod-network`, and
  `luci-mod-status` exact component builds pass. MLD-order, malformed-array,
  radio-fact, reversed-order, null/fallback, scan-wrapper ownership, package
  payload, syntax, and existing radio/MLO fixtures pass. The evidence manifest
  verifies with zero SHA256 mismatches.
- Evidence:
  `work/analysis/patch85-wifi-gap-closure-daybreak12-20260904/REPORT.md`, SHA256
  `ced46cdf1e211980eac4784ed5e6904ad9bccacd3fba8e803a35a07619a4e418`.
  Patch SHA256 values are `5e14bb46903a0068c3a953ad265826e8fd6983fb4d2beec01459d8c2e251ab5c`,
  `5719cfdc7668a8ee46ee6895f3b2132e85971d715643b186ab42fe000f350400`,
  and `bad9ddb20497bee0a4711ecc859e8855a958a2763cb9be23b91f389f6dfaa432`.
- This is source/package proof, not runtime certification. Real scan/join,
  first-attempt and repeated MLD association, live LuCI ubus polling, memory,
  throughput, regulatory behavior, and full W1700K `ubi2` FIT/DTB identity
  remain open. An independent adversarial review is active. No authoritative
  source, image, router, or V6.87 state changed; release remains
  **NO-GO / NO-IMAGE / NO-FLASH**.

## Patch85 RX Refill/Fatal-Debt Checkpoint - 2026-09-04 14:22 +03:00

- The isolated refill closure fixes seven proven Daybreak13 defects across
  `dma.c`, `npu.c`, and `mt7996/init.c`: partial physical/NPU fills cannot be
  published, scatter-reuse publication debt is durable, physical refill stops
  after fatal closure, debt blocks IRQ/NAPI rearm, NPU initial fill requires
  exact depth, and terminal graph accounting includes outstanding refill debt.
- The hostile model reports 1,079/1,200 baseline schedule failures and zero in
  the correction; 45/45 source contracts pass and 22/22 mutants are killed.
  Two exact Linux 6.18.34 AArch64 `-Werror` builds are byte-identical. Module
  SHA256 values are `8bb5c65a3e8a8ec8cf002e2a4a4de53c35fef3fdf47fc6bfb5e2714f114a2286`,
  `9a62e4ef99c83088b2c0f9e9178edcfc8b0ebfbd2d7c465037fd2b93ef7966ef`,
  and `a963819b023d953e4e3758e46f5ccd84e3e6e63aadd26b54fee01e3e10e458b6`.
- The portable patch applies cleanly to both Daybreak13 and the
  nightly-restored Daybreak14 tree. Report SHA256 is
  `c680f8f9a7f72c82e8ca0602890515cd2d8d8095e867b200d8121e68fa00a1f1`;
  patch SHA256 is
  `f99af95e52811bd1bacaac12f061d34cd68a5fc50ed9b6cfcf988ac025497d9c`.
  This is GO for controlled composition only. Completion/reset interaction,
  full image, Ghidra final-binary, and hardware gates remain open; no
  authoritative source, image, router, or V6.87 state changed and release
  remains **NO-GO / NO-IMAGE / NO-FLASH**.

## Patch85 Daybreak15 Semantic-Composition Checkpoint - 2026-09-04 14:41 +03:00

- Built an isolated composition from the nightly-restored Daybreak14 mt76
  tree in `work/analysis/patch85-integration-daybreak15-20260904/mt76`.
  Applied the completion P0 correction, then semantically rebased reset and
  refill/fatal-debt changes instead of mechanically stacking their conflicting
  `npu.c` hunks. The NPU refill path uses the already-owned
  `mt76_npu_completion_publish_execute_locked()` boundary, retains exact-depth
  refill/debt accounting, and blocks debt-bearing IRQ/NAPI rearm.
- Composed static gates pass: nightly 20/20; completion 57/57; refill 45/45
  with 12/12 source mutants; refill hostile model 0/1,200 corrected failures
  versus 1,079 baseline failures; reset 127/127; reset hostile model all 256
  capability combinations with every partial set blocked before physical
  mutation; completion hostile model all 168 cases.
- The reset and completion integration harnesses were rebased only where
  composition intentionally changed representation: named-struct epoch checks,
  the ownership-lock/inner-gate callback hierarchy, locked versus public
  publication call counts, and refill's stronger durable-debt expression.
  The underlying invariants remain asserted, not skipped.
- The mac80211 compatibility lane produced paired per-link discovery-template
  helper patches for the 6.18.26 backport and mt7996 consumer; both exact
  component builds pass. They are staged candidates pending runtime MLO proof.
  The unrelated 7.2 action-layout change remains deferred because its isolated
  mt76 consumer does not compile against 6.18.26.
- No exact Daybreak15 cross-build, final-binary Ghidra run, full image, or
  router test has occurred yet. Active-NPU reset remains correctly blocked by
  absent provider restart receipt/boot epoch and complete reconstruction
  authority. Authoritative source, V6.87, images, and router are untouched;
  release remains **NO-GO / NO-IMAGE / NO-FLASH**.

## Patch85 Daybreak15 Binary/Ghidra Checkpoint - 2026-09-04 15:04 +03:00

- Two exact Linux 6.18.34 AArch64 `-Werror` builds of the composed candidate
  are byte-identical. SHA256 values are
  `415070c2bfd04ac71a35ba5800c5d932701b08e7d1e94d0e500e7830479464e7`
  (`mt76.ko`),
  `eb13a0e46c6c977106c89461d54b6cbb63d6d88b09f14ee8b7d1bb3fca7d3d4f`
  (`mt76-connac-lib.ko`), and
  `3b9010960bcfd33b5f8b88b81303cabf0eefe086733b6df01fd0fee60c2f4636`
  (`mt7996e.ko`).
- Full Ghidra 12.1.2 auto-analysis recovered 849, 240, and 1,169 functions.
  All 31 requested decompilations completed; the only absent named helpers are
  two expected compiler-inlined refill helpers. The machine verifier passes
  29/29 checks for exact artifact hashes, call topology, exact-depth refill,
  fail-closed publication, IRQ/fatal masking, restore ordering, and reset
  refusal before physical DMA mutation. Report SHA256 is
  `b8319f794bdee766566c4ebd3aa0e9783baca9a40ded506416945802ed33a7f2`.
- The normalized eight-file portable patch applies to the restored nightly
  baseline and reproduces the composed normalized sources byte-for-byte.
  Patch SHA256 is
  `9b0e22b828095b7da7d09b04dcfc797239792109ea84c8d7689c5f0830b15389`.
  Strict checkpatch has zero errors but still reports 14 memory-order-comment
  warnings and 59 formatting checks; a semantics-preserving cleanup review is
  active before promotion.
- Independent WiFi review found and corrected a cross-anchor MLD MAC collision,
  wrong LuCI MLO-owner retention, aggregate channel/frequency ambiguity, and
  unsafe optional-value normalization in an isolated sidecar. Corrective patch
  SHA256 is
  `7b02833309d2144ce914319b7fc5923caf8bfbfa0e9ba06f2b9ec275fdb9f423`.
  Exact parser/fixture/replay gates pass, but live browser, scan, association,
  and reload lifetimes remain unverified.
- Independent lifecycle composition and all-series semantic reviews remain
  active. No authoritative source, image, router, reboot, upload, or flash
  changed. Release remains **NO-GO / NO-IMAGE / NO-FLASH**.

## Patch85 Daybreak18 Correction/Audit Checkpoint - 2026-09-04 16:48 +03:00

- The close/refill race is corrected in isolation: an OPEN-admitted root lease
  may complete only matching RX-refill/IRQ-rearm publication during CLOSING;
  new root admission, DMA publication, stale identities, fatal, and quarantine
  states remain blocked. All 146 candidate schedules pass versus 42 baseline
  debt schedules; the final-mask mutant exposes 36 unsafe schedules. Patch
  SHA256 is `1bd8fac54e421770570103535ae9c5d465df51824ea3cdc77b2af674e1e96e37`.
- The P2/P3 lifecycle sidecar bounds fatal-mask callbacks to two failed
  attempts and one successful mask, removes duplicate caller closure, restores
  gate/NAPI/replay/tasklet/producers/TX in order, and propagates debug-recycle
  release failure before mutation. Its 847 schedules, 22 source checks, 11
  Ghidra checks, two reproducible builds, and 1,192 hashes pass. Patch SHA256 is
  `36037b35bde5882a530562ab859800e365f17a3bd57e82a2fc2a616527f47b56`.
- Default-on success/empty packet-path atomics are now gated by the existing
  telemetry static key in an isolated patch; failures and fault context remain
  unconditional. Source/model, strict checkpatch, two reproducible builds,
  full Ghidra analysis, and 1,097 hashes pass. Patch SHA256 is
  `8bc1c112a4e731d813c221d211f8914924952e9efb8c61a16e2ca166a300a037`.
- Debugfs stock-parity wording now matches recovered binary evidence: stock
  releases its WiFi token before host-adapter handoff, no explicit stock DMA
  barrier was recovered, and OpenWrt release-last is a safer divergence rather
  than equivalence. Patch SHA256 is
  `938ee5c28ffb4e0f96656f0a9d0b97ff38283c7400478939a41a93c5d2f307fe`.
- The semantic audit now covers all 345 patch paths. The remaining 113 target
  patches expose three P0 rebase hazards: the split kernel/mt76 NPU ABI, old
  LRO versus current HW-GRO, and current 920-12's rewritten RCU QDMA/QoS
  lifecycle. Current-nightly migration reviews are active; historical queues
  must not be stacked wholesale. The current profile remains the verified
  `gemtek_w1700k-ubi` path, not the audit report's generic `ubi2` shorthand.
- Cleanup removed exactly 41 reproducible WSL scratch/build directories
  (9,772,818,432 bytes) and 2,444 old RDP ETL traces (15,726,018,560 bytes).
  Exact logs are retained. Source, reference builds, reports, patches, hashes,
  releases, signing material, images, FinalResult, backups, and router state
  were preserved. No image or router action occurred; release remains
  **NO-GO / NO-IMAGE / NO-FLASH**.

## Patch85 Daybreak19 Final Composition And Nightly Migration - 2026-09-04 17:18 +03:00

- The four Daybreak18 corrections were composed in order on the isolated
  Patch85 mt76 baseline and finished with a style-only cleanup. Final commit is
  `03680307cb0f2586af9e56f5b2f994e5288105f8`; consolidated patch SHA256 is
  `f4f83cf09000917a33c29618661b4c1c615fdbfdb1bcca3216dd7fbe29cfb1d5`.
  Strict checkpatch is 0 errors, 0 warnings, and 0 checks.
- Fourteen aggregate source/model gates pass: nightly 20/20, refill 45/45 with
  12/12 mutants, completion 58/58 plus 48,048 schedules and 8/8 mutants,
  reset 123/123 plus all 256 capability combinations, and the hostile
  lifecycle/refill schedules. Active-NPU reset remains blocked before physical
  writes because restart receipt and complete RX/RRO graph authority are absent.
- Two exact Linux 6.18.34 AArch64 `-Werror` builds are byte-identical:
  `mt76.ko=270f9f6f12a5692c80f2757a7f8ab942f12491fc27d3d3dfe68b940d8cbc2996`,
  `mt76-connac-lib.ko=eb13a0e46c6c977106c89461d54b6cbb63d6d88b09f14ee8b7d1bb3fca7d3d4f`,
  and `mt7996e.ko=cea0696cfcb02be1cb9932ab14fface9858a6f6a019432d71e74a4952d0ddbe8`.
- Full Ghidra 12.1.2 analysis recovered 847, 240, and 1,170 functions and
  completed all 49 requested decompilations. The 35/35 binary verifier confirms
  bounded fatal masking, close-drain publication ownership, NAPI/IRQ replay,
  provider-before-host restore, static telemetry keys, and pre-mutation reset
  refusal. Report SHA256 is `9f3544439d0ae376eddf9299c2fdd6cd53db998ea9b9576d066fcd58cb231d7e`;
  129 evidence hashes verify.
- Current-nightly migration audits pass independently. WiFi/MLO passes all 17
  static gates and preserves 2,395 inputs; its exact current-nightly omissions
  are the W1700K validation/LuCI/MLD owner work, while official AP-MLD and
  backports-7.2 changes must not be duplicated. The isolated GRO correction is
  one capability line (`NETIF_F_GRO_HW`, patch SHA256 `c96f30fb...`). Dormant
  FastTX remains NO-GO. The QDMA lifecycle/TX-unwind sidecar passes 32 checks
  but remains NO-GO for source/image promotion until FastTX RX ownership and
  provider teardown are redesigned.
- Next action is one isolated full-source candidate on pinned current nightly,
  followed by package/module build, full `gemtek_w1700k-ubi` image, FIT/DTB
  identity, browser/runtime, memory, WiFi association, NPU, and throughput
  gates. No authoritative source, image, or router state changed; release stays
  **NO-GO / NO-IMAGE / NO-FLASH**.

## Patch85 Daybreak20 Power-Loss Recovery And Storage Checkpoint - 2026-09-04 18:18 +03:00

- Post-power-loss verification preserved the isolated current-nightly OpenWrt
  branch at `8e813125739179533fb2a59ded89bd8cb879b344` with tree
  `90ee6ab1cbe33e5a8cc0a4ed8e1733ada282a610`, and the mt76 worktree remains
  pinned to `be5ce7910521492d4a2e4ce7ee3843680a46c047`. Both worktrees are clean;
  full Git object checks pass after WSL restart and VHD maintenance.
- The committed OpenWrt delta remains only the independently proven one-line
  `NETIF_F_GRO_HW` advertisement. Direct replay of the Daybreak19 ten-file mt76
  patch against current mt76 failed on all ten files, as expected: current
  upstream lacks the custom lifecycle substrate, so any migration must be a
  semantic rebase rather than a forced textual apply.
- A concurrent five-agent audit was stopped when `C:` reached 0.32 GiB free,
  coincident with the system-managed pagefile expanding to 27.04 GiB. Seven
  incomplete, reproducible source/fixture copies and five stale Temp folders
  were removed; reports, tests, audit JSON, patches, Ghidra data, trackers,
  authoritative trees, images, and recovery media were preserved.
- Ninety-two closed subagent transcripts belonging to this exact parent task
  were retained under lossless NTFS compression. Their 67,445,181,473 logical
  bytes now occupy 57,578,033,152 bytes. The active main transcript and
  unrelated tasks were not touched.
- The active Ubuntu VHD compacted from 97.14 GiB to 71.12 GiB, restoring `D:`
  free space from 3.77 GiB to 29.80 GiB. The read-only 63.93 GiB W1700K
  recovery VHD retained its size and timestamp. The post-restart kernel log has
  no ext4/I/O corruption indicator; it only replaced the system journal marked
  unclean by the original power loss.
- The interrupted current-mt76 audit has useful hunk evidence but an incomplete
  report and a provisional NO-GO/zero-portable-runtime-patch result; the WiFi
  composition and image-plan audits are also incomplete. They are not release
  evidence until rebuilt with bounded, non-forked workflows. No image or router
  action occurred; release remains **NO-GO / NO-IMAGE / NO-FLASH**.
