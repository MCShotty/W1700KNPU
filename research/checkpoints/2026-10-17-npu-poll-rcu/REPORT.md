# Explicit Poll Provider Lifetime Scope

## Change And Boundary

`mt76_dma_rx_poll` drops its explicit RCU read lock before invoking the driver's
poll completion callback. The MT7996 NPU branch previously dereferenced and
used the provider without its own explicit bracket. It now calls `rcu_read_lock`
before the lookup and `rcu_read_unlock` after provider use,including the null
case. Ordinary IRQ queues are unchanged. `mt76_npu_deinit` clears the published
pointer and waits through `synchronize_rcu` before dropping the provider reference.

This makes the callback's read-side scope explicit rather than relying on an
outer/implicit softirq context. No physical use-after-free was reproduced.
Modeled brackets/ordering are not actual kernel concurrency or DMA lifetime
acceptance. The provider's void IRQ ABI still loses12 startup/eight hot modeled
errors. Completed cold/session/lifetime gates,checked initial/atomic hot rearm,
possible-effects/readback/partial-failure quarantine,worker/drain/reset/removal/
recovery and actual-client scope remain open. No sleeping RPC/mutex was added
to the poll body and no hardware action was performed.

## Exact-C And Compile Evidence

The extended actual-C fixture fails against the preserved old poll body at
`poll-read-without-RCU`. That failing run remains in `rcu-before-q1`;it is not
relabeled as passing. The corrected body passes21 startup and31 poll cases,
keeping all earlier register errors/partial effects/null/ordinary routing cases.
Five compiled mutants must abort at their intended boundary:missing begin,
missing end,end before dereference,end before provider,and ordinary-scope bleed.
All compile and fail at the expected assertion under address/undefined/leak
sanitizers. RCU,initializer stages,regmap errors/effects and ordinary IRQ masks
remain explicit fixtures.

Actual receipt `.local/npu-final-irq-contract/rcu-after-q1/result.json`,SHA256
`d90a28e372878a2f8d5a27501a4dbbb76bd91db41099f29e5d43bc62f0f29569`.

Two isolated full `mt7996/mmio.c` AArch64 objects use the current source tree,
pinned6.18.52 headers and GCC14.4. Both have32-byte poll frames. NPU-on retains
the saved compile configuration;NPU-off explicitly undefines the four NPU
macros after forced includes. That is a preprocessor fixture,not an alternate
full kernel configuration/world or module relink. Receipt
`.local/npu-poll-rcu-20261017/objects-q1.json`,SHA256
`38263c5f8422a063ec639102bb27ab5b02f01d79082449bee438fbee08029820`.
Eight prepared kernel/mt76 source/object/module/FIT hashes are unchanged.
FIT978f9ddd remains unchanged and unflashed.

## Source Closure

The first exportq1 did not include the changed file:the mt76 export allowlist
omitted `mt7996/mmio.c`,which was unchanged from upstream before this fix.
Source-lock stayed008c428e. Q1's successful generic source-closure check is not
proof that it exported the fix;its files/receipt remain intact.

The exporter now explicitly includes that one file. Correctedq2 applies the
entire tracked integrated mt76 patch with zero fuzz to an isolated upstream
copy,then compares all10 changed files byte-for-byte to the current merged
reference. Source closure verifies70 OpenWrt/five LuCI files and22 component
sources,while all eight protected prepared identities stay unchanged.

- Integrated patch SHA256
  `624e2831f6b502c14d975b97f588a37e9195ae538357f87dae9d901ace704c69`.
- Source-lock SHA256
  `0705aea884e103ef5f4d7c8e226c1ac87777111cbfb521f52c654fb0d6844c0f`.
- Export/application scope receipt SHA256
  `06a7fb4859f815e9e3f8a11c3e477e2207fcd6a2c82eeed9124f4fd0ffde1b5f`.

Two regression units require the explicit extra export path and its locked
patch section. The initial unit incorrectly assumed git-style headers;the
exporter emits unified headers. The corrected parser/checks pass. Nested patch
context lines necessarily retain leading context spaces/tabs and blank lines;
non-patch diff whitespace is clean and the real zero-fuzz application/source
comparison is the patch check. No guest guard,size,source hash or test gate was
waived to obtain these results.

## Scoped Seal And Live Isolation

`.local/npu-poll-rcu-20261017/scope-q1.json`,SHA256
`f2a4c15c7af1e6997f25e9ce74eaf0b5024682cd2e027603167129a972c8603e`,
verifies496 exact hashes and210 unique tests/228 executions,no skips. The18
preexisting imported fixture cases still execute twice. This seal covers CPU
models,source/object/export/unit scope only;all native/complete IRQ/kernel
concurrency/physical/full-setup flags remain false. Jev's six narrow source
checks/raw probabilities are retained alongside the deterministic evidence.

The two existing actual cold callers and both eight-case full512 DESC10 fault
matrices remain live on the600055c producing copy. Read-only actual-process view
receipt `.local/npu-poll-rcu-20261017/live-views-q1.json`,SHA256
`d457e4b14de8bc28d5fd3598d5cc27cfdf96fcaef1b4829ac0ba7031ceae8fdc`,
verifies all2330 original files and five explicit diagnostic supplements are
unchanged. Both live namespace views still show their old source-lock/exporter
after main changes. These cold results never qualify the new poll patch.
No source-hash waiver,fabricated earlier SETUP,job restart or subagents.
