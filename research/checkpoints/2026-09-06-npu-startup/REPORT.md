# Cold-Start Candidate And OpenWrt Snapshot Comparison

2026-09-06. Implemented and tested an **unpromoted cold-reset candidate**.
No packaged firmware/source-lock change, router action, flash or new release.
R1 remains the last router-tested baseline, with WLAN NPU compiled out.

## Snapshot Findings

The rolling official snapshot advanced during inspection to
`r36060-d6933d6aed` (September 6), kernel6.18.44, mt76`be5ce791` and NPU
firmware package20260810-r1. Eighteen relevant OpenWrt files and all four
inspected NPU payloads match our pinned inputs. The newer top-level commits
do not fix the relevant Airoha startup or recovery paths.

The actual snapshot W1700K DTB still has the short26KiB TX-check reservation;
it does not include our detached-provider guard, mailbox fix926 or preflight927.
Its NPU compile flags are enabled, which is not safe-recovery or runtime proof.
There is no justified NPU rebase/cherry-pick here. See `SNAPSHOT_COMPARISON.md`
and `snapshot-comparison.json` for58 artifact hashes, exact versions, source
comparisons and FIT identity. Official HTTPS/checksums were used; detached
signatures were not verified, and the downloaded image was not flashed.

## Implemented Candidate

- Added `firmware/npu/startup.c/.h`: a64-byte, versioned cold-loader header,
  hart-owned arrival slots, coordinator-only initialization publication, and
  sticky failed-state handling. READY means candidate control state initialized,
  not complete native bootstrap, all-worker parking or physical drain.
- Native reset detour at`0x84000074` validates the coordinator's fresh header
  and native all-ones BSS-retention marker before BSS clear or stack use.
  Common detour at`0x840000f0` waits for actual coordinator initialization of
  barrier/admission/mask state and preserves the displaced reset registers.
- The test loader preserves the original3084-byte DATA prefix and supplies a
 25024-byte SRAM test image, placing the header at`0x3e906180`. Every hart uses
  the reset path; the native reset tests do not call init from Python.
- Independent review found READY-after-fault resurrection. Fixed it by making
  FAILED's atomic phase store precede the fault latch and rechecking the latch
  after acquiring READY. Assembly failure ordering matches with release fences.
  Review and correction are preserved in `STARTUP_REVIEW.md`.

## Verification

- 32 serialized eight-hart reset orders,32 complete register comparisons,
  30 rejected entries, an interrupted-init fault and two missing-hook controls.
  Missing common gate permits premature native continuation; missing pre-BSS
  gate detects a bad template only after native BSS destruction.
- 173 native-C/RV32 protocol cases,2126 differential calls and six compiling
  mutants. Neither initialization nor READY fabricates worker ACKs or drains.
- Two instruction-paused races reproduce the pre-fix CONTINUE result and are
  blocked by the correction. The test uses noinline helpers and NOP pause labels
  around the real source operations; it does not claim hardware concurrency.
- Twelve prior suites plus combined copy/worker/admission checks pass. Both
  poll-limit builds reproduce; two65536-poll holds retain ownership after late
  completion. These component tests remain distinct from the reset tests.
- Final ELF SHA256:
  `16d330eb21f84e47a7bc9f0e5ff49d2c1552cef241455d48770768ded211850a`.
  Ghidra exports six selected startup functions from56 discovered functions.
  Explicit symbol-span seeding repairs the missed precheck and split cold-start
  body. The pre-fix five-function export is retained separately, not a final gate.

Ghidra confirms phase-before-fault stores in poll at`0x8404236e/374`, in
publish at`0x84042688/690`, and precheck at`0x840427da/7e6`; the publish CAS
uses LR/SC at`0x8404266e/676`. The early gate jumps to native`0x84000078`, and
the common gate restores registers and jumps to`0x840000f4`. Native tests execute
those continuations. Ghidra's standalone extension import lacks original-code
memory at those targets and reports truncated decompiler flow there; do not
interpret it as complete linked-boot analysis. Its existing GUI XML warning is
also retained. Instruction bytes, spans and native execution are the evidence.

## Bootstrap Contracts And Next Work

The second subagent's218 original-firmware cases pass on rerun:
API32 releases the56KiB clear, API23 releases consumer initialization waits,
API18 is a successful no-op, and API12 changes routing rather than proving stop.
Address diagnostics do not reject writes. API23 consumers already perform MMIO
writes before their address wait. See `BOOTSTRAP_CALLBACKS.md`; these are not
physically safe callback classifications or a completed admission allowlist.

Next implement complete bootstrap sequencing and checked negotiation: permit
required initialization commands without opening general legacy admission;
prevent startup consumers from running with incomplete resources; prove native
callback installation, main/IRQ reachability and transition into the barrier.
Current strict admission remains closed, so this checkpoint does not claim that
core0 can finish its address-dependent main initialization with that adapter.

The host must independently contain prior users and coherently upload fresh
paired state before release. A fresh-looking header does not prove containment;
the all-ones marker is only the observed native BSS-retention condition, not
exhaustive warm-reset detection. No instantaneous revocation of already-passed
gates, no-BSS-write guarantee after an overlapping fault, or production SRAM/cache
proof is claimed. Physical drains, Linux recovery/removal/retention, full datapath
parity and real-client Wi-Fi acceptance remain open.

## Replay

```sh
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_startup_native.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_startup_protocol.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_startup_race.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_bootstrap_callbacks.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/run_startup_regressions.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/verify_startup_evidence.py
```

Proprietary inputs and generated ELF/SRAM test inputs remain ignored. There is
no flattened patched firmware or installable image. Ledger/reference/remaining
work are updated; protected historical and recovery files are untouched.
