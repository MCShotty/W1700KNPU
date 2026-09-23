#!/usr/bin/env python3
"""Pinned MT7996 RX header preparation and parser integration checks."""
import argparse
import difflib
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
from elftools.elf.elffile import ELFFile

sys.dont_write_bytecode = True
import test_npu_rx_ownership as rx

ROOT, KERNEL = rx.ROOT, rx.KERNEL
BUILD = ROOT / '.local/npu-rx-parser'
OUT = ROOT / 'research/checkpoints/2026-09-23-npu-rx-parser'
PRIOR = rx.OUT / 'rx-ownership.json'
MT76 = rx.BUILD / 'kernel-after-1/mt76-2026.09.01~be5ce791'
SOURCE = MT76 / 'mt7996/mac.c'
PREPARE = OUT / 'mt7996-rx-prepare.c'
PATCH = OUT / '009-mt7996-npu-rx-header-views.patch'
HARNESS = ROOT / 'tests/npu/npu-rx-parser-harness.c'
PROBE = [
    'sizeof(struct mt76_rx_status)', 'offsetof(struct mt76_rx_status, flag)',
    'sizeof(struct ieee80211_hdr)', 'offsetof(struct ieee80211_hdr, seq_ctrl)',
    'sizeof(struct ieee80211_radiotap_he)', 'sizeof(struct ieee80211_radiotap_he_mu)',
    'sizeof(struct ieee80211_radiotap_tlv)', 'sizeof(struct ieee80211_radiotap_eht)',
    'sizeof(struct ieee80211_radiotap_eht_usig)', 'sizeof(struct mt7996_mcu_rxd)',
    'MT_RXD1_NORMAL_GROUP_1', 'MT_RXD1_NORMAL_GROUP_2', 'MT_RXD1_NORMAL_GROUP_3',
    'MT_RXD1_NORMAL_GROUP_4', 'MT_RXD1_NORMAL_GROUP_5', 'MT_RXD2_NORMAL_HDR_OFFSET',
    'MT_PRXV_TX_MODE', 'MT_PRXV_FRAME_MODE', 'RX_FLAG_RADIOTAP_HE',
    'RX_FLAG_RADIOTAP_HE_MU', 'RX_FLAG_RADIOTAP_TLV_AT_END',
    'MT_TXS_HDR_SIZE', 'MT_TXS_SIZE', 'MT_RXQ_NPU0', 'MT_RXQ_NPU1',
]
q, sha, execute, once = rx.q, rx.sha, rx.execute, rx.lifetime.once


def function(source, name):
    pattern = r'^(?:[\w* \t]+\n)?[\w* \t]*\b' + re.escape(name) + r'\([^;{]*?\)\s*\{'
    return rx.lifetime.preflight.block(source, pattern)


