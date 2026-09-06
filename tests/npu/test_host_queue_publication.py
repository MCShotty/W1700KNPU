#!/usr/bin/env python3
"""Pinned host-C TX queue evidence; no firmware, device, or shared-helper imports.

Run directly in WSL. Only the generated host harness runs. Whole-driver startup,
connac/mac80211 framework implementation, provider implementation and hardware
are not executed. Outputs stay in the three task-owned paths.
"""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / '.local/npu-startup/snapshot-audit/mt76'
ARCHIVE = ROOT / '.build/openwrt/dl/mt76-2026.09.01~be5ce791.tar.zst'
SCRATCH = ROOT / '.local/npu-hostqueue'
OUT = ROOT / 'research/checkpoints/2026-09-06-npu-hostqueue/host-queues.json'
PIN = 'be5ce7910521492d4a2e4ce7ee3843680a46c047'
BASE = '834786a0248b23a602c168c268c7852c0cf9b6fc'
ARCHIVE_SHA = 'd1d0f7588c5b9ceafcac341ce19dd206ed9ec106847e672ab77e48bacb57f81a'
FILES = ['mt7996/init.c', 'mt7996/dma.c', 'dma.c', 'dma.h', 'npu.c',
         'mt76.h', 'mt7996/mt7996.h', 'mt7996/regs.h', 'mt7996/eeprom.h',
         'airoha_offload.h', 'mt76_connac_mac.c', 'mac80211.c']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_sources():
    assert sha(ARCHIVE.read_bytes()) == ARCHIVE_SHA, 'archive identity'
    zstd = ROOT / '.build/openwrt/staging_dir/host/bin/zstd'
    raw = subprocess.check_output([str(zstd), '-dc', str(ARCHIVE)], timeout=30)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        sources = {name: archive.extractfile(
            'mt76-2026.09.01~be5ce791/' + name).read() for name in FILES}
    for name, data in sources.items():
        path = SNAPSHOT / name
        if path.exists():
            assert path.read_bytes() == data, f'snapshot drift: {name}'
    return {name: data.decode() for name, data in sources.items()}


def function(source, name):
    # Mask comments/literals before brace balancing; return original bytes.
    masked = re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                    lambda m: ' ' * len(m[0]), source, flags=re.S)
    match = re.search(r'(?m)^(?:static\s+(?:inline\s+)?)?'
                      r'(?:int|void|u32|bool|struct mt76_queue\s*\*)\s*'
                      + re.escape(name) + r'\s*\([^;{}]*\)\s*\{', masked)
    assert match, name
    end, depth = match.end(), 1
    while depth:
        depth += (masked[end] == '{') - (masked[end] == '}')
        end += 1
    return source[match.start():end]


def declaration(source, kind, name):
    match = re.search(r'(?m)^' + kind + ' ' + name + r' \{.*?^\}[^;]*;', source, re.S)
    assert match, name
    return match[0]


def macro(source, name):
    lines = source.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if re.match(r'#define\s+' + re.escape(name) + r'(?:\s|\()', line):
            result = line
            while result.endswith('\\\n'):
                i += 1
                result += lines[i]
            return result.rstrip('\n')
    raise AssertionError(name)


