/* Selected production bodies are generated verbatim; framework boundaries below
 * are a single-threaded model, not a kernel or physical DMA implementation. */
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
typedef uint16_t __le16;
typedef uint32_t u32;
typedef uint32_t __le32;
typedef uint64_t dma_addr_t;
typedef unsigned gfp_t;
typedef unsigned spinlock_t;
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define GENMASK(h, l) ((~0U << (l)) & (~0U >> (31 - (h))))
#define FIELD_PREP(mask, v) (((u32)(v) << __builtin_ctz(mask)) & (mask))
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))
#define cpu_to_le32(v) ((u32)(v))
#define GFP_KERNEL 1U
#define GFP_ATOMIC 2U
#define __GFP_NOWARN 4U
#define DMA_ATTR_NO_WARN 1U
#define WARN_ON(v) assert(!(v))
#define CONFIG_NET_MEDIATEK_SOC_WED 1

struct list_head { struct list_head *next, *prev; };
static void INIT_LIST_HEAD(struct list_head *h) { h->next = h->prev = h; }
static bool list_empty(struct list_head *h) { return h->next == h; }
static void list_add_tail(struct list_head *e, struct list_head *h)
{
    e->prev = h->prev; e->next = h; h->prev->next = e; h->prev = e;
}
static void list_del_init(struct list_head *e)
{
    e->prev->next = e->next; e->next->prev = e->prev; INIT_LIST_HEAD(e);
}
static void list_splice_init(struct list_head *from, struct list_head *to)
{
    assert(list_empty(to));
    if (list_empty(from)) return;
    to->next = from->next; to->prev = from->prev;
    to->next->prev = to; to->prev->next = to; INIT_LIST_HEAD(from);
}
#define LIST_HEAD(name) struct list_head name = { &name, &name }
#define list_first_entry(h, t, m) container_of((h)->next, t, m)
struct work_struct { void (*fn)(struct work_struct *); };
#define INIT_WORK(w, f) ((w)->fn = (f))
static void spin_lock_init(spinlock_t *s) { *s = 0; }
static void spin_lock_bh(spinlock_t *s) { assert(!*s); *s = 1; }
static void spin_unlock_bh(spinlock_t *s) { assert(*s == 1); *s = 0; }

#include "geometry.h"
struct resource_node;
struct device { unsigned id; struct resource_node *head; };
struct airoha_npu {
    struct device *dev;
    struct { int (*wlan_send_msg)(struct airoha_npu *, int,
             enum airoha_npu_wlan_set_cmd, void *, int, gfp_t);
        int (*wlan_rro_open)(struct airoha_npu *,struct device *,struct device *,u32,const dma_addr_t *,unsigned);
        int (*wlan_rro_alloc)(struct airoha_npu *,struct device *,struct device *,u32,u32,u32,void **,dma_addr_t *);
        int (*wlan_rro_publish)(struct airoha_npu *,struct device *,u32);
        int (*wlan_rro_close)(struct airoha_npu *,struct device *);
    } ops;
};
struct airoha_npu_priv { struct airoha_npu npu; bool checked_pair; u32 txbuf_min_size; };
struct mtk_wed_device {
    bool active, rx;
    struct { struct { dma_addr_t addr_elem_phys[128]; } ind_cmd; } wlan;
};
struct mt76_dev {
    struct device *dev, *dma_dev;
    struct { struct airoha_npu *npu; void *ppe_dev; struct mtk_wed_device wed; } mmio;
    struct { unsigned long state; } phy;
    void *hw, *wq;
    unsigned tx_worker, q_rx[__MT_RXQ_MAX];
    int mutex;
    enum mt76_hwrro_mode hwrro_mode;
    bool chip7996, mmio_bus;
    unsigned long wcid_mask[1];
    struct { int idx, hw_key_idx; unsigned tx_info; } global_wcid;
    void *wcid[1];
    unsigned irq_tasklet;
};
struct mt7996_phy { unsigned unused; };
struct mt7996_dev {
    struct mt76_dev mt76;
    struct { unsigned long state; } mphy;
    struct work_struct init_work, dump_work, reset_work, rc_work;
    struct mt7996_phy phy;
    dma_addr_t npu_txd_addr[6];
    bool npu_rro_owned;
#include "rro-member.h"
};

enum { MAX_ALLOCS = 140, MAX_MESSAGES = 256, MAX_EVENTS = 1024 };
enum { EV_MCU_RESET = 1, EV_ITEM_FREE, EV_CANCEL, EV_UNREGISTER,
       EV_DMA_FREE, EV_MCU_EXIT, EV_TOKENS, EV_DMA_CLEANUP, EV_DEVICE_FREE,
       EV_WORKER_TEARDOWN, EV_WORKQUEUE_DESTROY, EV_UNPUBLISH, EV_RCU_JOIN,
       EV_QUEUE_CLEANUP, EV_NPU_PUT, EV_PPE_PUT, EV_RRO_CLOSE };
