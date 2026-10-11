# Ordered Descriptor Lookup And TX Status Ownership

## Current Qualification

This descriptor checkpoint passes the scoped qualification below on the canonical
experimental mainline. The full NPU objective remains open. No router contact,
reset, flash or physical write has occurred. Current offline-qualified,
unflashed FIT:
`3951dc7c9160f5adbde30285c0a70cdf1cd36685b2c7222498977caddad9bdec`.

Implemented source:

- The16th archive object, `cold-descriptor.c/.h`, owns eight ordered lookups
  and1536 TX-status stores. Its6188-byte one-shot state retains preimages,
  reservation and committed/published progress; it never rolls back or retires.
- Native component14 has6264 bytes of private BSS and installs three detours:
  original GET callback0x84010164 and status loops0x8400d8cc/0x8400d8fc. Total raw
  hook count is77. The original operands, cursor increments and failure-frame
  unwind are preserved. Metadata, slots, code table, earlier owners and held
  context are checked under original allocator lock18.
- The existing80-byte cold envelope admits GET/API4 selectors0,2,10,11,12,8,5,7.
  Private server history grows104 to120 bytes, recording getter count/arena and
  callback preimages. The stateless codec validates geometry; the Linux executor
  additionally pins getter order/arena before exposing caller output. The
  provider treats every GET header as an output operation, without reading its
  caller's initially uninitialized value into a request.
- The original RX selectors return fixed arena subregion pointers. TX5/7 also
  initialize512/1024 status words to0x80000000. Unsupported0x457 success is not
  accepted as an address. Capturing arbitrary status preimages does not establish
  physical prior-user exclusion, engine coverage, coherency or retirement.
- Native descriptor, TX and indication callbacks now use per-invocation lock
  acquisition for cleanup. An old-code RV32 counterexample reproduced an unlock
  and cleared preowned flag in all three rejected callbacks. Fixed raw CODE
  preserves the flag and emits no acquire/unlock in all three direct controls.
  This test seeds the preowned flag; it is not physical lock-ownership proof.

Passing evidence:

- Exact compiled descriptor object:5732 host/RV32 comparisons,1592 controls and
  five mutants; AddressSanitizer, UndefinedBehaviorSanitizer and leak checks.
- Actual mt76 pointer publication:three cases. Actual mt7996 RX getter caller:
  seven rejection positions, with no corresponding host register write after
  failure. Queue/register backing and transport in this standalone test are
  synthetic, not hardware execution.
- Expanded cold wire657 cases/23 mutants and parser60/eight pass. It separately
  exercises host preflight, native-server pointer/order and stateless codec
  rejection, including saved-history corruption. A first valid arena is captured
  by the host; a different valid first pointer is not independently authenticated
  by its range check. Exact native binding and physical authority are separate.
- Fixed raw pair/repeat are byte-identical:14 native components/77 hooks,16
  assembly groups without skips. CODE567972 bytes:
  `11151179c3bad61b563d1c14703fb886945de036669edf589f376880bcc872e0`;
  DATA25728 bytes:
  `20e416709d1534c72752626e15fa67f75cb99ef7c16cce4256d117e376e9a619`.
- Fresh world and offline FIT/board/218-package/78-module checks pass. Candidate
  FIT26973002 bytes:
  `3951dc7c9160f5adbde30285c0a70cdf1cd36685b2c7222498977caddad9bdec`.
  Exact packaged provider707331d2... exports54 functions in Ghidra without failed
  decompilations. Source replay67 top-level/12 nested files and14 canonical Linux
  component mappings pass. Driver delta has zero strict-checkpatch findings.
- Exact world-built descriptor object repeats5732/1592/five with sanitizers.
  Endpoint, retained DMA lifetime, request, probe, boot and memory/retry/V2
  regressions pass. Twenty-one builder/source/ownership unit tests pass.
- All nine independently completed exact-input native cases pass. Nominal/HIF2
  pass all eight GETs and35 indication/28 TX/28 descriptor negative controls.
  TX5/7 faults retain1/0 and513/512 committed/published status words, with
  active/inflight1 and2,560 PKT/1,792 BA claims retained. No rollback/reclamation.
  Actual offload/RX callers complete; actual TX stops at API21 after GET5.
  Diagnostic GET7 does not establish full host initialization.
