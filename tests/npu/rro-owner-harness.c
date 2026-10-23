#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "rro-lifetime.h"
#include "rro-source-geometry.h"

_Static_assert(MT7996_RRO_ADDR_ELEM_LEN == NPU_RRO_BLOCKS, "complete block count");
_Static_assert(MT7996_RRO_MAX_SESSION + 1 == NPU_RRO_SESSIONS, "special session included");
_Static_assert(MT7996_RRO_WINDOW_MAX_SIZE * sizeof(struct mt7996_wed_rro_addr) == NPU_RRO_BLOCK_BYTES, "full block extent");
_Static_assert(MT7996_RRO_WINDOW_MAX_LEN * sizeof(struct mt7996_wed_rro_addr) == NPU_RRO_SESSION_BYTES, "full session extent");
_Static_assert(MT7996_RRO_BA_BITMAP_CR_SIZE == NPU_RRO_BLOCK_BYTES, "BA extent");
_Static_assert(MT7996_RRO_MSDU_PG_SIZE_PER_CR == NPU_RRO_BLOCK_BYTES, "MSDU extent");
_Static_assert(sizeof(struct mt7996_rro_queue_regs_emi) == 16, "EMI extent");
_Static_assert(MT7996_RRO_BA_BITMAP_LEN + MT7996_RRO_ADDR_ELEM_LEN + MT7996_RRO_MSDU_PG_CR_CNT + 1 == NPU_RRO_MAX_EXTENTS, "V3 allocations");
_Static_assert(MT7996_RRO_ADDR_ELEM_LEN + MT7996_RRO_MSDU_PG_CR_CNT + 3 == NPU_RRO_MAX_EXTENTS, "V3.1 allocations");

static struct npu_rro_lifetime state, before, baseline;
static struct npu_rro_plan plan, different;
static FILE *capture;
static unsigned cases, frames;

static void unchanged(void) { assert(!memcmp(&state, &before, sizeof(state))); }
static void remember(void) { before = state; }

static void initialize(uint32_t profile)
{
    memset(&state, 0, sizeof(state));
    memset(&plan, 0, sizeof(plan));
    plan.identity = (struct npu_rro_identity){1, 1, 2, 1, 3, 1, 4, 1, 1};
    plan.profile = profile;
    for (uint32_t i = 0; i < 8; i++)
        plan.mailbox[i] = (struct npu_rro_span){0x90000000u + i * 0x40000u, 0x1000};
    for (uint32_t i = 0; i < 6; i++) {
        plan.tx[i].address = 0x91000000u + i * 0x40000u;
        plan.tx[i].bytes = i < 2 ? 0x20000 : 0x40000;
        plan.native[i] = (struct npu_rro_span){0x84000000u + i * 0x100000u, 0x100000};
    }
    plan.rx_event = (struct npu_rro_span){0x92000000, 8192};
    plan.bar = (struct npu_rro_span){0x20000000, 0x100000};
    assert(!npu_rro_open(&state, &plan));
}

static struct npu_rro_extent extent(uint32_t ordinal)
{
    struct npu_rro_extent out;
    assert(!npu_rro_extent_geometry(plan.profile, ordinal, &out));
    out.cpu_lo = 0x10000000 + ordinal * 0x20000;
    out.cpu_hi = 1;
    if (out.role == NPU_RRO_ELEMENT)
        out.dma_lo = 0x88000000 + out.index * 65536;
    else if (out.role == NPU_RRO_SESSION)
        out.dma_lo = 0x88801000;
    else if (out.role == NPU_RRO_BA)
        out.dma_lo = 0x88900000 + out.index * 65536;
    else if (out.role == NPU_RRO_MSDU)
        out.dma_lo = 0x88a00000 + out.index * 65536;
    else
        out.dma_lo = 0x88b00000 + (out.role == NPU_RRO_EMI_DMA ? 0x1000 : 0);
    return out;
}

static void save_frame(const struct npu_rro_command *command)
{
    uint32_t words[6] = {0x10 | command->selector, 24};
    memcpy(words + 2, command->words, sizeof(command->words));
    assert(fwrite(words, sizeof(words), 1, capture) == 1);
    frames++;
}

/* Build via the actual interleaved allocation/publication ordering. Addresses
 * and CPU identities are fixture metadata, not allocated or mapped DMA memory. */
