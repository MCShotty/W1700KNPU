#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "rro-wire.h"

_Static_assert(sizeof(struct npu_rro_identity) == 36, "identity test layout");
_Static_assert(sizeof(struct npu_rro_plan) == 216, "plan test layout");
_Static_assert(sizeof(struct npu_rro_extent) == 28, "extent test layout");
_Static_assert(sizeof(struct npu_rro_wire_message) == 300, "message test layout");

static unsigned cases, roundtrips, echo_corruptions, reserved_rejections, rejected_inputs;

#define REQUIRE(condition, label) do { \
    if (!(condition)) { \
        fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, label); \
        abort(); \
    } \
    cases++; \
} while (0)

static void put(unsigned char *packet, unsigned word, uint32_t value)
{
    unsigned offset = 4u * word;

    packet[offset] = (unsigned char)value;
    packet[offset + 1u] = (unsigned char)(value >> 8);
    packet[offset + 2u] = (unsigned char)(value >> 16);
    packet[offset + 3u] = (unsigned char)(value >> 24);
}

static unsigned used_words(uint32_t operation)
{
    switch (operation) {
    case NPU_RRO_WIRE_OPEN: return 54;
    case NPU_RRO_WIRE_ENROLL: return 18;
    case NPU_RRO_WIRE_PUBLISH: return 17;
    case NPU_RRO_WIRE_HARDWARE: return 10;
    case NPU_RRO_WIRE_RESET_NPU: return 18;
    case NPU_RRO_WIRE_MCU_BEGIN: return 13;
    case NPU_RRO_WIRE_MCU_COMPLETE: return 14;
    case NPU_RRO_WIRE_CLOSE: return 12;
    default: abort();
    }
}

static unsigned extent_count(uint32_t profile)
{
    return profile == NPU_RRO_V3_1_WED ? 137u : 139u;
}

static struct npu_rro_wire_message fixture(uint32_t profile, uint32_t operation)
{
    struct npu_rro_wire_message message;

    memset(&message, 0xa5, sizeof(message));
    message.operation = operation;
    message.sequence = 0xfedcba98u;
    message.status = 0;
    message.plan.identity.provider_lo = 0x11223344u;
    message.plan.identity.provider_hi = 0xdeadbeefu;
    message.plan.identity.endpoint_lo = 0x55667788u;
    message.plan.identity.endpoint_hi = 0x9abcdef0u;
    message.plan.identity.boot_lo = 0x13579bdfu;
    message.plan.identity.boot_hi = 0xfedcba98u;
    message.plan.identity.nonce_lo = 0x2468ace0u;
    message.plan.identity.nonce_hi = 0x8badf00du;
    message.plan.identity.epoch = 0xc001d00du;
    message.plan.profile = profile;
    for (unsigned i = 0; i < 8; i++) {
        message.plan.mailbox[i].address = 0x81000000u + i * 0x10000u;
        message.plan.mailbox[i].bytes = 0x1000u + i;
    }
    for (unsigned i = 0; i < 6; i++) {
        message.plan.tx[i].address = 0x92000000u + i * 0x20000u;
        message.plan.tx[i].bytes = 0x20000u + i;
        message.plan.native[i].address = 0xa3000000u + i * 0x30000u;
        message.plan.native[i].bytes = 0x3000u + i;
    }
    message.plan.rx_event.address = 0xb456789au;
    message.plan.rx_event.bytes = 0x1234u;
    message.plan.bar.address = 0xc1234567u;
    message.plan.bar.bytes = 0x5678u;
    message.ordinal = operation == NPU_RRO_WIRE_ENROLL ? extent_count(profile) - 1u : 128u;
    message.session = 1024u;
    message.generation = 0xe1234567u;
    message.ticket = 0xd2345678u;
    message.stop_epoch = 0xc001d00eu;
    message.mcu_error = 0x87654321u;
    message.extent.role = NPU_RRO_SESSION;
    message.extent.index = 0x12345678u;
    message.extent.bytes = 0x11112222u;
    message.extent.cpu_lo = 0x33334444u;
    message.extent.cpu_hi = 0xdeadbeefu;
    message.extent.dma_lo = 0x55556666u;
    message.extent.dma_hi = 0xfacecafeu;
    message.command.selector = operation == NPU_RRO_WIRE_RESET_NPU ? 3u : 1u;
    message.command.words[0] = operation == NPU_RRO_WIRE_RESET_NPU ? message.session : 0u;
    message.command.words[1] = operation == NPU_RRO_WIRE_PUBLISH ? 0xe2468aceu : 0u;
    message.command.words[2] = 0;
    message.command.words[3] = 0;
    return message;
}

