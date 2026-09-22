# NPU Host Callback And Reference Lifetime

Date: 2026-09-16. Two unpromoted CPU-lifetime candidates; no image or router
change. These are not a complete safe-removal or recovery implementation.

## Source Findings

The pinned provider requests each watchdog IRQ before initializing that core's
work item. An enabled watchdog delivered during registration can reach
`schedule_work()` before `INIT_WORK()`. On normal removal, explicit work
cancellation runs while the managed IRQs remain registered; another IRQ can
queue work afterward. Failed probe does not call that removal callback at all.

The pinned `mt76_npu_deinit()` clears and immediately releases each provider
reference, with no function-local grace period for existing RCU readers. It
also drops those references before its own queue cleanup. The new tests retain
old reader snapshots and model last-reference release to expose these ordering
gaps. This is not a claim of a reproduced live-device UAF or a complete audit
of every higher-level caller's earlier synchronization.

`mt76_free_device()` is the current caller. Normal MT7996 unregister releases
tokens and performs DMA cleanup before reaching it. This checkpoint does not
protect those earlier releases or prove that the caller's queue/device objects
remain valid throughout every unregister or failed-probe path.

## Candidates

`929-net-airoha-npu-irq-work-lifetime.patch` composes after candidate 928:

- Initialize every core's parent pointer, lock and watchdog work before any
  provider IRQ registration.
- Use the kernel's existing `devm_work_autocancel()` helper, with cleanup actions
  registered before IRQ resources. Reverse devres release therefore frees and
  synchronizes the nine provider IRQ actions before canceling watchdog work,
  while provider storage and regmap are still alive.
- Remove the incomplete manual removal callback. Managed cancellation now also
  covers probe errors. Failure to register a work action occurs before IRQ
  publication, so that initialized-but-unregistered work cannot be queued.

The kernel helper and devres/IRQ source were inspected and fingerprinted:
`include/linux/devm-helpers.h`, `drivers/base/devres.c`,
`kernel/irq/devres.c`, and `kernel/irq/manage.c`. No shared IRQ line is disabled
globally. Coherent buffers still have their original managed ownership; this
patch does not stop device DMA or make pending mailbox buffers safe to free.

`007-mt76-npu-rcu-reader-lifetime.patch`:

- Unpublish both NPU and PPE pointers under the existing device mutex.
- Wait for an RCU grace period when either reference exists.
- Retain those references through the caller's two queue-cleanup calls, then
  release them. Empty/repeated detach does not repeat reference drops.

This does not make queue cleanup physically safe. Both patches remain in this
checkpoint, outside the source lock, cumulative patches and firmware overlay.

## Verification

The runner extracts the actual provider probe, mailbox/watchdog handlers and
watchdog worker, plus the actual kernel work helpers. The mt76 test executes the
actual before/after detach function. Framework operations are explicit models;
firmware loading, unrelated provider operations and hardware are not executed.

- Provider baseline: 161 modeled cases. The principal control records eight
  attempts to queue uninitialized work, eight outstanding work items at private
  release, and modeled accesses after lifetime end.
- Corrected provider: 193 cases, with zero lifetime violations. Every one of
  the 46 modeled fallible probe steps is rejected in each of four delivery
  profiles. Profiles cover pending work, immediate execution and a modeled
  already-running worker completed by synchronous cancellation, plus disabled
  watchdog controls. IRQs can arrive during registration and devres cleanup.
- RCU: 24 schedules per version, covering neither/either/both providers,
  one/two/eight retained readers and forward/reverse release order. Pthreads
  delay the old readers while the actual detach function executes. The corrected
  function waits, new pointer observations are NULL, cleanup retains references,
  and repeated detach does not double-put. This is an RCU model, not kernel RCU.
- ASan/UBSan pass the nominal and baseline harnesses. Deliberate dangling-access
  controls retain fixture backing and record lifetime violations rather than
  executing an actual use-after-free. Sanitizers do not certify hardware races.
- Four compiled mutants fail their named oracles: missing managed cancellation,
  missing grace period, NPU put before grace, and NPU put before queue cleanup.
- Twelve actual AArch64 kernel objects pass: provider before/after plus public
  header probes with NPU in/out; mt76 caller objects with NPU in/out and enabled
  `npu.o` before/after. Public provider layout is unchanged. Relocations confirm
  the added `synchronize_rcu` call inside `mt76_npu_deinit`, not merely elsewhere
  in the same object. No linked module or loaded-kernel test is claimed.
- Both patches pass strict checkpatch with zero errors, warnings or checks.
  Final kernel builds have no warnings/errors. Native Clang is 21.1.8 and the
  AArch64 OpenWrt compiler is GCC 14.4.0.

Independent readback verified 42 input fingerprints, 40 derived source/include
files, eight sanitized executables, 12 kernel objects, both patches and six
build logs. Thread wakeup/assertion totals can vary by scheduling; no
byte-identical full-replay claim is made. The final receipt is:

`host-lifetime.json`, SHA256
`685a40fffe2f6e690784ae503b9a5b68717912dd5fc8730aa6b65d86d390e45f`.

Patch SHA256 values:

- Provider 929: `876a8e547d370ae73afcdbc67a659c509ad7ed456df39e3cfe2c2cb81663e51b`.
- mt76 007: `e7cf9585cbf558762b1119b78db86068c68dbe1f170779ca7929a1c3f2a8d555`.

Preliminary harness fixes corrected a C-library name collision, one patch
alignment check and a mutation replacement that needed function-local scope.
A transient UNC timeout was rechecked through WSL before the edit was retried.
The final full run completed after those corrections.

## Remaining Gates

The RCU tests deliberately keep an independent DMA actor alive through cleanup
in both versions. A grace period, IRQ teardown or work cancellation is not a
drain witness. Earlier token/ring releases, consumer IRQ/NAPI lifetime, complete
probe/unregister/full-reset ordering, provider removal under live traffic,
mailbox DMA containment and safe restart still require closure.

V2 client integration and identity publication, postgate NPU boot, production
memory/cache/PLIC contracts and real physical drains remain open. No reclaim or
restart capability is added. There is no firmware/RV32 callback execution,
restricted INODE/DESC retry, physical test, Wi-Fi configuration, subagent,
deployment, commit/push or protected-data change in this checkpoint.

## Replay

```sh
cd /home/captain/W1700KNPU
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_npu_host_lifetime.py
```

`--skip-kernel` writes a separate `host-lifetime-models.json`; it does not replace
the full kernel-validated receipt. Builds remain in `.local/npu-host-lifetime`.
