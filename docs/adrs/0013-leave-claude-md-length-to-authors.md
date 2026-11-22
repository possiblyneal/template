---
type: Architecture Decision Record
title: Leave CLAUDE.md Length to Authors
description: The structure audit and the large-file hook impose no length or size limits on CLAUDE.md.
scope: [global]
tags: [documentation, tooling, structure]
generated: { by: "agent/gpt-6.2-astra", at: "2026-11-22T21:58:42Z" }
supersedes: 0012-cap-claude-md-line-and-block-length.md
superseded_by:
status: accepted
---

# Leave CLAUDE.md Length to Authors

## Decision

Authors decide how long a `CLAUDE.md` file, section, block, or line should be. The structure audit does not measure its prose. The large-file hook exempts the exact filename at any depth, both here and in the template payload.

## Context

ADR 0012 used byte counts to enforce readability. The operator chose to leave wrapping and section breaks to authors. Keeping only the repository-wide size check would still prevent adding a long instruction file, so its exemption is limited to `CLAUDE.md` rather than raising the threshold for all files.
