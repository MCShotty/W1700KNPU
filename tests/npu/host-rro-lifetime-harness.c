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
#include "rro-session.h"

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

#define RRO_MAP_BASE 0x58000000u
#define RRO_MAP_BYTES 0x8b0000u
#define RRO_SRAM_BASE 0x3e900000u
#define RRO_SRAM_BYTES 0x5000u

static struct npu_rro_session rro_broker;
static unsigned char rro_memory[RRO_MAP_BYTES], rro_expected[RRO_MAP_BYTES];
static unsigned char rro_sram[RRO_SRAM_BYTES], rro_sram_expected[RRO_SRAM_BYTES];
static unsigned char rro_span_expected[NPU_RRO_BLOCK_BYTES];
static struct npu_rro_wire_packet rro_last_request, rro_last_reply;
static unsigned rro_rpc_calls, rro_effects, rro_positive, rro_faults;
static unsigned rro_last_pub_reads, rro_last_pub_writes, rro_late_checks;
static unsigned rro_negative_joint, rro_full_profiles, rro_total_publications;
static unsigned rro_total_effects;
static u32 rro_last_sequence, rro_last_status;
static unsigned rro_corrupt_reply, rro_fail_write, rro_fail_read, rro_after_write;
static void dispose(void);

struct rro_bus_state {
    unsigned active, ordinal, slot, reads, writes;
    unsigned fail_read, fail_write, after_write;
};
static struct rro_bus_state rro_bus;

static u32 rro_alias(u32 dma)
{
    return (dma & 0x3fffffffu) | 0x40000000u;
}

static unsigned rro_slot(unsigned profile,unsigned ordinal)
{
    return ordinal==NPU_RRO_BLOCKS?npu_rro_extent_count(profile)-1:
           ordinal+(profile==NPU_RRO_V3?2:0);
}

static unsigned char *rro_map(u32 address,u32 bytes)
{
    if(bytes && bytes<=RRO_SRAM_BYTES && address>=RRO_SRAM_BASE &&
       address-RRO_SRAM_BASE<=RRO_SRAM_BYTES-bytes)
        return rro_sram+(address-RRO_SRAM_BASE);
    if(bytes && bytes<=RRO_MAP_BYTES && address>=RRO_MAP_BASE &&
       address-RRO_MAP_BASE<=RRO_MAP_BYTES-bytes)
        return rro_memory+(address-RRO_MAP_BASE);
    check(false,"native RRO I/O stays inside mapped retained arrays");
    return NULL;
}

static void rro_access(u32 address,u32 bytes)
{
    u32 base,table,size;

    check(rro_bus.active && (bytes==1 || bytes==4) && !(address&(bytes-1)),
          "native RRO access width and active publication");
    check(rro_broker.owner.publication[rro_bus.ordinal].ticket &&
          (rro_broker.owner.exposure[rro_bus.slot]&NPU_RRO_NPU_POSSIBLE),
          "native effect follows retained possible-publication ticket");
    base=rro_alias(rro_broker.owner.extents[rro_bus.slot].dma_lo);
    table=rro_bus.ordinal==NPU_RRO_BLOCKS?NPU_RRO_NATIVE_SESSION_TABLE:
          NPU_RRO_NATIVE_BLOCK_TABLE+rro_bus.ordinal*4;
    size=rro_bus.ordinal==NPU_RRO_BLOCKS?NPU_RRO_SESSION_BYTES:NPU_RRO_BLOCK_BYTES;
    check((address==table && bytes==4) ||
          (address>=base && bytes<=size && address-base<=size-bytes),
          "native effect stays inside table or exact retained extent");
}

static int rro_read(void *opaque,u32 address,u32 bytes,u32 *value)
{
    unsigned index;

    check(opaque==&rro_bus,"native read context");
    rro_access(address,bytes);
    index=rro_bus.reads++;
    if(index==rro_bus.fail_read)return 0;
    *value=0;
    memcpy(value,rro_map(address,bytes),bytes);
    return 1;
}

