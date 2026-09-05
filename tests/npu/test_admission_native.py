#!/usr/bin/env python3
"""Coordinator IRQ/idle and mailbox adapters against native firmware handlers."""
import json
import shutil
import struct
import subprocess

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_READ
from unicorn import riscv_const as r

from test_admission_protocol import ROOT, OUT, BUILD, SOURCE, ADMISSION, ADM, packet, REGS
from test_barrier_protocol import Rv32, STATE, STACK, END, digest
from test_barrier_core5 import jump
from test_firmware_mailbox_dispatch import Mailbox, MBOX, CALLBACK, PAYLOAD
from test_firmware_stop_irqs import DISPATCH, UART, PPE, FREE
from test_firmware_stop_counterexample import SRAM, CODE_SHA, DATA_SHA
from test_barrier_workers import Worker, SITES as WORKER_SITES, ENTRIES, OUTER, HELPERS
from test_barrier_core5 import SITES as CORE5_SITES
import test_barrier_workers as worker_suite
import test_barrier_core5 as core5_suite

PLATFORM = ROOT / 'tests/npu/admission-platform-emulation.c'
ASSEMBLY = ROOT / 'tests/npu/admission-emulation.S'
HOOKS = {0x840030b2: ('npu_emulation_irq_dispatch', '411122c4'),
         0x84000188: ('npu_coordinator_main_return', 'b2400145')}


def build_platform(state_address=None):
    lld = shutil.which('ld.lld') or str(BUILD / 'lld/usr/lib/llvm-21/bin/ld.lld')
    tag = '' if state_address is None else '-' + hex(state_address)
    path = BUILD / ('admission-platform' + tag + '.elf')
    extra = [] if state_address is None else [f'-Wl,--defsym=npu_emulation_barrier_state={state_address}']
    subprocess.run([shutil.which('clang'), '--target=riscv32', '-march=rv32imac_zicsr',
                    '-mabi=ilp32', '-O2', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
                    '-nostdlib', '-fno-stack-protector', f'--ld-path={lld}',
                    '-I', str(SOURCE.parent), str(SOURCE), str(ADMISSION),
                    str(ROOT / 'tests/npu/barrier-core5-emulation.S'),
                    str(ROOT / 'tests/npu/barrier-workers-emulation.S'), str(PLATFORM), str(ASSEMBLY),
                    *extra, '-Wl,-T,' + str(ROOT / 'tests/npu/barrier-workers-emulation.ld') + ',--no-relax',
                    '-Wl,--defsym=original_irq_30b6=0x840030b6', '-o', str(path)],
                   check=True, capture_output=state_address is not None, text=True)
    return path


