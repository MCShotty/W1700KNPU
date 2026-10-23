/* Selected actual PCI probe/remove/IRQ/unregister C; kernel and hardware models. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
typedef uint32_t u32;
typedef int irqreturn_t;
#define CHECK(ok, message) assert((ok) && message)
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define BIT(n) (1UL << (n))
#define DMA_BIT_MASK(n) ((1ULL << (n)) - 1)
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define READ_ONCE(v) (v)
#define IS_ERR(v) ((uintptr_t)(v) >= (uintptr_t)-4095)
#define PTR_ERR(v) ((int)(intptr_t)(v))
#define IRQF_SHARED 1
#define PCI_IRQ_ALL_TYPES 7
#define KBUILD_MODNAME "pci-lifetime-model"
enum { IRQ_NONE, IRQ_HANDLED, MT76_STATE_INITIALIZED };
enum { MT_INT_MASK_CSR = 1, MT_INT1_MASK_CSR, MT_PCIE_MAC_INT_ENABLE, MT_PCIE1_MAC_INT_ENABLE };
enum { MT7996_DEVICE_ID_2 = 0x7991, MT7992_DEVICE_ID_2 = 0x7993, MT7990_DEVICE_ID_2 = 0x7995 };
struct device { int refs, index; };
struct pci_bus { int domain; };
struct pci_dev { struct device dev; struct pci_bus *bus; int irq; void *driver_data; };
struct pci_device_id { unsigned device; };
struct tasklet_struct { bool pending, disabled; unsigned kills; };
struct work_struct { int unused; };
struct mt7996_hif { struct device *dev; int irq; };
struct mtk_wed_device { bool active; int irq; u32 mask; };
struct mt76_dev {
	struct device *dev;
	struct { int irq_lock; u32 irqmask; struct mtk_wed_device wed, wed_hif2; } mmio;
	struct tasklet_struct irq_tasklet;
};
struct mt76_phy { unsigned long state; };
#include "selected-pci-irq.inc"
struct mt7996_dev {
	struct mt76_dev mt76;
	struct mt76_phy mphy;
	struct mt7996_hif *hif2;
	struct mt7996_pci_irq pci_irq[2];
	bool irq_shutdown;
	struct work_struct dump_work, reset_work, rc_work;
	struct { struct work_struct work; } wed_rro;
	int phy;
};
static struct {
	struct pci_dev primary, secondary;
	struct pci_bus buses[2];
	struct mt7996_hif hif;
	struct mt7996_dev dev;
	bool hif_present, wed[2], consumer_live, hif_ref, initialized;
	bool action[2], vectors[2], wed_owned[2];
	int exact_irq[2], callback_after_free, releases, vector_frees, hif_puts;
	int failure, cancel_calls, free_calls, dma_cleanup, mcu_exit, registered;
	bool enable_context;
} model;
static unsigned cases;

static void clear_bit(int bit, unsigned long *state) { *state &= ~BIT(bit); }
static bool test_bit(int bit, const unsigned long *state) { return !!(*state & BIT(bit)); }
static void model_lock(int *lock) { CHECK(!*lock, "model-IRQ-lock-not-recursive"); *lock = 1; }
static void model_unlock(int *lock) { CHECK(*lock, "model-IRQ-lock-held"); *lock = 0; }
#define spin_lock_irqsave(lock, flags) do { (flags) = 0; model_lock(lock); } while (0)
#define spin_unlock_irqrestore(lock, flags) do { (void)(flags); model_unlock(lock); } while (0)
static bool mtk_wed_device_active(struct mtk_wed_device *wed) { return wed->active; }
static void mtk_wed_device_irq_set_mask(struct mtk_wed_device *wed, u32 mask)
{
	CHECK(model.consumer_live, "WED-mask-before-consumer-free");
	wed->mask = mask;
}
static void mt76_wr(struct mt7996_dev *dev, u32 reg, u32 value)
{
	CHECK(dev == &model.dev && model.consumer_live, "MMIO-before-consumer-free");
	CHECK(!dev->hif2 || model.hif_ref, "HIF2-reference-held-during-MMIO");
	if (reg == MT_INT_MASK_CSR) dev->mt76.mmio.wed.mask = value;
	if (reg == MT_INT1_MASK_CSR) dev->mt76.mmio.wed_hif2.mask = value;
}
static void tasklet_schedule(struct tasklet_struct *tasklet)
{
	CHECK(model.consumer_live, "tasklet-scheduled-before-consumer-free");
	CHECK(!model.enable_context || model.dev.mt76.mmio.irq_lock,
	      "poll-completion-scheduling-shares-shutdown-admission-lock");
	tasklet->pending = true;
}
static void tasklet_kill(struct tasklet_struct *tasklet)
{
	CHECK(!model.action[0] && !model.action[1], "IRQ-actions-removed-before-tasklet-join");
	tasklet->pending = false;
	tasklet->kills++;
}
static void tasklet_disable(struct tasklet_struct *tasklet) { tasklet->disabled = true; }
static void mt76_set_irq_mask(struct mt76_dev *dev, u32 reg, u32 clear, u32 set)
{
	(void)reg;
	model_lock(&dev->mmio.irq_lock);
	dev->mmio.irqmask = (dev->mmio.irqmask & ~clear) | set;
	model_unlock(&dev->mmio.irq_lock);
}
static void mt7996_dual_hif_set_irq_mask(struct mt7996_dev *dev, bool write, u32 clear, u32 set)
{
	(void)write;
	mt76_set_irq_mask(&dev->mt76, 0, clear, set);
}
#include "selected-irq-enable.inc"
#include "selected-irq-handler.inc"

static void invoke_enable(u32 mask)
{
	model.enable_context = true;
	mt7996_irq_enable(&model.dev, mask);
	model.enable_context = false;
}

static int pcim_enable_device(struct pci_dev *pdev) { (void)pdev; return model.failure == 1 ? -EIO : 0; }
static int pcim_iomap_regions(struct pci_dev *pdev, unsigned mask, const char *name)
{ (void)pdev; (void)mask; (void)name; return model.failure == 2 ? -EIO : 0; }
static const char *pci_name(struct pci_dev *pdev) { (void)pdev; return "model"; }
static void pci_set_master(struct pci_dev *pdev) { (void)pdev; }
static int dma_set_mask(struct device *dev, uint64_t mask)
{ (void)dev; (void)mask; return model.failure == 3 ? -EIO : 0; }
static int dma_set_coherent_mask(struct device *dev, uint64_t mask)
{ (void)dev; (void)mask; return model.failure == 4 ? -EIO : 0; }
static void mt76_pci_disable_aspm(struct pci_dev *pdev) { (void)pdev; }
static int mt7996_pci_hif2_probe(struct pci_dev *pdev) { (void)pdev; return 0; }
static void **pcim_iomap_table(struct pci_dev *pdev)
{ static void *maps[1]; (void)pdev; return maps; }
static struct mt7996_dev *mt7996_mmio_probe(struct device *dev, void *base, unsigned id)
{
	(void)base; (void)id;
	if (model.failure == 5) return (void *)(intptr_t)-ENOMEM;
	model.consumer_live = true;
	model.dev.mt76.dev = dev;
	model.primary.driver_data = &model.dev.mt76;
	return &model.dev;
}
static void mt7996_wfsys_reset(struct mt7996_dev *dev) { (void)dev; }
static struct mt7996_hif *mt7996_pci_init_hif2(struct pci_dev *pdev)
{
	(void)pdev;
	if (!model.hif_present) return NULL;
	model.hif_ref = true;
	model.secondary.dev.refs++;
	return &model.hif;
}
static void mt76_npu_init(struct mt76_dev *dev, unsigned long base, unsigned long length, int port)
{ (void)dev; (void)base; (void)length; CHECK(port == (model.buses[0].domain ? 3 : 2), "NPU-port-selection-kept"); }
static unsigned long pci_resource_start(struct pci_dev *pdev, int bar) { (void)pdev; (void)bar; return 0x1000; }
static unsigned long pci_resource_len(struct pci_dev *pdev, int bar) { (void)pdev; (void)bar; return 0x1000; }
static int pci_domain_nr(struct pci_bus *bus) { return bus->domain; }
static int mt7996_mmio_wed_init(struct mt7996_dev *dev, struct pci_dev *pdev, bool hif2, int *irq)
{
	unsigned index = hif2;
	struct mtk_wed_device *wed = hif2 ? &dev->mt76.mmio.wed_hif2 : &dev->mt76.mmio.wed;
	CHECK(pdev->dev.index == (int)index, "exact-WED-endpoint");
	if (model.failure == (hif2 ? 9 : 6)) return -EIO;
	if (!model.wed[index]) return 0;
	wed->active = model.wed_owned[index] = true;
	*irq = wed->irq;
	return 1;
}
static int pci_alloc_irq_vectors(struct pci_dev *pdev, int min, int max, int types)
{
	unsigned index = pdev->dev.index;
	(void)min; (void)max; (void)types;
	if (model.failure == (index ? 10 : 7)) return -ENOMEM;
	CHECK(!model.vectors[index], "PCI-vectors-allocated-once");
	model.vectors[index] = true;
	return 1;
}
static int devm_request_irq(struct device *dev, int irq, irqreturn_t (*handler)(int, void *),
			    int flags, const char *name, void *cookie)
{
	unsigned index = model.action[0] ? 1 : 0;
	(void)name;
	CHECK(dev == &model.primary.dev && cookie == &model.dev && handler == mt7996_irq_handler && flags == IRQF_SHARED,
	      "exact-managed-IRQ-owner-cookie-and-handler");
	CHECK(index < 2 && irq == model.exact_irq[index], "selected-IRQ-not-assumed-PCI-vector");
	if (model.failure == (index ? 11 : 8)) return -EIO;
	model.action[index] = true;
	CHECK(handler(irq, cookie) == IRQ_NONE,
	      "IRQ-registration-is-live-before-probe-completes");
	return 0;
}
static void devm_free_irq(struct device *dev, int irq, void *cookie)
{
	int index = irq == model.exact_irq[0] ? 0 : 1;
	CHECK(model.consumer_live && dev == &model.primary.dev && cookie == &model.dev,
	      "registered-IRQ-owner-and-cookie-live-at-removal");
	CHECK(model.action[index] && irq == model.exact_irq[index], "only-successfully-requested-exact-IRQ-freed-once");
	CHECK(!model.dev.mt76.mmio.wed.mask && (!model.hif_present || !model.dev.mt76.mmio.wed_hif2.mask),
	      "source-masked-before-shared-IRQ-removal");
	model.action[index] = false;
	model.releases++;
}
static void pci_free_irq_vectors(struct pci_dev *pdev)
{
	unsigned index = pdev->dev.index;
	CHECK(model.vectors[index] && !model.action[index], "only-owned-vectors-freed-after-IRQ-removal");
	model.vectors[index] = false;
	model.vector_frees++;
}
static void mtk_wed_device_detach(struct mtk_wed_device *wed)
{
	unsigned index = wed == &model.dev.mt76.mmio.wed_hif2;
	CHECK(model.wed_owned[index] && !model.action[index], "IRQ-removal-precedes-WED-domain-detach");
	wed->active = model.wed_owned[index] = false;
}
static void put_device(struct device *dev)
{
	CHECK(dev == &model.secondary.dev && model.hif_ref && dev->refs == 2,
	      "HIF2-pin-released-once-after-use");
	CHECK(!model.action[1] && !model.wed_owned[1] && !model.vectors[1], "HIF2-resources-stop-before-last-pin-put");
	dev->refs--;
	model.hif_ref = false;
	model.hif_puts++;
}
static int mt7996_register_device(struct mt7996_dev *dev)
{
	model.registered++;
	dev->mphy.state |= BIT(MT76_STATE_INITIALIZED);
	model.initialized = true;
	return model.failure == 12 ? -EIO : 0;
}
static void mt76_free_device(struct mt76_dev *dev)
{
	CHECK(dev == &model.dev.mt76 && model.consumer_live, "consumer-context-freed-once");
	CHECK(!model.action[0] && !model.action[1], "no-managed-IRQ-action-may-outlive-consumer-context");
	CHECK(!dev->irq_tasklet.pending && dev->irq_tasklet.kills,
	      "deferred-IRQ-tasklet-joined-before-consumer-free");
	model.consumer_live = false;
	model.free_calls++;
}
static void *pci_get_drvdata(struct pci_dev *pdev) { return pdev->driver_data; }
static void mt7996_npu_rro_reset_close(struct mt7996_dev *dev) { (void)dev; }
static void cancel_work_sync(struct work_struct *work) { (void)work; model.cancel_calls++; }
static void mt7996_npu_rro_reset_join(struct mt7996_dev *dev) { (void)dev; }
static int *mt7996_phy3(struct mt7996_dev *dev) { (void)dev; return NULL; }
static int *mt7996_phy2(struct mt7996_dev *dev) { (void)dev; return NULL; }
static void mt7996_unregister_phy(int *phy) { (void)phy; }
static void mt7996_unregister_thermal(int *phy) { (void)phy; }
static void mt7996_coredump_unregister(struct mt7996_dev *dev) { (void)dev; }
static void mt76_unregister_device(struct mt76_dev *dev) { (void)dev; }
static void mt7996_wed_rro_free(struct mt7996_dev *dev) { (void)dev; }
static void mt7996_mcu_exit(struct mt7996_dev *dev) { (void)dev; model.mcu_exit++; }
static void mt7996_tx_token_put(struct mt7996_dev *dev) { (void)dev; }
static void mt7996_dma_cleanup(struct mt7996_dev *dev)
{
	CHECK(model.mcu_exit && !model.action[0] && !model.action[1] && dev->mt76.irq_tasklet.kills,
	      "IRQ-and-tasklet-join-before-modeled-DMA-cleanup");
	CHECK(!dev->hif2 || model.hif_ref, "HIF2-reference-kept-through-unregister");
	if (dev->mt76.mmio.wed_hif2.active) mtk_wed_device_detach(&dev->mt76.mmio.wed_hif2);
	if (dev->mt76.mmio.wed.active) mtk_wed_device_detach(&dev->mt76.mmio.wed);
	model.dma_cleanup++;
}
static bool mt7996_has_hwrro(struct mt7996_dev *dev) { (void)dev; return false; }
static void mt7996_rro_msdu_page_map_free(struct mt7996_dev *dev) { (void)dev; }

#include "selected-pci-shutdown.inc"
#include "selected-unregister.inc"
#include "selected-pci-probe.inc"
#include "selected-pci-remove.inc"

static void setup(bool hif2, unsigned wed, int failure, unsigned domain)
{
	memset(&model, 0, sizeof(model));
	model.hif_present = hif2;
	model.wed[0] = wed & 1;
	model.wed[1] = wed & 2;
	model.failure = failure;
	model.buses[0].domain = domain;
	model.primary = (struct pci_dev){ .dev = { .refs = 1, .index = 0 }, .bus = &model.buses[0], .irq = domain == 2 ? 0 : 41 };
	model.secondary = (struct pci_dev){ .dev = { .refs = 1, .index = 1 }, .bus = &model.buses[1], .irq = domain == 2 ? 1 : 42 };
	model.hif = (struct mt7996_hif){ .dev = &model.secondary.dev, .irq = 42 };
	model.dev.mt76.mmio.wed.irq = 71;
	model.dev.mt76.mmio.wed_hif2.irq = 72;
	model.exact_irq[0] = model.wed[0] ? 71 : model.primary.irq;
	model.exact_irq[1] = model.wed[1] ? 72 : model.secondary.irq;
	cases++;
}
static void run_case(bool hif2, unsigned wed, int failure, unsigned domain)
{
	struct pci_device_id id = { .device = 0x7990 };
	int error;
	setup(hif2, wed, failure, domain);
	error = mt7996_pci_probe(&model.primary, &id);
	if (!error) {
		CHECK(!failure || (failure >= 7 && failure <= 11), "unreachable-profile-failure-is-not-a-probe-error");
		invoke_enable(0xff);
		CHECK(model.dev.mt76.mmio.irqmask == 0xff && model.dev.mt76.irq_tasklet.pending,
		      "ordinary-enable-behavior-kept");
		CHECK(mt7996_irq_handler(model.exact_irq[0], &model.dev) == IRQ_HANDLED,
		      "actual-IRQ-handler-executed-before-remove");
		mt7996_pci_remove(&model.primary);
	} else {
		CHECK(error == -EIO || error == -ENOMEM, "original-probe-error-propagated");
	}
	CHECK(!model.consumer_live && !model.action[0] && !model.action[1] &&
	      !model.vectors[0] && !model.vectors[1] && !model.wed_owned[0] && !model.wed_owned[1] &&
	      !model.hif_ref && model.secondary.dev.refs == 1,
	      "every-reached-prefix-releases-only-its-IRQ-vector-and-HIF2-resources");
	if (failure < 1 || failure > 5) {
		unsigned kills = model.dev.mt76.irq_tasklet.kills;
		model.consumer_live = true; /* Test-only tombstone storage, not production rearm. */
		mt7996_pci_shutdown_irqs(&model.dev);
		invoke_enable(0xff);
		CHECK(model.dev.irq_shutdown && !model.dev.mt76.mmio.irqmask &&
		      !model.dev.mt76.irq_tasklet.pending && model.dev.mt76.irq_tasklet.kills == kills + 1,
		      "repeated-close-and-late-enable-cannot-rearm-or-touch-released-HIF2");
		model.consumer_live = false;
	}
}
int main(void)
{
	for (unsigned hif = 0; hif < 2; hif++)
		for (unsigned wed = 0; wed < (hif ? 4U : 2U); wed++)
			for (unsigned domain = 0; domain < 3; domain++)
				for (unsigned failure = 0; failure <= 12; failure++)
					run_case(hif, wed, failure, domain);
	printf("{\"passed\":true,\"cases\":%u,\"kernel_framework_modeled\":true,"
	       "\"complete_RX_NAPI_join\":false,\"physical_drain\":false,\"hardware\":false}\n", cases);
	return 0;
}
