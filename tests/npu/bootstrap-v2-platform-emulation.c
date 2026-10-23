/* Test-only composition with the original cold-start and six-command binding. */
#include "bootstrap-v2.h"
#include "cold-setup.h"
#ifdef NPU_EMULATION_RRO_WIRE
#include "rro-wire.h"
#include "rro-wire-native-abi.h"
#endif
extern int npu_emulation_cold_mailbox(struct npu_cold_packet *, uint32_t);

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
#ifdef NPU_EMULATION_RRO_WIRE
    if (bytes == NPU_RRO_WIRE_SIZE && packet->v1.header == NPU_CONTROL_HEADER &&
        packet->v1.api == NPU_RRO_WIRE_API && packet->v1.magic == NPU_RRO_WIRE_REQUEST)
        return ((int (*)(void *, uint32_t))(uintptr_t)NPU_RRO_NATIVE_MAILBOX_VENEER)(packet, bytes);
#endif
    if (bytes == NPU_COLD_SIZE && packet->v1.header == NPU_CONTROL_HEADER &&
        packet->v1.api == NPU_COLD_API && packet->v1.magic == NPU_COLD_REQUEST)
        return npu_emulation_cold_mailbox((struct npu_cold_packet *)packet, bytes);
    return npu_bootstrap_v2_control(&npu_emulation_bootstrap_state, session,
                                    admission, barrier, packet, bytes);
}

#define npu_control_v2_init bootstrap_session_init
#define npu_control_v2_dispatch bootstrap_control
#define npu_bootstrap_transport npu_bootstrap_v2_transport
#include "control-v2-platform-emulation.c"
