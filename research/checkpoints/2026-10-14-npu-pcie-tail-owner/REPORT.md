# Remaining PCIe Portable Owner

## Canonical Promotion - 2026-10-15

Source is now firmware/npu/cold-pcie-tail.c/.h in the normal22-object build;
fixtures, tests and all nine store trampolines are canonical tests/npu inputs.
Current host/RV32446/376, seven compiled mutants/sanitizers and42 stub-guard ABI
cases pass. Real native guard/history binding remains open. Current evidence is
in ../2026-10-15-npu-owner-promotion/REPORT.md. Staged paths and current-input
claims below describe the separately preserved historical producing cohort.

## Scope

This checkpoint implements the next original API0 selectors0/2/15 as a portable
one-shot owner. It does not bind their original stores, extend authenticated
caller admission, prove physical BAR aliases or establish hardware operation.
The full NPU reverse-engineering/implementation goal remains active.

Source is temporarily staged at .local/npu-pcie-tail-owner-20261014 while the
earlier actual-caller and native fault runs consume frozen source/test inputs.
It is intended for the normal archive and unified image, without a separate
experimental feature flag. Existing firmware README and consumed inputs were
not changed. The prior image FIT69c88ce9 remains unchanged and unflashed.

## Implementation

- The180-byte plan embeds the136-byte RX PCIe/DESC10 plan and independently
  finished44-byte TX plan. The256-byte owner retains stage/reservation/completion,
  possible/published effect counts, captured preimages and the complete plan.
- TX0+0x160 and TX2+0x110 supply the two PCIe operands. TX2 must match the
  retained HIF1/HIF2 profile, BAR/arena and full12-byte derived register extent.
  An incoming HIF flag is not used as an independent authority.
- Effects are the two pointer/index pairs followed by all five retained index
  stores. Literal independent test events cover all nine addresses/widths/values.
- Every operation requires live prior owners/final memory, exact plan/history
  and stage order. A reservation retains the possible effect before a store;
  exact readback precedes publication. Failure never resets earlier effects.
  There is no release/recycle/reset/retirement API.
- A focused initial probe showed prior PCIe state could change in a reader
  callback while first begin still succeeded. Prior TX/PCIe/plan snapshots now
  precede all reader callbacks and exact equality is checked afterward.

## Current Evidence

The local checkpoint .local/npu-pcie-tail-owner-20261014/checkpoint-q1.json has
SHA256 e2898dd50b2477efd04d6a4b4ad3b0b91aa57f3718e35a12d1111d5da69f5071.
It rechecks51 current input hashes and three receipt hashes:

| Receipt | Result | Scope |
| --- | --- | --- |
| host-q3/result.json |446 calls/376 controls, both HIF profiles | Compiled host C, whole logical/prior memory. |
| rv32-q2/result.json |446 compared calls/376 controls, both profiles | Exact normal-Os RV32 owner plus existing normal prior objects. |
| mutants-q3/result.json | All seven compile and fail behavioral assertions | Host-C mutation sensitivity, not original native mutants. |
| sanitize-build-q1.log / sanitize-run-q1.log | Terminal0 | ASan/UBSan/leak, both profiles and four reader-mutation cases. |

Controls cover dirty initial owner words, corrupted owner/plan/prior headers,
missing pointer/count/preimage reads, malformed selector/value/address/width,
stage order/replay, finish without publication, possible effects without a store,
wrong readback, late faults and mutation during each reader-bearing operation.
All prior fixture memory is compared; only the named injected mutation, fault
bit and explicit reader diagnostic counters may change in mutation controls.

The seven compiled faults remove prior-reader equality, admit active TX,
accept wrong store values, forget possible effects, select a wrong PCIe2
register, underflow the last index and finish before all stores. The initial
mutant prototype had an unused-parameter compile error; it was repaired and is
not counted as a killed mutant. Initial host-q1 also had the wrong expected
fixture arena, corrected from the actual prior fixture. Earlier receipt input
hashes are historical; only the current three sealed receipts are claimed.

