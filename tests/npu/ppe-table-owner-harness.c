/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint32_t u32;
typedef uintptr_t dma_addr_t;

struct device {
	int refs;
	void (*action)(void *);
	void *action_data;
};

struct airoha_npu {
	struct {
		int (*ppe_init)(struct airoha_npu *);
		int (*ppe_init_stats)(struct airoha_npu *, dma_addr_t, int);
		int (*ppe_deinit)(struct airoha_npu *);
	} ops;
};

struct airoha_ppe_dev { void *priv; };
struct airoha_foe_entry { unsigned char bytes[80]; };
struct airoha_eth;

struct airoha_ppe {
	struct airoha_ppe_dev dev;
	struct airoha_eth *eth;
	void *foe;
	void *foe_stats;
	dma_addr_t foe_dma, foe_stats_dma;
	int l2_flows;
	int debugfs_dir;
};

struct airoha_eth {
	struct device *dev;
	struct airoha_ppe *ppe;
	struct airoha_ppe_dma_owner *ppe_dma;
	struct airoha_npu *npu;
	unsigned long state;
	int flow_table;
};

static struct {
	bool w1700k, module_dying, fail_owner, fail_action;
	int fail_dma_call, dma_calls, managed_calls, module_refs;
	int init_error, wait_error, stats_error, deinit_error, get_error;
	int get_calls, init_calls, stats_calls, hw_calls, put_calls, stop_calls;
	int rcu_syncs, flow_calls, warnings, sram_calls, sram_error, stats_count;
	bool live[2];
	void *va[2];
} t;
static bool flow_offload_mutex;

#define GFP_KERNEL 0
#define DEV_STATE_REGISTERED 0
#define THIS_MODULE ((void *)1)
#define IS_ERR(p) ((intptr_t)(p) < 0)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define dev_warn(dev, ...) (assert((dev)->refs > 0), ++t.warnings)
#define mutex_lock(lock) (assert(!*(lock)), *(lock) = true)
#define mutex_unlock(lock) (assert(*(lock)), *(lock) = false)
#define lockdep_assert_held(lock) assert(*(lock))
#define lockdep_is_held(lock) (*(lock))
#define test_bit(bit, addr) (!!(*(addr) & (1UL << (bit))))
#define clear_bit(bit, addr) (*(addr) &= ~(1UL << (bit)))
#define rcu_assign_pointer(ptr, value) ((ptr) = (value))
#define rcu_replace_pointer(ptr, value, held) \
	({ assert(held); __auto_type old = (ptr); (ptr) = (value); old; })
#define synchronize_rcu() (++t.rcu_syncs)
#define rhashtable_destroy(ptr) assert(ptr)
#define debugfs_remove(value) (void)(value)

static bool of_machine_is_compatible(const char *name)
{
	assert(!strcmp(name, "gemtek,w1700k-ubi"));
	return t.w1700k;
}

static void *kzalloc(size_t bytes, int flags)
{
	assert(flags == GFP_KERNEL);
	return t.fail_owner ? NULL : calloc(1, bytes);
}

#define kfree free

static struct device *get_device(struct device *dev)
{
	++dev->refs;
	return dev;
}

static void put_device(struct device *dev)
{
	assert(dev->refs == 2);
	--dev->refs;
}

static int devm_add_action_or_reset(struct device *dev,
				   void (*fn)(void *), void *data)
{
	assert(!dev->action);
	if (t.fail_action) {
		fn(data);
		return -ENOMEM;
	}
	dev->action = fn;
	dev->action_data = data;
	return 0;
}

static void release_devres(struct device *dev)
{
	assert(dev->action);
	dev->action(dev->action_data);
	dev->action = NULL;
}

static bool try_module_get(void *module)
{
	assert(module == THIS_MODULE);
	if (t.module_dying)
		return false;
	++t.module_refs;
	return true;
}

static void *dma_alloc_coherent(struct device *dev, size_t size,
				dma_addr_t *addr, int flags)
{
	int slot = t.dma_calls++;

	assert(dev->refs > 0 && slot < 2 && size == 160 && flags == GFP_KERNEL);
	if (t.fail_dma_call == slot + 1)
		return NULL;
	*addr = slot + 1;
	t.live[slot] = true;
	return t.va[slot] = calloc(1, size);
}

static void *dmam_alloc_coherent(struct device *dev, size_t size,
				 dma_addr_t *addr, int flags)
{
	++t.managed_calls;
	return dma_alloc_coherent(dev, size, addr, flags);
}

static void dma_free_coherent(struct device *dev, size_t size, void *va,
			      dma_addr_t addr)
{
	int slot = addr - 1;

	assert(dev->refs > 0 && slot >= 0 && slot < 2 && size == 160);
	assert(t.live[slot] && t.va[slot] == va);
	free(va);
	t.va[slot] = NULL;
	t.live[slot] = false;
}

static struct airoha_npu provider;

static struct airoha_npu *airoha_ppe_npu_get(struct airoha_eth *eth)
{
	assert(flow_offload_mutex && eth);
	++t.get_calls;
	return t.get_error ? (void *)(intptr_t)t.get_error : &provider;
}

