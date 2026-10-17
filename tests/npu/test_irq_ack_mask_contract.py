#!/usr/bin/env python3
"""Characterize actual IRQ read/ack/mask callers;not a checked-IRQ fix."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
import test_npu_firmware_loader as loader
import test_npu_host_lifetime as lifetime
import native_prefix_snapshot
from test_final_irq_contract import PROVIDER, KHEADER, HEADER, MHEADER

ROOT = loader.ROOT
CALLER = ROOT / '.local/merge-nonoc-20260923/mt76-merged/npu.c'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    destination = ROOT / '.local/npu-irq-ack-mask-contract' / args.name
    assert not destination.exists()
    destination.mkdir(parents=True)
    files = (PROVIDER, KHEADER, HEADER, MHEADER, CALLER, Path(__file__),
             Path(loader.__file__), Path(loader.extract.__file__))
    inputs = native_prefix_snapshot.source_inputs({str(path.relative_to(ROOT)): sha(path) for path in files})
    provider = PROVIDER.read_text()
    constants = [line for line in provider.splitlines() if line.startswith('#define ') and
        line.split()[1].split('(')[0] in ('NPU_WLAN_BASE_ADDR', 'REG_IRQ_STATUS', 'REG_IRQ_RXDONE', 'NPU_IRQ_RX_MASK')]
    assert len(constants) == 4
    functions = [loader.extract.function(provider, name) for name in
        ('airoha_npu_wlan_irq_status_set', 'airoha_npu_wlan_irq_status_get', 'airoha_npu_wlan_irq_disable')]
    functions += [loader.extract.function(HEADER.read_text(), name) for name in
        ('airoha_npu_wlan_set_irq_status', 'airoha_npu_wlan_get_irq_status', 'airoha_npu_wlan_disable_irq')]
    functions += [lifetime.function(CALLER.read_text(), name) for name in
        ('mt76_npu_irq_handler', 'mt76_npu_disable_irqs')]
    queues = loader.extract.declaration(MHEADER.read_text(), 'enum', 'mt76_rxq_id')
    prefix = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
typedef int irqreturn_t;
#define IRQ_HANDLED 1
#define BIT(n) (1u << (n))
''' + queues + '\n' + '\n'.join(constants) + r'''
struct airoha_npu {
    void *regmap;
    struct {
        void (*wlan_set_irq_status)(struct airoha_npu *, u32);
        u32 (*wlan_get_irq_status)(struct airoha_npu *, int);
        void (*wlan_disable_irq)(struct airoha_npu *, int);
    } ops;
};
struct mt76_dev;
struct mt76_queue { struct mt76_dev *dev; };
struct napi_struct { unsigned qid; };
struct mt76_dev {
    struct { struct airoha_npu *npu; } mmio;
    struct mt76_queue q_rx[__MT_RXQ_MAX];
    struct napi_struct napi[__MT_RXQ_MAX];
};
struct configuration { int error[3]; unsigned ack_effect, mask_effect; };
struct call { unsigned stage, queue; u32 value; int error; };
static struct mt76_dev dev;
static struct airoha_npu npu;
static struct configuration config[2];
static struct call calls[6];
static unsigned count, cursor, scope, locks, unlocks, schedules, last_qid;
static u32 pending, masks[2], original_masks[2], read_value;
static int cookie;
static void rcu_read_lock(void) { assert(!scope); scope=1; locks++; }
static void rcu_read_unlock(void) { assert(scope==1); scope=0; unlocks++; }
static struct airoha_npu *lookup(struct airoha_npu *p) { assert(scope==1); return p; }
#define rcu_dereference(p) lookup(p)
static void napi_schedule(struct napi_struct *napi) {
    assert(scope==1 && napi>=dev.napi && napi<dev.napi+__MT_RXQ_MAX);
    assert(napi->qid==MT_RXQ_NPU0 || napi->qid==MT_RXQ_NPU1); schedules++; last_qid=napi->qid;
}
static void event(unsigned stage, u32 value) {
    assert(count<6 && scope==1); calls[count++]=(struct call){stage,cursor,value,config[cursor].error[stage]};
}
static int regmap_read(void *map, u32 reg, u32 *value) {
    assert(map==&cookie && reg==REG_IRQ_STATUS && value);
    /* Even error cases explicitly provide an output;no undefined uninitialized read is executed. */
    *value=read_value=pending; event(0,*value); return config[cursor].error[0];
}
static int regmap_write(void *map, u32 reg, u32 value) {
    assert(map==&cookie && reg==REG_IRQ_STATUS && value==(config[cursor].error[0]?0:(read_value&NPU_IRQ_RX_MASK(cursor))));
    event(1,value); if(config[cursor].ack_effect) pending&=~value;
    return config[cursor].error[1];
}
static int regmap_clear_bits(void *map, u32 reg, u32 mask) {
    int q=reg==0x30d034u ? 0 : reg==0x30d038u ? 1 : -1;
    assert(map==&cookie && q>=0 && (unsigned)q==cursor && mask==(q ? 0x20000u : 0x10000u));
    event(2,mask); if(config[cursor].mask_effect) masks[q]&=~mask;
    int result=config[cursor].error[2]; cursor++; return result;
}
'''
    # The bulk caller advances to queue1 after mask0;the single handler uses its own queue index.
    suffix = r'''
static void reset(unsigned first, struct configuration a, struct configuration b) {
    assert(!scope); memset(calls,0,sizeof(calls)); count=0; cursor=first;
    locks=unlocks=schedules=last_qid=0; pending=0x80030005u;
    config[0]=a; config[1]=b;
    masks[0]=original_masks[0]=0x5a010008u;
    masks[1]=original_masks[1]=0xa5020020u;
    npu.regmap=&cookie;
    npu.ops.wlan_set_irq_status=airoha_npu_wlan_irq_status_set;
    npu.ops.wlan_get_irq_status=airoha_npu_wlan_irq_status_get;
    npu.ops.wlan_disable_irq=airoha_npu_wlan_irq_disable;
    dev.mmio.npu=&npu;
    for(unsigned q=0;q<__MT_RXQ_MAX;q++) { dev.q_rx[q].dev=&dev; dev.napi[q].qid=q; }
}
static void check(unsigned first, unsigned queues) {
    assert(!scope && locks==1 && unlocks==1 && count==queues*3);
    u32 expected_pending=0x80030005u;
    for(unsigned i=0;i<queues;i++) {
        unsigned q=first+i;
        assert(calls[i*3].stage==0 && calls[i*3].queue==q && calls[i*3].value==expected_pending);
        u32 ack=config[q].error[0]?0:(expected_pending&NPU_IRQ_RX_MASK(q));
        assert(calls[i*3+1].stage==1 && calls[i*3+1].queue==q && calls[i*3+1].value==ack);
        assert(calls[i*3+2].stage==2 && calls[i*3+2].queue==q && calls[i*3+2].value==NPU_IRQ_RX_MASK(q));
        for(unsigned stage=0;stage<3;stage++) assert(calls[i*3+stage].error==config[q].error[stage]);
        if(config[q].ack_effect) expected_pending&=~ack;
    }
    assert(pending==expected_pending);
    for(unsigned q=0;q<2;q++) {
        int used=q>=first && q<first+queues;
        assert(masks[q]==(original_masks[q]&~((used&&config[q].mask_effect)?NPU_IRQ_RX_MASK(q):0)));
    }
}
int main(void) {
    struct configuration options[75]; unsigned options_count=0;
    const int errors[]={0,-5,-110};
    for(unsigned read=0;read<3;read++)for(unsigned ack=0;ack<3;ack++)for(unsigned mask=0;mask<3;mask++)
        for(unsigned ae=0;ae<2;ae++)for(unsigned me=0;me<2;me++) {
            if((!ack&&!ae)||(!mask&&!me)) continue;
            assert(options_count<75);
            options[options_count++]=(struct configuration){{errors[read],errors[ack],errors[mask]},ae,me};
        }
    assert(options_count==75);
    unsigned hard=0, scheduled_after_error=0, bulk=0, bulk_error_cases=0;
    for(unsigned q=0;q<2;q++)for(unsigned i=0;i<options_count;i++) {
        reset(q,options[i],options[i]);
        int result=mt76_npu_irq_handler(91+q,&dev.q_rx[MT_RXQ_NPU0+q]);
        check(q,1); assert(result==IRQ_HANDLED && schedules==1 && last_qid==MT_RXQ_NPU0+q);
        hard++; scheduled_after_error+=!!(options[i].error[0]||options[i].error[1]||options[i].error[2]);
    }
    for(unsigned a=0;a<options_count;a++)for(unsigned b=0;b<options_count;b++) {
        reset(0,options[a],options[b]); mt76_npu_disable_irqs(&dev); check(0,2);
        assert(!schedules); bulk++;
        bulk_error_cases+=!!(options[a].error[0]||options[a].error[1]||options[a].error[2]||
                            options[b].error[0]||options[b].error[1]||options[b].error[2]);
    }
    for(unsigned q=0;q<2;q++) {
        reset(q,options[0],options[0]); dev.mmio.npu=0;
        assert(mt76_npu_irq_handler(91+q,&dev.q_rx[MT_RXQ_NPU0+q])==IRQ_HANDLED);
        assert(!scope && locks==1 && unlocks==1 && !count && !schedules);
    }
    reset(0,options[0],options[0]); dev.mmio.npu=0; mt76_npu_disable_irqs(&dev);
    assert(!scope && locks==1 && unlocks==1 && !count && !schedules);
    assert(hard==150 && scheduled_after_error==148 && bulk==5625 && bulk_error_cases==5624);
    printf("{\"passed\":true,\"handler_cases\":%u,\"schedules_after_modeled_error\":%u,"
           "\"bulk_disable_cases\":%u,\"silent_bulk_error_cases\":%u,\"null_cases\":3}\n",
           hard,scheduled_after_error,bulk,bulk_error_cases);
    return 0;
}
'''
    source, binary = destination / 'actual.c', destination / 'actual'
    source.write_text(prefix + '\n\n'.join(functions) + suffix)
    loader.run([shutil.which('clang'), '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
        '-fno-omit-frame-pointer', '-fsanitize=address,undefined', source, '-o', binary], destination / 'build.log')
    result = loader.run([binary], destination / 'run.log', env=dict(os.environ,
        ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1'))
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(sha(ROOT / name) == expected for name, expected in inputs.items())
    record = json.loads(result.stdout)
    record.update(inputs=inputs, binary_sha256=sha(binary), source_sha256=sha(source),
        actual_provider_wrappers_handler_bulk_caller=True, actual_queue_enum=True,
        effects_errors_RCU_and_NAPI_modeled=True, all_read_errors_explicitly_supply_output=True,
        getter_error_output_defined=True, read_errors_acknowledge_zero=True,
        successful_reads_filtered_to_requested_queue=True, unrelated_pending_bits_preserved=True,
        uninitialized_read_executed=False, characterization_only=True, checked_IRQ_contract=False,
        complete_drain_witness=False, full_setup=False, hardware=False,
        limits=['Actual read/ack/mask bodies and two callers;register effects/errors/RCU/NAPI are synthetic fixtures.',
            'Current handlers schedule despite errors and bulk disable cannot return errors;passing characterizes that loss,not correctness.',
            'Successful reads ack only the requested queue bit;read errors ack zero. No physical lost-interrupt/client result is established.',
            'Read-error fixtures always supply an output;the separate potential uninitialized-output path is not executed.',
            'Defined error output and queue filtering are fixed;no checked IRQ error-channel,actual concurrency,drain,reset,reclaim or physical acceptance.'])
    with (destination / 'result.json').open('x') as stream: stream.write(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, handler_cases=record['handler_cases'], bulk_cases=record['bulk_disable_cases'],
        characterization_only=True, checked_IRQ_contract=False, sha256=sha(destination / 'result.json'))), flush=True)


if __name__ == '__main__': main()