PRELUDE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef uint16_t __le16;
typedef uint32_t __le32;
typedef uint64_t dma_addr_t;
typedef int spinlock_t;
#define __packed __attribute__((packed))
#define __aligned(n) __attribute__((aligned(n)))
#define __iomem
#define BIT(n) (1U << (n))
#define GENMASK(h,l) ((~0U << (l)) & (~0U >> (31-(h))))
#define FIELD_GET(mask,v) (((v) & (mask)) >> __builtin_ctz(mask))
#define FIELD_PREP(mask,v) (((v) << __builtin_ctz(mask)) & (mask))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define GFP_KERNEL 0
#define ETH_ALEN 6
#define IEEE80211_AC_VO 0
#define IEEE80211_AC_VI 1
#define IEEE80211_AC_BE 2
#define IEEE80211_AC_BK 3
#define CONFIG_MT76_NPU 1
#define CONFIG_NET_MEDIATEK_SOC_WED 0
#define IS_ENABLED(x) (x)
#define cpu_to_le32(x) (x)
#define rcu_dereference(x) (x)
#define rcu_access_pointer(x) (x)
#define rcu_dereference_protected(x,lock) (x)
#define mt76_is_mmio(dev) true
#define rcu_read_lock() ((void)0)
#define rcu_read_unlock() ((void)0)
#define spin_lock_init(x) ((void)0)
#define INIT_DELAYED_WORK(work,fn) ((void)0)
'''

FRAMEWORK = r'''
struct mtk_wed_device { int unused; };
struct airoha_npu { void *regmap; };
struct mt76_phy {
    struct mt76_dev *dev; void *priv; void *hw;
    struct mt76_queue *q_tx[__MT_TXQ_MAX];
    u8 band_idx, macaddr[ETH_ALEN]; int mac_work;
};
struct mt76_dev {
    struct { void *regs; struct mtk_wed_device wed, wed_hif2;
             struct airoha_npu *npu; } mmio;
    struct mt76_phy *phys[3];
    struct { void *data; } eeprom;
    void *dev, *dma_dev; int mutex;
};
struct mt7996_phy { struct mt7996_dev *dev; struct mt76_phy *mt76; };
struct mt7996_dev {
    struct mt76_dev mt76; struct mt76_phy mphy; struct mt7996_phy phy;
    void *hif2; u8 q_id[64]; u32 q_wfdma_mask;
};
static struct mt7996_dev fixture;
static u32 mmio[0x100000 / 4], regmap[0x313000 / 4];
static int band, fail_band, hits, alloc_count;
static const char *failure;
static void *allocations[64];
static unsigned allocation_count;
static dma_addr_t next_dma = 0x20000000;
static const int mt76_rates[] = {0};

static void event(const char *op, u32 addr, u32 value) {
    printf("{\"op\":\"%s\",\"band\":%d,\"address\":%u,\"value\":%u}\n",
           op, band, addr, value);
}
static bool fail(const char *point) {
    if (band == fail_band && !strcmp(failure, point)) { hits++; return true; }
    return false;
}
static void *allocate(size_t size) {
    assert(allocation_count < ARRAY_SIZE(allocations));
    void *p = calloc(1, size); assert(p);
    allocations[allocation_count++] = p; return p;
}
static bool is_mt7996(struct mt76_dev *dev) { assert(dev == &fixture.mt76); return true; }
static bool is_mt7992(struct mt76_dev *dev) { assert(dev == &fixture.mt76); return false; }
static bool mtk_wed_device_active(struct mtk_wed_device *wed) { (void)wed; return false; }
static bool mtk_wed_get_rx_capa(struct mtk_wed_device *wed) { (void)wed; return false; }
static void writel(u32 value, u32 *addr) {
    uintptr_t offset = (uintptr_t)addr - (uintptr_t)mmio;
    assert(offset < sizeof(mmio) && !(offset % 4));
    *addr = value; event("mmio_write", offset, value);
}
static u32 readl(u32 *addr) {
    uintptr_t offset = (uintptr_t)addr - (uintptr_t)mmio;
    assert(offset < sizeof(mmio) && !(offset % 4));
    event("mmio_read", offset, *addr); return *addr;
}
static int regmap_write(void *map, u32 addr, u32 value) {
    assert(map == regmap && addr < sizeof(regmap) && !(addr % 4));
    regmap[addr/4] = value; event("regmap_write", addr, value); return 0;
}
static int regmap_read(void *map, u32 addr, u32 *value) {
    assert(map == regmap && addr < sizeof(regmap) && !(addr % 4));
    *value = regmap[addr/4]; event("regmap_read", addr, *value); return 0;
}
static u32 airoha_npu_wlan_get_queue_addr(struct airoha_npu *npu, int qid, bool tx) {
    assert(npu && tx && qid >= 0 && qid < 3);
    u32 addr = 0x30d000 + 0x80 + ((qid + 2) << 4);
    event("provider_address_model", addr, qid); return addr;
}
static void *dmam_alloc_coherent(void *dev, size_t size, dma_addr_t *dma, int flags) {
    (void)dev; (void)flags;
    if (fail("descriptor")) return NULL;
    *dma = next_dma; next_dma += 0x100000;
    event("descriptor_allocation", *dma, size); alloc_count++;
    return allocate(size);
}
static void *devm_kzalloc(void *dev, size_t size, int flags) {
    (void)dev; (void)flags;
    if (fail("entry")) return NULL;
    event("entry_allocation", 0, size); return allocate(size);
}
static int mt76_create_page_pool(struct mt76_dev *dev, struct mt76_queue *q) {
    (void)dev; assert(q->buf_size == 0);
    return fail("page_pool") ? -ENOMEM : 0;
}
static int mt76_wed_dma_setup(struct mt76_dev *dev, struct mt76_queue *q, bool reset) {
    (void)dev; assert(!reset && !(q->flags & MT_QFLAG_WED));
    return fail("wed_setup") ? -EIO : 0;
}
static void mt76_dma_queue_magic_cnt_init(struct mt76_dev *dev, struct mt76_queue *q) {
    (void)dev; assert(!(q->flags & MT_QFLAG_WED_RRO));
}
static struct mt76_phy *mt76_alloc_radio_phy(struct mt76_dev *dev, size_t size, int index) {
    if (fail("phy")) return NULL;
    struct mt76_phy *phy = allocate(sizeof(*phy));
    phy->dev = dev; phy->band_idx = index; phy->priv = allocate(size); return phy;
}
static int mt7996_eeprom_parse_hw_cap(struct mt7996_dev *dev, struct mt7996_phy *phy) {
    (void)dev; (void)phy; return fail("eeprom_cap") ? -EIO : 0;
}
static bool is_valid_ether_addr(const u8 *addr) { (void)addr; return true; }
static int mt76_eeprom_override(struct mt76_phy *phy) {
    (void)phy; return fail("override") ? -EIO : 0;
}
static void mt7996_init_wiphy_band(void *hw, struct mt7996_phy *phy) { (void)hw; (void)phy; }
static int mt76_register_phy(struct mt76_phy *phy, bool vht, const int *rates, size_t count) {
    (void)phy; (void)vht; (void)rates; (void)count;
    return fail("registration") ? -EIO : 0;
}
#define mt76_wr(...) abort()
#define mtk_wed_device_start(...) abort()
static int mt76_connac_init_tx_queues(struct mt76_phy *, int, int, int, void *, u32);
'''

BRIDGE = r'''
/* Modeled connac -> mt76_init_tx_queue -> mt76_init_queue boundary.
 * Bodies from the two out-of-scope C files are hashed, not compiled here.
 */