struct allocation {
    void *ptr; size_t size; dma_addr_t dma; struct device *owner;
    bool live, model_published;
};
struct resource_node {
    struct resource_node *next;
    void (*release)(struct device *, void *);
    unsigned char data[];
};
struct message { u32 selector, words[4]; int result; };
static struct {
    struct mt7996_dev dev;
    struct device endpoint, provider;
    struct airoha_npu_priv priv;
    struct allocation allocations[MAX_ALLOCS];
    struct message messages[MAX_MESSAGES];
    unsigned events[MAX_EVENTS], nevents;
    unsigned attempts, dma_attempts, allocated, freed, live;
    unsigned resources, resource_frees, released_callbacks;
    unsigned nmessages, downstream, cold, lookups, rcu_depth;
    unsigned frame_allocations, fail_frame_allocation;
    unsigned mcu_resets, items_freed, hw_init, dma_rro_init, published_frees;
    unsigned unregister_calls, rcu_joins, queue_cleanups, npu_puts, ppe_puts;
    unsigned worker_teardowns, workqueue_destroys;
    unsigned tx_prepares;
    unsigned rro_opens, rro_closes, rro_publications;
    unsigned fail_devres, fail_dma, disconnect_at_lookup;
    int raw_result, mcu_result, stage, stage_result, rro_open_result, rro_publish_result;
    bool high_dma, tx_prepared, owned_capability;
    FILE *capture;
} s;

static void event(unsigned value)
{
    assert(s.nevents < MAX_EVENTS); s.events[s.nevents++] = value;
}
static bool is_mt7996(struct mt76_dev *d) { return d->chip7996; }
static bool is_mt7992(struct mt76_dev *d) { return !d->chip7996; }
static bool mt76_is_mmio(struct mt76_dev *d) { return d->mmio_bus; }
static bool mtk_wed_device_active(struct mtk_wed_device *d) { return d->active; }
static bool mtk_wed_get_rx_capa(struct mtk_wed_device *d) { return d->rx; }
#define rcu_access_pointer(p) (p)
static void rcu_read_lock(void) { assert(!s.rcu_depth++); }
static void rcu_read_unlock(void) { assert(s.rcu_depth-- == 1); }
static struct airoha_npu *lookup(struct airoha_npu **p)
{
    assert(s.rcu_depth == 1);
    if (++s.lookups == s.disconnect_at_lookup) *p = NULL;
    return *p;
}
#define rcu_dereference(p) lookup(&(p))
#define rcu_assign_pointer(p, v) ((p) = (v))
#include "active.h"

static void *devres_alloc(void (*release)(struct device *, void *), size_t size, gfp_t gfp)
{
    assert(gfp == GFP_KERNEL);
    assert(s.tx_prepared && "TX preparation must precede first RRO allocation");
    if (++s.attempts == s.fail_devres) return NULL;
    struct resource_node *n = calloc(1, sizeof(*n) + size);
    assert(n); n->release = release; s.resources++;
    return n->data;
}
static void devres_free(void *p)
{
    free(container_of(p, struct resource_node, data)); s.resource_frees++;
}
static void devres_add(struct device *d, void *p)
{
    struct resource_node *n = container_of(p, struct resource_node, data);
    n->next = d->head; d->head = n;
}
static int devres_destroy(struct device *d, void (*release)(struct device *, void *),
                          int (*match)(struct device *, void *, void *), void *data)
{
    struct resource_node **link = &d->head;
    while (*link) {
        struct resource_node *n = *link;
        if (n->release == release && match(d, n->data, data)) {
            *link = n->next; devres_free(n->data); return 0;
        }
        link = &n->next;
    }
    return -ENOENT;
}
static dma_addr_t modeled_dma(dma_addr_t *out)
{
    struct mt7996_dev *d = &s.dev;
    for (unsigned i = 0; i < ARRAY_SIZE(d->wed_rro.addr_elem); i++)
        if (out == &d->wed_rro.addr_elem[i].phy_addr)
            return 0x88000000ULL + i * 65536 + (s.high_dma ? 0x100000000ULL : 0);
    if (out == &d->wed_rro.session.phy_addr) return 0x88801000;
    return 0x90000000ULL + s.allocated * 0x10000;
}
static void *dma_alloc_attrs(struct device *d, size_t size, dma_addr_t *out,
                            gfp_t gfp, unsigned long attrs)
{
    assert(d == s.dev.mt76.dma_dev && gfp == GFP_KERNEL && attrs == 0);
    if (++s.dma_attempts == s.fail_dma) return NULL;
    assert(s.allocated < MAX_ALLOCS);
    struct allocation *a = &s.allocations[s.allocated++];
    a->ptr = calloc(1, size); assert(a->ptr);
    a->size = size; a->owner = d; a->dma = *out = modeled_dma(out);
    a->live = true; s.live++;
    return a->ptr;
}
static void dma_free_attrs(struct device *d, size_t size, void *p,
                           dma_addr_t dma, unsigned long attrs)
{
    assert(!s.dev.npu_rro_owned && "owned RRO must not enter managed free");
    assert(!attrs);
    for (unsigned i = 0; i < s.allocated; i++) {
        struct allocation *a = &s.allocations[i];
        if (a->ptr != p) continue;
        assert(a->live && a->owner == d && a->size == size && a->dma == dma);
        s.published_frees += a->model_published;
        a->live = false; s.live--; s.freed++; event(EV_DMA_FREE); free(p); return;
    }
    assert(!"unknown DMA free");
}
#include "managed-dma.h"

