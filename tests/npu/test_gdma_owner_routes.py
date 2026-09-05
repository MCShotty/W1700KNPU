#!/usr/bin/env python3
"""Known direct-call routes, not closure of all indirect firmware entry paths."""
from collections import deque
import json
import re

from test_firmware_stop_counterexample import ROOT, CODE_SHA, CORE_ROOTS
from test_barrier_protocol import digest

OUT = ROOT / 'research/checkpoints/2026-09-06-npu-copy'
EXPORT = ROOT / 'research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt'


def inventory():
    text = EXPORT.read_text()
    assert 'sha256=' + CODE_SHA in text and 'failed_decompilations=0' in text
    starts = list(re.finditer(r'^FUNCTION (\S+) @ ram:([0-9a-f]+)$', text, re.M))
    assert len(starts) == 427
    blocks = {int(row[2], 16): text[row.end():starts[index + 1].start() if index + 1 < len(starts) else len(text)]
              for index, row in enumerate(starts)}
    graph = {}
    for address, block in blocks.items():
        graph[address] = [(int(target, 16), int(site, 16)) for site, target in re.findall(
            r'^ram:([0-9a-f]+) (?:c\.jal |jal ra,|j |c\.j )0x([0-9a-f]+)$', block, re.M)
            if int(target, 16) in blocks and int(target, 16) != address]
    routes = []
    for hart, root in enumerate(CORE_ROOTS):
        queue = deque([(root, [])])
        visited = set()
        while queue:
            address, path = queue.popleft()
            if address in visited:
                continue
            visited.add(address)
            for target, site in graph[address]:
                route = path + [{'function': hex(address), 'call': hex(site), 'target': hex(target)}]
                if target == 0x840053a6:
                    routes.append({'hart': hart, 'route': route, 'immediate_caller': hex(address)})
                else:
                    queue.append((target, route))
    callers = {hex(address): [hex(site) for target, site in calls if target == 0x840053a6]
               for address, calls in graph.items() if any(target == 0x840053a6 for target, _ in calls)}
    assert set(callers) == {'0x8400e87a', '0x8400f0c4', '0x8400f528'}
    assert {(row['hart'], row['immediate_caller']) for row in routes} == {
        (2, '0x8400e87a'), (3, '0x8400f0c4'), (3, '0x8400f528')}
    return {'passed': True, 'code_sha256': CODE_SHA, 'export_sha256': digest(EXPORT.read_bytes()),
            'immediate_callers': callers, 'known_root_routes': routes,
            'scope': 'Direct calls/tail calls in 427 discovered functions only. Missing functions, computed MMIO, indirect callbacks and other masters are not excluded.'}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = inventory()
    (OUT / 'known-gdma-owners.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
