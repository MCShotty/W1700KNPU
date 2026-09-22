# Host TXFREE Allocation Boundary

Date: 2026-09-09. Status: **unpromoted host candidate**, compiled for AArch64
and connected to selected original RV32 consumers in an isolated emulator.
This advances the allocation contract, not complete attachment, physical DMA
backing, safe recovery or full NPU parity.

## Source Contract

The pinned mt76 archive is `mt76-2026.09.01~be5ce791.tar.zst`, SHA256
`d1d0f7588c5b9ceafcac341ce19dd206ed9ec106847e672ab77e48bacb57f81a`.
The harness extracts unchanged functions/declarations from that archive,
with the actual prepared Airoha provider queue-address getter and header.
Selected span and source-file hashes are recorded in the receipts.

- Normal MT7996 allocation selects `MT_RXQ_TXFREE_BAND0`; the MT7992 branch
  selects `MT_RXQ_MAIN_WA`. Both request `MT7996_RX_MCU_RING_SIZE`, or 512
  descriptors. Actual `mt76_dma_alloc_queue` requests `ndesc * sizeof(*q->desc)`
  through `dmam_alloc_coherent`: 512 complete 16-byte descriptors, or 8,192
  logical bytes. TXFREE is neither the special NPU RX nor NPU TX allocation
  branch. Queue allocation/setup/reset functions execute in the host test.
- `mt7996_npu_rx_event_init` publishes SET22/selector0 with the DMA address,
  DESC/selector10 with constant 512, then SET0/selector10 with the PCIe
  register address. It does not negotiate the live queue's count or backing.
- Native SET22 wrapper `0x8400fbb4` reaches `0x8400b5c6`, storing
  `(address & 0x3fffffff) | 0x40000000` at SRAM offset `0x3964`. It diagnoses
  inputs at/above `0xc0000000` but continues. SET0/selector10 at `0x8400b94e`
  stores its address at offset `0x2a90`. The Ghidra mailbox export identifies
  these functions at lines 22429, 22896 and 32571; their instructions execute.
- Native TXDONE uses a 16-byte descriptor stride. The preceding checked
  callback validates a declared 8 KiB span, not its actual host allocation.

Normal source already requests 512 entries. Short counts, malformed queues,
addresses and forged metadata below are injected controls, **not observed
normal live allocation failures**. An 8,176-byte request also does not prove
unmapped physical memory follows it; the real allocator may round to pages.

## Candidate

`005-mt7996-npu-txfree-preflight.patch` adds a helper at the beginning of
`__mt7996_npu_hw_init`, after the absent-provider no-op and before attachment
helpers. Exact `MT_NPU_Q_TXFREE(0)` flags, descriptor/entry pointers and a
512-entry count are required, otherwise `-EINVAL`. Compile-time descriptor
size is 16. DMA alignment, high-32-bit truncation, the native `0xc0000000`
upper limit and a non-wrapping 8 KiB low-30-bit span are checked, otherwise
`-ERANGE`. DMA address zero is not automatically an allocation failure.

The normal message sequence is unchanged. The candidate does not allocate,
free, change transport or open strict firmware admission. Earlier queue reset
already performs MMIO: "before attachment" does **not** mean before every
hardware publication. RX0/TXFREE register-sharing ownership remains unresolved.
The patch stays outside the firmware overlay and source lock.

## Verification

`test_host_txfree.py` passes 152 actual-host-C traces: 38 inputs, two chip
branches and original/corrected phases. Counts, missing pointers, ownership,
alignment/width/aperture/native-range boundaries, lower aliases, allocator/
framework failures, all three command timeouts and absent provider are covered.
ASan/UBSan run in fresh processes. Allocation sizes/content hashes remain
unchanged during attachment, including failures. Final fixture teardown is
process-local, not device reclamation.

Thirty-four controls preserve entire event streams and summaries. Nine
compiled guard-removal mutants fail specific assertions: count, descriptor,
entry, owner, alignment, width, native range, wrap and early call placement.
None is counted from compilation failure or timeout. Forging `q->ndesc=512`
after a modeled 511-entry allocation still passes. Accurate, stable metadata
is an explicit requirement of the helper, not something it proves.

