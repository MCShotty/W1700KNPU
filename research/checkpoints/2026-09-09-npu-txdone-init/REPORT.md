# Checked Cold TXDONE Initialization

Date: 2026-09-09. Status: compiled and native-instruction-tested emulator
candidate, **unpromoted**. This advances callback failure handling and a
startup dependency; it does not establish complete NPU boot, recovery or parity.
Active work remains NPU-only codebase work with physical testing deferred.

## Native Findings

The pinned original RV32 instructions reproduce these behaviors:

- `0x8400fe34` loads the header/count and invokes selector dispatch
  `0x8400dd82`, then returns 1 regardless of the selected helper's result.
- TXDONE initializer `0x8400b432` logs counts outside 1..512 but continues.
  Count 0 still resets SKB state and publishes its legacy ready byte; count
  513 writes a 513th 16-byte descriptor. These are supplied-input native
  counterexamples, not observations of a live host sending those counts.
- ID exhaustion after 0 or 17 descriptors returns from the initializer
  without ready publication, yet the outer callback still returns 1. The
  already consumed IDs and written descriptors remain committed.
- Bufid pop `0x84004d80` ignores lock 28's failed ownership result. SKB reset
  `0x840049f0` reads but ignores lock 19's owner and ignores lock 20's result.
  Each can perform protected work and release ownership it did not acquire.
- At `0x84004b08`, SKB reset reads the next temporary halfword before checking
  the gathered-ID bound at `0x84004b10`. The native fixture gathers 2,048 IDs
  into a 4 KiB allocation but executes 8,192 halfword reads, spanning 16 KiB.
  The extra 12 KiB crosses that logical allocation into other mapped heap
  storage. This is not a demonstrated physical unmapped-memory access.

Static motivation: TX workers at `0x8400ec48` and `0x8400d0ae` depend on legacy
TXDONE-ready state and a separate mode flag. This pass does not fabricate the
mode, execute restricted initialization or claim their full post-gate startup.

Source evidence is the existing Ghidra export at
`research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt`:
SKB reset begins at line 10066, bufid pop at 10584, TXDONE at 22215, and its
wrapper at 33074. Original instructions, rather than the decompilation alone,
are executed by the tests. Input hashes are recorded in `txdone-init.json`.

## Implementation

New files are `tests/npu/txdone-init-emulation.c`, its `.S`/`.ld` companions,
and `tests/npu/test_txdone_init.py`. Six four-byte detours apply only to the
in-memory emulator image:

| Native Site | Role |
| --- | --- |
| `0x8400fe34` | Select and validate cold API1/selector10; private 12-byte snapshot; propagate failure |
| `0x84004d92` | Check owned lock 28 and bounded queue/packet ID before pop mutation |
| `0x84004a28` | Acquire and verify SKB lock 19 through the original lock helper |
| `0x84004a3a` | Verify lock 20 and selected SKB/descriptor layout before reset |
| `0x84004b08` | Check the gathered count before the temporary ID load |
| `0x8400b546` | On helper fault, unwind before index clear and legacy ready publication |

The outer wrapper selects only low-nibble selector 10 and requires exact
header `0x1a`, API 1, count 1..512, coordinator hart, completed bootstrap,
closed admission and epoch-1 parked state for all eight harts. Prior fault,
prepared/released/armed state, nested active count, prior legacy readiness,
wrong lock IDs, wrong packet base and selected descriptor-address failures
are rejected before callback mutation. It checks an aligned 8 KiB descriptor
address span against the normalized reserved-memory plan; that is not proof
that the host actually allocated the span.

Bufid checks execute only when the saved caller is TXDONE (`0x8400b4e4`),
with lock 28 owned. They bound head/tail, the full pool span and the selected
ID's packet extent. Empty-queue statistics retain native behavior. Failed
ownership never releases; invalid metadata after successful ownership releases
once without advancing the queue. Other callers keep their original behavior.

SKB checks are similarly scoped to the TXDONE return site (`0x8400b546`).
Denied lock 19 unwinds without requesting 20; denied 20 releases only owned
19. Both owned locks precede checks of capacity, temporary/queue spans,
TX-check alias, fixed TX ring pointers and all 2,048 TX packet IDs. IDs must
be aligned, in range and unique. Invalid checked layout releases 20 then 19
before fault publication, without the native reset. A stack bitmap is used;
the component has no data or BSS section.

Selected runtime failures retain partial descriptors, consumed IDs and active
ownership. Admission/barrier fault is latched; no rollback, token reclamation,
new generation or resource-release authorization is invented. The native
callback returns 0, and the directly exercised original IRQ handler reports
failure flags 3 rather than success flags 7. That handler is invoked explicitly
as a component test: the installed strict mailbox still rejects this API.

## Verification

The combined default run and byte-identical `--check` replay pass:

- 62 native cases: eight original counterexamples/controls and 54 corrected
  cases, comprising six successful, 24 rejected and 24 retained-partial cases.
  The matrix includes counts 1/2/511/512, invalid counts, exhaustion, first/
  later owner denial, malformed selected metadata, duplicate/out-of-range TX
  IDs, protocol-state rejection, private-count mutation and four original IRQ
  entry cases. The JSON names each input and expected outcome.
