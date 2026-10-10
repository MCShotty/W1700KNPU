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

static void empty(void)
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
    const struct npu_bootstrap_plan plan = {.region = {
        {0x80000000, 0x240000}, {0x81000000, 0xe000}, {0x81200000, 0x100000},
        {0x81400000, 0x100000}, {0x81600000, 0x100000}, {0x83000000, 256}
    }};
    boot.plan = plan;
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
    {0x30, 10, 0}, {0x10, 14, 2}, {0x10, 1, 1536}, {0x12, 1, 1024},
    {0x15, 0, 0x200d45a0}, {0x15, 1, 256},
    {0x16, 0, 0x200d45b0}, {0x16, 1, 512},
    {0x17, 0, 0x200d45c0}, {0x17, 1, 1024},
    {0x18, 0, 0x2000a040}, {0x18, 1, 1536}, {0x13, 19, 0x2000a050},
    {0x10, 19, 0x200d4420}, {0x12, 19, 0x200d4450}, {0x10, 33, 8192}
};

static const struct npu_bootstrap_packet anchor[] = {
    {NPU_COLD_BIND_HEADER, NPU_COLD_BIND_BASE_API, 0x20000000},
    {NPU_COLD_BIND_HEADER, NPU_COLD_BIND_BYTES_API, 0x100000}
};

