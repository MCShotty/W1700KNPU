"""Bind compiler frame measurements to exact normal objects, not whole-stack proof."""
import argparse
import hashlib
import json
from pathlib import Path

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_usage(text):
    rows, seen = [], set()
    for line in text.splitlines():
        fields = line.split('\t')
        assert len(fields) == 3, ('stack-usage-fields', line)
        location, size, qualifier = fields
        origin = location.rsplit(':', 2)
        assert len(origin) == 3 and origin[0] and origin[1].isdecimal() and int(origin[1]) > 0
        source, number, function = origin
        assert function and size.isdecimal() and qualifier == 'static', ('unbounded-stack-frame', line)
        key = source, function
        assert key not in seen, ('duplicate-stack-frame', key)
        seen.add(key)
        frame = int(size)
        assert frame % 16 == 0, ('rv32-stack-alignment', function, frame)
        rows.append(dict(source=source, line=int(number), function=function, bytes=frame,
                         qualifier=qualifier))
    assert rows, 'empty-stack-usage'
    return rows


def inventory(instrumented, reference, instrumented_archive=None):
    objects = {path.name: path for path in instrumented.glob('*.o')}
    expected = {path.name: path for path in reference.glob('*.o')}
    assert len(objects) == 22 and objects.keys() == expected.keys(), 'normal-object-set'
    inputs, frames = {}, []
    for name, path in sorted(objects.items()):
        original = expected[name]
        assert path.read_bytes() == original.read_bytes(), ('instrumentation-changed-object', name)
        usage = path.with_suffix('.su')
        rows = parse_usage(usage.read_text())
        with path.open('rb') as stream:
            elf = ELFFile(stream)
            assert elf['e_machine'] == 'EM_RISCV' and elf.elfclass == 32
            functions = {symbol.name for symbol in elf.get_section_by_name('.symtab').iter_symbols()
                         if symbol['st_info']['type'] == 'STT_FUNC' and symbol['st_size']}
        assert {row['function'] for row in rows} == functions, ('stack-function-coverage', name)
        frames.extend(dict(row, object=name) for row in rows)
        for item in (path, original, usage):
            inputs[str(item.relative_to(ROOT))] = digest(item)
    archive = instrumented_archive or instrumented / 'libw1700k-npu.a'
    original_archive = reference / 'libw1700k-npu.a'
    assert archive.read_bytes() == original_archive.read_bytes(), 'normal-archive-drift'
    for item in (archive, original_archive):
        inputs[str(item.relative_to(ROOT))] = digest(item)
    for item in (ROOT / 'firmware/npu').iterdir():
        if item.is_file() and (item.suffix in ('.c', '.h') or item.name == 'Makefile'):
            inputs[str(item.relative_to(ROOT))] = digest(item)
    inputs[str(Path(__file__).relative_to(ROOT))] = digest(Path(__file__))
    return dict(passed=True, normal_objects_byte_identical=len(objects), functions=len(frames),
        largest_individual_frame=max(row['bytes'] for row in frames), frames=frames,
        inputs=inputs, compiler_optimization='normal-Os', individual_frames_only=True,
        complete_call_chain_bound_proven=False, raw_pair_binding_frames_measured=False,
        hardware=False, limits=[
            'Compiler .su records are matched to every defined function in the exact normal RV32 objects.',
            'Instrumented objects and the complete archive must be byte-identical to the packaged normal build.',
            'These frame sizes are not a call-chain sum, interrupt bound, indirect-call target proof or physical stack acceptance.',
            'Raw-pair O2 bindings, assembly frames, original firmware, runtime stack placement and concurrency remain separate.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--instrumented-directory', type=Path, required=True)
    parser.add_argument('--core-directory', type=Path, required=True)
    parser.add_argument('--instrumented-archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    instrumented, reference, output = (path.resolve() for path in
        (args.instrumented_directory, args.core_directory, args.output))
    assert all(path.is_relative_to(ROOT / '.local') or path.is_relative_to(ROOT / '.build')
               for path in (instrumented, reference, output))
    assert not output.exists()
    archive = args.instrumented_archive.resolve() if args.instrumented_archive else None
    assert archive is None or archive.is_relative_to(instrumented)
    result = inventory(instrumented, reference, archive)
    assert all(digest(ROOT / name) == expected for name, expected in result['inputs'].items())
    with output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, objects=result['normal_objects_byte_identical'],
        functions=result['functions'], largest_individual_frame=result['largest_individual_frame'],
        complete_call_chain_bound_proven=False, receipt=str(output.relative_to(ROOT)), sha256=digest(output))))


if __name__ == '__main__':
    main()
