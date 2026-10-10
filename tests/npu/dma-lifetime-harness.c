/* Actual lease/exposure/cleanup C; DMA, module/device refs and lists are modeled. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

typedef uint32_t u32;
typedef uint64_t u64;
typedef uint64_t dma_addr_t;
struct device { int refs; };
struct resource { u64 start, end; };
struct list_head { struct list_head *next, *prev; };
struct airoha_npu { struct device *dev; };
#define NPU_NUM_CORES 8
#define NPU_EN7581_7996_PLAN_REGIONS 6
#define AIROHA_NPU_MBOX_SIZE 256
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define THIS_MODULE NULL
#define LIST_HEAD(name) struct list_head name = {&name, &name}
#define DEFINE_MUTEX(name) int name
#define dev_warn(...) ((void)0)
#define list_for_each_entry(pos, head, member) \
    for (struct list_head *node = (head)->next; \
         node != (head) && ((pos) = (void *)((char *)node - offsetof(__typeof__(*(pos)), member)), 1); \
         node = node->next)

static unsigned freed_buffers, freed_contexts, module_pins;
static void mutex_lock(int *mutex) { assert(!*mutex); *mutex = 1; }
static void mutex_unlock(int *mutex) { assert(*mutex); *mutex = 0; }
static void list_add_tail(struct list_head *node, struct list_head *head) {
    node->prev = head->prev; node->next = head;
    head->prev->next = node; head->prev = node;
}
static void __module_get(void *module) { (void)module; module_pins++; }
static void put_device(struct device *device) { assert(device->refs > 0); device->refs--; }
static void kfree(void *p) { freed_contexts++; free(p); }
static void dma_free_coherent(struct device *device, size_t bytes, void *buf, dma_addr_t address) {
    assert(device->refs > 0 && bytes == 256 && address >= 0x83000000);
    freed_buffers++; free(buf);
}
#include "lease.inc"

int main(void)
{
    unsigned cases = 0;
    for (unsigned count = 0; count <= 8; count++) {
        struct device device = {1};
        struct airoha_npu_priv priv = {};
        struct airoha_npu_dma_lifetime *life = calloc(1, sizeof(*life));
        assert(life); life->dev = &device; priv.dma_lifetime = life;
        for (unsigned i = 0; i < count; i++) {
            life->buffers[i].buf = calloc(1, 256);
            life->buffers[i].addr = 0x83000000 + i * 256;
            assert(life->buffers[i].buf);
        }
        unsigned old_free = freed_buffers, old_ctx = freed_contexts, old_pin = module_pins;
        assert(!airoha_npu_dma_retained(&device));
        int exposed = airoha_npu_firmware_expose(&priv);
        if (count < 8) {
            assert(exposed == -EINVAL && !life->exposed && module_pins == old_pin);
            airoha_npu_dma_cleanup(life);
            assert(freed_buffers == old_free + count && freed_contexts == old_ctx + 1 && device.refs == 0);
        } else {
            assert(!exposed && life->exposed && module_pins == old_pin + 1);
            assert(airoha_npu_firmware_expose(&priv) == -EBUSY && module_pins == old_pin + 1);
            airoha_npu_dma_cleanup(life);
            assert(freed_buffers == old_free && freed_contexts == old_ctx && device.refs == 1);
            assert(airoha_npu_retained_dma.next == &life->retained);
            struct device other = {1};
            assert(airoha_npu_dma_retained(&device) && !airoha_npu_dma_retained(&other));
            cases += 2;
            /* Fixture-only retirement after assertions, never a driver free API. */
            life->retained.prev->next = life->retained.next;
            life->retained.next->prev = life->retained.prev;
            for (unsigned i = 0; i < 8; i++) free(life->buffers[i].buf);
            free(life);
            assert(!airoha_npu_dma_retained(&device));
            cases++;
        }
        cases++;
    }
    struct airoha_npu_priv missing = {};
    assert(airoha_npu_firmware_expose(&missing) == -EBUSY);
    cases++;
    printf("{\"passed\":true,\"cases\":%u,\"exposed_frees\":0,\"module_pins\":%u}\n", cases, module_pins);
    return 0;
}
