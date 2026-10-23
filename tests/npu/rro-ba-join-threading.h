/* POSIX models of kernel locks/RCU; scheduling gates are test instrumentation. */
#ifndef W1700K_BA_JOIN_THREADING_H
#define W1700K_BA_JOIN_THREADING_H
#include <pthread.h>
#include <stdatomic.h>

struct join_lock_slot { int *key; pthread_mutex_t mutex; };
static struct join_lock_slot join_locks[512];
static pthread_mutex_t join_registry = PTHREAD_MUTEX_INITIALIZER;
static _Thread_local int *join_held[32];
static _Thread_local unsigned join_held_count;
static pthread_rwlock_t join_rcu = PTHREAD_RWLOCK_INITIALIZER;
static atomic_uint join_readers;

static bool join_model_held(const int *lock)
{
	for (unsigned i = 0; i < join_held_count; i++)
		if (join_held[i] == lock)
			return true;
	return false;
}
static pthread_mutex_t *join_model_mutex(int *lock)
{
	pthread_mutex_t *result = NULL;
	CHECK(!pthread_mutex_lock(&join_registry), "join-registry-lock");
	for (unsigned i = 0; i < ARRAY_SIZE(join_locks); i++) {
		if (!join_locks[i].key) {
			CHECK(!pthread_mutex_init(&join_locks[i].mutex, NULL), "join-lock-initialize");
			join_locks[i].key = lock;
		}
		if (join_locks[i].key == lock) {
			result = &join_locks[i].mutex;
			break;
		}
	}
	CHECK(!pthread_mutex_unlock(&join_registry) && result, "join-registry-capacity");
	return result;
}
static void join_model_lock(int *lock)
{
	CHECK(!join_model_held(lock), "join-recursive-model-lock");
	CHECK(!pthread_mutex_lock(join_model_mutex(lock)), "join-model-lock");
	CHECK(!*lock && join_held_count < ARRAY_SIZE(join_held), "join-model-lock-state");
	*lock = 1;
	join_held[join_held_count++] = lock;
}
static void join_model_unlock(int *lock)
{
	unsigned index = join_held_count;
	for (unsigned i = 0; i < join_held_count; i++)
		if (join_held[i] == lock)
			index = i;
	CHECK(index < join_held_count && *lock, "join-model-unlock-owner");
	*lock = 0;
	join_held[index] = join_held[--join_held_count];
	CHECK(!pthread_mutex_unlock(join_model_mutex(lock)), "join-model-unlock");
}
static void join_model_rcu_enter(int depth)
{
	if (!depth) {
		CHECK(!pthread_rwlock_rdlock(&join_rcu), "join-RCU-read-enter");
		atomic_fetch_add(&join_readers, 1);
	}
}
static void join_model_rcu_exit(int depth)
{
	if (!depth) {
		CHECK(atomic_fetch_sub(&join_readers, 1) > 0, "join-RCU-reader-balance");
		CHECK(!pthread_rwlock_unlock(&join_rcu), "join-RCU-read-exit");
	}
}

static struct {
	pthread_mutex_t lock;
	pthread_cond_t condition;
	bool gate_status, gate_worker;
	bool status_waiting, status_release, worker_waiting, worker_release;
	bool cancel_entered, cancel_finished, sync_entered, sync_finished, join_returned;
	bool worker_started, worker_returning, require_reader;
	pthread_t worker;
} join_state = { .lock = PTHREAD_MUTEX_INITIALIZER, .condition = PTHREAD_COND_INITIALIZER };

static void join_state_lock(void) { CHECK(!pthread_mutex_lock(&join_state.lock), "join-state-lock"); }
static void join_state_unlock(void) { CHECK(!pthread_mutex_unlock(&join_state.lock), "join-state-unlock"); }
static void join_signal(void) { CHECK(!pthread_cond_broadcast(&join_state.condition), "join-state-signal"); }
static void join_wait(void) { CHECK(!pthread_cond_wait(&join_state.condition, &join_state.lock), "join-state-wait"); }

static void join_status_gate(void)
{
	join_state_lock();
	if (join_state.gate_status) {
		join_state.status_waiting = true;
		join_signal();
		while (!join_state.status_release)
			join_wait();
	}
	join_state_unlock();
}
static void join_worker_gate(void)
{
	join_state_lock();
	join_state.worker_waiting = true;
	join_signal();
	while (join_state.gate_worker && !join_state.worker_release)
		join_wait();
	join_state_unlock();
}
static void join_reset_state(bool status, bool worker)
{
	CHECK(!atomic_load(&join_readers) && !join_held_count, "prior-join-framework-quiescent");
	join_state_lock();
	CHECK(!join_state.worker_started, "prior-worker-joined");
	join_state.gate_status = status;
	join_state.gate_worker = worker;
	join_state.status_waiting = join_state.status_release = false;
	join_state.worker_waiting = join_state.worker_release = false;
	join_state.cancel_entered = join_state.cancel_finished = false;
	join_state.sync_entered = join_state.sync_finished = join_state.join_returned = false;
	join_state.worker_returning = false;
	join_state.require_reader = status;
	join_state_unlock();
}

#define MODEL_RCU_ENTER(depth) join_model_rcu_enter(depth)
#define MODEL_RCU_EXIT(depth) join_model_rcu_exit(depth)
#define MODEL_STATUS_WRITE_GATE() join_status_gate()
#define MODEL_LOCK_HELD(pointer) join_model_held(pointer)
#endif
