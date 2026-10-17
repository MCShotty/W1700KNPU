# Defined IRQ Status Error Output

## Fix And Remaining Boundary

The actual provider status getter declared an uninitialized `val`,ignored the
`regmap_read` result,and returned the local value. Host MemorySanitizer reproduced
the uninitialized return when an explicit regmap fixture returned an error
without supplying output. The getter now initializes `val` and returns0 on any
read error. A partial-output error also returns0. No ABI changed.

This fixes the value path only. Zero status is not an error channel,physical
containment or drain witness. Actual handlers still schedule NAPI after errors;
bulk disable still has no error return. Read/ack/mask/enable,initial/atomic hot
rearm,exact completed setup/session/lifetime gates,possible effects/readback/
partial failures and quarantine must be handled together. Kernel concurrency,
physical routing,worker/drain/reset/removal/recovery and clients remain open.
No router or physical bus fault was exercised.

## Evidence

| Receipt | SHA256 | Scope |
| --- | --- | --- |
| `.local/npu-irq-status-msan/status-output-q2/result.json` | `c285f1b36ead59d4231407e9f9fcac6594023d080687682c9782c36ce6d3bdc7` | Corrected success/error clean under host MSan;exact preserved legacy error still detected |
| `.local/npu-irq-ack-mask-contract/read-ack-mask-q4/result.json` | `d68f802c1d30e51fba4c20d7adbd1efaad411c565d0b9357bc2bfd1e933d1bbf` | 150 actual handler/5625 bulk/three null modeled cases under address/undefined/leak sanitizers |
| `.local/npu-irq-status-20261017/provider-object-q1/result.json` | `a277372bbca56c56ffff5fd011357df26ff142ca88eb4c2ea82cb776ced0b0db` | Isolated current AArch64 provider:getter32/cold544-byte static frames |
| `.local/npu-irq-status-20261017/kernel-patch-q2.json` | `b9eca0977e0dc54341e4b21e2bf950342d13753157c2ec2727bac27b503e4b5c` | Zero-fuzz exported kernel patch;all five resulting files match merged reference |
| `.local/npu-irq-status-20261017/scope-q1.json` | `3f61aa3263dda4219f7d490763afab616800a756a2c8a15266535104aa2f2d17` | 274 exact hashes/210 unique units/228 executions;current host/RCU regressions/export scope |

The read/ack/mask fixture compiles exact provider functions,compatibility
wrappers,queue enum,hard IRQ handler and bulk caller. RCU,NAPI,register effects
and errors are modeled. All read errors explicitly provide an output here;
the separate MSan fixture covers the no-output error. Read errors now ack0.
Nevertheless148 handler error cases still schedule NAPI,and5624 bulk-error
cases cannot propagate an error. Successful reads pass the full shared status
word to ack. This does not establish physical lost interrupts or client loss.

Fresh provider609/nine mutants and RCU21 startup/31 poll/five compiled mutants
pass on current C. Existing12 startup/eight hot IRQ-enable errors remain lost.
Passing characterization preserves these faults as requirements,not fixes.

## Preserved Evidence And Source Closure

Before editing the getter,the legacy producing cohort was preserved:2245
files/520729699 bytes,receipt
`5c38698e987172c7f13aaa237db83eadcd0922335d0c026cfa785e17fcd5239c`.
That is preservation only,not full original-path replay. The old getter is
separately compiled as the MSan negative. Its original MSan26f0510a and legacy
read/ack/mask1b3d3165 receipts are not promoted to the corrected source.

Initial read/ack/maskq1 stopped before execution because its extraction helper
did not support `irqreturn_t`;the existing lifetime extractor is used instead.
Q2 stopped at unused-parameter compile warnings. The host fixture now uses the
normal kernel unused-parameter policy while retaining other warnings-as-errors
and all sanitizers. Both failed attempts/drivers remain intact. No original
production C was edited to satisfy extraction. Legacyq3/correctedq4 are distinct.

Source export verifies70 OpenWrt/five LuCI files and22 component sources. The
kernel patch applies with zero fuzz and all five manifest-selected files match
the edited reference. Initial verifierq1 wrongly expected four files;it remains
failed. Q2 derives the full set from the merge manifest plus Makefile,including
Kconfig. Integrated kernel patch SHA256
`ebc830d8caaa56189da898df59d922e77c78c589e93d611e528aa1ee7d635098`;
current source-lock SHA256
`f9f90ba521cba96360784d53b265a6c4281d28ec84808671d662639893a0152c`.

The isolated provider compile preceded that intentional source export. Its
guard-only0705 source-lock is preserved in the earlier legacy copy;it was not
an input to GCC. Current seal binds the newf9f9 source-lock and both proof scopes
explicitly,without treating changed metadata as identical. Nine prepared
source/object/module/FIT identities stay unchanged;no module/world/image rebuild
or flash. FIT978f9ddd remains unchanged.

## Native Runs Stay Separate

Live-view receipt
`aeed28bba420c334daab2676362375ea9559e636959a721ef45de3bc1d958465`
verifies all2330 original files/five supplemental consumers and both actual
process views still match600055c after main's provider/source-lock changes.
Both nominal callers and both eight-DESC10-fault matrices remain live. Six
individual faults/profile pass;two readiness cases/profile remain. No terminal
native constructor verdict or qualification of newer main. All36 tail/new24
INODE faults and broader native regression remain required. No source-hash
waiver,fabricated SETUP,job restart,hardware or subagents.
