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

## Full Raw-Pair Frame Inventory

The first local all-frames-q1 run rebuilt matching raw bytes/allocated sections,
then failed an inventory condition that incorrectly demanded C .su records from
every component. Its driver/compiler outputs remain unchanged at
`.local/npu-pcie-tail-native-20261016/all-frames-q1`. A separate corrected
inventory records its partial C scope; the failed run is not relabeled passed.

The canonical `tests/npu/test_npu_raw_stack_usage.py` independently recompiles
each C translation unit with `-fstack-usage`, relinks in original input order and
requires every allocated section and complete CODE/DATA to match the frozen
reference exactly. It measures264 C frames/39 translation units over15 C-bearing
components. Largest individual frame3600 bytes is
`npu_emulation_txdone_skb_valid`; DESC10 packets_live2064/complete1072 and portable
tail context560 are also measured. These maxima must not be added as if all
functions shared one call chain or treated as a complete stack bound.

The four assembly-only components bridge/reset/order/egress remain unmeasured.
Five other defined symbols remain explicitly listed: base mailbox_register,
bridge base/channel guards, reset_prepare and allocator_startup_dispatch. This
is not complete function/assembly coverage, indirect-target closure, IRQ nesting
or physical per-hart stack acceptance.

Canonical receipt `.local/npu-raw-stack/pcie-tail-q1/result.json`, SHA256
`ddbe81abe7766313f693ec24e3adb0095c0a3e180d16aa7319e6b650481a4e25`.
Five synthetic inventory controls and the expanded144-test suite pass. Jev
checks byte-gate/failure/scope claims separately; no semantic result replaces
the actual byte, compiler or runtime checks.

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu:tools \
  python3 -B tests/npu/test_npu_raw_stack_usage.py \
  --pair .local/npu-pcie-tail-native-20261016/native-pair-q1 --name fresh-name
```

The current portable INODE host-only regression also passes382 calls/142
controls against normal-q1 objects, with the stack probe's allocated/relocation
sections unchanged. Receipt `.local/npu-inode-owner/pcie-tail-host-q1/result.json`.
This is not fresh RV32 execution or original-store/native admission.
Six retained native faults now pass; the two readiness faults and actual caller
are still live. No consumed source or native instruction/checkpoint limit was
changed for the frame/host follow-up. FIT978f9ddd remains unchanged/unflashed.

## Scoped Assembly Stack References

`test_npu_assembly_stack_usage.py` uses Capstone5.0.7 structured operands,
requires complete decoding of every selected byte,and matches each scanned
range to the hash-verified raw CODE. It covers complete bridge/reset/order/
egress text and five explicitly typed wrappers in base/bridge/reset/allocator.
The overlapping wrapper/component ranges are not independent coverage.

All five typed wrappers and bridge/reset text have no explicit SP references.
The ring consumer has one caller-owned `lhu a4,6(sp)`. Egress replays the
successful original16-byte prologue,or takes a separate nonreturning48-byte
fault reservation with12 saved words before calling npu_barrier_fail. These
local observations do not justify adding alternative paths together,omitting
callee frames or claiming complete permitted call-chain bounds. Other assembly
in C-bearing components,original firmware,indirect/IRQ closure and physical
per-hart stack placement remain separate work.

Receipt `.local/npu-assembly-stack/pcie-tail-q1/result.json`, SHA256
`e5e559dc02ec192602416669d206a7111a821fbfaba8aa4989a8862e88c00b84`.
Six synthetic decoder/byte/coverage/layout controls and all150 selected units
pass. This audit does not run or mutate a guest and changes no live input.

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu:tools \
  python3 -B tests/npu/test_npu_assembly_stack_usage.py \
  --pair .local/npu-pcie-tail-native-20261016/native-pair-q1 --name fresh-name
```

A separate profiled full512 denied-lock diagnostic passes with the existing
retained-control checks and native limits. Its result is
`.local/npu-pcie-tail-native-20261016/profile-denied-q1/result.json`, SHA256
`943aaa33186708801e4ff2064eae9acf7e6a6a1dca58c24d385803bad6445ea8`.
This restored diagnostic is not the fresh caller or a replacement for all eight
faults. The53267 emu_start calls include native C emulator work in their own
time;that time is not all removable observation overhead or physical NPU
performance. No observation scheduling change was implemented.
Jev checks these scope/path/performance/qualification claims in the retained
`jev-assembly-scope-q1-result.json`,not a runtime or stack proof. The actual
caller/two readiness faults remain live;the six other native faults pass.

## Address-Bound Direct Stack Candidates

`test_npu_direct_stack.py` independently matches all264 compiler frame records
to exact linked function extents and SP-based DWARF CFA records. Each function
is completely decoded and byte-matched to raw CODE. It resolves604 direct
transfers into this C-frame inventory and records81 unresolved transfers,
including register transfers and known addresses outside the C inventory.
It does not infer indirect targets from names or conflate Capstone's CALL group
with actual calls;this backend also labels some returns/tail jumps as CALL.

