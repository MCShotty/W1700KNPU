#!/usr/bin/env python3
"""Native bridge postgate regression with explicit synthetic drain callbacks."""
import argparse
from collections import Counter, deque
from copy import deepcopy
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from unicorn import riscv_const as r

import test_bootstrap_v2_composition as composition
import test_host_queue_publication as extract
import test_mt7996_bootstrap_sequence as host_sequence
from test_attach_tx_callbacks import REGS, TARGETS
from test_firmware_memory_layout import STACK_TOPS
from test_firmware_mailbox_dispatch import PAYLOAD
from test_firmware_stop_counterexample import END
from test_barrier_workers import OUTER, STARTUP_FLAGS
from test_barrier_protocol import Rv32
from test_multihart_cold_boot import STARTUPS
from test_bridge_startup import BRIDGE, CHANNELS
from emulation_layout import STATE, SRAM, HEAP, HEAP_BYTES

ROOT = Path(__file__).resolve().parents[2]


def host_tx_calls(dest):
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    linux = ROOT / lock['build_directory'] / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581'
    trees = [p for p in linux.glob('mt76-*') if (p / 'mt7996/npu.c').is_file()]
    assert len(trees) == 1
    tree = trees[0]
    kernel = linux / ('linux-' + lock['kernel'])
    header = (kernel / 'include/linux/soc/airoha/airoha_offload.h').read_text()
    common = (tree / 'mt76.h').read_text()
    regs = (tree / 'mt7996/regs.h').read_text()
    driver = (tree / 'mt7996/npu.c').read_text()
    constants = (tree / 'mt7996/mt7996.h').read_text()
    parts = [host_sequence.C_MODEL, extract.declaration(header, 'enum', 'airoha_npu_wlan_set_cmd')]
    parts += [extract.declaration(common, 'enum', name) for name in ('mt76_mcuq_id', 'mt76_rxq_id', 'mt76_band_id')]
    parts += [regs, extract.macro(constants, 'MT7996_RX_RING_SIZE'),
              extract.macro(constants, 'MT7996_NPU_RX_RING_SIZE'), r'''
struct airoha_npu { int unused; };
struct mt7996_dev {
    struct { struct { phys_addr_t phy_addr; } mmio; void *dev; } mt76;
    void *hif2;
    u32 q_wfdma_mask;
};
static int mt76_npu_send_msg(struct airoha_npu *npu, int selector,
                            enum airoha_npu_wlan_set_cmd command, u32 value, int flags) {
    (void)npu; (void)flags;
    printf("{\"selector\":%d,\"api\":%d,\"value\":%u}\n", selector, command, value);
    return 0;
}
''', extract.function(driver, 'mt7996_npu_txrx_offload_init'), r'''
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    struct airoha_npu npu = {0};
    struct mt7996_dev dev = {0};
    dev.mt76.mmio.phy_addr = 0x20000000;
    dev.hif2 = atoi(argv[1]) ? &npu : NULL;
    return mt7996_npu_txrx_offload_init(&dev, &npu);
}
''']
    source, binary = dest / 'host.c', dest / 'host'
    source.write_text('\n\n'.join(parts))
    subprocess.run(['gcc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-fno-pie', '-no-pie', source, '-o', binary], check=True)
    rows = [[json.loads(line) for line in subprocess.check_output([binary, str(hif)], text=True).splitlines()]
            for hif in (0, 1)]
    selected = [[row for row in trace if row['api'] == 19 and row['selector'] in (0, 2)] for trace in rows]
    assert selected == [[dict(selector=0, api=19, value=0x200d4420),
                         dict(selector=2, api=19, value=0x200d4450 + hif * 0x4000)] for hif in (0, 1)]
    return selected, dict(trace=rows, source=composition.sha(source),
                         inputs={str(p.relative_to(ROOT)): composition.sha(p) for p in (
                             tree / 'mt7996/npu.c', tree / 'mt76.h', tree / 'mt7996/regs.h',
                             tree / 'mt7996/mt7996.h', kernel / 'include/linux/soc/airoha/airoha_offload.h')})


