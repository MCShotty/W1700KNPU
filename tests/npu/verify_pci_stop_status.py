#!/usr/bin/env python3
"""Check radio stop and cleanup control flow in pinned AArch64 modules."""
import argparse
import errno
import hashlib
import io
import json
from pathlib import Path
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from npu_world_sources import digest, linked_module_sources

STOCK = {
    'mtk_hwifi.ko': '6d82ba02d96d638da9e80592a63e31c09d2f8603620066b604c1702d1171c8f7',
    'mtk_pci.ko': 'c71b2073eeb2498c05c5e42bb5ceaf3df664cff42bf0b0740eb6152458e0857b',
    'mt7990.ko': '502cd4b1ddab60b5a23a0d4d904f49ddae795dfa09154d70b63f933add323f81',
}
ABS64, ADRP, ADD, CALL = 257, 275, 277, 283


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


class Module:
    def __init__(self, path, pin):
        self.name = path.name
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == pin, f'{self.name}: module SHA256 mismatch')
        self.elf = ELFFile(io.BytesIO(raw))
        require(self.elf.elfclass == 64 and self.elf.little_endian and
                self.elf['e_type'] == 'ET_REL' and self.elf['e_machine'] == 'EM_AARCH64',
                f'{self.name}: expected AArch64 relocatable module')
        self.dec = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        self.sections, self.relocs = {}, {}

    def data(self, section):
        if section not in self.sections:
            self.sections[section] = self.elf.get_section_by_name(section).data()
        return self.sections[section]

    def relocations(self, section):
        if section not in self.relocs:
            rel = self.elf.get_section_by_name('.rela' + section)
            require(rel is not None and rel['sh_type'] == 'SHT_RELA' and
                    rel['sh_info'] == self.elf.get_section_index(section),
                    f'{self.name}: wrong relocation section for {section}')
            symbols = self.elf.get_section(rel['sh_link'])
            require(symbols['sh_type'] == 'SHT_SYMTAB', f'{self.name}: wrong symbol table')
            by_offset = {}
            for entry in rel.iter_relocations():
                offset = entry['r_offset']
                require(offset not in by_offset, f'{self.name}:{section}+{offset:#x}: duplicate relocation')
                sym = symbols.get_symbol(entry['r_info_sym'])
                index = sym['st_shndx']
                target = (self.elf.get_section(index).name if isinstance(index, int) else sym.name,
                          sym['st_value'] + entry['r_addend'])
                by_offset[offset] = (entry['r_info_type'], *target)
            self.relocs[section] = by_offset
        return self.relocs[section]

    def bind(self, section, offset, kind, target, value=0):
        require(self.relocations(section).get(offset) == (kind, target, value),
                f'{self.name}:{section}+{offset:#x}: wrong target, expected {target}+{value:#x}')

    def calls(self, *calls):
        for offset, name, value in calls:
            self.ops(f'{offset:x} bl #{offset:#x}')
            self.bind('.text', offset, CALL, name, value)

    def null(self, offset):
        require(self.data('.data')[offset:offset + 8] == bytes(8) and
                all(not offset <= p < offset + 8 for p in self.relocations('.data')),
                f'{self.name}:.data+{offset:#x}: not a static null slot')

    def ops(self, spec, section='.text'):
        code = self.data(section)
        for anchor in spec.strip().splitlines():
            address, want = anchor.strip().split(' ', 1)
            off = int(address, 16)
            i = next(self.dec.disasm(code[off:off + 4], off), None)
            actual = f'{i.mnemonic} {i.op_str}'.rstrip() if i else '<invalid>'
            require(actual == want, f'{self.name}:{section}+{off:#x}: expected {want}, got {actual}')