static void build(uint32_t profile, uint32_t allocations, int fail_at, int failure, int save)
{
    initialize(profile);
    for (uint32_t i = 0; i < allocations; i++) {
        struct npu_rro_extent item = extent(i);
        struct npu_rro_command command;
        uint32_t ordinal, ticket;
        assert(!npu_rro_enroll(&state, &plan, &item));
        assert(!memcmp(&state.extents[i], &item, sizeof(item)));
        if (item.role != NPU_RRO_ELEMENT && item.role != NPU_RRO_SESSION)
            continue;
        ordinal = item.role == NPU_RRO_SESSION ? 128 : item.index;
        assert(!npu_rro_publish_begin(&state, &plan, ordinal, &ticket, &command));
        assert(command.selector == (ordinal == 128 ? 1u : 0u));
        assert(command.words[0] == (ordinal == 128 ? 0u : ordinal));
        assert(command.words[1] == item.dma_lo && !command.words[2] && !command.words[3]);
        assert(ticket == ordinal + 1 && state.exposure[i] == 3 && "publication exposure must precede command output");
        if (save)
            save_frame(&command);
        if ((int)ordinal == fail_at) {
            assert(npu_rro_publish_complete(&state, &plan, ordinal, ticket, failure) == NPU_RRO_HELD);
            return;
        }
        assert(!npu_rro_publish_complete(&state, &plan, ordinal, ticket, 0));
        assert(state.exposure[i] == 7);
    }
}

static void close_recorded(uint32_t epoch, uint32_t allocated)
{
    struct npu_rro_retirement out;
    uint32_t ticket, again;
    assert(!npu_rro_retirement_begin(&state, &plan, epoch, &ticket));
    remember();
    assert(npu_rro_retirement_record(&state, &plan, ticket, epoch, 0) == NPU_RRO_ORDER && "retirement observations require CPU join");
    unchanged();
    assert(npu_rro_retirement_join(&state, &plan, ticket + 1, epoch) == NPU_RRO_STALE);
    unchanged();
    assert(!npu_rro_retirement_join(&state, &plan, ticket, epoch));
    for (uint32_t i = 0; i < 5; i++) {
        remember();
        assert(npu_rro_retirement_record(&state, &plan, ticket, epoch + 1, i) == NPU_RRO_STALE);
        unchanged();
        assert(!npu_rro_retirement_record(&state, &plan, ticket, epoch, i));
        assert(state.phase == (i == 4 ? NPU_RRO_DRAIN_RECORDED : NPU_RRO_CLOSING));
    }
    remember();
    assert(npu_rro_retirement_record(&state, &plan, ticket, epoch, 5) == NPU_RRO_ARGUMENT);
    unchanged();
    assert(npu_rro_retirement_begin(&state, &plan, epoch, &again) == NPU_RRO_DUPLICATE && again == ticket);
    unchanged();
    assert(!npu_rro_retirement_snapshot(&state, &plan, &out));
    assert(out.allocated == allocated && state.allocated == allocated);
    assert(out.phase == NPU_RRO_DRAIN_RECORDED && out.cpu_joined == 1);
    assert(!memcmp(state.extents, before.extents, sizeof(state.extents)));
    assert(npu_rro_open(&state, &plan) == NPU_RRO_REINITIALIZE);
    unchanged();
}

