# MT7996 Bootstrap Candidate

This is an unpromoted coordinator-only policy and test binding. It is not in the
packaged firmware, does not implement full mt76 attachment, and supplies no
physical containment, drain, reclaim or restart capability.

## Cold Input

The loader must independently contain prior owners, load CODE/DATA and initialize
the existing startup header and fresh bootstrap storage coherently. The test map
places the 80-byte bootstrap state at `0x3e906200` and immutable 48-byte memory
plan at `0x3e906300`. The complete synthetic DATA input is 25,392 bytes and
preserves the original 3,084-byte DATA prefix. These are not production addresses
or a completed Linux loader contract.

The plan contains six `(u32 base, u32 bytes)` ranges: binary, TX-check, packet,
TX-packet, BA, and the host's retained coherent request buffer. Bases must be
4-byte aligned in `[0x80000000,0xc0000000)`, ranges nonempty and nonoverlapping,
and all endpoints within that window. Binary requires at least `0x240000`,
TX-check `0xe000`, and request capacity exactly 256 bytes. Other resource sizes
receive structural checks only: **complete packet/TX-packet/BA consumer
footprints are not proved**. Do not treat accepted small declarations as safe
production capacities. The W1700K test uses the corrected compiled DTB plus a
synthetic request allocation at `0x82000000`.

Initialization rejects nonzero state and never clears existing ownership to
recover from failure. The caller owns the plan before initialization; only core
0 with local interrupts disabled accesses the resulting bootstrap state.

## Accepted Requests

The transport requires mailbox flags exactly 1: synchronous dynamic Wi-Fi
function 0, no STATIC or other bits. Address must exactly match the declared
request buffer. Only 12-byte bootstrap or 64-byte existing control packets may
be read. Offsets, aliases, unaligned addresses and unsupported sizes are rejected
before payload dereference. Physical mapping/cache validity remains a loader
and host responsibility.

Bootstrap words are `(header, api, value)`, little endian. GET `(0x30,10,0)` is
available before, between and after the six following SET requests while the
initial generation remains closed, unbound and fault-free:

| Order | Header | API | Value |
| --- | --- | --- | --- |
| 1 | `0x11` | 18 | 0, native band-0 CPU no-op |
| 2 | `0x10` | 32 | Declared TX-check base |
| 3 | `0x10` | 8 | Declared packet base |
| 4 | `0x10` | 23 | Declared TX-packet base |
| 5 | `0x10` | 7 | Declared BA base |
| 6 | `0x10` | 12 | 0, native force-to-CPU setting |

This profile requires BA. Optional-BA and MT7992 profiles are not implemented.
Duplicate, reordered or different requests do not advance the sequence. The
bootstrap gate never opens general legacy commands, even after all six replies.
PCIe/ring/descriptor/token setup, later startup notifications and running-state
commands remain future work. Control BIND/STOP ends eligibility for bootstrap;
the existing control capabilities continue to exclude reclaim/restart.

Before invoking a native callback, the policy validates a private packet snapshot,
sets the active-handler count and conservatively retains the address's resource
bit. The binding checks the pinned original table pointer, invokes that original
wrapper on private state, and copies only a GET result back to the host. Later
host payload changes cannot redirect that callback. Success requires native
return value exactly 1. A returned failure keeps the inflight count and resource
bits, faults admission/barrier, and leaves control status available. A callback
that never returns is not made interruptible by this policy.

## Native Installation

The test detour at `0x84003f2e` substitutes only source 8's handler argument,
then invokes original registration `0x84003254` with continuation `0x84003f32`.
This installs strict handling before source 8 is unmasked, and survives the later
native Wi-Fi callback-array clear. The existing dispatch gate covers coordinator
datapath IRQs. Global MIE and UART are already enabled at this boundary; this
detour is not a global IRQ mask or complete trap-entry implementation.

The normal native cold boot writes UINT_MAX to `0x1ec0c140` at `0x840043fc`.
Only coordinator 0 uses that marker to reject warm entry. Late workers use the
validated startup phase and once-only arrival claim, not this changing global
marker. Duplicate entry and coordinator warm/BSS protection remain enforced.

Native execution reaches and clears the complete TX-check table after API32.
The current integrated test stops at Wi-Fi initialization entry `0x8400e330`.
The separate original-path probe identifies the next unmodeled L2-control write
at `0x8400d1c0 -> 0x1ec0f200`. Neither full core-0 return nor later host-adapter
initialization is established here. GET version's observed `0x457` is the native
fallback, not a parsed version or readiness signal.

Evidence and replay: `research/checkpoints/2026-09-06-npu-bootstrap/REPORT.md`.