static int rro_write(void *opaque,u32 address,u32 bytes,u32 value)
{
    unsigned index;

    check(opaque==&rro_bus,"native write context");
    rro_access(address,bytes);
    index=rro_bus.writes++;
    if(index==rro_bus.fail_write && !rro_bus.after_write)return 0;
    memcpy(rro_map(address,bytes),&value,bytes);
    return index!=rro_bus.fail_write;
}

static int rro_transport(void *packet,unsigned bytes)
{
    struct npu_rro_wire_message request,reply;
    const struct npu_rro_native_context context={rro_read,rro_write,&rro_bus};

    check(bytes==NPU_RRO_WIRE_SIZE &&
          !npu_rro_wire_decode(&request,packet,bytes,0),
          "only well-formed 256-byte API-2 requests enter native broker");
    npu_rro_wire_copy(&rro_last_request,packet);
    memset(&rro_bus,0,sizeof(rro_bus));
    rro_bus.fail_read=rro_fail_read;
    rro_bus.fail_write=rro_fail_write;
    rro_bus.after_write=rro_after_write;
    if(request.operation==NPU_RRO_WIRE_PUBLISH){
        rro_bus.active=1;
        rro_bus.ordinal=request.ordinal;
        rro_bus.slot=rro_slot(request.plan.profile,request.ordinal);
    }
    check(npu_rro_session_dispatch(&rro_broker,&session,&admission,&barrier,
          &bootstrap,&cold,packet,bytes,&context),
          "actual native broker shapes each RRO reply");
    check(npu_rro_wire_echo(&rro_last_request,packet,bytes) &&
          !npu_rro_wire_decode(&reply,packet,bytes,1),
          "broker preserves immutable host request and typed reply");
    rro_last_sequence=request.sequence;
    rro_last_status=reply.status;
    rro_rpc_calls++;
    if(request.operation==NPU_RRO_WIRE_PUBLISH){
        rro_last_pub_reads=rro_bus.reads;
        rro_last_pub_writes=rro_bus.writes;
        if(rro_bus.writes)rro_effects++;
    }
    if(rro_corrupt_reply){
        /* A valid alternate profile still decodes; only echo catches it. */
        ((unsigned char *)packet)[17u*4u]^=1u;
        rro_corrupt_reply=0;
    }
    npu_rro_wire_copy(&rro_last_reply,packet);
    return 0;
}

static void rro_journals_equal(const char *stage)
{
    check(life.rro && !memcmp(&life.rro->journal,&rro_broker.owner,
          sizeof(life.rro->journal)),stage);
    check(!memcmp(&life.rro->plan,&rro_broker.plan,sizeof(life.rro->plan)) &&
          !rro_broker.error && !rro_broker.inflight,
          "provider and native retain identical full identity and healthy state");
    rro_positive++;
}

static void rro_chain(unsigned expected_steps)
{
    struct npu_linux_control_snapshot snapshot;

    check(!npu_linux_control_snapshot(&priv.wlan_control,&snapshot),
          "snapshot reads control state without RPC");
    check(life.rro && life.rro->origin_serial==life.tx_serial &&
          life.rro->wire_steps==expected_steps &&
          life.rro->control_serial==life.tx_serial+expected_steps &&
          life.rro->control_serial==snapshot.client.base.serial &&
          rro_last_sequence==life.rro->control_serial,
          "accepted wire sequence extends original TX lease exactly once");
}

static void rro_verify_target(unsigned ordinal)
{
    unsigned slot=rro_slot(life.rro->plan.profile,ordinal);
    u32 base=rro_alias(life.rro->journal.extents[slot].dma_lo);
    u32 bytes=ordinal==NPU_RRO_BLOCKS?NPU_RRO_SESSION_BYTES:NPU_RRO_BLOCK_BYTES;
    u32 table=ordinal==NPU_RRO_BLOCKS?NPU_RRO_NATIVE_SESSION_TABLE:
              NPU_RRO_NATIVE_BLOCK_TABLE+ordinal*4;

    memset(rro_span_expected,ordinal==NPU_RRO_BLOCKS?0xa5:0,bytes);
    for(u32 i=7;i<bytes;i+=8)rro_span_expected[i]=0xff;
    check(!memcmp(rro_map(base,bytes),rro_span_expected,bytes),
          "full native publication bytes and unchanged non-signatures");
    check(!memcmp(rro_map(table,4),&base,4),"native table retains exact alias");
    check(rro_last_pub_writes==(ordinal==NPU_RRO_BLOCKS?1025u:24577u) &&
          rro_last_pub_reads==(ordinal==NPU_RRO_BLOCKS?1026u:24578u),
          "actual native effect engine executes complete readback geometry");
}