class Postgate(composition.Composed):
    def __init__(self, paths, parts):
        self.trace = deque(maxlen=32)
        self.instruction_counts = Counter()
        self.trace_enabled = False
        self.tx_registers = set()
        self.bridge_active = False
        self.timer_value = 0xfffffff0
        self.interrupt_release = False
        self.interrupted = False
        super().__init__(paths, parts)
        for base in sorted({address & ~0xfff for address in REGS}):
            self.cpu.mem_map(base, 0x1000)
        self.cpu.mem_map(BRIDGE, 0x1000)
        for address in CHANNELS:
            self.put32(address, 1)
        self.put32(0x1ec10100, 1)

    def register_model(self, address, write):
        if address in CHANNELS or address in (BRIDGE + 8, BRIDGE + 0x10, BRIDGE + 0x18):
            return 'bridge status/configuration storage; no physical completion or DMA effect'
        if address == 0x1ec10108:
            return 'synthetic decreasing timer; no hardware time/frequency evidence'
        if address in (0x1ec03c48, 0x1ec03e48):
            return 'hart7 allocator mutex with synthetic owner; no arbitration proof'
        if write and address in REGS:
            return 'native TX setup writes; register storage only, no hardware effect'
        if not write and address in self.tx_registers:
            return 'synthetic PCIe TX DMA index; no device ownership or completion proof'
        return super().register_model(address, write)

    def read_hook(self, cpu, access, address, size, value, data):
        if self.bridge_active and address == 0x1ec10108:
            self.timer_value = (self.timer_value - 65536) & 0xffffffff
            self.put32(address, self.timer_value)
        if self.bridge_active and address == 0x1ec03c48:
            self.put32(address, 0x10700)
        super().read_hook(cpu, access, address, size, value, data)

    def code_hook(self, cpu, pc, size, data):
        if self.interrupt_release and self.hart == 7 and pc == 0x8400651c:
            self.put32(STATE, 2)
            self.interrupted = True
            self.interrupt_release = False
        if self.trace_enabled:
            self.trace.append(hex(pc))
            self.instruction_counts[pc] += 1
        super().code_hook(cpu, pc, size, data)

    def barrier(self, name, *args):
        context, hart = self.cpu.context_save(), self.hart
        self.hart = 0
        self.stops, self.skip_once = set(), None
        try:
            return self.rv.call(name, *args)
        finally:
            self.cpu.context_restore(context)
            self.hart = hart

    def snapshot(self):
        return dict(memory=[(lo, bytes(self.cpu.mem_read(lo, hi - lo + 1)))
                            for lo, hi, _ in self.cpu.mem_regions()],
                    contexts=dict(self.contexts), banks=deepcopy(self.plic_banks),
                    patches=deepcopy(self.patches))

    def restore(self, saved):
        for address, data in saved['memory']:
            self.cpu.mem_write(address, data)
        self.cpu.ctl_remove_cache(0x84000000, 0x84201000)
        self.contexts = dict(saved['contexts'])
        self.plic_banks = deepcopy(saved['banks'])
        self.patches = deepcopy(saved['patches'])
        self.events, self.mmio, self.allocations = [], [], []
        self.executions = Counter()
        self.pending_call = None
        self.unmodeled = None
        self.interrupted = self.interrupt_release = False
        self.trace_enabled = False
        self.timer_value = 0xfffffff0
        self.hart = 7
        self.cpu.context_restore(self.contexts[7])

    def cold(self):
        self.hart = 0
        self.cpu.context_restore(self.fresh)
        assert self.reset() == 0x8400420a
        host = composition.control.Host(self.paths)
        assert composition.control.exchange(host, self)[0] == composition.control.ACCEPTED
        composition.boot.setup(self, run_clear=True)
        composition.control.advance(host, self)
        self.finish_coordinator()
        for hart in range(1, 8):
            self.worker(hart)
        assert self.barrier('workers_parked', 1) == 1

    def publish_tx(self, calls):
        rows = []
        for call in calls:
            words = [0x10 | call['selector'], call['api'], call['value']]
            self.on_core0()
            denied = composition.boot.Bootstrap.message(self, words)
            assert denied['flags'] == 3 and not denied['callbacks']
            # Direct callback analysis does not open the strict mailbox gate.
            saved = self.cpu.context_save()
            self.cpu.mem_write(PAYLOAD, struct.pack('<3I', *words))
            self.cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[0] - 0x1000)
            self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
            self.cpu.reg_write(r.UC_RISCV_REG_A0, PAYLOAD)
            self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
            before = dict(self.executions)
            assert self.run(TARGETS[0], []) == END
            assert self.cpu.reg_read(r.UC_RISCV_REG_A0) == 1
            offset = 0x4700 if call['selector'] == 0 else 0x46fc
            assert self.get32(SRAM + offset) == call['value']
            self.cpu.context_restore(saved)
            page = call['value'] & ~0xfff
            if not any(lo <= page <= hi for lo, hi, _ in self.cpu.mem_regions()):
                self.cpu.mem_map(page, 0x1000)
            self.tx_registers.add(call['value'] + 12)
            self.put32(call['value'] + 12, 0)
            rows.append(dict(**call, strict_denied=True, direct_native_return=1,
                             entries=[hex(pc) for pc in TARGETS if self.executions[pc] > before.get(pc, 0)]))
        return rows

    def modeled_release(self):
        # These are injected platform completions, never hardware witnesses.
        for domain in range(5):
            assert self.barrier('record_drain', domain, 1) == 1
        assert self.barrier('prepare', 1) == 1
        assert self.barrier('release', 1) == 1
        for hart in range(8):
            self.repoll(hart)
            assert self.get32(STATE + 52 + 4 * hart) == 1, ('refresh', hart)
        assert self.barrier('arm', 1) == 1

    def advance(self, hart):
        self.hart = hart
        self.bridge_active = hart == 7
        self.cpu.context_restore(self.contexts[hart])
        self.trace.clear()
        self.instruction_counts.clear()
        self.trace_enabled = True
        start = self.cpu.reg_read(r.UC_RISCV_REG_PC)
        target = OUTER[hart] if hart != 5 else 0x8400cbbe
        faults = [self.allocator_rv.symbols['npu_emulation_allocator_startup_hold'],
                  self.guard_rv.symbols['npu_emulation_bridge_base_fault_park'],
                  self.guard_rv.symbols['npu_emulation_bridge_channel_fault_park']]
        row = dict(hart=hart, start=hex(start), target=hex(target))
        try:
            wait = STARTUPS[hart][0]
            stop = self.run(start, [target, wait, *faults])
            outcome = ('outer-boundary' if stop == target else
                       'fault-hold' if stop in faults else 'native-startup-wait')
            row.update(outcome=outcome, stopped=hex(stop))
        except (AssertionError, TimeoutError) as error:
            row.update(outcome=type(error).__name__, error=str(error),
                       stopped=hex(self.cpu.reg_read(r.UC_RISCV_REG_PC)))
        finally:
            self.trace_enabled = False
        row.update(trace=list(self.trace),
                   startup_flags={hex(SRAM + offset): self.get32(SRAM + offset)
                                  for offset in STARTUP_FLAGS.get(hart, ()) if offset % 4 == 0},
                   fault=self.get32(STATE + 16),
                   hot=[dict(pc=hex(pc), instructions=count)
                        for pc, count in self.instruction_counts.most_common(12)])
        self.contexts[hart] = self.cpu.context_save()
        return row


