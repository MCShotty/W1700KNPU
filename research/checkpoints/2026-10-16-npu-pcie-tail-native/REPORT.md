# Native PCIe Tail Binding

## Status

Implemented in the canonical checkout; fresh actual allocator/caller and
full512/fault qualification are pending. Fresh caller `pcie-tail-native-q2`
is live with consumed inputs frozen. The older successful native seal applies only to its preserved
producing inputs, not this changed pair.

## Implementation

- Nine original PCIe0/2/15 stores are guarded by a retained 256-byte owner,
  bounded source readers, actual lock18 and masked IRQ, exact effects/readback,
  held SETUP404 and unchanged neighbors/prior owners.
- Explicit tail successors preserve completed descriptor, TX-buffer, RX-event,
  DESC10 and RX PCIe checks without forging an earlier request. The callback
  chains to the linked RX PCIe predecessor for non-tail commands.
- The actual provider checks its retained allocation/session/endpoint/TX2/HIF
  lifetime before and after tail exchanges. The actual MT7996 sender and legacy
  envelope wrapper are extracted rather than replacing INODE framing with a
  hand-authored short frame.
- A read-only observer projects exact nine-store/lock/private/protected-memory
  effects. Modeled BAR pages and synthetic fixture records are not physical
  DMA backing, device exclusion, reclamation or hardware evidence.

## Passing Scoped Checks

| Scope | Local receipt | Result |
| --- | --- | --- |
| Portable owner/current stage | `.local/npu-pcie-tail-owner/native-binding-q2/result.json` | Host and normal-Os RV32 467 calls/379 controls, both HIF |
| Portable mutants | `.local/npu-pcie-tail-owner/native-binding-mutants-q1/result.json` | Nine compiled mutants killed; sanitizers |
| Completed packet guard | `.local/npu-desc10-packet-plan/pcie-tail-native-q1/result.json` | 32 host/RV32 cases; dependency stubs |
| Dispatcher | `.local/npu-cold-native-dispatch/tail-bound-q1/result.json` | 52 RV32 cases/three mutants; dependency stubs |
| Provider lifetime | `.local/npu-pcie-tail-provider/native-binding-q1/result.json` | 84 cases/five mutants; synthetic retained records |
| Existing provider | `.local/npu-provider-session-20261010/pcie-tail-routing-q1/result.json` | 609 cases/nine mutants |
| Actual sender framing | `.local/npu-cold-pages-wire-20261010/pcie-tail-sender-q2/result.json` | 12 tail/error cases, both HIF |
| Intermediate raw image | `.local/npu-pcie-tail-native-20261016/bound-pair-q1` | 19 components/156 hooks/all19 groups, not final qualification |
| Unleased raw callbacks | `.local/npu-pcie-tail-unleased/bound-q1/result.json` | 18 denied cases; no seeded completed history |

Five synthetic trace units cover both HIF profiles, all stages, malformed
frames, store/lock/private/protected-memory violations and hook cleanup. A saved
trace is not a pass unless independent validation succeeds.

## Qualification Attempts

`pcie-tail-native-q1` stopped before native execution: the newly extracted
kernel legacy wrapper has three signedness warnings under the host fixture's
`-Werror`. Its generated C, build log and exact driver copy remain in its local
directory; driver SHA256
`693b931bd0572bcc5571c0da9ca130223a0ca30f53bc8d31a2e7bea6bb337202`.
The tail fixture now uses the existing checked-loader convention
`-Wno-sign-compare`; runtime/native guards and finite budgets are unchanged.

Final raw builds `native-pair-q1/q2` repeat CODE SHA256
`92bb5620380bab477b8a49a57761ff7c42274350742af4214968af11ec9ac9af`
and DATA SHA256
`bba7d2b429f1cac523fe614cfd46197289bb08bbce8bd9fa2eb325907e5bb1d8`.
All19 image groups pass. Checked loader `pcie-tail-native-q1` passes60 cases/
eight mutants; native `pcie-tail-native-boot-q1` passes the actual publication
boot with eight harts. Canonical export verifies70 OpenWrt/five LuCI files,
source-lock SHA256
`2e0665f4572c03bde002bc5aecbba46ddd82c37b0d2102544a3523bdf89a1e86`.
All46 focused observer units pass, including five added tail checkpoint/BAR/
failure-cleanup controls. These do not establish the live caller's verdict.

Four additional synthetic fault-contract units check all12 distinct control
classes, original store prefixes, exact retained owner/preimages and full868352
protected-byte projections across all three stages and both HIF profiles.
`test_pcie_tail_native_controls.py` uses strict actual-prefix restoration and
explicit single mutations; its native matrix has not yet run. These new Python
consumers are not inputs consumed by the live producer, which remains frozen.

Scoped check `.local/npu-pcie-tail-native-20261016/scoped-check-q1.json`, SHA256
`c725d267e8abcb5a8e52de3b2cdc758694d11d8d271726039464552ed9e01060`,
verifies343 current input hashes/eleven passing scoped receipts with no drift.
It explicitly records fresh native tail and full512/eight-fault qualification
as false. Jev separately checked four evidence-scope claims; its uncertainty
and probabilities are retained in `jev-qualification-scope-q1-result.json`.
This semantic check is not a runtime verdict or authority to release buffers.

The selected116-test unit suite passes across strict capture/restoration,
DESC10 effect/store/transaction/retained contracts, PCIe transaction oracles,
retained raw contracts/cache, frame inventories and cold/reader/tail observers.
This count includes imported fixture tests; it is not a claim of116 distinct
native scenarios. Its four new fault-oracle tests are included, not additional
native admission evidence.

## Preservation And Limits

The prior journal cohort was copied and hash-verified before native edits:
454 files/124259837 bytes at
`.local/npu-pcie-tail-bind-20261016/preserved-journal-q2/receipt.json`, SHA256
`bdda5060f6e13bfcf5c8e83123a299445d15a63872201e69e3a3fd30d25a37a1`.
The accepted older1171-file native cohort is also protected. Neither is a full
executable environment or physical-device verdict.

FIT `978f9ddd735e860df25ebab52dfeb1ef2b6fa991832c90893c4916dfa335f33f`
is unchanged and unflashed. No world/hardware/subagent action. Final export,
repeat raw pair, checked loader publication, fresh full512/nine-store caller and
complete retained faults must pass before claiming this binding qualified.
INODE2/7, checked initial/hot IRQ, workers/hot ownership, full stack bounds,
physical backing/cache/exclusion/drains/lifecycle/recovery and actual-image/
client acceptance remain open under the full NPU goal.
