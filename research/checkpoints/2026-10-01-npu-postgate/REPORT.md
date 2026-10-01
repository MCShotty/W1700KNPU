# Native Bridge Postgate Startup

2026-10-01. Continued the full NPU objective from synchronized main `eb31bae`.
This checkpoint advances the composed native startup path. It does not complete
the replacement firmware, bootable loader, physical recovery or client acceptance.

## Findings And Correction

The original all-50-detour replay ended at the initial parking gates. Extending
it first exposed an incomplete test precondition: hart2's refresh reads the PCIe
TX DMA index through globals at `0x3e904700` and `0x3e9046fc`. The six reserved-
memory setup commands do not publish these addresses. The native SET19 setter
at `0x8400d5da` does, for selectors 0 and 2. This was not established as an
adapter defect during a correctly prepared boot; no fast-refresh guard was
removed or changed to hide the missing publication.

The new replay compiles the current prepared MT7996 host setup C, checks its
single/dual-HIF SET19 values, and directly executes those two original RV32
callbacks for the single-HIF case. The strict mailbox endpoint still rejects
both requests. This is a deliberately visible missing integration boundary,
not a claim of successful real host-to-firmware setup. Other host messages are
recorded by the host-C transport model but do not execute native callbacks.

With those addresses published and explicit synthetic drain completions,
all eight actual refresh adapters complete. Hart7 then reaches its bridge
allocation at native caller `0x8400148a`. The existing checked binding rejects
that call because it only permits allocation before parking/release. The new
baseline control reproduces this fault with the binding from `eb31bae` while
the other 49 detours, cold prefix and prepared inputs remain the same.

The shared native startup binding now admits this selected hart7/type-0x81
caller in the first prepared, released and armed epoch, after its own park and
refresh, with all four retained regions, completed memory bootstrap and
admission still closed. Core0's
selected cold callers retain their pre-gate rules. Other epochs, invalid caller
or type, active callbacks and failed/incomplete state remain rejected. The
complete lifetime predicate is rechecked after allocation; if a stop arrives
during the native unlock, the committed record is retained and no bridge base
is published. No allocator reset or release of the committed block is added.

## Verification

`postgate.json` records:

- All 50 detours installed before native reset; eight harts park and refresh.
- Original binding faults before allocation or bridge MMIO publication.
- Corrected hart7 reaches outer loop `0x84000b36`, allocates the selected
  68 KiB bridge extent, and performs the exact expected base/configuration and
  eight channel writes in the explicit register-storage model.
- Nineteen invalid-context/late-stop cases pass; nine guard-removal mutants
  are rejected. A stop injected at native unlock retains committed metadata
  without changing the heap payload or publishing bridge state.
- Harts 1-6 remain at their native startup waits for later host setup. Their
  flags are observed, not filled in to force progress. No packet work is claimed.
- The selected current host C compiles with ASan/UBSan; both HIF traces are
  checked. Only single-HIF SET19 values feed direct native callbacks here.

`allocator-regression.json` records seven successful selected core0 cold
allocations, 18 failure cases, 36 preserved fallback cases, five bridge cases,
the retained initial-gate control and eight rejected mutants. The existing
mutation test was updated to remove the pre-allocation predicate independently
of the new shared post-allocation recheck; it still detects allocation after a
prior fault. Historical checkpoint receipts were not overwritten.

## Evidence Limits And Next Work

This is compiled C/RV32 instruction execution with a serialized scheduler.
PCIe DMA indexes, platform drains, PLIC, allocator lock ownership, timer and
bridge-register behavior are explicit models. They are not physical witnesses.
The 68 KiB bridge layout and fixed code/state addresses retain their existing
placement hypotheses. There is no bootable replacement or physical cache proof.

The correction is in the shared native binding used by composition replay,
`tests/npu/allocator-startup-emulation.c`, not in the supplied vendor blob.
Canonical Linux/provider patches, source lock and the previously verified
local FIT are unchanged. No new image, router operation or flash was performed.
No INODE/provider framing correction or native DESC5/6/7/8 operation was retried.

Next: finish the remaining host setup/publication and native postgate paths;
connect actual cold loader identity/storage and V2 callers; establish real
engine containment, drains, teardown/rearm and physical/client acceptance.
In particular, do not label direct SET19 callback success as strict transport
integration or use the modeled release as a production boot procedure.

## Replay

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu NPU_EMULATION_TIMEOUT_US=60000000 python3 tests/npu/test_bootstrap_postgate.py --name fresh-postgate-replay
PYTHONPATH=.local/npu-reset/python-lib:tests/npu NPU_EMULATION_TIMEOUT_US=60000000 python3 tests/npu/test_allocator_startup.py --output .local/npu-postgate/fresh-allocator-regression.json
```

Use a fresh postgate result name. Retained private firmware inputs, the prepared
current kernel/mt76 tree and the existing emulator toolchain are required. The
new runner records exact input/binary hashes and original/mutated controls.
