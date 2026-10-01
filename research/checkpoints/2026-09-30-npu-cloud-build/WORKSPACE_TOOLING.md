# Cloud Tooling And Reproducible Build Entry Points

This supplements the canonical source-lock preparation workflow. The existing
checkout is `.build/merged-openwrt`; do not rerun the preparer over it. Runtime
inputs remain pinned in `firmware/source-lock.json`. No host APT/security setting
was changed. Tooling installation approval was received for this cloud work.

## Installed tools and provenance

- `llvm-tooling.json`: official LLVM 22.1.3 asset digest, selected installation,
  and synthetic host/RISC-V/AArch64 checks. Full local manifest and extraction
  script: `.local/cloud-build-access/llvm/`. Only 786 MB of the official 12 GB
  unpacked distribution was selected. Clang resources and sanitizer runtimes
  are retained, together with LLD and required object tools.
- `gnu-tooling.json`: exact official source URLs, signatures, signing-key
  fingerprints, configure arguments, logs and smoke results for GNU awk 5.4.0,
  static ncurses 6.6 and rsync 3.5.1. Their installed paths are under
  `.local/cloud-tools/host`; full evidence is in
  `.local/cloud-build-access/host-prereqs/`. Signer identity is based on the
  official HTTPS release/maintainer sources, not a personal web of trust.
- `swig-tooling.json`: SWIG 4.5.1 from the official project's HTTPS release link,
  with version and synthetic Python wrapper smoke checks. Its archive SHA-256
  is a measured fingerprint. No independently published vendor digest/signature
  was verified because the metadata endpoint returned HTTP 404.
- `python-tooling.json`: exact Unicorn 2.1.4 and pyelftools 0.32 PyPI wheel
  hashes, versions and synthetic emulator smoke. Environment:
  `.local/cloud-tools-venv`, for tests and offline image inspection.
- `python-build-tooling.json`: a separate native Python 3.13 venv with
  setuptools 84.0.0, matching the pinned packages feed version. Host
  site-packages are unchanged; the venv lives in `.local/cloud-build-python313`.
- `ghidra-tooling.json`: official Ghidra 12.1.2 and Temurin JDK 21.0.12.1+1
  digests and repeated synthetic headless export checks. Launcher:
  `.local/cloud-tools/bin/analyzeHeadless`. Full instructions, logs and
  `reproduce-smoke.sh` are in `.local/cloud-build-access/ghidra/`.

The JSON receipts contain exact URLs and checksums to recover an absent tool.
Use fresh download/source/build directories and verify them before extraction
or execution. Run configure/help in the dedicated source-build directory, never
in the repository root: rsync's wrapper creates files before handling `--help`.
Do not overwrite an existing installation, generated project or prior receipt.

## Build environment

`tools/build_firmware.py` accepts repeatable `--host-tools PREFIX`. Each resolved
prefix and its `bin` must exist strictly beneath this repository's `.local` or
`.build`. The option prepends only those bins to the unchanged fixed system
PATH; it does not inherit an ambient PATH. State records the chosen prefixes,
effective PATH and selected make hash. The focused test is:

```sh
python3 tests/test_build_firmware_host_tools.py
```

The cloud uses three prefixes, in this order:

1. `.local/cloud-tools/host-wrappers-v2`: host-only gcc/g++ wrappers adding
   `-idirafter <host>/include`, with `-L<host>/lib` placed after caller
   arguments so package-local include/library paths win, plus a wrapper for native Python 3.13's local
   venv. The `cc`/`c++` aliases select those host wrappers.
2. `.local/cloud-tools/host`: signature-verified GNU prerequisites and the
   separately recorded SWIG installation.
3. `.local/cloud-tools/LLVM-22.1.3-Linux-X64`: official selected LLVM tools.

Do not globally set CPATH, LIBRARY_PATH or LD_LIBRARY_PATH to host libraries in
this cross-build. Target GCC remains the pinned OpenWrt cross-toolchain. Static
ncurses smoke binaries link only libc dynamically.

