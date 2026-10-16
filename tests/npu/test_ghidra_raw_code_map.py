#!/usr/bin/env python3
"""Execute Ghidra map rejection controls, not firmware or native admission."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile

from elftools.elf.elffile import ELFFile
import npu_image as image

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(pair, ghidra, destination):
    manifest = json.loads((pair / 'manifest.json').read_bytes())
    code, data = (pair / 'CODE.bin').read_bytes(), (pair / 'DATA.bin').read_bytes()
    image.validate(code, data, manifest)
    component = ROOT / manifest['symbol_files']['cold-pcie-tail']
    assert digest(component) == manifest['components']['cold-pcie-tail']['sha256']
    binary = ELFFile(io.BytesIO(component.read_bytes()))
    section = next(section for section in binary.iter_sections() if section['sh_flags'] & 6 == 6 and section['sh_size'])
    offset = section['sh_addr'] - image.CODE
    assert code[offset:offset + section['sh_size']] == section.data()
    assert destination.is_relative_to(ROOT / '.local') and not destination.exists()
    destination.mkdir(parents=True)
    altered = bytearray(code)
    altered[offset] ^= 1
    changed = destination / 'component-drift-CODE.bin'
    changed.write_bytes(altered)
    inputs = dict(manifest['inputs'])
    for path in (component, pair / 'manifest.json', pair / 'CODE.bin', pair / 'DATA.bin',
                 ROOT / 'tools/ghidra/MapNpuRawCode.java', ROOT / 'tools/npu_image.py', Path(__file__), changed):
        inputs[str(path.relative_to(ROOT))] = digest(path)
    assert all(digest(ROOT / name) == expected for name, expected in inputs.items())
    cases = [('wrong-hash', pair / 'CODE.bin', '0' * 64, 'java.lang.IllegalStateException: CODE hash mismatch'),
             ('component-byte-drift', changed, digest(changed),
              'java.lang.IllegalStateException: Imported component bytes disagree with paired CODE:')]
    results = []
    for name, candidate, expected, marker in cases:
        with tempfile.TemporaryDirectory(prefix='w1700k-ghidra-map-') as project:
            command = [str(ghidra), project, 'RejectMap', '-import', str(component),
                '-processor', 'RISCV:LE:32:AndeStar_v5', '-cspec', 'gcc', '-noanalysis',
                '-scriptPath', str(ROOT / 'tools/ghidra'), '-preScript', 'MapNpuRawCode.java',
                str(candidate), expected, '-deleteProject']
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=240)
        log = destination / (name + '.log')
        log.write_text(completed.stdout + completed.stderr)
        text = log.read_text()
        assert marker in text and 'NPU_RAW_CODE_MAP_PASS' not in text, (name, text[-3000:])
        inputs[str(log.relative_to(ROOT))] = digest(log)
        results.append(dict(name=name, expected_guard_exception=marker, tool_exit_code=completed.returncode,
                            no_map_success=True, candidate_sha256=digest(candidate)))
        print(json.dumps(dict(ghidra_map_negative=name, passed=True)), flush=True)
    assert all(digest(ROOT / name) == expected for name, expected in inputs.items())
    result = dict(passed=True, cases=results, inputs=inputs, executable=str(ghidra),
        ghidra_analysis_map_only=True, native_admission=False, hardware=False,
        limits=['Runs the exact Java script under Ghidra on an actual component and explicit corrupted fixtures.',
                'A tool exit code alone never establishes guard success; require the exact exception and absence of map-pass marker.',
                'No runtime firmware state, source, flash or physical device is modified.'])
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--ghidra', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    assert args.ghidra.is_file()
    result = run(args.pair.resolve(), args.ghidra.resolve(), ROOT / '.local/npu-ghidra-map' / args.name)
    print(json.dumps(dict(passed=True, cases=len(result['cases']), native_admission=False)))


if __name__ == '__main__': main()
