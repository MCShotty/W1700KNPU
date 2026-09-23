# Remaining W1700K Work

## Active Merge - 2026-09-23

The current source lock now targets the unified experimental non-OC merge:
kernel 6.18.52, mt76 fork 01367e60, WLAN NPU enabled and the implemented host/
provider corrections included. See `docs/NONOC_MERGE.md`. The cross-toolchain,
complete image, 60-file source replay, focused driver/emulation tests and offline
FIT/board/package/module verification pass. The user's new instruction
supersedes the former policy of leaving implemented candidates outside the
build; historical checkpoint descriptions below retain their original scope.
Physical testing remains deferred and the full NPU implementation is incomplete.
The new local image is `r36536-merged-288d79449f`, SHA256
`132a35c746e008345032d1c862ea1ace1ef7a27d87a3fd363b8225045554e670`.

Updated 2026-09-23 from the reset-control prerequisite, Linux V2 executor, linked provider/host candidates, RX ownership,
parser and CPU lifetime, V2
composition and earlier NPU/Wi-Fi evidence. This is the resume checklist, not a completion percentage.
The current source includes the detached-provider allocation guard and mailbox
publication/timeout-ownership fix (patch 926) and memory preflight (patch 927,
kernel/ABI/Ghidra verification passed). The last
router-tested release is still Daybreak21 R1 with WLAN NPU compiled out.
The last recorded router state additionally has userspace script hotfixes and a companion
nl80211 userspace library fix; this is not a new tested firmware image.

## Resume Blockers

The merge includes the newer platform/Wi-Fi/userspace sources and all currently
implemented host/provider corrections. It does not authorize router contact,
flashing or subagents. Remaining NPU implementation priorities are:

- Establish contained cold-provider/reset lifetime and complete engine coverage.
- Implement fresh loader identity, storage reservation and publication.
- Wire Linux executor initialization and actual setup/recovery callers with the
  required DISCOVER/setup/BIND order and correct lifetime ownership.
- Complete postgate/native hooks, physical drains, teardown and cleanup/rearm.
- Perform separately authorized hardware and real-client acceptance. The new
  image's static/build verification is not a substitute for these tests.

## Pre-Merge Checkpoint Context

The entries below retain the scope of their original checkpoints. Their
"unpromoted" and isolated-build labels are historical; the implemented source
changes are now in the unified build. The new full build uses its own mac80211
symbol index, not the temporary reconstructed index described below.

Tracing the cold-provider prerequisite found defects in the shared reset
primitive. Unpromoted candidate 930 initializes the requested value and returns
register read/write errors. The pinned driver reconstructs from the kernel
archive and eleven source patches. All 147 reset mappings pass 23,088 host
cases, four original failure controls, seven mutants and four AArch64 object
builds. Native before/after callbacks each execute 5,007 cases: this target
compiler happens to preserve normal polarity, but the original suppresses
3,087 injected register errors. Independent readback verifies 132 files.
Regmap/MMIO remains modeled. No provider reset wiring, physical containment,
fresh loader identity/publication or cleanup permission is established; these
remain prerequisites for V2 caller integration. See
`research/checkpoints/2026-09-23-npu-reset-control/REPORT.md`.

The new Linux V2 executor serializes full provider exchanges, checks intended
operations, preserves the first error, rejects reinitialization and joins CPU
calls on close. Forty-four ASan/UBSan host cases, six mutants and two linked
AArch64 module profiles pass; four shared layout values match and 83 files
independently hash-verify. Mutex/regmap/storage/delivery dependencies are modeled;
the disabled profile changes test headers only. Initialization still requires a
caller-established cold provider lifetime and fresh nonce. Consumer attachment
does not prove that condition, so the executor is not yet wired into mt76.
Loader identity/placement/publication, bootstrap ordering, provider/caller
lifetime and physical drain/recovery remain open. See
`research/checkpoints/2026-09-23-npu-linux-control/REPORT.md`.

Provider candidates 928/929 now compile and link into an isolated copy of the
prepared AArch64 kernel. Its configuration is unchanged; regenerated exports
include get/put and `airoha_npu_wlan_control`. The three retained NPU-enabled
mt76 modules relink against it, and an unloaded probe links the new control
API. Actual mt76 still calls only get/put; V2 client integration remains open.
The temporary 351-export mac80211 dependency index remains necessary. The
build records 65 kernel, three mt76 and one probe description warnings under
the target's stripped-metadata configuration, with no compiler/unresolved-symbol
error. Independent readback matches 45 files. No candidate promotion, module
load or image/runtime acceptance; physical DMA and full lifecycle/recovery
remain open. See
`research/checkpoints/2026-09-23-npu-provider-kernel-link/REPORT.md`.

Unpromoted patch 009 now prepares bounded views in the shared MT7996 RX parser,
retains nonlinear data bodies, snapshots RX-vector metadata across header edits,
checks absent stations, and bounds common control dispatch headers. Actual
selected parser/radiotap C passes 7,680 baseline/613,113 corrected executions,
five original failure controls and eleven mutants. Four driver objects and two
AArch64 layout probes pass with 25 matching values; 176 file hashes verify.
These are modeled-dependency host tests and object builds, not complete receive
or hardware acceptance. Firmware-event bodies/TLVs, callback/stack semantics,
metadata provenance, physical DMA and full lifecycle remain open. See
`research/checkpoints/2026-09-23-npu-rx-parser/REPORT.md`.