static void rro_verify_whole(void)
{
    memset(rro_expected,0xa5,sizeof(rro_expected));
    memset(rro_sram_expected,0xa5,sizeof(rro_sram_expected));
    for(unsigned ordinal=0;ordinal<NPU_RRO_PUBLICATIONS;ordinal++){
        unsigned slot=rro_slot(life.rro->plan.profile,ordinal);
        u32 base=rro_alias(life.rro->journal.extents[slot].dma_lo);
        u32 bytes=ordinal==NPU_RRO_BLOCKS?NPU_RRO_SESSION_BYTES:NPU_RRO_BLOCK_BYTES;
        u32 table=ordinal==NPU_RRO_BLOCKS?NPU_RRO_NATIVE_SESSION_TABLE:
                  NPU_RRO_NATIVE_BLOCK_TABLE+ordinal*4;
        unsigned char *span;

        check(base>=RRO_MAP_BASE && bytes<=RRO_MAP_BYTES &&
              base-RRO_MAP_BASE<=RRO_MAP_BYTES-bytes,
              "full native extent fits mapped array");
        span=rro_expected+(base-RRO_MAP_BASE);
        memset(span,ordinal==NPU_RRO_BLOCKS?0xa5:0,bytes);
        for(u32 i=7;i<bytes;i+=8)span[i]=0xff;
        check(table>=RRO_SRAM_BASE && table-RRO_SRAM_BASE<=RRO_SRAM_BYTES-4,
              "full native table fits mapped SRAM");
        memcpy(rro_sram_expected+(table-RRO_SRAM_BASE),&base,4);
    }
    check(!memcmp(rro_memory,rro_expected,sizeof(rro_memory)) &&
          !memcmp(rro_sram,rro_sram_expected,sizeof(rro_sram)),
          "all native bytes, untouched extents and SRAM gaps match full oracle");
}

static void fixture(void)
{
    fresh();
    memset(&rro_broker,0,sizeof(rro_broker));
    memset(&rro_last_request,0,sizeof(rro_last_request));
    memset(&rro_last_reply,0,sizeof(rro_last_reply));
    memset(&rro_bus,0,sizeof(rro_bus));
    memset(rro_memory,0xa5,sizeof(rro_memory));
    memset(rro_sram,0xa5,sizeof(rro_sram));
    rro_rpc_calls=rro_effects=rro_positive=rro_faults=0;
    rro_last_pub_reads=rro_last_pub_writes=0;
    rro_last_sequence=rro_last_status=0;
    rro_corrupt_reply=rro_after_write=0;
    rro_fail_read=rro_fail_write=UINT32_MAX;
    npu_test_callbacks(rro_transport,NULL);
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
    priv.npu.ops.wlan_validate_tx_buffers=airoha_npu_wlan_validate_tx_buffers_session;
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
    check(cold.completed==(NPU_COLD_ENDPOINT_BASE|NPU_COLD_ENDPOINT_BYTES) &&
          cold.txbuf_enrolled==NPU_COLD_TXBUF_RECORDS && cold.rx_event==life.rx_event.addr &&
          !cold.rx_event_steps && npu_cold_txbuf_dma_valid(&cold.txbuf,NPU_COLD_TXBUF_RECORDS) &&
          bootstrap.plan.region[NPU_BOOT_REQUEST].bytes==256,
          "actual pre-RRO cold enrollment passes complete 256-byte mailbox gate");
}

