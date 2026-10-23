/* Actual provider/core/bridge above; DMA, refs and framework are modeled. */
struct mt76_dev {
    struct { struct airoha_npu *npu; } mmio;
    struct device *dev, *dma_dev;
    struct mutex mutex;
};
static struct mt76_dev wifi;
#define lockdep_is_held(p) (pthread_mutex_trylock(&(p)->native)==EBUSY)
#define rcu_dereference_protected(p,c) (check((c),"process bridge holds caller mutex"),(p))
#include "consumer.inc"

_Static_assert((int)MT76_NPU_RRO_V3 == (int)NPU_RRO_V3 && (int)MT76_NPU_RRO_V3_1 == (int)NPU_RRO_V3_1 &&
               (int)MT76_NPU_RRO_V3_1_WED == (int)NPU_RRO_V3_1_WED, "profile ABI");
_Static_assert((int)MT76_NPU_RRO_BA == (int)NPU_RRO_BA && (int)MT76_NPU_RRO_ELEMENT == (int)NPU_RRO_ELEMENT &&
               (int)MT76_NPU_RRO_MSDU == (int)NPU_RRO_MSDU && (int)MT76_NPU_RRO_EMI_CPU == (int)NPU_RRO_EMI_CPU &&
               (int)MT76_NPU_RRO_EMI_DMA == (int)NPU_RRO_EMI_DMA && (int)MT76_NPU_RRO_SESSION == (int)NPU_RRO_SESSION,
               "extent role ABI");

static unsigned rro_cases;
static bool corrupt_exposed;
static const u32 tx_bytes[6]={0x20000,0x20000,0x40000,0x40000,0x40000,0x40000};
static dma_addr_t tx[6];

static void fixture(void)
{
    fresh();
    memset(&wifi,0,sizeof(wifi));
    wifi.mmio.npu=&priv.npu; wifi.dev=&endpoint_device; wifi.dma_dev=&dma_device;
    mutex_init(&wifi.mutex); consumer_mutex=&wifi.mutex.native;
    dma_calls=object_count=managed_calls=freed_buffers=freed_contexts=put_refs=0;
    metadata_allocations=0;fail_metadata=false;bad_rro_cpu=NULL;fail_allocation=999;corrupt_exposed=false;
    override_cpu=late_mutation=mutate_after=mutate_on_call=0;
    memset(objects,0,sizeof(objects));
    addresses[0]=0x97000000;
    for(unsigned i=1;i<7;i++)addresses[i]=0x96000000+(i-1)*0x100000;
    for(unsigned i=7;i<147;i++)addresses[i]=0x98000000+(i-7)*0x10000;
    for(unsigned i=0;i<8;i++){
        life.buffers[i].buf=(void *)(uintptr_t)(i+1);
        life.buffers[i].addr=0x83000000+i*256;
    }
    priv.npu.ops.wlan_alloc_rx_event=airoha_npu_wlan_alloc_rx_event_session;
    priv.npu.ops.wlan_alloc_tx_buffers=airoha_npu_wlan_alloc_tx_buffers_session;
    priv.npu.ops.wlan_rro_open=airoha_npu_wlan_rro_open_session;
    priv.npu.ops.wlan_rro_alloc=airoha_npu_wlan_rro_alloc_session;
    priv.npu.ops.wlan_rro_publish=airoha_npu_wlan_rro_publish_session;
    priv.npu.ops.wlan_rro_close=airoha_npu_wlan_rro_close_session;
    check(!npu_test_run() && !npu_test_endpoint(0x20000000,0x100000,2),"actual provider setup and endpoint binding");
    void *rx;
    dma_addr_t rx_addr;
    check(!airoha_npu_wlan_alloc_rx_event(&priv.npu,&endpoint_device,&dma_device,512,16,&rx,&rx_addr),
          "actual retained RX prerequisite");
    check(!airoha_npu_wlan_alloc_tx_buffers(&priv.npu,&endpoint_device,&dma_device,tx_bytes,tx,6),
          "actual retained TX prerequisite");
    check(dma_calls==7 && object_count==7,"one RX and six TX backing allocations");
}

static void open_owner(unsigned profile)
{
    check(!mt76_npu_rro_open(&wifi,profile,tx,6),"actual RRO open bridge");
    check(life.rro && metadata_allocations==1 && life.rro->plan.profile==profile &&
          life.rro->journal.phase==NPU_RRO_BUILDING,"journal belongs to independent retained lifetime");
    check(sizeof(*life.rro)<=65536,"bounded heap owner, not a large stack copy");
}

