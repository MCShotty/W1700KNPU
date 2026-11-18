"""Successor source contracts, without running a complete build or loading modules."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_npu_image_seal import put

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import npu_successor_sources as successor
import npu_world_sources as world_sources


class SuccessorSourceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="npu-successor-sources-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.authority = self.root / "authority"
        self.build = self.root / "prepared"
        self.revision = "a1b2c3d4" * 5
        self.release = "6.18.52"
        self.kernel = self.build / successor.PREPARED / ("linux-" + self.release)
        self.mt76 = self.build / successor.PREPARED / ("mt76-fixture~" + self.revision[:8])

        def overlay(name, contents):
            target = self.build / name
            pin = put(target, contents)
            target.chmod(0o644)
            return dict(path=name, sha256=pin, mode="0644")

        series = {}
        rows = []
        for group, old in successor.handoff.OLD_PATCHES.items():
            path = Path(old).parent
            order = [Path(old).name, "zz-checked-late.patch"]
            additions = [overlay((path / name).as_posix(), name.encode()) for name in order]
            rows += additions
            series[group] = dict(directory=path.as_posix(), order=order,
                                 sha256=dict(zip(order, [r["sha256"] for r in additions])))
        config = b"pinned OpenWrt config"
        config_pin = put(self.authority / successor.CONFIG, config)
        put(self.build / ".config", config)
        self.component = "drivers/example/component.c"
        component = dict(tree="openwrt",
                         destination="target/linux/airoha/files-6.18/" + self.component,
                         source="firmware/component.c",
                         sha256=put(self.kernel / self.component, b"component"), mode="0644")
        put(self.authority / component["source"], b"component")
        self.lock = dict(kernel=self.release, mt76=self.revision, openwrt=dict(changed_files=rows),
                         luci=dict(changed_files=[]), component_sources=[component])
        self.kernel_files = {"new.c": b"new Linux output", "old.c": b"unchanged Linux output"}
        self.mt76_files = {"changed.c": b"new mt76 output", "old.c": b"unchanged mt76 source"}
        self.sources = {}
        files = {successor.SOURCE_LOCK: put(self.authority / successor.SOURCE_LOCK, self.lock),
                 successor.CONFIG: config_pin}
        for group, tree, names in (("kernel", self.kernel, self.kernel_files), ("mt76", self.mt76, self.mt76_files)):
            self.sources[group] = {}
            for name, raw in names.items():
                rel = f"{successor.MERGED}/{group}-merged/{name}"
                pin = put(self.authority / rel, raw)
                self.sources[group][name] = files[rel] = pin
                put(tree / name, raw)
        self.contract = dict(schema=successor.SCHEMA, source_only=True, compiler_ran=False,
                             source_lock_sha256=files[successor.SOURCE_LOCK], parent_lock_sha256="a" * 64,
                             parent_producer_sha256="b" * 64, config_sha256=config_pin,
                             parent_artifacts={"airoha_npu.ko": "c" * 64, "mt76.ko": "d" * 64},
                             files=files, sources=self.sources, patches=series)
        self.contract_pin = put(self.authority / successor.CONTRACT, self.contract)

    def test_prepared_and_authority_match_full_maps(self):
        contract, pin, lock = successor.verify_authority(self.authority, self.contract_pin)
        proof = successor.verify_prepared(self.build, contract, lock)
        self.assertEqual(pin, self.contract_pin)
        self.assertEqual(proof["kernel_files"], 2)
        self.assertEqual(proof["mt76_files"], 2)
        self.assertEqual(proof["component_files"], 1)

    def test_prepared_late_patch_not_in_lock_is_refused(self):
        series = self.contract["patches"]["kernel"]
        put(self.build / series["directory"] / "zzz-extra.patch", b"extra patch")
        with self.assertRaisesRegex(ValueError, "patch tail differs"):
            successor.verify_prepared(self.build, self.contract, self.lock)

    def test_prepared_kernel_and_unchanged_mt76_sources_must_match(self):
        for path, diagnostic in ((self.kernel / "new.c", "Prepared kernel source"),
                                 (self.mt76 / "old.c", "Prepared mt76 source")):
            with self.subTest(path=path):
                previous = path.read_bytes()
                put(path, b"stale")
                with self.assertRaisesRegex(ValueError, diagnostic):
                    successor.verify_prepared(self.build, self.contract, self.lock)
                put(path, previous)

    def test_prepared_component_must_match(self):
        put(self.kernel / self.component, b"copied wrong component")
        with self.assertRaisesRegex(ValueError, "Prepared component differs"):
            successor.verify_prepared(self.build, self.contract, self.lock)

    def test_ambiguous_mt76_revision_refuses_fallback(self):
        (self.mt76.parent / ("mt76-extra~" + self.revision[:8])).mkdir()
        with self.assertRaisesRegex(ValueError, "Expected one prepared tree"):
            successor.verify_prepared(self.build, self.contract, self.lock)

    def test_aliased_authority_source_is_refused_even_with_matching_contents(self):
        real = self.authority / successor.MERGED / "kernel-merged/old.c"
        duplicate = real.with_name("outside-name.c")
        real.rename(duplicate)
        real.symlink_to(duplicate)
        with self.assertRaisesRegex(ValueError, "aliased path"):
            successor.verify_authority(self.authority, self.contract_pin)

    def test_producer_requires_contract_and_changed_artifact_identity(self):
        path = self.authority / "test-result.json"
        pin = put(path, b"independent receipt")
        base = dict(receipt_sha256=pin, source_lock_sha256=self.contract["source_lock_sha256"],
                    inputs={successor.CONFIG: self.contract["config_sha256"], successor.CONTRACT: self.contract_pin},
                    artifacts={"output/airoha_npu.ko": "e" * 64, "output/mt76.ko": "f" * 64}, **self.sources)
        for fake, diagnostic in (
            (base | dict(inputs={successor.CONFIG: self.contract["config_sha256"]}), "does not bind"),
            (base | dict(kernel={"old.c": "e" * 64}), "kernel prepared inputs differ"),
            (base | dict(artifacts=self.contract["parent_artifacts"]), "reuses the parent's complete module set"),
        ):
            with self.subTest(diagnostic=diagnostic), \
                 patch.object(successor, "linked_module_sources", return_value=fake), \
                 self.assertRaisesRegex(ValueError, diagnostic):
                successor.verify_producer(self.authority, self.contract, self.contract_pin, path, pin)
        with patch.object(successor, "linked_module_sources", return_value=base):
            self.assertEqual(successor.verify_producer(self.authority, self.contract, self.contract_pin, path, pin), base)

    def test_late_patch_lock_dispatches_to_successor_check_without_fallback(self):
        receipt = self.authority / "test-result.json"
        pin = put(receipt, b"independent receipt")
        base = dict(receipt_sha256=pin, source_lock_sha256=self.contract["source_lock_sha256"],
                    inputs={successor.CONFIG: self.contract["config_sha256"], successor.CONTRACT: self.contract_pin},
                    artifacts={"output/airoha_npu.ko": "e" * 64, "output/mt76.ko": "f" * 64}, **self.sources)
        self.assertTrue(world_sources.has_late_module_patches(self.lock))
        with self.assertRaisesRegex(ValueError, "require a combined successor"):
            world_sources.verify(self.build, self.authority, self.lock)
        with patch.object(world_sources, "linked_module_sources", return_value=base):
            proof = world_sources.verify(self.build, self.authority, self.lock, module_receipt=receipt)
        self.assertEqual(proof["kernel_patch_files"], 2)
        self.assertEqual(proof["source_contract_sha256"], self.contract_pin)
        with patch.object(world_sources, "linked_module_sources", return_value=base | dict(inputs={})), \
             self.assertRaisesRegex(ValueError, "require the successor source contract"):
            world_sources.verify(self.build, self.authority, self.lock, module_receipt=receipt)


if __name__ == "__main__":
    unittest.main()
