# Provider Memory Preflight

Date: 2026-09-06. Source patch 927 is packaged and kernel/binary verification
passes. No new release image, router contact, configuration change or flash.
The last router-tested release remains R1 with WLAN NPU compiled out, not parity.

## Implemented

- The provider resolves and snapshots every applicable WLAN reserved region
  before cmd18, cmd32 or any other WLAN initialization command. Invalid regions
  return without publishing even the first WLAN command.
- Reject zero, inverted, unaligned and above-32-bit addresses, overlapping WLAN
  regions and overlap with the binary reservation used to load this provider.
  The selected MT7996 profile additionally requires its firmware DRAM aperture
  and the full 56 KiB TX-check table proved by the preceding native boot test.
- Cache the loaded profile and original binary range in provider-private
  allocation storage. The public consumer structure and successful wire order
  are unchanged; optional BA and generic-firmware behavior are retained.
- Validate the binary reservation before mapping or firmware copying: the
  2 MiB code capacity plus the 256 KiB backup published by probe must fit.

Canonical patch:
`firmware/overlay/openwrt/target/linux/airoha/patches-6.18/927-net-airoha-npu-validate-memory-before-wlan.patch`

Patch SHA-256: `608ce7728255d281714f982387f78bc9c1226e86e684c696b91a7f6500452708`.
Prepared provider SHA-256: `8eed02dd963c9d80fcaf4f15368506f4a4720dd7be4f080c394a21bba7e1fe8f`.

## Verification

- 109 compiled-C cases execute the actual provider function bodies with stubbed
  OF, mapping, load and mailbox boundaries. They cover load/profile selection,
  all required lookups, bounds/overlaps, adjacency, loaded-state caching,
  address snapshots, and every message-position failure. Six compiling mutants
  fail the suite. This is component execution, not kernel/device runtime.
- Eight compiled-DTB fixtures are resolved through the NPU node's named memory
  phandles. The actual C accepts all three corrected MT7996 profiles and both
  generic controls, and rejects all three short-table predecessors before sends.
- The actual preimage accepts the short TX table, sends four messages before
  discovering a missing BA region, and maps/loads an undersized binary region.
  Valid before/after six-message sequences are identical.
- The unchanged mailbox function passes 143 actual-C assertions and its two
  original failure controls. Source reconstruction verifies 36 OpenWrt and
  three LuCI changed files. Checkpatch reports zero errors, warnings or checks.
- Independent bounded review found no actionable regression. Its recorded
  candidate hash precedes a whitespace-only alignment correction; the final
  source differs only by those two indentation columns from the reviewed source.

- Real kernel preparation and full compilation exited 0, with exact source
  reconstruction and no compiler warnings. ARM64 kernel-context layout probes
  preserve all nine public sizes/offsets: 664-byte public object, 736-byte private
  allocation, public prefix at zero and cached minimum at offset 728.
- Final-object Ghidra exports all 24 executable functions without failed
  decompilation. Instruction review confirms validation precedes the first send,
  snapshot-based publication, capacity-before-map and private profile stores.
  See `BINARY_REVIEW.md` for addresses and explicit tool/DWARF limitations.
- `verify_preflight_evidence.py` binds source, patch, tests, object, public header,
  build exits, Ghidra identity and reconstruction results; all checks pass.
- Staged Gitleaks scan found no secrets. Source/document/test whitespace checks
  pass; raw logs, Ghidra exports and patch-context whitespace are preserved as
  evidence and checked separately from authored-source formatting.

Provider object SHA-256:
`74753cbc9f78ddb94190bb83a5d8a4319acff670a8ccc4ac9f9988457520c40d`.

## Limits And Remaining Work

This is startup layout preflight, not a complete bootstrap or recovery protocol.
Probe has already booted cores before exposing the provider. Rejecting a layout
means zero WLAN initialization messages, not zero earlier NPU activity. A later
send failure can leave a partial accepted sequence; no rollback/drain is added.

Firmware identity remains the trusted selected filename, not cryptographic blob
authentication. Renamed/replaced or unknown firmware requires a separate memory
contract. Only TX-check has a profile-specific capacity check here; packet,
TX-packet and BA access footprints, SRAM capacity and binary linked placement
are not newly proved. The prior optional-BA malformed-tail behavior is retained.
No live-DT-overlay, installed-RAM, exclusive-ownership or cache proof is claimed.

Contained barrier initialization, complete startup/host-adapter negotiation,
physical DMA drain/cache witnesses, Linux L1/full-reset/removal retention and
validated restart remain open. Full TX/RX/TXFREE/RRO/PPE ownership integration,
an accepted active-NPU image, and real-client Wi-Fi acceptance remain unfinished.
See `docs/REMAINING_WORK.md`; this patch does not narrow either project goal.

## Replay

From the canonical WSL repository after preparing the source:

```sh
python3 tests/npu/preflight_dtb_cases.py --check
python3 tests/npu/test_memory_preflight.py
python3 tests/npu/build_preflight_layout.py
python3 tools/migration/verify_source_export.py --output research/checkpoints/2026-09-06-npu-preflight/source-export-verification.json
python3 tests/npu/verify_preflight_evidence.py
```

The DTB generator uses the retained baseline/candidate outputs of
`tests/npu/test_txbuf_dtbs.py`. The C test reconstructs its preimage by reversing
patch 927, not by substituting a separately handwritten implementation.
