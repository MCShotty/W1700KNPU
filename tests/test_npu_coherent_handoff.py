"""Check locking, patch-order and publication rules for the source delta."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage_npu_coherent_handoff as handoff


class HandoffTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_derive_preserves_parent_and_last_router_tested_snapshot(self):
        original = dict(snapshot="parent", last_router_tested_snapshot="router-tested",
                        openwrt=dict(changed_files=[dict(path="base", sha256="c" * 64, mode="0o755")]),
                        luci=dict(changed_files=[]), mt76="fixed", kernel="6.18.52")
        old_bytes = handoff.as_json(original)
        result = handoff.derive_lock(original, {"added": b"candidate"})
        self.assertEqual(handoff.as_json(original), old_bytes)
        self.assertEqual(result["openwrt"]["changed_files"], [
            dict(path="added", sha256=handoff.sha_bytes(b"candidate"), mode="0o644"),
            original["openwrt"]["changed_files"][0],
        ])
        self.assertEqual(result["last_router_tested_snapshot"], "router-tested")
        self.assertEqual(result["luci"], original["luci"])
        self.assertNotEqual(original["snapshot"], result["snapshot"])
        with_ppe = handoff.derive_lock(original, {"added": b"candidate"}, with_ppe=True)
        self.assertNotEqual(with_ppe["snapshot"], result["snapshot"])
        self.assertEqual(with_ppe["openwrt"], result["openwrt"])
        with_qdma = handoff.derive_lock(original, {"added": b"candidate"}, with_qdma=True)
        self.assertNotEqual(with_qdma["snapshot"], with_ppe["snapshot"])
        self.assertEqual(with_qdma["openwrt"], with_ppe["openwrt"])
        with self.assertRaisesRegex(ValueError, "already owns"):
            handoff.derive_lock(original, {"base": b"different"})

    def test_only_late_series_with_unambiguous_order(self):
        old = "999-w1700k-integrated-npu.patch"
        names = [old, "001-board.patch"]
        for name in names:
            (self.root / name).touch()
        extras = ["9999-w1700k-b.patch", "9999-w1700k-a.patch"]
        self.assertEqual(handoff.check_order(self.root, old, extras), [old, *sorted(extras)])
        with self.assertRaisesRegex(ValueError, "does not follow"):
            handoff.check_order(self.root, old, ["800-too-early.patch"])
        with self.assertRaisesRegex(ValueError, "no longer the last"):
            handoff.check_order(self.root, old, [old])
        (self.root / "series").write_text(old + "\n")
        with self.assertRaisesRegex(ValueError, "convention changed"):
            handoff.check_order(self.root, old, extras)

    def test_fresh_bundle_and_exact_publication_check(self):
        bundle = self.root / "ready"
        inputs = {"firmware/source-lock.json": b"lock", "firmware/overlay/a.patch": b"patch"}
        receipt = {"source_delta_only": True}
        handoff.publish(bundle, inputs, receipt)
        handoff.check_published(bundle, inputs, receipt)
        with self.assertRaises(FileExistsError):
            handoff.publish(bundle, inputs, receipt)
        (bundle / "firmware/overlay/a.patch").write_bytes(b"wrong")
        with self.assertRaisesRegex(ValueError, "bundle differs"):
            handoff.check_published(bundle, inputs, receipt)

    def test_refuses_alias_extra_and_incomplete_bundle(self):
        bundle = self.root / "ready"
        inputs = {"firmware/source-lock.json": b"lock"}
        receipt = {"source_delta_only": True}
        handoff.publish(bundle, inputs, receipt)
        alias = bundle / "alias"
        alias.symlink_to(bundle / "firmware/source-lock.json")
        with self.assertRaisesRegex(ValueError, "unexpected bundle contents"):
            handoff.check_published(bundle, inputs, receipt)
        alias.unlink()
        (bundle / "receipt.json").unlink()
        with self.assertRaisesRegex(ValueError, "unexpected bundle contents"):
            handoff.check_published(bundle, inputs, receipt)

    def test_source_bundle_name_is_not_a_path(self):
        for name in ("../firmware", "project/other", "a.patch", " ", ""):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "invalid bundle name"):
                handoff.bundle_path(name)


if __name__ == "__main__":
    unittest.main()
