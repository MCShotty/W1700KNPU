"""Actual C/RV32 byte-snapshot guards; not a native constructor proof."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, riscv_const as r
from test_barrier_protocol import Rv32

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'firmware/npu'
HERE = Path(__file__).resolve().parent
CAPTURE_COST_TARGET = 2000000


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
        unrolled = '''    uint32_t i = 0;

    /* Retain byte-width volatile reads while amortizing loop control. */
    for (; bytes - i >= 4; i += 4)
        if (x[i] != y[i] || x[i + 1] != y[i + 1] ||
            x[i + 2] != y[i + 2] || x[i + 3] != y[i + 3])
            return 0;
    for (; i < bytes; i++)'''
        bytewise = '    for (uint32_t i = 0; i < bytes; i++)'
        variants = {
            'nominal': (None, None, 378),
            'missing-before': (
                'return equal(p, held, sizeof(*p)) &&\n           c->read',
                'return c->read', 1),
            'missing-after': (
                'c->read(c->opaque, address, bytes, value) &&\n           equal(p, held, sizeof(*p));',
                'c->read(c->opaque, address, bytes, value);', 189),
            'bytewise-cost': (unrolled, bytewise, 378)
        }
        rows = []
        for variant, (before, after, cases) in variants.items():
            guard_mutant = variant in ('missing-before', 'missing-after')
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
            self.assertEqual(host_run.returncode == 0, not guard_mutant)
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
            self.assertEqual(returned == 0, not guard_mutant)
            count = int.from_bytes(cpu.mem_read(rv.symbols['npu_test_snapshot_cases'], 4), 'little')
            self.assertEqual(count, cases)
            rows.append(dict(variant=variant, cases_before_return=count,
                host_returncode=host_run.returncode, RV32_return_value=returned,
                RV32_instructions=instructions[0], source_sha256=digest(staged),
                host_sha256=digest(host), RV32_sha256=digest(elf), commands=commands))
            if not guard_mutant:
                capture_rv = Rv32(elf)
                capture_cpu = capture_rv.cpu
                capture_cpu.reg_write(r.UC_RISCV_REG_SP, 0x84100000)
                capture_cpu.reg_write(r.UC_RISCV_REG_RA, 0x84200000)
                capture_instructions = [0]

                def capture_observed(cpu_, pc, size, unused):
                    capture_instructions[0] += 1

                capture_hook = capture_cpu.hook_add(UC_HOOK_CODE, capture_observed)
                capture_cpu.emu_start(capture_rv.symbols['npu_test_capture_all'], 0x84200000,
                    count=3000000, timeout=60000000)
                capture_cpu.hook_del(capture_hook)
                captured = int.from_bytes(capture_cpu.mem_read(
                    capture_rv.symbols['npu_test_capture_count'], 4), 'little')
                capture = dict(scope='synthetic-plan-read-predicate-full-preimage-loop-not-full-constructor',
                    passed=capture_cpu.reg_read(r.UC_RISCV_REG_PC) == 0x84200000 and
                        capture_cpu.reg_read(r.UC_RISCV_REG_A0) == 0 and captured == 1030,
                    pc=hex(capture_cpu.reg_read(r.UC_RISCV_REG_PC)), captured=captured,
                    instructions=capture_instructions[0], instruction_limit=3000000, timeout_us=60000000,
                    predicate_cost_target=CAPTURE_COST_TARGET,
                    headroom_satisfied=capture_instructions[0] <= CAPTURE_COST_TARGET,
                    expected_headroom_satisfied=variant == 'nominal',
                    full_constructor_executed=False, geometry_validation_proved=False, hardware=False)
                with (work / 'capture-observed.json').open('x') as stream:
                    stream.write(json.dumps(capture, indent=2) + '\n')
                self.assertEqual(capture_cpu.reg_read(r.UC_RISCV_REG_PC), 0x84200000, capture)
                self.assertEqual(capture_cpu.reg_read(r.UC_RISCV_REG_SP), 0x84100000)
                self.assertEqual(capture_cpu.reg_read(r.UC_RISCV_REG_A0), 0)
                self.assertEqual(captured, 1030)
                self.assertEqual(capture['headroom_satisfied'], variant == 'nominal', capture)
                self.assertEqual(bytes(capture_cpu.mem_read(capture_rv.symbols['npu_test_capture_before'],
                    1030 * 4)), (0x12345678).to_bytes(4, 'little') * 1030)
                rows[-1]['capture'] = capture
            if variant == 'nominal':
                boundary_rv = Rv32(elf)
                boundary_cpu = boundary_rv.cpu
                left, right = (boundary_rv.symbols[name] for name in ('compare_left', 'compare_right'))
                running = boundary_rv.symbols['npu_test_compare_running']
                reads = []

                def comparison_read(cpu_, access, address, size, value, unused):
                    if int.from_bytes(cpu_.mem_read(running, 4), 'little'):
                        reads.append((address, size))

                hooks = [boundary_cpu.hook_add(UC_HOOK_MEM_READ, comparison_read,
                    begin=base, end=base + 4376 - 1) for base in (left, right)]
                boundaries = []
                try:
                    for offset in range(4):
                        for length in (*range(10), 188, 4372):
                            for changed in sorted({0, length // 2, max(0, length - 1), length}):
                                reads.clear()
                                for reg, value in zip((r.UC_RISCV_REG_A0, r.UC_RISCV_REG_A1,
                                        r.UC_RISCV_REG_A2), (offset, length, changed)):
                                    boundary_cpu.reg_write(reg, value)
                                boundary_cpu.reg_write(r.UC_RISCV_REG_SP, 0x84100000)
                                boundary_cpu.reg_write(r.UC_RISCV_REG_RA, 0x84200000)
                                boundary_cpu.emu_start(boundary_rv.symbols['npu_test_equal_boundary'],
                                    0x84200000, count=3000000, timeout=60000000)
                                self.assertEqual(boundary_cpu.reg_read(r.UC_RISCV_REG_PC), 0x84200000)
                                self.assertEqual(boundary_cpu.reg_read(r.UC_RISCV_REG_A0), 0)
                                self.assertEqual(boundary_cpu.reg_read(r.UC_RISCV_REG_SP), 0x84100000)
                                prefix = min(length, changed + 1)
                                expected_reads = [(base + offset + i, 1)
                                    for base in (left, right) for i in range(prefix)]
                                self.assertEqual(sorted(reads), sorted(expected_reads), (offset, length, changed))
                                boundaries.append(dict(offset=offset, bytes=length, changed=changed,
                                    exact_byte_reads=len(reads)))
                finally:
                    for hook in hooks:
                        boundary_cpu.hook_del(hook)
                rows[-1]['comparison_boundaries'] = boundaries
        self.assertTrue(all(digest(ROOT / name) == expected for name, expected in inputs.items()))
        artifacts = {str(path.relative_to(ROOT)): digest(path)
            for path in directory.rglob('*') if path.is_file()}
        result = dict(passed=True, rows=rows, inputs=inputs, artifacts=artifacts,
            predicate_cases=378, plan_bytes=188, independent_mutants=2,
            cost_regression_controls=1, predicate_cost_target=CAPTURE_COST_TARGET,
            address_undefined_leak_sanitizers=True, native_limits_changed=False,
            full_constructor_executed=False, geometry_validation_proved=False, hardware=False,
            limits=['Only the exact byte-snapshot read predicate is executed over synthetic byte-pattern plans.',
                'The complete plan must be independently geometry-validated before using this predicate.',
                'The 2M predicate cost target leaves headroom but does not prove the full entry meets3M.',
                'Neither cold constructor progress nor physical exclusion follows from these unit tests.'])
        with (directory / 'result.json').open('x') as stream:
            stream.write(json.dumps(result, indent=2) + '\n')
        print(json.dumps(dict(snapshot_predicate_cases=378, host_and_RV32_mutants=2,
            cost_regression_controls=1,
            receipt=str((directory / 'result.json').relative_to(ROOT)), hardware=False)), flush=True)


if __name__ == '__main__':
    unittest.main()
