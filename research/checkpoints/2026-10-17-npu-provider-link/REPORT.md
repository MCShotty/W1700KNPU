# Current Provider Final Module Link

## Actual Build

`tests/npu/test_current_provider_module.py` applies the tracked integrated kernel
patch with zero fuzz to its upstream reference, checks all five resulting files
against merged source, and verifies all 22 locked component sources. It copies
the complete prepared Linux 6.18.52 tree into an independent local directory,
checks the copy against the original inventory, and installs current source
there. No original source, object, module, image or native capsule is modified.

Pinned AArch64 GCC 14.4.0 and the unchanged kernel configuration build the five
provider C objects, perform modpost, and link `airoha_npu.ko` at two jobs.
The real resulting module is AArch64/ET_REL, 247,152 bytes, with vermagic
`6.18.52 SMP mod_unload aarch64`. Its three exports are `airoha_npu_get`,
`airoha_npu_put` and `airoha_npu_wlan_control`; all 70 imports are present in the
linked kernel's symbol index. The module differs from the old prepared module.

Module SHA256:
`8f8a6a5480faf81ab6b047d484e88726aba143b876cd3ab08f80c504ae27b096`.
Build receipt `.local/npu-current-provider-module/current-f9-q1/result.json`,
SHA256 `6fef3cfc1924ef43fe61098e1f7203521eae95a5f4e431c82404caed089f308b`.
Producing HEAD was `f50fff27a394b63917064ca3fcc167ca56c715a9` and source-lock
`f9f90ba521cba96360784d53b265a6c4281d28ec84808671d662639893a0152c`.

The log retains one modpost warning: missing `MODULE_DESCRIPTION()` for the
provider. This metadata warning is not suppressed or counted as runtime
acceptance. No unrelated production metadata edit was made to remove it.

## Original Build Protection

The runner hashes all original regular-file contents and file modes, plus
literal internal relative-symlink targets. Absolute or escaping links are
rejected. All 102,685 inventoried entries match before and after the build;
the copied provider has a distinct inode, not a shared hardlink. Configuration,
generated configuration/UTS release and every selected source are rechecked.

A second scope pass repeats the original inventory comparison, checks that the
copied `vmlinux` was not relinked, reparses the actual module, verifies protected
prepared mt76/source/object/module/FIT identities and binds the build artifacts.
Compiler/toolchain and host runtime remain external. This is an independently
written output tree, not a complete portable or hermetic execution environment.

## Focused Controls And Seal

Eight new synthetic controls exercise exact inventory content/modes, changed
content/modes, addition/removal, internal relative links, rejected absolute and
escaping links, rejected host ELF and a tiny synthetic AArch64 metadata parser.
They do not link or load a real kernel module. The real module/build log above
provide the separate actual-link evidence.

Scope `.local/npu-provider-link-20261017/scope-q1.json`, SHA256
`7044084edce5dfb481fd11a2f40c2126905b138f302fa4acb66193d2bad0181ed`,
verifies 200 exact input identities and 218 unique selected unit cases in 236
executions, with no skips. Eighteen imported preexisting fixture cases repeat.
The deterministic mode test sets its initial mode explicitly before mutation.

Four focused Jev claim checks and full probabilities are retained in
`.local/npu-provider-link-20261017/jev-q1.result.json` using `jev-1.13.0`.
Original-tree guard: supported probability 0.96/confidence 0.94. Actual link:
supported 0.57/confidence 0.35, a limited-confidence semantic judgment. Runtime/
hardware and synthetic-test promotion were not established, probabilities 0.77
and 0.62 respectively. These judgments do not replace exact source/build/ELF
checks or establish runtime, physical or broader native behavior.

## Still Open

This closes only the isolated current-provider final-link gate. The module has
not been loaded. Current mt76 consumers have not been relinked against it;
`vmlinux`, the world and FIT have not been rebuilt. Source-lock and protected
prepared outputs remain unchanged. No complete IRQ contract, fresh current
cold-constructor/fault qualification, full setup, physical DMA/cache/drain,
reset/removal/rearm/recovery or actual-client acceptance follows from this link.

Both actual cold callers and the two eight-DESC10-fault matrices remain live
on their exact preserved older source. They were not restarted, rewritten or
promoted to current main. No fabricated SETUP, source-hash waiver, flash, radio,
reset, reclamation, hardware operation or subagents.
