/* Host-only RRO session integration. No physical DMA, IRQ, MCU, or references. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "bootstrap-v2.h"
#include "rro-session.h"
#include "rro-native-fixture.h"

_Static_assert(NPU_RRO_BLOCKS == 128 && NPU_RRO_SESSIONS == 1025,
               "full RRO geometry required");
_Static_assert(NPU_RRO_PUBLICATIONS == 129 && NPU_RRO_MAX_EXTENTS == 139,
               "full RRO publication geometry required");
_Static_assert(NPU_RRO_WIRE_SIZE == 256 && NPU_BOOTSTRAP_STEPS == 6,
               "full request and boot geometry required");
_Static_assert(NPU_COLD_TXBUF_RECORDS == 14 && NPU_BARRIER_WORKERS == 8,
               "complete cold inventory and held barrier required");

static unsigned checks, handshakes, positive_rpc, direct_negative;
static unsigned enrollments, publications, hardware_begins, reset_npu;
static unsigned mcu_begins, mcu_completions, close_calls, journal_compares;
static unsigned memory_checks, full_memory_checks, io_faults, negative_cases;

static void check_at(int condition, const char *label, unsigned line)
{
    checks++;
    if (!condition) {
        fprintf(stderr, "rro-session:%u: %s\n", line, label);
        abort();
    }
}
#define CHECK(condition, label) check_at(!!(condition), (label), __LINE__)

enum bus_kind { BUS_NONE, BUS_PUBLISH, BUS_RESET };

struct mapped_bus {
    uint32_t kind, ordinal, session, slot, reads, writes;
    uint32_t fail_read, fail_write;
    int after_write, wrong_read;
};

struct modeled_boundary {
    uint32_t transport_address, transport_bytes, transport_flags;
    uint32_t provider_ref, endpoint_ref, retained_backing, cpu_excluded;
    uint32_t mcu_result_model;
};

struct rig {
    struct npu_rro_session broker;
    struct npu_rro_lifetime host;
    struct npu_rro_plan plan;
    struct npu_control_v2_client client;
    struct npu_control_v2_session server;
    struct npu_admission admission;
    struct npu_barrier barrier;
    struct npu_bootstrap boot;
    struct npu_cold_setup cold;
    struct mapped_bus bus;
    struct modeled_boundary boundary;
    unsigned char sram[RRO_TEST_SRAM_BYTES];
    unsigned char dma[RRO_TEST_ALIAS_BYTES];
};

static struct rig work, fresh, prepublication, live;
static unsigned char expected_dma[RRO_TEST_ALIAS_BYTES];
static unsigned char expected_sram[RRO_TEST_SRAM_BYTES];

static uint32_t alias(uint32_t physical)
{
    return (physical & 0x3fffffffu) | 0x40000000u;
}

static uint32_t slot_for(const struct rig *r, uint32_t ordinal)
{
    return ordinal == NPU_RRO_BLOCKS ? npu_rro_extent_count(r->plan.profile) - 1u :
           ordinal + (r->plan.profile == NPU_RRO_V3 ? 2u : 0u);
}

static unsigned char *mapping(struct rig *r, uint32_t address, uint32_t bytes)
{
    if (bytes && bytes <= RRO_TEST_SRAM_BYTES && address >= RRO_TEST_SRAM &&
        address - RRO_TEST_SRAM <= RRO_TEST_SRAM_BYTES - bytes)
        return r->sram + (address - RRO_TEST_SRAM);
    if (bytes && bytes <= RRO_TEST_ALIAS_BYTES && address >= RRO_TEST_ALIAS &&
        address - RRO_TEST_ALIAS <= RRO_TEST_ALIAS_BYTES - bytes)
        return r->dma + (address - RRO_TEST_ALIAS);
    CHECK(0, "native I/O must remain inside mapped arrays");
    return NULL;
}

static uint32_t target_address(const struct rig *r)
{
    uint32_t base = alias(r->broker.owner.extents[r->bus.slot].dma_lo);

    return r->bus.kind == BUS_RESET && r->bus.session != NPU_RRO_SESSIONS - 1u ?
           base + (r->bus.session % 8u) * NPU_RRO_SESSION_BYTES : base;
}

static uint32_t target_bytes(const struct rig *r)
{
    return r->bus.kind == BUS_RESET || r->bus.ordinal == NPU_RRO_BLOCKS ?
           NPU_RRO_SESSION_BYTES : NPU_RRO_BLOCK_BYTES;
}

static uint32_t target_table(const struct rig *r)
{
    return r->bus.ordinal == NPU_RRO_BLOCKS ? NPU_RRO_NATIVE_SESSION_TABLE :
           NPU_RRO_NATIVE_BLOCK_TABLE + r->bus.ordinal * 4u;
}

static void access_check(struct rig *r, uint32_t address, uint32_t bytes)
{
    uint32_t base, size;

    CHECK(r->bus.kind != BUS_NONE, "unexpected native I/O");
    CHECK((bytes == 1u || bytes == 4u) && !(address & (bytes - 1u)),
          "native I/O width and alignment");
    if (r->bus.kind == BUS_PUBLISH)
        CHECK(r->broker.owner.publication[r->bus.ordinal].ticket &&
              (r->broker.owner.exposure[r->bus.slot] & NPU_RRO_NPU_POSSIBLE),
              "publication exposure precedes native memory access");
    else
        CHECK(r->broker.owner.resets[r->bus.session].phase == NPU_RRO_RESET_NPU_POSSIBLE,
              "reset exposure precedes native memory access");
    base = target_address(r);
    size = target_bytes(r);
    CHECK((address == target_table(r) && bytes == 4u) ||
          (address >= base && bytes <= size && address - base <= size - bytes),
          "native access must stay within its table or exact retained extent");
}

static int mapped_read(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value)
{
    struct rig *r = opaque;
    uint32_t index;

    access_check(r, address, bytes);
    index = r->bus.reads++;
    if (index == r->bus.fail_read && !r->bus.wrong_read)
        return 0;
    *value = 0;
    memcpy(value, mapping(r, address, bytes), bytes);
    if (index == r->bus.fail_read)
        *value ^= 1u;
    return 1;
}

static int mapped_write(void *opaque, uint32_t address, uint32_t bytes, uint32_t value)
{
    struct rig *r = opaque;
    uint32_t index;

    access_check(r, address, bytes);
    CHECK(r->bus.kind != BUS_RESET || address != target_table(r),
          "reset must not rewrite its table pointer");
    index = r->bus.writes++;
    if (index == r->bus.fail_write && !r->bus.after_write)
        return 0;
    memcpy(mapping(r, address, bytes), &value, bytes);
    return index != r->bus.fail_write;
}

static void bus_arm(struct rig *r, uint32_t ordinal, uint32_t session, int reset)
{
    memset(&r->bus, 0, sizeof(r->bus));
    r->bus.kind = reset ? BUS_RESET : BUS_PUBLISH;
    r->bus.ordinal = ordinal;
    r->bus.session = session;
    r->bus.slot = slot_for(r, ordinal);
    r->bus.fail_read = r->bus.fail_write = UINT32_MAX;
}

static void bus_idle(struct rig *r)
{
    memset(&r->bus, 0, sizeof(r->bus));
    r->bus.fail_read = r->bus.fail_write = UINT32_MAX;
}

static void require_modeled_boundary(const struct rig *r)
{
    CHECK(r->boundary.transport_address ==
              r->boot.plan.region[NPU_BOOT_REQUEST].base &&
          r->boundary.transport_bytes == NPU_RRO_WIRE_SIZE &&
          r->boot.plan.region[NPU_BOOT_REQUEST].bytes == NPU_RRO_WIRE_SIZE &&
          r->boundary.transport_flags == 1u &&
          r->boundary.provider_ref && r->boundary.endpoint_ref &&
          r->boundary.retained_backing && r->boundary.cpu_excluded,
          "modeled pinned transport, retained references and CPU exclusion");
}

static struct npu_rro_wire_message message_for(const struct rig *r, uint32_t operation)
{
    struct npu_rro_wire_message message;

    memset(&message, 0, sizeof(message));
    message.plan.identity = r->plan.identity;
    message.plan.profile = r->plan.profile;
    message.operation = operation;
    message.sequence = r->server.last_sequence + 1u;
    if (operation == NPU_RRO_WIRE_OPEN)
        message.plan = r->plan;
    return message;
}

static uint32_t exchange(struct rig *r, const struct npu_rro_wire_message *message,
                         uint32_t expected_status)
{
    struct npu_rro_wire_packet packet, immutable;
    struct npu_rro_wire_message decoded;
    const struct npu_rro_native_context native = {mapped_read, mapped_write, r};
    uint32_t ticket, remote_status = 0xfeedfaceu;
    enum npu_client_result result;

    memset(&packet, 0xa5, sizeof(packet));
    require_modeled_boundary(r);
    ticket = npu_rro_client_request(&r->client, &packet, sizeof(packet), message);
    CHECK(ticket && ticket == r->client.base.pending, "client must issue RRO request");
    memcpy(&immutable, &packet, sizeof(packet));
    CHECK(!npu_rro_wire_decode(&decoded, &immutable, sizeof(immutable), 0) &&
          decoded.sequence == ticket && decoded.operation == message->operation,
          "client must encode its serial and operation");
    CHECK(npu_rro_session_dispatch(&r->broker, &r->server, &r->admission, &r->barrier,
          &r->boot, &r->cold, &packet, sizeof(packet), &native),
          "broker must return a shaped reply");
    CHECK(npu_rro_wire_echo(&immutable, &packet, sizeof(packet)),
          "broker reply must echo immutable request");
    CHECK(!npu_rro_wire_decode(&decoded, &packet, sizeof(packet), 1) &&
          decoded.status == expected_status, "broker status must match case");
    result = npu_rro_client_complete(&r->client, ticket, 0, &immutable, &packet,
                                      sizeof(packet), &remote_status);
    CHECK(remote_status == expected_status, "client must expose exact remote status");
    CHECK(result == (expected_status ? NPU_CLIENT_REJECTED : NPU_CLIENT_ACCEPTED),
          "client completion must honor remote status");
    if (!expected_status) {
        CHECK(!r->client.base.pending && r->client.base.phase == NPU_CLIENT_PARKED,
              "accepted client returns to parked idle");
        positive_rpc++;
    }
    return ticket;
}

static void compare_journals(struct rig *r)
{
    CHECK(!memcmp(&r->host, &r->broker.owner, sizeof(r->host)),
          "every positive broker journal byte must equal host mirror");
    CHECK(!memcmp(&r->plan, &r->broker.plan, sizeof(r->plan)),
          "broker must retain exact immutable plan");
    CHECK(!r->broker.error && !r->broker.inflight && !r->admission.active &&
          !r->admission.fault && !r->barrier.fault,
          "positive RPC leaves held owner and admission healthy");
    journal_compares++;
}

static void init_rig(struct rig *r, uint32_t profile)
{
    static const struct npu_bootstrap_plan boot_plan = {.region = {
        {0x80000000u, 0x240000u}, {0x81000000u, 0xe000u},
        {0x81200000u, 0x100000u}, {0x81400000u, 0x100000u},
        {0x81600000u, 0x100000u}, {0x83000000u, 256u}
    }};
    static const uint32_t api[NPU_BOOTSTRAP_STEPS] = {18u, 32u, 8u, 23u, 7u, 12u};
    struct npu_control_v2_packet packet;
    uint32_t epoch;

    memset(r, 0, sizeof(*r));
    npu_admission_init(&r->admission);
    npu_barrier_init(&r->barrier);
    CHECK(npu_bootstrap_init(&r->boot, &boot_plan), "real six-region bootstrap plan");
    CHECK(npu_bootstrap_v2_session_init(&r->server, &r->admission, &r->barrier,
          0x13579bdfu, 0xfedcba98u), "fresh V2 server identity");
    for (uint32_t i = 0; i < NPU_BOOTSTRAP_STEPS; i++) {
        const struct npu_bootstrap_packet command = {
            i ? 0x10u : 0x11u, api[i], i > 0 && i < 5 ? boot_plan.region[i].base : 0u
        };
        CHECK(npu_bootstrap_begin(&r->boot, &r->admission, &r->barrier,
              &command, sizeof(command)), "bootstrap step accepted");
        CHECK(npu_bootstrap_finish(&r->boot, &r->admission, &r->barrier, 1),
              "modeled bootstrap callback success");
    }
    CHECK(r->boot.step == 6 && r->boot.retained_mask == 0x1eu &&
          r->boot.plan.region[NPU_BOOT_REQUEST].bytes == 256u,
          "modeled boot must retain exact six regions and request window");
    npu_client_v2_init(&r->client, 0x2468ace0u, 0x8badf00du);
    for (uint32_t i = 0; i < 4u; i++) {
        uint32_t ticket = npu_client_v2_request(&r->client, &packet, sizeof(packet));

        CHECK(ticket == i + 1u, "real V2 handshake serial");
        if (i == 2u)
            for (uint32_t hart = 0; hart < NPU_BARRIER_WORKERS; hart++)
                CHECK(npu_barrier_poll(&r->barrier, hart, &epoch) == NPU_BARRIER_PARK &&
                      epoch == 1u, "modeled workers park before STOP");
        CHECK(npu_bootstrap_v2_control(&r->boot, &r->server, &r->admission,
              &r->barrier, &packet, sizeof(packet)), "V2 boot-bound control dispatch");
        CHECK(npu_client_v2_complete(&r->client, ticket, 0, &packet, sizeof(packet)) ==
              NPU_CLIENT_ACCEPTED, "V2 discover/bind/stop/status completion");
        handshakes++;
    }
    CHECK(r->client.base.phase == NPU_CLIENT_PARKED &&
          r->client.base.parked_mask == 0xffu && r->server.last_sequence == 4u &&
          r->admission.nonce_lo == r->client.base.nonce_lo &&
          r->admission.nonce_hi == r->client.base.nonce_hi,
          "real V2 client and server must be bound and parked");

    /* Cold DMA ownership and RX binding are modeled, then checked by the same
     * complete-inventory validator used by the broker. The request is 256 bytes. */
    r->cold.completed = NPU_COLD_ENDPOINT_BASE | NPU_COLD_ENDPOINT_BYTES;
    r->cold.endpoint_base = r->cold.txbuf.endpoint_base = 0x20000000u;
    r->cold.endpoint_bytes = r->cold.txbuf.endpoint_bytes = 0x100000u;
    r->cold.boot_lo = r->server.boot_lo;
    r->cold.boot_hi = r->server.boot_hi;
    r->cold.nonce_lo = r->server.nonce_lo;
    r->cold.nonce_hi = r->server.nonce_hi;
    r->cold.txbuf.boot = r->boot.plan;
    r->cold.txbuf_enrolled = NPU_COLD_TXBUF_RECORDS;
    r->cold.rx_event = 0x92000000u;
    for (uint32_t i = 0; i < NPU_COLD_TXBUF_MAILBOXES; i++)
        r->cold.txbuf.mailbox[i] = 0x83000000u + i * 256u;
    for (uint32_t i = 0; i < NPU_COLD_TXBUF_STEPS; i++)
        r->cold.txbuf.host[i] = 0x96000000u + i * 0x100000u;
    CHECK(npu_cold_endpoint_valid(r->cold.endpoint_base, r->cold.endpoint_bytes) &&
          npu_cold_txbuf_dma_valid(&r->cold.txbuf, NPU_COLD_TXBUF_RECORDS) &&
          r->cold.txbuf.mailbox[0] == r->boot.plan.region[NPU_BOOT_REQUEST].base,
          "modeled cold inventory must pass actual complete DMA validation");

    rro_test_plan(&r->plan, profile);
    r->plan.identity = (struct npu_rro_identity){
        0x11223344u, 0xdeadbeefu, 0x55667788u, 0x9abcdef0u,
        r->server.boot_lo, r->server.boot_hi,
        r->server.nonce_lo, r->server.nonce_hi, 1u
    };
    for (uint32_t i = 0; i < 8u; i++)
        r->plan.mailbox[i] = (struct npu_rro_span){r->cold.txbuf.mailbox[i], 256u};
    for (uint32_t i = 0; i < 6u; i++) {
        r->plan.tx[i] = (struct npu_rro_span){
            r->cold.txbuf.host[i], npu_cold_txbuf_bytes(i)
        };
        r->plan.native[i] = (struct npu_rro_span){
            r->boot.plan.region[i].base, r->boot.plan.region[i].bytes
        };
    }
    r->plan.rx_event = (struct npu_rro_span){r->cold.rx_event, 8192u};
    r->plan.bar = (struct npu_rro_span){r->cold.endpoint_base, r->cold.endpoint_bytes};
    r->boundary = (struct modeled_boundary){
        r->boot.plan.region[NPU_BOOT_REQUEST].base, NPU_RRO_WIRE_SIZE, 1u,
        1u, 1u, 1u, 1u, 1u
    };
    CHECK(r->plan.mailbox[0].bytes == r->boot.plan.region[NPU_BOOT_REQUEST].bytes,
          "protocol request occupies the exact 256-byte mailbox window");
    memset(r->sram, 0xa5, sizeof(r->sram));
    memset(r->dma, 0xa5, sizeof(r->dma));
    bus_idle(r);
}

