# Bounded Independent Wi-Fi Review

Date: 2026-09-06. Starting and observed HEAD:
`666b63245d3c13921cb4cdedeef4d7e3f418bd1e`.

Scope: only today's two regulatory decimal regex replacements, hostapd empty
interface-dump handling, LuCI NO_IR casing and runtime channel-shape helper.
Read AGENTS.md, scoped cumulative diffs, prepared functions, the three named
test files, current Wi-Fi receipts and the target-build nl80211 implementation.
Parent retains ownership of all production edits and trackers.

## Finding

### [P2] Null plus no error does not prove an empty interface dump

Changed location: `firmware/patches/openwrt.patch:1540-1543`, corresponding to
prepared `package/network/services/hostapd/files/hostapd.uc:1411-1414`.

The newly accepted null/no-error result also occurs when native interface
attribute decoding fails for every returned record, for example a singleton
interface reply whose decoder allocation fails. The old array-only check
rejected this result; the new check normalizes it to an empty list and proceeds
without the global live-address reservations.

Static path in `.build/openwrt/build_dir/target-aarch64_cortex-a53_musl/ucode-2026.07.09~b885dd0f/lib/nl80211.c`:

- Lines 1256-1259: `uc_nl_convert_attrs()` returns false on `calloc()` failure
  without setting the module's error state.
- Lines 2256-2305: `cb_reply()` discards an unsuccessful conversion, leaves
  `res` unset, and marks the request continuing.
- Lines 2188-2194 and 2775: the zero-initialized request reaches REPLIED on
  multipart completion; completion does not set an error.
- Lines 2865-2867: the completed request returns the still-null `st.res`.

The subsequent `phydev.macaddr_init()` is not an equivalent global safeguard:
`package/network/config/wifi-scripts/files/usr/share/hostap/common.uc:325-339`
enumerates one PHY and filters by the anchor radio mask. External interfaces
on another radio/PHY can remain unreserved. This is a conditional low-memory
regression, not a reproduced live collision or explanation of client failures.

Action: propagate decoder allocation/conversion failure through the native
error channel before relying on null/no-error as evidence of successful empty
enumeration, or obtain another authoritative completeness check. Add a native
decoder-failure negative test with an existing interface outside the anchor
radio. `test_mld_enumeration.py` models return values and currently treats
null/no-error solely as empty success, so its 19 cases cannot distinguish this
path. Limit claims about successful enumeration accordingly until closed.

## Other Results And Limits

- No other actionable introduced regression found in the three remaining
  corrections. Integer/decimal regex anchoring, case normalization, static
  fallbacks, radio mapping and width-subchannel consumers remain consistent
  with their scoped tests. Existing widget/MLO NO_IR predicate differences
  are explicitly documented and are not a new finding.
- All three prepared-source SHA256 values match the changed entries read
  from `firmware/source-lock.json`. Target nl80211.c SHA256:
  `9deca47fdd30853b676c97bb89bbca951ea9bf4ecccb781ec3fab682a44ad2bf`.
- The reported 80 shell / 19 ucode / 11 JS passes and 29 live configurations
  plus six unchanged reload stages were not independently rerun. Reported
  daemon configuration/width checks are not client authentication or traffic
  proof; authenticated live LuCI and changed-configuration transitions remain
  unverified, as the parent's report states.
- No router, remote, browser, build, image/flash, NPU action, restriction retry,
  commit or fork. This report is the only file written. Source, patches, lock,
  tests and all trackers, including the ledger, were left unchanged.

## Closure Verification - 2026-09-06

Status: **P2 CLOSED** for the reported decoder-allocation/MLD-guard defect.
No concrete closure gap found. This section supersedes the open status above;
the original finding is retained as history.

- Patch 112 sets `NLE_NOMEM` before the decoder returns false. The overlay and
  prepared package patch are byte-identical, SHA256
  `cde7d970a40624d2a0567b516588dab0f7ce5b5b4310c6bc9994be4e81706f39`.
  Actual target-build nl80211.c matches the harness's corrected full source,
  SHA256 `e6132b4ecf341908fab157ac98fbd30a7715241373c78d0ec896539cc5eb59f0`.
- Error state is sticky across later successful record decoding and dump
  completion. Neither `cb_reply()` success nor `cb_done()` clears it, and the
  successful request return preserves it. `uc_nl_error()` returns the error
  string and then clears the code. The host guard reads that error before
  accepting any result, rejecting both null/error and partial-array/error;
  genuine empty/null/no-error remains accepted.
- Inspected the full-source C harness and both six-case native receipts.
  The one local calloc callsite is faulted; per-case allocation counts verify
  the intended footprint. Original single/first/last OOM cases hide errors;
  all three corrected cases retain code 5 / `Out of memory` through completion
  and clear it through the real error API. First-then-success and
  success-then-last-failure cases establish both relevant record orderings.
- Independently hashed the harness, original/corrected source files and both
  local ARM64 executables: they match `decoder-build.json` and the binary
  identities in `decoder-runtime.json`. The latter's SHA256 matches the
  receipt consumed by the updated host-guard test.
- The updated test consumes actual native result/error values, including the
  synthetic external PHY42 address. Its inspected receipt records 25 passes,
  nine old-hostapd failures and three killed mutants. Pairing the current
  host guard with the original decoder outputs reproduces exactly the three
  OOM failures, demonstrating the companion patch is required.
- `PKG_RELEASE:=2`, its cumulative Makefile hunk, and the two new lock entries
  match prepared files. The export receipt records 38 OpenWrt / 3 LuCI files
  verified; full reconstruction was not rerun by this reviewer.

Verification was read-only source/receipt inspection and local hashing, not a
new native execution, build or deployment check. Parent-reported installation,
wpad readiness and ongoing seven-case post-decoder AP/MLO matrix were not
independently checked and are not counted as completed here. No router,
netlink request, browser, NPU, image/flash, commit or fork operation occurred.
Only this closure section was appended; source, tests, patches, lock and
trackers, including the ledger, remain untouched by this review.
