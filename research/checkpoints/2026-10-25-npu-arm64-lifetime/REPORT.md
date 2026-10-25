# ARM64/SMP Work And HIF2 Lifetime

Date: 2026-10-25. Base: 603c290e2d609c43466eca09bc5277ffd1e63a95.
Classification: progress. Full NPU reverse engineering and implementation stays
active. Continued solo.

## Result

Selected current constructor/init/cleanup and HIF2 lookup/init/probe/remove C now
runs inside Linux 6.18.52 on two emulated Cortex-A53 CPUs. All 14 positive KUnit
cases pass, with zero failures, crashes, errors or skips. Six driver-behavior
controls and two CPU-topology controls each fail the intended KUnit assertion;
none crashes, errors or skips. Twenty separate synthetic-host verifier units pass.

The shared fixtures' default UP/UML mode is freshly rebuilt and executed too:
14 positive cases and all six original controls pass their respective checks.
The same 20 verifier units pass in that phase, not 20 additional unique tests.
Its producer is
'.local/npu-build-scratch/native-c2/arm64-lifetime-compat-q9/result.json',
SHA-256 15bdee3509f312290b359e1edb8f73245edadb7b39cfb86ef5804ea2fc1d6477.

The final execution producer is
'.local/npu-build-scratch/native-c2/arm64-lifetime-run-q7/result.json',
SHA-256 b2deaab205f30d7f78b1abaa29955816141f6d089035a0e6cd3740b578b2860d.
The final generic ARM64 test Image SHA-256 is
8996f4b794d5e5d1e9999f385c043943ae7239ad1662e22ab06e689f5c1eed3b.
The vmlinux SHA-256 is
40287d17b0c5859f70cbf860b0c7d2fae626acfaf964a36648a8b7209331cfe4.
The config SHA-256 is
42281ef23d60d22c09445912c76b52c5187eaaf138b51e5f56ae2e8a8ae18230.

This is selected-code ARM64/SMP Linux API qualification. It is not execution of
the complete mt76 module, W1700K board emulation, physical DMA drain, native NPU
firmware completion, a router image, or actual-client/performance acceptance.

## Cross-CPU Evidence

The SMP mode requires CPUs 0 and 1 online. Work uses WQ_PERCPU and explicit
queue_work_on/queue_delayed_work_on placement on CPU 0. The cleanup kthread is
created stopped, bound to CPU 1 and then awakened. HIF consumer probe and supplier
unbind threads are similarly bound to CPUs 0 and 1. No workqueue worker's affinity
is changed from inside its callback. The default non-SMP test mode keeps its
original ordered queue.

Callbacks record their actual raw CPU IDs. The verifier requires the exact
per-case JSON observations, two online CPUs, both SMP kernel parameters, and the
expected case set. Kernel config and the VM's requested CPU count alone are not
accepted as cross-CPU proof. QEMU logs also show both processors activated.

| Cases | Observed Scope |
| ---: | --- |
| 1 | Cold constructor recovery admission, with two CPUs online |
| 10 | Held init/RC/dump/reset/WED/scan and primary/extra mac/ROC work on CPU 0, cleanup on CPU 1 |
| 3 | HIF consumer probe on CPU 0 and supplier unbind on CPU 1, using real driver-core links, references and devres |

The six earlier controls retain their exact intended failure checks. Two new
compiled topology controls place cleanup or unbind on CPU 0 and must fail the
CPU 1 assertion, while recording that same-CPU arrangement. No arbitrary failed
boot is accepted. The official KUnit parser checks exact case/status counts;
the additional checker validates placement and rejects missing, duplicate,
wrong-CPU, boolean-CPU or wrong-online-count observations.

