# Remaining Native Setup Contract

This is the continuation after selector10/API0, not permission to retire owners
or release workers. Full NPU/physical/hot/recovery/client scope remains open.

## Actual MT7996 Caller Order

The pinned mt76 source calls the RX-event sender (API22, DESC10, PCIe10), then
mt7996_npu_set_pcie_addr, then mt7996_npu_tx_done_init, then enables two IRQs.
The remaining messages are:

| Header | API | Value | Effect |
| --- | --- | --- | --- |
| 0x10 | 0 | BAR+0xd4580 | Bind RX0 PCIe pointer and index1535. |
| 0x12 | 0 | BAR+0xd4560+(HIF2?0x4000:0) | Bind RX2 PCIe pointer and index1023. |
| 0x1f | 0 | 0 | Reset the five previously retained page/indication/RX10 indices. |
| 0x12 | 24 | 0 | Original INODE selector2 run flags followed by ICV clear. |
| 0x17 | 24 | 0 | Original INODE selector7 flags; not a readiness/drain witness. |

Sources: .local/merge-nonoc-20260923/mt76-merged/mt7996/npu.c and
tests/npu/test_mt7996_bootstrap_sequence.py. The latter contains the independent
38-message expected order for HIF1/HIF2 and port2/3. Its sequence is not fresh
hardware execution. The MT7992 selector1 path is a separate model/profile and
must not be silently substituted for this MT7996 contract.

## Original API0 Instruction Effects

Original hash-pinned RV32 observations identify:

- Selector0:8400ba0c stores the supplied pointer at3e902cf0;8400ba18 then stores
  four-byte1535 at supplied+8. Zero/invalid supplied values can retain the first
  metadata effect before an unmapped second-store failure.
- Selector2:8400ba24 stores the supplied pointer at3e903904;8400ba30 then stores
  four-byte1023 at supplied+8, with the same possible partial-effect ordering.
- Selector15 uses the five existing pointers at3e90395c,3e902a80,3e904630,
  3e902a9c,3e902a90. Ordered stores at each pointer+8 are255,511,1023,1535 and
  DESC10-count-minus-one. With the now-proven512 DESC10 count, the last is511.
  Missing-pointer controls retain preceding writes, then fail. Zero count wraps
  the last value to0xffffffff in the original; this must not become admission.

Evidence: .local/npu-pcie-tail-20261014/original-api0-q1.json (64 independent
observations/nine index sequences). These use patterned synthetic DATA/host
regions and skip printf; the index sequences alone model the DESC10 count.
They are original-instruction observations, not new ownership or hardware proof.

The new original-remaining-profiles-q1 receipt adds12 complete BAR/HIF profiles
and missing-pointer controls using actual0xd4580/0xd4560/HIF2 offsets. Original
callbacks install all five preceding pointers; only DESC10 count512 is modeled.
All nine distinct store sites and whole1MiB BAR/64KiB DATA comparisons pass.
This remains an original-instruction fixture, not candidate admission.

The completed TX owner provides a direct software profile link: PCIe0 equals
retained TX0+0x160; PCIe2 equals retained TX2+0x110. Exact arithmetic is checked
for HIF1/HIF2. Validate the independently finished TX owner/held immutable plan
before using this relation, rather than accepting a new request flag as its own
provenance. Require the extra full12-byte register extent after the addition.
Neither numerical correspondence nor this fixture proves a physical alias.

## Required Implementation

Bind all nine original store sites (two + two + five) and retain their ordered possible effects.
Require completed selector10/DESC10/prior owners and authentic current setup,
held BAR/endpoint/session/nonce, exact register extent/address/value, original
lock/IRQ context, neighbors and readback before advancing each stage. Never
reset existing ownership after a failed second/later store. Preserve HIF2's
derived offset explicitly and reject wrong-profile operands before effects.

Selector15 must derive every pointer/count from the independent completed
owners, not from unchecked nonzero metadata or a test-written lease. Compare
all protected bytes against pre-state plus exact request-derived effects and
sequence; retain callee-saved registers and original frame. Cover early/late
failure, malformed operands, register/readback/neighbor/IRQ faults, lost/mutated
replies and native mutation controls before full actual-caller acceptance.

INODE's original wrapper reads24 bytes although these three-argument commands
carry12 declared bytes; the provider's retained bounce has256 bytes. Existing
framing proof and selector2/7/4 traces distinguish declared span from physical
capacity. Maintain the padded contract and exact ignored-tail semantics; do
not call it a physical overrun or Wi-Fi root-cause fix. Own run flags, full
4104-byte ICV extent/clear and every prerequisite before any initialization
claim. Final IRQ and full worker/hot/physical/recovery contracts stay separate.