class Coordinator(Mailbox):
    def __init__(self, path, omit=None):
        self.idle_context = None
        self.watch_idle = self.skip_idle = self.finish_free = False
        super().__init__()
        self.register(22, UART)
        self.register(95, PPE)
        self.barrier = Rv32(path, self.cpu)
        assert self.barrier.symbols['npu_emulation_barrier_state'] == STATE
        assert self.barrier.symbols['npu_emulation_admission_state'] == ADM
        assert self.barrier.symbols['npu_emulation_masked_state'] == ADM + 0x40
        self.patches = []
        for address, (name, expected) in HOOKS.items():
            assert bytes(self.cpu.mem_read(address, 4)).hex() == expected
            if omit != address:
                target = self.barrier.symbols[name]
                self.cpu.mem_write(address, jump(address, target))
                self.patches.append({'site': hex(address), 'preimage': expected,
                                     'target': hex(target), 'postimage': jump(address, target).hex()})
        self.put32(SRAM + 0x1850 + 8 * 4, self.barrier.symbols['npu_emulation_mailbox'])
        self.cpu.hook_add(UC_HOOK_CODE, self.idle_hook,
                          begin=self.barrier.symbols['npu_emulation_idle_irq_window'],
                          end=self.barrier.symbols['npu_emulation_idle_irq_window'])
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.ppe_pop, begin=0x1fb50fe0, end=0x1fb50fe3)
        self.call('b:init')
        self.cpu.mem_write(ADM + 0x40, b'\xff' * 24)
        self.call('e:admission_init')
        assert bytes(self.cpu.mem_read(ADM + 0x40, 24)) == bytes(24)
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)

    def invoke(self, address, args, halt=None):
        # Separate modeled IRQ stack, below the saved coordinator idle frame.
        # This invokes functions directly, not the hardware trap entry sequence.
        self.cpu.reg_write(r.UC_RISCV_REG_SP, 0x84020e00)
        self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        for register, value in zip(REGS, args):
            self.cpu.reg_write(register, value)
        self.cpu.emu_start(address, END, count=50000, timeout=1000000)
        assert self.cpu.reg_read(r.UC_RISCV_REG_PC) == (halt or END)

    def free_hook(self, cpu, address, size, data):
        if self.finish_free:
            cpu.reg_write(r.UC_RISCV_REG_A0, 0)
            cpu.reg_write(r.UC_RISCV_REG_PC, cpu.reg_read(r.UC_RISCV_REG_RA))
        else:
            super().free_hook(cpu, address, size, data)

    def ppe_pop(self, cpu, access, address, size, value, data):
        if value == 0x40000000:
            # One modeled completion entry; the native handler performs pop.
            self.put32(0x1fb50fe4, 0)

    def idle_hook(self, cpu, address, size, data):
        if self.watch_idle:
            if self.skip_idle:
                self.skip_idle = False
            else:
                cpu.emu_stop()

    def call(self, operation, *args):
        group, name = operation.split(':')
        context = self.cpu.context_save()
        prefix = {'a': 'npu_admission_', 'b': 'npu_barrier_', 'e': 'npu_emulation_'}[group]
        values = [STATE] if group == 'b' else ([ADM] if name == 'init' else [ADM, STATE])
        if group == 'e':
            values = []
        values.extend(args)
        if group == 'b' and name == 'poll':
            values.append(STATE + 0x1000)
        for register, value in zip(REGS, values):
            self.cpu.reg_write(register, value)
        self.cpu.reg_write(r.UC_RISCV_REG_SP, STACK)
        self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        self.cpu.emu_start(self.barrier.symbols[prefix + name], END, count=20000, timeout=1000000)
        assert self.cpu.reg_read(r.UC_RISCV_REG_PC) == END, operation
        result = self.cpu.reg_read(r.UC_RISCV_REG_A0)
        self.cpu.context_restore(context)
        return result

    def run_idle(self):
        self.watch_idle = True
        if self.idle_context is None:
            self.cpu.reg_write(r.UC_RISCV_REG_SP, 0x84021df0)
            self.put32(0x84021dfc, END)
            self.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
            start = 0x84000188
        else:
            self.cpu.context_restore(self.idle_context)
            start = self.cpu.reg_read(r.UC_RISCV_REG_PC)
        window = self.barrier.symbols['npu_emulation_idle_irq_window']
        self.skip_idle = start == window
        self.cpu.emu_start(start, END, count=20000, timeout=1000000)
        assert self.cpu.reg_read(r.UC_RISCV_REG_PC) == window
        assert self.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        self.idle_context = self.cpu.context_save()
        self.watch_idle = False

    def running(self):
        for hart in range(1, 8):
            assert self.call('b:poll', hart) == 0
        self.run_idle()
        assert self.call('b:workers_parked', 1) == 1
        for domain in range(5):
            assert self.call('b:record_drain', domain, 1) == 1
        assert self.call('b:prepare', 1) == 1
        assert self.call('b:release', 1) == 1
        for hart in range(1, 8):
            assert self.call('b:refreshed', hart, 1) == 1
        self.run_idle()
        assert self.call('b:arm', 1) == 1
        assert self.call('e:open') == 1

    def control_message(self, operation, epoch=0, nonce=(0, 0)):
        reply = self.message(packet(operation, epoch, nonce))
        assert reply['flags'] == 7
        assert reply['words'][2] == 0x3152514e
        assert reply['words'][10] == 7  # No physical drain/restart capability.
        return reply


