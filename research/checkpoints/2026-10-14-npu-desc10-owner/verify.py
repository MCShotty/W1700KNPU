import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path('/home/captain/W1700KNPU')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools'))
import npu_image as image
import test_bootstrap_v2_composition as composition
from capstone import Cs, CS_ARCH_RISCV, CS_MODE_RISCV32, CS_MODE_RISCVC


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


references = {}
receipts = [HERE / 'owner-q6/result.json',
    ROOT / '.local/npu-rx-event-bind-20261013/desc10-regression-q1/result.json',
    HERE / 'current-pair-q2/manifest.json', HERE / 'repeat-pair-q1/manifest.json', HERE / 'focused.json']
for path in receipts:
    body = json.loads(path.read_text())
    assert body.get('passed', True)
    for name, expected in body['inputs'].items():
        assert sha(ROOT / name) == expected, (str(path), name)
        if name in references:
            assert references[name] == expected
        references[name] = expected
    for name, expected in body.get('binaries', {}).items():
        assert sha(ROOT / name) == expected, name
owner = json.loads(receipts[0].read_text())
assert len(owner['mutants']) == 8 and owner['exact_core_object'] == '.local/npu-desc10-owner-20261013/core/cold-txdone.o'
for mutant in owner['mutants']:
    directory = HERE / 'owner-q6/mutants' / mutant['name']
    assert sha(directory / 'host.so') == mutant['host_sha256']
    assert sha(directory / 'owner.elf') == mutant['rv_sha256']
archive = HERE / 'core/libw1700k-npu.a'
members = subprocess.check_output(['ar', 't', str(archive)], text=True).splitlines()
expected_members = [name + '.o' for name in ('barrier', 'admission', 'control-v2', 'bootstrap',
    'bootstrap-v2', 'cold-setup', 'startup', 'allocator', 'cold-page', 'cold-packet',
    'cold-indication', 'cold-tx', 'cold-descriptor', 'cold-tx-buffer', 'cold-rx-event',
    'cold-txdone', 'gdma', 'tunnel-header', 'tunnel-packet')]
assert members == expected_members
assert subprocess.check_output(['ar', 'p', str(archive), 'cold-txdone.o']) == (HERE / 'core/cold-txdone.o').read_bytes()

source = ROOT / '.local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c'
after = source.read_text()
before = after
changes = [
    ('\t\t    life->rx_published || life->rx_serial || life->tx_attempted || life->tx_published ||\n',
     '\t\t    life->rx_published || life->rx_serial ||\n\t\t    life->tx_attempted || life->tx_published ||\n'),
    ('\t\t    life->endpoint_base != endpoint_base || life->endpoint_bytes != endpoint_bytes ||\n',
     '\t\t    life->endpoint_base != endpoint_base ||\n\t\t    life->endpoint_bytes != endpoint_bytes ||\n'),
    ('\t\t\terr = npu_linux_control_cold_exchange(&priv->wlan_control, &command, &value);\n',
     '\t\t\terr = npu_linux_control_cold_exchange(&priv->wlan_control,\n\t\t\t\t\t\t\t      &command, &value);\n')]
for old, new in changes:
    assert before.count(new) == 1
    before = before.replace(new, old, 1)
sealed = json.loads((ROOT / 'research/checkpoints/2026-10-13-npu-rx-event-bind/allocation.json').read_text())
source_name = str(source.relative_to(ROOT))
assert hashlib.sha256(before.encode()).hexdigest() == sealed['inputs'][source_name]
delta = HERE / 'source-delta.patch'
relative = 'drivers/net/ethernet/airoha/airoha_npu.c'
delta.write_text('Subject: [PATCH] net: airoha: wrap retained RX allocation checks\n\n'
    'Keep the existing allocation predicates and exchange arguments unchanged.\n\n---\n' +
    ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
        fromfile='a/' + relative, tofile='b/' + relative)))
checker = ROOT / '.build/merged-openwrt/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_an7581/linux-6.18.52/scripts/checkpatch.pl'
check = subprocess.run(['perl', str(checker), '--no-tree', '--strict', '--no-signoff', str(delta)], capture_output=True, text=True)
(HERE / 'checkpatch.txt').write_text(check.stdout + check.stderr)
assert check.returncode == 0, check.stdout + check.stderr

diagnostic = ROOT / 'tests/npu/test_host_tx_lifetime_native.py'
tree = ast.parse(diagnostic.read_text())
calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and
         isinstance(node.func, ast.Name) and node.func.id == 'print']
