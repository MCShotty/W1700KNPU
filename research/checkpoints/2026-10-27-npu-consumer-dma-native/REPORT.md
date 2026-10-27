# Compiled Consumer RX Cleanup Contract

## Scope

From mainline `38deb5a`, a new source-bound test executes seven retained
AArch64 cleanup bodies under Unicorn. It extends the earlier MCU replay across
the shared mt76 DMA boundary: `mt7996_cleanup_device`, `mt7996_mcu_exit`,
`mt7996_dma_cleanup`, `mt7996_dma_disable`, `mt76_dma_cleanup`,
`mt76_dma_rx_cleanup` and `mt76_npu_queue_cleanup`.

In the tested failed-MCU-poll cases, these compiled bodies continue through
NPU queue cleanup and reach modeled page-return and page-pool-destruction
calls. This is selected compiled-body execution, not execution of Linux itself.
Firmware responses, MMIO effects, IRQ/NAPI/scheduler APIs, DMA synchronization,
page-pool return/destruction effects and physical ownership remain models.
No physical DMA drain, physical use-after-free or working retention fix is
demonstrated. No production firmware or driver source changes in this checkpoint.

## Qualified Inputs

- Current four-module producer: `92c75156014d8e4a4ed795656bf29d47268ca6b64e5a40544a35acc181d4e31e`.
- Core `mt76.ko`: `3011a7968e1e0f206571b4057bbd6f66a8ade65021e6e546b59ca855595cd834`.
- Radio `mt7996e.ko`: `d7cad6dfeb8578fa884220f14462089b416f0b98a895dd9d5d601214052d266d`.
- Final source-bound q7 receipt: `ca9a5ebae9f4152908169a90dcb279883b91019bec7f7a1de4316f9a0a357aad`.
- Final test source: `724519bb4825eedc08fec2ee85f1130c72d32cd60ae756d8c3b5d57e096536f2`.

The receipt binds 19 source/module/producer inputs. Nine mt76 source/header
files match the actual producer context. Selected text, relocations and local
BL targets come from the hash-bound modules; required compiled load/store
operands bind fixture offsets. The retained ELF has partial DWARF, but it lacks
the required queue-layout definitions. Neither failed q3/q4 extraction attempt
is used as a layout source. Both failures remain preserved.

Host versions are Python 3.14.4, Unicorn 2.1.4, Capstone 5.0.7 and pyelftools
0.32. The private audit also hashes the Python binary. No compiler, new target
module or router image was produced.

## Executed Contract

The current q7 run passes 35 cases and six independent instruction-mutation
controls. Earlier q5/q6 runs are preserved versions, not additional cases.

- Sixteen shared-cleanup cases cross tracked/legacy NAPI and coherent/noncoherent
  DMA settings with zero, one, three and 511 queued entries. The actual NPU
  queue indices 19/20 and 512-entry capacity are used, including tail wrap.
  Current nominal occupancy leaves one ring slot empty, as refill does.
- Twelve outer-cleanup cases cross modeled MCU poll success/failure,
  send return 0/EIO/ETIMEDOUT and HIF2 presence. All three send-return variants
  have identical ordered traces within each of four poll/HIF2 groups.
- Two ordinary-RX cases have an empty dequeue and a pending synthetic rx_head;
  only that head's modeled release is covered, not nonempty ordinary RX.
- Two direct RX-cleanup boundary cases cover no descriptor allocation and an
  empty NPU queue. A separate shared-cleanup case covers no descriptor allocation.
- Two extra shared-fragment helper cases exercise the compiled page-fragment
  decrement branch. They are synthetic helper models, not proof of the current
  NPU allocation profile.

Queued descriptor DMA addresses match their entries, with DONE both clear and
set. The compiled NPU cleanup does not consult descriptor status in these cases:
memory-access hooks see no descriptor read/write. A mutation inserting a real
descriptor read trips the access assertion. This observation is not a physical
ownership or drain witness.

At each modeled pool destruction, assertions require every queued entry drained,
the exact wrapped tail, each modeled page returned once after its fragments are
exhausted, and exact ordered DMA-sync arguments for noncoherent entries. Coherent
fixtures skip the external sync call. Bottom-half nesting is balanced. The outer
cleanup is inert on a second invocation.

Six byte mutations made only in emulator memory each fail the intended assertion:
omitted queue cleanup, page return, DMA sync, pool destruction and firmware poll,
plus the inserted descriptor read. The real module files remain unchanged.

TX queues/tokens and managed RRO allocation slots are empty. RXWI cleanup,
IRQ/NAPI joining, page-pool internals, devres release, endpoint unbind and context
destruction are not newly executed as Linux behavior. Do not extend this receipt
to those owners or to nonempty ordinary RX/TX/RRO retirement.

The first q5 run passed its own assertions but used a 512-queued-entry fixture,
outside refill's reachable one-slot-empty occupancy. Its original source and
receipt remain preserved. The current q7 replaces that nominal boundary with
511, initializes descriptor addresses, bounds shared-fragment claims explicitly
and adds a descriptor-read mutation control. Q6's consumed source is also retained.

## Running Full Replay

The independent full native firmware replay is still the original full-q16
invocation `20c8f1ab62d74236bf977c134d09b059`, with guard137794/wrapper137812/
driver137844, driver start ticks5470636. The before-publication snapshot records
237 positive RPCs and 97 publications in profile0, plus advancing driver CPU.
That is a progress prefix, not a profile or complete-recipe pass. EVIDENCE.json
records a later exact observation; do not substitute its prefix for a verdict.

All 332 live producing inputs and read-only retained versions rehash. The new
test and six tracking documents are outside that frozen set. Its 400MiB/no-swap
cap, boot3M/10s, RPC100M/60s, 512MiB C-output reserve and writer lock stay intact.
No restart, competing compilation or sampling occurred.

The separate analysis runs use fresh Windows/Linux headroom checks and a
192MiB/no-swap, Nice19/CPUWeight1 read-only namespace. The C-write negative
control fails with EROFS, and C output is zero. Final q7 peaks at 63MiB reported
by systemd, without swap. It finishes in 4.919s; this is not a firmware speedup.

## Remaining Work

This closes a selected compiled consumer RX cleanup characterization, not its
complete ownership/containment contract. A complete failure path still needs
all consumer allocations, provider/endpoint devres, page pools, token/RRO owners
and context lifetime accounted for through real physical containment and drain.
Ordinary device/provider references or a successful modeled ACK are insufficient.
BA reuse/hot lifetime, the complete fresh native recipe, current image/board
acceptance and real-client performance/stability remain open.

Ethernet stays disconnected. No router contact, module load, image, flash,
Wi-Fi change, shutdown or additional compaction occurred. The full NPU goal
remains active. Preserve the live replay and all consumed versions.

Reproduce with `tests/npu/test_consumer_dma_native.py --producer RECEIPT
--expected-producer-sha256 HASH --source MT76_SOURCE --output FRESH_DIRECTORY`
in the documented read-only, bounded analysis environment. Private inputs and
full receipts remain under `.local/npu-consumer-native-20261027/` and are not
uploaded. EVIDENCE.json records their hashes and the public source/document bindings.
