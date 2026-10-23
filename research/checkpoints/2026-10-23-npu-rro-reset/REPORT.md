# Retained Host RRO Reset Ownership

Goal-turn classification: **progress**. The full NPU reverse-engineering and
implementation objective remains active and incomplete.

## Implementation

The owned host DELETE lane now preallocates 1,025 immutable request records in
an independently retained owner. Records keep session/WLAN/TID, a host arrival
ordinal, possible/acknowledged phases and raw NPU/MCU results. Module/device
references pin the record owner beyond consumer release. Arrival is a host
receipt identity, not an authenticated firmware BA generation.

The complete WED worker chooses the retained ownership marker before legacy
current-provider/CPU fallback. NPU failure retains the request and prevents the
later MCU call. MCU failure retains both its raw result and possible exposure.
First failure is sticky; pending exact duplicates do not retransmit, conflicts
and completed-slot reuse stop admission. Invalid IDs never index the array.
Owner publication and missing-owner enqueue now share the admission lock. A
producer that first saw NULL rechecks under that lock and retains an intervening
publication's tuple. If the missing-owner event wins first, its sticky ENODEV
prevents constructor publication; higher init propagates the error before RRO
extents. Pre-owner failure retains an error, not the lost tuple or a BA epoch.
The lower abort path quarantines IRQ delivery and attempts provider closing,
including provider-loss handling, without claiming physical drain.

Unregister, full reset and L1 reset close admission before cancel_work_sync and
record software join afterward. A pre-admitted synchronous MCU call may finish
during close; no later MCU call is admitted. Owned free closes before provider
close and returns before managed frees. Constructor failure unwinds only an
unpublished owner. Published records and pins have no production retirement path.
This intentionally prevents transparent module unload/rearm on the owned lane
until a separately qualified retirement path exists.

Checked-provider legacy scalar selector3 remains denied. The new worker does not
yet bridge its request to the typed reset journal/transport. Modeled successful
NPU/MCU replies in the host fixture are not operational admission. A generic MCU
ACK and the host tuple do not prove which BA lifetime generated an event or when
a session ID can be safely reused. Actual RX-TID lifetime-token creation and a
qualified late-event/reuse fence remain open; current-generation lookup cannot
manufacture either.

## Validation

Installed-source selected actual helper/lower abort/IRQ/complete-worker C passes
17 host scenarios and six compiled intended-assertion mutation controls with ASan,
UBSan and leak detection. Allocation, locks, RCU, scheduling, device/module refs,
NPU and MCU boundaries are explicit single-threaded models. Test-only disposal
after retention assertions is not a production retirement implementation.

Installed-source BA/event fixture passes 15 scenarios/three controls, adding owned
DELETE routing with changed HWRRO mode and failed legacy event allocation.
Seven structural checks cover close/cancel/join call sites, owned free, early
owner construction, parser ordering and CONFIG object linkage.

Jev's source review supported NPU-error and MCU-retention claims with 0.96/0.98
probability. Its provider-loss classification was uncertain (supported0.48,
confidence0.22); the actual selected-C provider-loss scenario and complete
worker ordering were inspected instead of treating that judgment as proof.
The BA-authentication claim was not established by this work. Full raw
probabilities and model/usage are retained privately and in EVIDENCE.json.
The fresh seven-question source review supports the two new constructor/error
and locked-recheck statements with0.96/0.97 probability. Its provider-loss
support is0.68/confidence0.52, still not kernel or hardware proof.

All132 current observer/tooling/verifier units pass, zero skips:116 tooling,
six modeled observer cases and ten inventory/completed-producer gate cases.
The observer suite retains its three Python mutation controls. Seven structural
hook checks also verify constructor error propagation and teardown ordering.

Four current AArch64 final module links and the source-bound1090 caller fixture
remain pending. The last successful producer b9e5003e is older-source only.
Partial provider/core/library objects from a failed attempt do not qualify a
current combined module set, image or ABI. The newly copied caller fixture's
owner init/close/join/work boundary is modeled and its current-source run is
not claimed here. No new RV32 archive/native instruction replay was required
or performed for this host-source checkpoint.

The cumulative mt76 patch reconstructs all 15 patched outputs with zero fuzz.
Its source-lock update preserves all 31 component mappings. Existing source
bytes were preserved before atomic replacement, detaching frozen hardlinks.
Current source lock is f7f843ff9f6580a2903fe8e716069728fa454ad13001f54e4507e40e6fd924fe.
Both running native replay input graphs remain unchanged. New unique fixtures
avoid modifying any existing tests/npu C file captured by the native replay.