The direct graph has no cycles. Its largest candidate4480 bytes starts at the
tail callback through portable tail context/prior,RX PCIe and DESC10 complete/
packet checks. Edges use the caller's CFA at the transfer site,not every local
maximum added indiscriminately. A graph path may be infeasible,and missing
assembly/original/indirect/IRQ edges prevent any complete per-hart stack bound.
Neither4480 nor the original modeled16KiB stack stride is physical acceptance.

Exploratoryq1 omitted self/interior calls as internal control flow and did not
inspect conditional transfers leaving a function. Its exact driver and receipt
are preserved at `.local/npu-direct-stack/pcie-tail-q1` with LIMITS.md. Corrected
q2 retains those edges conservatively and gives no finite candidate to any
root reaching a direct cycle. Ten synthetic controls and all160 selected units
pass. The corrected independent receipt is
`.local/npu-direct-stack/pcie-tail-q2/result.json`, SHA256
`61661c058951497fe46a11d096144ee1e9488307a541afbb02f4a566dfb66e90`.

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu:tools \
  python3 -B tests/npu/test_npu_direct_stack.py \
  --pair .local/npu-pcie-tail-native-20261016/native-pair-q1 \
  --frames .local/npu-raw-stack/pcie-tail-q1/result.json --name fresh-name
```

Jev's retained semantic scope checks do not establish a full bound. The full-bound
question is split between contradicted.54/not_established.46;the deterministic
scope remains incomplete either way. Original/assembly calls,allowed indirect
targets/IRQ nesting and actual physical per-hart placement remain open. Native
caller/two readiness tests and all their consumed sources remain unchanged/live.

## Fresh DESC10 And Eight Retained Faults Pass

The actual provider/allocator/caller pcie-tail-native-q2 has passed full512
DESC10:25606 original stores/3072 packet claims/1792 BA claims,ready1/RX step2
and exact856064 protected bytes. Its independent read-only original-store
trace is validated and no projected protected byte differs. Observed receipt
`.local/npu-host-tx-lifetime-20261011/pcie-tail-native-q2/desc10-observed.json`,
SHA256 `dc5dfe943099871b5eb83b3a8febfd90f054a663021b10e29dd331a11066ced8`.
This is a completed stage of a still-live fresh caller,not its terminal result.

The separate retained-control job is terminal0 with all eight unchanged full512
cases passing. Both before-ready-bitmap and before-ready-plan stop25604 before
the final counter/ready stores. Denied/partial-pool/claim-fault/head-changed/
release-fault/denied-skb19 preserve their exact original expected effects and
claim counts. The cached verifier independently rechecks every case,original
snapshot,current source input and stored artifact without source-drift waivers.
Aggregate `.local/npu-host-tx-lifetime-20261011/pcie-tail-native-q2/desc10-retained-controls/result.json`,
SHA256 `70b8bf5994410e835370d3ade401325e62df86e17625a812693f0f45607b488e`.

The actual caller is still executing RX PCIe. New tail admission,the full caller
receipt,broader raw qualification and tail-specific native fault matrix remain
pending. Keep its consumed inputs frozen. Do not restart the completed fault
job from earlier live notes. Restored controls remain diagnostics,not fresh
boots,physical faults,full setup or hardware acceptance.

## Complete Tail Fault Matrix Runner

`pcie_tail_retained_controls.py` requires all12 existing tail fault classes at
each of the three strict actual-caller prefix origins. It validates every
current input/artifact hash,stage/case/effect count,404-byte SETUP/256-byte owner,
3072 claims and exact protected region identities/sizes with zero unexpected
differences. Cached aggregates cannot omit a case or promote diagnostic scope
to fresh caller/full setup/hardware. Missing/incomplete cases remain failures.
It invokes the unchanged native case driver with the same60-second host-entry
budget as the current caller;no RV32 instruction/checkpoint bound is changed.

Seven synthetic aggregate contract tests and all167 selected units pass. The
actual36-case matrix has not run while the fresh caller is still in RX PCIe and
its three tail prefixes are pending. The existing eight-case DESC10 matrix is
separate and already terminal0. No new native positive is inferred from the
runner's tests or Jev's retained semantic scope checks.

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu:tools \
  python3 -B tests/npu/pcie_tail_retained_controls.py \
  --pair .local/npu-pcie-tail-native-20261016/native-pair-q1 \
  --caller .local/npu-host-tx-lifetime-20261011/pcie-tail-native-q2 \
  --output .local/npu-host-tx-lifetime-20261011/pcie-tail-native-q2/tail-retained-controls
```

## Preservation And Limits

Latest progress:the fresh actual caller's RX PCIe memory comparison passes.
Tail stage0 is live,and five of its restored entry/reserve faults pass;the
complete36-case matrix remains pending. Independent original RRO0/1/3 probes
pass137 exact byte/ABI cases in synthetic RAM,five projection controls/all172
selected units pass. See RRO.md for the separate API24 allocation/session/reset
contract;this is not checked admission,physical DMA or permission to release
workers. The live checked source inputs remain unchanged.

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
