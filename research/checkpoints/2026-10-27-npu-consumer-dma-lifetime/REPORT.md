# Consumer DMA Ownership During Cold Cleanup

## Scope

Continued solo from `e5cf6a54d38508333af53bb8523524bf627c71f4` while the
qualified profile6 full native replay runs unchanged. This checkpoint closes
a source-ownership investigation, not physical retirement or implementation.
No compiler, kernel/module execution, target contact, image build or flash ran.

The audit matches seven current mt76/provider source files to the retained
four-module producer `a840d3cccb1d0bd8cc60a856d1a1bb9723dfc05af73484d955a33978a458d22f`.
Five Linux 6.18.52 reference files match the retained 91236-entry source
inventory `83e832d8071cd2de382320390195f56c58116af14931755f0d55d26fefe59f18`.
Only these selected source files were rehashed; no complete inventory was rerun.
Twenty structural assertions and 26 selected functions retain locations and
digests in `EVIDENCE.json`. These counts are not executed lifetime-test cases.

## Allocation And Release Domains

| Resource | Current Owner | Current Release Or Retention |
| --- | --- | --- |
| Provider mailboxes, six TX buffers, special RX-event and RRO allocations | Explicit provider DMA lifetime | Retained after exposure or RRO creation pending physical retirement proof |
| Ordinary descriptor rings, including NPU0/1 RX | `dmam_alloc_coherent(dev->dma_dev)` | Provider-device devres after NPU admission selects `npu->dev`; not transferred into the explicit retained owner |
| Queue entry metadata | `devm_kzalloc(dev->dev)` | Consumer endpoint devres |
| Consumer NPU RX packet pages and page pools | mt76 queues and their page pools | Queue cleanup returns buffers; shared DMA cleanup calls `page_pool_destroy` |
| mt76/mt7996 context and queue objects | ieee80211 hardware context | `mt76_free_device` releases provider references then frees hardware context |

The provider-owned RX-event exception checks one exact TXFREE queue and flags.
It does not turn every receive descriptor ring into an explicitly retained
provider allocation. Likewise, retaining `life->endpoint` or `life->dev` does
not transfer the endpoint's managed allocations or the consumer's pages.

The source trace is deliberately narrower than a complete allocation census:
TX payload/token/RXWI, wider RRO page maps, generic-provider fallbacks and every
HIF2/hot path still need full ownership and failure-path coverage.

## Cleanup Evidence

`mt7996_cleanup_device` closes work and CPU ingress, invokes the void
`mt7996_mcu_exit`, then continues to token and DMA cleanup without a returned
MCU-success gate. `mt7996_dma_cleanup` issues reset/disable writes before shared
DMA cleanup. The selected disable helper has no returned idle result or poll.
This does not establish what those writes or firmware-state transitions mean
on physical hardware; no physical DMA fault is demonstrated.

For NPU RX queues, `mt76_dma_rx_cleanup` invokes `mt76_npu_queue_cleanup`,
which returns every queued page. The shared cleanup then destroys the pool.
The Linux reference `page_pool_release` calls `page_pool_scrub` before checking
inflight pages. Scrub can unmap outstanding DMA mappings before delayed pool
destruction finishes. Thus delayed pool release is not, by itself, a witness
that mappings or device-visible buffers remain available until a hardware drain.

The Linux unbind source invokes driver remove before `device_unbind_cleanup`,
which releases devres without an ordinary outstanding-device-reference gate.
Managed DMA release calls the DMA free operation. A device reference preserves
the device object, not an attached driver's managed allocation lifetime.

The selected generic PCI remove helper has no bus-master-clear call. The shown
conditional clear belongs to kexec shutdown, a different lifecycle path. This
bounded source observation is not proof that no other PCI path disables DMA,
nor that clearing PCI bus mastering alone drains radio and SoC NPU engines.

## Required Implementation And Qualification

1. Establish the actual MCU/radio/NPU containment or drain decision, including
   error and partial-initialization paths. An enqueue return or requested ACK
   is not automatically a completion witness.
2. Bind an explicit consumer owner to every possibly device-visible resource.
   On uncertain retirement, preserve pages and mappings, descriptor storage,
   metadata and required context across both endpoint and provider devres
   release. Retaining only a provider pointer or a pool object is insufficient.
3. Gate token/page/descriptor/context release on that decision after CPU joins.
   Prove failure-path retention and successful release exactly once with actual
   selected C and kernel APIs, then qualify complete target/HIF2/hot paths.
4. Obtain physical W1700K reset/drain, reuse, current-image and actual-client
   evidence before claiming retirement, stock parity or full NPU completion.

These are the next implementation requirements, not an implemented fix.

## Live Replay Observation

The same `w1700k-npu-native-block-hook-full-q21.service` invocation
`6c1bc5ff20d74add9235553e70e26931` is verified through actual process arguments,
parentage, start ticks and cgroup membership: guard18906, wrapper18920,
driver18942. Two samples add 242 driver CPU ticks. The retained complete-line
profile0 journal prefix contains157 checked positive RPCs:
OPEN1, ENROLL139, PUBLISH17. It is not an atomic guest snapshot or a full verdict.

All294 frozen input bindings rehash. None of the traced production/reference
source or tracking documents is bound by this native replay. No bound input,
instruction/time/I/O/count check,400MiB/no-swap cap, storage lock or margin was
changed. The original replay was not restarted and no competing compilation
was launched. Preserve its original producing commit even as these unbound
tracking documents change. Future observations must inspect actual status;
this finite live observation is not a promise of later success.

## Jev And Preserved Attempts

The official TypeSafe helper used `jev-1.13.0` for seven source-claim questions;
raw probabilities, request hash, model and usage remain retained. The question
whether page-pool deferred release preserves DMA until all inflight returns is
uncertain at0.59. Direct source inspection and structural ordering show scrub
before inflight and DMA unmapping inside scrub; the model answer is not used as
acceptance. Provider-page coverage0.11, ordinary-reference gate0.22, MCU-success
gate0.05 and physical-fault proof0.04 likewise do not substitute for tests.
The request follows the [official System One API](https://docs.typesafe.ai/api/system-one).

The first source extractor rejects `dmam_alloc_attrs`' void-pointer return and
exits1 before writing evidence or a Jev request. Its helper and failure note
remain unchanged. A fresh helper adds an exact uniqueness-checked signature
using the existing mask/braced extraction helpers. No production source,
assertion or runtime guard was changed to obtain the source characterization.

## Unchanged Boundaries

The earlier approved VHD compaction remains complete at78MiB reclaimed; no new
shutdown, compaction or deletion occurred. Six pre-existing tracking document
bodies are preserved byte-for-byte. Source lock88502ab3, mt76 patchbb457928,
kernel patchaacc0ffc and four-module producera840d3cc remain unchanged.
No firmware implementation, module/image/load, router contact or flash changed.
Full native, physical ownership/drain, BA reuse/hot lifecycle, current image,
actual clients, performance and stability remain open. The full goal is active.
