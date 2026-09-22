# V2 Cold-Bootstrap Admission

Date: 2026-09-16. Status: **unpromoted software candidate**. This joins the V2
control envelope to the selected core0 bootstrap flow, not complete all-hart
boot, physical quiescence or production recovery.

## Change And Finding

The original bootstrap transport admits only 12/64-byte requests. Its `fresh()`
predicate also requires admission to be unbound. An early successful V2 BIND
would therefore prevent the remaining setup commands from running.

`firmware/npu/bootstrap-v2.c/.h` adds exact pinned 12/80-byte transport admission,
cold session initialization and binding prerequisites. The staged dispatch patch
defers BIND until the six selected commands finish and retained-region metadata
is complete. It applies the error only after sequence consumption, preserving
the existing V2 anti-replay behavior and any earlier protocol error.

An early BIND leaves admission unbound and does not mutate bootstrap progress.
Setup can finish; replay of that abandoned request is still rejected. Missing
identity or stale session data faults the native startup path without erasing
the prior session. The original V1/V2/bootstrap sources remain unchanged, with
the new dispatch implementation staged by the test builder.

The four-region retained mask is publication bookkeeping, not physical drains.
Neither BIND nor the six-command completion adds cleanup/restart authority.

## Verification

| Check | Result |
| --- | --- |
| Native reset-to-core0-boundary profiles | 3 boot-identity variants |
| Early BIND stages | 6; setup continues, duplicate replay denied |
| Cold identity/stale-session failures | 6 |
| Native callback-return failures | 6 |
| Native transport rejections | 28, before payload access |
| Preserved protocol errors | 5 |
| Nominal policy cases | 786: 46 initialization, 228 transport, 512 BIND states |
| Guard-removal mutants | 8 detected by named semantic oracles |
| ASan/UBSan | 453 assertions, including 128 invalid-length pointer controls |
| x86/AArch64 host comparisons | 933 across nominal, mutation and regression runs |
| x86/RV32 bootstrap-control comparisons | 55 |
| x86/RV32 policy comparisons | 2,346, including mutation controls |
| Standalone V2 server comparisons | 233 |
| Static analysis | No diagnostics |

The native positive paths execute reset and strict IRQ8 registration, version
0x457 before callback-table initialization, all six original bootstrap wrappers
and setters, and the original 56 KiB TX-check clear. Execution reaches the
existing core0 boundary at 0x8400e330. Subsequent BIND/STOP/STATUS preserves
bootstrap state and leaves release, arm and drain values zero.

Callback failures force a zero return at the selected original callback entry.
They verify caller failure handling and retained metadata, not an observed
hardware fault or partial native callback execution. Diagnostic V2 replies
remain available while repeated legacy setup is rejected.

Policy tests compare complete arena contents with an independent expected-state
calculation, while also comparing native and RV32 execution and checking RV32
callee-saved registers/stack. These tests reuse an emulator with a fully reset
arena; they are not cold-reset proof. Native reset scenarios use fresh instances.
The sanitizer models successful callback returns separately from the original
RV32 callback execution tests.

The staged server retains the prior standalone V2 behavior: 21 scenarios,
51 malformed/boundary cases, its separate eight saved contexts and the existing
reused-identity limitation control pass. This is not all-hart composition with
the new cold-bootstrap profile. Original baseline sources/receipts are retained.

Independent readback verified 64 input/derived-file fingerprints and 31 binaries,
including mutant artifacts and the sanitizer. Compiler: Ubuntu clang 21.1.8;
emulator: Unicorn 2.1.4. The source patch applies without fuzz or offsets.

## Boundaries

The test loader supplies nonzero identity bytes in modeled SRAM. Real identity
generation, nonreuse, publication, storage placement and independent containment
remain unimplemented/unproved. The prior reused-identity plus replayed-BIND
counterexample remains relevant. Copying the identity once is not authentication.

The tested native path is core0 reset/IRQ/selected memory setup to the stated
boundary. It does not complete core0 postgate boot or compose all later retained
firmware detours with all harts. MMIO, interrupt invocation, scheduling and
coherent storage remain modeled. Complete shared-provider/mt76 integration,
callback lifetime, physical DMA/FIFO/cache/PMA drains, ownership-safe cleanup/
rearm and hardware acceptance remain open.

The kernel provider, source lock and packaged overlay are unchanged. No image,
router, Wi-Fi, physical test, subagent, protected-data or restricted-selector
operation was performed. Firmware requests are V2 control, early version and
the existing six-command setup; no INODE framing or DESC5/6/7/8 case is retried.

See `firmware/npu/BOOTSTRAP_V2_CONTRACT.md` for the precise caller contract.

## Replay

From the canonical WSL repository:

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_bootstrap_control_v2.py
```

Generated source copies, native/AArch64/RV32 binaries, mutants and sanitizer
artifacts stay under ignored `.local/npu-bootstrap-v2/`, with standalone
regression binaries under `.local/npu-control-v2/`. Private original firmware
and the candidate DTB remain local and hash-checked.

`bootstrap-control-v2.json` SHA256:
`06829c7473bc02b5b5372c9d970713384640fdc6153eefca0370fbacc4d28fec`.

The final full runner reproduced the receipt byte-for-byte. Scoped whitespace
checks pass, and both private original-firmware hashes were independently
rechecked in addition to the 64 input/derived fingerprints and 31 binaries.
