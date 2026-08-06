# shellcheck shell=bash
# Language detection, defined once.
#
# Source this; do not execute it. It defines functions and constants and sets no
# state, so a caller keeps its own `set` options. Every function reads paths
# relative to the current directory, and every caller cds to the repository root
# before sourcing.
#
# No shebang, and not executable: running it does nothing, and pre-commit's
# check-shebang-scripts-are-executable would otherwise require an executable bit
# that says this is a command. The .sh extension marks it as shell to the
# linter, and the directive above names the dialect the shebang used to.
#
# This exists because detection used to be copied across eight files, and the
# copies answered the same question differently. A language wired into some of
# them is worse than one wired into none: the checks that know about it pass,
# and the ones that do not report a clean run over work they never looked at.
#
# Pipes here end in a variable or a `-print -quit` test rather than feeding a
# reader that exits early. Under `set -euo pipefail` a `grep -q` or `head` that
# closes the pipe kills the writer with SIGPIPE and pipefail reports 141, which
# a detection function reads as "absent" — the one wrong answer that is silent
# rather than loud.

# The single place the supported set is written down. Callers iterate this
# rather than keeping their own list.
DETECT_LANGUAGES=(node python go rust swift kotlin)

has_node() { [[ -s package.json ]]; }
has_python() { [[ -s pyproject.toml ]]; }
has_go() { [[ -s go.mod || -s go.work ]]; }
has_rust() { [[ -s Cargo.toml ]]; }
has_kotlin() { [[ -s settings.gradle.kts || -s build.gradle.kts ]]; }

# Directories holding manifests that belong to a dependency or another
# repository rather than to this one. Searching them reports another project's
# packages as this project's.
DETECT_PRUNE_DIRS=(.git node_modules .build target .venv venv vendor)

# find(1) with the directories above pruned. Arguments after the filename are
# forwarded, so callers choose -print, -print -quit, or a test of their own.
detect_find() {
  local name="$1" prune=() dir
  shift

  for dir in "${DETECT_PRUNE_DIRS[@]}"; do
    prune+=(-name "$dir" -o)
  done
  unset 'prune[${#prune[@]}-1]'

  find . \( "${prune[@]}" \) -prune -o -name "$name" -type f "$@"
}

# Swift is the one supported language with no root manifest: SwiftPM has no
# workspace file, so packages sit at apps/<name>/ and libs/<name>/ and nothing
# at the root names them. Found by search, and the result is cached because that
# search walks the tree and no manifest appears or disappears mid-run.
_detect_swift_cache=""
has_swift() {
  if [[ -z "$_detect_swift_cache" ]]; then
    if [[ -n "$(detect_find Package.swift -print -quit)" ]]; then
      _detect_swift_cache=yes
    else
      _detect_swift_cache=no
    fi
  fi
  [[ "$_detect_swift_cache" == yes ]]
}

has_language() { "has_$1"; }

# Present languages, one per line, in DETECT_LANGUAGES order.
detect_present_languages() {
  local lang
  for lang in "${DETECT_LANGUAGES[@]}"; do
    if has_language "$lang"; then echo "$lang"; fi
  done
}

# Whether the repository is a project at all. A caller that found no runner
# needs this to tell "nothing to check yet" from "a manifest is present and its
# checks silently did not run", which produce the same output otherwise.
has_any_manifest() {
  local lang
  for lang in "${DETECT_LANGUAGES[@]}"; do
    if has_language "$lang"; then return 0; fi
  done
  return 1
}

# Returned by a check whose language has no wired-up runner, or whose runner is
# not installed here. Distinct from any exit code a real tool is likely to
# return, so "the tool reported a problem" is never read as "no tool ran".
#
# Assigned only when unset: re-assigning a readonly is an error, and under
# `set -e` that would abort a caller that sources this file twice.
if [[ -z "${NO_RUNNER:-}" ]]; then
  readonly NO_RUNNER=199
fi

# `uv run <tool>` exits 2 when the tool is not installed, which is the same
# shape as a tool that ran and reported problems. Reporting that as a failure
# blames the code for a missing dependency, so the tool is looked up first and
# its absence reported as no runner, which scripts/doctor then explains.
uv_run() {
  command -v uv >/dev/null 2>&1 || return "$NO_RUNNER"
  uv run --quiet "$1" --version >/dev/null 2>&1 || return "$NO_RUNNER"
  uv run "$@"
}