static void fresh(void)
{
    empty();
    uint32_t value;
    for (unsigned i = 0; i < 2; i++)
        check(!npu_linux_control_cold_exchange(&control, &anchor[i], &value));
    check(setup.completed == 24 && calls == 5);
}

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
    for (unsigned i = 0; i < sizeof(commands) / sizeof(commands[0]); i++) {
        uint32_t value = 0;
        check(!npu_linux_control_cold_exchange(&control, &commands[i], &value));
        check(value == (i ? commands[i].value : 0x457));
        check(!setup.inflight && !admission.active && !setup.failed);
    }
    check(setup.completed == 131071 && session.last_sequence == control.client.base.serial);
    check(!npu_linux_control_exchange(&control, NPU_CONTROL_STATUS));
    check(session.last_sequence == control.client.base.serial && !barrier.released && !barrier.armed);
    for (unsigned word = 0; word < 20; word++) {
        fresh();
        struct npu_cold_packet p;
        envelope(&p, 1);
        ((uint32_t *)&p)[word] ^= 1;
        if (word == 6) p.sequence = session.last_sequence;
        check(npu_cold_setup_begin(&setup, &session, &admission, &barrier, &boot, &p, sizeof(p)) != NPU_COLD_OK);
        check(!setup.inflight && !admission.active && setup.completed == 24);
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
    for (unsigned field = 0; field < 19; field++) {
        fresh();
        unsigned next = 1;
        if (field >= 14) {
            const unsigned selected[] = {2, 3, 5, 7, 9};
            uint32_t value;
            next = selected[field - 14] + 1;
            for (unsigned index = 1; index < next; index++)
                check(!npu_linux_control_cold_exchange(&control, &commands[index], &value));
        }
        unsigned before_completed = setup.completed;
        struct npu_cold_packet p;
        envelope(&p, next);
        check(!npu_cold_setup_begin(&setup, &session, &admission, &barrier, &boot, &p, sizeof(p)));
        struct npu_bootstrap_packet reply = setup.command;
        switch (field) {
        case 0: session.boot_lo++; break;
        case 1: session.boot_hi++; break;
        case 2: session.nonce_lo++; admission.nonce_lo++; break;
        case 3: session.nonce_hi++; admission.nonce_hi++; break;
        case 4: session.last_sequence++; break;
        case 5: barrier.parked[7] = 0; break;
        case 6: setup.completed = 25; break;
        case 7: admission.active = 2; break;
        case 8: reply.header++; break;
        case 9: reply.api++; break;
        case 10: reply.value++; break;
        case 11: callback_error = 1; break;
        case 12: setup.endpoint_base += 4096; break;
        case 13: setup.endpoint_bytes += 4096; break;
        default: setup.counts[field - 14]--; break;
        }
        check(npu_cold_setup_finish(&setup, &session, &admission, &barrier, &boot,
                                   callback_error ? 0 : 1, &reply) == NPU_COLD_CALLBACK_FAILED);
        check(setup.inflight == 1 && admission.active && setup.failed && setup.completed == (field == 6 ? 25u : before_completed));
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
    const uint32_t bases[] = {0, 1, 0x1fffffff, 0x20000000, 0x80000000, 0x81000000,
                              0x81200000, 0x81400000, 0x81600000, 0x83000000,
                              0xbff00000, 0xbffff000, 0xc0000000, 0xfffff000};
    const uint32_t lengths[] = {0, 1, 0xd4000, 0xd5000, 0x100000, 0x100001, 0x40000000, 0xfffff000};
    unsigned geometry_cases = 0, order_cases = 0;
    for (unsigned i = 0; i < sizeof(bases) / sizeof(bases[0]); i++)
        for (unsigned j = 0; j < sizeof(lengths) / sizeof(lengths[0]); j++) {
            empty();
            uint32_t value = 0xabcdef01;
            struct npu_bootstrap_packet command = anchor[0];
            command.value = bases[i];
            int base_ok = bases[i] && !(bases[i] & 4095u) && bases[i] < 0xc0000000u;
            check(npu_linux_control_cold_exchange(&control, &command, &value) == (base_ok ? 0 : -EPROTO));
            if (base_ok) {
                command = anchor[1]; command.value = lengths[j];
                int valid = npu_cold_endpoint_valid(bases[i], lengths[j]);
                for (unsigned k = 0; k < 6; k++)
                    if ((uint64_t)bases[i] < (uint64_t)boot.plan.region[k].base + boot.plan.region[k].bytes &&
                        boot.plan.region[k].base < (uint64_t)bases[i] + lengths[j]) valid = 0;
                check(npu_linux_control_cold_exchange(&control, &command, &value) == (valid ? 0 : -EPROTO));
                check(setup.completed == (valid ? 24u : 8u));
            }
            check(!setup.inflight && !admission.active);
            geometry_cases++;
        }
    for (unsigned index = 1; index < sizeof(commands) / sizeof(commands[0]); index++)
        for (unsigned kind = 0; kind < 6; kind++) {
            fresh();
            uint32_t value = 0;
            for (unsigned before = 1; before < index; before++)
                check(!npu_linux_control_cold_exchange(&control, &commands[before], &value));
            struct npu_bootstrap_packet command = commands[index];
            if (kind == 0) {
                check(!npu_linux_control_cold_exchange(&control, &command, &value));
                /* Every state-changing command is one shot. */
            } else if (kind == 1) {
                setup.completed ^= 1;
            } else if (kind == 2) {
                command.value = 0;
            } else if (kind == 3) {
                command.value = command.api == 0 ? command.value + 16 : command.value + 1;
            } else if (kind == 4) {
                command.header = 0x19; /* Selector9 remains unimplemented. */
            } else {
                command.header = 0x1f; command.api = 0; /* Native selector15 writes saved bases. */
            }
            check(npu_linux_control_cold_exchange(&control, &command, &value) == -EPROTO);
            check(setup.failed && !setup.inflight && !admission.active && admission.fault && barrier.fault);
            order_cases++;
        }
    for (unsigned changed = 0; changed < 5; changed++) {
        fresh();
        uint32_t value = 0;
        const unsigned selected[] = {2, 3, 5, 7, 9};
        for (unsigned index = 1; index < 10; index++) {
            struct npu_bootstrap_packet command = commands[index];
            if (index == selected[changed]) command.value--;
            check(!npu_linux_control_cold_exchange(&control, &command, &value));
        }
        check(npu_linux_control_cold_exchange(&control, &commands[10], &value) == -EPROTO);
        check(setup.completed == 2047 && setup.failed && !setup.inflight && !admission.active);
    }
    const uint32_t tx_lengths[] = {0xd5000, 0xd8000, 0xd9000, 0x100000};
    const uint32_t tx_offsets[] = {0xd4450, 0xd8450, 0xd4454, 0xd8454};
    unsigned tx_geometry_cases = 0;
    for (unsigned length = 0; length < 4; length++)
        for (unsigned offset = 0; offset < 4; offset++) {
            empty();
            uint32_t value = 0;
            struct npu_bootstrap_packet command = anchor[1];
            command.value = tx_lengths[length];
            check(!npu_linux_control_cold_exchange(&control, &anchor[0], &value));
            check(!npu_linux_control_cold_exchange(&control, &command, &value));
            for (unsigned index = 1; index < 14; index++)
                check(!npu_linux_control_cold_exchange(&control, &commands[index], &value));
            command = commands[14]; command.value = 0x20000000 + tx_offsets[offset];
            int valid = offset < 2 && tx_offsets[offset] + 12 <= tx_lengths[length];
            check(npu_linux_control_cold_exchange(&control, &command, &value) == (valid ? 0 : -EPROTO));
            check(setup.completed == (valid ? 65535u : 32767u));
            check(!setup.inflight && !admission.active);
            if (valid) {
                check(!npu_linux_control_cold_exchange(&control, &commands[15], &value));
                check(setup.completed == 131071 && !setup.failed);
            } else check(setup.failed && admission.fault && barrier.fault);
            tx_geometry_cases++;
        }
    unsigned total = cases;
    npu_linux_control_close(&control);
    check(!pthread_mutex_destroy(&control.mutex.native));
    printf("{\"passed\":true,\"cases\":%u,\"request_fields\":20,\"reply_fields\":20,"
           "\"bad_lengths\":128,\"held_controls\":38,\"late_controls\":19,\"transport_faults\":8,"
           "\"geometry_cases\":%u,\"order_cases\":%u,\"partial_prefix_controls\":5,"
           "\"tx_geometry_cases\":%u}\n", total, geometry_cases, order_cases, tx_geometry_cases);
    return 0;
}
