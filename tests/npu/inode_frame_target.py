"""Execute the packaged AArch64 sender with explicit kernel dependency models."""
import hashlib
import io
import struct

from elftools.elf.elffile import ELFFile
from elftools.elf.enums import ENUM_RELOC_TYPE_AARCH64
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as a

CODE, NPU, INPUT, BUFFER, STACK = 0x10000000, 0x20000000, 0x20010000, 0x20020000, 0x20030000
END, STUB = CODE + 0x20000, CODE + 0x20100
ARGS = [getattr(a, 'UC_ARM64_REG_X' + str(i)) for i in range(6)]


class Sender:
    def __init__(self, module):
        self.raw = module.read_bytes()
        elf = ELFFile(io.BytesIO(self.raw))
        assert elf['e_machine'] == 'EM_AARCH64' and elf.little_endian
        symbols = elf.get_section_by_name('.symtab')
        selected = [s for s in symbols.iter_symbols() if s.name == 'airoha_npu_wlan_msg_send']
        assert len(selected) == 1
        symbol = selected[0]
        section_index = symbol['st_shndx']
        section = elf.get_section(section_index)
        self.entry, self.size = symbol['st_value'], symbol['st_size']
        self.text = bytearray(section.data())
        assert len(self.text) < 0x20000 and self.size and self.size % 4 == 0
        self.imports = {}
        relocation_offsets = set()
        for relocations in elf.iter_sections():
            if relocations['sh_type'] != 'SHT_RELA' or relocations['sh_info'] != section_index:
                continue
            table = elf.get_section(relocations['sh_link'])
            for reloc in relocations.iter_relocations():
                offset = reloc['r_offset']
                if not self.entry <= offset < self.entry + self.size:
                    continue
                assert reloc['r_info_type'] == ENUM_RELOC_TYPE_AARCH64['R_AARCH64_CALL26']
                name = table.get_symbol(reloc['r_info_sym']).name
                assert name in ('__kmalloc_noprof', 'memcpy', 'kfree', '__fortify_panic'), name
                address = STUB + 16 * len(self.imports)
                self.imports[address] = name
                distance = address - (CODE + offset)
                assert distance % 4 == 0 and abs(distance) < 1 << 27
                struct.pack_into('<I', self.text, offset, 0x94000000 | ((distance >> 2) & 0x3ffffff))
                relocation_offsets.add(offset)
        assert set(self.imports.values()) == {'__kmalloc_noprof', 'memcpy', 'kfree', '__fortify_panic'}
        self.transport = []
        loads = []
        for offset in range(self.entry, self.entry + self.size, 4):
            word = struct.unpack_from('<I', self.text, offset)[0]
            if word & 0xffc003ff == 0xb9400000:
                loads.append((offset, ((word >> 10) & 0xfff) * 4))
            if word >> 26 == 0b100101 and offset not in relocation_offsets:
                displacement = word & 0x3ffffff
                if displacement & 1 << 25:
                    displacement -= 1 << 26
                self.transport.append(CODE + offset + displacement * 4)
        assert len(loads) == len(self.transport) == 1
        self.profile_offset = loads[0][1]
        assert self.profile_offset < 4096
        self.cpu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.cpu.mem_map(CODE, 0x30000)
        self.cpu.mem_write(CODE, bytes(self.text))
        for base in (NPU, INPUT, BUFFER, STACK):
            self.cpu.mem_map(base, 0x10000)
        self.cpu.hook_add(UC_HOOK_CODE, self.hook)
        self.fresh = self.cpu.context_save()

    def hook(self, cpu, pc, size, _):
        values = [cpu.reg_read(reg) for reg in ARGS]
        if pc in self.imports:
            name = self.imports[pc]
            if name == '__kmalloc_noprof':
                assert 8 <= values[0] <= 256 and values[1] & 0x100
                self.allocations += 1
                cpu.mem_write(BUFFER, bytes(values[0]))
                self.capacity = values[0]
                result = 0 if self.deny_allocation else BUFFER
            elif name == 'memcpy':
                assert values[0] == BUFFER + 8 and values[1] == INPUT
                assert values[2] <= self.input_length and 8 + values[2] <= self.capacity
                cpu.mem_write(values[0], bytes(cpu.mem_read(values[1], values[2])))
                result = values[0]
            elif name == 'kfree':
                assert values[0] == BUFFER
                self.frees += 1
                result = 0
            else:
                raise AssertionError('unexpected-target-fortify-panic')
        elif pc in self.transport:
            assert values[0] == NPU and values[1] == 0 and values[2] == values[4] == BUFFER
            assert values[3] == values[5] and values[3] <= self.capacity
            self.sends += 1
            self.packet = bytes(cpu.mem_read(BUFFER, values[3]))
            result = self.transport_error & 0xffffffff
        else:
            return
        cpu.reg_write(a.UC_ARM64_REG_X0, result)
        cpu.reg_write(a.UC_ARM64_REG_PC, cpu.reg_read(a.UC_ARM64_REG_X30))

    def call(self, profile, api, selector, payload, *, declared=None, null=False,
             deny_allocation=False, transport_error=0):
        self.cpu.context_restore(self.fresh)
        self.cpu.mem_write(NPU, bytes(4096))
        self.cpu.mem_write(NPU + self.profile_offset, struct.pack('<I', (0, 0xe000, 0x10000)[profile]))
        self.cpu.mem_write(INPUT, payload or b'\xa5')
        self.cpu.mem_write(BUFFER, b'\xa5' * 256)
        self.allocations = self.frees = self.sends = self.capacity = 0
        self.packet = b''
        self.deny_allocation, self.transport_error = deny_allocation, transport_error
        self.input_length = len(payload)
        length = len(payload) if declared is None else declared
        values = [NPU, selector, api, 0 if null else INPUT, length & 0xffffffff, 7]
        for reg, value in zip(ARGS, values):
            self.cpu.reg_write(reg, value)
        self.cpu.reg_write(a.UC_ARM64_REG_SP, STACK + 0x10000)
        self.cpu.reg_write(a.UC_ARM64_REG_X30, END)
        self.cpu.emu_start(CODE + self.entry, END, count=2000, timeout=1000000)
        assert self.cpu.reg_read(a.UC_ARM64_REG_PC) == END
        result = self.cpu.reg_read(a.UC_ARM64_REG_X0) & 0xffffffff
        if result & 1 << 31:
            result -= 1 << 32
        return result