def stage():
    prior = json.loads(PRIOR.read_text())
    assert sha(SOURCE) == prior['inputs_before_after'][str((rx.MT76 / 'mt7996/mac.c').relative_to(ROOT))]
    old = SOURCE.read_text()
    fill = function(old, 'mt7996_mac_fill_rx')
    new_fill = once(fill, '\t__le32 *rxd = (__le32 *)skb->data;', '\t__le32 *rxd, rxv_data[28];')
    for i in range(5):
        new_fill = once(new_fill, f'\tu32 rxd{i} = le32_to_cpu(rxd[{i}]);', f'\tu32 rxd{i};')
    new_fill = once(new_fill, '\tbool is_mesh = (rxd0 & mesh_mask) == mesh_mask;', '\tbool is_mesh;')
    init = '\tif (mt7996_mac_rx_prepare(skb))\n\t\treturn -EINVAL;\n\n\trxd = (__le32 *)skb->data;\n'
    init += ''.join(f'\trxd{i} = le32_to_cpu(rxd[{i}]);\n' for i in range(5))
    init += '\tis_mesh = (rxd0 & mesh_mask) == mesh_mask;\n\n'
    new_fill = once(new_fill, '\thw_aggr = status->aggr;\n', init + '\thw_aggr = status->aggr;\n')
    new_fill = once(new_fill, '\t\tif (ret < 0)\n\t\t\treturn ret;\n',
                    '\t\tif (ret < 0)\n\t\t\treturn ret;\n\n'
                    '\t\t/* Packet edits below can overwrite the consumed RX vector. */\n'
                    '\t\tif (rxd1 & MT_RXD1_NORMAL_GROUP_5) {\n'
                    '\t\t\tmemcpy(rxv_data, rxv, sizeof(rxv_data));\n'
                    '\t\t\trxv = rxv_data;\n'
                    '\t\t} else {\n\t\t\trxv = NULL;\n\t\t}\n')
    new = once(old, fill, PREPARE.read_text().rstrip() + '\n\n' + new_fill)
    new = once(new, '#include <linux/etherdevice.h>\n', '#include <linux/etherdevice.h>\n#include <linux/if_vlan.h>\n')
    reverse = function(new, 'mt7996_reverse_frag0_hdr_trans')
    revised = once(reverse, '\tstruct mt7996_sta *msta = msta_link->sta;', '\tstruct mt7996_sta *msta;')
    revised = once(revised, '\tif (!msta || !msta->vif)\n',
                   '\tif (!msta_link)\n\t\treturn -EINVAL;\n\n'
                   '\tmsta = msta_link->sta;\n\tif (!msta || !msta->vif)\n')
    new = once(new, reverse, revised)
    queue = function(new, 'mt7996_queue_rx_skb')
    revised = once(queue, '\t__le32 *rxd = (__le32 *)skb->data;\n\t__le32 *end = (__le32 *)&skb->data[skb->len];',
                   '\t__le32 *rxd, *end;')
    revised = once(revised, '\ttype = le32_get_bits(rxd[0], MT_RXD0_PKT_TYPE);',
                   '\tif (!pskb_may_pull(skb, sizeof(*rxd)))\n\t\tgoto free_skb;\n\n'
                   '\trxd = (__le32 *)skb->data;\n\ttype = le32_get_bits(rxd[0], MT_RXD0_PKT_TYPE);')
    revised = once(revised, '\tswitch (type) {\n',
                   '\t/* Control handlers consume a flat data pointer and length. */\n'
                   '\tif (type != PKT_TYPE_NORMAL && !pskb_may_pull(skb, skb->len))\n'
                   '\t\tgoto free_skb;\n\n\tswitch (type) {\n')
    revised = once(revised, '\tcase PKT_TYPE_RX_EVENT:\n',
                   '\tcase PKT_TYPE_RX_EVENT:\n\t\tif (skb->len < sizeof(struct mt7996_mcu_rxd))\n\t\t\tgoto free_skb;\n')
    revised = once(revised, '\tcase PKT_TYPE_TXS:\n',
                   '\tcase PKT_TYPE_TXS:\n\t\tif (skb->len < MT_TXS_HDR_SIZE * sizeof(*rxd))\n'
                   '\t\t\tgoto free_skb;\n\t\trxd = (__le32 *)skb->data;\n'
                   '\t\tend = (__le32 *)(skb->data + skb->len);\n')
    revised = once(revised, '\tdefault:\n\t\tdev_kfree_skb(skb);',
                   '\tdefault:\nfree_skb:\n\t\tdev_kfree_skb(skb);')
    new = once(new, queue, revised)
    PATCH.write_text('From: W1700KNPU development <noreply@example.invalid>\n'
                     'Subject: [CANDIDATE] wifi: mt7996: prepare bounded RX header views\n\n'
                     'Pull only the required RXD and data header prefix before caching\n'
                     'parser pointers. Retain non-linear packet bodies, snapshot RXV\n'
                     'metadata across packet edits, and bound the common type dispatch.\n\n'
                     'Unpromoted; firmware-event payload semantics and physical NPU\n'
                     'publication/lifetime remain separate integration contracts.\n\n---\n' +
                     ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                                  fromfile='a/mt7996/mac.c', tofile='b/mt7996/mac.c')))
    target = BUILD / 'staged/mt7996'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'mac.c').write_text(old)
    done = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(PATCH)],
                          cwd=target.parent, capture_output=True, text=True, timeout=30)
    assert done.returncode == 0 and 'offset' not in done.stdout and 'fuzz' not in done.stdout
    assert (target / 'mac.c').read_text() == new
    return old, new


