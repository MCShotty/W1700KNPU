// SPDX-License-Identifier: GPL-2.0
/* Actual selected driver C and Linux work APIs; radio/MCU/DMA remain models. */
#include <kunit/test.h>
#include <linux/atomic.h>
#include <linux/completion.h>
#include <linux/cpu.h>
#include <linux/delay.h>
#include <linux/err.h>
#include <linux/kthread.h>
#include <linux/list.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/slab.h>
#include <linux/smp.h>
#include <linux/spinlock.h>
#include <linux/wait.h>
#include <linux/workqueue.h>

#include "selected-work-state.inc"

enum work_kind { WK_NONE, WK_INIT, WK_RC, WK_DUMP, WK_RESET, WK_WED,
		 WK_SCAN, WK_MAC, WK_ROC, WK_EXTRA_MAC, WK_EXTRA_ROC };
struct mt7996_dev;
struct mt76_phy {
	void *priv;
	unsigned long state;
	struct delayed_work mac_work, roc_work;
};
struct model_tx_worker { bool parked; };
struct mt76_dev {
	struct mt76_phy phy;
	void *queue_ops, *mcu_ops;
	struct { unsigned int res_q; } mcu;
	struct delayed_work scan_work;
	struct model_tx_worker tx_worker;
	struct { unsigned int wed; } mmio;
};
struct mt7996_phy { struct mt7996_dev *dev; struct mt76_phy *mt76; };
struct mt7996_dev {
	union { struct mt76_dev mt76; struct mt76_phy mphy; };
	struct mt7996_phy phy, extra;
	struct mt76_phy extra_mphy;
	struct mt7996_phy *phys[2];
	struct work_struct init_work, rc_work, reset_work, dump_work;
	struct list_head sta_rc_list, twt_list;
	wait_queue_head_t reset_wait;
	struct mutex dump_mutex;
	struct {
		struct work_struct work;
		struct list_head poll_list;
		spinlock_t lock;
	} wed_rro;
	struct { bool hw_init_done; } recovery;
	bool cleanup_started;
	struct workqueue_struct *test_wq;
	struct completion entered, release, cleanup_entered, cleanup_done;
	atomic_t running, invariant_bad, self_queued, self_attempted;
	int callback_cpu, cleanup_cpu;
	enum work_kind held;
	unsigned int retired, mcu_exits, dma_cleanups, late_purges;
};
#define mt7996_for_each_phy(dev, p) \
	for (unsigned int _band = 0; _band < ARRAY_SIZE((dev)->phys); _band++) \
		if (((p) = (dev)->phys[_band]))

static unsigned int work_mutation;
module_param(work_mutation, uint, 0444);
static bool work_smp;
module_param(work_smp, bool, 0444);

static void work_callback(struct mt7996_dev *dev, enum work_kind kind)
{
	if (READ_ONCE(dev->held) != kind)
		return;
	WRITE_ONCE(dev->callback_cpu, raw_smp_processor_id());
	atomic_inc(&dev->running);
	complete(&dev->entered);
	if (!wait_for_completion_timeout(&dev->release, 10 * HZ))
		atomic_set(&dev->invariant_bad, 1);
	if (kind == WK_INIT && !atomic_cmpxchg(&dev->self_attempted, 0, 1))
		atomic_set(&dev->self_queued, queue_work(dev->test_wq, &dev->init_work));
	atomic_dec(&dev->running);
}

