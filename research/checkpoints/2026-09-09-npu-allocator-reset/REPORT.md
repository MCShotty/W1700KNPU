# Preserve The Cold-Reset Control Word

2026-09-09. Status: native allocation-lifetime defect reproduced; reset-order
correction compiled and tested with the existing NPU candidates. Unpromoted,
codebase-only work. No router contact, physical testing, Wi-Fi configuration
change, subagent, image or flash. Full NPU implementation remains incomplete.

## Finding

The pinned native allocator reset at `0x84005296` clears the heap and cache,
initializes lock ID 18, calls the no-op prerequisite at `0x8400fb12`, and then
calls `0x84005a28`. That helper allocates four bytes as type `0x89` through
the original getter/allocator and publishes the pointer at `0x3e901f10`.
Only afterward does reset zero the used cursor and cached entry count.

The pointer remains live. Native writer `0x84005a42` stores 1 through it;
getter `0x84005a52` returns it. Static consumers at `0x8400580e` and table
callback `0x8400fd2e` further establish retained use, including returning its
physical alias and invoking the writer. These last two consumers were read
statically, not executed in this checkpoint. Their production reachability
after pool initialization remains unverified.

The next type-`0x8a` allocation, made by the native buffer-ID initializer at
`0x84004e76`, reuses the forgotten allocation's base. Executing reset, the
complete first 16,384-entry ID initialization loop, and the control writer
reproduces the following result:

| Observation | Original | Corrected |
| --- | --- | --- |
| Retained control pointer | `0x3e800000` | `0x3e800000` |
| Reset entry count / used bytes | 0 / 0 | 1 / 4 |
| ID-pool pointer | `0x3e800000` | `0x3e800020` |
| Control value after ID initialization | `0x00010000` | 0 |
| Pool's first four IDs before control write | 0, 1, 2, 3 | 0, 1, 2, 3 |
| Pool's first four IDs after control write | 1, 0, 2, 3 | 0, 1, 2, 3 |

This is an actual native-instruction overlap and unintended pool write under
the emulator's inputs, not an observed live traffic failure. No claim of
packet loss, external exploitability or physical memory corruption follows.

The preceding checked allocator cannot detect this erased lifetime by itself:
count zero and cursor zero form valid metadata even though a separate global
still retains an old allocation. Fixing bounds without fixing this reset order
would preserve the overlap.

## Implemented Correction

`tests/npu/allocator-reset-emulation.S` moves the count/cursor initialization
before the native helper, then the installer skips their old late stores:

| Native site | Original bytes | Replacement | Effect |
| --- | --- | --- | --- |
| `0x840052ca` | `efa09004` | `ef607453` | Linked call to the reset adapter at `0x8404c000` |
| `0x840052d4` | `97d78fba` | `6f000001` | Jump to `0x840052e4`, retaining the native stack adjustment and return |

The adapter zeros count and used bytes, then tail-calls the original no-op
prerequisite. The original control-word allocator, pointer publication, return
address reload and function epilogue still execute. Cache/heap clearing and
lock initialization remain native. The diagnostic attempt counter retains
its original increment/wrap behavior; it is not used as a reset generation.

The sidecar contains 20 text bytes at `0x8404c000..0x8404c014`, with no new
data/BSS allocation. Its disassembly and both verified native preimages are
included in the receipt. The original firmware files and baseline candidate
ELF are not modified; the detours exist only in emulator memory. This test
reservation is not a validated production placement.

This is a cold, independently contained reset contract. It does not make
clearing storage safe while other harts or devices still own it. The stale and
corrupt-state tests below use isolated memory inputs, not a live warm reset.
Original core0 allocation calls still ignore hardware-lock failure; this
checkpoint does not close that separate ownership contract.

## Verification

`tests/npu/test_allocator_reset.py` records:

- Five primitive cases: original cold behavior, and corrected cold, stale,
  corrupted-count/capacity and diagnostic-counter-wrap inputs. All 824 metadata
  bytes are checked against the independent allocator oracle. Native entry
  witnesses confirm count/cursor are zero before helper allocation and remain
  1/4 afterward. The entire 480 KiB heap, 32 KiB ID pool, and unchanged 32 KiB
  local SRAM across the control writer/getter are checked.
- Four mutation/installation controls: missing early count clear, missing
  early cursor clear, missing entry hook, and retained late clears. Each has
  an asserted incorrect count/cursor/control-pointer result, not just an
  unexplained hash difference.
- Actual core0 reset through native NPU Wi-Fi initialization, synthetic host
  publication and the existing coordinator idle acknowledgement. The complete
  824-byte allocation state and existing whole-256-KiB L2 footprint oracle pass.
  The persistent type-`0x89` allocation now precedes the six core0 allocations.
