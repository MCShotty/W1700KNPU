/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint32_t u32;
typedef uintptr_t dma_addr_t;
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define WRITE_ONCE(n, v) ((n) = (v))
#define READ_ONCE(n) (n)
#define GFP_KERNEL 0
#define THIS_MODULE ((void *)1)
#define ERR_PTR(n) ((void *)(intptr_t)(n))
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define test_bit(b, p) (!!(*(p) & (1UL << (b))))
#define set_bit(b, p) (*(p) |= 1UL << (b))
#define DEV_STATE_QDMA_DETACH 2
#define CONFIG_DMA_DECLARE_COHERENT
#define USEC_PER_MSEC 1000
#define REG_QDMA_GLOBAL_CFG 4
#define GLOBAL_CFG_TX_WB_DONE_MASK (1U << 6)
#define U32_MAX UINT32_MAX

struct list_head { struct list_head *next, *prev; };
#define INIT_LIST_HEAD(h) ((h)->next = (h)->prev = (h))
#define list_entry(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define list_for_each_entry_safe(p, n, head, member) \
	for (struct list_head *it = (head)->next, *after; \
	     it != (head) && (after = it->next, \
	     (p) = list_entry(it, __typeof__(*(p)), member), \
	     (n) = NULL, (void)(n), 1); it = after)

static void list_add_tail(struct list_head *item, struct list_head *head)
{
	item->next = head;
	item->prev = head->prev;
	head->prev->next = item;
	head->prev = item;
}

static void list_del(struct list_head *item)
{
	item->next->prev = item->prev;
	item->prev->next = item->next;
}

struct device {
	int refs;
	bool iommu, ops;
	void *dma_mem, *action_data;
	void (*action)(void *);
};

struct net_device { bool running; };
struct sk_buff { struct net_device *dev; bool orphaned, scrubbed; int data; };
struct napi_struct { bool enabled, deleted; };
struct page_pool { bool detached, destroyed; };

struct airoha_queue_entry {
	struct sk_buff *skb;
	struct net_device *tx_dev;
	dma_addr_t dma_addr;
};

struct airoha_queue {
	int ndesc, forced;
	bool lock;
	struct airoha_queue_entry *entry;
	struct page_pool *page_pool;
	struct napi_struct napi;
};

struct airoha_irq_bank {
	bool requested;
	int irq;
	u32 irqmask[2];
};

struct airoha_qdma {
	struct airoha_eth *eth;
	struct airoha_queue q_tx[2], q_rx[2];
	struct { int size; struct napi_struct napi; } q_tx_irq[2];
	struct airoha_irq_bank irq_banks[2];
	struct list_head dma_tables;
	bool dma_exposed, blocked, parked, napi_started;
	int users;
	u32 last_status, script[4];
	unsigned int reads;
};

struct airoha_eth {
	struct device *dev;
	struct airoha_qdma qdma[2];
	unsigned long state;
	bool owns_qdma;
};

static struct {
	bool w1700k, fail_action, fail_dma, dying;
	int refs, warnings, allocs, frees, managed, irq_joins, disables;
	int mask_writes, mmio_writes, rx_cleanup, tx_cleanup, rcu_joins, app_lock;
} t;
static bool flow_offload_mutex;

#define DEFINE_MUTEX(lock) bool lock
#define mutex_lock(lock) (assert(!*(lock)), *(lock) = true)
#define mutex_unlock(lock) (assert(*(lock)), *(lock) = false)
#define spin_lock_bh(lock) mutex_lock(lock)
#define spin_unlock_bh(lock) mutex_unlock(lock)
#define dev_warn(dev, ...) (assert((dev)->refs > 0), ++t.warnings)
#define devm_kzalloc(dev, size, gfp) (assert((dev)->refs > 0), kzalloc(size, gfp))
#define devm_kcalloc(dev, num, size, gfp) (assert((dev)->refs > 0), kcalloc(num, size, gfp))
#define kmalloc(size, gfp) (assert(gfp == GFP_KERNEL), malloc(size))
#define kzalloc(size, gfp) (assert(gfp == GFP_KERNEL), calloc(1, size))
#define kcalloc(num, size, gfp) (assert(gfp == GFP_KERNEL), calloc(num, size))
#define kfree free
#define device_iommu_mapped(dev) ((dev)->iommu)
#define get_dma_ops(dev) ((dev)->ops)
#define of_machine_is_compatible(str) (assert(!strcmp(str, "gemtek,w1700k-ubi")), t.w1700k)
#define try_module_get(module) (assert(module == THIS_MODULE), !t.dying && ++t.refs)
#define module_put(module) (assert(module == THIS_MODULE && t.refs > 0), --t.refs)
#define put_device(dev) (assert((dev)->refs == 2), --(dev)->refs)
#define get_device(dev) (++(dev)->refs, (dev))
#define rtnl_lock() (assert(!t.app_lock), ++t.app_lock)
#define rtnl_unlock() (assert(t.app_lock == 1), --t.app_lock)
#define synchronize_rcu() (++t.rcu_joins)
#define skb_orphan(skb) ((skb)->orphaned = true)
#define skb_scrub_packet(skb, xnet) (assert(xnet), (skb)->scrubbed = true)

