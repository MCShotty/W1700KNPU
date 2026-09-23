# MT7996 RX Header Views And RX-Vector Lifetime

2026-09-23. Unpromoted candidate patch 009, based on the prepared source after
the host RX ownership candidate 008. Packaged sources and firmware are unchanged.
This continues the NPU receive path into its shared MT7996 packet consumer;
the correction is not restricted to NPU queue IDs.

## Source Findings

The predecessor dispatcher reads its first packet-type word without first
checking availability. Normal RX reads fixed and optional RXD groups before
all corresponding bounds checks, and some checks use total skb length despite
directly accessing its linear head. NPU dequeue can construct a fragmented skb,
so total packet length alone is not a valid contiguous-header witness.

The reversed header-translation path also dereferences `msta_link` before
checking whether the station lookup succeeded. The HE/EHT radiotap path retains
a pointer into consumed RX-vector storage while subsequent skb header edits can
overwrite that storage. With Group 5 absent, the decoder can instead read beyond
the supplied vector or need more headroom than the consumed metadata provides.

Five executed predecessor controls expose short/split-head bounds failures,
RX-vector overwrite, missing-vector headroom failure and a null station access.
These are actual selected C paths under a deliberately strict skb model, not
observed physical router failures or proof of native NPU reachability.

## Correction

- Pull the common type word before reading it. Existing control handlers that
  consume flat data pointers receive a contiguous control message; normal data
  packets do not unconditionally linearize their bodies.
- Require the MCU event base header and TX-status fixed header before their
  corresponding dispatch operations. This does not validate event bodies/TLVs.
- Preflight the fixed RXD, selected optional groups, hardware padding and the
  required Ethernet/802.11 header prefix before normal RX caches pointers.
  VLAN translation-error and A-MSDU padding paths include their extra bytes.
- Recompute cached data pointers after possible head relocation. Snapshot the
  Group-3/5 vector into independent storage before packet edits; absent Group 5
  disables the optional HE/EHT radiotap decode rather than dropping normal data.
- Reject an absent station before dereferencing it during header reconstruction.

Only `mt7996/mac.c` changes. The package/source lock, public headers, NPU firmware
and the earlier host RX ownership implementation are unchanged.

## Executed Validation

The harness compiles the extracted normal parser and dispatcher, header
reconstruction, rate decoder, IEEE header helpers, CCMP insertion and HE/EHT
radiotap functions. It uses the exact staged driver headers and models skb
allocation/pull/push, station/framework state and external delivery/control/PPE
callbacks. Pulling a split head deliberately reallocates it, exposing stale
pointers. Normal packet bodies are required to remain nonlinear in split cases.

| Check | Result |
| --- | --- |
| Linear predecessor corpus | 7,680 cases |
| Corrected matrices | 613,113 cases |
| Predecessor failure controls | 5 reproduced |
| Compiled mutants | 11 rejected by designated failure checks |
| AArch64 driver objects | 4, before/after with NPU enabled/disabled |
| AArch64 layout probes | 2, matching 25 native-host values |
| Strict checkpatch | 0 errors, 0 warnings, 0 checks |
| Independent readback | 176 unique files matched |

Cases are parameterized executions repeated across MAIN, NPU0 and NPU1, not a
percentage of full NPU coverage. They cover all 32 selected-group combinations,
all eight padding encodings, eleven selected frame/translation formats and nine
linear-head splits. Six PHY-mode profiles exercise HT, HE and EHT metadata paths.
There are per-byte header truncations, pull-allocation failures, control-message
header boundaries, absent-station and absent-vector cases. Packet/status digests
match for the tested linear predecessor/corrected corpus. Radiotap output is
compared byte-for-byte with the actual decoder using an immutable vector copy.

The original logical head bounds are exposed by allocating only the modeled
head extent; real NPU page-pool allocations may be larger. Thus sanitizer errors
are not presented as proof of physical memory corruption. Control callback
internals and full network-stack semantics are not executed by this harness.

All six AArch64 objects compile without diagnostics. The layout probes compare
RX-status/header structures and relevant masks/flags against the actual kernel
build context. Initial scaffolding fixes supplied missing extracted definitions,
the VLAN include and correct staged radiotap header; the final full run followed
those corrections. The test's constants/layouts do not rely on the default
kernel radiotap header matching the driver's backport.

Readback covers 82 inputs, 54 derived files, 13 native executables, six AArch64
objects, 20 failure/build logs and the patch. Baseline sanitizer logs contain
process addresses and can vary across replays; no byte-identical full-replay
claim is made. Jev checked five narrow scope claims, with raw probabilities
retained locally. Its uncertain vector/event judgments were resolved against
the source and executed controls, not treated as correctness authority.

## Receipt And Replay

`rx-parser.json`, SHA256:
`1650e5f50ce6c188b48dcc62a649534ac5b3288df96a9ec98b1cc480bbafbff0`.

`009-mt7996-npu-rx-header-views.patch`, SHA256:
`09581cde14c4f21a0e9a6cb05262c982b9306e7b29888d08fefe4642190e740b`.

```sh
cd /home/captain/W1700KNPU
PYTHONPATH=.local/npu-reset/python-lib:tests/npu python3 tests/npu/test_npu_rx_parser.py
```

`--skip-kernel` writes a separate models receipt. Builds, independent readback
and raw semantic-review results stay in `.local/npu-rx-parser/`.

## Remaining Gates

These checks cover selected header views and transformations, not all packet
semantics. Firmware-event bodies/TLVs, full control/PPE callback validation,
metadata provenance, device group/publication contracts and complete Linux
receive-stack acceptance remain open. Refill/removal concurrency, physical DMA
coherence/drains, full boot, provider integration, recovery and safe rearming
remain separate requirements. Physical tests are still deferred.

No full-module/image build, loaded driver, hardware test, deployment, flash,
Wi-Fi configuration, protected-data, restricted INODE/DESC, subagent or
commit/push action occurred. The full NPU implementation goal is not achieved.
