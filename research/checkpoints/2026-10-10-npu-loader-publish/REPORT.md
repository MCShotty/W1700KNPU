# Checked Loader Publication And Mainline Pair Packaging

Date: 2026-10-10. Canonical WSL workspace `/home/captain/W1700KNPU`.
Source baseline: `efb80ba58c8be41c1b44f9700cbfea0bfc00224b` on `main`.
This checkpoint is implemented and offline verified, not full NPU completion.
No router contact, module loading, hardware operation or flash occurred.

## Implemented

- Raw pair ABI v2 adds a 32-byte CODE tag at0x3f000 and a 128-byte DATA
  descriptor at0x6400. Exact header/tag fields and CODE/DATA-payload SHA256 bind
  layout/content. This is integrity, not authenticated publisher identity.
- Actual Linux C validates both markers, exact DATA length/offsets, digests and
  zero plan/session/identity slots before either copy. Oversized unmarked
  selected MT7996 images cannot silently take the small legacy route. Known
  small unmarked legacy images and other profiles retain their acceptance and
  firmware selection. The common lease/one-shot rules apply to every profile.
- The provider calls `get_random_bytes_wait` before exposure/copies and requires
  a nonzero identity. It publishes12 plan words/two identity words and reads
  back those14 words plus five zero session words before the boot trigger.
  The request address comes from the actual coherent core0 plan, not a fixture.
- Bare coherent allocations replace automatically reclaimed mailboxes. A lease
  latches exposure before copies and pins module/device/backing lifetime. Failed
  readback or detach retains all eight buffers; pre-exposure partial failures
  free only allocated buffers after IRQ/work producer cleanup. Same-instance
  reload and ordinary retained same-device rebind return `-EBUSY`.
- The normal world builder assembles/validates/stages the checked pair before
  package installation. The MT7996 recipe installs CODE, DATA and manifest;
  other profiles are unchanged. The archive remains separate, not raw CODE.
- The image audit caught cached old manifest metadata on an incremental build.
  All three staged files are now `PKG_FILE_DEPENDS` before package rules. Two
  subsequent worlds, including unchanged-source fresh-stage rebuilding, pass
  exact packaged-to-staged manifest checks. No failing receipt is called a pass.
- Pair assembly no longer depends on a historical stale-symbol ELF merely to
  run a negative control. That control remains enabled in its original test;
  production assembly uses fresh components and pinned original firmware.

## Exact Build

Linux6.18.52, mt76 `01367e60`, OpenW1700k `288d79449f`; revision
`r36536-merged-288d79449f`, board `gemtek,w1700k-ubi`, compatibility2.0.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| Final FIT | 26,956,618 | `05ca2802ec5c9149b2c1a928f829a61d666edb00d8a37316493689c28990001a` |
| Checked CODE | 529,336 | `bc15190ead08ebb44a6feba439f39ae8e7bcbaf9e5ce5851a3e2146ebd1893a5` |
| Checked DATA | 25,728 | `5311ef172aec19164723a273230d47fb147b7bee8e522f13a86580ce87c58d75` |

`image-final.json` records the exact provider/module/core archive identities and
package manifest. Final packaged pair manifest SHA256:
`5e991752cb8c4a7eb13f917c63edd1cfac77ae613633bc1d3ba3229afa966267`.
Canonical kernel patch SHA256:
`7dabb25a81d70c7f4ae9a289df34a08df9dbd5dc50f3bf14cc19f6b8a491ca4f`.
Source-lock SHA256:
`04a273fd62097aebc9a8fe6680cc697f1df8230f7e3c2f4e228bf9712b7eead8`.
Earlier verified8efb19fb, be11f1cb and3c0d1e3e FITs are preserved locally;
preservation receipts check the retained copies. R1/recovery/calibration/keys
are untouched. No raw image, vendor blob or device backup is uploaded here.

## Verification

| Scope | Result | Receipt |
| --- | --- | --- |
| Actual parser/RNG/publisher/one-shot C | 60 cases, eight compiled mutants rejected; ASan/UBSan/leak | `checked-loader.json` |
| Actual DMA lease cleanup/exposure/rebind C | 13 cases, four mutants rejected; sanitizers | `dma-lifetime.json` |
| Actual probe/IRQ/work/lease and managed-work helper C | 205 fault/delivery cases, two mutants rejected; sanitizers | `probe-lifetime.json` |
| Actual request preparation C | 310 cases,476 pre-copy checks, nine mutants rejected | `request-plan.json` |
| Canonical memory/loader/retry/V2 C | 273/159 cases, three prior controls, nine mutants,6,174 retry,44 V2; sanitizers | `memory-retry-v2.json` |
| Exact final packaged pair through actual C | 273 matrix/seven copy/publication/failure cases; canonical replay matches prepared source | `actual-pair-loader.json` |
| Native raw boot from actual C-published bytes | Eight harts parked; no synthetic plan/identity rewrites; old address/full-setup denials | `native-published.json` |
| Full raw RX0/RX2/TXDONE/BA instruction replay | 3,072 retained PKT/1,792 separate BA claims; six boot/eight TXDONE controls | `raw-native.json` |
| Independent assembly | Identical CODE/DATA;16 groups, zero skips,61 hooks/12 components/explicit NOBITS | `assembly.json` |
| Unit/replay checks | 13 builder/four verifier tests;57 OpenWrt plus five LuCI files reconstruct | `units.json`, `source-export.json` |
| Complete image and incremental package freshness | Worlds return0; FIT/DTB/hash/218-package/78-module ABI, exact staged pair/manifest checks | `build-final.json`, `image-final.json`, `image-first.json` |
| Current provider/Kconfig source style | Strict checkpatch:0 errors/warnings/checks | `checkpatch.log` |

