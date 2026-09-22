#include "control-client.h"

_Static_assert(NPU_BARRIER_WORKERS == 8, "client worker mask changed");
_Static_assert(NPU_BARRIER_DOMAINS == 5, "client drain mask changed");
_Static_assert(NPU_CONTROL_SIZE == 64, "client wire size changed");
_Static_assert(NPU_CONTROL_CAPS == 7, "client needs a reviewed capability contract");

static uint32_t read_word(const unsigned char *bytes, uint32_t word)
{
    const unsigned char *p = bytes + word * 4;

    return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
           (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static void write_word(unsigned char *bytes, uint32_t word, uint32_t value)
{
    unsigned char *p = bytes + word * 4;

    p[0] = (unsigned char)value;
    p[1] = (unsigned char)(value >> 8);
    p[2] = (unsigned char)(value >> 16);
    p[3] = (unsigned char)(value >> 24);
}

static enum npu_client_result fail(struct npu_control_client *s,
                                   enum npu_client_error error)
{
    s->phase = NPU_CLIENT_FAILED;
    s->error = error;
    s->pending = 0;
    return NPU_CLIENT_REJECTED;
}

void npu_client_init(struct npu_control_client *s, uint32_t nonce_lo,
                     uint32_t nonce_hi)
{
    s->phase = NPU_CLIENT_NEW;
    s->error = NPU_CLIENT_NO_ERROR;
    s->nonce_lo = nonce_lo;
    s->nonce_hi = nonce_hi;
    s->serial = s->pending = s->operation = 0;
    s->epoch = s->released = s->armed = 0;
    s->parked_mask = s->ready_mask = s->drain_mask = s->capabilities = 0;
    if (!(nonce_lo || nonce_hi))
        fail(s, NPU_CLIENT_ARGUMENT);
}

void npu_client_abort(struct npu_control_client *s)
{
    if (s->phase != NPU_CLIENT_FAILED)
        fail(s, NPU_CLIENT_ABORTED);
}

uint32_t npu_client_request(struct npu_control_client *s, void *request,
                            uint32_t bytes)
{
    uint32_t operation, i;

    if (s->phase == NPU_CLIENT_FAILED || s->pending)
        return 0;
    if (!request || bytes != NPU_CONTROL_SIZE) {
        fail(s, NPU_CLIENT_ARGUMENT);
        return 0;
    }
    switch (s->phase) {
    case NPU_CLIENT_NEW:
        operation = NPU_CONTROL_DISCOVER;
        break;
    case NPU_CLIENT_DISCOVERED:
        operation = NPU_CONTROL_BIND;
        break;
    case NPU_CLIENT_BOUND:
        operation = NPU_CONTROL_STOP;
        break;
    case NPU_CLIENT_STOPPING:
    case NPU_CLIENT_PARKED:
        operation = NPU_CONTROL_STATUS;
        break;
    default:
        fail(s, NPU_CLIENT_ARGUMENT);
        return 0;
    }
    if (s->serial == UINT32_MAX ||
        (operation == NPU_CONTROL_STOP && s->epoch == UINT32_MAX &&
         s->released == s->epoch)) {
        fail(s, NPU_CLIENT_EXHAUSTED);
        return 0;
    }
    for (i = 0; i < NPU_CONTROL_SIZE / 4; i++)
        write_word(request, i, 0);
    write_word(request, 0, NPU_CONTROL_HEADER);
    write_word(request, 1, NPU_CONTROL_API);
    write_word(request, 2, NPU_CONTROL_REQUEST);
    write_word(request, 3, NPU_CONTROL_VERSION);
    write_word(request, 4, NPU_CONTROL_SIZE);
    write_word(request, 5, operation);
    write_word(request, 6, s->epoch);
    write_word(request, 7, s->nonce_lo);
    write_word(request, 8, s->nonce_hi);
    s->operation = operation;
    s->pending = ++s->serial;
    return s->pending;
}

enum npu_client_result npu_client_complete(struct npu_control_client *s,
                                          uint32_t ticket, int transport_error,
                                          const void *reply, uint32_t bytes)
{
    uint32_t epoch, released, armed, parked, ready, drained, expected;

    /* Reject unrelated/late completions before looking at their storage. */
    if (!ticket || !s->pending || ticket != s->pending ||
        s->phase == NPU_CLIENT_FAILED)
        return NPU_CLIENT_IGNORED;
    if (transport_error)
        return fail(s, NPU_CLIENT_TRANSPORT);
    if (!reply || bytes != NPU_CONTROL_SIZE)
        return fail(s, NPU_CLIENT_ARGUMENT);
    if (read_word(reply, 0) != NPU_CONTROL_HEADER ||
        read_word(reply, 1) != NPU_CONTROL_API ||
        read_word(reply, 2) != NPU_CONTROL_REPLY ||
        read_word(reply, 3) != NPU_CONTROL_VERSION ||
        read_word(reply, 4) != NPU_CONTROL_SIZE ||
        read_word(reply, 5) != s->operation ||
        read_word(reply, 7) != s->nonce_lo ||
        read_word(reply, 8) != s->nonce_hi)
        return fail(s, NPU_CLIENT_ENVELOPE);
    /* V1 has no supported reclaim/restart contract, even if a peer sets bits. */
    if (read_word(reply, 10) != NPU_CONTROL_CAPS)
        return fail(s, NPU_CLIENT_CAPABILITY);
    if (read_word(reply, 9) != NPU_CONTROL_OK)
        return fail(s, NPU_CLIENT_REMOTE);

    epoch = read_word(reply, 6);
    released = read_word(reply, 14);
    armed = read_word(reply, 15);
    parked = read_word(reply, 11);
    ready = read_word(reply, 12);
    drained = read_word(reply, 13);
    expected = s->epoch;
    if (s->operation == NPU_CONTROL_STOP && s->released == expected)
        expected++;
    if (!epoch || (s->operation != NPU_CONTROL_DISCOVER && epoch != expected))
        return fail(s, NPU_CLIENT_GENERATION);
    if ((parked & ~0xffu) || (ready & ~0xffu) || (drained & ~0x1fu) ||
        released > epoch || armed > released ||
        (ready && released != epoch) || (drained && parked != 0xffu) ||
        (armed == epoch && ready != 0xffu))
        return fail(s, NPU_CLIENT_SNAPSHOT);
    if (s->operation == NPU_CONTROL_STOP || s->operation == NPU_CONTROL_STATUS) {
        if (released == epoch || ready || armed == epoch)
            return fail(s, NPU_CLIENT_SNAPSHOT);
        if (s->operation == NPU_CONTROL_STATUS &&
            (released != s->released || armed != s->armed ||
             (parked & s->parked_mask) != s->parked_mask ||
             (drained & s->drain_mask) != s->drain_mask))
            return fail(s, NPU_CLIENT_SNAPSHOT);
        s->phase = parked == 0xffu ? NPU_CLIENT_PARKED : NPU_CLIENT_STOPPING;
    } else {
        s->phase = s->operation == NPU_CONTROL_DISCOVER ?
                   NPU_CLIENT_DISCOVERED : NPU_CLIENT_BOUND;
    }
    s->epoch = epoch;
    s->released = released;
    s->armed = armed;
    s->parked_mask = parked;
    s->ready_mask = ready;
    s->drain_mask = drained;
    s->capabilities = read_word(reply, 10);
    s->pending = 0;
    return NPU_CLIENT_ACCEPTED;
}
