#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "control-v2.h"

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef unsigned int gfp_t;
#define DECLARE_FLEX_ARRAY(type, member) type member[]
#define EXPORT_SYMBOL_GPL(name)
#define AIROHA_NPU_MBOX_SIZE 256
#define MSEC_PER_SEC 1000
#define MBOX_MSG_FUNC_ID (15u << 11)
#define MBOX_MSG_STATUS (7u << 2)
#define MBOX_MSG_DONE 2u
#define MBOX_MSG_WAIT_RSP 1u
#define NPU_MBOX_SUCCESS 1u
#define FIELD_PREP(mask, v) (((u32)(v) << __builtin_ctz(mask)) & (mask))
#define FIELD_GET(mask, v) (((v) & (mask)) >> __builtin_ctz(mask))
#define REG_CR_MBQ0_CTRL(n) (0x30c030u + (n) * 4)

struct regmap { u32 r[4]; };
struct airoha_npu_core { int lock; bool mbox_pending; unsigned char *buf; u32 addr; };
struct airoha_npu { struct airoha_npu_core cores[8]; struct regmap *regmap; };
static struct regmap map;
static struct airoha_npu npu;
static struct npu_admission admission;
static struct npu_barrier barrier;
static struct npu_control_v2_session session;
static struct npu_control_v2_client client;
static u32 bounce[64];
static unsigned char wire[82];
static int depth, writes, kicks, deferred, fault_index, fault_after, poll_fault;
static int assertions;

static void check(bool condition)
{
    assert(condition);
    assertions++;
}

static void spin_lock_bh(int *lock) { (void)lock; check(!depth); depth++; }
static void spin_unlock_bh(int *lock) { (void)lock; check(depth == 1); depth--; }
static void *kzalloc(size_t bytes, gfp_t gfp) { (void)gfp; return calloc(1, bytes); }
static void kfree(void *pointer) { free(pointer); }
static u32 get_unaligned_le32(const void *pointer)
{
    const unsigned char *p = pointer;
    return (u32)p[0] | (u32)p[1] << 8 | (u32)p[2] << 16 | (u32)p[3] << 24;
}

static void firmware_complete(void)
{
    check(map.r[0] == npu.cores[0].addr && map.r[1] == 80);
    check(FIELD_GET(MBOX_MSG_FUNC_ID, map.r[3]) == 0 && (map.r[3] & 1));
    int handled = npu_control_v2_dispatch(&session, &admission, &barrier,
                                         (struct npu_control_v2_packet *)bounce, map.r[1]);
    map.r[3] |= MBOX_MSG_DONE | (handled ? FIELD_PREP(MBOX_MSG_STATUS, NPU_MBOX_SUCCESS) : 0);
}

static int regmap_read(struct regmap *m, u32 reg, u32 *value)
{
    u32 index = (reg - REG_CR_MBQ0_CTRL(0)) / 4;
    check(index < 4);
    *value = m->r[index];
    return 0;
}

static int regmap_write(struct regmap *m, u32 reg, u32 value)
{
    u32 index = (reg - REG_CR_MBQ0_CTRL(0)) / 4;
    check(index < 4);
    writes++;
    if ((int)index == fault_index && !fault_after)
        return -EIO;
    m->r[index] = value;
    if (index == 2) {
        kicks++;
        if (!deferred)
            firmware_complete();
    }
    return (int)index == fault_index ? -EIO : 0;
}

#define regmap_read_poll_timeout_atomic(m, reg, value, condition, delay, timeout) ({ \
    int status = regmap_read((m), (reg), &(value)); \
    if (!status && (poll_fault || !(condition))) \
        status = poll_fault ? -EIO : -ETIMEDOUT; \
    status; })

#include "control-v2-provider.inc"

static void reset(void)
{
    memset(&map, 0, sizeof(map));
    memset(&npu, 0, sizeof(npu));
    memset(bounce, 0xa5, sizeof(bounce));
    npu.regmap = &map;
    npu.cores[0].buf = (unsigned char *)bounce;
    npu.cores[0].addr = 0x02000000;
    depth = writes = kicks = deferred = fault_after = poll_fault = 0;
    fault_index = -1;
    npu_barrier_init(&barrier);
    npu_admission_init(&admission);
    npu_control_v2_init(&session, 0x12345678, 0x9abcdef0);
    npu_client_v2_init(&client, 0x31415926, 0x27182818);
}

static u32 request(void)
{
    memset(wire, 0xcc, sizeof(wire));
    u32 ticket = npu_client_v2_request(&client, wire + 1, 80);
    check(ticket != 0 && wire[0] == 0xcc && wire[81] == 0xcc);
    return ticket;
}

