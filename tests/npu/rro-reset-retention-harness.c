/* Selected production C is compiled below with explicitly modeled host boundaries.
 * This is not a kernel concurrency, firmware, provider admission, or drain test.
 */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef u32 __le32;

#define CHECK(ok, label) do { \
	if (!(ok)) { fprintf(stderr, "%s\n", label); abort(); } \
} while (0)
#define ARRAY_SIZE(value) (sizeof(value) / sizeof((value)[0]))
#define BIT(n) (1UL << (n))
#define GENMASK(high, low) (((~0U) << (low)) & (~0U >> (31 - (high))))
#define FIELD_PREP(mask, value) (((u32)(value) << __builtin_ctz(mask)) & (mask))
#define U64_MAX UINT64_MAX
#define IEEE80211_NUM_TIDS 16
#define GFP_KERNEL 0
#ifdef static_assert
#undef static_assert
#endif
#define static_assert(condition, ...) _Static_assert(condition, #condition)
#define READ_ONCE(value) (value)
#define WRITE_ONCE(slot, value) ((slot) = (value))
#define smp_load_acquire(slot) (*(slot))
#define smp_store_release(slot, value) (*(slot) = (value))

struct list_head { struct list_head *next, *prev; };
#define LIST_HEAD(name) struct list_head name = { &(name), &(name) }

static void INIT_LIST_HEAD(struct list_head *head)
{
	head->next = head->prev = head;
}

static bool list_empty(const struct list_head *head)
{
	return head->next == head;
}

static void list_add_tail(struct list_head *node, struct list_head *head)
{
	CHECK(node->next == node && node->prev == node, "list-add-unlinked");
	node->prev = head->prev;
	node->next = head;
	head->prev->next = node;
	head->prev = node;
}

static void list_del_init(struct list_head *node)
{
	CHECK(node->next->prev == node && node->prev->next == node,
	      "list-delete-linked");
	node->prev->next = node->next;
	node->next->prev = node->prev;
	INIT_LIST_HEAD(node);
}

static void list_splice_tail_init(struct list_head *from, struct list_head *to)
{
	struct list_head *first, *last;

	if (list_empty(from))
		return;
	first = from->next;
	last = from->prev;
	first->prev = to->prev;
	to->prev->next = first;
	last->next = to;
	to->prev = last;
	INIT_LIST_HEAD(from);
}

static void list_splice_init(struct list_head *from, struct list_head *to)
{
	struct list_head *first, *last, *next;

	if (list_empty(from))
		return;
	first = from->next;
	last = from->prev;
	next = to->next;
	to->next = first;
	first->prev = to;
	last->next = next;
	next->prev = last;
	INIT_LIST_HEAD(from);
}

#define list_first_entry(head, type, member) \
	((type *)((char *)(head)->next - offsetof(type, member)))
#define container_of(pointer, type, member) \
	((type *)((char *)(pointer) - offsetof(type, member)))

typedef struct { int held; } spinlock_t;
#define DEFINE_SPINLOCK(name) spinlock_t name = { 0 }
static void (*before_spin_lock)(spinlock_t *);

static void spin_lock_init(spinlock_t *lock) { lock->held = 0; }
static void spin_lock_bh(spinlock_t *lock)
{
	if (before_spin_lock) {
		void (*callback)(spinlock_t *) = before_spin_lock;

		before_spin_lock = NULL;
		callback(lock);
	}
	CHECK(!lock->held, "nested-spinlock");
	lock->held = 1;
}
static void spin_unlock_bh(spinlock_t *lock)
{
	CHECK(lock->held, "unbalanced-spinlock");
	lock->held = 0;
}
#define spin_lock_irqsave(lock, flags) do { (flags) = 0; spin_lock_bh(lock); } while (0)
#define spin_unlock_irqrestore(lock, flags) do { (void)(flags); spin_unlock_bh(lock); } while (0)

#include "selected-types.inc"

struct device { int refs; bool alive; };
struct module { int refs; bool enabled; };
struct airoha_npu { int marker; };
struct work_struct { int unused; };

struct mt76_dev {
	struct device *dev;
	int mutex;
	struct {
		struct airoha_npu *npu;
		spinlock_t irq_lock;
		struct mt76_npu_irq npu_irq;
	} mmio;
};

struct mt7996_npu_rro_reset_owner;
struct mt7996_dev {
	struct mt76_dev mt76;
	bool npu_rro_owned;
	struct { int npu_error; } recovery;
	struct {
		struct work_struct work;
		spinlock_t lock;
		struct list_head poll_list;
		struct mt7996_npu_rro_reset_owner *reset_owner;
		bool reset_closing;
		struct { struct mt7996_wed_rro_addr *ptr; } session;
		struct { struct mt7996_wed_rro_addr *ptr; } addr_elem[MT7996_RRO_ADDR_ELEM_LEN];
	} wed_rro;
};

void mt7996_npu_rro_reset_close(struct mt7996_dev *dev);
int mt7996_npu_rro_reset_enqueue(struct mt7996_dev *dev, u16 id, u16 wlan_id, u8 tid);