static int devm_add_action_or_reset(struct device *dev, void (*fn)(void *), void *data)
{
	if (t.fail_action) {
		fn(data);
		return -ENOMEM;
	}
	assert(!dev->action);
	dev->action = fn;
	dev->action_data = data;
	return 0;
}

static void *dma_alloc_coherent(struct device *dev, size_t bytes, dma_addr_t *dma, int gfp)
{
	assert(dev->refs > 0 && bytes == 16 && gfp == GFP_KERNEL);
	if (t.fail_dma)
		return NULL;
	*dma = 0x1000 + ++t.allocs * 16;
	return calloc(1, bytes);
}

static void *dmam_alloc_coherent(struct device *dev, size_t bytes, dma_addr_t *dma, int gfp)
{
	++t.managed;
	return dma_alloc_coherent(dev, bytes, dma, gfp);
}

static void dma_free_coherent(struct device *dev, size_t bytes, void *va, dma_addr_t dma)
{
	assert(dev->refs > 0 && bytes == 16 && va && dma > 0x1000);
	++t.frees;
	free(va);
}

static void airoha_qdma_wr(struct airoha_qdma *qdma, u32 reg, u32 val)
{
	if (reg == REG_QDMA_GLOBAL_CFG) {
		qdma->last_status = val;
	} else {
		assert(!qdma->eth->owns_qdma || qdma->dma_exposed);
		assert(val > 0x1000);
	}
	++t.mmio_writes;
}

static u32 airoha_qdma_rr(struct airoha_qdma *qdma, u32 reg)
{
	assert(reg == REG_QDMA_GLOBAL_CFG);
	unsigned int index = qdma->reads++;

	return qdma->script[index < 4 ? index : 3];
}

static void airoha_qdma_clear(struct airoha_qdma *qdma, u32 reg, u32 mask)
{
	airoha_qdma_wr(qdma, reg, qdma->last_status & ~mask);
}

#define airoha_qdma_set(qdma, reg, mask) \
	airoha_qdma_wr(qdma, reg, (qdma)->last_status | (mask))
#define read_poll_timeout(op, status, cond, delay, timeout, sleep, ...) \
	({ int rc = -ETIMEDOUT; \
	   for (int i = 0; i < 4; i++) { \
		(status) = op(__VA_ARGS__); \
		if (cond) { rc = 0; break; } \
	   } rc; })
#define airoha_qdma_irq_disable(bank, index, mask) \
	(assert((bank)->requested && (mask) == U32_MAX), (bank)->irqmask[index] = 0, ++t.mask_writes)
#define synchronize_irq(irq) (assert(irq == 7), ++t.irq_joins)
#define napi_disable(p) (assert((p)->enabled), (p)->enabled = false, ++t.disables)
#define netif_napi_del(p) (assert(!(p)->deleted && !(p)->enabled), (p)->deleted = true)
#define page_pool_disable_direct_recycling(pool) (assert(!(pool)->destroyed), (pool)->detached = true)
#define page_pool_destroy(pool) (assert(!(pool)->destroyed), (pool)->destroyed = true)
#define airoha_qdma_cleanup_rx_queue(q) (assert((q)->ndesc), ++t.rx_cleanup)
#define airoha_qdma_cleanup_tx_queue(q) (assert((q)->ndesc), ++(q)->forced, ++t.tx_cleanup)

#include "qdma-owner-under-test.inc"

static void release(struct device *dev)
{
	assert(dev->action);
	dev->action(dev->action_data);
	dev->action = NULL;
}

static void reset(void)
{
	if (w1700k_qdma_owner) {
		struct airoha_eth *eth = w1700k_qdma_owner;

		/* End of an isolated fixture, not a driver release operation. */
		eth->dev = &(struct device){ .refs = 2 };
		for (int i = 0; i < 2; i++)
			airoha_qdma_free_unexposed(&eth->qdma[i], eth->dev);
		free(eth);
		w1700k_qdma_owner = NULL;
	}
	memset(&t, 0, sizeof(t));
	t.w1700k = true;
}

