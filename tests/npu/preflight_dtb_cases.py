#!/usr/bin/env python3
"""Extract compiled-DTB fixtures; resource ends are inclusive, as in Linux.

Expected results are the fixed bootmem regression matrix, not a Python version
of provider preflight. Absent firmware-name stays null: the generic SoC defaults
are airoha/en7581_npu_rv32.bin and en7581_npu_data.bin.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from test_txbuf_dtbs import BUILD, PROFILES, ROOT, digest, properties

OUTPUT = ROOT / 'research/checkpoints/2026-09-06-npu-preflight/dtb-cases.json'
NPU_COMPATIBLE = 'airoha,en7581-npu'
REQUIRED_RESOURCES = {'binary', 'pkt', 'tx-pkt', 'tx-bufid', 'ba'}


def raw(tree, node, name):
    if name not in tree[node]:
        raise ValueError(f'{node}: missing {name}')
    return bytes.fromhex(tree[node][name])


def strings(tree, node, name):
    value = raw(tree, node, name)
    if not value.endswith(b'\0') or not all(value[:-1].split(b'\0')):
        raise ValueError(f'{node}: invalid {name} string list')
    return value[:-1].decode('utf-8').split('\0')


def cells(tree, node, name):
    value = raw(tree, node, name)
    if not value or len(value) % 4:
        raise ValueError(f'{node}: invalid {name} cells')
    return struct.unpack(f'>{len(value) // 4}I', value)


def scalar(tree, node, name):
    value = cells(tree, node, name)
    if len(value) != 1:
        raise ValueError(f'{node}: ambiguous {name}')
    return value[0]


def resource(tree, node):
    parent = node.rsplit('/', 1)[0] or '/'
    address_cells = scalar(tree, parent, '#address-cells')
    size_cells = scalar(tree, parent, '#size-cells')
    if address_cells not in (1, 2) or size_cells not in (1, 2):
        raise ValueError(f'{parent}: unsupported reg cell widths')
    if parent != '/' and raw(tree, parent, 'ranges'):
        raise ValueError(f'{parent}: non-identity address translation')
    reg = cells(tree, node, 'reg')
    if len(reg) != address_cells + size_cells:
        raise ValueError(f'{node}: expected one complete reg entry')
    encoded = struct.pack(f'>{len(reg)}I', *reg)
    start = int.from_bytes(encoded[:address_cells * 4], 'big')
    size = int.from_bytes(encoded[address_cells * 4:], 'big')
    if size == 0:
        raise ValueError(f'{node}: empty resource')
    return {'start': start, 'end': start + size - 1, 'size': size}


def npu_properties(tree):
    nodes = [node for node, props in tree.items() if 'compatible' in props
             and NPU_COMPATIBLE in strings(tree, node, 'compatible')]
    if len(nodes) != 1:
        raise ValueError(f'expected one NPU node, found {len(nodes)}')
    npu = nodes[0]
    names = strings(tree, npu, 'memory-region-names')
    handles = cells(tree, npu, 'memory-region')
    if len(names) != len(handles) or len(set(names)) != len(names):
        raise ValueError(f'{npu}: ambiguous memory-region names/handles')
    missing = REQUIRED_RESOURCES - set(names)
    if missing:
        raise ValueError(f'{npu}: missing resources {sorted(missing)}')
    if len(set(handles)) != len(handles):
        raise ValueError(f'{npu}: aliased memory regions')

    targets = {}
    for node, props in tree.items():
        values = [scalar(tree, node, key) for key in ('phandle', 'linux,phandle')
                  if key in props]
        if not values:
            continue
        handle = values[0]
        if len(set(values)) != 1 or handle in (0, 0xffffffff) or handle in targets:
            raise ValueError(f'{node}: invalid or ambiguous phandle')
        targets[handle] = node

    resources = {}
    for name, handle in zip(names, handles):
        if handle not in targets:
            raise ValueError(f'{npu}: unresolved {name} phandle {handle:#x}')
        resources[name] = resource(tree, targets[handle])
    return {
        'compatible': strings(tree, npu, 'compatible'),
        'firmware_names': strings(tree, npu, 'firmware-name')
                          if 'firmware-name' in tree[npu] else None,
        'resources': resources,
    }


def cases():
    rows = []
    for variant in ('baseline', 'candidate'):
        for profile in PROFILES:
            dtb = BUILD / variant / (profile + '.dtb')
            rows.append({
                'label': f'{variant}/{profile}',
                'profile': profile,
                'variant': variant,
                'dtb_sha256': digest(dtb),
                **npu_properties(properties(dtb)),
                'expected_preflight_accept': variant == 'candidate' or profile == 'an7581-evb',
            })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true', help='compare without writing')
    args = parser.parse_args()
    rows = cases()
    encoded = (json.dumps(rows, indent=2) + '\n').encode('utf-8')
    if args.check:
        if args.output.read_bytes() != encoded:
            raise SystemExit(f'fixture regeneration differs: {args.output}')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    accepted = sum(row['expected_preflight_accept'] for row in rows)
    print(f'{len(rows)} cases: {accepted} accept, {len(rows) - accepted} reject; '
          f'{"verified" if args.check else "wrote"} {args.output}')


if __name__ == '__main__':
    main()
