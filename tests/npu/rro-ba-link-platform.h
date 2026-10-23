/* Single-threaded framework boundaries around the selected real RX BA C. */
static struct mt76_rx_tid *retired_tids[32];
static unsigned retired_count, cancelled_count, freed_frames;
static bool stop_during_dereference;
static struct mt76_wcid *stop_wcid;
static unsigned mcu_fail_ordinal, mcu_link_order[8];
static bool mcu_saw_published;

void mt76_rx_aggr_stop(struct mt76_dev *dev, struct mt76_wcid *wcid, u8 tidno);

static void mt76_rx_aggr_reorder_work(struct work_struct *work) { (void)work; }
#define INIT_DELAYED_WORK(work, callback) ((work)->function = (callback))
#define spin_lock_init(lock) (*(lock) = 0)
#define lockdep_is_held(lock) (*(lock) != 0)
#define lockdep_assert_held(lock) CHECK(*(lock), "RX-TID-creation-under-device-mutex")
#define U64_MAX UINT64_MAX
#define struct_size(pointer, member, count) \
	(sizeof(*(pointer)) + sizeof((pointer)->member[0]) * (count))

static void model_publish_tid(struct mt76_rx_tid **slot, struct mt76_rx_tid *tid)
{
	CHECK(aggr_dev->mt76.mutex, "RX-TID-publication-under-device-mutex");
	CHECK(tid->dev == &aggr_dev->mt76 && tid->reorder_work.function &&
	      !tid->lock && !tid->stopped && !*slot,
	      "RX-TID-initialized-before-publication");
	CHECK(tid->serial && tid->serial == aggr_dev->mt76.rx_tid_serial,
	      "RX-TID-serial-assigned-before-publication");
	*slot = tid;
}
#define rcu_assign_pointer(slot, value) model_publish_tid(&(slot), (value))

static struct mt76_rx_tid *model_replace_tid(struct mt76_rx_tid **slot,
					   struct mt76_rx_tid *value, bool held)
{
	struct mt76_rx_tid *old = *slot;

	CHECK(held && aggr_dev->mt76.mutex, "RX-TID-stop-under-device-mutex");
	CHECK(!value, "RX-TID-unpublication-clears-slot");
	*slot = value;
	host_stop_calls++;
	return old;
}
#define rcu_replace_pointer(slot, value, held) model_replace_tid(&(slot), (value), (held))

static void cancel_delayed_work_sync(struct delayed_work *work)
{
	CHECK(!work->cancelled, "RX-reorder-work-cancelled-once");
	work->cancelled = true;
	cancelled_count++;
}
static void dev_kfree_skb(struct sk_buff *skb) { freed_frames++; free(skb); }
static void model_retire_tid(struct mt76_rx_tid *tid)
{
	CHECK(tid->stopped && !tid->lock && tid->reorder_work.cancelled,
	      "RX-TID-stopped-and-work-cancelled-before-RCU-retirement");
	CHECK(retired_count < ARRAY_SIZE(retired_tids), "retired-fixture-capacity");
	retired_tids[retired_count++] = tid;
}
#define kfree_rcu(pointer, member) model_retire_tid(pointer)

static struct mt76_rx_tid *model_aggr_dereference(struct mt76_rx_tid **slot)
{
	struct mt76_rx_tid *old = *slot;

	CHECK(rcu_depth > 0, "aggr-deref-without-RCU");
	if (stop_during_dereference) {
		stop_during_dereference = false;
		mutex_lock(&aggr_dev->mt76.mutex);
		mt76_rx_aggr_stop(&aggr_dev->mt76, stop_wcid, 2);
		mutex_unlock(&aggr_dev->mt76.mutex);
	}
	return old;
}

#define for_each_sta_active_link(vif, sta, link_sta, link_id) \
	for ((link_id) = 0; (link_id) < 4; (link_id)++) \
		if ((((sta)->valid_links ? ((sta)->valid_links & (vif)->active_links) : 1U) & \
		     (1U << (link_id))) && (((link_sta) = &(sta)->links[link_id]), true))
static struct mt7996_sta_link *
mt7996_sta_link_protected(struct mt7996_dev *dev, struct mt7996_sta *sta, unsigned id)
{
	CHECK(dev->mt76.mutex && id < ARRAY_SIZE(sta->links), "active-link-lookup-under-mutex");
	return sta->links[id];
}
static struct mt7996_vif_link *
mt7996_vif_link(struct mt7996_dev *dev, struct ieee80211_vif *vif, unsigned id)
{
	CHECK(dev->mt76.mutex && id < ARRAY_SIZE(vif->links), "active-vif-lookup-under-mutex");
	return vif->links[id];
}
static int mt7996_mcu_sta_ba(struct mt7996_dev *dev, struct mt76_vif_link *link,
			   struct ieee80211_ampdu_params *params,
			   struct mt76_wcid *wcid, bool enable, bool tx)
{
	struct mt7996_sta *sta = params->sta->drv_priv;
	struct mt76_rx_tid *tid = sta->deflink.wcid.aggr[params->tid];

	CHECK(dev->mt76.mutex && !tx && link && wcid, "modeled-MCU-BA-call-boundary");
	CHECK((unsigned)mcu_rx_calls < ARRAY_SIZE(mcu_link_order), "MCU-fixture-capacity");
	if (enable) {
		CHECK(tid, "MCU-enable-requires-published-RX-TID");
		CHECK(tid->num == params->tid && tid->head == params->ssn &&
		      tid->size == params->buf_size, "MCU-observes-real-RX-TID-geometry");
		mcu_saw_published = true;
	}
	mcu_link_order[mcu_rx_calls++] = link->index;
	return mcu_rx_errno && (!mcu_fail_ordinal || (unsigned)mcu_rx_calls == mcu_fail_ordinal) ?
		mcu_rx_errno : 0;
}
