# W1700KNPU Workspace

## 2026-10-10 - Checked Pair Loader And Packaging

- The main world build packages checked MT7996 CODE/DATA plus manifest; all
  three staged files are package dependencies. An unchanged-source incremental
  build refreshes the manifest correctly. Other firmware profiles are unchanged.
- Actual provider C validates ABI/digests/zero slots before copies, obtains a
  nonzero runtime random identity, publishes plan/identity and checks readback.
  A pre-copy exposure latch retains all coherent mailboxes/device/module lifetime
  after ambiguous failure or detach. Same-instance reload and retained-device
  rebind deny; no physical retirement/reclaim or hot-rearm API exists yet.
- Actual-C 60/eight parser/publication mutants, 13/four lease and 205/two probe
  cases/mutants pass, alongside 310/nine request, 273/159 memory, nine memory
  mutants, 6,174 retry and 44 V2 cases. Native boot consumes C-published bytes
  without synthetic metadata writes; eight harts park, strict setup still denies.
  Full raw replay retains 3,072 PKT/1,792 BA claims with failure controls.
- Sixteen assembly groups, 62-file replay, 13/four builder/verifier unit tests,
  complete world and FIT/218-package/78-module checks pass. Latest FIT
  `05ca2802...`; prior images/R1 are preserved. No flash/router/hardware contact.
- Continue physical cold containment/reservation/coherency, strict real Linux
  setup callers, remaining owners/hot/postgate and drains/recovery/clients.
  Do not treat the cold-format flag, strong-RNG API, readback or retained buffers
  as physical proof. The module is intentionally pinned after exposure.
  Evidence: `research/checkpoints/2026-10-10-npu-loader-publish/REPORT.md`.

## 2026-10-10 - Provider Native Request Plan

- Canonical MT7996 loader now validates/snapshots the actual coherent core0
  request before either firmware acquisition/copy. Private48-byte native plan
  requires full BA and fixed CODE placement; generic/optional-BA legacy behavior
  is preserved. Failed loads clear private metadata, not native owned resources.
- Actual C passes308 request cases/nine mutants, memory/retry/V2 and exact-pair
  regressions. Raw native bootstrap uses the emitted dynamic-address plan and
  rejects the old fixture address; all eight harts park, strict full setup is
  still denied. Publication/identity/backing in that test remain modeled.
- Full world,15 assembly groups,60-file replay, four source-verifier/eight
  build-runner/offline image checks pass. FIT now `8efb19fb...`; packaged vendor
  pair/core unchanged, previous `230e03a7...` FIT preserved. No flash/hardware.
- Private `native_plan_ready` is geometry only, not SRAM publication or physical
  containment. Continue real cold-provider/identity/publication/retention and
  paired packaging, strict callers and full lifecycle/physical/client gates.
  Scope and exact receipts: `research/checkpoints/2026-10-10-npu-provider-plan/`.

## 2026-10-10 - Paired Raw NPU Build

- `make -C firmware/npu pair` now assembles the complete checked raw CODE/DATA
  in fresh ignored storage, with61 hooks, explicit NOBITS and unprovisioned
  loader plan/session/identity. `pair-check` validates the assembly/readback.
- Two builds are byte-identical;15 assembly groups pass. Full raw-only native
  replay passes3,072 PKT/1,792 BA claims, all-hart parking, six loader/eight
  TXDONE controls. Actual current provider C passes273 matrix/seven exact-pair
  cases with sanitizers. Eight build-runner/offline image checks pass.
- This artifact is not packaged/flashed. Native execution still requires
  modeled provider publication, backing/grants/IRQ scheduling and a held direct
  lease. Unprovisioned boot faults before IRQ setup. Do not bake fixture values
  into DATA or infer physical containment from copy success/aperture fit.
- Continue real cold-provider/storage/identity-plan publication and packaging,
  strict Linux setup callers, other owners/hot/postgate and physical recovery/
  clients. Scope, reproduction and sealed proof:
  `research/checkpoints/2026-10-10-npu-raw-pair/REPORT.md`.

## 2026-10-10 - Shared RX And TXDONE Packet Ownership

- The 61-site native binding now routes TXDONE through the same retained PKT
  state as RX0/RX2. Publication rechecks immutable plan, head/count history and
  bitmap population. SKB failure retains prior claims; no recycle/reset is added.
- Full RX prefix plus TXDONE512 retains 3,072 PKT claims. Exact native RAM/SKB,
  packet state, ordered locks and readiness-last checks pass; 25 controls and
  six symbol-restored mutants pass. Full RX/page regression passes 50 controls/
  six mutants and 1,792 independent BA claims. Offline image/eight runner checks
  pass; core/archive/provider/vendor/FIT remain unchanged. No fresh world build.