KUnit supports separate cross-architecture configuration/build and parsing of
captured logs. [KUnit runner](https://docs.kernel.org/dev-tools/kunit/run_wrapper.html).
Bound and unbound workqueues have different CPU-locality contracts.
[Linux workqueues](https://docs.kernel.org/core-api/workqueue.html).

## Real Implementations And Remaining Models

Linux workqueues, disable/cancel APIs, kthreads, completions, scheduler binding,
driver-core probe/remove, device links, device references and devres execute.
The built-in object imports are inspected before boot. The kernel is an
EM_AARCH64, 64-bit ELF with CONFIG_SMP=y, CONFIG_NR_CPUS=2, work-object debugging
enabled by integer default 1, and atomic-sleep debugging.

Reduced mt76 types remain; this is not a full-module layout/ABI test. PCI
presence, register maps, bandwidth and MMIO are synthetic. Radio/mac80211, MCU,
DMA, IRQ, NAPI, NPU-owner and TX-worker internals remain models. The synthetic
primary still returns -EIO before radio setup; actual deferred-reprobe policy
is not qualified. Controlled cross-CPU schedules do not prove all schedules,
weak-memory cases or physical timing.

The virtual platform is virt-10.2, not an AN7581/Gemtek board. QEMU documents
virt as a generic platform rather than a real machine and supports the selected
Cortex-A53 model. [QEMU Arm virt](https://www.qemu.org/docs/master/system/arm/virt.html).
No Gemtek FIT/DTB identity or physical boot is claimed for this test Image.

## Provenance And Resource Boundaries

The prior stock Linux archive/source and the same two exact target overrides
are reused: drivers/base/core.c and include/linux/pci.h. The earlier 16 critical
file comparisons stay bound. This is not full OpenWrt kernel identity.
The source archive SHA-256 remains
2b69564f7d4fea0c859b1959ba33709ee6e9139bd100e30a853b57159a8221b8.

OpenWrt GCC 14.4.0 cross-compiles the generic test kernel, with one build job and
the explicit compiler GC parameter ggc-min-expand=5. Host compiler/toolchain
identities are retained. The original source is read-only behind a private
overlay; prior UML and completed ARM64 caches are not modified.

Four Ubuntu APT-identified packages supply a private QEMU 10.2.1 runtime on the
existing C-backed scratch volume. Download sizes and SHA-256 values match the
selected APT metadata. No global package installation or maintainer script runs.
The runtime uses two vCPUs, TCG multi-thread mode, a 32 MiB translation buffer,
192 MiB guest RAM, no default devices/network/storage, and a 90-second per-boot
deadline. Live QEMU mappings are captured and 48 actual executable/library file
identities are checked. Host libraries remain external; this is not a hermetic
runtime. Two missing package changelog links are retained as documentation
aliases, not repaired or treated as missing runtime code.

All new phases retain the 400 MiB/no-swap ceiling, fresh Windows RAM checks,
dual backing-storage margins and the existing C-scratch lock. C reserves 4 GiB
for kernel builds and 512 MiB for execution. D still reserves the old compact
replay's 1 GiB future output, 64 MiB phase allowance and unchanged 2 GiB margin.
The completed initial ARM64 build occupies 162979704 visible bytes; its repaired
copied build occupies 164009412. Final execution output is 413691 bytes.
No old replay cap, VM/swap policy, system launcher or global execution policy
changes. Tracking-body backups are on C to avoid duplicating them on D.

## Retained Diagnostic Failure

The first ARM64 run passes all 14 positive cases and six original controls, then
the verifier refuses the new same-CPU work control. The intended CPU assertion
fails, but the expanded READ_ONCE assertion text is truncated before the required
custom message. That whole controller remains
failed; it is not relabeled as a complete pass.

The two fixture sources are preserved before repair. Assertions now compare
short local snapshots, keeping both the CPU requirement and intended-message
check. A copy of the completed build is rebound at its old private O= alias for
an incremental rebuild; the original 3684-entry cache remains identical, SHA-256
e50144e6a741d6c820821247f6e8358b929bd835abb158e8b54963ee852b8e05.
The fresh final run executes every positive case and all eight controls.

Full live source, earlier UML-cache and original ARM64-cache inventories are
recomputed at sealing and after publication. Their separate entry counts are
not deduplicated totals or flattened project-file counts. Earlier evidence
bindings are rehashed with the exact superseded public test/doc bytes preserved.
The default-mode run also verifies its original selected-UML cache unchanged;
that directory and the final ARM64 cache are inventory-bound in the new seal.

## Firmware Status And Next Work

Production source, the integrated patches, four existing ARM64 module binaries
and firmware lock are unchanged. The lock remains
88502ab3798b2ccdf01e6fd3c8779bcd2ad0f24a970c080f97ac9992b97f740a.
The retained four-module producer remains
a840d3cccb1d0bd8cc60a856d1a1bb9723dfc05af73484d955a33978a458d22f.
Those module and earlier host-suite results are revalidated retained evidence,
not fresh module builds or freshly rerun old suites.

The physical cold cleanup gap remains concrete: mt7996_mcu_exit does not return
its failed-exit status to cleanup, and mt7996_dma_disable writes reset/disable
registers without returning an idle/drain result. CPU callback joins do not
establish that physical retirement contract. No hardware failure was reproduced
by these synthetic lower layers.

Next qualify the complete PCI/mac80211/IRQ/NAPI paths, physical cold/MCU failure
handling and drain/retention, current-firmware BA ordering/cookies or a reuse
fence, hot admission, production retirement and rearm. Complete full native
replays, the current router image, hardware/cold faults/HIF2, actual clients,
performance and stability.

Both old transient replay handles remain absent in the current WSL boot, not
successful. The original third-profile native failure and unproved compact
completion stay unchanged. Neither is restarted. The separate 60-second raw-boot
question remains unanswered and that proposed budget is not used. No host module
load, router image promotion, flash or physical acceptance occurs.
