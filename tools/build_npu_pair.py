#!/usr/bin/env python3
"""Compile and assemble the checked native pair. Does not package or flash it."""
import argparse
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'tests/npu'))
import npu_image as image
import test_bootstrap_v2_composition as composition
import test_cold_page_native as pages
import test_rx_stats as stats
import test_cold_packet_native as packets
import tx_wire_native as tx
import descriptor_wire_native as descriptor
import tx_buffer_wire_native as txbuf
import rx_event_wire_native as rx_event
import txdone_wire_native as desc10
import rx_pcie_wire_native as rx_pcie
import pcie_tail_wire_native as pcie_tail
import test_startup_native as startup
import test_admission_native as admission
from test_barrier_workers import SITES as WORKER_SITES
from test_barrier_core5 import SITES as CORE5_SITES


def source_inputs():
    sources = {Path(__file__), ROOT / 'tools/npu_image.py'}
    for directory, patterns in ((ROOT / 'firmware/npu', ('*.c', '*.h')), (ROOT / 'tests/npu', ('*.c', '*.S', '*.ld'))):
        for pattern in patterns:
            sources.update(directory.glob(pattern))
    sources.update(Path(module.__file__).resolve() for module in list(sys.modules.values())
                   if getattr(module, '__file__', None) and Path(module.__file__).resolve().is_relative_to(ROOT / 'tests/npu'))
    return {str(path.relative_to(ROOT)): image.sha(path.read_bytes()) for path in sorted(sources)}


def hook_plan(code, components):
    symbols = {name: image.symbols(path) for name, path in components.items()}
    hooks = {}
    def put(site, component, symbol=None, before=None, length=4, rd=0, target=None):
        actual = code[site - image.CODE:site - image.CODE + length].hex()
        if before is not None:
            image.require(actual == before, 'profile-preimage')
        hooks[site] = dict(site=site, component=component, symbol=symbol,
                           before=actual, target=target if target is not None else symbols[component][symbol], rd=rd)
    for site, (name, expected) in {**startup.SITES, **admission.HOOKS,
                                  0x84003f2e: ('npu_emulation_mailbox_register', 'eff06fb2')}.items():
        put(site, 'base', name, expected)
    for site, (hart, kind, expected, *_) in WORKER_SITES.items():
        put(site, 'base', f'gate_core{hart}_{kind}', expected)
    for site, (name, expected) in CORE5_SITES.items():
        put(site, 'base', name, expected)
    put(0x840053a6, 'base', 'npu_emulation_gdma_copy', '93174500')
    reset, allocator = composition.reset, composition.allocator
    put(reset.CALL, 'reset', 'npu_emulation_allocator_reset_prepare', reset.PREIMAGES[reset.CALL], rd=1)
    put(reset.SKIP, 'reset', before=reset.PREIMAGES[reset.SKIP], target=0x840052e4)
    put(allocator.GETTER, 'allocator', 'npu_emulation_allocator_startup_dispatch', '13070008')
    for site, (kind, expected) in composition.bridge.GUARDS.items():
        put(site, 'bridge', 'npu_emulation_bridge_' + kind + '_guard', expected)
    for site, (name, expected) in composition.txdone.SITES.items():
        put(site, 'txdone', name, expected)
    for site, (name, _) in composition.order.SITES.items():
        put(site, 'order', 'npu_emulation_ring_' + name)
    for site, name in composition.headers.SITES.items():
        put(site, 'headers', 'npu_emulation_' + name)
    for site, name in composition.egress.SITES.items():
        put(site, 'egress', 'npu_emulation_egress_' + name)
    for site, name in composition.packets.SITES.items():
        put(site, 'packets', 'npu_emulation_srv6_' + name)
    for component, sites in (('cold-pages', pages.SITES), ('rx-stats', stats.SITES),
                             ('cold-packets', packets.SITES), ('cold-tx', tx.SITES),
                             ('cold-descriptor', descriptor.SITES)):
        for site, name in sites.items():
            put(site, component, name, length=6 if site == packets.GETTER else 4)
    for site, name in txbuf.SITES.items():
        put(site, 'cold-tx-buffer', name, length=txbuf.WIDTHS.get(site, 4))
    for site, name in rx_event.SITES.items():
        put(site, 'cold-rx-event', name)
    for site, name in desc10.SITES.items():
        put(site, 'cold-txdone', name, length=desc10.WIDTHS.get(site, 4))
    for site, name in rx_pcie.SITES.items():
        put(site, 'cold-rx-pcie', name)
    for site, name in pcie_tail.SITES.items():
        put(site, 'cold-pcie-tail', name, length=pcie_tail.WIDTHS.get(site, 4))
    return sorted(hooks.values(), key=lambda row: row['site'])