static void verify_target(struct rig *r, uint32_t ordinal, int reset)
{
    uint32_t base = target_address(r), bytes = target_bytes(r), table = target_table(r);
    uint32_t pointer = alias(r->broker.owner.extents[r->bus.slot].dma_lo);
    unsigned char *target = mapping(r, base, bytes);

    memset(expected_dma, reset ? 0x35 : ordinal == NPU_RRO_BLOCKS ? 0xa5 : 0,
           bytes);
    for (uint32_t i = 7u; i < bytes; i += 8u)
        expected_dma[i] = 0xffu;
    CHECK(!memcmp(target, expected_dma, bytes),
          reset ? "reset must change only every eighth signature byte" :
                  "publication must have full exact block/session bytes");
    CHECK(!memcmp(mapping(r, table, 4u), &pointer, 4u),
          "native table must retain the exact DMA alias");
    if (reset) {
        CHECK(r->bus.writes == 1024u && r->bus.reads == 1026u,
              "reset must execute complete native signature/readback engine");
    } else {
        CHECK(r->bus.writes == (ordinal == NPU_RRO_BLOCKS ? 1025u : 24577u) &&
              r->bus.reads == (ordinal == NPU_RRO_BLOCKS ? 1026u : 24578u),
              "publication must execute complete native clear/signature/readback engine");
    }
    memory_checks++;
}

