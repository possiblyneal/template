# Adopt Conventional Commits, enforced by commitlint

> **Historical record — read `.openclaude/` as `.claude/`.** This plan predates the rename. The `.openclaude` → `.claude` compatibility symlink has since been removed, so paths and commands written here fail as typed. The text is left as approved rather than corrected, because a plan records what was agreed to, not what the tree looks like now.

## Context

Commit subjects in this repository are written by agents whose sessions end
immediately afterward. The body is the only durable record of why a change was
made, and nothing currently enforces any shape on either. Across 97 commits the
convention that emerged is strong but entirely informal: every non-merge commit
has a body, median 8 lines, and subjects average 46 characters.

Adopting Conventional Commits makes that shape machine-checkable and gives the
`CHANGELOG.md` workflow a signal it currently lacks — a commit typed `feat` or
carrying `BREAKING CHANGE:` announces that an entry is probably owed, without
replacing the per-pull-request judgment that decides whether one actually is.

This ships to every generated repository, so the cost lands in each of them:
commitlint is a JavaScript program, and pre-commit will provision an isolated
Node environment for it. That environment is invisible to this repository's own
language detection — `has_node()` in `scripts/libs/detect.sh:29` tests for
`package.json`, which none of this adds — so no generated repository starts
looking like a JavaScript project because of it.

### Decisions already made

- **commitlint over `conventional-pre-commit`.** The Python alternative checks
  only the header shape; it has no length, casing, or blank-line rules at all.
- **Merge commits, not squash.** commitlint's default ignore list already
  contains `^((Merge pull request)|(Merge branch ...))`, so GitHub's generated
  merge subjects pass without extra configuration.
- **Two rules raised from warning to error**, because the Conventional Commits
  specification states both as MUST and `config-conventional` ships them at
  warning level: `body-leading-blank` and `footer-leading-blank`.
- **`subject-case` keeps the stock default.** Subjects become lowercase after
  the type (`feat: publish the release from the changelog`). This is a real
  change — 67 of 93 existing subjects would have failed it.
- **The hook-wiring test runs for real in CI**, including a Node bootstrap.

## Changes

Every functional change below lands in **both** trees in the same commit: the
root, and `apps/github-repository-template/src/base-repo/`. The two copies of
`.pre-commit-config.yaml`, `scripts/doctor`, `scripts/tests/`, `ci.yml`, and
`.openclaude/hooks/session-start.sh` are currently byte-identical and must stay so.

### 1. `.pre-commit-config.yaml` — new top-level key and hook

Add above `repos:`:

```yaml
default_install_hook_types: [pre-commit, commit-msg]
```

This is what makes a plain `pre-commit install` write both hook files.
Without it the commit-msg hook is silently never installed and every commit
passes unchecked — the same class of failure the `adr-index` wiring bugs were.

Add the hook, with a comment in the style of the existing entries explaining
what it prevents:

```yaml
  - repo: https://github.com/alessandrojcm/commitlint-pre-commit-hook
    rev: v9.26.0
    hooks:
      - id: commitlint
        stages: [commit-msg]
        additional_dependencies: ["@commitlint/config-conventional@21.2.0"]
```

`config-conventional` is pinned deliberately, and the comment must say why it
needs manual bumping: Dependabot's pre-commit ecosystem updates `rev:` only and
never looks inside `additional_dependencies`, so an unpinned entry would drift
silently on whatever npm serves that day.

`scripts/check` runs `pre-commit run --all-files`, which runs `pre-commit`-stage
hooks only. A `commit-msg`-stage hook is correctly skipped there. Do not "fix"
this — the message does not exist yet at that point.

### 2. `.commitlintrc.yaml` — new file, repository root

```yaml
extends:
  - "@commitlint/config-conventional"

rules:
  body-leading-blank: [2, always]
  footer-leading-blank: [2, always]
```

YAML rather than `commitlint.config.mjs`: it needs no `package.json` (which
would make `has_node()` true and route every check through JavaScript adapters
in a repository containing none), and the existing `check-yaml` hook already
validates it on every commit. commitlint resolves `.commitlintrc.yaml` through
cosmiconfig — confirmed against its configuration reference.

Nothing else is overridden. `config-conventional` already supplies `type-enum`,
`header-max-length: 100`, `body-max-line-length: 100`, `subject-case`,
`subject-empty`, `subject-full-stop`, `type-case`, and `type-empty` at error
level.

### 3. `scripts/doctor` — check the second hook file

Extend the existing block at `scripts/doctor:78-90`. It already resolves the
hook path with `git rev-parse --git-path` rather than hardcoding `.git/hooks`,
for linked-worktree safety; add a matching `elif` branch for
`hooks/commit-msg`, with the same remedy line (`Run: pre-commit install`, which
now installs both).

### 4. `.openclaude/hooks/session-start.sh` — install both hook types

The condition at line 9 tests `! -f .git/hooks/pre-commit`. A clone that
already has the pre-commit hook but not the commit-msg hook — which is every
existing clone — passes that test and never gets the new hook. Widen it to
require both.

This also replaces the hardcoded `.git/hooks/` path with `git rev-parse
--git-path`, matching `scripts/doctor`. That is a pre-existing inconsistency,
not something this change introduces: the current form fails to install hooks
in a linked worktree. It is fixed here because the same condition is being
rewritten anyway, and leaving it hardcoded would spread the bug to a second
hook type.