static void reset(uint32_t session, uint32_t generation, int save)
{
    struct npu_rro_command command;
    uint32_t ticket, duplicate;
    assert(!npu_rro_reset_queue(&state, &plan, session, generation, &ticket));
    remember();
    assert(npu_rro_reset_queue(&state, &plan, session, generation, &duplicate) == NPU_RRO_DUPLICATE);
    assert(duplicate == ticket);
    unchanged();
    assert(npu_rro_reset_npu_complete(&state, &plan, session, generation, ticket, 0) == NPU_RRO_ORDER);
    unchanged();
    assert(!npu_rro_reset_npu_begin(&state, &plan, session, generation, ticket, &command));
    assert(command.selector == 3 && command.words[0] == session);
    assert(!command.words[1] && !command.words[2] && !command.words[3]);
    if (save)
        save_frame(&command);
    remember();
    assert(npu_rro_reset_mcu_begin(&state, &plan, session, generation, ticket) == NPU_RRO_ORDER);
    unchanged();
    assert(npu_rro_reset_npu_complete(&state, &plan, session, generation, ticket + 1, 0) == NPU_RRO_STALE && "reset completion requires exact transport ticket");
    unchanged();
    assert(!npu_rro_reset_npu_complete(&state, &plan, session, generation, ticket, 0));
    remember();
    assert(npu_rro_reset_npu_complete(&state, &plan, session, generation, ticket, 0) == NPU_RRO_DUPLICATE);
    unchanged();
    assert(!npu_rro_reset_mcu_begin(&state, &plan, session, generation, ticket));
    assert(!npu_rro_reset_mcu_complete(&state, &plan, session, generation, ticket, 0));
    assert(state.resets[session].generation == generation + 1);
    remember();
    duplicate = 0xdeadbeef;
    assert(npu_rro_reset_queue(&state, &plan, session, generation, &duplicate) == NPU_RRO_STALE);
    assert(duplicate == 0xdeadbeef);
    unchanged();
    assert(npu_rro_reset_mcu_complete(&state, &plan, session, generation, ticket, 0) == NPU_RRO_DUPLICATE);
    unchanged();
}

static void report(const char *group, uint32_t profile, unsigned start)
{
    printf("{\"group\":\"%s\",\"profile\":%u,\"cases\":%u,\"passed\":true}\n", group, profile, cases - start);
}