static void oracle_span(unsigned char *wire, unsigned body_word,
                        const struct npu_rro_span *span)
{
    put(wire, 8u + body_word, span->address);
    put(wire, 9u + body_word, span->bytes);
}

static void oracle(unsigned char *wire, const struct npu_rro_wire_message *message)
{
    const struct npu_rro_identity *id = &message->plan.identity;

    memset(wire, 0, NPU_RRO_WIRE_SIZE);
    put(wire, 0, NPU_CONTROL_HEADER);
    put(wire, 1, NPU_RRO_WIRE_API);
    put(wire, 2, NPU_RRO_WIRE_REQUEST);
    put(wire, 3, NPU_RRO_WIRE_VERSION);
    put(wire, 4, NPU_RRO_WIRE_SIZE);
    put(wire, 5, message->sequence);
    put(wire, 6, message->operation);
    put(wire, 8, id->provider_lo);
    put(wire, 9, id->provider_hi);
    put(wire, 10, id->endpoint_lo);
    put(wire, 11, id->endpoint_hi);
    put(wire, 12, id->boot_lo);
    put(wire, 13, id->boot_hi);
    put(wire, 14, id->nonce_lo);
    put(wire, 15, id->nonce_hi);
    put(wire, 16, id->epoch);
    put(wire, 17, message->plan.profile);

    switch (message->operation) {
    case NPU_RRO_WIRE_OPEN:
        for (unsigned i = 0; i < 8; i++)
            oracle_span(wire, 10u + 2u * i, &message->plan.mailbox[i]);
        for (unsigned i = 0; i < 6; i++)
            oracle_span(wire, 26u + 2u * i, &message->plan.tx[i]);
        oracle_span(wire, 38u, &message->plan.rx_event);
        for (unsigned i = 0; i < 6; i++)
            oracle_span(wire, 40u + 2u * i, &message->plan.native[i]);
        oracle_span(wire, 52u, &message->plan.bar);
        break;
    case NPU_RRO_WIRE_ENROLL:
        put(wire, 18, message->ordinal);
        put(wire, 19, message->extent.role);
        put(wire, 20, message->extent.index);
        put(wire, 21, message->extent.bytes);
        put(wire, 22, message->extent.cpu_lo);
        put(wire, 23, message->extent.cpu_hi);
        put(wire, 24, message->extent.dma_lo);
        put(wire, 25, message->extent.dma_hi);
        break;
    case NPU_RRO_WIRE_PUBLISH:
        put(wire, 18, message->ordinal);
        put(wire, 19, message->ticket);
        put(wire, 20, message->command.selector);
        for (unsigned i = 0; i < 4; i++)
            put(wire, 21u + i, message->command.words[i]);
        break;
    case NPU_RRO_WIRE_RESET_NPU:
        put(wire, 18, message->session);
        put(wire, 19, message->generation);
        put(wire, 20, message->ticket);
        put(wire, 21, message->command.selector);
        for (unsigned i = 0; i < 4; i++)
            put(wire, 22u + i, message->command.words[i]);
        break;
    case NPU_RRO_WIRE_MCU_BEGIN:
    case NPU_RRO_WIRE_MCU_COMPLETE:
        put(wire, 18, message->session);
        put(wire, 19, message->generation);
        put(wire, 20, message->ticket);
        if (message->operation == NPU_RRO_WIRE_MCU_COMPLETE)
            put(wire, 21, message->mcu_error);
        break;
    case NPU_RRO_WIRE_CLOSE:
        put(wire, 18, message->stop_epoch);
        put(wire, 19, message->ticket);
        break;
    default:
        break;
    }
}

