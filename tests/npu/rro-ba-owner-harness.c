/* Actual RX creation, AMPDU/link/event C and the retained owner execute together.
 * Kernel scheduling/references, transport/backing and physical MCU are models.
 */
#define W1700K_REAL_BA_OWNER 1
#define W1700K_BA_OWNER_SUITE 1
#include "rro-ba-link-harness.c"

static void ba_owner_queue_work(void *hw, struct work_struct *work)
{
	struct mt7996_npu_rro_reset_owner *owner = ba_device->wed_rro.reset_owner;
	CHECK(hw == ba_device && work == &ba_device->wed_rro.work,
	      "BA-owner-queue-target");
	CHECK(ba_device->wed_rro.lock || (owner && owner->lock),
	      "BA-owner-queue-under-admission-lock");
	CHECK(!ba_device->wed_rro.reset_closing && (!owner || !owner->closing),
	      "BA-owner-no-queue-after-close");
	queue_calls++;
}
static int mt76_npu_rro_abort(struct mt76_dev *dev, int error)
{
	CHECK(dev == &ba_device->mt76 && dev->mutex && !rcu_depth &&
	      !ba_device->wed_rro.reset_owner->lock, "modeled-abort-process-boundary");
	ba_abort_calls++;
	return error;
}
static struct mt7996_npu_rro_ba_binding *ba_callback_identity(u32 id)
{
	struct mt7996_npu_rro_reset_owner *owner = ba_device->wed_rro.reset_owner;
	struct mt7996_npu_rro_ba_binding *ba = &owner->bindings[id];
	CHECK(ba_device->mt76.mutex && !rcu_depth && !owner->lock &&
	      ba->serial && ba->reset_serial == ba->serial && ba->serial == ba_callback_serial,
	      "provider-callback-needs-original-retained-identity");
	return ba;
}
static int mt76_npu_rro_reset_npu(struct mt76_dev *dev, u32 id, u32 generation, u32 *ticket)
{
	struct mt7996_npu_rro_reset_owner *owner = ba_device->wed_rro.reset_owner;
	ba_callback_serial = owner->bindings[id].serial;
	ba_callback_identity(id);
	CHECK(dev == &ba_device->mt76 && generation == 1 &&
	      ticket == &owner->records[id].ticket && ba_callback_serial != generation,
	      "reset-journal-generation-not-host-BA-serial");
	ba_npu_calls++;
	*ticket = 130 + id;
	return ba_npu_error;
}
static int mt76_npu_rro_reset_mcu_begin(struct mt76_dev *dev, u32 id, u32 generation, u32 ticket)
{
	ba_callback_identity(id);
	CHECK(dev == &ba_device->mt76 && generation == 1 && ticket == 130 + id,
	      "BA-owner-typed-begin-exact-reset-ticket");
	ba_begin_calls++;
	if (ba_close_on_begin)
		mt7996_npu_rro_reset_close(ba_device);
	return ba_begin_error;
}
static int mt7996_mcu_wed_rro_reset_sessions(struct mt7996_dev *dev, u16 id)
{
	ba_callback_identity(id);
	CHECK(dev == ba_device && dev->wed_rro.reset_owner->records[id].phase == MT7996_NPU_RRO_MCU_POSSIBLE,
	      "BA-owner-MCU-admission-phase");
	ba_mcu_calls++;
	return ba_mcu_error;
}
static int mt76_npu_rro_reset_mcu_complete(struct mt76_dev *dev, u32 id,
					 u32 generation, u32 ticket, int result)
{
	ba_callback_identity(id);
	CHECK(dev == &ba_device->mt76 && generation == 1 && ticket == 130 + id && result == ba_mcu_error,
	      "BA-owner-typed-complete-exact-reset-ticket-and-result");
	ba_complete_calls++;
	return ba_complete_error;
}
static struct mt7996_npu_rro_reset_owner *ba_owner(struct linked_fixture *f)
{
	return f->common.dev.wed_rro.reset_owner;
}
static void ba_setup(struct linked_fixture *f)
{
	CHECK(list_empty(&mt7996_npu_rro_retained), "prior-BA-owner-disposed-only-by-test");
	linked_setup(f);
	ba_device = &f->common.dev;
	ba_endpoint = (struct device){ .refs = 1 };
	ba_module = (struct module){ .enabled = true };
	ba_allocs = ba_frees = ba_alloc_attempts = ba_fail_alloc_ordinal = 0;
	ba_abort_calls = ba_npu_calls = ba_begin_calls = ba_mcu_calls = ba_complete_calls = 0;
	ba_npu_error = ba_begin_error = ba_mcu_error = ba_complete_error = 0;
	ba_fail_device = ba_close_on_begin = false;
	ba_callback_serial = 0;
	ba_device->npu_rro_owned = true;
	ba_device->mt76.dev = &ba_endpoint;
	ba_device->mt76.rx_tid_serial = 40;
	primary(f)->idx = 1;
	f->links[1].wcid.idx = 3;
	f->links[2].wcid.idx = 0;
}
static int ba_init(struct linked_fixture *f)
{
	int error;
	mutex_lock(&f->common.dev.mt76.mutex);
	error = mt7996_npu_rro_reset_init(&f->common.dev);
	mutex_unlock(&f->common.dev.mt76.mutex);
	return error;
}
static void ba_setup_owner(struct linked_fixture *f)
{
	ba_setup(f);
	CHECK(!ba_init(f) && ba_owner(f) && ba_owner(f)->bindings &&
	      ba_allocs == 2 && ba_module.refs == 1 && ba_endpoint.refs == 2,
	      "BA-owner-both-reference-pins");
}
static void ba_work(struct linked_fixture *f)
{
	mutex_lock(&f->common.dev.mt76.mutex);
	mt7996_npu_rro_reset_work(&f->common.dev);
	mutex_unlock(&f->common.dev.mt76.mutex);
}
static void ba_delete(struct linked_fixture *f, u16 id, u16 wlan, u8 tid)
{
	size_t end = put_delete(&f->common, PREFIX_LEN, id, wlan, tid, 0);
	run_event(&f->common, end, end, end);
}
static void ba_finish(struct linked_fixture *f)
{
	struct mt7996_npu_rro_reset_owner *owner = ba_owner(f);
	if (owner) {
		mt7996_npu_rro_reset_close(&f->common.dev);
		mt7996_npu_rro_reset_join(&f->common.dev);
		CHECK(owner->closing && owner->joined && owner->retained_once &&
		      ba_endpoint.refs == 2 && ba_module.refs == 1 && !ba_frees,
		      "published-BA-owner-and-table-remain-pinned");
	}
	linked_finish(f);
	if (owner) {
		/* Test-only disposal after modeled software readers; not production drain. */
		list_del_init(&owner->retained);
		put_device(owner->endpoint);
		module_put(owner->module);
		ba_owner_free(owner->bindings);
		ba_owner_free(owner);
		f->common.dev.wed_rro.reset_owner = NULL;
	}
	CHECK(ba_allocs == ba_frees && ba_endpoint.refs == 1 && !ba_module.refs,
	      "test-only-BA-disposal-balanced");
}
static void ba_create_status(struct linked_fixture *f)
{
	CHECK(!linked_action(f, IEEE80211_AMPDU_RX_START), "actual-BA-RX-creation");
	linked_status(f, 3, 21);
}

