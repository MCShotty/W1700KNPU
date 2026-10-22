# Lossless Replay Observer Journal

This repairs a measured replay-tool memory-growth path without reducing native
geometry, guards, checkpoint coverage or instruction/time limits. It is not a
full cold-caller verdict, retained RRO implementation or physical NPU acceptance.

## Measured Growth

The old default/HIF2 service remains terminal `oom-kill`, not running. Its exact
victim/allocation cause is unavailable; do not attribute the entire historical
OOM exclusively to this finding. Both old prefixes reached INODE0 after passing
PCIe-tail0/1/2, without final verdicts. Original outputs and capsule are retained.

New single-process diagnostics restore the unchanged hash-bound old prefix in
its original source namespace. Each is capped at768MiB/no swap, with a declared
50,000-observer-event/120-second diagnostic boundary. Existing native3M/60M-us
per-engine limits and all checkpoint PCs remain unchanged. These cuts are NOT
passed native commands. No original INODE store is reached at this sample.

The baseline grows to50,000 event dictionaries,49,975 of them `paused`; MMIO
stays23, request reads83 and CSR-event count0. This is consistent with
`Installation.record` appending every checkpoint pause to a Python list. The
full INODE path can repeat those checkpoints far beyond this sample.

## Implemented Tool Change

`native_event_journal.py` retains every logical event. SQLite stores completed
runs of identical JSON fields with an exact integer step progression; each
stream keeps only one pending run in Python. Field/type/progression changes
start a new run. Indexes, negative indexes, iteration and lazy slice views
reconstruct exact records. No sampling, dropped records or guest writes occur.
Completed runs have integrity digests; SQLite's cache is limited. The default
64MiB database cap is a file-growth bound, not a disk reservation. A full or
failed database poisons the journal: no fallback or successful finish is allowed.
Unfinished transactions/tails are not crash-complete evidence.

The existing caller runner accepts explicit `--event-journal`; default list
behavior remains. The option is wired through the actual factory and records
the journal descriptor/hash in the native result inputs. Logs are finalized at
mailbox boundaries and closed by the caller. This adds observer storage only,
not admission, retirement or a physical operation. Full fresh replay with this
option still needs a frozen source/capacity/RAM-budgeted controlled launch.

## Exact Bounded A/B

Final comparison uses baseline profile-q5 and final-journal profile-q7. Their
request, cut, event digest, checkpoint/read/CSR/callback counts, all33 mapped
memory regions and49 selected architectural registers are equal. Reading the
final database back reproduces all50,000 logical events and the same digest.
Those50,000 events occupy26 runs; the journal database is32,768 bytes, also
holding all23 MMIO observations. RSS at the cut is88,512KiB versus76,156KiB.
These are observations at this prefix, not a global peak-memory bound.

The initial raw CPU-context hash comparison correctly failed. Investigation
retains both raw contexts and compiles the actual upstream `uc_context`
declaration against the installed SDK: `last_block` is the8-byte host pointer
at offset24; architecture data starts at40. Differences are confined to that
host field. ALL remaining bytes, including the complete928-byte architecture
payload, match. No context file or restoration identity check was rewritten.
See the [Unicorn2.1.4 context declaration](https://github.com/unicorn-engine/unicorn/blob/2.1.4/include/uc_priv.h)
and its [RV32 context-size definition](https://github.com/unicorn-engine/unicorn/blob/2.1.4/qemu/target/riscv/unicorn.c).

`ab-final-q1.json` retains the compiled layout, raw differing offsets, exact
comparisons and final module hash. Prior profile/failed-wrapper attempts remain
separate, not overwritten or promoted into full native proof. Fresh D/C host
and native-ext4 observations cover final profile-q5/q7 budgets; profile-q3's
small preliminary run reused the earlier budget and is not the final A/B authority.

## Tests And Remaining Scope

All50 observer/oracle/factory/prefix units pass, zero skips. This includes an
exact million-event reconstruction/digest, lazy views, type and integer bounds,
independent streams, append snapshots, corruption/gap controls, read-only reopen,
exclusive paths and poisoned storage exhaustion. All56 build-tool units pass.
These are not hardware, complete original startup or full-caller tests.

The full objective remains active. Next freeze the observer-integrated current
caller, validate RAM and backing storage, then run complete default/HIF2 scopes
nonconcurrently without lowering coverage. Continue full cold faults/setup,
retained RRO extents/identity/generation/order/handoff/errors/late completion,
reset/IRQ/DMA drain/retirement, hot paths, whole-stack and physical/client proof.
The long original replays have NOT been restarted by this work.

Firmware, source-lockcb035741, raw pair4e43/a282, offline imagea3f1d04b and
protected images are unchanged. No flash, router access, module load, global
policy change, swap change or subagents. `EVIDENCE.json` binds the final seal,
old capsule preservation and the actual, separately scoped observations.
