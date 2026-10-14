/* Logical fixture only; earlier owners use their real portable APIs. */
#include "cold-pcie-tail.h"

extern struct npu_cold_rx_pcie_state npu_test_pcie_state;
extern struct npu_cold_rx_pcie_plan npu_test_pcie_plan;
extern uint32_t npu_test_pcie_metadata[3];
extern uint32_t npu_test_pcie_prepare(uint32_t), npu_test_pcie_begin(uint32_t, uint32_t);
extern uint32_t npu_test_pcie_reserve(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);
extern uint32_t npu_test_pcie_effect(uint32_t), npu_test_pcie_publish(uint32_t, uint32_t, uint32_t, uint32_t);
extern uint32_t npu_test_pcie_finish(uint32_t);
extern struct npu_cold_txdone_state npu_test_txdone_state;
extern struct npu_cold_rx_event_state npu_test_txdone_rx;
extern struct npu_cold_packet_state npu_test_txdone_packet;
extern struct npu_cold_txdone_plan npu_test_txdone_plan;
extern uint32_t npu_test_txdone_ready, npu_test_txdone_count;
extern int npu_test_txdone_read(void *, uint32_t, uint32_t, uint32_t *);

struct npu_cold_pcie_tail_state npu_test_tail_state;
struct npu_cold_pcie_tail_plan npu_test_tail_plan;
struct npu_cold_tx_state npu_test_tail_tx;
uint32_t npu_test_tail_cells[9], npu_test_tail_addresses[9];
uint32_t npu_test_tail_events[27], npu_test_tail_effects;
uint32_t npu_test_tail_reads, npu_test_tail_mutation, npu_test_tail_mutated;
uint32_t npu_test_tail_read_failure;
static uint32_t cookie = 0x314c5450;

static void clear(void *target, uint32_t bytes)
{
    volatile unsigned char *p = target;

    for (uint32_t i = 0; i < bytes; i++)
        p[i] = 0;
}

static void copy(void *target, const void *source, uint32_t bytes)
{
    volatile unsigned char *to = target;
    const volatile unsigned char *from = source;

    for (uint32_t i = 0; i < bytes; i++)
        to[i] = from[i];
}

static int prior_read(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value)
{
    int result = npu_test_txdone_read(opaque, address, bytes, value);

    npu_test_tail_reads++;
    if (npu_test_tail_mutation && !npu_test_tail_mutated && address == 0x3e9046fa) {
        if (npu_test_tail_mutation == 1) npu_test_tail_state.fault = 1;
        if (npu_test_tail_mutation == 2) npu_test_tail_state.published++;
        if (npu_test_tail_mutation == 3) npu_test_tail_tx.fault = 1;
        if (npu_test_tail_mutation == 4) npu_test_pcie_state.before ^= 1;
        npu_test_tail_mutated = 1;
    }
    return result;
}

static int tail_read(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value)
{
    static const uint32_t metadata[] = {0x3e90395c, 0x3e902a80, 0x3e904630, 0x3e902a9c, 0x3e902a90};
    static const uint32_t offsets[] = {0xd45a0, 0xd45b0, 0xd45c0, 0xa040, 0xd4590};

    if (opaque != &cookie || !value || address == npu_test_tail_read_failure)
        return 0;
    if (address == 0x3e902a7c && bytes == 2) {
        *value = npu_test_txdone_count & 65535;
        return 1;
    }
    if (bytes != 4)
        return 0;
    for (uint32_t i = 0; i < 5; i++)
        if (address == metadata[i]) {
            *value = i == 4 ? npu_test_pcie_metadata[1] : npu_test_tail_plan.tx.endpoint_base + offsets[i];
            return 1;
        }
    for (uint32_t i = 0; i < 9; i++)
        if (address == npu_test_tail_addresses[i]) {
            *value = npu_test_tail_cells[i];
            return 1;
        }
    return 0;
}

static struct npu_cold_pcie_tail_context context(void)
{
    const struct npu_cold_pcie_tail_context c = {
        .pcie = &npu_test_pcie_state, .tx = &npu_test_tail_tx,
        .prior = {.done = &npu_test_txdone_state, .rx = &npu_test_txdone_rx,
            .packets = &npu_test_txdone_packet, .read = prior_read, .opaque = &cookie,
            .rx_readback = npu_cold_rx_event_value(npu_test_txdone_plan.prior.ring),
            .ready = npu_test_txdone_ready & 255},
        .read = tail_read, .opaque = &cookie, .pcie_readback = npu_test_pcie_metadata[1]
    };

    npu_test_tail_reads = npu_test_tail_mutated = 0;
    return c;
}

struct npu_cold_pcie_tail_context npu_test_tail_context(void)
{
    return context();
}

