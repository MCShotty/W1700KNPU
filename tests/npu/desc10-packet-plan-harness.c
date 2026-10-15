/* Extracted binding logic with explicit valid-prior/readback/allocation stubs. */
#include <stdint.h>
#include "cold-setup.h"

struct npu_cold_setup npu_emulation_cold_setup_state;
struct npu_cold_txdone_state npu_emulation_desc10_state;
struct npu_cold_packet_state npu_emulation_packet_state;
struct npu_cold_packet_plan npu_emulation_packet_plan;
struct npu_cold_rx_event_state npu_emulation_rx_event_state;
struct npu_admission npu_emulation_admission_state;
struct npu_barrier npu_emulation_barrier_state;
uint32_t npu_emulation_callback_guarded, npu_emulation_desc10_running;
static struct npu_cold_txdone_plan plan;
static uint32_t held_setup[sizeof(struct npu_cold_setup) / 4];
static uint32_t fixture_status, mutation, mutation_point;
uint32_t npu_test_observed[8];

#define SETUP (&npu_emulation_cold_setup_state)
#define OWNER (&npu_emulation_desc10_state)
#define PKT (&npu_emulation_packet_state)
#define RX (&npu_emulation_rx_event_state)

static void mutate(uint32_t point)
{
    if (point == mutation_point) {
        if (mutation == 1)
            npu_emulation_packet_plan.packet_base += 2048;
        if (mutation == 2)
            npu_emulation_packet_plan.packet_bytes -= 2048;
    }
}

static int allocations_live(void) { return 1; }
static uint32_t word(uint32_t address) { (void)address; return 1; }
static uint32_t read(uint32_t address, uint32_t bytes) { (void)address; (void)bytes; return 1; }
int npu_emulation_rx_event_prior_live(uint32_t count, uint32_t full)
{ (void)count; (void)full; mutate(1); return 1; }
int npu_emulation_rx_event_prior_live_done(uint32_t count)
{ (void)count; mutate(3); return 1; }
int npu_cold_txdone_packets_live(const struct npu_cold_txdone_state *s,
    const struct npu_cold_txdone_plan *p, uint32_t epoch, const struct npu_cold_packet_state *pkt)
{ (void)s; (void)p; (void)epoch; (void)pkt; mutate(2); return 1; }
int npu_cold_txdone_plan_equal(const struct npu_cold_txdone_plan *a, const struct npu_cold_txdone_plan *b)
{ (void)a; (void)b; return 1; }
int npu_cold_txdone_live(const struct npu_cold_txdone_state *s,
    const struct npu_cold_txdone_plan *p, uint32_t epoch, const struct npu_cold_rx_event_state *rx,
    uint32_t rb, const struct npu_cold_packet_state *pkt, uint32_t ready)
{ (void)s; (void)p; (void)epoch; (void)rx; (void)rb; (void)pkt; (void)ready; return 1; }
int npu_emulation_desc10_read(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value)
{ (void)opaque; (void)address; (void)bytes; (void)value; return 0; }
int npu_cold_txdone_memory_live(const struct npu_cold_txdone_state *s,
    const struct npu_cold_txdone_plan *p, uint32_t epoch, const struct npu_cold_rx_event_state *rx,
    uint32_t rb, const struct npu_cold_packet_state *pkt, uint32_t ready,
    npu_cold_txdone_read_fn reader, void *opaque)
{
    (void)s; (void)p; (void)epoch; (void)rx; (void)rb; (void)pkt;
    (void)ready; (void)reader; (void)opaque;
    mutate(4);
    return 1;
}
static uint32_t fail(void)
{
    OWNER->fault = npu_emulation_admission_state.fault = npu_emulation_barrier_state.fault = 1;
    return 0;
}

#include "desc10-packet-plan.inc"

static void zero(void *destination, uint32_t bytes)
{
    volatile unsigned char *p = destination;
    for (uint32_t i = 0; i < bytes; i++) p[i] = 0;
}

uint32_t npu_test_plan_case(uint32_t phase, uint32_t kind, uint32_t point, uint32_t irq)
{
    zero(SETUP, sizeof(*SETUP));
    zero(OWNER, sizeof(*OWNER));
    zero(&plan, sizeof(plan));
    zero(&npu_emulation_admission_state, sizeof(npu_emulation_admission_state));
    zero(&npu_emulation_barrier_state, sizeof(npu_emulation_barrier_state));
    plan.prior.prior.boot.region[NPU_BOOT_PKT].base = 0x8a000000;
    plan.prior.prior.boot.region[NPU_BOOT_PKT].bytes = 0x02000000;
    plan.prior.prior.endpoint_base = 0x20000000;
    npu_emulation_packet_plan.packet_base = 0x8a000000;
    npu_emulation_packet_plan.packet_bytes = 0x02000000;
    SETUP->inflight = 1;
    SETUP->sequence = 57;
    SETUP->command.header = 0x1a;
    SETUP->command.api = 1;
    SETUP->command.value = 512;
    SETUP->rx_event_steps = SETUP->prior_rx_event_steps = 1;
    for (uint32_t i = 0; i < sizeof(held_setup) / 4; i++)
        held_setup[i] = ((const uint32_t *)SETUP)[i];
    OWNER->magic = NPU_COLD_TXDONE_MAGIC;
    OWNER->committed = OWNER->published = NPU_COLD_TXDONE_STORES - 2;
    OWNER->claims_committed = OWNER->claims_published = 512;
    OWNER->skb_reserved = 1;
    npu_emulation_desc10_running = npu_emulation_callback_guarded = phase != 2;
    if (phase == 2) {
        SETUP->sequence++;
        SETUP->command.api = 0;
        SETUP->command.value = 0x200d4590;
        SETUP->rx_event_steps = SETUP->prior_rx_event_steps = 2;
    }
    mutation = kind;
    mutation_point = point;
    fixture_status = irq;
#ifdef __riscv
    __asm__ volatile ("csrw mstatus, %0" :: "r"(irq) : "memory");
#endif
    if (!point) mutate(0);
    uint32_t result = phase == 0 ? npu_emulation_desc10_ready() :
        phase == 1 ? (uint32_t)context(1) : (uint32_t)npu_emulation_desc10_prior_live(&plan);
    npu_test_observed[0] = result;
    npu_test_observed[1] = npu_emulation_packet_plan.packet_base;
    npu_test_observed[2] = npu_emulation_packet_plan.packet_bytes;
    npu_test_observed[3] = OWNER->fault;
    npu_test_observed[4] = npu_emulation_admission_state.fault;
    npu_test_observed[5] = npu_emulation_barrier_state.fault;
    npu_test_observed[6] = OWNER->committed;
    npu_test_observed[7] = OWNER->published;
    return result;
}
