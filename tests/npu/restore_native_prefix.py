"""Strict restoration of hash-bound native captures; never a fresh boot proof."""
from functools import partial
import hashlib
import json
from pathlib import Path

import unicorn
from cold_wire_native import ColdProviderRequest
import test_npu_raw_pair as raw

ROOT = raw.ROOT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(pair, snapshot, *, origin):
    pair, snapshot = pair.resolve(), snapshot.resolve()
    assert pair.is_relative_to(ROOT) and snapshot.is_relative_to(ROOT / '.local')
    record = json.loads(snapshot.read_bytes())
    assert record['format'] == 'npu-native-prefix-diagnostic-v1'
    assert record['fresh_loader_allocator_caller_proof'] is False
    assert record['origin'] == origin
    assert record['unicorn_version'] == unicorn.__version__
    for name, expected in record['inputs'].items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and path.is_file(), name
        assert digest(path) == expected, ('captured-input-drift', name)
    published = []
    for name in ('CODE-copied.bin', 'DATA-published.bin'):
        matches = [ROOT / path for path in record['inputs'] if Path(path).name == name]
        assert len(matches) == 1, name
        published.append(matches[0].read_bytes())
    h, _, _, manifest = raw.load(pair, factory=partial(
        ColdProviderRequest, request=record['request_address']), published=tuple(published))
    regions = [(item['begin'], item['end'], item['permissions']) for item in record['regions']]
    assert sorted(h.cpu.mem_regions()) == sorted(regions)
    assert sum(end - begin + 1 for begin, end, _ in regions) <= 32 * 1024 * 1024
    inputs = dict(record['inputs'])
    for name, expected in manifest['inputs'].items():
        assert name not in inputs or inputs[name] == expected, ('pair-input-drift', name)
        inputs[name] = expected
    inputs[str(snapshot.relative_to(ROOT))] = digest(snapshot)
    inputs[str(Path(__file__).resolve().relative_to(ROOT))] = digest(Path(__file__).resolve())
    memory = []
    for item in record['regions']:
        assert Path(item['file']).name == item['file']
        path = snapshot.parent / item['file']
        contents = path.read_bytes()
        assert len(contents) == item['end'] - item['begin'] + 1
        assert digest(path) == item['sha256']
        inputs[str(path.relative_to(ROOT))] = digest(path)
        memory.append((item['begin'], contents))
    info = record['context']
    assert Path(info['file']).name == info['file']
    path = snapshot.parent / info['file']
    contents = path.read_bytes()
    context = h.cpu.context_save()
    assert (context.size, context.arch, context.mode) == (info['size'], info['arch'], info['mode'])
    assert len(contents) == context.size and digest(path) == info['sha256']
    inputs[str(path.relative_to(ROOT))] = digest(path)
    restored = type(context).__new__(type(context))
    restored.__setstate__((contents, context.size, context.arch, context.mode))
    observer = {}
    for name, value in record['observer'].items():
        assert name in ('hart', 'clear_count', 'l2_clear_active', 'l2_writes', 'last_csr'), (
            'unknown-observer-field', name)
        observer[name] = tuple(value) if name == 'last_csr' and value is not None else value

    def restore():
        for begin, contents_ in memory:
            h.cpu.mem_write(begin, contents_)
        h.cpu.context_restore(restored)
        for name, value in observer.items():
            setattr(h, name, value)
        h.unmodeled = None
        h.check_hooks()

    restore()
    return h, restore, record, inputs
