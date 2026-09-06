# Bounded Bootstrap Review

Date: 2026-09-06. Independent read-only review and existing-binary execution.

## Findings

**No actionable code regression found within the requested contract.** This is
not approval for full mt76 attach, production loading, restart/reclaim, physical
boot, or execution beyond the intentional native `0x8400e330` boundary.

The reviewed bootstrap policy admits the selected MT7996 provider's six commands
in order, plus version GET. The pre-existing 64-byte discovery/status/session/STOP
control envelope remains separate; its presence does not open general Wi-Fi
commands. No implementation fix was made by this reviewer.

The earlier IRQ evidence did contain a reviewer-owned address error, now fixed:
the common-init one-time DATA flag is **`0x3e900bb8`**, not `0x3e9005b8`.
`gp=0x3e9013a8 - 0x7f0` selects it; original DATA supplies 1 and native
`0x840043ac` stores zero before normal cold-marker write `0x840043fc`.
The corrected IRQ test asserts the initial value and exact store, not merely a
zero read from another location. All 13 IRQ scenarios pass again, with a
byte-identical independent scratch rerun. Installation's callable API is unchanged.

## Reviewed Invariants

| Area | Review result and evidence |
| --- | --- |
| Stale owner / repeat init | `firmware/npu/bootstrap.c:31` rejects dirty state, including retained/inflight/packet/plan fields, without clearing ownership. Actual repeated reset after an in-flight fault is rejected by the existing pre-BSS gate and preserves the complete 80-byte bootstrap and 44-byte admission state. |
| Initialization failure | Missing plan, short TX-check reservation and request/binary overlap reach startup FAULT before native IRQ setup, marker write, any modeled MMIO write, or TX clear. Global MIE remains off. |
| Fault / callback failure | `bootstrap.c:111` requires the matching active/inflight state, fresh barrier/admission state and callback result exactly 1. Failure latches bootstrap/admission/barrier fault without advancing step or clearing retained/inflight/active ownership. Actual callback-entry fault injection also verifies this when a native side effect has already occurred. |
| Overlap / arithmetic bounds | `bootstrap.c:34` checks every range before using it in subsequent pair comparisons. Bases are aligned in `[0x80000000,0xc0000000)`, sizes nonzero and endpoints bounded without unsigned addition overflow. All six regions are mutually disjoint, including request versus binary and TX-check. Known binary/TX-check/request capacities are checked. This is structural validation, not complete packet-footprint validation. |
| Strict transport | `tests/npu/admission-platform-emulation.c:107` performs general transport checks and bootstrap transport binding before request dereference. Exact flags=1, exact planned request base and lengths 12/64 reject STATIC, other functions, aliases, offsets, oversized/high-bit lengths and invalid pointers. |
| Private command packet | `tests/npu/bootstrap-platform-emulation.c:22` snapshots the three host words; `bootstrap.c:86` validates and copies them into private state. Native wrappers receive `BOOT+20`, not the host payload. Mutation of the host payload at API32 wrapper entry does not change the admitted address. |
| Callback target / overwrite | `bootstrap-platform-emulation.c:27` selects only admitted API slots, checks their fixed original callback values, then calls the fixed target with the private packet. A table mismatch fails while retaining ownership. Poisoning dynamic Wi-Fi callback 0 does not redirect the strict version path. |
| Early IRQ / registration | `tests/npu/bootstrap-emulation.S:7` substitutes A1 only for source 8, sets RA to `0x84003f32` and enters native `0x84003254`. Registration installs the strict handler before native source enable. Early version GET works before dynamic Wi-Fi table initialization; the later native clear/publication does not overwrite IRQ8. |
| Cold-marker binding | `tests/npu/startup-platform-emulation.c:23` restricts the marker check to core 0. Workers still need the shared startup state and valid arrival/phase checks. The original core-0 normal marker write does not by itself classify a late worker as warm. |
| Closed remainder | Six commands complete with retained mask `0x1e`, admission still closed and no barrier release. Duplicates and later ordinary mt76 commands remain rejected. Discovery/status expose capabilities 7 without physical reclaim/restart capabilities. |