static struct airoha_eth *owner(struct device *dev)
{
	struct airoha_eth *eth = airoha_alloc_eth(dev);

	assert((intptr_t)eth > 0 && eth->owns_qdma && dev->refs == 2);
	assert(w1700k_qdma_owner == eth && t.refs == 1);
	for (int i = 0; i < 2; i++)
		eth->qdma[i].eth = eth;
	return eth;
}

static void early_refusals(void)
{
	struct device a = { .refs = 1 }, b = { .refs = 1 };

	a.ops = true;
	assert(PTR_ERR(airoha_alloc_eth(&a)) == -EOPNOTSUPP);
	a.ops = false;
	a.iommu = true;
	assert(PTR_ERR(airoha_alloc_eth(&a)) == -EOPNOTSUPP);
	a.iommu = false;
	a.dma_mem = &a;
	assert(PTR_ERR(airoha_alloc_eth(&a)) == -EOPNOTSUPP);
	a.dma_mem = NULL;
	t.dying = true;
	assert(PTR_ERR(airoha_alloc_eth(&a)) == -ENODEV);
	t.dying = false;
	t.fail_action = true;
	assert(PTR_ERR(airoha_alloc_eth(&a)) == -ENOMEM);
	assert(!t.refs && a.refs == 1 && !w1700k_qdma_owner);
	t.fail_action = false;
	owner(&a);
	assert(PTR_ERR(airoha_alloc_eth(&b)) == -EBUSY && b.refs == 1);
	release(&a);
	assert(!t.refs && a.refs == 1 && !w1700k_qdma_owner);
}

static void allocation_rollback(void)
{
	struct device a = { .refs = 1 };
	struct airoha_eth *eth = owner(&a);
	struct airoha_qdma *qdma = &eth->qdma[0];
	dma_addr_t dma;

	assert(airoha_qdma_alloc_table(qdma, 16, &dma));
	t.fail_dma = true;
	assert(!airoha_qdma_alloc_table(qdma, 16, &dma));
	assert((qdma->q_tx[0].entry = airoha_qdma_alloc_entries(qdma, 2)));
	release(&a);
	assert(t.allocs == 1 && t.frees == 1 && !t.refs && !w1700k_qdma_owner);
}

static void published_probe_failure(void)
{
	struct device a = { .refs = 1 }, b = { .refs = 1 };
	struct airoha_eth *eth = owner(&a);
	struct airoha_qdma *qdma = &eth->qdma[0];
	struct page_pool pool = {0};
	dma_addr_t dma;

	assert(airoha_qdma_alloc_table(qdma, 16, &dma));
	airoha_qdma_publish_base(qdma, 8, dma);
	assert(airoha_qdma_alloc_table(&eth->qdma[1], 16, &dma));
	qdma->q_rx[0].ndesc = 2;
	qdma->q_rx[0].page_pool = &pool;
	qdma->q_tx[0].ndesc = 2;
	qdma->q_tx_irq[0].size = 2;
	qdma->irq_banks[0].requested = true;
	qdma->irq_banks[0].irq = 7;
	airoha_qdma_cleanup(qdma);
	assert(qdma->q_rx[0].napi.deleted && qdma->q_tx_irq[0].napi.deleted);
	assert(pool.detached && !pool.destroyed && !t.rx_cleanup && !t.tx_cleanup);
	assert(!t.disables && t.irq_joins == 1 && t.mask_writes == 2);
	release(&a);
	assert(t.refs == 1 && a.refs == 2 && t.allocs == 2 && t.frees == 1);
	assert(PTR_ERR(airoha_alloc_eth(&b)) == -EBUSY && !b.action);
}

