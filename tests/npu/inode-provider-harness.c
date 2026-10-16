/* Real C protocol history; transport effects and retained backing are modeled. */
static unsigned inode_cases, post_fault;
static struct airoha_npu_dma_lifetime replacement;
static struct device changed_device;
static const struct npu_bootstrap_packet final_commands[] = {
    {0x10, 0, 0x200d4580}, {0x12, 0, 0x200d4560}, {0x1f, 0, 0},
    {0x12, 24, 0}, {0x17, 24, 0}
};

static struct npu_bootstrap_packet final_command(unsigned lane, unsigned hif2)
{
    struct npu_bootstrap_packet command = final_commands[lane];
    if (lane == 1) command.value += hif2 * 0x4000;
    return command;
}

static void checked_command(struct npu_bootstrap_packet command)
{
    uint32_t output = UINT32_MAX;
    unsigned before = calls;
    check(!npu_test_command(command.header, command.api, command.value, &output), "modeled checked command");
    check(calls == before + 1 && last_transport_bytes == 80, "exactly one checked80 transaction");
}

static void inode_fixture(unsigned hif2, unsigned lane)
{
    static const struct npu_bootstrap_packet prefix[] = {
        {0x30, 10, 0}, {0x10, 14, 2}, {0x10, 1, 1536}, {0x12, 1, 1024},
        {0x15, 0, 0x200d45a0}, {0x15, 1, 256},
        {0x16, 0, 0x200d45b0}, {0x16, 1, 512},
        {0x17, 0, 0x200d45c0}, {0x17, 1, 1024},
        {0x18, 0, 0x2000a040}, {0x18, 1, 1536},
        {0x13, 19, 0x2000a050}, {0x10, 19, 0x200d4420}
    };
    npu_test_reset(UINT64_C(0x1122334455667788), 0x83000000);
    check(!npu_test_run(), "actual session before constructor");
    check(!npu_test_endpoint(0x20000000, 0x100000, 2), "actual endpoint before constructor");
    life.rx_attempted = life.rx_published = life.tx_attempted = life.tx_published = true;
    life.rx_serial = priv.wlan_control.client.base.serial;
    life.rx_event.buf = (void *)(uintptr_t)0x10000;
    life.rx_event.addr = 0x97000000;
    life.rx_event.bytes = 8192;
    for (unsigned i = 0; i < 8; i++) {
        life.buffers[i].buf = (void *)(uintptr_t)(0x20000 + i * 256);
        life.buffers[i].addr = 0x83000000 + i * 256;
    }
    for (unsigned i = 0; i < 6; i++) {
        life.tx_buffers[i].buf = (void *)(uintptr_t)(0x30000 + i * 256);
        life.tx_buffers[i].addr = 0x96000000 + i * 0x100000;
        life.tx_buffers[i].bytes = i < 2 ? 0x20000 : 0x40000;
    }
    for (unsigned i = 0; i < NPU_COLD_TXBUF_RECORDS; i++) {
        uint32_t output;
        struct npu_bootstrap_packet command = {NPU_COLD_BIND_HEADER,
            NPU_COLD_BIND_DMA_API + i, i < 8 ? (uint32_t)life.buffers[i].addr :
                                                 (uint32_t)life.tx_buffers[i - 8].addr};
        check(!npu_linux_control_cold_exchange(&priv.wlan_control, &command, &output), "actual DMA enrollment");
        if (i == 7) {
            command.api = NPU_COLD_BIND_RX_EVENT_API;
            command.value = life.rx_event.addr;
            check(!npu_linux_control_cold_exchange(&priv.wlan_control, &command, &output), "actual RX enrollment");
        }
    }
    for (unsigned i = 0; i < ARRAY_SIZE(prefix); i++) checked_command(prefix[i]);
    checked_command((struct npu_bootstrap_packet){0x12, 19, 0x200d4450 + hif2 * 0x4000});
    checked_command((struct npu_bootstrap_packet){0x10, 33, 8192});
    for (unsigned i = 0; i < 8; i++) {
        if (i == 7)
            for (unsigned j = 0; j < 3; j++)
                checked_command((struct npu_bootstrap_packet){0x10 | npu_cold_txbuf_selector(j),
                                                            21, life.tx_buffers[j].addr});
        checked_command((struct npu_bootstrap_packet){0x30 | npu_cold_descriptor_selector(i), 4, 0});
    }
    for (unsigned i = 3; i < 6; i++)
        checked_command((struct npu_bootstrap_packet){0x10 | npu_cold_txbuf_selector(i),
                                                    21, life.tx_buffers[i].addr});
    checked_command((struct npu_bootstrap_packet){0x10, 22, life.rx_event.addr});
    checked_command((struct npu_bootstrap_packet){0x1a, 1, 512});
    checked_command((struct npu_bootstrap_packet){0x1a, 0, 0x200d4590});
    for (unsigned i = 0; i < lane; i++) checked_command(final_command(i, hif2));
    check(!cold.failed && !cold.inflight && cold.completed == NPU_COLD_COMPLETED_MASK &&
          cold.rx_event_steps == 3 && cold.descriptor_gets == 8 && cold.txbuf_steps == 6 &&
          cold.pcie_tail_steps == (lane < 3 ? lane : 3) && cold.inode_steps == (lane > 3),
          "server history obtained only through actual begin/finish");
    check(priv.wlan_control.pcie_tail_steps == cold.pcie_tail_steps &&
          priv.wlan_control.inode_steps == cold.inode_steps &&
          airoha_npu_wlan_tail_lifetime_valid(&priv), "client and retained model agree");
}

