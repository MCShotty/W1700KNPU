/* Real provider/caller C; coherent DMA, refs, transport and devres are modeled. */
struct mt76_dev {
    struct { struct airoha_npu *npu; unsigned irq_lock; struct { int error; } npu_irq; } mmio;
    struct device *dev, *dma_dev;
    struct mutex mutex;
};
struct mt7996_dev {
    struct mt76_dev mt76;
    dma_addr_t npu_txd_addr[6];
    bool npu_txd_prepared, npu_txd_claimed;
};
static unsigned spin_depth;
#define spin_lock_irqsave(lock, flags) do { (void)(lock); (flags)=0; check(!spin_depth++, "modeled IRQ lock"); } while (0)
#define spin_unlock_irqrestore(lock, flags) do { (void)(lock); (void)(flags); check(spin_depth-- == 1, "modeled IRQ unlock"); } while (0)
static bool family7996 = true;
static unsigned managed_calls, hw_calls;
static int hw_error;
static bool require_blocked_entry;
static bool is_mt7996(struct mt76_dev *dev) { (void)dev; return family7996; }
#define BUILD_BUG_ON(c) _Static_assert(!(c), "array contract")
#define rcu_dereference_protected(p, condition) (p)
static bool mt76_npu_device_active(struct mt76_dev *dev) { return dev->mmio.npu != NULL; }
static void *dmam_alloc_coherent(struct device *dev, size_t bytes, dma_addr_t *addr, int flags)
{
    managed_calls++;
    return dma_alloc_coherent(dev, bytes, addr, flags);
}
static int __mt7996_npu_hw_init(struct mt7996_dev *dev)
{
    check(pthread_mutex_trylock(&dev->mt76.mutex.native) == EBUSY, "host caller owns mutex");
    check(!require_blocked_entry, "stale or consumed prepared lease must not reach hardware entry");
    hw_calls++;
#ifndef BEFORE_HOST
    if (priv.checked_pair) {
        check(life.tx_published && life.tx_attempted && dma_calls == 6 && !managed_calls,
              "retained owner precedes actual initializer");
        for (unsigned i = 0; i < 6; i++)
            check(dev->npu_txd_addr[i] == life.tx_buffers[i].addr && life.tx_buffers[i].buf,
                  "caller handles are actual retained allocations");
    }
#endif
    return hw_error;
}
#include "host-caller.inc"

static const u32 expected_sizes[] = {0x20000,0x20000,0x40000,0x40000,0x40000,0x40000};
static unsigned lifetime_cases;

static void fixture(bool bound)
{
    fresh();
    endpoint_device.unused = dma_device.unused = 1;
    dma_calls = managed_calls = hw_calls = freed_tx = freed_contexts = put_refs = 0;
    object_count = mutation = 0; fail_allocation = 99; mutable_sizes = NULL;
    memset(objects,0,sizeof(objects));
    for (unsigned i = 0; i < 6; i++) addresses[i] = 0x90000000u + i * 0x100000u;
    for (unsigned i = 0; i < 8; i++) {
        life.buffers[i].buf = (void *)(uintptr_t)(i + 1);
        life.buffers[i].addr = 0x83000000u + i * 256;
    }
    priv.npu.ops.wlan_alloc_tx_buffers = airoha_npu_wlan_alloc_tx_buffers_session;
#ifdef HAS_EARLY_TX_PREP
    priv.npu.ops.wlan_validate_tx_buffers = airoha_npu_wlan_validate_tx_buffers_session;
#endif
    family7996 = true; hw_error = 0; require_blocked_entry = false;
    check(!npu_test_run(), "actual initial held session");
    if (bound) {
        check(!npu_test_endpoint(0x20000000,0x100000,2), "actual endpoint binding");
        check(life.endpoint == &endpoint_device && endpoint_device.unused == 2 &&
              life.endpoint_bound && life.bound_serial == priv.wlan_control.client.base.serial,
              "endpoint device reference and serial retained");
    }
}

