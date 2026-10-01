# Pre-Copy MT7996 Memory Plan And Engine Ownership

Checked 2026-09-30 in the transferred cloud checkout, starting from clean
`59e75a84267f24a13d5fbb917ac3d608405a286a`. The bounded source correction is
integrated into the canonical kernel patch and source lock. It moves selected
memory admission earlier; it does **not** establish a contained cold provider
lifetime, exclusive storage ownership or physical DMA retirement.

## Correction

The preceding provider validated `tx-bufid`, `pkt`, `tx-pkt` and optional `ba`
only when WLAN setup ran. Probe had already copied the firmware pair and issued
boot/MIB writes by then. Invalid geometry could therefore be detected after
firmware replacement and boot publication.

For the exact EN7581/MT7996 image profile, the paired loader now validates the
complete WLAN memory plan before either firmware request or copy. The existing
checks remain: lookup errors, nonzero/aligned 32-bit extents, the firmware DRAM
window, firmware/pairwise overlap and the 56 KiB TX-check minimum. Only a fully
validated plan gets a usable count. Setup consumes that captured address/count
snapshot without reading the DT again.

Other image profiles still need no WLAN reservation to load, preserving
PPE-only use. If they later request WLAN setup, they validate into a per-call
stack plan. They do not share mutable setup scratch storage. The existing
command order, optional BA behavior and allocation-only retry policy remain.

A private `firmware_loaded` flag is cleared at run entry and set only after
both copies finish. Setup rejects failed/uninitialized loads before commands.
Request failures invalidate the MT7996 plan, and early match-data, mapping and
binary-region failures cannot reuse an earlier successful admission. This flag
means the image-copy path completed; it is not a boot, reset or drain witness.
The production entry remains probe-only. Repeated-call test fixtures do not
authorize live reload or concurrent firmware replacement.

No public provider struct/ops ABI, reset control, teardown, resource free,
post-publication register error path, restricted INODE framing or DESC5-8 path
was changed. In particular, ignored MIB errors were not changed into unsafe
probe returns that could release device-owned resources.

## Source Authority And Replay

Official Linux `v6.18.52` provider source plus nine patches from OpenW1700k
`288d79449f622a37c727cb12e81e85dba822aecb` reconstruct the upstream provider:

- Upstream provider SHA256:
  `37bf128e7cd7c212e9a30c8b76f031522dede2059b4709e97805b648e01193d9`
- Previous integrated provider SHA256:
  `8dc8545d3b5ea776820f2d75ed0795fee0ca8f93a12bb9e0708169320425f052`
- Updated integrated provider SHA256:
  `026789bacd65b4a8c6ff25317c4ba8b33acfd52dde66c7c455758812ce8fe582`
- Unchanged integrated public header SHA256:
  `b33a814650dac669b826016cf4201301913f766dbc882a248abb63e6fe013ee0`

Both earlier provider hashes match the retained paired-loader receipt; the
header matches the unified-merge prepared-driver receipt. Fetches are read-only
through the authorized GitHub connector. Git blob identities were verified
before patching. The compact public fixtures and URLs/blob IDs are retained in
`tests/npu/fixtures/airoha-npu-6.18.52/`. No credentials or private router data
were transferred or published.

The new replay runner checks the canonical patch against the source lock,
reconstructs the prior control from `ac4c639`, and applies the current patch to
the fingerprinted upstream fixture. This is exact **provider-file replay**,
not a new replay of all 60 OpenWrt/LuCI changed files.

## Verification

- The existing 273 actual-C firmware-loader cases pass, preserving paired
  preflight, whole-destination guards, request errors and acquired-object release
- 165 additional load scenarios pass, with further assertions for invalid
  region rejection before requests/copies, optional BA, exact command order,
  setup failures, immutable snapshots, stale-plan rejection and generic-profile
  reentry. The counter counts load-verification calls, not every assertion
- Three original-source controls fail their named oracles and pass after the
  change: late invalid-memory detection, post-load DT rereading and admission
  following a failed image load
- Nine compiled mutants are rejected, including omitted early preflight,
  post-load rereading, stale early-run admission, lost snapshot copy, missing
  overlap/minimum checks, forced generic WLAN loading and shared generic plans
- Existing actual-C retry and Linux V2 executor regressions pass 6,174 and 44
  cases respectively; the executor receipt explicitly keeps physical drains false
- GCC 14.2 x86-64 AddressSanitizer and UndefinedBehaviorSanitizer are enabled
  with warnings treated as errors. LeakSanitizer is disabled because its
  ptrace-based check fails in this managed environment; these memory-plan
  fixtures use static storage. This is disclosed, not counted as a leak pass
- Strict Linux 6.18.52 checkpatch on the isolated source delta reports zero
  errors, warnings and checks. Python compilation and Git whitespace checks pass

Review found a shared mutable scratch-plan risk in the first generic-profile
draft; the accepted implementation keeps generic plans caller-local. A reentry
oracle and a mutant retain this regression boundary. Initial scaffold/style
and LeakSanitizer failures remain in ignored scratch evidence and are not
counted as successful runs.

The host models replace OF lookup, memory mapping, firmware delivery, register/
mailbox delivery and kernel mutex behavior. They do not execute RV32 firmware
or real hardware. No complete AArch64 provider object, prepared kernel, module
link, full image or hardware test was run for this change: the transferred
checkout has no prepared kernel/cross-toolchain or Clang. Earlier target-object
and image receipts retain only their earlier source scope.

No installed local TypeSafe/Jev skill, service tool or authorized credential is
available in this cloud checkout. No new Jev call or probability is claimed.
Codex source review and the explicitly scoped tests provide this checkpoint's
software evidence.

## Remaining Gate And Physical Handoff

`ENGINE_OWNERSHIP.md` records the separate reset lines, copy-engine versus
FE/PPE naming distinction, known RV32 owners and missing hardware witnesses.
Its expanded reset-map review is explicitly tied to the hash-matched 6.18.44
prerequisite source; it does not pretend to independently verify the entire
6.18.52 reset map.

No physical action is needed to finish this offline checkpoint. Before a
subsequent boot test, prepare the full pinned build/toolchain, compile and link
the updated provider, run aggregate source/image checks, verify the exact FIT
and target identity, and arrange separately authorized serial-backed testing
with current protected backups and R1 rollback. The old flashed image predates
both this change and the paired-loader correction.

Reset/drain stress is a later gate: first close the producer/consumer graph and
corroborate each domain's coverage, outstanding bus behavior, SRAM accessibility,
visibility and failure-retention contract. Identify physical retirement witnesses
for every engine before designing a reset test. STOP/GET, PARKED, IRQ masking,
fixed delays or reset-bit readback do not supply those witnesses.

Fresh loader identity, reserved/coherent storage publication, actual
DISCOVER/setup/BIND callers, postgate/native execution, complete teardown/rearm
and real-client acceptance remain open. Full stock-NPU parity remains unfinished.
No image, flash, router setting, protected device data, commit or remote ref was
changed by this checkpoint.

## Reproduce

From the repository root, with GCC and Git, choose a fresh name:

```sh
python3 tests/npu/test_cold_memory_plan.py --name fresh-replay
```

The runner creates ignored `.local/npu-cold-memory-plan/fresh-replay/` evidence
and performs no network or hardware operations. Its default path tests the
canonical source-lock-checked patch. The optional `--candidate-source` path is
explicitly marked as a staged candidate and is not the accepted canonical run.

Current receipts, delta, logs and final fingerprints are retained beside this
report. Generated binaries and fetched build-helper inputs remain ignored.
