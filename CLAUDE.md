## What this repository is

This repository builds other repositories. It holds two trees and they must not be confused:

- **Live configuration** — `scripts/`, `.github/`, `.claude/`, and the root dotfiles govern *this* repository, the same way they govern any other.
- **Template payload** — `apps/github-repository-template/src/base-repo/` is the content copied into repositories generated from this one. Editing a file there changes every future generated repository and changes nothing here.

The two trees hold near-identical files. Before editing, decide which one the change belongs to: a fix applied only at the root leaves the template shipping the bug, and a fix applied only in the payload leaves this repository running it. Editing under `apps/github-repository-template/src/` prompts for approval so the choice stays deliberate.

This repository was generated from its own payload, so the root files are that payload plus repository-specific merges. `.repo-template.json` records the payload commit the root was last reconciled with, and marks `apps/**` as product so an update never overwrites the payload that produced it. It names this file managed, since a directory pattern reaches no root file and an unmatched path is product-owned, which would put the repository's own instructions beyond every update.

`apps/github-repository-template/docs/github_repository_structure.md` is the structure and bill of materials for the payload, naming briefly what each file and folder is for. Read it before changing what the template ships, to see where a file belongs and what it is there to do.

## Commands

Use these instead of per-language tools; each detects the languages present and fails when an expected check cannot run.

- `scripts/doctor` — verify local toolchains, dependencies, hooks, and configuration without contacting hosted services
- `scripts/repo-settings check` — inspect GitHub-hosted security and branch settings; run explicitly because it needs network access and repository administration visibility
- `scripts/check` — full local gate: `doctor`, the script tests, then lint, format, type check, test, build, then the security audit and pre-commit across every file, tracked and untracked, not just staged ones. Local means it reads no hosted GitHub state, not that it stays offline: `commitlint-test` and pre-commit's own hook environments fetch on first use
- `scripts/fix` — rewrite formatting for every detected stack; the write half of `check`'s format check, no lint autofixes
- `scripts/summarize <command…>` — run a check command and print only its Result table, findings included, exiting with that command's status. The way to read a `check` or `ci` run without a hand-built filter over hundreds of lines of tool output
- `scripts/clean` — recursively delete build output and tool caches (`dist`, `build`, `coverage`, `__pycache__`, `.*_cache`, `*.pyc`)
- `scripts/run [unit] [-- args…]` — start the unit, dispatching on the `run` fact it declared; requires the unit name when `apps/` holds several, since a run is one foreground process. Everything after `--` reaches the program unchanged
- `scripts/package [unit]` — deliver what the unit declared it ships: an executable per declared target into the unit's `dist/`, or a `deploy/quadlet/` pair validated and nothing built. Where a language packages into `dist/`, that directory is this command's output and is emptied before the build refills it, so a binary from an earlier build cannot reach a release; where a language has no packaging adapter, `dist/` is left alone. Not part of the gate: packaging is not a check
- `scripts/structure` — audit where files sit against the Layout rules below; called by `scripts/check` and by pre-commit on every commit
- `scripts/github-parity` — refuse a divergence between `.github/` and the payload copy at `apps/github-repository-template/src/base-repo/.github/`; called by `scripts/check` and by pre-commit on every commit. It reports rather than repairs, so a Dependabot bump merged into the root only fails until it is mirrored

Every check runs for every language present, not the first one detected. Results distinguish `pass`, `not-applicable`, `unavailable`, and `FAIL`, so an intentional no-op cannot look like a runner that executed. See `scripts/CLAUDE.md` before adding a language or a check.

The only code this repository runs beyond shell is the Python under `apps/repo-builder/`, and detection reads a root manifest, so the root `pyproject.toml` exists to declare it — that is what puts ruff, ty, and pytest over that unit, and what makes `scripts/doctor` require `uv`. It configures two things. `testpaths`, which bounds pytest to that unit's suite so a `.py` added under `src/base-repo/` is collected as the generated repository's file it is rather than as a test of this one; ruff and ty get no `include`, since one would not widen what they see — it would narrow them to that path and drop any Python later added under `apps/` or `libs/`. And the formatter's `exclude = ["*.md"]`, because `*.md` is in ruff's own default include list and `ruff format` rewrites the Python fenced inside one, which would put `scripts/fix` in the business of editing the payload under `src/base-repo/` and the frozen plans in `docs/plans/`. The file is root-only and must never be mirrored into the payload: a generated repository has no repo-builder unit and would be declaring a language it does not have.

