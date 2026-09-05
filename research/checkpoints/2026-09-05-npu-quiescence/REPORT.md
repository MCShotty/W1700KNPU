# NPU Mailbox Ownership And Firmware Stop Contract

Date: 2026-09-05. Source checkpoint is ahead of Daybreak21 R1. No router access,
configuration change, firmware upload, image flash or hardware test in this pass.
Both project goals remain unfinished. The last router-tested image remains the
WLAN-NPU-compiled-out R1 engineering baseline, not stock parity.

## Implemented Change

Kernel overlay patch `926-net-airoha-npu-protect-inflight-mailbox-buffer.patch`
fixes two independently reproduced transport defects in
`__airoha_npu_send_msg()`:

- Publish payload address, length and command flags before incrementing the
  producer counter. The previous flags-after-counter order permits immediate
  firmware completion to be overwritten, and permits observation of stale flags.
- Preserve ownership of the coherent mailbox buffer after timeout or uncertain
  publication. A later caller returns `-EBUSY` while DONE remains clear, without
  changing the payload or mailbox registers. Observed late completion permits
  reuse. The CPU spinlock alone cannot protect a buffer still used by firmware.

The patch also propagates register-access errors and rejects negative payload
lengths. A completed firmware-error response releases mailbox ownership without
copying a reply. It does not claim STOP or GET means all WLAN DMA has drained.
The `mbox_pending` flag uses existing ARM64 structure padding, and is protected
by the existing per-core lock. Only core 0 is used by the current provider.

`924-net-airoha-use-dma_alloc_coherent-buf.patch` is already in public base
`28ba2708f1f609bfd134975808b2bc6ed9dc9742`. It was not an untracked local change.
Patch 926 builds on that coherent-buffer implementation; it does not replace it.

## Evidence And Validation

- Actual prepared kernel function compiled against adversarial MMIO/firmware
  stubs: **143 assertions pass**. The unpatched function fails both independent
  negative controls: immediate-consumer completion and timeout-buffer retention.
  Busy, late DONE, status/read/write failures, reply bounds, wrap, zero/max/negative
  sizes and lock balance are covered. This is a CPU model, not hardware emulation.
- Real `target/linux/prepare` and `target/linux/compile` exited 0. Kernel 6.18.44
  provider object SHA256 is
  `5b025cfa3ae234909ff4164f42a789b08390248de471cbf803afecad65374a68`.
- Real mt76 package compilation with `CONFIG_MT76_AIROHA_NPU=y` exited 0, followed
  by the ordinary WLAN-NPU-disabled build, also exit 0. Both variants' mt76,
  mt76-connac-lib and mt7996e executable sections match the prior detached-provider
  checkpoint. Original `firmware/build.config` and active `.config` are byte-equal.
- Real ARM64 kernel-context layout probes compile. Before/after values are equal:
  core size 64, provider size 664; core lock/work/buffer/address offsets 8/16/48/56;
  provider irqs/stats/ops offsets 528/552/560. This is layout evidence, not module
  load or lifetime proof. See `abi-layout.json` and `layout-build.log`.
- Full Ghidra auto-analysis: stock kernel **33,676** initialized executable
  functions, **18** selected mailbox/NPU exports; current provider **24** functions,
  **2** selected exports. All selected functions decompile successfully.
- The actual provider assembly confirms pending-byte checks before `memcpy`,
  command publication at import address `001002ac` before counter publication at
  `001002cc`, and timeout/error exits preserving the pending byte. These are Ghidra
  ELF-import addresses, not live kernel addresses. DWARF local-variable expression
  warnings do not imply successful local type recovery; assembly is retained.
- Current-source reconstruction verifies **34 OpenWrt + 3 LuCI** changed files.
  Source lock names the new snapshot and retains R1 as last router-tested.

Kernel/component compilation is not a complete sysupgrade-image build. No active
WLAN-NPU image is approved by these tests. The provider is also shared with
Ethernet offload, so full image and hardware regression gates still apply.

## Stock Host Transport

Stock kernel input SHA256:
`a51e6d0a6deee620a5f715c9469f193906cdf3fcea28b97ce01cf88383aa704e`.

`host_notify_npuMbox` at `ffffffc0100d1cc4` writes payload address `0x30c030`,
length `0x30c034`, command `0x30c03c`, then increments counter `0x30c038`. It polls
DONE bit 1 and status bits 4:2. A per-core lock serializes host callers; timeout
releases that lock. Vendor ordering supports the publication correction but is
not proof that vendor timeout handling is itself safe.

The complete supplied stock inventory covers **134 modules plus the kernel**,
5,680 named undefined imports and 435,395 relocations. There are 37 proven direct
mailbox CALL26 sites: mtk_pci 21, hw_nat 8, npu 4, mt_wifi 2, speedtest 1, tccicmd 1.
`inventory/REPORT.md` and `ghidra_targets.tsv` distinguish direct relocation-backed
calls, function-table correspondence and unresolved indirect dispatch. In
particular, PCI stop/start callback offsets `+0x128/+0x130` correspond to the slots
loaded by `mtk_ge_stop_npu`/`mtk_ge_start_npu`; live binding is not proven here.

## Current Firmware Analysis

Pristine linux-firmware-20260810 MT7996 NPU code:
`e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643`,
122,336 bytes, loaded at `0x84000000`. Initialized data is 3,084 bytes,
SHA256 `61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1`.
Neither firmware file was modified.