static void verify_whole_memory(struct rig *r, int after_all_resets)
{
    memset(expected_dma, 0xa5, sizeof(expected_dma));
    memset(expected_sram, 0xa5, sizeof(expected_sram));
    for (uint32_t ordinal = 0; ordinal < NPU_RRO_PUBLICATIONS; ordinal++) {
        uint32_t slot = slot_for(r, ordinal);
        uint32_t base = alias(r->broker.owner.extents[slot].dma_lo);
        uint32_t bytes = ordinal == NPU_RRO_BLOCKS ? NPU_RRO_SESSION_BYTES :
                         NPU_RRO_BLOCK_BYTES;
        uint32_t table = ordinal == NPU_RRO_BLOCKS ? NPU_RRO_NATIVE_SESSION_TABLE :
                         NPU_RRO_NATIVE_BLOCK_TABLE + ordinal * 4u;
        unsigned char *span;

        CHECK(base >= RRO_TEST_ALIAS && bytes <= RRO_TEST_ALIAS_BYTES &&
              base - RRO_TEST_ALIAS <= RRO_TEST_ALIAS_BYTES - bytes,
              "all native extents fit in bounded DMA array");
        CHECK(table >= RRO_TEST_SRAM && table - RRO_TEST_SRAM <= RRO_TEST_SRAM_BYTES - 4u,
              "all native table words fit in bounded SRAM array");
        span = expected_dma + (base - RRO_TEST_ALIAS);
        memset(span, after_all_resets ? 0x35 : ordinal == NPU_RRO_BLOCKS ? 0xa5 : 0,
               bytes);
        for (uint32_t i = 7u; i < bytes; i += 8u)
            span[i] = 0xffu;
        memcpy(expected_sram + (table - RRO_TEST_SRAM), &base, 4u);
    }
    CHECK(!memcmp(r->dma, expected_dma, sizeof(r->dma)),
          "every mapped DMA byte, including non-RRO guards, must match oracle");
    CHECK(!memcmp(r->sram, expected_sram, sizeof(r->sram)),
          "every mapped SRAM byte, including untouched table gaps, must match oracle");
    full_memory_checks++;
}

static void open_and_enroll(struct rig *r)
{
    struct npu_rro_wire_message message = message_for(r, NPU_RRO_WIRE_OPEN);
    uint32_t count = npu_rro_extent_count(r->plan.profile);

    CHECK(count == (r->plan.profile == NPU_RRO_V3_1_WED ? 137u : 139u),
          "profile uses complete 139/139/137 enrollment geometry");
    CHECK(!npu_rro_open(&r->host, &r->plan), "host journal open");
    exchange(r, &message, NPU_RRO_WIRE_OK);
    compare_journals(r);
    CHECK(!npu_rro_session_cold_ready(&r->broker),
          "building journal is not cold-ready");
    for (uint32_t ordinal = 0; ordinal < count; ordinal++) {
        struct npu_rro_extent extent;

        CHECK(!rro_test_extent(r->plan.profile, ordinal, &extent),
              "existing full-geometry extent fixture");
        CHECK(!npu_rro_enroll(&r->host, &r->plan, &extent),
              "host journal enrollment");
        message = message_for(r, NPU_RRO_WIRE_ENROLL);
        message.ordinal = ordinal;
        message.extent = extent;
        exchange(r, &message, NPU_RRO_WIRE_OK);
        compare_journals(r);
        enrollments++;
    }
}

