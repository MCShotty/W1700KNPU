"""Checked EN7581/MT7996 raw-image assembly; physical loader contracts are separate."""
import hashlib
import io
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_RISCV, CS_MODE_RISCV32, CS_MODE_RISCVC
from elftools.elf.elffile import ELFFile

CODE, SRAM = 0x84000000, 0x3e900000
CODE_LIMIT, DATA_LIMIT = 0x200000, 0x10000
CODE_SHA = 'e743d1b59a9ca6d043e38ff71075e8d28702a104b94abb17a4035514efda4643'
DATA_SHA = '61a75afb052feed2ceb2f3023e16f50317c05c78f9c8e564bf01924ce39c7ec1'
ORIGINAL_CODE_BYTES, ORIGINAL_DATA_BYTES = 122336, 3084
COMPONENTS = frozenset(('base', 'bridge', 'reset', 'allocator', 'txdone', 'order', 'headers',
                        'egress', 'packets', 'cold-pages', 'rx-stats', 'cold-packets', 'cold-tx', 'cold-descriptor', 'cold-tx-buffer', 'cold-rx-event'))
HOOK_SITES = frozenset(CODE + offset for offset in (
    0x74, 0xf0, 0x188, 0xb24, 0xb36, 0x148a, 0x1500, 0x1582, 0x159e, 0x178e,
    0x1e78, 0x1e92, 0x1eea, 0x1f00, 0x1f3a, 0x30b2, 0x3f2e, 0x4a28, 0x4a3a,
    0x4b08, 0x4d80, 0x4d92, 0x5200, 0x52ca, 0x52d4, 0x53a6, 0x5c30, 0x5c82,
    0xa39a, 0xa3ae, 0xb546, 0xb7c8, 0xb8f6, 0xbb10, 0xbb1a, 0xbb9c, 0xbd48, 0xbd62, 0xbd86,
    0xc96c, 0xcb3e, 0xcbbe, 0xcbca, 0xcc0c, 0xcc1e, 0xcc4e, 0xcd3e, 0xcd8a,
    0xcd9e, 0xce1c, 0xcf10, 0xcf26, 0xd0ea, 0xd144, 0xd160, 0xddc0, 0xddd6,
    0xe440, 0xe4d4, 0xec7e, 0xecc2, 0xece6, 0xfe34,
    0xfc16, 0xfdda, 0xd638, 0xd66c, 0xd4be, 0xd4c6, 0xd584, 0xd588, 0xd5b8, 0xd5be, 0xdfd0,
    0x10164, 0xd8cc, 0xd8fc, 0xfbca,
    0xef98, 0xefba, 0xefd8, 0xf014, 0xf062, 0xf092,
    0xa630, 0xa638, 0xa644, 0xa6a6, 0xa6ae, 0xa6c6,
    0xeeb2, *range(0xeeb8, 0xef2c, 4), 0xef2c, 0xa672, 0xa678, 0xa67c, 0xfbb4, 0xb5ec))
HOOK_WIDTHS = {CODE + 0x4d80: 6, CODE + 0xeeb2: 6, CODE + 0xa672: 6}
LOADER_SLOTS = {SRAM + 0x6300: 48, SRAM + 0x6380: 20, SRAM + 0x63a0: 8}
STARTUP_ADDRESS = SRAM + 0x6180
STARTUP_BYTES = struct.pack('<16I', 0x3153504e, 1, 64, *([0] * 13))
BRIDGE_EDIT = dict(site=CODE + 0x1b230, before=struct.pack('<I', 58879).hex(),
                   after=struct.pack('<I', 69632).hex())
PAIR_MAGIC, PAIR_VERSION, PAIR_PROFILE, PAIR_FLAGS = 0x32504e57, 1, 0x7996, 1
CODE_TAG_OFFSET, DESCRIPTOR_OFFSET, DESCRIPTOR_BYTES = 0x3f000, 0x6400, 128
CODE_TAG = struct.pack('<8I', PAIR_MAGIC, PAIR_VERSION, 32, PAIR_PROFILE,
                       DESCRIPTOR_OFFSET, DESCRIPTOR_BYTES, PAIR_FLAGS, 0)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def elf(path):
    result = ELFFile(io.BytesIO(Path(path).read_bytes()))
    require(result.elfclass == 32 and result.little_endian and result['e_machine'] == 'EM_RISCV',
            'wrong-elf-machine')
    require(result['e_type'] == 'ET_EXEC', 'unlinked-elf')
    for section in result.iter_sections():
        if section['sh_type'] in ('SHT_REL', 'SHT_RELA'):
            require(not section.num_relocations(), 'unresolved-relocations')
    table = result.get_section_by_name('.symtab')
    require(table is not None, 'missing-symbols')
    require(not any(s.name and s['st_shndx'] == 'SHN_UNDEF' for s in table.iter_symbols()), 'undefined-symbols')
    return result


