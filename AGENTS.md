# W1700KNPU Workspace

## 2026-10-17 - Current Provider Module Linked In Isolation

- Current source-lock f9f90ba5 links the provider's five C objects/22 source
  components into a real AArch64 .ko in an independent complete kernel copy.
  Vermagic is 6.18.52 SMP mod_unload aarch64; three expected exports and all 70
  imports pass offline checks. Module SHA256 starts 8f8a6a54, not the old module.
- Receipt 6fef3cfc and scope 7044084e verify all 102,685 original kernel content/
  file-mode/relative-link entries unchanged, protected mt76/FIT identities and
  218 unique tests/236 executions. Eight inventory/ELF-parser controls are
  synthetic tests, not the real link evidence. One preexisting-style modpost
  MODULE_DESCRIPTION metadata warning is retained and reported.
- No module load, mt76 consumer relink, vmlinux/world/FIT rebuild, native cold/
  full IRQ/physical acceptance or hardware action. Source-lock stays f9f90ba5.
  Both old-cohort cold callers/fault matrices remain live and must not be
  restarted. Read research/checkpoints/2026-10-17-npu-provider-link/REPORT.md.

## 2026-10-17 - RRO Caller Boundary Rechecked

- Actual16-byte/four-word mt76 RRO helper holds RCU and uses GFP_ATOMIC. New
  caller/provider C294 cases verify checked denial before modeled mutex/RPC,
  exact payload,balanced null/use scope and unchanged metadata. This does not
  certify arbitrary scalar4 atomic calls or implement an atomic RRO transport.
- Fresh137 original callback probes pass all128 blocks/session/reset/alias
  cases on synthetic RAM;five projection units pass. Scope c5e611c6 verifies108
  hashes. No checked RRO admission or physical backing/drain is established.
- Higher-level init/reset ignores returned errors;that remains source-only
  observation. RRO backing uses dmam-managed allocations;future error returns
  must be coupled to retention before uncertain device-visible publication,
  not merely early abort/cleanup. No production/source-lock/image/hardware
  changes in this pass. Current source-lock staysf9f90ba5. Native cold/fault
  jobs below remain live/frozen. Read rro-bridge/REPORT.md in the checkpoints.

## 2026-10-17 - IRQ Status Value And Poll Scope; Cold Runs Frozen

- Status getter now initializes its output and returns0 on read error. Host
  MSan is clean for the corrected body and reproduces the preserved legacy
  uninitialized return. Actual read/ack/mask5778 fixtures still show148 handler
  error cases scheduling NAPI/5624 silent bulk errors. This is a value-path fix,
  not checked IRQ propagation,quarantine or a drain/physical witness.
- New scope3f61aa32 binds274 current hashes/210 unique units/228 executions,
  provider609/nine,RCU52/five mutants and isolated provider object(getter32/
  cold544 frames). Kernel patch applies zero-fuzz to all five manifest-selected
  files;source70/5/22 passes,source-lockf9f90ba5. Prepared kernel/modules/FIT
  stay unchanged. Earlier seal/source-lock notes below describe older cohorts.

- Main's NPU poll callback explicitly brackets pointer lookup/provider use
  with RCU,including null;ordinary IRQ route is unchanged. Actual-C21 startup/
 31 poll fixtures/five compiled RCU mutants pass. Twelve startup/eight hot IRQ
  errors are still lost by the void ABI;this is not the checked IRQ contract.
- Two isolated AArch64 objects compile with32-byte poll frames;NPU-off uses an
  explicit preprocessor fixture,not a full alternate Kconfig/world. Scoped seal
  f2a4c15c binds496 hashes/210 unique units/228 executions. No kernel concurrency
  or physical lifetime proof,world/module/image rebuild or hardware action.
- Export allowlist now includes mt7996/mmio.c. Q1 missed the file and changed
  no source-lock;it does not export the fix. Q2 zero-fuzz patch application
  reproduces all10 changed files,source70/5/22 passes;source-lock0705aea8.
  All eight protected prepared source/object/module/FIT hashes are unchanged.
- Both actual cold callers/eight-DESC10-fault matrices remain live on600055c.
  Live-viewd457e4b1 verifies all2330 original files/five supplements unchanged
  after main edits. Latest live-viewaeed28bb also verifies old provider C after
  the status fix. Both fault matrices have six individual passes;two readiness
  cases/profile and both nominal callers remain live. No terminal constructor
  verdict. These results cannot qualify newer main. No hash
  waivers,job restarts or subagents. Read the poll-rcu/REPORT.md checkpoint.
  New status evidence:research/checkpoints/2026-10-17-npu-irq-status/REPORT.md.

## 2026-10-17 - INODE Caller Qualification In Progress

- Current driver sends both constructors via checked80 after all three tail
  commands;`--pcie-tail` now requires explicit `--inode`. Read-only oracle checks
  literal1030/six original stores,exact4372-owner/412-SETUP/868352 protected
  bytes/all native private fields/2MiB CODE,except the existing current stack
  band. ABI is observed before mailbox context restoration;an actual tiny guest
  demonstrates why post-restore checking hides corruption. Units are synthetic
  oracle evidence,not INODE admission. Old denial receipts cannot be promoted.
- Cold observer now uses the pinned fresh C-API CSR reader;legacy observers
  retain scalar mode. Existing native guards/raw bytes/3M entry gates/old lane
  budgets are unchanged. No whole-native/hardware speedup is measured.
- Preflight9fcea999 verifies372 current hashes,196 unique unit cases/214 runs,
  all20 image/repeat groups,loader60/eight,six negative boot controls and actual
  C sender checks.18 imported fixture cases repeat and are explicitly counted.
  First count-only assertion failure is preserved;no native fault gate shrank.
- D975 cohort2388 files is preserved(a0e02b38). Original-path current copy
  e62be4a8 preserves2330 files;wrong-boot native smoke passes and parent mount
  stays unchanged. Both fresh HIF callers are live on600055c,through full RX/
  page/TX-buffer/API22 prefix. Both eight-case full512 DESC10 diagnostic matrices
  are also live from actual captures;no terminal caller/fault verdict yet.
- Added24-case INODE fault runner with exact owner/SETUP/protected/private/CODE/
  ABI and case-specific unlock CSR checks. Fault preflight4c7f7174 passes208
  unique cases/226 executions,including12 new synthetic contracts. Original2330
  frozen files/receipt are unchanged;new diagnostic-only supplements2c323aa1/
  f6fee208 add five files. Both seven/five-case unit suites also pass in the
  original-path copy. Actual INODE faults await real constructor prefixes.
- Exact20-component stack audit measures297 C frames,largest4704;687 direct
  transfers yield a9696-byte candidate,with91 unresolved transfers. This is not
  a complete/physical stack bound. All36 tail faults/both constructors/new24
  faults and broader raw qualification remain pending. FIT978f9ddd and prepared
  kernel/module remain unchanged/unflashed. No hardware/subagents. Read
  research/checkpoints/2026-10-17-npu-inode-caller/REPORT.md.
  This supersedes earlier current/live notes below.

## 2026-10-17 - Native INODE Binding; Positive Qualification Open

- Mainline now builds20 components/168 hooks:actual API24 callback/11 original
  store guards,authenticated predecessor successors,SETUP412 and checked
  provider constructor2/7 routing. RRO0/1/3 remain denied in this checked lane.
  Added lock18 exclusion is not an original constructor mutex. Native24-byte
  frame preserves the original wrapper read extent; no earlier SETUP is forged.
- Protocol2282/60 mutants,provider609/nine,new retained-pin provider504/10,
  portable INODE418 host/2348 RV32/154 controls/eight mutants,dispatcher70/five,
  packet guard48,36 raw unleased denials,repeat20-image groups,loader60/eight,
  published eight-hart boot and189 selected units pass their separate scopes.
  Fresh authenticated INODE/current full512/eight-fault/full36 qualification is
  still false. The actual native sender driver/oracle must be extended next.
- Frozen404 HIF2 caller is terminal0. All36 old tail cases pass individually,
  but aggregate615ce917 is terminal1 for missing per-case pair artifacts. Keep
  that failure;future restoration/aggregation now require all pair/ELF hashes.
  No old native result qualifies current20/412. All older jobs are terminal.
- Source70/5/22 is exported;isolated AArch64 provider compiles(frame544),not a
  module/world/image rebuild. Prepared kernel/module/FIT978f9ddd unchanged and
  unflashed. Full RRO/IRQ/hot/workers/stack/physical/drain/lifecycle/recovery/
  clients remain open. No hardware/subagents. Read
  research/checkpoints/2026-10-17-npu-inode-native/REPORT.md.
  This supersedes earlier current/live/closed-dispatch notes below.
- Scoped seal42f6ff34 verifies502 exact current hashes,189 units,22 archive
  objects and six negative boot controls. Native INODE/full512/eight-fault/
  current full36/full_setup/hardware qualification flags remain false.

## 2026-10-16 - Checked INODE Journal; Native Owner Still Closed

- Canonical server/Linux client retain API24 selector2 then7/scalar0 only after
  all three PCIe tail stages. SETUP grows404->412 by appending two words; clang
  AST/RV32 object tables independently verify all35 old offsets unchanged.
  VERSION/STATUS remain compatible. RRO0/1/3 are not constructor ownership.
