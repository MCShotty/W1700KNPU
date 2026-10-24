/* Actual selected driver C; POSIX NAPI ownership and RCU are explicit models. */
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>

#define BIT(n) (1ul << (n))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define BITS_PER_LONG (8 * sizeof(unsigned long))
#define DECLARE_BITMAP(name, n) unsigned long name[((n) + BITS_PER_LONG - 1) / BITS_PER_LONG]
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define EXPORT_SYMBOL_GPL(name)
#define REQUIRE(c, message) do { if (!(c)) { fprintf(stderr, "%s\n", message); abort(); } } while (0)
#define for_each_set_bit(i, bits, max) for ((i) = 0; (i) < (max); (i)++) if (test_bit((i), (bits)))

struct mutex { pthread_mutex_t lock; };
static void mutex_init(struct mutex *m) { assert(!pthread_mutex_init(&m->lock, NULL)); }
static void mutex_lock(struct mutex *m) { assert(!pthread_mutex_lock(&m->lock)); }
static void mutex_unlock(struct mutex *m) { assert(!pthread_mutex_unlock(&m->lock)); }
static bool test_bit(unsigned int i, const unsigned long *p) { return !!(p[i / BITS_PER_LONG] & BIT(i % BITS_PER_LONG)); }
static void set_bit(unsigned int i, unsigned long *p) { p[i / BITS_PER_LONG] |= BIT(i % BITS_PER_LONG); }
static void clear_bit(unsigned int i, unsigned long *p) { p[i / BITS_PER_LONG] &= ~BIT(i % BITS_PER_LONG); }
static void bitmap_zero(unsigned long *p, unsigned int n) { memset(p, 0, ((n + BITS_PER_LONG - 1) / BITS_PER_LONG) * sizeof(*p)); }
static bool bitmap_empty(const unsigned long *p, unsigned int n) {
    for (unsigned int i = 0; i < n; i++) if (test_bit(i, p)) return false;
    return true;
}

#include "selected-types.inc"

struct mt76_dev;
struct net_device { struct mt76_dev *parent; bool tx; };
struct napi_struct {
    struct net_device *dev;
    bool added, enabled, owned;
    int (*poll)(struct napi_struct *, int);
    unsigned int qid;
    pthread_mutex_t lock;
    pthread_cond_t changed;
};
struct sk_buff { int unused; };
struct mt76_queue { int packets, ndesc; };
struct airoha_npu { int unused; };
struct mt76_driver_ops {
    unsigned long drv_flags;
    void (*rx_poll_complete)(struct mt76_dev *, enum mt76_rxq_id);
    void (*rx_skb)(struct mt76_dev *, enum mt76_rxq_id, struct sk_buff *, uint32_t *);
};
struct mt76_dev {
    struct mt76_driver_ops *drv;
    struct net_device *napi_dev, *tx_napi_dev;
    struct napi_struct napi[__MT_RXQ_MAX], tx_napi;
    struct mt76_queue q_rx[__MT_RXQ_MAX];
    struct mt76_napi_lifetime napi_lifetime;
    struct { struct airoha_npu *npu; } mmio;
};
struct mt7996_dev { struct mt76_dev mt76; };
static struct mt7996_dev chip;
static struct mt76_driver_ops ops;
static struct airoha_npu provider;
static struct sk_buff packet;
static atomic_uint adds, enables, disables, deletes, frees, completions, callbacks;
static atomic_uint rx_calls, rx_post, fills, tx_calls, irq_enables, denied_schedules;
static atomic_uint rcu_readers, grace_calls;
static atomic_ulong scheduled_mask;
static atomic_bool grace_entered, cleanup_done, closing_irq;
static _Thread_local unsigned int rcu_depth;
static pthread_mutex_t rcu_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t rcu_changed = PTHREAD_COND_INITIALIZER;
static pthread_mutex_t gate_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t gate_changed = PTHREAD_COND_INITIALIZER;
static bool pause_tail, tail_released, tail_waiting;
static unsigned int cases;