static void modeled_device_release(struct device *d)
{
    while (d->head) {
        struct resource_node *n = d->head;
        d->head = n->next; n->release(d, n->data);
        s.released_callbacks++; devres_free(n->data);
    }
}
static int airoha_npu_wlan_cold_command(struct airoha_npu *npu, int cmd,
        enum airoha_npu_wlan_set_cmd api, void *data, int length)
{
    (void)npu; (void)cmd; (void)api; (void)data; (void)length;
    s.cold++; assert(!"RRO selector reached cold dispatcher"); return -EIO;
}
enum { NPU_COLD_TXBUF_STEPS = 6 };
static unsigned npu_cold_txbuf_step(int i) { (void)i; return NPU_COLD_TXBUF_STEPS; }
#define DECLARE_FLEX_ARRAY(t, n) t n[]
#define NPU_OP_SET 1
#define NPU_FUNC_WIFI 0
static void *frame_alloc(size_t size, gfp_t gfp)
{
    assert(gfp == GFP_ATOMIC && size == 24);
    if (++s.frame_allocations == s.fail_frame_allocation) return NULL;
    void *p = calloc(1, size); assert(p); return p;
}
static int airoha_npu_send_msg(struct airoha_npu *npu, int api, void *data, int length)
{
    /* The actual raw framing body calls this modeled mailbox boundary. */
    assert(npu == &s.priv.npu && api == NPU_FUNC_WIFI && length == 24);
    u32 frame[6]; memcpy(frame, data, sizeof(frame));
    unsigned selector = frame[0] & 15;
    assert(frame[0] == (0x10 | selector) && frame[1] == 24);
    assert(selector == 0 || selector == 1 || selector == 3);
    s.downstream++;
    if (s.capture) assert(fwrite(frame, sizeof(frame), 1, s.capture) == 1);
    if (selector != 3) {
        for (unsigned i = 0; i < s.allocated; i++)
            if ((u32)s.allocations[i].dma == frame[3]) s.allocations[i].model_published = true;
    }
    return s.raw_result;
}
#define kzalloc frame_alloc
#define kfree free
#include "raw-framing.h"
#undef kfree
#undef kzalloc
#include "provider.h"
#include "sender.h"
static int observe_send(struct mt76_dev *d, int selector, u32 a, u32 b, u32 c, u32 e)
{
    assert(s.nmessages < MAX_MESSAGES);
    struct message *m = &s.messages[s.nmessages++];
    m->selector = selector; m->words[0] = a; m->words[1] = b;
    m->words[2] = c; m->words[3] = e;
    return m->result = mt76_npu_send_txrx_addr(d, selector, a, b, c, e);
}

/* Unselected chip/framework APIs are observable boundaries, not no-op proof
 * of quiescence. Lower mt76 unregister/free/NPU detach bodies run verbatim;
 * mac80211,worker,queue-cleanup,MCU and DMA internals remain modeled. */
#define MT_INT_SOURCE_CSR 0
#define MT_BAND0 0
#define MT_BAND1 1
#define MT_AFE_CTL_BAND_PLL_03(b) (b)
#define MT_AFE_CTL_BAND_PLL_03_MSB_EN 1
#define MT7996_WTBL_STA 1
#define MT_WCID_TX_INFO_SET 1
static void mt76_wr(struct mt7996_dev *d, unsigned r, unsigned v) { (void)d; (void)r; (void)v; }
static void mt76_rmw(struct mt7996_dev *d, unsigned r, unsigned m, unsigned v)
{ (void)d; (void)r; (void)m; (void)v; }
static void set_bit(unsigned b, unsigned long *p) { *p |= 1UL << b; }
static void mt7996_init_work(struct work_struct *w) { (void)w; }
static int stage_result(int stage) { return s.stage == stage ? s.stage_result : 0; }
static int mt7996_variant_type_init(struct mt7996_dev *d) { (void)d; return stage_result(1); }
static int mt7996_dma_init(struct mt7996_dev *d) { (void)d; return stage_result(2); }
static int mt7996_mcu_init(struct mt7996_dev *d) { (void)d; return stage_result(3); }
static int mt7996_npu_prepare_tx_buffers(struct mt7996_dev *d)
{
    assert(d == &s.dev && !s.allocated && !s.nmessages);
    s.tx_prepares++;
    int result = stage_result(8);
    if (!result) {
        s.tx_prepared = true;
        for(unsigned i=0;i<6;i++)d->npu_txd_addr[i]=0x96000000+i*0x100000;
    }
    return result;
}
static void mt7996_rro_hw_init(struct mt7996_dev *d) { (void)d; s.hw_init++; }
static int mt7996_dma_rro_init(struct mt7996_dev *d) { (void)d; s.dma_rro_init++; return stage_result(4); }
static int mt7996_variant_fem_init(struct mt7996_dev *d) { (void)d; return stage_result(5); }
static int mt7996_eeprom_init(struct mt7996_dev *d) { (void)d; return stage_result(6); }
static int mt76_wcid_alloc(unsigned long *mask, int max) { (void)mask; (void)max; return stage_result(7); }
static int mt7996_mcu_wed_rro_reset_sessions(struct mt7996_dev *d, u16 id)
{ (void)d; (void)id; s.mcu_resets++; event(EV_MCU_RESET); return s.mcu_result; }
static void kfree(void *p) { s.items_freed++; event(EV_ITEM_FREE); free(p); }
static void cancel_work_sync(struct work_struct *w) { (void)w; event(EV_CANCEL); }
static struct mt7996_phy *mt7996_phy3(struct mt7996_dev *d) { return &d->phy; }
static struct mt7996_phy *mt7996_phy2(struct mt7996_dev *d) { return &d->phy; }
static void mt7996_unregister_phy(struct mt7996_phy *p) { (void)p; }
static void mt7996_unregister_thermal(struct mt7996_phy *p) { (void)p; }
static void mt7996_coredump_unregister(struct mt7996_dev *d) { (void)d; }
static void mt7996_mcu_exit(struct mt7996_dev *d) { (void)d; event(EV_MCU_EXIT); }
static void mt7996_tx_token_put(struct mt7996_dev *d) { (void)d; event(EV_TOKENS); }
static void mt7996_dma_cleanup(struct mt7996_dev *d) { (void)d; event(EV_DMA_CLEANUP); }
static void mt7996_rro_msdu_page_map_free(struct mt7996_dev *d) { (void)d; }
static void tasklet_disable(unsigned *t) { (void)t; }
struct airoha_ppe_dev;
#define CONFIG_MT76_LEDS 0
#define IS_ENABLED(v) (v)
static bool test_bit(unsigned bit, const unsigned long *word) { return !!(*word & (1UL << bit)); }
static void mt76_led_cleanup(void *p) { (void)p; }
static void mt76_tx_status_check(struct mt76_dev *d, bool flush) { assert(d == &s.dev.mt76 && flush); }
static void mt76_wcid_cleanup(struct mt76_dev *d, void *wcid) { assert(wcid == &d->global_wcid); }
static void ieee80211_unregister_hw(void *hw)
{ assert(hw == &s.endpoint); s.unregister_calls++; event(EV_UNREGISTER); }
static void mt76_worker_teardown(unsigned *worker)
{ assert(worker == &s.dev.mt76.tx_worker); s.worker_teardowns++; event(EV_WORKER_TEARDOWN); }
static void destroy_workqueue(void *wq)
{ assert(wq == &s); s.workqueue_destroys++; event(EV_WORKQUEUE_DESTROY); }
static void mutex_lock(int *lock) { assert(!*lock); *lock = 1; }
static void mutex_unlock(int *lock) { assert(*lock == 1); *lock = 0; }
#define lockdep_is_held(lock) (*(lock) == 1)
#define rcu_replace_pointer(pointer, value, held) ({ \
    assert(held); __auto_type old = (pointer); (pointer) = (value); event(EV_UNPUBLISH); old; })
