# Independent Native C0 Review

## Finding

- **[P3] Exclude pre-execution pause events from native entry counts.**
  `tests/npu/test_native_wifi_boot.py:232` counts every inherited `entry`
  event, including the event recorded before a breakpoint stops execution.
  The new pause/resume at lines 116 and 122 consequently reports
  `FUN_ram_8400d1d4` twice in every case and `FUN_ram_84009fc8` twice in the
  exhausted case, although each body executes once. The generated probe shows
  this at `native-wifi-probe.json:133` and `native-wifi-probe.json:22540`.
  `Installation.code_hook` records entry before checking stops
  (`tests/npu/test_boot_irq_installation.py:118-130`). Independent replay
  reproduced the counts and confirmed that removing entry events sharing a
  step with `paused` leaves one execution of each body. The delay entry
  `0x8400420a` is similarly inflated. Filter those events in the new test,
  or rename the field to `native_entry_hook_hits` and explicitly include pause
  observations in its definition. Do not change the unchanged helper for this
  correction. This is inaccurate evidence metadata, not a false native-return
  or L2-content result.

No other actionable issue found within the two-file review scope.

## Verification

- Replayed all five cases against the existing SHA-bound ELF without building;
  every full case object matched the generated probe. All three missing-MMIO
  controls reproduced their exact expected failures.
- All 33 recorded source hashes, the test, original code/data, DTB, ELF,
  Ghidra export and 13 source spans verified. Original `FUN_ram_*` assembly
  was inspected at the selected Wi-Fi/L2/SKB/host-adapter boundaries.
- The complete 262,144-byte expected L2 image passes in all five cases and
  remains unchanged through candidate idle acknowledgement. Reviewer-only
  mutations of an unused L2 byte and a duplicate TX pointer both fail the
  complete-image assertion. Normal cases contain 2,048 distinct 2-KiB TX
  pointers covering `[0x8cc00000, 0x8d000000)`, within the reservation ending
  at `0x90c00000`; the exhausted case has zero valid TX pointer entries.
- Thirty mailbox calls preserve all 32 integer registers, PC, MSTATUS, MIE,
  MTVEC and the paused caller's live stack. These are harness-restored saved
  contexts, not proof of native trap entry/exit or physical IRQ delivery.
- Observed substitutions stay within declared printf, hart-ID/CSR and delay
  helpers; the candidate cold/admission/bootstrap detours are separately
  disclosed. Wi-Fi, L2 initialization and SKB allocator bodies execute.
- Malformed host-register acceptance and exhausted-SKB zero returns are real
  modeled instruction outcomes, not success-stub artifacts: the original
  `FUN_ram_8400f832` only waits for nonzero readiness registers and returns
  zero; `FUN_ram_84009fc8` warns on all 2,048 failed allocations, publishes
  ring indices and returns zero. `core0_native_return` is reachability, not
  healthy-ring admission. The report's explicit malformed/exhausted markers
  and zero physical/all-worker witnesses preserve that distinction.

## Reproduction And Limits

Reviewer scratch: `.local/npu-nativewifi/review/replay.py` and `replay.json`.

```sh
PYTHONPATH=.local/npu-reset/python-lib python3 -B .local/npu-nativewifi/review/replay.py
```

- Reviewed test SHA256: `926e772ff5ee93eace3a132d890306751e08af39f19a46e6667549f8ce8e32da`.
- Reviewed probe SHA256: `a3eba4d79a3b6b54af419688fd6f6c6dbac989335899041bd5390abe0ff8f709`.
- Replayed ELF SHA256: `bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931`.
- This bounds only serialized core0 emulation with synthetic host publication
  and named storage-only MMIO. Physical L2 mode/cache/coherency, DMA ownership,
  concurrent harts, all-worker boot/containment, real ring usability, Linux
  attach/recovery and packet operation remain unproved. Host-sequence review
  belongs to the other reviewer and was not duplicated.
- Only this report and reviewer scratch were written. Parent tests, firmware,
  configuration, router and Git staging/commits were untouched. The ledger
  was deliberately left unchanged under this report-only assignment.

## Final Delta Check

- Static review of test SHA256
  `d8d597e6bf4aeb651422043f0d2b1b62b94c46441470b8b1a7cf2b8f636c7dfc`
  found no new major false-proof risk. The TX0 count is now 1,024; lines
  183-189 publish the other synthetic host fields, leave TX1 base zero and
  execute eight native wait iterations before asserting both readiness and
  coordinator acknowledgement remain zero. This does not claim timed or
  hardware waiting, and normal publication still precedes native return.
- The two added helper source hashes widen provenance coverage. The existing
  P3 entry-count finding remains, now at test line 240.
- Parent regeneration completed during this check. The new probe SHA256 is
  `cf4393ad4f07f5129bd2c45df34fe38451c473c6e5ea08fd19cc7e2999ecf6f7`;
  it matches the current test hash, reports five passing cases and three
  controls, and all 35 recorded source hashes match current files. Structured
  MMIO queries show nine zero-TX1 reads in each applicable case: the existing
  one plus the eight new iterations. TX0 count is `0x400`.
- The independent five-case replay above remains evidence for the earlier
  snapshot; the regenerated artifact was inspected, not independently rerun.
  No duplicate host-sequence review or broader report/verifier audit was
  performed. Only this review report changed in the follow-up.

## P3 Fix Verification

- **P3 resolved; no new actionable issue found.** Reviewed and executed test
  SHA256 `d86cf4fddda6804bd0391426cc5201b7e7214be7520ab688d9a8cb97cbec8340`,
  unchanged before and after the check. Lines 234-237 exclude entry events
  sharing a step with `paused` and assert one entry for both Wi-Fi bodies;
  line 246 exports those corrected counts.
- Ran exactly one normal and one exhausted case against the existing ELF
  `bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931`.
  Both passed. Raw `(d1d4, 9fc8)` entry counts were `(2, 1)` and `(2, 2)`;
  both reported `(1, 1)`. Independent hooks at the following body instructions
  `0x8400d1d8` and `0x84009fcc` each observed one execution in both cases,
  confirming the filter removes pause observations without hiding execution.
- The new post-idle full-L2 hash assertion at line 223 passed at the actual
  candidate idle window. Normal hash remains
  `76717ae9c218b9c0624320319f811670abe6e3961c3ee8021383fe5c384c6757`;
  exhausted hash remains
  `0d5c00b319672481e47f2ac99d7e4a5039ad7b4db2caad1fb73e24cc1e9af3a6`.
  Both cases retain TX0 count `0x400`, nine zero-TX1 reads including the eight
  added waits, and respectively 2,048 and zero valid TX pointers.
- No five-case rerun, missing-MMIO-control rerun, shared build, host-sequence
  audit or final-receipt certification was performed. The parent owns final
  regeneration and verifier binding. Only this report was written; the
  ledger and all parent files remain untouched. Earlier physical/all-hart
  limitations still apply.