static void open_owner(unsigned profile)
{
    check(!mt76_npu_rro_open(&wifi,profile,tx,6),"actual RRO open bridge");
    check(life.rro && metadata_allocations==1 && life.rro->plan.profile==profile &&
          life.rro->journal.phase==NPU_RRO_BUILDING,"journal belongs to independent retained lifetime");
    check(sizeof(*life.rro)<=65536,"bounded heap owner, not a large stack copy");
    check(life.rro->plan.mailbox[0].bytes==256 && rro_rpc_calls==1 &&
          rro_last_status==NPU_RRO_WIRE_OK,
          "typed RRO OPEN crosses real client/codec/native broker");
    rro_journals_equal("typed OPEN matches every native journal byte");
    rro_chain(1);
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
    check(rro_rpc_calls==ordinal+2 && rro_last_status==NPU_RRO_WIRE_OK,
          "each exact enrollment advances typed transport once");
    rro_journals_equal("typed ENROLL matches every native journal byte");
    rro_chain(ordinal+2);
}

static void late_tx_validate(void)
{
    unsigned before_calls=calls, serial=priv.wlan_control.client.base.serial;

    check(!airoha_npu_wlan_validate_tx_buffers(&priv.npu,&endpoint_device,
          &dma_device,tx_bytes,tx,6),
          "late TX validator accepts original serial plus exact RRO wire chain");
    check(calls==before_calls && priv.wlan_control.client.base.serial==serial &&
          life.tx_serial==life.rro->origin_serial,
          "late TX snapshot is pure read, never an RPC or new TX lease");
    rro_late_checks++;
}

static void publish_all(unsigned profile,unsigned count)
{
    for(unsigned ordinal=0;ordinal<NPU_RRO_PUBLICATIONS;ordinal++){
        unsigned prior=rro_rpc_calls;
        check(!mt76_npu_rro_publish(&wifi,ordinal),
              "actual typed bridge publishes every block and session table");
        check(rro_rpc_calls==prior+(ordinal==NPU_RRO_BLOCKS?2u:1u) &&
              rro_last_status==NPU_RRO_WIRE_OK &&
              life.rro->journal.confirmed==ordinal+1,
              "each accepted publication advances one transport ticket");
        rro_journals_equal("full provider/client/broker publication journal equality");
        rro_chain(1u+count+ordinal+1u+(ordinal==NPU_RRO_BLOCKS?1u:0u));
        rro_verify_target(ordinal);
        if(ordinal==0 || ordinal==64 || ordinal==NPU_RRO_BLOCKS)
            late_tx_validate();
    }
    check(rro_effects==NPU_RRO_PUBLICATIONS &&
          life.rro->journal.phase==NPU_RRO_LIVE &&
          life.rro->journal.hardware_exposed &&
          npu_rro_session_cold_ready(&rro_broker),
          "all 129 actual native effects precede live hardware metadata");
    for(unsigned i=0;i<count;i++)
        check(life.rro->journal.exposure[i]&NPU_RRO_HARDWARE_POSSIBLE,
              "hardware exposure retained for every allocated extent");
    rro_verify_whole();
    check(life.rro->origin_serial==life.tx_serial &&
          life.rro->wire_steps==1u+count+NPU_RRO_PUBLICATIONS+1u,
          "original TX serial remains unchanged across full typed RRO wire chain");
    rro_total_publications+=NPU_RRO_PUBLICATIONS;
    rro_total_effects+=rro_effects;
    (void)profile;
}

static void chain_failure_cases(void)
{
    for(unsigned kind=0;kind<6;kind++){
        struct npu_rro_extent shape;
        void *out=(void *)(uintptr_t)0x1234;
        dma_addr_t addr=UINT64_C(0xabcdef0123456789);
        unsigned before_wire,before_dma;

        fixture();open_owner(0);allocate(0,0);
        check(!npu_rro_extent_geometry(0,1,&shape),"serial-chain failure geometry");
        before_wire=calls;before_dma=dma_calls;
        if(kind==0)life.rro->origin_serial++;
        if(kind==1)life.rro->control_serial++;
        if(kind==2)life.rro->wire_steps=0;
        if(kind==3)life.rro->wire_steps++;
        if(kind==4)life.tx_serial++;
        if(kind==5)priv.wlan_control.client.base.serial++;
        check(mt76_npu_rro_alloc(&wifi,shape.role,shape.index,shape.bytes,&out,&addr)!=0 &&
              out==(void *)(uintptr_t)0x1234 && addr==UINT64_C(0xabcdef0123456789) &&
              calls==before_wire && dma_calls==before_dma && life.rro->attempts==1 &&
              life.rro->journal.allocated==1 && rro_broker.owner.allocated==1,
              "broken origin/control/wire chain denies before allocation or RPC");
        check(life.rro->error && !freed_buffers && !freed_contexts,
              "chain failure holds the previously exposed owner");
        rro_negative_joint++;
        dispose();
    }
}

