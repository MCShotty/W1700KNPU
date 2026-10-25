#!/usr/bin/env python3
"""Actual ABI2 raw-image RRO mailbox replay with a complete host journal oracle.

Provider publication, mapped backing, IRQ entry, and MCU results are models.
The raw reset, eight parked harts, V2 exchange, and cold enrollment execute.
"""
import argparse
from collections import Counter
from copy import deepcopy
import gc
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import select
import shutil
import struct
import subprocess
import sys
import time

sys.dont_write_bytecode = True
import unicorn
from unicorn import UC_HOOK_BLOCK, UC_HOOK_CODE, riscv_const as r

import cold_client_native
import test_npu_raw_pair as raw
from test_bootstrap_native import Bootstrap, REQUEST, ADM, BOOT
from test_firmware_mailbox_dispatch import MBOX, PAYLOAD, DISPATCH
from test_firmware_memory_layout import STACK_TOPS
from test_firmware_stop_counterexample import END
from emulation_layout import CODE, SRAM, SRAM_BYTES, STATE

ROOT = raw.ROOT
CORE = ROOT / 'firmware/npu'
HELPER = ROOT / 'tests/npu/rro-wire-native-pair-oracle.c'
HELPER_SHA256 = '3aaa465d5774ee7c76c0e747209dab20493ba3b1137f8b4e57701b4b5ee5ab32'
OUTPUT = ROOT / '.local/npu-rro-wire-native-pair-20261023'
DMA, DMA_BYTES = 0x48000000, 0xc00000
BLOCK_TABLE, SESSION_TABLE = 0x3e901fdc, 0x3e90458c
MAILBOX_VENEER, READY_VENEER = 0x84100000, 0x84100004
RPC_INSTRUCTIONS, RPC_TIMEOUT_US = 100000000, 60000000
MAX_UNIQUE_BLOCKS = 16384
OUTPUT_BUDGET_BYTES, RPC_LOG_BYTES = 256 * 1024 * 1024, 60 * 1024 * 1024
OPEN, ENROLL, PUBLISH, HARDWARE, RESET, MCU_BEGIN, MCU_COMPLETE, CLOSE = range(1, 9)
LAYOUT_NAMES = (
    'magic', 'version', 'words', 'plan_bytes', 'journal_bytes', 'session_bytes',
    'owner_offset', 'plan_offset', 'extents_offset', 'extent_bytes', 'resets_offset',
    'reset_bytes', 'error_offset', 'phase_offset', 'allocated_offset', 'confirmed_offset',
    'publication_offset', 'publication_bytes', 'exposure_offset', 'cold_bytes',
    'cold_enrolled_offset', 'cold_rx_offset', 'wire_held', 'publication_failed',
    'reset_failed', 'possible', 'last_ticket_offset', 'session_magic', 'blocks', 'sessions',
    'publications', 'max_extents',
)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def words(value):
    assert len(value) % 4 == 0
    return list(struct.unpack('<' + 'I' * (len(value) // 4), value))


def packed(value):
    return struct.pack('<' + 'I' * len(value), *value)


def contained(address, size, start, count):
    return size > 0 and start <= address and address + size <= start + count


def exact(actual, expected, label, directory):
    if actual != expected:
        (directory / (label + '.actual.bin')).write_bytes(actual)
        (directory / (label + '.expected.bin')).write_bytes(expected)
        first = next((i for i, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]), None)
        raise AssertionError((label, 'complete-byte-mismatch', len(actual), len(expected), first))


def verify_inputs(inputs):
    assert isinstance(inputs, dict) and inputs
    for name, expected in inputs.items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and path.is_file(), ('input-path', name)
        assert file_hash(path) == expected, ('source-drift', name)


def host_evidence(path):
    record = json.loads(path.read_bytes())
    matrix = record['matrix']
    assert record['passed'] is True and matrix['profiles'] == 3
    assert matrix['positive_rpc'] == matrix['journal_compares'] == 19261
    assert matrix['enrollments'] == 415 and matrix['publications'] == 387
    assert matrix['reset_npu'] == matrix['mcu_begin'] == matrix['mcu_complete'] == 6150
    assert matrix['negative_cases'] == 34 and matrix['direct_negative'] == 19
    assert matrix['io_faults'] == 6 and len(record['mutation_controls']) == 5
    assert record['hardware'] is False and record['physical_retirement'] is False
    verify_inputs(record['inputs'])
    return record


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def storage_bytes(destination):
    count = sum(path.stat().st_size for path in destination.rglob('*') if path.is_file())
    assert count <= OUTPUT_BUDGET_BYTES, ('new-test-output-budget', count, OUTPUT_BUDGET_BYTES)
    return count


class JsonLines:
    def __init__(self, path):
        self.path, self.bytes = path, 0

    def __enter__(self):
        self.stream = self.path.open('xb')
        return self

    def write(self, value):
        value = value.encode('ascii')
        assert self.bytes + len(value) <= RPC_LOG_BYTES, ('bounded-RPC-log', str(self.path), self.bytes)
        self.stream.write(value)
        self.bytes += len(value)

    def flush(self):
        self.stream.flush()

    def __exit__(self, *unused):
        self.stream.close()


def build_oracle(destination):
    clang = shutil.which('clang')
    assert clang, 'host Clang is required for the independent journal oracle'
    binary = destination / 'oracle'
    command = [clang, '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
        '-fno-omit-frame-pointer', '-I', CORE, CORE / 'rro-lifetime.c',
        CORE / 'rro-wire.c', HELPER, '-o', binary]
    completed = subprocess.run(list(map(str, command)), capture_output=True, text=True,
                               timeout=180, preexec_fn=no_core)
    (destination / 'oracle-build.log').write_text(completed.stdout + completed.stderr)
    assert completed.returncode == 0, ('oracle-build', completed.returncode, completed.stderr[-6000:])
    return binary, list(map(str, command))


class Oracle:
    def __init__(self, binary, plan, directory):
        self.log = (directory / 'oracle.log').open('xb')
        environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
                           UBSAN_OPTIONS='halt_on_error=1')
        self.process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.log, env=environment, preexec_fn=no_core, bufsize=0)
        try:
            values = words(self.read(128))
            self.layout = dict(zip(LAYOUT_NAMES, values))
            assert values[:3] == [0x314f524e, 1, 32]
            assert self.layout['plan_bytes'] == 216 and self.layout['session_bytes'] == 30588
            assert self.layout['journal_bytes'] == 30356
            assert self.layout['cold_bytes'] == 412
            assert values[28:] == [128, 1025, 129, 139]
            self.process.stdin.write(plan)
            self.process.stdin.flush()
            self.journal = None
        except BaseException:
            self.close(False)
            raise

    def read(self, count):
        data = bytearray()
        deadline = time.monotonic() + 60
        while len(data) < count:
            remaining = deadline - time.monotonic()
            assert remaining > 0 and select.select([self.process.stdout], [], [], remaining)[0], \
                ('oracle-output-timeout', len(data), count, self.process.poll())
            part = os.read(self.process.stdout.fileno(), count - len(data))
            assert part, ('oracle-incomplete-output', len(data), count, self.process.poll())
            data.extend(part)
        return bytes(data)

    def request(self, operation, sequence, argument=0, generation=0):
        self.process.stdin.write(packed([operation, sequence, argument, generation]))
        self.process.stdin.flush()
        header = words(self.read(16))
        assert header == [0x314f524e, operation, sequence, self.layout['journal_bytes']]
        wire = self.read(256)
        self.journal = self.read(self.layout['journal_bytes'])
        assert words(wire)[:7] == [0x3f, 2, 0x3151524e, 1, 256, sequence, operation]
        return wire, self.journal

    def close(self, okay):
        if not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            try:
                result = self.process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
                assert not okay, 'owned oracle did not terminate after input closed'
                return
            tail = self.process.stdout.read()
        finally:
            self.process.stdout.close()
            self.log.close()
        if okay:
            assert result == 0 and tail == b'', ('oracle-terminal', result, tail[:100])


