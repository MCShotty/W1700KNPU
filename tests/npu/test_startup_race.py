#!/usr/bin/env python3
"""Instruction-paused startup fault/publication counterexamples in RV32."""
import json
import sys

sys.dont_write_bytecode = True
from unicorn import UC_HOOK_CODE
from unicorn import riscv_const as r
from test_startup_protocol import Pair, build, SOURCE, REGS, FAULT, CONTINUE
from test_startup_native import ROOT, OUT, BUILD, STARTUP, sha
from test_barrier_protocol import END


def instrument(source, tag):
    anchors = {
        'before_cas': '    if (__atomic_compare_exchange_n(&s->phase, &expected, NPU_STARTUP_READY,',
        'before_phase': '    phase = load(&s->phase);',
        'after_phase': '    phase = load(&s->phase);',
        'after_fault': '    __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);',
    }
    text = source
    text = text.replace('static enum npu_startup_action fail(',
                        'static __attribute__((noinline)) enum npu_startup_action fail(')
    text = text.replace('enum npu_startup_action npu_startup_poll(',
                        '__attribute__((noinline)) enum npu_startup_action npu_startup_poll(')
    for name, anchor in anchors.items():
        assert text.count(anchor) == 1, name
        marker = '    __asm__ volatile (".global race_' + name + '\\nrace_' + name + ': nop" ::: "memory");'
        text = text.replace(anchor, marker+'\n'+anchor if name.startswith('before') else anchor+'\n'+marker)
    path = BUILD / ('race-' + tag + '.c')
    path.write_text(text)
    return build(path)


class Race:
    def __init__(self, paths):
        self.pair = Pair(paths)
        self.cpu = self.pair.rv.cpu
        self.stop_at = None
        self.hit = None
        self.cpu.hook_add(UC_HOOK_CODE, self.hook)
        self.pair.initialized()
        assert self.pair.call('s', 'arrive', 1, 0) == 0
        assert self.pair.call('s', 'arrive', 2, 0) == 0

    def hook(self, cpu, address, size, data):
        if address == self.stop_at:
            self.hit = address
            cpu.emu_stop()

    def call(self, hart, name, args, pause=None, context=None):
        if context is None:
            values = [STARTUP]
            if name == 'publish':
                values += [self.pair.address[k] for k in ('b', 'a', 'm')]
            values += list(args)
            for reg, value in zip(REGS, values):
                self.cpu.reg_write(reg, value)
            self.cpu.reg_write(r.UC_RISCV_REG_SP, 0x84020000 + hart*0x1000)
            self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
            start = self.pair.rv.symbols['npu_startup_'+name]
        else:
            self.cpu.context_restore(context)
            start = self.cpu.reg_read(r.UC_RISCV_REG_PC)
        self.stop_at = self.pair.rv.symbols['race_'+pause] if pause else None
        self.hit = None
        self.cpu.emu_start(start, END, count=30000, timeout=1000000)
        assert self.cpu.reg_read(r.UC_RISCV_REG_PC) == (self.stop_at or END), (
            name, pause, hex(self.cpu.reg_read(r.UC_RISCV_REG_PC)), hex(self.stop_at or END),
            self.word(12), self.word(16), self.cpu.reg_read(r.UC_RISCV_REG_A0))
        return self.cpu.reg_read(r.UC_RISCV_REG_A0), self.cpu.context_save()

    def word(self, offset):
        return int.from_bytes(self.cpu.mem_read(STARTUP+offset, 4), 'little')


def publication_race(paths):
    h = Race(paths)
    _, publisher = h.call(0, 'publish', (0,), 'before_cas')
    _, poller = h.call(2, 'poll', (2,), 'before_phase')
    _, failing = h.call(1, 'arrive', (1, 0), 'after_fault')
    phase_before_publish = h.word(12)
    assert h.word(16) == 1
    published, _ = h.call(0, 'publish', (), context=publisher)
    polled, _ = h.call(2, 'poll', (), context=poller)
    failure, _ = h.call(1, 'arrive', (), context=failing)
    assert failure == FAULT
    return {'phase_when_fault_latched': phase_before_publish,
            'publish_result': published, 'poll_result': polled}


def acquired_ready_race(paths):
    h = Race(paths)
    assert h.call(0, 'publish', (0,))[0] == 1
    _, poller = h.call(2, 'poll', (2,), 'after_phase')
    assert h.call(1, 'arrive', (1, 0))[0] == FAULT
    assert h.word(12) == 3 and h.word(16) == 1
    return h.call(2, 'poll', (), context=poller)[0]


def main():
    current = SOURCE.read_text()
    fixed_order = ('    /* FAILED arbitrates with the publisher\'s CAS before the fault latch. */\n'
                   '    __atomic_store_n(&s->phase, NPU_STARTUP_FAILED, __ATOMIC_RELEASE);\n'
                   '    __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);')
    old_order = ('    __atomic_store_n(&s->fault, 1, __ATOMIC_RELEASE);\n'
                 '    __atomic_store_n(&s->phase, NPU_STARTUP_FAILED, __ATOMIC_RELEASE);')
    fixed_poll = ('    if (phase == NPU_STARTUP_READY) {\n'
                  '        if (load(&s->fault))\n            return fail(s);\n'
                  '        return NPU_STARTUP_CONTINUE;\n    }')
    assert fixed_order in current and fixed_poll in current
    old = current.replace(fixed_order, old_order).replace(fixed_poll,
        '    if (phase == NPU_STARTUP_READY)\n        return NPU_STARTUP_CONTINUE;')
    assert sha(old.encode()) == '9580a0d0bcc6ae1d00e0792228aeabe092ac26c968ff2e78d85b9e22fc48f914'
    result = {}
    for tag, text in [('preimage', old), ('fixed', current)]:
        paths = instrument(text, tag)
        result[tag] = {'publication': publication_race(paths),
                       'fault_after_ready_acquire': acquired_ready_race(paths),
                       'instrumented_elf_sha256': sha(paths[1].read_bytes())}
    assert result['preimage']['publication'] == {'phase_when_fault_latched': 1,
                                                'publish_result': 1, 'poll_result': CONTINUE}
    assert result['preimage']['fault_after_ready_acquire'] == CONTINUE
    assert result['fixed']['publication'] == {'phase_when_fault_latched': 3,
                                             'publish_result': 0, 'poll_result': FAULT}
    assert result['fixed']['fault_after_ready_acquire'] == FAULT
    result.update({'passed': True, 'source_sha256': sha(SOURCE.read_bytes()),
                   'scope': 'Three saved RV32 contexts; source with memory-clobber NOP pause labels and noinline on fault/poll helpers. No simultaneous-hardware/cache proof or instantaneous containment of a hart already past the gate.'})
    (OUT / 'startup-race-tests.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
