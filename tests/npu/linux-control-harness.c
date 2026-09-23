#define main preserved_provider_test_main
#define airoha_npu_wlan_control preserved_provider_control
#include "control-v2-provider-harness.c"
#undef airoha_npu_wlan_control
#undef main

#include <pthread.h>
#include <stdatomic.h>
#include "linux-control.h"

static const char *suite;
static int checks, cases;
static atomic_int calls;
static int forced_error, corrupt_word;
static u32 corrupt_mask;
static pthread_mutex_t gate = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed = PTHREAD_COND_INITIALIZER;
static bool pause_call, entered, release_call, close_attempt, close_returned;
static _Thread_local bool closing_thread;

static void verify(bool ok, const char *expression, int line)
{
    if (!ok) {
        fprintf(stderr, "FAIL[%s] line %d: %s\n", suite, line, expression);
        abort();
    }
    checks++;
}
#define VERIFY(expression) verify((expression), #expression, __LINE__)

void npu_test_mutex_init(struct mutex *m)
{
    assert(pthread_mutex_init(&m->native, NULL) == 0);
}

void npu_test_mutex_lock(struct mutex *m)
{
    assert(pthread_mutex_lock(&gate) == 0);
    if (closing_thread) {
        close_attempt = true;
        assert(pthread_cond_broadcast(&changed) == 0);
    }
    assert(pthread_mutex_unlock(&gate) == 0);
    assert(pthread_mutex_lock(&m->native) == 0);
}

void npu_test_mutex_unlock(struct mutex *m)
{
    assert(pthread_mutex_unlock(&m->native) == 0);
}

int airoha_npu_wlan_control(struct airoha_npu *provider, void *data, int len)
{
    int result;
    assert(provider == &npu);
    atomic_fetch_add(&calls, 1);
    assert(pthread_mutex_lock(&gate) == 0);
    if (pause_call) {
        entered = true;
        assert(pthread_cond_broadcast(&changed) == 0);
        while (!release_call)
            assert(pthread_cond_wait(&changed, &gate) == 0);
    }
    assert(pthread_mutex_unlock(&gate) == 0);
    if (forced_error)
        return forced_error;
    result = preserved_provider_control(provider, data, len);
    if (!result && corrupt_word >= 0) {
        unsigned char *word = (unsigned char *)data + corrupt_word * 4;
        for (int i = 0; i < 4; i++)
            word[i] ^= (unsigned char)(corrupt_mask >> (8 * i));
    }
    return result;
}

static void fresh(struct npu_linux_control *control)
{
    reset();
    atomic_store(&calls, 0);
    forced_error = 0;
    corrupt_word = -1;
    corrupt_mask = 0;
    pause_call = entered = release_call = close_attempt = close_returned = false;
    closing_thread = false;
    memset(control, 0, sizeof(*control));
    VERIFY(npu_linux_control_init(control, &npu, 0x31415926, 0x27182818) == 0);
}

static struct npu_linux_control_snapshot snapshot(struct npu_linux_control *control)
{
    struct npu_linux_control_snapshot state = {0};
    VERIFY(npu_linux_control_snapshot(control, &state) == 0);
    return state;
}

static void dispose(struct npu_linux_control *control)
{
    npu_linux_control_close(control);
    npu_linux_control_close(control);
    VERIFY(pthread_mutex_destroy(&control->mutex.native) == 0);
    cases++;
}

static void bind_client(struct npu_linux_control *control)
{
    VERIFY(npu_linux_control_exchange(control, NPU_CONTROL_DISCOVER) == 0);
    VERIFY(npu_linux_control_exchange(control, NPU_CONTROL_BIND) == 0);
    struct npu_linux_control_snapshot state = snapshot(control);
    VERIFY(state.client.base.phase == NPU_CLIENT_BOUND && !state.error && !state.closed);
}