static void publish_all(struct rig *r)
{
    for (uint32_t ordinal = 0; ordinal < NPU_RRO_PUBLICATIONS; ordinal++) {
        struct npu_rro_wire_message message = message_for(r, NPU_RRO_WIRE_PUBLISH);
        uint32_t ticket;

        CHECK(!npu_rro_publish_begin(&r->host, &r->plan, ordinal, &ticket,
              &message.command), "host journal generates four-word publication");
        message.ordinal = ordinal;
        message.ticket = ticket;
        CHECK(message.command.words[1] == r->host.extents[slot_for(r, ordinal)].dma_lo &&
              !message.command.words[2] && !message.command.words[3],
              "host four-word publication must bind actual retained DMA");
        bus_arm(r, ordinal, 0, 0);
        exchange(r, &message, NPU_RRO_WIRE_OK);
        CHECK(!npu_rro_publish_complete(&r->host, &r->plan, ordinal, ticket, 0),
              "host journal confirms only completed publication");
        compare_journals(r);
        verify_target(r, ordinal, 0);
        bus_idle(r);
        publications++;
    }
    verify_whole_memory(r, 0);
    CHECK(!npu_rro_session_cold_ready(&r->broker),
          "complete publications alone do not expose hardware");
}

static void begin_hardware(struct rig *r)
{
    struct npu_rro_wire_message message = message_for(r, NPU_RRO_WIRE_HARDWARE);

    CHECK(!npu_rro_hardware_begin(&r->host, &r->plan),
          "host journal records hardware-possible metadata");
    exchange(r, &message, NPU_RRO_WIRE_OK);
    compare_journals(r);
    CHECK(npu_rro_session_cold_ready(&r->broker) &&
          r->broker.owner.phase == NPU_RRO_LIVE && r->broker.owner.hardware_exposed,
          "full native publication plus hardware metadata is cold-ready");
    for (uint32_t i = 0; i < r->broker.owner.allocated; i++)
        CHECK((r->broker.owner.exposure[i] & NPU_RRO_HARDWARE_POSSIBLE) != 0,
              "hardware exposure retained for every full-geometry extent");
    hardware_begins++;
}

static void reset_one(struct rig *r, uint32_t generation, uint32_t id)
{
    struct npu_rro_wire_message message = message_for(r, NPU_RRO_WIRE_RESET_NPU);
    uint32_t ordinal = id == NPU_RRO_SESSIONS - 1u ? NPU_RRO_BLOCKS : id / 8u;
    uint32_t ticket;

    CHECK(r->host.resets[id].generation == generation &&
          r->broker.owner.resets[id].generation == generation,
          "test model supplies explicit current generation; production does not infer it");
    CHECK(!npu_rro_reset_queue(&r->host, &r->plan, id, generation, &ticket),
          "host queue reserves exact reset ticket");
    message.session = id;
    message.generation = generation;
    message.ticket = ticket;
    CHECK(!npu_rro_reset_npu_begin(&r->host, &r->plan, id, generation, ticket,
          &message.command), "host NPU_BEGIN generates four-word reset command");
    CHECK(message.command.selector == 3u && message.command.words[0] == id &&
          !message.command.words[1] && !message.command.words[2] &&
          !message.command.words[3], "full reset command identity and payload");
    bus_arm(r, ordinal, id, 1);
    memset(mapping(r, target_address(r), NPU_RRO_SESSION_BYTES), 0x35,
           NPU_RRO_SESSION_BYTES); /* Modeled intervening firmware data. */
    memcpy(expected_sram, r->sram, sizeof(r->sram));
    exchange(r, &message, NPU_RRO_WIRE_OK);
    CHECK(!npu_rro_reset_npu_complete(&r->host, &r->plan, id, generation,
          ticket, 0), "host journal confirms exact reset NPU completion");
    compare_journals(r);
    verify_target(r, ordinal, 1);
    CHECK(!memcmp(r->sram, expected_sram, sizeof(r->sram)),
          "reset cannot change any native table or SRAM guard byte");
    bus_idle(r);
    reset_npu++;

    message = message_for(r, NPU_RRO_WIRE_MCU_BEGIN);
    message.session = id;
    message.generation = generation;
    message.ticket = ticket;
    CHECK(!npu_rro_reset_mcu_begin(&r->host, &r->plan, id, generation,
          ticket), "host MCU_BEGIN records a modeled MCU boundary");
    exchange(r, &message, NPU_RRO_WIRE_OK);
    compare_journals(r);
    mcu_begins++;

    message = message_for(r, NPU_RRO_WIRE_MCU_COMPLETE);
    message.session = id;
    message.generation = generation;
    message.ticket = ticket;
    message.mcu_error = 0; /* Host-correlated model result, not physical MCU proof. */
    CHECK(r->boundary.mcu_result_model,
          "MCU completion is a modeled host-correlated result only");
    CHECK(!npu_rro_reset_mcu_complete(&r->host, &r->plan, id, generation,
          ticket, 0), "host journal records modeled MCU result");
    exchange(r, &message, NPU_RRO_WIRE_OK);
    compare_journals(r);
    CHECK(r->host.resets[id].generation == generation + 1u &&
          r->broker.owner.resets[id].phase == NPU_RRO_RESET_COMPLETE,
          "generation advances only after explicit modeled MCU result");
    mcu_completions++;
}

static void close_and_snapshot(struct rig *r)
{
    struct npu_rro_wire_message message = message_for(r, NPU_RRO_WIRE_CLOSE);
    struct npu_rro_retirement host_snapshot, broker_snapshot;
    uint32_t ticket;

    memcpy(expected_dma, r->dma, sizeof(r->dma));
    memcpy(expected_sram, r->sram, sizeof(r->sram));
    CHECK(!npu_rro_retirement_begin(&r->host, &r->plan, 2u, &ticket),
          "host close records stop epoch and ticket");
    message.stop_epoch = 2u;
    message.ticket = ticket;
    exchange(r, &message, NPU_RRO_WIRE_OK);
    compare_journals(r);
    CHECK(!npu_rro_retirement_snapshot(&r->host, &r->plan, &host_snapshot) &&
          !npu_rro_retirement_snapshot(&r->broker.owner, &r->broker.plan,
                                       &broker_snapshot), "both closing snapshots valid");
    CHECK(!memcmp(&host_snapshot, &broker_snapshot, sizeof(host_snapshot)) &&
          host_snapshot.phase == NPU_RRO_CLOSING && !host_snapshot.cpu_joined &&
          host_snapshot.allocated == npu_rro_extent_count(r->plan.profile) &&
          host_snapshot.confirmed_publications == NPU_RRO_PUBLICATIONS,
          "close preserves full ownership without CPU join authority");
    for (uint32_t domain = 0; domain < NPU_RRO_DRAIN_DOMAINS; domain++)
        CHECK(!host_snapshot.drained[domain], "close is not a physical drain witness");
    CHECK(!memcmp(expected_dma, r->dma, sizeof(r->dma)) &&
          !memcmp(expected_sram, r->sram, sizeof(r->sram)) &&
          !npu_rro_session_cold_ready(&r->broker),
          "closing retains mapped memory and is no longer cold-ready");
    require_modeled_boundary(r);
    close_calls++;
}

