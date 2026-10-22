#!/usr/bin/env python3
"""Run actual TX allocator STATUS through the exact assembled RV32 peer."""
import argparse
import ctypes
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode=True
import test_provider_session as parent
import test_host_tx_lifetime as lifetime
import test_host_rx_event_lifetime as rx_lifetime


def checked_host_sender(receipt):
    assert receipt['passed'] is True, 'host-sender-receipt-not-passed'
    path = (parent.ROOT / receipt['shared']).resolve()
    assert path.is_relative_to(parent.ROOT / '.local'), 'host-sender-path-outside-private-storage'
    expected = receipt['shared_sha256']
    assert parent.loader.sha(path) == expected, 'host-sender-binary-drift'
    return path, {str(path.relative_to(parent.ROOT)): expected}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--header',type=Path,required=True)
    parser.add_argument('--pair',type=Path,required=True)
    parser.add_argument('--publication',type=Path,required=True)
    parser.add_argument('--host-receipt',type=Path,required=True)
    parser.add_argument('--name',required=True)
    parser.add_argument('--rx-event',action='store_true')
    parser.add_argument('--desc10',action='store_true')
    parser.add_argument('--nominal-only',action='store_true')
    parser.add_argument('--pcie-tail',action='store_true')
    parser.add_argument('--inode',action='store_true')
    parser.add_argument('--hif2',action='store_true')
    parser.add_argument('--event-journal', action='store_true',
                        help='Lossless disk-backed observer events; native limits/checkpoints remain unchanged')
    args=parser.parse_args()
    assert not args.desc10 or args.rx_event
    assert not args.pcie_tail or args.desc10
    assert args.inode == args.pcie_tail, 'current-tail-sender-requires-explicit-INODE-qualification'
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    root=parent.ROOT;q=parent.loader.extract
    destination=root/'.local/npu-host-tx-lifetime-20261011'/args.name
    assert not destination.exists()
    source,header=args.source.resolve(),args.header.resolve()
    paths=[source,header,parent.HARNESS,Path(__file__).resolve(),Path(parent.__file__),
           Path(lifetime.__file__),Path(rx_lifetime.__file__),Path(parent.loader.__file__),Path(q.__file__),
           root/'tests/npu/tx_buffer_native_controls.py',root/'tests/npu/test_cold_tx_buffer.py']
    paths += [path for path in parent.SOURCE.rglob('*') if path.is_file()]
    inputs={str(path.relative_to(root)):parent.loader.sha(path) for path in paths}
    text,htext=source.read_text(),header.read_text()
    command=parent.prepare(destination,text,htext)
    inc=destination/'provider-session.inc'
    functions=[q.function(text,name) for name in ('airoha_npu_wlan_rx_event_valid',
        'airoha_npu_wlan_tx_buffer_valid','airoha_npu_wlan_alloc_tx_buffers_session') if name not in parent.FUNCTIONS]
    if args.rx_event:
        functions.insert(1,q.function(text,'airoha_npu_wlan_alloc_rx_event_session'))
    inc.write_text(inc.read_text()+'\n'.join(functions))
    model=parent.HARNESS.read_text()
    if args.pcie_tail:
        legacy=q.function(text,'airoha_npu_wlan_msg_send')
        declarations='\n'.join(q.macro(text,name) for name in
            ('NPU_EN7581_7996_TX_CHECK_SIZE','NPU_EN7581_7996_INODE_DATA_SIZE'))
        framing=r'''
typedef uint16_t u16;
#define DECLARE_FLEX_ARRAY(type,name) type name[]
#define NPU_OP_SET 1
#define NPU_FUNC_WIFI 0
static void *npu_test_raw_alloc(size_t bytes,gfp_t flags) {
    check(flags==GFP_KERNEL,"modeled raw-frame allocator");return calloc(1,bytes);
}
static void npu_test_raw_free(void *pointer) { free(pointer); }
static int airoha_npu_send_msg(struct airoha_npu *npu,int function,void *data,int bytes) {
    check(npu==&priv.npu && function==NPU_FUNC_WIFI,"actual legacy wrapper transport");
    return transaction(data,bytes);
}
#define kzalloc npu_test_raw_alloc
#define kfree npu_test_raw_free
'''
        raw=declarations+'\n'+framing+'\n'+q.declaration(text,'struct','wlan_mbox_data')+'\n'+legacy+'\n#undef kzalloc\n#undef kfree\n'
        model=parent.loader.once(model,q.function(model,'airoha_npu_wlan_msg_send'),raw)
    platform=rx_lifetime.PLATFORM if args.rx_event else lifetime.PLATFORM
    model=parent.loader.once(model,'#include "provider-session.inc"',platform+'\n#include "provider-session.inc"')
    entry=r'''
int npu_test_allocate_tx(void) {
    const u32 sizes[]={0x20000,0x20000,0x40000,0x40000,0x40000,0x40000};
    dma_addr_t output[6]={0};fail_allocation=99;
    for(unsigned i=0;i<8;i++) {
        life.buffers[i].buf=(void *)(uintptr_t)(i+1);
        life.buffers[i].addr=priv.native_plan[5][0]+i*256;
    }
    unsigned shift=0;
#ifdef RX_EVENT
    void *rx_buf=NULL;dma_addr_t rx_addr=0;
    addresses[0]=0x97000000u;
    int rx_error=airoha_npu_wlan_alloc_rx_event_session(&priv.npu,&endpoint_device,&dma_device,
                                                     512,16,&rx_buf,&rx_addr);
    check(!rx_error && dma_calls==1 && object_count==1 && life.rx_published && life.rx_attempted &&
          life.rx_event.buf==rx_buf && life.rx_event.addr==rx_addr && life.rx_event.bytes==8192 &&
          rx_addr==addresses[0],"native RX-event allocator STATUS and retained record");
    shift=1;
#endif
    for(unsigned i=0;i<6;i++)addresses[i+shift]=0x96000000u+i*0x100000u;
    int error=airoha_npu_wlan_alloc_tx_buffers_session(&priv.npu,&endpoint_device,&dma_device,sizes,output,6);
    check(!error && dma_calls==6+shift && object_count==6+shift && life.tx_published && life.tx_attempted &&
          priv.wlan_control.txbuf_enrolled==14,"native allocator publication after enrollment");
    for(unsigned i=0;i<6;i++)check(output[i]==addresses[i+shift] && life.tx_buffers[i].addr==output[i] && life.tx_buffers[i].buf,"native retained allocation records");
    return error;
}
void npu_test_dispose_tx_fixture(void) { for(unsigned i=0;i<object_count;i++)free(objects[i]); }
'''
    generated=destination/'native.c'
    generated.write_text('#define main provider_matrix_main\n'+model+'\n#undef main\n'+entry)
    command=[generated if item==parent.HARNESS else item for item in command]
    shared=destination/'native.so'
    flags=['-Wno-unused-function','-Wno-unused-variable','-shared','-fPIC']
    if args.pcie_tail:flags+=['-Wno-sign-compare']
    if args.rx_event:flags+=['-DRX_EVENT']
    parent.loader.run(command+flags+['-o',shared],destination/'build.log')
    host=json.loads(args.host_receipt.read_bytes())
    assert host['passed'] and all(parent.loader.sha(root/path)==digest for path,digest in host['inputs'].items())
    inputs |= host['inputs']
    host_sender, sender_inputs = checked_host_sender(host)
    assert all(name not in inputs or inputs[name] == digest for name, digest in sender_inputs.items())
    inputs |= sender_inputs
    inputs |= {str(path.relative_to(root)): parent.loader.sha(path)
               for path in destination.rglob('*') if path.is_file() and path.suffix in ('.c', '.h', '.inc', '.so')}
    original_cdll=ctypes.CDLL
    observed=[]

    class Endpoint:
        def __init__(self,target,library):
            object.__setattr__(self,'target',target);object.__setattr__(self,'library',library)
        def __getattr__(self,key):return getattr(self.target,key)
        def __setattr__(self,key,value):setattr(self.target,key,value)
        def __call__(self,*values):
            result=self.target(*values)
            if not result:
                allocate=self.library.npu_test_allocate_tx;allocate.restype=ctypes.c_int
                assert allocate()==0
                observed.append(dict(allocations=6,published=True))
            return result

    class Library:
        def __init__(self,library):
            self.library=library;self.endpoint=Endpoint(library.npu_test_endpoint,library)
        def __getattr__(self,key):return self.endpoint if key=='npu_test_endpoint' else getattr(self.library,key)

    loaded=[]
    journal = None
    if args.event_journal:
        from native_event_journal import EventJournal
        journal = EventJournal(destination / 'native-events.sqlite')
        path = root / 'tests/npu/native_event_journal.py'
        inputs[str(path.relative_to(root))] = parent.loader.sha(path)
    def load(path,*values,**options):
        library=original_cdll(path,*values,**options)
        if path is not None and Path(path).resolve()==shared:
            loaded.append(library);return Library(library)
        return library
    ctypes.CDLL=load
    try:
        native=parent.native_peer(shared,args.pair.resolve(),args.publication.resolve(),cold_commands=True,
                                  host_sender=host_sender,txbuffer_enrollment=True,rx_event=args.rx_event,
                                  desc10=args.desc10,pcie_tail=args.pcie_tail,inode=args.inode,hif2=args.hif2,
                                  nominal_only=args.nominal_only,producer_inputs=inputs,event_journal=journal)
    finally:
        ctypes.CDLL=original_cdll
        for library in loaded:library.npu_test_dispose_tx_fixture()
        if journal is not None: journal.close()
    assert native['passed'] and observed==[dict(allocations=6,published=True)]
    inputs |= native['inputs']
    for path in (shared,args.host_receipt.resolve()):inputs[str(path.relative_to(root))]=parent.loader.sha(path)
    assert all(parent.loader.sha(root/path)==digest for path,digest in inputs.items())
    result=dict(passed=True,allocations=observed,native=native,inputs=inputs,native_enrollment_records=14+int(args.rx_event),
        rx_event_allocations=int(args.rx_event),rx_event_bytes=8192 if args.rx_event else 0,
        pcie_tail_requested=args.pcie_tail,actual_legacy_wrapper_framing=False,
        actual_legacy_wrapper_compiled=args.pcie_tail, inode_checked_framing=args.inode,
        inode_requested=args.inode,
        limits=['Actual provider allocation/STATUS/client C with raw RV32 reply execution; DMA backing/device references/delivery/scheduling are modeled.',
                'Allocation runs after real BAR binding and before real offload/RX/TX caller replay. TX caller uses the returned retained handles.',
                'Original API21 instructions are guarded by retained store ownership; physical buffer consumption is not established.',
                'Fixture-only frees after assertions are not production retirement. No physical exclusion/coherency/drain or hardware/client acceptance.'])
    (destination/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,tx_allocations=6,native_status=True,
                          native_enrollment_records=14+int(args.rx_event))))


if __name__=='__main__':main()
