# Paired Raw NPU Build And Native Replay

Date: 2026-10-10. Base main: `629a65037e460e647a363aeadf274bc9279c62db`.

## Implemented

`tools/build_npu_pair.py` produces actual paired CODE/DATA from the pinned
vendor pair, twelve linked components and the final native composition. It
assembles twenty allocated sections, explicitly zeroes three NOBITS sections,
installs exactly61 original-site detours and checks the bridge extent edit.
It does not dump emulator memory or concatenate ELF containers. Each build has
its own compiled components rather than borrowing mutable shared build files.

`tools/npu_image.py` checks RV32/little-endian/linked identity, undefined symbols,
relocations, section aperture/overlap, exact site coverage/width/link register,
symbol identity/executable target, displaced instruction boundaries and original
preimages. Byte readback reconstructs the original pinned prefix and rejects
unaccounted bytes, altered hooks, nonzero BSS or preseeded loader storage.
This is structural consistency, not an authenticity signature or physical proof.

DATA covers the startup header and zero-filled plan/session/identity storage
through offset0x63a8. No fixture identity, request address or callback lease is
baked into the artifact. A real provider must publish the validated plan and a
fresh boot identity while prior actors are contained. Those contracts remain
unimplemented/unproved in the production path; unprovisioned native boot holds.

## Verified

- Two independent builds produce byte-identical CODE529,336 bytes and DATA25,512
  bytes. Their hashes are recorded below. Fifteen assembly/readback test groups
  pass, including ELF failures, wrong/missing sites and components, bad symbol/
  nonexecuting target, overlap, instruction splitting and raw-byte corruption.
- `raw-result.json` is the full-size native run, not a quick receipt. Constructor
  ELF/fixture effects in CODE2MiB and SRAM32KiB are erased with0xcc before copying
  only the raw pair. Allocated sections and all61 hooks read back correctly.
  No ELF bytes are injected afterward; ELF objects supply symbol/observer metadata.
- Native reset, six bootstrap commands, V2 DISCOVER/BIND and all-hart parking
  execute from these bytes. Selected RX0/RX2 retain2,560 packet claims; TXDONE512
  reaches3,072. Independent DESC5/6/7 add1,792 BA claims without changing packet
  state. Descriptor bytes, whole native RAM/SKB, exact ownership state, ordered
  locks, readiness-last and bounded stack checks pass using existing oracles.
- Six loader controls cover an unprovisioned pair, identity without plan, missing
  identity, stale session, short TXCHECK and overlapping request storage. Each
  stops before native IRQ setup, with no observed MMIO writes or TX clear.
- Eight TXDONE controls cover denied grant, partial pool, committed claim/cursor/
  release faults, failed SKB19 and bitmap/plan corruption before publication.
  Exact RAM/private-state predictions pass. Partial exhaustion retains17 new
  claims/descriptors; late failures do not reclaim or publish false readiness.
- `provider-result.json` executes the current reviewed Linux6.18.52 provider C
  with modeled external dependencies. The273-case loader matrix and seven cases
  using this exact pair pass address/undefined/leak sanitizers. Both copies read
  back byte-identical in order; request/size/plan failures preserve destinations.
- Eight build-runner tests and fresh offline FIT/board/218-package/78-module
  checks pass. A fresh normal build has twelve object payloads identical to the
  packaged core. Archive container hashes differ only with recorded member order;
  the packaged archive and image are unchanged. No fresh world build is claimed.
- `seal.py` verifies all159 raw-run input seals plus assembler/provider inputs,
  copies scoped text receipts and records current source/artifact hashes. Private
  raw binaries and modeled memory dumps stay under ignored local storage.

CODE SHA256: `2c73c38a406c514220ec3c4c9ceb9a7e1c530b3c218e494c50f3f3405f58744e`.
DATA SHA256: `44e907a4535cf40f999041acfc820000db9fe7c0822ad4c0166bfd8587648566`.
Unchanged FIT: `230e03a7b87cb9e14e0464b53d324bb2c4eb650b3c9a64a63514b30dde4458fe`.

The first identity control incorrectly expected discovery rejection; native V2
session initialization actually faults earlier. The loader test also initially
compared against an outdated staging tree; it now checks the prepared source
against the committed installer trace. Failed exploratory outputs are not proof.

Jev's actual `jev-1.13.0` pre-check selects checked sections rather than a mutable
snapshot (Choice confidence0.95). The post-check supports raw replay at its modeled
scope (0.95), unbaked identity (0.89) and actual-C copy scope (0.98); physical
acceptance is contradicted (0.97). It selects real-loader integration as the next
boundary (1.0). All probabilities/model/usage are preserved, not thresholded into
test proof or authority.

## Reproduce

From the repository root, using the installed WSL Clang/LLD and Python dependencies:

```sh
export PYTHONPATH=.local/npu-reset/python-lib:tests/npu
make -C firmware/npu pair PAIR_OUT=../../.local/npu-pair-fresh
make -C firmware/npu pair-check PAIR_OUT=../../.local/npu-pair-fresh
python3 tests/npu/test_npu_raw_pair.py --pair .local/npu-pair-fresh --name raw-fresh
python3 tests/npu/test_npu_pair_loader.py --pair .local/npu-pair-fresh --name loader-fresh
```

Use fresh output directories/names; the builder refuses to overwrite. Normal
`make all` still builds the archive. `--quick` raw replay is exploratory only.

## Remaining

The production recipe still copies vendor CODE/DATA, not this pair. The actual
provider does not publish the new plan/session/identity or contain prior users
before copying/triggering. Numeric aperture fit and native parking with modeled
platform inputs do not prove physical reservation, reset coverage or coherency.

Next implement the real cold provider/storage/identity-plan publication and paired
packaging, then wire strict Linux DISCOVER/setup/BIND callers. Other packet owners,
hot recycle, remaining worker/postgate consumers, physical backing/grants/cache/
DMA drains, teardown/recovery/rearm and actual clients remain required. No flash,
hardware contact, private backup upload or protected-storage change occurred.
The full NPU goal remains active.
