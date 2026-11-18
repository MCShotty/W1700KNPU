"""Exercise the successor replay's source selection and cross-stage bindings."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import npu_replay_proof as proof
import npu_successor_replay as replay


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return proof.digest(path)


class SuccessorReplayTests(unittest.TestCase):
    def plan(self):
        runtime = {f'input-{i}': f'{i:064x}' for i in range(330)}
        name = '.local/npu-successor-modules/new/result.json'
        result = dict(format=proof.SUCCESSOR_PLAN, runtime_bindings=330, runtime_inputs=runtime,
                      capsule_sha256='c'*64, source_lock_sha256='d'*64, source_contract_sha256='e'*64,
                      producer=name, producer_sha256='f'*64, config_sha256='1'*64,
                      launcher_sha256='2'*64, checker_sha256='3'*64, bwrap_sha256='4'*64)
        result['inputs'] = runtime | {proof.SOURCE_LOCK: result['source_lock_sha256'],
                    proof.SUCCESSOR_CONTRACT: result['source_contract_sha256'],
                    name: result['producer_sha256'], 'firmware/build.config': result['config_sha256'],
                    proof.REPLAY_LAUNCHER: result['launcher_sha256'],
                    proof.REPLAY_CHECKER: result['checker_sha256'], proof.REPLAY_BWRAP: result['bwrap_sha256']}
        return result

    def test_successor_requires_exact_input_map(self):
        plan = self.plan()
        self.assertEqual(proof.plan_cohort(plan)['producer_sha256'], plan['producer_sha256'])
        for name in (proof.SUCCESSOR_CONTRACT, plan['producer'], 'input-2'):
            with self.subTest(name=name):
                changed = dict(plan, inputs=plan['inputs'] | {name: 'b'*64})
                with self.assertRaisesRegex(ValueError, 'membership or control'):
                    proof.plan_cohort(changed)
        with self.assertRaisesRegex(ValueError, 'membership or control'):
            proof.plan_cohort(dict(plan, inputs=plan['inputs'] | {'extra': 'a'*64}))

    def test_legacy_does_not_qualify_the_successor_world(self):
        plan = self.plan()
        cohort = proof.plan_cohort(plan) | {'source_lock_sha256': plan['source_lock_sha256']}
        proof.bind_world_replay(cohort, plan['source_lock_sha256'], plan['producer_sha256'], plan['source_contract_sha256'])
        with self.assertRaisesRegex(ValueError, 'producer differ'):
            proof.bind_world_replay({'source_lock_sha256': plan['source_lock_sha256']},
                plan['source_lock_sha256'], plan['producer_sha256'], plan['source_contract_sha256'])
        with self.assertRaisesRegex(ValueError, 'producer differ'):
            proof.bind_world_replay(cohort, plan['source_lock_sha256'], '1'*64, plan['source_contract_sha256'])

    def test_copy_picks_new_driver_and_keeps_legacy_profiles_out(self):
        with TemporaryDirectory(prefix='rv32-cohort-fixture-') as directory:
            root = Path(directory)
            reuse = dict(root=root / 'baseline', files={})
            required = ['tests/npu/raw.py', '.build/merged-openwrt/target/linux/generic/kernel-6.18',
                        proof.REPLAY_BWRAP, '.build/openwrt/dl/cache', '.local/old-output/profile-0/rpc.jsonl']
            for name in required:
                reuse['files'][name] = put(reuse['root'] / name, name.encode())
            authority = root / 'authority'
            key = '.local/merge-nonoc-20260923/mt76-merged/npu.c'
            producer = '.local/npu-successor-modules/a/result.json'
            checked = dict(inputs={key: put(authority / key, b'new driver')},
                           artifacts={}, receipt=producer, receipt_sha256=put(authority / producer, b'new producer'))
            tracked = {proof.SOURCE_LOCK: put(root / proof.SOURCE_LOCK, b'promoted')}
            files, chosen = replay.map_sources(tracked, {'tests/npu/raw.py': reuse['files']['tests/npu/raw.py']},
                reuse, authority, checked, {'files': tracked}, '6.18.52')
            self.assertEqual(chosen[key], authority / key)
            self.assertEqual(chosen[producer], authority / producer)
            self.assertNotIn(required[-1], files)
            with self.assertRaisesRegex(ValueError, 'tracked source'):
                replay.map_sources(tracked, {}, reuse, authority, checked,
                                   {'files': {'firmware/other': 'a'*64}}, '6.18.52')

    def test_selected_copy_can_preserve_old_same_named_file(self):
        with TemporaryDirectory(prefix='rv32-selected-fixture-') as directory:
            root = Path(directory)
            canonical = put(root / 'module', b'baseline')
            candidate = root / 'authority/module'
            expected = put(candidate, b'successor')
            with self.assertRaisesRegex(AssertionError, 'pre-copy-drift'):
                replay.capsule.copy_files(root, root / 'dest', {'module': expected})
            replay.capsule.copy_files(root, root / 'dest', {'module': expected}, selected_sources={'module': candidate})
            self.assertEqual(proof.digest(root / 'dest/module'), expected)
            self.assertEqual(proof.digest(root / 'module'), canonical)
            self.assertFalse((root / 'dest/module').stat().st_mode & 0o222)


if __name__ == '__main__':
    unittest.main()