ADM, BOOT = composition.native.ADM, composition.native.BOOT
GUARDS = {
    'epoch-zero': [(STATE, 0)], 'later-epoch': [(STATE, 2)],
    'barrier-fault': [(STATE + 16, 1)],
    'not-prepared': [(STATE + 12, 0)], 'not-released': [(STATE + 4, 0)],
    'not-armed': [(STATE + 8, 0)], 'not-parked': [(STATE + 20 + 28, 0)],
    'not-refreshed': [(STATE + 52 + 28, 0)],
    'open-admission': [(ADM, 0)], 'active-callback': [(ADM + 4, 1)],
    'admission-fault': [(ADM + 8, 1)], 'bad-bootstrap': [(BOOT, 0)],
    'bootstrap-failed': [(BOOT + 4, 1)], 'bootstrap-inflight': [(BOOT + 12, 1)],
    'incomplete-bootstrap': [(BOOT + 8, 5)],
    'missing-retained-regions': [(BOOT + 16, 0)],
    'wrong-type': [], 'wrong-caller': [], 'late-stop': [],
}


def guard_case(h, saved, name):
    h.restore(saved)
    h.bridge_active = True
    for address, value in GUARDS[name]:
        h.put32(address, value)
    before = composition.allocator.state(h)
    heap = bytes(h.cpu.mem_read(HEAP, HEAP_BYTES))
    bridge = bytes(h.cpu.mem_read(BRIDGE, 0x1000))
    base = h.get32(SRAM + 0x184c)
    h.interrupt_release = name == 'late-stop'
    h.cpu.reg_write(r.UC_RISCV_REG_A0, 0x80 if name == 'wrong-type' else 0x81)
    h.cpu.reg_write(r.UC_RISCV_REG_A1, 0x8400148c if name == 'wrong-caller' else 0x8400148a)
    h.cpu.reg_write(r.UC_RISCV_REG_RA, END)
    h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
    entry = h.allocator_rv.symbols['npu_emulation_startup_allocate']
    hold = h.allocator_rv.symbols['npu_emulation_allocator_startup_hold']
    assert h.run(entry, [hold]) == hold, 'postgate-context-not-held'
    after = composition.allocator.state(h)
    if name == 'late-stop':
        assert h.interrupted and h.get32(STATE) == 2
        assert struct.unpack_from('<I', after, 8)[0] == struct.unpack_from('<I', before, 8)[0] + 1
        assert struct.unpack_from('<I', after, 20)[0] > struct.unpack_from('<I', before, 20)[0]
    else:
        assert after == before, 'denied-context-allocated'
    assert bytes(h.cpu.mem_read(HEAP, HEAP_BYTES)) == heap
    assert bytes(h.cpu.mem_read(BRIDGE, 0x1000)) == bridge
    assert h.get32(SRAM + 0x184c) == base and h.get32(STATE + 16) == 1
    return dict(case=name, held=True, metadata_changed=after != before,
                committed_allocation_retained=name == 'late-stop',
                bridge_unpublished=True)


