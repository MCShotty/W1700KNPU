"""Original DESC10 constructor behind the retained RX/PKT/store owner."""
import shutil
import subprocess

import test_bootstrap_v2_composition as composition
from test_barrier_protocol import Rv32

ROOT = composition.ROOT
TESTS, CORE = ROOT / 'tests/npu', ROOT / 'firmware/npu'
STORES = [0xb45e, 0xb46a, 0xb530, 0xb53c, 0xb4b6, 0xb4ba, 0xb4c0, 0xb4ce, 0xb4d6,
          0x4a62, 0x9b04, 0x4aac, 0x4ad2, 0x4afa, 0x4b32, 0x4b5c, 0x4b60, 0xb54a, 0xb558]
SITES = {0x8400fe34: 'npu_emulation_desc10_callback',
         0x84004d92: 'npu_emulation_desc10_packet_guard',
         0x84004a3a: 'npu_emulation_desc10_skb_guard',
         0x8400b546: 'npu_emulation_desc10_ready_guard'} | {
    0x84000000 + site: 'npu_emulation_desc10_' + format(site, 'x') for site in STORES}
WIDTHS = {0x8400b4ba: 6}
EXTRA_START, EXTRA_BYTES = 0x840d4000, 0x10000
CONTINUATIONS = [0xb534, 0xb540, 0xb4ba, 0xb4c0, 0xb4c4, 0xb4d2, 0xb4da,
                 0x4a66, 0x9b08, 0x4ab0, 0x4ad6, 0x4afe, 0x4b36, 0x4b60,
                 0x4b64, 0xb54e, 0xb55c, 0x4a3e, 0xb54a, 0xb462, 0xb46e]


def build(destination, parts, packet_path, rx_event_path):
    path = destination / 'native-txdone.elf'
    symbols = {**composition.symbols(packet_path), **composition.symbols(rx_event_path)}
    command = ['clang', '--target=riscv32', '-march=rv32imac_zicsr', '-mabi=ilp32',
        '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
        '-fno-stack-protector', '-nostdlib', '-I' + str(CORE), CORE / 'cold-txdone.c',
        TESTS / 'cold-txdone-native-emulation.c', TESTS / 'cold-txdone-native-emulation.S',
        '--ld-path=' + str(shutil.which('ld.lld') or ROOT / '.local/npu-barrier/lld/usr/lib/llvm-21/bin/ld.lld'),
        '-Wl,-T,' + str(TESTS / 'cold-txdone-native-emulation.ld') + ',--no-relax',
        '-Wl,--just-symbols=' + str(parts['base'])]
    for name in ('npu_emulation_callback_guarded', 'npu_emulation_packet_state',
                 'npu_emulation_packet_plan', 'npu_emulation_packet_last', 'npu_emulation_packet_live',
                 'npu_emulation_packet_callback', 'npu_emulation_packet_take', 'npu_emulation_packet_guard',
                 'npu_emulation_rx_event_state', 'npu_emulation_rx_event_prior_live',
                 'npu_emulation_rx_event_prior_live_done', 'npu_emulation_rx_event_prior_live_tail',
                 'npu_emulation_rx_event_prior_live_inode'):
        command.append('-Wl,--defsym=' + name + '=' + hex(symbols[name]))
    previous = composition.symbols(parts['txdone'])
    for name in ('npu_emulation_txdone_skb_valid',):
        command.append('-Wl,--defsym=' + name + '=' + hex(previous[name]))
    command.append('-Wl,--defsym=npu_previous_txdone_lock20_guard=' +
                   hex(previous['npu_emulation_txdone_lock20_guard']))
    for offset in CONTINUATIONS:
        command.append('-Wl,--defsym=original_desc10_' + format(offset, 'x') + '=' + hex(0x84000000 + offset))
    command += ['-o', path]
    done = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
    (destination / 'build.log').write_text(done.stdout + done.stderr)
    assert done.returncode == 0, done.stderr
    composition.check_imports(path, parts['base'])
    return path


def install(h, path):
    h.cpu.mem_write(EXTRA_START, bytes(EXTRA_BYTES))
    h.desc10 = Rv32(path, h.cpu)
    for site, name in SITES.items():
        width = WIDTHS.get(site, 4)
        previous = next((p for p in h.patches if int(p['site'], 16) == site), None)
        after = composition.jump(site, h.desc10.symbols[name]) + (b'\x01\x00' if width == 6 else b'')
        if previous:
            assert bytes(h.cpu.mem_read(site, width)).hex() == previous['after']
            previous.update(after=after.hex(), target=hex(h.desc10.symbols[name]))
        else:
            before = h.code[site - composition.CODE:site - composition.CODE + width]
            assert bytes(h.cpu.mem_read(site, width)) == before
            h.patches.append(dict(site=hex(site), before=before.hex(), after=after.hex(),
                                 target=hex(h.desc10.symbols[name])))
        h.cpu.mem_write(site, after)
    h.cpu.ctl_remove_cache(composition.CODE, composition.CODE + 0x201000)
    h.check_hooks()
    assert len(h.patches) == 145
