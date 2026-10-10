import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from verify_merged_image import verify_control_ownership


class ControlOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.control = {'npu_linux_control_init', 'npu_linux_control_exchange',
                        'npu_linux_control_close', 'npu_linux_control_snapshot',
                        'npu_client_v2_request', 'npu_client_v2_complete',
                        'npu_linux_control_cold_exchange', 'npu_cold_client_request', 'npu_cold_client_complete'}
        self.provider = self.control | {'airoha_npu_wlan_control'}

    def test_provider_links_all_control_symbols(self):
        verify_control_ownership('airoha_npu.ko', self.provider, set())
        for missing in self.provider:
            with self.subTest(missing=missing), self.assertRaises(AssertionError):
                verify_control_ownership('airoha_npu.ko', self.provider - {missing}, set())

    def test_provider_does_not_import_its_client(self):
        for imported in self.control:
            with self.subTest(imported=imported), self.assertRaises(AssertionError):
                verify_control_ownership('airoha_npu.ko', self.provider, {imported})

    def test_consumer_has_no_control_definitions(self):
        verify_control_ownership('mt76.ko', {'mt76_npu_init'}, {'airoha_npu_get'})
        for duplicate in self.control:
            with self.subTest(duplicate=duplicate), self.assertRaises(AssertionError):
                verify_control_ownership('mt76.ko', {duplicate}, set())

    def test_consumer_does_not_import_private_transport(self):
        with self.assertRaises(AssertionError):
            verify_control_ownership('mt76.ko', set(), {'airoha_npu_wlan_control'})


if __name__ == '__main__':
    unittest.main()
