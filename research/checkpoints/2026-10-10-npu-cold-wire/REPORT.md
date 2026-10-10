# Session-Bound Initial Cold RX Wire

## Result And Boundary

The checked provider now sends post-BIND version, port type2 and RX0/RX2 DESC
through a distinct80-byte NCS2/NCR2 envelope. It reuses the existing V2 client,
nonce, loader identity, epoch1 and monotonic sequence. No new attachment session,
reset, resource retirement or hot-rearm API is added.

The native server checks the pinned transport and complete private snapshot,
bound identity/session/sequence, completed bootstrap, held barrier and one-shot
command order before acquiring its software callback lease. All software workers
must acknowledge the initial epoch; release, arm, ready, drain, deferred IRQ,
active and fault state must be clear. Completion rechecks identity, sequence,
history and held state. Failed callbacks retain active/inflight/resources and
fault admission. Valid bound sequences are consumed before platform/command
rejection so an abandoned request cannot become effective on replay.

First authenticated RX0 initializes packet ownership from the pinned plan. The
new native tests do not write admission.active or call packet initialization.
The Linux executor and provider setup mutex serialize the new path and CPU close;
errors stay sticky and rejected replies do not modify the caller's output.
Probe's early version query and unmarked/raw callbacks retain their dispatch.

This implements the initial strict RX prefix, not full offload. The actual Linux
setup still encounters later denied PCIe-address/page/indication/INODE/TXDONE
commands. Their parameter/ownership contracts and remaining owners/hot/postgate
need implementation. Independent physical exclusion, backing/cache/DMA visibility,
drains/retirement/recovery and actual clients remain open. A software lease,
matching nonce or PARKED observation is not physical retirement authority.

## Evidence

- Actual cold server, byte codec and Linux executor C pass229 cases with
  address/undefined/leak sanitizers:20 request-field controls,20 reply-field
  controls,128 invalid lengths before dereference,38 held-state controls,
  12 late identity/history/callback controls, eight transport faults and
  sequence/order tests. Eight compiled mutants fail the intended assertions.
- Initial real-provider setup/executor C still passes279 cases/nine mutants.
  The new helper/callback wrappers compile in the same actual-C harness.
- Three Linux-C-to-assembled-RV32 cases cover full nominal RX0/RX2, wrong boot
  identity rejection and a fault after the first committed packet claim.
  Nominal retains2,560 packet claims and observes native lease writes
  `[1,0,1,0,1,0,1,0]`. Fault retains one claim and active/inflight1; no resource
  release or retry occurs. The test injects a packet-owner fault, not a grant.
- Native callbacks receive a private stack snapshot matching the native owner's
  command. The old fixed-bootstrap-address/no-DESC observer was too narrow for
  the new lane; the added observer verifies snapshot/lease/dispatcher arguments
  without changing native guards. Full RX steps at existing getter boundaries
  keep the same instruction/wall budgets and bounded progress.
- The raw RV32 link originally exposed compiler-generated libc memcpy calls.
  Fixed-size volatile byte copying removes that dependency and pins the complete
  request/reply span. Assembly verifies the new48-byte cold-owner NOBITS section
  alongside existing allocator/page/packet sections, with no undefined symbols.
- A preliminary native run completed functionally but its input seal rejected
  concurrent formatting/document edits. It is not final acceptance evidence;
  the final frozen-source run and exact input hashes are retained here.
- Parser/publication60/eight, boot248/ten, lease13/four, probe269/three and
  request310/nine cases/mutants pass. Memory273/159/three earlier controls/nine
  mutants, retry6,174 and V2 44 regressions pass.
- Full raw ownership regression retains3,072 PKT/1,792 BA claims with six boot
  and eight TXDONE failure controls. Its later full-ring calls still use an
  explicit modeled lease; that broader test is not proof of the missing later
  real strict transport.