- Host protocol2282/352 INODE cases/60 compiled mutants,provider609/nine,
  RV32 dispatcher70/four,packet guard32,raw19/156/all19 image groups,loader60/
  eight and actual published-byte/eight-hart boot pass. Selected186 units pass.
  API24 checked dispatch explicitly stays closed until its actual11 original
  store guards/retained owner are bound. No fresh full512 qualification of412.
- Original canonical HIF2/full36-tail jobs were intentionally migrated,not
  timeout-restarted or counted as passes. Their731 terminal files are preserved.
  New runs use the frozen37ee4e3/404-byte candidate at original paths in private
  namespaces. Six actual /proc/PID/root source views still match that copy after
  main edits. Their results cannot qualify412 or later main changes.
- Source export70 OpenWrt/five LuCI passes;normal22 RV32 objects compile.
  Prepared kernel sources have an older Linux-control revision and were left
  intact. No AArch64 provider/world/image rebuild is claimed. FIT978f9ddd stays
  unchanged/unflashed. No hardware/subagents. Next actual native INODE binding,
  then checked IRQ/hot/workers/stack/physical/drain/lifecycle/recovery/clients.
  Read research/checkpoints/2026-10-16-npu-inode-journal/REPORT.md.
  This section supersedes earlier current/live notes below.
- Scoped seald56cdfe0 verifies433 current input hashes,all186 selected units,
  exact22 archive objects and six raw boot controls. It explicitly leaves
  fresh native INODE/full512/eight-fault qualification of412 false.

## 2026-10-16 - Latest Verified Qualification State

- Fresh default-HIF actual caller pcie-tail-native-q2 is terminal0 through
  full512 DESC10, RX PCIe and all three tail stages/nine original stores.
  Receipt cd9650e8 revalidates351 current inputs. Actual padded API24 INODE
  is denied before its callback; this is not a constructor verdict.
- All eight full512 DESC10 retained faults and broader raw/six boot controls
  pass (70b8bf59/66130bdf). All12 stage0 tail faults pass; the full36 matrix
  and fresh HIF2 caller are still running. Do not claim their final verdicts.
- New private validation capsule preserves3320 files/633122048 bytes for
  candidate37ee4e3, receipt24b9d075. Original-path native restored fault and
  raw/six-boot/eight-cached-fault checks pass without receipt/hash waivers;
  parent mount unchanged. Not a complete portable execution environment or
  acceptance of later main changes. Read checkpoint CAPSULE.md.
- Isolated CSR sampler/eight controls is not wired into any NPU observer.
  Host-read timings are not whole-emulation/hardware speedup. All185 selected
  units pass, including five capsule copy/path controls. Consumed original
  native inputs remain frozen until their runs finish or are explicitly migrated.
- This section supersedes older live-status notes below. FIT978f9ddd remains
  unchanged/unflashed. INODE/checked IRQ/hot/workers/full stack/physical/drain/
  lifecycle/recovery/client gates remain open. No hardware or subagents.

## 2026-10-16 - Native PCIe Tail Binding In Qualification

- New native component binds all nine original PCIe0/2/15 stores and delegates
  other callbacks to the already-linked RX PCIe predecessor. Explicit tail
  successor helpers retain completed owners, packet geometry, original lock18,
  IRQ, neighbors and exact readbacks. No earlier SETUP history is fabricated.
- Actual provider lifetime/routing and actual MT7996 five-frame sender are
  extended. Scoped provider84/five mutants, dispatcher52/three, guard32,
  portable host/RV32467/379 controls/nine mutants and sender12 pass. New raw
  intermediate19-component/156-hook image passes all19 groups and18 unleased
  denials; it is not a fresh actual-caller/full512/fault qualification.
- Previous journal cohort454 files is hash-preserved (receiptbdda5060), as is
  the accepted older1171-file native cohort. Actual caller and retained faults
  are still pending; scoped sealc9913292 verifies343 current input hashes.
  Freeze consumed inputs during native replay; never waive source hashes or
  weaken full512/eight-fault coverage. Current SETUP remains404 bytes.
- Final source70/5, repeated raw19/156/all19 groups, loader60/eight and actual
  published-byte/eight-hart boot pass. Fresh actual caller pcie-tail-native-q2
  is live; freeze consumed inputs. Q1 stopped at host compilation, before
  native execution, and is preserved. FIT978f9ddd remains unchanged
  and unflashed. INODE, checked IRQ/hot, workers, full stack/physical/drain/
  lifecycle/recovery/client scope remains open. No hardware or subagents.
  Read research/checkpoints/2026-10-16-npu-pcie-tail-native/REPORT.md.

- Follow-up scoped seal5cedd413 verifies404 hashes/139 units. Exact tail21 C
  frames match current allocated bytes (largest560); raw-CODE mapping fixes
  the standalone Ghidra predecessor gap and exports eight selected functions.
  Two corrupt-map guards pass. Raw retained consumer now explicitly checks
  appended nine-store tail/actual padded INODE denial and independent sender
  enum; all eight full512 faults remain mandatory. Producer inputs are frozen;
  fresh caller and eight-fault jobs are live, five early faults have passed.
- Canonical test_npu_raw_stack_usage.py now measures264 C frames/39 translation
  units with all19 allocated component sections and full CODE/DATA byte-exact.
  Largest3600;four assembly-only components and five other function symbols
  remain unmeasured. Five inventory controls pass; selected suite144 passes.
  Portable INODE host382/142 passes against current normal objects, not native
  admission. Six native retained faults pass; readiness pair/caller remain live.
- Exact Capstone assembly audit covers four pure-assembly text sections and
  five typed wrappers. Egress reserves16 bytes on its success path or48 on
  its nonreturning fault path; ring consumer reads caller SP+6. Wrapper local
  SP references are absent,not proof about callees. Six new controls/all150
  selected units pass. Receipt e5e559dc; other assembly/full chains/IRQ/physical
  stacks remain open. Native jobs/inputs stay unchanged and live.
- CFI/direct-stack audit independently binds all264 C frames to linked symbols,
  resolves604 direct transfers and lists81 unresolved transfers. Largest direct
  graph candidate4480 is not a full bound; original/assembly/indirect/IRQ/
  physical scope stays open. Correctedq2 receipt61661c05 retains conservative
  self/interior/conditional edges;old exploratoryq1 is preserved with limits.
  Ten new controls/all160 selected units pass;native jobs/inputs unchanged.
- Latest native progress: fresh actual caller's full512 DESC10 passes25606
  original stores/3072 packet claims/exact856064 protected bytes. All eight
  full512 retained faults pass;both readiness cases stop25604. Aggregate
  70b8bf59 revalidates current inputs/artifacts without drift waivers. Fault
  job is terminal;actual caller remains live in RX PCIe,tail qualification
  pending. Do not restart the completed fault job from earlier live notes.
- pcie_tail_retained_controls.py now runs/revalidates all36 native tail faults
  (12 cases/three strict actual prefixes),with exact stage/effects/regions,
  current hashes and no cached scope promotion. Seven contracts/all167 units
  pass;native matrix has not run while three prefixes are pending. New runner
  does not edit frozen RV32/observer inputs or change native count bounds.
- Original API24 RRO0/1/3 now has137 direct byte/ABI probes over synthetic RAM,
  all128 blocks/session/reset boundaries/aliases,with distinct saved registers
  and unchanged MSTATUS. Receipt2d01b092;five projection controls/all172 units
  pass. No checked admission or physical backing/reset/drain proof. Read the
  checkpoint RRO.md before treating constructor2/7 as the full API24 contract.
  Fresh caller RX PCIe passes;tail stage0 and its fault shard remain live.

## 2026-10-16 - PCIe Tail Journal Integrated; Native Dispatch Closed

- Actual server/Linux executor retain accepted TX2/HIF and ordered PCIe0/2/15
  progress separately from RX steps. Private SETUP404 appends four words;
  previous field offsets stay unchanged. Version/STATUS reads remain available.
- Exact native dispatcher denies the three unbound tail commands, retaining
  failed leases. Header0x1f alone is no longer synthetic-bind success. Do not
  remove this denial until real completed-owner/store guards are bound.
- Protocol1930/53 mutants,provider609/nine,compiled RV32 dispatch45/three,
  guard24,118 units,raw18/147/all18 image groups and six boot/six unleased
  denials pass. Normal22 objects compile; exact DESC1029 C frames match.
  Scoped seala07b27a7 verifies452 inputs. Source export/lock refresh70/5 passes.
- All jobs are terminal. Current raw CODE6bedb6cc/DATA076912dc is not fresh
  actual-caller/full512/eight-fault qualified. Old native sealb02ebf82 applies
  only to its preserved1171-file producing cohort, not these changed inputs.
  FIT978f9ddd remains unchanged/unflashed; no world/hardware/subagents.
- Next explicit authenticated tail successor helpers,actual nine-store owner,
  provider lifetime/routing and fresh full512/fault qualification; INODE/IRQ/
  hot/physical/drain/lifecycle/client/full-stack scope remains open. Read
  research/checkpoints/2026-10-16-npu-pcie-tail-journal/REPORT.md.

## 2026-10-16 - Packet-Plan Guard And Retained Raw Replay Qualified

