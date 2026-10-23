# Typed Retained RRO Reset Integration

Classification: progress toward full NPU reverse engineering/implementation,
not operational or physical acceptance. The previous target checkpoint's broad
caller pass belongs to older source, not the current typed callback cohort.

## Implementation

The retained worker now invokes dedicated process-context NPU-reset, MCU-begin
and MCU-complete bridges instead of legacy selector3. The provider queues a
nonzero journal ticket before transport, records possible NPU exposure, exchanges
the exact session/reset-generation/ticket and records the raw result. Duplicates
return the same ticket without retransmission. The existing TX serial-chain and
provider/endpoint/backing identity checks remain in force.

MCU begin updates the host/native journals before the physical command boundary.
The worker rechecks close after that potentially sleeping bridge and admits no
new physical call on error or close. The physical MCU return and typed-completion
return are retained separately. An exact late MCU result can update host metadata
after close without a new RPC, CPU join, free, rearm or cleared sticky error.

The current consumer owner remains one-shot per session ID. It uses initial
journal generation1, not an inferred firmware BA epoch; acknowledged reuse is
still denied. Provider APIs accept explicit caller generations, independently
tested across two generations. Legacy selector3 remains denied. The existing
parked-only client/broker guards are unchanged: hot typed reset is still open.

## Executed Evidence

- Candidate selected worker C:22 host scenarios/eight compiled intended-assertion
  controls, including all1025 IDs, NPU/MCU/bridge errors, duplicates, close during
  NPU/begin/MCU and constructor/event handoff. Lock/device/module/transport/MCU
  boundaries are models, not kernel concurrency or physical firmware proof.
- Actual provider/mt76 bridge/client/codec/broker/journal/native C:6150 complete
  reset transactions across three profiles/two generations,12 negative cases
  and three compiled controls. Full journals, all retained DMA/SRAM array bytes,
  exact signature-only access/readback and original TX serial-chain checks pass.
  MCU responses, backing, transport and CPU exclusion remain modeled boundaries.
- Both authority patches reconstruct at fuzz0:5 kernel and15 mt76 outputs,
  with31 component mappings. New source lock4f862e1a. The pre-edit check caught
  a fixture belonging to the live replay; it remains unchanged and is included
  by a new separately named fixture, not edited in place.
- All four current AArch64 modules link with GCC14.4.0/Linux6.18.52; three typed
  reset import/export edges resolve. Producer22b9827e binds5 kernel/330 mt76
  sources/31 mappings. Original kernel/mt76 inventories remain unchanged.
  Private incremental build236MiB; output267096480 bytes. No module load.
- Installed-source worker22/eight controls, BA15/three and the same complete
  joint reset matrix pass. All142 units pass, zero skips. Broader456 allocation/
  fault and1090 caller refreshes remain pending for this producer; a400MiB
  launch was refused by full-cap RAM preflight, not a test pass.

Retained failures include a pre-edit native-graph overlap refusal, a400MiB
preflight RAM refusal, an oracle intermediate-pointer UBSan failure and an
ambiguous mutation anchor. The corrected oracle still checks all bytes; the
control now selects the exact complete production function before mutation.
No sanitizer, geometry, replay bound/cap or2GiB margin was relaxed.

## BA Review And Remaining Work

The closed Luna/max read-only reviewer and main-agent source check confirm that
status events bind the currently looked-up WCID/TID object and carry no BA cookie.
The current handler also ignores its status field. Retained stock/V6.24 evidence
requires status-0-only publication and describes status-3 retry; cached-pointer
retry was deliberately omitted because RX-TID lifetime was unproven. This is a
concrete next parity hook, not evidence of an authenticated BA reuse fence.

Still create the real BA lifetime at RX-TID creation, preserve primary/active-link
mapping and late events, qualify reuse/cookie ordering, implement hot admission
and production retirement/rearm, and establish independent physical drain.
Both full replay cohorts remain live and untouched; partial traces are not full
verdicts. Full current image/cold-fault-HIF2/hardware/client/performance/stability
acceptance remains required. No module load, image promotion, hardware access or
VM/global-policy change occurs here. The complete NPU objective remains active.