static void synchronize_rcu(void)
{
    assert(s.dev.mt76.mutex == 1 && !s.rcu_depth &&
           !s.dev.mt76.mmio.npu && !s.dev.mt76.mmio.ppe_dev);
    s.rcu_joins++; event(EV_RCU_JOIN);
}
static void mt76_npu_queue_cleanup(struct mt76_dev *d, unsigned *queue)
{
    assert(d == &s.dev.mt76 && !d->mutex && !d->mmio.npu && !d->mmio.ppe_dev);
    assert(queue == &d->q_rx[MT_RXQ_NPU0] || queue == &d->q_rx[MT_RXQ_NPU1]);
    s.queue_cleanups++; event(EV_QUEUE_CLEANUP);
}
static void airoha_npu_put(struct airoha_npu *npu)
{ assert(npu == &s.priv.npu); s.npu_puts++; event(EV_NPU_PUT); }
static void airoha_ppe_put_dev(struct airoha_ppe_dev *ppe)
{ assert((void *)ppe == &s.provider); s.ppe_puts++; event(EV_PPE_PUT); }
static void ieee80211_free_hw(void *hw)
{ assert(hw == &s.endpoint && !s.dev.mt76.mutex); event(EV_DEVICE_FREE); }
#define rcu_dereference_protected(p,c) (assert(c),(p))
static int model_rro_open(struct airoha_npu *npu,struct device *endpoint,struct device *dma,
                          u32 profile,const dma_addr_t *tx,unsigned count)
{
    assert(npu==&s.priv.npu && endpoint==&s.endpoint && dma==&s.provider && s.dev.mt76.mutex);
    if(!s.owned_capability)return -EOPNOTSUPP;
    assert(s.tx_prepared && count==6 && profile<3 && "TX preparation must precede first RRO allocation");
    for(unsigned i=0;i<6;i++)assert(tx[i]==0x96000000+i*0x100000);
    s.rro_opens++;
    return s.rro_open_result;
}
static int model_rro_alloc(struct airoha_npu *npu,struct device *endpoint,struct device *dma,
                           u32 role,u32 index,u32 bytes,void **buf,dma_addr_t *addr)
{
    assert(npu==&s.priv.npu && endpoint==&s.endpoint && dma==&s.provider && s.dev.mt76.mutex);
    assert(s.owned_capability && s.dev.npu_rro_owned && role<=MT76_NPU_RRO_SESSION && index<128);
    void *allocated=dma_alloc_attrs(dma,bytes,addr,GFP_KERNEL,0);
    if(!allocated)return -ENOMEM;
    *buf=allocated;
    return 0;
}
static int model_rro_publish(struct airoha_npu *npu,struct device *endpoint,u32 ordinal)
{
    assert(npu==&s.priv.npu && endpoint==&s.endpoint && s.dev.mt76.mutex && ordinal<=128);
    assert(s.owned_capability && s.dev.npu_rro_owned && s.rro_publish_result);
    struct mt7996_wed_rro_addr *addr=ordinal<128?s.dev.wed_rro.addr_elem[ordinal].ptr:s.dev.wed_rro.session.ptr;
    assert(addr && !addr[0].head_low && addr[0].data==0xff000000);
    s.rro_publications++;
    return s.rro_publish_result;
}
static int model_rro_close(struct airoha_npu *npu,struct device *endpoint)
{
    assert(npu==&s.priv.npu && endpoint==&s.endpoint && s.dev.mt76.mutex);
    s.rro_closes++;event(EV_RRO_CLOSE);
    return s.owned_capability?0:-EOPNOTSUPP;
}
#include "rro-bridges.h"
#include "teardown.h"
#define mt76_npu_send_txrx_addr observe_send
/* The independent reset owner executes in its separate actual-C suite.
 * These selected full callers model that additional ownership boundary. */
