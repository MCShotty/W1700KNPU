#!/usr/bin/env python3
"""Stage, test and kernel-compile the unpromoted bidirectional control entry."""
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
import test_host_queue_publication as extract
import test_memory_preflight as preflight
import test_control_v2 as v2
import build_host_tx_topology as kernel_build

ROOT, BUILD, OUT = v2.ROOT, v2.BUILD / 'provider', v2.OUT
KERNEL, SOURCE, HEADER = preflight.KERNEL, preflight.SOURCE, preflight.HEADER
FRAGMENT = OUT / 'airoha-control.c'
HARNESS = ROOT / 'tests/npu/control-v2-provider-harness.c'
sha, execute = v2.sha, v2.execute
DECLARATION = 'int airoha_npu_wlan_control(struct airoha_npu *npu, void *data, int len);\n'
STUB = '''static inline int airoha_npu_wlan_control(struct airoha_npu *npu,
                                           void *data, int len)
{
\treturn -EOPNOTSUPP;
}

'''.replace('                                           ', '\t\t\t\t\t  ')

PROBE = '''#include <linux/kconfig.h>
#undef CONFIG_NET_AIROHA_NPU
#undef CONFIG_NET_AIROHA_NPU_MODULE
#ifdef TEST_NPU_ON
#define CONFIG_NET_AIROHA_NPU 1
#endif
#include <linux/module.h>
#include <linux/stddef.h>
#include "public.h"
static const u32 layout[] __used __section(".npu_layout") = {
#ifdef TEST_NPU_ON
    sizeof(struct airoha_npu_core), sizeof(struct airoha_npu),
    offsetof(struct airoha_npu_core, lock), offsetof(struct airoha_npu_core, wdt_work),
    offsetof(struct airoha_npu_core, buf), offsetof(struct airoha_npu_core, addr),
    offsetof(struct airoha_npu, irqs), offsetof(struct airoha_npu, stats),
    offsetof(struct airoha_npu, ops),
#else
    0, sizeof(struct airoha_npu), 0, 0, 0, 0, 0, 0, 0,
#endif
};
#ifdef TEST_CONTROL_DECL
int control_probe(struct airoha_npu *npu, void *data, int len);
int control_probe(struct airoha_npu *npu, void *data, int len)
{
    return airoha_npu_wlan_control(npu, data, len);
}
#endif
MODULE_LICENSE("GPL");
'''


def replace_once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new)


def stage():
    prior = json.loads((preflight.OUT / 'abi-layout.json').read_text())
    assert sha(SOURCE) == prior['source_sha256'] == '8eed02dd963c9d80fcaf4f15368506f4a4720dd7be4f080c394a21bba7e1fe8f'
    assert sha(HEADER) == prior['public_header_sha256'] == '9359009a4161de572e7f44b41b172860bb6414b56332f16ed6ff8df972126364'
    old_source, old_header = SOURCE.read_text(), HEADER.read_text()
    new_source = replace_once(old_source, '#include <linux/regmap.h>\n',
                              '#include <linux/regmap.h>\n#include <linux/unaligned.h>\n')
    anchor = 'static int airoha_npu_load_firmware('
    new_source = replace_once(new_source, anchor, FRAGMENT.read_text() + '\n' + anchor)
    new_header = replace_once(old_header, 'void airoha_npu_put(struct airoha_npu *npu);\n',
                              'void airoha_npu_put(struct airoha_npu *npu);\n' + DECLARATION)
    anchor = 'static inline void airoha_npu_put(struct airoha_npu *npu)\n{\n}\n\n'
    new_header = replace_once(new_header, anchor, anchor + STUB)
    before = {'drivers/net/ethernet/airoha/airoha_npu.c': old_source,
              'include/linux/soc/airoha/airoha_offload.h': old_header}
    after = dict(zip(before, (new_source, new_header)))
    patch = ('From: W1700K firmware work\n'
             'Subject: [PATCH] net: airoha: add bidirectional NPU control transport\n\n'
             'The existing WLAN GET wrapper leaves its request body zeroed. Add a\n'
             'dedicated NQC2 request/reply path through the coherent mailbox bounce\n'
             'buffer, including its existing timeout ownership policy. Restrict\n'
             'the entry to the 80-byte control envelope; do not change legacy GET.\n\n'
             'This adds an exported entry without changing the public ops layout.\n'
             'The caller still needs a valid provider lifetime and must validate\n'
             'the structured response. No DMA drain or reclamation is implied.\n\n---\n\n')
    for name in before:
        patch += ''.join(difflib.unified_diff(before[name].splitlines(True), after[name].splitlines(True),
                                              fromfile='a/' + name, tofile='b/' + name))
    patch_path = OUT / '928-net-airoha-npu-bidirectional-control.patch'
    patch_path.write_text(patch)
    destination = BUILD / 'patch-application'
    for name, contents in before.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    result = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch_path)],
                            cwd=destination, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and 'offset' not in result.stdout and 'fuzz' not in result.stdout, result.stdout + result.stderr
    assert all((destination / name).read_text() == contents for name, contents in after.items())
    return before, after, patch_path


