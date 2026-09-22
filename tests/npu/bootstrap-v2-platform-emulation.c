/* Test-only composition with the original cold-start and six-command binding. */
#include "bootstrap-v2.h"

#ifndef NPU_EMULATION_BOOTSTRAP
#error "V2 bootstrap binding requires the cold-bootstrap profile"
#endif

extern struct npu_bootstrap npu_emulation_bootstrap_state;
extern struct npu_admission npu_emulation_admission_state;
extern struct npu_barrier npu_emulation_barrier_state;

static void bootstrap_session_init(struct npu_control_v2_session *session,
                                    uint32_t boot_lo, uint32_t boot_hi)
{
    npu_bootstrap_v2_session_init(session, &npu_emulation_admission_state,
                                  &npu_emulation_barrier_state, boot_lo, boot_hi);
}

static int bootstrap_control(struct npu_control_v2_session *session,
                              struct npu_admission *admission,
                              struct npu_barrier *barrier,
                              struct npu_control_v2_packet *packet, uint32_t bytes)
{
    return npu_bootstrap_v2_control(&npu_emulation_bootstrap_state, session,
                                    admission, barrier, packet, bytes);
}

#define npu_control_v2_init bootstrap_session_init
#define npu_control_v2_dispatch bootstrap_control
#define npu_bootstrap_transport npu_bootstrap_v2_transport
#include "control-v2-platform-emulation.c"
