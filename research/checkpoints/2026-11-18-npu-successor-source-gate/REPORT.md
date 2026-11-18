# Exact Successor Sources And Baseline FIT Recheck

## Baseline

The original capsule and four-module producer were not changed. Its private
`make world` returned zero and emitted a 27,042,634-byte W1700K UBI FIT.
The frozen image verifier returned one: its RV32 allowlist had 23 names
while the current Makefile and archive include `rro-native.o`, `rro-wire.o` and
`rro-session.o` as well.

The current verifier now requires all 26 exact RV32 names and still checks
architecture, nonempty text, unique archive membership and exact archived
bytes. Its roster has a Makefile dry-run regression test. An independent
recheck opened the original upper and lower files in a read-only overlay,
mounted the frozen producer separately, and used the corrected verifier.
It passed for W1700K `config-1`: 218 packages, 78 module ABI checks,
four matching packaged modules, and 26 byte-matched RV32 archive members.
The original wrapper then exited with verifier failure and confirmed that
both protected inventories and the snapshot were unchanged. The independent
recheck never replaces that failed wrapper result.

The baseline is now sealed locally as `baseline-txp-20261118-a`.
`--recover-rv32-roster` is explicit and only accepts the pinned failure. It
reconstructs the read-only build view, verifies the prepared sources, and
requires the corrected image receipt to exactly match the independent
recheck. The ordinary sealing path rejected the failed result without
writing anything. The seal then checked the complete original replay
(19,261 operations, 345 input hashes) and extracted the FIT payload
again. The original world receipt is preserved and the seal records its
nonzero return code.

## Successor

`coherent-ppe-qdma-frame-a` supersedes the prior source bundle for the next
build. The prior coherent provider's in-tree Kbuild probe failed: the
cold-command frame was 2,400 bytes, above the 2,048-byte limit. The additive
patch moves the retained lease snapshot to probe-managed memory. The session
mutex, captured fields, offset that excludes the retained-list links, and
before/after comparisons are unchanged. No allocation is added to the cold
command itself.

The new pinned authority verifies the ordered patch tail, nine effective
prepared Linux files, all 330 mt76 source hashes, and 31 component mappings.
The private source fixture does not claim a production build. A late-patch
world must carry a new exact four-module producer bound to that source lock,
configuration and contract. The image seal refuses a stale or missing
prepared-source proof, and the Ethernet seal requires the same bundle.

The revised provider, mt76 `dma.c` and `npu.c` compiled separately using the
pinned AArch64 compiler, retained flags and the original frame limit. All
126 focused host tests passed. These are relocatable objects only. Source
pins, artifact hashes, and the independent FIT receipt are in
[EVIDENCE.json](EVIDENCE.json).

## Next

Keep the sealed baseline as an offline reference. Build a fresh
source-bound producer and world for the successor, then bind its own
replay and fifth (Ethernet) module. No image was flashed, module loaded,
or board contacted.
