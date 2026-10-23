/* Real allocator/start/shutdown/stop, AMPDU, per-link BA loop and event parser.
 * RCU, locks, work, active-link iteration and physical MCU calls remain models.
 */
#define W1700K_REAL_RX_AGGR 1
#define main previous_ba_fixture_main
#include "rro-reset-ba-harness.c"
#undef main

struct linked_fixture {
	struct mt7996_sta_link links[3];
	struct mt7996_vif_link vif_links[3];
	struct fixture common;
};

static struct mt76_wcid *primary(struct linked_fixture *f)
{
	return &f->common.msta.deflink.wcid;
}
static struct mt76_rx_tid *current(struct linked_fixture *f)
{
	return primary(f)->aggr[2];
}
static void linked_setup(struct linked_fixture *f)
{
	memset(f, 0, sizeof(*f));
	setup(&f->common);
	aggr_dev = &f->common.dev;
	retired_count = cancelled_count = freed_frames = 0;
	stop_during_dereference = false;
	stop_wcid = NULL;
	mcu_fail_ordinal = 0;
	mcu_saw_published = false;
	memset(mcu_link_order, 0xff, sizeof(mcu_link_order));
	primary(f)->sta = &f->common.sta;
	primary(f)->def_wcid = primary(f);
	f->common.dev.wcids[1] = primary(f);
	f->common.sta.valid_links = f->common.vif.active_links = 7;
	f->common.rx_tid.id = 0xbeef;
	for (unsigned i = 0; i < 3; i++) {
		struct mt7996_sta_link *link = i ? &f->links[i] : &f->common.msta.deflink;

		link->wcid.sta = &f->common.sta;
		link->wcid.def_wcid = primary(f);
		if (i)
			link->wcid.aggr[2] = &f->common.rx_tid;
		f->common.msta.links[i] = link;
		f->vif_links[i].mt76.index = i;
		f->common.vif.links[i] = &f->vif_links[i];
	}
	f->common.dev.wcids[3] = &f->links[1].wcid;
	f->common.dev.wcids[0] = &f->links[2].wcid;
}
static int linked_action(struct linked_fixture *f, int action)
{
	struct ieee80211_ampdu_params params = {
		.sta = &f->common.sta, .tid = 2, .ssn = 511, .buf_size = 16, .action = action,
	};
	return mt7996_ampdu_action(&f->common.hw, &f->common.vif, &params);
}
static void linked_status(struct linked_fixture *f, unsigned wlan, u16 id)
{
	size_t used = put_status(&f->common, PREFIX_LEN, wlan, 2, id, 0);
	run_event(&f->common, used, used, used);
}
static void linked_finish(struct linked_fixture *f)
{
	if (current(f)) {
		mutex_lock(&f->common.dev.mt76.mutex);
		mt76_rx_aggr_stop(&f->common.dev.mt76, primary(f), 2);
		mutex_unlock(&f->common.dev.mt76.mutex);
	}
	CHECK(!rcu_depth && cancelled_count == retired_count,
	      "fixture-grace-period-after-all-software-cancellations");
	for (unsigned i = 0; i < retired_count; i++)
		free(retired_tids[i]);
	retired_count = 0;
	finish(&f->common);
}

