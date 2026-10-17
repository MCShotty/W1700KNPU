# Current Provider And Consumer Module Links

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
