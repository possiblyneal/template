# TODO

Backlogged, informal tasks for this repository. Tasks for the template itself,
not for a project cloned from it.

## Backlog

- Name the candidate build directory in `repo-builder`. `references/lifecycle.md`
  says "an isolated local directory" and leaves the choice to the agent, which
  picks somewhere outside the repository and trips `ask-outside-repo.sh`. The
  repository already ships the answer: `tmp/` is inside `CLAUDE_PROJECT_DIR` and
  gitignored, in both this tree and the payload.
- Rewrite `~/.openclaude/skills/domain-modeling/ADR-FORMAT.md` to match the
  OKF-aligned template in
  `apps/github-repository-template/src/base-repo/docs/adrs/0000-template.md`.
  (Global-skill task, parked here because this repo owns the template it
  should match.)
- Add a standalone addon-adoption flow to `repo-builder`. Today addons are
  offered only during `generate` (`references/lifecycle.md` step 2); a
  repository already carrying `.repo-template.json` has no supported way to
  adopt a held-back addon after the fact. Needs an operation in `SKILL.md`
  beside generate/update, a lifecycle flow that reads the addon from the
  recorded template commit and lands it as a PR, and a decision on whether
  `preflight.py` gains an `adopt` subcommand or reuses the agent's own
  validation. Depends on the walkthrough first being factored out of
  generate step 2 so both flows share it.
