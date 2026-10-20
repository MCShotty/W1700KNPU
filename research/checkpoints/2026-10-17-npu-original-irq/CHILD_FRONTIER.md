# Original Child Frontier

Follow-up: [finite whole-routine execution](MEMSET_EXECUTION.md) covers4992
original memory-routine cases;the static denied contracts here remain denied.

2026-10-20.64 original routines are byte-bound to current CODE658c9c32;
62 pass conditional local-body checks and two remain denied. This selected
corpus is not the complete NPU graph, a whole-chain/IRQ/per-hart/physical
stack bound, successful constructor or hardware acceptance.

## Checked Change

The explicit guard-set profile now admits at most two pure ADDI/XOR setup
instructions before the unsigned guard. They cannot write the bound, index,
table base, zero, RA or SP. The separately checked single index bias remains.
No arbitrary instruction, load, store, call or third setup is skipped. Actual
guard constants, safe-entry predecessors, protected-prefix uniqueness/cutset
and table-target checks remain. The strict default still rejects this new
shape; the previous31 absolute/22 relative/31 guard-set fixtures are unchanged.

Original `0x84017ce8` now qualifies its1084-byte local body and48-byte local
frame with bound14,15 entries and the two verified setup instructions. Its
children remain separate costs.13 new compiled fixtures,18 synthetic prefix
guests and17 exact original isolated-prefix guests pass. Full GPR/PC/MSTATUS,
ordered reads/no writes and whole protected bytes match before restoration.
Registers and permissions are synthetic; original guests stop before cases,
not at a complete original function/constructor result.

All275 unique units / 293 executions pass without skips, including the prior
full selection. Older runs overlap and are not added. Ghidra12.1.2 ran
read-only/no-analysis on the existing older a681 CODE project:28 exact entry
inventories,28 child exports,then six and one further exports. Every selected
range and instruction is checked against original/current bytes independently.
The reusable entry inventory tool is byte-identical to the executed script;
an exact Ghidra entry alone grants no ABI/frame/target permission.

## Still Denied

- `0x84017086`:116 bytes; local analysis rejects unsupported control flow.
  ECALLs at `0x840170a8` and `0x840170ce` use `a7=0xd6`. The installed Linux
  generic UAPI header defines `__NR_brk=214`, but that match does not establish
  the NPU's handler, privilege mode, syscall ABI, return preservation or an
  equivalent replacement. Its error child `0x840170fa` remains unreviewed.
- `0x840103aa`:Ghidra reports two ranges totaling106 bytes,
  `0x840103aa..0x840103e3` and `0x84010422..0x84010451`, with62 intervening
  bytes outside that recovered body. Local analysis rejects this noncontiguous
  extent. Computed sites `0x840103e0` (`jalr zero,a3,0xa`) and `0x84010440`
  (`jalr ra,a3,-0x58`) retain unproved nonlinking/linking entry contracts.
  Those ranges are never concatenated into a fabricated contiguous function.

The qualified callers have two blocked child sites. An empty pending list of
other named targets is not closure: denied bodies' outgoing paths, computed
entries and ECALL/error handling remain open. No complete original routine or
child ran as part of these new prefix checks. Ordinary ABI, immutable-code
snapshots and no asynchronous mutation remain assumptions. The older global
300/718/six/56/9696 graph is neither extended nor requalified here.

## Evidence

Metadata-only `CHILD_FRONTIER.json` hashes
`692ed5390ac786f1830f2626aeb6003f3527d1120bb075336379a1cef852d23b`.
Private scope `7c245788999a3645baa7b3a25235e7b1ce9b5a78e9574974a0d8c2445b584a6d`
verifies2589 paths and2385 readonly pre-edit files. Exact historical source
bindings retain the former unrecognized-prefix denial. The initial single-body
assumption abort and evidence-output name collision remain with their sources;
the protected older receipt3f22a3bd is unchanged, not overwritten.

Jev checks report bounded setup0.92/explicit activation0.88; they are not
proofs. ECALL role is `unknown`0.99/confidence0.99, not a confirmed heap-growth
implementation. NPU ABI/replacement equivalence is not-established0.92/
confidence0.88. No ECALL is admitted as ordinary fallthrough or rewritten.

Source-lockd6b6e2da, raw658c9c32/3d821c93 and all three saved FIT hashes
978f9ddd/a22300ea/633b4d71 reverify unchanged. The633b image still predates
the INODE optimization. Native budgets/checkpoints, hardware and subagents
are unchanged. Normal INODE2522/326 remains passed; actual both-HIF cold
callers/frozen fault matrices and full setup/latest image/hot/checked IRQ/RRO/
lifecycle/DMA/cache/recovery/real Gemtek boot/radios/clients/performance gates
remain. Next original work is the two denied entry/trap contracts, not a waiver.
