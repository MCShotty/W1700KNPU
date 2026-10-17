# RRO Caller And Retention Boundary

## Two Different Contracts

Constructors2/7 use the checked scalar4 payload. The generic RRO helper
`mt76_npu_send_txrx_addr` constructs four little-endian words:direction,
input-count address,output-status address and output-count address. It sends
those16 bytes with GFP_ATOMIC while holding RCU. Current higher calls use
selectors0/1/3 for element blocks,session table and reset. Their16-byte payload
cannot be treated as the scalar constructor contract.

The current checked provider rejects RRO0/1/3 before transport. Selectors2/7
with this16-byte shape also fail its actual length check before the session
mutex. This does not establish that arbitrary scalar4 requests are atomic-safe
or that the existing mutex-based client may be reused under RCU for future RRO.

## Actual Caller Fixture

`test_inode_rro_caller.py` compiles the actual helper,checked provider and existing
Linux client/portable server C. The public ops forwarding boundary and kernel
mutex/RCU/backing are explicit fixtures. It checks18 selector candidates/eight
payload vectors in both fresh and actual-initialized modeled C states:288
denials plus six null-provider cases. Every16-byte field is exact;RCU lookup/use
is balanced,including null. No modeled mutex or RPC is invoked and provider/
client/retained metadata stays byte-identical. No earlier native SETUP,lease,
original callback or checked RRO acceptance is asserted.

Receipt `.local/npu-inode-rro-caller/bridge-q1/result.json`,SHA256
`db0f59c45227cf04369e1c97e8bf033ba0e193ba786fa629ef9a27505e4007ad`.
Address/undefined/leak sanitizers pass. The complete higher-level initializer/
reset worker was not executed by this focused fixture.

## Original Instructions Rechecked

Fresh `test_inode_rro_original.py` executes137 original callback probes:all128
blocks,one session table,five reset boundaries and three additional aliases.
It checks exact original stores/whole SRAM and synthetic alias image,distinct
callee-saved registers/GP/TP/SP,MSTATUS and unchanged original CODE. Original
clear helper runs normally. No new Ghidra analysis or helper substitution.

Receipt `.local/npu-inode-rro-original/rro-bridge-q1/result.json`,SHA256
`b5177c055b2d6d6cbf471e6a6d00fc92095f8c968095b31fe4961c91e9740672`.
The original packet is24 bytes including header/API and four payload words;
the current caller fixture does not emit a native packet because it is denied.
Original probes use the real callers'zero tail arguments,not every arbitrary
vector tested by the rejected sender. Mathematical alias conversion remains
synthetic RAM,not a verified physical/PMA/cache mapping. See the earlier
[original effect table](../2026-10-16-npu-pcie-tail-native/RRO.md).

## Error And Managed Lifetime Gap

Source-only observations in current mt7996/init.c:

- Both RRO initialization publications ignore the returned error and continue.
- The reset worker ignores that error,then proceeds to the MCU reset/free-item
  path. No checked reset-generation or drain result is established by this.
- RRO storage uses dmam_alloc_coherent. The pinned6.18.52 kernel records a
  devres release which calls dma_free_attrs;device cleanup releases devres.

Consequently a future early-return-only error fix is not enough:once a
publication may have reached the NPU,the allocation/work item must remain
owned through ambiguous errors,late callbacks,detach and reset until independent
quiescence/drain is verified. This is source/design reasoning,not an executed
physical use-after-free demonstration. Exact DMA-device identity and cleanup
ordering still require the actual retained-lifetime port.

Implement retained block/session extents and identities,generations/order,
appropriate atomic/process handoff,checked higher errors,partial publication/
timeout/late completion and reset/drain together. These remain implementation
requirements;no source fix or checked RRO admission is claimed here.

## Seal And Unchanged Scope

`.local/npu-rro-bridge-20261017/scope-q1.json`,SHA256
`c5e611c65bcdf7928975bd327d9758481d89d825a88a62c9f06ba724ad4b1c5e`,
verifies108 current hashes and the294/137/five projection-unit scopes. Jev's
six bounded source judgments/probabilities are retained;its limited-confidence
denial judgment is not a broader runtime or physical proof.

No provider/RRO guard/source-lock,prepared object/module/FIT or hardware changed.
Current source-lock remainsf9f90ba5. Both full cold callers/eight-DESC10-fault
matrices remain live on600055c's preserved inputs;this report does not promote
their pending results or change their instruction/state/coverage limits.
No source-hash waiver,job restart,flash,reset,reclaim,radio or subagents.