The interrupted host RX ownership draft now has an unpromoted patch and passing
receipt. Complete fragment readiness and mapped lengths are validated before
skb ownership transfer; incomplete/allocation-failed packets retain their ring
buffers. Complete rejected packets consume budget, and zero-budget polls avoid
page-pool refill. 3,228 baseline/3,376 corrected host cases, eleven mutants, six
AArch64 objects and strict checkpatch pass; 127 file hashes independently match.
This is selected host C against explicit dependency models, not physical DMA
or full RX parsing proof. Zero/short payloads, downstream RXD/header/group and
nonlinear views, producer publication, concurrent refill/removal and full
lifecycle/drain/rearm remain open. No packaged source or router change. See
`research/checkpoints/2026-09-16-npu-rx-ownership/REPORT.md`.

Two unpromoted host-lifetime candidates now initialize provider watchdog work
before IRQ publication, order managed cancellation after IRQ teardown, and
wait for old mt76 RCU readers before dropping provider references. Those
references also remain held through the detach function's queue cleanup.
161 baseline/193 corrected provider cases, 24 RCU schedules per version, four
mutation controls, 12 AArch64 kernel objects and strict checkpatch pass.
These are function-local CPU lifetime fixes, not safe whole-device removal:
MT7996 unregister releases tokens/rings earlier, consumer IRQ/NAPI shutdown is
not certified, and an independent DMA actor remains active through cleanup in
the model. Full probe/unregister/reset ordering, actual DMA containment and V2
client/provider integration remain open. No packaged source or router change.
See `research/checkpoints/2026-09-16-npu-host-lifetime/REPORT.md`.

The V2 bootstrap binding now reaches all eight initial parking gates with all
50 retained detours installed before reset. The isolated builder relinks the
dependent components against V2 and rejects a stale V1-linked control. Four
banked-PLIC startup profiles, six cold rejections, three allocator failures,
seven missing-hook controls and a flat-PLIC limit control pass, with 209 host
and 96 server comparisons. Checked allocator/reset placement, the full command
ring and the 68 KiB bridge definition remain selected; no postgate packet work
executes. Initial all-hart composition is covered, not complete NPU boot.
The flat model loses mailbox enable despite successful direct handler calls,
so physical PLIC/delivery remains open along with loader identity/coherency/
placement, postgate startup, provider/mt76 lifetime, physical drains and safe
cleanup/rearm. No firmware C, source-lock/overlay, image or router change. See
`research/checkpoints/2026-09-16-npu-bootstrap-composition/REPORT.md`.

The V2 bootstrap adapter now admits exact pinned 12/80-byte frames and defers
BIND until the selected six setup commands finish. The existing bootstrap
requires admission to remain unbound during setup; early BIND is now consumed
and rejected without blocking those commands or becoming effective on replay.
Missing/stale session identity fails through the native cold-start gate.
Three native core0 scenarios, six early-BIND cases, six cold failures, six
callback failures, 28 transport rejections, 786 policy cases, eight mutants and
453 sanitizer assertions pass. Standalone V2 regressions remain compatible.
This is a tested core0 path to 0x8400e330, not full all-hart/postgate boot or
physical containment. The guard patch is staged, not applied to baseline V2 or
packaged sources. The newer checkpoint above adds retained-detour/initial-
parking composition; production loader identity/placement/publication,
postgate boot, provider/mt76 ownership and physical drains/rearm remain open.
See `research/checkpoints/2026-09-16-npu-bootstrap-control/REPORT.md` and
`firmware/npu/BOOTSTRAP_V2_CONTRACT.md`.

The unpromoted V2 control candidate now rejects stale wire replies, wrong boot
identities, unbound STATUS and duplicate failed-BIND replay. It uses an 80-byte
envelope, not V1 fallback. 830 host and 254 server differential comparisons,
21 scenarios, 51 malformed/boundary cases, six mutants and eight saved worker
contexts pass. Original firmware and both closed/open V1 endpoints reject it.
The unchanged V1 suite reproduces its prior receipt exactly.

The provider GET wrapper cannot carry this outbound body. Candidate patch 928
adds a dedicated bidirectional control entry: 290 ASan/UBSan assertions, six
AArch64 kernel-context objects and strict checkpatch pass; public struct/ops
layout is unchanged. The candidate remains outside the packaged source lock.
The real loader still needs fresh identity generation/publication and approved
state placement. The original 12/64-byte transport is unchanged; the newer
candidate above selects an explicit 12/80-byte bootstrap adapter. Complete
all-hart/postgate and production-loader integration remain incomplete.
mt76 binding, exact provider/callback lifetime, physical drains, ownership-safe
cleanup/rearm and full boot remain open. Software PARKED is not reclaim authority.
See `research/checkpoints/2026-09-14-npu-control-v2/REPORT.md` and
`firmware/npu/CONTROL_V2_CONTRACT.md`.

An unpromoted host control client now encodes/validates V1 DISCOVER/BIND/STOP/
STATUS, enforces the exact stop epoch and one outstanding local ticket, and
holds on failures or abort. 6,443 x86/AArch64 comparisons, eleven round trips
with eight saved RV32 contexts, twelve firmware scenarios, ten mutants and
ASan/UBSan pass. It observes software parking only; even a synthetic complete
drain mask cannot authorize reclamation or restart. V1 STATUS echoes rather
than validates the session and has no per-request wire sequence. Two retained
controls expose same-epoch replay and replacement-provider ambiguity. Exact
provider/transfer identity and lifetime, coherent pinned transport storage,
Linux host integration and physical recovery remain open. This helper is not
connected to L1 cleanup and does not close the following stop/drain blocker.
See `research/checkpoints/2026-09-14-npu-control-client/REPORT.md` and
`firmware/npu/CONTROL_CLIENT_CONTRACT.md`.

