#!/usr/bin/env python3
"""Actual RX-event allocation/queue C; DMA, registers and framework are modeled."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
import test_provider_session as parent
import test_host_queue_publication as queue_source

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
static unsigned dma_calls, managed_calls, object_count, freed_buffers, freed_contexts, put_refs;
static unsigned fail_allocation, late_mutation, mutate_after, override_cpu;
static dma_addr_t addresses[7];
static void *objects[7];
static void list_add_tail(struct list_head *node,struct list_head *head) {
    node->prev=head->prev;node->next=head;head->prev->next=node;head->prev=node;
}
static void put_device(struct device *dev) { put_refs++; (void)dev; }
static void kfree(void *pointer) { freed_contexts++; (void)pointer; }
static void dma_free_coherent(struct device *dev,size_t bytes,void *buf,dma_addr_t addr) {
    (void)dev;(void)bytes;(void)buf;(void)addr;freed_buffers++;
}
static void *dma_alloc_coherent(struct device *dev,size_t bytes,dma_addr_t *addr,int flags) {
    check(dev==&dma_device && flags==GFP_KERNEL,"actual NPU DMA allocation device");
    unsigned index=dma_calls++;
    check(index<7,"one RX-event and six TX allocation attempts");
    if(index==fail_allocation)return NULL;
    *addr=addresses[index];
    if(override_cpu && index==0)return life.buffers[override_cpu-1].buf;
    if(override_cpu==9 && index==1)return objects[0];
    void *buf=calloc(1,bytes);check(buf!=NULL,"modeled coherent backing");
    objects[object_count++]=buf;
    return buf;
}
'''

FRAMEWORK = r'''
typedef uint16_t u16;
typedef uint32_t __le32;
#define __packed __attribute__((packed))
#define __aligned(n) __attribute__((aligned(n)))
#define BIT(n) (1U << (n))
#define GENMASK(h,l) ((~0U << (l)) & (~0U >> (31-(h))))
#define FIELD_PREP(mask,val) (((val)<<__builtin_ctz(mask))&(mask))
#define BUILD_BUG_ON(c) _Static_assert(!(c),"descriptor contract")
#define rcu_dereference_protected(p,c) (p)
#define spin_lock_init(p) ((void)(p))
struct mtk_wed_device { unsigned active; };
struct mt76_queue_entry { unsigned modeled; };
struct mt76_queue_regs { u32 desc_base, ring_size, cpu_idx, dma_idx; };
struct mt76_queue {
    struct mt76_queue_regs *regs;
    struct mt76_desc *desc;
    struct mt76_queue_entry *entry;
    int ndesc,buf_size,hw_idx,lock,cleanup_lock;
    u16 flags;
    dma_addr_t desc_dma;
    struct mt76_dev *dev;
};
struct mt76_dev {
    struct { void *regs; struct airoha_npu *npu; struct mtk_wed_device wed; } mmio;
    struct mt76_queue q_rx[__MT_RXQ_MAX];
    struct device *dev,*dma_dev;
    struct mutex mutex;
};
struct mt7996_dev { struct mt76_dev mt76; dma_addr_t npu_txd_addr[6]; };
static struct mt7996_dev wifi;
static unsigned char register_space[4096];
static struct mt76_queue_entry entries[512];
static unsigned fail_entry,fail_page,fail_wed,programmed,hw_calls;
static bool family7996=true;
static bool is_mt7996(struct mt76_dev *dev) { (void)dev; return family7996; }
static bool mt76_queue_is_wed_rro_ind(struct mt76_queue *q) { (void)q;return false; }
static bool mt76_queue_is_npu_tx(struct mt76_queue *q) { (void)q;return false; }
static bool mt76_queue_is_npu_rx(struct mt76_queue *q) { (void)q;return false; }
static bool mt76_queue_is_wed_rro(struct mt76_queue *q) { (void)q;return false; }
static bool mt76_queue_is_wed_tx_free(struct mt76_queue *q) { return q->flags&MT_QFLAG_WED; }
static bool mt76_queue_is_emi(struct mt76_queue *q) { (void)q;return false; }
static bool mtk_wed_device_active(struct mtk_wed_device *wed) { return wed->active; }
static bool mtk_wed_get_rx_capa(struct mtk_wed_device *wed) { (void)wed;return false; }
static void mt76_dma_queue_magic_cnt_init(struct mt76_dev *dev,struct mt76_queue *q) { (void)dev;(void)q; }
static void mt76_npu_queue_setup(struct mt76_dev *dev,struct mt76_queue *q) { (void)dev;(void)q; }
static int mt76_create_page_pool(struct mt76_dev *dev,struct mt76_queue *q) { (void)dev;(void)q;return fail_page?-ENOMEM:0; }
static int mt76_wed_dma_setup(struct mt76_dev *dev,struct mt76_queue *q,bool reset) { (void)dev;(void)q;(void)reset;return fail_wed?-EIO:0; }
static void *devm_kzalloc(struct device *dev,size_t bytes,int flags) {
    check(dev==&endpoint_device && flags==GFP_KERNEL && bytes<=sizeof(entries),"modeled software entries");
    return fail_entry?NULL:entries;
}
static void *dmam_alloc_coherent(struct device *dev,size_t bytes,dma_addr_t *addr,int flags) {
    managed_calls++;return dma_alloc_coherent(dev,bytes,addr,flags);
}
static void mt76_dma_queue_reset(struct mt76_dev *dev,struct mt76_queue *q,bool reset) {
    (void)dev;(void)reset;
    if(priv.checked_pair && q==&wifi.mt76.q_rx[MT_RXQ_TXFREE_BAND0] && q->flags==MT_NPU_Q_TXFREE(0))
        check(life.rx_attempted && life.rx_published && q->desc==life.rx_event.buf &&
              q->desc_dma==life.rx_event.addr && !managed_calls,"retained backing precedes queue address publication");
    programmed++;q->regs->desc_base=q->desc_dma;
}
static int __mt7996_npu_hw_init(struct mt7996_dev *dev) {
    check(dev==&wifi && life.rx_published && life.tx_published,"RX and TX owners precede initializer");
    hw_calls++;return -EIO;
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--header', type=Path, required=True)
    parser.add_argument('--mt76', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--mutants', action='store_true')
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    root, q = parent.ROOT, parent.loader.extract
    source, header, mt76 = args.source.resolve(), args.header.resolve(), args.mt76.resolve()
    destination = root / '.local/npu-rx-event-20261013' / args.name
    assert not destination.exists()
    paths = [source, header, Path(__file__).resolve(), parent.HARNESS,
             Path(parent.__file__), Path(parent.loader.__file__), Path(q.__file__),
             Path(queue_source.__file__), root / 'tests/npu/host-rx-event-lifetime-harness.c']
    paths += [mt76 / p for p in ('npu.c', 'dma.c', 'dma.h', 'mt76.h', 'mt7996/npu.c', 'mt7996/mt7996.h')]
    paths += [p for p in parent.SOURCE.rglob('*') if p.is_file()]
    inputs = {str(p.relative_to(root)): parent.loader.sha(p) for p in paths}
    text, htext = source.read_text(), header.read_text()
    command = parent.prepare(destination, text, htext)
    names = ('airoha_npu_dma_retained', 'airoha_npu_dma_cleanup',
             'airoha_npu_wlan_rx_event_valid', 'airoha_npu_wlan_alloc_rx_event_session',
             'airoha_npu_wlan_tx_buffer_valid', 'airoha_npu_wlan_alloc_tx_buffers_session')
    provider = '\n'.join(q.function(text, name) for name in names)
    inc = destination / 'provider-session.inc'
    inc.write_text(inc.read_text() + provider + '\n' +
                   q.function(htext, 'airoha_npu_wlan_alloc_rx_event') + '\n' +
                   q.function(htext, 'airoha_npu_wlan_alloc_tx_buffers') + '\n')
    model = parent.HARNESS.read_text()
    ops = '''struct airoha_npu { struct device *dev; struct {
int (*wlan_alloc_rx_event)(struct airoha_npu *,struct device *,struct device *,u32,u32,void **,dma_addr_t *);
int (*wlan_alloc_tx_buffers)(struct airoha_npu *,struct device *,struct device *,const u32 *,dma_addr_t *,unsigned);
} ops; };'''
    model = parent.loader.once(model, 'struct airoha_npu { struct device *dev; };', ops)
    model = parent.loader.once(model, 'static void park(void)', 'static void rx_late_mutate(void);\nstatic void park(void)')
    model = parent.loader.once(model, '    if (calls == mutate_at) {', '    rx_late_mutate();\n    if (calls == mutate_at) {')
    model = parent.loader.once(model, '#include "provider-session.inc"', PLATFORM + '\n#include "provider-session.inc"')
    common = (mt76 / 'mt76.h').read_text()
    definitions = [queue_source.macro(common, name) for name in
                   ('MT_QFLAG_WED_RING', 'MT_QFLAG_WED_TYPE', 'MT_QFLAG_WED', 'MT_NPU_Q_TXFREE')]
    definitions += [q.declaration(common, 'enum', name) for name in ('mt76_rxq_id', 'mt76_wed_type')]
    declarations = q.declaration((mt76 / 'dma.h').read_text(), 'struct', 'mt76_desc')
    hardware = 'struct mt76_wed_rro_desc { u32 modeled[2]; };\nstruct airoha_npu_tx_dma_desc { u32 modeled[52]; };\nstruct airoha_npu_rx_dma_desc { u32 modeled[4]; };\n'
    host_parts = '\n'.join(definitions) + '\n' + FRAMEWORK.split('struct mtk_wed_device', 1)[0] + declarations + '\n' + hardware
    host_parts += 'struct mtk_wed_device' + FRAMEWORK.split('struct mtk_wed_device', 1)[1]
    host_parts += '\n#define MT_RING_SIZE 16\n' + q.function((mt76 / 'npu.c').read_text(), 'mt76_npu_alloc_rx_event')
    host_parts += '\n' + q.function((mt76 / 'dma.c').read_text(), 'mt76_dma_alloc_queue')
    constants = (mt76 / 'mt7996/mt7996.h').read_text()
    host_parts += '\n#define MT_BAND0 0\n#define MT_BAND2 2\n' + '\n'.join(queue_source.macro(constants, name) for name in
                  ('MT7996_NPU_RX_RING_SIZE', 'MT7996_NPU_TX_RING_SIZE', 'MT7996_TX_RING_SIZE'))
    host_parts += '\n' + q.function((mt76 / 'mt7996/npu.c').read_text(), 'mt7996_npu_hw_init')
    (destination / 'host-queue.inc').write_text(host_parts + '\n')
    generated = destination / 'test.c'
    generated.write_text('#define main provider_matrix_main\n' + model + '\n#undef main\n#include "host-queue.inc"\n#include "' + str(root / 'tests/npu/host-rx-event-lifetime-harness.c') + '"\n')
    command = [generated if item == parent.HARNESS else item for item in command]
    flags = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all',
             '-Wno-unused-function', '-Wno-unused-variable', '-Wno-sign-compare']
    binary = destination / 'test'
    parent.loader.run(command + flags + ['-o', binary], destination / 'build.log')
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    matrix = json.loads(parent.loader.run([binary], destination / 'run.log', env=env).stdout)
    rejected = []
    if args.mutants:
        original = inc.read_text()
        changes = {
            'omit-rx-attempt': ('life->rx_attempted = true;', '(void)life;'),
            'omit-rx-publication': ('life->rx_published = true;', '(void)life;'),
            'omit-rx-status': ('err = npu_linux_control_exchange(&priv->wlan_control, NPU_CONTROL_STATUS);', 'err = 0;'),
            'omit-rx-geometry': ('if (!airoha_npu_wlan_rx_event_valid(priv)) {', 'if (false) {'),
            'omit-rx-late-record': ('life->rx_event.buf != allocated || life->rx_event.addr != allocated_addr ||', 'false ||'),
            'omit-rx-late-mailbox': ('life->buffers[i].addr != mailboxes[i].addr', 'false'),
            'omit-tx-rx-overlap': ('if (life->rx_event.buf) {', 'if (false) {'),
        }
        for name, (before, after) in changes.items():
            target = destination / 'mutants' / name
            target.mkdir(parents=True)
            function_name = 'airoha_npu_wlan_tx_buffer_valid' if name == 'omit-tx-rx-overlap' else 'airoha_npu_wlan_alloc_rx_event_session'
            body = q.function(text, function_name)
            modified = parent.loader.once(body, before, after)
            inc.write_text(parent.loader.once(original, body, modified))
            mutant = target / 'test'
            parent.loader.run(command + flags + ['-o', mutant], target / 'build.log')
            done = parent.loader.run([mutant], target / 'run.log', env=env, accepted=11)
            assert 'FAIL[session]' in done.stderr and 'AddressSanitizer' not in done.stderr
            rejected.append(dict(name=name, oracle=done.stderr.strip(), sha256=parent.loader.sha(mutant)))
        inc.write_text(original)
    assert matrix['passed'] and all(parent.loader.sha(root / p) == digest for p, digest in inputs.items())
    result = dict(passed=True, matrix=matrix, mutants=rejected, inputs=inputs,
                  binary_sha256=parent.loader.sha(binary), sanitizers=['address', 'undefined', 'leak'],
                  limits=['Actual provider allocation/binding/cleanup, inline wrappers, mt76 allocation hook/queue allocator and mt7996 TX allocator caller C.',
                          'DMA backing/device refs/register programming/page pool/entries/WED and transport delivery are modeled.',
                          'No native API22 enrollment/admission or complete strict setup/lifecycle/physical drain/router/client acceptance.',
                          'Fixture-only frees/resets are not production retirement.'])
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=matrix['cases'], mutants=len(rejected))))


if __name__ == '__main__':
    main()