static struct mt7996_dev fixture;
static struct device endpoint;
static struct module model_module;
static struct airoha_npu provider;
static struct mt7996_wed_rro_addr legacy_session[MT7996_RRO_WINDOW_MAX_LEN];
static void *legacy_event_pointer;
static int legacy_frees;
static struct mt7996_dev *close_on_get;
static bool fail_alloc, fail_device, consumer_released;
static bool fail_table_alloc;
static bool enqueue_on_get;
static int allocs, frees, test_only_disposals, cases;
static int queue_calls, cancel_calls, send_calls, mcu_calls, cpu_writes;
static int disable_count[2], mask_count[2], provider_close_calls;
static int send_error, mcu_error, send_last_id, mcu_last_id;
static bool close_on_send, close_on_mcu, physical_drain_witness;
static int mcu_begin_calls, mcu_complete_calls, begin_error, complete_error;
static bool close_on_begin;

#define THIS_MODULE (&model_module)

static void *kzalloc(size_t size, int flags)
{
	void *pointer;

	CHECK(flags == GFP_KERNEL, "allocator-flags");
	if (fail_alloc)
		return NULL;
	pointer = calloc(1, size);
	CHECK(pointer != NULL, "host-allocation");
	allocs++;
	return pointer;
}

static void *kcalloc(size_t count, size_t size, int flags)
{
	CHECK(count == MT7996_RRO_MAX_SESSION + 1 && size && count <= SIZE_MAX / size,
	      "BA-binding-table-full-geometry");
	return fail_table_alloc ? NULL : kzalloc(count * size, flags);
}

static void kfree(void *pointer)
{
	CHECK(pointer != NULL, "constructor-free-pointer");
	if (pointer == legacy_event_pointer) {
		legacy_frees++;
		return;
	}
	frees++;
	free(pointer);
}

static bool try_module_get(struct module *module)
{
	CHECK(module == &model_module, "module-identity");
	if (!module->enabled)
		return false;
	module->refs++;
	return true;
}

static void module_put(struct module *module)
{
	CHECK(module == &model_module && module->refs > 0, "module-put-balanced");
	module->refs--;
}

static struct device *get_device(struct device *device)
{
	CHECK(device == &endpoint, "endpoint-identity");
	if (fail_device)
		return NULL;
	CHECK(device->alive && device->refs > 0, "endpoint-get-live");
	device->refs++;
	if (enqueue_on_get) {
		enqueue_on_get = false;
		CHECK(mt7996_npu_rro_reset_enqueue(&fixture, 23, 45, 6) == -ENODEV,
		      "constructor-missing-owner-arrival");
	}
	if (close_on_get)
		mt7996_npu_rro_reset_close(close_on_get);
	return device;
}

static void put_device(struct device *device)
{
	CHECK(device == &endpoint && device->refs > 0, "endpoint-put-balanced");
	device->refs--;
	device->alive = device->refs > 0;
}

static void mutex_lock(int *lock)
{
	CHECK(!*lock, "nested-mutex");
	*lock = 1;
}

static void mutex_unlock(int *lock)
{
	CHECK(*lock, "unbalanced-mutex");
	*lock = 0;
}

static bool lockdep_is_held(int *lock) { return *lock == 1; }
static void check_rcu_protected(bool condition)
{
	CHECK(condition, "RCU-protected-mutex");
}
#define rcu_dereference_protected(pointer, condition) \
	(check_rcu_protected(condition), (pointer))

static void disable_irq_nosync(int line)
{
	CHECK(fixture.mt76.mmio.irq_lock.held, "irq-disable-lock");
	CHECK(line == 10 || line == 11, "irq-line-identity");
	disable_count[line - 10]++;
}

static int airoha_npu_wlan_irq_mask(struct airoha_npu *npu, unsigned int q)
{
	CHECK(fixture.mt76.mmio.irq_lock.held, "irq-mask-lock");
	CHECK(npu == &provider && q < ARRAY_SIZE(mask_count), "irq-mask-target");
	mask_count[q]++;
	return 0;
}

static int airoha_npu_wlan_rro_close(struct airoha_npu *npu,
				      struct device *device)
{
	CHECK(fixture.mt76.mutex && npu == &provider && device == &endpoint,
	      "provider-close-boundary");
	provider_close_calls++;
	return 0;
}

#define mt76_hw(dev) (dev)
static void ieee80211_queue_work(void *hw, struct work_struct *work);
static int mt76_npu_send_txrx_addr(struct mt76_dev *dev, int selector, u16 id,
				    int a, int b, int c);
static int mt7996_mcu_wed_rro_reset_sessions(struct mt7996_dev *dev, u16 id);
static int mt76_npu_rro_reset_npu(struct mt76_dev *dev, u32 id, u32 generation, u32 *ticket);
static int mt76_npu_rro_reset_mcu_begin(struct mt76_dev *dev, u32 id, u32 generation, u32 ticket);
static int mt76_npu_rro_reset_mcu_complete(struct mt76_dev *dev, u32 id,
					 u32 generation, u32 ticket, int result);

