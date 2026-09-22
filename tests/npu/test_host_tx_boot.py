#!/usr/bin/env python3
"""Replay host-C TX publication into native core-0 bootstrap, offline only."""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from unicorn import riscv_const as r

import test_host_tx_topology as host
import test_native_wifi_boot as native
from preflight_dtb_cases import properties, strings, resource, NPU_COMPATIBLE

ROOT = host.ROOT
OUT = host.OUT
ELF = ROOT / '.local/npu-barrier/admission-platform-bootstrap-bootstrap-startup-gdma-gdma-65536.elf'
ELF_SHA = 'bdb64d12d738bdef85a747d0b638e6b148c1c534410fd893348fbaf5908e2931'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mapping():
    tree = properties(native.DTB)
    nodes = [node for node, props in tree.items() if 'compatible' in props
             and NPU_COMPATIBLE in strings(tree, node, 'compatible')]
    assert len(nodes) == 1
    result = resource(tree, nodes[0])
    assert result['start'] == 0x1e900000
    provider = host.PROVIDER.read_text()
    probe = host.queues.function(provider, 'airoha_npu_probe')
    assert 'base = devm_platform_ioremap_resource(pdev, 0);' in probe
    assert 'npu->regmap = devm_regmap_init_mmio(dev, base, &regmap_config);' in probe
    assert 'npu->ops.wlan_get_queue_addr = airoha_npu_wlan_queue_addr_get;' in probe
    return dict(node=nodes[0], resource=result, dtb_sha256=sha(native.DTB),
                probe_sha256=hashlib.sha256(probe.encode()).hexdigest(),
                basis='Compiled DTB reg/ranges and provider source binding; no physical MMIO execution.')


def run(trace, region, drop=None, zero_size=False):
    h = native.to_wifi(ELF)
    memory = native.footprints(h)
    assert h.get32(native.SRAM+0x4708) == h.get32(native.STATE+20) == 0
    publication, _ = host.split_events(trace)
    writes = []
    for event in publication:
        if event['op'] != 'regmap_write':
            continue
        address = region['start'] + event['address']
        assert 0x1ec0d0a0 <= address <= 0x1ec0d0bc
        if address == drop:
            continue
        value = 0 if zero_size and address == 0x1ec0d0b4 else event['value']
        h.put32(address, value)
        writes.append(dict(address=hex(address), value=value))
    values = {address: h.get32(address) for address in native.HOST_REGISTERS}
    if values[0x1ec0d0b0] == 0:
        for _ in range(8):
            assert h.run(0x8400f836, [0x8400f836]) == 0x8400f836
        assert h.get32(native.SRAM+0x4708) == h.get32(native.STATE+20) == 0
        return dict(native_return=False, stop_pc='0x8400f836', polls=8,
                    writes=writes, footprints=memory, zero_tx1=True)
    h.put32(0x1ec0d180, native.HOST_FIXTURE[0x1ec0d180])
    assert h.run(0x8400f836, [0x8400f880]) == 0x8400f880
    for _ in range(8):
        assert h.run(0x8400f880, [0x8400f880]) == 0x8400f880
    assert h.get32(native.SRAM+0x4708) == h.get32(native.STATE+20) == 0
    h.put32(0x1ec0d190, native.HOST_FIXTURE[0x1ec0d190])
    values[0x1ec0d180] = native.HOST_FIXTURE[0x1ec0d180]
    values[0x1ec0d190] = native.HOST_FIXTURE[0x1ec0d190]
    assert h.run(0x8400f880, [0x84000188]) == 0x84000188
    assert h.get32(native.SRAM+0x4708) == 1
    for offset, dest, alias in ((0xa0, 0x4718, True), (0xb0, 0x4714, True),
                                (0xa4, 0x4728, False), (0xb4, 0x4724, False),
                                (0x180, 0x4710, True), (0x190, 0x470c, True)):
        value = values[0x1ec0d000+offset]
        expected = (value & 0x3fffffff) | 0x40000000 if alias else value
        assert h.get32(native.SRAM+dest) == expected
    assert h.returns == [{'pc': '0x8400e37a', 'a0': 0}, {'pc': '0x8400e37e', 'a0': 0}]
    window = h.rv.symbols['npu_emulation_idle_irq_window']
    assert h.run(0x84000188, [window]) == window
    assert h.get32(native.STATE+20) == 1
    assert [h.get32(native.STATE+20+i*4) for i in range(1, 8)] == [0]*7
    assert [h.get32(native.STATE+52+i*4) for i in range(13)] == [0]*13
    assert h.get32(native.STATE+8) == 0 and h.get32(native.ADM) == 1
    assert hashlib.sha256(h.cpu.mem_read(native.L2, native.L2_BYTES)).hexdigest() == memory['l2_sha256']
    assert set(h.stub_counts) <= {'0x840048f4', '0x84004212', '0x84004130', '0x8400452a', 'mhartid-csr'}
    return dict(native_return=True, core0_idle_ack=1, other_workers_parked=0,
                physical_domains_drained=0, release=0, arm=0,
                writes=writes, footprints=memory,
                host_fields={hex(address): value for address, value in values.items()},
                synthetic_rx=[hex(0x1ec0d180), hex(0x1ec0d190)],
                zero_tx1_size=zero_size, stub_counts=h.stub_counts,
                pc=hex(h.cpu.reg_read(r.UC_RISCV_REG_PC)))


