#!/usr/bin/env python3
"""Compile the actual typed-record guard; allocator state is a labeled fixture."""
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
    body = loader.extract.function(SOURCE.read_text(), 'typed_pool')
    assert body in SOURCE.read_text()
    prefix = '#include <assert.h>\n#include <stdio.h>\n#include <string.h>\n#include "allocator.h"\n'
    suffix = r'''
static unsigned cases;
static void check(uint32_t type, uint32_t bytes, unsigned bad) {
    struct npu_allocator_state state = {.count=1};
    uint32_t pool=0x3e800020u;
    state.entries[0]=(struct npu_allocator_entry){.type=type,.address=pool};
    const struct npu_allocator_state *input=&state;
    switch (bad) {
    case 1: input=NULL; break;
    case 2: state.count=101; break;
    case 3: state.count=0; break;
    case 4: state.entries[0].reserved=1; break;
    case 5: state.entries[0].type^=1; break;
    case 6: state.entries[0].address+=32; break;
    case 7: pool+=32; break;
    case 8: pool+=1; state.entries[0].address=pool; break;
    case 9: pool=0x3e7fffe0u; state.entries[0].address=pool; break;
    case 10: pool=0x3e877fe0u; state.entries[0].address=pool; break;
    case 11: state.count=2; state.entries[1]=state.entries[0]; break;
    case 12: state.count=2; state.entries[1]=state.entries[0]; state.entries[1].type^=1; break;
    case 13: bytes=0; break;
    case 14: bytes=0x78001; break;
    case 15: pool=0xffffffe0u; state.entries[0].address=pool; break;
    case 16: pool=0; state.entries[0].address=pool; break;
    case 17: state.count=2; state.entries[1]=state.entries[0]; state.entries[1].address+=32; break;
    case 18: pool=0x3e878000u-bytes; state.entries[0].address=pool; break;
    }
    struct npu_allocator_state before=state;
    assert(typed_pool(input,type,pool,bytes)==(bad==0 || bad==18));
    assert(!memcmp(&state,&before,sizeof(state))); cases++;
}
int main(void) {
    const uint32_t types[]={0x8a,0x12,0x1d},sizes[]={32768,57344,4096};
    for(unsigned i=0;i<3;i++)for(unsigned bad=0;bad<19;bad++)check(types[i],sizes[i],bad);
    printf("{\"passed\":true,\"cases\":%u}\n",cases); return 0;
}
'''
    variants = [('nominal', body, 0)]
    for name, old, new in (
        ('ignore-record-address', 'entry->reserved || entry->address != pool)', 'entry->reserved || 0)'),
        ('ignore-reserved-record', 'entry->reserved ||', ''),
        ('accept-duplicate-record', 'found || entry->type', 'entry->type')):
        variants.append((name, loader.once(body, old, new), -6))
    programs = []
    for name, function, expected in variants:
        source = destination / (name + '.c')
        source.write_text(prefix + function + suffix)
        binary = destination / name
        loader.run(['clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
            '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
            '-I' + str(ROOT / 'firmware/npu'), source, '-o', binary], destination / (name + '-build.log'))
        done = loader.run([binary], destination / (name + '-run.log'), accepted=expected,
                          env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1'))
        if not expected:
            matrix = json.loads(done.stdout)
        else:
            assert 'Assertion' in done.stderr and 'AddressSanitizer' not in done.stderr
        programs.append(dict(name=name, exit_code=done.returncode, sha256=loader.sha(binary)))
    paths = (SOURCE, Path(__file__).resolve(), Path(loader.__file__), Path(loader.extract.__file__),
             ROOT / 'firmware/npu/allocator.h')
    result = dict(passed=True, cases=matrix['cases'], mutants=len(variants)-1, programs=programs,
        inputs={str(path.relative_to(ROOT)): loader.sha(path) for path in paths},
        limits=['Actual extracted typed-record and heap-extent guard with host sanitizers.',
                'Allocator state is modeled; paired-CODE definitions and full native context are separate checks.',
                'No fresh native allocator/caller, physical backing, DMA/drain or client proof.'])
    (destination / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, cases=matrix['cases'], mutants=len(variants)-1)))


if __name__ == '__main__':
    main()