- Fresh actual provider allocator/host caller desc10-plan-q2 is terminal0
  through full512 DESC10 and RX PCIe:25606 original stores,1028 original lock
  writes, exact856064 protected/2076 packet bytes and3072 PKT/1792 BA claims.
  Default HIF only; nominal-only skipped earlier negatives. full_setup=false.
- All eight full512 restored faults pass with current input/artifact hashes;
  both readiness faults stop at25604. Broader raw q2/six boot controls pass.
  No seeded lease, forged history, post-load ELF injection or source-drift waiver.
- Sealb02ebf82 verifies1169 inputs/117 focused units;1171-file exact producing
  cohort is preserved at .local/npu-desc10-plan-20261015/qualified-q2-inputs,
  receipt55a17e60. Not a complete executable environment or hardware proof.
- All jobs are terminal. Earlier dated live notes are historical; never restart
  them. Preserve the accepted cohort before editing consumed native inputs.
  FIT978f9ddd remains offline-qualified only; no flash/hardware/subagents.
- Next real PCIe0/2/15 and INODE2/7 guard/history bindings, checked initial/hot
  IRQ, workers/hot ownership, complete stack bounds and physical DMA/cache/
  exclusion/drains/reset/removal/rearm/boot/client acceptance remain open.
  Read research/checkpoints/2026-10-15-npu-desc10-plan/REPORT.md and STACK.md.

## 2026-10-15 - Packet-Plan Guard Fixed; Fresh Qualification Live

- Prior retained-replay-q3 is terminal: nominal DESC10/RX PCIe prefix passed,
  seven faults passed, before-ready-plan failed25606 versus required25604 stores.
  Its526-file exact replay cohort is preserved before native edits. No waiver.
- Actual guard now checks borrowed packet base/extent before and after readers,
  including the PCIe successor. Compiled host/RV3224 cases,103 focused units,
  repeated raw18/147/all18 image groups and checked loader60/eight mutants pass.
- WSL restarted during desc10-plan-q1: nominal/two late faults are incomplete,
  six individual faults pass. Its144-file stopped cohort is hash-preserved;
  original files/receipts are unchanged. Fresh actual allocator/caller
  desc10-plan-q2 is live with a bounded eight-fault/raw/seal follower. Freeze
  consumed inputs; do not restart either producer from dated live notes below.
  Full512 nominal/eight native fault results remain pending. World/FIT978f9ddd
  passes offline board/218-package/78-module/22-object checks; unflashed. Prior
  FIT1aa17499/eight artifacts protected. Ghidra exports five functions with both
  geometry checks around readers. No hardware/subagents.
  All103 units and24 compiled guard cases pass again after access restoration.
  Independent stack audits add14 units: all166 normal functions/22 exact
  objects and29 exact DESC10 C functions. Individual frames are not full
  call-chain/assembly/physical stack bounds; see the checkpoint STACK.md.
  Read research/checkpoints/2026-10-15-npu-desc10-plan/REPORT.md.

## 2026-10-15 - Retained Raw Replay Migration In Progress

- The raw regression now requires a current actual allocator/caller receipt,
  not its rejected seeded lease. Full512 nominal/25606 original stores and all
  eight fault classes remain required. The earlier broader raw failure is not
  relabeled. New fault/CLI contracts are synthetic until native results pass.
- Strict restoration has no observer-source drift exceptions. Captures bind
  imported project replay modules and actual generated provider inputs before
  execution. Current focused units96 pass. A read-only ordered-store/lock trace
  is integrated but not yet fresh-native qualified.
- Actual allocator/caller retained-replay-q3 is live with frozen inputs and
  unchanged native guards/finite entry/checkpoint limits. Q1/Q2 were deliberately
  interrupted for capture/CLI fixes and are terminal non-passes. Never restart
  those from these notes. Eight retained native fault results remain pending.
- No firmware/image/hardware/subagent changes; FIT1aa17499 stays unflashed.
  Complete native/IRQ/worker/hot/lifecycle/physical/recovery/client scope stays
  open. Read research/checkpoints/2026-10-15-npu-retained-replay/REPORT.md.

## 2026-10-15 - Canonical PCIe/INODE Owners Qualified

- All older native jobs are terminal. Fresh82479 passed the actual-C caller
  prefix through DESC10 and RX PCIe; full_setup=false/prior_controls_skipped=true.
  Its exact530-file producing cohort is preserved locally before canonical edits.
- PCIe-tail/INODE source is now canonical and in the normal22-object archive.
  Exact normal-Os RV32 passes446/376 and2312/142 respectively; host checks,
  15 compiled mutants/sanitizers,42/120 original-store ABI cases and61 focused
  units pass. ABI guards remain explicit stubs, not native admission.
- Independent current-input raw builds repeat CODEeea4cfc6/DATA8fb7ca09,
  18 components/147 hooks. Source70 OpenWrt/5 LuCI and full world/FIT checks
  pass; new unflashed FIT1aa17499/provider1a001dc2. Prior69c88ce9 plus seven
  companions are protected. Archive members now must exactly match22 objects.
- Broader raw12172 is terminal1: six boot controls,2560 RX/1792 BA claims
  pass, then its later modeled TXDONE lease is rejected before descriptor writes.
  It lacks the current authenticated RX/API22/DESC10 prerequisites; exact first
  failed guard was not captured. Keep full512-store/fault coverage when moving
  that test onto the actual retained caller. Do not loosen guards or count a pass.
  Qualification status verifies299 current inputs/14 passing scoped receipts,
  but explicitly records the broader raw failure. All jobs are terminal.
  Normal promotion does not admit PCIe0/2/15 or INODE2/7.
  Next real native guard/history bindings, checked final IRQ/hot re-enable,
  full worker/packet/lifecycle/physical/drain/recovery/boot/client scope remains.
  See research/checkpoints/2026-10-15-npu-owner-promotion/REPORT.md.

## 2026-10-15 - Portable INODE Owner Tested

- Staged188-byte plan/4372-byte owner implements selector2's1030 effects
  (full4104-byte ICV clear) then selector7's six flags. Requires the finished
  PCIe tail and exact paired-CODE type109/base/metadata; prior validity is
  rechecked after reader callbacks. No IRQ/worker/release/reset authority.
- Host382 and exact normal-Os RV322312 calls/142 controls each/both HIF
  profiles, eight compiled host mutants and ASan/UBSan/leak pass. Original
  eleven-store trampolines add120 byte/frame/register cases with explicit guard
  stubs; outer callback returns1 even on inner failure. Six receipts/78 current
  hashes verify; latest checkpoint SHA starts d01fde28. No real guard admission.
  Fixed fixture intermediate-pointer UB. Individual RV32 frame4688 bytes is
  measured, not full call-chain/physical stack proof. Idempotent flags require
  real native site execution; matching readback alone is insufficient.
- Final IRQ is two host regmap writes, not more mailbox callbacks. Exact
  provider/wrapper/initializer C passes21 sanitized fixture cases;12 modeled
  IRQ errors are lost by the current void ABI and init returns0. Seven earlier
  initializer errors propagate correctly. No source fix/hardware verdict yet;
  include hot poll re-enable in the next contract. See checkpoint NEXT_IRQ.md.
- Single-effect RV32 run47692 is terminal0; only older fresh82479/PID3199667
  remains live. Its DESC10 now passes25606 effects/3072 claims and exact856064
  protected bytes;225 inputs/44 files independently recheck. PCIe is pending.
  Earlier fixture/batch runs hit finite entry limits or were
  intentionally stopped for the fixture fix; no pass. Single-effect driver
  preserves500M/30-second entry limits and the full sequence/control set.
  Freeze their inputs; integrate staged PCIe/INODE normally after terminal.
  Full native/store/IRQ/worker/hot/lifecycle/physical/recovery/client goal stays
  open. Read research/checkpoints/2026-10-15-npu-inode-owner/REPORT.md.

## 2026-10-14 - Remaining PCIe Portable Owner Tested

- Staged PCIe0/2/15 owner retains all nine ordered possible effects across
  three commands, derives HIF profile from the independent finished TX owner
  and requires completed RX PCIe/DESC10 owners and live final memory. Plan180/
  owner256 have no reset/retirement API. Fixed a reproduced first-begin reader
  mutation gap by snapshotting prior owners/plan before callbacks.
- Current host and exact normal-Os RV32 each pass446 calls/376 controls across
  both HIF profiles; seven compiled host mutants and ASan/UBSan/leak pass.
  Checkpoint verifies51 inputs/three receipts. This is portable/logical memory,
  not original-store/native-caller or hardware proof. Source is temporarily in
  .local/npu-pcie-tail-owner-20261014 while earlier replay inputs remain frozen.
- Staged nine-store assembly plus original callback passes42 ABI cases with
  explicit guard stubs; original4/6-byte boundaries/opcodes, AUIPC relocation
  and frame-specific unwinds match. Original INODE lookup109 returns fixed
  3e8bc470/no writes; four nominal/1036 pre-store interruption cases pass.
  Not real guard/admission or hardware proof. Exact NEXT_NATIVE.md is in the
  pcie-tail-owner checkpoint. Three scopes cross-check57 current input hashes.
