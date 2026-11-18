# Separate PPE shutdown from DMA retirement

**The PPE deinit reply is not a drain result.** The checked Ethernet
module also discards the provider reply. Separately, the Ethernet
QDMA busy-timeout edge reaches TX cleanup. Neither observation
authorizes releasing shared NPU, PPE, or Wi-Fi backing.

## Firmware Route

The [upstream PPE/NPU integration](https://lists.openwall.net/netdev/2025/02/07/372)
uses the NPU to configure PPE. The locked local provider sends group 5,
SET type 1 and deinit selector 2. In the pinned initialized DATA the
selector's slot at `0x3e900134` points to `0x84005eae`. The
handler calls `0x84008c94` and unconditionally returns 1 after that call.
The helper changes configuration for the PPE blocks; it does not
return a drain status. Its two direct callees and both containing
functions have no polling cycle or unresolved call in the decoded graph
(466 reachable instructions total).

These slices, the mailbox ISR and the dispatcher are byte-identical
between pristine CODE and the exact active replay pair. The DATA table
matches too. The replay does change one registration call: its hook
tail-calls the original routine with the original continuation
`0x84003f32`. The later PPE dispatcher store is unchanged. This checks
the initial bytes and static control flow; it does not attest a
live board's dispatch table, register timing, or execution of deinit.

## Host Route

In the retained prepared Ethernet module `dc9e5cdc`, the indirect
deinit call at `0xc368` is immediately followed by overwriting its
return register and calling `airoha_npu_put`. Pointer removal and the
RCU join synchronize CPU readers. They do not report which PPE engines
are idle. The FOE and stats backing are managed by the Ethernet driver;
the staged NPU coherent pool is not their owner.

The same module disables Ethernet QDMA, polls TX/RX busy with mask
`0xa`, and on timeout logs a warning. The linked timeout edge branches
back into the normal TX cleanup loop, whose callee can unmap queued TX
mappings. That stop logic is scoped to Ethernet QDMA, even on a
successful poll. It is not a fence for PPE, WLAN, or firmware.

Keep PPE table ownership and Ethernet QDMA queue ownership as distinct
requirements. A repair must carry the status to the release decision
and preserve the backing on uncertain completion, including device
removal. Do not route either status to the shared barrier as a
whole-graph drain witness. No driver, firmware or image was changed here.

```sh
python3 -B tests/npu/verify_ppe_stop.py \
  --check research/checkpoints/2026-11-18-npu-ppe-stop/EVIDENCE.json
```

[Exact inputs and decoded scopes](EVIDENCE.json).
All 74 focused host regressions passed.
The [original replay observation](REPLAY-LIVE.json) had 5,848 positive
profile 2 records, 345 matching inputs and no terminal verdict.
