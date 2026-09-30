# W1700KNPU Workspace

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

## Current Checkpoint - 2026-09-30

- Source checkpoint `ac4c639` includes paired firmware preflight in the unified
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
- The local source is WSL Ubuntu `/home/captain/W1700KNPU`, accessible from
  Windows at `\\wsl.localhost\Ubuntu\home\captain\W1700KNPU`. The Ubuntu backing
  disk is under `D:\WSL\Ubuntu`. The prior `D:\W1700K-Recovery` snapshot path
  was absent on 2026-09-30; verify the current location of recovery material
  before relying on historical backup paths.
- Preserve the distinction between modeled, compiled, Ghidra-verified, flashed,
  synthetic-router-tested, and actual-client-tested behavior. Stock NPU parity
  remains incomplete. Never label the WLAN-NPU-disabled baseline stock parity.
- Use `firmware/source-lock.json`, cumulative patches and overlays as source
  authority. Build on WSL native ext4, never directly on NTFS. Generated builds
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
