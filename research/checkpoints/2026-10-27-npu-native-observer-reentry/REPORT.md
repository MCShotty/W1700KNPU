# Native Observer Counter Reentry Qualification

Base: `32ae6139023e560c01d3f695a4d7e7354a4bfd06`, mainline, solo.
Private receipts: `.local/npu-observer-reentry-20261027` and C-backed
`.local/npu-build-scratch/native-c2/observer-reentry-*`.
`EVIDENCE.json` binds the published source, diagnostic inputs and receipts.

## Reproduced Failure

Four bounded probes compare the actual Python `Pair.block` with the retained
profile-6 native adapter. A custom numeric counter value replaces the current
counter, minimum, cached names, or the counter used by a later name. All four
produce a state mismatch. The probes deliberately keep old counters/names alive;
they demonstrate fidelity failures, not a heap use-after-free or firmware fault.

Six new mainline regressions also require Python's `__iadd__` protocol, the
original exception object and the reference's cache-clear `KeyError`. All six
fail against the old adapter. These are negative controls, not six passing tests.

## Mainline Fix

`tests/npu/native-read-api.c` preflights the examined block/name counter values.
Missing or exact Python-int values retain the existing path. A custom value
delegates the entire callback to the original before the native block increment.
The original then performs its own arithmetic and re-reads live state in order.
Host observer profile advances from 6 to 7; read API remains 2. The default Pair
is still the Python reference. No firmware, mt76, provider or kernel source changes.

This is a bounded custom-arithmetic fix, not a universal proof about arbitrary
class monkeypatches, reentrant handle accessors, key equality or object lifetime.
Future optimizations must continue testing dynamic state rather than assuming it
immutable. No counts, fresh stack reads, exact cache-miss checks or I/O/fault
checks are intentionally removed.

## Fresh Qualification

- Plain and UBSan: each 32 read/CSR plus 63 observer methods, zero skips/errors.
- Twenty independently compiled behavioral mutants: one intended assertion
  failure each, including separately omitting the block and name preflights.
- Actual raw finite run: equal complete transcripts for 19,517 instructions and
  40 memory regions, including registers, CSRs, memory hashes and observations.
- Tooling: 167 methods, zero skips/errors. This is not a fresh kernel replay.

## Timing And Profiling

The actual ordinary RV32 loop executes 400,000 blocks per timed run. Three old
and three current direct-gateway runs alternate order. Guest counts, minimum SP,
terminal PC and cached block keys match. Median wall times are old 548839600ns,
current 555230629ns, old/current ratio 0.9884894156298427. This is roughly unchanged,
not a speedup. The Python reference ran once at 1768116517ns, not three times.

Ubuntu's `linux-perf` and two required libraries were SHA-checked and privately
extracted, not installed globally. User-only `cpu-clock:u` sampling at 997Hz
records a four-million-block run with the current UBSan adapter. It reports zero
lost samples. Generic attribute lookup is the largest named entry at 10.03%;
`block_call` is 7.36%, tuple packing 1.18%, and the new preflight helper 0.73%.
These are self-sample shares of the bounded worker, including startup, without
call chains. They do not attribute the entire cost or diagnose full-q21's timeout.
The kernel sampling policy was not changed. Limits remain 10s for this loop.

## Preservation And Limits

All 294 original full-q21 input versions remain read-only and hash-correct.
Three live host input paths changed and have fresh source-bound build receipts.
Old full-recipe results are not relabeled current. The separate 438 target inputs
remain unchanged, so the qualified RXWI source/modules are not superseded.
Source lock `d55e71a3`, mt76 patch `5fa42f93`, kernel patch `aacc0ffc` stay.

Each new guarded phase retains 400MiB/no swap, a 128MiB C-output reserve, fresh
Windows/Linux backing and full-cap-plus-margin checks, and the existing C writer
lock. Existing failed receipts, old producing inputs and tracking bodies remain.
Two actual Jev batches are retained; the preliminary dynamic-counter answer
disagreed with direct source and reproduction. Tests, not that answer, determine
the observed contract. No model inference is treated as execution proof.
The later fidelity answers are uncertain (0.40/0.57); the narrow executable
tests and independently broken controls provide the covered runtime evidence.
Facts-q10's mode check incorrectly demanded 0444 for a retained 0555 executable;
that failure remains. Fresh q11 requires the exact recorded mode and no write
bits, and passes all retained/target checks. The missing q10 request produced
no Jev inference. No retained input permissions were changed to satisfy it.

Full-q21 is still terminal failed; no full retry or increased replay budget was
attempted. No router contact, module load, image build, flash, Wi-Fi change or
shutdown occurred. Ethernet stays disconnected at the user's request.

Next sample a representative publication before changing its hot path, then
requalify faithful timing and a fresh full recipe. Complete consumer containment/
physical drain, BA reuse/hot lifetime, current image/board and real-client
performance/stability acceptance remain open. The full NPU goal stays active.
