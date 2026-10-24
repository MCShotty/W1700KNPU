/* Selected actual HIF2 and driver-core C, with explicit framework/MMIO models. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint32_t u32;
#define CHECK(ok, message) assert((ok) && message)
#define BIT(n) (1U << (n))
#define GFP_KERNEL 0
#define EPROBE_DEFER 517
#define MT_PCIE_RECOG_ID 0
#define MT_PCIE_RECOG_ID_MASK 0x7fffffffU
#define MT_PCIE_RECOG_ID_SEM BIT(31)
#define READ_ONCE(v) (v)
#define WRITE_ONCE(v, x) ((v) = (x))
#define ERR_PTR(v) ((void *)(intptr_t)(v))
#define IS_ERR(v) ((uintptr_t)(v) >= (uintptr_t)-4095)
#define PTR_ERR(v) ((int)(intptr_t)(v))
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
struct list_head { struct list_head *next, *prev; };
#define LIST_HEAD(name) struct list_head name = { &(name), &(name) }
#define INIT_LIST_HEAD(p) do { (p)->next = (p); (p)->prev = (p); } while (0)
#define list_for_each_entry(pos, head, member) \
	for (pos = container_of((head)->next, __typeof__(*pos), member); \
	     &pos->member != (head); \
	     pos = container_of(pos->member.next, __typeof__(*pos), member))
static void link_insert(struct list_head *node, struct list_head *head)
{
	node->next = head->next;
	node->prev = head;
	head->next->prev = node;
	head->next = node;
}
static void link_remove(struct list_head *node)
{
	node->next->prev = node->prev;
	node->prev->next = node->next;
	INIT_LIST_HEAD(node);
}
enum device_link_state { DL_STATE_NONE, DL_STATE_DORMANT, DL_STATE_AVAILABLE,
	DL_STATE_CONSUMER_PROBE, DL_STATE_ACTIVE, DL_STATE_SUPPLIER_UNBIND };
enum { DL_DEV_NO_DRIVER, DL_DEV_PROBING, DL_DEV_DRIVER_BOUND, DL_DEV_UNBINDING };
enum { DL_FLAG_MANAGED = BIT(0), DL_FLAG_AUTOREMOVE_CONSUMER = BIT(1),
	DL_FLAG_STATELESS = BIT(2), DL_FLAG_SYNC_STATE_ONLY = BIT(3) };
struct device_driver { int id; };
struct device {
	struct device *parent;
	struct device_driver *driver;
	void *driver_data;
	int refs;
	struct { int status; struct list_head consumers; } links;
};
struct device_link {
	struct device *consumer, *supplier;
	struct list_head s_node;
	enum device_link_state status;
	unsigned flags;
};
struct pci_device_id { unsigned device; };
struct pci_dev { struct device dev; void *maps[1]; int irq; };
struct { struct device_driver driver; } mt7996_hif_driver;
static struct device_driver other_driver;
struct mt7996_hif {
	struct list_head list;
	struct device *dev;
	void *regs;
	int irq, speed, width;
};
static const struct pci_device_id mt7996_hif_device_table[] = {{1}, {0}};
static LIST_HEAD(hif_list);
static int hif_lock, links_lock;
static u32 hif_idx;
enum gap { GAP_NONE, GAP_UNBIND_STARTED, GAP_REMOVED, GAP_OTHER_DRIVER,
	GAP_REBOUND, GAP_NULL_DATA, GAP_WRONG_OWNER, GAP_WRONG_ID };
static struct {
	struct pci_dev primary, secondary;
	struct mt7996_hif *hif;
	struct device_link link;
	u32 primary_reg, secondary_reg;
	bool live, present, echo, alloc_fail, link_fail, link_exists, pending_gap;
	bool gap_done, expected_driver, probe_fail, bound, explicit_ref;
	bool consumer_released, supplier_released;
	enum gap gap;
	unsigned data_reads, reg_reads, links_added, waits, releases;
} model;
static unsigned cases;
static void inject_gap(void);
static void spin_lock_bh(int *lock)
{
	CHECK(lock == &hif_lock && !*lock, "HIF-list-lock-owned-once");
	*lock = 1;
}
static void spin_unlock_bh(int *lock)
{
	CHECK(lock == &hif_lock && *lock, "HIF-list-unlock-owned");
	*lock = 0;
	if (model.pending_gap) {
		model.pending_gap = false;
		inject_gap();
	}
}
static void list_add(struct list_head *node, struct list_head *head)
{
	CHECK(hif_lock && head == &hif_list, "HIF-list-publication-locked");
	CHECK(model.secondary.dev.driver_data == model.hif && model.hif->regs == &model.secondary_reg &&
	      model.hif->dev == &model.secondary.dev && model.hif->irq == model.secondary.irq &&
	      model.hif->speed == 4 && model.hif->width == 2,
	      "HIF-drvdata-and-resources-ready-before-list-publication");
	link_insert(node, head);
}
static void list_del_init(struct list_head *node)
{
	CHECK(hif_lock, "HIF-list-removal-uses-lookup-lock");
	link_remove(node);
}
static struct device *get_device(struct device *dev)
{
	CHECK(dev && dev->refs >= 1, "only-live-device-reference-acquired");
	dev->refs++;
	if (hif_lock && dev == &model.secondary.dev) {
		model.explicit_ref = true;
		model.pending_gap = !model.gap_done;
	}
	return dev;
}
static void put_device(struct device *dev)
{
	CHECK(dev && dev->refs > 1, "only-owned-device-reference-released");
	dev->refs--;
}
static void **pcim_iomap_table(struct pci_dev *dev) { return dev->maps; }
static bool pci_dev_present(const struct pci_device_id *ids)
{
	CHECK(ids == mt7996_hif_device_table, "presence-query-uses-HIF-ID-table");
	return model.present;
}
static u32 readl(void *address)
{
	CHECK(address == &model.secondary_reg && model.live, "no-released-HIF-MMIO-access");
	CHECK(hif_lock || (model.link_exists && model.link.status == DL_STATE_CONSUMER_PROBE &&
	      model.secondary.dev.driver == &mt7996_hif_driver.driver),
	      "HIF-MMIO-has-list-lock-or-qualified-driver-pin");
	model.reg_reads++;
	return *(u32 *)address;
}
static void writel(u32 value, void *address)
{
	CHECK(address == &model.primary_reg && !hif_lock &&
	      (value & MT_PCIE_RECOG_ID_SEM), "recognition-write-keeps-semaphore");
	model.primary_reg = value;
	if (model.echo && model.live) model.secondary_reg = value;
}
static void *devm_kzalloc(struct device *dev, size_t size, int flags)
{
	CHECK(dev == &model.secondary.dev && size == sizeof(*model.hif) && !flags,
	      "modeled-HIF-devres-owner");
	if (model.alloc_fail) return NULL;
	CHECK(!model.hif, "old-HIF-devres-retired-before-new-probe");
	model.hif = calloc(1, size);
	CHECK(model.hif, "host-allocation");
	model.live = true;
	return model.hif;
}
static void pci_set_drvdata(struct pci_dev *dev, void *data) { dev->dev.driver_data = data; }
static void *pci_get_drvdata(struct pci_dev *dev) { return dev->dev.driver_data; }
static void pcie_bandwidth_available(struct pci_dev *dev, void *unused, int *speed, int *width)
{ (void)dev; (void)unused; *speed = 4; *width = 2; }
static void *dev_get_drvdata(struct device *dev)
{
	CHECK(dev == &model.secondary.dev && model.link_exists &&
	      (model.link.flags & DL_FLAG_MANAGED) &&
	      model.link.status == DL_STATE_CONSUMER_PROBE,
	      "supplier-data-read-only-after-qualified-managed-link");
	CHECK(dev->driver == &mt7996_hif_driver.driver,
	      "supplier-driver-identity-checked-before-drvdata");
	model.data_reads++;
	return dev->driver_data;
}
static void device_links_write_lock(void)
{ CHECK(!links_lock, "device-links-lock-not-recursive"); links_lock = 1; }
static void device_links_write_unlock(void)
{ CHECK(links_lock, "device-links-lock-owned"); links_lock = 0; }
static bool device_link_test(struct device_link *link, unsigned flags) { return link->flags & flags; }
#include "selected-link-init.inc"
static struct device_link *device_link_add(struct device *consumer, struct device *supplier, unsigned flags)
{
	CHECK(!hif_lock && consumer == &model.primary.dev && supplier == &model.secondary.dev,
	      "device-link-created-outside-HIF-spinlock");
	CHECK(supplier->refs == 2, "lookup-keeps-device-through-link-creation");
	if (model.link_fail) return NULL;
	CHECK(!model.link_exists, "one-link-per-test-consumer");
	model.link_exists = true;
	model.links_added++;
	model.link = (struct device_link){ .consumer = consumer, .supplier = supplier,
		.flags = flags | ((flags & DL_FLAG_STATELESS) ? 0 : DL_FLAG_MANAGED) };
	get_device(consumer);
	get_device(supplier);
	link_insert(&model.link.s_node, &supplier->links.consumers);
	device_link_init_status(&model.link, consumer, supplier);
	return &model.link;
}
static void purge_link(void)
{
	if (!model.link_exists) return;
	CHECK(model.link.flags & DL_FLAG_AUTOREMOVE_CONSUMER, "consumer-lifecycle-owns-link-removal");
	link_remove(&model.link.s_node);
	put_device(model.link.consumer);
	put_device(model.link.supplier);
	model.link_exists = false;
}
#include "selected-HIF-lookup.inc"
#include "selected-HIF-init.inc"
#include "selected-HIF-probe.inc"
#include "selected-HIF-remove.inc"

static void release_devres(void)
{
	CHECK(model.live && model.hif && model.hif->list.next == &model.hif->list &&
	      !model.secondary.dev.driver_data, "HIF-unpublished-before-modeled-devres-free");
	free(model.hif);
	model.hif = NULL;
	model.live = false;
}
static void inject_gap(void)
{
	model.gap_done = true;
	CHECK(!hif_lock && model.explicit_ref && model.secondary.dev.refs == 2,
	      "device-not-devres-retained-across-lookup-gap");
	if (model.gap == GAP_UNBIND_STARTED) {
		model.secondary.dev.links.status = DL_DEV_UNBINDING;
	} else if (model.gap == GAP_REMOVED || model.gap == GAP_OTHER_DRIVER || model.gap == GAP_REBOUND) {
		mt7996_hif_remove(&model.secondary);
		release_devres();
		model.secondary.dev.driver = NULL;
		model.secondary.dev.links.status = DL_DEV_NO_DRIVER;
		if (model.gap == GAP_OTHER_DRIVER) {
			model.secondary.dev.driver = &other_driver;
			model.secondary.dev.links.status = DL_DEV_DRIVER_BOUND;
		} else if (model.gap == GAP_REBOUND) {
			model.secondary.dev.driver = &mt7996_hif_driver.driver;
			model.secondary.dev.links.status = DL_DEV_PROBING;
			CHECK(!mt7996_pci_hif2_probe(&model.secondary), "new-HIF-binding-probes");
			model.secondary.dev.links.status = DL_DEV_DRIVER_BOUND;
		}
	} else if (model.gap == GAP_NULL_DATA) {
		model.secondary.dev.driver_data = NULL;
	} else if (model.gap == GAP_WRONG_OWNER) {
		model.hif->dev = &model.primary.dev;
	} else if (model.gap == GAP_WRONG_ID) {
		model.secondary_reg ^= 1;
	}
}
static void wait_for_device_probe(void)
{
	CHECK(!links_lock && model.link.status == DL_STATE_CONSUMER_PROBE && model.live &&
	      model.explicit_ref, "supplier-unbind-waits-for-probing-consumer");
	model.waits++;
	if (model.probe_fail) {
		put_device(&model.secondary.dev);
		model.explicit_ref = false;
		purge_link();
	} else {
		model.bound = true;
		model.link.status = DL_STATE_ACTIVE;
	}
}
static void device_release_driver_internal(struct device *consumer, void *driver, struct device *parent)
{
	CHECK(!links_lock && consumer == &model.primary.dev && !driver && parent == consumer->parent &&
	      model.bound && model.live && model.explicit_ref && !model.supplier_released,
	      "consumer-unbound-synchronously-before-supplier-devres");
	model.releases++;
	model.consumer_released = true;
	model.bound = false;
	put_device(&model.secondary.dev);
	model.explicit_ref = false;
	purge_link();
}
#include "selected-link-unbind.inc"

static void setup(void)
{
	memset(&model, 0, sizeof(model));
	INIT_LIST_HEAD(&hif_list);
	hif_lock = links_lock = 0;
	hif_idx = 0;
	model.primary.dev.refs = model.secondary.dev.refs = 1;
	INIT_LIST_HEAD(&model.primary.dev.links.consumers);
	INIT_LIST_HEAD(&model.secondary.dev.links.consumers);
	model.primary.dev.links.status = DL_DEV_PROBING;
	model.secondary.dev.links.status = DL_DEV_PROBING;
	model.secondary.dev.driver = &mt7996_hif_driver.driver;
	model.primary.maps[0] = &model.primary_reg;
	model.secondary.maps[0] = &model.secondary_reg;
	model.secondary.irq = 0;
	model.present = model.echo = model.expected_driver = true;
	cases++;
}
static void publish(void)
{
	CHECK(!mt7996_pci_hif2_probe(&model.secondary), "HIF-probe-succeeds");
	model.secondary.dev.links.status = DL_DEV_DRIVER_BOUND;
}
static void finish(void)
{
	if (model.explicit_ref) {
		put_device(&model.secondary.dev);
		model.explicit_ref = false;
	}
	purge_link();
	if (model.live) {
		/* Restore test-only corrupt metadata before the real remove callback. */
		model.hif->dev = &model.secondary.dev;
		model.secondary.dev.driver_data = model.hif;
		mt7996_hif_remove(&model.secondary);
		release_devres();
	}
	CHECK(model.primary.dev.refs == 1 && model.secondary.dev.refs == 1 &&
	      hif_list.next == &hif_list && !hif_lock && !links_lock,
	      "all-explicit-and-managed-references-balanced");
}
static void binding_case(enum gap gap, bool probing, bool fail_link)
{
	struct mt7996_hif *result;
	bool success = gap == GAP_NONE || gap == GAP_REBOUND;
	setup();
	publish();
	if (probing) model.secondary.dev.links.status = DL_DEV_PROBING;
	model.gap = gap;
	model.link_fail = fail_link;
	result = mt7996_pci_init_hif2(&model.primary);
	if (fail_link) {
		CHECK(IS_ERR(result) && PTR_ERR(result) == -ENOMEM && model.secondary.dev.refs == 1,
		      "link-allocation-error-releases-lookup-reference");
		model.explicit_ref = false;
	} else if (success) {
		CHECK(result == model.hif && !IS_ERR(result) && model.data_reads == 1 &&
		      model.secondary.dev.refs == 3 && model.link.status == DL_STATE_CONSUMER_PROBE,
		      "successful-lookup-uses-fresh-qualified-HIF-with-both-pins");
	} else {
		CHECK(IS_ERR(result) && PTR_ERR(result) == -EPROBE_DEFER,
		      "unsafe-selected-supplier-defers-not-optional-or-success");
		CHECK(model.secondary.dev.refs == 2, "rejected-binding-drops-explicit-pin-keeps-core-link");
		model.explicit_ref = false;
		if (gap == GAP_UNBIND_STARTED || gap == GAP_REMOVED || gap == GAP_OTHER_DRIVER)
			CHECK(!model.data_reads, "unavailable-or-wrong-driver-never-read-drvdata");
	}
	CHECK(model.primary_reg == (MT_PCIE_RECOG_ID_SEM | 1), "local-nonzero-recognition-ID");
	finish();
}
int main(void)
{
	for (unsigned probing = 0; probing < 2; probing++)
		for (enum gap gap = GAP_NONE; gap <= GAP_WRONG_ID; gap++)
			binding_case(gap, probing, false);
	binding_case(GAP_NONE, false, true);
	setup();
	model.present = false;
	hif_idx = MT_PCIE_RECOG_ID_MASK;
	CHECK(!mt7996_pci_init_hif2(&model.primary) && !model.primary_reg,
	      "absent-HIF-remains-optional-even-at-ID-exhaustion");
	finish();
	setup();
	publish();
	model.echo = false;
	model.secondary_reg = 23;
	CHECK(!mt7996_pci_init_hif2(&model.primary) && !model.links_added &&
	      model.secondary.dev.refs == 1, "unmatched-HIF-remains-optional-without-reference-leak");
	finish();
	setup();
	publish();
	hif_idx = MT_PCIE_RECOG_ID_MASK;
	struct mt7996_hif *result = mt7996_pci_init_hif2(&model.primary);
	CHECK(IS_ERR(result) && PTR_ERR(result) == -EOVERFLOW && !model.primary_reg &&
	      hif_idx == MT_PCIE_RECOG_ID_MASK, "recognition-ID-never-wraps-or-reuses");
	finish();
	setup();
	publish();
	hif_idx = MT_PCIE_RECOG_ID_MASK - 1;
	result = mt7996_pci_init_hif2(&model.primary);
	CHECK(result == model.hif && hif_idx == MT_PCIE_RECOG_ID_MASK &&
	      (model.primary_reg & MT_PCIE_RECOG_ID_MASK) == MT_PCIE_RECOG_ID_MASK,
	      "last-recognition-ID-remains-usable");
	finish();
	setup();
	model.alloc_fail = true;
	CHECK(mt7996_pci_hif2_probe(&model.secondary) == -ENOMEM && !model.live &&
	      !model.secondary.dev.driver_data && hif_list.next == &hif_list,
	      "failed-HIF-allocation-publishes-nothing");
	finish();
	setup();
	publish();
	struct device *supplier = mt7996_pci_get_hif2(23);
	CHECK(!supplier && model.secondary.dev.refs == 1, "direct-unmatched-lookup-has-no-reference");
	mt7996_hif_remove(&model.secondary);
	CHECK(!model.secondary.dev.driver_data && hif_list.next == &hif_list,
	      "removed-HIF-clears-drvdata-and-list");
	release_devres();
	CHECK(!mt7996_pci_get_hif2(0), "removed-HIF-is-not-discoverable");
	finish();
	for (unsigned mode = 0; mode < 3; mode++) {
		setup();
		publish();
		CHECK(mt7996_pci_init_hif2(&model.primary) == model.hif, "unbind-fixture-gets-qualified-HIF");
		model.probe_fail = mode == 1;
		if (mode == 2) { model.bound = true; model.link.status = DL_STATE_ACTIVE; }
		model.secondary.dev.links.status = DL_DEV_UNBINDING;
		device_links_unbind_consumers(&model.secondary.dev);
		CHECK(model.waits == (mode == 2 ? 0U : 1U) && model.releases == (mode == 1 ? 0U : 1U) &&
		      !model.link_exists && !model.explicit_ref && model.live,
		      "actual-core-waits-or-removes-consumer-before-supplier-teardown");
		mt7996_hif_remove(&model.secondary);
		release_devres();
		model.supplier_released = true;
		finish();
	}
	printf("{\"passed\":true,\"cases\":%u,\"framework_modeled\":true,"
	       "\"kernel_concurrency\":false,\"physical_drain\":false,\"hardware\":false}\n", cases);
	return 0;
}
