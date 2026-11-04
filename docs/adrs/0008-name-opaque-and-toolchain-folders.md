---
type: Architecture Decision Record
title: Name the Folders a Repository Needs Beyond Its Code, and Let Tools Fix the Rest by Table
description: config/, examples/, and vendor/ join the scoped folders, examples/ and vendor/ stop the depth rules as src/ does, and a folder a toolchain fixes by name beside its manifest is permitted from a template table rather than per repository.
scope: [global]
tags: [template-payload, repository-layout]
generated: { by: "agent/claude-opus-5-5", at: "2026-11-03T12:00:00Z" }
superseded_by:
status: proposed
---

# Name the Folders a Repository Needs Beyond Its Code, and Let Tools Fix the Rest by Table

## Decision

`config/`, `examples/`, and `vendor/` are scoped folders, permitted at the root, a unit, or a domain. `examples/` and `vendor/` are opaque: the depth rules stop at them as they stop at the first `src/`, and `vendor/` is excluded from lint, format, type check, test, and every pre-commit fixer and lint, while the secret and large-file hooks still read it. A folder whose name a toolchain fixes beside a manifest, such as `gradle/` beside `gradlew` or `public/` beside `package.json`, is permitted only beside that file, from `toolchain_folders` in `scripts/structure`. Nothing else is added.

## Context

A survey of popular repositories found three needs the scoped folders could not hold without `.structure-allow`: runnable sample programs (`examples/`), third-party code kept verbatim (`vendor/`), and read settings distinct from assets (`config/`). Each would otherwise be a per-repository permission, which is the drift the template exists to prevent. The same survey found folders no layout can rename, because a tool looks for them by name beside its manifest; `gradle/` was already a root special case.

An example and a vendored tree each carry their own layout, often with their own `src/`, so holding them to this repository's depth rules would reject them for being what they are. A vendored tree is someone else's code, so a lint or format finding in it is noise or, after an autofix, an unrecorded fork.

## Alternatives Considered

- **Permit each in `.structure-allow`.** Rejected: the folder exists in most repositories that grow, and a per-repository entry makes its location unpredictable, failing the template's first question.
- **Permit toolchain folders anywhere by name.** Rejected: `public/` without `package.json` beside it is an ordinary misplaced folder, and the pairing is what tells the two apart.
- **Keep `config/` under `assets/`.** Rejected: a setting changes how a program behaves and an asset does not, and an agent looking for one should not search the other.

## Consequences

- The table grows by template change only, so a repository whose tool needs an unlisted folder waits on the template or uses `.structure-allow` until then.
- Nothing checks that `vendor/` holds unmodified code; a patched copy belongs in `libs/` as a fork, and only review enforces that.
- Every language adapter must keep excluding `vendor/`; `scripts/tests/capabilities-test` pins the Python commands, and the Go format check reads `go_sources`.
