#ifndef W1700K_NPU_COLD_PACKET_H
#define W1700K_NPU_COLD_PACKET_H

#include <stdint.h>

#define NPU_COLD_PACKET_MAGIC 0x314b5043u
#define NPU_COLD_PACKET_IDS 16384u
#define NPU_COLD_PACKET_BYTES 2048u
#define NPU_COLD_PACKET_WORDS (NPU_COLD_PACKET_IDS / 32u)

struct npu_cold_packet_plan {
    uint32_t packet_base;
    uint32_t packet_bytes;
};

struct npu_cold_packet_state {
    uint32_t magic;
    uint32_t epoch;
    uint32_t fault;
    uint32_t head;
    uint32_t count;
    uint32_t packet_base;
    uint32_t packet_bytes;
    uint32_t claimed[NPU_COLD_PACKET_WORDS];
};

enum npu_cold_packet_status {
    NPU_COLD_PACKET_OK,
    NPU_COLD_PACKET_ARGUMENT,
    NPU_COLD_PACKET_PLAN,
    NPU_COLD_PACKET_REINITIALIZE,
    NPU_COLD_PACKET_FAULT,
    NPU_COLD_PACKET_STALE,
    NPU_COLD_PACKET_CORRUPT,
    NPU_COLD_PACKET_EMPTY,
    NPU_COLD_PACKET_ID,
    NPU_COLD_PACKET_DUPLICATE,
};

struct npu_cold_packet_result {
    uint32_t status;
    uint32_t id;
    uint32_t address;
    uint32_t next_head;
    uint32_t committed;
};

struct npu_cold_packet_queue {
    volatile uint16_t *head;
    const volatile uint16_t *tail;
    const volatile uint16_t *ids;
    uint32_t capacity;
};

struct npu_cold_packet_queue_result {
    struct npu_cold_packet_result packet;
    uint32_t published;
};

/* Fixed cold PKT pool, not hot recycle. The platform supplies fresh coherent
 * storage, real reserved backing and exclusion of every metadata user. No API
 * releases ownership, clears fault or reinitializes an existing lifetime.
 * This pool must not alias the separate BA page pool or its ownership state. */
uint32_t npu_cold_packet_init(struct npu_cold_packet_state *state,
                             const struct npu_cold_packet_plan *plan, uint32_t epoch);
struct npu_cold_packet_result npu_cold_packet_take(
    struct npu_cold_packet_state *state, const struct npu_cold_packet_plan *plan,
    uint32_t epoch, uint32_t head, uint32_t tail, uint32_t id);

/* Validate pointer backing and acquire the native queue lock before this call;
 * retain it through snapshot/claim/head publication. A committed late fault
 * remains owned even if the native head cannot be published. Release an acquired
 * lock once, recheck lifetime and deny descriptor/readiness exposure on failure.
 * published is verified head publication, not a physical grant/drain witness. */
struct npu_cold_packet_queue_result npu_cold_packet_queue_take(
    struct npu_cold_packet_state *state, const struct npu_cold_packet_plan *plan,
    uint32_t epoch, const struct npu_cold_packet_queue *queue);
void npu_cold_packet_fault(struct npu_cold_packet_state *state);

#endif
