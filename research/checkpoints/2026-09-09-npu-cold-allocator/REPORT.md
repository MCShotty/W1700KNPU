# Checked Startup Allocation And Core0 Fault Service

2026-09-09. Status: seven core0 startup allocation calls and hart7's bridge
allocation now use the checked allocator in an unpromoted emulator candidate.
Core0 failures retain control-mailbox service in the verified interrupt context.
This is not global callback integration, physical containment or full NPU parity.

## Native Ordering

Actual core0 reset/initialization traces establish that all seven dynamic
startup allocations, including the type-`0x89` control word, occur after the
strict mailbox handler is installed. At every call, MSTATUS has MIE set,
MIE includes external interrupts, IRQ8 points to `npu_emulation_mailbox`,
admission has no active callback, and bootstrap magic is initialized.

The earlier possibility of a pre-IRQ control-word allocation was a hypothesis,
not evidence. These traces support using the existing coordinator idle and
mailbox path; no new polled mailbox transport was added.

The original allocator still ignores a failed lock-owner return. A baseline
with the preceding reset-lifetime correction installed but this new getter
hook omitted injects owner failure for type `0x8a`. The actual acquire returns
`0xffffffff`, yet native core0 initialization completes and reports idle ACK
with no barrier fault. This is a modeled owner input, not a live device failure.

## Implemented Binding

The native getter's first instruction at `0x84005200` is replaced only in
emulator memory: `13070008` becomes `6f90a43c`, jumping to dispatch at
`0x8404e5ca`. The assembly selects the following original return addresses:

| Hart | Allocation type | Original caller return PC |
| --- | --- | --- |
| 0 | `0x89` | `0x84005a34` |
| 0 | `0x8a` | `0x84004eca` |
| 0 | `0x12` | `0x84004eee` |
| 0 | `0x1d` | `0x84004f2c` |
| 0 | `0x01` | `0x8400b932` |
| 0 | `0x0b` | `0x8400a376` |
| 0 | `0x19` | `0x8400bab8` |
| 7 | `0x81` | `0x8400148a` |

All other call sites replay the displaced `li a4, 0x80` and continue at
`0x84005204`. Fixed-L2 lookup paths remain native. This is a reviewed-startup
binding, not a claim that all dynamic allocation users are checked.

`allocator-startup-emulation.c` masks local interrupts, checks the expected
hart/type/caller and cold protocol state, then uses the unchanged checked C
allocator with the original ROM definitions and native lock routines. The
request epoch must be 1, with no fault, preparation, release, arm or existing
parked acknowledgement for the caller. Admission/bootstrap must be valid and
have no active or in-flight callback. Invalid types/roles are rejected before
indexing the hart slot. Lock ID must be 18 before requesting hardware ownership.

For core0, control service is allowed only when the saved interrupt state has
MIE set, external interrupts are enabled, the exact strict IRQ8 handler is
installed, its PLIC source is enabled and no callback is active. Those are
verified software/register conditions, not physical interrupt-delivery proof.

On allocation or post-allocation fault, an I/O fence precedes fault publication:

- Core0 sets admission closed/fault and the shared barrier fault. In the
  verified service context it restores the saved interrupt state and enters
  the existing `npu_emulation_idle()`. The failed native caller never resumes.
- Otherwise core0 holds permanently with interrupts disabled. It does not
  invent an IRQ handler, unwind an active callback or claim mailbox availability.
- Hart7 publishes only the shared barrier fault and holds with interrupts
  disabled. It does not write coordinator-owned admission fields.
- Failed ownership never releases the unowned lock. Rejected allocation leaves
  metadata intact. A fault arriving at successful unlock retains the newly
  committed allocation instead of rolling it back or publishing its pointer.

There is no free, retry, allocator reset, new parked/ready acknowledgement,
physical drain, release or restart authorization on these failure paths.

The new combined component contains 1,594 text bytes at `0x8404e000` and
24 read-only bytes at `0x8404e63c`, with two alignment bytes between them.
It ends at `0x8404e654` and adds no BSS. The existing baseline ELF supplies
barrier/admission/idle symbols and is unchanged. These linker addresses are
test reservations, not a production loader/cache/placement contract.

## Verification

The complete runner, `tests/npu/test_allocator_startup.py`, passes:

- Healthy actual core0 reset through native initialization, synthetic host
  publication and coordinator idle ACK. All seven dynamic calls execute the
  checked core. All 824 allocator metadata bytes and the existing complete
  256 KiB L2 footprint oracle agree. The retained control-word allocation and
  its 32-byte aligned cost remain intact.
- Eighteen core0 failure/context cases, starting from native reset: denied
  ownership separately at each of the seven calls; corrupt count; capacity;
  invalid lock ID; wrong type at a selected caller; prior fault; fault at
  successful unlock; active-callback state; disabled MIE; disabled external
  interrupts; poisoned IRQ8 handler; and a masked mailbox source.
- Thirteen cases preserve the valid service context. Each executes DISCOVER,
  STATUS, STOP and another STATUS through the actual native dispatch and
  strict mailbox handler. All 52 replies complete; STATUS/STOP report FAULT,
  capability bits stay 7 and parked/ready/drain/release/arm remain zero.
  Thirteen legacy-version requests are rejected without entering their native
  callback. No failed allocator call returns to its native caller.