static void nominal(void)
{
    struct npu_linux_control control;
    u32 epoch;
    suite = "nominal";
    fresh(&control);
    bind_client(&control);
    VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_STOP) == 0);
    VERIFY(snapshot(&control).client.base.phase == NPU_CLIENT_STOPPING);
    for (u32 hart = 1; hart < 8; hart++)
        VERIFY(npu_barrier_poll(&barrier, hart, &epoch) == NPU_BARRIER_PARK);
    npu_admission_idle(&admission, &barrier);
    VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_STATUS) == 0);
    struct npu_linux_control_snapshot state = snapshot(&control);
    VERIFY(state.client.base.phase == NPU_CLIENT_PARKED);
    VERIFY(state.client.base.parked_mask == 255 && !state.client.base.drain_mask);
    VERIFY(state.client.boot_lo == 0x12345678 && state.client.boot_hi == 0x9abcdef0);
    VERIFY(!npu_barrier_reclaimable(&barrier, state.client.base.epoch));
    VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_STATUS) == 0);
    VERIFY(atomic_load(&calls) == 5 && !depth);
    npu_linux_control_close(&control);
    state = snapshot(&control);
    VERIFY(state.closed && state.error == -ESHUTDOWN && state.client.base.phase == NPU_CLIENT_FAILED);
    VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_STATUS) == -ESHUTDOWN);
    VERIFY(atomic_load(&calls) == 5);
    dispose(&control);
}

static void initialization(void)
{
    struct npu_linux_control control;
    suite = "init";
    fresh(&control);
    bind_client(&control);
    struct npu_linux_control_snapshot before = snapshot(&control);
    VERIFY(npu_linux_control_init(&control, &npu, 4, 5) == -EALREADY);
    struct npu_linux_control_snapshot after = snapshot(&control);
    VERIFY(!memcmp(&before.client, &after.client, sizeof(before.client)) && after.error == before.error);
    npu_linux_control_close(&control);
    VERIFY(npu_linux_control_init(&control, &npu, 4, 5) == -EALREADY);
    VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_DISCOVER) == -ESHUTDOWN);
    dispose(&control);
    for (int missing = 0; missing < 2; missing++) {
        memset(&control, 0, sizeof(control));
        int error = missing ? -ENODEV : -EINVAL;
        VERIFY(npu_linux_control_init(&control, missing ? NULL : &npu,
                                     missing ? 1 : 0, 0) == error);
        VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_DISCOVER) == error);
        VERIFY(npu_linux_control_init(&control, &npu, 4, 5) == -EALREADY);
        VERIFY(snapshot(&control).closed);
        dispose(&control);
    }
    memset(&control, 0, sizeof(control));
    VERIFY(npu_linux_control_init(NULL, &npu, 1, 2) == -EINVAL);
    VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_DISCOVER) == -EINVAL);
    VERIFY(npu_linux_control_exchange(NULL, NPU_CONTROL_DISCOVER) == -EINVAL);
    VERIFY(npu_linux_control_snapshot(&control, &before) == -EINVAL);
    npu_linux_control_close(&control);
    npu_linux_control_close(NULL);
    cases++;
}

static void operations(void)
{
    struct npu_linux_control control;
    suite = "operation";
    for (int op = -1; op <= 4; op++) {
        if (op == NPU_CONTROL_DISCOVER)
            continue;
        fresh(&control);
        VERIFY(npu_linux_control_exchange(&control, (enum npu_control_operation)op) == -EINVAL);
        VERIFY(!atomic_load(&calls));
        VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_DISCOVER) == -EINVAL);
        dispose(&control);
    }
    fresh(&control);
    bind_client(&control);
    VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_BIND) == -EINVAL);
    VERIFY(atomic_load(&calls) == 2 && barrier.request == 1);
    dispose(&control);
}

static void protocol_errors(void)
{
    struct npu_linux_control control;
    suite = "protocol";
    for (int word = 0; word < 20; word++) {
        fresh(&control);
        VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_DISCOVER) == 0);
        corrupt_word = word;
        corrupt_mask = word == 11 || word == 12 ? 256 : word == 13 ? 32 :
                       word == 14 || word == 15 ? 0x80000000u : 1;
        VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_BIND) == -EPROTO);
        struct npu_linux_control_snapshot state = snapshot(&control);
        VERIFY(state.error == -EPROTO && state.client.base.phase == NPU_CLIENT_FAILED);
        int prior_calls = atomic_load(&calls);
        corrupt_word = -1;
        VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_BIND) == -EPROTO);
        VERIFY(atomic_load(&calls) == prior_calls);
        dispose(&control);
    }
}

