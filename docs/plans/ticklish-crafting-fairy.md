# Reverse Claude User-Config Links

## Context

`apps/claude-user-level-files/` is intended to become the versioned source for the selected user-level Claude Code configuration. It currently contains ten symbolic links into `~/.claude/`, while the matching home paths contain the real files and directories. Reverse that direction: materialize the selected entries in the app, then replace the matching home entries with symbolic links to the app. This keeps Claude Code usable from `~/.claude/` while the repository owns the configuration content.

## Scope

Manage only these corresponding entries:

- `agents/`, `hooks/`, `output-styles/`, `rules/`, `skills/`, `workflows/`
- `CLAUDE.md`, `keybindings.json`, `settings.json`, `statusline.sh`

Leave all other `~/.claude` state alone, including credentials, sessions, projects, caches, plugins, history, daemon data, backups, and the existing `chrome` link.

## Recommended approach

1. Preflight the fixed allowlist: assert every app entry is currently a symlink resolving to its matching `~/.claude` path, and each home source is the expected regular file or directory. Capture modes and hashes, and check the content for secrets before it becomes version-controlled.
2. Materialize each allowlisted source under `apps/claude-user-level-files/` using a temporary sibling staging area. Preserve directory contents and executable modes (especially `statusline.sh`), then verify staged content matches the current home sources before replacing only the existing app symlinks.
3. After the app has verified real copies, replace each allowlisted home path with an atomic symbolic link to its canonical app location, `/home/neal/code/template/apps/claude-user-level-files/<entry>`. Retain a timestamped, recoverable backup of the original home nodes until all link checks complete; if a replacement fails, restore the affected source rather than continuing.
4. Add the ownership and link-direction contract to `apps/claude-user-level-files/CLAUDE.md`: the app holds the real selected user configuration; `~/.claude` links to it; runtime/private state remains outside the app; and changes must preserve the allowlist and source-of-truth direction. Add the app to the root `CLAUDE.md` Child Index.
5. Verify end-to-end: app entries are no longer symlinks, home entries are symlinks resolving to the real app entries, file hashes/modes and directory trees match the staged copies, excluded home state is untouched, JSON files parse, and `git status` reflects only the intended materialized configuration and documentation.

## Critical paths

- `apps/claude-user-level-files/`
- `apps/claude-user-level-files/CLAUDE.md`
- `CLAUDE.md`
- `~/.claude/{agents,hooks,output-styles,rules,skills,workflows,CLAUDE.md,keybindings.json,settings.json,statusline.sh}`

## Verification

- Use `stat`/`readlink` or equivalent to assert node types and canonical targets for the allowlist.
- Compare hashes and preserved modes before and after reversal, recursively for directories.
- Validate `settings.json` and `keybindings.json` with a JSON parser.
- Run `scripts/check` if the imported files pass the repository’s pre-commit/configuration checks; otherwise report the exact gate that is not applicable or fails.