static void host_stop(u32 status, bool passes, bool owned)
{
	struct device dev = { .refs = 1 };
	struct airoha_eth eth = { .dev = &dev, .owns_qdma = owned };
	struct airoha_qdma *qdma = &eth.qdma[0];

	qdma->eth = &eth;
	qdma->dma_exposed = owned;
	qdma->napi_started = true;
	for (int i = 0; i < 2; ++i)
		qdma->q_tx_irq[i].napi.enabled = true;
	qdma->q_tx[0].ndesc = 2;
	qdma->irq_banks[0].requested = true;
	qdma->irq_banks[0].irq = 7;
	for (int i = 0; i < 4; i++)
		qdma->script[i] = status;
	airoha_qdma_start(qdma);
	airoha_qdma_start(qdma);
	airoha_qdma_stop(qdma);
	assert(qdma->users == 1 && qdma->reads == 0 && !t.tx_cleanup);
	airoha_qdma_stop(qdma);
	assert(qdma->users == 0 && !(qdma->last_status & AIROHA_QDMA_HOST_EN));
	if (passes || !owned) {
		assert(t.tx_cleanup == 1 && !qdma->blocked && !t.disables);
		assert(!airoha_qdma_admit(qdma));
	} else {
		assert(!t.tx_cleanup && qdma->blocked && qdma->parked);
		assert(t.warnings == 1 && t.disables == 2 && t.irq_joins == 1);
		assert(airoha_qdma_admit(qdma) == -EIO);
		eth.qdma[1].eth = &eth;
		assert(airoha_qdma_admit(&eth.qdma[1]) == 0);
	}
}

static void detach_while_nominally_idle(void)
{
	struct device dev = { .refs = 1 };
	struct airoha_eth eth = { .dev = &dev, .owns_qdma = true };
	struct airoha_qdma *qdma = &eth.qdma[0];

	for (int i = 0; i < 2; i++)
		eth.qdma[i].eth = &eth;
	qdma->dma_exposed = true;
	qdma->q_tx[0].ndesc = 2;
	qdma->script[0] = GLOBAL_CFG_TX_WB_DONE_MASK;
	qdma->users = 1;
	airoha_hw_stop_napi(&eth);
	assert(t.rcu_joins == 1 && !t.app_lock && !flow_offload_mutex);
	assert(airoha_qdma_admit(qdma) == -ENODEV && qdma->parked);
	airoha_qdma_stop(qdma);
	airoha_qdma_cleanup(qdma);
	assert(!qdma->users && !t.tx_cleanup && qdma->reads == 1);
}

static void detach_metadata(void)
{
	struct net_device a, b;
	struct sk_buff sa = { .dev = &a, .data = 7 }, sb = { .dev = &b, .data = 8 };
	struct airoha_queue_entry entries[] = {
		{ .skb = &sa, .tx_dev = &a, .dma_addr = 3 },
		{ .skb = &sb, .tx_dev = &b, .dma_addr = 4 },
		{ .skb = &sb, .tx_dev = &a, .dma_addr = 0 },
	};
	struct airoha_qdma qdma = { .q_tx[0] = { .ndesc = 3, .entry = entries } };

	airoha_qdma_detach_tx_dev(&qdma, &a);
	assert(!sa.dev && sa.orphaned && sa.scrubbed && sa.data == 7);
	assert(entries[0].skb == &sa && entries[0].dma_addr == 3 && !entries[0].tx_dev);
	assert(sb.dev == &b && !sb.orphaned && !sb.scrubbed && sb.data == 8);
	assert(entries[1].dma_addr == 4 && entries[1].tx_dev == &b);
}

static void legacy_allocation(void)
{
	struct device dev = { .refs = 1 };
	dma_addr_t dma;
	void *va;

	t.w1700k = false;
	struct airoha_eth *eth = airoha_alloc_eth(&dev);

	assert(!eth->owns_qdma && !dev.action && !t.refs);
	eth->dev = &dev;
	eth->qdma[0].eth = eth;
	va = airoha_qdma_alloc_table(&eth->qdma[0], 16, &dma);
	assert(va && t.managed == 1);
	airoha_qdma_publish_base(&eth->qdma[0], 8, dma);
	assert(!eth->qdma[0].dma_exposed);
	free(va);
	free(eth);
}

int main(void)
{
	reset(); early_refusals();
	reset(); allocation_rollback();
	reset(); published_probe_failure();
	reset(); host_stop(GLOBAL_CFG_TX_WB_DONE_MASK, true, true);
	reset(); host_stop(GLOBAL_CFG_TX_WB_DONE_MASK | AIROHA_QDMA_HOST_BUSY, false, true);
	reset(); host_stop(GLOBAL_CFG_TX_WB_DONE_MASK | AIROHA_QDMA_HOST_EN, false, true);
	reset(); host_stop(0, false, true);
	reset(); detach_while_nominally_idle();
	reset(); detach_metadata();
	reset(); legacy_allocation();
	reset(); host_stop(AIROHA_QDMA_HOST_BUSY, false, false);
	reset();
	puts("11 QDMA owner cases passed");
	return 0;
}
