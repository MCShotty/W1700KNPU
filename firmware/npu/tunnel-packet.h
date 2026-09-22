#ifndef W1700K_NPU_TUNNEL_PACKET_H
#define W1700K_NPU_TUNNEL_PACKET_H

#include <stdint.h>

/* total includes the 32-byte native descriptor; l3 is wire-frame-relative.
 * This checks extents and the ordinary IPv6 payload-length field, not packet
 * contents, MTU, backing, ownership or atomic configuration. */
uint32_t npu_tunnel_srv6_extent_valid(uint32_t channel, uint32_t total,
                                    uint32_t packet, uint32_t udf, uint32_t l3,
                                    uint32_t header_bytes, uint32_t header_base);

#endif
