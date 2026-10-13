"""Retained selector0/API22 metadata binding in the assembled native pair."""
import shutil
import subprocess

import test_bootstrap_v2_composition as composition
from test_barrier_protocol import Rv32

ROOT = composition.ROOT
TESTS, CORE = ROOT / 'tests/npu', ROOT / 'firmware/npu'
SITES = {0x8400fbb4: 'npu_emulation_rx_event_callback',
         0x8400b5ec: 'npu_emulation_rx_event_b5ec'}
EXTRA_START, EXTRA_BYTES = 0x840d0000, 0x4000


def build(destination, parts, txbuf_path):
    path = destination / 'native-rx-event.elf'
    symbols = composition.symbols(txbuf_path)
    command = ['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
               '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
               '-fno-stack-protector', '-nostdlib', '-I' + str(CORE),
               TESTS / 'cold-rx-event-native-emulation.c', TESTS / 'cold-rx-event-native-emulation.S',
               '--ld-path=' + str(shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
               '-Wl,-T,' + str(TESTS / 'cold-rx-event-native-emulation.ld') + ',--no-relax',
               '-Wl,--just-symbols=' + str(parts['base']),
               '-Wl,--defsym=npu_emulation_txbuf_prior_live=' + hex(symbols['npu_emulation_txbuf_prior_live']),
               '-o', path]
    done = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
    (destination / 'build.log').write_text(done.stdout + done.stderr)
    assert done.returncode == 0, done.stderr
    composition.check_imports(path, parts['base'])
    return path


def install(h, path):
    h.cpu.mem_write(EXTRA_START, bytes(EXTRA_BYTES))
    h.rx_event = Rv32(path, h.cpu)
    for site, name in SITES.items():
        before = h.code[site - composition.CODE:site - composition.CODE + 4]
        assert bytes(h.cpu.mem_read(site, 4)) == before
        after = composition.jump(site, h.rx_event.symbols[name])
        h.cpu.mem_write(site, after)
        h.patches.append(dict(site=hex(site), before=before.hex(), after=after.hex(),
                              target=hex(h.rx_event.symbols[name])))
    h.cpu.ctl_remove_cache(composition.CODE, composition.CODE + 0x201000)
    h.check_hooks()
    assert len(h.patches) == 126
