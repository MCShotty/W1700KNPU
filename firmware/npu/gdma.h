#ifndef W1700K_NPU_GDMA_H
#define W1700K_NPU_GDMA_H

#include <stdint.h>

enum npu_gdma_result {
    NPU_GDMA_OK,
    NPU_GDMA_INVALID,
    NPU_GDMA_BUSY,
    NPU_GDMA_STALE_DONE,
    NPU_GDMA_TIMEOUT,
    NPU_GDMA_ACK_FAILED,
};

/* Caller serializes the owning hart with IRQs gated. Failure must not return to
 * a legacy void caller that would publish/release the still-owned buffer.
 * Poll limits count observations, not microseconds. Not a full-domain drain. */
enum npu_gdma_result npu_gdma_copy(uint32_t hart, uint32_t channel,
                                   uint32_t source, uint32_t destination,
                                   uint32_t length, uint32_t poll_limit);

#endif
