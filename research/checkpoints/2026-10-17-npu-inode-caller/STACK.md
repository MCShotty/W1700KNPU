# Current Exact Stack Audit

These are static checks of the20-component/168-hook600055c candidate,not a full
physical stack bound or a native constructor verdict. No firmware source or
image changed for these measurements.

## Evidence

| Receipt | SHA256 | Covered Scope |
| --- | --- | --- |
| `.local/npu-raw-stack/inode-caller-q1/result.json` | `83f8262587f7aeb8e21bed2fb41ac658ca2a57dd37a0f2ca39ad31502b1887ab` | 297 compiler C frames;all20 allocated components/full CODE/DATA byte-identical |
| `.local/npu-assembly-stack/inode-caller-q1/result.json` | `16295fbcd6e904a5a35b5647d3f3ef25874c45318f62e7b9a12f8ce9cfd115d8` | Four pure-assembly ranges/five explicitly typed wrappers;not all assembly |
| `.local/npu-direct-stack/inode-caller-q1/result.json` | `c209050c08a95ec0d8b5f58adf12f1ed1728146b7302deefe5942bf6ea2d4174` | All297 C frames independently matched to CFI;687 direct transfers |

Largest individual frame is4704 bytes in the portable INODE `context`,which
holds an exact4372-byte owner snapshot across read callbacks. The largest direct
graph candidate is9696 bytes,rooted at `npu_emulation_inode_callback`,through
INODE begin/context,PCIe-tail/RX-PCIe/DESC10 predecessor checks and
`packets_live`. Each edge uses its callsite CFA,not blindly adding every local
peak. Reserve/publish roots have9648-byte candidates.

## Still Open

There are91 unresolved transfers:75 register transfers and16 direct calls/tails
outside the measured C graph. No cycle was found in this restricted graph.
Missing indirect readers,original firmware/assembly,native wrappers,IRQ nesting,
per-hart placement and physical stack mapping prevent a full permitted-path or
physical bound. A direct graph candidate can include infeasible paths;it is not
a measured runtime watermark. The earlier264-frame/4480-byte candidate does not
cover this new constructor component. Do not compare9696 with an assumed stack
size and declare the stack safe.

## Direct-Target Identification Lead

A read-only exact-ELF lookup maps the16 outside-C direct edges to10 target
addresses:nine named displaced prefixes and the original target0x8400dd82.
`.local/npu-world-overlay-20261017/direct-targets-q1.json`,SHA256
`7d4bb1b20dca10bfaf1d06d8f56875f210d68d502b916b2a507ad0599de20276`.
This is symbol identification,not a replay/extension of the earlier C graph.

Exact CODEa6813d39 fragments record at most five instructions per target,
stopping at the first unconditional jump. Receipt
`.local/npu-world-overlay-20261017/stack-prefix-fragments-q1.json`,SHA256
`a3be61db25887126bb584819dd9bbd84affff70a5a46a28d3392a83ad81fe27e`.
IRQ prefix0x84044f08,token prefix0x8408523c and descriptor prefix0x840894fe
each contain addi sp,sp,-16 before the jump. Thus the named prefixes cannot
all be treated as zero-stack wrappers. This does not establish their complete
function frames or original continuation behavior;the other fragments are not
whole-function zero-stack proofs either.

The297-C-frame/687-direct/91-unresolved graph and9696-byte restricted candidate
are unchanged. Original continuations,all75 register transfers,IRQ nesting and
physical/per-hart placement remain open. Jev q10 contradicts the all-zero-SP
claim0.67/confidence0.51 and leaves a whole-path bound not established0.95/0.92;
neither judgment replaces instruction/flow contracts. No source/image/native
admission change,guest execution or new permitted-path/physical bound.

## Bounded Prefix Verifier