static bool is_mt7996(struct mt76_dev *dev)
{
	CHECK(dev == &fixture.mt76, "chip-boundary");
	return true;
}

static bool mt76_npu_device_active(struct mt76_dev *dev)
{
	CHECK(dev == &fixture.mt76, "device-active-argument");
	return dev->mmio.npu != NULL;
}

static u32 model_cpu_to_le32(u32 value)
{
	cpu_writes++;
	return value;
}
#define cpu_to_le32(value) model_cpu_to_le32(value)

#include "selected-npu.inc"
#include "selected-helper.inc"

static void ieee80211_queue_work(void *hw, struct work_struct *work)
{
	struct mt7996_npu_rro_reset_owner *owner = fixture.wed_rro.reset_owner;

	CHECK(hw == &fixture && work == &fixture.wed_rro.work, "queue-target");
	CHECK(fixture.wed_rro.lock.held || (owner && owner->lock.held),
	      "queue-under-admission-lock");
	CHECK(!fixture.wed_rro.reset_closing, "queue-after-close");
	queue_calls++;
}

static int mt76_npu_send_txrx_addr(struct mt76_dev *dev, int selector, u16 id,
				    int a, int b, int c)
{
	CHECK(dev == &fixture.mt76 && selector == 3 && !a && !b && !c,
	      "NPU-send-arguments");
	CHECK(!fixture.wed_rro.reset_owner->lock.held,
	      "NPU-send-outside-owner-lock");
	send_calls++;
	send_last_id = id;
	if (close_on_send)
		mt7996_npu_rro_reset_close(&fixture);
	return dev->mmio.npu ? send_error : -ENODEV;
}

static int mt76_npu_rro_reset_npu(struct mt76_dev *dev, u32 id, u32 generation, u32 *ticket)
{
	CHECK(generation == 1 && ticket == &fixture.wed_rro.reset_owner->records[id].ticket,
	      "typed-reset-immutable-generation-output");
	if (dev->mmio.npu)
		*ticket = 130 + id;
	return mt76_npu_send_txrx_addr(dev, 3, id, 0, 0, 0);
}

static void typed_mcu_identity(struct mt76_dev *dev, u32 id, u32 generation, u32 ticket)
{
	CHECK(dev == &fixture.mt76 && !fixture.wed_rro.reset_owner->lock.held &&
	      generation == 1 && ticket == 130 + id,
	      "typed-MCU-exact-ticket-outside-owner-lock");
}

static int mt76_npu_rro_reset_mcu_begin(struct mt76_dev *dev, u32 id, u32 generation, u32 ticket)
{
	typed_mcu_identity(dev, id, generation, ticket);
	mcu_begin_calls++;
	if (close_on_begin)
		mt7996_npu_rro_reset_close(&fixture);
	return begin_error;
}

static int mt76_npu_rro_reset_mcu_complete(struct mt76_dev *dev, u32 id,
					 u32 generation, u32 ticket, int result)
{
	typed_mcu_identity(dev, id, generation, ticket);
	CHECK(mcu_calls && result == mcu_error, "typed-MCU-complete-keeps-raw-result");
	mcu_complete_calls++;
	return complete_error;
}

static int mt7996_mcu_wed_rro_reset_sessions(struct mt7996_dev *dev, u16 id)
{
	CHECK(dev == &fixture && !dev->wed_rro.reset_owner->lock.held,
	      "MCU-call-outside-owner-lock");
	CHECK(dev->wed_rro.reset_owner->records[id].phase ==
	      MT7996_NPU_RRO_MCU_POSSIBLE, "MCU-admitted-credit");
	mcu_calls++;
	mcu_last_id = id;
	if (close_on_mcu)
		mt7996_npu_rro_reset_close(dev);
	return mcu_error;
}

#include "selected-worker.inc"

static size_t list_count(struct list_head *head)
{
	struct list_head *entry;
	size_t count = 0;

	for (entry = head->next; entry != head; entry = entry->next) {
		CHECK(++count <= 2048, "list-cycle");
		CHECK(entry->next->prev == entry, "list-link-forward");
	}
	return count;
}

