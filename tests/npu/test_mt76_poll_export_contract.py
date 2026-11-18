"""Source-export regression checks; not execution or kernel lifetime proof."""
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
    def patched_lines(self, text, name):
        marker = f'--- a/{name}\n+++ b/{name}\n'
        self.assertEqual(text.count(marker), 1)
        section = text.split(marker, 1)[1].split('\n--- a/', 1)[0]
        return ''.join(line[1:] for line in section.splitlines(keepends=True)
                       if line.startswith((' ', '+')))

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
        section = self.patched_lines(text, 'dma.c')
        if 'ret = mt76_npu_alloc_queue_mem(dev, q, size);' in section:
            self.assertIn('if (ret == MT76_NPU_QUEUE_MEM_MANAGED) {', section)
            self.assertIn('} else if (ret) {\n\t\tgoto clear_count;', section)
            npu = self.patched_lines(text, 'npu.c')
            self.assertIn('q->flags == MT_NPU_Q_TXFREE(0)', npu)
            self.assertIn('airoha_npu_wlan_alloc_queue_mem(npu,', npu)
        else:
            self.assertIn('ret = mt76_npu_alloc_rx_event(dev, q);', section)
            self.assertIn('if (ret == -EOPNOTSUPP)\n', section)
            self.assertIn('else if (ret)\n\t\treturn ret;', section)

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
        text = patch.read_text()
        poll = self.patched_lines(text, POLL)
        self.assertIn('int err = mt76_npu_rearm_irq(mdev, q);', poll)
        self.assertIn('if (err && err != -ESHUTDOWN)', poll)
        self.assertNotIn('airoha_npu_wlan_enable_irq(', poll)
        npu = self.patched_lines(text, 'npu.c')
        name = 'int mt76_npu_rearm_irq('
        self.assertEqual(npu.count(name), 1)
        rearm = npu.split(name, 1)[1].split('\n}', 1)[0]
        parts = ['rcu_read_lock();', 'rcu_dereference(dev->mmio.npu);',
                 'spin_lock_irqsave(&dev->mmio.irq_lock, flags);',
                 'if (state->closing)', 'else if (state->error)', 'else if (!state->running)',
                 'err = airoha_npu_wlan_irq_arm(npu, q);',
                 'err = mt76_npu_irq_fault_locked(dev, npu, err);',
                 'spin_unlock_irqrestore(&dev->mmio.irq_lock, flags);',
                 'rcu_read_unlock();', 'return err;']
        cursor = 0
        for part in parts:
            pos = rearm.find(part, cursor)
            self.assertGreaterEqual(pos, 0, part)
            cursor = pos + len(part)
        lock = json.loads((ROOT / 'firmware/source-lock.json').read_bytes())
        rows = [row for row in lock['openwrt']['changed_files'] if row['path'] == PATCH]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['sha256'], hashlib.sha256(patch.read_bytes()).hexdigest())


if __name__ == '__main__': unittest.main()