- Real installation is still absent. The current loader copies the vendor pair;
  test session/identity offsets0x6380/0x63a0 are beyond its 3,084-byte DATA image.
  Do not treat range fit as approved storage/containment or the archive as CODE.
- Continue paired raw-image/real-loader storage/identity and Linux strict caller
  wiring, other owners/hot lifecycle, postgate and physical drain/recovery/clients.
  Evidence and exact boundary: `research/checkpoints/2026-10-10-npu-cold-txdone/`.

## 2026-10-10 - Checked Cold RX Packet Ownership

- The normal archive now has a distinct 16,384-ID/2,048-byte packet profile;
  ownership state is 2,076 bytes. It shares the retained-claim algorithm without
  changing the page ABI or compiled page object. No release/recycle API exists.
- Selected original RX0/RX2 and lock28 instructions compose with claim, immutable
  table identity, release and readiness guards: 61 sites, 2,560 packet claims,
  50 controls and six initialized mutants pass. Separate BA replay adds 1,792
  claims without changing packet state. Unrelated getter routing is preserved.
- Exact packet-object replay passes 8,243 calls/546 controls/five mutants with
  sanitizers; page-core and RX-statistics regressions, full world, 60-file source
  replay, eight build-runner tests and offline image checks pass. Twelve objects;
  FIT remains `230e03a7...`. No blob installation, flash or hardware change.
- Full ownership for other packet users, real loader/strict setup, hot lifecycle,
  workers/physical backing/coherency/drains/recovery and clients remain open.
  Evidence: `research/checkpoints/2026-10-10-npu-cold-packet/REPORT.md`.

## 2026-10-10 - Checked RX Statistics

- RX0/type10 and RX2/type9 now use the actual checked allocator in the held
  cold callback context, including an already-bound V2 coordinator nonce.
  Guarded native clear/dispatcher/readiness and outer failure propagation pass
  in 60-site composition: 2,560 descriptors, 26 controls and six mutants.
- Allocation metadata and exact 1,000-byte clears/descriptor bytes are verified;
  late faults retain committed records and leases. Startup/page/postgate and
  unrelated-getter regressions pass. No shared core/kernel/image or hardware change.
- Strict setup, real loader, packet-ID ownership/hot lifecycle and physical
  drain/recovery/client acceptance remain open. Evidence:
  `research/checkpoints/2026-10-10-npu-rx-stats/REPORT.md`.

## 2026-10-10 - Native Cold Page Composition

- The shared core now validates/publishes a native queue snapshot while retaining
  committed claims on failure. DESC5/6/7 compose with original initializer code
  in a 54-site native replay: 1,792 claims, 48 controls and six binding mutants
  pass. Partial/late failures deny outer success and readiness, retaining leases.
- Exact built RV32/core sanitizer replay, original page-ring regression, full
  world build, 60-file replay and offline image checks pass. FIT stays `230e03a7...`.
- This wires selected callers in native instruction emulation, not the vendor
  blob or physical loader. Strict setup, hot lifecycle, workers/drains/recovery
  and real-client acceptance remain open. No flash or hardware changes.
  Evidence: `research/checkpoints/2026-10-10-npu-cold-page-native/REPORT.md`.

## 2026-10-01 - Mainline Follow-Up

- The user explicitly authorized merging all outstanding source work into `main`.
  This supersedes the cold-page checkpoint's earlier draft-PR-only restriction;
  it does not authorize a flash or establish hardware acceptance.
- The final test runner supports `--core-object` for exact built RV32 replay.
  Fresh source and archive-member runs each pass 5,702 calls, 294 controls and
  ten mutants with address/undefined/leak sanitizers. Eight build-runner tests
  and unchanged-FIT offline image verification pass. Final receipts and scope:
  `research/checkpoints/2026-10-01-npu-cold-page/REPORT.md`.
- Keep ignored builds, private inputs and protected backups local. Native caller
  integration, physical ownership/drains and actual clients remain open.

## 2026-10-01 - Checked Cold Page Ownership Core

- Preserved pending work after remote-verified `eabfedb`; completed the shared
  cold-page ownership core and added cursor/claim-history consistency validation.
  Claims and late-fault committed resources remain retained; no recycle/reset
  reclamation is implemented. The core is compiled, not wired into native callers.
- 5,702 host/RV32 calls, 294 controls, ten mutants and address/undefined/leak
  sanitizers pass. Existing 273/165 loader-memory, nine mutants, 6,174 retry and
  44 V2 cases pass. Eleven RV32 components and offline image checks pass; unchanged
  FIT `230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe`.
- Corrected native 50-hook caller replay shows direct RX0/RX2 statistics callers
  use original unchecked type-10/type-9 allocator fallback, adding two records.
  Strict setup remains denied; an earlier expected-hold assertion was incorrect.
