/* Actual BA event/owner C with POSIX models of work cancellation and RCU. */
#define W1700K_THREADED_BA_JOIN 1
#define W1700K_BA_JOIN_SUITE 1
#include "rro-ba-owner-harness.c"

static bool cancel_work_sync(struct work_struct *work)
{
	struct mt7996_npu_rro_reset_owner *owner = ba_device->wed_rro.reset_owner;
	bool active;
	pthread_t worker;
	CHECK(work == &ba_device->wed_rro.work && owner && owner->closing && !rcu_depth &&
	      !MODEL_LOCK_HELD(&owner->lock) && !MODEL_LOCK_HELD(&ba_device->mt76.mutex),
	      "owned-close-before-process-cancellation");
	join_state_lock();
	join_state.cancel_entered = true;
	active = join_state.worker_started;
	worker = join_state.worker;
	join_signal();
	join_state_unlock();
	if (active) {
		CHECK(!pthread_equal(worker, pthread_self()), "join-does-not-cancel-itself");
		CHECK(!pthread_join(worker, NULL), "modeled-work-callback-joined");
	}
	join_state_lock();
	join_state.worker_started = false;
	join_state.cancel_finished = true;
	join_signal();
	join_state_unlock();
	return active;
}
static void synchronize_rcu(void)
{
	struct mt7996_npu_rro_reset_owner *owner = ba_device->wed_rro.reset_owner;
	CHECK(owner && owner->closing && !rcu_depth &&
	      !MODEL_LOCK_HELD(&owner->lock) && !MODEL_LOCK_HELD(&ba_device->mt76.mutex),
	      "owned-close-before-process-grace-period");
	join_state_lock();
	CHECK(join_state.cancel_finished && !join_state.worker_started,
	      "work-callback-cancellation-must-precede-status-grace-period");
	CHECK(!join_state.require_reader || atomic_load(&join_readers) > 0,
	      "accepted-status-reader-present-at-grace-period");
	join_state.sync_entered = true;
	join_signal();
	join_state_unlock();
	CHECK(!pthread_rwlock_wrlock(&join_rcu), "modeled-RCU-grace-period-waits-readers");
	CHECK(!pthread_rwlock_unlock(&join_rcu), "modeled-RCU-grace-period-completes");
	join_state_lock();
	join_state.sync_finished = true;
	join_signal();
	join_state_unlock();
}

struct join_event_input { struct mt7996_dev *dev; struct fixture packet; };
static void join_event_prepare(struct join_event_input *input)
{
	size_t end;
	memset(input, 0, sizeof(*input));
	input->dev = ba_device;
	end = put_status(&input->packet, PREFIX_LEN, 3, 2, 21, 0);
	input->packet.skb = (struct sk_buff) {
		.data = input->packet.bytes, .len = end, .linear = end, .pull_limit = end,
	};
}
static void *join_event_thread(void *argument)
{
	struct join_event_input *input = argument;
	mt7996_mcu_wed_rro_event(input->dev, &input->packet.skb);
	CHECK(!rcu_depth && !join_held_count, "event-thread-releases-all-framework-readers");
	return NULL;
}
static void *join_close_thread(void *argument)
{
	struct mt7996_dev *dev = argument;
	mt7996_npu_rro_reset_close(dev);
	mt7996_npu_rro_reset_join(dev);
	join_state_lock();
	join_state.join_returned = true;
	join_signal();
	join_state_unlock();
	return NULL;
}
static void *join_work_thread(void *argument)
{
	struct mt7996_dev *dev = argument;
	mutex_lock(&dev->mt76.mutex);
	mt7996_npu_rro_reset_work(dev);
	/* Model the outer WED callback epilogue after helper inflight is cleared. */
	join_worker_gate();
	mutex_unlock(&dev->mt76.mutex);
	join_state_lock();
	join_state.worker_returning = true;
	join_signal();
	join_state_unlock();
	CHECK(!join_held_count, "worker-thread-releases-all-framework-locks");
	return NULL;
}
static bool join_owner_joined(struct linked_fixture *f)
{
	struct mt7996_npu_rro_reset_owner *owner = ba_owner(f);
	bool joined;
	spin_lock_bh(&owner->lock);
	joined = owner->joined;
	spin_unlock_bh(&owner->lock);
	return joined;
}
static void join_finish(struct linked_fixture *f)
{
	join_state_lock();
	join_state.require_reader = false;
	join_state.gate_status = join_state.gate_worker = false;
	join_state_unlock();
	ba_finish(f);
}

