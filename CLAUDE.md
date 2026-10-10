## Mission

This repository builds repositories for AI agents first and people second.

Every repository generated from it shares one shape: the same folders, the same commands, the same checks, and the same kinds of docs in the same places. What is shared is that each file exists and where it sits, not what it says. The program and its files differ from one repository to the next, and so do the contents of the files that describe it: every repository has a `CLAUDE.md` and a `docs/LESSONS.md`, but each holds that repository's own contract and lessons. So does local configuration: every repository has a `.env`, and some fill it. An addon is part of the shape too: a repository adopts it only when it has a reason to, but once adopted it sits where it sits everywhere else. An agent that has learned one repository has learned the rest, so it spends its context on the task instead of on finding its way around.

Judge every structural decision by four questions:

1. **Is it the same everywhere?** If a repository needs its structure to differ, that's a gap in the template. Fix it here so every repository gets the fix, rather than letting one repository drift on its own.
2. **Can an agent find it without searching?** A file's location should follow from what the file is, so the path can be predicted before anything is opened.
3. **Does it cost fewer tokens to understand?** The nearest `CLAUDE.md`, the glossary, and one command per job should answer what would otherwise take a sweep of the tree.
4. **Is the work as good or better?** Saving tokens never justifies a worse result. If a shortcut makes the agent's output worse, it doesn't belong here.

When something is easy for an agent to navigate, a person can usually navigate it too. Where the two needs conflict, the agent's needs win.

## What this repository is

This repository builds other repositories, and holds two trees that must not be confused:

- **Live configuration** — `scripts/`, `.github/`, `.claude/`, and the root dotfiles govern *this* repository.
- **Template payload** — `apps/github-repository-template/src/base-repo/` is copied into every generated repository. Editing it changes future repositories and nothing here.

The trees hold near-identical files, so decide which one a change belongs to before editing: a root-only fix leaves the template shipping the bug, and a payload-only fix leaves this repository running it. Editing under `apps/github-repository-template/src/` prompts for approval to keep that choice deliberate.

The root was generated from its own payload, plus repository-specific merges. `.repo-template.json` records the payload commit it was last reconciled with and marks `apps/**` as product, so an update never overwrites the payload. It names this file managed: an unmatched path is product-owned, which would put this file beyond every update.

`apps/github-repository-template/docs/github_repository_structure.md` is the payload's structure and bill of materials. Read it before changing what the template ships.

## Commands

Use these instead of per-language tools; each detects the languages present and fails when an expected check cannot run. The payload's `CLAUDE.md` Template Contract restates this section and Layout as bare rules; `apps/github-repository-template/CLAUDE.md` owns keeping them in step. Each script's header comment carries its full reasoning.

- `scripts/doctor` — verify local toolchains, dependencies, hooks, and configuration without contacting hosted services
- `scripts/repo-settings check` — inspect GitHub-hosted security and branch settings; run explicitly, since it needs the network and administration visibility
- `scripts/check` — the full local gate: `doctor`, the script tests, lint, format, type check, test, build, the security audit, and pre-commit over every file, tracked and untracked. It reads no hosted GitHub state but is not offline: `commitlint-test` and pre-commit's hook environments fetch on first use
- `scripts/fix` — the write half of `check`: lint autofix, then formatting, for every stack, unconditionally and in that order so the formatter lays out what the linter rewrote. Go, Swift and Kotlin have no lint autofix and report `lint-fix` `not-applicable`. A `lint-fix` FAIL means findings remain that need hand work
- `scripts/summarize <command…>` — run a check and print only its Result table with findings, exiting with that command's status; read `check` and `ci` output through this
- `scripts/clean` — recursively delete build output and tool caches (`dist`, `build`, `coverage`, `__pycache__`, `.*_cache`, `*.pyc`)
- `scripts/run [unit] [--entry <name>] [-- args…]` — start a unit per its declared `run` fact. The unit name is required when `apps/` holds several; `--entry` names one program from the unit's own language manifest (a `[project.scripts]` name, a `bin` key, a main package's import path) and is required when it declares several. Arguments after `--` pass through unchanged
- `scripts/integration` — run every `tests/integration/` tier, at any scope. Kept out of the gate, since a tier may need a database, container, or network the gate cannot assume
- `scripts/package [unit]` — deliver what the unit ships: an executable per declared target into its `dist/`, emptied first so no stale binary reaches a release, or its `deploy/quadlet/` files validated. Not part of the gate
- `scripts/structure` — audit file placement against Layout below; run by `scripts/check` and by pre-commit on every commit
- `scripts/github-parity` — refuse a divergence between `.github/` and the payload's copy; run by `scripts/check` and by pre-commit. It reports rather than repairs, so a Dependabot bump merged into the root fails until it is mirrored