static int mt76_connac_init_tx_queues(struct mt76_phy *phy, int idx, int count,
                                      int base, void *wed, u32 flags) {
    event("framework_queue_request", base + idx * MT_RING_SIZE, count);
    if (fail("queue")) return -ENOMEM;
    struct mt76_queue *q = allocate(sizeof(*q));
    q->flags = flags; q->wed = wed;
    int ret = mt76_dma_alloc_queue(phy->dev, q, idx, count, 0, base);
    if (ret < 0) return ret;
    for (int i = 0; i <= MT_TXQ_PSD; i++) phy->q_tx[i] = q;
    return 0;
}
'''

DRIVER = r'''
int main(int argc, char **argv) {
    assert(argc == 7);
    int hif = atoi(argv[1]), active = atoi(argv[2]), through = atoi(argv[3]);
    failure = argv[4]; fail_band = atoi(argv[5]); int seed = atoi(argv[6]);
    static struct airoha_npu npu;
    static u8 eeprom[4096];
    fixture.mt76.mmio.regs = mmio; npu.regmap = regmap;
    fixture.mt76.mmio.npu = active ? &npu : NULL;
    fixture.mt76.eeprom.data = eeprom;
    fixture.hif2 = hif ? &fixture : NULL;
    fixture.mphy.dev = &fixture.mt76; fixture.mphy.priv = &fixture.phy;
    fixture.phy.dev = &fixture; fixture.phy.mt76 = &fixture.mphy;
    fixture.mt76.phys[0] = &fixture.mphy;
    if (seed) { regmap[0x30d0b0/4] = 0xdead0000; regmap[0x30d0b4/4] = 77; }
    fixture_tx_config(&fixture);
    int ret = fixture_primary_tx(&fixture);
    for (band = 1; !ret && band <= through; band++) ret = mt7996_register_phy(&fixture, band);
    int owners[3] = {-1,-1,-1};
    for (int i = 0; i < 3; i++) {
        struct mt76_phy *p = fixture.mt76.phys[i];
        if (!p || !p->q_tx[0]) continue;
        for (int j = 0; j <= i; j++) {
            struct mt76_phy *prior = fixture.mt76.phys[j];
            if (prior && prior->q_tx[0] == p->q_tx[0]) { owners[i] = j; break; }
        }
        for (int j = 0; j <= MT_TXQ_PSD; j++) assert(p->q_tx[j] == p->q_tx[0]);
        assert(p->q_tx[0]->head == 0 && p->q_tx[0]->tail == 0);
    }
    printf("{\"result\":%d,\"owners\":[%d,%d,%d],\"fault_hits\":%d,"
           "\"allocations\":%d,\"tx1\":[%u,%u]}\n", ret, owners[0], owners[1], owners[2],
           hits, alloc_count, regmap[0x30d0b0/4], regmap[0x30d0b4/4]);
    for (unsigned i = 0; i < allocation_count; i++) free(allocations[i]);
    return 0;
}
'''


def build_unit(sources):
    refs, parts = [], [PRELUDE]

    def add(path, text, name, kind):
        source = sources[path]
        assert text in source, name
        refs.append(dict(path=path, name=name, kind=kind,
                         line=source.count('\n', 0, source.index(text)) + 1,
                         sha256=sha(text.encode())))
        parts.append(text)

    for path, names in {
        'mt76.h': ['MT_QFLAG_WED_RING', 'MT_QFLAG_WED_TYPE', 'MT_QFLAG_WED',
                   'MT_QFLAG_WED_RRO', 'MT_QFLAG_WED_RRO_EN', 'MT_QFLAG_EMI_EN',
                   'MT_QFLAG_NPU', '__MT_NPU_Q', 'MT_NPU_Q_TX', '__MT_WED_Q', 'MT_WED_Q_TX'],
        'mt7996/mt7996.h': ['MT7996_TX_RING_SIZE', 'MT7996_NPU_TX_RING_SIZE'],
        'mt7996/regs.h': ['MT_WFDMA0_BASE', 'MT_WFDMA0', 'MT_WFDMA0_PCIE1_BASE',
                         'MT_WFDMA0_PCIE1', 'MT_WFDMA1_BASE', '__RXQ', '__TXQ',
                         'MT_Q_ID', 'MT_Q_BASE', 'MT_TXQ_ID', 'MT_TXQ_RING_BASE'],
        'dma.h': ['MT_RING_SIZE', 'MT_DMA_CTL_DMA_DONE', 'MT_DMA_RRO_EN'],
        'airoha_offload.h': ['NPU_TXWI_LEN'],
    }.items():
        for name in names:
            add(path, macro(sources[path], name), name, 'macro')
    for path, kind, names in (
        ('mt76.h', 'enum', ['mt76_txq_id', 'mt76_mcuq_id', 'mt76_rxq_id',
                           'mt76_band_id', 'mt76_wed_type']),
        ('mt7996/mt7996.h', 'enum', ['mt7996_txq_id']),
        ('mt7996/eeprom.h', 'enum', ['mt7996_eeprom_field']),
        ('mt76.h', 'struct', ['mt76_queue_entry', 'mt76_queue_regs', 'mt76_queue']),
        ('dma.h', 'struct', ['mt76_desc', 'mt76_wed_rro_desc']),
        ('airoha_offload.h', 'struct', ['airoha_npu_tx_dma_desc', 'airoha_npu_rx_dma_desc']),
    ):
        for name in names:
            add(path, declaration(sources[path], kind, name), name, kind)
    parts.append(FRAMEWORK)
    for path, names in (
        ('mt76.h', ['mt76_npu_device_active', 'mt76_queue_is_wed_tx_free', 'mt76_queue_is_wed_rro',
                    'mt76_queue_is_wed_rro_ind', 'mt76_queue_is_wed_rro_rxdmad_c',
                    'mt76_queue_is_emi', 'mt76_queue_is_npu', 'mt76_queue_is_npu_tx',
                    'mt76_queue_is_npu_rx']),
        ('mt7996/mt7996.h', ['mt7996_band_valid']),
        ('dma.h', ['mt76_dma_handle_read', 'mt76_dma_handle_write']),
    ):
        for name in names:
            add(path, function(sources[path], name), name, 'whole_function')
    for name in ('Q_READ', 'Q_WRITE'):
        add('dma.h', macro(sources['dma.h'], name), name, 'macro')
    for path, names in (
        ('npu.c', ['mt76_npu_queue_setup']),
        ('dma.c', ['mt76_dma_read_dma_idx', 'mt76_dma_sync_idx',
                   'mt76_dma_queue_reset', 'mt76_dma_alloc_queue']),
        ('mt7996/dma.c', ['mt7996_init_tx_queues']),
    ):
        for name in names:
            add(path, function(sources[path], name), name, 'whole_function')
    parts.append(BRIDGE)
    add('mt7996/init.c', function(sources['mt7996/init.c'], 'mt7996_register_phy'),
        'mt7996_register_phy', 'whole_function')
    config = sources['mt7996/dma.c'].split('\t/* data tx queue */\n', 1)[1].split('\n\t/* mcu tx queue */', 1)[0]
    parts.append('''
