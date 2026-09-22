/* Kernel devres/IRQ/work behavior is modeled; driver/helper C is extracted. */
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
typedef uint64_t u64;
typedef uint64_t dma_addr_t;
typedef unsigned int gfp_t;
typedef int spinlock_t;
typedef int irqreturn_t;
struct work_struct;
typedef void (*work_func_t)(struct work_struct *);
struct work_struct { work_func_t fn; bool initialized, pending, running; unsigned int cancels; };
struct device { void *of_node; };
struct platform_device { struct device dev; void *data; };
struct resource { u64 start, end; };
struct regmap { bool alive; };
struct regmap_config { int unused; };
static const struct regmap_config regmap_config;
#define __iomem
#define IS_BUILTIN(x) 1
#define IS_MODULE(x) 0
#define NPU_NUM_CORES 8
#define NPU_NUM_IRQ 6
#define GFP_KERNEL 0
#define IRQF_SHARED 1
#define IRQ_HANDLED 1
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define BIT(n) (1u << (n))
#define GENMASK(hi, lo) (((~0u) << (lo)) & ((~0u) >> (31 - (hi))))
#define DMA_BIT_MASK(n) ((1ull << (n)) - 1)
#define FIELD_GET(mask, x) (((x) & (mask)) >> __builtin_ctz(mask))
#define ERR_PTR(x) ((void *)(intptr_t)(x))
#define PTR_ERR(x) ((int)(intptr_t)(x))
#define IS_ERR(x) ((uintptr_t)(x) > UINTPTR_MAX - 4095)
#define dev_info(...) ((void)0)
#include "constants.inc"
#include "types.inc"

enum resource_kind { BASE_RESOURCE, PRIVATE_RESOURCE, MAP_RESOURCE, IRQ_RESOURCE, WORK_RESOURCE, DMA_RESOURCE };
struct managed {
    enum resource_kind kind;
    void *value;
    void (*action)(void *);
};
struct irq_slot { bool active; irqreturn_t (*handler)(int, void *); void *cookie; };
static struct managed resources[64];
static struct irq_slot irqs[9];
static struct regmap map;
static struct airoha_npu_priv *allocation;
static int count, operation, fail_at, policy, wdt_enabled;
static int uninitialized, pending_at_free, dead_access, cancel_with_producer;
static int initialized, queued, canceled, work_ran, requested, freed, assertions;
static bool private_alive;

static void check(bool value)
{
    assert(value);
    assertions++;
}

static bool fail(void) { return ++operation == fail_at; }

static void add(enum resource_kind kind, void *value, void (*action)(void *))
{
    check(count < (int)ARRAY_SIZE(resources));
    resources[count++] = (struct managed){kind, value, action};
}

static void init_work(struct work_struct *work, work_func_t fn)
{
    check(!work->initialized);
    work->fn = fn;
    work->initialized = true;
    initialized++;
}
#define INIT_WORK(w, fn) init_work(w, fn)

static bool schedule_work(struct work_struct *work)
{
    if (!work->initialized) {
        uninitialized++;
        return false;
    }
    if (work->pending)
        return false;
    work->pending = true;
    queued++;
    if (policy == 2) {
        work->pending = false;
        work->fn(work);
        work_ran++;
    } else if (policy == 3 && !work->running) {
        work->pending = false;
        work->running = true;
    }
    return true;
}

static bool cancel_work_sync(struct work_struct *work)
{
    bool pending = work->pending;
    check(work->initialized);
    for (unsigned int i = 1; i < ARRAY_SIZE(irqs); i++)
        if (irqs[i].active && irqs[i].cookie == container_of(work, struct airoha_npu_core, wdt_work))
            cancel_with_producer++;
    if (work->running) {
        /* Model completion of an already-running worker before cancellation returns. */
        work->fn(work);
        work->running = false;
        work_ran++;
    }
    work->pending = false;
    work->cancels++;
    canceled++;
    return pending;
}

