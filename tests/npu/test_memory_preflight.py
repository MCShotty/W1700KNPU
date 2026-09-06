#!/usr/bin/env python3
"""Compile the provider's actual functions with OF/load/mailbox boundary stubs."""
import ctypes
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
KERNEL = ROOT / '.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.44'
SOURCE = KERNEL / 'drivers/net/ethernet/airoha/airoha_npu.c'
OUT = ROOT / 'research/checkpoints/2026-09-06-npu-preflight'
LOCAL = ROOT / '.local/npu-preflight'
PATCH = ROOT / 'firmware/overlay/openwrt/target/linux/airoha/patches-6.18/927-net-airoha-npu-validate-memory-before-wlan.patch'
HEADER = KERNEL / 'include/linux/soc/airoha/airoha_offload.h'
NAMES = ['tx-bufid', 'pkt', 'tx-pkt', 'ba', 'binary']
DEFAULT = [(0x90c00000, 0xe000), (0x8a000000, 0x2c00000),
           (0x8cc00000, 0x4000000), (0x90c0e000, 0x200000), (0x84000000, 0xa00000)]

PREFIX = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
typedef uint16_t u16;
#define __iomem
#define GFP_KERNEL 0
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define upper_32_bits(a) ((uint64_t)(a) >> 32)
#define IS_ALIGNED(a,b) (!((a) & ((b)-1)))
#define container_of(p,t,m) ((t *)((char *)(p) - offsetof(t,m)))
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
struct resource { uint64_t start, end; };
static uint64_t resource_size(const struct resource *r) { return r->end-r->start+1; }
static bool resource_overlaps(const struct resource *a, const struct resource *b) {
    return a->start <= b->end && a->end >= b->start;
}
struct device_node { int unused; };
struct device { struct device_node *of_node; };
struct airoha_npu { struct device *dev; };
static struct device_node node;
static struct device dev = { &node };
static struct resource regions[5];
static const char *names[] = { "tx-bufid", "pkt", "tx-pkt", "ba", "binary" };
static const char *fw_names[2];
static int profile, present, fw_count, ba, lookup_failure, map_failure, load_failure;
static int maps, loads, lookups, sends, fail_send, first_send_lookups, mutate_on_send;
static uint32_t messages[8][3];
static const char *loaded_names[2];
static uintptr_t loaded_addrs[2];
static uint64_t loaded_sizes[2];
static int dev_err_probe(struct device *d, int err, const char *fmt, ...) {
    (void)d; (void)fmt; return err;
}
static int of_property_read_string_array(struct device_node *n, const char *name,
                                         const char **out, size_t count) {
    (void)n; (void)name; (void)count;
    if (fw_count == 2) { out[0] = fw_names[0]; out[1] = fw_names[1]; }
    return fw_count;
}
static void *of_find_property(struct device_node *n, const char *name, void *len) {
    (void)n; (void)name; (void)len; return present ? &node : NULL;
}
static int of_property_match_string(struct device_node *n, const char *p, const char *s) {
    (void)n; (void)p; (void)s; return ba ? 3 : -EINVAL;
}
static int of_reserved_mem_region_to_resource_byname(struct device_node *n,
                                                     const char *name, struct resource *res) {
    (void)n; lookups++;
    for (int i=0; i<5; i++) if (!strcmp(name, names[i])) {
        if (lookup_failure == i) return -ENOENT;
        *res=regions[i]; return 0;
    }
    return -EINVAL;
}
static void *devm_ioremap_resource(struct device *d, struct resource *r) {
    (void)d; (void)r; maps++;
    return map_failure ? (void *)(intptr_t)-EBUSY : (void *)(uintptr_t)0x10000000;
}
static int airoha_npu_load_firmware(struct device *d, void *addr, const char *name,
                                   uint64_t max_size) {
    (void)d; loaded_names[loads] = name; loaded_addrs[loads] = (uintptr_t)addr;
    loaded_sizes[loads] = max_size; loads++;
    return load_failure == loads ? -EIO : 0;
}
'''

MIDDLE = r'''
static struct airoha_npu_priv priv;
static struct airoha_npu_soc_data soc;
static const struct airoha_npu_soc_data *of_device_get_match_data(struct device *d) {
    (void)d; return profile == -1 ? NULL : &soc;
}
static int airoha_npu_wlan_msg_send(struct airoha_npu *n, int index,
                                    enum airoha_npu_wlan_set_cmd cmd,
                                    const void *buf, int len, int flags) {
    (void)n; (void)flags;
    if (len != 4 || sends >= 8) return -E2BIG;
    if (!sends) first_send_lookups = lookups;
    messages[sends][0] = index; messages[sends][1] = cmd;
    memcpy(&messages[sends][2], buf, 4); sends++;
    if (sends == 1 && mutate_on_send) regions[2].start = 0x100000123ULL;
    return sends == fail_send ? -ETIMEDOUT : 0;
}
'''

SUFFIX = r'''
void set_region(int i, uint64_t start, uint64_t end) {
    regions[i].start=start; regions[i].end=end;
}
void set_profile(int p, int has_property, int count) {
    profile=p; present=has_property; fw_count=count;
    fw_names[0] = p == 1 ? NPU_EN7581_7996_FIRMWARE_RV32 :
                  p == 2 ? NPU_AN7583_FIRMWARE_RV32 : NPU_EN7581_FIRMWARE_RV32;
    fw_names[1] = p == 1 ? NPU_EN7581_7996_FIRMWARE_DATA :
                  p == 2 ? NPU_AN7583_FIRMWARE_DATA : NPU_EN7581_FIRMWARE_DATA;
    soc.fw_rv32.name=fw_names[0]; soc.fw_rv32.max_size=NPU_EN7581_FIRMWARE_RV32_MAX_SIZE;
    soc.fw_data.name=fw_names[1]; soc.fw_data.max_size=NPU_EN7581_FIRMWARE_DATA_MAX_SIZE;
}
void reset(void) {
    memset(&priv, 0, sizeof(priv)); priv.npu.dev=&dev;
    memset(messages, 0, sizeof(messages));
    maps=loads=lookups=sends=map_failure=load_failure=fail_send=mutate_on_send=0;
    first_send_lookups=-1; lookup_failure=-1; ba=1;
    set_profile(1,1,2);
}
void options(int has_ba, int missing, int map_error, int load_error, int send_error,
             int mutate) {
    ba=has_ba; lookup_failure=missing; map_failure=map_error; load_failure=load_error;
    fail_send=send_error; mutate_on_send=mutate;
}
int start(void) { return airoha_npu_run_firmware(RUN_ARG, (void *)(uintptr_t)0x20000000, &regions[4]); }
int wlan(void) { return airoha_npu_wlan_init_memory(&priv.npu); }
int metric(int n) {
    int values[] = { maps, loads, lookups, sends, first_send_lookups, priv.txbuf_min_size };
    return values[n];
}
uint32_t message(int n, int field) { return messages[n][field]; }
uint64_t loaded(int n, int field) { return field ? loaded_sizes[n] : loaded_addrs[n]; }
const char *loaded_name(int n) { return loaded_names[n]; }
'''


def block(text, pattern):
    match = re.search(pattern, text, re.M)
    if not match:
        raise RuntimeError('Missing source block: ' + pattern)
    start = match.start()
    brace = text.index('{', match.end() - 1)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def function(text, name):
    return block(text, r'^static (?:bool|int)\s+' + name + r'\([^;]*?\)\n\{')


def build(source, current, name, temp):
    original = 'struct airoha_npu_priv' not in source
    constants = '\n'.join(re.findall(r'^#define NPU_(?:EN7581|AN7583|SRAM_BACKUP)[^\n]+', source, re.M))
    constants += '\n' + re.search(r'^#define REG_NPU_LOCAL_SRAM[^\n]+', source, re.M)[0]
    types = '\n'.join(block(current, r'^struct ' + n + r' \{') + ';' for n in
                      ['airoha_npu_fw', 'airoha_npu_soc_data', 'airoha_npu_priv'])
    types += '\n' + block(HEADER.read_text(), r'^enum airoha_npu_wlan_set_cmd \{') + ';'
    names = ['airoha_npu_load_firmware_from_dts', 'airoha_npu_run_firmware',
             'airoha_npu_wlan_init_memory']
    names.insert(0, 'airoha_npu_wlan_set_reserved_memory' if original else 'airoha_npu_memory_valid')
    functions = '\n\n'.join(function(source, n) for n in names)
    suffix = SUFFIX.replace('RUN_ARG', '&dev' if original else '&priv')
    path = temp / (name + '.c')
    path.write_text(PREFIX + constants + '\n' + types + MIDDLE + functions + suffix)
    so = temp / (name + '.so')
    subprocess.run(['gcc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-function', '-Wno-sign-compare', '-fPIC', '-shared',
                    str(path), '-o', str(so)], check=True)
    lib = ctypes.CDLL(str(so))
    lib.set_region.argtypes = [ctypes.c_int, ctypes.c_uint64, ctypes.c_uint64]
    lib.message.restype = ctypes.c_uint32
    lib.loaded.restype = ctypes.c_uint64
    lib.loaded_name.restype = ctypes.c_char_p
    return lib


def init(lib, profile=1, prop=1):
    lib.reset()
    lib.set_profile(profile, prop, 2)
    for i, (start, size) in enumerate(DEFAULT):
        lib.set_region(i, start, start + size - 1)


def wire(lib):
    return [[lib.message(i, j) for j in range(3)] for i in range(lib.metric(3))]


def metrics(lib):
    return [lib.metric(i) for i in range(6)]


def suite(lib):
    cases = []

    def check(name, condition):
        if not condition:
            raise AssertionError(f'{name}: metrics={metrics(lib)} wire={wire(lib)}')
        cases.append(name)

    def reject(name, expected=-22):
        result = lib.wlan()
        check(name, result == expected and lib.metric(3) == 0)

    for profile, prop, ba in itertools.product([0, 1, 2], [0, 1], [0, 1]):
        init(lib, profile, prop)
        lib.options(ba, -1, 0, 0, 0, 0)
        if profile != 1:
            lib.set_region(0, 0x90c00000, 0x90c067ff)
            lib.set_region(3, 0x90c06800, 0x90e067ff)
        check(f'load profile={profile} property={prop} ba={ba}', lib.start() == 0)
        expected = [[1, 18, 0], [0, 32, 0x90c00000], [0, 8, 0x8a000000],
                    [0, 23, 0x8cc00000]]
        if ba:
            expected.append([0, 7, 0x90c0e000 if profile == 1 else 0x90c06800])
        expected.append([0, 12, 0])
        check(f'wire profile={profile} property={prop} ba={ba}',
              lib.wlan() == 0 and wire(lib) == expected and lib.metric(4) == 3+ba)
        check(f'load-addresses profile={profile} property={prop} ba={ba}',
              [lib.loaded(i, j) for i in range(2) for j in range(2)] ==
              [0x10000000, 0x200000, 0x20000000, 0x10000])

    init(lib)
    reject('uninitialized-provider')
    for region in range(4):
        init(lib)
        assert lib.start() == 0
        lib.options(1, region, 0, 0, 0, 0)
        reject(f'missing-{NAMES[region]}', -2)
    invalid = [(0, 0xff), (0x90000004, 0x90000003), (0x91000001, 0x91000010),
               (0x190c00000, 0x190c0dfff), (0xfffff000, 0x100000fff)]
    for i, bounds in itertools.product(range(4), invalid):
        init(lib)
        assert lib.start() == 0
        lib.set_region(i, *bounds)
        reject(f'invalid-range-{i}-{bounds}')
    for i, bounds in itertools.product(range(4), [(0x70000000, 0x7000ffff),
                                                  (0xbffff000, 0xc0000fff)]):
        init(lib)
        assert lib.start() == 0
        lib.set_region(i, *bounds)
        reject(f'firmware-aperture-{i}-{bounds}', -34)
    for i, j in itertools.combinations(range(4), 2):
        init(lib)
        assert lib.start() == 0
        start, size = DEFAULT[i]
        lib.set_region(j, start, start+size-1)
        reject(f'wlan-overlap-{i}-{j}')
    for i in range(4):
        init(lib)
        assert lib.start() == 0
        lib.set_region(i, 0x84000000, 0x84ffffff)
        reject(f'firmware-overlap-{i}')
    for size in [1, 0x6800, 0xdfff]:
        init(lib)
        assert lib.start() == 0
        lib.set_region(0, 0x90c00000, 0x90c00000+size-1)
        reject(f'undersized-tx-check-{size}')
    init(lib)
    assert lib.start() == 0
    lib.set_region(0, 0x90c00000, 0x90c0e000)
    reject('one-byte-overlap')
    init(lib)
    assert lib.start() == 0
    lib.set_region(0, 0x90c00000, 0x90c0dfff)
    check('adjacent-regions-accepted', lib.wlan() == 0)
    init(lib)
    assert lib.start() == 0
    lib.set_profile(0, 1, 2)
    lib.set_region(0, 0x90c00000, 0x90c067ff)
    reject('loaded-profile-cached')
    init(lib)
    assert lib.start() == 0
    lib.set_region(4, 0x86000000, 0x86ffffff)
    lib.set_region(1, 0x84000000, 0x8400ffff)
    reject('loaded-binary-region-cached')
    init(lib)
    assert lib.start() == 0
    lib.options(1, -1, 0, 0, 0, 1)
    check('addresses-snapshotted-before-send', lib.wlan() == 0 and wire(lib)[3][2] == 0x8cc00000)
    for fail in range(1, 7):
        init(lib)
        assert lib.start() == 0
        lib.options(1, -1, 0, 0, fail, 0)
        check(f'send-failure-{fail}', lib.wlan() == -110 and lib.metric(3) == fail)
    for bounds in invalid + [(0x84000000, 0x8423fffe)]:
        init(lib)
        lib.set_region(4, *bounds)
        check(f'binary-pre-map-{bounds}', lib.start() == -22 and metrics(lib)[:2] == [0, 0])
    init(lib)
    lib.set_region(4, 0x84000000, 0x8423ffff)
    check('binary-exact-minimum', lib.start() == 0 and metrics(lib)[:2] == [1, 2])
    for count in [-22, 0, 1]:
        init(lib)
        lib.set_profile(1, 1, count)
        check(f'bad-property-count-{count}', lib.start() == -22 and lib.metric(1) == 0)
    init(lib, -1)
    check('missing-soc', lib.start() == -22 and metrics(lib)[:2] == [0, 0])
    init(lib)
    lib.options(1, -1, 1, 0, 0, 0)
    check('map-error', lib.start() == -16 and metrics(lib)[:2] == [1, 0])
    for fail, prop in itertools.product([1, 2], [0, 1]):
        init(lib, 1, prop)
        lib.options(1, -1, 0, fail, 0, 0)
        check(f'load-error-{fail}-{prop}', lib.start() == -5 and lib.metric(1) == fail)
    return cases


def original_cases(lib):
    result = {}
    init(lib)
    assert lib.start() == 0
    lib.set_region(0, 0x90c00000, 0x90c067ff)
    result['undersized_tx'] = {'ret': lib.wlan(), 'wire': wire(lib)}
    init(lib)
    assert lib.start() == 0
    lib.options(1, 3, 0, 0, 0, 0)
    result['missing_ba'] = {'ret': lib.wlan(), 'wire': wire(lib)}
    init(lib)
    lib.set_region(4, 0x84000000, 0x84000003)
    result['undersized_binary'] = {'ret': lib.start(), 'maps_loads': metrics(lib)[:2]}
    assert result['undersized_tx']['ret'] == 0 and len(result['undersized_tx']['wire']) == 6
    assert result['missing_ba']['ret'] == -2 and len(result['missing_ba']['wire']) == 4
    assert result['undersized_binary'] == {'ret': 0, 'maps_loads': [1, 2]}
    init(lib)
    assert lib.start() == 0 and lib.wlan() == 0
    result['valid_wire'] = wire(lib)
    return result


def dtb_cases(lib):
    path = OUT / 'dtb-cases.json'
    cases = json.loads(path.read_text())
    results = []
    for case in cases:
        init(lib, 1 if case['firmware_names'] and 'MT7996' in case['firmware_names'][0] else 0,
             int(case['firmware_names'] is not None))
        for i, name in enumerate(NAMES):
            region = case['resources'].get(name)
            if region is not None:
                lib.set_region(i, region['start'], region['end'])
        lib.options(int('ba' in case['resources']), -1, 0, 0, 0, 0)
        assert lib.start() == 0, case['label']
        ret = lib.wlan()
        assert (ret == 0) == case['expected_preflight_accept'], case['label']
        assert ret == 0 or lib.metric(3) == 0, case['label']
        results.append({'label': case['label'], 'dtb_sha256': case['dtb_sha256'],
                        'ret': ret, 'wire': wire(lib)})
    return results


def main():
    LOCAL.mkdir(parents=True, exist_ok=True)
    source = SOURCE.read_text()
    with tempfile.TemporaryDirectory(dir=LOCAL) as directory:
        temp = Path(directory)
        if PATCH.exists():
            before = temp / 'before.c'
            before.write_text(source)
            subprocess.run(['patch', '--silent', '--reverse', str(before), str(PATCH)], check=True)
            original = before.read_text()
        else:
            original = (LOCAL / 'airoha_npu_before.c').read_text()
        good = build(source, source, 'fixed', temp)
        cases = suite(good)
        fixtures = dtb_cases(good)
        preimage = original_cases(build(original, source, 'preimage', temp))
        init(good)
        assert good.start() == 0 and good.wlan() == 0 and wire(good) == preimage['valid_wire']
        mutations = {
            'omit-tx-minimum': ('resource_size(&memory[0].res) < priv->txbuf_min_size', 'false'),
            'omit-overlap': ('resource_overlaps(res,', 'false && resource_overlaps(res,'),
            'omit-upper-bits': ('!upper_32_bits(res->start) && !upper_32_bits(res->end)', 'true'),
            'omit-binary-capacity': ('resource_size(res) < NPU_EN7581_FIRMWARE_RV32_MAX_SIZE + NPU_SRAM_BACKUP_SIZE', 'false'),
            'reread-profile': ('unsigned int i, j, count = ARRAY_SIZE(memory);',
                              'unsigned int i, j, count = ARRAY_SIZE(memory);\n'
                              '\tpriv->txbuf_min_size = strstr(fw_names[0], "MT7996") ? 0xe000 : 0;'),
            'publish-before-validation': ('if (!airoha_npu_memory_valid(&priv->firmware_region))',
                                         'airoha_npu_wlan_msg_send(npu, 1, WLAN_FUNC_SET_WAIT_NPU_BAND0_ONCPU, &val, sizeof(val), GFP_KERNEL);\n'
                                         '\tif (!airoha_npu_memory_valid(&priv->firmware_region))'),
        }
        killed = {}
        for name, (old, new) in mutations.items():
            assert old in source, name
            mutant = build(source.replace(old, new), source, name, temp)
            try:
                suite(mutant)
            except AssertionError as error:
                killed[name] = str(error)
            else:
                raise RuntimeError('Mutation survived: ' + name)
    result = {'passed': True, 'type': 'compiled actual provider C functions; stubbed OF/load/mailbox boundaries',
              'cases': len(cases), 'case_names': cases, 'dtb_cases': fixtures,
              'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'preimage_sha256': hashlib.sha256(original.encode()).hexdigest(),
              'header_sha256': hashlib.sha256(HEADER.read_bytes()).hexdigest(),
              'mutations_killed': killed, 'preimage_counterexamples': preimage,
              'limits': 'Not kernel runtime, hardware containment/drain, firmware content attestation, hot DT overlay safety, or actual-client proof.'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'compiled-c-tests.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['passed', 'cases', 'source_sha256']}))
    print(f'DTB cases={len(fixtures)} mutations killed={len(killed)} preimage counterexamples=3')


if __name__ == '__main__':
    main()