- TypeSafe receipts retain the five initial semantic checks and three approved
  claim checks; exact models/probabilities are recorded in the report.
  Full native ownership/error/publication, strict callers, loader,
  physical drains/recovery and clients remain open. No flash or hardware changes.
  Evidence: `research/checkpoints/2026-10-01-npu-cold-page/REPORT.md`.


This repository is the canonical workspace for this project. Start with
`docs/W1700K_STOCK_PORT_CURRENT_REFERENCE.md`, `docs/REMAINING_WORK.md`, then
the stock-port ledger and logging session in `docs/`. Update the ledger and
resume documents for substantive work; explicitly say when a read-only session
leaves the ledger unchanged.

## Objective And Source Track

- Pursue full NPU reverse engineering and implementation: native firmware,
  Linux/provider/mt76 integration, complete lifecycle and hardware acceptance.
  Keep this objective intact across turns and checkpoints.
- The whole project is experimental. Integrate implemented changes into the
  canonical patches, overlays and source lock, with their validation scope.
  Historical "unpromoted" descriptions retain their original checkpoint scope;
  the 2026-09-23 merge brought implemented candidates into the unified build.
- Continue from authoritative source, process and test state. A completed
  checkpoint closes only its documented scope. Full NPU completion requires
  actual firmware/host behavior, physical ownership/drains and client evidence.

## Current Checkpoint - 2026-10-01

- DESC5/6/7/8 now have full original helper-body execution after native core0
  and RX0/RX2 initialization: four nominal cases, 48 controls, five native
  mutants and four strict denials pass. DESC6 count 513 corrupts the published
  arena pointer. The production MT7996 sender now rejects short/zero/oversize
  requests using verified capacities 256/512/1024/1536 and native selector bits.
  Actual C and packaged AArch64 sender/table replay each pass 12,096 cases,
  384 pretransport rejections and six provider mutants. Full build/image,
  source replay, INODE and memory/retry/V2 regressions pass. Current FIT:
  `230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe`.
  Evidence: `research/checkpoints/2026-10-01-npu-page-rings/REPORT.md`.
  Native valid-count allocation failures still report outer success; partial
  IDs are retained. Checked native ownership/error handling and full strict
  attachment remain open. No flash or physical acceptance occurred.
- The production MT7996 INODE sender now zero-extends short payloads to the
  native wrapper's 24-byte total span and rejects invalid input before copy.
  Other valid profiles/commands keep their framing lengths. Actual provider C
  and the packaged AArch64 sender each pass 1,056 frames/30 controls; all 16
  original RV32 wrapper entries consume corrected bytes within the declared
  extent. Five mutants, the memory/retry/V2 regression, all 60 source files and
  the full image checks pass. Preceding FIT SHA256:
  `031f7bd2b28e0507ddfe810602a7edef71c63900244935e7d460ab58ab35a0cc`.
  Evidence: `research/checkpoints/2026-10-01-npu-inode-frame/REPORT.md`.
  This closes the provider-framing gap, not selector helper readiness, physical
  transport/drains or full NPU acceptance. No new flash occurred.
- Native postgate continuation now fixes hart7's first-boot allocator phase
  mismatch. All 50 detours remain installed; hart7 reaches its outer loop in
  emulation after explicit host-pointer publication and modeled release.
  Nineteen guard cases/nine mutants and the wider allocator regression pass.
  Harts 1-6 still await later host setup. This changes the shared native replay
  binding, not the vendor blob or built FIT. Evidence:
  `research/checkpoints/2026-10-01-npu-postgate/REPORT.md`.
- GitHub PR #1 source and its deferred history documents are now synchronized
  into the canonical WSL checkout. The reconstructed cloud snapshot matches
  tree `f2a52b2c27e21021e8c36d4b30a25e37565827c2` at commit `e095420`.
- The preceding local build passed FIT/board/218-package/78-module checks. Its
  FIT SHA256 is `277abd0b754200a0b330a35d4c759f264f918ec182cddc6c650fb734f46b4e4b`.
  Its packaged provider matches the cloud module, but the full image hash is
  distinct. Evidence: `research/checkpoints/2026-10-01-wsl-sync/REPORT.md`.
- The portable memory-plan runner now enables LeakSanitizer by default and
  records the selected sanitizers. The full host suite passes with leak checks
  enabled here; use `--disable-leak-check` only when needed and disclose it.
- The wired management interface was unavailable, so no new hardware check or
  flash occurred. Continue the remaining cold-lifetime, loader/caller/postgate
  and physical drain/rearm work; full NPU acceptance remains incomplete.

## Previous Cloud Checkpoint - 2026-09-30