static int airoha_ppe_wait_for_npu_init(struct airoha_eth *eth)
{
	assert(eth && t.init_calls);
	return t.wait_error;
}

static int airoha_ppe_get_total_num_stats_entries(struct airoha_ppe *ppe)
{
	assert(ppe);
	return t.stats_count;
}

static int airoha_ppe_flow_offload_cmd(struct airoha_eth *eth, void *data)
{
	assert(eth->npu == &provider && !data && t.hw_calls == 1);
	++t.flow_calls;
	return 0;
}

static void airoha_npu_put(struct airoha_npu *npu)
{
	assert(npu == &provider);
	++t.put_calls;
}

static u32 airoha_ppe_get_total_sram_num_entries(struct airoha_ppe *ppe)
{
	assert(ppe);
	return 2;
}

static int airoha_ppe_foe_commit_sram_entry(struct airoha_ppe *ppe, u32 i)
{
	const struct airoha_foe_entry *entry = ppe->foe;
	struct airoha_foe_entry zero = {0};

	assert(i < 2 && !memcmp(&entry[i], &zero, sizeof(zero)));
	++t.sram_calls;
	return t.sram_error;
}

static void airoha_ppe_hw_init(struct airoha_ppe *ppe);
static void airoha_ppe_foe_flow_stats_reset(struct airoha_ppe *ppe,
					  struct airoha_npu *npu);

#include "ppe-table-owner-under-test.inc"

static int init(struct airoha_npu *npu)
{
	assert(npu == &provider && flow_offload_mutex);
	++t.init_calls;
	return t.init_error;
}

static int stats(struct airoha_npu *npu, dma_addr_t addr, int count)
{
	assert(npu == &provider && addr == 2 && count == t.stats_count);
	assert(t.live[1] && flow_offload_mutex);
	assert(!t.w1700k || (w1700k_ppe_owner->stats.exposed && t.module_refs == 1));
	++t.stats_calls;
	return t.stats_error;
}

static int deinit(struct airoha_npu *npu)
{
	assert(npu == &provider && flow_offload_mutex);
	++t.stop_calls;
	return t.deinit_error;
}

static struct airoha_npu provider = { .ops = {
	.ppe_init = init, .ppe_init_stats = stats, .ppe_deinit = deinit,
} };

static void airoha_ppe_hw_init(struct airoha_ppe *ppe)
{
	assert(ppe->foe_dma == 1 && t.live[0] && flow_offload_mutex);
	assert(!t.w1700k || (ppe->eth->ppe_dma->foe.exposed && t.module_refs == 1));
	++t.hw_calls;
}

static void airoha_ppe_foe_flow_stats_reset(struct airoha_ppe *ppe,
					  struct airoha_npu *npu)
{
	assert(ppe && npu == &provider && t.hw_calls == 1);
}

struct fixture {
	struct device dev;
	struct airoha_eth eth;
	struct airoha_ppe ppe;
};

static void fixture_init(struct fixture *f)
{
	memset(f, 0, sizeof(*f));
	f->dev.refs = 1;
	f->eth.dev = &f->dev;
	f->eth.ppe = &f->ppe;
	f->eth.state = 1U << DEV_STATE_REGISTERED;
	f->ppe.dev.priv = &f->ppe;
	f->ppe.eth = &f->eth;
}

static void table_alloc(struct fixture *f, bool with_stats)
{
	f->ppe.foe = airoha_ppe_alloc_table(&f->ppe, 160, false);
	assert(f->ppe.foe);
	if (with_stats) {
		f->ppe.foe_stats = airoha_ppe_alloc_table(&f->ppe, 160, true);
		assert(f->ppe.foe_stats);
		t.stats_count = 20;
	}
}

static int setup(struct fixture *f)
{
	return airoha_ppe_setup_tc_block_cb(&f->ppe.dev, NULL);
}

/* A fresh kernel starts each test. This is not a driver release path. */
static void fresh(void)
{
	assert(!flow_offload_mutex);
	free(w1700k_ppe_owner);
	w1700k_ppe_owner = NULL;
	free(t.va[0]);
	free(t.va[1]);
	memset(&t, 0, sizeof(t));
	t.w1700k = true;
}

static void early_owner_failures(void)
{
	struct fixture f;

	fixture_init(&f);
	t.fail_owner = true;
	assert(airoha_ppe_prepare_dma(&f.eth) == -ENOMEM);
	assert(!w1700k_ppe_owner && !f.eth.ppe_dma && f.dev.refs == 1);
	t.fail_owner = false;
	t.fail_action = true;
	assert(airoha_ppe_prepare_dma(&f.eth) == -ENOMEM);
	assert(!w1700k_ppe_owner && !f.eth.ppe_dma && f.dev.refs == 1);
	t.fail_action = false;
	assert(airoha_ppe_prepare_dma(&f.eth) == 0);
	release_devres(&f.dev);
	assert(!w1700k_ppe_owner && f.dev.refs == 1 && !t.module_refs);
}