Every check runs for every language present. Results distinguish `pass`, `not-applicable`, `unavailable`, and `FAIL`, so an intentional no-op cannot look like a runner that executed. See `scripts/CLAUDE.md` before adding a language or a check.

The only non-shell code here is the Python under `apps/repo-builder/`, declared by the root `pyproject.toml`. Detection reads it, which puts ruff, ty, and pytest over that unit and makes `scripts/doctor` require `uv`. It is root-only and never mirrored into the payload, whose repositories have no such unit. It sets:

- `testpaths`, bounding pytest to that unit so a payload `.py` is not collected as a test here. ruff and ty get no `include`: one would narrow them to that path rather than widen them.
- the formatter's `exclude = ["*.md"]`, since `ruff format` rewrites Python fenced in Markdown, which would put `scripts/fix` in the business of editing the payload and the frozen plans in `docs/plans/`.
- `addopts`, running the suite with a worker per CPU through pytest-xdist, since it waits on git and subprocesses; `-n 0` runs it serially.

## Git

- Pre-commit blocks commits to `main` and `master`; branch first.
- Run `scripts/check` before committing. It runs CI's checks plus pre-commit over every file, but with the machine's tool versions rather than CI's fresh installs, so a lint can pass here and fail there; `scripts/CLAUDE.md` carries the rule.
- These prompt for approval: `git reset --hard`, `git clean`, `git rebase`, `rm`, `git rm`, and the `gh` commands that merge pull requests, cut releases, or delete the repository. So does creating or editing any dotfile or dot-folder, anything under the payload's `src/`, and anything directly in the root. Only the payload rule lives in this repository's `.claude/settings.json`; the rest come from the operator's global `~/.claude/settings.json`. It names `apps/github-repository-template/src/**`, not every `src/`, because the payload-or-root question means nothing for `apps/repo-builder/src/`.
- Work reaches `main` through a pull request under `.github/PULL_REQUEST_TEMPLATE.md`; a ruleset enforces it (Repository settings below).
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/#specification): `type(optional scope): subject`, a blank line, then the body. commitlint enforces it at `commit-msg`, with rules in `.commitlintrc.yaml`. The subject is lowercase after the type, with no trailing period. A body is expected: it is the only surviving record of why.
- Every commit carries a `Generated-By: <model>` trailer, required by `trailer-exists` in `.commitlintrc.yaml`. `scripts/attribute-commit` writes it at `prepare-commit-msg` by rewriting Claude Code's `Co-Authored-By: <model> <noreply@anthropic.com>`, since a tool is not a co-author; a human's `Co-Authored-By:` stays. It never inserts one, so a commit written by hand adds its own line or is refused at `commit-msg`.
- GitHub's generated merge subjects are on commitlint's default ignore list and need no CI check.
- A changed `CHANGELOG.md` is structurally checked at `pre-push`, and in CI over the pull-request range; that validates an entry, not whether one was owed. This repository keeps none: `CHANGELOG.md` is an addon at `apps/github-repository-template/src/repository-addons/CHANGELOG.md`, the only changelog the check fires on here.
- The commit type signals a changelog entry without deciding it: `feat`, `fix`, and anything with `!` or a `BREAKING CHANGE:` footer usually owe one; `docs`, `style`, `test`, `ci`, and `chore` usually do not. Notability is judged per pull request.
- Plan mode writes to the tracked `docs/plans/`, so a plan lands in the diff with its code.

## Layout

Where a new file goes. `scripts/structure` enforces every placement rule here as code, checks a unit declaration's values, and reports the three content rules `not-applicable`. The orphan-manifest rule at the end is `libs/detect.sh`'s, since it needs a language.

**Root holds only these, and everything at root is repo-wide.** Root `libs/`, `tests/`, `scripts/`, `tools/`, `deploy/`, and `assets/` hold only what spans apps or operates on the whole repository; anything scoped to one app belongs under that app.

