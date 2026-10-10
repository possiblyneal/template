# Scripts

## Purpose

Every portable shell script, whether a person runs it or a workflow does. Project logic lives here rather than in YAML so it runs locally exactly as it runs in GitHub Actions.

## Ownership

One flat directory, not a `ci/` and a `scripts/` split: `check` calls `ci` and `security`, `release` calls `ci`, and every script sources the same detection library, so a file's caller is not a property that stays put. A helper that must be built before it runs belongs in `tools/`.

Each script's header comment says what it does, who calls it, and why it is shaped that way; each `tests/*-test` header says what that suite covers. Read the header before editing the file. This document holds only the rules that span scripts.

- Run by a person: `doctor`, `check`, `fix`, `clean`, `run`, `integration`, `package`, `summarize`, `repo-settings check`
- Called by `.github/`: `ci`, `security`, `release`, `detect`, `changelog-check`, `system-packages`, `script-tests`
- Called by pre-commit: `adr-index`, `structure`, `github-parity`, `attribute-commit`, `changelog-check`, `protect-branch`, `worktree-cleanup`
- Sourced: `libs/detect.sh`, `libs/result.sh`, `libs/unit.sh`, `libs/precommit.sh`, `libs/dependabot.sh`, `libs/quadlet.sh`, `tests/libs/harness.sh`

## Local Contracts

- **`libs/detect.sh` owns every language decision.** Commands name a capability, never an adapter; `DETECT_LANGUAGES` and `DETECT_PRUNE_DIRS` are the lists.
- **The toolchains are the machine's, not a pinned set.** `check` runs whatever compiler, linter, and formatter the machine has; `.github/actions/setup-toolchains` installs each fresh on the runner (`go-version: stable`, `node-version: lts/*`, `swift-version: latest`, `rustup component add` over a rustup the host must already have). pre-commit pins what it owns by `rev`, so a check that passes locally and fails in CI is a version difference before it is a flaky runner. rustup is the one prerequisite neither installs; the setup action and `security.yml`'s cargo-audit step fail with one line naming the host. Pin a toolchain in the repository that has the language: a pin shipped from the payload obliges every generated repository to bump a file for a language it may not have, and Dependabot has no ecosystem for any of them.
- **A check that did not run is not a check that passed.** `unavailable` fails the run whenever the check was expected.
- **`libs/result.sh`'s printed layout is an interface**, parsed by `summarize`; `tally` is a command's last line and its exit status.
- **A check owns no stdin.** `script-tests` closes fd 0 for each suite and `check` for `structure`, and the dispatch closes it for every capability but `run`, so a stdin-draining tool cannot hang the gate. The `*_each` helpers take their list on fd 3, and pipes end in a variable, never a reader that exits early, since `pipefail` turns SIGPIPE into 141, read as absent.
- **An adapter is honest about what it did.** Capture the tool's exit status, not only its output. No function stands in for an absent one: the probe reads `absent` off the function table and the dispatch reports `unavailable`. A runner that exits non-zero without a real failure is translated, and `libs/detect.sh`'s header lists the four.
- **`libs/*.sh` and `harness.sh` are sourced, never executed**: no shebang, no executable bit, `.sh`. Every other script is extensionless and executable; pre-commit reads a shebang only on one.
- **`adr-index` and `structure` are hooks, not capabilities**, and run `always_run` with no `files:` filter, since staged paths exclude deletions.
- **Local commands stay off hosted GitHub state.** The boundary is hosted state, not connectivity; only `repo-settings check` crosses it.

## Work Guidance

Adding a language: add it to `DETECT_LANGUAGES`, add its `has_<lang>` detector, add a `_capability_<check>_<lang>` function for each capability it can answer (one with no honest adapter is left absent, not stubbed), add a `_codeql_entry` row, add its toolchain to `.github/actions/setup-toolchains/action.yml`, and add its column to the table `tests/capabilities-test` holds against `language_capabilities probe`, naming which cells are deliberately `absent`. That suite is the only thing that notices a dropped language, which otherwise produces a shorter green run.

Adding a check: add it to `DETECT_CAPABILITIES` and write an adapter per language, or declare it not-applicable in `_capability_is_not_applicable`.

Adding a suite: name it `tests/<name>-test`, report through `tests/libs/harness.sh`, assert through the public surface, and say what it covers in its header. It runs concurrently beside every other suite, so it keeps to its own scratch repositories.

Changes here almost always belong in `apps/github-repository-template/src/base-repo/scripts/` too. Decide explicitly; a fix in one tree only is how the two drift.

## Verification

`scripts/check` runs every suite through `script-tests` before the checks they guard, then `structure` and `github-parity` before `ci`. `ci.yml` runs them the same way before toolchain setup, with `pre-commit` installed first so `adr-index-test` and `commitlint-test` do not skip their hook-wiring cases. shellcheck runs via pre-commit with `-x`.
