#include "tunnel-header.h"

_Static_assert(sizeof(struct npu_tunnel_header_result) == 8, "RV32 result register ABI");

struct npu_tunnel_header_result npu_tunnel_header_decode(
    const volatile uint8_t *message, uint32_t available, uint32_t kind)
{
    struct npu_tunnel_header_result result = {NPU_TUNNEL_INVALID, 0};
    uint32_t index, bytes, slots;

    if (!message || available > UINTPTR_MAX - (uintptr_t)message)
        return result;
    if (kind == NPU_TUNNEL_VXLAN) {
        if (available < 59)
            return result;
        index = message[8];
        bytes = 50;
        slots = NPU_TUNNEL_VXLAN_SLOTS;
    } else if (kind == NPU_TUNNEL_SRV6) {
        if (available < 10)
            return result;
        index = message[8];
        bytes = message[9];
        if (bytes > NPU_TUNNEL_HEADER_BYTES || bytes > available - 10)
            return result;
        slots = NPU_TUNNEL_SRV6_SLOTS;
    } else {
        return result;
    }
    if (index >= slots)
        return result;
    result.index = index;
    result.bytes = bytes;
    return result;
}

uint32_t npu_tunnel_srv6_read_length(uint32_t udf,
                                  const volatile uint8_t *lengths)
{
    uint32_t bytes;

    if (!lengths || udf < 41 || udf - 41 >= NPU_TUNNEL_SRV6_SLOTS)
        return NPU_TUNNEL_INVALID;
    bytes = lengths[udf - 41];
    if (bytes <= 12 || bytes > NPU_TUNNEL_HEADER_BYTES)
        return NPU_TUNNEL_INVALID;
    return bytes;
}
