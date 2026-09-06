# Native INODE Contract

Date: 2026-09-06. Status: bounded native evidence passes; provider correction
is **not integrated**. This is not a proved live Wi-Fi failure cause, full
host attachment, strict admission, hardware readiness or stock parity.

## Verified Behavior

- Original callback `0x8400fc2c` performs five unconditional 32-bit loads at
  request offsets `0, 20, 16, 12, 8`. They span 24 bytes for every selector
  `0..15`. The common Wi-Fi dispatcher separately consumes API word1; the
  wrapper itself does not load six words. All 16 entry-only tests stop before
  helper `0x8400e084`, without executing the other selectors' consumers.
- Pinned host attachment previously established 12-byte INODE requests. A
  poisoned 256-byte retained bounce-buffer model reproduces three reads beyond
  that declared request. The actual provider allocates 256 bytes: this evidence
  does **not** establish a physical allocation overrun. A synthetic 24-byte
  zero-padded request keeps all wrapper reads inside its declared extent.
- Native selectors2/7/4 complete after actual core0 bootstrap with only printf
  stubbed during the callback. No allocator, INODE helper or return-value stub
  is used. Six complete calls cover each selector with both old-length poisoned
  tail and synthetic padded input. All 786432 bytes of SRAM/heap/L2 and exact
  write sets match source-derived oracles. The memory results are identical:
  these three selectors ignore the extra arguments. Padding therefore cannot
  be claimed as a demonstrated fix for their live behavior.
- Selector2 clears the native fixed allocation type `0x109` at `0x3e8bc470`:
  1026 words, 4104 bytes. Neighbor guards remain unchanged. Exact instruction
  ordering shows run flags at SRAM offsets `0x46ec`, `0x46f0` and `0x46f8`
  are stored before the first ICV clear. The unavailable-ICV control stops
  without callback return but leaves those flags set. They are not a complete
  initialization witness.
- Selector7 updates six run/control fields; selector4 updates six stop/control
  fields. These are software stores, not evidence of physical worker drain.
  All three callbacks leave mailbox flags untouched when called directly.
- Three declared-extent controls stop at the first `20+4 > 12` read before
  helper execution or RAM writes. Three strict-transport controls reject
  24-byte requests with flags3, no callbacks and unchanged RAM. The installed
  strict IRQ handler, admission policy, native CODE and extension ELF are
  unchanged. Direct legacy callback testing does not expand their permissions.

Counts: 16 callback-entry footprints, six complete native calls, four negative
controls and three strict denials. Evidence is `native-inode.json`; the test
supports byte-for-byte replay with `--check`.

## Interrupted Provider Work

The provider-framing subagent ended with a tool restriction. It was not retried,
rephrased, delegated again or completed through another tool. Its unfinished
patch, test and scratch files were preserved under ignored
`.local/npu-inode/interrupted-provider/`; the patch was removed from the firmware
overlay so that it cannot be included in a later build. No candidate provider
test result, kernel build or native/provider integration is claimed.

The synthetic padded frame in this completed native test is not output from
compiled corrected provider C. Framing correction remains an open item. Earlier
DESC5/6/7/8 restrictions remain untouched. No production firmware/config,
source-lock, cumulative patch, shared harness, router, image or flash change.

## Reproduction And Bindings

From the canonical WSL repository:

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_inode_native_contract.py --check
```

The test requires retained private local binary inputs; they are not included
in this checkpoint. It verifies native CODE/DATA, Ghidra export, compiled ELF
and four bootstrap parent hashes plus the RX closure harness before execution.

- Test SHA256: `69740f2d4ffc7dce894925980911ccfd65b9546c4fb01879fcfad522aa3bc1ff`.
- Receipt SHA256: `2f753a0c13f0d4466435675d5677b6617bed6f52104c76d79296eeb652b9e4d1`.
- Unchanged source-lock SHA256: `46d69e60a43a793796691e2656d4376871274f8b20e637c40c0143fb0bc26c09`.
- Unchanged cumulative OpenWrt patch SHA256: `589481fde3271e88c83bab2cac87e56132f883ad40ac035135dd6423360d0a8d`.

The last router-tested release remains R1 with WLAN NPU compiled out. Full
Wi-Fi root-cause/fix, worker initialization, Linux recovery/removal, physical
loader/cache/containment and client acceptance remain open. This checkpoint
closes only the stated native contract measurements, not either full goal.
