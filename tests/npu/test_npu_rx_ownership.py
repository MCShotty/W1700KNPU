#!/usr/bin/env python3
"""NPU RX buffer ownership through actual dequeue, poll, refill and cleanup C."""
import argparse
import difflib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
from elftools.elf.elffile import ELFFile
import test_npu_host_lifetime as lifetime

ROOT, KERNEL = lifetime.ROOT, lifetime.KERNEL
BUILD = ROOT / '.local/npu-rx-ownership'
OUT = ROOT / 'research/checkpoints/2026-09-16-npu-rx-ownership'
PREDECESSOR = lifetime.OUT / 'host-lifetime.json'
MT76 = lifetime.BUILD / 'kernel-mt76-after-1/mt76-2026.09.01~be5ce791'
SOURCE = MT76 / 'npu.c'
FRAGMENT = OUT / 'mt76-npu-dequeue.c'
HARNESS = ROOT / 'tests/npu/npu-rx-ownership-harness.c'
PATCH = OUT / '008-mt76-npu-rx-packet-ownership.patch'
q, sha, execute = lifetime.q, lifetime.sha, lifetime.execute


def function(source, name):
    if name == 'mt76_npu_dequeue':
        return lifetime.preflight.block(source, r'^static struct sk_buff \*mt76_npu_dequeue\([^;{]*?\)\s*\{')
    return lifetime.function(source, name)


def stage():
    prior = json.loads(PREDECESSOR.read_text())
    for path in (SOURCE, MT76 / 'mt76.h', MT76 / 'airoha_offload.h'):
        assert sha(path) == prior['derived'][str(path.relative_to(ROOT))]
    old = SOURCE.read_text()
    new = lifetime.once(old, function(old, 'mt76_npu_dequeue'), FRAGMENT.read_text().rstrip())
    poll = function(new, 'mt76_npu_rx_poll')
    changed = lifetime.once(poll, '\t\tif (!skb)\n\t\t\tbreak;\n',
                            '\t\tif (!skb)\n\t\t\tbreak;\n'
                            '\t\tif (IS_ERR(skb)) {\n\t\t\tdone++;\n\t\t\tcontinue;\n\t\t}\n')
    changed = lifetime.once(changed, '\trcu_read_lock();\n',
                            '\tif (!budget)\n\t\treturn 0;\n\n\trcu_read_lock();\n')
    new = lifetime.once(new, poll, changed)
    header = ('From: W1700KNPU development <noreply@example.invalid>\n'
              'Subject: [CANDIDATE] wifi: mt76: retain NPU RX packet ownership until validation\n\n'
              'Validate complete fragment readiness and lengths before transferring\n'
              'ownership to an skb. Snapshot device metadata after DMA read barriers.\n'
              'Drop complete malformed packets within the NAPI budget; retain\n'
              'incomplete packets and failed skb allocations for retry.\n\n'
              'Unpromoted: DMA backing/publication and whole-device recovery remain\n'
              'separate contracts. No native firmware descriptor callback is run.\n\n---\n')
    PATCH.write_text(header + ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                                        fromfile='a/npu.c', tofile='b/npu.c')))
    target = BUILD / 'staged'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'npu.c').write_text(old)
    applied = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(PATCH)],
                             cwd=target, capture_output=True, text=True, timeout=30)
    assert applied.returncode == 0 and 'offset' not in applied.stdout and 'fuzz' not in applied.stdout
    assert (target / 'npu.c').read_text() == new
    return old, new


def build(source, name, max_frags=17):
    path = BUILD / name
    path.mkdir(parents=True, exist_ok=True)
    header = (MT76 / 'airoha_offload.h').read_text()
    definitions = [q.declaration(header, 'struct', 'airoha_npu_rx_dma_desc')]
    definitions += [q.macro(header, n) for n in ('NPU_RX_DMA_PKT_COUNT_MASK',
                   'NPU_RX_DMA_DESC_CUR_LEN_MASK', 'NPU_RX_DMA_DESC_DONE_MASK')]
    mt76 = (MT76 / 'mt76.h').read_text()
    definitions += [q.declaration(mt76, 'enum', 'mt76_rxq_id')]
    definitions += [q.declaration(mt76, 'struct', name) for name in
                    ('mt76_queue_entry', 'mt76_queue')]
    (path / 'rx-definitions.inc').write_text('\n'.join(definitions) + '\n')
    names = ('mt76_npu_fill_rx_queue', 'mt76_npu_queue_cleanup', 'mt76_npu_dequeue', 'mt76_npu_rx_poll')
    (path / 'rx-driver.inc').write_text('\n\n'.join(function(source, n) for n in names) + '\n')
    binary = path / 'rx'
    command = [shutil.which('clang'), '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-sign-compare',
               '-Wno-address-of-packed-member',
               '-fsanitize=address,undefined', '-fno-sanitize-recover=all', f'-DMAX_SKB_FRAGS={max_frags}',
               '-I', path, HARNESS, '-o', binary]
    execute(command)
    return binary, dict(command=list(map(str, command)), path=str(binary.relative_to(ROOT)), sha256=sha(binary))