def mutations(h, saved, dest, parts, command):
    source = composition.allocator.SOURCE.read_text()
    variants = {
        'not-prepared': source.replace('load(&BARRIER->prepared) == 1 &&', ''),
        'not-released': source.replace('load(&BARRIER->released) == 1 &&', ''),
        'not-armed': source.replace('load(&BARRIER->armed) == 1 &&', ''),
        'not-parked': source.replace('load(&BARRIER->parked[7]) == 1 &&', ''),
        'not-refreshed': source.replace('load(&BARRIER->ready[7]) == 1 &&', ''),
        'incomplete-bootstrap': source.replace('BOOTSTRAP->step == NPU_BOOTSTRAP_STEPS &&', ''),
        'missing-retained-regions': source.replace('BOOTSTRAP->retained_mask == 0x1e &&', ''),
        'later-epoch': source.replace('load(&BARRIER->request) != 1', '0').replace(
            'load(&BARRIER->request) == 1', '1'),
        'late-stop': source.replace('result.status != NPU_ALLOCATOR_OK || !startup_lifetime(hart)',
                                    'result.status != NPU_ALLOCATOR_OK'),
    }
    results = []
    for name, text in variants.items():
        assert text != source
        candidate = dest / ('mutant-' + name + '.c')
        candidate.write_text(text)
        binary = candidate.with_suffix('.elf')
        args = [str(candidate) if x == str(composition.allocator.SOURCE) else x for x in command]
        args[args.index('-o') + 1] = str(binary)
        composition.execute(args)
        composition.check_imports(binary, parts['base'])
        # Keep the same cold prefix; only the selected allocator component differs.
        h.restore(saved)
        h.allocator_rv = Rv32(binary, h.cpu)
        modified = h.snapshot()
        try:
            guard_case(h, modified, name)
        except AssertionError as error:
            assert str(error) in ('postgate-context-not-held', 'denied-context-allocated'), str(error)
            results.append(dict(name=name, detected=str(error), sha256=composition.sha(binary)))
        else:
            raise AssertionError('surviving-postgate-mutant:' + name)
    h.restore(saved)
    h.allocator_rv = Rv32(parts['allocator'], h.cpu)
    return results


def baseline(h, saved, dest, parts, command):
    source = dest / 'baseline-allocator.c'
    source.write_bytes(subprocess.check_output([
        'git', '-C', ROOT, 'show', 'eb31bae:tests/npu/allocator-startup-emulation.c']))
    binary = source.with_suffix('.elf')
    args = [str(source) if x == str(composition.allocator.SOURCE) else x for x in command]
    args[args.index('-o') + 1] = str(binary)
    composition.execute(args)
    composition.check_imports(binary, parts['base'])
    h.restore(saved)
    getter = composition.allocator.GETTER
    h.cpu.mem_write(getter, h.code[getter - 0x84000000:getter - 0x84000000 + 4])
    h.allocator_rv, patch = composition.allocator.install(h, binary)
    h.patches = [patch if int(row['site'], 16) == getter else row for row in h.patches]
    before = composition.allocator.state(h)
    row = h.advance(7)
    assert row['outcome'] == 'fault-hold' and row['fault'] == 1
    assert composition.allocator.state(h) == before and h.get32(SRAM + 0x184c) == 0
    assert not any(BRIDGE <= int(event['address'], 16) < BRIDGE + 0x1000 for event in h.mmio)
    row.update(source_sha256=composition.sha(source), elf_sha256=composition.sha(binary),
               allocation_unchanged=True, bridge_unpublished=True)
    h.restore(saved)
    h.allocator_rv = Rv32(parts['allocator'], h.cpu)
    return row


