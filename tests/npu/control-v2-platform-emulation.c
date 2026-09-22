/* Test-only replacement control endpoint. Fixed addresses are linker fixtures,
 * and the boot identity is seeded by the test loader before cold initialization. */
#include "control-v2.h"

extern struct npu_control_v2_session npu_emulation_control_v2_state;
extern const uint32_t npu_emulation_control_v2_boot[2];

static void control_v2_admission_init(struct npu_admission *admission)
{
    npu_admission_init(admission);
    npu_control_v2_init(&npu_emulation_control_v2_state,
                       npu_emulation_control_v2_boot[0],
                       npu_emulation_control_v2_boot[1]);
}

static int control_v2_dispatch(struct npu_admission *admission,
                               struct npu_barrier *barrier,
                               struct npu_control_packet *packet, uint32_t bytes)
{
    return npu_control_v2_dispatch(&npu_emulation_control_v2_state, admission,
                                    barrier, (struct npu_control_v2_packet *)packet, bytes);
}

#define npu_admission_init control_v2_admission_init
#define npu_admission_control control_v2_dispatch
#include "admission-platform-emulation.c"