- Earlier parallel24394 is terminal0: all30 native PCIe fault cases and267
  current input hashes pass the checked aggregate. Redundant serial30156 was
  intentionally interrupted afterward (terminal1), not counted as a pass.
  Fresh82479/PID3199667 is still live at the actual pre-DESC10 prefix after
  all six API21 phases/53260 effects. Promote the qualified owner after
  terminal, then bind all nine original sites and authenticated ordering.
  Full INODE/IRQ/worker/hot/lifecycle/physical/recovery/client goal stays open.
  No hardware/subagents/image change. Read the new pcie-tail-owner REPORT.md.

## 2026-10-14 - PCIe Diagnostic And World Passed; Fresh Sender Live

- Restored actual pre-PCIe nominal is terminal0: original guarded store/owner
  finishes1/1/1,3072 claims/RXsteps3 and all856064 bytes match only pointer/
  sequence updates. Real reader checkpoint preserves native guards/finite
  instruction/chunk bounds;4 observer units pass. Not fresh full setup proof.
- World q2 and exact FIT verification pass20 RV32 objects/raw18-147/218 packages/
  78 module ABIs/Gemtek W1700K. New unflashed FIT69c88ce9/provider1a001dc2;
  prior82b1563a plus seven companions are hash-protected. Missing three exported
  headers are fixed;6 include-closure units and source67 OpenWrt/5 LuCI pass.
  REA inspects exact compiled sender/cold routing guards; session closed.
- Freeze live inputs: serial controls30156, fixed8-group controls24394 and fresh
  sender82479 remain live. Fresh q2 stopped on reset's10-second host wall budget;
  q3 records a supported60-second host profile, unchanged3M instruction and
  finite checkpoint/state limits. It passed reset/15-record enrollment.
  No complete matrix/fresh sender or physical verdict yet. Integrate qualified
  helpers/observer after terminal, check final input closure and publish main.
  Full remaining setup/hot/lifecycle/physical/recovery/client goal stays active.
  Report/NEXT_SETUP: research/checkpoints/2026-10-14-npu-rx-pcie-bind/.

## 2026-10-14 - Native DESC10 Passed; PCIe Observation Open

- Raw18 components/147 hooks/private388 now binds the final selector10/API0
  pointer store with retained completed-DESC10/prior owners and original lock/
  IRQ/neighbor/readback/frame guards. Same-input pairs/all18 image groups,
  wire1436/45 mutants, provider609/nine, loader60/eight and28 units pass.
- Actual allocator/caller q1 is terminal1: DESC10 itself passes25606 effects/
  512 added claims/total3072/RXsteps2/ready1 and all856064 protected bytes.
  Subsequent PCIe execution reaches an instruction observation boundary inside
  DMA-plan checking before the pointer owner begins; no PCIe acceptance yet.
- Current-input restored-prefix DESC10 controls31 and early API0/history denials4
  pass without input-drift exceptions. Added read-only reader-checkpoint helper
  passes4 units; PCIe nominal/control diagnostics are live (48837/30156).
  Keep consumed inputs frozen. Ghidra exports15 functions with explicit W1700K
  language and actual raw continuation mapped; DWARF/type warnings remain.
- Canonical observer integration, fresh full sender, late/native mutants,
  export/lock/world/provider/FIT/mainline and full setup/hot/lifecycle/physical/
  recovery/boot/client gates remain. FIT82b1563a remains unchanged/unflashed.
  No hardware/subagents. Read research/checkpoints/2026-10-14-npu-rx-pcie-bind/REPORT.md.

## 2026-10-14 - Portable RX PCIe Owner Tested

- Normal archive20 objects now includes136-byte RX PCIe plan/168-byte one-shot
  owner. Final DESC10 memory helper checks20998 final cells with a bounded
  reader and live prior owners before/after. Compiled host-C/RV32 passes226
  calls/213 controls/eight mutants/sanitizers; DESC10 regression3656/3541/nine
  and24 observer/transaction units pass. Two raw17/145/private388 builds repeat
  (CODEab78628b/DATA6bc539e7), all17 image groups and loader60/eight pass.
- This is portable ownership/final memory inspection, not native PCIe admission.
  No pointer owner instance/store binding or full three-command sender pass yet.
  Server/client/provider API0 ordering remains closed. Next bind completed
  DESC10/prior owners and original8400ba88 under held BAR/session/typed spans/
  IRQ/neighbor/ABI guards, then extend ordering and run fresh complete native.
- Six receipt input maps/binaries hash-check228 current files. No live jobs,
  hardware, subagents, export/world/publish or new image. Full setup/lifecycle/
  physical/recovery/client scope stays active; FIT82b1563a remains unflashed.
  Read research/checkpoints/2026-10-14-npu-rx-pcie-owner/REPORT.md.

## 2026-10-14 - DESC10 Protected Memory Reconciled

- Q7 native returned error0/all25606 effects/512 new claims/total3072/
  RXsteps2/ready1, but its old whole-memory oracle failed. Same-image prefix
  replay is now terminal0: the only differing byte is session sequence56->57
  at3e906390. A request-derived exact4-byte protocol update reconciles all
  856064 protected bytes across five regions, without exclusions/post-state copy.
- Integrated the corrected transaction oracle before guest transport execution
  and retained actual/expected images in the main harness. Twenty-four units
  pass. Typed lookup57/three mutants, width18/one, real-symbol30, native39 and
  raw17/145/all17 repeat groups remain their qualified prior scopes. Old producer
  input is archived locally; new harness has not had a fresh full native run.
- No native verdict is upgraded to physical/full setup. Add owned selector10/
  API0 PCIe tail, remaining setup/hot/physical/drain/recovery/client gates and
  fresh native/current-input/export/world/image validation. No live jobs, source
  export/publish or hardware action; full goal active. Read local RESUME_Q7.md.

## 2026-10-14 - Native DESC10 Integration In Progress

- Working-tree native composition now builds17 components/145 hooks and binds
  DESC10 to the one-shot RX/PKT/store owner. Private cold state remains388 bytes.
  The17/145 pair is compiled, not yet a passing complete native setup or world.
- Original type0x107 lookup returns fixed L2 pointer0x3e8adc70 without writes;
  allocator metadata stays unchanged. It is not an extra dynamic heap allocation.
  All20 selected store instructions match original/raw bytes, including valid
  metadata storesb45e/b46a and alternate copiesb530/b53c at the same two fields.
  The corrected portable object passes3656 calls/3541 controls/nine mutants and
  sanitizers. This supersedes the earlier portable fixture's pool assumption.
- First actual allocator/caller replay reached API22, then stopped inside prior
  TX-buffer verification before DESC10 completed. The observer now pauses at
  both real recipe entries and distinguishes callback count from checkpoint
  budget; nine observer/three read-only capture units pass. Q3 reached a real
  rejection with2560 claims: valid-count metadata stores had not been hooked,
  so their writes were untracked and claim ordering correctly rejected. Both
  paths are now bound. Wire1378/40 mutants includes58 DESC10 cases; loader60/eight
  and16 image groups plus the new branch test pass (repeat group still skipped).
  Q4 ended after3074 stores/512 claims: a signed halfword register needed
  effective-width normalization. That boundary now passes18 cases/one mutant.
  Q5 ended at the old boot-only TX-clear observer after7170 published stores,
  not a native rejection. A separate pending-owner/store-site observation keeps
  all inherited access checks and the boot counter;15 observer/three capture
  units pass. Captured-prefix replay exposed a wrong guard-symbol owner: use
  allocator_rv, not rv. Actual raw-loaded symbol observation passes30 cases.
  Q6 and the incomplete Q3 negative suite were intentionally stopped for fixes,
  not timeouts/native verdicts. Exact typed8a/12/1d allocator starts/definitions
  now gate all effects; the actual C lookup passes57 cases/three mutants.
  CODEaff56189/DATA03c504e5 repeat identically with all17 image groups. Fresh Q7
  is terminal1: native error0/25606 effects/512 new claims/total3072/RXsteps2/
  ready1, but whole protected-memory oracle comparison failed. No nominal pass.
  A same-prefix byte-diff diagnostic is live; keep its consumed inputs frozen.
  The actual Q7 prefix feeds31
  passing native early/first-two-store fault controls, with245 current input
  hashes and saved-register checks before CPU restoration. Restores are fixtures;
  eight additional malformed-count/unmarked/seeded-lease denials pass without
  constructor effects or changed packet prefix. These are39 native controls,
  later SKB/readiness/native-mutant controls remain. Freeze consumed source/tests;
  never interpret skipped controls or compiled hooks as native acceptance.
- Source export, native fault/mutation coverage, current-input closure and world
  remain pending. FIT82b1563a/providerf163e26e are unchanged and unflashed. Full
  PCIe/INODE/IRQ/owners/hot/physical/drain/recovery/boot/client scope stays open.
  No hardware or subagents. Live evidence: .local/npu-desc10-native-20261014/.

## 2026-10-14 - Portable DESC10 Owner Tested

- `cold-txdone.c/.h` now belongs to the normal19-object portable Makefile.
  Its13512-byte one-shot state requires a finished matching RX-event owner,
  retains the2560-claim PKT bitmap and owns512 additional claims plus25606
  ordered metadata/descriptor/SKB/readiness effects. No reset or retirement API.
