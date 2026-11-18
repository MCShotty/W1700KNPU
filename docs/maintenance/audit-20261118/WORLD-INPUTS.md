# Current source, image-input and orphan audit

Continuation of the [workspace audit](REPORT.md) and [storage follow-up](FOLLOWUP.md).
The code, tests and frozen inputs below are from clean main `28abea8` on
Linux 6.18.52 target sources. This is not a new world build, router boot, flash
or client test. [Selected machine-readable evidence](WORLD-INPUTS.json).

## Two defects reproduced and fixed

- The capsule builder read entire archives into a Python bytes object. With
  the same 64 MiB address-space limit and 656,677,324-byte real cache archive,
  its old hash function raised `MemoryError`; the streaming implementation
  returned the declared SHA-256. The world runner already streamed file hashes.
  Both validation tools now refuse optimized Python before assertions can be
  stripped from their checks, including when imported by another launcher.
- A successful module compilation records the prepared sysupgrade as an
  observed input. A world replaces that path. Looking up original inputs
  through the build overlay therefore rejects the producer before inspecting
  the new image. The runner now binds a second, read-only view of the same
  snapshot; producer inputs and linked modules are read there. The new FIT,
  packaged modules and packaging tool are still read from the build being tested.
- The production namespace probe passed. In a second private mount using the
  same mount layout, replacing the output name reproduced the old failure on
  that specific input. The independent view verified all 420 original inputs
  and four linked modules. The real FIT comparison then correctly rejected all
  four packaged modules in prepared image `978f9ddd`. Its selected DTB named
  the Gemtek W1700K. The host FIT, namespaces and frozen inputs remained
  unchanged; the temporary overlays were removed. No compiler was launched by
  this probe. The first admission check declined to start for insufficient
  host RAM; the successful probe used the original limits and a fresh reading.

## Frozen inputs

Private capsule: `.local/npu-validation-capsules/world-txp-20261118-a/receipt.json`,
SHA-256 `3d166089dbb5a89650521a1d7331f8e2ce967472ed67ed1eebe0af50362caff3`.
It binds the current producer `b5af9591`, all 345 replay-plan inputs, the
linker, private bubblewrap and the 3,774-file offline download cache. The
previous capsule supplies storage, not authority: 6,518 matching read-only
files share inodes, 378 files were copied (18,093,943 payload bytes).
All 6,896 files were checked. The logical total is 3,070,306,025 bytes.
Hardlinks are not independent backups. The prepared OpenWrt lower tree,
external host tools and eventual build still need their normal world checks.
The snapshot used a capped D: job, not the replay's C: writer or output path.

## Integrity and cleanup

- At the code commit, 2,555 tracked files were present; 952 tracked JSON files
  parsed; 147 local guide links resolved. Across 162 checkpoint directories,
  18 explicit report digest bindings and all 1,329 artifact declarations in
  the 11 private/retained maps matched. Four historical helper plans still
  resolve to their exact inputs using preserved read-only copies where needed.
- All 127 migration entries, 31 R1 and 82 rollback checksums matched. All 18
  archive parts and three reconstructed stream digests matched without restoring
  a file. The expanded 22-module host suite ran 236 tests with no skips.
- Git full integrity verification passed. Both old topic tips were ancestors of
  main; no prunable worktree or packed loose duplicate was found. All 41 capsule
  directories had receipts. Left 22 dangling blobs and four dangling trees
  alone: an object without a ref is not proof its contents are disposable.
- Two ignored CPython caches reproduced byte-for-byte and had no reference
  in the checked 4,834 evidence records. Removed only those two files and the
  two resulting empty directories. A root descriptor scan found no remaining
  handles to either deleted file; the initial `fuser --` usage error was not
  counted as evidence. The two files used **36,864 allocated file bytes**, in
  addition to the earlier 1.75 GiB guest cleanup. No host free-space claim.
  Left the old comparison bytecode whose source is missing, a descriptor
  cache whose source now differs, the installed solver, Ghidra projects,
  device backups, recovery images and failed-run evidence intact.

## Replay and next check

Original invocation `61e2d7b8caed4f76bd9b5e61c55b02db` advanced while the
audit ran. All 345 live and retained inputs rehashed. Independently verified
its completed profile 0: 6,421 ordered positive RPCs and journal comparisons,
2,179 extent comparisons, four full-memory comparisons, final broker/journal
and transcript hashes. At the saved observation, profile 1 had started with
141 positive records. No earlier profile was reused. MCU results here are
modeled; there is **no three-profile terminal pass or physical acceptance**.

Observe this exact invocation. Before a world build, verify the terminal
outcome, the frozen receipt, space, RAM and the exclusive C: writer lock.
Use the combined producer and compare the new image's actual CODE/DATA with
the replayed pair independently. Board/client work still requires separate
authorization and a connection. Detailed local receipts are in
`.local/audit-world-inputs-20261118/`; no binary or device backup was published.
