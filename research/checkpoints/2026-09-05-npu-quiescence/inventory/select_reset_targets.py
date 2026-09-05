#!/usr/bin/env python3
"""Reduce the complete ELF inventory to relocation-backed Ghidra selection inputs."""

import csv
import gzip
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from elftools.elf.elffile import ELFFile

from inventory_stock_elf import OUT, RELOC_FIELDS, ROOT, sha256


SEEDS = {
    'mt7990_ser_1_0_v1', 'mt7990_ser_0_0_v1', 'mt7990_ser_0_5_v1',
    'mt7990_ser_10_0_v1', 'mt7990_fe_reset', 'mt7990_fe_wdma_reset',
    'ser_event_enq', 'ser_ack_event', 'ser_sys_reset', 'ser_mngr_init',
    'ser_l1_timeout', 'asic_ser_handler', 'hwifi_ser_handler',
    'mtk_ge_stop_npu', 'mtk_ge_start_npu', 'mtk_ge_hw_reset', 'mtk_bus_rx_ser_event',
    'send_rro_stop_msg_2_NPU', 'send_rro_done_msg_2_NPU', 'mtk_hdev_ops_init',
}
INTERFACE = re.compile(r'(?<!i)npu|hostadpt|hostdapt|mbox|mailbox', re.I)


def read_rows(name):
    opener = gzip.open if name.endswith('.gz') else open
    with opener(OUT / name, 'rt', encoding='utf-8', newline='') as stream:
        yield from csv.DictReader(stream, delimiter='\t')


