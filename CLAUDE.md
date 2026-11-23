## Mission

This repository builds repositories for AI agents first and people second.

Every repository generated from it shares one shape: the same folders, the same commands, the same checks, and the same kinds of docs in the same places. What is shared is that each file exists and
where it sits, not what it says. The program and its files differ from one repository to the next, and so do the contents of the files that describe it: every repository has a `CLAUDE.md`, but each
holds that repository's own contract.

So does local configuration: every repository has a `.env`, and some fill it. An addon is part of the shape too: a repository adopts it only when it has a reason to, but once adopted it sits where it
sits everywhere else. An agent that has learned one repository has learned the rest, so it spends its context on the task instead of on finding its way around.

Judge every structural decision by four questions:

1. **Is it the same everywhere?** If a repository needs its structure to differ, that's a gap in the template. Fix it here so every repository gets the fix, rather than letting one repository drift on
   its own.
2. **Can an agent find it without searching?** A file's location should follow from what the file is, so the path can be predicted before anything is opened.
3. **Does it cost fewer tokens to understand?** The nearest `CLAUDE.md`, the glossary, and one command per job should answer what would otherwise take a sweep of the tree.
4. **Is the work as good or better?** Saving tokens never justifies a worse result. If a shortcut makes the agent's output worse, it doesn't belong here.

When something is easy for an agent to navigate, a person can usually navigate it too. Where the two needs conflict, the agent's needs win.

## What this repository is

Choose the tree by who needs the change:

- **This checkout:** Edit the live configuration under `scripts/`, `.github/`, `.claude/`, or the root dotfiles.
- **Generated repositories:** Edit `apps/github-repository-template/src/base-repo/`. Read `apps/github-repository-template/docs/github_repository_structure.md` before changing what ships.
- **Shared behavior:** Edit both copies. `scripts/payload-parity` checks `.github/` and `scripts/`; see the template app contract for intentional differences.

In `.repo-template.json`, keep this file managed so template updates reconcile it. Keep `apps/**` product-owned so updates cannot overwrite the payload.

## Commands

Use the repository scripts instead of per-language tools. When changing a command or layout rule, keep the payload's Template Contract in step with this section and Layout below.

| Task | Command and decision |
|---|---|
| Check prerequisites | Run `scripts/doctor` for local tools, dependencies, hooks, and configuration. It does not inspect GitHub. |
| Verify a change | Run `scripts/check --fast` before committing. Run `scripts/check` instead when the change could break the build; `--fast` skips only the build. |
| Diagnose a slow or failing gate | Read the Result table and elapsed wall times. For the full run, read `tmp/check.log` or use `scripts/check --verbose`. First-time hook setup and `commitlint-test` may need the network. |
| Read CI or another check | Use `scripts/summarize <command…>` for findings and exit status. `scripts/check` already summarizes its output. |
| Apply automatic fixes | Run `scripts/fix` for lint autofix followed by formatting. A remaining `lint-fix` failure needs a hand edit. |
| Check layout | Run `scripts/structure` for file placement and unit declarations. Judge content scope separately. |
| Check mirrored files | Run `scripts/payload-parity`. It reports rather than repairs; some findings include a mirror command when staged changes establish the direction. |
| Run a program | Use `scripts/run [unit] [--entry <name>] [-- args…]`. Name the unit or entry when there is more than one; take the entry name from its language manifest. |
| Run integration tests | Run `scripts/integration` for `tests/integration/` at any scope. The gate excludes this tier because it may need external services. |
| Package a unit | Run `scripts/package [unit]` outside the gate. Executable packaging empties the unit's `dist/` before writing targets; Quadlet packaging validates `deploy/quadlet/`. |
| Remove build output | Run `scripts/clean` to recursively delete build output and tool caches. |
| Check hosted settings | Run `scripts/repo-settings check` explicitly with network access and administration visibility. The local gate does not check hosted state. |

Only `pass` means a check ran successfully. Distinguish `not-applicable` (nothing to run) from `unavailable` (a required runner is missing) and `FAIL` (the check failed).

Keep the root `pyproject.toml` out of the payload: it declares this checkout's `apps/repo-builder/` Python unit.
Scope pytest discovery to that unit, leave Ruff and ty unnarrowed, and exclude Markdown from formatting so `scripts/fix` cannot rewrite fenced Python in the payload or frozen plans.

## Git

- **Branch first.** Pre-commit blocks commits to `main` and `master`. Use `.github/PULL_REQUEST_TEMPLATE.md` for work entering `main`.
- **Explain the change.** Use `type(optional scope): subject` with a lowercase subject, no trailing period, and a body explaining why. For a hand-written merge, use `Merge <what> into <branch>`.
- **Attribute the commit.** Use `Generated-By: <model ID>` rather than a model co-author. Preserve human co-authors. If `scripts/attribute-commit` cannot infer the ID, supply the trailer yourself.
- **Judge changelogs per pull request.** Features, fixes, and breaking changes usually warrant an entry where a changelog exists. Validation checks changed entries, not missing ones.
  This checkout ships the changelog addon but keeps no root changelog.
