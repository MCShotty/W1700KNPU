# Provider And Host Kernel Link

2026-09-23. Provider candidates 928/929 now compile and link into an isolated
copy of the prepared AArch64 6.18.44 kernel. The retained mt76 candidates also
link against that kernel. This adds a linked-kernel check for the provider
candidates. Runtime NPU operation and V2 host integration remain open.

## Inputs And Isolation

The runner pins the host-lifetime and linked-module receipts, verifies the
original provider/header hashes, copies the prepared kernel using independent
files, and preserves its internal relative symlinks. It applies 928 followed
by 929 with zero fuzz. The resulting provider and public header match the
earlier host-lifetime candidate hashes exactly.

All generated trees stay under `.local/npu-provider-kernel-link/`. The original
kernel, configuration, source lock, cumulative OpenWrt patch and release build
configuration retain their hashes. The existing prepared objects are available
to Kbuild: this is a rebuild/relink of a prepared tree, not a clean OpenWrt or
toolchain build. No candidate was promoted into the packaged sources.

## Results

`make vmlinux modules` succeeds with the existing kernel configuration.
`CONFIG_NET_AIROHA_NPU=y`, `CONFIG_RELOCATABLE=y` and disabled symbol versioning
remain unchanged. The linked `vmlinux` is AArch64 `ET_DYN`, as is its baseline.
Its regenerated `Module.symvers` and ELF export symbols contain all three GPL
provider entries: `airoha_npu_get`, `airoha_npu_put` and the new
`airoha_npu_wlan_control`.

The provider object contains `devm_work_drop` and no longer contains
`airoha_npu_remove`. Its source matches the previously tested managed-work
lifetime candidate. Earlier sanitizer and lifecycle models were not rerun;
these symbols and this build do not independently prove runtime ordering.

The NPU-enabled `mt76.ko`, `mt76-connac-lib.ko` and `mt7996e.ko` all relink.
Their vermagic remains `6.18.44 SMP mod_unload aarch64`. The NPU RX poll and
corrected shared parser are present. MT7996's six NPU imports resolve to mt76;
mt76's get/put imports resolve to the rebuilt provider. The existing 351-export
index reconstructed from installed mac80211/cfg80211/compat modules is still
used because their original external `Module.symvers` is unavailable.

A separate unloaded GPL probe includes the corrected public kernel header and
links a call to `airoha_npu_wlan_control`. The actual mt76 module still imports
only provider get/put: the new control transport is not yet wired into mt76.

| Artifact | SHA256 |
| --- | --- |
| `vmlinux` | `85d33ff1ad893aba996ba92f1f374d3040c8254ed8e21d02f911be995f916eb1` |
| `mt76.ko` | `c0109ab02a198c2ba50aa53074127d6bc265cf9841a384edbfd0608ef4888bfe` |
| `mt76-connac-lib.ko` | `bec7037c9227f470bc02866e2878ae2b8eebaa9eaa5d1d2d4c8aad1fceda553d` |
| `mt7996e.ko` | `f783d8acd8c7a43a31f05a8fc8e5a30cd56bfd724249c7d54d53ee43b5dc5fcb` |
| Control export probe | `4244faf84c15e5453684368628eb1b224b0b42d265ee1b3dbba3366c8832ab65` |

Independent Windows readback matches all 45 unique files referenced by the
receipt, including protected inputs, patches, sources, kernel/module outputs,
dependencies and retained logs. Receipt: `provider-kernel-link.json`, SHA256
`cdd3284695bcc9b02b5290a9a04b956db6dd3967625d24b831cbd0e0f2be0cd8`.

## Diagnostics And Runner Corrections

The initial kernel build emitted 65 missing-description modpost warnings;
the first mt76 build emitted three, and the control probe emitted one.
`CONFIG_MODULE_STRIPPED=y` makes `MODULE_DESCRIPTION` expand to disabled
metadata in this target. The probe demonstrates this even though it declares
a description. These are recorded warnings, not a warning-free build claim.
No compiler or unresolved-symbol error occurred. The runner accepts only the
description-warning form for actual names in the kernel's `modules.order`,
the three known mt76 names and the one probe name.

The first runner stopped after successful kernel linking because it expected
`ET_EXEC`; baseline readback established that `ET_DYN` is correct. Subsequent
checks corrected the description-warning expectation, including the preserved
first kernel log. These were runner fixes, with no provider or driver source
changes. The checked copy was reused and Kbuild rerun. Initial logs and two
earlier runner versions are fingerprinted in the final receipt; cached later
builds do not replace the initial diagnostic record.

## Replay And Limits

Use the existing prepared inputs and a fresh ignored build/output directory:

```sh
cd /home/captain/W1700KNPU
python3 tests/npu/test_npu_provider_kernel_link.py \
  --build-name replay \
  --output-dir .local/npu-provider-kernel-link/replay-evidence
```

`--resume-build` rechecks the pinned provider/header/configuration and mt76
sources before rerunning Kbuild in an existing isolated copy. The runner
refuses to overwrite an existing receipt. The installed dependency modules,
matching GCC toolchain and pyelftools remain prerequisites.

V2 Linux client/binding, loader identity/publication/placement, postgate firmware
execution, full probe/unregister/reset ordering, IRQ/NAPI lifetime and physical
DMA/coherency/drain/recovery remain open. No module was loaded and no bootable
FIT/image was produced or qualified. Physical testing remains deferred. No
router, Wi-Fi configuration, protected data, restricted INODE/DESC operation,
subagent, deployment, flash or commit/push action occurred.