# Whether anything here needs trivy, which .github/workflows/security.yml reads
# to decide whether to install it. Package.resolved is committed by SwiftPM;
# Gradle writes gradle.lockfile only once dependency locking is turned on, so a
# Gradle repository without one has no resolved versions to scan.
has_trivy_target() {
  [[ -n "$(detect_find Package.resolved -print -quit)" ]] ||
    [[ -n "$(detect_find gradle.lockfile -print -quit)" ]]
}

# Runs trivy over every lockfile matching a name, since Swift and Gradle have no
# first-party audit command. Every lockfile is scanned even after one reports a
# vulnerability, so the first hit does not hide the rest.
trivy_each() {
  local lockfile status=0 found=1

  while IFS= read -r lockfile; do
    [[ -n "$lockfile" ]] || continue
    found=0
    trivy fs --exit-code 1 --severity HIGH,CRITICAL --scanners vuln "$lockfile" || status=1
  done < <(detect_find "$1" -print)

  (( found == 0 )) || return "$NO_RUNNER"
  return "$status"
}

# Runs a command once per Swift package directory. Every package runs even after
# one fails, so a single broken package does not hide the state of the rest,
# while any failure still decides the exit status.
swift_each() {
  local manifest status=0
  while IFS= read -r manifest; do
    ( cd "$(dirname "$manifest")" && "$@" ) || status=1
  done < <(detect_find Package.swift -print)
  return "$status"
}

# Gradle exposes lint and format tasks only when the matching plugin is applied,
# so the task list decides which checks exist. Listing costs a daemon start, so
# the result is read once and reused.
_detect_gradle_tasks=""
gradle_has_task() {
  has_kotlin && [[ -x ./gradlew ]] || return 1

  if [[ -z "$_detect_gradle_tasks" ]]; then
    _detect_gradle_tasks="$(./gradlew -q tasks --all 2>/dev/null || true)"
    # A newline marks "listed, found nothing" so the next call does not relist.
    [[ -n "$_detect_gradle_tasks" ]] || _detect_gradle_tasks=$'\n'
  fi

  grep -qE "^$1( |$)" <<<"$_detect_gradle_tasks"
}

# `npm init -y` writes a placeholder test script that prints an error and exits
# 1. Counting it as a configured runner turns a scaffold that has never had a
# test into a failing test run, which reads as a broken suite. It is passed as
# an argument rather than written into the -e program, which would need a
# backtick or an escaped quote in a string the shell must not expand.
NPM_PLACEHOLDER_TEST='echo "Error: no test specified" && exit 1'

# Reads package.json directly. `npm run` writes its listing to stderr and prints
# nothing under --silent, so parsing its output silently matches nothing.
has_npm_script() {
  has_node &&
    command -v node >/dev/null 2>&1 &&
    command -v npm >/dev/null 2>&1 &&
    node -e 'const s=require("./package.json").scripts||{};const v=s[process.argv[1]];process.exit(v&&v!==process.argv[2]?0:1)' "$1" "$NPM_PLACEHOLDER_TEST" 2>/dev/null
}

# The root manifest each language is checked from. Swift is absent deliberately:
# it has no root manifest, so nested packages are how a Swift repository is
# supposed to look and the orphan rule below must not fire on them.
_detect_root_manifest() {
  case "$1" in
    node) echo "package.json" ;;
    python) echo "pyproject.toml" ;;
    go) echo "go.work" ;;
    rust) echo "Cargo.toml" ;;
    kotlin) echo "settings.gradle.kts" ;;
    *) return 1 ;;
  esac
}

# Every check runs from the repository root against a root workspace manifest.
# A package nested under apps/ or libs/ with no root manifest of its language is
# therefore invisible: nothing lints it, tests it, or audits its dependencies,
# and the run is green because no check ever looked.
#
# This catches "no root manifest at all", not "root manifest that omits this
# package". Reading membership out of npm workspaces, uv sources, or Cargo
# members needs a parser per tool, so a package left out of an existing root
# manifest is still missed.
#
# A nested manifest is not always named like the root one it belongs to: a Go
# module is go.mod under a root go.work, and a Gradle project is build.gradle.kts
# under a root settings.gradle.kts. Each pair is listed rather than assumed.
_detect_orphan_report() {
  local nested="${1#./}" root="$2" noun="$3" fix="$4"

  echo "Found $nested with no root $root."
  echo
  echo "  This repository's checks run from root workspace manifests, so this"
  echo "  $noun is invisible to lint, test, and audit."
  echo
  echo "  Fix: $fix, or move the $noun under an existing workspace."
  echo
}