- `.claude/` — agent configuration for this repository
- `.devcontainer/` — the dev container, an addition by occasion
- `.github/` — CI/CD workflows and repository automation
- `apps/` — deployable units, below
- `docs/` — repository-wide documentation
- `libs/` — code shared across apps
- `scripts/` — every portable shell script, whoever runs it
- `tests/` — cross-app and end-to-end tests only
- `tools/` — helpers built before they run, one directory per program with its own manifest. The split from `scripts/` is by artifact, not caller: a CI script is the first thing run locally to reproduce a failure
- `deploy/` — one folder per technology: `quadlet/`, `containerfile/`, `compose/`, `systemd/`, `env/`, and no loose files
- `assets/` — static non-code files shared across apps
- `gradle/` — the Gradle wrapper, which Gradle writes and locates by that name
- `tmp/` — gitignored scratch space

Root *files* are permitted by name: the eight the template ships, `.repo-template.json`, `.structure-allow`, `GLOSSARY.md`, `GLOSSARY-MAP.md`, every addition by occasion, and the root workspace manifests and lockfiles of five of the six languages (Swift has none; see the orphan-manifest rule). `.gitkeep` is permitted anywhere. Anything else needs an entry in `.structure-allow`.

**`apps/` holds the smallest deployable units**, possibly just one.

- A unit is one folder under `apps/`: the smallest piece delivered on its own, whether deployed, installed, published, or copied. A file directly in `apps/` belongs to no unit.
- Split a unit into domains only for distinct business areas that benefit from isolation. Each domain is a folder under its unit with its own `src/`, which is what tells a domain from a misspelled scoped folder, so a folder under a unit without one is a finding. Below a domain only `src/`, scoped folders, and the domain's own files are allowed. Domains do not nest.
- `src/` sits under the unit, or under each domain when there are domains. Never both, and never `apps/src/`.
- A unit or domain may hold its own `libs/`, `tests/`, `scripts/`, `docs/`, `tools/`, `deploy/`, or `assets/`, scoped to it. A unit, never a domain, may hold a gitignored `state/` at its root; see the rule on files a program writes.

**Every unit declares how it runs and what it ships** in a `.unit.json` at the unit's root, never a domain's. Neither fact is on disk: a Go module with one `main` package could be a CLI, a TUI, or a service. `docs/adrs/0001-declare-unit-delivery-as-two-facts.md` has the reasoning; read it before changing the shape.

```json
{ "schema_version": 1, "run": "oneshot", "ships": { "kind": "executable", "targets": ["linux-amd64"] } }
```

- `run` — `oneshot` (exits on its own), `longlived` (runs until stopped), or `none` (nothing to run).
- `ships.kind` — `executable`, `quadlet`, or `none`.
- `ships.targets` — required exactly when the kind is `executable`, rejected otherwise. The template's own vocabulary, which each language adapter translates: `linux-amd64`, `macos-arm64`.

The two facts vary independently and every pairing is legal: a scheduled job runs `oneshot` and ships a `quadlet`; a library runs `none` and still ships. The audit checks values only, since a rule forbidding a combination is one nobody revisits when the exception arrives.

Reading the file needs `jq`, which `scripts/doctor` requires. Without it the audit reports `unavailable` and fails, and the suites that exercise a unit skip every case.

**`tests/integration/` is the integration tier**, at any scope holder. It needs no placement rule, since `tests/` may nest its own kind; the name matters only to the capabilities: `scripts/integration` runs it and the gate does not. pytest and `go test ./...` discover by walking the tree, so their exclusion is wired; the other four languages declare their test set (an npm script, a Gradle source set, a SwiftPM or Cargo test target), and that declaration leaves the tier out.

**Scoped folders nest freely but never hold a `src/`.** `libs/`, `tests/`, `scripts/`, `tools/`, `assets/`, `docs/`, and `deploy/` may nest another kind (`scripts/tests/libs/`) or their own (`tests/` under `tests/`). Choose the folder whose scope matches the file's.

**`apps/` is not a scope holder.** The scope holders are the root, a unit, and a domain, so the segment directly under `apps/` is always a unit name: `apps/docs/` and `apps/tests/` are ordinary units. The rules resume at the unit: `apps/docs/docs/notes.yaml` still needs permission, and `apps/api/docs/src/` is still a `src/` under a scope holder.

**Every rule that reads depth stops at the first `src/`.** Below it the language decides, whether a Go package named `docs/`, a Python `scripts/` module, or a vendored tree. So `apps/api/src/internal/docs/swagger.json` is fine, `apps/api/docs/swagger.json` is not, and a `src/` inside a `src/` is the source tree's own business.