#define WFDMA0 0
#define TXQ_CONFIG(q,wfdma,irq,id) do { assert((wfdma) == 0); dev->q_id[__TXQ(q)] = (id); } while (0)
static void fixture_tx_config(struct mt7996_dev *dev) {
''')
    add('mt7996/dma.c', config, 'mt7996_dma_config:data_tx', 'unchanged_block')
    parts.append('}\nstatic int fixture_primary_tx(struct mt7996_dev *dev) {\n'
                 'struct mtk_wed_device *wed = &dev->mt76.mmio.wed;\n'
                 'u32 hif1_ofs = dev->hif2 ? MT_WFDMA0_PCIE1(0) - MT_WFDMA0(0) : 0;\nint ret;\n')
    primary = sources['mt7996/dma.c'].split('\t/* init tx queue */\n', 1)[1].split('\n\t/* command to WM */', 1)[0]
    add('mt7996/dma.c', primary, 'mt7996_dma_init:primary_tx', 'unchanged_block')
    parts.append('return 0;\n}\n')
    parts.append('_Static_assert(sizeof(struct airoha_npu_tx_dma_desc) == 208, "TX stride");\n'
                 '_Static_assert(sizeof(struct mt76_desc) == 16, "DMA stride");\n'
                 '_Static_assert(sizeof(struct mt76_queue_regs) == 16, "register stride");\n')
    parts.append(DRIVER)
    boundaries = []
    for path, name in [('mt76_connac_mac.c', 'mt76_connac_init_tx_queues'),
                       ('mac80211.c', 'mt76_init_queue'), ('mt76.h', 'mt76_init_tx_queue'),
                       ('mac80211.c', 'mt76_create_page_pool'),
                       ('dma.c', 'mt76_dma_queue_magic_cnt_init')]:
        body = function(sources[path], name)
        boundaries.append(dict(path=path, name=name, sha256=sha(body.encode()),
                               line=sources[path].count('\n', 0, sources[path].index(body)) + 1,
                               execution='modeled boundary, not extracted execution'))
    return '\n\n'.join(parts), refs, boundaries


def compile_unit(unit, name):
    source, binary = SCRATCH / (name + '.c'), SCRATCH / name
    source.write_text(unit)
    command = ['gcc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-Wno-sign-compare', '-fsanitize=undefined', '-fno-sanitize-recover=all',
               '-o', str(binary), str(source)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return binary, command


def execute(binary, hif, active, through=2, failure='none', fail_band=-1, seed=0):
    args = [str(binary), str(hif), str(active), str(through), failure, str(fail_band), str(seed)]
    result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=5)
    assert not result.stderr, result.stderr
    records = [json.loads(line) for line in result.stdout.splitlines()]
    category = ('counterfactual_boundary_return' if failure in ('page_pool', 'wed_setup')
                else 'modeled_framework_failure' if failure != 'none'
                else 'preseeded_storage_control' if seed else 'success_path')
    return dict(hif2=bool(hif), npu_active=bool(active), through_band=through,
                failure=failure, fail_band=fail_band, seeded_tx1=bool(seed),
                category=category, events=records[:-1], summary=records[-1])


def verify(trace):
    hif, active, through = trace['hif2'], trace['npu_active'], trace['through_band']
    events, result = trace['events'], trace['summary']
    assert result['result'] == 0 and result['fault_hits'] == 0
    owners = [0, 1 if hif else 0, (1 if hif else 0) if active else 2]
    assert result['owners'] == [owners[i] if i <= through else -1 for i in range(3)]
    bands = [i for i in range(through + 1) if owners[i] == i]
    assert result['allocations'] == len(bands)
    expected_writes = []
    for index, b in enumerate(bands):
        count = (1024 if b == 0 else 512) if active else 2048
        hw_idx = ([21, 18, 19] if hif and active else [18, 19, 21] if hif else [18, 0, 19])[b]
        hif_offset = 0x4000 if hif and ((active and b == 0) or (not active and b == 2)) else 0
        mmio_base = 0xd4300 + hif_offset + hw_idx * 16
        dma = 0x20000000 + index * 0x100000
        alloc = [e for e in events if e['op'] == 'descriptor_allocation' and e['band'] == b]
        assert [(e['address'], e['value']) for e in alloc] == [(dma, count * (208 if active else 16))]
        request = [e for e in events if e['op'] == 'framework_queue_request' and e['band'] == b]
        assert [(e['address'], e['value']) for e in request] == [(mmio_base, count)]
        route, base = ('regmap_write', 0x30d0a0 + b * 16) if active else ('mmio_write', mmio_base)
        writes = [(route, base + 8, 0), (route, base + 12, 0), (route, base + 4, count)]
        if active:
            writes += [('mmio_write', mmio_base + 4, count), ('mmio_write', mmio_base, dma)]
        writes += [(route, base, dma)]
        expected_writes += [(b, *w) for w in writes]
    actual = [(e['band'], e['op'], e['address'], e['value']) for e in events if e['op'].endswith('_write')]
    assert actual == expected_writes, (actual, expected_writes)
    tx1 = [e for e in events if e['op'] == 'regmap_write' and e['address'] in (0x30d0b0, 0x30d0b4)]
    assert len(tx1) == (2 if hif and active and through >= 1 else 0)
    expected_tx1 = [0x20100000, 512] if tx1 else [0xdead0000, 77] if trace['seeded_tx1'] else [0, 0]
    assert result['tx1'] == expected_tx1


def main():
    sources = load_sources()
    unit, refs, boundaries = build_unit(sources)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    binary, command = compile_unit(unit, 'host-queues')
    valid, controls = [], []
    for hif in (0, 1):
        for active in (0, 1):
            for through in (0, 1, 2):
                trace = execute(binary, hif, active, through)
                verify(trace)
                valid.append(trace)
            trace = execute(binary, hif, active, seed=1)
            verify(trace)
            controls.append(trace)
            baseline = valid[-1]
            allocating_bands = sorted({e['band'] for e in baseline['events'] if e['op'] == 'descriptor_allocation'})
            for point in ('queue', 'descriptor', 'entry', 'page_pool', 'wed_setup'):
                for b in allocating_bands:
                    trace = execute(binary, hif, active, failure=point, fail_band=b)
                    assert trace['summary']['result'] == (-EIO if point == 'wed_setup' else -ENOMEM)
                    assert trace['summary']['fault_hits'] == 1
                    assert not any(e['band'] >= b and e['op'].endswith('_write') for e in trace['events'])
                    controls.append(trace)
            for point in ('phy', 'eeprom_cap', 'override', 'registration'):
                trace = execute(binary, hif, active, failure=point, fail_band=1)
                assert trace['summary']['result'] == (-ENOMEM if point == 'phy' else -EIO)
                assert trace['summary']['fault_hits'] == 1
                assert trace['summary']['owners'][1:] == [-1, -1]
                # Framework registration fails after queue publication on DUAL-HIF.
                writes = [e for e in trace['events'] if e['band'] >= 1 and e['op'].endswith('_write')]
                assert bool(writes) == (point == 'registration' and bool(hif))
                controls.append(trace)
    mutants = []
    sync = function(sources['dma.c'], 'mt76_dma_sync_idx')
    early_base = sync.replace('\tQ_WRITE(q, desc_base, q->desc_dma);\n', '').replace(
        '{\n', '{\n\tQ_WRITE(q, desc_base, q->desc_dma);\n', 1)
    for name, old, new, case in (
        ('drop_base', 'Q_WRITE(q, desc_base, q->desc_dma);', '(void)q->desc_dma;', (1, 1)),
        ('wrong_npu_qid', 'MT_NPU_Q_TX(phy->mt76->band_idx)', 'MT_NPU_Q_TX(0)', (1, 1)),
        ('single_hif_allocates', '(band == MT_BAND1 && !dev->hif2)', '(band == MT_BAND1 && false)', (0, 1)),
        ('base_before_size', sync, early_base, (1, 1)),
    ):
        assert unit.count(old) == 1
        mutant, _ = compile_unit(unit.replace(old, new), name)
        trace = execute(mutant, *case)
        try:
            verify(trace)
        except AssertionError:
            mutants.append(dict(name=name, killed=True, source_sha256=sha(unit.replace(old, new).encode())))
        else:
            raise AssertionError('surviving mutant: ' + name)
    # Detect concurrent drift of every input used, without reading other lanes.
    assert load_sources() == sources
    result = dict(schema=1, pin=PIN, requested_base=BASE, archive_sha256=ARCHIVE_SHA,
                  counts=dict(valid_traces=len(valid), controls=len(controls), mutants_killed=len(mutants),
                              whole_extracted_functions=sum(ref['kind'] == 'whole_function' for ref in refs),
                              unchanged_tx_blocks=sum(ref['kind'] == 'unchanged_block' for ref in refs),
                              counterfactual_controls=sum(t['category'] == 'counterfactual_boundary_return' for t in controls)),
                  source_dependencies=[dict(path=name, sha256=sha(text.encode()),
                      snapshot_compared=(SNAPSHOT / name).exists()) for name, text in sources.items()],
                  extracted=refs, modeled_framework_bridge=boundaries,
                  harness_sha256=sha(unit.encode()), binary_sha256=sha(binary.read_bytes()),
                  test_sha256=sha(Path(__file__).read_bytes()), compiler_command=command,
                  compiler=subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
                  valid=valid, controls=controls, mutants=mutants,
                  conclusions=dict(single_hif_active='Only TX0 allocated; band1 and band2 alias band0. No TX1 writes.',
                      dual_hif_active='TX0 1024x208, TX1 512x208; band2 aliases band1.',
                      inactive='No NPU regmap writes. Physical DMA uses 2048x16 per allocated queue.',
                      readiness='Publication is not readiness; framework registration failure can follow publication.',
                      next_action='Resolve SINGLE-HIF host TX1 ownership/allocation/publication contract before treating the independently supplied boot prerequisite as satisfied. TX configuration does not assign band1 q_id in SINGLE-HIF; merely removing its alias would select zero-initialized physical queue ID 0. No production fix selected.'),
                  parent_context=dict(provenance='User supplied read-only live context; not revalidated by this test.',
                      baseline='R1 has no configured wifi-iface/wifi-mld and no hostapd interfaces; no client failure reproduced.',
                      pci_bindings=['mt7996e:0000:01:00.0', 'mt7996e_hif:0002:01:00.0'],
                      pairing='Both bindings do not prove internal dev->hif2 pairing. SINGLE-HIF evidence is not a current live-device root cause.'),
                  limits=['Host C only; no native firmware, emulator, Ghidra, device or network execution.',
                      'WED inactive, MT7996 only, serialized storage/RCU and coherent-allocation models.',
                      'Complete selected functions retain original bytes; two TX-only source blocks have fixture entrypoints.',
                      'Framework bridge models three pinned helpers; their actual implementations do not execute.',
                      'Page-pool and WED setup error returns are explicitly counterfactual propagation controls: ordinary TX/WED-inactive boundaries return zero. They are not reachable-failure findings.',
                      'Provider queue-address formula 0x30d000+0x80+((qid+2)<<4) and NPU physical base 0x1e900000 are supplied prior-evidence assumptions, not revalidated provider execution.',
                      'No full register_device/dma_init, RX fill, packet, mailbox, native prerequisite, cache or concurrency proof.',
                      'No production patch; parent-owned docs, canonical ledger and live Wi-Fi files not modified by this task.'])
    OUT.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(counts=result['counts'], harness_sha256=result['harness_sha256'],
                          binary_sha256=result['binary_sha256'], evidence_sha256=sha(OUT.read_bytes()))))


ENOMEM, EIO = 12, 5

if __name__ == '__main__':
    main()
