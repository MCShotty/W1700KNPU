#!/usr/bin/env python3
"""Current mt76 publication order and actual mt7996 cold sender C.

Kernel references and queue configuration are explicitly modeled. The shared
sender can forward its actual calls to the provider/native replay.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode = True
import test_npu_firmware_loader as loader

ROOT = loader.ROOT
MODEL = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
typedef uint64_t u64;
typedef uint64_t phys_addr_t;
typedef uint64_t dma_addr_t;
typedef int gfp_t;
#define GFP_KERNEL 0
#define dev_warn(...) ((void)0)
#define dev_info(...) ((void)0)
#define IS_ERR(p) ((uintptr_t)(p) > UINTPTR_MAX - 4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define MT76_HWRRO_V3 3
#define MT76_HWRRO_V3_1 4
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define BUILD_BUG_ON(c) _Static_assert(!(c), "array contract")
'''
STRUCTS = r'''
struct mt76_queue_regs { u32 desc_base; };
struct mt76_queue { struct mt76_queue_regs *regs; u64 desc_dma; };
struct mt76_phy { struct mt76_queue *q_tx[1]; };
struct airoha_npu { void *dev; };
struct airoha_ppe_dev { unsigned unused; };
struct mt76_dev {
    struct { struct airoha_npu *npu; struct airoha_ppe_dev *ppe_dev;
             phys_addr_t phy_addr; int npu_type; } mmio;
    void *dev, *dma_dev;
    int mutex, hwrro_mode, rx_token_size;
    u32 token_start;
    struct mt76_queue q_rx[__MT_RXQ_MAX];
    struct mt76_phy *phys[2];
};
struct mt7996_dev { struct mt76_dev mt76; void *hif2; u32 q_wfdma_mask; u32 npu_txd_addr[6]; };
static struct mt76_queue_regs rx_regs[__MT_RXQ_MAX], tx_regs[2];
static unsigned register_writes;
static void writel(u32 value, u32 *target) { *target = value; register_writes++; }
static struct airoha_npu npu;
static struct airoha_ppe_dev ppe;
static unsigned events[16], event_count, fault_stage, command_count;
static int (*peer)(unsigned, unsigned, unsigned);
static int (*peer4)(unsigned, unsigned, unsigned, u32 *);
static void event(unsigned id) { assert(event_count < 16); events[event_count++] = id; }
static bool is_mt7996(struct mt76_dev *dev) { return true; }
static int mt7992_npu_txrx_offload_init(struct mt7996_dev *d, struct airoha_npu *p) { assert(false); return -EINVAL; }
static void mutex_lock(int *lock) { assert(!*lock); *lock = 1; event(1); }
static void mutex_unlock(int *lock) { assert(*lock); *lock = 0; event(8); }
static struct airoha_npu *airoha_npu_get(void *dev) { event(2); return &npu; }
static struct airoha_ppe_dev *airoha_ppe_get_dev(void *dev) { event(3); return &ppe; }
static void request_module(const char *name) { assert(false); }
static void airoha_npu_put(struct airoha_npu *p) { assert(p == &npu); event(10); }
static void airoha_ppe_put_dev(struct airoha_ppe_dev *p) { assert(p == &ppe); event(9); }
static int airoha_npu_wlan_init_reserved_memory(struct airoha_npu *p) {
    assert(p == &npu); event(4); return fault_stage == 4 ? -EIO : 0;
}
static int airoha_npu_wlan_bind_endpoint(struct airoha_npu *p, void *endpoint, u64 base, u64 bytes, int type) {
    assert(p == &npu && base == 0x20000000 && bytes == 0x100000 && type == 2);
    event(5); return fault_stage == 5 ? -EIO : 0;
}
#define rcu_assign_pointer(target, value) do { event(6); (target) = (value); } while (0)
static void synchronize_rcu(void) { event(7); }
static int airoha_npu_wlan_send_msg(struct airoha_npu *p, int index,
    enum airoha_npu_wlan_set_cmd api, void *data, int bytes, gfp_t gfp) {
    assert(p == &npu && bytes == 4 && gfp == GFP_KERNEL);
    u32 value; memcpy(&value, data, sizeof(value)); command_count++;
    if (peer4) { u32 result; return peer4(0x10 | index, api, value, &result); }
    if (peer) return peer(0x10 | index, api, value);
    printf("{\"header\":%u,\"api\":%u,\"value\":%u}\n", 0x10 | index, api, value);
    return 0;
}
static int airoha_npu_wlan_get_msg(struct airoha_npu *p, int index,
    enum airoha_npu_wlan_get_cmd api, void *data, int bytes, gfp_t gfp) {
    assert(p == &npu && bytes == 4 && gfp == GFP_KERNEL); command_count++;
    if (peer4) return peer4(0x30 | index, api, 0, data);
    printf("{\"header\":%u,\"api\":%u,\"value\":0}\n", 0x30 | index, api);
    *(u32 *)data = 0x457;
    return 0;
}
'''
ENTRY = r'''
static u32 tx_dma[6] = {0x96000000,0x96100000,0x96200000,0x96300000,0x96400000,0x96500000};
void npu_host_tx_dma(const u32 *values) { memcpy(tx_dma, values, sizeof(tx_dma)); }
int npu_host_rxdesc(int (*transport)(unsigned, unsigned, unsigned, u32 *)) {
    struct mt7996_dev dev = {0};
    for (unsigned i = 0; i < __MT_RXQ_MAX; i++) {
        rx_regs[i].desc_base = 0xabcdef01;
        dev.mt76.q_rx[i].regs = &rx_regs[i];
    }
    peer4 = transport; register_writes = 0;
    int result = mt7996_npu_rxd_init(&dev, &npu);
    peer4 = NULL;
    return result;
}
int npu_host_txdesc(int (*transport)(unsigned, unsigned, unsigned, u32 *)) {
    struct mt7996_dev dev = {0};
    struct mt76_queue queues[2]; struct mt76_phy phys[2] = {0};
    for (unsigned i = 0; i < 2; i++) {
        tx_regs[i].desc_base = 0xabcdef01; queues[i].regs = &tx_regs[i];
        phys[i].q_tx[0] = &queues[i]; dev.mt76.phys[i] = &phys[i];
    }
    for (unsigned i = 0; i < 6; i++) dev.npu_txd_addr[i] = tx_dma[i];
    peer4 = transport; register_writes = 0;
    int result = mt7996_npu_txd_init(&dev, &npu);
    peer4 = NULL;
    return result;
}
u32 npu_host_rxdesc_value(unsigned i) { assert(i < __MT_RXQ_MAX); return rx_regs[i].desc_base; }
u32 npu_host_txdesc_value(unsigned i) { assert(i < 2); return tx_regs[i].desc_base; }
unsigned npu_host_register_writes(void) { return register_writes; }
int npu_host_rx_event(u64 ring, int (*transport)(unsigned, unsigned, unsigned, u32 *)) {
    struct mt7996_dev dev = {0};
    dev.mt76.mmio.phy_addr = 0x20000000;
    dev.mt76.q_rx[MT_RXQ_TXFREE_BAND0].desc_dma = ring;
    peer4 = transport;
    int result = mt7996_npu_rx_event_init(&dev, &npu);
    peer4 = NULL;
    return result;
}
int npu_host_pcie_tail(unsigned hif2, int (*transport)(unsigned, unsigned, unsigned, u32 *)) {
    struct mt7996_dev dev = {0};
    dev.mt76.mmio.phy_addr = 0x20000000;
    dev.hif2 = hif2 ? &npu : NULL;
    peer4 = transport;
    int result = mt7996_npu_set_pcie_addr(&dev, &npu);
    if (!result) result = mt7996_npu_tx_done_init(&dev, &npu);
    peer4 = NULL;
    return result;
}
unsigned npu_host_inode_api(void) { return WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR; }
static unsigned tail_calls, tail_fail_at, tail_hif2;
static int tail_peer(unsigned header, unsigned api, unsigned value, u32 *output) {
    const unsigned headers[] = {0x10, 0x12, 0x1f, 0x12, 0x17};
    const unsigned apis[] = {WLAN_FUNC_SET_WAIT_PCIE_ADDR, WLAN_FUNC_SET_WAIT_PCIE_ADDR,
        WLAN_FUNC_SET_WAIT_PCIE_ADDR, WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR, WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR};
    const unsigned values[] = {0x200d4580, 0x200d4560 + tail_hif2 * 0x4000, 0, 0, 0};
    assert(tail_calls < 5 && header == headers[tail_calls] && api == apis[tail_calls] && value == values[tail_calls]);
    *output = value;
    return tail_calls++ == tail_fail_at ? -EPROTO : 0;
}
static unsigned getter_calls, getter_failure;
static int getter_peer(unsigned header, unsigned api, unsigned value, u32 *output) {
    static const unsigned selectors[] = {0, 2, 10, 11, 12, 8};
    assert(api == 4 && value == 0 && header == (0x30 | selectors[getter_calls]));
    if (getter_calls++ == getter_failure) return -EPROTO;
    *output = 0x1e810000 + getter_calls * 32;
    return 0;
}
int npu_host_txrx(u64 base, unsigned hif2, u32 mask,
                  int (*transport)(unsigned, unsigned, unsigned)) {
    struct mt7996_dev dev = {0};
    dev.mt76.mmio.phy_addr = base;
    dev.hif2 = hif2 ? &npu : NULL;
    dev.q_wfdma_mask = mask;
    peer = transport; command_count = 0;
    int error = mt7996_npu_txrx_offload_init(&dev, &npu);
    peer = NULL;
    return error;
}
int npu_host_offload(u64 base, unsigned hif2, u32 mask,
                     int (*transport)(unsigned, unsigned, unsigned, u32 *)) {
    struct mt7996_dev dev = {0};
    dev.mt76.mmio.phy_addr = base;
    dev.mt76.mmio.npu_type = 2;
    dev.hif2 = hif2 ? &npu : NULL;
    dev.q_wfdma_mask = mask;
    peer4 = transport; command_count = 0;
    int error = mt7996_npu_offload_init(&dev, &npu);
    peer4 = NULL;
    return error;
}
int main(void) {
    const unsigned nominal[] = {1, 2, 3, 4, 5, 6, 6, 7, 8};
    const unsigned fail_init[] = {1, 2, 3, 4, 9, 10, 8};
    const unsigned fail_bind[] = {1, 2, 3, 4, 5, 9, 10, 8};
    for (unsigned stage = 0; stage < 3; stage++) {
        struct mt76_dev dev = {0};
        event_count = 0; fault_stage = stage ? stage + 3 : 0;
        int error = mt76_npu_init(&dev, 0x20000000, 0x100000, 2);
        const unsigned *expected = stage == 1 ? fail_init : stage == 2 ? fail_bind : nominal;
        unsigned count = stage == 1 ? 7 : stage == 2 ? 8 : 9;
        assert(error == (stage ? -EIO : 0) && event_count == count);
        assert(!memcmp(events, expected, count * sizeof(*expected)));
        assert(!dev.mutex);
        assert(stage ? !dev.mmio.npu && !dev.mmio.ppe_dev && !dev.dma_dev :
               dev.mmio.npu == &npu && dev.mmio.ppe_dev == &ppe &&
               dev.mmio.phy_addr == 0x20000000 && dev.hwrro_mode == MT76_HWRRO_V3);
    }
    assert(npu_host_offload(0x20000000, 0, 0, NULL) == 0 && command_count == 16);
    for (getter_failure = 0; getter_failure <= 6; getter_failure++) {
        getter_calls = 0;
        assert(npu_host_rxdesc(getter_peer) == (getter_failure == 6 ? 0 : -EPROTO));
        assert(register_writes == getter_failure);
        assert(getter_calls == (getter_failure == 6 ? 6 : getter_failure + 1));
    }
    for (tail_hif2 = 0; tail_hif2 < 2; tail_hif2++) {
        for (tail_fail_at = 0; tail_fail_at <= 5; tail_fail_at++) {
            tail_calls = 0;
            assert(npu_host_pcie_tail(tail_hif2, tail_peer) == (tail_fail_at == 5 ? 0 : -EPROTO));
            assert(tail_calls == (tail_fail_at == 5 ? 5 : tail_fail_at + 1));
        }
    }
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mt76', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    tree = args.mt76.resolve()
    header = ROOT / '.local/merge-nonoc-20260923/kernel-merged/include/linux/soc/airoha/airoha_offload.h'
    dest = ROOT / '.local/npu-cold-pages-wire-20261010' / args.name
    assert tree.is_relative_to(ROOT) and not dest.exists()
    dest.mkdir(parents=True)
    files = [tree / name for name in ('npu.c', 'mt76.h', 'mt7996/npu.c', 'mt7996/pci.c',
                                      'mt7996/dma.c', 'mt7996/regs.h', 'mt7996/mt7996.h')]
    inputs = {str(p.relative_to(ROOT)): loader.sha(p) for p in
              (*files, header, Path(__file__), Path(loader.__file__), Path(loader.extract.__file__))}
    text = {p.relative_to(tree).as_posix(): p.read_text() for p in files}
    q = loader.extract
    config = q.function(text['mt7996/dma.c'], 'mt7996_dma_config')
    for band in range(3):
        assert re.search(r'RXQ_CONFIG\(MT_RXQ_MSDU_PAGE_BAND' + str(band) + r',\s*WFDMA0,', config)
        assert re.search(r'TXQ_CONFIG\(' + str(band) + r',\s*WFDMA0,', config)
    assert 'pci_resource_start(pdev, 0),\n\t\t      pci_resource_len(pdev, 0),' in text['mt7996/pci.c']
    common = text['mt76.h']
    program = [MODEL, q.declaration(header.read_text(), 'enum', 'airoha_npu_wlan_set_cmd')]
    program += [q.declaration(header.read_text(), 'enum', 'airoha_npu_wlan_get_cmd')]
    program += [q.declaration(common, 'enum', name) for name in ('mt76_mcuq_id', 'mt76_rxq_id', 'mt76_band_id')]
    program += [text['mt7996/regs.h']]
    program += [q.macro(text['mt7996/mt7996.h'], name) for name in ('MT7996_RX_RING_SIZE', 'MT7996_NPU_RX_RING_SIZE', 'MT7996_HW_TOKEN_SIZE', 'MT7996_RX_MCU_RING_SIZE')]
    program += [STRUCTS, q.function(common, 'mt76_npu_send_msg'),
                q.function(common, 'mt76_npu_get_msg'),
                q.function(text['npu.c'], 'mt76_npu_init'),
                q.function(text['mt7996/npu.c'], 'mt7996_npu_txrx_offload_init'),
                q.function(text['mt7996/npu.c'], 'mt7996_npu_offload_init'), ENTRY]
    program.insert(-1, q.function(text['mt7996/npu.c'], 'mt7996_npu_rxd_init'))
    program.insert(-1, q.function(text['mt7996/npu.c'], 'mt7996_npu_txd_init'))
    program.insert(-1, q.function(text['mt7996/npu.c'], 'mt7996_npu_rx_event_init'))
    program.insert(-1, q.function(text['mt7996/npu.c'], 'mt7996_npu_set_pcie_addr'))
    program.insert(-1, q.function(text['mt7996/npu.c'], 'mt7996_npu_tx_done_init'))
    source = dest / 'host.c'
    source.write_text('\n\n'.join(program) + '\n')
    command = [shutil.which('clang'), '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-sign-compare', source]
    binary, shared = dest / 'host-test', dest / 'host-sender.so'
    loader.run(command + ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-o', binary], dest / 'build.log')
    done = loader.run([binary], dest / 'run.log', env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1'))
    rows = [json.loads(line) for line in done.stdout.splitlines()]
    prefix = [dict(header=header, api=api, value=value) for header, api, value in (
        (0x30, 10, 0), (0x10, 14, 2),
        (0x10, 1, 1536), (0x12, 1, 1024), (0x15, 0, 0x200d45a0), (0x15, 1, 256),
        (0x16, 0, 0x200d45b0), (0x16, 1, 512), (0x17, 0, 0x200d45c0), (0x17, 1, 1024),
        (0x18, 0, 0x2000a040), (0x18, 1, 1536), (0x13, 19, 0x2000a050),
        (0x10, 19, 0x200d4420), (0x12, 19, 0x200d4450), (0x10, 33, 8192))]
    assert rows == prefix
    loader.run(command + ['-shared', '-fPIC', '-o', shared], dest / 'shared-build.log')
    assert all(loader.sha(ROOT / p) == digest for p, digest in inputs.items())
    result = dict(passed=True, publication_cases=3, prefix=prefix, unsupported_next=None, completed_offload=True,
                  rx_getter_failure_cases=7,
                  pcie_tail_sender_cases=12,
                  inputs=inputs, shared=str(shared.relative_to(ROOT)), shared_sha256=loader.sha(shared),
                  binary_sha256=loader.sha(binary), sanitizers=['address', 'undefined', 'leak'],
                  limits=['Actual mt76 initialization and complete mt7996 offload sender C; kernel references/RCU and queue state modeled.',
                          'Current DMA configuration is source-checked to WFDMA0 for page/TX bands, not physically executed.',
                          'Binding-before-publication is CPU ordering, not prior-user exclusion or a physical DMA grant.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, publication_cases=3, prefix_commands=len(prefix), completed_offload=True)))


if __name__ == '__main__':
    main()
