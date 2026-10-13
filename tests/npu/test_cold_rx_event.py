#!/usr/bin/env python3
"""Compare exact host-C and RV32 metadata-owner state; no physical admission."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode = True
import test_cold_tx_buffer as tx
from test_barrier_protocol import Rv32
from unicorn import riscv_const as r

ROOT = tx.ROOT
CORE = ROOT / 'firmware/npu'
STATE, PLAN, END = tx.STATE, tx.PLAN, tx.END
METADATA = 0x3e903964


class Pair:
    def __init__(self, shared, elf):
        self.host, self.rv = ctypes.CDLL(str(shared)), Rv32(elf)
        self.state = (ctypes.c_uint32 * 38)()
        self.plan = (ctypes.c_uint32 * 30)(*tx.PROFILE, 0x97000000)
        self.calls = 0
        pointer, integer = ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint32
        for name, signature in {
            'begin': [pointer, pointer, integer, integer],
            'reserve': [pointer, pointer, integer, integer, integer, integer, integer],
            'publish': [pointer, pointer, integer, integer, integer, integer],
            'finish': [pointer, pointer, integer, integer],
            'live': [pointer, pointer, integer, integer],
            'plan_valid': [pointer], 'dma_valid': [pointer, integer, integer],
        }.items():
            function = getattr(self.host, 'npu_cold_rx_event_' + name)
            function.argtypes, function.restype = signature, integer
        self.fresh()

    def fresh(self, ring=0x97000000):
        self.state[:] = [0] * 38
        self.plan[:] = [*tx.PROFILE, ring]
        self.sync()

    def sync(self):
        self.rv.cpu.mem_write(STATE, bytes(self.state))
        self.rv.cpu.mem_write(PLAN, bytes(self.plan))

    def invoke(self, name, host, native):
        result = getattr(self.host, 'npu_cold_rx_event_' + name)(*host)
        for i, value in enumerate(native):
            self.rv.cpu.reg_write(getattr(r, 'UC_RISCV_REG_A' + str(i)), value)
        self.rv.cpu.reg_write(r.UC_RISCV_REG_SP, 0x84100000)
        self.rv.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.rv.cpu.emu_start(self.rv.symbols['npu_cold_rx_event_' + name], END,
                              count=1000000, timeout=1000000)
        assert self.rv.cpu.reg_read(r.UC_RISCV_REG_PC) == END
        assert self.rv.cpu.reg_read(r.UC_RISCV_REG_SP) == 0x84100000
        assert result == self.rv.cpu.reg_read(r.UC_RISCV_REG_A0), name
        assert bytes(self.state) == bytes(self.rv.cpu.mem_read(STATE, len(bytes(self.state)))), name
        assert bytes(self.plan) == bytes(self.rv.cpu.mem_read(PLAN, len(bytes(self.plan)))), name
        self.calls += 1
        return result

    def call(self, name, *values, epoch=1):
        return self.invoke(name, [self.state, self.plan, epoch, *values], [STATE, PLAN, epoch, *values])

    def valid(self):
        return self.invoke('plan_valid', [self.plan], [PLAN])


def exercise(pair):
    controls, successes = 0, 0
    for tag in range(3):
        ring = 0x17000000 + tag * 0x40000000
        expected = (ring & 0x3fffffff) | 0x40000000
        for before in (0, expected, 0xdeadbeef, 0xffffffff):
            pair.fresh(ring)
            assert pair.valid() == 1
            assert pair.call('begin', before) == 0
            assert list(pair.state[:8]) == [0x31455852, 1, 0, 1, 0, 0, 0, before]
            assert pair.call('reserve', METADATA, 4, expected, before) == 0
            assert pair.call('publish', METADATA, 4, expected) == 0
            assert pair.call('finish', expected) == 0
            assert list(pair.state[:8]) == [0x31455852, 1, 0, 0, 1, 1, 1, before]
            assert pair.call('live', expected) == 1 and pair.call('live', expected ^ 1) == 0
            assert pair.call('begin', before) == 3 and pair.state[2] == 1
            assert list(pair.state[4:7]) == [1, 1, 1]
            successes += 1
    invalid = [0, 1, 0x97000001, 0xc0000000, 0xbffffff0, 0x3ffff000]
    spans = [(pair.plan[1], pair.plan[2])]
    spans += [(tx.PROFILE[17 + 2 * i], tx.PROFILE[18 + 2 * i]) for i in range(6)]
    spans += [(tx.PROFILE[9 + i], 256) for i in range(8)]
    spans += [(tx.PROFILE[3 + i], 0x20000 if i < 2 else 0x40000) for i in range(6)]
    for base, size in spans:
        for tag in range(3):
            invalid.append((base & 0x3fffffff) + tag * 0x40000000)
            invalid.append(((base & 0x3fffffff) + size - 16) + tag * 0x40000000)
    for ring in invalid:
        pair.fresh(ring)
        assert pair.valid() == 0, hex(ring)
        assert pair.call('begin', 0) == 2 and pair.state[2] == 1
        assert not any(pair.state[i] for i in (0, 3, 4, 5, 6))
        controls += 1
    for word in range(30):
        pair.fresh()
        assert pair.call('begin', 7) == 0
        pair.plan[word] ^= 1
        pair.sync()
        assert pair.call('reserve', METADATA, 4, 0x57000000, 7) == 5
        assert pair.state[2] == pair.state[3] == 1 and not any(pair.state[4:7])
        controls += 1
    for kind in range(8):
        pair.fresh()
        assert pair.call('begin', 7) == 0
        if kind == 0:
            assert pair.call('reserve', METADATA + 4, 4, 0x57000000, 7) == 7
        elif kind == 1:
            assert pair.call('reserve', METADATA, 2, 0x57000000, 7) == 7
        elif kind == 2:
            assert pair.call('reserve', METADATA, 4, 0x57000001, 7) == 7
        elif kind == 3:
            assert pair.call('reserve', METADATA, 4, 0x57000000, 8) == 7
        elif kind == 4:
            assert pair.call('publish', METADATA, 4, 0x57000000) == 7
        elif kind == 5:
            assert pair.call('finish', 0x57000000) == 6
        elif kind == 6:
            assert pair.call('reserve', METADATA, 4, 0x57000000, 7) == 0
            assert pair.call('publish', METADATA, 4, 0x57000001) == 8
            assert list(pair.state[4:7]) == [1, 1, 0]
        else:
            assert pair.call('reserve', METADATA, 4, 0x57000000, 7) == 0
            assert pair.call('reserve', METADATA, 4, 0x57000000, 7) == 7
            assert list(pair.state[4:7]) == [1, 1, 0]
        assert pair.state[2] == pair.state[3] == 1
        assert pair.call('live', 0x57000000) == 0
        controls += 1
    for epoch in (0, 2, 0xffffffff):
        pair.fresh()
        assert pair.call('begin', 0, epoch=epoch) == 2 and pair.state[2] == 1
        controls += 1
    for word in range(38):
        pair.fresh()
        pair.state[word] = 1
        pair.sync()
        assert pair.call('begin', 0) == 3 and pair.state[2] == 1
        controls += 1
    return dict(passed=True, calls=pair.calls, successes=successes, controls=controls)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--core-object', type=Path)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-rx-event-bind-20261013' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    paths = [CORE / p for p in ('cold-rx-event.c', 'cold-rx-event.h', 'cold-tx-buffer.c',
                               'cold-tx-buffer.h', 'cold-descriptor.h', 'bootstrap.h')]
    paths += [Path(__file__).resolve(), ROOT / 'tests/npu/cold-rx-event-probe.ld',
              ROOT / 'tests/npu/cold-rx-event-sanitize.c',
              Path(tx.__file__), Path(tx.loader.__file__), Path(tx.loader.extract.__file__),
              ROOT / 'tests/npu/test_barrier_protocol.py']
    if args.core_object:
        assert args.core_object.resolve().is_relative_to(ROOT)
        paths.append(args.core_object.resolve())
    inputs = {str(p.relative_to(ROOT)): tx.loader.sha(p) for p in paths}
    sources = [CORE / 'cold-rx-event.c', CORE / 'cold-tx-buffer.c']
    shared, elf = dest / 'host.so', dest / 'owner.elf'
    command = [shutil.which('clang'), '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-I' + str(CORE)]
    tx.loader.run(command + ['-shared', '-fPIC', *sources, '-o', shared], dest / 'host-build.log')
    linker = shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'
    rv_sources = [args.core_object.resolve() if args.core_object else sources[0], sources[1]]
    tx.loader.run(command + ['--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
                  '-nostdlib', '-ffreestanding', '-fno-builtin', '-fno-stack-protector',
                  '--ld-path=' + str(linker), '-Wl,-T,' + str(ROOT / 'tests/npu/cold-rx-event-probe.ld'),
                  *rv_sources, '-o', elf], dest / 'rv-build.log')
    pair = Pair(shared, elf)
    result = exercise(pair)
    sanitizer = dest / 'sanitize'
    tx.loader.run(command + ['-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                  ROOT / 'tests/npu/cold-rx-event-sanitize.c', *sources, '-o', sanitizer], dest / 'sanitize-build.log')
    tx.loader.run([sanitizer], dest / 'sanitize.log', env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1'))
    original = sources[0].read_text()
    changes = {
        'ignore-TX-overlap': ('if (overlap(ring, NPU_COLD_RX_EVENT_BYTES, p->host[i], npu_cold_txbuf_bytes(i)))',
                              'if (0 && overlap(ring, NPU_COLD_RX_EVENT_BYTES, p->host[i], npu_cold_txbuf_bytes(i)))'),
        'ignore-owner-plan': ('npu_cold_rx_event_plan_equal(&s->plan, p);', '(1);'),
        'ignore-reserve-preimage': ('before != s->before ||', '(0 && before != s->before) ||'),
        'ignore-reserve-address': ('address != NPU_COLD_RX_EVENT_METADATA || bytes != 4 || before',
                                    '(0 && address != NPU_COLD_RX_EVENT_METADATA) || bytes != 4 || before'),
        'ignore-readback': ('if (readback != npu_cold_rx_event_value(p->ring))',
                            'if (0 && readback != npu_cold_rx_event_value(p->ring))'),
        'omit-retained-commit': ('s->reserved = s->committed = 1;', 's->reserved = 1;'),
        'allow-reinitialize': ('if (words[i])', 'if (0 && words[i])'),
    }
    mutants = []
    for name, (old, new) in changes.items():
        assert original.count(old) == 1, name
        target = dest / 'mutants' / name
        target.mkdir(parents=True)
        source = target / 'owner.c'
        source.write_text(original.replace(old, new))
        mshared, melf = target / 'host.so', target / 'owner.elf'
        tx.loader.run(command + ['-shared', '-fPIC', source, sources[1], '-o', mshared], target / 'host-build.log')
        tx.loader.run(command + ['--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32', '-nostdlib',
                      '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '--ld-path=' + str(linker),
                      '-Wl,-T,' + str(ROOT / 'tests/npu/cold-rx-event-probe.ld'),
                      source, sources[1], '-o', melf], target / 'rv-build.log')
        rejected = False
        try:
            exercise(Pair(mshared, melf))
        except AssertionError:
            rejected = True
        assert rejected, name
        mutants.append(dict(name=name, host_sha256=tx.loader.sha(mshared), rv_sha256=tx.loader.sha(melf)))
    assert all(tx.loader.sha(ROOT / p) == digest for p, digest in inputs.items())
    result.update(inputs=inputs, mutants=mutants, sanitizers=['address', 'undefined', 'leak'],
                  exact_core_object=str(args.core_object.resolve().relative_to(ROOT)) if args.core_object else None,
                  binaries={str(p.relative_to(ROOT)): tx.loader.sha(p) for p in (shared, elf, sanitizer)},
                  limits=['Exact host-C/RV32 returns and complete 152-byte owner state; plan/spans/preimages are modeled.',
                          'This does not bind original API22 stores, authorize physical DMA/drains or establish full setup.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('passed', 'calls', 'successes', 'controls')}))


if __name__ == '__main__':
    main()
