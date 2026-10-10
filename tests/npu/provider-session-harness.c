#include <errno.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "linux-control.h"
#include "bootstrap-v2.h"

typedef uint64_t dma_addr_t;
typedef int gfp_t;
struct device { unsigned unused; };
struct list_head { struct list_head *next, *prev; };
struct resource { uint64_t start, end; };
struct airoha_npu { unsigned unused; };
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define container_of(p, type, member) ((type *)((char *)(p) - __builtin_offsetof(type, member)))
#define lower_32_bits(v) ((uint32_t)(v))
#define upper_32_bits(v) ((uint32_t)((v) >> 32))
#define GFP_KERNEL 0
#define NPU_EN7581_7996_PLAN_REGIONS 6
#define NPU_NUM_CORES 8
#define READ_ONCE(value) (value)
#include "provider-session-types.inc"

static uint32_t get_unaligned_le32(const void *p) { uint32_t value; memcpy(&value, p, 4); return value; }
static void put_unaligned_le32(uint32_t value, void *p) { memcpy(p, &value, 4); }

static struct airoha_npu_priv priv;
static struct airoha_npu_dma_lifetime life;
static struct npu_bootstrap bootstrap;
static struct npu_control_v2_session session;
static struct npu_admission admission;
static struct npu_barrier barrier;
static unsigned calls, ticks, rng_calls, case_count;
static unsigned fault_at, effect_fault, mutate_at, mutate_word, mutate_value;
static int fault_error, rng_error;
static unsigned rng_zeros, park_after;
static bool allocated;
static int (*external_transport)(void *, unsigned);
static void (*external_tick)(void);
static pthread_mutex_t gate = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t gate_cv = PTHREAD_COND_INITIALIZER;
static bool block_transport, entered, resume_transport, close_started, close_done;

static void check(bool condition, const char *what)
{
    if (!condition) {
        fprintf(stderr, "FAIL[session] case=%u %s\n", case_count, what);
        exit(11);
    }
}

static void park(void)
{
    for (unsigned i = 0; i < 8; i++)
        barrier.parked[i] = 1;
}

static int get_random_bytes_wait(void *output, size_t bytes)
{
    check(bytes == 8, "nonce size");
    rng_calls++;
    if (rng_error)
        return rng_error;
    uint64_t nonce = rng_calls <= rng_zeros ? 0 : UINT64_C(0x123456789abcdef0);
    memcpy(output, &nonce, bytes);
    return 0;
}

static void mdelay(unsigned ms) { check(ms == 10, "setup delay"); }
static void usleep_range(unsigned lo, unsigned hi)
{
    check(lo == 1000 && hi == 2000, "bounded polling delay");
    ticks++;
    if (external_tick)
        external_tick();
    else if (ticks >= park_after)
        park();
}

static int transaction(void *packet, unsigned bytes)
{
    calls++;
    pthread_mutex_lock(&gate);
    if (block_transport) {
        entered = true;
        pthread_cond_broadcast(&gate_cv);
        while (!resume_transport)
            pthread_cond_wait(&gate_cv, &gate);
    }
    pthread_mutex_unlock(&gate);
    if (calls == fault_at && !effect_fault)
        return fault_error;
    int error = 0;
    if (external_transport) {
        error = external_transport(packet, bytes);
    } else if (bytes == 80) {
        struct npu_control_v2_packet *p = packet;
        if (p->v1.operation == NPU_CONTROL_STOP && !park_after)
            park();
        if (!npu_bootstrap_v2_control(&bootstrap, &session, &admission, &barrier, p, bytes))
            error = -EPROTO;
    } else {
        if (!npu_bootstrap_begin(&bootstrap, &admission, &barrier, packet, bytes))
            error = -EINVAL;
        else if (!npu_bootstrap_finish(&bootstrap, &admission, &barrier, 1))
            error = -EINVAL;
    }
    if (calls == mutate_at) {
        check(bytes == 80 && mutate_word < 20, "reply mutation bounds");
        ((uint32_t *)packet)[mutate_word] = mutate_value;
    }
    return calls == fault_at && effect_fault ? fault_error : error;
}

