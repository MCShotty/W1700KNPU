# Next Checked INODE Boundary

This is an implementation contract, not an implemented native owner or a
hardware authorization. Preserve the current live caller/fault inputs until
terminal and hash-preserve their producing cohort before changing them.

## Exact Caller And Original Entry

- The actual `mt7996_npu_tx_done_init` sends PCIe15/API0, then INODE selectors2
  and7 with `WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR` and scalar zero. The
  compiler-produced sender's getter returns API24, not the unrelated API2
  `WLAN_FUNC_SET_WAIT_NPU_INIT_DONE`. Local receipt `inode-enum-q1.json`, SHA256
  `24c1d82fc6d5eb422d0fc5f262695c27b7e4c623ab2e813d622406b82a38b3f8`,
  checks the actual hashed getter and synthetic raw-consumer contracts for both
  HIF profiles; it is not constructor execution.
- Actual legacy provider framing pads each INODE request to24 bytes. Native
  bootstrap currently admits its12-byte packet, while checked cold requests
  use a separate80-byte NCS2 envelope. A length rejection happens before the
  INODE callback. Do not relabel it as a failed constructor or fix it merely
  by allowing unchecked legacy lengths.
- The original INODE callback is8400fc2c, at API24 slot3e9001d8. Existing original
  prefix/ABI probes cover both12/24-byte payloads, all1036 effects and eleven
  original store sites. They use synthetic RAM/published metadata and explicit
  guard stubs; they do not establish admission of this completed-owner chain.
  The current cold dispatcher has no explicit API24 callback identity; its
  generic fallback is not the original INODE entry.

## Required Source Integration

1. Extend the actual Linux client/server history for exactly selector2 then7,
   API24/scalar zero, after all three tail stages/nine stores. Keep boot/nonce/
   endpoint/TX2/HIF/lease identities and prior STATUS/version compatibility.
   Any new private fields must be appended with updated size/offset receipts;
   the current live producing cohort remains SETUP404, not a later layout.
2. Add explicit authenticated INODE successor helpers through the completed
   tail/RX PCIe/DESC10/RX/TX-buffer/descriptor chain. The current tail helpers
   require a tail request in flight; they cannot be reused unchanged after it.
   Compare held snapshots and exact allowed transitions, not a selector-only
   whitelist or temporarily forged older SETUP.
3. Bind the actual API24 callback and all eleven original stores to the normal
   canonical portable INODE owner. Verify exact paired-CODE type109/fixed ICV
   definition, pointer3e902ac0, full4104-byte extent, neighbors and retained
   storage. Type109 is fixed lookup storage, not a dynamic allocation record.
4. Keep original effect order, frame/volatile/callee-saved/IRQ discipline,
   commit-before-store, exact readbacks and retained faults. Selector2 has1030
   effects;selector7 has six. Matching final flags or callback return1 is not
   execution of every original effect, worker readiness or drain evidence.
5. Extend provider retained-lifetime checks/routing, the actual sender, independent
   store/private/protected-memory oracles and early/late native faults. Rebuild
   the pair/export/source lock normally and rerun full512/eight-fault coverage;
   never promote the old producing cohort or shorten that matrix.

## Following Gate

Final IRQ enablement is two host/provider MMIO operations, not more RV32 mailbox
selectors. Its current void ABI loses startup and hot-poll errors. Constructor
success cannot repair that ABI or prove physical readiness. Continue at
`../2026-10-15-npu-inode-owner/NEXT_IRQ.md` after the checked constructor gate;
workers/hot ownership, complete stack/physical backing/cache/exclusion/drains,
reset/removal/rearm/recovery and actual-image/client acceptance remain open.