The new test_npu_displaced_prefix_stack.py binds the nine selected prefixes to
their hash-checked linked ELF and raw CODE bytes. It decodes through only the
first unconditional direct jump,records local SP changes/stores/continuations
and checks the exact known9-prefix set. Unsupported/dynamic SP changes,caller-
frame/foreign stores,conditional/indirect flow,missing tails and malformed
metadata fail closed. These are not complete functions or an ABI-return proof.

Actual20-component-pair audit
`.local/npu-displaced-prefix-stack/inode-caller-q2/result.json`,SHA256
`6d0422522bfbc88ec3f9881f52a8d6e49b0ed2d836d6abd959c17aa923373a1b`,
passes nine prefixes/12 input hashes. IRQ/token/descriptor reserve16 local
bytes;the other six have no selected-prefix SP change,not zero whole frames.
Do not add the copied prologue reservation blindly to original function frames.
The297/687/91/9696 C-graph scope is neither replayed nor extended by this check.

Initial ordinary-lw operand assumptions rejected compressed c.lw in the new
synthetic and actual checks. Capstone5.0.7 exposes c.lw as REG,IMM,REG,not the
ordinary REG,MEM form. The bad source/fixture copies and two actual failed
commands/logs remain read-only at
`.local/npu-world-overlay-20261017/prefix-parser-failure-q1/result.json`,SHA256
`1b9ca810de257f85718403d7aa65b61feb36c521a5d28ac3a665fd2f9b73d739`.
The corrected operand-specific path retains the strict checks.

Twelve contracts use22 LLVM21-generated synthetic program fixtures,plus a
backward transfer built with the existing npu_image.jal encoder. Six tiny
programs execute in Unicorn;actual PC/SP/all32 GPRs/writes match before any
register restoration. This is synthetic RV32 execution,not router firmware.
Fixture SHA256
`eacc7bf0dc7349859aa03e21e914bf069b1534154ed82d7a306d6fbaa513763d`.
The earlier five-guest72-test source/artifact set is preserved in90 files/
1119620 bytes,receipt
`.local/npu-world-overlay-20261017/prefix-forward-scope-preserved-q1/receipt.json`,
SHA256 `65050f7bf2962cf59c020ce5f08746c202e026a259f2b264e7b41748b89d1ef0`.
Preservation alone is not a private replay or complete runtime environment.

Latest focused scope `.local/npu-world-overlay-20261017/host-scope-q5/result.json`,
SHA256 `00b9f6edbd1a9ebfb00204b4826796b1fe4457861b5ae33c0c476faf509335b4`,
passes72 unique tests/no skips/87 source/artifact hashes,including the12 new
contracts and six recorded synthetic guests. Jev q11 supports raw binding0.99/
confidence0.98,pre-restore observation0.87/0.80 and compressed shape0.98/0.97;
whole-chain bound stays not established0.81/0.72. Final q12 supports the
independent target0.96/0.94,observation0.81/0.72 and synthetic-only category
1.00/1.00. Raw probabilities are retained,not substituted for direct checks.

Original continuations/75 register transfers/IRQ/per-hart/physical bounds remain
open. No NPU source/guard/source-lock/image or hardware changed. Both frozen
callers/full36 matrices and HIF2 bitmap remain live;these static/synthetic
checks do not promote their pending results or newer Linux integration.

## Guarded Literal Register Target Supplement

The new test_npu_constant_targets.py supplements,not rewrites,the prior graph.
It verifies its inputs and every297 measured function's exact symbol extent,
linked ELF bytes and raw CODE match. Adjacent LUI/ADDI/register-transfer
sequences are checked with decoded operands and local control flow. An unknown
register transfer or unsupported flow anywhere in the function prevents local
qualification. Direct branches entering the ADDI/jump without its preceding
definition,unreachable definitions,mid-instruction targets and traps are rejected.
This assumes entry at the exact function start and ordinary ABI call/return.

Actual20-component audit
`.local/npu-constant-targets/inode-caller-q1/result.json`,SHA256
`9ab060c56efd3a26dfd8680fb75d4f4a8345c82e78526bd49d378319c1dff673`,
verifies371 inputs. Of75 prior unknown register sites,30 match the literal
shape and27 pass the guards. All27 point to three original-firmware addresses:

