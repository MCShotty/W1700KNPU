#!/usr/bin/env python3
"""Original INODE payload extent and native 2/7/4 effects, not readiness."""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
from unicorn import riscv_const as r

from test_attach_rx_callbacks import (Closure, Trace, ELF, ELF_SHA, IMAGES,
                                      images, digest, PARENTS)
from test_bootstrap_native import ROOT, sha, BOOT, ADM
from test_boot_irq_installation import UnmodeledAccess
from test_firmware_memory_layout import STACK_TOPS
from test_firmware_mailbox_dispatch import MBOX, PAYLOAD
from test_firmware_stop_counterexample import INPUT, CODE_SHA, DATA_SHA, END
from test_mt7996_bootstrap_sequence import exports, GHIDRA, GHIDRA_SHA
from emulation_layout import CODE, SRAM

OUT = ROOT/'research/checkpoints/2026-09-06-npu-inode/native-inode.json'
CALLBACK, HELPER = 0x8400fc2c, 0x8400e084
ICV_BYTES = 0x1008
RX_SHA = 'c7b04924b71e9a09fef3eeba3c1143381a5a1e67157f51b1e341a1910e37f100'


class PayloadExtent(Exception):
    pass


class InodeTrace(Trace):
    def __init__(self, declared, enforce):
        super().__init__()
        self.declared, self.enforce = declared, enforce
        self.payload = []

    def access(self, h, address, size, value, write):
        if PAYLOAD <= address < PAYLOAD+256:
            assert not write and address+size <= PAYLOAD+256
            outside = address+size > PAYLOAD+self.declared
            self.payload.append(dict(pc=hex(h.cpu.reg_read(r.UC_RISCV_REG_PC)),
                                     offset=address-PAYLOAD, size=size,
                                     value=hex(value), outside_declared=outside))
            if outside and self.enforce:
                raise PayloadExtent(f'payload read {address-PAYLOAD}+{size} exceeds {self.declared}')
            return
        super().access(h, address, size, value, write)

    def code(self, h, pc):
        if pc in (CALLBACK, HELPER):
            self.entries[pc] += 1
            self.first_args.setdefault(pc, [h.cpu.reg_read(getattr(r, f'UC_RISCV_REG_A{i}'))
                                            for i in range(5)])


class InodeClosure(Closure):
    def __init__(self, path, exported):
        super().__init__(path, exported)
        self.code_image = bytes(self.h.cpu.mem_read(CODE, len(self.h.code)))

    def invoke_inode(self, frame, declared=None, enforce=False, entry_only=False):
        h = self.h
        declared = len(frame) if declared is None else declared
        assert 0 <= declared <= 256 and len(frame) <= 256
        # Match the retained provider bounce: copy only len, leaving previous tail.
        h.cpu.mem_write(PAYLOAD, b'\xa5'*256)
        h.cpu.mem_write(PAYLOAD, frame)
        h.put32(MBOX+0x34, declared)
        h.put32(MBOX+0x3c, 1)
        h.cpu.reg_write(r.UC_RISCV_REG_SP, STACK_TOPS[0])
        h.cpu.reg_write(r.UC_RISCV_REG_RA, END)
        h.cpu.reg_write(r.UC_RISCV_REG_A0, PAYLOAD)
        h.cpu.reg_write(r.UC_RISCV_REG_MSTATUS, 0)
        h.unmodeled = None
        self.trace = trace = InodeTrace(declared, enforce)
        error, result, arguments = None, None, None
        try:
            reached = h.run(CALLBACK, [HELPER] if entry_only else [])
            assert reached == (HELPER if entry_only else END)
            if entry_only:
                arguments = [h.cpu.reg_read(getattr(r, f'UC_RISCV_REG_A{i}')) for i in range(5)]
            else:
                result = h.cpu.reg_read(r.UC_RISCV_REG_A0)
                arguments = trace.first_args[HELPER]
        except (UnmodeledAccess, PayloadExtent) as exc:
            error = str(exc)
        finally:
            self.trace = None
        assert set(h.stub_counts) <= {'0x840048f4'}, h.stub_counts
        assert set(trace.all_entries) <= {CALLBACK, HELPER, 0x840048f4}, trace.all_entries
        assert h.get32(MBOX+0x3c) == 1
        assert h.get32(BOOT+8) == 6 and h.get32(ADM) == 1
        assert bytes(h.cpu.mem_read(CODE, len(h.code))) == self.code_image
        return dict(declared_bytes=declared, frame_hex=frame.hex(), entry_only=entry_only,
                    callback_return=result, arguments=arguments, error=error,
                    payload_reads=trace.payload, mailbox_flags_untouched=1,
                    stubs=dict(h.stub_counts), trace=trace.result(True)), trace


