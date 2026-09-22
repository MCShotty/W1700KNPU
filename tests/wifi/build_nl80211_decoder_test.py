#!/usr/bin/env python3
"""Cross-build the real nl80211 decoder with process-local allocation faults."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / '.build/openwrt'
UCODE = BUILD / 'build_dir/target-aarch64_cortex-a53_musl/ucode-2026.07.09~b885dd0f'
STAGING = BUILD / 'staging_dir/target-aarch64_cortex-a53_musl'
CC = BUILD / 'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-gcc'
SCRATCH = ROOT / '.local/wifi-config/decoder'
PATCH = ROOT / 'firmware/overlay/openwrt/package/utils/ucode/patches/112-nl80211-report-decoder-allocation-failure.patch'
OLD_SHA = '9deca47fdd30853b676c97bb89bbca951ea9bf4ecccb781ec3fab682a44ad2bf'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    source = (UCODE / 'lib/nl80211.c').read_bytes()
    new_block = b'\tif (!tb) {\n\t\tset_error(NLE_NOMEM, NULL);\n\t\treturn false;\n\t}'
    if new_block in source:
        source = source.replace(new_block, b'\tif (!tb)\n\t\treturn false;', 1)
    assert sha(source) == OLD_SHA
    old = SCRATCH / 'old.c'
    old.write_bytes(source)
    patch = subprocess.run(['patch', '--silent', '--fuzz=0', '--output=-', str(old)],
                           input=PATCH.read_bytes(), capture_output=True, timeout=20)
    assert patch.returncode == 0, patch.stderr
    corrected = SCRATCH / 'corrected.c'
    corrected.write_bytes(patch.stdout)
    assert patch.stdout.replace(new_block, b'\tif (!tb)\n\t\treturn false;', 1) == source
    outputs = []
    for variant, path, expected in [('old', old, 0), ('corrected', corrected, 1)]:
        executable = SCRATCH / f'nl80211-decoder-{variant}'
        command = [str(CC), '-std=gnu11', '-D_GNU_SOURCE', '-O2', '-ffunction-sections', '-fdata-sections',
                   '-Werror', '-Wall', '-Wextra', '-Wno-unused-parameter', '-Wno-sign-compare',
                   '-Wno-unused-function', f'-DNL80211_SOURCE="{path}"', f'-DEXPECT_ERROR={expected}',
                   f'-I{UCODE / "include"}', f'-I{STAGING / "usr/include"}',
                   f'-I{STAGING / "usr/include/libnl-tiny"}',
                   str(ROOT / 'tests/wifi/nl80211_decoder_harness.c'),
                   f'-L{STAGING / "usr/lib"}', '-Wl,--gc-sections',
                   '-lucode', '-lnl-tiny', '-lubox', '-ljson-c', '-lm', '-o', str(executable)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=120,
                                env=dict(os.environ, STAGING_DIR=str(STAGING)))
        assert result.returncode == 0, result.stderr
        outputs.append(dict(variant=variant, source_sha256=sha(path.read_bytes()),
                            executable_sha256=sha(executable.read_bytes()), command=command))
    report = dict(scope='Cross-built actual converter/reply/completion/error API, synthetic netlink messages only',
                  patch_sha256=sha(PATCH.read_bytes()), harness_sha256=sha((ROOT / 'tests/wifi/nl80211_decoder_harness.c').read_bytes()),
                  compiler_sha256=sha(CC.read_bytes()), outputs=outputs, runtime_executed=False)
    (ROOT / 'research/checkpoints/2026-09-06-wifi-config/decoder-build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({item['variant']: item['executable_sha256'] for item in outputs}))


if __name__ == '__main__':
    main()