int airoha_npu_wlan_control(struct airoha_npu *npu, void *packet, int bytes)
{
    check(npu == &priv.npu && bytes == 80, "control provider");
    return transaction(packet, bytes);
}

static int airoha_npu_wlan_msg_send(struct airoha_npu *npu, int index,
                                  enum airoha_npu_wlan_set_cmd command,
                                  void *payload, int bytes, int flags)
{
    check(npu == &priv.npu && bytes == 4 && flags == GFP_KERNEL, "setup provider");
    uint32_t packet[] = {0x10u | (unsigned)index, command, *(uint32_t *)payload};
    return transaction(packet, sizeof(packet));
}

static int airoha_npu_wlan_prepare_memory(struct airoha_npu_priv *p,
                                        struct resource *memory, unsigned *count)
{
    check(p == &priv, "generic provider");
    memcpy(memory, p->wlan_memory, sizeof(p->wlan_memory));
    *count = p->wlan_memory_count;
    return 0;
}

static int airoha_npu_wlan_msg_get(struct airoha_npu *npu, int index,
                                 enum airoha_npu_wlan_get_cmd command,
                                 void *data, int bytes, int flags)
{
    check(npu == &priv.npu && bytes == 4 && flags == GFP_KERNEL, "legacy get");
    uint32_t packet[] = {0x30u | (unsigned)index, command, 0};
    int error = transaction(packet, sizeof(packet));
    if (!error) put_unaligned_le32(packet[2], data);
    return error;
}

#include "provider-session.inc"

void npu_test_reset(uint64_t identity, uint32_t request)
{
    /* Fixture-only CPU destruction; never a production lifetime/recovery API. */
    if (allocated) {
        airoha_npu_wlan_session_close(&priv);
        if (priv.wlan_control.initialized)
            check(!pthread_mutex_destroy(&priv.wlan_control.mutex.native), "executor destroy");
        check(!pthread_mutex_destroy(&priv.wlan_session_lock.native), "setup destroy");
    }
    memset(&priv, 0, sizeof(priv));
    memset(&life, 0, sizeof(life));
    memset(&bootstrap, 0, sizeof(bootstrap));
    memset(&session, 0, sizeof(session));
    npu_barrier_init(&barrier);
    npu_admission_init(&admission);
    const struct npu_bootstrap_plan plan = {.region = {
        {0x80000000, 0x240000}, {0x81000000, 0xe000}, {0x81200000, 0x100000},
        {0x81400000, 0x100000}, {0x81600000, 0x100000}, {request, 256}
    }};
    check(npu_bootstrap_init(&bootstrap, &plan), "server plan");
    check(npu_bootstrap_v2_session_init(&session, &admission, &barrier,
                                      lower_32_bits(identity), upper_32_bits(identity)), "server identity");
    for (unsigned i = 0; i < 4; i++) {
        priv.wlan_memory[i].start = plan.region[i + 1].base;
        priv.wlan_memory[i].end = plan.region[i + 1].base + plan.region[i + 1].bytes - 1;
    }
    priv.wlan_memory_count = 4;
    priv.txbuf_min_size = 0xe000;
    priv.checked_pair = priv.firmware_loaded = priv.boot_attempted = true;
    priv.native_plan_ready = priv.native_published = life.exposed = true;
    priv.boot_identity = identity;
    priv.dma_lifetime = &life;
    mutex_init(&priv.wlan_session_lock);
    calls = ticks = rng_calls = fault_at = mutate_at = rng_zeros = park_after = 0;
    fault_error = rng_error = 0;
    effect_fault = 0;
    external_transport = NULL;
    external_tick = NULL;
    allocated = true;
}

void npu_test_callbacks(int (*transport)(void *, unsigned), void (*tick)(void))
{
    external_transport = transport;
    external_tick = tick;
}

