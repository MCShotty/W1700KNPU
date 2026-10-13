# Retained Host TX DMA Lifetime

Qualified 2026-10-13; implementation started 2026-10-11. Baseline: `f0d864c`.
This checkpoint advances the full NPU implementation; it does not complete it.
No flash, reset, router contact, or actual-client test occurred.

## Implemented Behavior

The actual `mt7996_npu_hw_init()` now allocates through the checked provider
while holding the existing mt76 mutex. The provider owns all six coherent CPU
pointers, full DMA handles, and allocation sizes in its retained lifetime.
The DMA device is the NPU provider device: `mt76_npu_init()` assigns it to
`dev->dma_dev`. The PCI endpoint is a separate pinned device reference.

Endpoint enrollment precedes possibly effective BAR publication. The one-shot
allocation attempt pins endpoint/DMA device, boot identity, nonce, bound serial,
and native plan. Fixed internal sizes prevent a changed caller array from
changing allocation extents after preflight. Address checks cover full width,
alignment, 30-bit alias-window boundaries, all admitted aliases, BAR/native-plan/
mailbox/earlier-TX overlaps, and duplicated CPU pointers. A newly issued STATUS
and complete identity/record/plan recheck precede the address publication latch.

Firmware exposure already latched the outer lifetime, so even partially
allocated or invalid TX records are retained on failure. Detach does not free
these buffers or the endpoint reference. There is no production retirement API.
Only `-EOPNOTSUPP` selects the unmarked provider's existing managed allocation
path; other errors cannot silently fall back or start the hardware initializer.
Repeated checked BAR binding closes the CPU session before another wire command.

This owns the Linux allocations, not complete native API21 consumption or
physical DMA visibility. Identity-corruption fixtures demonstrate rejection and
no frees, not repair of arbitrary kernel-memory corruption or original-device
reprobe exclusion after that corruption.

## Verification

| Evidence | Qualified Result |
| --- | --- |
| Actual allocator/binding/cleanup/header/caller C | 76 cases, seven rejected mutants, address/undefined/leak sanitizers |
| Original host caller counterexample | Six managed frees reproduced |
| Pre-fix alias guard counterexample | Cached-alias overlap reproduced |
| Current provider/session C | 609 cases, nine rejected mutants, including 272 BAR geometry cases |
| BAR binding mutants | Seven rejected, including pre-validation truncation and alias-window crossing |
| Existing DMA lease | 13 cases, four rejected mutants |
| Actual mt76/offload/RX prefix | Three publication cases, 16 offload commands, seven RX rejection positions |
| Actual allocator plus assembled RV32 STATUS peer | One completed case, six retained allocations, 38 frames |
| Endpoint/request/probe/boot/memory regressions | Passed with exact current input hashes |
| Unit suites | 21 nonzero tests: 13 host-tool, four source-export, four ownership-verifier |
| Source replay | 67 top-level files and byte-equal replay of all four changed nested Linux files |
| Strict driver checkpatch | Zero errors, warnings, or checks across the 391-line delta |
| Exact packaged provider Ghidra | 59 exported functions, zero failed decompilations |
| Full world and offline image | Passed FIT/board/218-package/78-module checks |

The native allocation/STATUS case executes actual provider C and raw RV32
reply instructions. Coherent backing, device references, transport and scheduling
are modeled. It allocates after real BAR binding and before actual offload/RX
caller replay. The later standalone TX sender still has synthetic handles:
this is not complete native consumption of the new buffers. Actual TX setup
still stops at denied API21; the following GET7 is diagnostic.

Earlier failed attempts are not qualification evidence. A mutation that removed
only a now-redundant size guard was replaced by a real truncation-before-check
mutant. Four BAR bases cover crossing all three alias windows. A stale unit
pattern discovered zero tests and was replaced with the actual nonzero suites.
One provider replay observed a replaced build-tree header and correctly failed
its final hash check; the qualified replay uses an explicit immutable header.
All final receipts are audited against current inputs before sealing.

## Original API21 Record Trace