def symbols(path):
    return {s.name: s['st_value'] for s in elf(path).get_section_by_name('.symtab').iter_symbols()
            if s.name and s['st_shndx'] != 'SHN_UNDEF'}


def jal(site, target, rd=0):
    offset = target - site
    require(rd in (0, 1) and not (site | target) & 1 and -(1 << 20) <= offset < (1 << 20), 'jal-range')
    immediate = offset & 0x1fffff
    word = ((immediate >> 20) << 31 | ((immediate >> 1) & 0x3ff) << 21 |
            ((immediate >> 11) & 1) << 20 | ((immediate >> 12) & 0xff) << 12 | rd << 7 | 0x6f)
    return struct.pack('<I', word)


def boundary(data, address):
    decoder = Cs(CS_ARCH_RISCV, CS_MODE_RISCV32 | CS_MODE_RISCVC)
    instructions = list(decoder.disasm(data, address))
    require(instructions and sum(i.size for i in instructions) == len(data), 'split-instruction')


def overlaps(left, right):
    return left[0] < right[1] and right[0] < left[1]


def descriptor(code, payload):
    require(len(payload) == DESCRIPTOR_OFFSET, 'descriptor-payload-size')
    fields = (PAIR_MAGIC, PAIR_VERSION, DESCRIPTOR_BYTES, PAIR_PROFILE, PAIR_FLAGS,
              CODE, len(code), DESCRIPTOR_OFFSET + DESCRIPTOR_BYTES, SRAM,
              0x6300, 0x6380, 20, 0x63a0, 8, 256, DESCRIPTOR_OFFSET)
    return struct.pack('<16I', *fields) + hashlib.sha256(code).digest() + hashlib.sha256(payload).digest()


def profile(hooks, edits, initializers, slots):
    require(len(hooks) == len(HOOK_SITES) and {p['site'] for p in hooks} == HOOK_SITES, 'incomplete-hook-set')
    for patch in hooks:
        require(len(bytes.fromhex(patch['before'])) == HOOK_WIDTHS.get(patch['site'], 4), 'hook-width')
        require(patch.get('rd', 0) == (1 if patch['site'] == CODE + 0x52ca else 0), 'hook-link-register')
    require(len(edits) == 1 and all(edits[0].get(k) == v for k, v in BRIDGE_EDIT.items()), 'wrong-data-edit')
    require(len(initializers) == 1 and initializers[0]['address'] == STARTUP_ADDRESS and
            bytes.fromhex(initializers[0]['bytes']) == STARTUP_BYTES, 'wrong-startup-initializer')
    require(len(slots) == 3 and {s['address']: s['bytes'] for s in slots} == LOADER_SLOTS, 'wrong-loader-slots')


def check_target(patch, sections):
    if patch['site'] == CODE + 0x52d4:
        require(patch['target'] == CODE + 0x52e4 and patch['symbol'] is None and
                patch['component'] == 'reset', 'wrong-native-continuation')
    else:
        require(patch['symbol'] and any(row['component'] == patch['component'] and row['flags'] & 4 and
                row['start'] <= patch['target'] < row['end'] for row in sections), 'nonexecuting-target')