An unpromoted L1 host candidate now checks stop/setup failures, attached-NPU
MCU recovery timeouts and provider detachment before cleanup. It keeps reset
state and host queues held, masks provider IRQs, and latches a failure so later
work cannot re-disable NAPI or escalate through this worker's full-reset path.
NPU setup precedes data-DMA/WED restart, including suppression of the earlier
reset-mode WED start when NPU is attached. 48 nominal and 240 failure host-C
pairs, twenty inactive controls, six mutants, four complete AArch64 driver
object builds and strict checkpatch pass. Stop errors retain original buffers;
setup errors hold the state reached after earlier cleanup. Legacy STOP/GET
success still does not establish quiescence: a control retains independent
NPU activity while the caller proceeds to cleanup. Genuine drains, full reset/
removal, provider lifetime and a safe rearm path remain open before promotion.
See `research/checkpoints/2026-09-14-npu-l1-recovery/`.

SRv6 packet extents now have an unpromoted C preflight and two native adapters.
Ingress supplies wire length plus a 32-byte descriptor; the new checks cover
that count, captured L3 offset/header length, source extents and ordinary IPv6
payload-length arithmetic before packet writes or submission. Tail offset now
uses 32 + L3 offset, removing the native extra four/eight inner bytes in the
selected tagged-frame cases. 2,037 helper comparisons, 33 accepted native flows,
fourteen early rejections, four controls and eight mutants pass. Native ingress,
alias construction and worker dispatch execute against explicit FIFO/storage
models; packet byte assembly is modeled, not physical DMA. All 50 detours retain
every initial gate. Content/MTU checks, normal packet rejection/backpressure,
other tunnel encoders, ownership/cache and complete boot/recovery remain open.
See `research/checkpoints/2026-09-10-npu-tunnel-packets/packet-extents.json`.

Egress submission now has three unpromoted native guards. Invalid channels
are stopped before register indexing; the generic 0x8400178e builder checks
length/offset width and the 29-bit source extent before truncation. A failed
availability check at 0x8400159e latches the barrier fault and holds the caller
with its failed request retained. Native multi-command paths no longer submit
the remaining commands or a follow-up release after that failure. Already
issued commands remain outstanding; no drain, rollback or reclamation is proved.
136 successful comparisons, 13 malformed inputs, 15 native failure scenarios,
eleven controls and eight mutants pass. All 48 detours retain every initial
gate. Other encoders still truncate arithmetic; queue reservation/backpressure,
packet/MTU validity, actual backing/ownership, cache/PMA and full boot/recovery
remain open. See `research/checkpoints/2026-09-10-npu-egress/egress-guards.json`.

Tunnel header bounds now have unpromoted C checks and five native adapters.
VXLAN indices stay within twenty slots; SRv6 stores stay within eight 128-byte
slots and declared message lengths. The consumer rejects stored lengths at
or below its twelve-byte skip and above 128 before descriptor/command writes.
Captured indices/lengths prevent check/use rereads from changing the extent.
5,370 helper comparisons, 46 native cases, ten mutants, eight ABI checks and
the all-45-detour retained-gate control pass. Actual backing/ownership and
atomic configuration are not proved: forged length metadata still permits
a source read stopped only by the fixture. General packet/MTU/translation
bounds, engine errors, cache/PMA, full loader/lifecycle and boot/recovery
remain open. Evidence is in
`research/checkpoints/2026-09-10-npu-tunnel-headers/`.

A 44-byte unpromoted ordering sidecar adds four IORW fences at three native
queue boundaries. 96 herd/RVWMO cases cover stale payload, premature slot reuse
and successful handoffs across all sixteen fence masks. The required ordering
excludes selected bad outcomes under ordinary coherent-memory assumptions;
producer acquire is redundant in this particular projection. 384 original/
corrected register/CSR comparisons and 8,194 native queue pairs pass. All 40
detours installed before reset retain every initial gate. Both new receipts
replay byte-for-byte, including the default unfenced layout regression.
This does not establish the target's cache/PMA/alias or initialization visibility.
Full pointer/reentry/index ownership, all consumers and loader/lifecycle paths,
performance, physical containment and full NPU boot/recovery remain open. No
image or router change. See
`research/checkpoints/2026-09-09-npu-ring-order/REPORT.md`.

The preceding capacity-preserving placement remains unpromoted:
The checked allocator now accepts immutable non-overlapping typed placements
outside the primary heap, preserving native records and cached lookups. An
unpromoted ELF profile relocates the full 2,048-slot command ring plus its
extra sixteen bytes. Actual core0 startup and a 68 KiB bridge now fit with
24,352 heap bytes left; four selected native header operations stay inside
the bridge. Compiled postboot allocations for types 2, 9 and 10 leave 16,152
bytes. Descriptor and SKB capacities remain unchanged.
2,362 allocator differential cases, 64,000 pthread calls, 8,194 native queue
pairs, 28 mutation controls and default startup failure/control regressions
pass. All 37 retained detours still park every hart with the larger bridge
definition present. Three receipts replay byte-for-byte.
This closes the selected arithmetic deficit, not complete relocation or boot.
The native ring producer/consumer contain no publication fences. Full pointer
alias closure, cross-hart cache/PMA/ordering, loader backing/fresh initialization,
all allocation profiles and consumer bounds remain open before promotion.
No image or physical test. See
`research/checkpoints/2026-09-09-npu-command-ring/REPORT.md`.