def sanitizer(source, header):
    include = []
    for name in ('NPU_OP_SET', 'NPU_FUNC_WIFI'):
        include.append(preflight.block(source, r'^enum \{(?=\n\t' + name + r'(?:\b|,))') + ';')
    include += [extract.declaration(header, 'enum', 'airoha_npu_wlan_get_cmd'),
                extract.declaration(source, 'struct', 'wlan_mbox_data')]
    include += [extract.function(source, name) for name in
                ('__airoha_npu_send_msg', 'airoha_npu_wlan_msg_get', 'airoha_npu_wlan_control')]
    (BUILD / 'control-v2-provider.inc').write_text('\n\n'.join(include) + '\n')
    executable = BUILD / 'provider-sanitize'
    command = [shutil.which('clang'), '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-I', str(v2.SOURCE),
               '-I', str(BUILD), str(HARNESS)]
    command += [str(v2.SOURCE / name) for name in ('control-client.c', 'control-v2-client.c',
                                                 'control-v2.c', 'admission.c', 'barrier.c')]
    execute([*command, '-o', executable])
    result = json.loads(execute([executable]))
    return dict(result=result, binary=str(executable.relative_to(ROOT)), binary_sha256=sha(executable),
                extracted_sha256=sha(BUILD / 'control-v2-provider.inc'),
                functions={name: hashlib.sha256(extract.function(source, name).encode()).hexdigest()
                           for name in ('__airoha_npu_send_msg', 'airoha_npu_wlan_msg_get',
                                        'airoha_npu_wlan_control')})