## Git

- Pre-commit blocks direct commits to `main` and `master`. Branch before you start; a commit attempted on either fails at the hook, not at review.
- Run `scripts/check` before committing. It runs the same checks CI does, plus pre-commit across every file rather than the staged ones. The same checks, not the same tool versions: CI installs its toolchains fresh while this runs the machine's, so a lint can pass here and fail there — `scripts/CLAUDE.md` carries the rule.
- These prompt for approval and cannot be assumed: `git reset --hard`, `git clean`, `git rebase`, `rm` and `git rm`, and the `gh` commands that merge pull requests, cut releases, or delete the repository.
- So do these paths, whether the change creates or modifies: any dotfile or dot-folder, anything under the payload's `src/`, and anything directly in the repository root. Only the payload rule lives in this repository's `.claude/settings.json`, since it protects a boundary specific to this repo; the rest, and the `rm` rules above, come from the operator's global `~/.claude/settings.json`. It names `apps/github-repository-template/src/**` rather than every `src/`: the prompt asks whether a change belongs to the payload or to the root, and `apps/repo-builder/src/` is a source tree where that question has no meaning.
- Work reaches `main` through a pull request, where `.github/PULL_REQUEST_TEMPLATE.md` applies. A ruleset enforces this at the remote; see Repository settings below.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/#specification): `type(optional scope): subject`, a blank line, then the body. commitlint enforces it at `commit-msg` and the rules live in `.commitlintrc.yaml`, so a malformed message fails at the hook rather than at review. The subject is lowercase after the type and takes no trailing period. A body is optional to the tool and expected here — the session that made the change ends with it, and the body is the only surviving record of why.
- Every commit carries a `Generated-By: <model>` trailer, required by `trailer-exists` in `.commitlintrc.yaml`. `scripts/attribute-commit` writes it at `prepare-commit-msg`, rewriting Claude Code's `Co-Authored-By: <model> <noreply@anthropic.com>` — a tool is not a co-author, and the model name is the only per-commit record of what produced the change. A human co-author keeps their own `Co-Authored-By:` line. The script rewrites and never inserts, so a message with no agent trailer is refused at `commit-msg`: a commit written by hand adds its own `Generated-By:` line rather than passing unnoticed, and a clone that never ran `pre-commit install` fails loudly instead of committing unattributed.
- A merge subject is generated by GitHub and sits on commitlint's default ignore list, so it passes untouched and needs no second check in CI.
- A changed `CHANGELOG.md` is structurally checked at `pre-push` and again for its pull-request range in CI. That validates an entry chosen for review; it does not decide whether a change owes one.
- This repository keeps no `CHANGELOG.md` of its own — it is a repository addon, held back at `apps/github-repository-template/src/repository-addons/CHANGELOG.md` for a generated repository to adopt. The check still fires here when that addon template is edited, which is the only changelog this tree has.
- The commit type is a signal about the changelog, not a rule for it. `feat`, `fix`, and anything carrying `!` or a `BREAKING CHANGE:` footer usually owe an entry; `docs`, `style`, `test`, `ci`, and `chore` usually owe none. Notability is still judged per pull request.
- Plan mode writes to `docs/plans/`, which is tracked. A plan lands in the diff alongside the code it describes.

## Layout

Where a new file goes, restated for a reader. Every rule here that is a question about placement is enforced by `scripts/structure`, which holds them as code rather than as a copy of this prose; it also checks the values in a unit's declaration and reports `not-applicable` for the three rules that are neither. The orphan-manifest rule at the end is `libs/detect.sh`'s, since it is the one that needs a language.

**Root holds only these, and everything at root is repo-wide in scope.** `libs/`, `tests/`, `scripts/`, `tools/`, `deploy/`, and `assets/` here hold only what is shared across apps or operates on the whole repository; anything scoped to one app or domain belongs under that app.

- `.claude/` — agent configuration for this repository
- `.devcontainer/` — the dev container definition, an addition by occasion
- `.github/` — CI/CD workflows and repository automation
- `apps/` — deployable units, see below
- `docs/` — repository-wide documentation
- `libs/` — code shared across several apps
- `scripts/` — every portable shell script, whether a person or a workflow runs it
- `tests/` — cross-app and end-to-end tests only
- `tools/` — helpers that must be built before they run, one directory per program with its own manifest. The split from `scripts/` is by artifact, not by caller; a script written for CI is the first thing someone runs locally to reproduce a failure
- `deploy/` — infrastructure and deployment, in one folder per technology: `quadlet/`, `containerfile/`, `compose/`, `systemd/`, `env/`. Only those five, and no loose files beside them
- `assets/` — static non-code files shared across several apps
- `gradle/` — the Gradle wrapper, which Gradle itself writes and locates by that name
- `tmp/` — gitignored scratch space

