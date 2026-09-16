---
type: Architecture Decision Record
title: Create the Destination Repository Before Wayfinding Runs, and End the Generate at Charting
description: A generate creates the repository and its tracker at step 4, derives its application boundaries at step 7, and stops when that derivation escalates to a `/wayfinder` map rather than working the map itself.
scope: [global]
tags: [agent-skills, repository-structure]
generated: { by: "agent/claude-opus-5", at: "2026-09-06T22:15:43Z" }
superseded_by:
status: accepted
---

# Create the Destination Repository Before Wayfinding Runs, and End the Generate at Charting

## Decision

`/repo-builder`'s generate flow creates the destination repository, applies its
settings, and creates its triage labels before it derives the repository's
application boundaries. Boundary derivation is step 7; the repository exists from
step 4.

Where that derivation escalates to `/wayfinder`, the generate charts the map and
stops. It reports `stopped`, opens no pull request, and leaves the materialized
candidate and the created repository in place to resume against. It does not work
a ticket, and it does not answer the method's six steps on the user's behalf.

## Context

Two orderings were available and only one of them leaves the map somewhere it can
be found again.

`/wayfinder` charts against whatever `docs/agents/issue-tracker.md` records, and
that file resolves the repository from `git remote -v`. A handoff before the
repository exists has nowhere durable to chart to, and the fallback — an effort
directory of Markdown files — cannot render a frontier from blocking edges, which
`/wayfinder` treats as essential. On the ordinary GitHub answer the map's native
`blocked_by` edges are what make the frontier visible in GitHub's own interface.
`gh issue create --label wayfinder:map` also fails outright until the label
exists, which is step 6's work against a repository step 4 created.

Step 7 is simultaneously the last position where the question can still be asked:
step 8 is the first thing that reads the answer, and nothing before it depends on
one. Asking there means an escalation stops a generate that has already banked
every deterministic thing it can — repository, settings, tracker, materialized
candidate — so the resumed session re-enters at personalization rather than
rebuilding the tree.

Stopping at charting is the point of reaching for `/wayfinder` at all. Its value
is concentrated in the answers only the user can give: a UI event mistaken for a
domain event, two aggregates that looked like one until asked whether either could
change alone. A generate that pushed on through its own map would hand back the
decomposition it had already guessed, wearing an ADR that claims it was
deliberated. Resuming with even one ticket open reads a partial answer out of
Decisions so far and records it as settled.

## Alternatives Considered

**Derive the boundaries before creating the repository**, so a stop leaves no
remote artifact. Rejected: it puts the map in an effort directory nobody finds
again, and gives up the frontier the tracker renders natively. It also inverts the
cost — a stop then discards the deterministic work rather than banking it.

**Let the generate work its own map.** Rejected for the reason above: the output
would be the skill's own first guess with a deliberation record attached, which is
worse than no ADR.

**Collect the boundaries as answers at step 2, with the other decisions.**
Rejected: they are derived from a decomposition, not preferences to collect. The
short form still asks the user, but it asks with a proposal on the table and
records what constraint bound.

## Consequences

A failed or stopped generate leaves a real repository the user now owns. The
failure report has to name it and say what it already carries, or the user goes
looking for something they already have.

The repository is created at a remote action gate that precedes any content, so
that gate authorizes an empty repository and a second gate at step 11 authorizes
publishing reviewed content. Two gates rather than one is a direct consequence of
this ordering.
