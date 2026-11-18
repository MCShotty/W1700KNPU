"""Offline fixtures for source staging and publication in the clean module link."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import link_npu_successor as link


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return link.digest(path)


class SuccessorLinkTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix='successor-link-test-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_exact_source_files_are_copied_without_parent_objects(self):
        authority = self.root / 'authority'
        scratch = self.root / 'scratch'
        k = f'{link.sources.MERGED}/kernel-merged/driver.c'
        m = f'{link.sources.MERGED}/mt76-merged/dma.c'
        kc, mc = put(authority / k, b'provider'), put(authority / m, b'mt76')
        put(authority / f'{link.sources.MERGED}/mt76-merged/dma.o', b'old object')
        proof = link.stage_inputs(scratch, authority, {'sources': {
            'kernel': {'driver.c': kc}, 'mt76': {'dma.c': mc}}})
        self.assertEqual(link.digest(scratch / 'provider-source/driver.c'), kc)
        self.assertEqual(proof['dma.c']['sha256'], mc)
        self.assertFalse((scratch / 'mt76/dma.o').exists())

    def test_stage_refuses_drift(self):
        name = f'{link.sources.MERGED}/kernel-merged/driver.c'
        put(self.root / name, b'new bytes')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            link.stage_inputs(self.root / 'output', self.root,
                              {'sources': {'kernel': {'driver.c': '0' * 64}, 'mt76': {}}})
        self.assertFalse((self.root / 'output').exists())

    def test_clearing_retained_objects_leaves_sources_and_outer_header(self):
        driver = self.root / link.DRIVER
        put(driver / 'airoha_npu.ko', b'old provider')
        put(driver / 'airoha-eth.ko', b'old ethernet')
        put(driver / 'w1700k/.provider-main.o.cmd', b'old command')
        put(driver / 'w1700k/provider-main.o', b'old object')
        source = put(driver / 'w1700k/provider-main.c', b'current source')
        context = put(self.root / 'Module.symvers', b'retained export context')
        self.assertEqual(len(link.clear_outputs(self.root)), 4)
        self.assertEqual(link.digest(driver / 'w1700k/provider-main.c'), source)
        self.assertEqual(link.digest(self.root / 'Module.symvers'), context)
        self.assertFalse((driver / 'w1700k/provider-main.o').exists())

    def test_clearing_rejects_aliased_module(self):
        driver = self.root / link.DRIVER
        keep = self.root / 'protected-file'
        pinned = put(keep, b'untouched')
        driver.mkdir(parents=True)
        (driver / 'airoha-eth.ko').symlink_to(keep)
        with self.assertRaisesRegex(ValueError, 'aliased path'):
            link.clear_outputs(self.root)
        self.assertEqual(link.digest(keep), pinned)

    def test_provider_and_mt76_must_both_link_new_edges(self):
        row = dict(provider=dict(exports=sorted(link.NEW_EDGES)),
                   modules={'mt76.ko': dict(imports=sorted(link.NEW_EDGES))})
        link.check_edges(row)
        row['modules']['mt76.ko']['imports'].pop()
        with self.assertRaisesRegex(ValueError, 'queue-ownership edges'):
            link.check_edges(row)

    def test_receipt_is_published_only_after_module_checks(self):
        scratch = self.root / 'scratch'
        authority = self.root / 'authority'
        (authority / '.local').mkdir(parents=True)
        for name in (*link.MODULES, 'airoha-eth.ko'):
            put(scratch / name, name.encode())
        record = {'overlay_proof': {'ethernet': {'sha256': link.digest(scratch / 'airoha-eth.ko')}}}
        destination = authority / link.STORE / 'link-a'
        with patch.object(link.sources, 'verify_producer', side_effect=ValueError('receipt rejected')):
            with self.assertRaisesRegex(ValueError, 'receipt rejected'):
                link.publish(authority, destination, scratch, record, {}, 'a' * 64)
        self.assertFalse(destination.exists())
        with patch.object(link.sources, 'verify_producer') as verify:
            receipt, pin = link.publish(authority, destination, scratch, record, {}, 'a' * 64)
        self.assertEqual(verify.call_args.args[-1], pin)
        self.assertEqual(link.digest(receipt), pin)
        self.assertEqual(json.loads(receipt.read_bytes()), record)
        self.assertTrue(all(not p.stat().st_mode & 0o222 for p in destination.rglob('*') if p.is_file()))
        with self.assertRaisesRegex(ValueError, 'already exists'):
            link.output_name(destination.parent, destination.name)


if __name__ == '__main__':
    unittest.main()
