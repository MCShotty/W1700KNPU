"""Independent request-derived tail projection and read-only original-store trace."""
import hashlib
import json
import struct

from unicorn import UC_HOOK_MEM_WRITE, riscv_const as r
from test_cold_txdone_native import SPACES
from pcie_tail_wire_native import MODEL_BAR_PAGES
from test_desc10_native_replay import compare

SITES = (0xba0c, 0xba18, 0xba24, 0xba30, 0xb9ae, 0xb9c0, 0xb9d2, 0xb9ea, 0xba00)
LOCKS = (0x1ec031c8, 0x1ec03248)


class PcieTailTrace:
    def __init__(self, h, request):
        self.h, self.hook, self.stores, self.locks = h, None, [], []
        assert len(request) == 20 and request[:5] == [0x3f, 1, 0x3253434e, 2, 80]
        assert request[5] == 1 and request[12] == 0 and request[14:] == [0] * 6
        assert request[11] in (0x10, 0x12, 0x1f)
        self.stage = (0x10, 0x12, 0x1f).index(request[11])
        self.first, self.last = self.stage * 2, 9 if self.stage == 2 else self.stage * 2 + 2
        self.setup = h.rv.symbols['npu_emulation_cold_setup_state']
        setup = list(struct.unpack('<103I', h.cpu.mem_read(self.setup, 412)))
        assert setup[101:103] == [0, 0], 'tail-before-INODE'
        assert setup[:3] == [0, 0, 131071] and setup[95] == 3 and setup[99] == self.stage
        base, extent, tx2 = setup[12], setup[13], setup[97]
        assert base == 0x20000000 and extent == 0x100000
        assert tx2 - base in (0xd4450, 0xd8450)
        assert request[13] == (base + 0xd4580 if self.stage == 0 else tx2 + 0x110 if self.stage == 1 else 0)
        session = h.rv.symbols['npu_emulation_control_v2_state']
        identity = struct.unpack('<5I', h.cpu.mem_read(session, 20))
        assert list(identity[:4]) == request[9:11] + request[7:9] and identity[4] < request[6]
        assert setup[3] < request[6] and setup[4:8] == list(identity[:4])
        tx = bytes(h.cpu.mem_read(h.tx.symbols['npu_emulation_tx_state'], 80))
        pcie = bytes(h.cpu.mem_read(h.rx_pcie.symbols['npu_emulation_rx_pcie_state'], 168))
        assert struct.unpack_from('<8I', tx) == (0x31585443, 1, 0, 0, 7, 7, 11, 11)
        assert struct.unpack_from('<I', tx, 32)[0] == 2
        assert struct.unpack_from('<2I', tx, 52) == (base + 0xd4420, tx2)
        assert struct.unpack_from('<7I', pcie) == (0x31455052, 1, 0, 0, 1, 1, 1)
        expected_plan = pcie[32:] + tx[36:]
        self.owner = h.pcie_tail.symbols['npu_emulation_pcie_tail_state']
        old_owner = bytes(h.cpu.mem_read(self.owner, 256))
        if not self.stage:
            assert old_owner == bytes(256)
        else:
            assert struct.unpack_from('<10I', old_owner) == (0x31545043, 1, 0, 0, self.stage - 1,
                (1 << self.stage) - 1, (1 << self.stage) - 1, self.first, self.first, (1 << self.first) - 1)
            assert old_owner[40:220] == expected_plan
        all_events = ((0x3e902cf0, 4, base + 0xd4580), (base + 0xd4588, 4, 1535),
            (0x3e903904, 4, tx2 + 0x110), (tx2 + 0x118, 4, 1023),
            (base + 0xd45a8, 4, 255), (base + 0xd45b8, 4, 511),
            (base + 0xd45c8, 4, 1023), (base + 0xa048, 4, 1535), (base + 0xd4598, 4, 511))
        self.events = all_events[self.first:self.last]
        self.memory = {address: bytearray(h.cpu.mem_read(address, length))
                       for address, length in (*SPACES, *((base, 4096) for base in MODEL_BAR_PAGES))}
        self.changes = []
        for address, width, value in (*self.events, (session + 16, 4, request[6])):
            region = next(base for base, data in self.memory.items() if base <= address and address + width <= base + len(data))
            before = struct.unpack_from('<I', self.memory[region], address - region)[0]
            struct.pack_into('<I', self.memory[region], address - region, value)
            self.changes.append(dict(address=hex(address), bytes=width, before=before, expected=value))
        preimages = list(struct.unpack_from('<9I', old_owner, 220))
        for index in range(self.first, self.last):
            preimages[index] = h.get32(all_events[index][0])
        mask = (1 << (self.stage + 1)) - 1
        self.owner_expected = struct.pack('<10I', 0x31545043, 1, 0, 0, self.stage,
            mask, mask, self.last, self.last, (1 << self.last) - 1) + expected_plan + struct.pack('<9I', *preimages)
        setup[3], setup[9:12] = request[6], request[11:14]
        for target, source in ((8, 2), (14, 12), (15, 13), (28, 26), (29, 27), (31, 30),
                               (91, 90), (93, 92), (94, 92), (96, 95), (98, 97), (100, 99)):
            setup[target] = setup[source]
        setup[21:26], setup[61:90] = setup[16:21], setup[32:61]
        setup[99] += 1
        self.setup_expected = struct.pack('<103I', *setup)
        self.prior = {}
        for component, name in ((h.packet, 'npu_emulation_packet_state'),
            (h.tx, 'npu_emulation_tx_state'), (h.rx_pcie, 'npu_emulation_rx_pcie_state'),
            (h.desc10, 'npu_emulation_desc10_state'), (h.rx_event, 'npu_emulation_rx_event_state'),
            (h.txbuf, 'npu_emulation_txbuf_state'), (h.descriptor, 'npu_emulation_descriptor_state'),
            (h.binding, 'npu_emulation_page_state'), (h.inode, 'npu_emulation_inode_state')):
            symbol = component.elf.get_section_by_name('.symtab').get_symbol_by_name(name)[0]
            assert symbol['st_size'] > 0
            address = component.symbols[name]
            self.prior[name] = (address, bytes(h.cpu.mem_read(address, symbol['st_size'])))
        self.sites = {h.pcie_tail.symbols[f'npu_emulation_pcie_tail_{site:x}_store']: 0x84000000 + site for site in SITES}

    def write(self, cpu, access, address, size, value, unused):
        pc = cpu.reg_read(r.UC_RISCV_REG_PC)
        if pc in self.sites:
            index = self.first + len(self.stores)
            state = struct.unpack('<10I', cpu.mem_read(self.owner, 40))
            assert state == (0x31545043, 1, 0, 1, self.stage, (1 << (self.stage + 1)) - 1,
                (1 << self.stage) - 1, index + 1, index, (1 << self.last) - 1), ('tail-reserve-before-store', state)
            assert not cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
            assert self.h.get32(self.h.pcie_tail.symbols['npu_emulation_pcie_tail_running']) == 1
            admission = self.h.rv.symbols['npu_emulation_admission_state']
            assert self.h.get32(self.setup + 4) == self.h.get32(admission + 4) == 1
            assert self.h.get32(self.setup + 396) == self.stage
            self.stores.append((self.sites[pc], address, size, value & ((1 << (size * 8)) - 1)))
        if 0x1ec03180 <= address < 0x1ec03300:
            self.locks.append((address, size, value))

    def __enter__(self):
        assert self.hook is None
        self.hook = self.h.cpu.hook_add(UC_HOOK_MEM_WRITE, self.write)
        return self

    def __exit__(self, *error):
        self.h.cpu.hook_del(self.hook)
        self.hook = None

    def validate(self):
        expected = [(0x84000000 + site, *event) for site, event in zip(SITES[self.first:self.last], self.events)]
        assert self.stores == expected, ('tail-original-stores', self.stores, expected)
        assert self.locks == [(LOCKS[0], 4, 0x40), (LOCKS[1], 4, 0)], ('tail-lock18', self.locks)
        assert all(bytes(self.h.cpu.mem_read(base, len(data))) == data for base, data in self.memory.items()), 'tail-protected-memory'
        assert bytes(self.h.cpu.mem_read(self.owner, 256)) == self.owner_expected, 'tail-owner-publication'
        assert bytes(self.h.cpu.mem_read(self.setup, 412)) == self.setup_expected, 'tail-setup-journal'
        assert all(bytes(self.h.cpu.mem_read(address, len(data))) == data for address, data in self.prior.values()), 'tail-prior-owner-mutation'

    def save(self, directory):
        directory.mkdir()
        memory = directory / 'protected'
        memory.mkdir()
        rows = compare(self.h, self.memory, memory)
        actual = b''.join(struct.pack('<4I', *event) for event in self.stores)
        for name, contents in (('actual-stores.bin', actual), ('owner-expected.bin', self.owner_expected),
                               ('owner-actual.bin', bytes(self.h.cpu.mem_read(self.owner, 256))),
                               ('setup-expected.bin', self.setup_expected),
                               ('setup-actual.bin', bytes(self.h.cpu.mem_read(self.setup, 412)))):
            with (directory / name).open('xb') as stream:
                stream.write(contents)
        result = dict(stage=self.stage, actual_stores=len(self.stores), expected_stores=len(self.events),
            actual_stores_sha256=hashlib.sha256(actual).hexdigest(), stores=self.stores,
            ordered_lock_writes=self.locks, expected_changes=self.changes, protected_memory=rows,
            protected_bytes=sum(len(data) for data in self.memory.values()),
            prior_owner_bytes=sum(len(data) for _, data in self.prior.values()),
            guest_writes_by_observer=False, validation_is_separate=True,
            limits=['Literal site/value/order and pre-command memory projection, not the owner recipe under test.',
                    'The observer never writes guest memory/registers; a saved trace is not a passing verdict.',
                    'BAR/lock storage, backing and scheduling remain modeled; no physical acceptance.'])
        (directory / 'trace.json').write_text(json.dumps(result, indent=2) + '\n')
        return result
