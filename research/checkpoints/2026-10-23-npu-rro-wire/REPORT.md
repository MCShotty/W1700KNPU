# Identity-Bearing RRO Transport

Status: integrated experimental source, passing host/module/binary checks;
full raw-pair native replay is still running. The full NPU objective is open.
Base commit: `c426a0dd585741f50a319500f9446161ddc6eeac`.

## Implementation

The dedicated 256-byte LE protocol carries full provider/endpoint/boot/nonce/
epoch identity, profile, operation and control sequence. Publication includes
ordinal, journal ticket, selector and all four words. Reset messages include
session/generation/ticket. Only reply tag/status may change. Exact echo is
correlation, not cryptographic authentication or physical MCU evidence.

Typed provider OPEN/enrollment/publication/hardware/closing now connect the
retained host and native journals. The control mutex returns the exact accepted
serial; a separate RRO chain extends the immutable TX allocation serial without
bypassing late backing/handle/geometry/identity validation. Legacy scalar RRO
selectors0/1/3 remain denied. Closing grants no join, drain or free authority.

Raw pair ABI2 contains21 components/168 hooks and30588 zero-filled session bytes
inside CODE. DATA still ends at0x6480; V2 control remains80 bytes/capabilities0x27.
The current kernel rejects ABI1 pairs. Do not mix old images with these modules.
Current pair CODE SHA256: `e6bc914ccc087e963a431279fc5759006e7449183da63b97a4c4f9770ae6e525`.
DATA SHA256: `ad905cb06b54b4f3f84308895c8de1bf9296ccec799bc20ef5aef0d14e000512`.

## Completed Checks

| Scope | Result |
| --- | --- |
| Wire codec, host sanitizers | 27276 checks;3 compiled mutation controls |
| Joint client/codec/broker/journal/effect C | 19261 full-journal comparisons;5 controls |
| Actual provider/process bridges with host models | 456 cases;4 controls;387 native effects |
| Existing TX/RX/journal regressions | 223/12,168/7,5279/3 cases/controls |
| Complete selected RRO callers | 1090 cases;7 controls; optional and modeled-owned scopes remain distinct |
| Actual coherent sender/envelope gate | 330 assertions;256-byte tail and timeout retention; modeled peer |
| Target modules/source authority | 4 AArch64 links;31 mappings;5 kernel/329 mt76 sources; fuzz0 export |
| Normal RV32 archive | 26 exact members; bootstrap-v2 changes, other23 prior members identical |
| Raw pair/repeat/materializer | Identical CODE/DATA;22 test groups, zero skips |
| Source/build tooling | 116 tests, zero skips |

Module producer is `16ec7aabbfaf61759a271cc60dcee28f3042a6bcd1ee85499548170f0c4ecdc3`.
Source lock is `4ad342ffa7fe2031aca5525a1bf782ec771c6dd4babc670a51dafa73f922fbd2`.
The original prepared kernel tree is unchanged. MCU completions, references,
coherent backing and exclusion in host suites are models, not hardware proof.

## Native Run And Retained Failures

`w1700k-npu-rro-wire-native-q2.service` is running the complete new protocol plan:
all3 profiles/19261 RPCs,415 enrollments,387 publications and6150 reset IDs across
two generations, with complete journal/extent comparisons. OPEN,139 enrollments
and initial publication have executed on the actual raw pair. This is a partial
observation, not a completed native verdict. Instrumented timing is not device
timing. The new test's100M-instruction/60M-us per-RPC bounds do not alter the
original frozen replay's3M/60M-us bounds, geometry, checkpoints or memory margin.

Retained evidence includes the initial RAM refusal, fixture pointer-arithmetic
UBSan failure, stale TX mutation anchor, duplicate source-lock metadata mismatch
and retirement-control diagnostic failure. Native-q1 plus a focused actual-code
probe exposed an overly strict wrapper magic check: a wholly unused RRO object
incorrectly denied the optional non-RRO cold path. The wrapper now delegates to
complete-zero validation; partial/stale/failed/closing objects still deny. Both
the failed pair/run and corrected repeat pair survive. Structural image checks
alone did not reveal that behavioral defect. Jev checks are advisory, not proof.

## Preservation And Remaining Work

All6068 prior bindings/external1,2865 live-capsule files and14 protected project
image bindings/external1 rehash. Prior receipts are unchanged; old source bytes
survive independent snapshots and atomic hardlink detachment. The original
compact replay retains its PIDs/start ticks/invocation and advances CPU time.

Finish the new native verdict, full cold/fault/HIF2 and hot ownership, retained
BA/MCU/work-item generations, actual CPU join and independent physical retirement.
Then build/qualify a complete current image, verify FIT/DTB and boot-log
`Machine model: Gemtek W1700K`, and complete actual-client/performance/stability
acceptance. No full image, router access, flash or physical drain was performed.
Both long runs remain untouched; no full-project completion is claimed.
