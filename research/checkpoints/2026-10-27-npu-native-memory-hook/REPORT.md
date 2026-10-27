# Native Memory Callback Gateway

Base `ff0788f20ab95a4d690d5623f101819ade37870d`, mainline, solo. Private cohort:
`.local/npu-native-memory-hook-20261027`; C-backed results:
`.local/npu-build-scratch/native-c2/native-memory-hook-*`.

## Implementation

Host observer profile 8 adds a direct C memory callback matching the loaded
Unicorn header's `uc_cb_hookmem_t`, checked with a C11 static assertion. It
forwards `(cpu, access, address, size, value, None)` into the existing observer,
preserving signed `int64_t` values and signed sizes. A strong registered CPU,
engine handle and thread binding support registration before Reader enablement;
later enablement rejects an inconsistent CPU/handle/thread.

The C callback pins itself across in-flight unhook, visits its CPU during GC,
and uses the existing first-exception/context/stop handler. Shared Python
registration code retains the callback before native registration, publishes
the handle afterward and retains userdata if rollback fails. The original
read/write registration positions are preserved by a default forwarding method;
the default Pair still uses its original Python callbacks.

Read API remains 2. Nine core C bodies are byte-identical to the retained source:
read dispatch, CSR/word reads, emulation, cold/block/memory dispatch, block error
handling and the block callback. No counting, fresh SP, exact miss, range, I/O
or fault logic is intentionally removed. This is a transport optimization, not
a universal reentrancy or heap-safety claim.

## Qualification

- Initial q2 plain/UBSan each pass 112 methods. Its consumed 80-method test
  version is preserved before adding the owner-CPU rebind regression.
- Fresh q3 plain/UBSan each pass 32 read/CSR plus 81 observer methods, zero
  skips/errors. Eighteen observer methods are new; repeated runs are not added
  together. Plain `f0f130b2` and UBSan `1c909741` binaries are identical across
  those two build generations.
- Twenty-five independently compiled controls fail one intended assertion each.
  New memory controls corrupt signed value/order, omit the in-flight pin or
  CPU GC edge, or bypass the enable-binding guard.
- Actual finite raw transcripts match 19517 instructions and 40 memory regions.
  Fresh tooling runs 167 methods with zero skips/errors. These are not new
  kernel executions or physical DMA tests. Backend-error precedence includes
  an explicit native-function stand-in, not a physical bus fault.

## Performance And Actual Native Replay

The same actual RV32 metadata loop alternates wrapped/direct transport over
three trials each. It preserves 200000 reads/writes, exact counters, data word,
terminal state and fresh SP per write. Median wall times are wrapped
1384101427ns/direct 512733364ns, ratio **2.699456528832401**. This is a controlled
host microbenchmark, not NPU or real-client throughput acceptance.

Native-q8 refuses the old pair manifest's IRQ-registration source hash before
firmware execution. That receipt and all consumed inputs remain. Fresh pair-q9
recompiles/assembles 274 current source inputs and 21 components. Its CODE and
DATA bytes are identical to the retained pair:

- CODE: `e6bc914ccc087e963a431279fc5759006e7449183da63b97a4c4f9770ae6e525`
- DATA: `ad905cb06b54b4f3f84308895c8de1bf9296ccec799bc20ef5aef0d14e000512`
- New manifest: `d0eddf16148c9a087bc299d166c242649314f8f86c2a4e7d0451baeb35d7209a`

No manifest/source check is bypassed. Native-q10 uses this fresh pair and passes
139 positive RPCs/journal comparisons; all 141 canonical rows match except
`wall_ns`. The raw prefix executes 1136899 tracked instructions in 35108769468ns.
The first publication takes **25518956577ns**, with 7438798 blocks, 760661 metadata
writes, 515 payload reads, one mailbox veneer/binding each, table writes/reads
1/2 and extent writes/readbacks 24576/24576. Complete broker, extent, DMA, SRAM
and code comparisons pass under unchanged boot 3M/10s and RPC 100M/60s limits.

The previous 46.865s first publication was perf-profiled, unlike this run. This
is encouraging single-run timing, not a paired whole-publication speedup or
acceptance of the original ordinal119 failure/full recipe.

## Preservation And Next Gate

All 323 current native inputs and current build/header/binary bindings verify.
Four changed paths in the old 309-input cohort have preserved pre-edit aliases;
all 294 original full-replay inputs remain read-only/hash-correct. All 438
target inputs, source lock `d55e71a3`, mt76/kernel patches and qualified RXWI
modules remain unchanged. Old tracking bodies and failed/consumed inputs remain.
Actual Jev judgments are retained as semantic checks, not execution proof.

Every new phase keeps 400MiB/no swap, a 128MiB C-output reserve, fresh dual
backing/RAM observations, margins and the C writer lock. The new pair is an
emulation artifact, not a packaged router image. No module load, router contact,
flash, shutdown, compaction or Wi-Fi change occurred. Ethernet stays disconnected.

Prepared full-q16 requires the committed/post-verified clean profile-8 cohort
and fresh pair. It will preserve producing inputs, then execute all three raw
profiles and independently check all 19261 RPCs under unchanged limits. The
script/launcher's existence is not a live job or a passing result; inspect
actual process/result evidence and never restart on observation timeout.
Full native, complete consumer containment/physical drain, BA reuse/hot lifetime,
current image/board and real-client performance/stability gates remain open.
The full NPU reverse-engineering and implementation goal stays active.