Ghidra's code region ends at `0x8401a2e8`; following relative-table/string data
is mapped read-only/non-executable through `0x8401dde0`. Physical data initialization,
cached data alias, NPU ring SRAM and volatile copy-DMA regions are mapped explicitly
by `SetupCurrentNpuMap.java`. Global pointer reset is analyzed from firmware,
not imposed as a universal function context.

The default RISC-V decoder missed opcode `0xfc200073` with mask `0xfff07fff`.
This is a SiFive-compatible `CDISCARD.D.L1` encoding, not a CSR write or NOP.
The separate `RISCV:LE:32:W1700KNPU` language adds explicit opaque cache-operation
pcode. Existing Ghidra languages are unchanged. The encoding identification does
not establish the exact CPU implementation or that cache discard drains DMA.

Primary encoding references: [LLVM instruction definition at pinned commit](https://raw.githubusercontent.com/llvm/llvm-project/207e45fb67ee3dbec9590d9303eebf4f720c8a40/llvm/lib/Target/RISCV/RISCVInstrInfoXSf.td)
and [GNU binutils opcode submission](https://sourceware.org/pipermail/binutils/2021-September/118032.html).

Corrected analysis exports **424/424** discovered initialized executable functions
with zero decompilation failures. This is analyzer coverage, not proof that all
indirect targets or firmware semantics are understood. The earlier
`ghidra-current-rv32/` attempt remains as failure evidence: missing cache-op decode,
one failed decompilation and invalid code/data boundaries. Use only
`ghidra-current-rv32-decoded/` for the current findings.

### Stop Is Not A Whole-Graph Barrier

| Current address | Observed behavior |
| --- | --- |
| `84003cd6` | Mailbox ISR reads command/length, invokes callback, then reports DONE. |
| `8400d7ca` | GET selector 3 returns `(flag_46f7 == 0 || flag_46f6 == 0) | flag_46e8`. |
| `8400e084` | SET selector 4 sets stop byte `46f5`, clears RX/indirect/FastTX/slow/TXDONE enables. Selector 6 resets buffer allocation. Selector 7 rearms several paths but does not restore RX enable `46ec`. |
| `8400c9b0` | RRO MSDU-page worker checks `46ec` only during startup, then loops permanently, consumes three rings and updates `4580/2ac8/4598`. |
| `8400cb0e` | Indirect part-2 worker checks `46f0/46ec` only during startup, then consumes descriptors, updates indices, releases buffer IDs and calls `8400ac30`. |
| `8400fcc8` -> `8400e036` | API27/INODE_STOP_ACTION reaches a not-supported-on-bellwether stub, not a hidden complete stop barrier. |

The worker loops permit ring/buffer mutations after selector-4 ACK and GET3 zero.
Increasing a host delay, masking host interrupts, or checking only existing status
bytes does not make these workers acknowledge quiescence. The mailbox transport
fix is necessary for reliable commands but does not repair that separate protocol.

### Historical Comparison Correction

The comparison blob used in the September 2 stop analysis had SHA256
`51f3583c45b2c356866ee53bd79dac93e10ad069bc75ff516019ea7edb929b79`.
It was our **July V28 patched firmware**, not an independent pristine vendor input.
Its code is 122,580 bytes: eight changed prefix bytes (two four-byte JAL hooks at
offsets `ac30` and `f0f6`) plus a 244-byte append. The hooks target `8401dde0` and
`8401de30`. The current pristine file restores those original prologues.

The ledger's July V28 entries establish origin. STOP/GET and worker-loop findings
are now independently confirmed against current pristine bytes and corrected
decoding. Preserve the September 2 report as history; do not carry forward its
unqualified comparison-file provenance.

## Required Recovery Contract

Do not enable active WLAN NPU until these shared ownership requirements are met:

1. Serialize recovery, stop new submissions/refills, and define ownership across
   all host and NPU producers. Cover L1, full reset, probe unwind and removal.
2. Provide a real all-worker barrier: each participating worker must acknowledge
   the requested generation only after its final descriptor/buffer/DMA action.
   Alternatively prove hardware containment that terminates all independent bus
   masters without corrupting Ethernet/PPE state. Current STOP/GET is insufficient.
3. On timeout or partial restart, retain possibly device-owned memory and keep
   submission disabled. Do not use successful mailbox completion as permission
   to release tokens, reset buffer-ID allocation or free coherent rings.
4. Reject stale-generation completions before IDs or storage can be reused. Prove
   that reset/reinit cannot make an old completion look like a new transaction.
5. Resume only after all required NPU paths and host resources are reinitialized;
   bounded failure handling must be shared by every lifecycle entry point.

Current mt76 L1 discards stop/reinit errors. Full reset releases tokens before
NPU stop. Removal/probe unwind also need an ownership-safe policy. Those remain
unmodified and unresolved, not silently accepted because the transport test passes.
Next: resolve stock SER/reset indirect dispatch and hardware containment, then
implement and verify the shared lifecycle contract with full host-adapter parity.

## Replay

From the canonical WSL repository, with its prepared build and retained inputs:

```sh
python3 tests/npu/test_mailbox_ownership.py
python3 tests/npu/verify_quiescence_evidence.py
python3 tools/migration/verify_source_export.py --output research/checkpoints/2026-09-05-npu-quiescence/source-export-verification.json
```

Ghidra tools: `run_mailbox_kernel.ps1`, `run_current_npu.ps1`, and
`run_mailbox_provider.ps1`. They guard against overwriting existing projects.
`install_npu_language.ps1` installs only the separately named decoder files.
Private build inputs and generated module binaries remain ignored/local;
no credentials, raw device backup, factory/calibration or recovery dump is included.
