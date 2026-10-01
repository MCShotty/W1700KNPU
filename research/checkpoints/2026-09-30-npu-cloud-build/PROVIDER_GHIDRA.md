# Current Provider Ghidra Receipt — 2026-09-30

## Result

PASS with recorded DWARF limitations: Ghidra 12.1.2 imported the current
`airoha_npu.ko` as `AARCH64:LE:64:v8A`, completed auto-analysis and post-analysis,
and saved a fresh project. There are 29 executable functions; all six surviving
selected functions exported with `decompiled=true` and zero failed decompilations.
No analysis timeout occurred. No additional ELF/library was imported.

The run used one Ghidra analysis CPU, `ActiveProcessorCount=1`, one parallel GC
thread, a 1 GiB heap, and a 240-second per-file analysis timeout. It performed no
C compilation, module execution, emulation or hardware access.

## Exact inputs

Original module:
`.build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.52/drivers/net/ethernet/airoha/airoha_npu.ko`

- Module SHA-256: `cee6f7735f0a0603c26be90f5f35af2e52143438d634ff3df112aeaf30f4ed20`
- Module size: 124776 bytes; ELF64 little-endian AArch64 relocatable
- Adjacent `airoha_npu.c` SHA-256: `026789bacd65b4a8c6ff25317c4ba8b33acfd52dde66c7c455758812ce8fe582`
- Compiler recorded in DWARF: GNU C11 14.4.0, optimized `-O2`, with debug data

Both inputs matched the assigned hashes before they were copied into `input/`,
and the copies matched before import. Ghidra's exported executable SHA-256
matches the expected module. The originals were hash-checked again after
analysis and still matched. Copying provided a stable snapshot while the world
build continued. No input or source was edited.

## Surviving functions

The six selected ELF FUNC symbols are local symbols in `.text` (section 8):

| Function suffix (`airoha_npu_`) | ELF section offset | Bytes | Ghidra address |
| --- | --- | ---: | --- |
| request_firmware | 0x580 | 208 | 0x001005c0 |
| wlan_prepare_memory | 0xda4 | 644 | 0x00100de4 |
| wlan_init_memory | 0x1028 | 240 | 0x00101068 |
| load_firmware | 0x1120 | 236 | 0x00101160 |
| run_firmware | 0x120c | 444 | 0x0010124c |
| probe | 0x13c8 | 1124 | 0x00101408 |

Ghidra addresses above are its relocation-assigned analysis addresses, not
physical addresses or the runtime addresses of a loaded kernel module.

The selection also names `airoha_npu_memory_valid` and
`airoha_npu_load_firmware_from_dts`. Neither has a standalone ELF FUNC symbol.
This is accounted for by explicit DWARF `DW_AT_inline: 1 (inlined)` records:

- `memory_valid`: three inlined instances at source call lines 691, 703 and 406
- `load_firmware_from_dts`: one inlined instance at source call line 421,
  inside `run_firmware`

See `provider-inline-evidence.txt` for the exact abstract DIEs and inlined-subroutine
records. Their absence as separate exports does not mean they were unexamined
or removed from the compiled control flow.

## Bounded source-to-symbol observations

These are static observations about this hash-bound module. They are useful
corroboration of the source structure, not a proof of semantic equivalence.
The complete decompiled C and AArch64 instruction listings are retained in
`provider-ghidra-export.txt`.

1. `request_firmware` (export line 5, source lines 299–321) retains the direct
   firmware request, the empty/oversize checks, -ENOENT to -EPROBE_DEFER mapping,
   and release on invalid size. Debug/prototype recovery is incomplete: one
   displayed `release_firmware()` call omits its argument in pseudocode, while
   the retained instructions load the firmware into x0 before the call.
2. `load_firmware` (export line 466, source lines 327–364) retains conditional
   memory-plan preparation before the image requests, two calls to
   `request_firmware`, and success branches before either `memcpy_toio` call.
   In its instruction listing the request calls are at 0x001011b0/0x001011e4;
   copies are at 0x00101208/0x00101218. The second-request failure path releases
   the first image and clears the plan count. The success path releases both
   and sets the firmware-loaded byte. The second copy's plain `base` in the
   decompilation is consistent with source `REG_NPU_LOCAL_SRAM == 0`.
3. `wlan_prepare_memory` (export line 93, source lines 680–727) retains the
   initially-zero output count; required/optional region lookup; nonzero,
   ordering, alignment and 32-bit checks; conditional 0x80000000–0xbfffffff
   bounds; firmware/pairwise overlap comparisons; and TX-buffer size check.
   The end of the success path copies 0x100 bytes, then writes the count.
   These are geometry checks; they do not prove exclusive physical reservation.
4. `wlan_init_memory` (export line 350, source lines 729–774) retains the
   firmware-loaded gate, retained-plan path for nonzero `txbuf_min_size`,
   caller-local preparation for the other profile, nonzero-count gate, and
   setup command calls through `wlan_cmd_with_retry`. Ghidra reconstructs some
   resource types/arrays imperfectly; do not use its displayed array sizes as
   source-layout proof.
5. `run_firmware` (export line 565, source lines 392–427) retains initial
   loaded/count clearing, firmware-region checks including 0x240000 total
   size, mapping, and both SoC-default and DTS-name loading routes. The
   inlined DTS route is visible here, including the two-name count check and
   the MT7996 0xe000 minimum TX-buffer size selection.
6. `probe` (export line 752, source lines 902–1028) retains the memory-setup
   callback assignment, work cleanup registration before IRQ setup, and the
   `run_firmware` call before the succeeding publication/boot-register writes.
   This does not establish reset ownership, runtime startup correctness,
   successful register writes, DMA drains or complete lifecycle containment.

## Recorded limitations

The analysis log contains ERROR-level DWARF import diagnostics for three
compiler-generated `__addressable_*` variables without address information,
and unrecoverable optimized register-location expressions. All are retained.
The decompiled output contains unresolved locals, raw field offsets, incomplete
structure types, and occasional imperfect external function prototypes.

The loader skips zero-sized `.note.GNU-stack` and `.bss` sections and reports
that the skipped GNU-stack section's symbol cannot be placed. These notices did
not prevent the six selected functions from decompiling. This receipt does not
claim a clean diagnostic log or full source-variable recovery.

No private binary, old Ghidra project, source/tool/build edit, hardware change,
publication, restricted execution, firmware execution, module loading, or
emulation was performed. No claim of physical containment/drain, semantic
equivalence, hardware acceptance, or stock parity follows from this result.
Source ledgers are left for the parent worker to integrate.

## Evidence

Published text evidence beside this report is `provider-ghidra.json`,
`provider-ghidra-export.txt` and `provider-inline-evidence.txt`. The provider
module was built from the public pinned source; no private binary was imported.

The complete original analysis is retained under ignored
`.local/cloud-build-access/provider-ghidra/`: `receipt.json`, hash-bound `input/`
copies, logs, ELF/DWARF dumps, `selected.pattern`, `project-path.txt` and the
original `export/airoha_npu.ko.txt`. Those generated inputs, logs and project
files are not included in this GitHub change. Its local `SHA256SUMS` records
the original receipt files; use the published checkpoint manifest for the
renamed text evidence. The project was created for this analysis.
