# Documentation

## Purpose

Durable knowledge about this repository: why decisions were made, what contracts span apps, what plans were approved, and what an agent would otherwise rediscover the hard way.

## Ownership

- `adrs/` — architectural decision records, one repo-wide numbered sequence; `adrs/index.md` is generated from their frontmatter and is never hand-edited
- `specs/` — contracts spanning apps, such as service-to-service APIs and shared schemas
- `plans/` — plans written in plan mode, pointed here by `plansDirectory` in `.openclaude/settings.json`
- `lessons.md` — repository-specific knowledge that prevents recurring mistakes

Specs for a single unit belong to that unit, under `apps/<name>/docs/specs/`, and change in the same commit as the code they describe.

## Local Contracts

**ADRs use one repo-wide numbered sequence**, so decisions stay discoverable without knowing which app to look in. `adrs/0000-template.md` is the template: copy it, replace every frontmatter line and placeholder, and number from `0001`. Never reuse a number across scopes. An app may keep its own `adrs/` once local decisions would drown the repo-wide ones; link it from here when that happens.

**An ADR explains why**, so an agent does not revert or fundamentally alter an established decision. Do not rewrite history in one — supersede it with a new record.

**`adrs/index.md` is derived, not written.** `scripts/adr-index` rebuilds it from each record's `title`, `status`, and `superseded_by`; a pre-commit hook runs on every commit and fails it when the file changed, so stage the regenerated index with the record that changed it. A hand edit does not survive the next run.

- Listed records are the files named `NNNN-…`, minus `0000-template.md`. Anything else in `adrs/` is left alone rather than listed.
- `superseded_by` must name a file that exists, written from the repository root or as a bare filename when the replacement sits in `adrs/`. That is the only thing the script rejects; nothing else validates frontmatter.
- The index is absent until a real record exists, so a fresh repository carries no file listing nothing.

**`plans/` is tracked**, unlike the `~/.openclaude/plans` default, so a plan arrives in the diff alongside the code it describes. That is the moment a human approves the plan before the work starts.

**`lessons.md` takes durable constraints only.** Not incident history, not generic advice, not facts already clear from the code. Lead with the required action, name the exact artifact or command, and link the authoritative source rather than duplicating it. The format is documented in the file.

## Work Guidance

`docs/` is product-owned in `.repo-template.json`, so a template update never overwrites anything here. `adrs/0000-template.md` arrived from the payload and stays as the reusable template; edits to the ADR *format* belong in the payload copy as well.

The repository's structural reasoning is not here — it lives in `apps/github-repository-template/docs/github_repository_structure.md`, because it documents the payload rather than this repository. Do not duplicate it.

## Verification

`scripts/adr-index` through pre-commit, covering `adrs/` only: the index matches the records, and each record's frontmatter is well-formed. `scripts/tests/adr-index-test` covers the script itself. Nothing checks the prose in any document here.

The closeout pass in `.openclaude/rules/documentation.md` is the check: re-check changed paths against the `CLAUDE.md` chain, update owning docs, refresh every affected Child Index, and remove stale text.
