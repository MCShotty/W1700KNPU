# Original Relative Switches

2026-10-20. One additional original routine now has a conditional local-SP
analysis. The formatter remains denied. This does not extend or requalify
the older whole-CODE graph, establish a whole interrupt-stack bound, or
qualify a cold constructor or physical device.

## Change And Controls

The table checker now recognizes the narrow AUIPC/ADDI, unsigned BLTU,
index-shift, relative-word-load, base-add and nonlinking-register-jump form.
It checks exact register relationships, bounded count, alignment, extent,
internal instruction starts, complete-prefix predecessors and guard-edge
dominance. The optional biased-index instruction is before the guard.
Unknown register flows and traps remain rejected. The older absolute-table
grammar, 31 fixture programs and strict Ghidra label/order contract stay.

The local-SP checker accepts an optional table reader, not a target allowlist.
It runs the complete table checker on the same body before using internal
successors. Default behavior, SP-write restrictions, merge consistency,
local-memory extent, balanced exits and all-body reachability remain. A table
snapshot's immutability is an assumption, not physical permission evidence.

All249 unique units / 267 executions pass, without skips. This includes the
previous broader selection and15 new methods; do not add overlapping older
runs. There are22 separately compiled synthetic relative fixtures and24
synthetic prefix guests with all32 GPRs, PC, MSTATUS, ordered reads, no writes
and whole mapped protected memory checked before restoration/case bodies.
The first synthetic assembly compilation failed on an out-of-range branch;
its exact source/log remain. Intermediate generated fixtures remain private.

## Original Bytes And Results

Both full bodies and table bytes match the original executable blob and
current CODE `658c9c32`. Full instruction bytes match the existing Ghidra
exports. Those exports came from older CODE `a6813d39`; unchanged bodies do
not requalify that imported ELF or the whole current graph.

- Formatter `0x840107ca`:7544 bytes/2707 instructions,91 words/28 unique
  targets at `0x8401d4b4`. CFG and local-SP still fail
  `prefix-can-bypass-definition`. External direct entries are
  `0x84010a38 -> 0x840108d2`, `0x840110fa -> 0x840108ca` and
  `0x84011118 -> 0x840108ca`. Those paths are not waived.
- Callee `0x840183b2`:2876 bytes,15 words/five unique targets at
  `0x8401dc3c`. Complete-prefix/guard CFG and all-body local-SP checks pass;
  its local frame is192 bytes. All external child costs remain unproved.
- Original isolated dispatch prefixes execute93 formatter and17 callee
  cases, including out-of-range guards. Exact registers/PC/MSTATUS, ordered
  reads, no writes and whole mapped CODE bytes are checked before restoration.
  Registers and memory permissions are synthetic. They stop before case
  bodies and execute neither complete routine nor external callees.

Both recovered Ghidra target sets match table-plus-default sets, but Ghidra
labels are not used as indices or permissions. Tables are inside executable
blobs, not the older compiled-ELF read-only-data profile. No physical read-only
permission, asynchronous mutation exclusion, termination, alias/escaped-stack
proof, complete child chain, per-hart/IRQ/physical bound or hardware proof.

## Evidence And Next

Metadata-only `RELATIVE_SWITCHES.json` hashes
`ce6f9e3ab699194b2c22f0bb71099666d71c6549e63f0f140e0268fa0fbdd9b6`.
Private scope `c569d64755b63aacfb547f425d6e6e7815b0e6091b9e9154368e082108e5a4a4`
verifies2551 paths, including2366 readonly pre-edit capsule files. That capsule
is preservation, not replay qualification. Original-prefix receipt
`f4a1995a1add4ef1e407941a5657c6b89f6d8265b3ac00f673dc165be009497c`
and broader-unit receipt `8613ccc6` remain private; no firmware bytes are
included here.

Jev's semantic checks report same-body requalification0.93 and retained
unknown-flow rejection0.88; tests/source provide the covered checks. Its
formatter-qualification contradiction is1.0; physical/whole-stack claim
contradiction0.91/confidence0.86. These are judgments, not proofs or approval.
Prior SP uncertainty is not erased by them.

Next: qualify every formatter prefix entry without weakening the guards,
then address remaining original/indirect and child-chain contracts. Current
fresh cold/fault jobs remain separate. No firmware, source-lock, raw pair,
saved image, native limit, hardware or subagent change occurred here.
