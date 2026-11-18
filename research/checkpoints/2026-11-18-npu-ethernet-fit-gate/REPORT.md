# Bind the linked Ethernet module to the selected FIT

The original offline seal binds four NPU and mt76 modules but does not
identify Ethernet bytes. A source lock that selects the staged PPE or
QDMA patch now also requires the exact linked `airoha-eth.ko`. The
unchanged frozen baseline keeps its original four-module contract.

For the staged lock the sealer requires a separately pinned source
bundle receipt. The source-lock and overlay hashes must agree with the
world capsule. The prepared Ethernet sources in that world's private
kernel output must match the bundle postimages and the expected patch
sequence. The independently pinned raw module is read from that same
output, with the correct module instance, kernel ABI, provider dependency
and required owner symbols. A relocatable aggregate without Kbuild
metadata is rejected.

The verifier reproduces the strip transform using the objcopy and
configuration pinned by the four-module comparison. The normalized
Ethernet bytes must match the file extracted from the **default** FIT
configuration's SquashFS. An absent or different Ethernet file cannot
fall back to the four-module seal; matching Ethernet cannot replace any
of those four checks or the existing replay proof.

## Retained-Context Link

The exact combined PPE/QDMA objects passed real Linux `modpost` against
8,596 retained kernel and peer exports, and the real final AArch64
module link. The control regenerated the retained metadata and
reproduced the old packaged bytes. The staged module has both owner
functions, the `airoha_npu` dependency and the matching 6.18.52 ABI.
Both module links report the existing missing-description warning.

The new raw module is `d86b170f` and the expected packaged form
`d7428fa7`. These were built using retained kernel headers and exports
in scratch, not the successor's production world. Do not use this
scratch pin as the production module pin.

A disposable source/output fixture bound that real module, exact
prepared files and the pinned staged bundle through the new verifier.
It reproduced the expected packaged digest without claiming a world pass.

The unchanged prepared FIT `978f9ddd` selected `config-1/rootfs-1`.
Its actual Ethernet bytes `9e8307fa` match the retained control, not the
staged module. This is an artifact difference, not a failed boot.
A separate two-configuration FIT with inert payloads accepted the
matching default and rejected the stale default even with the matching
module still present in another rootfs. All 103 focused host tests
passed. [Exact evidence](EVIDENCE.json).

## Handoff

Reproduce the isolated link with a fresh private name:

```sh
python3 -B tests/npu/link_qdma_module.py --name NEW_RETAINED_LINK_NAME
```

After sealing the frozen baseline, the successor still needs a fresh
source-bound module producer, world and replay binding for its source
lock. Extend the normal seal command for that passing successor:

```sh
--ethernet-bundle .local/npu-coherent-handoff-20261118/bundles/coherent-ppe-qdma-a/receipt.json \
--ethernet-bundle-sha256 f3bd466ba6e62f7f65e4553f25e5b9e721042b7a1f7c9903fb92296dec775054 \
--ethernet-linked-sha256 EXPECTED_RAW_ETHERNET_MODULE_FROM_THE_PASSING_WORLD
```

No successor world or FIT was built here. No module was loaded and no
boot, physical DMA retirement, or board result was inferred.