def verify_binding(hw, pci, radio):
    for mod, page, add, call, target in ((pci, 4, 8, 0x10, 'mtk_bus_driver_register'),
                                         (radio, 0, 4, 0xfc, 'mtk_chip_register')):
        mod.ops(f'{page:x} adrp x0, #0\n{add:x} add x0, x0, #0\n{call:x} bl #{call:#x}', '.init.text')
        for offset, kind, name in ((page, ADRP, '.data'), (add, ADD, '.data'), (call, CALL, target)):
            mod.bind('.init.text', offset, kind, name)
    require(pci.data('.data')[0] == radio.data('.data')[0x2c] == 1, 'PCI registration ID mismatch')
    pci.bind('.data', 0x10, ABS64, '.text', 0x20)
    pci.null(0x28)
    for slot, target in ((0x108, 0x7e0), (0x128, 0x1c14), (0x1f0, 0x580), (0x1f8, 0x5a0)):
        pci.bind('.data', slot, ABS64, '.text', target)
    pci.null(0x138)
    radio.bind('.data', 0x10, ABS64, '.data', 0x70)
    radio.bind('.data', 0x80, ABS64, '.text', 0xcc4)
    pci.ops("""
        3c adrp x3, #0
        40 add x3, x3, #0
        58 stp x2, x3, [x0, #0x18]
        cc ldr x22, [x0, #0x60]
        d0 ldur x1, [x22, #-0x18]
        f4 mov w1, #1
        1c0 mov x1, x22
        1cc adrp x3, #0
        1d4 add x3, x3, #0
        1d8 adrp x2, #0
        1dc add x2, x2, #0
        29c ldr x0, [x0]
        2a0 str x0, [x22, #0xb78]
        580 ldr x0, [x0, #0xb78]
        584 add x0, x0, w1, uxtw
        588 ldr w0, [x0]
        5a4 ldr x0, [x0, #0xb78]
        5a8 add x1, x0, w1, uxtw
        5ac str w2, [x1]
        7ec ldr x0, [x1, #0x10]
        800 str x1, [x2, #0xbc0]
        1c14 ldr x1, [x0, #0xbc0]
        1c18 ldr x1, [x1, #0x10]
        1c1c cbz x1, #0x1c34
        1c28 blr x1
        1c2c ldp x29, x30, [sp], #0x10
        1c30 ret
    """)
    for page, add, section, offset in ((0x3c, 0x40, '.text', 0xb0),
                                        (0x1cc, 0x1d4, '.data', 0xb8),
                                        (0x1d8, 0x1dc, '.data', 0x1f0)):
        pci.bind('.text', page, ADRP, section, offset)
        pci.bind('.text', add, ADD, section, offset)
    pci.calls((0x70, '__pci_register_driver', 0), (0xf8, 'pcim_iomap_regions', 0),
              (0x1f0, 'mtk_bus_alloc_trans', 0), (0x204, 'pcim_iomap_table', 0))
    hw.ops("""
        7b0 mov x19, x0
        7d8 mov x2, x19
        b0c sub x22, x1, #0x40
        b14 mov x20, x3
        b28 mov x25, x2
        b2c ldr x21, [x22, #0x28]
        b84 stp x25, x20, [x19, #0x60]
        ba8 ldr x0, [x22, #0x38]
        bac cbz x0, #0xbd0
        bb0 ldr x1, [x22, #0x30]
        bb4 ldr x3, [x1, #0x28]
        bb8 cbz x3, #0xbd0
        bc8 blr x3
        bcc ldr x20, [x19, #0x68]
        bd0 ldr x2, [x20, #0x50]
        bd4 ldr x1, [x21, #0x10]
        be0 blr x2
        15f8 ldr x21, [x0, #0x28]
        15fc ldrb w23, [x21, #0x2c]
        1610 ldrb w1, [x19]
        1614 cmp w1, w23
        1618 b.eq #0x163c
        167c stp x19, x0, [x20, #0x30]
        1680 add x1, x20, #0x40
        1684 mov x0, x21
        1688 ldr x2, [x19, #0x10]
        168c blr x2
        1b1c str x20, [x19, #0x28]
    """)
    hw.calls((0x7e8, '.text', 0x21c0), (0x1b7c, '.text', 0x15e0))


