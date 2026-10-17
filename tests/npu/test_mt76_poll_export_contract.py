"""Source-export regression checks;not execution or kernel lifetime proof."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from merge_nonoc_sources import changed_existing_files

ROOT = Path(__file__).resolve().parents[2]
POLL = 'mt7996/mmio.c'
PATCH = 'package/kernel/mt76/patches/900-w1700k-integrated-npu.patch'


class PollExportContractTests(unittest.TestCase):
    def test_existing_changes_do_not_require_an_additional_allowlist_entry(self):
        with tempfile.TemporaryDirectory() as temporary:
            base, merged = Path(temporary) / 'base', Path(temporary) / 'merged'
            for tree in (base, merged):
                (tree / 'mt7996').mkdir(parents=True)
                (tree / 'dma.c').write_text('old\n')
                (tree / 'mt7996/mmio.c').write_text('same\n')
            (merged / 'dma.c').write_text('retained RX-event enrollment\n')
            self.assertEqual(changed_existing_files(base, merged), {'dma.c'})

    def test_source_discovery_excludes_metadata_backups_and_unlisted_new_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            base, merged = Path(temporary) / 'base', Path(temporary) / 'merged'
            for tree, body in ((base, 'old'), (merged, 'new')):
                (tree / '.git').mkdir(parents=True)
                for name in ('.git/config', 'source.c.orig', 'source.c.rej'):
                    (tree / name).write_text(body)
            (merged / 'new.c').write_text('requires explicit new-source enrollment\n')
            self.assertEqual(changed_existing_files(base, merged), set())

    def test_export_invokes_existing_source_discovery(self):
        tree = ast.parse((ROOT / 'tools/merge_nonoc_sources.py').read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and
                 isinstance(node.func, ast.Name) and node.func.id == 'changed_existing_files']
        self.assertEqual(len(calls), 1)
        self.assertEqual([item.id for item in calls[0].args], ['base', 'merged'])

    def test_tracked_patch_contains_retained_rx_event_allocation(self):
        text = (ROOT / 'firmware/overlay/openwrt' / PATCH).read_text()
        marker = '--- a/dma.c\n+++ b/dma.c\n'
        self.assertEqual(text.count(marker), 1)
        section = text.split(marker, 1)[1].split('\n--- a/', 1)[0]
        self.assertIn('+\tret = mt76_npu_alloc_rx_event(dev, q);\n', section)
        self.assertIn('+\tif (ret == -EOPNOTSUPP)\n', section)
        self.assertIn('+\telse if (ret)\n+\t\treturn ret;\n', section)

    def test_poll_is_in_the_explicit_additional_export_set(self):
        tree = ast.parse((ROOT / 'tools/merge_nonoc_sources.py').read_text())
        additions = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
                    isinstance(node.func.value, ast.Name) and node.func.value.id == 'names' and
                    node.func.attr == 'update' and len(node.args) == 1 and isinstance(node.args[0], ast.Tuple)):
                additions.update(ast.literal_eval(node.args[0]))
        self.assertIn(POLL, additions)

    def test_tracked_patch_contains_and_locks_the_poll_change(self):
        patch = ROOT / 'firmware/overlay/openwrt' / PATCH
        marker = '--- a/' + POLL + '\n+++ b/' + POLL + '\n'
        text = patch.read_text()
        self.assertEqual(text.count(marker), 1)
        section = text.split(marker, 1)[1].split('\n--- a/', 1)[0]
        self.assertIn('+\t\trcu_read_lock();\n', section)
        self.assertIn('+\t\trcu_read_unlock();\n', section)
        lock = json.loads((ROOT / 'firmware/source-lock.json').read_bytes())
        rows = [row for row in lock['openwrt']['changed_files'] if row['path'] == PATCH]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['sha256'], hashlib.sha256(patch.read_bytes()).hexdigest())


if __name__ == '__main__': unittest.main()