The earlier bridge-sizing checkpoint remains the baseline counterexample:
The bridge's 58,879-byte allocation is now disproved as backing for its native
header consumers: the getter returns base plus 65,536. Four ordered component
stores overwrite the following descriptor allocation. After actual core0
startup, the first header write attempts an address 4,352 bytes beyond the
declared heap. Eight primitives and two startup cases pass with exact memory/
write checks and byte-identical replay. A 68 KiB sizing hypothesis contains
the selected header stores but exceeds the startup heap by 8,448 bytes; the
checked allocator holds before publication. No layout change is promoted.
The native SKB initializer hard-codes 28,672 entries and the later host token
count is 8,192: allocation, initialization, host-count changes and all consumers
need a consistent capacity contract. Complete profiles, placement and consumer
index/length bounds remain open. The new read-only Ghidra export helper did
not execute because of the local signing policy; verified existing exports
and native instruction tests supply this evidence. See
`research/checkpoints/2026-09-09-npu-memory-budget/REPORT.md`.

An unpromoted host TXFREE preflight now checks selected queue ownership,
pointers, 512-entry metadata and DMA alignment/width/native-range/aperture
bounds before attachment helpers. Normal source already allocates 512
sixteen-byte descriptors. 152 host-C cases, nine mutants, 34 unchanged controls,
ten AArch64 objects, strict checkpatch and 22 native bridge cases pass with
byte-identical receipt replay. Native SET22/DESC10/SET0 consume recorded host
messages; the descriptor pointer is not preseeded. All 83 inputs of the
preceding TXDONE checkpoint remain unchanged.
This is a metadata-dependent guard, not actual DMA/lifetime proof: forged
count after short allocation still reaches an emulator-only stop. Three
timeout-delivery models reach native ready despite host failure and retain
published memory. Earlier queue MMIO publication, global ownership, mapping/
cache, complete attachment, containment and recovery remain open. Strict API1
stays closed. No candidate is promoted to the overlay. See
`research/checkpoints/2026-09-09-npu-txfree-host/REPORT.md`.

Selected cold TXDONE initialization now has six unpromoted emulator detours.
They enforce request/count and selected metadata bounds, check bufid/SKB lock
ownership, retain partial state and propagate local helper failures before
ready publication. The temporary SKB scan is bounded to 2,048 gathered IDs,
preserving normal output. Sixty-two native cases, eight mutants, four integration
controls and four missing-model controls pass whole-memory/exact-write/lock
checks with byte-identical replay. All 37 detours installed before reset keep
all eight harts parked; strict API1 admission remains closed and native RX0/2
fallback is unchanged.
This is not complete attachment or safe recovery. Without the host preflight,
or with forged queue metadata, short backing still reaches an out-of-span
access that only the emulator rejects. Actual
backing, full allocation/global provenance, concurrent publication and physical
ownership/containment must be resolved before admission. See
`research/checkpoints/2026-09-09-npu-txdone-init/REPORT.md`.

Seven reviewed core0 startup calls plus hart7 bridge allocation now use the
checked core. Native ordering verifies IRQ8/control installation precedes all
seven core0 calls. Eighteen failure cases pass: thirteen preserve control
service through the existing faulted idle, and five invalid interrupt/active
contexts hold without claiming service. Fifty-two control replies, thirteen
rejected legacy-version queries, five hart7 cases, eight mutants, 36 preserved
lookups and the 31-detour retained-gate control pass with byte-identical replay.
Whole metadata/SRAM/heap/L2 checks apply; no failed caller resumes or gains
release/ready/drain/arm permission. This remains unpromoted. Other dynamic
callers, active-callback failure/IRQ repair, complete memory budget and physical
ownership/containment/recovery remain open. See
`research/checkpoints/2026-09-09-npu-cold-allocator/REPORT.md`.

Native cold reset was forgetting a published four-byte control allocation.
The following ID pool reused its address, and the actual control writer altered
pool entries. An unpromoted reset-order correction now preserves that lifetime.
Five original/corrected primitives, four mutants, full core0 startup, four
checked bridge cases and all 31 installed detours/retained initial gate pass.
Whole-state/heap/ID/L2 checks and byte-identical replay verify the modeled scope.
The word costs 32 aligned bytes; 2,305 remain after the bridge. Type-2 allocation
then exceeds the declared heap by 3,864 bytes in the original allocator and is
rejected unchanged by checked native/RV32 C. Full budget, remaining-caller
error retention, physical containment/ownership and production integration are
still open. No safe active-reset claim. See
`research/checkpoints/2026-09-09-npu-allocator-reset/REPORT.md`.

The checked allocator core and hart7 bridge call-site binding are implemented
and unpromoted. 1,367 native/RV32 pairs, eight mutants, 32,000 pthread calls,
48 original comparisons, four native counterexamples and eight bridge cases
pass. Failed ownership/metadata/capacity checks preserve metadata and hold
before bridge publication. All 29 detours with the first gate retained still
park all eight harts without bridge work. The follow-up above covers seven
reviewed core0 startup sites; other dynamic callers still use native allocation.
Original type-2 after core0 plus bridge exceeds the declared heap by 3,832 bytes;
checked rejection exposes an unresolved complete-allocation budget, not a
working full cold-init sequence. The 58,879-byte/64 KiB bridge discrepancy,
global failure integration and physical ownership/cache remain open. See
`research/checkpoints/2026-09-09-npu-allocator/REPORT.md`.