def stopped_irqs(path, omit=None):
    coordinator = Coordinator(path, omit)
    coordinator.running()
    nonce = (0x12345678, 0x87654321)
    assert coordinator.control_message(0)['words'][9] == 0
    assert coordinator.control_message(1, 1, nonce)['words'][9] == 0
    reply = coordinator.control_message(2, 1, nonce)
    assert reply['words'][6] == 2 and reply['words'][9] == 0
    assert coordinator.barrier.snapshot()[5] == 1, 'mailbox IRQ published idle ACK'
    coordinator.run_idle()
    assert coordinator.barrier.snapshot()[5] == 2
    coordinator.put32(SRAM + 0x46ec, 0)
    for character in b'wt 3e9046ec 00000001\r':
        coordinator.character, coordinator.consumed = character, False
        coordinator.invoke(DISPATCH, (22,))
    assert coordinator.get32(SRAM + 0x46ec) == 0, 'UART write admitted while stopped'
    assert not coordinator.consumed
    coordinator.put32(0x1fb50fe4, 1)
    coordinator.put32(0x1fb50fe0, 0x11234)
    coordinator.invoke(DISPATCH, (95,))
    assert not coordinator.free_arguments
    assert coordinator.get32(0x1fb50fe4) == 1
    assert coordinator.get32(0x0c200004) == 96
    assert not coordinator.get32(0x0c002000) & (1 << 23)
    assert not coordinator.get32(0x0c00200c) & 1
    assert coordinator.get32(0x0c002000) & (1 << 9)
    before = coordinator.get32(CALLBACK)
    assert coordinator.message([0], function=12, static=True)['flags'] & 0x1c == 0
    assert coordinator.get32(CALLBACK) == before
    assert coordinator.message([0x12, 24, 0, 0, 0, 0])['flags'] == 3
    assert coordinator.get32(SRAM + 0x46ec) == 0
    status = coordinator.control_message(3)
    assert status['words'][11] == 1 and status['words'][13] == 0
    for hart in range(1, 8):
        assert coordinator.call('b:poll', hart) == 0
    assert coordinator.call('b:workers_parked', 2) == 1
    assert coordinator.call('b:reclaimable', 2) == 0
    assert coordinator.call('a:retire_irq', 95, 2) == 0
    # This is the modeled platform-retirement boundary, not hardware proof.
    coordinator.put32(0x1fb50fe4, 0)
    coordinator.consumed = True
    for domain in range(5):
        assert coordinator.call('b:record_drain', domain, 2) == 1
    for source in (22, 95):
        assert coordinator.call('a:retire_irq', source, 2) == 1
    assert coordinator.call('b:prepare', 2) == 1
    assert coordinator.call('b:release', 2) == 1
    for hart in range(1, 8):
        assert coordinator.call('b:refreshed', hart, 2) == 1
    coordinator.run_idle()
    assert coordinator.call('e:open') == 0
    assert coordinator.call('b:arm', 2) == 1
    assert coordinator.call('e:open') == 1
    assert coordinator.get32(0x0c002000) & (1 << 23)
    assert coordinator.get32(0x0c00200c) & 1
    assert coordinator.message([0x12, 24, 0, 0, 0, 0])['flags'] == 7
    assert coordinator.get32(SRAM + 0x46ec) == 1
    return {'uart_not_consumed_or_executed': True, 'ppe_entry_retained': True,
            'mailbox_status_available': True, 'legacy_restart_denied_until_arm': True,
            'masked_irqs_restored_after_modeled_retirement_and_arm': True,
            'patches': coordinator.patches}


def inflight_irq(path):
    coordinator = Coordinator(path)
    coordinator.running()
    coordinator.put32(0x1fb50fe4, 1)
    coordinator.put32(0x1fb50fe0, 0x11234)
    coordinator.invoke(DISPATCH, (95,), halt=FREE)
    interrupt_context = coordinator.cpu.context_save()
    assert coordinator.get32(ADM + 4) == 1
    assert coordinator.call('a:close') == 2
    coordinator.run_idle()
    assert coordinator.barrier.snapshot()[5] == 1
    assert coordinator.call('b:workers_parked', 2) == 0
    coordinator.finish_free = True
    coordinator.cpu.context_restore(interrupt_context)
    coordinator.cpu.emu_start(FREE, END, count=50000, timeout=1000000)
    assert coordinator.cpu.reg_read(r.UC_RISCV_REG_PC) == END
    assert coordinator.get32(ADM + 4) == 0
    coordinator.run_idle()
    assert coordinator.barrier.snapshot()[5] == 2
    return {'native_ppe_handler_lease_held': True, 'ack_withheld': True,
            'free_body_return_modeled': True, 'ack_after_handler_and_dispatch_return': True}


