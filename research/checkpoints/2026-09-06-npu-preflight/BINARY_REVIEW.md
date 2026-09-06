# ARM64 Provider Binary Review

Object SHA-256:
`74753cbc9f78ddb94190bb83a5d8a4319acff670a8ccc4ac9f9988457520c40d`.
Full Ghidra AARCH64 analysis exported 24/24 executable functions with no failed
decompilation. Addresses below are ELF-import addresses, not live addresses.

## Memory Initialization

`airoha_npu_wlan_init_memory` starts at `001011e0`.

- `0010120c` reads cached binary start at private offset `0x298`; checks through
  `00101294` reject missing, inverted, unaligned and high-bit binary endpoints.
- `001012c8` calls the named resource lookup. `001012cc` returns its failure;
  the sequence through `001012f0` rejects invalid resource endpoints before
  reaching the firmware aperture and overlap checks.
- `00101354` loads the cached MT7996 minimum at private offset `0x2d8`.
  The `001014b0` branch requires start above `0x7fffffff` and end no greater than
  `0xbfffffff`. `0010135c`/`00101488` check the cached binary interval;
  `00101378` through `001013d8` check preceding WLAN intervals.
- `001013e8` repeats resource validation until all applicable entries resolve.
  `001013ec` through `001013fc` compute inclusive TX-check size and branch to
  the error return if below the cached minimum. The first WLAN send is only at
  `00101418`, with cmd `0x12` (18), ifindex 1 and a four-byte zero.
- `00101428` loads addresses from the validated stack snapshot. The loop at
  `0010144c` sends cmd32/8/23/optional7, with immediate error exits. `00101474`
  explicitly restores zero before final cmd12 at `00101478`.

## Probe And ABI

- `airoha_npu_probe` starts at `00100c64`; allocation at `00100ca0` requests
  `0x2e0` (736) bytes. The independent ARM64 kernel layout probe confirms the
  unchanged 664-byte public prefix, followed by a 64-byte resource and private
  minimum at offset 728. All nine recorded public sizes/offsets are unchanged.
- Firmware-run checks are inlined into probe. Range checks precede capacity
  arithmetic at `00101054`; `00101064` rejects sizes no greater than `0x23ffff`.
  Cached endpoints/minimum are stored before `devm_ioremap_resource` at
  `0010107c`. Both selected-name branches store `0xe000` only for the MT7996
  name, at `001010c4` and `00101150` respectively, before loading that code.

This agrees with the compiled-C tests and original source, but is not execution
of the kernel on a router or proof of bus/cache/drain behavior.

## Tool Limits

The signed-script policy rejected launching the new PowerShell script from UNC.
The same native headless CLI and explicit arguments were invoked directly;
no execution-policy setting was changed. The recorded script preserves those
arguments and the expected-object-hash guard.

Ghidra logged an existing malformed GUI tool-configuration XML and unsupported
DWARF local-variable register expressions. Neither stopped ELF analysis,
instruction export or any of the 24 decompilations. Decompiled local-variable
types/pointer spelling are not treated as authoritative; the review above uses
instruction operations, the actual C and compiled layout offsets together.
