---
type: Architecture Decision Record
title: Carry the GitHub Tracker and Label Defaults in the Skills, and Record Departures in the Manifest
description: The engineering skills carry the GitHub Issues, gh, and seven-role label defaults, and a repository that differs records a departure in .repo-template.json generation.features instead of shipping docs/agents/.
scope: [global]
tags: [template-payload, agent-configuration, agent-skills]
generated: { by: "agent/claude-sonnet-5-5", at: "2026-10-11T12:00:00Z" }
supersedes: docs/adrs/0002-ship-agent-skill-configuration-in-the-payload.md
superseded_by:
status: accepted
---

# Carry the GitHub Tracker and Label Defaults in the Skills, and Record Departures in the Manifest

## Decision

`/wayfinder`, `/triage` and `/ship` carry the defaults: GitHub Issues via `gh`, the seven canonical triage roles unrenamed, pull requests not a request surface. A repository that differs records a **departure** in `.repo-template.json` under `generation.features` (`issue_tracker`, `prs_are_requests`, `triage_labels`); absent a record, the default holds. The payload and this repository ship no `docs/agents/`.

## Context

The three `docs/agents/` files held the same content in every repository, and every per-repo copy cost tokens on each read. `domain.md` had no reader at all. Because `docs/**` is product, a fix to the payload copies also never reached an existing repository.

[ADR-0002](0002-ship-agent-skill-configuration-in-the-payload.md) rejected editing the vendored skills because an upstream bump reverts the edits silently. That no longer holds: the vendored tree is tracked in devex git, so a bump that drops the edits shows in the diff, and devex's root `CLAUDE.md` lists the local edits to re-apply.

## Alternatives Considered

**A personal overlay skill with a pointer file.** Rejected because it adds a second skill and a pointer to read on every run to carry text that is constant; the vendored skills can hold it directly now that edits are visible.

**Keep the per-repo files.** Rejected because the content is constant, each copy is read on every use, and a repository that does differ is better served by a small structured record than by a file that mostly restates the defaults.
