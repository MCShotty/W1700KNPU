"""All original API21 mutations behind one retained cold owner."""
from pathlib import Path
import shutil
import subprocess

import test_bootstrap_v2_composition as composition
from test_barrier_protocol import Rv32

ROOT = composition.ROOT
TESTS, CORE = ROOT / 'tests/npu', ROOT / 'firmware/npu'
INTERNAL = [0xeeb2, *range(0xeeb8, 0xef2c, 4), 0xef2c]
METADATA = [0xef98, 0xefba, 0xefd8, 0xf014, 0xf062, 0xf092,
            0xa630, 0xa638, 0xa644, 0xa6a6, 0xa6ae, 0xa6c6]
L2 = [0xa672, 0xa678, 0xa67c]
SITES = {0x8400fbca: 'npu_emulation_txbuf_callback'} | {
    0x84000000 + site: 'npu_emulation_txbuf_' + format(site, 'x') for site in INTERNAL + METADATA + L2}
WIDTHS = {0x8400eeb2: 6, 0x8400a672: 6}
EXTRA_START, EXTRA_BYTES = 0x84090000, 0x40000


def build(destination, parts, descriptor_path):
    path = destination / 'native-tx-buffer.elf'
    symbols = composition.symbols(descriptor_path)
    command = ['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
               '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
               '-fno-stack-protector', '-nostdlib', '-I' + str(CORE),
               TESTS / 'cold-tx-buffer-native-emulation.c', TESTS / 'cold-tx-buffer-native-emulation.S',
               '--ld-path=' + str(shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
               '-Wl,-T,' + str(TESTS / 'cold-tx-buffer-native-emulation.ld') + ',--no-relax',
               '-Wl,--just-symbols=' + str(parts['base']),
               '-Wl,--defsym=npu_emulation_descriptor_prior_live=' + hex(symbols['npu_emulation_descriptor_prior_live']),
               '-Wl,--defsym=npu_emulation_descriptor_prior_live_packets=' + hex(symbols['npu_emulation_descriptor_prior_live_packets']),
               '-Wl,--defsym=npu_emulation_descriptor_prior_live_done=' + hex(symbols['npu_emulation_descriptor_prior_live_done'])]
    for site in SITES:
        if site == 0x8400fbca:
            continue
        continuation = site + WIDTHS.get(site, 4)
        command.append('-Wl,--defsym=original_txbuf_' + format(continuation - 0x84000000, 'x') + '=' + hex(continuation))
    command += ['-o', path]
    done = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
    (destination / 'build.log').write_text(done.stdout + done.stderr)
    assert done.returncode == 0, done.stderr
    composition.check_imports(path, parts['base'])
    return path


def install(h, path):
    h.cpu.mem_write(EXTRA_START, bytes(EXTRA_BYTES))
    h.txbuf = Rv32(path, h.cpu)
    for site, name in SITES.items():
        width = WIDTHS.get(site, 4)
        before = h.code[site - composition.CODE:site - composition.CODE + width]
        assert bytes(h.cpu.mem_read(site, width)) == before
        after = composition.jump(site, h.txbuf.symbols[name]) + (b'\x01\x00' if width == 6 else b'')
        h.cpu.mem_write(site, after)
        h.patches.append(dict(site=hex(site), before=before.hex(), after=after.hex(), target=hex(h.txbuf.symbols[name])))
    h.cpu.ctl_remove_cache(composition.CODE, composition.CODE + 0x201000)
    h.check_hooks()
    assert len(h.patches) == 124
