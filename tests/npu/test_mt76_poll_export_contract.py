"""Source-export regression checks;not execution or kernel lifetime proof."""
import ast
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
POLL = 'mt7996/mmio.c'
PATCH = 'package/kernel/mt76/patches/900-w1700k-integrated-npu.patch'


class PollExportContractTests(unittest.TestCase):
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
