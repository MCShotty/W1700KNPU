/* Linux/framework/provider boundaries are models. No firmware selector runs. */
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

typedef uint32_t u32;
#define BIT(n) (1u << (n))
#define GENMASK(high, low) ((UINT32_MAX << (low)) & (UINT32_MAX >> (31 - (high))))
#define FIELD_GET(mask, value) (((value) & (mask)) >> __builtin_ctz(mask))
#define FIELD_PREP(mask, value) (((u32)(value) << __builtin_ctz(mask)) & (mask))
#define READ_ONCE(value) (value)
#define WRITE_ONCE(target, value) ((target) = (value))
#define container_of(pointer, type, member) ((type *)((char *)(pointer) - offsetof(type, member)))
#define GFP_KERNEL 0
#define MT76_RESET 0
#define MT76_MCU_RESET 1
#define MT76_HWRRO_V3 3
#define MT_BAND0 0
#define MT_BAND1 1
#define MT_BAND2 2
#define MT_RXQ_NPU0 10
#define MT_RXQ_NPU1 11
#define MT_RXQ_MAIN_WA 0
#define MT_RXQ_BAND1_WA 1
#define MT_RXQ_TXFREE_BAND0 2
#define MT_RXQ_MSDU_PAGE_BAND2 3
#define MT_INT_RX(q) BIT(20 + (q))
#define MT_WFDMA0(offset) (0x10000u + (offset))
#define MT_WFDMA0_PCIE1(offset) (0x20000u + (offset))
#define MT7996_WATCHDOG_TIME 1000
#define RX_COUNT 5
#include "l1-constants.inc"

enum {
    MT_MCU_CMD_NORMAL_STATE = BIT(0), MT_MCU_CMD_STOP_DMA = BIT(1),
    MT_MCU_CMD_RESET_DONE = BIT(2), MT_MCU_CMD_RECOVERY_DONE = BIT(3),
    MT_MCU_CMD_WA_WDT = BIT(4), MT_MCU_CMD_WDT_MASK = BIT(4) | BIT(5),
    MT_INT_MCU_CMD = BIT(6), MT_INT_RX_DONE_MCU = BIT(7), MT_INT_TX_DONE_MCU = BIT(8),
    MT_INT_BAND0_RX_DONE = BIT(9), MT_INT_BAND1_RX_DONE = BIT(10),
    MT_INT_BAND2_RX_DONE = BIT(11), MT_INT_TX_RX_DONE_EXT = BIT(12),
    MT_INT_RX_TXFREE_BAND1_EXT = BIT(13), MT_INT_TX_DONE_BAND0 = BIT(14),
    MT_INT_TX_DONE_BAND1 = BIT(15), MT_INT_TX_DONE_BAND2 = BIT(16),
    MT_WFDMA0_GLO_CFG_TX_DMA_EN = BIT(0), MT_WFDMA0_GLO_CFG_RX_DMA_EN = BIT(1),
    MT_WFDMA0_GLO_CFG_OMIT_TX_INFO = BIT(2), MT_WFDMA0_GLO_CFG_EXT_EN = BIT(3),
    MT_WFDMA0_GLO_CFG_OMIT_RX_INFO_PFET2 = BIT(4), MT_RRO_3_0_EMU_CONF_EN_MASK = BIT(5),
};
enum {
    MT_WFDMA0_MCU_HOST_INT_ENA = 0x10, MT_MCU_INT_EVENT = 0x20,
    MT_INT_MASK_CSR = 0x30, MT_INT_PCIE1_MASK_CSR = 0x40,
    MT_WFDMA0_GLO_CFG = 0x50, MT_RRO_3_0_EMU_CONF = 0x60,
    MT_MCU_INT_EVENT_DMA_STOPPED = 1, MT_MCU_INT_EVENT_DMA_INIT = 2,
    MT_MCU_INT_EVENT_RESET_DONE = 3,
};

