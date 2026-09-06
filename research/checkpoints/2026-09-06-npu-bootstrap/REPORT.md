# Early Bootstrap Admission Candidate

2026-09-06, based on source checkpoint `452d420`. Work remains unpromoted in
`firmware/npu` and test adapters. No packaged overlay, patches, source lock,
build configuration, router state, release image or flash change.

## Corrections And Implementation

- Fixed the startup adapter's late-cold-hart rejection. Original core 0 sets
  mailbox marker UINT_MAX during normal boot at `0x840043fc`; workers must not
  interpret that as warm entry after coordinator initialization. Coordinator
  pre-BSS/warm protection and once-only hart entry remain in force.
- Added the MT7996-only bootstrap policy with an immutable memory plan, private
  request snapshot, exact transport validation, ordered reserved-address SETs,
  early GET version, active-handler retention and failure latching. Structural
  ranges plus known binary/TX-check/request extents are checked; other complete
  buffer footprints are not proved. See `firmware/npu/BOOTSTRAP_CONTRACT.md`.
- Installed strict source-8 handling through a compiled argument detour at
  `0x84003f2e`, before native registration enables that source. It survives the
  subsequent native callback clear and covers the interval before Wi-Fi callback
  0 is published. Other coordinator datapath IRQs use the existing admission
  dispatch gate. This is not physical trap/IRQ-delivery evidence.
- Only the provider sequence API18,32,8,23,7,12 is allowed, with exact indexes,
  declared addresses and zero flags/settings. GET `(0x30,10,0)` remains available
  throughout fresh bootstrap. General mt76 ring, PCIe, descriptor, token and
  running-state commands remain closed, including after those six completions.
- Callback addresses must match the pinned original DATA table. Native wrappers
  use private validated state, not rereadable host payload. A failed callback
  retains its resource bit and active/inflight state; no success or release is
  fabricated. Existing control status remains available after returned failure.

## Verification

| Gate | Result | Evidence |
| --- | --- | --- |
| Original reset/IRQ ordering | 13 scenarios; explicit MMIO models | `IRQ_INSTALLATION.md`, `irq-installation.json` |
| Late cold workers | 16 fixed schedules; 14 old-binding false rejections; 2 all-early controls | `startup-late-hart.json` |
| Policy | 228 scenarios, 5,935 native/RV32 pairs, 5,286 independent oracle checks | `bootstrap-protocol.json` |
| Mutation sensitivity | 14 variants compile on both targets and fail their independent oracle | `bootstrap-protocol.json` |
| Integrated native candidate | Early version, all six SETs, native TX-check clear, 35 invalid requests, 6 duplicate rejections, 4 later-command denials, 7 controls | `bootstrap-native.json` |
| Existing modes | 32 reset orders, 32 register cases, 30 entry rejections, 173 startup cases, both prior phase races, twelve worker/admission/copy suites | `regressions/` |
| Compiled inspection | 11 selected exports from 62 functions; zero failed decompilations | `analysis-input.json`, `ghidra/` |

The integrated test starts at original reset with the expanded 25,392-byte
synthetic DATA input. No Python call initializes barrier/admission/bootstrap
state. At first source-8 registration return `0x84003f32`, Wi-Fi callback 0 is
still zero but the compiled strict handler already serves version GET. It then
survives original mailbox initialization and reaches the API32 wait. After the
validated address callback, original core 0 clears exactly 56 KiB before the
remaining addresses arrive, then stops at `0x8400e330`.

The seven native controls cover missing registration interception, missing plan,
short TX-check, request/binary overlap, altered native callback pointer, native
callback failure, and host mutation after validation. Missing interception
accepts an unaligned out-of-order TX-check address; the candidate rejects it.
Invalid cold plans fault before native IRQ setup/peripheral writes. Returned
callback failures preserve ownership and status, and a mutated host request does
not change the private callback argument.

Final combined ELF:
`bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931`.
Text occupies `0x84040000..0x84042e07`, followed by 128 bytes of rodata. State and
plan end at `0x3e906330`, within the conservative emulator SRAM map. The corrected
W1700K DTB hash is
`dfe83e60933b9905712ebd1dc35f182cf943acbbd6f03902031be3856cf70344`.
The cold DATA fixture hash is
`5e37e4a19468019d7550ee44f59bb31aa93ffc3816056f4e4c3936a3b75c2272`.
None is a deployable or hardware-validated firmware artifact.

Ghidra confirms transport validation before payload dispatch, active/resource
publication before callbacks, fault-only failed completion, the source-8-only
argument substitution and continuation `0x84003f32 -> 0x84003254`, and the
coordinator-only warm-marker read. Explicit ELF-derived seeds prevent internal
pause labels from splitting startup functions. Three standalone-ELF jumps lead
to unmapped original code (`0x84003254`, `0x84000078`, `0x840000f4`), so their C
decompilation reports truncated flow; assembly and native integration establish
the jumps, not complete decompilation of the original firmware. The preexisting
Ghidra GUI-template XML warning remains unrelated and was not changed.

## Remaining Boundaries

The separate original probe executes common init and the allocator/TX-check
path, then stops at L2-control write `0x8400d1c0 -> 0x1ec0f200`, value 1. It does
not silently map that register or pretend its reset/clear semantics are known.
The integrated candidate stops earlier, at Wi-Fi initializer entry. Complete
L2/cache setup, all Wi-Fi helper initialization, core-0 return, worker bootstrap
dependencies and mt76's full attach sequence remain required.

The version query returns native fallback `0x457` (0.1111), not a parsed version
or readiness signal. API18 is a no-op, and six successful reservation replies do
not mean the datapath is ready. Bootstrap completion advertises no new capability.
Native IRQ timing, peripheral reset effects, simultaneous harts, cache/alias
coherency and hardware DMA execution remain modeled or absent. The loader still
needs a real containment, placement, upload and pinned-request ownership contract.

The previous software worker/copy suites run their existing non-bootstrap mode;
they are regressions, not proof that the strict-bootstrap candidate can yet run
or restart the datapath. Full Linux L1/reset/removal retention, host-adapter
TX/RX/TXFREE/RRO/PPE parity, active-NPU release and real-client Wi-Fi acceptance
remain open. R1 remains the last router-tested baseline, with WLAN NPU compiled
out. Protected calibration/recovery and private device inputs remain untouched.

## Replay

```sh
cd /home/captain/W1700KNPU
export PYTHONPATH=.local/npu-reset/python-lib
python3 -B tests/npu/test_boot_irq_installation.py
python3 -B tests/npu/test_startup_late_hart.py
python3 -B tests/npu/test_bootstrap_protocol.py
python3 -B tests/npu/test_bootstrap_native.py
python3 -B tests/npu/run_bootstrap_regressions.py
python3 -B tests/npu/prepare_bootstrap_analysis.py
python3 -B tests/npu/verify_bootstrap_evidence.py
```

`tools/ghidra/run_bootstrap_candidate.ps1` records the equivalent headless
invocation with the final ELF hash. Existing Ghidra evidence is not overwritten.
The current reference, canonical ledger and remaining-work checklist track this
checkpoint; neither full project goal is complete.