The feeds were indexed/installed and canonical `firmware/build.config` copied to
`.config`. `make defconfig` returned zero with the config byte-identical. Its
unselected librespeed/squeezelite recursive-dependency diagnostics are recorded
in `configuration.json`; the log is not described as clean. After selecting the
local Python venv, the normal prerequisite target was rerun using Make's `-W
include/prereq-build.mk` dependency refresh. Every real check executed and passed;
no `FORCE=1` prerequisite bypass was used.

## Build stages

From the repository root, use a fresh name for every attempt:

```sh
FAKEROOTDONTTRYCHOWN=1 CURL_OPTIONS='-4 --connect-timeout 15' \
python3 tools/build_firmware.py \
  --destination .build/merged-openwrt --name fresh-tools --jobs 4 \
  --target tools/install \
  --host-tools .local/cloud-tools/host-wrappers-v2 \
  --host-tools .local/cloud-tools/host \
  --host-tools .local/cloud-tools/LLVM-22.1.3-Linux-X64
```

Use the same prefix arguments and fresh names for `toolchain/install`, relevant
target compilation, then `world`. Monitor disk and memory. The current run adds
an ignored wrapper, `.local/cloud-build-access/run-guarded-build.py`, which
executes that builder and sends its normal termination signal if workspace
free space drops below 3 GiB. During the active OpenWrt phase, the builder
forwards the signal to that child process group. This is not whole-builder
termination coverage: its initial synchronous RV32 make precedes the signal
forwarder and could outlive an early stop. Check capacity before launching
fresh RV32 work; the current ten small objects already completed with ample
space. The guard receipt retains samples and stop reasons. It never deletes
inputs or changes source/build configuration.

Logs and terminal build states are in `.local/merge-nonoc-20260923/`. Separate
attempts are retained, including the first real package prerequisite failure
for SWIG and native Python setuptools. Build success must be established from
the final exit state and exact output verification, never merely from an
existing archive or log. The current RV32 archive receipt proves ten compiled
ELF objects only, not a bootable NPU image or execution on hardware.

After `world` succeeds, run the exact image/FIT/board/package/module checks with
the pinned Python environment and the freshly built host tools on PATH. This
must precede any separately authorized serial-backed physical test. No flash
or publication is part of this cloud setup.

## Host Wrapper Precedence Correction

The original host-only wrapper placed fallback ncurses headers/libraries first.
The first `world` run linked the kernel/provider, then its own newer host ncurses
package picked the fallback headers and failed. The original prefix and failed
package tree are preserved. Current `host-wrappers-v2` uses `-idirafter` for
fallback headers and appends fallback `-L` after caller arguments. Two controls
show the original wrapper incorrectly wins over explicit package header/library
paths, while v2 preserves both. The real host ncurses package then rebuilds in
its fresh generated directory. Only host tooling changed; canonical firmware
source, target compiler and configuration were not modified.

`host-wrapper-v2.json` and subsequent build receipts retain these facts. The
initial host-tools/cross-toolchain receipts still name the original immutable
prefix used for those successful stages. Use v2 for current retries.

## Approved Download-Archive Cleanup

After the storage guard paused the second world attempt, the user approved
removing exactly the downloaded LLVM/Ghidra/Temurin archives. Those archives
were hash-checked, then removed; installed tools were retained. The recovery
URLs/hashes are in `approved-archive-cleanup.json`. Earlier download manifests
are historical verified provenance, not a claim that the archives still exist
locally. The third guarded world attempt resumes with the same installed tools.

## Fakeroot Ownership Simulation

All packages compiled, but APK rootfs installation under default fakeroot
reported ownership errors. The pinned upstream fakeroot 2.1.3 already supports
`FAKEROOTDONTTRYCHOWN=1`: its fchownat wrapper first reads the file and records
requested uid/gid in the simulated metadata store, then this option skips an
unnecessary real ownership syscall. It does not disable APK ownership checks,
remove metadata, ignore preliminary stat errors or grant host privilege. Set it
only in the build process environment as shown above. [Debian's fakeroot
manual](https://manpages.debian.org/testing/fakeroot/fakeroot.1.en.html) explains
its standard unprivileged archive-ownership simulation; exact flag semantics
are verified in the pinned source at libfakeroot.c:669–677 and 968–998.

`fakeroot-compatibility.json` covers four scratch-only controls using the actual
built fakeroot and a sentinel which rejects any would-be real fchownat call
without invoking the kernel. Default mode reproduces EACCES return values for
regular files/symlinks; simulation-only mode succeeds, records fake uid123/gid456
and makes zero such calls. Real uid/gid stay 1000/1000. The previous actual host
errno was not traced, so its exact identity remains an inference. The normal
full APK/image retry is the integration check, not an assumed pass.

The standalone probe deliberately refuses to run without its sentinel symbol.
Both C sources are retained here. Do not run privileged chown, ignore ownership
failures or substitute real root access as a shortcut. Source/configuration pins
and target permissions remain unchanged.
