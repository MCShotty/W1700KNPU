# RRO Lifetime Requirements

Status: operational implementation requirements, **not a qualified RRO ABI**.
The portable journal is now connected to actual retained provider allocations,
process-context mt76 calls, initializer errors and early closing handoff; see
`RRO_LIFETIME_CONTRACT.md` and the 2026-10-23 rro-provider checkpoint. Its host-C
tests and target module links do not qualify native/MCU admission, authenticated
completion identity, physical backing/coherency or retirement witnesses.
See `research/checkpoints/2026-10-23-npu-rro-lifetime/REPORT.md` for executed
caller, managed-bookkeeping and stock/current instruction evidence.

## Allocation Order

The checked provider now prepares its six retained TX buffers before the actual
`mt7996_wed_rro_init` call. Late `mt7996_npu_hw_init` validates the retained lease
and consumes its hardware attempt without allocating again. Generic providers
retain their previous allocation path. The checked provider's optional RRO open
now attaches an independent heap owner to the already retained DMA lifetime.
Its actual allocation path records CPU pointer, full DMA handle and length,
enrolls the exact slot, then returns caller outputs. Failed prefixes and invalid
nonnull backing remain owned. Only an open result of `-EOPNOTSUPP` permits the
legacy managed path; other open errors return without fallback.

Current prepared validation expects the captured pre-constructor client serial.
The admitted RRO protocol must explicitly coordinate its generation/serial
transition with that validation. Do not simply bypass the validator to make
additional commands fit. The current checked sender still rejects the first RRO
publication. Full allocation geometry is tested separately; no successful
current RRO publication was invented. This intermediate failure/retention path
is not the requested final operational state.

## Ownership

Current mt76 attachment assigns `dma_dev = npu->dev`. The owned RRO path uses
provider-retained coherent allocations, not either device's managed list. The
optional-provider legacy path can still belong to provider devres rather than
the PCI endpoint. Preserve both identities and their reference contract; an
endpoint disappearing must not make extents unaccounted for. The allocator/free
device, DMA handle, CPU pointer and full length must agree. Do not substitute
generic consumer-devres cleanup for provider retirement.

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

Generic sends hold RCU and use GFP_ATOMIC. New owned RRO calls hold the consumer
mutex and use process-context provider operations. Publication latches possible
exposure/ticket before invoking the existing checked sender, outside the provider
mutex, then completes that host invocation under the mutex. This is not an
authenticated firmware echo. Native admission/completion and the MCU worker's
atomic/process handoff and retained request identity still need implementation.
Keep selectors0/1/3's four-word payload distinct from scalar constructors2/7.

Owned publication errors now propagate through the higher initializer before RRO
hardware setup. Still preserve reset request identity/generation through NPU and
MCU errors, duplicates and late results. Validate session IDs before publication.
The existing reset worker does not yet invoke the retained journal; a freed work
item cannot represent unfinished reset ownership. Define retry deduplication.

## Retirement And Acceptance

Complete selected teardown includes `mt76_unregister_device`, `mt76_free_device`
and `mt76_npu_deinit`. Owned `mt7996_wed_rro_free` attempts closing and returns
before explicit managed frees, MCU/token/DMA cleanup and final lower detach.
Its ownership marker remains set even after mode changes/provider loss, so an
unavailable closing callback cannot trigger managed fallback. Lower detach also
attempts provider closing before unpublication. A lost provider may prevent the
callback; neither attempt nor failure grants free authority. Preserve all owners
and extents through failed initialization and ordinary unregister.

The lower detach's pointer unpublication, reader join and reference puts are
software lifetime operations, not physical NPU/firmware/DMA drain witnesses.
Earlier mac80211 callbacks and the modeled DMA/MCU boundaries could contain
other behavior; their relative position must not be used to invent a missing
hardware proof. The current 1,090 caller cases/seven controls separate 1,040
optional-provider cases from 50 modeled owned-provider cases. Actual provider,
journal and process bridges execute independently in 448 cases/four controls.
These suites are not full joint kernel execution. No actual CPU join or physical
retirement observation is recorded by the new closing calls.

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
