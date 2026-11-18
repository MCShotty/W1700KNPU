#!/usr/bin/env python3
"""Check the paired checked-NPU teardown patch, exact preimages and failure routes."""
import argparse
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from verify_consumer_queue_owner import (
    HEADER, PROVIDER, ROOT, digest, function, linked_baseline,
    linked_module_sources, ordered, patch_into, require,
)
from verify_hot_reset_retention import check_contract as check_hot_reset, shapes as hot_reset_shapes

CHECKPOINT = ROOT / 'research/checkpoints/2026-11-18-npu-packet-owner'
PREVIOUS = CHECKPOINT.parent / '2026-11-18-npu-consumer-queue-owner'
CORE = 'npu.c'
MAC80211 = 'mac80211.c'
RADIO = 'mt7996/init.c'
PCI = 'mt7996/pci.c'
FILES = {
    'kernel': ('airoha-checked-dma-owner.patch', (PROVIDER, HEADER)),
    'mt76': ('mt76-checked-dma-owner.patch', (
        'dma.c', MAC80211, 'mt76.h', CORE, 'mt7996/dma.c', 'mt7996/mac.c',
        RADIO, 'mt7996/npu.c', PCI, 'mt7996/mt7996.h')),
}
CORE_LOCK = 'mutex_lock(&dev->mutex);'
CORE_UNLOCK = 'mutex_unlock(&dev->mutex);'
OWNER_LOCK = 'mutex_lock(&dev->npu_dma.lock);'
OWNER_UNLOCK = 'mutex_unlock(&dev->npu_dma.lock);'
PRESERVE = 'if(READ_ONCE(dev->npu_dma.hold))'
RELEASE = 'if(!READ_ONCE(dev->npu_dma.hold))'
LATCH = 'if(airoha_npu_wlan_uses_checked_dma(npu))WRITE_ONCE(dev->npu_dma.hold,true);'
DEV_LOCKED_ALLOC = 'err=dev->queue_ops->alloc(dev,q,0,size,MT76_NPU_RX_BUF_SIZE,0);'
NO_FALLBACK = 'err=dev->npu_dma.hold?-EPROTO:MT76_NPU_QUEUE_MEM_MANAGED;'


def captures(text):
    def select(component, file, name):
        return function(text[component][file], name)

    result = {
        key: select('mt76', file, name)
        for key, file, name in (
            ('init', CORE, 'mt76_npu_init'),
            ('rx', CORE, 'mt76_npu_rx_queue_init'),
            ('alloc', CORE, 'mt76_npu_alloc_queue_mem'),
            ('deinit', CORE, 'mt76_npu_deinit'),
            ('qobj', MAC80211, 'mt76_init_queue'),
            ('phy', MAC80211, 'mt76_alloc_radio_phy'),
            ('napi', MAC80211, 'mt76_napi_cleanup'),
            ('free', MAC80211, 'mt76_free_device'),
            ('macinit', MAC80211, 'mt76_alloc_device'),
            ('core_dma', 'dma.c', 'mt76_dma_cleanup'),
            ('qalloc', 'dma.c', 'mt76_dma_alloc_queue'),
            ('cleanup', RADIO, 'mt7996_cleanup_device'),
            ('rro', RADIO, 'mt7996_wed_rro_init'),
            ('txfirst', 'mt7996/npu.c', 'mt7996_npu_prepare_tx_buffers'),
            ('txlater', 'mt7996/npu.c', 'mt7996_npu_hw_init'),
            ('probe', PCI, 'mt7996_pci_probe'),
            ('remove', PCI, 'mt7996_pci_remove'),
            ('registry', PCI, 'mt7996_pci_dma_retained'),
            ('keep', PCI, 'mt7996_pci_keep_dma'),
            ('match', PCI, 'mt7996_pci_matches_retained'),
        )
    }
    for key, symbol in (('provider_type', 'airoha_npu_wlan_uses_checked_dma'),
                        ('provider_alloc', 'airoha_npu_wlan_alloc_queue_mem'),
                        ('provider_free', 'airoha_npu_dma_cleanup')):
        result[key] = select('kernel', PROVIDER, symbol)
    return result