struct work_struct { int id; };
struct napi_struct { int id; bool enabled; };
struct mt76_worker { bool enabled; };
struct ieee80211_hw { void *wiphy; };
struct mt76_phy { unsigned long state; struct work_struct mac_work; int band_idx; };
struct mt7996_phy { struct mt76_phy *mt76; };
struct mt76_queue { u32 flags; };
struct mtk_wed_device { int id; bool active; bool running; };
struct airoha_npu { int id; };
struct mt76_dev {
    void *dev;
    struct ieee80211_hw *hw;
    int mutex, token, hwrro_mode, irq_tasklet;
    struct { int wait; } mcu;
    struct {
        struct mtk_wed_device wed, wed_hif2;
        struct airoha_npu *npu;
        u32 irqmask;
    } mmio;
    struct mt76_queue q_rx[RX_COUNT];
    struct napi_struct napi[RX_COUNT], tx_napi;
    struct mt76_worker tx_worker;
};
struct mt7996_dev {
    struct mt76_dev mt76;
    struct mt76_phy mphy, extra[2];
    struct mt7996_phy phys[3];
    void *hif2;
    struct work_struct reset_work;
    struct { struct work_struct work; } wed_rro;
    struct {
        u32 state, wa_reset_count, wm_reset_count;
        int npu_error;
        bool restart;
    } recovery;
};

static struct mt7996_dev fixture;
static struct ieee80211_hw hw;
static struct airoha_npu provider;
static int chip, phy_mask, stop_mode, init_fail, wait_mask, repeat_mode, detached;
static int events, send_count, get_count, setup_count, wait_count, cleanup_count;
static int queue_stops, queue_wakes, completed, failed, data_starts, full_resets;
static int irq_enables, irq_disables, lock_depth, rcu_depth, independent_access, unsafe_cleanup;
static unsigned char token_memory[64], ring_memory[64];

static void event(const char *name, long a, long b)
{
    events++;
    printf("{\"op\":\"%s\",\"a\":%ld,\"b\":%ld}\n", name, a, b);
}

#define mt7996_for_each_phy(dev, phy) \
    for (int cursor = 0; cursor < 3; cursor++) \
        if ((phy_mask & BIT(cursor)) && ((phy) = &(dev)->phys[cursor]))
#define mt76_for_each_q_rx(dev, index) for ((index) = 0; (index) < RX_COUNT; (index)++)
#define mt76_hw(dev) ((dev)->mt76.hw)
#define is_mt7996(dev) ((void)(dev), chip == 7996)
#define is_mt7992(dev) ((void)(dev), chip == 7992)
#define mt76_npu_device_active(dev) (!!(dev)->mmio.npu)
#define mtk_wed_device_active(wed) ((wed)->active)
#define mtk_wed_get_rx_capa(wed) ((wed)->active)
#define mt7996_has_wa(dev) ((void)(dev), true)
#define mt7996_band_valid(dev, band) ((void)(dev), !!(phy_mask & BIT(band)))
#define rcu_dereference_protected(pointer, condition) ((void)(condition), assert(lock_depth == 1), (pointer))
#define rcu_dereference(pointer) (assert(rcu_depth == 1), (pointer))
#define wiphy_name(wiphy) ((void)(wiphy), "synthetic-l1")
#define dev_info(dev, format, ...) do { \
    (void)(dev); \
    if (strstr((format), "completed")) { completed++; event("completed", 0, 0); } \
    else event("info", 0, 0); \
} while (0)
#define dev_err(dev, format, ...) do { \
    (void)(dev); \
    if (strstr((format), "L1 recovery failed")) failed++; \
    event("error", fixture.recovery.npu_error, 0); \
} while (0)