def objects(before, after):
    rows = []
    env = dict(os.environ, STAGING_DIR=str(kernel_build.TARGET_INCLUDE.parent.parent),
               PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')
    for phase, files in (('before', before), ('after', after)):
        directory = BUILD / phase
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'airoha_npu.c').write_text(files['drivers/net/ethernet/airoha/airoha_npu.c'])
        (directory / 'public.h').write_text(files['include/linux/soc/airoha/airoha_offload.h'])
        for path in SOURCE.parent.glob('*.h'):
            shutil.copy2(path, directory / path.name)
        for enabled in (False, True):
            prefix = '#define TEST_NPU_ON\n' if enabled else ''
            if phase == 'after':
                prefix += '#define TEST_CONTROL_DECL\n'
            (directory / f'probe-{int(enabled)}.c').write_text(prefix + PROBE)
        (directory / 'Makefile').write_text('obj-m += airoha_npu.o probe-0.o probe-1.o\n'
                                           'CFLAGS_airoha_npu.o += -include $(src)/public.h\n')
        command = ['make', '-C', str(KERNEL), f'M={directory}', 'ARCH=arm64',
                   f'CROSS_COMPILE={kernel_build.PREFIX}', 'airoha_npu.o', 'probe-0.o', 'probe-1.o']
        result = subprocess.run(command, capture_output=True, text=True, timeout=180, env=env)
        log = result.stdout + result.stderr
        (OUT / f'provider-{phase}-build.log').write_text(log)
        assert result.returncode == 0, log
        assert not re.search(r'\b(?:warning|error):', log, re.I), log
        layout = {}
        for enabled in (False, True):
            elf = ELFFile(io.BytesIO((directory / f'probe-{int(enabled)}.o').read_bytes()))
            assert elf['e_machine'] == 'EM_AARCH64'
            layout[str(int(enabled))] = list(struct.unpack('<9I', elf.get_section_by_name('.npu_layout').data()))
        elf = ELFFile(io.BytesIO((directory / 'airoha_npu.o').read_bytes()))
        symbols = {s.name for s in elf.get_section_by_name('.symtab').iter_symbols()}
        assert ('airoha_npu_wlan_control' in symbols) == (phase == 'after')
        rows.append(dict(phase=phase, command=command, layout=layout,
                         objects={str(path.relative_to(ROOT)): sha(path) for path in
                                  [directory / name for name in ('airoha_npu.o', 'probe-0.o', 'probe-1.o')]}))
    assert rows[0]['layout'] == rows[1]['layout'], 'public ABI layout changed'
    return rows


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    paths = [Path(__file__), FRAGMENT, HARNESS, SOURCE, HEADER, preflight.OUT / 'abi-layout.json',
             Path(extract.__file__), Path(preflight.__file__), Path(kernel_build.__file__),
             Path(v2.__file__), Path(v2.v1.__file__),
             ROOT / 'firmware/source-lock.json', ROOT / 'firmware/patches/openwrt.patch',
             ROOT / 'firmware/patches/luci.patch', ROOT / 'firmware/build.config',
             kernel_build.OPENWRT / '.config', KERNEL / '.config', KERNEL / 'Module.symvers',
             KERNEL / 'include/generated/autoconf.h', KERNEL / 'include/generated/utsrelease.h']
    paths += sorted(SOURCE.parent.glob('*.h'))
    paths += [v2.SOURCE / name for name in ('control-client.c', 'control-client.h', 'control-v2.h',
                                          'control-v2-client.c', 'control-v2.c', 'admission.c',
                                          'admission.h', 'barrier.c', 'barrier.h')]
    paths.append(v2.SOURCE / 'CONTROL_V2_CONTRACT.md')
    inputs = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    before, after, patch = stage()
    sanitized = sanitizer(after['drivers/net/ethernet/airoha/airoha_npu.c'], after['include/linux/soc/airoha/airoha_offload.h'])
    builds = objects(before, after)
    checkpatch = execute(['perl', KERNEL / 'scripts/checkpatch.pl', '--strict', '--no-tree', '--no-signoff', patch])
    (OUT / 'provider-checkpatch.log').write_text(checkpatch)
    assert '0 errors, 0 warnings, 0 checks' in checkpatch, checkpatch
    assert inputs == {str(path.relative_to(ROOT)): sha(path) for path in paths}
    report = dict(passed=True, inputs=inputs, patch_sha256=sha(patch), sanitizer=sanitized,
                  builds=builds, checkpatch=checkpatch,
                  compiler=execute([str(kernel_build.PREFIX) + 'gcc', '--version']).splitlines()[0],
                  scope='Actual provider send/GET and candidate control functions with explicit regmap/DMA-storage/delivery models, actual V2 server/client C under ASan/UBSan, and six isolated AArch64 kernel-context objects. No live provider references, IRQ/RCU/removal proof, physical DMA/cache containment, module load, image or router validation.')
    output = OUT / 'control-v2-provider.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=True, sanitizer=sanitized['result'], objects=6,
                         public_layout_unchanged=True, evidence_sha256=sha(output))))


if __name__ == '__main__':
    main()
