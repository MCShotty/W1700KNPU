#!/usr/bin/env python3
"""Exact raw-pair compiler frames, not complete call-chain or physical bounds."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
from unittest.mock import patch

from elftools.elf.elffile import ELFFile
import build_npu_pair as build
import native_prefix_snapshot
import npu_stack_usage as usage
from test_desc10_stack_usage import sections

ROOT = build.ROOT
ASSEMBLY_ONLY = {'bridge', 'reset', 'order', 'egress'}


def check_frames(defined, frames, assembly_only):
    emitted = Counter(row['function'] for row in frames)
    assert not emitted - defined, ('frame-not-in-linked-component', emitted - defined)
    assert not frames if assembly_only else frames, 'unexpected-or-missing-C-frames'
    return dict(defined - emitted)


def measure(reference, destination):
    original_run, objects, commands = subprocess.run, {}, []

    def instrument(command, **options):
        command = list(map(str, command))
        sources = [i for i, word in enumerate(command) if not word.startswith('-') and Path(word).suffix == '.c']
        if Path(command[0]).name != 'clang' or not any('riscv32' in word for word in command) or not sources:
            return original_run(command, **options)
        assert command.count('-o') == 1
        output_index = command.index('-o')
        output = Path(command[output_index + 1]).resolve()
        assert output.is_relative_to(destination)
        if '-c' in command:
            assert len(sources) == 1
            command.append('-fstack-usage')
            done = original_run(command, **options)
            objects[str(output)] = output.with_suffix('.su')
            commands.append(command)
            return done
        flags = []
        for index, word in enumerate(command[1:], 1):
            if index in sources or index in (output_index, output_index + 1): continue
            if word.startswith(('-Wl,', '--ld-path=')) or word == '-nostdlib': continue
            if not word.startswith('-') and Path(word).suffix in ('.S', '.s', '.o'): continue
            flags.append(word)
        directory = output.parent / (output.name + '.frames')
        directory.mkdir()
        for index in sources:
            source = Path(command[index])
            obj = directory / (source.stem + '.o')
            assert not obj.exists()
            compile_command = [command[0], *flags, '-Wno-unused-command-line-argument',
                               '-fstack-usage', '-c', str(source), '-o', str(obj)]
            done = original_run(compile_command, capture_output=True, text=True, timeout=180)
            obj.with_suffix('.log').write_text(done.stdout + done.stderr)
            assert done.returncode == 0, done.stderr
            objects[str(obj)] = obj.with_suffix('.su')
            commands.append(compile_command)
            command[index] = str(obj)
        commands.append(command)
        return original_run(command, **options)

    with patch.object(subprocess, 'run', side_effect=instrument):
        pair, candidate = build.build(destination)
    prior = json.loads((reference / 'manifest.json').read_bytes())
    assert candidate['components'].keys() == prior['components'].keys()
    assert len(candidate['hooks']) == len(prior['hooks'])
    for name in ('CODE.bin', 'DATA.bin'):
        assert (pair / name).read_bytes() == (reference / name).read_bytes(), ('raw-repeat-drift', name)
    inputs = dict(prior['inputs'])
    for name, expected in candidate['inputs'].items():
        assert name not in inputs or inputs[name] == expected, ('stack-source-conflict', name)
        inputs[name] = expected
    rows = []
    for name, filename in candidate['symbol_files'].items():
        path, original = ROOT / filename, ROOT / prior['symbol_files'][name]
        for manifest, item in ((candidate, path), (prior, original)):
            assert usage.digest(item) == manifest['components'][name]['sha256']
            inputs[str(item.relative_to(ROOT))] = usage.digest(item)
        assert sections(path) == sections(original), ('allocated-section-drift', name)
        with path.open('rb') as stream:
            binary = ELFFile(stream)
            defined = Counter(symbol.name for symbol in binary.get_section_by_name('.symtab').iter_symbols()
                if symbol['st_info']['type'] == 'STT_FUNC' and symbol['st_size'] and isinstance(symbol['st_shndx'], int))
        records = sorted((path.parent / (path.name + '.frames')).glob('*.su'))
        frames = []
        for record in records:
            frames.extend(dict(row, usage=str(record.relative_to(ROOT))) for row in usage.parse_usage(record.read_text()))
        unmeasured = check_frames(defined, frames, name in ASSEMBLY_ONLY)
        rows.append(dict(component=name, translation_units=len(records), measured_C_frames=len(frames),
            frames=frames, unmeasured_defined_functions=unmeasured,
            assembly_only=name in ASSEMBLY_ONLY, allocated_sections_byte_identical=True))
    for obj, record in objects.items():
        assert record.is_file()
        usage.parse_usage(record.read_text())
        for path in (Path(obj), record): inputs[str(path.relative_to(ROOT))] = usage.digest(path)
    for path in (Path(__file__), pair / 'CODE.bin', pair / 'DATA.bin', pair / 'manifest.json',
                 reference / 'CODE.bin', reference / 'DATA.bin', reference / 'manifest.json'):
        inputs[str(path.relative_to(ROOT))] = usage.digest(path)
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(usage.digest(ROOT / name) == expected for name, expected in inputs.items())
    measured = [frame for row in rows for frame in row['frames']]
    assert measured
    return dict(passed=True, components=rows, complete_CODE_DATA_byte_identical=True,
        component_count=len(rows), hooks=len(candidate['hooks']), measured_C_frames=len(measured),
        instrumented_objects=len(objects), largest_individual_frame=max(row['bytes'] for row in measured),
        individual_frames_only=True, complete_call_chain_bound_proven=False,
        original_assembly_frames_measured=False, hardware=False, commands=commands, inputs=inputs,
        limits=['Separate C compiles prevent .su records from being overwritten by another translation unit.',
                'Every allocated component section and complete CODE/DATA must match the frozen reference exactly.',
                'Four assembly-only components and all other unmeasured defined functions remain explicit, not counted as measured.',
                'This is not full function/assembly coverage, a call-chain/indirect/IRQ bound or physical stack acceptance.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    reference = args.pair.resolve()
    assert reference.is_relative_to(ROOT)
    destination = ROOT / '.local/npu-raw-stack' / args.name
    result = measure(reference, destination)
    output = destination / 'result.json'
    with output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, components=result['component_count'], measured_C_frames=result['measured_C_frames'],
        largest_individual_frame=result['largest_individual_frame'], sha256=usage.digest(output))), flush=True)


if __name__ == '__main__': main()
