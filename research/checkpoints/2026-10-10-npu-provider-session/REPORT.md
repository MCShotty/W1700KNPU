# Provider-Owned Initial Held NPU Session

## Result

The actual checked Linux provider's `wlan_init_reserved_memory` callback now
owns the initial V2 setup lane. The existing mt76 caller reaches it without
creating per-attachment session state. One provider embeds the executor and
serializes the whole attempt, RNG, protocol/prefix and CPU close.

The attempt is consumed before RNG or transport. DISCOVER must match the
loader-published boot identity and initial held epoch before the six existing
commands. BIND/STOP and at most100 STATUS polls require epoch1, all software
workers parked, and release/arm/ready/drain zero. The final polling snapshot is
checked. Failed setup closes CPU control and retains the first error; a repeat
after success returns EBUSY. No reset, DMA release, token cleanup or rearm is
introduced. Existing pre-publication allocation retries remain unchanged.

The canonical client/executor objects now link into `airoha_npu.ko`, not mt76.
`provider-main.c` preserves the established provider source path and module
filename while enabling a composite Kbuild object. Source-lock mappings place
the ten exact canonical files in the target kernel overlay. The image verifier
requires the client definitions in the provider and rejects them in mt76.

CPU/wire initialization is explicitly separated from independent physical cold
containment. The latter is still required for hardware setup and any eventual
release/rearm; neither enrollment nor a matching identity establishes it.
Wider CPU ownership continues to depend on existing consumer references/device
links. Close joins only this setup/executor, not every independent provider user.

## Verification

- Actual provider setup, executor/client and portable bootstrap server C pass
  279 cases with address/undefined/leak sanitizers. Covered:80 transaction faults
  before/after modeled effect,80 reply-field corruptions,101 polling boundaries,
  required loader state, zero/error RNG and two concurrent setup/close cases.
  Nine compiled mutants fail the intended assertions.
- The tests were strengthened after a wrong-identity mutant exposed an oracle
  that detected eventual failure but did not require immediate prefix denial.
  The final oracle checks that no subsequent transaction follows a bad reply.
- Two actual Linux-C-to-raw-RV32 cases consume CODE/DATA emitted by the actual
  C loader/publication harness. Nominal DISCOVER/prefix/BIND/STOP/STATUS parks
  all eight harts in the held epoch; wrong identity stops after DISCOVER. No
  synthetic plan/identity overwrite or post-load ELF injection occurs. Backing,
  transport delivery, host pointer publication and worker scheduling are modeled.
- Exact source comparison shows the legacy initializer, retry policy and WLAN
  framing unchanged. The unmarked dispatch directly returns that initializer;
  this is source preservation, not physical legacy runtime acceptance.
- Actual parser/publication60/eight, boot248/ten, lease13/four, probe269/three
  and request310/nine cases/mutants pass. Probe tests model session callbacks;
  the separate session runner executes them. Memory273/159 plus three earlier
  controls/nine mutants, retry6,174 and V2 44 regressions pass.
- Full raw-only replay retains3,072 PKT and1,792 independent BA claims, with six
  boot/eight TXDONE failure controls. Its full ring setup still uses an explicit
  modeled held callback lease. The real strict legacy transport remains denied.
- Sixteen assembly/readback groups pass without skips. Two independent builds
  have identical CODE/DATA and matching pinned input provenance. An initial
  comparison used different original-input paths and was correctly rejected.
- Full OpenWrt world exits0;58 OpenWrt plus5 LuCI source files replay;13 builder,
  four source-verifier and four module-owner unit tests pass. FIT/Gemtek board,
  checked pair/manifest,218 packages and78 module ABI checks pass.
- Exact packaged provider `f8dfc82e...` undergoes full Ghidra autoanalysis/export:
  48 executable functions,48 exports, zero decompilation failures. The compiled
  identity guard, once latch, bounded polling/final snapshot, error close,
  provider callback registration and cleanup are present. Ghidra is static
  evidence, not kernel or hardware execution.
- Provider delta checkpatch reports zero errors/warnings/checks. World retains
  upstream/package warnings and its ignored U-Boot install error; this is not a
  warning-free build. An obsolete image-verifier expectation was corrected to
  enforce provider ownership. A post-fix source selected as an original failure
  control was not accepted as negative evidence; final probe receipts omit it.

## Artifacts

FIT26956618 bytes:
`6a7dc41ebcec3070231764e8ba226cef29b7b5383ba1ed5e5b7c9cf0e639461a`.

Packaged provider:
`f8dfc82e86ae5cca751ed3e7b7073d41cd4af28deee0fce13f05f618c91db13f`.

Unchanged CODE529336 bytes:
`bc15190ead08ebb44a6feba439f39ae8e7bcbaf9e5ce5851a3e2146ebd1893a5`.
Unchanged DATA25728 bytes:
`5311ef172aec19164723a273230d47fb147b7bee8e522f13a86580ce87c58d75`.
The core archive remains unchanged. Exact source/artifact hashes and sealed
receipt copies are in `verification.json` and `file-manifest.json`.

The preceding `b0400eaa...` complete image is hash-verified and preserved under
`.local/npu-provider-session-20261010/pre-world-image/`. Prior images, R1,
bootloader/calibration/private backups remain protected. No router contact,
hardware reset, flash or physical acceptance occurred.

## Jev Review

The official Windows helper uses `Typesafe API` in memory and modeljev-1.13.0.
Five design questions, seven source/receipt checks and a focused follow-up are
retained with raw probabilities. Seven review choices select supported; the
legacy check initially has probability.67/confidence.51 and is not treated as
proof; the focused follow-up remains uncertain at probability.66/confidence.49.
Exact unchanged-function comparison and compiled-branch inspection
provide additional evidence for that narrow source claim. The report preserves
that scope, not a legacy hardware claim. Identity/failure claims are reviewed
against the actual source, Ghidra and deterministic fault oracles as well.
Jev supplies semantic judgments, never code, execution or action authorization.

## Reproduction

Run in canonical WSL `/home/captain/W1700KNPU`, with fresh result names:

```sh
export PYTHONPATH=.local/npu-reset/python-lib:tests/npu
provider=.build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.52/drivers/net/ethernet/airoha/airoha_npu.c
pair=.build/merged-openwrt/bin/npu-pair-npu-provider-session-20261010
python3 tests/npu/test_checked_loader.py --source "$provider" --pair "$pair" --name fresh-publish
python3 tests/npu/test_provider_session.py --source "$provider" --pair "$pair" --publication .local/npu-loader-publish-20261010/fresh-publish/nominal --name fresh-session
python3 tools/build_firmware.py --name fresh-session-world --jobs 8
python3 tools/verify_merged_image.py --name fresh-session-offline
```

Do not modify consumed sources while assembling/sealing receipts or run tests
against a prepared kernel directory while world is replacing it. The portable
test shims do not assert the real private kernel structure layout; complete
module compilation/Ghidra provide a separate compiled check.

## Remaining

Full strict held cold RX/TXDONE transport/callers remain unimplemented. Do not
fabricate an active callback lease to make that path pass. Independently prove
prior-user physical exclusion, exact backing/cache/DMA visibility, remaining
packet/page owners, workers/hot lifecycle/postgate and physical drains/retirement/
teardown/rearm/recovery. Exact-image physical boot/recovery and actual clients
remain required. The full NPU reverse-engineering/implementation goal stays open.
