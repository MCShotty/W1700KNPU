#!/usr/bin/env python3
"""Pinned native reset/lookup instructions under a bounded, non-production map."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from unicorn import Uc, UcError, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE
from unicorn import riscv_const as r

from emulation_layout import CODE, SRAM, SRAM_BYTES, HEAP, HEAP_BYTES, STATE, map_sram
from test_firmware_stop_counterexample import INPUT, CODE_SHA, DATA_SHA, END, PRINTF, HART_ID

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-06-npu-layout'
BUILD = ROOT / '.local/npu-barrier'
FIT = ROOT / '.build/openwrt/bin/targets/airoha/an7581/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb'
BSS_START, BSS_END = SRAM + 0xc10, SRAM + 0x4754
STACK_TOPS = [0x84021e00 + hart * 0x4000 for hart in range(8)]
SOURCE_URL = 'https://github.com/merbanan/airoha_ml/blob/92f7959aa1750e428d10efbeb21360e0955c1895/en7581-base.dtsi'


def sha(data):
    return hashlib.sha256(data).hexdigest()


class NativeMemory:
    def __init__(self):
        self.code = (INPUT / 'en7581_MT7996_npu_rv32.bin').read_bytes()
        data = (INPUT / 'en7581_MT7996_npu_data.bin').read_bytes()
        assert sha(self.code) == CODE_SHA and sha(data) == DATA_SHA
        self.cpu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        self.cpu.mem_map(CODE, 0x201000)
        self.cpu.mem_write(CODE, self.code)
        map_sram(self.cpu)
        self.cpu.mem_write(SRAM, data)
        self.cpu.mem_map(0x1ec0c000, 0x1000)
        self.cpu.mem_map(0x1ec03000, 0x1000)
        # Single-hart mutex owner readback is modeled, not a concurrency test.
        self.put32(0x1ec03048, 0x10000)
        self.cpu.hook_add(UC_HOOK_CODE, self.skip, begin=PRINTF, end=PRINTF)
        self.cpu.hook_add(UC_HOOK_CODE, self.skip, begin=HART_ID, end=HART_ID)
        self.cpu.reg_write(r.UC_RISCV_REG_GP, SRAM + 0x13a8)

    def set_hart(self, hart):
        def read_hart(cpu, address, size, _):
            assert self.get32(address) == 0xf14022f3  # csrr t0,mhartid
            cpu.reg_write(r.UC_RISCV_REG_T0, hart)
            cpu.reg_write(r.UC_RISCV_REG_PC, address + 4)

        # Unicorn ignores writes to MHARTID. Substitute only this CSR result.
        for offset in (0x24, 0x2e, 0x38, 0x42, 0x4c, 0x56, 0x60, 0x6a):
            self.cpu.hook_add(UC_HOOK_CODE, read_hart, begin=CODE + offset, end=CODE + offset)

    def skip(self, cpu, address, size, _):
        cpu.reg_write(r.UC_RISCV_REG_A0, 0)
        cpu.reg_write(r.UC_RISCV_REG_PC, cpu.reg_read(r.UC_RISCV_REG_RA))

    def put32(self, address, value):
        self.cpu.mem_write(address, struct.pack('<I', value))

    def get32(self, address):
        return struct.unpack('<I', self.cpu.mem_read(address, 4))[0]

    def call(self, address, *args):
        self.cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[0])
        self.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        for index, value in enumerate(args):
            self.cpu.reg_write(getattr(r, 'UC_RISCV_REG_A' + str(index)), value)
        self.cpu.emu_start(address, END, count=2000000, timeout=3000000)
        assert self.cpu.reg_read(r.UC_RISCV_REG_PC) == END, hex(address)
        return self.cpu.reg_read(r.UC_RISCV_REG_A0)


def native_reset():
    results = []
    for hart in range(8):
        for warm in (False, True):
            h = NativeMemory()
            h.cpu.mem_write(BSS_START - 4, b'\xa5' * (BSS_END - BSS_START + 8))
            h.cpu.mem_write(STATE, b'\x96' * 0x158)
            h.set_hart(hart)
            h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 8)
            h.put32(0x1ec0c140, 0xffffffff if warm else 0)
            h.cpu.emu_start(CODE, CODE + 0xf0, count=30000, timeout=1000000)
            assert h.cpu.reg_read(r.UC_RISCV_REG_PC) == CODE + 0xf0
            assert h.cpu.reg_read(r.UC_RISCV_REG_SP) == STACK_TOPS[hart], (
                hart, hex(h.cpu.reg_read(r.UC_RISCV_REG_SP)), hex(STACK_TOPS[hart]),
                h.cpu.reg_read(r.UC_RISCV_REG_MHARTID))
            assert h.cpu.reg_read(r.UC_RISCV_REG_GP) == SRAM + 0x13a8
            assert not h.cpu.reg_read(r.UC_RISCV_REG_MSTATUS) & 8
            expected = 0 if hart == 0 and not warm else 0xa5
            assert bytes(h.cpu.mem_read(BSS_START, BSS_END - BSS_START)) == bytes([expected]) * (BSS_END - BSS_START)
            assert h.get32(BSS_START - 4) == h.get32(BSS_END) == 0xa5a5a5a5
            assert bytes(h.cpu.mem_read(STATE, 0x158)) == b'\x96' * 0x158
            results.append({'hart': hart, 'mailbox_word_all_ones': warm,
                            'bss_cleared': expected == 0, 'stack': hex(STACK_TOPS[hart])})
    return results


def table(code, address):
    rows = []
    for index in range(100):
        offset = address - CODE + index * 8
        assert 0 <= offset <= len(code) - 8
        kind, alignment, reserved, value = struct.unpack_from('<HBBI', code, offset)
        if kind == 0xffff:
            return rows
        assert kind not in [row['type'] for row in rows]
        rows.append({'type': kind, 'alignment_tag': alignment, 'reserved': reserved, 'value': value})
    raise AssertionError('unterminated table')


def native_lookup():
    h = NativeMemory()
    tables = {name: table(h.code, address) for name, address in (
        ('dynamic_low', 0x8401cfc8), ('dynamic_high', 0x8401b224),
        ('fixed_low', 0x8401cf70), ('fixed_high', 0x8401b20c))}
    h.cpu.mem_write(HEAP, b'\xa5' * HEAP_BYTES)
    h.call(0x84005296)
    assert bytes(h.cpu.mem_read(HEAP, HEAP_BYTES)) == bytes(HEAP_BYTES)
    assert h.get32(SRAM + 0x1bcc) == 0x12
    assert h.get32(SRAM + 0x1f10) == HEAP
    assert h.get32(SRAM + 0x1bd4) == h.get32(SRAM + 0x1be0) == 0
    checks = 0
    for name, rows in tables.items():
        for row in rows:
            h.put32(SRAM + 0x1bd4, 0)
            h.put32(SRAM + 0x1be0, 0)
            result = h.call(0x84005200, row['type'])
            assert result == (row['value'] if name.startswith('fixed') else HEAP)
            if name.startswith('dynamic'):
                assert h.get32(SRAM + 0x1be0) == row['value']
                assert h.call(0x84005200, row['type']) == result
                assert h.get32(SRAM + 0x1bd4) == 1
                # Native rounding with an unaligned existing heap offset.
                h.put32(SRAM + 0x1bd4, 0)
                h.put32(SRAM + 0x1be0, 1)
                align = 16 if row['alignment_tag'] == 1 else 32
                assert h.call(0x84005200, row['type']) == HEAP + align
                assert h.get32(SRAM + 0x1be0) == align + row['value']
            else:
                assert 0x3e880000 <= result < 0x3e8c0000
            checks += 1
    for address in (SRAM + SRAM_BYTES, 0x3e910000, 0x3e920000, HEAP + HEAP_BYTES):
        try:
            h.cpu.mem_read(address, 4)
        except UcError:
            continue
        raise AssertionError('out-of-window fixture is mapped: ' + hex(address))
    return {'tables': tables, 'table_entries_checked': checks,
            'native_allocator_init': True, 'old_virtual_state_unmapped': True,
            'extent_note': 'Fixed entries contain start addresses, not allocation lengths; no dynamic caller closure asserted.'}


def fdt(dtb, node, prop=None, kind='s'):
    args = ['fdtget', '-t', kind, str(dtb), node, prop] if prop else ['fdtget', '-l', str(dtb), node]
    result = subprocess.check_output(args, text=True).strip()
    return [int(word, 16) for word in result.split()] if kind == 'x' else result


def board_map():
    dtb = BUILD / 'w1700k-r1.dtb'
    BUILD.mkdir(parents=True, exist_ok=True)
    subprocess.run(['dumpimage', '-T', 'flat_dt', '-p', '1', '-o', str(dtb), str(FIT)],
                   check=True, stdout=subprocess.PIPE, text=True)
    fit_bytes = FIT.read_bytes()
    assert sha(fit_bytes) == '0788f405337ceb030d873463bbf278497dcd9b86e8f75a1a3f57fd318eda195f'
    assert fdt(FIT, '/configurations', 'default') == 'config-1'
    assert fdt(FIT, '/configurations/config-1', 'fdt') == 'fdt-1'
    assert hashlib.sha1(dtb.read_bytes()).hexdigest() == '87f9deb7de897756f792628ff475d2451cd674de'
    assert fdt(dtb, '/', 'model') == 'Gemtek W1700K (OpenWrt U-Boot layout)'
    assert fdt(dtb, '/', 'compatible').split()[0] == 'gemtek,w1700k-ubi'
    npu = '/soc/npu@1e900000'
    assert fdt(dtb, npu, 'status') == 'okay'
    assert fdt(dtb, npu, 'reg', 'x') == [0, 0x1e900000, 0, 0x313000]
    reserved = {}
    for name in fdt(dtb, '/reserved-memory').splitlines():
        cells = fdt(dtb, '/reserved-memory/' + name, 'reg', 'x')
        assert len(cells) == 4
        reserved[name] = {'start': (cells[0] << 32) | cells[1], 'size': (cells[2] << 32) | cells[3]}
    assert reserved['npu-binary@84000000'] == {'start': CODE, 'size': 0xa00000}
    regions = fdt(dtb, npu, 'memory-region', 'x')
    ordered = ['npu-binary@84000000', 'npu-pkt@8a000000', 'npu-txpkt@8cc00000',
               'npu-txbufid@90c00000', 'npu-ba@90c06800']
    assert regions == [fdt(dtb, '/reserved-memory/' + name, 'phandle', 'x')[0] for name in ordered]
    assert CODE + (INPUT / 'en7581_MT7996_npu_rv32.bin').stat().st_size <= STACK_TOPS[0] - 0x4000
    assert STACK_TOPS[-1] <= 0x84040000 < 0x84048000 < CODE + 0x200000
    ref = BUILD / 'en7581-base-92f7959.dtsi'
    reference = ref.read_text()
    assert 'NPU 32K SRAM' in reference and 'NPU 480K SRAM' in reference
    return {'fit_sha256': sha(fit_bytes), 'dtb_sha256': sha(dtb.read_bytes()),
            'reserved_memory': reserved, 'npu_memory_region_order': ordered,
            'native_bss': [hex(BSS_START), hex(BSS_END)],
            'candidate_state': [hex(STATE), hex(STATE + 0x158)],
            'local_sram_test_bound': SRAM_BYTES, 'reference_url': SOURCE_URL,
            'reference_sha256': sha(ref.read_bytes()),
            'boundary': 'DTB reg includes SRAM and registers; the 32KiB RAM bound comes from a separate reference DTS, not this board DTB or hardware.'}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = {'status': 'PASS', 'code_sha256': CODE_SHA, 'data_sha256': DATA_SHA,
              'reset_cases': native_reset(), 'lookup': native_lookup(), 'board': board_map(),
              'scope': 'Original instructions and retained R1 FIT; no full boot, live MMIO, cache, DMA or production reservation proof.'}
    (OUT / 'native-memory-layout.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'reset_cases': len(result['reset_cases']),
                      'table_entries': result['lookup']['table_entries_checked']}))


if __name__ == '__main__':
    main()
