# GitHub Sync And WSL Firmware Validation

2026-10-01. The user requested refreshing from GitHub, synchronizing this
computer and continuing the full NPU objective.

## Source Synchronization

GitHub main was already at `59e75a8`; the new work was draft PR #1 on
`codex/npu-cold-memory-cloud-validation-20260930`, commit `9218506`.
Its pre-copy memory plan and build-host changes were reviewed and brought into
the canonical WSL checkout. The three deferred history documents were applied
and the temporary publication patch removed. The resulting tree exactly
matches the cloud agent's recorded full tree:
`f2a52b2c27e21021e8c36d4b30a25e37565827c2`.
Commit `e095420` preserves that complete snapshot before local continuation.

Only the integrated NPU patch differed in the existing prepared OpenWrt tree.
It was synchronized from the new source lock; the full build regenerated the
provider with SHA256
`026789bacd65b4a8c6ff25317c4ba8b33acfd52dde66c7c455758812ce8fe582`,
matching the canonical replay and cloud source receipt.

## Local Image

The complete WSL world build succeeds. Offline verification passes FIT hashes,
Gemtek W1700K model/compatibility 2.0, configured NPU memory reservations,
firmware identities, 218 package checks, 78 module ABI checks and ten RV32
components. The RV32 component library still is not a bootable replacement.

- Image: `.build/merged-openwrt/bin/targets/airoha/an7581/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb`
- Size: 26,932,042 bytes
- Local image SHA256: `277abd0b754200a0b330a35d4c759f264f918ec182cddc6c650fb734f46b4e4b`
- Packaged NPU provider SHA256: `29a25d03b19e8927a230d5f82369325d26af064dd73b066761a9c35b52e6eed9`
- Source-lock SHA256: `6f814270a93b156fab0b3d71e46a4ff1a8bab18bd1c44c85c1aa71580d017aba`

The provider matches the cloud packaged module exactly. The complete local
image has a different hash from the cloud image and is identified separately.
Both retain revision `r36536-merged-288d79449f` and kernel 6.18.52; version labels
alone cannot identify either update.

The previously flashed image was copied and rehashed before rebuilding:
`.local/github-sync-20261001/flashed-20260923-sysupgrade.itb`, SHA256
`132a35c746e008345032d1c862ea1ace1ef7a27d87a3fd363b8225045554e670`.
The retained R1 rollback baseline is separate. No new image was flashed.

## Continued Validation

Local replay passes 273 loader cases, 165 additional load scenarios, three
original failure controls, nine mutants, 6,174 retry cases and 44 V2 executor
cases. The eight build-host tests also pass.

The portable runner previously forced LeakSanitizer off and attributed that
choice to a cloud restriction on every host. It now enables leak checking by
default, accepts `--disable-leak-check` for a host that requires it, and records
the actual sanitizer selection. A complete fresh WSL run passes with address,
undefined-behavior and leak sanitizers enabled. This remains actual host C with
modeled OF, I/O, firmware and mailbox dependencies.

The reviewed `firmware_loaded` flag records successful copies before the later
boot-register sequence. The memory plan validates geometry and snapshots
addresses; it does not claim exclusive physical ownership or completed DMA.
Jev corroborates these bounded claim distinctions; requests and probabilities
are retained as supplementary evidence.

## Next Work

The existing pinned management path requires a configured Ethernet address,
which was unavailable. A later interface check showed only a link-local address.
No router connection or hardware test was
attempted through another interface. Current board/layout, serial recovery and
protected backups must be revalidated when the wired connection is available.
The cloud physical handoff remains useful for method and scope, but a proposed
test of this local image must use the local hash above.

The full objective remains open: contained cold-provider lifetime and engine
coverage, fresh loader identity/storage publication, real DISCOVER/setup/BIND
callers, native postgate execution, physical drain/teardown/rearm and actual
client acceptance. Passing this synchronization/build checkpoint does not
complete the NPU implementation.

## Replay

```sh
python3 tests/npu/test_cold_memory_plan.py --name fresh-wsl-replay
python3 -m unittest discover -s tests -p test_build_firmware_host_tools.py
python3 tools/build_firmware.py --destination .build/merged-openwrt --name fresh-wsl-build --jobs 8
PYTHONPATH=.local/npu-reset/python-lib python3 tools/verify_merged_image.py --name fresh-wsl-image-check
```

Use fresh result names. Image builds replace outputs in their build directory;
retain any needed current image first. Binaries, build logs, private inputs and
local recovery copies remain ignored; this checkpoint publishes text receipts.
