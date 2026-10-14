"""Read-only capture of a real emulated prefix; restoration is diagnostic only."""
import hashlib
import json
from pathlib import Path

import unicorn

ROOT = Path(__file__).resolve().parents[2]


def capture(h, destination, request, inputs, *, origin):
    destination = destination.resolve()
    assert any(destination.is_relative_to(ROOT / name) for name in ('.local', '.build'))
    destination.mkdir()
    regions = []
    for index, (begin, end, permissions) in enumerate(h.cpu.mem_regions()):
        data = bytes(h.cpu.mem_read(begin, end - begin + 1))
        name = f'region-{index:03d}.bin'
        with (destination / name).open('xb') as stream:
            stream.write(data)
        regions.append(dict(begin=begin, end=end, permissions=permissions, file=name,
                            sha256=hashlib.sha256(data).hexdigest()))
    context = h.cpu.context_save()
    data = bytes(context)
    with (destination / 'cpu-context.bin').open('xb') as stream:
        stream.write(data)
    record = dict(format='npu-native-prefix-diagnostic-v1', origin=origin,
        request=request, request_address=h.request_address, unicorn_version=unicorn.__version__,
        context=dict(file='cpu-context.bin', sha256=hashlib.sha256(data).hexdigest(),
                     size=context.size, arch=context.arch, mode=context.mode),
        regions=regions, inputs=inputs,
        observer={name: getattr(h, name) for name in
                  ('hart', 'clear_count', 'l2_clear_active', 'l2_writes', 'last_csr') if hasattr(h, name)},
        fresh_loader_allocator_caller_proof=False,
        limits=['Captured state comes from the named producing run, without native writes during capture.',
                'Restored state is a diagnostic/negative-control fixture, not a fresh loader/allocator/caller run.',
                'DMA/backing, MMIO and scheduling remain modeled; no physical or hardware acceptance.'])
    with (destination / 'snapshot.json').open('x') as stream:
        stream.write(json.dumps(record, indent=2) + '\n')
    return destination / 'snapshot.json'
