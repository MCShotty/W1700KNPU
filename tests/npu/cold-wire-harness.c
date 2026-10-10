#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "linux-control.h"
#include "bootstrap-v2.h"

struct airoha_npu { unsigned unused; };
static struct airoha_npu provider;
static struct npu_cold_setup setup;
static struct npu_bootstrap boot;
static struct npu_control_v2_session session;
static struct npu_admission admission;
static struct npu_barrier barrier;
static struct npu_linux_control control;
static unsigned calls, cases;
static int transport_error, after_effect;
static unsigned corrupt_word, corrupt, callback_error;

static void check(int condition)
{
    assert(condition);
}

int airoha_npu_wlan_control(struct airoha_npu *npu, void *packet, int bytes)
{
    check(npu == &provider && bytes == 80);
    calls++;
    if (transport_error && !after_effect)
        return transport_error;
    uint32_t *words = packet;
    if (words[2] == NPU_CONTROL_V2_REQUEST) {
        check(npu_bootstrap_v2_control(&boot, &session, &admission, &barrier, packet, bytes));
    } else {
        struct npu_cold_packet *p = packet;
        enum npu_cold_status status = npu_cold_setup_begin(&setup, &session,
            &admission, &barrier, &boot, p, bytes);
        if (status == NPU_COLD_OK) {
            struct npu_bootstrap_packet reply = setup.command;
            if (reply.header == 0x30)
                reply.value = 0x457;
            status = npu_cold_setup_finish(&setup, &session, &admission, &barrier,
                                          &boot, callback_error ? 0 : 1, &reply);
            if (status == NPU_COLD_OK)
                p->command = reply;
        }
        p->status = status;
        p->magic = NPU_COLD_REPLY;
    }
    if (corrupt) words[corrupt_word] ^= 1;
    return transport_error;
}

static void fresh(void)
{
    if (cases) {
        npu_linux_control_close(&control);
        check(!pthread_mutex_destroy(&control.mutex.native));
    }
    cases++;
    memset(&setup, 0, sizeof(setup));
    memset(&boot, 0, sizeof(boot));
    memset(&control, 0, sizeof(control));
    npu_barrier_init(&barrier);
    npu_admission_init(&admission);
    for (unsigned i = 0; i < 8; i++) barrier.parked[i] = 1;
    boot.magic = NPU_BOOTSTRAP_MAGIC;
    boot.step = NPU_BOOTSTRAP_STEPS;
    boot.retained_mask = 0x1e;
    npu_control_v2_init(&session, 1, 2);
    transport_error = after_effect = corrupt = callback_error = 0;
    calls = 0;
    check(!npu_linux_control_init(&control, &provider, 3, 4));
    check(!npu_linux_control_exchange(&control, NPU_CONTROL_DISCOVER));
    check(!npu_linux_control_exchange(&control, NPU_CONTROL_BIND));
    check(!npu_linux_control_exchange(&control, NPU_CONTROL_STOP));
    check(control.client.base.phase == NPU_CLIENT_PARKED && calls == 3);
}

static const struct npu_bootstrap_packet commands[] = {
    {0x30, 10, 0}, {0x10, 14, 2}, {0x10, 1, 1536}, {0x12, 1, 1024}
};

static void envelope(struct npu_cold_packet *p, unsigned command)
{
    check(npu_cold_client_request(&control.client, p, sizeof(*p), &commands[command]));
}

static void sticky(int error, unsigned old_calls)
{
    uint32_t value = 0xabcdef01;
    check(npu_linux_control_cold_exchange(&control, &commands[0], &value) == error);
    check(value == 0xabcdef01 && calls == old_calls);
    npu_linux_control_close(&control);
    check(npu_linux_control_cold_exchange(&control, &commands[0], &value) == error);
    check(calls == old_calls && !barrier.released && !barrier.armed);
}