static void start_case(void)
{
	CHECK(list_empty(&mt7996_npu_rro_retained), "prior-case-retained-owner");
	memset(&fixture, 0, sizeof(fixture));
	memset(&endpoint, 0, sizeof(endpoint));
	memset(&model_module, 0, sizeof(model_module));
	memset(&provider, 0, sizeof(provider));
	memset(legacy_session, 0, sizeof(legacy_session));
	endpoint.refs = 1;
	endpoint.alive = true;
	model_module.enabled = true;
	fixture.mt76.dev = &endpoint;
	fixture.mt76.mmio.npu = &provider;
	fixture.mt76.mmio.npu_irq.line[0] = 10;
	fixture.mt76.mmio.npu_irq.line[1] = 11;
	fixture.mt76.mmio.npu_irq.requested = BIT(0) | BIT(1);
	fixture.mt76.mmio.npu_irq.running = true;
	fixture.wed_rro.session.ptr = legacy_session;
	fixture.npu_rro_owned = true;
	INIT_LIST_HEAD(&fixture.wed_rro.poll_list);
	close_on_get = NULL;
	enqueue_on_get = false;
	before_spin_lock = NULL;
	legacy_event_pointer = NULL;
	legacy_frees = 0;
	fail_alloc = fail_device = consumer_released = false;
	fail_table_alloc = false;
	close_on_send = close_on_mcu = physical_drain_witness = false;
	allocs = frees = test_only_disposals = 0;
	queue_calls = cancel_calls = send_calls = mcu_calls = cpu_writes = 0;
	disable_count[0] = disable_count[1] = 0;
	mask_count[0] = mask_count[1] = provider_close_calls = 0;
	send_error = mcu_error = send_last_id = mcu_last_id = 0;
	mcu_begin_calls = mcu_complete_calls = begin_error = complete_error = 0;
	close_on_begin = false;
	cases++;
}

static struct mt7996_npu_rro_reset_owner *init_owner(void)
{
	struct mt7996_npu_rro_reset_owner *owner;

	CHECK(mt7996_npu_rro_reset_init(&fixture) == 0, "constructor-success");
	owner = fixture.wed_rro.reset_owner;
	CHECK(owner && owner->endpoint == &endpoint && owner->module == &model_module,
	      "owner-pinned-identities");
	CHECK(model_module.refs == 1, "module-pin-retained");
	CHECK(endpoint.refs == 2, "endpoint-pin-retained");
	return owner;
}

static void assert_quarantined(int error, bool provider_present)
{
	struct mt76_npu_irq *irq = &fixture.mt76.mmio.npu_irq;

	CHECK(irq->error == error && !irq->running &&
	      disable_count[0] == 1 && disable_count[1] == 1 &&
	      mask_count[0] == (provider_present ? 1 : 0) &&
	      mask_count[1] == (provider_present ? 1 : 0),
	      "irq-quarantine-on-abort");
	CHECK(fixture.recovery.npu_error == error, "recovery-error-latched");
	CHECK(provider_close_calls == (provider_present ? 1 : 0),
	      "provider-close-attempt-on-abort");
}

static void end_case(void)
{
	struct mt7996_npu_rro_reset_owner *owner = fixture.wed_rro.reset_owner;

	if (owner) {
		if (!owner->closing)
			mt7996_npu_rro_reset_close(&fixture);
		CHECK(owner->closing && owner->retained_once &&
		      list_count(&mt7996_npu_rro_retained) == 1,
		      "owner-retained-before-test-only-disposal");
		CHECK(model_module.refs == 1 &&
		      endpoint.refs == (consumer_released ? 1 : 2),
		      "production-no-owner-release");
		CHECK(!physical_drain_witness, "software-join-not-physical-drain");
		/* Test-only final disposal: production has no retirement authority. */
		list_del_init(&owner->retained);
		put_device(owner->endpoint);
		module_put(owner->module);
		free(owner->bindings);
		free(owner);
		fixture.wed_rro.reset_owner = NULL;
		test_only_disposals += 2;
	} else {
		CHECK(model_module.refs == 0, "constructor-unwind-module");
	}
	CHECK(list_empty(&mt7996_npu_rro_retained), "test-only-disposal-list");
	CHECK(allocs == frees + test_only_disposals, "allocation-balance");
	CHECK(endpoint.refs == (consumer_released ? 0 : 1),
	      "endpoint-reference-balance");
}

/* These worker/IRQ regressions model prior status enrollment explicitly. The
 * separate BA-owner suite executes actual RX creation/status/DELETE together.
 */
static int enqueue_with_modeled_BA(struct mt7996_dev *dev, u16 id, u16 wlan, u8 tid)
{
	struct mt7996_npu_rro_reset_owner *owner = dev->wed_rro.reset_owner;
	if (owner && id < ARRAY_SIZE(owner->records) && !owner->bindings[id].serial) {
		(void)mt7996_npu_rro_ba_bind(dev, id, wlan, wlan, tid, (u64)id + 1);
		CHECK(owner->bindings[id].serial == (u64)id + 1, "modeled-BA-enrollment-retained");
	}
	return mt7996_npu_rro_reset_enqueue(dev, id, wlan, tid);
}

