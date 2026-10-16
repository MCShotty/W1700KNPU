"""Selector10/API0 original store behind completed DESC10 and its pointer owner."""
import shutil
import subprocess

import test_bootstrap_v2_composition as composition
from test_barrier_protocol import Rv32

ROOT = composition.ROOT
TESTS, CORE = ROOT / 'tests/npu', ROOT / 'firmware/npu'
SITES = {0x8400fdc4: 'npu_emulation_rx_pcie_callback',
         0x8400ba88: 'npu_emulation_rx_pcie_ba88'}
EXTRA_START, EXTRA_BYTES = 0x840e4000, 0x4000


def build(destination, parts, descriptor_path, rx_event_path, packet_path):
    path = destination / 'native-rx-pcie.elf'
    symbols = {**composition.symbols(descriptor_path), **composition.symbols(rx_event_path),
               **composition.symbols(packet_path)}
    command = ['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
        '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
        '-fno-stack-protector', '-nostdlib', '-I' + str(CORE), CORE / 'cold-rx-pcie.c',
        TESTS / 'cold-rx-pcie-native-emulation.c', TESTS / 'cold-rx-pcie-native-emulation.S',
        '--ld-path=' + str(shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
        '-Wl,-T,' + str(TESTS / 'cold-rx-pcie-native-emulation.ld') + ',--no-relax',
        '-Wl,--just-symbols=' + str(parts['base'])]
    for name in ('npu_emulation_desc10_state', 'npu_emulation_desc10_prior_live',
                 'npu_emulation_desc10_prior_live_tail',
                 'npu_emulation_desc10_read', 'npu_emulation_rx_event_state',
                 'npu_emulation_packet_state', 'npu_cold_txdone_plan_copy',
                 'npu_cold_txdone_plan_equal', 'npu_cold_txdone_plan_valid',
                 'npu_cold_txdone_memory_live'):
        command.append('-Wl,--defsym=' + name + '=' + hex(symbols[name]))
    command += ['-o', path]
    done = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
    (destination / 'build.log').write_text(done.stdout + done.stderr)
    assert done.returncode == 0, done.stderr
    composition.check_imports(path, parts['base'])
    return path


def install(h, path):
    h.cpu.mem_write(EXTRA_START, bytes(EXTRA_BYTES))
    h.rx_pcie = Rv32(path, h.cpu)
    for site, name in SITES.items():
        before = h.code[site - composition.CODE:site - composition.CODE + 4]
        assert bytes(h.cpu.mem_read(site, 4)) == before
        after = composition.jump(site, h.rx_pcie.symbols[name])
        h.cpu.mem_write(site, after)
        h.patches.append(dict(site=hex(site), before=before.hex(), after=after.hex(),
                              target=hex(h.rx_pcie.symbols[name])))
    h.cpu.ctl_remove_cache(composition.CODE, composition.CODE + 0x201000)
    h.check_hooks()
    assert len(h.patches) == 147