static void mt7996_mac_sta_rc_work(struct work_struct *work)
{ work_callback(container_of(work, struct mt7996_dev, rc_work), WK_RC); }
static void mt7996_mac_reset_work(struct work_struct *work)
{ work_callback(container_of(work, struct mt7996_dev, reset_work), WK_RESET); }
static void mt7996_mac_dump_work(struct work_struct *work)
{ work_callback(container_of(work, struct mt7996_dev, dump_work), WK_DUMP); }
static void mt7996_wed_rro_work(struct work_struct *work)
{ work_callback(container_of(work, struct mt7996_dev, wed_rro.work), WK_WED); }
static void model_scan_work(struct work_struct *work)
{
	struct mt76_dev *mdev = container_of(to_delayed_work(work), struct mt76_dev, scan_work);
	work_callback(container_of(mdev, struct mt7996_dev, mt76), WK_SCAN);
}
static void mt7996_mac_work(struct work_struct *work)
{
	struct mt76_phy *mphy = container_of(to_delayed_work(work), struct mt76_phy, mac_work);
	struct mt7996_phy *phy = mphy->priv;
	work_callback(phy->dev, phy == &phy->dev->extra ? WK_EXTRA_MAC : WK_MAC);
}
static void model_roc_work(struct work_struct *work)
{
	struct mt76_phy *mphy = container_of(to_delayed_work(work), struct mt76_phy, roc_work);
	struct mt7996_phy *phy = mphy->priv;
	work_callback(phy->dev, phy == &phy->dev->extra ? WK_EXTRA_ROC : WK_ROC);
}
static void mt7996_mcu_set_eeprom(struct mt7996_dev *dev) { work_callback(dev, WK_INIT); }
static void mt7996_mac_init(struct mt7996_dev *dev) { }
static void mt7996_txbf_init(struct mt7996_dev *dev) { }
static bool is_mt7990(struct mt76_dev *dev) { return false; }
static void mt7996_mcu_set_dup_wtbl(struct mt7996_dev *dev) { }

void mt7996_init_device(struct mt7996_dev *dev);
void mt7996_cleanup_device(struct mt7996_dev *dev);
#include "selected-work-init.inc"
#include "selected-work-constructor.inc"
#include "selected-work-constructor-early.inc"

/* These are explicit non-workqueue boundaries, not physical cleanup proof. */
static void mt7996_npu_rro_reset_close(struct mt7996_dev *dev)
{ complete(&dev->cleanup_entered); }
static void mt7996_npu_rro_reset_join(struct mt7996_dev *dev) { }
static struct mt7996_phy *mt7996_phy3(struct mt7996_dev *dev) { return NULL; }
static struct mt7996_phy *mt7996_phy2(struct mt7996_dev *dev) { return dev->phys[1]; }
static void mt7996_unregister_phy(struct mt7996_phy *phy) { }
static void mt7996_unregister_thermal(struct mt7996_phy *phy) { }
static void mt76_unregister_device(struct mt76_dev *mdev) { }
static void mt76_worker_disable(struct model_tx_worker *worker) { worker->parked = true; }
static void mt7996_coredump_unregister(struct mt7996_dev *dev) { }
static void mt7996_mcu_exit(struct mt7996_dev *dev) { dev->mcu_exits++; }
static void mt7996_pci_shutdown_irqs(struct mt7996_dev *dev) { dev->mt76.mcu.res_q++; }
static void mt76_npu_shutdown_irqs(struct mt76_dev *dev) { }
static void mt76_napi_cleanup(struct mt76_dev *dev) { }
static void model_response_purge(unsigned int *queue) { *queue = 0; }
static void mt7996_tx_token_put(struct mt7996_dev *dev)
{
	if (atomic_read(&dev->running))
		atomic_set(&dev->invariant_bad, 1);
	dev->retired++;
}
static void mt7996_dma_cleanup(struct mt7996_dev *dev) { dev->dma_cleanups++; }
static void mt7996_wed_rro_free(struct mt7996_dev *dev) { }
static bool mt7996_has_hwrro(struct mt7996_dev *dev) { return false; }
static bool mtk_wed_device_active(void *dev) { return false; }
static void mt7996_rro_msdu_page_map_free(struct mt7996_dev *dev) { }

#define skb_queue_purge model_response_purge
#include "selected-work-cleanup.inc"
#include "selected-work-cleanup-cancel.inc"
#include "selected-work-cleanup-missing-rc.inc"
#include "selected-work-cleanup-cancel-scan.inc"
#undef skb_queue_purge