def frame(selector, padded):
    return struct.pack('<3I', 0x10|selector, 24, 0) + (bytes(12) if padded else b'')


def oracle(h, selector):
    result, writes = images(h), set()

    def put(offset, value, fmt):
        encoded = struct.pack('<'+fmt, value)
        result[SRAM][offset:offset+len(encoded)] = encoded
        writes.update(range(SRAM+offset, SRAM+offset+len(encoded)))

    if selector == 2:
        put(0x46ec, 1, 'I')
        put(0x46f0, 1, 'I')
        put(0x46f8, 3, 'B')
        put(0x46f7, 0, 'B')
        icv = h.get32(SRAM+0x2ac0)
        base, length = next((base, length) for base, length in IMAGES
                            if base <= icv and icv+ICV_BYTES <= base+length)
        result[base][icv-base:icv-base+ICV_BYTES] = bytes(ICV_BYTES)
        writes.update(range(icv, icv+ICV_BYTES))
    elif selector == 7:
        for offset, value, fmt in ((0x46f5, 0, 'B'), (0x46f0, 1, 'I'),
                                   (0x46f9, 3, 'B'), (0x46f8, 3, 'B'),
                                   (0x46e1, 1, 'B'), (0x46e0, 1, 'B')):
            put(offset, value, fmt)
    elif selector == 4:
        for offset, value, fmt in ((0x46f5, 1, 'B'), (0x46ec, 0, 'I'),
                                   (0x46f0, 0, 'I'), (0x46f9, 0, 'B'),
                                   (0x46f8, 0, 'B'), (0x46fa, 0, 'B')):
            put(offset, value, fmt)
    else:
        raise AssertionError(selector)
    return result, writes