Native hart7 bridge startup now has two unpromoted failure guards. Fifty-two
before/after cases and seven mutation controls pass;20 guarded failures hold,
including18 late-ready cases. Coordinator STATUS exposes the fault, while
ready/drain/release remain zero. Four missing-model controls and a retained
initial-gate/all-eight-hart control pass. The post-gate analysis deliberately
omits the first gate only in its isolated fixture, not production admission.
The follow-up allocator candidate above checks ownership at the hart7 call;
other allocator callers, bridge extent, real timer/engine semantics and full
cold-init/containment remain unresolved.
See `research/checkpoints/2026-09-09-npu-bridge-startup/REPORT.md`.

An unpromoted host TX correction now resolves the single-HIF source alias/ID
mismatch and duplicate physical descriptor-base writes. Sixty host-C traces,
63 controls, four mutants, four native bridge cases/two controls and eight real
AArch64 object builds pass. RX publication/hardware stay modeled; zero-sized
TX1 still permits native return. Publication can precede later registration or
attachment failure, so containment and production integration remain open.
The patch is outside the firmware overlay. No active-NPU image or router change.
See `research/checkpoints/2026-09-09-npu-tx-topology/REPORT.md`.

The source lock already includes the preceding SAE-file reload follow-up
(receiver `e9bdbed02f2072121083130d1de0dc91996c95217550fd5604fcc641d96e6338`).
That baseline is retained without fresh Wi-Fi or physical validation in NPU work.

MLO security defaults now enable GCMP-256 and SAE-EXT-KEY; native before/after
readback confirms the correction on all three SAE links. Non-MLO defaults and
explicit overrides remain intact. Shell/ucode preflight rejects OWE transition
on MLO/6GHz before file mutation or commit/reload. Generation284, shell63,
desktop/mobile default handlers, five-stage native transitions, rapid13/settled13
and key/missing-marker replays pass. Five userspace files are deployed with
backups; both packages build and40 OpenWrt/3 LuCI export entries reconstruct.
Original config and zero APs/pending changes verify. This does not establish
client compatibility or certification for explicit weaker-cipher selections;
OWE/Enterprise have only generation proof. See
`research/checkpoints/2026-09-09-wifi-security/REPORT.md`.

MLO membership, stale-SSID reuse, failed-file-open removal and same-SSID stale
shared-key admission are corrected. The fingerprinted receiver/generator pass
49 target-ucode checks, two native-marker key replays, a missing-marker replay,
and all13 rapid plus13 settled stages. Prior regression suites also pass.
Original config is restored with zero APs and zero pending changes. See
`research/checkpoints/2026-09-09-wifi-credentials/REPORT.md`.

Multiple simultaneous MLD groups remain blocked by the existing physical-radio
ownership validator before commit/reload, not by proved hardware limitations.
Cross-owner support, remaining security/client transitions, per-station/VLAN changes,
external-file content changes at unchanged paths, UI save/apply and real clients
remain open. The shared wifi-iface fingerprint does not cover those separate
collections/file contents or establish every configuration's reliability.

Ordinary Wi-Fi work resumed under temporary-AP authorization. Twenty-nine AP/
MLO configurations and six further reload stages pass daemon/kernel checks.
Two live script defects and two LuCI loader defects are corrected; source,
package and desktop/mobile widget checks pass. Native decoder allocation-error
propagation closes an independently found empty-dump ambiguity; six original/
six corrected native cases and25 ucode cases pass. Three scripts plus the
companion userspace library are deployed. Seven post-library AP/MLO cases and
four further reload stages pass; final readback has no AP or pending UCI change.
Real-client authentication/traffic and authenticated LuCI save/apply remain
unverified. See `research/checkpoints/2026-09-06-wifi-config/REPORT.md`.

Core NPU work still requires resolution of the tool restrictions. The provider INODE correction and
native DESC5/6/7/8 operations have not been retried or rerouted. The optional
PowerShell collector still awaits approved execution; direct SSH observations
are already complete. Generic goal continuation does not resolve those restrictions.

A fresh L1 source review confirms ignored NPU stop/init returns and DMA restart
before NPU reinitialization. A return-check-only change would not establish
quiescence before token release or cover failed restart/removal, so none was
promoted as a safe recovery fix. Outstanding implementation and acceptance
items below remain open. See `research/checkpoints/2026-09-06-work-blockers/BLOCKERS.md`.

## Priority 1: Safe NPU Recovery

- [x] Implement provider memory-layout preflight before WLAN initialization
  messages. Actual-C and DTB tests reject stale short TX-check tables, invalid
  addresses and overlaps; binary code/backup capacity is checked before copy.
  Kernel/ABI/object validation passes. This does not prove all other buffer
  capacities, hardware containment, complete bootstrap or send-failure rollback.
- [x] Correct the MT7996 TX-check reservation: native initialization clears
  56 KiB, not the previously reserved 26 KiB. The MT7996 include now moves BA
  beyond the full table; three affected DTBs and a generic control verify.
  This is source/DTB proof, not a new image or active-NPU hardware acceptance.
