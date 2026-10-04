---
type: Architecture Decision Record
title: Stage a Retrofit Locally and Write to the Host Last
description: A retrofit builds and proves its candidate in a linked worktree, reviews it before any hosted write, and performs every hosted write at one gate after the bar, with each fixed step recorded by a script.
scope: [apps/repo-builder]
tags: [repo-builder, retrofit]
generated: { by: "agent/claude-opus-5-5", at: "2026-10-04T13:16:16Z" }
superseded_by:
status: accepted
---

# Stage a Retrofit Locally and Write to the Host Last

## Decision

A retrofit (`apps/repo-builder/src/references/retrofit.md`) is shaped by
seven choices:

1. The candidate is a linked worktree of the operator's clone, under this
   repository's `tmp/`.
2. Every hosted write happens at one gate, after the bar is met.
3. Generate's ruleset probe is not run.
4. One architecture record covers the whole decomposition.
5. The destination's autofix is bounded to what its tools do unattended,
   and committed alone.
6. The authored surface is reviewed before the hosted-write gate.
7. Every fixed step is a `retrofit.py` subcommand writing a JSON record at
   one prefix, and the report and pull-request body are rendered from those
   records.

This covers the retrofit flow only. Generate, update and adopt keep their
own orderings.

## Context

A retrofit's destination already has content, history, collaborators and
hosted state that somebody chose. Generate's shape assumes an empty
repository: it creates the repository early, probes the ruleset by pushing
to the default branch, and writes one record per deployable. Each of those
does harm against a destination that is being shipped. The retrofit was
also paying for prose: the session redid by hand, every run, work that has
one correct answer, then copied the results into a report.

## Alternatives Considered

- **A payload-only candidate, as generate builds one.** Rejected because
  the pull-request diff would not be the destination's real history. A
  linked worktree carries that history and shares the clone's objects, so a
  large history costs disk once. It also leaves the operator's working
  directory untouched. It sits under `tmp/` because `tmp/*` is gitignored
  here and a resumed run needs a fixed address.
- **Hosted writes where generate makes them, early.** Rejected because a
  destination whose bar cannot be met would then have had settings, labels
  and a renamed branch changed for nothing. Nothing before the gate needs
  the host: the repository exists and the tracker is the destination's
  own. With every write after the bar, a stopped run has changed nothing on
  the host, and re-running it undoes nothing.
- **Generate's ruleset probe.** Rejected because it pushes a throwaway
  commit to a live default branch. Where enforcement is missing, only a
  force-push removes that commit, and other people's clones fetch it in the
  meantime. The retrofit's own pull request proves the ruleset through
  `mergeable`/`mergeStateStatus` at no extra cost, so enforcement is
  reported as not yet proven at the gate.
- **One record per unit, as generate writes.** Rejected because a retrofit
  argues no choke point per deployable. It observes languages the
  destination already chose, so a record per unit would restate a choice
  nobody made.
- **No autofix, or autofix mixed into the flow's own commit.** Without a
  pass, every retrofit stops at formatter and lint debt the destination's
  own tools would clear. Mixed into the flow's commit, the formatter's
  near-total rewrite buries the edits this flow judged, and the operator
  cannot revert it alone. The pass therefore never takes unsafe fixes,
  runs at most twice, and lands as its own commit. That commit's diff is
  also exactly the set of paths kept off the reviewed surface.
- **Review after the pull request opens.** Rejected because a review that
  late can stop nothing. A correction pushed after it moves the head that
  the gate, the checks and the merge offer were read against. Reviewing
  the local candidate before the gate lets the pull request open at the
  head that was reviewed. The PR-open review request is then answered by
  that review rather than by a second one.
- **The session computes and transcribes results by hand.** Rejected
  because a count assembled by reading cannot be reproduced, and a line
  copied into the report can disagree with the run it describes. Each
  fixed step writes `<records>.<name>.json` under one prefix. The renderer
  reads those records by name and leaves only the judgements as fill
  slots, and an absent record says the step did not run.

## Consequences

- The candidate, its branch and the records outlive a stopped run, and the
  sweep removes the candidate only once the flow ends.
- Ruleset enforcement is unproven until a pull request exists. A ruleset
  that cannot be satisfied is found at step 9, after it has been written.
- Behaviour now lives in two places, the step references and
  `retrofit.py`. A change to a step's fixed work is a code change with
  tests, and the reference describes only the judgement around it.
