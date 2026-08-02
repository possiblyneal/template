## Commands

Use these instead of per-language tools; each detects the languages present and fails when an expected check cannot run.

- `tools/scripts/doctor` — verify the tools each present manifest needs, and that the pre-commit hook is installed in this clone
- `tools/scripts/check` — full local gate: `doctor`, then lint, format, typecheck, test, build, then the security audit and pre-commit across every file, not just staged ones
- `tools/scripts/fix` — rewrite formatting for the detected stack; the write half of `check`'s format check, no lint autofixes
- `tools/scripts/clean` — recursively delete build output and tool caches (`dist`, `build`, `coverage`, `__pycache__`, `.*_cache`, `*.pyc`)
- `tools/scripts/dev [app-name]` — start the dev server for the detected stack, inside `apps/<name>` if given; prints what to add when the stack has no default

## Compact instructions

When compacting, preserve: the current task and its acceptance criteria, decisions the user made and their reasons, the `CLAUDE.md` chain already read, files changed so far, and unresolved test failures or errors. Drop exploratory dead ends and raw command output already acted on.

## Child Index

This project is not yet indexed. Before continuing you must scan the project, build the `CLAUDE.md` tree and replace this message with the actual index. Go deep and scan files recursively to properly evaluate complexity and create nested `CLAUDE.md` files where needed.
