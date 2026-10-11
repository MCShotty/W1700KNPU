#!/usr/bin/env python3
"""Audit per-callback release and actual TX register readback without editing replays."""
import argparse
import ctypes
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
import descriptor_native_controls as descriptor
import tx_native_controls as tx
import test_provider_session as parent
from unicorn import UC_HOOK_MEM_WRITE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--native-receipt', type=Path, required=True)
    parser.add_argument('--host-receipt', type=Path, required=True)
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--publication', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]{0,39}', args.name)
    root = parent.ROOT
    destination = root / '.local/npu-cold-descriptor-20261010' / args.name
    assert not destination.exists()
    destination.mkdir()
    inputs = {}
    for receipt in (args.native_receipt.resolve(), args.host_receipt.resolve()):
        evidence = json.loads(receipt.read_text())
        assert receipt.is_relative_to(root) and evidence['passed']
        for path,digest in evidence['inputs'].items():
            assert parent.loader.sha(root / path) == digest
            assert path not in inputs or inputs[path] == digest
            inputs[path] = digest
        inputs[str(receipt.relative_to(root))] = parent.loader.sha(receipt)
    rows = []
    def audit(module, component):
        original_check = module.check
        def checked(h, *arguments, **options):
            original_message = h.message
            flag = getattr(h, component).symbols['lock_owned']
            observed = []
            def message(words, **keywords):
                before, first = h.get32(flag), len(h.mmio)
                writes = []
                def record(cpu,access,address,size,value,data):
                    writes.append(value)
                hook = h.cpu.hook_add(UC_HOOK_MEM_WRITE,record,begin=flag,end=flag + 3)
                try:
                    reply = original_message(words,**keywords)
                finally:
                    h.cpu.hook_del(hook)
                releases = [entry for entry in h.mmio[first:] if entry['kind'] == 'mmio-write'
                            and entry['address'] == '0x1ec03248']
                acquired = before == 0 and 1 in writes
                assert len(releases) == int(acquired), (component,writes,releases)
                assert h.get32(flag) == (0 if acquired else before)
                assert writes == ([1,0] if acquired else []), (component,writes)
                observed.append(dict(acquired=acquired,unlock_writes=len(releases),
                                     flag_before=before,flag_after=h.get32(flag)))
                return reply
            h.message = message
            try:
                cases = original_check(h,*arguments,**options)
            finally:
                h.message = original_message
            assert len(cases) == len(observed)
            rows.extend(dict(component=component,name=case['name'],**observation)
                        for case,observation in zip(cases,observed))
            return cases
        module.check = checked
    audit(descriptor,'descriptor')
    audit(tx,'tx')
    native_directory = args.native_receipt.resolve().parent
    shared = native_directory / 'host/provider-session.so'
    host = root / json.loads(args.host_receipt.read_text())['shared']
    native = parent.native_peer(shared,args.pair.resolve(),args.publication.resolve(),
                                cold_commands=True,host_sender=host)
    assert native['passed'] and native['actual_c_txrx_sender'] and len(rows) == 56
    getter = next(entry for entry in native['cold'] if entry.get('header') == 0x35 and entry.get('api') == 4)
    lib = ctypes.CDLL(str(host))
    lib.npu_host_txdesc_value.argtypes = [ctypes.c_uint]
    lib.npu_host_txdesc_value.restype = ctypes.c_uint32
    assert lib.npu_host_txdesc_value(1) == getter['output']
    assert lib.npu_host_txdesc_value(0) == 0xabcdef01 and lib.npu_host_register_writes() == 1
    for path in (Path(__file__),Path(descriptor.__file__),Path(tx.__file__),Path(parent.__file__),shared,host):
        inputs[str(path.relative_to(root))] = parent.loader.sha(path)
    assert all(parent.loader.sha(root / path) == digest for path,digest in inputs.items())
    result = dict(passed=True,release_controls=rows,tx_register_values=[lib.npu_host_txdesc_value(i) for i in range(2)],
                  tx_native_getter_reply=getter['output'],native=native,inputs=inputs,
                  limits=['Observed actual native callbacks and actual host TX register storage with modeled backing/delivery.',
                          'Actual TX initializer still stops at API21. GET7 remains diagnostic; no physical ownership or retirement proof.'])
    (destination / 'result.json').write_text(json.dumps(result,indent=2) + '\n')
    print(json.dumps(dict(passed=True,release_controls=len(rows),tx_register_readback=True)))


if __name__ == '__main__':
    main()
