# GitHub Repository Template

## Purpose

Owns what generated repositories receive and the reference documentation that explains why. Read `docs/github_repository_structure.md` before changing what ships.

## Ownership

| Path | What it owns |
|---|---|
| `src/base-repo/` | The payload for generated repositories. `/repo-builder` reads it at a specific commit, not from the working tree. |
| `src/repository-addons/` | Files adopted when a destination needs them, not copied during generation. See “Additions by Occasion” in `docs/github_repository_structure.md` for each trigger. |
| `src/addon-adoption.json` | The addon walkthrough inputs: `slots` are tokens to replace, `reviews` require judgment without a token, and `external` steps happen outside the repository. See `apps/repo-builder/src/references/addon-adoption.md`. |
| `src/ownership.json` | The starting ownership rules for a destination's `.repo-template.json`. `apps/repo-builder/src/scripts/generate.py manifest` reads the rules at the source commit. Add a rule in the same commit as a new payload path; `test_reference_assertions.py` checks coverage. |
| `src/ruleset.json` | The initial `main` ruleset sent to GitHub by `apps/repo-builder/src/scripts/generate.py settings`. Keep the required contexts in sync with the job `name:` values in payload `ci.yml`, `security.yml`, and `codeql.yml`'s `scanning` job. Update both in the same commit; `test_generate.py` checks the match. |
| `docs/github_repository_structure.md` | The payload's inventory, placement conventions, and reasons for additions. |

Keep the three JSON files beside the payload and addons, not inside either tree.
They are inputs to `/repo-builder`, not files for a destination to adopt or read.
In-file addon guidance serves manual adoption and is not a substitute for the walkthrough manifest.

## Local Contracts

### Choose what ships

**Day-one test:** Ship a file only if its reason for being there holds for every generated repository.
Keep `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CODEOWNERS`, and other conditional files as additions by occasion; their absence is not a consequence of repository visibility.

**Addons:** Use a path absent from `src/base-repo/` so adoption cannot overwrite a shipped file.
Put optional guidance for an existing payload path in comments in that file.
Each addon must be nonempty and carry its own adoption guidance: use comments where supported and prose otherwise.

**Optional support in the payload:** A shipped file may support an addon if the unadopted state is a no-op.
`src/base-repo/scripts/system-packages` exits `0` if `.github/system-packages.txt` is absent.
A failure without the addon would break every destination that did not adopt it.

### Mirror live and payload changes

Use root `scripts/check` to verify this checkout; `src/base-repo/scripts/check` is data for generated repositories.
If a change applies to both, edit both trees in the same commit.
Write payload references against the destination's layout, without the `src/base-repo/` prefix.

| Change | What to do |
|---|---|
| Dependabot action bump | Mirror it into `src/base-repo/.github/` on the bot's branch before merging. The `github-actions` ecosystem scans the root and `/.github/actions/*`, not `apps/`. Actionlint can pass on both copies while revisions differ. |
| Pre-commit dependency bump | Keep both directories in the `pre-commit` ecosystem and keep `group-by: dependency-name`; otherwise Dependabot opens separate pull requests. The payload directory is re-derived from tracked manifests, not carried forward. |
| Manual `.pre-commit-config.yaml` edit | Compare the two configs directly; `scripts/payload-parity` checks `.github/` and `scripts/`, not these root files. Preserve the deliberate differences below. |
| New language manifest | Let `/repo-builder` derive entries for tracked destination manifests. The payload Dependabot config ships only actions and pre-commit; an entry without a manifest fails with `dependency_file_not_found`. Root `uv` needs no second directory because root `pyproject.toml` is not shipped. |

When changing Dependabot derivation, read “Dependabot entries follow the manifests present” in `apps/repo-builder/src/references/lifecycle.md`.
See `.github/dependabot.yml`'s header for the manifest mapping.

### Deliberate differences between root and payload

- **Dev container JSON:** Preserve `check-json` exclusions for the commented `devcontainer.json`.
  Root excludes `apps/github-repository-template/src/repository-addons/.devcontainer/devcontainer.json`; payload excludes `.devcontainer/devcontainer.json` at the destination root.
  The dev container schema allows comments, but the hook requires strict JSON.
