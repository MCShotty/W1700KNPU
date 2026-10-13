#!/usr/bin/env python3
"""Actual boot-sequence C and fault/mutant oracles; no hardware operations."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode = True
import test_npu_firmware_loader as loader

ROOT = loader.ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--header', type=Path,
                        help='Immutable prepared header when a world build can replace the build tree')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    source = args.source.resolve()
    lock = ROOT / 'firmware/source-lock.json'
    build = ROOT / json.loads(lock.read_bytes())['build_directory']
    kernel = build / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.52'
    header = (args.header or kernel / 'include/linux/soc/airoha/airoha_offload.h').resolve()
    assert header.is_relative_to(ROOT)
    harness = ROOT / 'tests/npu/boot-launch-harness.c'
    dest = ROOT / '.local/npu-boot-launch-20261010' / args.name
    assert source.is_relative_to(ROOT) and not dest.exists()
    dest.mkdir(parents=True)
    text = source.read_text()
    q = loader.extract
    helper = q.function(text, 'airoha_npu_start_firmware')
    constants = '\n'.join(q.macro(text, name) for name in (
        'NPU_EN7581_7996_PLAN_REGIONS', 'NPU_EN7581_FIRMWARE_RV32_MAX_SIZE', 'NPU_SRAM_BACKUP_SIZE',
        'NPU_EN7581_NATIVE_VERSION', 'NPU_CLUSTER_BASE_ADDR', 'REG_CR_BOOT_TRIGGER', 'REG_CR_BOOT_CONFIG',
        'REG_CR_BOOT_BASE', 'NPU_MBOX_BASE_ADDR', 'REG_CR_NPU_MIB'))
    types = loader.unused_session_types(text) + q.declaration(header.read_text(), 'enum', 'airoha_npu_wlan_get_cmd')
    types += '\n' + '\n'.join(q.declaration(text, 'struct', name) for name in ('airoha_npu_dma_lifetime', 'airoha_npu_priv'))
    inputs = {str(p.relative_to(ROOT)): loader.sha(p) for p in (source, header, harness, Path(__file__),
              Path(loader.__file__), Path(q.__file__))}
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')

    def run(name, body, expected=0):
        directory = dest / name
        directory.mkdir()
        (directory / 'constants.inc').write_text(constants + '\n')
        (directory / 'types.inc').write_text(types + '\n')
        (directory / 'boot.inc').write_text(body + '\n')
        binary = directory / 'test'
        loader.run([shutil.which('gcc'), '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-fno-pie', '-no-pie', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-I' + str(directory), harness, '-o', binary], directory / 'build.log')
        return loader.run([binary], directory / 'run.log', env=env, accepted=expected), binary

    done, binary = run('nominal', helper)
    matrix = json.loads(done.stdout)
    mutants = [('ignore-first-write-error', helper.replace('\n\tif (err)\n\t\treturn err;', '\n\t(void)err;', 1)),
               ('omit-boot-attempt-latch', loader.once(helper, 'priv->boot_attempted = true;', '(void)priv;')),
               ('allow-second-launch', loader.once(helper, 'if (priv->boot_attempted)', 'if (false)')),
               ('ignore-version-transport', loader.once(helper, 'return priv->checked_pair ? err : 0;', 'return 0;')),
               ('accept-wrong-checked-version', loader.once(helper, 'val != NPU_EN7581_NATIVE_VERSION', 'false')),
               ('wrong-backup-address', loader.once(helper, 'res->start + NPU_EN7581_FIRMWARE_RV32_MAX_SIZE', 'res->start')),
               ('wrong-core-boot-base', loader.once(helper, 'REG_CR_BOOT_BASE(i), res->start', 'REG_CR_BOOT_BASE(i), res->start + 4'))]
    for register in ('REG_CR_NPU_MIB(21)', 'REG_CR_BOOT_CONFIG', 'REG_CR_BOOT_TRIGGER'):
        prefix = '\terr = regmap_write(npu->regmap, ' + register
        start = helper.index(prefix)
        tail = helper.index('\tif (err)\n\t\treturn err;', start)
        mutant = helper[:tail] + helper[tail:].replace('\tif (err)\n\t\treturn err;', '\t(void)err;', 1)
        mutants.append(('ignore-error-' + ('mib21' if 'MIB' in register else register.lower().removeprefix('reg_cr_')), mutant))
    rejected = []
    for name, body in mutants:
        assert body != helper
        _, artifact = run(name, body, 11)
        rejected.append(dict(name=name, binary_sha256=loader.sha(artifact)))
    probe = q.function(text, 'airoha_npu_probe')
    assert probe.index('airoha_npu_run_firmware') < probe.index('airoha_npu_start_firmware') < probe.index('platform_set_drvdata')
    assert all(loader.sha(ROOT / path) == digest for path, digest in inputs.items())
    result = dict(passed=True, matrix=matrix, rejected_mutants=rejected, inputs=inputs,
                  binary_sha256=loader.sha(binary), sanitizers=['address', 'undefined', 'leak'],
                  limits=['Actual Linux boot sequencer C; register/timing/version responses are modeled.',
                          'Expected version response is not all-hart startup,physical containment,drains or complete NPU/client acceptance.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=matrix['cases'], mutants=len(rejected))))


if __name__ == '__main__':
    main()