def header_paths():
    mac802 = rx.lifetime.kernel.TARGET_INCLUDE / 'mac80211'
    paths = [MT76 / name for name in ('mt76.h', 'mt76_connac.h', 'mt76_connac3_mac.h', 'mt7996/mac.h', 'mt7996/mcu.h')]
    paths += [mac802 / name for name in ('linux/ieee80211.h', 'net/mac80211.h', 'net/cfg80211.h',
                                        'uapi/linux/nl80211.h', 'net/ieee80211_radiotap.h')]
    return paths + sorted((mac802 / 'linux').glob('ieee80211-*.h'))


def build(source, name):
    path = BUILD / name
    path.mkdir(parents=True, exist_ok=True)
    mac802 = rx.lifetime.kernel.TARGET_INCLUDE / 'mac80211'
    ieee = (mac802 / 'linux/ieee80211.h').read_text()
    headers = [p.read_text() for p in header_paths()]
    combined = '\n'.join(headers)
    connac = (MT76 / 'mt76_connac3_mac.c').read_text()
    standard_names = ['ieee80211_is_ext', 'ieee80211_is_data', 'ieee80211_is_mgmt', 'ieee80211_is_ctl',
                      'ieee80211_has_a4', 'ieee80211_is_data_qos', 'ieee80211_has_order',
                      'ieee80211_has_morefrags', 'ieee80211_is_beacon', 'ieee80211_is_qos_nullfunc',
                      'ieee80211_get_qos_ctl']
    functions = [function(ieee, n) for n in standard_names]
    util = (KERNEL / 'net/wireless/util.c').read_text()
    functions += [function(util, n) for n in ('ieee80211_hdrlen', 'ieee80211_get_hdrlen_from_skb')]
    functions += [function((MT76 / 'mt76.h').read_text(), 'mt76_skb_get_hdr'),
                  function((MT76 / 'mac80211.c').read_text(), 'mt76_insert_ccmp_hdr')]
    functions += [function(connac, n) for n in ('mt76_connac3_mac_decode_he_radiotap_ru',
                  'mt76_connac3_mac_decode_he_mu_radiotap', 'mt76_connac3_mac_decode_he_radiotap',
                  'mt76_connac3_mac_radiotap_push_tlv', 'mt76_connac3_mac_decode_eht_radiotap')]
    names = ['mt7996_reverse_frag0_hdr_trans', 'mt7996_mac_fill_rx_rate']
    if 'static int mt7996_mac_rx_prepare' in source:
        names.append('mt7996_mac_rx_prepare')
    names += ['mt7996_mac_fill_rx', 'mt7996_queue_rx_skb']
    functions += [function(source, n) for n in names]
    structs = ['ieee80211_hdr', 'ieee80211_qos_hdr', 'ieee80211_qos_hdr_4addr',
               'mt76_rx_status', 'mt7996_mcu_rxd', 'ieee80211_radiotap_he',
               'ieee80211_radiotap_he_mu', 'ieee80211_radiotap_tlv', 'ieee80211_radiotap_eht', 'ieee80211_radiotap_eht_usig']
    declarations = [q.declaration(combined, 'struct', n) for n in structs]
    selected_enums = set()
    enums = re.findall(r'\benum(?:\s+\w+)?\s*\{[^{}]*\}\s*;', combined)
    macros = {m[1] for m in re.finditer(r'^#define\s+(\w+)', combined, re.M)}
    selected_macros = {}
    existing = set(re.findall(r'^#define\s+(\w+)', HARNESS.read_text(), re.M))
    extra = [q.macro(connac, n) for n in ('HE_BITS', 'HE_PREP', 'MU_PREP', 'EHT_BITS', 'EHT_PREP')]
    extra.append(q.macro(source, 'to_rssi'))
    for unused in range(20):
        corpus = '\n'.join([HARNESS.read_text(), *PROBE, *functions, *declarations, *extra,
                            *selected_enums, *selected_macros.values()])
        tokens = set(re.findall(r'\b[A-Z][A-Z0-9_]+\b', corpus))
        tokens.update(re.findall(r'\b(?:MT_CRXV_HE_|MT_CRXV_EHT_|IEEE80211_RADIOTAP_HE_|IEEE80211_RADIOTAP_EHT_)\w+', combined))
        new_enums = {e for e in enums if tokens.intersection(re.findall(r'\b([A-Z][A-Z0-9_]+)\b\s*(?==|,|\})', e))} - selected_enums
        new_macros = (tokens & macros) - selected_macros.keys() - existing
        if not new_enums and not new_macros:
            break
        selected_enums |= new_enums
        selected_macros.update({n: q.macro(combined, n) for n in sorted(new_macros)})
    # Named enum types used in extracted signatures may have no referenced value yet.
    declarations.insert(0, q.declaration((MT76 / 'mt76.h').read_text(), 'enum', 'mt76_rxq_id'))
    selected_enums.discard(declarations[0])
    (path / 'parser-definitions.inc').write_text('\n\n'.join([*selected_macros.values(), *sorted(selected_enums), *declarations, *extra]) + '\n')
    (path / 'parser-functions.inc').write_text('\n\n'.join(functions) + '\n')
    (path / 'probe-values.inc').write_text(',\n'.join(PROBE) + '\n')
    binary = path / 'parser'
    command = [shutil.which('clang'), '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-unused-variable', '-Wno-sign-compare',
               '-Wno-address-of-packed-member', '-Wno-macro-redefined', '-fsanitize=address,undefined',
               '-fno-sanitize-recover=all', '-I', path, HARNESS, '-o', binary]
    execute(command)
    return binary, dict(path=str(binary.relative_to(ROOT)), sha256=sha(binary), command=list(map(str, command)))


