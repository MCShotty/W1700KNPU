"""Original constructor oracle plus exact authenticated transaction metadata."""
import struct
from types import SimpleNamespace

from test_attach_tx_callbacks import done_oracle


def expected(h, request):
    assert len(request) == 20 and request[:5] == [0x3f, 1, 0x3253434e, 2, 80]
    assert request[5] == 1 and request[11:14] == [0x1a, 1, 512] and request[14:] == [0] * 6
    address = h.rv.symbols['npu_emulation_control_v2_state']
    before = bytes(h.cpu.mem_read(address, 20))
    words = struct.unpack('<5I', before)
    assert list(words[:4]) == request[9:11] + request[7:9]
    assert words[4] < request[6] <= 0xffffffff
    images, allowed, footprint = done_oracle(SimpleNamespace(h=h, fixed=h.fixed), 512)
    base = next(base for base, data in images.items() if base <= address and address + 20 <= base + len(data))
    assert bytes(images[base][address - base:address - base + 20]) == before
    images = {base: bytearray(data) for base, data in images.items()}
    sequence_address = address + 16
    struct.pack_into('<I', images[base], sequence_address - base, request[6])
    allowed = allowed | set(range(sequence_address, sequence_address + 4))
    footprint = dict(footprint, transaction_sequence=dict(address=hex(sequence_address),
        before=words[4], expected=request[6], bytes=4))
    return images, allowed, footprint