static int devm_add_action(struct device *dev, void (*action)(void *), void *data)
{
    if (fail())
        return -ENOMEM;
    add(WORK_RESOURCE, data, action);
    return 0;
}

static void spin_lock_init(spinlock_t *lock) { *lock = 1; }
static int regmap_write(struct regmap *m, u32 reg, u32 val)
{
    if (!m->alive || !private_alive)
        dead_access++;
    return 0;
}
static int regmap_update_bits(struct regmap *m, u32 reg, u32 mask, u32 value)
{
    return regmap_write(m, reg, value);
}
static int regmap_set_bits(struct regmap *m, u32 reg, u32 mask)
{
    return regmap_write(m, reg, mask);
}
static int regmap_read(struct regmap *m, u32 reg, u32 *value)
{
    regmap_write(m, reg, 0);
    *value = wdt_enabled ? WDT_EN_MASK : 0;
    return 0;
}
static int regmap_bulk_read(struct regmap *m, u32 reg, u32 *values, int n)
{
    regmap_write(m, reg, 0);
    memset(values, 0x42, n * sizeof(*values));
    return 0;
}
static void *vzalloc(size_t size) { return calloc(1, size); }
static void dev_coredumpv(struct device *dev, void *dump, size_t size, gfp_t flags) { free(dump); }

static void fire_irqs(void)
{
    for (unsigned int i = 0; i < ARRAY_SIZE(irqs); i++)
        if (irqs[i].active)
            check(irqs[i].handler(i, irqs[i].cookie) == IRQ_HANDLED);
}

static void *devm_platform_ioremap_resource(struct platform_device *pdev, int n)
{
    if (fail())
        return ERR_PTR(-ENOMEM);
    add(BASE_RESOURCE, NULL, NULL);
    return (void *)(uintptr_t)0x1000;
}
static void *devm_kzalloc(struct device *dev, size_t bytes, gfp_t flags)
{
    if (fail())
        return NULL;
    allocation = calloc(1, bytes);
    check(allocation != NULL);
    private_alive = true;
    add(PRIVATE_RESOURCE, allocation, NULL);
    return allocation;
}
static struct regmap *devm_regmap_init_mmio(struct device *dev, void *base, const struct regmap_config *config)
{
    if (fail())
        return ERR_PTR(-ENOMEM);
    map.alive = true;
    add(MAP_RESOURCE, &map, NULL);
    return &map;
}
static int of_reserved_mem_region_to_resource(void *np, int n, struct resource *res)
{
    if (fail())
        return -EINVAL;
    *res = (struct resource){0x84000000, 0x842fffff};
    return 0;
}
static int platform_get_irq(struct platform_device *pdev, int index)
{
    return fail() ? -ENXIO : index;
}
static int devm_request_irq(struct device *dev, int irq, irqreturn_t (*handler)(int, void *),
                            unsigned long flags, const char *name, void *cookie)
{
    if (fail())
        return -EBUSY;
    check(irq >= 0 && irq < (int)ARRAY_SIZE(irqs) && !irqs[irq].active);
    irqs[irq] = (struct irq_slot){true, handler, cookie};
    requested++;
    add(IRQ_RESOURCE, &irqs[irq], NULL);
    if (policy)
        check(handler(irq, cookie) == IRQ_HANDLED);
    return 0;
}
static int dma_set_coherent_mask(struct device *dev, u64 mask) { return fail() ? -EIO : 0; }
static void *dmam_alloc_coherent(struct device *dev, size_t bytes, dma_addr_t *address, gfp_t flags)
{
    if (fail())
        return NULL;
    void *buffer = malloc(bytes);
    check(buffer != NULL);
    *address = 0x82000000 + count * 256;
    add(DMA_RESOURCE, buffer, NULL);
    return buffer;
}
static int model_firmware(void) { return fail() ? -EINVAL : 0; }
static void msleep(int value) { }
static void usleep_range(int low, int high) { }
static void platform_set_drvdata(struct platform_device *pdev, void *data) { pdev->data = data; }
static void *platform_get_drvdata(struct platform_device *pdev) { return pdev->data; }
#include "driver.inc"