`build_host_txfree.py` compiles ten real AArch64 objects against Linux 6.18.44:
init/dma before/after with NPU enabled/disabled, plus npu.o in enabled phases.
Three promoted mt76 patches and the prior TX-topology candidate are common
to both phases; only the after phase adds this patch. Candidate application
has zero fuzz/offset; strict checkpatch has zero errors/warnings/checks.
Selected NPU functions equal the host-test source. Four unchanged init/dma
text pairs match. NPU text grows from 4,440 to 4,568 bytes. Disassembly places
the guards before the first provider call with distinct -22/-34 exits. This
is not a module link, package, image or target-runtime test.

`test_host_txfree_native.py` recompiles the host units and matches fresh traces
to the host receipt, then feeds recorded SET22/DESC10/SET0 messages to native
consumers. Supporting cold/RX0/RX2/TX setup is explicit. SET22 is absent from
fixture setup: its pointer remains zero until the tested message executes.
The memory observer derives logical backing from the host allocation trace,
not an independently selected 512-entry capacity.

Twenty-two bridge cases and a strict-admission control pass:

- Normal before/after, three lower aliases and original/checked native TXDONE
  preserve complete results. Successful TXDONE compares all 856,064 memory
  bytes, exact write extents and ordered locks. Each pointer setter changes
  exactly four bytes. The corrected temporary scan still reads 2,048 IDs
  versus the original 8,192.
- Accurate count 511 is rejected before attachment messages. Original host
  still sends 512: both native variants attempt descriptor 512's second word
  first at `0x57001ff4`, from `0x8400b4b6`, outside 8,176-byte logical backing.
  Forged count reaches the same stop. These three failures are detected only
  by the emulator, **not firmware backing protection**.
- Original host address `0xd7000000` produces the native diagnostic but
  completes. Corrected host rejects it before messages.
- Six timeout cases model the last attempted command as delivered/undelivered.
  Three have host `-ETIMEDOUT` with native ready=1. Published memory and modeled
  active ownership remain retained; no barrier release/preparation/arm occurs.
  These alternatives do not prove real transport behavior or safe reclamation.
- Allocation failure and absent provider make no selected native calls.
  Strict API1/selector10 rejects without callback or protected-memory mutation.
  Direct component invocation is separate from production admission.

The native firmware is **MT7996 only**. MT7992 rows test that host branch's
shared three-message shape against this fixture, not MT7992 firmware
compatibility or full initialization. Host and emulator do not share physical
storage: size/message agreement is not DMA mapping/cache/lifetime proof.
Other attachment helpers, chip inputs, framework/page-pool/IRQ services, MMIO
ownership and independent cold containment remain models or caller contracts.

## Replay

From the canonical WSL checkout:

```sh
python3 tests/npu/test_host_txfree.py
python3 tests/npu/test_host_txfree.py --check
python3 tests/npu/build_host_txfree.py
python3 tests/npu/build_host_txfree.py --check
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_host_txfree_native.py
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_host_txfree_native.py --check
```

All three receipts replay byte-for-byte, binding 16/23/96 inputs respectively
before/after. Parallel compiler-log ordering is not part of reproducibility.
All 83 preceding TXDONE-checkpoint inputs were rehashed and remain unchanged,
including its sidecar and source-lock/cumulative-patch baseline.

| Artifact | SHA256 |
| --- | --- |
| Candidate patch | `aaf72bef7df25d9bb1b2d282a1b0f32a3eacdfa1ef04c3bc687b76c6b1c0253d` |
| `host-txfree.json` | `53e762d4cace62d1316c34c545b97ef1b89f720079b48f700eac1fc30299f05e` |
| `kernel-objects.json` | `9df5f9764d2ee02634a19783d70a489633b09cf3474ef59b7e66897a8f4b6237` |
| `native-txfree.json` | `fdd62febc3653326930b8926dfa787a8bf697c078749906a16ecb83e61d7486d` |

Remaining gates include immutable allocation/global ownership, actual DMA
backing/mapping, RX publication geometry, concurrent fault/publication, full
memory budgeting and callback/worker closure, physical containment/cache/drains,
production integration and recovery/removal/full parity. No package, overlay,
source-lock, image, router/Wi-Fi/physical-test, subagent, protected backup or
Git-publication change occurred. Restricted INODE-provider and native
DESC5/6/7/8 operations were not retried or rerouted. The full goal remains
open. All four trackers and the NPU README are updated for this checkpoint.
