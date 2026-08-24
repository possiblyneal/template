# Tools

## Purpose

Helpers that must be built before they run: a linter, a code generator, a
protobuf plugin, anything compiled or packaged rather than executed from source.
One directory per program, each owning its own manifest and source.

The split from `scripts/` is by artifact, not by caller. A helper that is a
shell script belongs in `scripts/` however automated its use, and a helper that
needs a build step belongs here however manually it is run.

## Ownership

- `tools/<name>/` — one program: its manifest, its source, its own tests.

Fill this list in as tools arrive. A directory here with nothing in the list is
a tool nobody documented.

## Local Contracts

**A tool whose language has no root manifest is built and tested by nobody.**
`scripts/check` runs from the repository root and reads the manifests it finds
there. A `tools/<name>/go.mod` with no `go.work` above it, or a
`tools/<name>/pyproject.toml` with no root `pyproject.toml`, is invisible to
every check in this repository — and nothing reports the gap, because there is
no failure to report. Add the root manifest in the same change that adds the
first tool in that language.

**A tool is a dependency of the build, not a part of it.** Whatever consumes a
tool's output has to say which version produced it, or a regenerated artifact
differs from the committed one for reasons nobody can reconstruct.

## Work Guidance

Reach for `scripts/` first. This directory earns its complexity only when the
helper genuinely cannot run from source.

## Verification

`scripts/check` — it detects the languages present and runs that language's
lint, format, type, test, and build steps against every manifest reachable from
the root.

## Child Index

None yet. Add a `tools/<name>/CLAUDE.md` when a tool grows rules of its own, and
list it here.
