#!/usr/bin/env python3
"""Actual host TXFREE allocation and early attachment preflight, offline only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
import test_host_tx_topology as host

q = host.queues
ROOT = host.ROOT
OUT = ROOT/'research/checkpoints/2026-09-09-npu-txfree-host'
BUILD = ROOT/'.local/npu-txfree-host'
PATCH = OUT/'005-mt7996-npu-txfree-preflight.patch'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def input_bindings():
    paths = [Path(__file__), Path(host.__file__), Path(q.__file__), PATCH, host.PATCH,
             q.ARCHIVE, host.PROVIDER, host.HEADER,
             ROOT/'research/checkpoints/2026-09-05-npu-admission/ghidra-mailbox/en7581_MT7996_npu_rv32.bin.txt',
             ROOT/'firmware/source-lock.json', ROOT/'firmware/patches/openwrt.patch',
             ROOT/'firmware/patches/luci.patch', ROOT/'firmware/build.config']
    paths += sorted((ROOT/'firmware/overlay/openwrt/package/kernel/mt76/patches').glob('*.patch'))
    return {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in paths}


def patched(sources):
    destination = BUILD/'source'
    path = destination/'mt7996/npu.c'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sources['mt7996/npu.c'])
    result = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(PATCH)],
                            cwd=destination, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    assert 'offset' not in result.stdout and 'fuzz' not in result.stdout, result.stdout
    return {**sources, 'mt7996/npu.c': path.read_text()}


BOUNDARIES = r'''
static int send_count, send_fail, setup_count;
static int mt76_npu_send_msg(struct airoha_npu *npu, int selector,
                           enum airoha_npu_wlan_set_cmd api, u32 value, int gfp) {
    assert(npu == fixture.mt76.mmio.npu && gfp == GFP_KERNEL);
    assert((selector == 0 && api == WLAN_FUNC_SET_WAIT_RX_RING_FOR_TXDONE_HW_BASE) ||
           (selector == 10 && (api == WLAN_FUNC_SET_WAIT_DESC || api == WLAN_FUNC_SET_WAIT_PCIE_ADDR)));
    printf("{\"op\":\"send\",\"selector\":%d,\"api\":%d,\"value\":%u}\n", selector, api, value);
    return ++send_count == send_fail ? -ETIMEDOUT : 0;
}
#define SETUP_MODEL(name) \
static int name(struct mt7996_dev *dev, struct airoha_npu *npu) { \
    assert(dev == &fixture && npu == dev->mt76.mmio.npu); \
    setup_count++; event(#name "_model", 0, 0); return 0; \
}
SETUP_MODEL(mt7996_npu_offload_init)
SETUP_MODEL(mt7996_npu_rxd_init)
SETUP_MODEL(mt7992_npu_rxd_init)
SETUP_MODEL(mt7996_npu_txd_init)
SETUP_MODEL(mt7996_npu_set_pcie_addr)
SETUP_MODEL(mt7996_npu_tx_done_init)
static void airoha_npu_wlan_enable_irq(struct airoha_npu *npu, int index) {
    assert(npu == fixture.mt76.mmio.npu && index >= 0 && index < 2);
    event("irq_enable_model", index, 0);
}
static unsigned long long allocation_hash(void) {
    unsigned long long value = 1469598103934665603ULL;
    for (unsigned i = 0; i < allocation_count; i++) {
        const unsigned char *bytes = allocations[i];
        for (size_t j = 0; j < allocation_sizes[i]; j++)
            value = (value ^ bytes[j]) * 1099511628211ULL;
    }
    return value;
}
'''

DRIVER = r'''
int main(int argc, char **argv) {
    assert(argc == 8);
    chip = atoi(argv[1]); int count = atoi(argv[2]);
    next_dma = strtoull(argv[3], NULL, 0);
    const char *edit = argv[4]; failure = argv[5];
    send_fail = atoi(argv[6]); int active = atoi(argv[7]);
    fail_band = band = 0;
    static struct airoha_npu npu;
    fixture.mt76.mmio.regs = mmio;
    fixture.mt76.mmio.phy_addr = 0x20000000;
    npu.regmap = regmap;
    npu.ops.wlan_get_queue_addr = airoha_npu_wlan_queue_addr_get;
    fixture.mt76.mmio.npu = active ? &npu : NULL;
    fixture.mt76.mutex = 1;
    fixture.q_id[__RXQ(MT_RXQ_TXFREE_BAND0)] = 9;
    fixture.q_id[__RXQ(MT_RXQ_MAIN_WA)] = 2;
    int qid = is_mt7996(&fixture.mt76) ? MT_RXQ_TXFREE_BAND0 : MT_RXQ_MAIN_WA;
    struct mt76_queue *queue = &fixture.mt76.q_rx[qid];
    queue->flags = MT_NPU_Q_TXFREE(0);
    int alloc_result;
    if (count == MT7996_RX_MCU_RING_SIZE)
        alloc_result = fixture_allocate_event(&fixture);
    else
        alloc_result = mt76_dma_alloc_queue(&fixture.mt76, queue, chip == 7996 ? 9 : 2,
                                           count, MT7996_RX_BUF_SIZE, MT_WFDMA0(0x500));
    event("allocation_finished", qid, alloc_result);
    if (!strcmp(edit, "missing-desc")) queue->desc = NULL;
    else if (!strcmp(edit, "missing-entry")) queue->entry = NULL;
    else if (!strcmp(edit, "plain-queue")) queue->flags = 0;
    else if (!strcmp(edit, "wrong-ring")) queue->flags = MT_NPU_Q_TXFREE(1);
    else if (!strcmp(edit, "npu-tx")) queue->flags = MT_NPU_Q_TX(0);
    else if (!strcmp(edit, "wed-owner")) queue->flags |= MT_QFLAG_WED;
    else if (!strcmp(edit, "emi-owner")) queue->flags |= MT_QFLAG_EMI_EN;
    else if (!strcmp(edit, "forged-count")) queue->ndesc = MT7996_RX_MCU_RING_SIZE;
    else assert(!strcmp(edit, "none"));
    unsigned long long before = allocation_hash();
    unsigned before_count = allocation_count;
    int result = alloc_result ? alloc_result : __mt7996_npu_hw_init(&fixture);
    assert(allocation_count == before_count && allocation_hash() == before);
    printf("{\"result\":%d,\"allocation_result\":%d,\"queue\":%d,\"ndesc\":%d,"
           "\"flags\":%u,\"descriptor_present\":%d,\"entry_present\":%d,"
           "\"desc_dma\":%llu,\"descriptor_bytes\":%zu,\"descriptor_stride\":%zu,"
           "\"send_count\":%d,\"setup_models\":%d,\"fault_hits\":%d,"
           "\"allocation_hash\":\"%016llx\",\"allocations_retained\":%u}\n",
           result, alloc_result, qid, queue->ndesc, queue->flags, !!queue->desc, !!queue->entry,
           (unsigned long long)queue->desc_dma, allocation_count ? allocation_sizes[0] : 0,
           sizeof(*queue->desc), send_count, setup_count, hits, before, allocation_count);
    /* Process-local fixture teardown, not a device or NPU reclaim operation. */
    for (unsigned i = 0; i < allocation_count; i++) free(allocations[i]);
    return 0;
}
'''


def unit(source):
    text, refs, previous_boundaries = q.build_unit(source)
    text = host.replace(text, 'static int band, fail_band, hits, alloc_count;',
                        'static int band, fail_band, hits, alloc_count, chip;')
    text = host.replace(text, 'static void *allocations[64];',
                        'static void *allocations[64];\nstatic size_t allocation_sizes[64];')
    text = host.replace(text, 'allocations[allocation_count++] = p; return p;',
                        'allocation_sizes[allocation_count] = size; allocations[allocation_count++] = p; return p;')
    text = host.replace(text, 'is_mt7996(struct mt76_dev *dev) { assert(dev == &fixture.mt76); return true;',
                        'is_mt7996(struct mt76_dev *dev) { assert(dev == &fixture.mt76); return chip == 7996;')
    text = host.replace(text, 'is_mt7992(struct mt76_dev *dev) { assert(dev == &fixture.mt76); return false;',
                        'is_mt7992(struct mt76_dev *dev) { assert(dev == &fixture.mt76); return chip == 7992;')
    text = host.replace(text, '(void)dev; assert(q->buf_size == 0);', '(void)dev; (void)q;')
    text = host.replace(text, 'struct airoha_npu { void *regmap; };', '''struct airoha_npu {
    void *regmap;
    struct { u32 (*wlan_get_queue_addr)(struct airoha_npu *, int, bool); } ops;
};''')
    text = host.replace(text, 'struct airoha_npu *npu; } mmio;',
                        'struct airoha_npu *npu; dma_addr_t phy_addr; } mmio;\n'
                        '    struct mt76_queue q_rx[__MT_RXQ_MAX];')
    provider, header = host.PROVIDER.read_text(), host.HEADER.read_text()
    provider_parts = [q.macro(provider, name) for name in ('NPU_WLAN_BASE_ADDR', 'REG_TX_BASE', 'REG_RX_BASE')]
    for path, name, content in (
        (str(host.PROVIDER.relative_to(ROOT)), 'airoha_npu_wlan_queue_addr_get', provider),
        (str(host.HEADER.relative_to(ROOT)), 'airoha_npu_wlan_get_queue_addr', header),
    ):
        body = q.function(content, name)
        provider_parts.append(body)
        refs.append(dict(path=path, name=name, kind='whole_function', sha256=sha(body.encode())))
    text = host.replace(text, q.function(text, 'airoha_npu_wlan_get_queue_addr'), '\n'.join(provider_parts))
    additions = ['typedef uint64_t phys_addr_t;',
                 '/* Synthetic packet-buffer accounting; descriptor size is independent. */',
                 'struct skb_shared_info { unsigned char modeled[320]; };',
                 '#define SKB_DATA_ALIGN(n) (((n)+63U) & ~63U)',
                 '#define BUILD_BUG_ON(x) _Static_assert(!(x), #x)',
                 '#define IS_ALIGNED(x, a) (!((x) & ((a)-1)))',
                 '#define upper_32_bits(x) ((u32)((u64)(x) >> 32))',
                 '#define dev_warn(...) ((void)0)',
                 '#define mt76_queue_alloc(dev, ...) mt76_dma_alloc_queue(&(dev)->mt76, __VA_ARGS__)']
    for path, names in (
        ('mt76.h', ('MT_NPU_Q_TXFREE', 'MT_RX_BUF_SIZE')),
        ('mt7996/mt7996.h', ('MT7996_RX_MCU_RING_SIZE', 'MT7996_RX_BUF_SIZE')),
        ('mt7996/regs.h', ('MT_RXQ_ID', 'MT_RXQ_RING_BASE')),
    ):
        for name in names:
            body = q.macro(source[path], name)
            additions.append(body)
            refs.append(dict(path=path, name=name, kind='macro', sha256=sha(body.encode())))
    additions.append(q.declaration(header, 'enum', 'airoha_npu_wlan_set_cmd'))
    additions.append(BOUNDARIES)
    dma = source['mt7996/dma.c']
    blocks = []
    for marker, end in (
        ('\t\t\tret = mt76_queue_alloc(dev,\n\t\t\t\t\t       &dev->mt76.q_rx[MT_RXQ_TXFREE_BAND0],', '\n\t\t}'),
        ('\t\tret = mt76_queue_alloc(dev, &dev->mt76.q_rx[MT_RXQ_MAIN_WA],', '\n\t} else {'),
    ):
        assert dma.count(marker) == 1
        body = dma[dma.index(marker):].split(end, 1)[0]
        assert body.endswith('return ret;')
        blocks.append(body)
        refs.append(dict(path='mt7996/dma.c', name=marker.split('MT_RXQ_')[-1].split(']')[0],
                         kind='unchanged_allocation_block', sha256=sha(body.encode())))
    additions += ['static int fixture_allocate_event(struct mt7996_dev *dev) {\nint ret;\n'
                  'if (is_mt7996(&dev->mt76)) {\n'+blocks[0]+'\n} else {\n'+blocks[1]+'\n}\nreturn 0;\n}']
    names = ['mt7996_npu_rx_event_init', '__mt7996_npu_hw_init']
    if 'static int mt7996_npu_rx_event_validate(' in source['mt7996/npu.c']:
        names.insert(0, 'mt7996_npu_rx_event_validate')
    for name in names:
        body = q.function(source['mt7996/npu.c'], name)
        additions.append(body)
        refs.append(dict(path='mt7996/npu.c', name=name, kind='whole_function', sha256=sha(body.encode())))
    return host.replace(text, q.DRIVER, '\n'.join(additions)+'\n'+DRIVER), refs, previous_boundaries


def compile_unit(text, name):
    path, binary = BUILD/(name+'.c'), BUILD/name
    path.write_text(text)
    command = ['gcc', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-Wno-sign-compare', '-Wno-unused-parameter', '-Wno-unused-function',
               '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-o', str(binary), str(path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return binary, command


def execute(binary, *, chip=7996, count=512, address=0x17000000, edit='none', failure='none', send_fail=0, active=1):
    args = [str(binary), str(chip), str(count), hex(address), edit, failure, str(send_fail), str(active)]
    run = subprocess.run(args, capture_output=True, text=True, timeout=10,
                         env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1:abort_on_error=1'})
    assert run.returncode == 0 and not run.stderr, run.stdout+run.stderr
    rows = [json.loads(line) for line in run.stdout.splitlines()]
    return dict(chip=chip, count=count, address=address, edit=edit, failure=failure,
                send_fail=send_fail, active=active, events=rows[:-1], summary=rows[-1])


def verify(row, corrected):
    summary = row['summary']
    address = row['address']
    invalid_state = summary['ndesc'] != 512 or row['edit'] not in ('none', 'forged-count')
    invalid_address = (address % 16 or address >> 32 or (address & 0xffffffff) >= 0xc0000000 or
                       (address & 0x3fffffff) > 0x40000000-8192)
    expected = summary['allocation_result']
    if not expected and row['active']:
        expected = -22 if corrected and invalid_state else -34 if corrected and invalid_address else -110 if row['send_fail'] else 0
    assert summary['result'] == expected, 'early queue preflight status'
    rejected = corrected and row['active'] and (invalid_state or invalid_address)
    no_commands = bool(summary['allocation_result'] or not row['active'] or rejected)
    messages = [e for e in row['events'] if e['op'] == 'send']
    assert len(messages) == (0 if no_commands else row['send_fail'] or 3), 'command count'
    if no_commands:
        assert summary['setup_models'] == 0, 'preflight must precede other attachment helpers'
    else:
        assert summary['setup_models'] == (3 if row['send_fail'] else 5)
        assert messages[0] == dict(op='send', selector=0, api=22, value=summary['desc_dma'] & 0xffffffff)
        if len(messages) >= 2:
            assert messages[1] == dict(op='send', selector=10, api=1, value=512)
        if len(messages) == 3:
            assert messages[2]['selector'] == 10 and messages[2]['api'] == 0
    if not summary['allocation_result']:
        assert summary['descriptor_stride'] == 16 and summary['descriptor_bytes'] == row['count']*16
    return dict(**row, expected_result=expected, invalid_state=invalid_state,
                invalid_address=bool(invalid_address), attachment_preflight_rejected=bool(rejected))


def mutations(text):
    rows = []
    for name, old, new, case in (
        ('count', ' ||\n\t    q->ndesc != MT7996_RX_MCU_RING_SIZE', '', dict(count=511)),
        ('descriptor', '!q->desc || ', '', dict(edit='missing-desc')),
        ('entries', '!q->entry ||', '0 ||', dict(edit='missing-entry')),
        ('owner', 'q->flags != MT_NPU_Q_TXFREE(0) || ', '', dict(edit='wrong-ring')),
        ('alignment', '!IS_ALIGNED(q->desc_dma, 16) || ', '', dict(address=0x17000001)),
        ('width', 'upper_32_bits(q->desc_dma) ||', '0 ||', dict(address=0x100000000)),
        ('native-range', '(u32)q->desc_dma >= 0xc0000000U ||', '0 ||', dict(address=0xd7000000)),
        ('wrap', '(q->desc_dma & GENMASK(29, 0)) > BIT(30) - size', 'size == 0', dict(address=0x3fffe010)),
        ('entry-order', '\terr = mt7996_npu_rx_event_validate(dev);\n\tif (err)\n\t\treturn err;\n', '', dict(count=511)),
    ):
        mutated = host.replace(text, old, new)
        binary, _ = compile_unit(mutated, 'mutant-'+name)
        trace = execute(binary, **case)
        try:
            verify(trace, True)
        except AssertionError as error:
            assert str(error) == 'early queue preflight status', (name, str(error))
            rows.append(dict(name=name, detected=True, witness=str(error),
                             summary=trace['summary'], binary_sha256=sha(binary.read_bytes())))
        else:
            raise AssertionError('undetected mutation: '+name)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    inputs = input_bindings()
    source = host.sources()
    changed = patched(source)
    builds, rows = {}, []
    specs = [('normal', {})]
    specs += [(f'count-{count}', dict(count=count)) for count in (0, 1, 511, 513, 1024)]
    specs += [(edit, dict(edit=edit)) for edit in
              ('missing-desc', 'missing-entry', 'plain-queue', 'wrong-ring', 'npu-tx', 'wed-owner', 'emi-owner')]
    specs += [(f'address-{address:x}', dict(address=address)) for address in
              (0, 1, 0x3fffe000, 0x3fffe010, 0x57000000, 0x7fffe000, 0x7fffe010,
               0x97000000, 0xbfffe000, 0xbfffe010, 0xc0000000, 0xd7000000,
               0xffffe000, 0xffffe010, 0x100000000)]
    specs += [(f'fail-{failure}', dict(failure=failure)) for failure in ('descriptor', 'entry', 'page_pool', 'wed_setup')]
    specs += [(f'send-fail-{index}', dict(send_fail=index)) for index in (1, 2, 3)]
    specs += [('provider-absent', dict(active=0)), ('provider-absent-invalid-queue', dict(active=0, count=1))]
    specs += [('forged-count-after-short-allocation', dict(count=511, edit='forged-count'))]
    for phase, sources in (('before', source), ('after', changed)):
        text, refs, boundaries = unit(sources)
        binary, command = compile_unit(text, phase)
        builds[phase] = dict(command=command, harness_sha256=sha(text.encode()),
                             binary_sha256=sha(binary.read_bytes()), source_spans=refs,
                             inherited_framework_boundaries=boundaries)
        for chip in (7996, 7992):
            for name, arguments in specs:
                row = verify(execute(binary, chip=chip, **arguments), phase == 'after')
                rows.append(dict(name=name, phase=phase, **row))
        print(json.dumps(dict(phase=phase, cases=len(specs)*2, passed=True)), flush=True)
    preserved = []
    for row in rows:
        if row['phase'] != 'after' or row['attachment_preflight_rejected']:
            continue
        prior = next(old for old in rows if old['phase'] == 'before' and
                     old['name'] == row['name'] and old['chip'] == row['chip'])
        assert prior['events'] == row['events'] and prior['summary'] == row['summary']
        preserved.append(dict(name=row['name'], chip=row['chip']))
    mutants = mutations(text)
    assert input_bindings() == inputs, 'bound inputs changed during execution'
    result = dict(schema=1, test_sha256=sha(Path(__file__).read_bytes()), patch_sha256=sha(PATCH.read_bytes()),
                  inputs_before_after=inputs,
                  builds=builds, cases=rows, unchanged_controls=preserved, mutations=mutants,
                  sources={name: dict(before=sha(value.encode()), after=sha(changed[name].encode()))
                           for name, value in source.items()},
                  limits=['Only host allocation, queue setup/reset, TXFREE attachment and early outer preflight execute.',
                          'Other attachment helpers, DMA/page-pool/framework/IRQ services and hardware are explicit models.',
                          'Malformed queue/count/address controls are injected, not evidence of a normal live failure.',
                          'The preflight trusts live queue metadata; forged count after a short allocation is deliberately not rejected.',
                          'No restricted provider/INODE or native DESC5/6/7/8 operation, hardware or image.'])
    output = OUT/'host-txfree.json'
    encoded = (json.dumps(result, indent=2)+'\n').encode()
    if args.check:
        assert output.read_bytes() == encoded
    else:
        output.write_bytes(encoded)
    print(json.dumps(dict(cases=len(rows), mutants=len(mutants), unchanged=len(preserved), evidence_sha256=sha(encoded))))


if __name__ == '__main__':
    main()
