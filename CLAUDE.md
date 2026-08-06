## Commands

Use these instead of per-language tools; each detects the languages present and fails when an expected check cannot run.

- `scripts/doctor` — verify local toolchains, dependencies, hooks, and configuration without contacting hosted services
- `scripts/repo-settings check` — inspect GitHub-hosted security and branch settings; run explicitly because it needs network access and repository administration visibility
- `scripts/check` — full local gate: `doctor`, the script tests, then lint, format, type check, test, build, then the security audit and pre-commit across every file, not just staged ones
- `scripts/fix` — rewrite formatting for every detected stack; the write half of `check`'s format check, no lint autofixes
- `scripts/clean` — recursively delete build output and tool caches (`dist`, `build`, `coverage`, `__pycache__`, `.*_cache`, `*.pyc`)
- `scripts/dev [app-name]` — start the dev server; requires the app name when several stacks are present, since only one process can run

Every check runs for every language present, not the first one detected. `scripts/libs/detect.sh` owns language detection and every language-specific capability behind the `language_capabilities` interface; command scripts name capabilities rather than language adapters, and `scripts/detect` exposes workflow projections. Results distinguish `pass`, `not-applicable`, `unavailable`, and `FAIL`, so an intentional no-op cannot look like a runner that executed. Adding a language is local to the module plus the hand-written CI toolchain adapter, whose coverage test fails when it is missing.

A package under `apps/` or `libs/` whose language has no root manifest fails the run rather than passing. Every check runs from the repository root, so nothing would look at it. The failure names the root manifest to add.

## Git

- Pre-commit blocks direct commits to `main` and `master`. Branch before you start; a commit attempted on either fails at the hook, not at review.
- Run `scripts/check` before committing. It runs the same checks CI does, plus pre-commit across every file rather than the staged ones.
- These prompt for approval and cannot be assumed: `git push`, `git reset --hard`, `git clean`, `git rebase`, and the `gh` commands that create or merge pull requests, cut releases, or delete the repository.
- Work reaches `main` through a pull request, where `.github/PULL_REQUEST_TEMPLATE.md` applies.
- Plan mode writes to `docs/plans/`, which is tracked. A plan lands in the diff alongside the code it describes.

## What this repository is

This repository builds other repositories. It holds two things and they must not be confused:

- **Live configuration** — the `scripts/`, `.github/`, `.claude/`, and dotfiles at the root govern *this* repository, the same way they would govern any other.
- **Template payload** — `apps/github-repository-template/src/base-repo/` is the content copied into repositories generated from this one. Editing a file there changes every future generated repository and changes nothing here.

The two trees hold near-identical files. Before editing, decide which one the change belongs to; a fix applied only at the root leaves the template shipping the bug, and a fix applied only in the payload leaves this repository running it. Editing under `src/` prompts for approval so the choice is deliberate.

This repository was itself generated from its own payload, so the root files are the payload plus repository-specific merges. Those merges are recorded in `.repo-template.json`, which also records the payload commit the root was last reconciled with.

## Child Index

- `apps/github-repository-template/CLAUDE.md` — the template payload and the reference docs describing it
- `.claude/skills/repo-builder/` — the skill that generates and updates repositories from the payload; its contract is `references/lifecycle.md`
