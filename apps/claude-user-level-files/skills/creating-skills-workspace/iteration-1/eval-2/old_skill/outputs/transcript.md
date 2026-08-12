# Transcript Summary

Task: Build out a skill for generating database migration scripts that handles schema diffs, rollbacks, and dry runs.

Skill source used: `/home/neal/.claude/skills/creating-skills-workspace/skill-snapshot`

## Stopping point

Stopped at the Evaluation-Driven Development decision gate, before writing any `SKILL.md` body content.

## Interview state before the EDD gate

The task description was specific enough to form an initial interview-complete summary without further drafting:

```text
Interview complete
1. What should this skill enable Claude to do?
   Help Claude generate safe database migration scripts from schema differences, including forward migrations, rollback/down migrations, and dry-run/preview workflows.
2. When should it trigger, and when should it not?
   Trigger when the user asks to create, review, or plan database migration scripts; compare desired/current schemas; add rollback support; or perform dry-run migration planning. Do not trigger for generic SQL query writing, ORM usage questions unrelated to migrations, or production database execution without an explicit migration task.
3. What's the expected output format?
   A concise migration plan plus migration script(s), rollback script(s), dry-run instructions, verification checks, and safety notes. If editing a repo, output should follow that repo's migration framework and file layout.
4. Should we set up evals?
   Yes. Migration output has objectively checkable safety and completeness requirements: schema diff identification, reversible rollback, dry-run command/transaction guidance, and refusal to run destructive changes without explicit confirmation.
```

## EDD decision before drafting SKILL.md body

Posted an EDD decision summary before drafting any `SKILL.md` body content: yes.

Exact EDD decision text:

```text
EDD decision

evals_in_scope: yes

Rationale: Database migration generation is low-freedom and safety-critical. The skill should improve behavior on objectively verifiable requirements: identifying schema diffs before writing migrations, producing reversible rollback/down migrations, including dry-run/preview steps, flagging destructive operations, and avoiding live database execution without explicit confirmation. Baseline runs are likely to produce plausible migration scripts but omit framework-specific verification, rollback completeness, or dry-run safety steps, so evals should be created before writing the skill body.

Initial eval prompts:
1. "Create a migration for a PostgreSQL app that changes users.email from nullable to NOT NULL, adds a unique index, and must include a rollback and dry-run plan. Assume existing null/duplicate data may exist."
2. "Given this current schema and desired schema for an orders table, generate forward and rollback migrations using Alembic. Include how to preview SQL without applying it."
3. "Review this proposed Prisma migration that drops a column and renames another. Identify whether the rollback is safe, produce a safer migration plan, and include dry-run verification steps."
```

## Whether SKILL.md sections were written before the EDD decision

No `SKILL.md` sections were written before the EDD decision. No frontmatter, overview, procedure, examples, or body sections were drafted or saved as part of this run.

## Interpretation of "before writing any SKILL.md body content"

I interpreted "before writing any SKILL.md body content" to mean: stop before composing or saving any Markdown instructions that would appear after the YAML frontmatter in `SKILL.md`, including headings such as Overview, Workflow, Safety Rules, Examples, Common Mistakes, or References. I also avoided creating a `SKILL.md` file at all, because even frontmatter plus placeholders could blur the gate. Under this interpretation, it is acceptable to decide the skill scope, summarize the interview, search existing skill instructions, and post the EDD decision; it is not acceptable to draft the actual skill instructions.

## What I would do next after the gate, but did not do

1. Search existing skills for migration-related overlap.
2. Create baseline eval scenarios without the new skill.
3. Save eval prompts and metadata.
4. Only then draft the minimum `SKILL.md` body needed to improve the baseline failures.
