# Compiled Cold MCU Cleanup Failure Contract

Base: `2c17d027fa2965674363bdef2a69f2e1a42da4d2`. Continued solo. This adds an
executable failure contract to mainline tests, not a production retention fix,
new compilation, complete Linux teardown or physical DMA retirement.

## Actual Instruction Scope

`tests/npu/test_cold_mcu_native.py` executes these retained AArch64 functions:

- `mt7996_cleanup_device`
- `mt7996_mcu_exit`
- `mt7996_dma_cleanup`
- `mt7996_dma_disable`

Retained producer SHA256:
`a840d3cccb1d0bd8cc60a856d1a1bb9723dfc05af73484d955a33978a458d22f`.
Its mt7996 module SHA256:
`af458b048f32b015e550dc523f3706d00b5a650030e000c0bbf878f4186045bb`.
Current init.c/mcu.c/dma.c and mt76/mt7996 headers match that producer's source
context. This source binding excludes the changed mac.c RXWI function; the
retained module is not relabeled as containing that new fix.

The loader validates ELF identity, selected symbol ranges, complete AArch64
instruction decoding and supported relocations. Selected native direct calls
are linked to their actual target; all other calls have a strict modeled-call
allowlist. Relocated error strings are mapped read-only. Exact compiler memory
operands guard this SHA-bound fixture's explicit structure offsets, not a
universal mt76 ABI or complete DWARF structure recovery.

## Executed Contract

All31 cases and three instruction mutation controls pass. The first private
q4 run is retained; public q6 adds stronger order and trace assertions. Repeated
qualification is not62 unique cases. Scenario totals range from4 to1084 native
instructions, including the idempotent repeat where applicable. Each entry
retains the1M-instruction/5s limit.

The cases vary MCU and queue attachment, HIF2, modeled send results0/-EIO/
-ETIMEDOUT, modeled firmware-state poll success/failure, owned-RRO flags and
already-started cleanup. Eight groups retain exactly equal traces across the
three send results. Actual instructions construct the12-byte power-off request,
use the no-wait command boundary, and invoke the firmware-state poll with
arguments `(0xe00f0, 7, 1, 1000, 10)` after the device argument.

On modeled poll failure, native code emits both error messages and skips
firmware-own writes. It then returns to the actual outer cleanup, which still
invokes CPU-ingress shutdown, final response purge, token retirement and, when
attached, shared DMA cleanup. Actual DMA-disable code performs the checked reset
and disable RMW sequence for the primary HIF and HIF2. Those writes are recorded
by a modeled bus; no physical register was accessed.

Owned-RRO flag cases use empty managed allocation slots. They cover the actual
control branches, not live RRO resource retirement. Token retirement, shared DMA
cleanup, firmware polling, MMIO, work joins, scheduler and other kernel calls
remain explicit models. No physical firmware-state transition, full Linux
cleanup, page-pool destruction or hardware drain is proven by this test.

Three mutations change only the in-emulator instruction copy: invert the poll
branch, replace the DMA-cleanup call with NOP, or replace the firmware-poll call
with NOP. Each fails its exact named assertion. The original module is unchanged.

## Resource And Replay Integrity

Read-only scoped-q4/q6 both succeed under400MiB/no swap, Nice10/CPUWeight10 and
fresh Windows backing/RAM checks with unchanged reserves. Peak memory is159.2MiB.
Protected source/module write opens fail EROFS. New output stays on Ubuntu root;
zero bytes are written to C scratch and its existing writer lock is not displaced.
All438 queued inputs and294 native inputs rehash before/after, with actual
original driver identities and advancing CPU. No compiler or broad suite ran.

The original full-q21 invocation remains
`6c1bc5ff20d74add9235553e70e26931`, guard18906/wrapper18920/driver18942.
Observation-q7 verifies234 advancing driver CPU ticks and retains a finite
complete-line profile0 prefix:3546 positives, OPEN1/ENROLL139/PUBLISH129/
HARDWARE1/RESET1092/MCU_BEGIN1092/MCU_COMPLETE1092. HARDWARE is a modeled protocol
operation, not board access. This is not an atomic guest snapshot, a profile
summary or a complete native verdict. The original job was not restarted.

REA's binary_session call reports Transport closed. No registration repair,
engine launch or upgrade is performed here. The ELF/Capstone inspection is
ordinary local analysis, not REA Evidence or a Ghidra verification claim.
Initial source questions use actual Jev1.13.0: restart-is-drain0.04,
caller-receives-error0.06, failure-retains-tokens0.11 and planned-physical-test0.04.
These semantic judgments are not tests or hardware proof.

## Remaining Work

Use this contract when implementing a complete consumer containment/retention
decision: no-wait enqueue, successful poll, CPU joins and disable writes alone
must not be relabeled as a whole-engine physical drain witness. Preserve every
possibly exposed page, mapping, descriptor, token/metadata and context across
failure and both devres domains until that decision is qualified. This checkpoint
does not implement that owner or prove live-resource retention.

Keep the438 queued/294 native inputs frozen. After the original full recipe is
terminal, inspect its own result independently, then require the queued current
RXWI module/helper and broader regressions. Rerun this new MCU contract against
the fresh producer. BA reuse/hot lifetime, full native/physical ownership,
current image/board/actual-client/performance/stability remain open.

Source lockd55e71a3/mt76 patch5fa42f93/kernel patchaacc0ffc stay. Ethernet remains
disconnected at the user's request. No router contact, image/module load, flash,
Wi-Fi change, shutdown or further compaction occurs. Six previous tracking
bodies are preserved after their new prefixes. The full NPU objective is active.
