/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef uint64_t dma_addr_t;
typedef uint64_t phys_addr_t;
typedef unsigned int gfp_t;
typedef int irqreturn_t;
typedef struct { int held; } spinlock_t;
struct work_struct { int unused; };
struct device { int unused; };
struct regmap { int unused; };
#define __iomem
#define IS_BUILTIN(x) 1
#define IS_MODULE(x) 0
#define BIT(n) (1ul << (n))
#define GENMASK(h,l) (((~0ul) >> (sizeof(unsigned long)*8-1-(h))) & ((~0ul) << (l)))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define IRQ_NONE 0
#define IRQ_HANDLED 1
#define IRQF_SHARED 0x80u
#define IRQF_NO_AUTOEN 0x80000u
#define GFP_KERNEL 0
#define MT76_NPU_RX_BUF_SIZE 2048
/* Symbolic routing tags;not a physical ordinary-queue register mask. */
#define MT_INT_RX(q) (0xb4000000u | (u32)(q))
#define MT_NPU_Q_RX(q) (0xc0000000u | (u32)(q))

/* ACTUAL_TYPES */

struct mt76_dev;
struct mt76_queue { struct mt76_dev *dev; unsigned int flags; };
struct napi_struct { unsigned int qid; bool added, enabled; };
struct queue_ops { int (*alloc)(struct mt76_dev *,struct mt76_queue *,int,int,int,int); };
struct mt76_dev {
    struct { struct airoha_npu *npu; spinlock_t irq_lock; struct mt76_npu_irq npu_irq; } mmio;
    struct mt76_queue q_rx[__MT_RXQ_MAX];
    struct napi_struct napi[__MT_RXQ_MAX];
    struct queue_ops *queue_ops;
    struct device *dev;
    void *napi_dev;
    int mutex;
};
struct mt7996_dev { struct mt76_dev mt76; };
static struct mt7996_dev chip;
static struct airoha_npu npu;
static struct regmap map;
static struct device device;
static int mutex_depth, spin_depth, rcu_depth, rcu_locks, rcu_unlocks;
static unsigned int schedules, ordinary, errors_logged, stage_failure, stage_calls;
static unsigned int allocations, names, requests, fills, fail_allocation, fail_name, fail_request, frees;
static unsigned int enables[2], disables[2], depth[2];
static bool claimed[2], late_fault, late_done, active_handler;
static int late_queue, target_queue;
static u32 pending, mask_bits[2], unrelated[2], ordinary_mask;
enum operation { READ_STATUS, ACK, ARM, MASK, READ_MASK, OP_MAX };
static struct { int op, q, error; unsigned int nth; bool effect, partial, mismatch; } fault;
static unsigned int operations[OP_MAX], accesses;
static int mt76_npu_rx_poll(struct napi_struct *napi,int budget) { return 0; }
static irqreturn_t mt76_npu_irq_handler(int irq,void *cookie);

