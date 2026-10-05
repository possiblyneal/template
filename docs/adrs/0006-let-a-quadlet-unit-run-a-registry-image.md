---
type: Architecture Decision Record
title: Let a Quadlet Unit Run a Registry Image It Does Not Build
description: A unit declaring ships quadlet may hold only a .container whose Image is a fully qualified registry reference; a .build is required only for an image the deploy host itself must produce.
scope: [global]
tags: [build-and-release, deployment]
generated: { by: "agent/claude-opus-5-5", at: "2026-10-05T00:00:00Z" }
superseded_by:
status: accepted
---

# Let a Quadlet Unit Run a Registry Image It Does Not Build

## Decision

`scripts/package` accepts a `ships: quadlet` unit whose `deploy/quadlet/` holds a
`.container` and no `.build`, provided the `.container`'s `Image=` is a fully
qualified registry reference: the part before the first `/` carries a `.` or a `:`
and is not `localhost`. A `.build` that is present is validated as before, and an
image named `localhost/...` or by a bare name must still be produced by a `.build`
there.

This narrows one clause of `docs/adrs/0001-declare-unit-delivery-as-two-facts.md`,
which describes a quadlet unit as a `.build` and `.container` pair that systemd and
podman build on the deploy host. Everything else in that record stands.

## Context

`inference-runtime-broker`'s broker is delivered as a quadlet: a deploy script
installs `runtime-broker.container`, which runs
`ghcr.io/possiblyneal/inference-runtime-broker/runtime-broker:latest`, an image a
CI workflow builds and pushes. Retrofitting it under the template, `scripts/package`
refused the unit for having no `.build`, although the quadlet is exactly how the
unit reaches its machine. Declaring `ships: none` would have described the unit
inaccurately to every reader of `.unit.json`.

The check exists to catch a service that will not start on the deploy host because
the image it asks for is never produced. A registry reference cannot be checked
without network access, which the gate does not assume, and a local image named by
`localhost/` or a bare name still can, so the rule keeps the second and admits the
first.

## Alternatives Considered

- **Keep the pair mandatory and declare such units `ships: none`.** Rejected: the
  declaration would say the unit ships nothing when its quadlet is its delivery.
- **Accept any `Image=` when no `.build` is present.** Rejected: a `localhost/`
  image with no build is the mismatch the check was written to catch.
- **Resolve the registry reference.** Rejected: it needs network access and a
  container runtime, and the gate passes on a machine with neither.

## Consequences

`scripts/package` passes on a quadlet unit whose image is published elsewhere, and
says nothing about whether that image exists; the workflow that pushes it is what
answers that. A typo in a registry host passes packaging and fails at the deploy
host's pull.
