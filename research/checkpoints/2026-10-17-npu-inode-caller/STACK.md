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
