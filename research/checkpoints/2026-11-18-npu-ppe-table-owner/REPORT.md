# Keep exposed W1700K PPE tables across teardown

The [existing binary analysis](../2026-11-18-npu-ppe-stop/REPORT.md) found
that the PPE deinit reply does not prove retirement. The host publishes
the FOE table base to each PPE. The optional stats setup sends a separate
DMA address in a mailbox call and can also fail after the send, during
the host's mapping of the firmware's reply.

The exact retained kernel configuration disables flow statistics. The
pinned pristine and replay firmware both initially dispatch its selector
4 to a two-instruction stub that returns zero (refusal). This is evidence
for the saved initial table and bytes, not a trace of a running router.
The default path under test is FOE setup, not successful stats setup.

## Staged Change

The [late Linux patch](airoha-ppe-table-owner.patch) reserves the W1700K
front-end owner before probe can reset hardware. Offload setup marks each
buffer exposed before sending its address and pins the owner module before
the first such publication. Cleanup releases only unexposed buffers.
An ambiguous stats setup error blocks renewed setup but can still release
an FOE allocation that was never published. Other boards retain their
existing managed coherent allocations.

CPU detach closes the flow setup gate under the mutex before dropping the
NPU pointer and joining RCU readers. Any published allocation and its board
guard are retained, including after a successful firmware acknowledgement.
The owner prevents normal unload and same-board reprobe after publication;
the staged code has no post-exposure reclamation path. Do not force unload.
This covers PPE table storage only, not Ethernet QDMA queues, Wi-Fi
payloads, or a physical retirement witness. SRAM initialization now returns
the first failed completion instead of masking it.

## Verification

Nine cases use the patched C functions with synthetic allocation, firmware
and device behavior. All five compiled negative controls were rejected.
Two AArch64 translation units compiled with the retained kernel flags and
headers in temporary output; the checked declaration and definition agree.
These are isolated ELF objects, not a linked kernel or module. The patch
applied without offsets or fuzz and passed strict checkpatch. The 23
focused nearby regressions passed. [Exact build and case hashes](EVIDENCE.json).

```sh
python3 -B tests/npu/verify_ppe_table_owner.py --check --cross
```

## Next Build

`coherent-ppe-a` stages the PPE change together with the already checked
coherent provider, pool binding, board DTS and mt76 changes. The private
stager reapplied the final series, verified all postimages, and rebuilt the
same standalone DTB. Its receipt is `bcab9998` and its lock is `2f912d3f`.
The prior `coherent-a` receipt is unchanged. [Handoff pins](BUNDLE.json).

```sh
python3 -B tools/stage_npu_coherent_handoff.py --check coherent-ppe-a \
  --ppe-table-owner \
  --producer .local/npu-build-scratch/native-c2/fw-txp-20261118-modules-a/modules/result.json \
  --producer-sha256 b5af9591d0f6116547a08749fe733a98ac4d89b6088f8d1465950b052e4f69bd
```

The independent frozen baseline has reached kernel compilation and still
uses its original lock. Verify and seal that run's FIT before switching to
the staged lock. The new kernel must link `airoha-eth.ko`; bind its bytes
from the selected FIT in addition to the existing NPU and mt76 checks.
No new driver was loaded, no router was contacted, and no physical
retirement or offload performance was measured.
