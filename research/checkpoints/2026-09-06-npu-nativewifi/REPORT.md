# Native Core-0 Wi-Fi Bootstrap

2026-09-06, source checkpoint `f8402e9`. This extends instruction-level boot
coverage; it does not promote the candidate, alter packaged firmware, or prove
the actual-client Wi-Fi failures fixed. R1 remains the last router-tested image,
with WLAN NPU compiled out. No router, MMIO, image, flash or release action.

## Native Execution

`test_native_wifi_boot.py` runs the pinned original reset, common initialization,
TX-check clear and every core-0 Wi-Fi initializer through return `0x84000188`.
The five previously compiled reset/admission/IRQ-registration detours remain;
no additional native initializer is replaced with a success stub. Only the
existing printf, UART printf, hart-ID and delay substitutions are permitted.

The test adds explicit storage-only models for L2 control, the exact Wi-Fi
ring/configuration registers used by these routines, the SKB allocator mutex,
and six host-adapter input registers. Access to any other register still fails
closed. This exercises instructions, not physical L2 mode switching, cache
coherency, concurrent mutex ownership, DMA progress or interrupt delivery.

The original L2 routine writes 1 to `0x1ec0f200` and clears all 262,144 bytes at
`0x3e880000` using 65,536 four-byte stores. The test checks sequential store
addresses, values and the entire zeroed region before later initialization.
It then independently compares the complete final L2 image, including untouched
bytes, against these native footprints:

| Structure | Native Address | Extent |
| --- | --- | --- |
| RX descriptors | `0x3e880000` | 2,048 entries, 32-byte stride |
| TX descriptors | `0x3e891000` | Two rings of 1,024 entries, 32-byte stride |
| ID table | `0x3e8a9c70` | 8,192 sequential 16-bit IDs |

The initialized TX descriptors reference the first 4 MiB of the corrected
64 MiB TX-packet reservation: `0x8cc00000..0x8d000000`. No packet backing memory
is accessed by this initialization trace. This does not prove every later
consumer's extent, DMA mapping or token lifetime. The native allocator and
fixed-table lookups execute; the receipt includes all eleven calls and returns.

After native return, the existing coordinator adapter acknowledges epoch 1.
All seven other worker acknowledgements, eight ready slots and five physical
drain slots remain zero. No test claims all-worker quiescence or restart.

## Waits And Failure Controls

Five complete instruction schedules pass:

- All six validated provider commands before core-0 Wi-Fi initialization.
- Delayed API23, then separately published host-adapter ring bases. The native
  waits at `0x8400a04a`, `0x8400f836` and `0x8400f880` are actually traversed;
  neither core-0 completion nor its idle acknowledgement is published early.
- Host inputs with only `0x1ec0d0b0` and `0x1ec0d190` set to 1, all other host
  bases/counts zero. Native initialization still returns zero and sets its
  completion flag. These replies do not validate rings.
- A forced-full native SKB free queue. All 2,048 allocations fail, descriptor
  buffer fields stay zero and 2,048 warnings are emitted, yet both ring CPU
  indexes and the DMA-enable bit are written and initialization returns zero.
  This is a conditional failure-propagation counterexample, not a demonstrated
  cold-boot exhaustion or observed live-client fault.
- All Wi-Fi register inputs initially UINT_MAX, checking preserved RMW bits
  as well as the normal zero-register case.

Three missing-model controls reject L2 control, Wi-Fi DMA control and the first
host-ring read at their exact native instruction addresses. The combined ELF
is byte-identical across two builds and matches the prior bootstrap candidate:
`bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931`.
The original CODE/DATA, corrected DTB, imported source files and thirteen
original Ghidra function spans are hash-bound in `native-wifi-probe.json`.
Independent review reproduced the five cases, three controls, saved caller
contexts and corruption-sensitive L2 checks. Its entry-count metadata finding
was corrected by excluding pre-execution pause events; both initializers are
now asserted to execute once. See `NATIVE_REVIEW.md` for review scope and replay.

## Current Host Dependencies

The separate `HOST_SEQUENCE.md` and `host-sequence.json` trace the pinned
OpenWrt snapshot's mt76 attach commands and original callback boundaries.
The host C trace and RV32 traces are separate experiments, not a linked Linux
driver / firmware boot simulation. Their modeled replies must not be treated
as evidence that the corresponding native operation completed.

Current source writes host ring bases through mt76 queue allocation/reset and
the NPU provider's register mapping before later ring fill/attachment work.
Nonzero base registers therefore are not sufficient readiness evidence.
With MT7996 `hif2` absent, band 1 shares the primary TX queue and band 2 shares
that queue; this source path does not initialize the TX1 base at `0x1ec0d0b0`.
The native core-0 wait for that register is unconditional. This identifies a
conditional host/firmware bootstrap gap, not proof that this W1700K currently
uses that single-interface configuration. See the exact source references in
the host receipt; no board topology or live failure has been inferred. The
native test also traverses eight wait iterations with all other host fields
populated and TX1 still zero, without core-0 completion or idle acknowledgement.

## Remaining Implementation

The candidate still admits only provider memory bootstrap and version/status.
General mt76 ring/PCIe/token setup remains closed. Next work must join validated
host plans and full native callback consumers, handle partial initialization
without losing owners, and bring all workers from actual reset through their
startup gates. Merely allowing more APIs would not establish safe bootstrap.

Original native initialization writes DMA-enabling controls before reaching
the software idle gate. The storage model intentionally does not execute that
hardware work. A real loader/host containment and cache contract, physical
ownership/drain witnesses, Linux L1/full-reset/removal lifetime fixes, full
TX/RX/TXFREE/RRO/PPE parity and actual-client Wi-Fi acceptance remain open.

## Replay

```sh
cd /home/captain/W1700KNPU
export PYTHONPATH=.local/npu-reset/python-lib
python3 -B tests/npu/test_native_wifi_boot.py
python3 -B tests/npu/test_mt7996_bootstrap_sequence.py
python3 -B tests/npu/verify_nativewifi_evidence.py
```

The canonical ledger, reference, logging session and remaining-work checklist
record this boundary. Protected calibration, recovery and private inputs are
untouched. Neither full project goal is complete.
