# V2 Bootstrap And All-Hart Composition

Date: 2026-09-16. Unpromoted, codebase-only checkpoint.

Status: the frozen full suite passes. Independent readback verifies 125 input
fingerprints, one derived staged source, 12 binaries and both original private
firmware hashes. No image or router change.

Receipt: `bootstrap-composition.json`, SHA256
`6fb797f97c05723531f9841483d6631083c8b6f9659fb669c565529449797d10`.
Compiler: Ubuntu clang 21.1.8 (6ubuntu1); Unicorn 2.1.4. All compilation commands
complete without diagnostics. The receipt records commands and binary hashes.

## Change

`tests/npu/test_bootstrap_v2_composition.py` composes the V2 cold-start adapter
with the latest retained 50-detour candidate. The previous V2 bootstrap test
installed five detours and stopped core0 at `0x8400e330`; the earlier all-50
test used the older V1 control base. Neither proved this combination.

The new builder applies the existing bootstrap dispatch-gate patch to an
isolated copy, compiles V2/bootstrap/GDMA into a new base, and relinks dependent
components against that base. It preserves the checked cold allocator, reset
ordering, full 2048-slot command ring at `0x84060000`, 68 KiB bridge definition,
TXDONE guards, ring ordering, tunnel-header checks, egress guards and packet
extent checks. No canonical firmware C, existing runner, source lock, overlay
or cumulative patch is edited.

All 50 distinct detours are installed and checked before reset: 26 base
reset/coordinator/mailbox/worker/GDMA hooks, two allocator-reset hooks, one
allocator dispatch, two bridge guards, six TXDONE guards, three ring-ordering
hooks, five header hooks, three egress guards and two packet-extent hooks.

Allocated ELF sections, original code, native stacks, provider backup, native
SRAM and explicit candidate state reservations are checked for overlap. Imported
symbol addresses must match the selected base. An intentionally V1-linked
bridge component is rejected by this check before it is loaded. These checks
validate the emulator composition, not production backing or placement.

## Coverage

- Coordinator-first, workers-first and mixed native reset schedules. Early
  workers wait for core0; late workers do not reinitialize V2 identity/session.
- Binding immediately after the six setup commands, and binding only after
  every hart has parked. STOP/STATUS reflects the exact progressive worker mask.
- Original early version `0x457`, six original setup callbacks, the 56 KiB
  TX-check clear, 256 KiB L2 clear and native initialization footprints.
- Native reset/prologue paths for all eight harts, strict mailbox registration,
  checked cold allocations, isolated control word/ID pool and full ring image.
- Six cold rejections: zero identity and each of the five stale session words.
- Three modeled allocator-lock denials: types `0x8a`, `1` and `0x19`. The native
  caller does not resume; heap, L2, allocator metadata and bootstrap retention
  are unchanged after denial. V2 diagnostics return FAULT and the host holds.
- Seven missing-worker-hook controls. Each restores a saved core0 prefix,
  removes one startup hook, and stops at the immediately following native gate
  boundary. The installation check rejects it and the worker ACK is absent.
  No postgate worker body runs in these controls.
- Whole V2 control/admission/barrier/bootstrap effects are compared with native
  x86 C, and host requests/completions execute as x86 and AArch64 code.

The wire capability mask stays `0x27`. The host's private V1 validation core
stores normalized mask `7`; this is not a wire downgrade. Ready/drain masks,
prepared/released/armed state and legacy TXDONE readiness remain zero. The
bridge is not allocated and GDMA, tunnel and TXDONE sidecars do not execute
their postgate work. Installing these guards is not testing their active paths.

Final totals are five startup profiles (four banked-PLIC and the flat-PLIC
limit control), six cold rejections, three allocator failures, seven hook
omissions and one stale-link control. There are 209 x86/AArch64 host comparisons
and 96 x86/RV32 control comparisons. Type `0x8a` fails before setup at caller
`0x84004eca`; types `1` and `0x19` fail after step six at `0x8400b932` and
`0x8400bab8`. Diagnostic operations are DISCOVER and STATUS respectively.

Preliminary failures were harness assumptions, not new firmware corrections:
the code/stack check initially used an oversized original-code reservation;
host capabilities needed the documented private normalization; allocation
observations also include unchanged fixed-L2 getters; and the failure runner
needed to observe allocations before the six-command setup boundary. The final
full run uses the corrected, frozen harness. Scoped whitespace checks pass.

## Model Boundary

Banked PLIC storage retains the core0 mailbox-enable bit. A separate flat-PLIC
control loses that enable bit after worker startup, although explicit handler
invocation still returns V2 replies. This is a retained delivery limitation,
not evidence that real mailbox interrupts remain available.

MMIO effects, host-register publication, hart-ID CSR reads, scheduling,
interrupt invocation and the loader identity are explicit emulator models.
The contexts share memory but execute serially, not as concurrent physical
harts. No cache/PMA, arbitration, DMA ownership or physical drain is proved.

Only selector-15 control, early version and the six allowed setup APIs
18/32/8/23/7/12 are submitted. No direct DESC dispatch or restricted INODE
provider-framing correction is attempted. SET7 here is the BA address command,
not DESC7. No gate is opened to execute postgate firmware.

Remaining gates include real never-reused loader identity and coherent
publication, approved production reservations, actual PLIC/cache semantics,
postgate startup and complete boot, provider/mt76 lifetime and integration,
physical containment/drains, and ownership-safe cleanup/rearm. Software PARKED
does not authorize reclamation or establish stock parity.

## Replay

```sh
cd /home/captain/W1700KNPU
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_bootstrap_v2_composition.py
```

The full run writes `bootstrap-composition.json` here. `--smoke` runs the first
schedule only; `--checks-only` runs the fault/omission controls. Neither partial
mode emits a full-run receipt. Builds and private inputs remain under `.local`.

Predecessor receipts remain unchanged:

- Bootstrap V2: `06829c7473bc02b5b5372c9d970713384640fdc6153eefca0370fbacc4d28fec`.
- Packet extents: `4272a3771117c35b0b0920b48644167e12c765072c923555858d6bc1011fd5d7`.

Earlier isolated suites are input-verified, not claimed as freshly rerun here.
No physical testing, Wi-Fi work, subagents, deployment, commit/push or protected
backup/calibration changes are part of this checkpoint.
