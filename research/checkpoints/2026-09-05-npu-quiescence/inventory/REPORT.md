# Stock NPU Mailbox / Reset Target Inventory

Scope: the 134 supplied stock modules plus the supplied stock kernel ELF. No router,
OpenWrt source, builds, shared Ghidra projects, or ledger changes. All output is in
this inventory directory. This is binary-location/call evidence, not reset/drain
semantics or runtime validation.

## First Ghidra Targets

`ghidra_targets.tsv` contains 19 ranked targets with exact input SHA256, section,
entry, exclusive end, file offset, symbol/FDE evidence, and selection reason.
All module addresses below are **section-relative**, not loaded addresses or
assumed Ghidra import bases. An `unnamed@` label is generated, not a vendor symbol.

| Binary | Entry / exclusive end | Target | Concrete evidence |
| --- | --- | --- | --- |
| `mtk_pci.ko` | `.text+0x6370..0x65d8` | `send_rro_stop_msg_2_NPU` | `R_AARCH64_CALL26 host_notify_npuMbox` at `.text+0x6418` and `0x64ec` (function `+0xa8`, `+0x17c`; `.rela.text` indices 879, 891). |
| `mtk_pci.ko` | `.text.unlikely+0x50..0xa0` | Unnamed stop callback | FDE `.eh_frame+0x3a0`; `CALL26 send_rro_stop_msg_2_NPU` at `+0x90` (`.rela.text.unlikely` index 15). `ABS64 .text.unlikely+0x50` at `.data+0x1e0 = pci_dma_ops+0x128`. |
| `mtk_pci.ko` | `.text+0x6250..0x6368` | `send_rro_done_msg_2_NPU` | `CALL26 host_notify_npuMbox` at `.text+0x62e0` (function `+0x90`; `.rela.text` index 863). |
| `mtk_pci.ko` | `.text.unlikely+0x0..0x50` | Unnamed start callback | FDE `.eh_frame+0x37c`; `CALL26 send_rro_done_msg_2_NPU` at `+0x40` (`.rela.text.unlikely` index 7). `ABS64 .text.unlikely+0x0` at `.data+0x1e8 = pci_dma_ops+0x130`. |
| `mtk_hwifi.ko` | `.text+0xce90..0xcec4` | `mtk_ge_stop_npu` | `ABS64` pointer at `.rodata+0x700`; `BLR x1` at `.text+0xceac`, after loading callback slot `+0x128`. No mailbox relocation in this function. |
| `mtk_hwifi.ko` | `.text+0xcec4..0xcef8` | `mtk_ge_start_npu` | `ABS64` pointer at `.rodata+0x708`; `BLR x1` at `.text+0xcee0`, after loading callback slot `+0x130`. No mailbox relocation in this function. |
| `mt_wifi.ko` | `.text+0x115440..0x115f74` | `mt7990_ser_1_0_v1` | L1 coordinator candidate. Eight `CALL26 asic_ser_handler` sites: `0x115668`, `0x115678`, `0x115734`, `0x115758`, `0x115b0c`, `0x115b20`, `0x115c00`, `0x115c10`. |
| `mt_wifi.ko` | `.text+0x397770..0x397f80` | Unnamed dispatcher candidate | FDE `.eh_frame+0x7d1f8`. Materializes `mt7990_ser_1_0_v1` at `0x397bd0/0x397bd4`, and `mt7990_fe_reset` at `0x397f60/0x397f64`, using ADRP/ADD relocations. These are address references, not direct calls. |
| `mt_wifi.ko` | `.text+0x1162e0..0x116450` | `mt7990_fe_reset` | FE-reset coordinator candidate. `CALL26 asic_ser_handler` at `0x116388`, `0x1163e4`. |
| `mt_wifi.ko` | `.text+0x34d820..0x34d8a0` | `asic_ser_handler` | Named SER wrapper with indirect dispatch. Its target is not resolved by relocations alone. |
| `mt_wifi.ko` | `.text+0x386870..0x386894` | `hwifi_ser_handler` | Address references from `mt7990_init` at `0x10d568/0x10d56c`; `BLR x3` at `0x386888`. Callback registration/reference is not invocation proof. |

The PCI stop/start slots match the offsets loaded by the two `mtk_ge_*_npu`
wrappers. This is static slot correspondence; the live object/table binding and
complete execution path remain for Ghidra analysis. Do not collapse the BLR gaps
into relocation-proven direct call edges.

Secondary targets in the TSV:

- `mtk_hwifi.ko:mtk_ge_hw_reset`, `.text+0xd020..0xd04c`: pointer at
  `.rodata+0x6b0`; `BLR x1` at `0xd038`. No direct mailbox call.
