#!/usr/bin/env python3
"""Compile an ARM64 kernel-context probe of the unchanged public NPU ABI."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from test_memory_preflight import HEADER, KERNEL, LOCAL, OUT, ROOT, SOURCE, block

PROBE = r'''
#include <linux/module.h>
#include <linux/stddef.h>
#include <linux/ioport.h>
#include <linux/soc/airoha/airoha_offload.h>
PRIVATE
static const u32 layout[] __used __section(".npu_layout") = {
    sizeof(struct airoha_npu_core), sizeof(struct airoha_npu),
    offsetof(struct airoha_npu_core, lock), offsetof(struct airoha_npu_core, wdt_work),
    offsetof(struct airoha_npu_core, buf), offsetof(struct airoha_npu_core, addr),
    offsetof(struct airoha_npu, irqs), offsetof(struct airoha_npu, stats),
    offsetof(struct airoha_npu, ops),
    sizeof(struct airoha_npu_priv), offsetof(struct airoha_npu_priv, npu),
    offsetof(struct airoha_npu_priv, firmware_region),
    offsetof(struct airoha_npu_priv, txbuf_min_size), sizeof(struct resource),
};
MODULE_LICENSE("GPL");
'''


def main():
    local = LOCAL / 'layout'
    local.mkdir(parents=True, exist_ok=True)
    private = block(SOURCE.read_text(), r'^struct airoha_npu_priv \{') + ';'
    (local / 'airoha-layout.c').write_text(PROBE.replace('PRIVATE', private))
    (local / 'Makefile').write_text('obj-m += airoha-layout.o\n')
    tc = ROOT / '.build/openwrt/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-'
    env = dict(os.environ, PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')
    command = ['make', '-C', str(KERNEL), f'M={local}', 'ARCH=arm64',
               f'CROSS_COMPILE={tc}', 'airoha-layout.o']
    with (OUT / 'layout-build.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env, check=True)
    binary = local / 'layout.bin'
    subprocess.run([str(tc) + 'objcopy', '-O', 'binary', '--only-section=.npu_layout',
                    str(local / 'airoha-layout.o'), str(binary)], check=True)
    actual = list(struct.unpack('<14I', binary.read_bytes()))
    baseline = json.loads((ROOT / 'research/checkpoints/2026-09-05-npu-quiescence/abi-layout.json').read_text())['after']
    assert actual[:9] == baseline
    assert actual[10] == 0 and actual[11] == actual[1]
    assert actual[12] >= actual[11] + actual[13] and actual[9] >= actual[12] + 4
    result = {'passed': True, 'command': command, 'public_baseline': baseline,
              'public_current': actual[:9], 'private': dict(zip(
                  ['allocation_size', 'public_offset', 'firmware_offset', 'minimum_offset', 'resource_size'], actual[9:])),
              'public_header_sha256': hashlib.sha256(HEADER.read_bytes()).hexdigest(),
              'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'object_sha256': hashlib.sha256((local / 'airoha-layout.o').read_bytes()).hexdigest(),
              'limits': 'ARM64 kernel compile and offsets, not runtime lifetime or concurrency proof.'}
    (OUT / 'abi-layout.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
