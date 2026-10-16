"""Read-only expected pointer/sequence projection, not native execution."""
from types import SimpleNamespace
from unittest.mock import Mock
import struct
import unittest

from rx_pcie_transaction_oracle import expected, SPACES


class PcieTransactionOracleTests(unittest.TestCase):
    def fixture(self, hif2=0):
        session, state = 0x3e906380, 0x84046000
        images = {address: bytearray(b'\xa5' * length) for address, length in SPACES}
        struct.pack_into('<5I', images[0x3e900000], session - 0x3e900000, 1, 2, 3, 4, 57)
        setup = [0] * 101
        setup[12:14] = [0x20000000, 0x100000]
        setup[95] = 2
        setup[97:99] = [0x200d4450 + hif2 * 0x4000] * 2
        setup = struct.pack('<101I', *setup)
        cpu = Mock()
        def read(address, length):
            if address == state:
                return setup[:length]
            region = next(base for base, data in images.items() if base <= address and address + length <= base + len(data))
            return bytes(images[region][address - region:address - region + length])
        cpu.mem_read.side_effect = read
        h = SimpleNamespace(cpu=cpu, rv=SimpleNamespace(symbols={
            'npu_emulation_control_v2_state': session, 'npu_emulation_cold_setup_state': state}))
        request = [0x3f, 1, 0x3253434e, 2, 80, 1, 58, 3, 4, 1, 2, 0x1a, 0, 0x200d4590, *([0] * 6)]
        return h, request, images, setup

    def test_only_two_request_derived_words_change_without_native_writes(self):
        h, request, images, _ = self.fixture()
        before = {base: bytes(data) for base, data in images.items()}
        result, changes = expected(h, request)
        self.assertEqual([row['address'] for row in changes], ['0x3e902a90', '0x3e906390'])
        want = {base: bytearray(data) for base, data in before.items()}
        struct.pack_into('<I', want[0x3e900000], 0x2a90, 0x200d4590)
        struct.pack_into('<I', want[0x3e900000], 0x6390, 58)
        self.assertEqual(result, want)
        self.assertEqual({base: bytes(data) for base, data in images.items()}, before)
        h.cpu.mem_write.assert_not_called()
        h.cpu.reg_write.assert_not_called()

    def test_wrong_pointer_replay_identity_envelope_and_reserved_reject(self):
        for index, value in ((13, 0), (13, 0x200d4594), (6, 57), (7, 9),
                             (9, 9), (4, 79), (11, 0x10), (12, 1), (15, 1)):
            h, request, _, _ = self.fixture()
            request[index] = value
            with self.assertRaises(AssertionError):
                expected(h, request)
            h.cpu.mem_write.assert_not_called()

    def test_completed_prefix_is_required_before_region_reads(self):
        for offset, value in ((0, 1), (4, 1), (380, 1), (48, 0x20000001), (52, 4096),
                              (388, 0), (388, 0x200d4454), (392, 0), (396, 1), (400, 1)):
            h, request, _, setup = self.fixture()
            data = bytearray(setup)
            struct.pack_into('<I', data, offset, value)
            original = h.cpu.mem_read.side_effect
            h.cpu.mem_read.side_effect = lambda address, size: bytes(data) if address == 0x84046000 else original(address, size)
            with self.assertRaises(AssertionError):
                expected(h, request)
            self.assertFalse(any(call.args[0] in dict(SPACES) for call in h.cpu.mem_read.call_args_list))

    def test_both_accepted_hif_profiles_keep_the_same_rx_pointer_projection(self):
        for hif2 in (0, 1):
            h, request, _, _ = self.fixture(hif2)
            result, changes = expected(h, request)
            self.assertEqual(struct.unpack_from('<I', result[0x3e900000], 0x2a90)[0], 0x200d4590)
            self.assertEqual(len(changes), 2)
            h.cpu.mem_write.assert_not_called()


if __name__ == '__main__':
    unittest.main()
