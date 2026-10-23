/* Actual provider/client/broker/native C; backing, transport and MCU are models. */
#define main publication_matrix_main
#include "publication-harness.inc"
#undef main

static unsigned reset_id, reset_reads, reset_writes, reset_transactions, reset_negatives;
static u32 reset_base, reset_table;
static int reset_transport_error;

static void reset_access(void *opaque,u32 address,u32 bytes,bool write)
{
    struct npu_rro_reset *r=&rro_broker.owner.resets[reset_id];
    check(opaque==&reset_id && r->phase==NPU_RRO_RESET_NPU_POSSIBLE && r->ticket,
          "native reset I/O follows the exact possible-reset ticket");
    check((!write && bytes==4 && address==reset_table) ||
          (bytes==1 && address>=reset_base && address-reset_base<NPU_RRO_SESSION_BYTES &&
           (address-reset_base)%8==7),"native reset touches only exact table and signature bytes");
}

static int reset_read(void *opaque,u32 address,u32 bytes,u32 *value)
{
    reset_access(opaque,address,bytes,false);reset_reads++;
    *value=0;memcpy(value,rro_map(address,bytes),bytes);return 1;
}

static int reset_write(void *opaque,u32 address,u32 bytes,u32 value)
{
    reset_access(opaque,address,bytes,true);reset_writes++;
    check(value==0xff,"reset signature value");
    memcpy(rro_map(address,bytes),&value,bytes);return 1;
}

static int reset_transport(void *packet,unsigned bytes)
{
    struct npu_rro_wire_message request,reply;
    const struct npu_rro_native_context context={reset_read,reset_write,&reset_id};
    check(!npu_rro_wire_decode(&request,packet,bytes,0),"typed reset request decodes");
    if(request.operation<NPU_RRO_WIRE_RESET_NPU || request.operation>NPU_RRO_WIRE_MCU_COMPLETE)
        return rro_transport(packet,bytes);
    check(request.session==reset_id,"reset wire session identity");
    npu_rro_wire_copy(&rro_last_request,packet);
    check(npu_rro_session_dispatch(&rro_broker,&session,&admission,&barrier,
          &bootstrap,&cold,packet,bytes,&context),"actual broker handles typed reset");
    check(npu_rro_wire_echo(&rro_last_request,packet,bytes) &&
          !npu_rro_wire_decode(&reply,packet,bytes,1),"typed reset reply exact echo");
    rro_last_sequence=request.sequence;rro_last_status=reply.status;rro_rpc_calls++;
    npu_rro_wire_copy(&rro_last_reply,packet);
    return reset_transport_error;
}

static void reset_live(unsigned profile)
{
    fixture();open_owner(profile);
    priv.npu.ops.wlan_rro_reset_npu=airoha_npu_wlan_rro_reset_npu_session;
    priv.npu.ops.wlan_rro_reset_mcu_begin=airoha_npu_wlan_rro_reset_mcu_begin_session;
    priv.npu.ops.wlan_rro_reset_mcu_complete=airoha_npu_wlan_rro_reset_mcu_complete_session;
    unsigned count=npu_rro_extent_count(profile);
    for(unsigned i=0;i<count;i++)allocate(profile,i);
    publish_all(profile,count);
    reset_transport_error=0;
    npu_test_callbacks(reset_transport,NULL);
}

static void reset_seed(unsigned id)
{
    unsigned ordinal=id==NPU_RRO_SESSIONS-1?NPU_RRO_BLOCKS:id/8;
    unsigned slot=rro_slot(life.rro->plan.profile,ordinal);
    unsigned offset=id==NPU_RRO_SESSIONS-1?0:(id%8)*NPU_RRO_SESSION_BYTES;
    reset_id=id;reset_reads=reset_writes=0;
    reset_table=ordinal==NPU_RRO_BLOCKS?NPU_RRO_NATIVE_SESSION_TABLE:NPU_RRO_NATIVE_BLOCK_TABLE+ordinal*4;
    reset_base=rro_alias(life.rro->journal.extents[slot].dma_lo)+offset;
    memset(rro_map(reset_base,NPU_RRO_SESSION_BYTES),0x35,NPU_RRO_SESSION_BYTES);
    memset(rro_expected+(reset_base-RRO_MAP_BASE),0x35,NPU_RRO_SESSION_BYTES);
}

