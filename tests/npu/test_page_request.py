#!/usr/bin/env python3
"""Check production provider admission for native page/indication counts."""
import argparse
import json
from pathlib import Path
import re
import struct
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
import test_inode_provider_frame as frame

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / 'tests/npu/page-request-harness.c'


def target_verify(module):
    from inode_frame_target import Sender
    sender = Sender(module)
    cases = rejected = 0
    for profile in range(3):
        for selector in range(16):
            selected = 5 <= selector <= 8
            limit = (256, 512, 1024, 1536)[selector - 5] if selected else 1024
            for alias in (0, 16):
                for command in (1, 19):
                    for count in (0, 1, limit - 1, limit, limit + 1, 0x80000000, 0xffffffff):
                        for length in (0, 1, 2, 3, 4, 8, 12, 16, 248):
                            payload = (struct.pack('<I', count) + b'\xa5' * 244)[:length]
                            deny = profile == 1 and command == 1 and selected and (length < 4 or not count or count > limit)
                            result = sender.call(profile, command, selector + alias, payload, input_offset=1)
                            if deny:
                                assert result == -22 and sender.allocations == sender.frees == sender.sends == 0
                                rejected += 1
                            else:
                                assert result == 0 and sender.allocations == sender.frees == sender.sends == 1
                                assert sender.packet == struct.pack('<II', 0x10 | selector, command) + payload
                            cases += 1
    return dict(passed=True, cases=cases, rejected=rejected, module_sha256=frame.sha(module),
                function_bytes=sender.size, function_offset=hex(sender.entry),
                readonly_sections=[dict(name=name, bytes=len(data), sha256=frame.hashlib.sha256(data).hexdigest())
                                   for _, data, name in sender.readonly.values()],
                scope='Actual packaged AArch64 instructions and ELF readonly table;kernel allocation/transport/free modeled.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--candidate-source', type=Path)
    parser.add_argument('--target-module', type=Path)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-page-rings-20261001' / args.name
    assert not dest.exists(), 'Choose a fresh result name'
    dest.mkdir(parents=True)
    replayed = frame.replay(dest)
    source = args.candidate_source.resolve() if args.candidate_source else replayed
    assert source.is_relative_to(ROOT)
    current = source.read_text()
    with patch.object(frame, 'HARNESS', HARNESS):
        binary = frame.build(current, dest / 'provider')
        result = json.loads(frame.run([binary], dest / 'provider', 'requests').stdout)
        mutants = {
            'omit-profile-gate': current.replace('func_id == WLAN_FUNC_SET_WAIT_DESC)', '0)'),
            'omit-zero-count': current.replace('!ring_size || ring_size > limit', 'ring_size > limit'),
            'allow-one-too-many': current.replace('ring_size > limit', 'ring_size > limit + 1'),
            'omit-selector-alias': current.replace('switch (ifindex & 0xf)', 'switch (ifindex)'),
            'guard-other-profiles': current.replace('priv->txbuf_min_size == NPU_EN7581_7996_TX_CHECK_SIZE &&\n\t    func_id == WLAN_FUNC_SET_WAIT_DESC',
                                                    'priv->txbuf_min_size != 0xffffffffU &&\n\t    func_id == WLAN_FUNC_SET_WAIT_DESC'),
            'guard-other-commands': current.replace('func_id == WLAN_FUNC_SET_WAIT_DESC)', 'func_id == WLAN_FUNC_SET_WAIT_TX_RING_PCIE_ADDR)'),
        }
        killed = []
        for name, mutated in mutants.items():
            assert mutated != current
            binary = frame.build(mutated, dest / name)
            frame.run([binary], dest / name, 'requests', expected=None)
            killed.append(name)
    result.update(rejected_mutants=killed, sanitizers=dict(address=True, undefined=True, leak=True),
                  inputs={str(p.relative_to(ROOT)): frame.sha(p) for p in
                          (source, replayed, HARNESS, Path(__file__), Path(frame.__file__),
                           frame.PATCH, ROOT / 'firmware/source-lock.json')},
                  artifacts={str(p.relative_to(ROOT)): frame.sha(p) for p in sorted(dest.rglob('*')) if p.is_file()},
                  limits=['Actual provider C; allocation and transport are modeled.',
                          'Selected MT7996 DESC5/6/7/8 request counts only; not native readiness or physical ownership.'])
    if args.target_module:
        module = args.target_module.resolve()
        assert module.is_relative_to(ROOT)
        result['target'] = target_verify(module)
        result['inputs'].update({str(p.relative_to(ROOT)): frame.sha(p) for p in
                                 (module, ROOT / 'tests/npu/inode_frame_target.py')})
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result | {'inputs': len(result['inputs']), 'artifacts': len(result['artifacts'])}))


if __name__ == '__main__':
    main()