static void dispose(void)
{
    npu_test_close();
    unsigned old_dma = dma_calls, old_wire = calls;
    airoha_npu_dma_cleanup(&life);
    check(!freed_tx && !freed_contexts && !put_refs && life.exposed,
          "exposed cleanup frees no object or device reference");
    check(airoha_npu_dma_retained(life.dev), "retained lease remains registered");
    check(dma_calls == old_dma && calls == old_wire, "cleanup issues no allocation or wire operation");
    /* Fixture disposal is not a driver retirement/reclamation operation. */
    life.retained.prev->next = life.retained.next;
    life.retained.next->prev = life.retained.prev;
    for (unsigned i = 0; i < object_count; i++) free(objects[i]);
    check(!pthread_mutex_destroy(&priv.wlan_session_lock.native), "fixture session mutex");
    memset(&priv,0,sizeof(priv));
    lifetime_cases++;
}

static void failed_output(int error, unsigned allocated, u32 *sizes)
{
    dma_addr_t out[6], sentinel[6];
    bool was_published = life.tx_published;
    for (unsigned i = 0; i < 6; i++) out[i] = sentinel[i] = UINT64_C(0xabcdef0100000000) + i;
    check(airoha_npu_wlan_alloc_tx_buffers(&priv.npu,&endpoint_device,&dma_device,
          sizes,out,6) == error, "allocation error propagates");
    check(!memcmp(out,sentinel,sizeof(out)) && life.tx_published == was_published,
          "failed operation leaves entire output unchanged");
    check(object_count == allocated && !freed_tx, "partial allocations remain retained");
    unsigned old_dma = dma_calls, old_wire = calls;
    if (priv.wlan_session_error) {
        check(airoha_npu_wlan_alloc_tx_buffers(&priv.npu,&endpoint_device,&dma_device,
              sizes,out,6) == error, "first issued error remains sticky");
        check(old_dma == dma_calls && old_wire == calls && !memcmp(out,sentinel,sizeof(out)),
              "retry has no allocation/wire/output effects");
    }
}

#ifdef HAS_EARLY_TX_PREP
struct prepare_thread {
    struct mt7996_dev *dev;
    int result;
};
static void *prepare_worker(void *argument)
{
    struct prepare_thread *thread = argument;
    thread->result = mt7996_npu_prepare_tx_buffers(thread->dev);
    return NULL;
}

