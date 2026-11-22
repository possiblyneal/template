---
type: Architecture Decision Record
title: Cap CLAUDE.md Line and Block Length in the Structure Audit
description: scripts/structure fails a CLAUDE.md with a physical line over 200 bytes or a rendered block over 600, and advises on a run over 8,000 bytes between headings.
scope: [global]
tags: [documentation, tooling, structure]
generated: { by: "agent/claude-opus-4-8", at: "2026-11-19T00:00:00Z" }
superseded_by: 0013-leave-claude-md-length-to-authors.md
status: superseded
---

# Cap CLAUDE.md Line and Block Length in the Structure Audit

> Superseded by [ADR 0013: Leave CLAUDE.md Length to Authors](0013-leave-claude-md-length-to-authors.md).

## Decision

`scripts/structure` reads every tracked `CLAUDE.md` and enforces two caps as
`FAIL`: no physical line over 200 bytes (`claudemd-lines`), and no rendered
block over 600 bytes (`claudemd-blocks`). A block is a paragraph or a single
list item — a list marker opens a new block. A third measure, a run over 8,000
bytes between headings, is a non-failing advisory: the `claudemd-blocks` row
counts it, so it shows in `scripts/check`'s table, and `scripts/structure`
lists each one below its own.

Lengths are measured in bytes, under `LC_ALL=C`. Fenced code (```` ``` ```` or
`~~~`, closed only by its own character at its opening length or longer), table
rows, and a line whose content is a single unbreakable token (a URL, a path)
are exempt from both caps; a heading is capped like any line. The caps govern `CLAUDE.md` files only; no other Markdown is
touched.

## Context

A `CLAUDE.md` is the local work contract, re-read every session before its
subtree is edited, so its length is paid in tokens and attention on every
visit. Left ungoverned, a contract drifts into unscannable walls of prose. A
mechanical cap keeps it legible without a human having to notice the drift.

The check lives in `scripts/structure` rather than a new script because
`structure` already audits the shape of the tree, already runs in pre-commit
and the gate, and is deliberately language-independent — it sources no
detection library and shells out to nothing a generated repository might lack.
A readability cap is the same kind of rule: it reads a file's shape, not its
meaning, and must run everywhere the audit does.

## Alternatives Considered

**Count Unicode code points, not bytes.** An em-dash is one glyph but three
bytes, so a byte cap flags a line a reader sees as under width. Rejected: a
portable code-point count in POSIX `awk` is not available without a guaranteed
UTF-8 locale, and the audit must give the same answer on every host. The files
are almost all ASCII, so the gap is a few bytes on a handful of lines, paid for
by a cap that is deterministic everywhere.

**Fail on an over-long section too.** Rejected: where a heading belongs is a
judgment about meaning, not a mechanical fact, and the audit does not force
judgments — the same reason three placement rules are reported
`not-applicable`. The template's own root and payload `CLAUDE.md` files run past
8,000 bytes between headings by design, so a `FAIL` there would be noise. The
advisory surfaces the length and leaves the call to the author.

**Require a quota of bold or italic markup for human readability.** Rejected:
markup density is a crude proxy for legibility and would reward noise over
substance. The length caps push toward structure — headings, lists, short
blocks — without dictating the prose.

## Consequences

Editing a `CLAUDE.md` now carries a wrapping discipline: a long paragraph must
be split at a blank line or behind a new heading, and a long line rewrapped.
The finding names the file, the line, the byte count, and the fix. Guidance on
which Markdown features keep a contract readable is not part of the check and
is not recorded here.

Because the caps are measured in bytes, a line dense with multi-byte
punctuation fails a little earlier than its glyph count suggests; the finding's
byte count makes the reason visible.
