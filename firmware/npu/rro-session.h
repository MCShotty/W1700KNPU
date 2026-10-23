#ifndef W1700K_NPU_RRO_SESSION_H
#define W1700K_NPU_RRO_SESSION_H

#include "rro-wire.h"
#include "rro-native.h"
#include "cold-setup.h"

#define NPU_RRO_SESSION_MAGIC 0x3153524eu /* NRS1 */

/* Fresh boot-owned storage, serialized on the coordinator with IRQs excluded.
 * This object is never cleared or recreated by an attachment, error or CLOSE.
 * The platform retains the actual backing and references independently.
 */
struct npu_rro_session {
    uint32_t magic, error, inflight, sequence;
    struct npu_rro_plan plan;
    struct npu_rro_lifetime owner;
};

/* Caller first validates the actual pinned transport address/length/flags.
 * The supplied wire buffer and all metadata objects are separately owned.
 * MCU result messages report a host-correlated result, not a physical witness.
 */
int npu_rro_session_dispatch(struct npu_rro_session *, struct npu_control_v2_session *,
    struct npu_admission *, struct npu_barrier *, const struct npu_bootstrap *,
    const struct npu_cold_setup *, void *packet, uint32_t bytes,
    const struct npu_rro_native_context *);
int npu_rro_session_cold_ready(const struct npu_rro_session *);

#endif
