/* Read-only lifetime predicate with explicit synthetic retained records. */
static unsigned tail_cases;

static void tail_fixture(unsigned hif2)
{
    npu_test_reset(UINT64_C(0x1122334455667788), 0x83000000);
    check(!npu_test_run(), "actual session prefix in modeled transport");
    check(!npu_test_endpoint(0x20000000, 0x100000, 2), "actual endpoint binding");
    life.rx_attempted = life.rx_published = life.tx_attempted = life.tx_published = true;
    life.rx_serial = priv.wlan_control.client.base.serial;
    life.rx_event.buf = (void *)(uintptr_t)0x1000;
    life.rx_event.addr = priv.wlan_control.rx_event = 0x97000000;
    life.rx_event.bytes = 8192;
    priv.wlan_control.tx0_register = 0x200d4420;
    priv.wlan_control.tx2_register = 0x200d4450 + hif2 * 0x4000;
    for (unsigned i = 0; i < 6; i++) {
        life.tx_buffers[i].buf = (void *)(uintptr_t)(0x2000 + i * 256);
        life.tx_buffers[i].addr = 0x96000000 + i * 0x100000;
        life.tx_buffers[i].bytes = i < 2 ? 0x20000 : 0x40000;
    }
}

int main(void)
{
    for (unsigned hif2 = 0; hif2 < 2; hif2++) {
        for (unsigned fault = 0; fault < 33; fault++) {
            tail_fixture(hif2);
            if (fault == 1) priv.dma_lifetime = NULL;
            if (fault == 2) life.exposed = false;
            if (fault == 3) priv.native_published = false;
            if (fault == 4) life.dev = &endpoint_device;
            if (fault == 5) life.endpoint = NULL;
            if (fault == 6) life.endpoint_bound = false;
            if (fault == 7) life.boot_identity ^= 1;
            if (fault == 8) life.rx_attempted = false;
            if (fault == 9) life.rx_published = false;
            if (fault == 10) life.rx_serial = 0;
            if (fault == 11) life.tx_attempted = false;
            if (fault == 12) life.tx_published = false;
            if (fault == 13) life.rx_event.buf = NULL;
            if (fault == 14) life.rx_event.bytes--;
            if (fault == 15) life.rx_event.addr += 16;
            if (fault == 16) life.rx_event.addr = priv.wlan_control.rx_event = 0;
            if (fault == 17) life.nonce_lo ^= 1;
            if (fault == 18) life.nonce_hi ^= 1;
            if (fault == 19) life.endpoint_base += 4096;
            if (fault == 20) life.endpoint_bytes = 4096;
            if (fault == 21) priv.wlan_control.tx0_register += 4;
            if (fault == 22) priv.wlan_control.tx2_register += 4;
            if (fault == 23) life.endpoint_bytes = UINT32_MAX;
            if (fault == 24) life.rx_event.addr = priv.wlan_control.rx_event = 0x2000a000;
            if (fault == 25) life.rx_event.addr = priv.wlan_control.rx_event = priv.native_plan[5][0];
            if (fault == 26) life.tx_buffers[0].buf = NULL;
            if (fault == 27) life.tx_buffers[1].bytes--;
            if (fault == 28) life.tx_buffers[2].addr = life.rx_event.addr;
            if (fault == 29) life.tx_buffers[3].addr = 0;
            if (fault == 30) life.tx_buffers[4].addr = life.tx_buffers[0].addr;
            if (fault == 31) life.tx_buffers[5].addr |= UINT64_C(1) << 32;
            if (fault == 32) life.tx_buffers[5].buf = life.rx_event.buf;
            unsigned char before_priv[sizeof(priv)], before_life[sizeof(life)];
            memcpy(before_priv, &priv, sizeof(priv));
            memcpy(before_life, &life, sizeof(life));
            check(airoha_npu_wlan_tail_lifetime_valid(&priv) == !fault, "tail lifetime field");
            check(!memcmp(before_priv, &priv, sizeof(priv)) && !memcmp(before_life, &life, sizeof(life)),
                  "tail lifetime validation is read only");
            tail_cases++;
        }
        for (unsigned i = 0; i < 6; i++) {
            tail_fixture(hif2);
            life.tx_buffers[i].bytes ^= 256;
            check(!airoha_npu_wlan_tail_lifetime_valid(&priv), "every retained TX record extent");
            tail_cases++;
        }
        for (unsigned header = 0x10; header <= 0x1f; header += header == 0x10 ? 2 : 13) {
            tail_fixture(hif2);
            unsigned before = calls;
            u32 output = 0xabcdef01;
            check(npu_test_command(header, 0, 0, &output) == -EPROTO, "tail needs actual protocol history");
            check(calls == before && priv.wlan_control.closed && priv.wlan_session_error == -EPROTO,
                  "checked route rejects before native transport without history");
            tail_cases++;
        }
    }
    npu_test_close();
    check(!pthread_mutex_destroy(&priv.wlan_control.mutex.native), "tail executor destroy");
    check(!pthread_mutex_destroy(&priv.wlan_session_lock.native), "tail session destroy");
    printf("{\"passed\":true,\"cases\":%u,\"synthetic_records\":true,\"native_admission\":false}\n", tail_cases);
    return 0;
}
