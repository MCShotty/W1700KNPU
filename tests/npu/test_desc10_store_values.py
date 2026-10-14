"""Compile the actual native reserve boundary with explicitly modeled owners."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import test_npu_firmware_loader as loader

ROOT = loader.ROOT
SOURCE = ROOT / 'tests/npu/cold-txdone-native-emulation.c'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert args.name.replace('-', '').isalnum()
    destination = ROOT / '.local/npu-desc10-native-20261014' / args.name
    destination.mkdir()
    signature = 'uint32_t npu_emulation_desc10_reserve('
    alias = 'u32 npu_emulation_desc10_reserve('
    view = loader.once(SOURCE.read_text(), signature, alias)
    body = loader.once(loader.extract.function(view, 'npu_emulation_desc10_reserve'), alias, signature)
    assert body in SOURCE.read_text()
    prefix = r'''
#include <assert.h>
#include <stdio.h>
#include "cold-txdone.h"
static struct npu_cold_txdone_state owner;
static struct npu_cold_txdone_plan plan;
static struct npu_cold_txdone_store desired;
#define OWNER (&owner)
static uint32_t npu_emulation_callback_guarded, allowed, reads, reserved, faults;
static int context(uint32_t full) { (void)full; return allowed; }
static uint32_t read(uint32_t address, uint32_t bytes) {
    assert(address == desired.address && bytes == desired.bytes); reads++; return 7;
}
static uint32_t fail(void) { faults++; return 0; }
uint32_t npu_cold_txdone_recipe(const struct npu_cold_txdone_state *s,
                               struct npu_cold_txdone_store *out) {
    assert(s == OWNER); *out = desired; return 0;
}
uint32_t npu_cold_txdone_reserve(struct npu_cold_txdone_state *s,
    const struct npu_cold_txdone_plan *p, uint32_t epoch, uint32_t address,
    uint32_t bytes, uint32_t value, uint32_t preimage) {
    assert(s == OWNER && p == &plan && epoch == 1 && address == desired.address &&
           bytes == desired.bytes && value == desired.value && preimage == 7);
    reserved++; return 0;
}
'''
    suffix = r'''
static unsigned cases;
static void check(uint32_t bytes, uint32_t value, unsigned bad) {
    desired = (struct npu_cold_txdone_store){.address=0x3e802000,.bytes=bytes,
                                          .value=bytes == 4 ? value : value & (bytes == 1 ? 255 : 65535)};
    allowed = npu_emulation_callback_guarded = 1; reads = reserved = faults = 0;
    uint32_t address = desired.address, width = bytes, actual = value;
    if (bad == 1) actual ^= 1;
    if (bad == 2) width = 3;
    if (bad == 3) address = 0xdead0000;
    if (bad == 4) allowed = 0;
    if (bad == 5) npu_emulation_callback_guarded = 0;
    uint32_t result = npu_emulation_desc10_reserve(address, actual, width);
    assert(result == !bad && reads == !bad && reserved == !bad && faults == !!bad);
    cases++;
}
int main(void) {
    for (unsigned bad=0;bad<6;bad++) {
        check(1,0xffffff80,bad); check(2,0xffffffff,bad); check(4,0xf1234567,bad);
    }
    printf("{\"passed\":true,\"cases\":%u}\n",cases);
    return 0;
}
'''
    programs = []
    for name, function, expected in (
        ('nominal', body, 0),
        ('keep-register-upper-bits', loader.once(body, 'value &= bytes == 1 ? 0xffu : 0xffffu;', '(void)value;'), -6)):
        path = destination / (name + '.c')
        path.write_text(prefix + function + suffix)
        binary = destination / name
        loader.run(['clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-I' + str(ROOT / 'firmware/npu'), path, '-o', binary], destination / (name + '-build.log'))
        done = loader.run([binary], destination / (name + '-run.log'), accepted=expected,
                          env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1'))
        if not expected:
            matrix = json.loads(done.stdout)
        else:
            assert 'Assertion' in done.stderr and 'AddressSanitizer' not in done.stderr
        programs.append(dict(name=name, exit_code=done.returncode, sha256=loader.sha(binary)))
    inputs = {str(path.relative_to(ROOT)): loader.sha(path) for path in
              (SOURCE, Path(__file__).resolve(), Path(loader.__file__), Path(loader.extract.__file__))}
    inputs |= {str(path.relative_to(ROOT)): loader.sha(path) for path in (ROOT / 'firmware/npu').glob('*.h')}
    result = dict(passed=True, matrix=matrix, mutants=1, programs=programs, inputs=inputs,
                  limits=['Actual extracted native reserve boundary is compiled with host sanitizers.',
                          'Context, recipe and owner reservation are modeled; this is width/value/address boundary scope only.',
                          'No complete native callback, register preservation, physical or client proof.'])
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=matrix['cases'], mutants=1)))


if __name__ == '__main__':
    main()
