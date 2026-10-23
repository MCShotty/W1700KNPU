# RRO Lifetime Requirements

Status: implementation requirements, **not an implemented or qualified RRO ABI**.
See `research/checkpoints/2026-10-23-npu-rro-lifetime/REPORT.md` for executed
caller, managed-bookkeeping and stock/current instruction evidence.

## Ownership

Current mt76 attachment assigns `dma_dev = npu->dev`. RRO allocations can belong
to the provider's devres list, not the PCI endpoint's. Preserve both identities;
an endpoint disappearing must not make provider-owned extents unaccounted for.
The allocator/free device, DMA handle, CPU pointer and full length must agree.
Do not substitute generic consumer-devres cleanup for provider retirement.

The complete geometry is 128 element blocks of 65,536 bytes, plus an 8,192-byte
session table. Keep mode-dependent BA/MSDU/EMI allocations distinct. Preserve
the complete context, generation and publication order; a block index or DMA
address alone is not an ownership identity. Reject unrepresentable DMA addresses
before publication rather than silently narrowing `dma_addr_t` to `u32`.

## Publication And Errors

Define an explicit retained state for unpublished, possibly published, confirmed
and retirement-pending extents. A timeout/error is not evidence that publication
did not happen. Partial publication must retain the prefix and the ambiguous
current extent through late completion, initialization failure and detach.

Current generic sends hold RCU and use GFP_ATOMIC; the checked constructor path
uses a process-context session. Introduce the real atomic/process handoff and
retained request ownership, rather than calling sleeping transport under RCU.
Keep selectors0/1/3's four-word payload distinct from scalar constructors2/7.

Propagate errors through the higher initializer. Preserve reset request identity
and generation through NPU and MCU errors, including duplicates and late results.
Validate session IDs before any publication. A freed work item cannot represent
unfinished reset ownership. Retrying must have defined deduplication semantics.

## Retirement And Acceptance

The complete selected lower teardown is now executed in the RRO teardown
checkpoint, including `mt76_unregister_device`, `mt76_free_device` and
`mt76_npu_deinit`. In `mt7996_unregister_device`, explicit RRO frees precede
MCU/token/DMA cleanup and the final lower provider detach. Put the retained
ownership handoff before those explicit frees, not only in the final
`mt76_npu_deinit`. Preserve the provider/endpoint identities and every allocated
extent through failed initialization as well as ordinary unregister.

The lower detach's pointer unpublication, reader join and reference puts are
software lifetime operations, not physical NPU/firmware/DMA drain witnesses.
Earlier mac80211 callbacks and the modeled DMA/MCU boundaries could contain
other behavior; their relative position must not be used to invent a missing
hardware proof. The new 1,037-case characterization and three negative controls
do not implement or qualify the retained RRO ABI.

Connect retained allocations to the actual provider/consumer teardown paths.
Require independently established IRQ exclusion, DMA/firmware quiescence,
cache/PMA correctness and drain/reset ordering before reclaim. Do not infer a
physical drain from a successful callback, a model boundary, a device-managed
allocation, or the relative order of selected unregister calls.

Implement admission and retirement together, then test the complete current
callers with full geometry, all prefix failures, ambiguous/late completions,
reset, detach and provider removal. Rebuild and inspect the resulting modules
and image, then prove boot/physical DMA/radios/actual-client behavior. Permanent
RRO denial and an early-return-only patch are not the project's requested end
state. Existing checked guards remain until the retained implementation exists.
