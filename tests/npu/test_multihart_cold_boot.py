#!/usr/bin/env python3
"""Actual hart reset/prologues with installed candidate gates; explicit models."""
import json
import argparse
from collections import Counter
import hashlib
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_CODE
from unicorn import riscv_const as r

from test_native_wifi_boot import NativeWifi, host_publish, footprints, L2, L2_BYTES
from test_bootstrap_native import sequence, ROOT, sha, BOOT
from test_startup_native import STARTUP
from test_boot_irq_installation import UnmodeledAccess, REGS, IRQ8
from test_admission_protocol import packet
from test_barrier_core5 import SITES as CORE5_SITES, jump
from test_barrier_workers import SITES as WORKER_SITES
from test_firmware_memory_layout import STACK_TOPS
from emulation_layout import CODE, SRAM, STATE

OUT = ROOT / 'research/checkpoints/2026-09-06-npu-allhart'
ELF = ROOT / '.local/npu-barrier/admission-platform-bootstrap-bootstrap-startup-gdma-gdma-65536.elf'
ELF_SHA = 'bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931'
POWERDOWN_INPUTS = {0x1fac080c: 0x01234000, 0x1fae080c: 0x02234000}
POWERDOWN_TARGETS = {0xa1234000: 0x1fac080c, 0xa2234000: 0x1fae080c}
STARTUPS = {hart: (site, f'gate_core{hart}_{kind}', next_, alternate)
            for site, (hart, kind, expected, reg, next_, alternate) in WORKER_SITES.items()
            if kind == 'startup'}
STARTUPS[5] = (0x8400cb3e, 'gate_core5_startup', 0x8400cb42, 0x8400cb3e)
STARTUP_PCS = {row[0] for row in STARTUPS.values()}


