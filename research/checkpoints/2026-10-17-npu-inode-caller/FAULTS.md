# Retained Constructor Fault Controls

## Scope

The new native diagnostic runner requires a real hash-bound pre-INODE snapshot
from the actual provider allocator/caller. It never constructs earlier SETUP,
seeds an owner,changes guest guards or replaces the original instructions.
Restored success is diagnostic,not a new boot/allocator/caller or physical proof.
At this checkpoint the real constructor prefixes are pending and **none of the
24 native INODE faults has executed**.

Both stages require the same12 faults:callback-slot,prior-tail-fault,wrong-address,
wrong-width,wrong-value,late-IRQ,late-nonce,late-neighbor,store-readback,
late-packet-fault,release-fault and unlock-neighbor. All24 must pass before the
aggregate can pass;every cached row is revalidated against current pair/raw/
component/host ELF and snapshot/source hashes. No case-count or native budget
reduction is allowed.

## Exact Checks

- Exactly one explicit fixture memory/register injection and the expected
  original store prefix:zero at entry/reserve,one unpublished at publish,or
  all1030/six stores before release. Expected store effects use the independent
  original literal recipe.
- Exact4372-byte owner,412-byte failed/inflight SETUP,3072 packet claims and
  all868352 protected bytes. The whole2MiB CODE/private region must match its
  projection except the existing current-core16KiB stack band. Earlier native
  private owners are not broadly exempted.
- Original callback/wrapper/helper/release entries and ordered added-lock18
  effects. Release checks MSTATUS0,or8 only for the deliberately injected
  late-IRQ fixture,and unchanged MIE/MTVEC. The real ABI is checked before the
  mailbox helper restores CPU context. No workers,reclaim,reset or drain claim.

The first diagnostic release override skipped the positive observer's common
masked-IRQ check as well as its clean-owner assertion. Review and Jev's narrow
check exposed that omission before any native fault execution. A dedicated
negative unit now flips each release CSR at both stages. The production guard
and positive observer were unchanged. Initial Jev probabilities and source
excerpts remain in `jev-fault-q1.*`;the changed-source check is `jev-fault-q2.*`.
Jev's limited-confidence judgments are not runtime or permission evidence.

## Preflight And Copy

Fault preflight `.local/npu-inode-caller-20261017/fault-preflight-q1.json`,SHA256
`4c7f7174e0c5e1d955ba2b75959e7198197f9c7f17a351f39a6e3194250215f2`,
verifies378 hashes and208 unique cases/226 executions,no skips. Twelve added
synthetic contracts cover the projected faults,release CSRs and matrix admission;
the18 preexisting imported cases still execute twice.

The original2330-file producing capsule and its receipt remain unchanged.
Additional diagnostic consumers are explicitly recorded in:

- `inode-fault-consumers-q1.json`,SHA256
  `2c323aa1db7877e43dbd1a9d3880ad76bfef74e9e3dffaad0fe15c1849a8e650`:
  four new runner/contract files.
- `desc10-entry-consumer-q1.json`,SHA256
  `f6fee2084ac165bd84748e3880faba41c0726bbab350ff0ce529e682644136ce`:
  a CLI entry into the unchanged eight-case full512 DESC10 consumer.

The seven projection/five matrix units also pass inside that original-path copy;
execution receipts82c1aae5/b74d4698 confirm unchanged parent mount. These are
synthetic units,not actual constructor faults. Both existing eight-case DESC10
matrices are live from actual captures,with two workers/profile. All36 tail
faults and all24 constructor faults remain required. Current partial/live status
never promotes the failed older404-byte aggregate or a later mainline change.