- [x] Establish current firmware STOP/GET limits and stock host mailbox ordering.
  Native RV32 emulation reaches core 5 through the hart dispatcher and reproduces
  descriptor consumption after STOP/GET3 zero. Standalone page-loop reachability
  remains unproven; do not count it as a second active ungated worker.
- [x] Fix mailbox publication order and preserve in-flight request buffers after
  timeout; 143 actual-code model assertions, both variants and kernel compile pass.
- [x] Resolve the conditional stock SER/reset registration path through connac_if,
  GE and PCI tables; original AArch64 instruction tests confirm status masking.
  This is static/model evidence, not proof of a live object's binding.
- [ ] Implement and prove all-worker quiescence or hardware containment before
  token/ring reclamation. Include slow path, both indirect workers, startup and
  in-flight work; close shared copy-engine/IRQ/PPE/tunnel ownership boundaries.
  Current STOP/GET cannot supply this guarantee; longer polling is insufficient.
  An unpromoted eight-hart protocol and 20 emulator detours for seven worker
  contexts and two coordinator/IRQ detours now pass tests, including all-eight
  shared-SRAM acknowledgement, cached-state refresh and IRQ admission. The
  versioned control candidate has no physical reclaim/restart capability.
  Complete boot/helper/IRQ closure, real drains, production placement/cache
  proof and host integration remain unimplemented/unproved. Individual legacy
  payload/indirect-call contracts and strict versus legacy transport also remain.
  The candidate now fits a conservative 32 KiB local SRAM test map with separate
  heap fixtures; reset/BSS/stacks, fixed tables and exact retained FIT reservations
  verify, but this is not a production reservation or complete boot/cache proof.
  Native stock GDMA WAIT polls CT0.ENABLE clear while the RV32 helper polls only
  DONE. Close owner/channel/alias/cache and actual start-clear semantics before
  using this as a physical drain witness; conditional stale-DONE tests are not
  a proved live-device fault.
  An unpromoted guard now enforces known hart/channel owners, pre-idle and
  DONE/ENABLE completion, with fault-only cross-hart publication and no return
  to legacy publishers after failure. All three callers and late completions
  pass native tests, but this is not a physical drain or restart implementation.
  The native boot test proves core 0 waits for SET API 32 before main returns;
  do not close bootstrap commands prematurely. Explicit contained barrier-state
  initialization and complete startup/host-adapter negotiation remain required.
  The unpromoted cold-loader/reset gate now initializes candidate state through
  actual reset entry and rejects stale coordinator entries before BSS clear.
  Its phase/fault race is corrected and tested; physical fresh-load containment,
  complete native boot/IRQ callback installation and checked bootstrap admission
  remain open. API32/API23 unblock initialization; API18 is a no-op. Do not
  equate these callback replies or software READY with physical containment.
  The next candidate now installs strict IRQ8 through original registration,
  serves early version and an ordered, plan-bound six-command MT7996 memory
  sequence, and retains failed callback ownership. A late-cold-hart marker bug
  is fixed. Original core-0 L2/Wi-Fi initialization now executes through return
  and candidate idle ACK in five instruction schedules, with the entire 256 KiB
  L2 image checked. Three missing-register controls fail closed. A subsequent
  actual-reset test reaches all eight first startup gates in 14 model schedules;
  seven missing-gate and six input controls pass. Only each owner writes its
  parked slot with IRQs disabled; STOP stays epoch1 while unreleased. Ready/drain/
  release/arm remain zero. This is not hardware boot/containment proof; actual
  chip inputs and PLIC banking are unverified and post-gate initialization remains.
  Hart7's bridge initializer now executes through native allocation, delay,
  channel checks and the60-byte service-state clear. It originally returns0
  after null allocation or failed channel status. Two88-byte-total test-only
  detours now mask IRQs, order I/O and publish only the shared barrier fault;
  failed startup never returns, writes the failed channel or claims parked/ready.
  Fifty-two cases, seven mutation controls, four missing-model controls and18
  late-ready holds pass. Whole32KiB SRAM/480KiB heap/256KiB L2 checks apply.
  All28 detours with the initial gate retained still park all eight harts with
  no bridge access. The next unpromoted allocator binding adds a 29th detour at
  the hart7 allocation call. Its checked core rejects failed lock ownership,
  invalid metadata and full-extent/cache-capacity failures before mutation;
  the binding holds before publication and retains a committed allocation if
  a concurrent barrier fault arrives at unlock. Eight native bridge cases and
  all-29-detour retained-gate control pass. This does not authorize post-gate
  initialization: other allocator users and unsupported core0 contexts, full memory budget, buffer
  extent/timer/physical ownership and production placement remain unresolved.
  Native success also occurs under forced SKB exhaustion and malformed host-ring
  inputs. Do not treat completion flags or the version fallback as readiness.
  Pinned host traces cover 38 attachment messages; 164 host C and 149 bounded
  callback cases pass. Two native RX descriptor callbacks now execute all helpers
  with 2,560 descriptor/ID and whole-memory checks, 21 negative controls and two
  strict denials. Native TX setup/TXDONE and four API21 selectors now add 17
  valid calls, 73 controls and seven strict denials; all reached allocation,
  lookup, descriptor and SKB-reset helpers execute. Four DESC5/6/7/8 cases remain
  unresolved after a tool restriction; the blocked lane was not retried or
  rerouted. The two separate API21 allocator substitutions are eliminated.
  SKB reset has only modeled lock/storage proof, not physical quiescence.
  A subsequent selected cold-TXDONE candidate adds count/status, lock-owner,
  metadata and temporary-read guards. Sixty-two native cases, eight mutants,
  RX0/2 compatibility and all37-detour retained-gate controls pass, without
  opening strict API1 admission. Missing owner/backing models are explicit;
  actual host allocation capacity, all pointer provenance, concurrent fault
  publication and remaining callbacks still need closure before admission.
  INODE now has 16 exact native entry footprints, six complete selector2/7/4
  calls, four controls and three strict denials. Five wrapper loads span24
  bytes even for a 12-byte request; the retained provider allocation is256,
  so this is not a physical allocation-overrun finding. These three selectors
  ignore the extra stale arguments and have identical padded/unpadded memory
  effects. Run flags precede ICV clear and are not initialization witnesses.
  The provider-framing correction was interrupted by a tool restriction;
  unfinished files are preserved outside the firmware overlay and no fix is
  integrated. Do not retry or reroute that blocked operation.
  General mt76 commands remain closed. Close
  remaining callback consumers and failure-status propagation, full post-gate
  worker initialization, production TX-queue integration, INODE 24-byte reads from
  12-byte logical requests, descriptor fallback validation, partial-init owner
  retention and the production cold-loader/request/cache contract.
  The prior host-C baseline proved band1 aliases TX0 with no physical ID in
  single-HIF mode. A two-branch source candidate now allocates independent TX0/
  TX1, selects the matching 21/18 physical IDs and preserves band2's TX1 alias.
  Actual TXD C no longer overwrites both returned bases through one register.
  Sixty before/after traces, 63 controls and four mutants pass; native core0
  progresses using these actual host TX writes with independent synthetic RX
  publication. Eight real AArch64 objects compile with NPU in/out. The patch is
  unpromoted: publication can precede registration/attachment failure, hardware
  routing and ownership release are unproved, and malformed size still permits
  native return. No readiness, containment or live-failure closure is claimed.
