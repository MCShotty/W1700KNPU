/* Pthread scheduling models an RCU grace period; extracted mt76 C runs unchanged. */
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

struct mutex { pthread_mutex_t lock; _Atomic bool held; };
struct airoha_npu { _Atomic bool alive; };
struct airoha_ppe_dev { _Atomic bool alive; };
struct mt76_queue { int index; };
struct mt76_dev {
    struct mutex mutex;
    struct {
        _Atomic(struct airoha_npu *) npu;
        _Atomic(struct airoha_ppe_dev *) ppe_dev;
    } mmio;
    struct mt76_queue q_rx[2];
};
enum { MT_RXQ_NPU0, MT_RXQ_NPU1 };
static struct mt76_dev device;
static struct airoha_npu provider;
static struct airoha_ppe_dev ppe;
static pthread_mutex_t gate;
static pthread_cond_t changed;
static int active, entered, completed, premature_put, late_reads, put_count[2], grace_count, cleanup_count;
static int present_mask, cleanup_after_put;
static bool require_cleanup_refs;
static bool permit[8], grace_started, writer_done, active_dma;
static _Atomic unsigned int assertions;

static void check(bool condition)
{
    assert(condition);
    atomic_fetch_add(&assertions, 1);
}

static void wait_event(void)
{
    struct timespec until;
    check(clock_gettime(CLOCK_REALTIME, &until) == 0);
    until.tv_sec += 5;
    check(pthread_cond_timedwait(&changed, &gate, &until) == 0);
}

static void mutex_lock(struct mutex *mutex)
{
    check(pthread_mutex_lock(&mutex->lock) == 0);
    check(!atomic_exchange(&mutex->held, true));
}
static void mutex_unlock(struct mutex *mutex)
{
    check(atomic_exchange(&mutex->held, false));
    check(pthread_mutex_unlock(&mutex->lock) == 0);
}
#define lockdep_is_held(mutex) atomic_load(&(mutex)->held)
#define rcu_replace_pointer(pointer, value, condition) ({ \
    check(condition); atomic_exchange_explicit(&(pointer), (value), memory_order_acq_rel); })

static void synchronize_rcu(void)
{
    check(pthread_mutex_lock(&gate) == 0);
    check(atomic_load(&device.mmio.npu) == NULL && atomic_load(&device.mmio.ppe_dev) == NULL);
    grace_count++;
    grace_started = true;
    check(pthread_cond_broadcast(&changed) == 0);
    while (active)
        wait_event();
    check(pthread_mutex_unlock(&gate) == 0);
}

static void airoha_npu_put(struct airoha_npu *npu)
{
    check(pthread_mutex_lock(&gate) == 0);
    check(npu == &provider && atomic_exchange(&npu->alive, false));
    premature_put += active != 0;
    put_count[0]++;
    check(pthread_mutex_unlock(&gate) == 0);
}
static void airoha_ppe_put_dev(struct airoha_ppe_dev *dev)
{
    check(pthread_mutex_lock(&gate) == 0);
    check(dev == &ppe && atomic_exchange(&dev->alive, false));
    premature_put += active != 0;
    put_count[1]++;
    check(pthread_mutex_unlock(&gate) == 0);
}
static void mt76_npu_queue_cleanup(struct mt76_dev *dev, struct mt76_queue *q)
{
    check(dev == &device && !atomic_load(&dev->mutex.held));
    check(q->index == cleanup_count % 2);
    cleanup_count++;
    if (cleanup_count <= 2) {
        cleanup_after_put += ((present_mask & 1) && !atomic_load(&provider.alive)) ||
                             ((present_mask & 2) && !atomic_load(&ppe.alive));
        if (require_cleanup_refs)
            assert(!cleanup_after_put && "cleanup-after-provider-put");
    }
    /* Kept active deliberately: an RCU grace period cannot drain this actor. */
    check(active_dma);
}
#include "deinit.inc"

static void *reader(void *argument)
{
    int index = (int)(uintptr_t)argument;
    check(pthread_mutex_lock(&gate) == 0);
    active++;
    struct airoha_npu *npu = atomic_load_explicit(&device.mmio.npu, memory_order_acquire);
    struct airoha_ppe_dev *p = atomic_load_explicit(&device.mmio.ppe_dev, memory_order_acquire);
    entered++;
    check(pthread_cond_broadcast(&changed) == 0);
    while (!permit[index])
        wait_event();
    if (npu && !atomic_load(&npu->alive))
        late_reads++;
    if (p && !atomic_load(&p->alive))
        late_reads++;
    active--;
    completed++;
    check(pthread_cond_broadcast(&changed) == 0);
    check(pthread_mutex_unlock(&gate) == 0);
    return NULL;
}

