# Retained RRO Ownership Journal

Date: 2026-10-23. This is concrete implementation progress toward the full NPU
objective, not completion of that objective. Base commit: `8f4a6a8`.

## Implemented

`firmware/npu/rro-lifetime.c` and its header implement a retained metadata
journal with immutable provider/endpoint/boot/nonce/epoch/profile identity.
Full selected-source geometry is preserved: 139 V3, 139 V3.1 and 137 V3.1-WED
extents, including 128 element blocks and all 1,025 session IDs. Complete CPU
pointers, DMA handles and lengths are retained; high DMA bits, alias/CPU overlap
and declared protected-span overlap are rejected before publication.

Ordered publication latches possible exposure before command/ticket output.
Errors retain ambiguous extents and the first sticky error; matching late
results update bookkeeping but cannot erase the failure. Session reset
generations and transfer tickets correlate duplicates and the ordered NPU/MCU
phases, with one in-flight credit per transport. Counters cannot wrap.

Closing retains every allocation/request. An exact ticket/epoch CPU join must
precede the five domain observations. Even the complete set confers **no
reclamation authority**. There is no free, reset, cancellation, rearm or
reinitialization API. See `firmware/npu/RRO_LIFETIME_CONTRACT.md`.

## Executed And Compiled

- Host C: 5,279 ASan/UBSan/leak cases cover complete profiles, every allocation
  and ambiguous-publication prefix, all reset IDs, duplicate/generation/error/
  late/credit boundaries, every retirement subset and invalid metadata.
  Counter exhaustion uses injected near-boundary state, not billions of calls.
- Three deliberate mutants compile, then fail at the intended exposure-latch,
  reset-ticket or pre-join-retirement assertion. Neither compiler errors nor
  sanitizer faults count as successful negative controls.
- Fresh actual selected caller/managed-bookkeeping characterization passes
  1,037 cases and three teardown controls against the new genuine producer.
  All 134 generated caller frames exactly equal the journal's emitted frames.
  Framework/DMA/devres/MCU/RCU scheduling remain explicit modeled boundaries.
- Normal RV32 build: all 23 ELF32 RISC-V objects compile. Archive members and
  bytes exactly match those objects; the journal has no undefined symbols.
- Pinned GCC14.4.0/Linux6.18.52 build: provider, mt76, connac and mt7996 modules
  all final-link. The new journal is compiled into the actual provider module.
  The current producer binds 24 component mappings, 5 reconstructed kernel
  source files and 329 mt76 files, with unchanged original prepared trees.
- All 116 source-export/header/module/parser/build/storage tooling units pass,
  zero skips. Current cumulative export verification passes separately.

Current source lock: `fd6dd27f6bbe6c34aaab7fe354588f6398a2fec7e6e4262966eab2084be06eb6`.
Current combined module receipt:
`383591e46fb5a2e2059a7a3a906e2de947c29998c6424bf673bee3274d98c764`.
Provider SHA256: `1a2f6c23f516294370aa76f5bce1a7e523dbcf5b4bbb0170896ae8285e9ac551`.
Full private/public identities and actual service observations are in
`EVIDENCE.json` and its hash-bound private receipt.

These are host journal executions and target compilations/links. This
checkpoint does **not** execute the new RV32/AArch64 journal instructions or
reexecute the earlier stock/current instruction replay. Frame equality does
not establish physical transport, DMA backing or caller admission.

## Preserved Failures

1. The first full journal/normal-archive check failed its undefined-symbol
   guard: Clang emitted `memset`. Actual source now uses freestanding volatile
   clears. No libc shim was added and no symbol check was weakened. Original
   objects, source snapshots, logs and the failed service remain retained.
2. The first kernel build compiled the journal but failed modpost on
   `__aarch64_cas4_rel`. The kernel path now uses kernel-native acquire/compare-
   exchange primitives; host/RV32 retain their compiler atomic path. A new
   independently guarded build final-links all four modules. Old outputs and
   the old source lock remain separate evidence, not current qualification.
3. q4 passed journal/mutants/current callers/RV32/export, but four tooling
   fixtures failed because the copied export script lacked its required
   `source_component_headers.py`. The fixture now copies that dependency.
   q5 reruns all 116 units successfully and rehashes q4's passing subresults.
   q4 remains an overall failed controller. q5 does not claim another journal
   execution or rewrite any earlier result.

Jev's fresh source batch preserves its probabilities. Its exposure-latch Noul
is uncertain at 0.50; reset ticket/generation/MCU/join checks are 0.93-0.96.
Covered behavior is supported by the actual C cases and intended-assertion
mutants, not by treating these model judgments as approval. Earlier and final
semantic review receipts remain distinct from deterministic validation.

## Cohorts And Preservation

The normal source Makefile, kernel Kbuild and source lock advance together.
One generated kernel Makefile is reconstructed from the new canonical patch;
the original prepared build is not edited to manufacture source authority.
Old source locks/Kbuild inputs are captured separately. Old producer90abc8f3
and protected imagea3f1d04b keep their original source qualification only.

There is **no new full image**. The protected image still contains the older
22-object normal archive; it cannot satisfy the new 23-object/current-lock
contract. The raw4e43de6f/a282ca7a pair, UI/WiFi sources and protected images
remain unchanged. Image path bindings do not imply distinct image contents.

The live compact default replay still executes its frozen2f85e54 cohort,
not these new working sources. Rehash all 2,865 captured inputs, 14 protected
project image path bindings and one external object, and verify original
controller/native start ticks when sealing. No terminal full-cold verdict is
inferred from a live process. No replay restart, limit/checkpoint/geometry
change, VM/swap/global policy change, hardware action, flash or subagents.
Earlier duplicate-cache cleanup and its keepers/restoration maps are retained.

## Next Required Work

Wire real provider/endpoint reference acquisition and retained allocations to
the journal. Handoff must precede explicit RRO frees. Implement process/atomic
transport ownership, actual generation/ticket completion binding, retained MCU
work, higher-init error propagation and provider/consumer removal together.
Then establish actual IRQ/DMA/firmware/cache/PMA drain and retirement evidence
before granting any reclamation or operational RRO admission.

Current operational RRO guards stay closed. This is not their final intended
state. Rebuild a complete current-source image and qualify it independently;
complete the existing default replay, separate HIF2/full-fault cases, hot
ownership/lifecycle/whole-stack and physical boot/radios/client/performance/
stability acceptance. Full NPU reverse engineering and implementation remains
active.

Current caller reproduction accepts a new producer explicitly, while retaining
strict source-lock and artifact checks:

```sh
python3 -B tests/npu/test_rro_lifetime_callers.py --name fresh-rro-callers \
  --module-receipt .local/npu-checked-irq-modules/rro-owner-q2/result.json
python3 -B tests/npu/test_rro_owner.py --name fresh-rro-owner
```

Use fresh output names and the applicable guest/backing-storage budgets.
Ignored private inputs, compiled outputs and device material are not uploaded.