- **Root-only hooks:** Keep `addon-adoption` and `reference-assertions` here; their inputs never reach a destination.
  Ship `payload-parity` in both configs; it reports `not-applicable` until a repository holds a payload of its own.
- **Scripts contract:** Keep `scripts/CLAUDE.md` root-only.
  It is the sole expected difference under `scripts/`; `scripts/payload-parity` reports other differences and fails until they are fixed.
  Destinations build their own child contracts.
- **Template Contract:** Put the bare Commands and Layout rules in `src/base-repo/CLAUDE.md`; the root keeps the fuller versions and rationale.
  Update a changed rule in both in the same commit.
  Merge template updates into root Commands and Layout instead of adding a second contract section.
  Keep the payload's four common commands and point to `ls scripts/` for the rest.
  Leave out Git rules enforced by shipped hooks and references to this repository, its `pyproject.toml`, or ADRs that do not ship.

### Preserve intentional scaffolding

- **First unit:** `src/base-repo/apps/app-name/` contains only `.unit.json` and `src/`.
  Generation moves it to the first derived unit rather than copying it.
  Update `apps/repo-builder/src/references/generate.md` step 8 if you change that skeleton.
- **Empty directories:** Keep root `libs/`, `tests/`, `docs/specs/`, and `docs/plans/`, and unit `tests/` and `docs/specs/`, as placement conventions rather than shipped placeholders.
  The default tracker holds specs as GitHub Issues; plan mode creates `docs/plans/` on first use.
  Keep `.gitkeep` in `tmp/` and the empty `.claude/` subdirectories so those scaffolds ship.
- **Local configuration:** Keep `src/base-repo/.env` empty.
  The root ignore pattern permits tracking the nested payload file; it ignores the copied `.env` at a destination root.
  Generation provides the local file, but later clones do not inherit it.
- **Agent surfaces:** Ship `.mcp.json` and the `.claude/` subdirectories without rules or tooling; personal hooks, rules, output styles, and skills live in `~/.claude`.
  Force-track the `.claude/` scaffold here so it ships, but keep it ignored in destinations.
  Track `CLAUDE.md` at every scope in destinations: it is the contract, not a shim.

## Work Guidance

Decide whether a change affects the live checkout, the payload, or both before editing.
Update `docs/github_repository_structure.md` in the same commit when a payload change makes its description stale.

Prefer explicit failure over silent omission in generated repositories. Keep `pass`, `not-applicable`, `unavailable`, and `FAIL` distinct so an agent can tell whether a check actually ran.

## Verification

| To verify… | Use… |
|---|---|
| Syntax and placement | Root `scripts/check` runs ShellCheck and actionlint through pre-commit; `scripts/structure` audits both trees. The payload must pass layout without a special `.structure-allow` entry. Root allowlists apply only at the real repository root. |
| Addon coverage | The `addon-adoption` hook always runs `apps/repo-builder/src/scripts/tests/test_addon_adoption.py`, with no path filter so deletions count. It checks manifest coverage, collisions with payload paths, nonempty addons, and presence of declared slot tokens. It does not judge the guidance. |
| Contract against code | `apps/repo-builder/src/scripts/tests/test_template_contract.py` runs under pytest in `scripts/check`, not as a hook. It compares root, scoped, toolchain, and `deploy/` folders and `.unit.json` values to payload `scripts/structure`. It checks named root files and executable commands, and runs the example through `unit_facts_program` when `jq` is available. Compare the root prose by hand. |
| Generated behavior | Use `src/base-repo/scripts/tests/*-test` after generation and the `/repo-builder` evals in `apps/repo-builder/src/evals/`. |
| Agent cost of the Template Contract | Run `scripts/contract-eval` manually after committing a contract change. It refuses a dirty payload and uses `HEAD` fixtures. It runs the same tasks with and without the contract via `claude -p` and reports pass, turns, tokens, and cost per arm. It spends money and is outside the gate; see its header for isolation. |

## Child Index

None for this app. `src/base-repo/CLAUDE.md` addresses a generated repository, not this checkout.
