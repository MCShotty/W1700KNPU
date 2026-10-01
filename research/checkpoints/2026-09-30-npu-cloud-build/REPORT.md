# Cloud Build Preparation And Expanded Offline Validation

Completed offline validation on 2026-09-30. The current candidate image builds
and passes exact FIT/board/package/firmware/module checks. It has not been
booted or flashed. This continuation validates the same pre-copy memory-plan
firmware source; host build integration was adapted without changing its pins.

## Final Result

- Candidate sysupgrade FIT: **26,932,042 bytes**, SHA-256
  `6abd366c08b5ad1609c4333cb2c1a9a52a212522a9be0951f71d137f82615c0d`
- Board `gemtek,w1700k-ubi`, compatibility **2.0**, Linux **6.18.52**;
  FIT hashes, NPU reservations, firmware identities, **218 packages** and
  **78 module ABI checks** pass
- **17** retained allocated provider sections in the image match the compiled
  module exactly. Packaging removes only the expected `.note.gnu.build-id`
  metadata section; its removal is specified by `scripts/strip-kmod.sh`
- **1,951** squashfs ownership entries are numeric root/root, as intended by
  this image build. APK completed with zero owner-preservation warnings
- Final actual-C replay again passes **273 loader cases, 165 added load cases,
  three original controls, nine mutants, 6,174 retry cases and 44 V2 cases**;
  eight builder tests, Python compilation and Git whitespace checks pass
- Current reset source has **23,088 modeled-regmap host cases** plus four named
  controls; all **60** locked source files replay; ten RV32 objects compile;
  six selected current-provider functions decompile successfully in Ghidra

Receipts: `final-validation.json`, `image-verification.json`,
`image-code-and-ownership.json`, `cloud-world-fourth.json` and
`final-cold-memory.json`. The full setup/build history below retains failures
and resolved blockers; its earlier pending statements describe those stages,
not the final status. Earlier reviewed document snapshots remain preserved.

Physical boot validation is now the next acceptance gate for this candidate.
Follow `PHYSICAL_BOOT_HANDOFF.md`: verify the actual current device/layout,
working serial recovery and known-good rollback, then obtain separate explicit
boot/flash authorization. Compatibility/layout mismatch is a stop, not license
to force or change the chainloader. No initramfs image was built; the sysupgrade
FIT is not a validated RAM-boot input. Reset/drain/rearm stress remains blocked
on physical engine-ownership and retention contracts. Full NPU parity is still
incomplete. No TypeSafe/Jev probability is fabricated or claimed.

## Preserved Checkpoint

The 47,503-byte `W1700K-NPU-cold-memory-checkpoint-20260930.zip` is retained in
the user's Library, SHA256
`d330635610ba3bd07a29245c7d738b4b83c0accffed95ec5b70d058e38a2b4d1`.
Its complete patch applies to clean base `59e75a8`; all 29 resulting files and
their modes match the checkpoint source. It contains no credentials, protected
device backups, generated binaries or build caches. This preserves the preceding
checkpoint before the additional source preparation below.

## New Passing Evidence

1. `tools/prepare_build.py` fetched the exact OpenW1700k base and all five feed
   pins from `firmware/source-lock.json` into `.build/merged-openwrt`. A separate
   clean-worktree run of `tests/test_prepared_sources.py` passes **all 60 locked
   OpenWrt/LuCI files**, including SHA256 and mode checks. Receipt:
   `source-replay.json`, SHA256
   `d4081195bea02c583759a76212bd91822d7fe02461e822f81bab3bce4e517ad9`
2. The 154,741,268-byte official Linux 6.18.52 source archive was downloaded
   and matches the pinned OpenWrt kernel-version file's SHA256:
   `2b69564f7d4fea0c859b1959ba33709ee6e9139bd100e30a853b57159a8221b8`
3. Current clock/reset source reconstructs from that archive, 13 byte-verified
   pinned upstream patches and the source-lock-verified integrated overlay.
   All 56 EN7581 map entries parse, and the 11 relevant NPU/DMA/FE mappings match
   the earlier engine inventory exactly. This closes its **current-source map
   verification gap**, not runtime consumer binding or physical reset coverage.
   Receipt: `reset-map.json`, SHA256
   `6edacccd853ac24545778e999f0ac14fb8571caac3afe4d0f27136d060733af5`
