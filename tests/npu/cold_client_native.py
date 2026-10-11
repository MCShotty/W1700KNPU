"""Actual cold-client C transport for a raw peer; backing/delivery stay modeled."""
import ctypes


def exchange(host, peer, words, *, expected_output=None):
    command = (ctypes.c_uint32 * 3)(*words)
    packet = (ctypes.c_uint32 * 20)()
    output = ctypes.c_uint32(0xabcdef01)
    pointer = ctypes.POINTER(ctypes.c_uint32)
    request = host.lib.npu_cold_client_request
    request.argtypes = [pointer, pointer, ctypes.c_uint32, pointer]
    request.restype = ctypes.c_uint32
    complete = host.lib.npu_cold_client_complete
    complete.argtypes = [pointer, ctypes.c_uint32, ctypes.c_int, pointer, ctypes.c_uint32, pointer, pointer]
    complete.restype = ctypes.c_uint32
    ticket = request(host.state, packet, 80, command)
    assert ticket
    request_words = list(packet)
    reply = peer.message(request_words)
    assert reply['flags'] == 7 and reply['words'][14] == 0, (words, reply)
    packet[:] = reply['words']
    assert complete(host.state, ticket, 0, packet, 80, command, ctypes.byref(output)) == 1
    expected = expected_output if expected_output is not None else 0x457 if words[:2] == (0x30, 10) else words[2]
    assert output.value == expected
    return dict(request=request_words, reply=reply, output=output.value)
