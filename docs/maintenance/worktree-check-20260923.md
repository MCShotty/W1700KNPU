# Pre-Publication Worktree Check

Date: 2026-09-23. Canonical workspace: `/home/captain/W1700KNPU`.
Target: private GitHub repository `MCShotty/W1700KNPU`, branch `main`.
Local HEAD and the observed remote main both started at
`666b63245d3c13921cb4cdedeef4d7e3f418bd1e`.

## Scope

The check covers 387 existing changed/new text files: accumulated completed
NPU candidates, harnesses and checkpoint evidence, earlier Wi-Fi source exports
and test evidence, and tracking documents. This report is the additional
publication record. NPU candidates remain unpromoted; committing research does
not add them to the packaged source lock or establish hardware acceptance.

Two interrupted, unvalidated RX draft files are deliberately left untracked:

- `research/checkpoints/2026-09-16-npu-rx-ownership/mt76-npu-dequeue.c`
- `tests/npu/test_npu_rx_ownership.py`

The draft has no completed ownership harness or validation receipt. No draft
code was changed or presented as validated by this check. Ignored build/local
trees, private keys, device backups, calibration and recovery data are excluded.

## Checks

- Git connectivity check passed; the repository has one registered worktree.
- All 387 selected files decoded as UTF-8 text without embedded NUL bytes.
  No selected file is a symlink or a protected binary/archive/key file type.
- Parsing passed for 86 JSON files and 43 Python files. Shell syntax checks
  passed for six scripts, and Node syntax checks passed for two JS/CJS files.
- Private-key, recognizable service-token, credential-bearing URL and merge
  marker screening found no hits. Eleven broader credential-related matches
  were inspected: they are runtime variable references, UI/source identifiers,
  or explicitly synthetic test fixtures. This is scoped screening, not proof
  that arbitrary secrets can never occur in text.
- The existing isolated-index source-export verifier reproduced all 40 OpenWrt
  and three LuCI files recorded in `firmware/source-lock.json`.
- Hash readback matched 110 file references in the host-lifetime receipt,
  138 in the bootstrap-composition receipt and 85 in bootstrap-control-v2.
  These counts overlap across receipts; no missing or mismatched files occurred.
- Eight host-lifetime harness executables were rebuilt in a separate ignored
  directory with ASan/UBSan. Fresh execution passed 161 baseline/193 corrected
  provider cases, 24 RCU cases in each version, and four expected mutant
  rejections. Historical receipts and their original binaries were unchanged.
- Staged ordinary source passed `git diff --check` with CRLF handling enabled
  and preserved patches/checkpoint artifacts excluded. The unfiltered check
  flags patch context prefixes, CRLF evidence files, captured compiler-command
  trailing spaces and whitespace in a preserved predecessor fixture. Those
  artifacts were not reformatted; patch application and source hashes passed.
- Jev `jev-1.13.0` evaluated 15 NPU checkpoint reports with two independent
  Choice questions each. Every report was classified as software validation
  with explicit limits on hardware/lifecycle claims. This wording review is
  supporting evidence, not a substitute for tests or a correctness proof.

Local audit manifests, source-export results, fresh sanitizer results and raw
Jev probabilities are retained under `.local/worktree-publication-20260923/`.
No credentials are stored there. The Jev helper used the expressly approved
one-process execution-policy override; permanent Windows policy was unchanged.

No full firmware rebuild, new kernel-object build, device test, flashing,
deployment or restricted NPU operation was performed for this publication.
The existing source lock and historical engineering results retain their
documented limits. Remote publication is verified separately after the commit.