static void *writer(void *argument)
{
    mt76_npu_deinit(&device);
    check(pthread_mutex_lock(&gate) == 0);
    writer_done = true;
    check(pthread_cond_broadcast(&changed) == 0);
    check(pthread_mutex_unlock(&gate) == 0);
    return NULL;
}

static void scenario(bool corrected, int present, int readers, bool reverse)
{
    pthread_t threads[8], teardown;
    check(pthread_mutex_init(&gate, NULL) == 0);
    check(pthread_cond_init(&changed, NULL) == 0);
    check(pthread_mutex_init(&device.mutex.lock, NULL) == 0);
    atomic_store(&device.mutex.held, false);
    atomic_store(&provider.alive, !!(present & 1));
    atomic_store(&ppe.alive, !!(present & 2));
    atomic_store(&device.mmio.npu, present & 1 ? &provider : NULL);
    atomic_store(&device.mmio.ppe_dev, present & 2 ? &ppe : NULL);
    device.q_rx[0].index = 0;
    device.q_rx[1].index = 1;
    active = entered = completed = premature_put = late_reads = grace_count = cleanup_count = 0;
    present_mask = present;
    cleanup_after_put = 0;
    require_cleanup_refs = corrected;
    put_count[0] = put_count[1] = 0;
    memset(permit, 0, sizeof(permit));
    writer_done = grace_started = false;
    active_dma = true;
    for (int i = 0; i < readers; i++)
        check(pthread_create(&threads[i], NULL, reader, (void *)(uintptr_t)i) == 0);
    check(pthread_mutex_lock(&gate) == 0);
    while (entered != readers)
        wait_event();
    check(pthread_mutex_unlock(&gate) == 0);
    check(pthread_create(&teardown, NULL, writer, NULL) == 0);
    check(pthread_mutex_lock(&gate) == 0);
    while (!grace_started && !writer_done)
        wait_event();
    check(!atomic_load(&device.mmio.npu) && !atomic_load(&device.mmio.ppe_dev));
    if (corrected && present) {
        assert(grace_started && !writer_done && "missing-reader-grace");
        assert(put_count[0] == 0 && put_count[1] == 0 && "put-before-reader-grace");
        atomic_fetch_add(&assertions, 2);
    }
    for (int i = 0; i < readers; i++) {
        permit[reverse ? readers - i - 1 : i] = true;
        check(pthread_cond_broadcast(&changed) == 0);
        while (completed != i + 1)
            wait_event();
        if (corrected && present && i + 1 < readers)
            check(!writer_done && put_count[0] == 0 && put_count[1] == 0);
    }
    check(pthread_mutex_unlock(&gate) == 0);
    for (int i = 0; i < readers; i++)
        check(pthread_join(threads[i], NULL) == 0);
    check(pthread_join(teardown, NULL) == 0);
    check(put_count[0] == !!(present & 1) && put_count[1] == !!(present & 2));
    check(cleanup_count == 2 && active_dma);
    if (corrected)
        check(!premature_put && !late_reads && grace_count == !!present);
    else if (present)
        check(premature_put && late_reads);
    int prior_grace = grace_count;
    mt76_npu_deinit(&device);
    check(grace_count == prior_grace && cleanup_count == 4);
    check(put_count[0] == !!(present & 1) && put_count[1] == !!(present & 2));
    printf("{\"providers\":%d,\"readers\":%d,\"reverse\":%s,\"premature_put\":%d,"
           "\"late_reader_access\":%d,\"grace_periods\":%d,\"cleanup_after_put\":%d,"
           "\"physical_dma_still_active\":true}",
           present, readers, reverse ? "true" : "false", premature_put, late_reads, grace_count, cleanup_after_put);
    check(pthread_mutex_destroy(&device.mutex.lock) == 0);
    check(pthread_mutex_destroy(&gate) == 0);
    check(pthread_cond_destroy(&changed) == 0);
}

int main(int argc, char **argv)
{
    check(argc == 2);
    bool corrected = !strcmp(argv[1], "after");
    const int counts[] = {1, 2, 8};
    bool first = true;
    printf("{\"cases\":[");
    for (int present = 0; present < 4; present++) {
        for (int j = 0; j < 3; j++) {
            for (int reverse = 0; reverse < 2; reverse++) {
                if (!first)
                    printf(",");
                scenario(corrected, present, counts[j], reverse);
                first = false;
            }
        }
    }
    printf("],\"assertions\":%u}\n", atomic_load(&assertions));
    return 0;
}