static void run_profile(uint32_t profile)
{
    init_rig(&work, profile);
    if (!profile)
        memcpy(&fresh, &work, sizeof(work));
    open_and_enroll(&work);
    if (!profile)
        memcpy(&prepublication, &work, sizeof(work));
    publish_all(&work);
    begin_hardware(&work);
    if (!profile)
        memcpy(&live, &work, sizeof(work));
    for (uint32_t generation = 1u; generation <= 2u; generation++)
        for (uint32_t id = 0; id < NPU_RRO_SESSIONS; id++)
            reset_one(&work, generation, id);
    verify_whole_memory(&work, 1);
    close_and_snapshot(&work);
}

static void direct_reply(struct rig *r, const struct npu_rro_wire_message *message,
                         uint32_t expected_status)
{
    struct npu_rro_wire_packet packet, immutable;
    struct npu_rro_wire_message decoded;
    const struct npu_rro_native_context native = {mapped_read, mapped_write, r};

    memset(&packet, 0xa5, sizeof(packet));
    require_modeled_boundary(r);
    CHECK(!npu_rro_wire_encode(&packet, sizeof(packet), message),
          "adversarial packet must be validly shaped before broker validation");
    immutable = packet;
    CHECK(npu_rro_session_dispatch(&r->broker, &r->server, &r->admission,
          &r->barrier, &r->boot, &r->cold, &packet, sizeof(packet), &native),
          "broker must reply to a shaped adversarial packet");
    CHECK(npu_rro_wire_echo(&immutable, &packet, sizeof(packet)) &&
          !npu_rro_wire_decode(&decoded, &packet, sizeof(packet), 1) &&
          decoded.status == expected_status,
          "adversarial reply must preserve exact request and expected status");
    direct_negative++;
}

static void unchanged_owner_and_memory(struct rig *r,
                                        const struct npu_rro_lifetime *before)
{
    CHECK(!memcmp(&r->broker.owner, before, sizeof(*before)),
          "rejected identity/replay must leave every journal byte unchanged");
    CHECK(!memcmp(r->dma, expected_dma, sizeof(r->dma)) &&
          !memcmp(r->sram, expected_sram, sizeof(r->sram)) &&
          !r->bus.reads && !r->bus.writes,
          "rejected operation must not perform native I/O");
}

static void identity_and_replay_controls(void)
{
    for (uint32_t kind = 0; kind < 5u; kind++) {
        struct npu_rro_wire_message message;
        struct npu_rro_lifetime before;
        uint32_t sequence, expected;

        memcpy(&work, &live, sizeof(work));
        bus_idle(&work);
        before = work.broker.owner;
        sequence = work.server.last_sequence;
        memcpy(expected_dma, work.dma, sizeof(work.dma));
        memcpy(expected_sram, work.sram, sizeof(work.sram));
        message = message_for(&work, NPU_RRO_WIRE_HARDWARE);
        expected = NPU_RRO_WIRE_BAD_IDENTITY;
        if (kind == 0u)
            message.plan.identity.provider_hi ^= 1u;
        else if (kind == 1u)
            message.plan.identity.endpoint_hi ^= 1u;
        else if (kind == 2u) {
            message.plan.identity.boot_hi ^= 1u;
            expected = NPU_RRO_WIRE_BAD_BOOT;
        } else if (kind == 3u)
            message.plan.identity.nonce_hi ^= 1u;
        else {
            message.sequence = sequence;
            expected = NPU_RRO_WIRE_REPLAY;
        }
        direct_reply(&work, &message, expected);
        unchanged_owner_and_memory(&work, &before);
        CHECK(work.server.last_sequence == sequence && !work.broker.error &&
              !work.admission.fault && !work.barrier.fault,
              kind < 2u ? "high identity must reject before operation" :
              "boot/nonce/replay must reject before sequence consumption");
        negative_cases++;
    }

    memcpy(&work, &live, sizeof(work));
    struct npu_rro_wire_message zero_sequence = message_for(&work, NPU_RRO_WIRE_HARDWARE);
    struct npu_rro_wire_packet packet, unchanged;
    zero_sequence.sequence = 0;
    memset(&packet, 0xa5, sizeof(packet));
    unchanged = packet;
    CHECK(npu_rro_wire_encode(&packet, sizeof(packet), &zero_sequence) ==
          NPU_RRO_WIRE_BAD_MESSAGE && !memcmp(&packet, &unchanged, sizeof(packet)),
          "zero sequence must reject without changing output packet");
    negative_cases++;
}

static void retained_state_failure(struct rig *r, uint32_t expected_status,
                                   uint32_t expected_ticket)
{
    CHECK(r->broker.error == expected_status && r->admission.fault &&
          r->barrier.fault && r->broker.owner.magic == NPU_RRO_MAGIC &&
          r->broker.owner.allocated == npu_rro_extent_count(r->plan.profile) &&
          r->broker.owner.last_ticket == expected_ticket,
          "broker failure must hold full retained journal, never release it");
    CHECK(!r->bus.reads && !r->bus.writes &&
          !memcmp(r->dma, expected_dma, sizeof(r->dma)) &&
          !memcmp(r->sram, expected_sram, sizeof(r->sram)),
          "rejected operation must not touch mapped native memory");
}

static void cold_inventory_controls(void)
{
    for (uint32_t kind = 0; kind < 3u; kind++) {
        struct npu_rro_wire_message message;

        memcpy(&work, &fresh, sizeof(work));
        bus_idle(&work);
        message = message_for(&work, NPU_RRO_WIRE_OPEN);
        if (kind == 0u)
            message.plan.mailbox[0].bytes = 4096u;
        else if (kind == 1u) {
            work.cold.txbuf.host[0] = work.cold.txbuf.mailbox[0];
            message.plan.tx[0].address = work.cold.txbuf.host[0];
            CHECK(!npu_cold_txbuf_dma_valid(&work.cold.txbuf, NPU_COLD_TXBUF_RECORDS),
                  "overlapping cold inventory must fail actual DMA validator");
        } else
            work.cold.txbuf_enrolled = NPU_COLD_TXBUF_RECORDS - 1u;
        memcpy(expected_dma, work.dma, sizeof(work.dma));
        memcpy(expected_sram, work.sram, sizeof(work.sram));
        direct_reply(&work, &message, NPU_RRO_WIRE_STATE);
        CHECK(!work.broker.owner.magic && !work.broker.owner.allocated &&
              !work.broker.magic && work.broker.error == NPU_RRO_WIRE_STATE &&
              !work.bus.reads && !work.bus.writes &&
              !memcmp(work.dma, expected_dma, sizeof(work.dma)) &&
              !memcmp(work.sram, expected_sram, sizeof(work.sram)),
              kind == 0u ? "4096-byte synthetic mailbox must reject actual 256-byte window" :
              "invalid complete cold inventory must reject before journal OPEN");
        negative_cases++;
    }
}

