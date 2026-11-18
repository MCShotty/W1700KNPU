"""Exercise the image verifier with compiled five- and six-region DTBs."""
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from verify_merged_image import board_configuration, expects_coherent_pool, sha


def dts(pool_size=None):
    regions = (('binary', 0x84000000, 0xa00000), ('pkt', 0x8a000000, 0x2c00000),
               ('txpkt', 0x8cc00000, 0x4000000), ('txbufid', 0x90c00000, 0xe000),
               ('ba', 0x90c0e000, 0x200000))
    fixed = '\n'.join(f'{label}: npu-{label}@{base:x} {{ reg = <0 0x{base:x} 0 0x{size:x}>; no-map; }};'
                      for label, base, size in regions)
    refs, names = '&binary &pkt &txpkt &txbufid &ba', '"binary", "pkt", "tx-pkt", "tx-bufid", "ba"'
    opp = '\n'.join(f'opp{hz} {{ opp-hz = /bits/ 64 <{hz}>; }};'
                     for hz in range(500000000, 1200000001, 50000000))
    pool = ''
    if pool_size is not None:
        refs += ' &dma'
        names += ', "dma"'
        pool = f'dma: npu-dma-pool {{ compatible = "shared-dma-pool"; no-map; size = <0 {pool_size}>; ' \
               'alignment = <0 0x1000000>; alloc-ranges = <0 0x80000000 0 0x40000000>; };'
    return f'''/dts-v1/;
/ {{
    #address-cells = <2>; #size-cells = <2>; compatible = "gemtek,w1700k-ubi";
    reserved-memory {{ #address-cells = <2>; #size-cells = <2>; ranges; {fixed} {pool} }};
    soc {{ npu@1e900000 {{
        compatible = "airoha,en7581-npu"; status = "okay";
        memory-region = <{refs}>; memory-region-names = {names};
    }}; }};
    opp-table {{ {opp} }};
}};
'''


class PoolLockTests(unittest.TestCase):
    def test_exact_pool_binding_patch_selects_layout(self):
        lock = dict(kernel='6.18.52', openwrt=dict(changed_files=[]))
        self.assertFalse(expects_coherent_pool(lock))
        lock['openwrt']['changed_files'].append(dict(path=
            'target/linux/airoha/patches-6.18/9999-w1700k-npu-coherent-pool-binding.patch'))
        self.assertTrue(expects_coherent_pool(lock))


@unittest.skipUnless(shutil.which('dtc') and shutil.which('fdtget'), 'DTB tools are required')
class PoolBoardTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory(prefix='npu-fit-pool-test-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)

    def compile(self, name, size=None):
        path = self.root / (name + '.dtb')
        subprocess.run(['dtc', '-q', '-I', 'dts', '-O', 'dtb', '-o', path, '-'],
                       input=dts(size), text=True, capture_output=True, check=True)
        return path

    def test_actual_dtb_is_checked_against_the_selected_layout(self):
        legacy = self.compile('legacy')
        successor = self.compile('successor', 16 << 20)
        self.assertNotIn('coherent_dma_pool', board_configuration(legacy))
        proof = board_configuration(successor, coherent_pool=True)['coherent_dma_pool']
        self.assertEqual(proof['dtb_sha256'], sha(successor))
        self.assertEqual(proof['pool_size'], 16 << 20)
        for file, policy in ((legacy, True), (successor, False)):
            with self.subTest(file=file.name), self.assertRaisesRegex(AssertionError, 'selected lock'):
                board_configuration(file, coherent_pool=policy)

    def test_dedicated_pool_geometry_remains_required(self):
        wrong = self.compile('wrong', 15 << 20)
        with self.assertRaisesRegex(ValueError, 'wrong NPU pool size'):
            board_configuration(wrong, coherent_pool=True)


if __name__ == '__main__':
    unittest.main()