static void publication_failure_case(unsigned kind)
{
    struct npu_rro_extent shape;
    u32 remote=0xfeedfaceu,table=NPU_RRO_NATIVE_BLOCK_TABLE;
    u32 base;
    unsigned before_wire,before_dma;
    int error;

    fixture();open_owner(0);
    for(unsigned ordinal=0;ordinal<3;ordinal++)allocate(0,ordinal);
    check(!npu_rro_extent_geometry(0,2,&shape) && shape.role==NPU_RRO_ELEMENT,
          "first publication uses full V3 element slot");
    base=rro_alias(life.rro->journal.extents[2].dma_lo);
    if(kind==0)rro_corrupt_reply=1;
    if(kind==1){rro_fail_write=0;rro_after_write=1;}
    if(kind==2)rro_fail_write=100;
    if(kind==3){fault_at=calls+1;effect_fault=1;fault_error=-ETIMEDOUT;}
    if(kind==4)rro_fail_read=0;
    before_wire=calls;before_dma=dma_calls;
    error=mt76_npu_rro_publish(&wifi,0);
    check(error && calls==before_wire+1 && dma_calls==before_dma &&
          life.rro->journal.publication[0].ticket==1 &&
          life.rro->journal.exposure[2]==(NPU_RRO_ALLOCATED|NPU_RRO_NPU_POSSIBLE) &&
          !life.rro->journal.confirmed && life.rro->error &&
          priv.wlan_control.client.base.phase==NPU_CLIENT_FAILED,
          "reply/transport/I/O failure retains host possible-publication ticket");
    check(rro_rpc_calls==4u+1u && rro_effects==1 &&
          rro_last_sequence==life.rro->control_serial+1u,
          "failed fifth wire request cannot extend accepted serial chain");
    if(kind==0 || kind==3){
        check(rro_last_status==NPU_RRO_WIRE_OK &&
              rro_broker.owner.confirmed==1 && !rro_broker.owner.error,
              "native effect may complete before corrupted reply or transport loss");
        memset(rro_span_expected,0,sizeof(rro_span_expected));
        for(u32 i=7;i<NPU_RRO_BLOCK_BYTES;i+=8)rro_span_expected[i]=0xff;
        check(!memcmp(rro_map(base,NPU_RRO_BLOCK_BYTES),rro_span_expected,NPU_RRO_BLOCK_BYTES) &&
              !memcmp(rro_map(table,4),&base,4),
              "ambiguous completion retains full native effect, not host confirmation");
    }else{
        check(rro_last_status==NPU_RRO_WIRE_CORE+NPU_RRO_HELD &&
              rro_broker.owner.error && !rro_broker.owner.confirmed &&
              rro_broker.owner.publication[0].ticket==1,
              "I/O failure retains native possible-publication prefix");
        check((kind==1 && rro_last_pub_writes==1 && !rro_last_pub_reads) ||
              (kind==2 && rro_last_pub_writes==101 && rro_last_pub_reads==1) ||
              (kind==4 && rro_last_pub_writes==1 && rro_last_pub_reads==1),
              "I/O injection reaches exact native write/readback boundary");
        memset(rro_expected,0xa5,sizeof(rro_expected));
        memset(rro_sram_expected,0xa5,sizeof(rro_sram_expected));
        memcpy(rro_sram_expected+(table-RRO_SRAM_BASE),&base,4);
        if(kind==2)memset(rro_expected+(base-RRO_MAP_BASE),0,99u*4u);
        check(!memcmp(rro_memory,rro_expected,sizeof(rro_memory)) &&
              !memcmp(rro_sram,rro_sram_expected,sizeof(rro_sram)),
              "failed table/clear store retains exact bounded native prefix");
    }
    check(npu_rro_client_complete(&priv.wlan_control.client,rro_last_sequence,0,
          &rro_last_request,&rro_last_reply,NPU_RRO_WIRE_SIZE,&remote)==
          NPU_CLIENT_IGNORED && remote==0xfeedfaceu &&
          !freed_buffers && !freed_contexts,
          "late completion after client failure is ignored before any free");
    rro_faults++;
    rro_negative_joint++;
    dispose();
}

