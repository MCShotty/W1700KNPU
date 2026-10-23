# BA Event Integrity And Native Replay Timeout

Goal-turn classification: **progress**. The full NPU objective remains active.
This checkpoint supersedes the preceding native-q2 running-status observation;
it does not turn an incomplete replay into a native pass.

## Implemented

The actual `mt7996_ampdu_action()` now returns host RX aggregation allocation
errors before requesting MCU BA enable. It does not invent a rollback for a
partially accepted multi-link MCU request.

The actual `mt7996_mcu_wed_rro_event()` validates linear availability, every TLV
tag/length and each known record's minimum size. Unknown well-framed tags and
extensions can be skipped. Malformed framing stops parsing. Unusable status
WCIDs/TIDs no longer discard later valid records. Status lookup/update is in
an explicit RCU read section with `WRITE_ONCE` publication. Delete queue items
now retain WLAN ID and TID alongside session ID.

These are wire tuples, **not authenticated BA lifetimes**. Matching the current
WCID/TID still cannot distinguish an identical delayed tuple after reuse. No
firmware epoch, counter or completion guarantee has been manufactured. The
existing reset worker's error handling, late-event ownership and unconditional
metadata retirement still require implementation. No storage free authority is
granted by this patch.

## Qualification

- Fourteen selected-C ASan/UBSan/leak fixture scenarios pass on both independent
  candidates and installed current sources. Three compiled controls reach their
  intended assertions: missing allocation guard, discarded delete TID, missing
  status RCU. skb linearization, allocation, locks, RCU scheduling and MCU calls
  are modeled; this is not kernel concurrency or firmware execution.
- Fresh complete selected caller characterization passes 1,090 cases and seven
  controls: 1,040 explicitly optional-provider cases and 50 modeled owned-provider
  cases. This is not full joint provider/kernel/native execution.
- All four pinned AArch64 modules final-link with GCC14.4.0/Linux6.18.52. Source
  reconstruction uses the cumulative mt76 patch at fuzz zero, adding `main.c`
  and `mcu.c` to that authority. All five kernel and 329 mt76 source identities
  and 31 component mappings are checked. No module load or full image follows.
- Current source export and all 116 tooling tests pass, zero skips.
- The previous 7,152 project bindings and one external binding rehash with
  version remaps to independent before snapshots. The 2,865 executing capsule
  inputs, 14 protected project image bindings and one external image rehash.
  Original compact controller/native starts and invocation match; CPU advances.

Module producer: `b9e5003e8185f34c051bfba47978628d8eee993b239102c7f8e8a577943f567b`.
Source lock: `8222e0e798ede46f8437f9075279a996cf2905ab9539107ad190135312f5b8bb`.
mt76 authority: `7ae5376f05ef07a1eaf39cd7d4e98e752031e347dc15e2f416c5c7b0131730e3`.

## Native Terminal Evidence

`w1700k-npu-rro-wire-native-q2.service` is terminal, exit-code 1, not OOM and
not a passing run. It completed 174 positive RPCs: one OPEN, 139 ENROLL and 34
PUBLISH. Publication ordinal 34 stopped at 60,000,489,374 wall nanoseconds, with
Unicorn's timeout flag set and 21,498 of 24,576 required extent reads observed.
The previous completed publication took 54,800,738,688 wall nanoseconds.

The unchanged bounds are 100,000,000 instructions and 60,000,000 microseconds.
The 6,869,172 observed basic blocks are not an instruction count. Python hook
overhead is a plausible contributor, not an isolated cause or proof of a native
firmware defect. The complete failed trace, counters and partial state remain.
Neither this run nor the original compact replay was restarted; no limit was
raised and no observer coverage was removed. Full transport qualification is
still required.

## Firmware Lead And Retained Failures

The WM carrier `99020e57ff91fdee09b833f9d35f97ff70722d0ef32fa8b02f70c8d3c6f95592`
is 2,666,168 bytes. Parsing the actual loader's 36-byte trailer and nine 40-byte
region descriptors identifies 2,665,616 bytes of loader payload. All nine regions
have the loader's ENCRYPT bit set; the first also overrides the start address.
The recorded build date is `20260721003035`. No payload was decrypted, exported
or assigned an ISA. No BA ordering semantics were recovered from plaintext.

The first inventory script incorrectly expected payload lengths to cover every
byte before the descriptors. Its assertion failed on a 156-byte gap. The failed
script/receipt remain; the corrected inventory records that gap as opaque with
its own hash rather than labeling it a signature or compressed stream.

The first module launch was refused before compilation because RAM did not cover
the original replay's full 4GiB cap, the new 512MiB cap and unchanged 2GiB margin.
Only the two idle REA helpers started for the now-closed subagents were retired
with identity/start-time checks and SIGTERM. Other helpers were untouched. A
fresh budget then passed at the same caps and margin. The original failed launch
and storage/RAM observations remain; no swap, VM or global-policy change occurred.

## Next

Reduce proven observer overhead without losing exact-code, memory, stack or
digest checks, then qualify a fresh source-bound replay at unchanged limits.
Finish real reset-worker retention and error/late/reuse correlation, hot lifecycle,
CPU join and independent IRQ/DMA/firmware/cache/PMA retirement. Build and qualify
a current full image and complete cold/fault/HIF2, physical boot/radio/client,
performance and stability acceptance. No image promotion or hardware action
occurred here. UI configuration and radio policy are unchanged.

Private cohort: `.local/npu-rro-ba-20261023/`; fixture cohorts:
`.local/npu-rro-ba-events-20261023/{candidate-q1,current-q1}/`; module receipt:
`.local/npu-checked-irq-modules/rro-ba-q2/result.json`. `EVIDENCE.json` binds the
private manifest and covered artifacts; device secrets and backups stay local.
