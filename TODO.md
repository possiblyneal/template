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

- **Point the agent at `tools/`.** The template `CLAUDE.md` carries the DocSync
  framework and no commands, so an agent reading it finds nothing naming
  `tools/scripts/check`, `fix`, or `doctor` and reaches for `npm run lint`
  instead. The scripts are only worth having if the thing doing the work knows
  they exist.
