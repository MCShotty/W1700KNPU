#!/usr/bin/env python3
"""Extracted current host C and bounded original RV32 attachment callbacks.

Only generated evidence and scratch below the two authorized output paths.
This is neither a kernel build nor full NPU boot / concurrent hardware proof.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import riscv_const as r

from test_firmware_mailbox_dispatch import Mailbox, MBOX, PAYLOAD
from test_firmware_stop_counterexample import ROOT, SRAM, END, CODE_SHA, DATA_SHA, INPUT
from emulation_layout import ICV

SNAPSHOT = ROOT / '.local/npu-startup/snapshot-audit/mt76'
KERNEL = ROOT / ('.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/'
                 'linux-airoha_an7581/linux-6.18.44')
HEADER = KERNEL / 'include/linux/soc/airoha/airoha_offload.h'
PROVIDER = KERNEL / 'drivers/net/ethernet/airoha/airoha_npu.c'
ARCHIVE = ROOT / '.build/openwrt/dl/mt76-2026.09.01~be5ce791.tar.zst'
GHIDRA = ROOT / ('research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/'
                 'en7581_MT7996_npu_rv32.bin.txt')
SCRATCH = ROOT / '.local/npu-nativewifi/host'
OUT = ROOT / 'research/checkpoints/2026-09-06-npu-nativewifi/host-sequence.json'
PIN = 'be5ce7910521492d4a2e4ce7ee3843680a46c047'
HOST_SHA = 'd70dc1953576c134c8732edb92efd2a8d18e5dbba35435cb230f98ce448b6b5e'
GHIDRA_SHA = '1536a9972838ca7c02da77629e784b392af919c5d25368478aff4d0c2422e2ca'
P = 0x20000000
A = [0x10000000 + i * 0x100000 for i in range(6)]
TXFREE = 0x17000000
PCIE = 0x18000000
ARENA = 0x50000000
DELAY = 0x8400420a
SET_CALLBACKS = {14: 0x8400ff34, 0: 0x8400fdc4, 1: 0x8400fe34, 2: 0x8400fb18,
                 19: 0x8400fc16, 33: 0x8400fdda, 21: 0x8400fbca,
                 22: 0x8400fbb4, 24: 0x8400fc2c}
GET_CALLBACKS = {4: 0x84010164, 10: 0x840101a6}
IMPLEMENTATIONS = {14: 0x8400da92, 0: 0x8400b94e, 1: 0x8400dd82,
                   19: 0x8400d5da, 33: 0x8400dfb0, 21: 0x8400ef36,
                   22: 0x8400b5c6, 24: 0x8400e084}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def function(source, name):
    """Balance lexical braces, retaining the original function bytes."""
    masked = re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                    lambda m: ' ' * len(m[0]), source, flags=re.S)
    match = re.search(r'(?m)^(?:static\s+(?:inline\s+)?)?(?:int|void|u32|bool)\s+' + re.escape(name)
                      + r'\s*\([^;{}]*\)\s*\{', masked)
    assert match, name
    start, depth = match.start(), 1
    end = match.end()
    while depth:
        depth += (masked[end] == '{') - (masked[end] == '}')
        end += 1
    return source[start:end]


def enum(source, name):
    return re.search(r'enum ' + name + r'\s*\{[^}]*\};', source).group()


def exports():
    assert sha(GHIDRA.read_bytes()) == GHIDRA_SHA
    text = GHIDRA.read_text()
    return {int(m[2], 16): {'name': m[1], 'line': text.count('\n', 0, m.start()) + 1,
                            'text': m[3].split('\nASSEMBLY')[0],
                            'assembly': m[3].split('\nASSEMBLY')[1]}
            for m in re.finditer(r'FUNCTION (\S+) @ ram:([0-9a-f]+)\n(.*?)(?=\nFUNCTION |\Z)',
                                 text, re.S)}


def sources():
    zstd = ROOT / '.build/openwrt/staging_dir/host/bin/zstd'
    raw = subprocess.check_output([str(zstd), '-dc', str(ARCHIVE)], timeout=30)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        members = {m.name.split('/', 1)[1]: archive.extractfile(m).read()
                   for m in archive.getmembers() if m.isfile() and '/' in m.name}
    used = ['mt7996/npu.c', 'mt7996/mt7996.h', 'mt7996/dma.c',
            'mt7996/init.c', 'mt76.h', 'npu.c', 'dma.c']
    for name in used:
        assert (SNAPSHOT / name).read_bytes() == members[name], name
    assert sha(members['mt7996/npu.c']) == HOST_SHA
    # All queue selections used by this path are WFDMA0; q_id does not enter
    # these address macros. HIF2 is an independent +0x4000 offset in npu.c.
    config = function(members['mt7996/dma.c'].decode(), 'mt7996_dma_config')
    selections = re.findall(r'(?:RXQ|TXQ|MCUQ)_CONFIG\([^,]+,\s*(WFDMA\d)', config)
    assert selections and set(selections) == {'WFDMA0'}
    pci = members['mt7996/pci.c'].decode()
    assert 'pci_domain_nr(pdev->bus) ? 3 : 2' in pci
    init_done = [name for name, data in members.items()
                 if name.endswith(('.c', '.h')) and b'WLAN_FUNC_SET_WAIT_NPU_INIT_DONE' in data]
    assert init_done == ['airoha_offload.h'], init_done
    return members


C_MODEL = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t phys_addr_t;
typedef uint64_t dma_addr_t;
typedef int gfp_t;
#define GFP_KERNEL 0
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define BUILD_BUG_ON(x) _Static_assert(!(x), #x)
#define dev_warn(...) ((void)0)
#define dev_info(...) ((void)0)
#define rcu_dereference_protected(p, lock) (p)
#define DECLARE_FLEX_ARRAY(t, n) t n[]
#define kzalloc(n, gfp) calloc(1, (n))
#define kfree(p) free(p)
'''

C_STRUCTS = r'''
struct airoha_npu { int dummy; };
struct queue_regs { u32 desc_base; };
struct mt76_queue { struct queue_regs *regs; dma_addr_t desc_dma; };
struct mt76_phy { struct mt76_queue *q_tx[1]; };
struct mt76_dev {
    struct { struct airoha_npu *npu; phys_addr_t phy_addr; int npu_type; } mmio;
    int mutex, token_start;
    void *dev;
    struct mt76_queue q_rx[__MT_RXQ_MAX];
    struct mt76_phy *phys[3];
};
struct mt7996_dev {
    struct mt76_dev mt76;
    void *hif2;
    u32 q_wfdma_mask;
    dma_addr_t npu_txd_addr[6];
};
static struct mt7996_dev fixture;
static struct queue_regs rxregs[__MT_RXQ_MAX], txregs[3];
static int serial, fail_at, fallback;
static int is_mt7996(struct mt76_dev *dev) { return 1; }
static void writel(u32 value, u32 *target) {
    for (int i = 0; i < __MT_RXQ_MAX; i++)
        if (target == &rxregs[i].desc_base)
            printf("{\"kind\":\"write\",\"target\":\"rx%d\",\"value\":%u}\n", i, value);
    for (int i = 0; i < 3; i++)
        if (target == &txregs[i].desc_base)
            printf("{\"kind\":\"write\",\"target\":\"tx%d\",\"value\":%u}\n", i, value);
    *target = value;
}
static void airoha_npu_wlan_enable_irq(struct airoha_npu *npu, int q) {
    printf("{\"kind\":\"irq\",\"queue\":%d}\n", q);
}
'''

C_TRANSPORT = r'''
static int observe(const void *data, int len, void *reply, int reply_len) {
    const u32 *words = data;
    int is_get = ((words[0] >> 4) & 15) == NPU_OP_GET;
    u32 value = (words[0] & 15) * 0x10000 + 0x18000000;
    if (is_get && (words[1] == WLAN_FUNC_GET_WAIT_NPU_VERSION || fallback))
        value = 0x457;
    serial++;
    printf("{\"kind\":\"message\",\"word0\":%u,\"api\":%u,"
           "\"value\":%u,\"length\":%d,\"reply\":%u}\n",
           words[0], words[1], words[2], len, is_get ? value : 0);
    if (serial == fail_at) return -EIO;
    if (is_get) {
        if (reply_len != 4) abort();
        memcpy(reply, &value, 4);
    }
    return 0;
}
static int airoha_npu_send_msg(struct airoha_npu *npu, int func, void *data, int len) {
    if (func != NPU_FUNC_WIFI) abort();
    return observe(data, len, NULL, 0);
}
static int __airoha_npu_send_msg(struct airoha_npu *npu, int func, void *data,
                               int len, void *reply, int reply_len) {
    if (func != NPU_FUNC_WIFI) abort();
    return observe(data, len, reply, reply_len);
}
'''

C_MAIN = r'''
int main(int argc, char **argv) {
    if (argc != 6) return 2;
    struct airoha_npu npu = {0};
    struct mt76_phy phys[3] = {0};
    struct mt76_queue tx[3] = {0};
    fixture.hif2 = atoi(argv[1]) ? &npu : NULL;
    fixture.mt76.mmio.npu_type = atoi(argv[2]);
    fail_at = atoi(argv[3]); fallback = atoi(argv[4]);
    fixture.mt76.mmio.npu = atoi(argv[5]) ? &npu : NULL;
    fixture.mt76.mmio.phy_addr = 0x20000000;
    for (int i = 0; i < 6; i++) fixture.npu_txd_addr[i] = 0x10000000 + i * 0x100000;
    for (int i = 0; i < __MT_RXQ_MAX; i++) fixture.mt76.q_rx[i].regs = &rxregs[i];
    fixture.mt76.q_rx[MT_RXQ_TXFREE_BAND0].desc_dma = 0x17000000;
    for (int i = 0; i < 3; i++) {
        tx[i].regs = &txregs[i]; phys[i].q_tx[0] = &tx[i];
        fixture.mt76.phys[i] = &phys[i];
    }
    if (!fixture.hif2) phys[1].q_tx[0] = phys[0].q_tx[0];
    phys[2].q_tx[0] = phys[1].q_tx[0];
    int result = __mt7996_npu_hw_init(&fixture);
    printf("{\"kind\":\"result\",\"rc\":%d,\"token_start\":%d}\n",
           result, fixture.mt76.token_start);
    return 0;
}
'''


def host_program(members):
    host = members['mt7996/npu.c'].decode()
    common = members['mt76.h'].decode()
    provider = PROVIDER.read_text()
    header = HEADER.read_text()
    funcs = ['mt7992_npu_txrx_offload_init', 'mt7996_npu_txrx_offload_init',
             'mt7996_npu_offload_init', 'mt7992_npu_rxd_init', 'mt7996_npu_rxd_init',
             'mt7996_npu_txd_init', 'mt7996_npu_rx_event_init', 'mt7996_npu_set_pcie_addr',
             'mt7996_npu_tx_done_init', '__mt7996_npu_hw_init']
    constants = re.findall(r'^#define MT7996_(?:RX_RING_SIZE|NPU_RX_RING_SIZE|RX_MCU_RING_SIZE|HW_TOKEN_SIZE)\s+\d+',
                           members['mt7996/mt7996.h'].decode(), re.M)
    assert len(constants) == 4
    parts = [C_MODEL, enum(header, 'airoha_npu_wlan_set_cmd'),
             enum(header, 'airoha_npu_wlan_get_cmd')]
    parts += [enum(common, name) for name in ('mt76_mcuq_id', 'mt76_rxq_id', 'mt76_band_id')]
    parts += [members['mt7996/regs.h'].decode(), '\n'.join(constants), C_STRUCTS]
    parts += [re.search(r'enum \{\s*NPU_OP_SET.*?\};', provider, re.S)[0],
              re.search(r'enum \{\s*NPU_FUNC_WIFI.*?\};', provider, re.S)[0],
              re.search(r'struct wlan_mbox_data \{.*?\};', provider, re.S)[0],
              '_Static_assert(sizeof(struct wlan_mbox_data) == 8, "wire header");', C_TRANSPORT]
    parts += [function(provider, name) for name in ('airoha_npu_wlan_msg_send', 'airoha_npu_wlan_msg_get')]
    parts += ['#define airoha_npu_wlan_send_msg airoha_npu_wlan_msg_send',
              '#define airoha_npu_wlan_get_msg airoha_npu_wlan_msg_get']
    parts += [function(common, name) for name in ('mt76_npu_send_msg', 'mt76_npu_get_msg')]
    parts += [function(host, name) for name in funcs]
    parts += [C_MAIN]
    identities = {name: sha(function(host, name).encode()) for name in funcs}
    return '\n\n'.join(parts), identities


def expected(hif2, port, fallback=False):
    result = []

    def set_(api, index, value):
        result.append(dict(kind='message', word0=0x10 | index, api=api, value=value, length=12, reply=0))

    def get_(api, index, target=None):
        value = 0x457 if api == 10 or fallback else 0x18000000 + index * 0x10000
        result.append(dict(kind='message', word0=0x30 | index, api=api, value=0, length=12, reply=value))
        if target:
            result.append(dict(kind='write', target=target, value=value))

    get_(10, 0)
    set_(14, 0, port)
    set_(1, 0, 1536)
    set_(1, 2, 1024)
    for index, offset, count in ((5, 0xd45a0, 256), (6, 0xd45b0, 512), (7, 0xd45c0, 1024),
                                 (8, 0xa040, 1536)):
        set_(0, index, P + offset)
        set_(1, index, count)
    set_(19, 3, P + 0xa050)
    set_(19, 0, P + 0xd4420)
    set_(19, 2, P + 0xd4450 + hif2 * 0x4000)
    set_(33, 0, 8192)
    for index, target in ((0, 'rx8'), (2, 'rx10'), (10, 'rx11'), (11, 'rx12'), (12, 'rx13'), (8, 'rx17')):
        get_(4, index, target)
    for band, phy, bases in ((0, 1 if hif2 else 0, A[:3]), (2, 0, A[3:])):
        get_(4, band + 5, f'tx{phy}')
        for index, base in zip((band, band + 5, band + 10), bases):
            set_(21, index, base)
    set_(22, 0, TXFREE)
    set_(1, 10, 512)
    set_(0, 10, P + 0xd4590)
    set_(0, 0, P + 0xd4580)
    set_(0, 2, P + 0xd4560 + hif2 * 0x4000)
    set_(0, 15, 0)
    set_(24, 2, 0)
    set_(24, 7, 0)
    result += [dict(kind='irq', queue=i) for i in (0, 1)]
    result.append(dict(kind='result', rc=0, token_start=8192))
    return result


def compile_host(text, name):
    src, exe = SCRATCH / (name + '.c'), SCRATCH / name
    src.write_text(text)
    command = ['cc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
               '-Wno-unused-parameter', '-Wno-sign-compare', '-o', str(exe), str(src)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30,
                               env=dict(os.environ, TMPDIR=str(SCRATCH)))
    assert completed.returncode == 0, completed.stderr
    return exe


def host_tests(members):
    text, identities = host_program(members)
    exe = compile_host(text, 'host-sequence')
    cases, good = [], []

    def run(hif2, port, failure=0, fallback=0, attached=1, binary=exe):
        output = subprocess.check_output([str(binary), *map(str, (hif2, port, failure, fallback, attached))], timeout=5)
        return [json.loads(line) for line in output.splitlines()]

    for hif2 in (0, 1):
        for port in (2, 3):
            want = expected(hif2, port)
            assert run(hif2, port) == want
            messages = [x for x in want if x['kind'] == 'message']
            assert len(messages) == 38
            good.append(dict(hif2=bool(hif2), port=port, trace=want))
            cases.append(f'success_hif{hif2}_port{port}')
            for failure in range(1, 39):
                stop = [i for i, x in enumerate(want) if x['kind'] == 'message'][failure - 1]
                cutoff = want[:stop + 1] + [dict(kind='result', rc=-5, token_start=8192 if failure > 16 else 0)]
                assert run(hif2, port, failure) == cutoff, (hif2, port, failure)
                cases.append(f'failure_hif{hif2}_port{port}_message{failure}')
            assert run(hif2, port, attached=0) == [dict(kind='result', rc=0, token_start=0)]
            assert run(hif2, port, fallback=1) == expected(hif2, port, True)
            cases += [f'absent_hif{hif2}_port{port}', f'fallback457_written_hif{hif2}_port{port}']
    mutations = []
    version_guard = 'if (err) {\n\t\tdev_warn(dev->mt76.dev, "failed getting NPU fw version'
    for name, old, new in (
        ('hif_offset_lost', 'dev->hif2 ? MT_WFDMA0_PCIE1(0) - MT_WFDMA0(0) : 0', '0'),
        ('tail_selector6', 'npu, 7, WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR',
         'npu, 6, WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR'),
        ('first_error_ignored', version_guard, version_guard.replace('if (err)', 'if (0)')),
    ):
        assert old in text
        mutant = compile_host(text.replace(old, new), name)
        differs = run(1, 2, 1 if name == 'first_error_ignored' else 0, binary=mutant)
        baseline = run(1, 2, 1 if name == 'first_error_ignored' else 0)
        assert differs != baseline, name
        mutations.append(name)
    return dict(case_count=len(cases), cases=cases, success_profiles=good,
                mutation_controls=mutations, extracted_function_sha256=identities,
                generated_c_sha256=sha(text.encode()), executable_sha256=sha(exe.read_bytes()),
                compiler=subprocess.check_output(['cc', '--version'], text=True).splitlines()[0])


class ObservedMailbox(Mailbox):
    """Original callback execution, with explicit stop or allocator substitutes."""
    def __init__(self, exported, stops=(), allocator=False):
        super().__init__()
        self.cpu.mem_map(PCIE, 0x10000)
        self.cpu.mem_map(ARENA, 0x100000)
        self.observed, self.calls, self.stops = [], [], set(stops)
        self.functions, self.active = exported, False
        self.allocator = allocator
        self.allocations = []
        self.cpu.hook_add(UC_HOOK_CODE, self.observe_code, begin=0x84000000, end=0x8401ffff)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.observe_write)

    def observe_code(self, cpu, pc, size, _):
        if not self.active:
            return
        args = [cpu.reg_read(getattr(r, f'UC_RISCV_REG_A{i}')) for i in range(5)]
        if pc in self.functions:
            self.calls.append(dict(pc=hex(pc), args=args))
        if pc in self.stops:
            cpu.emu_stop()
        elif self.allocator and pc in (0x8400fab2, 0x84005200):
            value = ARENA + 0x10000 + len(self.allocations) * 0x20000
            self.allocations.append(dict(pc=hex(pc), args=args, value=hex(value)))
            cpu.reg_write(r.UC_RISCV_REG_A0, value)
            cpu.reg_write(r.UC_RISCV_REG_PC, cpu.reg_read(r.UC_RISCV_REG_RA))

    def observe_write(self, cpu, access, address, size, value, _):
        if self.active and not 0x84020000 <= address < 0x84022000:
            self.observed.append(dict(pc=hex(cpu.reg_read(r.UC_RISCV_REG_PC)),
                                      address=hex(address), size=size, value=value))

    def send(self, api, index=0, value=0, get=False, length=12, halt=None, tail=(0xdeadbeef, 0x12345678, 0x87654321)):
        self.calls.clear()
        self.observed.clear()
        self.active = True
        reply = self.message([(0x30 if get else 0x10) | index, api, value, *tail], length=length, halt=halt)
        self.active = False
        reads = [x for x in reply['events'] if x['kind'] == 'payload-read']
        writes = [x for x in self.observed if SRAM <= int(x['address'], 16) < SRAM + 0x8000
                  or PCIE <= int(x['address'], 16) < PCIE + 0x10000
                  or ICV <= int(x['address'], 16) < ICV + 0x1008
                  or ARENA <= int(x['address'], 16) < ARENA + 0x100000]
        return dict(api=api, ifindex=index, operation='GET' if get else 'SET', value=hex(value),
                    advertised_length=length, flags=reply['flags'], words=reply['words'],
                    payload_reads=reads, read_footprint=max((x['offset'] + x['size'] for x in reads), default=0),
                    calls=self.calls.copy(), write_count=len(writes), writes=writes if len(writes) <= 12 else
                    {'first': writes[:4], 'last': writes[-4:]},
                    writes_sha256=sha(json.dumps(writes, sort_keys=True).encode()),
                    halted_at=hex(halt) if halt else None)


def native_tests(exported):
    cases = []

    def record(name, result, footprint=None, flags=7):
        if footprint is not None:
            assert result['read_footprint'] == footprint, (name, result)
        assert result['flags'] == (1 if result['halted_at'] else flags), (name, result)
        result['name'] = name
        cases.append(result)

    h = ObservedMailbox(exported)
    data = (INPUT / 'en7581_MT7996_npu_data.bin').read_bytes()
    table = []
    for operation, callbacks, base in (('SET', SET_CALLBACKS, 0x178), ('GET', GET_CALLBACKS, 0x148)):
        for api, callback in callbacks.items():
            assert struct.unpack_from('<I', data, base + api * 4)[0] == callback
            assert h.get32(SRAM + base + api * 4) == callback
            assert callback in exported
            table.append(dict(operation=operation, api=api, data_offset=hex(base + api * 4),
                              callback=hex(callback), ghidra_line=exported[callback]['line']))

    for index in range(16):
        m = ObservedMailbox(exported)
        m.put32(SRAM + 0x46ec, 0)
        result = m.send(14, index, 0x103)
        assert m.cpu.mem_read(SRAM + 0x390e, 1) == b'\x03'
        record(f'port_low_byte_if{index}', result, 9)
        for api in (0, 22):
            m = ObservedMailbox(exported)
            for slot, offset in ((0x395c, 0), (0x2a80, 0x100), (0x4630, 0x200),
                                 (0x2a9c, 0x300), (0x2a90, 0x400)):
                m.put32(SRAM + slot, PCIE + offset)
            m.put16(SRAM + 0x2a7c, 512)
            result = m.send(api, index, PCIE + 0x1000)
            accepted = {0: {0, 2, 5, 6, 7, 8, 10, 15}, 22: {0, 5, 6, 7}}[api]
            if index not in accepted:
                assert result['write_count'] == 0
            slots = {0: {0: 0x2cf0, 2: 0x3904, 5: 0x395c, 6: 0x2a80, 7: 0x4630,
                         8: 0x2a9c, 10: 0x2a90},
                     22: {0: 0x3964, 5: 0x2a94, 6: 0x2aa4, 7: 0x4638}}
            if index in slots[api]:
                assert m.get32(SRAM + slots[api][index]) == (PCIE + 0x1000 | (0x40000000 if api == 22 else 0))
            if api == 0 and index in (0, 2):
                assert m.get32(PCIE + 0x1008) == (1535 if index == 0 else 1023)
            if api == 0 and index == 15:
                assert [m.get32(PCIE + i * 0x100 + 8) for i in range(5)] == [255, 511, 1023, 1535, 511]
            record(f'api{api}_selector{index}', result, 12)

    for index in (0, 1, 15):
        m = ObservedMailbox(exported)
        before = bytes(m.cpu.mem_read(SRAM, 0x8000))
        result = m.send(2, index, 1)
        assert bytes(m.cpu.mem_read(SRAM, 0x8000)) == before and result['write_count'] == 0
        record(f'api2_init_done_if{index}_no_op', result, 8)
    m = ObservedMailbox(exported)
    result = m.send(10, get=True)
    assert result['words'][2] == 0x457
    record('get10_version_fallback457', result, 8)

    for value in (0, 0x7fe, 0x7ff, 8192, 0x7000, 0x7001, 0xffffffff):
        m = ObservedMailbox(exported)
        before = m.get32(SRAM + 0xbc0)
        result = m.send(33, 0, value)
        assert m.get32(SRAM + 0xbc0) == (value if 0x7ff <= value <= 0x7000 else before)
        record(f'token_bound_{value:x}', result, 12, 7 if 0x7ff <= value <= 0x7000 else 3)

    # Halt at complex initialization entries. No return is invented, and the
    # mailbox remains pending. This records actual wrapper routing/arguments.
    for api, indices, targets in (
        (1, (0, 2, 5, 6, 7, 8, 10), {0: 0x8400d2d4, 2: 0x8400d2d4,
                                      5: 0x8400fab2, 6: 0x8400fab2, 7: 0x8400fab2,
                                      8: 0x8400fab2, 10: 0x8400b432}),
        (19, (0, 2), {0: 0x8400d490, 2: 0x8400d490}),
    ):
        for index in indices:
            target = targets[index]
            m = ObservedMailbox(exported, stops=(target,))
            value = 512 if index == 10 else 1024
            result = m.send(api, index, value, halt=target)
            assert result['calls'][-1]['pc'] == hex(target)
            if api == 19:
                assert m.get32(SRAM + (0x4700 if index == 0 else 0x46fc)) == value
            record(f'api{api}_if{index}_native_entry_only', result, 12)
    for api, valid in ((1, {0, 2, 5, 6, 7, 8, 10}), (19, {0, 2, 3}), (21, {0, 2, 5, 7, 10, 12})):
        for index in sorted(set(range(16)) - valid):
            m = ObservedMailbox(exported)
            result = m.send(api, index, PCIE)
            assert result['write_count'] == 0
            record(f'api{api}_if{index}_no_action', result, 12)

    for index in (0, 2, 3):
        api = 19 if index == 3 else 21
        m = ObservedMailbox(exported)
        result = m.send(api, index, PCIE)
        record(f'api{api}_if{index}_store', result, 12)

    for index, depth, slot in ((5, 512, 0x1f38), (7, 1024, 0x2abc)):
        m = ObservedMailbox(exported, allocator=True)
        result = m.send(21, index, PCIE)
        base = m.get32(SRAM + slot)
        assert len(m.allocations) == 1 and m.allocations[0]['args'][2] == (10 if index == 5 else 11)
        want = struct.pack('<32I', 0x100000, *([0] * 30), 0x10000) * depth
        assert bytes(m.cpu.mem_read(base, len(want))) == want
        result['allocator_substitutions'] = m.allocations
        result['descriptor_bytes'] = len(want)
        record(f'txbuf_if{index}_native_128byte_records_model_allocator', result, 12)

    for index, slot in ((10, 0x3960), (12, 0x2a88)):
        for value in (0, 0x8a000000):
            m = ObservedMailbox(exported, stops=(DELAY, 0x8400a61c))
            m.put32(SRAM + 0x2ab8, value)
            halt = 0x8400a61c if value else DELAY
            result = m.send(21, index, PCIE, halt=halt)
            assert m.get32(SRAM + slot) == (PCIE | 0x40000000)
            record(f'txbuf_if{index}_txpkt_{value:x}_wait_boundary', result, 12)

    slots = {0: 0x2ab0, 2: 0x2ce0, 5: 0x21ec, 7: 0x459c,
             8: 0x2aa0, 10: 0x2a94, 11: 0x2aa4, 12: 0x4638}
    for index in range(16):
        for populated in (False, True):
            m = ObservedMailbox(exported)
            for slot in slots.values():
                m.put32(SRAM + slot, 0)
            if populated and index in slots:
                m.put32(SRAM + slots[index], ARENA + 0x20000)
            m.cpu.mem_write(ARENA + 0x20000, b'\xa5' * 0x4004)
            result = m.send(4, index, get=True)
            want = 0x10020000 if populated and index in slots else 0x457
            assert result['words'][2] == want
            count = {5: 512, 7: 1024}.get(index, 0) if populated else 0
            assert result['write_count'] == count
            if count:
                for i in range(count):
                    assert m.get32(ARENA + 0x20004 + i * 16) == 0x80000000
                    assert m.get32(ARENA + 0x20000 + i * 16) == 0xa5a5a5a5
                assert m.get32(ARENA + 0x20000 + count * 16) == 0xa5a5a5a5
            record(f'get4_if{index}_populated{int(populated)}', result, 8)

    for index in (2, 7):
        for length in (0, 8, 12, 24):
            m = ObservedMailbox(exported)
            m.put32(SRAM + 0x46ec, 0)
            m.put32(SRAM + 0x46f0, 0)
            m.cpu.mem_write(SRAM + 0x46f5, b'\x01' * 6)
            m.cpu.mem_write(ICV, b'\xa5' * 0x100c)
            result = m.send(24, index, 0, length=length)
            assert m.get32(SRAM + 0x46f0) == 1
            assert m.cpu.mem_read(SRAM + 0x46f8, 1) == b'\x03'
            if index == 2:
                assert m.get32(SRAM + 0x46ec) == 1
                assert bytes(m.cpu.mem_read(ICV, 0x1008)) == bytes(0x1008)
                assert m.get32(ICV + 0x1008) == 0xa5a5a5a5
                assert m.cpu.mem_read(SRAM + 0x46f7, 1) == b'\x00'
            else:
                assert m.get32(SRAM + 0x46ec) == 0
                assert m.cpu.mem_read(SRAM + 0x46f5, 1) == b'\x00'
                assert m.cpu.mem_read(SRAM + 0x46f9, 1) == b'\x03'
                assert m.cpu.mem_read(SRAM + 0x46e0, 2) == b'\x01\x01'
            record(f'inode_if{index}_zero_len{length}_overread_and_release', result, 24)
    return dict(case_count=len(cases), table_bindings=table, cases=cases)


def host_adapter_source(members):
    """Static source identities only; parent owns f832 execution and scheduling."""
    common = members['mt76.h'].decode()
    npu = members['npu.c'].decode()
    dma = members['dma.c'].decode()
    dma_h = members['dma.h'].decode()
    mt_dma = members['mt7996/dma.c'].decode()
    init = members['mt7996/init.c'].decode()
    provider = PROVIDER.read_text()
    dts_path = ROOT / '.build/openwrt/target/linux/airoha/dts/an7581.dtsi'
    dts = dts_path.read_text()
    assert 'reg = <0x0 0x1e900000 0x0 0x313000>;' in dts
    assert 'return REG_TX_BASE(qid + 2);' in provider
    assert 'return REG_RX_BASE(qid);' in provider
    for text, pattern in (
        (provider, r'#define NPU_WLAN_BASE_ADDR\s+0x30d000'),
        (provider, r'#define REG_TX_BASE\(_n\)\s+\(NPU_WLAN_BASE_ADDR \+ \(\(_n\) << 4\) \+ 0x080\)'),
        (provider, r'#define REG_RX_BASE\(_n\)\s+\(NPU_WLAN_BASE_ADDR \+ \(\(_n\) << 4\) \+ 0x180\)'),
        (common, r'struct mt76_queue_regs \{\s*u32 desc_base;\s*u32 ring_size;\s*u32 cpu_idx;\s*u32 dma_idx;'),
        (dma_h, r'regmap_write\(npu->regmap, q->wed_regs \+ offset, val\)'),
        (npu, r'q->wed_regs = airoha_npu_wlan_get_queue_addr\(npu, qid, xmit\)'),
        (mt_dma, r'flags = MT_NPU_Q_TX\(phy->mt76->band_idx\)'),
        (npu, r'q->flags = MT_NPU_Q_RX\(index\)'),
        (init, r'band == MT_BAND1 && !dev->hif2'),
        (init, r'mphy->q_tx\[i\] = dev->mt76.phys\[band - 1\]->q_tx\[0\]'),
    ):
        assert re.search(pattern, text), pattern
    sync = function(dma, 'mt76_dma_sync_idx')
    assert sync.index('Q_WRITE(q, ring_size') < sync.index('Q_WRITE(q, desc_base')
    alloc = function(dma, 'mt76_dma_alloc_queue')
    assert alloc.index('dmam_alloc_coherent') < alloc.index('mt76_npu_queue_setup') < alloc.index('mt76_dma_queue_reset')
    reset = function(dma, 'mt76_dma_queue_reset')
    assert reset.index('Q_WRITE(q, cpu_idx, 0)') < reset.index('mt76_dma_sync_idx')
    registration = function(init, 'mt7996_register_device')
    order = ['mt7996_init_hardware(dev)', 'mt7996_register_phy(dev, MT_BAND1)',
             'mt7996_register_phy(dev, MT_BAND2)', 'mt7996_npu_hw_init(dev)',
             'mt7996_dma_rro_start(dev)', 'dev->recovery.hw_init_done = true']
    assert [registration.index(x) for x in order] == sorted(registration.index(x) for x in order)
    connac = next((name for name, data in members.items() if name.endswith('.c') and
                   re.search(rb'(?m)^int\s+mt76_connac_init_tx_queues\(', data)), None)
    assert connac
    connac_body = function(members[connac].decode(), 'mt76_connac_init_tx_queues')
    assert 'mt76_init_tx_queue' in connac_body
    assert 'mt76_init_queue' in function(common, 'mt76_init_tx_queue')
    queue_source = next(name for name, data in members.items() if name.endswith('.c') and
                        re.search(rb'(?m)^mt76_init_queue\(', data))
    queue_body = re.search(r'(?m)^mt76_init_queue\(.*?\n\}', members[queue_source].decode(), re.S)[0]
    assert 'dev->queue_ops->alloc' in queue_body, queue_body
    selected = [('mt76_queue_regs', 'mt76.h', 'struct mt76_queue_regs'),
                ('mt76_init_tx_queue', 'mt76.h', 'static inline int mt76_init_tx_queue'),
                ('mt76_init_queue', queue_source, 'mt76_init_queue('),
                ('mt76_dma_handle_write', 'dma.h', 'mt76_dma_handle_write'),
                ('mt76_dma_sync_idx', 'dma.c', 'mt76_dma_sync_idx'),
                ('mt76_dma_alloc_queue', 'dma.c', 'mt76_dma_alloc_queue'),
                ('mt76_dma_queue_reset', 'dma.c', 'void mt76_dma_queue_reset'),
                ('mt76_npu_queue_setup', 'npu.c', 'void mt76_npu_queue_setup'),
                ('mt76_npu_rx_queue_init', 'npu.c', 'int mt76_npu_rx_queue_init'),
                ('mt7996_init_tx_queues', 'mt7996/dma.c', 'int mt7996_init_tx_queues'),
                ('mt7996_dma_init', 'mt7996/dma.c', 'int mt7996_dma_init'),
                ('mt7996_register_phy', 'mt7996/init.c', 'mt7996_register_phy'),
                ('mt7996_register_device', 'mt7996/init.c', 'int mt7996_register_device'),
                ('mt76_connac_init_tx_queues', connac, 'int mt76_connac_init_tx_queues')]
    refs = {name: dict(archive_member=path, line=members[path].decode().count('\n', 0, members[path].decode().index(marker)) + 1,
                       sha256=sha(members[path])) for name, path, marker in selected}
    refs['airoha_npu_wlan_queue_addr_get'] = dict(path=str(PROVIDER.relative_to(ROOT)),
        line=provider.count('\n', 0, provider.index('static u32 airoha_npu_wlan_queue_addr_get')) + 1,
        sha256=sha(PROVIDER.read_bytes()))
    refs['an7581_npu_reg'] = dict(path=str(dts_path.relative_to(ROOT)),
        line=dts.count('\n', 0, dts.index('npu: npu@1e900000')) + 1, sha256=sha(dts_path.read_bytes()))
    return dict(scope='Static current-host source only; no additional firmware execution or MMIO action.',
        source_refs=refs, ordered_source_phase=order,
        writer_chain=['mt7996_init_tx_queues -> mt76_connac_init_tx_queues -> mt76_init_tx_queue -> mt76_init_queue -> queue_ops->alloc',
                      'mt7996_npu_rx_queues_init -> mt76_npu_rx_queue_init -> queue_ops->alloc',
                      'mt76_dma_alloc_queue -> mt76_npu_queue_setup -> wlan_get_queue_addr',
                      'mt76_dma_queue_reset -> mt76_dma_sync_idx -> Q_WRITE -> mt76_dma_handle_write -> regmap_write'],
        registers=[dict(physical=hex(0x1ec0d000 + offset), field=field, writer=writer, value=value)
                   for offset, field, writer, value in (
                       (0xa0, 'TX0 desc_base', 'primary PHY band0 queue allocation/reset', 'q->desc_dma; 1024 * 208-byte descriptors'),
                       (0xa4, 'TX0 ring_size', 'primary PHY band0 queue allocation/reset', '1024'),
                       (0xb0, 'TX1 desc_base', 'band1 registration with hif2 present', 'q->desc_dma; 512 * 208-byte descriptors'),
                       (0xb4, 'TX1 ring_size', 'band1 registration with hif2 present', '512'),
                       (0x180, 'RX0 desc_base', 'MT_RXQ_NPU0 allocation/reset inside mt7996_dma_init', 'q->desc_dma; 512 * 24-byte descriptors'),
                       (0x190, 'RX1 desc_base', 'MT_RXQ_NPU1 allocation/reset inside mt7996_dma_init', 'q->desc_dma; 512 * 24-byte descriptors'))],
        single_hif_gap='With hif2 absent, band1 shares band0 q_tx[0] and does not allocate NPU TX1; band2 shares band1. This path has no write establishing nonzero 0x1ec0d0b0. Full f832 wait outcome is owned by parent, not executed here.',
        publication_limit='Base writes precede later RX fill/NAPI setup. Nonzero bases are not a filled-ring/readiness or complete-attach certificate.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-write', action='store_true', help='Do not replace tracked JSON evidence.')
    args = parser.parse_args()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    members = sources()
    host = host_tests(members)
    exported = exports()
    native = native_tests(exported)
    adapter = host_adapter_source(members)
    paths = [SNAPSHOT / 'mt7996/npu.c', HEADER, PROVIDER, ARCHIVE, GHIDRA,
             INPUT / 'en7581_MT7996_npu_rv32.bin', INPUT / 'en7581_MT7996_npu_data.bin', Path(__file__)]
    report = dict(passed=True, mt76_revision=PIN,
                  scope='Extracted x86-64 host C with modeled structs/MMIO/replies and bounded original RV32 callback execution. No kernel build, core0/L2 boot, concurrent workers, cache/DMA hardware or router action.',
                  inputs={str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths},
                  mt76_archive_members={name: sha(members[name]) for name in
                                        ('mt7996/regs.h', 'mt7996/pci.c', 'mt7996/dma.c', 'mt7996/init.c', 'mt76.h')},
                  host=host, native=native, host_adapter_source=adapter,
                  static_ghidra_dependencies={hex(pc): dict(name=exported[pc]['name'],
                      line=exported[pc]['line'], decompiled_sha256=sha(exported[pc]['text'].encode()))
                      for pc in (0x8400dd82, 0x8400d2d4, 0x8400b6ba, 0x8400b7e8, 0x8400bc02,
                                 0x8400bae6, 0x8400b432, 0x8400d490, 0x8400a5fa,
                                 0x8400c9b0, 0x8400cdc6, 0x8400d0ae, 0x8400e084)},
                  firmware_sha256=CODE_SHA, data_sha256=DATA_SHA,
                  assumptions=['is_mt7996=true; MT7992 bodies compile but branch is not executed',
                               'native compiler little-endian wire header checked at 8 bytes',
                               'queue mask zero justified by pinned dma_config WFDMA0 selections',
                               'BAR, six host TX addresses and TXFREE DMA address are synthetic',
                               'GET replies in host executable are synthetic, not linked to RV32 callbacks',
                               'Mailbox inherits modeled PLIC/W1C and printf/hart-ID substitutions',
                               'RV32 allocator substitutions only for TXBUFSPACE selectors 5/7; complex routes halt pending at stated entries',
                               'Mailbox payload backing is 256 readable bytes even for short advertised lengths'],
                  gaps=['Full NPU goal remains open; six provider reservations are not full host attach',
                        'Full native DESC/TX initialization and worker scheduling owned by parent',
                        'Physical/cache/IRQ timing, Linux lifetimes, removal/recovery and complete attach not proved',
                        'No production, policy/platform, source lock, overlay, config, build tree, staging, router, commit or ledger edits'])
    if not args.no_write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=True, host_cases=host['case_count'], native_cases=native['case_count'],
                          mutations=len(host['mutation_controls']), messages_per_attach=38,
                          test_sha256=sha(Path(__file__).read_bytes()),
                          evidence_sha256=sha(OUT.read_bytes()) if not args.no_write else None)))


if __name__ == '__main__':
    main()
