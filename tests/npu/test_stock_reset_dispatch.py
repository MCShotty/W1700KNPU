#!/usr/bin/env python3
"""Execute stock AArch64 dispatch code with synthetic objects/callbacks, not DMA."""
import hashlib
import io
import json
from pathlib import Path
import struct

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2
from unicorn.arm64_const import UC_ARM64_REG_X30, UC_ARM64_REG_SP, UC_ARM64_REG_PC
import unicorn

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / '.local/npu-reset/inputs'
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-reset'
IDENTITIES = {
    'mt_wifi.ko': ('40c8f974ad7317776f602c069c009d1f0d5d939d622ccdee275423fad1e35cb0', 0x10000000),
    'connac_if.ko': ('52f5c19cacf0febddc73a72247250a7c067039c80b8bbd744f5283a5492e0d28', 0x11000000),
    'mtk_hwifi.ko': ('6d82ba02d96d638da9e80592a63e31c09d2f8603620066b604c1702d1171c8f7', 0x12000000),
}
ADAPTER, COOKIE, WRAPPER = 0x40000000, 0x41000000, 0x41002000
CTRL, PHY, HDEV, BUS = 0x41004000, 0x41006000, 0x41008000, 0x4100a000
GE_OPS, DMA_OPS, CONNAC_OPS = 0x4100c000, 0x4100e000, 0x41010000
STACK, END, CALLBACK = 0x42010000, 0x43000000, 0x43001000


