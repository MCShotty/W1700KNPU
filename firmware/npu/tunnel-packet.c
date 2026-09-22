#include "tunnel-packet.h"
#include "tunnel-header.h"

static int source_extent(uint32_t base, uint32_t bytes)
{
    return bytes <= UINT32_MAX - base &&
           bytes <= 0x20000000u - (base & 0x1fffffffu);
}

uint32_t npu_tunnel_srv6_extent_valid(uint32_t channel, uint32_t total,
                                    uint32_t packet, uint32_t udf, uint32_t l3,
                                    uint32_t header_bytes, uint32_t header_base)
{
    uint32_t tail_bytes, header_end;

    if (channel >= 8 || udf < 41 || udf - 41 >= NPU_TUNNEL_SRV6_SLOTS ||
        !packet || total < 32 || total - 32 > UINT16_MAX ||
        l3 < 14 || l3 > 127 || total <= 32 + l3 ||
        header_bytes < 54 || header_bytes > NPU_TUNNEL_HEADER_BYTES)
        return 0;

    /* Outer Ethernet + fixed IPv6 header occupy 54 bytes of the template. */
    tail_bytes = total - 32 - l3;
    if (tail_bytes > UINT16_MAX - (header_bytes - 54))
        return 0;

    header_end = (udf - 21) * 128 + header_bytes;
    return source_extent(packet, total) && source_extent(header_base, header_end);
}
