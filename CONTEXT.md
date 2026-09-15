# Template

This repository builds other repositories. Its language is about how a
repository is shaped, what its parts deliver, and which checks apply to them.

## Language

### Structure

**Unit**:
The smallest piece of a repository delivered on its own — deployed, installed,
published, or copied. One folder under `apps/`.
_Avoid_: app, service, package, project, module

**Domain**:
A distinct business area within a unit, given its own folder when isolation
earns its keep. A unit has domains or it has none.
_Avoid_: subdomain, area, feature

**Scope holder**:
A place that owns scoped folders — the repository root, a unit, or a domain.
`apps/` is not one.
_Avoid_: container, parent, level

**Scoped folder**:
A folder whose contents belong to exactly one scope: `libs/`, `tests/`,
`scripts/`, `tools/`, `assets/`, `docs/`, `deploy/`.
_Avoid_: shared folder, common folder

### Delivery

**Unit declaration**:
`.unit.json` at a unit's root, stating how that unit runs and what it ships.
_Avoid_: unit config, manifest, metadata

**Run fact**:
How a unit is invoked locally: `oneshot` for a process that exits on its own,
`longlived` for one that runs until stopped, `none` for a unit with nothing to run.
_Avoid_: shape, type, mode, dev command

**Ship fact**:
What a unit delivers, named as intent so the language adapter decides the
concrete form: `executable`, `quadlet`, or `none`.
_Avoid_: artifact type, output, build target

**Target**:
A platform an executable is built for, in a vocabulary the template owns and
each language adapter translates: `linux-amd64`, `macos-arm64`.
_Avoid_: platform, arch, triple, GOOS

**Web language**:
Node, the language this template reaches for when a unit serves or renders. A
Node unit that runs and exits is a script or a job; a CLI here is written in Go,
Rust, or Python.
_Avoid_: frontend stack, JS, TS, JavaScript

**Shape**:
Deliberately not a term here: one word naming what a unit "is" collapses the run
fact and the ship fact, which vary separately. ADR 0001 has the argument.
_Avoid_: shape, kind, app type

### Template

**Payload**:
The content copied into repositories generated from this one. Editing it changes
every future generated repository and changes nothing here.
_Avoid_: template files, source, boilerplate

**Addon**:
A file held back from the payload for a generated repository to adopt when the
occasion arrives, rather than shipped to every repository by default.
_Avoid_: optional file, extra

**Addition by occasion**:
The rule that governs an addon — it arrives when a repository has a reason for
it, not at generation.
_Avoid_: optional, as-needed

### Flows

**Flow**:
One of the four routes the payload takes into a repository: `generate`,
`update`, `adopt`, `retrofit`.
_Avoid_: mode, command, operation, run

**Destination**:
The repository a flow acts on. Never this repository, and never the candidate.
_Avoid_: target, output repo, the repo

**Retrofit**:
Landing the payload in a repository that grew without it, which arrives with its
own content and no record of the template.
_Avoid_: convert, migrate, onboard, adopt, backfill

**Overridden path**:
A payload path a flow did not land, because the destination's own version was
chosen over it.
_Avoid_: skipped file, collision, exception

**Candidate**:
The working copy of a destination a flow builds and measures before publishing
anything. It is not the destination: the destination is what the pull request
asks to change.
_Avoid_: working copy, staging repo, draft, workspace

**Resume record**:
The account, held beside the candidate, of what a stopped flow decided and of the
writes it made that cannot be observed back.
_Avoid_: journal, checkpoint, state file, progress file

**Unobservable write**:
A write a flow cannot recognize as its own by reading the destination back, so
repeating it duplicates rather than repeats.
_Avoid_: keyless write, non-idempotent write

**Hosted write**:
A change to a destination's state on GitHub itself, which no pull request can
carry.
_Avoid_: remote write, settings change, API call

**Authored surface**:
The part of a candidate a flow wrote rather than copied, and so the only part a
reader must read line by line. A file proved identical to what it was copied
from, or proved unchanged by a move, is not on it.
_Avoid_: custom content, hand-written files, non-template files, the diff

### Checks

**Capability**:
A named check or action — `lint`, `test`, `build`, `run`, `package` — that
callers request without knowing which language or tool provides it.
_Avoid_: task, command, step, script

**Adapter**:
The per-language implementation of one capability.
_Avoid_: handler, driver, backend

**Result state**:
The outcome of one capability against one language: `pass`, `not-applicable`,
`unavailable`, or `FAIL`.
_Avoid_: status, skipped, n/a

**Bar**:
The destination's own `scripts/check` passing, measured on the candidate before
it is published. `FAIL` and `unavailable` both fail it; `not-applicable` does
not.
_Avoid_: gate, green, verification, passing checks

**Tool declaration**:
The entries in a repository's root manifest naming the tools its adapters run.
_Avoid_: dev dependencies, dev group, tooling config, npm scripts