- Exact normal-Os object:3656 compared host-C/RV32 entry calls,3541 controls,
  eight mutants and ASan/UBSan/leak pass. Whole logical memory and ordered
  address/width/value events match an independent oracle at phase boundaries.
  Original DESC10 instructions and allocator/caller/session/locks are not
  exercised by this portable fixture. Five receipts/210 current input hashes
  verify; source69 and all16 image groups including independent repeats pass.
- Raw CODEc6548555/DATAe0495a5f and16/126/private388 remain unchanged. The
  portable owner is not yet instantiated or invoked by the native dispatcher;
  authenticated DESC10 remains denied. No world/provider/Ghidra/full-native
  rerun or hardware action is claimed. FIT82b1563a remains unflashed.
- Earlier three provider line-length warnings and the14-record stdout label
  are corrected. The cleanup delta matches the sealed prior source on exact
  reversal and passes strict checkpatch without signoff checks. Read
  `research/checkpoints/2026-10-14-npu-desc10-owner/NEXT_DESC10.md` to bind the
  original constructor next. Keep the full NPU/physical/client goal active;
  freeze consumed sources/tests during replay. No subagents or hardware.

## 2026-10-13 - RX Enrollment/API22 Native Replay Passed

- Actual RX allocation enrolls eight mailbox handles plus the retained RX ring
  before CPU/DMA outputs. TX allocation appends six handles. Selector0/API22
  uses a152-byte owner and original wrapper/store hooks, exact earlier owners/
  effects, original lock18, masked IRQs and metadata-neighbor/readback checks.
- Raw16/126/archive18/private388, world/source69/Ghidra61 (43 named functions)/
  REA/FIT218+78 and independent identical raw builds/all16 groups pass.
  Owner487/211/seven, actual C166/seven, wire1320/34, seven regressions and21
  units pass. Eleven receipts/290 current input hashes verify.
- Session47388/PID673535 is terminal0: actual allocator/caller/original RV32
  passes15 records, six API21 phases/53260 effects/76 controls and API22/30
  native controls, including retained1/0 and1/1 late failures. Earlier q1/q2
  runs were intentionally interrupted for harness corrections, not timeouts or
  API22 verdicts. Checkpatch has three line-length warnings. Native final stdout
  has a legacy14-record label; JSON/early trace correctly report15.
  Freeze consumed sources/tests during future replays and derive snapshot sizes
  from ELF. Fix the style/diagnostic cleanup before the next proof cycle.
- FIT82b1563a is unflashed; f185a731 and seven companions are hash-protected.
  Next authenticated DESC10 must share PKT/TXDONE/SKB ownership rather than
  recreate a test-written lease. Remaining PCIe/INODE/IRQ/owners/hot/physical/
  recovery/boot/client gates keep the full goal active. No hardware or subagents.
  Scope: `research/checkpoints/2026-10-13-npu-rx-event-bind/REPORT.md`.

## 2026-10-13 - Retained RX-Event Backing

- Canonical queue allocation retains the actual 512x16 RX-event descriptor ring
  before queue address publication. Only unmarked EOPNOTSUPP uses managed
  fallback. RX serial/record rechecks and RX/TX overlap guards preserve the held
  lifetime; failures/detach never authorize release.
- C115/seven mutants/sanitizers, source68, strict367-line delta, world,
  Ghidra60/REA and FIT218+78 pass. Latest unflashed FITf185a731; prior9d1fa30d
  plus seven companions are preserved. Raw CODE/DATA remain identical.
- Current native replay passes: one RX/six TX allocations, all six API21 phases/
  53260 effects/76 controls and14 native mailbox/TX records. RX native enrollment
  is still absent. Eight receipts/266 current input hashes verify.
  Freeze consumed sources/tests. RX-event native enrollment/API22/DESC10 and
  remaining full setup/lifecycle/physical/client gates remain open. API0 original
  64 observations/nine index sequences expose immediate host writes and retained
  partial five-pointer resets. No hardware action or subagents.
  Scope: `research/checkpoints/2026-10-13-npu-rx-event-lifetime/REPORT.md`.

## 2026-10-13 - Original API21 Callbacks Bound

- Continue the actual six-callback/53260-store native binding, not a blanket
  API21 whitelist. Raw15/124, private368 and retained213200-byte CODE owner are
  integrated into canonical export and the normal world/image.
- Wire1250/29, portable owner106640/80/seven and identical raw builds/all16 image
  groups pass. Actual allocator/caller/raw-native covers all six phases/53260
  effects/76 controls and46 lease pairs; world/Ghidra59/source68/FIT218+78 pass.
  Full current-input raw3072 PKT/1792 BA/six boot/eight TXDONE controls pass;
  later TXDONE lease/ring metadata remain modeled, not full strict setup.
  Never treat an output directory as a receipt. Dependency hashes are recorded;
  extend neighbor/native-mutant/HIF2 and wider native-fault coverage.
- Snapshot restores must include the new84090000/40000 binding window and the
  complete ELF-derived cold state. API21 uses bounded recipe-entry checkpoints;
  sparse CSR observation does not bypass native guards or original instructions.
- Latest unflashed FIT9d1fa30d;69257a6b/6c76e14a plus seven companions each are
  preserved. API22 original64 vectors accept zero/unaligned values after aliasing;
  next retain RX-event queue lifetime and wire owned API22/DESC10/PCIe setup.
  See NEXT_RX_EVENT.md. No physical proof or hardware action.
  Freeze consumed sources/tests; no subagents. Full goal stays open. Scope:
  `research/checkpoints/2026-10-13-npu-api21-native/REPORT.md`.

## 2026-10-13 - Native TX Enrollment Qualified

- Actual allocator enrolls eight mailbox/six TX records before output under the
  same boot/nonce/held session. Wire80 stays fixed; private360 pins pending and
  accepted BOOT/BAR/record plans. Lost replies retain both prefixes/resources.
- Packaged owner106640 calls/53260 stores/80 controls/seven mutants, wire1203/25,
  lifetime113/nine, native14/forty lease pairs, provider609/nine,21 units and
  source68/nested/style/world/Ghidra58/FIT218+78 pass. Unflashed FIT69257a6b;
  prior6efaa878/ffbd4344 and companions are protected. No hardware action.
- API21 stays denied. The213200-byte portable owner is not instantiated/bound
  to original stores. Next pin typed tables, metadata neighbors/internal/L2
  spans, exact TXPKT, prior owners and original lock/IRQ/session, preserving
  actual GET/SET interleaving. Remaining setup/hot/physical/recovery/clients open.
  Do not infer physical DDR/SRAM alias equivalence/independence from low bits.
- Freeze consumed sources during replays/builds; derive private snapshot size
  from ELF, not historical120. Use existing WSL Python libraries and LLVM21
  linker; Linux Ghidra temporary project paths must not have dotted elements.
  No subagents. Scope: `research/checkpoints/2026-10-13-npu-tx-enrollment/REPORT.md`.

## 2026-10-13 - Host TX Lifetime Qualified

- Checked allocation owns six coherent CPU/DMA/size records and a pinned PCI
  endpoint in the exposed provider lifetime. The DMA device is the NPU device,
  not the endpoint. Full geometry/alias/overlap and fresh STATUS/identity checks
  precede output; partial errors and detach retain all exposed resources.
- Actual C76/seven, provider C609/nine with BAR272/seven, native allocation/STATUS,
  21 nonzero unit tests, strict checkpatch/source/world/Ghidra59/FIT218+78 pass.
  Current unflashed FIT `6efaa878...`; older `123e3084...`, `3951dc7c...` and
  seven companions each are preserved. Raw CODE/DATA stay byte-identical.
- Eight original API21 helper cases verify 512 records per band with 4/4/4/1
  stores and untouched bytes13-15. Missing static tables clear counters and
  publish a null pointer before faulting. This is reverse-engineered/model proof,
  not native API21 admission, physical ownership or complete setup.
- Next enroll the host DMA records into the native session and implement exact
  API21 internal/L2/table/metadata ownership with actual GET/SET interleaving.
  Complete other setup/owners/hot/physical/recovery/client gates; full goal open.
- Freeze consumed sources/tests during replay/build. Use explicit immutable
  `--header` for provider replay when world may replace the build-tree header.
  Reject zero-test discovery and any final input drift. Continue this goal solo
  unless the user changes the no-more-subagents instruction; use Jev normally.
  Evidence: `research/checkpoints/2026-10-13-npu-host-tx-lifetime/REPORT.md`.

## 2026-10-11 - Retained Descriptor GETs

- Descriptor source adds the16th archive object and14th raw component/77 hooks.
  The6188-byte one-shot state retains eight ordered GETs, arbitrary TX preimages
  and1536 status reservations/publications under original lock18 and pinned
  allocator/slot/session/earlier-owner state. No rollback/reset/retirement API.
- Wire80 stays unchanged; private cold history120 and Linux cached getter order/
  arena reject fallback0x457 and pointer substitution before caller output.
  Core5732/1592/five and wire657/23 pass. All nine exact-input native cases/HIF2,
  35 indication/28 TX/28 descriptor controls, raw/world/source/Ghidra54/image
  checks pass. TX5/7 faults retain1/0 and513/512 committed/published status words.
  Invocation-local cleanup fixes the preowned-lock release bug in all three
  bindings. Freeze consumed firmware and test files during replay/builds.