static void publication_and_reset_controls(void)
{
    for (uint32_t kind = 0; kind < 2u; kind++) {
        struct npu_rro_wire_message message;

        memcpy(&work, &prepublication, sizeof(work));
        bus_idle(&work);
        message = message_for(&work, NPU_RRO_WIRE_PUBLISH);
        message.ordinal = 0;
        message.ticket = kind ? 2u : 1u;
        message.command.selector = 0;
        message.command.words[0] = 0;
        message.command.words[1] = work.broker.owner.extents[slot_for(&work, 0)].dma_lo;
        if (!kind)
            message.command.words[1] ^= 4u;
        memcpy(expected_dma, work.dma, sizeof(work.dma));
        memcpy(expected_sram, work.sram, sizeof(work.sram));
        direct_reply(&work, &message, NPU_RRO_WIRE_STATE);
        retained_state_failure(&work, NPU_RRO_WIRE_STATE, 0);
        CHECK(!work.broker.owner.publication[0].ticket &&
              !work.broker.owner.confirmed,
              kind ? "publish ticket must match the next journal ticket" :
                     "publish payload DMA must match retained extent");
        negative_cases++;
    }
    for (uint32_t kind = 0; kind < 2u; kind++) {
        struct npu_rro_wire_message message;
        uint32_t expected;

        memcpy(&work, &live, sizeof(work));
        bus_idle(&work);
        message = message_for(&work, NPU_RRO_WIRE_RESET_NPU);
        message.session = 0;
        message.generation = kind ? 1u : 2u;
        message.ticket = kind ? NPU_RRO_PUBLICATIONS + 2u : NPU_RRO_PUBLICATIONS + 1u;
        message.command.selector = 3u;
        message.command.words[0] = 0;
        expected = kind ? NPU_RRO_WIRE_STATE : NPU_RRO_WIRE_CORE + NPU_RRO_STALE;
        memcpy(expected_dma, work.dma, sizeof(work.dma));
        memcpy(expected_sram, work.sram, sizeof(work.sram));
        direct_reply(&work, &message, expected);
        retained_state_failure(&work, expected, kind ? NPU_RRO_PUBLICATIONS + 1u :
                                      NPU_RRO_PUBLICATIONS);
        CHECK(work.broker.owner.resets[0].phase == (kind ? NPU_RRO_RESET_QUEUED :
                                                   NPU_RRO_RESET_IDLE),
              kind ? "wrong reset ticket retains queued prefix" :
                     "wrong reset generation cannot queue");
        negative_cases++;
    }
}

static void changed_held_controls(void)
{
    for (uint32_t kind = 0; kind < 7u; kind++) {
        struct npu_rro_wire_message message;
        uint32_t ticket = live.broker.owner.last_ticket;

        memcpy(&work, &live, sizeof(work));
        bus_idle(&work);
        if (kind == 0u)
            work.cold.txbuf.host[0] ^= 256u;
        else if (kind == 1u)
            work.cold.rx_event ^= 4u;
        else if (kind == 2u)
            work.cold.failed = 1;
        else if (kind == 3u)
            work.cold.inflight = 1;
        else if (kind == 4u)
            work.barrier.parked[7] = 0;
        else if (kind == 5u)
            work.admission.fault = 1;
        else
            work.admission.deferred[0] = 1;
        message = message_for(&work, NPU_RRO_WIRE_HARDWARE);
        memcpy(expected_dma, work.dma, sizeof(work.dma));
        memcpy(expected_sram, work.sram, sizeof(work.sram));
        direct_reply(&work, &message, NPU_RRO_WIRE_STATE);
        retained_state_failure(&work, NPU_RRO_WIRE_STATE, ticket);
        CHECK(work.broker.owner.phase == NPU_RRO_LIVE &&
              work.broker.owner.allocated == 139u &&
              work.broker.owner.confirmed == 129u,
              "changed cold/parked/fault/deferred state cannot shed retained ownership");
        negative_cases++;
    }
}

static void expected_publication_prefix(struct rig *r, uint32_t successful_writes)
{
    uint32_t table = NPU_RRO_NATIVE_BLOCK_TABLE;
    uint32_t pointer = alias(r->broker.owner.extents[slot_for(r, 0)].dma_lo);
    uint32_t clears = successful_writes ? successful_writes - 1u : 0u;
    uint32_t signatures;

    CHECK(clears <= NPU_RRO_BLOCK_BYTES / 4u + NPU_RRO_BLOCK_BYTES / 8u,
          "fault point stays within publication engine");
    if (successful_writes)
        memcpy(expected_sram + (table - RRO_TEST_SRAM), &pointer, 4u);
    if (clears > NPU_RRO_BLOCK_BYTES / 4u)
        clears = NPU_RRO_BLOCK_BYTES / 4u;
    memset(expected_dma + (pointer - RRO_TEST_ALIAS), 0, clears * 4u);
    signatures = successful_writes > 1u + NPU_RRO_BLOCK_BYTES / 4u ?
                 successful_writes - 1u - NPU_RRO_BLOCK_BYTES / 4u : 0u;
    for (uint32_t i = 0; i < signatures; i++)
        expected_dma[pointer - RRO_TEST_ALIAS + i * 8u + 7u] = 0xffu;
}

static void publication_io_failures(void)
{
    for (uint32_t kind = 0; kind < 4u; kind++) {
        struct npu_rro_wire_message message;
        uint32_t ticket, successful;

        memcpy(&work, &prepublication, sizeof(work));
        message = message_for(&work, NPU_RRO_WIRE_PUBLISH);
        message.ordinal = 0;
        CHECK(!npu_rro_publish_begin(&work.host, &work.plan, 0, &ticket,
              &message.command), "host claim precedes failing native publication");
        message.ticket = ticket;
        bus_arm(&work, 0, 0, 0);
        work.bus.fail_write = kind == 0u || kind == 1u ? 0u : kind == 2u ? 100u : UINT32_MAX;
        work.bus.after_write = kind == 1u;
        work.bus.fail_read = kind == 3u ? 0u : UINT32_MAX;
        memcpy(expected_dma, work.dma, sizeof(work.dma));
        memcpy(expected_sram, work.sram, sizeof(work.sram));
        exchange(&work, &message, NPU_RRO_WIRE_CORE + NPU_RRO_HELD);
        CHECK(npu_rro_publish_complete(&work.host, &work.plan, 0, ticket, -1) ==
              NPU_RRO_HELD, "host failure retains possible publication");
        CHECK(!memcmp(&work.host, &work.broker.owner, sizeof(work.host)) &&
              work.broker.owner.publication[0].ticket == ticket &&
              work.broker.owner.publication[0].error &&
              work.broker.owner.exposure[slot_for(&work, 0)] ==
                  (NPU_RRO_ALLOCATED | NPU_RRO_NPU_POSSIBLE) &&
              work.broker.owner.confirmed == 0,
              "failed native publication retains exactly the host possible prefix");
        successful = kind == 3u ? 1u : work.bus.writes - (work.bus.after_write ? 0u : 1u);
        expected_publication_prefix(&work, successful);
        CHECK(!memcmp(expected_dma, work.dma, sizeof(work.dma)) &&
              !memcmp(expected_sram, work.sram, sizeof(work.sram)),
              "failed publication retains exact full-array write prefix");
        CHECK(work.client.base.phase == NPU_CLIENT_FAILED &&
              work.broker.error == NPU_RRO_WIRE_CORE + NPU_RRO_HELD &&
              work.admission.fault && work.barrier.fault,
              "I/O failure holds client, broker and admission");
        io_faults++;
        negative_cases++;
    }
}