static void mutate_lease(unsigned fault)
{
    if (fault == 1) { replacement = life; priv.dma_lifetime = &replacement; }
    if (fault == 2) priv.checked_pair = false;
    if (fault == 3) priv.native_published = false;
    if (fault == 4) life.exposed = false;
    if (fault == 5) life.endpoint = &changed_device;
    if (fault == 6) life.endpoint_bytes += 4096;
    if (fault == 7) life.bound_serial++;
    if (fault == 8) life.rx_serial++;
    if (fault == 9) life.rx_event.buf = (void *)(uintptr_t)0x40000;
    if (fault == 10) priv.native_plan[0][0] += 4096;
    if (fault == 11) priv.native_plan[0][1] += 4096;
    if (fault == 12) life.dev = priv.npu.dev = &changed_device;
    if (fault >= 13 && fault < 21) life.buffers[fault - 13].buf = (void *)(uintptr_t)(0x50000 + fault * 256);
    if (fault >= 21 && fault < 29) life.buffers[fault - 21].addr += 0x10000;
    if (fault >= 29 && fault < 35) life.tx_buffers[fault - 29].buf = (void *)(uintptr_t)(0x60000 + fault * 256);
    if (fault >= 35 && fault < 41) life.tx_buffers[fault - 35].addr += 0x80000;
}

static void post_mutation(void) { mutate_lease(post_fault); }
static void list_mutation(void) { life.retained.next = life.retained.prev = &life.retained; }

static void sticky_command(struct npu_bootstrap_packet command, int expected)
{
    unsigned before = calls;
    uint32_t output = UINT32_MAX;
    external_after_transport = NULL;
    check(priv.wlan_session_error == expected && priv.wlan_control.closed, "failed checked lane closes without releasing");
    check(airoha_npu_wlan_cold_command(&priv.npu, command.header, command.api, &command.value, 4) == expected,
          "checked error is sticky after uncertain effect");
    check(calls == before && output == UINT32_MAX && life.rx_event.buf && life.tx_buffers[5].buf,
          "no replay or reclaimed backing");
}

