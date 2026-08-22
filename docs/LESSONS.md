---
type: Lessons Learned
title: Repository Lessons Learned
description: Repository-specific knowledge that prevents recurring mistakes or expensive rediscovery.
tags: [template, repo-builder]
generated: { by: "agent/claude-opus-5", at: "2026-08-06T00:00:00Z" }
status: draft
---

# Lessons learned

## How to add a lesson

Add only durable, repeatable, non-obvious constraints, conventions, or tool/provider quirks. Do not add one-off incident history, generic advice, or facts already clear from the code. Write concisely and concretely. Lead with the required action; name the exact artifact, command, or constraint; remove background and filler words. State why only when the consequence is not self-evident. Link to the authoritative source rather than duplicating it.

### Lesson format

```md
## <Short, imperative title>

<The non-obvious rule or constraint.>

**Do:** <The specific required action.>

**Why:** <The consequence avoided, if it is not self-evident.>

**Source:** [<Authoritative source title>](<URL or relative path>)
```

## Lessons

## Decide whether a change is payload or root

The root config files and `apps/github-repository-template/src/base-repo/` hold near-identical copies of the same files. They are not the same file.

**Do:** Before editing `scripts/`, `.github/`, `.claude/`, or a root dotfile, decide whether the change belongs to this repository, to every generated repository, or to both. Apply it to both trees in one commit when it is both.

**Why:** A fix made only at the root leaves the template shipping the bug to every repository generated afterward. A fix made only in the payload leaves this repository running the bug.

**Source:** [Template payload contract](../apps/github-repository-template/CLAUDE.md)

## CodeQL fails fast here, and that failure is the finding

Code scanning accepts uploaded results from a public repository, or from a private one with GitHub Advanced Security. This repository is private on a free plan, so the `scanning` job in `.github/workflows/codeql.yml` fails in seconds with the reason in the run summary, instead of analyzing for an hour and dying at the upload step.

**Do:** Read a red `Code scanning enabled` check as accurate — this repository genuinely has no static analysis coverage. Fix it by making the repository public or enabling Advanced Security. Never quiet it with `continue-on-error`, a removed upload step, or an `if:` that skips the job.

**Why not skip it:** A skipped job renders the workflow green, so a repository with no coverage looks on the checks list exactly like one that scanned clean and found nothing. That is the same false green `continue-on-error` produces, reached by a different route, and it is worth being precise about which problem the fail-fast solves: not that the check was red, but that it burned an hour and then reported `Code scanning is not enabled` underneath a misleading note about pull requests from forks. Red was always the honest answer. Slow and misdescribed was the defect.

**Why the API and not the event:** Visibility is read through `gh api` because `github.event.repository` is documented as "Not applicable" for `schedule`. Read from the event, the weekly run would compare a null against `public` and fail a public repository every Tuesday. A failed lookup fails the job for the same reason, rather than defaulting either way.

**Source:** [Payload structure](../apps/github-repository-template/docs/github_repository_structure.md)

**Source:** [`.repo-template.json`](../.repo-template.json)

## The repo-builder tests are not covered by scripts/check

`.claude/skills/repo-builder/` holds Python with a pytest suite, but this repository has no root `pyproject.toml`, so language detection finds no Python and `scripts/check` reports there is nothing to check.

**Do:** Run `python3 -m pytest .claude/skills/repo-builder/scripts/tests/` directly after changing `preflight.py`.

**Why:** A green `scripts/check` is not evidence the skill's tests ran. It is evidence they were never looked for.

**Source:** [Preflight tests](../.claude/skills/repo-builder/scripts/tests/test_preflight.py)

## Root dotfiles are unowned, so updates never reach them

The ownership rules in `.repo-template.json` match `scripts/**`, `.github/**`, and parts of `.claude/`. No rule matches a root dotfile, and an unmatched path defaults to product.

**Do:** When reconciling a template update, check `.pre-commit-config.yaml`, `.gitattributes`, `.gitignore`, `.mcp.json`, and `.worktreeinclude` by hand. Confirm a path's ownership with `preflight.classify_path` rather than assuming a broad rule covers it.

**Why:** These are the files enforcing the template's guarantees — the hook revisions carrying the secret scanner, the merge policy stopping a lockfile from being line-merged. A defect fixed in the payload silently never lands in any generated repository, and the update reports success.

**Source:** [Ownership rules](../.repo-template.json)

## .env is tracked in the payload and ignored at a destination root

The root `.gitignore` pattern does not reach `apps/.../src/base-repo/.env`, so it is tracked there. At a destination root the same pattern matches, so the copied file is present and untracked.

**Do:** Read its absence from a fresh clone as correct. Do not force it into the index.

**Why:** Tracked in the template reads as a file the generated repository will commit, and it is a place for secrets, so untracked is the right end state.

