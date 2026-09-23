# Unified Non-OC Merge Checkpoint

Source integration, full build and offline image verification pass. No router
contact, flash, physical recovery test, commit or push was performed.
Current scope, exact versions, artifact path and unfinished implementation:
[`docs/NONOC_MERGE.md`](../../../docs/NONOC_MERGE.md).

## Accepted Image

- Revision: `r36536-merged-288d79449f`.
- Kernel: 6.18.52. Board: `gemtek,w1700k-ubi`, compatibility 2.0.
- Size: 26,932,042 bytes.
- SHA256: `132a35c746e008345032d1c862ea1ace1ef7a27d87a3fd363b8225045554e670`.
- Full image remains in the ignored `.build/merged-openwrt/bin/targets/airoha/an7581/` directory.

## Receipts

| Receipt | Scope |
| --- | --- |
| `validation.json` | Input/artifact hashes, static checks, build results/log hashes, native executable-input rebinding |
| `image.json`, `fit.txt`, `fwtool.json` | FIT/DTB, 218 packages, 78 module ABIs, NPU symbols/memory, non-OC OPPs, firmware hashes, RV32 archive |
| `source-replay.json` | 60 changed files reconstructed from clean pinned checkouts |
| `prepared-driver-tests.json` | 20 exact source bindings; 109 preflight, 6174 retry and 44 executor cases; three retry mutants |
| `bootstrap-control-v2.json` | Integrated firmware gate, early-BIND/cold/fault/transport/policy tests and eight mutants |
| `bootstrap-composition.json` | All-hart initial parking with 50 detours, 209 host and 96 server comparisons, failure controls |
| `release-helper-tests.json` | 18 synthetic authenticated updater tests; no external requests or flash |
| `package-selection.json` | Every upstream explicit selection retained; six prior variants replaced with verified OpenSSL/MT7996 packages |
| `source-export.json`, `source.json`, `feed-pins.json`, `component-sources.json` | Source authority and upstream/component provenance |
| `jev-final-request.json`, `jev-final-result.json` | Bounded semantic claim checks, including raw probabilities and scope limits |

Commands used, from the canonical checkout:

```sh
python3 tools/build_firmware.py --name versioned-apk --jobs 4
python3 tests/npu/test_nonoc_merge.py --name prepared-final --prepared
python3 tests/test_prepared_sources.py --name source-replay-accepted
PYTHONPATH=.local/npu-reset/python-lib python3 tools/verify_merged_image.py --name image-accepted
PYTHONPATH=.local/npu-reset/python-lib NPU_EMULATION_TIMEOUT_US=60000000 python3 tests/npu/run_nonoc_bootstrap.py bootstrap --resume-build
PYTHONPATH=.local/npu-reset/python-lib NPU_EMULATION_TIMEOUT_US=60000000 python3 tests/npu/run_nonoc_bootstrap.py composition
python3 tools/record_nonoc_merge.py
```

These are retained execution commands, not permission to overwrite their output.
Runners reject existing output names; preserve receipts when repeating tests.
Native harnesses require the previously restored local analysis dependencies.
The final host metadata changed after native tests; `validation.json` verifies
all executable inputs remain identical and records the metadata-only differences.
Independent Windows SHA256 readback verified 151 source, receipt and image files.

## Limits

The Linux V2 client is compiled into mt76, but actual cold-session initialization
and setup/recovery callers are unfinished. The RV32 core archive is not a
bootable replacement: real loader identity/publication/placement, postgate hooks,
physical drains and complete reset/removal/rearm remain open. The supplied legacy
NPU binary is unchanged. None of the synthetic or emulation receipts grants
hardware cleanup or flashing authority. Protected backups, calibration and
signing keys are excluded from this checkpoint.