- Four checked hart7 bridge cases on that corrected boot state: normal,
  denied owner, corrupted cursor and external fault at successful unlock.
  Existing whole-SRAM/heap, lock-operation and STATUS assertions pass. Held
  faults do not publish a bridge base or claim ready/drain/release/arm; a
  committed allocation remains retained if a fault arrives at unlock.
- A subsequent successful bridge setup plus the original control writer and
  getter changes exactly the control word. The complete ID pool and local
  SRAM remain unchanged, and the entire heap matches the expected image.
- All 31 detours installed with the original first hart7 gate retained: all
  eight native reset/prologue contexts park and repoll. STATUS reports parked
  mask `0xff`, capability bits 7 and zero ready/drain/release/arm, with no
  bridge or checked-allocator execution. This is one serialized banked-PLIC
  storage model, not hardware concurrency or interrupt-delivery proof.

Post-gate bridge analysis retains the existing explicitly isolated first-gate
omission. It does not fabricate a physical drain, release, arm or cold-init
permission. The separately invoked control writer is a component test, not
proof of host callback delivery or an admitted running-worker transition.

The final full `--check` replay matches its saved receipt byte-for-byte.
Seventy-one current inputs are bound before and after the run, including the
original Ghidra export, native/candidate source and source-lock/patch files.
Seven function spans distinguish five executed functions from two static-only
consumers. Prior allocator core/binding sources and generated core/bridge ELFs
retain their hashes. No historical receipt is overwritten; glob-based older
input inventories now discover the new reset assembly as an additional input.

## Allocation Budget

Keeping the four-byte word costs 32 bytes after alignment. The corrected
core0 sequence is `[0x89, 0x8a, 0x12, 0x1d, 1, 0x0b, 0x19]`:

| State | Entries | Used bytes |
| --- | --- | --- |
| Corrected core0 initialization | 7 | 430,320 |
| Corrected core0 plus bridge `0x81` | 8 | 489,215 |

The bridge base becomes `0x3e869100`; its 58,879-byte declared allocation ends
at `0x3e8776ff`, leaving 2,305 bytes before heap end `0x3e878000`.

A separate original-allocator invocation on the actual boot-derived metadata
still accepts type 2, returning `0x3e877700` for 6,168 bytes. The declared end
is `0x3e878f18`, 3,864 bytes past the heap. The same metadata submitted to the
unchanged checked C core under both native/UBSan and RV32 execution returns
CAPACITY without mutation. This is a typed allocation request only: no native
RX callback, resumed worker, packet access or out-of-range DMA is executed.

The earlier 3,832-byte counterexample remains correct for the original reset
sequence that forgot the word. The extra 32 bytes needed to retain its lifetime
must be included in the complete allocation budget.
Rejecting a required allocation is not a full functional initialization plan.

## Remaining Work

- Integrate checked allocation/error retention across remaining native callers,
  including core0, without losing control-mailbox service on failure. The new
  reset ordering does not fix ignored lock-owner returns or hardware release.
- Close post-initialization control-consumer and callback-delivery reachability.
  The component write isolates the alias; it does not establish a live failure.
- Reconcile every required allocation and actual consumer extent. The separate
  58,879-byte versus printed 64 KiB bridge envelope remains unresolved. No heap
  or definition table was resized based only on a log string or emulator map.
- Establish fresh-load containment, physical memory/lock/cache behavior,
  complete post-gate startup, ingress/copy/PPE/tunnel/Wi-Fi drains and common
  recovery/removal retention before production integration and NPU-active tests.
- Complete host-adapter datapath and full stock-parity/release acceptance.

Provider-INODE framing and native DESC5/6/7/8 restricted operations were not
retried or rerouted. Source-lock, cumulative patches and packaged overlay are
unchanged. Protected device/calibration/recovery data remain untouched.

## Reproduction

From the canonical WSL repository with the existing pinned local inputs:

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_allocator_reset.py --check
```

Omit `--check` to regenerate `allocator-reset.json`. Generated sidecars and
mutants remain in ignored `.local/npu-allocator-reset/`. The existing checked
allocator build products remain in `.local/npu-allocator/`; no patched firmware
blob or image is emitted.

SHA256:

```text
reset assembly  e98461a2e92c0935a20de76815cc95576ce9ff2da865ea7534f76fe1e7fb1325
reset linker    cf3ac8ba7d426ce1d681d9384b5aae0c9ae0a8c64298b7e7e68b0f8c44c5fd08
reset ELF       c88f39a100106784d813517c2b2be506b798350b2e253eb96608b7658d30cce1
test runner     71c78aed365ef19680d00c508e0cfde19bd9b7754af7649a9a9329204c656af9
receipt         cc7b58883fac7913c71ec383e4d0133f1cd8c892226548923d21d78245c53355
baseline ELF    bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931
```

The four canonical trackers and NPU README record this correction without
closing global allocator ownership, recovery or full NPU implementation gates.
