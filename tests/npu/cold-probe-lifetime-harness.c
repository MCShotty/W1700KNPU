/* Selected real registration/cleanup C; hardware and framework boundaries are models. */
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint32_t u32;
#define CHECK(ok, message) assert((ok) && message)
#define BIT(n) (1UL << (n))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define READ_ONCE(v) (v)
#define WRITE_ONCE(v, x) ((v) = (x))
#define IS_ENABLED(v) (v)
#define GFP_KERNEL 0
#define WARN_ON(v) (!!(v))
#define rcu_assign_pointer(p, v) ((p) = (v))
#define dev_err(...) ((void)0)
#define MT7996_WTBL_STA 1024
#define MT_WCID_TX_INFO_SET 1
#define MT_INT_SOURCE_CSR 1
#define MT_AFE_CTL_BAND_PLL_03(band) (2 + (band))
#define MT_AFE_CTL_BAND_PLL_03_MSB_EN 1
#define MT_TOP_LPCR_HOST_BAND(band) (10 + (band))
#define MT_TOP_LPCR_HOST_FW_OWN 1
#define FW_STATE_FW_DOWNLOAD 0
enum { MT_BAND0, MT_BAND1, MT_BAND2 };
enum { NL80211_BAND_2GHZ, NL80211_BAND_5GHZ, NL80211_BAND_6GHZ };
#include "selected-state.inc"
#include "selected-driver-flag.inc"
#include "selected-pci-irq.inc"

struct work_struct {
	void (*fn)(struct work_struct *);
	bool initialized, pending, running;
	unsigned disabled;
};
struct delayed_work { struct work_struct work; };
struct device { int refs; };
struct pci_dev { struct device dev; };
struct led_classdev { void *brightness_set, *blink_set; };
struct wiphy { int unused; };
struct ieee80211_hw { struct wiphy *wiphy; };
struct ieee80211_rate { int unused; };
struct mt76_dev;
struct mt7996_dev;
struct mt76_phy {
	struct ieee80211_hw *hw;
	struct mt76_dev *dev;
	void *priv;
	unsigned long state;
	unsigned band_idx;
	struct delayed_work mac_work, roc_work;
	struct { bool has_2ghz, has_5ghz, has_6ghz; } cap;
	struct { struct led_classdev cdev; } leds;
	int sband_2g, sband_5g, sband_6g;
};
struct mt76_wcid { int idx, hw_key_idx, tx_info; };
struct mt76_worker { void *task; };
struct mt76_driver_ops { unsigned long drv_flags; };
struct mtk_wed_device { bool active; };
struct mt76_dev {
	struct mt76_phy phy;
	struct device *dev;
	struct ieee80211_hw *hw;
	struct mt76_driver_ops *drv;
	struct mt76_phy *phys[3];
	int (*init_wiphy)(struct mt76_dev *);
	void *wq, *queue_ops, *mcu_ops;
	struct mt76_worker tx_worker;
	int irq_tasklet;
	struct delayed_work scan_work;
	struct { int res_q, wait; } mcu;
	struct { struct mtk_wed_device wed, wed_hif2; } mmio;
	struct mt76_wcid global_wcid, *wcid[2];
	u32 wcid_mask[2];
};
struct mt7996_phy { struct mt76_phy *mt76; struct mt7996_dev *dev; };
struct mt7996_hif { struct device *dev; };
struct mt7996_crash_data { void *memdump_buf; size_t memdump_buf_len; int guid, timestamp; };
struct mt7996_dev {
	union { struct mt76_dev mt76; struct mt76_phy mphy; };
	struct mt7996_phy phy;
	struct mt7996_hif *hif2;
	struct mt7996_pci_irq pci_irq[2];
	bool cleanup_started;
	struct work_struct init_work, rc_work, reset_work, dump_work;
	struct { struct work_struct work; int poll_list, lock; } wed_rro;
	int sta_rc_list, twt_list, reset_wait, dump_mutex;
	struct { bool hw_init_done, restart; } recovery;
	struct { struct mt7996_crash_data *crash_data; } coredump;
};
static struct mt7996_dev device;
static struct {
	struct pci_dev primary, secondary;
	struct ieee80211_hw hw;
	struct wiphy wiphy;
	struct mt76_driver_ops drv;
	struct mt7996_phy extra[2];
	struct mt76_phy mphy[2];
	struct mt7996_hif hif;
	unsigned stage, family, cleanup_calls, dma_closes, mcu_exits, free_calls, purges;
	unsigned early_recovery, null_scheduler, leaked_registration;
	bool live, registered, led, tx_parked, pci_closed, npu_closed, napi_joined;
	bool rro, dma_cleaned, hif_ref, vectors[2];
	bool block_init, entered_init, release_init, waiting_init, cleanup_finished;
	bool inject_tail;
	struct { void *ptr; bool live; } allocs[8];
	unsigned allocations;
} model;
static unsigned cases;
static bool coredump_memdump;
static struct ieee80211_rate mt76_rates[8];
static pthread_mutex_t work_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t work_cond = PTHREAD_COND_INITIALIZER;
#define mt76_hw(dev) ((dev)->mt76.hw)
#define mt7996_for_each_phy(dev, phy) \
	for (unsigned __band = 0; __band < 3; __band++) \
		if (((phy) = (dev)->mt76.phys[__band] ? (dev)->mt76.phys[__band]->priv : NULL))