def check(c):
    require(ordered(c['rx'], CORE_LOCK, DEV_LOCKED_ALLOC, CORE_UNLOCK), 'missing RX caller lock contract')
    require(ordered(c['alloc'], OWNER_LOCK, 'if(dev->npu_dma.closing){err=-ESHUTDOWN;gotounlock;}',
                    'lockdep_is_held(&dev->npu_dma.lock)', 'err=dev->npu_dma.hold?-ENODEV:',
                    'airoha_npu_wlan_alloc_queue_mem(', NO_FALLBACK, 'q->desc=mem.desc;',
                    'q->desc_dma=mem.dma_addr;', 'q->entry=mem.entry;', 'unlock:' + OWNER_UNLOCK)
            and CORE_LOCK not in c['alloc'], 'recursive or unowned queue allocator')
    require(ordered(c['init'], CORE_LOCK, 'airoha_npu_wlan_init_reserved_memory(npu);',
                    OWNER_LOCK, LATCH, 'err=airoha_npu_wlan_bind_endpoint(',
                    'rcu_assign_pointer(dev->mmio.npu,npu);', OWNER_UNLOCK,
                    'synchronize_rcu();', CORE_UNLOCK)
            and 'returnpriv->checked_pair;' in c['provider_type'], 'checked ownership after binding')
    require(ordered(c['deinit'], CORE_LOCK, OWNER_LOCK, 'dev->npu_dma.closing=true;',
                    'airoha_npu_wlan_rro_close(npu,dev->dev);',
                    'rcu_replace_pointer(dev->mmio.npu,NULL,',
                    'rcu_replace_pointer(dev->mmio.ppe_dev,NULL,', OWNER_UNLOCK,
                    'synchronize_rcu();', CORE_UNLOCK,
                    RELEASE + '{mt76_npu_queue_cleanup(dev,&dev->q_rx[MT_RXQ_NPU0]);'
                    'mt76_npu_queue_cleanup(dev,&dev->q_rx[MT_RXQ_NPU1]);}',
                    'airoha_npu_put(npu);', 'airoha_ppe_put_dev(ppe_dev);'), 'lost held RX allocations on detach')
    require('mutex_init(&dev->npu_dma.lock);' in c['macinit'] and
            ordered(c['qobj'], PRESERVE + '{' + OWNER_LOCK,
                    'returnERR_PTR(-ENOSPC);', 'hwq=kzalloc(sizeof(*hwq),GFP_KERNEL);',
                    'dev->npu_dma.queues[dev->npu_dma.queue_count++]=hwq;', OWNER_UNLOCK,
                    'else{hwq=devm_kzalloc(', 'err=dev->queue_ops->alloc(') and
            ordered(c['phy'], PRESERVE + '{' + OWNER_LOCK, 'phy=kzalloc(size+phy_size,GFP_KERNEL);',
                    'dev->npu_dma.phys[band_idx]=phy;', OWNER_UNLOCK, 'else{phy=devm_kzalloc('),
            'dynamically allocated owner is managed')
    require(ordered(c['napi'], 'state->closing=true;', 'napi_disable(mt76_napi_get(dev,qid));',
                    'synchronize_rcu();', PRESERVE + '{', 'page_pool_disable_direct_recycling(',
                    'netif_napi_del(mt76_napi_get(dev,qid));', 'free_netdev(')
            and 'page_pool_destroy(' not in c['napi'], 'pool detached before NAPI join')
    require(ordered(c['cleanup'], 'hold_dma=READ_ONCE(dev->mt76.npu_dma.hold);',
                    'mt76_unregister_device(&dev->mt76);', 'mt76_worker_disable(',
                    'if(dev->mt76.mcu_ops&&!hold_dma)mt7996_mcu_exit(dev);',
                    'mt7996_pci_shutdown_irqs(dev);', 'mt76_npu_shutdown_irqs(&dev->mt76);',
                    'mt76_napi_cleanup(&dev->mt76);', 'skb_queue_purge(&dev->mt76.mcu.res_q);',
                    'if(hold_dma){dev_warn(', 'return;}', 'mt7996_tx_token_put(dev);',
                    'mt7996_dma_cleanup(dev);', 'mt7996_wed_rro_free(dev);',
                    'mt7996_rro_msdu_page_map_free(dev);')
            and ordered(c['core_dma'], 'mt76_napi_cleanup(dev);', PRESERVE + 'return;',
                        'mt76_dma_tx_cleanup(', 'mt76_dma_rx_cleanup(', 'page_pool_destroy(')
            and ordered(c['free'], 'mt76_worker_teardown(', 'destroy_workqueue(',
                        'mt76_npu_deinit(dev);', RELEASE + 'ieee80211_free_hw(dev->hw);'),
            'destructive teardown before checked retention')
    require(ordered(c['probe'], 'if(mt7996_pci_dma_retained(pdev))returndev_err_probe(',
                    'pcim_enable_device(pdev);', 'pci_set_master(pdev);',
                    'if(!try_module_get(THIS_MODULE)){', 'ret=mt76_npu_init(',
                    'if(mdev->npu_dma.hold){mt7996_pci_keep_dma(dev,pdev,hif2_dev);'
                    'if(ret)gotofree_device;}else{module_put(THIS_MODULE);}',
                    'ret=mdev->npu_dma.hold?0:mt7996_mmio_wed_init(dev,pdev,false,&irq);',
                    'ret=mdev->npu_dma.hold?0:mt7996_mmio_wed_init(dev,hif2_dev,true,&hif2_irq);',
                    'free_device:mt7996_cleanup_device(dev);', 'mt76_free_device(&dev->mt76);')
            and ordered(c['remove'], 'mt7996_unregister_device(dev);', 'pci_free_irq_vectors(hif2_dev);',
                        'pci_free_irq_vectors(pdev);', 'put_device(&hif2_dev->dev);')
            and ordered(c['registry'], 'mutex_lock(&mt7996_retained_dma_lock);',
                        'mt7996_pci_matches_retained(&dev->retained_pci[0],pdev)',
                        'mt7996_pci_matches_retained(&dev->retained_pci[1],pdev)')
            and ordered(c['keep'], '&dev->retained_pci[0],pdev', '&dev->retained_pci[1],hif2',
                        'list_add_tail(&dev->retained_dma,&mt7996_retained_dma);')
            and ordered(c['match'], 'id->domain==pci_domain_nr(pdev->bus)', 'id->bus==pdev->bus->number',
                        'id->devfn==pdev->devfn', 'pci_resource_start(pdev,0)<=id->bar_end',
                        'id->bar_start<=pci_resource_end(pdev,0)'), 'lost PCI hold or early rebind check')
    tx_legacy = 'if(err==-EOPNOTSUPP&&!dev->mt76.npu_dma.hold){'
    require('ret=mt76_npu_rro_open(' in c['rro'] and
            'if(ret!=-EOPNOTSUPP||dev->mt76.npu_dma.hold){if(ret)returnret;' in c['rro'] and
            all(tx_legacy in c[k] for k in ('txfirst', 'txlater')), 'checked TX or RRO managed fallback')
    require(ordered(c['provider_alloc'], 'if(!priv->checked_pair)returnAIROHA_NPU_WLAN_QUEUE_MANAGED;',
                    'life->endpoint!=endpoint||life->dev!=dma_dev',
                    'life->queue_mem_count>=ARRAY_SIZE(life->queue_mem)',
                    'life->queue_mem[life->queue_mem_count++]=',
                    '.desc_bytes=rx_event?0:desc_bytes', '*out=mem;') and
            ordered(c['provider_free'], 'if(life->exposed||life->rro){', 'return;}',
                    'if(queue->desc_bytes)dma_free_coherent(') and
            ordered(c['qalloc'], 'mt76_npu_alloc_queue_mem(dev,q,size);',
                    'if(ret==MT76_NPU_QUEUE_MEM_MANAGED){', 'dmam_alloc_coherent(',
                    'elseif(ret){gotoclear_count;}', 'mt76_npu_queue_setup(dev,q);',
                    'clear_count:q->ndesc=0;'), 'provider or queue storage not retained')


