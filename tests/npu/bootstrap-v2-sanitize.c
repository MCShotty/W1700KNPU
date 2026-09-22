#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "bootstrap-v2.h"

static const struct npu_bootstrap_plan plan = { .region = {
#include "bootstrap-v2-plan.inc"
} };
static struct npu_bootstrap bootstrap;
static struct npu_control_v2_session session;
static struct npu_admission admission;
static struct npu_barrier barrier;
static struct npu_control_v2_client client;
static struct npu_control_v2_packet wire;
static unsigned int assertions;

static void check(int condition)
{
    assert(condition);
    assertions++;
}

static void fresh(void)
{
    memset(&bootstrap, 0, sizeof(bootstrap));
    memset(&session, 0, sizeof(session));
    npu_barrier_init(&barrier);
    npu_admission_init(&admission);
    check(npu_bootstrap_v2_session_init(&session, &admission, &barrier, 1, 2));
    check(npu_bootstrap_init(&bootstrap, &plan));
    npu_client_v2_init(&client, 3, 4);
}

static void setup_step(unsigned int step)
{
    static const uint32_t api[] = {18, 32, 8, 23, 7, 12};
    struct npu_bootstrap_packet p = {
        .header = step ? 0x10 : 0x11,
        .api = api[step],
        .value = step >= 1 && step <= 4 ? plan.region[step].base : 0,
    };

    check(npu_bootstrap_begin(&bootstrap, &admission, &barrier, &p, sizeof(p)));
    /* Only this harness models callback success; native tests execute the
     * original wrappers/setters independently against explicit MMIO models. */
    check(npu_bootstrap_finish(&bootstrap, &admission, &barrier, 1));
}

static uint32_t request(void)
{
    uint32_t ticket = npu_client_v2_request(&client, &wire, sizeof(wire));

    check(ticket != 0);
    check(npu_bootstrap_v2_transport(&bootstrap, plan.region[NPU_BOOT_REQUEST].base,
                                     sizeof(wire), 1));
    return ticket;
}

static void exchange(void)
{
    uint32_t ticket = request();

    check(npu_bootstrap_v2_control(&bootstrap, &session, &admission, &barrier,
                                   &wire, sizeof(wire)));
    check(npu_client_v2_complete(&client, ticket, 0, &wire, sizeof(wire)) == NPU_CLIENT_ACCEPTED);
}

int main(void)
{
    for (unsigned int early = 0; early < 6; early++) {
        fresh();
        exchange();
        for (unsigned int step = 0; step < early; step++)
            setup_step(step);
        uint32_t ticket = request();
        struct npu_control_v2_packet abandoned = wire;
        check(npu_bootstrap_v2_control(&bootstrap, &session, &admission, &barrier,
                                       &wire, sizeof(wire)));
        check(wire.v1.status == NPU_CONTROL_BUSY && !admission.nonce_lo && !admission.nonce_hi);
        check(npu_client_v2_complete(&client, ticket, 0, &wire, sizeof(wire)) == NPU_CLIENT_REJECTED);
        for (unsigned int step = early; step < 6; step++)
            setup_step(step);
        check(npu_bootstrap_v2_control(&bootstrap, &session, &admission, &barrier,
                                       &abandoned, sizeof(abandoned)));
        check(abandoned.v1.status == NPU_CONTROL_REPLAY && !admission.nonce_lo && !admission.nonce_hi);
        check(npu_client_v2_complete(&client, ticket, 0,
                                      (void *)(uintptr_t)1, 80) == NPU_CLIENT_IGNORED);
        check(!npu_client_v2_request(&client, (void *)(uintptr_t)1, 80));
    }
    fresh();
    exchange();
    for (unsigned int step = 0; step < 6; step++)
        setup_step(step);
    exchange();
    exchange();
    exchange();
    check(client.base.phase == NPU_CLIENT_STOPPING && !client.base.drain_mask);
    check(!barrier.released && !barrier.armed);
    for (uint32_t length = 0; length <= 128; length++) {
        if (length == NPU_CONTROL_V2_SIZE)
            continue;
        struct npu_control_v2_session before = session;
        check(!npu_bootstrap_v2_control(&bootstrap, &session, &admission, &barrier,
                                         (void *)(uintptr_t)1, length));
        check(!memcmp(&before, &session, sizeof(session)));
    }
    struct npu_control_v2_session retained = session;
    check(!npu_bootstrap_v2_session_init(&session, &admission, &barrier, 5, 6));
    check(!memcmp(&retained, &session, sizeof(session)));
    check(admission.fault && barrier.fault);
    printf("{\"passed\":true,\"assertions\":%u,\"early_bind_cases\":6,"
           "\"invalid_lengths\":128,\"physical_drains\":false}\n", assertions);
    return 0;
}
