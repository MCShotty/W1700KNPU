# RXWI Metadata Cache Reclamation

## Finding And Source Fix

Continued solo from `5328fb670025edef4aa0ce2b6305f8d87c6daa37`.
The current non-WED RRO teardown has a software-metadata ownership hole:
shared DMA cleanup drains `rxwi_cache`, then later RRO page-map cleanup removes
outstanding RX tokens, clears their page/DMA fields and puts the RXWI metadata
back into that cache. The shown core-free path has no subsequent cache drain.
This is a conditional CPU ownership finding, not an observed router memory leak.

The unified source now invokes the already declared/exported
`mt76_free_pending_rxwi(&dev->mt76)` immediately after `mt7996_rx_token_put(dev)`
in `mt7996_rro_msdu_page_map_free`. The existing WED RX-buffer release helper
uses the same retire-then-drain pattern. The two-line C delta does not change
structures, descriptor formats, firmware, NPU barriers or physical drain policy.

All18 cumulative mt76 patch outputs reconstruct with zero fuzz and offsets;
only `mt7996/mac.c` changes, with17 outputs byte-identical. Strict checkpatch of
the narrow source delta passes. The source-export verifier checks79 OpenWrt
and five LuCI entries;31 component mappings remain unchanged.

- Source lock: `d55e71a34038adbc16dc4d38c126469ff76f64a904d4f6b75fc0612531bd5da7`.
- mt76 patch: `5fa42f93cd3528557556978f9335a3c78013b447f5b7cfd2503e607af3cf5cb6`.
- Kernel patch stays `aacc0ffccdd91a6f004e5e0a85d5e10be83ddf54f0efd0ea661c80087d4e15e6`.

**Target compilation of this fix is pending.** Retained four-module producer
`a840d3cccb1d0bd8cc60a856d1a1bb9723dfc05af73484d955a33978a458d22f`
predates the fix. Its exact source, patch and source-lock preimages are preserved
under `.local/npu-rxwi-late-drain-20261027/before-source` and `before-project`.
Do not describe those old modules as containing the new source call.

## Executed Helper Evidence

`tests/npu/test_rxwi_retirement_native.py` loads the exact retained AArch64
module instructions for RRO page-map cleanup, native cache enqueue, pending-cache
free and core hardware free. It relocates selected address references and models
only declared external boundaries. Imported put-RXWI calls execute the actual
shared-module function and its internal helper, not a Python list substitute.

Five seeded fixtures cover empty and cached-only state, one active RX token,
three sparse tokens including32767, and two page fragments sharing one page.
Each runs with and without an additional modeled late-drain call: ten cases,
not ten physical devices or complete Linux teardowns. Without that call, live
RXWI metadata at modeled context free is0/0/1/3/2. With it all are zero, with
exactly-once metadata frees and page-return accounting. All32768 modeled token
queries execute in every RRO sweep; no empty ranges are skipped.

The actual list/atomic instructions, original function ranges, AAPCS64 callee
preservation and fresh argument reads execute. Every modeled call clobbers the
same caller-saved registers. IDR removal, page-pool return, IRQ/NAPI/NPU CPU
lifecycle and hardware-context free are explicit models. The full outer cold
cleanup and actual Linux IDR/page-pool implementations are not executed.
The additional late-drain sequence is not newly compiled source-fix execution.

Three boundary controls fail their intended assertions: omit native enqueue,
omit modeled metadata free, or use the failing batched-PC transfer path. These
are not compiled mutation controls. The loader can later verify a fresh target
producer using `--expected-producer-sha256`; it requires the compiled RRO helper's
cache-drain call to agree with the supplied SHA-bound source.

scoped-q11 and protected scoped-q16 each pass the same ten cases/three controls;
they are repeats, not20 unique cases. Both use400MiB/no swap and unchanged
1M-instruction/5-second per-helper bounds. q16 enforces read-only shared inputs
in a private mount namespace and confirms write opens fail with EROFS. Output
stays on Ubuntu's root backing, not C scratch; no C writer lock is displaced.
The old full replay remains live and advancing before/after both finite probes.

## Preserved Preparation And Failures

The first DWARF-layout assertion covered both missing and inconsistent layouts.
Fresh diagnostics find no matching complete structure-type DIEs; they do not
show an ABI mismatch. This fixture's offsets come from actual inspected memory
operands in the exact modules, not a guessed or universal structure layout.

q4/q5 hit the fixed helper bound. q6 retains actual stopped state:24081 token
queries,218105 block-accounted instructions,5001056777ns andPC11016e14. Fresh
preallocated SDK batch buffers preserve all four fresh reads,19 result/scratch/
LR writes and scalar PC transfer. No limit or modeled effect is removed.
q7's batched-PC assertion, q8's parse refusal, q9's bound failure and q10's late
relative-path receipt failure remain with consumed sources. None is relabeled
as a passing receipt. q11/q16 are fresh, complete passing runs.

Raw Git whitespace diagnostics on newly added nested-patch context lines are
retained. Those context prefixes are patch syntax, not the generated C delta;
strict narrow checkpatch and whitespace checks on non-patch public files are
the corresponding source/publication checks. No patch context is removed.

Jev used the official helper/model `jev-1.13.0`. Actual Noul results include
late metadata transfer0.95, existing caller drain0.24, proposed cache target0.83,
complete-kernel proof0.05 and physical retirement0.05. Raw probabilities remain
semantic evidence, not proof, generation or authority. The
[official System One API](https://docs.typesafe.ai/api/system-one) defines the
request shape used by the local helper.

## Native Replay And Next Work

The original full-q21 invocation remains live. A retained two-sample observation
verifies the actual guard18906/wrapper18920/driver18942,241 advancing driver CPU
ticks and a complete-line profile0 prefix of237 checked RPCs:
OPEN1/ENROLL139/PUBLISH97. It is not an atomic guest snapshot or a full verdict.
All294 frozen inputs rehash; none of the changed source/patch/lock/tracking paths
is in that bound set. No replay restart or competing compilation occurred.

After full-q21 is authoritatively terminal, build/link the current target modules,
run the helper replay against that fresh producer and current source, and require
zero live RXWI from the compiled source drain without the modeled extra call.
Then execute selected-C cold/PCI/NAPI/RRO regressions and actual-kernel coverage.
No new target compile, image, module load, router contact or flash occurred here.
Ethernet is disconnected; no Wi-Fi association or system policy changed.

This metadata fix is not a substitute for the complete MCU/queue/page-pool
retention/drain contract. Physical ownership, BA reuse and hot lifecycle, current
image/board/client evidence, performance and stability remain open. Six existing
tracking bodies are preserved byte-for-byte; the full NPU goal remains active.
