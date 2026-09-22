# Hart-7 Bridge Startup And Failure Guards

2026-09-09. Status: native post-gate path reconstructed; two compiled,
unpromoted failure guards tested. Full cold-start permission, containment,
recovery and NPU parity remain incomplete. No router or Wi-Fi changes.

## Native Path

After the hart7 startup site at `0x84000b24`, the original firmware calls the
bridge initializer at `0x84001472`, clears the service's software state through
`0x84001392`, then reaches the retained outer gate at `0x84000b36`.

The bridge initializer executes the native allocator for type `0x81` and:

- Publishes the returned pointer at SRAM `0x3e90184c`.
- Writes its low29 bits to `0x1ec12008`, `0x40800` to `0x1ec12010`, and1 to
  `0x1ec12018`.
- Executes the original `delay1ms(10)` routine at `0x84003712`.
- Reads bit0 at `0x1ec12210 + channel*16` for each of eight channels, chooses a
  success/failure log, and writes1 to each status address.
- Returns0 even after a null allocation or any failed channel status. The
  following native routine clears15 words/60 bytes at SRAM `0x3e900c54`.

Original reset, core0 bootstrap, hart7 prologue, allocator lookup/locking,
delay, initializer and software-state clear execute. Initializer, allocator
and delay returns are not stubbed. Existing printf and hart-ID substitutions
are explicit; bridge status, timer and mutex register behavior are models.

These are instruction-level findings under supplied register conditions, not
observed W1700K failures. The first startup gate is deliberately omitted only
in the post-gate analysis fixture; no release, drain, prepare or arm is faked
to reach the initializer. The original outer gate remains installed.

## Implemented Candidate

`tests/npu/bridge-startup-emulation.S` supplies two guards:

| Native site | Preimage | Guard behavior |
| --- | --- | --- |
| `0x8400148a` | `aa87aa85` | Reject null allocator result before global/MMIO base publication; otherwise replay both native moves |
| `0x84001500` | `91e35685` | Reject clear channel status before its native write-one; otherwise follow the original successful branch |

Failure disables local machine interrupts, executes `fence iorw, iorw`,
publishes the existing atomic barrier fault and holds permanently. Hart7
does not write coordinator-owned admission fields or publish a parked/ready
acknowledgement from this failed initializer. No cache clear, further channel
write, service-loop return, resource free or automatic retry follows.

The compiled sidecar contains88 text bytes at the separate emulator-only
reservation `0x84048000..0x84048058`. It imports symbol addresses from the
hash-verified existing candidate ELF; that ELF is not rebuilt or modified.
Disassembly confirms the two native continuations, MSTATUS clear, I/O fence,
call to `npu_barrier_fail` at `0x840400a8`, and the two permanent holds.
This is not a production code-placement or physical cache/coherency proof.

The fence orders issued I/O; it does not drain the bridge or prove earlier
hardware writes completed. Channel failures occur after base/control writes
and possibly earlier channel writes. That partial hardware ownership remains
retained and unresolved, not cleaned up or certified quiescent by this guard.

## Verification

The complete matrix contains26 original and26 guarded native cases. Both
plain-storage and write-one-to-clear hypotheses cover normal status, each
single missing channel bit, all missing bits, allocator exhaustion, disabled
timer and wrong allocator-lock owner.

- All26 original cases reach service-state clear and the outer gate.
- Twenty guarded failures hold: two null allocations and18 channel failures.
  The old bridge pointer marker is preserved on allocation failure. Channel
  failures preserve the service-state marker and stop the native write-one
  sequence at the first failed channel.
- In all18 channel failures, later ready values for the failed and remaining
  channels do not resume execution, issue more I/O or clear the fault.
- Six non-faulting controls retain the original memory and register results.
  This includes disabled-timer/wrong-owner controls and is explicitly not a
  declaration that those hardware states are valid.
- Every case compares the entire32KiB local SRAM against an independent
  expected image, checks all480KiB modeled heap bytes unchanged and verifies
  the whole256KiB L2 image unchanged. Allocator metadata, alignment, pointer
  publication, service-state clearing and protocol writes are accounted for.
- Actual strict coordinator STATUS replies report fault6 and parked mask1
  after guarded failure. Original failures still report status0 and mask0x81.
  Capability bits remain7, without safe-reclaim/restart; ready, drain,
  released and armed fields remain zero. STATUS leaves protocol state intact.

Seven mutation/installation controls detect omitted base/channel tests, either
missing native hook, missing IRQ masking, missing barrier fault publication
and missing I/O fence. Every corrected trace requires actual guard-entry
witnesses. Four missing-register models stop explicitly at the base write,
channel read, hart7 allocator-owner read and timer counter read.

