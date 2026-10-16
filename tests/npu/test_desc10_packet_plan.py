#!/usr/bin/env python3
"""Exact binding predicates in host/RV32; prior guards are explicit stubs."""
import argparse
import ctypes
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
import native_prefix_snapshot
import test_npu_firmware_loader as loader
from test_barrier_protocol import Rv32, ARGS, STACK, END
import unicorn
from unicorn import riscv_const as r

ROOT = loader.ROOT
SOURCE = ROOT / 'tests/npu/cold-txdone-native-emulation.c'
HARNESS = ROOT / 'tests/npu/desc10-packet-plan-harness.c'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    destination = ROOT / '.local/npu-desc10-packet-plan' / args.name
    assert not destination.exists()
    destination.mkdir(parents=True)
    paths = [SOURCE, HARNESS, Path(__file__), Path(loader.extract.__file__),
             *sorted((ROOT / 'firmware/npu').glob('*.h'))]
    inputs = native_prefix_snapshot.source_inputs(
        {str(path.relative_to(ROOT)): loader.sha(path) for path in paths})
    text = SOURCE.read_text()
    signature = 'uint32_t npu_emulation_desc10_ready('
    parsed = loader.once(text, signature, 'u32 npu_emulation_desc10_ready(')
    functions = [loader.extract.function(parsed, name) for name in
                 ('packet_plan_live', 'context', 'npu_emulation_desc10_ready', 'completed_prior_live',
                  'npu_emulation_desc10_prior_live', 'npu_emulation_desc10_prior_live_tail',
                  'npu_emulation_desc10_prior_live_inode')]
    functions = [function.replace('u32 npu_emulation_desc10_ready(', signature) for function in functions]
    assert all(function in text for function in functions)
    instruction = '__asm__ volatile ("csrr %0, mstatus" : "=r"(status));'
    shim = '#ifdef __riscv\n' + instruction + '\n#else\nstatus = fixture_status;\n#endif'
    functions = [function.replace(instruction, shim) for function in functions]
    (destination / 'desc10-packet-plan.inc').write_text('\n\n'.join(functions) + '\n')
    linker = destination / 'fixture.ld'
    linker.write_text('ENTRY(npu_test_plan_case)\nSECTIONS { . = 0x84040000; .text : { *(.text*) } '
        '.rodata : { *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } '
        'ASSERT(. < 0x84060000, "fixture overflow") }\n')
    common = [shutil.which('clang'), '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror',
        '-fno-builtin', '-fno-stack-protector', '-I' + str(ROOT / 'firmware/npu'),
        '-I' + str(destination), HARNESS]
    shared, elf = destination / 'fixture.so', destination / 'fixture.elf'
    loader.run(common + ['-shared', '-fPIC', '-o', shared], destination / 'host-build.log')
    lld = shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'
    loader.run(common + ['--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32', '-nostdlib',
        '--ld-path=' + str(lld), '-Wl,-T,' + str(linker) + ',--no-relax', '-o', elf], destination / 'rv32-build.log')
    host = ctypes.CDLL(str(shared))
    call = host.npu_test_plan_case
    call.argtypes = [ctypes.c_uint32] * 4
    call.restype = ctypes.c_uint32
    observed_host = (ctypes.c_uint32 * 8).in_dll(host, 'npu_test_observed')
    guest = Rv32(elf)
    cases = []
    for phase in range(6):
        points = (0, 1, 2) if phase < 2 else (0, 3, 4)
        configurations = [(0, 0, 0), (0, 0, 8)]
        configurations += [(kind, point, 0) for kind in (1, 2) for point in points]
        for kind, point, irq in configurations:
            values = (phase, kind, point, irq)
            actual = call(*values)
            for register, value in zip(ARGS, values):
                guest.cpu.reg_write(register, value)
            guest.cpu.reg_write(r.UC_RISCV_REG_SP, STACK)
            guest.cpu.reg_write(r.UC_RISCV_REG_RA, END)
            guest.cpu.emu_start(guest.symbols['npu_test_plan_case'], END, timeout=1000000, count=3000000)
            assert guest.cpu.reg_read(r.UC_RISCV_REG_PC) == END
            assert guest.cpu.reg_read(r.UC_RISCV_REG_SP) == STACK
            result = guest.cpu.reg_read(r.UC_RISCV_REG_A0)
            words = struct.unpack('<8I', guest.cpu.mem_read(guest.symbols['npu_test_observed'], 32))
            assert result == actual == int(not kind and not irq), (values, actual, result, words)
            assert words == tuple(observed_host), (values, words, tuple(observed_host))
            assert words[6:] == (25604, 25604)
            assert words[3:6] == ((1, 1, 1) if phase == 0 and not actual else (0, 0, 0))
            cases.append(dict(phase=phase, mutation=kind, callback=point, initial_irq=irq, result=result))
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(loader.sha(ROOT / name) == expected for name, expected in inputs.items())
    result = dict(passed=True, cases=cases, inputs=inputs,
        actual_source_predicates=True, host_and_rv32=True,
        binary_sha256={path.name: loader.sha(path) for path in (shared, elf)},
        prior_allocation_readback_guards_stubbed=True, host_csr_modeled=True,
        rv32_csr_actual=True, unicorn_version=unicorn.__version__,
        native_owner_admission=False, full_setup=False, hardware=False,
        limits=['Exact extracted binding predicates compile on host and RV32; only host MSTATUS is modeled.',
                'Prior owners, allocation metadata and readback are explicit valid stubs, with callback mutation hooks.',
                'This tests matching geometry before/after callbacks, not real allocator/caller or original-store admission.',
                'Fresh full512 and all eight native fault classes remain required for the changed raw pair.'])
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=len(cases), native_owner_admission=False)))


if __name__ == '__main__':
    main()