def verify_radio_stop(radio):
    radio.ops("""
        cdc ldr x1, [x0, #0x60]
        ce0 ldr x3, [x1]
        ce4 cbz x3, #0xd00
        ce8 mov w1, #0x4208
        cec movk w1, #0xd, lsl #16
        cf0 blr x3
        cf8 mov w2, #-6
        cfc and w2, w0, w2
        d00 ldr x3, [x1, #8]
        d04 cbz x3, #0xe38
        d08 mov w1, #0x4208
        d10 movk w1, #0xd, lsl #16
        d14 blr x3
        d20 ldr x3, [x1]
        d28 mov w1, #0x413c
        d30 movk w1, #0xd, lsl #16
        d34 blr x3
        d3c orr w2, w0, #0x1f
        d40 ldr x3, [x1, #8]
        d48 mov w1, #0x413c
        d50 movk w1, #0xd, lsl #16
        d54 blr x3
        d58 ldr x0, [x20, #0x60]
        d5c ldr x2, [x0]
        d60 mov w22, #0x7044
        d64 mov x21, #0x8958
        d68 mov w19, #0x65
        d6c movk w22, #0xd, lsl #16
        d70 movk x21, #0x41, lsl #16
        d74 cbz x2, #0xdac
        d78 mov w1, w22
        d7c mov x0, x20
        d80 blr x2
        d84 mov w1, w0
        d88 mov x0, x21
        d8c tbz w1, #0, #0xdac
        d94 sub w1, w19, #1
        d98 ands w19, w1, #0xff
        d9c b.eq #0xe4c
        da0 ldr x0, [x20, #0x60]
        da4 ldr x2, [x0]
        da8 cbnz x2, #0xd78
        dac mov w19, #0
        db0 add x0, x20, #0xbac
        db4 bl #0x850
        db8 ldr x1, [x20, #0x60]
        dc0 ldr x3, [x1, #8]
        dc4 cbz x3, #0xdf4
        dc8 ldr w1, [x20, #0xdf0]
        dd0 mov w2, #0
        dd4 blr x3
        dd8 ldr x0, [x20, #0x60]
        ddc ldr w1, [x20, #0xb48]
        de0 ldr x3, [x0, #8]
        de4 cbz x3, #0xdf4
        dec mov w2, #0
        df0 blr x3
        e08 mov x0, #1
        e0c add x3, x20, #0xbd0
        e18 bic x1, x1, x0
        e24 mov w0, w19
        e34 ret
        e38 ldr x3, [x1]
        e3c cbnz x3, #0xd28
        e40 b #0xdac
        e44 ldr x2, [x1]
        e48 b #0xd60
        e5c add x2, x2, #0x3a0
        e64 mov w19, #1
        e6c b #0xdb0
    """)
    for page, add, section, offset in ((0xe50, 0xe54, '.rodata', 0),
                                        (0xe58, 0xe60, '.rodata.str1.8', 0x288)):
        radio.bind('.text', page, ADRP, section, offset)
        radio.bind('.text', add, ADD, section, offset)
    radio.calls((0xd90, '__const_udelay', 0), (0xe68, '_dev_err', 0))
    require(radio.data('.rodata')[0x3a0:].startswith(b'mt7990_pdma_disable\x00') and
            radio.data('.rodata.str1.8')[0x288:].startswith(b'%s(): Polling to idle failed\n\x00'),
            'different PDMA timeout diagnostic')


def verify_callers(hw):
    hw.ops("""
        13d4 mov x20, #4
        13d8 ldr x0, [x19, #0x30]
        13dc tbz w0, #2, #0x140c
        13e8 ldxr x0, [x2]
        13ec bic x0, x0, x20
        13f0 stxr w1, x0, [x2]
        13f4 cbnz w1, #0x13e8
        13f8 ldr x1, [x19, #0x68]
        13fc mov x0, x19
        1400 ldr x1, [x1, #0x70]
        1404 cbz x1, #0x140c
        1408 blr x1
        140c ldr x19, [x19, #0x48]
        1410 cbnz x19, #0x13d8
        1414 ldp x19, x20, [sp, #0x10]
        1418 ldp x29, x30, [sp], #0x20
        141c ret
        14b0 ldr x1, [x19, #0x68]
        14b8 ldr x1, [x1, #0x80]
        14bc cbz x1, #0x14e4
        14c0 blr x1
        14c4 cbz w0, #0x14a8
        14e4 mov w0, #-0x5f
        c64c ldr x0, [x19, #0x690]
        c654 ldr x0, [x19, #0x690]
        c65c mov x0, x19
        c664 mov w0, #0
        cf44 mov w19, #0
        cf48 ldr x0, [x20, #0x690]
        cf50 mov x0, x20
        cf58 mov w0, w19
        d074 ldp x29, x30, [sp], #0x10
        d078 ret
    """)
    hw.calls((0xc650, '.text', 0x13c0), (0xc658, '.text', 0x12a0), (0xc660, '.text', 0xbec4),
             (0xcf40, '.text', 0x13c0), (0xcf4c, '.text', 0x12a0), (0xcf54, '.text', 0xbec4),
             (0xd070, '.text', 0x1490))


