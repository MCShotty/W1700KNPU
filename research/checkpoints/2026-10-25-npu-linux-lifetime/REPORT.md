# Linux UML Work And HIF2 Lifetime

Date: 2026-10-25. Base: e87f1d04bf7ab5a500424126af556c7e37c5db16.
Classification: progress. Full NPU reverse engineering and implementation remains
active. Continued without subagents.

## Result

Selected current driver C executes inside Linux 6.18.52 User-mode Linux (UML).
All 14 positive KUnit cases pass, with zero failures, crashes, errors or skips.
Six compiled negative controls each produce exactly their intended KUnit failure,
with zero crashes, errors or skips. Eleven separate host-only verifier units pass;
their synthetic logs and mocked parser are not additional kernel tests.

The successful execution producer is
'.local/npu-build-scratch/native-c2/linux-lifetime-lifetime-q7/result.json',
SHA-256 a28080b85a5d116625fecb8c6a70cc6c57f56290ac1ac16de9a86d343beab181.
The executed kernel SHA-256 is
1bc41df809ec73b5f79020be68e34845dae5c9cbefae73514c9729da465f36b0.
Its config SHA-256 is
9efb4541e1bb39d6ed89aa6e241307ffa146c27e684b20f6a70d733d6ad5ff4d.
Raw logs, official parser output, commands, selected/generated input digests and
the two built-in component objects are retained locally.

## What Actually Ran

The public staging tool extracts the current mt7996 constructor, init and cleanup
bodies, state enum, HIF2 lookup/init/probe/remove bodies, HIF type and register
constants. Work structs, workqueues, disable/cancel operations, kthreads,
completions, device links, driver-core probe/remove, device references and devres
are real Linux implementations. Object undefined-symbol inspection checks the
required Linux API imports before execution.

