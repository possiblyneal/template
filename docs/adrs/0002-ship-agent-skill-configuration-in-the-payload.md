---
type: Architecture Decision Record
title: Ship Agent Skill Configuration in the Template Payload
description: The payload carries docs/agents/, so a generated repository is configured for the engineering skills at birth rather than being asked to configure itself.
scope: [global]
tags: [template-payload, agent-configuration, generation]
generated: { by: "agent/claude-opus-5", at: "2026-09-01T17:53:28Z" }
superseded_by:
status: accepted
---

# Ship Agent Skill Configuration in the Template Payload

## Decision

`apps/github-repository-template/src/base-repo/docs/agents/` ships `issue-tracker.md`, `triage-labels.md`, and `domain.md`, so every generated repository carries them from its first commit. `apps/repo-builder/src/references/generate.md` step 6 confirms the three files are present.

Step 6 also creates the labels those files name, plus `wayfinder:map`, since a file recording label strings does not make them exist and step 7's `gh issue create --label wayfinder:map` fails until they do.

This covers repositories this template generates. It does not change the engineering skills themselves, which stay stock.

## Context

Step 6 ran a setup skill on every generate to collect three answers that were the same answer every time: GitHub Issues via `gh`, the canonical triage roles unrenamed, the standard domain-doc layout. A question whose answer is a constant is a question worth deleting.

Two failures followed from the files being absent when the candidate materialized. `setup-matt-pocock-skills/SKILL.md:27` reads an existing `.scratch/` directory as a sign that a local-markdown tracker is already in use, so a destination with a stray `.scratch/` and no `docs/agents/` got local markdown proposed — and `/wayfinder` then charted its map into the repository as files instead of onto GitHub Issues, where the native blocking edges that render its frontier live. Separately, the setup skill writes five canonical triage roles where `triage/SKILL.md` defines seven, so the file it produced was already behind the skill that reads it.

`apps/github-repository-template/CLAUDE.md` holds that adding a file to the payload asserts its condition holds for every generated repository. It does here, and step 6 is the proof: the template already ran the setup skill unconditionally, so it already asserted that every repository it builds uses these skills. Shipping the answer replaces asking the question rather than widening what the template claims.

## Alternatives Considered

**Edit the vendored skills to carry standing defaults.** A `DEFAULTS.md` beside `~/.claude/skills/mattpocock/`, pointed at from each consuming skill, would work in every repository including ones this template never touched. Rejected because that tree is a vendored third-party distribution carrying a `VERSION` file rather than a git remote: an upstream bump reverts the edits with no conflict and no warning, and the symptom — skills asking for setup again — arrives long after the cause. This was tried first and backed out.

**Guard inside the setup skill itself.** One skip rule in its Section A would fix the behaviour everywhere. Rejected for the same reason: it is an edit to the vendored tree.

**Leave step 6 unconditional and accept the questions.** Rejected because it preserves the interrogation this decision exists to remove, and because Section B would still overwrite the payload's seven labels with five.

## Consequences

The setup skill is no longer part of the generate path, and `references/generate.md`, `references/lifecycle.md`, `references/wayfinding.md`, and `SKILL.md` all had prose resting on the fact that it ran. That prose now describes a step that confirms rather than collects. Running that skill by hand in a generated repository is a deliberate reconfiguration rather than an accident, and it is left alone; note that it writes five canonical triage roles where `triage/SKILL.md` defines seven, so it puts the repository behind the skill that reads it.

The payload now asserts GitHub Issues as the tracker for every repository it generates. The offline path at `generate.md:37` gets worse rather than better, and says so: step 6 finds the files present as always, but has no repository to create labels on, and step 7 cannot chart at all, because the tracker doc resolves the repository from `git remote -v` and there is no remote. Before this change that path settled on a local tracker and produced a map; now it produces a plan and stops, which is the honest outcome for a generate that never reached GitHub but is a capability lost. A destination that tracks work elsewhere likewise gets a file naming the wrong place until someone edits it.

`docs/agents/` becomes a payload path rather than a candidate-only addition, so it now falls under the two-tree discipline in `apps/github-repository-template/CLAUDE.md`: a change to this repository's copies and a change to the payload's are two edits in one commit. Their one deliberate divergence is that this repository's `domain.md` names its own ADR-0001 where the payload's carries a placeholder.

Because `.repo-template.json` marks `docs/**` as product, a later fix to the payload's `docs/agents/` never reaches an already-generated repository through `/repo-builder` update — product is preserved automatically, so the files land once, at generation. The divergence is reported rather than hidden: the path is still in the old-to-new delta, and `update.md` step 5 classifies it `preserved`, so a reader of the update's report can see the fix was withheld and port it by hand. That is the intended ownership (a repository's own tracker doc is its own), but it means these three files get one chance to be right per repository.

## Amendment — 2026-09-22

The payload's root `CLAUDE.md` no longer carries the `## Agent skills` block this record originally named as the mechanism. It ships as an empty section skeleton whose Child Index instruction is the destination's prompt to index itself, and building that tree is the last thing done either way: a retrofit does it among its final steps, and a generate does no part of it at all, leaving it to the destination's first session after the handoff. `docs/agents/` is reached by path instead, which is what `docs/CLAUDE.md` already recorded.

The decision itself is unchanged: the three files still ship, and step 6 still confirms them. What changes is the provision, and it is not restored by anything downstream. `/wayfinder`, `/triage`, `/to-spec`, and `/to-tickets` each say the tracker "should have been provided to you"; `wayfinder/SKILL.md` then defaults to local markdown outright and the others leave it unspecified, which is the worse state of the two. So the gap lasts until something names the tracker in a file that loads automatically. The destination's indexing pass does not necessarily do it: that pass writes child `CLAUDE.md` files and a Child Index of paths, and a bullet naming `docs/CLAUDE.md` names no tracker.

The exposure also starts before the destination is indexed at all. `generate.md` step 7 charts the wayfinding map, and `references/wayfinding.md` has `/wayfinder` reading `docs/agents/issue-tracker.md` — which the vendored skill does not do by path. So the generate's own charting runs in the window, which is the failure this record's Context paragraph describes. A generated repository carries the right files from its first commit and does not yet advertise them; closing that is work this amendment records rather than performs.
