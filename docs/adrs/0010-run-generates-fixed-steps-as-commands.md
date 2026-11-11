---
type: Architecture Decision Record
title: Run Generate's Fixed Steps as Commands and Keep Their Reasoning Out of the Run
description: A generate's mechanical steps become generate.py subcommands over checked-in ownership and ruleset data, generate.md states only the rules a generate applies, and the reasoning behind each fixed step lives outside what a run reads.
scope: [apps/repo-builder]
tags: [repo-builder, generate]
generated: { by: "agent/claude-opus-5-5", at: "2026-11-11T12:00:00Z" }
superseded_by:
status: accepted
---

# Run Generate's Fixed Steps as Commands and Keep Their Reasoning Out of the Run

## Decision

A generate (`apps/repo-builder/src/references/generate.md`) is shaped by
five choices:

1. Generate's fixed steps become `generate.py` subcommands, each writing a
   JSON record at one prefix, the way `retrofit.py` and `update.py` already
   run theirs. The ownership rules a generated repository starts with and
   the ruleset body are checked-in data, not copied from another repository.
2. `generate.md` states the lifecycle rules a generate needs inline, each
   with an anchor link to its `lifecycle.md` section, so a generate never
   opens `lifecycle.md` whole. The rules for a destination that already has
   content live in `references/generate-into-content.md`, read only when the
   destination is not empty.
3. The reasoning behind a fixed step is not on the path a run reads. It is
   recorded below until the step's command carries it as a docstring. Each
   step keeps its instruction and a link here. Judgement text stays inline:
   `CODEOWNERS`, the explicit pull-request body, and when to stop.
4. The ruleset probe is kept, unlike a retrofit's step 8.
5. A bootstrap generate merges its own pull request.

## Context

An empty-destination generate read `lifecycle.md` and `generate.md` whole,
about 100 KB, most of it about update, retrofit, adopt, or a destination
with content (`docs/research/generate-eval-baseline.md` records the bytes).
It then rebuilt six mechanical steps from prose on every run, and copied two
inputs that had no canonical source: the ruleset body from this template's
live ruleset, and the ownership array from another generated repository.
Retrofit and update had already solved the same problem with a script per
flow and inline lifecycle extracts
(`docs/adrs/0005-stage-a-retrofit-locally-and-write-the-host-last.md`).

The probe stays because a generate's ruleset is new and nothing else proves
it binds: creation returns 201 whether or not it does. A retrofit skips it
because its destination is shared and already in use, where a direct push to
the default branch is not a throwaway. A generate's default branch is still
the empty root commit, so the probe costs nothing but the rewind.

The bootstrap merge stays because the destination's default branch is the
empty root commit, so no worktree can be checked out against it to review
the pull request before it merges. Every other flow has a destination
worktree for ordinary review and never merges.

## Reasoning behind the fixed steps

### The merge settings go in one call

GitHub refuses to leave a repository with no merge method enabled, so turning
squash and rebase off against a destination that already has the merge commit
off is rejected when the three are sent separately and accepted when they
arrive together. `allow_merge_commit=true` is therefore not a no-op on a
repository that looks fine — it is what makes the other two writable.

### REST and GraphQL name the merge settings differently

Each of the two routes to these settings has its own field names, and neither
route rejects the other's. REST — `gh api repos/<owner>/<name>` and the
`PATCH` — names them `allow_merge_commit`, `allow_squash_merge`,
`allow_rebase_merge`, `delete_branch_on_merge`. The GraphQL-backed
`gh repo view --json` names the same four `mergeCommitAllowed`,
`squashMergeAllowed`, `rebaseMergeAllowed`, `deleteBranchOnMerge`. Ask either
route for the other's names and every field comes back `null` rather than an
error, which reads exactly like a repository with all four settings off — so
the wrong spelling produces a confident wrong answer that survives being
checked. Name the endpoint and its field set together wherever either is
written down.

### A required status check is named by its check run

GitHub matches every `required_status_checks[].context` the ruleset names
against the name a check run reports, which is the job's `name:` where the
workflow sets one and the job id only where it does not. The payload sets both
on every job, so the two always differ.

Require `ci` rather than `CI` and nothing ever reports that context, so it
stays pending for the life of the repository. That failure is invisible from
every angle the flow otherwise checks: creation returns 201, the ruleset reads
back `active`, `scripts/repo-settings check` passes it, the probe is rejected
exactly as it should be — and the default branch is simply never mergeable,
with nothing anywhere naming the misspelling as the cause.

Require only contexts a run on this repository has actually reported.
`codeql.yml`'s analyze leg is one context per language and `release.yml` does
not run on a pull request, so neither belongs in a rule gating one. A gated
`codeql.yml` leg is not that trap: on a destination that is not public
`Detect languages` reports a completed check run with conclusion `skipped`
under the same name it reports when it runs, rather than never reporting. The
analyze leg reports its name unexpanded when skipped, which is a second reason
it does not belong in a rule.

### The probe is empty and rewound with `update-ref`

The materialized payload is sitting untracked in the candidate's own worktree,
and a `git reset --hard` against an empty base takes the working tree with the
probe. An empty commit rewound with `update-ref` leaves the working tree
alone.

### `check-ignore --no-index` reads the direction the totals miss

An ignored payload path that appears in the tracked comparison is the defect
the two file lists agree about. For each such path the delivered state is
present on disk and absent from history, so a candidate that committed one is
wrong in a way both comparisons read as correct: the tracked list matches the
payload's, because the template repository tracks all of them itself, and the
untracked list is merely short. So check the direction rather than the totals.
`--no-index` is the whole of it: without the flag `check-ignore` skips a
tracked path and reports nothing on exactly the case this catches.

## Consequences

- A generate reads only the rules it applies; a lifecycle section is opened
  through an inline bullet's anchor link, and only when its statement is not
  enough.
- The inline extracts are a second statement of `lifecycle.md`.
  `test_reference_assertions.py` holds their code spans verbatim to the
  linked section, as it does for `retrofit.md` and `update.md`; the prose
  around the spans can still drift.
- A content-destination generate opens one more file than before.
