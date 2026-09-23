# NPU Cold-Loader Reset-Control Prerequisite

Checked 2026-09-23. Candidate 930 corrects the shared reset-controller primitive
that would underpin a future NPU cold-loader integration. It is unpromoted and
does not itself wire a reset line into the provider, establish containment, or
make the Linux V2 executor safe to initialize on each mt76 attachment.

## Source And Defect

The pinned Linux 6.18.44 archive and eleven patches from OpenWrt commit
`f3173f41940ab15d63a205f6d618e145d49ee58a` reconstruct
`drivers/clk/clk-en7523.c` byte-for-byte against both prepared kernel trees.
Each contributing patch matches that Git commit; the tarball matches the
commit's `LINUX_KERNEL_HASH-6.18.44`. Baseline driver SHA256:
`a4fc60fd9cbde304bf4e925c7de8c08becae8aa37837f76abfeed5d6d07e98ca`.

The reset update callback uses `val |= ...` before initializing `val` and always
returns zero after `regmap_update_bits()`. The status callback ignores the
`regmap_read()` return before inspecting its output. Thus callers can receive
success or a boolean status when the underlying register operation failed.

The EN7581 NPU binding is logical ID 8, translated to bank 0 bit 9 at offset
0x830. The callbacks also serve EN7523 and AN7583, including inverted PCI reset
lines where supported. Their maps, polarity and public layout are unchanged.

Candidate 930 changes only two functions:

- Assign the requested reset value directly, with the existing polarity.
- Return the reset-write status instead of unconditional success.
- Return read errors before evaluating reset status.

Patch SHA256:
`59a2c14ed7e8ba6f215bb4c4b8e649f8db3842a9d75d9486588d4875cd3fa1d5`.
It applies with zero fuzz and no offset; strict checkpatch reports zero errors,
warnings and checks. Initial patch-format/checkpatch issues were corrected
before the successful run; failed scratch attempts remain under `.local/`.

## Host And Target Evidence

The actual extracted callback/translation C runs under ASan/UBSan with a regmap
model. All 147 logical reset entries are covered: 42 EN7523, 56 EN7581 and
49 AN7583. The 23,088 corrected executions comprise:

- 19,992 nominal assert/deassert cases with subsequent status checks, across
  68 register seeds and every mapping.
- 1,764 failed writes, including failures both before and after a modeled
  register side effect. No retry or rollback is invented.
- 1,323 failed reads with unchanged, zeroed or all-one output storage.
- Nine invalid logical-ID rejections before register access.

Four original-source controls fail the named oracles, while the candidate
passes. Seven compiled mutants are rejected: indeterminate value, hidden write
error, hidden read error, wrong PCIC polarity, wrong mask, wrong bank and repeated
failed write. Parameterized case counts are not full-goal coverage.

Both complete driver variants and two layout probes compile as four AArch64
kernel objects without diagnostics. The 13-value target layout is identical.
The target kernel configuration remains unchanged, with `CONFIG_INIT_STACK_NONE=y`.

`test_npu_reset_native.py` executes the actual target-compiled assert, deassert,
status and translation instructions. Each variant passes 5,007 oracle checks,
including 3,087 injected-error cases. Regmap is an explicit external-call model;
the emulator checks call arguments, side effects, one-call behavior, preserved
registers/stack and translated IDs. It does not execute real MMIO.

**Important distinction:** this GCC build resolves the source's indeterminate
write local to zero. The original and corrected target instructions therefore
agree on the tested normal polarity. The source failure controls use explicit
Clang pattern initialization; they do not demonstrate a live target polarity
failure. The original target instructions do suppress every injected register
error, whereas the corrected instructions return it. Native NPU-ID examples
are retained in `reset-native.json`.

Independent Windows readback verifies 132 unique referenced files, totaling
172,501,687 bytes, with no mismatch. This includes the source archive, pinned
patches, generated/extracted sources, binaries, objects, logs and both receipts.

Receipts:

- `reset-control.json`:
  `c627c45569b2e142b635f68a6ced59460749232f184bc99fe5215bf672a60c7d`.
- `reset-native.json`:
  `d0fe65272e356c397324ddd763416e5c5c80166f3ec13676503acc03e23779d9`.

Jev's bounded checks corroborated shared-map regression scope and the separation
of software behavior from physical containment. Raw probabilities and requests
are retained under `.local/npu-reset-control/jev-*-*.json`; these judgments are
not used as replacement proof for the tests or native instruction checks.

## Remaining Integration

The current provider loads firmware before any proven containment operation and
does not request the NPU reset line. Merely adding an assert call is not enough:
the reset domain's coverage, shared GDMA/PPE/tunnel owners, outstanding bus work,
SRAM access while reset, and release/publication ordering remain unresolved.
Readback of a reset bit would still not certify those properties.

Next, establish the actual containment and provider lifetime contract before
publishing fresh boot identity/session storage and connecting the V2 executor
to mt76. Do not turn successful reset register I/O, software PARKED, or a new
consumer attachment into permission to reclaim tokens/rings or restart DMA.
Full boot, physical drains, cleanup/rearm and full stock-NPU parity remain open.

No source-lock/overlay promotion, packaged image, module load, router operation,
Wi-Fi configuration, protected-data, restricted INODE/DESC operation, subagent,
flash or commit/push action occurred. The ledger and resume documents record
this prerequisite without closing the recovery gates.

## Replay

Run in the canonical WSL repository; choose fresh replay destinations:

```sh
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_npu_reset_control.py --build-name replay --output-dir .local/npu-reset-control/replay-evidence
PYTHONPATH=.local/npu-reset/python-lib python3 tests/npu/test_npu_reset_native.py --output-dir .local/npu-reset-control/native-replay
```

The second command checks the retained canonical target objects and receipt.
It does not silently substitute the first command's newly compiled objects.
The canonical successful build directory is
`.local/npu-reset-control/verified-three/`; earlier failed scratch attempts are
not acceptance evidence. The kernel/source authority and build configuration
are hash-checked before/after the successful source/host/build run.