- Actual RX caller completes six endpoint writes. Actual TX caller reaches GET5
  then denied API21; later GET7 is diagnostic. Next retain host managed TX DMA
  buffers before API21 exposure, then remaining strict setup/lifecycle/physical/
  clients. API21 types0x100/0x101 are static L2 lookups, not dynamic allocations;
  guard exact table/record/metadata spans and the existing TXPKT prerequisite.
  Current offline-qualified FIT3951dc7c is unflashed; old4da01cfe/R1 preserved.
  No hardware action. Full goal open.
  Evidence: `research/checkpoints/2026-10-10-npu-cold-descriptor/REPORT.md`.

## 2026-10-10 - Retained TX0/TX2 And Token Prefix

- The15th archive object owns11 ordered original metadata/index/CSR/token
  writes in80-byte one-shot state. Original lock18 pins the unique type1 arena,
  allocator count/used, BAR, identity/sequence and full RX/page/indication state.
  Faults retain claims/progress/outer lease; no rollback/reset/retirement API.
- API19 selectors0/2 and API33 selector0 now use the authenticated cold lane.
  Wire80/private history104 stay unchanged. Host offsets are BAR0+d4420,
  d4450/d8450 with HIF2 full-span check, then token8192. The separate13th raw
  component adds11 hooks, for74; canonical Linux component mappings stay13.
- Exact-world525 calls/205 controls/six mutants, wire459/16, nominal/HIF2 with
  27 TX/34 indication controls and full raw3,072 PKT/1,792 BA pass. All seven
  native cases pass; register/token faults retain4/3 and11/10 progress. World,
  Ghidra54/source66+nested12/assembly/FIT218+78 pass; FIT `4da01cfe...` unflashed.
- Initial raw setup now uses actual cold-client C, never test active/init writes.
  Later TXDONE lease/ring metadata stay modeled. Next denied GET0/API4 has mixed
  selector effects: RX pointer lookup, TX5/7 descriptor-status stores, and an
  unsupported0x457 success sentinel. Do not blindly whitelist all getters.
- Continue remaining strict host/INODE/TXDONE/final IRQ setup, owners/hot/postgate,
  physical exclusion/backing/coherency/drains/retirement/recovery and clients.
  No hardware action. Full goal stays open. Scope/next source trace:
  `research/checkpoints/2026-10-10-npu-cold-tx/REPORT.md` and `NEXT_SETUP_TRACE.md`.

## 2026-10-10 - Retained Indication And ACK Prefix

- First authenticated DESC8 initializes the one-shot 1,536-record owner under
  original allocator lock18. It pins the unique type1 arena/type6 span, reserves
  before original read/store and rechecks held state, metadata and readback.
  Faults retain claims/reservation/outer lease; no reset/retirement API exists.
- Private cold history is104 bytes with five RX/page count snapshots. Full
  profile precedes indication setup. The80-byte wire and existing nonce/identity
  remain unchanged. API19 selector3 only records ACK metadata; selectors0/2
  program TX registers and remain unsupported in the strict lane.
- Exact-object12,322 calls/3,095 controls/seven mutants, nominal actual-C/native
  setup and34 native negative controls pass. Snapshot restores are test-only
  and include private CODE history, not a production reset or active grant.
- World/Ghidra54/source66+nested12/components13/assembly/image218+78 pass.
  Latest FIT `8dd1f2f4...`; old `5c94b20d...`/R1 preserved. No hardware action.
  Driver delta now passes strict checkpatch with zero errors/warnings/checks.
- Continue strict TX0/TX2 programming and remaining TX/INODE/TXDONE setup,
  owners/workers/hot/postgate, independent physical backing/exclusion/coherency,
  drains/retirement/recovery and clients. Later/full raw TXDONE still uses a
  modeled direct lease. Full goal stays open. Scope and sealed receipts:
  `research/checkpoints/2026-10-10-npu-cold-indication/REPORT.md`.

## 2026-10-10 - Session-Bound BAR And Page Prefix

- Real mt7996 BAR0 start/length binds through two metadata commands before mt76
  publishes NPU/PPE pointers. Native64-byte cold owner checks exact window,
  bootstrap overlap, completed prefix and existing identity/sequence/held epoch.
  Page5/6/7 addresses must be BAR0+0xd45a0/b0/c0; limits remain256/512/1024.
- Authenticated first DESC5 initializes BA ownership. Actual txrx sender through
  the provider/native raw pair retains2,560 PKT/1,792 BA claims without test
  active/init writes. It stops next at unsupported selector8, not full setup.
- Provider C545/nine and cold C397/eleven cases/mutants plus six BAR mutants,
  54-function Ghidra, world,66 top-level/12 nested file replay,13 components,
  assembly/FIT/218-package/78-module checks pass. FIT `5c94b20d...`; preceding
  `7622acf9...`/R1 preserved. No flash/reset/router contact.
- Continue indication/INODE/TXDONE strict setup and remaining owners/hot/postgate,
  independent physical exclusion/backing/coherency, drains/retirement/recovery
  and clients. BAR geometry/lease/parking is not physical authority. Full goal
  stays open. Scope: `research/checkpoints/2026-10-10-npu-cold-pages-wire/REPORT.md`.

## 2026-10-10 - Session-Bound Initial Cold Commands

- Distinct80-byte NCS2/NCR2 commands reuse the provider boot/nonce and existing
  V2 sequence. Native begin checks the held epoch, bootstrap, parked workers,
  deferred IRQs and completed history before granting a software callback lease.
  Native failure retains active/inflight/claims; no resource retirement exists.
- Real provider ops route post-BIND version, port type2 and checked RX0/RX2 DESC
  commands to that lane. Early probe version and unmarked/raw callbacks retain
  their dispatch. Authenticated first RX0 initializes packet ownership itself;
  native replay uses no test-written active lease or packet-init call.
- Cold C229/eight and initial-session C279/nine cases/mutants, native full RX
  prefix/partial-fault controls,53-function packaged-provider Ghidra, full world,
  66-file source replay and offline image/module checks pass. FIT `7622acf9...`;
  prior `6a7dc41e...`/R1 preserved. No flash or hardware contact.
- Continue later strict PCIe/page/INODE/TXDONE setup, other owners/hot/postgate,
  independent physical containment/backing/coherency, drains/retirement/recovery
  and clients. Do not describe the initial RX prefix as full setup or the
  software lease as physical drain authority. Full objective stays open.
  Evidence: `research/checkpoints/2026-10-10-npu-cold-wire/REPORT.md`.

## 2026-10-10 - Provider-Owned Initial Session

- The checked provider owns one executor/setup attempt under its own mutex.
  DISCOVER must match the loader identity before the six existing commands;
  BIND, STOP and bounded STATUS require initial epoch1 held/parked, never release
  or arm. Failure closes CPU control with the first error; reattach cannot reset
  it. Exposed DMA lifetime stays retained. Unmarked source dispatch is preserved.
- Canonical client objects now link into `airoha_npu.ko`, not mt76. A small
  translation-unit wrapper preserves the driver path/module name. The exact
  component mapping, cumulative patches and image ownership verifier are updated.
- Actual-C279/nine mutants, two Linux-to-raw-RV32 session cases,48-function
  packaged-module Ghidra and full raw ownership regression pass. World,63-file
  replay,16 assembly groups and FIT/218-package/78-module checks pass. Latest FIT
  `6a7dc41e...`; prior `b0400eaa...`/R1 preserved. No flash or hardware contact.
- Continue strict cold RX/TXDONE transport/callers, actual prior-user exclusion,
  exclusive backing/coherency, other owners/hot/postgate, physical retirement/
  recovery and clients. CPU/wire enrollment is not cold-containment proof, and
  this held handshake does not authorize DMA cleanup/rearm. Full goal stays open.
  Evidence: `research/checkpoints/2026-10-10-npu-provider-session/REPORT.md`.

## 2026-10-10 - Boot Launch Error Closure

- Actual provider now checks14 existing boot writes, latches one launch attempt,
  propagates the first error without retry/reset/free, and requires expected
  checked-profile version transport before `platform_set_drvdata`. Generic
  unmarked version reporting remains diagnostic; common write errors reject.
- Actual-C248/ten boot cases/mutants and265 probe cases/three mutants plus one
  original-source false-success control pass. Native version before DISCOVER
  succeeds from actual C-published DATA, then bootstrap parks eight harts.
- Current6.18.52 clock/reset source reconstructs exactly,147 IDs/23,088 host
  and5,007 actual AArch64 cases pass. The NPU DTS still has no reset binding;
  mapping/readback/version do not certify independent DMA coverage or retirement.
- World,62-file replay,16 assembly groups and FIT/218-package/78-module checks
  pass. FIT `b0400eaa...`; old `05ca2802...`/R1 preserved. No flash/router contact.
  Continue real cold exclusion/backing/coherency and strict host setup, remaining
  owners/hot/postgate and physical recovery/clients. Full objective stays open.
  Evidence: `research/checkpoints/2026-10-10-npu-boot-launch/REPORT.md`.

## 2026-10-10 - Checked Pair Loader And Packaging

- The main world build packages checked MT7996 CODE/DATA plus manifest; all
  three staged files are package dependencies. An unchanged-source incremental
  build refreshes the manifest correctly. Other firmware profiles are unchanged.