def complete(c, encoded, name):
    selector = encoded[0] & 15
    want, writes = oracle(c.h, selector)
    row, trace = c.invoke_inode(encoded)
    assert row['callback_return'] == 1 and row['error'] is None
    assert images(c.h) == want
    assert trace.memory_written == writes
    assert [item['offset'] for item in row['payload_reads']] == [0, 20, 16, 12, 8]
    assert row['arguments'] == [selector, 0] + ([0]*3 if len(encoded) >= 24 else [0xa5a5a5a5]*3)
    if selector == 2:
        clear = trace.groups[(0x8400e196, 'write', 4, 'memory')]
        assert clear['count'] == 1026
        assert trace.groups[(0x8400e178, 'write', 4, 'memory')]['last_ordinal'] < clear['first_ordinal']
        assert trace.groups[(0x8400e180, 'write', 4, 'memory')]['last_ordinal'] < clear['first_ordinal']
        assert trace.groups[(0x8400e18a, 'write', 1, 'memory')]['last_ordinal'] < clear['first_ordinal']
    row.update(name=name, full_memory_bytes_compared=sum(length for _, length in IMAGES),
               memory_sha256={hex(base): digest(data) for base, data in want.items()})
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    assert sha(ELF) == ELF_SHA and sha(GHIDRA) == GHIDRA_SHA
    assert sha(INPUT/'en7581_MT7996_npu_rv32.bin') == CODE_SHA
    assert sha(INPUT/'en7581_MT7996_npu_data.bin') == DATA_SHA
    for name, expected_sha in {**PARENTS, 'test_attach_rx_callbacks.py': RX_SHA}.items():
        assert sha(ROOT/'tests/npu'/name) == expected_sha, name
    c = InodeClosure(ELF, exports())
    h = c.h
    icv = h.get32(SRAM+0x2ac0)
    assert icv == c.fixed[0x109]
    h.cpu.mem_write(icv-16, b'\xa5'*(ICV_BYTES+32))
    snapshot = c.snapshot()
    valid, controls, entries = [], [], []
    for selector in range(16):
        c.restore(snapshot)
        before = images(h)
        row, trace = c.invoke_inode(frame(selector, True), enforce=True, entry_only=True)
        assert row['error'] is None and row['arguments'] == [selector, 0, 0, 0, 0]
        assert [item['offset'] for item in row['payload_reads']] == [0, 20, 16, 12, 8]
        assert images(h) == before and not trace.memory_written
        entries.append(row)
    for selector in (2, 7, 4):
        for padded in (False, True):
            c.restore(snapshot)
            valid.append(complete(c, frame(selector, padded), f'if{selector}-'+('24-byte' if padded else '12-byte-stale-tail')))
        assert valid[-2]['memory_sha256'] == valid[-1]['memory_sha256']
        c.restore(snapshot)
        before = images(h)
        row, trace = c.invoke_inode(frame(selector, False), enforce=True)
        assert row['error'] == 'payload read 20+4 exceeds 12'
        assert row['callback_return'] is None and images(h) == before and not trace.memory_written
        controls.append(dict(name=f'if{selector}-declared-extent', **row))
    c.restore(snapshot)
    h.put32(SRAM+0x2ac0, 0x40000000)
    row, trace = c.invoke_inode(frame(2, True), enforce=True)
    assert row['callback_return'] is None and row['error']
    assert h.get32(SRAM+0x46ec) == h.get32(SRAM+0x46f0) == 1
    assert bytes(h.cpu.mem_read(SRAM+0x46f8, 1)) == b'\x03'
    controls.append(dict(name='if2-missing-icv-run-flags-precede-failed-clear', **row))
    strict = []
    for selector in (2, 7, 4):
        c.restore(snapshot)
        before = images(h)
        row = h.message(list(struct.unpack('<6I', frame(selector, True))))
        assert row['flags'] == 3 and not row['callbacks'] and images(h) == before
        strict.append(row)
    output = dict(schema=1, verdict='PASS',
        inputs=dict(elf_sha256=ELF_SHA, code_sha256=CODE_SHA, data_sha256=DATA_SHA,
                    ghidra_sha256=GHIDRA_SHA, self_sha256=sha(Path(__file__))),
        counts=dict(callback_entry_footprints=len(entries), native_complete=len(valid),
                    negative_controls=len(controls), strict_denials=len(strict)),
        native_core0_icv=hex(icv), icv_bytes=ICV_BYTES, valid_callbacks=valid,
        entry_footprints=entries, controls=controls, strict_replies=strict,
        boundaries=['Original callback invocation after native core0 boot; strict IRQ registration is unchanged.',
                    'Five wrapper loads span 24 bytes; API word1 is read by the common Wi-Fi dispatcher.',
                    'The provider allocation is 256 bytes; stale undeclared reads are not a physical heap overrun.',
                    'Selectors2/7/4 ignore the stale arguments; no live Wi-Fi failure causality is established.',
                    'Selectors0/1/3/5/6/8..15 are stopped at helper entry, not claimed as consumer closure.',
                    'Run flags precede ICV initialization; no physical ready/drain/reclaim proof.'])
    encoded = json.dumps(output, indent=2)+'\n'
    if args.check:
        assert args.out.read_text() == encoded, 'Stored evidence differs from current native execution'
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded)
    print(json.dumps(dict(verdict=output['verdict'], counts=output['counts'], output=str(args.out))))


if __name__ == '__main__':
    main()
