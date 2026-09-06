# Native TX Setup And TXDONE Callbacks

2026-09-06. Base `d41ac7ba1987f2d47a5e95146f8127cd7f7d49e4`.
Three previously pending direct callbacks now execute to completion: SET19
selectors 0/2 and DESC selector 10. Strict API1/API19 admission is unchanged
and closed. No firmware, configuration, hardware, image or flash change.

## Native Inputs And Observer

The immutable combined ELF is
`bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931`.
CODE/DATA and the existing Ghidra export are hash-pinned in the JSON. Imported
helper hashes are checked before/after execution; complete native code remains
unchanged after each callback. Original callback-array entries bind API19 to
`0x8400fc16` and API1 to `0x8400fe34`. Fourteen reached function spans are
compared with original CODE and bound to Ghidra identities.

The test executes the existing native core0 boot and complete L2 oracle, then
native RX callbacks for 1536/1024 descriptors. Only the selected TX commands
are replayed afterward, not all 38 host messages. Page callbacks are neither
executed nor inferred. All allocation, lookup, descriptor and SKB-reset helper
instructions reached here run natively. Existing boot stubs are listed separately;
callback substitutions are printf, hart-id input, and MHARTID input only.

A process-local observer subclass replaces the inherited boot-only sequential
zero-write assertion for later writes to the same SKB-state reservation. It
does not alter native instructions, helper returns or CPU control flow. New
models are six write-only TX registers and software mutex20 acquire/read/release
storage. Mutex20 reads hart0 owner value `0x10000`; this is not arbitration,
physical lock ownership or synchronization proof. Inherited mutex19/28 models
retain their existing limits. The synthetic TXFREE CPU view is `0x57000000`,
8192 nominal bytes plus a 4096-byte poisoned guard, corresponding to the pinned
host fixture's DMA value `0x17000000`. No alias coherence is inferred.

## SET19

All four pinned port/HIF host profiles execute selectors 3, 0 and 2 in order.
The supplied host values are stored at SRAM `+4610`, `+4700` and `+46fc`.
The helper clears halfwords `+3978` and `+21f4`; nonzero seeds prove both stores.
It performs two original subregion lookups, not dynamic allocation. Selector2
normalizes its helper band to1. No supplied host pointer is dereferenced here.

| Port | Selector | Register Pair | Values Before 29-bit Mask |
|---|---|---|---|
| 2 | 0 | `1fc08030/34` | `3e817000`, `3e839020` |
| 2 | 2 | `1fc48030/34` | `3e839020`, `3e861040` |
| 3 | 0 | `1fc28030/34` | `3e817000`, `3e839020` |
| 3 | 2 | `1fc08030/34` | `3e839020`, `3e861040` |

Ports0/1 use the combined pair `3e817000/3e861040` at the first/second register
bank. Other port values store the host pointer and clear counters without a
register write. The second pair endpoint equals the native Wi-Fi arena end;
register semantics are not established, so this is not by itself evidence of
an out-of-bounds consumer. HIF2 changes the host-supplied selector2 value, not
the arena-derived register values in this stage.

Twelve nominal calls and 22 controls pass. Every completed call compares all
786432 bytes of SRAM/heap/L2 and its exact unique RAM writes, ordered MMIO writes
and final six register values. Controls include ports0/1/4/255, zero and
out-of-range supplied pointers, missing arena, and all six missing register
models. Zero/malformed pointers and zero arena still yield wrapper return1.
Missing modeled registers stop at the native access, without wrapper completion.

## TXDONE And SKB Reset

The initialized prefix runs SET19(3,0,2), native token-bound SET33(8192), then
SET22(TXFREE). DESC10(512) consumes IDs2560..3071 from the actual native free-ID
table, fills 512 16-byte TXFREE descriptors and 512 software IDs at `3e8adc70`.
Descriptor words are packet pointer, `07000100`, zero, zero; packet pointers
span `8a500080..8a5ff880`. No backing packet memory is accessed.

The success path then executes `np_skb_tx_force_reset` (`840049f0`), including
`84009aa6` reading 2048 pointers from the two original L2 TX rings. It writes
2048 temporary IDs at `3e816000`, clears/rebuilds 8192 state entries at
`50c00000`, writes the 8192-entry queue at `3e808000`, and marks the 2048 occupied
IDs with state3. SRAM head becomes 2048, tail0. Only after this finishes does
`8400b558` publish the byte ready flag at `3e9046fa`.

The source loop at `84004b08` unconditionally reads 8192 halfwords beginning
at the temporary ID table, although only its first 2048 halfwords were filled
by `84009aa6`; the index comparison precedes use of later values, not their
load. The exact 16384-byte read extent is checked. The max-token control extends
that read to 57344 bytes. This does not establish a live client failure.

An independent source-table oracle checks all 856064 bytes of SRAM/heap/L2,
TXFREE plus guard, and the complete 57344-byte SKB-state reservation. It also
checks the exact successful byte-write set, allocator IDs, lookup returns,
ordered mutex writes, temporary-table read addresses, and ready publication
after every other non-stack write. Nominal TXDONE has 46105 unique bytes written.
The initialized occupied-ID list is also changed to include 8191 in one control;
the rebuilt ownership/queue oracle checks the changed order and remaining IDs.

Sixteen controls cover zero/513 ring counts, zero/17 available IDs, missing
packet base, maximum native token bound, the altered occupied ID, six missing
reset register models, missing descriptor/state pointers, and a host ring one
descriptor short. Completed controls use full-memory/write checks. Access-stop
controls verify exact failure instructions/addresses and absent ready/return;
their partial state is traced, not claimed to have a full-prefix oracle.

Native zero/oversized counts still publish ready. Buffer-ID exhaustion returns
wrapper1 while keeping ready0 and retaining any already-consumed IDs; reset is
not entered. Missing packet base is accepted. Emulator capacity stops are not
firmware error propagation or rollback. Software reset under modeled locks is
not physical DMA quiescence and must never authorize live token reclamation.

## Replay And Integration

```sh
PYTHONPATH=.local/npu-reset/python-lib \
  python3 tests/npu/test_attach_tx_callbacks.py --check
```

Generation and byte-identical replay pass 13 valid calls, 38 controls and three
strict denials.
The strict calls execute no native callback and leave all compared RAM unchanged.
JSON is 351571 bytes. Test SHA256:
`02a81009ff74bfef0386b9d669c0089d0d092fbd8f99f7583773e6392ef3a3c6`.
JSON SHA256:
`3636a435970acfa4c6fe7d973be3165d86191064e66d8257a99a3b77a438dbd5`.

The separate API21 suite closes selectors5/7/10/12 with 1536 records, 1024
descriptors, 35 controls and four strict denials; the parent independently
replayed its receipt byte-for-byte. Together these suites cover seven new
native callback selectors, replacing seven of the 11 previously pending labels
and both separately allocator-substituted cases. Four original labels remain:
DESC5/6/7/8. That lane stopped after an automatic tool restriction and was not
retried or rerouted. It remains unresolved, not implicitly closed by this work.

Independent review found no actionable issues in this bounded scope. Ten focused
cases and seven strict denials passed independently. The evidence verifier binds
28 current inputs and confirms that firmware and shared helpers remain unchanged.
See `REVIEW.md` and `evidence-verification.json` in this directory.

Complete host attachment, single-HIF TX1 publication, INODE read extents,
descriptor fallback, checked failure ownership, post-gate workers, production
loader/cache/containment, Linux recovery/removal and actual-client acceptance
remain open. R1 remains last router-tested with WLAN NPU compiled out.