class Pair(raw.tx.TxPackets):
    def __init__(self, paths, parts):
        self.rpc_active = False
        self.retained = []
        self.block_cache = {}
        self.current = None
        self.injection = None
        self.injected = False
        self.total = Counter()
        self.last_failure = None
        super().__init__(paths, parts)

    def message(self, request, **kwargs):
        # The inherited composition's request whitelist predates API1/API2.
        # Use its actual raw mailbox caller, without that diagnostic whitelist.
        return Bootstrap.message(self, request, **kwargs)

    def is_memory(self, address, size):
        return (contained(address, size, DMA, DMA_BYTES) or
                any(contained(address, size, start, count) for start, count in self.retained) or
                super().is_memory(address, size))

    def configure(self, files, manifest, code):
        self.raw_code, self.manifest = code, manifest
        self.rro = raw.image.symbols(files['rro-wire'])
        self.broker = self.rro['npu_emulation_rro_session_state']
        self.cold = self.rv.symbols['npu_emulation_cold_setup_state']
        assert self.rro['npu_emulation_rro_mailbox_veneer'] == MAILBOX_VENEER
        assert self.rro['npu_emulation_rro_cold_ready_veneer'] == READY_VENEER
        for site, symbol in ((MAILBOX_VENEER, 'npu_emulation_rro_mailbox'),
                             (READY_VENEER, 'npu_emulation_rro_cold_ready')):
            assert bytes(self.cpu.mem_read(site, 4)) == raw.image.jal(site, self.rro[symbol])
        self.executables = ((CODE, raw.image.ORIGINAL_CODE_BYTES),) + tuple(
            (row['start'], row['end'] - row['start']) for row in manifest['sections']
            if row['component'] in ('base', 'rro-wire') and row['flags'] & 4)
        self.rro_mutable = tuple((row['start'], row['end'] - row['start'])
                            for row in manifest['sections']
                            if row['component'] == 'rro-wire' and row['flags'] & 1)
        self.block_sites = ((MAILBOX_VENEER, 'mailbox_veneer'),
                            (READY_VENEER, 'ready_veneer'),
                            (self.rro['npu_emulation_rro_mailbox'], 'mailbox_binding'),
                            (self.rro['npu_emulation_rro_cold_ready'], 'cold_ready_binding'))
        self.rpc_writable = ((STACK_TOPS[0] - 0x4000, 0x4000), (PAYLOAD, 256),
                             (ADM, 44), (STATE, 104), (raw.composition.boot.SESSION, 20),
                             (self.cold, 412), *self.rro_mutable)
        self.cpu.mem_map(DMA, DMA_BYTES)
        self.cpu.mem_write(DMA, b'\xa5' * DMA_BYTES)
        for physical, count in [(0x92000000, 8192)] + [
                (0x96000000 + i * 0x100000, 0x20000 if i < 2 else 0x40000) for i in range(6)]:
            address = (physical & 0x3fffffff) | 0x40000000
            self.cpu.mem_map(address, count)
            self.cpu.mem_write(address, b'\xa5' * count)
            self.retained.append((address, count))
        self.initial_retained = [(address, bytes(self.cpu.mem_read(address, count)))
                                 for address, count in self.retained]
        self.cpu.hook_add(UC_HOOK_BLOCK, self.block)
        self.bss_zero()

    def bss_zero(self):
        row = next(row for row in self.manifest['sections']
                   if row['component'] == 'rro-wire' and row['zero_fill'])
        assert row['start'] == self.broker and row['end'] - row['start'] == 30588
        assert bytes(self.cpu.mem_read(self.broker, 30588)) == bytes(30588), 'raw RRO BSS is not zero'

    def block(self, cpu, address, size, unused):
        if not self.rpc_active:
            return
        key = (address, size)
        if key not in self.block_cache:
            assert any(contained(address, size, start, count) for start, count in self.executables), \
                ('unexpected-executed-component', hex(address), size)
            assert not any(address <= old < address + size for old in (0x8400fc2c, 0x8400e084)), \
                'original raw RRO callback/helper executed'
            assert len(self.block_cache) < MAX_UNIQUE_BLOCKS, 'bounded exact-code observer exhausted'
            assert bytes(cpu.mem_read(address, size)) == self.raw_code[address - CODE:address - CODE + size]
            # Code/layout are fixed for this Pair; dynamic counters and SP are not.
            self.block_cache[key] = tuple(name for site, name in self.block_sites
                                          if address <= site < address + size)
        self.counts['blocks'] += 1
        self.min_sp = min(self.min_sp, cpu.reg_read(r.UC_RISCV_REG_SP))
        for name in self.block_cache[key]:
            self.counts[name] += 1

    def effect(self, address, size, value, write):
        scope = self.current
        table = scope.get('table')
        if table is not None and contained(address, size, table, 4):
            kind = 'table'
            assert size == 4 and address == table
            assert not write or scope['kind'] == 'publish', 'reset rewrote table'
            if write:
                assert value == scope['pointer']
        elif scope.get('base') is not None and contained(address, size, scope['base'], scope['bytes']):
            kind = 'extent'
            offset = address - scope['base']
            assert size in (1, 4) and not address & (size - 1)
            if size == 1:
                assert offset % 8 == 7 and (not write or value == 0xff)
            elif write:
                assert scope['kind'] == 'publish' and scope['bytes'] == 65536 and value == 0
        else:
            raise AssertionError(('RRO access outside exact operation extent/table', hex(address), size, scope))
        assert not self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8, 'RRO I/O with IRQs enabled'
        assert self.get32(ADM + 4) == self.get32(self.broker + 8) == 1, 'I/O without active owner'
        self.counts[kind + ('_writes' if write else '_reads')] += 1
        if write:
            self.io_digest.update(struct.pack('<IIIQ', self.cpu.reg_read(r.UC_RISCV_REG_PC),
                                              address, size, value & 0xffffffffffffffff))
        if not self.injected and self.injection:
            if self.injection in ('barrier', 'admission') and write:
                self.put32(STATE + 16 if self.injection == 'barrier' else ADM + 8, 1)
                self.injected = True
            elif self.injection == 'readback' and kind == 'table' and not write:
                self.put32(address, self.get32(address) ^ 4)
                self.injected = True

    def read_hook(self, cpu, access, address, size, value, data):
        if not self.rpc_active:
            return super().read_hook(cpu, access, address, size, value, data)
        if contained(address, size, PAYLOAD, 256):
            self.counts['payload_reads'] += 1
            return
        if (contained(address, size, DMA, DMA_BYTES) or
                contained(address, size, BLOCK_TABLE, 128 * 4) or
                contained(address, size, SESSION_TABLE, 4)):
            return self.effect(address, size, value, False)
        if contained(address, size, CODE, raw.image.CODE_LIMIT) or contained(address, size, SRAM, SRAM_BYTES):
            return
        assert not any(contained(address, size, start, count) for start, count in self.retained), \
            'RRO read a protected retained TX/RX buffer'
        return super().read_hook(cpu, access, address, size, value, data)

    def write_hook(self, cpu, access, address, size, value, data):
        if not self.rpc_active:
            return super().write_hook(cpu, access, address, size, value, data)
        self.min_sp = min(self.min_sp, cpu.reg_read(r.UC_RISCV_REG_SP))
        if (contained(address, size, DMA, DMA_BYTES) or
                contained(address, size, BLOCK_TABLE, 128 * 4) or
                contained(address, size, SESSION_TABLE, 4)):
            return self.effect(address, size, value, True)
        if any(contained(address, size, start, count) for start, count in self.rpc_writable):
            self.counts['metadata_writes'] += 1
            return
        assert not self.is_memory(address, size), ('unexpected raw RRO memory write', hex(address), size)
        return super().write_hook(cpu, access, address, size, value, data)

    def execute(self, start, arguments, scope=None, *, mstatus=0):
        context = self.cpu.context_save()
        events, mmio = len(self.events), len(self.mmio)
        self.current = scope or {'kind': 'metadata'}
        self.counts, self.io_digest = Counter(), hashlib.sha256()
        self.min_sp = STACK_TOPS[0] - 0x1000
        self.injected = False
        self.last_failure = None
        self.cpu.reg_write(r.UC_RISCV_REG_SP, self.min_sp)
        self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, mstatus)
        for i in range(8):
            self.cpu.reg_write(getattr(r, 'UC_RISCV_REG_A' + str(i)), arguments[i] if i < len(arguments) else 0)
        # Replace only this test's general instruction observer during RPCs.
        # Exact raw blocks, scoped memory access, and Unicorn's instruction and
        # time limits remain enforced; no guest instructions are substituted.
        self.cpu.hook_del(self.instruction_hook)
        self.cpu.hook_del(self.callback_hook)
        self.rpc_active = True
        began = time.monotonic_ns()
        try:
            self.cpu.emu_start(start, END, count=RPC_INSTRUCTIONS, timeout=RPC_TIMEOUT_US)
            pc = self.cpu.reg_read(r.UC_RISCV_REG_PC)
            assert pc == END, ('new-RPC-budget', hex(pc), self.cpu.query(unicorn.UC_QUERY_TIMEOUT),
                               RPC_INSTRUCTIONS, RPC_TIMEOUT_US, self.current, dict(self.counts))
            assert self.cpu.reg_read(r.UC_RISCV_REG_SP) == STACK_TOPS[0] - 0x1000
            assert self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) == mstatus
            assert self.min_sp >= STACK_TOPS[0] - 0x4000, ('native-stack-bound', hex(self.min_sp))
            result = self.cpu.reg_read(r.UC_RISCV_REG_A0)
            record = dict(counts=dict(self.counts), write_sha256=self.io_digest.hexdigest(),
                wall_ns=time.monotonic_ns() - began, min_sp=self.min_sp,
                mmio=[{key: event[key] for key in ('kind', 'address', 'size', 'value')}
                      for event in self.mmio[mmio:]])
            self.total.update(self.counts)
            return result, record
        except BaseException as error:
            self.last_failure = dict(error=repr(error), terminal_PC=self.cpu.reg_read(r.UC_RISCV_REG_PC),
                SP=self.cpu.reg_read(r.UC_RISCV_REG_SP), min_sp=self.min_sp,
                mstatus=self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS), current=self.current,
                wall_ns=time.monotonic_ns() - began, counts=dict(self.counts),
                timed_out=bool(self.cpu.query(unicorn.UC_QUERY_TIMEOUT)))
            raise
        finally:
            self.rpc_active = False
            self.instruction_hook = self.cpu.hook_add(UC_HOOK_CODE, self.code_hook)
            self.callback_hook = self.cpu.hook_add(UC_HOOK_CODE, self.native_callback)
            del self.events[events:]
            del self.mmio[mmio:]
            self.cpu.context_restore(context)

    def mailbox(self, request, scope=None, *, address=REQUEST, length=None, flags=1):
        assert len(request) <= 256
        self.payload_reads.clear()
        self.callback_entries.clear()
        self.cpu.mem_write(PAYLOAD, request + bytes(256 - len(request)))
        self.put32(MBOX + 0x30, address)
        self.put32(MBOX + 0x34, len(request) if length is None else length)
        self.put32(MBOX + 0x3c, flags)
        _, record = self.execute(DISPATCH, [8], scope)
        self.payload_reads.clear()
        return self.get32(MBOX + 0x3c), bytes(self.cpu.mem_read(PAYLOAD, len(request))), record

    def checkpoint(self):
        spans = [(CODE, raw.image.CODE_LIMIT), (SRAM, SRAM_BYTES), (DMA, DMA_BYTES),
                 (PAYLOAD, 4096), (MBOX, 4096), (0x0c002000, 28), (0x0c003000, 28), (0x0c200000, 8)]
        return ([(start, bytes(self.cpu.mem_read(start, count))) for start, count in spans],
                deepcopy(self.plic_banks))

    def rewind(self, checkpoint):
        spans, banks = checkpoint
        for start, value in spans:
            self.cpu.mem_write(start, value)
        self.plic_banks = deepcopy(banks)
        self.cpu.ctl_remove_cache(CODE, CODE + raw.image.CODE_LIMIT)
        self.injection = None

    def code_readback(self):
        for row in self.manifest['sections']:
            if row['flags'] & 4:
                assert bytes(self.cpu.mem_read(row['start'], row['end'] - row['start'])) == \
                    self.raw_code[row['start'] - CODE:row['end'] - CODE]
        self.check_hooks()
        for address, before in self.initial_retained:
            assert bytes(self.cpu.mem_read(address, len(before))) == before, 'retained TX/RX backing changed'


