#!/usr/bin/env python3
"""Actual RRO sender and checked-provider denial;not RRO/native admission."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import native_prefix_snapshot
import test_provider_session as parent

ROOT = parent.ROOT
PROVIDER = ROOT / '.local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c'
HEADER = ROOT / '.local/merge-nonoc-20260923/kernel-merged/include/linux/soc/airoha/airoha_offload.h'
CALLER = ROOT / '.local/merge-nonoc-20260923/mt76-merged/npu.c'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    directory = ROOT / '.local/npu-inode-rro-caller' / args.name
    assert not directory.exists()
    paths = [PROVIDER, HEADER, CALLER, Path(__file__), parent.HARNESS,
             Path(parent.__file__), Path(parent.loader.__file__), Path(parent.loader.extract.__file__),
             *[path for path in parent.SOURCE.rglob('*') if path.is_file()]]
    inputs = native_prefix_snapshot.source_inputs({str(path.relative_to(ROOT)): parent.loader.sha(path) for path in paths})
    command = parent.prepare(directory, PROVIDER.read_text(), HEADER.read_text())
    mutex_header = directory / 'shims/linux/mutex.h'
    mutex = mutex_header.read_text()
    mutex = parent.loader.once(mutex, 'struct mutex { pthread_mutex_t native; };',
        'extern int npu_rro_atomic_fixture;\nextern unsigned npu_rro_atomic_mutexes;\nstruct mutex { pthread_mutex_t native; };')
    mutex = parent.loader.once(mutex, 'static inline void mutex_lock(struct mutex *m) {',
        'static inline void mutex_lock(struct mutex *m) { if (npu_rro_atomic_fixture) npu_rro_atomic_mutexes++;')
    mutex_header.write_text(mutex)
    caller = parent.loader.extract.function(CALLER.read_text(), 'mt76_npu_send_txrx_addr')
    prefix = r'''
int npu_rro_atomic_fixture;
unsigned npu_rro_atomic_mutexes;
typedef uint32_t __le32;
#define GFP_ATOMIC 1
#define cpu_to_le32(v) ((uint32_t)(v))
struct mt76_dev { struct { struct airoha_npu *npu; } mmio; };
static unsigned rro_rcu_depth,rro_locks,rro_unlocks,rro_reads,rro_sends;
static uint32_t payload[4],expected_payload[4];
static int expected_index;
static void rcu_read_lock(void) { check(!rro_rcu_depth,"RRO RCU nesting"); rro_rcu_depth=1; rro_locks++; }
static void rcu_read_unlock(void) { check(rro_rcu_depth==1,"RRO RCU unlock"); rro_rcu_depth=0; rro_unlocks++; }
static struct airoha_npu *rro_lookup(struct airoha_npu *p) {
    check(rro_rcu_depth==1,"RRO provider lookup held"); rro_reads++; return p;
}
#define rcu_dereference(p) rro_lookup(p)
/* A modeled public forwarding boundary;the real checked provider body executes below. */
static int airoha_npu_wlan_send_msg(struct airoha_npu *npu,int index,
    enum airoha_npu_wlan_set_cmd api,void *data,int bytes,gfp_t gfp) {
    check(rro_rcu_depth==1 && npu_rro_atomic_fixture,"RRO provider use held");
    check(npu==&priv.npu && index==expected_index && api==24,"RRO command identity");
    check(bytes==16 && data && gfp==GFP_ATOMIC,"RRO actual16-byte atomic payload");
    memcpy(payload,data,sizeof(payload));
    check(!memcmp(payload,expected_payload,sizeof(payload)),"RRO exact little-endian fields");
    rro_sends++;
    return airoha_npu_wlan_msg_send_session(npu,index,api,data,bytes,gfp);
}
'''
    suffix = r'''
int main(void) {
    const uint32_t arguments[]={0,7,8,127,128,1023,1024,UINT32_MAX};
    const int selectors[]={-1,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
    const uint32_t endian=1;
    check(*(const unsigned char *)&endian==1,"fixture host little endian");
    unsigned cases=0,rro=0,scalar_selectors=0,nulls=0;
    for(unsigned initialized=0;initialized<2;initialized++) {
        for(unsigned i=0;i<ARRAY_SIZE(selectors);i++)for(unsigned p=0;p<ARRAY_SIZE(arguments);p++) {
            npu_test_reset(UINT64_C(0x1122334455667788),0x83000000);
            if(initialized) check(!npu_test_run(),"actual modeled C setup before RRO denial");
            struct mt76_dev dev={.mmio.npu=&priv.npu};
            struct airoha_npu_priv before=priv;
            struct airoha_npu_dma_lifetime life_before=life;
            unsigned transport_before=calls;
            rro_rcu_depth=rro_locks=rro_unlocks=rro_reads=rro_sends=npu_rro_atomic_mutexes=0;
            expected_index=selectors[i];
            expected_payload[0]=arguments[p]; expected_payload[1]=0x88000000u+p*0x10000u;
            expected_payload[2]=0x51a20000u+p*4u; expected_payload[3]=0x62b30000u+p*8u;
            npu_rro_atomic_fixture=1;
            int error=mt76_npu_send_txrx_addr(&dev,expected_index,expected_payload[0],expected_payload[1],
                                            expected_payload[2],expected_payload[3]);
            npu_rro_atomic_fixture=0;
            check(error==-EINVAL,"checked provider denies unbound RRO or wrong-length constructor");
            check(!rro_rcu_depth && rro_locks==1 && rro_unlocks==1 && rro_reads==1 && rro_sends==1,
                  "RRO lookup/use/null scope balanced");
            check(!npu_rro_atomic_mutexes && calls==transport_before,"RRO denial precedes mutex or transport");
            check(!memcmp(&priv,&before,sizeof(priv)) && !memcmp(&life,&life_before,sizeof(life)),
                  "RRO denial leaves provider/client/retained metadata unchanged");
            cases++; rro+=(expected_index==0||expected_index==1||expected_index==3);
            scalar_selectors+=(expected_index==2||expected_index==7);
        }
        const int missing[]={0,1,3};
        for(unsigned i=0;i<ARRAY_SIZE(missing);i++) {
            struct mt76_dev dev={0}; unsigned transport_before=calls;
            rro_rcu_depth=rro_locks=rro_unlocks=rro_reads=rro_sends=npu_rro_atomic_mutexes=0;
            npu_rro_atomic_fixture=1;
            int error=mt76_npu_send_txrx_addr(&dev,missing[i],0,0,0,0);
            npu_rro_atomic_fixture=0;
            check(error==-ENODEV && !rro_rcu_depth && rro_locks==1 && rro_unlocks==1 && rro_reads==1 &&
                  !rro_sends && !npu_rro_atomic_mutexes && calls==transport_before,"null RRO provider");
            nulls++;
        }
    }
    check(cases==288 && rro==48 && scalar_selectors==32 && nulls==6,"complete actual caller matrix");
    printf("{\"passed\":true,\"checked_denials\":%u,\"RRO_denials\":%u,\"constructor_shape_denials\":%u,"
           "\"null_cases\":%u,\"payload_bytes\":16,\"atomic_mutex_calls\":0,\"native_admission\":false}\n",
           cases,rro,scalar_selectors,nulls);
    return 0;
}
'''
    source, binary = directory / 'fixture.c', directory / 'test'
    source.write_text('#define main original_provider_main\n' + parent.HARNESS.read_text() +
        '\n#undef main\n' + prefix + caller + suffix)
    command = [source if item == parent.HARNESS else item for item in command]
    flags = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-Wno-unused-function',
             '-Wno-unused-variable', '-Wno-unused-but-set-variable']
    parent.loader.run(command + flags + ['-o', binary], directory / 'build.log')
    result = parent.loader.run([binary], directory / 'run.log', env=dict(os.environ,
        ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1'))
    record = json.loads(result.stdout)
    assert record['checked_denials'] == 288 and record['null_cases'] == 6 and record['native_admission'] is False
    inputs = native_prefix_snapshot.source_inputs(inputs)
    assert all(parent.loader.sha(ROOT / name) == expected for name, expected in inputs.items())
    record.update(inputs=inputs, source_sha256=parent.loader.sha(source), binary_sha256=parent.loader.sha(binary),
        actual_sender_and_checked_provider=True, public_forwarding_boundary_modeled=True,
        mutex_RCU_backing_and_transport_modeled=True, provider_sources_changed=False,
        original_callback_executed=False, complete_RRO_init_or_reset_caller=False,
        full_setup=False, hardware=False,
        limits=['Actual16-byte sender and actual checked provider/client/server C;public ops forwarding is modeled.',
                'Fresh and initialized modeled C sessions;all18 selector candidates/eight payload vectors and null provider cases.',
                'Every request is denied before modeled mutex/transport;this is not admitted RRO or native/fresh allocator proof.',
                'Real constructor2/7 uses the distinct scalar4 payload;16-byte RRO frames cannot be relabeled as it.',
                'Ignored higher-level init/reset errors,managed DMA retention,physical aliases/cache,workers/drain/reset remain open.'])
    with (directory / 'result.json').open('x') as stream: stream.write(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=record['checked_denials'] + record['null_cases'],
        payload_bytes=16, checked_RRO_admitted=False, sha256=parent.loader.sha(directory / 'result.json'))), flush=True)


if __name__ == '__main__': main()