def verify(module, frames):
    sender = Sender(module)
    for row in frames:
        payload = bytes((0x71 + i) & 255 for i in range(row['input_bytes']))
        assert sender.call(row['profile'], row['api'], row['selector'], payload) == 0
        assert sender.packet == bytes.fromhex(row['hex'])
        assert sender.allocations == sender.frees == sender.sends == 1
    controls = 0
    for profile in range(3):
        for length in (-1, -2147483648, 249, 2147483647):
            assert sender.call(profile, 24, 2, b'abcd', declared=length) == -22
            assert sender.allocations == sender.frees == sender.sends == 0
            controls += 1
        assert sender.call(profile, 24, 2, b'abcd', null=True) == -22
        assert sender.allocations == sender.frees == sender.sends == 0
        controls += 1
        assert sender.call(profile, 24, 2, b'', null=True) == 0
        assert len(sender.packet) == (24 if profile == 1 else 8)
        controls += 1
        assert sender.call(profile, 24, 2, b'abcd', deny_allocation=True) == -12
        assert sender.allocations == 1 and sender.frees == sender.sends == 0
        controls += 1
        for error in (-110, -16, -5):
            assert sender.call(profile, 24, 2, b'abcd', transport_error=error) == error
            assert sender.allocations == sender.frees == sender.sends == 1
            controls += 1
    return dict(passed=True, cases=len(frames), controls=controls,
                module_sha256=hashlib.sha256(sender.raw).hexdigest(),
                function_offset=hex(sender.entry), function_bytes=sender.size,
                observed_profile_load_offset=sender.profile_offset,
                modeled_imports=sorted(sender.imports.values()),
                modeled_internal_transport=[hex(x - CODE) for x in sender.transport],
                scope='Actual packaged AArch64 instructions; kernel allocation, memcpy, mailbox transport and free modeled.')