class AllHarts(NativeWifi):
    def __init__(self, path, chip=0x100000, variant=0, powerdown='sentinel',
                 plic='flat', omit=None, extension_csr=True, missing=None):
        self.plic = plic
        self.plic_banks = [{} for _ in range(8)]
        self.omit = omit
        super().__init__(path)
        self.missing = missing
        self.cpu.mem_map(0x1fb00000, 0x1000)
        self.put32(0x1fb00064, chip)
        self.put32(0x1fb00284, variant)
        for base in (0x1fac0000, 0x1fae0000, 0x1fa5b000, 0x1fa5c000, *POWERDOWN_TARGETS):
            self.cpu.mem_map(base, 0x1000)
        self.put32(0x1fa5b460, 0xa5a5a5a5)
        self.put32(0x1fa5c460, 0xa5a5a5a5)
        for address, value in POWERDOWN_INPUTS.items():
            self.put32(address, 0xdeadbeef if powerdown == 'sentinel' else value)
        extra = {site: (f'gate_core{hart}_{kind}', expected)
                 for site, (hart, kind, expected, *_) in WORKER_SITES.items()}
        extra.update(CORE5_SITES)
        extra[0x840053a6] = ('npu_emulation_gdma_copy', '93174500')
        for site, (name, expected) in extra.items():
            assert bytes(self.cpu.mem_read(site, 4)).hex() == expected
            if site == omit:
                continue
            target = self.rv.symbols[name]
            replacement = jump(site, target)
            self.cpu.mem_write(site, replacement)
            self.patches.append({'site': hex(site), 'name': name, 'before': expected,
                                 'after': replacement.hex(), 'target': hex(target)})
        assert len(self.patches) == 26 - (omit is not None)
        if extension_csr:
            for name in ('npu_emulation_precheck_hart_csr', 'npu_emulation_startup_hart_csr'):
                pc = self.rv.symbols[name]
                self.cpu.hook_add(UC_HOOK_CODE, self.extension_hart, begin=pc, end=pc)
        self.fresh = self.cpu.context_save()
        self.contexts = {}

    def record(self, kind, **details):
        return super().record(kind, hart=self.hart, **details)

    def register_model(self, address, write):
        if address == self.missing:
            return None
        if self.plic == 'banked' and self.banked_address(address):
            return 'per-hart PLIC storage hypothesis; no physical banking/arbitration/delivery proof'
        if not write and address in (0x1fb00064, 0x1fb00284):
            return 'synthetic chip/variant input to native module table; not observed W1700K identity'
        if not write and address in POWERDOWN_INPUTS:
            return 'native power-down register input; synthetic absent sentinel or indirect target'
        if write and address in POWERDOWN_TARGETS:
            return 'native indirect power-down target storage only; no physical peripheral effect'
        if address == 0x1fb00830:
            return 'native chip-feature power-down control storage only; no physical effect'
        if write and address in (0x1fa5b460, 0x1fa5c460):
            return 'native chip-feature fixed zero-write storage; physical peripheral meaning unproved'
        return super().register_model(address, write)

    @staticmethod
    def banked_address(address):
        return address in (0x0c200000, 0x0c200004) or any(
            base <= address <= base+24 and not address % 4 for base in (0x0c002000, 0x0c003000))

    def read_hook(self, cpu, access, address, size, value, data):
        if self.plic == 'banked' and self.banked_address(address):
            self.put32(address, self.plic_banks[self.hart].get(address, 0))
        super().read_hook(cpu, access, address, size, value, data)

    def write_hook(self, cpu, access, address, size, value, data):
        super().write_hook(cpu, access, address, size, value, data)
        if STATE+20 <= address < STATE+52 and value:
            assert address == STATE+20+self.hart*4 and size == 4
            assert not cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
            self.record('parked-owner-write', address=hex(address), value=value)
        if self.plic == 'banked' and self.banked_address(address):
            self.plic_banks[self.hart][address] = value

    def code_hook(self, cpu, pc, size, data):
        super().code_hook(cpu, pc, size, data)
        if pc in STARTUP_PCS:
            self.record('startup-site', installed=pc != self.omit)
        if pc in (self.rv.symbols['npu_barrier_init'], self.rv.symbols['npu_emulation_admission_init']):
            self.record('candidate-initializer')

    def extension_hart(self, cpu, pc, size, data):
        word = self.get32(pc)
        assert word >> 20 == 0xf14 and word & 0x707f == 0x2073
        cpu.reg_write(REGS[(word >> 7) & 31], self.hart)
        cpu.reg_write(r.UC_RISCV_REG_PC, pc+4)
        self.record('extension-mhartid-model', source_pc=hex(pc), value=self.hart)

    def coordinator(self):
        self.hart = 0
        self.cpu.context_restore(self.fresh)
        self.reset()
        for words in sequence():
            assert self.message(words)['flags'] == 7
        assert self.run(self.cpu.reg_read(r.UC_RISCV_REG_PC), [0x8400d1d4]) == 0x8400d1d4
        assert self.l2_writes*4 == L2_BYTES
        assert bytes(self.cpu.mem_read(L2, L2_BYTES)) == bytes(L2_BYTES)
        self.l2_clear_active = False
        assert self.run(0x8400d1d4, [0x8400f836]) == 0x8400f836
        footprint = footprints(self)
        host_publish(self, staggered=False)
        self.contexts[0] = self.cpu.context_save()
        return footprint

    def early_worker(self, hart):
        self.hart = hart
        self.cpu.context_restore(self.fresh)
        stop = self.rv.symbols['npu_emulation_startup_wait']
        assert self.reset(stop) == stop
        assert self.get32(STATE) == 0 and self.get32(STATE+20+hart*4) == 0
        self.contexts[hart] = self.cpu.context_save()

    def worker(self, hart):
        self.hart = hart
        self.cpu.context_restore(self.contexts.get(hart, self.fresh))
        start = self.cpu.reg_read(r.UC_RISCV_REG_PC) if hart in self.contexts else CODE
        begin = len(self.events)
        poll = self.rv.symbols['npu_barrier_poll']
        faults = [self.rv.symbols[name] for name in (
            'npu_emulation_startup_fault', 'npu_emulation_startup_precheck_fault')]
        if start == CODE:
            self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
        else:
            assert not self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        assert self.run(start, [poll, *faults]) == poll
        assert self.get32(STATE+20+hart*4) == 0
        sites = [e for e in self.events[begin:] if e['kind'] == 'startup-site']
        assert len(sites) == 1 and sites[0]['pc'] == hex(STARTUPS[hart][0])
        assert self.run(poll, [poll]) == poll
        epoch = self.get32(STATE)
        assert self.get32(STATE+20+hart*4) == epoch
        assert not self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        sp = self.cpu.reg_read(r.UC_RISCV_REG_SP)
        assert STACK_TOPS[hart]-0x4000 <= sp < STACK_TOPS[hart]
        assert self.cpu.reg_read(r.UC_RISCV_REG_GP) == SRAM+0x13a8
        assert self.get32(IRQ8) == self.rv.symbols['npu_emulation_mailbox']
        self.contexts[hart] = self.cpu.context_save()
        entries = sorted({e['pc'] for e in self.events[begin:] if e['kind'] == 'entry'})
        return {'hart': hart, 'parked': epoch, 'pc': hex(poll), 'sp': hex(sp),
                'entry_from_early_wait': start != CODE, 'startup_site': sites[0]['pc'],
                'native_entry_sites_observed': entries}

    def control(self, operation, epoch=0, nonce=(0, 0)):
        previous_hart, context = self.hart, self.cpu.context_save()
        self.hart = 0
        self.cpu.context_restore(self.contexts[0])
        result = self.message(packet(operation, epoch, nonce))
        self.cpu.context_restore(context)
        self.hart = previous_hart
        assert result['flags'] == 7 and result['words'][10] == 7
        return result['words']

    def repoll(self, hart):
        self.hart = hart
        self.cpu.context_restore(self.contexts[hart])
        pc = self.cpu.reg_read(r.UC_RISCV_REG_PC)
        assert self.run(pc, [pc]) == pc
        assert self.get32(STATE+20+hart*4) == self.get32(STATE)
        self.contexts[hart] = self.cpu.context_save()

    def plic_snapshot(self):
        if self.plic == 'banked':
            return [hex(bank.get(0x0c002000, 0)) for bank in self.plic_banks]
        return [hex(self.get32(0x0c002000))]


