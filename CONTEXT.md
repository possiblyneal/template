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
The file at a unit's root stating how that unit runs and what it ships.
Required of every unit; its absence is a structure failure, not a default.
_Avoid_: unit config, manifest, metadata

**Run fact**:
How a unit is invoked locally — as a process that exits on its own, as one that
runs until stopped, or not at all.
_Avoid_: shape, type, mode, dev command

**Ship fact**:
What a unit delivers, named as intent rather than as a file format, so the
language adapter decides the concrete form.
_Avoid_: artifact type, output, build target

**Target**:
A platform an executable is built for, written in a neutral vocabulary the
template owns and each language adapter translates.
_Avoid_: platform, arch, triple, GOOS

**Shape**:
Deliberately not a term here. A single word naming what a unit "is" collapses
two independent facts — how it runs and what it ships — that vary separately.
_Avoid_: shape, kind, app type

### Checks

**Capability**:
A named check or action — `lint`, `test`, `build`, `run`, `package` — that
callers request without knowing which language or tool provides it.
_Avoid_: task, command, step, script

**Adapter**:
The per-language implementation of one capability.
_Avoid_: handler, driver, backend

**Result state**:
The outcome of a capability: `pass`, `not-applicable`, `unavailable`, or `FAIL`.
A check that did not run is never one that passed.
_Avoid_: status, skipped, n/a

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
