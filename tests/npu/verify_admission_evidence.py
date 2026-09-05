#!/usr/bin/env python3
"""Bind admission evidence to tested inputs; do not infer hardware containment."""
import json
from pathlib import Path
import re
import subprocess

from test_barrier_protocol import ROOT, BUILD, Rv32, digest
from test_admission_protocol import OUT, ADMISSION
from test_firmware_stop_counterexample import INPUT, CODE_SHA, DATA_SHA

BASE = '37a83526487c82682448864e9f6cad9aaf3bf8fa'


def main():
    names = ('native-mailbox-dispatch.json', 'admission-protocol-tests.json', 'admission-native-tests.json')
    native, protocol, adapter = [json.loads((OUT / name).read_text()) for name in names]
    assert all(report['passed'] for report in (native, protocol, adapter))
    assert protocol['native_rv32_call_pairs'] == 1667
    assert len(protocol['mutation_controls']) == 6
    assert all(row['rejected'] and row['assertion'] for row in protocol['mutation_controls'].values())
    assert protocol['source_sha256'] == digest(ADMISSION.read_bytes())
    assert protocol['header_sha256'] == digest(ADMISSION.with_suffix('.h').read_bytes())
    assert protocol['native_elf_sha256'] == digest((BUILD / 'admission.so').read_bytes())
    assert protocol['rv32_elf_sha256'] == digest((BUILD / 'admission.elf').read_bytes())
    assert adapter['elf_sha256'] == digest((BUILD / 'admission-platform.elf').read_bytes())
    for name, expected in adapter['source_sha256'].items():
        assert digest((ROOT / name).read_bytes()) == expected, name
    assert native['firmware_sha256'] == adapter['firmware_sha256'] == CODE_SHA
    assert native['data_sha256'] == adapter['data_sha256'] == DATA_SHA
    code = (INPUT / 'en7581_MT7996_npu_rv32.bin').read_bytes()
    assert digest(code) == CODE_SHA
    assert digest((INPUT / 'en7581_MT7996_npu_data.bin').read_bytes()) == DATA_SHA
    assert native['native_stop']['trace'] == ['0x840030b2', '0x84003cd6', '0x84003a9c', '0x8400fc2c', '0x8400e084']
    assert native['unsupported_info_selector15']['words'][2] == 0
    assert native['static_function12_overwrites_wifi_callback'] == {'before': '0x84003a9c', 'after': '0x2000000'}
    assert adapter['eight_shared_contexts']['wire_status_parked_mask'] == 255
    assert adapter['eight_shared_contexts']['all_acks_via_actual_code']
    assert adapter['eight_shared_contexts']['no_drain_witnesses']
    assert len(adapter['mask_readback_failures']) == 2 and len(adapter['irq_abi_cases']) == 5
    assert adapter['static_registration_rejections'] == list(range(16))
    assert adapter['omitted_irq_admission']['rejected']
    assert adapter['combined_elf_worker_regressions'] == {
        'new_worker_register_cases': 96, 'new_worker_stop_resume': 16,
        'new_worker_inflight': 6, 'new_worker_interrupted_refresh': 6,
        'core5_stop_resume': 4, 'core5_register_cases': 10, 'core5_inflight': True}

    export = OUT / 'ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt'
    text = export.read_text()
    assert 'failed_decompilations=0' in text and 'decompiled=false' not in text
    starts = list(re.finditer(r'^FUNCTION (\S+) @ ram:([0-9a-f]+)$', text, re.M))
    assert len(starts) == 427
    blocks = {int(start[2], 16): text[start.end():starts[index + 1].start() if index + 1 < len(starts) else len(text)]
              for index, start in enumerate(starts)}
    assert 'ram:84003aa8 c.lw a1,0x0(a4)' in blocks[0x84003a9c]
    assert 'ram:84003b1e c.jalr a5' in blocks[0x84003a9c]
    assert 'ram:84003b70 c.jalr a5' in blocks[0x84003a9c]
    assert 'ram:84003a9a c.jr t1' in blocks[0x84003a86]
    assert 'ram:84003f80 sw a5,-0x67c(gp)' in blocks[0x84003f00]
    assert 'ram:84003f8c sw a5,-0x678(gp)' in blocks[0x84003f00]
    log = (OUT / 'ghidra-mailbox/analysis.log').read_text()
    assert 'Analysis timed out' not in log and 'Save succeeded' in log and 'Analysis succeeded' in log
    rv = Rv32(BUILD / 'admission-platform.elf')
    sections = [{'name': section.name, 'start': int(section['sh_addr']),
                 'end': int(section['sh_addr']) + int(section['sh_size'])}
                for section in rv.elf.iter_sections() if section['sh_flags'] & 2 and section['sh_size']]
    assert all(0x84040000 <= section['start'] < section['end'] < 0x84048000 for section in sections)
    for patch in adapter['irq_stop_resume']['patches']:
        address, target = int(patch['site'], 16), int(patch['target'], 16)
        assert patch['preimage'] == code[address - 0x84000000:address - 0x84000000 + 4].hex()
        value = int.from_bytes(bytes.fromhex(patch['postimage']), 'little')
        assert value & 0xfff == 0x6f
        offset = ((value >> 31 & 1) << 20 | (value >> 21 & 0x3ff) << 1 |
                  (value >> 20 & 1) << 11 | (value >> 12 & 0xff) << 12)
        if offset & (1 << 20):
            offset -= 1 << 21
        assert address + offset == target
    lock = ROOT / 'firmware/source-lock.json'
    assert subprocess.check_output(['git', 'show', BASE + ':firmware/source-lock.json'], cwd=ROOT) == lock.read_bytes()
    assert not subprocess.check_output(['git', 'diff', '--name-only', BASE, '--',
                                       'firmware/source-lock.json', 'firmware/overlay', 'firmware/patches',
                                       'firmware/build.config', 'firmware/feeds.conf.default'], cwd=ROOT)
    report = {'passed': True, 'packaged_source_unchanged_from': BASE,
              'source_lock_sha256': digest(lock.read_bytes()),
              'result_files': {name: digest((OUT / name).read_bytes()) for name in names},
              'ghidra_export_sha256': digest(export.read_bytes()),
              'analysis_helpers': {name: digest((ROOT / 'tools/ghidra' / name).read_bytes()) for name in
                                   ('SeedNpuMailboxCallbacks.java', 'run_admission_mailbox.ps1',
                                    'SetupCurrentNpuMap.java', 'ModelNpuConcurrency.java',
                                    'SeedNpuUartIrq.java', 'ExportMailboxContract.java')},
              'discovered_functions': 427, 'failed_decompilations': 0,
              'elf_allocated_sections': sections,
              'verifier_sha256': digest(Path(__file__).read_bytes()),
              'scope': 'Artifact provenance, native dispatch facts and recorded test inventory. Not independent full-path coverage, live hardware containment or production integration.'}
    (OUT / 'evidence-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
