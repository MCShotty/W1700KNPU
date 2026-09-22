# Checked Cold Allocator And Hart-7 Bridge Binding

2026-09-09. Status: native allocation behavior reconstructed; checked C core
and one bridge call-site binding implemented, compiled and tested. This is
unpromoted code, not packaged firmware or full NPU parity. Physical testing
is deferred. No router contact, Wi-Fi changes, subagents or flashing occurred.

## Native Contract

The pinned original RV32 getter at `0x84005200` selects dynamic definitions
and calls allocator `0x84004ff8`. The high table at `0x8401b224` contains six
definitions, and the low table at `0x8401cfc8` contains eighteen. Each row is
eight bytes: 16-bit type, 8-bit alignment tag, 8-bit reserved field and 32-bit
size. Tag zero selects 32-byte alignment; tag one selects 16-byte alignment.
Types below `0x81` select the low table. Fixed-L2 getter paths are separate
and are not replaced by this candidate.

Native allocation metadata begins at `0x3e901bcc`:

| Offset | Meaning |
| --- | --- |
| 0 | Lock ID, initialized to 18 |
| 4 | Native word preserved by the candidate |
| 8 | Cached entry count |
| 12 | Native word preserved by the candidate |
| 16 | Diagnostic allocation-attempt counter |
| 20 | Used heap bytes |
| 24 | 100 eight-byte entries: type, reserved halfword, address |

The 824-byte object ends at `0x3e901f04`, where other globals begin. The
modeled native heap is `[0x3e800000, 0x3e878000)`, or 480 KiB. Reset routine
`0x84005296`, getter, allocator and original lock acquire/release routines
`0x840064b4`/`0x8400651c` execute in the native comparisons. Register storage,
hart-ID and logging behavior retain the existing explicit emulator models.

Forty-eight comparisons cover fresh and cached lookup for all 24 pinned
dynamic types. Returned addresses and all 824 metadata bytes match the
independent checked arithmetic/state oracle for these valid calls.

## Original Counterexamples

Four instruction-level counterexamples are retained in `allocator-native.json`:

- A failed owner check does not stop allocation. Metadata changes and the
  original release MMIO write still occurs despite acquire returning failure.
- Requesting unknown type `0x80` after type 1 returns zero but caches that
  result and rewinds the used cursor to zero. A following type `0x8a` then
  receives the same heap base as type 1. This is a supplied invalid request,
  not proof that a normal production caller requests that type.
- The allocator checks the start, not the complete requested extent. After
  the six core-0 allocations and bridge type `0x81`, type 2 returns
  `0x3e8776e0` for 6,168 bytes. Its end is `0x3e878ef8`, 3,832 bytes beyond
  the declared heap end. Only typed allocation calls execute in this proof;
  no native RX callback, packet write or out-of-bounds DMA is demonstrated.
- A deliberately corrupted count of 100 allows the next entry to overwrite
  globals at `0x3e901f04` and `0x3e901f08`. The supplied cache is invalid;
  this is not a reachable 100-entry cold sequence of the 24 pinned types.

These are original instruction results under the documented inputs. They
are not observed live W1700K failures or an external exploitability claim.

## Implemented Core

`firmware/npu/allocator.c/.h` provides `npu_allocator_allocate()` with a
status/address result, immutable layout and definition tables, and explicit
acquire/release callbacks. It implements:

- Bounded, unique definition validation, category/alignment/size checks and
  overflow-safe heap layout arithmetic before requesting the lock.
- No mutable allocation-metadata reads before a successful acquire. An
  ownership fence follows acquire, and no release follows denied ownership.
- Full validation of count, cursor and every occupied entry under the lock.
  Known types must be unique and have the exact native ordered/aligned
  allocation chain; malformed addresses, gaps and cursor rewinds are rejected.
- Full-extent and 100-entry checks before commit. Valid cached allocations
  remain available even when the heap or entry cache is full.
- Mutation-free rejected calls. Successful allocation writes the entry and
  cursor, increments the diagnostic counter and publishes count last, with
  an ownership fence before release. Unused native words are preserved.

Unsigned diagnostic-counter wrap matches the original valid allocation
behavior; it is not a lifecycle generation or reclamation authorization.
Tables must remain immutable and every metadata user must honor the same
lock. Fences do not establish physical grants, cache coherency, lock release
completion or containment. Those remain platform/caller contracts.