- Five unsupported-context cases remain in the interrupt-disabled hold.
  The active-callback fixture retains its active count of 1. No mailbox
  delivery is simulated into these disabled contexts and no service is claimed.
- Every core0 failure compares the entire 32 KiB local SRAM with an expected
  image, including only authorized fault/metadata changes. All 480 KiB of heap
  and 256 KiB of L2 remain unchanged, including after control queries. Native
  lock request/release counts and bounded stack position are asserted.
- Thirty-six valid unrelated-call lookups retain original behavior: 24 dynamic
  definitions and 12 fixed-L2 definitions. These component calls deliberately
  use an unselected return address. They verify fallback compatibility, not
  repaired ownership or bounds for those unselected users.
- Five hart7 cases cover success, denied ownership, corrupt metadata, a prior
  fault and an already-parked input. Whole SRAM/heap and lock/STATUS checks pass.
  An existing parked slot in the last fixture is retained, not manufactured
  as a new acknowledgement. Hart7 never changes admission's fault field.
- All 31 detours with the first hart7 gate retained park all eight actual
  reset/prologue contexts and repoll successfully. STATUS has mask `0xff`,
  capability bits 7 and zero ready/drain/release/arm. Hart7 does not execute
  bridge initialization or allocation. The generic startup getter hook replaces
  the earlier hart7-only allocation detour; it is not installed in addition.

Eight mutation/installation controls detect ignored allocation failure,
missing coordinator fault publication, lost interrupt restoration, dropped
control service, allocation after a prior fault, missing getter installation,
changed native fallback and omission of the control-word caller. The tests
check specific failing invariants, including executed checked-call counts.
Unsafe variants run only as RV32 emulator code, not on the router.

The capacity fixture adds two valid definition records before type 1; it is a
supplied capacity condition, not a claimed normal admitted startup sequence.
Likewise, the active-callback and damaged-IRQ fixtures are explicit controls,
not observed current failures. The test does not establish failure recovery
inside a real active callback or the ability to repair a damaged IRQ setup.

IRQ frames are serialized through the existing test dispatch helper. Mailbox,
PLIC, lock and timer storage semantics and synthetic host publication remain
explicit models. No physical IRQ delivery, cache coherence, DMA stop, complete
mt76 attach, packet flow or safe recovery/removal is established.

The full `--check` replay matches the saved receipt byte-for-byte. The receipt
binds 73 current inputs before/after execution and contains the exact compiler
command, allocated sections, disassembly, caller observations, failure results
and mutation assertions. Historical receipts are preserved; their glob-based
inventories can now discover these new source files and are not represented
as whole-file-identical current receipts.

## Remaining Contracts

- Complete other dynamic getter users and callback failure/retention paths.
  Unselected call sites still reach the original allocator, including its
  known bounds and ownership defects. Reuse of selected helper sites outside
  the checked cold context is held, not certified as supported reinitialization.
- Implement control handling for real active-callback failures and unavailable
  IRQ contexts without losing in-flight ownership. The tested raw hold is
  retention, not a complete recovery or callback-unwind implementation.
- Reconcile the full allocation budget and actual consumer extents. Core0 plus
  bridge still consumes 489,215 bytes and leaves 2,305 bytes; the earlier
  corrected-reset type-2 deficit and 58,879-byte/64 KiB bridge discrepancy
  remain open. No table or heap was resized in this checkpoint.
- Complete post-gate worker startup, physical ingress/copy/PPE/tunnel/Wi-Fi
  containment, fresh loader/cache/placement integration and common Linux
  recovery/removal ownership before promotion or NPU-active hardware tests.
- Finish host-adapter datapath and full stock-parity/release acceptance.

No router contact, physical testing, Wi-Fi configuration change, subagent,
image, flash, protected-data change or Git publication occurred. Packaged
overlay, source lock and cumulative patches remain unchanged. The restricted
provider-INODE correction and native DESC5/6/7/8 operations were not retried
or rerouted. No new mailbox transport was introduced.

## Reproduction

From the canonical WSL repository with the existing pinned local inputs:

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_allocator_startup.py --check
```

Omit `--check` to regenerate `allocator-startup.json`. Generated ELF and
mutation files remain under ignored `.local/npu-cold-allocator/`. The existing
reset and bridge-guard sidecars are rebuilt without changing their sources.
No patched native firmware blob or image is emitted.

SHA256:

```text
startup C        c41ef09677b190c2051b272b75e013807681dbe2abfa0d7b93798317a274367c
startup assembly fa9442ac4a28b9ca1152b30a40f4cc790da1a57888ab60712cbed2b588d97230
startup linker   b6dd5267d0fb4a3f336bed9f572940e124fdc2e83b7d1eab00cb7e38d3b854cb
startup ELF      e6be5eb0d094db525f72dc8cbcf6469748a27e5859931240e04dd052bb631c59
test runner      cc1b4660ec7541846eb58eb23ef9e0e867322abbc1eca9843ffc9ac8008fe3a0
receipt          4899bfdec2645b0e12da4755baf30231024c37be941dec9ba37b22f3fa198e1a
baseline ELF     bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931
```

All four canonical trackers and the NPU README record this scoped integration.
The full NPU reverse-engineering/implementation goal remains active and unmet.
