/* Actual allocation paths above; teardown frees here are fixture-only. */
static unsigned rx_cases;

static void rx_late_mutate(void)
{
    if (!late_mutation || dma_calls < mutate_after || (mutate_on_call && calls < mutate_on_call))
        return;
    unsigned kind = late_mutation;
    late_mutation = 0;
    if (kind == 1) life.rx_event.addr += 0x10000;
    if (kind == 2) life.rx_event.buf = (void *)(uintptr_t)0x1234;
    if (kind == 3) life.rx_event.bytes += 16;
    if (kind == 4) life.rx_serial++;
    if (kind == 5) life.rx_published = !life.rx_published;
    if (kind == 6) life.rx_attempted = !life.rx_attempted;
    if (kind == 7) priv.native_plan[2][0] += 0x10000;
    if (kind == 8) priv.boot_identity++;
    if (kind == 9) life.boot_identity++;
    if (kind == 10) life.nonce_lo++;
    if (kind == 11) life.nonce_hi++;
    if (kind == 12) life.endpoint = &other_device;
    if (kind == 13) life.endpoint_base += 0x100000;
    if (kind == 14) life.endpoint_bytes += 4096;
    if (kind == 15) life.bound_serial++;
    if (kind == 16) life.buffers[3].buf = (void *)(uintptr_t)0x4321;
    if (kind == 17) life.buffers[3].addr += 256;
    if (kind == 18) priv.native_published = false;
    if (kind == 19) priv.npu.dev = &other_device;
    if (kind == 20) life.dev = &other_device;
    if (kind == 21) life.tx_attempted = true;
    if (kind == 22) life.tx_published = true;
    if (kind == 23) priv.wlan_control.txbuf_steps++;
    if (kind == 24) priv.wlan_control.rx_event ^= 16;
    if (kind == 25) priv.wlan_control.rx_event_steps++;
    if (kind == 26) priv.wlan_control.txbuf_enrolled++;
}

static void rx_fixture(void)
{
    fresh();
    memset(&wifi, 0, sizeof(wifi));
    memset(register_space, 0, sizeof(register_space));
    memset(objects, 0, sizeof(objects));
    dma_calls = managed_calls = object_count = freed_buffers = freed_contexts = put_refs = 0;
    fail_allocation = 99;
    late_mutation = mutate_on_call = override_cpu = fail_entry = fail_page = fail_wed = programmed = hw_calls = 0;
    family7996 = true;
    mutate_after = 1;
    addresses[0] = 0x97000000;
    for (unsigned i = 1; i < 7; i++) addresses[i] = 0x96000000 + (i - 1) * 0x100000;
    for (unsigned i = 0; i < 8; i++) {
        life.buffers[i].buf = (void *)(uintptr_t)(i + 1);
        life.buffers[i].addr = 0x83000000 + i * 256;
    }
    priv.npu.ops.wlan_alloc_rx_event = airoha_npu_wlan_alloc_rx_event_session;
    priv.npu.ops.wlan_alloc_tx_buffers = airoha_npu_wlan_alloc_tx_buffers_session;
#ifdef HAS_EARLY_TX_PREP
    priv.npu.ops.wlan_validate_tx_buffers = airoha_npu_wlan_validate_tx_buffers_session;
#endif
    wifi.mt76.dev = &endpoint_device;
    wifi.mt76.dma_dev = &dma_device;
    wifi.mt76.mmio.npu = &priv.npu;
    wifi.mt76.mmio.regs = register_space;
    mutex_init(&wifi.mt76.mutex);
    wifi.mt76.q_rx[MT_RXQ_TXFREE_BAND0].flags = MT_NPU_Q_TXFREE(0);
    check(!npu_test_run() && !npu_test_endpoint(0x20000000, 0x100000, 2), "actual held BAR binding");
}

static void rx_dispose(void)
{
    npu_test_close();
    life.exposed = true;
    life.dev = &dma_device;
    airoha_npu_dma_cleanup(&life);
    check(!freed_buffers && !freed_contexts && !put_refs && airoha_npu_dma_retained(&dma_device),
          "exposed teardown retains every allocation and reference");
    life.retained.prev->next = life.retained.next;
    life.retained.next->prev = life.retained.prev;
    for (unsigned i = 0; i < object_count; i++) free(objects[i]);
    check(!pthread_mutex_destroy(&wifi.mt76.mutex.native), "queue fixture mutex");
    check(!pthread_mutex_destroy(&priv.wlan_session_lock.native), "provider fixture mutex");
    memset(&priv, 0, sizeof(priv));
    rx_cases++;
}

static int rx_queue(int count)
{
    return mt76_dma_alloc_queue(&wifi.mt76, &wifi.mt76.q_rx[MT_RXQ_TXFREE_BAND0], 9, count, 2048, 0x100);
}

