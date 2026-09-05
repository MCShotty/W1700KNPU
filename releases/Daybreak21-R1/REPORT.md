# W1700K Daybreak21 Engineering Image

**Flashed engineering baseline with synthetic runtime checks passed. WLAN NPU is compiled
out; Ethernet offload is unchanged. This is not the legacy numeric mode 0 API
or a completed stock-NPU port.**

Image: `openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb`

SHA256: `0788f405337ceb030d873463bbf278497dcd9b86e8f75a1a3f57fd318eda195f`

Size: 20439877 bytes. Board: `Gemtek W1700K (OpenWrt U-Boot layout)`.
Kernel: 6.18.44. Layout/compatible: `gemtek,w1700k-ubi`.

## Changes

- Corrected MLO radio ownership, index validation, scan-join width/hidden-SSID
  validation, TKIP rejection, and truthful radio reporting in LuCI/backend.
- Added MLD MAC collision checks and complete raw MLO setup snapshot validation.
- Added an explicit WLAN NPU build gate and read-only compiled-support reporting.
  Current upstream recovery ignores NPU stop/reinitialization failures; this
  baseline excludes that WLAN path. The active-NPU recovery defect is not fixed
  by these exclusions and remains a separate implementation task.
- Includes full wpad, LuCI HTTPS, matching SQM packages/kmods, adblock integration,
  and the SoftEther server UI. SoftEther defaults disabled for baseline tests.
- No transmit-power or regulatory database modifications. No bootloader,
  chainloader, factory/calibration image, private key, or router backup included.

## Verification

165 LuCI, 43 generator, 38 MAC/allocator, and 535 shell assertions passed.
Both driver variants compiled. Full Ghidra auto-analysis completed for all six
ELFs; 27 selected defined functions in the upstream comparison and 8 in this
baseline decompiled successfully. External symbols are excluded from those
counts; DWARF/tool-layout warnings are retained in workspace logs.

The full image build passed. FIT hashes, DT model, supported-device metadata,
rootfs/package contents, official firmware bytes, and executable sections of
packaged modules were verified against the audited artifacts. See VERIFICATION
and BINARY-VERIFICATION. These checks are not client association, throughput,
fault-injection, stock parity, or production-reliability certification.

## Runtime Acceptance

Flashed on 2026-09-05 over pinned Ethernet SSH after backup and router-side
`sysupgrade -T`. Normal config-preserving upgrade was used, without force,
wipe, raw NAND erase, bootloader, or chainloader operations. Exact running FIT
and driver hashes match; factory and wireless configuration hashes are unchanged.
Standalone APs, two/three-link MLO, scan API calls, invalid-config rejection,
teardown and restoration passed. These are synthetic configuration tests, not
real-client association, throughput, long-term reliability, or stock-NPU parity
certification. See LIVE-REPORT.md and LIVE-VERIFICATION.json.

Source changes are based on local OpenWrt `f3173f41940ab15d63a205f6d618e145d49ee58a` and LuCI
`83073becd3e0e217a7e55f04ad71b32cfefaf26c`. SOURCE-PINS, source-overlay, and the separate tracked diffs
describe this build; do not apply overlapping historical patch series.

## R1 Runtime Corrections

The first image booted and its factory/configuration/driver hashes matched.
Standalone 2.4/5/6 GHz APs and two/three-link MLO passed synthetic creation,
channel/radio checks and teardown; five invalid configurations were rejected.
The original wireless configuration was restored byte-for-byte. This was not
real-client association or throughput testing.

Live testing found the NPU JSON helper inherited nounset into jshn, whose
dynamic variables assume unset values are allowed. R1 scopes serialization to
a subshell with nounset disabled. A real-jshn clean-environment regression fails
on the old helper and passes on the fix; the corrected JSON was also verified
on the router. R1 additionally detects the built-in Ethernet provider's actual
airoha_eth sysfs name. No kernel code changed for these helper corrections.

CPU frequency readback remains unavailable: current firmware/SMC-backed reads
report zero and cpufreq policies do not register. Hardware frequency is unknown,
not zero. No assumed frequency, governor, voltage or clock-register write was
introduced to mask this. Full stock-NPU parity remains unfinished.
