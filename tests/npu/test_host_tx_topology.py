#!/usr/bin/env python3
"""Execute pinned host TX paths; no firmware callbacks or hardware execution."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
import test_host_queue_publication as queues

ROOT = queues.ROOT
OUT = ROOT / 'research/checkpoints/2026-09-09-npu-tx-topology'
SCRATCH = ROOT / '.local/npu-tx-topology'
PATCH = OUT / '004-mt7996-npu-tx-topology.patch'
KERNEL = ROOT / ('.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/'
                 'linux-airoha_an7581/linux-6.18.44')
PROVIDER = KERNEL / 'drivers/net/ethernet/airoha/airoha_npu.c'
HEADER = KERNEL / 'include/linux/soc/airoha/airoha_offload.h'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replace(text, old, new):
    assert text.count(old) == 1, old[:120]
    return text.replace(old, new, 1)


def sources():
    result = queues.load_sources()
    zstd = ROOT / '.build/openwrt/staging_dir/host/bin/zstd'
    raw = subprocess.check_output([str(zstd), '-dc', str(queues.ARCHIVE)], timeout=30)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        result['mt7996/npu.c'] = archive.extractfile(
            'mt76-2026.09.01~be5ce791/mt7996/npu.c').read().decode()
    return result


def patched(before):
    destination = SCRATCH / 'patched-source'
    for name in ('mt7996/dma.c', 'mt7996/init.c'):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(before[name])
    result = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1',
                             '-i', str(PATCH)], cwd=destination,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'offset' not in result.stdout and 'fuzz' not in result.stdout
    return {**before, **{name: (destination / name).read_text()
                        for name in ('mt7996/dma.c', 'mt7996/init.c')}}


ATTACH = r'''
static int attach_serial, attach_fail;
static int mt76_npu_get_msg(struct airoha_npu *npu, int selector,
                           enum airoha_npu_wlan_get_cmd api, u32 *value, int gfp) {
    assert(npu && api == WLAN_FUNC_GET_WAIT_RXDESC_BASE);
    *value = 0x81000000U + (u32)selector * 0x10000U;
    event("attach_get", selector, *value);
    return ++attach_serial == attach_fail ? -EIO : 0;
}
static int mt76_npu_send_msg(struct airoha_npu *npu, int selector,
                            enum airoha_npu_wlan_set_cmd api, u32 value, int gfp) {
    assert(npu && api == WLAN_FUNC_SET_WAIT_TX_BUF_SPACE_HW_BASE);
    event("attach_set", selector, value);
    return ++attach_serial == attach_fail ? -EIO : 0;
}
'''


def unit(source, provider, header, chip=7996, compiled=1):
    text, refs, boundaries = queues.build_unit(source)
    text = replace(text, '#define CONFIG_MT76_NPU 1', f'#define CONFIG_MT76_NPU {compiled}')
    if not compiled:
        for name in ('regmap_read', 'regmap_write'):
            text = replace(text, 'static int ' + name + '(',
                           'static int __attribute__((unused)) ' + name + '(')
    text = replace(text, 'struct airoha_npu { void *regmap; };', '''struct airoha_npu {
    void *regmap;
    struct { u32 (*wlan_get_queue_addr)(struct airoha_npu *, int, bool); } ops;
};''')
    text = replace(text, 'void *hif2; u8 q_id[64]; u32 q_wfdma_mask;',
                   'void *hif2; u8 q_id[64]; u32 q_wfdma_mask, q_int_mask[64];\n'
                   'dma_addr_t npu_txd_addr[6];')
    old_provider = queues.function(text, 'airoha_npu_wlan_get_queue_addr')
    provider_parts = [queues.macro(provider, name) for name in
                      ('NPU_WLAN_BASE_ADDR', 'REG_TX_BASE', 'REG_RX_BASE')]
    for path, name, content in (
        (str(PROVIDER.relative_to(ROOT)), 'airoha_npu_wlan_queue_addr_get', provider),
        (str(HEADER.relative_to(ROOT)), 'airoha_npu_wlan_get_queue_addr', header),
    ):
        body = queues.function(content, name)
        provider_parts.append(body)
        refs.append(dict(path=path, name=name, kind='whole_function', sha256=sha(body.encode())))
    text = replace(text, old_provider, '\n'.join(provider_parts))
    projection = '#define TXQ_CONFIG(q,wfdma,irq,id) do { assert((wfdma) == 0); dev->q_id[__TXQ(q)] = (id); } while (0)'
    macros = [queues.macro(source['mt7996/regs.h'], name) for name in
              ('MT_INT_TX_DONE_BAND0', 'MT_INT_TX_DONE_BAND1', 'MT_INT_TX_DONE_BAND2')]
    macros += [queues.macro(source['mt7996/dma.c'], name) for name in ('Q_CONFIG', 'TXQ_CONFIG')]
    text = replace(text, projection, '\n'.join(macros))
    if chip == 7992:
        text = replace(text, 'return true; }\nstatic bool is_mt7992',
                       'return false; }\nstatic bool is_mt7992')
        text = replace(text, 'is_mt7992(struct mt76_dev *dev) { assert(dev == &fixture.mt76); return false;',
                       'is_mt7992(struct mt76_dev *dev) { assert(dev == &fixture.mt76); return true;')
    attachment = queues.function(source['mt7996/npu.c'], 'mt7996_npu_txd_init')
    refs.append(dict(path='mt7996/npu.c', name='mt7996_npu_txd_init',
                     kind='whole_function', sha256=sha(attachment.encode())))
    declarations = '\n'.join(queues.declaration(header, 'enum', name) for name in
                             ('airoha_npu_wlan_set_cmd', 'airoha_npu_wlan_get_cmd'))
    text = replace(text, queues.DRIVER, declarations + '\n#define BUILD_BUG_ON(x) _Static_assert(!(x), #x)\n'
                   '#define dev_warn(...) ((void)0)\n' + ATTACH + '\n' + attachment + '\n' + queues.DRIVER)
    text = replace(text, 'assert(argc == 7);', 'assert(argc == 8); attach_fail = atoi(argv[7]);')
    text = replace(text, 'fixture.mt76.mmio.regs = mmio; npu.regmap = regmap;',
                   'fixture.mt76.mmio.regs = mmio; npu.regmap = regmap;\n'
                   '    npu.ops.wlan_get_queue_addr = airoha_npu_wlan_queue_addr_get;\n'
                   '    for (int i = 0; i < 6; i++) fixture.npu_txd_addr[i] = 0x82000000 + i * 0x100000;')
    text = replace(text, 'fixture_tx_config(&fixture);', 'fixture_tx_config(&fixture);\n'
                   '    for (int i = 0; i < 3; i++) {\n'
                   '        event("queue_mapping", i, fixture.q_id[__TXQ(i)]);\n'
                   '        event("queue_irq", i, fixture.q_int_mask[__TXQ(i)]);\n'
                   '    }')
    text = replace(text, 'int owners[3] = {-1,-1,-1};', '''if (!ret && through == 2 && is_mt7996(&fixture.mt76) &&
        mt76_npu_device_active(&fixture.mt76)) {
        event("attachment_begin", 0, 0);
        ret = mt7996_npu_txd_init(&fixture, &npu);
    }
    int owners[3] = {-1,-1,-1};''')
    return text, refs, boundaries


def compile_unit(text, name):
    path, binary = SCRATCH / (name + '.c'), SCRATCH / name
    path.write_text(text)
    command = ['gcc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-Wno-sign-compare', '-Wno-unused-parameter', '-fsanitize=address,undefined',
               '-fno-sanitize-recover=all', '-o', str(binary), str(path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return binary, command


def execute(binary, hif, active, through=2, failure='none', fail_band=-1, seed=0, attach_fail=0):
    command = [str(binary), str(hif), str(active), str(through), failure,
               str(fail_band), str(seed), str(attach_fail)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10,
                            env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1:abort_on_error=1'})
    assert result.returncode == 0 and not result.stderr, result.stderr
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    return dict(hif=hif, active=active, through=through, failure=failure,
                fail_band=fail_band, seeded=seed, attach_fail=attach_fail,
                events=rows[:-1], summary=rows[-1])


def split_events(trace):
    events = trace['events']
    split = next((i for i, row in enumerate(events) if row['op'] == 'attachment_begin'), len(events))
    return events[:split], events[split+1:]


def verify(trace, corrected):
    hif, active, through = trace['hif'], trace['active'], trace['through']
    events, attachment = split_events(trace)
    result = trace['summary']
    assert result['result'] == 0 and result['fault_hits'] == 0
    separate = bool(hif or (corrected and active))
    owners = [0, int(separate), int(separate) if active else 2]
    assert result['owners'] == [owners[i] if i <= through else -1 for i in range(3)]
    hardware = ([21, 18, 19] if active and separate else
                [18, 19, 21] if hif else [18, 0, 19])
    assert [row['value'] for row in events if row['op'] == 'queue_mapping'] == hardware
    irq_by_qid = {0: 0, 18: 1 << 30, 19: 1 << 31, 21: 1 << 15}
    assert [row['value'] for row in events if row['op'] == 'queue_irq'] == [irq_by_qid[q] for q in hardware]
    physical = {b: 0xd4300 + hardware[b] * 16 +
                (0x4000 if hif and ((active and b == 0) or (not active and b == 2)) else 0)
                for b in range(3)}
    allocated = [b for b in range(through+1) if owners[b] == b]
    assert result['allocations'] == len(allocated)
    writes = []
    for index, b in enumerate(allocated):
        count = (1024 if b == 0 else 512) if active else 2048
        dma = 0x20000000 + index * 0x100000
        assert [(r['address'], r['value']) for r in events
                if r['op'] == 'descriptor_allocation' and r['band'] == b] == [(dma, count * (208 if active else 16))]
        assert [(r['address'], r['value']) for r in events
                if r['op'] == 'framework_queue_request' and r['band'] == b] == [(physical[b], count)]
        route, base = ('regmap_write', 0x30d0a0 + b*16) if active else ('mmio_write', physical[b])
        expected = [(route, base+8, 0), (route, base+12, 0), (route, base+4, count)]
        if active:
            expected += [('mmio_write', physical[b]+4, count), ('mmio_write', physical[b], dma)]
        expected.append((route, base, dma))
        writes += [(b, *row) for row in expected]
    assert [(r['band'], r['op'], r['address'], r['value']) for r in events
            if r['op'].endswith('_write')] == writes
    tx1 = [0x20100000, 512] if active and separate and through >= 1 else [0xdead0000, 77] if trace['seeded'] else [0, 0]
    assert result['tx1'] == tx1
    if active and through == 2:
        actual = [(r['address'], r['value']) for r in attachment if r['op'] == 'mmio_write']
        assert actual == [(physical[owners[1]], 0x81050000), (physical[0], 0x81070000)]
        requests = [(r['op'], r['address'], r['value']) for r in attachment if r['op'].startswith('attach_')]
        assert requests == [('attach_get', 5, 0x81050000), ('attach_set', 0, 0x82000000),
                            ('attach_set', 5, 0x82100000), ('attach_set', 10, 0x82200000),
                            ('attach_get', 7, 0x81070000), ('attach_set', 2, 0x82300000),
                            ('attach_set', 7, 0x82400000), ('attach_set', 12, 0x82500000)]
        if corrected:
            # These are the two physical destinations advertised by the host's
            # SET_TX_RING_PCIE_ADDR expressions, not a hardware routing oracle.
            assert [address for address, _ in actual] == [0xd4420, 0xd4450 + (0x4000 if hif else 0)]
            assert actual[0][0] != actual[1][0]
    else:
        assert not attachment


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    before = sources()
    after = patched(before)
    provider, header = PROVIDER.read_text(), HEADER.read_text()
    advertised = [
        'u32 hif1_ofs = dev->hif2 ? MT_WFDMA0_PCIE1(0) - MT_WFDMA0(0) : 0;',
        'dma_addr = phy_addr + MT_TXQ_RING_BASE(1) + 0x120;',
        'dma_addr = phy_addr + MT_TXQ_RING_BASE(0) + 0x150 + hif1_ofs;',
    ]
    offload = queues.function(before['mt7996/npu.c'], 'mt7996_npu_txrx_offload_init')
    assert all(statement in offload for statement in advertised)
    cases, controls, binaries = [], [], []
    for chip, compiled in ((7996, 1), (7996, 0), (7992, 1)):
        pair = []
        for phase, source in (('before', before), ('after', after)):
            text, refs, boundaries = unit(source, provider, header, chip, compiled)
            binary, command = compile_unit(text, f'{phase}-{chip}-{compiled}')
            binaries.append(dict(phase=phase, chip=chip, compiled=compiled,
                                 harness_sha256=sha(text.encode()), binary_sha256=sha(binary.read_bytes()),
                                 command=command, extracted=refs, modeled_bridge=boundaries))
            rows = []
            for hif in (0, 1):
                for pointer in ((0, 1) if compiled else (0,)):
                    for through in (0, 1, 2):
                        trace = execute(binary, hif, pointer, through)
                        if chip == 7996:
                            trace['active'] = pointer * compiled
                            verify(trace, phase == 'after')
                        rows.append(trace)
            pair.append(rows)
            cases.append(dict(phase=phase, chip=chip, compiled=compiled, traces=rows))
            if chip != 7996 or not compiled or phase != 'after':
                continue
            for hif in (0, 1):
                for active in (0, 1):
                    seeded = execute(binary, hif, active, seed=1)
                    verify(seeded, True)
                    controls.append(seeded)
                    allocating = [0, 1] if hif or active else [0, 2]
                    if not active and hif:
                        allocating.append(2)
                    for point in ('queue', 'descriptor', 'entry'):
                        for band in allocating:
                            trace = execute(binary, hif, active, failure=point, fail_band=band)
                            assert trace['summary']['result'] == -12 and trace['summary']['fault_hits'] == 1
                            assert not any(r['band'] >= band and r['op'].endswith('_write') for r in trace['events'])
                            controls.append(trace)
                    for point in ('phy', 'eeprom_cap', 'override', 'registration'):
                        trace = execute(binary, hif, active, failure=point, fail_band=1)
                        assert trace['summary']['result'] == (-12 if point == 'phy' else -5)
                        assert trace['summary']['fault_hits'] == 1
                        assert not any(r['op'] == 'attachment_begin' for r in trace['events'])
                        controls.append(trace)
                for fail_at in range(1, 9):
                    trace = execute(binary, hif, 1, attach_fail=fail_at)
                    _, attachment = split_events(trace)
                    assert trace['summary']['result'] == -5
                    assert len([r for r in attachment if r['op'].startswith('attach_')]) == fail_at
                    assert len([r for r in attachment if r['op'] == 'mmio_write']) == int(fail_at > 1) + int(fail_at > 5)
                    controls.append(trace)
        for old, new in zip(*pair, strict=True):
            if chip != 7996 or not compiled or old['hif'] or not old['active']:
                assert old == new, (chip, compiled, old)
    mutants = []
    for name, source in (
        ('mapping_only', {**after, 'mt7996/init.c': before['mt7996/init.c']}),
        ('ownership_only', {**after, 'mt7996/dma.c': before['mt7996/dma.c']}),
        ('duplicate_descriptor_target', {**after, 'mt7996/npu.c': replace(after['mt7996/npu.c'],
            'phy_id = is_mt7996(&dev->mt76) ? band == MT_BAND0 ? 1 : 0\n\t\t\t\t\t       : band;', 'phy_id = 0;')}),
        ('wrong_irq_mapping', {**after, 'mt7996/dma.c': replace(after['mt7996/dma.c'],
            'TXQ_CONFIG(1, WFDMA0, MT_INT_TX_DONE_BAND0,',
            'TXQ_CONFIG(1, WFDMA0, MT_INT_TX_DONE_BAND1,')}),
    ):
        text, _, _ = unit(source, provider, header)
        binary, _ = compile_unit(text, name)
        trace = execute(binary, 0, 1)
        try:
            verify(trace, True)
        except AssertionError:
            mutants.append(dict(name=name, killed=True))
        else:
            raise AssertionError('surviving mutant: ' + name)
    assert sources() == before and PROVIDER.read_text() == provider and HEADER.read_text() == header
    result = dict(schema=1, archive_sha256=queues.ARCHIVE_SHA, pin=queues.PIN,
                  patch_sha256=sha(PATCH.read_bytes()), test_sha256=sha(Path(__file__).read_bytes()),
                  provider_sha256=sha(provider.encode()), header_sha256=sha(header.encode()),
                  counts=dict(nominal_traces=sum(len(row['traces']) for row in cases), controls=len(controls), mutants=len(mutants)),
                  sources={name: dict(before=sha(before[name].encode()), after=sha(after[name].encode())) for name in before},
                  binaries=binaries, cases=cases, controls=controls, mutants=mutants,
                  advertised_tx_addresses=dict(function='mt7996_npu_txrx_offload_init',
                                               sha256=sha(offload.encode()), statements=advertised,
                                               execution='Source binding only; this function is not executed.'),
                  boundaries=['Extracted host C and actual provider queue-address dispatch; no native firmware callbacks.',
                              'TX configuration blocks execute with original Q_CONFIG/TXQ_CONFIG macros; full DMA initialization does not.',
                              'Connac bridge, framework failures, MMIO, coherent allocation, WED-inactive and RCU remain models.',
                              'TXD GET/SET replies are synthetic transport inputs, not native callback or readiness proof.',
                              'Publication survives later registration/attachment failure; containment and lifetime are unresolved.',
                              'No router, firmware image, configuration, shared source, INODE or DESC5/6/7/8 operation.'])
    receipt = OUT / 'host-tx-topology.json'
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(counts=result['counts'], evidence_sha256=sha(receipt.read_bytes()))))


if __name__ == '__main__':
    main()
