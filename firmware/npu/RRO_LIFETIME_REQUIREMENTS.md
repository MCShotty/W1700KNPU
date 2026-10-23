# RRO Lifetime Requirements

Status: operational implementation requirements, **not a qualified RRO ABI**.
The portable journal is now connected to actual retained provider allocations,
process-context mt76 calls, initializer errors and early closing handoff; see
`RRO_LIFETIME_CONTRACT.md` and the 2026-10-23 rro-provider checkpoint. Its host-C
tests and target module links do not qualify native/MCU admission, authenticated
completion identity, physical backing/coherency or retirement witnesses.
See `research/checkpoints/2026-10-23-npu-rro-lifetime/REPORT.md` for executed
caller, managed-bookkeeping and stock/current instruction evidence.

## Current Retained Host BA Association

Status0 now snapshots actual RX-TID serial, original active WLAN/TID and primary
WCID into a separate preallocated1025-entry binding table attached to the pinned
owner. The table stays below32KiB; the existing owner stays below64KiB. All
unpublished allocation/reference failures unwind both objects. Published table,
records and pins remain independently retained; no event allocates a BA record.
Core association fields are write-once. Conflicting serial or tuple cannot rebind
the first association and retains the proposed fault metadata. Missing-owner
events still latch the pre-publication error; they cannot publish a later owner.

DELETE requires the retained session/WLAN/TID association and snapshots its BA
serial without looking up the current RX object. Work checks that snapshot and
tuple before the existing typed reset-generation/ticket operations. Generation1
is still the initial reset journal generation, not the BA creation serial.
Closed/faulted valid metadata remains held without new reset admission. No
provider-loss CPU fallback, production retirement/rearm or free authority is added.

The combined actual selected RX creation/shutdown/stop, AMPDU, per-link BA loop,
status/DELETE and complete owner C passes23 setups/14 controls. Separate worker
23/eight includes explicitly synthetic prior BA enrollment; real creation/status
is executed in the joint fixture. Framework scheduling/locks/references, provider
transport, IRQ-abort effect and physical MCU/backing/drain remain models.

First unseen cookie-less late status can still bind a replacement. Current
firmware reachability/order, association authentication and late/reuse fencing
remain unqualified. Close rejects later admission but is not a join for a status
writer already accepted before close; the final tid->id write follows helper
owner-lock release while retaining the TID lock/RCU. Full hot CPU lifetime must
cover these readers/writers before consumer or backing retirement. Parked-only
transport remains unchanged; no module-load/image/hardware/client proof follows.

## Allocation Order

The reconstructed `rro-native.c` engine now implements publication/reset byte
effects against retained extents with readback. This is one operational
implementation component, not the final admission or reclamation contract.
The new 256-byte client/codec/broker connects native-owned plan/enrollment and
exact correlated replies; host/native journal storage remains separate. Its
19,261 host RPCs/full-journal comparisons and five mutation controls are not full
cold target-transport, physical MCU or hardware proof. Qualify the ABI2 raw-pair
binding and current provider/module cohort before promoting any current image.

The checked provider now prepares its six retained TX buffers before the actual
`mt7996_wed_rro_init` call. Late `mt7996_npu_hw_init` validates the retained lease
and consumes its hardware attempt without allocating again. Generic providers
retain their previous allocation path. The checked provider's optional RRO open
now attaches an independent heap owner to the already retained DMA lifetime.
Its actual allocation path records CPU pointer, full DMA handle and length,
enrolls the exact slot, then returns caller outputs. Failed prefixes and invalid
nonnull backing remain owned. Only an open result of `-EOPNOTSUPP` permits the
legacy managed path; other open errors return without fallback.

The original TX allocation serial remains immutable. The typed provider now
tracks an explicit origin/control/accepted-step chain, extending it only for the
exact accepted reply sequence. Late TX validation checks this chain and retains
all original backing/handle/geometry/provider/endpoint/boot/nonce checks. Validate
serial corruption, unrelated advances and late/error replies jointly; do not
bypass the lease validator to make additional commands fit. Native pair and
provider integration are under qualification, not physical acceptance.

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
exposure/ticket before the dedicated typed call, while holding the provider
process mutex. The control mutex serializes the accepted reply. Exact echo
correlates identities and full payload; it is not cryptographic authentication.
Typed provider NPU-reset/MCU-begin/MCU-complete handoff is now connected to the
retained worker. BA-lifetime identity and hot transport remain incomplete.
Independent host work retention is implemented as described below. The
broker's MCU messages accept a host-reported correlated
result; the host test models success and cannot establish a physical response.
Keep selectors0/1/3's four-word payload distinct from scalar constructors2/7.

Owned publication errors now propagate through the higher initializer before RRO
hardware setup. Still preserve reset request identity/generation through NPU and
MCU errors, duplicates and late results. Validate session IDs before publication.
The owned reset worker now uses independently retained preallocated records,
not legacy disposable items. It now invokes the typed reset journal through
process-context provider bridges and keeps raw MCU/completion-bridge results
separate. Its one-shot initial journal generation does not authenticate a BA.
Pending identical tuples deduplicate; conflicts/completed-slot reuse stop the
owner. This fail-closed policy is not a qualified firmware retry/reuse fence.

## Current Device-Local RX-TID Creation Identity