int main(void)
{
    fresh();
    for (unsigned i = 0; i < 4; i++) {
        uint32_t value = 0;
        check(!npu_linux_control_cold_exchange(&control, &commands[i], &value));
        check(value == (i ? commands[i].value : 0x457));
        check(!setup.inflight && !admission.active && !setup.failed);
    }
    check(setup.completed == 7 && session.last_sequence == control.client.base.serial);
    check(!npu_linux_control_exchange(&control, NPU_CONTROL_STATUS));
    check(session.last_sequence == control.client.base.serial && !barrier.released && !barrier.armed);
    for (unsigned word = 0; word < 20; word++) {
        fresh();
        struct npu_cold_packet p;
        envelope(&p, 1);
        ((uint32_t *)&p)[word] ^= 1;
        if (word == 6) p.sequence = session.last_sequence;
        check(npu_cold_setup_begin(&setup, &session, &admission, &barrier, &boot, &p, sizeof(p)) != NPU_COLD_OK);
        check(!setup.inflight && !admission.active && !setup.completed);
    }
    for (unsigned bytes = 0; bytes <= 128; bytes++) {
        if (bytes == 80) continue;
        fresh();
        check(npu_cold_setup_begin(&setup, &session, &admission, &barrier, &boot,
                                  (const void *)(uintptr_t)1, bytes) == NPU_COLD_BAD_MESSAGE);
        check(!admission.active && !setup.inflight);
    }
    for (unsigned field = 0; field < 38; field++) {
        fresh();
        struct npu_cold_packet p;
        envelope(&p, 1);
        if (field < 8) barrier.parked[field] = 0;
        else if (field < 16) barrier.ready[field - 8] = 1;
        else if (field < 21) barrier.drained[field - 16] = 1;
        else if (field < 27) admission.deferred[field - 21] = 1;
        else switch (field) {
        case 27: barrier.request = 2; break;
        case 28: barrier.released = 1; break;
        case 29: barrier.prepared = 1; break;
        case 30: barrier.armed = 1; break;
        case 31: barrier.fault = 1; break;
        case 32: admission.closed = 0; break;
        case 33: admission.active = 1; break;
        case 34: boot.step = 5; break;
        case 35: boot.retained_mask = 0; break;
        case 36: boot.inflight = 1; break;
        case 37: setup.completed = 8; break;
        }
        check(npu_cold_setup_begin(&setup, &session, &admission, &barrier, &boot, &p, sizeof(p)) == NPU_COLD_BAD_STATE);
        check(setup.failed && admission.fault && barrier.fault);
    }
    for (unsigned field = 0; field < 12; field++) {
        fresh();
        struct npu_cold_packet p;
        envelope(&p, 1);
        check(!npu_cold_setup_begin(&setup, &session, &admission, &barrier, &boot, &p, sizeof(p)));
        struct npu_bootstrap_packet reply = setup.command;
        switch (field) {
        case 0: session.boot_lo++; break;
        case 1: session.boot_hi++; break;
        case 2: session.nonce_lo++; admission.nonce_lo++; break;
        case 3: session.nonce_hi++; admission.nonce_hi++; break;
        case 4: session.last_sequence++; break;
        case 5: barrier.parked[7] = 0; break;
        case 6: setup.completed = 1; break;
        case 7: admission.active = 2; break;
        case 8: reply.header++; break;
        case 9: reply.api++; break;
        case 10: reply.value++; break;
        case 11: callback_error = 1; break;
        }
        check(npu_cold_setup_finish(&setup, &session, &admission, &barrier, &boot,
                                   callback_error ? 0 : 1, &reply) == NPU_COLD_CALLBACK_FAILED);
        check(setup.inflight == 1 && admission.active && setup.failed && setup.completed == (field == 6 ? 1u : 0u));
    }
    for (unsigned word = 0; word < 20; word++) {
        fresh(); corrupt = 1; corrupt_word = word;
        uint32_t value = 0xabcdef01;
        check(npu_linux_control_cold_exchange(&control, &commands[0], &value) == -EPROTO);
        check(value == 0xabcdef01);
        sticky(-EPROTO, calls);
    }
    for (unsigned effect = 0; effect < 2; effect++)
        for (unsigned kind = 0; kind < 4; kind++) {
            fresh(); after_effect = effect;
            transport_error = kind == 0 ? -ETIMEDOUT : kind == 1 ? -EBUSY : kind == 2 ? -EIO : 1;
            int expected = transport_error < 0 ? transport_error : -EIO;
            uint32_t value = 0xabcdef01;
            check(npu_linux_control_cold_exchange(&control, &commands[0], &value) == expected);
            check(value == 0xabcdef01);
            sticky(expected, calls);
        }
    fresh();
    struct npu_cold_packet p;
    envelope(&p, 1);
    check(!npu_cold_setup_begin(&setup, &session, &admission, &barrier, &boot, &p, sizeof(p)));
    struct npu_bootstrap_packet reply = setup.command;
    check(!npu_cold_setup_finish(&setup, &session, &admission, &barrier, &boot, 1, &reply));
    check(npu_cold_setup_begin(&setup, &session, &admission, &barrier, &boot, &p, sizeof(p)) == NPU_COLD_REPLAY);
    fresh(); envelope(&p, 2);
    check(npu_cold_setup_begin(&setup, &session, &admission, &barrier, &boot, &p, sizeof(p)) == NPU_COLD_BAD_STATE);
    check(session.last_sequence == p.sequence && !admission.active);
    unsigned total = cases;
    npu_linux_control_close(&control);
    check(!pthread_mutex_destroy(&control.mutex.native));
    printf("{\"passed\":true,\"cases\":%u,\"request_fields\":20,\"reply_fields\":20,"
           "\"bad_lengths\":128,\"held_controls\":38,\"late_controls\":12,\"transport_faults\":8}\n", total);
    return 0;
}
