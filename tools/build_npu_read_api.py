#!/usr/bin/env python3
"""Build the explicitly loaded host-only Unicorn read adapter, never firmware."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import sysconfig
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='New directory under the project .local tree on native Linux storage')
    parser.add_argument('--sanitize', choices=('undefined', 'none'), default='undefined')
    args = parser.parse_args()
    if (sys.platform != 'linux' or platform.machine() != 'x86_64' or
            sys.implementation.name != 'cpython' or sys.version_info[:2] != (3, 14) or
            hasattr(sys, '_is_gil_enabled') and not sys._is_gil_enabled()):
        parser.error('the reviewed build profile is GIL-enabled Linux x86_64 CPython3.14')
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output = output.resolve()
    parent = output.parent.resolve(strict=True)
    if not output.is_relative_to(ROOT / '.local') or output.exists():
        parser.error('use a new private project .local output directory')
    filesystem = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '--target', str(parent)], text=True).strip()
    if filesystem not in ('ext4', 'xfs', 'btrfs', 'overlay'):
        parser.error('native Linux output storage is required')
    sys.path.insert(0, str(ROOT / 'tests/npu'))
    import unicorn
    import unicorn.unicorn_py3.unicorn as binding
    from npu_csr_sampler import CsrSampler
    from native_cold_observer import PROFILE_SOURCES
    cpu = unicorn.Uc(unicorn.UC_ARCH_RISCV, unicorn.UC_MODE_RISCV32)
    CsrSampler(cpu)
    include = Path(unicorn.__file__).resolve().parent / 'include'
    headers = {str(path): sha(path) for path in sorted(include.rglob('*.h'))}
    if str(include / 'unicorn/unicorn.h') not in headers:
        parser.error('the loaded Unicorn package does not supply its reviewed headers')
    source = ROOT / 'tests/npu/native-read-api.c'
    inputs = {str(path): sha(path) for path in (source, Path(__file__),
        ROOT / 'tests/npu/native_read_api.py', ROOT / 'tests/npu/npu_csr_sampler.py',
        ROOT / 'tests/npu/test_native_read_api.py')}
    inputs.update({str(ROOT / name): sha(ROOT / name) for name in PROFILE_SOURCES})
    output.mkdir()
    extension = output / ('_npu_read_api' + sysconfig.get_config_var('EXT_SUFFIX'))
    command = ['/usr/bin/cc', '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror',
        '-fPIC', '-shared', '-I' + sysconfig.get_paths()['include'], '-I' + str(include)]
    if args.sanitize == 'undefined':
        command += ['-fsanitize=undefined', '-fno-sanitize-recover=undefined']
    command += [str(source), '-o', str(extension)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
    with (output / 'compile.log').open('x') as stream:
        stream.write(completed.stdout + completed.stderr)
    if completed.returncode:
        raise RuntimeError('native read adapter compilation failed; retained compile.log')
    if any(sha(path) != digest for path, digest in {**inputs, **headers}.items()):
        raise RuntimeError('build inputs changed during compilation')
    result = dict(format='w1700k-npu-read-api-build-v1', passed=True,
        variant='ubsan' if args.sanitize == 'undefined' else 'plain', command=command,
        compiler=subprocess.check_output(['/usr/bin/cc', '--version'], text=True),
        inputs=inputs, headers=headers, extension=dict(path=str(extension), sha256=sha(extension)),
        interpreter=dict(path=str(Path(sys.executable).resolve()), sha256=sha(Path(sys.executable).resolve()),
            version=sys.version, GIL_enabled=True),
        unicorn=dict(version=unicorn.__version__, native_version=unicorn.uc_version(),
            library=str(binding.uclib._name), sha256=sha(Path(binding.uclib._name).resolve())),
        observed_unix_ns=time.time_ns(), firmware=False, hardware=False,
        limits=['Host read-API build only, not native replay or performance acceptance.',
            'Caller must qualify live RAM and backing storage before this compiler launch.'])
    with (output / 'build.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, variant=result['variant'], extension=result['extension'])))


if __name__ == '__main__':
    main()