void npu_test_memory(unsigned index, uint32_t base, uint32_t bytes)
{
    check(index < 4 && bytes, "fixture memory");
    priv.wlan_memory[index].start = base;
    priv.wlan_memory[index].end = (uint64_t)base + bytes - 1;
}

int npu_test_run(void) { return airoha_npu_wlan_init_session(&priv.npu); }
int npu_test_command(unsigned header, unsigned api, unsigned value, uint32_t *output)
{
    int error = header == 0x30 ?
        airoha_npu_wlan_msg_get_session(&priv.npu, 0, api, &value, 4, GFP_KERNEL) :
        airoha_npu_wlan_msg_send_session(&priv.npu, header & 15, api, &value, 4, GFP_KERNEL);
    *output = value;
    return error;
}
void npu_test_close(void) { airoha_npu_wlan_session_close(&priv); }
unsigned npu_test_calls(void) { return calls; }
unsigned npu_test_ticks(void) { return ticks; }
unsigned npu_test_rng_calls(void) { return rng_calls; }
int npu_test_error(void) { return priv.wlan_session_error; }
unsigned npu_test_phase(void) { return priv.wlan_control.client.base.phase; }
unsigned npu_test_closed(void) { return priv.wlan_control.closed; }

static void fresh(void) { npu_test_reset(UINT64_C(0x1122334455667788), 0x83000000); case_count++; }

static void retained(int expected)
{
    unsigned old_calls = calls, old_rng = rng_calls;
    int closed_error = priv.wlan_session_error ? expected : -ESHUTDOWN;
    check(npu_test_run() == expected, "no setup replay");
    check(calls == old_calls && rng_calls == old_rng, "no new nonce or transport");
    npu_test_close();
    check(npu_test_run() == closed_error, "sticky close");
    check(calls == old_calls && rng_calls == old_rng && life.exposed, "retained exposure");
    check(!barrier.released && !barrier.armed && !barrier.drained[0], "no release/arm/drain");
}

static void *setup_thread(void *output) { *(int *)output = npu_test_run(); return NULL; }
static void *close_thread(void *unused)
{
    (void)unused;
    pthread_mutex_lock(&gate);
    close_started = true;
    pthread_cond_broadcast(&gate_cv);
    pthread_mutex_unlock(&gate);
    npu_test_close();
    pthread_mutex_lock(&gate);
    close_done = true;
    pthread_cond_broadcast(&gate_cv);
    pthread_mutex_unlock(&gate);
    return NULL;
}

static void threads(bool closing)
{
    fresh();
    pthread_t first, second;
    int a = -999, b = -999;
    block_transport = true;
    entered = resume_transport = close_started = close_done = false;
    check(!pthread_create(&first, NULL, setup_thread, &a), "first thread");
    pthread_mutex_lock(&gate);
    while (!entered)
        pthread_cond_wait(&gate_cv, &gate);
    pthread_mutex_unlock(&gate);
    check(!pthread_create(&second, NULL, closing ? close_thread : setup_thread, &b), "second thread");
    pthread_mutex_lock(&gate);
    if (closing) {
        while (!close_started)
            pthread_cond_wait(&gate_cv, &gate);
        check(!close_done, "close must join executing setup");
    }
    resume_transport = true;
    pthread_cond_broadcast(&gate_cv);
    pthread_mutex_unlock(&gate);
    check(!pthread_join(first, NULL) && !pthread_join(second, NULL), "join threads");
    block_transport = false;
    check(a == 0 && calls == 9 && rng_calls == 1, "one setup lane");
    if (closing)
        check(close_done && npu_test_run() == -ESHUTDOWN && priv.wlan_control.closed, "closed setup");
    else
        check(b == -EBUSY, "second consumer cannot enroll");
}