## Bridge Integration

`tests/npu/allocator-bridge-emulation.c` replaces only hart7's allocation call
at `0x84001486`, not the global getter or every allocation call:

| Call site | Original bytes/target | Candidate bytes/target |
| --- | --- | --- |
| `0x84001486` | `ef30b057` / `0x84005200` | `ef80b46b` / `0x8404a340` |

The test decodes the original JAL and verifies its destination and return
register before installing the new linked call. The binding accepts only
hart7/type `0x81`, disables local interrupts, rejects a prior barrier fault,
uses the original ROM tables/native state, and validates lock ID 18 before
calling the original hardware-lock routines. It checks both allocator status
and the barrier fault before returning to native bridge-base publication.

On failure, an I/O fence precedes the existing atomic barrier fault, then
hart7 holds permanently. There is no return to base publication, no lock
release on failed acquisition, no parked/ready claim and no automatic retry.
An external fault injected at successful unlock leaves the committed
allocation retained and holds before bridge publication; it does not roll
the allocation back. A later owner-ready register value cannot resume a hold.

Eight cases cover native cold state, denied owner, corrupted cursor, valid
but insufficient capacity, cached bridge reuse, invalid lock ID, a prior
fault and an external fault at unlock. The capacity prefix is created by
original allocator instructions, not solely by the arithmetic oracle.
All 32 KiB of local SRAM are compared with an independent expected image,
and all 480 KiB of modeled heap bytes remain unchanged. Acquire/release
MMIO counts and actual checked-core return values are asserted.

Coordinator STATUS reports fault 6 and parked mask 1 after a held failure;
successful cases reach the retained outer gate with mask `0x81`. Capability
bits remain 7, without physical reclaim/restart, and ready/drain/release/arm
remain zero. The earlier null-base/channel guards remain installed.

With all 29 detours and the original first gate retained, all eight actual
reset/prologue contexts park and repoll without any bridge or checked
allocator execution. This is one serialized banked-PLIC storage schedule,
not physical concurrency. Post-gate analysis omits the first hart7 gate only
in its isolated fixture; no drain, release, arm or cold-init permission is
fabricated to exercise the binding.

The RV32 bridge candidate has 1,042 text bytes at `0x8404a000`, followed by
two alignment bytes and 24 read-only bytes at `0x8404a414`, ending at
`0x8404a42c`. It uses the unchanged baseline candidate ELF for shared symbols.
This separate emulator reservation is not a production placement or image.

## Differential And Concurrency Tests

`test_allocator_protocol.py` compiles the same allocation C as a native
UBSan shared library and RV32IMAC ELF. Its 1,367 paired calls compare both
executions with a separate Python integer-arithmetic oracle, all 824 metadata
bytes, lock counts and the state snapshot observed at unlock. Coverage includes
all pinned types, seven cold-sequence prefixes, corrupt/capacity/invalid inputs,
state replacement at acquire, cached lookup after acquire, full-cache reuse,
alignment, counter wrap and 80 seeded 16-step definition/order sequences.

Eight mutation controls remove or weaken lock, extent, cache-capacity,
cursor, cached-address, alignment, read-order and count-bound checks. All
are detected in RV32 execution; unsafe mutants are not run as native C.
The count-bound control explicitly traps reads past the 824-byte object.
Its initial one-entry/count-101 fixture still rejected an unknown second
entry and therefore did not expose the removed bound. The corrected fixture
contains 100 valid entries before count 101, and detects the out-of-range read.
This was a test-fixture correction, not a firmware implementation finding.

`allocator-concurrency.c` runs eight pthread workers for 32,000 calls with
a real mutex under ASan/UBSan. It checks 100 unique allocations, stable cached
addresses, 3,200 total bytes, intact reserved words and three post-run checks
for full cache, full heap/cached reuse and denied ownership. Sanitizer failures
are fatal; the successful result has no stderr. This is host-thread concurrency
evidence, not an eight-hart hardware lock, DMA or cache test.

Both allocator runners' `--check` replays reproduce their full receipts
byte-for-byte. The protocol receipt binds six direct inputs; the native
integration receipt binds 67 current input files before and after execution.

