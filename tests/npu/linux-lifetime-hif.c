// SPDX-License-Identifier: GPL-2.0
/* Real driver-core/devres/link lifecycle; PCI presence and MMIO are synthetic. */
#include <kunit/test.h>
#include <linux/atomic.h>
#include <linux/completion.h>
#include <linux/cpu.h>
#include <linux/delay.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/kthread.h>
#include <linux/module.h>
#include <linux/pci.h>
#include <linux/slab.h>
#include <linux/smp.h>
#include <linux/spinlock.h>

#include "selected-HIF-types.inc"

struct hif_fixture {
	struct pci_dev supplier, consumer;
	struct completion probe_entered, allow_probe, probe_done;
	struct completion consumer_remove_entered, allow_consumer_remove;
	struct completion supplier_remove_entered, allow_supplier_remove;
	struct completion supplier_freed, unbind_started, unbind_done;
	struct completion supplier_released, consumer_released;
	struct task_struct *probe_task, *unbind_task;
	struct device *explicit_supplier;
	void __iomem *maps[1];
	u32 recognition;
	atomic_t sequence;
	unsigned int consumer_remove_seq, supplier_free_seq;
	int helper_result, probe_result, add_result;
	int probe_cpu, unbind_cpu;
	bool hold_probe, hold_consumer_remove, hold_supplier_remove, fail_probe, late_case;
	bool supplier_added, consumer_added, supplier_initialized, consumer_initialized;
	bool supplier_driver_added, consumer_driver_added, bus_added;
};
static struct hif_fixture *active_fixture;
static unsigned int hif_mutation;
module_param(hif_mutation, uint, 0444);
static bool hif_smp;
module_param(hif_smp, bool, 0444);
static LIST_HEAD(hif_list);
static DEFINE_SPINLOCK(hif_lock);
static u32 hif_idx;
static const struct bus_type hif_test_bus;
static int supplier_probe(struct device *dev);
static int supplier_remove(struct device *dev);
static int consumer_probe(struct device *dev);
static int consumer_remove(struct device *dev);
static struct pci_driver mt7996_hif_driver = {
	.driver = { .name = "w1700k-test-supplier", .bus = &hif_test_bus,
		.owner = THIS_MODULE, .probe = supplier_probe, .remove = supplier_remove },
};
static struct device_driver consumer_driver = {
	.name = "w1700k-test-consumer", .bus = &hif_test_bus,
	.owner = THIS_MODULE, .probe = consumer_probe, .remove = consumer_remove,
};

static u32 model_readl(const void __iomem *address)
{
	return READ_ONCE(active_fixture->recognition);
}
static void model_writel(u32 value, void __iomem *address)
{
	WRITE_ONCE(active_fixture->recognition, value);
}
static void __iomem *const *model_iomap_table(struct pci_dev *pdev)
{
	return ((struct hif_fixture *)pdev->dev.platform_data)->maps;
}
static u32 model_bandwidth(enum pci_bus_speed *speed, enum pcie_link_width *width)
{
	*speed = PCIE_SPEED_2_5GT;
	*width = PCIE_LNK_X1;
	return 2500;
}
#undef readl
#undef writel
#define readl model_readl
#define writel model_writel
#define pci_dev_present(table) (active_fixture && active_fixture->supplier_added)
#define pcim_iomap_table model_iomap_table
#define pcie_bandwidth_available(pdev, limiter, speed, width) model_bandwidth(speed, width)
#include "selected-HIF-lookup.inc"
#include "selected-HIF-init.inc"
#include "selected-HIF-init-no-link.inc"
#include "selected-HIF-init-no-state.inc"
#include "selected-HIF-probe.inc"
#include "selected-HIF-remove.inc"
#undef readl
#undef writel
#undef pci_dev_present
#undef pcim_iomap_table
#undef pcie_bandwidth_available

