#include "rro-wire.h"

typedef __UINTPTR_TYPE__ wire_address_t;

#define BODY_WORD(index) (8u + (index))

static int range_ok(const void *pointer, wire_address_t bytes)
{
    wire_address_t address = (wire_address_t)pointer;

    return address && bytes <= ~(wire_address_t)0 - address;
}

static int separate(const void *a, wire_address_t an, const void *b, wire_address_t bn)
{
    wire_address_t x = (wire_address_t)a, y = (wire_address_t)b;

    return range_ok(a, an) && range_ok(b, bn) &&
           (x + an <= y || y + bn <= x);
}

static int message_ok(const struct npu_rro_wire_message *message)
{
    return range_ok(message, sizeof(*message)) &&
           !((wire_address_t)message % _Alignof(struct npu_rro_wire_message));
}

static void clear_bytes(void *pointer, wire_address_t bytes)
{
    volatile unsigned char *to = pointer;

    for (wire_address_t i = 0; i < bytes; i++)
        to[i] = 0;
}

static void copy_bytes(void *destination, const void *source, wire_address_t bytes)
{
    volatile unsigned char *to = destination;
    const volatile unsigned char *from = source;

    for (wire_address_t i = 0; i < bytes; i++)
        to[i] = from[i];
}

static uint32_t read_word(const unsigned char *bytes, uint32_t word)
{
    const unsigned char *at = bytes + word * 4u;

    return (uint32_t)at[0] | (uint32_t)at[1] << 8 |
           (uint32_t)at[2] << 16 | (uint32_t)at[3] << 24;
}

static void write_word(unsigned char *bytes, uint32_t word, uint32_t value)
{
    unsigned char *at = bytes + word * 4u;

    at[0] = (unsigned char)value;
    at[1] = (unsigned char)(value >> 8);
    at[2] = (unsigned char)(value >> 16);
    at[3] = (unsigned char)(value >> 24);
}

static void write_identity(unsigned char *bytes, const struct npu_rro_plan *plan)
{
    const struct npu_rro_identity *id = &plan->identity;

    write_word(bytes, BODY_WORD(0), id->provider_lo);
    write_word(bytes, BODY_WORD(1), id->provider_hi);
    write_word(bytes, BODY_WORD(2), id->endpoint_lo);
    write_word(bytes, BODY_WORD(3), id->endpoint_hi);
    write_word(bytes, BODY_WORD(4), id->boot_lo);
    write_word(bytes, BODY_WORD(5), id->boot_hi);
    write_word(bytes, BODY_WORD(6), id->nonce_lo);
    write_word(bytes, BODY_WORD(7), id->nonce_hi);
    write_word(bytes, BODY_WORD(8), id->epoch);
    write_word(bytes, BODY_WORD(9), plan->profile);
}

static void read_identity(struct npu_rro_plan *plan, const unsigned char *bytes)
{
    struct npu_rro_identity *id = &plan->identity;

    id->provider_lo = read_word(bytes, BODY_WORD(0));
    id->provider_hi = read_word(bytes, BODY_WORD(1));
    id->endpoint_lo = read_word(bytes, BODY_WORD(2));
    id->endpoint_hi = read_word(bytes, BODY_WORD(3));
    id->boot_lo = read_word(bytes, BODY_WORD(4));
    id->boot_hi = read_word(bytes, BODY_WORD(5));
    id->nonce_lo = read_word(bytes, BODY_WORD(6));
    id->nonce_hi = read_word(bytes, BODY_WORD(7));
    id->epoch = read_word(bytes, BODY_WORD(8));
    plan->profile = read_word(bytes, BODY_WORD(9));
}

static void write_span(unsigned char *bytes, uint32_t body_word,
                       const struct npu_rro_span *span)
{
    write_word(bytes, BODY_WORD(body_word), span->address);
    write_word(bytes, BODY_WORD(body_word + 1u), span->bytes);
}

static void read_span(struct npu_rro_span *span, const unsigned char *bytes,
                      uint32_t body_word)
{
    span->address = read_word(bytes, BODY_WORD(body_word));
    span->bytes = read_word(bytes, BODY_WORD(body_word + 1u));
}

