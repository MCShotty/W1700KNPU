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

Scoped check `.local/npu-pcie-tail-native-20261016/scoped-check-q2.json`, SHA256
`c99132924fc50e332f88660a11be2b8ec9ed60e3e9b4a77b904c1480d4ec2ca9`,
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

Mainline checkpoint `1bc4d0e8043850285b00da8192773ed560ece940` is pushed and
remote-ref verified; tree `8edae1dd0a6dc3127d6fe78d9e1f5dfc309da393`.
Scopeq2 supersedesq1 after removal of an unused import from the new fault
consumer. No source consumed by the live actual caller changed. Q1 is retained
as a historical scoped result, not relabeled a current-input seal.

## Compiled Follow-Up

- Exact tail allocated sections match a separate two-translation-unit O2/
  `-fstack-usage` build. All21 defined C functions are covered, largest individual
  frame560 bytes. Receipt `.local/npu-pcie-tail-native-20261016/stack-tail-q1/result.json`,
  SHA256 `28ec12e03ca95143cbb44134843fd481a4b622a7d3c905f6687a75a0829aceb9`.
  This does not measure other components/original assembly, complete call chains,
  IRQ nesting or physical stack placement.
- Standalone Ghidra q1 exports eight functions but cannot follow its unmapped
  imported predecessor at840e4b72. Keep that result partial. New
  `MapNpuRawCode.java` validates the requested raw hash and every existing
  component byte before filling analysis-map gaps, then reads back the entire
  CODE image byte-for-byte. This changes a temporary Ghidra database, not the
  firmware file or native replay state.
- Ghidra q2 maps960940 bytes, verifies10666 existing component bytes and exports
  eight selected functions/zero failed decompilations among965 auto-analyzed
  executable functions under `RISCV:LE:32:AndeStar_v5:gcc`. The predecessor hole
  is absent and the completed-stage checks bracket unlock in the compiled
  callback. DWARF expressions and type propagation still limit pseudocode;
  965 is an analysis observation, not an exhaustive firmware inventory.
  Export SHA256 `b62d8c4ad3f89b238d3bc17a80fc14374ec0588c82ceeedacdb83b992ee086c4`;
  ELF SHA256 `5c1ff5b8772144d7b90fccf9d9236cbc7573fb4c9c000182b915e8aeddb510cd`.
- Actual Ghidra negative controls reject wrong raw hash and an explicitly
  corrupted component byte, requiring the exact exception and absence of the
  map-pass marker rather than trusting the tool exit code alone. Receipt:
  `.local/npu-ghidra-map/tail-map-q1/result.json`.
- Existing sanitized TX lifetime113/nine mutants and RX166/seven mutants pass;
  no exposed TX frees. Their records/backing/framework remain modeled.

## Retained Consumer And Live Qualification

The old broader raw consumer assumed RX PCIe was the caller's final command.
It now checks the appended three tail stages, all nine literal original effects,
ordered lock18 writes and every protected region, followed by the actual padded
INODE envelope denial. Its enum is obtained from the independently hashed
compiler-produced sender, not trusted from the caller's self-description.
Missing/duplicate/inexact tail evidence cannot pass. This consumer was verified
absent from the frozen producing snapshot's inputs before editing; all source
consumed by the live actual caller remains unchanged.

Seven new synthetic contract tests and the expanded139-test suite pass. All old
full512/eight-fault gates are retained. Five early native retained cases pass
(`denied`, `partial-pool`, `claim-fault`, `head-changed`, `release-fault`); three
late full-size cases and fresh caller `pcie-tail-native-q2` are still live.
The fresh caller has passed all six API21 phases/53260 effects and RX-event,
and is in full512 DESC10. No positive tail or completed native matrix verdict.

Extended scoped receipt
`.local/npu-pcie-tail-native-20261016/extended-scoped-check-q1.json`, SHA256
`5cedd413f6499bd6630b446295706c5c694b7a35bb3cbe834830db2ab10cf2ff`,
verifies404 current input hashes and all139 units. Its native qualification
flags remain false and its live notes describe the moment of that receipt.
This is not a new full executable environment, physical proof or promotion of
the preserved older native seal.

Mainline follow-up `2d359dc23e6d23c9e77f48a59d11a824c98f1191` is pushed and
remote-ref verified, tree `255041935d21b9490db39881039d02d01e69b40f`.
The worktree check lists only canonical main; no additional worktree/subagent
was created. The current independently compiled INODE enum is24; both HIF
synthetic consumer contracts reject the unrelated API2 when bound to that
sender. See `NEXT_INODE.md` for the exact remaining checked envelope/prior/
original callback contract. Jev checks three scope/requirement claims in the
retained `jev-next-inode-q1-result.json`; that is semantic evidence, not native
constructor or IRQ execution.

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
