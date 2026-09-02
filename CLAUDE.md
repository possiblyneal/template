## What this repository is

This repository builds other repositories. It holds two trees and they must not be confused:

- **Live configuration** — `scripts/`, `.github/`, `.claude/`, and the root dotfiles govern *this* repository, the same way they govern any other.
- **Template payload** — `apps/github-repository-template/src/base-repo/` is the content copied into repositories generated from this one. Editing a file there changes every future generated repository and changes nothing here.

The two trees hold near-identical files. Before editing, decide which one the change belongs to: a fix applied only at the root leaves the template shipping the bug, and a fix applied only in the payload leaves this repository running it. Editing under `src/` prompts for approval so the choice stays deliberate.

This repository was generated from its own payload, so the root files are that payload plus repository-specific merges. `.repo-template.json` records the payload commit the root was last reconciled with, and marks `apps/**` as product so an update never overwrites the payload that produced it.

`apps/github-repository-template/docs/github_repository_structure.md` is the structure and bill of materials for the payload, naming briefly what each file and folder is for. Read it before changing what the template ships, to see where a file belongs and what it is there to do.

## Commands

Use these instead of per-language tools; each detects the languages present and fails when an expected check cannot run.

- `scripts/doctor` — verify local toolchains, dependencies, hooks, and configuration without contacting hosted services
- `scripts/repo-settings check` — inspect GitHub-hosted security and branch settings; run explicitly because it needs network access and repository administration visibility
- `scripts/check` — full local gate: `doctor`, the script tests, then lint, format, type check, test, build, then the security audit and pre-commit across every file, tracked and untracked, not just staged ones. Local means it reads no hosted GitHub state, not that it stays offline: `commitlint-test` and pre-commit's own hook environments fetch on first use
- `scripts/fix` — rewrite formatting for every detected stack; the write half of `check`'s format check, no lint autofixes
- `scripts/clean` — recursively delete build output and tool caches (`dist`, `build`, `coverage`, `__pycache__`, `.*_cache`, `*.pyc`)
- `scripts/run [unit] [-- args…]` — start the unit, dispatching on the `run` fact it declared; requires the unit name when `apps/` holds several, since a run is one foreground process. Everything after `--` reaches the program unchanged
- `scripts/package [unit]` — deliver what the unit declared it ships: an executable per declared target into the unit's `dist/`, or a `deploy/quadlet/` pair validated and nothing built. Where a language packages into `dist/`, that directory is this command's output and is emptied before the build refills it, so a binary from an earlier build cannot reach a release; where a language has no packaging adapter, `dist/` is left alone. Not part of the gate: packaging is not a check
- `scripts/structure` — audit where files sit against the Layout rules below; called by `scripts/check` and by pre-commit on every commit

Every check runs for every language present, not the first one detected. Results distinguish `pass`, `not-applicable`, `unavailable`, and `FAIL`, so an intentional no-op cannot look like a runner that executed. See `scripts/CLAUDE.md` before adding a language or a check.

The only code this repository runs beyond shell is the Python under `.claude/skills/repo-builder/`, and detection reads a root manifest, so the root `pyproject.toml` exists to declare it — that is what puts ruff, ty, and pytest over the skill, and what makes `scripts/doctor` require `uv`. It configures two things. `testpaths`, because pytest's default `norecursedirs` skips `.*`; ruff and ty walk into a dot-directory unasked, so an `include` naming the skill would not widen what they see — it would narrow them to that path and drop any Python later added under `apps/` or `libs/`. And the formatter's `exclude = ["*.md"]`, because `*.md` is in ruff's own default include list and `ruff format` rewrites the Python fenced inside one, which would put `scripts/fix` in the business of editing the payload under `src/base-repo/` and the frozen plans in `docs/plans/`. The file is root-only and must never be mirrored into the payload: a generated repository has no repo-builder skill and would be declaring a language it does not have.

## Git

- Pre-commit blocks direct commits to `main` and `master`. Branch before you start; a commit attempted on either fails at the hook, not at review.
- Run `scripts/check` before committing. It runs the same checks CI does, plus pre-commit across every file rather than the staged ones.
- These prompt for approval and cannot be assumed: `git reset --hard`, `git clean`, `git rebase`, `rm` and `git rm`, and the `gh` commands that merge pull requests, cut releases, or delete the repository.
- So do these paths, whether the change creates or modifies: any dotfile or dot-folder, anything under a `src/` directory, and anything directly in the repository root. Only the `src/` rule lives in this repository's `.claude/settings.json`, since it protects a boundary specific to this repo; the rest, and the `rm` rules above, come from the operator's global `~/.claude/settings.json`.
- Work reaches `main` through a pull request, where `.github/PULL_REQUEST_TEMPLATE.md` applies.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/#specification): `type(optional scope): subject`, a blank line, then the body. commitlint enforces it at `commit-msg` and the rules live in `.commitlintrc.yaml`, so a malformed message fails at the hook rather than at review. The subject is lowercase after the type and takes no trailing period. A body is optional to the tool and expected here — the session that made the change ends with it, and the body is the only surviving record of why.
- Pull requests merge; they are neither squashed nor rebased. A merge subject is generated by GitHub and sits on commitlint's default ignore list, so it passes untouched and needs no second check in CI.
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

