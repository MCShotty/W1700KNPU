# Native Word Reader And Unchanged Raw-Boot Frontier

Continued solo from `7f88c65`. This checkpoint implements and tests a host-only,
explicitly loaded memory-read adapter. It does not complete native NPU replay,
physical retirement, BA reuse, hot operation or any hardware acceptance gate.

## Implemented Scope

`tests/npu/native-read-api.c` now exposes API version2 and `Reader.u32(address)`.
Every call checks the retained engine identity and calling thread, invokes the
same loaded Unicorn `uc_mem_read` API, and converts exactly four fresh bytes to
a little-endian integer. Backend errors raise `UcError`, including after a
backend writes partial output. No guest bytes, CSR values or registers are
cached. This API deliberately rejects non-exact integers, negative addresses
and unsigned64 address-range overflow; it is not a transparent replacement for
general Python `mem_read` argument coercion.

The Python installer checks the memory API signature as well as the existing
reviewed Linux x86_64, GIL-enabled CPython3.14 and RV32 Unicorn2.1.4 profile.
Both explicit module digest and adapter version are enforced. The optional
memory-function constructor argument preserves register-only construction;
calling `u32` without that API fails before native access.

Normal Pair behavior and its source are unchanged. Only the fresh private
DiagnosticPair opts into native register/CSR reads and binds its `get32` to the
word reader. No instruction hooks, memory hooks, guest instructions, bounds,
MMIO models, original replay inputs or global policies are removed or changed.

## Verification

- Public build CLI produces plain and UBSan extensions. Each passes32 API/CSR
  units with zero failures, errors or skips:19 reader units and13 CSR units.
  The six added word tests cover fresh/unaligned/cross-page reads, strict
  arguments, unmapped boundaries and partial-output errors, non-mutating host
  observation, and actual RV32 instruction/memory-hook transcript equivalence.
- The instruction fixture injects a host write, executes a guest load/increment/
  store/return, checks final memory/register values, and compares complete
  Python/native transcripts. Existing handle and cross-thread denial tests now
  exercise the word API too. These are API/observer tests, not NPU execution.
- Fresh observer/tooling/build-CLI/inventory/phase/kernel-log-checker suite
  passes167 units, zero skips. Prior selected ARM64/SMP and UML producers are
  revalidated, not rerun or counted as new kernel execution here.
- Complete original stock-source and four prior build-cache inventories remain
  unchanged. The current source lock, cumulative mt76 patch and four-module
  producer remain unchanged. No production firmware/module rebuild is claimed.

Build producer: `.local/npu-build-scratch/native-c2/read-memory-build-q2/result.json`.
Plain extension SHA256: `7e98cb7da36d3007d77fbbb5ea6568cec5ee9497ec87f6cf7b848857cd7f50c0`.
UBSan extension SHA256: `e8eedd2bfc5cbb758357ad29cc5c542b7400810b29cf5bc9134c3e6a17584b4e`.
Exact producer and source hashes are bound by `EVIDENCE.json`.

## Supplemental Diagnostic

One local100000-call observation measures Python four-byte reads at653249447ns
and C-backed reads at123776179ns, approximately5.3 times faster. This serial
microbenchmark is not a whole-emulator, NPU or client-throughput result; API
freshness is established by the separate live-value tests, not the benchmark.

Fresh profile2 diagnostic still times out in the raw boot prefix at
`0x84004efe`, with287383 cumulative observed instructions across preceding
steps. Its unchanged per-run raw-boot limits are3000000 instructions and
10000000us. It does not reach the RRO RPC being investigated. The separate
100000000-instruction/60000000us RPC limits are also unchanged, and the proposed
longer raw-boot budget was not used. Retained original profile2 PUBLISH failure
remains authoritative; neither the original q3 replay nor the compact replay
was restarted. Missing original service handles are not successful completion.

Retained failure: `.local/npu-build-scratch/native-c2/read-memory-probe-q4/raw-prefix-failure.json`.
The probe controller remains failed, not retroactively promoted by API tests.

## Execution And Evidence

New work uses the existing C-backed native ext4 scratch, held storage lock,
400MiB cgroups, no swap, fresh Windows/WSL RAM checks, both backing-volume
checks, conservative old compact1GiB future allowance and unchanged2GiB margins.
Two storage-capture launches stopped before dispatch because native PowerShell
could not resolve Get-FileHash in that subprocess. A wrapper explicitly imports
the Utility module in that subprocess, then runs the unchanged capture scripts.
The failures and successful diagnostic capture are retained; no permanent
execution-policy or global environment change was made.

Original consumed source/document versions, failed diagnostic, compiled outputs,
prior bindings, aliases and complete directory inventories are preserved.
Jev reviewed six narrow adapter/test claims; probabilities are retained, including
0.70 for the live transcript claim. Direct fixture inspection and its executed
assertions resolve that uncertainty within the small API-test scope only.

Full native replay remains open. Further faithful observer-cost reduction or an
explicitly approved separately labelled diagnostic budget is needed before
claiming progress beyond this raw-boot frontier. Complete MCU-exit failure and
all queue/page-pool physical lifetime, firmware BA reuse and hot retirement/rearm,
current image, hardware, clients, performance and stability remain unqualified.
No router contact, host module load or flash occurred. Full NPU goal stays active.
