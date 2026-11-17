# Which NPU bytes are in the default W1700K image?

**Neither inspected local sysupgrade FIT contains the four modules from
producer `b5af9591` or the RV32 CODE/DATA pair currently under replay.**
The protected October image still matches its own independently frozen
four-module producer. The mismatches are evidence of different artifacts,
not evidence of corruption or a failed boot.

| FIT (SHA256 prefix) | Modules vs its historical producer | Modules vs current producer | Packaged RV32 CODE / DATA |
| --- | --- | --- | --- |
| Protected checked-IRQ image `a3f1d04b` | 4/4 match `90abc8f3` | 0/4 | `4e43de6f` / `a282ca7a` |
| Prepared build-directory sysupgrade `978f9ddd` | Not assessed | 0/4 | `07f3585b` / `eb15df4e` |

Both FITs declare `config-1` as default and reference `kernel-1`, `fdt-1`
and the filesystem loadable `rootfs-1`. The selected DTBs identify Gemtek
W1700K, OpenWrt U-Boot layout, compatible `gemtek,w1700k-ubi`. For both
images the actual CODE and DATA read from that SquashFS match their own
embedded manifest's sizes and SHA256 values. Neither pair matches the bytes
bound to the new replay (`e6bc914c` / `ad905cb0`). No firmware was executed
by these comparisons.

## What changed

The full verifier used to remember the last kernel, DTB and filesystem seen
under `/images`. With unchanged, inert payloads and two ordinary configurations,
the preserved verifier inspected rootfs A for **both** defaults. The corrected
verifier selected A for default A and B for default B. It still verifies
hashes on unselected subimages. It now resolves named references in the
[FIT configuration](https://fitspec.osfw.foundation/) and rejects missing
references, wrong component types, or configurations outside the supported
W1700K sysupgrade layout (one kernel, one DTB, one filesystem loadable).
It does not infer a bootloader override, verify signature trust, or accept
arbitrary overlay, initramfs or multi-loadable layouts.

For a combined-producer world build, the runner passes the **exact producer
receipt and SHA256** to the image verifier. On this locked OpenWrt configuration
the linked modules contain debug information that is not in the package.
The verifier uses the configured build's AArch64 objcopy to reproduce the
`NO_RENAME`, no-build-ID, no-profiling strip-kmod operation on independent
temporary outputs. It compares those expected bytes to the untouched packaged
bytes, not just vermagic, symbol presence, filenames, or the build staging
tree. The acquired modules, tool and configuration are hash-checked.
For example, the fresh radio module `cb1d9f0f` has expected packaged hash
`134e6913ca37`; the protected image actually contains `1791cd6e37eb`.

A full combined run refuses a mismatch, and its parent checks all four
individual digests against both the producer and the image receipt. The
separate legacy producer path does not acquire this byte-identity claim.
The focused CLI can check an existing FIT without a world build:

```sh
python3 -B tools/verify_merged_image.py \
  --name <unused-receipt-name> --modules-only-image <candidate.itb> \
  --module-receipt <combined-result.json> --expected-producer-sha256 <pinned-sha256>
```

A completed comparison writes `module-comparison.json`; a mismatch exits 1.
The focused path never emits the successful full-world `result.json`.

## Evidence and limits

- The historical positive rehashed 364 producing inputs under the read-only
  `world-checked-irq-v5` snapshot. The new producer rehashed all 420 current
  inputs. Both real current comparisons exited 1 with all four names listed.
  The protected positive also agrees with the modules in the archived image
  verification receipt. The FITs and source module artifacts stayed unchanged.
- 90 host methods passed with no skips, including 21 focused tests. A real
  two-configuration FIT fixture exercised fdtget, fdtput and dumpimage.
  No target compiler, module load, world build, flash or router contact was
  used. A future real world build still has to pass the integrated path.
- The separate replay remained the original invocation `61e2d7b8`. A private
  read-only observation verified the guard/wrapper/driver, CPU advance, and
  all 345 live and retained input hashes. The observed profile-0 prefix had
  1,140 complete positive records and 129 publications, **not** a full verdict.
  Do not restart it or combine it with a historical profile.

After that invocation terminates, verify its own three profiles and terminal
receipt. A later current image must bind its Linux modules to `b5af9591`
or a newly qualified successor and its RV32 payloads to the intended verified
pair. Board boot, physical containment/drain, BA reuse/hot lifetime and actual
clients remain independent gates. See [EVIDENCE.json](EVIDENCE.json).
