# Original Core-0 Bootstrap IRQ Installation

Date: 2026-09-06. Bounded native-instruction sidecar. No bootstrap policy,
production edits, candidate/kernel builds, hardware actions, staging or commits.

## Integration Result

- Preferred early installation boundary: **PC `0x84004384`**, immediately after
  native PLIC init `0x840032e2` returns from the call at `0x84004380`. Cold reset
  has disabled MSTATUS.MIE, native PLIC init has disabled sources 0..191 and
  filled the IRQ table with default handler `0x8400309c`. Slot 8 at
  `0x3e901870` can now be rebound without being destroyed by that initialization.
  Preserve/replay displaced `csrrci a5,mstatus,8` (`f3770430`).
- Minimal source-8-specific alternative: **call site `0x84003f2e`**
  (`eff06fb2`, `jal ra,0x84003254`). When `a0 == 8`, substitute the desired ISR
  in `a1`; preserve other registrations, arguments and native call continuation
  at `0x84003f32`. The tested substitution occurs before source 8 is enabled.
  Global MIE and UART are already enabled here; this is not a global IRQ gate.
- Both witnesses retain the installed non-default ISR through the normal common
  initializer, allocator, API32 wait/release, complete 56 KiB TX-check clear and
  entry into the Wi-Fi initializer. Re-running the original mailbox initializer
  also leaves the non-default IRQ8 pointer intact.
- These tests install an inert routing sentinel that tail-forwards the original
  ISR. They prove installation/dispatch ordering, **not strict admission**.
  Parent owns the handler, detour ABI, bootstrap policy, and integration tests.
- A Wi-Fi-table-only rebind is not an equivalent transport interception:
  mailbox IRQs are enabled before that table is valid, and legacy STATIC
  function 12 writes over its slot without invoking the Wi-Fi dispatcher.

## Executed Ordering

Original reset starts at `0x84000000`, calls common init at `0x840000f8`, then
reaches hart dispatcher `0x84000104` and core-0 main `0x84000164`. The fixture
does not call Mailbox's pre-registering constructor or load an extension ELF.

| Order | Executed PC | Effect |
| --- | --- | --- |
| 1 | `0x84000096` | Cold BSS clear includes Wi-Fi slot `0x3e900d2c` and IRQ8 `0x3e901870`. |
| 2 | `0x84003360` | Common PLIC init fills all 192 callback slots with `0x8400309c`, including slot 8. |
| 3 | `0x84004390`, `0x8400439a` | MTVEC becomes `0x84006894`; MIE becomes `0x800` (machine external interrupt). |
| 4 | `0x8400439e` | **First post-reset global IRQ enable:** MSTATUS.MIE becomes 1. Recorded at following PC `0x840043a2`. |
| 5 | `0x840043fc` | **Normal first-boot write** `*(u32 *)0x1ec0c140 = 0xffffffff`. |
| 6 | `0x84004480 -> 0x84003254` | Register UART source `0x16` with handler `0x840047a0`. |
| 7 | `0x84003232`, UART invocation | First source enable after PLIC init: `0x0c002000 |= 1 << 23`. |
| 8 | `0x8400385c`, `0x84003868` | Timer-0 reload/control writes from native `0x840037c8(0,1,10)`. |
| 9 | `0x84003f14` | Mailbox routing/mask register `0x1ec0c008 = 1`. |
| 10 | `0x84003f2e -> 0x84003132` | Register source 8: IRQ8 becomes original mailbox ISR `0x84003cd6`. |
| 11 | `0x84003232`, source-8 invocation | First mailbox PLIC enable: `0x0c002000 |= 1 << 9`; MIE is already set, Wi-Fi slot is still zero. |
| 12 | `0x84003f2e` loop | Register/enable sources 9..14 with the same ISR; write routing words through `0x1ec0c024`. |
| 13 | `0x84003f48` | Host-facing mailbox mask/routing word `0x1ec0c004 = 0x100`. |
| 14 | `0x84003f70 -> 0x840103aa` | Eight native 0x50-byte clears cover `0x3e900cfc..0x3e900f7b`; Wi-Fi slot is cleared at store PC `0x840103c8`. |
| 15 | `0x84003f80` | **Wi-Fi dynamic callback 0 first becomes valid:** `0x3e900d2c = 0x84003a9c`, visible at next PC `0x84003f84`. |
| 16 | `0x84003f8c`, `0x84003f9c`, `0x84003fa8` | Install tunnel, TR471, PPE callbacks at Wi-Fi slot +4, +16, +20. |
| 17 | `0x8400449e`, `0x840044b2` | Publish native common-ready `0x3e904694 = 1`, then mailbox MIB31 `0x1ec0c1bc = 0xcccccccc`. |
| 18 | `0x84000164` | Native allocator `0x84005296`, then initializer `0x84004e76`; stop at its API32 delay entry `0x8400420a`. |
| 19 | native API32 and saved main | Address callback returns DONE; resumed initializer clears 0xe000 bytes and reaches `0x8400e330`. |