static void set_bit(int bit, unsigned long *state) { *state |= 1ul << bit; }
static void clear_bit(int bit, unsigned long *state) { *state &= ~(1ul << bit); }
static void mutex_lock(int *lock) { assert(!lock_depth && !*lock); *lock = ++lock_depth; }
static void mutex_unlock(int *lock) { assert(lock_depth == 1 && *lock == 1); *lock = --lock_depth; }
static void rcu_read_lock(void) { assert(!rcu_depth); rcu_depth++; }
static void rcu_read_unlock(void) { assert(rcu_depth == 1); rcu_depth--; }
static void wake_up(int *wait) { (void)wait; event("mcu_wake", 0, 0); }
static void mt76_abort_scan(struct mt76_dev *dev) { (void)dev; event("abort_scan", 0, 0); }
static void mt76_abort_roc(struct mt76_phy *phy) { event("abort_roc", phy->band_idx, 0); }
static void cancel_work_sync(struct work_struct *work) { event("cancel_work", work->id, 0); }
static void cancel_delayed_work_sync(struct work_struct *work) { event("cancel_mac", work->id, 0); }
static void mt76_worker_disable(struct mt76_worker *worker) { assert(worker->enabled); worker->enabled = false; event("worker_disable", 0, 0); }
static void mt76_worker_enable(struct mt76_worker *worker) { assert(!worker->enabled); worker->enabled = true; event("worker_enable", 0, 0); }
static void napi_disable(struct napi_struct *napi) { assert(napi->enabled); napi->enabled = false; event("napi_disable", napi->id, 0); }
static void napi_enable(struct napi_struct *napi) { assert(!napi->enabled); napi->enabled = true; event("napi_enable", napi->id, 0); }
static void napi_schedule(struct napi_struct *napi) { assert(napi->enabled); event("napi_schedule", napi->id, 0); }
static void local_bh_disable(void) {}
static void local_bh_enable(void) {}
static void tasklet_schedule(void *tasklet) { (void)tasklet; event("tasklet", 0, 0); }
static void ieee80211_stop_queues(struct ieee80211_hw *h) { assert(h == &hw); queue_stops++; event("queues_stop", 0, 0); }
static void ieee80211_wake_queues(struct ieee80211_hw *h) { assert(h == &hw); queue_wakes++; event("queues_wake", 0, 0); }
static void mt7996_update_beacons(struct mt7996_dev *dev) { (void)dev; event("beacons", 0, 0); }
static void ieee80211_queue_delayed_work(struct ieee80211_hw *h, struct work_struct *work, int delay)
{ assert(h == &hw && delay == MT7996_WATCHDOG_TIME); event("mac_reschedule", work->id, 0); }
static void mtk_wed_device_stop(struct mtk_wed_device *wed) { wed->running = false; event("wed_stop", wed->id, 0); }
static void mtk_wed_device_start(struct mtk_wed_device *wed, u32 mask) { wed->running = true; event("wed_start", wed->id, mask); }
static void mtk_wed_device_start_hw_rro(struct mtk_wed_device *wed, u32 mask, bool reset)
{ assert(reset); wed->running = true; event("wed_rro_start", wed->id, mask); }
static void mt7996_irq_enable(struct mt7996_dev *dev, u32 mask) { (void)dev; event("host_irq_enable", mask, 0); }
static void mt7996_irq_disable(struct mt7996_dev *dev, u32 mask) { (void)dev; event("host_irq_disable", mask, 0); }
static void mt76_wr(struct mt7996_dev *dev, u32 reg, u32 value) { (void)dev; event("write", reg, value); }
static void mt76_clear(struct mt7996_dev *dev, u32 reg, u32 value) { (void)dev; event("clear", reg, value); }
static void mt76_set(struct mt7996_dev *dev, u32 reg, u32 value)
{
    (void)dev;
    if ((reg == MT_WFDMA0_GLO_CFG || reg == MT_WFDMA0_GLO_CFG+0x10000) &&
        (value & (MT_WFDMA0_GLO_CFG_TX_DMA_EN | MT_WFDMA0_GLO_CFG_RX_DMA_EN))) data_starts++;
    event("set", reg, value);
}
static bool mt7996_wait_reset_state(struct mt7996_dev *dev, u32 state)
{
    (void)dev;
    int index = state == MT_MCU_CMD_RESET_DONE ? 0 : state == MT_MCU_CMD_RECOVERY_DONE ? 1 : 2;
    bool ok = !!(wait_mask & BIT(index));
    wait_count++;
    event("wait", state, ok);
    return ok;
}
void mt7996_dma_start(struct mt7996_dev *dev, bool reset, bool wed_reset);
static void mt7996_dma_reset(struct mt7996_dev *dev, bool force)
{
    assert(!force);
    cleanup_count++;
    unsafe_cleanup += independent_access;
    memset(ring_memory, 0, sizeof(ring_memory));
    event("dma_reset_model", 0, 0);
    mt7996_dma_start(dev, true, true);
}
static void mt7996_tx_token_put(struct mt7996_dev *dev)
{
    (void)dev;
    cleanup_count++;
    unsafe_cleanup += independent_access;
    memset(token_memory, 0, sizeof(token_memory));
    event("token_put_model", 0, 0);
}
static void idr_init(int *token) { *token = 0; event("idr_init", 0, 0); }
static void mt7996_mac_full_reset(struct mt7996_dev *dev) { (void)dev; full_resets++; event("full_reset_model", 0, 0); }
static void usleep_range(int low, int high) { assert(low == 10000 && high == 15000); event("stop_sleep_model", low, high); }