- Sixteen assembly/readback groups pass without skips; two independent builds
  match bytes and input provenance. World exits0;61 OpenWrt plus5 LuCI files
  replay, and offline FIT/Gemtek/218-package/78-module checks pass. The provider
  links cold/client objects internally; mt76 has no duplicate client symbols.
- Exact packaged provider undergoes full Ghidra analysis/export:53 executable
  functions,53 exports, zero decompilation failures. Cold ops, codec, shared
  sequence/executor/close and dedicated envelope checks are present in AArch64.
  This is static compiled evidence, not a loaded-kernel or hardware result.
- Kernel/executor delta checkpatch has zero errors/warnings/checks. World still
  contains upstream/package warnings and an ignored U-Boot install error; it is
  not a warning-free build. No hardware action or flash occurred.

## Artifacts

FIT26960714 bytes:
`7622acf9d0926c89849a06b130de8ae9a382048c7eaf32bcaee08649e12ee02d`.
Provider:
`7f043120585bfffb43f6d5c9d22682b52a95eeb16a97bc9a9f31ff74d027761d`.
CODE529528 bytes:
`0dc0d021a304502b3353a8be927050c4e6a746f8ab33390f32c5304603534c50`.
DATA25728 bytes:
`f762674e0d816518de6ef8cbe4e6f6f9bf5c7f2b49868162173fd3e679f3a72d`.
The13-object core archive SHA256 is
`09d16263213019a942773b4497a2c4aaaed160cb5d045e95ed90cbfb67988f19`.

The preceding `6a7dc41e...` complete image is hash-verified/preserved under
`.local/npu-cold-wire-20261010/pre-world-image/`; R1 and other protected images,
bootloader/calibration/private backups remain untouched. Exact source/artifact
hashes and sealed receipts are in `verification.json` and `file-manifest.json`.

## Jev Review

The official helper uses `Typesafe API` in memory and actual modeljev-1.13.0.
Five independent design questions and seven narrow source/receipt checks retain
their raw probabilities. Review choices select supported with probability.85
to.99 except early version at.70/confidence.55. This uncertainty is not hidden or
treated as proof: exact source comparison shows raw getter/sender/initializer
unchanged, and the launch helper directly calls the raw getter before provider
publication. The actual boot regression separately covers that order. Full-setup
scope is explicitly limited in the source contract and report. Jev supplies
semantic judgments; tests, exact comparisons and code inspection establish
their covered behavior, not physical acceptance or action authorization.

## Reproduction And Limits

Use fresh names in canonical WSL `/home/captain/W1700KNPU`:

```sh
export PYTHONPATH=.local/npu-reset/python-lib:tests/npu
provider=.local/merge-nonoc-20260923/kernel-merged/drivers/net/ethernet/airoha/airoha_npu.c
header=.local/merge-nonoc-20260923/kernel-merged/include/linux/soc/airoha/airoha_offload.h
pair=.build/merged-openwrt/bin/npu-pair-npu-cold-wire-20261010
python3 tests/npu/test_cold_wire.py --source "$provider" --name fresh-cold
python3 tests/npu/test_checked_loader.py --source "$provider" --pair "$pair" --name fresh-cold-publish
python3 tests/npu/test_provider_session.py --source "$provider" --header "$header" --pair "$pair" --publication .local/npu-loader-publish-20261010/fresh-cold-publish/nominal --cold-commands --name fresh-cold-native
python3 tools/build_firmware.py --name fresh-cold-world --jobs 8
python3 tools/verify_merged_image.py --name fresh-cold-offline
```

Do not change consumed sources during replay/sealing or use the prepared kernel
tree while world replaces it. Host kernel/RNG/firmware/OF/transport dependencies
and native backing/grants/host publication/scheduling are modeled. Actual C,
compiled code, native instruction replay and physical/client evidence are
distinct. Current software acceptance does not satisfy physical/hot/full-setup
requirements. The full user objective remains active.