def kernel_objects(sources, expected_layout):
    prior = json.loads(PRIOR.read_text())
    kernel = rx.lifetime.kernel
    templates = {row['npu_enabled']: row for row in prior['kernel_objects'] if row['phase'] == 'after'}
    env = dict(os.environ, STAGING_DIR=str(kernel.TARGET_INCLUDE.parent.parent),
               PATH=str(kernel.TOOLCHAIN / 'bin') + ':' + str(kernel.STAGING / 'host/bin') + ':/usr/bin:/bin')
    rows = []
    for phase, contents in zip(('before', 'after'), sources):
        for enabled, template in templates.items():
            origin = Path(next(arg[2:] for arg in template['command'] if arg.startswith('M=')))
            destination = BUILD / f'kernel-{phase}-{enabled}' / origin.name
            shutil.copytree(origin, destination, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('*.o', '*.cmd', '*.d', '*.mod', '*.ko'))
            (destination / 'mt7996/mac.c').write_text(contents)
            assert sha(destination / 'npu.c') == prior['derived'][str((origin / 'npu.c').relative_to(ROOT))]
            obj = destination / 'mt7996/mac.o'
            assert obj.resolve().is_relative_to(BUILD.resolve())
            obj.unlink(missing_ok=True)
            command = [arg.replace(str(origin), str(destination)) for arg in template['command'] if not arg.endswith('.o')]
            command.append('mt7996/mac.o')
            if phase == 'after':
                probe = destination / 'rx-layout.c'
                probe.write_text('#include "mt7996/mt7996.h"\n#include "mt7996/mac.h"\n#include "mt7996/mcu.h"\n'
                                 'const u64 rx_layout[] __used __section(".rx_layout") = {\n' +
                                 ',\n'.join(PROBE) + '\n};\n')
                (destination / 'rx-layout.o').unlink(missing_ok=True)
                command.append('rx-layout.o')
            done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=300)
            log = OUT / f'kernel-{phase}-{enabled}.log'
            log.write_text(done.stdout + done.stderr)
            assert done.returncode == 0 and not re.search(r'\b(?:warning|error):', log.read_text(), re.I), log.read_text()
            elf = ELFFile(io.BytesIO(obj.read_bytes()))
            assert elf['e_machine'] == 'EM_AARCH64' and elf['e_type'] == 'ET_REL'
            rows.append(dict(phase=phase, npu_enabled=enabled, command=command, path=str(obj.relative_to(ROOT)),
                             sha256=sha(obj), log=str(log.relative_to(ROOT)), log_sha256=sha(log)))
            if phase == 'after':
                probe_object = destination / 'rx-layout.o'
                elf = ELFFile(io.BytesIO(probe_object.read_bytes()))
                assert elf['e_machine'] == 'EM_AARCH64'
                layout = list(struct.unpack('<' + 'Q' * len(PROBE), elf.get_section_by_name('.rx_layout').data()))
                assert layout == expected_layout, (layout, expected_layout)
                rows[-1]['layout_probe'] = dict(path=str(probe_object.relative_to(ROOT)), sha256=sha(probe_object), values=layout)
            print(json.dumps(dict(stage='kernel', phase=phase, npu_enabled=enabled)), flush=True)
    return rows