| Target | Guarded Sites |
| --- | --- |
| 0x84004212 | 9 |
| 0x840064b4 | 8 |
| 0x8400651c | 10 |

The other three candidates remain rejected:one in npu_emulation_irq_dispatch
and two in npu_emulation_descriptor_callback,because their functions also
contain other unresolved register flow.48 sites remain unidentified by this
qualified subset. This does not mean27 stack edges are closed:the three original
callees' complete frames/paths are outside this supplement. The prior graph
remains297/687/91/9696,not extended or replayed as a new complete bound.

Twelve new contracts use18 toolchain-generated synthetic fixtures,including
bypass/unknown-flow/unreachable/trap/encoding/alias cases. Seven tiny RV32 guests
check actual PC,RA,SP,all32 GPRs and absence of memory writes,including backward,
low-bit clearing,32-bit wrap and both conditional paths into a full definition.
They are synthetic instruction programs,not original firmware. The target and
compressed return-address rules were checked against the primary
[RV32I ISA](https://docs.riscv.org/reference/isa/v20260120/unpriv/rv32.html) and
[compressed ISA](https://docs.riscv.org/reference/isa/v20260120/unpriv/c-st-ext.html).
Fixture SHA256
`fcab677111e580e6745e1190023a9dae17a0a83943af70eaaad21276bf649c34`.

Latest focused `.local/npu-world-overlay-20261017/host-scope-q6/result.json`,
SHA256 `e90da153dd876dbc573a44321524390fbca4e39c0614b3de2c91181227ccf044`,
passes84 unique units/no skips/95 source and artifact hashes. It records13 tiny
synthetic guests:seven new literal-target guests plus the previous six prefixes.
The older72-test scope is unchanged,not relabeled as testing these new files.

Jev q14 supports the narrow scope0.86/confidence0.79,bypass rejection0.95/0.92
and unknown-flow rejection0.95/0.92. Its observation judgment is contradictory
but uncertain0.58/0.37;whole-stack claim is also contradicted0.70/0.55.
All probabilities are retained. The code sets initial registers before emulation
and reads them afterward;expected-value list updates do not write the guest.
Rather than treating a model judgment as proof,an independent unchanged-test
replay installs a Python API proxy that raises on post-emulation reg_write.

`.local/npu-world-overlay-20261017/literal-guest-observation-q1.json`,SHA256
`e8027d69bfc07c1ddfd413bbc1b5a26796f4a8d1d728ab2c05b26e255a58efea`,
passes seven replayed synthetic guests with records exactly matching the84-test
scope. Each has33 post-emulation reads (PC plus32 GPRs),one emulation and zero
forbidden writes. The proxy guards test Python API writes,not normal Unicorn
internal instruction effects;it does not certify original firmware/observers.
This is separate evidence,not a repaired or silently relabeled Jev result.

No NPU/source-lock/image/guard changed,guest pipeline restarted,hardware action
or subagent used. Both original callers/full36 matrices and HIF2 bitmap remain
live. Original callees,other indirect paths,IRQ/per-hart/physical bounds and all
broader/current-source native/full-setup/hot/lifecycle/boot/client gates remain.

## Three Original Callee Bodies And Hart0 Diagnostics

Fresh Ghidra12.1.2 analysis imports the checked inode ELF and uses the existing
MapNpuRawCode script to verify all998644 paired CODE bytes (15602 imported
component bytes,two exact gap mappings). Three analyst-seeded function entries
are exported after automatic analysis. Every decoded instruction and complete
body range matches Capstone and the untouched original e743d1b5 CODE bytes,
not merely the patched pair's labels.

| Original Entry | Body Bytes | Local SP Depth |
| --- | --- | --- |
| 0x84004212 | 6 | 0 |
| 0x840064b4 | 104 | 16 |
| 0x8400651c | 64 | 16 |

The getter reads mhartid. Acquire/release call that getter and save/restore their
16-byte frames. The one-off exact-body CFG/SP audit admits only the reviewed
opcode set,checks branch destinations/instruction boundaries,requires one SP
delta at each merge/cycle and balances every reviewed return. Both direct calls
target the zero-frame getter. This assumes exact entry,ordinary call/return and
no asynchronous IRQ or external stack mutation. It is not a generic firmware
prover,physical stack map or complete permitted-path/IRQ/per-hart bound. The old
297/687/91/9696 graph is not rewritten or extended;fresh scoped integration is
still needed before any new graph claim.

129 isolated executions use the actual emulator hart0,synthetic argument/stack/
MMIO RAM and original instructions:one getter,96 acquire comparisons across32
lock encodings/three status outcomes,and32 release-encoding comparisons. Actual
PC/SP/RA/14 saved registers/MSTATUS,ordered writes and complete protected code,
argument,stack and MMIO bytes match before restoration. No observer modifies
guest instructions,registers or memory. Synthetic owner/status values are test inputs,
not genuine allocations or physical ownership. Release cases characterize byte
encoding,not authorization to release a real/unowned lock. A direct attempt to
write Unicorn MHARTID was ignored;the diagnostics therefore do not claim harts1-7.

Metadata-only [ORIGINAL_CALLEES.json](ORIGINAL_CALLEES.json),SHA256
`2fb12ac4d37e4bacc64a311df2d4f76939bed37df538c1ec36bb9c8df9c21fc9`,
records the verified ranges,helper copies,receipts,limits and unchanged images.
Private evidence under `.local/npu-world-overlay-20261017/`:

- `ghidra-literal-targets-q4/functions.json`,SHA256
  `59f8ee3ac505349d83e611795e6b267fe7fed225ec4be59a6ef12f5619cb64a8`.
- `original-literal-callees-q1/result.json`,SHA256
  `32fe94a44cce2a3c75f2c4770ba9113f3651502ce05dfc5931be644a73693f5c`.
- `original-literal-stack-q2.json`,SHA256
  `a8b07ff182546c0f87d2684a34ab97e51906a27496de1e6e988e5ea3d3367c50`.
- `original-observer-write-audit-q1.json`,SHA256
  `9eca582e114ba22338366dd38c8be56978d62620d2220e457a3d1df94a22f323`.

The selected original bodies export/decompile successfully;imported C-component
DWARF expressions could not all be recovered. Those errors stay in analysis.log;
this does not certify all variable locations or the rest of the mapped program.
The committed Java helpers are byte-identical to q4's tested private copies.
The project is under scratch/npu-literal-targets-20261017-q4,not protected old
analysis state. Earlier q1 split-script-path/q3 hidden-project-path launches
failed before import. The q2 preparation log assumption and the first SP audit's
malformed digest failed before producing a result;their sources remain intact.
Successful q4/q2 outputs have new identities,not repaired failed records.

Jev q15 selects original-routines-on-synthetic-platform1.00/confidence1.00,
supports scoped wording0.97/0.95 and classifies the DWARF errors as metadata
limitations1.00/1.00. Its expected-array-restoration claim is supported0.67/0.51
but not followed:the source makes no explicit mutating API call after emulation
or in its observers. Separate source/API audit9eca582e also performs two actual
memory-copy experiments with no guest instructions. Updating a local expected
bytearray after copying bytes into Unicorn does not restore guest memory.
The observer-mutation claim is contradicted0.80/0.70. All raw distributions
remain retained;none is substituted for the direct source/byte/execution checks.

The84-unit/95-hash/13-synthetic-guest scope is unchanged and separate. Original
and new image hashes978f9ddd/a22300ea and source-lock40d29368 recheck unchanged.
No NPU implementation,live producing input,guard,coverage,budget or hardware
changed. Both actual callers/full36 matrices/HIF2 bitmap remain live;new24
INODE/broader/current-source native/full setup/hot/lifecycle/physical/boot and
actual-client gates remain open. No restart or subagents.

## New Restricted Mixed-Proof Graph

A fresh view composes the297 prior CFI C frames with the three exact original
body/SP proofs and27 locally guarded literal targets. It does not modify or
reinterpret the old c209050c receipt. The new graph verifies the prior graph,
literal-site and original-body input identities,exact callsite CFA/name/address,
covered target entries,nonoverlapping extents and original call instructions.
No unselected unresolved record is discarded. Unknown added callees,duplicate
sites,CFA drift,overlaps,unqualified targets and malformed frame shapes fail.

An explicit guard requires every complete CODE.bin alias in the prior graph to
match both native and Ghidra CODE identities. This rejects cross-version proof
mixes even if the selected routines happen to have the same entry addresses.
The actual shared identity remainsa6813d39. This does not qualify later Linux
host integration,physical context or full NPU setup.

| New Subset Measure | Result |
| --- | --- |
| Nodes | 300:297 CFI C frames plus3 original-body SP frames |
| Resolved transfers | 716:687 prior direct,27 literal-register,2 original direct |
| Remaining transfers | 64:48 register-unknown,16 known targets outside subset |
| Cycles in reviewed subset | 0 |
| Largest restricted candidate | 9696 bytes |

The count716 must not be called syntactically all-direct;the300 frames are not
all CFI-proved. The remaining64 targets are outside the ranked subset,not proved
zero-frame functions. Ranking can include infeasible paths and excludes missing
callees;no complete permitted-path/IRQ/per-hart/physical bound follows from the
unchanged9696 value. Exact entry,ordinary call/return and no asynchronous or
external stack mutation remain assumptions. Other assembly/original/indirect
paths remain required. The original graph stays297/687/91/9696.

Actual `.local/npu-resolved-stack-subset/inode-caller-q2/result.json`,SHA256
`66b6ac6a5218b5f12d5ac8e9ed724b3e685fb623003782c8e28af6e39016a748`,
passes with387 input hashes. Sixteen new subset contracts and10 existing
direct-transfer regressions cover composition,missing/duplicate/unqualified
targets,CFA drift,frame shapes,cycles,overlap,input immutability and mismatched
CODE cohorts. The unchanged13 tiny synthetic guests remain separate from129
original-routine hart0 diagnostics. No new original firmware executes here.

Latest `.local/npu-world-overlay-20261017/host-scope-q8/result.json`,SHA256
`aca6da424e7706208f9c70e9631cc145d54de2668f16a52a73b32c89891de7d6`,
passes110 unique units/no skips/102 source and artifact hashes. No earlier
scope is relabeled as testing this final CODE guard.

The first subset and108-test source/artifact cohort were preserved before the
guard edit in `.local/npu-validation-capsules/stack-subset-v1/receipt.json`,SHA256
`781aca3c2781db17215b809cbe01593bc50afab2398907223af606fbd17f12f5`.
All2434 readonly files/525298077 bytes and the contained older receipts' declared
inputs/artifacts recheck. It is not privately replayed or a complete portable
environment. Git8fbac57 is only an anchor:the two subset source files were then
untracked and explicitly included,not secretly part of that commit.

Metadata-only [SUBSET_STACK.json](SUBSET_STACK.json),SHA256
`f0085c20e1585d20609cb174e97cd0fb8023652f457257f2a251d3b7c046e55e`,
retains the full64 unresolved records and provenance. Jev q16 selects the
mixed-static and missing-targets-outside-ranking categories1.00/confidence1.00,
supports scoped wording0.97/0.95 and contradicts a physical-bound claim with
uncertainty0.69/0.53. Raw probabilities remain retained;code performs all counts
and candidate calculations. Model judgments are not proof or permission.

No NPU implementation,source-lock,image,live producing input,coverage or native
budget changed. Both actual callers/full36 matrices/HIF2 bitmap remain live;
new24 INODE/broader/current-source native/full setup/hot/lifecycle/physical/boot/
client gates stay open. No hardware,restart,waiver or subagents.