Global/source enables above are executed CSR/MMIO-write instructions under an
explicit storage model, not proof of physical IRQ delivery. Initial PLIC enables
are tested both zero and all ones; source 0's reserved PLIC bit 0 is preserved.
Common init registers sources 8..14, not 15. Source 15 has a separate core-7
registration in `0x84000aee` (source-only evidence, not executed here).

### Cold Marker Handoff

At the first instruction after `0x840043fc` (`0x84004400`): marker is UINT_MAX,
MSTATUS=`8`, MIE=`0x800`, IRQ8 is the default handler, Wi-Fi callback 0 is zero,
native common-ready at `0x3e904694` is zero, and the one-time DATA flag at
`0x3e900bb8` has been consumed. The address is `gp=0x3e9013a8 - 0x7f0`;
native PC `0x840043ac` changes the original DATA value 1 to 0 before the marker.
The test checks both values and records that exact write. The marker write is after common entry and before
UART/timer/mailbox registration; it is not evidence of a warm reentry.

Consequently a late cold hart can observe UINT_MAX after core 0 has normally
crossed the earlier `0x840000f0` candidate gate. This sidecar verifies the original
write and ordering only. Parent owns worker marker authority and the separate
late-hart regression; neither startup binding nor existing startup tests changed
in this sidecar.

## Registration And Early IRQ Controls

`0x84003106` only installs a non-default callback when the current slot is zero
or default. Its store is at `0x84003132`; an occupied non-default slot takes the
diagnostic path at `0x84003150` and is not overwritten. Wrapper `0x84003254`
nevertheless proceeds to enable the source through `0x84003200`.

Seven controls verify: pre-BSS IRQ8 binding is lost; pre-PLIC IRQ8 binding is
lost; pre-mailbox Wi-Fi binding is lost; post-mailbox rebind at `0x84004492`
misses an already-enabled interval; native reinit retains a non-default IRQ8;
STATIC/function12 overwrites Wi-Fi callback 0 while IRQ8 remains installed;
and removing the `0x1ec11834` model stops at its first access, PC `0x840043d2`.

Both interception cases inject a saved-frame IRQ at `0x84003f32`, after source 8
enable but before Wi-Fi publication. Original version GET returns flags 3
(DONE, status 0), with reply still zero. An API32 request immediately before
`0x84003f80` likewise returns flags 3 without setting its release address.
The sentinel is reached in both cases. After the store at `0x84003f80`, version
GET works even before the remainder of mailbox init returns. A rebind only at
`0x84004492`, or Wi-Fi callback validation alone, cannot cover the earlier path.

## Provider Version Query

Actual generated Linux 6.18.44 provider source is checked, not executed. Probe
starts the firmware, sets boot addresses, writes BOOT_CONFIG/BOOT_TRIGGER, sleeps
100 ms, performs this query, then publishes `platform_set_drvdata`. It does not
call WLAN memory initialization in probe. The 100 ms sleep is not a readiness
acknowledgement, and concurrent driver scheduling is not modeled.

- Core 0, mailbox function Wi-Fi=0, WAIT=1, STATIC clear, length 12.
- Payload words `[0x00000030, 10, 0]`: ifindex 0, GET type 3, API10.
- Provider writes regmap offsets `0x30c030` address, `0x30c034` length,
  `0x30c03c` flags, then `0x30c038` producer sequence +1. Corresponding RV32
  addresses are `0x1ec0c030/34/3c/38`. The host polls DONE/status at `...3c`
  and copies the final four payload bytes back from its coherent bounce buffer.
- Native route: IRQ dispatch `0x840030b2` -> IRQ8 -> `0x84003cd6` -> dynamic
  Wi-Fi callback `0x84003a9c` -> GET table slot `0x3e900170` -> `0x840101a6`
  -> version parser `0x8400d998` and native string helpers.