uint32_t npu_test_tail_prepare(uint32_t hif2)
{
    struct npu_cold_tx_plan tx = {0};
    const struct npu_cold_txbuf_plan *bar;
    uint32_t readback[5], address, bytes, value, before;

    if (hif2 > 1 || npu_test_pcie_prepare(0) || npu_test_pcie_begin(1, 0) ||
        npu_test_pcie_reserve(NPU_COLD_RX_PCIE_METADATA, 4, 0x200d4590, 0xdeadbeef, 1) ||
        npu_test_pcie_effect(0x200d4590) ||
        npu_test_pcie_publish(NPU_COLD_RX_PCIE_METADATA, 4, 0x200d4590, 1) ||
        npu_test_pcie_finish(1))
        return 1;
    npu_cold_txdone_plan_copy(&npu_test_tail_plan.prior.prior, &npu_test_pcie_plan.prior);
    bar = &npu_test_tail_plan.prior.prior.prior.prior;
    tx.arena = bar->arena;
    tx.arena_bytes = NPU_COLD_TX_ARENA_BYTES;
    tx.endpoint_base = bar->endpoint_base;
    tx.endpoint_bytes = bar->endpoint_bytes;
    tx.host0 = tx.endpoint_base + 0xd4420;
    tx.token_before = 0x12345678;
    for (uint32_t i = 0; i < 4; i++) tx.register_before[i] = 0xabc10000 + i;
    clear(&npu_test_tail_tx, sizeof(npu_test_tail_tx));
    for (uint32_t stage = 0; stage < 3; stage++) {
        if (stage == 1) tx.host2 = tx.endpoint_base + 0xd4450 + hif2 * 0x4000;
        if (npu_cold_tx_begin(&npu_test_tail_tx, &tx, 1, stage)) return 2;
        for (uint32_t i = 0; i < (stage == 2 ? 1u : 5u); i++) {
            bytes = 4;
            before = value = 0;
            if (stage == 2) {
                address = 0x3e900bc0; value = 8192; before = tx.token_before;
            } else if (!i) {
                address = stage ? 0x3e9046fc : 0x3e904700;
                value = stage ? tx.host2 : tx.host0;
            } else if (i < 3) {
                address = i == 1 ? 0x3e903978 : 0x3e9021f4; bytes = 2;
            } else {
                address = (stage ? 0x1fc48030 : 0x1fc08030) + (i - 3) * 4;
                value = (tx.arena + (stage ? i == 3 ? 0x22020 : 0x4a040 : i == 3 ? 0 : 0x22020)) & 0x1fffffff;
                before = tx.register_before[stage * 2 + i - 3];
            }
            if (npu_cold_tx_reserve(&npu_test_tail_tx, &tx, 1, address, value, bytes, before) ||
                npu_cold_tx_publish(&npu_test_tail_tx, &tx, 1, address, bytes, value)) return 3;
            readback[i] = value;
        }
        if (npu_cold_tx_finish(&npu_test_tail_tx, &tx, 1, readback)) return 4;
    }
    copy(&npu_test_tail_plan.tx, &tx, sizeof(tx));
    clear(&npu_test_tail_state, sizeof(npu_test_tail_state));
    clear(npu_test_tail_events, sizeof(npu_test_tail_events));
    npu_test_tail_effects = npu_test_tail_reads = npu_test_tail_mutation = npu_test_tail_mutated = 0;
    npu_test_tail_read_failure = 0;
    npu_test_tail_addresses[0] = 0x3e902cf0;
    npu_test_tail_addresses[1] = tx.host0 + 0x168;
    npu_test_tail_addresses[2] = 0x3e903904;
    npu_test_tail_addresses[3] = tx.host2 + 0x118;
    for (uint32_t i = 0; i < 5; i++) {
        static const uint32_t offsets[] = {0xd45a8, 0xd45b8, 0xd45c8, 0xa048, 0xd4598};
        npu_test_tail_addresses[i + 4] = tx.endpoint_base + offsets[i];
    }
    for (uint32_t i = 0; i < 9; i++) npu_test_tail_cells[i] = 0xa5a50100 + i * 17;
    return 0;
}

uint32_t npu_test_tail_begin(uint32_t selector, uint32_t value, uint32_t epoch)
{
    struct npu_cold_pcie_tail_context c = context();
    return npu_cold_pcie_tail_begin(&npu_test_tail_state, &npu_test_tail_plan, epoch, &c, selector, value);
}

uint32_t npu_test_tail_reserve(uint32_t address, uint32_t bytes, uint32_t value, uint32_t before)
{
    struct npu_cold_pcie_tail_context c = context();
    return npu_cold_pcie_tail_reserve(&npu_test_tail_state, &npu_test_tail_plan, 1, &c, address, bytes, value, before);
}

uint32_t npu_test_tail_effect(uint32_t index, uint32_t value)
{
    if (index >= 9 || npu_test_tail_effects >= 9) return 1;
    npu_test_tail_cells[index] = value;
    npu_test_tail_events[npu_test_tail_effects * 3] = npu_test_tail_addresses[index];
    npu_test_tail_events[npu_test_tail_effects * 3 + 1] = 4;
    npu_test_tail_events[npu_test_tail_effects * 3 + 2] = value;
    npu_test_tail_effects++;
    return 0;
}

uint32_t npu_test_tail_publish(uint32_t address, uint32_t bytes, uint32_t value)
{
    struct npu_cold_pcie_tail_context c = context();
    return npu_cold_pcie_tail_publish(&npu_test_tail_state, &npu_test_tail_plan, 1, &c, address, bytes, value);
}

uint32_t npu_test_tail_finish(void)
{
    struct npu_cold_pcie_tail_context c = context();
    return npu_cold_pcie_tail_finish(&npu_test_tail_state, &npu_test_tail_plan, 1, &c);
}

uint32_t npu_test_tail_live(void)
{
    struct npu_cold_pcie_tail_context c = context();
    return npu_cold_pcie_tail_live(&npu_test_tail_state, &npu_test_tail_plan, 1, &c);
}