static void early_preparation_cases(void)
{
    for (unsigned mode = 0; mode < 4; mode++) {
        fixture(true);
        struct mt7996_dev dev = {.mt76={.mmio.npu=&priv.npu,.dev=&endpoint_device,.dma_dev=&dma_device}};
        mutex_init(&dev.mt76.mutex);
        if (mode == 1) hw_error = -EIO;
        if (mode == 2) priv.checked_pair = false;
        if (mode == 3) { priv.checked_pair = false; priv.npu.ops.wlan_alloc_tx_buffers = NULL; }
        check(!mt7996_npu_prepare_tx_buffers(&dev), "early TX preparation result");
        if (mode < 2) {
            check(dev.npu_txd_prepared && !dev.npu_txd_claimed && dma_calls == 6 &&
                  !managed_calls && !hw_calls && life.tx_serial == priv.wlan_control.client.base.serial,
                  "early preparation publishes one retained TX lease before hardware");
            unsigned wire = calls;
            check(mt7996_npu_prepare_tx_buffers(&dev) == -EBUSY && calls == wire && dma_calls == 6,
                  "second early preparation cannot allocate or publish again");
        } else {
            check(!dev.npu_txd_prepared && !dma_calls && !managed_calls && !hw_calls,
                  "generic early preparation does not move its managed allocations");
            for (unsigned i=0;i<6;i++) check(!dev.npu_txd_addr[i], "generic early outputs stay zero");
        }
        check(mt7996_npu_hw_init(&dev) == (mode == 1 ? -EIO : 0), "late hardware uses prepared lease");
        check(hw_calls == 1 && dma_calls == 6 && managed_calls == (mode >= 2 ? 6 : 0),
              "prepared path has no second allocation or managed fallback");
        if (mode < 2) {
            require_blocked_entry = true;
            unsigned wire = calls;
            check(dev.npu_txd_claimed && mt7996_npu_hw_init(&dev) == -EBUSY &&
                  hw_calls == 1 && calls == wire && dma_calls == 6,
                  "late hardware attempt consumes the lease even when it fails");
        }
        check(!pthread_mutex_destroy(&dev.mt76.mutex.native), "early fixture mutex");
        dispose();
    }
    for (unsigned failure=0;failure<6;failure++) {
        fixture(true); fail_allocation = failure;
        struct mt7996_dev dev = {.mt76={.mmio.npu=&priv.npu,.dev=&endpoint_device,.dma_dev=&dma_device}};
        mutex_init(&dev.mt76.mutex);
        check(mt7996_npu_prepare_tx_buffers(&dev) == -ENOMEM && object_count == failure &&
              dma_calls == failure + 1 && !dev.npu_txd_prepared && !hw_calls && !managed_calls,
              "early allocation failure retains its whole prefix without hardware entry");
        for (unsigned i=0;i<6;i++) check(!dev.npu_txd_addr[i], "failed early outputs stay zero");
        unsigned wire=calls, allocations=dma_calls;
        check(mt7996_npu_prepare_tx_buffers(&dev) == -ENOMEM && calls == wire && dma_calls == allocations,
              "early failure is sticky and cannot allocate another prefix");
        check(!pthread_mutex_destroy(&dev.mt76.mutex.native), "early failure mutex");
        dispose();
    }
    for (unsigned kind=0;kind<82;kind++) {
        fixture(true);
        struct mt7996_dev dev = {.mt76={.mmio.npu=&priv.npu,.dev=&endpoint_device,.dma_dev=&dma_device}};
        mutex_init(&dev.mt76.mutex);
        check(!mt7996_npu_prepare_tx_buffers(&dev), "prepared mutation baseline");
        if (kind < 6) dev.npu_txd_addr[kind] ^= 0x100;
        else if (kind < 12) life.tx_buffers[kind-6].addr ^= 0x100;
        else if (kind < 18) life.tx_buffers[kind-12].bytes++;
        else if (kind < 24) life.tx_buffers[kind-18].buf = NULL;
        else if (kind == 24) life.boot_identity ^= 1;
        else if (kind == 25) life.nonce_lo ^= 1;
        else if (kind == 26) life.nonce_hi ^= 1;
        else if (kind == 27) life.tx_serial++;
        else if (kind == 28) priv.wlan_control.client.base.serial++;
        else if (kind == 29) life.endpoint = &other_device;
        else if (kind == 30) life.dev = &other_device;
        else if (kind == 31) life.tx_attempted = false;
        else if (kind == 32) life.tx_published = false;
        else if (kind == 33) life.tx_serial = 0;
        else if (kind == 34) priv.wlan_control.descriptor_gets = 1;
        else if (kind == 35) priv.wlan_control.descriptor_arena = 1;
        else if (kind == 36) priv.wlan_control.txbuf_steps = 1;
        else if (kind == 37) priv.wlan_control.rx_event = 1;
        else if (kind == 38) priv.wlan_control.rx_event_steps = 1;
        else if (kind == 39) priv.wlan_control.txbuf_enrolled--;
        else if (kind == 40) life.endpoint_bound = false;
        else if (kind == 41) priv.boot_identity ^= 1;
        else if (kind == 42) priv.native_published = false;
        else if (kind < 51) life.buffers[kind-43].addr = life.tx_buffers[0].addr;
        else if (kind < 57) priv.native_plan[kind-51][0] = life.tx_buffers[0].addr;
        else if (kind == 57) life.rx_event.buf = (void *)(uintptr_t)0x1234;
        else if (kind < 66) life.buffers[kind-58].buf = NULL;
        else if (kind < 74) life.buffers[kind-66].addr = 0;
        else life.buffers[kind-74].addr |= UINT64_C(0x100000000);
        unsigned wire=calls, allocations=dma_calls;
        require_blocked_entry = true;
        check(mt7996_npu_hw_init(&dev) == -EPROTO && !hw_calls && !managed_calls &&
              calls == wire && dma_calls == allocations && !dev.npu_txd_claimed,
              "stale prepared lease rejects before hardware, transport or allocation");
        check(priv.wlan_session_error == -EPROTO && priv.wlan_control.closed && !freed_tx,
              "stale prepared lease retains storage and closes the failed session");
        check(!pthread_mutex_destroy(&dev.mt76.mutex.native), "mutation fixture mutex");
        dispose();
    }
    for (unsigned kind=0;kind<3;kind++) {
        fixture(true);
        struct mt7996_dev dev = {.mt76={.mmio.npu=&priv.npu,.dev=&endpoint_device,.dma_dev=&dma_device}};
        mutex_init(&dev.mt76.mutex);
        check(!mt7996_npu_prepare_tx_buffers(&dev), "interrupted preparation baseline");
        int expected;
        if (!kind) { dev.mt76.mmio.npu=NULL; expected=-ENODEV; }
        else if (kind == 1) { npu_test_close(); expected=-ESHUTDOWN; }
        else { priv.npu.ops.wlan_validate_tx_buffers=NULL; expected=-EOPNOTSUPP; }
        unsigned wire=calls;
        require_blocked_entry = true;
        check(mt7996_npu_hw_init(&dev) == expected && !hw_calls && !managed_calls &&
              calls == wire && dma_calls == 6 && !dev.npu_txd_claimed,
              "missing, closed or unsupported prepared owner never falls back");
        check(!pthread_mutex_destroy(&dev.mt76.mutex.native), "interrupted fixture mutex");
        dispose();
    }
    for (unsigned kind=0;kind<6;kind++) {
        fixture(true);
        struct mt7996_dev dev = {.mt76={.mmio.npu=&priv.npu,.dev=&endpoint_device,.dma_dev=&dma_device}};
        mutex_init(&dev.mt76.mutex); dev.npu_txd_addr[kind]=0x1234;
        unsigned wire=calls;
        check(mt7996_npu_prepare_tx_buffers(&dev) == -EBUSY && !dma_calls && calls == wire &&
              dev.npu_txd_addr[kind] == 0x1234 && !dev.npu_txd_prepared,
              "early preparation cannot overwrite an existing handle");
        check(!pthread_mutex_destroy(&dev.mt76.mutex.native), "existing-handle mutex");
        dispose();
    }
    for (unsigned after=0;after<2;after++)
        for (unsigned kind=0;kind<4;kind++) {
            const int errors[]={-EIO,-EFAULT,-ESHUTDOWN,-ETIMEDOUT};
            fixture(true);
            struct mt7996_dev dev = {.mt76={.mmio.npu=&priv.npu,.dev=&endpoint_device,.dma_dev=&dma_device}};
            mutex_init(&dev.mt76.mutex);
            if (after) check(!mt7996_npu_prepare_tx_buffers(&dev), "IRQ prepared baseline");
            dev.mt76.mmio.npu_irq.error=errors[kind];
            unsigned wire=calls, allocations=dma_calls;
            require_blocked_entry = true;
            check(mt7996_npu_prepare_tx_buffers(&dev) == errors[kind] &&
                  mt7996_npu_hw_init(&dev) == errors[kind] && calls == wire && dma_calls == allocations &&
                  !hw_calls && !managed_calls, "actual sticky IRQ accessor precedes both TX entries");
            check(!pthread_mutex_destroy(&dev.mt76.mutex.native), "IRQ fixture mutex");
            dispose();
        }
    fixture(true);
    struct mt7996_dev dev = {.mt76={.mmio.npu=&priv.npu,.dev=&endpoint_device,.dma_dev=&dma_device}};
    mutex_init(&dev.mt76.mutex);
    struct prepare_thread args[2]={{.dev=&dev},{.dev=&dev}};
    pthread_t threads[2];
    for (unsigned i=0;i<2;i++) check(!pthread_create(&threads[i],NULL,prepare_worker,&args[i]), "prepare thread create");
    for (unsigned i=0;i<2;i++) check(!pthread_join(threads[i],NULL), "prepare thread join");
    check((args[0].result == 0 && args[1].result == -EBUSY) ||
          (args[1].result == 0 && args[0].result == -EBUSY), "one concurrent early preparation wins");
    check(dma_calls == 6 && !managed_calls && !hw_calls && dev.npu_txd_prepared,
          "concurrent preparation retains exactly one six-buffer lease");
    check(!pthread_mutex_destroy(&dev.mt76.mutex.native), "concurrent fixture mutex");
    dispose();
}
#endif