int main(void)
{
    fresh();
    check(!npu_test_run() && calls == 9 && rng_calls == 1 && !ticks, "nominal");
    check(priv.wlan_control.client.base.phase == NPU_CLIENT_PARKED, "parked client");
    retained(-EBUSY);
    for (unsigned delay = 1; delay <= 101; delay++) {
        fresh(); park_after = delay;
        int expected = delay <= 100 ? 0 : -ETIMEDOUT;
        check(npu_test_run() == expected && ticks == (delay <= 100 ? delay : 100), "poll boundary");
        retained(expected ? expected : -EBUSY);
    }
    for (unsigned slot = 1; slot <= 10; slot++)
        for (unsigned effect = 0; effect <= 1; effect++)
            for (unsigned kind = 0; kind < 4; kind++) {
                fresh(); park_after = slot == 10 ? 1 : 0;
                fault_at = slot; effect_fault = effect;
                fault_error = kind == 0 ? -ETIMEDOUT : kind == 1 ? -EBUSY : kind == 2 ? -EIO : 7;
                int expected = fault_error < 0 ? fault_error : -EIO;
                check(npu_test_run() == expected && calls == slot, "transaction error stop");
                retained(expected);
            }
    for (unsigned zeros = 0; zeros <= 3; zeros++) {
        fresh(); rng_zeros = zeros;
        check(npu_test_run() == (zeros == 3 ? -EAGAIN : 0), "nonce zero handling");
        check(rng_calls == (zeros == 3 ? 3 : zeros + 1), "nonce bounded calls");
        retained(zeros == 3 ? -EAGAIN : -EBUSY);
    }
    fresh(); rng_error = -EINTR;
    check(npu_test_run() == -EINTR && !calls, "RNG failure before transport"); retained(-EINTR);
    for (unsigned field = 0; field < 9; field++) {
        fresh();
        switch (field) {
        case 0: priv.firmware_loaded = false; break;
        case 1: priv.boot_attempted = false; break;
        case 2: priv.native_plan_ready = false; break;
        case 3: priv.native_published = false; break;
        case 4: priv.boot_identity = 0; break;
        case 5: priv.dma_lifetime = NULL; break;
        case 6: life.exposed = false; break;
        case 7: priv.wlan_memory_count = 3; break;
        case 8: priv.wlan_memory_count = 5; break;
        }
        check(npu_test_run() == -EINVAL && !calls && !rng_calls, "precondition before transport");
        if (field == 6) life.exposed = true;
        retained(-EINVAL);
    }
    const unsigned slots[] = {1, 8, 9, 10};
    for (unsigned i = 0; i < ARRAY_SIZE(slots); i++)
        for (unsigned word = 0; word < 20; word++) {
            fresh(); park_after = slots[i] == 10 ? 1 : 0;
            mutate_at = slots[i]; mutate_word = word;
            /* Mutate every wire field to a value invalid for its role. */
            mutate_value = word == 11 ? 0x100 : word == 12 ? 1 : word == 13 ? 1 :
                           word == 19 ? 1 : word == 17 || word == 18 ? 0xfedcba98 : 0;
            if (word == 1 || word == 9) mutate_value = 1;
            if (word == 5) mutate_value = 0xff;
            if (word == 14 || word == 15) mutate_value = 1;
            check(npu_test_run() == -EPROTO, "malformed/unheld reply");
            check(calls == slots[i], "bad reply stops before subsequent setup");
            retained(-EPROTO);
        }
    fresh(); npu_test_close();
    check(npu_test_run() == -ESHUTDOWN && !calls && !rng_calls, "close before first consumer");
    threads(false); threads(true);
    unsigned total = case_count;
    npu_test_reset(UINT64_C(0x1122334455667788), 0x83000000);
    npu_test_close();
    check(!pthread_mutex_destroy(&priv.wlan_session_lock.native), "final fixture destroy");
    allocated = false;
    printf("{\"passed\":true,\"cases\":%u,\"transaction_faults\":80,"
           "\"malformed_replies\":80,\"poll_boundaries\":101,\"thread_cases\":2}\n", total);
    return 0;
}
