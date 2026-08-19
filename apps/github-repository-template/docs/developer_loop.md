**1. Sync & Pick - loop start**

- **1a.** Agent confirms its current worktree is clean and fetches `origin/main`.
- **1b.** Agent chooses the next ticket.
- **1c.** Agent creates a fresh feature worktree and branch from `origin/main` (for example, `git worktree add -b feat/ticket-123 <path> origin/main`).

**2. Plan / Breakdown / Context**

- **2a.** Planning agent reads the acceptance criteria to define the target end-state.
- **2b.** Agent decomposes the task into strictly 2-3 logical blocks that require minimal file traversal.
  - *Constraint:* If a task exceeds this scope, the agent must kick it back to the backlog as an epic or halt execution to request a manual breakdown from you.
- **2c.** Agent maps out edge cases and defines the necessary test coverage.
- **2d.** Agent performs a workspace search to ingest specific files, polyglot architectural constraints, and relevant docs to build a tightly scoped context window.

**3. Coding loop [repeats 10-20x per ticket]**

- **3a.** Coding agent writes a targeted chunk of code and the corresponding test.
- **3b.** Agent executes local tests AND performs programmatic "manual" verification using terminal tools (e.g., executing `curl` against local endpoints, running headless scripts, or querying local databases to verify state).
- **3c.** If red, the test output and error logs are piped directly back into the agent's prompt for immediate remediation.
  - *Circuit Breaker:* If the agent fails to clear a test or verification step after 3 attempts, it halts execution, preserves the feature branch and any reviewable WIP commit, and pings you with the failing command, logs, attempt count, and decision needed for a tie-breaker.
- **3d.** Agent refactors the chunk to align with the repository's architecture.
- **3e.** Agent repeats 3a-3d autonomously until the sub-task is complete.

**4. Full Verify - once per chunk**

- **4a.** Agent triggers the unified verification script to automatically format, lint, and typecheck across the stack.
- **4b.** Agent runs the full test suite and build.
- **4c.** Agent analyzes the diff to ensure no dead code, junk, or secrets are present.
- **4d.** Agent updates the relevant documentation.

**5. Commit + Lint commit (Agent Executed)**

- **5a.** Agent utilizes patch-level staging (the programmatic equivalent of `git add -p`), evaluating every single hunk against the "one logical idea" rule before staging.
- **5b.** Agent generates standard commit messages (`type(scope): description` + WHY + `Closes #123`).
- **5c.** Pre-commit hooks run commitlint. If it fails, the agent intercepts the error and amends the commit automatically.

**6. Changelog - before push (Agent Executed) (skip if no `CHANGELOG.md` in project root)**

- **6a.** Agent determines if the changes are notable to the user
- **6b.** Agent categorizes the change: Added / Changed / Fixed / Deprecated / Removed / Security.
- **6c.** Agent synthesizes a curated, human-readable entry specifically under `## [Unreleased]`.
- **6d.** Agent commits the changelog update.

**7. Push / PR / Merge / Cleanup - then loop back to 1 (Agent & Human Executed)**

- **7a.** Agent rebases against origin `main` and pushes the branch.
- **7b.** Agent opens the PR via API, filling out the PR template and linking the issue.
- **7c.** CI pipeline runs. If red, a webhook triggers the coding agent to ingest the CI logs, fix the issue, and push a new commit.
  - *Circuit Breaker:* Agent halts and alerts you after 3 failed CI fix attempts.
- **7d. The Adversarial AI Review:** A distinct, high-parameter local model acts as a hostile reviewer, critiquing the PR for logical regressions and edge cases. The primary agent ingests the feedback, fixes, and pushes.
  - *Circuit Breaker:* If the adversarial model does not issue a formal approval after 3 iteration loops, the process halts and escalates to you.
- **7e. Human Review & Merge (Your Step):** You review the final PR, the adversarial AI's sign-off, and the proposed code. You make the final decision to approve and merge.
- **7f.** Post-merge webhook triggers branch deletion and syncs `main`.
- **7g.** Agent moves the ticket to Done and loops back to Step 1 to pick the next ticket.
