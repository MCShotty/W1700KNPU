#!/usr/bin/env python3
"""Read-only stock ELF inventory; all generated files remain beside this script."""

import bisect
import csv
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path

import elftools
from elftools.dwarf.callframe import FDE
from elftools.elf.descriptions import describe_reloc_type
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from elftools.elf.sections import SymbolTableSection


ROOT = Path('/home/captain/W1700KNPU')
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-quiescence/inventory'
MODULES = ROOT / '.local/legacy-firmware/work/extract/stock-rootfs/lib/modules/5.4.55'
KERNEL = ROOT / 'research/stock/elf/stock-kernel.vmlinux.elf'
RELATED = re.compile(
    r'(?<!i)npu|mbox|mailbox|hostadpt|host_notify|host_(?:send|rcv|recv)|reset|'
    r'recover|(?:^|_)ser(?:_|$)|quiesc|drain|wifi.*(?:stop|start|enable|disable)', re.I
)
RELOC_FIELDS = [
    'file', 'sha256', 'relocation_section', 'relocation_index', 'target_section',
    'offset', 'elf_address', 'file_offset', 'type', 'symbol', 'symbol_index',
    'symbol_undefined', 'symbol_type', 'symbol_section', 'symbol_value', 'addend',
    'resolved_target_functions', 'resolved_target_address', 'owners', 'owner_start',
    'owner_offset', 'owner_extent', 'owner_end', 'owner_fde', 'evidence', 'instruction_word',
]
SYMBOL_FIELDS = [
    'file', 'sha256', 'table', 'index', 'name', 'type', 'bind', 'visibility',
    'section', 'value', 'size', 'undefined', 'related_name',
]


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def hx(value):
    return hex(value) if value is not None else ''


class FunctionIndex:
    def __init__(self, symbols, sections, elf):
        self.groups = defaultdict(dict)
        self.starts = {}
        self.fdes = defaultdict(dict)
        self.fde_starts = {}
        for symbol in symbols:
            section = symbol['st_shndx']
            if symbol['st_info']['type'] != 'STT_FUNC' or not isinstance(section, int):
                continue
            start = symbol['st_value']
            group = self.groups[section].setdefault(start, {'names': set(), 'size': 0})
            group['names'].add(symbol.name)
            group['size'] = max(group['size'], symbol['st_size'])
        for section, groups in self.groups.items():
            starts = self.starts[section] = sorted(groups)
            end = sections[section]['sh_addr'] + sections[section]['sh_size']
            for index, start in enumerate(starts):
                group = groups[start]
                group['names'] = sorted(group['names'])
                group['end'] = start + group['size'] if group['size'] else (
                    starts[index + 1] if index + 1 < len(starts) else end
                )
                group['extent'] = 'symbol_size' if group['size'] else 'inferred_next_symbol'

        # In stripped modules, FDE relocations preserve exact anonymous code ranges.
        eh_frame = elf.get_section_by_name('.eh_frame')
        if eh_frame is not None:
            eh_index = sections.index(eh_frame) if eh_frame in sections else next(
                i for i, section in enumerate(sections) if section.name == '.eh_frame')
            fde_relocs = {}
            for section in sections:
                if isinstance(section, RelocationSection) and section['sh_info'] == eh_index:
                    table = elf.get_section(section['sh_link'])
                    for reloc in section.iter_relocations():
                        fde_relocs[reloc['r_offset']] = (reloc, table.get_symbol(reloc['r_info_sym']))
            dwarf = elf.get_dwarf_info(relocate_dwarf_sections=False)
            for entry in dwarf.EH_CFI_entries():
                if not isinstance(entry, FDE):
                    continue
                assert entry.structs.dwarf_format == 32
                assert entry.cie.augmentation_dict['FDE_encoding'] == 0x1b
                reloc, symbol = fde_relocs[entry.offset + 8]
                assert reloc['r_info_type'] == 261  # R_AARCH64_PREL32, signed 4-byte PC-relative.
                section = symbol['st_shndx']
                assert isinstance(section, int)
                start = symbol['st_value'] + reloc['r_addend']
                size = entry['address_range']
                known = self.groups.get(section, {}).get(start)
                self.fdes[section][start] = dict(
                    names=known['names'] if known else [f'unnamed@{sections[section].name}+{hx(start)}'],
                    start=start, size=size, end=start + size, extent='eh_frame_FDE',
                    fde=hx(entry.offset),
                )
            self.fde_starts = {section: sorted(groups) for section, groups in self.fdes.items()}

    def at(self, section, address):
        starts = self.starts.get(section, [])
        index = bisect.bisect_right(starts, address) - 1
        if index >= 0:
            start = starts[index]
            group = self.groups[section][start]
            if address < group['end']:
                return dict(group, start=start, delta=address - start)
        starts = self.fde_starts.get(section, [])
        index = bisect.bisect_right(starts, address) - 1
        if index >= 0:
            group = self.fdes[section][starts[index]]
            if address < group['end']:
                return dict(group, delta=address - group['start'])
        return None