static struct npu_rro_wire_message normalized(const struct npu_rro_wire_message *source,
                                                uint32_t status)
{
    struct npu_rro_wire_message expected;

    memset(&expected, 0, sizeof(expected));
    expected.operation = source->operation;
    expected.sequence = source->sequence;
    expected.status = status;
    expected.plan.identity = source->plan.identity;
    expected.plan.profile = source->plan.profile;
    switch (source->operation) {
    case NPU_RRO_WIRE_OPEN:
        expected.plan = source->plan;
        break;
    case NPU_RRO_WIRE_ENROLL:
        expected.ordinal = source->ordinal;
        expected.extent = source->extent;
        break;
    case NPU_RRO_WIRE_PUBLISH:
        expected.ordinal = source->ordinal;
        expected.ticket = source->ticket;
        expected.command = source->command;
        break;
    case NPU_RRO_WIRE_RESET_NPU:
        expected.session = source->session;
        expected.generation = source->generation;
        expected.ticket = source->ticket;
        expected.command = source->command;
        break;
    case NPU_RRO_WIRE_MCU_BEGIN:
    case NPU_RRO_WIRE_MCU_COMPLETE:
        expected.session = source->session;
        expected.generation = source->generation;
        expected.ticket = source->ticket;
        if (source->operation == NPU_RRO_WIRE_MCU_COMPLETE)
            expected.mcu_error = source->mcu_error;
        break;
    case NPU_RRO_WIRE_CLOSE:
        expected.stop_epoch = source->stop_epoch;
        expected.ticket = source->ticket;
        break;
    default:
        break;
    }
    return expected;
}

static void reject_decode(const void *wire, uint32_t bytes, uint32_t reply, const char *label)
{
    struct npu_rro_wire_message output, before;

    memset(&output, 0xa5, sizeof(output));
    before = output;
    REQUIRE(npu_rro_wire_decode(&output, wire, bytes, reply) == NPU_RRO_WIRE_BAD_MESSAGE, label);
    REQUIRE(!memcmp(&output, &before, sizeof(output)), "decode rejection must preserve output");
    rejected_inputs++;
}

static void reject_encode(const struct npu_rro_wire_message *message)
{
    unsigned char wire[NPU_RRO_WIRE_SIZE + 2u];

    memset(wire, 0xa5, sizeof(wire));
    REQUIRE(npu_rro_wire_encode(wire + 1, NPU_RRO_WIRE_SIZE, message) ==
            NPU_RRO_WIRE_BAD_MESSAGE, "invalid encode must reject");
    for (unsigned i = 0; i < sizeof(wire); i++)
        REQUIRE(wire[i] == 0xa5, "invalid encode must preserve output");
    rejected_inputs++;
}

static void roundtrip(const struct npu_rro_wire_message *message)
{
    unsigned char wire[NPU_RRO_WIRE_SIZE + 2u], request[NPU_RRO_WIRE_SIZE];
    unsigned char reply[NPU_RRO_WIRE_SIZE], expected[NPU_RRO_WIRE_SIZE];
    struct npu_rro_wire_message output, normalized_request, normalized_reply;
    const uint32_t remote_error = 0x80001234u;

    memset(wire, 0xa5, sizeof(wire));
    REQUIRE(npu_rro_wire_encode(wire + 1, NPU_RRO_WIRE_SIZE, message) == 0,
            "valid encode must succeed");
    REQUIRE(wire[0] == 0xa5 && wire[sizeof(wire) - 1] == 0xa5,
            "encode must not touch guards");
    oracle(expected, message);
    REQUIRE(!memcmp(wire + 1, expected, sizeof(expected)), "wire oracle must match");
    memcpy(request, wire + 1, sizeof(request));
    memset(&output, 0xa5, sizeof(output));
    REQUIRE(npu_rro_wire_decode(&output, request, sizeof(request), 0) == 0,
            "request decode must succeed");
    normalized_request = normalized(message, 0);
    REQUIRE(!memcmp(&output, &normalized_request, sizeof(output)),
            "request decode must zero every unused field");
    reject_decode(request, sizeof(request), 1, "request tag must not decode as reply");

    memcpy(reply, request, sizeof(reply));
    REQUIRE(npu_rro_wire_reply(reply, sizeof(reply), remote_error) == 0,
            "canonical request must form reply");
    put(expected, 2, NPU_RRO_WIRE_REPLY);
    put(expected, 7, remote_error);
    REQUIRE(!memcmp(reply, expected, sizeof(reply)), "reply may change only tag/status");
    memset(&output, 0xa5, sizeof(output));
    REQUIRE(npu_rro_wire_decode(&output, reply, sizeof(reply), 1) == 0,
            "remote error reply must decode");
    normalized_reply = normalized(message, remote_error);
    REQUIRE(!memcmp(&output, &normalized_reply, sizeof(output)),
            "remote error must survive decoding without implying success");
    REQUIRE(npu_rro_wire_echo(request, reply, sizeof(reply)),
            "remote error still correlates; echo alone is not success");
    reject_decode(reply, sizeof(reply), 0, "reply tag must not decode as request");

    for (unsigned byte = 0; byte < NPU_RRO_WIRE_SIZE; byte++) {
        unsigned char changed[NPU_RRO_WIRE_SIZE];

        memcpy(changed, reply, sizeof(changed));
        changed[byte] ^= 1u;
        if (byte >= 28u && byte < 32u) {
            REQUIRE(npu_rro_wire_echo(request, changed, sizeof(changed)),
                    "only reply status may vary for correlation");
            continue;
        }
        REQUIRE(!npu_rro_wire_echo(request, changed, sizeof(changed)),
                "echo must compare every non-status byte");
        echo_corruptions++;
        if (byte >= (8u + used_words(message->operation)) * 4u) {
            reject_decode(changed, sizeof(changed), 1, "reserved body word must reject");
            reserved_rejections++;
        }
    }
    roundtrips++;
}

