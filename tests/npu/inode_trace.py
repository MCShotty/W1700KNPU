"""Read-only original INODE stores, private journal, protected memory and ABI."""
import hashlib
import json
import struct
from unittest.mock import patch

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE, riscv_const as r
from emulation_layout import CODE
from test_firmware_memory_layout import STACK_TOPS
from test_firmware_stop_counterexample import END
from test_cold_txdone_native import SPACES
from pcie_tail_wire_native import MODEL_BAR_PAGES
from test_desc10_native_replay import compare
from test_inode_original_prefixes import recipe, ICV, ICV_BYTES

SITES = (0xe0c4, 0xe0ce, 0xe0d8, 0xe0e0, 0xe0e8, 0xe0f0,
         0xe178, 0xe180, 0xe18a, 0xe196, 0xe1b4)
LOCKS = (0x1ec031c8, 0x1ec03248)
SAVED = tuple(getattr(r, 'UC_RISCV_REG_S' + str(index)) for index in range(12)) + (
    r.UC_RISCV_REG_GP, r.UC_RISCV_REG_TP)


def original_events(stage):
    assert stage in (0, 1)
    sites = (0xe178, 0xe180, 0xe18a) + (0xe196,) * 1026 + (0xe1b4,) if stage == 0 else SITES[:6]
    effects = recipe(2 if stage == 0 else 7)
    assert len(sites) == len(effects) == (1030 if stage == 0 else 6)
    return tuple((CODE + site, *effect) for site, effect in zip(sites, effects))


def put(images, address, contents):
    base = next(base for base, data in images.items() if base <= address and address + len(contents) <= base + len(data))
    images[base][address - base:address - base + len(contents)] = contents


