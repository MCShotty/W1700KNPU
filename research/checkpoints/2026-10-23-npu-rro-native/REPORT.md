# Reconstructed RRO Native Effects

Status: implementation progress, not full NPU completion or operational RRO
admission. Base commit: `70521a9f339dca25ca82122e569c344ee6a5da8d`.

## Implementation

`firmware/npu/rro-native.c` implements the stock-derived memory effects using
the retained ownership journal. Publication records possible exposure before
any callback, writes and reads back the exact table pointer, clears complete
64 KiB element blocks, sets signature bytes and verifies the resulting words.
Session publication preserves other bytes. Reset requires the caller's exact
generation/ticket, validates the retained table pointer and updates only the
1,024 signature bytes for its selected session, including special ID1,024.

Any access/readback failure stops successful confirmation and retains the
ambiguous prefix, ticket and journal error. The engine provides no free, CPU
join, drain or retirement capability. Stable backing/context/plan and CPU
exclusion remain explicit caller obligations.

The normal RV32 Makefile and canonical kernel Kbuild now include the engine;
the authoritative source lock has 26 component mappings. Only the generated
kernel Makefile changes in the selected kernel sources. No raw pair, radio/UI
policy, complete image or hardware state changes.

## Executed Checks

- Host engine: 14,412 ASan/UBSan/leak cases and four compiled intended-assertion
  mutation controls pass. All three profiles, 129 publications, 1,025 IDs and
  two generations execute. Includes 7,740 selected publication failure cases
  and 135 selected reset failure cases, not every instruction/write prefix.
- All 134 emitted frames match the previous actual caller capture. The host
  emits 6,958 complete first-generation states, each 30,356 bytes, across the
  three profiles. Generation two is tested on host but not emitted to this
  comparison stream.
- Existing actual TX 223/12, RX 168/7, provider 448/4, caller 1,090/seven
  controls, journal 5,279/3 and 116 tooling units pass, zero skips. The caller
  fixture separates 1,040 optional-provider cases from 50 modeled owned cases;
  these separate suites are not full joint kernel execution.
- All four AArch64 modules final-link with GCC14.4.0/Linux6.18.52. Producer
  `c137169d` and source lock `180d4358` bind 5 kernel/329 mt76 sources and
  26 component mappings. Original prepared build trees remain unchanged.
- Normal archive has 24 exact RV32 objects. All previous 23 members remain
  byte-identical. The two engine/journal members have no compiler runtime
  dependencies; the engine's undefined names are its journal API references.
- RV32 compile preflight and complete exact-object Unicorn execution pass:
  all three profiles, 6,958 entire host state records, 6,150 NPU resets across
  two generations, 78 selected I/O faults and 13,342 fixture calls. Integer ABI,
  MSTATUS, instruction bytes and entire mapped SRAM/alias projections are
  checked. The fixture links the extracted normal archive members without
  recompiling them or substituting instruction bodies. Peak service charge:
  317,894,656 bytes under the unchanged 400 MiB ceiling.
- Supplemental session-table publication/ID1,024 reset tests pass six positive
  cases and 78 fault cases across all profiles. These use explicitly host-seeded
  journal prefixes, not a previously executed native prefix or full startup.
  Six fake-CPU observer-method guard units pass, zero skips. Auxiliary ceilings
  are 128 MiB for guard units and 256 MiB for the additional native boundaries;
  measured peaks are 53,063,680 and 110,002,176 bytes respectively.

## Scope And Preserved Failures

The target fixture uses direct function entry, synthetic mapped backing, CPU
exclusion wrappers and modeled MCU success. It is not full cold startup,
current raw-pair enrollment/transport or physical acceptance. The stock byte
projection derives from previously verified original-instruction work; no
fresh original-stock instruction replay is claimed here. Fault-prefix memory
restoration is a fixture mechanism, not production rollback or retirement.
The full native-prefix replay injects faults at block publication0/reset0;
the supplemental host-seeded run adds session-table publication/reset1024.
These are selected software-I/O fault cases, not every native instruction
prefix, transport race, hardware reset or physical lifecycle fault.

Host q1 exposed undefined fixture pointer arithmetic before baseline completion.
Host q2 passed its baseline but a mutation hit an earlier correct assertion
than expected. Both cohorts and their logs/binaries remain preserved. Corrected
fixture/expected diagnostic, not the production engine. Compile-only output is
separate from terminal execution results and never says full execution passed.
The parallel observer-unit launch was refused by the full-capacity RAM budget
before any tests started. Its failed unit and reviewed controller version are
preserved. After the target replay exited successfully, sequential auxiliary
units passed under their separate tighter ceilings. Neither live replay's cap,
instruction policy nor the reserved margin was relaxed to fit concurrent tests.

Jev source checks support exposure-before-access/readback obligations and
distinguish caller exclusion/modeled MCU from physical proof. The judgments
remain advisory, not test replacements or action authority. Focused subagent
reviews and observer tests are additional scoped checks, not firmware proof.
One initial reviewer finding confused expected-state bytearray edits with input
seeding. The reviewer retracted it after checking the actual Python side effects;
no production or fixture change was made to satisfy that mistaken finding.
The MCU source review left two Jev judgments uncertain (0.36 and 0.42).
Direct inspection confirms that status dereferences the current aggregation
pointer and BA start stops/replaces that object; model uncertainty is not
reported as proof of a particular device event ordering or a physical race.

## Remaining Work

Connect native-owned enrollment and identity-bearing transport/completion,
retained MCU/BA/work-item generations, serial transitions with late TX lease
validation, and actual CPU join plus IRQ/DMA/firmware/cache/PMA retirement.
Current selectors0/1/3 remain closed; permanent denial is not the final state.
RX-TID creation must own a BA-lifetime token, distinct from the retained reset
generation/ticket. Existing queued delete work loses WLAN/TID association, and
the wrapping MCU ACK sequence is not that BA token. Where no event cookie is
available, an actual ordered reuse fence is required, not a guessed generation.

Finish the original frozen default replay, separate HIF2/full faults, complete
current image and hot/whole-stack/physical boot/radios/actual-client/performance/
stability acceptance. The original compact replay stays live on frozen2f85e54,
not restarted or upgraded in place. Protected image a3f1d04b is old-source only.
No flash, VM restart, swap, limit relaxation or global policy change occurred.
