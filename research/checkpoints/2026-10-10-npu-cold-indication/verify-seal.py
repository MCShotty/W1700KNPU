from pathlib import Path
import argparse
import hashlib
import json
import subprocess

root = Path('/home/captain/W1700KNPU')
parser = argparse.ArgumentParser()
parser.add_argument('--index-only', action='store_true')
args = parser.parse_args()
out = root / 'research/checkpoints/2026-10-10-npu-cold-indication'
digest = lambda data: hashlib.sha256(data).hexdigest()
sealed = json.loads((out / 'verification.json').read_text())
files = json.loads((out / 'file-manifest.json').read_text())['files']
for path, expected in sealed['inputs'].items():
    assert digest((root / path).read_bytes()) == expected, ('input', path)
for row in files:
    path = root / row['path']
    assert path.stat().st_size == row['bytes'] and digest(path.read_bytes()) == row['sha256'], ('file', row['path'])
index = subprocess.check_output(['git', '-C', root, 'diff', '--cached', '--name-only'], text=True).splitlines()
for name in index:
    value = subprocess.check_output(['git', '-C', root, 'show', ':' + name])
    assert value == (root / name).read_bytes(), ('index-normalized', name)
committed = [] if args.index_only else subprocess.check_output(['git', '-C', root, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD'], text=True).splitlines()
for name in committed:
    value = subprocess.check_output(['git', '-C', root, 'show', 'HEAD:' + name])
    assert value == (root / name).read_bytes(), ('committed-normalized', name)
print(json.dumps(dict(passed=True, sealed_inputs=len(sealed['inputs']), sealed_files=len(files),
                      index_exact_files=len(index), committed_exact_files=len(committed))))