- Each case compares all 856,064 bytes across local SRAM, heap, L2, host ring
  and TX-check storage, plus exact memory-write byte sets and ordered lock
  requests/releases. A nonzero index sentinel proves failures do not silently
  clear the index. Successful ready publication is the final observed memory
  write; selected failed/rejected cases make no ready write.
- Corrected success reads exactly 2,048 distinct temporary halfwords at
  `0x3e816020` through `0x3e81701e`, versus the original 8,192. Full SKB/queue
  output remains equal to the independent native-layout oracle. A normal
  512-descriptor call requests/releases lock 28 512 times and 19/20 once each.
  The lowest observed SP is `0x84020f20`, 3,808 bytes below its entry value,
  inside the 16 KiB test stack. Entry SP and disabled MIE are preserved.
- Eight compiled/installation mutations are detected: removed count bound,
  private snapshot, callback failure propagation, bufid ownership, lock 19,
  lock 20, temporary-read bound and failed-publication guard. Each has a named
  behavioral assertion witness, not a compiler failure or observation timeout.
- Four integration controls pass: strict API1/selector10 rejection without
  callback or SRAM mutation; native RX selectors 0 and 2 unchanged before/
  after all six detours; and all 37 combined detours installed before reset.
  All eight harts reach their retained first gates, with no H7 bridge
  allocation, legacy ready, drain, release or arm. This does not grant cold
  initialization permission beyond the existing fixture contract.
- Four missing-model controls stop at the expected boundary: owner 28/19/20
  reads at `0x840064f4`, and the first attempted write to descriptor 512 with
  only 511 entries backed, at `0x57001ff4` from `0x8400b4b6`. The latter is the
  descriptor's second word, written first by native code. These are emulator
  boundary failures, **not firmware validation or recovery of missing backing**.

Reached allocation, bufid, descriptor-gather and SKB-reset helpers execute
natively; entry counts are recorded. Substitutions during selected calls are
limited to diagnostic printing and hart-ID/CSR inputs. MMIO ownership, banked
PLIC, host publication, chip inputs and startup timing remain explicit models.

The original candidate ELF is unchanged. The new sidecar contains 1,738 text
bytes at `0x84052000`, inside a separate 8 KiB emulator reservation. Linked
section and instruction inspection verify the detours, continuations, request
snapshot, ownership branches and temporary-read guard. This is not production
placement or a packaged firmware binary.

## Reproduction

From the canonical WSL checkout:

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_txdone_init.py
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_txdone_init.py --check
```

The receipt binds 83 inputs before/after, including imported harnesses, NPU
sources, linker scripts, the original candidate, Ghidra export and unchanged
source-lock/packaged patch authority. Build outputs and generated mutants stay
in ignored `.local/npu-txdone-init/`; no patched firmware image is emitted.
All 73 inputs from the preceding checked-startup allocator receipt were also
rehashed against the current worktree and remain unchanged. Historical receipts
are retained rather than overwritten by expanded input inventories.

- Sidecar ELF SHA256: `b28baccbbd13be6eeba0db61d34051081316cd4bc280200423c2dcf72a99b5a0`.
- Text SHA256: `fdb95687c93119835b3bf822998b4ac6b6867e8423e5bd1b732c4a28b0f0191d`.
- Receipt SHA256: `381af3635f6ebd739119783e00441b2057100600c385fd33d2cff2a1ab2e0be1`.

Development-only failures were confined to the observer: the inherited
three-second call budget was too short with detailed tracing; the existing
3M-instruction/60-second callback bound completes without instruction changes.
A control used the wrong result key, and the short-ring control initially
expected descriptor word 0 rather than native code's first write to word 1.
Both assertions were corrected against the actual helper/trace. None counts
as a detected firmware defect or a passing regression result.

Scoped whitespace checks pass for the five updated documentation files and
six new source/receipt/report files. Repository-wide `git diff --check` still
flags context/whitespace lines in the existing cumulative OpenWrt/LuCI patch
artifacts. Their hashes are unchanged; unrelated patch content was not edited.

## Remaining Work

- Do not open strict command admission yet. The component assumes a readable,
  caller-owned request, immutable boot/global/descriptor state and independent
  containment of previous users. Software parked bits are not physical proof.
- Establish actual host-ring backing, complete allocation provenance/non-overlap
  and all remaining global/statistics pointers. Coarse heap spans and selected
  metadata controls are not validation of every arbitrary corrupted state.
- Prove concurrent fault/publication and producer ownership, hardware lock
  acquisition/release, DMA/cache visibility and real drains. The successful
  last-write assertion covers serialized cases, not every asynchronous race.
- Complete other callbacks and post-gate workers, partial-attachment retention,
  full memory budgeting, host integration and recovery/removal before an active
  NPU image or any stock-parity claim. RX fallback preservation here does not
  correct its separate native ownership/error boundaries.
- The INODE-provider correction and native DESC5/6/7/8 operations remain
  restricted and were not retried or rerouted. No mode flag was fabricated to
  bypass that gap.

All four trackers and the NPU README are updated. No source-lock/packaged
patch/overlay change, image/flash, router/Wi-Fi/physical test, subagent,
protected-data change or Git publication occurred in this pass. The full goal
remains active and incomplete.
