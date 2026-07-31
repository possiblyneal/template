# TODO

Backlogged, informal tasks for this repository. Tasks for the template itself,
not for a project cloned from it.

## Backlog

- **Decide whether `.claude/settings.json` should ship as empty scaffolding.**
  Every key in it is an empty default (`permissions.allow: []`, `hooks: {}`,
  `sandbox: {}`), so the file changes no behavior and only names the keys that
  exist, which `docs/github-repository-structure.md` already does. Either fill
  it with settings the template actually wants, or drop it and let Claude Code
  write the file when a real setting is first set. Left alone for now because
  an empty file is a harmless discovery aid, unlike the entries it lists.

- **Untrack `.env` and ship `.env.example` instead.** `.gitignore` ignores
  `.env` on line 2, but the file is tracked, and tracking overrides the ignore
  rule. A clone therefore starts with a git-tracked `.env`, so the first
  `git add -A` after a real secret is written commits it, which is the case
  that rule exists to prevent. History is clean: only placeholder values were
  ever committed. This also revives two dead rules, since `.gitignore` negates
  for an `.env.example` that does not exist, and `.worktreeinclude` copies only
  gitignored files, so its `.env` entry never fires while the file is tracked.

- **Point the agent at `tools/`.** The template `CLAUDE.md` carries the DocSync
  framework and no commands, so an agent reading it finds nothing naming
  `tools/scripts/check`, `fix`, or `doctor` and reaches for `npm run lint`
  instead. The scripts are only worth having if the thing doing the work knows
  they exist.

- **Upgrade the pinned audit tools when a release lands.** `govulncheck` and
  `cargo-audit` are pinned by version in `.github/workflows/security.yml`.
  Dependabot reads no version from a `run` step, so nothing opens a pull
  request for either and they age until someone checks.
