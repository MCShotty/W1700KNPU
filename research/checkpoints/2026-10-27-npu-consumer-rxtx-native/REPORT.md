# Compiled Ordinary RX And TX Cleanup

## Scope And Result

From `71c9da7`, the new `test_consumer_rxtx_native.py` extends the compiled
consumer contract into nonempty ordinary RX and TX queues. Final q15 passes
64 cases and seven instruction-mutation controls, with 23 producing inputs
and four identical send-return trace groups. Repeating q14/q15 is not128 cases.
No production firmware/driver edit, compiler, module load or image build ran.

Fourteen retained AArch64 bodies actually execute under Unicorn. They include
the four radio cleanup bodies, shared/RX cleanup, ordinary dequeue, the split
TX cleanup body, index synchronization/read/kick, TX completion, TXWI cache
insertion and NPU TX descriptor cleanup. The mapped wrapper
`mt76_dma_tx_cleanup` and NPU RX helper `mt76_npu_queue_cleanup` are not entered
by this matrix. They are not counted as newly executed bodies.

Selected compiled instructions execute, not an actual Linux kernel. Firmware
polling, MMIO/regmap effects, IRQ/NAPI/scheduler APIs, DMA sync/unmapping,
SKB completion, page-pool return/destruction and allocation frees are explicit
models. No physical DMA drain, observed physical use-after-free or working
retention fix is demonstrated.

## Source Binding

- Current producer: `92c75156014d8e4a4ed795656bf29d47268ca6b64e5a40544a35acc181d4e31e`.
- Core module: `3011a7968e1e0f206571b4057bbd6f66a8ade65021e6e546b59ca855595cd834`.
- Radio module: `d7cad6dfeb8578fa884220f14462089b416f0b98a895dd9d5d601214052d266d`.
- Final q15 receipt: `024228bffa6f53d07ef6c3a7a3ec0ebadf4e2b1ff8d6bc20600bff43bd57a267`.
- Final test: `bb02f2c2c462339ad78932ebdd1d4d0f17c9df6f0bd01ec749889766c6b9a683`.

Twelve mt76 source/header files match the producer context. The new test also
binds imported repository helpers. Function boundaries, compiler-split/local
BL targets and relocations come from the retained modules. Required compiled
operands validate fixture offsets. The preceding35-case NPU RX test/source
and its19 input bindings rehash unchanged; its evidence is not rerun or relabeled.

The q10 extractor failed on absent standalone `mt76_dma_tx_cleanup_idx` before
writing a result. Inspection then located the compiler-split
`mt76_dma_tx_cleanup.part.0`; `get_buf` and cleanup_idx are not invented as
standalone entries. The failed helper/log and successful inspections remain.

## Coverage

- Sixteen ordinary-RX cases cross tracked/legacy NAPI and coherent/noncoherent
  DMA with occupancy0/1/3/1535 in a1536-entry ring, including tail wrap and
  descriptor DONE initially clear/set. Compiled flush sets software DONE,
  advances/decrements the queue and clears entry buffers before modeled page
  returns and pool destruction. A software DONE write is not hardware completion.
- Thirty-two TX cases cross ordinary/NPU descriptor paths, none/dummy/cached/
  no-free TXWI values and both buffer-unmap skip bits. Assertions cover exact
  payload-unmap arguments, copied entries at the modeled SKB callback, zeroed
  retired entries, wrapped tail, DMA-index resynchronization and waiter wakeup.
  NPU descriptor cleanup clears its DONE bit; ordinary TX cleanup does not
  consult descriptor status in these fixtures.
- Twelve composed radio/core cases cross modeled MCU poll success/failure,
  send return0/EIO/ETIMEDOUT and HIF2. The real MT7996 `TXWI_NO_FREE` bit remains
  set in every outer case. Send-return variants have equal ordered traces
  within each of four poll/HIF2 groups. Outer cleanup is inert on a second call.
- Four owner/boundary fixtures cover band2 ordinary2048/NPU1024 capacities
  at2047/1023 occupancy, plus MCU256/FWDL128 queues at255/127 occupancy.

Capacities are source-derived isolated queue fixtures. Mixed queue combinations
and synthetic packets are not a captured physical initialization topology or
proof of a complete current-image allocation profile.

MT7996's source sets `MT_DRV_TXWI_NO_FREE`. Only explicitly labeled generic
driver-flag-clear cases exercise actual TXWI cache insertion and the shared
cleanup's compiled cache-drain path, reaching modeled metadata unmap/free once
in reverse cache order. This is not proof of MT7996 token reclamation. Its
nonempty token IDR and the real connac SKB completion callback are not executed.
The callback here validates synthetic copied entries but models SKB effects.

Seven emulator-byte mutations each fail the intended assertion: omitted RX
DONE write, RX buffer clear, TX payload unmaps, generic TXWI cache insertion,
NPU TX DONE clear, SKB callback and TX index sync. Original modules stay intact.
Bottom-half and modeled RCU nesting are balanced.

The earlier q13 is only a one-case probe with the then-default cleared TXWI flag.
Its original source is preserved, not used as current acceptance. Q14 already
uses the MT7996 outer flag, but its receipt lists selected regions rather than
distinguishing entry coverage. Q15 retains the same64 cases/seven controls,
asserts four trace groups and records14 entered bodies separately from16 mapped
regions. Both producing source versions remain available.

## Full Replay And Resource Guards

The independent native firmware job remains original full-q16 invocation
`20c8f1ab62d74236bf977c134d09b059`, guard137794/wrapper137812/driver137844,
driver start ticks5470636. Corrected observation17 records1239 checked positive
RPCs in profile0:129 publications and323 RESET/MCU_BEGIN/MCU_COMPLETE each.
Driver CPU advances; all332 inputs and their read-only copies rehash. This is
a prefix, not a finished profile or complete three-profile/19261-RPC verdict.

The first before-q16 observation helper used wrong numeric labels for reset/
MCU counters; its zero values are invalid. The old helper/snapshot are preserved.
Corrected17 and later observations parse the operation ordering from the frozen
producing source. Positive/publication counts and the other checks were unaffected.

The full job keeps boot3M/10s, RPC100M/60s,400MiB/no swap,512MiB C-output reserve,
fresh margin checks and its writer lock. It was not restarted. No competing
compile or sampling ran. The new test/tracking docs are outside its input set.
Analysis uses192MiB/no swap, Nice19/CPUWeight1, fresh dual backing/RAM checks,
read-only C storage, an EROFS write control and zero C output. Systemd reports
q15 at92.4MiB peak/27.973s; this is not a firmware speedup or target benchmark.

## Remaining Work

The executable consumer contract now covers nonempty ordinary RX/TX as well as
the preceding NPU RX case set. It still does not establish complete consumer
ownership or physical retirement. Actual token/RRO owners, real SKB effects,
provider/endpoint devres, pool internals, context lifetime, containment/drain,
reuse/hot paths and current image/board/real-client acceptance remain open.
Do not fix that lifetime contract by retaining only a provider/device pointer.

Ethernet stays disconnected. No router contact, flash, Wi-Fi change, shutdown,
new compaction or protected-data cleanup occurred. Full NPU goal stays active.
Reproduction: `tests/npu/test_consumer_rxtx_native.py --producer RECEIPT
--expected-producer-sha256 HASH --source MT76_SOURCE --output FRESH_DIRECTORY`
under the documented bounded read-only environment. `--probe-only` is explicitly
not complete-matrix acceptance. Private receipts stay in
`.local/npu-consumer-native-20261027/`; EVIDENCE.json binds public/private hashes.
