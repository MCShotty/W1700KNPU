# W1700K NPU and OpenWrt Workbench

## 2026-10-18 - Current Driver Links

The current provider and all three mt76 consumer modules link successfully
against the pinned Linux6.18.52 kernel,with matching ABI metadata and unchanged
original build trees.74 separate build-contract tests pass. This prepares a
fresh isolated full-image build;no module load or new image is qualified yet.
See the [module checkpoint](research/checkpoints/2026-10-18-npu-current-image/REPORT.md).

## 2026-10-18 - Original Formatter And Older Tail Diagnostics

The local stack checker now handles nine additional non-SP arithmetic forms,
with28 compiled fixtures/84 synthetic guest executions and234 unique tests
passing.20 individual formatter callees qualify locally;two computed-flow
boundaries still prevent a whole logger/IRQ bound. See the
[formatter checkpoint](research/checkpoints/2026-10-17-npu-original-irq/FORMATTER.md).
Both older tail diagnostic collections now pass36 cases each;they are distinct
from the still-running current cold callers and do not qualify the new firmware.

## 2026-10-18 - Fresh Caller Replay

Both current cold callers are running from a new frozen input set. The test
runner now verifies and records the test DTB and independently compiled sender
library before replay; nine new controls and228 unique tests pass. Four earlier
input-capture failures remain failures. No fresh constructor result is claimed,
and the paired firmware bytes and saved router images are unchanged. See the
[runtime-input follow-up](research/checkpoints/2026-10-17-npu-late-readers/REPORT.md#runtime-input-follow-up).

## 2026-10-18 - Late-Reader Owner Checks

Fixed two reproduced cold-owner liveness gaps: PCIe-tail readers now recheck
the complete earlier TXDONE/packet/RX owner state after external reads, and
INODE rechecks its complete tail dependency after its published-prefix reads.
The normal RV32 fixtures pass 647 tail calls/559 controls and 2522 INODE
calls/326 controls; these are modeled core tests, not original cold-constructor
or physical acceptance. Both profiles retain the full 1030+6 INODE effects.
See the [reader checkpoint](research/checkpoints/2026-10-17-npu-late-readers/REPORT.md).

The old tail matrices were interrupted with 34 passed cases each. Separate
frozen-source completion diagnostics are running; neither qualifies this new
candidate. Both old cold-caller ABI failures remain failures. Fresh complete
cold setup, hot TX/RX, checked IRQ/rearm, ownership/drain/recovery, remaining
original/indirect/stack analysis and real-router/client validation remain open.
Saved images and source-lock are unchanged; no hardware action occurred.
This supersedes older live-job descriptions below.

## 2026-10-17 - INODE ABI Observer Corrected

Both old cold callers reached all three PCIe tail stages/nine stores,then failed
a misplaced callback-entry ABI check. Both real stage0 captures and failures
are retained. The observer now checks callback entry-to-return before outer
epilogue,plus outer return before host restoration.35 focused/215 broader unique
tests pass;groups overlap. Repeat pair bytes are unchanged. Fresh constructor
qualification remains. HIF2 full512 bitmap diagnostic passes separately;old
failed matrices stay failed. Both all36-tail matrices remain live. See the
[ABI checkpoint](research/checkpoints/2026-10-17-npu-inode-caller/ABI.md).
This supersedes older running-caller descriptions below.

## 2026-10-17 - Logger Child Local-SP Checks

The local checker now handles three additional non-SP instruction forms while
rejecting their SP-writing counterparts.25 controls/199 focused units pass.
The four logger children analyze at16/0/0/16 local bytes,but a128-byte formatter
wrapper still calls an unreviewed child. No full logger cost or graph extension
is claimed. Fresh394 original-code probe records match the preserved earlier
scope exactly,without executing those children. See the
[logger-child extension](research/checkpoints/2026-10-17-npu-original-irq/LOGGER_CHILDREN.md).

## 2026-10-17 - Original IRQ Bodies And Error Tails

The two original PLIC routines have zero local SP depth,but their error paths
tail into a64-byte logger with four still-unqualified children. Fresh exact-body
checks and394 original-code emulations pass on synthetic hart0 RAM/MMIO:
384 normal returns,eight explicitly disabled-logger returns andtwo stopped
prefixes. This is not IRQ delivery,cold setup or a whole-stack bound.
The new checker passes19 controls;the focused suite passes193 tests and41
tiny synthetic guests. Initial checker failures remain preserved. Source-lock,
images and the older partial graph are unchanged. See the
[original IRQ checkpoint](research/checkpoints/2026-10-17-npu-original-irq/REPORT.md).

## 2026-10-17 - Queue-Filtered IRQ Status

The provider now filters shared status to the requested queue before its caller
acknowledges it,and rejects invalid queue IDs without register access. The
canonical patch/source-lock are updated.120 getter cases,five compiled mutants,
5778 handler/bulk/null fixtures and a fresh isolated AArch64 object pass.
174 focused units and a separate214 unique broader units pass;these groups
overlap. Error propagation,initial/hot rearm,readiness/quarantine and physical
IRQ acceptance remain open. Neither saved image contains this new change.
Stock REA observations and uncertain Jev checks retain their limits. See the
[queue-status checkpoint](research/checkpoints/2026-10-17-npu-irq-queue/REPORT.md).
Native jobs stay on their frozen older sources;no restart or hardware action.

## 2026-10-17 - Native Qualification And Offline Image Work

Both nominal callers passed full512 DESC10 setup and their first two PCIe tail
commands; later stages and both full 36-case tail matrices are running.
Each old DESC10 fault matrix remains failed at its original bitmap host deadline.
A fresh restored-prefix default bitmap replay now passes all strict checks;
the HIF2 equivalent is running. A separate default collection now passes the
unchanged grader over all eight byte-exact cached cases. This is cached
diagnostic coverage, not a fresh native matrix or a repaired failed run.
The observed denied replay also passes with
15 native artifacts byte-identical to its earlier case. No fresh complete
native matrix or final constructor qualification is claimed.

The fourth isolated Linux 6.18.52 world/image build now passes FIT, Gemtek
board, 218-package, 78-module and prepared-source 5/22/329 checks. The separate
numeric SquashFS check passes six critical files and their parents. All 891,138
original build entries, 4,617 cache entries, frozen inputs and parent namespaces
remain unchanged. The latest focused suite passes 174 tests, including the
nine-prefix verifier, guarded literal-call targets and 41 tiny synthetic RV32
guests. The new static supplement identifies 27 fixed register targets. Three
original callee bodies also pass 129 isolated hart-0 RAM/MMIO checks and a
narrow SP-balance audit. A new restricted graph has 300 mixed-proof nodes and
718 resolved transfers and six checked intra-function dispatches; 56 transfers
remain unresolved. Separate diagnostics cover 118 earlier table prefixes,
32 descriptor-table prefixes and two fixed-call prefixes, stopping before
case or callee bodies. They do not qualify constructors or a whole-stack bound.
See the [joint descriptor checkpoint](research/checkpoints/2026-10-17-npu-inode-caller/DESCRIPTOR_TARGETS.json).
Separate [reaching-definition checks](research/checkpoints/2026-10-17-npu-inode-caller/REACHING_TARGETS.json)
identify three IRQ/open call targets under ordinary-ABI assumptions, without
adding callee frames or extending that partial graph.
The new 27,009,866-byte image
hash starts `a22300ea`; [metadata and full hashes](research/checkpoints/2026-10-17-npu-world-isolation/WORLD.json)
are committed, not the binary. It is unflashed and not native/physical/client
qualified. The three earlier failed world attempts remain preserved.
See the [isolation and timing checkpoint](research/checkpoints/2026-10-17-npu-world-isolation/REPORT.md).

## 2026-10-17 - RX-Event Export Gap Repaired

Whole-source comparison found the retained RX-event allocation hook missing
from the exported mt76 patch. The exporter now discovers changed existing files;
the corrected patch reproduces all 329 clean source files across 11 changes.
Exported-source C checks pass 166 modeled cases/seven mutants. The provider and
all three mt76 consumers link against the refreshed source lock; 238 unique
focused tests pass in 256 executions. No rebuilt image, module load or hardware
acceptance is claimed; the native cold/fault jobs remain on their older cohort.
See the [mt76 integration checkpoint](research/checkpoints/2026-10-17-npu-mt76-link/REPORT.md).

## 2026-10-17 - Current Provider Module Linked

The current provider and its 22 source components now link into a real AArch64
module against the pinned Linux 6.18.52 configuration. Vermagic, three exports
and all 70 imports check out. All 102,685 original prepared-kernel inventory
entries remain unchanged; 218 unique focused tests pass in 236 executions.
This is an isolated, unloaded module, not a new world/image or native/hardware
qualification. mt76 consumers still need their current-source relink.
See the [provider link checkpoint](research/checkpoints/2026-10-17-npu-provider-link/REPORT.md).

## 2026-10-17 - RRO Bridge Still Open

Fresh137 original-firmware RRO probes pass on synthetic RAM. The current checked
bridge still rejects its actual16-byte atomic caller,verified by294 C cases.
It needs retained allocations,an appropriate atomic/process handoff,and checked
initialization/reset errors before RRO can be enabled. This is not native RRO
or physical DMA acceptance. See the [RRO bridge checkpoint](research/checkpoints/2026-10-17-npu-rro-bridge/REPORT.md).

## 2026-10-17 - IRQ Status And Poll Lifetime

Fixed an uninitialized status return on register-read failure. MemorySanitizer
is clean for the corrected body and reproduces the preserved old defect. The
5778 read/ack/mask fixtures still show missing error propagation and quarantine;
this value fix does not complete IRQ handling or establish quiescence.
See the [status/error checkpoint](research/checkpoints/2026-10-17-npu-irq-status/REPORT.md).

The NPU poll callback now explicitly keeps its provider lookup/use inside RCU.
Actual-C52 cases/five compiled RCU mutants,two isolated AArch64 objects and210
unique focused units pass. The exported source patch reproduces the change;
prepared kernel/modules/FIT are unchanged. This does not fix the still-discarded
IRQ errors or establish physical lifetime/drain safety.
See the [poll lifetime checkpoint](research/checkpoints/2026-10-17-npu-poll-rcu/REPORT.md).
Existing cold native runs remain on their frozen producing source,not this edit.

## 2026-10-17 - INODE Caller Qualification Running

The actual caller now sends both checked INODE constructors after the PCIe
tail. Its independent read-only oracle checks original stores,protected memory,
private state and ABI before the mailbox helper restores CPU context. Fresh
CSR reads are integrated into the cold observer;native guards/raw firmware bytes
are unchanged.208 unique focused tests,repeat image/loader/sender checks pass.

Both fresh HIF callers and their full512 DESC10 fault matrices are running in
the tested original-path frozen copy. Constructor/fault verdicts remain pending.
The new24-case INODE fault runner is prepared,not yet natively qualified. Exact
stack auditing finds297 C frames and a9696-byte partial direct-call candidate;
indirect/IRQ/physical stack bounds stay open. No new world/image/flash or hardware
acceptance. See the [caller/oracle checkpoint](research/checkpoints/2026-10-17-npu-inode-caller/REPORT.md).
Older checkpoints retain their original scope;full NPU implementation remains open.

## 2026-10-17 - Native INODE Binding In Mainline

The20-component/168-hook experimental pair now binds both INODE constructors
to their real callback/store guards and routes them through the checked Linux
provider. Retained allocation records and the published plan are pinned across
all tail/constructor commands. Both-HIF modeled provider504/10 mutants,portable
owner checks,36 raw unleased denials,repeat image checks and eight-hart published
boot pass. Fresh authenticated native constructor success is still untested.

The older frozen HIF2 tail caller passed. Its36 individual tail cases passed,
but their aggregate failed for missing artifact provenance;that failure stays
failed. The new recorder requires all manifest/raw/ELF identities. Neither old
cohort result qualifies the new build. Source export and an isolated AArch64
provider object pass;no module/world/image rebuild or flash is claimed.
See the [current native checkpoint](research/checkpoints/2026-10-17-npu-inode-native/REPORT.md).
Earlier live notes are historical. Full NPU/physical/client work remains open.

## 2026-10-16 - Checked INODE Command Journal

API24 constructors2/7 now have ordered server/Linux-client progress after the
complete PCIe tail. All35 old private offsets remain unchanged;two appended
words grow SETUP to412 bytes. Version/STATUS,early and late faults,lost replies
and retained failures are tested. Host protocol2282 cases/60 mutants,compiled
RV32 dispatch70/four,186 selected units,repeat raw19/156/all19 image groups and
actual published-byte/eight-hart boot pass their scopes.

Native INODE execution remains explicitly closed until its retained owner and
all11 original store guards are bound. The ongoing HIF2/full36 tail validation
runs against a preserved older404-byte candidate in private mount namespaces,
not newer main. No rebuilt world/image or hardware acceptance is claimed.
See the [current journal report](research/checkpoints/2026-10-16-npu-inode-journal/REPORT.md).
Earlier live notes below are historical. Full NPU implementation remains open.

## 2026-10-16 - Actual Nine-Store Tail Passes

The fresh default-HIF allocator/provider/caller passes full512 DESC10, RX PCIe
and all three PCIe-tail stages/nine original stores. All eight retained DESC10
faults and broader raw/six boot controls pass. The actual padded API24 INODE
request is rejected before the constructor, not a constructor failure/success.
All12 stage0 tail faults pass; the complete36-case matrix and fresh HIF2 caller
are still running. Full setup and physical hardware operation remain unproven.

A hash-preserved validation copy passes original-path native restored-fault
and raw revalidation inside a private mount namespace, with the parent project
mount unchanged. This isolates an older candidate's validation from later main
edits; it never qualifies those edits. All185 selected unit tests pass. The new
CSR read helper remains unintegrated and has only host-read microbenchmark
evidence. See [validation isolation and limits](research/checkpoints/2026-10-16-npu-pcie-tail-native/CAPSULE.md).

Older live-status notes below are historical. FIT978f9ddd remains unchanged and
unflashed; INODE, checked IRQ/hot paths, workers, full stack/physical ownership,
drains/lifecycle/recovery and actual-client acceptance are still required.

## 2026-10-16 - Native PCIe Tail Binding In Qualification

All nine original PCIe0/2/15 stores now have retained native owner guards and
explicit authenticated prior-owner successors. The actual provider lifetime
check/routing and MT7996 sender are extended. Repeated raw19-component/156-hook
images, all19 image checks, checked loader60/eight mutants, actual published-byte
eight-hart boot, provider84/five mutants and18 unleased tail denials pass.
Protocol1930/53 and existing provider609/nine regressions also pass.

Scoped sealc9913292 verifies343 current inputs, not a fresh positive native
verdict. Actual allocator/caller pcie-tail-native-q2 is live with consumed
inputs frozen. Full512 DESC10/all eight retained faults pass;RX PCIe/nine-store
tail qualification remains pending. The selected172-test suite,including fault-oracle/raw-caller/frame contracts,passes
its synthetic scopes. Older producing cohorts are protected. FIT978f9ddd remains
unchanged/unflashed; full INODE/IRQ/hot/worker/stack/physical/drain/lifecycle/
client work remains open. See the [native binding report](research/checkpoints/2026-10-16-npu-pcie-tail-native/REPORT.md).

Extended scoped seal5cedd413 binds404 current input hashes, including exact
tail C frames, the raw-CODE-mapped Ghidra export and two corrupt-map controls.
Those static/fixture checks do not qualify the still-running native caller or
the full512/eight-fault matrix.

The canonical raw frame audit reproduces all19 components and complete CODE/DATA,
measures264 C frames across39 translation units, and lists remaining assembly/
function gaps explicitly. Largest individual frame3600 is not a full stack bound.

A separate exact-byte assembly audit covers the four pure-assembly components
and five typed wrappers. It records egress's16/48-byte alternative reservations
and the ring consumer's caller-stack read; it does not bound complete paths or
physical stacks. All150 selected units pass. Native caller/readiness jobs remain
live with their consumed inputs unchanged.

The address-bound CFI audit matches all264 C frames,resolves604 direct transfers
and lists81 unresolved transfers. Its4480-byte largest direct-chain candidate
is not a complete stack limit. Ten further controls bring the selected suite
to160 passing tests;native qualification remains pending.

Latest native progress: the actual caller's full512 DESC10 and all eight full512
retained faults pass with current input hashes. Both readiness faults stop at
25604 stores. The caller is still in RX PCIe;new nine-store tail qualification
and tail-specific faults remain pending. No hardware/full-setup verdict.
The strict36-case tail matrix runner is canonical;seven aggregate contract
tests pass,not the native matrix whose three actual prefixes are still pending.
RX PCIe now passes;tail stage0 and its restored fault shard are live. Separate
original RRO0/1/3 probes pass137 byte/ABI cases in synthetic RAM,not checked
admission or physical DMA. See [RRO scope](research/checkpoints/2026-10-16-npu-pcie-tail-native/RRO.md).

## 2026-10-16 - PCIe Tail Protocol Journal

The checked protocol now retains the accepted TX2/HIF register and the ordered
PCIe0/2/15 command journal. Both HIF profiles, late mutations, lost/corrupt
replies and callback failures are covered. Native dispatch explicitly denies
these commands until their actual nine-store owner is bound; selector15 can no
longer be mistaken for a successful synthetic binding just because of its header.

Scoped checks pass1930 protocol cases/53 mutants,609 provider cases/nine mutants,
45 compiled RV32 dispatch cases/three mutants,118 focused units and all18 image
groups. Two raw18-component/147-hook builds repeat, private setup is404 bytes,
and the unified source export/lock verifies70 OpenWrt/five LuCI files.
Seala07b27a7 binds452 inputs. No fresh full512 caller/fault qualification of this
changed pair is claimed. The prior qualified producing cohort remains preserved;
FIT978f9ddd is unchanged/unflashed. Full native/IRQ/hot/lifecycle/physical/client
work remains open. See the [journal report](research/checkpoints/2026-10-16-npu-pcie-tail-journal/REPORT.md).

## 2026-10-16 - Packet-Plan Guard Qualified

The fresh actual allocator/provider/host caller now passes full512 DESC10 and
RX PCIe in native emulation, with25606 original stores,1028 ordered lock writes,
exact856064 protected bytes and3072 packet/1792 BA claims. All eight full-size
retained faults pass; packet-plan mutation stops at25604 before readiness.
The migrated broader raw regression and six boot controls pass without a seeded
lease or source-hash waiver. Sealb02ebf82 verifies1169 current inputs/117 units;
its1171-file producing cohort is hash-preserved. All jobs are terminal.

This is the default-HIF initialization prefix, not full setup or hardware proof;
earlier native negatives were skipped. No flash was performed. Remaining native
PCIe/INODE, IRQ/hot ownership, stack/drain/lifecycle and actual-client acceptance
remain open. Older live notes below are historical, not restart instructions.
See the [qualification report](research/checkpoints/2026-10-15-npu-desc10-plan/REPORT.md).

## 2026-10-15 - Packet-Plan Guard Qualification

The actual native readiness fault exposed premature final counter/ready stores
after borrowed packet-plan mutation. The guard now checks base/extent before
and after readers, including the later PCIe handoff. Scoped compiled24 cases,
103 units, repeated raw18/147/all18 image groups and loader60/eight mutants pass.
WSL restarted during desc10-plan-q1; its nominal/two late faults are incomplete,
six individual faults pass and its144-file stopped cohort is hash-preserved.
Fresh actual caller desc10-plan-q2 is live with inputs frozen; all eight native
faults and complete changed-pair qualification remain pending. All103 units and
24 compiled guard cases pass again after access restoration. Normal world and
exact FIT978f9ddd board/package/module/archive checks pass; unflashed. Prior
FIT1aa17499 and companions are protected. No hardware acceptance is claimed. See
research/checkpoints/2026-10-15-npu-desc10-plan/REPORT.md.

The independent frame audit covers166 normal-build functions/22 exact objects
and29 C functions in the exact DESC10 component; all117 focused units pass.
This measures individual frames, not full call-chain or physical stack bounds.
See [frame measurements](research/checkpoints/2026-10-15-npu-desc10-plan/STACK.md).

## 2026-10-15 - Retained Replay Migration

The broader raw regression is moving onto the actual allocator/host caller,
without a seeded TXDONE lease or relaxed native guards. Strict capture/restoration,
pre-state-derived partial-memory oracles and original-store/lock tracing are
integrated. The 96 focused units pass; fresh full512 execution and all eight
retained native fault verdicts are pending. Current caller retained-replay-q3
is live with inputs frozen; interrupted Q1/Q2 are not passes.
No firmware/image/hardware change occurred. FIT1aa17499 remains unflashed and
full stock parity remains incomplete. See the
[retained replay report](research/checkpoints/2026-10-15-npu-retained-replay/REPORT.md).

## 2026-10-15 - Canonical PCIe/INODE Owners

The remaining PCIe-tail and INODE owners are now canonical normal-build inputs,
not temporary staged source. Exact normal-Os RV32 qualification passes446/376
and2312/142 calls/controls, both HIF profiles,15 compiled host mutants/sanitizers,
42/120 original-store ABI cases with guard stubs, and61 focused units. Real native
guard/admission binding remains open for these commands.

The earlier fresh actual-C allocator/caller replay completed through DESC10 and
RX PCIe, not full setup. Its producing cohort was preserved before promotion.
Current raw CODE/DATA repeat unchanged at18 components/147 hooks; source70/5,
world and offline Gemtek W1700K/218-package/78-module/22-object checks pass.
New FIT1aa17499 is unflashed; prior69c88ce9 and companions are protected.
The broader raw regression is terminal1: its old modeled TXDONE lease is rejected
before descriptor stores because it lacks the strict authenticated prerequisites.
That test still needs migration with full constructor/fault coverage intact.
Final IRQ, worker/hot datapath,
lifecycle/drain/recovery and actual hardware/clients remain open. See the
[canonical promotion report](research/checkpoints/2026-10-15-npu-owner-promotion/REPORT.md).

## 2026-10-15 - INODE Ownership

The staged INODE owner now covers the complete4104-byte ICV clear and both
ordered flag commands, requiring completed PCIe/TX/RX/DESC10 ownership. Host
validation passes382 host and2312 exact normal-Os RV32 calls/142 controls each,
both HIF profiles, eight compiled mutants and address/undefined/leak sanitizers.
Five receipts/71 current input hashes verify. Neither this owner nor the
preceding PCIe tail is original-store/authenticated-native admitted yet.
Its eleven original-store trampolines pass120 ABI cases with explicit guard
stubs; six scoped receipts/78 current input hashes now verify.

The fresh caller has passed DESC10 and all856064 protected bytes; PCIe execution
remains active. Source inputs stay frozen,
and the qualified staged work will join the normal build after terminal. No
worker/IRQ release, new image, flash or hardware acceptance is claimed.
The following IRQ gap is also reproduced in actual C with modeled register
errors: its void API loses failures. Checked propagation and runtime re-enable
handling remain to implement; the checkpoint's NEXT_IRQ.md records the contract.
Evidence: [INODE owner](research/checkpoints/2026-10-15-npu-inode-owner/REPORT.md).

## 2026-10-14 - Remaining PCIe Owner

The next three-command PCIe owner now retains all nine ordered effects and
requires the independently finished TX and RX PCIe/DESC10 owners. Both host C
and the exact normal-Os RV32 object pass446 calls/376 controls, including both
HIF profiles and partial-failure retention. Seven compiled mutants and address/
undefined/leak sanitizers pass. A reader-mutation hole in first-command admission
was reproduced and fixed. These are portable/logical-memory tests, not a new
native or hardware admission claim.

The nine native store trampolines now pass42 original-callback/ABI cases with
explicit guard stubs. Following INODE tracing passes four nominal and1036
interrupted-write prefixes, including the fixed type109 lookup and full4104-byte
clear. Real native guard/history integration is still required; exact contracts
are in the checkpoint's NEXT_NATIVE.md.

Source is temporarily staged while earlier native replay inputs remain frozen;
normal-build integration and all nine original store bindings are next, without
a separate experimental feature mode. The existing30-case native PCIe fault
matrix now passes with267 current input hashes; its redundant serial copy was
intentionally interrupted, not counted as a pass. Fresh full caller82479 remains
live at pre-DESC10. FIT69c88ce9 stays unchanged/unflashed; full scope is open.
Evidence: [portable PCIe tail owner](research/checkpoints/2026-10-14-npu-pcie-tail-owner/REPORT.md).

## 2026-10-14 - RX PCIe Diagnostic And Unified Image

The original guarded pointer store now passes a strict restored-prefix nominal
test:3072 claims/RXsteps3, completed one-shot owner and exact856064-byte memory
agreement. This is not fresh full setup or hardware proof. The corrected header
export and unified world build pass; exact unflashed FIT69c88ce9 includes20 RV32
objects/raw18-147,218 packages/78 matching module ABIs and Gemtek W1700K metadata.
Previous82b1563a plus seven companions are protected. Source67 OpenWrt/5 LuCI,
six header-closure units and compiled-provider REA inspection also pass.

Native fault groups and fresh full sender remain live; current source stays
frozen/uncommitted until their verdicts. Full setup, packet handling, recovery,
physical DMA/drain and real-client gates remain open. No hardware or publication.
Scope: research/checkpoints/2026-10-14-npu-rx-pcie-bind/REPORT.md.

## 2026-10-14 - Native RX PCIe Binding In Progress

The working tree binds the final RX PCIe pointer store in raw18 components/
147 hooks. The actual allocator/caller replay now completes DESC10 with25606
effects,3072 packet claims and exact agreement across856064 protected bytes.
Its following PCIe command stops at an observation boundary before the pointer
owner begins, so the complete sender is not yet accepted. Current-prefix DESC10
controls31 and early API0/history denials4 pass with no input-drift exceptions.
A bounded read-only reader checkpoint passes4 units; nominal/fault diagnostics
are live. Ghidra's mapped15-function export retains debug/type limitations.

Full setup, packet handling, recovery, physical DMA/drain proof and real-client
acceptance remain open. No new world image, hardware action or publication;
FIT82b1563a is unchanged/unflashed. Current evidence and continuation:
research/checkpoints/2026-10-14-npu-rx-pcie-bind/REPORT.md.

## 2026-10-14 - Portable RX PCIe Ownership

The normal20-object archive includes a168-byte one-shot owner for the final
RX-event PCIe pointer, derived from the retained BAR. Its completed-DESC10
memory check reads20998 final cells, including full descriptor/ID/SKB/queue
contents. Exact host-C/RV32 passes226 calls/213 controls/eight mutants and
sanitizers. DESC10 regression3656/3541/nine,24 units, identical raw17/145 pairs,
all17 image groups and checked loader60/eight pass.

Native binding of this PCIe tail is still next; API0 admission remains closed
and the full three-command sender has no passing current native receipt.
No world/image promotion, hardware or publish occurred; FIT82b1563a is unchanged.
Full setup/lifecycle/physical/recovery/client scope remains. Evidence and next
binding: research/checkpoints/2026-10-14-npu-rx-pcie-owner/REPORT.md.

## 2026-10-14 - DESC10 Protected Memory Reconciled

Native Q7 reached25606 effects/512 new claims/total3072/RXsteps2/ready1, then
failed an incomplete oracle. The terminal same-image prefix replay shows only
the required sequence56->57 byte at3e906390 differed. Modeling that exact
request-derived protocol word reconciles all856064 protected bytes in five
regions. No memory region is excluded and no observed post-state drives expected
data. The main harness now uses this oracle and retains memory images;24 units pass.

This is scoped native/diagnostic evidence, not a new passing full caller or
physical acceptance. The corrected harness needs a fresh run; the owned PCIe
tail and remaining setup/hot/physical/drain/recovery/client gates stay open.
Canonical export/world/publish are pending; FIT82b1563a is unchanged/unflashed.
No live jobs or hardware action. Latest continuation is in the canonical trackers.

## 2026-10-14 - Native DESC10 Integration In Progress

The working-tree raw composition now builds17 components/145 hooks, binding
the original DESC10 stores to retained RX/PKT/TXDONE/SKB ownership. Original
type0x107 lookup is fixed L2 storage at0x3e8adc70, not a new heap allocation.
All20 selected store instructions match original/raw bytes, including both
valid-count and alternate metadata branches; the
corrected portable owner passes3656 calls/3541 controls/nine mutants/sanitizers.

Full native DESC10 validation is still in progress. The first actual caller
run stopped in a prior-effect scan. Q3 then
revealed two missing valid-count metadata hooks, now fixed. Wire1378/40 mutants
covers58 DESC10 cases. Q4 stopped after3074 stores/512 claims on a signed
halfword payload; width normalization passes18 cases/one mutant. Q5 published
7170 stores before the boot-only TX-clear observer stopped it. The narrow
pending-owner/store-site observer fix passes15 units plus three capture units;
captured-prefix replay exposed a guard-symbol lookup error, now fixed and
covered by30 real linked-symbol observer checks. Exact typed allocator records
and full paired-CODE sizes now precede effects;57 C cases/three mutants pass.
Q6 was intentionally cancelled for these fixes. Current CODEaff56189/
DATA03c504e5 repeat identically; all17 image groups, loader60/eight and current
wire1378/40 pass. Fresh Q7 is terminal: native error0/all25606 effects/512 new
claims/RXsteps2/ready1, but the whole-memory oracle comparison failed. No full
nominal pass is claimed. Same-prefix byte-diff replay is live. Its captured actual
prefix passes31 native early/first-two-store fault/ABI controls with245 current
input hashes; fixture restores are not fresh setup or physical proof.
Eight malformed-count/unmarked/seeded-lease denials also pass with no effects;
39 focused native controls are now checked. Later
SKB/readiness/native mutations and export/world are not
claimed complete. The82b1563a image is unchanged/unflashed, and the full
setup/lifecycle/physical/recovery/client objective remains open. No hardware
action or subagents. Current local receipts: .local/npu-desc10-native-20261014/.

## 2026-10-14 - Portable DESC10 Ownership

The normal portable Makefile now includes a13512-byte one-shot DESC10 owner.
It requires the finished RX/API22 owner, preserves the shared PKT prefix and
tracks512 further claims plus25606 ordered descriptor/SKB/readiness effects.
The exact compiled object passes3656 compared host-C/RV32 entry calls,3541
controls, eight mutants and sanitizers. Source69 and all16 image groups pass;
independent current raw builds remain byte-identical to the preceding image.

This is portable logical execution, not the original authenticated constructor.
Native binding and complete setup/lifecycle/physical/recovery/client acceptance
remain open. FIT82b1563a is still unflashed; no new world image was built.
The three style warnings and stale stdout record count are fixed. No hardware
action or subagents. Evidence and concrete continuation:
`research/checkpoints/2026-10-14-npu-desc10-owner/REPORT.md`.

## 2026-10-13 - Owned RX Enrollment And API22 Tested

Normal source now enrolls eight mailbox handles and the retained RX-event ring
before queue exposure, then appends six TX handles. Selector0/API22 is bound to
the original metadata store under a152-byte retained owner. Raw16/126,
archive18/private388, world, source69, Ghidra61/43 named ELF functions, REA and
FIT218+78 checks pass. The82b1563a image is unflashed; f185a731 plus seven
companions are preserved. Owner487/211/seven, C166/seven, wire1320/34 and all16
assembly groups pass. Eleven receipts/290 current input hashes verify.

Actual allocator/caller/original-RV32 replay passes15 enrollment records, all
six API21 phases/53260 effects/76 controls and API22 metadata/30 native controls.
Authenticated DESC10/shared PKT/TXDONE/SKB and remaining setup/lifecycle/
physical/recovery/client gates remain open. Checkpatch reports zero errors and
three line-length warnings. No hardware action or subagents. Current scope:
`research/checkpoints/2026-10-13-npu-rx-event-bind/REPORT.md`.

## 2026-10-13 - Retained RX-Event Backing

The real RX-event descriptor allocation now belongs to the retained provider
lifetime before queue registers can expose it. C115/seven mutants, sanitizers,
source68, strict style, full world, Ghidra60/REA and FIT218+78 checks pass.
The new `f185a731...` image is unflashed; prior `9d1fa30d...` and companions
are protected. Raw CODE/DATA remain unchanged. Current native replay passes
one RX/six TX allocations and all six API21 phases/53260 effects/76 controls.
RX-event native enrollment, complete setup and physical/client
acceptance remain open. No hardware action.
Scope: `research/checkpoints/2026-10-13-npu-rx-event-lifetime/REPORT.md`.

## 2026-10-13 - Original API21 Callbacks Bound

Mainline source now binds all six original API21 callbacks and53260 stores
to retained ownership, with exact enrolled handles and GET/SET interleaving.
Raw composition is15 components/124 hooks; private cold history is368 bytes.
Actual allocator/caller/raw-native replay passes both TX bands, exact protected
bytes and76 fault/guard controls. Wire1250/29, packaged owner106640/80/seven,
world/Ghidra59/source68/FIT218+78 and all16 image groups pass. Full current-input
raw3072 PKT/1792 BA/six boot/eight TXDONE controls pass with later lease/ring
metadata modeled. Latest FIT9d1fa30d
is unflashed;69257a6b/6c76e14a and companions are protected. Wider native/HIF2/
neighbor/mutant, RX-event/lifecycle/physical/client work remains open. No hardware
action or full parity claim.
Current scope and next work:
`research/checkpoints/2026-10-13-npu-api21-native/REPORT.md`.

## 2026-10-13 - Native TX Records Enrolled

The retained allocator binds eight mailbox and six TX DMA records into native
boot/nonce/held state before returning handles. Wire80 is unchanged; private
history is360 bytes. Lost replies retain both prefixes and every allocation.
The portable owner covers all53260 stores; original API21 hooks are not bound.

Owner106640/80/seven mutants, wire1203/25, lifetime113/nine, native14/forty lease
pairs, provider609/nine,21 units, source68/style/world/Ghidra58/FIT218+78 pass.
Latest unflashed FIT69257a6b; prior6efaa878/ffbd4344 and companions are protected.
Next bind API21, then remaining setup/owners/hot/physical/recovery/clients.
No hardware contact or full stock-parity claim. Scope and evidence:
`research/checkpoints/2026-10-13-npu-tx-enrollment/REPORT.md`.

## 2026-10-13 - Retained Host TX DMA Buffers

The checked provider now owns all six coherent TX allocations, their CPU/DMA
records and the endpoint reference across partial errors and detach. Allocation
uses the NPU DMA device, pins the boot/session/native plan, validates complete
alias/overlap geometry and requires fresh STATUS before returning handles.
Only an unmarked provider's `-EOPNOTSUPP` selects managed allocation.

Actual C passes 76 cases/seven mutants; provider C passes 609 cases/nine mutants
with 272 BAR geometry cases. Native allocator/STATUS replay, 21 unit tests,
strict checkpatch, source/world/Ghidra59 and image checks pass. The new unflashed
FIT is `6efaa878...`; previous images and private backups remain protected.
Eight original RV32 cases pin down API21's 512-record writes and partial
metadata faults. API21 admission, physical retirement and full NPU acceptance
remain open. No router contact occurred. Scope and next implementation:
`research/checkpoints/2026-10-13-npu-host-tx-lifetime/REPORT.md` and `NEXT_API21.md`.

## 2026-10-11 - Retained Descriptor GETs

Mainline source now admits eight ordered descriptor GETs with a retained owner
for the512/1024 TX-status writes. The wire stays80 bytes; private history is120.
The Linux executor pins getter order and arena before publishing caller output.
The portable core passes5732 host/RV32 comparisons,1592 controls/five mutants;
the expanded wire suite passes657 cases/23 mutants, including independent host,
server and codec rejection checks. All nine native cases and HIF2 pass, with
35 indication/28 TX/28 descriptor controls and retained partial status faults.
Full raw replay, world/source/Ghidra54 and FIT/218-package/78-module checks pass.
The invocation-local lock cleanup fix prevents rejected callbacks from releasing
an earlier owner's lock; three old-code counterexamples and fixed controls pass.

The actual RX caller completes six endpoint writes. The TX caller completes GET5
then stops at denied API21; GET7 afterward is diagnostic, not full host setup.
Retained host TX-buffer lifetime and remaining PCIe/INODE/TXDONE/IRQ, hot and
physical/client gates remain open. API21 types0x100/0x101 use static L2 pointer
lookups, not dynamic allocations; six original RV32 controls expose unchecked
pointer returns. Current offline-qualified, unflashed FIT is `3951dc7c...`;
previous `4da01cfe...` and older/R1 are preserved. No hardware contact. Scope:
`research/checkpoints/2026-10-10-npu-cold-descriptor/REPORT.md`.

## 2026-10-10 - Authenticated TX0/TX2 And Token Prefix

The checked mainline now completes the real mt7996 offload initializer through
TX0, TX2 and token-limit publication. A retained80-byte owner reserves11 original
metadata/index/CSR/token writes under pinned allocator/session state; partial
faults retain progress and the outer lease. There is no reset/reclamation API.

Exact world-object525 calls/205 controls/six mutants, wire459/16, nominal and
HIF2 actual-C/native replay with27 TX/34 indication controls, full raw3,072 PKT/
1,792 BA regression, world/source/Ghidra54/FIT218+78 and16 assembly groups pass.
All seven native cases, including register/token partial faults, pass.
Latest unflashed FIT `4da01cfe...`; previous `8dd1f2f4...` and older/R1 preserved.
Initial raw setup uses the actual cold-client C, with no test active/init writes.
Only later TXDONE still uses directly modeled lease/ring metadata.

Next is RXDESC-base GET-selector0/API4, which remains denied, followed by the
remaining host/TX-buffer/INODE/TXDONE/final IRQ setup. Other owners/hot/postgate,
physical exclusion/backing/coherency/drains/recovery and actual clients remain
open. No flash or router contact occurred. Full NPU goal stays open. Scope:
[TX checkpoint](research/checkpoints/2026-10-10-npu-cold-tx/REPORT.md) and
[next setup trace](research/checkpoints/2026-10-10-npu-cold-tx/NEXT_SETUP_TRACE.md).

## 2026-10-10 - Retained Indication And ACK Prefix

The checked cold path now initializes all 1,536 indication records under a
one-shot retained owner, then records the ACK address. Original allocator lock18,
unique arena/subregion identity, full RX/page count history and per-record
held-state checks guard the native read/store hooks. No reset or retirement API
was added; the existing 80-byte wire/session is unchanged.

The exact 14th core object passes 12,322 host/RV32 calls, 3,095 controls and seven
mutants. Actual-C nominal setup and 34 native negative controls pass without a
synthetic active grant or direct owner initializer. The actual txrx sender now
stops at TX0/API19, which programs native DMA registers, not at selector8.

World, 54-function packaged-provider Ghidra, 66 top-level/12 nested source files,
13 provider components, assembly and FIT/218-package/78-module checks pass.
Latest FIT `8dd1f2f4...`; prior `5c94b20d...`/R1 preserved. No flash or router
contact. Full strict TX/INODE/TXDONE, remaining owners/hot/postgate and physical
containment/coherency/drains/recovery/clients remain open. Evidence and limits:
`research/checkpoints/2026-10-10-npu-cold-indication/REPORT.md`.

## 2026-10-10 - Bound PCI BAR And Cold Page Rings

The real mt7996 PCI caller now passes BAR0 start/length to the checked provider
before mt76 publishes its NPU/PPE pointers. Session-bound metadata and exact
native history gate port/RX and page5/6/7 address/DESC commands. First authenticated
DESC5 initializes BA ownership; no new session, retirement or reset API is added.

Actual host/provider C, geometry/fault/mutant tests, sender-to-provider-to-raw-RV32
replay of2,560 packet/1,792 BA claims,54-function packaged-module Ghidra and
world/source/image checks pass. FIT `5c94b20d...`; previous `7622acf9...`/R1
preserved. No flash, reset or router contact. The actual txrx sender next stops
at unsupported indication selector8. INODE/TXDONE/full setup, other owners/hot/
postgate and physical containment/coherency/drains/recovery/clients remain open.
Evidence: `research/checkpoints/2026-10-10-npu-cold-pages-wire/REPORT.md`.

## 2026-10-10 - Session-Bound Cold RX Commands

The real checked provider now sends the post-BIND version query, port type and
RX0/RX2 descriptor setup through a distinct session-bound cold envelope. Native
code validates the existing nonce/boot identity/sequence and held epoch before
granting the callback lease. Packet ownership initializes in that authenticated
path; the native tests do not inject an active lease or call its initializer.

Cold C/codec/executor tests, native full RX prefix and retained-fault controls,
packaged-module Ghidra, full world/66-file replay and offline image checks pass.
Latest FIT `7622acf9...`; previous `6a7dc41e...`/R1 preserved. No flash/contact.
This is the initial strict RX prefix, not full offload: later PCIe/page/INODE/
TXDONE setup, physical containment/coherency/retirement and clients remain open.
Evidence: `research/checkpoints/2026-10-10-npu-cold-wire/REPORT.md`.

## 2026-10-10 - Provider-Owned Initial Session

The real reserved-memory callback now owns one checked V2 session in the NPU
provider, not per mt76 attachment. It verifies the loader's boot identity before
setup, sends the existing six-command prefix, binds and polls the held initial
epoch. Failure stays sticky; reattachment cannot create another nonce or replay
setup. Close joins this CPU path without releasing exposed DMA storage.

Actual C passes279 cases/nine mutants; the Linux client completes the prefix
against assembled RV32 firmware using C-published DATA, and a wrong identity
stops before setup. Packaged-module Ghidra, full raw ownership regression,
world/63-file replay and FIT/218-package/78-module checks pass. Latest FIT:
`6a7dc41e...`; previous `b0400eaa...` and R1 are preserved. No flash/contact.
Full strict RX/TXDONE setup, physical containment/retirement and clients remain
open. Evidence: `research/checkpoints/2026-10-10-npu-provider-session/REPORT.md`.

## 2026-10-10 - Checked Boot Launch

The actual provider now checks every existing boot-register write, stops on the
first error without retry/reclamation, and permits only one launch attempt.
Checked MT7996 pairs also require the expected version reply before provider
publication; legacy version reporting stays diagnostic. Actual-C 248 cases/ten
mutants and 265 probe cases/three mutants/one original-source control pass.
Native early version succeeds before DISCOVER, matching Linux probe order.

The current6.18.52 reset map now reconstructs exactly and passes147 IDs/23,088
host and5,007 AArch64 instruction cases. Its independent-engine coverage is
still not a physical containment certificate. Full world/source/image checks
pass; latest FIT `b0400eaa...`, previous `05ca2802...` preserved. No flash/contact.
Full strict setup, physical containment/retirement and clients remain open.
Evidence: `research/checkpoints/2026-10-10-npu-boot-launch/REPORT.md`.

## 2026-10-10 - Checked Loader And Mainline Pair Packaging

The normal experimental image now packages the checked MT7996 CODE/DATA pair.
The actual Linux loader checks its ABI/digests and zero session storage, obtains
a nonzero runtime random identity, publishes the real private memory/request
plan and identity, and checks SRAM readback. Exposed DMA mailboxes are retained;
same-instance reload and retained-device rebind are rejected. Retirement is not
implemented, so the module remains pinned after exposure.

Actual-C fault/mutant tests, all-hart native boot from C-published bytes, full raw
RX/TXDONE/BA replay, independent assembly, two package builds and incremental
manifest refresh pass. Latest offline-verified FIT: `05ca2802...`; previous images
are preserved. No flash or router contact. Physical cold containment, complete
strict setup, other owners/hot lifecycle, drains/recovery and clients remain open.
The newest entry defines current state; older dated entries retain their original
scope. Details: `research/checkpoints/2026-10-10-npu-loader-publish/REPORT.md`.

## 2026-10-10 - Provider Request Plan Bridge

The actual MT7996 provider now preflights its coherent mailbox before copying
firmware and prepares the native six-region private snapshot. Actual-C guards/
mutants and raw-native dynamic-address bootstrap pass. Full world/60-file replay/
offline image checks pass; the new FIT is `8efb19fb...`. The previous image is
preserved. This does not publish SRAM/identity, establish reset containment or
install the raw pair. Full strict setup, lifecycle and physical acceptance remain
open. Details: `research/checkpoints/2026-10-10-npu-provider-plan/REPORT.md`.

## 2026-10-10 - Paired Raw NPU Build

The checked native composition now builds a complete raw CODE/DATA pair through
the canonical `pair` target. Independent builds are byte-identical. Fifteen
assembly groups, full raw-only replay with3,072 packet/1,792 page claims and
failure controls, plus actual-provider-C exact-pair copy tests pass. No ELF bytes
are injected after raw loading. Eight build-runner/offline image checks pass.
This is an assembled artifact with modeled platform inputs, not a flashed or
physically accepted replacement. Real loader/storage/identity-plan publication,
strict setup and full lifecycle/physical gates remain. Reproduction and receipts:
`research/checkpoints/2026-10-10-npu-raw-pair/REPORT.md`.

## 2026-10-10 - Shared RX/TXDONE Packet Claims

TXDONE now uses the same retained packet state as RX0/RX2 in native instruction
composition. The full prefix/ring retains 3,072 claims; complete native RAM/SKB,
ordered locks, 25 controls and six mutants pass. Full RX/page regression and
unchanged-image checks also pass. Readiness now rejects late plan/history/bitmap
corruption without reclaiming resources. The real loader still installs the
vendor pair, not these linked hooks. Evidence and the exact installation gap:
`research/checkpoints/2026-10-10-npu-cold-txdone/REPORT.md` and `INSTALL_TRACE.md`
in that directory. Real loader/strict setup/hot lifecycle/physical gates remain.

## 2026-10-10 - Cold RX Packet Ownership

The normal RV32 archive now includes a distinct cold packet ownership profile.
Selected RX0/RX2 callers execute original lock/initializer instructions with
retained claims, immutable table identity and guarded release/readiness.
The 61-site composition passes 2,560 packet claims, 50 controls and six mutants;
1,792 separate BA-page claims leave packet state unchanged. Exact core/sanitizer,
page/statistics regression, full build/source and offline image checks pass.
This is native-emulated integration, not a replacement vendor blob or physical
acceptance. Full setup, other owners, hot lifecycle and hardware gates remain.
Evidence and remaining work: `research/checkpoints/2026-10-10-npu-cold-packet/REPORT.md`.

## 2026-10-10 - Checked RX Statistics Callers

Original RX0/RX2 statistics allocation now uses the checked active-callback
path in native instruction composition. Guards stop failed statistics clears,
RX initialization and readiness while retaining resources. Two nominal rings,
26 controls/six mutants and startup/page/postgate regressions pass. No vendor
blob, loader or physical acceptance is implied. Details and next gates:
`research/checkpoints/2026-10-10-npu-rx-stats/REPORT.md`.

## 2026-10-10 - Native Page Ownership Composition

The shared ownership core now publishes validated native queue heads. Checked
DESC5/6/7 caller composition runs original initializer instructions and prevents
false outer success/readiness after allocation or late-publication faults.
The 54-site replay passes 1,792 claims, 48 controls and six binding mutants;
exact archive replay, sanitizers, full build and offline image checks pass.
This is native-emulated caller integration, not a replacement vendor blob or
hardware acceptance. Remaining gates and receipts are in
`research/checkpoints/2026-10-10-npu-cold-page-native/REPORT.md`.

## 2026-10-01 - Mainline Follow-Up

The user authorized merging the cold-page work and final test-runner change
into `main`. The runner now accepts the exact compiled RV32 core object and
records its path/hash. Fresh source and archive-member replay each pass 5,702
calls, 294 controls and ten mutants with sanitizers; eight build-runner tests
and offline image verification also pass. See the final receipts in
`research/checkpoints/2026-10-01-npu-cold-page/REPORT.md`.
The core remains unwired to native callers; physical acceptance is still open.
No flash or hardware change accompanies this source integration.

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


Canonical workspace for W1700K firmware development, WiFi/MLO fixes,
and stock host-adapter/NPU reverse engineering.

## Current State

Updated 2026-10-10. The objective is complete stock-NPU reverse engineering and
implementation, including host/firmware integration and hardware validation.

The active source is the **unified experimental non-OC merge**, pinned to
OpenW1700k `288d79449f`, Linux **6.18.52**, and mt76 `01367e60`.
Our provider/driver corrections and Linux control client are build inputs, with
WLAN NPU enabled. The RV32 core has a normal build target. There is no separate
release-ready versus experimental source track. Build and hardware verification
remain distinct. The complete image builds and passes offline FIT/board/package/
module checks as `r36536-merged-288d79449f`. The September 23 image passed a user-authorized flash, basic boot and wired
management checks, with unchanged protected storage. At that checkpoint, Wi-Fi
remained blocked by the retained channel-161/SA validation error seen before
flashing. Current hardware state must be rechecked; client traffic and complete
NPU recovery are not validated.
See the [physical boot report](research/checkpoints/2026-09-23-nonoc-flash/REPORT.md) and the
[merge report](docs/NONOC_MERGE.md) for the image path, SHA256 and test receipts.

The current source also validates and snapshots the MT7996 WLAN
memory plan before either firmware copy. Generic/PPE-only profiles retain their
optional WLAN behavior and caller-local setup plans. The September30 host-C
replay passes 273 loader cases, 165 additional load scenarios, three original
failure controls, nine rejected mutants, 6,174 retry cases and 44 V2 executor
cases. This change is integrated in the canonical patch/source lock and now has
a compiled/linked AArch64 provider module and ten RV32 objects at that checkpoint;
its full image passes offline FIT/board/firmware/218-package/78-module checks.
The candidate has not been booted or flashed. See the
[cold-memory checkpoint](research/checkpoints/2026-09-30-npu-cold-memory/REPORT.md)
and [completed cloud validation](research/checkpoints/2026-09-30-npu-cloud-build/REPORT.md).

That source and its deferred history documents were synchronized back to
the local WSL checkout. The preceding full local build passed the same offline checks;
the packaged NPU provider matches the cloud module byte-for-byte. The local
FIT has its own SHA256:
`277abd0b754200a0b330a35d4c759f264f918ec182cddc6c650fb734f46b4e4b`.
The host suite also passes with LeakSanitizer enabled. See the
[WSL sync checkpoint](research/checkpoints/2026-10-01-wsl-sync/REPORT.md).

Native startup continuation fixes hart7's first-boot allocation phase mismatch
in the shared replay binding. With all 50 detours installed, hart7 now reaches
its outer loop under explicit host-publication and hardware models; other
workers still await later host setup. This is not a new packaged firmware or
physical boot claim. See the
[postgate checkpoint](research/checkpoints/2026-10-01-npu-postgate/REPORT.md).

The latest production correction covers the MT7996 INODE wrapper's 24-byte
read span with zero-extended short requests. Other valid profile/command frame
lengths and caller bytes are preserved; invalid lengths and NULL-positive-data
are rejected before allocation/copy. Actual provider C and the packaged
AArch64 sender each pass 1,056 frame cases and 30 controls. All 16 original
RV32 wrapper entries accept those emitted bytes within their declared extent;
five mutants are rejected. The full image and 60-file source replay pass.
Preceding local FIT SHA256:
`031f7bd2b28e0507ddfe810602a7edef71c63900244935e7d460ab58ab35a0cc`.
This image has not been flashed. Native selector readiness, physical delivery
and complete recovery remain open; padding is not a proved Wi-Fi root-cause
fix. See the [INODE framing checkpoint](research/checkpoints/2026-10-01-npu-inode-frame/REPORT.md).

The formerly entry-only DESC5/6/7/8 consumers now execute their complete native
helper paths after RX0/RX2 initialization. Four nominal cases, 48 controls and
five native mutants establish their descriptor/ID footprints and failure state.
A DESC6 count of 513 corrupts the arena pointer despite an outer success reply.
The production provider now bounds the selected MT7996 page/indication requests
before transport; actual C and packaged AArch64 instructions/table each pass
12,096 cases and 384 rejections, with six provider mutants rejected. The full
build, image/source checks and INODE/memory regressions pass. Latest FIT SHA256:
`230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe`.
This is not a native allocation-failure, full attachment or physical acceptance
fix. See the [page-ring checkpoint](research/checkpoints/2026-10-01-npu-page-rings/REPORT.md).

The preceding paired-loader source checkpoint is [`ac4c639`](https://github.com/MCShotty/W1700KNPU/commit/ac4c6390f070d5f5e0e4e7365e96cbaa89c99d89).
It preflights both NPU firmware images before either copy, rejects empty images
and releases acquired firmware on error. The correction is included in the
unified kernel patch and source lock. The earlier flashed image predates it.

The following target-object/source-tree evidence applies to that preceding
paired-loader checkpoint, not the newer memory-plan change:

| Verification | Paired-Loader Evidence |
| --- | --- |
| Firmware pair loader | 273 actual-C host cases, four original failure controls and six rejected mutants |
| Provider build | Complete before/after AArch64 objects on Linux 6.18.52; strict checkpatch passes |
| Existing regressions | 109 memory, 6,174 retry and 44 Linux V2 control cases |
| Source reconstruction | All 60 locked OpenWrt/LuCI files replay; kernel patch reproduces the tested provider |
| Independent readback | 174 referenced files match their SHA256 fingerprints |

The [loader checkpoint](research/checkpoints/2026-09-30-npu-loader/REPORT.md)
records the software tests and reset-domain review. The paired-loader change is also included in the September 30 cold-memory
candidate, which now passes full offline image verification. That candidate
has not been booted or flashed.

The retained rollback baseline is **Daybreak21 WLAN-DMA R1 (2026-09-05)**,
Linux 6.18.44, SHA256
`0788f405337ceb030d873463bbf278497dcd9b86e8f75a1a3f57fd318eda195f`.
It deliberately compiles out WLAN NPU support; Ethernet offload is separate.
Stock NPU parity is **not complete**. Synthetic radio/MLO and LuCI save checks
passed; actual-client association and throughput acceptance remain open.

Start with [current reference](docs/W1700K_STOCK_PORT_CURRENT_REFERENCE.md),
[ledger](docs/W1700K_STOCK_PORT_LEDGER.md), and
[logging session](docs/W1700K_STOCK_PORT_LOGGING_SESSION_20260625.md).
The [remaining-work checklist](docs/REMAINING_WORK.md) is the resume plan.

## Remaining NPU Work

- Establish contained cold-provider reset and ownership of every affected engine.
- Independently prove physical backing/cache/DMA contracts; software loader
  identity/publication and initial DISCOVER/setup/BIND are implemented.
- Complete strict RXDESC/host/TX-buffer/INODE/TXDONE/final IRQ setup and recovery
  callers; initial RX/page/indication/ACK/TX0/TX2/token setup is implemented.
- Complete native postgate execution, physical DMA drains, teardown and rearm.
- Validate sustained traffic, recovery and actual Wi-Fi/MLO clients on hardware.

The current Wi-Fi channel/regulatory configuration, stale status-script source
labels and boot-environment/NVMEM warnings also remain on the checklist.

## Layout

- `firmware/`: pinned public source revisions, full cumulative OpenWrt/LuCI
  patches, tracked overlays, RV32/host components and the build configuration.
- `tests/`: actual-source fault harnesses, emulation and source-replay checks.
- `tools/`: reproducible workspace preparation and migration verification.
- `research/`: preserved historical patches, tests, Ghidra exports, audit
  reports, and manifests. Archived experiments are not active build inputs.
- `releases/`: selected current/rollback release material and provenance.
- `docs/migration/`: migration, privacy screening, cleanup and path records.
- `.build/`, `.local/`, `.migration/`: ignored builds, protected local data and
  temporary staging. Never commit private keys or device-specific backups.

See [migration and cleanup report](docs/migration/REPORT.md) for exact retained
archives and retirement receipts. Historical source/research is provided as a
checksummed archive with 49,891 entries and a searchable JSON manifest. Large
binary inputs use `.parts.json` manifests; `tools/restore_artifact.py` restores
the original file with end-to-end SHA256 verification.

## Build Preparation

Use a native Linux filesystem, including WSL ext4 or the authorized cloud
checkout. The current local checkout is `/home/captain/W1700KNPU`,
accessible in Explorer at `\\wsl.localhost\Ubuntu\home\captain\W1700KNPU`.
The registered Ubuntu backing disk is under `D:\WSL\Ubuntu`.
The earlier `D:\W1700K-Recovery` snapshot location was absent in the
2026-09-30 directory check. Verify current recovery material before using
historical backup paths.

For a fresh destination:

```sh
python3 tools/prepare_build.py --destination .build/local-openwrt
python3 tools/build_firmware.py --destination .build/local-openwrt --target tools/install --name local-tools
make -C .build/local-openwrt package/firmware/linux-firmware/prepare V=s
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tools/build_firmware.py --destination .build/local-openwrt --name local-build
```

On this WSL executor, the working build is `.build/merged-openwrt`; the earlier
`.build/openwrt` is retained as a rollback/evidence reference. Use fresh
destination and log names; the preparer refuses an existing destination and
verifies every locked changed source file. It does not flash a router. Image
signing keys are not uploaded; fresh build keys must be generated or supplied locally.
An existing imported build may instead be reused as recorded in migration docs.
The cloud transfer contains source/evidence. This computer's existing WSL build
was refreshed and rebuilt after synchronization; other executors must prepare
their own build trees and local credentials.
The combined builder compiles the RV32 archive and checked raw pair using host
Clang/LLD with RISC-V support and `ar`. Python needs Unicorn, Capstone and
pyelftools; the local dependency directory above supplies the existing tested
versions. The hash-pinned original pair comes from prepared linux-firmware, or
an explicit workspace `--npu-firmware-directory`. Pair staging is validated
before package installation, and all three staged files are package dependencies.
The archive itself is not raw CODE. Runtime loader publication is implemented;
physical cold containment/retirement, complete strict setup and postgate remain
unfinished. The builder and verifier never contact a router.

For the portable current provider/loader/retry/V2 host checks (GCC and Git):

```sh
python3 tests/npu/test_cold_memory_plan.py --name readme-cold-replay
```

Address, undefined-behavior and leak checks are enabled by default. Hosts that
cannot run LeakSanitizer can explicitly use `--disable-leak-check`; the receipt
records the reduced coverage.

With the pinned build and Python ELF tooling available, verify current source
replay and the built image using fresh result names:

```sh
python3 tests/test_prepared_sources.py --name source-readme-replay
PYTHONPATH=.local/npu-reset/python-lib python3 tools/verify_merged_image.py --name readme-image-check
```

Older paired-loader/prepared-driver runners use checkpoint-specific `.local/`
snapshots. Their reports identify the source context needed to replay them;
the portable memory-plan suite above covers the current provider.

Do not force old `ubi2` recipes onto current images: the latest board is
`gemtek,w1700k-ubi`, with the OpenWrt U-Boot layout and compatibility metadata.
Validate the actual device and the exact FIT/DTB/sysupgrade metadata before use.

## Preservation Rules

Private router backups, factory/calibration, bootloader dumps, signing keys and
the recovery VHD stay local. Original historical files with suspected credentials
are quarantined locally rather than uploaded. Historical paths and test outcomes
are retained as evidence, not silently rewritten into claims of current support.
Upstream source licensing applies to source/diffs; stock vendor materials are
analysis inputs, not a blanket redistribution license or approved module port.
