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
    parts = {key: value for key, value in files.items() if key not in ('cold-pages', 'rx-stats', 'cold-packets', 'cold-tx')}
    h = factory(paths, parts)
    h.install(files['cold-pages'])
    h.install_rx(files['rx-stats'])
    h.install_packet(files['cold-packets'])
    tx_wire.install(h, files['cold-tx'])
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
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-raw-pair-20261010' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    pair = args.pair.resolve()
    early_controls = boot_controls(pair)
    from cold_wire_native import ColdProviderRequest
    from cold_client_native import exchange as cold_exchange
    request = 0x83000000
    h, paths, files, manifest = load(pair, factory=partial(ColdProviderRequest, request=request))
    sources = {Path(__file__), ROOT / 'tools/npu_image.py', ROOT / 'tools/build_npu_pair.py'}
    sources.update(Path(module.__file__).resolve() for module in list(sys.modules.values())
                   if getattr(module, '__file__', None) and Path(module.__file__).resolve().is_relative_to(ROOT / 'tests/npu'))
    inputs = manifest['inputs'] | {str(path.relative_to(ROOT)): composition.sha(path) for path in sources}
    inputs |= {str(path.relative_to(ROOT)): composition.sha(path) for path in
               (pair / 'CODE.bin', pair / 'DATA.bin', pair / 'manifest.json', *paths, *files.values())}
    assert all(composition.sha(ROOT / path) == digest for path, digest in inputs.items()), 'stale-build-input'
    identity = composition.control.BOOT
    loader = provision(h, identity, request=request)
    h.hart = 0
    h.cpu.context_restore(h.fresh)
    assert h.reset() == 0x8400420a
    host = composition.control.Host(paths)
    assert composition.control.exchange(host, h)[0] == composition.control.ACCEPTED
    composition.boot.setup(h, run_clear=True)
    composition.control.advance(host, h)
    h.finish_coordinator()
    workers = [h.worker(hart) for hart in range(1, 8)]
    h.on_core0()
    assert composition.control.exchange(host, h)[0] == composition.control.ACCEPTED
    denied = h.message([0x1a, 1, 512])
    assert denied['flags'] == 3 and not denied['callbacks']
    frames = []
    def command(*words):
        row = cold_exchange(host, h, words)
        frames.append(row)
        return row
    for words in ((0x1f, 0x100, 0x20000000), (0x1f, 0x101, 0x100000), (0x30, 10, 0), (0x10, 14, 2)):
        command(*words)
    prefix = []
    for selector, count in ((0, 1536), (2, 1024)):
        row = h.invoke_packet(selector, count, transport=lambda: command(0x10 | selector, 1, count))
        tx.stats.expected(row, 1, count, 1, 250, expected_active=0)
        prefix.append(row)
        print(json.dumps(dict(raw_rx=selector, claimed=row['claimed'])), flush=True)
    packet_before = bytes(h.cpu.mem_read(h.packet.symbols['npu_emulation_packet_state'], 2076))
    page_rows, page_total = [], 0
    for selector, count in tx.pages.COUNTS.items():
        page_total += count
        command(0x10 | selector, 0, 0x200d45a0 + (selector - 5) * 16)
        row = h.invoke(selector, count, transport=lambda: command(0x10 | selector, 1, count))
        tx.pages.check(row, 1, page_total, count, page_total, expected_active=0)
        for index in range(count):
            ident = page_total - count + index
            assert struct.unpack('<4I', h.cpu.mem_read(row['ring'] + index * 16, 16)) == (
                0x90c0e000 + ident * 128, 0x800100, ident << 16, 0)
        page_rows.append(row)
    assert bytes(h.cpu.mem_read(h.packet.symbols['npu_emulation_packet_state'], 2076)) == packet_before
    print(json.dumps(dict(raw_ba_claims=page_total, packet_state_unchanged=True)), flush=True)
    for words in ((0x18, 0, 0x2000a040), (0x18, 1, 1536), (0x13, 19, 0x2000a050),
                  (0x10, 19, 0x200d4420), (0x12, 19, 0x200d4450), (0x10, 33, 8192)):
        command(*words)
    assert h.get32(h.rv.symbols['npu_emulation_cold_setup_state'] + 8) == 131071
    assert h.get32(h.tx.symbols['npu_emulation_tx_state'] + 24) == 11 and h.get32(ADM + 4) == 0
    # Later TXDONE is still a separately declared modeled lease until its full
    # host/INODE/physical contract is implemented. It cannot reinitialize TX.
    h.put32(ADM + 4, 1)
    h.cpu.mem_write(PAYLOAD, struct.pack('<3I', 0x10, 22, TXFREE) + bytes(12))
    assert h.direct(SET_CALLBACKS[22], PAYLOAD) == 1
    h.put32(tx.SRAM + 0x3974, 0x87654321)
    core = h.packet.symbols['npu_emulation_packet_state']
    before = list(struct.unpack('<519I', h.cpu.mem_read(core, 2076)))
    initial = h.snapshot()
    count = 16 if args.quick else 512
    want, _, _ = tx.oracle(h, count)
    row = h.invoke_done(count)
    tx.check_success(h, before, want, row, count)
    nominal = row
    controls = []
    for mode in ('denied', 'partial-pool', 'claim-fault', 'head-changed', 'release-fault',
                 'denied-skb19', 'before-ready-bitmap', 'before-ready-plan'):
        h.restore(initial)
        if mode == 'partial-pool':
            h.cpu.mem_write(tx.packets.TAIL, struct.pack('<H', (before[3] + 18) % 16384))
        seeded = h.snapshot()
        observed = h.invoke_done(32, mode)
        actual = {base: bytes(h.cpu.mem_read(base, size)) for base, size in tx.SPACES}
        actual_state = bytes(h.cpu.mem_read(core, 2076))
        h.restore(seeded)
        want, state = tx.check_control(h, mode, before, 32, observed)
        assert actual == want and actual_state == state, ('raw-fault-oracle', mode)
        controls.append(observed)
        print(json.dumps(dict(raw_txdone_control=mode, passed=True)), flush=True)
    assert bytes(h.cpu.mem_read(image.CODE, 0x1dde0)) == (pair / 'CODE.bin').read_bytes()[:0x1dde0]
    assert all(composition.sha(ROOT / path) == digest for path, digest in inputs.items()), 'inputs-changed-during-replay'
    result = dict(passed=True, full_nominal=not args.quick, raw_pair=True, post_load_elf_injection=False,
                  hooks=74, loader_publication=loader, workers=workers, prefix=prefix, txdone=nominal,
                  authenticated_cold_prefix=frames, initial_test_active_writes=False,
                  initial_direct_owner_init=False, later_txdone_lease_modeled=True,
                  independent_pages=page_rows, boot_controls=early_controls, controls=controls,
                  strict_denial=denied, pair_manifest_sha256=image.sha((pair / 'manifest.json').read_bytes()),
                  inputs=inputs,
                  limits=['Actual raw CODE/DATA copies, native reset/all-hart parking and selected RX/TXDONE bodies.',
                          'Initial setup uses the actual cold-client protocol; provider publication/backing/grants/delivery remain modeled.',
                          'Only the later TXDONE lease/ring metadata are directly modeled; complete strict host/INODE setup remains open.',
                          'Strict full setup, real loader publication, hot lifecycle and physical drains/clients remain open.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, full_nominal=not args.quick, claims=nominal['claimed'], raw_pair=True,
                          boot_controls=len(early_controls), txdone_controls=len(controls))))


if __name__ == '__main__':
    main()