static int mt76_npu_send_msg(struct airoha_npu *npu, int selector, int api, u32 value, int gfp)
{
    assert(npu == &provider && !value && gfp == GFP_KERNEL && (selector == 4 || selector == 6));
    assert(api == WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR);
    int ret = (stop_mode == 1 && selector == 4) || (stop_mode == 4 && selector == 6) ? -EIO : 0;
    send_count++;
    event("stop_send_model", selector, ret);
    if (detached && selector == 6 && !ret) {
        fixture.mt76.mmio.npu = NULL;
        event("provider_detached_model", 0, 0);
    }
    return ret;
}
static int mt76_npu_get_msg(struct airoha_npu *npu, int selector, int api, u32 *value, int gfp)
{
    assert(npu == &provider && selector == 3 && gfp == GFP_KERNEL);
    assert(api == WLAN_FUNC_GET_WAIT_NPU_INFO);
    int ret = stop_mode == 3 ? -EIO : 0;
    *value = stop_mode == 2 || (stop_mode == 5 && get_count < 9);
    get_count++;
    event("stop_get_model", *value, ret);
    return ret;
}
#define SETUP(name) \
static int name(struct mt7996_dev *dev, struct airoha_npu *npu) { \
    assert(dev == &fixture && npu == &provider && lock_depth == 1); \
    int ret = ++setup_count == init_fail ? -ENOMEM : 0; \
    event("setup_model", setup_count, ret); return ret; \
}
SETUP(mt7996_npu_offload_init)
SETUP(mt7996_npu_rxd_init)
SETUP(mt7992_npu_rxd_init)
SETUP(mt7996_npu_txd_init)
SETUP(mt7996_npu_rx_event_init)
SETUP(mt7996_npu_set_pcie_addr)
SETUP(mt7996_npu_tx_done_init)
static int mt7996_npu_rx_event_validate(struct mt7996_dev *dev)
{
    assert(dev == &fixture && lock_depth == 1);
    int ret = ++setup_count == init_fail ? -ENOMEM : 0;
    event("setup_model", setup_count, ret);
    return ret;
}
static void airoha_npu_wlan_enable_irq(struct airoha_npu *npu, int index)
{ assert(npu == &provider); irq_enables++; event("npu_irq_enable_model", index, 0); }
static u32 airoha_npu_wlan_get_irq_status(struct airoha_npu *npu, int index)
{ assert(npu == &provider); event("npu_irq_status_model", index, 0); return BIT(index); }
static void airoha_npu_wlan_set_irq_status(struct airoha_npu *npu, u32 status)
{ assert(npu == &provider); event("npu_irq_ack_model", status, 0); }
static void airoha_npu_wlan_disable_irq(struct airoha_npu *npu, int index)
{ assert(npu == &provider); irq_disables++; event("npu_irq_disable_model", index, 0); }

#include "l1-driver.inc"

static unsigned memory_sum(const unsigned char *data, size_t bytes)
{
    unsigned sum = 0;
    for (size_t i = 0; i < bytes; i++) sum += data[i];
    return sum;
}

