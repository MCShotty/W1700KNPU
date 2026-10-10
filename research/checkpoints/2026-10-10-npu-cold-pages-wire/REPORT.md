# Session-Bound PCI BAR And Cold Page Prefix

Date: 2026-10-10. Canonical WSL workspace, mainline experimental source. This
checkpoint advances the full NPU reverse-engineering/implementation objective;
it does not complete that objective or establish stock parity. No router
contact, physical reset, hardware write or flash occurred.

## Implementation

The current mt7996 PCI caller supplies `pci_resource_start(pdev, 0)` and
`pci_resource_len(pdev, 0)` to `mt76_npu_init`. After the existing initial held
session, the checked provider binds the window before mt76 publishes either
NPU/PPE RCU pointer or changes its DMA device. Unmarked profiles return success
without these new wire effects, retaining their previous raw dispatch.

Checked type2 requires nonzero4KiB-aligned base/length,32-bit representation,
the complete page-register span and an end no higher than0xc0000000. Both host
and native reject overlaps with all six bootstrap regions. These are geometry
contracts, not actual PCI reservation/exclusion or physical DMA grants.

Two NCS2 commands use internal header0x1f/API0x100 and0x101 to bind start and
length. They never invoke native selector15's legacy multi-register write.
They reuse the existing provider identity/nonce/V2 sequence; no new session or
reattachment nonce exists. One provider mutex covers both commands and CPU close.
Transport/protocol error is sticky and closes the CPU client, not DMA resources.

The native cold owner grows from48 to64 bytes; appended fields store the window
and its completion snapshot. Valid completed prefixes are0,8,24,25,27,31,63,127,
255,511,1023,2047. Binding precedes port/RX0/RX2; each page address precedes its
DESC. GET-version remains repeatable. Completion rechecks window, command,
identity/nonce/sequence/history and held state before returning the software
callback lease. Failure retains active/inflight and any committed claims.

Current host page offsets are BAR0+0xd45a0,0xd45b0,0xd45c0; DESC capacities are
256,512,1024. Actual current sender C and register macros emit these values;
current DMA configuration is source-checked to WFDMA0 for all three page bands.
The native address callback stores the original three SRAM pointers. First
authenticated DESC5 initializes the BA owner from the pinned plan, without a
test-written active lease or direct test initializer. Packet state is unchanged
by page allocation. No owner retirement/recycle/reset API was introduced.

## Verification

- Actual provider C545 cases/nine initial-session mutants:208 BAR geometry/type
  cases,16 metadata transport faults and40 additional reply corruptions. Invalid
  geometry has no wire effects; repeated enrollment and protocol failures retain
  the first error. Six additional BAR binding mutants are rejected.
- Cold server/codec/Linux executor C397 cases/eleven mutants, including112
  geometry and54 order/offset/duplicate/unsupported controls,20 request/reply
  fields,128 bad lengths,38 held-state,14 late-state and8 transport controls.
  Address/undefined/leak sanitizers are enabled on the host runs.
- Three actual mt76-C publication-order cases check nominal, reserved-session
  failure and endpoint-binding failure. Kernel references/RCU remain modeled.
- Actual current txrx sender C calls the provider's actual wrapper/client into
  raw RV32 firmware using actual-C-published CODE/DATA. The full RX/page prefix
  retains2,560 packet and1,792 BA claims, with exact descriptor bytes/ready flags
  and unchanged packet state during pages. Twelve native lease pairs come from
  firmware instructions. The actual sender next receives denial at selector8.
- Four native cases pass: nominal, wrong loader identity before setup, packet
  fault after one committed claim, and BA fault after its first committed claim.
  The BA fault retains that claim,2,560 packet claims, completed-prefix63 and
  active/inflight1, with readiness withheld. CPU close makes no new transport.
- The separate full raw regression retains3,072 PKT/1,792 BA claims and passes
  six boot/eight TXDONE controls. Its later/full-ring direct lease is explicitly
  modeled and does not close the still-missing full strict host setup path.
- Parser/publication60/eight, boot248/ten, lease13/four, probe269/three and
  request310/nine cases/mutants pass. Memory273/159, three original controls,
  nine memory mutants, retry6,174 and V2 44 cases pass.
- Sixteen assembly groups pass with no skips; independent raw builds and the
  world-packaged raw pair have identical CODE/DATA. Sixty-six top-level source
  files reconstruct, plus12 actual nested kernel/mt76 files and13 canonical
  provider components match their prepared compiled source.
- Full world exits0. Actual FIT model/compatible/layout,218 package and78 module
  ABI checks pass. Ghidra full analysis of the exact packaged provider exports
  all54 executable functions, with zero failed decompilations or analysis timeout.

The first world attempt found a private/public inline function-name collision;
the private implementation was renamed and the corrected world passes. The
first native run was deliberately interrupted to freeze corrected inputs; it is
not a successful receipt. A boot receipt racing tree re-preparation and a probe
receipt missing an immutable helper were discarded and rerun. Raw artifacts,
tests and firmware documents were frozen before the final recorded replays.