Root *files* are permitted by name rather than by pattern: the eight the template ships, `.repo-template.json`, `.structure-allow`, `CONTEXT.md` and `CONTEXT-MAP.md`, every addition by occasion, and the root workspace manifests and lockfiles of five of the six supported languages — Swift has no root manifest, for the reason the orphan-manifest rule below gives. `.gitkeep` is permitted anywhere, since holding an empty directory open is what it is for. Anything else needs permission, recorded in `.structure-allow`.

**`apps/` breaks the project into its smallest deployable units.** There may be only one.

- Each unit is one folder under `apps/`: the smallest piece of this repository delivered on its own — deployed, installed, published, or copied. A file sitting directly in `apps/` belongs to no unit.
- Split a unit into domains only when it spans distinct business areas that benefit from isolation. Each domain is one folder under its unit and holds its own `src/`. That `src/` is what tells a domain from a misspelled scoped folder — the unit level cannot be an allowlist, since a domain name is yours to choose — so a folder under a unit without one is a finding rather than a new domain. Below a domain the vocabulary does close: `src/`, a scoped folder, or the domain's own files. Domains do not nest.
- `src/` sits under the unit when there are no domains, and under each domain when there are. Never both, and never `apps/src/`.
- A unit or domain may hold its own `libs/`, `tests/`, `scripts/`, `docs/`, `tools/`, `deploy/`, or `assets/`, scoped strictly to it.

**Every unit declares how it runs and what it ships**, in a `.unit.json` at the unit's root — never at a domain's. Neither fact is on disk: a Go module with one `main` package is a CLI, a TUI, or a service, and the compiler cannot tell them apart. `docs/adrs/0001-declare-unit-delivery-as-two-facts.md` has the reasoning; read it before changing the shape.

```json
{ "schema_version": 1, "run": "oneshot", "ships": { "kind": "executable", "targets": ["linux-amd64"] } }
```

- `run` — `oneshot` for a process that exits on its own, `longlived` for one that runs until stopped, `none` for a unit with nothing to run.
- `ships.kind` — `executable`, `quadlet`, or `none`.
- `ships.targets` — required exactly when the kind is `executable`, rejected on every other kind. The vocabulary is the template's own and each language adapter translates it: `linux-amd64`, `macos-arm64`.

The two facts vary independently, so every pairing is legal and the audit checks values alone. A scheduled job runs `oneshot` and ships a `quadlet`; a library runs `none` and still ships. A rule forbidding a combination is a rule nobody revisits when the exception arrives.

Reading the file needs `jq`, which `scripts/doctor` requires. Without it the audit reports `unavailable` and fails rather than passing over a file it never opened, and the suites that exercise a unit skip every case.

**Scoped folders nest freely, but never hold a `src/`.** `libs/`, `tests/`, `scripts/`, `tools/`, `assets/`, `docs/`, and `deploy/` may nest a different kind — `scripts/tests/libs/` — and may nest their own kind, since `tests/` for the tests under `tests/` is a real arrangement. Choose the folder whose scope matches the file's scope.

**`apps/` is not a scope holder.** The scope holders are the root, a unit, and a domain, so the segment directly under `apps/` is a unit name and is never read as a scoped folder however it is spelled. `apps/docs/`, `apps/tests/`, `apps/scripts/`, and `apps/deploy/` are ordinary units. The rules resume at the unit: `apps/docs/docs/notes.yaml` still needs permission and `apps/api/docs/src/` is still a `src/` under a scope holder.

**Every rule that reads depth stops at the first `src/`.** Below one, the arrangement belongs to the language rather than to this repository: a Go package named `docs/`, a Python `scripts/` module, a generated or vendored tree whose shape nobody here chose. So `apps/api/src/internal/docs/swagger.json` is fine and `apps/api/docs/swagger.json` is not, and a `src/` nested inside a `src/` is the source tree's own business. The rules govern the tree around the source, and the source is where they stop.

**`docs/` takes Markdown freely at every scope**; anything else needs permission. `.gitkeep` is exempt everywhere.