static u32 reset_npu(unsigned generation)
{
    u32 ticket=0;
    check(!mt76_npu_rro_reset_npu(&wifi,reset_id,generation,&ticket),
          "typed NPU reset succeeds with the caller generation");
    check(ticket>NPU_RRO_PUBLICATIONS &&
          life.rro->journal.resets[reset_id].ticket==ticket &&
          life.rro->journal.resets[reset_id].phase==NPU_RRO_RESET_NPU_CONFIRMED,
          "host journal confirms exact NPU reset ticket");
    check(reset_writes==1024 && reset_reads==1026,"full reset readback geometry");
    for(unsigned i=7;i<NPU_RRO_SESSION_BYTES;i+=8)rro_expected[reset_base-RRO_MAP_BASE+i]=0xff;
    check(!memcmp(rro_memory,rro_expected,sizeof(rro_memory)) &&
          !memcmp(rro_sram,rro_sram_expected,sizeof(rro_sram)),
          "reset preserves every non-signature byte and other retained extent");
    rro_journals_equal("NPU reset matches entire provider and native journals");
    return ticket;
}

static void full_reset_profiles(void)
{
    for(unsigned profile=0;profile<3;profile++){
        reset_live(profile);
        for(unsigned generation=1;generation<=2;generation++){
            for(unsigned id=0;id<NPU_RRO_SESSIONS;id++){
                reset_seed(id);u32 ticket=reset_npu(generation);
                check(!mt76_npu_rro_reset_mcu_begin(&wifi,id,generation,ticket),
                      "typed MCU begin succeeds only after NPU completion");
                rro_journals_equal("MCU begin matches complete provider and native journals");
                unsigned accesses=reset_reads+reset_writes;
                check(!mt76_npu_rro_reset_mcu_complete(&wifi,id,generation,ticket,0),
                      "typed MCU completion carries exact identity and modeled result");
                rro_journals_equal("MCU completion matches complete provider and native journals");
                check(life.rro->journal.resets[id].generation==generation+1 &&
                      life.rro->journal.resets[id].request_generation==generation &&
                      life.rro->journal.resets[id].ticket==ticket &&
                      reset_reads+reset_writes==accesses,"MCU RPCs cannot change reset payload bytes");
                rro_chain(1+npu_rro_extent_count(profile)+NPU_RRO_PUBLICATIONS+1+
                          ((generation-1)*NPU_RRO_SESSIONS+id+1)*3);
                reset_transactions++;
            }
        }
        dispose();
    }
}

