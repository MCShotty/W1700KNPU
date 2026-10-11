#include "cold-setup.h"

static uint32_t read_word(const unsigned char *p, uint32_t i)
{
    p += i * 4;
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
           (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static void write_word(unsigned char *p, uint32_t i, uint32_t value)
{
    p += i * 4;
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
        npu_client_v2_abort(s);
    }
    return NPU_CLIENT_REJECTED;
}

uint32_t npu_cold_client_request(struct npu_control_v2_client *s,
    void *packet, uint32_t bytes, const struct npu_bootstrap_packet *p)
{
    uint32_t i;

    if (s->base.phase == NPU_CLIENT_FAILED || s->base.pending)
        return 0;
    if (!packet || bytes != NPU_COLD_SIZE || !p ||
        s->base.phase != NPU_CLIENT_PARKED || s->base.epoch != 1 ||
        s->base.released || s->base.armed || s->base.ready_mask || s->base.drain_mask ||
        s->base.parked_mask != 0xff || !(s->boot_lo || s->boot_hi) ||
        !(s->base.nonce_lo || s->base.nonce_hi) || s->base.serial == UINT32_MAX) {
        fail(s, NPU_CLIENT_V2_ARGUMENT);
        return 0;
    }
    for (i = 0; i < NPU_COLD_SIZE / 4; i++)
        write_word(packet, i, 0);
    write_word(packet, 0, NPU_CONTROL_HEADER);
    write_word(packet, 1, NPU_COLD_API);
    write_word(packet, 2, NPU_COLD_REQUEST);
    write_word(packet, 3, NPU_COLD_VERSION);
    write_word(packet, 4, NPU_COLD_SIZE);
    write_word(packet, 5, 1);
    write_word(packet, 6, s->base.serial + 1);
    write_word(packet, 7, s->base.nonce_lo);
    write_word(packet, 8, s->base.nonce_hi);
    write_word(packet, 9, s->boot_lo);
    write_word(packet, 10, s->boot_hi);
    write_word(packet, 11, p->header);
    write_word(packet, 12, p->api);
    write_word(packet, 13, p->value);
    s->base.operation = NPU_COLD_PENDING_OPERATION;
    s->base.pending = ++s->base.serial;
    return s->base.pending;
}

enum npu_client_result npu_cold_client_complete(struct npu_control_v2_client *s,
    uint32_t ticket, int error, const void *packet, uint32_t bytes,
    const struct npu_bootstrap_packet *command, uint32_t *value)
{
    uint32_t i, result, descriptor;

    if (!ticket || ticket != s->base.pending || s->base.phase == NPU_CLIENT_FAILED)
        return NPU_CLIENT_IGNORED;
    if (error)
        return fail(s, NPU_CLIENT_V2_ENVELOPE);
    if (!packet || bytes != NPU_COLD_SIZE || !command || !value ||
        s->base.phase != NPU_CLIENT_PARKED || s->base.operation != NPU_COLD_PENDING_OPERATION)
        return fail(s, NPU_CLIENT_V2_ARGUMENT);
    if (read_word(packet, 0) != NPU_CONTROL_HEADER || read_word(packet, 1) != NPU_COLD_API ||
        read_word(packet, 2) != NPU_COLD_REPLY || read_word(packet, 3) != NPU_COLD_VERSION ||
        read_word(packet, 4) != NPU_COLD_SIZE || read_word(packet, 5) != 1 ||
        read_word(packet, 6) != ticket || read_word(packet, 7) != s->base.nonce_lo ||
        read_word(packet, 8) != s->base.nonce_hi || read_word(packet, 9) != s->boot_lo ||
        read_word(packet, 10) != s->boot_hi || read_word(packet, 11) != command->header ||
        read_word(packet, 12) != command->api || read_word(packet, 14) != NPU_COLD_OK)
        return fail(s, NPU_CLIENT_V2_ENVELOPE);
    for (i = 15; i < 20; i++)
        if (read_word(packet, i))
            return fail(s, NPU_CLIENT_V2_ENVELOPE);
    result = read_word(packet, 13);
    descriptor = npu_cold_descriptor_command_step(command);
    if (descriptor < NPU_COLD_DESCRIPTOR_STEPS ?
        !npu_cold_descriptor_reply_arena(descriptor, result, 0) :
        result != (command->header == 0x30 && command->api == 10 ? 0x457u : command->value))
        return fail(s, NPU_CLIENT_V2_ENVELOPE);
    s->base.pending = 0;
    *value = result;
    return NPU_CLIENT_ACCEPTED;
}