static void mutex_lock(int *mutex) { assert(mutex==&chip.mt76.mutex && !mutex_depth); mutex_depth=1; }
static void mutex_unlock(int *mutex) { assert(mutex==&chip.mt76.mutex && mutex_depth==1); mutex_depth=0; }
static void assert_mutex(int *mutex) { assert(mutex==&chip.mt76.mutex && mutex_depth==1); }
#define lockdep_assert_held(p) assert_mutex(p)
#define lockdep_is_held(p) (mutex_depth==1)
static unsigned long spin_take(spinlock_t *lock) {
    assert(lock==&chip.mt76.mmio.irq_lock && !lock->held && !spin_depth);
    lock->held=1;spin_depth=1;return 0;
}
static void spin_drop(spinlock_t *lock,unsigned long flags) {
    assert(lock->held==1 && spin_depth==1 && !flags);lock->held=0;spin_depth=0;
}
#define spin_lock_irqsave(p,f) do { (f)=spin_take(p); } while(0)
#define spin_unlock_irqrestore(p,f) spin_drop(p,f)
static void rcu_read_lock(void) { rcu_depth++;rcu_locks++; }
static void rcu_read_unlock(void) { assert(rcu_depth>0);rcu_depth--;rcu_unlocks++; }
#define rcu_dereference(p) (assert(rcu_depth>0),(p))
#define rcu_dereference_protected(p,c) (assert(mutex_depth==1),(p))
static int line_queue(int irq) { return irq==npu.irqs[0]?0:irq==npu.irqs[1]?1:-1; }
static void disable_irq_nosync(int irq) {
    int q=line_queue(irq);assert(q>=0 && claimed[q] && spin_depth==1);
    depth[q]++;disables[q]++;
}
static void enable_irq(int irq) {
    int q=line_queue(irq);assert(q>=0 && claimed[q] && !spin_depth && !rcu_depth && mutex_depth==1);
    assert(chip.mt76.napi[MT_RXQ_NPU0].enabled && chip.mt76.napi[MT_RXQ_NPU1].enabled);
    assert(depth[q]>0);depth[q]--;enables[q]++;
    if(late_fault && !late_done && q==late_queue) {
        late_done=true;target_queue=q;pending|=(u32)NPU_IRQ_RX_MASK(q);
        fault.op=READ_STATUS;fault.q=q;fault.error=-EIO;fault.nth=1;
        active_handler=true;
        assert(mt76_npu_irq_handler(irq,&chip.mt76.q_rx[MT_RXQ_NPU0+q])==IRQ_HANDLED);
        active_handler=false;
    }
}
static void napi_schedule(struct napi_struct *napi) {
    assert(spin_depth==1 && rcu_depth>0 && napi->added && napi->enabled);
    assert(!chip.mt76.mmio.npu_irq.error && chip.mt76.mmio.npu_irq.running);schedules++;
}
static void netif_napi_add(void *dev,struct napi_struct *napi,int (*poll)(struct napi_struct *,int)) {
    assert(mutex_depth==1 && !spin_depth && poll==mt76_npu_rx_poll && !napi->added);napi->added=true;
}
static void napi_enable(struct napi_struct *napi) { assert(napi->added && !napi->enabled);napi->enabled=true; }
static int mt76_napi_add(struct mt76_dev *dev,unsigned int qid,int (*poll)(struct napi_struct *,int)) {
    assert(dev==&chip.mt76 && qid<__MT_RXQ_MAX);
    if(dev->napi[qid].added)return -EEXIST;
    netif_napi_add(dev->napi_dev,&dev->napi[qid],poll);return 0;
}
static bool mt76_napi_enable(struct mt76_dev *dev,unsigned int qid) {
    assert(dev==&chip.mt76 && qid<__MT_RXQ_MAX);
    napi_enable(&dev->napi[qid]);return true;
}
static void mt76_npu_fill_rx_queue(struct mt76_dev *dev,struct mt76_queue *q) {
    assert(dev==&chip.mt76 && mutex_depth==1);fills++;
}
static int allocate(struct mt76_dev *dev,struct mt76_queue *q,int id,int count,int bytes,int reg) {
    assert(dev==&chip.mt76 && mutex_depth==1 && count==512 && bytes==MT76_NPU_RX_BUF_SIZE);
    allocations++;q->dev=dev;return fail_allocation?-ENOMEM:0;
}
static struct queue_ops queue_ops={allocate};
static const char *devm_kasprintf(struct device *dev,gfp_t flags,const char *format,int q) {
    assert(dev==&device && mutex_depth==1 && q>=0 && q<2);names++;return fail_name?NULL:"fixture";
}
static int devm_request_irq(struct device *dev,int irq,irqreturn_t (*handler)(int,void *),
                            unsigned int flags,const char *name,void *cookie) {
    int q=line_queue(irq);assert(q>=0 && dev==&device && handler==mt76_npu_irq_handler && mutex_depth==1);
    assert(flags==IRQF_NO_AUTOEN && !(flags&IRQF_SHARED) && !spin_depth);
    assert(cookie==&chip.mt76.q_rx[MT_RXQ_NPU0+q]);requests++;
    if(fail_request || claimed[q])return -EBUSY;
    claimed[q]=true;depth[q]=1;return 0;
}
static void devm_free_irq(struct device *dev,int irq,void *cookie) {
    int q=line_queue(irq);
    assert(q>=0 && dev==&device && mutex_depth==1 && !spin_depth && !rcu_depth);
    assert(cookie==&chip.mt76.q_rx[MT_RXQ_NPU0+q] && claimed[q]);
    assert(chip.mt76.mmio.npu_irq.closing && !chip.mt76.mmio.npu_irq.running);
    assert(!(chip.mt76.mmio.npu_irq.requested&BIT(q)));
    claimed[q]=false;depth[q]=0;frees++;
}
static int event(enum operation op,int q) {
    assert(spin_depth==1 && q>=0 && q<2);accesses++;operations[op]++;
    if(fault.op==(int)op && fault.q==q && fault.nth && !--fault.nth)return fault.error;
    return 0;
}
static int regmap_read(struct regmap *m,u32 reg,u32 *value) {
    assert(m==&map && value);
    if(reg==REG_IRQ_STATUS) {
        int err=event(READ_STATUS,target_queue);if(!err || fault.partial)*value=pending;return err;
    }
    int q=reg==REG_IRQ_RXDONE(0)?0:reg==REG_IRQ_RXDONE(1)?1:-1;
    target_queue=q;
    int err=event(READ_MASK,q);if(!err || fault.partial)*value=mask_bits[q]^((fault.mismatch&&fault.q==q)?NPU_IRQ_RX_MASK(q):0);
    return err;
}
static int regmap_write(struct regmap *m,u32 reg,u32 value) {
    assert(m==&map && reg==REG_IRQ_STATUS && value==NPU_IRQ_RX_MASK(target_queue));
    int err=event(ACK,target_queue);if(!err || fault.effect)pending&=~value;return err;
}
static int regmap_set_bits(struct regmap *m,u32 reg,u32 bits) {
    int q=reg==REG_IRQ_RXDONE(0)?0:reg==REG_IRQ_RXDONE(1)?1:-1;
    assert(m==&map && q>=0 && bits==NPU_IRQ_RX_MASK(q));
    target_queue=q;
    int err=event(ARM,q);if(!err || fault.effect)mask_bits[q]|=bits;return err;
}
static int regmap_clear_bits(struct regmap *m,u32 reg,u32 bits) {
    int q=reg==REG_IRQ_RXDONE(0)?0:reg==REG_IRQ_RXDONE(1)?1:-1;
    assert(m==&map && q>=0 && bits==NPU_IRQ_RX_MASK(q));
    target_queue=q;
    int err=event(MASK,q);if(!err || fault.effect)mask_bits[q]&=~bits;return err;
}
static int stage(unsigned int number) { stage_calls++;return stage_failure==number?-(int)(200+number):0; }
static int is_mt7996(struct mt76_dev *dev) { assert(dev==&chip.mt76);return 1; }
static int mt7996_npu_rx_event_validate(struct mt7996_dev *dev) { assert(dev==&chip);return stage(1); }
#define STAGE(n,f) static int f(struct mt7996_dev *d,struct airoha_npu *p) { assert(d==&chip && p==&npu);return stage(n); }
STAGE(2,mt7996_npu_offload_init)
STAGE(3,mt7996_npu_rxd_init)
STAGE(3,mt7992_npu_rxd_init)
STAGE(4,mt7996_npu_txd_init)
STAGE(5,mt7996_npu_rx_event_init)
STAGE(6,mt7996_npu_set_pcie_addr)
STAGE(7,mt7996_npu_tx_done_init)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
static void mt7996_irq_enable(struct mt7996_dev *dev,u32 mask) { assert(dev==&chip && !spin_depth);ordinary++;ordinary_mask=mask; }
#define dev_err_ratelimited(d,f,e) do { assert((d)==&device && (e)<0 && !spin_depth);errors_logged++; } while(0)

