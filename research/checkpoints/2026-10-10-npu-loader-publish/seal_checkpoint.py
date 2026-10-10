#!/usr/bin/env python3
"""Seal this checkpoint's text receipts; never export binaries or device backups."""
import hashlib
import io
import json
from pathlib import Path
import re
import shutil

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
LOCAL = ROOT / '.local/npu-loader-publish-20261010'
MERGE = ROOT / '.local/merge-nonoc-20260923'
PAIR = ROOT / '.build/merged-openwrt/bin/npu-pair-checked-loader-incremental-20261010'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not (OUT / 'verification.json').exists(), 'Preserve the existing seal.'
    receipts = {
        'checked-loader.json': LOCAL / 'checked-final-current/result.json',
        'dma-lifetime.json': LOCAL / 'lifetime-final-current/result.json',
        'probe-lifetime.json': LOCAL / 'probe-final-current/result.json',
        'request-plan.json': ROOT / '.local/npu-provider-plan-20261010/publish-final-current/result.json',
        'memory-retry-v2.json': ROOT / '.local/npu-cold-memory-plan/checked-package-current/result.json',
        'actual-pair-loader.json': ROOT / '.local/npu-raw-pair-20261010/packaged-incremental/result.json',
        'native-published.json': LOCAL / 'published-native-current/result.json',
        'raw-native.json': ROOT / '.local/npu-raw-pair-20261010/loader-packaged-full/result.json',
        'assembly.json': LOCAL / 'assembly-package-final.json',
        'units.json': LOCAL / 'unit-package-final.json',
        'source-export.json': LOCAL / 'source-package-final.json',
        'image-first.json': MERGE / 'checked-loader-package-20261010-offline/result.json',
        'image-final.json': MERGE / 'checked-loader-incremental-20261010-offline/result.json',
        'build-first.json': MERGE / 'build-checked-loader-package-20261010.json',
        'build-final.json': MERGE / 'build-checked-loader-incremental-20261010.json',
        'pair-manifest.json': PAIR / 'manifest.json',
        'checkpatch.json': LOCAL / 'checkpatch-final.json',
        'checkpatch.log': LOCAL / 'checkpatch-final-clean.log',
        'provider-loader-publish.patch': LOCAL / 'provider-loader-publish-final.patch',
        'build-runner.log': LOCAL / 'build-runner-package-final.log',
        'source-verifier.log': LOCAL / 'source-verifier-package-final.log',
        'preserved-previous.json': LOCAL / 'pre-world-image/preservation.json',
        'preserved-first-pair.json': LOCAL / 'pre-style-image/preservation.json',
        'preserved-first-package.json': LOCAL / 'pre-incremental-image/preservation.json',
    }
    for phase in ('pre', 'post', 'package'):
        for kind in ('request', 'result'):
            name = f'jev-{phase}-{kind}.json'
            receipts[name] = LOCAL / name
    inputs = {}
    host_tools = {}

    def remember(name, digest):
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and sha(path) == digest, ('changed-input', name)
        if name in inputs:
            assert inputs[name] == digest, ('conflicting-input', name)
        inputs[name] = digest

    def inspect(value):
        if isinstance(value, list):
            for row in value:
                inspect(row)
        elif isinstance(value, dict):
            if 'path' in value and 'sha256' in value:
                path = Path(value['path'])
                if path.is_absolute() and not path.is_relative_to(ROOT):
                    assert str(path) == '/usr/bin/make' and sha(path) == value['sha256']
                    host_tools[str(path)] = value['sha256']
                else:
                    remember(value['path'], value['sha256'])
            for name, row in value.items():
                if name in ('inputs', 'source_inputs') and isinstance(row, dict):
                    for path, digest in row.items():
                        remember(path, digest)
                else:
                    inspect(row)

    data = {}
    for name, source in receipts.items():
        assert source.suffix in ('.json', '.log', '.patch') and source.stat().st_size < 4 * 1024 * 1024
        if source.suffix == '.json':
            data[name] = json.loads(source.read_bytes())
            inspect(data[name])
            if 'passed' in data[name]:
                assert data[name]['passed'] is True, name
        shutil.copy2(source, OUT / name)
    for name in ('preserved-previous.json', 'preserved-first-pair.json', 'preserved-first-package.json'):
        receipt = data[name]
        remember(receipt['preserved'], receipt['sha256'])
    final = data['image-final.json']
    remember(final['image'], final['sha256'])
    assert final['sha256'] == '05ca2802ec5c9149b2c1a928f829a61d666edb00d8a37316493689c28990001a'
    assert final['source_lock_sha256'] == sha(ROOT / 'firmware/source-lock.json')
    assert final['checked_npu_pair']['manifest_sha256'] == sha(PAIR / 'manifest.json')
    for name, field in (('CODE.bin', 'code'), ('DATA.bin', 'data')):
        assert sha(PAIR / name) == final['checked_npu_pair'][field]['sha256']
        for other in (ROOT / '.build/merged-openwrt/bin/npu-pair-checked-loader-20261010-v2',
                      ROOT / '.build/merged-openwrt/bin/npu-pair-checked-loader-20261010-final'):
            assert (other / name).read_bytes() == (PAIR / name).read_bytes()
    assert all(data[name]['exit_code'] == 0 for name in ('build-first.json', 'build-final.json'))
    assert data['image-first.json']['checked_npu_pair']['manifest_sha256'] != final['checked_npu_pair']['manifest_sha256']
    assert sum(row['changed_files_verified'] for row in data['source-export.json']) == 62
    assert data['assembly.json']['test_groups'] == 16 and data['assembly.json']['skipped'] == 0
    assert data['native-published.json']['synthetic_plan_identity_writes'] is False
    source = ROOT / '.local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c'
    prepared = ROOT / '.build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.52/drivers/net/ethernet/airoha/airoha_npu.c'
    assert source.read_bytes() == prepared.read_bytes()
    for path in (source, prepared, ROOT / 'firmware/source-lock.json', ROOT / 'firmware/patches/openwrt.patch',
                 ROOT / 'firmware/overlay/openwrt/target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch'):
        remember(str(path.relative_to(ROOT)), sha(path))
    module = ROOT / final['selected_modules']['airoha_npu.ko']['path']
    elf = ELFFile(io.BytesIO(module.read_bytes()))
    symbols = elf.get_section_by_name('.symtab')
    imports = {symbol.name for symbol in symbols.iter_symbols() if symbol['st_shndx'] == 'SHN_UNDEF'}
    assert {'__module_get', 'dma_alloc_attrs', 'dma_free_attrs', 'get_random_bytes', 'wait_for_random_bytes', 'sha256'} <= imports
    # Count log findings without treating ignored upstream diagnostics as acceptance.
    log = (MERGE / 'build-checked-loader-incremental-20261010.log').read_text()
    diagnostics = dict(warning_lines=len(re.findall(r'(?m)^.*\bwarning:', log)),
                       ignored_errors=re.findall(r'(?m)^.*Error .*\(ignored\).*$', log))
    result = dict(passed=True, source_commit_before='efb80ba58c8be41c1b44f9700cbfea0bfc00224b',
                  image_sha256=final['sha256'], source_lock_sha256=sha(ROOT / 'firmware/source-lock.json'),
                  pair_code_sha256=sha(PAIR / 'CODE.bin'), pair_data_sha256=sha(PAIR / 'DATA.bin'),
                  provider_module_sha256=sha(module), provider_imports=sorted(imports),
                  canonical_prepared_source_equal=True, incremental_manifest_refresh=True,
                  earlier_executed_pair_bytes_equal=True, inputs=inputs, host_tools=host_tools, diagnostics=diagnostics,
                  physical_acceptance=False, full_npu_goal_complete=False,
                  limits=['Exact input/artifact seal plus source/offline/emulated evidence only.',
                          'Physical containment,strict real setup,retirement/hot lifecycle and clients remain open.'])
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    manifest = [dict(path=str(path.relative_to(OUT)), bytes=path.stat().st_size, sha256=sha(path))
                for path in sorted(OUT.iterdir()) if path.is_file() and path.name != 'file-manifest.json']
    (OUT / 'file-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(passed=True, inputs=len(inputs), files=len(manifest), image_sha256=final['sha256'])))


if __name__ == '__main__':
    main()
