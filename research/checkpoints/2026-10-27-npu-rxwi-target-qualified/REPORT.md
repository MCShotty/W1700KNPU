# Current RXWI Target Qualification And Terminal Native Failure

Base: `ca05dff2adaa985aff277561e75b434014d97df6`. Continued solo. The integrated
RXWI change now has target compilation and selected compiled-helper evidence.
The separate full native recipe failed. Neither outcome establishes complete
Linux teardown, physical DMA retirement, stock parity or full NPU completion.

## Terminal Native Recipe

Original full-q21 invocation `6c1bc5ff20d74add9235553e70e26931` is failed,
exit1/MainPID0, with no cgroup/original processes. Its wrapper/controller fail
and no full result exists. The dependency queue waited for that termination;
it did not stop or restart the original replay.

| Profile | Checked Positive RPCs | Publications | RESET / MCU_BEGIN / MCU_COMPLETE Each | Result |
| --- | ---: | ---: | ---: | --- |
| 0 | 6421 | 129 | 2050 | Complete profile receipt |
| 1 | 6421 | 129 | 2050 | Complete profile receipt |
| 2 | 257 | 119 | 0 | Next publication times out |

The bounded audit rechecks positive operation/argument/generation order against
the recipe, exact I/O counts, performance aggregates, final rolling digest and
broker/journal/prefix hashes. Each completed profile includes2179 full extent
comparisons and four full DMA/SRAM/code checkpoints. The driver reaches profile2
only after the sequential earlier profile calls return. MCU results and device
effects remain modeled; these are not physical-board or whole-cold-setup tests.

Overall13099 positives/377 publications do not satisfy the full19261-RPC recipe.
Profile2's ordinal119/slot119 fails at `0x841047c4` after60000840634ns under the
unchanged100M-instruction/60s limit. It records24576 extent writes,23721 reads and
one of two table reads. No injection or unmodeled access is recorded. The error
is a wall-time budget assertion, not a data-mismatch finding or demonstrated
firmware logic defect. The remaining readback was not completed or accepted.

Local ELF/Capstone inspection places that PC at `lw a0, 0(s3)` in `read_memory`.
All96 function bytes match paired CODE. This locates the stopped instruction;
it does not prove why it timed out. No REA or Ghidra verification is claimed.
Do not restart unchanged inputs or combine old/new subset passes into a fresh
complete native verdict. Faithful observation overhead and timing reliability
need further qualification without dropping any count, fresh SP, I/O or fault
check or extending guest limits.

## Current Module Qualification

Four-module producer:
`92c75156014d8e4a4ed795656bf29d47268ca6b64e5a40544a35acc181d4e31e`.
It binds current source lock `d55e71a3`, mt76 patch `5fa42f93`, Linux6.18.52 and
aarch64 vermagic. A fresh copied-cache compile/link reconstructs18 patch outputs
without fuzz. The verifier's before/after inventories match:102685 original
kernel entries,516 original mt76 entries and1036 old-cache entries. Read-only
namespace/overlay protections keep original source and cache separate from the
new output; this is not an independent audit of every inaccessible host object.

Only mt7996e changes, to
`d7cad6dfeb8578fa884220f14462089b416f0b98a895dd9d5d601214052d266d`.
Provider, mt76 core and connac bytes match their qualified prior counterparts.
This is cache-backed current compilation/linking, not a claim that every
unchanged translation unit was recompiled from scratch or modules were loaded.

The actual compiled RRO/helper receipt `c85efeb3` passes10 cases/three controls:
the source drain is present, every case performs32768 token queries and all
RXWI metadata is gone at modeled context free. Original selected AArch64 list
and free instructions execute; IDR/page-pool/kernel and outer effects remain
models. This is now compiled-source-fix execution, not merely the earlier
pre-fix helper plus a modeled extra drain.

The fresh-module MCU contract passes31 cases/three instruction mutations and
eight equal send-error trace groups. It still demonstrates cleanup continuation
after modeled MCU failure, not a complete consumer-retention implementation.

All15 selected-C/lifetime/tooling regression suites pass, including167 tooling
units with zero skips and the three selected host-C ThreadSanitizer lanes.
Declared nested inputs, suite hashes and actual module bytes are revalidated.
These are fresh selected-C/model/tooling tests, not fresh UML/ARM64-kernel runs
or physical tests. The finite Windows queue has completed both phases; its
successful transient units are collected and no longer executing.

## Preservation And Resources

All294 prepared native input versions are retained read-only:5777126 bytes,
an explicit original-to-retained manifest, original/retained modes and checked
hashes. This preserves those consumed file bytes, not an entire runtime or
toolchain. The separate438 target-input graph also rehashes but is not copied.
Older source versions must remain available when future edits change a bound
input. Terminal artifacts and both completed profile receipts stay intact.

Module/regression phases retain400MiB/no swap,512/768MiB C-output reserves,
fresh Windows/Linux backing/RAM guards, dual margins and the original C writer
lock. The terminal audit runs read-only at192MiB/no swap/Nice19; the fresh MCU
probe runs read-only at400MiB, with EROFS controls and no C output. Additional
concurrent D-output reserve is counted. No resource margin or replay limit is
relaxed. No original job is restarted, no data deleted or Ubuntu stopped.

The q3 semantic-request preparer fails parsing; q4's mechanical local rename
accidentally changes a fixed producer path. Both remain preserved and neither
produces inference. Fresh q5 retains six actual Jev1.13.0 answers: corruption
demonstrated0.12, firmware-cause0.13, full-native-acceptance0.07, compiled metadata
fix0.86, physical-drain0.05 and cleanup-continuation0.90. Direct compiler/test
and artifact checks establish their covered software scope, not these probabilities.

## Remaining Project Work

Complete the unchanged three-profile native recipe on a freshly qualified
timing implementation. Implement and qualify complete consumer ownership and
containment/retention across devres, pages/mappings, rings, tokens/metadata and
context. Physical MCU/radio/NPU drain, BA reuse/hot lifetime, current image,
board/actual clients/performance/stability remain open. Existing images predate
this RXWI target qualification and are not relabeled current by these module tests.

Source lock/patches remain unchanged. No new image, module load, router contact,
flash, Wi-Fi association change or further compaction occurs. Ethernet remains
disconnected at the user's request. Six previous tracking bodies are preserved
after new prefixes. The full NPU objective remains active.
