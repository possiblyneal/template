# Claude Configuration

## Purpose

The agent's operating parameters for this repository: hooks wired to tool events, permission rules, the documentation contract, and the skills invocable by name.

## Ownership

- `settings.json` — overrides for the global settings file; wires the hooks below
- `hooks/` — three shell scripts, each parsing input with `jq`, which is why `scripts/doctor` requires `jq` while any of them is present
- `rules/documentation.md` — the contract governing every `CLAUDE.md` in this repository
- `skills/` — reusable multi-step prompts, each invocable as `/name`
- `agents/`, `output-styles/`, `workflows/` — empty, shipped so the available surfaces are visible without inheriting rules

`skills/repo-builder/` is this repository's own product, not configuration. Its contract is `skills/repo-builder/references/lifecycle.md`.

## Local Contracts

**A session must not grant itself new permissions.** `hooks/block-config-change.sh` blocks mid-session reloads of settings and skills. The edit stays on disk as a reviewable diff and applies next session. Without it, a session editing its own settings gets the new permissions immediately, unwinding the ask gates from inside — the same path a malicious skill file would take.

**Only rules that restrict belong in `settings.json`.** Permission rules merge across scopes and a deny rule cannot be lifted downstream, so a rule here binds every clone. Granting capability from a repository-controlled file is the shape behind past trust-dialog bypasses.

**Omit a key rather than blanking it when an empty value would be invalid**, because a settings file failing validation is rejected whole rather than partially applied. Enum strings, minimum-length strings, and objects with required sub-fields must stay absent until they hold a real value.

**`hooks/ask-outside-repo.sh` cannot cover Bash redirection, and no hook can.** A `PreToolUse` hook on Bash receives one command string with no `file_path`, so catching a redirect means parsing shell syntax — which fails on variables, `eval`, heredocs, and subshells, and fails silently. Enforcing that boundary takes the OS: `sandbox` in `settings.json`, which ships empty.

**Every pipe in a hook ends in a variable or a herestring.** `set -euo pipefail` turns SIGPIPE into a failure, and in a hook that ends the run.

**`hooks/session-start.sh` installs both git hook types, not just `pre-commit`.** A clone that predates the commit-msg hook already has `hooks/pre-commit`, so testing for that file alone reports the clone as set up and the message check never lands. It resolves the hooks directory through `git rev-parse --git-path` for the reason `scripts/doctor` does: in a linked worktree `.git` is a file and the hooks live in the shared common dir.

**`rules/documentation.md` carries no `paths:` frontmatter, deliberately.** It loads in every session. Scoping it to Markdown is the obvious economy and the wrong one: the documentation pass is owed on the source change, not on a `.md` file being open, so a rule loading only when docs are already open covers the sessions that were going to update docs anyway and misses every session that should have.

## Work Guidance

This repository's `settings.json` differs from the payload's by one rule: `Edit(/apps/github-repository-template/src/**)`, which prompts before a payload edit so the payload-versus-root choice stays deliberate. Preserve it when reconciling a template update.

Changes to `hooks/`, `rules/`, and `settings.json` usually belong in the payload too. `skills/` does not — it is product, and the manifest classifies it that way.

## Verification

`scripts/doctor` fails when `jq` is missing while a hook is present. shellcheck runs over `hooks/` through pre-commit. `check json` validates `settings.json` on every commit.

Nothing verifies that a hook does what it claims; changing one means reasoning about the failure it prevents.

## Child Index

None. `skills/repo-builder/` documents itself through `SKILL.md` and `references/lifecycle.md`.
