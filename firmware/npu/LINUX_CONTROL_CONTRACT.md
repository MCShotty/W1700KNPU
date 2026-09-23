# Linux V2 Control Executor

`linux-control.c/.h` bind the existing V2 client to a Linux mutex and the
provider's `airoha_npu_wlan_control()` transport. The 2026-09-23 unified merge
compiles these canonical sources into mt76. Cold-session initialization and
actual setup/recovery callers are not yet implemented.

## Ownership

The caller must initialize an unpublished, zeroed executor exactly once for an
independently contained cold provider lifetime, using a fresh nonzero nonce.
Initialization must not race other operations. A new mt76 attachment alone does
not establish that lifetime, and this API does not fabricate a boot identity.
The production loader and the owner that anchors this state remain open work.

The caller already owns the provider reference. It must retain it until close
returns, and retain the executor allocation until every API caller retires.
The executor neither gets nor puts a provider reference. Its fields are private
to these functions; callers inspect state through the snapshot function.

Initialization failure also consumes the instance. Reinitialization returns
`-EALREADY` before altering its mutex, nonce, sequence, error or provider. A
failed or closed instance is not a recovery mechanism for an existing NPU boot.

## Exchanges

The caller supplies the intended operation. The executor checks it against the
existing client's next operation before creating any request:

- NEW: DISCOVER.
- DISCOVERED: BIND.
- BOUND: STOP.
- STOPPING or PARKED: STATUS.

This preserves the current client contract. It does not add running-state
STATUS, restart or arm operations. In the bootstrap profile the caller must
complete the required setup between DISCOVER and BIND; this executor does not
perform that setup or bypass the firmware BIND gate.

One mutex covers operation selection, ticket creation, the synchronous provider
call and complete reply validation. A repeated BIND therefore cannot silently
execute the client's next STOP. Unexpected operations permanently hold the
instance. Transport and protocol failures also hold it; positive transport
errors are normalized to `-EIO`, and the first error remains visible after close.

The 80-byte stack packet is copied into the provider's coherent buffer before
publication. The provider retains only its coherent copy after a timeout and
does not retain the caller's pointer. This is the existing provider ownership
contract, not evidence of physical DMA or cache correctness.

Success means that the structured reply was accepted. PARKED remains a software
observation. No result authorizes DMA buffer release, token/ring cleanup, rearm
or reset. The provider's pending transaction and device-visible resources still
need independent retirement even after the CPU call returns.

## Close And Inspection

Close acquires the same mutex, waits for any executing exchange, permanently
aborts the client, and clears the executor's provider pointer. Queued later
exchanges observe the retained error and do not call the provider. Repeated
close is idempotent. This joins this executor's CPU calls only; it does not join
other users of the provider or establish device drain/containment.

The snapshot function copies the complete client/error/closed state under the
mutex. It returns no provider pointer or resource-release permission.

## Kernel Build

The existing portable protocol sources remain unchanged. For the selected
kernel objects only, `kernel-include/stdint.h` supplies the kernel's fixed-width
types and limit macro. It must not be placed on an unrelated or userspace include
path. The caller must link the executor, `control-client.c` and
`control-v2-client.c` together with the provider export available. The unified
OpenWrt patch series and source-lock component mappings perform this build.

Evidence and exact replay instructions are in
`research/checkpoints/2026-09-23-npu-linux-control/REPORT.md`. The host tests use
pthreads for kernel mutexes and modeled regmap/coherent storage/delivery. Their
server is standalone V2, not the native cold-bootstrap binding. Two AArch64
modules check the enabled provider API and a forced-disabled header profile;
neither module is loaded. Production initialization/loader identity, mt76
caller wiring, native bootstrap composition, full lifecycle and physical
drain/recovery remain required for complete NPU recovery.
