# Compiled Kernel IDR In The TX Token Replay

## Result And Scope

`tests/npu/test_tx_token_kernel_native.py` replaces the earlier Python token-IDR
get-next/destroy hooks with retained Linux 6.18.52 AArch64 routines. Final
replay-q5 passes 56 token cases and seven emulator-byte controls, with 30 input
bindings. This executes selected driver/kernel-library bodies in emulation, not
a running Linux kernel or complete SMP/physical lifetime.

The driver producer remains pre-FW-high-DMA-fix `92c75156`. The original kernel
inventory binds idr.o, radix-tree.o, their source/headers, config and vmlinux.
All 417 old producer inputs verify with three preserved old-source aliases.
The prior 62-case token/callback suite and its 17 inputs also remain unchanged.
Current source lock `cc128c3b` and the FW-TXP fix remain target-compile/execution
pending; this suite does not accept the new FW high-address decoder.

Final result SHA256:
`bd0830659f3573b62a2de6e43fb6e24b402a07775728821d041f0a7ba10c7266`.
Test source SHA256:
`83f0f8b20dbce41268005f1142032914f214fb263de83fa2559a41f795c48fc9`.
Private evidence: `.local/npu-kernel-idr-native-20261027/`.

## Actual Compiled Execution

The five kernel bodies are `idr_get_next`, `idr_get_next_ul`,
`radix_tree_next_chunk`, `idr_destroy` and `radix_tree_node_rcu_free`. Their object
bodies match the linked vmlinux symbols after normalizing only relocation
immediates. Opcode/register bits and nonrelocated bytes must match unchanged.
This is not an unchecked assumption that an old object was linked.

The fixture binds root/base, node slot/parent/RCU offsets, chunk width and the
IDR free marker to source and exact compiled operands. It supplies valid radix
tree memory; allocation/registration of that tree is still modeled. Native code,
not a Python get-next/destroy implementation, traverses it and clears its root.
All five selected kernel bodies actually enter. Eleven bodies enter overall;
13 are mapped. The ordinary connac callback and put_txwi.part.0 copies do not
enter this token-only suite; the earlier callback suite has separate evidence.

Cases include empty/single/sparse trees, IDs through 16383, a full 64-slot leaf,
crossings at 63/64 and 4095/4096, actual MT7996 flags, FW/MAC layouts and pending/
ready SKBs. Aggregate counts across these fixtures are 229 entries each into
get-next/get-next-ul/next-chunk, 56 destroys, 173 TXWI returns and 188 node callback
invocations. These are fixture execution counts, not physical packet counts.

Before each driver continuation, actual IDR return values and index stores must
match the independent fixture oracle. After destroy, the actual root pointer and
free marker must be correct. The driver still performs the compiled TXWI/SKB
release, count decrement and cache operations qualified in the preceding work.

## RCU And Payload Boundaries

Actual compiled destroy queues node callbacks through a modeled call_rcu service.
No node may reach the modeled slab free before a declared modeled grace point.
The test then invokes the actual compiled callback, which clears slot/tag bytes
and restores the private list before reaching modeled kmem_cache_free. All 188
queued callbacks and slab returns must match, exactly once for each fixture node.

Manually invoking that callback after a modeled grace point does not establish
real RCU grace-period scheduling, concurrent readers or Linux SMP correctness.
Slab allocation/free, initial tree construction, mac80211 and DMA effects remain
models. Kernel and modules were not loaded.

IDR destruction reclaims tree nodes, not every TXWI/SKB payload value. The
pending-status case still returns TXWIs while three SKBs await TX status; the
ready case reaches three modeled mac80211 completions. Packet-status IDR
registration/removal, later TXS/flush ordering, station/PS/non-AQL branches and
complete consumer/devres/context ownership remain unexecuted. Physical containment,
DMA drain, reuse/hot and board/client acceptance remain open.

## Controls And Provenance

Seven controls omit the kernel destroy call, RCU enqueue, callback slot zeroing,
slab return, next-index store, root-head clearing or free-marker update. Each
must fail its specific assertion. Mutation touches only emulated instruction
bytes. A full leaf is required for the free-marker control so the missing write
cannot hide behind an already-set marker. No modeled IDR service is permitted.

Inspection-q3 and object-only replay-q4 remain retained with consumed sources.
Final replay-q5 adds linked-body equivalence and explicit native-entry/model-hook
checks. Repeated 56-case runs are not 112 distinct cases. Preparer-q1's overly
strict replacement-count check failed because the guard derives its directory
from __file__; q2 preserves the source and recovers the identical partial launcher.
No production guard or native control was weakened.

Final service runtime was 29.355 seconds, peak memory 163 MiB under a 192 MiB cap,
no swap, low priority, fresh Windows/Linux RAM and backing-storage margins,
120-second oneshot deadline and EROFS C-write control. No compilation or C-output
write occurred. All frozen inputs verify before and after execution.

## Ongoing Recipe And Queue

Original full-q16 invocation `20c8f1ab62d74236bf977c134d09b059` keeps its exact
guard/wrapper/driver identities and advancing CPU. Profile 0 retains its verified
6421-RPC final artifacts. Snapshot-q6 captures profile 1 at 237 positive RPCs and
97 publications, not a completed profile. All three profiles/19261 RPCs still
require their complete result; no older subsets are substituted.

Windows queue PID 17788/plan `e67d5198` remains live and waiting. Its 454 target
inputs and all 332 native/read-only retained inputs verify unchanged. No target
phase has started. This new suite is outside those frozen sets and was not added
to the queue. Follow the existing queue; do not duplicate or edit it. After fresh
module/regression qualification, rerun both token suites against matching new
modules/source without the old mac.c alias.

Next ownership work must follow nonempty packet-status IDRs through actual
registration/removal and TXS/flush/DMA ordering, not infer it from token zero.
Six prior tracking bodies are byte-preserved. Ethernet stays disconnected; no
module load, image, flash, Wi-Fi change, shutdown, compaction or subagent occurred.
Full NPU goal remains active.