def mutants(source):
    variants = [
        ('eight-snapshots', '\tu16 lengths[16];', '\tu16 lengths[8];', 'complete-delivery', 17),
        ('no-length-check', '\t\tdrop |= lengths[i] > e->dma_len[0];', '', 'length-drop', 17),
        ('capacity-not-mapped-length', 'drop |= lengths[i] > e->dma_len[0];',
         'drop |= lengths[i] > SKB_WITH_OVERHEAD(q->buf_size);', 'mapped-length-bound', 17),
        ('no-fragment-ready', '\t\t\tif (!(ctrl & NPU_RX_DMA_DESC_DONE_MASK))\n\t\t\t\treturn NULL;\n', '', 'partial-retain', 17),
        ('negative-buffer-size', ' || q->buf_size <= 0', '', 'invalid-host-hold', 17),
        ('stale-entry', '\t\te->buf = NULL;', '', 'consumed-entry-clear', 17),
        ('no-drop-budget', '\t\tif (IS_ERR(skb)) {\n\t\t\tdone++;', '\t\tif (IS_ERR(skb)) {', 'drop-budget', 17),
        ('zero-budget-refill', '\tif (!budget)\n\t\treturn 0;\n\n', '', 'zero-budget-page-pool', 17),
        ('no-queued-limit', ' || nframes > q->queued', '', 'insufficient-queued', 17),
        ('no-capacity-check', '\tdrop = nframes > MAX_SKB_FRAGS + 1;', '\tdrop = false;', 'fragment-capacity', 4),
    ]
    rows = []
    for name, old, new, oracle, capacity in variants:
        changed = lifetime.once(source, old, new)
        binary, compiled = build(changed, 'mutant-' + name, capacity)
        done = subprocess.run([str(binary), 'after', 'npu0'], capture_output=True, text=True, timeout=60)
        assert done.returncode != 0 and 'oracle:' + oracle in done.stderr, (name, done.stdout, done.stderr)
        assert 'AddressSanitizer' not in done.stderr and 'runtime error:' not in done.stderr
        rows.append(dict(name=name, build=compiled, oracle=oracle, failure=done.stderr.strip()))
    body = function(source, 'mt76_npu_dequeue')
    assert body.count('dma_rmb();') == 2
    changed = lifetime.once(source, body, body.replace('dma_rmb();', ''))
    binary, compiled = build(changed, 'mutant-no-dma-barrier')
    done = subprocess.run([str(binary), 'after', 'npu0'], capture_output=True, text=True, timeout=60)
    assert done.returncode != 0 and 'oracle:publication-count' in done.stderr, done.stderr
    assert 'AddressSanitizer' not in done.stderr and 'runtime error:' not in done.stderr
    rows.append(dict(name='no-dma-barrier', build=compiled, oracle='publication-count', failure=done.stderr.strip()))
    return rows


def kernel_objects(sources):
    kernel = lifetime.kernel
    prior = json.loads(PREDECESSOR.read_text())
    templates = {row['npu_enabled']: row for row in prior['kernel_objects']
                 if row['kind'] == 'mt76' and row['phase'] == 'after'}
    env = dict(os.environ, STAGING_DIR=str(kernel.TARGET_INCLUDE.parent.parent),
               PATH=str(kernel.TOOLCHAIN / 'bin') + ':' + str(kernel.STAGING / 'host/bin') + ':/usr/bin:/bin')
    rows = []
    for phase, source in zip(('before', 'after'), sources):
        for enabled, template in templates.items():
            old_root = Path(next(arg[2:] for arg in template['command'] if arg.startswith('M=')))
            destination = BUILD / f'kernel-{phase}-{enabled}' / old_root.name
            shutil.copytree(old_root, destination, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('*.o', '*.cmd', '*.d', '*.mod', '*.ko'))
            (destination / 'npu.c').write_text(source)
            for name in ('mt76.h', 'airoha_offload.h', 'mac80211.c'):
                assert sha(destination / name) == prior['derived'][str((old_root / name).relative_to(ROOT))]
            names = ['mac80211.o'] + (['npu.o'] if enabled else [])
            for name in names:
                target = destination / name
                assert target.resolve().is_relative_to(BUILD.resolve())
                target.unlink(missing_ok=True)
            command = [arg.replace(str(old_root), str(destination)) for arg in template['command']]
            command = [arg.replace('Wed Sep 16', 'Wed Sep 23') for arg in command]
            done = subprocess.run(command, capture_output=True, text=True, env=env, timeout=300)
            log = OUT / f'kernel-{phase}-{enabled}.log'
            log.write_text(done.stdout + done.stderr)
            assert done.returncode == 0 and not re.search(r'\b(?:warning|error):', log.read_text(), re.I), log.read_text()
            objects = [lifetime.object_info(destination / name) for name in names]
            if enabled:
                disassembly = execute([str(kernel.PREFIX) + 'objdump', '-dr', destination / 'npu.o'])
                poll = re.search(r'<mt76_npu_rx_poll>:\n(.*?)(?=\n[0-9a-f]+ <|\Z)', disassembly, re.S)
                assert poll, 'RX poll function not found in object disassembly'
                barriers = len(re.findall(r'\bdmb\s+oshld\b', poll[1]))
                assert barriers >= 2 if phase == 'after' else barriers == 0
                objects[-1]['rx_poll_dma_read_barriers'] = barriers
            rows.append(dict(phase=phase, npu_enabled=enabled, command=command, objects=objects,
                             log=str(log.relative_to(ROOT)), log_sha256=sha(log)))
            print(json.dumps(dict(stage='kernel', phase=phase, npu_enabled=enabled)), flush=True)
    return rows