detect_orphan_manifests() {
  local lang root nested dir found=1

  # language:nested manifest:root manifest:noun. Swift is absent deliberately:
  # it has no root manifest, so nested packages are how a Swift repository is
  # supposed to look and this rule must never fire on one.
  local -a pairs=(
    "node:package.json:package.json:package"
    "python:pyproject.toml:pyproject.toml:package"
    "rust:Cargo.toml:Cargo.toml:crate"
    "go:go.mod:go.work:module"
    "kotlin:build.gradle.kts:settings.gradle.kts:project"
  )

  local entry nested_name
  for entry in "${pairs[@]}"; do
    IFS=: read -r lang nested_name root noun <<<"$entry"

    # A present root manifest means the language is wired up; nested packages
    # under it are ordinary workspace members, not orphans.
    if has_language "$lang"; then continue; fi

    while IFS= read -r nested; do
      [[ -n "$nested" ]] || continue
      found=0
      dir="$(dirname "${nested#./}")"

      case "$lang" in
        go) _detect_orphan_report "$nested" "$root" "$noun" \
          "run 'go work init ./$dir' at the repository root" ;;
        kotlin) _detect_orphan_report "$nested" "$root" "$noun" \
          "add a root $root with an include() entry covering $dir" ;;
        *) _detect_orphan_report "$nested" "$root" "$noun" \
          "add a root $root covering $dir" ;;
      esac
    done < <(detect_find "$nested_name" -print)
  done

  return "$found"
}

# The module's external interface is `language_capabilities` below. Everything
# after this point is its private per-language implementation. Callers name a
# capability; they do not know which command, manifest, or tool provides it.

_capability_lint_node() { has_npm_script lint || return "$NO_RUNNER"; npm run lint; }
_capability_lint_python() { uv_run ruff check .; }
_capability_lint_go() { go vet ./...; }
_capability_lint_rust() { cargo clippy -- -D warnings; }
_capability_lint_swift() { command -v swift >/dev/null 2>&1 || return "$NO_RUNNER"; swift_each swift format lint --recursive --strict .; }
_capability_lint_kotlin() {
  if gradle_has_task ktlintCheck; then ./gradlew ktlintCheck; return; fi
  if gradle_has_task detekt; then ./gradlew detekt; return; fi
  return "$NO_RUNNER"
}

_capability_format_check_node() { has_npm_script format:check || return "$NO_RUNNER"; npm run format:check; }
_capability_format_check_python() { uv_run ruff format --check .; }
_capability_format_check_go() {
  local unformatted
  unformatted="$(gofmt -l .)"
  [[ -z "$unformatted" ]] || { echo "gofmt needed: $unformatted"; return 1; }
}
_capability_format_check_rust() { cargo fmt --check; }
_capability_format_check_swift() { command -v swift >/dev/null 2>&1 || return "$NO_RUNNER"; swift_each swift format lint --recursive .; }
_capability_format_check_kotlin() { gradle_has_task ktlintCheck || return "$NO_RUNNER"; ./gradlew ktlintCheck; }

_capability_typecheck_node() { has_npm_script typecheck || return "$NO_RUNNER"; npm run typecheck; }
_capability_typecheck_python() { uv_run mypy .; }

_capability_test_node() { has_npm_script test || return "$NO_RUNNER"; npm run test; }
_capability_test_python() {
  local status=0
  uv_run pytest || status=$?
  if (( status == 5 )); then
    echo "pytest collected no tests."
    return 0
  fi
  return "$status"
}
_capability_test_go() { go test ./...; }
_capability_test_rust() { cargo test; }
_capability_test_swift() { command -v swift >/dev/null 2>&1 || return "$NO_RUNNER"; swift_each swift test; }
_capability_test_kotlin() { [[ -x ./gradlew ]] || return "$NO_RUNNER"; ./gradlew test; }

