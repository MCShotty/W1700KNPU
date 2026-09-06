#!/usr/bin/env python3
"""Bounded original-RV32 startup callbacks; no physical admission claim."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r
import unicorn

from test_boot_txbuf_extent import Boot, TX_SIZE
from test_firmware_mailbox_dispatch import Mailbox, MBOX, PAYLOAD, WIFI, ISR, DISPATCH
from test_firmware_stop_counterexample import ROOT, SRAM, END, CODE_SHA, DATA_SHA, INPUT

OUT = ROOT / 'research/checkpoints/2026-09-06-npu-startup/bootstrap-callbacks.json'
GHIDRA = ROOT / ('research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/'
                 'en7581_MT7996_npu_rv32.bin.txt')
PROVIDER = ROOT / ('.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/'
                   'linux-airoha_an7581/linux-6.18.44/drivers/net/ethernet/airoha/airoha_npu.c')
HEADER = PROVIDER.parents[4] / 'include/linux/soc/airoha/airoha_offload.h'
DELAY, PRINTF, HART = 0x8400420a, 0x840048f4, 0x84004212
# API: name, callback, implementation, destination, width, normal host value.
CONTRACTS = {
    32: ('TXcheck', 0x8400fb84, 0x8400e30e, SRAM + 0x469c, 4, 0x90c00000),
    8: ('pkt', 0x8400febe, 0x8400dbbe, SRAM + 0x396c, 4, 0x88000000),
    23: ('txpkt', 0x8400fb2e, 0x8400e2bc, SRAM + 0x2ab8, 4, 0x8a000000),
    7: ('BA', 0x8400feac, 0x8400dc0e, SRAM + 0x2ce4, 4, 0x90c0e000),
    18: ('band0CPU', 0x8400ff88, 0x8400dcc0, None, 1, 0),
    12: ('forceCPU', 0x8400ff0c, 0x8400dace, SRAM + 0x2a78, 1, 0),
}
WRITE_PC = {32: 0x8400e320, 8: 0x8400dbd2, 23: 0x8400e2d0,
            7: 0x8400dc22, 12: 0x8400dad4}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_value(api, value):
    if api == 32:
        return value & 0x3fffffff | 0x40000000
    return value & (0xff if api in (12, 18) else 0xffffffff)


class Evidence:
    """Observe only; inherited helper substitutions remain explicit below."""
    def __init__(self, harness, functions):
        self.h = harness
        self.functions = functions
        self.active = False
        self.calls, self.writes, self.prints = [], [], []
        harness.cpu.hook_add(UC_HOOK_CODE, self.code, begin=0x84000000, end=0x8401ffff)
        harness.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write)

    def code(self, cpu, pc, size, _data):
        if not self.active:
            return
        if pc in self.functions:
            self.calls.append(hex(pc))
        if pc == PRINTF:
            # The inherited printf hook may already have replaced a0 with zero.
            # Caller PCs, not text decoding after that stub, establish diagnostics.
            self.prints.append({'return_pc': hex(cpu.reg_read(r.UC_RISCV_REG_RA))})

    def write(self, cpu, access, address, size, value, _data):
        if not self.active:
            return
        if 0x84020000 <= address < 0x84022000:
            return
        self.writes.append({'pc': hex(cpu.reg_read(r.UC_RISCV_REG_PC)),
                            'address': hex(address), 'size': size, 'value': value})

    def message(self, words, **kwargs):
        self.calls, self.writes, self.prints = [], [], []
        self.active = True
        reply = self.h.message(words, **kwargs)
        self.active = False
        return dict(reply, calls=self.calls.copy(), writes=self.writes.copy(),
                    printf_calls=self.prints.copy())


def callback_case(functions, name, api, value, *, index=0, length=None,
                  missing=False, wait=True, prefix=0x10):
    h = Mailbox()
    e = Evidence(h, functions)
    _, callback, implementation, destination, width, _ = CONTRACTS[api]
    assert h.get32(SRAM + 0x178 + api * 4) == callback
    before = bytes(h.cpu.mem_read(SRAM, 0x8000))
    words = [prefix | index, api] if missing else [prefix | index, api, value, 0xdeadbeef]
    reply = e.message(words, length=length, wait=wait, halt=None if wait else 0x84003c28)
    actual = 0 if missing else value
    assert reply['flags'] == (7 if wait else 6), name
    assert reply['words'] == words, name
    route = [hex(x) for x in (DISPATCH, HART, ISR, HART, WIFI, callback)]
    assert reply['calls'][:6] == route, (name, reply['calls'])
    assert hex(implementation) in reply['calls'], name
    allowed = {DISPATCH, ISR, HART, WIFI, callback, implementation, PRINTF}
    if not wait:
        allowed.add(0x84003c28)
    assert all(int(pc, 16) in allowed for pc in reply['calls']), (name, reply['calls'])
    state = [w for w in reply['writes'] if SRAM <= int(w['address'], 16) < SRAM + 0x8000]
    after = bytearray(before)
    if destination is None:
        assert state == [], (name, state)
    else:
        pc = 0x8400e304 if api == 23 and actual >= 0xc0000000 else WRITE_PC[api]
        assert state == [{'pc': hex(pc), 'address': hex(destination), 'size': width,
                          'value': expected_value(api, actual)}], (name, state)
        offset = destination - SRAM
        after[offset:offset + width] = expected_value(api, actual).to_bytes(width, 'little')
    assert bytes(h.cpu.mem_read(SRAM, 0x8000)) == bytes(after), name
    mmio = [w for w in reply['writes'] if w not in state]
    assert [(int(w['address'], 16), w['value']) for w in mmio] == (
        [(MBOX, 1), (MBOX + 0x3c, 7), (0x0c200004, 9)] if wait else
        [(MBOX, 1), (MBOX + 0x3c, 6)]), (name, mmio)
    reads = [v for v in reply['events'] if v['kind'] == 'payload-read']
    assert {'kind': 'payload-read', 'offset': 8, 'size': width} in reads, (name, reads)
    assert all(v['offset'] < 12 for v in reads), (name, reads)
    count = {32: 2, 8: 1, 23: 0, 7: 1, 18: 1, 12: 1}[api]
    count += 2 if api in (7, 8, 23) and actual >= 0xc0000000 else 0
    count += 1 if api == 12 and actual & 0xff > 1 else 0
    assert len(reply['printf_calls']) == count, (name, reply['printf_calls'])
    flags = next(i for i, ev in enumerate(reply['events']) if ev['kind'] == 'mailbox-flags-write')
    assert (flags == len(reply['events']) - 1) if wait else flags == 0
    return {'name': name, 'api': api, 'index': index, 'word0': hex(prefix | index),
            'input': None if missing else hex(value), 'advertised_length': length,
            'readable_payload_bytes': 256, 'wait': wait, 'flags': reply['flags'],
            'calls': reply['calls'], 'state_writes': state, 'mmio_writes': mmio,
            'payload_reads': reads, 'printf_call_count': count}


def resume_delay(h, context, halt=END):
    h.cpu.context_restore(context)
    pc = h.cpu.reg_read(r.UC_RISCV_REG_RA)
    h.waiting = False
    h.cpu.emu_start(pc, END, count=2000000, timeout=3000000)
    assert h.cpu.reg_read(r.UC_RISCV_REG_PC) == halt, hex(h.cpu.reg_read(r.UC_RISCV_REG_PC))


def boot_case(api, value):
    base = expected_value(32, value) if api == 32 else 0x50c00000
    h = Boot(base, TX_SIZE)
    clear_pcs = set()

    def clear_write(cpu, access, address, size, written, data):
        clear_pcs.add(hex(cpu.reg_read(r.UC_RISCV_REG_PC)))

    h.cpu.hook_add(UC_HOOK_MEM_WRITE, clear_write, begin=base, end=base + TX_SIZE - 1)
    h.initialize()
    context = h.cpu.context_save()
    reply = h.message([0x10, api, value])
    assert reply['flags'] == 7 and h.clear_writes == 0
    resume_delay(h, context, END if api == 32 else DELAY)
    if api == 32:
        assert h.clear_writes == 0x7000 and h.outside == 0
        assert h.first == base and h.last == base + TX_SIZE
        assert bytes(h.cpu.mem_read(base, TX_SIZE)) == bytes(TX_SIZE)
        assert bytes(h.cpu.mem_read(base + TX_SIZE, 32)) == b'\xa5' * 32
        assert clear_pcs == {'0x84004f1e'}
    else:
        assert h.waiting and h.clear_writes == 0 and h.get32(SRAM + 0x469c) == 0
    return {'name': f'boot_wait_api{api}_{value:08x}', 'api': api, 'input': hex(value),
            'callback_done_before_clear': True, 'resume_pc': hex(h.cpu.reg_read(r.UC_RISCV_REG_PC)),
            'cleared_bytes': h.clear_writes * 2, 'clear_base': hex(base),
            'clear_pcs': sorted(clear_pcs),
            'scope': 'Original allocator and TX-check initializer, not complete reset/main.'}


def txpkt_wait_case(entry, direction, value):
    h = Boot(0x90c00000, TX_SIZE)
    h.initialize()
    h.put32(SRAM + 0x2ab8, 0)
    h.cpu.mem_map(0x1fb54000, 0x1000)
    post_wait = 0x8400a058 if entry == 0x84009fc8 else 0x8400a61c
    reached = []
    mmio = []

    def boundary(cpu, pc, size, data):
        reached.append(hex(pc))
        cpu.emu_stop()

    def writes(cpu, access, address, size, written, data):
        mmio.append({'pc': hex(cpu.reg_read(r.UC_RISCV_REG_PC)), 'address': hex(address),
                     'size': size, 'value': written})

    h.cpu.hook_add(UC_HOOK_CODE, boundary, begin=post_wait, end=post_wait)
    h.cpu.hook_add(UC_HOOK_MEM_WRITE, writes, begin=0x1fb50000, end=0x1fb54fff)
    h.cpu.reg_write(r.UC_RISCV_REG_SP, 0x84021e00)
    h.cpu.reg_write(r.UC_RISCV_REG_RA, END)
    h.cpu.reg_write(r.UC_RISCV_REG_A0, direction)
    h.waiting = False
    h.cpu.emu_start(entry, END, count=2000000, timeout=3000000)
    assert h.waiting and h.cpu.reg_read(r.UC_RISCV_REG_PC) == DELAY and not reached
    if entry == 0x84009fc8:
        assert [w['address'] for w in mmio] == [hex(x) for x in
                (0x1fb54710, 0x1fb50900, 0x1fb50904, 0x1fb50910, 0x1fb50914)]
    else:
        assert not mmio
    context = h.cpu.context_save()
    assert h.message([0x10, 23, value])['flags'] == 7
    resume_delay(h, context, post_wait if value else DELAY)
    assert bool(reached) == bool(value)
    return {'name': f'txpkt_wait_{entry:x}_{direction}_{value:08x}', 'api': 23,
            'consumer_entry': hex(entry), 'direction': direction, 'input': hex(value),
            'wait_pc': hex(DELAY), 'post_wait_boundary': hex(post_wait),
            'advanced': bool(reached), 'pre_wait_mmio_writes': mmio,
            'scope': 'Original entry through zero wait and post-wait branch. Stops before descriptor construction; MMIO is RAM, no DMA execution.'}


def provider_sequence(functions):
    h = Boot(0x90c00000, TX_SIZE)
    h.initialize()
    context = h.cpu.context_save()
    e = Evidence(h, functions)
    replies = []
    for index, api, value in ((1, 18, 0), (0, 32, 0x90c00000), (0, 8, 0x88000000),
                              (0, 23, 0x8a000000), (0, 7, 0x90c0e000), (0, 12, 0)):
        reply = e.message([0x10 | index, api, value])
        assert reply['flags'] == 7
        replies.append({'api': api, 'ifindex': index, 'value': hex(value),
                        'calls': reply['calls'], 'writes': reply['writes']})
        if api == 32:
            assert h.get32(SRAM + 0x396c) == 0 and h.get32(SRAM + 0x2ab8) == 0
            assert h.get32(SRAM + 0x2ce4) == 0
            resume_delay(h, context)
            assert h.clear_writes * 2 == TX_SIZE
    return {'name': 'provider_order_core0_runs_after_api32_before_remaining_addresses',
            'sequence': replies, 'cleared_before_pkt_txpkt_ba': True,
            'scope': 'Serialized native callbacks and saved boot initializer; host order read from current source, provider C is not executed here.'}


def force_route_case(functions, value):
    h = Mailbox()
    e = Evidence(h, functions)
    assert e.message([0x10, 8, 0x88000000])['flags'] == 7
    assert e.message([0x10, 12, value])['flags'] == 7
    target = 0x8400ac30 if value & 0xff else 0x840091b4
    reached = []

    def boundary(cpu, pc, size, data):
        reached.append({'pc': hex(pc), 'arguments': [cpu.reg_read(getattr(r, 'UC_RISCV_REG_A' + str(i)))
                                                    for i in range(6)]})
        cpu.emu_stop()

    h.cpu.hook_add(UC_HOOK_CODE, boundary, begin=0x840091b4, end=0x840091b4)
    h.cpu.reg_write(r.UC_RISCV_REG_A3, 0)
    h.invoke(0x8400aedc, (7, 64, 0), halt=target)
    if target == 0x8400ac30:
        # The inherited enqueue hook stops execution before later hooks run.
        reached.append({'pc': hex(target), 'arguments': h.enqueue})
    assert len(reached) == 1 and reached[0]['pc'] == hex(target)
    args = reached[0]['arguments']
    if value & 0xff:
        assert args == [7, 64, 0, 0, 0, 2]
    else:
        assert args[:3] == [7, 62, 0x48007082], args
    return {'name': f'force_cpu_route_{value:08x}', 'api': 12, 'input': hex(value),
            'consumer_entry': '0x8400aedc', 'boundary': reached[0],
            'scope': 'Original routing branch after API8/API12. Stops at enqueue/PPE helper entry; neither helper executes.'}


def dispatch_controls(functions):
    results = []
    for prefix, api, expected_flags in ((0x10, 34, 3), (0x10, 0xffffffff, 3),
                                        (0x20, 32, 3), (0, 32, 7)):
        h = Mailbox()
        e = Evidence(h, functions)
        before = bytes(h.cpu.mem_read(SRAM, 0x8000))
        reply = e.message([prefix, api, 0x90c00000])
        assert reply['flags'] == expected_flags
        assert bytes(h.cpu.mem_read(SRAM, 0x8000)) == before
        assert not any(hex(spec[1]) in reply['calls'] for spec in CONTRACTS.values())
        results.append({'name': f'noncallback_dispatch_{prefix:x}_{api:x}',
                        'word0': prefix, 'api': api, 'flags': reply['flags'],
                        'calls': reply['calls'], 'unchanged_sram': True})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    assert CODE_SHA == 'e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643'
    assert DATA_SHA == '61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1'
    allowed = ROOT / '.local/npu-startup/callbacks'
    target = args.output.resolve()
    assert target == OUT.resolve() or target.is_relative_to(allowed.resolve()), target
    text = GHIDRA.read_text()
    functions = {int(match[1], 16): match[0] for match in
                 re.findall(r'^FUNCTION ([^\n]+) @ ram:([0-9a-f]+)', text, re.M)}
    for spec in CONTRACTS.values():
        assert spec[1] in functions and spec[2] in functions
    selected = {WIFI, ISR, DISPATCH, 0x84004e76, 0x84009fc8, 0x8400a5fa,
                0x8400aedc, 0x8400bc02, 0x8400b432, 0x8400b6ba, 0x8400b7e8}
    selected.update(pc for spec in CONTRACTS.values() for pc in spec[1:3])
    sections = {}
    for match in re.finditer(r'^FUNCTION [^\n]+ @ ram:([0-9a-f]+).*?(?=^FUNCTION |\Z)', text, re.M | re.S):
        pc = int(match[1], 16)
        if pc in selected:
            assert 'decompiled=true' in match[0] and 'ASSEMBLY' in match[0]
            sections[hex(pc)] = {'name': functions[pc], 'start_line': text.count('\n', 0, match.start()) + 1,
                                 'end_line': text.count('\n', 0, match.end()),
                                 'normalized_text_sha256': hashlib.sha256(match[0].encode()).hexdigest()}
    assert len(sections) == len(selected)
    provider = PROVIDER.read_text()
    init = provider.split('static int airoha_npu_wlan_init_memory(', 1)[1].split('\nstatic ', 1)[0]
    commands = re.findall(r'\.cmd = (WLAN_FUNC_\w+)', init)
    assert commands == ['WLAN_FUNC_SET_WAIT_TX_BUF_CHECK_ADDR', 'WLAN_FUNC_SET_WAIT_PKT_BUF_ADDR',
                        'WLAN_FUNC_SET_WAIT_TX_PKT_BUF_ADDR', 'WLAN_FUNC_SET_WAIT_DRAM_BA_NODE_ADDR']
    assert init.index('npu, 1, WLAN_FUNC_SET_WAIT_NPU_BAND0_ONCPU') < init.index('val = memory[i].res.start')
    assert init.index('WLAN_FUNC_SET_WAIT_IS_FORCE_TO_CPU') > init.index('val = memory[i].res.start')
    enum = HEADER.read_text().split('enum airoha_npu_wlan_set_cmd {', 1)[1].split('};', 1)[0]
    names = [item.strip() for item in enum.split(',') if item.strip()]
    assert all(re.fullmatch(r'WLAN_FUNC_\w+', name) for name in names), 'enum needs reinspection'
    assert [names.index(name) for name in commands] == [32, 8, 23, 7]
    assert names.index('WLAN_FUNC_SET_WAIT_NPU_BAND0_ONCPU') == 18
    assert names.index('WLAN_FUNC_SET_WAIT_IS_FORCE_TO_CPU') == 12
    cases = []
    for api, spec in CONTRACTS.items():
        values = ((0, 1, 0x90c00000, 0x50c00000, 0xbfffffff, 0xc0000000, 0xffffffff)
                  if api not in (12, 18) else (0, 1, 2, 255, 256, 257, 0xffffffff))
        for value in values:
            cases.append(callback_case(functions, f'api{api}_value_{value:08x}', api, value))
        for index in range(16):
            cases.append(callback_case(functions, f'api{api}_index{index}', api, spec[5], index=index))
        for length in (0, 8, 9, 11, 12, 65536):
            cases.append(callback_case(functions, f'api{api}_length{length}', api, spec[5], length=length))
        cases.append(callback_case(functions, f'api{api}_missing_readable_zero_tail', api, 0, missing=True))
        cases.append(callback_case(functions, f'api{api}_nowait_early_done', api, spec[5], wait=False))
        cases.append(callback_case(functions, f'api{api}_ignored_high_header', api, spec[5], prefix=0xffffff10))
    controls = dispatch_controls(functions)
    boots = [boot_case(32, value) for value in (0x90c00000, 0x50c00000, 0)]
    boots += [boot_case(api, spec[5]) for api, spec in CONTRACTS.items() if api != 32]
    txpkt = [txpkt_wait_case(entry, direction, value)
             for entry, direction in ((0x84009fc8, 0), (0x8400a5fa, 0), (0x8400a5fa, 1))
             for value in (0, 0x8a000000, 0xc0000000)]
    sequence = provider_sequence(functions)
    routes = [force_route_case(functions, value) for value in (0, 1, 2, 256)]
    inputs = [INPUT / 'en7581_MT7996_npu_rv32.bin', INPUT / 'en7581_MT7996_npu_data.bin',
              GHIDRA, PROVIDER, HEADER, Path(__file__).resolve()]
    inputs += [ROOT / 'tests/npu' / name for name in
               ('test_firmware_mailbox_dispatch.py', 'test_boot_txbuf_extent.py',
                'test_firmware_stop_irqs.py', 'test_firmware_stop_counterexample.py', 'emulation_layout.py')]
    counts = {'callback_cases': len(cases), 'dispatch_controls': len(controls),
              'boot_wait_cases': len(boots), 'txpkt_consumer_wait_cases': len(txpkt),
              'force_routing_cases': len(routes),
              'provider_sequence_cases': 1}
    counts['total'] = sum(counts.values())
    report = {'passed': True, 'counts': counts, 'unicorn': unicorn.__version__,
              'firmware_sha256': CODE_SHA, 'data_sha256': DATA_SHA,
              'inputs_sha256': {str(path.relative_to(ROOT)): sha(path) for path in inputs},
              'complete_ghidra_functions': sections,
              'contracts': {str(api): dict(zip(('name', 'callback', 'implementation', 'destination',
                                               'load_bytes', 'normal_host_value'), spec))
                            for api, spec in CONTRACTS.items()},
              'callback_cases': cases, 'dispatch_controls': controls,
              'boot_wait_cases': boots, 'txpkt_consumer_wait_cases': txpkt,
              'provider_sequence': sequence,
              'force_routing_cases': routes,
              'limits': ['Original instructions and original callback table; helper fixtures are not complete reset state.',
                         'Hart ID and printf are stubbed; PLIC and mailbox W1C are modeled.',
                         'Boot helper seeds mutex owner at 0x1ec03048; IRQ invocation and delay completion are modeled.',
                         'Mailbox helper supplies 256 readable coherent bytes even for truncated messages; no inaccessible-buffer or physical coherency claim.',
                         'No-wait stops at host-notifier entry; host notification, its mutex and timeout are not executed.',
                         'MMIO is ordinary emulator RAM. No concurrent harts, interrupts, cache, bus, DMA, containment or physical wake proof.',
                         'API23 consumer probes stop immediately after their wait; downstream descriptor/DMA effects remain source evidence.',
                         'No new boot protocol, reset implementation, production admission classification, router, build or configuration change.']}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'counts': counts, 'output_sha256': sha(target)}))


if __name__ == '__main__':
    main()