record = next(k.value for k in calls[-1].args[0].args[0].keywords if k.arg == 'native_enrollment_records')
code = compile(ast.Expression(record), str(diagnostic), 'eval')
from types import SimpleNamespace
assert [eval(code, {'__builtins__': {}, 'int': int}, {'args': SimpleNamespace(rx_event=b)})
        for b in (False, True)] == [14, 15]

original = composition.CODE_INPUT.read_bytes()
assert hashlib.sha256(original).hexdigest() == image.CODE_SHA
sites = {0x8400b530: 'count metadata', 0x8400b53c: 'typed ID-pool pointer',
    0x8400b4b6: 'descriptor field4 clear', 0x8400b4ba: 'descriptor packet pointer',
    0x8400b4bc: 'descriptor field8 clear', 0x8400b4c0: 'descriptor field12 clear',
    0x8400b4ce: 'descriptor field4 status', 0x8400b4d6: 'software packet ID',
    0x84004a62: 'temporary sentinel', 0x84009b04: 'temporary occupied ID',
    0x84004aac: 'SKB state clear', 0x84004ad2: 'SKB occupied marker',
    0x84004afa: 'SKB occupied queue ID', 0x84004b32: 'SKB free queue ID',
    0x84004b5c: 'SKB head', 0x84004b60: 'SKB tail',
    0x8400b54a: 'TXDONE counter clear', 0x8400b558: 'TXDONE ready byte'}
md = Cs(CS_ARCH_RISCV, CS_MODE_RISCV32 | CS_MODE_RISCVC)
instructions = []
for address, role in sites.items():
    instruction = next(md.disasm(original[address - image.CODE:address - image.CODE + 8], address))
    assert instruction.address == address and instruction.mnemonic in ('sw', 'c.sw', 'sh', 'sb')
    instructions.append(dict(address=hex(address), role=role, bytes=instruction.bytes.hex(),
                             mnemonic=instruction.mnemonic, operands=instruction.op_str))
(HERE / 'native-sites.json').write_text(json.dumps(dict(original_code_sha256=image.CODE_SHA,
    instructions=instructions, limits=['Static original store sites, not dynamic execution or hook installation.']), indent=2) + '\n')

assembly = json.loads((HERE / 'assembly.json').read_text())
assert assembly['passed'] and assembly['repeat_build']
exports = json.loads((HERE / 'source-export.json').read_text())
assert all(row['passed'] for row in exports)
fit = ROOT / '.build/merged-openwrt/bin/targets/airoha/an7581/openwrt-airoha-an7581-gemtek_w1700k-ubi-squashfs-sysupgrade.itb'
assert sha(fit) == '82b1563a809b7c5a2b7872fde908e2d16b261e1f40306090f73a93ae498d19f7'
extra = [Path(__file__), source, diagnostic, ROOT / 'firmware/source-lock.json',
    ROOT / 'firmware/overlay/openwrt/target/linux/airoha/patches-6.18/999-w1700k-integrated-npu.patch']
references.update({str(path.relative_to(ROOT)): sha(path) for path in extra})
result = dict(passed=True, completed_receipts=len(receipts), verified_input_hashes=len(references),
    inputs=references, receipts={str(path.relative_to(ROOT)): sha(path) for path in receipts},
    archive=dict(path=str(archive.relative_to(ROOT)), sha256=sha(archive), objects=members),
    normal_raw_unchanged=dict(code_sha256=image.sha((HERE / 'current-pair-q2/CODE.bin').read_bytes()),
        data_sha256=image.sha((HERE / 'current-pair-q2/DATA.bin').read_bytes()), hooks=126, components=16),
    source_export_files=sum(row['changed_files_verified'] for row in exports),
    provider_style=dict(before_sha256=sealed['inputs'][source_name], after_sha256=sha(source),
        exact_reverse_cleanup_matches_sealed_source=True, checkpatch_returncode=check.returncode),
    diagnostics=dict(enrollment_records=[14, 15]), existing_fit_sha256=sha(fit),
    limits=['Portable DESC10 owner is not yet instantiated or invoked by the normal native dispatcher.',
            'No new original DESC10, full allocator/caller, world/provider/Ghidra or hardware/client acceptance is claimed.'])
(HERE / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ('passed', 'completed_receipts', 'verified_input_hashes', 'source_export_files')}))
