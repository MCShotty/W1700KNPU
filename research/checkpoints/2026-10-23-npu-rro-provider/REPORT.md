# Provider-Owned RRO Allocation And Closing Handoff

## Scope

This checkpoint connects the portable RRO journal to actual provider-owned DMA
allocations and process-context mt76 calls. It is not operational checked RRO,
a full joint kernel execution, a new image, or physical retirement acceptance.
The full NPU objective remains active.

## Implementation

- An independently allocated owner belongs to the already retained provider DMA
  lifetime. It stores the immutable provider/endpoint/boot/nonce/epoch plan,
  protected CPU identities, journal, and every attempted CPU/DMA/length slot.
  The provider's existing pinned-reference contract is reused, not replaced by
  opaque identity numbers. Kernel compilation checks its bounded heap size.
- The actual allocator validates the retained TX/RX/mailbox/native/BAR context,
  exact next role/index/length and CPU/DMA overlap. It records backing before
  journal enrollment and only then returns caller outputs. Failures retain the
  complete prefix and nonnull invalid backing; no managed fallback or retry is
  introduced on this owned lane.
- Four optional provider operations and exported mt76 process wrappers implement
  open, allocate, publish and close. The consumer mutex protects provider lookup;
  the provider mutex serializes metadata. Publication records possible exposure
  and its invocation ticket before using the existing checked sender. It never
  bypasses that sender into raw transport.
- The actual initializer selects owned allocation after successful open. Only
  `-EOPNOTSUPP` permits the legacy optional-provider path. Each owned publication
  error returns through the higher initializer before RRO hardware setup.
- Owned RRO free attempts closing and returns before managed frees, even after a
  mode change or provider-pointer loss. Its ownership marker is not cleared.
  Lower mt76 detach also attempts closing before pointer unpublication. Provider
  cleanup retains an attached RRO owner independently of the exposure flag.
- Closing records the journal handoff only. No CPU join, IRQ/DMA/firmware/cache/
  PMA drain observation, free, reset or rearm authority is asserted.

## Executed Validation

Current canonical patches reconstruct with fuzz zero and exact selected-source
hashes. Source lock `975c55055fe246af714e0c72cc96b4bdb9bca4913fc08ee8e35e0f7e8dc5eca4`
and producer `e0ff1a43f31f79bf049cb694ce25b8eda061ec3f4227bebe3c660c9a8cafbcd4`
bind five kernel and 329 mt76 sources, with 24 component mappings. All four
AArch64 modules final-link using GCC 14.4.0 and Linux 6.18.52. Existing modpost
`MODULE_DESCRIPTION` warnings remain warnings, not a clean-warning claim.

- Actual provider, journal and mt76 bridges: 448 ASan/UBSan/leak cases and four
  compiled intended-assertion controls. This includes all 139/139/137 allocation
  profiles, every allocation-failure prefix, invalid CPU/DMA backing, changed
  identities, output preservation, checked rejection and retained cleanup.
- Existing actual-C TX and RX composition: 223 cases/12 controls and 168 cases/
  seven controls, respectively. The extracted locked-validator dependency is
  included in both fixtures.
- Complete selected consumer bodies and mt76 bridges: 1,090 sanitizer cases,
  four teardown controls, one early-TX control and two owned-caller controls.
  Exactly 1,040 cases explicitly model an optional provider returning
  `-EOPNOTSUPP`; they are not current checked-provider admission evidence.
  The other 50 use modeled owned-provider callbacks to test open errors,
  allocation prefixes, publication error propagation and teardown with changed
  mode/provider presence. They do not execute the actual provider jointly.
- Portable journal regression: 5,279 cases/three controls. All 134 emitted frame
  bytes match the independently executed legacy optional-provider callers and
  prior captures. This does not admit those frames through the current gate.
- The normal RV32 archive has 23 exact members and no journal undefined symbols.
  Its bytes match the prior 23-object build. All 116 tooling tests pass, zero
  skips, alongside the source-export and component-header checks.

Low-level DMA allocation/device references/transport/framework and the consumer
suite's provider callbacks are explicit models. Actual host heap bytes are used
for coherent-buffer contents. These are host-C tests and target compilation,
not execution of the new AArch64/RV32 RRO instructions or actual hardware.

The first provider fixture did not define the kernel endian type/conversion and
compared distinct enum types under `-Werror`. Its compile failure is preserved;
only the model was corrected. The first owned-free mutation reached the actual
kernel devres-match assertion earlier than the newly expected model assertion.
That failed diagnostic check and exact generated files are retained. The
expected assertion was corrected; production code was not weakened.

The first seal also rejected the combined runner's RX receipt because that
invocation omitted `--mutants`: its 168 cases passed, but it contained zero
controls. The failed seal and baseline are retained. A separate fresh canonical
RX run executes all seven controls; the seal requires that complete receipt.
The next preflight rejected a mistyped old public digest literal. The preserved
public receipt is now checked against its exact pinned Git-commit bytes; neither
that old receipt nor its private evidence was rewritten.

Baseline runs enable leak checking. The four provider mutation runs intentionally
exit at their assertion before fixture-only disposal, so leak checks are disabled
only for those runs; ASan/UBSan remain enabled. Fixture disposal of retained
objects is not production reclamation.

Jev 1.13 reviewed focused before/after source excerpts using the official
[System One API](https://docs.typesafe.ai/api/system-one). Its owned-free and
non-EOP-fallback answers were uncertain, 0.51 and 0.49. The exact C cases and
compiled controls establish their tested behavior; Jev is advisory, not proof
or action authority. Raw questions, probabilities and usage remain in receipts.

## Still Required

The current checked sender still rejects RRO selectors 0/1/3. Consequently the
owned initializer stops at its first element publication: after two BA buffers
and one element in V3, or one element in either V3.1 profile. Full allocation
geometry was exercised separately without inventing successful publication.
This failure/retention behavior is an intermediate implementation, not the
project's intended final operational state.

Next implement native admission and authenticated completion identity, retained
MCU/reset/work-item generations, CPU join and physical retirement witnesses.
The current ticket binds a host invocation, not an authenticated firmware echo.
Coordinate serial/epoch advancement with late TX validation rather than bypassing
that validator. Complete cold/fault/HIF2, hot ownership, lifecycle and whole-stack
tests, then build and qualify a complete current image and prove physical boot,
radios, actual clients, performance and stability.

No raw pair, UI/radio policy, image, hardware or flash change occurred. Old image
`a3f1d04b` does not contain this callback ABI. The existing compact default replay
continues on its frozen `2f85e54` cohort, not these sources; it was not restarted
or re-scoped. Sealed evidence rehashes its 2,865 inputs, prior receipt generations,
14 protected project image bindings and the external protected object. Historical
mutable names are resolved to captured versions, not claimed to remain current.