static void malformed_packets(void)
{
    struct npu_rro_wire_message message = fixture(NPU_RRO_V3, NPU_RRO_WIRE_OPEN);
    unsigned char valid[NPU_RRO_WIRE_SIZE], changed[NPU_RRO_WIRE_SIZE];
    const unsigned words[] = {0, 1, 2, 3, 4, 5, 6, 7, 17};
    const uint32_t values[] = {0, 0, 0, 0, 0, 0, 9, 1, 3};

    REQUIRE(npu_rro_wire_encode(valid, sizeof(valid), &message) == 0, "setup packet");
    for (unsigned i = 0; i < sizeof(words) / sizeof(words[0]); i++) {
        memcpy(changed, valid, sizeof(changed));
        put(changed, words[i], values[i]);
        reject_decode(changed, sizeof(changed), 0, "wrong header, status or profile must reject");
    }
    memcpy(changed, valid, sizeof(changed));
    put(changed, 8, 0);
    put(changed, 9, 0);
    reject_decode(changed, sizeof(changed), 0, "zero provider identity must reject");
    memcpy(changed, valid, sizeof(changed));
    put(changed, 10, 0x11223344u);
    put(changed, 11, 0xdeadbeefu);
    reject_decode(changed, sizeof(changed), 0, "identical provider/endpoint must reject");
    memcpy(changed, valid, sizeof(changed));
    put(changed, 16, 0);
    reject_decode(changed, sizeof(changed), 0, "zero epoch must reject");
    memcpy(changed, valid, sizeof(changed));
    put(changed, 62, 1);
    reject_decode(changed, sizeof(changed), 0, "OPEN final padding must reject");
    memcpy(changed, valid, sizeof(changed));
    put(changed, 63, 1);
    reject_decode(changed, sizeof(changed), 0, "OPEN final padding must reject");

    for (uint32_t op = NPU_RRO_WIRE_OPEN; op <= NPU_RRO_WIRE_CLOSE; op++) {
        message = fixture(NPU_RRO_V3_1_WED, op);
        REQUIRE(npu_rro_wire_encode(valid, sizeof(valid), &message) == 0,
                "operation packet setup");
        for (unsigned body = used_words(op); body < 56u; body++) {
            memcpy(changed, valid, sizeof(changed));
            put(changed, 8u + body, 0x01020304u);
            reject_decode(changed, sizeof(changed), 0, "reserved body word must reject");
            reserved_rejections++;
        }
    }
}

static void reject_wire_field(uint32_t profile, uint32_t operation,
                              unsigned word, uint32_t value)
{
    struct npu_rro_wire_message message = fixture(profile, operation);
    unsigned char wire[NPU_RRO_WIRE_SIZE];

    REQUIRE(npu_rro_wire_encode(wire, sizeof(wire), &message) == 0,
            "shape mutation setup");
    put(wire, word, value);
    reject_decode(wire, sizeof(wire), 0, "invalid operation shape must reject on decode");
}