static void selected_cleanup(struct mt7996_dev *dev)
{
	switch (work_mutation) {
	case 1: mt7996_cleanup_cancel(dev); break;
	case 2: mt7996_cleanup_missing_rc(dev); break;
	case 3: mt7996_cleanup_cancel_scan(dev); break;
	default: mt7996_cleanup_device(dev); break;
	}
}

static int cleanup_thread(void *data)
{
	struct mt7996_dev *dev = data;

	WRITE_ONCE(dev->cleanup_cpu, raw_smp_processor_id());
	selected_cleanup(dev);
	complete(&dev->cleanup_done);
	set_current_state(TASK_INTERRUPTIBLE);
	while (!kthread_should_stop()) {
		schedule();
		set_current_state(TASK_INTERRUPTIBLE);
	}
	__set_current_state(TASK_RUNNING);
	return 0;
}

static struct mt7996_dev *fixture_new(bool registered)
{
	struct mt7996_dev *dev;

	if (work_smp && (!IS_ENABLED(CONFIG_SMP) || !cpu_online(0) || !cpu_online(1)))
		return NULL;
	dev = kzalloc(sizeof(*dev), GFP_KERNEL);
	if (!dev)
		return NULL;
	dev->callback_cpu = -1;
	dev->cleanup_cpu = -1;
	init_completion(&dev->entered);
	init_completion(&dev->release);
	init_completion(&dev->cleanup_entered);
	init_completion(&dev->cleanup_done);
	INIT_DELAYED_WORK(&dev->mt76.scan_work, model_scan_work);
	dev->test_wq = work_smp ? alloc_workqueue("w1700k-lifetime", WQ_PERCPU, 1) :
		alloc_ordered_workqueue("w1700k-lifetime", 0);
	if (!dev->test_wq) {
		kfree(dev);
		return NULL;
	}
	if (work_mutation == 4)
		mt7996_init_device_early(dev);
	else
		mt7996_init_device(dev);
	dev->phys[0] = &dev->phy;
	if (registered) {
		INIT_DELAYED_WORK(&dev->mphy.roc_work, model_roc_work);
		set_bit(MT76_STATE_REGISTERED, &dev->mphy.state);
		dev->extra.dev = dev;
		dev->extra.mt76 = &dev->extra_mphy;
		dev->extra_mphy.priv = &dev->extra;
		INIT_DELAYED_WORK(&dev->extra_mphy.mac_work, mt7996_mac_work);
		INIT_DELAYED_WORK(&dev->extra_mphy.roc_work, model_roc_work);
		set_bit(MT76_STATE_REGISTERED, &dev->extra_mphy.state);
		dev->phys[1] = &dev->extra;
		dev->mt76.queue_ops = dev;
		dev->mt76.mcu_ops = dev;
		enable_work(&dev->dump_work);
		enable_work(&dev->reset_work);
		WRITE_ONCE(dev->recovery.hw_init_done, true);
	}
	return dev;
}

static void fixture_free(struct mt7996_dev *dev, bool registered)
{
	complete_all(&dev->release);
	WRITE_ONCE(dev->held, WK_NONE);
	disable_work_sync(&dev->init_work);
	disable_work_sync(&dev->rc_work);
	disable_work_sync(&dev->dump_work);
	disable_work_sync(&dev->reset_work);
	disable_work_sync(&dev->wed_rro.work);
	disable_delayed_work_sync(&dev->mt76.scan_work);
	disable_delayed_work_sync(&dev->mphy.mac_work);
	if (registered) {
		disable_delayed_work_sync(&dev->mphy.roc_work);
		disable_delayed_work_sync(&dev->extra_mphy.mac_work);
		disable_delayed_work_sync(&dev->extra_mphy.roc_work);
	}
	destroy_workqueue(dev->test_wq);
	kfree(dev);
}