#define INIT_LIST_HEAD(p) (*(p) = 1)
#define spin_lock_init(p) (*(p) = 1)
#define mutex_init(p) (*(p) = 1)
#define init_waitqueue_head(p) (*(p) = 1)
#define lockdep_assert_held(p) CHECK(*(p), "modeled-dump-mutex-initialized")
static void set_bit(unsigned bit, unsigned long *state) { *state |= BIT(bit); }
static bool test_bit(unsigned bit, unsigned long *state) { return !!(*state & BIT(bit)); }
static bool test_and_set_bit(unsigned bit, unsigned long *state)
{ bool old = test_bit(bit, state); set_bit(bit, state); return old; }
static void wake_up(int *wait) { (void)wait; }
static void work_init(struct work_struct *work, void (*fn)(struct work_struct *))
{
	CHECK(!work->initialized, "work-constructed-once-before-use");
	*work = (struct work_struct){ .fn = fn, .initialized = true };
}
#define INIT_WORK(w, fn) work_init(w, fn)
#define INIT_DELAYED_WORK(w, fn) work_init(&(w)->work, fn)
static bool queue_work(void *queue, struct work_struct *work)
{
	bool queued = false;
	CHECK(queue && model.live, "queue-has-live-device-and-workqueue");
	pthread_mutex_lock(&work_lock);
	CHECK(work->initialized, "no-queue-of-uninitialized-work");
	if (!work->disabled && !work->pending) {
		work->pending = queued = true;
		if ((work == &device.reset_work || work == &device.dump_work) && !device.recovery.hw_init_done)
			model.early_recovery++;
	}
	pthread_mutex_unlock(&work_lock);
	return queued;
}
static void ieee80211_queue_work(struct ieee80211_hw *hw, struct work_struct *work)
{ CHECK(hw == &model.hw, "exact-wiphy-workqueue-owner"); (void)queue_work(device.mt76.wq, work); }
static bool cancel_model(struct work_struct *work, bool disable, bool sync)
{
	bool pending;
	pthread_mutex_lock(&work_lock);
	CHECK(work->initialized, "no-control-of-uninitialized-work");
	pending = work->pending;
	if (disable) work->disabled++;
	work->pending = false;
	if (sync && work == &device.init_work && work->running) {
		model.waiting_init = true;
		pthread_cond_broadcast(&work_cond);
	}
	while (sync && work->running) pthread_cond_wait(&work_cond, &work_lock);
	if (sync) work->pending = false;
	pthread_mutex_unlock(&work_lock);
	return pending;
}
static bool disable_work(struct work_struct *w) { return cancel_model(w, true, false); }
static bool disable_work_sync(struct work_struct *w) { return cancel_model(w, true, true); }
static bool cancel_work_sync(struct work_struct *w) { return cancel_model(w, false, true); }
static bool disable_delayed_work_sync(struct delayed_work *w) { return disable_work_sync(&w->work); }
static bool cancel_delayed_work_sync(struct delayed_work *w) { return cancel_work_sync(&w->work); }
static bool enable_work(struct work_struct *w)
{
	CHECK(model.registered && device.coredump.crash_data, "recovery-enabled-only-after-coredump-and-registration");
	CHECK(w->initialized && w->disabled, "enable-matches-initial-disable-depth");
	return !--w->disabled;
}
static void dummy_work(struct work_struct *work) { (void)work; }
static void mt7996_init_work(struct work_struct *work);
#define mt7996_mac_sta_rc_work dummy_work
#define mt7996_mac_work dummy_work
#define mt7996_mac_reset_work dummy_work
#define mt7996_mac_dump_work dummy_work
#define mt7996_wed_rro_work dummy_work
static void *run_work(void *opaque)
{
	struct work_struct *work = opaque;
	pthread_mutex_lock(&work_lock);
	CHECK(work->pending && !work->disabled, "running-only-accepted-work");
	work->pending = false; work->running = true;
	pthread_mutex_unlock(&work_lock);
	work->fn(work);
	pthread_mutex_lock(&work_lock);
	work->running = false;
	pthread_cond_broadcast(&work_cond);
	pthread_mutex_unlock(&work_lock);
	return NULL;
}
static void check_work_closed(struct work_struct *w)
{
	CHECK(w->initialized && w->disabled && !w->pending && !w->running,
	      "permanent-work-admission-closed-before-context-free");
}
static void all_work_closed(void)
{
	check_work_closed(&device.init_work); check_work_closed(&device.rc_work);
	check_work_closed(&device.dump_work); check_work_closed(&device.reset_work);
	check_work_closed(&device.wed_rro.work); check_work_closed(&device.mt76.scan_work.work);
	for (unsigned i = 0; i < 3; i++) if (device.mt76.phys[i]) {
		struct mt76_phy *phy = device.mt76.phys[i];
		check_work_closed(&phy->mac_work.work);
		if (test_bit(MT76_STATE_REGISTERED, &phy->state)) check_work_closed(&phy->roc_work.work);
	}
}
static void mt7996_pci_shutdown_irqs(struct mt7996_dev *dev)
{
	CHECK(dev == &device && model.live, "PCI-close-before-context-free");
	if (!model.pci_closed && dev->mt76.mcu_ops) dev->mt76.mcu.res_q++;
	model.pci_closed = true;
}
static void mt76_npu_shutdown_irqs(struct mt76_dev *dev)
{ CHECK(dev == &device.mt76 && model.pci_closed, "PCI-before-modeled-NPU-close"); model.npu_closed = true; }
static void mt76_napi_cleanup(struct mt76_dev *dev)
{ CHECK(dev == &device.mt76 && model.npu_closed, "NPU-before-modeled-NAPI-join"); model.napi_joined = true; }
static void mt76_npu_deinit(struct mt76_dev *dev) { (void)dev; }
static void mt76_worker_disable(struct mt76_worker *worker)
{ CHECK(worker == &device.mt76.tx_worker, "exact-TX-worker"); model.tx_parked = true; }
static void mt76_worker_teardown(struct mt76_worker *worker) { worker->task = NULL; }
static void destroy_workqueue(void *queue)
{
	CHECK(queue == &model, "exact-device-workqueue-destroyed");
#if !BASELINE
	all_work_closed();
#endif
}
static void ieee80211_free_hw(struct ieee80211_hw *hw)
{
	CHECK(hw == &model.hw && model.live, "context-freed-exactly-once");
	if (model.registered) model.leaked_registration++;
#if !BASELINE
	CHECK(!model.registered && !model.led, "mac80211-and-LED-ownership-released-before-context-free");
	CHECK(model.pci_closed && model.npu_closed && model.napi_joined, "IRQ-and-NAPI-join-before-context-free");
	CHECK(!device.mt76.mcu.res_q, "late-MCU-responses-purged-after-ingress-join");
	all_work_closed();
#endif
	model.live = false; model.free_calls++;
}
#include "selected-core-free.inc"
static bool mtk_wed_device_active(struct mtk_wed_device *wed) { return wed->active; }
static void mtk_wed_device_detach(struct mtk_wed_device *wed) { wed->active = false; }
static void pci_free_irq_vectors(struct pci_dev *pci)
{ unsigned index = pci == &model.secondary; CHECK(model.vectors[index], "only-owned-vectors-freed"); model.vectors[index] = false; }
static void put_device(struct device *dev)
{ CHECK(dev == &model.secondary.dev && model.hif_ref && dev->refs == 2, "HIF-reference-held-until-cleanup-finishes"); dev->refs--; model.hif_ref = false; }
static void mt76_wr(struct mt7996_dev *dev, u32 reg, u32 value)
{ (void)reg; (void)value; CHECK(dev == &device && model.live && (!dev->hif2 || model.hif_ref), "MMIO-owner-and-HIF-pin-live"); }
static void mt76_rmw(struct mt7996_dev *dev, u32 reg, u32 clear, u32 set)
{ (void)clear; mt76_wr(dev, reg, set); }
static bool is_mt7992(struct mt76_dev *dev) { (void)dev; return model.family == 1; }
static bool is_mt7990(struct mt76_dev *dev) { (void)dev; return model.family == 0; }
static void skb_queue_purge(int *queue) { *queue = 0; model.purges++; }
static int mt7996_mcu_restart(struct mt76_dev *dev)
{
	CHECK(dev->mcu_ops && dev->queue_ops, "MCU-exit-only-after-MCU-and-DMA-attempt");
#if !BASELINE
	CHECK(!model.pci_closed && !model.napi_joined && model.tx_parked,
	      "MCU-exit-keeps-response-ingress-after-TX-worker-join");
	all_work_closed();
#endif
	model.mcu_exits++;
	return 0;
}
static bool mt7996_firmware_state(struct mt7996_dev *dev, int expected) { (void)dev; (void)expected; return false; }
#include "selected-mcu-exit.inc"
static bool allocation_live(void *ptr)
{ for (unsigned i=0;i<model.allocations;i++) if (model.allocs[i].ptr==ptr) return model.allocs[i].live; return false; }
static void *vzalloc(size_t size)
{
	if ((!model.allocations && model.stage == 23) || (model.allocations && model.stage == 24)) return NULL;
	CHECK(model.allocations < ARRAY_SIZE(model.allocs), "bounded-coredump-allocations");
	void *ptr = calloc(1, size);
	CHECK(ptr, "host-allocation");
	model.allocs[model.allocations].ptr = ptr; model.allocs[model.allocations++].live = true;
	return ptr;
}
static void vfree(void *ptr)
{
	for (unsigned i=0;i<model.allocations;i++) if (model.allocs[i].ptr==ptr) {
		CHECK(model.allocs[i].live, "coredump-allocation-released-once");
		model.allocs[i].live = false; return;
	}
	CHECK(false, "only-owned-coredump-allocation-released");
}
static int mt7996_coredump_get_mem_size(struct mt7996_dev *dev) { (void)dev; return model.family == 2 ? 16 : 0; }
#include "selected-coredump-register.inc"
#include "selected-coredump-unregister.inc"
static void mt7996_npu_rro_reset_close(struct mt7996_dev *dev) { (void)dev; }
static void mt7996_npu_rro_reset_join(struct mt7996_dev *dev) { (void)dev; }
static struct mt7996_phy *mt7996_phy2(struct mt7996_dev *dev) { return dev->mt76.phys[1] ? dev->mt76.phys[1]->priv : NULL; }
static struct mt7996_phy *mt7996_phy3(struct mt7996_dev *dev) { return dev->mt76.phys[2] ? dev->mt76.phys[2]->priv : NULL; }
static void mt7996_unregister_phy(struct mt7996_phy *phy) { (void)phy; }
static void mt7996_unregister_thermal(struct mt7996_phy *phy) { (void)phy; }
static void mt7996_tx_token_put(struct mt7996_dev *dev)
{
	(void)dev;
#if !BASELINE
	CHECK(model.tx_parked && model.pci_closed && model.napi_joined, "TX-worker-and-ingress-joined-before-token-retirement");
#endif
}
static void mt7996_dma_cleanup(struct mt7996_dev *dev)
{
	CHECK(dev->mt76.queue_ops, "DMA-cleanup-requires-attached-queue-operations");
#if !BASELINE
	all_work_closed();
	CHECK(model.pci_closed && model.napi_joined && model.tx_parked, "CPU-joins-before-DMA-cleanup");
#endif
	model.dma_closes++; model.dma_cleaned = true;
	mtk_wed_device_detach(&dev->mt76.mmio.wed); mtk_wed_device_detach(&dev->mt76.mmio.wed_hif2);
}
static void mt7996_wed_rro_free(struct mt7996_dev *dev)
{
#if !BASELINE
	CHECK(model.napi_joined && (!dev->mt76.queue_ops || model.dma_cleaned), "RRO-cleanup-follows-CPU-and-DMA-cleanup");
#endif
	model.rro = false;
}
static bool mt7996_has_hwrro(struct mt7996_dev *dev) { (void)dev; return true; }
static void mt7996_rro_msdu_page_map_free(struct mt7996_dev *dev) { (void)dev; }
static void tasklet_disable(void *tasklet) { (void)tasklet; }
static int fail(unsigned stage) { return model.stage == stage ? -EIO : 0; }
static int mt7996_variant_type_init(struct mt7996_dev *dev) { (void)dev; return fail(1); }
static int mt7996_dma_init(struct mt7996_dev *dev) { dev->mt76.queue_ops = &model; return fail(2); }
static int timeout_response(struct mt76_dev *mdev, int cmd, int seq)
{
	struct mt7996_dev *dev = container_of(mdev, struct mt7996_dev, mt76);
	void *skb = NULL;
	(void)cmd; (void)seq;
#include "selected-timeout-branch.inc"
	return 0;
}
static int mt7996_mcu_init(struct mt7996_dev *dev)
{
	CHECK(dev->mt76.queue_ops, "MCU-init-after-DMA-init");
	dev->mt76.mcu_ops = &model; dev->mt76.mcu.res_q = 2;
	return model.stage == 3 ? timeout_response(&dev->mt76, 7, 1) : 0;
}
static int mt7996_npu_prepare_tx_buffers(struct mt7996_dev *dev) { (void)dev; return fail(4); }
static int mt7996_wed_rro_init(struct mt7996_dev *dev) { (void)dev; model.rro = true; return fail(5); }
static int mt7996_variant_fem_init(struct mt7996_dev *dev) { (void)dev; return fail(6); }
static int mt7996_eeprom_init(struct mt7996_dev *dev) { (void)dev; return fail(7); }
static int mt76_wcid_alloc(u32 *mask, unsigned size) { (void)mask; (void)size; return model.stage == 8; }
static int mt76_phy_init(struct mt76_phy *phy, struct ieee80211_hw *hw)
{ (void)hw; INIT_DELAYED_WORK(&phy->roc_work, dummy_work); return phy == &device.mphy ? fail(13) : 0; }
static int mt7996_register_phy(struct mt7996_dev *dev, unsigned band)
{
	struct mt76_phy *mphy = &model.mphy[band-1];
	struct mt7996_phy *phy = &model.extra[band-1];
	*mphy = (struct mt76_phy){ .hw = &model.hw, .dev = &dev->mt76, .priv = phy };
	*phy = (struct mt7996_phy){ .mt76=mphy, .dev=dev };
	INIT_DELAYED_WORK(&mphy->mac_work, dummy_work);
	mt76_phy_init(mphy, &model.hw);
	if (model.stage == band + 8) return -EIO;
	set_bit(MT76_STATE_REGISTERED, &mphy->state); dev->mt76.phys[band] = mphy;
	return 0;
}
static void mt7996_init_wiphy(struct ieee80211_hw *hw, struct mtk_wed_device *wed)
{ (void)hw; (void)wed; if (CONFIG_MT76_LEDS) device.mphy.leds.cdev.brightness_set = &model; }
static int mt7996_npu_hw_init(struct mt7996_dev *dev) { (void)dev; return fail(11); }
static int mt7996_dma_rro_start(struct mt7996_dev *dev) { (void)dev; return fail(12); }
static void mt76_wcid_init(struct mt76_wcid *wcid, unsigned band) { (void)wcid; (void)band; }
static void dev_set_drvdata(struct device *dev, void *data)
{ CHECK(dev == &model.primary.dev && data == &device.mt76, "exact-core-device-driver-data"); }
static int mt76_init_sband_2g(struct mt76_phy *phy, struct ieee80211_rate *rates, int count)
{ (void)phy; (void)rates; (void)count; return fail(14); }
static int mt76_init_sband_5g(struct mt76_phy *phy, struct ieee80211_rate *rates, int count, bool vht)
{ (void)phy; (void)rates; (void)count; (void)vht; return fail(15); }
static int mt76_init_sband_6g(struct mt76_phy *phy, struct ieee80211_rate *rates, int count)
{ (void)phy; (void)rates; (void)count; return fail(16); }
static void wiphy_read_of_freq_limits(struct wiphy *wiphy) { (void)wiphy; }
static void mt76_check_sband(struct mt76_phy *phy, int *band, unsigned id) { (void)phy; (void)band; (void)id; }
static int init_wiphy(struct mt76_dev *dev) { (void)dev; return fail(17); }
static int mt76_led_init(struct mt76_phy *phy)
{ (void)phy; if (fail(18)) return -EIO; model.led = true; return 0; }
static void led_classdev_unregister(struct led_classdev *led)
{ (void)led; CHECK(model.led, "only-registered-LED-released"); model.led = false; }
#include "selected-led-cleanup.inc"
static int ieee80211_register_hw(struct ieee80211_hw *hw)
{ (void)hw; if (fail(19)) return -EIO; model.registered = true; return 0; }
static void ieee80211_unregister_hw(struct ieee80211_hw *hw)
{ (void)hw; CHECK(model.registered, "only-registered-wiphy-unregistered"); model.registered = false; }
static int mt76_worker_setup(struct ieee80211_hw *hw, struct mt76_worker *worker, void *fn, const char *name)
{ (void)hw; (void)fn; (void)name; if (model.stage == 20) return -ENOMEM; worker->task = &model; return 0; }
static void sched_set_fifo_low(void *task)
{
	if (!task) model.null_scheduler++;
#if !BASELINE
	CHECK(task, "worker-start-error-cannot-reach-null-scheduler-task");
#endif
}
static void mt76_tx_status_check(struct mt76_dev *dev, bool flush) { (void)dev; (void)flush; }
static void mt76_wcid_cleanup(struct mt76_dev *dev, struct mt76_wcid *wcid) { (void)dev; (void)wcid; }
#include "selected-core-register.inc"
#include "selected-core-unregister.inc"
static int mt7996_thermal_init(struct mt7996_phy *phy) { (void)phy; return fail(21); }
static int mt7996_init_debugfs(struct mt7996_dev *dev) { (void)dev; return fail(22); }
static int mt7996_mcu_set_eeprom(struct mt7996_dev *dev)
{
	CHECK(dev->mt76.mcu_ops && model.live, "init-callback-has-live-MCU-context");
	pthread_mutex_lock(&work_lock);
	if (model.block_init) {
		model.entered_init = true; pthread_cond_broadcast(&work_cond);
		while (!model.release_init) pthread_cond_wait(&work_cond, &work_lock);
	}
	pthread_mutex_unlock(&work_lock);
	if (model.inject_tail) CHECK(!queue_work(dev->mt76.wq, &dev->init_work), "running-callback-cannot-requeue-after-disable");
	return 0;
}
static void mt7996_mac_init(struct mt7996_dev *dev) { (void)dev; }
static int mt7996_txbf_init(struct mt7996_dev *dev) { (void)dev; return 0; }
static int mt7996_mcu_set_dup_wtbl(struct mt7996_dev *dev) { (void)dev; return 0; }
#include "selected-init-work.inc"
#if !BASELINE
#include "selected-constructor.inc"
#endif
#include "selected-hardware.inc"
#include "selected-register.inc"
#if !BASELINE
#include "selected-cleanup.inc"
#endif
#include "selected-unregister.inc"