The full raw replay used an earlier generation with byte-identical CODE/DATA;
the seal verifies equality to the final packaged pair. Generation manifests
differ because their component/output paths differ. The actual-C published
native boot is also byte-identical input, with external dependencies modeled.
The full ownership replay still grants an explicit held callback lease; it does
not open the real strict Linux setup lane. Tests use deterministic host RNG,
kernel/OF/firmware/I/O/DMA/devres/IRQ models and modeled native backing/scheduling.
Fixture-only lease retirement is test teardown, not a driver reclamation API.
Complete world logs contain upstream/package warnings and an ignored U-Boot
install error; this is not a warning-free build or a bootloader operation.

## Remaining Gates

1. Prove and implement prior-user physical cold exclusion/reset coverage before
   replacement, plus exclusive SRAM/DRAM reservation and cache/DMA visibility.
   The format flag, geometry, random API and metadata readback are not witnesses.
2. Wire real strict Linux DISCOVER/setup/BIND callers. Full RX0/RX2/TXDONE
   transport remains denied; source-only leases must not replace physical proof.
3. Finish other packet/page owners, workers/hot lifecycle and postgate consumers.
4. Implement physical drain/retirement, teardown/rearm/recovery and buffer/token
   reclamation. Exposure currently retains buffers and module pin permanently.
   The same-device guard is not containment of every earlier physical user.
5. Separately validate exact-image boot/recovery and actual clients/throughput.
   The last physical evidence is September23, not any image built here.

## Reproduction

Use fresh output/log names. Current executor supplies Unicorn2.1.4,
Capstone5.0.7 and pyelftools0.32 under `.local/npu-reset/python-lib`.
Clang/LLD, GCC/ASan and host OpenSSL headers/libcrypto are also required.
The originals are hash-pinned linux-firmware files, not device calibration.

```sh
export PYTHONPATH=.local/npu-reset/python-lib:tests/npu
python3 tools/build_firmware.py --target world --jobs 4 --name loader-fresh
python3 tools/verify_merged_image.py --name loader-fresh-offline
python3 tests/npu/test_cold_memory_plan.py --name loader-fresh
python3 tests/npu/test_checked_loader.py --source .local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c --pair .build/merged-openwrt/bin/npu-pair-loader-fresh --name checked-fresh
python3 tests/npu/test_npu_raw_pair.py --pair .build/merged-openwrt/bin/npu-pair-loader-fresh --name raw-fresh
```

The world wrapper requires prepared original linux-firmware or an explicit
workspace `--npu-firmware-directory`. Its fixed PATH does not implicitly add
Python dependency directories; supply the existing dependency environment.
Do not run prepared-source tests while a world build replaces that directory;
use the immutable staged source or wait for completion. Reported final receipts
exclude failed dependency-discovery, style, build/test-race and stale-manifest
candidates; those remain in ignored local storage for diagnosis.

## Semantic Scope Checks

Actual TypeSafe `jev-1.13.0` requests use the
[current official API](https://docs.typesafe.ai/api) and
[model documentation](https://docs.typesafe.ai/models); all raw probabilities
are retained. Four pre-change questions distinguish integrity/retention from
containment. Nine post-source questions classify parser/identity/publication,
retention/rebind, packaging and modeled versus physical evidence. Lower Noul
results for runtime identity0.78 and packaging0.75 were reviewed against actual
control flow, failure cases and exact image/incremental tests, not rounded into
acceptance. Physical containment Noul0.11 does not authorize hardware work.

After the package evidence changed, a fresh four-question review marks the
scoped package claim supported(probability0.99/confidence0.98), software-only
retention supported(0.91/0.86), hardware-completion claim contradicted(0.95/0.92),
and current scope wording Noul0.95. The retention uncertainty was reviewed
against actual exposure/cleanup/probe tests; no physical recovery claim is made.
Jev contributes semantic checking only, not code, tests, arithmetic or authority.

## Receipts

`seal_checkpoint.py` copies only allowlisted text receipts, checks their current
inputs/artifacts, verifies final package identity and preserves scope flags.
`verification.json` and `file-manifest.json` seal this checkpoint. Canonical
source and docs are integrated into `main`; the full project goal remains open.