def write_rows(name, rows, fields):
    with (OUT / name).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fields, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    assert Path(__file__).resolve().parent == OUT == OUT.resolve()
    inventory = json.loads((OUT / 'inventory.json').read_text())
    assert all(sha256(ROOT / item['file']) == item['sha256'] for item in inventory['files'])
    symbols = list(read_rows('all_symbols.tsv.gz'))
    related = list(read_rows('related_relocations.tsv'))
    mailbox = [row for row in related if row['symbol'] == 'host_notify_npuMbox']
    assert len(mailbox) == 37 and all(row['evidence'] == 'direct_call_BL' for row in mailbox)
    assert all(row['owners'] for row in mailbox)
    write_rows('mailbox_calls.tsv', mailbox, RELOC_FIELDS)

    imports = [row for row in read_rows('all_imports.tsv') if INTERFACE.search(row['name'])]
    write_rows('interface_imports.tsv', imports, list(imports[0]))
    definitions = defaultdict(list)
    objects = defaultdict(list)
    for row in symbols:
        if row['undefined'] == '0':
            definitions[row['name']].append(row)
        if row['type'] == 'STT_OBJECT' and row['undefined'] == '0' and int(row['size'], 16):
            objects[row['file'], row['section']].append(row)
    seed_locations = {(row['file'], row['target_section'], row['owner_start']) for row in mailbox}
    module_prefix = '.local/legacy-firmware/work/extract/stock-rootfs/lib/modules/5.4.55/'
    seed_locations.update((module_prefix + 'mtk_pci.ko', '.text.unlikely', start) for start in ['0x0', '0x50'])
    seed_locations.update((module_prefix + 'mt7990.ko', '.text', start) for start in ['0x140', '0xcc4'])
    for row in symbols:
        if row['name'] in SEEDS and row['undefined'] == '0':
            seed_locations.add((row['file'], row['section'], row['value']))

    fields = RELOC_FIELDS + ['selection_relation', 'containing_object']
    focus_rows = []
    export_refs = defaultdict(list)
    total_relocations = 0
    command_names = []
    for row in read_rows('all_relocations.tsv.gz'):
        total_relocations += 1
        if 'ksymtab' in row['target_section']:
            export_refs[row['file'], row['symbol']].append(
                row['target_section'] + '+' + row['offset'] + ':' + row['type'])
        if row['file'].endswith('/mt_wifi.ko') and row['target_section'] == '.data' and row['offset'] in {'0x1270', '0x1280'}:
            command_names.append(row)
        outgoing = (row['file'], row['target_section'], row['owner_start']) in seed_locations
        incoming = (row['file'], row['symbol_section'], row['resolved_target_address']) in seed_locations
        incoming = incoming or bool(set(row['resolved_target_functions'].split('|')) & SEEDS)
        incoming = incoming or row['symbol'] in SEEDS
        if not outgoing and not incoming:
            continue
        row['selection_relation'] = 'both' if outgoing and incoming else 'outgoing' if outgoing else 'incoming'
        offset = int(row['offset'], 16)
        row['containing_object'] = '|'.join(
            f"{obj['name']}+{hex(offset - int(obj['value'], 16))}"
            for obj in objects.get((row['file'], row['target_section']), [])
            if int(obj['value'], 16) <= offset < int(obj['value'], 16) + int(obj['size'], 16)
        )
        focus_rows.append(row)
    assert total_relocations == inventory['totals']['relocations']
    provider_rows = []
    for name in sorted({row['name'] for row in imports}):
        for definition in definitions.get(name, []):
            provider_rows.append(dict(name=name, file=definition['file'], sha256=definition['sha256'],
                                      section=definition['section'], value=definition['value'],
                                      size=definition['size'], type=definition['type'], bind=definition['bind'],
                                      export_relocations='|'.join(export_refs[definition['file'], name]),
                                      evidence='same_named_definition_not_runtime_binding'))
    write_rows('interface_providers.tsv', provider_rows,
               ['name', 'file', 'sha256', 'section', 'value', 'size', 'type', 'bind', 'export_relocations', 'evidence'])
    write_rows('seed_relations.tsv', focus_rows, fields)
    calls = [row for row in focus_rows if row['evidence'] in {'direct_call_BL', 'direct_branch_B'}]
    write_rows('seed_calls.tsv', calls, fields)
    pointers = [row for row in focus_rows if row['selection_relation'] in {'incoming', 'both'}
                and row['evidence'] == 'data_reference' and row['target_section'] != '.eh_frame']
    write_rows('seed_data_references.tsv', pointers, fields)

    target_specs = [
        ('mtk_pci.ko', '.text', '0x6370', 1, 'Named stop-mailbox helper; two direct mailbox CALL26 sites'),
        ('mtk_pci.ko', '.text.unlikely', '0x50', 1, 'PCI stop callback slot +0x128; direct call to named stop helper'),
        ('mtk_pci.ko', '.text', '0x6250', 1, 'Named done-mailbox helper; one direct mailbox CALL26 site'),
        ('mtk_pci.ko', '.text.unlikely', '0x0', 1, 'PCI start callback slot +0x130; direct call to named done helper'),
        ('mtk_hwifi.ko', '.text', '0xce90', 1, 'Named stop wrapper; BLR through slot +0x128, not a direct mailbox call'),
        ('mtk_hwifi.ko', '.text', '0xcec4', 1, 'Named start wrapper; BLR through slot +0x130, not a direct mailbox call'),
        ('mt_wifi.ko', '.text', '0x115440', 1, 'Named L1 coordinator candidate; eight direct asic_ser_handler calls'),
        ('mt_wifi.ko', '.text', '0x397770', 1, 'Anonymous dispatcher; materializes L1 and FE handler addresses, not direct-call proof'),
        ('mt_wifi.ko', '.text', '0x1162e0', 1, 'Named FE reset coordinator candidate; direct asic_ser_handler calls'),
        ('mt_wifi.ko', '.text', '0x34d820', 1, 'Named ASIC SER wrapper; unresolved indirect dispatch'),
        ('mt_wifi.ko', '.text', '0x386870', 1, 'Named hwifi SER wrapper; unresolved indirect dispatch'),
        ('mtk_hwifi.ko', '.text', '0xd020', 2, 'Named hardware-reset wrapper; unresolved indirect dispatch'),
        ('mt7990.ko', '.text', '0x140', 2, 'Anonymous hardware-reset candidate; .data+0x420 callback pointer, no mailbox import'),
        ('mt7990.ko', '.text', '0xcc4', 2, 'Anonymous PDMA-disable candidate; .data+0x80 callback pointer, debug string name hint only'),
        ('mtk_pci.ko', '.text', '0x14c0', 2, 'Anonymous SER event caller; CALL26 at +0x153c and +0x1560'),
        ('mtk_pci.ko', '.text', '0x3924', 2, 'Anonymous SER event caller; CALL26 at +0x3c24'),
        ('mtk_hwifi.ko', '.text', '0x6f4', 2, 'Named exported mtk_bus_rx_ser_event provider'),
        ('mt_wifi.ko', '.text', '0x236c0', 3, 'Private command npu_noba; name comes from command string, not a function symbol'),
        ('mt_wifi.ko', '.text.unlikely', '0x1374', 3, 'Private command force2cpu; name comes from command string, not a function symbol'),
    ]
    targets = []
    for module, section, start, priority, reason in target_specs:
        file = module_prefix + module
        named = [row for row in symbols if row['file'] == file and row['section'] == section
                 and row['value'] == start and row['type'] == 'STT_FUNC']
        owner_rows = [row for row in focus_rows if row['file'] == file and row['target_section'] == section
                      and row['owner_start'] == start]
        if named:
            end = hex(int(start, 16) + max(int(row['size'], 16) for row in named))
            name = '|'.join(sorted(row['name'] for row in named))
            evidence = 'STT_FUNC_symbol_size'
            digest = named[0]['sha256']
        else:
            assert owner_rows and owner_rows[0]['owner_extent'] == 'eh_frame_FDE'
            end = owner_rows[0]['owner_end']
            name = owner_rows[0]['owners']
            evidence = 'eh_frame_FDE:' + owner_rows[0]['owner_fde']
            digest = owner_rows[0]['sha256']
        with (ROOT / file).open('rb') as stream:
            header = ELFFile(stream).get_section_by_name(section).header
        targets.append(dict(priority=priority, file=file, sha256=digest, section=section,
                            start=start, end_exclusive=end,
                            file_offset=hex(header['sh_offset'] + int(start, 16)),
                            name=name, range_evidence=evidence, reason=reason))
    write_rows('ghidra_targets.tsv', targets, list(targets[0]))

    for row in command_names:
        with (ROOT / row['file']).open('rb') as stream:
            elf = ELFFile(stream)
            data = elf.get_section_by_name(row['symbol_section']).data()
            address = int(row['resolved_target_address'], 16)
            row['string_value'] = data[address:data.index(b'\0', address)].decode('ascii')
    write_rows('mailbox_command_names.tsv', command_names, RELOC_FIELDS + ['string_value'])

    disassembly_ranges = [
        ('mtk_pci.ko', '.text.unlikely', 0, 0xa0),
        ('mtk_pci.ko', '.text', 0x6250, 0x65d8),
        ('mtk_hwifi.ko', '.text', 0xce90, 0xcef8),
        ('mtk_hwifi.ko', '.text', 0xd020, 0xd04c),
        ('mtk_hwifi.ko', '.text', 0xcb64, 0xcb7c),
        ('mt_wifi.ko', '.text', 0x386870, 0x386894),
        ('mt_wifi.ko', '.text', 0x34d820, 0x34d8a0),
        ('mt7990.ko', '.text', 0x140, 0x1ac),
        ('mt7990.ko', '.text', 0xcc4, 0xe70),
    ]
    with (OUT / 'bounded_disassembly.txt').open('w') as output:
        for name, section, start, end in disassembly_ranges:
            path = ROOT / module_prefix / name
            command = ['aarch64-linux-gnu-objdump', '-dr', '-j', section,
                       f'--start-address={hex(start)}', f'--stop-address={hex(end)}', str(path)]
            output.write(f'\nSHA256 {sha256(path)}\nCOMMAND {json.dumps(command)}\n')
            output.write(subprocess.run(command, check=True, capture_output=True, text=True).stdout)

    summary = {
        'mailbox_calls': len(mailbox),
        'mailbox_modules': dict(sorted(Counter(Path(row['file']).name for row in mailbox).items())),
        'mailbox_symbol_owned_calls': sum(row['owner_extent'] == 'symbol_size' for row in mailbox),
        'mailbox_fde_owned_calls': sum(row['owner_extent'] == 'eh_frame_FDE' for row in mailbox),
        'interface_imports': len(imports), 'seed_locations': len(seed_locations),
        'seed_relations': len(focus_rows), 'seed_calls_or_branches': len(calls),
        'seed_data_references_excluding_unwind': len(pointers),
        'kernel_relocations': inventory['files'][-1]['counts'].get('relocations', 0),
        'input_hashes_verified': len(inventory['files']),
        'relocation_rows_verified': total_relocations,
    }
    (OUT / 'selection.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    print('Mailbox callers:')
    for row in mailbox:
        print('\t'.join([Path(row['file']).name, row['target_section'] + '+' + row['offset'],
                         row['owners'], row['owner_start'], row['owner_end'], row['owner_extent']]))
    print('PCI stop/start incoming references:')
    for row in focus_rows:
        if row['file'].endswith('/mtk_pci.ko') and row['symbol_section'] == '.text.unlikely' and row['resolved_target_address'] in {'0x0', '0x50'}:
            print('\t'.join([row['target_section'] + '+' + row['offset'], row['type'],
                             row['resolved_target_functions'], row['containing_object']]))
    outputs = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != 'SHA256SUMS')
    (OUT / 'SHA256SUMS').write_text(''.join(f'{sha256(path)}  {path.name}\n' for path in outputs))


if __name__ == '__main__':
    main()
