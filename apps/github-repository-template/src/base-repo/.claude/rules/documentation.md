# Documentation Framework

Rules to keep core contract

- `CLAUDE.md` files are binding work contracts for their subtrees
- `CLAUDE.md` files are aligned with repo structure, workflows, and durable conventions.
- Work products, source materials, instructions, records, assets, and durable docs must stay understandable from the nearest applicable `CLAUDE.md` plus every t `CLAUDE.md` above it
- Agent must follow these instructions across all edits and writes

## Read Before Editing

1. Read the root `CLAUDE.md`
2. Identify every file or folder you expect to touch
3. Walk from the repository root to each target path
4. Read every `CLAUDE.md` found along each route
5. If a parent `CLAUDE.md` lists a child `CLAUDE.md` whose scope contains the path, read that child and continue from there
6. Use the nearest `CLAUDE.md` as the local contract and parent docs for repo-wide rules
7. If docs conflict, the closer doc controls local work details, but no child doc may weaken the system

Do not rely on memory. Re-read the applicable `CLAUDE.md` chain in the current session before editing.

## Update After Editing

Every meaningful change requires a documentation pass before the task is done. A meaningful change is one that changes durable behavior, structure, workflow, ownership, commands, interfaces, or conventions.

Update the closest owning `CLAUDE.md` when a change affects:

- purpose, scope, ownership, or responsibilities
- durable structure, contracts, workflows, or operating rules
- required inputs, outputs, permissions, constraints, side effects, or artifacts
- durable user preferences that should affect future work in this repo
- `CLAUDE.md` creation, deletion, move, rename, or index contents

Update parent docs when parent-level structure, ownership, workflow, or child index changes. Update child docs when parent changes alter local rules. Remove stale or contradictory text immediately. Small edits that do not change behavior or contracts may leave docs unchanged, but the document pass still must happen.

## Hierarchy

- Root `CLAUDE.md` Answers the question, "How should an unfamiliar coding agent make a correct, minimal, verifiable change without introducing bugs? Typically carries project-wide instructions, global preferences, durable workflow rules, and the top-level Child Index
- Child `CLAUDE.md` files own domain-specific instructions and their own Child Index
- Each parent explains what its direct children cover and what stays owned by the parent
- The closer a doc is to the work, the more specific and practical it must be

## Child CLAUDE.md Shape

- Create a child `CLAUDE.md` when a folder becomes a durable boundary with its own purpose, ownership, rules, responsibilities, workflow, materials, or quality standards
- Work Guidance must reflect the current standards of the project or user instructions; if there are no specific standards or instructions yet, leave it empty
- Verification must reflect an existing check; if no verification framework exists yet, leave it empty and update it when one exists

Default section order:

- Purpose
- Ownership
- Local Contracts
- Work Guidance
- Verification
- Child Index

**Note:** Root `CLAUDE.md` is exempt from the child document shape. It may evolve as the project-wide documentation contract changes, but it must remain concise and operational.

## Style

- Keep docs concise, current, and operational
- Document stable contracts, not diary entries
- Put broad rules in parent docs and concrete details in child docs
- Prefer direct bullets with explicit names
- Do not duplicate rules across many files unless each scope needs a local version
- Delete stale notes instead of explaining history
- Trim obvious statements, repeated rules, misplaced detail, and warnings for risks that no longer exist

## Delegation

- Built-in Explore and Plan subagents do not load `CLAUDE.md`. When delegating to them, restate the documentation obligations that apply to the delegated work in the prompt, or use a custom subagent, which does load `CLAUDE.md`.

## Closeout

1. Re-check changed paths against the chain of `CLAUDE.md` files
2. Update nearest owning docs and any affected parents or children
3. Refresh every affected Child Index
4. Remove stale or contradictory text
5. Run existing verification when relevant
6. Report any docs intentionally left unchanged and why

## User Preferences

When the user requests a durable behavior change, record it in the relevant `CLAUDE.md`

## Continuous improvement

When you discover a recurring repo-specific mistake, stale doc, missing command, missing script, or missing convention that would help future agents, propose a minimal update to the closest `CLAUDE.md` Do not add broad rules from one-off incidents.

## Lessons Learned

For critical lessons learned regarding this repo, refer to docs/lessons.md. This file contains the "hard-won" knowledge required to avoid common provider-specific pitfalls.
