---
type: Architecture Decision Record
title: Support C, C++ and Assembly as One Language Built by CMake
description: C, C++ and assembly join the supported set as one detected language, cpp, present when the root holds a CMakeLists.txt, with clang-tidy, clang-format, CMake and ctest as its adapters and the firmware ship targets left until a firmware unit exists.
scope: [global]
tags: [language-support, lang:cpp]
generated: { by: "agent/claude-opus-5-5", at: "2026-11-18T18:08:39Z" }
superseded_by:
status: accepted
---

# Support C, C++ and Assembly as One Language Built by CMake

## Decision

C, C++ and assembly are one entry in `DETECT_LANGUAGES`, `cpp`, present
when the root holds a non-empty `CMakeLists.txt`. Its adapters are:

- **lint**: clang-tidy over the compilation database CMake exports,
  narrowed to the repository's own C and C++ files. **lint-fix** runs the
  same with `--fix`.
- **format-check** and **format-write**: clang-format over the same files.
- **build**: `cmake --build` into the root `build/`.
- **test**: ctest, after a build.
- **toolchain**: checks for `cmake` and `ctest`.
- **CodeQL**: `c-cpp` with `build-mode: none`.

typecheck, audit and integration are not applicable. run and package are
left absent, so `scripts/run` and `scripts/package` report `unavailable`
for a C or C++ unit. The ship targets a firmware unit needs are not
decided here: they wait until a firmware unit exists to decide them
against.

## Context

The template supported six languages, and C, C++ and assembly were rows 7, 8
and 17 of `docs/language-ranking.md`, each to be added "only when that
specific kind of project comes up". Microcontroller firmware is that
project. A firmware tree mixes all three in one target: a startup file in
assembly, a HAL in C, application code in C or C++. One build file compiles
them together, and CodeQL treats C and C++ as the one language `c-cpp`. So
three detected languages would mean three detectors over one file, and
three columns of adapters that could not differ.

CMake is the build system because the checks need things only it reports:

- `CMAKE_EXPORT_COMPILE_COMMANDS` writes `compile_commands.json`, which is
  how clang-tidy learns each file's flags and include paths.
- `enable_testing()` and `add_test()` give ctest a test set to run.
- The File API (`build/.cmake/api/v1/reply/`) lists every target with its
  type, which is what a later run or package adapter will read to find the
  executables.

The tools ship on GitHub's Ubuntu 24.04 image: CMake 3.31, gcc 13, and
clang, clang-format and clang-tidy 16 to 18. That puts nothing in the setup
action but a check that they are there.

Three behaviours shaped the adapters, each found by probing:

- clang-tidy parses `.S` as C and fails, and clang-format has no assembly
  mode. Both tools are therefore handed the compilation database
  intersected with the repository's own `.c`/`.cc`/`.cpp`-family files.
  That one intersection also drops vendored code and sources generated
  into, or fetched into, `build/`.
- ctest reads only the top-level `CTestTestfile.cmake`, which CMake writes
  only when the root `CMakeLists.txt` calls `enable_testing()`. When only a
  unit calls it, ctest prints "No tests were found" and exits 0, so tests
  that were written are silently skipped. The test adapter fails when a
  nested test file exists and the top-level one does not. A project with
  no tests at all still passes, as pytest collecting none does.
- `FetchContent` clones each dependency's tree into `build/`, so the root
  `build/` is pruned from every search, and `scripts/clean` removes it by
  path.

## Alternatives Considered

**GNU Make.** Rejected because it reports nothing the checks need. Make has
no compilation database without wrapping the build in a tool like Bear, no
test registry, and no way to list its executables, so lint, test, run and
package would each need a list that every repository declares and keeps up
to date by hand. This would be worth revisiting if a firmware vendor's SDK
can only be driven by Make. A CMake project can still invoke such a build
through `ExternalProject`.

**C, C++ and assembly as separate languages.** Rejected for the reasons in
Context: they share one build file, and CodeQL already counts C and C++ as
one language.

**Wiring run and package now.** Deferred. The File API makes finding
executables cheap, but a host executable and a firmware image are delivered
differently, and the target vocabulary has no word for a microcontroller
yet. Choosing that vocabulary before a firmware unit exists would mean
guessing.

## Consequences

- Dependabot has no CMake ecosystem, so a `FetchContent` pin is a URL and a
  tag that nothing bumps, and `scripts/security` has no C or C++ audit.
  A repository that adopts vcpkg or Conan can add Dependabot's `vcpkg`
  ecosystem, or Trivy's Conan support, when that happens.
- `scripts/run` and `scripts/package` fail for a C or C++ unit, which is the
  same honest gap Swift's run has, until the firmware decision is made.
- The root `CMakeLists.txt` is the workspace file. A nested one that the
  root does not reach is reported by `detect_orphan_manifests`, the same
  way a Go module missing from `go.work` is.
- Neither clang-tidy nor clang-format reads a manifest. `.clang-format` and
  `.clang-tidy` are therefore permitted at the root by name, and without
  them each tool uses its built-in defaults.