- Current cloud working source adds pre-copy MT7996 WLAN memory admission and
  an immutable setup plan, with generic profiles keeping caller-local plans.
  The canonical patch and source lock are updated. Portable actual-C replay
  passes 273 loader/165 added load cases, three original controls, nine mutants,
  6,174 retry and 44 V2 executor cases. The current AArch64 provider module
  and ten RV32 components compile/link. The complete candidate image now
  passes FIT/board/firmware/218-package/78-module checks; physical boot and
  ownership/drain acceptance remain open. See the cloud-build report/handoff.
  Evidence: `research/checkpoints/2026-09-30-npu-cold-memory/REPORT.md`.
- Geometry admission and successful image copies are not containment, exclusive
  memory reservation or physical drain witnesses. The engine/reset matrix in
  that checkpoint records the separate unresolved owner contracts.
- Prior published source checkpoint `ac4c639` includes paired firmware preflight in the unified
  kernel patch on Linux 6.18.52 and mt76 `01367e60`. Both images validate before
  either copy; empty images fail and acquired firmware is released on error.
- Evidence: `research/checkpoints/2026-09-30-npu-loader/REPORT.md`. Actual-C
  faults, complete AArch64 provider objects, existing regressions and all 60
  source replay files pass. The earlier flashed image predates this change.
- Resume at contained cold-provider/reset lifetime, fresh loader identity and
  storage publication, DISCOVER/setup/BIND caller wiring, native postgate
  execution and physical DMA drain/teardown/rearm. Stock NPU parity is incomplete.
- Physical boot evidence is in `research/checkpoints/2026-09-23-nonoc-flash/`.
  Wired management passed; retained channel 161/EHT80 under country SA blocks
  Wi-Fi. R1 remains the protected rollback image. Check current observations
  before treating historical hardware evidence as current runtime state.

## Workspace And Engineering

- Work here, not in the superseded Windows task directory. Historical paths
  in evidence are provenance, not current workspace instructions.
- Current continuation is back in the canonical WSL checkout with its local
  prepared build and private inputs. Cloud receipt paths describe that earlier
  executor; verify local state before reusing environment-specific assumptions.
- The local source is WSL Ubuntu `/home/captain/W1700KNPU`, accessible from
  Windows at `\\wsl.localhost\Ubuntu\home\captain\W1700KNPU`. The Ubuntu backing
  disk is under `D:\WSL\Ubuntu`. The prior `D:\W1700K-Recovery` snapshot path
  was absent on 2026-09-30; verify the current location of recovery material
  before relying on historical backup paths.
- Preserve the distinction between modeled, compiled, Ghidra-verified, flashed,
  synthetic-router-tested, and actual-client-tested behavior. Stock NPU parity
  remains incomplete. Never label the WLAN-NPU-disabled baseline stock parity.
- Use `firmware/source-lock.json`, cumulative patches and overlays as source
  authority. Build on native Linux storage (including WSL ext4), never directly on NTFS. Generated builds
  and private inputs belong under ignored `.build/` and `.local/` paths.
- Preserve bootloader, factory/calibration, known-good rollback, and private
  router backups. Never upload keys, credentials, or raw device backups.
- Verify actual model, board/layout, FIT metadata, build status and hashes before
  flashing. Do not assume 192.168.1.1 is the W1700K. Do not switch this computer's
  Wi-Fi association for router testing or override radio transmit power.
- Historical archives may include superseded/unsafe experiments. They are
  evidence, not an instruction to apply every old patch to current upstream.
- Keep edits surgical and use existing source patterns. Do not apply global
  path rewrites to archived evidence or delete an only copy during cleanup.
- Use bounded standalone prompts for authorized subagents; do not fork this
  accumulated task history by default. Keep large evidence in files and return
  concise summaries/hashes so duplicate histories do not exhaust the drives.
- Use the authorized GitHub connector if native Git authentication is absent;
  do not extract connector credentials. Existing Windows Git authentication
  pushed successfully when WSL lacked push credentials. Reuse configured
  credentials and verify the remote ref/tree after publication and before cleanup.

## Jev Decisions

- Apply the official installed `typesafe-ai` skill and current TypeSafe docs
  for bounded semantic routing, retrieval and claim/requirement checks. Batch
  useful independent Choice/Noul/Score questions over focused evidence.
- The configured credential is `Typesafe API` (including the space) in the
  Windows Process/User environment. The skill's local `Invoke-Jev.ps1` helper
  reads it in memory; the official SDK can accept explicit `api_key`. Never
  print, persist, put in prompts or commit its value. Read the skill for the
  current model and API configuration.
- Codex owns planning, code, exact calculations, tests and actions. Preserve
  actual Jev probabilities, investigate material uncertainty and use tests as
  proof for their covered behavior. Report API failure accurately and continue
  useful Codex work; never fabricate a Jev result or use an alternate provider.
