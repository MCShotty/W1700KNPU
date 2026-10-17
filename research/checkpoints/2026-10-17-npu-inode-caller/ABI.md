# INODE Callback ABI Boundaries

## Terminal Evidence

Both frozen600055c cold callers ended exit1 `INODE-entry-ABI`,before the first
callback instruction. Each completed all three PCIe tail stages with the exact
nine original stores,owner/SETUP and protected-memory projections. Each captured
a real INODE stage0 prefix;neither produced stage1 or overall caller success.
These failures remain failures,not repaired executions.

Strict restored-prefix stopping probes on both profiles show s0-s3 differ from
outer-dispatch entry,with GP/TP and interrupt CSRs unchanged. The INODE owner
is untouched. The old observer compared two different procedure-entry states.
A callee preserves its own incoming saved registers;its caller can use those
registers internally while preserving its own caller's state. See the
[RISC-V calling convention](https://riscv-non-isa.github.io/riscv-elf-psabi-doc/#_procedure_calling_convention).

The new observer captures callback-entry saved registers/SP and actual RA.
A hook at that return-to-caller PC checks them before the outer epilogue can
mask a callback clobber. Fixed GP/TP/interrupt-entry invariants remain. The
separate dispatcher-to-END check still runs before host context restoration.
Nominal/fault receipt contracts require both observations. Original stores,
owners,SETUP,private/protected memory,native guards and budgets are not reduced.
This is an observer/receipt correction,not a firmware implementation.

## Checks And Limits

- 35 focused tests pass. Tiny synthetic RV32 guests demonstrate a legal nested
  caller and a callback clobber hidden by outer epilogue without the new hook.
  The hook rejects it first. Each saved-register/SP/interrupt clobber and
  missing/duplicate records are checked. These are not native INODE runs.
- Broader215 unique units/233 executions pass,with18 explicitly duplicated
  imported fixture tests,no skips. They overlap the focused35,not250 tests.
- Initial35-test expansion had two failures from aliased synthetic entry/return
  lists. Exact72-source failed cohort/log/receipt5a717f68 remain. Independent
  list copies fix the fixture,not a native callback defect.
- Two fresh20-component/168-hook builds retain CODEa6813d39/DATA180bc808 bytes.
  All20 repeat/image groups,60 checked-loader cases/eight mutants,six negative
  native boot controls and12 both-HIF actual-C sender cases pass. Preparation
  receiptd14ff98b binds379 current inputs,not a positive INODE constructor.
- HIF2 restored DESC10 bitmap diagnostic passes unchanged full512/25604 stores/
  3072 packet claims/512 private claims/publications and protected bytes. Native
  budget60M us/host21600s stay unchanged. This is not a repaired old matrix or
  a fresh constructor. Both old matrix failures/missing verdicts stay intact.

Terminal audit SHA256
`76ebb98f5dab2df4f1ee36249cd03ccc5e6772c09e8ca1afb2d9f2fa8d0f9655`
binds934 files and verifies2330 original/eight supplemental read-only source
files unchanged. Its initial audit filename mistake is preserved separately;
no native artifact changed. Focused9e699821 and broader55f98f4b bind the tested
sources. [ABI_BOUNDARIES.json](ABI_BOUNDARIES.json),SHA25688d0191f,has metadata only.

Jev's first boundary-design label is supported0.98/confidence0.97,but later
boundary/proof labels are not-established0.55/0.71 with limited confidence.
History/fixture labels are also uncertain. Raw judgments remain,not a model
approval. Exact source wiring,tiny-guest execution and receipt checks establish
only their stated scope,not original constructor or physical acceptance.

## Continue

Both original all36-tail matrices remain live on unchanged inputs. Fresh both-
HIF corrected/current-source cold/full512/eight-DESC10/all36-tail and actual-
stage1/new24-INODE qualification remain. Do not promote failed callers or
diagnostic-derived states to fresh constructor proof. Check late outer-reader/
transitive-owner liveness before the next long cohort:currently a hypothesis.

Source-lockd6b6e2da,both saved FITs978f9ddd/a22300ea and partial300-node/718-
transfer/six-internal/56-unknown/9696 stack graph stay unchanged. Full setup,
checked IRQ/hot/RRO/lifetime/drain/DMA/cache/recovery,remaining original/indirect/
IRQ/per-hart/physical bounds,actual Gemtek boot and clients remain open.
No hardware,flash,radio/reset,reclaim,job restart,hash waiver or subagents.
