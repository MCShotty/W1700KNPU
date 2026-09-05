# Stock Reset Dispatch And Executable Stop Counterexample

Date: 2026-09-05. This is reverse-engineering and emulator evidence, not a new
firmware fix or release. Firmware source lock remains at checkpoint `068832a`.
No router contact, configuration change, upload, flash or hardware test occurred.
Daybreak21 R1 remains the last router-tested WLAN-NPU-disabled baseline.

## Confirmed Protocol Defect

The pristine MT7996 NPU firmware can report GET3 zero after STOP4 completes while
its already-started core-5 indirect worker still consumes a pending descriptor.
The proof now executes the original RV32 instructions, rather than relying only
on reading decompiled C. The relevant input remains:

`e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643`.

`tests/npu/test_firmware_stop_counterexample.py` performs this sequence:

1. Execute the actual post-common-init hart dispatcher. With modeled hart ID 5,
   execution reaches `84000104 -> 84000aa6 -> 8400e7f8 -> 8400cb0e`.
2. Let the indirect worker pass its startup gates, then pause at `8400cbbe`,
   before consuming an already-pending descriptor. Save its register context.
3. Execute actual SET4 instructions. Supply the idle values that the three
   queried workers can write, then execute actual GET3; its result is **zero**.
4. Restore the core-5 register context while retaining shared SRAM changes.
   Native instruction `8400cc4e` advances consumer `3e9046e2` from 0 to 1;
   `8400cc52` marks the descriptor consumed (`4 -> 0xfe`). Execution reaches
   `8400ac30` with arguments `[0x1234, 64, 0, 0, 1, 2]`.

Both controls pass: an empty ring does not mutate, and STOP before startup holds
the worker in its startup gate. All eight hart-dispatch table selections are
also executed and checked. See `firmware-stop-counterexample.json`.

The hart-ID getter and printf are stubbed, other workers' idle values are
modeled, and execution stops at enqueue entry. No custom cache opcode or physical
DMA engine is emulated in this test. It proves a valid instruction-level protocol
counterexample with modeled shared SRAM, not actual hardware DMA traffic.
STOP callback completion is not presented as an independently exercised mailbox
ISR/interrupt transaction. The prior checkpoint separately recovered that ISR's
callback-before-DONE sequence.

Current `mt7996_npu_hw_stop()` treats GET3 zero as permission to issue SET6 and
reset buffer allocation. L1 ignores its return value, and full reset releases
tokens before stopping NPU. These defects remain unresolved. The existing
mailbox-order/timeout fix does not turn GET3 into a graph-wide ownership barrier.

## Resolved Stock Callback Route

The missing adapter between `mt_wifi` and `mtk_hwifi` is **connac_if.ko**. It has
no direct mailbox import, so a mailbox-only import graph omitted this layer.
This is the statically registered path for interface type 7 and the supplied PCI
tables, not proof of a particular live object's binding:

| Layer | Binding or dispatch |
| --- | --- |
| `mt_wifi:mt7990_init` | Sets arch-ops `+0x388 = hwifi_ser_handler` when adapter interface type is 7. |
| `mt_wifi:asic_ser_handler` | Gets arch ops through `hc_get_arch_ops`, then invokes slot `+0x388`. |
| `mt_wifi:mtk_mac_alloc_hw` | Stores the supplied API table in its wrapper; connac allocation supplies `hw_ops`. |
| `mt_wifi:hwifi_ser_handler` | Uses wrapper API slot `+0x90`, forwarding action/state registers. |
| `connac_if:.text+0xc80` | `hw_ops +0x90` resolves here. Action 8 selects GE slot `+0xf8`; action 9 selects `+0x100`. |
| `mtk_hwifi:mtk_hdev_ops_init` | Assigns GE table `.rodata+0x608`; slots `+0xf8/+0x100` hold `mtk_ge_stop_npu`/`mtk_ge_start_npu`. |
| `mtk_hwifi:mtk_ge_*_npu` | Uses bus DMA slots `+0x128/+0x130`, then returns zero even when the callback is absent or returns an error. |
| `mtk_pci` | `mtk_bus_alloc_trans` receives `pci_dma_ops`; stop/start slots point to `.text.unlikely+0x50/+0x0`, which call the named RRO mailbox helpers. |

