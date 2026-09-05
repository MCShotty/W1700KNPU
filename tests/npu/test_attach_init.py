#!/usr/bin/env python3
"""Execute the actual initializer body with allocation/provider fault stubs."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MT76 = ROOT / '.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/mt76-2026.09.01~be5ce791'
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-attach'

PREFIX = r'''
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#define ENOMEM 12
#define GFP_KERNEL 0
#define MT_BAND0 0
#define MT_BAND2 2
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define BUILD_BUG_ON(e) _Static_assert(!(e), "array contract")
typedef uint64_t dma_addr_t;
typedef uint32_t u32;
struct mt76_dev { bool attached, chip7996; void *dma_dev; int mutex; };
struct mt7996_dev { struct mt76_dev mt76; dma_addr_t npu_txd_addr[6]; };
static int allocations, fail_at, initializations, init_error, locks, unlocks, cases;
static size_t allocated_bytes;
static bool mt76_npu_device_active(struct mt76_dev *dev) { return dev->attached; }
static bool is_mt7996(struct mt76_dev *dev) { return dev->chip7996; }
static void *dmam_alloc_coherent(void *dev, size_t size, dma_addr_t *addr, int flags)
{
    (void)dev; (void)flags;
    allocations++;
    if (allocations == fail_at) return NULL;
    allocated_bytes += size;
    *addr = allocations;
    return addr;
}
static void mutex_lock(int *lock) { (void)lock; locks++; }
static void mutex_unlock(int *lock) { (void)lock; unlocks++; }
static int __mt7996_npu_hw_init(struct mt7996_dev *dev)
{
    initializations++;
    return dev->mt76.attached ? init_error : 0;
}
'''
SUFFIX = r'''
static int check(bool chip, bool attached, int fail, int inner_error)
{
    struct mt7996_dev dev = { .mt76 = { .attached=attached, .chip7996=chip } };
    allocations = initializations = locks = unlocks = 0;
    allocated_bytes = 0;
    fail_at = fail;
    init_error = inner_error;
    int result = mt7996_npu_hw_init(&dev);
    int expected_alloc = attached ? (fail ? fail : 6) : 0;
    int expected_init = attached && !fail;
    int expected_result = !attached ? 0 : fail ? -ENOMEM : inner_error;
    size_t expected_bytes = chip ? 1310720 : 2621440;
    if (result != expected_result || allocations != expected_alloc ||
        initializations != expected_init || locks != expected_init ||
        unlocks != expected_init || (!attached && allocated_bytes) ||
        (attached && !fail && allocated_bytes != expected_bytes)) {
        printf("FAIL attached=%d chip7996=%d fail=%d result=%d allocations=%d expected=%d\n",
               attached, chip, fail, result, allocations, expected_alloc);
        return 1;
    }
    cases++;
    return 0;
}
int main(void)
{
    for (int chip = 0; chip <= 1; chip++) {
        if (check(chip, false, 0, 0) || check(chip, false, 1, 0) ||
            check(chip, true, 0, 0) || check(chip, true, 0, -110)) return 1;
        for (int fail = 1; fail <= 6; fail++)
            if (check(chip, true, fail, 0)) return 1;
    }
    printf("PASS cases=%d mt7996_bytes=1310720 mt7992_bytes=2621440\n", cases);
    return 0;
}
'''


def body(path):
    source = path.read_text()
    start = source.index('int mt7996_npu_hw_init(struct mt7996_dev *dev)\n{')
    end = source.index('\nint mt7996_npu_hw_stop(', start)
    return source[start:end]


def compile_and_run(source, name, temp, constants):
    path = temp / (name + '.c')
    path.write_text(PREFIX + constants + source + SUFFIX)
    binary = temp / name
    subprocess.run(['gcc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-Wno-sign-compare', '-Wno-unused-function', str(path), '-o', str(binary)], check=True)
    return subprocess.run([str(binary)], capture_output=True, text=True)


def main():
    source = MT76 / 'mt7996/npu.c'
    header = (MT76 / 'mt7996/mt7996.h').read_text()
    constants = ''
    for name in ['MT7996_TX_RING_SIZE', 'MT7996_NPU_TX_RING_SIZE', 'MT7996_NPU_RX_RING_SIZE']:
        match = re.search(r'^#define\s+' + name + r'\s+(\d+)\s*$', header, re.M)
        if not match:
            raise RuntimeError('Re-audit changed ring constant: ' + name)
        constants += f'#define {name} {match[1]}\n'
    fixed = body(source)
    preimage = ROOT / 'tests/npu/fixtures/mt7996-npu-be5ce791.c'
    original = body(preimage)
    guard = '\tif (!mt76_npu_device_active(&dev->mt76))\n\t\treturn 0;\n\n'
    if fixed.replace(guard, '', 1) != original or guard not in fixed:
        raise RuntimeError('Initializer change exceeds the provider-presence guard')
    with tempfile.TemporaryDirectory(dir=ROOT / '.local/npu-attach') as directory:
        temp = Path(directory)
        good = compile_and_run(fixed, 'fixed', temp, constants)
        bad = compile_and_run(original, 'preimage', temp, constants)
    if good.returncode or 'PASS cases=20' not in good.stdout:
        raise RuntimeError(good.stdout + good.stderr)
    if not bad.returncode or 'FAIL attached=0' not in bad.stdout:
        raise RuntimeError('Unpatched negative control did not reproduce the detached-provider defect')
    report = {'passed': True, 'cases': 20, 'test_type': 'compiled actual C body with fault-injected stubs',
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'preimage_sha256': hashlib.sha256(preimage.read_bytes()).hexdigest(),
              'unpatched_negative_control': bad.stdout.strip(), 'fixed_result': good.stdout.strip(),
              'limits': 'Not kernel runtime, provider concurrency, DMA ownership or recovery certification'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'initializer-tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