## Fresh Execution

No compiler, linker, candidate builder, test `main()`, report writer, router,
interface or physical MMIO operation was invoked for this review. Existing
libraries/ELFs were loaded into process-local test memory. Python bytecode writes
were disabled. Review probes were supplied over stdin and wrote no scratch files.

### Existing Suite Entry Points

- `test_bootstrap_protocol.suite((bootstrap.so, bootstrap.elf))`: **228 scenarios,
  5,935 native/RV32 call pairs, 5,286 bootstrap-oracle call pairs**, all pass.
  The 14 mutation compilations/kills in the parent's protocol JSON were inspected
  but not rerun or counted as fresh reviewer mutation evidence.
- `test_bootstrap_native.integrated(existing_elf)`: pass. Strict early version GET,
  all six original wrappers, retained mask 30, and native clear of 57,344 bytes.
- `test_bootstrap_native.rejected(existing_elf)`: **35 invalid requests, six
  duplicate commands and four post-reservation mt76 commands**, all rejected.
- `test_bootstrap_native.controls(existing_elf)`: **seven controls**, freshly
  rerun after parent additions: omitted registration detour, missing plan,
  short TX-check, request overlap, callback-table mismatch, callback failure,
  and post-validation host mutation.

These calls do not use `compile_pair()` or `build_platform()`. Imported native
integration/rejection bodies were unchanged during the parent's later test-main
provenance additions; the final seven-control run used the current test hash below.

### Independent Targeted Probes

1. Boot normally, then set dynamic Wi-Fi callback 0 (`0x3e900d2c`) to
   `0xdeadbeef`. Version GET still returns flags 7 and fallback `0x457` through
   the fixed native GET wrapper. No attempt to execute the poisoned pointer.
2. With that poisoned dynamic slot, submit STATIC function12 flags `0x6021`.
   Status is failure; no request-payload reads or callbacks occur, and the
   entire 32 KiB local SRAM remains byte-identical. This closes the original
   static callback-table overwrite route under the tested strict binding.
3. Admit API18, then inject `barrier.fault=1` at actual original API32 wrapper
   entry `0x8400fb84`, after ownership acquisition and before wrapper execution.
   The original callback writes the TX-check address, but finish returns failure:
   flags=3, step=1, failed=1, inflight=active=1, retained mask=2. Admission fault
   is set. The result correctly retains the side effect; it does not imply rollback.
4. Re-enter actual original reset from that failed, active state. Execution stops
   at `npu_emulation_startup_precheck_fault` with MIE off, while both bootstrap
   and admission objects remain byte-identical. No stale-owner clearing via
   the initializer is reachable on that repeated-reset path.

The native/control targeted-run input hashes and all three executable hashes
were checked unchanged before/after their corresponding executions. An initial
attempt stopped at the artifact-hash guard, before test execution, because an
older parent report still named a different combined ELF. The parent has since
refreshed `bootstrap-native.json`; its ELF and source hashes now match the final
reviewed inputs. The superseded ELF hash is not fresh execution evidence here.

## Assumptions And Gaps

- `bootstrap.h:38` requires coordinator-only, local-IRQ-disabled access and a
  fresh, zeroed cold-loader input with prior users independently contained.
  The plan must remain immutable during initialization. This review does not
  reinterpret the platform initializer as a safe general-purpose reinitializer
  of arbitrary live ownership state.
- The private-packet guarantee established here is for the 12-byte bootstrap
  command path. The inherited 64-byte control parser operates on the retained
  host request buffer under its existing ownership contract; this review is
  not an additional hostile concurrent-host mutation proof for that parser.
- Packet, TX-packet and BA regions receive structural checks only. The policy
  deliberately permits structurally valid small regions; all downstream
  consumer footprints and full attach remain outside this contract. Native
  fixed callbacks and provider source order do not establish physical safety.
