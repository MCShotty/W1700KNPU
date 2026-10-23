/* The selected production structs/functions are generated verbatim by the
 * companion driver. skb linearization, allocator, RCU, locks and MCU calls are
 * single-threaded host models. No hardware or lifetime authentication here. */
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
typedef u16 __le16;
typedef u32 __le32;
#define __packed __attribute__((packed))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define GFP_ATOMIC 1
#define READ_ONCE(value) (value)
#define CHECK(ok, message) assert((ok) && message)
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#define cpu_to_le16(value) ((u16)(value))
#define le16_to_cpu(value) ((u16)(value))
#else
#define cpu_to_le16(value) __builtin_bswap16((u16)(value))
#define le16_to_cpu(value) __builtin_bswap16((u16)(value))
#endif

struct list_head { struct list_head *next, *prev; };
static void INIT_LIST_HEAD(struct list_head *head) { head->next = head->prev = head; }
static bool list_empty(const struct list_head *head) { return head->next == head; }
static void list_add_tail(struct list_head *node, struct list_head *head)
{
	node->next = head;
	node->prev = head->prev;
	head->prev->next = node;
	head->prev = node;
}
#define list_first_entry(head, type, member) \
	((type *)((char *)(head)->next - offsetof(type, member)))
struct work_struct { int unused; };

#include "selected-structs.inc"

struct mt76_rx_tid { u16 id; };
struct mt76_wcid {
	struct mt76_rx_tid *aggr[16];
	void *sta;
	unsigned long ampdu_state;
};
struct mt76_dev { int mutex; };
struct mt7996_dev {
	struct mt76_dev mt76;
	bool npu_rro_owned;
	struct mt76_wcid *wcids[4];
	bool hwrro;
	struct {
		struct work_struct work;
		struct list_head poll_list;
		int lock;
	} wed_rro;
};
struct sk_buff {
	u8 *data;
	size_t len;
	size_t linear;
	size_t pull_limit;
};
struct mt76_txq { bool aggr, send_bar; };
struct ieee80211_txq { void *drv_priv; };
struct ieee80211_sta { void *drv_priv; struct ieee80211_txq *txq[16]; u8 addr[6]; };
struct mt7996_sta { struct { struct mt76_wcid wcid; } deflink; };
struct ieee80211_hw { struct mt7996_dev *dev; };
struct ieee80211_vif { int unused; };
struct ieee80211_ampdu_params {
	struct ieee80211_sta *sta;
	u16 tid, ssn, buf_size;
	int action;
};
enum {
	IEEE80211_AMPDU_RX_START = 1,
	IEEE80211_AMPDU_RX_STOP,
	IEEE80211_AMPDU_TX_OPERATIONAL,
	IEEE80211_AMPDU_TX_STOP_FLUSH,
	IEEE80211_AMPDU_TX_STOP_FLUSH_CONT,
	IEEE80211_AMPDU_TX_START,
	IEEE80211_AMPDU_TX_STOP_CONT,
	IEEE80211_AMPDU_TX_START_IMMEDIATE = 50,
};

static int rcu_depth, rcu_locks, rcu_unlocks, status_writes;
static int host_start_calls, host_stop_calls, mcu_rx_calls, mcu_tx_calls;
static int queue_calls, skb_pull_calls, may_pull_calls, may_pull_failures;
static int host_alloc_errno, mcu_rx_errno;
static bool delete_alloc_fail;
static struct mt76_rx_tid *new_host_tid;