static void write_plan(unsigned char *bytes, const struct npu_rro_plan *plan)
{
    for (uint32_t i = 0; i < 8u; i++)
        write_span(bytes, 10u + 2u * i, &plan->mailbox[i]);
    for (uint32_t i = 0; i < 6u; i++)
        write_span(bytes, 26u + 2u * i, &plan->tx[i]);
    write_span(bytes, 38u, &plan->rx_event);
    for (uint32_t i = 0; i < 6u; i++)
        write_span(bytes, 40u + 2u * i, &plan->native[i]);
    write_span(bytes, 52u, &plan->bar);
}

static void read_plan(struct npu_rro_plan *plan, const unsigned char *bytes)
{
    for (uint32_t i = 0; i < 8u; i++)
        read_span(&plan->mailbox[i], bytes, 10u + 2u * i);
    for (uint32_t i = 0; i < 6u; i++)
        read_span(&plan->tx[i], bytes, 26u + 2u * i);
    read_span(&plan->rx_event, bytes, 38u);
    for (uint32_t i = 0; i < 6u; i++)
        read_span(&plan->native[i], bytes, 40u + 2u * i);
    read_span(&plan->bar, bytes, 52u);
}

static int identity_valid(const struct npu_rro_plan *plan)
{
    const struct npu_rro_identity *id = &plan->identity;

    return (id->provider_lo | id->provider_hi) &&
           (id->endpoint_lo | id->endpoint_hi) &&
           (id->provider_lo != id->endpoint_lo || id->provider_hi != id->endpoint_hi) &&
           (id->boot_lo | id->boot_hi) && (id->nonce_lo | id->nonce_hi) &&
           id->epoch && plan->profile <= NPU_RRO_V3_1_WED;
}

static uint32_t extent_count(uint32_t profile)
{
    return profile == NPU_RRO_V3_1_WED ? 137u : 139u;
}

static uint32_t body_words(uint32_t operation)
{
    switch (operation) {
    case NPU_RRO_WIRE_OPEN: return 54u;
    case NPU_RRO_WIRE_ENROLL: return 18u;
    case NPU_RRO_WIRE_PUBLISH: return 17u;
    case NPU_RRO_WIRE_HARDWARE: return 10u;
    case NPU_RRO_WIRE_RESET_NPU: return 18u;
    case NPU_RRO_WIRE_MCU_BEGIN: return 13u;
    case NPU_RRO_WIRE_MCU_COMPLETE: return 14u;
    case NPU_RRO_WIRE_CLOSE: return 12u;
    default: return 0;
    }
}

static int shape_valid(const struct npu_rro_wire_message *message, int reply)
{
    if (!message->sequence || (!reply && message->status) ||
        !identity_valid(&message->plan) || !body_words(message->operation))
        return 0;

    switch (message->operation) {
    case NPU_RRO_WIRE_ENROLL:
        return message->ordinal < extent_count(message->plan.profile);
    case NPU_RRO_WIRE_PUBLISH:
        return message->ordinal < NPU_RRO_PUBLICATIONS && message->ticket &&
               message->command.selector == (message->ordinal == NPU_RRO_BLOCKS ? 1u : 0u) &&
               message->command.words[0] ==
                   (message->ordinal == NPU_RRO_BLOCKS ? 0u : message->ordinal) &&
               !message->command.words[2] && !message->command.words[3];
    case NPU_RRO_WIRE_RESET_NPU:
        return message->session < NPU_RRO_SESSIONS && message->generation &&
               message->ticket && message->command.selector == 3u &&
               message->command.words[0] == message->session &&
               !message->command.words[1] && !message->command.words[2] &&
               !message->command.words[3];
    case NPU_RRO_WIRE_MCU_BEGIN:
    case NPU_RRO_WIRE_MCU_COMPLETE:
        return message->session < NPU_RRO_SESSIONS &&
               message->generation && message->ticket;
    case NPU_RRO_WIRE_CLOSE:
        return message->stop_epoch && message->ticket;
    default:
        return 1;
    }
}