static void malformed_shapes(void)
{
    for (uint32_t profile = 0; profile <= NPU_RRO_V3_1_WED; profile++)
        reject_wire_field(profile, NPU_RRO_WIRE_ENROLL, 18, extent_count(profile));
    reject_wire_field(0, NPU_RRO_WIRE_PUBLISH, 18, NPU_RRO_PUBLICATIONS);
    reject_wire_field(0, NPU_RRO_WIRE_PUBLISH, 19, 0);
    reject_wire_field(0, NPU_RRO_WIRE_PUBLISH, 20, 0);
    reject_wire_field(0, NPU_RRO_WIRE_PUBLISH, 21, 1);
    reject_wire_field(0, NPU_RRO_WIRE_PUBLISH, 23, 1);
    reject_wire_field(0, NPU_RRO_WIRE_PUBLISH, 24, 1);
    reject_wire_field(0, NPU_RRO_WIRE_RESET_NPU, 18, NPU_RRO_SESSIONS);
    reject_wire_field(0, NPU_RRO_WIRE_RESET_NPU, 19, 0);
    reject_wire_field(0, NPU_RRO_WIRE_RESET_NPU, 20, 0);
    reject_wire_field(0, NPU_RRO_WIRE_RESET_NPU, 21, 1);
    reject_wire_field(0, NPU_RRO_WIRE_RESET_NPU, 22, 0);
    reject_wire_field(0, NPU_RRO_WIRE_RESET_NPU, 23, 1);
    reject_wire_field(0, NPU_RRO_WIRE_RESET_NPU, 24, 1);
    reject_wire_field(0, NPU_RRO_WIRE_RESET_NPU, 25, 1);
    for (uint32_t operation = NPU_RRO_WIRE_MCU_BEGIN;
         operation <= NPU_RRO_WIRE_MCU_COMPLETE; operation++) {
        reject_wire_field(0, operation, 18, NPU_RRO_SESSIONS);
        reject_wire_field(0, operation, 19, 0);
        reject_wire_field(0, operation, 20, 0);
    }
    reject_wire_field(0, NPU_RRO_WIRE_CLOSE, 18, 0);
    reject_wire_field(0, NPU_RRO_WIRE_CLOSE, 19, 0);
}

static void invalid_shapes(void)
{
    struct npu_rro_wire_message m;

    m = fixture(0, NPU_RRO_WIRE_OPEN); m.sequence = 0; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_OPEN); m.status = 1; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_OPEN); m.operation = 0; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_OPEN); m.operation = 9; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_OPEN); m.plan.profile = 3; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_OPEN); m.plan.identity.provider_lo = m.plan.identity.provider_hi = 0; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_OPEN); m.plan.identity.endpoint_lo = m.plan.identity.endpoint_hi = 0; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_OPEN); m.plan.identity.endpoint_lo = m.plan.identity.provider_lo;
    m.plan.identity.endpoint_hi = m.plan.identity.provider_hi; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_OPEN); m.plan.identity.boot_lo = m.plan.identity.boot_hi = 0; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_OPEN); m.plan.identity.nonce_lo = m.plan.identity.nonce_hi = 0; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_OPEN); m.plan.identity.epoch = 0; reject_encode(&m);
    for (uint32_t profile = 0; profile <= NPU_RRO_V3_1_WED; profile++) {
        m = fixture(profile, NPU_RRO_WIRE_ENROLL); m.ordinal = extent_count(profile); reject_encode(&m);
    }
    m = fixture(0, NPU_RRO_WIRE_PUBLISH); m.ordinal = NPU_RRO_PUBLICATIONS; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_PUBLISH); m.ticket = 0; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_PUBLISH); m.command.selector = 0; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_PUBLISH); m.command.words[0] = 1; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_PUBLISH); m.command.words[2] = 1; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_PUBLISH); m.command.words[3] = 1; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_PUBLISH); m.ordinal = 127; m.command.selector = 0;
    m.command.words[0] = 0; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_RESET_NPU); m.session = NPU_RRO_SESSIONS; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_RESET_NPU); m.generation = 0; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_RESET_NPU); m.ticket = 0; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_RESET_NPU); m.command.selector = 1; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_RESET_NPU); m.command.words[0] = 0; reject_encode(&m);
    for (unsigned i = 1; i < 4; i++) {
        m = fixture(0, NPU_RRO_WIRE_RESET_NPU); m.command.words[i] = 1; reject_encode(&m);
    }
    for (uint32_t op = NPU_RRO_WIRE_MCU_BEGIN; op <= NPU_RRO_WIRE_MCU_COMPLETE; op++) {
        m = fixture(0, op); m.session = NPU_RRO_SESSIONS; reject_encode(&m);
        m = fixture(0, op); m.generation = 0; reject_encode(&m);
        m = fixture(0, op); m.ticket = 0; reject_encode(&m);
    }
    m = fixture(0, NPU_RRO_WIRE_CLOSE); m.stop_epoch = 0; reject_encode(&m);
    m = fixture(0, NPU_RRO_WIRE_CLOSE); m.ticket = 0; reject_encode(&m);
}