- Actual provider C validates ABI/digests/zero slots before copies, obtains a
  nonzero runtime random identity, publishes plan/identity and checks readback.
  A pre-copy exposure latch retains all coherent mailboxes/device/module lifetime
  after ambiguous failure or detach. Same-instance reload and retained-device
  rebind deny; no physical retirement/reclaim or hot-rearm API exists yet.
- Actual-C 60/eight parser/publication mutants, 13/four lease and 205/two probe
  cases/mutants pass, alongside 310/nine request, 273/159 memory, nine memory
  mutants, 6,174 retry and 44 V2 cases. Native boot consumes C-published bytes
  without synthetic metadata writes; eight harts park, strict setup still denies.
  Full raw replay retains 3,072 PKT/1,792 BA claims with failure controls.
- Sixteen assembly groups, 62-file replay, 13/four builder/verifier unit tests,
  complete world and FIT/218-package/78-module checks pass. Latest FIT
  `05ca2802...`; prior images/R1 are preserved. No flash/router/hardware contact.
- Continue physical cold containment/reservation/coherency, strict real Linux
  setup callers, remaining owners/hot/postgate and drains/recovery/clients.
  Do not treat the cold-format flag, strong-RNG API, readback or retained buffers
  as physical proof. The module is intentionally pinned after exposure.
  Evidence: `research/checkpoints/2026-10-10-npu-loader-publish/REPORT.md`.

## 2026-10-10 - Provider Native Request Plan

- Canonical MT7996 loader now validates/snapshots the actual coherent core0
  request before either firmware acquisition/copy. Private48-byte native plan
  requires full BA and fixed CODE placement; generic/optional-BA legacy behavior
  is preserved. Failed loads clear private metadata, not native owned resources.
- Actual C passes308 request cases/nine mutants, memory/retry/V2 and exact-pair
  regressions. Raw native bootstrap uses the emitted dynamic-address plan and
  rejects the old fixture address; all eight harts park, strict full setup is
  still denied. Publication/identity/backing in that test remain modeled.
- Full world,15 assembly groups,60-file replay, four source-verifier/eight
  build-runner/offline image checks pass. FIT now `8efb19fb...`; packaged vendor
  pair/core unchanged, previous `230e03a7...` FIT preserved. No flash/hardware.
- Private `native_plan_ready` is geometry only, not SRAM publication or physical
  containment. Continue real cold-provider/identity/publication/retention and
  paired packaging, strict callers and full lifecycle/physical/client gates.
  Scope and exact receipts: `research/checkpoints/2026-10-10-npu-provider-plan/`.

## 2026-10-10 - Paired Raw NPU Build

- `make -C firmware/npu pair` now assembles the complete checked raw CODE/DATA
  in fresh ignored storage, with61 hooks, explicit NOBITS and unprovisioned
  loader plan/session/identity. `pair-check` validates the assembly/readback.
- Two builds are byte-identical;15 assembly groups pass. Full raw-only native
  replay passes3,072 PKT/1,792 BA claims, all-hart parking, six loader/eight
  TXDONE controls. Actual current provider C passes273 matrix/seven exact-pair
  cases with sanitizers. Eight build-runner/offline image checks pass.
- This artifact is not packaged/flashed. Native execution still requires
  modeled provider publication, backing/grants/IRQ scheduling and a held direct
  lease. Unprovisioned boot faults before IRQ setup. Do not bake fixture values
  into DATA or infer physical containment from copy success/aperture fit.
- Continue real cold-provider/storage/identity-plan publication and packaging,
  strict Linux setup callers, other owners/hot/postgate and physical recovery/
  clients. Scope, reproduction and sealed proof:
  `research/checkpoints/2026-10-10-npu-raw-pair/REPORT.md`.

## 2026-10-10 - Shared RX And TXDONE Packet Ownership

- The 61-site native binding now routes TXDONE through the same retained PKT
  state as RX0/RX2. Publication rechecks immutable plan, head/count history and
  bitmap population. SKB failure retains prior claims; no recycle/reset is added.
- Full RX prefix plus TXDONE512 retains 3,072 PKT claims. Exact native RAM/SKB,
  packet state, ordered locks and readiness-last checks pass; 25 controls and
  six symbol-restored mutants pass. Full RX/page regression passes 50 controls/
  six mutants and 1,792 independent BA claims. Offline image/eight runner checks
  pass; core/archive/provider/vendor/FIT remain unchanged. No fresh world build.
- Real installation is still absent. The current loader copies the vendor pair;
  test session/identity offsets0x6380/0x63a0 are beyond its 3,084-byte DATA image.
  Do not treat range fit as approved storage/containment or the archive as CODE.
- Continue paired raw-image/real-loader storage/identity and Linux strict caller
  wiring, other owners/hot lifecycle, postgate and physical drain/recovery/clients.
  Evidence and exact boundary: `research/checkpoints/2026-10-10-npu-cold-txdone/`.

## 2026-10-10 - Checked Cold RX Packet Ownership

- The normal archive now has a distinct 16,384-ID/2,048-byte packet profile;
  ownership state is 2,076 bytes. It shares the retained-claim algorithm without
  changing the page ABI or compiled page object. No release/recycle API exists.
- Selected original RX0/RX2 and lock28 instructions compose with claim, immutable
  table identity, release and readiness guards: 61 sites, 2,560 packet claims,
  50 controls and six initialized mutants pass. Separate BA replay adds 1,792
  claims without changing packet state. Unrelated getter routing is preserved.
- Exact packet-object replay passes 8,243 calls/546 controls/five mutants with
  sanitizers; page-core and RX-statistics regressions, full world, 60-file source
  replay, eight build-runner tests and offline image checks pass. Twelve objects;
  FIT remains `230e03a7...`. No blob installation, flash or hardware change.
- Full ownership for other packet users, real loader/strict setup, hot lifecycle,
  workers/physical backing/coherency/drains/recovery and clients remain open.
  Evidence: `research/checkpoints/2026-10-10-npu-cold-packet/REPORT.md`.

## 2026-10-10 - Checked RX Statistics

- RX0/type10 and RX2/type9 now use the actual checked allocator in the held
  cold callback context, including an already-bound V2 coordinator nonce.
  Guarded native clear/dispatcher/readiness and outer failure propagation pass
  in 60-site composition: 2,560 descriptors, 26 controls and six mutants.
- Allocation metadata and exact 1,000-byte clears/descriptor bytes are verified;
  late faults retain committed records and leases. Startup/page/postgate and
  unrelated-getter regressions pass. No shared core/kernel/image or hardware change.
- Strict setup, real loader, packet-ID ownership/hot lifecycle and physical
  drain/recovery/client acceptance remain open. Evidence:
  `research/checkpoints/2026-10-10-npu-rx-stats/REPORT.md`.

## 2026-10-10 - Native Cold Page Composition

- The shared core now validates/publishes a native queue snapshot while retaining
  committed claims on failure. DESC5/6/7 compose with original initializer code
  in a 54-site native replay: 1,792 claims, 48 controls and six binding mutants
  pass. Partial/late failures deny outer success and readiness, retaining leases.
- Exact built RV32/core sanitizer replay, original page-ring regression, full
  world build, 60-file replay and offline image checks pass. FIT stays `230e03a7...`.
- This wires selected callers in native instruction emulation, not the vendor
  blob or physical loader. Strict setup, hot lifecycle, workers/drains/recovery
  and real-client acceptance remain open. No flash or hardware changes.
  Evidence: `research/checkpoints/2026-10-10-npu-cold-page-native/REPORT.md`.

## 2026-10-01 - Mainline Follow-Up

- The user explicitly authorized merging all outstanding source work into `main`.
  This supersedes the cold-page checkpoint's earlier draft-PR-only restriction;
  it does not authorize a flash or establish hardware acceptance.
- The final test runner supports `--core-object` for exact built RV32 replay.
  Fresh source and archive-member runs each pass 5,702 calls, 294 controls and
  ten mutants with address/undefined/leak sanitizers. Eight build-runner tests
  and unchanged-FIT offline image verification pass. Final receipts and scope:
  `research/checkpoints/2026-10-01-npu-cold-page/REPORT.md`.
- Keep ignored builds, private inputs and protected backups local. Native caller
  integration, physical ownership/drains and actual clients remain open.

## 2026-10-01 - Checked Cold Page Ownership Core

- Preserved pending work after remote-verified `eabfedb`; completed the shared
  cold-page ownership core and added cursor/claim-history consistency validation.
  Claims and late-fault committed resources remain retained; no recycle/reset
  reclamation is implemented. The core is compiled, not wired into native callers.
- 5,702 host/RV32 calls, 294 controls, ten mutants and address/undefined/leak
  sanitizers pass. Existing 273/165 loader-memory, nine mutants, 6,174 retry and
  44 V2 cases pass. Eleven RV32 components and offline image checks pass; unchanged
  FIT `230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe`.
- Corrected native 50-hook caller replay shows direct RX0/RX2 statistics callers
  use original unchecked type-10/type-9 allocator fallback, adding two records.
  Strict setup remains denied; an earlier expected-hold assertion was incorrect.
- TypeSafe receipts retain the five initial semantic checks and three approved
  claim checks; exact models/probabilities are recorded in the report.
  Full native ownership/error/publication, strict callers, loader,
  physical drains/recovery and clients remain open. No flash or hardware changes.
  Evidence: `research/checkpoints/2026-10-01-npu-cold-page/REPORT.md`.