/* ACTUAL_BODIES */

static void reset(void) {
    assert(!spin_depth && !mutex_depth && !rcu_depth);
    memset(&chip,0,sizeof(chip));memset(&npu,0,sizeof(npu));
    memset(depth,0,sizeof(depth));memset(claimed,0,sizeof(claimed));
    memset(enables,0,sizeof(enables));memset(disables,0,sizeof(disables));memset(operations,0,sizeof(operations));
    fault=(typeof(fault)){.op=-1,.q=-1,.effect=true};
    late_fault=late_done=active_handler=false;late_queue=0;target_queue=0;
    schedules=ordinary=errors_logged=stage_failure=stage_calls=allocations=names=requests=fills=0;
    fail_allocation=fail_name=fail_request=accesses=rcu_locks=rcu_unlocks=frees=0;
    mask_bits[0]=unrelated[0]=0x5a000008u;mask_bits[1]=unrelated[1]=0xa5000020u;pending=0x80030005u;
    chip.mt76.mmio.npu=&npu;chip.mt76.queue_ops=&queue_ops;chip.mt76.dev=&device;
    npu.regmap=&map;npu.irqs[0]=91;npu.irqs[1]=92;
    npu.ops.wlan_irq_read=airoha_npu_wlan_irq_read_checked;
    npu.ops.wlan_irq_ack=airoha_npu_wlan_irq_ack_checked;
    npu.ops.wlan_irq_arm=airoha_npu_wlan_irq_arm_checked;
    npu.ops.wlan_irq_mask=airoha_npu_wlan_irq_mask_checked;
    for(unsigned int q=0;q<__MT_RXQ_MAX;q++){chip.mt76.q_rx[q].dev=&chip.mt76;chip.mt76.napi[q].qid=q;}
}
static void register_queues(void) {
    for(int q=0;q<2;q++)assert(mt76_npu_rx_queue_init(&chip.mt76,&chip.mt76.q_rx[MT_RXQ_NPU0+q])==0);
    assert(chip.mt76.mmio.npu_irq.requested==3 && chip.mt76.mmio.npu_irq.blocked==3);
    assert(depth[0]==1 && depth[1]==1 && !enables[0] && !enables[1] && !accesses);
}
static int start(void) { mutex_lock(&chip.mt76.mutex);int err=__mt7996_npu_hw_init(&chip);mutex_unlock(&chip.mt76.mutex);return err; }
static int stop(void) { mutex_lock(&chip.mt76.mutex);int err=mt76_npu_disable_irqs(&chip.mt76);mutex_unlock(&chip.mt76.mutex);return err; }
static void running(void) { register_queues();assert(start()==0 && !depth[0] && !depth[1]); }
static void configure(int op,int q,int error,bool effect,bool partial) {
    fault=(typeof(fault)){.op=op,.q=q,.error=error,.nth=1,.effect=effect,.partial=partial};target_queue=q;
}
static void unchanged_unrelated(void) {
    for(int q=0;q<2;q++)assert((mask_bits[q]&~NPU_IRQ_RX_MASK(q))==unrelated[q]);
    assert((pending&~0x30000u)==0x80000005u);
}
static void quarantined(int error) {
    assert(chip.mt76.mmio.npu_irq.error==error && !chip.mt76.mmio.npu_irq.running);
    assert(depth[0]>0 && depth[1]>0 && mt76_npu_io_admit(&chip.mt76)==error && !mt76_npu_irq_poll_allowed(&chip.mt76));
    unsigned int previous=accesses, blocked[2]={disables[0],disables[1]};
    for(int q=0;q<2;q++)assert(mt76_npu_rearm_irq(&chip.mt76,MT_RXQ_NPU0+q)==error);
    assert(accesses==previous && disables[0]==blocked[0] && disables[1]==blocked[1]);
    unsigned int stages=stage_calls;
    assert(mt76_npu_irq_error(&chip.mt76)==error);
    assert(start()==error && accesses==previous && stage_calls==stages);unchanged_unrelated();
}
int main(void) {
    unsigned int cases=0, handler_cases=0, start_cases=0, rearm_cases=0, stop_cases=0, late_cases=0;
    reset();assert(mt76_npu_io_admit(&chip.mt76)==-ESHUTDOWN);register_queues();
    assert(start()==0 && stage_calls==7 && mt76_npu_io_admit(&chip.mt76)==0);cases++;
    for(int q=0;q<2;q++) {
        reset();running();target_queue=q;
        assert(mt76_npu_irq_handler(91+q,&chip.mt76.q_rx[MT_RXQ_NPU0+q])==IRQ_HANDLED && schedules==1);
        assert(!(mask_bits[q]&NPU_IRQ_RX_MASK(q)) && !(pending&NPU_IRQ_RX_MASK(q)));
        assert(mt76_npu_rearm_irq(&chip.mt76,MT_RXQ_NPU0+q)==0 && (mask_bits[q]&NPU_IRQ_RX_MASK(q)));
        assert(!chip.mt76.mmio.npu_irq.error && !depth[0] && !depth[1]);unchanged_unrelated();cases++;
        reset();running();target_queue=q;pending&=~NPU_IRQ_RX_MASK(q);
        unsigned int old=accesses;
        assert(mt76_npu_irq_handler(91+q,&chip.mt76.q_rx[MT_RXQ_NPU0+q])==IRQ_NONE && !schedules && accesses==old+1);cases++;
    }
    const int errors[]={-EIO,-ETIMEDOUT,9};
    const int handler_ops[]={READ_STATUS,MASK,READ_MASK,ACK};
    const int update_ops[]={ARM,READ_MASK};
    for(int q=0;q<2;q++)for(unsigned int e=0;e<ARRAY_SIZE(errors);e++)for(int effect=0;effect<2;effect++)for(int partial=0;partial<2;partial++) {
        int expected=errors[e]<0?errors[e]:-EIO;
        for(unsigned int op=0;op<ARRAY_SIZE(handler_ops);op++) {
            reset();running();configure(handler_ops[op],q,errors[e],effect,partial);
            assert(mt76_npu_irq_handler(91+q,&chip.mt76.q_rx[MT_RXQ_NPU0+q])==IRQ_HANDLED && !schedules);
            quarantined(expected);handler_cases++;cases++;
        }
        for(unsigned int op=0;op<ARRAY_SIZE(update_ops);op++) {
            reset();register_queues();configure(update_ops[op],q,errors[e],effect,partial);
            assert(start()==expected && !enables[0] && !enables[1]);quarantined(expected);start_cases++;cases++;
            reset();running();configure(update_ops[op],q,errors[e],effect,partial);
            assert(mt76_npu_rearm_irq(&chip.mt76,MT_RXQ_NPU0+q)==expected);quarantined(expected);rearm_cases++;cases++;
        }
        for(unsigned int op=0;op<ARRAY_SIZE(handler_ops);op++) {
            reset();running();configure(handler_ops[op],q,errors[e],effect,partial);
            assert(stop()==expected);quarantined(expected);stop_cases++;cases++;
        }
    }
    for(int q=0;q<2;q++) {
        reset();register_queues();fault.mismatch=true;fault.q=q;target_queue=q;
        assert(start()==-EIO);quarantined(-EIO);cases++;
        reset();running();fault.mismatch=true;fault.q=q;target_queue=q;
        assert(mt76_npu_irq_handler(91+q,&chip.mt76.q_rx[MT_RXQ_NPU0+q])==IRQ_HANDLED && !schedules);
        quarantined(-EIO);cases++;
        reset();running();fault.mismatch=true;fault.q=q;
        assert(mt76_npu_rearm_irq(&chip.mt76,MT_RXQ_NPU0+q)==-EIO);quarantined(-EIO);cases++;
        reset();running();fault.mismatch=true;fault.q=q;
        assert(stop()==-EIO);quarantined(-EIO);cases++;
        reset();register_queues();late_fault=true;late_queue=q;
        assert(start()==-EIO && late_done && enables[0]==1 && enables[1]==1);
        assert(depth[0]==1 && depth[1]==1 && !schedules);quarantined(-EIO);late_cases++;cases++;
    }
    for(unsigned int stage=1;stage<=7;stage++) {
        reset();register_queues();stage_failure=stage;
        assert(start()==-(int)(200+stage) && stage_calls==stage && !accesses && !enables[0] && !enables[1]);cases++;
    }
    reset();running();assert(stop()==0 && depth[0]==1 && depth[1]==1 && !chip.mt76.mmio.npu_irq.running);
    assert(stop()==0 && depth[0]==1 && depth[1]==1);cases++;
    assert(mt76_npu_rearm_irq(&chip.mt76,MT_RXQ_NPU0)==-ESHUTDOWN && start()==0 && !depth[0] && !depth[1]);cases++;
    for(int q=0;q<2;q++) {
        reset();npu.irqs[1]=npu.irqs[0];
        assert(mt76_npu_rx_queue_init(&chip.mt76,&chip.mt76.q_rx[MT_RXQ_NPU0+q])==-EINVAL && !allocations && !requests);cases++;
        reset();npu.ops.wlan_irq_mask=NULL;
        assert(mt76_npu_rx_queue_init(&chip.mt76,&chip.mt76.q_rx[MT_RXQ_NPU0+q])==-EOPNOTSUPP && !allocations && !requests);cases++;
        reset();fail_request=1;
        assert(mt76_npu_rx_queue_init(&chip.mt76,&chip.mt76.q_rx[MT_RXQ_NPU0+q])==-EBUSY && !chip.mt76.mmio.npu_irq.requested);
        assert(chip.mt76.napi[MT_RXQ_NPU0+q].added && !chip.mt76.napi[MT_RXQ_NPU0+q].enabled && !disables[0] && !disables[1]);cases++;
    }
    unsigned int ordinary_cases=0;
    for(int q=0;q<__MT_RXQ_MAX;q++) {
        if(q==MT_RXQ_NPU0 || q==MT_RXQ_NPU1)continue;
        reset();mt7996_rx_poll_complete(&chip.mt76,(enum mt76_rxq_id)q);
        assert(ordinary==1 && ordinary_mask==(0xb4000000u|(u32)q) && !accesses && !rcu_locks);ordinary_cases++;cases++;
    }
    reset();running();chip.mt76.mmio.npu=NULL;
    assert(mt76_npu_irq_handler(91,&chip.mt76.q_rx[MT_RXQ_NPU0])==IRQ_HANDLED && !schedules);
    quarantined(-ENODEV);cases++;
    reset();
    assert(!airoha_npu_wlan_irq_supported(NULL));
    u32 status=UINT_MAX;
    assert(airoha_npu_wlan_irq_read(NULL,0,&status)==-EOPNOTSUPP && status==0);
    assert(airoha_npu_wlan_irq_read(&npu,0,NULL)==-EINVAL && !accesses);cases++;
    for(int q=-1;q<3;q++) {
        if(q==0 || q==1)continue;
        reset();status=UINT_MAX;
        assert(airoha_npu_wlan_irq_read(&npu,q,&status)==-EINVAL && status==0);
        assert(airoha_npu_wlan_irq_ack(&npu,q,0)==-EINVAL);
        assert(airoha_npu_wlan_irq_arm(&npu,q)==-EINVAL && airoha_npu_wlan_irq_mask(&npu,q)==-EINVAL && !accesses);cases++;
    }
    for(int q=0;q<2;q++) {
        reset();
        assert(airoha_npu_wlan_irq_ack(&npu,q,0)==0);
        assert(airoha_npu_wlan_irq_ack(&npu,q,NPU_IRQ_RX_MASK(1-q))==-EINVAL && !accesses);cases++;
        reset();mutex_lock(&chip.mt76.mutex);
        assert(mt76_npu_start_irqs(&chip.mt76)==-EAGAIN && !accesses);
        mutex_unlock(&chip.mt76.mutex);cases++;
        reset();register_queues();
        assert(mt76_npu_rx_queue_init(&chip.mt76,&chip.mt76.q_rx[MT_RXQ_NPU0+q])==-EBUSY && requests==2);cases++;
        reset();fail_allocation=1;
        assert(mt76_npu_rx_queue_init(&chip.mt76,&chip.mt76.q_rx[MT_RXQ_NPU0+q])==-ENOMEM && !names && !requests);cases++;
        reset();fail_name=1;
        assert(mt76_npu_rx_queue_init(&chip.mt76,&chip.mt76.q_rx[MT_RXQ_NPU0+q])==-ENOMEM && !requests);cases++;
        reset();running();
        assert(mt76_npu_irq_handler(92-q,&chip.mt76.q_rx[MT_RXQ_NPU0+q])==IRQ_NONE && !schedules);cases++;
    }
    for(int partial=0;partial<=2;partial++) {
        reset();
        for(int q=0;q<partial;q++)assert(!mt76_npu_rx_queue_init(&chip.mt76,&chip.mt76.q_rx[MT_RXQ_NPU0+q]));
        mt76_npu_shutdown_irqs(&chip.mt76);
        assert(frees==(unsigned int)partial && !claimed[0] && !claimed[1]);
        assert(chip.mt76.mmio.npu_irq.closing && !chip.mt76.mmio.npu_irq.requested && !chip.mt76.mmio.npu_irq.running);
        unsigned int old_accesses=accesses,old_requests=requests;
        mt76_npu_shutdown_irqs(&chip.mt76);
        assert(frees==(unsigned int)partial && accesses==old_accesses);
        assert(start()==-ESHUTDOWN && mt76_npu_rearm_irq(&chip.mt76,MT_RXQ_NPU0)==-ESHUTDOWN);
        assert(mt76_npu_rx_queue_init(&chip.mt76,&chip.mt76.q_rx[MT_RXQ_NPU0])==-ESHUTDOWN && requests==old_requests);
        cases++;
    }
    for(int q=0;q<2;q++) {
        reset();running();configure(MASK,q,-EIO,false,false);
        mt76_npu_shutdown_irqs(&chip.mt76);
        assert(frees==2 && !claimed[0] && !claimed[1] && chip.mt76.mmio.npu_irq.error==-EIO);cases++;
    }
    reset();running();chip.mt76.mmio.npu=NULL;
    mt76_npu_shutdown_irqs(&chip.mt76);
    assert(frees==2 && !claimed[0] && !claimed[1] && chip.mt76.mmio.npu_irq.error);cases++;
    reset();npu.irqs[0]=0;register_queues();mt76_npu_shutdown_irqs(&chip.mt76);
    assert(frees==2 && chip.mt76.mmio.npu_irq.line[0]==0 && !claimed[0] && !claimed[1]);cases++;
    assert(!spin_depth && !mutex_depth && !rcu_depth && rcu_locks==rcu_unlocks);
    printf("{\"passed\":true,\"cases\":%u,\"handler_fault_cases\":%u,\"start_fault_cases\":%u,"
           "\"rearm_fault_cases\":%u,\"stop_fault_cases\":%u,\"late_start_fault_cases\":%u,\"ordinary_poll_cases\":%u}\n",
           cases,handler_cases,start_cases,rearm_cases,stop_cases,late_cases,ordinary_cases);
    return 0;
}
