# Current RRO Reset Target Qualification

Classification: progress, not completion of the full NPU goal. This supersedes
the pending target links and caller regression in the prior rro-reset checkpoint.

## Current Results

- All four AArch64 modules final-link with GCC14.4.0/Linux6.18.52:
  airoha_npu.ko, mt76.ko, mt76-connac-lib.ko and mt7996/mt7996e.ko.
- Actual mt7996e defines all five new reset helpers and imports mt76_npu_rro_abort,
  exported by mt76. Current checked header and dependency edges pass inspection.
- Producer `.local/npu-checked-irq-modules/rro-reset-target-q1/result.json`, SHA
  `8065c523c42c9c09f8a4e46ae2eb93ddf4962578a7e7e830672df16d09b5f3e9`,
  binds 5 kernel/330 mt76 sources and all 31 component mappings. Source lock:
  `f7f843ff9f6580a2903fe8e716069728fa454ad13001f54e4507e40e6fd924fe`.
- Source-bound caller receipt `target-q3/result.json`, SHA
  `1517bcfb7767f6a86a578872a54fcbef9cd19279f500962330c07f0f164ed477`,
  passes 1090 cases/seven compiled intended-assertion controls. Geometry and
  ASan/UBSan/leak detection are unchanged: 1040 optional-provider cases and
  50 modeled-owned-provider cases, not joint kernel execution.
- All 142 observer/tooling/inventory/phase units pass, zero skips. Ten new phase
  controller checks cover unchanged inspections, phase identity, failed phases,
  command/log drift, identical symbol replay and the non-renewing deadline.

## Bounded Build Changes

`test_rro_reset_phased_modules.py` transforms only nested make dispatch and
exclusive dependency-symbol creation in the original inspector. All other AST
assertions remain unchanged and rerun before/after the compiler phases. A phase
is replayed only with exact command/log hashes and a successful compiler result.
Python execs timeout/make, removing its resident heap during GCC. The three
compiler phases share one 1800-second clock, not a new deadline per phase.

The private copy of the prior failed auxiliary cache was checked against all
330 current sources, reconstructed with zero patch fuzz and namespace-isolated.
This is an incremental module build, not a fresh world build. Per-object GCC
garbage-collection settings change heap collection only, not optimizer/config.
It passed at 236 MiB; outputs occupy 185719792 bytes. The original kernel's
102685 and old mt76's 516 inventory entries remain unchanged. Old failed bytes
are preserved. No module was loaded and no image was built or promoted.

## Retained Failures And Resources

Preparation metadata assertions, a non-root verifier FD-permission failure,
the missing host-fixture READ_ONCE compile failure and the 192 MiB caller OOM
are retained. Fresh root verification retains the exact replay FD check and
passes. Fixture READ_ONCE is only a value read, not modeled kernel ordering.
The fresh caller run passes at 400 MiB with all sanitizer settings unchanged.
Both runs passed fresh full-service-cap RAM/storage preflight with the original
2 GiB margin; no native replay cap, bound, geometry or VM policy changed.

Controlled request/response I/O attributed the current-chat REA connection to
PID2825659/start15309995. Its session had no open target/analysis or retained
evidence. Exact UID/start/argv/no-child identity was rechecked before SIGTERM.
Other REA servers2015608/3717030 were untouched; this is not an age-based kill.

## Still Open

Both long replay cohorts retain their original PID/start/invocation and captured
input graphs; neither is restarted for observation timeout. Their partial traces
are not complete native verdicts. EVIDENCE records a fresh bounded trace snapshot.
Typed reset journal/transport bridging, actual RX-TID BA creation/late/reuse
authentication, hot CPU lifetime, production owner retirement/rearm and physical
drain/retirement remain. Host arrival is not BA epoch; MCU ACK is not a reuse
fence. Checked legacy selector3 remains denied. Current full image, cold/fault/
HIF2, actual hardware/client/performance/stability acceptance remain required.

Public EVIDENCE binds the private source/artifact manifest and preservation
versions. Private binaries, device backups, calibration, keys and recovery images
are not uploaded. Full NPU reverse engineering and implementation remains active.

## Later Authorized Cleanup

After the above result was sealed, the user authorized stopping the two older
REA servers. PID2825659 was already retired; exact UID/argv/start/no-child identity
of3717030 was rechecked and SIGTERM sent through a process descriptor. Both are
absent; the newer server was not signaled. Both firmware replay identities remain
unchanged. The earlier "untouched" statement is the pre-authorization snapshot.
`CLEANUP.json` binds this later receipt and the preserved pre-addendum report and
ledger. The original EVIDENCE/private manifest remain immutable; no new firmware,
source, module, image or hardware qualification is implied by this cleanup.
