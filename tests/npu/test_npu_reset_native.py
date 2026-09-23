#!/usr/bin/env python3
"""Execute the actual before/after AArch64 reset callbacks with modeled regmap."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import arm64_const as arm
import unicorn

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-23-npu-reset-control'
PRIOR = OUT / 'reset-control.json'
CODE, DATA, STACK, END = 0x10000000, 0x41000000, 0x42000000, 0x43000000
BANKS, IDS, MAP, SPEC = DATA + 0x1000, DATA + 0x2000, DATA + 0x3000, DATA + 0x4000
SP = STACK + 0x8000
NAMES = ('en7523_reset_assert', 'en7523_reset_deassert', 'en7523_reset_status', 'en7523_reset_xlate')
REGS = [getattr(arm, 'UC_ARM64_REG_X' + str(i)) for i in range(29)] + [arm.UC_ARM64_REG_X29, arm.UC_ARM64_REG_X30]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signed(value):
    return struct.unpack('<i', struct.pack('<I', value & 0xffffffff))[0]


class Target:
    def __init__(self, row):
        path = ROOT / row['object']['path']
        assert sha(path) == row['object']['sha256']
        elf = ELFFile(io.BytesIO(path.read_bytes()))
        self.symbols = {s.name: s for s in elf.get_section_by_name('.symtab').iter_symbols()}
        self.text = elf.get_section_by_name('.text').data()
        self.layout = row['layout']
        self.profile = row['profile']
        self.ranges = {name: (self.symbols[name]['st_value'],
                             self.symbols[name]['st_value'] + self.symbols[name]['st_size']) for name in NAMES}
        self.arrays = {}
        for name in ('en7581_rst_ofs', 'en7523_rst_map', 'en7581_rst_map', 'an7583_rst_map'):
            symbol = self.symbols[name]
            data = elf.get_section(symbol['st_shndx']).data()
            data = data[symbol['st_value']:symbol['st_value'] + symbol['st_size']]
            self.arrays[name] = list(struct.unpack('<' + 'H' * (len(data) // 2), data))
        self.calls = {}
        relocations = elf.get_section_by_name('.rela.text')
        table = elf.get_section(relocations['sh_link'])
        for reloc in relocations.iter_relocations():
            offset = reloc['r_offset']
            owner = next((name for name, (lo, hi) in self.ranges.items() if lo <= offset < hi), None)
            if owner is None:
                continue
            name = table.get_symbol(reloc['r_info_sym']).name
            assert reloc['r_info_type'] == 283 and reloc['r_addend'] == 0
            assert name in ('regmap_update_bits_base', 'regmap_read')
            self.calls[CODE + offset] = name
        assert len(self.calls) == 3
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.uc.mem_map(CODE, (len(self.text) + 0xfff) & ~0xfff)
        self.uc.mem_write(CODE, self.text)
        self.uc.mem_map(DATA, 0x6000)
        self.uc.mem_map(STACK, 0x10000)
        self.uc.mem_map(END, 0x1000)
        self.uc.hook_add(UC_HOOK_CODE, self.code)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, self.write)
        self.total = 0
        self.digest = hashlib.sha256()

    def write(self, uc, _access, address, size, _value, _user):
        assert SP - 128 <= address < SP and address + size <= SP, (self.name, hex(address), size)

    def code(self, uc, address, _size, _user):
        low, high = self.ranges[self.name]
        assert CODE + low <= address < CODE + high, (self.name, hex(address))
        if address not in self.calls:
            return
        args = [uc.reg_read(register) for register in REGS[:7]]
        assert args[0] == MAP
        addr = args[1] & 0xffffffff
        assert addr in self.arrays['en7581_rst_ofs']
        self.events.append(dict(function=self.calls[address], offset=hex(address - CODE), address=addr))
        if self.calls[address] == 'regmap_read':
            assert self.name == 'en7523_reset_status'
            assert SP - 128 <= args[2] <= SP - 4
            if not self.error:
                uc.mem_write(args[2], struct.pack('<I', self.seed))
            elif self.output is not None:
                uc.mem_write(args[2], struct.pack('<I', self.output))
        else:
            mask, value = args[2] & 0xffffffff, args[3] & 0xffffffff
            assert args[4:] == [0, 0, 0]
            self.events[-1].update(mask=mask, value=value)
            if not self.error or self.commit:
                self.word = (self.seed & ~mask) | (value & mask)
        # Model a normal external AAPCS64 call, including caller-saved clobbers.
        for index in range(1, 19):
            uc.reg_write(REGS[index], 0xbad00000 + index)
        uc.reg_write(REGS[0], self.error & 0xffffffff)
        uc.reg_write(arm.UC_ARM64_REG_X30, address + 4)
        uc.reg_write(arm.UC_ARM64_REG_PC, address + 4)

    def call(self, name, variant, logical, seed=0, error=0, commit=False, output=None):
        self.name, self.seed, self.word, self.error = name, seed, seed, error
        self.commit, self.output, self.events = commit, output, []
        ids = self.arrays[variant]
        size, bankoff, idoff, mapoff, rcdev, countoff, argsoff = self.layout[:7]
        payload = bytearray(size)
        for offset, address in ((bankoff, BANKS), (idoff, IDS), (mapoff, MAP)):
            struct.pack_into('<Q', payload, offset, address)
        struct.pack_into('<I', payload, rcdev + countoff, len(ids))
        self.uc.mem_write(DATA, bytes(payload))
        self.uc.mem_write(BANKS, struct.pack('<3H', *self.arrays['en7581_rst_ofs']))
        self.uc.mem_write(IDS, struct.pack('<' + 'H' * len(ids), *ids))
        self.uc.mem_write(STACK, b'\xaa' * 0x10000)
        self.uc.mem_write(SPEC + argsoff, struct.pack('<I', logical))
        for index, reg in enumerate(REGS):
            self.uc.reg_write(reg, 0x50000000 + index)
        self.uc.reg_write(REGS[0], DATA + rcdev)
        self.uc.reg_write(REGS[1], SPEC if name.endswith('xlate') else ids[logical])
        self.uc.reg_write(arm.UC_ARM64_REG_SP, SP)
        self.uc.reg_write(arm.UC_ARM64_REG_X30, END)
        self.uc.reg_write(arm.UC_ARM64_REG_NZCV, 0)
        self.uc.emu_start(CODE + self.ranges[name][0], END, count=300)
        assert self.uc.reg_read(arm.UC_ARM64_REG_PC) == END
        assert self.uc.reg_read(arm.UC_ARM64_REG_SP) == SP
        assert all(self.uc.reg_read(REGS[i]) == 0x50000000 + i for i in range(19, 30))
        assert bytes(self.uc.mem_read(DATA, size)) == payload
        result = signed(self.uc.reg_read(REGS[0]))
        record = dict(function=name, variant=variant, logical=logical, seed=seed,
                      error=error, commit=commit, output=output, result=result,
                      word=self.word, events=self.events)
        self.digest.update(json.dumps(record, sort_keys=True).encode() + b'\n')
        self.total += 1
        return record


def main():
    options = argparse.ArgumentParser()
    options.add_argument('--output-dir', type=Path, default=OUT)
    args = options.parse_args()
    out = args.output_dir.resolve()
    assert out == OUT or out.is_relative_to((ROOT / '.local').resolve())
    assert not (out / 'reset-native.json').exists()
    out.mkdir(parents=True, exist_ok=True)
    assert sha(PRIOR) == 'c627c45569b2e142b635f68a6ced59460749232f184bc99fe5215bf672a60c7d'
    prior = json.loads(PRIOR.read_text())
    targets = [Target(row) for row in prior['kernel_objects']]
    assert targets[0].arrays == targets[1].arrays
    summaries, witnesses = [], []
    for target in targets:
        fault_count = 0
        for variant in ('en7523_rst_map', 'en7581_rst_map', 'an7583_rst_map'):
            ids = target.arrays[variant]
            for logical, hardware in enumerate(ids):
                row = target.call('en7523_reset_xlate', variant, logical)
                assert row['result'] == hardware and not row['events']
                address = target.arrays['en7581_rst_ofs'][hardware // 32]
                mask, inverted = 1 << (hardware % 32), address == 0x88
                for seed in (0, 0xffffffff, 0xaaaaaaaa, 0x55555555):
                    for asserted in (False, True):
                        name = 'en7523_reset_assert' if asserted else 'en7523_reset_deassert'
                        row = target.call(name, variant, logical, seed)
                        value = mask if asserted != inverted else 0
                        assert row['result'] == 0 and row['word'] == (seed & ~mask) | value
                        assert len(row['events']) == 1
                        assert (row['events'][0]['address'], row['events'][0]['mask'], row['events'][0]['value']) == (address, mask, value)
                    row = target.call('en7523_reset_status', variant, logical, seed)
                    assert row['result'] == (bool(seed & mask) != inverted) and row['word'] == seed
                    assert len(row['events']) == 1 and row['events'][0]['address'] == address
                for error in (-5, -110, -11):
                    for asserted in (False, True):
                        for commit in (False, True):
                            name = 'en7523_reset_assert' if asserted else 'en7523_reset_deassert'
                            row = target.call(name, variant, logical, 0x55555555, error, commit)
                            value = mask if asserted != inverted else 0
                            assert row['result'] == (error if target.profile == 'after' else 0)
                            assert row['word'] == (((0x55555555 & ~mask) | value) if commit else 0x55555555)
                            assert len(row['events']) == 1
                            fault_count += 1
                            if variant == 'en7581_rst_map' and logical == 8 and error == -5 and asserted and not commit:
                                witnesses.append(dict(profile=target.profile, **row))
                    for output in (None, 0, 0xffffffff):
                        row = target.call('en7523_reset_status', variant, logical, 0, error, output=output)
                        expected = error if target.profile == 'after' else (bool((0xaaaaaaaa if output is None else output) & mask) != inverted)
                        assert row['result'] == expected and row['word'] == 0
                        assert len(row['events']) == 1
                        fault_count += 1
                        if variant == 'en7581_rst_map' and logical == 8 and error == -110 and output is None:
                            witnesses.append(dict(profile=target.profile, **row))
            for invalid in (len(ids), len(ids) + 1, 0xffffffff):
                row = target.call('en7523_reset_xlate', variant, invalid)
                assert row['result'] == -22 and not row['events']
        summaries.append(dict(profile=target.profile, executions=target.total,
                              fault_cases=fault_count, observations_sha256=target.digest.hexdigest()))
        print(json.dumps(summaries[-1]), flush=True)
    inputs = [Path(__file__), PRIOR]
    for row in prior['kernel_objects']:
        inputs += [ROOT / row[key]['path'] for key in ('object', 'probe')]
    receipt = dict(schema=1, inputs={str(p.relative_to(ROOT)): sha(p) for p in inputs},
                   unicorn_version=unicorn.__version__, profiles=summaries,
                   layout=targets[0].layout, maps=targets[0].arrays, npu_failure_witnesses=witnesses,
                   limits=['Actual target-compiled reset callback and translator instructions execute; regmap I/O, memory and call delivery are modeled.',
                           'The pinned GCC target binary resolves the indeterminate source local to zero in these callbacks; its nominal polarity matches the correction.',
                           'The original target binary still hides every injected write/read error. Pattern-init source controls are not claimed as live-target failures.',
                           'No MMIO hardware, physical reset coverage/drain, probe containment, module loading or production NPU integration is established.'])
    path = out / 'reset-native.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(receipt_sha256=sha(path), executions=sum(r['executions'] for r in summaries))), flush=True)


if __name__ == '__main__':
    main()
