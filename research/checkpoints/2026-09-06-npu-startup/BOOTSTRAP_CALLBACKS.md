# Original RV32 Bootstrap Callback Contracts

Date: 2026-09-06. Bounded code/test sidecar, no production change.

## Parent Handoff

- API32 is a release condition for the native TX-check initializer, not merely
  passive configuration. Even input zero becomes `0x40000000`. After its callback
  returns DONE, the saved initializer clears `0xe000` bytes at PC `0x84004f1e`.
  The current provider sends it before pkt, txpkt and BA. The native replay
  completes that clear while all three later addresses are still zero.
- API23 releases the zero-address waits in `0x84009fc8` and `0x8400a5fa`
  (both direction selections). Input `0xc0000000` logs errors but still releases
  them. The first consumer already writes five MMIO registers before its wait;
  withholding API23 alone is not evidence that this consumer did no hardware work.
- APIs7/8/23 store all tested 32-bit inputs unchanged. Their `>= 0xc0000000`
  diagnostics are warnings, not rejection. Zero and unaligned values also succeed.
- API18 ignores its value, reports unsupported-on-eagle through printf, and
  returns success without a state write. It does not establish band containment.
- API12 stores the low byte first. Values above 1 produce a diagnostic but remain
  stored. Native routing confirms 1 and 2 take CPU enqueue; 0 and input 256 take
  the PPE-side helper. This is a routing control, not a stop/drain acknowledgement.
- These results establish modelable instruction contracts, not physical safety
  or an admission allowlist. The parent owns reset/state initialization and the
  ledger update; this sidecar does not design a boot protocol.

## Provenance And Reproduction

Run from the canonical WSL repository:

```sh
cd /home/captain/W1700KNPU
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.local/npu-reset/python-lib \
  python3 tests/npu/test_bootstrap_callbacks.py
```

The executable imports the unchanged `Mailbox` and `Boot` helpers, runs original
CODE bytes with the original DATA callback table, and records all non-stack writes
and function-entry PCs for its callback cases. It asserts exact write PCs, the
complete 32 KiB local-SRAM result, diagnostic call counts, payload read widths,
mailbox flags and PLIC completion writes. Both firmware hashes are hard guards.

| Input | SHA-256 |
| --- | --- |
| Original CODE | `e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643` |
| Original DATA | `61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1` |
| Original full Ghidra export | `1536a9972838ca7c02da77629e784b392af919c5d25368478aff4d0c2422e2ca` |
| Actual provider `airoha_npu.c` | `8eed02dd963c9d80fcaf4f15368506f4a4720dd7be4f080c394a21bba7e1fe8f` |
| Actual `airoha_offload.h` | `9359009a4161de572e7f44b41b172860bb6414b56332f16ed6ff8df972126364` |
| Regression executable | `69097c9da46e1223d3e059fec368d7d101c01e6e5b0e542d96733a7221d4af31` |
| Generated JSON | `fda9b83bf73f372b60aa7f9272db66d2c5d680c5850601fe965c7b40f717b626` |

The JSON records full input paths, unchanged helper hashes and 23 complete Ghidra
function spans with normalized-text hashes. Ghidra source is
`research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt`.
Provider inputs are the actual Linux `6.18.44` generated tree specified in the
task, not packaged patch text or an official comparison snapshot.

## Payload And Dispatch

All six current host calls use mailbox function 0 (Wi-Fi), transport WAIT set,
and a 12-byte little-endian payload:

```text
word[0] = (SET=1 << 4) | ifindex
word[1] = API number
word[2] = u32 host value/address
```

`airoha_npu.c:178` defines the header; `:551` builds the message. The native
Wi-Fi dispatcher is `0x84003a9c` (Ghidra lines 7951-8184). It normalizes the
mailbox payload pointer with `(address & 0x3fffffff) | 0x40000000`, selects type
from bits 4-7 of word 0, and indexes the SET table at `0x3e900178 + API * 4`.
It rejects SET API numbers above 33. All six callbacks ignore the interface
nibble; all 16 indices and ignored high header bits are tested for each API.

