# GitHub Repository Template

## Purpose

Owns the payload copied into every repository generated from this template, and the reference documentation explaining why the payload is shaped the way it is.

## Ownership

- `src/base-repo/` — the payload. Every file here is destined for other repositories.
- `docs/` — reference material about the payload. Not copied anywhere; read by whoever edits the payload.

The `repo-builder` skill reads `src/base-repo` at a specific commit. It never reads the working tree, so an uncommitted payload edit does not reach a generated repository.

## Local Contracts

- A file under `src/base-repo/` is not this repository's configuration. It is data. `src/base-repo/scripts/check` never runs here; the root `scripts/check` does.
- Payload changes and root changes are separate edits. When a change should apply to both, make it in both places in the same commit, so the two do not drift.
- `src/base-repo/apps/app-name/` is a deliberate placeholder. It is renamed during generation, not here.
- `src/base-repo/.env` is an intentionally empty tracked file that gives a generated repository somewhere to put local variables. Do not add content to it.
- Payload paths appear in the generated repository without the `src/base-repo/` prefix, so a reference written inside the payload must be relative to the generated root.

## Work Guidance

Editing under `src/` prompts for approval, per `.claude/settings.json`. Treat the prompt as the question "is this a payload change or a root change?"

A payload change ships to repositories that cannot be inspected from here. Prefer changes that fail loudly in a generated repository over changes that silently do nothing: the payload's own scripts distinguish `pass`, `not-applicable`, `unavailable`, and `FAIL` for exactly this reason.

## Verification

No checks run against the payload as source. The root `scripts/check` runs shellcheck and actionlint over these files through pre-commit, which is syntax-level only.

The payload's behavior is verified where it lands: by `src/base-repo/scripts/tests/*-test` once a repository is generated, and by the `repo-builder` evals under `.claude/skills/repo-builder/evals/`.

## Child Index

None. `src/base-repo/CLAUDE.md` is payload content addressed to a generated repository, not a child contract for this one.
