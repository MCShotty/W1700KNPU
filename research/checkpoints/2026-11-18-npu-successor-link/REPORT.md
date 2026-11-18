# Successor Module Link And Source Promotion

## Actual Link

The bounded, offline user service `w1700k-successor-link-20261118-b.service`
(invocation `3ddb8e6a`) exited zero. It used the exact source authority
`74879585`, one Kbuild job, a 1.5 GiB cap and no swap. It reused prepared
kernel headers and dependency exports. It cleared 38 old target outputs
inside a private kernel overlay and compiled mt76 from a clean copy of
all 330 pinned inputs.

Four AArch64 NPU and Wi-Fi modules completed modpost and final linking.
`mt76.ko` imports both new queue-owner functions from the fresh provider.
Under the pinned OpenWrt normalization, the provider, mt76 core and
MT7996 modules differ from the baseline, and the rebuilt connac library
is byte-identical. The Ethernet scratch link has the PPE and QDMA owner
symbols and reproduces the earlier independent scratch result after
normalization. The full world must still supply its own Ethernet module.
Modpost emitted the existing missing-description warnings for the two
Airoha drivers; there were no unresolved symbol errors.

The service matched both retained inventories after the build and
published the thin read-only module bundle. A separate verification
matched its receipt `659a9626`, all 412 inputs, four raw module artifacts,
and the new source contract. The baseline seal and its frozen sources
are unchanged. [Exact pins](EVIDENCE.json).

## Canonical Source

The verified stack is now the canonical source: lock `e4ac1fd7` and
seven exact overlay files (board DTS, five kernel patches and one mt76
patch). The original integrated patches, build configuration, upstream
versions, and 31 component mappings are unchanged. The old raw OpenWrt
lower tree was not promoted or rebuilt in place. Its separate sealed
offline FIT is still the baseline.

For future capsule assembly, use the current tracked tree and explicitly
select the successor's private prepared sources, contract and producer.
Do not overwrite the older private `kernel-merged`, `mt76-merged`, or
frozen replay inputs. The original staging command rehearses the old
parent lock; use the verified source authority for the promoted stack.

Next: freeze and run the successor's own RV32 replay, build the world,
and verify the produced FIT against the four-module producer and its own
Ethernet module. No successor FIT, module load, physical retirement,
boot or router contact here. All 132 focused host tests passed.