static void allocate(unsigned profile,unsigned ordinal)
{
    struct npu_rro_extent shape;
    check(!npu_rro_extent_geometry(profile,ordinal,&shape),"full allocation geometry");
    void *buf=NULL;
    dma_addr_t addr=0;
    check(!mt76_npu_rro_alloc(&wifi,shape.role,shape.index,shape.bytes,&buf,&addr),"actual RRO allocation bridge");
    check(buf==life.rro->allocations[ordinal].buf && addr==life.rro->allocations[ordinal].addr &&
          life.rro->journal.allocated==ordinal+1 && life.rro->attempts==ordinal+1,
          "journal enrollment precedes caller CPU and full DMA outputs");
    check(life.rro->journal.extents[ordinal].cpu_lo==(u32)(uintptr_t)buf &&
          life.rro->journal.extents[ordinal].cpu_hi==(u32)((uint64_t)(uintptr_t)buf>>32),
          "full CPU identity preserved");
}

static void dispose(void)
{
    struct airoha_npu_rro_owner *owner=life.rro;
    if(owner && owner->journal.magic==NPU_RRO_MAGIC){
        check(!mt76_npu_rro_close(&wifi),"retained close accepts failed or pending owner");
        uint32_t ticket=owner->journal.retirement_ticket;
        check(ticket && owner->journal.phase==NPU_RRO_CLOSING && !owner->journal.cpu_joined,
              "close records handoff, not CPU or physical retirement");
        for(unsigned i=0;i<NPU_RRO_DRAIN_DOMAINS;i++)check(!owner->journal.drained[i],"no fabricated domain witnesses");
        check(!mt76_npu_rro_close(&wifi) && owner->journal.retirement_ticket==ticket,
              "repeated close keeps the same retirement ticket");
    }
    npu_test_close();
    if(corrupt_exposed)life.exposed=false;
    airoha_npu_dma_cleanup(&life);
    check(!freed_buffers && !freed_contexts && !put_refs && airoha_npu_dma_retained(life.dev),
          "actual cleanup retains RRO, RX, TX, mailboxes and reference ownership");
    life.retained.prev->next=life.retained.next;
    life.retained.next->prev=life.retained.prev;
    /* The test owns these model heap objects; production grants no such free. */
    for(unsigned i=0;i<object_count;i++)free(objects[i]);
    free(owner);
    check(!pthread_mutex_destroy(&wifi.mutex.native),"consumer fixture mutex");
    check(!pthread_mutex_destroy(&priv.wlan_session_lock.native),"provider fixture mutex");
    memset(&priv,0,sizeof(priv)); consumer_mutex=NULL;rro_cases++;
}