This repository is the canonical workspace for this project. Start with
`docs/W1700K_STOCK_PORT_CURRENT_REFERENCE.md`, `docs/REMAINING_WORK.md`, then
the stock-port ledger and logging session in `docs/`. Update the ledger and
resume documents for substantive work; explicitly say when a read-only session
leaves the ledger unchanged.

## Objective And Source Track

- Pursue full NPU reverse engineering and implementation: native firmware,
  Linux/provider/mt76 integration, complete lifecycle and hardware acceptance.
  Keep this objective intact across turns and checkpoints.
- The whole project is experimental. Integrate implemented changes into the
  canonical patches, overlays and source lock, with their validation scope.
  Historical "unpromoted" descriptions retain their original checkpoint scope;
  the 2026-09-23 merge brought implemented candidates into the unified build.
- Continue from authoritative source, process and test state. A completed
  checkpoint closes only its documented scope. Full NPU completion requires
  actual firmware/host behavior, physical ownership/drains and client evidence.

## Current Checkpoint - 2026-10-01

- DESC5/6/7/8 now have full original helper-body execution after native core0
  and RX0/RX2 initialization: four nominal cases, 48 controls, five native
  mutants and four strict denials pass. DESC6 count 513 corrupts the published
  arena pointer. The production MT7996 sender now rejects short/zero/oversize
  requests using verified capacities 256/512/1024/1536 and native selector bits.
  Actual C and packaged AArch64 sender/table replay each pass 12,096 cases,
  384 pretransport rejections and six provider mutants. Full build/image,
  source replay, INODE and memory/retry/V2 regressions pass. Current FIT:
  `230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe`.
  Evidence: `research/checkpoints/2026-10-01-npu-page-rings/REPORT.md`.
  Native valid-count allocation failures still report outer success; partial
  IDs are retained. Checked native ownership/error handling and full strict
  attachment remain open. No flash or physical acceptance occurred.
- The production MT7996 INODE sender now zero-extends short payloads to the
  native wrapper's 24-byte total span and rejects invalid input before copy.
  Other valid profiles/commands keep their framing lengths. Actual provider C
  and the packaged AArch64 sender each pass 1,056 frames/30 controls; all 16
  original RV32 wrapper entries consume corrected bytes within the declared
  extent. Five mutants, the memory/retry/V2 regression, all 60 source files and
  the full image checks pass. Preceding FIT SHA256:
  `031f7bd2b28e0507ddfe810602a7edef71c63900244935e7d460ab58ab35a0cc`.
  Evidence: `research/checkpoints/2026-10-01-npu-inode-frame/REPORT.md`.
  This closes the provider-framing gap, not selector helper readiness, physical
  transport/drains or full NPU acceptance. No new flash occurred.
- Native postgate continuation now fixes hart7's first-boot allocator phase
  mismatch. All 50 detours remain installed; hart7 reaches its outer loop in
  emulation after explicit host-pointer publication and modeled release.
  Nineteen guard cases/nine mutants and the wider allocator regression pass.
  Harts 1-6 still await later host setup. This changes the shared native replay
  binding, not the vendor blob or built FIT. Evidence:
  `research/checkpoints/2026-10-01-npu-postgate/REPORT.md`.
- GitHub PR #1 source and its deferred history documents are now synchronized
  into the canonical WSL checkout. The reconstructed cloud snapshot matches
  tree `f2a52b2c27e21021e8c36d4b30a25e37565827c2` at commit `e095420`.
- The preceding local build passed FIT/board/218-package/78-module checks. Its
  FIT SHA256 is `277abd0b754200a0b330a35d4c759f264f918ec182cddc6c650fb734f46b4e4b`.
  Its packaged provider matches the cloud module, but the full image hash is
  distinct. Evidence: `research/checkpoints/2026-10-01-wsl-sync/REPORT.md`.
- The portable memory-plan runner now enables LeakSanitizer by default and
  records the selected sanitizers. The full host suite passes with leak checks
  enabled here; use `--disable-leak-check` only when needed and disclose it.
- The wired management interface was unavailable, so no new hardware check or
  flash occurred. Continue the remaining cold-lifetime, loader/caller/postgate
  and physical drain/rearm work; full NPU acceptance remains incomplete.

## Previous Cloud Checkpoint - 2026-09-30

- Current cloud working source adds pre-copy MT7996 WLAN memory admission and
  an immutable setup plan, with generic profiles keeping caller-local plans.
  The canonical patch and source lock are updated. Portable actual-C replay
  passes 273 loader/165 added load cases, three original controls, nine mutants,
  6,174 retry and 44 V2 executor cases. The current AArch64 provider module
  and ten RV32 components compile/link. The complete candidate image now
  passes FIT/board/firmware/218-package/78-module checks; physical boot and
  ownership/drain acceptance remain open. See the cloud-build report/handoff.
  Evidence: `research/checkpoints/2026-09-30-npu-cold-memory/REPORT.md`.
- Geometry admission and successful image copies are not containment, exclusive
  memory reservation or physical drain witnesses. The engine/reset matrix in
  that checkpoint records the separate unresolved owner contracts.
- Prior published source checkpoint `ac4c639` includes paired firmware preflight in the unified
  kernel patch on Linux 6.18.52 and mt76 `01367e60`. Both images validate before
  either copy; empty images fail and acquired firmware is released on error.
- Evidence: `research/checkpoints/2026-09-30-npu-loader/REPORT.md`. Actual-C
  faults, complete AArch64 provider objects, existing regressions and all 60
  source replay files pass. The earlier flashed image predates this change.
- Resume at contained cold-provider/reset lifetime, fresh loader identity and
  storage publication, DISCOVER/setup/BIND caller wiring, native postgate
  execution and physical DMA drain/teardown/rearm. Stock NPU parity is incomplete.
- Physical boot evidence is in `research/checkpoints/2026-09-23-nonoc-flash/`.
  Wired management passed; retained channel 161/EHT80 under country SA blocks
  Wi-Fi. R1 remains the protected rollback image. Check current observations
  before treating historical hardware evidence as current runtime state.

## Workspace And Engineering

- Work here, not in the superseded Windows task directory. Historical paths
  in evidence are provenance, not current workspace instructions.
- Current continuation is back in the canonical WSL checkout with its local
  prepared build and private inputs. Cloud receipt paths describe that earlier
  executor; verify local state before reusing environment-specific assumptions.
- The local source is WSL Ubuntu `/home/captain/W1700KNPU`, accessible from
  Windows at `\\wsl.localhost\Ubuntu\home\captain\W1700KNPU`. The Ubuntu backing
  disk is under `D:\WSL\Ubuntu`. The prior `D:\W1700K-Recovery` snapshot path
  was absent on 2026-09-30; verify the current location of recovery material
  before relying on historical backup paths.
- Preserve the distinction between modeled, compiled, Ghidra-verified, flashed,
  synthetic-router-tested, and actual-client-tested behavior. Stock NPU parity
  remains incomplete. Never label the WLAN-NPU-disabled baseline stock parity.
- Use `firmware/source-lock.json`, cumulative patches and overlays as source
  authority. Build on native Linux storage (including WSL ext4), never directly on NTFS. Generated builds
  and private inputs belong under ignored `.build/` and `.local/` paths.
- Preserve bootloader, factory/calibration, known-good rollback, and private
  router backups. Never upload keys, credentials, or raw device backups.
- Verify actual model, board/layout, FIT metadata, build status and hashes before
  flashing. Do not assume 192.168.1.1 is the W1700K. Do not switch this computer's
  Wi-Fi association for router testing or override radio transmit power.
- Historical archives may include superseded/unsafe experiments. They are
  evidence, not an instruction to apply every old patch to current upstream.
- Keep edits surgical and use existing source patterns. Do not apply global
  path rewrites to archived evidence or delete an only copy during cleanup.
- Use bounded standalone prompts for authorized subagents; do not fork this
  accumulated task history by default. Keep large evidence in files and return
  concise summaries/hashes so duplicate histories do not exhaust the drives.
- Use GPT-6 Luna with max reasoning for subagents. Prefer the requested v2 flow;
  the user authorized the exposed v1 interface for read-only reviews on
  2026-10-11. Do not substitute user-owned chats for subagents.
- Use the authorized GitHub connector if native Git authentication is absent;
  do not extract connector credentials. Existing Windows Git authentication
  pushed successfully when WSL lacked push credentials. Reuse configured
  credentials and verify the remote ref/tree after publication and before cleanup.

## Jev Decisions

- Apply the official installed `typesafe-ai` skill and current TypeSafe docs
  for bounded semantic routing, retrieval and claim/requirement checks. Batch
  useful independent Choice/Noul/Score questions over focused evidence.
- The configured credential is `Typesafe API` (including the space) in the
  Windows Process/User environment. The skill's local `Invoke-Jev.ps1` helper
  reads it in memory; the official SDK can accept explicit `api_key`. Never
  print, persist, put in prompts or commit its value. Read the skill for the
  current model and API configuration.
- Codex owns planning, code, exact calculations, tests and actions. Preserve
  actual Jev probabilities, investigate material uncertainty and use tests as
  proof for their covered behavior. Report API failure accurately and continue
  useful Codex work; never fabricate a Jev result or use an alternate provider.