APIs32/8/23/7 load the 32-bit word at offset 8; APIs18/12 load only the byte at
offset 8. Thus their native readable minimum is respectively 12 or 9 bytes,
including the two header words. This is not firmware length validation: advertised
lengths 0, 8, 9, 11, 12 and 65536 still dispatch with readable backing storage.
The ISR truncates length to 16 bits; the selected Wi-Fi callbacks never check it.
Missing word 2 is read as zero only because the inherited fixture supplies a
256-byte readable, zero-padded tail. No inaccessible/truncated allocation is
claimed safe. Extra word 3 is a canary and is neither read nor changed.

Each selected callback returns 1 even after diagnostics. With WAIT, status 1
and DONE produce flags 7 after callback reads/writes; this is not consumer
completion. Without WAIT, flags 6 precede the first payload read. Those six tests
stop at `0x84003c28` before host notification executes. SET API34 and `0xffffffff`,
and SET_NO_WAIT type with API32, return flags 3 without calling these callbacks.
Unknown type 0 returns flags 7 without executing any of them.

## Exact Callback Effects

Every row also has the common mailbox W1C request at `0x1ec0c000`, synchronous
DONE/status write at `0x1ec0c03c`, and PLIC completion at `0x0c200004`. No other
non-stack write occurs in the tested synchronous callback executions. Firmware
printf internals are stubbed, so this is not a claim about their physical effects.

| API | Callback -> implementation | Native state write and transform | Calls besides dispatcher/return |
| --- | --- | --- | --- |
| 32 TXcheck | `0x8400fb84 -> 0x8400e30e` | u32 `0x3e90469c = (value & 0x3fffffff) \| 0x40000000`, store PC `0x8400e320` | Two printf calls; no address check |
| 8 pkt | `0x8400febe -> 0x8400dbbe` | u32 `0x3e90396c = value`, store PC `0x8400dbd2` | One printf, plus two at/above `0xc0000000`; still writes |
| 23 txpkt | `0x8400fb2e -> 0x8400e2bc` | u32 `0x3e902ab8 = value`, PC `0x8400e2d0` below `0xc0000000`, else `0x8400e304` | No printf below threshold; two above, then writes |
| 7 BA | `0x8400feac -> 0x8400dc0e` | u32 `0x3e902ce4 = value`, store PC `0x8400dc22` | One printf, plus two at/above `0xc0000000`; still writes |
| 18 band0CPU | `0x8400ff88 -> 0x8400dcc0` | None; byte load discarded | One unsupported-on-eagle printf; success |
| 12 forceCPU | `0x8400ff0c -> 0x8400dace` | u8 `0x3e902a78 = value & 255`, store PC `0x8400dad4` | One printf; another if stored byte exceeds 1, without undo/rejection |

## Consumer Dependencies

### Executed Boundaries

- TX-check initializer `0x84004e76` (Ghidra 10729-10854) waits at delay entry
  `0x8400420a` until `0x3e90469c != 0`, then performs 28,672 halfword clears at
  `0x84004f1e`. API32 inputs `0x90c00000`, `0x50c00000` and zero each release it
  and clear exactly 56 KiB in separately mapped model memory. Each other API,
  independently, leaves this wait blocked. Callback completion occurs before
  the saved initializer resumes. This is the initializer, not full reset/main.
- TX consumer `0x84009fc8` (Ghidra 19974-20171) enters its wait with
  `0x3e902ab8 == 0`. Native pre-wait writes are `0x1fb54710` at PC `0x84009ff2`,
  `0x1fb50900` at `0x8400a00e`, `0x1fb50904` at `0x8400a022`, `0x1fb50910` at
  `0x8400a028`, and `0x1fb50914` at `0x8400a040`. API23 zero remains waiting;
  `0x8a000000` and warning-only `0xc0000000` reach `0x8400a058`.
- Consumer `0x8400a5fa` (Ghidra 20840-20959) likewise waits on txpkt for both
  direction 0 and 1; the same three API23 inputs block or reach `0x8400a61c`.
  Both consumer probes stop at their first post-wait branch before descriptor
  construction, and do not represent concurrent execution with the boot context.