## Failed Attempts And Resources

RAM guard refusals happened before compilation, including the first BA and
retention launches and the 256 MiB module launch. A retention launch omitted
WSL_DISTRO_NAME and failed before the test; a correctly scoped fresh launch
passed. All failed attempts and budgets remain local.

The first 192 MiB four-module attempt hit its cgroup OOM limit, not a source
compiler diagnostic. Its controller retained a complete roughly 102,000-entry
kernel inventory beside the compiler. A new verifier copy streams sorted
complete inventories to disk and releases them before compilation; before/after
SHA256 comparison still covers every file path, mode, symlink and byte hash.
That attempt progressed to provider-main.o but also hit the 192 MiB limit. A
fresh attempt additionally set GCC ggc-min-expand=5/ggc-min-heapsize=8192; these
are compiler garbage-collection controls, not optimization changes, per the
[GCC documentation](https://gcc.gnu.org/onlinedocs/gcc-14.2.0/gcc/Optimize-Options.html).
That CPU-active attempt was intentionally stopped, without a build verdict,
after ten minutes on provider-main.o. Only its exact auxiliary unit was stopped;
both replay starts/invocations remained unchanged. A fresh stage/compile/verify
flow replaces staging controllers before compilation, then verifies the exact
completed unit invocation/exit and all original sources/inventories afterward.
It initially retains the 192 MiB compile cap and uses ggc-min-expand=20/heapsize8192.
Observed executable-page refaults exposed cache thrashing near that cap. A fresh
full-cap/Windows-storage/RAM check later permits 224 MiB plus an 8 MiB bounded
property setter while retaining the full 2 GiB margin. Only this live auxiliary
unit receives the runtime-only 192->224 MiB adjustment; the compiler is not
restarted and both original/native replay caps and instruction/time bounds stay
unchanged. The initial and adjusted budget receipts are both retained.
A second fresh full-cap check permits 224->236 MiB for the same live compiler
when the large shared-MCU translation unit encounters cache pressure. Its
8 MiB setter is included too; no restart, replay bound or margin change occurs.
That auxiliary attempt eventually reached its unchanged30-minute make deadline
in mt7996/mcu.o. Its partial provider/core/library links remain failure evidence,
not a successful combined producer. It was not restarted.

Fresh copied-cache preparations at236MiB refused RAM before any compilation.
One malformed pre-start command tried to execute a filename containing a space
and also failed before work. A224MiB preparation then caught a bookkeeping type
error: a SHA string was compared with the source-inventory metadata object.
The parser/API returns hash/mode/link records, not SHA strings. The correction
uses the existing full inventory record comparison; its next launch refused
RAM before execution. The copied failed cohort and original failed build both
remain intact. No current incremental module success is claimed. The older REA
servers remain untouched pending the user's resource-cleanup answer.
No original replay cap, instruction/time bound or reserved margin was relaxed.

The authorized Sol/max worker wrote only new retention test files and was closed.
Two idle REA helpers introduced by its bootstrap are now absent: one exited on
agent close, the other received identity/start/UID/argv/children-checked SIGTERM.
The first cleanup receipt incorrectly claimed both were already absent. It is
retained and explicitly invalidated by corrected retired-helpers-q2.json, not
used as proof. Older helpers and both native replay jobs were left untouched.

All auxiliary jobs use explicit caps, no service swap, one build job, OOM stop
and no restart. Fresh Windows backing-volume observations and full original plus
native plus auxiliary caps retain the 2 GiB margin. No VM, swap or global-policy
change occurred. Private raw failures, binaries, device data and keys stay local.

## Remaining Gates

Neither native replay has a complete verdict here; partial RPC/reset logs are
observations only. Never restart them because observation expires. Full typed
reset/BA identity integration, hot CPU exclusion and joins, independent physical
NPU/MCU/DMA drain and retirement/rearm, current full image, cold/fault/HIF2,
hardware/client/performance/stability acceptance remain required. No raw pair,
RV32 firmware component, full image, promotion, flash or hardware action changed.

Private cohort: .local/npu-rro-reset-20261023/. Receipts and exact source versions
are bound by EVIDENCE.json; no device secrets are published.