def main():
    assert OUT.resolve() == OUT and Path(__file__).resolve().parent == OUT
    files = sorted(MODULES.rglob('*.ko')) + [KERNEL]
    manifest = []
    related_rows = []
    with ExitStack() as stack:
        def writer(name, fields, compressed=False):
            if compressed:
                raw = stack.enter_context((OUT / name).open('wb'))
                binary = stack.enter_context(gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0))
                import io
                stream = stack.enter_context(io.TextIOWrapper(binary, encoding='utf-8', newline=''))
            else:
                stream = stack.enter_context((OUT / name).open('w', encoding='utf-8', newline=''))
            result = csv.DictWriter(stream, fields, delimiter='\t', lineterminator='\n')
            result.writeheader()
            return result

        all_symbols = writer('all_symbols.tsv.gz', SYMBOL_FIELDS, True)
        related_symbols = writer('related_symbols.tsv', SYMBOL_FIELDS)
        all_relocs = writer('all_relocations.tsv.gz', RELOC_FIELDS, True)
        imported_refs = writer('all_import_relocations.tsv.gz', RELOC_FIELDS, True)
        imports = writer('all_imports.tsv', SYMBOL_FIELDS + ['relocations', 'direct_calls', 'direct_branches'])

        for path in files:
            relative = str(path.relative_to(ROOT))
            digest = sha256(path)
            with path.open('rb') as stream:
                elf = ELFFile(stream)
                assert elf['e_machine'] == 'EM_AARCH64' and elf.little_endian
                sections = list(elf.iter_sections())
                tables = {i: list(s.iter_symbols()) for i, s in enumerate(sections)
                          if isinstance(s, SymbolTableSection)}
                symbols = [symbol for table in tables.values() for symbol in table]
                functions = FunctionIndex(symbols, sections, elf)
                counts = Counter()
                import_rows = {}
                import_counts = defaultdict(Counter)
                for table_index, table in tables.items():
                    for index, symbol in enumerate(table):
                        section = symbol['st_shndx']
                        undefined = section == 'SHN_UNDEF'
                        row = dict(
                            file=relative, sha256=digest, table=sections[table_index].name,
                            index=index, name=symbol.name, type=symbol['st_info']['type'],
                            bind=symbol['st_info']['bind'], visibility=symbol['st_other']['visibility'],
                            section=sections[section].name if isinstance(section, int) else section,
                            value=hx(symbol['st_value']), size=hx(symbol['st_size']),
                            undefined=int(undefined), related_name=int(bool(RELATED.search(symbol.name))),
                        )
                        all_symbols.writerow(row)
                        counts['symbols'] += 1
                        if row['related_name']:
                            related_symbols.writerow(row)
                            counts['related_symbols'] += 1
                        if undefined and symbol.name:
                            import_rows[table_index, index] = row
                            counts['imports'] += 1

                for reloc_section in sections:
                    if not isinstance(reloc_section, RelocationSection):
                        continue
                    counts['relocation_sections'] += 1
                    table_index = reloc_section['sh_link']
                    table = tables[table_index]
                    target_index = reloc_section['sh_info']
                    target = sections[target_index]
                    data = target.data()
                    executable = bool(target['sh_flags'] & 4)
                    for index, reloc in enumerate(reloc_section.iter_relocations()):
                        counts['relocations'] += 1
                        symbol_index = reloc['r_info_sym']
                        symbol = table[symbol_index]
                        offset = reloc['r_offset']
                        address = offset + target['sh_addr'] if elf['e_type'] == 'ET_REL' else offset
                        section_offset = address - target['sh_addr']
                        symbol_section = symbol['st_shndx']
                        addend = reloc['r_addend'] if reloc_section.is_RELA() else None
                        undefined = symbol_section == 'SHN_UNDEF'
                        owner = functions.at(target_index, address) if executable else None
                        destination = None
                        destination_address = None
                        if isinstance(symbol_section, int) and addend is not None:
                            destination_address = symbol['st_value'] + addend
                            destination = functions.at(symbol_section, destination_address)
                        opcode = None
                        if executable and 0 <= section_offset <= len(data) - 4:
                            opcode = int.from_bytes(data[section_offset:section_offset + 4], 'little')
                        relocation_type = describe_reloc_type(reloc['r_info_type'], elf)
                        evidence = 'executable_reference' if executable else 'data_reference'
                        if relocation_type == 'R_AARCH64_CALL26':
                            evidence = 'direct_call_BL' if opcode is not None and opcode & 0xfc000000 == 0x94000000 else 'CALL26_opcode_mismatch'
                        elif relocation_type == 'R_AARCH64_JUMP26':
                            evidence = 'direct_branch_B' if opcode is not None and opcode & 0xfc000000 == 0x14000000 else 'JUMP26_opcode_mismatch'
                        counts[evidence] += 1
                        row = dict(
                            file=relative, sha256=digest, relocation_section=reloc_section.name,
                            relocation_index=index, target_section=target.name,
                            offset=hx(section_offset), elf_address=hx(address),
                            file_offset=hx(target['sh_offset'] + section_offset), type=relocation_type,
                            symbol=symbol.name, symbol_index=symbol_index, symbol_undefined=int(undefined),
                            symbol_type=symbol['st_info']['type'],
                            symbol_section=sections[symbol_section].name if isinstance(symbol_section, int) else symbol_section,
                            symbol_value=hx(symbol['st_value']), addend=hx(addend),
                            resolved_target_functions='|'.join(destination['names']) if destination else '',
                            resolved_target_address=hx(destination_address),
                            owners='|'.join(owner['names']) if owner else '',
                            owner_start=hx(owner['start']) if owner else '',
                            owner_offset=hx(owner['delta']) if owner else '',
                            owner_extent=owner['extent'] if owner else '',
                            owner_end=hx(owner['end']) if owner else '',
                            owner_fde=owner.get('fde', '') if owner else '',
                            evidence=evidence, instruction_word=hx(opcode),
                        )
                        all_relocs.writerow(row)
                        if undefined and symbol.name:
                            imported_refs.writerow(row)
                            tally = import_counts[table_index, symbol_index]
                            tally['relocations'] += 1
                            tally['direct_calls'] += evidence == 'direct_call_BL'
                            tally['direct_branches'] += evidence == 'direct_branch_B'
                        if RELATED.search(symbol.name) or RELATED.search(row['resolved_target_functions']):
                            related_rows.append(row)
                            counts['related_relocations'] += 1

                for key, row in import_rows.items():
                    imports.writerow(dict(row, **{k: import_counts[key][k] for k in
                                                 ['relocations', 'direct_calls', 'direct_branches']}))
                entry = dict(file=relative, sha256=digest, size=path.stat().st_size,
                             elf_type=elf['e_type'], machine=elf['e_machine'], counts=dict(counts))
                manifest.append(entry)
                if path.name in {'mt_wifi.ko', 'mt_wifi_cmn.ko', 'mtk_pci.ko', 'mtk_hwifi.ko',
                                 'mt7990.ko', 'eth.ko', 'npu.ko', KERNEL.name}:
                    print(json.dumps(entry), flush=True)

        related_writer = writer('related_relocations.tsv', RELOC_FIELDS)
        related_writer.writerows(related_rows)

    summary = dict(
        module_count=len(files) - 1, kernel_count=1, pyelftools_version=elftools.__version__,
        related_name_pattern=RELATED.pattern, files=manifest,
        totals=dict(sum((Counter(item['counts']) for item in manifest), Counter())),
        methodology=[
            'Complete symbol and relocation enumeration for every *.ko beneath the supplied stock module root plus the supplied stock kernel ELF.',
            'ET_REL addresses are section-relative; pair the file and target_section with offset. elf_address in ET_EXEC is a linked virtual address, never a loaded module address.',
            'direct_call_BL requires R_AARCH64_CALL26 and a BL opcode; direct_branch_B requires R_AARCH64_JUMP26 and a B opcode, and may be a tail call or branch, not necessarily a returning call.',
            'Data/executable references, undefined names, export records, and callback pointer relocations do not prove execution or a call.',
            'Containing function uses same-section STT_FUNC ranges. Zero-size symbols use an explicitly labeled next-symbol extent. Aliases at the same start are retained.',
            'Absent STT_FUNC containment falls back to a .eh_frame FDE: relocation-backed initial address plus the parsed address_range. unnamed@ labels are generated locators, not vendor symbol names.',
            'Section-symbol relocations resolve symbol value plus RELA addend to a function range when possible. All original symbol/addend fields remain available.',
            'No indirect call resolution, path feasibility, ordering, drain completion, runtime semantics, or Ghidra analysis is claimed.',
        ],
    )
    (OUT / 'inventory.json').write_text(json.dumps(summary, indent=2) + '\n')
    outputs = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != 'SHA256SUMS')
    (OUT / 'SHA256SUMS').write_text(''.join(f'{sha256(p)}  {p.name}\n' for p in outputs))
    print(json.dumps({'module_count': summary['module_count'], 'totals': summary['totals']}), flush=True)


if __name__ == '__main__':
    main()