MUTANTS = (
    ('recursive-core-lock', 'alloc', OWNER_LOCK, CORE_LOCK, 'recursive or unowned queue allocator'),
    ('allow-checked-managed-fallback', 'alloc', NO_FALLBACK, 'err=MT76_NPU_QUEUE_MEM_MANAGED;',
     'recursive or unowned queue allocator'),
    ('require-reply-before-hold', 'init', LATCH, '', 'checked ownership after binding'),
    ('unconditional-NPU-RX-release', 'deinit', RELEASE, 'if(true)', 'lost held RX allocations on detach'),
    ('managed-extra-queue', 'qobj', 'hwq=kzalloc(', 'hwq=devm_kzalloc(dev->dev,',
     'dynamically allocated owner is managed'),
    ('pool-unmaps-before-detach', 'napi', 'page_pool_disable_direct_recycling(', 'page_pool_destroy(',
     'pool detached before NAPI join'),
    ('release-held-hw-context', 'free', RELEASE, '', 'destructive teardown before checked retention'),
    ('restart-MCU-with-held-DMA', 'cleanup', 'dev->mt76.mcu_ops&&!hold_dma', 'dev->mt76.mcu_ops',
     'destructive teardown before checked retention'),
    ('release-tokens-before-guard', 'cleanup', 'if(hold_dma){dev_warn(', 'if(false){dev_warn(',
     'destructive teardown before checked retention'),
    ('drop-retained-HIF2-match', 'registry', 'mt7996_pci_matches_retained(&dev->retained_pci[1],pdev)',
     'false', 'lost PCI hold or early rebind check'),
    ('omit-pin-before-bind', 'probe', 'try_module_get(THIS_MODULE)', 'true',
     'lost PCI hold or early rebind check'),
    ('allow-checked-RRO-fallback', 'rro', 'ret!=-EOPNOTSUPP||dev->mt76.npu_dma.hold',
     'ret!=-EOPNOTSUPP', 'checked TX or RRO managed fallback'),
)