def bindings():
    paths = [Path(__file__), composition.CODE_INPUT,
             composition.ROOT / '.local/npu-quiescence/firmware/en7581_MT7996_npu_data.bin',
             composition.native.DTB, composition.bridge.GHIDRA, ROOT / 'firmware/source-lock.json']
    paths += list((ROOT / 'firmware/npu').glob('*.[ch]'))
    paths += list((ROOT / 'tests/npu').glob('*emulation.*'))
    paths += [Path(m.__file__) for m in tuple(sys.modules.values()) if getattr(m, '__file__', None)
              and Path(m.__file__).resolve().parent == ROOT / 'tests/npu']
    return {str(p.relative_to(ROOT)): composition.sha(p) for p in sorted(set(paths))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-postgate' / args.name
    assert not dest.exists(), 'Choose a fresh result name'
    dest.mkdir(parents=True)
    before = bindings()
    composition.BUILD = dest / 'build'
    paths, parts = composition.build()
    layout = composition.memory_layout(parts)
    allocator_command = next(cmd for cmd in composition.COMMANDS
                             if str(composition.allocator.SOURCE) in cmd)
    calls, host = host_tx_calls(dest)
    h = Postgate(paths, parts)
    h.paths = paths
    h.cold()
    published = h.publish_tx(calls[0])
    h.modeled_release()
    saved = h.snapshot()
    original = baseline(h, saved, dest, parts, allocator_command)
    checks = [guard_case(h, saved, name) for name in GUARDS]
    killed = mutations(h, saved, dest, parts, allocator_command)
    h.restore(saved)
    prior_metadata = composition.allocator.state(h)
    rows = []
    for hart in (7, 3, 1, 2, 4, 5, 6):
        rows.append(h.advance(hart))
        print(json.dumps({key: rows[-1][key] for key in ('hart', 'outcome', 'stopped')}), flush=True)
        if rows[-1]['outcome'] not in ('outer-boundary', 'native-startup-wait'):
            break
    assert len(rows) == 7 and rows[0]['outcome'] == 'outer-boundary'
    assert all(row['outcome'] == 'native-startup-wait' and not row['fault'] for row in rows[1:])
    assert h.get32(STATE + 16) == 0 and h.get32(SRAM + 0x184c) != 0
    bridge_base = (HEAP + struct.unpack_from('<I', prior_metadata, 20)[0] + 31) & ~31
    assert h.get32(SRAM + 0x184c) == bridge_base
    after_metadata = composition.allocator.state(h)
    assert struct.unpack_from('<I', after_metadata, 8)[0] == struct.unpack_from('<I', prior_metadata, 8)[0] + 1
    assert struct.unpack_from('<I', after_metadata, 20)[0] == bridge_base - HEAP + composition.layout.LAYOUT_HYPOTHESIS
    writes = [(int(event['address'], 16), event['value']) for event in h.mmio
              if event['kind'] == 'mmio-write' and BRIDGE <= int(event['address'], 16) < BRIDGE + 0x1000]
    assert writes == [(BRIDGE + 8, bridge_base & 0x1fffffff), (BRIDGE + 0x10, 0x40800),
                      (BRIDGE + 0x18, 1), *[(address, 1) for address in CHANNELS]]
    h.check_hooks()
    assert before == bindings(), 'input-drift'
    result = dict(schema=1, passed=True, layout=layout, harts=rows,
                  host=host, native_tx_publication=published,
                  guards=checks, rejected_mutants=killed, inputs_before_after=before,
                  original_failure_control=original, bridge_base=hex(bridge_base), bridge_writes=writes,
                  commands=composition.COMMANDS, unicorn=composition.unicorn.__version__,
                  compiler=composition.execute(['clang', '--version']).splitlines()[0],
                  binaries={str(path.relative_to(ROOT)): composition.sha(path)
                            for path in sorted(set([*paths, *parts.values(), dest / 'host']))},
                  hooks=h.patches, hardware_drains='synthetic completions only',
                  physical_tested=False, full_postgate_boot=False,
                  limits=['Only hart7 reaches its outer loop. Other workers still need later host setup.',
                          'Two SET19 callbacks execute directly; strict transport still rejects them.',
                          'No INODE/provider framing change or DESC5/6/7/8 callback executes.',
                          'Drain completions, timer, PCIe indexes, PLIC, locks and placement are modeled.',
                          'No bootable replacement, image, router access or physical recovery proof.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, guards=len(checks), mutants=len(killed),
                          receipt=str((dest / 'result.json').relative_to(ROOT)))), flush=True)


if __name__ == '__main__':
    main()