static void write_operation(unsigned char *bytes, const struct npu_rro_wire_message *message)
{
    switch (message->operation) {
    case NPU_RRO_WIRE_OPEN:
        write_plan(bytes, &message->plan);
        break;
    case NPU_RRO_WIRE_ENROLL:
        write_word(bytes, BODY_WORD(10), message->ordinal);
        write_word(bytes, BODY_WORD(11), message->extent.role);
        write_word(bytes, BODY_WORD(12), message->extent.index);
        write_word(bytes, BODY_WORD(13), message->extent.bytes);
        write_word(bytes, BODY_WORD(14), message->extent.cpu_lo);
        write_word(bytes, BODY_WORD(15), message->extent.cpu_hi);
        write_word(bytes, BODY_WORD(16), message->extent.dma_lo);
        write_word(bytes, BODY_WORD(17), message->extent.dma_hi);
        break;
    case NPU_RRO_WIRE_PUBLISH:
        write_word(bytes, BODY_WORD(10), message->ordinal);
        write_word(bytes, BODY_WORD(11), message->ticket);
        write_word(bytes, BODY_WORD(12), message->command.selector);
        for (uint32_t i = 0; i < 4u; i++)
            write_word(bytes, BODY_WORD(13u + i), message->command.words[i]);
        break;
    case NPU_RRO_WIRE_RESET_NPU:
        write_word(bytes, BODY_WORD(10), message->session);
        write_word(bytes, BODY_WORD(11), message->generation);
        write_word(bytes, BODY_WORD(12), message->ticket);
        write_word(bytes, BODY_WORD(13), message->command.selector);
        for (uint32_t i = 0; i < 4u; i++)
            write_word(bytes, BODY_WORD(14u + i), message->command.words[i]);
        break;
    case NPU_RRO_WIRE_MCU_BEGIN:
    case NPU_RRO_WIRE_MCU_COMPLETE:
        write_word(bytes, BODY_WORD(10), message->session);
        write_word(bytes, BODY_WORD(11), message->generation);
        write_word(bytes, BODY_WORD(12), message->ticket);
        if (message->operation == NPU_RRO_WIRE_MCU_COMPLETE)
            write_word(bytes, BODY_WORD(13), message->mcu_error);
        break;
    case NPU_RRO_WIRE_CLOSE:
        write_word(bytes, BODY_WORD(10), message->stop_epoch);
        write_word(bytes, BODY_WORD(11), message->ticket);
        break;
    default:
        break;
    }
}

static void read_operation(struct npu_rro_wire_message *message, const unsigned char *bytes)
{
    switch (message->operation) {
    case NPU_RRO_WIRE_OPEN:
        read_plan(&message->plan, bytes);
        break;
    case NPU_RRO_WIRE_ENROLL:
        message->ordinal = read_word(bytes, BODY_WORD(10));
        message->extent.role = read_word(bytes, BODY_WORD(11));
        message->extent.index = read_word(bytes, BODY_WORD(12));
        message->extent.bytes = read_word(bytes, BODY_WORD(13));
        message->extent.cpu_lo = read_word(bytes, BODY_WORD(14));
        message->extent.cpu_hi = read_word(bytes, BODY_WORD(15));
        message->extent.dma_lo = read_word(bytes, BODY_WORD(16));
        message->extent.dma_hi = read_word(bytes, BODY_WORD(17));
        break;
    case NPU_RRO_WIRE_PUBLISH:
        message->ordinal = read_word(bytes, BODY_WORD(10));
        message->ticket = read_word(bytes, BODY_WORD(11));
        message->command.selector = read_word(bytes, BODY_WORD(12));
        for (uint32_t i = 0; i < 4u; i++)
            message->command.words[i] = read_word(bytes, BODY_WORD(13u + i));
        break;
    case NPU_RRO_WIRE_RESET_NPU:
        message->session = read_word(bytes, BODY_WORD(10));
        message->generation = read_word(bytes, BODY_WORD(11));
        message->ticket = read_word(bytes, BODY_WORD(12));
        message->command.selector = read_word(bytes, BODY_WORD(13));
        for (uint32_t i = 0; i < 4u; i++)
            message->command.words[i] = read_word(bytes, BODY_WORD(14u + i));
        break;
    case NPU_RRO_WIRE_MCU_BEGIN:
    case NPU_RRO_WIRE_MCU_COMPLETE:
        message->session = read_word(bytes, BODY_WORD(10));
        message->generation = read_word(bytes, BODY_WORD(11));
        message->ticket = read_word(bytes, BODY_WORD(12));
        if (message->operation == NPU_RRO_WIRE_MCU_COMPLETE)
            message->mcu_error = read_word(bytes, BODY_WORD(13));
        break;
    case NPU_RRO_WIRE_CLOSE:
        message->stop_epoch = read_word(bytes, BODY_WORD(10));
        message->ticket = read_word(bytes, BODY_WORD(11));
        break;
    default:
        break;
    }
}