- Routing consumer `0x8400aedc` (Ghidra 21470-21703) follows actual API8/API12.
  With packet id 7, length 64 and direction 0, nonzero force bytes 1 and 2 reach
  enqueue `0x8400ac30` with six register arguments `[7,64,0,0,0,2]`. Zero and
  input 256 reach `0x840091b4` with leading arguments `[7,62,0x48007082]` from
  pkt base `0x88000000`. Execution halts at these helper entries.

### Downstream Source Evidence Only

- Beyond the API23 boundary, `0x84009fc8` calls bufid allocator `0x84004c16`,
  writes 2 x 1024 descriptors using `(bufid * 0x800 + txpkt) & 0x3fffffff |
  0x80000000`, publishes ring indices, and sets bit 2 at `0x1fb50a04`. The other
  consumer allocates table index `0x100` or `0x101`, then writes 512 entries.
  These downstream operations are not executed by the wait probes.
- pkt readers include RX descriptor initializers `0x8400b6ba`/`0x8400b7e8`
  (Ghidra 22548-22845) and TX-done initializer `0x8400b432` (22215-22375).
  They form `((bufid * 0x800 + pkt) & 0x3fffffff | 0x80000000) + 0x80`.
- BA consumer `0x8400bc02` (Ghidra 23282-23485) calls `0x8400bb9c`, forms
  `(nodeid * 0x80 + BA) & 0x3fffffff | 0x80000000`, writes descriptors and sets
  a per-selection initialized flag. API7 itself neither calls this consumer nor
  sets that flag. API8 likewise has no direct consumer call/start flag in its
  complete handler. Neither is thereby proved physically harmless to active readers.
- API18 supplies no observed wake or containment condition. API12 changes a
  live branch, not a dedicated startup wait. The exact immediate wake conditions
  executed here are API32 and API23; this is not exhaustive scheduler/hardware proof.

## Coverage And Limits

218 cases pass: 192 callback cases (42 values, 96 indices, 36 lengths, six missing
payload tails, six no-wait and six high-header controls), four dispatch controls,
eight TX-check boot-wait cases, nine txpkt consumer-wait cases, four force-routing
cases and one provider-order interleaving. The actual provider order is checked
against source and enum names/values: `(ifindex=1, API18, 0)`, then index 0 APIs
`32,8,23,7`, finally `(API12,0)`. BA is optional in that source; the interleaving
fixture uses the BA-present variant. Its synthetic addresses are not fresh DTB proof.

The canonical run and two independent scratch reruns produce byte-identical JSON
with the hash above. `git diff --exit-code` confirms all five imported mailbox,
boot, IRQ, stop-counterexample and memory-layout helper files remain unchanged.
Concurrent parent-owned startup/test edits are outside this sidecar and preserved.

Safe to model from this evidence: exact payload loads, alias/truncation behavior,
warning-only writes, callback return codes, immediate SRAM footprints, saved-context
wait transitions, observed MMIO-write instructions and the tested routing branch.

Unproved: complete boot/reset state; physical IRQ delivery, notification or timing;
actual mutex arbitration (the Boot helper seeds owner status `0x1ec03048=0x10000`);
simultaneous harts; cache/coherency/alias semantics; DMA effects, containment/drain;
printf internals; provider failure rollback; downstream helper completion; live
restart or client behavior. Hart ID/printf and mailbox W1C/PLIC are modeled,
IRQ invocation is a saved-frame call and delay completion skips to native RA.
No callback is classified physically safe from source alone.

Only these tracked paths are added by this sidecar:

- `tests/npu/test_bootstrap_callbacks.py`
- `research/checkpoints/2026-09-06-npu-startup/bootstrap-callbacks.json`
- `research/checkpoints/2026-09-06-npu-startup/BOOTSTRAP_CALLBACKS.md`

Reproduction scratch is restricted to `.local/npu-startup/callbacks`. Existing
source, helpers, build trees, configuration, router/hardware, staging and commits
are untouched. The canonical ledger is intentionally unchanged because it is
outside this sidecar's authorized write scope; the parent must integrate this
handoff into its own substantive-work ledger entry.