static void profile(uint32_t mode)
{
    const uint32_t sessions[] = {0, 7, 8, 1023, 1024};
    const int errors[] = {-5, -110};
    uint32_t count = npu_rro_extent_count(mode);
    unsigned start = cases;
    build(mode, count, -1, 0, mode == 0);
    assert(!npu_rro_hardware_begin(&state, &plan));
    for (uint32_t i = 0; i < 5; i++)
        reset(sessions[i], 1, mode == 0);
    close_recorded(2, count);
    cases++;
    report("complete-geometry-and-wire", mode, start);

    start = cases;
    for (uint32_t stop = 0; stop <= count; stop++) {
        build(mode, stop, -1, 0, 0);
        npu_rro_fault(&state, 0x100);
        assert(state.allocated == stop && state.error == 0x100);
        close_recorded(1, stop);
        assert(state.error == 0x100);
        cases++;
    }
    report("every-allocation-prefix", mode, start);

    start = cases;
    for (uint32_t ordinal = 0; ordinal < 129; ordinal++) {
        for (uint32_t error = 0; error < 2; error++) {
            for (uint32_t late = 0; late < 2; late++) {
                struct npu_rro_retirement out;
                uint32_t ticket = ordinal + 1;
                build(mode, count, (int)ordinal, errors[error], 0);
                assert(state.confirmed == ordinal && state.publication[ordinal].ticket == ticket);
                assert(state.publication[ordinal].error == (uint32_t)errors[error]);
                remember();
                assert(npu_rro_publish_complete(&state, &plan, ordinal, ticket + 1, 0) == NPU_RRO_STALE);
                unchanged();
                assert(npu_rro_publish_complete(&state, &plan, ordinal, ticket, -12) == NPU_RRO_HELD);
                assert(state.publication[ordinal].error == (uint32_t)errors[error]);
                if (late)
                    assert(!npu_rro_publish_complete(&state, &plan, ordinal, ticket, 0));
                assert(state.error == NPU_RRO_PUBLICATION_FAILED);
                assert(!npu_rro_retirement_snapshot(&state, &plan, &out));
                assert(out.possible_publications == !late);
                assert(out.confirmed_publications == ordinal + late);
                close_recorded(1, state.allocated);
                remember();
                assert(npu_rro_publish_complete(&state, &plan, ordinal, ticket, 0) == NPU_RRO_STALE);
                unchanged();
                cases++;
            }
        }
    }
    report("every-ambiguous-publication-prefix", mode, start);

    start = cases;
    build(mode, count, -1, 0, 0);
    assert(!npu_rro_hardware_begin(&state, &plan));
    baseline = state;
    for (uint32_t session = 0; session < NPU_RRO_SESSIONS; session++) {
        reset(session, 1, 0);
        cases++;
    }
    reset(0, 2, 0);
    cases++;
    report("every-session-reset-generation-and-duplicates", mode, start);

    start = cases;
    state = baseline;
    uint32_t first, second, queued;
    struct npu_rro_command credit_command;
    assert(!npu_rro_reset_queue(&state, &plan, 0, 1, &first));
    assert(!npu_rro_reset_queue(&state, &plan, 1, 1, &second));
    assert(!npu_rro_reset_queue(&state, &plan, 2, 1, &queued));
    assert(!npu_rro_reset_npu_begin(&state, &plan, 0, 1, first, &credit_command));
    remember();
    assert(npu_rro_reset_npu_begin(&state, &plan, 1, 1, second, &credit_command) == NPU_RRO_BUSY);
    assert(credit_command.words[0] == 0);
    unchanged();
    assert(!npu_rro_reset_npu_complete(&state, &plan, 0, 1, first, 0));
    assert(!npu_rro_reset_mcu_begin(&state, &plan, 0, 1, first));
    assert(!npu_rro_reset_npu_begin(&state, &plan, 1, 1, second, &credit_command));
    assert(!npu_rro_reset_npu_complete(&state, &plan, 1, 1, second, 0));
    remember();
    assert(npu_rro_reset_mcu_begin(&state, &plan, 1, 1, second) == NPU_RRO_BUSY);
    unchanged();
    assert(!npu_rro_reset_mcu_complete(&state, &plan, 0, 1, first, 0));
    assert(!npu_rro_reset_mcu_begin(&state, &plan, 1, 1, second));
    assert(!npu_rro_reset_mcu_complete(&state, &plan, 1, 1, second, 0));
    assert(state.resets[2].ticket == queued && state.resets[2].phase == NPU_RRO_RESET_QUEUED);
    close_recorded(2, count);
    cases++;
    report("single-NPU-and-MCU-inflight-credit", mode, start);

    start = cases;
    for (uint32_t i = 0; i < 5; i++) {
        for (uint32_t mcu = 0; mcu < 2; mcu++) {
            for (uint32_t err = 0; err < 2; err++) {
                for (uint32_t late = 0; late < 2; late++) {
                    struct npu_rro_command command;
                    struct npu_rro_retirement out;
                    uint32_t ticket, session = sessions[i];
                    state = baseline;
                    assert(!npu_rro_reset_queue(&state, &plan, session, 1, &ticket));
                    assert(!npu_rro_reset_npu_begin(&state, &plan, session, 1, ticket, &command));
                    if (mcu) {
                        assert(!npu_rro_reset_npu_complete(&state, &plan, session, 1, ticket, 0));
                        assert(!npu_rro_reset_mcu_begin(&state, &plan, session, 1, ticket));
                        assert(npu_rro_reset_mcu_complete(&state, &plan, session, 1, ticket, errors[err]) == NPU_RRO_HELD);
                        if (late)
                            assert(!npu_rro_reset_mcu_complete(&state, &plan, session, 1, ticket, 0));
                    } else {
                        assert(npu_rro_reset_npu_complete(&state, &plan, session, 1, ticket, errors[err]) == NPU_RRO_HELD);
                        if (late)
                            assert(!npu_rro_reset_npu_complete(&state, &plan, session, 1, ticket, 0));
                    }
                    assert(state.error == (mcu ? NPU_RRO_MCU_RESET_FAILED : NPU_RRO_NPU_RESET_FAILED));
                    assert(!npu_rro_retirement_snapshot(&state, &plan, &out));
                    assert(out.possible_npu_resets == (!mcu && !late));
                    assert(out.possible_mcu_resets == (mcu && !late));
                    assert(state.resets[session].ticket == ticket);
                    close_recorded(2, count);
                    remember();
                    assert(npu_rro_reset_npu_complete(&state, &plan, session, 1, ticket, 0) == NPU_RRO_STALE);
                    unchanged();
                    cases++;
                }
            }
        }
    }
    report("reset-NPU-MCU-errors-late-and-retirement", mode, start);

    start = cases;
    for (uint32_t mask = 0; mask < 32; mask++) {
        struct npu_rro_retirement out;
        uint32_t ticket;
        state = baseline;
        assert(!npu_rro_retirement_begin(&state, &plan, 2, &ticket));
        assert(!npu_rro_retirement_join(&state, &plan, ticket, 2));
        for (uint32_t domain = 0; domain < 5; domain++)
            if (mask & (1u << domain))
                assert(!npu_rro_retirement_record(&state, &plan, ticket, 2, domain));
        assert(!npu_rro_retirement_snapshot(&state, &plan, &out));
        assert(out.phase == (mask == 31 ? NPU_RRO_DRAIN_RECORDED : NPU_RRO_CLOSING));
        assert(state.allocated == count);
        assert(!memcmp(state.extents, baseline.extents, sizeof(state.extents)));
        cases++;
    }
    report("every-retirement-domain-subset-retains-extents", mode, start);
}

