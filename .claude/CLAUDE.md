# Claude Configuration

## Purpose

The agent's operating parameters for this repository: permission rules and the skills invocable by name. Hooks, the documentation contract, and the output style live in the operator's global `~/.claude` instead.

## Ownership

- `settings.json` — overrides for the global settings file
- `skills/` — reusable multi-step prompts, each invocable as `/name`
- `hooks/`, `rules/`, `output-styles/`, `agents/`, `workflows/` — empty, shipped so the available surfaces are visible without inheriting rules

`skills/repo-builder/` is this repository's own product, not configuration. Its contract is `skills/repo-builder/references/lifecycle.md`, and `skills/repo-builder/references/choosing_a_language.md` is the method behind its wayfinding step — how a repository's application boundaries and their languages get derived rather than asked for.

That step is where repo-builder depends on skills it does not ship, and there are two of them. Every generate invokes the operator's global `/setup-matt-pocock-skills` to record where the new repository tracks its issues; when the two short-form questions fail to settle the decomposition, the contract then invokes `/wayfinder` to chart the remaining decisions as a map on that tracker and stops, because charting hand-resolves nothing and a generate that worked its own map would return the decomposition it had already guessed. Both are invoked rather than reimplemented.

That dependency is why a generate creates the destination repository as its fourth step, immediately after materializing the candidate and before configuring or personalizing it. `/setup-matt-pocock-skills` proposes a tracker from `git remote -v` and `/wayfinder` charts wherever that answer sends it, so both give the wrong answer against a candidate with no remote. A session running without either global skill installed hits a stop with nowhere to send the user — the same personal-use tradeoff the settings note below records, and it reaches the generated repository too, since nothing in the payload supplies either skill.

## Local Contracts

**A session must not grant itself new permissions.** `~/.claude/hooks/block-config-change.sh` blocks mid-session reloads of settings and skills. The edit stays on disk as a reviewable diff and applies next session. Without it, a session editing its own settings gets the new permissions immediately, unwinding the ask gates from inside — the same path a malicious skill file would take.

**Single source of truth: the operator's global `~/.claude/settings.json` carries the real policy — `env`, the secret `deny` list, and the dotfile/root-file/`rm`/`git rm`/`.npmrc`/`.pypirc` half of `ask` all live there now, not here.** This repository, and the payload it produces, are personal-use only for now — both are read and run exclusively by the one operator whose global config is always present. Duplicating that policy locally added no protection, only a second place to keep in sync, so it was removed from both `settings.json` files. The tradeoff: a session running here without that global config loaded (a different machine, a different `HOME`, a stripped-down environment) has no local fallback for it. If the payload ever starts reaching other operators, the deny list and the rest of `ask` need to move back into the payload's `settings.json`, since a stranger's global config can't be assumed the way this operator's can.

**`allow` ships empty and stays empty.** Allow rules have no effect under `bypassPermissions`, so one added here buys nothing for a session running that mode while still granting capability to every clone that accepts the trust dialog — the shape behind past trust-dialog bypasses. A rule that is genuinely machine-local has no home in this repository; keep it in user settings.

**Root keeps one local rule the payload doesn't: `Edit(**/src/**)`.** It protects a duality that exists only in this repository — `apps/github-repository-template/src/base-repo/` is template payload, not root configuration, and an edit there needs to read as deliberate regardless of whose global config is loaded. A generated repository has no such duality; ordinary application code under a `src/` directory is just code, so the payload's `ask` ships empty rather than carrying a rule that exists to solve a problem the payload doesn't have.

**Omit a key rather than blanking it when an empty value would be invalid**, because a settings file failing validation is rejected whole rather than partially applied. Enum strings, minimum-length strings, and objects with required sub-fields must stay absent until they hold a real value.

**`~/.claude/hooks/ask-outside-repo.sh` cannot cover Bash redirection, and no hook can.** A `PreToolUse` hook on Bash receives one command string with no `file_path`, so catching a redirect means parsing shell syntax — which fails on variables, `eval`, heredocs, and subshells, and fails silently. Enforcing that boundary takes the OS: `sandbox` in `settings.json`, which ships empty.

**Every pipe in a hook ends in a variable or a herestring.** `set -euo pipefail` turns SIGPIPE into a failure, and in a hook that ends the run.

**`~/.claude/hooks/session-start.sh` installs every git hook type the config asks for, not just `pre-commit`.** A clone that predates the commit-msg hook already has `hooks/pre-commit`, so testing for that file alone reports the clone as set up and the message check never lands.

**`~/.claude/hooks/session-start.sh` reports stale worktree metadata; it does not prune it.** It calls `scripts/worktree-cleanup --report`, guarded on the file being executable and with its failure swallowed, because everything the hook prints after that point is the session's orientation and a missing or broken optional script must not cost it. Pruning belongs to the `post-checkout` and `post-merge` hooks, where a person asked git to do something; starting a session is not that.

That module also resolves the hooks directory with `git rev-parse --git-path` instead of a literal `.git/hooks`, so the install fires in a linked worktree, where `.git` is a file and the hooks live in the shared common directory. The hardcoded path this replaced reported those clones as already set up.

It gets that list by sourcing `scripts/libs/precommit.sh` rather than reading the config itself — the only dependency any hook here has on `scripts/`, and deliberate. `scripts/doctor` reports the same gap this closes, and when the two disagreed about whether a clone was set up, the disagreement was invisible from either file. The source is guarded on the file existing, so a tree without `scripts/` still starts a session.

## Work Guidance

This repository's `settings.json` differs from the payload's in exactly one place, and a normalized `jq -S` diff of the two files should show nothing else: root's `permissions.ask` carries `Edit(**/src/**)` and the payload's is empty, for the reason above. That is deliberate and settled. Do not raise it again as a finding.

Changes to `settings.json` usually belong in the payload too. `hooks/`, `rules/`, `output-styles/`, and `skills/` do not — they are product, and the manifest classifies them that way.

## Verification

`check json` validates `settings.json` on every commit.

## Child Index

None. `skills/repo-builder/` documents itself through `SKILL.md` and its `references/`.
