#!/usr/bin/env python3
"""Native execution from assembled CODE/DATA, without post-load ELF injection."""
import argparse
from functools import partial
import json
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import npu_image as image
import test_cold_txdone_native as tx
import test_bootstrap_v2_composition as composition
import tx_wire_native as tx_wire
from test_bootstrap_native import Bootstrap, ADM, PLAN
from test_firmware_memory_layout import STACK_TOPS
from test_firmware_mailbox_dispatch import PAYLOAD
from test_mt7996_bootstrap_sequence import SET_CALLBACKS, expected, TXFREE
from unicorn import riscv_const as r


def load(pair, *, factory=tx.TxPackets, published=None):
    manifest = json.loads((pair / 'manifest.json').read_bytes())
    code, data = (pair / 'CODE.bin').read_bytes(), (pair / 'DATA.bin').read_bytes()
    image.validate(code, data, manifest)
    if published is not None:
        copied_code, published_data = published
        assert copied_code == code and len(published_data) == len(data)
        expected = bytearray(data)
        for offset, size in ((0x6300, 48), (0x63a0, 8)):
            expected[offset:offset + size] = published_data[offset:offset + size]
        assert bytes(expected) == published_data, 'unexpected-runtime-publication'
        assert any(published_data[0x63a0:0x63a8])
        data = published_data
    files = {key: (ROOT / value).resolve() for key, value in manifest['symbol_files'].items()}
    host_files = [(ROOT / value).resolve() for value in manifest['host_files']]
    assert all(path.is_relative_to(pair.resolve()) for path in [*files.values(), *host_files])
    assert all(composition.sha(path) == manifest['components'][name]['sha256'] for name, path in files.items())
    assert all(composition.sha(ROOT / path) == digest for path, digest in manifest['host_inputs'].items())
    paths = host_files + [files['base']]
    parts = {key: value for key, value in files.items() if key not in ('cold-pages', 'rx-stats', 'cold-packets', 'cold-tx', 'cold-descriptor', 'cold-tx-buffer', 'cold-rx-event', 'cold-txdone', 'cold-rx-pcie')}
    h = factory(paths, parts)
    h.install(files['cold-pages'])
    h.install_rx(files['rx-stats'])
    h.install_packet(files['cold-packets'])
    tx_wire.install(h, files['cold-tx'])
    import descriptor_wire_native
    descriptor_wire_native.install(h, files['cold-descriptor'])
    import tx_buffer_wire_native
    tx_buffer_wire_native.install(h, files['cold-tx-buffer'])
    import rx_event_wire_native
    rx_event_wire_native.install(h, files['cold-rx-event'])
    import txdone_wire_native
    txdone_wire_native.install(h, files['cold-txdone'])
    import rx_pcie_wire_native
    rx_pcie_wire_native.install(h, files['cold-rx-pcie'])
    # Erase all ELF-loader effects, fixture plans and fixture identity before the
    # two raw copies. Retained Python objects supply only observer/symbol metadata.
    h.cpu.mem_write(image.CODE, b'\xcc' * image.CODE_LIMIT)
    h.cpu.mem_write(image.SRAM, b'\xcc' * 0x8000)
    h.cpu.mem_write(image.CODE, code)
    h.cpu.mem_write(image.SRAM, data)
    h.cpu.ctl_remove_cache(image.CODE, image.CODE + image.CODE_LIMIT)
    assert bytes(h.cpu.mem_read(image.CODE, len(code))) == code
    assert bytes(h.cpu.mem_read(image.SRAM, len(data))) == data
    for row in manifest['sections']:
        assert image.sha(bytes(h.cpu.mem_read(row['start'], row['end'] - row['start']))) == row['sha256']
    h.check_hooks()
    assert all(bytes(h.cpu.mem_read(slot['address'], slot['bytes'])) == bytes(slot['bytes'])
               for slot in manifest['loader_slots'] if published is None or slot['address'] == image.SRAM + 0x6380)
    return h, paths, files, manifest


def provision(h, identity, request=None):
    # Explicit synthetic provider publication, separate from the stored artifact.
    plan = composition.native.plan()
    if request is not None:
        plan[-1] = (request, 256)
    h.cpu.mem_write(PLAN, struct.pack('<12I', *[word for row in plan for word in row]))
    h.cpu.mem_write(composition.boot.LOADER, struct.pack('<2I', *identity))
    return dict(modeled=True, identity=list(identity), plan=plan, request_buffer=plan[-1])


def boot_controls(pair):
    results = []
    for mode in ('unprovisioned', 'identity-only', 'missing-identity', 'stale-session', 'short-txcheck', 'request-overlap'):
        h, paths, _, _ = load(pair)
        if mode != 'unprovisioned':
            provision(h, (0, 0) if mode == 'missing-identity' else composition.control.BOOT)
            if mode == 'identity-only':
                h.cpu.mem_write(PLAN, bytes(48))
            elif mode == 'short-txcheck':
                h.put32(PLAN + 12, 0x6800)
            elif mode == 'request-overlap':
                h.put32(PLAN + 40, composition.native.plan()[0][0])
            elif mode == 'stale-session':
                h.put32(composition.boot.SESSION + 8, 1)
        h.hart = 0
        h.cpu.context_restore(h.fresh)
        stopped = h.reset()
        assert stopped == h.rv.symbols['npu_emulation_startup_fault']
        assert h.get32(composition.native.STARTUP + 12) == 3
        assert h.get32(composition.native.STATE + 16) == 1
        assert h.get32(composition.native.BOOT + 4) == int(mode not in ('missing-identity', 'stale-session'))
        assert h.get32(composition.native.IRQ8) == 0 and h.clear_count == 0
        assert not any(event['kind'] == 'mmio-write' for event in h.mmio)
        results.append(dict(mode=mode, pc=hex(stopped), before_irq=True, clear_stores=0))
        print(json.dumps(dict(raw_boot_control=mode, passed=True)), flush=True)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--caller-receipt', type=Path, required=True,
                        help='Current actual allocator/caller receipt through DESC10 and RX PCIe')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-raw-pair-20261010' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    pair = args.pair.resolve()
    from raw_pair_retained import check
    result = check(pair, args.caller_receipt.resolve(), dest, boot_controls)
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=result['passed'], full_nominal=result['full_nominal'],
                          claims=result['retained_packet_claims'], raw_pair=True,
                          boot_controls=len(result['boot_controls']), txdone_controls=len(result['controls']))))


if __name__ == '__main__':
    main()
