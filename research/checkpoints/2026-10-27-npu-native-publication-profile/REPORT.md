# Current Native Publication Profile

Base `c18c7dcd3a84fb5202d287cd042869612d4082d2`, mainline, solo. Host observer
profile 7/read API 2 and qualified UBSan adapter `79f91fc4` are unchanged.
Private cohort: `.local/npu-publication-profile-20261027`; C-backed results:
`.local/npu-build-scratch/native-c2/publication-profile-*`.

## Actual Native Result

Fresh profile-2 boot/prefix completes 1136899 tracked instructions in
38637348105ns. The probe checks OPEN and 137 ENROLL before its first PUBLISH.
All 139 positive RPCs/journal comparisons pass; all 141 canonical rows match
the retained reference except `wall_ns`. Complete broker, extent, DMA, SRAM and
code comparisons pass. All 309 declared inputs and the current adapter's
source/header/binary bindings are rechecked before publication.

First-publication wall time is **46864880212ns** under the unchanged 100-million
instruction/60-second RPC limit. Boot limits remain 3 million/10 seconds per run.
The publication records 7438798 blocks, 760661 metadata writes, 515 payload
reads, one mailbox veneer/binding each, table writes/reads 1/2, and extent
writes/readbacks **24576/24576**. No instruction, stack, I/O or fault checks were
intentionally removed. No guest code or checked operation body was edited.

This is a fresh passing first-publication subset, not a complete recipe or a
reproduction of publication 119. Original full-q21 remains terminal failed.
Neither a timeout fix nor a firmware logic defect is established.

## Scoped Sampling

The existing privately extracted perf starts with events disabled. A control
FIFO enables sampling immediately around `positive(PUBLISH)` and disables it
afterward. This includes parent request and broker/extent comparison work, not
just the `emu_start` call. Boot, enrollment and complete final DMA/SRAM/code
comparisons lie outside the enabled window.

Sampling uses main-task `cpu-clock:u`, 997Hz, explicit CLOCK_MONOTONIC, no
inheritance and no call chains. All **46693** sample timestamps fall inside the
acknowledged enable/disable bounds. Perf reports **zero lost samples**. The
independent half-second control yields 498 samples within its own bounds.
Kernel policy and global packages are unchanged.

The initial control-q2 fails before any firmware replay: the ACK reader expected
newline only. The actual protocol includes NUL, `61636b0a00`. Fresh q4 helpers
retain and verify that frame; control-q5 and publication-q6 pass. Failed inputs
and output remain untouched. There was no unchanged full-recipe retry.

## Measured Leads

Largest named self-sample entries include Python evaluation 8.48%, generic
attribute lookup 5.60%, Unicorn trace helper 5.14%, C `block_call` 1.99% and
`memory_vectorcall` 1.71%. These are sample shares, not causal cost assignments.
Without call chains they do not identify which Python callers account for the
evaluation samples, or establish the cause of the old publication-119 timeout.

The initial `memory_call` annotation reports no samples under that name. A fresh
analysis annotates the actual `memory_vectorcall` symbol; this is not evidence
that memory traffic or the observer's work was absent.

Current base registration calls `cpu.hook_add` for memory reads/writes. The
bound Unicorn Python callback then calls MemoryObserver with six arguments.
Unlike block callbacks, memory callbacks do not yet have a direct native hook
gateway. That boundary is the next testable optimization candidate, not an
implemented fix or a proven speedup.

## Preservation And Scope

All 438 target inputs and 294 read-only historical native versions rehash.
Source lock `d55e71a3`, mt76 patch `5fa42f93`, kernel patch `aacc0ffc`, and qualified
RXWI modules stay unchanged. Prior 95-method-per-build/20-control/167-tooling
qualification remains source-matched; those suites were not rerun here. No new
compiler, firmware, observer, driver or registration source change occurred.
`EVIDENCE.json` binds the new native/sampling/control/analyzer artifacts and six
tracking-body preservation records, not an archived complete runtime/toolchain.
Actual Jev scope/claim responses are retained as semantic checks, not proof.

Each guarded phase keeps 400MiB/no swap, a 128MiB C-output reserve, fresh host/
Linux backing observations, full-cap-plus-margin checks and the held C writer
lock. Native and dependent diagnostic jobs are terminal. No image build, module
load, router contact, flash, shutdown or Wi-Fi change occurred. Ethernet stays
disconnected at the user's request.

Next qualify a direct memory callback gateway at the original registration
position. Preserve all six arguments and signed values, default reference
behavior, dynamic metadata, fresh SP, I/O/fault checks, exception identity and
precedence, and callback retention/inflight unhook/GC/rollback. Require actual
guest trace identity and measured performance before a new complete recipe.
Full native, complete consumer containment/physical drain, BA reuse/hot lifetime,
current image/board and real-client performance/stability acceptance remain
open. The full NPU reverse-engineering and implementation goal stays active.
