"""Actual C/RV32 byte-snapshot guards; not a native constructor proof."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from unicorn import UC_HOOK_CODE, riscv_const as r
from test_barrier_protocol import Rv32

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'firmware/npu'
HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InodePlanSnapshotTests(unittest.TestCase):
    def test_full_byte_boundaries_and_independent_guard_mutants(self):
        paths = [Path(__file__), HERE / 'inode-plan-snapshot-fixture.c',
            HERE / 'inode-plan-snapshot.ld', HERE / 'test_barrier_protocol.py',
            CORE / 'cold-inode.c', *CORE.glob('*.h')]
        inputs = {str(path.relative_to(ROOT)): digest(path) for path in paths}
        store = ROOT / '.local/npu-inode-plan-snapshot'
        store.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix='guards-', dir=store))
        source = (CORE / 'cold-inode.c').read_text()
        variants = {
            'nominal': (None, None, 378),
            'missing-before': (
                'return equal(p, held, sizeof(*p)) &&\n           c->read',
                'return c->read', 1),
            'missing-after': (
                'c->read(c->opaque, address, bytes, value) &&\n           equal(p, held, sizeof(*p));',
                'c->read(c->opaque, address, bytes, value);', 189)
        }
        rows = []
        for variant, (before, after, cases) in variants.items():
            work = directory / variant
            work.mkdir()
            contents = source
            if before is not None:
                self.assertEqual(source.count(before), 1)
                contents = source.replace(before, after)
            staged = work / 'cold-inode.c'
            staged.write_text(contents)
            common = [shutil.which('clang'), '-std=c11', '-O2', '-g',
                '-Wall', '-Wextra', '-Werror', '-fno-builtin',
                '-ffunction-sections', '-fdata-sections', '-I' + str(work),
                '-I' + str(CORE), str(HERE / 'inode-plan-snapshot-fixture.c')]
            host, elf = work / 'host', work / 'guard.elf'
            commands = [common + ['-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                '-Wl,--gc-sections', '-o', str(host)],
                common + ['--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
                '-nostdlib', '-fno-stack-protector', '--ld-path=' + str(shutil.which('ld.lld') or
                    ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
                '-Wl,--gc-sections,--no-relax,-T,' + str(HERE / 'inode-plan-snapshot.ld'),
                '-o', str(elf)]]
            for number, command in enumerate(commands):
                completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
                (work / ('build-' + str(number) + '.log')).write_text(completed.stdout + completed.stderr)
                self.assertEqual(completed.returncode, 0, completed.stderr)
            host_run = subprocess.run([str(host)], capture_output=True, text=True, timeout=30,
                env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1'))
            (work / 'host-run.log').write_text(host_run.stdout + host_run.stderr)
            self.assertNotIn('AddressSanitizer', host_run.stderr)
            self.assertNotIn('runtime error:', host_run.stderr)
            self.assertEqual(host_run.returncode == 0, variant == 'nominal')
            rv = Rv32(elf)
            cpu = rv.cpu
            cpu.reg_write(r.UC_RISCV_REG_SP, 0x84100000)
            cpu.reg_write(r.UC_RISCV_REG_RA, 0x84200000)
            instructions = [0]

            def observed(cpu_, pc, size, unused):
                instructions[0] += 1

            hook = cpu.hook_add(UC_HOOK_CODE, observed)
            cpu.emu_start(rv.symbols['npu_test_snapshot_all'], 0x84200000,
                count=3000000, timeout=60000000)
            cpu.hook_del(hook)
            self.assertEqual(cpu.reg_read(r.UC_RISCV_REG_PC), 0x84200000)
            self.assertEqual(cpu.reg_read(r.UC_RISCV_REG_SP), 0x84100000)
            returned = cpu.reg_read(r.UC_RISCV_REG_A0)
            self.assertEqual(returned == 0, variant == 'nominal')
            count = int.from_bytes(cpu.mem_read(rv.symbols['npu_test_snapshot_cases'], 4), 'little')
            self.assertEqual(count, cases)
            rows.append(dict(variant=variant, cases_before_return=count,
                host_returncode=host_run.returncode, RV32_return_value=returned,
                RV32_instructions=instructions[0], source_sha256=digest(staged),
                host_sha256=digest(host), RV32_sha256=digest(elf), commands=commands))
        self.assertTrue(all(digest(ROOT / name) == expected for name, expected in inputs.items()))
        artifacts = {str(path.relative_to(ROOT)): digest(path)
            for path in directory.rglob('*') if path.is_file()}
        result = dict(passed=True, rows=rows, inputs=inputs, artifacts=artifacts,
            predicate_cases=378, plan_bytes=188, independent_mutants=2,
            address_undefined_leak_sanitizers=True, native_limits_changed=False,
            full_constructor_executed=False, geometry_validation_proved=False, hardware=False,
            limits=['Only the exact byte-snapshot read predicate is executed over synthetic byte-pattern plans.',
                'The complete plan must be independently geometry-validated before using this predicate.',
                'Neither cold constructor progress nor physical exclusion follows from these unit tests.'])
        with (directory / 'result.json').open('x') as stream:
            stream.write(json.dumps(result, indent=2) + '\n')
        print(json.dumps(dict(snapshot_predicate_cases=378, host_and_RV32_mutants=2,
            receipt=str((directory / 'result.json').relative_to(ROOT)), hardware=False)), flush=True)


if __name__ == '__main__':
    unittest.main()