def scenario(order, chip=0x100000, variant=0, powerdown='sentinel', plic='flat'):
    h = AllHarts(ELF, chip, variant, powerdown, plic)
    early, workers = [], []
    nonce = (0x10203040, 0x50607080)
    status_rows, mask = [], 1

    def stop_status(hart):
        nonlocal mask
        mask |= 1 << hart
        stopped = h.control(2, 1, nonce)
        assert stopped[6] == 1 and stopped[9] == 0 and stopped[11:] == [mask, 0, 0, 0, 0]
        status_rows.append({'hart': hart, 'epoch': 1, 'parked_mask': mask})

    for hart in order:
        if hart == 0:
            footprint = h.coordinator()
            assert h.control(1, 1, nonce)[9] == 0
            stop_status(0)
        elif 0 not in h.contexts:
            h.early_worker(hart)
            early.append(hart)
        else:
            workers.append(h.worker(hart))
            stop_status(hart)
    for hart in reversed(early):
        workers.append(h.worker(hart))
        stop_status(hart)
    assert len(workers) == 7
    assert [h.get32(STATE+20+i*4) for i in range(8)] == [1]*8
    assert [h.get32(STARTUP+20+i*4) for i in range(8)] == [1]*8
    assert h.get32(STARTUP+12) == 2 and h.get32(STARTUP+16) == 0
    assert h.get32(IRQ8) == h.rv.symbols['npu_emulation_mailbox']
    initial = h.control(0)
    assert initial[6] == 1 and initial[9] == 0 and initial[11:] == [255, 0, 0, 0, 0]
    for pass_index in (0, 1):
        stopped = h.control(2, 1, nonce)
        assert stopped[6] == 1 and stopped[9] == 0 and stopped[11:] == [255, 0, 0, 0, 0]
        for hart in reversed(order) if pass_index == 0 else order:
            h.repoll(hart)
            status = h.control(3, 1, nonce)
            assert status[9] == 0 and status[11:] == [255, 0, 0, 0, 0]
    assert h.get32(STATE+16) == h.get32(STATE+8) == 0
    assert [h.get32(STATE+52+i*4) for i in range(13)] == [0]*13
    assert h.get32(BOOT+8) == 6 and h.get32(BOOT+16) == 0x1e
    initialized = [event for event in h.events if event['kind'] == 'candidate-initializer']
    assert len(initialized) == 2 and all(event['hart'] == 0 for event in initialized)
    owners = Counter(event['hart'] for event in h.events if event['kind'] == 'parked-owner-write')
    assert owners == {hart: 3 for hart in range(8)}
    assert hashlib.sha256(h.cpu.mem_read(L2, L2_BYTES)).hexdigest() == footprint['l2_sha256']
    assert not any(event['pc'] == '0x840053a6' for event in h.events if event['kind'] == 'entry')
    plic_state = h.plic_snapshot()
    if plic == 'banked':
        assert int(plic_state[0], 16) & (1 << 9)
    else:
        assert not int(plic_state[0], 16) & (1 << 9)
    outputs = {hex(address): hex(h.get32(address)) for address in POWERDOWN_TARGETS}
    if chip == 0x100000 and variant == 5 and powerdown == 'indirect':
        assert outputs == {hex(k): hex(v) for k, v in POWERDOWN_TARGETS.items()}
        assert h.get32(0x1fa5b460) == h.get32(0x1fa5c460) == 0
        assert h.get32(0x1fb00830) == 0x8000
    groups = Counter((e['kind'], e['pc'], e['address'], e['value'], e['hart'])
                     for e in h.mmio if e['address'] in {
                         hex(address) for address in (*POWERDOWN_INPUTS, *POWERDOWN_TARGETS,
                                                       0x1fb00064, 0x1fb00284, 0x1fb00830,
                                                       0x1fa5b460, 0x1fa5c460)})
    return {'order': order, 'early_waiting_harts': early, 'synthetic_chip': hex(chip),
            'synthetic_variant': hex(variant), 'selected_native_chip_index': h.get32(SRAM+0xba8),
            'powerdown_model': powerdown, 'plic_model': plic, 'plic_enable_word0': plic_state,
            'workers': workers, 'status_progress': status_rows, 'final_parked': [1]*8,
            'parked_write_counts_by_owner': dict(owners), 'candidate_initializers': initialized,
            'idempotent_stop_repoll_passes': 2,
            'ready_and_drained': [0]*13, 'released': 0, 'armed': 0,
            'coordinator_footprint': footprint, 'powerdown_outputs': outputs,
            'chip_feature_control': hex(h.get32(0x1fb00830)),
            'system_mmio': [{'kind': key[0], 'pc': key[1], 'address': key[2],
                             'value': key[3], 'hart': key[4], 'count': count}
                            for key, count in groups.items()]}


