# Original three-profile RV32 replay passed

The original systemd invocation `61e2d7b8` exited successfully. The
separate terminal verifier bound its controller, result, transcript
orders, final states, and memory comparisons to the original start
receipt and the read-only frozen capsule `3d166089`. All **345**
replay inputs rehashed in both retained and frozen views.

| Profile | Verified positive RPCs |
| --- | ---: |
| 0 | 6,421 |
| 1 | 6,421 |
| 2 | 6,419 |
| Total | 19,261 |

The original pair is CODE `e6bc914c` and DATA `ad905cb0`, on source
lock `cc128c3b`. This verifies the original RV32 emulator run from
reset, with no reused profile outputs or target contact. It does not
verify a board boot, a physical drain, or the replacement kernel and
mt76 patches. [Exact terminal, profile and input pins](EVIDENCE.json).

## Next Build

Keep the existing production source lock in place. Build the unchanged
baseline in a fresh isolated world from capsule `3d166089` and combined
producer `b5af9591`, after rechecking the native C: mount, D: reserve,
host and guest RAM, and writer locks. No image build started here; storage
and the expected scratch mount were present, but the last Windows RAM
check had only 3,917,254,656 bytes free. Do not reuse a live-prefix receipt
or qualify the frozen image with the later coherent-window sources.

Independently compare the new FIT's selected payload with the replayed
pair and apply the [image seal](../2026-11-18-npu-image-seal/REPORT.md).
That image is a frozen-baseline result, not a deployment of the
[coherent-window delta](../2026-11-18-npu-coherent-handoff/REPORT.md).
The delta still requires newly linked modules, a new FIT and
separately authorized hardware and client validation.
