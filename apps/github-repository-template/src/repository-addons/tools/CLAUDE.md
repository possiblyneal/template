# Tools

## Purpose

Use `tools/` for helpers that must be built before use, such as code generators. Put portable shell scripts in `scripts/` regardless of who runs them.

## Ownership

- `tools/<name>/` — one program's manifest, source, and tests.

Replace the placeholder with one entry per actual tool as you add it.

## Local Contracts

Add the root workspace manifest with the first tool in a language that requires one. A tool's `go.mod` needs a root `go.work`; a tool's `pyproject.toml` needs a root `pyproject.toml`.
Swift has no root workspace manifest: `scripts/check` discovers `Package.swift` files directly.

## Work Guidance

Treat a tool as a build dependency. Record which version produced its output so differences between committed and regenerated artifacts can be explained.

## Verification

Run `scripts/check` to lint, format-check, type-check, test, and build the detected languages. Keep each tool's manifest reachable from the root so the gate sees it.

## Child Index

None yet. Add and index `tools/<name>/CLAUDE.md` when a tool needs its own rules.
