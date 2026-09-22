#ifndef W1700K_NPU_BOOTSTRAP_V2_H
#define W1700K_NPU_BOOTSTRAP_V2_H

#include "bootstrap.h"
#include "control-v2.h"

/* The gated V2 dispatch is supplied by the bootstrap candidate patch. It still
 * consumes a valid request sequence before returning a platform BIND error. */
int npu_control_v2_dispatch_gate(struct npu_control_v2_session *session,
                                  struct npu_admission *admission,
                                  struct npu_barrier *barrier,
                                  struct npu_control_v2_packet *packet,
                                  uint32_t bytes, enum npu_control_status bind_status);

/* Cold, independently contained initialization only; failed attempts preserve
 * the session and fault common admission instead of erasing old ownership. */
int npu_bootstrap_v2_session_init(struct npu_control_v2_session *session,
                                   struct npu_admission *admission,
                                   struct npu_barrier *barrier,
                                   uint32_t boot_lo, uint32_t boot_hi);
int npu_bootstrap_v2_transport(const struct npu_bootstrap *bootstrap,
                                uint32_t address, uint32_t bytes, uint32_t flags);
int npu_bootstrap_v2_control(const struct npu_bootstrap *bootstrap,
                              struct npu_control_v2_session *session,
                              struct npu_admission *admission,
                              struct npu_barrier *barrier,
                              struct npu_control_v2_packet *packet, uint32_t bytes);

#endif
