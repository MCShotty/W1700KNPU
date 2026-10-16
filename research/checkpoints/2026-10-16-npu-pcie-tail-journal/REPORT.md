# PCIe Tail Protocol Journal And Native Dispatch Boundary

Date: 2026-10-16. Canonical WSL mainline, following `1bc68bee`.

## Implemented

- The cold server retains the exact accepted TX2 register, including the chosen
  HIF profile, after later commands overwrite `command.value`.
- A separate three-step journal admits header/API/value tuples `(0x10,0,TX0+0x160)`,
  `(0x12,0,TX2+0x110)`, then `(0x1f,0,0)`. Completed RX PCIe/DESC10 protocol
  history, enrolled TX backing, full prefix, exact window and matching late
  predecessor fields remain prerequisites. This is protocol admission only.
- Linux retains accepted TX0/TX2 values and tail progress, rejects order/value/
  overflow errors before transport, and detects changes to those fields during
  transport. Snapshot reporting includes them. No timeout retry or reclamation
  authority is added. Read-only version/STATUS operations remain compatible.
- Four words append to private `npu_cold_setup`, growing388 to404 bytes. Wire
  messages remain80 bytes and old private offsets remain unchanged. Exact raw
  BSS expectations and read-only RX PCIe projection now include the new fields.
- The native dispatcher previously classified every header0x1f as a successful
  synthetic binding. Older protocol code rejected these tail commands before
  dispatch, so this was a latent problem exposed by extending admission, not
  evidence that older qualified images executed them incorrectly. Binding now
  requires its exact API. All three unbound tail commands explicitly fail the
  callback boundary, retaining the failed transaction rather than reaching
  unguarded original stores or falsely acknowledging selector15.
- The existing exporter refreshed the unified22 component copies/source lock.
  Cumulative OpenWrt/LuCI patches and earlier UI/WiFi content are unchanged.
  Source replay verifies70 OpenWrt/five LuCI files at the existing6.18.52 pins.

## Scoped Checks

Final `.local/npu-pcie-tail-bind-20261016/journal-scope-q2.json` SHA256:

`a07b27a753153006f753cfd98248bb86093400110534588ed86de88708d40de2`

It verifies452 current source/artifact inputs and records these separate scopes:

| Check | Result | Boundary |
| --- | --- | --- |
| Actual cold server/codec/Linux executor |1930 cases,486 tail cases,53 compiled mutants; ASan/UBSan/leak | Explicit callback/backing/parking models; both HIF profiles |
| Existing provider/session C |609 cases,nine compiled mutants; sanitizers | Kernel/transport effects modeled; no native cases requested |
| Exact RV32 native dispatcher |45 routing cases,three compiled mutants | Begin/finish and original callback targets are explicit stubs |
| Borrowed packet-plan guard |24 host/RV32 cases | Prior/readback/allocation guards remain explicit stubs |
| Focused regressions |118 units,no skips | Synthetic fixture/parser/oracle/observer/archive/header contracts |
| Raw pair/image | Independent pairs match,all18 groups pass,18 components/147 hooks | Offline assembly/readback/hook closure,not fresh initialization |
| Negative raw execution | Six boot denials,six unleased DESC10 denials | Actual raw guard/boot code with explicit forbidden synthetic contexts |
| Normal archive |22 RV32 objects compile | Not a newly packaged kernel/world/FIT |
| Exact DESC10 C frames |29 functions,two translation units,max2064 bytes | Allocated sections match; not assembly/call-chain/physical bounds |
| Unified source export |70 OpenWrt/five LuCI files,22 component copies | Temporary-index patch/header/hash checks,not a world build |

Final protocol receipt: `.local/npu-cold-wire-20261010/pcie-tail-protocol-q7/result.json`,
SHA256 `3698f27028b3d9a67a324f669719ba298842042c3c12adfe05c91605ed6d4cb0`.
Provider receipt: `.local/npu-provider-session-20261010/pcie-tail-host-q2/result.json`,
SHA256 `4362b5fe288c4944edc1af8000fb78f1b9727e3b5eb969bba6d2b63d51972aae`.
Dispatcher receipt: `.local/npu-cold-native-dispatch/pcie-tail-q5/result.json`,
SHA256 `cc977e80bcbc9b1699e4cd7fe6e18ef8711ea1499bdcf934e5c519bdf504119f`.

Current repeat pairs are `.local/npu-pcie-tail-bind-20261016/pair-q4` and `pair-q5`:

- CODE937844 bytes, SHA256 `6bedb6ccea78bf1a528b58e710dc8607fe02634ec2e6e20f4c79a67e658d3695`.
- DATA25728 bytes, SHA256 `076912dc2efc39328a51d46e29faae0d9d930ca0f1a6d9dc8143a4108465288b`.
- Source-lock SHA256 `18d8b114bbac11f622dfd7cc7d72909c7be1099147875d3a748301ebf317de64`.

Intermediate failed attempts remain local. They exposed an obsolete pretransport
assertion, an invalid XOR-based HIF fixture, missing isolated late-journal mutant
coverage, and dispatch-fixture build/emulator setup errors. They are not native
failure or success verdicts. Later passing intermediate matrices are not reused
as current-input qualification after subsequent source changes. The first seal
attempt stopped at a wrong tooling path before writing a success receipt; q2
uses the corrected existing migration-helper path and verifies all hashes.

Jev supplied bounded contract/scope checks, not code, planning or permission.
The retained scope batch `.local/npu-pcie-tail-bind-20261016/jev-scope-q2-result.json`
labels native-admission-from-fixtures contradicted(.99), bounded dispatcher scope
supported(1.0), and old-receipt-as-current-pair qualification contradicted(1.0).
The earlier held-snapshot transition warning had Noul.8. These are semantic
evidence, not proof. The official [API](https://docs.typesafe.ai/api) and
[primitives](https://docs.typesafe.ai/primitives) were checked; no key was exposed.

## Still Required

1. Keep existing RX PCIe prior helpers narrow. Add explicit authenticated tail
   successors through descriptor,TXBUF,RX-event and DESC10 helpers. Validate the
   actual current404-byte SETUP; never fabricate an earlier header/RX-step view.
   Handle only verified journal transitions in earlier whole-SETUP comparisons
   and bind selected TX2 back to the independent completed native TX owner.
2. Instantiate the actual portable PCIe-tail owner and bind all nine original
   stores under completed prior owners,exact BAR/session/boot/nonce,original
   lock18,masked IRQs,slot identity,neighbor preimages and failure retention.
   Preserve the qualified4/6-byte boundaries/displaced AUIPC continuations.
   Replace the native denial only with actual ownership checks,not a whitelist.
3. Extend actual provider lifetime/routing and the real MT7996 caller. Capture a
   fresh current-input prefix; retain full512 DESC10 and all eight fault classes.
   A returned1 from the stock callback is not a completed store-owner journal.
4. Complete INODE2/7,checked initial/hot IRQ,workers/hot ownership,full stack and
   physical backing/cache/exclusion/drain/reset/removal/rearm/recovery/client
   requirements. The overall NPU goal remains active.

All current jobs are terminal. The old native sealb02ebf82 applies only to its
separately preserved1171-file producing cohort,not the changed current pair.
This checkpoint is not fresh actual-caller/full512/eight-fault qualification.
No world rebuild,flash,hardware action or subagent was performed. Existing FIT
SHA256 `978f9ddd735e860df25ebab52dfeb1ef2b6fa991832c90893c4916dfa335f33f`
was rechecked unchanged; it remains offline-qualified/unflashed.