static void rcu_read_lock(void) {
    assert(!pthread_mutex_lock(&rcu_lock));
    atomic_fetch_add(&rcu_readers, 1); rcu_depth++;
    assert(!pthread_mutex_unlock(&rcu_lock));
}
static void rcu_read_unlock(void) {
    REQUIRE(rcu_depth > 0, "balanced-RCU-reader");
    assert(!pthread_mutex_lock(&rcu_lock));
    rcu_depth--; atomic_fetch_sub(&rcu_readers, 1);
    assert(!pthread_cond_broadcast(&rcu_changed));
    assert(!pthread_mutex_unlock(&rcu_lock));
}
static void synchronize_rcu(void) {
    REQUIRE(!rcu_depth, "no-grace-period-inside-read-section");
    atomic_fetch_add(&grace_calls, 1);
    assert(!pthread_mutex_lock(&rcu_lock));
    atomic_store(&grace_entered, true);
    while (atomic_load(&rcu_readers)) assert(!pthread_cond_wait(&rcu_changed, &rcu_lock));
    assert(!pthread_mutex_unlock(&rcu_lock));
}
#define rcu_dereference(p) (REQUIRE_VALUE(rcu_depth > 0, "provider-lookup-requires-RCU"), (p))
static int REQUIRE_VALUE(bool condition, const char *message) { REQUIRE(condition, message); return 0; }

static void netif_napi_add(struct net_device *netdev, struct napi_struct *napi,
                            int (*poll)(struct napi_struct *, int)) {
    REQUIRE(netdev && netdev->parent == &chip.mt76, "only-live-dummy-device-can-register");
    assert(!pthread_mutex_lock(&napi->lock));
    REQUIRE(!napi->added, "no-duplicate-NAPI-registration");
    napi->dev = netdev; napi->poll = poll; napi->added = true;
    atomic_fetch_add(&adds, 1);
    assert(!pthread_mutex_unlock(&napi->lock));
}
static void netif_napi_add_tx(struct net_device *netdev, struct napi_struct *napi,
                               int (*poll)(struct napi_struct *, int)) {
    REQUIRE(netdev && netdev->tx, "TX-NAPI-uses-TX-dummy-device");
    netif_napi_add(netdev, napi, poll);
}
static void napi_enable(struct napi_struct *napi) {
    assert(!pthread_mutex_lock(&napi->lock));
    REQUIRE(napi->added && !napi->enabled, "enable-only-added-disabled-NAPI-once");
    napi->enabled = true; atomic_fetch_add(&enables, 1);
    assert(!pthread_mutex_unlock(&napi->lock));
}
static void napi_disable(struct napi_struct *napi) {
    assert(!pthread_mutex_lock(&napi->lock));
    REQUIRE(napi->added && napi->enabled, "disable-only-enabled-NAPI-once");
    napi->enabled = false;
    while (napi->owned) assert(!pthread_cond_wait(&napi->changed, &napi->lock));
    atomic_fetch_add(&disables, 1);
    assert(!pthread_mutex_unlock(&napi->lock));
}
static void netif_napi_del(struct napi_struct *napi) {
    assert(!pthread_mutex_lock(&napi->lock));
    REQUIRE(napi->added && !napi->enabled && !napi->owned, "delete-only-registered-disabled-NAPI");
    REQUIRE(!atomic_load(&rcu_readers), "poll-tail-must-finish-before-NAPI-delete");
    napi->added = false; atomic_fetch_add(&deletes, 1);
    assert(!pthread_mutex_unlock(&napi->lock));
}
static void free_netdev(struct net_device *netdev) {
    REQUIRE(netdev && netdev->parent == &chip.mt76, "dummy-storage-freed-exactly-once");
    REQUIRE(!atomic_load(&rcu_readers), "poll-tail-must-finish-before-dummy-free");
    netdev->parent = NULL; free(netdev); atomic_fetch_add(&frees, 1);
}
static bool napi_complete_done(struct napi_struct *napi, int done) {
    REQUIRE(rcu_depth > 0, "completion-and-rearm-tail-must-share-RCU");
    assert(done == 0);
    assert(!pthread_mutex_lock(&napi->lock));
    REQUIRE(napi->owned, "complete-releases-existing-ownership");
    napi->owned = false; atomic_fetch_add(&completions, 1);
    assert(!pthread_cond_broadcast(&napi->changed));
    assert(!pthread_mutex_unlock(&napi->lock));
    assert(!pthread_mutex_lock(&gate_lock));
    if (pause_tail) {
        tail_waiting = true;
        assert(!pthread_cond_broadcast(&gate_changed));
        while (!tail_released) assert(!pthread_cond_wait(&gate_changed, &gate_lock));
    }
    assert(!pthread_mutex_unlock(&gate_lock));
    return true;
}
#define napi_complete(napi) napi_complete_done((napi), 0)
static struct mt76_dev *mt76_priv(struct net_device *dev) {
    REQUIRE(rcu_depth > 0 && dev && dev->parent == &chip.mt76, "poll-device-lookup-within-RCU");
    return dev->parent;
}
static void rx_complete(struct mt76_dev *dev, enum mt76_rxq_id qid) {
    REQUIRE(rcu_depth > 0 && dev == &chip.mt76 && qid < __MT_RXQ_MAX,
        "completion-and-rearm-tail-must-share-RCU");
    REQUIRE(dev->napi_dev && !atomic_load(&cleanup_done), "completion-before-consumer-retirement");
    atomic_fetch_add(&callbacks, 1);
}
static void rx_skb(struct mt76_dev *dev, enum mt76_rxq_id qid, struct sk_buff *skb, uint32_t *info) {
    REQUIRE(rcu_depth && dev == &chip.mt76 && skb == &packet && info && qid < __MT_RXQ_MAX,
        "RX-processing-within-RCU");
    atomic_fetch_add(&rx_calls, 1);
}
static int mt76_dma_rx_process(struct mt76_dev *dev, struct mt76_queue *q, int budget) {
    REQUIRE(rcu_depth && dev == &chip.mt76 && budget > 0, "zero-budget-must-not-run-RX-page-pool-APIs");
    int done = q->packets < budget ? q->packets : budget;
    q->packets -= done; atomic_fetch_add(&rx_calls, done); return done;
}
static void mt76_rx_poll_complete(struct mt76_dev *dev, int qid, struct napi_struct *napi) {
    REQUIRE(rcu_depth && dev == &chip.mt76 && napi == &dev->napi[qid], "RX-postprocess-within-RCU");
    atomic_fetch_add(&rx_post, 1);
}
static bool mt76_npu_irq_poll_allowed(struct mt76_dev *dev) { assert(dev == &chip.mt76); return true; }
static struct sk_buff *mt76_npu_dequeue(struct mt76_dev *dev, struct mt76_queue *q, uint32_t *info) {
    REQUIRE(rcu_depth && dev == &chip.mt76 && info, "NPU-dequeue-within-RCU");
    if (!q->packets) return NULL;
    q->packets--; return &packet;
}
static void mt76_npu_fill_rx_queue(struct mt76_dev *dev, struct mt76_queue *q) {
    REQUIRE(rcu_depth && dev == &chip.mt76 && q, "NPU-fill-within-RCU"); atomic_fetch_add(&fills, 1);
}
#define IS_ERR(p) false
typedef uint32_t u32;
static void mt76_connac_tx_cleanup(struct mt76_dev *dev) {
    REQUIRE(rcu_depth && dev == &chip.mt76 && !atomic_load(&cleanup_done), "TX-cleanup-within-RCU");
    atomic_fetch_add(&tx_calls, 1);
}
#define MT_INT_TX_DONE_MCU 1
static void mt7996_irq_enable(struct mt7996_dev *dev, unsigned int mask) {
    REQUIRE(rcu_depth && dev == &chip && mask == MT_INT_TX_DONE_MCU && dev->mt76.tx_napi_dev,
        "completion-and-rearm-tail-must-share-RCU");
    if (!atomic_load(&closing_irq)) atomic_fetch_add(&irq_enables, 1);
}