static void k_ctor_admission(struct kunit *test)
{
	struct mt7996_dev *dev = fixture_new(false);
	bool reset, dump;

	KUNIT_ASSERT_NOT_NULL(test, dev);
	reset = queue_work(dev->test_wq, &dev->reset_work);
	dump = queue_work(dev->test_wq, &dev->dump_work);
	selected_cleanup(dev);
	KUNIT_EXPECT_FALSE_MSG(test, reset, "cold reset admission must be closed");
	KUNIT_EXPECT_FALSE_MSG(test, dump, "cold dump admission must be closed");
	KUNIT_EXPECT_EQ(test, dev->mcu_exits, 0U);
	KUNIT_EXPECT_EQ(test, dev->dma_cleanups, 0U);
	KUNIT_EXPECT_EQ(test, dev->mt76.mcu.res_q, 0U);
	if (work_smp)
		pr_info("# W1700K_SMP {\"kind\":\"ctor\",\"case\":\"%s\",\"online\":%u}\n",
			test->name, num_online_cpus());
	fixture_free(dev, false);
}

static bool work_disabled(struct work_struct *work)
{
	unsigned long data = atomic_long_read(&work->data);

	/* Observe the pinned kernel's real off-queue disable encoding, never set it. */
	return !(data & WORK_STRUCT_PWQ) && (data & WORK_OFFQ_DISABLE_MASK);
}

static void run_join_case(struct kunit *test, enum work_kind kind)
{
	struct mt7996_dev *dev = fixture_new(true);
	struct work_struct *work;
	struct delayed_work *delayed = NULL;
	struct task_struct *task = NULL;
	unsigned long deadline;
	bool queued, after;
	int callback_cpu, cleanup_cpu;
	unsigned int retired;

	KUNIT_ASSERT_NOT_NULL(test, dev);
	switch (kind) {
	case WK_INIT: work = &dev->init_work; break;
	case WK_RC: work = &dev->rc_work; break;
	case WK_DUMP: work = &dev->dump_work; break;
	case WK_RESET: work = &dev->reset_work; break;
	case WK_WED: work = &dev->wed_rro.work; break;
	case WK_SCAN: delayed = &dev->mt76.scan_work; work = &delayed->work; break;
	case WK_MAC: delayed = &dev->mphy.mac_work; work = &delayed->work; break;
	case WK_ROC: delayed = &dev->mphy.roc_work; work = &delayed->work; break;
	case WK_EXTRA_MAC: delayed = &dev->extra_mphy.mac_work; work = &delayed->work; break;
	case WK_EXTRA_ROC: delayed = &dev->extra_mphy.roc_work; work = &delayed->work; break;
	default: fixture_free(dev, true); KUNIT_FAIL(test, "invalid work kind"); return;
	}
	WRITE_ONCE(dev->held, kind);
	if (work_smp)
		queued = delayed ? queue_delayed_work_on(0, dev->test_wq, delayed, 0) :
			queue_work_on(0, dev->test_wq, work);
	else
		queued = delayed ? queue_delayed_work(dev->test_wq, delayed, 0) :
			queue_work(dev->test_wq, work);
	KUNIT_EXPECT_TRUE(test, queued);
	if (!queued || !wait_for_completion_timeout(&dev->entered, 5 * HZ)) {
		KUNIT_FAIL(test, "work callback did not enter");
		goto out;
	}
	if (work_smp) {
		task = kthread_create(cleanup_thread, dev, "w1700k-cleanup");
		if (!IS_ERR(task)) {
			kthread_bind(task, work_mutation == 5 ? 0 : 1);
			wake_up_process(task);
		}
	} else {
		task = kthread_run(cleanup_thread, dev, "w1700k-cleanup");
	}
	if (IS_ERR(task)) {
		KUNIT_FAIL(test, "cleanup kthread creation failed");
		task = NULL;
		goto out;
	}
	if (!wait_for_completion_timeout(&dev->cleanup_entered, 5 * HZ)) {
		KUNIT_FAIL(test, "cleanup did not enter");
		goto out;
	}
	deadline = jiffies + 5 * HZ;
	while (!work_disabled(work) && !completion_done(&dev->cleanup_done) && time_before(jiffies, deadline))
		msleep(1);
	KUNIT_EXPECT_FALSE_MSG(test, completion_done(&dev->cleanup_done), "cleanup must wait for held callback");
	KUNIT_EXPECT_EQ(test, READ_ONCE(dev->retired), 0U);
	complete_all(&dev->release);
	if (!wait_for_completion_timeout(&dev->cleanup_done, 5 * HZ)) {
		KUNIT_FAIL(test, "cleanup did not finish after callback release");
		goto out;
	}
	kthread_stop(task);
	task = NULL;
	if (work_smp) {
		callback_cpu = READ_ONCE(dev->callback_cpu);
		cleanup_cpu = READ_ONCE(dev->cleanup_cpu);
		KUNIT_EXPECT_EQ_MSG(test, callback_cpu, 0, "held work must execute on CPU 0");
		KUNIT_EXPECT_EQ_MSG(test, cleanup_cpu, 1, "cleanup must execute on CPU 1");
		pr_info("# W1700K_SMP {\"kind\":\"work\",\"case\":\"%s\",\"callback\":%d,\"cleanup\":%d,\"online\":%u}\n",
			test->name, callback_cpu, cleanup_cpu, num_online_cpus());
	}
	KUNIT_EXPECT_EQ_MSG(test, atomic_read(&dev->invariant_bad), 0, "resources must outlive held callback");
	KUNIT_EXPECT_EQ(test, atomic_read(&dev->self_queued), 0);
	WRITE_ONCE(dev->held, WK_NONE);
	after = delayed ? queue_delayed_work(dev->test_wq, delayed, 0) : queue_work(dev->test_wq, work);
	KUNIT_EXPECT_FALSE_MSG(test, after, "work must reject queue after cleanup");
	KUNIT_EXPECT_TRUE(test, dev->mt76.tx_worker.parked);
	KUNIT_EXPECT_EQ(test, dev->mt76.mcu.res_q, 0U);
	KUNIT_EXPECT_EQ(test, dev->mcu_exits, 1U);
	KUNIT_EXPECT_EQ(test, dev->dma_cleanups, 1U);
	retired = dev->retired;
	selected_cleanup(dev);
	KUNIT_EXPECT_EQ(test, dev->retired, retired);
out:
	complete_all(&dev->release);
	if (task)
		kthread_stop(task);
	fixture_free(dev, true);
}

