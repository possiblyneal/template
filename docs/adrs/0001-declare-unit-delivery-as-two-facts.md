---
type: Architecture Decision Record
title: Declare Unit Delivery as Two Independent Facts Rather Than One Shape Name
description: Every unit under apps/ declares how it runs and what it ships as two separate facts in .unit.json, rather than a single word naming what kind of application it is.
scope: [global]
tags: [repository-structure, build-and-release, language-capabilities]
generated: { by: "agent/claude-opus-5", at: "2026-08-30T18:14:33Z" }
superseded_by:
status: proposed
---

# Declare Unit Delivery as Two Independent Facts Rather Than One Shape Name

## Decision

Every unit under `apps/` carries a `.unit.json` at its root declaring
`schema_version` and two independent facts:

- `run` — `oneshot` | `longlived` | `none`: how the unit is invoked locally.
- `ships` — an object with `kind` (`executable` | `quadlet` | `none`) plus
  kind-specific parameters; `executable` carries `targets`.

The facts are independent: any `run` value may pair with any `ships` value, and
nothing validates the combination. `scripts/structure` requires the file on every
unit and checks each value against a fixed enum, values only.

This covers what the template must dispatch on. It explicitly does not name an
entry point — the Go adapter keeps resolving main packages and keeps refusing when
several exist — and does not describe architectural position (frontend, backend),
which no check consumes.

## Context

The template detects languages but cannot detect what a unit *is*. A Go module with
one `main` package is a CLI, a TUI, or a long-running service, and nothing on disk
distinguishes them. Two capabilities need that answer and no other source can supply
it: what `scripts/dev` should start, and what `scripts/release` should attach.

The obvious design is one declared word — `cli`, `service`, `web`. Enumerating the
candidate shapes and filtering them by the only test that matters — does this change
what we run, or what we ship? — broke that design on two entries. A **scheduled job**
runs oneshot like a CLI but ships as a container like a service; one word cannot
carry both. A **library** has nothing to run at all and still ships. The two facts
vary independently, so one name has to encode their product, and the product grows
combinatorially while each fact stays small.

`/home/neal/code/knowledge-base` settled it against a real repository. That single
unit is a FastAPI service, a Jinja-rendered web UI, and a `python -m kb` maintenance
CLI simultaneously. No shape name fits it. `run: longlived, ships: quadlet` does.

## Alternatives Considered

**One `shape` word per unit.** Rejected because scheduled job and library have no
consistent single-word form, and because the real driving case is three shapes at
once.

**Detect instead of declare.** Rejected: the fact is not on disk. A `main` package
compiles identically whatever it becomes at runtime.

**Concrete artifact names in `ships` (`binary`, `tarball`, `image`).** Rejected in
favour of intent, so each language adapter chooses the concrete form — a Go binary
and a Python wheel are both `executable`. The one break from that principle is
`quadlet`, which names a file format because the alternative names nothing usable:
"container" would suggest the template builds an image, which it deliberately does not.

**A `site` kind and a TTY flag.** Both dropped for having no consumer. Nothing in the
capability layer reads either, and `interactive` is orthogonal to lifecycle anyway —
`k9s` and `htop` are long-lived *and* interactive, so a third `run` value would be a
category error.

## Consequences

**`scripts/dev` becomes `scripts/run`.** The old name promised a dev server, which is
one shape's version of the fact. `run` is lifecycle-neutral and idiomatic in all six
supported languages. Argument passthrough uses a `--` separator; the unit name stays
optional when only one unit exists and required when several do.

**`package` is a new capability, invoked at release only.** `scripts/release` walks
`apps/`, packages every shippable unit, and skips `ships: none`. One tag releases
everything.

**`ships: quadlet` produces no release asset.** The unit ships
`deploy/quadlet/<name>.build` and `<name>.container`; systemd and podman build on the
deploy host. `package` only *validates* the pair — that `.build` names a real
Containerfile and `.container`'s `Image=` matches it. The template never shells out to
podman, so `scripts/doctor` needs no container-runtime check and a machine without
podman can still run the full gate.

**The unit definition changes.** "Deploys, scales, and versions independently" — the
Dockerfile test — is replaced by "the smallest piece of this repository delivered on
its own: deployed, installed, published, or copied." The old test silently excluded
every unit that is installed rather than deployed, which is what a CLI is.

**The `run` fact earns its place unevenly.** In Go and Rust the dispatch is a no-op —
the command is identical whatever the unit is. In Node and Python it is real: a CLI
runs its `bin`/console-script entry, a service runs its dev server. A future reader
who audits only the Go adapter will conclude the fact is dead weight. It is not.

**Every unit now needs a file it did not need before,** including single-unit
repositories that never ship anything. The payload skeleton ships a filled-in
`.unit.json` with `run: none, ships: none` so the cost is a value to change, not a
file to discover.

**Adapting an existing repository can mean moving its source.** `knowledge-base` keeps
`src/` at the repository root, which the root-folder allowlist does not permit;
adopting the template means `apps/kb/src/`.

**Deferred:** worker, scheduled job, desktop GUI, serverless function, plugin, and
library are all expressible in the two facts but have no adapter wired. Python and
Node report no runner for `ships: executable` until someone needs them.