def fingerprints():
    paths = [Path(__file__), HARNESS, FRAGMENT, PREDECESSOR, SOURCE, MT76 / 'mt76.h',
             MT76 / 'airoha_offload.h', MT76 / 'dma.h', MT76 / 'mt7996/mac.c',
             KERNEL / 'net/core/skbuff.c', KERNEL / 'include/linux/skbuff.h',
             KERNEL / 'Documentation/networking/napi.rst']
    return {**lifetime.fingerprints(), **{str(path.relative_to(ROOT)): sha(path) for path in paths}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-kernel', action='store_true')
    args = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    before = fingerprints()
    sources = stage()
    rows = []
    for phase, source in zip(('before', 'after'), sources):
        for capacity in (17, 4):
            binary, compiled = build(source, phase + '-frags-' + str(capacity), capacity)
            for queue in ('npu0', 'npu1'):
                result = json.loads(execute([binary, phase, queue]))
                rows.append(dict(phase=phase, queue=queue, build=compiled, result=result))
    mutations = mutants(sources[1])
    check = subprocess.run(['perl', str(KERNEL / 'scripts/checkpatch.pl'), '--strict', '--no-tree',
                            '--no-signoff', str(PATCH)], capture_output=True, text=True, timeout=30)
    (OUT / 'checkpatch.log').write_text(check.stdout + check.stderr)
    assert check.returncode == 0, check.stdout + check.stderr
    compiled = [] if args.skip_kernel else kernel_objects(sources)
    assert fingerprints() == before
    generated = [BUILD / 'staged/npu.c']
    for row in [*rows, *mutations]:
        directory = ROOT / Path(row['build']['path']).parent
        generated.extend(directory / name for name in ('rx-driver.inc', 'rx-definitions.inc'))
    for row in compiled:
        directory = ROOT / Path(row['objects'][0]['path']).parent
        generated.extend(directory / name for name in ('npu.c', 'mt76.h', 'airoha_offload.h', 'mac80211.c'))
    derived = {str(path.relative_to(ROOT)): sha(path) for path in generated}
    output = OUT / ('rx-ownership-models.json' if args.skip_kernel else 'rx-ownership.json')
    summary = dict(baseline_cases=sum(row['result']['cases'] for row in rows if row['phase'] == 'before'),
                   corrected_cases=sum(row['result']['cases'] for row in rows if row['phase'] == 'after'),
                   mutants=len(mutations), kernel_objects=sum(len(row['objects']) for row in compiled))
    output.write_text(json.dumps(dict(schema=1, summary=summary, inputs_before_after=before, derived=derived,
                                     profiles=rows, mutants=mutations, kernel_objects=compiled,
                                     patch=dict(path=str(PATCH.relative_to(ROOT)), sha256=sha(PATCH)),
                                     checkpatch=check.stdout + check.stderr,
                                     compilers=dict(native=execute(['clang', '--version']).splitlines()[0],
                                                    kernel=execute([str(lifetime.kernel.PREFIX) + 'gcc', '--version']).splitlines()[0]),
                                     limits=['The actual selected driver functions execute against modeled page-pool, skb, DMA and NAPI dependencies.',
                                             'Retained storage exposes logical duplicate release and bounds violations without executing a real UAF or overflow.',
                                             'Capacity four is an artificial stress profile, not the target kernel configuration.',
                                             'Zero/short payloads retain prior buffer-bound behavior; downstream RX header and protocol validation is not proven.',
                                             'DMA publication, buffer identity/backing, cache coherence, producer recycling and complete teardown remain physical/integration contracts.',
                                             'No native firmware descriptor callback, restricted lane, source-lock/overlay, image or router change.']), indent=2) + '\n')
    print(json.dumps(dict(**summary, receipt_sha256=sha(output))))


if __name__ == '__main__':
    main()