static int hif_match(struct device *dev, const struct device_driver *driver)
{
	struct hif_fixture *fixture = dev->platform_data;

	return (dev == &fixture->supplier.dev && driver == &mt7996_hif_driver.driver) ||
	       (dev == &fixture->consumer.dev && driver == &consumer_driver);
}
static const struct bus_type hif_test_bus = {
	.name = "w1700k-hif-lifetime", .match = hif_match,
};
static void device_released(struct device *dev)
{
	struct hif_fixture *fixture = dev->platform_data;

	complete(dev == &fixture->supplier.dev ? &fixture->supplier_released : &fixture->consumer_released);
}
static void supplier_devres_freed(void *data)
{
	struct hif_fixture *fixture = data;

	WRITE_ONCE(fixture->supplier_free_seq, atomic_inc_return(&fixture->sequence));
	complete(&fixture->supplier_freed);
}
static int supplier_probe(struct device *dev)
{
	struct hif_fixture *fixture = dev->platform_data;
	int error;

	/* Added first, so the marker runs after the later devm HIF allocation frees. */
	error = devm_add_action_or_reset(dev, supplier_devres_freed, fixture);
	if (error)
		return error;
	return mt7996_pci_hif2_probe(&fixture->supplier);
}
static int supplier_remove(struct device *dev)
{
	struct hif_fixture *fixture = dev->platform_data;

	complete(&fixture->supplier_remove_entered);
	if (fixture->hold_supplier_remove)
		wait_for_completion_timeout(&fixture->allow_supplier_remove, 10 * HZ);
	mt7996_hif_remove(&fixture->supplier);
	return 0;
}
static int consumer_probe(struct device *dev)
{
	struct hif_fixture *fixture = dev->platform_data;
	struct mt7996_hif *hif;

	WRITE_ONCE(fixture->probe_cpu, raw_smp_processor_id());
	switch (hif_mutation) {
	case 1: hif = mt7996_pci_init_hif2_no_link(&fixture->consumer); break;
	case 2: hif = mt7996_pci_init_hif2_no_state(&fixture->consumer); break;
	default: hif = mt7996_pci_init_hif2(&fixture->consumer); break;
	}
	fixture->helper_result = IS_ERR(hif) ? PTR_ERR(hif) : hif ? 0 : -ENODEV;
	if (!IS_ERR_OR_NULL(hif))
		fixture->explicit_supplier = hif->dev;
	complete(&fixture->probe_entered);
	if (fixture->hold_probe)
		wait_for_completion_timeout(&fixture->allow_probe, 10 * HZ);
	if (fixture->late_case || fixture->fail_probe || fixture->helper_result) {
		if (fixture->explicit_supplier) {
			put_device(fixture->explicit_supplier);
			fixture->explicit_supplier = NULL;
		}
		/* The synthetic primary stops before radio setup; no deferred retry. */
		fixture->probe_result = -EIO;
		return -EIO;
	}
	fixture->probe_result = 0;
	return 0;
}
static int consumer_remove(struct device *dev)
{
	struct hif_fixture *fixture = dev->platform_data;

	complete(&fixture->consumer_remove_entered);
	if (fixture->hold_consumer_remove)
		wait_for_completion_timeout(&fixture->allow_consumer_remove, 10 * HZ);
	WRITE_ONCE(fixture->consumer_remove_seq, atomic_inc_return(&fixture->sequence));
	if (fixture->explicit_supplier) {
		put_device(fixture->explicit_supplier);
		fixture->explicit_supplier = NULL;
	}
	return 0;
}
static void park_until_stop(void)
{
	set_current_state(TASK_INTERRUPTIBLE);
	while (!kthread_should_stop()) {
		schedule();
		set_current_state(TASK_INTERRUPTIBLE);
	}
	__set_current_state(TASK_RUNNING);
}
static int probe_thread(void *data)
{
	struct hif_fixture *fixture = data;

	fixture->add_result = device_add(&fixture->consumer.dev);
	fixture->consumer_added = !fixture->add_result;
	complete(&fixture->probe_done);
	park_until_stop();
	return 0;
}
static int unbind_thread(void *data)
{
	struct hif_fixture *fixture = data;

	WRITE_ONCE(fixture->unbind_cpu, raw_smp_processor_id());
	complete(&fixture->unbind_started);
	device_release_driver(&fixture->supplier.dev);
	complete(&fixture->unbind_done);
	park_until_stop();
	return 0;
}
static struct task_struct *start_hif_thread(int (*function)(void *), void *data,
					   const char *name, unsigned int cpu)
{
	struct task_struct *task;

	if (!hif_smp)
		return kthread_run(function, data, "%s", name);
	task = kthread_create(function, data, "%s", name);
	if (!IS_ERR(task)) {
		kthread_bind(task, cpu);
		wake_up_process(task);
	}
	return task;
}

