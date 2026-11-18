"""Fixture receipts, not firmware execution, board acceptance or a real candidate."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import npu_replay_proof as replay
import seal_npu_image as seal


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else json.dumps(data).encode())
    return replay.digest(path)


@contextmanager
def replace(path, data):
    before = path.read_bytes()
    try:
        yield put(path, data)
    finally:
        path.write_bytes(before)


def make_profile(directory, profile):
    totals = replay.counts(profile)
    total = totals['positive_rpc']
    schedule = {total-6152: 'all-publications', total-3076: 'generation-1',
                total-1: 'generation-2', total: 'closing-retains-all-extents'}
    broker = put(directory / 'broker-final.bin', b'fixture state')
    journal = put(directory / 'oracle-journal-final.bin', b'fixture oracle')
    prefix = put(directory / 'prefix.json', {'fixture': True})
    marker = sha(b'fixture bit pattern')
    rows = []
    for serial, (op, arg, generation) in enumerate(replay.recipe(profile), 1):
        rows.append(dict(operation=op, argument=arg, generation=generation, sequence=serial,
                         journal_sha256=journal, broker_sha256=broker, rolling_sha256=marker,
                         request_sha256=marker, reply_sha256=marker, modeled_MCU_result=op == 7))
        if serial in schedule:
            rows.append(dict(case=schedule[serial], complete_DMA_bytes=12582912, DMA_sha256=marker, native_SRAM_sha256=marker))
    transcript = put(directory / 'rpc.jsonl', ''.join(json.dumps(row)+'\n' for row in rows).encode())
    info = dict(profile=profile, counts=totals, actual_raw_boot=True, modeled_MCU_results=2050,
                whole_cold_setup=False, hardware=False, complete_DMA_sha256=marker, final_broker_sha256=broker,
                final_journal_sha256=journal, rolling_transcript_sha256=marker, prefix_receipt_sha256=prefix)
    summary = put(directory / 'summary.json', info)
    return info, dict(profile=profile, positive_rpc=total, transcript_sha256=transcript, summary_sha256=summary)


class SealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='npu-fixture-seal-')
        cls.addClassCleanup(cls.temp.cleanup)
        root = cls.root = Path(cls.temp.name).resolve()
        local = root / '.local'
        cls.store = root / seal.QUALIFIED
        cls.store.mkdir(parents=True)
        cls.output = local / 'fixture-run'
        matrix = cls.output / 'runs/matrix-r1'
        cls.retained = cls.output / 'retained-inputs'
        cls.control = local / 'fixture-controller'
        cls.terminal = cls.control / 'terminal.json'
        cls.start = root / 'fixture-start.json'
        cls.snapshot = local / 'npu-validation-capsules/fixture/receipt.json'
        cls.frozen = cls.snapshot.parent / 'root'
        pair = local / 'fixture-pair'
        adapter = local / 'adapter.json'
        host = local / 'host.json'
        cls.inputs = inputs = {
            replay.SOURCE_LOCK: put(root / replay.SOURCE_LOCK, dict(kernel='6.18.52')),
            str(adapter.relative_to(root)): put(adapter, b'fixture adapter'),
            str(host.relative_to(root)): put(host, b'fixture host'),
        }
        cls.raw = {key: put(pair / name, f'synthetic {key}'.encode()) for key, name in replay.PAIR_FILES.items()}
        inputs.update({(pair / name).relative_to(root).as_posix(): cls.raw[key] for key, name in replay.PAIR_FILES.items()})
        while len(inputs) < 345:
            n = f'tests/fixture-{len(inputs)}'
            inputs[n] = put(root / n, b'fixture source')
        for name in inputs:
            for directory in (cls.retained, cls.frozen):
                put(directory / name, (root / name).read_bytes())
                (directory / name).chmod(0o444)
        invocation, boot, head = '1'*32, 'fixture-boot', '2'*40
        phase = dict(unit='fixture.service', output=str(cls.output))
        plan = put(cls.control / 'plan.json', dict(boot=boot, head=head, old_transcripts_used=False, runtime_bindings=330,
                                                  phases={'full-a': phase}, inputs=inputs))
        prep = put(cls.output / 'prepared.json', dict(boot=boot, invocation=invocation, head=head, plan=plan, from_reset=True,
            earlier_profile_outputs_used=False, retained_plan_inputs=345, runtime_bindings=330,
            command=['/usr/bin/python3','-u','-B',str(root/'tests/npu/test_rro_wire_native_pair.py'),'--pair',str(pair),
                     '--host-evidence',str(host),'--name','matrix-r1','--output-root',str(cls.output/'runs'),
                     '--native-cold-receipt',str(adapter)]))
        cls.start_pin = put(cls.start, dict(source_commit=head, private_plan_input_count=345, qualified_runtime_input_count=330,
            prior_results_stitched=False, observation=dict(invocation=invocation, boot=boot, expected_boot=boot, status='live',
            observed_unix_ns=1000, unit=dict(InvocationID=invocation)), private_receipts={'plan.json':plan,'prepared.json':prep},
            windows_wait_client={'unit':phase['unit']}))
        profiles, summaries = zip(*(make_profile(matrix / f'profile-{i}', i) for i in range(3)))
        cls.profiles = profiles
        totals = {key: sum(row['counts'][key] for row in profiles) for key in profiles[0]['counts']}
        cls.matrix = matrix
        artifacts = {p.relative_to(root).as_posix(): replay.digest(p) for p in matrix.rglob('*') if p.is_file()}
        matrix_pin = put(matrix / 'result.json', dict(passed=True, artifacts=artifacts, profiles=profiles, counts=totals,
            inputs=inputs, native_cold_adapter=dict(cold_observer_API=8, build_receipt=adapter.relative_to(root).as_posix(),
                build_receipt_sha256=inputs[adapter.relative_to(root).as_posix()], per_engine_GIL_attached_emulation=True,
                instruction_and_timeout_limits_unchanged=True),
            host_evidence_sha256=inputs[host.relative_to(root).as_posix()],
            per_RPC_limits=dict(instructions=100000000,timeout_us=60000000,unique_exact_blocks=16384),
            raw_boot_limits=dict(instructions_per_run=3000000,timeout_us=10000000),
            actual_raw_pair=True, actual_raw_boots=3, actual_mailbox_broker=True, hardware=False, whole_cold_setup=False,
            physical_IRQ_entry=False, physical_retirement=False, MCU_authenticated=False))
        result = put(cls.output / 'result.json', dict(passed=True, invocation=invocation, plan=plan, matrix_sha256=matrix_pin,
            profiles=summaries, counts=totals, from_reset=True, hardware=False, physical_retirement=False))
        controller = put(cls.control/'full-a-controller.json', dict(passed=True, invocation=invocation, boot=boot, plan=plan,
            phase='full-a', returncode=0, breach=False, hardware=False, result=result))
        cls.terminal_row = dict(passed=True, service_result='success', exit_code='exited', exit_status='0',
                                invocation=invocation, boot=boot, plan=plan, controller_sha256=controller,
                                observed_unix_ns=2000)
        cls.terminal_pin = put(cls.terminal, cls.terminal_row)

        # Synthetic combined ELF headers exercise the same source/artifact resolver as a real world.
        prod = cls.frozen / '.local/fixture-producer/result.json'
        linked_inputs = {replay.SOURCE_LOCK: inputs[replay.SOURCE_LOCK]}
        for label in ('kernel', 'mt76'):
            n = f'.local/merge-nonoc-20260923/{label}-merged/fixture.c'
            linked_inputs[n] = put(cls.frozen/n, b'synthetic source')
        asm = b'\x7fELF\x02\x01' + bytes(10) + b'\x01\x00\xb7\x00'
        art, package, module_hashes = {}, {}, {}
        cls.declarations = inputs | linked_inputs
        for name in ('airoha_npu.ko', 'mt76/mt76.ko','mt76/mt76-connac-lib.ko','mt76/mt7996/mt7996e.ko'):
            file = prod.parent / name
            pin = put(file, asm)
            cls.declarations[file.relative_to(cls.frozen).as_posix()] = pin
            art[name] = dict(sha256=pin, bytes=len(asm), vermagic='6.18.52 SMP mod_unload aarch64')
            label = file.name
            modpin = sha(label.encode())
            module_hashes[label] = modpin
            package[label] = dict(matches=True, linked_sha256=pin, actual_packaged_sha256=modpin,
                                  expected_packaged_sha256=modpin)
        producer_name = prod.relative_to(cls.frozen).as_posix()
        producer_pin = put(prod, dict(passed=True, returncode=0, originals_unchanged=True, inputs=linked_inputs,
            inner=dict(passed=True, current_checked_header_compiled=True, image_built=False, hardware=False,
            module_loaded=False,provider=art.pop('airoha_npu.ko'),modules={k.removeprefix('mt76/'):v for k,v in art.items()})))
        cls.declarations[producer_name] = producer_pin
        snapshot_pin = put(cls.snapshot,dict(format='npu-validation-capsule-v1',preservation_verified=True,sources_read_only=True,
            source_root=str(root), input_root=str(cls.frozen), source_commit=head, tracked_dirty=False, files=cls.declarations))
        cls.world = local / 'fixture-world/result.json'
        directory = cls.world.parent
        cls.fit = directory / 'build-upper' / seal.IMAGE_PATH
        cls.fit_bytes = b'not an image; unit test uses an independent reader result'
        cls.fit_pin = put(cls.fit, cls.fit_bytes)
        fmt = dict(fit_configuration={'name':'fixture-default'}, components=[], model='fixture', compatible='gemtek,w1700k-ubi',
                   pair={k:dict(sha256=v) for k,v in cls.raw.items() if k != 'manifest'} | dict(manifest_sha256='f'*64),
                   module_sha256=module_hashes)
        cls.packed = fmt
        img = {k:fmt[k] for k in ('fit_configuration','components','model','compatible')} | dict(
            passed=True, source_lock_sha256=inputs[replay.SOURCE_LOCK], image=f'{seal.BUILD}/{seal.IMAGE_PATH}', bytes=len(cls.fit_bytes),
            sha256=cls.fit_pin, pinned_module_bytes_verified=True, checked_npu_pair=fmt['pair'],
            selected_modules={k:dict(sha256=v) for k,v in module_hashes.items()},
            packaged_module_provenance=dict(producer=producer_name, producer_sha256=producer_pin, matches=True, mismatches=[],
                                           source_lock_sha256=inputs[replay.SOURCE_LOCK], modules=package))
        imgpin = put(directory/'log-upper/fixture-image/result.json', img)
        cls.world_row = dict(passed=True, returncode=0, world_build=True, snapshot_unchanged=True, parent_namespaces_unchanged=True,
                original_build_content_modes_ownership_links_unchanged=True,
                original_download_cache_content_modes_ownership_links_unchanged=True,
                host_timeout=False, probe_only=False, hardware=False, module_loaded=False, physical_image=str(cls.fit),
                physical_image_sha256=cls.fit_pin,
                envelope=dict(network_isolated=True, physical_output_root=str(directory), protected_lower_build=str(root/seal.BUILD),
                          source_lock_sha256=inputs[replay.SOURCE_LOCK], snapshot_source_commit=head, snapshot_receipt_sha256=snapshot_pin),
                child=dict(world_build=True, passed=True, hardware=False, critical_kernel_modules_and_RV32_cleaned=True,
                       proof=dict(root_readonly=True,producer_view_readonly=True),image_verification=img,
                       image_verification_sha256=imgpin,image_verification_receipt=f'{seal.LOGS}/fixture-image/result.json'))
        cls.world_pin = put(cls.world, cls.world_row)

    def args(self, name, **changes):
        return SimpleNamespace(**(dict(name=name, start=self.start, start_sha256=self.start_pin, snapshot=self.snapshot,
            terminal=self.terminal, terminal_sha256=self.terminal_pin, world_result=self.world, world_sha256=self.world_pin) | changes))

    def verify_replay(self):
        return replay.verify_replay(self.root, self.start, self.start_pin, self.terminal, self.terminal_pin,
                                    self.frozen, self.declarations)

    def test_complete_replay_and_world_publish_one_exact_readonly_candidate(self):
        with patch.object(seal, 'inspect_fit_pair', return_value=self.packed) as inspect:
            receipt = seal.seal(self.root, self.args('fixture-positive'))
        old_stage = inspect.call_args.args[0]
        self.assertFalse(old_stage.exists())
        self.assertEqual(inspect.call_args.args[3], self.raw)
        row, _ = replay.read_receipt(receipt)
        fit = receipt.parent / row['image']
        self.assertEqual(fit.read_bytes(), self.fit_bytes)
        self.assertEqual(row['replay']['positive_rpc'], 19261)
        self.assertEqual(row['replay']['start_sha256'], self.start_pin)
        self.assertEqual(row['replay']['reverified_inputs'], 345)
        self.assertEqual([p['positive_rpc'] for p in row['replay']['profiles']], [6421,6421,6419])
        self.assertNotEqual(row['packaged']['pair']['manifest_sha256'], row['replay']['pair']['manifest'])
        self.assertFalse(fit.stat().st_mode & 0o222 or receipt.stat().st_mode & 0o222)
        self.assertFalse(any(row[k] for k in ('boot_verified','physical_retirement','hardware','flash_authorized')))
        self.assertEqual(self.fit.read_bytes(), self.fit_bytes)
        with self.assertRaisesRegex(ValueError,'already exists'):
            seal.seal(self.root,self.args('fixture-positive'))
        self.assertEqual(fit.read_bytes(), self.fit_bytes)

    def test_roster_recheck_is_explicit_and_still_requires_a_terminal_replay(self):
        original = self.world_row['child']
        failed = self.world_row | dict(passed=False, world_build=False, returncode=1, child=None)
        proof = dict(original_wrapper_passed=False, original_wrapper_returncode=1)
        with replace(self.world, failed) as pin, \
             patch('npu_world_postflight.recheck', return_value=(
                 original['image_verification'], original['image_verification_sha256'], proof)) as recheck, \
             patch.object(seal, 'inspect_fit_pair', return_value=self.packed):
            with self.assertRaisesRegex(ValueError, 'Not a passing isolated world'):
                seal.seal(self.root, self.args('fixture-recheck', world_sha256=pin))
            recheck.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'Receipt digest mismatch'):
                seal.seal(self.root, self.args('fixture-recheck', world_sha256=pin,
                                              recover_rv32_roster=True, terminal_sha256='0' * 64))
            self.assertFalse((self.store / 'fixture-recheck').exists())
            receipt = seal.seal(self.root, self.args('fixture-recheck', world_sha256=pin, recover_rv32_roster=True))
            self.assertEqual(replay.digest(self.world), pin)
        row, _ = replay.read_receipt(receipt)
        self.assertEqual(row['world_postflight'], proof)
        self.assertEqual(row['world_sha256'], pin)
        self.assertTrue(row['rv32_emulator_replay_bound'])
        self.assertFalse(row['flash_authorized'])

    def test_ethernet_enabled_seal_uses_five_modules_and_no_fallback(self):
        name = seal.npu_ethernet_fit.ETH_MODULE
        eth_pin = "7" * 64
        evidence = dict(expected_packaged_sha256=eth_pin, linked_sha256="8" * 64)
        with patch.object(seal.npu_ethernet_fit, 'bind_linked', return_value=evidence), \
             patch.object(seal, 'inspect_fit_pair') as inspect:
            for bad in (self.packed['module_sha256'],
                        self.packed['module_sha256'] | {name: "9" * 64}):
                inspect.return_value = self.packed | dict(module_sha256=bad)
                with self.assertRaisesRegex(ValueError, 'FIT Ethernet module differs'):
                    seal.seal(self.root, self.args('fixture-ethernet-fail'))
                self.assertFalse((self.store/'fixture-ethernet-fail').exists())
            modules = self.packed['module_sha256'] | {name: eth_pin}
            inspect.return_value = self.packed | dict(module_sha256=modules | {'mt76.ko': '6' * 64})
            with self.assertRaisesRegex(ValueError, 'four qualified modules'):
                seal.seal(self.root, self.args('fixture-ethernet-fail'))
            self.assertFalse((self.store/'fixture-ethernet-fail').exists())
            inspect.return_value = self.packed | dict(module_sha256=modules)
            receipt = seal.seal(self.root, self.args('fixture-ethernet-pass'))
        row, _ = replay.read_receipt(receipt)
        self.assertEqual(set(inspect.call_args.args[4]), set(modules))
        self.assertEqual(row['ethernet']['actual_packaged_sha256'], eth_pin)
        self.assertEqual(row['packaged']['module_sha256'], modules)
        self.assertFalse(row['hardware'])

    def test_missing_terminal_cannot_publish_even_if_image_and_prefix_exist(self):
        with patch.object(seal, 'verify_world') as world:
            with self.assertRaisesRegex(ValueError, 'no terminal receipt'):
                seal.seal(self.root,self.args('fixture-wait',terminal=self.control/'missing.json'))
        world.assert_not_called()
        self.assertFalse((self.store/'fixture-wait').exists())

    def test_terminal_of_other_invocation_or_failed_run_does_not_qualify(self):
        for defect in (dict(invocation='d'*32),dict(boot='wrong-boot'),dict(passed=False),
                       dict(service_result='timeout'),dict(exit_status='1'),dict(plan='0'*64),dict(observed_unix_ns=999)):
            with self.subTest(defect=defect), replace(self.terminal,self.terminal_row | defect) as pin:
                with self.assertRaisesRegex(ValueError,'terminal gate'):
                    seal.seal(self.root,self.args('fixture-invalid-terminal',terminal_sha256=pin))
        self.assertFalse((self.store/'fixture-invalid-terminal').exists())

    def test_pins_are_required_not_just_receipt_filenames(self):
        for impact in (dict(start_sha256='b'*64),dict(terminal_sha256='b'*64),dict(world_sha256='b'*64)):
            with self.subTest(impact=impact), self.assertRaisesRegex(ValueError,'Receipt digest mismatch'):
                seal.seal(self.root,self.args('fixture-wrong-pin',**impact))

    def test_missing_replay_map_entry_or_writable_copy_is_rejected(self):
        f = 'tests/fixture-344'
        with self.assertRaisesRegex(ValueError,'does not bind replay input'):
            replay.verify_replay(self.root,self.start,self.start_pin,self.terminal,self.terminal_pin,self.frozen,
                                 {k:v for k,v in self.declarations.items() if k!=f})
        protected = self.retained/f
        protected.chmod(0o644)
        try:
            with self.assertRaisesRegex(ValueError,'Replay input drift'):
                self.verify_replay()
        finally:
            protected.chmod(0o444)

    def test_failure_or_extra_matrix_artifact_cannot_be_ignored(self):
        failure = self.matrix/'failure.json'
        put(failure,dict(fixture=True))
        try:
            with self.assertRaisesRegex(ValueError,'Different matrix artifact set'):
                self.verify_replay()
        finally:
            failure.unlink()

    def test_profile_checks_order_memory_placement_and_final_state(self):
        p = self.matrix/'profile-0'
        rows = (p/'rpc.jsonl').read_bytes().splitlines(keepends=True)
        bad = rows.copy()
        bad[1], bad[2] = bad[2], bad[1]
        memory = next(i for i,line in enumerate(rows) if b'all-publications' in line)
        misplaced = rows.copy()
        misplaced[memory], misplaced[memory-1] = misplaced[memory-1], misplaced[memory]
        for change, message in ((bad,'Unordered'),(misplaced,'full-memory schedule'),(rows[:-1],'full-memory schedule')):
            with self.subTest(message=message), replace(p/'rpc.jsonl',b''.join(change)), self.assertRaisesRegex(ValueError,message):
                replay.verify_profile(p,0,self.profiles[0])
        with replace(p/'broker-final.bin',b'not same'), self.assertRaisesRegex(ValueError,'final state'):
            replay.verify_profile(p,0,self.profiles[0])

    def test_probe_only_world_cannot_qualify(self):
        with replace(self.world,self.world_row | dict(probe_only=True)) as pin:
            with self.assertRaisesRegex(ValueError,'passing isolated world'):
                seal.seal(self.root,self.args('fixture-probe',world_sha256=pin))

    def test_image_verifier_receipt_must_exist_and_match(self):
        p = self.world.parent/'log-upper/fixture-image/result.json'
        with replace(p,{'passed':True}), self.assertRaisesRegex(ValueError,'Receipt digest mismatch'):
            seal.seal(self.root,self.args('fixture-unmatched'))

    def test_a_late_patch_world_must_publish_the_exact_prepared_source_proof(self):
        proof = dict(kernel_patch_files=9, component_sources=31, mt76_source_files=330,
                     source_contract_sha256='b'*64, patch_orders={'kernel': ['integrated', 'late']})
        with patch.object(seal.npu_world_sources, 'has_late_module_patches', return_value=True), \
             patch('npu_successor_sources.world_contract', return_value=({'staged_bundle_sha256': 'c'*64}, proof)):
            with self.assertRaisesRegex(ValueError, 'lacks the exact successor prepared-source proof'):
                seal.verify_world(self.root, self.world, self.world_pin, self.snapshot)
            child = self.world_row['child'] | dict(prepared_sources_verified=proof)
            with replace(self.world, self.world_row | dict(child=child)) as pin:
                world = seal.verify_world(self.root, self.world, pin, self.snapshot)
        self.assertEqual(world['source_contract_sha256'], 'b'*64)
        self.assertEqual(world['staged_bundle_sha256'], 'c'*64)

    def test_fit_is_copied_by_digest_not_name_or_size(self):
        with replace(self.fit,b'x'*len(self.fit_bytes)), patch.object(seal,'inspect_fit_pair') as inspect:
            with self.assertRaisesRegex(ValueError,'FIT bytes differ'):
                seal.seal(self.root,self.args('fixture-drift'))
        inspect.assert_not_called()
        self.assertFalse((self.store/'fixture-drift').exists())

    def test_selected_packaged_payload_must_match_both_receipts(self):
        world = seal.verify_world(self.root,self.world,self.world_pin,self.snapshot)
        for changed, message in ((self.packed | dict(fit_configuration={'name':'other'}),'FIT fit_configuration'),
              (self.packed | dict(module_sha256={}),'four qualified modules'),
              (self.packed | dict(pair=self.packed['pair'] | dict(manifest_sha256='e'*64)),'pair differs from the world')):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError,message):
                seal.bind_packaged(changed,world,dict(pair=self.raw))
        for part in ('code','data'):
            with self.subTest(part=part), self.assertRaisesRegex(ValueError, part.upper()+' differs from the replay'):
                seal.bind_packaged(self.packed,world,dict(pair=self.raw | {part:'e'*64}))

    def test_name_collision_during_publication_does_not_replace_destination(self):
        output = self.store/'fixture-concurrent'
        def inspect(*args):
            output.mkdir()
            put(output/'owner.txt',b'existing')
            return self.packed
        with patch.object(seal,'inspect_fit_pair',side_effect=inspect), self.assertRaises(FileExistsError):
            seal.seal(self.root,self.args('fixture-concurrent'))
        self.assertEqual({f.name for f in output.iterdir()},{'owner.txt'})

    def test_interrupted_publication_never_writes_the_completion_marker(self):
        # Simulate interruption between the two atomic links without changing real files.
        real_link = seal.os.link
        def after_fit(*args, **kwargs):
            if args[1] == 'receipt.json':
                raise OSError('simulated interruption')
            return real_link(*args, **kwargs)
        with (patch.object(seal, 'inspect_fit_pair', return_value=self.packed),
              patch.object(seal.os, 'link', side_effect=after_fit), self.assertRaisesRegex(OSError, 'simulated interruption')):
            seal.seal(self.root, self.args('fixture-interrupted'))
        partial = self.store/'fixture-interrupted'
        self.assertEqual({f.name for f in partial.iterdir()},{self.fit_pin+'.itb'})
        self.assertFalse((partial/'receipt.json').exists())

    def test_symlinked_rootfs_leaf_is_not_a_regular_selected_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            scratch = root / 'scratch'
            scratch.mkdir()
            paths = {role:root/role for role in ('fdt','rootfs')}
            def fake_extract(argv):
                selected = scratch/'selected-rootfs'
                target = selected/seal.FIT_PAIR_FILES['code']
                target.parent.mkdir(parents=True)
                put(selected/'another.bin',b'symlink target')
                target.symlink_to(selected/'another.bin')
            with (patch.object(seal.fit_tools,'extract_fit_components',return_value=({},[],paths)),
                  patch.object(seal.fit_tools,'board_identity',return_value=('fixture','fixture')),
                  patch.object(seal.fit_tools,'run',side_effect=fake_extract),
                  self.assertRaisesRegex(ValueError,'aliased path')):
                seal.inspect_fit_pair(root/'not-used',scratch,'6.18.52',self.raw)


if __name__ == '__main__':
    unittest.main()
