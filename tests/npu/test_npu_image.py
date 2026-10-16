#!/usr/bin/env python3
"""Raw assembly and byte-readback controls against the actual linked components."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import npu_image as image


class ImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((PAIR / 'manifest.json').read_bytes())
        cls.components = {name: ROOT / path for name, path in cls.manifest['symbol_files'].items()}
        cls.code = (ROOT / '.local/npu-quiescence/firmware/en7581_MT7996_npu_rv32.bin').read_bytes()
        cls.data = (ROOT / '.local/npu-quiescence/firmware/en7581_MT7996_npu_data.bin').read_bytes()
        cls.raw_code, cls.raw_data = [(PAIR / name).read_bytes() for name in ('CODE.bin', 'DATA.bin')]

    def arguments(self):
        m = deepcopy(self.manifest)
        return dict(code=self.code, data=self.data, components=self.components.copy(), patches=m['hooks'],
                    edits=m['edits'], initializers=m['initializers'], loader_slots=m['loader_slots'])

    def rejected(self, reason, **changes):
        args = self.arguments() | changes
        with self.assertRaisesRegex(ValueError, '^' + reason + '$'):
            image.assemble(**args)

    def mutated_elf(self, component, mutate, reason, *, assemble=False):
        original = self.components[component]
        binary, payload = image.elf(original), bytearray(original.read_bytes())
        mutate(binary, payload)
        with tempfile.TemporaryDirectory(dir=ROOT / '.local') as directory:
            path = Path(directory) / 'mutant.elf'
            path.write_bytes(payload)
            if assemble:
                self.rejected(reason, components=self.components | {component: path})
            else:
                with self.assertRaisesRegex(ValueError, '^' + reason + '$'):
                    image.elf(path)

    def test_exact_pair_and_nobits(self):
        code, data, manifest = image.assemble(**self.arguments())
        self.assertEqual((code, data), (self.raw_code, self.raw_data))
        image.validate(code, data, manifest)
        bss = [row for row in manifest['sections'] if row['zero_fill']]
        self.assertEqual({row['component']: row['end'] - row['start'] for row in bss},
                         {'base': 412, 'allocator': 4, 'cold-pages': 1172, 'cold-packets': 2120,
                          'cold-tx': 164, 'cold-descriptor': 6264, 'cold-tx-buffer': 213768,
                          'cold-rx-event': 696, 'cold-txdone': 23080, 'cold-rx-pcie': 732,
                          'cold-pcie-tail': 936})
        for row in bss:
            self.assertEqual(code[row['start'] - image.CODE:row['end'] - image.CODE], bytes(row['end'] - row['start']))

    def test_desc10_metadata_branches_enrolled(self):
        hooks = {row['site']: row for row in self.manifest['hooks']}
        symbols = image.symbols(self.components['cold-txdone'])
        for offset in (0xb45e, 0xb46a, 0xb530, 0xb53c):
            site = image.CODE + offset
            name = 'npu_emulation_desc10_' + format(offset, 'x')
            self.assertEqual((hooks[site]['component'], hooks[site]['symbol']), ('cold-txdone', name))
            target = symbols[name + '_store'] - image.CODE
            self.assertEqual(self.raw_code[target:target + 4], self.code[offset:offset + 4])
        remaining = [row for row in self.arguments()['patches']
                     if row['site'] not in (image.CODE + 0xb45e, image.CODE + 0xb46a)]
        self.rejected('incomplete-hook-set', patches=remaining)

    def test_repeat_build(self):
        if COMPARE is None:
            self.skipTest('No second build supplied')
        manifest = json.loads((COMPARE / 'manifest.json').read_bytes())
        code, data = [(COMPARE / name).read_bytes() for name in ('CODE.bin', 'DATA.bin')]
        image.validate(code, data, manifest)
        self.assertEqual((code, data), (self.raw_code, self.raw_data))
        self.assertEqual(manifest['inputs'], self.manifest['inputs'])

    def test_rx_pcie_original_store_and_hooks(self):
        hooks = {row['site']: row for row in self.manifest['hooks']}
        for offset, name in ((0xba88, 'npu_emulation_rx_pcie_ba88'),):
            self.assertEqual((hooks[image.CODE + offset]['component'], hooks[image.CODE + offset]['symbol']),
                             ('cold-rx-pcie', name))
        symbols = image.symbols(self.components['cold-rx-pcie'])
        address = symbols['npu_emulation_rx_pcie_ba88_store'] - image.CODE
        self.assertEqual(self.raw_code[address:address + 4], self.code[0xba88:0xba8c])
        remaining = [row for row in self.arguments()['patches'] if row['site'] != image.CODE + 0xba88]
        self.rejected('incomplete-hook-set', patches=remaining)

    def test_pcie_tail_original_stores_and_predecessor_link(self):
        import pcie_tail_wire_native as tail
        hooks = {row['site']: row for row in self.manifest['hooks']}
        symbols = image.symbols(self.components['cold-pcie-tail'])
        for site, name in tail.SITES.items():
            self.assertEqual((hooks[site]['component'], hooks[site]['symbol']), ('cold-pcie-tail', name))
        predecessor = image.symbols(self.components['cold-rx-pcie'])['npu_emulation_rx_pcie_callback']
        self.assertEqual(symbols['npu_emulation_rx_pcie_callback'], predecessor)
        self.assertNotEqual(predecessor, image.CODE + 0xfdc4)
        decoder = image.Cs(image.CS_ARCH_RISCV, image.CS_MODE_RISCV32 | image.CS_MODE_RISCVC)
        for offset in tail.STORES:
            site = image.CODE + offset
            width = tail.WIDTHS.get(site, 4)
            first = next(decoder.disasm(self.code[offset:offset + width], site))
            target = symbols['npu_emulation_pcie_tail_' + format(offset, 'x') + '_store'] - image.CODE
            self.assertEqual(self.raw_code[target:target + first.size], self.code[offset:offset + first.size])
            self.assertEqual(len(bytes.fromhex(hooks[site]['before'])), width)
        remaining = [row for row in self.arguments()['patches'] if row['site'] != image.CODE + tail.STORES[-1]]
        self.rejected('incomplete-hook-set', patches=remaining)

    def test_original_identity(self):
        self.rejected('wrong-original-pair', code=b'\x00' + self.code[1:])
        self.rejected('wrong-original-pair', data=self.data[:-1])

    def test_exact_sites_not_only_count(self):
        hooks = self.arguments()['patches']
        self.rejected('incomplete-hook-set', patches=hooks[:-1])
        hooks[-1]['site'] = hooks[0]['site']
        self.rejected('incomplete-hook-set', patches=hooks)
        hooks[-1]['site'] = image.CODE + 0x100
        self.rejected('incomplete-hook-set', patches=hooks)

    def test_missing_component(self):
        parts = self.components.copy()
        parts.pop('cold-packets')
        self.rejected('incomplete-components', components=parts)

    def test_hook_preimage_and_width(self):
        hooks = self.arguments()['patches']
        hooks[0]['before'] = '01000100'
        self.rejected('hook-preimage', patches=hooks)
        hooks = self.arguments()['patches']
        getter = next(row for row in hooks if row['site'] == image.CODE + 0x4d80)
        getter['before'] = getter['before'][:8]
        self.rejected('hook-width', patches=hooks)
        with self.assertRaisesRegex(ValueError, 'split-instruction'):
            image.boundary(bytes.fromhex('1300'), image.CODE)

    def test_symbol_target_and_register(self):
        hooks = self.arguments()['patches']
        hooks[0]['target'] += 2
        self.rejected('wrong-hook-symbol', patches=hooks)
        hooks = self.arguments()['patches']
        hooks[0]['rd'] = 1
        self.rejected('hook-link-register', patches=hooks)
        hooks = self.arguments()['patches']
        skip = next(row for row in hooks if row['site'] == image.CODE + 0x52d4)
        skip['target'] += 2
        self.rejected('wrong-native-continuation', patches=hooks)

    def test_hook_encoding_and_jump_range(self):
        hooks = self.arguments()['patches']
        hooks[0]['after'] = '01000100'
        self.rejected('hook-encoding', patches=hooks)
        for target, rd in ((image.CODE + 0x100000, 0), (image.CODE + 1, 0), (image.CODE + 4, 2)):
            with self.assertRaisesRegex(ValueError, 'jal-range'):
                image.jal(image.CODE, target, rd)
        image.boundary(image.jal(image.CODE, image.CODE - 0x100000), image.CODE)

    def test_nonexecuting_target(self):
        hooks = self.arguments()['patches']
        hooks[0].update(component='cold-packets', symbol='npu_emulation_packet_state',
                        target=image.symbols(self.components['cold-packets'])['npu_emulation_packet_state'])
        self.rejected('nonexecuting-target', patches=hooks)

    def test_fixed_data_layout(self):
        self.rejected('wrong-data-edit', edits=[])
        self.rejected('wrong-startup-initializer', initializers=[])
        slots = self.arguments()['loader_slots']
        slots[0]['address'] += 4
        self.rejected('wrong-loader-slots', loader_slots=slots)

    def test_elf_machine_and_link(self):
        self.mutated_elf('base', lambda e, b: struct.pack_into('<H', b, 18, 40), 'wrong-elf-machine')
        self.mutated_elf('base', lambda e, b: struct.pack_into('<H', b, 16, 1), 'unlinked-elf')

    def test_elf_undefined_and_relocations(self):
        def undefined(elf, payload):
            table = elf.get_section_by_name('.symtab')
            index = next(i for i, symbol in enumerate(table.iter_symbols()) if symbol.name == 'npu_barrier_fail')
            struct.pack_into('<H', payload, table['sh_offset'] + index * table['sh_entsize'] + 14, 0)
        self.mutated_elf('base', undefined, 'undefined-symbols')
        def relocation(elf, payload):
            index = next(i for i, section in enumerate(elf.iter_sections()) if section.name == '.comment')
            offset = elf['e_shoff'] + index * elf['e_shentsize']
            struct.pack_into('<I', payload, offset + 4, 9)
            struct.pack_into('<I', payload, offset + 20, 8)
            struct.pack_into('<I', payload, offset + 36, 8)
        self.mutated_elf('base', relocation, 'unresolved-relocations')

    def test_allocated_section_overlap_and_aperture(self):
        def moved(address):
            def mutate(elf, payload):
                index = next(i for i, section in enumerate(elf.iter_sections()) if section.name == '.text')
                struct.pack_into('<I', payload, elf['e_shoff'] + index * elf['e_shentsize'] + 12, address)
            return mutate
        base = next(row['start'] for row in self.manifest['sections'] if row['component'] == 'base' and row['flags'] & 4)
        self.mutated_elf('order', moved(base), 'section-overlap', assemble=True)
        self.mutated_elf('order', moved(image.CODE + image.CODE_LIMIT), 'section-aperture', assemble=True)

    def test_byte_readback_controls(self):
        for name in ('code', 'data'):
            m = deepcopy(self.manifest)
            m[name]['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'image-digest'):
                image.validate(self.raw_code, self.raw_data, m)
        controls = [('code', 0x20000, 'unaccounted-code'), ('data', 0x5000, 'unaccounted-data'),
                    ('data', 0x63a0, 'provisioned-loader-slot')]
        bss = next(row for row in self.manifest['sections'] if row['zero_fill'])
        controls.append(('code', bss['start'] - image.CODE, 'nonzero-bss'))
        for name, offset, reason in controls:
            m = deepcopy(self.manifest)
            value = bytearray(self.raw_code if name == 'code' else self.raw_data)
            value[offset] ^= 1
            m[name]['sha256'] = image.sha(value)
            for row in m['sections']:
                if name == 'code' and row['start'] - image.CODE <= offset < row['end'] - image.CODE:
                    row['sha256'] = image.sha(value[row['start'] - image.CODE:row['end'] - image.CODE])
            code, data = (bytes(value), self.raw_data) if name == 'code' else (self.raw_code, bytes(value))
            with self.assertRaisesRegex(ValueError, '^' + reason + '$'):
                image.validate(code, data, m)

    def test_profile_and_changed_native_prefix(self):
        for name, value, reason in (('profile', 'generic', 'wrong-profile'),
                                    ('loader_provisioned', True, 'unsupported-acceptance-claim')):
            m = deepcopy(self.manifest)
            m[name] = value
            with self.assertRaisesRegex(ValueError, reason):
                image.validate(self.raw_code, self.raw_data, m)
        for offset, reason in ((0, 'original-prefix-readback'), (0x74, 'hook-readback')):
            value = bytearray(self.raw_code)
            value[offset] ^= 1
            m = deepcopy(self.manifest)
            m['code']['sha256'] = image.sha(value)
            with self.assertRaisesRegex(ValueError, reason):
                image.validate(bytes(value), self.raw_data, m)

    def test_loader_descriptor_and_tag(self):
        self.assertEqual(self.raw_code[image.CODE_TAG_OFFSET:image.CODE_TAG_OFFSET + 32], image.CODE_TAG)
        self.assertEqual(self.raw_data[image.DESCRIPTOR_OFFSET:], image.descriptor(self.raw_code, self.raw_data[:image.DESCRIPTOR_OFFSET]))
        for name, offset, reason in (('code', image.CODE_TAG_OFFSET, 'code-tag-readback'),
                                    ('data', image.DESCRIPTOR_OFFSET, 'loader-descriptor-readback'),
                                    ('data', image.DESCRIPTOR_OFFSET + 64, 'loader-descriptor-readback'),
                                    ('data', image.DESCRIPTOR_OFFSET + 96, 'loader-descriptor-readback')):
            m = deepcopy(self.manifest)
            value = bytearray(self.raw_code if name == 'code' else self.raw_data)
            value[offset] ^= 1
            m[name]['sha256'] = image.sha(value)
            code, data = (bytes(value), self.raw_data) if name == 'code' else (self.raw_code, bytes(value))
            with self.assertRaisesRegex(ValueError, reason):
                image.validate(code, data, m)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--compare', type=Path)
    parser.add_argument('--report', type=Path)
    args, remaining = parser.parse_known_args()
    PAIR = args.pair.resolve()
    COMPARE = args.compare.resolve() if args.compare else None
    if args.report:
        assert args.report.resolve().is_relative_to(ROOT / '.local') and not args.report.exists()
    result = unittest.main(argv=[sys.argv[0], *remaining], exit=False).result
    if args.report:
        receipt = dict(passed=result.wasSuccessful(), test_groups=result.testsRun, skipped=len(result.skipped),
                       repeat_build=COMPARE is not None, failures=len(result.failures), errors=len(result.errors),
                       source_inputs={str(path.relative_to(ROOT)): image.sha(path.read_bytes())
                                      for path in (Path(__file__), ROOT / 'tools/npu_image.py')},
                       pairs={str(path.relative_to(ROOT)): {
                           name: image.sha((path / name).read_bytes()) for name in ('CODE.bin', 'DATA.bin', 'manifest.json')}
                           for path in (PAIR, COMPARE) if path is not None})
        args.report.write_text(json.dumps(receipt, indent=2) + '\n')
    sys.exit(0 if result.wasSuccessful() else 1)