static bool start_probe(struct hif_fixture *fixture)
{
	fixture->probe_task = start_hif_thread(probe_thread, fixture, "w1700k-probe", 0);
	if (!IS_ERR(fixture->probe_task))
		return true;
	fixture->probe_task = NULL;
	return false;
}
static bool start_unbind(struct hif_fixture *fixture)
{
	fixture->unbind_task = start_hif_thread(unbind_thread, fixture, "w1700k-unbind", hif_mutation == 3 ? 0 : 1);
	if (!IS_ERR(fixture->unbind_task))
		return true;
	fixture->unbind_task = NULL;
	return false;
}
static bool waited(struct completion *completion)
{
	return !!wait_for_completion_timeout(completion, 5 * HZ);
}
static void fixture_dispose(struct kunit *test, struct hif_fixture *fixture)
{
	bool released = true;
	int probe_cpu, unbind_cpu;

	complete_all(&fixture->allow_probe);
	complete_all(&fixture->allow_consumer_remove);
	complete_all(&fixture->allow_supplier_remove);
	if (fixture->probe_task)
		kthread_stop(fixture->probe_task);
	if (fixture->unbind_task)
		kthread_stop(fixture->unbind_task);
	if (hif_smp) {
		probe_cpu = READ_ONCE(fixture->probe_cpu);
		unbind_cpu = READ_ONCE(fixture->unbind_cpu);
		KUNIT_EXPECT_EQ_MSG(test, probe_cpu, 0, "HIF probe must execute on CPU 0");
		KUNIT_EXPECT_EQ_MSG(test, unbind_cpu, 1, "HIF unbind must execute on CPU 1");
		pr_info("# W1700K_SMP {\"kind\":\"hif\",\"case\":\"%s\",\"probe\":%d,\"unbind\":%d,\"online\":%u}\n",
			test->name, probe_cpu, unbind_cpu, num_online_cpus());
	}
	if (fixture->consumer_added)
		device_unregister(&fixture->consumer.dev);
	else if (fixture->consumer_initialized)
		put_device(&fixture->consumer.dev);
	if (fixture->supplier_added)
		device_unregister(&fixture->supplier.dev);
	else if (fixture->supplier_initialized)
		put_device(&fixture->supplier.dev);
	if (fixture->consumer_driver_added)
		driver_unregister(&consumer_driver);
	if (fixture->supplier_driver_added)
		driver_unregister(&mt7996_hif_driver.driver);
	if (fixture->bus_added)
		bus_unregister(&hif_test_bus);
	if (fixture->consumer_initialized)
		released &= waited(&fixture->consumer_released);
	if (fixture->supplier_initialized)
		released &= waited(&fixture->supplier_released);
	KUNIT_EXPECT_TRUE_MSG(test, released, "all real device references must be released");
	KUNIT_EXPECT_TRUE(test, list_empty(&hif_list));
	active_fixture = NULL;
	if (released)
		kfree(fixture);
	/* On a failed lifetime assertion, retain storage rather than free live refs. */
}
static struct hif_fixture *fixture_create(struct kunit *test)
{
	struct hif_fixture *fixture;
	int error;

	if (hif_smp && (!IS_ENABLED(CONFIG_SMP) || !cpu_online(0) || !cpu_online(1))) {
		KUNIT_FAIL(test, "two online CPUs are required for the HIF SMP fixture");
		return NULL;
	}
	fixture = kzalloc(sizeof(*fixture), GFP_KERNEL);
	if (!fixture)
		return NULL;
	fixture->probe_cpu = -1;
	fixture->unbind_cpu = -1;
#define INIT_GATE(name) init_completion(&fixture->name)
	INIT_GATE(probe_entered); INIT_GATE(allow_probe); INIT_GATE(probe_done);
	INIT_GATE(consumer_remove_entered); INIT_GATE(allow_consumer_remove);
	INIT_GATE(supplier_remove_entered); INIT_GATE(allow_supplier_remove);
	INIT_GATE(supplier_freed); INIT_GATE(unbind_started); INIT_GATE(unbind_done);
	INIT_GATE(supplier_released); INIT_GATE(consumer_released);
#undef INIT_GATE
	fixture->maps[0] = (void __iomem *)0x1000UL;
	active_fixture = fixture;
	spin_lock_bh(&hif_lock);
	hif_idx = 0;
	spin_unlock_bh(&hif_lock);
	error = bus_register(&hif_test_bus);
	if (error)
		goto fail;
	fixture->bus_added = true;
	error = driver_register(&mt7996_hif_driver.driver);
	if (error)
		goto fail;
	fixture->supplier_driver_added = true;
	error = driver_register(&consumer_driver);
	if (error)
		goto fail;
	fixture->consumer_driver_added = true;
	device_initialize(&fixture->supplier.dev);
	fixture->supplier_initialized = true;
	fixture->supplier.dev.bus = &hif_test_bus;
	fixture->supplier.dev.release = device_released;
	fixture->supplier.dev.platform_data = fixture;
	error = dev_set_name(&fixture->supplier.dev, "w1700k-supplier");
	if (error)
		goto fail;
	error = device_add(&fixture->supplier.dev);
	if (error)
		goto fail;
	fixture->supplier_added = true;
	if (READ_ONCE(fixture->supplier.dev.driver) != &mt7996_hif_driver.driver)
		goto fail;
	device_initialize(&fixture->consumer.dev);
	fixture->consumer_initialized = true;
	fixture->consumer.dev.bus = &hif_test_bus;
	fixture->consumer.dev.release = device_released;
	fixture->consumer.dev.platform_data = fixture;
	error = dev_set_name(&fixture->consumer.dev, "w1700k-consumer");
	if (error)
		goto fail;
	return fixture;
fail:
	KUNIT_FAIL(test, "real driver-core fixture registration failed");
	fixture_dispose(test, fixture);
	return NULL;
}