int main(int argc, char **argv)
{
    assert(argc == 11);
    chip = atoi(argv[1]); int active = atoi(argv[2]); phy_mask = atoi(argv[3]);
    int wed_mask = atoi(argv[4]); stop_mode = atoi(argv[5]); init_fail = atoi(argv[6]);
    wait_mask = atoi(argv[7]); repeat_mode = atoi(argv[8]); independent_access = atoi(argv[9]);
    detached = atoi(argv[10]);
    fixture.mt76.dev = &fixture;
    fixture.mt76.hw = &hw;
    fixture.mt76.mmio.npu = active ? &provider : NULL;
    fixture.mt76.mmio.irqmask = 0xabcdef;
    fixture.mt76.mmio.wed = (struct mtk_wed_device){0, !!(wed_mask & 1), !!(wed_mask & 1)};
    fixture.mt76.mmio.wed_hif2 = (struct mtk_wed_device){1, !!(wed_mask & 2), !!(wed_mask & 2)};
    fixture.hif2 = wed_mask & 2 ? &fixture : NULL;
    fixture.mt76.hwrro_mode = 3;
    fixture.mt76.tx_worker.enabled = true;
    fixture.mt76.tx_napi = (struct napi_struct){99, true};
    fixture.phys[0].mt76 = &fixture.mphy;
    fixture.phys[1].mt76 = &fixture.extra[0];
    fixture.phys[2].mt76 = &fixture.extra[1];
    for (int i = 0; i < 3; i++) {
        fixture.phys[i].mt76->band_idx = i;
        fixture.phys[i].mt76->mac_work.id = i;
    }
    for (int i = 0; i < RX_COUNT; i++) fixture.mt76.napi[i] = (struct napi_struct){i, true};
    fixture.mt76.q_rx[1].flags = MT_QFLAG_WED_RRO;
    fixture.mt76.q_rx[2].flags = FIELD_PREP(MT_QFLAG_WED_TYPE, MT76_WED_Q_TXFREE);
    fixture.mt76.q_rx[3].flags = MT_QFLAG_WED | FIELD_PREP(MT_QFLAG_WED_TYPE, MT76_WED_Q_TXFREE);
    fixture.mt76.q_rx[4].flags = MT_QFLAG_WED_RRO | MT_QFLAG_WED;
    fixture.recovery.state = MT_MCU_CMD_STOP_DMA;
    memset(token_memory, 0xa5, sizeof(token_memory));
    memset(ring_memory, 0x5a, sizeof(ring_memory));
    mt7996_mac_reset_work(&fixture.reset_work);
    int first_events = events, first_error = fixture.recovery.npu_error;
    int second_events = 0;
    if (repeat_mode) {
        fixture.recovery.restart = repeat_mode == 2;
        fixture.recovery.state = repeat_mode == 2 ? MT_MCU_CMD_WA_WDT : MT_MCU_CMD_STOP_DMA;
        event("repeat_request", repeat_mode, 0);
        int begin = events;
        mt7996_mac_reset_work(&fixture.reset_work);
        second_events = events-begin;
    }
    assert(!lock_depth && !fixture.mt76.mutex && !rcu_depth);
    printf("{\"summary\":true,\"error\":%d,\"first_error\":%d,\"first_events\":%d,"
           "\"second_events\":%d,\"sends\":%d,\"gets\":%d,\"setups\":%d,\"waits\":%d,"
           "\"cleanup\":%d,\"unsafe_cleanup_model\":%d,\"queue_wakes\":%d,\"completed\":%d,"
           "\"failed\":%d,\"data_starts\":%d,\"full_resets\":%d,\"irq_enables\":%d,"
           "\"irq_disables\":%d,\"tx_worker\":%d,\"tx_napi\":%d,\"reset_state\":%lu,"
           "\"token_sum\":%u,\"ring_sum\":%u,\"napi\":[%d,%d,%d,%d,%d]}\n",
           fixture.recovery.npu_error, first_error, first_events, second_events, send_count,
           get_count, setup_count, wait_count, cleanup_count, unsafe_cleanup, queue_wakes,
           completed, failed, data_starts, full_resets, irq_enables, irq_disables,
           fixture.mt76.tx_worker.enabled, fixture.mt76.tx_napi.enabled, fixture.mphy.state,
           memory_sum(token_memory, sizeof(token_memory)), memory_sum(ring_memory, sizeof(ring_memory)),
           fixture.mt76.napi[0].enabled, fixture.mt76.napi[1].enabled, fixture.mt76.napi[2].enabled,
           fixture.mt76.napi[3].enabled, fixture.mt76.napi[4].enabled);
    return 0;
}