int main(void)
{
    for (unsigned hif2 = 0; hif2 < 2; hif2++) {
        for (unsigned lane = 0; lane < 5; lane++) {
            struct npu_bootstrap_packet command = final_command(lane, hif2);
            inode_fixture(hif2, lane);
            checked_command(command);
            check((lane < 3 ? cold.pcie_tail_steps : cold.inode_steps) == (lane < 3 ? lane + 1 : lane - 2),
                  "accepted model advances its own stage");
            inode_cases++;
            inode_fixture(hif2, lane);
            external_after_transport = list_mutation;
            checked_command(command);
            check(life.retained.next == &life.retained && !priv.wlan_control.closed,
                  "independently managed list links are not lease fields");
            inode_cases++;
            for (post_fault = 1; post_fault < 41; post_fault++) {
                inode_fixture(hif2, lane);
                unsigned before = calls;
                uint32_t output = UINT32_MAX;
                external_after_transport = post_mutation;
                check(npu_test_command(command.header, command.api, command.value, &output) == -EPROTO,
                      "post-effect record or plan drift is retained");
                check(calls == before + 1 && last_transport_bytes == 80 && !cold.failed && !cold.inflight,
                      "one actual model effect precedes postflight denial");
                check((lane < 3 ? cold.pcie_tail_steps : cold.inode_steps) == (lane < 3 ? lane + 1 : lane - 2),
                      "postflight failure never rolls back server history");
                if (post_fault != 3 && post_fault != 4)
                    check(airoha_npu_wlan_tail_lifetime_valid(&priv), "coherent drift still passes current-value predicate");
                sticky_command(command, -EPROTO);
                inode_cases++;
            }
            for (unsigned fault = 3; fault <= 4; fault++) {
                inode_fixture(hif2, lane);
                mutate_lease(fault);
                unsigned before = calls;
                uint32_t output;
                check(npu_test_command(command.header, command.api, command.value, &output) == -EPROTO && calls == before,
                      "invalid lease denied before transport");
                sticky_command(command, -EPROTO);
                inode_cases++;
            }
            for (unsigned effect = 0; effect < 2; effect++) {
                inode_fixture(hif2, lane);
                fault_at = calls + 1; fault_error = -ETIMEDOUT; effect_fault = effect;
                uint32_t output;
                check(npu_test_command(command.header, command.api, command.value, &output) == -ETIMEDOUT,
                      "early or lost reply stays failed");
                check((lane < 3 ? cold.pcie_tail_steps : cold.inode_steps) ==
                      (lane < 3 ? lane + effect : lane - 3 + effect), "server records only actual model effects");
                sticky_command(command, -ETIMEDOUT);
                inode_cases++;
            }
        }
        for (unsigned selector = 0; selector < 16; selector++) {
            if (selector == 2 || selector == 7) continue;
            inode_fixture(hif2, 3);
            uint32_t payload[4] = {0};
            unsigned before = calls;
            for (unsigned bytes = 4; bytes <= 16; bytes += 12)
                check(airoha_npu_wlan_msg_send_session(&priv.npu, selector,
                          WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR, payload, bytes, GFP_KERNEL) == -EINVAL,
                      "RRO and other selectors have no checked constructor route");
            check(calls == before && !priv.wlan_session_error && !cold.inode_steps, "closed selectors never use raw fallback");
            inode_cases++;
        }
        for (unsigned selector = 2; selector <= 7; selector += 5)
            for (unsigned kind = 0; kind < 4; kind++) {
                inode_fixture(hif2, selector == 2 ? 3 : 4);
                unsigned before = calls;
                uint32_t payload[4] = {kind == 3};
                int error = airoha_npu_wlan_msg_send_session(&priv.npu, selector,
                    WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR, kind ? payload : NULL,
                    kind == 1 ? 0 : kind == 2 ? 16 : 4, GFP_KERNEL);
                check(error == (kind == 3 ? -EPROTO : -EINVAL) && calls == before,
                      "only one scalar zero may reach the checked constructor");
                inode_cases++;
            }
    }
    npu_test_close();
    check(!pthread_mutex_destroy(&priv.wlan_control.mutex.native), "constructor executor destroy");
    check(!pthread_mutex_destroy(&priv.wlan_session_lock.native), "constructor session destroy");
    allocated = false;
    printf("{\"passed\":true,\"cases\":%u,\"coherent_post_mutations\":38,\"lanes\":5,"
           "\"both_hif\":true,\"modeled_callbacks\":true,\"native_admission\":false}\n", inode_cases);
    return 0;
}
