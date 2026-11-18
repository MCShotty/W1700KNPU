"""Saved-buffer diagnostics only; these fixtures never communicate with a device."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import inspect_rro_release as wire


STOCK = bytes.fromhex('00000000 0600 0800 2301 0000')
MT76 = bytes.fromhex('00000000 0600 0a00 2301 00000000')


def tx_fixture(body=MT76, seq=3):
    size = 48 + len(body)
    tx = bytearray(size)
    struct.pack_into('<II', tx, 0, 0x41000000 | size, 0x4000)
    struct.pack_into('<HH', tx, 32, size-32, 0x57)
    tx[37], tx[39], tx[43] = 0xa0, seq, 7
    tx[48:] = body
    return tx


def rx_fixture(seq=3, status=0):
    rx = bytearray(52)
    struct.pack_into('<I', rx, 0, 0x38000034)
    struct.pack_into('<HH', rx, 32, 20, 0xe000)
    rx[36:39] = bytes([1, seq, 2])
    struct.pack_into('<H2xI', rx, 44, 0x57, status)
    return rx


class ReleaseWireTests(unittest.TestCase):
    def test_known_layouts_share_id_not_declared_length(self):
        rows = [wire.decode_body(b) for b in (STOCK, MT76)]
        self.assertEqual([(r['profile'], r['session_id'], r['tlv_bytes']) for r in rows],
                         [('stock-12', 0x123, 8), ('mt76-14', 0x123, 10)])
        self.assertNotEqual(rows[0]['sha256'], rows[1]['sha256'])

    def test_does_not_normalize_one_shape_to_the_other(self):
        for buf in (STOCK+bytes(2), MT76[:-2], MT76+bytes(2), STOCK[:-1], STOCK+MT76):
            with self.subTest(buf=buf), self.assertRaises(ValueError):
                wire.decode_body(buf)

    def test_requires_the_recognized_tag_and_zero_reservations(self):
        for original in (STOCK, MT76):
            for idx in (0, 3, 4, 5, 6, 7, *range(10, len(original))):
                changed = bytearray(original)
                changed[idx] ^= 1
                with self.subTest(length=len(original), idx=idx), self.assertRaises(ValueError):
                    wire.decode_body(changed)

    def test_observes_ids_outside_the_owned_pool_without_accepting_them_as_owners(self):
        for seid in (0, 1023, 1024, 1025, 65535):
            buf = bytearray(MT76)
            struct.pack_into('<H', buf, 8, seid)
            row = wire.decode_body(buf)
            self.assertEqual(row['session_id'], seid)
            self.assertEqual(row['in_owned_id_range'], seid <= 1024)

    def test_tx_frame_binds_sequence_command_and_actual_payload(self):
        for body, expected in ((STOCK, 'stock-12'), (MT76, 'mt76-14')):
            tx = tx_fixture(body, seq=15)
            r = wire.decode_request(tx)
            self.assertEqual((r['cid'], r['sequence'], r['body']['profile']), (0x57, 15, expected))
            self.assertEqual(r['tx_sha256'], hashlib.sha256(tx).hexdigest())

    def test_unsupported_descriptor_command_route_or_fragment(self):
        for off, value in ((0, 63), (3, 0), (5, 0), (32, 28), (34, 0x56), (37, 0),
                           (38, 1), (39, 0), (39, 16), (42, 2), (43, 2), (43, 6)):
            tx = tx_fixture()
            tx[off] = value
            with self.subTest(off=off, value=value), self.assertRaises(ValueError):
                wire.decode_request(tx)

    def test_outer_and_inner_len_are_independent(self):
        for tx in (tx_fixture()[:-1], tx_fixture()+bytes(1), tx_fixture(MT76[:-2])):
            with self.assertRaises(ValueError):
                wire.decode_request(tx)

    def test_result_reports_status_even_when_not_successful(self):
        request = wire.decode_request(tx_fixture())
        for status in (0, 1, 0x01020304, 0xffffffff):
            rx = rx_fixture(status=status)
            r = wire.match_result(request, rx)
            self.assertEqual(r['status'], status)
            self.assertIs(r['status_zero'], status == 0)
            self.assertEqual(r['rx_sha256'], hashlib.sha256(rx).hexdigest())
            self.assertFalse(any(r[k] for k in ('ba_session_echoed','generation_authenticated','dma_drain_proven')))

    def test_unified_result_must_be_solicited_for_that_sequence_and_command(self):
        request = wire.decode_request(tx_fixture())
        for off, value in ((36, 2), (37, 0), (37, 4), (38, 0), (38, 6), (40, 0x13), (44, 0x58), (45, 1)):
            rx = rx_fixture()
            rx[off] = value
            with self.subTest(off=off, value=value), self.assertRaises(ValueError):
                wire.match_result(request, rx)

    def test_rx_event_not_data_redirect_or_truncated_capture(self):
        request = wire.decode_request(tx_fixture())
        for word in (0x38000033, 0x38010034, 0x10000034):
            rx = rx_fixture()
            struct.pack_into('<I', rx, 0, word)
            with self.assertRaises(ValueError):
                wire.match_result(request, rx)
        for rx in (rx_fixture()[:-1], rx_fixture()+b'\0'):
            with self.assertRaises(ValueError):
                wire.match_result(request, rx)

    def test_cookie_is_not_inferred_from_a_wrapped_sequence(self):
        other = bytearray(MT76)
        struct.pack_into('<H', other, 8, 7)
        for data in (MT76, other):
            row = wire.match_result(wire.decode_request(tx_fixture(data)), rx_fixture())
            self.assertEqual(row['match'], 'sequence-and-command-only')
            self.assertFalse(row['transaction_identity_proven'])
            self.assertNotIn('session_id', row)

    def test_uninterpreted_rx_metadata_is_reported_as_raw_fields(self):
        rx = rx_fixture()
        rx[32:36] = bytes.fromhex('14001122')
        rx[43] = 0x12
        r = wire.match_result(wire.decode_request(tx_fixture()), rx)
        self.assertEqual((r['rx_header_length_field'], r['rx_header_packet_type'], r['rx_header_direction']),
                         (20, 0x2211, 0x12))

    def test_capture_files_are_bounded_and_inputs_stay_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'record'
            for data in (b'', bytes(15)):
                p.write_bytes(data)
                with self.assertRaises(ValueError):
                    wire.capture_bytes(p, 14)
            p.write_bytes(MT76)
            self.assertEqual(wire.capture_bytes(p, 14), p.read_bytes())
            if hasattr(os, 'mkfifo'):
                fifo = p.with_name('pipe')
                os.mkfifo(fifo)
                with self.assertRaises(ValueError):
                    wire.capture_bytes(fifo, 14)

    def test_cli_modes_and_evidence_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            for name, data in [('b', STOCK), ('t', tx_fixture()), ('r', rx_fixture())]:
                (d/name).write_bytes(data)
            def run(*args):
                return subprocess.run([sys.executable,'-B',wire.__file__,*args], cwd=d, capture_output=True, text=True)
            for args, key in [(('--body','b'), 'body'), (('--tx','t'), 'request'), (('--tx','t','--rx','r'), 'result')]:
                done = run(*args)
                self.assertEqual(done.returncode, 0, done.stderr)
                result = json.loads(done.stdout)
                self.assertIn(key, result)
                self.assertFalse(result['capture_provenance_verified'] or result['hardware_verified'])
            for args in (('--body','b','--rx','r'), ('--rx','r'), ('--tx','b'), ('--tx','t','--body','b')):
                self.assertEqual(run(*args).returncode, 2)
            self.assertEqual({p.name for p in d.iterdir()}, {'b', 'r', 't'})


if __name__ == '__main__':
    unittest.main()