static uint32_t parse_packet(struct npu_rro_wire_message *result,
                             const unsigned char *bytes, int reply)
{
    struct npu_rro_wire_message message;
    uint32_t used;

    if (read_word(bytes, 0) != NPU_CONTROL_HEADER ||
        read_word(bytes, 1) != NPU_RRO_WIRE_API ||
        read_word(bytes, 2) != (reply ? NPU_RRO_WIRE_REPLY : NPU_RRO_WIRE_REQUEST) ||
        read_word(bytes, 3) != NPU_RRO_WIRE_VERSION ||
        read_word(bytes, 4) != NPU_RRO_WIRE_SIZE)
        return NPU_RRO_WIRE_BAD_MESSAGE;

    clear_bytes(&message, sizeof(message));
    message.sequence = read_word(bytes, 5);
    message.operation = read_word(bytes, 6);
    message.status = read_word(bytes, 7);
    used = body_words(message.operation);
    if (!used)
        return NPU_RRO_WIRE_BAD_MESSAGE;
    read_identity(&message.plan, bytes);
    read_operation(&message, bytes);
    if (!shape_valid(&message, reply))
        return NPU_RRO_WIRE_BAD_MESSAGE;
    for (uint32_t word = used; word < NPU_RRO_WIRE_SIZE / 4u - 8u; word++)
        if (read_word(bytes, BODY_WORD(word)))
            return NPU_RRO_WIRE_BAD_MESSAGE;
    if (result)
        copy_bytes(result, &message, sizeof(message));
    return NPU_RRO_WIRE_OK;
}

uint32_t npu_rro_wire_encode(void *output, uint32_t bytes,
                             const struct npu_rro_wire_message *message)
{
    unsigned char packet[NPU_RRO_WIRE_SIZE];

    if (bytes != NPU_RRO_WIRE_SIZE || !message_ok(message) ||
        !separate(output, bytes, message, sizeof(*message)) ||
        !shape_valid(message, 0))
        return NPU_RRO_WIRE_BAD_MESSAGE;

    clear_bytes(packet, sizeof(packet));
    write_word(packet, 0, NPU_CONTROL_HEADER);
    write_word(packet, 1, NPU_RRO_WIRE_API);
    write_word(packet, 2, NPU_RRO_WIRE_REQUEST);
    write_word(packet, 3, NPU_RRO_WIRE_VERSION);
    write_word(packet, 4, NPU_RRO_WIRE_SIZE);
    write_word(packet, 5, message->sequence);
    write_word(packet, 6, message->operation);
    write_identity(packet, &message->plan);
    write_operation(packet, message);
    copy_bytes(output, packet, sizeof(packet));
    return NPU_RRO_WIRE_OK;
}

uint32_t npu_rro_wire_decode(struct npu_rro_wire_message *output, const void *input,
                             uint32_t bytes, uint32_t reply)
{
    if (bytes != NPU_RRO_WIRE_SIZE || reply > 1u || !message_ok(output) ||
        !separate(output, sizeof(*output), input, bytes))
        return NPU_RRO_WIRE_BAD_MESSAGE;
    return parse_packet(output, input, reply != 0);
}

uint32_t npu_rro_wire_reply(void *packet, uint32_t bytes, uint32_t status)
{
    unsigned char *wire = packet;

    if (bytes != NPU_RRO_WIRE_SIZE || !range_ok(packet, bytes) ||
        parse_packet(0, wire, 0))
        return NPU_RRO_WIRE_BAD_MESSAGE;
    write_word(wire, 2, NPU_RRO_WIRE_REPLY);
    write_word(wire, 7, status);
    return NPU_RRO_WIRE_OK;
}

int npu_rro_wire_echo(const void *request, const void *reply, uint32_t bytes)
{
    const unsigned char *left = request, *right = reply;

    if (bytes != NPU_RRO_WIRE_SIZE || !range_ok(request, bytes) ||
        !range_ok(reply, bytes) || parse_packet(0, left, 0) ||
        parse_packet(0, right, 1))
        return 0;
    for (uint32_t i = 0; i < bytes; i++) {
        if ((i >= 8u && i < 12u) || (i >= 28u && i < 32u))
            continue;
        if (left[i] != right[i])
            return 0;
    }
    return 1;
}