4. The current extracted reset callbacks pass the unchanged existing actual-C
   GCC 14.2 ASan/UBSan harness: **23,088 cases over 147 reset mappings** across
   three variants, comprising 19,992 nominal cases, 1,764 write faults with
   modeled side effects, 1,323 read faults and nine invalid translations. Four
   corrected named controls also pass. EN7523/AN7583 bindings reconstruct with
   two byte-verified upstream patches. No new mutants or target objects are
   claimed. Receipt: `reset-host.json`, SHA256
   `e06614f516e235d90cb282417402c1857f62c4186e3507e5bf948fe91530972c`

The reset harness uses explicit regmap models. LeakSanitizer is disabled because
its tracing-dependent check fails in this environment; ASan/UBSan are active.
These checks add no containment, bus drain, reclaim or rearm authority. The
pre-copy memory source and source-lock hashes remain unchanged from the preceding
checkpoint. No restricted INODE/provider-framing or DESC5-8 operation ran.

## Initial Build Blocker (Resolved By Workspace Tooling)

The preparer reaches OpenWrt's real prerequisite checks. Native filesystem,
case sensitivity, GCC/G++, make, Perl and Python pass; `make defconfig` stops on
missing **ncurses headers/library, rsync and GNU awk**. No FORCE override is used.
The pinned check is `.build/merged-openwrt/include/prereq-build.mk`.

At that initial stop, installation approval was requested for cloud-only Debian
packages: clang, flex, bison, gawk, rsync, libncurses-dev, libelf-dev, python3-dev,
swig, gettext, bc, cpio and shellcheck, plus their required dependencies. The
repository also pins unicorn 2.1.4 and pyelftools 0.32 for a workspace-only
Python environment. No installation had occurred at that initial stop. The
unprivileged APT metadata read reports a permission error; any later elevation
must use the supported tool approval, without bypassing the denied read or
changing repository/security settings.

The preserved prepare log is `.local/cloud-build-access/prepare.log`.
`setup-state.json` records the latest tooling, capacity and build state.

## Reproducible Resume

Do not rerun the preparer over an existing destination. Its pinned fetch and
apply phases passed. After dependencies are available, resume the remaining
operations inside `.build/merged-openwrt`: index the existing feeds with
`./scripts/feeds update -i`, install them with `./scripts/feeds install -a`, copy
the canonical `firmware/build.config` into `.config`, then run `make defconfig`.
Confirm the board, NPU and package selections before proceeding.

Use the repository's `tools/build_firmware.py` with the explicit build
destination and fresh log names. It first builds the ten RV32 component objects
with Clang, then invokes the selected OpenWrt target. Begin with four jobs;
build the pinned host tools/cross-toolchain and target objects before exact
image/module validation. Do not substitute an unrelated toolchain or change
source pins merely to make the build pass.

