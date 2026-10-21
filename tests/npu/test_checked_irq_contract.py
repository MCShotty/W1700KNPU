#!/usr/bin/env python3
"""Compile the actual checked IRQ controller with explicit host/IO fault fixtures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
import test_npu_firmware_loader as loader
import test_npu_host_lifetime as lifetime
from test_final_irq_contract import PROVIDER, KHEADER, MHEADER, CALLER, POLL

ROOT = loader.ROOT
CONSUMER = ROOT / '.local/merge-nonoc-20260923/mt76-merged/npu.c'
HARNESS = ROOT / 'tests/npu/checked-irq-harness.c'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(source, name):
    return lifetime.preflight.block(source,
        r'^(?:static\s+(?:inline\s+)?)?(?:bool|int|void|u32|irqreturn_t)\s+' +
        re.escape(name) + r'\([^;{]*?\)\s*\{')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--mutants', action='store_true')
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    output = ROOT / '.local/npu-checked-irq' / args.name
    assert not output.exists()
    output.mkdir(parents=True)
    paths = (PROVIDER, KHEADER, MHEADER, CONSUMER, CALLER, POLL, HARNESS,
        Path(__file__).resolve(), Path(loader.__file__), Path(loader.extract.__file__), Path(lifetime.__file__))
    inputs = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    provider, header, mt76, consumer = [path.read_text() for path in (PROVIDER, KHEADER, MHEADER, CONSUMER)]
    q = loader.extract
    types = '\n'.join(q.declaration(header, 'enum', name) for name in
        ('airoha_npu_wlan_set_cmd', 'airoha_npu_wlan_get_cmd'))
    types += '\n' + q.declaration(header, 'struct', 'airoha_npu')
    types += '\n' + q.declaration(mt76, 'enum', 'mt76_rxq_id')
    types += '\n' + q.declaration(mt76, 'struct', 'mt76_npu_irq')
    constants = '\n'.join(line for text in (provider, header) for line in text.splitlines()
        if line.startswith('#define ') and line.split()[1].split('(')[0] in
        ('NPU_WLAN_BASE_ADDR', 'REG_IRQ_STATUS', 'REG_IRQ_RXDONE', 'NPU_IRQ_RX_MASK',
         'NPU_NUM_CORES', 'NPU_NUM_IRQ', 'NPU_RX0_DESC_NUM', 'NPU_RX1_DESC_NUM'))
    provider_names = ('airoha_npu_wlan_irq_read_checked', 'airoha_npu_wlan_irq_ack_checked',
        'airoha_npu_wlan_irq_update_checked', 'airoha_npu_wlan_irq_arm_checked', 'airoha_npu_wlan_irq_mask_checked')
    wrappers = ('airoha_npu_wlan_irq_supported', 'airoha_npu_wlan_irq_read',
        'airoha_npu_wlan_irq_ack', 'airoha_npu_wlan_irq_arm', 'airoha_npu_wlan_irq_mask')
    consumer_names = ('mt76_npu_io_admit', 'mt76_npu_irq_error', 'mt76_npu_irq_poll_allowed',
        'mt76_npu_irq_fault_locked', 'mt76_npu_irq_block_locked', 'mt76_npu_irq_handler',
        'mt76_npu_rx_queue_init', 'mt76_npu_start_irqs', 'mt76_npu_rearm_irq', 'mt76_npu_disable_irqs')
    bodies = '\n'.join([*[function(provider, name) for name in provider_names],
        *[function(header, name) for name in wrappers], *[function(consumer, name) for name in consumer_names],
        function(CALLER.read_text(), '__mt7996_npu_hw_init'),
        function(POLL.read_text(), 'mt7996_rx_poll_complete')])
    template = HARNESS.read_text()
    for token in ('/* ACTUAL_TYPES */', '/* ACTUAL_BODIES */'):
        assert template.count(token) == 1
    source = template.replace('/* ACTUAL_TYPES */', constants + '\n' + types)
    environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    def execute(contents, name, expected_pass):
        c, binary = output / (name + '.c'), output / name
        c.write_text(source.replace('/* ACTUAL_BODIES */', contents))
        command = [shutil.which('clang'), '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
            '-Wno-unused-parameter', '-Wno-sign-compare', '-fno-omit-frame-pointer',
            '-fsanitize=address,undefined', str(c), '-o', str(binary)]
        loader.run(command, output / (name + '.build.log'))
        result = subprocess.run([str(binary)], capture_output=True, text=True, env=environment,
            timeout=120, preexec_fn=loader.no_core)
        log = output / (name + '.run.log')
        log.write_text(result.stdout + result.stderr)
        if expected_pass:
            assert result.returncode == 0, result.stderr[-5000:]
            record = json.loads(result.stdout)
            assert record['passed'] is True
        else:
            assert result.returncode != 0 and any(value in result.stderr for value in
                ('Assertion', 'AddressSanitizer', 'runtime error:')), result.stderr[-5000:]
            record = dict(rejected=True)
        return record | dict(returncode=result.returncode, source_sha256=sha(c),
            binary_sha256=sha(binary), log_sha256=sha(log))

    actual = execute(bodies, 'actual', True)
    mutants = []
    if args.mutants:
        variants = []

        def mutate(name, original, replacement):
            assert bodies.count(original) == 1, name
            variants.append((name, bodies.replace(original, replacement, 1)))

        fault = function(consumer, 'mt76_npu_irq_fault_locked')
        mutate('missing-fault-depth', fault, fault.replace('disable_irq_nosync(state->line[q]);', '(void)q;'))
        mutate('missing-sticky-error', 'state->error = error < 0 ? error : -EIO;', 'state->error = 0;')
        mutate('accept-mask-readback-mismatch', 'return !!(val & mask) == enabled ? 0 : -EIO;', 'return 0;')
        handler = function(consumer, 'mt76_npu_irq_handler')
        ack = '\terr = airoha_npu_wlan_irq_ack(npu, index, status);\n\tif (err)\n\t\tgoto fault;'
        assert handler.count(ack) == 1
        mutate('schedule-after-ack-error', handler, handler.replace(ack,
            '\terr = airoha_npu_wlan_irq_ack(npu, index, status);\n\t(void)err;'))
        start = function(consumer, 'mt76_npu_start_irqs')
        final = '\tif (state->error)\n\t\terr = state->error;'
        assert start.count(final) == 1
        mutate('lose-late-start-fault', start, start.replace(final, ''))
        mutate('shared-auto-enabled-registration', 'IRQF_NO_AUTOEN, name, q', 'IRQF_SHARED, name, q')
        for name, candidate in variants:
            mutants.append(dict(name=name, **execute(candidate, name, False)))
    assert all(sha(ROOT / name) == expected for name, expected in inputs.items())
    record = dict(passed=True, actual=actual, mutants=mutants, inputs=inputs,
        actual_provider_checked_functions=True, actual_kernel_interface_types=True,
        actual_consumer_controller_handler_registration=True, actual_init_and_poll_callers=True,
        sanitizers=['address', 'undefined', 'leak'], physical_IRQ_or_DMA_contract=False,
        complete_poll_or_TX_packet_lifecycle=False, full_setup=False, hardware=False,
        limits=['Actual selected C bodies/types are compiled;regmap effects/errors,IRQ nesting,RCU,NAPI and setup stages are explicit fixtures.',
            'A host-disable depth prevents a late normal enable from undoing quarantine;disable_nosync is not handler synchronization or DMA drain.',
            'I/O admission rejects new work after fault;already-admitted work and all physical ownership/drain/retirement contracts remain separate.',
            'No complete packet poll/TX/reset-body execution,kernel concurrency,module load,router boot or client acceptance.'])
    (output / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, actual=actual, rejected_mutants=len(mutants),
        result_sha256=sha(output / 'result.json'))), flush=True)


if __name__ == '__main__':
    main()