def eight_contexts(path):
    coordinator = Coordinator(path)
    # Reuse the existing worker runner on the coordinator's memory image.
    # Its temporary private CPU has not executed a firmware workload.
    workers = Worker(path, 1)
    workers.cpu, workers.barrier = coordinator.cpu, coordinator.barrier
    workers.fixture()
    coordinator.phase = workers.phase = 'shared-eight-contexts'
    for address, (hart, kind, preimage, *_) in WORKER_SITES.items():
        assert bytes(coordinator.cpu.mem_read(address, 4)).hex() == preimage
        target = coordinator.barrier.symbols[f'gate_core{hart}_{kind}']
        coordinator.cpu.mem_write(address, jump(address, target))
    for address, (symbol, preimage) in CORE5_SITES.items():
        assert bytes(coordinator.cpu.mem_read(address, 4)).hex() == preimage
        coordinator.cpu.mem_write(address, jump(address, coordinator.barrier.symbols[symbol]))
    for address in {*WORKER_SITES, *CORE5_SITES, *HELPERS}:
        coordinator.cpu.hook_add(UC_HOOK_CODE, workers.worker_hook, begin=address, end=address)
    initial = coordinator.cpu.context_save()
    contexts = {}
    for hart in range(1, 8):
        coordinator.cpu.context_restore(initial)
        coordinator.hart = workers.hart = hart
        coordinator.cpu.reg_write(r.UC_RISCV_REG_SP, 0x84021e00 + hart * 0x4000)
        coordinator.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
        workers.execute({**ENTRIES, 5: 0x8400cb0e}[hart], count=60000)
        contexts[hart] = coordinator.cpu.context_save()
        assert coordinator.barrier.snapshot()[5 + hart] == 1
    coordinator.hart = 0
    coordinator.run_idle()
    assert coordinator.call('b:workers_parked', 1) == 1
    for domain in range(5):
        assert coordinator.call('b:record_drain', domain, 1) == 1
    assert coordinator.call('b:prepare', 1) == 1
    assert coordinator.call('b:release', 1) == 1
    for hart in range(1, 8):
        coordinator.hart = workers.hart = hart
        coordinator.cpu.context_restore(contexts[hart])
        workers.execute()
        contexts[hart] = coordinator.cpu.context_save()
        assert coordinator.barrier.snapshot()[13 + hart] == 1
    coordinator.hart = 0
    coordinator.run_idle()
    assert coordinator.call('b:arm', 1) == 1
    assert coordinator.call('e:open') == 1
    for hart in range(1, 8):
        coordinator.hart = workers.hart = hart
        coordinator.cpu.context_restore(contexts[hart])
        workers.until({**OUTER, 5: 0x8400cbbe}[hart])
        contexts[hart] = coordinator.cpu.context_save()
    coordinator.hart = 0
    nonce = (0x31415926, 0x27182818)
    assert coordinator.control_message(1, 1, nonce)['words'][9] == 0
    reply = coordinator.control_message(2, 1, nonce)
    assert reply['words'][6] == 2 and reply['words'][11] == 0
    order = (5, 2, 7, 1, 6, 4, 3)
    for index, hart in enumerate(order):
        coordinator.hart = workers.hart = hart
        coordinator.cpu.context_restore(contexts[hart])
        workers.execute()
        contexts[hart] = coordinator.cpu.context_save()
        assert coordinator.barrier.snapshot()[5 + hart] == 2
        assert not coordinator.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        coordinator.hart = 0
        status = coordinator.control_message(3)['words']
        assert status[11] == sum(1 << owner for owner in order[:index + 1])
        assert coordinator.call('b:record_drain', 0, 2) == 0
    coordinator.run_idle()
    status = coordinator.control_message(3)['words']
    assert status[11] == 0xff and status[13] == 0
    assert coordinator.call('b:workers_parked', 2) == 1
    assert coordinator.call('b:reclaimable', 2) == 0
    return {'native_worker_and_coordinator_contexts': 8, 'shared_sram': True,
            'worker_ack_order': list(order), 'all_acks_via_actual_code': True,
            'wire_status_parked_mask': status[11], 'no_drain_witnesses': True,
            'scope': 'Serialized RV32 contexts at worker entries/core0 return; modeled helper returns, MMIO and IRQ function invocation, no physical simultaneous-core or boot proof.'}


