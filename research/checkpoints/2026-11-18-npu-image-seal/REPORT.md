# Bind the built FIT to the replayed RV32 pair

The isolated world can pass its package and ABI checks without containing
the executable/data pair that passed a separate native-emulator run.
`tools/seal_npu_image.py` now closes that gap at offline publication. It
consumes the existing frozen world and replay outputs without changing either
producer. No production image was built or promoted in this checkpoint.
[Evidence](EVIDENCE.json).

## What the gate checks

- Pin the original start, terminal and world receipts independently. Follow the
  same invocation, boot, plan, controller, result and matrix digests. A live
  prefix, missing terminal, timeout or older boot/invocation is not a pass.
- Rehash all 345 retained replay inputs against the independently frozen world
  inputs. Check all three transcript orders and final broker, journal, prefix
  and summary identities, plus four full-memory comparison records at their
  expected positions in each profile. The complete recipe is 6,421 + 6,421 +
  6,419 positive RPCs. This checks stored evidence; it does not rerun emulation.
- Bind the exact completed isolated-world receipt to its clean snapshot, the
  actual independent image-check file, the source lock and four linked modules.
  Inspect a byte-for-byte copy of the FIT, following its declared default, and
  extract only the four packaged modules and three NPU files from that
  SquashFS. Check their bytes against the world receipt and the replayed pair.
  The packaged manifest must be internally valid and match the world manifest
  pin, but it need not byte-match the replay manifest's build-path metadata.
- Publish the inspected bytes by SHA-256 into a **new** private candidate
  directory. The FIT and receipt are read-only. No existing name or link is
  replaced. A directory lacking its final `receipt.json` is incomplete and is
  not an accepted candidate. Nothing is copied to a router or to a release.

This is artifact integrity and emulator-to-image binding, not signature trust,
boot, physical SRAM/DMA/IRQ, MCU acceptance, BA reuse, or a flash authorization.

## Evidence

The expanded 24-module host suite passed 264 tests with no skips, including
14 new seal tests. Controls cover the other invocation, wrong pin, transcript
order or incomplete memory schedule, changed final state, absent image
verification, probe-only success, altered FIT bytes, replay payload mismatch,
symlinked member, existing candidate name and interruption before publication.

- The real CLI refused the original invocation while its terminal receipt was
  absent, without creating any candidate. The independent profile reader
  verified the original profile 0 transcript and all 6,421 ordered RPCs.
- Protected FIT `a3f1d04b` and prepared FIT `978f9ddd` both differ from the
  replay in **both** CODE and DATA. Their selected SquashFS files were read
  directly and their original image hashes remained unchanged.
- A disposable nonbootable FIT contained the actual replay CODE/DATA, a
  different object-path field in the manifest, a placeholder kernel, and four
  placeholder modules. Extraction and the production raw-pair validator
  passed. It never entered the candidate store. The first fixture preparation
  timed out in host mksquashfs at a 256 MiB address-space cap. A bounded retry
  with one allocator arena and a smaller stack completed at the same cap.
  Both temporary directories were removed; no firmware or replay limits changed.

## Handoff after both gates pass

The original invocation `61e2d7b8` was still advancing with all 345 inputs
intact. Profile 1 had 2,874 positive records at the saved check; that is a
prefix, not a finished profile or three-profile result. Do not start a
competing compiler or use the earlier incomplete replay.

After the exact terminal pass, use the frozen snapshot `3d166089` for a
fresh isolated world with the combined producer `b5af9591`. Recheck RAM,
actual backing volumes and the exclusive writer lock first. Once that
world has passed, run the following from canonical WSL as the workspace user,
with independent expected pins from the verified receipts:

```sh
python3 -B tools/seal_npu_image.py --name REPLACE_WITH_FRESH_CANDIDATE_NAME \
  --snapshot .local/npu-validation-capsules/world-txp-20261118-a/receipt.json \
  --start research/checkpoints/2026-11-18-npu-txp-current-target/RV32-STARTED.json \
  --start-sha256 7742f7d08849a7d238b72367d45a9a161a3aea017826b044eb9662871c87fcff \
  --terminal .local/npu-rv32-fresh-20261118/terminal.json --terminal-sha256 EXPECTED_TERMINAL_SHA256 \
  --world-result NEW_ISOLATED_WORLD_RESULT --world-sha256 EXPECTED_WORLD_SHA256
```

Allow scratch space on the actual D: backing volume for the verified copy,
temporary FIT components and selected extraction. Use the existing storage
budget wrapper and a fresh local budget receipt. A sealed candidate would
still need separately authorized board, recovery and real-client validation.
Private controls are in `.local/npu-image-seal-20261118/`.
