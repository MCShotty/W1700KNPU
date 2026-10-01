#!/usr/bin/env python3
"""Actual provider frames consumed by the original native INODE wrapper."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
import test_host_queue_publication as extract
import test_inode_native_contract as native

ROOT = Path(__file__).resolve().parents[2]
DRIVER = 'drivers/net/ethernet/airoha/airoha_npu.c'
PATCH = ROOT / 'firmware/overlay/openwrt/target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch'
FIXTURES = ROOT / 'tests/npu/fixtures/airoha-npu-6.18.52'
HARNESS = ROOT / 'tests/npu/inode-frame-harness.c'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, directory, name, expected=0):
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1',
               GIT_CEILING_DIRECTORIES=str(directory.parent))
    result = subprocess.run(list(map(str, command)), cwd=directory, capture_output=True,
                            text=True, timeout=120, env=env)
    (directory / (name + '.stdout')).write_text(result.stdout)
    (directory / (name + '.stderr')).write_text(result.stderr)
    if expected is None:
        assert result.returncode != 0, ('surviving-mutant', name)
    else:
        assert result.returncode == expected, (command, result.returncode, result.stderr[-3000:])
    return result


def replay(dest):
    lock = json.loads((ROOT / 'firmware/source-lock.json').read_text())
    provenance = json.loads((FIXTURES / 'provenance.json').read_text())
    assert lock['kernel'] == provenance['kernel']
    assert lock['openwrt']['base'] == provenance['openwrt_base']
    for name, digest in provenance['files'].items():
        assert sha(FIXTURES / name) == digest
    relative = str(PATCH.relative_to(ROOT / 'firmware/overlay/openwrt'))
    assert sha(PATCH) == next(row['sha256'] for row in lock['openwrt']['changed_files'] if row['path'] == relative)
    file = dest / 'replayed' / DRIVER
    file.parent.mkdir(parents=True)
    shutil.copy2(FIXTURES / 'provider-upstream.c', file)
    run(['git', 'apply', '--include=' + DRIVER, PATCH], dest / 'replayed', 'apply')
    return file


def build(source, directory):
    directory.mkdir()
    header = (FIXTURES / 'airoha_offload.h').read_text()
    types = [extract.macro(source, 'NPU_EN7581_7996_TX_CHECK_SIZE'),
             extract.declaration(header, 'enum', 'airoha_npu_wlan_set_cmd'),
             extract.declaration(source, 'struct', 'wlan_mbox_data'),
             extract.declaration(source, 'struct', 'airoha_npu_priv')]
    if '#define NPU_EN7581_7996_INODE_DATA_SIZE' in source:
        types.insert(0, extract.macro(source, 'NPU_EN7581_7996_INODE_DATA_SIZE'))
    (directory / 'frame-types.inc').write_text('\n\n'.join(types))
    (directory / 'frame-send.inc').write_text(extract.function(source, 'airoha_npu_wlan_msg_send'))
    binary = directory / 'test'
    run(['gcc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
         '-Wno-sign-compare', '-fno-pie', '-no-pie', '-fsanitize=address,undefined',
         '-fno-sanitize-recover=all', '-I' + str(directory), HARNESS, '-o', binary],
        directory, 'build')
    return binary


def native_frames(frames, original):
    c = native.InodeClosure(native.ELF, native.exports())
    snapshot = c.snapshot()
    rows, negatives = [], []
    for selector in range(16):
        frame = next(row for row in frames if row['profile'] == 1 and row['api'] == 24
                     and row['selector'] == selector and row['input_bytes'] == 4)
        old = next(row for row in original if row['profile'] == 1 and row['api'] == 24
                   and row['selector'] == selector and row['input_bytes'] == 4)
        c.restore(snapshot)
        denied, _ = c.invoke_inode(bytes.fromhex(old['hex']), enforce=True, entry_only=True)
        assert denied['error'] == 'payload read 20+4 exceeds 12' and denied['arguments'] is None
        negatives.append(dict(selector=selector, error=denied['error'], declared_bytes=old['bytes']))
        c.restore(snapshot)
        row, _ = c.invoke_inode(bytes.fromhex(frame['hex']), enforce=True, entry_only=True)
        assert row['error'] is None and row['declared_bytes'] == 24
        assert row['arguments'] == [selector, 0x74737271, 0, 0, 0]
        assert [read['offset'] for read in row['payload_reads']] == [0, 20, 16, 12, 8]
        rows.append(row)
    return dict(entry_cases=rows, original_short_controls=negatives,
                firmware_sha256=native.CODE_SHA, data_sha256=native.DATA_SHA,
                ghidra_sha256=sha(native.GHIDRA), elf_sha256=sha(native.ELF),
                scope='Original wrapper stops at helper entry; no new selector helper execution or readiness claim.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--candidate-source', type=Path)
    parser.add_argument('--target-module', type=Path,
                        help='Also execute the sender in a verified packaged AArch64 module')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-inode-frame-20261001' / args.name
    assert not dest.exists(), 'Choose a fresh result name'
    dest.mkdir(parents=True)
    current = replay(dest)
    tested = args.candidate_source.resolve() if args.candidate_source else current
    assert tested.is_relative_to(ROOT)
    original = subprocess.check_output(['git', '-C', ROOT, 'show',
                                       'a6105f3:' + str(PATCH.relative_to(ROOT))])
    old = dest / 'original' / DRIVER
    old.parent.mkdir(parents=True)
    shutil.copy2(FIXTURES / 'provider-upstream.c', old)
    prior_patch = dest / 'original.patch'
    prior_patch.write_bytes(original)
    run(['git', 'apply', '--include=' + DRIVER, prior_patch], dest / 'original', 'apply')
    before, after = old.read_text(), tested.read_text()
    old_binary = build(before, dest / 'before')
    old_output = run([old_binary, '--original'], dest / 'before', 'frames')
    new_binary = build(after, dest / 'after')
    new_output = run([new_binary], dest / 'after', 'frames')
    originals = [json.loads(line) for line in old_output.stdout.splitlines()]
    frames = [json.loads(line) for line in new_output.stdout.splitlines()]
    assert len(originals) == len(frames) == 1056
    assert 'PASS frames=1056 auxiliary=30 original=0' in new_output.stderr
    native_result = native_frames(frames, originals)
    target_result = None
    if args.target_module:
        from inode_frame_target import verify
        module = args.target_module.resolve()
        assert module.is_relative_to(ROOT)
        target_result = verify(module, frames)
    mutants = {
        'short-native-span': after.replace('(4 * sizeof(u32))', '(3 * sizeof(u32))'),
        'omit-profile-padding': after.replace('func_id == WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR &&', '0 &&'),
        'pad-other-commands': after.replace('func_id == WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR &&', '1 &&'),
        'pad-other-profiles': after.replace('priv->txbuf_min_size == NPU_EN7581_7996_TX_CHECK_SIZE &&',
                                           'priv->txbuf_min_size != 0xffffffffU &&'),
        'copy-padded-length': after.replace('memcpy(wlan_data->d, data, data_len);',
                                           'memcpy(wlan_data->d, data, len - sizeof(*wlan_data));'),
    }
    killed = []
    for name, source in mutants.items():
        assert source != after
        binary = build(source, dest / name)
        run([binary], dest / name, 'frames', expected=None)
        killed.append(name)
    paths = [tested, current, old, HARNESS, Path(__file__), PATCH,
             ROOT / 'firmware/source-lock.json', FIXTURES / 'provenance.json',
             native.GHIDRA, native.ELF, Path(native.__file__)]
    if args.target_module:
        paths += [args.target_module.resolve(), ROOT / 'tests/npu/inode_frame_target.py']
    receipt = dict(passed=True, staged_candidate=bool(args.candidate_source),
                   cases=len(frames), auxiliary_cases=30, profiles=3, original_controls=16,
                   native=native_result, target=target_result,
                   rejected_mutants=killed,
                   sanitizers=dict(address=True, undefined=True, leak=True),
                   inputs={str(path.relative_to(ROOT)): sha(path) for path in paths},
                   artifacts={str(path.relative_to(ROOT)): sha(path) for path in sorted(dest.rglob('*')) if path.is_file()},
                   limits=['Provider send C runs with modeled allocator and mailbox transport.',
                           'The actual original wrapper consumes emitted provider bytes; helper bodies are not run.',
                           'MT7996 short INODE payloads are zero-extended; other profiles/commands retain their lengths.',
                           'No physical coherent storage, mailbox completion, full attachment, image or router proof.'])
    (dest / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=len(frames), native_entries=16, original_controls=16,
                          mutants=len(killed), receipt=str((dest / 'result.json').relative_to(ROOT)))))


if __name__ == '__main__':
    main()