class Module:
    def __init__(self, name):
        self.name = name
        self.sha, self.base = IDENTITIES[name]
        data = (INPUT / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == self.sha, name
        self.elf = ELFFile(io.BytesIO(data))
        self.text = self.elf.get_section_by_name('.text').data()
        self.symbols = {symbol.name: symbol for symbol in self.elf.get_section_by_name('.symtab').iter_symbols()}

    def address(self, name):
        return self.base + self.symbols[name]['st_value']

    def relocation(self, section, offset):
        relocations = self.elf.get_section_by_name('.rela' + section)
        table = self.elf.get_section(relocations['sh_link'])
        matches = [entry for entry in relocations.iter_relocations() if entry['r_offset'] == offset]
        assert len(matches) == 1, (self.name, section, hex(offset))
        entry = matches[0]
        return entry, table.get_symbol(entry['r_info_sym'])


MODULES = {name: Module(name) for name in IDENTITIES}
WIFI, CONNAC, HWIFI = (MODULES[name] for name in IDENTITIES)


def verify_table(module, section, offset, target):
    reloc, symbol = module.relocation(section, offset)
    assert reloc['r_info_type'] == 257  # R_AARCH64_ABS64
    assert symbol['st_value'] + reloc['r_addend'] == target
    assert module.elf.get_section(symbol['st_shndx']).name == '.text'


def signed32(value):
    return struct.unpack('<i', struct.pack('<I', value & 0xffffffff))[0]


def emulate(action, callback_status=0, missing=None, mutant=False):
    assert action in (8, 9)
    machine = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    for module in MODULES.values():
        machine.mem_map(module.base, (len(module.text) + 0xfff) & ~0xfff)
        machine.mem_write(module.base, module.text)
    machine.mem_map(ADAPTER, 0x1000)
    machine.mem_map((ADAPTER + 0x13096c0) & ~0xfff, 0x1000)
    machine.mem_map(COOKIE, 0x12000)
    machine.mem_map(STACK - 0x10000, 0x20000)
    machine.mem_map(END, 0x2000)
    machine.mem_write(CALLBACK, struct.pack('<I', 0xd65f03c0))  # Synthetic callback's RET.

    def pointer(address, value):
        machine.mem_write(address, struct.pack('<Q', value))

    entry = WIFI.address('asic_ser_handler')
    arch = WIFI.address('hc_get_arch_ops')
    bridge = WIFI.address('hwifi_ser_handler')
    dispatch = CONNAC.base + 0xc80
    wrapper_name = 'mtk_ge_stop_npu' if action == 8 else 'mtk_ge_start_npu'
    wrapper = HWIFI.address(wrapper_name)
    pointer(ADAPTER + 0x13096c0, CTRL)
    pointer(CTRL + 0x13a8 + 0x388, bridge)
    pointer(ADAPTER + 8, COOKIE)
    pointer(COOKIE + 0x80, WRAPPER)
    pointer(WRAPPER, CONNAC_OPS)
    pointer(WRAPPER + 0x20 + 0x48, PHY)
    pointer(CONNAC_OPS + 0x90, dispatch)
    pointer(PHY + 0xb0, HDEV)
    pointer(HDEV + 0x688, GE_OPS)
    pointer(HDEV + 0x690, BUS)
    pointer(BUS + 0x68, DMA_OPS)
    pointer(GE_OPS + (0xf8 if action == 8 else 0x100), 0 if missing == 'ge' else wrapper)
    pointer(DMA_OPS + (0x128 if action == 8 else 0x130), 0 if missing == 'pci' else CALLBACK)

    # Apply the one static CALL26 relocation reached on these paths; other code is untouched.
    call_offset = WIFI.symbols['asic_ser_handler']['st_value'] + 0x2c
    reloc, symbol = WIFI.relocation('.text', call_offset)
    assert reloc['r_info_type'] == 283 and symbol.name == 'hc_get_arch_ops'
    assert struct.unpack_from('<I', WIFI.text, call_offset)[0] == 0x94000000
    displacement = arch + reloc['r_addend'] - (WIFI.base + call_offset)
    assert displacement % 4 == 0 and -(1 << 27) <= displacement < (1 << 27)
    machine.mem_write(WIFI.base + call_offset, struct.pack('<I', 0x94000000 | ((displacement >> 2) & 0x3ffffff)))
    if mutant:
        # Negative control only: retaining the callback return must invalidate the stock-zero observation.
        assert bytes(machine.mem_read(wrapper + 0x20, 4)) == struct.pack('<I', 0x52800000)
        machine.mem_write(wrapper + 0x20, struct.pack('<I', 0xd503201f))

    watched = {entry: 'asic_ser_handler', arch: 'hc_get_arch_ops', bridge: 'hwifi_ser_handler',
               dispatch: 'connac_if .text+0xc80', wrapper: wrapper_name, CALLBACK: 'synthetic PCI callback'}
    trace = []

    def hook(cpu, address, size, _data):
        if address in watched:
            arguments = [cpu.reg_read(register) for register in (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2)]
            trace.append({'function': watched[address], 'x0_x1_x2': [hex(value) for value in arguments]})
        if address == CALLBACK:
            assert cpu.reg_read(UC_ARM64_REG_X0) == BUS, 'Bus object forwarding mismatch'
            cpu.reg_write(UC_ARM64_REG_X0, callback_status & 0xffffffff)

    machine.hook_add(UC_HOOK_CODE, hook)
    machine.reg_write(UC_ARM64_REG_X0, ADAPTER)
    machine.reg_write(UC_ARM64_REG_X1, action)
    machine.reg_write(UC_ARM64_REG_X2, 0)
    machine.reg_write(UC_ARM64_REG_SP, STACK)
    machine.reg_write(UC_ARM64_REG_X30, END)
    machine.emu_start(entry, END, timeout=1000000, count=2000)
    assert machine.reg_read(UC_ARM64_REG_PC) == END, 'Instruction/time bound reached'
    assert machine.reg_read(UC_ARM64_REG_SP) == STACK, 'Stack not restored'
    expected = ['asic_ser_handler', 'hc_get_arch_ops', 'hwifi_ser_handler', 'connac_if .text+0xc80']
    if missing != 'ge':
        expected.append(wrapper_name)
    if missing is None:
        expected.append('synthetic PCI callback')
    assert [item['function'] for item in trace] == expected
    assert trace[3]['x0_x1_x2'] == [hex(WRAPPER + 0x20), hex(action), '0x0']
    return {'action': action, 'callback_status': callback_status, 'missing': missing,
            'mutant': mutant, 'return': signed32(machine.reg_read(UC_ARM64_REG_X0)), 'trace': trace}


def main():
    verify_table(CONNAC, '.data', 0x90, 0xc80)
    verify_table(HWIFI, '.rodata', 0x700, HWIFI.symbols['mtk_ge_stop_npu']['st_value'])
    verify_table(HWIFI, '.rodata', 0x708, HWIFI.symbols['mtk_ge_start_npu']['st_value'])
    cases = []
    for action in (8, 9):
        for status in (0, 1, -5, -16, -95, -110):
            result = emulate(action, status)
            assert result['return'] == 0, result
            cases.append(result)
        for missing, expected in [('pci', 0), ('ge', -95)]:
            result = emulate(action, -110, missing)
            assert result['return'] == expected, result
            cases.append(result)
    controls = [emulate(action, -110, mutant=True) for action in (8, 9)]
    assert all(result['return'] == -110 for result in controls), 'Negative control did not expose changed semantics'
    report = {'passed': True, 'unicorn': unicorn.__version__, 'normal_cases': len(cases),
              'negative_controls': len(controls), 'inputs': {name: sha for name, (sha, _) in IDENTITIES.items()},
              'scope': 'original stock AArch64 wrapper instructions, one standard CALL26 relocation, synthetic callback tables/objects/results; not hardware, kernel scheduling, firmware stop, or DMA proof',
              'cases': cases, 'controls': controls}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'stock-dispatch-emulation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'normal_cases': len(cases), 'negative_controls': len(controls),
                      'stock_masks_pci_callback_status': True, 'unicorn': unicorn.__version__}))


if __name__ == '__main__':
    main()