def boot_prefix(pair, profile, directory):
    h, paths, files, manifest = raw.load(pair, factory=Pair)
    assert manifest['loader_abi']['version'] == 2 and len(manifest['hooks']) == 168
    assert manifest['data']['bytes'] == 0x6480
    verify_inputs(manifest['inputs'])
    h.configure(files, manifest, (pair / 'CODE.bin').read_bytes())
    publication = raw.provision(h, raw.composition.control.BOOT)
    h.hart = 0
    h.cpu.context_restore(h.fresh)
    assert h.reset(0x84003f32) == 0x84003f32
    assert h.get32(raw.composition.native.IRQ8) == h.rv.symbols['npu_emulation_mailbox']
    host = raw.composition.control.Host(paths)
    accepted, discovery_request, discovery_reply = raw.composition.control.exchange(host, h)
    assert accepted == raw.composition.control.ACCEPTED
    assert len(discovery_request) == len(discovery_reply) == 20 and discovery_reply[10] == 0x27
    assert h.run(0x84003f32, [0x8400420a]) == 0x8400420a
    bootstrap = raw.composition.boot.setup(h, run_clear=True)
    raw.composition.control.advance(host, h)
    footprint = h.finish_coordinator()
    workers = [h.worker(hart) for hart in range(1, 8)]
    h.on_core0()
    accepted, status_request, status_reply = raw.composition.control.exchange(host, h)
    assert accepted == raw.composition.control.ACCEPTED
    assert len(status_request) == len(status_reply) == 20 and status_reply[10] == 0x27
    assert host.state[0] == raw.composition.control.PARKED and host.state[10] == 255
    assert words(bytes(h.cpu.mem_read(STATE, 104))) == [1, 0, 0, 0, 0] + [1] * 8 + [0] * 13
    assert h.get32(ADM) == 1 and h.get32(ADM + 4) == h.get32(ADM + 8) == 0
    mailbox = [REQUEST + i * 256 for i in range(8)]
    tx = [0x96000000 + i * 0x100000 for i in range(6)]
    commands = [(0x1f, 0x100, 0x20000000), (0x1f, 0x101, 0x100000)]
    commands += [(0x1f, 0x102 + i, address) for i, address in enumerate(mailbox)]
    commands += [(0x1f, 0x110, 0x92000000)]
    commands += [(0x1f, 0x10a + i, address) for i, address in enumerate(tx)]
    enrollment = [cold_client_native.exchange(host, h, command) for command in commands]
    assert len(enrollment) == 17
    h.bss_zero()
    server = words(bytes(h.cpu.mem_read(raw.composition.boot.SESSION, 20)))
    native = words(bytes(h.cpu.mem_read(BOOT + 32, 48)))
    assert native == [word for span in raw.composition.native.plan() for word in span]
    identity = [0x11223344, 0xdeadbeef, 0x55667788, 0x9abcdef0,
                *server[:2], *server[2:4], 1, profile]
    plan = identity + [word for address in mailbox for word in (address, 256)]
    plan += [word for i, address in enumerate(tx) for word in (address, 0x20000 if i < 2 else 0x40000)]
    plan += [0x92000000, 8192, *native, 0x20000000, 0x100000]
    assert len(plan) == 54 and plan[10:12] == [REQUEST, 256]
    receipt = dict(profile=profile, provider_publication=publication, bootstrap=bootstrap,
        workers=workers, coordinator_footprint=footprint, cold_enrollment=enrollment,
        V2_discovery=dict(request=discovery_request, reply=discovery_reply),
        V2_status=dict(request=status_request, reply=status_reply),
        v2_server=server, plan_words=plan, actual_raw_reset=True,
        modeled=['coherent provider publication/backing', 'machine IRQ entry with MIE cleared',
                 'per-hart CSR/PLIC and host pointer publication', 'MCU result assertion'])
    (directory / 'prefix.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return h, packed(plan), receipt


def next_sequence(h):
    return h.get32(raw.composition.boot.SESSION + 16) + 1


def probe(plan, operation, sequence, fields=()):
    value = [0] * 64
    value[:8] = [0x3f, 2, 0x3151524e, 1, 256, sequence, operation, 0]
    value[8:18] = words(plan)[:10]
    if operation == OPEN:
        value[8:62] = words(plan)
    for index, field in fields:
        value[8 + index] = field
    return packed(value)


def reply(request, response, status=0):
    expected = words(request)
    expected[2], expected[7] = 0x3152524e, status
    assert response == packed(expected), ('RRO immutable echo/status', status, words(response)[:8])


def metadata(h, layout):
    return [bytes(h.cpu.mem_read(start, count)) for start, count in (
        (h.broker, layout['session_bytes']), (raw.composition.boot.SESSION, 20),
        (ADM, 44), (STATE, 104), (h.cold, layout['cold_bytes']))]


def cold_packet(h):
    boot_lo, boot_hi, nonce_lo, nonce_hi, serial = words(
        bytes(h.cpu.mem_read(raw.composition.boot.SESSION, 20)))
    return packed([0x3f, 1, 0x3253434e, 2, 80, 1, serial + 1,
                   nonce_lo, nonce_hi, boot_lo, boot_hi, 0x30, 10, 0, 0, *([0] * 5)])


def cold_gate(h, layout, expected, label, stream):
    before = metadata(h, layout)
    request = cold_packet(h)
    flags, response, record = h.mailbox(request)
    value = words(response)
    assert flags == 7 and value[2] == 0x3252434e and value[14] == expected, (label, flags, value)
    assert record['counts'].get('ready_veneer') == 1
    assert record['counts'].get('cold_ready_binding') == 1
    if expected:
        assert metadata(h, layout) == before, ('cold gate changed held state', label)
        assert value[:2] == [0x3f, 1] and value[13] == 0
    else:
        assert value[13] == 0x457 and h.get32(raw.composition.boot.SESSION + 16) == words(request)[6]
    stream.write(json.dumps(dict(case=label, expected_cold_status=expected, **record)) + '\n')


def transport_controls(h, plan, layout, stream):
    saved = h.checkpoint()
    request = probe(plan, OPEN, next_sequence(h))
    cases = [('wrong-address-interior', dict(address=REQUEST + 4)),
             ('wrong-address-unmapped', dict(address=0x83000000))]
    cases += [('length-' + str(count), dict(length=count)) for count in (0, 255, 257, 4096, 0xffffffff)]
    cases += [('flags-' + str(flags), dict(flags=flags)) for flags in (0, 0x21, 0x801)]
    for label, options in cases:
        h.rewind(saved)
        before = metadata(h, layout)
        flags, response, record = h.mailbox(request, **options)
        assert flags & 0x1c == 0 and response == request, (label, flags)
        assert record['counts'].get('payload_reads', 0) == 0, ('dereference before admission', label)
        assert not record['counts'].get('mailbox_veneer') and metadata(h, layout) == before
        stream.write(json.dumps(dict(case=label, rejected_before_dereference=True, **record)) + '\n')
    for index, value, label in ((0, 0x3e, 'header'), (1, 3, 'api'), (2, 0, 'tag'),
                                (3, 2, 'wire-version'), (4, 252, 'wire-size'), (63, 1, 'tail')):
        h.rewind(saved)
        changed = words(request)
        changed[index] = value
        before = metadata(h, layout)
        flags, response, record = h.mailbox(packed(changed))
        assert flags == 3 and response == packed(changed) and metadata(h, layout) == before
        stream.write(json.dumps(dict(case='bad-' + label, **record)) + '\n')
    h.rewind(saved)
    before = metadata(h, layout)
    h.cpu.mem_write(PAYLOAD, request)
    value, record = h.execute(MAILBOX_VENEER, [PAYLOAD, 256], mstatus=8)
    assert value == 0 and metadata(h, layout) == before and record['counts'].get('payload_reads', 0) == 0
    assert record['counts'].get('mailbox_binding') == 1
    stream.write(json.dumps(dict(case='direct-veneer-IRQ-enabled', rejected=True, **record)) + '\n')
    value, record = h.execute(READY_VENEER, [], mstatus=8)
    assert value == 0 and metadata(h, layout) == before
    stream.write(json.dumps(dict(case='direct-ready-IRQ-enabled', rejected=True, **record)) + '\n')
    h.rewind(saved)
    cold_gate(h, layout, 0, 'unused-zero-session-cold-diagnostic', stream)
    h.rewind(saved)
    h.cpu.mem_write(h.broker + layout['session_bytes'] - 1, b'\x01')
    cold_gate(h, layout, 5, 'stale-unopened-BSS-cold-denial', stream)
    flags, response, record = h.mailbox(request)
    assert flags == 7
    reply(request, response, 5)
    assert bytes(h.cpu.mem_read(h.broker + layout['session_bytes'] - 1, 1)) == b'\x01'
    assert h.get32(h.broker + 4) == 5 and h.get32(ADM + 8) and h.get32(STATE + 16)
    stream.write(json.dumps(dict(case='stale-nonzero-BSS-denied-and-retained', **record)) + '\n')
    h.rewind(saved)
    h.bss_zero()


def identity_controls(h, plan, layout, stream):
    saved = h.checkpoint()
    request = words(probe(plan, HARDWARE, next_sequence(h)))
    labels = ('provider-low', 'provider-high', 'endpoint-low', 'endpoint-high',
              'boot-low', 'boot-high', 'nonce-low', 'nonce-high', 'epoch', 'profile')
    for index, label in enumerate(labels):
        h.rewind(saved)
        before = metadata(h, layout)
        changed = request.copy()
        changed[8 + index] = changed[8 + index] + 1 if index == 8 else changed[8 + index] ^ 1
        expected = 2 if index in (4, 5) else 3
        flags, response, record = h.mailbox(packed(changed))
        assert flags == 7
        reply(packed(changed), response, expected)
        assert metadata(h, layout) == before and not record['counts'].get('table_reads')
        assert not record['counts'].get('extent_reads') and not record['counts'].get('extent_writes')
        stream.write(json.dumps(dict(case='identity-' + label, status=expected, **record)) + '\n')
    h.rewind(saved)
    before = metadata(h, layout)
    changed = request.copy()
    changed[5] = next_sequence(h) - 1
    flags, response, record = h.mailbox(packed(changed))
    assert flags == 7
    reply(packed(changed), response, 4)
    assert metadata(h, layout) == before
    stream.write(json.dumps(dict(case='replayed-serial', **record)) + '\n')
    for address, value, label in ((h.broker + 4, 5, 'session-error'),
                                   (h.broker + 8, 1, 'session-inflight'),
                                   (ADM + 8, 1, 'admission-fault'),
                                   (STATE + 16, 1, 'barrier-fault')):
        h.rewind(saved)
        h.put32(address, value)
        cold_gate(h, layout, 5, label + '-cold-denial', stream)
    h.rewind(saved)


def effect_scope(plan, journal, layout, operation, argument):
    if operation not in (PUBLISH, RESET):
        return {'kind': 'metadata'}
    profile = words(plan)[9]
    count = 137 if profile == 2 else 139
    ordinal = argument if operation == PUBLISH else 128 if argument == 1024 else argument // 8
    slot = count - 1 if ordinal == 128 else ordinal + (2 if profile == 0 else 0)
    offset = layout['extents_offset'] + slot * layout['extent_bytes']
    item = words(journal[offset:offset + layout['extent_bytes']])
    pointer = (item[5] & 0x3fffffff) | 0x40000000
    base = pointer + (argument % 8 * 8192 if operation == RESET and argument != 1024 else 0)
    count = 8192 if operation == RESET or ordinal == 128 else 65536
    return dict(kind='publish' if operation == PUBLISH else 'reset', ordinal=ordinal, slot=slot,
                table=SESSION_TABLE if ordinal == 128 else BLOCK_TABLE + ordinal * 4,
                pointer=pointer, base=base, bytes=count)


def pattern(count, seed):
    value = bytearray([seed]) * count
    value[7::8] = b'\xff' * (count // 8)
    return bytes(value)


def compare_broker(h, oracle, plan, sequence, directory, label):
    layout = oracle.layout
    state = bytes(h.cpu.mem_read(h.broker, layout['session_bytes']))
    assert words(state[:16]) == [layout['session_magic'], 0, 0, sequence]
    exact(state[layout['plan_offset']:layout['owner_offset']], plan, label + '-plan', directory)
    exact(state[layout['owner_offset']:], oracle.journal, label + '-journal', directory)
    assert h.get32(raw.composition.boot.SESSION + 16) == sequence
    assert h.get32(ADM + 4) == h.get32(ADM + 8) == h.get32(STATE + 16) == 0
    assert h.get32(ADM) == h.get32(STATE) == 1
    assert bytes(h.cpu.mem_read(STATE + 4, 12)) == bytes(12)
    assert [h.get32(STATE + 20 + i * 4) for i in range(8)] == [1] * 8
    assert bytes(h.cpu.mem_read(STATE + 52, 52)) == bytes(52)
    return digest(state)


def fault_controls(h, plan, oracle, operation, stream):
    layout, saved = oracle.layout, h.checkpoint()
    journal = oracle.journal
    owner = h.broker + layout['owner_offset']
    ticket = struct.unpack_from('<I', journal, layout['last_ticket_offset'])[0] + 1
    if operation == PUBLISH:
        scope = effect_scope(plan, journal, layout, PUBLISH, 0)
        physical = scope['pointer'] ^ 0xc0000000
        fields = [(10, 0), (11, ticket), (12, 0), (13, 0), (14, physical)]
    else:
        scope = effect_scope(plan, journal, layout, RESET, 0)
        fields = [(10, 0), (11, 1), (12, ticket), (13, 3), (14, 0)]
    for injection in ('barrier', 'admission', 'readback'):
        h.rewind(saved)
        if operation == RESET:
            h.cpu.mem_write(scope['base'], b'\x35' * 8192)
        before_dma = bytearray(h.cpu.mem_read(DMA, DMA_BYTES))
        request = probe(plan, operation, next_sequence(h), fields)
        h.injection = injection
        flags, response, record = h.mailbox(request, scope)
        assert h.injected and flags == 7
        reply(request, response, layout['wire_held'])
        assert h.get32(h.broker + 4) == layout['wire_held'] and h.get32(h.broker + 8) == 1
        expected_error = layout['publication_failed'] if operation == PUBLISH else layout['reset_failed']
        assert h.get32(owner + layout['error_offset']) == expected_error
        assert h.get32(ADM + 8) and h.get32(STATE + 16)
        if operation == PUBLISH:
            assert h.get32(owner + layout['confirmed_offset']) == 0
            assert h.get32(owner + layout['exposure_offset'] + scope['slot'] * 4) == layout['possible']
            assert h.get32(owner + layout['publication_offset']) == ticket
            assert bytes(h.cpu.mem_read(DMA, DMA_BYTES)) == before_dma
        else:
            if injection != 'readback':
                before_dma[scope['base'] - DMA + 7] = 0xff
            assert bytes(h.cpu.mem_read(DMA, DMA_BYTES)) == before_dma
        assert h.get32(owner + layout['allocated_offset']) == (137 if words(plan)[9] == 2 else 139)
        stream.write(json.dumps(dict(case=scope['kind'] + '-' + injection + '-fault',
            retained=True, physical_fault_model=True, **record)) + '\n')
        h.injection = None
        cold_gate(h, layout, 5, scope['kind'] + '-' + injection + '-held-cold-denial', stream)
    h.rewind(saved)


def run_profile(pair, binary, profile, directory):
    directory.mkdir()
    h, plan, prefix = boot_prefix(pair, profile, directory)
    oracle = Oracle(binary, plan, directory)
    layout = oracle.layout
    assert h.get32(h.cold + layout['cold_enrolled_offset']) == 14
    assert h.get32(h.cold + layout['cold_rx_offset']) == 0x92000000
    golden_dma = bytearray(h.cpu.mem_read(DMA, DMA_BYTES))
    golden_sram = bytearray(h.cpu.mem_read(SRAM, 0x4754))
    assert golden_dma == b'\xa5' * DMA_BYTES
    counts, performance = Counter(), {}
    rolling = hashlib.sha256()
    okay = False
    try:
        with JsonLines(directory / 'rpc.jsonl') as stream:
            if profile == 0:
                transport_controls(h, plan, layout, stream)
            else:
                cold_gate(h, layout, 0, 'unused-zero-session-cold-diagnostic', stream)

            def positive(operation, argument=0, generation=0):
                sequence = next_sequence(h)
                request, expected = oracle.request(operation, sequence, argument, generation)
                scope = effect_scope(plan, expected, layout, operation, argument)
                if operation == RESET:
                    # Explicit modeled intervening device data. Generation is
                    # advanced by completed MCU-result messages in both journals.
                    seed = b'\x35' * 8192
                    h.cpu.mem_write(scope['base'], seed)
                    golden_dma[scope['base'] - DMA:scope['base'] - DMA + 8192] = seed
                flags, response, record = h.mailbox(request, scope)
                assert flags == 7, ('outer-mailbox-status', profile, operation, argument, flags)
                reply(request, response)
                assert record['counts'].get('mailbox_veneer') == 1, 'fixed mailbox veneer was not executed'
                assert record['counts'].get('mailbox_binding') == 1, 'actual native binding was not executed'
                state_hash = compare_broker(h, oracle, plan, sequence, directory,
                                            'rpc-' + str(sequence))
                if operation in (PUBLISH, RESET):
                    seed = 0x35 if operation == RESET else 0xa5 if argument == 128 else 0
                    target = pattern(scope['bytes'], seed)
                    exact(bytes(h.cpu.mem_read(scope['base'], scope['bytes'])), target,
                          'rpc-' + str(sequence) + '-extent', directory)
                    golden_dma[scope['base'] - DMA:scope['base'] - DMA + scope['bytes']] = target
                    if operation == PUBLISH:
                        struct.pack_into('<I', golden_sram, scope['table'] - SRAM, scope['pointer'])
                    actual = tuple(record['counts'].get(key, 0) for key in
                                   ('table_writes', 'table_reads', 'extent_writes', 'extent_reads'))
                    required = ((1, 2, 24576, 24576) if scope['bytes'] == 65536 else
                                (1, 2, 1024, 1024)) if operation == PUBLISH else (0, 2, 1024, 1024)
                    assert actual == required, ('complete native I/O engine', scope, actual, required)
                    assert h.get32(scope['table']) == scope['pointer']
                    counts['complete_extent_compares'] += 1
                else:
                    assert not any(record['counts'].get(key, 0) for key in
                                   ('table_writes', 'table_reads', 'extent_writes', 'extent_reads'))
                counts[operation] += 1
                counts['positive_rpc'] += 1
                counts['complete_journal_compares'] += 1
                rolling.update(packed([operation, argument, generation, sequence]))
                rolling.update(request)
                rolling.update(response)
                rolling.update(expected)
                rolling.update(bytes.fromhex(state_hash))
                statistic = performance.setdefault(str(operation), dict(calls=0, wall_ns=0,
                    max_wall_ns=0, max_blocks=0, min_sp=STACK_TOPS[0]))
                statistic['calls'] += 1
                statistic['wall_ns'] += record['wall_ns']
                statistic['max_wall_ns'] = max(statistic['max_wall_ns'], record['wall_ns'])
                statistic['max_blocks'] = max(statistic['max_blocks'], record['counts'].get('blocks', 0))
                statistic['min_sp'] = min(statistic['min_sp'], record['min_sp'])
                stream.write(json.dumps(dict(operation=operation, argument=argument,
                    generation=generation, sequence=sequence, journal_sha256=digest(expected),
                    broker_sha256=state_hash, request_sha256=digest(request), reply_sha256=digest(response),
                    rolling_sha256=rolling.hexdigest(), modeled_MCU_result=operation == MCU_COMPLETE,
                    **record)) + '\n')

            def complete_memory(label):
                exact(bytes(h.cpu.mem_read(DMA, DMA_BYTES)), golden_dma, label + '-all-DMA', directory)
                exact(bytes(h.cpu.mem_read(SRAM, 0x4754)), golden_sram, label + '-native-SRAM', directory)
                h.code_readback()
                counts['complete_memory_compares'] += 1
                stream.write(json.dumps(dict(case=label, complete_DMA_bytes=DMA_BYTES,
                    DMA_sha256=digest(golden_dma), native_SRAM_sha256=digest(golden_sram))) + '\n')
                stream.flush()
                storage_bytes(directory.parent)

            positive(OPEN)
            cold_gate(h, layout, 5, 'building-cold-denial', stream)
            for ordinal in range(137 if profile == 2 else 139):
                positive(ENROLL, ordinal)
            if profile == 0:
                fault_controls(h, plan, oracle, PUBLISH, stream)
            for ordinal in range(129):
                positive(PUBLISH, ordinal)
                if ordinal % 16 == 0:
                    stream.flush()
                    print(json.dumps(dict(profile=profile, publications=ordinal + 1,
                                          rpc=counts['positive_rpc'])), flush=True)
            complete_memory('all-publications')
            cold_gate(h, layout, 5, 'published-before-hardware-cold-denial', stream)
            positive(HARDWARE)
            value, record = h.execute(READY_VENEER, [])
            assert value == 1 and record['counts'].get('ready_veneer') == 1
            assert record['counts'].get('cold_ready_binding') == 1
            stream.write(json.dumps(dict(case='live-fixed-ready-veneer', **record)) + '\n')
            before = metadata(h, layout)
            value, record = h.execute(READY_VENEER, [], mstatus=8)
            assert value == 0 and metadata(h, layout) == before
            assert record['counts'].get('cold_ready_binding') == 1
            stream.write(json.dumps(dict(case='live-ready-IRQ-enabled-denial', **record)) + '\n')
            if profile == 0:
                identity_controls(h, plan, layout, stream)
                fault_controls(h, plan, oracle, RESET, stream)
            cold_gate(h, layout, 0, 'live-cold-diagnostic', stream)
            for generation in (1, 2):
                for session in range(1025):
                    positive(RESET, session, generation)
                    positive(MCU_BEGIN, session, generation)
                    positive(MCU_COMPLETE, session, generation)
                    if session % 128 == 0:
                        stream.flush()
                        print(json.dumps(dict(profile=profile, generation=generation,
                            reset_ids=session + 1, rpc=counts['positive_rpc'])), flush=True)
                complete_memory('generation-' + str(generation))
            positive(CLOSE)
            cold_gate(h, layout, 5, 'closing-cold-denial', stream)
            value, record = h.execute(READY_VENEER, [])
            assert value == 0
            stream.write(json.dumps(dict(case='closing-fixed-ready-veneer', **record)) + '\n')
            complete_memory('closing-retains-all-extents')
        expected_count = 6419 if profile == 2 else 6421
        assert counts['positive_rpc'] == counts['complete_journal_compares'] == expected_count
        assert counts[ENROLL] == (137 if profile == 2 else 139) and counts[PUBLISH] == 129
        assert counts[RESET] == counts[MCU_BEGIN] == counts[MCU_COMPLETE] == 2050
        assert counts['complete_extent_compares'] == 2179 and counts['complete_memory_compares'] == 4
        state = bytes(h.cpu.mem_read(h.broker, layout['session_bytes']))
        (directory / 'broker-final.bin').write_bytes(state)
        (directory / 'oracle-journal-final.bin').write_bytes(oracle.journal)
        summary = dict(profile=profile, counts={str(key): value for key, value in counts.items()},
            performance=performance, layout=layout, exact_code_blocks=len(h.block_cache),
            observer_counts=dict(h.total), final_broker_sha256=digest(state),
            final_journal_sha256=digest(oracle.journal), complete_DMA_sha256=digest(golden_dma),
            rolling_transcript_sha256=rolling.hexdigest(),
            replay_recipe=dict(profile=profile, enrollments=137 if profile == 2 else 139,
                publications=list(range(129)), reset_ids=list(range(1025)), generations=[1, 2],
                per_id=['RESET_NPU', 'MCU_BEGIN', 'MCU_COMPLETE'], reset_data_seed=0x35,
                sequence='V2 server last_sequence + 1; cold diagnostic consumes one serial',
                rolling_encoding='LE32 op,arg,generation,serial; request256; reply256; '
                                 'complete oracle journal30356; binary broker SHA256'),
            prefix_receipt_sha256=file_hash(directory / 'prefix.json'), actual_raw_boot=True,
            modeled_MCU_results=2050, hardware=False, whole_cold_setup=False)
        (directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        okay = True
        return summary
    except BaseException as error:
        failure = dict(profile=profile, error=repr(error), counts=dict(h.counts) if hasattr(h, 'counts') else {},
            current=h.current, injected=h.injected, instruction_budget=RPC_INSTRUCTIONS,
            timeout_us=RPC_TIMEOUT_US, last_native_failure=h.last_failure,
            restored_context_PC=h.cpu.reg_read(r.UC_RISCV_REG_PC),
            unmodeled=h.unmodeled, complete_verdict=False)
        (directory / 'failure.json').write_text(json.dumps(failure, indent=2) + '\n')
        raise
    finally:
        oracle.close(okay)


def inputs_for(manifest, evidence, pair, evidence_path):
    inputs = dict(manifest['inputs'])
    for name, expected in evidence['inputs'].items():
        assert name not in inputs or inputs[name] == expected, ('incompatible source cohorts', name)
        inputs[name] = expected
    files = {Path(__file__), HELPER, raw.composition.native.DTB, evidence_path,
             pair / 'manifest.json', pair / 'CODE.bin', pair / 'DATA.bin'}
    files.update(Path(module.__file__).resolve() for module in list(sys.modules.values())
                 if getattr(module, '__file__', None) and
                 Path(module.__file__).resolve().is_relative_to(ROOT / 'tests/npu'))
    for path in files:
        name = str(path.relative_to(ROOT))
        actual = file_hash(path)
        assert name not in inputs or inputs[name] == actual, ('input cohort drift', name)
        inputs[name] = actual
    verify_inputs(inputs)
    return inputs


def select_output_root(candidate):
    if candidate is None:
        return OUTPUT
    path = Path(candidate)
    path = path if path.is_absolute() else ROOT / path
    resolved = path.resolve(strict=True)
    if (path != resolved or not resolved.is_relative_to(ROOT / '.local') or
            not resolved.is_dir() or not os.access(resolved, os.W_OK)):
        raise ValueError('output root must be an existing writable unaliased private project directory')
    filesystem = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '--target', str(resolved)], text=True).strip()
    if filesystem not in ('ext4', 'xfs', 'btrfs', 'overlay'):
        raise ValueError('native Linux output storage is required')
    return resolved


def main():
    global Pair
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--host-evidence', type=Path, required=True,
                        help='Current passing host-q2 session result.json, with exact input hashes')
    parser.add_argument('--name', required=True)
    parser.add_argument('--native-cold-receipt', type=Path,
                        help='Explicit source-bound native read/cold-observer build receipt; default keeps the reference backend')
    parser.add_argument('--output-root', type=Path,
                        help='Existing writable unaliased native Linux directory under project .local')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    pair, evidence_path = args.pair.resolve(), args.host_evidence.resolve()
    assert pair.is_relative_to(ROOT / '.local') or pair.is_relative_to(ROOT / '.build')
    assert evidence_path.is_relative_to(ROOT / '.local')
    manifest = json.loads((pair / 'manifest.json').read_bytes())
    raw.image.validate((pair / 'CODE.bin').read_bytes(), (pair / 'DATA.bin').read_bytes(), manifest)
    assert manifest['inputs'].get(str(HELPER.relative_to(ROOT))) == file_hash(HELPER) == HELPER_SHA256, \
        'pair must capture the frozen new C oracle source'
    evidence = host_evidence(evidence_path)
    native_adapter = None
    if args.native_cold_receipt is not None:
        import native_cold_observer
        receipt_path = args.native_cold_receipt.resolve(strict=True)
        native_module = native_cold_observer.load_reviewed(receipt_path)
        build = json.loads(receipt_path.read_bytes())
        Pair = native_cold_observer.make_pair_type(Pair, native_module)
        native_adapter = dict(build_receipt=str(receipt_path.relative_to(ROOT)),
            build_receipt_sha256=file_hash(receipt_path), extension=build['extension'],
            cold_observer_API=native_module.COLD_OBSERVER_API_VERSION,
            per_engine_GIL_attached_emulation=True, instruction_and_timeout_limits_unchanged=True)
    inputs = inputs_for(manifest, evidence, pair, evidence_path)
    if native_adapter is not None:
        for absolute, expected in {**build['inputs'], **build['headers'],
                build['extension']['path']:build['extension']['sha256'], str(receipt_path):file_hash(receipt_path)}.items():
            name = str(Path(absolute).relative_to(ROOT))
            assert name not in inputs or inputs[name] == expected, ('incompatible adapter input', name)
            inputs[name] = expected
        verify_inputs(inputs)
    destination = select_output_root(args.output_root) / args.name
    destination.mkdir(parents=True, exist_ok=False)
    binary, command = build_oracle(destination)
    rows = []
    for profile in range(3):
        try:
            rows.append(run_profile(pair, binary, profile, destination / ('profile-' + str(profile))))
        except BaseException as error:
            (destination / 'failure.json').write_text(json.dumps(dict(profile=profile,
                error=repr(error), complete_verdict=False,
                output_bytes=storage_bytes(destination)), indent=2) + '\n')
            raise
        gc.collect()
        verify_inputs(inputs)
    counts = Counter()
    for row in rows:
        counts.update(row['counts'])
    assert counts['positive_rpc'] == counts['complete_journal_compares'] == 19261
    assert counts[str(ENROLL)] == 415 and counts[str(PUBLISH)] == 387
    assert counts[str(RESET)] == counts[str(MCU_BEGIN)] == counts[str(MCU_COMPLETE)] == 6150
    verify_inputs(inputs)
    artifacts = {str(path.relative_to(ROOT)): file_hash(path) for path in sorted(destination.rglob('*'))
                 if path.is_file()}
    result = dict(passed=True, profiles=rows, counts=dict(counts), inputs=inputs, artifacts=artifacts,
        oracle_compile_command=command, host_evidence_sha256=file_hash(evidence_path),
        per_RPC_limits=dict(instructions=RPC_INSTRUCTIONS, timeout_us=RPC_TIMEOUT_US,
                            unique_exact_blocks=MAX_UNIQUE_BLOCKS),
        peak_process_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        storage=dict(output_bytes_before_result=storage_bytes(destination),
                     reserved_output_bytes=OUTPUT_BUDGET_BYTES, per_profile_log_limit=RPC_LOG_BYTES,
                     journal_comparison_bytes=30356, journals_saved_per_profile=1,
                     comparison='complete bytes online, per-RPC and rolling SHA256 retained'),
        actual_raw_pair=True, actual_mailbox_broker=True, actual_raw_boots=3,
        native_cold_adapter=native_adapter,
        raw_boot_limits=dict(instructions_per_run=3000000,
            timeout_us=int(os.environ.get('NPU_EMULATION_TIMEOUT_US', '10000000'))),
        physical_IRQ_entry=False, MCU_authenticated=False, hardware=False,
        whole_cold_setup=False, physical_retirement=False,
        scope=['Raw CODE/DATA bytes supply every executed base/RRO instruction and boot-owned RRO BSS.',
               'Each profile executes actual reset/bootstrap/eight-hart parking/V2 bind and STOP, '
               'then actual cold mailbox/TX/RX enrollment before RRO OPEN.',
               'Provider references, coherent mappings, PLIC delivery, machine IRQ entry and MCU '
               'results are explicit models. Successful MCU replies are host assertions.',
               'The host oracle uses current journal APIs and codec, independently of the RV32 broker/native engine.',
               'New per-RPC limits apply only to this test. Existing 3M/60M-us replay limits are unchanged.'])
    with (destination / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    storage_bytes(destination)
    print(json.dumps(dict(passed=True, positive_rpc=19261, full_journal_compares=19261,
        publications=387, NPU_resets=6150, modeled_MCU_completions=6150,
        receipt=str((destination / 'result.json').relative_to(ROOT)))), flush=True)


if __name__ == '__main__':
    main()