- Full raw replay authenticates26 initial commands through actual cold-client C,
  without test active writes or direct owner initialization. It retains3,072 PKT/
  1,792 BA claims and passes six boot/eight TXDONE controls. Later TXDONE's direct
  lease/ring metadata remain modeled; they do not complete the strict host lane.
- Previous4da01cfe FIT and all seven companion files were copied/hash-verified
  before world under `.local/npu-cold-descriptor-20261010/pre-world-image/`.
  Older/R1, calibration/bootloader/recovery and private backups are untouched.

Two authorized read-only GPT-6 Luna/max reviews completed through the available
v1 interface. Their missing-coverage findings led to40 begin/finish pointer
controls, nine actual TX-caller success/failure cases and56 acquired-versus-
preowned release observations. The standalone TX caller uses a synthetic
successful API21 peer solely to reach every failure position; the real native
lane still denies API21. Nine invalid provider-only selector arguments preserve
output/session and perform no transport; a malformed issued reply remains sticky.
The contract now states that distinction explicitly rather than changing the
existing no-effect preflight behavior to poison an otherwise usable instance.
One reviewer called that nonsticky preflight a defect; exact source/actual-C
tests and the clarified scope resolve the finding, not the label alone.

Initial fresh-name diagnostics exposed missing local linker selection, an
unmapped synthetic descriptor buffer, the old private-size assertion and a
missing page-owner include. These were corrected without relaxing instruction,
ownership or state checks. Failures are not counted as passes. Expanded wire
qualification corrected a host-preflight-versus-firmware-fault oracle mismatch,
then added independent saved-history and direct-codec controls to kill redundant
guard mutants. An initial unit selector ran zero tests and failed; corrected
discovery runs21 actual tests. Ghidra rejected a dot-prefixed project path before
import; the fresh ignored scratch project completed exact-module analysis.
The first long native diagnostic was explicitly interrupted after the lock bug
was identified, before editing its frozen inputs; it has no passing receipt.
The following serial qualification reached the final case but stopped at the
expected API21 denial before GET7, so its intended GET7 fault never ran. The
test now preserves that denial and explicitly continues the diagnostic GET7.
It also saves each completed case before proceeding. The corrected serial
attempt completed nominal/wrong-boot and was intentionally stopped while the
remaining cases ran independently with frozen inputs. Its partial run is not
credited as a passing complete invocation; the suite collector requires all
nine exact-input case receipts and records that execution method.

Actual `jev-1.13.0` source review selected retained failure at probability0.99,
codec-range/host-exact binding at0.97/confidence0.96. Reserve/readback/output
checks were0.91/0.85/0.93; physical-proof Noul0.06. Probabilities are evidence,
not acceptance thresholds. The source-extractor initially lacked enum return
types; its temporary adapter preserves original source slices. No model result
was fabricated for that failed preparation.

The broader native review retained uncertain readback/fault/lock labels
(0.46/0.66/0.26), prompting direct source/test inspection rather than automatic
acceptance. Focused readback/retention/acquisition questions returned
0.89/0.97/0.94/0.88; direct old/fixed lock execution is the acceptance evidence.
Broad API21 classification mislabeled four branches. A branch-focused follow-up
corrected the classifications, retaining selector5 confidence0.42. The source
and exact control-flow review, not a unanimous model label, support the next trace.
The argument-contract review returned not-established at probability0.60/
confidence0.40 about mandatory preflight poisoning; it is retained as uncertain,
not a unanimous approval. Issued versus preflight C tests establish the covered
behavior. A later lookup-focused review selected the static type100/101 path
at probability/confidence1.00, with pointer-admission/endpoint-retention/physical
proof Noul0.21/0.07/0.05. Six actual original RV32 lookup controls verify that
route and expose unvalidated static-pointer returns, without opening API21.

## Next Work

The descriptor/native/raw/HIF2/world/image/source/Ghidra qualification is closed
at its stated software/model scope. Continue the remaining TX-buffer address
publication and its host lifetime: current managed
TX allocations can be released on detach, so API21 exposure needs retained
ownership until a real retirement witness. Continue PCIe/INODE/TXDONE/final IRQ,
all remaining owners/workers/hot/postgate and physical containment/backing/cache/
DMA visibility, drains/retirement/recovery, exact-image boot and actual clients.
This checkpoint does not redefine the requested full objective around getters.
`NEXT_TX_BUFFER_TRACE.md` records the actual interleaved caller order, selector-
specific metadata/internal-header/typed-allocation effects and managed lifetime
boundary. API21 is not a uniform address setter or safe blanket whitelist.
