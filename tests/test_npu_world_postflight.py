"""The opt-in recheck only accepts the known baseline failure."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from npu_world_postflight import check_failure


class WorldPostflightTests(unittest.TestCase):
    def setUp(self):
        self.pin = 'a' * 64
        self.build = Path('/fixture/build')
        self.log = Path('/fixture/log')
        self.evidence = dict(terminal_world_sha256=self.pin,
                             producer_sha256='b' * 64, source_lock_sha256='c' * 64)
        inventories = dict(lower=dict(entries=4, sha256='d' * 64),
                           cache=dict(entries=5, sha256='e' * 64))
        self.launch = dict(network_isolated=True, streamed_inventories=inventories,
                           producer_sha256='b' * 64, source_lock_sha256='c' * 64)
        self.world = dict(passed=False, returncode=1, world_build=False, child=None,
                          envelope=deepcopy(self.launch), streamed_inventories_after=deepcopy(inventories),
                          snapshot_unchanged=True, parent_namespaces_unchanged=True,
                          original_build_content_modes_ownership_links_unchanged=True,
                          original_download_cache_content_modes_ownership_links_unchanged=True,
                          host_timeout=False, probe_only=False, hardware=False, module_loaded=False)
        self.state = dict(exit_code=0, started=5, finished=10, command=['make', '-j2', 'world', 'V=s'],
                          cwd=str(self.build), log=str(self.log))

    def check(self):
        check_failure(self.world, self.pin, self.evidence, self.launch, self.state, self.build, self.log)

    def test_eligible_failure_is_not_rewritten(self):
        before = deepcopy(self.world)
        self.check()
        self.assertEqual(self.world, before)

    def test_unknown_terminal_receipt_is_not_eligible(self):
        self.pin = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'pinned RV32 roster'):
            self.check()

    def test_changed_protected_inventory_cannot_be_ignored(self):
        self.world['streamed_inventories_after']['cache']['sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            self.check()

    def test_unsuccessful_world_build_is_not_a_roster_failure(self):
        self.state['exit_code'] = 1
        with self.assertRaisesRegex(ValueError, 'No completed make world'):
            self.check()

    def test_unrelated_launch_is_not_eligible(self):
        self.launch['producer_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'Frozen launch differs'):
            self.check()


if __name__ == '__main__':
    unittest.main()