static void test_constructor(void)
{
	start_case();
	fail_alloc = true;
	CHECK(mt7996_npu_rro_reset_init(&fixture) == -ENOMEM,
	      "constructor-allocation-failure");
	fail_alloc = false;
	model_module.enabled = false;
	CHECK(mt7996_npu_rro_reset_init(&fixture) == -ENODEV,
	      "constructor-module-failure");
	model_module.enabled = true;
	fail_device = true;
	CHECK(mt7996_npu_rro_reset_init(&fixture) == -ENODEV,
	      "constructor-endpoint-failure");
	fail_device = false;
	init_owner();
	CHECK(mt7996_npu_rro_reset_init(&fixture) == -EALREADY,
	      "constructor-duplicate-owner");
	end_case();

	start_case();
	fail_table_alloc = true;
	CHECK(mt7996_npu_rro_reset_init(&fixture) == -ENOMEM && !fixture.wed_rro.reset_owner &&
	      allocs == 1 && frees == 1 && model_module.refs == 0 && endpoint.refs == 1,
	      "constructor-BA-table-failure-unwinds-owner");
	end_case();

	start_case();
	close_on_get = &fixture;
	CHECK(mt7996_npu_rro_reset_init(&fixture) == -ESHUTDOWN,
	      "constructor-close-before-publish");
	CHECK(!fixture.wed_rro.reset_owner && fixture.wed_rro.reset_closing,
	      "constructor-unpublished-on-close");
	end_case();
}

static void test_missing_owner_close(void)
{
	start_case();
	CHECK(enqueue_with_modeled_BA(&fixture, 1, 21, 2) == -ENODEV,
	      "missing-owner-enqueue");
	CHECK(queue_calls == 1 && fixture.wed_rro.lock.held == 0,
	      "missing-owner-queue-under-lock");
	CHECK(mt7996_npu_rro_reset_init(&fixture) == -ENODEV &&
	      !fixture.wed_rro.reset_owner, "missing-owner-error-prevents-later-publication");
	mt7996_npu_rro_reset_close(&fixture);
	CHECK(enqueue_with_modeled_BA(&fixture, 2, 22, 3) == -ENODEV &&
	      queue_calls == 1, "missing-owner-close-admission");
	CHECK(mt7996_npu_rro_reset_init(&fixture) == -ESHUTDOWN,
	      "close-before-init-refused");
	mt7996_wed_rro_work(&fixture.wed_rro.work);
	assert_quarantined(-ENODEV, true);
	CHECK(!mcu_calls && !cpu_writes, "missing-owner-no-fallback");
	end_case();
}

static void test_constructor_event_error(void)
{
	start_case();
	enqueue_on_get = true;
	CHECK(mt7996_npu_rro_reset_init(&fixture) == -ENODEV &&
	      !fixture.wed_rro.reset_owner, "constructor-latches-missing-owner-error");
	CHECK(queue_calls == 1 && model_module.refs == 0 && endpoint.refs == 1,
	      "constructor-error-unwinds-unpublished-owner");
	mt7996_wed_rro_work(&fixture.wed_rro.work);
	assert_quarantined(-ENODEV, true);
	CHECK(!send_calls && !mcu_calls && !cpu_writes, "constructor-error-no-side-effects");
	end_case();
}

static void publish_before_lock(spinlock_t *lock)
{
	CHECK(lock == &fixture.wed_rro.lock, "publication-race-lock");
	init_owner();
	CHECK(!mt7996_npu_rro_ba_bind(&fixture, 19, 31, 31, 7, 20),
	      "publication-race-modeled-status-binding");
}

static void test_publication_recheck(void)
{
	struct mt7996_npu_rro_reset_owner *owner;

	start_case();
	before_spin_lock = publish_before_lock;
	CHECK(enqueue_with_modeled_BA(&fixture, 19, 31, 7) == 0,
	      "publication-recheck-retains-arrival");
	owner = fixture.wed_rro.reset_owner;
	CHECK(owner && !fixture.recovery.npu_error && queue_calls == 1 &&
	      owner->records[19].arrival == 1 && owner->records[19].wlan_id == 31 &&
	      owner->records[19].tid == 7 && list_count(&owner->pending) == 1,
	      "publication-race-exact-record");
	mt7996_wed_rro_work(&fixture.wed_rro.work);
	CHECK(send_calls == 1 && mcu_calls == 1 &&
	      owner->records[19].phase == MT7996_NPU_RRO_MCU_ACKED,
	      "publication-race-modeled-completion");
	end_case();
}

static void test_all_ids_and_bounds(void)
{
	struct mt7996_npu_rro_reset_owner *owner;
	unsigned int id;

	start_case();
	owner = init_owner();
	for (id = 0; id <= MT7996_RRO_MAX_SESSION; id++) {
		CHECK(enqueue_with_modeled_BA(&fixture, id, id + 30,
							id % 16) == 0,
		      "all-1025-ids-admitted");
		CHECK(owner->records[id].id == id &&
		      owner->records[id].arrival == id + 1 &&
		      owner->records[id].wlan_id == id + 30 &&
		      owner->records[id].tid == id % 16,
		      "id-tuple-arrival-retained");
	}
	CHECK(owner->arrivals == 1025 && list_count(&owner->pending) == 1025,
	      "all-1025-pending");
	CHECK(allocs == 2 && frees == 0, "all-records-preallocated");
	mt7996_wed_rro_work(&fixture.wed_rro.work);
	CHECK(send_calls == 1025 && mcu_calls == 1025 &&
	      send_last_id == 1024 && mcu_last_id == 1024 &&
	      list_count(&owner->held) == 1025 && list_empty(&owner->pending),
	      "all-1025-modeled-completions");
	for (id = 0; id <= MT7996_RRO_MAX_SESSION; id++)
		CHECK(owner->records[id].phase == MT7996_NPU_RRO_MCU_ACKED,
		      "all-completed-records-held");
	CHECK(enqueue_with_modeled_BA(&fixture, 1025, 7, 1) == -EINVAL,
	      "id-1025-out-of-bounds");
	CHECK(enqueue_with_modeled_BA(&fixture, UINT16_MAX, 8, 2) == -EINVAL,
	      "u16-max-out-of-bounds");
	CHECK(owner->bad_valid && owner->bad_id == 1025 &&
	      owner->bad_wlan_id == 7 && owner->bad_tid == 1 &&
	      owner->conflicts == 2 && owner->arrivals == 1025,
	      "first-bad-tuple-retained");
	mt7996_wed_rro_work(&fixture.wed_rro.work);
	assert_quarantined(-EINVAL, true);
	end_case();
}

