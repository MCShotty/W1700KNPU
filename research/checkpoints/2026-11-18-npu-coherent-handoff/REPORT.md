# Rehearse the next W1700K build inputs

The later [combined bundle](../2026-11-18-npu-ppe-table-owner/REPORT.md)
adds PPE retention to this verified substack. This report records the
unchanged original `coherent-a` receipt.

The raw prepared OpenWrt directory has older copies of both integrated
patches. Using those copies on the retained component bases produced
different `airoha_npu.c` and `npu.c` bytes. Both were refused before the
new patches were applied. The active source authority is the locked
firmware overlays, not the copies in the prepared directory.

## Verified source-only bundle

The materializer reapplies the lock-authorized `999` Airoha and `900`
mt76 patches to sparse copies of the retained component bases. All 23
files produced by these existing patches match the combined producer.
It then uses OpenWrt's patch script at zero fuzz to apply the two late
kernel patches and the late mt76 patch. No offsets were accepted, and
all resulting files were compared with the pinned outputs. This rehearses
the end of each series, not a fresh kernel/package unpack and build.

The real private-world staging helper verifies a sparse copy with
83 OpenWrt paths, five LuCI paths and 31 component mappings. It refreshes
both stale integrated patches and introduces four locked source files:
two late kernel patches, the late mt76 patch, and the W1700K board DTS.
Compiling that staged DTS and its includes reproduces DTB `8c12d907`
from the [coherent window](../2026-11-18-npu-coherent-window/REPORT.md)
and [sizing check](../2026-11-18-npu-coherent-budget/REPORT.md).

The private bundle is `.local/npu-coherent-handoff-20261118/bundles/coherent-a`.
Its receipt starts `8911be49`; the derived lock starts `2b692d07`.
The parent lock, its previous patch files, prepared lower and replay
were not modified. The last router-tested snapshot is unchanged.
The bundle is a **source delta**, not a full checkout, compiled producer,
FIT or deployment candidate. [Exact hashes and refusal cases](EVIDENCE.json).

```sh
python3 -B tools/stage_npu_coherent_handoff.py --check coherent-a \
  --producer .local/npu-build-scratch/native-c2/fw-txp-20261118-modules-a/modules/result.json \
  --producer-sha256 b5af9591d0f6116547a08749fe733a98ac4d89b6088f8d1465950b052e4f69bd
```

Use `--name` with a fresh name to materialize the bundle again while the
parent inputs remain current. The verifier refuses changed layout, mixed
preimages, existing names, aliases and incomplete bundles. All 70
focused host regressions passed. No compiler for Linux or mt76 ran.

## Resume gates

1. Finish and verify the original replay and qualify its unchanged
   producer and FIT from the frozen snapshot. That FIT is baseline
   evidence, not a replacement for the low-pool candidate.
2. Activate the verified delta on the exact parent sources. Build and
   independently pin new linked modules against the derived lock; the
   old linked receipt cannot qualify changed sources.
3. Check the refreshed FIT, actual boot pool and allocation bounds
   before any release decision. Retained ownership still needs a
   physical retirement witness and real-client validation.

At the [read-only observation](REPLAY-LIVE.json), original profile 2
had 4,411 positive trace records. All 345 input bindings matched,
but the whole-run verdict did not exist.