_capability_build_node() { has_npm_script build || return "$NO_RUNNER"; npm run build; }
_capability_build_go() { go build ./...; }
_capability_build_rust() { cargo build --locked; }
_capability_build_swift() { command -v swift >/dev/null 2>&1 || return "$NO_RUNNER"; swift_each swift build; }
_capability_build_kotlin() { [[ -x ./gradlew ]] || return "$NO_RUNNER"; ./gradlew build -x test; }

_capability_audit_node() {
  if [[ -s package-lock.json ]] && command -v npm >/dev/null 2>&1; then
    npm audit --audit-level=moderate
    return
  fi
  if [[ -s pnpm-lock.yaml ]] && command -v pnpm >/dev/null 2>&1; then
    pnpm audit --audit-level moderate
    return
  fi
  if [[ -s yarn.lock ]] && command -v yarn >/dev/null 2>&1; then
    yarn npm audit --severity moderate
    return
  fi
  return "$NO_RUNNER"
}
_capability_audit_python() { uv_run pip-audit; }
_capability_audit_go() { command -v govulncheck >/dev/null 2>&1 || return "$NO_RUNNER"; govulncheck ./...; }
_capability_audit_rust() { command -v cargo-audit >/dev/null 2>&1 || return "$NO_RUNNER"; cargo audit; }
_capability_audit_swift() { command -v trivy >/dev/null 2>&1 || return "$NO_RUNNER"; trivy_each Package.resolved; }
_capability_audit_kotlin() { command -v trivy >/dev/null 2>&1 || return "$NO_RUNNER"; trivy_each gradle.lockfile; }

_capability_toolchain_node() { command -v npm >/dev/null 2>&1 || return "$NO_RUNNER"; }
_capability_toolchain_python() { command -v uv >/dev/null 2>&1 || return "$NO_RUNNER"; }
_capability_toolchain_go() { command -v go >/dev/null 2>&1 || return "$NO_RUNNER"; }
_capability_toolchain_rust() { command -v cargo >/dev/null 2>&1 || return "$NO_RUNNER"; }
_capability_toolchain_swift() { command -v swift >/dev/null 2>&1 || return "$NO_RUNNER"; }
_capability_toolchain_kotlin() {
  command -v java >/dev/null 2>&1 || return "$NO_RUNNER"
  [[ -x ./gradlew ]] || return "$NO_RUNNER"
}

_capability_format_write_node() { has_npm_script format || return "$NO_RUNNER"; npm run format; }
_capability_format_write_python() { uv_run ruff format .; }
_capability_format_write_go() { gofmt -w .; }
_capability_format_write_rust() { cargo fmt; }
_capability_format_write_swift() { command -v swift >/dev/null 2>&1 || return "$NO_RUNNER"; swift_each swift format --in-place --recursive .; }
_capability_format_write_kotlin() { gradle_has_task ktlintFormat || return "$NO_RUNNER"; ./gradlew ktlintFormat; }

_capability_dev_node() { has_npm_script dev || return "$NO_RUNNER"; npm run dev; }
_capability_dev_python() { return "$NO_RUNNER"; }
_capability_dev_go() { go run .; }
_capability_dev_rust() { cargo run; }
_capability_dev_swift() { return "$NO_RUNNER"; }
_capability_dev_kotlin() { gradle_has_task run || return "$NO_RUNNER"; ./gradlew run; }

_capability_is_not_applicable() {
  case "$1:$2" in
    typecheck:go|typecheck:rust|typecheck:swift|typecheck:kotlin|build:python) return 0 ;;
    *) return 1 ;;
  esac
}

_capability_is_supported() {
  case "$1" in
    lint|format-check|typecheck|test|build|audit|toolchain|format-write|dev) return 0 ;;
    *) return 1 ;;
  esac
}

_language_is_supported() {
  local supported
  for supported in "${DETECT_LANGUAGES[@]}"; do
    [[ "$1" == "$supported" ]] && return 0
  done
  return 1
}

_capability_result() {
  printf '%-14s %s %s\n' "$1" "$2" "$3"
}

