#!/usr/bin/env python3
"""Exercise the Linux executor with actual V2/provider C and modeled dependencies."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import resource
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
import build_control_v2_provider as provider
import test_npu_linked_modules as modules

ROOT = modules.ROOT
SOURCE = ROOT / 'firmware/npu'
BUILD = ROOT / '.local/npu-linux-control'
OUT = ROOT / 'research/checkpoints/2026-09-23-npu-linux-control'
KERNEL = ROOT / '.local/npu-provider-kernel-link/verified/linux-6.18.44'
PREVIOUS = ROOT / 'research/checkpoints/2026-09-23-npu-provider-kernel-link/provider-kernel-link.json'
HARNESS = ROOT / 'tests/npu/linux-control-harness.c'
sha, relative = modules.sha, modules.relative


def record(path):
    return dict(path=relative(path), sha256=sha(path), bytes=path.stat().st_size)


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def execute(command, log, *, env=None, timeout=60, accepted=0):
    result = subprocess.run([str(p) for p in command], capture_output=True, text=True,
                            timeout=timeout, env=env, preexec_fn=no_core)
    log.write_text(result.stdout + result.stderr)
    assert result.returncode == accepted, log.read_text()[-5000:]
    return result


def once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-name', default='verified')
    parser.add_argument('--output-dir', type=Path, default=OUT)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,31}', args.build_name)
    dest = BUILD / args.build_name
    out = args.output_dir.resolve()
    assert out == OUT or out.is_relative_to((ROOT / '.local').resolve())
    assert not dest.exists() and not (out / 'linux-control.json').exists()
    assert sha(PREVIOUS) == 'cdd3284695bcc9b02b5290a9a04b956db6dd3967625d24b831cbd0e0f2be0cd8'
    previous = json.loads(PREVIOUS.read_text())
    provider_source = KERNEL / 'drivers/net/ethernet/airoha/airoha_npu.c'
    provider_header = KERNEL / 'include/linux/soc/airoha/airoha_offload.h'
    for path in (provider_source, provider_header, KERNEL / '.config', KERNEL / 'Module.symvers'):
        assert sha(path) == next(row['sha256'] for row in previous['artifacts'] if row['path'] == relative(path))
    names = ('barrier.h', 'admission.h', 'control-client.h', 'control-v2.h',
             'control-client.c', 'control-v2-client.c', 'control-v2.c', 'admission.c', 'barrier.c',
             'linux-control.c', 'linux-control.h', 'kernel-include/stdint.h')
    inputs = [Path(__file__), HARNESS, ROOT / 'tests/npu/control-v2-provider-harness.c',
              Path(provider.__file__), Path(provider.extract.__file__), Path(provider.preflight.__file__),
              Path(modules.__file__), PREVIOUS, provider.OUT / 'control-v2-provider.json',
              provider_source, provider_header, KERNEL / '.config', KERNEL / 'Module.symvers',
              KERNEL / 'include/generated/autoconf.h', ROOT / 'firmware/source-lock.json',
              ROOT / 'firmware/patches/openwrt.patch', ROOT / 'firmware/build.config']
    inputs += [SOURCE / name for name in names]
    before = {relative(p): sha(p) for p in inputs}
    dest.mkdir(parents=True)
    out.mkdir(parents=True, exist_ok=True)
    text, header = provider_source.read_text(), provider_header.read_text()
    extract, preflight = provider.extract, provider.preflight
    parts = [preflight.block(text, r'^enum \{(?=\n\t' + name + r'(?:\b|,))') + ';'
             for name in ('NPU_OP_SET', 'NPU_FUNC_WIFI')]
    parts += [extract.declaration(header, 'enum', 'airoha_npu_wlan_get_cmd'),
              extract.declaration(text, 'struct', 'wlan_mbox_data')]
    functions = ('__airoha_npu_send_msg', 'airoha_npu_wlan_msg_get', 'airoha_npu_wlan_control')
    excerpts = {name: extract.function(text, name) for name in functions}
    prior_provider = json.loads((provider.OUT / 'control-v2-provider.json').read_text())
    fingerprints = {name: hashlib.sha256(source.encode()).hexdigest() for name, source in excerpts.items()}
    assert fingerprints == prior_provider['sanitizer']['functions']
    (dest / 'control-v2-provider.inc').write_text('\n\n'.join(parts + list(excerpts.values())) + '\n')
    shims = {
        'linux/types.h': '#ifndef NPU_TEST_TYPES_H\n#define NPU_TEST_TYPES_H\n#include <stdint.h>\n#include <stdbool.h>\n#include <stddef.h>\ntypedef uint8_t u8;\ntypedef uint16_t u16;\ntypedef uint32_t u32;\n#endif\n',
        'linux/mutex.h': '#ifndef NPU_TEST_MUTEX_H\n#define NPU_TEST_MUTEX_H\n#include <pthread.h>\nstruct mutex { pthread_mutex_t native; };\nvoid npu_test_mutex_init(struct mutex *m);\nvoid npu_test_mutex_lock(struct mutex *m);\nvoid npu_test_mutex_unlock(struct mutex *m);\nstatic inline void mutex_init(struct mutex *m) { npu_test_mutex_init(m); }\nstatic inline void mutex_lock(struct mutex *m) { npu_test_mutex_lock(m); }\nstatic inline void mutex_unlock(struct mutex *m) { npu_test_mutex_unlock(m); }\n#endif\n',
        'linux/soc/airoha/airoha_offload.h': 'struct airoha_npu;\nint airoha_npu_wlan_control(struct airoha_npu *npu, void *data, int len);\n',
    }
    for name, contents in shims.items():
        path = dest / 'shims' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    compiler = shutil.which('clang')
    assert compiler
    command = [compiler, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-pthread',
               '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
               '-I' + str(dest / 'shims'), '-I' + str(dest), '-I' + str(SOURCE),
               '-I' + str(ROOT / 'tests/npu'), str(HARNESS)]
    command += [str(SOURCE / name) for name in ('control-client.c', 'control-v2-client.c',
                'control-v2.c', 'admission.c', 'barrier.c')]
    binary = dest / 'linux-control-sanitize'
    build_log = out / 'host-build.log'
    execute(command + [SOURCE / 'linux-control.c', '-o', binary], build_log)
    assert not build_log.read_text()
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    run_log = out / 'host-run.log'
    result = json.loads(execute([binary], run_log, env=env, timeout=30).stdout)
    print(json.dumps(dict(stage='host', **result)), flush=True)
    original = (SOURCE / 'linux-control.c').read_text()
    mutations = {
        'reinitialize': ('init', once(original, '\tif (control->initialized)\n\t\treturn -EALREADY;\n', '')),
        'wrong-operation': ('operation', once(original, 'next_operation(control) != (int)operation',
                                              'next_operation(control) != (int)operation && (int)operation == -99')),
        'ignore-reply-rejection': ('protocol', once(original, 'result != NPU_CLIENT_ACCEPTED',
                                                   'result == NPU_CLIENT_IGNORED')),
        'replace-first-error': ('sticky', once(original, '\tif (!control->error)\n\t\tcontrol->error = error;',
                                              '\tcontrol->error = error;')),
        'positive-transport-error': ('sticky', once(original, 'error < 0 ? error : error ? -EIO : -EPROTO',
                                                   'error ? error : -EPROTO')),
    }
    prefix, anchor, close = original.partition('void npu_linux_control_close(')
    assert anchor
    mutations['close-without-join'] = ('close', prefix + anchor +
        once(once(close, '\tmutex_lock(&control->mutex);\n', ''), '\tmutex_unlock(&control->mutex);\n', ''))
    mutants = []
    for name, (case, changed) in mutations.items():
        directory = dest / 'mutants' / name
        directory.mkdir(parents=True)
        source, mutant = directory / 'linux-control.c', directory / 'test'
        source.write_text(changed)
        log = directory / 'build.log'
        execute(command + [source, '-o', mutant], log)
        assert not log.read_text()
        done = subprocess.run([str(mutant), case], capture_output=True, text=True,
                              env=env, timeout=15, preexec_fn=no_core)
        (directory / 'run.log').write_text(done.stdout + done.stderr)
        assert done.returncode != 0 and 'FAIL[' + case + ']' in done.stderr, (name, done.stdout, done.stderr)
        mutants.append(dict(name=name, case=case, returncode=done.returncode,
                            source=record(source), binary=record(mutant), log=record(directory / 'run.log')))
    print(json.dumps(dict(stage='mutants', rejected=len(mutants))), flush=True)
    prefix = modules.STAGING.parent / 'toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-'
    kernel_env = dict(os.environ, STAGING_DIR=str(modules.STAGING),
                      PATH=str(prefix.parent) + ':' + str(modules.STAGING.parent / 'host/bin') + ':/usr/bin:/bin')
    kernel_rows = []
    for enabled in (1, 0):
        directory = dest / ('kernel-' + str(enabled))
        directory.mkdir()
        for name in ('barrier.h', 'admission.h', 'control-client.h', 'control-v2.h',
                     'control-client.c', 'control-v2-client.c', 'linux-control.h'):
            shutil.copy2(SOURCE / name, directory / name)
        shutil.copy2(SOURCE / 'linux-control.c', directory / 'executor.c')
        (directory / 'compat').mkdir()
        shutil.copy2(SOURCE / 'kernel-include/stdint.h', directory / 'compat/stdint.h')
        (directory / 'module.c').write_text('#include <linux/module.h>\n#include <linux/stddef.h>\n#include "linux-control.h"\n'
            'static const u32 layout[] __used __section(".npu_control_layout") = {\n'
            'sizeof(struct npu_control_client), sizeof(struct npu_control_v2_client),\n'
            'sizeof(struct npu_control_v2_packet), offsetof(struct npu_control_v2_client, boot_lo) };\n'
            'MODULE_LICENSE("GPL");\nMODULE_DESCRIPTION("Unloaded Linux NPU control executor");\n')
        makefile = ('obj-m += npu-control-linux-test.o\n'
                    'npu-control-linux-test-y := executor.o control-client.o control-v2-client.o module.o\n'
                    'ccflags-y += -I$(src)/compat\n')
        if not enabled:
            (directory / 'disable-npu.h').write_text('#include <linux/kconfig.h>\n#undef CONFIG_NET_AIROHA_NPU\n#undef CONFIG_NET_AIROHA_NPU_MODULE\n')
            makefile += 'ccflags-y += -include $(src)/disable-npu.h\n'
        (directory / 'Makefile').write_text(makefile)
        kernel_command = ['make', '-C', str(KERNEL), '-j2', 'ARCH=arm64', 'CROSS_COMPILE=' + str(prefix),
                          'CC=' + str(prefix) + 'gcc', 'KERNELRELEASE=6.18.44', 'KBUILD_BUILD_USER=',
                          'KBUILD_BUILD_HOST=', 'KBUILD_BUILD_VERSION=0',
                          'KBUILD_BUILD_TIMESTAMP=Fri Sep 4 16:17:19 2026', 'V=0', 'M=' + str(directory), 'modules']
        log = out / ('kernel-' + str(enabled) + '.log')
        execute(kernel_command, log, env=kernel_env, timeout=180)
        diagnostics = [line for line in log.read_text().splitlines() if re.search(r'\b(?:warning|error):', line, re.I)]
        assert set(diagnostics) <= {'WARNING: modpost: missing MODULE_DESCRIPTION() in npu-control-linux-test.o'}, diagnostics
        row, defined, undefined = modules.parse_module(directory / 'npu-control-linux-test.ko')
        assert {'npu_linux_control_init', 'npu_linux_control_exchange', 'npu_linux_control_snapshot',
                'npu_linux_control_close', 'npu_client_v2_complete'} <= defined
        assert ('airoha_npu_wlan_control' in undefined) == bool(enabled)
        elf = ELFFile(io.BytesIO((directory / 'module.o').read_bytes()))
        layout = list(struct.unpack('<4I', elf.get_section_by_name('.npu_control_layout').data()))
        assert layout == result['layout'], layout
        kernel_rows.append(dict(npu_enabled=enabled, command=kernel_command, module=row,
                                layout=layout, provider_control_import=bool(enabled),
                                diagnostics=diagnostics, log=record(log)))
        print(json.dumps(dict(stage='kernel', npu_enabled=enabled, linked=True)), flush=True)
    assert before == {relative(p): sha(p) for p in inputs}
    derived = {relative(p): sha(p) for p in dest.rglob('*')
               if p.is_file() and (p.suffix in ('.c', '.h', '.inc') or p.name == 'Makefile')}
    receipt = dict(schema=1, inputs_before_after=before, extracted_provider_functions=fingerprints,
                   derived=derived, host=dict(command=command + [str(SOURCE / 'linux-control.c'), '-o', str(binary)],
                       result=result, binary=record(binary), build_log=record(build_log), run_log=record(run_log)),
                   mutants=mutants, kernel_modules=kernel_rows,
                   limits=['Kernel mutex behavior is modeled with pthreads; regmap, coherent storage and firmware delivery use the existing explicit provider model.',
                           'The real V2 client, server and selected provider C execute, but no physical DMA/cache/drain or live kernel execution is established.',
                           'The executor requires a caller-established cold provider lifetime and retained reference; automatic mt76 initialization and production loader identity remain unimplemented.',
                           'No resource cleanup, restart authority, restricted selector execution, packaged source promotion, router action or firmware image is introduced.'])
    path = out / 'linux-control.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(receipt_sha256=sha(path), cases=result['cases'], mutants=len(mutants), kernel_modules=2)), flush=True)


if __name__ == '__main__':
    main()
