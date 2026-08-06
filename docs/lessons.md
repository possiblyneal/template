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