def main():
    assert sha(ELF) == ELF_SHA
    receipt = OUT / 'host-tx-topology.json'
    recorded = json.loads(receipt.read_text())
    assert recorded['test_sha256'] == sha(Path(host.__file__))
    assert recorded['patch_sha256'] == sha(host.PATCH)
    assert recorded['provider_sha256'] == sha(host.PROVIDER)
    current = host.sources()
    assert all(recorded['sources'][name]['before'] == hashlib.sha256(text.encode()).hexdigest()
               for name, text in current.items())
    address_map = mapping()
    cases, corrected_single = [], None
    for phase in ('before', 'after'):
        group = next(row for row in recorded['cases'] if row['phase'] == phase
                     and row['chip'] == 7996 and row['compiled'] == 1)
        for hif in (0, 1):
            trace = next(row for row in group['traces'] if row['hif'] == hif
                         and row['active'] == 1 and row['through'] == 2)
            result = run(trace, address_map['resource'])
            assert result['native_return'] == (phase == 'after' or bool(hif))
            cases.append(dict(phase=phase, hif=hif, result=result))
            if phase == 'after' and not hif:
                corrected_single = trace
            print(json.dumps(dict(phase=phase, hif=hif, native_return=result['native_return'])), flush=True)
    missing = run(corrected_single, address_map['resource'], drop=0x1ec0d0b0)
    assert not missing['native_return']
    malformed = run(corrected_single, address_map['resource'], zero_size=True)
    assert malformed['native_return'] and malformed['host_fields']['0x1ec0d0b4'] == 0
    result = dict(schema=1, firmware_sha256=native.CODE_SHA, data_sha256=native.DATA_SHA,
                  elf_sha256=sha(ELF), host_receipt_sha256=sha(receipt), test_sha256=sha(Path(__file__)),
                  native_test_sha256=sha(Path(native.__file__)), ghidra_sha256=sha(native.GHIDRA),
                  source_spans=native.source_spans(), mapping=address_map, cases=cases,
                  controls=dict(missing_tx1=missing, zero_tx1_size=malformed),
                  limits=['Only host TX register writes are bridged; RX pointers remain independent synthetic fixtures.',
                          'Physical MMIO, IRQs, caches, ownership barriers and all-hart initialization are not proved.',
                          'Native core-0 accepts zero TX1 size; completion is not a valid-ring/readiness certificate.',
                          'No native attachment callback, INODE or DESC5/6/7/8 path executes.',
                          'Candidate firmware ELF and stock bytes unchanged; no image or router operation.'])
    output = OUT / 'host-tx-native-boot.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(cases=len(cases), controls=2, evidence_sha256=sha(output))))


if __name__ == '__main__':
    main()