static int probe_registration_tail(void)
{
	struct mt7996_dev *dev = &device;
	struct mt76_dev *mdev = &dev->mt76;
	struct pci_dev *pdev = &model.primary;
	struct pci_dev *hif2_dev = dev->hif2 ? &model.secondary : NULL;
	int ret;
#include "selected-pci-tail.inc"

static void dispose_allocations(void)
{ for (unsigned i=0;i<model.allocations;i++) free(model.allocs[i].ptr); }
static void setup(unsigned family, bool hif, bool memdump, unsigned stage)
{
	memset(&device, 0, sizeof(device)); memset(&model, 0, sizeof(model));
	model.family = family; model.stage = stage; model.live = true;
	model.hw.wiphy = &model.wiphy; model.drv.drv_flags = MT_DRV_NAPI_LIFETIME;
	model.primary.dev.refs = 1; model.secondary.dev.refs = hif ? 2 : 1;
	model.hif_ref = hif; model.hif.dev = &model.secondary.dev;
	device.hif2 = hif ? &model.hif : NULL;
	device.mt76.dev = &model.primary.dev; device.mt76.hw = &model.hw; device.mt76.drv = &model.drv;
	device.mt76.wq = &model; device.mt76.init_wiphy = init_wiphy;
	device.mphy.hw = &model.hw; device.mphy.dev = &device.mt76;
	device.mphy.cap.has_2ghz = device.mphy.cap.has_5ghz = device.mphy.cap.has_6ghz = true;
	device.mt76.phys[0] = &device.mphy;
	device.pci_irq[0].vectors = model.vectors[0] = true;
	device.pci_irq[1].vectors = model.vectors[1] = hif;
	INIT_DELAYED_WORK(&device.mt76.scan_work, dummy_work);
	coredump_memdump = memdump;
#if !BASELINE
	mt7996_init_device(&device);
#endif
	cases++;
}
static void release_outer_resources(void)
{
	for (unsigned i=0;i<2;i++) if (model.vectors[i]) pci_free_irq_vectors(i ? &model.secondary : &model.primary);
	if (model.hif_ref) put_device(&model.secondary.dev);
}
static void check_final(void)
{
	CHECK(!model.live && model.free_calls == 1 && !model.registered && !model.led,
	      "every-reached-registration-prefix-unwinds-before-base-free");
	CHECK(!model.early_recovery && !model.null_scheduler, "cold-failure-does-not-run-unready-recovery");
	CHECK(!device.mt76.mcu.res_q && (!device.mt76.queue_ops || model.dma_closes == 1),
	      "reached-MCU-DMA-prefix-cleaned-with-late-response-join");
	CHECK(model.mcu_exits == !!device.mt76.mcu_ops, "MCU-attempt-boundary-not-firmware-success-guess");
	for (unsigned i=0;i<model.allocations;i++) CHECK(!model.allocs[i].live, "all-reached-coredump-allocations-released");
	CHECK(!device.coredump.crash_data, "failed-or-removed-coredump-is-not-published");
	release_outer_resources(); dispose_allocations();
}
static void *cleanup_thread(void *unused)
{
	(void)unused;
#if !BASELINE
	mt7996_cleanup_device(&device);
#endif
	pthread_mutex_lock(&work_lock); model.cleanup_finished = true;
	pthread_cond_broadcast(&work_cond); pthread_mutex_unlock(&work_lock);
	return NULL;
}
int main(void)
{
#if BASELINE
	setup(0, false, false, 23);
	CHECK(probe_registration_tail() == -ENOMEM, "real-coredump-metadata-failure-propagated");
	bool missing_unregister = model.leaked_registration == 1;
	dispose_allocations();
	setup(2, false, true, 24);
	CHECK(probe_registration_tail() == -ENOMEM, "conditional-memdump-failure-propagated");
	bool dangling_coredump = device.coredump.crash_data && !allocation_live(device.coredump.crash_data);
	dispose_allocations();
	setup(0, false, false, 3);
	CHECK(probe_registration_tail() == -ETIMEDOUT, "cold-MCU-timeout-propagated");
	bool early_queue = model.early_recovery != 0;
	dispose_allocations();
	setup(0, false, false, 20);
	CHECK(!probe_registration_tail(), "baseline-worker-error-is-ignored");
	bool null_scheduler = model.null_scheduler == 1;
	dispose_allocations();
	CHECK(missing_unregister && dangling_coredump && early_queue && null_scheduler, "baseline-defects-reproduced");
	printf("{\"characterization_complete\":true,\"cases\":%u,\"missing_unregister\":true,"
	       "\"conditional_dangling_coredump\":true,\"unready_recovery_queued\":true,"
	       "\"ignored_worker_error_null_scheduler\":true,\"hardware\":false}\n", cases);
#else
	for (unsigned family=0;family<3;family++) for (unsigned hif=0;hif<2;hif++)
	for (unsigned mem=0;mem<2;mem++) for (unsigned stage=0;stage<=24;stage++) {
		setup(family, hif, mem, stage);
		int error = probe_registration_tail();
		if (!error) {
			run_work(&device.init_work);
			mt7996_unregister_device(&device);
		} else CHECK(error == -EIO || error == -ENOSPC || error == -ENOMEM || error == -ETIMEDOUT,
			     "original-init-error-propagated");
		check_final();
	}
	for (unsigned prefix=0;prefix<3;prefix++) {
		setup(0, false, false, 0);
		if (prefix) device.mt76.queue_ops = &model;
		if (prefix == 2) device.mt76.mcu_ops = &model;
		mt7996_cleanup_device(&device);
		unsigned exits = model.mcu_exits, dma = model.dma_closes, purges = model.purges;
		mt7996_cleanup_device(&device);
		CHECK(exits == model.mcu_exits && dma == model.dma_closes && purges == model.purges,
		      "serial-repeated-cleanup-does-not-repeat-resource-release");
		mt7996_unregister_device(&device); check_final();
	}
	setup(0, true, false, 0);
	CHECK(!probe_registration_tail(), "concurrent-fixture-registers");
	model.block_init = model.inject_tail = true;
	pthread_t callback, closer;
	CHECK(!pthread_create(&callback, NULL, run_work, &device.init_work), "callback-thread-start");
	pthread_mutex_lock(&work_lock);
	while (!model.entered_init) pthread_cond_wait(&work_cond, &work_lock);
	pthread_mutex_unlock(&work_lock);
	CHECK(!pthread_create(&closer, NULL, cleanup_thread, NULL), "cleanup-thread-start");
	pthread_mutex_lock(&work_lock);
	while (!model.waiting_init && !model.cleanup_finished) pthread_cond_wait(&work_cond, &work_lock);
	CHECK(!model.cleanup_finished && model.live, "cleanup-waits-for-actual-init-callback-tail");
	model.release_init = true; pthread_cond_broadcast(&work_cond);
	pthread_mutex_unlock(&work_lock);
	CHECK(!pthread_join(callback, NULL) && !pthread_join(closer, NULL), "threads-joined");
	mt7996_unregister_device(&device); check_final();
	printf("{\"passed\":true,\"cases\":%u,\"profiles\":12,\"fault_stages\":25,"
	       "\"early_prefixes\":3,\"concurrency_cases\":1,\"kernel_framework_modeled\":true,"
	       "\"physical_drain\":false,\"hardware\":false}\n", cases);
#endif
	return 0;
}