static void test_duplicates_and_conflicts(void)
{
	struct mt7996_npu_rro_reset_owner *owner;

	start_case();
	owner = init_owner();
	CHECK(enqueue_with_modeled_BA(&fixture, 17, 71, 3) == 0,
	      "initial-tuple");
	CHECK(enqueue_with_modeled_BA(&fixture, 17, 71, 3) == -EALREADY,
	      "pending-duplicate");
	CHECK(owner->duplicates == 1 && owner->arrivals == 1 &&
	      !owner->error, "pending-duplicate-no-new-arrival");
	CHECK(enqueue_with_modeled_BA(&fixture, 17, 72, 3) == -ESTALE,
	      "pending-conflicting-tuple");
	CHECK(enqueue_with_modeled_BA(&fixture, 18, 72, 4) == 0,
	      "post-conflict-record-held");
	CHECK(owner->error == -ESTALE && owner->bad_valid &&
	      owner->bad_id == 17 && owner->bad_wlan_id == 72 &&
	      owner->bad_tid == 3 && owner->records[18].arrival == 2 &&
	      list_count(&owner->held) == 1, "conflict-state-retained");
	mt7996_wed_rro_work(&fixture.wed_rro.work);
	CHECK(!send_calls && !mcu_calls && list_count(&owner->held) == 2,
	      "conflict-prevents-admission");
	assert_quarantined(-ESTALE, true);
	end_case();

	start_case();
	owner = init_owner();
	CHECK(enqueue_with_modeled_BA(&fixture, 5, 62, 6) == 0,
	      "completion-first-arrival");
	mt7996_wed_rro_work(&fixture.wed_rro.work);
	CHECK(owner->records[5].phase == MT7996_NPU_RRO_MCU_ACKED,
	      "modeled-completion");
	CHECK(enqueue_with_modeled_BA(&fixture, 5, 62, 6) == -ESTALE,
	      "completed-id-reuse-held");
	CHECK(owner->arrivals == 1 && owner->conflicts == 1 &&
	      owner->records[5].arrival == 1 && send_calls == 1 && mcu_calls == 1,
	      "completed-reuse-no-new-generation");
	mt7996_wed_rro_work(&fixture.wed_rro.work);
	assert_quarantined(-ESTALE, true);
	end_case();
}

static void test_npu_errors(void)
{
	struct mt7996_npu_rro_reset_owner *owner;
	int raw[2] = { -ETIMEDOUT, 7 };
	unsigned int i;

	for (i = 0; i < ARRAY_SIZE(raw); i++) {
		start_case();
		owner = init_owner();
		send_error = raw[i];
		CHECK(enqueue_with_modeled_BA(&fixture, 41, 91, 1) == 0 &&
		      enqueue_with_modeled_BA(&fixture, 42, 92, 2) == 0,
		      "NPU-error-seed");
		mt7996_wed_rro_work(&fixture.wed_rro.work);
		CHECK(send_calls == 1 && mcu_calls == 0,
		      "npu-error-blocks-mcu");
		CHECK(owner->records[41].npu_error == raw[i] &&
		      owner->records[41].phase == MT7996_NPU_RRO_NPU_POSSIBLE &&
		      owner->records[42].phase == MT7996_NPU_RRO_QUEUED &&
		      list_count(&owner->held) == 2 && list_empty(&owner->pending),
		      "NPU-raw-error-and-records-held");
		CHECK(owner->error == (raw[i] < 0 ? raw[i] : -EIO),
		      "positive-NPU-error-normalized-globally");
		assert_quarantined(owner->error, true);
		end_case();
	}
}

