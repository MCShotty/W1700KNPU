"""Compile/install ordered descriptor GET detours; hardware delivery stays modeled."""
from pathlib import Path
import shutil
import subprocess

import test_bootstrap_v2_composition as composition
from test_barrier_protocol import Rv32

ROOT = composition.ROOT
TESTS, CORE = ROOT / 'tests/npu', ROOT / 'firmware/npu'
SITES = {0x84010164: 'npu_emulation_descriptor_callback',
         0x8400d8cc: 'npu_emulation_descriptor_status0',
         0x8400d8fc: 'npu_emulation_descriptor_status2'}
EXTRA_START, EXTRA_BYTES = 0x84088000, 0x4000


def build(destination, parts, page_path, packet_path, tx_path):
    path = destination / 'native-descriptor.elf'
    symbols = {**composition.symbols(page_path), **composition.symbols(packet_path), **composition.symbols(tx_path)}
    command = ['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
               '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
               '-fno-stack-protector', '-nostdlib', '-I' + str(CORE),
               CORE / 'cold-descriptor.c', TESTS / 'cold-descriptor-native-emulation.c',
               TESTS / 'cold-descriptor-native-emulation.S',
               '--ld-path=' + str(shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
               '-Wl,-T,' + str(TESTS / 'cold-descriptor-native-emulation.ld') + ',--no-relax',
               '-Wl,--just-symbols=' + str(parts['base'])]
    for name in ('npu_emulation_cold_arena_live', 'npu_emulation_indication_state',
                 'npu_emulation_packet_state', 'npu_emulation_page_state', 'npu_emulation_tx_state'):
        command.append('-Wl,--defsym=' + name + '=' + hex(symbols[name]))
    command += ['-o', path]
    done = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
    (destination / 'build.log').write_text(done.stdout + done.stderr)
    assert done.returncode == 0, done.stderr
    composition.check_imports(path, parts['base'])
    return path


def install(h, path):
    h.cpu.mem_write(EXTRA_START, bytes(EXTRA_BYTES))
    h.descriptor = Rv32(path, h.cpu)
    for site, name in SITES.items():
        h.install_site(site, h.descriptor.symbols[name], h.code[site - composition.CODE:site - composition.CODE + 4].hex())
    h.cpu.ctl_remove_cache(composition.CODE, composition.CODE + 0x201000)
    h.check_hooks()
    assert len(h.patches) == 77