static void k_init_joins(struct kunit *test) { run_join_case(test, WK_INIT); }
static void k_rc_joins(struct kunit *test) { run_join_case(test, WK_RC); }
static void k_dump_joins(struct kunit *test) { run_join_case(test, WK_DUMP); }
static void k_reset_joins(struct kunit *test) { run_join_case(test, WK_RESET); }
static void k_wed_joins(struct kunit *test) { run_join_case(test, WK_WED); }
static void k_scan_joins(struct kunit *test) { run_join_case(test, WK_SCAN); }
static void k_mac_joins(struct kunit *test) { run_join_case(test, WK_MAC); }
static void k_roc_joins(struct kunit *test) { run_join_case(test, WK_ROC); }
static void k_extra_mac_joins(struct kunit *test) { run_join_case(test, WK_EXTRA_MAC); }
static void k_extra_roc_joins(struct kunit *test) { run_join_case(test, WK_EXTRA_ROC); }

static struct kunit_case work_cases[] = {
	KUNIT_CASE(k_ctor_admission), KUNIT_CASE(k_init_joins), KUNIT_CASE(k_rc_joins),
	KUNIT_CASE(k_dump_joins), KUNIT_CASE(k_reset_joins), KUNIT_CASE(k_wed_joins),
	KUNIT_CASE(k_scan_joins), KUNIT_CASE(k_mac_joins), KUNIT_CASE(k_roc_joins),
	KUNIT_CASE(k_extra_mac_joins), KUNIT_CASE(k_extra_roc_joins), {}
};
static struct kunit_suite work_suite = {
	.name = "w1700k-linux-work",
	.test_cases = work_cases,
};
kunit_test_suite(work_suite);
MODULE_LICENSE("GPL");