static int mt7996_npu_rro_reset_init(struct mt7996_dev *dev)
{
	(void)dev;
	return 0;
}
static void mt7996_npu_rro_reset_close(struct mt7996_dev *dev) { (void)dev; }
static void mt7996_npu_rro_reset_join(struct mt7996_dev *dev) { (void)dev; }
static void mt7996_npu_rro_reset_work(struct mt7996_dev *dev) { (void)dev; }

#include "callers.h"
#undef mt76_npu_send_txrx_addr

static unsigned cases;
static void setup(int profile, bool checked, bool npu)
{
    assert(!s.live && !s.provider.head && !s.endpoint.head);
    memset(&s, 0, sizeof(s));
    s.provider.id = 1; s.endpoint.id = 2;
    s.priv.checked_pair = checked; s.priv.npu.dev = &s.provider;
    s.priv.txbuf_min_size = NPU_EN7581_7996_TX_CHECK_SIZE;
    s.priv.npu.ops.wlan_send_msg = airoha_npu_wlan_msg_send_session;
    s.priv.npu.ops.wlan_rro_open=model_rro_open;
    s.priv.npu.ops.wlan_rro_alloc=model_rro_alloc;
    s.priv.npu.ops.wlan_rro_publish=model_rro_publish;
    s.priv.npu.ops.wlan_rro_close=model_rro_close;
    s.dev.mt76.dev = &s.endpoint; s.dev.mt76.dma_dev = npu ? &s.provider : &s.endpoint;
    s.dev.mt76.mmio.npu = npu ? &s.priv.npu : NULL;
    s.dev.mt76.mmio.ppe_dev = npu ? &s.provider : NULL;
    s.dev.mt76.hw = &s.endpoint; s.dev.mt76.wq = &s;
    s.dev.mt76.mmio_bus = true; s.dev.mt76.chip7996 = true;
    s.dev.mt76.hwrro_mode = profile == 0 ? MT76_HWRRO_V3 : MT76_HWRRO_V3_1;
    s.dev.mt76.mmio.wed.active = profile == 2;
    s.dev.mt76.mmio.wed.rx = true;
    INIT_LIST_HEAD(&s.dev.wed_rro.poll_list);
}
static unsigned allocations_for(int profile) { return profile == 2 ? 137 : 139; }
static void geometry_check(void)
{
    assert(MT7996_RRO_ADDR_ELEM_LEN == 128 && MT7996_RRO_WINDOW_MAX_SIZE == 8192);
    assert(sizeof(struct mt7996_wed_rro_addr) == 8 && MT7996_RRO_MAX_SESSION == 1024);
    assert(MT7996_RRO_WINDOW_MAX_LEN == 1024 && sizeof(struct mt7996_rro_queue_regs_emi) == 16);
}
static void check_initialized(unsigned expected_messages)
{
    assert(s.nmessages == expected_messages);
    for (unsigned i = 0; i < 128; i++) {
        struct mt7996_wed_rro_addr *a = s.dev.wed_rro.addr_elem[i].ptr;
        assert(a);
        for (unsigned j = 0; j < 8192; j++) assert(!a[j].head_low && a[j].data == 0xff000000);
        if (expected_messages) {
            struct message *m = &s.messages[i];
            assert(m->selector == 0 && m->words[0] == i && !m->words[2] && !m->words[3]);
            assert(m->words[1] == (u32)s.dev.wed_rro.addr_elem[i].phy_addr);
        }
        if (s.dev.mt76.mmio.wed.active)
            assert(s.dev.mt76.mmio.wed.wlan.ind_cmd.addr_elem_phys[i] == s.dev.wed_rro.addr_elem[i].phy_addr);
    }
    if (expected_messages) assert(s.messages[128].selector == 1 && s.messages[128].words[0] == 0);
}
static void finish(const char *kind, int profile, int result, unsigned failure)
{
    unsigned prefix = s.live;
    modeled_device_release(&s.endpoint);
    unsigned after_endpoint = s.live;
    if (s.dev.mt76.dma_dev == &s.provider) assert(after_endpoint == prefix);
    else assert(!after_endpoint);
    modeled_device_release(&s.provider);
    assert(!s.live && s.allocated == s.freed && s.resources == s.resource_frees && !s.rcu_depth);
    printf("{\"kind\":\"%s\",\"profile\":%d,\"result\":%d,\"failure\":%u,"
           "\"allocations\":%u,\"before_endpoint_cleanup\":%u,\"after_endpoint_cleanup\":%u,"
           "\"managed_release_callbacks\":%u,\"messages\":%u,\"downstream\":%u,"
           "\"model_published_frees\":%u,\"MCU_resets\":%u,\"items_freed\":%u,"
           "\"unregister_calls\":%u,\"worker_teardowns\":%u,\"workqueue_destroys\":%u,"
           "\"RCU_joins\":%u,\"queue_cleanups\":%u,\"NPU_puts\":%u,\"PPE_puts\":%u}\n",
           kind, profile, result, failure, s.allocated, prefix, after_endpoint,
           s.released_callbacks, s.nmessages, s.downstream, s.published_frees, s.mcu_resets, s.items_freed,
           s.unregister_calls, s.worker_teardowns, s.workqueue_destroys, s.rcu_joins,
           s.queue_cleanups, s.npu_puts, s.ppe_puts);
    cases++;
}
static void queue_ids(const u16 *ids, unsigned count)
{
    for (unsigned i = 0; i < count; i++) {
        struct mt7996_wed_rro_session_id *e = calloc(1, sizeof(*e)); assert(e);
        e->id = ids[i]; INIT_LIST_HEAD(&e->list); list_add_tail(&e->list, &s.dev.wed_rro.poll_list);
    }
}
static unsigned first_event(unsigned value)
{
    for (unsigned i = 0; i < s.nevents; i++) if (s.events[i] == value) return i;
    assert(!"missing event"); return 0;
}
static void finish_owned(const char *kind,int profile,int result,unsigned mask)
{
    unsigned retained=s.live;
    modeled_device_release(&s.endpoint);modeled_device_release(&s.provider);
    assert(s.live==retained && !s.freed && !s.resources && !s.resource_frees &&
           !s.released_callbacks && !s.hw_init && !s.dma_rro_init && !s.nmessages && !s.downstream);
    printf("{\"kind\":\"%s\",\"profile\":%d,\"result\":%d,\"mask\":%u,"
           "\"retained_allocations\":%u,\"managed_allocations\":%u,\"production_frees\":%u,"
           "\"handoff_calls\":%u,\"publication_attempts\":%u,\"provider_callbacks_modeled\":true}\n",
           kind,profile,result,mask,retained,s.resources,s.freed,s.rro_closes,s.rro_publications);
    /* Fixture-only disposal is not provider retirement authority. */
    for(unsigned i=0;i<s.allocated;i++)free(s.allocations[i].ptr);
    s.live=0;cases++;
}
int main(int argc, char **argv)
{
    assert(argc == 2 && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__);
    geometry_check();
    for (int profile = 0; profile < 3; profile++) {
        unsigned count = allocations_for(profile);
        for (unsigned failure = 1; failure <= count; failure++) {
            for (unsigned backend = 0; backend < 2; backend++) {
                setup(profile, true, true);
                if (backend) s.fail_dma = failure; else s.fail_devres = failure;
                int result = mt7996_init_hardware(&s.dev);
                assert(result == -ENOMEM && s.allocated == failure - 1 && !s.hw_init && !s.dma_rro_init);
                assert(s.downstream == 0 && s.cold == 0);
                for (unsigned i = 0; i < s.nmessages; i++) assert(s.messages[i].result == -EINVAL);
                finish(backend ? "dma-allocation-failure" : "devres-allocation-failure", profile, result, failure);
            }
        }
        for (int stage = 1; stage <= 8; stage++) {
            setup(profile, true, true); s.stage = stage; s.stage_result = stage == 7 ? 1 : -EIO;
            int result = mt7996_init_hardware(&s.dev);
            assert(result == (stage == 7 ? -ENOSPC : -EIO));
            assert(s.allocated == (stage < 4 || stage == 8 ? 0 : count) && !s.downstream);
            if (stage == 8) assert(s.tx_prepares == 1 && !s.tx_prepared && !s.nmessages);
            finish("higher-startup-failure", profile, result, stage);
        }
        const int statuses[] = { 0, -EIO, -ETIMEDOUT, EIO };
        for (unsigned checked = 0; checked < 2; checked++) {
            for (unsigned j = 0; j < ARRAY_SIZE(statuses); j++) {
                setup(profile, checked, true); s.raw_result = statuses[j];
                int result = mt7996_init_hardware(&s.dev);
                assert(!result && s.allocated == count && s.hw_init == 1 && s.dma_rro_init == 1);
                check_initialized(129);
                for (unsigned i = 0; i < s.nmessages; i++)
                    assert(s.messages[i].result == (checked ? -EINVAL : statuses[j]));
                assert(s.downstream == (checked ? 0 : 129));
                set_bit(MT76_STATE_REGISTERED, &s.dev.mt76.phy.state);
                mt7996_unregister_device(&s.dev);
                assert(!s.live && !s.provider.head && !s.released_callbacks);
                assert(!s.dev.mt76.mmio.npu && !s.dev.mt76.mmio.ppe_dev &&
                       "provider pointers must be unpublished");
                assert(s.rcu_joins == 1 && "provider detach must join prior RCU readers");
                assert(s.npu_puts == 1 && "NPU detach must release borrowed reference");
                assert(s.rro_closes==1 && first_event(EV_RRO_CLOSE)<first_event(EV_UNPUBLISH) &&
                       "lower detach must hand off RRO before unpublishing provider");
                assert(first_event(EV_UNREGISTER) < first_event(EV_DMA_FREE));
                assert(first_event(EV_DMA_FREE) < first_event(EV_MCU_EXIT));
                assert(first_event(EV_MCU_EXIT) < first_event(EV_DMA_CLEANUP));
                assert(first_event(EV_DMA_CLEANUP) < first_event(EV_WORKER_TEARDOWN));
                assert(first_event(EV_WORKER_TEARDOWN) < first_event(EV_WORKQUEUE_DESTROY));
                assert(first_event(EV_WORKQUEUE_DESTROY) < first_event(EV_UNPUBLISH));
                assert(first_event(EV_UNPUBLISH) < first_event(EV_RCU_JOIN));
                assert(first_event(EV_RCU_JOIN) < first_event(EV_QUEUE_CLEANUP));
                assert(first_event(EV_QUEUE_CLEANUP) < first_event(EV_NPU_PUT));
                assert(first_event(EV_NPU_PUT) < first_event(EV_PPE_PUT));
                assert(first_event(EV_PPE_PUT) < first_event(EV_DEVICE_FREE));
                assert(s.rcu_joins == 1 && s.npu_puts == 1 && s.ppe_puts == 1 && s.queue_cleanups == 2);
                finish(checked ? "checked-denial-ignored" : "raw-result-ignored", profile, result, j);
            }
        }
        setup(profile, true, false);
        assert(!mt7996_init_hardware(&s.dev)); check_initialized(0);
        finish("endpoint-owned-without-NPU", profile, 0, 0);
    }
    for (unsigned mask = 0; mask < 16; mask++) {
        bool npu = mask & 1, ppe = mask & 2, registered = mask & 4, workqueue = mask & 8;
        setup(0, true, npu);
        assert(!mt7996_init_hardware(&s.dev));
        s.dev.mt76.mmio.ppe_dev = ppe ? &s.provider : NULL;
        s.dev.mt76.phy.state = registered ? 1UL << MT76_STATE_REGISTERED : 0;
        s.dev.mt76.wq = workqueue ? &s : NULL;
        mt7996_unregister_device(&s.dev);
        assert(!s.live && !s.dev.mt76.mmio.npu && !s.dev.mt76.mmio.ppe_dev && !s.dev.mt76.wq);
        assert(s.unregister_calls == registered && s.worker_teardowns == 1 && s.workqueue_destroys == workqueue);
        assert(s.rcu_joins == (npu || ppe) && s.npu_puts == npu && s.ppe_puts == ppe && s.queue_cleanups == 2);
        assert(first_event(EV_DMA_FREE) < first_event(EV_UNPUBLISH));
        assert(first_event(EV_UNPUBLISH) < first_event(EV_QUEUE_CLEANUP));
        assert(first_event(EV_QUEUE_CLEANUP) < first_event(EV_DEVICE_FREE));
        finish("complete-mt76-detach-reference-and-registration-boundaries", 0, 0, mask);
    }
    const u16 ids[] = { 0, 7, 8, 1023, 1024, 1025, 65535 };
    const int statuses[] = { 0, -EIO, -ETIMEDOUT };
    for (unsigned mode = 0; mode < 3; mode++) {
        for (unsigned n = 0; n < ARRAY_SIZE(statuses); n++) {
            setup(0, mode == 1, mode != 0);
            assert(!mt7996_init_hardware(&s.dev));
            s.nmessages = s.downstream = 0;
            s.raw_result = s.mcu_result = statuses[n];
            /* Distinct input bytes show the CPU-only branch really touches its
             * exact session, rather than merely revisiting existing signatures. */
            for (unsigned i = 0; i < 128; i++) memset(s.dev.wed_rro.addr_elem[i].ptr, 0x35, 65536);
            memset(s.dev.wed_rro.session.ptr, 0x35, 8192);
            queue_ids(ids, ARRAY_SIZE(ids)); mt7996_wed_rro_work(&s.dev.wed_rro.work);
            assert(list_empty(&s.dev.wed_rro.poll_list) && s.items_freed == 7);
            assert(s.mcu_resets == (mode == 0 ? 5 : 7));
            assert(s.nmessages == (mode == 0 ? 0 : 7));
            for (unsigned i = 0; i < s.nmessages; i++) {
                assert(s.messages[i].selector == 3 && s.messages[i].words[0] == ids[i]);
                assert(s.messages[i].result == (mode == 1 ? -EINVAL : statuses[n]));
            }
            for (unsigned block = 0; block < 128; block++) {
                struct mt7996_wed_rro_addr *a = s.dev.wed_rro.addr_elem[block].ptr;
                for (unsigned j = 0; j < 8192; j++) {
                    unsigned id = block * 8 + j / 1024;
                    bool reset = mode == 0 && (id == 0 || id == 7 || id == 8 || id == 1023);
                    assert(a[j].head_low == 0x35353535 && a[j].data == (reset ? 0xff353535 : 0x35353535));
                }
            }
            struct mt7996_wed_rro_addr *a = s.dev.wed_rro.session.ptr;
            for (unsigned j = 0; j < 1024; j++)
                assert(a[j].head_low == 0x35353535 && a[j].data == (mode == 0 ? 0xff353535 : 0x35353535));
            finish("worker-errors-and-injected-ID-boundaries", mode, statuses[n], 0);
        }
    }
    for (unsigned failure = 1; failure <= 129; failure++) {
        setup(0, false, true); s.fail_frame_allocation = failure;
        assert(!mt7996_init_hardware(&s.dev)); check_initialized(129);
        assert(s.allocated == 139 && s.downstream == 128 && s.frame_allocations == 129);
        for (unsigned i = 0; i < s.nmessages; i++)
            assert(s.messages[i].result == (i + 1 == failure ? -ENOMEM : 0));
        finish("raw-framing-allocation-failure-ignored", 0, 0, failure);
    }
    setup(0, true, true); s.disconnect_at_lookup = 1;
    assert(!mt7996_init_hardware(&s.dev));
    assert(s.nmessages == 1 && s.messages[0].result == -ENODEV && !s.downstream);
    finish("disconnect-between-active-and-lookup", 0, 0, 0);
    setup(0, false, true); s.high_dma = true;
    assert(!mt7996_init_hardware(&s.dev)); check_initialized(129);
    assert(s.dev.wed_rro.addr_elem[0].phy_addr == 0x188000000ULL && s.messages[0].words[1] == 0x88000000);
    finish("injected-64-bit-DMA-narrows-to-u32", 0, 0, 0);
    setup(0, true, true); s.dev.mt76.hwrro_mode = MT76_HWRRO_OFF;
    assert(!mt7996_init_hardware(&s.dev) && !s.allocated && !s.nmessages);
    finish("RRO-off", 0, 0, 0);
    setup(0, true, true); s.dev.mt76.chip7996 = false;
    assert(!mt7996_init_hardware(&s.dev) && !s.nmessages);
    queue_ids(ids, ARRAY_SIZE(ids)); mt7996_wed_rro_work(&s.dev.wed_rro.work);
    assert(!s.nmessages && s.mcu_resets == 7 && s.items_freed == 7);
    finish("non-7996-active-NPU-worker", 0, 0, 0);
    setup(0, false, true); s.capture = fopen(argv[1], "wbx"); assert(s.capture);
    assert(!mt7996_init_hardware(&s.dev)); check_initialized(129);
    queue_ids(ids, 5); mt7996_wed_rro_work(&s.dev.wed_rro.work);
    assert(s.downstream == 134 && s.nmessages == 134 && s.items_freed == 5);
    assert(!fclose(s.capture)); s.capture = NULL;
    finish("captured-full-caller-sequence", 0, 0, 0);
    const int owned_errors[]={-EINVAL,-EIO,-ETIMEDOUT};
    for(int profile=0;profile<3;profile++){
        unsigned prefix=profile==0?3:1;
        for(unsigned error=0;error<ARRAY_SIZE(owned_errors);error++){
            for(unsigned mask=0;mask<4;mask++){
                setup(profile,true,true);s.owned_capability=true;s.rro_publish_result=owned_errors[error];
                int result=mt7996_init_hardware(&s.dev);
                assert(result==owned_errors[error] && s.dev.npu_rro_owned && s.allocated==prefix &&
                       s.rro_publications==1 && !s.hw_init && !s.dma_rro_init &&
                       "owned publication error stops higher init before hardware setup");
                if(mask&1)s.dev.mt76.hwrro_mode=MT76_HWRRO_OFF;
                if(mask&2)s.dev.mt76.mmio.npu=NULL;
                mt7996_unregister_device(&s.dev);
                assert(s.dev.npu_rro_owned && !s.freed && s.live==prefix);
                assert(s.rro_closes==((mask&2)?0:2) &&
                       "lower detach must hand off RRO before unpublishing provider");
                if(!(mask&2))assert(first_event(EV_RRO_CLOSE)<first_event(EV_MCU_EXIT) &&
                                    first_event(EV_RRO_CLOSE)<first_event(EV_UNPUBLISH));
                finish_owned("owned-publication-error-retained",profile,result,mask);
            }
        }
        for(unsigned failure=1;failure<=prefix;failure++){
            setup(profile,true,true);s.owned_capability=true;s.rro_publish_result=-EINVAL;s.fail_dma=failure;
            int result=mt7996_init_hardware(&s.dev);
            assert(result==-ENOMEM && s.dev.npu_rro_owned && s.live==failure-1 && !s.rro_publications);
            mt7996_unregister_device(&s.dev);
            finish_owned("owned-allocation-prefix-retained",profile,result,failure);
        }
        for(unsigned error=0;error<ARRAY_SIZE(owned_errors);error++){
            setup(profile,true,true);s.owned_capability=true;s.rro_open_result=owned_errors[error];
            int result=mt7996_init_hardware(&s.dev);
            assert(result==owned_errors[error] && !s.dev.npu_rro_owned && !s.dma_attempts && !s.attempts &&
                   !s.rro_publications && "owned open error must not fall back to managed allocation");
            mt7996_unregister_device(&s.dev);
            finish_owned("owned-open-error-no-fallback",profile,result,error);
        }
    }
    fprintf(stderr, "RRO_LIFETIME_CHARACTERIZATION cases=%u target_qualified=0 hardware=0\n", cases);
    return 0;
}
