/* Host journal oracle for the raw CODE/DATA test. Native I/O runs in RV32.
 * MCU completions here are explicit host-result models. */
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "rro-session.h"

#define ORACLE_MAGIC 0x314f524eu
#define ORACLE_WORDS 32u

static struct npu_rro_lifetime journal;
static struct npu_rro_plan plan;

static void require(int okay, const char *operation)
{
    if (!okay) {
        fprintf(stderr, "raw-pair-oracle: %s\n", operation);
        abort();
    }
}

static void write_exact(const void *data, size_t bytes)
{
    require(fwrite(data, 1, bytes, stdout) == bytes, "write");
}

static void read_exact(void *data, size_t bytes)
{
    require(fread(data, 1, bytes, stdin) == bytes, "read");
}

static void extent(uint32_t ordinal, struct npu_rro_extent *out)
{
    require(!npu_rro_extent_geometry(plan.profile, ordinal, out), "extent geometry");
    /* Same retained extent coordinates as the host-q2 session evidence. The
     * mailbox/TX/RX/native protected spans come from the executed raw prefix. */
    out->cpu_lo = 0x10000000u + ordinal * 0x20000u;
    out->cpu_hi = 1;
    if (out->role == NPU_RRO_ELEMENT)
        out->dma_lo = 0x88000000u + out->index * NPU_RRO_BLOCK_BYTES;
    else if (out->role == NPU_RRO_SESSION)
        out->dma_lo = 0x88801000u;
    else if (out->role == NPU_RRO_BA)
        out->dma_lo = 0x88900000u + out->index * NPU_RRO_BLOCK_BYTES;
    else if (out->role == NPU_RRO_MSDU)
        out->dma_lo = 0x88a00000u + out->index * NPU_RRO_BLOCK_BYTES;
    else
        out->dma_lo = 0x88b00000u + (out->role == NPU_RRO_EMI_DMA ? 0x1000u : 0u);
}

static void request(const uint32_t command[4])
{
    struct npu_rro_wire_message message;
    struct npu_rro_wire_packet wire;
    uint32_t ticket = 0, status = NPU_RRO_ARGUMENT;
    uint32_t header[4] = {ORACLE_MAGIC, command[0], command[1], sizeof(journal)};

    memset(&message, 0, sizeof(message));
    message.operation = command[0];
    message.sequence = command[1];
    message.plan = plan;
    switch (message.operation) {
    case NPU_RRO_WIRE_OPEN:
        status = npu_rro_open(&journal, &plan);
        break;
    case NPU_RRO_WIRE_ENROLL:
        message.ordinal = command[2];
        extent(message.ordinal, &message.extent);
        status = npu_rro_enroll(&journal, &plan, &message.extent);
        break;
    case NPU_RRO_WIRE_PUBLISH:
        message.ordinal = command[2];
        status = npu_rro_publish_begin(&journal, &plan, message.ordinal,
                                       &ticket, &message.command);
        message.ticket = ticket;
        require(!status, "publish begin");
        status = npu_rro_publish_complete(&journal, &plan, message.ordinal, ticket, 0);
        break;
    case NPU_RRO_WIRE_HARDWARE:
        status = npu_rro_hardware_begin(&journal, &plan);
        break;
    case NPU_RRO_WIRE_RESET_NPU:
        message.session = command[2];
        message.generation = command[3];
        status = npu_rro_reset_queue(&journal, &plan, message.session,
                                     message.generation, &ticket);
        message.ticket = ticket;
        require(!status, "reset queue");
        status = npu_rro_reset_npu_begin(&journal, &plan, message.session,
            message.generation, ticket, &message.command);
        require(!status, "reset begin");
        status = npu_rro_reset_npu_complete(&journal, &plan, message.session,
                                            message.generation, ticket, 0);
        break;
    case NPU_RRO_WIRE_MCU_BEGIN:
    case NPU_RRO_WIRE_MCU_COMPLETE:
        message.session = command[2];
        message.generation = command[3];
        require(message.session < NPU_RRO_SESSIONS, "MCU session");
        message.ticket = journal.resets[message.session].ticket;
        if (message.operation == NPU_RRO_WIRE_MCU_BEGIN)
            status = npu_rro_reset_mcu_begin(&journal, &plan, message.session,
                                             message.generation, message.ticket);
        else
            status = npu_rro_reset_mcu_complete(&journal, &plan, message.session,
                                                message.generation, message.ticket, 0);
        break;
    case NPU_RRO_WIRE_CLOSE:
        message.stop_epoch = 2;
        status = npu_rro_retirement_begin(&journal, &plan, message.stop_epoch, &ticket);
        message.ticket = ticket;
        break;
    }
    require(!status, "journal transition");
    require(!npu_rro_wire_encode(&wire, sizeof(wire), &message), "wire encode");
    write_exact(header, sizeof(header));
    write_exact(&wire, sizeof(wire));
    write_exact(&journal, sizeof(journal));
    require(!fflush(stdout), "flush record");
}

int main(void)
{
    const uint32_t layout[ORACLE_WORDS] = {
        ORACLE_MAGIC, 1, ORACLE_WORDS, sizeof(plan), sizeof(journal),
        sizeof(struct npu_rro_session), offsetof(struct npu_rro_session, owner),
        offsetof(struct npu_rro_session, plan),
        offsetof(struct npu_rro_lifetime, extents), sizeof(struct npu_rro_extent),
        offsetof(struct npu_rro_lifetime, resets), sizeof(struct npu_rro_reset),
        offsetof(struct npu_rro_lifetime, error), offsetof(struct npu_rro_lifetime, phase),
        offsetof(struct npu_rro_lifetime, allocated),
        offsetof(struct npu_rro_lifetime, confirmed),
        offsetof(struct npu_rro_lifetime, publication), sizeof(struct npu_rro_publication),
        offsetof(struct npu_rro_lifetime, exposure),
        sizeof(struct npu_cold_setup), offsetof(struct npu_cold_setup, txbuf_enrolled),
        offsetof(struct npu_cold_setup, rx_event),
        NPU_RRO_WIRE_CORE + NPU_RRO_HELD, NPU_RRO_PUBLICATION_FAILED,
        NPU_RRO_NPU_RESET_FAILED, NPU_RRO_ALLOCATED | NPU_RRO_NPU_POSSIBLE,
        offsetof(struct npu_rro_lifetime, last_ticket), NPU_RRO_SESSION_MAGIC,
        NPU_RRO_BLOCKS, NPU_RRO_SESSIONS,
        NPU_RRO_PUBLICATIONS, NPU_RRO_MAX_EXTENTS
    };
    uint32_t command[4], previous = 0;

    _Static_assert(sizeof(struct npu_rro_plan) == 216, "complete plan");
    _Static_assert(sizeof(struct npu_rro_session) == 30588, "complete broker");
    write_exact(layout, sizeof(layout));
    require(!fflush(stdout), "flush layout");
    read_exact(&plan, sizeof(plan));
    while (1) {
        size_t bytes = fread(command, 1, sizeof(command), stdin);
        if (!bytes && feof(stdin))
            break;
        require(bytes == sizeof(command), "complete command");
        require(command[1] > previous, "strict oracle sequence");
        previous = command[1];
        request(command);
    }
    require(!ferror(stdin), "input error");
    return 0;
}