static void bounds_and_overlap(void)
{
    struct npu_rro_wire_message message = fixture(0, NPU_RRO_WIRE_OPEN), output, before;
    unsigned char wire[NPU_RRO_WIRE_SIZE], saved[NPU_RRO_WIRE_SIZE];
    union {
        struct npu_rro_wire_message message;
        unsigned char raw[sizeof(struct npu_rro_wire_message) + NPU_RRO_WIRE_SIZE];
    } shared;
    unsigned char shared_before[sizeof(shared)];
    void *wrapped = (void *)(uintptr_t)(UINTPTR_MAX - 100u);

    REQUIRE(npu_rro_wire_encode(wire, sizeof(wire), &message) == 0, "bounds setup");
    memset(&output, 0xa5, sizeof(output));
    before = output;
    reject_decode(NULL, sizeof(wire), 0, "null input must reject");
    reject_decode(wrapped, sizeof(wire), 0, "wrapped input must reject");
    reject_decode(wire, sizeof(wire) - 1u, 0, "short input must reject");
    reject_decode(wire, sizeof(wire) + 1u, 0, "oversized input must reject");
    reject_decode(wire, UINT32_MAX, 0, "unbounded input size must reject");
    reject_decode(wire, sizeof(wire), 2, "invalid reply flag must reject");
    REQUIRE(npu_rro_wire_decode(NULL, wire, sizeof(wire), 0) == NPU_RRO_WIRE_BAD_MESSAGE,
            "null output must reject");
    REQUIRE(npu_rro_wire_decode(&output, wire, sizeof(wire), 0) == 0, "bounds decode setup");
    memset(&output, 0xa5, sizeof(output));
    REQUIRE(npu_rro_wire_decode((void *)wrapped, wire, sizeof(wire), 0) ==
            NPU_RRO_WIRE_BAD_MESSAGE, "wrapped output must reject");
    REQUIRE(!memcmp(&output, &before, sizeof(output)), "unrelated output untouched");

    memset(wire, 0xa5, sizeof(wire));
    memcpy(saved, wire, sizeof(wire));
    REQUIRE(npu_rro_wire_encode(NULL, sizeof(wire), &message) == NPU_RRO_WIRE_BAD_MESSAGE,
            "null encode output must reject");
    REQUIRE(npu_rro_wire_encode(wrapped, sizeof(wire), &message) == NPU_RRO_WIRE_BAD_MESSAGE,
            "wrapped encode output must reject");
    REQUIRE(npu_rro_wire_encode(wire, sizeof(wire), NULL) == NPU_RRO_WIRE_BAD_MESSAGE,
            "null encode input must reject");
    REQUIRE(npu_rro_wire_encode(wire, sizeof(wire), (void *)wrapped) == NPU_RRO_WIRE_BAD_MESSAGE,
            "wrapped encode input must reject");
    REQUIRE(npu_rro_wire_encode(wire, sizeof(wire) - 1u, &message) == NPU_RRO_WIRE_BAD_MESSAGE,
            "short encode output must reject");
    REQUIRE(npu_rro_wire_encode(wire, sizeof(wire) + 1u, &message) == NPU_RRO_WIRE_BAD_MESSAGE,
            "oversized encode output must reject");
    REQUIRE(!memcmp(wire, saved, sizeof(wire)), "bad encode calls must preserve output");

    memset(&shared, 0xa5, sizeof(shared));
    shared.message = message;
    memcpy(shared_before, &shared, sizeof(shared));
    REQUIRE(npu_rro_wire_encode(shared.raw + 4, NPU_RRO_WIRE_SIZE, &shared.message) ==
            NPU_RRO_WIRE_BAD_MESSAGE, "partial encode overlap must reject");
    REQUIRE(!memcmp(&shared, shared_before, sizeof(shared)), "encode overlap must not write");
    REQUIRE(npu_rro_wire_encode(saved, sizeof(saved), &message) == 0, "overlap setup");
    memset(&shared, 0xa5, sizeof(shared));
    memcpy(shared.raw, saved, sizeof(saved));
    memcpy(shared_before, &shared, sizeof(shared));
    REQUIRE(npu_rro_wire_decode(&shared.message, shared.raw, NPU_RRO_WIRE_SIZE, 0) ==
            NPU_RRO_WIRE_BAD_MESSAGE, "decode overlap must reject");
    REQUIRE(!memcmp(&shared, shared_before, sizeof(shared)), "decode overlap must not write");

    REQUIRE(npu_rro_wire_reply(NULL, sizeof(saved), 0) == NPU_RRO_WIRE_BAD_MESSAGE,
            "null reply must reject");
    REQUIRE(npu_rro_wire_reply(wrapped, sizeof(saved), 0) == NPU_RRO_WIRE_BAD_MESSAGE,
            "wrapped reply must reject");
    REQUIRE(npu_rro_wire_reply(saved, sizeof(saved) - 1u, 0) == NPU_RRO_WIRE_BAD_MESSAGE,
            "short reply must reject");
    REQUIRE(npu_rro_wire_reply(saved, sizeof(saved) + 1u, 0) == NPU_RRO_WIRE_BAD_MESSAGE,
            "oversized reply must reject");
    memcpy(wire, saved, sizeof(wire));
    put(wire, 63, 1);
    memcpy(saved, wire, sizeof(wire));
    REQUIRE(npu_rro_wire_reply(wire, sizeof(wire), 0) == NPU_RRO_WIRE_BAD_MESSAGE,
            "reply must reject noncanonical request");
    REQUIRE(!memcmp(wire, saved, sizeof(wire)), "bad reply must preserve packet");
    REQUIRE(!npu_rro_wire_echo(NULL, saved, sizeof(saved)), "null echo request must reject");
    REQUIRE(!npu_rro_wire_echo(saved, NULL, sizeof(saved)), "null echo reply must reject");
    REQUIRE(!npu_rro_wire_echo(wrapped, saved, sizeof(saved)), "wrapped echo request must reject");
    REQUIRE(!npu_rro_wire_echo(saved, wrapped, sizeof(saved)), "wrapped echo reply must reject");
    REQUIRE(!npu_rro_wire_echo(saved, saved, sizeof(saved) - 1u), "short echo must reject");
    REQUIRE(!npu_rro_wire_echo(saved, saved, sizeof(saved) + 1u), "oversized echo must reject");
}

int main(void)
{
    for (uint32_t profile = NPU_RRO_V3; profile <= NPU_RRO_V3_1_WED; profile++) {
        for (uint32_t operation = NPU_RRO_WIRE_OPEN; operation <= NPU_RRO_WIRE_CLOSE; operation++) {
            struct npu_rro_wire_message message = fixture(profile, operation);
            roundtrip(&message);
        }
        struct npu_rro_wire_message block = fixture(profile, NPU_RRO_WIRE_PUBLISH);
        block.ordinal = 127;
        block.command.selector = 0;
        block.command.words[0] = 127;
        roundtrip(&block);
        struct npu_rro_wire_message first = fixture(profile, NPU_RRO_WIRE_ENROLL);
        first.ordinal = 0;
        roundtrip(&first);
    }
    malformed_packets();
    malformed_shapes();
    invalid_shapes();
    bounds_and_overlap();
    printf("{\"passed\":true,\"cases\":%u,\"roundtrips\":%u,"
           "\"echo_corruptions\":%u,\"reserved_rejections\":%u,"
           "\"rejected_inputs\":%u,\"profiles\":3,\"operations\":8}\n",
           cases, roundtrips, echo_corruptions, reserved_rejections, rejected_inputs);
    return 0;
}