**Source:** [Root configuration files](../apps/github-repository-template/docs/github_repository_structure.md)

## Verify a generation by file-list diff, not by the checks passing

`scripts/check` passing says the files present are valid. It says nothing about files that should be there and are not.

**Do:** Diff the payload's tracked paths against the destination's tracked paths as a generation step. Investigate every difference, then state which are intentional. Compare against the working tree as well as the index, since an ignored file is present and untracked rather than missing.

**Why:** Every check in this repository is a check on content. Absence has no runner, so a missing file produces a green run.

**Source:** [Lifecycle contract](../.claude/skills/repo-builder/references/lifecycle.md)

## pre-commit --all-files reads the index, not the working tree

`pre-commit run --all-files` enumerates files through git. Untracked files are invisible to it, and it reports a pass over them rather than saying it skipped them.

**Do:** Run `scripts/check`, which follows the sweep with a second pass over `git ls-files --others --exclude-standard`, rather than the bare command. Invoking `pre-commit run --all-files` yourself still needs the new files staged first.

**Why:** A run over an unstaged candidate checks the two files that were already tracked and reports a pass for the forty-eight that were not.

**Source:** [scripts/check](../scripts/check)

## Trust pre-commit's environments over PATH for gitleaks and actionlint

`scripts/doctor` and `scripts/security` look for tools on PATH. pre-commit installs its own pinned copies in isolated environments.

**Do:** Read "unavailable" from `scripts/security` as "not on PATH", not as "never ran". Check the pre-commit output for the same tool before concluding a scan was skipped.

**Why:** `scripts/security` reports the secret scan unavailable while gitleaks is passing three lines later in the same `scripts/check` run. Reading the first and not the second understates the coverage and invites installing a redundant copy.

**Source:** [.pre-commit-config.yaml](../.pre-commit-config.yaml)

## Check GitHub status before diagnosing a workflow that never runs

Workflow registration and run dispatch are separate services. A workflow can register as `active` while no run is ever created and no Actions check suite appears on the commit — which is what an Actions outage looks like from every API surface, since each one keeps reporting healthy.

**Do:** Check [githubstatus.com](https://www.githubstatus.com/) first when a workflow registers but dispatches nothing. Confirm the blast radius with a scratch repository: a new public repo with a single `on: push` job that registers and never runs is not a repository problem.

**Why:** Every repo-level explanation — visibility, plan minutes, the `is_template` flag, trigger config, branch — is testable and wrong here, and each costs a push-and-wait cycle to eliminate. An outage is one page load.

**Source:** [githubstatus.com](https://www.githubstatus.com/)

## Fix a zizmor finding rather than ignoring it

`.pre-commit-config.yaml` runs zizmor at `--min-severity medium`, and this repository passes with nothing suppressed. Two medium findings were fixed rather than ignored to get there: `codeql.yml` set `security-events: write` at the workflow level where the detect job inherited it, and `security.yml` pinned `setup-trivy` by commit while its `version` input still defaulted to `latest`.

**Do:** Fix the finding, or raise the threshold and say why. Reach for `rules.<id>.ignore` in `zizmor.yml` only when the finding is genuinely wrong about this repository.

**Why:** A threshold is one visible line that reads as "known findings below this level". An ignore list is a set of individually plausible entries that nobody revisits, and it only grows. The pinning policy in `zizmor.yml` is the deliberate exception: it encodes a trust boundary — ref-pin first-party, hash-pin third-party — rather than dismissing a finding.

**Source:** [.pre-commit-config.yaml](../.pre-commit-config.yaml), [zizmor.yml](../zizmor.yml)

## A per-directory CLAUDE.md is what loads — don't split the contract into a separate file

Claude Code loads `CLAUDE.md`. It never loads `AGENTS.md`. At launch it walks the directory hierarchy above the working directory; below that, it loads on demand when it reads a file in a subdirectory, and the on-demand path reads exactly `<dir>/CLAUDE.md` and `<dir>/.claude/CLAUDE.md`. No setting renames the file it looks for. An instruction to read `AGENTS.md` is context the agent may act on, not a mechanism that loads anything.

**Do:** Write the folder's contract directly in `CLAUDE.md`. Don't split it into a separate `AGENTS.md` with a `CLAUDE.md` that merely points at it — that indirection is exactly the failure mode below.

**Why:** This repository used to carry the contract in `AGENTS.md` with a one-line `@AGENTS.md` shim in `CLAUDE.md`. Deleting a shim without confirming the contract was reachable another way silently dropped it from context — the incident that first produced this lesson (#30). Rather than keep re-litigating shim upkeep, the contract now lives directly in the file that actually loads, removing the indirection instead of policing it.

**Source:** [Claude Code memory docs](https://code.claude.com/docs/en/memory), [apps/github-repository-template/CLAUDE.md](../apps/github-repository-template/CLAUDE.md)