static void rcu_read_lock(void) { rcu_depth++; rcu_locks++; }
static void rcu_read_unlock(void)
{
	CHECK(rcu_depth > 0, "unbalanced-RCU-unlock");
	rcu_depth--;
	rcu_unlocks++;
}
static struct mt76_wcid *mt76_wcid_ptr(struct mt7996_dev *dev, u16 idx)
{
	CHECK(rcu_depth > 0, "wcid-lookup-without-RCU");
	return idx < ARRAY_SIZE(dev->wcids) ? dev->wcids[idx] : NULL;
}
#define rcu_dereference(pointer) (CHECK(rcu_depth > 0, "aggr-deref-without-RCU"), (pointer))
static void model_write_once(u16 *slot, u16 value)
{
	CHECK(rcu_depth > 0, "status-write-without-RCU");
	*slot = value;
	status_writes++;
}
#define WRITE_ONCE(slot, value) model_write_once(&(slot), (value))
static bool mt7996_has_hwrro(struct mt7996_dev *dev) { return dev->hwrro; }
static bool pskb_may_pull(struct sk_buff *skb, size_t bytes)
{
	may_pull_calls++;
	if (bytes > skb->len || bytes > skb->pull_limit) {
		may_pull_failures++;
		return false;
	}
	if (bytes > skb->linear)
		skb->linear = bytes;
	return true;
}
static void *skb_pull(struct sk_buff *skb, size_t bytes)
{
	CHECK(bytes <= skb->len && bytes <= skb->linear, "skb-pull-before-linearization");
	skb->data += bytes;
	skb->len -= bytes;
	skb->linear -= bytes;
	skb->pull_limit -= bytes;
	skb_pull_calls++;
	return skb->data;
}
static void *kzalloc(size_t bytes, int flags)
{
	CHECK(flags == GFP_ATOMIC, "delete-allocator-flag");
	return delete_alloc_fail ? NULL : calloc(1, bytes);
}
static void spin_lock_bh(int *lock)
{
	CHECK(!*lock, "nested-queue-lock");
	*lock = 1;
}
static void spin_unlock_bh(int *lock)
{
	CHECK(*lock == 1, "unbalanced-queue-unlock");
	*lock = 0;
}
#define mt76_hw(dev) (dev)
static void ieee80211_queue_work(void *hw, struct work_struct *work)
{
	CHECK(hw && work, "queue-work-arguments");
	queue_calls++;
}
static struct mt7996_dev *mt7996_hw_dev(struct ieee80211_hw *hw) { return hw->dev; }
static void mutex_lock(int *lock)
{
	CHECK(!*lock, "nested-ampdu-mutex");
	*lock = 1;
}
static void mutex_unlock(int *lock)
{
	CHECK(*lock == 1, "unbalanced-ampdu-mutex");
	*lock = 0;
}
static int mt76_rx_aggr_start(struct mt76_dev *dev, struct mt76_wcid *wcid,
			     u8 tid, u16 ssn, u16 size)
{
	(void)dev;
	(void)ssn;
	(void)size;
	host_start_calls++;
	if (host_alloc_errno)
		return host_alloc_errno;
	wcid->aggr[tid] = new_host_tid;
	return 0;
}
static void mt76_rx_aggr_stop(struct mt76_dev *dev, struct mt76_wcid *wcid, u8 tid)
{
	(void)dev;
	wcid->aggr[tid] = NULL;
	host_stop_calls++;
}
static int mt7996_mcu_add_rx_ba(struct mt7996_dev *dev,
				struct ieee80211_ampdu_params *params,
				struct ieee80211_vif *vif, bool enable)
{
	CHECK(dev && params && vif, "mcu-rx-arguments");
	(void)enable;
	mcu_rx_calls++;
	return mcu_rx_errno;
}
static int mt7996_mcu_add_tx_ba(struct mt7996_dev *dev,
				struct ieee80211_ampdu_params *params,
				struct ieee80211_vif *vif, bool enable)
{
	CHECK(dev && params && vif, "mcu-tx-arguments");
	(void)enable;
	mcu_tx_calls++;
	return 0;
}
static void set_bit(u16 bit, unsigned long *value) { *value |= 1UL << bit; }
static void clear_bit(u16 bit, unsigned long *value) { *value &= ~(1UL << bit); }
static void ieee80211_stop_tx_ba_cb_irqsafe(struct ieee80211_vif *vif,
					    const u8 *addr, u16 tid)
{
	(void)vif;
	(void)addr;
	(void)tid;
}

