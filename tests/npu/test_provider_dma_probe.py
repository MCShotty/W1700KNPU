#!/usr/bin/env python3
"""Current actual probe/IRQ/work/lease C with modeled kernel dependencies."""
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


def c_function(source, name):
    # Extend the existing extractor's return-type vocabulary without changing bytes.
    masked = source.replace('irqreturn_t', 'int        ')
    fragment = loader.extract.function(masked, name)
    start = masked.index(fragment)
    return source[start:start + len(fragment)]


def model_harness(original):
    once = loader.once
    text = once(original, 'struct device { void *of_node; };',
                'struct device { void *of_node; unsigned refs; };')
    text = once(text, '#include "types.inc"', '''struct list_head { struct list_head *next, *prev; };
#define LIST_HEAD(name) struct list_head name = {&name, &name}
#define DEFINE_MUTEX(name) int name
#define THIS_MODULE NULL
#define dev_warn(...) ((void)0)
#define list_for_each_entry(pos, head, member) \\
    for (struct list_head *node = (head)->next; \\
         node != (head) && ((pos) = container_of(node, __typeof__(*(pos)), member), 1); \\
         node = node->next)
#include "types.inc"''')
    text = once(text, 'WORK_RESOURCE, DMA_RESOURCE', 'WORK_RESOURCE, DMA_RESOURCE, LEASE_RESOURCE')
    text = once(text, '''    if (!m->alive || !private_alive)
        dead_access++;
    return 0;''', '''    if (!m->alive || !private_alive)
        dead_access++;
    bool boot = reg == REG_CR_BOOT_TRIGGER || reg == REG_CR_BOOT_CONFIG ||
        (reg >= REG_CR_BOOT_BASE(0) && reg <= REG_CR_BOOT_BASE(7)) ||
        reg == REG_CR_NPU_MIB(10) || reg == REG_CR_NPU_MIB(11) ||
        reg == REG_CR_NPU_MIB(12) || reg == REG_CR_NPU_MIB(21);
    return boot && fail() ? -EIO : 0;''')
    text = once(text, 'static int model_firmware(void) { return fail() ? -EINVAL : 0; }', '''
static struct airoha_npu_dma_lifetime *life_model;
static unsigned bare_allocated, bare_freed, lease_freed, module_pins;
static void mutex_lock(int *lock) { check(!*lock); *lock = 1; }
static void mutex_unlock(int *lock) { check(*lock); *lock = 0; }
#ifdef NPU_TEST_SESSION_TYPES
static void mutex_init(struct mutex *lock) { lock->opaque = 0; }
#endif
static void list_add_tail(struct list_head *node, struct list_head *head) {
    node->prev = head->prev; node->next = head;
    head->prev->next = node; head->prev = node;
}
static void __module_get(void *module) { (void)module; module_pins++; }
static struct device *get_device(struct device *dev) { dev->refs++; return dev; }
static void put_device(struct device *dev) { check(dev->refs > 1); dev->refs--; }
static void *kzalloc(size_t bytes, gfp_t flags) {
    if (fail()) return NULL;
    check(bytes == sizeof(*life_model) && !life_model);
    life_model = calloc(1, bytes); check(life_model != NULL); return life_model;
}
static void kfree(void *value) { check(value == life_model); free(value); life_model = NULL; lease_freed++; }
static int dev_err_probe(struct device *dev, int error, const char *message) { return error; }
static int devm_add_action_or_reset(struct device *dev, void (*action)(void *), void *value) {
    if (fail()) { action(value); return -ENOMEM; }
    add(LEASE_RESOURCE, value, action); return 0;
}
static int dma_set_mask_and_coherent(struct device *dev, u64 mask) { return fail() ? -EIO : 0; }
static void *dma_alloc_coherent(struct device *dev, size_t bytes, dma_addr_t *address, gfp_t flags) {
    if (fail()) return NULL;
    check(bytes == AIROHA_NPU_MBOX_SIZE);
    void *buf = calloc(1, bytes); check(buf != NULL);
    *address = 0x83000000 + 256 * bare_allocated++; return buf;
}
static void dma_free_coherent(struct device *dev, size_t bytes, void *buf, dma_addr_t address) {
    for (unsigned i = 0; i < ARRAY_SIZE(irqs); i++) check(!irqs[i].active);
    for (unsigned i = 0; i < NPU_NUM_CORES; i++)
        check(!allocation->npu.cores[i].wdt_work.pending && !allocation->npu.cores[i].wdt_work.running);
    check(bytes == AIROHA_NPU_MBOX_SIZE && address >= 0x83000000);
    bare_freed++; free(buf);
}''')
    text = once(text, 'case WORK_RESOURCE:\n', 'case LEASE_RESOURCE:\n        case WORK_RESOURCE:\n')
    text = once(text, 'struct platform_device pdev = {0};', 'struct platform_device pdev = {0};\n    pdev.dev.refs = 1;')
    text = once(text, '        check(ret < 0 && pdev.data == NULL);',
                '        assert(ret < 0 && pdev.data == NULL && "probe-error-not-published");')
    text = once(text, 'allocation = NULL;\n    map.alive',
                'allocation = NULL;\n    bare_allocated = bare_freed = lease_freed = module_pins = 0;\n    check(!life_model);\n    map.alive')
    text = once(text, '    release_resources();', '''    bool exposed = life_model && life_model->exposed;
    release_resources();
    if (exposed) {
        check(life_model && pdev.dev.refs == 2 && !bare_freed && !lease_freed && module_pins == 1);
        check(airoha_npu_dma_retained(&pdev.dev));
        unsigned old_operation = operation;
        struct airoha_npu_priv *old_allocation = allocation;
        bool old_private_alive = private_alive;
        int old_requested = requested, old_freed = freed;
        fail_at = 0;
        check(airoha_npu_probe(&pdev) == -EBUSY);
        check(bare_allocated == 8 && !bare_freed && module_pins == 1);
        release_resources();
        free(allocation); allocation = old_allocation;
        private_alive = old_private_alive; operation = old_operation;
        requested = old_requested; freed = old_freed;
        /* Fixture-only retirement, not an implementation or physical witness. */
        life_model->retained.prev->next = life_model->retained.next;
        life_model->retained.next->prev = life_model->retained.prev;
        for (unsigned i = 0; i < 8; i++) free(life_model->buffers[i].buf);
        free(life_model); life_model = NULL;
    } else {
        check(!life_model && pdev.dev.refs == 1 && bare_freed == bare_allocated && !module_pins);
    }''')
    # Reprobe has a fresh managed private allocation; reset CPU producer counters.
    text = once(text, '        fail_at = 0;\n        check(airoha_npu_probe',
                '        fail_at = 0;\n        requested = freed = 0;\n        check(airoha_npu_probe')
    text = once(text, r'\"executed_work\":%d}',
                r'\"executed_work\":%d,\"exposed\":%s,\"dma_allocated\":%u,\"dma_freed\":%u,\"module_pins\":%u}')
    text = once(text, 'requested, canceled, work_ran);',
                'requested, canceled, work_ran, exposed ? "true" : "false", bare_allocated, bare_freed, module_pins);')
    return text