The earlier bridge suite was rerun in a fresh process to
`regressions/bridge/native-startup.json`: 52 cases, seven mutation/installation
controls, four missing-model controls and its 28-detour retained-gate case
still pass. All non-provenance fields equal the historical receipt. Its
61 original input hashes also match; the only change is three additional
glob-discovered inputs: allocator C/header and bridge binding C. The historical
receipt is preserved, not overwritten. Its old whole-file `--check` now sees
the expanded input inventory, so the two complete JSON files are not identical.

## Remaining Work

- Global allocator integration remains open. Core0 and other native callers
  still use the original allocator. Each needs reviewed error propagation,
  retention and mailbox-safe failure behavior; a global NULL substitution or
  permanent core0 halt would not implement that contract. The checked hart7
  path cannot protect against an unchecked concurrent metadata writer.
- Reconcile the complete dynamic allocation budget and reachable consumers.
  The actual core0 sequence `[0x8a, 0x12, 0x1d, 1, 0x0b, 0x19]` consumes
  430,288 bytes. Bridge type `0x81` starts at `0x3e8690e0`, requests 58,879
  bytes and leaves the cursor at 489,183 bytes. The following type-2 request
  exceeds the declared capacity and is now rejected by the checked core.
  Rejecting it is not a functional implementation of all required consumers.
- Type `0x81`'s 58,879-byte definition still disagrees with the printed
  64 KiB bridge envelope. The actual hardware geometry/maximum consumer span
  is unproved; neither heap nor table has been resized on the print alone.
- Close physical lock ownership/release, fresh initialization, immutable-table
  lifetime, SRAM/code placement, cache coherence and bounded timer/channel
  semantics. This checkpoint is not global allocation ownership proof.
- Complete all-worker post-gate initialization and physical ingress/copy/PPE/
  tunnel/Wi-Fi containment before common reset/recovery/removal integration.
  Full host-adapter datapath and release acceptance remain incomplete.

The existing INODE-provider and native DESC5/6/7/8 restricted operations were
not retried or rerouted. This work executes the separate dynamic allocator
and hart7 bridge path. No packaged overlay, source-lock or cumulative patch
change was made; existing Wi-Fi changes and protected device data remain intact.

## Reproduction And Hashes

From the canonical WSL repository, with the existing pinned private firmware
inputs and local compiler/emulator dependencies:

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_allocator_protocol.py --check
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_allocator_native.py --check
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 -c 'import sys; import test_bridge_startup as m; m.OUT=m.ROOT/"research/checkpoints/2026-09-09-npu-allocator/regressions/bridge"; sys.argv=["test_bridge_startup.py", "--check"]; m.main()'
```

Omit `--check` to regenerate the allocator receipts. Generated shared objects,
mutants, RV32 ELFs and the pthread executable remain under ignored
`.local/npu-allocator/`; no patched firmware blob is emitted. Compiler commands
and individual case traces/hashes are recorded in the JSON receipts.

SHA256:

```text
allocator.c        797b502cb0d1d9f803934956122e459512433e7e83d10612200ae81d6c3110d8
allocator.h        922842faf3fccb7dd7d993a3e12fac5440c7d718d6ed470abe22ec7223fa8347
test binding       728cf85fd08c7641635c796d421a9e0e8686bc8bbbcc1fe2b8745d8c5b6425b2
test linker        ab6c13d09c0763fe64fc162c453c94bd38d197e0a26d24b9a8e66711d1c992c9
bridge binding     55c718588a515a916940388aa2f2df21c28c87cbb43285b2fb016e5402314a64
concurrency C      ce796acfb7ab22e7f754aaeefefb5aec6c3bf6d038847b5c8485788436d8a84d
protocol runner    a3c45894c299ea54b5fe182fb05c0086c5cfd053c6cf3d64d562b941e0f38b66
native runner      b0cb3896489be0eb07b35d90fcfce713882f1ce4b9a8ad7aeb6398ec6bdd4b91
protocol receipt   1ba7fd47b52a5fc46219c0414f4367cef94d1b096ac2905bc1b09f238109f530
native receipt     e1af13de42692f4b1130b5b2cd7bddc5a76a84cc84c39b056c956ad0ede9f222
bridge regression  c69a99c51fe530893113f2112903a6decf4eaf4df033a5fa2d5a319ddc1905f9
bridge ELF         6a07e4fe3669791edef614bf4071f7f7d469535c350d2fb7f9bd4ca063162304
baseline ELF       bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931
```

All four canonical trackers and the NPU candidate README record this work.
The full NPU reverse-engineering/implementation goal remains active and unmet.