def mutants(source):
    specifications = [
        ('no-type-view', '\tif (!pskb_may_pull(skb, sizeof(*rxd)))\n\t\tgoto free_skb;\n\n', '', 'truncated', 'AddressSanitizer'),
        ('no-normal-view', '\tif (mt7996_mac_rx_prepare(skb))\n\t\treturn -EINVAL;\n\n', '', 'fragmented', 'AddressSanitizer'),
        ('no-group4-size', '\tif (rxd1 & MT_RXD1_NORMAL_GROUP_4)\n\t\toffset += 4 * sizeof(__le32);\n', '', 'truncated', 'oracle:truncated-header-drop'),
        ('no-group5-size', '\t\tif (rxd1 & MT_RXD1_NORMAL_GROUP_5)\n\t\t\toffset += 24 * sizeof(__le32);\n', '', 'fragmented', 'AddressSanitizer'),
        ('no-padding-size', '\toffset += 2 * FIELD_GET(MT_RXD2_NORMAL_HDR_OFFSET, rxd2);\n', '', 'fragmented', 'AddressSanitizer'),
        ('no-data-header-view', 'return pskb_may_pull(skb, offset + len) ? 0 : -EINVAL;',
         'return pskb_may_pull(skb, offset + sizeof(__le16)) ? 0 : -EINVAL;', 'fragmented', 'AddressSanitizer'),
        ('no-rxv-snapshot', '\t\t\tmemcpy(rxv_data, rxv, sizeof(rxv_data));\n\t\t\trxv = rxv_data;\n', '', 'snapshot', 'oracle:immutable-rxv-radiotap'),
        ('missing-vector-decode', '\t\t} else {\n\t\t\trxv = NULL;\n\t\t}\n', '\t\t}\n', 'missing-vector', 'oracle:push-headroom'),
        ('null-station-dereference', '\tif (!msta_link)\n\t\treturn -EINVAL;\n\n', '', 'unknown-station', 'runtime error:'),
        ('no-control-view', '\tif (type != PKT_TYPE_NORMAL && !pskb_may_pull(skb, skb->len))\n\t\tgoto free_skb;\n\n', '', 'controls', 'oracle:control-linear-view'),
        ('no-event-header', '\t\tif (skb->len < sizeof(struct mt7996_mcu_rxd))\n\t\t\tgoto free_skb;\n', '', 'controls', 'oracle:event-header-extent'),
    ]
    rows = []
    for name, old, replacement, mode, expected in specifications:
        changed = once(source, old, replacement)
        binary, compiled = build(changed, 'mutant-' + name)
        done = subprocess.run([str(binary), mode], capture_output=True, text=True, timeout=120)
        assert done.returncode != 0 and expected in done.stderr, (name, done.stdout, done.stderr)
        log = OUT / ('mutant-' + name + '.log')
        log.write_text(done.stderr)
        rows.append(dict(name=name, mode=mode, expected=expected, build=compiled,
                         log=str(log.relative_to(ROOT)), log_sha256=sha(log), exit_code=done.returncode))
        print(json.dumps(dict(stage='mutant', name=name)), flush=True)
    return rows