The ba-creation checkpoint adds an immutable nonzero u64 serial to each actual
successfully allocated RX-TID before its RCU publication. A per-mt76-device
sequence is protected by the existing device mutex. Failed allocation consumes
no serial. MCU failure does not recycle a published serial. Exhaustion returns
EOVERFLOW before shutting down an existing object; ordinary ENOMEM still follows
the existing stop-before-allocation behavior. No BA stop/recovery reset is added.

The actual selected creation/shutdown/stop/AMPDU/per-link BA/event suite passes19
measured setups/12 compiled controls, including distinct WCID/TID creations and
the final u64 value. Framework/concurrency/physical MCU remain host models.
Current BA18/six, worker22/eight, joint6150 resets/12 negatives/three controls,
broad456/four, callers1090/seven and142 units pass; all four modules link.

This serial is not carried by current firmware events and has not yet been
propagated into immutable retained BA status/delete/reset associations. It is
neither a host arrival ordinal nor a reset-journal generation. An injected
cookie-less late status still selects the replacement even when creation serials
differ. This proves host indistinguishability, not real firmware reachability.
A current-build firmware cookie or qualified late/reuse fence remains required.
No hot admission, production retirement/rearm, DMA drain or free authority follows.

## BA Lifetime And MCU Identity

The ba-link checkpoint executes the actual RX-TID start/shutdown/stop, AMPDU,
per-link RX BA loop and status parser together in14 measured host setups/seven
controls. The status path now follows def_wcid and takes tid->lock, rejecting an
already stopped object under the same lock as shutdown. RCU protects lookup and
disposal; RCU scheduling, locks, nested types, allocation, active-link iteration,
work and physical MCU remain models, not kernel-concurrency qualification.

The host fixture injects an old-looking status after replacement and observes
the current slot receiving it. This establishes host indistinguishability, not
real-firmware reachability/order or a physical race. A current-build firmware
cookie or qualified reuse fence remains required. No actual BA token/generation
was created by this fix. MCU errors retain the published context, including
partial per-link enable; no physical rollback/free authority is established.
Current BA18/six, worker22/eight, joint6150 resets/12 negatives/three controls,
broad456/four, callers1090/seven and142 units pass; all four target modules link.
Parked-only guards, hot admission and physical-retirement limits remain unchanged.

The current status handler requires the complete little-endian32 status to be
zero before WCID/TID lookup and session-ID assignment. Nonzero statuses advance
to later TLVs without rebinding or a cached-pointer status3 retry. Legacy DELETE
IDs above1024 are rejected before allocation;1024 remains valid. The owned route
comes first and retains invalid tuples/errors rather than silently discarding
them. Current selected-C BA coverage is18 measured setups/six controls. The old
hardcoded15 label measured14 setups; all old assertions remain, plus four new
setups. These rules are not a BA-lifetime or reuse-fence witness.

The selected MCU status handler resolves `wlan_id`, follows the primary
`def_wcid` mapping and finds the current `tid` slot before assigning the firmware
session ID under the TID lock. It rejects an already stopped object. RX BA start first
stops an old object in that slot and publishes a new one. The tuple therefore
does not by itself distinguish BA lifetimes. The selected delete event carries
session ID/WLAN/TID. Legacy queued items retain all three fields after the BA
integrity checkpoint, but legacy worker error/disposal behavior is unchanged.
The owned lane now retains the tuple, host arrival ordinal, raw NPU/MCU results
and possible/acknowledged phases in an independent module/device-pinned owner.
NPU error blocks the later MCU call, MCU error stays sticky, and provider loss
cannot choose the legacy CPU-memory fallback. Close precedes cancellation and
software join; requests/pins remain retained after consumer teardown. No published
owner retirement or transparent rearm exists. Legacy selector3 remains denied;
the dedicated typed path still requires parked workers, not hot operational
admission. Exact late MCU results can update retained host metadata after close
without a new RPC or CPU join/reclamation authority.

Owner publication and the missing-owner event path share the admission lock.
An enqueue that initially sees NULL rechecks under that lock, so an intervening
publication receives the exact tuple. If the event wins first, its sticky
ENODEV prevents later owner publication and higher init stops before extents.
This pre-owner failure retains an error, not a tuple or BA lifetime. Two explicit
host interleavings and intended-failure controls cover these software decisions;
they are not kernel concurrency or firmware-ordering qualification.

Create a BA-lifetime token at actual RX-TID creation and a separate reset
generation/ticket when an immutable retained reset request is first issued.
Keep WLAN/TID/session/BA association through queued work, errors, retries and
late completions. A wrapping four-bit MCU command sequence correlates a command
transaction; it is not a BA generation. Do not derive an event's generation
from whichever journal or TID object happens to be current when it arrives.
If the firmware event cannot echo a lifetime cookie, qualify an actual ordering/
reuse fence before rebinding a slot or session ID. Merely adding a host counter
does not establish that fence. These are open integration requirements, not
claims of a demonstrated physical race or a newly qualified MCU contract.

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
hardware proof. The refreshed 1,090 caller cases/seven controls separate 1,040
optional-provider cases from 50 modeled owned-provider cases. Actual provider,
journal and process bridges execute independently in456 allocation/fault cases/
four controls, plus6150 reset transactions/12 negatives/three controls.
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
