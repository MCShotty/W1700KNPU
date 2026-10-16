# Original-Path Validation Copy

## Why This Exists

Native replay captures bind producing source and artifacts by hash. Changing
main during a long canonical replay must not invalidate its receipt or produce
a source-drift exception. The new runner makes independent, hash-checked copies
of tracked source, declared passing-receipt dependencies, selected captures,
the existing Python dependency directory and explicit extra runtime inputs.
It is a frozen validation artifact, not another development branch or worktree.

`tools/npu_validation_capsule.py run` requires WSL root only to create a private
mount namespace and bind the copied root at `/home/captain/W1700KNPU`. It checks
that the namespace differs, makes mount propagation private, checks the bound
inode and drops supplementary groups/gid/uid to captain before executing the
original test. The parent verifies its mount namespace and project inode after
child completion. The original JSON paths and existing hash guards are retained.

## Actual Results

- `tail-v1` preserved inputs but failed its first replay before native execution:
  the bootstrap fixture also needs the DTB outside the supplied receipt maps.
  Its failed envelope and copied inputs remain unchanged; it is not promoted.
- `tail-v2` explicitly includes that DTB and all18 then-complete tail fault
  receipts. Its preservation receipt binds3320 files/633122048 bytes and
  source commit37ee4e3a88402127360f7a44e89983eeb56b35d2, SHA256
  `24b9d075a9adb59eb4667c1065721a7e821c90475929d5bbeb733e006cc76f08`.
- `smoke-tail2` passes the actual original stage2 callback-slot fault from a
  strict restored prefix. It executes no original stores,as required for that
  entry denial. This is a diagnostic restore,not a fresh caller or boot.
- `smoke-raw` passes all six original raw boot controls and strict cached
  revalidation of the copied actual-caller/full512/all-eight-fault evidence.
  The cached nominal result remains a result of its original fresh caller.
- Both execution envelopes report returncode0 and parent mount unchanged.
  `hif2-caller-q1` starts a separate fresh actual provider/caller inside the copy;
  no terminal verdict has been observed yet. Original canonical long jobs were
  subsequently stopped deliberately for execution isolation,not counted as
  passes. Their731 terminal files are hash-preserved in original-migration-q1.
  Fresh HIF2/full36 tail continuation runs remain in this frozen candidate.
- Five copy/path/hash controls pass,including source drift,escapes,independent
  read-only copies and refusal to overwrite. All185 selected units pass.

Local evidence is under `.local/npu-validation-capsules/tail-v2/`; native output
is physically inside its `root/.local/` subtree. The unchanged canonical path
shown inside a test is namespace-local,not evidence that it used newer main.
After main changed to the412-byte journal,six live process source views were
read through /proc/PID/root. All match the frozen candidate and differ from
main;live-isolation-q1.json records this actual isolation check. The frozen
404-byte cohort's results never qualify the changed journal or later code.

## Isolated CSR Reader

`tests/npu/npu_csr_sampler.py` is not imported by current NPU observers. It uses
the already-loaded Unicorn2.1.4 `uc_reg_read_batch` C API with preallocated
storage. Its private Python engine-handle bridge is explicitly Linux/RV32/
Python-binding/C-version/signature/handle/thread pinned. Every invocation reads
fresh MSTATUS/MIE/MTVEC; it does not cache values or write guest state.

Eight isolated controls pass,including compiled CSR instruction transcripts,
an injected host write,context restoration,memory/GPR invariance and error cases.
The first stronger fixture used an MIE bit masked by the actual CSR instruction
and failed its final-value expectation. Its driver/failure remain preserved;
the corrected machine-external-bit fixture independently passes. Scalar and
batch readers agreed even in the failed fixture; it was not a native NPU pass.

An alternating-order three-by50k host-read microbenchmark is retained at
`.local/npu-csr-sampler/microbench-q1.json`,with exact driver/helper/test/library
hashes. Batched reads are faster in those samples. This is not a whole-emulation
speedup,physical throughput result or permission to skip observer reads.

Jev checked four narrow scope claims: old-copy validation cannot qualify later
main changes (contradicted .97); original-path/no-waiver/unchanged-parent smoke
scope supported .91; restored fault is fresh full caller contradicted1; whole
NPU/hardware speedup not established1. Raw distributions/confidence remain in
`jev-scope-q1.result.json`. These are semantic checks,not runtime proof.

## Limits

The host interpreter,compiler and system libraries remain external. File modes
and hashes are evidence preservation,not an adversarial sandbox or a complete
portable execution environment. The full36 tail fault matrix,HIF2 qualification,
checked INODE/IRQ/hot/workers,complete stack/physical DMA/cache/exclusion/drains,
lifecycle/reset/removal/rearm/recovery and actual-image/client gates remain open.
FIT978f9ddd is unchanged and unflashed. No hardware or subagents were used.
