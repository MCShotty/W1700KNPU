# The frozen baseline world is running

Keep observing `w1700k-world-txp-20261118-stream-a.service` under the
WSL user manager. Invocation `1137136aae6141e9bbaa3196bc3e69a9` holds
both writer locks. It has **not** produced a world verdict or FIT.
[Launch, resource and live-process pins](EVIDENCE.json).

At the [follow-up](../2026-11-18-npu-ppe-table-owner/BUNDLE.json), the same
invocation had completed the 845,102-entry protected inventory at
36.1 MiB parent peak RSS and reached kernel compilation.

## Smaller Host Overhead

The previous host launcher retained a full lower-tree dictionary during
the build and constructed another at completion. The new host launcher
streams JSONL rows, records a count and SHA-256, and compares a separate
post-build walk. Each row preserves path, kind, numeric ownership, mode,
and either file bytes by hash or the literal link. Special nodes, walk
errors, and a mismatching second walk still refuse acceptance.

A 891,138-row synthetic control passed a 128 MiB address-space limit
at 20.6 MiB peak RSS; materializing the old row dictionary failed that
limit. All 101 focused host tests passed, including a successful synthetic
child whose result was rejected when the original lower changed.
This is host bookkeeping only. The pinned inner launcher, full world
command, namespace isolation, cache, module producer and source lock
are unchanged. The image-sealing checks remain in force.

## Exact Run

The original terminal verifier passed before launch. The unit uses
capsule `3d166089`, producer `b5af9591`, the C-backed native ext4 output,
and the existing D-backed protected lower. Both storage budgets passed
with their margins. Windows had 6,215,200,768 bytes available at admission;
the job has a 1.5 GiB cgroup cap, no swap and a 2 GiB headroom requirement
for admission. The capped full compilation has not passed.

At the saved observation, the unit and controller identities matched,
the CPU counter and streamed lower inventory advanced, and no OOM kill
was recorded. It was still scanning inputs, before dispatching the
frozen inner world. Follow the same handle:

```sh
systemctl --user show w1700k-world-txp-20261118-stream-a.service \
  -p InvocationID -p MainPID -p ActiveState -p SubState -p Result -p CPUUsageNSec
journalctl --user-unit w1700k-world-txp-20261118-stream-a.service -n 12 --no-pager
```

Check the matching terminal controller and actual world receipt, not
`Result=success` on an active service or mere presence of an output folder.
If the full build passes, rehash and [seal the selected baseline FIT](../2026-11-18-npu-image-seal/REPORT.md)
against the verified replay before activating the coherent-window delta.
No module load, router contact, flash, or physical retirement test.
