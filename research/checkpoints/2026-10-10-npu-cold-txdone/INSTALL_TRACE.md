# Real Firmware Installation Boundary

This is current source/compiled-layout evidence, not an installation or physical
reservation certificate. Exact input hashes and section ranges are in
`install-trace.json`. The full NPU objective still requires the implementation
and validation described below, not merely these range calculations.

## Current Path

- `tools/build_firmware.py` builds `firmware/npu/Makefile` into the normal RV32
  archive, then invokes the OpenWrt world target. The component Makefile has no
  CODE/DATA binary-image target.
- The prepared `package/firmware/linux-firmware/airoha.mk` MT7996 package copies
  upstream `en7581_MT7996_npu_rv32.bin` and `en7581_MT7996_npu_data.bin` directly
  into `/lib/firmware/airoha`. It does not link or install the component archive.
- The actual prepared Linux 6.18.52 `airoha_npu.c` validates both objects before
  either copy. `airoha_npu_load_firmware()` copies CODE to the reserved binary
  resource and DATA to `base + REG_NPU_LOCAL_SRAM` (offset zero).
- CODE is limited to `0x200000` bytes, DATA to `0x10000`; the binary resource must
  also cover a `0x40000`-byte SRAM-backup reservation after the CODE area.
- `airoha_npu_probe()` allocates coherent mailbox buffers, loads the pair,
  publishes backup MIB registers, writes all eight boot bases, then writes
  boot configuration `0xff` and trigger `1`. This path does not publish the
  revised binding's boot identity/session input. Probe freshness is not a
  certificate that every previous NPU/DMA user is independently contained.

The verified W1700K DTB maps the NPU register/SRAM resource at `0x1e900000`
with size `0x313000` and selects the MT7996 pair. The native test uses SRAM view
`0x3e900000`. This address correspondence does not approve new storage use or
establish cache/IRQ/DMA behavior on the device.

## Measured Candidate Layout

The current RX/TXDONE-capable smoke composition's allocated CODE sections end
at offset 529,336 from `0x84000000`, within the provider's two-MiB image limit.
Some sections are writable or NOBITS; a raw-image builder must deliberately
encode their initialization, rather than concatenate ELF files or omit BSS.
Overlap checks also preserve native stacks, command ring, backup and state areas.

The model places the 20-byte V2 session at `0x3e906380` and its eight-byte loader
identity at `0x3e9063a0`, SRAM offsets `0x6380` and `0x63a0`. The original DATA
image is only 3,084 bytes and does not reach either location. The original CODE
image is 122,336 bytes. Current packaged hashes remain the original vendor pair;
compilation of a separate archive has not changed that fact.

## Required Implementation

1. Produce a deterministic paired CODE/DATA artifact from checked source,
   original-byte identities, linked sections, relocations and all reviewed
   detours. Reject overlap, truncated displaced instructions, stale imports,
   missing initialization and wrong-profile inputs. Replay the resulting raw
   pair through the native reset/setup paths, not just separate loaded ELFs.
2. Establish the real cold-provider/previous-user containment contract and
   reserve the actual code, state, session, ring and mailbox storage. Numeric
   aperture/extent checks alone do not establish any of those ownership facts.
3. Publish a fresh nonzero boot identity, initialized session/plan storage and
   actual request-buffer identity coherently before releasing any hart. Use
   the real provider lifetime and buffers, not the test constructor's identity
   or fixed request address. Preserve both-image preflight and failure retention.
4. Wire the Linux executor and complete DISCOVER/setup/BIND, remaining cold
   owners/callbacks and postgate consumers. The current strict lane still denies
   later setup; do not install a partly wired image and call it complete NPU boot.
5. Implement the hot packet/token lifecycle and real engine drains, teardown,
   recovery/rearm, then perform separately authorized physical and client tests.
   Keep synthetic storage/grants distinct from device evidence throughout.

The current work implements shared selected RX/TXDONE ownership in native
instruction composition and identifies this concrete installation boundary.
It does not silently promote emulator reservations or claim physical acceptance.