def fingerprints():
    paths = [Path(__file__), HARNESS, PREPARE, PRIOR, SOURCE, *header_paths(),
             MT76 / 'mt76_connac3_mac.c', MT76 / 'mac80211.c', KERNEL / 'net/wireless/util.c',
             KERNEL / 'include/linux/if_vlan.h']
    return {**rx.fingerprints(), **{str(path.relative_to(ROOT)): sha(path) for path in paths}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-kernel', action='store_true')
    args = parser.parse_args()
    before = fingerprints()
    sources = stage()
    rows, negatives, layouts = [], [], []
    for phase, source in zip(('before', 'after'), sources):
        binary, built = build(source, phase)
        layouts.append(json.loads(execute([binary, 'layout'])))
        for queue in (0, 19, 20):
            modes = ('linear',) if phase == 'before' else ('linear', 'fragmented', 'radiotap', 'truncated', 'failures', 'controls', 'snapshot', 'missing-vector', 'unknown-station')
            for mode in modes:
                result = json.loads(execute([binary, mode, str(queue)]))
                rows.append(dict(phase=phase, build=built, result=result))
        if phase == 'before':
            for mode, failure in [('truncated', 'AddressSanitizer'), ('fragmented', 'AddressSanitizer'),
                                  ('snapshot', 'oracle:immutable-rxv-radiotap'),
                                  ('missing-vector', 'oracle:push-headroom'),
                                  ('unknown-station', 'runtime error:')]:
                done = subprocess.run([str(binary), mode], capture_output=True, text=True, timeout=60)
                assert done.returncode != 0 and failure in done.stderr, (mode, done.stdout, done.stderr)
                log = OUT / ('baseline-' + mode + '.log')
                log.write_text(done.stderr)
                negatives.append(dict(mode=mode, exit_code=done.returncode, expected=failure,
                                      log=str(log.relative_to(ROOT)), log_sha256=sha(log)))
        print(json.dumps(dict(stage='host', phase=phase)), flush=True)
    linear = [row['result']['digest'] for row in rows if row['result']['mode'] == 'linear']
    assert len(set(linear)) == 1
    mutations = mutants(sources[1])
    assert layouts[0] == layouts[1]
    compiled = [] if args.skip_kernel else kernel_objects(sources, layouts[0])
    check = subprocess.run(['perl', str(KERNEL / 'scripts/checkpatch.pl'), '--strict', '--no-tree',
                            '--no-signoff', str(PATCH)], capture_output=True, text=True, timeout=30)
    (OUT / 'checkpatch.log').write_text(check.stdout + check.stderr)
    assert check.returncode == 0, check.stdout + check.stderr
    assert fingerprints() == before
    paths = [BUILD / 'staged/mt7996/mac.c']
    for row in [*rows, *mutations]:
        directory = ROOT / Path(row['build']['path']).parent
        paths.extend(directory / name for name in ('parser-definitions.inc', 'parser-functions.inc', 'probe-values.inc'))
    for row in compiled:
        directory = ROOT / Path(row['path']).parent
        paths += [directory / 'mac.c', directory.parent / 'npu.c', directory.parent / 'mt76.h']
        if 'layout_probe' in row:
            paths.append(directory.parent / 'rx-layout.c')
    derived = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    summary = dict(baseline_cases=sum(row['result']['cases'] for row in rows if row['phase'] == 'before'),
                   corrected_cases=sum(row['result']['cases'] for row in rows if row['phase'] == 'after'),
                   baseline_controls=len(negatives), mutants=len(mutations),
                   kernel_objects=len(compiled) + sum('layout_probe' in row for row in compiled))
    output = OUT / ('rx-parser-models.json' if args.skip_kernel else 'rx-parser.json')
    output.write_text(json.dumps(dict(schema=1, summary=summary, inputs_before_after=before, derived=derived,
                                     profiles=rows, baseline_controls=negatives, mutants=mutations,
                                     kernel_objects=compiled, patch=dict(path=str(PATCH.relative_to(ROOT)), sha256=sha(PATCH)),
                                     layout=dict(expressions=PROBE, values=layouts[0]),
                                     compilers=dict(native=execute(['clang', '--version']).splitlines()[0],
                                                    kernel=execute([str(rx.lifetime.kernel.PREFIX) + 'gcc', '--version']).splitlines()[0]),
                                     checkpatch=check.stdout + check.stderr,
                                     limits=['Selected actual MT7996 parser, rate, header reconstruction, CCMP and HE/EHT radiotap C executes with modeled skb/framework dependencies.',
                                             'Short model head allocations and forced relocation expose logical bounds/stale-pointer failures; no physical router reachability is claimed.',
                                             'Firmware-event body semantics, control/PPE callback internals, metadata provenance, physical DMA and complete lifecycle remain open.',
                                             'Shared MT7996 receive code changes affect MAIN and NPU queues; the tested queue IDs are 0, 19 and 20.',
                                             'No source-lock/overlay, firmware image, router, Wi-Fi configuration or restricted-lane change.']), indent=2) + '\n')
    print(json.dumps(dict(**summary, receipt_sha256=sha(output))))


if __name__ == '__main__':
    main()
