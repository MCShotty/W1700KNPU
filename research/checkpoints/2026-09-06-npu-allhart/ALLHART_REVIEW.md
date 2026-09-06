# Independent All-Hart Cold-Boot Review

## Findings

No actionable findings in the current `tests/npu/test_multihart_cold_boot.py`
and source-bound `allhart-native.json`, within the requested first-gate scope.
This is not approval of physical containment, complete worker initialization
or production restart.

## Accepted Verification

- Replayed two scenarios only against the existing immutable ELF: receipt
  case 1, flat PLIC with order `[1,2,3,4,5,6,7,0]`; and case 13, banked PLIC,
  order `[7,3,5,0,2,4,6,1]`, synthetic chip `0x100000`, variant 5 and indirect
  powerdown. Both complete case objects match the regenerated parent receipt.
- All eight harts enter original reset exactly once in each replay. Shared
  memory is retained across CPU-context switches. All 26 distinct detours
  match the parent patch receipt; original preimages and ELF identity verify
  (test lines 53-70). No older worker fixture or helper-return injection runs.
- Each hart writes only its own nonzero parked slot, with MSTATUS.MIE clear,
  exactly three times: initial park and two repolls (lines 104-109, 249-252).
  Reviewer hooks checked every barrier write: coordinator-only control/domain
  fields stay coordinator-owned; release, prepare, arm, ready and drain fields
  never receive nonzero values. Actual final request/released/armed/prepared/
  fault words are `[1,0,0,0,0]`, not merely the returned summary constants.
- Both candidate initializers execute once, on C0 only. Early resumptions
  preserve MSTATUS exactly zero for seven and three early workers respectively
  (lines 151-163). Across the two replays, 56 control-call CPU-context checks
  and 1,610 saved-stack comparisons pass. No other saved hart's stack changes.
- Each replay observes nine declared extension-CSR substitutions: one C0
  precheck and eight startup hart-ID reads. Observed substitutions otherwise
  remain the inherited printf/hart/delay models. The missing-extension-CSR
  control is correctly labeled emulator behavior, not a firmware finding.
- Strict source-8 callback binding remains installed after every worker and
  at the final boundary (lines 174, 236). Flat storage ends with word0 zero;
  banked storage retains C0 word0 `0x80fe00`. Consequently binding preservation
  is not evidence of physical interrupt delivery under either hypothesis.
- Repeated STOP remains epoch 1 while unreleased (lines 237-245). All eight
  parked slots remain 1, ready/drain slots remain zero, and the complete C0 L2
  image remains unchanged. No release or second-generation claim is inferred.
- The indirect profile writes `0x1fac080c` to `0xa1234000` and `0x1fae080c` to
  `0xa2234000`. GNU objdump independently confirms native zero stores at
  `0x84000986` and `0x84000990` to `0x1fa5b460` and `0x1fa5c460`. These are
  synthetic register/path witnesses, not observed board identity or powerdown.
- Inspected all seven missing-gate and six input-control receipts and their
  source assertions (lines 284-334); did not rerun them. Gate omissions prove
  missing ACK at the recorded immediate native boundary, not absence of every
  later gate. Unknown-chip handling stops at the unmodeled native reboot write
  `0x1fb00040` from `0x84005a22`; no physical reboot is emulated.

## Binding And Limits

- Test SHA256: `c7a34f40abb30b444e47adfc6d2761d665d3cf764210a64878baa53208cc6e85`.
- Final receipt SHA256: `7a95959ce24ac8edfb8bd53483301b9506abd92c44ec939de7444ff187f87ad6`.
- ELF SHA256: `bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931`.
- The regenerated receipt reports 14 positive cases, seven gate controls and
  six input controls. All 39 recorded source hashes match current files.
  The parent owns its broader final verifier/report; it was not duplicated.
- Eight rotated schedules and six feature profiles are bounded coverage, not
  all interleavings or a full cross-product of chip and PLIC behavior. Resets,
  IRQ frames and repolls are serialized. Physical CSR/PLIC banking, IRQ
  delivery, bus/cache behavior, DMA drains, post-gate work, complete attach,
  restart and actual-client operation remain unproved. RX callbacks are outside
  this review and remain with their assigned reviewer.
- Reviewer artifacts are under `.local/npu-allhart/review/`: `replay.py`,
  `replay.json`, `replayed-cases.json` and `binding.json`. An initial comparison
  against the older receipt was discarded during parent updates; only the
  two current-hash replays above are accepted verification.
- Only this report and reviewer scratch were written. No shared build,
  firmware/configuration, router/network, Git, parent test or protocol changes
  were made. The ledger was deliberately left unchanged.