static void cold_allocation_failure(int allocation)
{
	struct fixture f;

	fixture_init(&f);
	assert(airoha_ppe_prepare_dma(&f.eth) == 0);
	t.fail_dma_call = allocation;
	assert((airoha_ppe_alloc_table(&f.ppe, 160, false) != NULL) == (allocation == 2));
	if (allocation == 2)
		assert(!airoha_ppe_alloc_table(&f.ppe, 160, true));
	release_devres(&f.dev);
	assert(!t.live[0] && !t.live[1] && !w1700k_ppe_owner);
	assert(!t.module_refs && f.dev.refs == 1);
}

static void before_publication(void)
{
	struct fixture a, b;

	fixture_init(&a);
	fixture_init(&b);
	assert(airoha_ppe_prepare_dma(&a.eth) == 0);
	assert(airoha_ppe_prepare_dma(&b.eth) == -EBUSY);
	assert(!b.eth.ppe_dma && b.dev.refs == 1);
	table_alloc(&a, true);
	t.sram_error = -ETIMEDOUT;
	assert(airoha_ppe_flush_sram_entries(&a.ppe) == -ETIMEDOUT);
	assert(t.sram_calls == 1);
	t.get_error = -ENODEV;
	assert(setup(&a) == -ENODEV && !t.init_calls && !t.put_calls);
	t.get_error = 0;
	t.init_error = -EIO;
	assert(setup(&a) == -EIO && t.put_calls == 1);
	t.init_error = 0;
	t.wait_error = -ETIMEDOUT;
	assert(setup(&a) == -ETIMEDOUT && t.put_calls == 2);
	t.wait_error = 0;
	t.module_dying = true;
	assert(setup(&a) == -ENODEV && t.put_calls == 3);
	assert(!t.hw_calls && !t.stats_calls && !t.module_refs && !a.eth.npu);
	release_devres(&a.dev);
	assert(!w1700k_ppe_owner && !t.live[0] && !t.live[1] && a.dev.refs == 1);
	assert(airoha_ppe_prepare_dma(&b.eth) == 0);
	release_devres(&b.dev);
}

static void publish_and_remove(bool with_stats, int deinit_error)
{
	struct fixture a, b;

	fixture_init(&a);
	fixture_init(&b);
	assert(airoha_ppe_prepare_dma(&a.eth) == 0);
	table_alloc(&a, with_stats);
	assert(!setup(&a) && !setup(&a));
	assert(t.init_calls == 1 && t.stats_calls == with_stats && t.flow_calls == 2);
	assert(t.module_refs == 1 && a.eth.npu == &provider && !t.managed_calls);
	t.deinit_error = deinit_error;
	airoha_ppe_deinit(&a.eth);
	assert(!a.eth.npu && !a.eth.state && t.rcu_syncs == 2 && t.put_calls == 1);
	assert(t.stop_calls == 1 && setup(&a) == -EBUSY && t.init_calls == 1);
	release_devres(&a.dev);
	assert(t.live[0] && t.live[1] == with_stats);
	assert(t.warnings == 1 + !!deinit_error && a.dev.refs == 2 && t.module_refs == 1);
	assert(w1700k_ppe_owner == a.eth.ppe_dma);
	assert(airoha_ppe_prepare_dma(&b.eth) == -EBUSY && !b.eth.ppe_dma);
}

static void failed_stats_delivery(void)
{
	struct fixture f;

	fixture_init(&f);
	assert(airoha_ppe_prepare_dma(&f.eth) == 0);
	table_alloc(&f, true);
	t.stats_error = -EIO;
	t.deinit_error = -ETIMEDOUT;
	assert(setup(&f) == -EIO && setup(&f) == -EIO);
	assert(t.init_calls == 1 && t.stats_calls == 1 && t.stop_calls == 1);
	assert(t.put_calls == 1 && !f.eth.npu && !t.hw_calls && !t.flow_calls);
	airoha_ppe_deinit(&f.eth);
	assert(t.stop_calls == 1);
	release_devres(&f.dev);
	assert(!t.live[0] && t.live[1] && f.dev.refs == 2 && t.module_refs == 1);
	assert(w1700k_ppe_owner == f.eth.ppe_dma && t.warnings == 2);
}

static void non_w1700k(void)
{
	struct fixture f;

	fixture_init(&f);
	t.w1700k = false;
	assert(airoha_ppe_prepare_dma(&f.eth) == 0);
	assert(!f.eth.ppe_dma && !w1700k_ppe_owner && !f.dev.action);
	table_alloc(&f, true);
	assert(t.managed_calls == 2 && !setup(&f));
	airoha_ppe_deinit(&f.eth);
	assert(t.stop_calls == 1 && t.put_calls == 1 && !t.module_refs && !t.warnings);
}

int main(void)
{
	fresh();
	early_owner_failures();
	fresh();
	cold_allocation_failure(1);
	fresh();
	cold_allocation_failure(2);
	fresh();
	before_publication();
	fresh();
	publish_and_remove(false, 0);
	fresh();
	publish_and_remove(false, -ETIMEDOUT);
	fresh();
	publish_and_remove(true, 0);
	fresh();
	failed_stats_delivery();
	fresh();
	non_w1700k();
	fresh();
	puts("9 PPE table owner cases passed");
	return 0;
}
