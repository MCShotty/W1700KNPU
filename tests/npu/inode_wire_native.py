"""Original API24 wrapper/eleven stores with retained constructor ownership."""
import shutil
import subprocess

import test_bootstrap_v2_composition as composition
from test_barrier_protocol import Rv32

ROOT = composition.ROOT
TESTS, CORE = ROOT / 'tests/npu', ROOT / 'firmware/npu'
STORES = (0xe0c4, 0xe0ce, 0xe0d8, 0xe0e0, 0xe0e8, 0xe0f0,
          0xe178, 0xe180, 0xe18a, 0xe196, 0xe1b4)
SITES = {0x8400fc2c: 'npu_emulation_inode_callback'} | {
    0x84000000 + site: 'npu_emulation_inode_' + format(site, 'x') for site in STORES}
EXTRA_START, EXTRA_BYTES = 0x840f0000, 0x8000


def build(destination, parts, tail_path, rx_pcie_path, tx_path, desc10_path, rx_event_path, packet_path):
    path = destination / 'native-inode.elf'
    symbols = {}
    for component in (tail_path, rx_pcie_path, tx_path, desc10_path, rx_event_path, packet_path):
        symbols.update(composition.symbols(component))
    command = ['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
        '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
        '-fno-stack-protector', '-nostdlib', '-I' + str(CORE), CORE / 'cold-inode.c',
        TESTS / 'cold-inode-native-emulation.c', TESTS / 'cold-inode-native-stores.S',
        TESTS / 'cold-inode-native-callback.S',
        '--ld-path=' + str(shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
        '-Wl,-T,' + str(TESTS / 'cold-inode-native-emulation.ld') + ',--no-relax',
        '-Wl,--just-symbols=' + str(parts['base'])]
    for name in ('npu_emulation_pcie_tail_state', 'npu_emulation_pcie_tail_prior_live_inode',
                 'npu_emulation_pcie_tail_read_inode', 'npu_cold_pcie_tail_plan_valid', 'npu_cold_pcie_tail_live',
                 'npu_emulation_rx_pcie_state', 'npu_emulation_tx_state', 'npu_emulation_desc10_state',
                 'npu_emulation_desc10_read', 'npu_emulation_rx_event_state', 'npu_emulation_packet_state'):
        command.append('-Wl,--defsym=' + name + '=' + hex(symbols[name]))
    command += ['-o', path]
    completed = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
    (destination / 'build.log').write_text(completed.stdout + completed.stderr)
    assert completed.returncode == 0, completed.stderr
    composition.check_imports(path, parts['base'])
    return path


def install(h, path):
    h.cpu.mem_write(EXTRA_START, bytes(EXTRA_BYTES))
    h.inode = Rv32(path, h.cpu)
    original = h.inode.symbols['npu_original_inode_callback']
    assert bytes(h.cpu.mem_read(original, 4)) == h.code[0xfc2c:0xfc30]
    for site, name in SITES.items():
        before = h.code[site - composition.CODE:site - composition.CODE + 4]
        assert bytes(h.cpu.mem_read(site, 4)) == before
        after = composition.jump(site, h.inode.symbols[name])
        h.cpu.mem_write(site, after)
        h.patches.append(dict(site=hex(site), before=before.hex(), after=after.hex(),
                              target=hex(h.inode.symbols[name])))
    h.cpu.ctl_remove_cache(composition.CODE, composition.CODE + 0x201000)
    h.check_hooks()
    assert len(h.patches) == 168
