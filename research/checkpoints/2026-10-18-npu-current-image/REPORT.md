# Current Driver And Image Validation

## Full Image, 2026-10-20

The frozen `f282a13159ef627a8cc78d99e8cbfe9c516e4a30` source now passes a
complete offline `make -j2 world` build in private build/log overlays. This
supersedes the module-only status below, not its earlier evidence. The
6,168-file, 3,053,878,771-byte snapshot remains unchanged. The separate
namespace probe and final comparison both pass; all 891,138 original build
entries and 4,617 original cache entries retain their content, modes,
ownership and literal links. The build copies 3,774 declared download files
into its private writable cache and has no network access.

The new 27,009,866-byte FIT hashes:

`633b4d71d7307a262c1e3d67980fafdc0f7e9bad15163a893a910c850dfb3fc1`.

It is retained at
`.local/npu-isolated-world/world-build-q5/build-upper/bin/targets/airoha/an7581/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb`.
The protected original FITs `978f9ddd` and `a22300ea` are unchanged.

Offline verification checks the actual DTB model
`Gemtek W1700K (OpenWrt U-Boot layout)` and compatible `gemtek,w1700k-ubi`,
the built Linux 6.18.52 kernel, 218 installed packages, 78 module ABI checks,
and numeric rootfs boot ownership, including root-owned mode-0600 shadow.
Actual prepared sources match the five-file kernel patch, 22 Linux exports
and 329-file mt76 source manifest. Critical kernel/module and RV32 outputs
were cleaned only in the private overlay before building.

All 22 RV32 objects match their archive members. The packaged checked raw
pair has 20 components and 168 hooks, with CODE `858d1408` / DATA `40483c19`,
matching the current reader fixes. No loader provisioning or physical
acceptance follows. The existing compatibility-2.0 partition-layout warning
is retained; this report is not a flash or chainloader instruction.

`WORLD.json` contains metadata only, SHA256
`de06f3a1e6e7e2682b50174cffec826a9bf3b8cca8fb022680ebe86dfce97554`.
The independent 6,213-path scope audit hashes
`413328b351963fdcd1ca3ac54cce9baf7e9d96ab6626252c46431895677a7d5e`;
the outer world receipt hashes
`8101de147c8cf58954e3055ef53f361f38c5d793b61c2a1f1fcd16b31796a8e0`.
These are build/image checks, not module loading, boot or NPU acceptance.

Both current cold callers are now terminal failures during initial INODE
capture. Their preceding full-512 DESC10 and all three tail stages have
validated traces, but neither produces a complete constructor verdict or
stage-1 INODE prefix. See `../2026-10-17-npu-late-readers/TERMINAL.md`.
Full fault matrices/setup, hot TX/RX, checked IRQ/rearm, RRO, physical
ownership/cache/drain/recovery, remaining original/indirect/stack contracts,
real Gemtek boot and client/performance/stability gates remain open.
No flash, hardware contact or subagents occurred.

Five focused Jev wording checks distinguish offline image evidence, failed
callers, the stop hypothesis, running fault diagnostics and protected older
inputs. Raw support probabilities are 0.99/1.00/0.97/0.98/0.99, with
confidence 0.98/1.00/0.95/0.97/0.98, model `jev-1.13.0`. Result SHA256
`a53ff0570bed4df1d15f3278022a9666b57414ef2ea200a1fc9717f2a879d8a4`.
These assess the supplied wording, not firmware correctness or permission.

## Earlier Module-Only Checkpoint

2026-10-18. This checkpoint qualifies isolated compilation/linking only.
No new complete image, module load, native cold setup or hardware is qualified.

The current tracked kernel patch applies with zero fuzz to the independent
upstream reference. All five patched files and22 locked Linux component
exports match their canonical sources. The export set contains five C files
and17 headers,not22 headers. Neither`cold-inode.c` nor`cold-pcie-tail.c` belongs
to that Linux export set;their native implementation changes are bound by Git
and raw-pair manifests. The source lock remains
`d6b6e2daf745414e82579bc89308821c5ba392d805fe3a220cd184dacbef7f47`.

A complete independent copy of the prepared Linux6.18.52 kernel links the
current AArch64 provider successfully. Its three exports/70 imports,22 source
exports and`6.18.52 SMP mod_unload aarch64` metadata are checked. All102685
original prepared-kernel files/relative links/content/modes remain unchanged.
The compile uses OpenWrt GCC14.4.0 and the real pinned kernel configuration.

The11-file mt76 patch applies with zero fuzz to its pinned upstream revision.
All329 source-manifest files match the resulting current tree. The real final
`mt76.ko`,`mt76-connac-lib.ko` and`mt7996/mt7996e.ko` links pass against the
new provider and actual dependency symbol indices. All module version metadata,
six mt7996e-to-mt76 NPU imports and unchanged original kernel/mt76 trees pass.
These checks do not establish runtime IRQ or physical ownership contracts.

The separate build-contract suite passes74 unique tests,no skips. It overlaps
other focused selections and is not added to their totals. Private receipts:

| Scope | SHA256 |
| --- | --- |
| Provider | `6fbcbd28837c7473586e8075b7037a550f108cf58e690d1353e1838e8a6030a9` |
| mt76 consumers | `863dc755bd50f19a51422f359cd1bf29de4a319861f40456db0899fb66b5fab2` |
| 74 build contracts | `7c319a8f06c9fe91eae74c1312ddd910c04dab714f7573cafc6a62ceed1e1819` |
| Module-scope audit | `8ce1f6ecab656feeb0b42301c14505017df1203b9a4c8b411f72115b62fff3c9` |

`MODULES.json` contains bounded metadata only. It hashes
`f381fa9758eaba828df6425fa91d6fe698174330fc33198b00e46bfa2ac1d488`.
The producer commit is`5b314c040e113985409d9a03ad02d8bdfa4c0146`.
Both protected FITs remain978f9ddd/a22300ea;paired CODE/DATA remain858d1408/
40483c19. Neither existing image is requalified or modified by these links.

Next: freeze current source, producer references, tool inputs and the checked
offline download cache for a full build in private build/log overlays. That
build must separately validate actual prepared sources, FIT/Gemtek W1700K,
packages/modules and numeric rootfs ownership without modifying the original
build/cache or protected images. The current v3 cold callers remain active;
full512/eight-DESC10/all36-tail/actual INODE stage1/new24 faults,full setup,
hot/checked IRQ/RRO/lifecycle/DMA/cache/drain/recovery/remaining original and
indirect/per-hart/physical/boot/client gates remain. No flash or subagents.
