# Host Generation-Control Client

Date: 2026-09-14. Status: **unpromoted software component**, not safe active-NPU
recovery, a Linux provider integration, or a tested firmware image.

## Change

`firmware/npu/control-client.c/.h` implements the host half of the existing
64-byte V1 admission protocol. It emits DISCOVER/BIND/STOP/STATUS, validates
structured replies independently of mailbox success, and tracks the exact stop
epoch. A single outstanding local ticket correlates completions. Failures,
generation/ticket exhaustion and explicit abort are terminal; late replies
cannot reopen the client. Requests/replies use an explicit little-endian byte
codec without assuming local buffer alignment.

The only positive endpoint is software `PARKED`. No function frees resources,
claims hardware drains or restarts engines. Capabilities other than the reviewed
value 0x07 are rejected, including claims of SAFE_RECLAIM/RESTART. The existing
firmware ABI, barrier/admission implementation and packaged host sources were
not changed.

## Verification

| Evidence | Result |
| --- | --- |
| Actual x86/AArch64 client comparisons | 6,443 calls; state, wire, stack and callee-saved registers match |
| Mask snapshots | 544 cases, including all 256 masks in cold/running histories and all 32 drain masks |
| Malformed replies | 58 cases |
| Transport failures | 25 cases across client phases |
| Ordering/boundary/abort checks | 19 / 24 / 10 cases |
| Actual host/RV32 round trips | 11, with eight serialized saved worker/coordinator contexts |
| Additional firmware scenarios | 12 |
| Check-removal mutants | 10 detected |
| ASan/UBSan | 259 boundary cases and four native C round trips |
| Clang static analysis | No diagnostics |

The RV32 path uses the existing strict mailbox adapter and original IRQ/worker
instructions. It sees all eight epoch-2 worker bits grow to 0xff while physical
drain bits remain zero and firmware reclamation remains false. Other scenarios
execute actual barrier C at modeled worker boundaries, and explicitly model
drain witnesses when testing full diagnostic masks. They do not prove drains.

Original firmware discovery returns mailbox flags 7 but zero reply magic; the
client rejects it. Remote faults, conflicting session, active-handler BUSY,
external generation change and STOP delivered before/after host timeout are
also covered. Only selector-15 control requests are submitted; no restricted
INODE-framing or DESC5/6/7/8 operation is executed. Ten check-removal mutants
are independently detected. A preliminary released-state mutant exercised a
redundant STATUS check; its probe was corrected to test STOP directly.

## Limits That Remain Demonstrated

- Old same-epoch STATUS bytes supplied with a new local completion ticket are
  accepted even if the actual firmware has since faulted. V1 has no per-request
  wire sequence. Local tickets require exact transport ownership; they cannot
  authenticate the freshness of returned bytes.
- STATUS echoes the request nonce without checking the bound session. A new
  coordinator at the same epoch can therefore answer an old client's STATUS.
  Exact provider lifetime/incarnation and callback ownership remain necessary.
- These are deliberate model controls, not observations of a Linux provider
  fault. They are retained as explicit reasons not to use this component as a
  destructive recovery permit.
- MMIO/interrupt invocation, helper returns, initial running-state platform
  witnesses, coherent storage and scheduling remain modeled. Full native boot,
  concurrent harts, actual DMA/cache/PMA and physical containment are unproved.
- The helper does not allocate/pin/publish/retire mailbox buffers or synchronize
  callbacks. Timeout and abort do not retire storage or cancel firmware work.
- There is no Linux provider/mt76 binding. The prior L1 candidate still lacks a
  real drain witness on successful legacy STOP, and full reset/removal/rearm
  remain open. No hardware test or image was produced.

Caller requirements and API details are in
`firmware/npu/CONTROL_CLIENT_CONTRACT.md`.

## Replay

From the canonical WSL repository:

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_control_client.py
```

Generated native/AArch64/RV32 binaries, sanitizer artifacts and mutants stay in
ignored `.local/` directories. Proprietary inputs remain local and SHA-checked.
The receipt binds the sources, test harnesses, packaged-source fingerprints,
compiler, emulator version and generated binaries:

`control-client.json` SHA256:
`2ff80b32d1615a14c11e1aa82dd399041471752604dee74e4de85e2780250327`.

The final complete replay reproduced this receipt byte-for-byte. An independent
readback verified all 30 recorded inputs, ten mutant sources and 24 binaries.
Scoped whitespace checks pass. A repository-wide whitespace check also found
pre-existing formatting in unrelated cumulative patches; those were untouched.

No source-lock/overlay/package, router, Wi-Fi, subagent, protected-data or
restricted-operation change. Existing unrelated worktree changes are retained.
