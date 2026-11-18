"""Host-only checks of the staged Ethernet artifact gate."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_npu_image_seal import put, sha

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import npu_ethernet_fit as eth
import seal_npu_image as seal


class EthernetBindingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ethernet-fit-fixture-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.frozen = self.root / "immutable-fixture"
        self.upper = self.root / "upper-fixture"
        self.kernel = self.upper / eth.KERNELS / "linux-6.18.52"
        self.sources = self.kernel / eth.ETH_DRIVER
        prefix = "target/linux/airoha/patches-6.18/"
        self.patches = {prefix + n: put(self.frozen / "firmware/overlay/openwrt" / prefix / n, n.encode())
                        for n in (eth.PPE, eth.QDMA)}
        self.lock = dict(kernel="6.18.52", openwrt=dict(changed_files=[
            dict(path=name, sha256=pin) for name, pin in self.patches.items()]))
        lock_pin = put(self.frozen / eth.SOURCE_LOCK, self.lock)
        files = {"firmware/overlay/openwrt/" + k: v for k, v in self.patches.items()}
        files[eth.SOURCE_LOCK] = lock_pin
        posts = {(eth.ETH_DRIVER / name).as_posix(): put(self.sources / name, name.encode())
                 for name in eth.ETH_SOURCES}
        self.bundle = self.root / eth.BUNDLES / "fixture" / "receipt.json"
        self.bundle_row = dict(
            schema=1, source_preflight_passed=True, source_delta_only=True, linux_modules_built=False,
            fit_built=False, board_contact=False, files=files, parent_lock_sha256="1" * 64,
            prepared_overlay_staging=dict(source_lock_sha256=lock_pin),
            source_stack=dict(kernel=dict(patch_order=[eth.PPE, eth.QDMA], postimages=posts)))
        self.bundle_pin = put(self.bundle, self.bundle_row)
        self.module = self.sources / eth.ETH_MODULE
        self.raw = b"opaque placeholder; ELF parsing is tested separately"
        self.module_pin = put(self.module, self.raw)
        objcopy = "staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-objcopy"
        self.objcopy = self.root / eth.BUILD / objcopy
        self.tool_pin = put(self.objcopy, b"placeholder tool")
        self.config_pin = put(self.frozen / eth.BUILD_CONFIG, b'CONFIG_GCC_VERSION="14.4.0"\n')
        self.packaging = dict(config_sha256=self.config_pin,
                              profile="openwrt-w1700k-no-rename-no-build-id",
                              objcopy_args=list(eth.fit_tools.KMOD_OBJCOPY_ARGS),
                              objcopy=objcopy, objcopy_sha256=self.tool_pin)
        self.world = dict(source_lock=self.lock, source_lock_sha256=lock_pin, frozen=self.frozen,
                          declarations={**files, eth.BUILD_CONFIG: self.config_pin}, kernel="6.18.52",
                          build_upper=self.upper, image=dict(packaged_module_provenance=self.packaging))

    def args(self, **changes):
        return SimpleNamespace(**(dict(ethernet_bundle=self.bundle, ethernet_bundle_sha256=self.bundle_pin,
                                       ethernet_linked_sha256=self.module_pin) | changes))

    def test_original_lock_keeps_four_module_contract_without_optional_override(self):
        original = self.world | dict(source_lock=dict(kernel="6.18.52"))
        self.assertIsNone(eth.bind_linked(self.root, original, SimpleNamespace(), self.root))
        with self.assertRaisesRegex(ValueError, "only for a staged Ethernet"):
            eth.bind_linked(self.root, original, self.args(), self.root)

    def test_staged_lock_requires_three_independent_inputs(self):
        for name in vars(self.args()):
            with self.subTest(missing=name), self.assertRaisesRegex(ValueError, "requires a pinned Ethernet"):
                eth.bind_linked(self.root, self.world, self.args(**{name: None}), self.root)

    def test_qdma_patch_without_ppe_preimage_is_refused(self):
        rows = self.lock["openwrt"]["changed_files"]
        with self.assertRaisesRegex(ValueError, "requires the staged PPE preimage"):
            eth.required_patches(self.lock | dict(openwrt=dict(changed_files=rows[1:])))

    def test_bind_uses_same_world_linked_output_and_configured_tool(self):
        with patch.object(eth, "inspect_linked", return_value={"name": "airoha_eth"}) as abi, \
             patch.object(eth, "normalize", return_value="4" * 64) as strip:
            proof = eth.bind_linked(self.root, self.world, self.args(), self.root)
        abi.assert_called_once_with(self.raw, "6.18.52", with_qdma=True)
        strip.assert_called_once_with(self.raw, self.objcopy, self.tool_pin, self.root)
        self.assertEqual(proof["linked_sha256"], self.module_pin)
        self.assertEqual(proof["bundle_sha256"], self.bundle_pin)
        self.assertEqual(proof["config_sha256"], self.config_pin)
        self.assertEqual(proof["expected_packaged_sha256"], "4" * 64)
        self.assertEqual(proof["patch_order"], [eth.PPE, eth.QDMA])

    def test_bundle_must_be_pinned_ordered_and_in_capsule(self):
        with self.assertRaisesRegex(ValueError, "Receipt digest mismatch"):
            eth.verify_bundle(self.root, self.world, self.patches, self.bundle, "2" * 64)
        unrelated = self.world | dict(staged_bundle_sha256="9" * 64)
        with self.assertRaisesRegex(ValueError, "differs from the successor source contract"):
            eth.verify_bundle(self.root, unrelated, self.patches, self.bundle, self.bundle_pin)
        trimmed = self.world | dict(declarations={eth.SOURCE_LOCK: self.world["source_lock_sha256"]})
        with self.assertRaisesRegex(ValueError, "does not bind Ethernet bundle member"):
            eth.verify_bundle(self.root, trimmed, self.patches, self.bundle, self.bundle_pin)
        tree = self.bundle_row["source_stack"]["kernel"] | dict(patch_order=[eth.QDMA, eth.PPE])
        swapped = put(self.bundle, self.bundle_row | dict(source_stack=dict(kernel=tree)))
        with self.assertRaisesRegex(ValueError, "patch sequence"):
            eth.verify_bundle(self.root, self.world, self.patches, self.bundle, swapped)

    def test_wrong_prepared_source_is_rejected_before_module_inspection(self):
        put(self.sources / "airoha_eth.c", b"pre-PPE source")
        with self.assertRaisesRegex(ValueError, "differs from staged postimage"), \
             patch.object(eth, "inspect_linked") as abi:
            eth.bind_linked(self.root, self.world, self.args(), self.root)
        abi.assert_not_called()

    def test_stale_or_aliased_linked_outputs_cannot_qualify(self):
        with self.assertRaisesRegex(ValueError, "differs from the independent pin"):
            eth.bind_linked(self.root, self.world, self.args(ethernet_linked_sha256="8" * 64), self.root)
        outside = self.root / eth.ETH_MODULE
        put(outside, self.raw)
        self.module.unlink()
        self.module.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "aliased path"):
            eth.bind_linked(self.root, self.world, self.args(), self.root)

    def test_artifact_changes_during_transform_are_refused(self):
        def normalize(*_):
            put(self.module, b"new unpinned build")
            return "4" * 64

        with patch.object(eth, "inspect_linked"), patch.object(eth, "normalize", side_effect=normalize), \
             self.assertRaisesRegex(ValueError, "outputs changed"):
            eth.bind_linked(self.root, self.world, self.args(), self.root)

    def test_pinned_transform_refuses_wrong_tool_or_profile(self):
        with patch.object(eth.fit_tools, "run") as runner, \
             self.assertRaisesRegex(ValueError, "strip tool digest mismatch"):
            eth.normalize(self.raw, self.objcopy, "a" * 64, self.root)
        runner.assert_not_called()
        self.packaging["objcopy_args"] = ["--strip-all"]
        with self.assertRaisesRegex(ValueError, "Unsupported Ethernet module packaging"):
            eth.normalization_tool(self.root, self.world)

    def test_plain_text_is_not_a_linked_module(self):
        with self.assertRaisesRegex(ValueError, "Malformed linked Ethernet ELF"):
            eth.inspect_linked(self.raw, self.world["kernel"])


@unittest.skipUnless(all(shutil.which(t) for t in ("dtc", "mkimage", "fdtget", "fdtput", "dumpimage",
                                                 "mksquashfs", "unsquashfs")),
                     "FIT fixture tools unavailable")
class EthernetFITSelectionTests(unittest.TestCase):
    def test_stale_ethernet_in_selected_squashfs_cannot_use_the_other_configuration(self):
        with tempfile.TemporaryDirectory(prefix="ethernet-fit-selection-") as directory:
            root = Path(directory).resolve()

            def run(*args):
                subprocess.run(args, cwd=root, check=True, capture_output=True, timeout=120,
                               env=dict(os.environ, SOURCE_DATE_EPOCH="0", MALLOC_ARENA_MAX="1"))

            kernel = "6.18.52"
            payloads = dict(code=b"fixture CODE", data=b"fixture DATA")
            replay = {key: sha(value) for key, value in payloads.items()}
            manifest = {key: dict(sha256=pin) for key, pin in replay.items()}
            common = {name: name.encode() for name in eth.fit_tools.MODULE_NAMES}
            ethernet = b"exact Ethernet payload fixture"
            for label, body in (("current", ethernet), ("stale", b"older Ethernet payload fixture")):
                tree = root / label
                for name, value in (common | {eth.ETH_MODULE: body}).items():
                    put(tree / f"lib/modules/{kernel}/{name}", value)
                for key, value in payloads.items():
                    put(tree / seal.FIT_PAIR_FILES[key], value)
                put(tree / seal.FIT_PAIR_FILES["manifest"], manifest)
                run("mksquashfs", tree, f"{label}.sqfs", "-processors", "1", "-no-xattrs",
                    "-noappend", "-no-progress", "-all-root", "-comp", "gzip")

            put(root / "fake-kernel", b"not executable")
            put(root / "w1700k.dts", b'/dts-v1/; / { model = "Gemtek W1700K (OpenWrt U-Boot layout)";'
                b' compatible = "gemtek,w1700k-ubi", "airoha,en7581"; };')
            run("dtc", "-I", "dts", "-O", "dtb", "-o", "w1700k.dtb", "w1700k.dts")

            def image(name, file, kind, extra=""):
                return (f'{name} {{ description = "{name}"; data = /incbin/("{file}");'
                        f' type = "{kind}"; arch = "arm64"; compression = "none"; {extra}'
                        ' hash-1 { algo = "sha256"; }; };')

            def config(name):
                return f'{name} {{ kernel = "k"; fdt = "d"; loadables = "{name}"; }};'

            nodes = (image("k", "fake-kernel", "kernel", 'os = "linux"; load = <0>; entry = <0>;') +
                     image("d", "w1700k.dtb", "flat_dt") +
                     image("current", "current.sqfs", "filesystem") +
                     image("stale", "stale.sqfs", "filesystem"))
            put(root / "fixture.its", ('/dts-v1/; / { description = "Nonbootable fixture";'
                f' #address-cells = <1>; images {{ {nodes} }}; configurations {{ default = "current";'
                f' {config("current")} {config("stale")} }}; }};').encode())
            fit = root / "fixture.itb"
            run("mkimage", "-f", "fixture.its", fit)

            names = (*eth.fit_tools.MODULE_NAMES, eth.ETH_MODULE)
            proof = dict(expected_packaged_sha256=sha(ethernet))
            for label in ("current", "stale"):
                run("fdtput", "-t", "s", fit, "/configurations", "default", label)
                out = root / f"extracted-{label}"
                out.mkdir()
                # The payloads are intentionally inert. FIT, SquashFS, hashes,
                # selection and the fifth module comparison are real here.
                with patch.object(seal.npu_image, "validate") as firmware:
                    packed = seal.inspect_fit_pair(fit, out, kernel, replay, names)
                firmware.assert_called_once_with(payloads["code"], payloads["data"], manifest)
                self.assertEqual(packed["fit_configuration"]["rootfs"], label)
                world = dict(image=packed | dict(checked_npu_pair=packed["pair"]),
                             module_sha256={k: sha(v) for k, v in common.items()})
                if label == "current":
                    seal.bind_packaged(packed, world, {"pair": replay}, proof)
                else:
                    with self.assertRaisesRegex(ValueError, "FIT Ethernet module differs"):
                        seal.bind_packaged(packed, world, {"pair": replay}, proof)


if __name__ == "__main__":
    unittest.main()