`tests/npu/test_tx_buffer_records.py` executes the original helper at
`0x8400a5fa` and its static lookup instructions. Eight isolated RV32 cases
verify patterned synthetic memory, full untouched-byte checks and write order.
Both bands emit 512 sixteen-byte records with 4/4/4/1-byte stores; bytes 13-15
are preserved. Each completed band has 2,048 record stores. Two 16-bit counters
and a 32-bit pointer are published before those stores. No dynamic allocator
call occurs for types `0x100` and `0x101`.

The original helper accepts an incorrect nonzero TXPKT prerequisite and a
nonzero unsupported band argument. A corrupted static pointer directs record
writes into another mapped region without rejection. A missing table entry
clears the counters and publishes a null pointer before the first record store
faults. Zero TXPKT reaches the original delay-call site; replay stops there
without pretending to prove a physical timeout or drain.

These are original-code counterexamples, not candidate API21 permission.
Authority remains the hash-pinned original Ghidra export:
`research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt`,
SHA256 `1536a9972838ca7c02da77629e784b392af919c5d25368478aff4d0c2422e2ca`.
The next implementation must enroll the six host DMA records in the native
session, preserve GET5/SET0/SET5/SET10/GET7/SET2/SET7/SET12 interleaving, and
own the exact internal-record/static-table/L2/metadata spans before any write.
See `NEXT_API21.md`.

## Artifacts and Scope

- Unflashed FIT: `6efaa878524140439aaced592c219a925f200dcc9a3f55b00f29bb7e1148dfa7`, 26,973,002 bytes.
- Provider module: `42ec4f37cfc06439292289c71e6523839d5cd0e527d9037e9b8d336750f44293`.
- Source lock: `8c49d4782d017086f963b9daf7b705e0d078bba026fc2e668f07cb53553794c5`.
- CODE: `11151179c3bad61b563d1c14703fb886945de036669edf589f376880bcc872e0`, 567,972 bytes.
- DATA: `20e416709d1534c72752626e15fa67f75cb99ef7c16cce4256d117e376e9a619`, 25,728 bytes.
- Archive objects 16, raw components 14, hooks 77, canonical Linux component mappings 14.

The raw CODE/DATA remain byte-identical to the descriptor checkpoint. Earlier
descriptor-suite results are historical exact-byte regression context, not a
claim that all nine old native cases were rerun here. The current single native
case additionally covers the new allocator/STATUS path.
Prior `3951dc7c...` and `123e3084...` images plus seven companions each pass
strict checksums in protected local pre-build storage. Older/R1 images and
private calibration, bootloader, recovery and device backups are untouched.

Jev contributed focused semantic requirement and scope checks. Its first broad
physical-scope judgment was uncertain/incompatible with the explicit modeled
evidence; a focused follow-up contradicted the physical-observation claim and
supported software alias coverage. Raw probabilities are retained. Tests and
Codex reasoning, not Jev, establish the qualified behavior. No subagents were
used in this continuation.

REA 6.4.0 reused the exact provider's retained function evidence and bounded
pseudocode view; full Ghidra export remains the all-function evidence. REA does
not directly admit the raw RV32 blobs. Static decompilation is not runtime proof.

Remaining full-objective requirements include native API21 and remaining
PCIe/INODE/TXDONE/IRQ setup, other owners/workers, hot and postgate behavior,
independent physical backing/exclusion/coherency, drains/retirement/removal/
rearm/recovery, exact-image boot, real clients and sustained acceptance.

## Reproduction

Run from `/home/captain/W1700KNPU`, preserving consumed inputs throughout:

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_host_tx_lifetime.py --source .local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c --header .local/merge-nonoc-20260923/kernel-merged/include/linux/soc/airoha/airoha_offload.h --host .local/merge-nonoc-20260923/mt76-merged/mt7996/npu.c --mutants --name fresh-host-tx
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_tx_buffer_records.py --pair .build/merged-openwrt/bin/npu-pair-npu-host-tx-final-20261013 --output .local/npu-host-tx-lifetime-20261011/fresh-original-records.json
cd research/checkpoints/2026-10-13-npu-host-tx-lifetime
sha256sum --check --strict CHECKSUMS.sha256
```

Run checksum verification from the checkpoint directory; its filenames are
relative to that directory. Use new absent test names/output paths. The complete
input hash map and included artifacts are in `verification.json`.
