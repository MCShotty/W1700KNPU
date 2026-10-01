#ifndef W1700K_NPU_COLD_PAGE_H
#define W1700K_NPU_COLD_PAGE_H

#include <stdint.h>

#define NPU_COLD_PAGE_MAGIC 0x31475043u
#define NPU_COLD_PAGE_IDS 8192u
#define NPU_COLD_PAGE_BYTES 128u
#define NPU_COLD_PAGE_WORDS (NPU_COLD_PAGE_IDS / 32u)

struct npu_cold_page_plan {
    uint32_t packet_base;
    uint32_t packet_bytes;
};

struct npu_cold_page_state {
    uint32_t magic;
    uint32_t epoch;
    uint32_t fault;
    uint32_t head;
    uint32_t count;
    uint32_t packet_base;
    uint32_t packet_bytes;
    uint32_t claimed[NPU_COLD_PAGE_WORDS];
};

enum npu_cold_page_status {
    NPU_COLD_PAGE_OK,
    NPU_COLD_PAGE_ARGUMENT,
    NPU_COLD_PAGE_PLAN,
    NPU_COLD_PAGE_REINITIALIZE,
    NPU_COLD_PAGE_FAULT,
    NPU_COLD_PAGE_STALE,
    NPU_COLD_PAGE_CORRUPT,
    NPU_COLD_PAGE_EMPTY,
    NPU_COLD_PAGE_ID,
    NPU_COLD_PAGE_DUPLICATE,
};

struct npu_cold_page_result {
    uint32_t status;
    uint32_t id;
    uint32_t address;
    uint32_t next_head;
    uint32_t committed;
};

/* Selected cold initialization only, not the running page recycle protocol.
 * The caller independently contains prior users, supplies fresh zeroed coherent
 * storage and a fresh epoch, and serializes every ownership/queue metadata user.
 * The immutable plan describes real reserved backing in one address namespace;
 * geometry checks do not establish that reservation or physical containment.
 * No API releases claims, clears faults or reinitializes an existing lifetime.
 */
uint32_t npu_cold_page_init(struct npu_cold_page_state *state,
                           const struct npu_cold_page_plan *plan, uint32_t epoch);

/* head/tail/id are a caller-validated native queue snapshot. On OK the caller
 * commits next_head to the native queue before exposing a descriptor. All users
 * must honor the same serialization. A committed result remains owned even if
 * a concurrent fault changes its status to FAULT; never roll it back or retry
 * over it. If native-head publication cannot finish, hold the entire lifetime
 * faulted with its storage retained. The caller rechecks the actual lifetime
 * and retains resources/denies readiness on failure. OK is an ownership claim,
 * not permission to admit workers, publish readiness or reclaim storage.
 */
struct npu_cold_page_result npu_cold_page_take(
    struct npu_cold_page_state *state, const struct npu_cold_page_plan *plan,
    uint32_t epoch, uint32_t head, uint32_t tail, uint32_t id);

/* May be called concurrently to close this lifetime, never to reclaim it. */
void npu_cold_page_fault(struct npu_cold_page_state *state);

#endif