Strict checkpatch reports zero errors/warnings and three continuation-alignment
checks, which remain style debt. The world log has upstream/package warnings
and the previously seen ignored U-Boot install error; this is not a warning-free
build. The complete FIT and required firmware/modules were separately verified.

## Semantic Review

Actual Jev1.13.0 design judgments classify the BAR as a geometry anchor and the
full goal as incomplete (Choice confidence1.0); selector15 scope/private init/
retention Nouls are0.89/0.91/0.93. A seven-claim source/receipt batch returns six
supported labels, but the window claim is not-established0.51 and several labels
have low confidence. A focused five-claim follow-up adds previously omitted
header definitions and metadata frames: window/order support probabilities are
0.83/0.62, while metadata/init/retention are not-established0.55/0.49/0.55.
All distributions, latency and usage are preserved; this is not unanimous
semantic verification or proof of correctness.

Codex reviewed the material uncertainties against exact code and receipts. Both
metadata frames have no legacy callback entries; the adapter's metadata branch
sets slot0 and cannot call the legacy callback. Header definitions plus C geometry,
order/offset/replay mutants exercise the guarded window/prefix. Native owner
storage starts zero and actual instructions acquire each observed lease/init;
the recorded test lane supplies no active or direct ownership-init writes. The
late BA fault retains claims/lease, and CPU-close source performs no transport or
native resource release. Those deterministic/model-scoped checks, not Jev labels,
support the claims above. Physical containment and complete acceptance remain open.

## Artifacts

- FIT26,960,714 bytes:
  `5c94b20d3dbcf37fafa4b2bce129671933cff4d61a582c636223061b69cfb43e`.
- Packaged provider:
  `f581c5036e357db2dff4e5060ac0bff8ede1eb2f5fa37c6a06337ad5baba63de`.
- CODE529,528 bytes:
  `313e08130c5a6df5aaa0ac6f3e90b8d5598e4f8fab9ee310c7d64c408a1ee93e`.
- DATA25,728 bytes:
  `481827ab57cd46eb499cd06c1ec91ba6d11e3127b4e53160c288133a15a36014`.
- Thirteen-object core archive:
  `b319f9a256e8872db7a85436ef3cde1008a5acf7bd5755e37f60463d2a3166a4`.
- Source lock:
  `a6199ffc0b07400af26519e38e240c2ec1a7f0f5e7e8ed24fe00480cc881dfa7`.

The previous complete FIT `7622acf9...` is preserved in ignored
`.local/npu-cold-pages-wire-20261010/pre-world-image/`. Earlier/R1 images,
calibration/bootloader/private backups remain protected. No image is flashed.

## Remaining Scope

The actual txrx sender still stops at unsupported indication selector8. Implement
its owner/address/DESC contract, then INODE/TXDONE and remaining strict setup.
The separate full raw regression uses a modeled direct lease for the later
TXDONE/rings; it is not proof of that still-missing host lane.

Backing, mailbox delivery, host pointer publication, queue state, IRQ grants and
worker scheduling in native replay are modeled. Independently establish actual
prior-user exclusion, exclusive backing/cache/DMA coherency and engine coverage.
Complete other owners/workers/hot/postgate, physical drains/retirement/teardown/
rearm/recovery, exact-image boot and actual clients. A software lease, BAR bound,
parked snapshot or retained claim never authorizes physical resource release.

## Reproduction

Use fresh names under ignored storage and immutable source/header copies while
world replaces its prepared trees. From canonical WSL, with the installed local
Unicorn/ELF Python dependencies:

```sh
export PYTHONPATH=.local/npu-reset/python-lib:tests/npu
provider=.local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c
header=.local/merge-nonoc-20260923/kernel-merged/include/linux/soc/airoha/airoha_offload.h
python3 tests/npu/test_cold_host_prefix.py --mt76 .local/merge-nonoc-20260923/mt76-merged --name fresh-pages-host
python3 tests/npu/test_endpoint_binding.py --source "$provider" --name fresh-pages-binding
python3 tests/npu/test_cold_wire.py --source "$provider" --name fresh-pages-wire
python3 tools/build_npu_pair.py --output .local/npu-fresh-pages-pair --firmware-directory .build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-firmware-20260910/airoha
python3 tests/npu/test_checked_loader.py --source "$provider" --pair .local/npu-fresh-pages-pair --name fresh-pages-publish
python3 tests/npu/test_provider_session.py --source "$provider" --header "$header" --pair .local/npu-fresh-pages-pair --publication .local/npu-loader-publish-20261010/fresh-pages-publish/nominal --host-sender-receipt .local/npu-cold-pages-wire-20261010/fresh-pages-host/result.json --cold-commands --name fresh-pages-native
python3 tools/build_firmware.py --name fresh-pages-world --jobs 8
python3 tools/verify_merged_image.py --name fresh-pages-offline
```