static void test_original_link_and_actual_serial(void)
{
	struct linked_fixture f;
	struct mt7996_npu_rro_ba_binding *ba;
	ba_setup_owner(&f);
	ba_create_status(&f);
	ba = &ba_owner(&f)->bindings[21];
	CHECK(ba->serial == current(&f)->serial && ba->serial == 41 &&
	      ba->wlan_id == 3 && ba->primary_wlan_id == 1 && ba->tid == 2 &&
	      !ba->reset_serial && current(&f)->id == 21 && !queue_calls && ba_allocs == 2,
	      "actual-serial-original-active-and-primary-mapping-retained");
	ba_finish(&f);
}
static void test_multiple_links_and_exact_status_duplicate(void)
{
	struct linked_fixture f;
	ba_setup_owner(&f);
	ba_create_status(&f);
	linked_status(&f, 3, 21);
	linked_status(&f, 0, 22);
	CHECK(!ba_owner(&f)->error && !queue_calls &&
	      ba_owner(&f)->bindings[21].serial == 41 && ba_owner(&f)->bindings[22].serial == 41 &&
	      ba_owner(&f)->bindings[22].wlan_id == 0 && ba_owner(&f)->bindings[22].primary_wlan_id == 1,
	      "per-link-associations-and-exact-status-duplicate-preserved");
	ba_finish(&f);
}
static void test_replacement_status_conflict_never_rebinds(void)
{
	struct linked_fixture f;
	ba_setup_owner(&f);
	ba_create_status(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-BA-replacement");
	linked_status(&f, 3, 21);
	CHECK(current(&f)->serial == 42 && !current(&f)->id &&
	      ba_owner(&f)->bindings[21].serial == 41 && ba_owner(&f)->error == -ESTALE &&
	      ba_owner(&f)->bad_serial == 42 && ba_owner(&f)->bad_primary_wlan_id == 1,
	      "conflicting-status-never-rebinds-first-association-or-new-TID");
	ba_work(&f);
	CHECK(ba_abort_calls == 1 && !ba_npu_calls, "conflicting-status-blocks-new-reset");
	ba_finish(&f);
}
static void test_delete_after_replacement_uses_retained_identity(void)
{
	struct linked_fixture f;
	ba_setup_owner(&f);
	ba_create_status(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-BA-replacement");
	ba_delete(&f, 21, 3, 2);
	CHECK(current(&f)->serial == 42 && ba_owner(&f)->bindings[21].reset_serial == 41 &&
	      ba_owner(&f)->records[21].wlan_id == 3 && ba_owner(&f)->records[21].tid == 2,
	      "DELETE-snapshots-original-BA-not-current-slot");
	ba_work(&f);
	CHECK(ba_npu_calls == 1 && ba_begin_calls == 1 && ba_mcu_calls == 1 && ba_complete_calls == 1 &&
	      ba_callback_serial == 41 && ba_owner(&f)->records[21].generation == 1 &&
	      ba_owner(&f)->records[21].phase == MT7996_NPU_RRO_MCU_ACKED,
	      "original-BA-identity-retained-through-reset-models");
	ba_finish(&f);
}
static void test_unbound_delete_and_wrong_tuples(void)
{
	for (unsigned variant = 0; variant < 3; variant++) {
		struct linked_fixture f;
		ba_setup_owner(&f);
		if (variant)
			ba_create_status(&f);
		ba_delete(&f, 21, variant == 1 ? 0 : 3, variant == 2 ? 3 : 2);
		CHECK(ba_owner(&f)->error == (variant ? -ESTALE : -ENODATA) &&
		      !ba_owner(&f)->arrivals && ba_owner(&f)->records[21].phase == MT7996_NPU_RRO_UNUSED,
		      "unbound-or-mismatched-DELETE-refused-before-record-publication");
		ba_work(&f);
		CHECK(!ba_npu_calls && !ba_mcu_calls && ba_abort_calls == 1,
		      "unbound-or-mismatched-DELETE-has-no-reset-side-effects");
		ba_finish(&f);
	}
}
static void test_closed_valid_metadata_retained_without_new_work(void)
{
	struct linked_fixture f;
	ba_setup_owner(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-BA-start");
	mt7996_npu_rro_reset_close(&f.common.dev);
	linked_status(&f, 3, 21);
	CHECK(ba_owner(&f)->bindings[21].serial == 41 && !current(&f)->id && !queue_calls && !ba_owner(&f)->error,
	      "closed-status-retains-metadata-without-ID-write-or-queue");
	ba_delete(&f, 21, 3, 2);
	CHECK(ba_owner(&f)->bindings[21].reset_serial == 41 && !queue_calls &&
	      !list_empty(&ba_owner(&f)->held), "closed-DELETE-retains-original-identity");
	ba_work(&f);
	CHECK(!ba_npu_calls && !ba_mcu_calls, "closed-BA-no-reset-admission");
	ba_finish(&f);
}
static void test_missing_and_stopped_RX_status_faults(void)
{
	for (unsigned stopped = 0; stopped < 2; stopped++) {
		struct linked_fixture f;
		ba_setup_owner(&f);
		if (stopped) {
			CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-BA-start");
			stop_wcid = primary(&f);
			stop_during_dereference = true;
		}
		linked_status(&f, 3, 21);
		CHECK(ba_owner(&f)->error == -EINVAL && ba_owner(&f)->bad_id == 21 &&
		      ba_owner(&f)->bad_wlan_id == 3 && !ba_owner(&f)->bad_serial &&
		      !ba_owner(&f)->bindings[21].serial && !status_writes,
		      "missing-or-stopped-owned-status-retains-first-fault-tuple");
		ba_finish(&f);
	}
}
static void test_nonzero_status_and_mode_change(void)
{
	for (unsigned mode_off = 0; mode_off < 2; mode_off++) {
		struct linked_fixture f;
		ba_setup_owner(&f);
		CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "real-BA-start");
		if (mode_off) {
			f.common.dev.hwrro = false;
			linked_status(&f, 3, 21);
			CHECK(ba_owner(&f)->bindings[21].serial == 41 && current(&f)->id == 21,
			      "owned-status-metadata-retained-after-mode-change");
		} else {
			size_t end = put_status_value(&f.common, PREFIX_LEN, 0x100, 21);
			run_event(&f.common, end, end, end);
			CHECK(!ba_owner(&f)->bindings[21].serial && !ba_owner(&f)->error && !status_writes,
			      "nonzero-status-is-not-BA-creation-binding");
		}
		ba_finish(&f);
	}
}
static void test_corrupt_reset_snapshot_refused(void)
{
	struct linked_fixture f;
	ba_setup_owner(&f);
	ba_create_status(&f);
	ba_delete(&f, 21, 3, 2);
	ba_owner(&f)->bindings[21].reset_serial++;
	ba_work(&f);
	CHECK(ba_owner(&f)->error == -ESTALE && ba_abort_calls == 1 && !ba_npu_calls &&
	      ba_owner(&f)->bindings[21].serial == 41,
	      "worker-refuses-corrupt-BA-snapshot-before-provider-call");
	ba_finish(&f);
}
static void test_errors_and_close_keep_identity(void)
{
	for (unsigned error = 0; error < 5; error++) {
		struct linked_fixture f;
		ba_setup_owner(&f);
		ba_create_status(&f);
		ba_delete(&f, 21, 3, 2);
		if (!error)
			ba_npu_error = -ETIMEDOUT;
		else if (error == 1)
			ba_begin_error = -EIO;
		else if (error == 2)
			ba_mcu_error = -ETIMEDOUT;
		else if (error == 3)
			ba_complete_error = -EIO;
		else
			ba_close_on_begin = true;
		ba_work(&f);
		CHECK(ba_npu_calls == 1 && ba_mcu_calls == (error == 2 || error == 3 ? 1U : 0U) &&
		      ba_owner(&f)->bindings[21].serial == 41 && ba_owner(&f)->bindings[21].reset_serial == 41,
		      "NPU-begin-error-or-close-retains-original-BA-identity");
		ba_finish(&f);
	}
}
static void test_first_unseen_late_status_gap_characterized(void)
{
	struct linked_fixture f;
	ba_setup_owner(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START) && current(&f)->serial == 41,
	      "original-unbound-real-BA");
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "replacement-before-any-status");
	linked_status(&f, 3, 21);
	CHECK(ba_owner(&f)->bindings[21].serial == 42 && current(&f)->id == 21 && !ba_owner(&f)->error,
	      "first-unseen-cookie-less-status-still-binds-replacement-not-a-firmware-fence");
	ba_finish(&f);
}
static void test_constructor_unwinds_both_allocations(void)
{
	for (unsigned failure = 0; failure < 3; failure++) {
		struct linked_fixture f;
		ba_setup(&f);
		if (!failure)
			ba_fail_alloc_ordinal = 2;
		else if (failure == 1)
			ba_module.enabled = false;
		else
			ba_fail_device = true;
		CHECK(ba_init(&f) == (!failure ? -ENOMEM : -ENODEV) && !ba_owner(&f) &&
		      ba_allocs == ba_frees && !ba_module.refs && ba_endpoint.refs == 1,
		      "unpublished-BA-table-and-owner-unwind");
		ba_finish(&f);
	}
}
static void test_closed_invalid_status_keeps_fault_without_queue(void)
{
	struct linked_fixture f;
	ba_setup_owner(&f);
	mt7996_npu_rro_reset_close(&f.common.dev);
	linked_status(&f, 3, 21);
	CHECK(ba_owner(&f)->error == -EINVAL && ba_owner(&f)->bad_id == 21 && !queue_calls,
	      "closed-invalid-status-retains-fault-without-queue");
	ba_finish(&f);
}

int main(void)
{
	test_original_link_and_actual_serial();
	test_multiple_links_and_exact_status_duplicate();
	test_replacement_status_conflict_never_rebinds();
	test_delete_after_replacement_uses_retained_identity();
	test_unbound_delete_and_wrong_tuples();
	test_closed_valid_metadata_retained_without_new_work();
	test_missing_and_stopped_RX_status_faults();
	test_nonzero_status_and_mode_change();
	test_corrupt_reset_snapshot_refused();
	test_errors_and_close_keep_identity();
	test_first_unseen_late_status_gap_characterized();
	test_constructor_unwinds_both_allocations();
	test_closed_invalid_status_keeps_fault_without_queue();
	printf("{\"passed\":true,\"cases\":%u,\"retained_host_BA_identity\":true,"
	       "\"firmware_reuse_fence\":false,\"hardware\":false}\n", cases);
	return 0;
}