static void transport_errors(void)
{
    struct npu_linux_control control;
    suite = "sticky";
    for (int index = 0; index < 4; index++) {
        for (int after = 0; after < 2; after++) {
            fresh(&control);
            fault_index = index;
            fault_after = after;
            VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_DISCOVER) == -EIO);
            VERIFY(npu.cores[0].mbox_pending == (index >= 2));
            fault_index = -1;
            VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_DISCOVER) == -EIO);
            VERIFY(atomic_load(&calls) == 1);
            dispose(&control);
        }
    }
    for (int poll_error = 0; poll_error < 2; poll_error++) {
        fresh(&control);
        bind_client(&control);
        deferred = 1;
        poll_fault = poll_error;
        int expected = poll_error ? -EIO : -ETIMEDOUT;
        VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_STOP) == expected);
        VERIFY(npu.cores[0].mbox_pending);
        /* The executor's stack packet is gone; only the coherent copy is used. */
        firmware_complete();
        VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_STATUS) == expected);
        VERIFY(npu_linux_control_init(&control, &npu, 8, 9) == -EALREADY);
        VERIFY(atomic_load(&calls) == 3 && snapshot(&control).error == expected);
        npu_linux_control_close(&control);
        VERIFY(snapshot(&control).error == expected);
        dispose(&control);
    }
    fresh(&control);
    forced_error = 1;
    VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_DISCOVER) == -EIO);
    dispose(&control);
}

struct thread_call { struct npu_linux_control *control; int result; };

static void *exchange_thread(void *arg)
{
    struct thread_call *call = arg;
    call->result = npu_linux_control_exchange(call->control, NPU_CONTROL_DISCOVER);
    return NULL;
}

static void *close_thread(void *arg)
{
    struct thread_call *call = arg;
    closing_thread = true;
    npu_linux_control_close(call->control);
    assert(pthread_mutex_lock(&gate) == 0);
    close_returned = true;
    assert(pthread_cond_broadcast(&changed) == 0);
    assert(pthread_mutex_unlock(&gate) == 0);
    return NULL;
}

static void close_races(void)
{
    struct npu_linux_control control;
    pthread_t sender, closer;
    suite = "close";
    for (int failure = 0; failure < 2; failure++) {
        fresh(&control);
        pause_call = true;
        forced_error = failure ? -EIO : 0;
        struct thread_call call = { .control = &control, .result = 123 };
        VERIFY(pthread_create(&sender, NULL, exchange_thread, &call) == 0);
        VERIFY(pthread_mutex_lock(&gate) == 0);
        while (!entered)
            VERIFY(pthread_cond_wait(&changed, &gate) == 0);
        VERIFY(pthread_create(&closer, NULL, close_thread, &call) == 0);
        while (!close_attempt && !close_returned)
            VERIFY(pthread_cond_wait(&changed, &gate) == 0);
        VERIFY(!close_returned);
        VERIFY(pthread_mutex_trylock(&control.mutex.native) == EBUSY);
        release_call = true;
        VERIFY(pthread_cond_broadcast(&changed) == 0);
        VERIFY(pthread_mutex_unlock(&gate) == 0);
        VERIFY(pthread_join(sender, NULL) == 0);
        VERIFY(pthread_join(closer, NULL) == 0);
        VERIFY(call.result == forced_error && close_returned);
        struct npu_linux_control_snapshot state = snapshot(&control);
        VERIFY(state.closed && state.client.base.phase == NPU_CLIENT_FAILED);
        VERIFY(state.error == (failure ? -EIO : -ESHUTDOWN));
        VERIFY(npu_linux_control_exchange(&control, NPU_CONTROL_DISCOVER) == state.error);
        VERIFY(atomic_load(&calls) == 1);
        dispose(&control);
    }
}

int main(int argc, char **argv)
{
    const char *selected = argc == 2 ? argv[1] : NULL;
    if (!selected || !strcmp(selected, "nominal")) nominal();
    if (!selected || !strcmp(selected, "init")) initialization();
    if (!selected || !strcmp(selected, "operation")) operations();
    if (!selected || !strcmp(selected, "protocol")) protocol_errors();
    if (!selected || !strcmp(selected, "sticky")) transport_errors();
    if (!selected || !strcmp(selected, "close")) close_races();
    VERIFY(cases > 0);
    printf("{\"passed\":true,\"cases\":%d,\"assertions\":%d,"
           "\"provider_model_assertions\":%d,\"physical_drains\":false,"
           "\"layout\":[%zu,%zu,%zu,%zu]}\n",
           cases, checks, assertions, sizeof(struct npu_control_client),
           sizeof(struct npu_control_v2_client), sizeof(struct npu_control_v2_packet),
           offsetof(struct npu_control_v2_client, boot_lo));
    return 0;
}
