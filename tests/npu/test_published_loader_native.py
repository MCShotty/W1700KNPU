#!/usr/bin/env python3
"""Native raw boot from actual-C copied CODE and published DATA readback."""
import argparse
from functools import partial
import json
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
import test_npu_raw_pair as raw
from test_provider_plan_native import ProviderRequest
from test_bootstrap_native import BOOT, PLAN, ADM
from emulation_layout import STATE

ROOT = raw.ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--publication', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    dest = ROOT / '.local/npu-loader-publish-20261010' / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    published = args.publication.resolve()
    code_path, data_path = published / 'CODE-copied.bin', published / 'DATA-published.bin'
    code, data = code_path.read_bytes(), data_path.read_bytes()
    plan, identity = data[0x6300:0x6330], data[0x63a0:0x63a8]
    request, size = struct.unpack('<2I', plan[40:48])
    assert size == 256 and request != raw.composition.native.REQUEST and any(identity)
    h, paths, _, manifest = raw.load(args.pair.resolve(), factory=partial(ProviderRequest, request=request),
                                      published=(code, data))
    # No synthetic plan/identity writes here: use the actual publisher readback.
    assert bytes(h.cpu.mem_read(PLAN, 48)) == plan
    assert bytes(h.cpu.mem_read(raw.composition.boot.LOADER, 8)) == identity
    h.hart = 0
    h.cpu.context_restore(h.fresh)
    assert h.reset() == 0x8400420a
    assert bytes(h.cpu.mem_read(BOOT + 32, 48)) == plan
    assert bytes(h.cpu.mem_read(raw.composition.boot.SESSION, 8)) == identity
    denied = h.message([0x30, 10, 0], address=raw.composition.native.REQUEST)
    assert denied['flags'] == 3 and not denied['reads'] and not denied['callbacks']
    host = raw.composition.control.Host(paths)
    assert raw.composition.control.exchange(host, h)[0] == raw.composition.control.ACCEPTED
    version = h.message([0x30, 10, 0])
    assert version['flags'] == 7 and version['words'][2] == 0x457
    setup = raw.composition.boot.setup(h, run_clear=True)
    raw.composition.control.advance(host, h)
    h.finish_coordinator()
    workers = [h.worker(hart) for hart in range(1, 8)]
    h.on_core0()
    assert raw.composition.control.exchange(host, h)[0] == raw.composition.control.ACCEPTED
    parked = [h.get32(STATE + 20 + 4 * hart) for hart in range(8)]
    assert parked == [1] * 8 and h.get32(ADM + 4) == 0
    strict = [h.message(frame) for frame in ([0x10, 1, 1536], [0x12, 1, 1024], [0x1a, 1, 512])]
    assert all(row['flags'] == 3 and not row['callbacks'] for row in strict)
    h.check_hooks()
    inputs = manifest['inputs'] | {str(p.relative_to(ROOT)): raw.composition.sha(p) for p in
                                  (code_path, data_path, Path(__file__), ROOT / 'tests/npu/test_npu_raw_pair.py',
                                   ROOT / 'tests/npu/test_provider_plan_native.py')}
    assert all(raw.composition.sha(ROOT / p) == digest for p, digest in inputs.items())
    result = dict(passed=True, actual_c_publication_readback=True, synthetic_plan_identity_writes=False,
                  raw_pair=True, post_load_elf_injection=False, request_base=hex(request), identity_hex=identity.hex(),
                  setup=setup, workers=workers, parked=parked, fixture_denial=denied, strict_denials=strict, inputs=inputs,
                  limits=['Actual C-copy/publication bytes feed native raw startup; no post-loader ELF or synthetic metadata overwrite.',
                          'Linux firmware/OF/RNG/I/O/allocation and native backing/IRQ inputs remain modeled; not physical containment or full strict setup.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, actual_c_publication=True, harts=8, request_base=hex(request))))


if __name__ == '__main__':
    main()
