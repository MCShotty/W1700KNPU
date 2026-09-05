#!/usr/bin/env python3
"""Compile actual mailbox code against an adversarial MMIO/firmware model."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/checkpoints/2026-09-05-npu-quiescence'
SOURCE = ROOT / '.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.44/drivers/net/ethernet/airoha/airoha_npu.c'
PREFIX = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
typedef uint32_t u32;
typedef uint16_t u16;
#define AIROHA_NPU_MBOX_SIZE 256
#define MSEC_PER_SEC 1000
#define MBOX_MSG_FUNC_ID (15u << 11)
#define MBOX_MSG_STATUS (7u << 2)
#define MBOX_MSG_DONE 2u
#define MBOX_MSG_WAIT_RSP 1u
#define NPU_MBOX_SUCCESS 1u
#define FIELD_PREP(mask,v) (((u32)(v) << __builtin_ctz(mask)) & (mask))
#define FIELD_GET(mask,v) (((v) & (mask)) >> __builtin_ctz(mask))
#define REG_CR_MBQ0_CTRL(n) (0x30c030u + (n) * 4)
struct airoha_npu_core { int lock; bool mbox_pending; unsigned char *buf; u32 addr; };
struct regmap { u32 r[4]; };
struct airoha_npu { struct airoha_npu_core cores[8]; struct regmap *regmap; };
static struct regmap map;
static struct airoha_npu npu;
static unsigned char buffer[256], payload[256], reply[256];
static int mode, write_fault, read_fault, poll_fault, writes, kicks, checked, lock_depth;
static u32 observed_flags;
static char order[64];
enum { IMMEDIATE, NEVER, FW_ERROR };
static void expect(bool ok, const char *name) {
    checked++;
    if (!ok) { printf("FAIL %s\n", name); exit(1); }
}
static void spin_lock_bh(int *lock) { (void)lock; expect(!lock_depth, "nonrecursive lock"); lock_depth++; }
static void spin_unlock_bh(int *lock) { (void)lock; expect(lock_depth == 1, "balanced unlock"); lock_depth--; }
static void complete_request(bool error) {
    memset(buffer, 0xa5, map.r[1]);
    map.r[3] |= MBOX_MSG_DONE | (error ? 0 : FIELD_PREP(MBOX_MSG_STATUS, NPU_MBOX_SUCCESS));
}
static int regmap_read(struct regmap *m, u32 reg, u32 *value) {
    unsigned index = (reg - REG_CR_MBQ0_CTRL(0)) / 4;
    expect(index < 4, "read register range");
    if ((int)index == read_fault) return -EIO;
    *value = m->r[index];
    return 0;
}
static int regmap_write(struct regmap *m, u32 reg, u32 value) {
    unsigned index = (reg - REG_CR_MBQ0_CTRL(0)) / 4;
    expect(index < 4, "write register range");
    order[writes++] = "ALPF"[index];
    if ((int)index == write_fault) return -EIO;
    m->r[index] = value;
    if (index == 2) {
        kicks++;
        observed_flags = m->r[3];
        if (mode != NEVER) complete_request(mode == FW_ERROR);
    }
    return 0;
}
#define regmap_read_poll_timeout_atomic(m,r,v,c,d,t) ({ \
    int status = poll_fault ? -EIO : regmap_read((m),(r),&(v)); \
    if (!status && !(c)) status = -ETIMEDOUT; status; })
static void reset_model(void) {
    memset(&map, 0, sizeof(map)); memset(&npu, 0, sizeof(npu));
    memset(buffer, 0xcc, sizeof(buffer)); memset(payload, 0x11, sizeof(payload));
    memset(reply, 0x77, sizeof(reply)); memset(order, 0, sizeof(order));
    npu.regmap = &map; npu.cores[0].buf = buffer; npu.cores[0].addr = 0x12340000;
    mode = IMMEDIATE; write_fault = read_fault = -1; poll_fault = 0;
    writes = kicks = lock_depth = 0; observed_flags = 0;
}
'''
SUFFIX = r'''
static int send(int len, int out_len) { return __airoha_npu_send_msg(&npu, 5, payload, len, reply, out_len); }
static void order_case(void) {
    reset_model();
    int ret = send(16, 4);
    expect(ret == 0, "immediate-consumer completion must not be overwritten");
    expect(observed_flags == (FIELD_PREP(MBOX_MSG_FUNC_ID, 5) | 1), "current command before producer counter");
    expect(!strcmp(order, "ALFP"), "address length flags producer publication order");
    expect(reply[0] == 0xa5 && reply[4] == 0x77, "bounded trailing reply copy");
    expect(!npu.cores[0].mbox_pending, "successful request returns buffer ownership");
}
static void timeout_case(void) {
    reset_model(); mode = NEVER;
    expect(send(16, 4) == -ETIMEDOUT, "first request times out");
    unsigned char retained[256]; memcpy(retained, buffer, sizeof(retained));
    int old_writes = writes; memset(payload, 0x22, sizeof(payload));
    int ret = send(16, 4);
    expect(!memcmp(retained, buffer, sizeof(retained)), "timed-out request buffer must not be overwritten");
    expect(ret == -EBUSY && writes == old_writes, "pending retry must not publish another request");
    expect(npu.cores[0].mbox_pending, "pending ownership retained");
    read_fault = 3;
    expect(send(16, 4) == -EIO && writes == old_writes, "pending status read failure retains request");
    read_fault = -1; complete_request(false); mode = IMMEDIATE;
    expect(send(16, 4) == 0 && kicks == 2, "late completion permits next transaction");
    expect(!npu.cores[0].mbox_pending && reply[0] == 0xa5, "new reply after late completion");
}
int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "order")) { order_case(); return 0; }
    if (argc == 2 && !strcmp(argv[1], "timeout")) { timeout_case(); return 0; }
    order_case(); timeout_case();
    reset_model(); expect(send(-1, 0) == -EINVAL && !writes && !lock_depth, "negative length rejected");
    reset_model(); expect(send(257, 0) == -EINVAL && !writes, "oversize length rejected");
    reset_model(); expect(send(4, 5) == -EINVAL && !writes, "oversize reply rejected");
    reset_model(); expect(send(256, 256) == 0 && reply[255] == 0xa5, "maximum buffer supported");
    reset_model(); expect(send(0, 0) == 0, "zero-length request compatibility");
    reset_model(); mode = FW_ERROR;
    expect(send(16, 4) == -EINVAL && !npu.cores[0].mbox_pending && reply[0] == 0x77, "firmware error releases completed buffer without reply copy");
    mode = IMMEDIATE; expect(send(16, 4) == 0, "reuse after completed firmware error");
    reset_model(); read_fault = 2;
    expect(send(16, 4) == -EIO && !writes && buffer[0] == 0xcc, "counter read fails before buffer preparation");
    for (int i = 0; i < 4; i++) {
        reset_model(); write_fault = i;
        expect(send(16, 4) == -EIO && !kicks, "register failure prevents successful publication");
        expect(npu.cores[0].mbox_pending == (i >= 2), "publication errors retain conservative ownership");
    }
    reset_model(); mode = NEVER; poll_fault = 1;
    expect(send(16, 4) == -EIO && npu.cores[0].mbox_pending, "poll error retains ownership");
    reset_model(); map.r[2] = UINT32_MAX;
    expect(send(16, 4) == 0 && map.r[2] == 0, "32-bit producer counter wraps");
    reset_model();
    expect(__airoha_npu_send_msg(&npu, 0, payload, 16, NULL, 0) == 0, "no-reply call supported");
    expect(lock_depth == 0, "final lock balance");
    printf("PASS assertions=%d\n", checked);
    return 0;
}
'''


def function(path):
    source = path.read_text()
    start = source.index('static int __airoha_npu_send_msg(')
    return source[start:source.index('\nstatic int airoha_npu_send_msg(', start)]


def compile_body(body, directory, name):
    source = directory / (name + '.c')
    source.write_text(PREFIX + body + SUFFIX)
    executable = directory / name
    subprocess.run(['gcc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-Wno-misleading-indentation', str(source), '-o', str(executable)], check=True)
    return executable


def main():
    baseline = ROOT / 'tests/npu/fixtures/airoha-mailbox-before.c'
    with tempfile.TemporaryDirectory(prefix='npu-mailbox-test-') as temp:
        good = compile_body(function(SOURCE), Path(temp), 'fixed')
        old = compile_body(function(baseline), Path(temp), 'before')
        fixed = subprocess.run([str(good)], capture_output=True, text=True)
        controls = {name: subprocess.run([str(old), name], capture_output=True, text=True)
                    for name in ['order', 'timeout']}
    if fixed.returncode or not fixed.stdout.startswith('PASS'):
        raise RuntimeError(fixed.stdout + fixed.stderr)
    if any(not value.returncode or 'FAIL' not in value.stdout for value in controls.values()):
        raise RuntimeError('Preimage negative control did not reproduce the ownership/order defect')
    report = {'passed': True, 'fixed': fixed.stdout.strip(),
              'negative_controls': {name: value.stdout.strip() for name, value in controls.items()},
              'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'preimage_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(),
              'scope': 'actual compiled mailbox function with adversarial MMIO stubs; not WLAN DMA quiescence or hardware proof'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'mailbox-tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