def assemble(code, data, components, patches, edits=(), initializers=(), loader_slots=()):
    require(sha(code) == CODE_SHA and sha(data) == DATA_SHA, 'wrong-original-pair')
    profile(patches, edits, initializers, loader_slots)
    require(set(components) == COMPONENTS, 'incomplete-components')
    sections, occupied, tables = [], [], {}
    provenance = {}
    for name, path in components.items():
        binary = elf(path)
        tables[name] = {s.name: s['st_value'] for s in binary.get_section_by_name('.symtab').iter_symbols() if s.name}
        provenance[name] = dict(path=str(path), sha256=sha(Path(path).read_bytes()))
        for section in binary.iter_sections():
            if not section['sh_flags'] & 2 or not section['sh_size']:
                continue
            start, end = section['sh_addr'], section['sh_addr'] + section['sh_size']
            require(CODE + 0x40000 <= start < end <= CODE + CODE_LIMIT, 'section-aperture')
            require(not any(overlaps((start, end), span) for span in occupied), 'section-overlap')
            occupied.append((start, end))
            payload = bytes(section['sh_size']) if section['sh_type'] == 'SHT_NOBITS' else section.data()
            require(len(payload) == section['sh_size'], 'section-size')
            row = dict(component=name, section=section.name, start=start, end=end,
                       zero_fill=section['sh_type'] == 'SHT_NOBITS', flags=section['sh_flags'], sha256=sha(payload))
            sections.append((row, payload))
    require(sections, 'missing-components')
    output_code = bytearray(max(row['end'] for row, _ in sections) - CODE)
    output_code[:len(code)] = code
    output_code[CODE_TAG_OFFSET:CODE_TAG_OFFSET + len(CODE_TAG)] = CODE_TAG
    for row, payload in sections:
        output_code[row['start'] - CODE:row['end'] - CODE] = payload
    changed = []
    for patch in patches:
        site, target, rd = patch['site'], patch['target'], patch.get('rd', 0)
        before = bytes.fromhex(patch['before'])
        require(len(before) in (4, 6) and CODE <= site <= CODE + len(code) - len(before), 'hook-range')
        require(code[site - CODE:site - CODE + len(before)] == before, 'hook-preimage')
        boundary(before, site)
        require(patch['component'] in components, 'unknown-hook-component')
        if patch['symbol'] is not None:
            require(tables[patch['component']].get(patch['symbol']) == target, 'wrong-hook-symbol')
        check_target(patch, [row for row, _ in sections])
        after = jal(site, target, rd) + (b'\x01\x00' if len(before) == 6 else b'')
        require(patch.get('after', after.hex()) == after.hex(), 'hook-encoding')
        span = (site, site + len(before))
        require(not any(overlaps(span, previous) for previous in changed), 'edit-overlap')
        changed.append(span)
        output_code[site - CODE:site - CODE + len(after)] = after
        patch['after'] = after.hex()
    for edit in edits:
        site, before, after = edit['site'], bytes.fromhex(edit['before']), bytes.fromhex(edit['after'])
        require(len(before) == len(after) and CODE <= site <= CODE + len(code) - len(before), 'data-edit-range')
        require(code[site - CODE:site - CODE + len(before)] == before, 'data-edit-preimage')
        span = (site, site + len(before))
        require(not any(overlaps(span, previous) for previous in changed), 'edit-overlap')
        changed.append(span)
        output_code[site - CODE:site - CODE + len(after)] = after
    length = max([len(data), DESCRIPTOR_OFFSET] + [row['address'] - SRAM + len(bytes.fromhex(row['bytes'])) for row in initializers] +
                 [row['address'] - SRAM + row['bytes'] for row in loader_slots])
    require(len(data) <= length <= DATA_LIMIT, 'data-aperture')
    output_data = bytearray(length)
    output_data[:len(data)] = data
    spans = [(SRAM, SRAM + len(data))]
    for row in initializers:
        address, payload = row['address'], bytes.fromhex(row['bytes'])
        span = (address, address + len(payload))
        require(SRAM + 0x4754 <= span[0] < span[1] <= SRAM + DATA_LIMIT, 'initializer-range')
        require(not any(overlaps(span, old) for old in spans), 'initializer-overlap')
        spans.append(span)
        output_data[address - SRAM:address - SRAM + len(payload)] = payload
    for slot in loader_slots:
        address, size = slot['address'], slot['bytes']
        require(SRAM + 0x4754 <= address < address + size <= SRAM + DATA_LIMIT and not address & 3, 'loader-slot-range')
        span = (address, address + size)
        require(not any(overlaps(span, old) for old in spans), 'loader-slot-overlap')
        spans.append(span)
        require(output_data[address - SRAM:address - SRAM + size] == bytes(size), 'provisioned-loader-slot')
    require(length == DESCRIPTOR_OFFSET, 'descriptor-overlap')
    output_data.extend(descriptor(output_code, output_data))
    manifest = dict(format='w1700k-npu-pair-v2', profile='mt7996-native-cold-v2',
        original=dict(code_sha256=CODE_SHA, data_sha256=DATA_SHA),
        code=dict(base=CODE, bytes=len(output_code), sha256=sha(output_code)),
        data=dict(base=SRAM, bytes=len(output_data), sha256=sha(output_data)),
        components=provenance, sections=[row for row, _ in sections], hooks=patches, edits=list(edits),
        initializers=list(initializers), loader_slots=list(loader_slots),
        loader_abi=dict(version=PAIR_VERSION, flags=PAIR_FLAGS, code_tag_offset=CODE_TAG_OFFSET,
                        descriptor_offset=DESCRIPTOR_OFFSET, descriptor_bytes=DESCRIPTOR_BYTES),
        loader_provisioned=False, physical_storage_or_containment_proved=False)
    validate(bytes(output_code), bytes(output_data), manifest)
    return bytes(output_code), bytes(output_data), manifest


