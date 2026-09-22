#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "control-client.h"

static void exchange(struct npu_control_client *client,
                     struct npu_admission *admission, struct npu_barrier *barrier)
{
    struct npu_control_packet packet;
    uint32_t ticket = npu_client_request(client, &packet, sizeof(packet));

    assert(ticket);
    assert(npu_admission_control(admission, barrier, &packet, sizeof(packet)));
    assert(npu_client_complete(client, ticket, 0, &packet, sizeof(packet)) ==
           NPU_CLIENT_ACCEPTED);
}

int main(void)
{
    struct npu_control_client client, before;
    struct npu_admission admission;
    struct npu_barrier barrier;
    unsigned char buffer[66], saved[66];
    uint32_t ticket, epoch, count = 0;

    npu_barrier_init(&barrier);
    npu_admission_init(&admission);
    npu_client_init(&client, 0x12345678, 0x9abcdef0);
    for (int i = 0; i < 3; i++)
        exchange(&client, &admission, &barrier);
    for (uint32_t hart = 1; hart < 8; hart++)
        assert(npu_barrier_poll(&barrier, hart, &epoch) == NPU_BARRIER_PARK);
    assert(npu_admission_idle(&admission, &barrier) == NPU_BARRIER_PARK);
    exchange(&client, &admission, &barrier);
    assert(client.phase == NPU_CLIENT_PARKED && client.drain_mask == 0);
    assert(!npu_barrier_reclaimable(&barrier, client.epoch));

    for (uint32_t length = 0; length < 128; length++) {
        if (length == 64)
            continue;
        npu_client_init(&client, 1, 0);
        assert(!npu_client_request(&client, (void *)(uintptr_t)1, length));
        assert(client.error == NPU_CLIENT_ARGUMENT);
        npu_client_init(&client, 1, 0);
        ticket = npu_client_request(&client, buffer + 1, 64);
        assert(ticket);
        assert(npu_client_complete(&client, ticket, 0, (void *)(uintptr_t)1,
                                   length) == NPU_CLIENT_REJECTED);
        count += 2;
    }
    for (int error = -2; error <= 2; error++) {
        if (!error)
            continue;
        npu_client_init(&client, 1, 0);
        memset(buffer, 0xa5, sizeof(buffer));
        ticket = npu_client_request(&client, buffer + 1, 64);
        assert(ticket && buffer[0] == 0xa5 && buffer[65] == 0xa5);
        before = client;
        memcpy(saved, buffer, sizeof(buffer));
        assert(!npu_client_request(&client, buffer + 1, 64));
        assert(!memcmp(&client, &before, sizeof(client)));
        assert(!memcmp(saved, buffer, sizeof(buffer)));
        assert(npu_client_complete(&client, ticket + 1, 0,
                                   (void *)(uintptr_t)1, 64) == NPU_CLIENT_IGNORED);
        assert(!memcmp(&client, &before, sizeof(client)));
        assert(npu_client_complete(&client, ticket, error,
                                   (void *)(uintptr_t)1, 64) == NPU_CLIENT_REJECTED);
        assert(client.error == NPU_CLIENT_TRANSPORT);
        before = client;
        assert(npu_client_complete(&client, ticket, 0,
                                   (void *)(uintptr_t)1, 64) == NPU_CLIENT_IGNORED);
        assert(!npu_client_request(&client, (void *)(uintptr_t)1, 64));
        npu_client_abort(&client);
        assert(!memcmp(&client, &before, sizeof(client)));
        count++;
    }
    npu_client_init(&client, 1, 0);
    ticket = npu_client_request(&client, buffer + 1, 64);
    npu_client_abort(&client);
    assert(client.error == NPU_CLIENT_ABORTED);
    assert(npu_client_complete(&client, ticket, 0, (void *)(uintptr_t)1, 64) ==
           NPU_CLIENT_IGNORED);
    count++;
    printf("{\"passed\":true,\"boundary_cases\":%u,\"native_round_trips\":4}\n", count);
    return 0;
}
