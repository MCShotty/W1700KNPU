#!/usr/bin/env python3
"""Run original C parsers, reload entry and password selector under sanitizers."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / '.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/hostapd-wpad-full-mbedtls/hostapd-2026.08.07~831364bf'
OUT = ROOT / '.local/wifi-file-reload'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def function(source, name):
    match = re.search(r'(?m)^[^\n]*\b' + re.escape(name) + r'\(', source)
    assert match, name
    start = match.start()
    if source[start:].startswith(name + '('):
        start = source.rfind('\n', 0, start - 1) + 1
    end = source.index('\n}', match.end()) + 2
    result = source[start:end]
    assert '{' in result and not result.split('{', 1)[0].rstrip().endswith(';'), name
    return result


def main():
    sources = {
        'src/utils/common.c': ['hex2num', 'hex2byte', 'hwaddr_parse', 'hwaddr_aton'],
        'hostapd/config_file.c': ['parse_sae_password', 'parse_sae_password_file'],
        'src/ap/ucode.c': ['uc_hostapd_bss_set_config'],
        'src/ap/ieee802_11.c': ['sae_get_password'],
    }
    snippets = []
    functions = {}
    for relative, names in sources.items():
        text = (NATIVE / relative).read_text()
        for name in names:
            body = function(text, name)
            snippets.append(body)
            functions[name] = dict(path=relative, sha256=hashlib.sha256(body.encode()).hexdigest())
    generated = OUT / 'native-snippets.inc'
    generated.write_text('\n\n'.join(snippets) + '\n')
    binary = OUT / 'sae-file-native'
    harness = ROOT / 'tests/wifi/sae_file_reload_harness.c'
    command = ['cc', '-std=gnu11', '-g', '-O1', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
               '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-Wno-unused-parameter',
               f'-DNATIVE_SNIPPETS="{generated}"', str(harness), '-o', str(binary)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    old = 'old-passphrase|mac=02:00:00:00:00:02\n'
    scenarios = [
        ('rekey', old, 'new-passphrase|mac=02:00:00:00:00:02\n', '02:00:00:00:00:02', '-', 'new', 0),
        ('remove', old, '', '02:00:00:00:00:02', '-', 'fallback', 0),
        ('add-peer', old, old + 'new-passphrase|mac=02:00:00:00:00:03\n', '02:00:00:00:00:03', '-', 'new', 0),
        ('vlan', old, 'old-passphrase|mac=02:00:00:00:00:02|vlanid=17\n', '02:00:00:00:00:02', '-', 'old', 17),
        ('identifier', old, 'new-passphrase|mac=02:00:00:00:00:02|id=changed\n', '02:00:00:00:00:02', 'changed', 'new', 0),
        ('wildcard', 'old-passphrase\n', 'new-passphrase\n', '02:00:00:00:00:03', '-', 'new', 0),
        ('unchanged', old, old, '02:00:00:00:00:02', '-', 'old', 0),
    ]
    rows = []
    with tempfile.TemporaryDirectory(prefix='sae-file-native-') as directory:
        directory = Path(directory)
        old_file, new_file = directory / 'old.sae', directory / 'new.sae'
        for name, before, after, peer, identifier, expected, vlan in scenarios:
            old_file.write_text(before)
            new_file.write_text(after)
            for files_only in [True, False]:
                run = subprocess.run([str(binary), str(old_file), str(new_file), str(int(files_only)), peer, identifier],
                    capture_output=True, text=True, timeout=20, env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=1'))
                assert run.returncode == 0, run.stderr
                result = json.loads(run.stdout)
                assert not run.stderr and result['ret'] == 0, (name, result, run.stderr)
                assert result['psk_path_new']
                correct = result['selected'] == expected and result['vlan'] == vlan
                assert correct == (not files_only or name == 'unchanged'), (name, files_only, result)
                assert result['stops'] == result['starts'] == result['updates'] == int(not files_only)
                rows.append(dict(case=name, files_only=files_only, desired_credential_state=correct, **result))
        old_file.write_text(old)
        for files_only in [True, False]:
            run = subprocess.run([str(binary), str(old_file), str(directory / 'missing.sae'), str(int(files_only)),
                                  '02:00:00:00:00:02', '-'], capture_output=True, text=True, timeout=20)
            assert run.returncode == 0 and not run.stderr, run.stderr
            result = json.loads(run.stdout)
            assert result['ret'] == -1 and result['selected'] == 'old'
            assert result['starts'] == result['stops'] == result['updates'] == 0
            rows.append(dict(case='missing-file', files_only=files_only, **result))
    report = dict(cases=len(rows), files_only_stale_cases=6, functions=functions,
                  harness_sha256=sha(harness), snippets_sha256=sha(generated), binary_sha256=sha(binary),
                  command=command, sanitizers='AddressSanitizer and UndefinedBehaviorSanitizer', rows=rows,
                  scope='Eight original C functions; synthetic structures, ucode binding, whole-config wrapper, memory release and driver lifecycle. Actual SAE file parser/selector. No crypto, ABI, client or live daemon memory proof.')
    (OUT / 'native.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ['rows', 'functions', 'command']}))


if __name__ == '__main__':
    main()
