#!/usr/bin/env python3
"""Inspect saved W1700K RRO table-release bytes. No capture, transmission or device access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct

RRO_CID = 0x57
RELEASE_TAG = 6
TX_HEADER = struct.Struct('<32xHHxBBB2xBB4x')
RX_HEADER = struct.Struct('<32xHHBBBxB2xB')
UNI_RESULT = struct.Struct('<H2xI')
BODY_PROFILES = {12: 'stock-12', 14: 'mt76-14'}


def decode_body(data):
    if len(data) not in BODY_PROFILES:
        raise ValueError('Expected one 12- or 14-byte release body without transport padding')
    tag, length, session_id = struct.unpack_from('<HHH', data, 4)
    if tag != RELEASE_TAG or length != len(data) - 4:
        raise ValueError('Not a complete RRO release TLV of the declared size')
    if any(data[:4]) or any(data[10:]):
        raise ValueError('Reserved bytes differ from both verified host encodings')
    return dict(profile=BODY_PROFILES[len(data)], body_bytes=len(data), tag=tag,
                tlv_bytes=length, session_id=session_id, in_owned_id_range=session_id <= 1024,
                sha256=hashlib.sha256(data).hexdigest())


def decode_request(tx):
    if len(tx) not in (60, 62):
        raise ValueError('Expected an entire 48-byte mt76 MCU TX descriptor followed by one release body')
    word0, word1 = struct.unpack_from('<II', tx)
    if word0 != (0x41000000 | len(tx)) or word1 != 0x4000:
        raise ValueError('Not the command descriptor written by the mt7996 sender')
    length, cid, pkt, frag, seq, dest, option = TX_HEADER.unpack_from(tx)
    if (length, cid, pkt, frag, dest, option) != (len(tx) - 32, RRO_CID, 0xa0, 0, 0, 7):
        raise ValueError('Expected one acknowledged unified WM RRO SET command')
    if not 1 <= seq <= 15:
        raise ValueError('Not an allocated mt7996 command sequence')
    return dict(body=decode_body(tx[TX_HEADER.size:]), cid=cid, sequence=seq,
                tx_sha256=hashlib.sha256(tx).hexdigest())


def match_result(request, rx):
    """Match host-observable fields only. Sequence numbers wrap; no BA identity is echoed."""
    if len(rx) != RX_HEADER.size + UNI_RESULT.size:
        raise ValueError('Expected one complete 44-byte mt7996 RX descriptor and 8-byte unified result')
    word0, = struct.unpack_from('<I', rx)
    sw_type = word0 >> 16
    if word0 >> 27 != 7 or (sw_type & 0x380f) == 0x3801 or (word0 & 0xffff) != len(rx):
        raise ValueError('Not a complete RX event at the mt7996 queue boundary')
    length, pkt, eid, seq, option, ext, direction = RX_HEADER.unpack_from(rx)
    if not option & 2 or option & 4 or eid != 1 or ext == 0x13 or seq != request['sequence']:
        raise ValueError('Not a matching solicited unified command result')
    cid, status = UNI_RESULT.unpack_from(rx, RX_HEADER.size)
    if cid != request['cid']:
        raise ValueError('Unified result is for a different command')
    # RX length/type/direction inside the MCU header are reported literally;
    # the source parser uses the sequence, option, event ID, CID and status.
    return dict(cid=cid, sequence=seq, status=status, status_zero=status == 0,
                rx_header_length_field=length, rx_header_packet_type=pkt, rx_header_direction=direction,
                rx_sha256=hashlib.sha256(rx).hexdigest(), match='sequence-and-command-only',
                transaction_identity_proven=False, ba_session_echoed=False, generation_authenticated=False,
                dma_drain_proven=False)


def capture_bytes(path, maximum):
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f'Expected a regular capture file: {path}')
    with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) |
                           getattr(os, 'O_BINARY', 0)), 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not os.path.samestat(before, info) or not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= maximum:
            raise ValueError(f'Expected a bounded regular capture file: {path}')
        data = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        if len(data) != info.st_size or (after.st_size, after.st_mtime_ns) != (info.st_size, info.st_mtime_ns):
            raise ValueError(f'Capture changed during inspection: {path}')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--body', type=Path, help='One release body at the command append/send API')
    group.add_argument('--tx', type=Path, help='One complete mt7996 command SKB, including its TX descriptor')
    parser.add_argument('--rx', type=Path, help='One complete result SKB, including its RX descriptor; requires --tx')
    args = parser.parse_args()
    if args.rx and not args.tx:
        parser.error('--rx requires --tx; a body has no transport sequence')
    try:
        if args.body:
            out = dict(body=decode_body(capture_bytes(args.body, 14)))
        else:
            out = dict(request=decode_request(capture_bytes(args.tx, 62)))
            if args.rx:
                out['result'] = match_result(out['request'], capture_bytes(args.rx, 52))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    out.update(capture_provenance_verified=False, hardware_verified=False)
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