int main(void)
{
    u32 sizes[6];
#ifdef ALIAS_COUNTEREXAMPLE
    fixture(false);
    check(!npu_test_endpoint(0xbf000000,0xd5000,2), "alias counterexample BAR enrollment");
    memcpy(sizes,expected_sizes,sizeof(sizes));addresses[0]=0x3f000000;
    dma_addr_t out[6];
    check(!airoha_npu_wlan_alloc_tx_buffers(&priv.npu,&endpoint_device,&dma_device,sizes,out,6),
          "old validator accepts omitted alias overlap");
    check(out[0]==0x3f000000 && life.tx_published,"overlapping backing address published");
    dispose();
    printf("{\"passed\":false,\"counterexample\":true,\"omitted_cached_alias\":true}\n");
    return 0;
#elif defined(BEFORE_HOST)
    fixture(true);
    struct mt7996_dev dev = {.mt76={.mmio.npu=&priv.npu,.dev=&endpoint_device,.dma_dev=&dma_device}};
    mutex_init(&dev.mt76.mutex); hw_error = -EIO;
    check(mt7996_npu_hw_init(&dev) == -EIO && managed_calls == 6 && !life.tx_attempted,
          "old actual caller bypasses retained TX owner");
    /* Model managed detach, invoking the coherent release contract. */
    for (unsigned i = 0; i < object_count; i++)
        dma_free_coherent(&dma_device,allocated_bytes[i],objects[i],addresses[i]);
    check(freed_tx == 6, "old managed path can release all TX buffers");
    freed_tx = 0; check(!pthread_mutex_destroy(&dev.mt76.mutex.native), "host mutex");
    dispose();
    printf("{\"passed\":false,\"counterexample\":true,\"managed_tx_frees\":6}\n");
    return 0;
#else
    for (unsigned failure = 0; failure < 6; failure++) {
        fixture(true); memcpy(sizes,expected_sizes,sizeof(sizes)); fail_allocation = failure;
        failed_output(-ENOMEM,failure,sizes);
        check(life.tx_attempted && dma_calls == failure + 1, "one-shot failed allocation prefix");
        dispose();
    }
    for (unsigned bar_tag = 0; bar_tag < 3; bar_tag++)
        for (unsigned dma_tag = 0; dma_tag < 3; dma_tag++) {
            fixture(false); memcpy(sizes,expected_sizes,sizeof(sizes));
            check(!npu_test_endpoint(0x3f000000u+bar_tag*0x40000000u,0xd5000,2),
                  "alias-window enrollment");
            addresses[0]=0x3f000000u+dma_tag*0x40000000u;
            failed_output(-EINVAL,1,sizes);dispose();
        }
    fixture(false);
    unsigned wire_before=calls;
    check(npu_test_endpoint(0x7fff0000,0x100000,2)==-EINVAL && calls==wire_before && !life.endpoint,
          "BAR cannot cross alias boundary before enrollment");
    dispose();
    for (unsigned kind=0;kind<11;kind++) {
        fixture(true);memcpy(sizes,expected_sizes,sizeof(sizes));
        dma_addr_t out[6]={0};
        unsigned old_wire=calls;
        int result;
        if(kind==0)result=airoha_npu_wlan_alloc_tx_buffers(&priv.npu,NULL,&dma_device,sizes,out,6);
        else if(kind==1)result=airoha_npu_wlan_alloc_tx_buffers(&priv.npu,&endpoint_device,&other_device,sizes,out,6);
        else if(kind==2)result=airoha_npu_wlan_alloc_tx_buffers(&priv.npu,&endpoint_device,&dma_device,NULL,out,6);
        else if(kind==3)result=airoha_npu_wlan_alloc_tx_buffers(&priv.npu,&endpoint_device,&dma_device,sizes,NULL,6);
        else if(kind==4)result=airoha_npu_wlan_alloc_tx_buffers(&priv.npu,&endpoint_device,&dma_device,sizes,out,5);
        else {sizes[kind-5]++;result=airoha_npu_wlan_alloc_tx_buffers(&priv.npu,&endpoint_device,&dma_device,sizes,out,6);}
        check(result==-EINVAL && !dma_calls && calls==old_wire && !life.tx_attempted && !priv.wlan_session_error,
              "argument preflight does not allocate, publish, poison or issue transport");
        for(unsigned i=0;i<6;i++)check(out[i]==0,"preflight output preserved");
        dispose();
    }
    for (unsigned kind = 0; kind < 17; kind++) {
        fixture(true); memcpy(sizes,expected_sizes,sizeof(sizes));
        unsigned position = 0;
        if (kind == 0) addresses[0] = 0;
        if (kind == 1) addresses[0] = UINT64_C(0x190000000);
        if (kind == 2) addresses[0]++;
        if (kind == 3) addresses[0] = 0xc0000000;
        if (kind == 4) addresses[0] = 0xbfffff00;
        if (kind == 5) addresses[0] = 0x80000000;
        if (kind == 6) addresses[0] = 0x40000000;
        if (kind == 7) addresses[0] = 0x20000000;
        if (kind >= 8 && kind <= 15) addresses[0] = life.buffers[kind - 8].addr ^ 0x80000000;
        if (kind == 16) { addresses[1] = addresses[0] ^ 0x80000000; position = 1; }
        failed_output(-EINVAL,position + 1,sizes);
        dispose();
    }
    for (unsigned kind = 0; kind < 14; kind++) {
        fixture(true); memcpy(sizes,expected_sizes,sizeof(sizes));
        if (kind == 0) life.boot_identity ^= 1;
        if (kind == 1) life.nonce_lo ^= 1;
        if (kind == 2) life.nonce_hi ^= 1;
        if (kind == 3) life.bound_serial++;
        if (kind == 4) priv.wlan_control.descriptor_gets = 1;
        if (kind == 5) priv.wlan_control.descriptor_arena = 0x3e810000;
        if (kind == 6) life.endpoint_bound = false;
        if (kind == 7) life.endpoint = &other_device;
        if (kind == 8) life.dev = &other_device;
        if (kind == 9) life.tx_attempted = true;
        if (kind == 10) life.tx_published = true;
        if (kind == 11) life.tx_buffers[0].addr = 0x90000000;
        if (kind == 12) life.tx_buffers[0].buf = (void *)1;
        if (kind == 13) life.tx_buffers[0].bytes = 0x20000;
        failed_output(kind <= 5 ? -EPROTO : -EBUSY,0,sizes);
        dispose();
    }
    for (unsigned kind = 1; kind <= 11; kind++) {
        if (kind == 6) continue;
        fixture(true); memcpy(sizes,expected_sizes,sizeof(sizes)); mutation = kind;
        failed_output(-EPROTO,6,sizes); dispose();
    }
    for (unsigned late = 0; late < 2; late++) {
        fixture(true); memcpy(sizes,expected_sizes,sizeof(sizes));
        fault_at = calls + 1; fault_error = -EIO; effect_fault = late;
        failed_output(-EIO,6,sizes); dispose();
    }
    for (unsigned slot = 1; slot <= 16; slot++)
        for (unsigned after = 0; after < 2; after++) {
            fixture(true); memcpy(sizes, expected_sizes, sizeof(sizes));
            unsigned before_calls = calls;
            fault_at = before_calls + slot; fault_error = -ETIMEDOUT; effect_fault = after;
            failed_output(-ETIMEDOUT, 6, sizes);
            unsigned prefix = slot <= 1 ? 0 : slot >= 16 ? 14 : slot - 2;
            check(cold.txbuf_enrolled == prefix + (slot >= 2 && slot <= 15 ? after : 0) &&
                  priv.wlan_control.txbuf_enrolled == prefix && calls == before_calls + slot &&
                  life.tx_attempted && !life.tx_published,
                  "lost reply retains exact native/CPU enrollment prefixes and all allocations");
            dispose();
        }
    for (unsigned word=16;word<20;word++) {
        fixture(true);memcpy(sizes,expected_sizes,sizeof(sizes));
        mutate_at=calls+1;mutate_word=word;mutate_value=0xffffffff;
        failed_output(-EPROTO,6,sizes);dispose();
    }
    fixture(true); memcpy(sizes,expected_sizes,sizeof(sizes));
    mutable_sizes = sizes; mutation = 6;
    dma_addr_t out[6];
    unsigned before_calls = calls;
    check(!airoha_npu_wlan_alloc_tx_buffers(&priv.npu,&endpoint_device,&dma_device,sizes,out,6),
          "caller size changes cannot change admitted allocations");
    check(calls == before_calls + 16 && cold.txbuf_enrolled == 14 &&
          priv.wlan_control.txbuf_enrolled == 14,
          "two fresh STATUS calls and all fourteen native records precede output");
    for (unsigned i = 0; i < 6; i++)
        check(allocated_bytes[i] == expected_sizes[i] && out[i] == addresses[i], "immutable allocation sizes");
    unsigned old_dma=dma_calls,old_wire=calls;
    memcpy(sizes,expected_sizes,sizeof(sizes));
    check(airoha_npu_wlan_alloc_tx_buffers(&priv.npu,&endpoint_device,&dma_device,sizes,out,6)==-EBUSY &&
          old_dma==dma_calls && old_wire==calls,"successful owner cannot be overwritten by another attempt");
    dispose();
    for (unsigned mode = 0; mode < 4; mode++) {
        fixture(true);
        struct mt7996_dev dev = {.mt76={.mmio.npu=&priv.npu,.dev=&endpoint_device,.dma_dev=&dma_device}};
        mutex_init(&dev.mt76.mutex);
        if (mode == 1) hw_error = -EIO;
        if (mode == 2) { priv.checked_pair = false; family7996 = false; }
        if (mode == 3) { priv.checked_pair = false; priv.npu.ops.wlan_alloc_tx_buffers = NULL; }
        check(mt7996_npu_hw_init(&dev) == (mode == 1 ? -EIO : 0), "actual host initializer result");
        check(hw_calls == 1 && dma_calls == 6 && managed_calls == (mode >= 2 ? 6 : 0),
              "legacy alone uses managed fallback");
        check(!pthread_mutex_destroy(&dev.mt76.mutex.native), "host mutex destroy");
        dispose();
    }
    fixture(true);
    struct mt7996_dev dev = {.mt76={.mmio.npu=&priv.npu,.dev=&endpoint_device,.dma_dev=&dma_device}};
    mutex_init(&dev.mt76.mutex); fail_allocation = 2;
    check(mt7996_npu_hw_init(&dev) == -ENOMEM && !managed_calls && !hw_calls && object_count == 2,
          "checked allocation failure never falls back or starts hardware initialization");
    check(!pthread_mutex_destroy(&dev.mt76.mutex.native), "failure host mutex"); dispose();
    fixture(true);
    struct mt7996_dev absent={0};mutex_init(&absent.mt76.mutex);
    check(!mt7996_npu_hw_init(&absent) && !dma_calls && !managed_calls && !hw_calls,
          "absent provider performs no allocation or initializer");
    check(!pthread_mutex_destroy(&absent.mt76.mutex.native),"absent host mutex");dispose();
#ifdef HAS_EARLY_TX_PREP
    early_preparation_cases();
#endif
    printf("{\"passed\":true,\"cases\":%u,\"exposed_tx_frees\":0}\n",lifetime_cases);
    return 0;
#endif
}