#include "selected-control.inc"
#include "selected-rx-poll.inc"
#include "selected-npu-poll.inc"
#include "selected-tx-poll.inc"

static void local_bh_disable(void) {}
static void local_bh_enable(void) {}
static void napi_schedule(struct napi_struct *napi) {
    REQUIRE(napi->qid < __MT_RXQ_MAX && chip.mt76.q_rx[napi->qid].ndesc,
        "reset-must-not-schedule-unallocated-RX");
    REQUIRE(napi->added && napi->enabled, "reset-must-not-schedule-unregistered-RX");
    atomic_fetch_or(&scheduled_mask, BIT(napi->qid));
}
static void restart_RX_enable(struct mt7996_dev *dev) {
    struct mt76_dev *mdev = &dev->mt76;
    int i;
#include "selected-restart-enable.inc"
}
static void L1_RX_enable(struct mt7996_dev *dev) {
    int i;
#include "selected-L1-enable.inc"
}

static struct napi_struct *slot(unsigned int qid) { return mt76_napi_get(&chip.mt76, qid); }
static void reset(void) {
    memset(&chip, 0, sizeof(chip)); memset(&ops, 0, sizeof(ops));
    ops.drv_flags = MT_DRV_NAPI_LIFETIME; ops.rx_poll_complete = rx_complete; ops.rx_skb = rx_skb;
    chip.mt76.drv = &ops; chip.mt76.mmio.npu = &provider;
    mutex_init(&chip.mt76.napi_lifetime.mutex);
    chip.mt76.napi_dev = calloc(1, sizeof(struct net_device));
    chip.mt76.tx_napi_dev = calloc(1, sizeof(struct net_device));
    assert(chip.mt76.napi_dev && chip.mt76.tx_napi_dev);
    chip.mt76.napi_dev->parent = chip.mt76.tx_napi_dev->parent = &chip.mt76;
    chip.mt76.tx_napi_dev->tx = true;
    for (unsigned int i = 0; i < MT76_NAPI_MAX; i++) {
        struct napi_struct *n = slot(i); n->qid = i;
        assert(!pthread_mutex_init(&n->lock, NULL)); assert(!pthread_cond_init(&n->changed, NULL));
    }
    atomic_store(&adds, 0); atomic_store(&enables, 0); atomic_store(&disables, 0);
    atomic_store(&deletes, 0); atomic_store(&frees, 0); atomic_store(&completions, 0);
    atomic_store(&callbacks, 0); atomic_store(&rx_calls, 0); atomic_store(&rx_post, 0);
    atomic_store(&fills, 0); atomic_store(&tx_calls, 0); atomic_store(&irq_enables, 0);
    atomic_store(&denied_schedules, 0); atomic_store(&rcu_readers, 0); atomic_store(&grace_calls, 0);
    atomic_store(&scheduled_mask, 0);
    atomic_store(&grace_entered, false); atomic_store(&cleanup_done, false); atomic_store(&closing_irq, false);
    pause_tail = tail_released = tail_waiting = false;
    cases++;
}
static void finish(void) {
    mt76_napi_cleanup(&chip.mt76);
    REQUIRE(bitmap_empty(chip.mt76.napi_lifetime.added, MT76_NAPI_MAX) &&
        bitmap_empty(chip.mt76.napi_lifetime.enabled, MT76_NAPI_MAX), "closed-registration-and-enable-state-empty");
    REQUIRE(atomic_load(&frees) == 2, "dummy-storage-freed-exactly-once");
    unsigned int old_disables = atomic_load(&disables), old_deletes = atomic_load(&deletes);
    mt76_napi_cleanup(&chip.mt76);
    REQUIRE(atomic_load(&disables) == old_disables && atomic_load(&deletes) == old_deletes &&
        atomic_load(&frees) == 2, "repeated-cleanup-no-second-control-or-free");
    REQUIRE(!mt76_napi_enable(&chip.mt76, 0), "permanent-close-denies-late-enable");
    REQUIRE(mt76_napi_add(&chip.mt76, 0, mt76_dma_rx_poll) == -ESHUTDOWN, "permanent-close-denies-new-registration");
    for (unsigned int i = 0; i < MT76_NAPI_MAX; i++) {
        assert(!pthread_mutex_destroy(&slot(i)->lock)); assert(!pthread_cond_destroy(&slot(i)->changed));
    }
    assert(!pthread_mutex_destroy(&chip.mt76.napi_lifetime.mutex.lock));
}
static void register_one(unsigned int qid, int (*poll)(struct napi_struct *, int)) {
    REQUIRE(mt76_napi_add(&chip.mt76, qid, poll) == 0, "registration-succeeds-before-close");
    REQUIRE(mt76_napi_enable(&chip.mt76, qid), "registered-NAPI-can-enable");
}
static void schedule_napi(struct napi_struct *n) {
    assert(!pthread_mutex_lock(&n->lock));
    REQUIRE(n->added && n->enabled && !n->owned, "schedule-only-registered-enabled-NAPI");
    n->owned = true; assert(!pthread_mutex_unlock(&n->lock));
}
struct poll_call { struct napi_struct *napi; int budget, result; };
static void *poll_thread(void *arg) {
    struct poll_call *call = arg;
    call->result = call->napi->poll(call->napi, call->budget);
    REQUIRE(!rcu_depth, "balanced-RCU-reader"); return NULL;
}
static void *cleanup_thread(void *arg) {
    assert(!arg); atomic_store(&closing_irq, true);
    mt76_napi_cleanup(&chip.mt76); atomic_store(&cleanup_done, true); return NULL;
}
static void adversarial_tail(int mode, bool already_disabled) {
    reset();
    unsigned int qid = mode == 2 ? MT76_NAPI_TX : mode == 1 ? MT_RXQ_NPU0 : MT_RXQ_MAIN;
    int (*poll)(struct napi_struct *, int) = mode == 2 ? mt7996_poll_tx : mode == 1 ? mt76_npu_rx_poll : mt76_dma_rx_poll;
    register_one(qid, poll); schedule_napi(slot(qid)); pause_tail = true;
    struct poll_call call = {slot(qid), 64, -1}; pthread_t reader, cleaner;
    assert(!pthread_create(&reader, NULL, poll_thread, &call));
    assert(!pthread_mutex_lock(&gate_lock));
    while (!tail_waiting) assert(!pthread_cond_wait(&gate_changed, &gate_lock));
    assert(!pthread_mutex_unlock(&gate_lock));
    REQUIRE(atomic_load(&rcu_readers) == 1, "completion-and-rearm-tail-must-share-RCU");
    if (already_disabled) mt76_napi_disable(&chip.mt76, qid);
    assert(!pthread_create(&cleaner, NULL, cleanup_thread, NULL));
    for (unsigned int i = 0; i < 1000000 && !atomic_load(&grace_entered) && !atomic_load(&cleanup_done); i++) sched_yield();
    REQUIRE(atomic_load(&grace_entered) && !atomic_load(&cleanup_done) && !atomic_load(&deletes) && !atomic_load(&frees),
        "ownership-release-is-not-poll-return");
    assert(!pthread_mutex_lock(&gate_lock)); tail_released = true;
    assert(!pthread_cond_broadcast(&gate_changed)); assert(!pthread_mutex_unlock(&gate_lock));
    assert(!pthread_join(reader, NULL)); assert(!pthread_join(cleaner, NULL));
    REQUIRE(call.result == 0 && atomic_load(&disables) == 1 && atomic_load(&deletes) == 1 &&
        atomic_load(&frees) == 2, "tail-joined-before-single-disable-delete-free");
    REQUIRE(mode == 2 ? !atomic_load(&irq_enables) : atomic_load(&callbacks) == 1,
        "accepted-tail-finishes-after-scheduling-close");
    finish();
}
static void serialized_cases(void) {
    reset(); mt76_napi_disable(&chip.mt76, MT76_NAPI_TX);
    REQUIRE(!mt76_napi_enable(&chip.mt76, 0), "missing-registration-cannot-enable");
    REQUIRE(mt76_napi_add(&chip.mt76, MT76_NAPI_MAX, mt76_dma_rx_poll) == -EINVAL &&
        mt76_napi_add(&chip.mt76, 0, NULL) == -EINVAL, "invalid-registration-rejected"); finish();
    for (unsigned int prefix = 0; prefix <= MT76_NAPI_MAX; prefix++) {
        reset();
        for (unsigned int qid = 0; qid < prefix; qid++) {
            REQUIRE(!mt76_napi_add(&chip.mt76, qid, mt76_dma_rx_poll), "registration-succeeds-before-close");
            if (qid % 3) REQUIRE(mt76_napi_enable(&chip.mt76, qid), "registered-NAPI-can-enable");
            if (qid % 3 == 2) mt76_napi_disable(&chip.mt76, qid);
        }
        mt76_napi_cleanup(&chip.mt76);
        REQUIRE(atomic_load(&deletes) == prefix, "partial-prefix-deletes-only-added-instances"); finish();
    }
    reset(); register_one(0, mt76_dma_rx_poll);
    REQUIRE(mt76_napi_add(&chip.mt76, 0, mt76_dma_rx_poll) == -EEXIST, "duplicate-registration-rejected");
    REQUIRE(mt76_napi_enable(&chip.mt76, 0) && atomic_load(&enables) == 1, "repeated-enable-no-second-control");
    mt76_napi_disable(&chip.mt76, 0); mt76_napi_disable(&chip.mt76, 0);
    REQUIRE(atomic_load(&disables) == 1, "disable-only-enabled-NAPI-once");
    REQUIRE(mt76_napi_enable(&chip.mt76, 0), "failed-recovery-can-resume-registered-instance"); finish();
    reset(); ops.drv_flags = 0;
    register_one(0, mt76_dma_rx_poll); mt76_napi_disable(&chip.mt76, 0);
    netif_napi_del(slot(0)); mt76_napi_cleanup(&chip.mt76);
    REQUIRE(chip.mt76.napi_dev && chip.mt76.tx_napi_dev && !atomic_load(&frees) &&
        bitmap_empty(chip.mt76.napi_lifetime.added, MT76_NAPI_MAX), "untracked-driver-retains-existing-control-lifetime");
    ops.drv_flags = MT_DRV_NAPI_LIFETIME; finish();
}
static void budget_cases(void) {
    for (int mode = 0; mode < 3; mode++) for (int budget = 0; budget <= 2; budget++) {
        reset(); unsigned int qid = mode == 2 ? MT76_NAPI_TX : mode == 1 ? MT_RXQ_NPU0 : 0;
        int (*poll)(struct napi_struct *, int) = mode == 2 ? mt7996_poll_tx : mode == 1 ? mt76_npu_rx_poll : mt76_dma_rx_poll;
        register_one(qid, poll); schedule_napi(slot(qid));
        if (mode != 2) chip.mt76.q_rx[qid].packets = budget == 2 ? 2 : 0;
        REQUIRE(poll(slot(qid), budget) == (mode != 2 && budget == 2 ? 2 : 0), "poll-budget-accounting");
        if (!budget) REQUIRE(!atomic_load(&completions) && !atomic_load(&rx_calls) && !atomic_load(&rx_post) &&
            !atomic_load(&fills) && atomic_load(&tx_calls) == (unsigned int)(mode == 2), "zero-budget-no-completion-or-RX-APIs");
        if (mode != 2 && budget == 2) REQUIRE(!atomic_load(&completions), "exhausted-budget-keeps-ownership");
        /* Model the core returning ownership for a budget-only probe. */
        assert(!pthread_mutex_lock(&slot(qid)->lock)); slot(qid)->owned = false;
        assert(!pthread_cond_broadcast(&slot(qid)->changed)); assert(!pthread_mutex_unlock(&slot(qid)->lock));
        finish();
    }
    reset(); chip.mt76.mmio.npu = NULL; register_one(MT_RXQ_NPU0, mt76_npu_rx_poll);
    schedule_napi(slot(MT_RXQ_NPU0)); REQUIRE(!mt76_npu_rx_poll(slot(MT_RXQ_NPU0), 1) &&
        atomic_load(&callbacks) == 1 && !atomic_load(&fills), "provider-loss-completes-within-RCU"); finish();
}
static void readiness_cases(void) {
    for (unsigned int mode = 0; mode < 2; mode++) {
        reset();
        unsigned int qids[] = {MT_RXQ_MAIN, MT_RXQ_RRO_BAND0, MT_RXQ_NPU0};
        for (unsigned int i = 0; i < ARRAY_SIZE(qids); i++) {
            register_one(qids[i], mt76_dma_rx_poll);
            mt76_napi_disable(&chip.mt76, qids[i]);
        }
        chip.mt76.q_rx[MT_RXQ_MAIN].ndesc = 128;
        chip.mt76.q_rx[MT_RXQ_NPU0].ndesc = 512;
        chip.mt76.q_rx[MT_RXQ_NPU1].ndesc = 512;
        if (mode) L1_RX_enable(&chip); else restart_RX_enable(&chip);
        REQUIRE(atomic_load(&scheduled_mask) == (BIT(MT_RXQ_MAIN) | BIT(MT_RXQ_NPU0)),
            "reset-only-schedules-allocated-and-registered-RX");
        REQUIRE(!test_bit(MT_RXQ_RRO_BAND0, chip.mt76.napi_lifetime.enabled),
            "registered-unallocated-RX-remains-disabled");
        finish();
    }
}
int main(int argc, char **argv) {
    const char *mode = argc > 1 ? argv[1] : "all";
    if (!strcmp(mode, "all") || !strcmp(mode, "serial")) serialized_cases();
    if (!strcmp(mode, "all") || !strcmp(mode, "budgets")) budget_cases();
    if (!strcmp(mode, "all") || !strcmp(mode, "readiness")) readiness_cases();
    for (int i = 0; i < 3; i++) if (!strcmp(mode, "all") ||
        (!strcmp(mode, "rx-tail") && i == 0) || (!strcmp(mode, "npu-tail") && i == 1) ||
        (!strcmp(mode, "tx-tail") && i == 2)) {
        adversarial_tail(i, false); adversarial_tail(i, true);
    }
    REQUIRE(cases > 0, "valid-fixture-mode");
    printf("{\"passed\":true,\"cases\":%u,\"kernel_concurrency\":false,\"physical_drain\":false,\"hardware\":false}\n", cases);
    return 0;
}