**Scoped folders are leaves for their own kind.** `libs/`, `tests/`, `scripts/`, `tools/`, `assets/`, `docs/`, and `deploy/` may nest a different kind — `scripts/tests/libs/` is fine — but never another of the same kind at any depth, and never a `src/`. Choose the folder whose scope matches the file's scope.

**`apps/` is not a scope holder.** The scope holders are the root, a unit, and a domain, so the segment directly under `apps/` is a unit name and is never read as a scoped folder however it is spelled. `apps/docs/`, `apps/tests/`, `apps/scripts/`, and `apps/deploy/` are ordinary units. The rules resume at the unit: `apps/docs/docs/notes.yaml` still needs permission and `apps/api/docs/src/` is still a `src/` under a scope holder.

**Every rule that reads depth stops at the first `src/`.** Below one, the arrangement belongs to the language rather than to this repository: a Go package named `docs/`, a Python `scripts/` module, a generated or vendored tree whose shape nobody here chose. So `apps/api/src/internal/docs/swagger.json` is fine and `apps/api/docs/swagger.json` is not, and a `src/` nested inside a `src/` is the source tree's own business. The rules govern the tree around the source, and the source is where they stop.

**`docs/` takes Markdown freely at every scope**; anything else needs permission. `.gitkeep` is exempt everywhere.

**`.structure-allow` is where permission is recorded.** A bare path allows that one file. A path ending in `/` names a prefix the audit stops descending into, which is how a vendored dependency or a tracked test fixture keeps a shape that is not this repository's to decide, without the rules growing an exception clause that would hollow them out. The one place it still looks inside is a domain's own `src/`: without that lookup a prefix entry would turn the domain rule stricter rather than more lenient.

Three rules are about content rather than placement and no script can settle them: whether `libs/` really holds what several apps share, whether `tests/` really spans them, and whether a file sits at the scope it belongs to. `scripts/structure` reports all three `not-applicable` rather than inferring them from paths.

A package anywhere in the tree whose language has no root manifest fails the run rather than passing, because for the languages this rule covers the root manifest is what lists it: `go list -m` names the `use` entries in `go.work` and nothing else, and the Gradle settings file the same. Swift is excluded deliberately — it has no root manifest, so its packages are found by searching and nested ones are how a Swift repository is supposed to look. The failure names the root manifest to add.

## Repository settings

Some guarantees these files make are only half-kept by the files themselves. Current state on `possiblyneal/template`:

- Dependabot alerts and security updates: **enabled**. `scripts/security` fails a pull request introducing a CVE; these open the pull request that resolves it.
- Push protection and branch rulesets: **unavailable** on this plan. So two local hooks are the whole of it: `no-commit-to-branch` refuses a commit made while HEAD is `main`, and `scripts/protect-branch` refuses a push whose destination ref is `main` — the case the first cannot see, since `git push origin HEAD:main` from a feature branch never makes HEAD `main`. Both live in each clone and both yield to `--no-verify`. gitleaks in `.pre-commit-config.yaml` is likewise the only check seeing a secret before it is pushed.
- Squash and rebase merging: **disabled**, leaving the merge commit as the only method. `scripts/repo-settings check` reports both and carries the reason; unlike code scanning below, they are offered on every plan.
- Automatic head branch deletion: **enabled**. GitHub deletes the head ref when a pull request merges, so the remote branch list stays the set of work in flight; the local branch and its remote-tracking ref survive until `git fetch --prune`. `scripts/repo-settings check` reports it, and it is a checkbox rather than a workflow on purpose — deleting the head ref from Actions means a `pull_request: closed` job holding `contents: write` to reimplement a setting GitHub offers on every plan.
- Code scanning: **unavailable**, and `.github/workflows/codeql.yml` is deleted here rather than left permanently failing — recorded as `"codeql": "omitted-by-choice"` under `generation.features` in `.repo-template.json`, the resolution the workflow's own error named. This repository has no static analysis coverage; the record is where that reads now. The payload still ships the workflow, and it uploaded cleanly on a public repository generated from that payload, so visibility is the only thing holding it back here. `docs/LESSONS.md` has the restore path and why nothing cheaper counts.
- GitHub Actions: **verified**. `ci.yml` and `security.yml` pass on `main`.

A generated repository is where a guarantee unavailable on this plan can actually be observed. Push protection, branch rulesets, and code scanning are all free on a public repository and unavailable on a private one here, so `scripts/repo-settings check` reports `not offered for the plan` against this repository whether or not the check works. Build a public repository from the payload to tell those apart.

## Agent skills

### Issue tracker

GitHub Issues on `possiblyneal/template`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The seven canonical roles, unrenamed. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` at the root, ADRs in `docs/adrs/`. See `docs/agents/domain.md`.

## Child Index

- `apps/github-repository-template/CLAUDE.md` — the template payload and the reference docs explaining it
- `scripts/CLAUDE.md` — the language-capabilities interface, and what adding a language or check requires
- `docs/CLAUDE.md` — ADRs, specs, plans, and lessons

Read the nearest `CLAUDE.md` above every path you touch before editing, and update the owning file after meaningful changes.
