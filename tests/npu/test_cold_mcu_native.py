#!/usr/bin/env python3
"""Execute compiled MCU/cold cleanup; firmware, MMIO and other kernel APIs are models."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import time

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile
from elftools.elf.enums import ENUM_RELOC_TYPE_AARCH64 as RELOC
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_PROT_READ, UC_PROT_EXEC
from unicorn import arm64_const as arm

import test_cold_probe_lifetime as extraction

ROOT = extraction.ROOT
PRODUCER_SHA = 'a840d3cccb1d0bd8cc60a856d1a1bb9723dfc05af73484d955a33978a458d22f'
TEXT, DATA, DEV, STACK, OPS, PHYS, END = (
    0x10000000, 0x12000000, 0x40000000, 0x41000000, 0x42000000, 0x43000000, 0x1f000000)
WR, RMW = 0x18000000, 0x18001000
REGS = [getattr(arm, 'UC_ARM64_REG_X' + str(index)) for index in range(29)] + [arm.UC_ARM64_REG_X29, arm.UC_ARM64_REG_X30]
SELECTED = ('mt7996_cleanup_device', 'mt7996_mcu_exit', 'mt7996_dma_cleanup', 'mt7996_dma_disable')
MODELED = {'mt7996_npu_rro_reset_close', 'mt7996_npu_rro_reset_join',
    'disable_work_sync', 'disable_delayed_work_sync', 'mt7996_unregister_thermal',
    'mt76_unregister_device', 'kthread_park', 'mt7996_coredump_unregister',
    'mt7996_pci_shutdown_irqs', 'mt76_npu_shutdown_irqs', 'mt76_napi_cleanup',
    'skb_queue_purge_reason', 'mt7996_tx_token_put', 'dmam_free_coherent',
    'mt7996_rro_msdu_page_map_free', 'mt76_npu_rro_close', 'mt76_dma_cleanup',
    'mt76_mcu_send_and_get_msg', '____mt76_poll_msec', '_dev_err'}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class Module:
    def __init__(self, path, expected):
        assert sha(path) == expected
        self.raw = path.read_bytes()
        elf = ELFFile(io.BytesIO(self.raw))
        assert elf['e_machine'] == 'EM_AARCH64' and elf.little_endian
        symbols = list(elf.get_section_by_name('.symtab').iter_symbols())
        table = {symbol.name:symbol for symbol in symbols if symbol.name}
        self.functions = {name:(TEXT + table[name]['st_value'], table[name]['st_size']) for name in SELECTED}
        index, = {table[name]['st_shndx'] for name in SELECTED}
        section = elf.get_section(index)
        self.text = bytearray(section.data())
        assert len(self.text) < 0x100000
        self.maps = {index:(TEXT, bytes(self.text))}
        self.calls, self.indirect = {}, {}
        self.relocations = []
        engine = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        self.instructions = {}
        for name, (start, size) in self.functions.items():
            assert 0 < size <= 8192 and size % 4 == 0
            instructions = list(engine.disasm(self.text[start - TEXT:start - TEXT + size], start))
            assert len(instructions) * 4 == size
            self.instructions[name] = [(item.address, item.mnemonic, item.op_str) for item in instructions]
        for relocations in elf.iter_sections():
            if relocations['sh_type'] != 'SHT_RELA' or relocations['sh_info'] != index:
                continue
            targets = elf.get_section(relocations['sh_link'])
            for relocation in relocations.iter_relocations():
                offset = relocation['r_offset']
                pc = TEXT + offset
                if not self.contains(pc):
                    continue
                target = targets.get_symbol(relocation['r_info_sym'])
                kind = relocation['r_info_type']
                word = struct.unpack_from('<I', self.text, offset)[0]
                if kind == RELOC['R_AARCH64_CALL26']:
                    assert word & 0xfc000000 == 0x94000000
                    self.calls[pc] = target.name
                    if target.name in SELECTED:
                        address = TEXT + target['st_value'] + relocation['r_addend']
                        delta = address - pc
                        assert delta % 4 == 0 and -(1 << 27) <= delta < 1 << 27
                        word = 0x94000000 | ((delta >> 2) & 0x3ffffff)
                        struct.pack_into('<I', self.text, offset, word)
                    continue
                target_index = target['st_shndx']
                assert isinstance(target_index, int)
                if target_index not in self.maps:
                    target_section = elf.get_section(target_index)
                    data = target_section.data()
                    assert len(data) < 0x100000 and not target_section['sh_flags'] & 4
                    self.maps[target_index] = (DATA + (len(self.maps) - 1) * 0x100000, data)
                address = self.maps[target_index][0] + target['st_value'] + relocation['r_addend']
                if kind == RELOC['R_AARCH64_ADR_PREL_PG_HI21']:
                    assert word & 0x9f000000 == 0x90000000
                    pages = (address >> 12) - (pc >> 12)
                    assert -(1 << 20) <= pages < 1 << 20
                    immediate = pages & 0x1fffff
                    word = (word & ~0x60ffffe0) | ((immediate & 3) << 29) | ((immediate >> 2) << 5)
                else:
                    assert kind == RELOC['R_AARCH64_ADD_ABS_LO12_NC']
                    assert word & 0x7f000000 == 0x11000000 and not word & (1 << 22)
                    word = (word & ~0x003ffc00) | ((address & 4095) << 10)
                struct.pack_into('<I', self.text, offset, word)
                self.relocations.append(dict(pc=pc, type=kind, target=address))
        for name, instructions in self.instructions.items():
            for pc, mnemonic, operands in instructions:
                if mnemonic == 'blr':
                    self.indirect[pc] = getattr(arm, 'UC_ARM64_REG_' + operands.upper())
                if mnemonic != 'bl' or pc in self.calls:
                    continue
                word = struct.unpack_from('<I', self.text, pc - TEXT)[0]
                delta = (word & 0x3ffffff) << 2
                if delta & (1 << 27):
                    delta -= 1 << 28
                target_address = pc + delta
                matches = [symbol.name for symbol in symbols if symbol['st_shndx'] == index and
                    symbol['st_info']['type'] == 'STT_FUNC' and TEXT + symbol['st_value'] == target_address]
                assert len(matches) == 1, ('unresolved-local-BL', hex(pc), matches)
                self.calls[pc] = matches[0]
        assert set(self.calls.values()) - set(SELECTED) <= MODELED
        # These operands bind this fixture's offsets to the retained compiler output.
        expected = {'mt7996_cleanup_device': (
            ('ldrb', 'w2, [x1, #0xa29]'), ('ldr', 'x22, [x0, #0x3e78]'),
            ('ldr', 'x0, [x20, #0x860]'), ('strb', 'wzr, [x2, #0x71]')),
            'mt7996_mcu_exit': (('ldr', 'x3, [x19, #0x850]'), ('ldr', 'x0, [x19, #0x6a10]'))}
        for name, required in expected.items():
            actual = {(mnemonic, operands) for _, mnemonic, operands in self.instructions[name]}
            assert set(required) <= actual, ('fixture-ABI-operands', name)
        self.text_index = index

    def contains(self, pc):
        return any(start <= pc < start + size for start, size in self.functions.values())


class Replay:
    def __init__(self, module, case, mutation=None):
        self.module, self.case = module, case
        self.events, self.logs, self.writes, self.rmws = [], [], [], []
        self.instructions, self.native_entries = 0, {name:0 for name in SELECTED}
        self.registers = {}
        self.cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        text = bytearray(module.text)
        self.nops = set()
        if mutation == 'invert-MCU-poll-branch':
            candidates = [pc for pc, mnemonic, operands in module.instructions['mt7996_mcu_exit']
                if mnemonic == 'tbz' and operands.startswith('w0, #0,')]
            pc, = candidates
            word = struct.unpack_from('<I', text, pc - TEXT)[0]
            struct.pack_into('<I', text, pc - TEXT, word ^ 0x01000000)
        elif mutation in ('omit-DMA-cleanup', 'omit-firmware-poll'):
            target = 'mt7996_dma_cleanup' if mutation == 'omit-DMA-cleanup' else '____mt76_poll_msec'
            pc, = [pc for pc, name in module.calls.items() if name == target]
            struct.pack_into('<I', text, pc - TEXT, 0xd503201f)
            self.nops.add(pc)
        else:
            assert mutation is None
        for index, (address, data) in module.maps.items():
            payload = bytes(text) if index == module.text_index else data
            size = (len(payload) + 4095) & ~4095
            self.cpu.mem_map(address, size)
            self.cpu.mem_write(address, payload)
            self.cpu.mem_protect(address, size, UC_PROT_READ | (UC_PROT_EXEC if index == module.text_index else 0))
        for address, size in ((DEV,0x20000), (STACK,0x10000), (OPS,0x1000), (PHYS,0x10000), (END,0x1000)):
            self.cpu.mem_map(address, size)
        self.put64(DEV + 0x850, OPS)
        self.put64(OPS + 8, WR)
        self.put64(OPS + 16, RMW)
        self.put64(DEV + 0x860, OPS if case['mcu'] else 0)
        self.put64(DEV + 0x3e78, OPS if case['dma'] else 0)
        self.put64(DEV + 0x6a10, OPS if case['hif2'] else 0)
        self.put64(DEV + 0x870, OPS)
        self.put64(DEV + 0x878, OPS)
        self.put64(DEV + 0x3e98, OPS)
        self.put64(DEV + 0x3ea8, 0xfeedface)
        self.put32(DEV + 0x3e90, int(case.get('hwrro', False)))
        self.cpu.mem_write(DEV + 0xb212, bytes([int(case.get('owned_rro', False))]))
        self.cpu.mem_write(DEV + 0x6a29, bytes([int(case.get('already_started', False))]))
        self.cpu.mem_write(DEV + 0xa071, b'\x01')
        for index, registered in enumerate((True, False, True)):
            address, base = PHYS + index * 0x1000, PHYS + 0x8000 + index * 0x1000
            self.put64(DEV + 0x6968 + index * 8, address)
            self.put64(address, base)
            self.put64(base + 0x18, 2 if registered else 0)
        self.cpu.hook_add(UC_HOOK_CODE, self.code)

    def put64(self, address, value):
        self.cpu.mem_write(address, struct.pack('<Q', value))

    def put32(self, address, value):
        self.cpu.mem_write(address, struct.pack('<I', value))

    def value64(self, address):
        return struct.unpack('<Q', self.cpu.mem_read(address, 8))[0]

    def returned(self, pc, value=0):
        for index in range(18):
            self.cpu.reg_write(REGS[index], value & ((1 << 64) - 1) if index == 0 else 0xbad00000 + index)
        self.cpu.reg_write(arm.UC_ARM64_REG_NZCV, 0xa0000000)
        self.cpu.reg_write(arm.UC_ARM64_REG_X30, pc + 4)
        self.cpu.reg_write(arm.UC_ARM64_REG_PC, pc + 4)

    def code(self, cpu, pc, size, _data):
        assert size == 4 and self.module.contains(pc), ('unexpected-execution', hex(pc))
        self.instructions += 1
        for name, (start, _) in self.module.functions.items():
            if pc == start:
                self.native_entries[name] += 1
                self.events.append(dict(kind='native-entry', name=name))
        if pc in self.nops:
            return
        if pc not in self.module.calls and pc not in self.module.indirect:
            return
        args = tuple(cpu.reg_read(REGS[index]) for index in range(6))
        if pc in self.module.indirect:
            target = cpu.reg_read(self.module.indirect[pc])
            assert args[0] == DEV
            if target == WR:
                assert args[1] in (0xe0010, 0xe0020) and args[2] == 1
                self.writes.append(dict(register=args[1], value=args[2]))
                self.events.append(dict(kind='modeled-MMIO-write', register=args[1], value=args[2]))
                self.returned(pc)
            else:
                assert target == RMW, ('unknown-MMIO-callback', hex(target))
                assert args[1] in (0xd4100, 0xd8100, 0xd4208, 0xd8208)
                old = self.registers.get(args[1], 0xffffffff)
                value = ((old & ~args[2]) | args[3]) & 0xffffffff
                self.registers[args[1]] = value
                self.rmws.append(dict(register=args[1], clear=args[2], set=args[3], before=old, after=value))
                self.events.append(dict(kind='modeled-MMIO-rmw', register=args[1], clear=args[2], set=args[3]))
                self.returned(pc, value)
            return
        name = self.module.calls[pc]
        if name in SELECTED:
            return
        assert name in MODELED, name
        event = dict(kind='modeled-call', name=name, args=list(args))
        self.events.append(event)
        if name == 'mt76_mcu_send_and_get_msg':
            assert args[:2] == (DEV, 0x12000f) and args[3:] == (12, 0, 0), 'power-off-command-framing'
            packet = bytes(cpu.mem_read(args[2], args[3]))
            assert packet == bytes.fromhex('000000000000080001000000'), 'power-off-packet'
            event['synthetic_request_hex'] = packet.hex()
            self.returned(pc, self.case['send_error'])
        elif name == '____mt76_poll_msec':
            assert args == (DEV, 0xe00f0, 7, 1, 1000, 10), 'firmware-state-poll-arguments'
            self.returned(pc, int(self.case['poll']))
        elif name == '_dev_err':
            assert args[0] == OPS
            message = bytes(cpu.mem_read(args[1], 128)).split(b'\0', 1)[0].decode('ascii')
            self.logs.append(message)
            event['message'] = message
            self.returned(pc)
        else:
            if name == 'dmam_free_coherent':
                raise AssertionError('unexpected-live-RRO-managed-allocation')
            self.returned(pc)

    def call(self):
        self.cpu.reg_write(arm.UC_ARM64_REG_SP, STACK + 0xf000)
        self.cpu.reg_write(arm.UC_ARM64_REG_X30, END)
        self.cpu.reg_write(arm.UC_ARM64_REG_X0, DEV)
        start = self.module.functions['mt7996_cleanup_device'][0]
        before = self.instructions
        then = time.monotonic_ns()
        self.cpu.emu_start(start, END, timeout=5_000_000, count=1_000_000)
        assert self.cpu.reg_read(arm.UC_ARM64_REG_PC) == END, 'bounded-cleanup-return'
        assert self.instructions - before < 1_000_000 and time.monotonic_ns() - then < 5_000_000_000

    def run(self):
        self.call()
        names = [event['name'] for event in self.events if event['kind'] == 'modeled-call']
        if self.case.get('already_started', False):
            assert names == [] and self.instructions == 4, 'already-started-cleanup-is-inert'
            return self.result()
        assert self.cpu.mem_read(DEV + 0x6a29, 1) == b'\x01'
        assert self.cpu.mem_read(DEV + 0xa071, 1) == b'\x00'
        assert self.value64(DEV + 0x3ea8) == 0
        assert names.count('disable_work_sync') == 5 and names.count('disable_delayed_work_sync') == 6
        assert names.count('mt7996_tx_token_put') == 1, 'TX-token-retirement-boundary'
        assert names.index('mt7996_pci_shutdown_irqs') < names.index('mt76_npu_shutdown_irqs') < names.index('mt76_napi_cleanup') < names.index('mt7996_tx_token_put'), 'CPU-ingress-before-token-retirement'
        expected_mcu = int(self.case['mcu'])
        assert names.count('mt76_mcu_send_and_get_msg') == expected_mcu, 'power-off-send-count'
        assert names.count('____mt76_poll_msec') == expected_mcu, 'firmware-state-poll-count'
        if expected_mcu:
            assert names.index('mt76_mcu_send_and_get_msg') < names.index('____mt76_poll_msec') < names.index('mt7996_pci_shutdown_irqs'), 'MCU-before-ingress-shutdown'
            assert names.index('skb_queue_purge_reason') < names.index('mt7996_pci_shutdown_irqs'), 'MCU-response-purge-before-ingress-shutdown'
        purge_indices = [index for index, name in enumerate(names) if name == 'skb_queue_purge_reason']
        assert names.index('mt76_napi_cleanup') < purge_indices[-1] < names.index('mt7996_tx_token_put'), 'final-response-purge-before-token-retirement'
        expected_logs = [] if not self.case['mcu'] or self.case['poll'] else [
            'Timeout for initializing firmware\n', 'Failed to exit mcu\n']
        assert self.logs == expected_logs, 'MCU-failure-log-contract'
        registers = [0xe0010, 0xe0020] if self.case['hif2'] else [0xe0010]
        expected_writes = registers if self.case['mcu'] and self.case['poll'] else []
        assert [entry['register'] for entry in self.writes] == expected_writes, 'firmware-ownership-write-contract'
        assert names.count('mt76_dma_cleanup') == int(self.case['dma']), 'DMA-cleanup-boundary'
        assert self.native_entries['mt7996_dma_disable'] == int(self.case['dma']), 'native-DMA-disable-boundary'
        expected_rmws = []
        if self.case['dma']:
            expected_rmws = [(0xd4100, 0x30, 0), (0xd4100, 0, 0x30)]
            if self.case['hif2']:
                expected_rmws += [(0xd8100, 0x30, 0), (0xd8100, 0, 0x30)]
            expected_rmws.append((0xd4208, 0x18200005, 0))
            if self.case['hif2']:
                expected_rmws.append((0xd8208, 0x18200005, 0))
        assert [(entry['register'], entry['clear'], entry['set']) for entry in self.rmws] == expected_rmws, 'DMA-reset-disable-MMIO-sequence'
        assert names.count('mt76_npu_rro_close') == int(self.case.get('owned_rro', False))
        assert names.count('mt7996_rro_msdu_page_map_free') == int(self.case['dma'] and self.case.get('hwrro', False))
        assert names.count('skb_queue_purge_reason') == 1 + expected_mcu
        before = len(self.events)
        self.call()
        assert len(self.events) == before + 1 and self.events[-1] == dict(kind='native-entry', name='mt7996_cleanup_device'), 'second-cleanup-is-idempotent'
        return self.result()

    def result(self):
        return dict(case=self.case, instructions=self.instructions, native_entries=self.native_entries,
            events=self.events, firmware_error_logs=self.logs, modeled_MMIO_writes=self.writes,
            modeled_MMIO_rmws=self.rmws, physical_drain_proven=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--producer', type=Path, required=True)
    parser.add_argument('--expected-producer-sha256', default=PRODUCER_SHA)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert sha(args.producer) == args.expected_producer_sha256
    producer = json.loads(args.producer.read_bytes())
    assert producer['passed'] and producer['originals_unchanged']
    module_path = args.producer.parent / 'mt76/mt7996/mt7996e.ko'
    expected = producer['inner']['modules']['mt7996/mt7996e.ko']['sha256']
    context_path = args.producer.parent / 'context.json'
    context = json.loads(context_path.read_bytes())
    inputs = {str(path.resolve()):sha(path) for path in (args.producer, context_path, module_path,
        Path(__file__), Path(extraction.__file__))}
    for name in ('mt7996/init.c', 'mt7996/mcu.c', 'mt7996/dma.c', 'mt7996/mt7996.h', 'mt76.h'):
        path = args.source / name
        assert sha(path) == context['mt76_sources'][name]['sha256'], ('source-module-profile-mismatch', name)
        inputs[str(path.resolve())] = sha(path)
    module = Module(module_path, expected)
    cases = []
    for dma in (False, True):
        for hif2 in (False, True):
            cases.append(dict(mcu=False, dma=dma, hif2=hif2, send_error=0, poll=False))
            for error in (0, -5, -110):
                for poll in (False, True):
                    cases.append(dict(mcu=True, dma=dma, hif2=hif2, send_error=error, poll=poll))
    for owned in (False, True):
        cases.append(dict(mcu=True, dma=True, hif2=True, send_error=-5, poll=False,
            hwrro=True, owned_rro=owned))
    cases.append(dict(mcu=True, dma=True, hif2=True, send_error=-110, poll=False, already_started=True))
    assert len(cases) == 31
    results = [Replay(module, case).run() for case in cases]
    trace_groups = {}
    for row in results:
        case = row['case']
        if not case['mcu'] or case.get('hwrro') or case.get('already_started'):
            continue
        key = (case['dma'], case['hif2'], case['poll'])
        trace = dict(events=row['events'], instructions=row['instructions'],
            native_entries=row['native_entries'])
        if key in trace_groups:
            assert trace_groups[key] == trace, 'send-error-changes-observed-cleanup-trace'
        else:
            trace_groups[key] = trace
    assert len(trace_groups) == 8
    controls = []
    for mutation, expected_assertion in (
        ('invert-MCU-poll-branch', 'MCU-failure-log-contract'),
        ('omit-DMA-cleanup', 'DMA-cleanup-boundary'),
        ('omit-firmware-poll', 'firmware-state-poll-count')):
        case = dict(mcu=True, dma=True, hif2=True, send_error=0, poll=False)
        try:
            Replay(module, case, mutation).run()
        except AssertionError as error:
            assert str(error) == expected_assertion, (mutation, str(error))
            controls.append(dict(mutation=mutation, failed_assertion=str(error), compiled_bytes_changed_in_emulator_only=True))
        else:
            raise AssertionError(('mutation-survived', mutation))
    for name, expected in inputs.items():
        assert sha(Path(name)) == expected
    args.output.mkdir(exist_ok=False)
    result = dict(passed=True, cases=len(results), controls=controls, results=results,
        producer_receipt_sha256=sha(args.producer), module_sha256=sha(module_path),
        actual_functions=list(SELECTED), module_relocations=module.relocations, inputs=inputs,
        send_error_trace_groups=len(trace_groups),
        per_call_instruction_limit=1_000_000, per_call_timeout_us=5_000_000,
        firmware_MMIO_and_other_kernel_apis_modeled=True, actual_Linux_cleanup_executed=False,
        physical_retirement=False, no_compilation=True, module_loaded=False, hardware=False)
    with (args.output / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, cases=len(results), controls=len(controls),
        result_sha256=sha(args.output / 'result.json'))))


if __name__ == '__main__':
    main()