def build(destination, *, firmware_directory=None):
    destination = destination.resolve()
    image.require(any(destination.is_relative_to(ROOT / name) for name in ('.local', '.build')), 'output-outside-build-storage')
    image.require(not destination.exists(), 'output-exists')
    firmware_directory = (firmware_directory or composition.CODE_INPUT.parent).resolve()
    code_input, data_input = [firmware_directory / name for name in
                             ('en7581_MT7996_npu_rv32.bin', 'en7581_MT7996_npu_data.bin')]
    image.require(firmware_directory.is_relative_to(ROOT), 'input-outside-workspace')
    original_code, original_data = code_input.read_bytes(), data_input.read_bytes()
    image.require((image.sha(original_code), image.sha(original_data)) == (image.CODE_SHA, image.DATA_SHA),
                  'wrong-original-pair')
    destination.mkdir(parents=True)
    inputs = source_inputs()
    paths, parts = composition.build(destination=destination / 'components', negative_controls=False)
    page_dir, rx_dir, packet_dir, tx_dir, descriptor_dir = [destination / name for name in ('page', 'rx', 'packet', 'tx', 'descriptor')]
    for path in (page_dir, rx_dir, packet_dir, tx_dir, descriptor_dir):
        path.mkdir()
    page_path = pages.build(page_dir, parts)
    rx_path = stats.build(rx_dir, parts, page_path)
    packet_path = packets.build(packet_dir, parts, rx_path)
    tx_path = tx.build(tx_dir, parts, page_path)
    descriptor_path = descriptor.build(descriptor_dir, parts, page_path, packet_path, tx_path)
    txbuf_dir = destination / 'tx-buffer'
    txbuf_dir.mkdir()
    txbuf_path = txbuf.build(txbuf_dir, parts, descriptor_path)
    rx_event_dir = destination / 'rx-event'
    rx_event_dir.mkdir()
    rx_event_path = rx_event.build(rx_event_dir, parts, txbuf_path)
    desc10_dir = destination / 'desc10'
    desc10_dir.mkdir()
    desc10_path = desc10.build(desc10_dir, parts, packet_path, rx_event_path)
    rx_pcie_dir = destination / 'rx-pcie'
    rx_pcie_dir.mkdir()
    rx_pcie_path = rx_pcie.build(rx_pcie_dir, parts, desc10_path, rx_event_path, packet_path)
    tail_dir = destination / 'pcie-tail'
    tail_dir.mkdir()
    tail_path = pcie_tail.build(tail_dir, parts, rx_pcie_path, desc10_path, rx_event_path, packet_path, tx_path)
    components = parts | {'cold-pages': page_path, 'rx-stats': rx_path, 'cold-packets': packet_path,
                          'cold-tx': tx_path, 'cold-descriptor': descriptor_path, 'cold-tx-buffer': txbuf_path,
                          'cold-rx-event': rx_event_path, 'cold-txdone': desc10_path,
                          'cold-rx-pcie': rx_pcie_path, 'cold-pcie-tail': tail_path}
    layout = composition.memory_layout(components, original_code_bytes=len(original_code), negative_controls=False)
    hooks = hook_plan(original_code, components)
    edits = [dict(site=0x8401b230, before=struct.pack('<I', 58879).hex(),
                  after=struct.pack('<I', composition.layout.LAYOUT_HYPOTHESIS).hex(), purpose='checked bridge extent')]
    initializers = [dict(address=startup.STARTUP, bytes=struct.pack('<16I', startup.MAGIC, 1, 64, *([0] * 13)).hex(),
                         purpose='fresh startup descriptor')]
    slots = [dict(address=composition.native.PLAN, bytes=48, purpose='validated real loader memory/request plan'),
             dict(address=composition.boot.SESSION, bytes=20, purpose='fresh V2 session storage'),
             dict(address=composition.boot.LOADER, bytes=8, purpose='fresh per-boot identity')]
    code, data, manifest = image.assemble(original_code, original_data, components, hooks, edits, initializers, slots)
    image.require(source_inputs() == inputs, 'sources-changed-during-build')
    manifest['inputs'] = inputs | {str(code_input.relative_to(ROOT)): image.sha(original_code),
                                  str(data_input.relative_to(ROOT)): image.sha(original_data)}
    manifest['memory_layout'] = layout
    manifest['host_inputs'] = {str(path.relative_to(ROOT)): image.sha(path.read_bytes()) for path in paths[:2]}
    manifest['symbol_files'] = {name: str(path.relative_to(ROOT)) for name, path in components.items()}
    manifest['host_files'] = [str(path.relative_to(ROOT)) for path in paths[:2]]
    (destination / 'CODE.bin').write_bytes(code)
    (destination / 'DATA.bin').write_bytes(data)
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return destination, manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--firmware-directory', type=Path,
                        help='Pinned original MT7996 pair directory inside the workspace')
    args = parser.parse_args()
    path, manifest = build(args.output, firmware_directory=args.firmware_directory)
    print(json.dumps(dict(output=str(path), code=manifest['code'], data=manifest['data'], hooks=len(manifest['hooks']),
                          loader_provisioned=False)))


if __name__ == '__main__':
    main()
