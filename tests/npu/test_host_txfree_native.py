#!/usr/bin/env python3
"""Bridge actual host allocation/messages to selected native TXFREE consumers."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
from unicorn import riscv_const as r
import test_host_txfree as host
import test_txdone_init as native
from test_mt7996_bootstrap_sequence import exports

ROOT, OUT = host.ROOT, host.OUT


class HostBackedTx(native.ColdTx):
    def setup(self):
        native.advance(self)
        assert self.packet([0x10, 14, 2]) == 1
        for selector, count in ((0, 1536), (2, 1024)):
            assert self.packet([0x10|selector, 1, count]) == 1
        for message in native.expected(0, 2):
            if message['kind'] == 'message' and message['api'] == 19:
                assert self.packet([message['word0'], 19, message['value']]) == 1
        assert self.packet([0x10, 33, 8192]) == 1
        # SET22 is intentionally absent: only the tested host trace publishes it.
        assert self.get32(native.SRAM+0x3964) == 0
        assert self.get32(native.SRAM+0x1b88) == native.HEAP+32
        for owner in range(1, 8):
            self.worker(owner)
        self.hart = 0
        self.cpu.context_restore(self.contexts[0])
        self.fixed = {row['type']: row['value'] for row in native.table(self.code, 0x8401cf70)}
        self.saved_banks = deepcopy(self.plic_banks)
        self.saved_memory = [(lo, bytes(self.cpu.mem_read(lo, hi-lo+1)))
                             for lo, hi, _ in self.cpu.mem_regions()]
        self.saved_context = self.cpu.context_save()


def bindings():
    values = {**native.input_bindings(), **host.input_bindings()}
    paths = [native.SOURCE, native.ASM, native.LINKER, Path(__file__), OUT/'host-txfree.json']
    paths += sorted((ROOT/'tests/npu').glob('*-emulation.ld'))
    values.update({str(p.relative_to(ROOT)): host.sha(p.read_bytes()) for p in paths})
    return values


def pointer_call(h, message):
    api, selector, value = (message[key] for key in ('api', 'selector', 'value'))
    assert (api, selector) in ((22, 0), (0, 10))
    before = native.images(h)
    wanted = deepcopy(before)
    offset = 0x3964 if api == 22 else 0x2a90
    stored = value & 0x3fffffff | 0x40000000 if api == 22 else value
    struct.pack_into('<I', wanted[native.SRAM], offset, stored)
    h.txdone_writes.clear()
    h.txdone_tracking = True
    try:
        result = h.packet([0x10|selector, api, value])
    finally:
        h.txdone_tracking = False
    assert result == 1 and native.images(h) == wanted, 'native pointer setter memory oracle'
    assert h.txdone_writes == set(range(native.SRAM+offset, native.SRAM+offset+4))
    return dict(api=api, selector=selector, value=hex(value), stored=hex(stored),
                whole_memory_compared=sum(size for _, size in native.SPACES), exact_write_bytes=4)


def run_case(h, path, trace, name, *, corrected=True, deliver_timeout=False, short=False):
    h.restore(path, corrected)
    h.put32(native.ADM+4, 1)
    h.put32(native.SRAM+0x3974, 0x87654321)
    assert h.get32(native.SRAM+0x3964) == 0
    capacity = trace['summary']['descriptor_bytes']
    assert capacity <= native.HOST_BYTES
    h.host_limit = capacity
    before = native.images(h)
    calls, stopped, done_result = [], None, None
    messages = [event for event in trace['events'] if event['op'] == 'send']
    for index, message in enumerate(messages, 1):
        if index == trace['send_fail'] and not deliver_timeout:
            break
        if message['api'] in (22, 0):
            if message['api'] == 22:
                assert message['value'] & 0x3fffffff | 0x40000000 == native.HOST
            calls.append(pointer_call(h, message))
            continue
        assert message['api'] == 1 and message['selector'] == 10
        h.txdone_writes.clear()
        h.txdone_write_ordinal = 0
        h.txdone_ready_writes = []
        want, writes, footprint = native.done_oracle(SimpleNamespace(h=h, fixed=h.fixed), message['value'])
        try:
            done_result = h.invoke(message['value'])
        except native.UnmodeledAccess as error:
            assert short, str(error)
            assert h.unmodeled and h.cpu.reg_read(r.UC_RISCV_REG_PC) == 0x8400b4b6
            assert hex(native.HOST+capacity+4) in str(error), str(error)
            assert h.cpu.mem_read(native.SRAM+0x46fa, 1) == b'\x00'
            stopped = dict(reason=str(error), pc=hex(h.cpu.reg_read(r.UC_RISCV_REG_PC)),
                           attempted_address=hex(native.HOST+capacity+4), backing_bytes=capacity,
                           firmware_detected_short_backing=False)
            break
        assert not short, 'short host backing unexpectedly accepted by memory observer'
        assert done_result['result'] == 1 and done_result['ready'] == 1
        assert native.images(h) == want, 'native TXDONE whole-memory oracle'
        assert h.txdone_writes == writes, 'native TXDONE exact write extent'
        count = message['value']
        operations = [(int(e['address'], 16), e['value']) for e in done_result['mmio']
                      if e['kind'] == 'mmio-write' and 0x1ec03180 <= int(e['address'], 16) < 0x1ec03300]
        assert operations == native.lock_oracle(count, count, 'full', corrected, None)
        assert done_result['owner_reads'] == {28: count, 19: 1, 20: 1}
        assert done_result['temporary_reads'] == (2048 if corrected else 8192)
        assert done_result['ready_writes'][0]['ordinal'] == done_result['memory_write_events']
        calls.append(dict(api=1, selector=10, value=count, callback_result=1,
                          descriptor_write_bytes=count*16, descriptor_allocated_bytes=capacity,
                          whole_memory_compared=sum(size for _, size in native.SPACES),
                          exact_write_bytes=len(writes), exact_lock_order=True,
                          temporary_reads=done_result['temporary_reads'], footprint=footprint))
    assert bool(stopped) == short
    if not calls:
        assert native.images(h) == before and not h.txdone_writes
    assert h.get32(native.ADM+4) == 1, 'fixture active ownership must remain retained'
    assert h.get32(native.STATE+4) == h.get32(native.STATE+8) == h.get32(native.STATE+12) == 0
    assert h.get32(native.ADM) == 1
    image = native.images(h)
    return dict(name=name, native_corrected=corrected, host_result=trace['summary']['result'],
                host_summary=trace['summary'], host_messages=messages, delivered_calls=calls,
                timeout_delivery=deliver_timeout, backing_bytes=capacity,
                firmware_ring_pointer=hex(h.get32(native.SRAM+0x3964)),
                pcie_pointer=hex(h.get32(native.SRAM+0x2a90)),
                ready=h.cpu.mem_read(native.SRAM+0x46fa, 1)[0], active_retained=h.get32(native.ADM+4),
                stopped=stopped, unchanged=image == before,
                image_sha256={hex(base): host.sha(data) for base, data in image.items()},
                substitutions=dict(h.stub_counts),
                diagnostics=[dict(format=entry['format']) for entry in h.logs])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    inputs = bindings()
    receipt = json.loads((OUT/'host-txfree.json').read_text())
    assert receipt['inputs_before_after'] == host.input_bindings()
    sources = host.host.sources()
    binaries, builds = {}, {}
    for phase, source in (('before', sources), ('after', host.patched(sources))):
        text, _, _ = host.unit(source)
        binary, command = host.compile_unit(text, 'native-host-'+phase)
        binaries[phase] = binary
        builds[phase] = dict(command=command, harness_sha256=host.sha(text.encode()),
                             binary_sha256=host.sha(binary.read_bytes()))
        assert builds[phase]['harness_sha256'] == receipt['builds'][phase]['harness_sha256']
    path, command = native.build()
    startup, _ = native.build_startup()
    reset, _ = native.build_reset()
    h = HostBackedTx(startup, reset)
    h.setup()
    cases = []
    def trace(phase='after', chip=7996, **kwargs):
        actual = host.execute(binaries[phase], chip=chip, **kwargs)
        row = host.verify(actual, phase == 'after')
        assert any(all(prior.get(k) == v for k, v in actual.items())
                   for prior in receipt['cases'] if prior['phase'] == phase)
        return row
    for chip in (7996, 7992):
        for phase in ('before', 'after'):
            cases.append(run_case(h, path, trace(phase, chip), f'{chip}-{phase}-normal'))
        cases.append(run_case(h, path, trace(chip=chip, count=511), f'{chip}-short-rejected'))
    for address in (0x57000000, 0x97000000):
        cases.append(run_case(h, path, trace(address=address), f'alias-{address:x}'))
    cases.append(run_case(h, path, trace('before'), 'original-native-normal', corrected=False))
    for corrected in (False, True):
        cases.append(run_case(h, path, trace('before', count=511),
                              f'original-host-short-native-{int(corrected)}', corrected=corrected, short=True))
    cases.append(run_case(h, path, trace(count=511, edit='forged-count'), 'forged-count-short-backing', short=True))
    for phase in ('before', 'after'):
        cases.append(run_case(h, path, trace(phase, address=0xd7000000), f'native-range-{phase}'))
    for index in (1, 2, 3):
        for delivered in (False, True):
            cases.append(run_case(h, path, trace(send_fail=index),
                                  f'timeout-{index}-delivered-{int(delivered)}', deliver_timeout=delivered))
    for arguments, name in ((dict(failure='descriptor'), 'allocation-failure'),
                            (dict(active=0), 'absent-provider')):
        cases.append(run_case(h, path, trace(**arguments), name))
    for case in cases:
        print(json.dumps(dict(case=case['name'], passed=True, ready=case['ready'])), flush=True)
    normals = [case for case in cases if case['name'] in
               ('7996-before-normal', '7996-after-normal', 'alias-57000000', 'alias-97000000', 'original-native-normal')]
    assert all(case['image_sha256'] == normals[0]['image_sha256'] for case in normals)
    bounds = next(case for case in cases if case['name'] == 'native-range-before')
    assert any('out of available range' in row['format'] for row in bounds['diagnostics'])
    assert not next(case for case in cases if case['name'] == 'native-range-after')['delivered_calls']
    for name in ('timeout-2-delivered-1', 'timeout-3-delivered-0', 'timeout-3-delivered-1'):
        case = next(case for case in cases if case['name'] == name)
        assert case['host_result'] == -110 and case['ready'] == 1 and case['active_retained'] == 1
    h.restore(path)
    before = native.images(h)
    rejected = h.message([0x1a, 1, 512])
    assert rejected['flags'] == 3 and not rejected['callbacks'] and native.images(h) == before
    exported = exports()
    spans = {hex(pc): dict(line=exported[pc]['line'],
                           sha256=host.sha((exported[pc]['text']+exported[pc]['assembly']).encode()))
             for pc in (0x8400b5c6, 0x8400b94e, 0x8400fbb4)}
    assert bindings() == inputs
    result = dict(schema=1, inputs_before_after=inputs, host_builds=builds,
                  native_command=command, native_elf_sha256=host.sha(path.read_bytes()),
                  native_pointer_source_spans=spans, cases=cases,
                  strict_admission_control=rejected, initial_ring_pointer=0,
                  limits=['Actual host allocation C and three selected native callbacks are connected by recorded messages.',
                          'Supporting RX0/2/TX/control setup and cold containment use the existing isolated fixture.',
                          'This is not a complete host attach, mailbox transport, concurrent boot or hardware test.',
                          'Logical allocation extent comes from modeled dmam_alloc_coherent; physical page/DMA mapping is not established.',
                          'Host preflight trusts queue metadata; a forged count still reaches the emulator-only short-backing stop.',
                          'Timeout delivery alternatives are explicit models; published memory and active ownership remain retained.',
                          'Strict API1 admission stays closed; no INODE-provider or native DESC5/6/7/8 operation, router or image.'])
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    output = OUT/'native-txfree.json'
    if args.check:
        assert output.read_bytes() == encoded
    else:
        output.write_bytes(encoded)
    print(json.dumps(dict(cases=len(cases), strict_controls=1, evidence_sha256=host.sha(encoded))))


if __name__ == '__main__':
    main()