**`.structure-allow` is where permission is recorded.** A bare path allows that one file. A path ending in `/` names a prefix the audit stops descending into, which is how a vendored dependency or a tracked test fixture keeps a shape that is not this repository's to decide, without the rules growing an exception clause that would hollow them out. The one place it still looks inside is a domain's own `src/`: without that lookup a prefix entry would turn the domain rule stricter rather than more lenient.

Three rules are about content rather than placement and no script can settle them: whether `libs/` really holds what several apps share, whether `tests/` really spans them, and whether a file sits at the scope it belongs to. `scripts/structure` reports all three `not-applicable` rather than inferring them from paths.

A package anywhere in the tree whose language has no root manifest fails the run rather than passing, because for the languages this rule covers the root manifest is what lists it: `go list -m` names the `use` entries in `go.work` and nothing else, and the Gradle settings file the same. Swift is excluded deliberately — it has no root manifest, so its packages are found by searching and nested ones are how a Swift repository is supposed to look. The failure names the root manifest to add.

## Repository settings

Some guarantees these files make are only half-kept by the files themselves. Current state on `possiblyneal/template`:

- Dependabot alerts and security updates: **enabled**. `scripts/security` fails a pull request introducing a CVE; these open the pull request that resolves it.
- Secret scanning and push protection: **enabled**. This repository is public, which is what made them available; GitHub offers neither on a private repository on this plan. Push protection refuses a push carrying a recognized secret, and it is enforced at the remote, where no `--no-verify` reaches. gitleaks in `.pre-commit-config.yaml` still runs at commit and still sees formats GitHub's providers do not, so it is the earlier check rather than a redundant one.
- Branch rulesets: **active on `main`**, named `main`, with no bypass actors — an administrator disabling the ruleset is the only way past it. It requires a pull request, restricts the merge to a true merge commit, refuses deletion and non-fast-forward, and requires `CI` and `Security` and no other check; `apps/repo-builder/src/references/generate.md` has why a name from CodeQL's language matrix does not belong in that list. `required_approving_review_count` is `0`, because GitHub refuses self-approval with HTTP 422 and any higher number leaves a solo pull request unmergeable; the `code-reviewed` label and its `Reviewed-Head:` comment stand in for the approval. `strict_required_status_checks_policy` is off, since `/land` already runs the full local gate when the base moved. It lives at the remote, so no `--no-verify` reaches it and a fresh clone is covered before `pre-commit install` runs; `no-commit-to-branch` and `scripts/protect-branch` stay useful as the earlier, faster refusal — they refuse a commit made while HEAD is `main`, and a push whose destination ref is `main`, the case the first cannot see.
- Automatic head branch deletion: **enabled**. GitHub deletes the head ref when a pull request merges, so the remote branch list stays the set of work in flight; the local branch and its remote-tracking ref survive until `git fetch --prune`. `scripts/repo-settings check` reports it, and it is a checkbox rather than a workflow on purpose — deleting the head ref from Actions means a `pull_request: closed` job holding `contents: write` to reimplement a setting GitHub offers on every plan.
- Code scanning: **enabled**. `.github/workflows/codeql.yml`'s `scanning` job finds the repository public, so `detect` and `analyze` run over actions and python rather than appearing on the checks list as skipped. The stand-down path beside it is still correct, because the payload ships to repositories that are private; `docs/LESSONS.md` has why it goes green there rather than failing. `generation.features` is empty, since nothing is omitted by choice.
- GitHub Actions: **verified**. `ci.yml` and `security.yml` pass on `main`.

Those three are free on a public repository and unavailable on a private one on this plan, so a generated repository that stays private still reports them `not offered for the plan` — the case `scripts/repo-settings check` reads against most destinations, and the reason its stand-down paths are exercised there rather than here.

## Agent skills

### Issue tracker

GitHub Issues on `possiblyneal/template`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The seven canonical roles, unrenamed. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` at the root, ADRs in `docs/adrs/`. See `docs/agents/domain.md`.

## Child Index

- `apps/github-repository-template/CLAUDE.md` — the template payload and the reference docs explaining it
- `apps/repo-builder/CLAUDE.md` — the `/repo-builder` skill, and how it is linked into a clone
- `scripts/CLAUDE.md` — the language-capabilities interface, and what adding a language or check requires
- `docs/CLAUDE.md` — ADRs, specs, plans, and lessons

Read the nearest `CLAUDE.md` above every path you touch before editing, and update the owning file after meaningful changes.