- **Track plans** in `docs/plans/` so the plan lands with its code.

For permission prompts, check `.claude/settings.json`, built-in protected paths, and the operator's `ask` rules. A repository edit allowance does not override the latter two.

## Layout

`CLAUDE.md` files have no repository-enforced length or size limit.

Choose the narrowest scope that owns the behavior: repository root, unit, or domain. Root `libs/` and `tests/` must span units; work specific to one unit belongs under that unit.

### Units and domains

- Put each independently delivered unit in `apps/<unit>/`. Nothing sits directly in `apps/` except unit directories; even `apps/docs/` names a unit.
- Put code in the unit's `src/`, or split distinct business areas into `apps/<unit>/<domain>/src/`. Do not combine the two layouts or nest domains.
- Declare each unit in its own `.unit.json`, never at domain scope. Read `docs/adrs/0001-declare-unit-delivery-as-two-facts.md` before changing the declaration.

| Field | Allowed values |
|---|---|
| `schema_version` | Use `1`. |
| `run` | Choose `oneshot`, `longlived`, or `none`. |
| `ships.kind` | Choose `executable`, `quadlet`, or `none` independently of `run`. |
| `ships.targets` | Specify targets only for `executable`, where they are required. Supported targets are `linux-amd64` and `macos-arm64`. |

Include each language's packages in its root workspace manifest. Swift has no root manifest; a `CMakeLists.txt` below `src/` or beside another language's manifest belongs to that native build.

### File placement

| What belongs together | Where it goes |
|---|---|
| Shared code and tests | Use `libs/` and `tests/` at the owning scope. Use `tests/integration/` for the separately run integration tier. |
| Shell scripts and built helpers | Use `scripts/` for portable shell regardless of caller. Use `tools/` for helpers built before use, one directory per program with its own manifest. |
| Settings and deployment | Put defaults in `config/` and environment overrides in `deploy/env/`. Other deployment files go under `deploy/{quadlet,containerfile,compose,systemd}/`, never loose in `deploy/`. |
| Data and runtime state | Track read-only data in `assets/`. Put files the program writes in gitignored `apps/<unit>/state/`. To seed a fresh clone, track the finished snapshot as an asset, not the working copy. |
| Examples and dependencies | Use `examples/` for runnable demonstrations without assertions and `vendor/` for verbatim third-party code. A dependency you patch belongs in `libs/`. |
| Documentation and scratch | Put Markdown in `docs/` at its owning scope. Other formats there need explicit permission. Use root `tmp/` for gitignored scratch. |
| Repository infrastructure | Use `.claude/` for agent configuration, `.github/` for hosted automation, and `.devcontainer/` when adopting a dev container. |

Scoped folders may nest but cannot introduce a `src/`. Depth rules stop at the first `src/`, `examples/`, `vendor/`, or recognized toolchain folder; the language or tool owns the layout below it.
Vendored code skips lint, formatting, and tests, but still undergoes secret, size, and merge-conflict checks.

Prefer the standard layout over an exception:

- Use `scripts/structure` for the exact root allowlists. Root files are admitted by name; `.gitkeep` is permitted anywhere.
- For a required toolchain directory, add the folder and its companion file to `toolchain_folders` in `scripts/structure` rather than granting each repository an exception.
  If the directory can be relocated, place it in the standard layout instead.
- In `.structure-allow`, name one file by exact path. Reserve a trailing `/` for a tracked fixture tree; the audit still checks that a domain has its own `src/`.

## Repository settings

Use `scripts/repo-settings check` for current hosted state.
For changes to the generated branch policy, inspect `apps/github-repository-template/src/ruleset.json`.

- Land on `main` through a pull request with a true merge commit. The required checks are `CI`, `Security`, and `Code scanning enabled`, not individual language-matrix jobs.
- Use the `code-reviewed` label and its `Reviewed-Head:` comment for solo review. Use `/land` when the base moved: it runs the full local gate; the GitHub merge button does not.
- Keep automatic head branch deletion enabled. A local hook cannot enforce this hosted setting.
- Distinguish CodeQL success from scan coverage: only an `analyze` job that ran means code was scanned. On private repositories, distinguish an unavailable plan feature from a disabled protection.

## Agent skills

Use the GitHub Issues, `gh`, and label defaults in `/wayfinder`, `/triage`, and `/ship`. Record departures in `.repo-template.json` under `generation.features`, rather than copying defaults here.

## Child Index

Read the applicable `CLAUDE.md` chain before editing. After a meaningful change, update the contract that owns the changed behavior.

- Read `apps/github-repository-template/CLAUDE.md` before changing what ships or the reference docs that describe it.
- Read `apps/repo-builder/CLAUDE.md` before changing the `/repo-builder` skill or the tracked link that exposes it.
- Read `scripts/CLAUDE.md` before adding a language or changing a repository check.
- Read `docs/CLAUDE.md` before writing an ADR, spec, plan, research record, or language ranking.
