## Commands

Use these instead of per-language tools; each detects the languages present and fails when an expected check cannot run.

- `scripts/doctor` — verify the tools each present manifest needs, and that the pre-commit hook is installed in this clone
- `scripts/check` — full local gate: `doctor`, the detection test, then lint, format, type check, test, build, then the security audit and pre-commit across every file, not just staged ones
- `scripts/fix` — rewrite formatting for every detected stack; the write half of `check`'s format check, no lint autofixes
- `scripts/clean` — recursively delete build output and tool caches (`dist`, `build`, `coverage`, `__pycache__`, `.*_cache`, `*.pyc`)
- `scripts/dev [app-name]` — start the dev server; requires the app name when several stacks are present, since only one process can run

Every check runs for every language present, not the first one detected. Shared script libraries live in `scripts/libs/`; detection lives once in `scripts/libs/detect.sh`, and `scripts/detect` exposes it to the workflows. Adding a language means adding a `<check>_<language>` function in each file the "no runner" message lists — that message is the authority, and wiring only some of the files leaves the language checked in one place and silently skipped in another while the run stays green.

A package under `apps/` or `libs/` whose language has no root manifest fails the run rather than passing. Every check runs from the repository root, so nothing would look at it. The failure names the root manifest to add.

## Git

- Pre-commit blocks direct commits to `main` and `master`. Branch before you start; a commit attempted on either fails at the hook, not at review.
- Run `scripts/check` before committing. It runs the same checks CI does, plus pre-commit across every file rather than the staged ones.
- These prompt for approval and cannot be assumed: `git push`, `git reset --hard`, `git clean`, `git rebase`, and the `gh` commands that create or merge pull requests, cut releases, or delete the repository.
- Work reaches `main` through a pull request, where `.github/PULL_REQUEST_TEMPLATE.md` applies.
- Plan mode writes to `docs/plans/`, which is tracked. A plan lands in the diff alongside the code it describes.

## Placeholders

`apps/app-name/` is a placeholder, not a real unit. Before writing any code into it, ask the user what the unit is called, then rename the directory to that name in kebab-case.

Ask with the question the answer has to fit: an `apps/` entry is one deployable service or one durable domain boundary, the unit that owns its own dependencies, tests, and specs. Offer the user the name you would pick from what the repository already shows, so a nod is enough when it is right.

Convert whatever they answer to kebab-case: lowercase, words joined by hyphens, no spaces, underscores, or capitals. `Billing API` becomes `billing-api`.

Rename with `git mv`, then grep for the old name and update every reference before continuing. Delete this section once no placeholder remains.

## Child Index

This project is not yet indexed. Before continuing you must read `.claude/rules/documentation.md`, scan the project, build the `CLAUDE.md` tree and replace this message with the actual index. Go deep and scan files recursively to properly evaluate complexity and create nested `CLAUDE.md` files where needed.
