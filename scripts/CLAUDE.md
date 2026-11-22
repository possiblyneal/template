# Scripts

## Purpose

Keep portable shell logic here so local runs and GitHub Actions use the same implementation. Put helpers that must be built before use in `tools/`.

## Ownership

Keep scripts in one directory regardless of caller. Read the script or suite header before editing it; this contract covers rules shared across scripts.

| Caller | Entry points |
|---|---|
| Operator | `doctor`, `check`, `fix`, `clean`, `run`, `integration`, `package`, `summarize`, `repo-settings check` |
| `.github/` | `ci`, `ci-tested`, `security`, `release`, `detect`, `changelog-check`, `system-packages`, `script-tests` |
| Pre-commit | `adr-index`, `structure`, `payload-parity`, `attribute-commit` (with `--check` at `commit-msg`), `changelog-check` and `protect-branch` (`pre-push`), `worktree-cleanup` (`post-checkout`, `post-merge`) |
| Other hooks | `attribute-commit` (`prepare-commit-msg`), `worktree-cleanup --report` (SessionStart) |

## Local Contracts

- **Detection:** `libs/detect.sh` owns language decisions. Commands name a capability, not an adapter. `DETECT_LANGUAGES` and `DETECT_PRUNE_DIRS` control discovery.
- **Toolchains:** `check` uses the machine's versions; `.github/actions/setup-toolchains/action.yml` installs fresh versions in CI, except that the host must already have `rustup`.
  The setup action and `security.yml`'s cargo audit report a missing `rustup`. Check versions first when CI and local results differ. Pre-commit pins its tools by `rev`.
  The Go audit reads the local standard library and names the release that clears a finding.
  Pin versions in repositories that use the language, not in the shared payload: Dependabot cannot maintain those toolchain pins.
- **Adapters:** Capture exit status as well as output. Leave missing adapters absent so the probe reports `absent` and dispatch reports `unavailable`.
  An expected check that is unavailable fails the run. See the `libs/detect.sh` header for translation of nonzero statuses that do not indicate real failures.
- **Result output:** `summarize` parses `libs/result.sh`'s layout. Keep `tally` as the exit status.
  Use `result_verdict` for the final line: `<command as invoked> exited <status>: <count per state>`.
  Emit results in the shell that exits; a subshell's counts cannot reach its trap. A custom EXIT trap calls `result_exit_verdict`. `summarize` ends with the verdict of the command it ran.
- **Stdin:** `script-tests` closes fd 0 for suites, `check` closes it for `structure`, and dispatch closes it except for `run`. `*_each` reads its list on fd 3.
  Capture pipeline output in a variable rather than using a reader that exits early: under `pipefail`, SIGPIPE becomes 141 and can be read as absent.
- **File mode:** Source `libs/*.sh` and `tests/libs/harness.sh`; omit the shebang and executable bit. Other scripts are executable and extensionless, so pre-commit can identify them by shebang.
- **Hooks:** `adr-index` and `structure` are hooks, not capabilities. Use `always_run` with no `files:` filter because staged path lists omit deletions.
- **Hosted state:** Only `repo-settings check` and `ci-tested` (called only by `ci.yml`) inspect hosted GitHub state. Other commands may still need network access.

## Work Guidance

**Adding a language:**

1. Add it to `DETECT_LANGUAGES`. Write `has_<lang>` and each supported `_capability_<check>_<lang>`; leave unsupported adapters absent.
2. Add a `_codeql_entry` row and the toolchain setup in `.github/actions/setup-toolchains/action.yml`.
3. Add its column to `tests/capabilities-test` against `language_capabilities probe`, marking intentionally `absent` cells.
   This suite detects a dropped language even if the gate stays green.
4. Add root manifests and lockfiles to `scripts/structure`'s `root_files`. Add the nested/root pair to `detect_orphan_manifests`'s `pairs`.
5. Add the manifest to `libs/dependabot.sh`'s `dependabot_ecosystem_of` if Dependabot supports it (it does not for C or C++).

**Adding a check:** Add it to `DETECT_CAPABILITIES`. Write adapters per language or declare inapplicability in `_capability_is_not_applicable`.

**Adding a suite:** Name it `tests/<name>-test`, report through `tests/libs/harness.sh`, test the public surface, and state coverage in the header.
Suites run concurrently: use private scratch repositories or write only paths the suite owns outright.

**Mirroring edits:** Apply changes under `scripts/` to `apps/github-repository-template/src/base-repo/scripts/` as well. `payload-parity` exempts this contract only.

## Verification

`scripts/check` runs `structure` and `payload-parity`, runs `script-tests` beside `ci` (holding suite output until `ci` ends), then sweeps pre-commit, skipping hooks that duplicate gate steps.

`ci.yml` runs suites before toolchain setup but after installing pre-commit so `adr-index-test` and `commitlint-test` exercise hook wiring.
Pre-commit runs ShellCheck with `-x` against live scripts; payload parity covers the copies.

## Child Index

None.