static void rx_failed(int error)
{
    struct mt76_queue *q = &wifi.mt76.q_rx[MT_RXQ_TXFREE_BAND0];
    unsigned before = calls;
    check(rx_queue(512) == error, "queue allocation error propagates");
    check(!q->desc && !q->desc_dma && !programmed && !managed_calls,
          "failed provider operation publishes no CPU/DMA or queue register");
    if (priv.wlan_session_error) {
        unsigned old_calls = calls, old_dma = dma_calls;
        check(rx_queue(512) == error && calls == old_calls && dma_calls == old_dma,
              "sticky error cannot reallocate, republish or retry transport");
    }
    check(calls >= before, "transport observation");
}

int main(void)
{
    for (unsigned alias = 0; alias < 3; alias++) {
        rx_fixture();
        addresses[0] = 0x17000000 + alias * 0x40000000;
        check(!rx_queue(512), "actual provider and queue allocator succeed");
        struct mt76_queue *q = &wifi.mt76.q_rx[MT_RXQ_TXFREE_BAND0];
        check(dma_calls == 1 && object_count == 1 && !managed_calls && life.rx_event.bytes == 8192 &&
              q->desc == objects[0] && q->desc_dma == addresses[0] && life.rx_published &&
              life.rx_serial == priv.wlan_control.client.base.serial && programmed == 1,
              "exact retained RX-event record before first queue publication");
        unsigned wire = calls;
        check(rx_queue(512) == -EBUSY && calls == wire && dma_calls == 1 && programmed == 1,
              "duplicate queue allocation never falls through to managed backing");
        check(mt7996_npu_hw_init(&wifi) == -EIO && hw_calls == 1 && dma_calls == 7 &&
              object_count == 7 && life.tx_published && !managed_calls,
              "actual TX caller follows fresh RX session serial with six retained allocations");
        rx_dispose();
    }
    for (unsigned kind = 0; kind < 3; kind++) {
        rx_fixture();
        fail_entry = kind == 0; fail_page = kind == 1; fail_wed = kind == 2;
        check(rx_queue(512) == (kind == 2 ? -EIO : -ENOMEM) && life.rx_published &&
              dma_calls == 1 && !programmed && !managed_calls,
              "post-allocation queue failure retains provider backing without programming registers");
        rx_dispose();
    }
    rx_fixture(); fail_allocation = 0; rx_failed(-ENOMEM);
    check(life.rx_attempted && !life.rx_published && dma_calls == 1, "one-shot RX allocation failure");
    rx_dispose();
    for (unsigned kind = 0; kind < 31; kind++) {
        rx_fixture();
        if (kind == 0) addresses[0] = 0;
        if (kind == 1) addresses[0] = UINT64_C(0x197000000);
        if (kind == 2) addresses[0]++;
        if (kind == 3) addresses[0] = 0xc0000000;
        if (kind == 4) addresses[0] = 0xbffffff0;
        if (kind == 5) addresses[0] = 0x7ffffff0;
        if (kind >= 6 && kind < 9) addresses[0] = 0x20000000 + (kind - 6) * 0x40000000;
        if (kind >= 9 && kind < 15) addresses[0] = priv.native_plan[kind - 9][0];
        if (kind >= 15 && kind < 23) addresses[0] = life.buffers[kind - 15].addr ^ 0x80000000;
        if (kind >= 23) override_cpu = kind - 22;
        rx_failed(-EINVAL);
        check(dma_calls == 1 && !freed_buffers, "invalid geometry retains allocation attempt");
        rx_dispose();
    }
    for (unsigned kind = 0; kind < 16; kind++) {
        rx_fixture();
        if (kind == 0) life.boot_identity++;
        if (kind == 1) life.nonce_lo++;
        if (kind == 2) life.nonce_hi++;
        if (kind == 3) life.bound_serial++;
        if (kind == 4) priv.wlan_control.descriptor_gets++;
        if (kind == 5) priv.wlan_control.descriptor_arena = 0x3e810000;
        if (kind == 6) priv.wlan_control.txbuf_enrolled++;
        if (kind == 7) priv.wlan_control.txbuf_steps++;
        if (kind >= 8 && kind < 12) life.buffers[kind - 8].buf = NULL;
        if (kind == 12) life.buffers[3].addr = 0;
        if (kind == 13) life.buffers[3].addr = UINT64_C(0x183000000);
        if (kind == 14) priv.wlan_control.rx_event = addresses[0];
        if (kind == 15) priv.wlan_control.rx_event_steps = 1;
        unsigned wire = calls;
        rx_failed(-EPROTO);
        check(!dma_calls && calls == wire, "bad held history or mailbox fails before allocation/status");
        rx_dispose();
    }
    for (unsigned round = 0; round < 2; round++) {
        for (unsigned kind = 1; kind <= 26; kind++) {
            rx_fixture(); late_mutation = kind;
            mutate_on_call = calls + (round ? 11 : 1);
            rx_failed(-EPROTO);
            check(dma_calls == 1 && life.rx_serial == (kind == 4 ? 1u : 0u),
                  "late mutation retains corrupt state without accepting a serial");
            rx_dispose();
        }
    }
    for (unsigned step = 1; step <= 11; step++) {
        for (unsigned effective = 0; effective < 2; effective++) {
            rx_fixture(); fault_at = calls + step; fault_error = -ETIMEDOUT; effect_fault = effective;
            rx_failed(-ETIMEDOUT);
            check(dma_calls == 1 && life.rx_event.buf && !life.rx_published,
                  "lost STATUS/mailbox/RX/final STATUS reply retains unpublished backing");
            rx_dispose();
        }
    }
    for (unsigned slot = 1; slot < 7; slot++) {
        for (unsigned alias = 0; alias < 3; alias++) {
            rx_fixture(); check(!rx_queue(512), "TX collision RX prerequisite");
            addresses[slot] = (addresses[0] & 0x3fffffff) + alias * 0x40000000;
            check(mt7996_npu_hw_init(&wifi) == -EINVAL && dma_calls == slot + 1 &&
                  !hw_calls && !life.tx_published && !managed_calls,
                  "later TX allocation cannot alias retained RX-event span");
            rx_dispose();
        }
    }
    for (unsigned kind = 1; kind <= 6; kind++) {
        rx_fixture(); check(!rx_queue(512), "TX recheck RX prerequisite");
        late_mutation = kind; mutate_after = 7;
        check(mt7996_npu_hw_init(&wifi) == -EPROTO && dma_calls == 7 && !hw_calls && !life.tx_published,
              "TX must recheck retained RX record and flags after fresh STATUS");
        rx_dispose();
    }
    rx_fixture(); check(!rx_queue(512), "CPU collision RX prerequisite");
    override_cpu = 9;
    check(mt7996_npu_hw_init(&wifi) == -EINVAL && dma_calls == 2 && object_count == 1 && !hw_calls,
          "later TX allocation cannot reuse retained RX CPU backing");
    rx_dispose();
    for (unsigned kind = 0; kind < 4; kind++) {
        rx_fixture();
        if (kind == 0) priv.checked_pair = false;
        if (kind == 1) priv.npu.ops.wlan_alloc_rx_event = NULL;
        if (kind == 2) wifi.mt76.q_rx[MT_RXQ_TXFREE_BAND0].flags = 0;
        if (kind == 3) wifi.mt76.q_rx[MT_RXQ_TXFREE_BAND0].flags |= MT_QFLAG_WED;
        if (kind == 1) priv.checked_pair = false;
        unsigned wire = calls;
        check(!rx_queue(512) && managed_calls == 1 && dma_calls == 1 && calls == wire &&
              !life.rx_attempted && !life.rx_published, "unmarked/non-target fallback remains managed");
        rx_dispose();
    }
    rx_fixture(); wifi.mt76.mmio.npu = NULL; rx_failed(-ENODEV); check(!dma_calls, "lost provider cannot fall back"); rx_dispose();
    rx_fixture(); check(rx_queue(511) == -EINVAL && !dma_calls && !managed_calls && !programmed, "exact ring count"); rx_dispose();
    for (unsigned kind = 0; kind < 7; kind++) {
        rx_fixture();
        void *out = (void *)(uintptr_t)0x12345678;
        dma_addr_t dma = UINT64_C(0xabcdef0123456789);
        unsigned wire = calls;
        int error = airoha_npu_wlan_alloc_rx_event(&priv.npu,
            kind == 0 ? NULL : &endpoint_device,
            kind == 1 ? NULL : kind == 2 ? &other_device : &dma_device,
            kind == 3 ? 511 : 512, kind == 4 ? 8 : 16,
            kind == 5 ? NULL : &out, kind == 6 ? NULL : &dma);
        check(error == -EINVAL && out == (void *)(uintptr_t)0x12345678 &&
              dma == UINT64_C(0xabcdef0123456789) && calls == wire && !dma_calls &&
              !life.rx_attempted && !priv.wlan_session_error,
              "argument preflight preserves outputs, transport and one-shot state");
        rx_dispose();
    }
#ifdef HAS_EARLY_TX_PREP
    for (unsigned mutate=0;mutate<2;mutate++) {
        rx_fixture(); check(!rx_queue(512), "early TX follows retained RX queue");
        check(!mt7996_npu_prepare_tx_buffers(&wifi) && wifi.npu_txd_prepared &&
              !wifi.npu_txd_claimed && dma_calls == 7 && !hw_calls && !managed_calls,
              "early TX retains all six buffers after the actual RX allocation path");
        unsigned wire = calls;
        if (mutate) life.rx_event.addr ^= 16;
        check(mt7996_npu_hw_init(&wifi) == (mutate ? -EPROTO : -EIO) &&
              dma_calls == 7 && !managed_calls && calls == wire &&
              hw_calls == !mutate && wifi.npu_txd_claimed == !mutate,
              "late prepared validation binds retained RX and TX without another allocation");
        rx_dispose();
    }
#endif
    printf("{\"passed\":true,\"cases\":%u,\"rx_bytes\":8192,\"tx_following\":6}\n", rx_cases);
    return 0;
}
