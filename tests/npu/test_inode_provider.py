#!/usr/bin/env python3
"""Actual provider INODE routing and immutable retained records; modeled peer."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import test_provider_session as parent

ROOT = parent.ROOT
HARNESS = ROOT / 'tests/npu/inode-provider-harness.c'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--header', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    destination = ROOT / '.local/npu-inode-provider' / args.name
    assert not destination.exists()
    source, header = args.source.resolve(), args.header.resolve()
    paths = [source, header, HARNESS, parent.HARNESS, Path(__file__), Path(parent.__file__),
             Path(parent.loader.__file__), Path(parent.loader.extract.__file__),
             *[path for path in parent.SOURCE.rglob('*') if path.is_file()]]
    inputs = {str(path.relative_to(ROOT)): parent.loader.sha(path) for path in paths}
    command = parent.prepare(destination, source.read_text(), header.read_text())
    generated = destination / 'fixture.c'
    generated.write_text('#define main original_provider_main\n' + parent.HARNESS.read_text() +
        '\n#undef main\n#include "' + str(HARNESS) + '"\n')
    command = [generated if item == parent.HARNESS else item for item in command]
    flags = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all',
             '-Wno-unused-function', '-Wno-unused-variable', '-Wno-unused-but-set-variable', '-fstack-usage']
    binary = destination / 'test'
    parent.loader.run(command + flags + ['-o', binary], destination / 'build.log')
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    matrix = json.loads(parent.loader.run([binary], destination / 'run.log', env=env).stdout)
    assert matrix['passed'] and matrix['cases'] == 504 and matrix['native_admission'] is False
    original = (destination / 'provider-session.inc').read_text()
    cold = parent.loader.extract.function(source.read_text(), 'airoha_npu_wlan_cold_command')
    mutations = {
        'omit-inode-pin': (' || inode < NPU_COLD_INODE_STAGES;', ';'),
        'omit-lease-precheck': ('pinned && (!priv->checked_pair || !airoha_npu_wlan_tail_lifetime_valid(priv))',
                                'pinned && !priv->checked_pair'),
        'omit-pointer-pin': ('priv->dma_lifetime != life ||', 'false ||'),
        'omit-checked-pin': ('!priv->checked_pair || life->dev', 'false || life->dev'),
        'omit-device-pin': ('life->dev != captured.dev ||', 'false ||'),
        'omit-lease-record-pin': ('memcmp((u8 *)life + lease_offset, (u8 *)&captured + lease_offset,\n'
                                  '\t\t    sizeof(captured) - lease_offset) ||', 'false ||'),
        'omit-plan-pin': ('memcmp(plan, priv->native_plan, sizeof(plan)) ||', 'false ||'),
        'omit-post-validity': ('!airoha_npu_wlan_tail_lifetime_valid(priv)))\n\t\terr = -EPROTO;\n\tif (err)',
                               'false))\n\t\terr = -EPROTO;\n\tif (err)')}
    rejected = []
    for name, (before, after) in mutations.items():
        target = destination / name
        target.mkdir()
        modified = parent.loader.once(cold, before, after)
        (destination / 'provider-session.inc').write_text(parent.loader.once(original, cold, modified))
        mutant = target / 'test'
        parent.loader.run(command + flags + ['-o', mutant], target / 'build.log')
        result = parent.loader.run([mutant], target / 'run.log', env=env, accepted=11)
        assert 'FAIL[session]' in result.stderr and 'AddressSanitizer' not in result.stderr
        rejected.append(dict(name=name, binary_sha256=parent.loader.sha(mutant), oracle=result.stderr.strip()))
    route = parent.loader.extract.function(source.read_text(), 'airoha_npu_wlan_msg_send_session')
    for name, before, after in (
            ('omit-inode-route', 'priv->checked_pair && func_id == WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR',
                                 'false && func_id == WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR'),
            ('allow-rro-route', 'ifindex != 2 && ifindex != 7', 'false')):
        target = destination / name
        target.mkdir()
        modified = parent.loader.once(route, before, after)
        (destination / 'provider-session.inc').write_text(parent.loader.once(original, route, modified))
        mutant = target / 'test'
        parent.loader.run(command + flags + ['-o', mutant], target / 'build.log')
        result = parent.loader.run([mutant], target / 'run.log', env=env, accepted=11)
        assert 'FAIL[session]' in result.stderr and 'AddressSanitizer' not in result.stderr
        rejected.append(dict(name=name, binary_sha256=parent.loader.sha(mutant), oracle=result.stderr.strip()))
    (destination / 'provider-session.inc').write_text(original)
    assert all(parent.loader.sha(ROOT / name) == digest for name, digest in inputs.items())
    receipt = dict(passed=True, matrix=matrix, mutants=rejected, inputs=inputs,
        binary_sha256=parent.loader.sha(binary), sanitizers=['address', 'undefined', 'leak'],
        native_inode_admission=False, full_setup=False, hardware=False,
        limits=['Actual provider, client and server C execute; callbacks, transport and backing are modeled.',
                'Complete prerequisite history is obtained only through actual C requests and begin/finish.',
                'Two HIF profiles and all five tail/INODE commands retain post-effect allocation/plan drift.',
                'No original native INODE store, physical containment or release/reclaim authority is proven.'])
    (destination / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=matrix['cases'], mutants=len(rejected), native_inode_admission=False)))


if __name__ == '__main__':
    main()
