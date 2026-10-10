# Linux V2 Control Executor

`linux-control.c/.h` bind the existing V2 client to a Linux mutex and the
provider's `airoha_npu_wlan_control()` transport. The 2026-10-10 provider-session
change moves these canonical objects from mt76 into `airoha_npu.ko`. The checked
provider now owns one executor and its existing reserved-memory callback invokes
the initial held-session sequence. Recovery and full strict RX/TXDONE setup are
not implemented.

The 2026-10-10 provider validates the checked pair, publishes its private native
memory/request plan and fresh runtime identity to SRAM, and retains exposed
mailboxes/device/module lifetime. Boot writes and checked version replies now
gate provider publication, with one launch attempt and no failed-operation retry
or reclamation. This is software publication/retention, not independently proven
physical cold containment. The provider-session checkpoint adds the CPU/wire
owner described below, without supplying the separate physical contract.
See `research/checkpoints/2026-10-10-npu-boot-launch/REPORT.md` and the preceding
loader-publication checkpoint. The reserved prefix is now wired; full strict
native setup remains denied.

## Ownership

The caller must initialize an unpublished, zeroed executor exactly once, using a
fresh nonzero nonce. Initialization must not race other operations. This enrolls
a CPU/wire client only. Earlier initializer comments bundled enrollment with the
independent physical cold-containment prerequisite; that requirement remains for
hardware setup and any eventual release/rearm, but initialization does not prove
or perform it. A new mt76 attachment never establishes a new provider boot.

The checked provider embeds the executor and serializes its entire setup attempt,
nonce generation and close under a separate setup mutex. It consumes the attempt
before RNG or transport. DISCOVER must match the loader's published boot identity
and initial held epoch before any reserved-memory command is sent. The six
existing commands run between DISCOVER and BIND, then STOP and at most 100 STATUS
polls require all eight software workers parked in epoch 1 with release, arm,
ready and drain fields zero. A final snapshot accepts parking on the last poll.

The first failed attempt is permanent and retains its error. A repeat call after
success returns `-EBUSY`; it cannot mint another nonce or repeat setup. Provider
devres closes this CPU session before its IRQ/work/lease cleanup. It does not
reset or free exposed mailboxes. Existing consumer references/device links still
own the wider CPU lifetime; this mutex is not a join for every independent user.

An external caller already owns the provider reference. It must retain it until close
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
perform that setup or bypass the firmware BIND gate. The provider-owned wrapper
now performs the exact reserved prefix; the executor's operation contract is
unchanged.

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

## Initial Cold Commands

`cold-setup.h` defines a distinct80-byte NCS2/NCR2 envelope on GET-selector15,
API1. It reuses the already-bound provider nonce, loader boot identity, epoch1
and the same client ticket/server sequence, never a new attachment session.
The Linux cold exchange is serialized by the executor mutex; provider callback
wrappers also hold the setup mutex so CPU close joins this path.

The implemented commands are the post-BIND version query, two BAR0 metadata
bindings, port type2, checked RX0/RX2 DESC, then page5/6/7 address/DESC pairs.
Version can be queried again; mutating commands are ordered and one-shot. The
64-byte native cold owner stores the bound window and exact completed prefix.
The real mt7996 PCI caller passes BAR0 start and length to mt76 initialization;
the provider sends both metadata commands before mt76 publishes NPU/PPE pointers.
Wrong port type, truncation, alignment/span or bootstrap-region overlap rejects
before host transport. Native checks independently repeat geometry and ordering.

RX0 permits1..1536 descriptors; RX2 permits1..1024. Their first authenticated
callback initializes packet ownership from the pinned plan. Page5/6/7 addresses
must match BAR0+0xd45a0/0xd45b0/0xd45c0, and DESC limits are256/512/1024. First
authenticated DESC5 initializes BA ownership. Tests do not seed active or call
either initializer for this lane. The actual txrx sender reaches unsupported
indication selector8 next; INODE/TXDONE/full setup remains incomplete. BAR bounds
are software geometry, not proof of physical PCI ownership or DMA visibility.

Native begin verifies the pinned transport/envelope and copies a private packet
snapshot. Binding, sequence, completed bootstrap and held initial barrier state
must agree, including no active callback, fault, deferred IRQ, release, arm,
ready or drain observation. Only then does it acquire the software callback
lease. Valid bound sequences are reserved before command/platform checks; an
abandoned rejected request cannot become effective when replayed later.

Completion revalidates the identity, nonce, sequence, held state, bound window
and immutable command/history. Successful callbacks return their software lease to zero;
ambiguous failure retains active/inflight ownership and faults admission.
Neither outcome permits physical resource release, DMA retirement or rearm.
Client errors stay sticky and reply errors do not modify the caller's output.
Fresh zero native cold-owner storage belongs to the checked provider boot; no
reset/reinitialization API exists. Old checked firmware without this endpoint
rejects the envelope, and the new host holds rather than falling back to an
unbound callback. Unmarked provider callbacks preserve their raw dispatch.

## Kernel Build

The existing portable protocol sources remain unchanged. For the selected
kernel objects only, `kernel-include/stdint.h` supplies the kernel's fixed-width
types and limit macro. It must not be placed on an unrelated or userspace include
path. The provider links the executor, `control-client.c` and
`control-v2-client.c` and `cold-client.c` together. A small `provider-main.c` translation-unit wrapper
preserves the established `airoha_npu.c` source path and module filename while
allowing Kbuild to link the separate protocol objects. They are no longer linked
into each mt76 consumer. Canonical source-lock mappings copy the exact sources
into the selected target's kernel files overlay.

Evidence and exact replay instructions are in
`research/checkpoints/2026-09-23-npu-linux-control/REPORT.md`. The host tests use
pthreads for kernel mutexes and modeled regmap/coherent storage/delivery. Their
server is standalone V2, not the native cold-bootstrap binding. Two AArch64
modules check the enabled provider API and a forced-disabled header profile;
neither module is loaded. The newer provider-session tests execute the real
Linux setup/executor against the native assembled pair and C-published DATA.
Backing, delivery, host pointer publication and worker scheduling remain modeled.
Full strict callbacks, wider lifecycle and physical containment/drain/recovery
remain required for complete NPU recovery.
