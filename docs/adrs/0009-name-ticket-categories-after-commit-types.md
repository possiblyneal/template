---
type: Architecture Decision Record
title: Name Ticket Categories After Conventional Commit Types
description: The triage category roles are the eleven Conventional Commit types, with fix, feat and docs labelled by GitHub's default names bug, enhancement and documentation.
scope: [global]
tags: [agent-skills, agent-configuration, template-payload]
generated: { by: "agent/claude-opus-5-5", at: "2026-11-07T12:00:00Z" }
superseded_by:
status: accepted
---
# Name Ticket Categories After Conventional Commit Types

## Decision

A ticket carries one of eleven category roles, one per Conventional Commit type in `@commitlint/config-conventional`'s `type-enum`. Each label is the type's own name except three, which keep the label GitHub creates on every repository: `bug` for `fix`, `enhancement` for `feat`, `documentation` for `docs`. With the five state roles that makes sixteen, which `/triage` defines and repo-builder creates. Governs the default vocabulary only; a `triage_labels` departure under `docs/adrs/0007-carry-agent-skill-defaults-in-the-skills.md` still overrides any label string.

## Context

The two categories, `bug` and `enhancement`, left no honest label for a performance ticket, a refactor, or a chore, so such tickets were filed under whichever was least wrong. Commits already carry a closed, mutually exclusive type vocabulary, enforced by commitlint, so a ticket's category can be the type its main commit will carry and an agent reads one from the other.

## Alternatives Considered

- **A curated subset** (`bug`, `enhancement`, `performance`, `refactor`, `documentation`, `chore`). Rejected: each review found another ticket that fit none, and choosing which types count is a judgement every repository would re-litigate.
- **Every type under its commit name** (`fix`, `feat`, `docs`). Rejected: GitHub creates `bug`, `enhancement` and `documentation` on every repository and people reach for them, so agents filing `fix` and people filing `bug` would split one category across two labels, or every repository would need its defaults renamed.

## Consequences

- An agent turning a ticket into a commit maps three labels to their types; `/triage`'s Roles list holds that mapping once.
- `style` and `revert` will rarely be applied. An unused label costs a line in the label list.
- Repo-builder creates eight labels the host does not ship and renames none.
