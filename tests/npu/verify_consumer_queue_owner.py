#!/usr/bin/env python3
"""Check exact staged provider and mt76 queue ownership against a qualified input tree."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from npu_world_sources import digest, linked_module_sources

SOURCE = ROOT / '.local/merge-nonoc-20260923'
CHECKPOINT = ROOT / 'research/checkpoints/2026-11-18-npu-consumer-queue-owner'
PREVIOUS = CHECKPOINT.parent / '2026-11-18-npu-hot-reset-retention/mt76-hot-reset-retention.patch'
PROVIDER = 'drivers/net/ethernet/airoha/airoha_npu.c'
HEADER = 'include/linux/soc/airoha/airoha_offload.h'
GROUPS = {
    'kernel': ('airoha-consumer-queue-owner.patch', (PROVIDER, HEADER)),
    'mt76': ('mt76-consumer-queue-owner.patch', ('dma.c', 'mt76.h', 'npu.c')),
}
PREVIOUS_FILES = ('mt7996/dma.c', 'mt7996/mac.c', 'mt7996/npu.c')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def compact(source):
    return re.sub(r'/\*.*?\*/|\s+', '', source, flags=re.S)


def function(source, name):
    start = re.search(r'^(?:[^\n]*\b)?' + re.escape(name) +
                      r'\([^;{}]*?\)\n\{', source, re.M)
    require(start is not None, 'function missing: ' + name)
    return compact(source[start.end():source.index('\n}', start.end())])


def ordered(body, *parts):
    cursor = 0
    for part in parts:
        pos = body.find(part, cursor)
        if pos < 0:
            return False
        cursor = pos + len(part)
    return True


def patch_into(parent, component, production, names, path):
    for name in names:
        origin = SOURCE / (component + '-merged') / name
        dest = parent / name
        require(digest(origin) == production[component][name], 'preimage drift: ' + name)
        require(not dest.exists(), 'patch input appears in two groups: ' + name)
        dest.parent.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(origin, dest)
    cmd = ['git', 'apply', '--whitespace=error-all']
    stat = subprocess.check_output(cmd + ['--numstat', '-z', str(path)], cwd=parent)
    paths = [line.split(b'\t', 2)[-1].decode() for line in stat.split(b'\0') if line]
    require(len(paths) == len(names) and set(paths) == set(names), 'wrong patch scope: ' + path.name)
    subprocess.run(cmd + ['--check', str(path)], cwd=parent, check=True)
    subprocess.run(cmd + [str(path)], cwd=parent, check=True)
    return {name: (parent / name).read_text() for name in names}


def linked_baseline(production):
    name, = (p for p in production['artifacts'] if Path(p).name == 'mt76.ko')
    calls = {0xe58: 'mt76_npu_alloc_rx_event', 0xe94: 'devm_kmalloc', 0xf18: 'dmam_alloc_attrs'}
    with (ROOT / name).open('rb') as stream:
        elf = ELFFile(stream)
        require(elf.little_endian and elf.elfclass == 64 and elf['e_machine'] == 'EM_AARCH64' and
                elf['e_type'] == 'ET_REL', 'wrong linked mt76 architecture')
        rel = elf.get_section_by_name('.rela.text')
        text_index = elf.get_section_index('.text')
        require(rel['sh_info'] == text_index, 'incorrect linked relocations')
        syms = elf.get_section(rel['sh_link'])
        bound, = syms.get_symbol_by_name('mt76_dma_alloc_queue')
        require(bound['st_shndx'] == text_index and all(
                bound['st_value'] <= off < bound['st_value'] + bound['st_size'] for off in calls),
                'managed calls outside linked queue allocator')
        actual = {}
        for entry in rel.iter_relocations():
            off = entry['r_offset']
            if off in calls:
                require(entry['r_info_type'] == 283 and entry['r_addend'] == 0 and off not in actual,
                        'wrong managed call relocation')
                actual[off] = syms.get_symbol(entry['r_info_sym']).name
        require(actual == calls, 'different qualified managed allocation')
    return {'module_sha256': production['artifacts'][name], 'calls': {hex(k): v for k, v in calls.items()}}


GUARD = 'life->endpoint!=endpoint||life->dev!=dma_dev||'
STAGE = 'life->queue_mem[life->queue_mem_count++]='
FALLBACK = 'if(ret==MT76_NPU_QUEUE_MEM_MANAGED){'
RX = ('err=airoha_npu_wlan_alloc_rx_event_session(npu,endpoint,dma_dev,count,desc_size,'
      '&mem.desc,&mem.dma_addr);if(err)returnerr;')
PUBLISH = ['q->desc=mem.desc;', 'q->desc_dma=mem.dma_addr;', 'q->entry=mem.entry;']


def check(code):
    alloc, clean, npu, queue = (code[key] for key in ('alloc', 'cleanup', 'npu', 'queue'))
    require(ordered(alloc, 'if(!priv->checked_pair)returnAIROHA_NPU_WLAN_QUEUE_MANAGED;',
                    'check_mul_overflow((size_t)count,desc_size,&desc_bytes)',
                    'check_mul_overflow((size_t)count,entry_size,&entry_bytes)',
                    'check_add_overflow(desc_bytes,entry_bytes,&bytes)', RX,
                    'mutex_lock(&priv->wlan_session_lock);',
                    'err=priv->wlan_session_error;if(err)gotounlock;',
                    '!life->exposed||!life->endpoint_bound||' + GUARD,
                    'life->dev!=npu->dev||life->boot_identity!=priv->boot_identity',
                    'life->queue_mem_count>=ARRAY_SIZE(life->queue_mem)',
                    'bytes>NPU_WLAN_MAX_QUEUE_BYTES-life->queue_mem_bytes',
                    'life->rx_event.addr!=mem.dma_addr||life->rx_event.bytes!=desc_bytes',
                    'mem.entry=kvzalloc(entry_bytes,GFP_KERNEL);',
                    'if(!rx_event){mem.desc=dma_alloc_coherent(dma_dev,desc_bytes,&mem.dma_addr,GFP_KERNEL);',
                    'if(!mem.desc){kvfree(mem.entry);err=-ENOMEM;gotounlock;}',
                    STAGE, '.desc_bytes=rx_event?0:desc_bytes', '*out=mem;', 'unlock:mutex_unlock(')
            and alloc.count('*out=') == 1 and 'dmam_alloc' not in alloc and 'devm_k' not in alloc,
            'provider-allocation-publication')
    require(ordered(clean, 'if(life->exposed||life->rro){',
                    'list_add_tail(&life->retained,&airoha_npu_retained_dma);',
                    'return;}for(i=0;i<life->queue_mem_count;i++){',
                    'if(queue->desc_bytes)dma_free_coherent(life->dev,queue->desc_bytes,'
                    'queue->mem.desc,queue->mem.dma_addr);', 'kvfree(queue->mem.entry);',
                    'if(life->rx_event.buf)dma_free_coherent('), 'provider-retains-exposed-and-borrowed')
    require(ordered(npu, 'rx_event=q==&dev->q_rx[qid]&&q->flags==MT_NPU_Q_TXFREE(0);',
                    'mutex_lock(&dev->mutex);', 'if(!npu){err=MT76_NPU_QUEUE_MEM_MANAGED;gotounlock;}',
                    'err=airoha_npu_wlan_alloc_queue_mem(npu,dev->dev,dev->dma_dev,q->ndesc,'
                    'desc_size,sizeof(*q->entry),rx_event,&mem);',
                    'if(err==AIROHA_NPU_WLAN_QUEUE_MANAGED){err=MT76_NPU_QUEUE_MEM_MANAGED;}'
                    'elseif(err>0){err=-EPROTO;}elseif(!err){', *PUBLISH,
                    'unlock:mutex_unlock(&dev->mutex);'), 'consumer-provider-routing')
    require(ordered(queue, 'if(q->desc||q->entry)return-EBUSY;', 'q->ndesc=n_desc;',
                    'ret=mt76_npu_alloc_queue_mem(dev,q,size);' + FALLBACK,
                    'dmam_alloc_coherent(', 'devm_kcalloc(', 'elseif(ret){gotoclear_count;}',
                    'if(!q->desc||!q->entry){ret=-ENOMEM;gotoclear_count;}',
                    'ret=mt76_create_page_pool(dev,q);if(ret)gotoclear_count;',
                    'mt76_npu_queue_setup(dev,q);', 'mt76_dma_queue_reset(',
                    'clear_count:q->ndesc=0;returnret;'), 'consumer-publishes-only-complete-queues')
    require('EXPORT_SYMBOL_GPL(airoha_npu_wlan_alloc_queue_mem);' in code['provider'] and
            'intairoha_npu_wlan_alloc_queue_mem(' in code['header'] and
            '#defineAIROHA_NPU_WLAN_QUEUE_MANAGED1' in code['header'] and
            '#defineMT76_NPU_QUEUE_MEM_MANAGED1' in code['mt_header'] and
            '#defineNPU_WLAN_MAX_QUEUE_MEM48' in code['provider'] and
            '#defineNPU_WLAN_MAX_QUEUE_BYTESSZ_8M' in code['provider'], 'abi-or-budget')


def controls(code):
    cases = [
        ('omit-endpoint-binding', 'alloc', GUARD, 'life->dev!=dma_dev||', 'provider-allocation-publication'),
        ('ignore-borrow-error', 'alloc', RX, RX.removesuffix('if(err)returnerr;'), 'provider-allocation-publication'),
        ('publish-before-enrollment', 'alloc', STAGE, '*out=mem;' + STAGE, 'provider-allocation-publication'),
        ('free-exposed-objects', 'cleanup', 'life->exposed||life->rro', 'life->rro',
         'provider-retains-exposed-and-borrowed'),
        ('double-free-borrowed-objects', 'cleanup', 'if(queue->desc_bytes)', '',
         'provider-retains-exposed-and-borrowed'),
        ('fallback-after-checked-failure', 'queue', FALLBACK, 'if(ret<0){',
         'consumer-publishes-only-complete-queues'),
        ('walk-incomplete-queue', 'queue', 'clear_count:q->ndesc=0;', 'clear_count:',
         'consumer-publishes-only-complete-queues'),
    ]
    for label, name, old, mutant, reason in cases:
        require(old in code[name], 'missing control anchor: ' + label)
        try:
            check({**code, name: code[name].replace(old, mutant, 1)})
        except ValueError as exc:
            require(str(exc) == reason, f'{label}: wrong failure {exc}')
        else:
            raise ValueError('accepted control: ' + label)
    return [label for label, *_ in cases]


def verify(receipt, pin):
    require(__debug__ and digest(receipt) == pin, 'unverified linked input tree')
    prod = linked_module_sources(ROOT, receipt)
    require(prod['receipt_sha256'] == pin, 'producer changed during verification')
    baseline = linked_baseline(prod)
    pre, post, pins, texts = {}, {}, {}, {}
    with TemporaryDirectory(prefix='w1700k-queue-owner-') as directory:
        for name, (patch, files) in GROUPS.items():
            staging = Path(directory) / name
            target = CHECKPOINT / patch
            texts[name] = patch_into(staging, name, prod, files, target)
            pre[name] = {f: prod[name][f] for f in files}
            post[name] = {f: digest(staging / f) for f in files}
            pins[patch] = digest(target)
        patch_into(Path(directory) / 'mt76', 'mt76', prod, PREVIOUS_FILES, PREVIOUS)
        require(post['mt76'] == {f: digest(Path(directory) / 'mt76' / f) for f in post['mt76']},
                'staged hot-reset patch altered queue-owner postimage')
    provider = texts['kernel'][PROVIDER]
    code = {'alloc': function(provider, 'airoha_npu_wlan_alloc_queue_mem'),
            'cleanup': function(provider, 'airoha_npu_dma_cleanup'),
            'npu': function(texts['mt76']['npu.c'], 'mt76_npu_alloc_queue_mem'),
            'queue': function(texts['mt76']['dma.c'], 'mt76_dma_alloc_queue'),
            'provider': compact(provider), 'header': compact(texts['kernel'][HEADER]),
            'mt_header': compact(texts['mt76']['mt76.h'])}
    check(code)
    return dict(schema=1, producer=prod['receipt'], producer_sha256=pin,
                source_lock_sha256=prod['source_lock_sha256'], before=pre, candidate=post,
                patch_sha256=pins, previous_hot_reset_patch_sha256=digest(PREVIOUS),
                linked_baseline=baseline, rejected_source_controls=controls(code),
                compiled=False, retains_packet_payload=False, physical_retirement_proven=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--producer', required=True, type=Path)
    parser.add_argument('--producer-sha256', required=True)
    parser.add_argument('--check', type=Path)
    args = parser.parse_args()
    try:
        record = verify(args.producer, args.producer_sha256)
        if args.check:
            require(record == json.loads(args.check.read_bytes()), 'retained evidence differs')
        else:
            print(json.dumps(record, indent=2, sort_keys=True))
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
