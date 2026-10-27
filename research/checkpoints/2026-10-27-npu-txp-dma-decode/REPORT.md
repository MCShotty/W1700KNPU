# MT7996 FW-TXP DMA Decode

## Result And Boundary

From `cba45d1`, retained AArch64 execution reproduces incorrect FW-TXP DMA-unmap
arguments in36 of90 cases. The source fix is integrated into canonical mt76
authority, but target compilation and execution of the fix are pending. No
fixed candidate is accepted by this checkpoint.

The PCI driver declares a36-bit streaming DMA mask separately from its32-bit
coherent mask. MT7996's FW-TXP writer stores DMA bits35:32 in length bits15:12.
The shared FW unmapper passes only the low address word and the unmasked encoded
length. For the reproduced high1/length64 case, it calls the modeled unmapper
with address `0x23400000`, length4160 rather than `0x123400000`, length64.

This proves the selected compiled argument mismatch for supplied valid-format
fixtures. It does not prove that this W1700K assigned such a DMA address or
experienced a physical fault. DMA, SKB completion and cache effects are models;
nonempty token IDR traversal and physical retirement remain unexecuted.

## Native Evidence

- Pre-fix producer: `92c75156014d8e4a4ed795656bf29d47268ca6b64e5a40544a35acc181d4e31e`.
- Radio: `d7cad6dfeb8578fa884220f14462089b416f0b98a895dd9d5d601214052d266d`.
- Connac: `c3a1dfffdd3481bb79b7d08f30d22f082a9711f5a971193325b94044be7aeed3`.
- Final q26 baseline receipt: `050b1964cd326662e8d2457e2c084b083d671139fa710a74b295634812a58a4a`.

`test_txp_dma_unmap_native.py` executes `mt7996_txwi_free` and its actual shared
FW unmapper, binding15 inputs including six source/header files and the exact
modules/producer. Both null/non-null SKB fixtures cover FW buffer counts0/1/2/6,
high fields0/1/15 and lengths1/64/4095. MAC-TXP controls cover its representable
high fields0/1/3 and the same lengths. Wider MAC address representability is not
established by these controls.

All36 nonzero-high, nonempty FW cases reproduce both malformed arguments;
the remaining54 cases match the expected argument lists. Four emulator-byte
controls fail the intended assertions: omitted FW unmaps, omitted MAC unmap,
omitted cache put and inverted format selection. Original modules stay intact.

The explicit `--contract baseline-bug` run succeeds as a bug reproduction while
recording `behavioral_contract_pass=false`. It is not correct-behavior acceptance.
The default correct contract against the old modules fails at
`native-unmap-arguments` in q20; that failure remains preserved.
Q19/q22 consumed test versions are retained. Repeated90-case runs are not270
unique cases. Q26 binds preserved old source after the canonical fix is installed.

The harness recognizes real compiler-emitted unmap-helper symbols when present,
rather than inventing an inlined symbol. Candidate compilation may still expose
new compiler shapes requiring fresh inspection; no future pass is inferred.

## Implemented Source Fix

Only the FW branch of `mt7996_txp_skb_unmap` changes. It decodes the existing
FW length/address fields locally, combines the address high bits under
`CONFIG_ARCH_DMA_ADDR_T_64BIT`, masks the length to `MT_TXP_BUF_LEN`, and unmaps
through the existing `mdev->dma_dev`. Valid low-address traffic keeps the same
arguments. No wire ABI, shared connac helper or other chip family is changed.
The MAC branch and remaining C-file suffix are byte-identical to the prior source.

Strict narrow checkpatch passes. The cumulative patch reconstructs all18
selected files with zero fuzz/offsets; only `mt7996/mac.c` changes. OpenWrt79/
LuCI5 source-export identities pass. Source lock is now
`cc128c3b2dc196c41c3b7db858dd22c3a1c7eb76ed9ca01efe11f060122c9d2d`;
mt76 patch is `73ccff87c6197d0bdd7cfcad0d9db6f73bb923833c1f079c87f1853d4661463c`.
The kernel patch and component mapping remain unchanged.

All417 old module-producer inputs remain verifiable, using three preserved
aliases for the pre-fix source lock, cumulative mt76 patch and mac.c. Old
module receipts must not be relabeled as qualifying the new source. Before
editing, six source/header versions and six tracking bodies were also retained.

Actual C compilation, the fresh four-module link, and the correct-contract
native execution of the new source have not run. Next require a fresh producer,
then this test's default correct contract with90 correct cases/four mutation
controls, plus RXWI/MCU/ordinary-RX-TX and broader lifetime regressions. Keep
the source change integrated; do not promote an image or load old modules as
though they contain it.

## Live Replay And Guards

Original full-q16 invocation `20c8f1ab62d74236bf977c134d09b059` remains live:
guard137794/wrapper137812/driver137844, driver start ticks5470636. Audit27 records
3060 checked positive RPCs in profile0,129 publications and930 RESET/MCU_BEGIN/
MCU_COMPLETE each. This is not a profile or complete three-profile verdict.
Driver CPU advances. All332 live inputs and read-only retained versions rehash;
the C source, cumulative patch, lock and new test are outside that set.

Do not restart or compile/sample alongside the timed replay. Keep boot3M/10s,
RPC100M/60s,400MiB/no swap,512MiB C-output reserve, margins and writer lock.
Analysis uses192MiB/no swap/Nice19/CPUWeight1, fresh Windows/Linux dual margins,
read-only C storage and an EROFS write control. Q26 reports52.2MiB peak/4.220s,
zero C output, not a target benchmark. Canonical source/export writes are on
the root D-backed device2096; C scratch remains separate device2112.

Jev1.13.0 reviewed six focused source/scope questions; raw probabilities and
request/results remain retained. It supports the declared streaming contract
at0.96 and the existing-format decode interpretation at0.88. Candidate-compiled
and physical-fault support are0.0. These judgments supplement the source/native
argument checks, not target or hardware acceptance.

Ethernet stays disconnected. No router contact, module load, image/flash,
Wi-Fi change, shutdown, new compaction or protected-data cleanup occurred.
Full native recipe, complete token/RRO/consumer lifetime, physical containment/
drain, reuse/hot and image/board/real-client gates remain. Full NPU goal is active.

Reproduce the old bug using the retained pre-fix source with
`tests/npu/test_txp_dma_unmap_native.py --producer RECEIPT
--expected-producer-sha256 HASH --source RETAINED_SOURCE --output FRESH_DIRECTORY
--contract baseline-bug`. For the future compiled fix, omit the baseline-bug
option and bind the new producer/current source. Private material stays under
`.local/npu-consumer-native-20261027/`; EVIDENCE.json records exact bindings.
