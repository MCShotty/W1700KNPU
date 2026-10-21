# Combined Module Receipt To World Build

Date: 2026-10-21. Previous goal turn made progress: checked IRQ implementation,
host fixtures and four unloaded AArch64 module links were pushed as `be36a6e`.
This turn repairs their next image-build integration; the full NPU goal remains
active and incomplete.

## Change

`tools/npu_isolated_world.py run --module-receipt <result.json>` now accepts the
actual combined checked-IRQ producer. It cannot be mixed with either old
separate producer option. The old provider/mt76 pair remains supported.

Admission checks passing/unloaded/current-header scope, source lock, every
declared input and all four module artifacts' bytes, size, AArch64 ELF header
and vermagic. The frozen snapshot must declare the receipt, all its inputs and
all four artifacts. No replacement historical receipts are generated or rewritten.

Before rebuilding, the inner runner validates that producer again. Afterward,
prepared kernel patch files, all locked components and the complete mt76 source
map must match its receipt-bound identities. The original receipt/hash/scope,
input map and source maps are rechecked. A new image is not compared to the old
image hash recorded only as a protected-output observation. Original lower
build/cache and frozen-snapshot postchecks remain in place. No Linux namespace,
clean/build, package/image check, native limit or physical gate is removed.

## Evidence

- `ADAPTER.json`: 15 Windows-portable synthetic contract/CLI/log tests pass,
  zero skips. Eleven new methods cover rejected mixed producers, receipt/input/
  artifact/source drift, undeclared frozen inputs, old-pair behavior and
  postbuild source checks despite legitimate output replacement. Four existing
  portable timeout/nonzero/CLI methods pass. These are not Linux POSIX tests.
- Actual unchanged producer `90abc8f3` re-admits 364 input files, five kernel
  and 329 mt76 source identities, and four retained module artifacts at lock
  `cb035741`. This is rechecking previous module links, not new compilation.
  The stale original prepared provider is correctly rejected; it is not edited.
- `LIVE.json`: same service/process start ticks, systemd cgroup and guard FLOCK;
  both native children have increasing CPU counters. Both prefixes retain six
  TXBUF phases/RX-event passed and DESC10 entered. No terminal caller verdict.
  No pause/restart/kill, native budget/checkpoint change, VM restart or flash.
- Initial Windows test discovery also collected POSIX tests and failed on
  Windows symlink privilege/path conventions; the new fixture had omitted a
  required context field. Its source is retained privately. Corrected fixtures
  use canonical receipt keys and test real missing declarations, not missing
  setup state. No production assertion was relaxed to obtain a pass.

## Execution Limitation

New `wsl.exe` launches as root/captain and the system-distribution entry time out
with `Wsl/Service/0x8007274c`. Ubuntu, filesystem access and the existing native
processes remain live. Debug shell requires Windows elevation and was not entered.
Ghidra MCP reports no running instances. No service/VM restart was attempted.

The new Linux POSIX/namespace path and fresh image are **not run or qualified**.
Windows contract tests and retained artifact checks do not establish them. This
is not a terminal verdict for the original jobs and not full NPU acceptance.

## Next

Recover a normal WSL entry without interrupting the two existing jobs, then run
the complete Linux world/source/combined test suites. Freeze a fresh clean source
snapshot with the real combined receipt and four module files; use the prior
read-only capsule only as verified storage reuse, not stale producer authority.
Re-evaluate the actual backing-drive budget including live native future output
and margin before starting a world build. Then build/inspect the complete image
through the new option and existing FIT/DTB/package/module/source gates.

Both original callers/full fault/setup, hot packet/event/token ownership, RRO
context, DMA/cache/PMA/exclusion, in-flight drain/recovery/retirement, whole-stack,
physical Gemtek boot/radios/MLO/clients/performance/stability remain open. Image
`01fc0ef0` predates checked IRQ. Firmware patches/source-lock/UI/WiFi are unchanged
this turn. No software-adapter result is promoted to a hardware claim.
