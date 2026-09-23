# Linux V2 Control Executor

2026-09-23. Added an unpromoted Linux executor for the existing V2 control
client and provider transport. It serializes complete exchanges, verifies the
caller's intended operation, preserves the first failure, refuses repeated
initialization and joins an active CPU call during close. The implementation
and ownership contract are in `firmware/npu/linux-control.c/.h` and
`firmware/npu/LINUX_CONTROL_CONTRACT.md`.

## Integration Boundary

Source inspection found that consumer attachment does not establish the fresh,
independently contained provider lifetime required by the protocol. The actual
loader still does not supply the V2 boot identity or approved session placement.
Automatically initializing a fresh client on every attachment would violate
that precondition. The new executor retains it as an explicit caller obligation
and is not yet wired into mt76 initialization, legacy setup, stop or recovery.

The provider reference remains caller-owned through close, and the executor
allocation remains caller-owned until every caller retires. Close joins only
this executor's synchronous CPU calls; it does not retire the provider's pending
coherent transaction or any device-visible resources. A successful reply and
PARKED state still provide no cleanup/restart authority.

The portable V1/V2 client and server sources are unchanged. A kernel-only
`stdint.h` include shim supplies actual Linux types for their selected build
objects. It is not a project-wide header replacement.

## Host Evidence

The harness compiles the actual new executor, existing client/server C and the
same extracted provider transport functions used by the earlier provider
checkpoint. Those three provider function hashes match that receipt. Linux
mutexes are represented by pthread mutexes; regmap, coherent storage and device
delivery reuse the explicit provider model. The server is standalone V2, not
the native bootstrap gate or a running NPU.

ASan/UBSan passes 44 cases:

| Cases | Scope |
| --- | --- |
| 1 | Discovery, binding, stop, worker software parking, status and close |
| 4 | Once-only initialization, invalid arguments and uninitialized instances |
| 6 | Wrong operations and repeated BIND without an unintended STOP |
| 20 | Independent corruption of every reply word |
| 11 | Register failures before/after modeled effects, timeout/read failure, late completion and positive transport error |
| 2 | Close waiting for a blocked successful or failed provider call |

The recorded run contains 367 executor assertions and 606 provider-model
assertions. These are execution counts, not whole-goal coverage. The late reply
uses only retained coherent storage after the executor's stack packet has gone.
PARKED is explicitly checked as non-reclaimable without physical drain evidence.

Six compiled mutants fail named assertions: reinitialization, wrong-operation
acceptance, ignored reply rejection, replacing the first error, positive-error
leakage and close without joining the active call. The initial wrong-operation
mutant needed a test-only adjustment to keep its argument referenced under
`-Werror`; no executor correction was needed after the first passing host run.

## Kernel Evidence

Two unloaded AArch64 modules link against the previously rebuilt provider
kernel. Each contains the executor and both real client translation units.
The enabled variant imports `airoha_npu_wlan_control`; the disabled-header
variant does not. The latter uses a forced include to undefine the provider
configuration for these test objects only. It is not a disabled target-kernel
build, and the actual kernel configuration remains unchanged.

Four shared layout values match host and target builds: V1 client size 56,
V2 client size 68, packet size 80 and boot-identity offset 56. This does not
compare pthread and kernel mutex layouts. Both modules retain target vermagic
`6.18.44 SMP mod_unload aarch64` and emit only the known missing-description
warning under `CONFIG_MODULE_STRIPPED=y`.

| Module Profile | SHA256 |
| --- | --- |
| Provider API enabled | `f21fd459b872ba07b3b7be7e1ac1b060fc851dd7a0d82323a2b3a6936e886425` |
| Provider header forced disabled | `c36808bde84a19f50a0ffb69918a8b38bded50acbcba96f000671b6c0ac80860` |

Independent Windows readback verifies all 83 unique recorded input, derived,
binary and log files. Receipt: `linux-control.json`, SHA256
`f49e8df57aa1aef8e41073548cff48145ed245b36ec89bdae1a23c2d08226ff7`.
Existing provider/kernel inputs, source lock, cumulative patch and release
configuration retain their hashes.

## Replay And Remaining Work

With the existing prepared provider kernel, toolchain, pyelftools and project
Python dependencies available, use fresh ignored build/output directories:

```sh
cd /home/captain/W1700KNPU
PYTHONPATH=.local/npu-reset/python-lib:tests/npu \
  python3 tests/npu/test_npu_linux_control.py --build-name replay \
  --output-dir .local/npu-linux-control/replay-evidence
```

The executor must still be anchored to the correct cold provider lifetime and
wired into real mt76 callers with bootstrap ordering. Production loader
identity/placement/publication, provider removal and other users' lifetime,
native postgate firmware execution, IRQ/NAPI shutdown and physical DMA/drain/
recovery remain open. No module load, packaged candidate promotion, firmware
image, router action, Wi-Fi configuration, restricted INODE/DESC operation,
subagent, protected-data upload, flash or commit/push occurred.