class InodeTrace:
    def __init__(self, h, request):
        self.h, self.request = h, tuple(request)
        self.stores, self.locks, self.entries, self.returns, self.hooks = [], [], [], [], []
        self._run, self._patch = h.run, None
        assert len(request) == 20 and request[:5] == [0x3f, 1, 0x3253434e, 2, 80]
        assert request[5] == 1 and request[12] == 24 and request[13:] == [0] * 7
        assert request[11] in (0x12, 0x17)
        self.stage = (0x12, 0x17).index(request[11])
        self.first, self.last = (0, 1030) if self.stage == 0 else (1030, 1036)
        self.events = original_events(self.stage)
        self.setup = h.rv.symbols['npu_emulation_cold_setup_state']
        setup = list(struct.unpack('<103I', h.cpu.mem_read(self.setup, 412)))
        assert setup[:3] == [0, 0, 131071] and setup[26] == 8 and setup[30] == 14
        assert setup[90] == 6 and setup[95] == setup[99] == 3 and setup[101] == self.stage
        assert setup[102] == 0 and setup[9:12] == ([0x1f, 0, 0] if self.stage == 0 else [0x12, 24, 0])
        assert setup[12:14] == [0x20000000, 0x100000] and setup[97] in (0x200d4450, 0x200d8450)
        session = h.rv.symbols['npu_emulation_control_v2_state']
        identity = struct.unpack('<5I', h.cpu.mem_read(session, 20))
        assert list(identity[:4]) == request[9:11] + request[7:9] == setup[4:8]
        assert setup[3] == identity[4] < request[6]
        tail = bytes(h.cpu.mem_read(h.pcie_tail.symbols['npu_emulation_pcie_tail_state'], 256))
        assert struct.unpack_from('<10I', tail) == (0x31545043, 1, 0, 0, 2, 7, 7, 9, 9, 511)
        assert struct.unpack_from('<4I', tail, 40 + 136 + 8) == (0x20000000, 0x100000, 0x200d4420, setup[97])
        assert h.get32(0x8401cfb8) == 0x109 and h.get32(0x8401cfbc) == h.get32(0x3e902ac0) == ICV
        expected_plan = tail[40:220] + struct.pack('<2I', ICV, ICV_BYTES)
        self.owner = h.inode.symbols['npu_emulation_inode_state']
        old_owner = bytes(h.cpu.mem_read(self.owner, 4372))
        if self.stage == 0:
            assert old_owner == bytes(4372)
        else:
            assert struct.unpack_from('<10I', old_owner) == (0x31444e49, 1, 0, 0, 0, 1, 1, 1030, 1030, 1030)
            assert old_owner[40:228] == expected_plan
        self.memory = {base: bytearray(h.cpu.mem_read(base, size)) for base, size in
                       (*SPACES, *((base, 4096) for base in MODEL_BAR_PAGES))}
        preimages = list(struct.unpack_from('<1036I', old_owner, 228))
        for index, (_, address, size, value) in enumerate(self.events, self.first):
            preimages[index] = int.from_bytes(h.cpu.mem_read(address, size), 'little')
            put(self.memory, address, value.to_bytes(size, 'little'))
        put(self.memory, session + 16, struct.pack('<I', request[6]))
        mask = (1 << (self.stage + 1)) - 1
        self.owner_expected = struct.pack('<10I', 0x31444e49, 1, 0, 0, self.stage,
            mask, mask, self.last, self.last, self.last) + expected_plan + struct.pack('<1036I', *preimages)
        setup[3], setup[9:12] = request[6], request[11:14]
        for target, source in ((8, 2), (14, 12), (15, 13), (28, 26), (29, 27), (31, 30),
                               (91, 90), (93, 92), (94, 92), (96, 95), (98, 97), (100, 99), (102, 101)):
            setup[target] = setup[source]
        setup[21:26], setup[61:90] = setup[16:21], setup[32:61]
        setup[101] += 1
        self.setup_expected = struct.pack('<103I', *setup)
        held = setup.copy()
        held[1], held[101] = 1, self.stage
        self.code_expected = {CODE: bytearray(h.cpu.mem_read(CODE, 0x200000))}
        put(self.code_expected, self.setup, self.setup_expected)
        self.private = {section['sh_addr']: bytearray(h.cpu.mem_read(section['sh_addr'], section['sh_size']))
                        for section in h.inode.elf.iter_sections()
                        if section['sh_flags'] & 3 == 3 and section['sh_size']}
        assert self.private and all(CODE + 0xf0000 <= base < base + len(data) <= CODE + 0xf8000
                                    for base, data in self.private.items())
        if self.stage == 0:
            assert all(not any(data) for data in self.private.values()), 'INODE-fresh-private'
        symbols = h.inode.elf.get_section_by_name('.symtab')

        def private_symbol(name):
            entries = [entry for entry in symbols.get_symbol_by_name(name) or () if entry['st_size'] and
                       any(base <= entry['st_value'] and entry['st_value'] + entry['st_size'] <= base + len(data)
                           for base, data in self.private.items())]
            assert len(entries) == 1, ('INODE-private-symbol', name)
            return entries[0]

        def private(name, contents):
            entry = private_symbol(name)
            assert entry['st_size'] == len(contents), ('INODE-private-size', name)
            put(self.private, entry['st_value'], contents)

        def integer(name, value):
            entry = private_symbol(name)
            assert entry['st_size'] in (1, 4)
            private(name, value.to_bytes(entry['st_size'], 'little'))

        private('npu_emulation_inode_state', self.owner_expected)
        integer('npu_emulation_inode_running', 0)
        integer('phase', self.stage)
        integer('lock_owned', 0)
        integer('neighbors_captured', 1)
        private('plan', expected_plan)
        private('held_setup', struct.pack('<103I', *held))
        if self.stage == 0:
            private('flag_neighbors', bytes(h.cpu.mem_read(0x3e9046dc, 36)))
            for index, address in enumerate((ICV - 4, ICV + ICV_BYTES)):
                private('icv_neighbors.' + str(index), bytes(h.cpu.mem_read(address, 4)))
        for base, contents in self.private.items(): put(self.code_expected, base, contents)
        self.saved_before = tuple(h.cpu.reg_read(register) for register in SAVED)
        self.interrupt_before = tuple(h.cpu.reg_read(register) for register in (r.UC_RISCV_REG_MIE, r.UC_RISCV_REG_MTVEC))
        self.sites = {h.inode.symbols[f'npu_emulation_inode_{site:x}_store']: CODE + site for site in SITES}
        self.entry_sites = {h.inode.symbols['npu_emulation_inode_callback']: 'callback',
            h.inode.symbols['npu_original_inode_callback']: 'wrapper', 0x8400e084: 'helper', 0x8400651c: 'release'}
        assert len(self.sites) == 11 and len(self.entry_sites) == 4

    def code(self, cpu, pc, size, unused):
        kind = self.entry_sites[pc]
        assert not cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
        if kind in ('callback', 'wrapper'):
            pointer = cpu.reg_read(r.UC_RISCV_REG_A0)
            length = 24 if kind == 'wrapper' else 12
            assert STACK_TOPS[0] - 0x4000 <= pointer <= STACK_TOPS[0] - length
            assert bytes(cpu.mem_read(pointer, length)) == struct.pack('<3I', *self.request[11:14]) + (bytes(12) if length == 24 else b'')
        if kind == 'callback':
            assert tuple(cpu.reg_read(register) for register in SAVED) == self.saved_before, 'INODE-entry-ABI'
        elif kind == 'helper':
            assert [cpu.reg_read(getattr(r, 'UC_RISCV_REG_A' + str(index))) for index in range(5)] == [
                2 if self.stage == 0 else 7, 0, 0, 0, 0], 'INODE-original-wrapper-arguments'
        elif kind == 'release':
            assert bytes(cpu.mem_read(self.owner, 4372)) == self.owner_expected, 'INODE-owner-before-unlock'
        self.entries.append(kind)

    def write(self, cpu, access, address, size, value, unused):
        pc = cpu.reg_read(r.UC_RISCV_REG_PC)
        if pc in self.sites:
            index = self.first + len(self.stores)
            assert index < self.last, 'extra-INODE-original-store'
            state = struct.unpack('<10I', cpu.mem_read(self.owner, 40))
            assert state == (0x31444e49, 1, 0, 1, self.stage, (1 << (self.stage + 1)) - 1,
                (1 << self.stage) - 1, index + 1, index, self.last), ('INODE-reserve-before-store', state)
            assert not cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
            assert self.h.get32(self.h.inode.symbols['npu_emulation_inode_running']) == 1
            admission = self.h.rv.symbols['npu_emulation_admission_state']
            assert self.h.get32(self.setup + 4) == self.h.get32(admission + 4) == 1
            assert self.h.get32(self.setup + 404) == self.stage
            self.stores.append((self.sites[pc], address, size, value & ((1 << (size * 8)) - 1)))
        if 0x1ec03180 <= address < 0x1ec03300:
            self.locks.append((address, size, value))

    def observe_return(self, start, stops):
        pc = self._run(start, stops)
        cpu = self.h.cpu
        self.returns.append(dict(pc=pc, saved=tuple(cpu.reg_read(register) for register in SAVED),
            sp=cpu.reg_read(r.UC_RISCV_REG_SP), mstatus=cpu.reg_read(r.UC_RISCV_REG_MSTATUS),
            interrupt=tuple(cpu.reg_read(register) for register in (r.UC_RISCV_REG_MIE, r.UC_RISCV_REG_MTVEC))))
        return pc

    def __enter__(self):
        assert not self.hooks and self._patch is None
        self._patch = patch.object(self.h, 'run', self.observe_return)
        self._patch.start()
        self.hooks.append(self.h.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write))
        for site in self.entry_sites:
            self.hooks.append(self.h.cpu.hook_add(UC_HOOK_CODE, self.code, begin=site, end=site))
        return self

    def __exit__(self, *error):
        for hook in reversed(self.hooks): self.h.cpu.hook_del(hook)
        self.hooks.clear()
        self._patch.stop()
        self._patch = None

    def validate(self):
        assert self.stores == list(self.events), ('INODE-original-stores', len(self.stores), len(self.events))
        assert self.locks == [(LOCKS[0], 4, 0x40), (LOCKS[1], 4, 0)], 'INODE-added-lock18'
        assert self.entries == ['callback', 'wrapper', 'helper', 'release'], ('INODE-original-entries', self.entries)
        assert self.returns == [dict(pc=END, saved=self.saved_before, sp=STACK_TOPS[0] - 0x1000,
            mstatus=0, interrupt=self.interrupt_before)], ('INODE-return-ABI-before-context-restore', self.returns)
        assert all(bytes(self.h.cpu.mem_read(base, len(data))) == data for base, data in self.memory.items()), 'INODE-protected-memory'
        assert bytes(self.h.cpu.mem_read(self.owner, 4372)) == self.owner_expected, 'INODE-owner-publication'
        assert bytes(self.h.cpu.mem_read(self.setup, 412)) == self.setup_expected, 'INODE-setup-journal'
        actual = bytearray(self.h.cpu.mem_read(CODE, 0x200000))
        begin, end = STACK_TOPS[0] - 0x4000 - CODE, STACK_TOPS[0] - CODE
        actual[begin:end] = self.code_expected[CODE][begin:end]
        assert actual == self.code_expected[CODE], 'INODE-code-or-private-mutation'

    def save(self, directory):
        directory.mkdir()
        protected = directory / 'protected'
        protected.mkdir()
        memory = compare(self.h, self.memory, protected)
        stores = b''.join(struct.pack('<4I', *event) for event in self.stores)
        expected = b''.join(struct.pack('<4I', *event) for event in self.events)
        for name, contents in (('actual-stores.bin', stores), ('expected-stores.bin', expected),
            ('owner-expected.bin', self.owner_expected), ('owner-actual.bin', bytes(self.h.cpu.mem_read(self.owner, 4372))),
            ('setup-expected.bin', self.setup_expected), ('setup-actual.bin', bytes(self.h.cpu.mem_read(self.setup, 412))),
            ('code-private-expected.bin', bytes(self.code_expected[CODE])),
            ('code-private-actual.bin', bytes(self.h.cpu.mem_read(CODE, 0x200000)))):
            with (directory / name).open('xb') as stream: stream.write(contents)
        result = dict(stage=self.stage, actual_stores=len(self.stores), expected_stores=len(self.events),
            stores=self.stores, actual_stores_sha256=hashlib.sha256(stores).hexdigest(),
            expected_stores_sha256=hashlib.sha256(expected).hexdigest(), ordered_lock_writes=self.locks,
            original_entries=self.entries, native_returns=self.returns, protected_memory=memory,
            entry_saved_registers=self.saved_before, entry_interrupt_csrs=self.interrupt_before,
            protected_bytes=sum(len(data) for data in self.memory.values()), exact_owner_bytes=4372,
            exact_setup_bytes=412, code_private_bytes=0x200000, guest_writes_by_observer=False,
            abi_observed_before_context_restore=True, validation_is_separate=True,
            limits=['Literal original2/7 sites/effects and pre-command memory,not the guarded owner recipe.',
                    'Only the current core stack may change outside the exactly projected owner,private fields and SETUP.',
                    'Saving is not validation; actual caller and diagnostic restored prefixes remain distinct.',
                    'Added lock18,MMIO,DMA backing and scheduling are modeled; no physical/drain or worker authority.'])
        (directory / 'trace.json').write_text(json.dumps(result, indent=2) + '\n')
        return result
