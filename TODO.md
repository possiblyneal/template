# TODO

Backlogged, informal tasks for this repository. Tasks for the template itself,
not for a project cloned from it.

## Backlog

- Name the candidate build directory in `repo-builder`. `references/lifecycle.md`
  says "an isolated local directory" and leaves the choice to the agent, which
  picks somewhere outside the repository and trips `ask-outside-repo.sh`. The
  repository already ships the answer: `tmp/` is inside `CLAUDE_PROJECT_DIR` and
  gitignored, in both this tree and the payload.
- Rewrite `~/.claude/skills/domain-modeling/ADR-FORMAT.md` to match the
  OKF-aligned template in
  `apps/github-repository-template/src/base-repo/docs/adr/0000-template.md`.
  (Global-skill task, parked here because this repo owns the template it
  should match.)