- `mt7990.ko` anonymous `.text+0x140..0x1ac`, FDE `0x8c`: pointer at
  `.data+0x420`; direct `__const_udelay` call at `0x178`. Hardware-reset candidate,
  not a recovered vendor function name or proven NPU coordinator.
- `mt7990.ko` anonymous `.text+0xcc4..0xe70`, FDE `0x3b0`: pointer at
  `.data+0x80`; `__const_udelay` call at `0xd90`; `_dev_err` call at `0xe68`.
  The latter uses `.rodata` via relocations `0xe50/0xe54`, then instruction
  `0xe5c` adds `0x3a0`, where the string `mt7990_pdma_disable` resides. This is a
  debug-string name hint, not an ELF function symbol. There is no direct NPU import.
- `mtk_pci.ko` anonymous `.text+0x14c0..0x1608`: calls
  `mtk_bus_rx_ser_event` at `0x153c` and `0x1560`.
- `mtk_pci.ko` anonymous `.text+0x3924..0x3ce0`: calls
  `mtk_bus_rx_ser_event` at `0x3c24`.
- The named, ksymtab-referenced `mtk_bus_rx_ser_event` definition is in
  `mtk_hwifi.ko`, `.text+0x6f4..0x7a4`; export relocation `__ksymtab+0x90`.

## Mailbox Definition And All Callers

The only `host_notify_npuMbox` definition found in the supplied ELF set is the
stock kernel symbol at `0xffffffc0100d1cc4`. No module defines it.
The kernel ELF contains **zero relocation sections**, so no kernel-internal call
graph is claimed from this inventory. Its zero-sized symbols are address/name
evidence, not measured function extents.

| Importing module | Direct mailbox CALL26 sites |
| --- | ---: |
| `mtk_pci.ko` | 21 |
| `hw_nat.ko` | 8 |
| `npu.ko` | 4 |
| `mt_wifi.ko` | 2 |
| `speedtest.ko` | 1 |
| `tccicmd.ko` | 1 |

All **37** are backed by both `R_AARCH64_CALL26` and a BL opcode (`0x94000000` in
the unrelocated module). `mailbox_calls.tsv` lists every exact file SHA, relocation
section/index, section address, file offset, caller entry/offset/end and evidence.
23 sites have containing STT_FUNC ranges; the other 14 have exact relocation-backed
FDE ranges. No call site is assigned to a merely preceding, out-of-range symbol.

The two `mt_wifi.ko` calls are lower-priority reset leads:

- `.text+0x23778` is inside anonymous `.text+0x236c0..0x237e4`, FDE `0x4580`.
  The private SHOW table points to this function at `.data+0x1278`; its adjacent
  name pointer at `.data+0x1270` targets `.rodata.str1.8+0xfd20`, `npu_noba`.
- `.text.unlikely+0x144c` is inside anonymous `+0x1374..0x14a0`, FDE `0x4554`.
  The table's `.data+0x1288` function pointer is paired with `.data+0x1280` naming
  `.rodata.str1.8+0xfd30`, `force2cpu`.
- Both registrations lie in `RTMP_PRIVATE_AP_SHOW_SUPPORT_PROC`. The command
  strings are not function symbol names. See `mailbox_command_names.tsv` and
  `seed_data_references.tsv`.

## Related Interfaces

Kernel definition addresses only, with no provider-semantic analysis:

| Symbol | Linked address |
| --- | --- |
| `get_ecnt_npu_dev` | `0xffffffc0100d0f84` |
| `boot_npu_all_cores` | `0xffffffc0100d10e0` |
| `set_npu_needed_info` | `0xffffffc0100d1274` |
| `set_npu_mbox_mib` | `0xffffffc0100d16a0` |
| `npuMbox2host_isr` | `0xffffffc0100d1700` |
| `host_notify_npuMbox` | `0xffffffc0100d1cc4` |
| `npu_hw_kern_reset_testing` | `0xffffffc0100d23b0` |
| `get_npu_mbox_mib` | `0xffffffc0100d2514` |
| `npu_wifi_offload_get_force_to_cpu_flag` | `0xffffffc0100d0d90` |
| `npu_wifi_offload_set_force_to_cpu_flag` | `0xffffffc0100d264c` |

- `npu.ko:boot_all_npu_cores` at `.text+0xa50` calls `boot_npu_all_cores` at `0xa58`.
  `init_module` at `.text+0x11c4` calls `set_npu_needed_info` at `0x121c`,
  `boot_npu_all_cores` at `0x1220`, and the force-to-CPU getter at `0x141c`.
- `hw_nat.ko` anonymous `.text.unlikely+0x98c..0xab0` calls the mailbox at `0xa54`
  and `npu_wifi_offload_set_force_to_cpu_flag` at `0xa98`.