static void release_resources(void)
{
    while (count) {
        if (policy)
            fire_irqs();
        struct managed entry = resources[--count];
        switch (entry.kind) {
        case IRQ_RESOURCE: {
            struct irq_slot *irq = entry.value;
            /* free_irq removes this action and joins in-flight handlers. */
            check(irq->active);
            if (policy)
                irq->handler((int)(irq - irqs), irq->cookie);
            irq->active = false;
            freed++;
            break;
        }
        case WORK_RESOURCE:
            entry.action(entry.value);
            break;
        case DMA_RESOURCE:
            free(entry.value);
            break;
        case MAP_RESOURCE:
            map.alive = false;
            break;
        case PRIVATE_RESOURCE:
            for (int i = 0; i < NPU_NUM_CORES; i++)
                pending_at_free += allocation->npu.cores[i].wdt_work.pending ||
                                   allocation->npu.cores[i].wdt_work.running;
            private_alive = false;
            break;
        case BASE_RESOURCE:
            break;
        }
    }
    /* Retain host fixture backing to observe, rather than execute, a UAF. */
    if (allocation) {
        for (int i = 0; i < NPU_NUM_CORES; i++) {
            struct work_struct *work = &allocation->npu.cores[i].wdt_work;
            if (work->pending || work->running) {
                work->fn(work);
                work->pending = work->running = false;
            }
        }
    }
    check(requested == freed);
}

static int scenario(bool corrected, int fault, int delivery, bool enabled, bool probe_only)
{
    struct platform_device pdev = {0};
    memset(resources, 0, sizeof(resources));
    memset(irqs, 0, sizeof(irqs));
    allocation = NULL;
    map.alive = private_alive = false;
    count = operation = 0;
    fail_at = fault;
    policy = delivery;
    wdt_enabled = enabled;
    uninitialized = pending_at_free = dead_access = cancel_with_producer = 0;
    initialized = queued = canceled = work_ran = requested = freed = 0;
    int ret = airoha_npu_probe(&pdev);
    int calls = operation;
    if (fault)
        check(ret < 0 && pdev.data == NULL);
    else
        check(ret == 0 && pdev.data == &allocation->npu);
    if (!ret && !probe_only) {
        fire_irqs();
        model_remove(&pdev);
        /* A still-registered IRQ may queue again after the remove callback. */
        if (policy)
            fire_irqs();
    }
    release_resources();
    int violations = uninitialized + pending_at_free + dead_access + cancel_with_producer;
    if (corrected) {
        assert(violations == 0 && "irq-work-lifetime");
        assertions++;
    }
    if (!enabled)
        check(uninitialized == 0 && queued == 0 && pending_at_free == 0 && dead_access == 0);
    printf("{\"fault\":%d,\"delivery\":%d,\"enabled\":%s,\"probe_only\":%s,\"return\":%d,"
           "\"operations\":%d,\"uninitialized_queue\":%d,\"pending_at_free\":%d,\"dead_access\":%d,"
           "\"cancel_with_live_irq\":%d,\"requested\":%d,\"canceled\":%d,\"executed_work\":%d}",
           fault, delivery, enabled ? "true" : "false", probe_only ? "true" : "false", ret,
           calls, uninitialized, pending_at_free, dead_access, cancel_with_producer, requested, canceled, work_ran);
    free(allocation);
    allocation = NULL;
    return calls;
}

int main(int argc, char **argv)
{
    check(argc == 2);
    bool corrected = !strcmp(argv[1], "after");
    printf("{\"cases\":[");
    int operations = scenario(corrected, 0, 1, true, false);
    for (int delivery = 0; delivery <= 3; delivery++) {
        for (int fault = 1; fault <= operations; fault++) {
            printf(",");
            scenario(corrected, fault, delivery, true, true);
        }
        printf(",");
        scenario(corrected, 0, delivery, false, false);
        printf(",");
        scenario(corrected, 0, delivery, true, true);
    }
    printf("],\"assertions\":%d}\n", assertions);
    return 0;
}