**No file a program writes is tracked.** What a program only reads is an asset, in the `assets/` at its scope. What it writes while running, such as a save file, a session, or its own cache, goes in its unit's `state/`, gitignored as `/apps/*/state/`, so a run, a test included, leaves git as it found it. The pattern is anchored to the unit root so a source package named `state/` below `src/` stays tracked; a re-clone or `git clean -x` loses it. A file the operator edits by hand is an asset, and so is a record the program wrote once and will not write again, such as a finished season: its snapshot is tracked under `assets/` and read when `state/` holds no working copy. No script checks this rule: it is about what a program does with a file, not where the file sits.

**`docs/` takes Markdown freely at every scope**; anything else needs permission. `.gitkeep` is exempt everywhere.

**`.structure-allow` records permission.** A bare path allows one file. A path ending in `/` is a prefix the audit stops descending into, for a vendored dependency or tracked fixture whose shape is not this repository's to decide. The one place it still looks inside is a domain's own `src/`, without which a prefix entry would make the domain rule stricter.

Three rules are about content, and no script can settle them: whether `libs/` holds what several apps share, whether `tests/` spans them, and whether a file sits at its own scope. `scripts/structure` reports them `not-applicable` rather than guessing from paths.

A package whose language has no root manifest fails the run, because that manifest is what lists it: `go list -m` names only `go.work`'s `use` entries, and the Gradle settings file likewise. Swift is excluded: it has no root manifest, and nested packages are how a Swift repository is meant to look. The failure names the root manifest to add.

## Repository settings

Some guarantees these files make depend on hosted settings. Current state on `possiblyneal/template`:

- Dependabot alerts and security updates: **enabled**. `scripts/security` fails a pull request introducing a CVE; these open the pull request that resolves it.
- Secret scanning and push protection: **enabled**, available because the repository is public. Push protection refuses a push carrying a recognized secret at the remote, beyond any `--no-verify`. gitleaks in `.pre-commit-config.yaml` still runs earlier and sees formats GitHub's providers do not.
- Branch rulesets: **active on `main`**, named `main`, with no bypass actors. It requires a pull request, a true merge commit, and the three checks that report on every pull request: `CI`, `Security`, and CodeQL's `Code scanning enabled` (`apps/repo-builder/src/references/generate.md` has why no language-matrix name is required). It refuses deletion and non-fast-forward. `required_approving_review_count` is `0` and `require_extra_approval_for_unattributed_changes` is off, because GitHub refuses self-approval with HTTP 422 and either would leave a solo pull request unmergeable; the `code-reviewed` label and its `Reviewed-Head:` comment stand in for approval. `strict_required_status_checks_policy` is off, leaving a stale base to `/land`, which runs the full local gate when the base moved; the GitHub merge button does not. The ruleset applies before a fresh clone runs `pre-commit install`; `no-commit-to-branch` and `scripts/protect-branch` stay as the earlier, faster refusal.
- Automatic head branch deletion: **enabled**, so the remote branch list stays the work in flight; local branches survive until `git fetch --prune`. It is a checkbox rather than a workflow, which would need a `contents: write` job to reimplement a free setting. `scripts/repo-settings check` reports it.
- Code scanning: **enabled**. `.github/workflows/codeql.yml`'s `scanning` job finds the repository public, so `detect` and `analyze` run over actions and python. The stand-down path stays for private generated repositories; `docs/LESSONS.md` has why it goes green there. `generation.features` is empty, since nothing is omitted by choice.
- GitHub Actions: **verified**. `ci.yml` and `security.yml` pass on `main`.

Secret scanning, push protection, code scanning, and rulesets are free on a public repository and unavailable on a private one on this plan, so a generated repository that stays private does without all four. `scripts/repo-settings check` reports push protection and rulesets `not offered for the plan` there, which is where its stand-down paths are exercised.

## Agent skills

### Issue tracker

GitHub Issues on `possiblyneal/template`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The seven canonical roles, unrenamed. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` at the root, ADRs in `docs/adrs/`. See `docs/agents/domain.md`.

## Child Index

- `apps/github-repository-template/CLAUDE.md` — the template payload and the reference docs explaining it
- `apps/repo-builder/CLAUDE.md` — the `/repo-builder` skill, and how it is linked into a clone
- `scripts/CLAUDE.md` — the language-capabilities interface, and what adding a language or check requires
- `docs/CLAUDE.md` — ADRs, specs, plans, research records, and lessons

Read the nearest `CLAUDE.md` above every path you touch before editing, and update the owning file after meaningful changes.
