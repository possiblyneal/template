# Documentation

## Purpose

Durable knowledge about this repository: why decisions were made, what contracts span apps, what plans were approved, and what an agent would otherwise rediscover the hard way.

## Ownership

- `adr/` — architectural decision records, one repo-wide numbered sequence
- `specs/` — contracts spanning apps, such as service-to-service APIs and shared schemas
- `plans/` — plans written in plan mode, pointed here by `plansDirectory` in `.claude/settings.json`
- `lessons.md` — repository-specific knowledge that prevents recurring mistakes

Specs for a single unit belong to that unit, under `apps/<name>/docs/specs/`, and change in the same commit as the code they describe.

## Local Contracts

**ADRs use one repo-wide numbered sequence**, so decisions stay discoverable without knowing which app to look in. `adr/0000-template.md` is the template: copy it, replace every frontmatter line and placeholder, and number from `0001`. Never reuse a number across scopes. An app may keep its own `adr/` once local decisions would drown the repo-wide ones; link it from here when that happens.

**An ADR explains why**, so an agent does not revert or fundamentally alter an established decision. Do not rewrite history in one — supersede it with a new record.

**`plans/` is tracked**, unlike the `~/.claude/plans` default, so a plan arrives in the diff alongside the code it describes. That is the moment a human approves the plan before the work starts.

**`lessons.md` takes durable constraints only.** Not incident history, not generic advice, not facts already clear from the code. Lead with the required action, name the exact artifact or command, and link the authoritative source rather than duplicating it. The format is documented in the file.

## Work Guidance

`docs/` is product-owned in `.repo-template.json`, so a template update never overwrites anything here. `adr/0000-template.md` arrived from the payload and stays as the reusable template; edits to the ADR *format* belong in the payload copy as well.

The repository's structural reasoning is not here — it lives in `apps/github-repository-template/docs/github_repository_structure.md`, because it documents the payload rather than this repository. Do not duplicate it.

## Verification

None. Documentation correctness is not machine-checkable here; pre-commit enforces only formatting and line endings.

The closeout pass in `.claude/rules/documentation.md` is the check: re-check changed paths against the `CLAUDE.md` chain, update owning docs, refresh every affected Child Index, and remove stale text.