Actual Jev1.13.0 checks retain raw probabilities: reader-regression fit0.83,
possible-effect retention0.76, portable-only scope1.0/confidence1.0, and remaining
native profile binding0.95. These judgments do not replace deterministic tests.

## Additional Original-Instruction And Store-ABI Evidence

Implemented staged native-tail-stores.S/.ld for all nine original store sites.
The original callback plus these assembled trampolines passes42 HIF/selector/
reserve-failure/publish-failure cases. Exact original compressed/full store
opcodes, complete4/6-byte detour boundaries, relocated AUIPC results, all
callee-saved registers,16-byte original frames, ordered effects and whole
64KiB DATA/1MiB BAR memory match. The probe deliberately stubs ownership guards
and skips only printf. No real native owner/session admission is established.

Receipt .local/npu-pcie-tail-owner-20261014/native-abi-q1/result.json SHA256:
8b7c98349fdfa5b09878adc7a077c503d331a3c9fdd2287032ab342794826831.

The following INODE original-code fixture separately executes type109 lookup:
fixed3e8bc470/no writes, not a dynamic allocation. Four nominal selector2/7
frames and all1036 interrupted-write prefixes match whole64KiB DATA/eightKiB
ICV-neighbor window plus unchanged original CODE. Selector2 has1030 effects
(three flags,1026 clear words, final flag); selector7 has six flag effects.
The synthetic cuts stop before original stores; physical bus/concurrent faults,
candidate prior owners and authenticated admission are not exercised.

Receipt .local/npu-inode-next-20261014/original-prefixes-q1.json SHA256:
4bafefb6349eac36676b4eb991a7b0b095d45d68f9f8f52550283207a7cabe5f.
The portable checkpoint plus these two new receipts cross-check57 current input
hashes. See NEXT_NATIVE.md for exact per-site frame/continuation handling,
required real guard/history integration and the following INODE contract.

## Continuing Native Jobs

Fixed8-group controls24394 is terminal0: all30 unique native PCIe fault cases
pass the checked aggregate, including exact protected memory/prior owners and
callee-saved registers before restoration. Its267 current input hashes were
independently rechecked; aggregate SHA256:
a82de767b3cb8250285d332eb2e0d4407ac30df7e4e22970ce5724024a901c54.
This is restored-prefix native fault proof, not a fresh caller or hardware proof.

The redundant serial30156/PID3816541 was intentionally interrupted only after
that equivalent complete checked coverage. SIGINT was swallowed in a ctypes
callback; SIGTERM ended the exact process (terminal1, PID absent). It is not
counted as a pass. The interruption receipt is local.

Fresh caller82479/PID3199667 is still confirmed live at the actual pre-DESC10
prefix after all six API21 phases/53260 effects. It has not completed DESC10/
PCIe acceptance. Poll the same handle; do not restart on observation timeout.

The second Jev scope batch selects restored native fault matrix and synthetic
INODE instruction prefixes (each1.0/confidence1.0), and retains real native guard
gap0.93/outer-owner gate requirement0.83. Raw results remain local; not proof.

## Next Implementation

1. Finish/reconcile those native verdicts and preserve their exact input hashes.
2. Promote the qualified owner/fixture/tests to normal source, Makefile/export
   and source-lock paths, then recheck their dependency closure.
3. Bind all nine original store sites, retained completed TX/RX/DESC10 history,
   authentic held session/BAR/nonce and exact native lock/IRQ/neighbors/readback.
   Preserve the original frame/callee-saved registers and all partial effects.
4. Extend server/client/provider ordering for the actual three commands; cover
   malformed operands, late failures, lost/mutated replies and native mutants.
5. Continue INODE2/7/full ICV extent, final IRQ, workers/hot packet paths and
   full physical backing/coherency/drains/reset/removal/rearm/recovery/boot/
   actual-client requirements. This checkpoint closes none of those scopes.

No router contact, flash/reset/Wi-Fi/power/private-backup changes, subagents,
new world image, commit or push occurred in this checkpoint.
