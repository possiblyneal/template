# Claude Configuration

## Purpose

The agent's operating parameters for this repository: permission rules and the skills invocable by name. Hooks, the documentation contract, and the output style live in the operator's global `~/.claude` instead.

## Ownership

- `settings.json` — overrides for the global settings file
- `skills/` — reusable multi-step prompts, each invocable as `/name`
- `hooks/`, `rules/`, `output-styles/`, `agents/`, `workflows/` — empty, shipped so the available surfaces are visible without inheriting rules

`skills/repo-builder/` is this repository's own product, not configuration. Its contract is `skills/repo-builder/references/lifecycle.md`.

## Local Contracts

**A session must not grant itself new permissions.** `~/.claude/hooks/block-config-change.sh` blocks mid-session reloads of settings and skills. The edit stays on disk as a reviewable diff and applies next session. Without it, a session editing its own settings gets the new permissions immediately, unwinding the ask gates from inside — the same path a malicious skill file would take.

**A rule here binds every clone.** Permission rules merge across scopes and a deny or ask rule cannot be lifted downstream, so restriction is what this file is for.

**`allow` ships empty and stays empty.** Allow rules have no effect under `bypassPermissions`, so one added here buys nothing for a session running that mode while still granting capability to every clone that accepts the trust dialog — the shape behind past trust-dialog bypasses. Deny rules block in every mode including bypass, and ask rules prompt in every mode, so those two are the only rules that do anything for every reader of this file. A rule that is genuinely machine-local has no home in this repository; keep it in user settings.

**Secrets are denied, not asked**, `//`-anchored so they hold outside the repository, and written twice — once as `Read`, once as `Edit`. The `Read` half also blocks the edit tools and drops the path from search and file discovery, but it does not cover `NotebookEdit`, and its Write coverage requires Claude Code v2.1.228 or later; the `Edit` twin closes both gaps.

**An enumerated deny plus a broad allow is a leak, not a boundary.** A deny list names the files it knows; `Read(//home/neal/.claude/**)` handed back `.credentials.json`, which `Read(//**/credentials.json)` does not match, and `Read(//home/neal/.agentmemory/**)` handed back `.env.bak.*`, which `Read(//**/.env)` does not match. Widen the deny when a new secret shape appears; do not re-open a directory to reach one file in it.

**Deny cannot carry exceptions**, so the `.env` variants stay enumerated rather than globbed — `.env.*` would take `src/repository-addons/.env.example` with it. The tracked payload `.env` is denied and that is correct: it ships intentionally empty and `apps/github-repository-template/AGENTS.md` forbids giving it content. The cost is that Glob and Grep no longer surface it, so the `.env` reconciliation step in `skills/repo-builder/references/lifecycle.md` has to name the path outright rather than discover it.

**Three ask families cover the paths a session should not touch on its own initiative**, and each is written to the widest form that still names the thing:

- Dotfiles and dot-folders, as four rules — `Edit(.*)`, `Edit(.*/**)`, `Edit(**/.*)`, `Edit(**/.*/**)`. Configuration is where a session grants itself capability, so it prompts.
- Source directories, as `Edit(**/src/**)`. This replaced the root-only `Edit(/apps/github-repository-template/src/**)`, which it fully subsumes; that is why the two settings files now agree on everything but one key. The payload gains the same gate, which is correct — `src/` is where a generated repository's code will live.
- Anything directly in the project root, as `Edit(/*)`. `*` stops at a path separator, so this matches root files and not directory contents.

**An `Edit` rule cannot see a deletion, so `Bash(rm:*)` and `Bash(git rm:*)` carry that half.** The path rules above cover creating and modifying, because those go through `Edit`, `Write`, or `NotebookEdit`. Removal goes through the shell, where the rule matches a command prefix and cannot read which path the argument names — so these two prompt on every `rm`, not only on a dotfile. That breadth is the cost of covering deletion at all; narrowing them to a path is not available.

**`.npmrc` and `.pypirc` are ask, not deny.** They sit in the same secret-shaped family as the denied paths and were briefly listed with them, which was wrong: both are ordinary package-manager configuration that a session has real reason to read, and unlike a key file the credential in one is a line rather than the whole file. Deny made a routine lookup impossible; ask keeps a person in the loop without doing that. The other entries in `deny` stay denied — nothing there has a legitimate read.

**Omit a key rather than blanking it when an empty value would be invalid**, because a settings file failing validation is rejected whole rather than partially applied. Enum strings, minimum-length strings, and objects with required sub-fields must stay absent until they hold a real value.

**`~/.claude/hooks/ask-outside-repo.sh` cannot cover Bash redirection, and no hook can.** A `PreToolUse` hook on Bash receives one command string with no `file_path`, so catching a redirect means parsing shell syntax — which fails on variables, `eval`, heredocs, and subshells, and fails silently. Enforcing that boundary takes the OS: `sandbox` in `settings.json`, which ships empty.

**Every pipe in a hook ends in a variable or a herestring.** `set -euo pipefail` turns SIGPIPE into a failure, and in a hook that ends the run.

**`~/.claude/hooks/session-start.sh` installs every git hook type the config asks for, not just `pre-commit`.** A clone that predates the commit-msg hook already has `hooks/pre-commit`, so testing for that file alone reports the clone as set up and the message check never lands.

**`~/.claude/hooks/session-start.sh` reports stale worktree metadata; it does not prune it.** It calls `scripts/worktree-cleanup --report`, guarded on the file being executable and with its failure swallowed, because everything the hook prints after that point is the session's orientation and a missing or broken optional script must not cost it. Pruning belongs to the `post-checkout` and `post-merge` hooks, where a person asked git to do something; starting a session is not that.

That module also resolves the hooks directory with `git rev-parse --git-path` instead of a literal `.git/hooks`, so the install fires in a linked worktree, where `.git` is a file and the hooks live in the shared common directory. The hardcoded path this replaced reported those clones as already set up.

It gets that list by sourcing `scripts/libs/precommit.sh` rather than reading the config itself — the only dependency any hook here has on `scripts/`, and deliberate. `scripts/doctor` reports the same gap this closes, and when the two disagreed about whether a clone was set up, the disagreement was invisible from either file. The source is guarded on the file existing, so a tree without `scripts/` still starts a session.

## Work Guidance

This repository's `settings.json` differs from the payload's in exactly one place, and a normalized `jq -S` diff of the two files should show nothing else. The payload sets `skipDangerousModePermissionPrompt: true` and the root does not. That is deliberate and settled: every generated repository suppresses the dangerous-mode confirmation, matching how these repositories are actually driven. Do not raise it again as a finding.

Changes to `settings.json` usually belong in the payload too. `hooks/`, `rules/`, `output-styles/`, and `skills/` do not — they are product, and the manifest classifies them that way.

## Verification

`check json` validates `settings.json` on every commit.

## Child Index

None. `skills/repo-builder/` documents itself through `SKILL.md` and `references/lifecycle.md`.
