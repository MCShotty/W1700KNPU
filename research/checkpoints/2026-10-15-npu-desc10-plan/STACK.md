# Compiled Frame Measurements

These checks measure individual compiler frames. They do not establish a full
call-chain maximum, interrupt/indirect-call bound, physical stack placement or
hardware acceptance. No production source, current raw pair or live producer
input was changed for this work.

## Normal Archive

All22 stack-instrumented RV32 normal-Os objects are byte-identical to the
packaged normal build. Every defined function has a matching static .su record:
166 functions, largest individual frame4688 bytes in cold-inode.c:context.
Other large frames include DESC10 packets_live2080 and complete1072 bytes,
PCIe-tail context560/prior_live464 and INODE prior_live480. Do not add unrelated
maxima together or infer that their largest single value bounds a call chain.

The first fresh Makefile archive has a different member order from the packaged
incremental archive and fails exact container equality. It is retained at
.local/npu-desc10-plan-20261015/stack-normal-q1/libw1700k-npu.a,
SHA25631af98d8865f7020175d5705da764b0ed8ddb7d2297e39000fa0f52d9926fa46.
All22 individual members are identical. Repacking those unchanged members into
a new normal-reference-order.a using the exact packaged order reproduces its
entire archive byte-for-byte, SHA256
b2cd47100d28e12146a4548a08d4159a6f7d8b46f71df2a48d20898568e4fdc0.
The verifier still requires exact container equality; no member/hash waiver.

Receipt .local/npu-desc10-plan-20261015/stack-normal-q2.json,
SHA256b421ab045ca506ee47865fecd2c81a04cfae7f60714d4f19fb9fd1028dbf84e8.

Reproduce compilation in a fresh ignored directory using the normal Makefile
flags plus -fstack-usage:

```sh
make -C firmware/npu OUT=/home/captain/W1700KNPU/.local/stack-audit-new \
  'CFLAGS=--target=riscv32 -march=rv32imac_zicsr -mabi=ilp32 -std=c11 -Os -Wall -Wextra -Werror -ffreestanding -fno-builtin -fno-stack-protector -fstack-usage' -j4
```

If its archive ordering differs, retain it and construct a separate new archive
from these objects in ar t's exact packaged-member order. Then run the canonical
verifier with --instrumented-directory, --core-directory, --instrumented-archive
and a new --output path. Both object and complete archive bytes must match.
The archive argument does not relax equality.

## Exact DESC10 Component

The first combined compile/link measurement emitted one .su file containing only
eleven binding functions because Clang reused the output-derived filename for
both C translation units. Its allocated-section equality observation remains
valid, but eleven records are not comprehensive component coverage. The original
driver/artifacts/receipt are retained locally under stack-raw-q1.

The canonical test now compiles the two translation units separately with the
original O2 options plus -fstack-usage, relinks in the original order and requires
every allocated section's name, address, extent, type and bytes to match the
actual current component. Its record multiset must exactly match all29 defined
C function symbols, including both distinct context functions. Largest individual
C frame2064 bytes; assembly/original-firmware frames and other components remain
unmeasured. This is not a complete stack bound or native admission test.

```sh
PYTHONPATH=.local/npu-reset/python-lib:tests/npu:tools \
  python3 -B tests/npu/test_desc10_stack_usage.py \
  --pair .local/npu-desc10-plan-20261015/pair-q1 --name stack-audit-new
PYTHONPATH=.local/npu-reset/python-lib:tests/npu:tools \
  python3 -B -m unittest test_npu_stack_usage
```

Canonical receipt .local/npu-desc10-stack/access-restored-q1/result.json,
SHA256d2840e58fd283254bfbc5e6c41138b154e4e890d473b0056cb671bdd52214fd2.
Fourteen parser/inventory units pass, including synthetic ELF/file fixtures
that reject dynamic/unbounded records, missing/duplicate/wrong functions,
unaligned frames, object drift and archive drift even with identical objects.
These explicit fixtures are not native execution evidence.

## Remaining Stack Gate

Account for actual original/assembly frames and all other linked components,
resolve the allowed indirect-reader/callback targets and active recursion,
bound complete permitted call chains and IRQ nesting, and validate actual
per-hart stack placement/exclusion before claiming stack containment. Current
normal archive and exact component frame measurements are inputs to that work,
not substitutes for it. Remaining PCIe/INODE/IRQ/worker/lifecycle/physical gates
and the full NPU objective remain open.