static void test_mcu_errors(void)
{
	struct mt7996_npu_rro_reset_owner *owner;
	int raw[2] = { -ETIMEDOUT, 9 };
	unsigned int i;

	for (i = 0; i < ARRAY_SIZE(raw); i++) {
		start_case();
		owner = init_owner();
		mcu_error = raw[i];
		CHECK(enqueue_with_modeled_BA(&fixture, 51, 111, 5) == 0 &&
		      enqueue_with_modeled_BA(&fixture, 52, 112, 6) == 0,
		      "MCU-error-seed");
		mt7996_wed_rro_work(&fixture.wed_rro.work);
		CHECK(send_calls == 1 && mcu_calls == 1 &&
		      owner->records[51].phase == MT7996_NPU_RRO_MCU_POSSIBLE &&
		      owner->records[51].mcu_error == raw[i] &&
		      owner->records[52].phase == MT7996_NPU_RRO_QUEUED &&
		      list_count(&owner->held) == 2, "MCU-raw-error-and-records-held");
		CHECK(owner->error == (raw[i] < 0 ? raw[i] : -EIO),
		      "positive-MCU-error-normalized-globally");
		assert_quarantined(owner->error, true);
		end_case();
	}
}

static void test_provider_loss_no_cpu_fallback(void)
{
	struct mt7996_npu_rro_reset_owner *owner;
	struct mt7996_wed_rro_session_id old;

	start_case();
	owner = init_owner();
	CHECK(enqueue_with_modeled_BA(&fixture, 7, 44, 3) == 0,
	      "provider-loss-owned-arrival");
	INIT_LIST_HEAD(&old.list);
	old.id = MT7996_RRO_MAX_SESSION;
	legacy_event_pointer = &old;
	list_add_tail(&old.list, &fixture.wed_rro.poll_list);
	fixture.mt76.mmio.npu = NULL;
	mt7996_wed_rro_work(&fixture.wed_rro.work);
	CHECK(send_calls == 1 && !mcu_calls && !cpu_writes &&
	      list_count(&fixture.wed_rro.poll_list) == 1 &&
	      list_count(&owner->held) == 1, "owned-provider-loss-no-CPU-fallback");
	assert_quarantined(-ENODEV, false);
	list_del_init(&old.list);
	end_case();
}

static void model_cancel_work_sync(void)
{
	CHECK(fixture.wed_rro.reset_closing &&
	      !fixture.wed_rro.lock.held &&
	      !fixture.wed_rro.reset_owner->lock.held,
	      "close-before-cancellation");
	cancel_calls++;
}

static void test_close_and_queue_order(void)
{
	struct mt7996_npu_rro_reset_owner *owner;
	int queued;

	start_case();
	owner = init_owner();
	CHECK(enqueue_with_modeled_BA(&fixture, 2, 16, 3) == 0,
	      "pre-close-queued");
	queued = queue_calls;
	mt7996_npu_rro_reset_close(&fixture);
	model_cancel_work_sync();
	CHECK(cancel_calls == 1 && owner->closing &&
	      list_count(&owner->held) == 1, "close-moves-pending-before-cancel");
	CHECK(enqueue_with_modeled_BA(&fixture, 3, 17, 4) == 0 &&
	      queue_calls == queued && list_count(&owner->held) == 2,
	      "queue-after-close-refused");
	mt7996_wed_rro_work(&fixture.wed_rro.work);
	CHECK(!send_calls && !mcu_calls, "closed-work-does-not-send");
	mt7996_npu_rro_reset_join(&fixture);
	CHECK(owner->joined && !physical_drain_witness,
	      "software-join-not-physical-drain");
	mt7996_npu_rro_reset_close(&fixture);
	CHECK(list_count(&mt7996_npu_rro_retained) == 1,
	      "close-retains-once");
	end_case();
}

static void test_close_during_responses(void)
{
	struct mt7996_npu_rro_reset_owner *owner;

	start_case();
	owner = init_owner();
	close_on_send = true;
	CHECK(enqueue_with_modeled_BA(&fixture, 9, 33, 1) == 0,
	      "close-during-NPU-seed");
	mt7996_wed_rro_work(&fixture.wed_rro.work);
	CHECK(owner->closing && !owner->inflight &&
	      owner->records[9].phase == MT7996_NPU_RRO_NPU_DONE &&
	      send_calls == 1 && !mcu_calls && list_count(&owner->held) == 1,
	      "close-during-NPU-no-new-MCU-admission");
	mt7996_npu_rro_reset_join(&fixture);
	CHECK(owner->joined && !owner->error, "NPU-close-join-only");
	end_case();

	start_case();
	owner = init_owner();
	close_on_mcu = true;
	CHECK(enqueue_with_modeled_BA(&fixture, 10, 34, 2) == 0,
	      "close-during-MCU-seed");
	mt7996_wed_rro_work(&fixture.wed_rro.work);
	CHECK(owner->closing && !owner->inflight &&
	      owner->records[10].phase == MT7996_NPU_RRO_MCU_ACKED &&
	      send_calls == 1 && mcu_calls == 1 && list_count(&owner->held) == 1,
	      "pre-admitted-MCU-may-complete-during-close");
	mt7996_npu_rro_reset_join(&fixture);
	CHECK(owner->joined && !owner->error && !physical_drain_witness,
	      "admitted-MCU-software-join-only");
	end_case();
}

