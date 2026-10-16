"""Exact pointer+sequence projection from the authenticated pre-command image."""
import struct

from test_cold_txdone_native import SPACES


def expected(h, request):
    assert len(request) == 20 and request[:5] == [0x3f, 1, 0x3253434e, 2, 80]
    assert request[5] == 1 and request[11:13] == [0x1a, 0] and request[14:] == [0] * 6
    session = h.rv.symbols['npu_emulation_control_v2_state']
    before = struct.unpack('<5I', h.cpu.mem_read(session, 20))
    assert list(before[:4]) == request[9:11] + request[7:9]
    assert before[4] < request[6] <= 0xffffffff
    state = h.rv.symbols['npu_emulation_cold_setup_state']
    setup = struct.unpack('<101I', h.cpu.mem_read(state, 404))
    assert setup[:2] == (0, 0) and setup[95] == 2
    base, extent = setup[12:14]
    assert base and not base & 4095 and base < 0xc0000000
    assert 0xd4590 + 12 <= extent <= 0xc0000000 - base
    tx2, prior_tx2, tail_steps, prior_tail_steps = setup[97:101]
    assert tx2 == prior_tx2 and tx2 - base in (0xd4450, 0xd8450)
    assert tx2 - base + 12 <= extent and tail_steps == prior_tail_steps == 0
    assert request[13] == base + 0xd4590
    images = {address: bytearray(h.cpu.mem_read(address, length)) for address, length in SPACES}
    changes = []
    for address, value in ((0x3e902a90, base + 0xd4590), (session + 16, request[6])):
        region = next(start for start, data in images.items() if start <= address and address + 4 <= start + len(data))
        old = struct.unpack_from('<I', images[region], address - region)[0]
        struct.pack_into('<I', images[region], address - region, value)
        changes.append(dict(address=hex(address), before=old, expected=value, bytes=4))
    return images, changes