static void dispose(void)
{
    struct airoha_npu_rro_owner *owner=life.rro;
    if(owner && owner->journal.magic==NPU_RRO_MAGIC){
        bool healthy=!owner->error && !priv.wlan_session_error;
        unsigned prior_wire=rro_rpc_calls;
        struct npu_rro_retirement host_snapshot,native_snapshot;
        check(!mt76_npu_rro_close(&wifi),"retained close accepts failed or pending owner");
        uint32_t ticket=owner->journal.retirement_ticket;
        check(ticket && owner->journal.phase==NPU_RRO_CLOSING && !owner->journal.cpu_joined,
              "close records handoff, not CPU or physical retirement");
        for(unsigned i=0;i<NPU_RRO_DRAIN_DOMAINS;i++)check(!owner->journal.drained[i],"no fabricated domain witnesses");
        if(healthy){
            check(rro_rpc_calls==prior_wire+1 && rro_last_status==NPU_RRO_WIRE_OK,
                  "healthy CLOSE crosses client and native broker once");
            rro_journals_equal("healthy CLOSE preserves exact mirrored journal");
            check(!npu_rro_retirement_snapshot(&owner->journal,&owner->plan,&host_snapshot) &&
                  !npu_rro_retirement_snapshot(&rro_broker.owner,&rro_broker.plan,&native_snapshot) &&
                  !memcmp(&host_snapshot,&native_snapshot,sizeof(host_snapshot)) &&
                  host_snapshot.allocated==owner->journal.allocated &&
                  host_snapshot.phase==NPU_RRO_CLOSING && !host_snapshot.cpu_joined &&
                  !npu_rro_session_cold_ready(&rro_broker),
                  "closing snapshots match without CPU join or free authority");
        }else
            check(rro_rpc_calls==prior_wire,"faulted close cannot invent a new RPC");
        check(!mt76_npu_rro_close(&wifi) && owner->journal.retirement_ticket==ticket,
              "repeated close keeps the same retirement ticket");
        check(rro_rpc_calls==prior_wire+(healthy?1u:0u),
              "repeated close never sends another native request");
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
        fixture();open_owner(profile);late_tx_validate();
        for(unsigned ordinal=0;ordinal<count;ordinal++)allocate(profile,ordinal);
        check(object_count==7+count && life.rro->journal.confirmed==0,"complete profiles allocated without fake publication");
        unsigned before=dma_calls,wire=calls;
        check(mt76_npu_rro_open(&wifi,profile,tx,6)==-EBUSY && dma_calls==before &&
              calls==wire && metadata_allocations==1,
              "one retained RRO owner per provider boot");
        publish_all(profile,count);
        rro_full_profiles++;
        u32 accepted=life.rro->control_serial,steps=life.rro->wire_steps;
        check(!npu_linux_control_exchange(&priv.wlan_control,NPU_CONTROL_STATUS) &&
              priv.wlan_control.client.base.serial==accepted+1 &&
              life.rro->control_serial==accepted && life.rro->wire_steps==steps,
              "ordinary control advances do not rewrite the pre-constructor RRO lease");
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
    }
    chain_failure_cases();
    for(unsigned kind=0;kind<5;kind++)publication_failure_case(kind);
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
    check(rro_full_profiles==3 && rro_total_publications==3*NPU_RRO_PUBLICATIONS &&
          rro_total_effects==3*NPU_RRO_PUBLICATIONS &&
          rro_negative_joint==11 && rro_late_checks==12 && rro_cases==456,
          "literal full profiles and bounded provider negative matrix");
    printf("{\"passed\":true,\"cases\":%u,\"profiles\":%u,"
           "\"publications\":%u,\"negative_joint\":%u,"
           "\"late_tx_checks\":%u,\"native_effects\":%u,"
           "\"hardware\":false}\n",rro_cases,rro_full_profiles,
           rro_total_publications,rro_negative_joint,rro_late_checks,
           rro_total_effects);
    return 0;
}