- This selected blob takes the unsupported/fallback path: store PC
  `0x840101dc` writes `0x457` at payload +8, returns success, flags become 7,
  PLIC completion writes 9. Provider would print 0.1111. This is **not** a
  successfully parsed version string or a boot-readiness guarantee.
- All checked version replies leave the complete 32 KiB local SRAM unchanged,
  and work while TX-check address is zero, before WLAN bootstrap attachment.

## Coverage, Reproduction And Hashes

13 scenarios pass: four full cold-order runs (clock MIB12 zero/nonzero crossed
with initial PLIC enables zero/all-ones), two interception paths with early and
valid version/API32 IRQs and native clear/resume, and seven binding controls.
The canonical trace retains executed function entries, CSR transitions, every
modeled MMIO read/write, callback writes, and named stub counts/return sites.
Twenty full Ghidra function spans and unchanged imported-helper hashes are in JSON.
The canonical run and an independent scratch rerun produce byte-identical JSON.
The imported-helper Git diff and workspace whitespace checks pass; concurrent
parent-owned changes are outside this sidecar and remain untouched.

```sh
cd /home/captain/W1700KNPU
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.local/npu-reset/python-lib \
  python3 tests/npu/test_boot_irq_installation.py
```

Reusable harness: import `Installation` from the new test. `reset(stop=PC)` runs
original reset; `run(start, stops)` resumes original instructions; `message(words,
static=False)` injects a saved-frame synchronous core-0 IRQ and restores the
caller context. `cpu`, `events`, `mmio`, `csr_events`, `get32`, `put32` and
`snapshot(h)` expose state. `intercept` is None, `before-global-enable`, or
`registration-argument`. Constructor performs no registration or file writes.
Only output may be redirected under `.local/npu-bootstrap/irq` using `--output`.

| Artifact | SHA-256 |
| --- | --- |
| Original CODE | `e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643` |
| Original DATA | `61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1` |
| Complete Ghidra export | `1536a9972838ca7c02da77629e784b392af919c5d25368478aff4d0c2422e2ca` |
| Test | `54fd846e16665d52cdcd79471bbac09e11b6e857ae0a717cb8c47f9698c93afd` |
| JSON | `07b1189711c9d847b0134cc95ae86a39dc7a49f7b6a494ddab623f5ac807f66a` |
| Provider C | `8eed02dd963c9d80fcaf4f15368506f4a4720dd7be4f080c394a21bba7e1fe8f` |
| Provider header | `9359009a4161de572e7f44b41b172860bb6414b56332f16ed6ff8df972126364` |

## Exact Unproven Boundaries

- Full original `0x84004348` and the stated allocator/TX-check paths execute.
  `0x8400e330 -> 0x8400d1a0` stops at the attempted L2-control write
  **PC `0x8400d1c0`, address `0x1ec0f200`, value 1**. That register is deliberately
  unmapped, not supplied as silent zero. The following 256 KiB L2 clear,
  remaining Wi-Fi helpers, and core-0 return `0x84000188` are not executed.
  No unrestricted claim of no future callback overwrite follows this boundary.
- PLIC priority/enable/disable/threshold/completion and selected mailbox,
  UART/timer, clock/reset registers are named storage models. Mailbox status
  models successful W1C. No new MMIO is silently mapped or ignored. Peripheral
  reset effects, bus ordering, IRQ pending/delivery/arbitration and timing are
  not established by these storage values.
- NativeMemory supplies the bounded SRAM/heap map and mutex owner value
  `0x1ec03048=0x10000`; only lock18 acquire/release registers are modeled for
  allocation. There is no real mutex contention, other-hart execution or cache,
  DMA, alias-coherency, containment or drain evidence.
- MHARTID reads return core 0; printf `0x840048f4` and UART printf `0x8400452a`
  return 0; delay `0x84004130` returns immediately. UART configuration and timer
  setup themselves execute. IRQ calls use a separate saved stack/context, not
  physical trap delivery or the complete MTVEC/MRET frame path.
- Sentinel pointer installation and argument substitution are emulator hooks,
  not built detours. Their production register/stack preservation, strict policy,
  reentrancy, startup integration and readiness behavior remain parent-owned.

Only the new test, this document, and `irq-installation.json` are written as
tracked artifacts; scratch is confined to `.local/npu-bootstrap/irq`. Existing
helper files are hash-checked unchanged. Concurrent parent edits are preserved.
The canonical ledger and remaining-work records are intentionally unchanged:
they are outside this sidecar's write scope, and the parent owns their update.
