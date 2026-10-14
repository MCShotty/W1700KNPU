#!/usr/bin/env python3
"""Actual provider/wrapper/caller C with explicit stage/regmap fixtures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
import test_npu_firmware_loader as loader

ROOT = loader.ROOT
PROVIDER = ROOT / ".local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c"
KHEADER = ROOT / ".local/merge-nonoc-20260923/kernel-merged/include/linux/soc/airoha/airoha_offload.h"
HEADER = ROOT / ".local/merge-nonoc-20260923/mt76-merged/airoha_offload.h"
CALLER = ROOT / ".local/merge-nonoc-20260923/mt76-merged/mt7996/npu.c"
POLL = ROOT / ".local/merge-nonoc-20260923/mt76-merged/mt7996/mmio.c"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    assert args.name.replace("-", "").isalnum()
    dest = ROOT / ".local/npu-final-irq-contract" / args.name
    assert not dest.exists()
    dest.mkdir(parents=True)
    paths = [PROVIDER, KHEADER, HEADER, CALLER, POLL, Path(__file__), Path(loader.__file__), Path(loader.extract.__file__)]
    inputs = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    provider = PROVIDER.read_text()
    macros = [line for line in provider.splitlines() if line.startswith("#define ") and
              line.split()[1].split("(")[0] in ("NPU_WLAN_BASE_ADDR", "REG_IRQ_RXDONE", "NPU_IRQ_RX_MASK")]
    assert len(macros) == 3
    enable = loader.extract.function(provider, "airoha_npu_wlan_irq_enable")
    wrapper = loader.extract.function(HEADER.read_text(), "airoha_npu_wlan_enable_irq")
    caller = loader.extract.function(CALLER.read_text(), "__mt7996_npu_hw_init")
    assert "void (*wlan_enable_irq)" in KHEADER.read_text()
    assert "airoha_npu_wlan_enable_irq(npu, q - MT_RXQ_NPU0)" in POLL.read_text()
    prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
#define BIT(n) (1u << (n))
#define MT_RXQ_NPU0 10
#define MT_RXQ_NPU1 11
#define rcu_dereference_protected(pointer, mutex) (pointer)
struct airoha_npu { void *regmap; struct { void (*wlan_enable_irq)(struct airoha_npu *, int); } ops; };
struct mt76_dev { struct { struct airoha_npu *npu; } mmio; int mutex; };
struct mt7996_dev { struct mt76_dev mt76; };
static int errors[2], applied[2], calls[16], count, failed_stage;
static u32 bits[2], original_bits[2];
static int cookie;
static struct airoha_npu npu;
static struct mt7996_dev dev;
static int regmap_set_bits(void *map, u32 reg, u32 mask) {
    assert(map==&cookie);
    int q=reg==0x30d034u ? 0 : reg==0x30d038u ? 1 : -1;
    assert(q>=0 && mask==(q ? 0x20000u : 0x10000u));
    calls[count++]=8+q;
    if(applied[q]) bits[q]|=mask;
    return errors[q];
}
static int stage(int n) { calls[count++]=n; return failed_stage==n ? -200-n : 0; }
static int is_mt7996(struct mt76_dev *m) { assert(m==&dev.mt76); return 1; }
static int mt7996_npu_rx_event_validate(struct mt7996_dev *d) { assert(d==&dev); return stage(1); }
#define STUB(name,n) static int name(struct mt7996_dev *d, struct airoha_npu *p) { assert(d==&dev && p==&npu); return stage(n); }
STUB(mt7996_npu_offload_init,2)
STUB(mt7996_npu_rxd_init,3)
STUB(mt7992_npu_rxd_init,3)
STUB(mt7996_npu_txd_init,4)
STUB(mt7996_npu_rx_event_init,5)
STUB(mt7996_npu_set_pcie_addr,6)
STUB(mt7996_npu_tx_done_init,7)
'''
    suffix = r'''
static void reset(void) {
    memset(calls,0,sizeof(calls)); count=failed_stage=0;
    errors[0]=errors[1]=0; applied[0]=applied[1]=1;
    bits[0]=original_bits[0]=0xa5002000u;
    bits[1]=original_bits[1]=0x5a000008u;
    npu.regmap=&cookie; npu.ops.wlan_enable_irq=airoha_npu_wlan_irq_enable;
    dev.mt76.mmio.npu=&npu;
}
int main(void) {
    const int matrix[][2]={{0,0},{-5,0},{0,-5},{-5,-5},{-110,0},{0,-110}};
    unsigned cases=0, irq_cases=0, lost=0;
    for(unsigned i=0;i<sizeof(matrix)/sizeof(matrix[0]);i++)for(unsigned effect=0;effect<4;effect++) {
        reset();
        for(int q=0;q<2;q++){ errors[q]=matrix[i][q]; applied[q]=(effect>>q)&1; }
        if((!errors[0]&&!applied[0])||(!errors[1]&&!applied[1])) continue;
        /* The actual void ABI cannot propagate either modeled write error. */
        assert(__mt7996_npu_hw_init(&dev)==0);
        assert(count==9); for(int j=0;j<9;j++)assert(calls[j]==j+1);
        for(int q=0;q<2;q++)assert(bits[q]==(original_bits[q]|(applied[q]?(q?0x20000u:0x10000u):0)));
        cases++; irq_cases++; lost+=(errors[0]||errors[1]);
    }
    for(int n=1;n<=7;n++) {
        reset(); failed_stage=n;
        assert(__mt7996_npu_hw_init(&dev)==-200-n && count==n);
        assert(bits[0]==original_bits[0] && bits[1]==original_bits[1]);
        for(int j=0;j<n;j++)assert(calls[j]==j+1); cases++;
    }
    reset(); dev.mt76.mmio.npu=0;
    assert(__mt7996_npu_hw_init(&dev)==0 && !count); cases++;
    assert(cases==21 && irq_cases==13 && lost==12);
    printf("{\"passed\":true,\"cases\":%u,\"irq_cases\":%u,\"lost_error_cases\":%u,\"early_error_cases\":7}\n",cases,irq_cases,lost);
    return 0;
}
'''
    source, binary = dest / "actual.c", dest / "actual"
    source.write_text(prefix + "\n".join(macros) + "\n" + enable + "\n" + wrapper + "\n" + caller + suffix)
    loader.run([shutil.which("clang"), "-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                "-fno-omit-frame-pointer", "-fsanitize=address,undefined", source, "-o", binary], dest / "build.log")
    result = loader.run([binary], dest / "run.log", env=dict(os.environ,
        ASAN_OPTIONS="detect_leaks=1:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1"))
    assert all(sha(ROOT / n) == h for n, h in inputs.items())
    record = json.loads(result.stdout)
    record.update(inputs=inputs, binary_sha256=sha(binary), generated_source_sha256=sha(source),
                  actual_provider_wrapper_caller=True, stages_and_regmap_modeled=True,
                  source_changed=False, hardware=False,
                  limits=["Actual extracted current C bodies; initializer stages and MMIO/regmap effects/errors are explicit fixtures.",
                          "The final two calls are host register writes, not native NPU mailbox callbacks.",
                          "This proves error-loss behavior under these fixtures, not observed physical bus errors or drain/ready acceptance.",
                          "Poll re-enable is a second caller and must retain appropriate runtime fault/lifetime handling."])
    (dest / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"passed": True, "cases": record["cases"], "lost_error_cases": record["lost_error_cases"],
                      "output": str(dest / "result.json")}), flush=True)


if __name__ == "__main__":
    main()
