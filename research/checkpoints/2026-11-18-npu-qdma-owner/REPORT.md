# Retain exposed Ethernet QDMA backing

The retained Linux Ethernet module's timeout still reaches forced TX
cleanup. The [maintainer's stop change](https://lists.openwall.net/netdev/2026/06/11/506)
describes that busy poll as a wait for in-flight host TX/RX work. It is
not a proof of forwarding or full-device retirement.
[Pinned baseline binary observations](../2026-11-18-npu-ppe-stop/REPORT.md).

The driver publishes RX descriptors, TX descriptors, the TX interrupt
ring, and two forwarding bases during probe. A later probe failure can
therefore precede the first netdev open and still follow publication.
The current W1700K DTS reserves the forwarding payload areas; the driver
can otherwise allocate them dynamically. RX pages and TX streaming
mappings have their own lifetime in addition to the coherent rings.

## Candidate Behavior

- The [late Linux patch](airoha-qdma-owner.patch) reserves the W1700K
  front-end owner, device and module before hardware setup. It requires
  direct DMA and rejects a separate device coherent allocation pool.
- On full detach or failed probe, an exposed engine keeps its coherent
  tables, descriptor entries, RX pools and outstanding TX mappings.
  An unexposed engine's allocations can still unwind. The patch masks
  and joins registered IRQs and detaches NAPI; no full-resource release
  is authorized by the host idle bits.
- Ordinary last-user close still admits scoped TX cleanup if enable
  and busy bits are clear and the initialized writeback bit is present.
  A timeout parks that engine. Open, TX and migration reject a parked
  engine, without parking the other engine.
- Close and migration disarm BQL for the affected netdev before
  resetting the counters. They scrub CPU packet metadata without
  unmapping or freeing outstanding data. The W1700K checked branch
  ensures it owns each affected skb header before enqueue.

The retained module and board owner cannot be reused after publication
and unbind. There is no post-exposure reclamation path in this candidate;
do not force unload. Normal runtime, probe-failure and cold-restart
behavior still need qualification on a board. The staged hold is not
an Ethernet forwarding, PPE, WLAN, NPU, or interconnect drain witness.

## Offline Verification

Twelve source contracts cover all five address sites and the callers of
the stop, reuse and detach paths. Eleven compiled synthetic cases and
seven negative controls tested the actual extracted driver functions.
Three AArch64 files built and linked into a relocatable Ethernet object
with the pinned toolchain; no modpost or production `.ko` ran. These are
not concurrency, timing, network, or board results. The patch applied
at zero fuzz and passed strict checkpatch; 27 nearby unit tests passed.
[Exact receipts](EVIDENCE.json).

```sh
python3 -B tests/npu/verify_qdma_owner.py --check --cross
```

## Combined Handoff

`coherent-ppe-qdma-a` applies this patch to the two pinned PPE postimages.
It retains the existing pool binding, provider, board DTS and mt76 delta.
The standalone DTB is unchanged from the prior coherent bundle.
The original source lock and both older receipts remain unchanged.
[Bundle pins](BUNDLE.json).

```sh
python3 -B tools/stage_npu_coherent_handoff.py --check coherent-ppe-qdma-a \
  --qdma-owner \
  --producer .local/npu-build-scratch/native-c2/fw-txp-20261118-modules-a/modules/result.json \
  --producer-sha256 b5af9591d0f6116547a08749fe733a98ac4d89b6088f8d1465950b052e4f69bd
```

Seal the independent frozen baseline first. Then build and bind the exact
new `airoha-eth.ko` from the selected FIT alongside the NPU and mt76
modules, verify normal open/close and shared-port migration, and separately
qualify physical retirement. No router was contacted, flashed or loaded.
