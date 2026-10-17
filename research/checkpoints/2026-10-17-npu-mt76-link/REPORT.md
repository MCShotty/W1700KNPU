# RX-Event Export And Current Consumer Link

## Build-Input Gap Repaired

The new whole-source comparison stopped the first consumer attempt before
kernel copying or compilation: the merged `dma.c` invokes the retained
`mt76_npu_alloc_rx_event` hook, while the exported patch left the upstream
managed-allocation path unchanged. The hook was implemented on October13 but
was outside the exporter's historical selected-file list. Previous selected-
file replay did not establish whole-source equivalence.

`changed_existing_files` now discovers every changed existing nonmetadata file
in the upstream/merged pair. Git metadata and `.orig`/`.rej` backups are not
source inputs. New sources still need explicit enrollment. Whole-source replay
applies the tracked patch with zero fuzz and checks all329 clean files against
merged source, including11 changed files. Unused legacy `w1700k` copies are not
copied, and source references to them are rejected.

Mt76 patch SHA256:
`ef19e49618292089e59727f9acb38627451f975efa2132094d185037a0c4a4a1`.
Current source-lock SHA256:
`40d293685243a51c56c8a153505f24bab0b2b9cb81231ff3a2b029afc3db331c`.
Kernel/provider sources and locked22 components are unchanged by this export
repair. Source70/5/22 checks pass.

The actual exported-source queue/allocation/provider C fixture passes166 cases
and rejects seven mutants with address/undefined/leak sanitizers. DMA backing,
registers/framework and transport are modeled. This is not native API22
admission, physical allocation/retention or a drain witness. Receipt:
`.local/npu-rx-event-20261013/exported-q1/result.json`.
SHA256 `83418761d02faf51a714f28f6d558b5097c6f27b4ca585ada45e324eee8ecba2`.

## Provider And Consumer Status

The provider was freshly relinked against the new source lock; the olderf9
receipt was not reused with a hash waiver. New receipt
`.local/npu-current-provider-module/rx-event-export-q1/result.json`, SHA256
`52ca956480506bf35c6efc1dc2e06dff841afca6c5ea8d9232cd0ed9820db372`,
passes matching6.18.52 vermagic,three exports/70 available imports and the
unchanged102685-entry original kernel inventory. New module SHA256:
`750796b42edf74fdb7fdc89ffa5793e066cb2250163b40fa92f06b648922b648`.
The output is still an unloaded isolated module,not a world/image build.

Current consumer final links **pass**. The fresh
`rx-event-export-q3` attempt uses independent copies of the current linked
kernel,clean patched mt76 and staged backport headers. It builds actual combined
objects before discovering dependency owners from their imports. It copies
actual symbol-index rows and verifies each dependency module's matching
vermagic/export names. Namespace/CRC/export-kind columns remain exact.

Real-object preflight identifies228 own exports and exactly three missing
prebuilt imports:the two PPE get/put symbols and hwmon registration. The actual
`airoha-eth` and `hwmon` modules match their14 original index rows. Backport
mac80211/cfg80211/compat dependencies use their real prepared build index.
No invented CRCs or unresolved-symbol bypass are used. Kernel-generated
`__this_module` and linker GOT symbols are not fabricated dependency exports;
final modules must resolve them internally and retain no undefined metadata.

Actual final modules have vermagic `6.18.52 SMP mod_unload aarch64`:

| Module | Bytes | Exports | Imports | SHA256 |
| --- | ---: | ---: | ---: | --- |
| mt76 | 1339968 | 131 | 187 | `22c01ff6b45c39cc5c6164f2ee00937b3748d13648ea10e0299ceb8f7ceba533` |
| mt76-connac-lib | 650480 | 97 | 65 | `3f9e3d079e2fca09a81d46ad713ba250ba3761955b71e3a00cbe316cd6fe9ac8` |
| mt7996e | 1847320 | 0 | 282 | `868464f2df55d6c59816abc54bf5caa626f5202ac7a989befc90613ecf02950b` |

All imports are available from the current provider/kernel,verified prebuilt
dependencies or the new modules. Six mt7996e NPU imports resolve to mt76
exports. Receipt `.local/npu-current-mt76-modules/rx-event-export-q3/result.json`,
SHA256 `079b47039fdf003dacb70c6733cf4c7eec1611ab91e94874dfbcb107d881505c`.
The two-stage actual compile/link shares one1800-second build deadline,not a
relaxed unresolved-symbol policy. Generated `__this_module` resolves inside
every final module; neither it nor GOT remains an undefined import.

