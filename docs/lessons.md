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

## CodeQL cannot report on this repository

`.github/workflows/codeql.yml` runs here, but this repository is private on a free plan, so code scanning is unavailable and the workflow fails when it uploads results.

**Do:** Read a red CodeQL run as the known plan limitation, not as a finding. Resolve it by making the repository public or adding GitHub Advanced Security, not by editing the workflow.

**Why:** The failure is at the upload step, after analysis. Nothing about the code is being reported, so treating it as a code problem sends you looking for a bug that was never found.

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

## The payload's .env cannot be materialized by copying

`apps/github-repository-template/src/base-repo/.env` is a tracked empty file, but the payload's own `.gitignore` ignores `.env`. Copying the payload to a destination root produces a file `git add -A` will not stage.

**Do:** After generating, compare the payload's tracked file list against the destination's. Create `.env` explicitly, or accept its absence deliberately rather than by accident.

**Why:** A file present in the payload and absent from the result is indistinguishable from a copy step that silently dropped it. Generation of this repository lost exactly this file, and nothing reported it.

**Source:** [Payload contract](../apps/github-repository-template/CLAUDE.md)

## Verify a generation by file-list diff, not by the checks passing

`scripts/check` passing says the files present are valid. It says nothing about files that should be there and are not.

**Do:** Diff the payload's tracked paths against the destination's tracked paths as a generation step. Investigate every difference, then state which are intentional.

**Why:** Every check in this repository is a check on content. Absence has no runner, so a missing file produces a green run.

**Source:** [Lifecycle contract](../.claude/skills/repo-builder/references/lifecycle.md)

## pre-commit --all-files reads the index, not the working tree

`scripts/check` ends in `pre-commit run --all-files`, which enumerates files through git. Untracked files are invisible to it.

**Do:** `git add` a new file before treating `scripts/check` as evidence it passed. On a fresh generation, stage everything first.

**Why:** A first run over an unstaged candidate checks the two files that were already tracked and reports a pass for the forty-eight that were not.

**Source:** [scripts/check](../scripts/check)

## Trust pre-commit's environments over PATH for gitleaks and actionlint

`scripts/doctor` and `scripts/security` look for tools on PATH. pre-commit installs its own pinned copies in isolated environments.

**Do:** Read "unavailable" from `scripts/security` as "not on PATH", not as "never ran". Check the pre-commit output for the same tool before concluding a scan was skipped.

**Why:** `scripts/security` reports the secret scan unavailable while gitleaks is passing three lines later in the same `scripts/check` run. Reading the first and not the second understates the coverage and invites installing a redundant copy.

**Source:** [.pre-commit-config.yaml](../.pre-commit-config.yaml)

## Workflows do not run until they exist on the default branch

GitHub registers workflows from the default branch. A pull request that introduces `.github/workflows/` for the first time gets no checks — not a failure, no runs at all.

**Do:** On a first-generation pull request, expect zero checks and say so. Do not read an empty check list as a passing one, and do not wait on runs that cannot start.

**Why:** An empty `statusCheckRollup` and a green one are both "no failures". Reporting CI as passing when nothing ran is the exact substitution this repository's scripts exist to prevent.

**Source:** [Repository settings](../CLAUDE.md)