def missing_gates():
    rows = []
    for hart, (site, name, next_, alternate) in sorted(STARTUPS.items()):
        h = AllHarts(ELF, omit=site)
        h.coordinator()
        h.hart = hart
        h.cpu.context_restore(h.fresh)
        assert h.reset(site) == site
        targets = [h.rv.symbols['npu_barrier_poll'], next_]
        if alternate:
            targets.append(alternate)
        stop = h.run(site, targets)
        assert stop != targets[0] and h.get32(STATE+20+hart*4) == 0
        rows.append({'hart': hart, 'omitted_site': hex(site), 'native_boundary': hex(stop),
                     'missing_ack': True})
    return rows


def negative_inputs():
    rows = []
    for address in (0x1fb00064, 0x1fac080c, 0xa1234000, 0x1fa5b460):
        h = AllHarts(ELF, variant=5, powerdown='indirect', missing=address)
        h.coordinator()
        try:
            h.worker(3)
        except UnmodeledAccess as error:
            assert hex(address) in str(error) and h.get32(STATE+32) == 0
            rows.append({'name': 'missing-startup-MMIO', 'address': hex(address), 'error': str(error)})
        else:
            raise AssertionError('unmodeled startup MMIO accepted')
    h = AllHarts(ELF, chip=0)
    h.coordinator()
    try:
        h.worker(3)
    except UnmodeledAccess as error:
        assert str(error) == 'write 0x1fb00040/4 at 0x84005a22'
        assert h.get32(STATE+32) == 0
        rows.append({'name': 'unknown-chip-native-reboot-boundary', 'error': str(error),
                     'physical_reboot_emulated': False})
    else:
        raise AssertionError('unknown chip skipped native reboot boundary')
    h = AllHarts(ELF, extension_csr=False)
    h.coordinator()
    h.hart = 1
    h.cpu.context_restore(h.fresh)
    fault = h.rv.symbols['npu_emulation_startup_fault']
    assert h.reset(fault) == fault
    assert h.get32(STARTUP+12) == 3 and h.get32(STATE+16) == 1 and h.get32(STATE+24) == 0
    assert h.get32(BOOT+16) == 0x1e
    rows.append({'name': 'missing-extension-hartid-model', 'fault': hex(fault),
                 'scope': 'Unicorn CSR default misidentifies hart1 as hart0; not a firmware defect.'})
    return rows


