/* Single-threaded owner allocation/reference/queue and provider/MCU boundaries. */
#define IEEE80211_NUM_TIDS 16
#ifdef static_assert
#undef static_assert
#endif
#define static_assert(condition, ...) _Static_assert(condition, #condition)
#define LIST_HEAD(name) struct list_head name = { &(name), &(name) }
#define DEFINE_SPINLOCK(name) spinlock_t name = 0
#define smp_load_acquire(pointer) (*(pointer))
#define smp_store_release(pointer, value) (*(pointer) = (value))

struct device { int refs; };
struct module { int refs; bool enabled; };
static struct device ba_endpoint;
static struct module ba_module;
static struct mt7996_dev *ba_device;
static unsigned ba_allocs, ba_frees, ba_alloc_attempts, ba_fail_alloc_ordinal;
static bool ba_fail_device;
static unsigned ba_abort_calls, ba_npu_calls, ba_begin_calls, ba_mcu_calls, ba_complete_calls;
static int ba_npu_error, ba_begin_error, ba_mcu_error, ba_complete_error;
static bool ba_close_on_begin;
static u64 ba_callback_serial;
#define THIS_MODULE (&ba_module)

static void list_del_init(struct list_head *node)
{
	CHECK(node->next->prev == node && node->prev->next == node, "owner-list-unlink");
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
static void *ba_owner_zalloc(size_t size, int flags)
{
	void *pointer;
	CHECK(flags == GFP_KERNEL && ba_device->mt76.mutex && !rcu_depth,
	      "owner-allocation-only-process-context");
	ba_alloc_attempts++;
	if (ba_fail_alloc_ordinal == ba_alloc_attempts)
		return NULL;
	pointer = calloc(1, size);
	CHECK(pointer, "owner-host-allocation");
	ba_allocs++;
	return pointer;
}
static void *ba_owner_calloc(size_t count, size_t size, int flags)
{
	CHECK(count == MT7996_RRO_MAX_SESSION + 1 && size && count <= SIZE_MAX / size,
	      "full-geometry-preallocated-BA-table");
	return ba_owner_zalloc(count * size, flags);
}
static void ba_owner_free(void *pointer)
{
	CHECK(pointer && !rcu_depth, "unpublished-owner-free-process-context");
	ba_frees++;
	free(pointer);
}
static bool try_module_get(struct module *module)
{
	CHECK(module == &ba_module, "BA-module-identity");
	if (!module->enabled)
		return false;
	module->refs++;
	return true;
}
static void module_put(struct module *module)
{
	CHECK(module == &ba_module && module->refs > 0, "BA-module-pin-balanced");
	module->refs--;
}
static struct device *get_device(struct device *device)
{
	CHECK(device == &ba_endpoint, "BA-endpoint-identity");
	if (ba_fail_device)
		return NULL;
	device->refs++;
	return device;
}
static void put_device(struct device *device)
{
	CHECK(device == &ba_endpoint && device->refs > 1, "BA-endpoint-pin-balanced");
	device->refs--;
}
static bool is_mt7996(struct mt76_dev *dev)
{
	CHECK(dev == &ba_device->mt76, "modeled-chip-identity");
	return true;
}
static void ba_owner_queue_work(void *hw, struct work_struct *work);
static int mt76_npu_rro_abort(struct mt76_dev *dev, int error);
static int mt76_npu_rro_reset_npu(struct mt76_dev *dev, u32 id, u32 generation, u32 *ticket);
static int mt76_npu_rro_reset_mcu_begin(struct mt76_dev *dev, u32 id, u32 generation, u32 ticket);
static int mt76_npu_rro_reset_mcu_complete(struct mt76_dev *dev, u32 id,
					 u32 generation, u32 ticket, int result);
static int mt7996_mcu_wed_rro_reset_sessions(struct mt7996_dev *dev, u16 id);
static bool cancel_work_sync(struct work_struct *work);
static void synchronize_rcu(void);
