#!/usr/bin/env python3
"""Read two pinned AArch64 senders and check their release bodies without executing either."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import capstone
from capstone import arm64
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from inspect_rro_release import decode_body
from npu_world_sources import digest, linked_module_sources

STOCK = 'research/stock/elf/stock_mt_wifi.ko'
STOCK_SHA = '40c8f974ad7317776f602c069c009d1f0d5d939d622ccdee275423fad1e35cb0'
STOCK_BODIES = {
    'uni_cmd_release_rro_setbl': 'ef75d3800eec51c3f6328996eb12df13150eac64b10a6f5dac8778dce6ee0c1d',
    'RTMP_FREE_RRO_SETBL': 'eeeed7d9cfced4d8f598d8da14b9b5b36210894d82f7bd4d4902056fb4db08da',
    'HwCtrlEnqueueCmd': '1176037a96ac4d565849a6900370ed7dfb5b63ce1d555b0bd24a8aa48e822854',
    'uni_event_rro_del_chk': '53f40f0b724b248d68c7213b655a981fa587d5c17a6a5c8cbc19e668b0244779',
}
STOCK_WINDOWS = {
    'table-lookup': (0x346eec, 0x80, '9d4db802848bf23f5ee562aaffb5fba643cae38af282725b41b552a1bee552dc'),
    'release-callback': (0x387784, 0x20, 'b88a161060726bc90a7177c3afe277ba412311c52bec0032870c86176e9f0b5b'),
}
MT76_BODIES = {
    'mt7996_mcu_wed_rro_reset_sessions': '31b09a59d7868c4bcdadea3ca78b80b279e61c529c7dbe5beda40555d5a7f00a',
    'mt7996_mcu_parse_response': '4d2b9a4340d3afbd09b9458a17b878af79c4ea6489bbfbb759b6e2455d239c8f',
    'mt7996_mcu_send_message': 'c224aab788e821d2d4994a2a525c383c0dd7c783edfc1bb89a2242a728e9820a',
    'mt7996_npu_rro_reset_work': '7c62ad2d130f0b63b215f68dc802ef486755ae677cf3f9fc08a122f25a9409b1',
}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


class Body:
    def __init__(self, name, start, data):
        self.name, self.start, self.data = name, start, data
        self.relocations = {}
        self.checked = {}
        decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
        decoder.detail = True
        self.ins = {i.address: i for i in decoder.disasm(data, 0)}
        require(len(self.ins) * 4 == len(data), 'incomplete disassembly: ' + name)

    def op(self, off, mnemonic, args=None):
        i = self.ins[off]
        require(i.mnemonic == mnemonic and (args is None or args == i.op_str),
                f'{self.name}+{off:#x}: unexpected {i.mnemonic} {i.op_str}')
        self.checked[hex(off)] = f'{i.mnemonic} {i.op_str}'
        return i

    def imm(self, off, register, high=False):
        i = self.op(off, 'movk' if high else 'mov')
        a, b = i.operands
        require(a.type == arm64.ARM64_OP_REG and i.reg_name(a.reg) == register and b.type == arm64.ARM64_OP_IMM,
                'unexpected immediate operand')
        require((b.shift.type, b.shift.value) == ((arm64.ARM64_SFT_LSL, 16) if high else (0, 0)),
                'unexpected immediate shift')
        return b.imm

    def relocation(self, off, kind, target):
        require(self.relocations.get(off) == (kind, target, 0), f'{self.name}+{off:#x}: wrong relocation for {target}')
        mnemonic = {283: 'bl', 275: 'adrp', 277: 'add'}[kind]
        self.op(off, mnemonic)
        self.checked[hex(off)] += f' -> {target}'

    def receipt(self):
        return dict(text_offset=hex(self.start), bytes=len(self.data),
                    sha256=hashlib.sha256(self.data).hexdigest(), anchors=self.checked)


def read_bodies(path, pins, windows=None):
    out = {}
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        require(elf.elfclass == 64 and elf.little_endian and elf['e_type'] == 'ET_REL' and
                elf['e_machine'] == 'EM_AARCH64', 'expected AArch64 relocatable module')
        text = elf.get_section_by_name('.text')
        table = elf.get_section_by_name('.symtab')
        reloc = elf.get_section_by_name('.rela.text')
        require(text is not None and table is not None and reloc is not None and
                elf.get_section_index('.text') == reloc['sh_info'] and
                elf.get_section_index('.symtab') == reloc['sh_link'], 'wrong ELF sections')
        for symbol in table.iter_symbols():
            name = symbol.name
            if name not in pins:
                continue
            start, size = symbol['st_value'], symbol['st_size']
            require(name not in out and symbol['st_info']['type'] == 'STT_FUNC' and
                    symbol['st_shndx'] == reloc['sh_info'] and 0 < size <= text['sh_size'] - start,
                    'invalid function definition: ' + name)
            stream.seek(text['sh_offset'] + start)
            data = stream.read(size)
            require(hashlib.sha256(data).hexdigest() == pins[name], 'different function body: ' + name)
            out[name] = Body(name, start, data)
        require(out.keys() == pins.keys(), 'missing function definitions')
        for name, (start, size, expected) in (windows or {}).items():
            require(0 <= start < start + size <= text['sh_size'], 'invalid text window')
            stream.seek(text['sh_offset'] + start)
            data = stream.read(size)
            require(hashlib.sha256(data).hexdigest() == expected, 'different unnamed text window: ' + name)
            out[name] = Body(name, start, data)
        # ELF64 Rela has fixed 24-byte records. Only decode symbols for our
        # few small windows; the vendor module has a large .rela.text.
        require(reloc['sh_type'] == 'SHT_RELA' and reloc['sh_entsize'] == 24, 'wrong relocation encoding')
        for address, info, addend in struct.iter_unpack('<QQq', reloc.data()):
            for body in out.values():
                off = address - body.start
                if 0 <= off < len(body.data):
                    require(off not in body.relocations, 'duplicate instruction relocation')
                    body.relocations[off] = (info & 0xffffffff, table.get_symbol(info >> 32).name, addend)
    return out


def stock_dispatch(path, bodies):
    wrap, queue, lookup, callback = (bodies[n] for n in
        ('RTMP_FREE_RRO_SETBL', 'HwCtrlEnqueueCmd', 'table-lookup', 'release-callback'))
    pair = wrap.imm(0x20, 'x0')
    group, command = pair & 0xffffffff, pair >> 32
    require(group == 0 and command == 0x55, 'different hardware-control request')
    for off, inst, args in (
            (0x14,'strh','w1, [sp, #0x6e]'), (0x24,'str','x0, [sp, #0x70]'),
            (0x28,'strb','wzr, [sp, #0x78]'), (0x2c,'add','x3, sp, #0x6e'),
            (0x38,'str','x3, [sp, #0x80]'), (0x3c,'add','x1, sp, #0x20'),
            (0x40,'str','w2, [sp, #0x88]'), (0x50,'ldp','x2, x3, [sp, #0x70]'),
            (0x54,'stp','x2, x3, [sp, #0x20]'), (0x5c,'ldp','x2, x3, [sp, #0x80]'),
            (0x60,'stp','x2, x3, [sp, #0x30]')):
        wrap.op(off, inst, args)
    require(wrap.imm(0x34, 'w2') == 2, 'different session argument width')
    wrap.relocation(0x74, 283, 'HwCtrlEnqueueCmd')
    queue.op(0x2c, 'ldrb', 'w23, [x1, #8]')
    queue.relocation(0x278, 283, 'os_move_mem')
    queue.relocation(0x2f4, 283, 'RtmpOsCmdUp')
    queue.op(0x2f8, 'cbz', 'w23, #0x45c')
    queue.relocation(0x31c, 283, 'wait_for_completion_timeout')
    queue.op(0x460, 'b', '#0x1c0')
    lookup.relocation(0x14, 275, 'HwCmdTable')
    lookup.relocation(0x18, 277, 'HwCmdTable')
    stride = lookup.imm(0x20, 'w0')
    for off, inst, args in ((0,'ldp','w7, w6, [x26]'), (0x24,'ldr','x2, [x2, w7, uxtw #3]'),
            (0x38,'smull','x3, w1, w0'), (0x48,'ldr','w3, [x2, x3]'), (0x50,'cmp','w6, w3'),
            (0x5c,'ldr','x2, [x5, #8]'), (0x7c,'blr','x2')):
        lookup.op(off, inst, args)
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        data = elf.get_section_by_name('.data')
        tab = elf.get_section_by_name('.symtab')
        rela = elf.get_section_by_name('.rela.data')
        dat, txt = elf.get_section_index('.data'), elf.get_section_index('.text')
        require(rela['sh_info'] == dat and rela['sh_link'] == elf.get_section_index('.symtab') and
                rela['sh_entsize'] == 24, 'wrong table relocations')
        table, = tab.get_symbol_by_name('HwCmdTable')
        require(table['st_shndx'] == dat and table['st_info']['type'] == 'STT_OBJECT' and
                table['st_size'] >= (group + 1) * 8, 'wrong command table')
        pointers = {}
        for address, info, addend in struct.iter_unpack('<QQq', rela.data()):
            if (info & 0xffffffff) == 257:  # R_AARCH64_ABS64
                require(address not in pointers, 'duplicate table relocation')
                pointers[address] = info >> 32, addend

        def pointer(address):
            require(address in pointers, 'missing table entry relocation')
            idx, addend = pointers[address]
            symbol = tab.get_symbol(idx)
            return symbol['st_shndx'], symbol['st_value'] + addend

        section, base = pointer(table['st_value'] + group * 8)
        raw = data.data()
        require(section == dat and stride == 24, 'wrong hardware-control group')
        for ordinal in range((len(raw)-base)//stride):
            row = base + ordinal * stride
            section, address = pointer(row + 8)
            require(isinstance(section, int) and elf.get_section(section)['sh_flags'] & 4,
                    'non-executable command handler before match')
            if struct.unpack_from('<I', raw, row)[0] == command:
                break
        else:
            raise ValueError('missing release command')
        require(section == txt and address == callback.start, 'wrong resolved release callback')
    callback.op(8, 'ldr', 'x1, [x1, #8]')
    callback.op(0xc, 'ldrh', 'w1, [x1]')
    callback.relocation(0x10, 283, 'uni_cmd_release_rro_setbl')
    require(callback.imm(0x14, 'w0') == 0, 'different callback return convention')
    callback.op(0x1c, 'ret')
    return dict(group=group, hardware_command=command, table_data_offset=hex(table['st_value']),
                group_data_offset=hex(base), row=ordinal, row_stride=stride, handler_slot=hex(row+8),
                callback_text_offset=hex(address), enqueue_wait_flag=0, callback_returns_sender_status=False)


def stock_encoding(f):
    f.op(0x10, 'and', 'w20, w1, #0xffff')
    alloc = f.imm(4, 'x2')
    f.relocation(0x30, 283, 'os_alloc_mem')
    clear = f.imm(0x3c, 'x1')
    f.relocation(0x40, 283, 'os_zero_mem')
    f.op(0x34, 'ldr', 'x0, [sp, #0x60]')
    f.op(0x44, 'ldr', 'x3, [sp, #0x60]')
    tag, tlv = f.imm(0x48, 'w4'), f.imm(0x4c, 'w4', high=True)
    f.op(0x5c, 'str', 'w4, [x3, #4]')
    f.op(0x60, 'strh', 'w20, [x3, #8]')
    msg = f.imm(0x58, 'w1')
    f.relocation(0x64, 283, 'hif_mcu_alloc_msg')
    cid = f.imm(0x70, 'w5')
    f.op(0x7c, 'strb', 'w5, [sp, #0x6a]')
    for off, symbol in ((0x84, 'UniCmdResultRsp'), (0x94, 'UniCmdResultToRsp')):
        f.relocation(off, 275, symbol)
    f.relocation(0x8c, 277, 'UniCmdResultRsp')
    f.relocation(0xa0, 277, 'UniCmdResultToRsp')
    f.relocation(0xb4, 283, 'AndesInitCmdMsg')
    f.relocation(0xbc, 283, 'AndesGetCmdMsgSeq')
    f.op(0xc0, 'ldr', 'x1, [sp, #0x60]')
    append = f.imm(0xc8, 'w2')
    f.relocation(0xd0, 283, 'AndesAppendCmdMsg')
    f.relocation(0xdc, 283, 'chip_cmd_tx')
    require(alloc == clear == msg == append == 4 + tlv, 'stock body lengths disagree')
    return dict(cid=cid, tag=tag, tlv_bytes=tlv, body_bytes=append, session_offset=8,
                zero_ranges=[[0, clear]], session_bytes=2)


def mt76_encoding(f):
    tag, tlv = f.imm(4, 'w6'), f.imm(8, 'w6', high=True)
    f.op(0x10, 'add', 'x2, sp, #0x10')
    f.op(0x14, 'str', 'xzr, [sp, #0x10]')
    f.op(0x1c, 'stp', 'w6, wzr, [sp, #0x14]')
    f.op(0x24, 'strh', 'w1, [sp, #0x18]')
    f.op(0x34, 'strh', 'wzr, [sp, #0x1c]')
    no_response_skb, wait = f.imm(0x18, 'x5'), f.imm(0x20, 'w4')
    cid, flags = f.imm(0x28, 'w1'), f.imm(0x30, 'w1', high=True)
    length = f.imm(0x2c, 'w3')
    f.relocation(0x38, 283, 'mt76_mcu_send_and_get_msg')
    require(no_response_skb == 0 and wait == 1 and flags == 0x12 and length == 4 + tlv,
            'different current transport profile')
    return dict(cid=cid, tag=tag, tlv_bytes=tlv, body_bytes=length, session_offset=8,
                zero_ranges=[[0, 8], [8, 12], [12, 14]], session_bytes=2, wait_response=True)


def crosscheck(stock, current):
    require(stock['cid'] == current['cid'] == 0x57 and stock['tag'] == current['tag'] == 6,
            'different command or tag')
    result = {}
    for name, encoding in [('stock', stock), ('mt76', current)]:
        transcript = hashlib.sha256()
        for seid in range(1025):
            buf = bytearray([0xff]) * encoding['body_bytes']
            for start, end in encoding['zero_ranges']:
                require(0 <= start <= end <= len(buf), 'zero store exceeds sender length')
                buf[start:end] = bytes(end-start)
            struct.pack_into('<HH', buf, 4, encoding['tag'], encoding['tlv_bytes'])
            struct.pack_into('<H', buf, encoding['session_offset'], seid)
            decoded = decode_body(buf)
            require(decoded['session_id'] == seid and decoded['profile'].split('-')[0] == name,
                    'wire decoder disagrees with sender stores')
            transcript.update(buf)
        result[name] = dict(**encoding, reconstructed_session_ids=1025, concatenated_sha256=transcript.hexdigest())
    return result


def verify(receipt, pin):
    require(__debug__, 'producer verification requires Python assertions enabled')
    stock = ROOT / STOCK
    require(digest(stock) == STOCK_SHA and digest(receipt) == pin, 'input SHA256 mismatch')
    producer = linked_module_sources(ROOT, receipt)
    require(producer['receipt_sha256'] == pin, 'producer changed during verification')
    matches = [(ROOT / n, h) for n, h in producer['artifacts'].items() if Path(n).name == 'mt7996e.ko']
    require(len(matches) == 1, 'expected one qualified radio module')
    radio, expected = matches[0]
    a, b = read_bodies(stock, STOCK_BODIES, STOCK_WINDOWS), read_bodies(radio, MT76_BODIES)
    encodings = crosscheck(stock_encoding(a['uni_cmd_release_rro_setbl']),
                           mt76_encoding(b['mt7996_mcu_wed_rro_reset_sessions']))
    queue = stock_dispatch(stock, a)
    for off, name in ((0x44, 'hc_init_rro_addr_elem_by_seid'), (0x150, 'reclaim_ba_rec_session_by_seid'),
                      (0x174, 'RTMP_FREE_RRO_SETBL')):
        a['uni_event_rro_del_chk'].relocation(off, 283, name)
    worker = b['mt7996_npu_rro_reset_work']
    for off, name in ((0x1d0, 'mt76_npu_rro_reset_mcu_begin'), (0x248, 'mt7996_mcu_wed_rro_reset_sessions'),
                      (0x260, 'mt76_npu_rro_reset_mcu_complete')):
        worker.relocation(off, 283, name)
    tx = b['mt7996_mcu_send_message']
    require(tx.imm(0xb8, 'w4') == 0x41000000 and tx.imm(0xbc, 'w3') == 0x4000, 'TX descriptor words differ')
    for off, args in ((0x1a8,'w2, [x0, #0x20]'), (0x1b0,'w24, [x0, #0x22]')):
        tx.op(off, 'strh', args)
    for off, args in ((0x1b8,'w6, [x0, #0x25]'), (0x1bc,'w23, [x0, #0x27]'),
                      (0x1d0,'w3, [x0, #0x2b]'), (0x238,'wzr, [x0, #0x2a]')):
        tx.op(off, 'strb', args)
    rsp = b['mt7996_mcu_parse_response']
    for off, op, args in ((0x1c,'ldrb','w2, [x0, #0x25]'), (0x20,'cmp','w2, w3'), (0x24,'b.ne','#0x80'),
                          (0x30,'ldrb','w1, [x0, #0x26]'), (0x34,'tbz','w1, #1, #0x44'),
                          (0x38,'ldrb','w0, [x0, #0x24]'), (0x3c,'cmp','w0, #1'), (0x40,'b.eq','#0x60'),
                          (0x70,'ldrh','w1, [x0]'), (0x74,'ldr','w0, [x0, #4]'),
                          (0x78,'cmp','w1, w20, uxtb'), (0x7c,'b.eq','#0x54')):
        rsp.op(off, op, args)
    require(rsp.imm(0x50, 'w0') == 0 and rsp.imm(0x80,'w0') == -11, 'different response outcomes')
    rsp.relocation(0x68, 283, 'skb_pull')
    require(digest(stock) == STOCK_SHA and digest(radio) == expected and digest(receipt) == pin,
            'artifact changed during analysis')
    return dict(stock_sha256=STOCK_SHA, producer_sha256=pin, source_lock_sha256=producer['source_lock_sha256'],
                producer_inputs=len(producer['inputs']), radio_sha256=expected, encodings=encodings,
                stock_dispatch=queue, functions={k: v.receipt() for k, v in (a | b).items()}, capstone=capstone.__version__,
                static_reconstruction=True, driver_or_firmware_executed=False,
                receiver_length_policy_known=False, ba_reuse_fence_proven=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module-receipt', type=Path, required=True)
    parser.add_argument('--expected-producer-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.module_receipt.resolve(strict=True), args.expected_producer_sha256), indent=2))