Initial resources were about 28 GiB free disk, 9.7 GiB RAM without swap and nine
available CPUs; approximately 26.5 GiB remained after source preparation and
replay. OpenWrt documents at least 10–15 GB for a default-package image, while
this custom 218-package build may need more. Check capacity at build-stage
boundaries rather than deleting unique/protected inputs. [OpenWrt build-system
essentials](https://openwrt.org/docs/guide-developer/toolchain/buildsystem_essentials)

The previous executor measured about 20 minutes for toolchain/install and
40 minutes for a subsequent world stage at eight jobs. Those retained receipts
are historical observations, not a cloud ETA.

No new full AArch64 provider object, module link, image, flash or router change
exists yet. Subsequent RV32 component compilation is recorded below.
The physical handoff prerequisites in the preceding engine-ownership matrix
remain open apart from the explicitly closed current-source map comparison.

## Approved Workspace Tooling Continuation

The user approved cloud-only software installation. APT still fails through the
supported elevation route: its configured retry file is unreadable and its list
state directory is unavailable. No APT configuration, permissions or host
packages were changed. The allowed independent route installs official tools
inside the writable workspace, with explicit provenance:

- Ghidra **12.1.2**, matching the repository's prior analysis version, and
  Temurin JDK **21.0.12.1+1** have official archive SHA-256 checks. Both a fresh
  synthetic headless run and its reproduction pass, including the repository's
  existing Java export script and two successful decompilations. This is tooling
  readiness only; no private or target firmware was imported.
- Official LLVM **22.1.3** matches the pinned OpenWrt LLVM version. The
  1,939,973,900-byte archive matches its official release digest; a selected
  785,846,010-byte subset supplies Clang, LLD, object tools and runtimes without
  unpacking the full 12 GB distribution. Host ASan/UBSan and RISC-V/AArch64 object
  smoke checks pass. LeakSanitizer remains disabled and is not a passing claim.
- GNU awk **5.4.0**, static ncurses **6.6**, and rsync **3.5.1** build from
  signature-verified official source releases. Host-only gcc/g++ wrappers add
  ncurses include/library paths; global target compiler paths are not polluted.
- Unicorn **2.1.4** and pyelftools **0.32** are installed in a project-local
  Python environment, with wheel hashes checked against official PyPI metadata.
  A synthetic AArch64 instruction smoke passes. A separate local environment
  adds setuptools **84.0.0**, matching the pinned feed version, to the existing
  native Python 3.13 without changing host site-packages.
- `tools/build_firmware.py --host-tools PREFIX` explicitly selects repeatable
  workspace tool prefixes. The default fixed PATH remains unchanged. Eight
  focused tests pass, including both build stages, ordering, path rejection and
  provenance after an OpenWrt failure. No ambient PATH is inherited.

The real host prerequisite checks now pass without a prerequisite override.
Feed indexing/install and defconfig exit zero, and `.config` is byte-identical
to canonical `firmware/build.config` (SHA-256
`b15966e2f04ee6a54e9344e08c049d201d3c38dcc1df88593fadd92971be6ec6`).
Defconfig retains upstream recursive-dependency diagnostics in unselected
librespeed/squeezelite packages; the log is **not clean** and those diagnostics
are not hidden. The requested board and NPU selections are verified.

All **ten current RV32 component objects** compile, verify as ELF32 RISC-V with
nonempty text, and form archive SHA-256
`2763ff7289fdc50e3d8a98efae5edf55c8b3a9fad2fc335ce46ed9657d31c3a2`.
This is not a bootable NPU loader or physical execution claim. The first real
OpenWrt tools stage stopped at package prerequisites for SWIG and native-Python
setuptools. Setuptools is supplied as above; official-source SWIG 4.5.1 also passes
version and synthetic wrapper-generation smoke, and an incremental four-job
retry is running. SWIG archive provenance is retained, but an independently
published vendor SHA-256 was unavailable and is not claimed. No target provider/module/image
is complete yet. For the active OpenWrt phase, a workspace disk guard requests normal
build termination if free space falls below 3 GiB, preserving inputs for a
capacity decision. It is not a whole-builder termination guarantee: the
initial synchronous RV32 make runs before the builder installs its signal
forwarder. Those ten small objects have already completed with ample space.

Complete current setup logs/receipts are under `.local/cloud-build-access/`;
subsequent build results will extend this status. No hardware or publication
operation has occurred.

## Later Build Status: Host Tools And Cross-Toolchain Passed

The complete pinned `tools/install` stage passed in 1,296.76 seconds at four
jobs. The pinned AArch64 GCC 14.4.0/musl `toolchain/install` stage then passed in
1,015.86 seconds. These are measured stage times on this cloud run, not an
estimate for the remaining image build. Receipts are `host-tools-build.json`
and `cross-toolchain-build.json`, binding successful exit states and full logs.
The logs retain upstream nonfatal cleanup/probe diagnostics; zero exit status
is not represented as a warning-free build.

The full `world` target is now running at four jobs. About 16 GiB disk space
and 8.3 GiB available memory remained at the cross-toolchain boundary. Its
active OpenWrt phase is covered by the documented free-space guard. Kernel,
provider/driver modules and exact image verification remain pending.

Offline inspection tools are ready separately: pinned DTC 1.8.1 built against
static libfdt, plus the just-built U-Boot dumpimage and unsquashfs tools. A
synthetic DTB readback, FIT extraction and squashfs extraction all round-trip
exactly. This additional prefix is used only for inspection; it is not prepended
to the firmware build. `image-tooling.json` records source/archive/tool hashes
and retained setup failures. The tests do not certify the eventual image.

The earlier tooling readback covers its timestamped setup snapshot. The exact
reviewed report is retained in `.local/cloud-build-access/review-tooling/`;
this later section adds build outcomes without expanding that review's scope.

## Kernel/Provider Link Passed; Host Ncurses Conflict Corrected

The first `world` attempt completed Linux 6.18.52 target compilation and linked
the current NPU provider as an AArch64 module. Its actual prepared provider,
public header and clock/reset source match the canonical reconstruction hashes.
`provider-kernel-build.json` records the object/module, generated configuration,
Module.symvers and kernel Image. Provider module SHA-256:
`cee6f7735f0a0603c26be90f5f35af2e52143438d634ff3df112aeaf30f4ed20`.
The existing nonfatal modpost warning for missing MODULE_DESCRIPTION remains
visible. This is a compilation/link result, not a module-load or hardware test.

The full first world attempt still **failed** later: a leading fallback include
path in the workspace host wrapper shadowed the package's own newer ncurses
headers. Original wrappers and that generated failed package tree are preserved.
The new immutable `host-wrappers-v2` prefix makes fallback headers `-idirafter`
and puts fallback library search after explicit caller paths. Original wrappers
fail both header/library precedence controls; v2 passes. The real host ncurses
package is rebuilt with this corrected environment before the world retry.
No canonical firmware source, target compiler or build configuration was
changed to resolve this setup issue. Exact image verification remains pending.

## Historical Storage-Guard Stop (Later Resolved)

The second world attempt was stopped by the active OpenWrt disk guard below
3 GiB free. The builder records child exit `-15` (SIGTERM); the shell wrapper
records 241. This is a guarded interruption, not a passing world build.
Completed kernel/provider, host-tool and cross-toolchain outputs and incremental
package state are retained. The normal mt76 mirror download also logged cache
misses before termination; its configured source fallback has not yet been
allowed to finish. No source pin is being changed to work around that.

Deletion approval has been requested for exactly three newly downloaded public
tool archives (LLVM, Ghidra and Temurin), totaling 2,720,251,113 bytes. Their
installed tools and exact recovery URLs/hashes are preserved. **No deletion has
occurred; the build is paused awaiting that capacity decision.** User inputs,
source, reports, logs, protected backups and installed tools remain intact.
The image/FIT/package/module checks are still pending. No physical test is
requested from this interrupted image state.

## Approved Archive Cleanup And Resumption

The user approved deletion of the three named downloaded archives. Each exact
file was checked against its expected hash before deletion; only those files
were removed, totaling **2,720,251,113 bytes**. Recovery URLs and digests remain
in `approved-archive-cleanup.json`. Installed Clang, Ghidra metadata and Java
executable fingerprints are unchanged. Free space rose from 3,168,026,624 to
5,888,294,912 bytes. These historical download archives are therefore no longer
available for immediate local readback; restore from the recorded sources when
needed. The earlier installation/readback receipts retain their original scope.

The third guarded four-job world attempt is now running from the preserved
incremental state. No source, user input, installed tool or signing key was
deleted, and no pin/configuration change was made. Exact image verification
and all hardware gates remain pending.

## Packaging Compatibility Retry

The third world attempt compiled all target packages, including mt76/MT7996,
but failed at APK rootfs installation with ownership-preservation diagnostics.
It is retained as a failed attempt. The pinned fakeroot library's built-in
simulation-only option was inspected against its original source and tested
on four fresh fixtures. Simulated owner/group metadata survives for files and
symlinks while a sentinel proves no real ownership call is attempted. Actual
host owners remain unchanged. `fakeroot-compatibility.json` records the bounded
checks, including the untraced prior host-errno limitation.

The fourth world attempt uses `FAKEROOTDONTTRYCHOWN=1` for that supported
packaging simulation. No APK ownership check, target permission, source pin,
OS security setting or host ownership is changed. Its full integration result
and exact image verification are still pending.

## Final Integration Outcome

The fourth world attempt passed with the documented upstream fakeroot
simulation-only flag. All 218 packages installed with no owner-preservation
warning, and the exact image then passed `tools/verify_merged_image.py`.
The provider binary-section and squashfs numeric-owner readbacks passed after
that. The fuller retained module's build-ID note is intentionally stripped by
the pinned OpenWrt packaging recipe; no executable/data section difference was
ignored. Source-lock and canonical NPU patch fingerprints remain unchanged.
The final host replay also passes against those same canonical bytes.

No new physical acceptance follows from these results. The supplied legacy NPU
firmware stays in use; the RV32 component archive is not a bootable replacement.
Only the user-approved three recoverable tool archives were deleted. Installed
tools, original inputs, protected releases, source and build logs are retained.
The guarded attempts and their failures are separate receipts, never folded
into the successful run. See the handoff for exact physical prerequisites.
