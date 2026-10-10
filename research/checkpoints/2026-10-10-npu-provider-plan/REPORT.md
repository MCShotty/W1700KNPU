# Pre-Copy Native Request Plan

Date: 2026-10-10. Base main: `ef29c39a4ba111874267b437c540b711368c6592`.

## Implemented

The canonical Linux6.18.52 provider now validates the MT7996 coherent core0
request buffer before requesting or copying either firmware image. It rejects
missing storage, a pending transaction, unaligned/out-of-window addresses and
overlap with firmware or any selected WLAN region. It does not substitute a CPU
source pointer or bake in an emulator address. Generic profiles keep their prior
behavior; optional-BA MT7996 remains usable without claiming a full native plan.

The provider prepares a private48-byte six-region snapshot from its firmware
region, validated WLAN snapshot and actual coherent DMA address. The native-plan
flag is set only with all four WLAN regions and fixed CODE placement0x84000000.
Absent BA or relocated legacy firmware leaves that array zero/unready. Failed
loads invalidate private metadata. No native ownership/claim state is erased.
This preparation does not write the plan into SRAM or create a boot identity.

The implemented correction is in the normal cumulative kernel patch/source lock,
not a separate branch. No public provider ABI or reset/reclamation API changes.
The raw-loader test now reconstructs the current provider from the canonical patch
instead of comparing every later version to the older installer-trace digest.

## Verified

- `request-result.json`: actual current provider C passes308 cases and476 checks
  at the modeled copy boundary, with address/undefined/leak sanitizers. Cases
  cover three profiles, DTS/default selection, optional BA, request boundaries,
  all reserved overlaps, pending/null storage, relocated CODE and failed reloads.
  All nine targeted mutants fail. The exact private plan is checked before each
  copy and remains a snapshot after modeled source fields change.
- `memory-result.json`: canonical source replay plus273 loader/165 added memory
  cases, nine earlier mutants,6,174 retry and44 Linux V2 executor cases pass with
  leak checks. These cover compatibility; they do not prove physical containment.
- `native-result.json`: the48 bytes emitted by actual provider C initialize the
  raw native firmware unchanged. Its modeled request base0x83000000 differs from
  the old fixture0x82000000. Native DISCOVER/version/six bootstrap commands/BIND/
  STATUS execute at the dynamic address; all eight harts park. Six wrong-address
  controls reject before payload reads. Native plan bytes exactly match C output.
  Loader SRAM/identity writes, allocation/OF/backing/IRQ scheduling are still
  modeled. Full strict RX0/RX2/TXDONE setup remains denied and is checked as such.
- `pair-loader-result.json`: actual canonical provider C passes273 matrix/seven
  exact-pair copy/failure cases with sanitizers. Byte readback and failed-copy
  destination retention are checked. No boot trigger or physical I/O is modeled.
- Independent fresh builds have identical raw CODE/DATA and15 assembly groups
  pass. Raw hashes remain `2c73c38a...` / `44e907a4...`; no firmware-core/native
  binding behavior is changed. No new full-size RX/TXDONE claim run is asserted
  in this checkpoint; the preceding raw checkpoint retains that covered proof.
- Full world rebuild returns0. Fresh offline FIT/hash/board/218-package/78-module
  checks pass. Packaged provider SHA256 is
  `7a401f45fad9285f5b97910e174a2ac0f1a15e7f5c3f3c7d721aa1be04e8ff27`.
  The12-object core archive remains `249a9a27...`, and packaged NPU blobs remain
  the original vendor pair. The new complete FIT SHA256 is
  `8efb19fb491f2446c50a367708c22a6882486c11f7b0ea03d41e99e37df239c5`.
- Strict checkpatch of only this provider delta passes0 errors/warnings/checks.
  The wider world build has upstream/package warnings and an ignored U-Boot
  install error; exit0 is not a warning-free-build claim. No bootloader operation
  was performed. The preceding FIT `230e03a7...` is hash-preserved locally.
- All60 OpenWrt/LuCI source files replay. The source-export verifier now follows
  the lock's canonical build directory and canonical component-source mappings;
  four focused tests and eight build-runner tests pass. It no longer consults
  the obsolete Daybreak20 checkout or looks for component inputs in a Git index.

`seal.py` checks current proof inputs and preserves scoped text receipts. The raw
pair,48-byte plan, modeled memory dumps, image and preserved previous image stay
in ignored local storage. The source lock changes only the kernel-patch digest.

Exploratory corrections: the request harness reset modeled firmware-request
accounting for a second load without wiping provider metadata; the old mutation
matcher was widened to cover the extended initialization block. An early repeat
comparison correctly rejected different source-input seals; fresh identical-input
builds pass. Export metadata was re-anchored only after exact mainline readback of
all four protected authority files, preserving the old local record. These failed
exploratory outputs are not final proof.

Jev's actual `jev-1.13.0` pre/broad post reviews are retained with uncertainty:
request-source Choice initially unknown(confidence0.37), later supported0.56;
the broad pre-copy claim was supported with low confidence0.31. Focused actual
source questions give Noul0.97 for pre-copy ordering/request-field derivation,
0.93 for incomplete-plan handling,0.97 for invalidation and0.08 for a physical
drain. Publication/full completion are contradicted(confidence1.0). These are
semantic evidence, not test proof, physical witnesses or universal thresholds.

## Reproduce

Use fresh names from the repository root:

```sh
export PYTHONPATH=.local/npu-reset/python-lib:tests/npu
python3 tests/npu/test_cold_memory_plan.py --name request-fresh
python3 tests/npu/test_provider_request_plan.py --source .build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.52/drivers/net/ethernet/airoha/airoha_npu.c --name plan-fresh
make -C firmware/npu pair PAIR_OUT=../../.local/npu-provider-pair-fresh
python3 tests/npu/test_provider_plan_native.py --pair .local/npu-provider-pair-fresh --plan .local/npu-provider-plan-20261010/plan-fresh/nominal/plan.bin --name native-fresh
python3 tests/npu/test_npu_pair_loader.py --pair .local/npu-provider-pair-fresh --name copy-fresh
```

The plan producer uses explicitly modeled allocation/OF inputs. This sequence
does not run a kernel module, install firmware, assert reset or flash a router.

## Remaining

The production loader still installs vendor CODE/DATA. Actual cold containment,
reserved/coherent storage, fresh per-boot identity and SRAM publication are not
implemented/verified. Numeric fit, private geometry and native software parking
do not authorize a reset, drain, reclaim or hot replacement. Do not call private
`native_plan_ready` a physical readiness/containment flag.

Continue actual cold-provider/retained-resource/publication and paired packaging,
strict Linux DISCOVER/setup/BIND callers, other owners/hot lifecycle/postgate,
physical backing/grants/cache/DMA drains, teardown/recovery/rearm and real clients.
No flash or hardware contact occurred. Protected recovery/calibration/keys and
rollback material were untouched. The full NPU goal remains active.
