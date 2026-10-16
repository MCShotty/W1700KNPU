"""Bind PCIe0/2/15 to completed prior owners and all nine original stores."""
import shutil
import subprocess

import test_bootstrap_v2_composition as composition
from test_barrier_protocol import Rv32

ROOT = composition.ROOT
TESTS, CORE = ROOT / 'tests/npu', ROOT / 'firmware/npu'
STORES = (0xb9ae, 0xb9c0, 0xb9d2, 0xb9ea, 0xba00, 0xba0c, 0xba18, 0xba24, 0xba30)
SITES = {0x8400fdc4: 'npu_emulation_pcie_tail_callback'} | {
    0x84000000 + site: 'npu_emulation_pcie_tail_' + format(site, 'x') for site in STORES}
WIDTHS = {0x84000000 + site: 6 for site in (0xb9ae, 0xb9c0, 0xb9d2, 0xb9ea)}
EXTRA_START, EXTRA_BYTES = 0x840e8000, 0x8000
MODEL_BAR_PAGES = (0x2000a000, 0x200d4000, 0x200d8000)


def build(destination, parts, rx_pcie_path, desc10_path, rx_event_path, packet_path, tx_path):
    path = destination / 'native-pcie-tail.elf'
    symbols = {}
    for component in (rx_pcie_path, desc10_path, rx_event_path, packet_path, tx_path):
        symbols.update(composition.symbols(component))
    command = ['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
        '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
        '-fno-stack-protector', '-nostdlib', '-I' + str(CORE), CORE / 'cold-pcie-tail.c',
        TESTS / 'cold-pcie-tail-native-emulation.c', TESTS / 'cold-pcie-tail-native-stores.S',
        '--ld-path=' + str(shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
        '-Wl,-T,' + str(TESTS / 'cold-pcie-tail-native-emulation.ld') + ',--no-relax',
        '-Wl,--just-symbols=' + str(parts['base'])]
    for name in ('npu_emulation_rx_pcie_state', 'npu_emulation_rx_pcie_prior_live_tail',
                 'npu_emulation_rx_pcie_prior_live_inode',
                 'npu_emulation_rx_pcie_callback', 'npu_cold_rx_pcie_plan_valid', 'npu_cold_rx_pcie_live',
                 'npu_emulation_desc10_state', 'npu_emulation_desc10_read',
                 'npu_cold_txdone_plan_valid', 'npu_cold_txdone_plan_equal',
                 'npu_emulation_rx_event_state', 'npu_emulation_packet_state', 'npu_emulation_tx_state'):
        command.append('-Wl,--defsym=' + name + '=' + hex(symbols[name]))
    command += ['-o', path]
    done = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
    (destination / 'build.log').write_text(done.stdout + done.stderr)
    assert done.returncode == 0, done.stderr
    composition.check_imports(path, parts['base'])
    return path


def install(h, path):
    h.cpu.mem_write(EXTRA_START, bytes(EXTRA_BYTES))
    h.pcie_tail = Rv32(path, h.cpu)
    h.pcie_tail_model_pages = MODEL_BAR_PAGES
    for base in MODEL_BAR_PAGES:
        regions = list(h.cpu.mem_regions())
        assert not any(start < base + 4096 and base < end + 1 for start, end, _ in regions)
        h.cpu.mem_map(base, 4096)
    for site, name in SITES.items():
        width = WIDTHS.get(site, 4)
        previous = next((p for p in h.patches if int(p['site'], 16) == site), None)
        after = composition.jump(site, h.pcie_tail.symbols[name]) + (b'\x01\x00' if width == 6 else b'')
        if previous:
            assert site == 0x8400fdc4 and previous['target'] == hex(h.rx_pcie.symbols['npu_emulation_rx_pcie_callback'])
            assert bytes(h.cpu.mem_read(site, width)).hex() == previous['after']
            previous.update(after=after.hex(), target=hex(h.pcie_tail.symbols[name]))
        else:
            before = h.code[site - composition.CODE:site - composition.CODE + width]
            assert bytes(h.cpu.mem_read(site, width)) == before
            h.patches.append(dict(site=hex(site), before=before.hex(), after=after.hex(),
                                  target=hex(h.pcie_tail.symbols[name])))
        h.cpu.mem_write(site, after)
    h.cpu.ctl_remove_cache(composition.CODE, composition.CODE + 0x201000)
    h.check_hooks()
    assert len(h.patches) == 156