def validate(code, data, manifest):
    """Check byte/manifest consistency, not authenticity or physical suitability."""
    require(manifest['format'] == 'w1700k-npu-pair-v2' and manifest['profile'] == 'mt7996-native-cold-v2', 'wrong-profile')
    require(manifest['loader_abi'] == dict(version=PAIR_VERSION, flags=PAIR_FLAGS, code_tag_offset=CODE_TAG_OFFSET,
            descriptor_offset=DESCRIPTOR_OFFSET, descriptor_bytes=DESCRIPTOR_BYTES), 'wrong-loader-abi')
    require(manifest['loader_provisioned'] is False and manifest['physical_storage_or_containment_proved'] is False,
            'unsupported-acceptance-claim')
    require(manifest['original'] == dict(code_sha256=CODE_SHA, data_sha256=DATA_SHA), 'wrong-original-identity')
    for name, value, base, limit, minimum in (('code', code, CODE, CODE_LIMIT, ORIGINAL_CODE_BYTES),
                                             ('data', data, SRAM, DATA_LIMIT, ORIGINAL_DATA_BYTES)):
        row = manifest[name]
        require(row['base'] == base and minimum <= len(value) <= limit and row['bytes'] == len(value), 'image-size')
        require(row['sha256'] == sha(value), 'image-digest')
    hooks, edits, initializers, slots = [manifest[k] for k in ('hooks', 'edits', 'initializers', 'loader_slots')]
    profile(hooks, edits, initializers, slots)
    original = bytearray(code[:ORIGINAL_CODE_BYTES])
    for patch in hooks:
        site, before = patch['site'], bytes.fromhex(patch['before'])
        boundary(before, site)
        after = jal(site, patch['target'], patch.get('rd', 0)) + (b'\x01\x00' if len(before) == 6 else b'')
        require(patch['after'] == after.hex() and code[site - CODE:site - CODE + len(after)] == after, 'hook-readback')
        check_target(patch, manifest['sections'])
        original[site - CODE:site - CODE + len(before)] = before
    edit = edits[0]
    offset = edit['site'] - CODE
    require(code[offset:offset + 4].hex() == edit['after'], 'data-edit-readback')
    original[offset:offset + 4] = bytes.fromhex(edit['before'])
    require(sha(original) == CODE_SHA and sha(data[:ORIGINAL_DATA_BYTES]) == DATA_SHA, 'original-prefix-readback')
    expected_code = bytearray(len(code))
    expected_code[:ORIGINAL_CODE_BYTES] = code[:ORIGINAL_CODE_BYTES]
    require(code[CODE_TAG_OFFSET:CODE_TAG_OFFSET + len(CODE_TAG)] == CODE_TAG, 'code-tag-readback')
    expected_code[CODE_TAG_OFFSET:CODE_TAG_OFFSET + len(CODE_TAG)] = CODE_TAG
    occupied, found = [], set()
    for row in manifest['sections']:
        start, end = row['start'], row['end']
        require(row['component'] in COMPONENTS and CODE + 0x40000 <= start < end <= CODE + len(code), 'section-aperture')
        require(not any(overlaps((start, end), old) for old in occupied), 'section-overlap')
        occupied.append((start, end))
        found.add(row['component'])
        payload = code[start - CODE:end - CODE]
        require(sha(payload) == row['sha256'], 'section-readback')
        require(not row['zero_fill'] or payload == bytes(len(payload)), 'nonzero-bss')
        expected_code[start - CODE:end - CODE] = payload
    require(found == set(manifest['components']) == COMPONENTS, 'incomplete-components')
    require(code == expected_code and len(code) == max(row['end'] for row in manifest['sections']) - CODE,
            'unaccounted-code')
    expected_data = bytearray(DESCRIPTOR_OFFSET)
    expected_data[:ORIGINAL_DATA_BYTES] = data[:ORIGINAL_DATA_BYTES]
    expected_data[STARTUP_ADDRESS - SRAM:STARTUP_ADDRESS - SRAM + len(STARTUP_BYTES)] = STARTUP_BYTES
    for slot in slots:
        offset = slot['address'] - SRAM
        require(data[offset:offset + slot['bytes']] == bytes(slot['bytes']), 'provisioned-loader-slot')
    require(data[:DESCRIPTOR_OFFSET] == expected_data, 'unaccounted-data')
    require(data[DESCRIPTOR_OFFSET:] == descriptor(code, expected_data), 'loader-descriptor-readback')