static void test_consumer_free_retains_records(void)
{
	struct mt7996_npu_rro_reset_owner *owner;
	void *consumer;

	start_case();
	owner = init_owner();
	CHECK(enqueue_with_modeled_BA(&fixture, 77, 255, 8) == 0,
	      "consumer-release-seed");
	mt7996_npu_rro_reset_close(&fixture);
	mt7996_npu_rro_reset_join(&fixture);
	consumer = malloc(8);
	CHECK(consumer != NULL, "model-consumer-allocation");
	free(consumer);
	put_device(&endpoint);
	consumer_released = true;
	CHECK(owner->joined && owner->records[77].arrival == 1 &&
	      owner->records[77].wlan_id == 255 && owner->records[77].tid == 8 &&
	      owner->records[77].phase == MT7996_NPU_RRO_QUEUED &&
	      list_count(&owner->held) == 1 && endpoint.alive &&
	      endpoint.refs == 1 && model_module.refs == 1,
	      "records-survive-consumer-free-with-pins");
	CHECK(!physical_drain_witness, "join-not-physical-drain");
	end_case();
}

static void test_typed_mcu_handoffs(void)
{
	struct mt7996_npu_rro_reset_owner *owner;
	const int errors[] = { -ETIMEDOUT, 6 };

	for (unsigned i = 0; i < ARRAY_SIZE(errors); i++) {
		start_case(); owner = init_owner(); begin_error = errors[i];
		CHECK(!enqueue_with_modeled_BA(&fixture, 11, 35, 3), "typed-begin-seed");
		mt7996_wed_rro_work(&fixture.wed_rro.work);
		CHECK(mcu_begin_calls == 1 && !mcu_calls && !mcu_complete_calls,
		      "typed-begin-error-blocks-physical-MCU");
		CHECK(owner->records[11].ticket == 141 && owner->records[11].generation == 1 &&
		      owner->records[11].phase == MT7996_NPU_RRO_MCU_PREPARING &&
		      owner->records[11].bridge_error == errors[i] && !owner->records[11].mcu_error,
		      "typed-begin-error-retains-ticket-and-raw-bridge-result");
		assert_quarantined(errors[i] < 0 ? errors[i] : -EIO, true); end_case();

		start_case(); owner = init_owner(); complete_error = errors[i];
		CHECK(!enqueue_with_modeled_BA(&fixture, 12, 36, 4), "typed-complete-seed");
		mt7996_wed_rro_work(&fixture.wed_rro.work);
		CHECK(mcu_begin_calls == 1 && mcu_calls == 1 && mcu_complete_calls == 1 &&
		      owner->records[12].phase == MT7996_NPU_RRO_MCU_ACKED &&
		      owner->records[12].bridge_error == errors[i] && !owner->records[12].mcu_error,
		      "typed-completion-error-does-not-overwrite-physical-result");
		assert_quarantined(errors[i] < 0 ? errors[i] : -EIO, true); end_case();
	}
	start_case(); owner = init_owner(); close_on_begin = true;
	CHECK(!enqueue_with_modeled_BA(&fixture, 13, 37, 5), "typed-close-seed");
	mt7996_wed_rro_work(&fixture.wed_rro.work);
	CHECK(owner->closing && mcu_begin_calls == 1 && !mcu_calls && !mcu_complete_calls &&
	      owner->records[13].phase == MT7996_NPU_RRO_MCU_PREPARING && !owner->error,
	      "close-during-typed-begin-does-not-admit-physical-MCU");
	mt7996_npu_rro_reset_join(&fixture); CHECK(owner->joined, "typed-close-software-join"); end_case();
}

int main(int argc, char **argv)
{
	if (argc == 2) {
		if (!strcmp(argv[1], "pin")) {
			start_case();
			init_owner();
			end_case();
		} else if (!strcmp(argv[1], "queue")) {
			test_close_and_queue_order();
		} else if (!strcmp(argv[1], "npu")) {
			test_npu_errors();
		} else if (!strcmp(argv[1], "irq")) {
			test_npu_errors();
		} else if (!strcmp(argv[1], "construction")) {
			test_constructor_event_error();
		} else if (!strcmp(argv[1], "publication")) {
			test_publication_recheck();
		} else if (!strcmp(argv[1], "typed")) {
			test_typed_mcu_handoffs();
		} else {
			CHECK(false, "unknown-targeted-case");
		}
		printf("{\"passed\":true,\"host_model_only\":true,\"cases\":%d}\n", cases);
		return 0;
	}
	CHECK(argc == 1, "unexpected-arguments");
	test_constructor();
	test_missing_owner_close();
	test_constructor_event_error();
	test_publication_recheck();
	test_all_ids_and_bounds();
	test_duplicates_and_conflicts();
	test_npu_errors();
	test_mcu_errors();
	test_provider_loss_no_cpu_fallback();
	test_close_and_queue_order();
	test_close_during_responses();
	test_consumer_free_retains_records();
	test_typed_mcu_handoffs();
	printf("{\"passed\":true,\"host_model_only\":true,\"cases\":%d}\n", cases);
	return 0;
}