static void negative_case(unsigned kind)
{
    reset_live(0);reset_seed(8);
    unsigned before=rro_rpc_calls;u32 ticket=0,duplicate=0;
    int error;
    if(kind<4){
        ticket=0xabcdef;
        error=kind==0?mt76_npu_rro_reset_npu(&wifi,1025,1,&ticket):
              kind==1?mt76_npu_rro_reset_npu(&wifi,8,0,&ticket):
              kind==2?mt76_npu_rro_reset_npu(&wifi,8,2,&ticket):
                      mt76_npu_rro_reset_mcu_begin(&wifi,8,1,130);
        check(error && ticket==0xabcdef && rro_rpc_calls==before && !reset_writes,
              "invalid reset identity or order cannot issue an RPC");
    }else if(kind==7){
        reset_transport_error=-ETIMEDOUT;
        error=mt76_npu_rro_reset_npu(&wifi,8,1,&ticket);
        check(error==-ETIMEDOUT && ticket && reset_writes==1024 &&
              life.rro->journal.resets[8].npu_error==(u32)-ETIMEDOUT &&
              life.rro->journal.resets[8].phase==NPU_RRO_RESET_NPU_POSSIBLE &&
              rro_broker.owner.resets[8].phase==NPU_RRO_RESET_NPU_CONFIRMED,
              "ambiguous NPU timeout retains ticket and raw transport error after effects");
    }else{
        ticket=reset_npu(1);before=rro_rpc_calls;
        if(kind==4){
            check(mt76_npu_rro_reset_npu(&wifi,8,1,&duplicate)==-EALREADY && duplicate==ticket &&
                  rro_rpc_calls==before,"duplicate reset returns same ticket without retransmission");
        }else if(kind==5){
            check(mt76_npu_rro_reset_mcu_begin(&wifi,8,1,ticket+1)==-ESTALE && rro_rpc_calls==before,
                  "wrong MCU ticket cannot advance the wire");
        }else if(kind==6){
            check(mt76_npu_rro_reset_mcu_complete(&wifi,8,2,ticket,0)==-ESTALE && rro_rpc_calls==before,
                  "late foreign generation cannot complete a reset");
        }else if(kind==8 || kind==9){
            int raw=kind==8?-ETIMEDOUT:7;
            check(!mt76_npu_rro_reset_mcu_begin(&wifi,8,1,ticket),"error MCU begin");
            error=mt76_npu_rro_reset_mcu_complete(&wifi,8,1,ticket,raw);
            check(error==(raw<0?raw:-EIO) && life.rro->journal.resets[8].mcu_error==(u32)raw &&
                  rro_broker.owner.resets[8].mcu_error==(u32)raw && life.rro->error==error,
                  "physical MCU raw error remains retained across typed failure");
        }else if(kind==10){
            check(!mt76_npu_rro_reset_mcu_begin(&wifi,8,1,ticket),"late MCU begin");
            check(!mt76_npu_rro_close(&wifi),"close before late exact MCU result");
            before=rro_rpc_calls;
            check(mt76_npu_rro_reset_mcu_complete(&wifi,8,1,ticket,0)==-ESHUTDOWN &&
                  rro_rpc_calls==before && life.rro->journal.resets[8].phase==NPU_RRO_RESET_COMPLETE &&
                  rro_broker.owner.resets[8].phase==NPU_RRO_RESET_MCU_POSSIBLE &&
                  !life.rro->journal.cpu_joined,"late MCU result is retained without new RPC or join");
        }else{
            check(!mt76_npu_rro_reset_mcu_begin(&wifi,8,1,ticket),"endpoint MCU begin");
            before=rro_rpc_calls;
            error=airoha_npu_wlan_rro_reset_mcu_complete(&priv.npu,&dma_device,8,1,ticket,0);
            check(error==-ENODEV && rro_rpc_calls==before &&
                  life.rro->journal.resets[8].phase==NPU_RRO_RESET_MCU_POSSIBLE,
                  "foreign endpoint cannot record an MCU completion");
            check(!mt76_npu_rro_reset_mcu_complete(&wifi,8,1,ticket,0),"exact endpoint still completes");
        }
    }
    dispose();reset_negatives++;
}

int main(int argc,char **argv)
{
    if(argc==2){
        check(!strcmp(argv[1],"timeout") || !strcmp(argv[1],"mcu") || !strcmp(argv[1],"begin"),"reset targeted case");
        if(!strcmp(argv[1],"timeout"))negative_case(7);
        else if(!strcmp(argv[1],"mcu"))negative_case(8);
        else{reset_live(0);reset_seed(8);u32 ticket=reset_npu(1);
            check(!mt76_npu_rro_reset_mcu_begin(&wifi,8,1,ticket),"typed MCU begin succeeds only after NPU completion");
            rro_journals_equal("MCU begin matches complete provider and native journals");dispose();}
        return 0;
    }
    check(argc==1,"reset arguments");full_reset_profiles();
    for(unsigned kind=0;kind<12;kind++)negative_case(kind);
    printf("{\"passed\":true,\"reset_transactions\":%u,\"profiles\":3,\"negative_cases\":%u,\"hardware\":false}\n",
           reset_transactions,reset_negatives);
    return 0;
}