def verify(receipt, pin):
    require(__debug__ and digest(receipt) == pin, 'unverified producer')
    prod = linked_module_sources(ROOT, receipt)
    require(prod['receipt_sha256'] == pin, 'producer drift')
    preimages, postimages, patches, texts = {}, {}, {}, {}
    with TemporaryDirectory(prefix='w1700k-packet-owner-') as directory:
        d = Path(directory)
        before = json.loads((PREVIOUS / 'EVIDENCE.json').read_bytes())
        old_patch = PREVIOUS / 'mt76-consumer-queue-owner.patch'
        require(digest(old_patch) == before['patch_sha256'][old_patch.name], 'superseded patch drift')
        legacy = patch_into(d / 'superseded', 'mt76', prod, tuple(before['before']['mt76']), old_patch)
        require(all(digest(d / 'superseded' / p) == h for p, h in before['candidate']['mt76'].items()) and
                CORE_LOCK in function(legacy[CORE], 'mt76_npu_alloc_queue_mem'), 'old recursion not reproduced')
        for g, (name, files) in FILES.items():
            target = CHECKPOINT / name
            texts[g] = patch_into(d / g, g, prod, files, target)
            preimages[g] = {n: prod[g][n] for n in files}
            postimages[g] = {n: digest(d / g / n) for n in files}
            patches[name] = digest(target)

    c = captures(texts)
    check(c)
    check_hot_reset(hot_reset_shapes(texts['mt76']))
    for label, key, old, new, reason in MUTANTS:
        require(old in c[key], f'missing control: {label}')
        try:
            check({**c, key: c[key].replace(old, new, 1)})
        except ValueError as exc:
            require(str(exc) == reason, f'{label}: wrong failure: {exc}')
        else:
            raise ValueError(f'accepted control: {label}')
    return dict(schema=1, producer=prod['receipt'], producer_sha256=pin, patch_sha256=patches,
                source_lock_sha256=prod['source_lock_sha256'], preimages=preimages, postimages=postimages,
                baseline=linked_baseline(prod), superseded_queue_patch_sha256=digest(old_patch),
                prior_hot_reset_contract_preserved=True, rejected_source_controls=[c[0] for c in MUTANTS],
                compiled=False, physical_retirement_proven=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--producer', required=True, type=Path)
    p.add_argument('--producer-sha256', required=True)
    p.add_argument('--check', type=Path)
    args = p.parse_args()
    try:
        record = verify(args.producer, args.producer_sha256)
        if args.check:
            require(json.loads(args.check.read_bytes()) == record, 'retained receipt differs')
        else:
            print(json.dumps(record, indent=2, sort_keys=True))
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as exc:
        p.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
