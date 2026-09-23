# Linked MT76 NPU Module Composition

2026-09-23. This checkpoint links the retained mt76 candidates, including RX
ownership patch 008 and shared MT7996 parser patch 009, against the prepared
6.18.44 AArch64 kernel. The build runs in an isolated ignored source copy.
Neither the packaged source lock nor the router was changed.

## Build Context

The source starts from the kernel validated `rx-parser.json` checkpoint. Its
`npu.c` matches the RX ownership receipt and `mt7996/mac.c` matches the parser
receipt. Earlier promoted mt76 overlays and staged host TX, TXFREE, L1 and RCU
candidates are already present in that prepared source. The runner checks both
source hashes before copying them into `.local/npu-linked-modules/`.

The target kernel has `CONFIG_NET_AIROHA_NPU=y`; Airoha NPU is built in.
The prepared kernel symbol table exports `airoha_npu_get` and
`airoha_npu_put`. It does not include the unpromoted provider transport/lifetime
patches 928/929. This is therefore a link check against the existing provider
contract, not a test of those pending provider corrections.

The first local build reached `modpost` but its kernel `Module.symvers` lacked
exports from the separately packaged mac80211 stack. The normal OpenWrt
mac80211 `Module.symvers` was not retained in this prepared build. A temporary
index was reconstructed from `__ksymtab` sections and namespace strings in
the installed 6.18.44 `mac80211.ko`, `cfg80211.ko` and `compat.ko` modules.
The script checks each ELF type and vermagic. It found 351 distinct exports,
preserved their GPL categories and namespaces, and rejected duplicates with
the kernel table. `CONFIG_MODVERSIONS` is off, so the generated index has zero
CRCs. This is a traceable modpost input, not the missing original index.

## Results

`make modules` completed and produced these AArch64 relocatable modules:

| Module | SHA256 |
| --- | --- |
| `mt76.ko` | `ff96182a9db00d1f7f4f268ef413c86e260352e26ae55c660c49510178cac93b` |
| `mt76-connac-lib.ko` | `35b110ec658e50d6d4ca5257392e75064d63fb645e5db1363dc204c175eb9ea2` |
| `mt7996e.ko` | `7c2f8edceabf544d324cafa25325b80dfb95340225dd22cdc205da972c1451c4` |

The modules and installed dependencies have matching
`6.18.44 SMP mod_unload aarch64` vermagic. The linked `mt76.ko` defines the
NPU RX poll and imports provider get/put. `mt7996e.ko` defines the corrected
receive parser and imports six `mt76_npu_*` functions that are defined in the
linked `mt76.ko`. The six imports are recorded by name in the receipt.

The successful `modpost` reported three nonfatal missing
`MODULE_DESCRIPTION()` warnings in the existing mt76, connac and MT7996
module sources. No unresolved-symbol error remained. The checkpoint verifier
accepts only that exact warning set; it does not label the build warning-free.
Independent Windows readback matched all three module hashes, the three
installed dependency hashes and the logged build hashes.

Receipt: `linked-modules.json`, SHA256
`196e783e84c098068f504e49dd816bf1709f2145f02593dc5a216d28506dfe03`.

## Replay

First reproduce the predecessor RX and parser checkpoints in this canonical
WSL workspace. Then use a fresh build name under the ignored local directory:

```sh
cd /home/captain/W1700KNPU
python3 tests/npu/test_npu_linked_modules.py --build-name linked-replay
```

The installed dependency modules, matching prepared kernel, compiler and
pyelftools are inputs. The runner refuses to overwrite an existing build name.
It writes the source copy and temporary export index under `.local/`, the
build log and receipt in this checkpoint directory.

## Remaining Gates

Module linking does not prove the candidate modules can be loaded together or
exercise the NPU. The synthesized external symbol index checks names and
export categories; it does not establish a full source/ABI equivalence with
the absent original mac80211 symbol index. The target kernel still needs the
provider lifetime/control candidates rebuilt in tree before end-to-end testing.
V2 host/provider binding, actual post-gate firmware execution, DMA coherence,
physical drain/containment, safe teardown/recovery and client acceptance are
open. Physical testing remains deferred by the user. No image, deployment,
router action, Wi-Fi configuration, protected-data upload, restricted INODE/
DESC operation, subagent or commit/push occurred.
