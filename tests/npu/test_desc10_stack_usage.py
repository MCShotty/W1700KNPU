#!/usr/bin/env python3
"""Exact DESC10 C frame coverage; not assembly, call-chain or hardware stack proof."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
from unittest.mock import patch

from elftools.elf.elffile import ELFFile
import native_prefix_snapshot
import npu_stack_usage as usage
import txdone_wire_native

ROOT = usage.ROOT


def sections(path):
    with path.open('rb') as stream:
        binary = ELFFile(stream)
        assert binary['e_machine'] == 'EM_RISCV' and binary.elfclass == 32
        return {section.name: (section['sh_addr'], section['sh_size'], section['sh_type'], section.data())
                for section in binary.iter_sections() if section['sh_flags'] & 2 and section['sh_size']}


def measure(pair, destination):
    inputs = native_prefix_snapshot.source_inputs({})
    manifest_path = pair / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    for name, expected in manifest['inputs'].items():
        assert name not in inputs or inputs[name] == expected, ('stack-cohort-conflict', name)
        inputs[name] = expected
    parts = {name: (ROOT / relative).resolve() for name, relative in manifest['symbol_files'].items()}
    for name, path in parts.items():
        assert path.is_relative_to(ROOT) and path.is_file()
        expected = manifest['components'][name]['sha256']
        assert usage.digest(path) == expected, ('stack-component-drift', name)
        inputs[str(path.relative_to(ROOT))] = expected
    assert all(usage.digest(ROOT / name) == expected for name, expected in inputs.items())
    assert destination.is_relative_to(ROOT / '.local') and not destination.exists()
    destination.mkdir(parents=True)
    original_run, commands = subprocess.run, []

    def instrument(command, **options):
        if Path(command[0]).name == 'clang':
            sources = [index for index, word in enumerate(command) if Path(word).suffix == '.c']
            assert len(sources) == 2
            flags = command[1:sources[0]]
            command = list(command)
            for index in sources:
                source = Path(command[index])
                obj = destination / (source.stem + '.o')
                compile_command = [command[0], *flags, '-Wno-unused-command-line-argument',
                                   '-fstack-usage', '-c', str(source), '-o', str(obj)]
                completed = original_run(compile_command, capture_output=True, text=True,
                                         cwd=destination, timeout=180)
                (destination / (source.stem + '.log')).write_text(completed.stdout + completed.stderr)
                assert completed.returncode == 0, completed.stderr
                commands.append(compile_command)
                command[index] = str(obj)
            commands.append(command)
            options['cwd'] = destination
        return original_run(command, **options)

    with patch.object(subprocess, 'run', side_effect=instrument):
        elf = txdone_wire_native.build(destination, parts, parts['cold-packets'], parts['cold-rx-event'])
    reference = parts['cold-txdone']
    assert sections(elf) == sections(reference), 'raw-allocated-section-drift'
    frames = []
    records = sorted(destination.glob('*.su'))
    assert len(records) == 2 and len(commands) == 3
    for record in records:
        frames.extend(dict(row, usage=record.name) for row in usage.parse_usage(record.read_text()))
    with elf.open('rb') as stream:
        binary = ELFFile(stream)
        defined = Counter(symbol.name for symbol in binary.get_section_by_name('.symtab').iter_symbols()
            if symbol['st_info']['type'] == 'STT_FUNC' and symbol['st_size'] and isinstance(symbol['st_shndx'], int))
    assert Counter(row['function'] for row in frames) == defined, 'raw-C-frame-coverage'
    for path in (elf, manifest_path, Path(__file__), *records, *destination.glob('*.o')):
        inputs[str(path.relative_to(ROOT))] = usage.digest(path)
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(usage.digest(ROOT / name) == expected for name, expected in inputs.items())
    return dict(passed=True, allocated_sections_byte_identical=True, all_defined_C_functions_measured=True,
        translation_units=2, frames=frames, c_functions=len(frames),
        largest_individual_frame=max(row['bytes'] for row in frames), commands=commands, inputs=inputs,
        individual_frames_only=True, complete_call_chain_bound_proven=False,
        asm_frames_measured=False, hardware=False, limits=[
            'Each C translation unit is compiled separately so Clang cannot silently overwrite its .su companion.',
            'All defined C functions in this exact DESC10 component are covered, including both same-named context functions.',
            'Allocated section names, addresses, extents, types and bytes must match the current component exactly.',
            'Other components, assembly/original firmware, indirect calls and complete physical stack bounds remain unresolved.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    pair = args.pair.resolve()
    assert pair.is_relative_to(ROOT)
    destination = ROOT / '.local/npu-desc10-stack' / args.name
    result = measure(pair, destination)
    output = destination / 'result.json'
    with output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, c_functions=result['c_functions'],
        largest_individual_frame=result['largest_individual_frame'], complete_call_chain_bound_proven=False,
        receipt=str(output.relative_to(ROOT)), sha256=usage.digest(output))))


if __name__ == '__main__':
    main()