static void exchange(void)
{
    u32 ticket = request();
    int status = airoha_npu_wlan_control(&npu, wire + 1, 80);
    check(status == 0 && !npu.cores[0].mbox_pending && !depth);
    check(npu_client_v2_complete(&client, ticket, status, wire + 1, 80) == NPU_CLIENT_ACCEPTED);
    check(wire[0] == 0xcc && wire[81] == 0xcc);
}

int main(void)
{
    u32 epoch;
    _Static_assert(sizeof(struct wlan_mbox_data) == 8, "WLAN header layout");
    reset();
    for (int i = 0; i < 3; i++)
        exchange();
    for (u32 hart = 1; hart < 8; hart++)
        check(npu_barrier_poll(&barrier, hart, &epoch) == NPU_BARRIER_PARK);
    npu_admission_idle(&admission, &barrier);
    exchange();
    check(client.base.phase == NPU_CLIENT_PARKED && !client.base.drain_mask);
    check(!npu_barrier_reclaimable(&barrier, 1));

    reset();
    request();
    unsigned char body[72];
    memcpy(body, wire + 9, sizeof(body));
    check(airoha_npu_wlan_msg_get(&npu, 15, WLAN_FUNC_GET_WAIT_NPU_INFO,
                                  body, sizeof(body), 0) == -EINVAL);
    check(bounce[0] == 0x3f && bounce[1] == 0 && bounce[2] == 0);
    check(get_unaligned_le32(body) == NPU_CONTROL_V2_REQUEST);

    const int lengths[] = { -1, 0, 64, 79, 81, 257 };
    for (unsigned int i = 0; i < sizeof(lengths) / sizeof(lengths[0]); i++) {
        reset();
        check(airoha_npu_wlan_control(&npu, (void *)(uintptr_t)1, lengths[i]) == -EINVAL);
        check(!writes && !depth && !npu.cores[0].mbox_pending);
    }
    reset();
    check(airoha_npu_wlan_control(NULL, (void *)(uintptr_t)1, 80) == -ENODEV);
    check(airoha_npu_wlan_control(&npu, NULL, 80) == -EINVAL);
    for (int field = 0; field < 5; field++) {
        reset();
        request();
        wire[1 + field * 4] ^= 1;
        check(airoha_npu_wlan_control(&npu, wire + 1, 80) == -EINVAL);
        check(!writes && !depth);
    }

    for (int index = 0; index < 4; index++) {
        for (int after = 0; after < 2; after++) {
            reset();
            u32 ticket = request();
            unsigned char saved[80];
            memcpy(saved, wire + 1, sizeof(saved));
            fault_index = index;
            fault_after = after;
            int status = airoha_npu_wlan_control(&npu, wire + 1, 80);
            check(status == -EIO && !memcmp(saved, wire + 1, sizeof(saved)));
            check(npu.cores[0].mbox_pending == (index >= 2));
            check(npu_client_v2_complete(&client, ticket, status,
                                          (void *)(uintptr_t)1, 80) == NPU_CLIENT_REJECTED);
            check(!npu_client_v2_request(&client, (void *)(uintptr_t)1, 80));
        }
    }

    for (int poll_error = 0; poll_error < 2; poll_error++) {
        reset();
        exchange();
        exchange();
        u32 ticket = request();
        deferred = 1;
        poll_fault = poll_error;
        int status = airoha_npu_wlan_control(&npu, wire + 1, 80);
        check(status == (poll_error ? -EIO : -ETIMEDOUT) && npu.cores[0].mbox_pending);
        check(npu_client_v2_complete(&client, ticket, status,
                                      (void *)(uintptr_t)1, 80) == NPU_CLIENT_REJECTED);
        u32 retained[64];
        memcpy(retained, bounce, sizeof(retained));
        int before = writes;
        check(airoha_npu_wlan_control(&npu, wire + 1, 80) == -EBUSY);
        check(before == writes && !memcmp(retained, bounce, sizeof(retained)));
        firmware_complete();
        check(npu_client_v2_complete(&client, ticket, 0, bounce, 80) == NPU_CLIENT_IGNORED);
        check(client.base.phase == NPU_CLIENT_FAILED && !barrier.released && !barrier.armed);
    }
    printf("{\"passed\":true,\"assertions\":%d,\"old_get_discards_body\":true,"
           "\"bidirectional_round_trips\":8,\"register_error_cases\":8,"
           "\"timeout_cases\":2,\"physical_drains\":false}\n", assertions);
    return 0;
}