`tests/npu/test_stock_reset_dispatch.py` executes original AArch64 instructions
for ASIC dispatch, arch-ops lookup, the hwifi bridge, connac selection and the GE
wrappers. One normal CALL26 relocation is applied; object/table contents and the
final PCI callback are synthetic. Six callback statuses for both actions plus
missing-callback cases give **16 passing cases**. Two in-memory mutation controls
replace the GE wrapper's forced-zero instruction with NOP and expose `-ETIMEDOUT`,
demonstrating that the test detects changed return semantics. No source/input ELF
is patched. This validates conditional dispatch/error handling, not DMA silence.

The source-level analogue must propagate failures; copying stock's forced-zero
wrapper behavior would preserve an unsafe assumption rather than repair it.

## Later Reset Steps Do Not Supply NPU Containment

- Stock L1 `mt7990_ser_1_0_v1` issues actions 8 and 6 before its state transition,
  then action 2 for bus/token teardown and reinitialization. It discards those
  callback results. `mtk_ge_set_dma_tk` stops/exits the bus and frees token state.
- The PCI stop callback reaches the MT7990 PDMA-disable callback through the
  per-chip table. That callback accesses PCI BAR offsets `0xd4208`, `0xd413c` and
  `0xd7044`, polls an idle bit, and disables interrupt-related fields. This is
  Wi-Fi endpoint control, not a demonstrated stop of independent SoC NPU harts.
- The chip hardware-reset callback toggles PCI BAR offset `0x1f8600` with a fixed
  delay. The BAR write helper is `.text+0x5a0` in mtk_pci, using the mapped BAR
  pointer at bus `+0xb78`. It is not a write to the SoC NPU boot/reset registers.
- FE reset uses action 7 (bus traffic control). The supplied static PCI table has
  NULL traffic callbacks at `pci_dma_ops +0x78/+0x80`. Dynamic overrides are not
  excluded by this table check; no full NPU-containment guarantee was recovered.
- Stock kernel `host_set_npu_core_on_off` changes `0x306004` and toggles boot
  trigger `0x306000`, with fixed delays and no demonstrated bus-drain handshake.
  `npu_hw_kern_reset_testing` only reads MIB offset `0x30c160`; its name does not
  make it a hardware reset operation. `is_npu_dma_done` reads a separate debug-DMA
  command field at `0x30c164`, not a proven whole-WLAN DMA status.
- The current provider has no reset-controller shutdown path. Its remove callback
  cancels watchdog work; devm allocations can subsequently be released. Probe
  unwind/removal therefore remain part of the required ownership policy.

