# Exact Observer Cache And Fresh Full Native Replay

Goal-turn classification: **progress**. Full NPU implementation and acceptance
remain incomplete. This is an observer optimization, not a firmware shortcut.

## Change

The existing bounded cache already checked exact bytes once per unique native
block. It now also retains the fixed executable-range, forbidden-PC and hook-site
classification for that address/size. Code/layout/binding addresses are fixed
for a Pair. Every block still samples SP and updates the block/veneer/binding
counters, including repeated cache hits. Metadata write-region construction is
precomputed once. Dynamic owner, IRQ, address/size/value, readback and write-digest
checks remain on every applicable access. No block or memory hook was removed.

AST comparison permits changes only in Pair initialization, configure, block and
write_hook. All non-observer module code, effect/read/execute/mailbox methods,
instruction/time bounds, complete replay recipe and geometry are unchanged.

## Measured Evidence

Both variants boot the actual same ABI2 raw CODE/DATA pair and execute OPEN,
139 ENROLL and two PUBLISH requests against the same sanitizer-enabled C oracle.
All142 complete broker/journal comparisons per variant pass. Every transcript
field other than wall time matches: requests, replies, complete journal and broker
hashes, counters, SP low-water, MMIO and write digests. Full12MiB DMA, native SRAM,
executable readback and retained TX/RX backing checks pass and match.

Reference publications took56,775,835,146 and56,338,091,345ns; optimized took
39,655,485,012 and39,425,809,900ns, roughly30% less elapsed time in this sample.
Both variants use the same100M-instruction/60M-us bounds and400MiB cap. This
supplemental profile0 probe does not establish full native transport completion
or physical correctness. Cold provider publication/backing, IRQ entry and MCU
boundaries remain modeled.

Six AST-extracted observer units compare synthetic CPU/register/memory/parent
fixtures, rejection cases, cache limits, repeated sites, SP, region boundaries
and dynamic effects. Three Python mutation controls fail their intended checks.
The small modeled cache-cap case uses two entries, not a claim that16,384 unique
native blocks executed. Candidate units pass; installed-source observer plus all
116 tooling units pass together:122 tests,zero skips.

## Full Replay

Fresh `w1700k-npu-rro-observer-native-q3.service` runs the unchanged complete
three-profile recipe:19,261 positive RPCs/full journal comparisons,415 enrollments,
387 publications,6150 NPU resets and6150 modeled MCU begin/completion pairs over
two generations, plus original transport/identity/fault checks. Its first full
publication passes. The full result is pending; partial logs are not a verdict.
The captured input graph must remain unchanged while it runs.

No limit, observer coverage, guest swap, safety margin or global policy was
relaxed. The earlier q2 time-limit failure is retained, not restarted. The
original compact replay remains live with its original starts/invocation and
frozen capsule. Structured hash bookkeeping runs on Windows. An explicitly
budgeted8MiB native checksum worker preserves Linux case/symlink resolution,
avoiding a full guest Python analysis reservation. Full guest caps and host
storage/RAM are checked. No idle helper was terminated in this turn.

The first bookkeeping launch refused its full guest-cap margin check. That
failed script and receipt remain. The replacement reads live process/cgroup/RAM
state through UNC without spawning a guest inspection process; the same full-cap
threshold is still enforced before and after hashing. No margin is waived.
The first UNC variant could not read protected process environ files. That
failure is retained too; exact live PID/start/cgroup checks now bind the fresh
systemctl invocation baseline without reading process environments.
Direct Windows hashing also failed on a Linux linker symlink; Windows filename
case folding is unsuitable for this corpus. That failure remains. Hash bytes
are now read by the bounded native checksum worker, not Windows path resolution.
The first checksum worker completed successfully, but its collector combined
`--wait` with `RemainAfterExit=yes` and timed out awaiting deactivation. Only that
already-exited helper was deactivated. A new collector omits that combination;
the failed collector and all replay processes remain unchanged.

Firmware, source lock8222e0e7, raw pair e6bc914c/ad905cb0 and current module
producer b9e5003e are unchanged. This is neither a module rebuild nor a new full
image, promotion, flash or hardware/client acceptance. Real reset-worker retained
errors and late/reuse authentication, hot lifecycle, CPU join and independent
physical retirement remain required. Full cold/fault/HIF2/current-image/physical/
client/performance/stability scope remains open.

Private evidence: `.local/npu-rro-observer-20261023/`; full replay output:
`.local/npu-rro-wire-native-pair-20261023/native-q3/`. Read `EVIDENCE.json` for
the retained manifest and scoped receipt hashes. No device secrets are published.
