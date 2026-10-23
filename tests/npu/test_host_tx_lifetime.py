#!/usr/bin/env python3
"""Execute actual provider-owned TX allocations, caller and retained cleanup C."""
import argparse
import json
import os
from pathlib import Path
import sys
import re
import shutil

sys.dont_write_bytecode = True
import test_provider_session as parent

PLATFORM = r'''
#define IS_ALIGNED(v,a) (!((v) & ((a)-1)))
#define AIROHA_NPU_MBOX_SIZE 256
#define LIST_HEAD(name) struct list_head name = {&name,&name}
#define DEFINE_MUTEX(name) struct mutex name = {.native=PTHREAD_MUTEX_INITIALIZER}
#define dev_warn(...) ((void)0)
#define list_for_each_entry(pos,head,member) \
    for (struct list_head *node=(head)->next; node!=(head) && \
         ((pos)=(void *)((char *)node-__builtin_offsetof(__typeof__(*(pos)),member)),1); node=node->next)
static LIST_HEAD(airoha_npu_retained_dma);
static DEFINE_MUTEX(airoha_npu_retained_lock);
static struct device other_device;
static unsigned dma_calls,fail_allocation,object_count,freed_tx,freed_contexts,put_refs,mutation;
static dma_addr_t addresses[6];
static void *objects[6];
static size_t allocated_bytes[6];
static u32 *mutable_sizes;
static void list_add_tail(struct list_head *node,struct list_head *head) {
    node->prev=head->prev;node->next=head;head->prev->next=node;head->prev=node;
}
static void put_device(struct device *dev) { put_refs++;(void)dev; }
static void kfree(void *pointer) { freed_contexts++;(void)pointer; }
static void dma_free_coherent(struct device *dev,size_t bytes,void *buf,dma_addr_t addr) {
    (void)dev;(void)bytes;(void)buf;(void)addr;freed_tx++;
}
static void *dma_alloc_coherent(struct device *dev,size_t bytes,dma_addr_t *addr,int flags) {
    check(dev==&dma_device && flags==GFP_KERNEL,"actual NPU DMA device");
    unsigned index=dma_calls++;check(index<6,"at most six allocation attempts");
    allocated_bytes[index]=bytes;
    if(index==fail_allocation)return NULL;
    void *buf=calloc(1,bytes);check(buf!=NULL,"model backing allocation");
    objects[object_count++]=buf;*addr=addresses[index];
    if(index==3) {
        if(mutation==1)priv.native_plan[1][0]^=0x100000;
        if(mutation==2)priv.boot_identity^=1;
        if(mutation==3)life.endpoint=&other_device;
        if(mutation==4)life.tx_buffers[0].addr^=0x10000;
        if(mutation==5)life.tx_buffers[0].bytes++;
        if(mutation==6)mutable_sizes[4]=1;
        if(mutation==7)life.buffers[3].addr^=256;
        if(mutation==8)life.buffers[3].buf=(void *)(uintptr_t)0x1234;
        if(mutation==9)life.endpoint_base+=0x1000000;
        if(mutation==10)life.endpoint_bytes+=4096;
        if(mutation==11)life.bound_serial++;
    }
    return buf;
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--header',type=Path,required=True)
    parser.add_argument('--host',type=Path,required=True)
    parser.add_argument('--mt76-npu',type=Path,default=parent.ROOT / '.local/merge-nonoc-20260923/mt76-merged/npu.c')
    parser.add_argument('--name',required=True)
    parser.add_argument('--before-host',type=Path)
    parser.add_argument('--alias-counterexample',action='store_true')
    parser.add_argument('--mutants',action='store_true')
    args=parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    root=parent.ROOT; q=parent.loader.extract
    destination=root / '.local/npu-host-tx-lifetime-20261011' / args.name
    assert not destination.exists()
    source,header=args.source.resolve(),args.header.resolve()
    host=(args.before_host or args.host).resolve()
    paths=[source,header,host,parent.HARNESS,Path(__file__).resolve(),Path(parent.__file__),
           Path(parent.loader.__file__),Path(q.__file__),root/'tests/npu/host-tx-lifetime-harness.c',
           args.host.resolve().with_name('mt7996.h'), args.mt76_npu.resolve()]
    paths += [path for path in parent.SOURCE.rglob('*') if path.is_file()]
    inputs={str(path.relative_to(root)):parent.loader.sha(path) for path in paths}
    text,htext=source.read_text(),header.read_text()
    function_names=('airoha_npu_dma_retained','airoha_npu_dma_cleanup',
        'airoha_npu_wlan_rx_event_valid',
        'airoha_npu_wlan_tx_buffer_valid','airoha_npu_wlan_alloc_tx_buffers_session')
    if 'airoha_npu_wlan_validate_tx_buffers_session' in text:
        function_names += ('airoha_npu_wlan_validate_tx_buffers_session',)
    functions=[q.function(text,name) for name in function_names]
    extra='\n'.join(body for name,body in zip(function_names,functions) if name not in parent.FUNCTIONS)+'\n'+q.function(htext,'airoha_npu_wlan_alloc_tx_buffers')+'\n'
    if 'airoha_npu_wlan_validate_tx_buffers_session' in text:
        extra += q.function(htext, 'airoha_npu_wlan_validate_tx_buffers') + '\n'
    command=parent.prepare(destination,text,htext)
    shutil.copyfile(__file__, destination / 'driver-at-run.py')
    shutil.copyfile(root / 'tests/npu/host-tx-lifetime-harness.c', destination / 'harness-at-run.c')
    inc=destination/'provider-session.inc'
    inc.write_text(inc.read_text()+extra)
    ops='struct airoha_npu { struct device *dev; struct { int (*wlan_alloc_tx_buffers)(struct airoha_npu *,struct device *,struct device *,const u32 *,dma_addr_t *,unsigned); int (*wlan_validate_tx_buffers)(struct airoha_npu *,struct device *,struct device *,const u32 *,const dma_addr_t *,unsigned); } ops; };'
    model=parent.loader.once(parent.HARNESS.read_text(),'struct airoha_npu { struct device *dev; };',ops)
    model=parent.loader.once(model,'static struct device *get_device(struct device *dev) { return dev; }',
                            'static struct device *get_device(struct device *dev) { dev->unused++; return dev; }')
    model=parent.loader.once(model,'#include "provider-session.inc"',PLATFORM+'\n#include "provider-session.inc"')
    generated=destination/'test.c'
    generated.write_text('#define main provider_matrix_main\n'+model+'\n#undef main\n#include "'+str(root/'tests/npu/host-tx-lifetime-harness.c')+'"\n')
    command=[generated if item==parent.HARNESS else item for item in command]
    constants=args.host.resolve().with_name('mt7996.h').read_text()
    definitions=[line for line in constants.splitlines() if re.match(r'#define MT7996_(?:NPU_RX_RING_SIZE|NPU_TX_RING_SIZE|TX_RING_SIZE)\b',line)]
    host_text = host.read_text()
    host_functions = []
    if 'mt76_npu_irq_error(' in host_text:
        host_functions.append(q.function(args.mt76_npu.read_text(), 'mt76_npu_irq_error'))
    if 'mt7996_npu_prepare_tx_buffers(' in host_text:
        assert 'airoha_npu_wlan_validate_tx_buffers_session' in text
        host_functions += ['#define HAS_EARLY_TX_PREP 1',
            q.function(host_text, 'mt7996_npu_tx_buffer_sizes'),
            q.function(host_text, 'mt7996_npu_prepare_tx_buffers')]
    host_functions.append(q.function(host_text,'mt7996_npu_hw_init'))
    (destination/'host-caller.inc').write_text('\n'.join(['#define MT_BAND0 0','#define MT_BAND2 2',*definitions,
        *host_functions])+'\n')
    flags=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-Wno-unused-function','-Wno-unused-variable','-Wno-sign-compare']
    if args.before_host:flags+=['-DBEFORE_HOST']
    if args.alias_counterexample:flags+=['-DALIAS_COUNTEREXAMPLE']
    binary=destination/'test'
    parent.loader.run(command+flags+['-o',binary],destination/'build.log')
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    matrix=json.loads(parent.loader.run([binary],destination/'run.log',env=env).stdout)
    assert all(parent.loader.sha(root/path)==digest for path,digest in inputs.items())
    rejected=[]
    if args.mutants:
        assert matrix['passed'] and not args.before_host and not args.alias_counterexample
        changes={
            'omit-attempt-latch':('life->tx_attempted = true;','(void)life;'),
            'omit-publication-latch':('life->tx_published = true;','(void)life;'),
            'skip-fresh-status':('err = npu_linux_control_exchange(&priv->wlan_control, NPU_CONTROL_STATUS);','err = 0;'),
            'permit-bar-alias-overlap':('if (base < bar + life->endpoint_bytes && bar < base + bytes)','if (false)'),
            'permit-native-plan-overlap':('if (base < other + priv->native_plan[i][1] && other < base + bytes)','if (false)'),
            'omit-endpoint-identity':('!life->endpoint_bound || life->endpoint != endpoint ||','!life->endpoint_bound || false ||'),
            'omit-record-recheck':('life->tx_buffers[i].addr != captured[i].addr ||','false ||'),
            'omit-native-enrollment':('for (i = rx_published ? NPU_COLD_TXBUF_MAILBOXES : 0; i < NPU_COLD_TXBUF_RECORDS; i++) {','for (i = NPU_COLD_TXBUF_RECORDS; i < NPU_COLD_TXBUF_RECORDS; i++) {'),
            'skip-late-mailbox-address':('life->buffers[i].addr != mailboxes[i].addr','false'),
        }
        original=inc.read_text()
        for name,(old,new) in changes.items():
            target=destination/'mutants'/name
            relevant=[fragment for name,fragment in zip(function_names,functions)
                      if name in ('airoha_npu_wlan_tx_buffer_valid',
                                  'airoha_npu_wlan_alloc_tx_buffers_session') and old in fragment]
            assert len(relevant)==1,(name,'mutation must target one extracted function')
            occurrences = 2 if name in ('skip-fresh-status', 'omit-record-recheck', 'omit-endpoint-identity') else 1
            assert relevant[0].count(old) == occurrences, (name, 'unexpected guard count')
            replacement = relevant[0].replace(old, new) if occurrences > 1 else parent.loader.once(relevant[0],old,new)
            mutated=parent.loader.once(original,relevant[0],replacement)
            target.mkdir(parents=True)
            inc.write_text(mutated)
            shutil.copyfile(inc, target / inc.name)
            mutant=target/'test'
            parent.loader.run(command+flags+['-o',mutant],target/'build.log')
            done=parent.loader.run([mutant],target/'run.log',env=env,accepted=11)
            assert 'FAIL[session]' in done.stderr and 'AddressSanitizer' not in done.stderr
            rejected.append(dict(name=name,oracle=done.stderr.strip(),binary_sha256=parent.loader.sha(mutant)))
        inc.write_text(original)
        if 'mt7996_npu_prepare_tx_buffers(' in host_text:
            host_inc = destination / 'host-caller.inc'
            host_original = host_inc.read_text()
            validation_call = re.search(r'\terr = airoha_npu_wlan_validate_tx_buffers\([^;]+;', host_original)
            assert validation_call is not None
            variants = (
                ('omit-prepared-validation', host_inc, host_original, validation_call.group(), '\terr = 0;',
                 'stale or consumed prepared lease must not reach hardware entry'),
                ('omit-prepared-consumption', host_inc, host_original, 'dev->npu_txd_claimed = true;', '(void)0;',
                 'late hardware attempt consumes the lease even when it fails'),
                ('omit-prepared-serial', inc, original, 'life->tx_serial != snapshot.client.base.serial ||', 'false ||',
                 'stale or consumed prepared lease must not reach hardware entry'),
            )
            for name, container, contents, old, new, diagnostic in variants:
                assert contents.count(old) == 1, ('early-mutant-anchor', name)
                target = destination / 'mutants' / name
                target.mkdir()
                container.write_text(parent.loader.once(contents, old, new))
                shutil.copyfile(container, target / container.name)
                mutant = target / 'test'
                compiled = parent.loader.run(command+flags+['-o',mutant],target/'build.log')
                done = parent.loader.run([mutant],target/'run.log',env=env,accepted=11)
                assert 'FAIL[session]' in done.stderr and diagnostic in done.stderr
                assert 'AddressSanitizer' not in done.stderr and 'runtime error:' not in done.stderr
                rejected.append(dict(name=name, compiled=compiled.returncode == 0,
                    run_returncode=done.returncode, intended_assertion=diagnostic, oracle=done.stderr.strip(),
                    binary_sha256=parent.loader.sha(mutant), source_sha256=parent.loader.sha(container)))
                container.write_text(contents)
    artifacts={str(path.relative_to(root)):parent.loader.sha(path) for path in destination.rglob('*') if path.is_file()}
    result=dict(passed=matrix['passed'],counterexample=bool(args.before_host or args.alias_counterexample),matrix=matrix,inputs=inputs,mutants=rejected,
        artifacts=artifacts, early_TX_preparation_executed='mt7996_npu_prepare_tx_buffers(' in host_text,
        binary_sha256=parent.loader.sha(binary),sanitizers=['address','undefined','leak'],
        limits=['Actual provider allocator/binding/cleanup, actual inline allocation wrapper and actual mt7996 caller C.',
                'DMA allocations/device refs/devres/backing/transport are modeled. STATUS validation is not physical drain proof.',
                'Native callbacks are not exercised here; full setup/lifecycle/hardware/client acceptance remains open.',
                'Direct fixture frees/reset are test-only, never a production retirement operation.'])
    (destination/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(matrix))


if __name__=='__main__':main()