_language_capabilities_run() {
  local dry_run="" selected="" cap lang function status
  local failed=0 unavailable=0
  local -a capabilities=() languages=()

  while (( $# > 0 )); do
    case "$1" in
      --dry-run) dry_run=1; shift ;;
      --language)
        (( $# >= 2 )) || { echo "--language needs a value" >&2; return 2; }
        selected="$2"
        shift 2
        ;;
      --) shift; break ;;
      *) break ;;
    esac
  done

  (( $# > 0 )) || { echo "run needs at least one capability" >&2; return 2; }
  capabilities=("$@")

  for cap in "${capabilities[@]}"; do
    _capability_is_supported "$cap" || { echo "Unknown capability: $cap" >&2; return 2; }
  done

  if [[ -n "$selected" ]]; then
    _language_is_supported "$selected" || { echo "Unsupported language: $selected" >&2; return 2; }
    has_language "$selected" || { echo "Language is not present: $selected" >&2; return 2; }
    languages=("$selected")
  else
    mapfile -t languages < <(detect_present_languages)
  fi

  for cap in "${capabilities[@]}"; do
    for lang in "${languages[@]}"; do
      if _capability_is_not_applicable "$cap" "$lang"; then
        _capability_result not-applicable "$cap" "$lang"
        continue
      fi

      function="_capability_${cap//-/_}_${lang}"
      if ! declare -F "$function" >/dev/null; then
        _capability_result unavailable "$cap" "$lang"
        unavailable=1
        continue
      fi

      if [[ -n "$dry_run" ]]; then
        _capability_result would-run "$cap" "$lang"
        continue
      fi

      status=0
      "$function" || status=$?
      case "$status" in
        0) _capability_result pass "$cap" "$lang" ;;
        "$NO_RUNNER")
          _capability_result unavailable "$cap" "$lang"
          unavailable=1
          ;;
        *)
          _capability_result "FAIL (exit $status)" "$cap" "$lang"
          failed=1
          ;;
      esac
    done
  done

  (( failed == 0 )) || return 1
  (( unavailable == 0 )) || return "$NO_RUNNER"
  return 0
}

_codeql_entry() {
  case "$1" in
    node) echo 'javascript-typescript none ubuntu-latest' ;;
    python) echo 'python none ubuntu-latest' ;;
    go) echo 'go autobuild ubuntu-latest' ;;
    rust) echo 'rust none ubuntu-latest' ;;
    kotlin) echo 'java-kotlin autobuild ubuntu-latest' ;;
    swift) echo 'swift autobuild macos-latest' ;;
    *) return 1 ;;
  esac
}

_language_capabilities_github_output() {
  local lang
  for lang in "${DETECT_LANGUAGES[@]}"; do
    if has_language "$lang"; then
      echo "$lang=true"
    else
      echo "$lang=false"
    fi
  done

  if has_trivy_target; then echo "trivy=true"; else echo "trivy=false"; fi
}

_language_capabilities_check_orphans() {
  local orphans
  orphans="$(detect_orphan_manifests || true)"
  [[ -n "$orphans" ]] || return 0
  echo "$orphans"
  return 1
}

_language_capabilities_codeql_matrix() {
  local lang entry language build_mode runner
  local -a entries=()

  while IFS= read -r lang; do
    [[ -n "$lang" ]] || continue
    entry="$(_codeql_entry "$lang")" || continue
    read -r language build_mode runner <<<"$entry"
    entries+=("{\"language\":\"$language\",\"build-mode\":\"$build_mode\",\"runner\":\"$runner\"}")
  done < <(detect_present_languages)

  entries+=('{"language":"actions","build-mode":"none","runner":"ubuntu-latest"}')
  printf 'matrix={"include":[%s]}\n' "$(IFS=,; echo "${entries[*]}")"
}

language_capabilities() {
  local command="${1:-}"
  (( $# == 0 )) || shift

  case "$command" in
    supported) printf '%s\n' "${DETECT_LANGUAGES[@]}" ;;
    present) detect_present_languages ;;
    has-any) has_any_manifest ;;
    check-orphans) _language_capabilities_check_orphans ;;
    github-output) _language_capabilities_github_output ;;
    codeql-matrix) _language_capabilities_codeql_matrix ;;
    run) _language_capabilities_run "$@" ;;
    ""|-h|--help|help)
      echo "Usage: language_capabilities supported|present|has-any|check-orphans|github-output|codeql-matrix|run"
      ;;
    *) echo "Unknown language capabilities command: $command" >&2; return 2 ;;
  esac
}
