#ifndef W1700K_NPU_TUNNEL_HEADER_H
#define W1700K_NPU_TUNNEL_HEADER_H

#include <stdint.h>

#define NPU_TUNNEL_VXLAN 0u
#define NPU_TUNNEL_SRV6 1u
#define NPU_TUNNEL_VXLAN_SLOTS 20u
#define NPU_TUNNEL_SRV6_SLOTS 8u
#define NPU_TUNNEL_HEADER_BYTES 128u
#define NPU_TUNNEL_INVALID UINT32_MAX

struct npu_tunnel_header_result {
    uint32_t index;
    uint32_t bytes;
};

/* The caller owns the declared readable message span. Results capture the
 * routing fields once; later copies must not reload those fields. */
struct npu_tunnel_header_result npu_tunnel_header_decode(
    const volatile uint8_t *message, uint32_t available, uint32_t kind);

/* Requires a nonempty source extent after the consumer's twelve-byte MAC skip.
 * Packet-format validity and lifetime are separate contracts. lengths must
 * back all eight slots. */
uint32_t npu_tunnel_srv6_read_length(uint32_t udf,
                                  const volatile uint8_t *lengths);

#endif