static int owned_enqueue_calls, owned_enqueue_error;
static u16 owned_id, owned_wlan;
static u8 owned_tid;
static int mt7996_npu_rro_reset_enqueue(struct mt7996_dev *dev, u16 id, u16 wlan, u8 tid)
{
	CHECK(dev->npu_rro_owned, "owned-enqueue-boundary");
	owned_enqueue_calls++;
	owned_id = id;
	owned_wlan = wlan;
	owned_tid = tid;
	return owned_enqueue_error;
}

#include "selected-main.inc"
#include "selected-mcu.inc"

enum { PREFIX_LEN = sizeof(struct mt7996_mcu_rxd) + 4 };
_Static_assert(sizeof(struct mt7996_mcu_wed_rro_event) == PREFIX_LEN + sizeof(struct tlv),
	       "RRO event prefix and first TLV header");
struct fixture {
	struct mt7996_dev dev;
	struct ieee80211_hw hw;
	struct ieee80211_vif vif;
	struct ieee80211_sta sta;
	struct mt7996_sta msta;
	struct ieee80211_txq txq;
	struct mt76_txq mtxq;
	struct mt76_wcid wcid;
	struct mt76_wcid wcid_no_sta;
	struct mt76_rx_tid rx_tid;
	struct sk_buff skb;
	u8 bytes[512];
};