KUnit executes built-in kernel tests and reports KTAP. The official parser can
also process a manually captured kernel log; these operations are distinct from
building or executing the kernel.
[KUnit architecture](https://docs.kernel.org/dev-tools/kunit/architecture.html),
[KUnit runner and parser](https://docs.kernel.org/dev-tools/kunit/run_wrapper.html).

| Group | Positive Cases | Checked Behavior |
| --- | ---: | --- |
| Work | 11 | Cold recovery admission; held init, RC, dump, reset, WED, scan, primary mac/ROC and extra mac/ROC callbacks; join before retirement; self-requeue and post-cleanup rejection |
| HIF2 | 3 | Supplier unbind waits for consumer probe/remove; already-unbinding helper rejection; failed consumer probe releases dependency and explicit reference |

The HIF fixture registers a private synthetic bus and real devices/drivers, then
uses real device_add and device_release_driver callbacks. It never obtains its
result by assigning driver pointers or link states directly. The devres release
marker was registered before the actual HIF allocation, so it runs after that
allocation is freed.

Controls replace permanent disable with cancel for init or scan, omit RC joining,
permit cold recovery, omit the managed HIF dependency, or accept an unbinding link.
Each is compiled into the same image and selected by a recorded kernel parameter.
The log checker requires the exact case, failure message, parameter and result
counts, rather than accepting an arbitrary failed boot.

## Scope Boundaries

This is a UP UML kernel on an x86-64 WSL host, not ARM64/SMP execution of the full
mt76 module or a physical W1700K. CONFIG_DEBUG_OBJECTS_WORK and
CONFIG_DEBUG_ATOMIC_SLEEP are enabled; CONFIG_DEBUG_OBJECTS_ENABLE_DEFAULT is the
integer value 1. Read-only observation of the pinned kernel's work-disable
encoding coordinates held-callback tests; the fixture does not set that encoding.

Reduced mt76 field types are used. PCI presence, register mapping, bandwidth and
MMIO are synthetic. Radio/mac80211, MCU, DMA, IRQ, NAPI, NPU-owner and TX-worker
internals remain explicit models. This qualifies selected code against the real
tested Linux APIs, not every driver call path or physical cleanup effect.

The synthetic primary deliberately returns -EIO before radio setup in late and
failed-probe cases. The HIF helper's -EPROBE_DEFER return is checked, but actual
deferred-reprobe policy is not exercised. No full registration-failure unwind,
real PCI binding, physical drain or whole-device concurrency claim follows.

## Kernel Provenance And Isolation

The existing linux-6.18.52.tar.xz archive is 154741268 bytes, SHA-256
2b69564f7d4fea0c859b1959ba33709ee6e9139bd100e30a853b57159a8221b8.
It matches the current OpenWrt recipe and the
[official kernel checksum](https://cdn.kernel.org/pub/linux/kernel/v6.x/sha256sums.asc).
This is checksum agreement, not a separate signing-key verification.

Sixteen whole critical workqueue, kthread, driver-core, device/header and KUnit
files were compared with the prepared target kernel. Fourteen are identical.
Two exact target files are overlaid: drivers/base/core.c changes the fw_devlink
default from RPM to PERMISSIVE, and include/linux/pci.h adds pci_dev.sysfs_init.
This is a focused critical-source comparison, not a full OpenWrt-kernel identity.

The private kernel overlay builds with host GCC 15.2.0/binutils 2.46, ARCH=um and
one build job. The original source is bound read-only. The system WSL kernel,
router toolchain, original target trees and previous build caches are not edited.
The runtime adapter reuses the completed selected-driver image; it does not
claim a fresh kernel compile.

The stock source inventory has 91236 entries, SHA-256
83e832d8071cd2de382320390195f56c58116af14931755f0d55d26fefe59f18.
The retained earlier UML cache inventory has 101408 entries, SHA-256
d9de98e65d31fb95f9e8ba0d9eda98e819cad8c3e196a2f20e927066793fda51.
Complete live inventories are compared again at sealing and after publication,
including file modes and symlink targets. They are bound-directory inventories,
not entries flattened into the separate project-file graph. Counts are not a
deduplicated total. The earlier ARM64 evidence graph is also rehashed.

## Retained Attempts And Resource Limits

All failed attempts remain failures. They include multithreaded-XZ extraction
OOM under the 400 MiB cap, the two real target-source differences, a boolean/
integer Kconfig request mismatch, the initial UML boot with a read-only HOME,
and inspection for a nonexistent combined object after a successful link.
The real built-in work/HIF objects are inspected instead. A later staging check
also refused tuple-versus-JSON-list equality; only serialization normalization
was corrected. None of these failed controllers is relabeled as a passing run.

One XZ decoder with a 192 MiB decoder limit resolves the extraction resource
issue. A private per-process HOME/TMPDIR resolves the UML startup path; the
kernel's failure path is not patched. The first cached build contains a copied
source-directory duplicate; it is retained but not propagated into the next
cache. The generic one-example bootstrap is not NPU qualification.

New phases use 400 MiB/no swap, include resident controllers/cache, hold the
existing C-scratch lock and retain fresh Windows RAM and dual backing-storage
checks. The driver execution reserves 512 MiB of C output capacity for its
128 MiB guest and logs; visible retained output is 29777484 bytes. The generic
bootstrap's visible-output monitor does not count unlinked UML RAM backing and
is not claimed as full backing-capacity qualification.

D conservatively reserves the old compact replay's 1 GiB future output, the
64 MiB new phase allowance and unchanged 2 GiB margin. No original replay cap,
VM/swap limit, system launcher or global execution policy changed. Older resource
controllers' generic kernel_concurrency=false fields are not UML test verdicts;
new metadata explicitly names the still-unqualified target ARM64 scope.

## Retained Firmware Status

No production driver, integrated patch, firmware lock, ARM64 module or router
image changed in this checkpoint. The source lock remains
88502ab3798b2ccdf01e6fd3c8779bcd2ad0f24a970c080f97ac9992b97f740a.
The retained four-module producer remains
a840d3cccb1d0bd8cc60a856d1a1bb9723dfc05af73484d955a33978a458d22f.
Its 18 zero-fuzz patch outputs, 31 mappings, module inputs and binary identities
are revalidated, not freshly compiled here. The earlier 15 host-suite receipts,
including 147 tooling tests, are retained results with unchanged bound inputs,
not 147 additional UML cases or freshly rerun suites.

Neither old replay handle exists in the current WSL boot. Missing is not success:
the original native third-profile failure remains and compact completion is
unproved. Neither original replay was restarted. The separate 60-second raw-boot
diagnostic question remains unanswered; its proposed limit was not used.

## Next Gates

Qualify actual ARM64/SMP and complete PCI/mac80211/IRQ/NAPI lifetime, full cold
physical cleanup and MCU-exit failures, and a real drain/retention contract.
Establish current-firmware BA ordering/cookies or a reuse fence; finish hot
admission, production retirement and rearm. Complete full native replays, the
current image, cold-fault/HIF2 hardware, actual clients, performance and stability.
No host module load, router image promotion, flash or hardware acceptance occurred.

EVIDENCE.json identifies the exact public blobs, private graph and execution
receipts. Source and test evidence stays distinct from physical acceptance.
