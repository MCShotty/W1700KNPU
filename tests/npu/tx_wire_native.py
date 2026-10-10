"""Compile/install the retained TX detours; register delivery remains modeled."""
import json
from pathlib import Path
import shutil
import subprocess

import test_bootstrap_v2_composition as composition
from test_barrier_core5 import jump
from test_barrier_protocol import Rv32

ROOT = composition.ROOT
TESTS, CORE = ROOT / 'tests/npu', ROOT / 'firmware/npu'
SITES = {0x8400fc16: 'npu_emulation_tx_callback',
         0x8400fdda: 'npu_emulation_token_callback',
         0x8400d638: 'npu_emulation_tx_meta0', 0x8400d66c: 'npu_emulation_tx_meta2',
         0x8400d4be: 'npu_emulation_tx_index0', 0x8400d4c6: 'npu_emulation_tx_index1',
         0x8400d584: 'npu_emulation_tx_reg0', 0x8400d588: 'npu_emulation_tx_reg1',
         0x8400d5b8: 'npu_emulation_tx_reg2', 0x8400d5be: 'npu_emulation_tx_reg3',
         0x8400dfd0: 'npu_emulation_tx_token'}
EXTRA_START, EXTRA_BYTES = 0x84084000, 0x4000


def build(destination, parts, page_path):
    path = destination / 'native-tx.elf'
    imported = composition.symbols(page_path)
    command = ['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
               '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
               '-fno-stack-protector', '-nostdlib', '-I' + str(CORE),
               CORE / 'cold-tx.c', TESTS / 'cold-tx-native-emulation.c', TESTS / 'cold-tx-native-emulation.S',
               '--ld-path=' + str(shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
               '-Wl,-T,' + str(TESTS / 'cold-tx-native-emulation.ld') + ',--no-relax',
               '-Wl,--just-symbols=' + str(parts['base'])]
    for symbol in ('npu_emulation_cold_arena_live', 'npu_emulation_indication_state'):
        command.append('-Wl,--defsym=' + symbol + '=' + hex(imported[symbol]))
    command += ['-o', path]
    done = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
    (destination / 'build.log').write_text(done.stdout + done.stderr)
    assert done.returncode == 0, done.stderr
    composition.check_imports(path, parts['base'])
    return path


def install(h, path):
    h.cpu.mem_write(EXTRA_START, bytes(EXTRA_BYTES))
    h.tx = Rv32(path, h.cpu)
    for site, symbol in SITES.items():
        h.install_site(site, h.tx.symbols[symbol], h.code[site - composition.CODE:site - composition.CODE + 4].hex())
    h.cpu.ctl_remove_cache(composition.CODE, composition.CODE + 0x201000)
    h.check_hooks()
    assert len(h.patches) == 74
