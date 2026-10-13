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


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--header',type=Path,required=True)
    parser.add_argument('--pair',type=Path,required=True)
    parser.add_argument('--publication',type=Path,required=True)
    parser.add_argument('--host-receipt',type=Path,required=True)
    parser.add_argument('--name',required=True)
    args=parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    root=parent.ROOT;q=parent.loader.extract
    destination=root/'.local/npu-host-tx-lifetime-20261011'/args.name
    assert not destination.exists()
    source,header=args.source.resolve(),args.header.resolve()
    paths=[source,header,parent.HARNESS,Path(__file__).resolve(),Path(parent.__file__),
           Path(lifetime.__file__),Path(parent.loader.__file__),Path(q.__file__),
           root/'tests/npu/tx_buffer_native_controls.py',root/'tests/npu/test_cold_tx_buffer.py']
    paths += [path for path in parent.SOURCE.rglob('*') if path.is_file()]
    inputs={str(path.relative_to(root)):parent.loader.sha(path) for path in paths}
    text,htext=source.read_text(),header.read_text()
    command=parent.prepare(destination,text,htext)
    inc=destination/'provider-session.inc'
    functions=[q.function(text,name) for name in ('airoha_npu_wlan_tx_buffer_valid','airoha_npu_wlan_alloc_tx_buffers_session')]
    inc.write_text(inc.read_text()+'\n'.join(functions))
    model=parent.HARNESS.read_text()
    model=parent.loader.once(model,'#include "provider-session.inc"',lifetime.PLATFORM+'\n#include "provider-session.inc"')
    entry=r'''
int npu_test_allocate_tx(void) {
    const u32 sizes[]={0x20000,0x20000,0x40000,0x40000,0x40000,0x40000};
    dma_addr_t output[6]={0};fail_allocation=99;
    for(unsigned i=0;i<8;i++) {
        life.buffers[i].buf=(void *)(uintptr_t)(i+1);
        life.buffers[i].addr=priv.native_plan[5][0]+i*256;
    }
    for(unsigned i=0;i<6;i++)addresses[i]=0x96000000u+i*0x100000u;
    int error=airoha_npu_wlan_alloc_tx_buffers_session(&priv.npu,&endpoint_device,&dma_device,sizes,output,6);
    check(!error && dma_calls==6 && object_count==6 && life.tx_published && life.tx_attempted &&
          priv.wlan_control.txbuf_enrolled==14,"native allocator publication after enrollment");
    for(unsigned i=0;i<6;i++)check(output[i]==addresses[i] && life.tx_buffers[i].addr==output[i] && life.tx_buffers[i].buf,"native retained allocation records");
    return error;
}
void npu_test_dispose_tx_fixture(void) { for(unsigned i=0;i<object_count;i++)free(objects[i]); }
'''
    generated=destination/'native.c'
    generated.write_text('#define main provider_matrix_main\n'+model+'\n#undef main\n'+entry)
    command=[generated if item==parent.HARNESS else item for item in command]
    shared=destination/'native.so'
    parent.loader.run(command+['-Wno-unused-function','-Wno-unused-variable','-shared','-fPIC','-o',shared],destination/'build.log')
    host=json.loads(args.host_receipt.read_bytes())
    assert host['passed'] and all(parent.loader.sha(root/path)==digest for path,digest in host['inputs'].items())
    inputs |= host['inputs']
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
    def load(path,*values,**options):
        library=original_cdll(path,*values,**options)
        if path is not None and Path(path).resolve()==shared:
            loaded.append(library);return Library(library)
        return library
    ctypes.CDLL=load
    try:
        native=parent.native_peer(shared,args.pair.resolve(),args.publication.resolve(),cold_commands=True,
                                  host_sender=root/host['shared'],txbuffer_enrollment=True)
    finally:
        ctypes.CDLL=original_cdll
        for library in loaded:library.npu_test_dispose_tx_fixture()
    assert native['passed'] and observed==[dict(allocations=6,published=True)]
    inputs |= native['inputs']
    for path in (shared,args.host_receipt.resolve()):inputs[str(path.relative_to(root))]=parent.loader.sha(path)
    assert all(parent.loader.sha(root/path)==digest for path,digest in inputs.items())
    result=dict(passed=True,allocations=observed,native=native,inputs=inputs,native_enrollment_records=14,
        limits=['Actual provider allocation/STATUS/client C with raw RV32 reply execution; DMA backing/device references/delivery/scheduling are modeled.',
                'Allocation runs after real BAR binding and before real offload/RX/TX caller replay. TX caller uses the returned retained handles.',
                'Original API21 instructions are guarded by retained store ownership; physical buffer consumption is not established.',
                'Fixture-only frees after assertions are not production retirement. No physical exclusion/coherency/drain or hardware/client acceptance.'])
    (destination/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,tx_allocations=6,native_status=True,native_enrollment_records=14)))


if __name__=='__main__':main()