static void test_accepted_status_writer(void)
{
	struct linked_fixture f;
	struct join_event_input input;
	pthread_t event, closer;
	join_reset_state(false, false);
	ba_setup_owner(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "threaded-real-RX-start");
	join_event_prepare(&input);
	join_reset_state(true, false);
	CHECK(!pthread_create(&event, NULL, join_event_thread, &input), "status-thread-created");
	join_state_lock();
	while (!join_state.status_waiting)
		join_wait();
	join_state_unlock();
	CHECK(!pthread_create(&closer, NULL, join_close_thread, ba_device), "close-thread-created");
	join_state_lock();
	while (!join_state.sync_entered && !join_state.join_returned)
		join_wait();
	CHECK(join_state.sync_entered && !join_state.join_returned && !join_owner_joined(&f) &&
	      !atomic_load(&status_writes) && current(&f)->id == 0,
	      "accepted-status-writer-must-finish-before-joined");
	join_state.status_release = true;
	join_signal();
	join_state_unlock();
	CHECK(!pthread_join(event, NULL) && !pthread_join(closer, NULL), "status-and-close-threads-joined");
	CHECK(join_owner_joined(&f) && current(&f)->id == 21 && atomic_load(&status_writes) == 1 &&
	      !atomic_load(&join_readers) && ba_owner(&f)->bindings[21].serial == 41,
	      "accepted-status-complete-before-join-return");
	join_finish(&f);
}
static void test_callback_tail_after_inflight_clear(void)
{
	struct linked_fixture f;
	pthread_t worker, closer;
	join_reset_state(false, false);
	ba_setup_owner(&f);
	ba_create_status(&f);
	ba_delete(&f, 21, 3, 2);
	join_reset_state(false, true);
	CHECK(!pthread_create(&worker, NULL, join_work_thread, ba_device), "reset-worker-thread-created");
	join_state_lock();
	join_state.worker = worker;
	join_state.worker_started = true;
	while (!join_state.worker_waiting)
		join_wait();
	join_state_unlock();
	spin_lock_bh(&ba_owner(&f)->lock);
	CHECK(!ba_owner(&f)->inflight && ba_owner(&f)->records[21].phase == MT7996_NPU_RRO_MCU_ACKED,
	      "helper-inflight-cleared-before-modeled-callback-tail");
	spin_unlock_bh(&ba_owner(&f)->lock);
	CHECK(!pthread_create(&closer, NULL, join_close_thread, ba_device), "work-close-thread-created");
	join_state_lock();
	while (!join_state.cancel_entered && !join_state.join_returned)
		join_wait();
	CHECK(join_state.cancel_entered && !join_state.cancel_finished && !join_state.sync_entered &&
	      !join_state.join_returned && !join_owner_joined(&f),
	      "callback-return-not-inflight-bit-is-work-join-witness");
	join_state.worker_release = true;
	join_signal();
	join_state_unlock();
	CHECK(!pthread_join(closer, NULL), "work-close-thread-joined");
	CHECK(join_owner_joined(&f) && ba_npu_calls == 1 && ba_mcu_calls == 1,
	      "work-and-status-join-finish-with-original-BA-identity");
	join_finish(&f);
}
static void test_join_requires_closed_admission(void)
{
	struct linked_fixture f;
	join_reset_state(false, false);
	ba_setup_owner(&f);
	mt7996_npu_rro_reset_join(ba_device);
	CHECK(!join_owner_joined(&f) && ba_owner(&f)->error == -EUCLEAN &&
	      !join_state.cancel_entered && !join_state.sync_entered,
	      "open-admission-cannot-start-or-advertise-join");
	join_finish(&f);
}
static void test_late_metadata_not_new_ID_write(void)
{
	struct linked_fixture f;
	join_reset_state(false, false);
	ba_setup_owner(&f);
	CHECK(!linked_action(&f, IEEE80211_AMPDU_RX_START), "late-status-real-RX-start");
	mt7996_npu_rro_reset_close(ba_device);
	mt7996_npu_rro_reset_join(ba_device);
	linked_status(&f, 3, 21);
	CHECK(join_owner_joined(&f) && !current(&f)->id && !atomic_load(&status_writes) &&
	      !atomic_load(&queue_calls) && ba_owner(&f)->bindings[21].serial == 41,
	      "post-join-metadata-retention-is-not-new-ID-admission-or-free-authority");
	join_finish(&f);
}
static void test_inflight_corruption_not_promoted(void)
{
	struct linked_fixture f;
	join_reset_state(false, false);
	ba_setup_owner(&f);
	mt7996_npu_rro_reset_close(ba_device);
	ba_owner(&f)->inflight = true;
	mt7996_npu_rro_reset_join(ba_device);
	CHECK(!join_owner_joined(&f) && ba_owner(&f)->error == -EUCLEAN,
	      "corrupt-inflight-state-cannot-be-promoted-to-joined");
	ba_owner(&f)->inflight = false; /* Test-only repair for fixture disposal. */
	join_finish(&f);
}
static void test_missing_owner_has_no_join_work(void)
{
	struct linked_fixture f;
	join_reset_state(false, false);
	ba_setup(&f);
	mt7996_npu_rro_reset_join(ba_device);
	CHECK(!join_state.cancel_entered && !join_state.sync_entered,
	      "missing-owner-cannot-advertise-a-join");
	join_finish(&f);
}

int main(int argc, char **argv)
{
	const char *mode = argc == 2 ? argv[1] : "all";
	CHECK(argc <= 2, "join-fixture-arguments");
	if (!strcmp(mode, "all")) {
		for (unsigned i = 0; i < 32; i++)
			test_accepted_status_writer();
		test_callback_tail_after_inflight_clear();
		test_join_requires_closed_admission();
		test_late_metadata_not_new_ID_write();
		test_inflight_corruption_not_promoted();
		test_missing_owner_has_no_join_work();
	} else if (!strcmp(mode, "status")) {
		test_accepted_status_writer();
	} else if (!strcmp(mode, "worker")) {
		test_callback_tail_after_inflight_clear();
	} else if (!strcmp(mode, "open")) {
		test_join_requires_closed_admission();
	} else if (!strcmp(mode, "late")) {
		test_late_metadata_not_new_ID_write();
	} else if (!strcmp(mode, "inflight")) {
		test_inflight_corruption_not_promoted();
	} else {
		CHECK(false, "join-fixture-mode");
	}
	printf("{\"passed\":true,\"cases\":%u,\"pthread_framework\":true,"
	       "\"kernel_concurrency\":false,\"physical_retirement\":false,\"hardware\":false}\n", cases);
	return 0;
}
