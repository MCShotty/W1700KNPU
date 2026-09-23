#!/usr/bin/env python3
"""Original core-0 IRQ installation with explicit, fail-closed MMIO models."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import UcError, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_INVALID
from unicorn import riscv_const as r
import unicorn

from test_firmware_memory_layout import NativeMemory, BSS_START, BSS_END, STACK_TOPS
from test_firmware_stop_counterexample import ROOT, INPUT, CODE_SHA, DATA_SHA, END
from test_firmware_mailbox_dispatch import MBOX, PAYLOAD, PHYSICAL, WIFI, ISR, DISPATCH
from emulation_layout import CODE, SRAM, SRAM_BYTES, HEAP, HEAP_BYTES

OUT = ROOT / 'research/checkpoints/2026-09-06-npu-bootstrap/irq-installation.json'
SCRATCH = ROOT / '.local/npu-bootstrap/irq'
GHIDRA = ROOT / ('research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/'
                 'en7581_MT7996_npu_rv32.bin.txt')
PROVIDER = ROOT / ('.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/'
                   'linux-airoha_an7581/linux-6.18.44/drivers/net/ethernet/airoha/airoha_npu.c')
HEADER = PROVIDER.parents[4] / 'include/linux/soc/airoha/airoha_offload.h'
IRQ_TABLE, WIFI_SLOT = SRAM + 0x1850, SRAM + 0xd2c
IRQ8, DEFAULT, SENTINEL = IRQ_TABLE + 32, 0x8400309c, 0x841ff000
TX = 0x50c00000
FUNCTIONS = {int(m.group(1), 16) for m in re.finditer(
    r'^FUNCTION .* @ ram:([0-9a-f]+)$', GHIDRA.read_text(), re.M)}
REGS = [getattr(r, 'UC_RISCV_REG_X' + str(i)) for i in range(32)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class UnmodeledAccess(AssertionError):
    pass


class Installation(NativeMemory):
    """No pre-registration, shared extension ELF or bootstrap policy is loaded."""
    def __init__(self, intercept=None, clock=1, enable_seed=0):
        self.events, self.stub_counts, self.stub_returns = [], {}, {}
        self.intercept = intercept
        self.intercepted = False
        self.hart = 0
        self.tick = 0
        self.stops = set()
        self.stop = None
        self.skip_once = None
        self.mmio = []
        self.csr_events = []
        self.last_csr = None
        self.clear_count = 0
        self.unmodeled = None
        super().__init__()
        self.put32(SENTINEL, 0x00008067)
        self.cpu.mem_map(0x0c000000, 0x201000)
        for base in (0x1ec00000, 0x1ec10000, 0x1ec11000, 0x1fa20000, PAYLOAD):
            self.cpu.mem_map(base, 0x1000)
        self.cpu.mem_map(TX, 0xe000)
        self.cpu.mem_write(TX, b'\xa5' * 0xe000)
        self.put32(MBOX + 0x170, clock)
        self.put32(MBOX + 0x194, 0x13572468)
        for offset in range(0, 28, 4):
            self.put32(0x0c002000 + offset, enable_seed)
        self.cpu.hook_add(UC_HOOK_CODE, self.code_hook)
        self.cpu.hook_add(UC_HOOK_MEM_READ, self.read_hook)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write_hook)
        self.cpu.hook_add(UC_HOOK_MEM_INVALID, self.invalid_hook)

    def record(self, kind, **details):
        event = {'step': self.tick, 'kind': kind,
                 'pc': hex(self.cpu.reg_read(r.UC_RISCV_REG_PC)), **details}
        self.events.append(event)
        return event

    def skip(self, cpu, address, size, data):
        # Inherited hooks land here, retaining explicit evidence of substitutions.
        self.stub_counts[hex(address)] = self.stub_counts.get(hex(address), 0) + 1
        ra = cpu.reg_read(r.UC_RISCV_REG_RA)
        self.stub_returns.setdefault(hex(address), set()).add(hex(ra))
        cpu.reg_write(r.UC_RISCV_REG_A0, self.hart if address == 0x84004212 else 0)
        cpu.reg_write(r.UC_RISCV_REG_PC, ra)

    def code_hook(self, cpu, pc, size, data):
        self.tick += 1
        csr = tuple(cpu.reg_read(reg) for reg in (
            r.UC_RISCV_REG_MSTATUS, r.UC_RISCV_REG_MIE, r.UC_RISCV_REG_MTVEC))
        if csr != self.last_csr:
            self.csr_events.append(self.record('csr-state', mstatus=hex(csr[0]),
                                              mie=hex(csr[1]), mtvec=hex(csr[2])))
            self.last_csr = csr
        if pc in (0x84004212, 0x840048f4):
            return
        if self.intercept == 'before-global-enable' and pc == 0x84004384 and not self.intercepted:
            assert not csr[0] & 8 and self.get32(IRQ8) == DEFAULT
            assert all(self.get32(0x0c002000 + n) & (0xfffffffe if n == 0 else 0xffffffff) == 0
                       for n in range(0, 24, 4))
            self.put32(IRQ8, SENTINEL)
            self.intercepted = True
            self.record('intercept', site='post-plic-init', installed=hex(SENTINEL))
        if self.intercept == 'registration-argument' and pc == 0x84003f2e:
            if cpu.reg_read(r.UC_RISCV_REG_A0) == 8:
                assert self.get32(IRQ8) == DEFAULT
                cpu.reg_write(r.UC_RISCV_REG_A1, SENTINEL)
                self.intercepted = True
                self.record('intercept', site='source8-registration-argument', installed=hex(SENTINEL))
        if pc == SENTINEL:
            # Routing witness only. This is NOT an implementation of strict admission.
            self.record('sentinel-entered', source=cpu.reg_read(r.UC_RISCV_REG_A0))
            cpu.reg_write(r.UC_RISCV_REG_PC, ISR)
            return
        if pc in FUNCTIONS and pc not in (0x84004212, 0x840048f4, 0x8400452a, 0x84004130):
            self.record('entry')
        if pc == 0x84004492:
            self.record('common-mailbox-return')
        if pc == 0x84003254:
            self.record('register-call', source=cpu.reg_read(r.UC_RISCV_REG_A0),
                        callback=hex(cpu.reg_read(r.UC_RISCV_REG_A1)))
        if self.skip_once == pc:
            self.skip_once = None
        elif pc in self.stops:
            self.stop = pc
            self.record('paused')
            cpu.emu_stop()
            return
        if pc in (0x84004130, 0x8400452a):
            self.skip(cpu, pc, size, data)
            return
        if CODE <= pc < CODE + len(self.code) and size == 4:
            word = self.get32(pc)
            if word >> 20 == 0xf14 and word & 0x707f == 0x2073:
                cpu.reg_write(REGS[(word >> 7) & 31], self.hart)
                cpu.reg_write(r.UC_RISCV_REG_PC, pc + 4)
                self.stub_counts['mhartid-csr'] = self.stub_counts.get('mhartid-csr', 0) + 1
                return
    @staticmethod
    def is_memory(address, size):
        return any(start <= address and address + size <= start + length
                   for start, length in ((CODE, 0x201000), (SRAM, SRAM_BYTES),
                                         (HEAP, HEAP_BYTES), (PAYLOAD, 0x1000), (TX, 0xe000)))

    @staticmethod
    def register_model(address, write):
        if address % 4:
            return None
        if 0x0c000004 <= address <= 0x0c000300:
            return 'PLIC priority storage; no arbitration'
        if any(base <= address <= base + 24 for base in (0x0c002000, 0x0c003000)):
            return 'PLIC enable/disable RMW storage; no interrupt delivery'
        if address in (0x0c200000, 0x0c200004):
            return 'PLIC threshold/claim/completion storage; claim explicitly seeded'
        if address == MBOX:
            return 'mailbox interrupt status; successful W1C readback'
        if address in ([MBOX + n for n in range(4, 0x28, 4)] +
                       [MBOX + n for n in (0x30, 0x34, 0x3c, 0x140, 0x170, 0x194, 0x1bc)]):
            return 'mailbox routing/control/MIB storage; no peripheral reset side effect'
        if address in (0x1ec11834, 0x1ec00f00):
            return 'common-init reset/control write storage; no physical effect'
        if address in (0x1ec10000, 0x1ec10004, 0x1ec10008, 0x1ec1000c,
                       0x1ec10010, 0x1ec10024, 0x1ec1002c, 0x1ec10100, 0x1ec10104):
            return 'UART/timer configuration storage; no FIFO/timer IRQ'
        if address == 0x1fa201fc:
            return 'clock-divider strap explicitly zero'
        if address in (0x1ec03048, 0x1ec031c8, 0x1ec03248):
            return 'single-hart mutex; owner readback fixed at 0x10000'
        return None

    def access(self, address, size, value, write):
        if self.is_memory(address, size):
            return
        model = self.register_model(address, write)
        if model is None or size != 4:
            self.unmodeled = (f'{"write" if write else "read"} {address:#x}/{size} '
                              f'at {self.cpu.reg_read(r.UC_RISCV_REG_PC):#x}')
            raise UnmodeledAccess(self.unmodeled)
        if not write and address == MBOX:
            self.put32(address, 0)
        event = self.record('mmio-write' if write else 'mmio-read', address=hex(address),
                            size=size, value=value if write else self.get32(address), model=model)
        self.mmio.append(event)

    def read_hook(self, cpu, access, address, size, value, data):
        self.access(address, size, value, False)

    def write_hook(self, cpu, access, address, size, value, data):
        self.access(address, size, value, True)
        if address == SRAM + 0xbb8:
            self.record('common-once-flag-write', address=hex(address), size=size, value=value)
        if IRQ_TABLE <= address < IRQ_TABLE + 192 * 4 or address <= WIFI_SLOT < address + size:
            self.record('callback-write', address=hex(address), size=size, value=hex(value))
        if PAYLOAD <= address < PAYLOAD + 256:
            self.record('payload-write', offset=address-PAYLOAD, size=size, value=hex(value))
        if TX <= address < TX + 0xe000:
            assert size == 2 and value == 0 and address == TX + self.clear_count * 2
            self.clear_count += 1

    def invalid_hook(self, cpu, access, address, size, value, data):
        self.unmodeled = (f'unmapped access={access} {address:#x}/{size} at '
                           f'{cpu.reg_read(r.UC_RISCV_REG_PC):#x}')
        return False

    def run(self, start, stops):
        self.stops = set(stops)
        self.stop = None
        self.skip_once = start if start in stops else None
        timeout = int(os.environ.get('NPU_EMULATION_TIMEOUT_US', '10000000'))
        assert 1000000 <= timeout <= 120000000
        try:
            self.cpu.emu_start(start, END, count=3000000, timeout=timeout)
        except UcError as exc:
            if self.unmodeled:
                raise UnmodeledAccess(self.unmodeled) from exc
            raise
        pc = self.cpu.reg_read(r.UC_RISCV_REG_PC)
        if pc != END and pc not in stops and self.cpu.query(unicorn.UC_QUERY_TIMEOUT):
            raise TimeoutError(f'Emulator wall budget exhausted at {pc:#x}; instruction/state gates unchanged')
        assert pc == END or pc in stops, hex(pc)
        return pc

    def reset(self, stop=0x8400420a):
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
        return self.run(CODE, [stop])

    def message(self, words, static=False):
        context = self.cpu.context_save()
        before_sram = bytes(self.cpu.mem_read(SRAM, SRAM_BYTES))
        begin = len(self.events)
        data = struct.pack('<' + 'I' * len(words), *words)
        self.cpu.mem_write(PAYLOAD, data + bytes(256 - len(data)))
        self.put32(MBOX + 0x30, PHYSICAL)
        self.put32(MBOX + 0x34, len(data))
        self.put32(MBOX + 0x3c, 1 | ((12 << 11 | 0x20) if static else 0))
        self.cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[0] - 0x1000)
        self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.cpu.reg_write(r.UC_RISCV_REG_A0, 8)
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        assert self.run(DISPATCH, []) == END
        result = {'flags': self.get32(MBOX + 0x3c),
                  'words': list(struct.unpack('<' + 'I' * len(words), self.cpu.mem_read(PAYLOAD, len(data)))),
                  'entries': [e['pc'] for e in self.events[begin:] if e['kind'] in ('entry', 'sentinel-entered')],
                  'writes': [e for e in self.events[begin:] if e['kind'].endswith('write')],
                  'local_sram_unchanged': before_sram == bytes(self.cpu.mem_read(SRAM, SRAM_BYTES))}
        self.cpu.context_restore(context)
        return result


def selected(h, kind, **fields):
    return [event for event in h.events if event['kind'] == kind and
            all(event.get(key) == value for key, value in fields.items())]


def snapshot(h):
    return {'pc': hex(h.cpu.reg_read(r.UC_RISCV_REG_PC)),
            'mstatus': hex(h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS)),
            'mie': hex(h.cpu.reg_read(r.UC_RISCV_REG_MIE)),
            'marker': hex(h.get32(MBOX + 0x140)),
            'common_initialized': h.get32(SRAM + 0x4694),
            'common_once_data_flag': h.get32(SRAM + 0xbb8),
            'irq8': hex(h.get32(IRQ8)), 'wifi0': hex(h.get32(WIFI_SLOT)),
            'core0_enable_word': hex(h.get32(0x0c002000)),
            'txcheck': hex(h.get32(SRAM + 0x469c))}


def assert_version(h, reply, sentinel=False):
    assert reply['flags'] == 7 and reply['words'] == [0x30, 10, 0x457]
    assert reply['local_sram_unchanged']
    assert reply['entries'] == [hex(n) for n in (
        DISPATCH, *([SENTINEL] if sentinel else []), ISR, WIFI, 0x840101a6, 0x8400d998,
        0x840103aa, 0x840104ea, *([0x840106c0] * 4), 0x840104ea, 0x840106c0)], reply['entries']
    payload = [event for event in reply['writes'] if event['kind'] == 'payload-write']
    assert len(payload) == 1
    assert payload == [dict(payload[0], pc='0x840101dc', offset=8, size=4, value='0x457')], payload
    assert h.get32(SRAM + 0x170) == 0x840101a6
    assert h.get32(SRAM + 0x469c) == 0
    assert h.clear_count == 0


def ordering_cases():
    rows = []
    canonical = None
    for clock in (1, 0):
        for seed in (0, 0xffffffff):
            h = Installation(clock=clock, enable_seed=seed)
            assert h.get32(SRAM + 0xbb8) == 1
            assert h.reset(0x84004400) == 0x84004400
            flag_writes = selected(h, 'common-once-flag-write')
            assert len(flag_writes) == 1
            assert flag_writes[0]['pc'] == '0x840043ac' and flag_writes[0]['value'] == 0
            marker_state = snapshot(h)
            assert marker_state['marker'] == '0xffffffff'
            assert marker_state['irq8'] == hex(DEFAULT) and marker_state['wifi0'] == '0x0'
            assert marker_state['mstatus'] == '0x8' and marker_state['mie'] == '0x800'
            assert marker_state['common_initialized'] == marker_state['common_once_data_flag'] == 0
            assert h.run(0x84004400, [0x8400420a]) == 0x8400420a
            assert h.get32(SRAM + 0x4694) == 1
            assert h.get32(IRQ8) == ISR and h.get32(WIFI_SLOT) == WIFI
            calls = selected(h, 'register-call')
            assert [e['source'] for e in calls] == [22, 8, 9, 10, 11, 12, 13, 14]
            assert [e['callback'] for e in calls] == [hex(0x840047a0)] + [hex(ISR)] * 7
            defaults = selected(h, 'callback-write', pc='0x84003360')
            assert [int(e['address'], 16) for e in defaults] == list(range(IRQ_TABLE, IRQ_TABLE + 768, 4))
            assert all(e['value'] == hex(DEFAULT) for e in defaults)
            slot8 = selected(h, 'callback-write', address=hex(IRQ8))
            assert [(e['pc'], e['value']) for e in slot8] == [
                ('0x84000096', '0x0'), ('0x84003360', hex(DEFAULT)), ('0x84003132', hex(ISR))]
            wifi = selected(h, 'callback-write', address=hex(WIFI_SLOT))
            assert [(e['pc'], e['value']) for e in wifi] == [
                ('0x84000096', '0x0'), ('0x840103c8', '0x0'), ('0x84003f80', hex(WIFI))]
            marker = selected(h, 'mmio-write', address=hex(MBOX + 0x140))
            assert len(marker) == 1 and marker[0]['pc'] == '0x840043fc' and marker[0]['value'] == 0xffffffff
            enables = selected(h, 'mmio-write', pc='0x84003232')
            assert len(enables) == 8
            assert enables[0]['value'] == (seed & 1) | (1 << 23)
            assert enables[1]['value'] == (seed & 1) | (1 << 23) | (1 << 9)
            global_enable = [e for e in h.csr_events if e['pc'] == '0x840043a2'][0]
            assert global_enable['mstatus'] == '0x8' and global_enable['mie'] == '0x800'
            assert defaults[-1]['step'] < global_enable['step'] < marker[0]['step'] < enables[0]['step']
            assert enables[0]['step'] < slot8[-1]['step'] < enables[1]['step'] < wifi[-2]['step'] < wifi[-1]['step']
            entries = selected(h, 'entry')
            assert next(e['step'] for e in entries if e['pc'] == '0x84000164') > wifi[-1]['step']
            version = h.message([0x30, 10, 0])
            assert_version(h, version)
            rows.append({'clock_mib12': clock, 'initial_plic_enable_words': hex(seed),
                         'common_once_flag_address': hex(SRAM + 0xbb8),
                         'common_once_flag_initial_value': 1, 'common_once_flag_writes': flag_writes,
                         'marker_state': marker_state, 'wait_state': snapshot(h),
                         'first_uart_enable': enables[0], 'first_mailbox_enable': enables[1],
                         'slot8_writes': slot8, 'wifi0_writes': wifi,
                         'version_reply': version})
            if canonical is None:
                canonical = h
    return rows, canonical


def interception_cases():
    rows = []
    for mode in ('before-global-enable', 'registration-argument'):
        h = Installation(intercept=mode)
        h.reset(0x84003f32)
        assert h.intercepted and h.get32(IRQ8) == SENTINEL and h.get32(WIFI_SLOT) == 0
        before_wifi = snapshot(h)
        early_version = h.message([0x30, 10, 0])
        assert early_version['flags'] == 3 and early_version['words'][2] == 0
        assert early_version['entries'] == [hex(n) for n in (DISPATCH, SENTINEL, ISR)]
        assert h.run(0x84003f32, [0x84003f80]) == 0x84003f80
        early_address = h.message([0x10, 32, 0x90c00000])
        assert early_address['flags'] == 3 and h.get32(SRAM + 0x469c) == 0
        assert h.run(0x84003f80, [0x84003f84]) == 0x84003f84
        at_wifi_store = snapshot(h)
        first_version = h.message([0x30, 10, 0])
        assert_version(h, first_version, sentinel=True)
        assert h.run(0x84003f84, [0x8400420a]) == 0x8400420a
        wait_version = h.message([0x30, 10, 0])
        assert_version(h, wait_version, sentinel=True)
        assert h.get32(IRQ8) == SENTINEL
        address_reply = h.message([0x10, 32, 0x90c00000])
        assert address_reply['flags'] == 7 and h.get32(SRAM + 0x469c) == TX
        assert h.run(0x8400420a, [0x8400e330]) == 0x8400e330
        assert h.clear_count == 0x7000 and bytes(h.cpu.mem_read(TX, 0xe000)) == bytes(0xe000)
        assert h.get32(IRQ8) == SENTINEL and h.get32(WIFI_SLOT) == WIFI
        assert not selected(h, 'callback-write', address=hex(IRQ8), value=hex(ISR))
        boundary = None
        try:
            h.run(0x8400e330, [0x84000188])
        except UnmodeledAccess as exc:
            boundary = str(exc)
        assert boundary, 'Native Wi-Fi initialization unexpectedly completed without peripheral models'
        assert boundary == 'unmapped access=20 0x1ec0f200/4 at 0x8400d1c0', boundary
        rows.append({'mode': mode, 'before_wifi_table': before_wifi,
                     'early_version_reply': early_version, 'early_api32_reply': early_address,
                     'first_wifi_table_valid': at_wifi_store, 'first_version_reply': first_version,
                     'api32_wait_version_reply': wait_version, 'api32_reply': address_reply,
                     'native_tx_clear_bytes': h.clear_count * 2,
                     'intercepts': selected(h, 'intercept'),
                     'slot8_writes': selected(h, 'callback-write', address=hex(IRQ8)),
                     'unmodeled_downstream_boundary': boundary,
                     'last_state': snapshot(h),
                     'boundary_scope': 'Sentinel tail-forwards original ISR; no strict validation is implemented.'})
    return rows


def binding_controls():
    rows = []
    for stop, table in ((0x84000074, IRQ8), (0x84004348, IRQ8), (0x84003f00, WIFI_SLOT)):
        h = Installation()
        h.reset(stop)
        h.put32(table, SENTINEL)
        h.run(stop, [0x84004492])
        assert h.get32(table) == (ISR if table == IRQ8 else WIFI)
        rows.append({'name': 'early-binding-overwritten', 'seed_pc': hex(stop), 'table': hex(table),
                     'observed': hex(h.get32(table)),
                     'writes': selected(h, 'callback-write', address=hex(table))})
    h = Installation()
    h.reset(0x84003f32)
    assert h.get32(IRQ8) == ISR and h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
    early = snapshot(h)
    h.run(0x84003f32, [0x84004492])
    h.put32(IRQ8, SENTINEL)
    rows.append({'name': 'post-mailbox-init-rebinding-is-late', 'earlier_enabled_state': early,
                 'late_rebind_pc': '0x84004492'})
    # The registration API refuses replacement; init reruns still clear Wi-Fi data.
    h = Installation(intercept='before-global-enable')
    h.reset(0x84004492)
    context = h.cpu.context_save()
    begin = len(h.events)
    h.cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[0] - 0x1000)
    h.cpu.reg_write(r.UC_RISCV_REG_RA, END)
    h.run(0x84003f00, [])
    assert h.get32(IRQ8) == SENTINEL and h.get32(WIFI_SLOT) == WIFI
    assert not [e for e in h.events[begin:] if e['kind'] == 'callback-write' and e['address'] == hex(IRQ8)]
    rows.append({'name': 'native-reinitialization-retains-nondefault-irq8',
                 'irq8': hex(h.get32(IRQ8)),
                 'wifi_writes': [e for e in h.events[begin:] if e['kind'] == 'callback-write' and e['address'] == hex(WIFI_SLOT)]})
    h.cpu.context_restore(context)
    static = h.message([0], static=True)
    assert h.get32(IRQ8) == SENTINEL and h.get32(WIFI_SLOT) == PHYSICAL
    assert hex(SENTINEL) in static['entries']
    rows.append({'name': 'static-function12-bypasses-wifi-rebinding', 'reply': static,
                 'irq8': hex(h.get32(IRQ8)), 'wifi0_after_static': hex(h.get32(WIFI_SLOT)),
                 'scope': 'Forwarding sentinel deliberately does not filter this unsafe legacy path.'})
    class MissingRegister(Installation):
        @staticmethod
        def register_model(address, write):
            if address == 0x1ec11834:
                return None
            return Installation.register_model(address, write)
    try:
        MissingRegister().reset()
    except UnmodeledAccess as exc:
        assert str(exc) == 'write 0x1ec11834/4 at 0x840043d2'
        rows.append({'name': 'missing-MMIO-model-fails-closed', 'error': str(exc)})
    else:
        raise AssertionError('Missing MMIO model was silently accepted')
    return rows


def source_evidence():
    source = PROVIDER.read_text()
    header = HEADER.read_text()
    get_enum = re.search(r'enum airoha_npu_wlan_get_cmd \{(.*?)\};', header, re.S).group(1)
    names = re.findall(r'\bWLAN_FUNC_GET_WAIT_\w+', get_enum)
    assert names.index('WLAN_FUNC_GET_WAIT_NPU_VERSION') == 10
    assert 'NPU_OP_SET = 1,' in source and 'NPU_OP_GET,' in source
    probe = source.split('static int airoha_npu_probe(', 1)[1].split('\nstatic ', 1)[0]
    assert probe.index('REG_CR_BOOT_TRIGGER') < probe.index('WLAN_FUNC_GET_WAIT_NPU_VERSION') < probe.index('platform_set_drvdata')
    assert 'airoha_npu_wlan_init_memory(' not in probe
    get = source.split('static int airoha_npu_wlan_msg_get(', 1)[1].split('\nstatic ', 1)[0]
    assert 'wlan_data->func_type = NPU_OP_GET;' in get
    assert '__airoha_npu_send_msg(npu, NPU_FUNC_WIFI, wlan_data, len,' in get
    send = source.split('static int __airoha_npu_send_msg(', 1)[1].split('\nstatic ', 1)[0]
    assert 'struct airoha_npu_core *core = &npu->cores[0];' in send
    assert send.index('REG_CR_MBQ0_CTRL(0)') < send.index('REG_CR_MBQ0_CTRL(1)')
    assert send.index('regmap_write(npu->regmap, REG_CR_MBQ0_CTRL(3)') < send.index('regmap_write(npu->regmap, REG_CR_MBQ0_CTRL(2)')
    assert 'core->buf + len - reply_len' in send
    spans = []
    text = GHIDRA.read_text()
    addresses = [0x84000000, 0x84000104, 0x84000164, 0x840030b2, 0x84003106,
                 0x84003200, 0x84003254, 0x840032e2, 0x840037c8, 0x84003a9c,
                 0x84003cd6, 0x84003f00, 0x84004348, 0x840047d2, 0x84004e76,
                 0x84005296, 0x8400e330, 0x8400d1a0, 0x8400d998, 0x840101a6]
    for address in addresses:
        match = re.search(r'^FUNCTION [^\n]* @ ram:' + f'{address:08x}' + r'\n.*?(?=^FUNCTION |\Z)', text, re.M | re.S)
        assert match, hex(address)
        block = match.group()
        assert 'decompiled=true' in block
        spans.append({'address': hex(address), 'first_line': text[:match.start()].count('\n') + 1,
                      'last_line': text[:match.end()].count('\n'),
                      'normalized_text_sha256': hashlib.sha256(block.encode()).hexdigest()})
    return {'provider_sha256': sha(PROVIDER), 'header_sha256': sha(HEADER),
            'provider_path': str(PROVIDER.relative_to(ROOT)), 'header_path': str(HEADER.relative_to(ROOT)),
            'ghidra_sha256': sha(GHIDRA), 'function_spans': spans,
            'version_wire': {'core': 0, 'function': 0, 'flags': 1, 'length': 12,
                             'payload_words': [0x30, 10, 0], 'reply_words': [0x30, 10, 0x457],
                             'write_order_rv32_registers': ['0x1ec0c030', '0x1ec0c034', '0x1ec0c03c', '0x1ec0c038'],
                             'provider_regmap_offsets': ['0x30c030', '0x30c034', '0x30c03c', '0x30c038'],
                             'completion_register': '0x1ec0c03c', 'response_payload_offset': 8,
                             'response_payload_bytes': 4, 'fallback_store_pc': '0x840101dc',
                             'fallback_is_not_a_successfully_parsed_version': True},
            'scope': 'Provider ordering is checked source, not executed ARM64 or a live attach schedule.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    target = args.output.resolve()
    assert target == OUT.resolve() or target.is_relative_to(SCRATCH.resolve())
    helpers = ['test_firmware_memory_layout.py', 'test_firmware_mailbox_dispatch.py',
               'test_firmware_stop_irqs.py', 'test_firmware_stop_counterexample.py',
               'test_boot_txbuf_extent.py', 'emulation_layout.py']
    before = {name: sha(ROOT / 'tests/npu' / name) for name in helpers}
    assert sha(GHIDRA) == '1536a9972838ca7c02da77629e784b392af919c5d25368478aff4d0c2422e2ca'
    order, h = ordering_cases()
    print('original-order cases=4 PASS', flush=True)
    interception = interception_cases()
    print('interception paths=2 PASS', flush=True)
    controls = binding_controls()
    print(f'binding controls={len(controls)} PASS', flush=True)
    source = source_evidence()
    assert bytes(h.cpu.mem_read(CODE, len(h.code))) == (INPUT / 'en7581_MT7996_npu_rv32.bin').read_bytes()
    assert before == {name: sha(ROOT / 'tests/npu' / name) for name in helpers}
    result = {'passed': True, 'unicorn': unicorn.__version__,
              'code_sha256': CODE_SHA, 'data_sha256': DATA_SHA,
              'test_sha256': sha(Path(__file__)), 'unchanged_helpers': before,
              'ordering_cases': order, 'interception_cases': interception,
              'binding_controls': controls, 'source_evidence': source,
              'canonical_native_events': h.events, 'stub_counts': h.stub_counts,
              'stub_returns': {k: sorted(v) for k, v in h.stub_returns.items()},
              'sites': {hex(pc): bytes(h.cpu.mem_read(pc, size)).hex() for pc, size in
                        [(0x84004380, 4), (0x84004384, 4), (0x8400439e, 4), (0x840043fc, 4),
                         (0x84003f2e, 4), (0x84003132, 2), (0x84003f80, 4), (0x84004492, 4)]},
              'scope': 'Original reset/common init/allocator/TXcheck wait and mailbox instructions, serialized saved-frame IRQ calls and explicit MMIO/printf/hart/delay stubs. No strict bootstrap policy, candidate build, hardware action, physical interrupt/cache/DMA proof or complete Wi-Fi main return.'}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(order) + len(interception) + len(controls),
                      'output_sha256': sha(target)}))


if __name__ == '__main__':
    main()