def inputs():
    previous = json.loads((ROOT / 'research/checkpoints/2026-09-06-npu-nativewifi/native-wifi-probe.json').read_text())
    result = {name: sha(ROOT / name) for name in previous['source_sha256']}
    assert result == previous['source_sha256']
    for module in list(sys.modules.values()):
        name = getattr(module, '__file__', None)
        if name:
            path = Path(name).resolve()
            if path.is_relative_to(ROOT / 'tests/npu') and path.suffix == '.py':
                result[str(path.relative_to(ROOT))] = sha(path)
    result[str(ELF.relative_to(ROOT))] = sha(ELF)
    return result


def suite():
    provenance = inputs()
    rows = []
    for index in range(8):
        order = list(range(8))
        order = order[index:] + order[:index]
        rows.append(scenario(order, plic='flat' if index % 2 else 'banked'))
        print(json.dumps({'reset_order': order, 'all_parked_epoch': 1}), flush=True)
    profiles = [(0xe0000, 0, 'sentinel'), (0xe0000, 2, 'indirect'),
                (0xe0000, 3, 'indirect'), (0xe0000, 6, 'indirect'),
                (0x100000, 5, 'sentinel'), (0x100000, 5, 'indirect')]
    for chip, variant, powerdown in profiles:
        rows.append(scenario([7, 3, 5, 0, 2, 4, 6, 1], chip, variant, powerdown, 'banked'))
        print(json.dumps({'chip': hex(chip), 'variant': variant, 'powerdown': powerdown,
                          'all_parked_epoch': 1}), flush=True)
    controls = missing_gates()
    negatives = negative_inputs()
    assert provenance == inputs()
    return {'passed': True, 'elf_sha256': ELF_SHA, 'source_sha256': provenance,
            'cases': rows, 'missing_gates': controls, 'input_controls': negatives,
            'patches': AllHarts(ELF).patches,
            'scope': 'Serialized actual resets through first worker gates plus repeated idempotent STOP requests. '
                     'Both flat and per-hart PLIC storage hypotheses, synthetic chip/peripheral inputs. '
                     'No hardware IRQ banking/delivery, cache/DMA containment, full post-gate initialization, '
                     'packet processing, production loader, full attach or restart proof.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chip', type=lambda value: int(value, 0), default=0x100000)
    parser.add_argument('--variant', type=lambda value: int(value, 0), default=0)
    parser.add_argument('--powerdown', choices=('sentinel', 'indirect'), default='sentinel')
    parser.add_argument('--suite', action='store_true')
    args = parser.parse_args()
    assert sha(ELF) == ELF_SHA
    if args.suite:
        result = suite()
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'allhart-native.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({'passed': True, 'cases': len(result['cases']),
                          'missing_gate_controls': len(result['missing_gates']),
                          'input_controls': len(result['input_controls'])}))
        return
    h = AllHarts(ELF, args.chip, args.variant, args.powerdown)
    footprint = h.coordinator()
    result = {'complete': False, 'elf_sha256': ELF_SHA, 'coordinator_footprint': footprint,
              'synthetic_chip': hex(args.chip), 'synthetic_variant': hex(args.variant),
              'powerdown_model': args.powerdown,
              'workers': [], 'patches': h.patches}
    for hart in range(1, 8):
        try:
            result['workers'].append(h.worker(hart))
            print(json.dumps({'hart': hart, 'parked': 1}), flush=True)
        except UnmodeledAccess as error:
            result['boundary'] = {'hart': hart, 'error': str(error)}
            break
    else:
        result['complete'] = True
    result['parked'] = [h.get32(STATE+20+i*4) for i in range(8)]
    result['ready_and_drained'] = [h.get32(STATE+52+i*4) for i in range(13)]
    result['powerdown_outputs'] = {hex(address): hex(h.get32(address)) for address in POWERDOWN_TARGETS}
    result['chip_feature_control'] = hex(h.get32(0x1fb00830))
    assert result['ready_and_drained'] == [0]*13 and h.get32(STATE+8) == 0
    result['scope'] = ('Exploratory serialized actual-reset multi-hart instruction trace with candidate gates. '
                       'No physical concurrency, DMA/cache/IRQ behavior, containment, attach or restart proof.')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'allhart-probe.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({key: value for key, value in result.items()
                      if key in ('complete', 'boundary', 'parked')}))


if __name__ == '__main__':
    main()
