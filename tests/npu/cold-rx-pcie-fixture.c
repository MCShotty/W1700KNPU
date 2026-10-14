/* Logical memory fixture; no original instructions, native locks or DMA proof. */
#include "cold-rx-pcie.h"

extern struct npu_cold_txdone_state npu_test_txdone_state;
extern struct npu_cold_txdone_plan npu_test_txdone_plan;
extern struct npu_cold_rx_event_state npu_test_txdone_rx;
extern struct npu_cold_packet_state npu_test_txdone_packet;
extern uint32_t npu_test_txdone_ready;
extern uint32_t npu_test_txdone_fresh(uint32_t);
extern uint32_t npu_test_txdone_begin(void);
extern uint32_t npu_test_txdone_run(uint32_t, uint32_t);
extern uint32_t npu_test_txdone_finish(void);
extern int npu_test_txdone_read(void *, uint32_t, uint32_t, uint32_t *);

#define READS 20998u
struct npu_cold_rx_pcie_state npu_test_pcie_state;
struct npu_cold_rx_pcie_plan npu_test_pcie_plan;
uint32_t npu_test_pcie_metadata[3], npu_test_pcie_effects;
uint32_t npu_test_pcie_reads[READS * 3], npu_test_pcie_read_count;
uint32_t npu_test_pcie_fault_address, npu_test_pcie_read_mode;
static uint32_t reader_cookie = 0x31454152u;

static int reader(void *opaque, uint32_t address, uint32_t bytes, uint32_t *value)
{
    if (opaque != &reader_cookie || npu_test_pcie_read_count >= READS ||
        !npu_test_txdone_read(opaque, address, bytes, value))
        return 0;
    if (address == npu_test_pcie_fault_address) {
        if (npu_test_pcie_read_mode == 1)
            return 0;
        if (npu_test_pcie_read_mode == 2)
            *value ^= 1;
        if (npu_test_pcie_read_mode == 3)
            npu_test_txdone_state.fault = 1;
    }
    npu_test_pcie_reads[npu_test_pcie_read_count * 3] = address;
    npu_test_pcie_reads[npu_test_pcie_read_count * 3 + 1] = bytes;
    npu_test_pcie_reads[npu_test_pcie_read_count * 3 + 2] = *value;
    npu_test_pcie_read_count++;
    return 1;
}

static struct npu_cold_rx_pcie_context context(void)
{
    const struct npu_cold_rx_pcie_context c = {
        .done = &npu_test_txdone_state, .rx = &npu_test_txdone_rx,
        .packets = &npu_test_txdone_packet, .read = reader, .opaque = &reader_cookie,
        .rx_readback = npu_cold_rx_event_value(npu_test_txdone_plan.prior.ring),
        .ready = npu_test_txdone_ready & 255
    };

    npu_test_pcie_read_count = 0;
    return c;
}

uint32_t npu_test_pcie_reset(void)
{
    volatile uint32_t *state = (volatile void *)&npu_test_pcie_state;

    for (uint32_t i = 0; i < sizeof(npu_test_pcie_state) / 4; i++)
        state[i] = 0;
    npu_cold_txdone_plan_copy(&npu_test_pcie_plan.prior, &npu_test_txdone_plan);
    npu_test_pcie_metadata[0] = 0x12345678;
    npu_test_pcie_metadata[1] = 0xdeadbeef;
    npu_test_pcie_metadata[2] = 0x87654321;
    npu_test_pcie_effects = npu_test_pcie_fault_address = npu_test_pcie_read_mode = 0;
    return 0;
}

uint32_t npu_test_pcie_prepare(uint32_t alias)
{
    if (npu_test_txdone_fresh(alias) || npu_test_txdone_begin() ||
        npu_test_txdone_run(NPU_COLD_TXDONE_STORES, 0) || npu_test_txdone_finish())
        return 1;
    return npu_test_pcie_reset();
}

uint32_t npu_test_pcie_begin(uint32_t epoch, uint32_t missing)
{
    struct npu_cold_rx_pcie_context c = context();

    if (missing & 8) c.read = 0;
    if (missing & 16) c.done = 0;
    if (missing & 32) c.rx = 0;
    if (missing & 64) c.packets = 0;
    if (missing & 128) c.opaque = 0;
    if (missing & 256) c.ready = 0;
    return npu_cold_rx_pcie_begin(missing & 1 ? 0 : &npu_test_pcie_state,
        missing & 2 ? 0 : &npu_test_pcie_plan, epoch,
        missing & 4 ? 0 : &c, npu_test_pcie_metadata[1]);
}

uint32_t npu_test_pcie_reserve(uint32_t address, uint32_t bytes,
                              uint32_t value, uint32_t before, uint32_t epoch)
{
    struct npu_cold_rx_pcie_context c = context();

    return npu_cold_rx_pcie_reserve(&npu_test_pcie_state, &npu_test_pcie_plan,
        epoch, &c, address, bytes, value, before);
}

uint32_t npu_test_pcie_effect(uint32_t value)
{
    npu_test_pcie_metadata[1] = value;
    npu_test_pcie_effects++;
    return 0;
}

uint32_t npu_test_pcie_publish(uint32_t address, uint32_t bytes, uint32_t readback, uint32_t epoch)
{
    struct npu_cold_rx_pcie_context c = context();

    return npu_cold_rx_pcie_publish(&npu_test_pcie_state, &npu_test_pcie_plan,
        epoch, &c, address, bytes, readback);
}

uint32_t npu_test_pcie_finish(uint32_t epoch)
{
    struct npu_cold_rx_pcie_context c = context();

    return npu_cold_rx_pcie_finish(&npu_test_pcie_state, &npu_test_pcie_plan,
        epoch, &c, npu_test_pcie_metadata[1]);
}

uint32_t npu_test_pcie_live(uint32_t epoch)
{
    struct npu_cold_rx_pcie_context c = context();

    return npu_cold_rx_pcie_live(&npu_test_pcie_state, &npu_test_pcie_plan,
        epoch, &c, npu_test_pcie_metadata[1]);
}

uint32_t npu_test_pcie_memory_live(uint32_t epoch)
{
    struct npu_cold_rx_pcie_context c = context();

    return npu_cold_txdone_memory_live(c.done, &npu_test_pcie_plan.prior,
        epoch, c.rx, c.rx_readback, c.packets, c.ready, c.read, c.opaque);
}

#ifdef NPU_PCIE_SANITIZER
#include <assert.h>
int main(void)
{
    for (uint32_t alias = 0; alias < 3; alias++) {
        assert(!npu_test_pcie_prepare(alias));
        assert(npu_test_pcie_memory_live(1));
        assert(!npu_test_pcie_begin(1, 0));
        assert(!npu_test_pcie_reserve(NPU_COLD_RX_PCIE_METADATA, 4, 0x200d4590, 0xdeadbeef, 1));
        assert(!npu_test_pcie_effect(0x200d4590));
        assert(!npu_test_pcie_publish(NPU_COLD_RX_PCIE_METADATA, 4, 0x200d4590, 1));
        assert(!npu_test_pcie_finish(1));
        assert(npu_test_pcie_live(1));
        assert(npu_test_pcie_metadata[0] == 0x12345678 && npu_test_pcie_metadata[2] == 0x87654321);
        assert(npu_test_pcie_begin(1, 0));
        assert(npu_test_pcie_state.fault && npu_test_pcie_state.committed == 1);
    }
    return 0;
}
#endif
