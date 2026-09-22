# V2 Control Identity And Provider Transport

Started 2026-09-14; completed software verification 2026-09-16.
Status: **unpromoted candidate**, not complete NPU boot, safe recovery or a
tested firmware image. Full NPU reverse engineering/implementation remains open.

## Changes

- `firmware/npu/control-v2.c/.h` and `control-v2-client.c` add an 80-byte V2
  envelope around the existing admission/barrier and host epoch/mask checks.
  Wire sequence and boot identity are validated; STATUS requires an actual
  session binding. A failed BIND consumes its sequence so replay cannot make
  that abandoned request effective later. V1 remains unchanged.
- Candidate patch `928-net-airoha-npu-bidirectional-control.patch` adds exported
  `airoha_npu_wlan_control()` and a disabled-NPU stub without changing public
  device/ops layout. The function restricts input to an 80-byte NQC2 prefix and
  transfers the entire request/reply through the existing coherent bounce
  buffer. Legacy GET is left unchanged: its zeroed request body cannot carry
  this protocol's outbound identity data.
- Capabilities remain non-destructive: `0x27` contains request identity but no
  SAFE_RECLAIM or RESTART. All-worker software PARKED is not drain authority.

## Verification

| Check | Result |
| --- | --- |
| x86/AArch64 host comparisons | 830; full state/wire and stack/callee-saved checks |
| x86/RV32 server comparisons | 254; reply, session, admission and barrier state match |
| Protocol scenarios | 21 |
| Malformed/boundary cases | 51 |
| Identity-check mutants | 6 detected |
| Shared RV32 worker contexts | 8, with 11 strict-mailbox round trips |
| Provider ASan/UBSan | 290 assertions |
| Bidirectional provider exchanges | 8 |
| Register-error/timeout models | 8 / 2 |
| AArch64 kernel-context objects | 6; public layout unchanged before/after |
| Strict checkpatch | 0 errors, 0 warnings, 0 checks |
| Clang static analysis | No diagnostics |

The protocol tests reject stale same-epoch wire replies supplied with a new
local ticket, new-boot replacement providers, unbound same-identity replacements,
duplicate/reordered sequences and abandoned BUSY BIND replay. Partial-release
STOP and exhaustion are covered. The original firmware executes the 80-byte
probe and returns mailbox success with zero reply magic, which the host rejects.
Closed/open V1 endpoints also reject it without barrier changes.

Eight saved cold worker/coordinator contexts execute actual instruction paths
and report mask 0xff for epoch 1 with no physical drains. These are worker entry
and IRQ/mailbox adapters, not full reset-to-postgate boot. Helper returns, MMIO,
interrupt invocation, coherent memory and scheduling remain modeled.

The provider harness executes the actual pinned send/GET functions and candidate
control function against actual V2 client/server C. It validates complete request
body publication, full reply copy, prefix/length/null guards, write-error models,
pending-buffer retention and ignored late completion after host failure. This
does not prove real device DONE, cache ordering or provider removal safety.

The provider/header baseline matches the prior memory-preflight receipt:

- Provider SHA256: `8eed02dd963c9d80fcaf4f15368506f4a4720dd7be4f080c394a21bba7e1fe8f`.
- Public header SHA256: `9359009a4161de572e7f44b41b172860bb6414b56332f16ed6ff8df972126364`.

The generated patch applies without fuzz or offsets to an isolated copy.
Kernel builds use the existing 6.18.44 configuration/toolchain without modifying
the shared provider/header, source lock or packaged overlay. Before/after NPU
enabled/disabled header probes confirm identical public layout. These are
objects, not linked/load-tested modules. Preliminary enum-extraction,
disabled-layout and stub-alignment harness/build issues were corrected.

The complete unchanged V1 suite was also replayed successfully, including its
6,443 host comparisons and original limitation controls. Its receipt remains
`2ff80b32d1615a14c11e1aa82dd399041471752604dee74e4de85e2780250327`.

## Limits And Next Gates

The real loader must generate/publish a fresh boot identity and reserve the
session storage before releasing users. The current seed and addresses are
test fixtures. A deliberately reused identity plus replayed old BIND is still
accepted by a replacement coordinator; both violations remain a negative
control. Neither boot IDs nor host nonces authenticate an untrusted peer.

The existing `npu_bootstrap_transport()` admits only 12/64-byte requests. The
complete cold-bootstrap route therefore does not yet admit this 80-byte V2
frame. The standalone V2 mailbox tests do not close that integration gap or
compose the endpoint with every later retained firmware detour.

There is no mt76 recovery binding yet. Exact provider/transfer ownership,
callback lifetime, shared-provider coordination, full native postgate boot,
physical DMA/FIFO/cache/PMA drains, ownership-safe cleanup/rearm and hardware
acceptance remain open. The L1 candidate's successful legacy STOP remains
insufficient. See `firmware/npu/CONTROL_V2_CONTRACT.md` for caller obligations.

No packaged image, router, Wi-Fi, physical test, subagent, protected-data or
restricted-selector change. Only selector-15 control requests were submitted;
no INODE-framing correction or native DESC5/6/7/8 case was attempted.

## Replay

From `/home/captain/W1700KNPU` in WSL:

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_control_v2.py
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/build_control_v2_provider.py
```

Generated binaries, mutant sources and prepared kernel copies remain under
ignored `.local/npu-control-v2/`. Raw proprietary inputs remain in their
existing private directory. The checkpoint contains source, patch, logs and
receipts, not a deployable blob.

- `control-v2.json` SHA256: `43e189ee4bcc1c00f703311d876423e4f63d9b181970f3535a7255f81ae90aca`.
- `control-v2-provider.json` SHA256: `3f6d83ed12876dabef826361bd6257cbb707ca6ba9cd1c00e3a2b308d3e4d6c8`.