static void test_primary_creation_status_and_stop(void)
{
	struct linked_fixture f;
	linked_setup(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-RX-TID-created");
	CHECK(current(&f) && mcu_saw_published && mcu_rx_calls == 3,
	      "real-RX-TID-published-before-all-active-link-MCU-calls");
	linked_status(&f, 1, 0x123);
	CHECK(current(&f)->id == 0x123, "primary-status-binds-real-RX-TID");
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_STOP) && !current(&f),
	      "real-RX-stop-unpublishes-before-MCU-disable");
	linked_finish(&f);
}
static void test_secondary_status_uses_primary(void)
{
	struct linked_fixture f;
	linked_setup(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-RX-start");
	linked_status(&f, 3, 0x234);
	CHECK(current(&f)->id == 0x234 && f.common.rx_tid.id == 0xbeef,
	      "secondary-status-resolves-primary-reorder-object");
	linked_status(&f, 0, 0x345);
	CHECK(current(&f)->id == 0x345 && f.common.rx_tid.id == 0xbeef,
	      "third-link-status-resolves-same-primary-object");
	linked_finish(&f);
}
static void test_primary_self_mapping(void)
{
	struct linked_fixture f;
	linked_setup(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-RX-start");
	linked_status(&f, 1, 0x456);
	CHECK(current(&f)->id == 0x456 && primary(&f)->def_wcid == primary(&f),
	      "primary-self-mapping-remains-valid");
	linked_finish(&f);
}
static void test_direct_legacy_mapping(void)
{
	struct linked_fixture f;
	linked_setup(&f);
	f.common.sta.valid_links = f.common.vif.active_links = 0;
	primary(&f)->def_wcid = NULL;
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START) && mcu_rx_calls == 1,
	      "modeled-non-MLD-iterator-selects-default-link");
	linked_status(&f, 1, 0x111);
	CHECK(current(&f)->id == 0x111, "null-def-WCID-keeps-direct-lookup");
	linked_finish(&f);
}
static void test_primary_absent_no_link_fallback(void)
{
	struct linked_fixture f;
	linked_setup(&f);
	linked_status(&f, 3, 0x222);
	CHECK(!status_writes && f.common.rx_tid.id == 0xbeef,
	      "missing-primary-object-must-not-fall-back-to-secondary-slot");
	linked_finish(&f);
}
static void test_stop_between_lookup_and_lock(void)
{
	struct linked_fixture f;
	struct mt76_rx_tid *old;
	linked_setup(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-RX-start");
	old = current(&f);
	old->id = 0x111;
	stop_wcid = primary(&f);
	stop_during_dereference = true;
	linked_status(&f, 3, 0x333);
	CHECK(!current(&f) && old->stopped && old->id == 0x111 && !status_writes &&
	      retired_count == 1 && retired_tids[0] == old,
	      "lookup-before-stop-must-not-write-stopped-RCU-held-object");
	linked_finish(&f);
}
static void test_post_stop_status_ignored(void)
{
	struct linked_fixture f;
	linked_setup(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-RX-start");
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_STOP), "real-RX-stop");
	linked_status(&f, 1, 0x444);
	CHECK(!status_writes && !current(&f), "status-does-not-resurrect-stopped-slot");
	linked_finish(&f);
}
static void test_replacement_stops_and_defers_old(void)
{
	struct linked_fixture f;
	struct mt76_rx_tid *old;
	linked_setup(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-RX-start");
	old = current(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-RX-replacement");
	CHECK(current(&f) != old && old->stopped && old->reorder_work.cancelled &&
	      retired_count == 1 && retired_tids[0] == old,
	      "replacement-shuts-down-old-object-before-publishing-new-object");
	linked_finish(&f);
}
static void test_oom_does_not_enable_mcu(void)
{
	struct linked_fixture f;
	struct mt76_rx_tid *old;
	linked_setup(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-RX-start");
	old = current(&f);
	mcu_rx_calls = 0;
	host_alloc_errno = -ENOMEM;
	CHECK(linked_action(&f, IEEE80211_AMPDU_RX_START) == -ENOMEM &&
	      !current(&f) && !mcu_rx_calls && old->stopped && retired_count == 1,
	      "real-allocation-failure-does-not-enable-MCU");
	linked_finish(&f);
}
static void test_mcu_error_retains_context(void)
{
	struct linked_fixture f;
	linked_setup(&f);
	mcu_rx_errno = -EIO;
	CHECK(linked_action(&f, IEEE80211_AMPDU_RX_START) == -EIO && current(&f) &&
	      !current(&f)->stopped && !retired_count && mcu_rx_calls == 1,
	      "MCU-error-leaves-published-context-characterization-not-rollback-proof");
	linked_finish(&f);
}
static void test_active_link_partial_mcu_failure(void)
{
	struct linked_fixture f;
	linked_setup(&f);
	mcu_rx_errno = -EIO;
	mcu_fail_ordinal = 2;
	CHECK(linked_action(&f, IEEE80211_AMPDU_RX_START) == -EIO &&
	      mcu_rx_calls == 2 && mcu_link_order[0] == 0 && mcu_link_order[1] == 1 && current(&f),
	      "per-link-MCU-loop-stops-after-error-with-context-retained");
	linked_finish(&f);
}
static void test_missing_active_link_objects_are_skipped(void)
{
	struct linked_fixture f;
	linked_setup(&f);
	f.common.msta.links[1] = NULL;
	f.common.vif.links[2] = NULL;
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START) && mcu_rx_calls == 1 &&
	      mcu_link_order[0] == 0, "per-link-loop-skips-missing-station-or-vif-object");
	linked_finish(&f);
}
static void test_late_event_on_replaced_slot_is_unfenced(void)
{
	struct linked_fixture f;
	struct mt76_rx_tid *old;
	linked_setup(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-RX-start");
	old = current(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-RX-replacement");
	linked_status(&f, 3, 0x123);
	CHECK(old->stopped && current(&f) != old && current(&f)->id == 0x123,
	      "cookie-less-late-event-still-targets-current-slot-characterization");
	linked_finish(&f);
}
static void test_real_shutdown_releases_buffered_frames(void)
{
	struct linked_fixture f;
	struct mt76_rx_tid *old;
	linked_setup(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-RX-start");
	old = current(&f);
	old->reorder_buf[1] = calloc(1, sizeof(struct sk_buff));
	old->reorder_buf[3] = calloc(1, sizeof(struct sk_buff));
	CHECK(old->reorder_buf[1] && old->reorder_buf[3], "frame-fixture-allocation");
	old->nframes = 2;
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_STOP) && freed_frames == 2 &&
	      !old->nframes && !old->reorder_buf[1] && !old->reorder_buf[3],
	      "actual-shutdown-disposes-all-buffered-frame-models");
	linked_finish(&f);
}

int main(void)
{
	test_primary_creation_status_and_stop();
	test_secondary_status_uses_primary();
	test_primary_self_mapping();
	test_direct_legacy_mapping();
	test_primary_absent_no_link_fallback();
	test_stop_between_lookup_and_lock();
	test_post_stop_status_ignored();
	test_replacement_stops_and_defers_old();
	test_oom_does_not_enable_mcu();
	test_mcu_error_retains_context();
	test_active_link_partial_mcu_failure();
	test_missing_active_link_objects_are_skipped();
	test_late_event_on_replaced_slot_is_unfenced();
	test_real_shutdown_releases_buffered_frames();
	printf("{\"passed\":true,\"cases\":%u,\"late_cookie_less_rebind_characterized\":true,"
	       "\"MCU_error_context_retained_characterized\":true,\"hardware\":false}\n", cases);
	return 0;
}