The Linux reset binding defines EN7581 NPU reset ID 8; the current clock driver
maps it to reset-bank bit 9 at offset `0x830`. A named reset line is not evidence
that all NPU-related bus masters and Ethernet/PPE ownership are contained.
Primary references: [Linux reset binding](https://github.com/torvalds/linux/blob/v6.18/include/dt-bindings/reset/airoha%2Cen7581-reset.h)
and [Airoha clock/reset driver](https://github.com/torvalds/linux/blob/v6.18/drivers/clk/clk-en7523.c).

## Corrected Concurrency Analysis

The prior decompilation mapped shared SRAM as ordinary memory. That let Ghidra
omit cross-hart stores which its single-function analysis considered overwritten:
the refill busy-clear and fast-TX/TXDONE idle acknowledgements. Raw assembly was
retained and shows the actual stores. `ModelNpuConcurrency.java` now marks shared
SRAM volatile and marks eight assembly-reviewed permanent loops as non-returning.
This also prevents false fallthrough across adjacent worker wrappers.

Use `ghidra-current-rv32-concurrent-final/` for C-level concurrency review.
The initial concurrent export still lacked the fast-TX non-return annotation;
it is preserved separately. All 424 discovered executable functions in the final
analysis decompile, but that count is not proof of complete semantic coverage.

| Hart | Recovered role and stop coverage |
| --- | --- |
| 0 | Mailbox/PPE/control and Wi-Fi initialization; IRQ and other-service interactions still require domain review. |
| 1 | `8400cdc6`, RRO refill and page consumption; GET3 includes busy word `3e9046e8`. |
| 2 | `8400ec48`, fast TX; GET3 includes idle byte `3e9046f7`. |
| 3 | `8400e3fc`, slow TX/RX; enable gate exists, but GET3 does not query a dedicated acknowledgement. |
| 4 | `8400d0ae`, TXDONE; GET3 includes idle byte `3e9046f6`. |
| 5 | `8400cb0e`, indirect part 2; startup-only gating, executable post-STOP mutation confirmed. |
| 6 | `8400cd1a`, indirect part 1; enable gate exists, but GET3 does not query a dedicated acknowledgement. |
| 7 | Tunnel service after its Wi-Fi wrapper; interaction with shared pools/engines is not yet closed. |

Important correction to the prior checkpoint: the standalone page loop
`8400c9b0` lacks a recovered caller or absolute code/data pointer here. Its
reachability is **unproven**, not established active and not established dead.
Do not count it as a second active ungated worker. The reachable core-5
counterexample independently establishes that STOP/GET is insufficient.

The copy helper at `840053a6` writes channel registers under `0x1fb30000`, waits
for a corresponding bit at `0x1fb30204`, then acknowledges it. Its reset domain,
all call sites, and completion semantics must be closed before treating worker
acknowledgements as physical bus containment. Do not assume it is a different
SoC's HSDMA implementation based on a similar register address.

## Coverage And Replay

Five stock modules were fully auto-analyzed: mtk_pci 143 functions, mtk_hwifi 351,
mt7990 29, mt_wifi 11,264, connac_if 59. All 19 inventory-selected targets export
successfully. The complete PCI/hwifi/connac exports and focused Wi-Fi bindings
are retained. The reused kernel analysis covers 33,676 functions; its 251
name-matched exports also include unrelated `input` names and must not be called
251 NPU functions. MT Wi-Fi analysis reports two VarnodeContext warnings at import
addresses `00283f40/00283f8c`; selected reset decompilations succeed, and assembly
and relocations remain the basis for the tested path.

```sh
python3 -m pip install --target .local/npu-reset/python-lib -r tests/npu/requirements-emulation.txt
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_stock_reset_dispatch.py
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_firmware_stop_counterexample.py
python3 tests/npu/verify_stock_reset_evidence.py
```

Inputs are SHA-guarded private/local stock ELFs and pristine firmware. Twelve
table relocations and ten export artifacts verify. Ghidra projects remain under
ignored `scratch/`; emulator packages remain local. No credentials, device
backup, calibration, recovery image or generated firmware image is included.

## Required Implementation

Implement a generation-aware barrier across the actual WLAN workers, including
not-yet-started and in-flight paths. Cover slow path and indirect part 1 as well
as the proven indirect-part-2 hole. Acknowledge only after the final ownership/DMA
action. Resume must refresh cached ring pointers/indices; clearing a stop byte
alone is insufficient after resources are replaced. Prove the shared copy-engine,
IRQ, mailbox, PPE and tunnel boundaries before freeing memory.

Then integrate one bounded failure/retention policy across L1, full reset, probe
unwind and removal. Preserve possibly device-owned resources on timeout, reject
late completions from old generations, and resume only after complete reinit.
Current init sends selector 2 before selector 7, so selector 7's lack of an RX
enable write alone is not an additional demonstrated current-driver defect.

This checkpoint establishes the defect and its call path; it does not implement
the barrier or authorize an active-NPU image. Both goals and client/throughput,
stock host-adapter lifecycle and release acceptance remain open.