static struct npu_rro_wire_message begin_test_reset(struct rig *r, uint32_t id,
                                                     uint32_t *ticket)
{
    struct npu_rro_wire_message message = message_for(r, NPU_RRO_WIRE_RESET_NPU);

    CHECK(!npu_rro_reset_queue(&r->host, &r->plan, id, 1u, ticket),
          "host reset queue for adversarial case");
    message.session = id;
    message.generation = 1u;
    message.ticket = *ticket;
    CHECK(!npu_rro_reset_npu_begin(&r->host, &r->plan, id, 1u, *ticket,
          &message.command), "host reset NPU_BEGIN for adversarial case");
    bus_arm(r, id == NPU_RRO_SESSIONS - 1u ? NPU_RRO_BLOCKS : id / 8u, id, 1);
    memset(mapping(r, target_address(r), NPU_RRO_SESSION_BYTES), 0x35,
           NPU_RRO_SESSION_BYTES);
    return message;
}

static void reset_io_failures(void)
{
    for (uint32_t kind = 0; kind < 2u; kind++) {
        struct npu_rro_wire_message message;
        uint32_t ticket, base, successful;

        memcpy(&work, &live, sizeof(work));
        message = begin_test_reset(&work, 7u, &ticket);
        work.bus.fail_write = kind ? 512u : 0u;
        work.bus.after_write = kind != 0u;
        memcpy(expected_dma, work.dma, sizeof(work.dma));
        memcpy(expected_sram, work.sram, sizeof(work.sram));
        exchange(&work, &message, NPU_RRO_WIRE_CORE + NPU_RRO_HELD);
        CHECK(npu_rro_reset_npu_complete(&work.host, &work.plan, 7u, 1u,
              ticket, -1) == NPU_RRO_HELD,
              "host reset failure retains NPU-possible ticket");
        CHECK(!memcmp(&work.host, &work.broker.owner, sizeof(work.host)) &&
              work.broker.owner.resets[7].phase == NPU_RRO_RESET_NPU_POSSIBLE &&
              work.broker.owner.resets[7].npu_error && work.broker.owner.error,
              "native reset fault and host journal retain same possible prefix");
        successful = work.bus.writes - (work.bus.after_write ? 0u : 1u);
        base = target_address(&work) - RRO_TEST_ALIAS;
        for (uint32_t i = 0; i < successful; i++)
            expected_dma[base + i * 8u + 7u] = 0xffu;
        CHECK(!memcmp(expected_dma, work.dma, sizeof(work.dma)) &&
              !memcmp(expected_sram, work.sram, sizeof(work.sram)),
              "failed reset retains exact full-array signature prefix");
        CHECK(npu_rro_reset_mcu_begin(&work.host, &work.plan, 7u, 1u, ticket) !=
              NPU_RRO_OK, "failed reset cannot advance into MCU completion");
        io_faults++;
        negative_cases++;
    }
}

static void pending_retry_and_replay(void)
{
    struct npu_rro_wire_packet packet, immutable, first_reply, retry;
    struct npu_rro_wire_message message, decoded;
    const struct npu_rro_native_context native = {mapped_read, mapped_write, &work};
    uint32_t host_ticket, local_ticket, status = UINT32_MAX;
    uint32_t read_count, write_count, sequence;
    struct npu_rro_lifetime after_first;

    memcpy(&work, &live, sizeof(work));
    message = begin_test_reset(&work, 0u, &host_ticket);
    require_modeled_boundary(&work);
    local_ticket = npu_rro_client_request(&work.client, &packet, sizeof(packet), &message);
    CHECK(local_ticket != 0, "client starts one pending request");
    immutable = packet;
    memset(&retry, 0xa5, sizeof(retry));
    CHECK(!npu_rro_client_request(&work.client, &retry, sizeof(retry), &message) &&
          work.client.base.pending == local_ticket,
          "pending retry must deduplicate before writing another packet");
    for (uint32_t i = 0; i < sizeof(retry.bytes); i++)
        CHECK(retry.bytes[i] == 0xa5u, "pending retry leaves packet unchanged");
    CHECK(npu_rro_session_dispatch(&work.broker, &work.server, &work.admission,
          &work.barrier, &work.boot, &work.cold, &packet, sizeof(packet), &native),
          "first pending packet executes through broker");
    first_reply = packet;
    CHECK(!npu_rro_wire_decode(&decoded, &first_reply, sizeof(first_reply), 1) &&
          !decoded.status, "first pending reply succeeds");
    CHECK(!npu_rro_reset_npu_complete(&work.host, &work.plan, 0u, 1u,
          host_ticket, 0), "host journals first reset completion once");
    CHECK(!memcmp(&work.host, &work.broker.owner, sizeof(work.host)),
          "first pending completion matches full host journal");
    after_first = work.broker.owner;
    read_count = work.bus.reads;
    write_count = work.bus.writes;
    sequence = work.server.last_sequence;
    packet = immutable;
    CHECK(npu_rro_session_dispatch(&work.broker, &work.server, &work.admission,
          &work.barrier, &work.boot, &work.cold, &packet, sizeof(packet), &native),
          "replayed exact request receives shaped reply");
    CHECK(!npu_rro_wire_decode(&decoded, &packet, sizeof(packet), 1) &&
          decoded.status == NPU_RRO_WIRE_REPLAY &&
          !memcmp(&after_first, &work.broker.owner, sizeof(after_first)) &&
          sequence == work.server.last_sequence && read_count == work.bus.reads &&
          write_count == work.bus.writes,
          "replay cannot repeat native effects or journal transition");
    CHECK(npu_rro_client_complete(&work.client, local_ticket, 0,
          &immutable, &first_reply, sizeof(first_reply), &status) ==
          NPU_CLIENT_ACCEPTED && !status, "original immutable request completes once");
    status = 0xfeedfaceu;
    CHECK(npu_rro_client_complete(&work.client, local_ticket, 0,
          &immutable, &packet, sizeof(packet), &status) == NPU_CLIENT_IGNORED &&
          status == 0xfeedfaceu, "late replay completion is ignored before dereference");
    negative_cases++;
}