- `eth.ko` does not import the mailbox. `eth_rx` at `.text+0x2400` has ADRP/LDST64
  references at `0x27fc/0x2800` to `ra_sw_nat_restore_npu_pingpong_info`; these are
  **not direct-call evidence**. `hw_nat.ko:ecnt_hwnat_npu_init` and
  `ecnt_hwnat_npu_deinit` reference the same hook at `0x38f34/0x38f60` and
  `0x39000/0x39014` respectively.
- `mt_wifi_cmn.ko`, `mtk_hwifi.ko`, `mt7990.ko`, and `eth.ko` have no direct
  `host_notify_npuMbox` import. This does not exclude callback-mediated roles.
- `interface_imports.tsv` covers 44 NPU/mailbox/host-adapter import entries across
  all modules. `interface_providers.tsv` retains same-named definitions, binding,
  and ksymtab relocation references where present. Some module exports have
  LOCAL ELF binding; same-name matching alone is not proof of runtime binding.

## Exact Input SHA256

Module root:
`/home/captain/W1700KNPU/.local/legacy-firmware/work/extract/stock-rootfs/lib/modules/5.4.55`

| File | SHA256 |
| --- | --- |
| `mt_wifi.ko` | `40c8f974ad7317776f602c069c009d1f0d5d939d622ccdee275423fad1e35cb0` |
| `mt_wifi_cmn.ko` | `b468c07710ca55055d610b5de6422f152487e20c2d509a2f186195ccfe2c3192` |
| `mtk_pci.ko` | `c71b2073eeb2498c05c5e42bb5ceaf3df664cff42bf0b0740eb6152458e0857b` |
| `mtk_hwifi.ko` | `6d82ba02d96d638da9e80592a63e31c09d2f8603620066b604c1702d1171c8f7` |
| `mt7990.ko` | `502cd4b1ddab60b5a23a0d4d904f49ddae795dfa09154d70b63f933add323f81` |
| `eth.ko` | `6dc3281e9cf784c38f8ea83b272ddc65ef4fdfe2bf3acf99391d5def1635451d` |
| `hw_nat.ko` | `894b91053435a85fa44abb62bfe218c50ffc316f2a2252a75c0d1847f527f200` |
| `npu.ko` | `fecef1a24531765da1243de773ee7e9bb5b20ff47f1ad3b3736e1f09e9db088e` |
| `speedtest.ko` | `2654ada906e418dc8320f4885996fda8ba4d4a6e06435220e5596cf7b8c94196` |
| `tccicmd.ko` | `9a0e081553d6d92ad198e8b346c28f97b63855dde181bde14f57575a2964ed45` |
| `research/stock/elf/stock-kernel.vmlinux.elf` | `a51e6d0a6deee620a5f715c9469f193906cdf3fcea28b97ce01cf88383aa704e` |

`inventory.json` records full repo-relative paths, SHA256, sizes, ELF types and
counts for **all 135 inputs**. All input hashes were reread and verified in the
selection pass.

## Coverage And Replay

- 134 modules, 1 kernel ELF, 59,398 symbols, 5,680 named undefined import entries,
  1,054 relocation sections, 435,395 relocation records. No branch-opcode mismatch.
- `all_imports.tsv`: every module import, with all-reference, BL-call and B-branch counts.
- `all_import_relocations.tsv.gz`: every relocation to a named undefined symbol,
  including data references and containing functions, not just the focus pattern.
- `all_symbols.tsv.gz` and `all_relocations.tsv.gz`: complete parsed records.
- `related_symbols.tsv` and `related_relocations.tsv`: explicitly regex-selected
  names/references. Selection is not a semantic classification.
- `seed_relations.tsv`, `seed_calls.tsv`, `seed_data_references.tsv`: exact
  incoming/outgoing seed references, call/branch subset, and non-unwind data subset.
- `bounded_disassembly.txt`: nine bounded objdump captures with command and input
  SHA, including indirect wrapper instructions. It does not use Ghidra.
- `SHA256SUMS`: generated artifact and script hashes.

```sh
python3 -B /home/captain/W1700KNPU/research/checkpoints/2026-09-05-npu-quiescence/inventory/inventory_stock_elf.py
python3 -B /home/captain/W1700KNPU/research/checkpoints/2026-09-05-npu-quiescence/inventory/select_reset_targets.py
cd /home/captain/W1700KNPU/research/checkpoints/2026-09-05-npu-quiescence/inventory
sha256sum -c SHA256SUMS
```

Dependencies used: installed pyelftools 0.32 and AArch64 GNU objdump. Unnamed
ranges are recovered with pyelftools FDE parsing plus `.rela.eh_frame` initial-PC
relocations, not inferred from arbitrary gaps between named functions. No kernel
provider internals, ordering, acknowledgement, drain completion, indirect-call
resolution, source changes, or runtime acceptance are claimed. Ledger untouched.
