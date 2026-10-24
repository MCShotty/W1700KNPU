# HIF2 Driver-Binding Ownership

Goal turn: progress toward full NPU reverse engineering and implementation,
not completion. Base commit: `cfdb7c981afb005e6035f239ff2f5d6bb7211f8c`.
Continue without subagents.

## Source Change

The old lookup retained `struct device` but returned an unpinned, devm-managed
HIF object. Removal changed the discovery list without its lookup lock.
These are source findings, not demonstrated router use-after-free incidents.

Lookup now returns the held device. Consumer probe adds a managed
`DL_FLAG_AUTOREMOVE_CONSUMER` link and requires `DL_STATE_CONSUMER_PROBE` plus the
expected HIF driver before reading fresh drvdata. It rechecks the HIF owner and
recognition ID. A non-null link alone is insufficient: the actual Linux 6.18.52
initializer can assign `DL_STATE_SUPPLIER_UNBIND` to an already-unbinding supplier.
The managed dependency survives consumer teardown; the explicit device reference
stays through existing IRQ/vector/WED cleanup. Link/qualification errors reach
the primary probe error path before NPU setup. Core-owned link cleanup is not
manually deleted. See the [kernel device-link contract](https://docs.kernel.org/driver-api/device_link.html).

HIF drvdata is ready before locked discovery publication. Removal locks and
unpublishes before clearing drvdata. Recognition IDs are allocated under the
lock and never wrap past the 31-bit hardware field. `pci_dev_present` replaces
reference-leaking presence probes. Absent hardware or no matching HIF remains
the original optional single-HIF path; it is not a global defer.

## Verification

- Candidate HIF2: 26 measured setups, 14 compiled intended mutation controls,
  ASan/UBSan/leaks. Actual selected lookup/init/probe/remove and Linux link-init/
  unbind-consumer C execute; other framework effects, locks, MMIO and scheduling
  interleavings are models, not live-kernel concurrency.
- Candidate PCI: all 234 previous cases plus 54 init-error cases pass, with 15
  controls. Defer/allocation/exhaustion errors stop before NPU setup and release
  the primary context without treating an error pointer as a HIF.
- Integrated patch reconstructs all 17 outputs at zero fuzz; 31 component
  mappings remain. Source lock:
  `b8901a719d37dd36b8be70c1d63ee7c33a6351ae541bad858c02a1082c442199`.
- Four GCC 14.4.0/Linux 6.18.52 AArch64 module links pass. Only `mt7996e.ko`
  changes; provider/shared-core/connac module bytes stay unchanged. Producer:
  `2b452f3f8b254259e2ce6804f28b6bb23cb075bf8d0358c40c236d8affed5a89`.
  All 102685 original kernel and 516 original mt76 inventory entries, plus the
  previous qualified cache inventory, compare unchanged before/after.
- Fresh installed-source HIF26/14, PCI288/15, detach16/2, NAPI44/12/separate
  TSan, IRQ360/10, BA-join37/8/separate TSan, owner23/14, creation19/12, BA18/6,
  worker23/8, 6150 resets/3, broad456/4 and callers1090/7 all pass. The tooling
  suite passes147 tests with zero skips. Counts denote measured setups and
  compiled controls, not a combined physical acceptance count.
- The first combined wrapper stopped after seven suites when the owner test
  had already written its result. It refused the duplicate write; that failure
  remains. An exclusive tail cohort finishes the remaining suites and rechecks
  every earlier suite's source bindings. The14-suite aggregate is
  `43e18ea1225e2ddbfbcbe439042b27e22c55cc79c1abf7b34fbc31f0ef40e20d`.

The compatible module receipt is
`.local/npu-build-scratch/native-c2/hif2-binding-current-q7/verified-modules/result.json`.
It retains the completed producer's verified status and copies the same four
binary identities for the existing receipt consumer; it is not another compile.

## Runtime And Resources

The fresh WSL boot has no old compact/native transient unit handles. They are
`not-found`, not successful completed jobs. No replay was restarted and no new
terminal verdict is inferred. The original native q3 failure remains retained;
compact completion is unproved. Three previous in-progress Jev artifacts were
zero length and are not used as successful review evidence.

The existing registered C-backed ext4 scratch share was restored and validated
by UUID, marker, native mount identity and Windows backing-VHD observation. New
output stays there under its existing lock. D still conservatively reserves the
old 1GiB future output, 64MiB phase output and unchanged 2GiB margin. New bounded
phases use 400MiB/no swap; modules reserve 512MiB on C and write 155598572 bytes
including controller metadata. The 400MiB includes resident controllers/file
cache, unlike the older 236MiB producer. No old cap, global swap, VM or system
launcher policy changed. Only the completed own auxiliary unit was released.

Jev retained raw probabilities, including 0.35 for the already-unbinding non-null
link interpretation. That uncertainty does not override the explicit selected
kernel switch and executable fixture. Actual checks govern scoped claims; no
model result grants permission or physical proof.

## Remaining

Qualify concurrent HIF2 unbind in actual Linux, complete cold-prefix work/MCU
unwind, establish current-firmware BA late/reuse ordering or a real fence, and
finish hot transport admission, production retirement/rearm and physical drains.
Both complete native replays, current full image, cold-fault/HIF2 hardware,
actual-client, performance and stability gates remain unproved. The new 60-second
diagnostic boot-budget question is still unanswered; original limits stay.
No module load, image build, flash or hardware/client acceptance occurred here.