static void k_probe_and_remove_join(struct kunit *test)
{
	struct hif_fixture *fixture = fixture_create(test);

	KUNIT_ASSERT_NOT_NULL(test, fixture);
	fixture->hold_probe = true;
	fixture->hold_consumer_remove = true;
	if (!start_probe(fixture) || !waited(&fixture->probe_entered)) {
		KUNIT_FAIL(test, "consumer probe did not enter");
		goto out;
	}
	KUNIT_EXPECT_EQ(test, fixture->helper_result, 0);
	if (!start_unbind(fixture) || !waited(&fixture->unbind_started)) {
		KUNIT_FAIL(test, "supplier unbind did not start");
		goto out;
	}
	KUNIT_EXPECT_FALSE_MSG(test, wait_for_completion_timeout(&fixture->supplier_freed, HZ / 5),
		"supplier devres must outlive probing consumer");
	complete_all(&fixture->allow_probe);
	if (!waited(&fixture->probe_done) || !waited(&fixture->consumer_remove_entered)) {
		KUNIT_FAIL(test, "managed dependency must trigger consumer remove");
		goto out;
	}
	KUNIT_EXPECT_FALSE_MSG(test, wait_for_completion_timeout(&fixture->supplier_freed, HZ / 5),
		"supplier devres must outlive consumer remove");
	complete_all(&fixture->allow_consumer_remove);
	KUNIT_EXPECT_TRUE(test, waited(&fixture->unbind_done));
	KUNIT_EXPECT_TRUE(test, completion_done(&fixture->supplier_freed));
	KUNIT_EXPECT_LT_MSG(test, fixture->consumer_remove_seq, fixture->supplier_free_seq,
		"consumer teardown must precede supplier devres");
out:
	fixture_dispose(test, fixture);
}
static void k_already_unbinding_defers(struct kunit *test)
{
	struct hif_fixture *fixture = fixture_create(test);

	KUNIT_ASSERT_NOT_NULL(test, fixture);
	fixture->late_case = true;
	fixture->hold_supplier_remove = true;
	if (!start_unbind(fixture) || !waited(&fixture->supplier_remove_entered)) {
		KUNIT_FAIL(test, "supplier remove did not enter");
		goto out;
	}
	if (!start_probe(fixture) || !waited(&fixture->probe_done)) {
		KUNIT_FAIL(test, "late consumer probe did not finish");
		goto out;
	}
	KUNIT_EXPECT_EQ_MSG(test, fixture->helper_result, -EPROBE_DEFER,
		"an already-unbinding supplier must be rejected");
	KUNIT_EXPECT_FALSE(test, completion_done(&fixture->supplier_freed));
	complete_all(&fixture->allow_supplier_remove);
	KUNIT_EXPECT_TRUE(test, waited(&fixture->unbind_done));
out:
	fixture_dispose(test, fixture);
}
static void k_failed_probe_drops_link(struct kunit *test)
{
	struct hif_fixture *fixture = fixture_create(test);

	KUNIT_ASSERT_NOT_NULL(test, fixture);
	fixture->fail_probe = true;
	fixture->hold_probe = true;
	if (!start_probe(fixture) || !waited(&fixture->probe_entered) ||
	    !start_unbind(fixture) || !waited(&fixture->unbind_started)) {
		KUNIT_FAIL(test, "failed-probe interleaving did not start");
		goto out;
	}
	KUNIT_EXPECT_FALSE_MSG(test, wait_for_completion_timeout(&fixture->supplier_freed, HZ / 5),
		"failed probe must finish before supplier devres");
	complete_all(&fixture->allow_probe);
	KUNIT_EXPECT_TRUE(test, waited(&fixture->probe_done));
	KUNIT_EXPECT_EQ(test, fixture->helper_result, 0);
	KUNIT_EXPECT_EQ(test, fixture->probe_result, -EIO);
	KUNIT_EXPECT_TRUE(test, waited(&fixture->unbind_done));
	KUNIT_EXPECT_FALSE(test, completion_done(&fixture->consumer_remove_entered));
	KUNIT_EXPECT_TRUE(test, completion_done(&fixture->supplier_freed));
out:
	fixture_dispose(test, fixture);
}
static struct kunit_case hif_cases[] = {
	KUNIT_CASE(k_probe_and_remove_join), KUNIT_CASE(k_already_unbinding_defers),
	KUNIT_CASE(k_failed_probe_drops_link), {}
};
static struct kunit_suite hif_suite = {
	.name = "w1700k-linux-hif", .test_cases = hif_cases,
};
kunit_test_suite(hif_suite);
MODULE_LICENSE("GPL");