def mask_failures(path):
    cases = []
    for address, value in ((0x0c00200c, 1), (0x0c00300c, 0)):
        coordinator = Coordinator(path)
        coordinator.running()
        assert coordinator.call('a:close') == 2
        def stuck(cpu, access, target, size, old, data):
            coordinator.put32(target, value)
        coordinator.cpu.hook_add(UC_HOOK_MEM_READ, stuck, begin=address, end=address)
        coordinator.put32(0x1fb50fe4, 1)
        coordinator.put32(0x1fb50fe0, 0x11234)
        coordinator.invoke(DISPATCH, (95,))
        assert not coordinator.free_arguments
        assert coordinator.get32(ADM + 8) == 1 and coordinator.barrier.snapshot()[4] == 1
        coordinator.run_idle()
        assert coordinator.barrier.snapshot()[5] == 1
        assert coordinator.call('b:reclaimable', 2) == 0
        assert coordinator.control_message(3)['words'][9] == 6
        cases.append({'stuck_register': hex(address), 'forced_readback': value,
                      'barrier_faulted': True, 'status_remains_available': True})
    return cases


def mask_boundaries(path):
    coordinator = Coordinator(path)
    cases = []
    for source in (0, 31, 32, 63, 64, 95, 96, 159, 160, 191):
        coordinator.register(source, PPE if source == 95 else UART)
        coordinator.invoke(DISPATCH, (source,))
        offset = (source + 1) // 32 * 4
        bit = 1 << ((source + 1) % 32)
        assert not coordinator.get32(0x0c002000 + offset) & bit
        assert coordinator.get32(0x0c003000 + offset) & bit
        assert coordinator.get32(0x0c200004) == source + 1
        assert coordinator.get32(ADM + 20 + (source // 32) * 4) & (1 << (source % 32))
        cases.append(source)
    return cases


def irq_abi(path):
    coordinator = Coordinator(path)
    coordinator.running()
    registers = [getattr(r, 'UC_RISCV_REG_X' + str(index)) for index in (8, 9, *range(18, 28))]
    cases = []
    for state, source in (('running', 95), ('running', 8), ('closed', 95), ('closed', 22), ('closed', 8)):
        if state == 'closed' and coordinator.barrier.snapshot()[0] == 1:
            assert coordinator.call('a:close') == 2
        expected = [0x12340000 + index for index in range(len(registers))]
        for register, value in zip(registers, expected):
            coordinator.cpu.reg_write(register, value)
        gp = coordinator.cpu.reg_read(r.UC_RISCV_REG_GP)
        if source == 8:
            coordinator.control_message(3)
        else:
            coordinator.put32(0x1fb50fe4, 0)
            coordinator.invoke(DISPATCH, (source,))
        assert [coordinator.cpu.reg_read(register) for register in registers] == expected
        assert coordinator.cpu.reg_read(r.UC_RISCV_REG_SP) == 0x84020e00
        assert coordinator.cpu.reg_read(r.UC_RISCV_REG_GP) == gp
        assert coordinator.cpu.reg_read(r.UC_RISCV_REG_RA) == END
        assert not coordinator.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        cases.append({'state': state, 'source': source, 'callee_saved_sp_gp_ra_preserved': True})
    return cases


def main():
    path = build_platform()
    irqs = stopped_irqs(path)
    busy = inflight_irq(path)
    shared = eight_contexts(path)
    failed_masks = mask_failures(path)
    mask_edges = mask_boundaries(path)
    abi = irq_abi(path)
    combined_regressions = {
        'new_worker_register_cases': len(worker_suite.preservation(path)),
        'new_worker_stop_resume': len([worker_suite.stop_resume(path, site) for site in WORKER_SITES]),
        'new_worker_inflight': len([worker_suite.in_flight(path, hart, helper) for hart, helper in
                                   ((1, 0x8400bd96), (2, 0x8400e87a), (3, 0x8400f638),
                                    (4, 0x8400b0a6), (6, 0x8400c284), (7, 0x84001528))]),
        'new_worker_interrupted_refresh': len([worker_suite.refresh_interrupted(path, hart) for hart in ENTRIES]),
        'core5_stop_resume': len([core5_suite.stopped_at(path, site) for site in CORE5_SITES]),
        'core5_register_cases': len(core5_suite.passthrough(path)),
        'core5_inflight': core5_suite.inflight(path)['ack_withheld_until_helper_returns'],
    }
    try:
        stopped_irqs(path, omit=DISPATCH)
    except AssertionError as error:
        assert str(error) == 'UART write admitted while stopped', str(error)
        negative = {'rejected': True, 'assertion': str(error)}
    else:
        raise AssertionError('Missing IRQ admission accepted')
    malformed = Coordinator(path)
    malformed.running()
    before = malformed.get32(SRAM + 0x46ec)
    invalid = []
    for length in (0, 4, 257, 65536):
        reply = malformed.message([0x14, 24, 0, 0, 0, 0], length=length)
        assert reply['flags'] == 3 and not any(event['kind'] == 'payload-read' for event in reply['events'])
        assert malformed.get32(SRAM + 0x46ec) == before
        invalid.append(length)
    nowait = malformed.message([0x14, 24, 0, 0, 0, 0], wait=False)
    assert nowait['flags'] == 2 and malformed.get32(SRAM + 0x46ec) == before
    static_rejections = []
    for function in range(16):
        before_table = bytes(malformed.cpu.mem_read(0x3e900cfc, 80))
        reply = malformed.message([0x14, 24, 0, 0, 0, 0], function=function, static=True)
        assert reply['flags'] & 0x1c == 0
        assert bytes(malformed.cpu.mem_read(0x3e900cfc, 80)) == before_table
        assert not any(event['kind'] == 'payload-read' for event in reply['events'])
        static_rejections.append(function)
    for address in (0, 0x02000001):
        reply = malformed.message([0x14, 24, 0, 0, 0, 0], address=address)
        assert reply['flags'] == 3 and not any(event['kind'] == 'payload-read' for event in reply['events'])
    report = {'passed': True, 'elf_sha256': digest(path.read_bytes()),
              'firmware_sha256': CODE_SHA, 'data_sha256': DATA_SHA,
              'irq_stop_resume': irqs, 'inflight_irq': busy,
              'eight_shared_contexts': shared,
              'mask_readback_failures': failed_masks, 'irq_mask_boundary_sources': mask_edges,
              'static_registration_rejections': static_rejections,
              'irq_abi_cases': abi, 'dirty_saved_masks_cleared_on_cold_init': True,
              'combined_elf_worker_regressions': combined_regressions,
              'omitted_irq_admission': negative, 'invalid_lengths_rejected_before_read': invalid,
              'nowait_rejected_before_callback': True,
              'source_sha256': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in
                                (SOURCE, ADMISSION, ADMISSION.with_suffix('.h'), PLATFORM, ASSEMBLY,
                                 ROOT / 'tests/npu/test_admission_native.py',
                                 ROOT / 'tests/npu/test_admission_protocol.py',
                                 ROOT / 'tests/npu/test_firmware_mailbox_dispatch.py',
                                 ROOT / 'tests/npu/test_barrier_workers.py',
                                 ROOT / 'tests/npu/barrier-core5-emulation.S',
                                 ROOT / 'tests/npu/barrier-workers-emulation.S',
                                 ROOT / 'tests/npu/barrier-workers-emulation.ld')},
              'scope': 'Test-only core0 return/IRQ detours and mailbox IRQ table replacement, actual C admission and original UART/PPE/Wi-Fi callbacks. Eight saved contexts execute in the shared case; other cases model the seven workers. MMIO, IRQ function invocation, physical drain/retirement and in-flight bufid-free return are modeled. No full boot, hardware timing/coherency or deployable firmware proof.'}
    (OUT / 'admission-native-tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
