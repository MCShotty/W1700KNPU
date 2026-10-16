#!/usr/bin/env python3
"""Exact compiled native dispatcher, with explicit protocol/callback stubs."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import sys

sys.dont_write_bytecode = True
import native_prefix_snapshot
import test_npu_firmware_loader as loader
from test_barrier_protocol import Rv32, ARGS, STACK, END
from unicorn import UC_HOOK_CODE, UcError, riscv_const as r

ROOT = loader.ROOT
SOURCE = ROOT / 'tests/npu/cold-setup-platform-emulation.c'
FIXTURE = ROOT / 'tests/npu/cold-native-dispatch-fixture.c'


def exercise(path):
    guest = Rv32(path)
    callbacks = []
    slots = {0: 0x8400fdc4, 1: 0x8400fe34, 14: 0x8400ff34,
             19: 0x8400fc16, 21: 0x8400fbca, 22: 0x8400fbb4, 33: 0x8400fdda}
    for api, address in slots.items():
        guest.cpu.mem_write(0x3e900178 + api * 4, struct.pack('<I', address))
    for api, address in ((4, 0x84010164), (10, 0x840101a6)):
        guest.cpu.mem_write(0x3e900148 + api * 4, struct.pack('<I', address))
    for address in (*slots.values(), 0x84010164, 0x840101a6):
        guest.cpu.mem_write(address, bytes.fromhex('1305100067800000'))  # Explicit return-1 stub.

    def callback(cpu, pc, size, opaque):
        callbacks.append(pc)
        cpu.reg_write(r.UC_RISCV_REG_A0, callback_result)
        cpu.reg_write(r.UC_RISCV_REG_PC, cpu.reg_read(r.UC_RISCV_REG_RA))

    guest.cpu.hook_add(UC_HOOK_CODE, callback, begin=0x8400fb00, end=0x84010200)
    cases = [(0x1f, api, 80, 0, 1, 0) for api in range(0x100, 0x111)]
    cases += [(header, 0, 80, 0, 1, slots[0]) for header in (0x10, 0x12, 0x1f)]
    cases += [(0x1f, api, 80, 0, 0, 0) for api in (0xff, 0x111, 0x200, 0xffffffff)]
    cases += [(header, api, 80, 0, 1, address) for header, api, address in
              ((0x10, 14, slots[14]), (0x10, 1, slots[1]), (0x10, 19, slots[19]),
               (0x15, 0, slots[0]), (0x1a, 0, slots[0]), (0x10, 21, slots[21]),
               (0x10, 22, slots[22]), (0x10, 33, slots[33]),
               (0x30, 4, 0x84010164), (0x30, 10, 0x840101a6))]
    cases += [(0x10, 0, size, 0, 0, 0) for size in (0, 79, 81, 0xffffffff)]
    cases += [(0x10, 14, 80, status, 0, 0) for status in range(1, 8)]
    cases = [(*case, 1, True) for case in cases]
    cases += [(header, api, 80, 0, 0, slots[api], 0, True)
              for header, api in ((0x10, 0), (0x12, 0), (0x1f, 0), (0x10, 14))]
    cases += [(header, 0, 80, 0, 0, 0, 1, False) for header in (0x10, 0x12, 0x1f)]
    observed = []
    for header, api, size, status, expected, target, callback_result, good_slot in cases:
        callbacks.clear()
        if api in slots:
            guest.cpu.mem_write(0x3e900178 + api * 4, struct.pack('<I', slots[api] ^ (0 if good_slot else 4)))
        for register, value in zip(ARGS, (header, api, size, status)):
            guest.cpu.reg_write(register, value)
        guest.cpu.reg_write(r.UC_RISCV_REG_SP, STACK)
        guest.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        try:
            guest.cpu.emu_start(guest.symbols['npu_test_dispatch'], END, timeout=1000000, count=100000)
        except UcError as error:
            raise RuntimeError((header, api, size, status, callbacks,
                                hex(guest.cpu.reg_read(r.UC_RISCV_REG_PC)))) from error
        assert guest.cpu.reg_read(r.UC_RISCV_REG_PC) == END, 'entry-budget'
        assert guest.cpu.reg_read(r.UC_RISCV_REG_SP) == STACK, 'stack-restore'
        words = struct.unpack('<6I', guest.cpu.mem_read(guest.symbols['npu_test_dispatch_observed'], 24))
        valid_size = size == 80
        assert words == (int(valid_size), int(valid_size and not status), expected,
                         int(valid_size), (status or (0 if expected else 7)) if valid_size else 0,
                         0x3252434e if valid_size else 0), (header, api, size, status, words)
        assert callbacks == ([target] if target else []), (header, api, callbacks)
        observed.append(dict(header=header, api=api, bytes=size, begin_status=status,
                             callback=target, callback_result=callback_result,
                             callback_slot_matches=good_slot, observed=list(words)))
    return observed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    destination = ROOT / '.local/npu-cold-native-dispatch' / args.name
    assert not destination.exists()
    destination.mkdir(parents=True)
    inputs = native_prefix_snapshot.source_inputs({str(p.relative_to(ROOT)): loader.sha(p) for p in
        (SOURCE, FIXTURE, Path(__file__), *sorted((ROOT / 'firmware/npu').glob('*.h')))})
    linker = destination / 'fixture.ld'
    linker.write_text('ENTRY(npu_test_dispatch)\nSECTIONS { . = 0x84040000; '
        '.text : { *(.text*) } .rodata : { *(.rodata*) } .data : { *(.data*) } '
        '.bss : { *(.bss*) *(COMMON) } ASSERT(. < 0x84060000, "fixture overflow") }\n')
    common = [shutil.which('clang'), '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
        '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin', '-fno-stack-protector',
        '-nostdlib', '-I' + str(ROOT / 'firmware/npu'), FIXTURE,
        '--ld-path=' + str(shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
        '-Wl,-T,' + str(linker) + ',--no-relax']
    source = SOURCE.read_text()
    mutations = {
        'header-only-binding': loader.once(source,
            'npu_cold_rx_event_enrollment(&command)))', 'npu_cold_rx_event_enrollment(&command) || 1))'),
        'ignore-callback-slot': loader.once(source,
            'if (slot && *(const volatile uint32_t *)(uintptr_t)slot == callback)', 'if (slot)'),
        'fake-callback-success': loader.once(source,
            'result = ((native_callback)(uintptr_t)callback)(&command);',
            'result = (((native_callback)(uintptr_t)callback)(&command), 1u);')
    }
    rows, rejected = [], []
    for name, text in [('nominal', source), *mutations.items()]:
        cfile, binary = destination / (name + '.c'), destination / (name + '.elf')
        cfile.write_text(text)
        loader.run(common + [cfile, '-o', binary], destination / (name + '-build.log'))
        try:
            actual = exercise(binary)
        except AssertionError as error:
            assert name != 'nominal'
            rejected.append(dict(name=name, oracle=str(error), binary_sha256=loader.sha(binary)))
        else:
            assert name == 'nominal', ('survived-mutant', name)
            rows = actual
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(loader.sha(ROOT / p) == value for p, value in inputs.items())
    result = dict(passed=True, cases=rows, mutants=rejected, inputs=inputs,
        binary_sha256=loader.sha(destination / 'nominal.elf'), protocol_and_callbacks_stubbed=True,
        native_tail_admission=False, full_setup=False, hardware=False,
        limits=['Exact compiled RV32 dispatcher only; begin/finish and callback effects are explicit stubs.',
                'PCIe0/2/15 route to API0 only through its matching slot; real guard admission is not established by these stubs.',
                'Existing callback families and exact synthetic enrollment APIs retain their routing.'])
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=len(rows), mutants=len(rejected), native_tail_admission=False)))


if __name__ == '__main__':
    main()
