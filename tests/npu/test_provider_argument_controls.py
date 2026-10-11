#!/usr/bin/env python3
"""Provider-only argument rejection versus sticky issued-command failure; modeled I/O."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
import test_provider_session as parent

ENTRY = r'''
int main(void)
{
    const int invalid[] = {-1,16,3,4,6,9,13,14,15};
    unsigned cases = 0;
    for (unsigned i = 0; i < ARRAY_SIZE(invalid); i++) {
        fresh(); check(!npu_test_run(), "held setup");
        unsigned before = calls;
        uint32_t output = 0xabcdef01;
        check(airoha_npu_wlan_msg_get_session(&priv.npu, invalid[i],
              WLAN_FUNC_GET_WAIT_RXDESC_BASE, &output, 4, GFP_KERNEL) == -EINVAL,
              "invalid selector preflight");
        check(calls == before && output == 0xabcdef01 && !priv.wlan_session_error,
              "preflight has no wire/output/session effects");
        check(!airoha_npu_wlan_msg_get_session(&priv.npu, 0,
              WLAN_FUNC_GET_WAIT_NPU_VERSION, &output, 4, GFP_KERNEL),
              "valid request after argument rejection");
        check(calls == before + 1 && output == 0x457, "valid version reply");
        mutate_at = calls + 1; mutate_word = 13; mutate_value = 0;
        output = 0xabcdef01;
        check(airoha_npu_wlan_msg_get_session(&priv.npu, 0,
              WLAN_FUNC_GET_WAIT_NPU_VERSION, &output, 4, GFP_KERNEL) == -EPROTO,
              "issued malformed reply fails sticky");
        before = calls;
        check(output == 0xabcdef01 && priv.wlan_session_error == -EPROTO,
              "error retained without output");
        check(airoha_npu_wlan_msg_get_session(&priv.npu, 0,
              WLAN_FUNC_GET_WAIT_NPU_VERSION, &output, 4, GFP_KERNEL) == -EPROTO,
              "valid retry retains protocol error");
        check(calls == before && output == 0xabcdef01, "sticky retry has no effects");
        cases++;
    }
    fresh(); check(!npu_test_run(), "unmarked fixture setup");
    priv.checked_pair = false;
    unsigned before = calls;
    uint32_t output = 0xabcdef01;
    int result = airoha_npu_wlan_msg_get_session(&priv.npu, 5,
        WLAN_FUNC_GET_WAIT_RXDESC_BASE, &output, 4, GFP_KERNEL);
    check(calls == before + 1 && !priv.wlan_session_error, "unmarked raw GET routing");
    npu_test_reset(UINT64_C(0x1122334455667788), 0x83000000);
    npu_test_close();
    check(!pthread_mutex_destroy(&priv.wlan_session_lock.native), "fixture destroy");
    printf("{\"passed\":true,\"argument_cases\":%u,\"unmarked_raw_get_return\":%d}\n",cases,result);
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--header', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}',args.name)
    destination = parent.ROOT / '.local/npu-cold-descriptor-20261010' / args.name
    assert not destination.exists()
    command = parent.prepare(destination,args.source.read_text(),args.header.read_text())
    generated = destination / 'argument-controls.c'
    generated.write_text('#define main provider_matrix_main\n' + parent.HARNESS.read_text() +
                         '\n#undef main\n' + ENTRY)
    command = [generated if item == parent.HARNESS else item for item in command]
    binary = destination / 'test'
    parent.loader.run(command + ['-fsanitize=address,undefined','-fno-sanitize-recover=all','-o',binary],
                      destination / 'build.log')
    env = dict(parent.os.environ,ASAN_OPTIONS='detect_leaks=1:detect_stack_use_after_return=1')
    matrix = json.loads(parent.loader.run([binary],destination / 'run.log',env=env).stdout)
    paths = [Path(__file__),Path(parent.__file__),parent.HARNESS,args.source.resolve(),args.header.resolve()]
    paths += [path for path in parent.SOURCE.rglob('*') if path.is_file()]
    result = dict(passed=True,matrix=matrix,sanitizers=['address','undefined','leak'],
                  inputs={str(path.relative_to(parent.ROOT)):parent.loader.sha(path) for path in paths},
                  binary_sha256=parent.loader.sha(binary),
                  limits=['Actual provider wrapper/client/server C; kernel dependencies and transport effects modeled.',
                          'Unmarked test proves raw dispatch only, not actual legacy firmware getter semantics.',
                          'Provider preflight is non-sticky; issued transport/protocol failures remain sticky. No physical proof.'])
    (destination / 'result.json').write_text(json.dumps(result,indent=2) + '\n')
    print(json.dumps(matrix))


if __name__ == '__main__':
    main()
