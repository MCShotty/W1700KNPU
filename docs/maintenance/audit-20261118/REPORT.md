# W1700K workspace audit, November 17-18, 2026

This is an offline maintenance and evidence audit of the canonical WSL checkout
and its native build scratch. At entry the worktree was clean at
`973ac20396acdb95811bf12718d5b8d5c0e9a56c`, identical to GitHub main.
There was one worktree, no unmerged index entries or prunable worktrees, and
both historical topic tips were ancestors of main. No firmware source, source
lock, board, radio, image, key, recovery volume or device backup was changed.

## Problems corrected

- **Orphaned replay and queue.** The October full-q16 process does not exist
  in the observed boot. Its historical invocation is
  `20c8f1ab62d74236bf977c134d09b059`; the unit was not found, no original
  processes/cgroup or terminal receipt remained, and the Windows controller
  was absent. The queue journal contains 490 complete records (last decision:
  `wait`) followed by 2,076 zero bytes. Its original is unmodified. Neither
  a queue result nor fresh target phase directory was present. The default
  systemd result on a missing unit is not an exit verdict.
- **Restore no-overwrite contract.** On POSIX the old final rename could replace
  an independently created output. Resolving the destination leaf also followed
  a dangling link. Both regression cases failed on the original. The restore
  tool now resolves only the parent and publishes a verified sibling partial
  without replacing an occupied name. On POSIX the output filesystem must
  support hard links; failure leaves no new output. Windows keeps its
  non-replacing rename. Six Linux tests passed. Five Windows cases passed,
  including concurrent publication; the symlink case requires a Windows
  privilege this account lacks. No system policy was changed.
- **Wi-Fi fixture provenance.** The security UI fixture had called the old
  `.build/openwrt` wireless view current (SHA prefix `d6f8c7b9`). The UI
  fixture and companion shell validator now default to the source lock's build
  directory; `--build-root` explicitly selects a historical tree. The old UI
  override reproduced the original fixture byte-for-byte. The current tests
  used the merged view `9241e054` and validator `8ad893d5`. Older dated Wi-Fi
  checkpoint generators with their own pinned builds/outputs remain historical.

## Evidence coverage

- At the starting revision: 2,543 tracked paths present, 947 tracked JSON files
  parsed, 160 checkpoint directories inventoried (150 reports, 49 EVIDENCE
  files). All 16 explicit top-level report SHA bindings matched. All 1,329
  declarations in the 11 `private_artifacts` / `retained_artifacts` maps
  matched; entries across maps are not necessarily unique files. All 116
  relative Markdown file links checked in the six starting guides resolved.
- All 127 migration artifact entries, 31 R1 and 82 V6.87 release checksum
  entries matched. All 18 parts and all three combined archive digests matched
  with no unlisted part in their directories. History, stock and rollback
  inputs were verified without restoring over a file.
- Cumulative patches and overlays reconstructed the locked content for 79
  OpenWrt and five LuCI files. 208 host tests passed with no skips, including
  the six restore cases. The 63 synthetic Wi-Fi validator cases passed. The
  existing Playwright/Edge fixture tested MLO defaults and explicit overrides
  on desktop (1280x800) and mobile (390x844) with both current and predecessor
  handlers: four fixture states, no browser errors or horizontal overflow.
  This was a synthetic form, not authenticated router save/apply.
- The original scratch ext4 UUID and marker SHA matched. Against that volume,
  all 454 queued target inputs, 332 original inputs and 332 retained copies
  rehashed; all retained files still have their write bits clear. The full-q16
  transcripts have 6,421 + 6,421 completed-profile positive RPCs and matching
  final artifacts. Profile 2 has **251 positive records**: one OPEN, 137 ENROLL,
  113 PUBLISH. Its 253 complete JSON lines end at serial 273; transcript SHA256
  `141ce1ebea5196c37522bbfe474905ef1b611ce792c8411b5fe52a1d78a7cfa1`.
  The saved positive sequences matched the recipe (a prefix for profile 2).
  No profile-2 summary, final broker/journal or matrix verdict was present.
  These are saved observations, not another execution or proof of how it ended.

## Cleanup

| Removed | Verified basis | Allocated bytes removed |
| --- | --- | ---: |
| Local compiler-cache entries | Project ccache, actual configured path, no remote storage, active compiler or linked files; cleared with its own tool under the build lock | 972,025,856 |
| 4,038 loose Git objects | Already packed; `git prune-packed`, no ref/reflog/stash/worktree change | 168,603,648 |
| 89 Python bytecode files | Each ignored cache path had a surviving tracked source; six resulting empty cache directories removed | 1,716,224 |

Total: **1,142,345,728 bytes (1.06 GiB)** of guest allocation, excluding the
six empty directory blocks. This is not a Windows free-space measurement.
`git fsck --full` passed before and after. No Git garbage or prune-packable
duplicates remained. The 25 dangling objects were retained: unreachable does
not establish that draft content is redundant. No reflog expiry, Git prune,
VHD compaction, volume remount, replay/queue restart or router access was performed.
Compiler statistics/configuration, input caches, validation capsules, Ghidra
projects, failed-run evidence, older modules and recovery data were left intact.

A filename/link scan of the source, tests, tools, docs, research and releases
trees (2,931 entries), and the first two levels of private project storage
(9,431 entries), found no unresolved symlinks or regular files ending in
`.partial`, `.rej`, `.orig`, `.swp` or `.tmp`. This is not a claim that
every file inside a private build or validation capsule is necessary.

## Resume

The scratch distribution held the data; the Ubuntu `native-c2` directory was
an empty, unmounted placeholder. Do not write build output there. Before any
new writer, establish the intended C-backed bind and verify the ext4 UUID
`b0b1bc48-d684-4090-a8cf-1ecb2939c36d` and storage marker SHA256
`88204019cf6b25344f75c97fdca80954018427519f8d023c46edb7490a9e2ebf`.
Recheck both guest and host budgets, writer lock, caps and current source.
The old queue is boot-bound; do not replay its launcher or splice the partial
third profile into another run. Use a distinct plan and output namespace for
fresh target modules and an independently qualified full 19,261-RPC invocation.
The FW-TXP fix is still source-only relative to the retained pre-fix producer.
Current-image, physical containment/drain, BA reuse/hot lifecycle and actual
client acceptance remain open. Keep Ethernet disconnected.

Machine-readable receipt: [EVIDENCE.json](EVIDENCE.json). Detailed inventories
and private hashes remain local in `.local/audit-20261117/`. This audit did not
rerun every historical emulator campaign, re-decompile stock, or boot hardware.