def verify_current(current):
    current.ops("""
        4784 mov w1, #0x7044
        4788 mov w4, #0x3e8
        478c movk w1, #0xd, lsl #16
        4790 mov w3, #0
        4794 mov w2, #1
        4798 mov x0, x19
        47a0 ldr x4, [x19, #0x850]
        47a4 mov w3, #0x4000
        47a8 mov w1, #0x42b0
        47ac movk w3, #4, lsl #16
        47b0 mov w2, #0
        47b4 movk w1, #0xd, lsl #16
        47b8 ldr x4, [x4, #0x10]
        47bc mov x0, x19
        47c0 blr x4
        5b0c cbnz w0, #0x5dc8
        5b14 mov w1, #0x4208
        5b20 movk w1, #0xd, lsl #16
        5b2c mov w2, #5
        5b34 blr x4
        5b3c cbz x0, #0x5b60
        5b44 mov w1, #0x8208
        5b4c movk w1, #0xd, lsl #16
        5b54 mov w2, #5
        5b5c blr x4
        5b68 mov x1, #0x7d0
        5b6c mov x0, #0x3e8
        5b74 nop
        5b78 nop
        5b7c nop
        5b80 ldr x3, [x19, #0x3e78]
        5b84 mov x0, x19
        5b88 ldr x1, [x19, x20]
        5b8c mov w2, #1
        5b90 ldr x3, [x3, #0x30]
        5b94 blr x3
        5e14 bl #0x4060
        5e18 mov x0, x19
    """)
    current.calls((0x479c, '__mt76_poll', 0), (0x5b04, 'mt76_npu_disable_irqs', 0),
                  (0x5b70, 'usleep_range_state', 0), (0x5e1c, 'mt76_dma_cleanup', 0))


def verify(stock_dir, producer_path, producer_pin):
    require(__debug__ and digest(producer_path) == producer_pin, 'unverified linked producer')
    producer = linked_module_sources(ROOT, producer_path)
    require(producer['receipt_sha256'] == producer_pin, 'producer changed during verification')
    paths = [(name, pin) for name, pin in producer['artifacts'].items() if Path(name).name == 'mt7996e.ko']
    require(len(paths) == 1, 'expected one linked radio module')
    name, pin = paths[0]
    hw, pci, radio = (Module(stock_dir / name, sha) for name, sha in STOCK.items())
    current = Module(ROOT / name, pin)

    verify_binding(hw, pci, radio)
    verify_radio_stop(radio)
    verify_callers(hw)
    verify_current(current)
    return {
        'schema': 1,
        'scope': 'pinned host instructions and static PCI registration; no live bus or DMA observation',
        'stock_sha256': STOCK,
        'stock': {
            'pci_traffic_stop': {'slot': '.data+0x138', 'has_relocation': False, 'return': -errno.EOPNOTSUPP},
            'pdma_stop': {
                'entry': '.text+0xcc4', 'pci_bar_idle_register': '0xd7044', 'busy_mask': 1,
                'maximum_busy_samples': 101, 'idle_return': 0, 'missing_accessor_can_return': 0,
                'timeout_return': 1, 'timeout_still_runs_interrupt_shutdown': True,
            },
            'bus_started_bit_cleared_before_dispatch': True,
            'bus_stop_callback_status_checked': False,
            'teardown_calls': {
                'device_stop': ['0xc650', '0xc658', '0xc660'],
                'ge_dma_token_disable': ['0xcf40', '0xcf4c', '0xcf54'],
                'order': ['mtk_bus_stop_device', 'mtk_bus_exit_device', 'mtk_tk_exit'],
            },
        },
        'current': {
            'producer': producer['receipt'], 'producer_sha256': producer_pin, 'module_sha256': pin,
            'enable_idle_poll_call': '.text+0x479c',
            'reset_sleep_then_tx_cleanup_calls': ['.text+0x5b70', '.text+0x5b94'],
            'cleanup_disable_then_release_calls': ['.text+0x5e14', '.text+0x5e1c'],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-inputs', type=Path, default=ROOT / '.local/npu-reset/inputs')
    parser.add_argument('--producer', required=True, type=Path)
    parser.add_argument('--producer-sha256', required=True)
    parser.add_argument('--check', type=Path, help='compare with a retained receipt instead of printing')
    args = parser.parse_args()
    try:
        result = verify(args.stock_inputs, args.producer, args.producer_sha256)
        if args.check:
            require(result == json.loads(args.check.read_bytes()), 'retained receipt differs')
        else:
            print(json.dumps(result, indent=2, sort_keys=True))
    except (AssertionError, OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
