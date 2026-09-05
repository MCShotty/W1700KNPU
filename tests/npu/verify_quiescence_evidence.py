#!/usr/bin/env python3
"""Check checkpoint identity/coverage; semantic findings require the cited review."""
import hashlib
import json
from pathlib import Path
import struct

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-quiescence'
BUILD = ROOT / '.build/openwrt'
KERNEL = BUILD / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.44'
FW = BUILD / 'build_dir/target-aarch64_cortex-a53_musl/linux-firmware-20260810/airoha'
ARTIFACTS = ROOT / '.local/npu-quiescence/artifacts'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def executable(path):
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        return {section.name: hashlib.sha256(section.data()).hexdigest()
                for section in elf.iter_sections()
                if section['sh_flags'] & 4 and section['sh_size']}


def check(condition, description):
    if not condition:
        raise RuntimeError(description)


def main():
    expected = {
        ROOT / 'research/stock/elf/stock-kernel.vmlinux.elf':
            'a51e6d0a6deee620a5f715c9469f193906cdf3fcea28b97ce01cf88383aa704e',
        FW / 'en7581_MT7996_npu_rv32.bin':
            'e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643',
        FW / 'en7581_MT7996_npu_data.bin':
            '61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1',
        ARTIFACTS / 'airoha_npu.o':
            '5b025cfa3ae234909ff4164f42a789b08390248de471cbf803afecad65374a68',
        KERNEL / 'drivers/net/ethernet/airoha/airoha_npu.c':
            '51cd396f8c141bbf6d425088ddbf39e8a59d4874fa529980332509ba3b52e1fa',
    }
    for path, sha in expected.items():
        check(digest(path) == sha, f'Input drift: {path}')
    check(digest(KERNEL / 'drivers/net/ethernet/airoha/airoha_npu.o') ==
          digest(ARTIFACTS / 'airoha_npu.o'), 'Preserved provider differs from kernel object')
    check((ROOT / 'firmware/build.config').read_bytes() == (BUILD / '.config').read_bytes(),
          'Original build configuration changed')
    exports = {}
    for name, filename, sha, count, total in [
        ('ghidra-kernel', 'stock-kernel.vmlinux.elf.txt', expected[ROOT / 'research/stock/elf/stock-kernel.vmlinux.elf'], 18, 33676),
        ('ghidra-current-rv32-decoded', 'en7581_MT7996_npu_rv32.bin.txt', expected[FW / 'en7581_MT7996_npu_rv32.bin'], 424, 424),
        ('ghidra-provider', 'airoha_npu.o.txt', expected[ARTIFACTS / 'airoha_npu.o'], 2, 24),
    ]:
        path = OUT / name / filename
        text = path.read_text()
        for marker in [f'sha256={sha}', f'exported_functions={count}',
                       f'total_executable_functions={total}', 'failed_decompilations=0']:
            check(marker in text, f'Export marker absent: {name}/{marker}')
        check('decompiled=false' not in text, f'Failed selected decompilation: {name}')
        check('Analysis timed out' not in (OUT / name / 'analysis.log').read_text(),
              f'Analysis timeout: {name}')
        exports[name] = {'sha256': digest(path), 'exported': count, 'analyzed_functions': total}
    firmware = (FW / 'en7581_MT7996_npu_rv32.bin').read_bytes()
    decoded = (OUT / 'ghidra-current-rv32-decoded/en7581_MT7996_npu_rv32.bin.txt').read_text()
    for address in [0x8400b19a, 0x8400b3ba, 0x8400c56a, 0x8400c720]:
        word = struct.unpack_from('<I', firmware, address - 0x84000000)[0]
        check(word & 0xfff07fff == 0xfc200073, f'Cache opcode mismatch at {address:x}')
        check(f'ram:{address:08x} sf.cdiscard.d.l1 ' in decoded,
              f'Missing decoded cache instruction at {address:x}')
    check('sifive_cdiscard_d_l1' in decoded, 'Custom cache-operation pcode absent')
    old_path = ROOT / '.local/legacy-windows/work/ghidra-live-npu-fw-20260713/input/en7581_MT7996_npu_rv32.bin'
    check(digest(old_path) == '51f3583c45b2c356866ee53bd79dac93e10ad069bc75ff516019ea7edb929b79',
          'Historical V28 input drift')
    old = old_path.read_bytes()
    differences = [i for i, (a, b) in enumerate(zip(firmware, old)) if a != b]
    check(len(firmware) == 122336 and len(old) == len(firmware) + 244,
          'Historical V28 lengths differ from comparison')
    check(differences == list(range(0xac30, 0xac34)) + list(range(0xf0f6, 0xf0fa)),
          'Historical V28 prefix differences are not the two recorded hooks')
    variants = {}
    for variant in ['npu-enabled', 'wlan-dma']:
        variants[variant] = {}
        for name in ['mt76.ko', 'mt76-connac-lib.ko', 'mt7996e.ko']:
            path = ARTIFACTS / variant / name
            sections = executable(path)
            check(bool(sections), f'Empty executable sections: {path}')
            check(sections == executable(ROOT / '.local/npu-attach/artifacts' / variant / name),
                  f'mt76 executable code changed unexpectedly: {variant}/{name}')
            variants[variant][name] = {'sha256': digest(path), 'executable_sections': sections,
                                     'matches_prior_provider_guard': True}
    report = {'passed': True, 'scope': 'identity, export coverage, cache opcode decoding, config and module-code consistency; not DMA quiescence or hardware proof',
              'inputs': {str(path.relative_to(ROOT)): sha for path, sha in expected.items()},
              'ghidra': exports, 'variants': variants,
              'historical_v28_comparison': {'sha256': digest(old_path),
                                           'changed_prefix_offsets': [hex(i) for i in differences],
                                           'appended_bytes': len(old) - len(firmware)},
              'config_sha256': digest(ROOT / 'firmware/build.config')}
    (OUT / 'evidence-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'ghidra': exports, 'module_variants': list(variants)}, indent=2))


if __name__ == '__main__':
    main()