The original prepared kernel/mt76,producing-provider kernel,staged headers and
FIT remain unchanged. One provider/three consumer missing MODULE_DESCRIPTION
metadata warnings are retained;there are no C warnings. Existing vmlinux and
prebuilt dependencies were not relinked. Host toolchain/runtime remain external.

## Retained Failed Attempts

- Initial `current-f9-q1` stopped at the unexported `dma.c` comparison,not a
  link or native fault. Record `.local/npu-mt76-link-20261017/export-gap-q1.json`
  SHA256 `dc6fa095bd9ef5e6bf359d7a68332f2ff9bef7804a30c1ac670a8532d4178b25`.
- Consumer `rx-event-export-q1` compiled all three combined objects,but real
  modpost failed on missing `devm_hwmon_device_register_with_groups`. The
  provider-only kernel index omitted other modular dependencies. Failed inputs,
  runner and log are preserved; original kernel/producing-provider/prepared-
  mt76 inventories stayed exact. Record SHA256
  `4aaa9c768e1ac6ac18f6850184e532381bec0e2b40191fef6001f223599191fa`.
- Q2 was canceled during its initial original-kernel inventory,before source
  copying or compilation. A separate preflight on the real q1 combined objects
  exposed the old parser's unsupported `.export_symbol`/`__export_symbol_`
  format. Pinned6.18.52 `include/linux/export.h` and actual ELF sections/symbols
  establish that format. The corrected parser also retains final `__ksymtab`
  support. Canceled record SHA256
  `05075ba8324eef19b6809285a4b10b65d0ec95e446cc8c81817e3572b73e1882`.

Sixteen consumer parser/source-copy controls and six exporter controls pass.
These synthetic controls are not actual module linking or loading. Scope
`.local/npu-mt76-link-20261017/scope-q1.json`, SHA256
`8c0fdc7ffa5fb39e7b3af2394f7ba03bb24e2f3aed5b6dbea58c7ab34ef63aae`,
verifies284 exact input hashes and238 unique unit cases in256 executions,
with no skips. Eighteen preexisting imported fixture cases repeat. It also
checks the real modules,complete source comparison,166/seven C fixture scope,
retained failures and unchanged protected build outputs. The source-lock change
is exactly the mt76 patch row;no unrelated lock fields differ.

The four post-link Jev judgments are retained under `jev-q2.result.json`, model
`jev-1.13.0`:source coverage supported0.49/confidence0.23 (uncertain),actual
dependency rows0.98/0.97,metadata-not-waiver0.86/0.79,and physical promotion not
established0.61/0.41. The limited source-coverage judgment is not promoted into
proof;the deterministic whole329-file comparison and explicit source tests
provide their narrower evidence. No physical claim follows from the judgments.

The olderf9 cohort is preserved as2294 files/563732366 bytes under
`.local/npu-validation-capsules/provider-link-f9-v1`;preservation is not a
complete execution replay. None of the failed/canceled attempts is retagged
as passed or silently replaced.
Preservation receipt SHA256
`a408d342628ed7359a81aa1bc71cccd2aee220ffaa9b6e1be899d43ee5ea05d5`.

## Native And Hardware Boundary

Live-view `.local/npu-mt76-link-20261017/live-views-q2.json`, SHA256
`c4feaf4feba72de3be1ae3a7d95533f5955f489050ca277c7297a55738c75491`,
checks both original native callers'2330 source files/five supplements unchanged.
The first new diagnostic incorrectly requested `dma.c`,which was not in that
producer's declared input set;the failed diagnostic source is preserved.
Correctedq2 explicitly checks the actual declared inputs and records that
absence. No original file,receipt or source hash was waived or changed.

Both callers and the two eight-DESC10-fault matrices continue on600055c's
preserved cohort. Their pending results do not qualify newer main. Constructor,
all required faults,broader raw,checked RRO/IRQ/hot/workers,complete stack and
physical DMA/cache/exclusion/drain/lifecycle/reset/recovery/client gates remain.
No module load,vmlinux/world/image rebuild,flash,radio/reset,reclaim,hardware
operation or subagents. The protected FIT remains unchanged.