- [ ] Handle L1 stop and reinitialization failures without resuming an unsafe
  datapath. Current upstream discards both return values.
  Candidate 006 now checks these results, MCU recovery handshakes and provider
  detachment, defers DMA/WED restart, and holds repeated recovery requests.
  Host-model and full-driver object checks pass, but the patch is unpromoted;
  successful STOP/GET is still insufficient for reclamation and real framework/
  hardware recovery, provider lifetime and rearming remain unproved.
- [ ] Close native cold-allocator ownership and bridge buffer extent before
  bridge/DMA publication. The checked core and hart7-only binding now reject
  failed ownership, corrupt metadata and insufficient extent/cache capacity.
  A subsequent reset-order candidate preserves the published type-0x89 control
  word instead of forgetting its record and overlapping the ID pool. Native
  before/after writes, four reset mutants, full core0/bridge replay and the
  31-detour retained-gate control pass. This is contained cold-model evidence,
  not authorization to clear allocations during an active reset.
  Same-C tests pass 1,367 native/RV32 pairs, eight mutants and 32,000 mutex-
  protected pthread calls; 48 original comparisons, four counterexamples and
  eight bridge cases verify. A new unpromoted binding covers seven core0
  startup calls and hart7 bridge allocation. All seven core0 calls occur after
  strict control-IRQ installation. Thirteen failures retain faulted-idle
  control service; five invalid interrupt/active contexts hold without service
  claims. Eighteen cases, 52 control replies, five H7 cases, eight mutants and
  36 preserved lookups pass. This does not close global integration: other
  callers still ignore failed acquisition. Real active-callback failures and
  damaged IRQ contexts need complete ownership-preserving error handling.
  The original reset sequence leaves insufficient room for type-2 by 3,832
  bytes. Retaining the control word costs 32 aligned bytes and raises that
  deficit to 3,864, leaving 2,305 free after bridge allocation. Both cases are
  typed allocation proofs, not packet/DMA writes; checked rejection is not a
  complete functional allocation plan. Reconcile
  all required consumers and type 0x81's 58,879-byte versus printed 64 KiB envelope
  without resizing memory on the print alone. Physical lock/cache/release,
  real timer/status/ingress and checked initialization permission remain open.
- [ ] Correct full-reset ordering: do not release tokens or clean rings before
  NPU quiescence is established. Cover device removal/unload as well as recovery.
- [ ] Define bounded timeout/partial-restart behavior, owner retention on failure,
  reset generation and late-completion rejection. Do not assume an IRQ mask
  proves the independent NPU stopped accessing memory.

## Priority 2: Current-Source Stock-Port Implementation

- [ ] Reconcile the Daybreak19 legacy implementation with current mt76/provider
  interfaces; port justified behavior instead of copying the historical series.
- [ ] Complete dedicated host-adapter TX rings, producer/consumer and doorbell
  ownership, descriptor bookkeeping and completion accounting.
- [ ] Complete SKB/bufid/token lifetime and TXFREE equivalence, scatter mapping,
  DMA handoff, delayed completion, wraparound and teardown/drain behavior.
- [ ] Complete RX/refill and RRO/BA session/free-pool ownership, reset semantics,
  ping-pong packet fate and applicable PPE/FastTX paths.
- [ ] Validate downstream MT7996 RXD/header/group extents and nonlinear skb
  views end-to-end. Patch 009 covers selected shared header views/transforms;
  firmware-event body/TLV, full callback/stack and real metadata validation
  remain open. Neither host candidate certifies complete payload parsing.
