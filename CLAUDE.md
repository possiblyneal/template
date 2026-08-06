## What this repository is

This repository builds other repositories. It holds two trees and they must not be confused:

- **Live configuration** — `scripts/`, `.github/`, `.claude/`, and the root dotfiles govern *this* repository, the same way they govern any other.
- **Template payload** — `apps/github-repository-template/src/base-repo/` is the content copied into repositories generated from this one. Editing a file there changes every future generated repository and changes nothing here.

The two trees hold near-identical files. Before editing, decide which one the change belongs to: a fix applied only at the root leaves the template shipping the bug, and a fix applied only in the payload leaves this repository running it. Editing under `src/` prompts for approval so the choice stays deliberate.

This repository was generated from its own payload, so the root files are that payload plus repository-specific merges. `.repo-template.json` records the payload commit the root was last reconciled with, and marks `apps/**` as product so an update never overwrites the payload that produced it.

`apps/github-repository-template/docs/github_repository_structure.md` is the reasoning behind every payload file. Read it before changing what the template ships; it explains what each file prevents, which is rarely visible from the file itself.

## Commands

Use these instead of per-language tools; each detects the languages present and fails when an expected check cannot run.

- `scripts/doctor` — verify local toolchains, dependencies, hooks, and configuration without contacting hosted services
- `scripts/repo-settings check` — inspect GitHub-hosted security and branch settings; run explicitly because it needs network access and repository administration visibility
- `scripts/check` — full local gate: `doctor`, the script tests, then lint, format, type check, test, build, then the security audit and pre-commit across every file, not just staged ones
- `scripts/fix` — rewrite formatting for every detected stack; the write half of `check`'s format check, no lint autofixes
- `scripts/clean` — recursively delete build output and tool caches (`dist`, `build`, `coverage`, `__pycache__`, `.*_cache`, `*.pyc`)
- `scripts/dev [app-name]` — start the dev server; requires the app name when several stacks are present, since only one process can run

Every check runs for every language present, not the first one detected. Results distinguish `pass`, `not-applicable`, `unavailable`, and `FAIL`, so an intentional no-op cannot look like a runner that executed. See `scripts/CLAUDE.md` before adding a language or a check.

This repository has no root language manifest, so `scripts/check` reports there is nothing to check and never reaches the Python under `.claude/skills/repo-builder/`. Run those tests directly: `uv run --with pytest python -m pytest .claude/skills/repo-builder/scripts/tests/`.

## Git

- Pre-commit blocks direct commits to `main` and `master`. Branch before you start; a commit attempted on either fails at the hook, not at review.
- Run `scripts/check` before committing. It runs the same checks CI does, plus pre-commit across every file rather than the staged ones.
- These prompt for approval and cannot be assumed: `git push`, `git reset --hard`, `git clean`, `git rebase`, and the `gh` commands that create or merge pull requests, cut releases, or delete the repository.
- Work reaches `main` through a pull request, where `.github/PULL_REQUEST_TEMPLATE.md` applies.
- Plan mode writes to `docs/plans/`, which is tracked. A plan lands in the diff alongside the code it describes.

## Layout

Where a new file goes, and why the boundary exists:

- `apps/<name>/` — one deployable service or one durable domain boundary: the unit owning its own dependencies, tests, and specs. Its tests live in `apps/<name>/tests/` and its specs in `apps/<name>/docs/specs/`.
- `libs/` — shared internal libraries and schemas used by apps. They need not be publishable.
- `tests/` — repo-level tests spanning several apps or libraries. App-local tests do not belong here.
- `scripts/` — every portable shell script, whether a person or a workflow runs it.
- `tools/` — helpers that must be built before they run, one directory per program with its own manifest. The split from `scripts/` is by artifact, not by caller; a script written for CI is the first thing someone runs locally to reproduce a failure.
- `docs/specs/` — contracts spanning apps. Single-unit specs stay with their unit.
- `docs/adr/` — one repo-wide numbered sequence. See `docs/CLAUDE.md`.

A package under `apps/` or `libs/` whose language has no root manifest fails the run rather than passing, because every check runs from the repository root and nothing would look at it. The failure names the root manifest to add.

## Repository settings

Some guarantees these files make are only half-kept by the files themselves. Current state on `possiblyneal/template`:

- Dependabot alerts and security updates: **enabled**. `scripts/security` fails a pull request introducing a CVE; these open the pull request that resolves it.
- Push protection and branch rulesets: **unavailable** on this plan. So `no-commit-to-branch` in each clone is the only thing keeping commits off `main`, and gitleaks in `.pre-commit-config.yaml` is the only check seeing a secret before it is pushed.
- Code scanning: **unavailable**. `.github/workflows/codeql.yml` ships unmodified and fails at its upload step. That failure is the plan, not a finding — see `docs/lessons.md`.
- GitHub Actions: **unverified**. `ci.yml` and `security.yml` have never run here, because they landed during a GitHub Actions outage that suppressed run dispatch account-wide. Nothing is known to be wrong with them, and nothing is known to be right either. `scripts/check` locally is the only gate that has actually run.

## Child Index

- `apps/github-repository-template/CLAUDE.md` — the template payload and the reference docs explaining it
- `scripts/CLAUDE.md` — the language-capabilities interface, and what adding a language or check requires
- `.claude/CLAUDE.md` — hooks, settings, and skills; what a session may not grant itself
- `docs/CLAUDE.md` — ADRs, specs, plans, and lessons

The full documentation contract is `.claude/rules/documentation.md`. Read the nearest `CLAUDE.md` above every path you touch before editing, and update the owning file after meaningful changes.
