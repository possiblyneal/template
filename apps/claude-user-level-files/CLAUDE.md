# Claude User-Level Files

## Purpose

Version control for the user-level Claude Code configuration that would otherwise exist only as loose files in `~/.openclaude`. `src/` holds the real files; `~/.openclaude` holds symlinks pointing back here. Editing either path edits the same file, so configuration changes arrive as reviewable diffs instead of untracked drift.

## Ownership

Everything under `src/`, each symlinked from `~/.openclaude/<name>`:

- `CLAUDE.md` — the user's global directives, loaded into every session on this machine
- `settings.json` — permissions, `statusLine`, model, and effort
- `keybindings.json`, `output-styles/`, `skills/`
- `agents/`, `hooks/`, `rules/`, `workflows/` — empty, each holding a `.gitkeep` so the surface is visible and ready to fill

Not owned here: `plans/` exists in `~/.openclaude` as a real directory and has never been versioned. It is a candidate, not an omission.

Also not owned here: the status line renderer. `settings.json` points `statusLine` at `~/.openclaude/statusline.sh`, which links into `code/devex`, so the file this app names is versioned in a different repository. Change the renderer there, not here.

## Local Contracts

**Only configuration is symlinked; runtime state stays in `~/.openclaude`.** `projects/`, `sessions/`, `history.jsonl`, `.openclaude.json`, `plugins/`, `cache/`, and `shell-snapshots/` are per-machine session state that would churn the working tree on every prompt. Moving any of them here is a mistake, not an extension.

**Claude Code writes to `settings.json` at runtime.** Selecting a model with `/model` persists through the symlink into this repository, so the working tree can go dirty without anyone editing a file. Read that diff before committing or discarding it — it records a real preference change.

**A branch switch changes live configuration.** The symlink target moves with the checkout, so a branch that predates a settings change silently applies the older settings to every new session on this machine. Checking out an unrelated branch is not neutral here the way it is elsewhere in this repository.

**No gateway token is committed.** Each CCR wrapper in `~/.local/share/ccr-upstream-client/bin/` exports its own `ANTHROPIC_API_KEY`; the token files stay there, outside version control. Never inline a `ccr-profile-*` value into `src/`.

## Work Guidance

Adding a file means creating it in `src/` and symlinking it from `~/.openclaude`, never creating it in `~/.openclaude` first — a real file there shadows the versioned copy and the divergence is invisible until something breaks.

Keep `settings.json` free of per-profile values. All CCR profiles share this file; anything profile-specific belongs in that profile's wrapper in `~/.local/share/ccr-upstream-client/bin/` as an environment variable. This is why `apiKeyHelper` is absent — the wrappers supply the key. `model` is set here because every profile is meant to run the same one.

## Verification

`ls -la ~/.openclaude` shows which entries are symlinks; anything listed under Ownership that appears as a real file has drifted and needs reconciling.

Pre-commit runs shellcheck over the shell scripts and validates the JSON here, the same as anywhere else in the repository. Nothing verifies that the symlinks point where they should, or that a `settings.json` change is one the user intended.

## Child Index

None.
