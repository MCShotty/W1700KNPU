#!/usr/bin/env python3
"""Selected actual NPU detach C; verify newly added controls remain opt-in."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess

import test_rro_reset_ba_events as ba
from test_host_queue_publication import function

ROOT = ba.ROOT
TEMPLATE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#define BIT(n) (1UL << (n))
#define CHECK(ok, message) do { if (!(ok)) { fputs(message "\n", stderr); abort(); } } while (0)
/* TYPES */
struct airoha_npu { int unused; };
struct airoha_ppe_dev { int unused; };
struct driver { unsigned long drv_flags; };
struct mt76_dev {
    struct driver *drv;
    int mutex, *dev;
    struct { struct airoha_npu *npu; struct airoha_ppe_dev *ppe_dev; } mmio;
    int q_rx[__MT_RXQ_MAX];
};
static struct mt76_dev device;
static struct driver driver;
static struct airoha_npu npu;
static struct airoha_ppe_dev ppe;
static unsigned int irq_closes, napi_joins, provider_closes, npu_puts, ppe_puts, grace, buffers;
static int close_error;
static void mutex_lock(int *m) { assert(m == &device.mutex && !*m); *m = 1; }
static void mutex_unlock(int *m) { assert(m == &device.mutex && *m == 1); *m = 0; }
#define lockdep_is_held(m) (*(m) == 1)
#define rcu_dereference_protected(p, c) (assert(c), (p))
#define rcu_replace_pointer(p, value, held) ({ assert(held); __auto_type old = (p); (p) = (value); old; })
static void mt76_npu_shutdown_irqs(struct mt76_dev *d) {
    CHECK(d == &device && (d->drv->drv_flags & MT_DRV_NAPI_LIFETIME), "new-CPU-controls-require-driver-opt-in");
    CHECK(!d->mutex, "CPU-IRQ-close-outside-device-mutex"); irq_closes++;
}
static void mt76_napi_cleanup(struct mt76_dev *d) {
    CHECK(d == &device && (d->drv->drv_flags & MT_DRV_NAPI_LIFETIME), "new-CPU-controls-require-driver-opt-in");
    CHECK(!d->mutex && irq_closes == napi_joins + 1, "IRQ-close-before-NAPI-join"); napi_joins++;
}
static int airoha_npu_wlan_rro_close(struct airoha_npu *p, int *endpoint) {
    assert(device.mutex && p == &npu && endpoint == device.dev); provider_closes++; return close_error;
}
static void synchronize_rcu(void) {
    assert(device.mutex && !device.mmio.npu && !device.mmio.ppe_dev); grace++;
}
static void mt76_npu_queue_cleanup(struct mt76_dev *d, int *q) {
    assert(d == &device && !d->mutex && !d->mmio.npu && !d->mmio.ppe_dev);
    assert(q == &d->q_rx[MT_RXQ_NPU0] || q == &d->q_rx[MT_RXQ_NPU1]); buffers++;
}
static void airoha_npu_put(struct airoha_npu *p) { assert(p == &npu && !device.mutex); npu_puts++; }
static void airoha_ppe_put_dev(struct airoha_ppe_dev *p) { assert(p == &ppe && !device.mutex); ppe_puts++; }
/* ACTUAL */
int main(void) {
    unsigned int cases = 0;
    for (unsigned int tracked = 0; tracked < 2; tracked++)
    for (unsigned int present = 0; present < 4; present++)
    for (unsigned int failed = 0; failed < 2; failed++) {
        device = (struct mt76_dev){0};
        driver.drv_flags = tracked ? MT_DRV_NAPI_LIFETIME : 0;
        device.drv = &driver; device.dev = &device.mutex;
        device.mmio.npu = present & 1 ? &npu : NULL;
        device.mmio.ppe_dev = present & 2 ? &ppe : NULL;
        irq_closes = napi_joins = provider_closes = npu_puts = ppe_puts = grace = buffers = 0;
        close_error = failed ? -5 : 0;
        mt76_npu_deinit(&device); mt76_npu_deinit(&device);
        CHECK(irq_closes == 2 * tracked && napi_joins == 2 * tracked, "opted-in-detach-must-close-new-CPU-controls");
        assert(provider_closes == !!(present & 1) && npu_puts == !!(present & 1) && ppe_puts == !!(present & 2));
        assert(grace == !!present && buffers == 4 && !device.mutex && !device.mmio.npu && !device.mmio.ppe_dev);
        cases++;
    }
    printf("{\"passed\":true,\"cases\":%u,\"kernel_concurrency\":false,\"hardware\":false}\n", cases);
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    output = ROOT / '.local/npu-deinit-scope-20261024' / args.name
    output.mkdir(parents=True, exist_ok=False)
    source, header = args.source_root / 'npu.c', args.source_root / 'mt76.h'
    inputs = {str(p.resolve()): ba.sha(p) for p in (source, header, Path(__file__), Path(ba.__file__))}
    text = header.read_text()
    types = ba.braced(text, text.index('enum mt76_rxq_id {'), True) + '\n' + ba.macro(text, 'MT_DRV_NAPI_LIFETIME')
    body = function(source.read_text(), 'mt76_npu_deinit')
    guard = '\tif (dev->drv->drv_flags & MT_DRV_NAPI_LIFETIME) {'
    assert body.count(guard) == 1
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    variants = [('actual', body, None),
        ('untracked-driver-shutdown', ba.once(body, guard, '\tif (true) {', 'guard'), 'new-CPU-controls-require-driver-opt-in'),
        ('tracked-driver-not-shutdown', ba.once(body, guard, '\tif (false) {', 'guard'), 'opted-in-detach-must-close-new-CPU-controls')]
    controls = []
    for name, chosen, assertion in variants:
        c, binary = output / (name + '.c'), output / name
        c.write_text(TEMPLATE.replace('/* TYPES */', types).replace('/* ACTUAL */', chosen))
        command = [shutil.which('clang') or shutil.which('gcc'), '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra',
            '-Werror', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', str(c), '-o', str(binary)]
        built = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (output / (name + '.build.log')).write_text(built.stdout + built.stderr)
        assert built.returncode == 0, built.stderr
        result = subprocess.run([str(binary)], capture_output=True, text=True, env=environment,
            timeout=120, preexec_fn=ba.no_core_dump)
        (output / (name + '.run.log')).write_text(result.stdout + result.stderr)
        if assertion:
            assert result.returncode == -signal.SIGABRT and assertion in result.stderr
            assert 'AddressSanitizer' not in result.stderr and 'runtime error:' not in result.stderr
            controls.append(dict(name=name, compiled=True, intended_assertion=assertion, returncode=result.returncode))
        else:
            assert result.returncode == 0, result.stderr
            assert json.loads(result.stdout)['cases'] == 16
    assert all(ba.sha(Path(p)) == value for p, value in inputs.items())
    row = dict(passed=True, cases=16, mutation_controls=controls, inputs_sha256=inputs,
        selected_body_sha256=hashlib.sha256(body.encode()).hexdigest(),
        artifacts_sha256={p.name: ba.sha(p) for p in output.iterdir() if p.is_file()},
        actual_selected_NPU_deinit_C=True, new_CPU_controls_modeled=True,
        kernel_concurrency=False, physical_drain=False, hardware=False)
    (output / 'result.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=16, controls=2, receipt=str(output / 'result.json'))), flush=True)


if __name__ == '__main__':
    main()
