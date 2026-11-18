#!/usr/bin/env python3
"""Verify hot-reset ordering in an exact patch to the qualified radio source."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from npu_world_sources import digest, linked_module_sources

CHECKPOINT = ROOT / 'research/checkpoints/2026-11-18-npu-hot-reset-retention'
SOURCE = ROOT / '.local/merge-nonoc-20260923/mt76-merged'
DMA, MAC, NPU = ('mt7996/' + name + '.c' for name in ('dma', 'mac', 'npu'))
FILES = (DMA, MAC, NPU)


def require(value, reason):
    if not value:
        raise ValueError(reason)


def body(sources, name, definition):
    match = re.search(r'^(?:[^\n]*\b)?' + re.escape(definition) +
                      r'\([^;\n]*\)\n\{\n(.*?)^\}', sources[name], re.M | re.S)
    require(match is not None, 'definition not found: ' + definition)
    return re.sub(r'/\*.*?\*/|\s+', '', match[1], flags=re.S)


PARK = 'mt76_npu_send_msg(npu,4,WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR,0,GFP_KERNEL)'
RESET6 = 'mt76_npu_send_msg(npu,6,WLAN_FUNC_SET_WAIT_INODE_TXRX_REG_ADDR,0,GFP_KERNEL)'
GET = 'mt76_npu_get_msg(npu,3,WLAN_FUNC_GET_WAIT_NPU_INFO,&info,GFP_KERNEL)'
POLL = 'mt76_poll(dev,MT_WFDMA_EXT_CSR_HIF_MISC,MT_WFDMA_EXT_CSR_HIF_MISC_BUSY,0,1000)'
ACTIVE = 'if(mt76_npu_device_active(&dev->mt76))return-EOPNOTSUPP;'
IDLE = 'if(!' + POLL + ')return-ETIMEDOUT;'
TOKENS = 'mt7996_tx_token_put(dev);idr_init(&dev->mt76.token);'
LATCH = 'WRITE_ONCE(dev->recovery.npu_error,ret);'
STOP = 'ret=mt7996_npu_hw_stop(dev);'
L1_BRANCH = 'if(ret)gotonpu_recovery_failed;'
IRQ_OFF = 'err=mt76_npu_disable_irqs(&dev->mt76);if(err)returnerr;'
HIF_OFF = ('mt76_clear(dev,MT_WFDMA0_GLO_CFG,MT_WFDMA0_GLO_CFG_TX_DMA_EN|MT_WFDMA0_GLO_CFG_RX_DMA_EN);'
           'if(dev->hif2)mt76_clear(dev,MT_WFDMA0_GLO_CFG+hif1_ofs,'
           'MT_WFDMA0_GLO_CFG_TX_DMA_EN|MT_WFDMA0_GLO_CFG_RX_DMA_EN);usleep_range(1000,2000);')


def ordered(code, *parts):
    start = 0
    for part in parts:
        at = code.find(part, start)
        if at < 0:
            return False
        start = at + len(part)
    return True


def shapes(sources):
    return {
        'dma': body(sources, DMA, 'mt7996_dma_reset'),
        'restart': body(sources, MAC, 'mt7996_mac_restart'),
        'full': body(sources, MAC, 'mt7996_mac_full_reset'),
        'l1': body(sources, MAC, 'mt7996_mac_reset_work'),
        'stop': body(sources, NPU, 'mt7996_npu_hw_stop'),
    }


def check_contract(code):
    dma = code['dma']
    require(IRQ_OFF + ACTIVE + HIF_OFF + IDLE + 'if(force){' + TOKENS + '}' in dma and
            dma.count('mt7996_tx_token_put(') == 1 and
            ordered(dma, IDLE, TOKENS, 'mt76_queue_tx_cleanup(', 'mt76_queue_rx_cleanup(',
                    'mt7996_rro_msdu_page_map_free(', 'mt7996_dma_enable('), 'dma-resources-before-gate')
    require('mt7996_tx_token_put(' not in code['restart'] and
            ordered(code['restart'], 'synchronize_rcu();',
                    'ret=mt7996_dma_reset(dev,true);if(ret){' + LATCH + 'returnret;}',
                    'mt76_napi_enable('), 'watchdog-token-or-error-order')
    full_gate = ('ret=mt7996_mac_restart(dev);if(!ret)break;'
                 'if(READ_ONCE(dev->mt76.mmio.npu_irq.error)||READ_ONCE(dev->recovery.npu_error)){'
                 + LATCH + 'mutex_unlock(&dev->mt76.mutex);')
    require(ordered(code['full'], full_gate, 'returnret;}', 'mt76_reset_device(',
                    'ieee80211_wake_queues('), 'watchdog-retries-unverified-stop')
    stop = code['stop']
    require(RESET6 not in stop and stop.count('mt76_npu_send_msg(') == 1 and ordered(
            stop, 'if(!npu)gotounlock;', 'err=' + PARK + ';if(err)gotounlock;',
            'err=' + GET + ';if(!err&&!info)break;', 'if(!err)err=-EOPNOTSUPP;',
            'unlock:mutex_unlock(&dev->mt76.mutex);returnerr;'), 'l1-accepts-zero-as-retirement')
    l1 = code['l1']
    require(ordered(l1, 'if(READ_ONCE(dev->recovery.npu_error))return;', STOP,
                    'synchronize_rcu();', L1_BRANCH, 'MT_MCU_INT_EVENT_DMA_STOPPED',
                    'ret=mt7996_dma_reset(dev,false);' + L1_BRANCH, TOKENS,
                    'ieee80211_wake_queues(', 'npu_recovery_failed:', LATCH),
            'l1-releases-or-resumes-on-error')


def controls(code):
    cases = [
        ('permit-attached-npu', 'dma', ACTIVE, '', 'dma-resources-before-gate'),
        ('ignore-radio-timeout', 'dma', IDLE, POLL + ';', 'dma-resources-before-gate'),
        ('move-early-token-free', 'restart', 'synchronize_rcu();',
         'synchronize_rcu();' + TOKENS, 'watchdog-token-or-error-order'),
        ('omit-watchdog-latch', 'restart', LATCH, '', 'watchdog-token-or-error-order'),
        ('retry-retained-reset', 'full', '||READ_ONCE(dev->recovery.npu_error)', '',
         'watchdog-retries-unverified-stop'),
        ('restore-set6', 'stop', 'if(!err)err=-EOPNOTSUPP;', 'if(!err)err=' + RESET6 + ';',
         'l1-accepts-zero-as-retirement'),
        ('ignore-l1-stop-error', 'l1', L1_BRANCH, '', 'l1-releases-or-resumes-on-error'),
    ]
    for label, func, old, new, reason in cases:
        require(old in code[func], f'control anchor missing: {label}')
        try:
            check_contract({**code, func: code[func].replace(old, new, 1)})
        except ValueError as exc:
            require(str(exc) == reason, f'wrong failure for {label}: {exc}')
        else:
            raise ValueError(f'accepted bypass: {label}')
    return [c[0] for c in cases]


def verify(producer_path, producer_pin, patch):
    require(__debug__ and digest(producer_path) == producer_pin, 'unverified linked producer')
    production = linked_module_sources(ROOT, producer_path)
    require(production['receipt_sha256'] == producer_pin, 'producer changed during verification')
    previous = {n: production['mt76'][n] for n in FILES}
    require(all(digest(SOURCE / n) == previous[n] for n in FILES), 'qualified radio source drift')
    before = shapes({n: (SOURCE / n).read_text() for n in FILES})
    require(ordered(before['restart'], TOKENS, 'ret=mt7996_dma_reset(dev,true);') and
            RESET6 in before['stop'] and POLL not in before['dma'], 'reference already differs')

    with TemporaryDirectory(prefix='w1700k-hot-reset-') as directory:
        root = Path(directory)
        for name in FILES:
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / name, root / name)
        cmd = ['git', 'apply', '--whitespace=error-all']
        stat = subprocess.check_output(cmd + ['--numstat', '-z', str(patch)], cwd=root)
        paths = [row.split(b'\t', 2)[-1].decode() for row in stat.split(b'\0') if row]
        require(len(paths) == len(FILES) and set(paths) == set(FILES), 'patch changed extra files')
        subprocess.run(cmd + ['--check', str(patch)], cwd=root, check=True)
        subprocess.run(cmd + [str(patch)], cwd=root, check=True)
        candidate = {n: digest(root / n) for n in FILES}
        code = shapes({n: (root / n).read_text() for n in FILES})
        check_contract(code)
        rejected = controls(code)

    return dict(schema=1, producer=production['receipt'], producer_sha256=producer_pin,
                source_lock_sha256=production['source_lock_sha256'], patch_sha256=digest(patch),
                before=previous, candidate=candidate, rejected_source_controls=rejected,
                compiled=False, physical_retirement_proven=False, staged_not_promoted=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--producer', type=Path, required=True)
    parser.add_argument('--producer-sha256', required=True)
    parser.add_argument('--patch', type=Path, default=CHECKPOINT / 'mt76-hot-reset-retention.patch')
    parser.add_argument('--check', type=Path, help='match a retained receipt')
    args = parser.parse_args()
    try:
        record = verify(args.producer, args.producer_sha256, args.patch.resolve())
        if args.check:
            require(record == json.loads(args.check.read_bytes()), 'retained receipt differs')
        else:
            print(json.dumps(record, indent=2, sort_keys=True))
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
