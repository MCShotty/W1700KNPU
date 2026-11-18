# Keep W1700K coherent NPU memory in its DRAM window

The [October EN7581 netdev RFC](https://lists.openwall.net/linux-kernel/2026/10/24/642)
reports that the NPU's host DRAM window is `0x80000000..0xbfffffff`.
External testing on the 2 GiB W1700K with a dedicated 16 MiB pool reported
working NPU mailboxes and rings, using about 10.7 MiB with those builds.
That is sizing and placement evidence, not a result for this checkout.
The RFC deliberately excludes Wi-Fi streaming mappings.

The protected FIT `a3f1d04b` and prepared FIT `978f9ddd` both select
`config-1/fdt-1`, DTB `8ad1b262`. The selected tree has the binary
and four WLAN reservations but no named coherent pool. The pinned
6.18.52 provider already allocates coherent mailboxes; the normal
32-bit DMA mask alone doesn't reserve its coherent storage in the NPU's
window. Neither saved image nor any replay input changed.

## One replacement stack

Apply these on the same frozen preimages **after** finishing replay and
qualification of the unmodified producer. Do not stack the preceding
provider patch on top of this one.

- Linux: [binding](airoha-npu-coherent-pool-binding.patch) and
  [replacement checked provider](airoha-checked-coherent-window.patch).
  The latter incorporates the prior queue and packet ownership work.
- OpenWrt: [W1700K DTS](openwrt-w1700k-coherent-window.patch) appends
  `dma` to the original five reservation references. The 16 MiB no-map
  allocation is placed by Linux within the lower window around static
  reservations, rather than hard-coding the address from the RFC test.
- mt76: use the [unchanged packet-owner patch](../2026-11-18-npu-packet-owner/mt76-checked-dma-owner.patch).
  No change to Wi-Fi streaming mappings or the radio/firmware wire format.

The W1700K UBI provider rejects a missing, disabled, conflicting, mis-sized
or out-of-window pool before registering IRQs and before allocating mailboxes.
It requires direct addressing and rejects another coherent allocator already
on the device. The pinned coherent allocator returns failure when its pool
is exhausted, with no fallback to unconstrained coherent memory. Unexposed
cleanup frees allocations before releasing the attachment. Once firmware
could own memory, the existing retention path keeps both the backing and
the allocator attachment. This does not add a physical DMA fence.

## Verified and pending

The three new patches apply to their exact locked preimages with zero
fuzz and pass checkpatch. The standalone DTB builds with the baseline
warnings only and preserves the original five reservation extents and
firmware names. The FIT verifier follows the default configuration and
rejects both historical images and bad placement/ownership fixtures.
[Exact hashes and scope](EVIDENCE.json).

```sh
python3 -B tools/verify_npu_coherent_window.py --fit <image.itb> --sha256 <expected-fit-sha256>
python3 -B -m unittest discover -s tests -p test_npu_coherent_window.py
```

No kernel/module or FIT was built with the new patches. When the frozen
run is accounted for, rebuild the exact stack, run binding validation and
repeat the linked ownership checks. Verify the selected FIT's pool and the
boot-time reservation's actual address, then check mailbox discovery, low
pool exhaustion, pre/post-exposure probe failures, normal Wi-Fi fallback,
offload, and teardown. Module/firmware identity must still pass the normal
image gates. No local board boot, DMA drain, hot reset, or client result has
been established by this checkpoint.

The [cold-probe sizing check](../2026-11-18-npu-coherent-budget/REPORT.md)
supports retaining 16 MiB for the exact staged stack.

The original replay was still live in profile 2 with 1,522 positive trace
records and no terminal verdict. The read-only observer rehashed all 345
bindings and sampled advancing driver CPU time. [Observation](REPLAY-LIVE.json).