static void invalid(void)
{
    struct npu_rro_extent item;
    struct npu_rro_command command;
    struct npu_rro_retirement out;
    uint32_t ticket;
    unsigned start = cases;
    initialize(0);
    item = extent(0);
    item.dma_hi = 1;
    remember();
    assert(npu_rro_enroll(&state, &plan, &item) == NPU_RRO_ARGUMENT);
    unchanged();
    item = extent(0);
    item.cpu_lo = 0xfffffff0; item.cpu_hi = UINT32_MAX;
    assert(npu_rro_enroll(&state, &plan, &item) == NPU_RRO_ARGUMENT);
    unchanged();
    item = extent(0);
    item.dma_lo = plan.mailbox[0].address ^ 0x40000000u;
    assert(npu_rro_enroll(&state, &plan, &item) == NPU_RRO_ARGUMENT);
    unchanged();
    item = extent(0);
    assert(!npu_rro_enroll(&state, &plan, &item));
    struct npu_rro_extent second = extent(1);
    second.dma_lo = item.dma_lo ^ 0x40000000u;
    remember();
    assert(npu_rro_enroll(&state, &plan, &second) == NPU_RRO_ARGUMENT);
    unchanged();
    second = extent(1); second.cpu_lo = item.cpu_lo;
    assert(npu_rro_enroll(&state, &plan, &second) == NPU_RRO_ARGUMENT);
    unchanged();
    different = plan; different.identity.nonce_lo++;
    assert(npu_rro_enroll(&state, &different, &second) == NPU_RRO_STALE);
    unchanged();
    assert(npu_rro_publish_begin(&state, &plan, 0, &ticket, &command) == NPU_RRO_ORDER);
    unchanged();
    assert(npu_rro_retirement_snapshot(&state, &plan, (void *)&state) == NPU_RRO_ARGUMENT);
    unchanged();
    assert(npu_rro_retirement_begin(&state, &plan, 3, &ticket) == NPU_RRO_ARGUMENT);
    unchanged();
    cases += 9;

    build(0, 139, -1, 0, 0);
    assert(!npu_rro_hardware_begin(&state, &plan));
    remember();
    for (uint32_t bad = 1025; bad <= 65535; bad += 64510) {
        assert(npu_rro_reset_queue(&state, &plan, bad, 1, &ticket) == NPU_RRO_ARGUMENT);
        unchanged();
        cases++;
    }
    assert(npu_rro_reset_queue(&state, &plan, 0, 1, (void *)&plan) == NPU_RRO_ARGUMENT);
    unchanged();
    cases++;
    state.resets[0] = (struct npu_rro_reset){1, 1, UINT32_MAX - 1, NPU_RRO_RESET_QUEUED, 0, 0};
    state.last_ticket = UINT32_MAX - 1;
    remember();
    assert(npu_rro_reset_queue(&state, &plan, 1, 1, &ticket) == NPU_RRO_EXHAUSTED);
    unchanged();
    assert(!npu_rro_retirement_begin(&state, &plan, 2, &ticket) && ticket == UINT32_MAX);
    assert(!npu_rro_retirement_snapshot(&state, &plan, &out) && out.queued_resets == 1);
    cases++;
    report("invalid-identities-addresses-aliases-bounds-and-counter-boundary", 0, start);
}

int main(int argc, char **argv)
{
    assert(argc == 2 && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__);
    capture = fopen(argv[1], "wb");
    assert(capture);
    for (uint32_t i = 0; i < 3; i++)
        profile(i);
    invalid();
    assert(frames == 134 && !fclose(capture));
    printf("{\"total_cases\":%u,\"captured_frames\":%u,\"passed\":true,\"hardware\":false}\n", cases, frames);
    return 0;
}
