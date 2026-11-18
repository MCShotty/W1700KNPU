"""Check the W1700K reserved coherent pool through real FDT host tools."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import verify_npu_coherent_window as window

POOL = "/reserved-memory/npu-dma-pool"
FIXTURE = """/dts-v1/;
/ {
    compatible = "gemtek,w1700k-ubi";
    #address-cells = <2>;
    #size-cells = <2>;
    reserved-memory {
        #address-cells = <2>;
        #size-cells = <2>;
        ranges;
        fw: fw@84000000 { reg = <0 0x84000000 0 0x100000>; };
        rx: rx@85000000 { reg = <0 0x85000000 0 0x100000>; };
        tx: tx@86000000 { reg = <0 0x86000000 0 0x100000>; };
        ids: ids@87000000 { reg = <0 0x87000000 0 0x100000>; };
        ba: ba@88000000 { reg = <0 0x88000000 0 0x100000>; };
        pool: npu-dma-pool {
            compatible = "shared-dma-pool";
            size = <0 0x01000000>;
            alignment = <0 0x01000000>;
            alloc-ranges = <0 0x80000000 0 0x40000000>;
            no-map;
        };
    };
    soc {
        #address-cells = <2>;
        #size-cells = <2>;
        ranges;
        npu@1e900000 {
            compatible = "airoha,en7581-npu";
            reg = <0 0x1e900000 0 0x313000>;
            memory-region-names = "binary", "pkt", "tx-pkt", "tx-bufid", "ba", "dma";
            memory-region = <&fw>, <&rx>, <&tx>, <&ids>, <&ba>, <&pool>;
        };
    };
};
"""


def call(*command, input=None):
    result = subprocess.run(command, input=input, capture_output=True, timeout=20)
    if result.returncode:
        raise AssertionError(result.stderr.decode(errors="replace"))


@unittest.skipUnless(all(shutil.which(t) for t in ("dtc", "fdtget", "fdtput")), "FDT tools unavailable")
class CoherentWindowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.dtb = self.root / "fixture.dtb"
        call("dtc", "-I", "dts", "-O", "dtb", "-o", self.dtb, "-", input=FIXTURE.encode())

    def set_property(self, path, node, prop, kind, *values):
        call("fdtput", "-t", kind, path, node, prop, *values)

    def test_valid_pool(self):
        result = window.verify_dtb(self.dtb)
        self.assertEqual(result["pool_path"], POOL)
        self.assertEqual(result["pool_window"], [0x80000000, 0xC0000000])
        self.assertEqual(result["pool_size"], 16 * 1024 * 1024)
        self.assertEqual(result["fixed_npu_regions"]["binary"], (0x84000000, 0x100000))
        self.assertEqual(result["dtb_sha256"], window.sha256(self.dtb))

    def test_refuses_incompatible_geometry_and_ownership(self):
        npu = window.NPU
        for node, prop, kind, values, diagnostic in (
            (POOL, "size", "x", ("0", "800000"), "wrong NPU pool size"),
            (POOL, "alloc-ranges", "x", ("0", "90000000", "0", "40000000"), "differs from"),
            (POOL, "alignment", "x", ("0", "1000"), "wrong NPU pool alignment"),
            (POOL, "reg", "x", ("0", "84000000", "0", "1000000"), "dynamically placed"),
            (POOL, "reusable", "x", (), "must be dedicated"),
            (POOL, "linux,dma-default", "x", (), "must be dedicated"),
            (POOL, "status", "s", ("disabled",), "pool is disabled"),
            (npu, "memory-region-names", "s", ("dma", *window.REGION_NAMES[:-1]), "changed order"),
            ("/soc", "dma-ranges", "x", (), "unexpected DMA routing"),
            ("/reserved-memory/rx@85000000", "reg", "x", ("0", "84000000", "0", "1000"), "overlaps"),
        ):
            with self.subTest(prop=prop, node=node):
                mutated = self.root / "mutated.dtb"
                shutil.copyfile(self.dtb, mutated)
                self.set_property(mutated, node, prop, kind, *values)
                with self.assertRaisesRegex(ValueError, diagnostic):
                    window.verify_dtb(mutated)

    def test_refuses_a_pool_without_no_map(self):
        call("fdtput", "-d", self.dtb, POOL, "no-map")
        with self.assertRaisesRegex(ValueError, "needs no-map"):
            window.verify_dtb(self.dtb)

    @unittest.skipUnless(shutil.which("mkimage") and shutil.which("dumpimage"), "FIT tools unavailable")
    def test_only_the_selected_dtb_can_satisfy_the_check(self):
        old = self.root / "old.dtb"
        shutil.copyfile(self.dtb, old)
        self.set_property(old, window.NPU, "memory-region-names", "s", *window.REGION_NAMES[:-1])
        blob = self.root / "dummy.bin"
        blob.write_bytes(b"inert test fixture")
        its, fit = self.root / "fixture.its", self.root / "fixture.itb"
        components = [
            f'{name} {{ description = "{name}"; data = /incbin/("{path}"); '
            f'type = "{kind}"; arch = "arm64"; os = "linux"; compression = "none"; }};'
            for name, path, kind in (
                ("kernel", blob, "kernel"), ("rootfs", blob, "filesystem"),
                ("with-pool", self.dtb, "flat_dt"), ("without-pool", old, "flat_dt"),
            )
        ]
        configs = [
            f'{name} {{ kernel = "kernel"; loadables = "rootfs"; fdt = "{name}"; }};'
            for name in ("with-pool", "without-pool")
        ]
        its.write_text('/dts-v1/; / { description = "Fixture"; images { '
                       + " ".join(components) + ' }; configurations { default = "with-pool"; '
                       + " ".join(configs) + " }; };", encoding="ascii")
        call("mkimage", "-f", its, fit)
        result = window.verify_fit(fit, window.sha256(fit))
        self.assertEqual(result["fit_configuration"]["fdt"], "with-pool")
        self.assertEqual(result["dtb_sha256"], window.sha256(self.dtb))
        self.set_property(fit, "/configurations", "default", "s", "without-pool")
        with self.assertRaisesRegex(ValueError, "input SHA-256 mismatch"):
            window.verify_fit(fit, result["fit_sha256"])
        with self.assertRaisesRegex(ValueError, "missing NPU coherent DMA pool"):
            window.verify_fit(fit, window.sha256(fit))


if __name__ == "__main__":
    unittest.main()