### 5. `scripts/tests/commitlint-test` — new test

Follows `scripts/tests/adr-index-test:265-323` closely. Sources
`scripts/tests/libs/harness.sh`, skips the whole suite with a printed `SKIP`
when `pre-commit` or `git` is absent, and builds each fixture as a real
throwaway git repository.

The fixture must lift **both** the `default_install_hook_types` line and the
commitlint hook block out of the real `.pre-commit-config.yaml` with `awk`,
exactly as `hook_fixture` lifts the `adr-index` block today — restating the
config in the test would assert against a copy rather than against what ships.
It must also copy the real `.commitlintrc.yaml` into the fixture, since
commitlint resolves its config from the repository root.

Cases, in order:

1. `pre-commit install` with no arguments writes the `commit-msg` hook file.
   This is the assertion that `default_install_hook_types` works, and it is the
   one that costs nothing — `pre-commit install` provisions no environments.
2. A commit whose subject is not Conventional Commits is rejected.
3. A commit with a valid `type: subject` and a blank-line-separated body is
   accepted.
4. A subject of `Merge pull request #1 from user/branch` is accepted. This is
   the case that guards the merge-commit strategy; if commitlint's default
   ignore list ever stops covering it, every local merge starts failing.
5. A commit whose body is not preceded by a blank line is rejected, covering
   the raised `body-leading-blank` rule.

Cases 2-5 run commitlint for real, which is why the Node bootstrap is required.

### 6. `.github/workflows/ci.yml` — correct the comment

The comment at lines 27-32 currently states the hook-wiring fixture downloads
no hook environment. That stops being true. Rewrite it to say the suite now
provisions a Node environment for commitlint and therefore depends on the npm
registry, and that this was accepted so a commit-message rule cannot pass
review without having been run. The `pipx install pre-commit` step itself is
unchanged and now serves two suites.

Not included: caching `~/.cache/pre-commit` with `actions/cache`. It would cut
the recurring cost, but it is a separate concern and this change is already
touching seven files across two trees.

### 7. Documentation

- **Root `CLAUDE.md`, Git section** — state the convention, that it is enforced
  at `commit-msg` by commitlint, and how type relates to the changelog: `feat`,
  `fix`, and anything carrying `!` or `BREAKING CHANGE:` are strong signals an
  entry is owed; `docs`, `style`, `test`, `ci`, and `chore` are strong signals
  none is. Word it as a signal, not a mapping — the existing rule that
  notability is judged per pull request, and that a changelog restating the
  commit log is `git log` with extra steps, still governs.
- **`apps/github-repository-template/src/base-repo/CLAUDE.md`, Git section** —
  the same, written for a repository with no history to look at.
- **`scripts/CLAUDE.md`** — add `tests/commitlint-test` to Ownership and to the
  Verification list, and note there that it is the first test requiring network
  access.
- **`.openclaude/CLAUDE.md`** — record that `session-start.sh` now installs both
  hook types and resolves the hook path for worktrees.
- **`apps/github-repository-template/docs/github_repository_structure.md`** —
  a `.commitlintrc.yaml` entry, and an update to the `.pre-commit-config.yaml`
  entry covering the commit-msg stage and the pinned `additional_dependencies`.
- **`CHANGELOG.md`** — an `### Added` entry under `## [Unreleased]`. This
  changes a requirement for every generated repository, so it is notable.

## Verification

1. `scripts/tests/commitlint-test` — all five cases pass. The first run
   downloads Node and commitlint; expect it to take about a minute.
2. `scripts/doctor` — reports `ok: pre-commit` in this clone once
   `pre-commit install` has been rerun, and reports the missing commit-msg hook
   before that. Check both by moving the hook file aside and back.
3. `scripts/check` — full gate passes, and commitlint does **not** appear in
   the `pre-commit run --all-files` output.
4. By hand, on the branch: `git commit -m "nope"` is rejected, and a properly
   typed message with a blank line before its body is accepted. This is the
   end-to-end proof that the hook is live in this clone.
5. `git merge --no-ff` of a throwaway branch is accepted, confirming the
   default ignore list covers the merge subject in practice.

The first commit made under this change is itself a test of it.

## What review changed

Everything above is the plan as approved, kept as written. Review of the first
commit directed work the plan did not anticipate, and the branch no longer
matches it in four places:

- **§3 and §4 were replaced rather than implemented.** The plan added an `elif`
  to `doctor` and widened a condition in `session-start.sh`. Both read the same
  config with the same single-line pattern, so both were moved into
  `scripts/libs/precommit.sh`, which parses the list instead. The two copies had
  already drifted in how they tested for a hook file.
- **`scripts/tests/precommit-hooks-test` was added**, covering that parser
  across every YAML list form. It needs neither `pre-commit` nor the network,
  unlike `commitlint-test`.
- **`.commitlintrc.yaml` needed an ownership rule** in `.repo-template.json`.
  Root dotfiles match no directory pattern, so without one the payload's
  commit-message rules would never reach a generated repository — and the
  reference manifest in the repo-builder skill was missing the same line.
- **Squash merging was turned off**, and `scripts/repo-settings check` now
  reports it. The plan assumed merge commits; nothing enforced that assumption,
  and a squash takes its subject from the pull request title, where no hook
  reaches it.

`scripts/check` also gained a pass over untracked files, which is not this
plan's work — it was found while doing it, when `check` passed over two new
files it had never read.