int main(void)
{
    for(unsigned profile=0;profile<3;profile++){
        unsigned count=npu_rro_extent_count(profile);
        fixture();open_owner(profile);
        for(unsigned ordinal=0;ordinal<count;ordinal++)allocate(profile,ordinal);
        check(object_count==7+count && life.rro->journal.confirmed==0,"complete profiles allocated without fake publication");
        unsigned before=dma_calls;
        check(mt76_npu_rro_open(&wifi,profile,tx,6)==-EBUSY && dma_calls==before && metadata_allocations==1,
              "one retained RRO owner per provider boot");
        dispose();
        for(unsigned failure=0;failure<count;failure++){
            fixture();open_owner(profile);
            for(unsigned ordinal=0;ordinal<failure;ordinal++)allocate(profile,ordinal);
            struct npu_rro_extent shape;
            check(!npu_rro_extent_geometry(profile,failure,&shape),"failed slot geometry");
            fail_allocation=7+failure;
            void *out=(void *)(uintptr_t)0x1234;
            dma_addr_t addr=UINT64_C(0xabcdef0123456789);
            check(mt76_npu_rro_alloc(&wifi,shape.role,shape.index,shape.bytes,&out,&addr)==-ENOMEM &&
                  out==(void *)(uintptr_t)0x1234 && addr==UINT64_C(0xabcdef0123456789),
                  "allocation failure preserves every caller output");
            check(object_count==7+failure && life.rro->attempts==failure+1 &&
                  life.rro->journal.allocated==failure && !freed_buffers,
                  "failed allocation keeps the complete prefix and attempted slot");
            unsigned wire=calls, allocations=dma_calls;
            check(mt76_npu_rro_alloc(&wifi,shape.role,shape.index,shape.bytes,&out,&addr)==-ENOMEM &&
                  calls==wire && dma_calls==allocations,"failed RRO owner never retries another allocation");
            dispose();
        }
        fixture();open_owner(profile);
        unsigned prefix=profile==NPU_RRO_V3?3:1;
        for(unsigned ordinal=0;ordinal<prefix;ordinal++)allocate(profile,ordinal);
        unsigned wire=calls;
        check(mt76_npu_rro_publish(&wifi,0)==-EINVAL && calls==wire,
              "actual checked RRO publication gate remains closed before transport");
        unsigned slot=profile==NPU_RRO_V3?2:0;
        check(life.rro->journal.exposure[slot]==3 && life.rro->journal.publication[0].ticket==1 &&
              !life.rro->journal.confirmed && life.rro->error==-EINVAL,
              "rejected publication retains its ticket and possible-exposure record");
        check(mt76_npu_rro_publish(&wifi,0)==-EINVAL && calls==wire,"publication failure remains sticky");
        dispose();
    }
    for(unsigned kind=0;kind<8;kind++){
        fixture();open_owner(0);
        struct npu_rro_extent shape;
        check(!npu_rro_extent_geometry(0,0,&shape),"invalid allocation baseline");
        if(kind==0)addresses[7]=UINT64_C(0x198000000);
        if(kind==1)addresses[7]=addresses[0];
        if(kind==2)addresses[7]=addresses[1];
        if(kind==3)addresses[7]=life.buffers[0].addr;
        if(kind==4)addresses[7]=priv.native_plan[0][0];
        if(kind==5)addresses[7]=life.endpoint_base;
        if(kind==6)bad_rro_cpu=objects[0];
        if(kind==7)addresses[7]=0;
        void *out=NULL;dma_addr_t addr=0;
        check(mt76_npu_rro_alloc(&wifi,shape.role,shape.index,shape.bytes,&out,&addr)==-EINVAL &&
              !out && !addr && life.rro->attempts==1 && !life.rro->journal.allocated,
              "invalid CPU/DMA backing is retained without narrowing or caller exposure");
        check(life.rro->allocations[0].buf && !freed_buffers,"invalid nonnull allocation remains owned");
        dispose();
    }
    fixture();fail_metadata=true;
    check(mt76_npu_rro_open(&wifi,0,tx,6)==-ENOMEM && !life.rro && dma_calls==7,
          "journal allocation failure keeps existing RX/TX references and resources");
    dispose();
    fixture();priv.checked_pair=false;
    check(mt76_npu_rro_open(&wifi,0,tx,6)==-EOPNOTSUPP && !life.rro && !metadata_allocations,
          "unmarked provider has no new RRO ownership effects");
    dispose();
    fixture();open_owner(0);allocate(0,0);corrupt_exposed=true;
    dispose();
    for(unsigned kind=0;kind<16;kind++){
        fixture();open_owner(0);allocate(0,0);
        struct npu_rro_extent shape;
        check(!npu_rro_extent_geometry(0,1,&shape),"identity mutation baseline");
        if(kind==0)life.boot_identity^=1;
        if(kind==1)life.nonce_lo^=1;
        if(kind==2)life.tx_serial++;
        if(kind==3)life.tx_buffers[0].buf=NULL;
        if(kind==4)life.tx_buffers[0].addr^=0x1000;
        if(kind==5)life.tx_buffers[0].bytes^=0x1000;
        if(kind==6)life.buffers[0].buf=NULL;
        if(kind==7)life.buffers[0].addr^=0x1000;
        if(kind==8)life.rx_event.buf=NULL;
        if(kind==9)life.rx_event.addr^=0x1000;
        if(kind==10)life.rx_event.bytes^=0x1000;
        if(kind==11)life.endpoint_base^=0x10000;
        if(kind==12)priv.native_plan[0][0]^=0x1000;
        if(kind==13)life.endpoint=&other_device;
        if(kind==14)wifi.mmio.npu=NULL;
        if(kind==15)life.rro->inflight=true;
        void *out=(void *)(uintptr_t)0x1234;
        dma_addr_t addr=UINT64_C(0xabcdef0123456789);
        unsigned allocations=dma_calls,wire=calls;
        check(mt76_npu_rro_alloc(&wifi,shape.role,shape.index,shape.bytes,&out,&addr)!=0 &&
              out==(void *)(uintptr_t)0x1234 && addr==UINT64_C(0xabcdef0123456789) &&
              allocations==dma_calls && wire==calls && life.rro->attempts==1,
              "changed ownership context or in-flight publication cannot allocate or expose outputs");
        life.endpoint=&endpoint_device;wifi.mmio.npu=&priv.npu;life.rro->inflight=false;
        dispose();
    }
    printf("{\"passed\":true,\"cases\":%u,\"profiles\":3,\"checked_publication_rejections\":3,\"RRO_admitted\":false}\n",rro_cases);
    return 0;
}
