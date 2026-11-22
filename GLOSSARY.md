# Template

This repository builds other repositories. These terms describe their structure, delivery, and checks.

## Language

### Structure

**Unit**:
The smallest piece delivered on its own, whether deployed, installed, published, or copied. Each unit occupies one folder under `apps/`.
_Avoid_: app, service, package, project, module

**Domain**:
A distinct business area within a unit with its own folder when it benefits from isolation. Domains are optional.
_Avoid_: subdomain, area, feature

**Scope holder**:
A repository root, unit, or domain that owns scoped folders. `apps/` itself is not a scope holder.
_Avoid_: container, parent, level

**Scoped folder**:
A folder whose contents belong to one scope, such as `libs/`, `tests/`, `scripts/`, `tools/`, `assets/`, `docs/`, or `deploy/`.
_Avoid_: shared folder, common folder

### Delivery

**Unit declaration**:
The `.unit.json` at a unit's root that states its run fact and ship fact.
_Avoid_: unit config, manifest, metadata

**Run fact**:
How a unit runs locally: `oneshot` exits on its own, `longlived` runs until stopped, and `none` means there is nothing to run.
_Avoid_: shape, type, mode, dev command

**Entry point**:
A program the unit can start, named in its language manifest rather than `.unit.json`. Select it with `scripts/run --entry`.
_Avoid_: target, command, service, binary

**Ship fact**:
What a unit intends to deliver: `executable`, `quadlet`, or `none`. The language adapter determines the concrete form.
_Avoid_: artifact type, output, build target

**Target**:
A platform an executable is built for. Language adapters translate the template's target names: `linux-amd64` and `macos-arm64`.
_Avoid_: platform, arch, triple, GOOS

**Web language**:
Node, the template's choice for units that serve or render. A Node unit that exits is a script or job; CLIs here use Go, Rust, or Python.
_Avoid_: frontend stack, JS, TS, JavaScript

**Shape**:
Not a unit classification: use the run fact and ship fact separately because they vary independently. See ADR 0001 for the rationale.
_Avoid_: shape, kind, app type

### Template

**Payload**:
The content copied into generated repositories. Editing it changes future generated repositories, not this checkout.
_Avoid_: template files, source, boilerplate

**Addon**:
A file held back from the payload for a generated repository to adopt when it needs it.
_Avoid_: optional file, extra

**Addition by occasion**:
The rule that an addon arrives when the repository has a reason for it, not at generation.
_Avoid_: optional, as-needed

**Template Contract**:
The Commands and Layout rules opening a generated repository's root `CLAUDE.md`. They are identical across generated repositories and change only through the template.
_Avoid_: template rules, shared instructions

### Flows

**Flow**:
A route the payload takes into a repository: `generate`, `update`, `adopt`, or `retrofit`.
_Avoid_: mode, command, operation, run

**Destination**:
The repository a flow acts on, distinct from both this template repository and the candidate.
_Avoid_: target, output repo, the repo

**Retrofit**:
Landing the payload in an existing repository that has its own content and no template record.
_Avoid_: convert, migrate, onboard, adopt, backfill

**Overridden path**:
A payload path a flow leaves out because it keeps the destination's version instead.
_Avoid_: skipped file, collision, exception

**Superseded path**:
A destination path the flow removes because the payload now fulfills its role. An override keeps the destination version; supersession removes it.
_Avoid_: replaced file, deleted file, clobbered

**Departure**:
A deliberate difference from a template default, recorded by the destination in `generation.features`, such as an omitted file or a tracker other than GitHub Issues. If unrecorded, the default holds.
_Avoid_: override, exception, customization

**Retired**:
A superseded gate script is retired when it is deleted and its callers switch to the equivalent payload command, preserving behavior.
_Avoid_: removed, dropped, deprecated

**Candidate**:
The destination's working copy, built and measured before publication. The pull request asks to change the destination, not the candidate.
_Avoid_: working copy, staging repo, draft, workspace

**Resume record**:
The record beside the candidate of a stopped flow's decisions and writes it cannot verify by reading the destination back.
_Avoid_: journal, checkpoint, state file, progress file

**Unobservable write**:
A write the flow cannot recognize as its own by reading the destination. Retrying it creates a duplicate.
_Avoid_: keyless write, non-idempotent write

**Hosted write**:
A change to the destination's GitHub state that a pull request cannot carry.
_Avoid_: remote write, settings change, API call

**Authored surface**:
The parts a flow wrote in the candidate and that require line-by-line review. Exclude proven identical copies and unchanged moves, and files the destination's linter or formatter rewrote during retrofit autofix.
_Avoid_: custom content, hand-written files, non-template files, the diff

### Checks

**Capability**:
A named check or action, such as `lint`, `test`, `build`, `run`, or `package`, that callers request independently of language or tool.
_Avoid_: task, command, step, script

**Adapter**:
The per-language implementation of one capability.
_Avoid_: handler, driver, backend

**Integration tier**:
Tests under `tests/integration/` at any scope holder. `scripts/integration` runs them outside the `test` capability and the gate.
_Avoid_: e2e, functional tests, slow tests, acceptance tests

**Result state**:
The outcome of one capability for one language: `pass`, `not-applicable`, `unavailable`, or `FAIL`.
_Avoid_: status, skipped, n/a

**Bar**:
A passing run of the destination's own `scripts/check` on the candidate before publication. `FAIL` and `unavailable` fail the bar; `not-applicable` does not.
_Avoid_: gate, green, verification, passing checks

**Tool declaration**:
The root manifest entries naming the tools the repository's adapters run.
_Avoid_: dev dependencies, dev group, tooling config, npm scripts

**Configuration boundary**:
A section in the repository's own manifest that keeps a tool from reading settings above the repository. The tool declaration writes it using tool defaults where the repository sets no preference.
_Avoid_: anchor, config root, settings file, pin
