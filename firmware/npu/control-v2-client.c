#include "control-v2.h"

_Static_assert(NPU_CONTROL_V2_CAPS == 0x27, "review V2 capability semantics");

static uint32_t read_word(const unsigned char *p, uint32_t word)
{
    p += word * 4;
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
           (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static void write_word(unsigned char *p, uint32_t word, uint32_t value)
{
    p += word * 4;
    p[0] = (unsigned char)value;
    p[1] = (unsigned char)(value >> 8);
    p[2] = (unsigned char)(value >> 16);
    p[3] = (unsigned char)(value >> 24);
}

static enum npu_client_result fail(struct npu_control_v2_client *s,
                                   enum npu_client_v2_error error)
{
    if (s->base.phase != NPU_CLIENT_FAILED) {
        s->error = error;
        npu_client_abort(&s->base);
    }
    return NPU_CLIENT_REJECTED;
}

void npu_client_v2_init(struct npu_control_v2_client *s,
                        uint32_t nonce_lo, uint32_t nonce_hi)
{
    npu_client_init(&s->base, nonce_lo, nonce_hi);
    s->boot_lo = s->boot_hi = s->error = 0;
}

void npu_client_v2_abort(struct npu_control_v2_client *s)
{
    npu_client_abort(&s->base);
}

uint32_t npu_client_v2_request(struct npu_control_v2_client *s,
                               void *request, uint32_t bytes)
{
    uint32_t ticket;

    if (s->base.phase == NPU_CLIENT_FAILED || s->base.pending)
        return 0;
    if (!request || bytes != NPU_CONTROL_V2_SIZE) {
        fail(s, NPU_CLIENT_V2_ARGUMENT);
        return 0;
    }
    ticket = npu_client_request(&s->base, request, NPU_CONTROL_SIZE);
    if (!ticket)
        return 0;
    write_word(request, 2, NPU_CONTROL_V2_REQUEST);
    write_word(request, 3, NPU_CONTROL_V2_VERSION);
    write_word(request, 4, NPU_CONTROL_V2_SIZE);
    write_word(request, 16, ticket);
    write_word(request, 17, s->boot_lo);
    write_word(request, 18, s->boot_hi);
    write_word(request, 19, 0);
    return ticket;
}

enum npu_client_result npu_client_v2_complete(struct npu_control_v2_client *s,
                                              uint32_t ticket, int transport_error,
                                              const void *reply, uint32_t bytes)
{
    unsigned char normalized[NPU_CONTROL_SIZE];
    uint32_t boot_lo, boot_hi, i;
    enum npu_client_result result;

    if (!ticket || !s->base.pending || ticket != s->base.pending ||
        s->base.phase == NPU_CLIENT_FAILED)
        return NPU_CLIENT_IGNORED;
    if (transport_error)
        return npu_client_complete(&s->base, ticket, transport_error, 0, 0);
    if (!reply || bytes != NPU_CONTROL_V2_SIZE)
        return fail(s, NPU_CLIENT_V2_ARGUMENT);
    if (read_word(reply, 2) != NPU_CONTROL_V2_REPLY ||
        read_word(reply, 3) != NPU_CONTROL_V2_VERSION ||
        read_word(reply, 4) != NPU_CONTROL_V2_SIZE || read_word(reply, 19))
        return fail(s, NPU_CLIENT_V2_ENVELOPE);
    if (read_word(reply, 16) != ticket)
        return fail(s, NPU_CLIENT_V2_SEQUENCE);
    boot_lo = read_word(reply, 17);
    boot_hi = read_word(reply, 18);
    if (!(boot_lo || boot_hi) ||
        (s->base.operation != NPU_CONTROL_DISCOVER &&
         (boot_lo != s->boot_lo || boot_hi != s->boot_hi)))
        return fail(s, NPU_CLIENT_V2_BOOT);
    if (read_word(reply, 10) != NPU_CONTROL_V2_CAPS)
        return fail(s, NPU_CLIENT_V2_CAPABILITY);

    for (i = 0; i < NPU_CONTROL_SIZE / 4; i++)
        write_word(normalized, i, read_word(reply, i));
    write_word(normalized, 2, NPU_CONTROL_REPLY);
    write_word(normalized, 3, NPU_CONTROL_VERSION);
    write_word(normalized, 4, NPU_CONTROL_SIZE);
    write_word(normalized, 10, NPU_CONTROL_CAPS);
    result = npu_client_complete(&s->base, ticket, 0, normalized, sizeof(normalized));
    if (result == NPU_CLIENT_ACCEPTED) {
        s->boot_lo = boot_lo;
        s->boot_hi = boot_hi;
    }
    return result;
}