A separate control retains the initial gate and installs all28 detours. All
eight harts enter through their actual reset/prologue paths, park, and repoll
in order0/7/1/2/3/4/5/6. The coordinator reports mask0xff; there is no bridge
access or allocation and all ready/drain/release/arm fields remain zero. This
is one serialized banked-PLIC-storage schedule, not physical concurrency or
interrupt-delivery proof. The guards do not open cold-start admission.

The runner verifies61 local input hashes before/after execution. It uses
Python3.14.4, Unicorn2.1.4 and Clang21.1.8. Its saved JSON includes exact
native function spans from the existing Ghidra export, per-case register
traces, source hashes, compiler command and candidate disassembly.
The complete `--check` replay matches the saved receipt byte-for-byte.

The first mixed original/guarded run exposed stale Unicorn translated blocks:
the patched instruction bytes were present but the old translation executed.
The harness now invalidates both affected native blocks and the sidecar range,
and checks executed guard entries. This was a harness correction, not a native
firmware finding. Plain-storage and W1C models are kept distinct; W1C preserves
the unmodified status bits. Neither hypothesis is asserted to be the hardware.

## Remaining Contracts

### Allocator Ownership

The native allocator ignores the return from its lock helper. With the supplied
hart7 owner register indicating owner0, the actual helper returns `0xffffffff`
and allocation still proceeds. Both original and guarded startup accept that
case. This is a separate conditional ownership finding, not fixed by these
bridge guards. Hardware lock-read/grant behavior and serialized cold-allocation
requirements need closure before checked startup can be claimed.

### Buffer Extent

The native high dynamic table requests58879 bytes (`0xe5ff`) for type0x81.
In this core0-completed fixture, allocation changes the entry count6 to7 and
used bytes430288 to489183, returning aligned base `0x3e8690e0`. The allocated
end is `0x3e8776df`, within the modeled heap end `0x3e878000`.

The initializer prints a64KiB buffer window, and helper `0x84001466` computes
base+`0x10000`. A full64KiB envelope from this base would end at `0x3e8790e0`,
4320 bytes beyond that heap boundary. This is an unresolved contract discrepancy,
not a demonstrated DMA overrun: the actual geometry encoded by `0x40800`,
reachable packet extents and physical backing have not been proved. The table
or memory reservation was not resized on the basis of the print string.

### Timer And External Owners

With the timer disabled, the original delay returns immediately and all-ready
channel inputs still pass. The guards do not establish a bounded real-time
initialization wait. The timer model advances only on counter reads; it is not
clock-frequency or elapsed-time evidence.

The current kernel's `airoha_fe_init()` also configures IP-fragment forwarding
toward NPU bridge channel3 (`airoha_eth.c:621..625`), consistent with the earlier
[upstream Ethernet patch](https://lists.infradead.org/pipermail/linux-arm-kernel/2024-June/937510.html).
That source context reinforces the need to cover external ingress owners; it
does not specify the bridge registers or prove physical routing/drain behavior.

Complete post-gate initialization for other harts, checked cold-init permission,
remaining native callbacks, full loader/placement/cache integration, physical
bridge/copy/PPE/Wi-Fi containment and safe reset/removal remain open. The existing
INODE-provider and native DESC5/6/7/8 restrictions were not retried or rerouted.
No production firmware patch or image is emitted by this checkpoint.

## Reproduction

From the canonical WSL repository:

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_bridge_startup.py
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_bridge_startup.py --check
```

The full authoritative receipt is `native-startup.json`; `native-smoke.json`
is only a reduced development smoke receipt. Generated ELF files remain under
ignored `.local/npu-bridge-startup/`. The original candidate ELF SHA256 remains
`bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931`.

SHA256:

```text
guard assembly cec1ac3003e121ef122519960cdb83a7ca72f5103486a9b67a3273d92eb771d8
guard linker   0c9a6cd2485d079a2fbfa41c646b39a05303170d8236167f93647e69ed233d78
guard ELF      75adfdfd5671a960e8323a7646f015de863ab0a957d750f9f3c7439ee2171d33
test runner    7a5568a7f7dfcd96c25855ca1262ae7306f03a36e7701a873be01975fdef765e
full receipt   4cd24f6a5f30d59feabcf88c6277f7af4a080d53f6e4cf650260685c50d66170
```

NPU-only, codebase-only work continues. No subagents, physical tests, router
contact, Wi-Fi/configuration changes, protected-data changes or Git publication.
The source lock and cumulative patches remain unchanged. The four canonical
trackers record this component without marking full NPU parity complete.