static void setup(struct fixture *f)
{
	memset(f, 0, sizeof(*f));
	host_start_calls = host_stop_calls = mcu_rx_calls = mcu_tx_calls = 0;
	queue_calls = skb_pull_calls = may_pull_calls = may_pull_failures = 0;
	rcu_depth = rcu_locks = rcu_unlocks = status_writes = 0;
	host_alloc_errno = mcu_rx_errno = 0;
	delete_alloc_fail = false;
	new_host_tid = &f->rx_tid;
	f->dev.hwrro = true;
	INIT_LIST_HEAD(&f->dev.wed_rro.poll_list);
	f->dev.wcids[1] = &f->wcid;
	f->dev.wcids[2] = &f->wcid_no_sta;
	f->wcid.sta = &f->sta;
	f->wcid.aggr[2] = &f->rx_tid;
	f->wcid_no_sta.aggr[2] = &f->rx_tid;
	f->hw.dev = &f->dev;
	f->sta.drv_priv = &f->msta;
	f->sta.txq[2] = &f->txq;
	f->txq.drv_priv = &f->mtxq;
}
static void prepare(struct fixture *f, size_t used, size_t linear, size_t limit)
{
	CHECK(used <= sizeof(f->bytes) && linear <= limit && limit <= used,
	      "fixture-skb-bounds");
	f->skb.data = f->bytes;
	f->skb.len = used;
	f->skb.linear = linear;
	f->skb.pull_limit = limit;
}
static void finish(struct fixture *f)
{
	struct list_head *head = &f->dev.wed_rro.poll_list;
	CHECK(!rcu_depth && !f->dev.mt76.mutex && !f->dev.wed_rro.lock,
	      "modeled-boundaries-balanced");
	while (!list_empty(head)) {
		struct mt7996_wed_rro_session_id *entry =
			list_first_entry(head, struct mt7996_wed_rro_session_id, list);
		entry->list.prev->next = entry->list.next;
		entry->list.next->prev = entry->list.prev;
		free(entry);
	}
}
static size_t put_status(struct fixture *f, size_t at, u16 wlan_id, u8 tid,
			 u16 id, size_t extension)
{
	struct mt7996_mcu_wed_rro_ba_event e = { 0 };
	CHECK(at + sizeof(e) + extension <= sizeof(f->bytes), "status-fixture-capacity");
	e.tag = cpu_to_le16(UNI_WED_RRO_BA_SESSION_STATUS);
	e.len = cpu_to_le16(sizeof(e) + extension);
	e.wlan_id = cpu_to_le16(wlan_id);
	e.tid = tid;
	e.id = cpu_to_le16(id);
	memcpy(f->bytes + at, &e, sizeof(e));
	memset(f->bytes + at + sizeof(e), 0xa5, extension);
	return at + sizeof(e) + extension;
}
static size_t put_delete(struct fixture *f, size_t at, u16 id, u16 wlan_id,
			 u8 tid, size_t extension)
{
	struct mt7996_mcu_wed_rro_ba_delete_event e = { 0 };
	CHECK(at + sizeof(e) + extension <= sizeof(f->bytes), "delete-fixture-capacity");
	e.tag = cpu_to_le16(UNI_WED_RRO_BA_SESSION_DELETE);
	e.len = cpu_to_le16(sizeof(e) + extension);
	e.session_id = cpu_to_le16(id);
	e.wlan_id = cpu_to_le16(wlan_id);
	e.tid = tid;
	memcpy(f->bytes + at, &e, sizeof(e));
	memset(f->bytes + at + sizeof(e), 0x5a, extension);
	return at + sizeof(e) + extension;
}
static size_t put_unknown(struct fixture *f, size_t at, u16 tag, size_t length)
{
	struct tlv tlv = { 0 };
	CHECK(length >= sizeof(tlv) && at + length <= sizeof(f->bytes),
	      "unknown-fixture-capacity");
	tlv.tag = cpu_to_le16(tag);
	tlv.len = cpu_to_le16(length);
	memcpy(f->bytes + at, &tlv, sizeof(tlv));
	memset(f->bytes + at + sizeof(tlv), 0x77, length - sizeof(tlv));
	return at + length;
}
static size_t put_header(struct fixture *f, size_t at, u16 tag, u16 length)
{
	struct tlv tlv = { 0 };
	CHECK(at + sizeof(tlv) <= sizeof(f->bytes), "header-fixture-capacity");
	tlv.tag = cpu_to_le16(tag);
	tlv.len = cpu_to_le16(length);
	memcpy(f->bytes + at, &tlv, sizeof(tlv));
	return at + sizeof(tlv);
}
static void run_event(struct fixture *f, size_t used, size_t linear, size_t limit)
{
	prepare(f, used, linear, limit);
	mt7996_mcu_wed_rro_event(&f->dev, &f->skb);
}
static void test_host_start(void)
{
	struct fixture f;
	struct ieee80211_ampdu_params params;
	int ret;

	setup(&f);
	params = (struct ieee80211_ampdu_params){
		.sta = &f.sta, .tid = 2, .ssn = 17, .buf_size = 64,
		.action = IEEE80211_AMPDU_RX_START,
	};
	host_alloc_errno = -ENOMEM;
	ret = mt7996_ampdu_action(&f.hw, &f.vif, &params);
	CHECK(mcu_rx_calls == 0, "no-mcu-on-host-allocation-failure");
	CHECK(ret == -ENOMEM && host_start_calls == 1,
	      "host-allocation-errno-preserved");
	CHECK(f.msta.deflink.wcid.aggr[2] == NULL, "no-host-BA-on-allocation-failure");
	finish(&f);

	setup(&f);
	params.sta = &f.sta;
	mcu_rx_errno = -EIO;
	ret = mt7996_ampdu_action(&f.hw, &f.vif, &params);
	CHECK(ret == -EIO && mcu_rx_calls == 1 && !host_stop_calls,
	      "mcu-error-no-invented-rollback");
	CHECK(f.msta.deflink.wcid.aggr[2] == &f.rx_tid,
	      "mcu-error-host-state-not-rolled-back");
	finish(&f);
}
static void test_no_hwrro_and_short_header(void)
{
	struct fixture f;
	setup(&f);
	f.dev.hwrro = false;
	run_event(&f, 0, 0, 0);
	CHECK(!may_pull_calls && !skb_pull_calls, "no-hwrro-is-noop");
	f.dev.hwrro = true;
	run_event(&f, PREFIX_LEN + 3, PREFIX_LEN + 3, PREFIX_LEN + 3);
	CHECK(may_pull_failures == 1 && !skb_pull_calls && !status_writes,
	      "short-event-header-stops-before-pull");
	finish(&f);
}
static void test_mixed_and_queue_identity(void)
{
	struct fixture f;
	struct mt7996_wed_rro_session_id *entry;
	size_t at = PREFIX_LEN;
	setup(&f);
	at = put_unknown(&f, at, 99, 7);
	at = put_status(&f, at, 1, 2, 0x123, 0);
	at = put_delete(&f, at, 0x456, 0x234, 7, 0);
	at = put_status(&f, at, 1, 2, 0x789, 0);
	run_event(&f, at, at, at);
	CHECK(f.rx_tid.id == 0x789 && status_writes == 2,
	      "mixed-TLV-batch-keeps-processing");
	CHECK(queue_calls == 1 && !list_empty(&f.dev.wed_rro.poll_list),
	      "delete-enqueued-once");
	entry = list_first_entry(&f.dev.wed_rro.poll_list,
				 struct mt7996_wed_rro_session_id, list);
	CHECK(entry->id == 0x456 && entry->wlan_id == 0x234 && entry->tid == 7,
	      "queued-wlan-tid-from-event");
	CHECK(rcu_locks == 2 && rcu_unlocks == 2,
	      "status-RCU-per-record");
	finish(&f);
}
static void test_extended_records(void)
{
	struct fixture f;
	struct mt7996_wed_rro_session_id *entry;
	size_t at = PREFIX_LEN;
	setup(&f);
	at = put_status(&f, at, 1, 2, 0x101, 5);
	at = put_delete(&f, at, 0x202, 0x303, 4, 3);
	at = put_status(&f, at, 1, 2, 0x404, 0);
	run_event(&f, at, PREFIX_LEN + sizeof(struct tlv), at);
	CHECK(f.rx_tid.id == 0x404 && status_writes == 2 && queue_calls == 1,
	      "extended-TLVs-advance-by-declared-length");
	entry = list_first_entry(&f.dev.wed_rro.poll_list,
				 struct mt7996_wed_rro_session_id, list);
	CHECK(entry->id == 0x202 && entry->wlan_id == 0x303 && entry->tid == 4,
	      "extended-delete-preserves-wire-fields");
	finish(&f);
}
static void test_invalid_destinations_continue(void)
{
	struct fixture f;
	size_t at = PREFIX_LEN;
	setup(&f);
	at = put_status(&f, at, 9, 2, 0x111, 0);
	at = put_status(&f, at, 1, 16, 0x222, 0);
	at = put_status(&f, at, 1, 3, 0x333, 0);
	at = put_status(&f, at, 2, 2, 0x334, 0);
	at = put_status(&f, at, 1, 2, 0x444, 0);
	run_event(&f, at, at, at);
	CHECK(f.rx_tid.id == 0x444 && status_writes == 1,
	      "invalid-status-destinations-skip-only-record");
	CHECK(rcu_locks == 5 && rcu_unlocks == 5,
	      "invalid-status-RCU-balanced");
	finish(&f);
}
static void test_malformed_and_short_known(void)
{
	struct fixture f;
	size_t at;
	setup(&f);
	at = put_status(&f, PREFIX_LEN, 1, 2, 0x111, 0);
	at = put_header(&f, at, 99, 2);
	at = put_status(&f, at, 1, 2, 0x222, 0);
	run_event(&f, at, at, at);
	CHECK(f.rx_tid.id == 0x111 && status_writes == 1,
	      "malformed-short-length-stops-batch");
	finish(&f);

	setup(&f);
	at = put_header(&f, PREFIX_LEN, 99, 30);
	at = put_status(&f, at, 1, 2, 0x333, 0);
	run_event(&f, at, at, at);
	CHECK(!status_writes && f.rx_tid.id == 0,
	      "length-beyond-remaining-stops-batch");
	finish(&f);

	setup(&f);
	at = put_header(&f, PREFIX_LEN, UNI_WED_RRO_BA_SESSION_STATUS,
			sizeof(struct tlv));
	at = put_status(&f, at, 1, 2, 0x444, 0);
	run_event(&f, at, at, at);
	CHECK(!status_writes && f.rx_tid.id == 0,
	      "short-known-status-stops-batch");
	finish(&f);

	setup(&f);
	at = put_header(&f, PREFIX_LEN, UNI_WED_RRO_BA_SESSION_DELETE,
			sizeof(struct tlv));
	at = put_delete(&f, at, 0x555, 1, 2, 0);
	run_event(&f, at, at, at);
	CHECK(!queue_calls && list_empty(&f.dev.wed_rro.poll_list),
	      "short-known-delete-stops-batch");
	finish(&f);
}
static void test_pull_boundaries(void)
{
	struct fixture f;
	size_t at;
	setup(&f);
	at = put_status(&f, PREFIX_LEN, 1, 2, 0x111, 0);
	run_event(&f, at, PREFIX_LEN + sizeof(struct tlv),
		  PREFIX_LEN + sizeof(struct tlv) + 3);
	CHECK(!status_writes && may_pull_failures == 1,
	      "nonlinear-record-pull-failure-stops");
	finish(&f);

	setup(&f);
	at = put_status(&f, PREFIX_LEN, 1, 2, 0x222, 0);
	at = put_status(&f, at, 1, 2, 0x333, 0);
	run_event(&f, at, PREFIX_LEN + sizeof(struct tlv),
		  PREFIX_LEN + sizeof(struct mt7996_mcu_wed_rro_ba_event) + 2);
	CHECK(f.rx_tid.id == 0x222 && status_writes == 1 && may_pull_failures == 1,
	      "later-TLV-header-pull-failure-stops");
	finish(&f);
}
static void test_delete_allocator_failure(void)
{
	struct fixture f;
	size_t at = PREFIX_LEN;
	setup(&f);
	at = put_delete(&f, at, 0x123, 1, 2, 0);
	at = put_status(&f, at, 1, 2, 0x456, 0);
	delete_alloc_fail = true;
	run_event(&f, at, at, at);
	CHECK(!queue_calls && !status_writes && list_empty(&f.dev.wed_rro.poll_list),
	      "delete-allocation-failure-stops-batch");
	finish(&f);
}
static void test_owned_delete_route(void)
{
	struct fixture f;
	size_t used;

	setup(&f);
	f.dev.npu_rro_owned = true;
	f.dev.hwrro = false;
	delete_alloc_fail = true;
	owned_enqueue_calls = 0;
	owned_enqueue_error = -EIO;
	used = put_delete(&f, PREFIX_LEN, 0x321, 0x123, 6, 0);
	run_event(&f, used, used, used);
	CHECK(owned_enqueue_calls == 1 && owned_id == 0x321 && owned_wlan == 0x123 && owned_tid == 6,
	      "owned-route-preserves-wire-tuple");
	CHECK(list_empty(&f.dev.wed_rro.poll_list) && !queue_calls,
	      "owned-enqueue-error-does-not-fall-back-to-legacy-allocation");
	finish(&f);
}

int main(void)
{
	test_host_start();
	test_no_hwrro_and_short_header();
	test_mixed_and_queue_identity();
	test_extended_records();
	test_invalid_destinations_continue();
	test_malformed_and_short_known();
	test_pull_boundaries();
	test_delete_allocator_failure();
	test_owned_delete_route();
	puts("{\"passed\":true,\"host_model_only\":true,\"cases\":15}");
	return 0;
}
