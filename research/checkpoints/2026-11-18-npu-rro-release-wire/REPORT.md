# What the two RRO release senders actually send

The stock W1700K driver and the current Linux 6.18.52 radio module do not
encode the same Block Ack (BA) session-release request. This is **host binary
evidence**. It does not determine which requests the July WM firmware accepts.
The driver, WM image, source lock and frozen world inputs were not changed.
[Machine-readable evidence](EVIDENCE.json).

| At the command-body boundary | Stock mt_wifi | Qualified mt7996e |
| --- | ---: | ---: |
| Unified command ID | 0x57 | 0x57 |
| Release TLV tag | 6 | 6 |
| Body bytes / declared TLV bytes | **12 / 8** | **14 / 10** |
| Little-endian session ID offset / width | 8 / 2 | 8 / 2 |
| Zero bytes following the ID | 2 | 4 |

The four bytes before the TLV are zero in both. Changing only the trailing
padding would not make the encodings identical: their length fields differ.
The 395-byte current sender definition is byte-identical to the definition in
the [pinned upstream mt76 revision](https://github.com/openwrt/mt76/blob/01367e60db433534ad0aa3d3b6c886de8cb7d44c/mt7996/mcu.c#L5276-L5292).
This difference was not introduced by the local merge.

## Where the stock return value stops

The stock delete handler calls the address-element initializer and reaches
`RTMP_FREE_RRO_SETBL` on its release path. The latter passes hardware-control
group 0, command **0x55** and a two-byte session argument to `HwCtrlEnqueueCmd`
with its wait flag clear. On the successful enqueue path, after waking the
worker, this flag branches around `wait_for_completion_timeout`.

The worker looks up 24-byte records through `HwCmdTable`. Group 0, row 27
resolves via the `.data+0x193c0` relocation to the unnamed callback at
`.text+0x387784`. It reads the session ID, calls `uni_cmd_release_rro_setbl`,
then sets W0 to zero before returning. **The callback discards the sender's
return value.** The sender itself sets up generic response handlers and calls
the command transport. Neither the internal queue ID 0x55 nor its return is
the WM command ID 0x57 or a radio acknowledgment.

In the current owned path the linked worker calls the MCU sender between
the begin and complete helpers. The sender requests a response. The typed
result branch checks the sequence and command ID and reads a 32-bit status;
the generic parser also has a zero-return path outside the typed result case.
The typed result does not echo the session ID or a BA generation. A matching
result is not proof of physical DMA retirement or safe reuse of the ID.

## Reproduce offline

`tests/npu/verify_rro_release_senders.py` uses the stock ELF, the independently
pinned combined producer and its linked radio module. In the canonical WSL tree:

```sh
python3 -B tests/npu/verify_rro_release_senders.py \
  --module-receipt .local/npu-build-scratch/native-c2/fw-txp-20261118-modules-a/modules/result.json \
  --expected-producer-sha256 b5af9591d0f6116547a08749fe733a98ac4d89b6088f8d1465950b052e4f69bd
```

All 420 producer inputs and four linked modules verified. Whole function or
named-window hashes, AArch64 operands and relocation targets bind the result.
The recovered layouts were reconstructed for IDs 0 through 1024 under each
profile; these are **not** 2,050 executed firmware transactions. GNU objdump
and readelf independently confirmed the widths, dispatch and relocations. Six
negative controls rejected wrong inputs, sizes or bindings. Historical Ghidra
exports for the delete/queue path were rehashed from the verified split
archive; this was not a new Ghidra run.

`tools/inspect_rro_release.py` is a read-only decoder for already-saved bytes:

```sh
python3 tools/inspect_rro_release.py --body saved-request-body.bin
python3 tools/inspect_rro_release.py --tx saved-mt7996-tx-skb.bin --rx saved-mt7996-rx-skb.bin
```

The second form expects one unpadded, complete mt76 command SKB and one
complete solicited unified result SKB including their hardware descriptors.
It is not a stock transport-envelope or PCAP parser. The MCU RX header's
length, packet-type and direction fields are reported literally; the outer
frame length/type and solicited-result fields are checked. A matching
four-bit sequence and CID do not authenticate either capture, identify the
transaction across wrap, or prove a generation fence. Nonzero firmware status
is reported as data, not as a decode error. All 250 host tests (14 new decoder
methods) passed with no skips.

## Open evidence

The current WM carrier is `99020e57`, build `20260721003035`, with all nine
loader regions flagged encrypted. The retained March mapped image is a
different build. There was no matching July receiver execution or hardware
capture in this check. Keep the existing sender and one-shot ownership guard.
The next useful hardware evidence is a same-boot, firmware-identified request
and matching result with unambiguous capture order. Proving session reuse
would additionally require excluding delayed old events and proving drain.

The separate RV32 invocation `61e2d7b8` was still active with all 345 inputs
intact. Profile 0 was already verified; profile 1 had 471 positive records
at the saved observation, not a final verdict. No second replay, target build,
module load, flash or router contact occurred. Detailed local receipts:
`.local/npu-rro-release-wire-20261118/`.