static void corrupted_reply_and_transport_failure(void)
{
    for (uint32_t kind = 0; kind < 2u; kind++) {
        struct npu_rro_wire_packet packet, immutable;
        struct npu_rro_wire_message message;
        const struct npu_rro_native_context native = {mapped_read, mapped_write, &work};
        uint32_t host_ticket, local_ticket, remote_status = 0xfeedfaceu;

        memcpy(&work, &live, sizeof(work));
        message = begin_test_reset(&work, 0u, &host_ticket);
        require_modeled_boundary(&work);
        local_ticket = npu_rro_client_request(&work.client, &packet, sizeof(packet), &message);
        CHECK(local_ticket, "client sends fault-control reset request");
        immutable = packet;
        CHECK(npu_rro_session_dispatch(&work.broker, &work.server, &work.admission,
              &work.barrier, &work.boot, &work.cold, &packet, sizeof(packet), &native),
              "broker executes before adversarial completion");
        CHECK(work.broker.owner.resets[0].phase == NPU_RRO_RESET_NPU_CONFIRMED &&
              work.host.resets[0].phase == NPU_RRO_RESET_NPU_POSSIBLE,
              "broker effect precedes independent host completion");
        if (!kind) {
            /* Profile is decoded but not part of client identity; only exact echo
             * correlates it to the immutable request. */
            packet.bytes[17u * 4u] ^= 1u;
            CHECK(npu_rro_client_complete(&work.client, local_ticket, 0,
                  &immutable, &packet, sizeof(packet), &remote_status) ==
                  NPU_CLIENT_REJECTED && remote_status == 0xfeedfaceu &&
                  work.client.error == NPU_CLIENT_V2_ENVELOPE,
                  "client echo must reject corrupted but parseable reply");
        } else {
            CHECK(npu_rro_client_complete(&work.client, local_ticket, 1,
                  NULL, NULL, 0, NULL) == NPU_CLIENT_REJECTED &&
                  work.client.error == NPU_CLIENT_V2_ENVELOPE,
                  "transport failure holds client without reading storage");
            CHECK(npu_rro_reset_npu_complete(&work.host, &work.plan, 0u, 1u,
                  host_ticket, -1) == NPU_RRO_HELD && work.host.error &&
                  work.host.resets[0].phase == NPU_RRO_RESET_NPU_POSSIBLE,
                  "transport ambiguity retains host possible prefix");
        }
        CHECK(npu_rro_client_complete(&work.client, local_ticket, 0,
              &immutable, &packet, sizeof(packet), &remote_status) ==
              NPU_CLIENT_IGNORED && remote_status == 0xfeedfaceu &&
              work.broker.owner.allocated == 139u,
              "late reply after client failure cannot grant release");
        negative_cases++;
    }
}

static void client_argument_controls(void)
{
    struct npu_rro_wire_message message, untouched;
    struct npu_rro_wire_packet packet, before, reply_before;
    uint32_t ticket, remote_status;
    struct npu_control_v2_session server_before;

    memcpy(&work, &live, sizeof(work));
    message = message_for(&work, NPU_RRO_WIRE_HARDWARE);
    message.plan.identity.boot_hi ^= 1u;
    memset(&packet, 0xa5, sizeof(packet));
    before = packet;
    CHECK(!npu_rro_client_request(&work.client, &packet, sizeof(packet), &message) &&
          !memcmp(&packet, &before, sizeof(packet)) &&
          work.client.base.phase == NPU_CLIENT_FAILED,
          "client identity rejection leaves separate packet unchanged");
    negative_cases++;

    memcpy(&work, &live, sizeof(work));
    message = message_for(&work, NPU_RRO_WIRE_HARDWARE);
    memset(&packet, 0xa5, sizeof(packet));
    before = packet;
    CHECK(!npu_rro_client_request(&work.client, &packet, sizeof(packet) - 1u,
          &message) && !memcmp(&packet, &before, sizeof(packet)),
          "client length rejection leaves packet unchanged");
    negative_cases++;

    memcpy(&work, &live, sizeof(work));
    message = message_for(&work, NPU_RRO_WIRE_HARDWARE);
    untouched = message;
    CHECK(!npu_rro_client_request(&work.client, &message, NPU_RRO_WIRE_SIZE,
          &message) && !memcmp(&message, &untouched, sizeof(message)),
          "client input/output alias must reject without changing input packet");
    negative_cases++;

    memcpy(&work, &live, sizeof(work));
    message = message_for(&work, NPU_RRO_WIRE_HARDWARE);
    server_before = work.server;
    CHECK(!npu_rro_client_request(&work.client, &work.client, NPU_RRO_WIRE_SIZE,
          &message) && work.client.base.phase == NPU_CLIENT_FAILED &&
          !memcmp(&server_before, &work.server, sizeof(server_before)),
          "client/output alias rejects without writing adjacent server storage");
    negative_cases++;

    memcpy(&work, &live, sizeof(work));
    message = message_for(&work, NPU_RRO_WIRE_HARDWARE);
    ticket = npu_rro_client_request(&work.client, &packet, sizeof(packet), &message);
    before = packet;
    CHECK(ticket && !npu_rro_wire_reply(&packet, sizeof(packet), 0),
          "shape a separate client completion alias control");
    reply_before = packet;
    remote_status = 0xfeedfaceu;
    CHECK(npu_rro_client_complete(&work.client, ticket, 0, &before, &packet,
          sizeof(packet), (uint32_t *)packet.bytes) == NPU_CLIENT_REJECTED &&
          work.client.error == NPU_CLIENT_V2_ARGUMENT &&
          remote_status == 0xfeedfaceu &&
          !memcmp(&packet, &reply_before, sizeof(packet)),
          "client remote-status/reply alias must reject before output");
    negative_cases++;
}

static void run_negative_controls(void)
{
    identity_and_replay_controls();
    cold_inventory_controls();
    publication_and_reset_controls();
    changed_held_controls();
    publication_io_failures();
    reset_io_failures();
    pending_retry_and_replay();
    corrupted_reply_and_transport_failure();
    client_argument_controls();
}

int main(int argc, char **argv)
{
    CHECK(__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__, "host mapping requires little endian");
    CHECK(argc == 1 || argc == 2, "optional single-case mutation selector");
    if (argc == 2) {
        init_rig(&work, NPU_RRO_V3);
        memcpy(&fresh, &work, sizeof(work));
        open_and_enroll(&work);
        memcpy(&prepublication, &work, sizeof(work));
        publish_all(&work);
        begin_hardware(&work);
        memcpy(&live, &work, sizeof(work));
        if (!strcmp(argv[1], "high-identity"))
            identity_and_replay_controls();
        else if (!strcmp(argv[1], "bad-ticket"))
            publication_and_reset_controls();
        else if (!strcmp(argv[1], "bad-mailbox"))
            cold_inventory_controls();
        else if (!strcmp(argv[1], "client-identity"))
            client_argument_controls();
        else if (!strcmp(argv[1], "reply-echo"))
            corrupted_reply_and_transport_failure();
        else if (!strcmp(argv[1], "native-clear")) {
            /* publish_all already checked all exact blocks. */
        } else
            CHECK(0, "unknown mutation selector");
        printf("{\"passed\":true,\"case\":\"%s\"}\n", argv[1]);
        return 0;
    }
    for (uint32_t profile = 0; profile < 3u; profile++)
        run_profile(profile);
    run_negative_controls();
    CHECK(handshakes == 12u && enrollments == 415u && publications == 387u &&
          hardware_begins == 3u && reset_npu == 6150u &&
          mcu_begins == 6150u && mcu_completions == 6150u && close_calls == 3u,
          "literal full three-profile operation matrix");
    CHECK(positive_rpc == 19261u && memory_checks == 6537u &&
          full_memory_checks == 6u && io_faults == 6u,
          "full matrix and six I/O prefix cases, never a truncated smoke");
    printf("{\"passed\":true,\"profiles\":3,\"enrollments\":%u,"
           "\"publications\":%u,\"reset_npu\":%u,\"mcu_begin\":%u,"
           "\"mcu_complete\":%u,\"positive_rpc\":%u,\"journal_compares\":%u,"
           "\"memory_checks\":%u,\"full_memory_checks\":%u,"
           "\"negative_cases\":%u,\"direct_negative\":%u,"
           "\"io_faults\":%u,\"checks\":%u,\"hardware\":false}\n",
           enrollments, publications, reset_npu, mcu_begins, mcu_completions,
           positive_rpc, journal_compares, memory_checks, full_memory_checks,
           negative_cases, direct_negative, io_faults, checks);
    return 0;
}
