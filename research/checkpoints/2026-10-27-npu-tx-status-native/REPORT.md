# Compiled MT7996 TXS And Packet-Status Ownership

## Qualified Result

Final replay-q6 of `test_tx_status_kernel_native.py` passes 64 distinct cases
and nine emulator-byte controls, with 34 current input bindings. It executes the
real retained MT7996 TXS parser, core status registration/retirement and 23 linked-
kernel-matched Linux 6.18.52 IDR/radix routines. All 23 kernel bodies enter.
Overall, 35 bodies enter and 38 map. The ordinary connac completion callback,
put_txwi.part.0 and legacy mt76_get_rate bodies do not enter this suite.

This is compiled-body execution in emulation, not a running Linux kernel or
physical acceptance. The module producer is still pre-FW-high-DMA-fix `92c75156`.
All 417 producer inputs verify with the three preserved old source-lock, patch
and mac.c aliases. Current lock `cc128c3b` and its FW-TXP source fix remain target-
compile/execution pending. FW fixtures use low addresses; MAC fixtures include
high address bits. This does not qualify the pending FW decoder fix.

Final result SHA256:
`c18140a1e858153d6470a5bac6effe13a3127b3bf95e3c61fb5be29ab4e089f7`.
Status-test source SHA256:
`b4a3327e2ffa8a76fd752befb0a0dfcf13b751202037e39c0b40c831ef7a3aa6`.
Shared-loader source SHA256:
`380726ac5ae51a13868347906d83f51d82733660e63fddc807538ceaff9bd636`.
Private evidence: `.local/npu-tx-status-native-20261027/`.

## Executed Ownership Matrix

Compiled `mt76_tx_status_skb_add` allocates packet IDs through the actual kernel
IDR code and links the WCID onto the status list. Compiled allocation/tree logic
and node constructors execute; the slab-memory backend supplies fixture buffers.
No Python implementation supplies IDR lookup, insertion, removal or destruction.
The TX token IDR is also populated through compiled kernel allocation routines.

Six orderings cover DMA then TXS, TXS then DMA, DMA then forced flush, forced flush
then DMA, DMA then expiry, and an expiry check while DMA is still outstanding.
Counts 1/3, FW/MAC formats and PHY presence vary; six dense 64-SKB cases cross
packet-IDR leaf boundaries. Four allocation-failure cases exercise compiled
no-SKB-status fallback. Two cases cross 64-bit jiffies wrap and four exercise ACK
timeout results. The total remains 64 cases, not a sum of earlier attempts.

For successfully registered status packets, DMA first leaves the packet-status
IDR holding the pending SKB after token zero/cache transfer. With TXS or forced
flush first, that IDR empties but the TXWI
retains the SKB until DMA completion. Neither first event alone may produce a
modeled mac80211 completion. Both orders must finish each SKB exactly once.
Allocation-failure fallback has no packet-status owner and completes at DMA.

The expiry path checks one jiffy before and exactly at the compiled 25-jiffy
boundary. It must not expire an SKB that has not reached DMA_DONE, even with an
advanced clock. Clock values and wrap arithmetic are fixture inputs, not a real
device timer witness. The simple non-AQL counter branch is also checked to zero;
station scheduling and complete non-AQL/PS behavior remain unexecuted.

## Actual TXS Parser

The final suite invokes compiled `mt7996_mac_add_txs` with raw HT MPDU TXS records.
That parser performs the PID/WCID checks, status locking, lookup/removal, ACK/rate
updates and completion handoff. Its locking is no longer injected by the fixture.
Reserved PID, out-of-range WCID and absent-WCID records must not enter status
lookup or alter ownership. Fresh unknown and duplicate TXS must not complete an
SKB twice. ACK-success and ACK-timeout records produce their expected flags.

The generic loader now accepts selected component paths/bases/roots, supports the
core jiffies reference, tracks writable ELF data and applies PREL32 switch-table
relocations. Code/data ranges remain bounded, with the return sentinel excluded.
The default kernel suite is independently requalified, not assumed compatible.

Across the 64 fixtures, 510 status registrations and 510 modeled mac80211
completions occur; 12 allocation requests fail as injected. There are 136 allocated
radix nodes, 136 compiled callback executions and 136 modeled slab returns. The
2,048 constructor entries include unused fixture-pool buffers and are not 2,048
live allocations. These are test-fixture counts, not physical packet counts.

## Limits And Controls

Device/WCID/SKB initial memory and RX record delivery are supplied by the fixture.
No RX interrupt/NAPI packet-delivery path or hardware traffic is executed. Initial
empty IDR/list setup is supplied, while subsequent tree allocation, traversal,
deletion and destruction execute compiled code. Slab memory, RCU grace scheduling,
mac80211 effects and DMA effects remain modeled. Compiled callbacks run only after
a declared modeled grace point; this is not real Linux SMP or RCU scheduling proof.
Station/PS, legacy rate paths, complete capacity pressure, consumer/devres/context,
RRO, physical containment/drain, reuse/hot and board/client gates remain open.

Nine controls omit registration, WCID linking, removal, TXS flag storage, DMA
completion, forced-flush selection, status return, WCID unlinking or RCU enqueue.
Each fails at its intended assertion. Only emulated instruction bytes change;
the retained modules and kernel objects do not. The final service ran 62.055
seconds, peaked at 105.9 MiB under a 192 MiB/no-swap cap, and retained the
120-second oneshot deadline, fresh dual margins and EROFS C-write control.
There was no compilation, C-output write, module load or hardware contact.

## Preserved History And Compatibility

Inspection-q2, helper probe-q3, helper-only replay-q4 and parser probe-q5 retain
their consumed sources. The successful 60-case helper stage modeled TXS entry/
locking and is superseded, not counted as extra parser acceptance. Its 32 inputs
verify with two consumed-source aliases. The final parser stage has no aliases
among its 34 current inputs.

The original published kernel-test source `83f0f8b2` is preserved read-only under
before-api-q1. Its old 30-input receipt verifies with that one source alias.
Current compat-q8 reexecutes the default 56 cases/seven controls with all 30
current inputs, without aliases; receipt SHA256 is
`aa8a5cb0affe13ef4442ebdb702af2805163741ef11aaf78f92c7e94185be42c`.
The preceding 62-case/nine-control token/callback suite and all 17 inputs remain
unchanged. Do not run historical current-file SHA assumptions against newer
canonical test sources or add repeated cases together.

## Original Replay And Queue

Original full-q16 invocation `20c8f1ab62d74236bf977c134d09b059` retains its exact
process chain and advancing CPU. Profile 0's verified final artifacts remain.
Snapshot-q8 captures profile 1 at 2874 positive RPCs, 129 publications and 868
RESET/MCU_BEGIN/MCU_COMPLETE each. This is not a finished profile or the complete
three-profile/19261-RPC verdict. No original job was restarted or limits changed.

Windows queue PID 17788/plan `e67d5198` remains live and waiting, with 454 target
inputs and 332 native/read-only retained inputs verified unchanged. No target
phase has started. These tests are outside both frozen sets and were not added
to the queue. Follow it without duplicating or changing bound inputs. After fresh
module/regression qualification, rerun the token, kernel and status suites against
matching new modules/source without the old mac.c alias.

Six old tracking bodies are byte-preserved. Ethernet remains disconnected. No
image/flash, Wi-Fi change, shutdown, compaction or subagent occurred. Full NPU
reverse engineering and implementation remains the active goal.
