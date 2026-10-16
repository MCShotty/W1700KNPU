/* Dispatch-only fixture: begin/finish and callback execution are explicit stubs. */
#include "cold-setup.h"

struct npu_bootstrap npu_emulation_bootstrap_state;
struct npu_control_v2_session npu_emulation_control_v2_state;
struct npu_admission npu_emulation_admission_state;
struct npu_barrier npu_emulation_barrier_state;
extern struct npu_cold_setup npu_emulation_cold_setup_state;
extern int npu_emulation_cold_mailbox(struct npu_cold_packet *, uint32_t);
uint32_t npu_test_dispatch_observed[6];
static uint32_t fixture_begin;

enum npu_cold_status npu_cold_setup_begin(struct npu_cold_setup *s,
    struct npu_control_v2_session *session, struct npu_admission *a,
    struct npu_barrier *b, const struct npu_bootstrap *boot,
    const struct npu_cold_packet *packet, uint32_t bytes)
{
    (void)session; (void)a; (void)b; (void)boot; (void)bytes;
    s->command = packet->command;
    npu_test_dispatch_observed[0]++;
    return fixture_begin;
}

enum npu_cold_status npu_cold_setup_finish(struct npu_cold_setup *s,
    struct npu_control_v2_session *session, struct npu_admission *a,
    struct npu_barrier *b, const struct npu_bootstrap *boot,
    uint32_t result, const struct npu_bootstrap_packet *reply)
{
    (void)s; (void)session; (void)a; (void)b; (void)boot; (void)reply;
    npu_test_dispatch_observed[1]++;
    npu_test_dispatch_observed[2] = result;
    return result == 1 ? NPU_COLD_OK : NPU_COLD_CALLBACK_FAILED;
}

uint32_t npu_test_dispatch(uint32_t header, uint32_t api, uint32_t bytes, uint32_t begin)
{
    struct npu_cold_packet packet;
    volatile unsigned char *clear = (volatile void *)&packet;

    for (uint32_t i = 0; i < sizeof(packet); i++) clear[i] = 0;
    for (uint32_t i = 0; i < 6; i++) npu_test_dispatch_observed[i] = 0;
    packet.command.header = header;
    packet.command.api = api;
    packet.command.value = 0x12345678;
    fixture_begin = begin;
    uint32_t result = npu_emulation_cold_mailbox(&packet, bytes);
    npu_test_dispatch_observed[3] = result;
    npu_test_dispatch_observed[4] = packet.status;
    npu_test_dispatch_observed[5] = packet.magic;
    return result;
}