def fragments(source, header, helper, directory):
    q = loader.extract
    macros = ('AIROHA_NPU_MBOX_SIZE', 'NPU_DUMP_SIZE', 'NPU_EN7581_FIRMWARE_RV32_MAX_SIZE',
              'NPU_SRAM_BACKUP_SIZE', 'NPU_CLUSTER_BASE_ADDR', 'REG_CR_BOOT_TRIGGER',
              'REG_CR_BOOT_CONFIG', 'REG_CR_BOOT_BASE', 'NPU_MBOX_BASE_ADDR',
              'REG_CR_MBOX_INT_STATUS', 'MBOX_INT_STATUS_MASK', 'REG_CR_MBQ8_CTRL',
              'REG_CR_NPU_MIB', 'REG_PC_DBG', 'NPU_TIMER_BASE_ADDR', 'REG_WDT_TIMER_CTRL',
              'WDT_EN_MASK', 'WDT_INTR_MASK', 'MBOX_MSG_STATUS', 'MBOX_MSG_DONE',
              'NPU_EN7581_7996_PLAN_REGIONS')
    if 'static int airoha_npu_start_firmware(' in source:
        macros += ('NPU_EN7581_NATIVE_VERSION',)
    (directory / 'constants.inc').write_text('\n'.join(q.macro(source, name) for name in macros) + '\n')
    types = [loader.unused_session_types(source)] + [q.declaration(header, 'enum', name) for name in ('airoha_npu_wlan_set_cmd', 'airoha_npu_wlan_get_cmd')]
    types += [q.declaration(header, 'struct', 'airoha_npu')]
    types += [q.declaration(source, 'struct', name) for name in ('airoha_npu_dma_lifetime', 'airoha_npu_priv')]
    (directory / 'types.inc').write_text('\n'.join(types) + '\n')
    parts = ['static LIST_HEAD(airoha_npu_retained_dma);\nstatic DEFINE_MUTEX(airoha_npu_retained_lock);']
    if 'struct npu_linux_control wlan_control;' in source:
        parts.append('static void airoha_npu_wlan_session_close(void *data) { (void)data; }')
    parts += [c_function(source, name) for name in ('airoha_npu_dma_retained', 'airoha_npu_dma_cleanup',
              'airoha_npu_firmware_expose', 'airoha_npu_mbox_handler', 'airoha_npu_wdt_work', 'airoha_npu_wdt_handler')]
    parts += [q.function(helper, name) for name in ('devm_work_drop', 'devm_work_autocancel')]
    probe = q.function(source, 'airoha_npu_probe')
    for name in re.findall(r'npu->ops\.\w+ = (\w+);', probe):
        signature = q.function(source, name).split('{', 1)[0]
        if name == 'airoha_npu_wlan_msg_get':
            parts.append(signature + '''{
    check(ifindex == 0 && func_id == WLAN_FUNC_GET_WAIT_NPU_VERSION && data_len == 4);
    if (fail()) return -EIO;
    *(u32 *)data = 0x457;
    return 0;
}''')
        else:
            parts.append(signature + '{ ' + ('' if re.match(r'(?:static\s+)?void\s', signature) else 'return 0; ') + '}')
    if 'static int airoha_npu_start_firmware(' in source:
        parts.append(q.function(source, 'airoha_npu_start_firmware'))
    parts += ['''static int airoha_npu_run_firmware(struct airoha_npu_priv *priv, void *base, struct resource *res)
{
    if (fail()) return -EINVAL;
    int ret = airoha_npu_firmware_expose(priv);
    if (ret) return ret;
    if (fail()) return -EIO;
    priv->firmware_loaded = true;
    priv->checked_pair = true;
    priv->native_published = true;
    priv->boot_identity = 1;
    return 0;
}''', probe, 'static void model_remove(struct platform_device *pdev) { (void)pdev; }']
    (directory / 'driver.inc').write_text('\n\n'.join(parts) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--baseline-source', type=Path,
                        help='Optional pre-correction source for an original launch-failure control')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    source = args.source.resolve()
    kernel = source.parents[4]
    header = kernel / 'include/linux/soc/airoha/airoha_offload.h'
    helper = kernel / 'include/linux/devm-helpers.h'
    base_harness = ROOT / 'tests/npu/provider-lifetime-harness.c'
    dest = ROOT / '.local/npu-loader-publish-20261010' / args.name
    assert source.is_relative_to(ROOT) and not dest.exists()
    dest.mkdir(parents=True)
    inputs = {str(p.relative_to(ROOT)): loader.sha(p) for p in
              (source, header, helper, base_harness, Path(__file__), Path(loader.__file__), Path(loader.extract.__file__))}
    text = source.read_text()
    variants = [('nominal', text, 0),
                ('free-exposed-mailboxes', loader.once(text, 'if (life->exposed) {', 'if (false) {'), -6),
                ('allow-retained-reprobe', loader.once(text, 'retained = true;', 'retained = false;'), -6)]
    if 'static int airoha_npu_start_firmware(' in text:
        old = '\terr = airoha_npu_start_firmware(priv, &res);\n\tif (err)\n\t\treturn err;'
        variants.append(('ignore-launch-error', loader.once(text, old, '\terr = airoha_npu_start_firmware(priv, &res);\n\t(void)err;'), -6))
    if args.baseline_source:
        baseline = args.baseline_source.resolve()
        assert baseline.is_relative_to(ROOT)
        inputs[str(baseline.relative_to(ROOT))] = loader.sha(baseline)
        variants.append(('original-launch-control', baseline.read_text(), -6))
    rows = []
    for name, contents, expected in variants:
        directory = dest / name
        directory.mkdir()
        fragments(contents, header.read_text(), helper.read_text(), directory)
        harness = directory / 'model.c'
        harness.write_text(model_harness(base_harness.read_text()))
        binary = directory / 'test'
        loader.run([shutil.which('gcc'), '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-sign-compare',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-I' + str(directory),
                    harness, '-o', binary], directory / 'build.log')
        done = loader.run([binary, 'after'], directory / 'run.log', accepted=expected,
                          env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1'))
        if name in ('ignore-launch-error', 'original-launch-control'):
            assert 'probe-error-not-published' in done.stderr and 'AddressSanitizer' not in done.stderr
        rows.append(dict(name=name, exit_code=done.returncode, binary_sha256=loader.sha(binary)))
        if not expected:
            matrix = json.loads(done.stdout)
    assert all(loader.sha(ROOT / path) == digest for path, digest in inputs.items())
    result = dict(passed=True, cases=len(matrix['cases']), matrix=matrix, variants=rows, inputs=inputs,
                  rejected_mutants=len(rows) - 1 - bool(args.baseline_source),
                  original_controls=int(bool(args.baseline_source)),
                  sanitizers=['address', 'undefined', 'leak'],
                  limits=['Actual current probe,IRQ/work,lease/exposure/cleanup and devm work-helper C; kernel dependencies are modeled.',
                          'Firmware validation/publication is replaced only at its caller boundary to inject pre/post-exposure faults. Session ops/close are modeled here; the separate session runner executes them.',
                          'Fixture retirement is only test teardown; no physical containment,drain,reclaim or hot-rearm implementation is proved.'])
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=result['cases'], mutants=result['rejected_mutants'],
                          original_controls=result['original_controls'])))


if __name__ == '__main__':
    main()