- [ ] Expose only controls/counters backed by implemented, validated driver ABI.
  Historical numeric NPU modes are currently retired; do not add cosmetic modes.

## Priority 3: Verification and Release

- [ ] Extend actual-code fault tests to busy/timeout, partial initialization,
  late completion, reset, concurrent refill and removal. Separate models from
  kernel/runtime and hardware evidence.
- [ ] Build and inspect the unified experimental NPU-active image, as requested
  on 2026-09-23. Verify full module/config consistency, FIT/DTB/layout and source
  provenance. An experimental image is not recovery/hardware acceptance; the
  outstanding physical gates remain prerequisites for those claims.
- [ ] Run serial-backed synthetic boot, reload, scan, reset, memory and traffic
  tests with known-good rollback. Do not switch the Codex PC's WiFi uplink.
- [ ] Obtain real-client association and throughput evidence for standalone
  2.4/5/6 GHz, two-link and tri-band MLO, including the iPhone/laptop regressions.
  Test client-to-client and wired-to-WiFi directions separately, with repeatable
  channel/width, signal, negotiated rate, NPU state and CPU-load observations.
  Fresh R1 readbacks on 2026-09-06 found zero configured Wi-Fi networks, zero
  runtime interfaces and zero hostapd interfaces despite all radios reporting
  up. Restore only the user's intended approved network configuration before
  reproduction; it has been requested, not inferred. The new read-only baseline
  collector and fixtures have syntax proof only: unsigned WSL-share execution
  was blocked by RemoteSigned, and a process-only override is awaiting approval.
- [ ] Long-running stability/memory/resource tests and fault recovery before any
  production-reliability claim. No current evidence establishes full stock parity.

## Other Unfinished Checks

- [ ] Resolve the CPU clock SMC readback/cpufreq-policy issue. Actual frequency
  remains unknown; do not reinstate the fabricated 1.2 GHz fallback.
- [ ] Broaden LuCI MLO save/apply and runtime-reporting coverage, including mobile
  layouts, radio combinations and shared-wiphy scan-cache semantics.
- [ ] Validate CPU/NPU realtime monitoring on the final stack. Queue/counter/PC
  activity must not be presented as measured per-core utilization without a
  supported measurement source; verify counter resets, polling and graph wiring.
- [ ] Verify regulatory/channel/width behavior using current driver/regdb data.
  The decimal-frequency helper bug is fixed with actual BusyBox/driver and
  80-case shell proof. Twenty-nine AP/MLO configurations now reach ENABLED,
  including6GHz320MHz and ACS, six BSS objects and mixed MLO/ordinary APs;
  six additional unchanged-config reload stages pass. Actual client traffic,
  all legal channels/security modes and changed-config MLO transitions remain.
  The parked SA/channel161 configuration is not an approved active AP choice.
  Preserve transmit-power policy and do not add unvalidated AFC/advanced MLO.
- [ ] Verify SQM/adblock/SoftEther services end to end on the final image. R1's
  manifest includes SQM, adblock and their LuCI apps, SoftEther server and its
  custom LuCI app, and full wpad-mbedtls. Presence is not service acceptance;
  SoftEther is disabled by first-run defaults. Recheck relay/NAT traversal and
  blocklist-update behavior rather than importing claims from older images.

## Preserve While Cleaning

- Canonical source, patches, tests, ledger/reports and current/rollback releases.
- Factory/calibration, bootloader/recovery dumps, router backups and credentials.
- WSL recovery VHD and the only copies of archived prepared source/Ghidra work.
- Current build toolchain and source needed to resume without reconstructing
  the whole environment. Clean reproducible caches and verified duplicates first.

Current official snapshot comparison found no new relevant upstream fix;
our local guard, memory and mailbox corrections remain required.

Detailed evidence: `research/checkpoints/2026-09-06-npu-bootstrap/REPORT.md`,
`research/checkpoints/2026-09-06-wifi-config/REPORT.md`,
`research/checkpoints/2026-09-06-wifi-baseline/REPORT.md`,
`research/checkpoints/2026-09-06-npu-hostqueue/HOST_QUEUES.md`,
`research/checkpoints/2026-09-06-npu-inode/INODE_CONTRACT.md`,
`research/checkpoints/2026-09-06-npu-attachtx/TX_CALLBACKS.md`,
`research/checkpoints/2026-09-06-npu-attachtxbuf/TXBUF_CALLBACKS.md`,
`research/checkpoints/2026-09-06-npu-startup/REPORT.md`,
`research/checkpoints/2026-09-06-npu-preflight/REPORT.md`,
`research/checkpoints/2026-09-06-npu-bootmem/REPORT.md`,
`research/checkpoints/2026-09-06-npu-copy/REPORT.md`,
`research/checkpoints/2026-09-06-npu-layout/REPORT.md`,
`research/checkpoints/2026-09-05-npu-admission/REPORT.md`,
`research/checkpoints/2026-09-05-npu-workers/REPORT.md`,
`research/checkpoints/2026-09-05-npu-barrier/REPORT.md`,
`research/checkpoints/2026-09-05-npu-reset/REPORT.md`,
`research/checkpoints/2026-09-05-npu-quiescence/REPORT.md`
and prior `research/checkpoints/2026-09-05-npu-attach/REPORT.md`.
All substantive changes must also be recorded in `W1700K_STOCK_PORT_LEDGER.md`.
