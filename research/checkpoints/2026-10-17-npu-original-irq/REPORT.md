# Original PLIC Bodies And Error Tails

## Exact Local Scope

Fresh Ghidra12.1.2/AndeStar analysis maps the whole paired CODE image without
overwriting imported bytes. The original80-byte routines at0x84003200 and
0x8400326a enable/disable PLIC sources through0x0c002000/0x0c003000,not Linux's
shared WLAN pending-status register0x30d030. Both have local SP depth0 but
error-tail to the252-byte logger0x840048f4,whose local depth is64 bytes.
Those tails are not silently ignored or treated as whole zero-cost callees.

The logger has four external calls at64-byte caller CFA:

| Site | Target |
| --- | --- |
| 0x8400492c | 0x840067b8 |
| 0x8400493c | 0x840106b2 |
| 0x8400496c | 0x84004218 |
| 0x840049c4 | 0x84006854 |

Their frames/behavior remain unproved here. UART readiness loops and formatting/
lock children remain open. Static logging code clears MIE and later sets it;
restoring the previous MIE value is not established. No full-path MIE-preservation
or termination claim is made. The original source check is signed upper-bound
only;negative arguments are not established as rejected. Our diagnostic normal
inputs are explicitly0..191,not a general original-input safety proof.

The local checker independently decodes every complete body byte,visits both
branch paths/loop joins,checks aligned self-relative SP adjustments and SP-based
memory reservations,and requires balanced SP at reviewed returns/external tails.
Ordinary call/return with restored SP is an explicit assumption. Unknown child
costs remain explicit. Stack aliases/escaped pointers,register-save correctness,
asynchronous IRQ,other harts and physical placement are not proved.

The earlier partial graph is not extended:300 mixed-proof nodes/718 transfers/
six internal dispatches/56 unresolved and candidate9696 remain its old scope,
not a whole permitted-path/IRQ/physical bound. Earlier metadata retains its
40d29368 source-lock;the current host IRQ source-lock remainsd6b6e2da.

## Execution Diagnostics

394 actual original-code emulations pass on synthetic hart0 RAM/MMIO:

- 384 normal-source returns:both routines for all192 explicit sources.
- Eight error returns with the logger explicitly disabled by a synthetic flag.
- Two enabled-logger prefixes stopped before the first unreviewed child at
  0x840067b8. SP remains64 bytes down and RA points inside the logger at those
  stops;the observer does not restore them or claim a completed return.

All32 GPRs,PC,MSTATUS,exact instruction traces,ordered reads/writes and whole
CODE/stack/PLIC/flag memory compare before any restoration. CODE is read/execute
only. Explicit host `reg_write`/`mem_write` are blocked after initialization and
callbacks receive that guarded proxy. This audited program is not a hostile-code
sandbox. MHARTID stays the actual emulator0;no hart-ID override is used.
No UART loops,unreviewed logger children,original cold constructor,physical
interrupt delivery,device pending events,release/reset/reclaim or client scope
is qualified. These394 runs are distinct from41 tiny synthetic unit guests.

## Controls And Preserved Failures

Nineteen local contracts use16 LLVM-generated synthetic fixtures. Initial tests
exposed two checker defects:absolute `SP=0` was confused with entry-relative0,
and a non-RA direct-link jump was accepted as an ordinary call. Failed source,
fixture/log and receipt709b4857 remain preserved. The initial selected-body
cohort is separately readonly-preserved in13 files/1260983 bytes,f1cfb0cb;
that is preservation,not replay qualification or promotion of the old checker.

The corrected checker permits only explicit immediate self-relative SP writes
and ordinary RA link forms. Absolute/dynamic/load/CSR/other-register SP writes,
leaking tails,stack growth/conflicting joins,caller-storage access,unknown
noncall control,traps and incomplete bytes fail closed. Indirect call targets
are not inferred from adjacent AUIPC pairs;opaque ABI calls retain unknown
child cost. All19 controls and the fresh whole-body audit pass. No old failed
receipt is repaired. Three fixture-build failures/default linker choices are
also retained;the successful attempt uses the existing explicit LLVM21 LLD
and image-base0. No tooling installation or native budget change was needed.

Fresh focused193 tests/no skips verify97 inputs/28 artifacts and41 tiny synthetic
RV32 guests. This group overlaps the previous separate214 broader unique tests;
do not sum them as distinct cases. Scopeb634bf81 verifies443 combined paths,
including the unchanged current Linux IRQ checkpoint and both protected images.

## Evidence

| Receipt | SHA256 |
| --- | --- |
| `.local/npu-original-irq-20261017/functions-q1.json` | `0cfa162d395349de0672c7d055bdef9af5f8c74c58d71a86ce2fa9b8f788809e` |
| `.local/npu-original-body-stack/irq-local-q2/result.json` | `159a9a4d6b2e2ea5510a82b0304d87f7b3478ad56b5a06148bec2cd46c36d6ce` |
| `.local/npu-original-irq-20261017/original-probes-q1/result.json` | `75ec9ae4150c25810fd5f874616ce933777c77dc42a75aa822dc572d32647748` |
| `.local/npu-original-irq-20261017/local-contracts-q2/result.json` | `98432df1311531cb39b7f8ef25e1e95d1e48a00373947621bd538ef7c27a65db` |
| `.local/npu-original-irq-20261017/host-scope-q1/result.json` | `3ac1fa2539b20635d7d311d52eb4dbcf7f4fe11e8665aee691baac4615939bbc` |
| `.local/npu-original-irq-20261017/scope-q1.json` | `b634bf819476fe541a9b02ac671aa07dda6a9f495ef394b4cfdbf8835d8750fc` |
| `.local/npu-original-irq-20261017/live-views-q1.json` | `439e87bcda2f2273c65afc26bca66ea361cd940cff5822331a0ce5e1b2e5f7b0` |

Metadata-only `ORIGINAL_IRQ.json` hashes
`58c3aac809d888f010ead1974e2b245ba1c236da441e60e875e5f71dc9b2b0f5`.
The tested seeder/exporter/mapper copies match maintained tools byte-for-byte.
Ghidra names are analyst seeds,not recovered original symbols. Its imported
component DWARF-expression errors remain recorded;the proof uses exact body
bytes,not complete recovered variable locations. No original binary or device
data is committed;the tracked assembly/JSON fixtures are synthetic.

Jev1.13 supports the narrow domain/frame/execution/guard/MIE/control wording with
probabilities0.79/0.73/0.57/0.85/0.55/0.84 and confidences0.69/0.59/0.35/0.77/
0.33/0.76. Execution/MIE uncertainty remains explicit;this is not model approval
or a replacement for byte/execution checks. No resampling was performed.

## Native And Hardware Gates

Read-only recheck verifies2330 frozen files/supplements and both actual caller
mount views still differ from newer main as expected. Neither live job was
restarted or retagged. Both callers/full36 tail matrices/HIF2 bitmap continue
with original guards/budgets. Actual INODE prefixes/new24 faults,full512/eight-
DESC10/all36-tail/broader/current-source/full setup and hot TX/RX/RRO/IRQ/error/
lifecycle/DMA/cache/per-hart/physical/boot/client gates remain required.
Both978f9ddd/a22300ea FITs and source-lockd6b6e2da stay unchanged. No firmware
implementation,image/module build,hardware operation or physical acceptance.
