# Documentation Framework

Rules to keep core contract

- `AGENTS.md` files are binding work contracts for their subtrees
- `AGENTS.md` files are aligned with repo structure, workflows, and durable conventions.
- Work products, source materials, instructions, records, assets, and durable docs must stay understandable from the nearest applicable `AGENTS.md` plus every t `AGENTS.md` above it
- Agent must follow these instructions across all edits and writes

## Read Before Editing

1. Read the root `AGENTS.md`
2. Identify every file or folder you expect to touch
3. Walk from the repository root to each target path
4. Read every `AGENTS.md` found along each route
5. If a parent `AGENTS.md` lists a child `AGENTS.md` whose scope contains the path, read that child and continue from there
6. Use the nearest `AGENTS.md` as the local contract and parent docs for repo-wide rules
7. If docs conflict, the closer doc controls local work details, but no child doc may weaken the system

Do not rely on memory. Re-read the applicable `AGENTS.md` chain in the current session before editing.

## Update After Editing

Every meaningful change requires a documentation pass before the task is done. A meaningful change is one that changes durable behavior, structure, workflow, ownership, commands, interfaces, or conventions.

Update the closest owning `AGENTS.md` when a change affects:

- purpose, scope, ownership, or responsibilities
- durable structure, contracts, workflows, or operating rules
- required inputs, outputs, permissions, constraints, side effects, or artifacts
- durable user preferences that should affect future work in this repo
- `AGENTS.md` creation, deletion, move, rename, or index contents

Update parent docs when parent-level structure, ownership, workflow, or child index changes. Update child docs when parent changes alter local rules. Remove stale or contradictory text immediately. Small edits that do not change behavior or contracts may leave docs unchanged, but the document pass still must happen.

## Hierarchy

- Root `AGENTS.md` Answers the question, "How should an unfamiliar coding agent make a correct, minimal, verifiable change without introducing bugs? Typically carries project-wide instructions, global preferences, durable workflow rules, and the top-level Child Index
- Child `AGENTS.md` files own domain-specific instructions and their own Child Index
- Each parent explains what its direct children cover and what stays owned by the parent
- The closer a doc is to the work, the more specific and practical it must be

## Child AGENTS.md Shape

- Create a child `AGENTS.md` when a folder becomes a durable boundary with its own purpose, ownership, rules, responsibilities, workflow, materials, or quality standards
- Create a `CLAUDE.md` beside it in the same commit, containing exactly `@AGENTS.md` and nothing else. Claude Code loads `CLAUDE.md` and never loads `AGENTS.md`, so the shim is the only thing that loads the contract when work happens inside that folder. Move, rename, or delete the pair together; a stranded `AGENTS.md` is a contract that silently does not load
- The root pair is exempt where the repository gitignores its root `CLAUDE.md`, as a generated repository does: that shim arrives through the working tree rather than history, so a fresh clone loads the root contract only once someone supplies it. The exemption stops at the root — every nested shim is committed
- Work Guidance must reflect the current standards of the project or user instructions; if there are no specific standards or instructions yet, leave it empty
- Verification must reflect an existing check; if no verification framework exists yet, leave it empty and update it when one exists

Default section order:

- Purpose
- Ownership
- Local Contracts
- Work Guidance
- Verification
- Child Index

**Note:** Root `AGENTS.md` is exempt from the child document shape. It may evolve as the project-wide documentation contract changes, but it must remain concise and operational.

## Style

- Keep docs concise, current, and operational
- Document stable contracts, not diary entries
- Put broad rules in parent docs and concrete details in child docs
- Prefer direct bullets with explicit names
- Do not duplicate rules across many files unless each scope needs a local version
- Delete stale notes instead of explaining history
- Trim obvious statements, repeated rules, misplaced detail, and warnings for risks that no longer exist

## Delegation

- Built-in Explore and Plan subagents do not load `AGENTS.md`. When delegating to them, restate the documentation obligations that apply to the delegated work in the prompt, or use a custom subagent, which does load `AGENTS.md`.

## Closeout

1. Re-check changed paths against the chain of `AGENTS.md` files
2. Update nearest owning docs and any affected parents or children
3. Refresh every affected Child Index
4. Confirm every `AGENTS.md` you added, moved, or renamed has its `CLAUDE.md` shim beside it, and that deleting one took its shim with it
5. Remove stale or contradictory text
6. Run existing verification when relevant
7. Report any docs intentionally left unchanged and why

## User Preferences

When the user requests a durable behavior change, record it in the relevant `AGENTS.md`

## Continuous improvement

When you discover a recurring repo-specific mistake, stale doc, missing command, missing script, or missing convention that would help future agents, propose a minimal update to the closest `AGENTS.md` Do not add broad rules from one-off incidents.

## Lessons Learned

For critical lessons learned regarding this repo, refer to docs/LESSONS.md. This file contains the "hard-won" knowledge required to avoid common repo-specific pitfalls.
