---
type: Architecture Decision Record
title: Ship Agent Skill Configuration in the Template Payload
description: The payload carries docs/agents/, so a generated repository is configured for the engineering skills at birth and /setup-matt-pocock-skills is skipped rather than run.
scope: [global]
tags: [template-payload, agent-configuration, generation]
generated: { by: "agent/claude-opus-5", at: "2026-09-01T18:00:00Z" }
superseded_by:
status: accepted
---

# Ship Agent Skill Configuration in the Template Payload

## Decision

`apps/github-repository-template/src/base-repo/docs/agents/` ships `issue-tracker.md`, `triage-labels.md`, and `domain.md`, so every generated repository carries them from its first commit. `.claude/skills/repo-builder/references/generate.md` step 6 confirms the three files and skips `/setup-matt-pocock-skills`, invoking it only when a file is missing or the request names something the payload does not record — a tracker other than GitHub Issues, or a label vocabulary the destination already uses.

This covers repositories this template generates. It does not change the engineering skills themselves, which stay stock, and it does not remove the setup skill, which remains the path for a repository built some other way.

## Context

Step 6 ran `/setup-matt-pocock-skills` on every generate to collect three answers that were the same answer every time: GitHub Issues via `gh`, the canonical triage roles unrenamed, the standard domain-doc layout. A question whose answer is a constant is a question worth deleting.

Two failures followed from the files being absent when the candidate materialized. `setup-matt-pocock-skills/SKILL.md:29` reads an existing `.scratch/` directory as a sign that a local-markdown tracker is already in use, so a destination with a stray `.scratch/` and no `docs/agents/` got local markdown proposed — and `/wayfinder` then charted its map into the repository as files instead of onto GitHub Issues, where the native blocking edges that render its frontier live. Separately, the setup skill writes five canonical triage roles where `triage/SKILL.md` defines seven, so the file it produced was already behind the skill that reads it.

`apps/github-repository-template/CLAUDE.md` holds that adding a file to the payload asserts its condition holds for every generated repository. It does here, and step 6 is the proof: the template already ran the setup skill unconditionally, so it already asserted that every repository it builds uses these skills. Shipping the answer replaces asking the question rather than widening what the template claims.

## Alternatives Considered

**Edit the vendored skills to carry standing defaults.** A `DEFAULTS.md` beside `~/.claude/skills/mattpocock/`, pointed at from each consuming skill, would work in every repository including ones this template never touched. Rejected because that tree is a vendored third-party distribution carrying a `VERSION` file rather than a git remote: an upstream bump reverts the edits with no conflict and no warning, and the symptom — skills asking for setup again — arrives long after the cause. This was tried first and backed out.

**Guard inside `setup-matt-pocock-skills` itself.** One skip rule in its Section A would fix the behaviour everywhere. Rejected for the same reason: it is an edit to the vendored tree.

**Leave step 6 unconditional and accept the questions.** Rejected because it preserves the interrogation this decision exists to remove, and because Section B would still overwrite the payload's seven labels with five.

## Consequences

The setup skill is no longer part of the ordinary generate path, and `references/generate.md`, `references/lifecycle.md`, `references/wayfinding.md`, and `SKILL.md` all had prose resting on the fact that it ran. That prose now describes a step that confirms rather than collects.

A manual `/setup-matt-pocock-skills` run still rewrites seven labels as five and adds an `## Agent skills` block to `CLAUDE.md`. That is a deliberate reconfiguration of a repository rather than an accident, and it is left alone: guarding the generate path covers every repository this template builds.

The payload now asserts GitHub Issues as the tracker for every repository it generates. The offline path at `generate.md:37` survives — it overwrites a file that exists instead of creating one — but a destination that tracks work elsewhere gets a file naming the wrong place until someone edits it or runs the setup skill.

`docs/agents/` becomes a payload path rather than a candidate-only addition, so it now falls under the two-tree discipline in `apps/github-repository-template/CLAUDE.md`: a change to this repository's copies and a change to the payload's are two edits in one commit. Their one deliberate divergence is that this repository's `domain.md` names its own ADR-0001 where the payload's carries a placeholder.