- The added fault probe is one exact native instruction boundary, not exhaustive
  interleaving exploration. A fault arriving after admission can coexist with
  an already-admitted native side effect; retention/failure, not reversal or
  physical containment, is the verified outcome.
- The six-command provider profile includes BA. Supporting a different optional
  resource profile or ordinary mt76 attachment requires explicit future policy
  work; no permissive legacy fallback is enabled by the current candidate.
- The strict early GET can work while the dynamic Wi-Fi callback table is still
  zero because the pinned original DATA GET table already exists. This relies
  on correct coherent loading of the selected CODE/DATA pair.
- Full native Wi-Fi `0x8400e330`, L2, DMA, cache/bus/IRQ delivery, other-hart
  concurrency, a production loader/host adapter and actual client behavior are
  intentionally not certified. No such missing proof is reported as a new
  implementation defect in this bounded review.

## Reviewed Hashes

| Input | SHA-256 |
| --- | --- |
| `firmware/npu/bootstrap.c` | `45a2c0d7fe2e21e25fbe93395490d4b4d8f0b7399419c3157d5f73b981a506c9` |
| `firmware/npu/bootstrap.h` | `fb67f754db5dba8988919166342ce59a2f1b39051ec133bb4f40e7f2cbde4a80` |
| `tests/npu/bootstrap-platform-emulation.c` | `f41237a0f610657516d24a788f9711ff883ffb3d5d7d2861ebad2bd97d22cd8d` |
| `tests/npu/bootstrap-emulation.S` | `78286ec3ae562263b4cff3eb9b2fa55480ec0a23eed220edb3f5301429d02bc0` |
| `tests/npu/admission-platform-emulation.c` | `bb6210b2a4ce60c4ff78b238305513384c38a1712bb821242ba4d61112942e35` |
| `tests/npu/admission-emulation.S` | `3b43049362ca39d7f10e1455035059b005c06635f5429e6c00babd8af1dadacf` |
| `tests/npu/startup-platform-emulation.c` | `bb04076315c005e114cdd0742fd83656ff696c5bebd5705e594a0203c0decbf7` |
| `tests/npu/startup-emulation.S` | `b29c875d0ed3e1b55f33879002b6e62bee79369b2fd58498c504fcc0ea6d0c46` |
| `tests/npu/test_bootstrap_native.py` | `8c78809cc82352c0b2b49de4cd7caee773228d77440bef479fc92bc0141cc843` |
| `tests/npu/barrier-workers-emulation.ld` | `6c69a874c4697d92a3cee0a89410e1d5816c711b31a589efeea96ffa23f80a90` |
| Combined existing RV32 ELF | `bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931` |
| Existing policy native shared library | `94494bc4660e88f61588c882cd39170cd0c2c5c49aa1f6910e91ec8cbf80e7e1` |
| Existing policy RV32 ELF | `016b0b8ad729c3bebb9af086955c41868483f0b2021d2b1e8801835752039a91` |
| Corrected IRQ test | `54fd846e16665d52cdcd79471bbac09e11b6e857ae0a717cb8c47f9698c93afd` |
| Corrected IRQ JSON | `07b1189711c9d847b0134cc95ae86a39dc7a49f7b6a494ddab623f5ac807f66a` |
| Corrected IRQ report | `0e5f25f5fb307978b8fb7176ba9e0451f65ece14b2702f28d75ad8f05044e70b` |

Binary paths: combined ELF is
`.local/npu-barrier/admission-platform-bootstrap-bootstrap-startup-gdma-gdma-65536.elf`;
policy binaries are `.local/npu-bootstrap/protocol/bootstrap.so` and
`.local/npu-bootstrap/protocol/bootstrap.elf`.

Only this review document was added for the review. The three previously owned
IRQ files were corrected under explicit authorization; corrected-test scratch
remained under `.local/npu-bootstrap/irq`. Parent-owned code/tests, candidate
builds, staging, commits, hardware, ledger and remaining-work records were not
modified by this reviewer.
