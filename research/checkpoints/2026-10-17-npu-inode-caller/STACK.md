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
