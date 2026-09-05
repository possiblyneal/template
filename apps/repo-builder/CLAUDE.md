# Repo Builder

## Purpose

Develops the `/repo-builder` skill, which builds a repository from the payload at `apps/github-repository-template/src/base-repo/` and carries later template deltas into repositories already generated from it. The skill is this repository's product, so it lives under `apps/` like any other unit; a clone links it into place rather than holding a second copy.

## Ownership

- `src/SKILL.md` — the entry point, and the only file Claude Code reads to decide the skill applies.
- `src/references/` — the flows the entry point routes to: `lifecycle.md` first, then `generate.md`, `update.md`, `adopt.md`, `wayfinding.md`, `addon-adoption.md`, and the method `choosing_a_language.md` is a short path through.
- `src/scripts/preflight.py` — validates and describes generate, update, and adopt inputs before any flow acts.
- `src/scripts/tests/` — the pytest suite over `preflight.py`, plus `test_addon_adoption.py`, which is a check on the template payload rather than on this unit.
- `src/evals/` — `evals.json` and the fixture helpers the skill-eval tooling runs it against.
- `scripts/install` — creates the link described below.

## Local Contracts

**The link is the install.** `apps/repo-builder/scripts/install` creates `.claude/skills/repo-builder` as a symlink to `../../apps/repo-builder/src`, and `.gitignore` holds it out of the tree. It is a deployment artifact of this unit, not repository content: committing it, or committing a copy of the skill beside it, puts the skill at two paths and the second one goes stale. Every clone runs the install once.

**The link targets `src/`, not the unit root.** A skill directory is `SKILL.md` plus the paths beside it; `.unit.json` and this file are this repository's bookkeeping and have no meaning to the skill.

**The skill runs from this repository.** Its paths are repository-root-relative — `apps/github-repository-template/src/base-repo`, `src/addon-adoption.json` — and the destination is an argument rather than the working directory. A session that invokes it from somewhere else resolves those paths against the wrong tree. A generate's candidate is repository-root-relative too, at `tmp/<repository-name>/`: gitignored, so it cannot be committed here, and inside the repository, so materializing a whole tree needs no approval for a path outside it. `references/generate.md` step 3 is where that is stated; do not restate the path in a third place.

**`ships.kind` is `none` because the vocabulary has no word for this.** The three kinds are `executable`, `quadlet`, and `none`, and a symlinked skill is none of them. Adding a fourth means editing `scripts/structure`, which is mirrored into the payload, so every generated repository would gain a kind it has no unit to use; `docs/adrs/0001-declare-unit-delivery-as-two-facts.md` gates the declaration's shape. `none` here reads as "nothing this repository's packaging adapters build", which is accurate — `scripts/install` is what delivers it.

**Two root-level checks name paths inside this unit**, and moving a file here breaks them silently rather than loudly: the `addon-adoption` pre-commit hook's `entry`, and `testpaths` in the root `pyproject.toml`. The root `pyproject.toml` exists for this unit's Python; it is root-only and never mirrored into the payload.

## Work Guidance

`test_addon_adoption.py` is stdlib-only, and the file says why: it runs under pytest and standalone from a pre-commit hook that resolves no dependencies. A pytest-only idiom added later passes the first and breaks the second.

Editing under this unit's `src/` does not prompt — `.claude/settings.json` asks only for `apps/github-repository-template/src/**`, where the prompt's question, payload or root, is a real one.

## Verification

- `uv run pytest` — the suite, bounded here by the root `testpaths`. Runs inside `scripts/check` as the Python test capability.
- `pre-commit run addon-adoption --all-files` — the payload manifest check, at this unit's path. Runs on every commit.
- `src/evals/` is run by the skill-eval tooling against the fixtures its helpers build. It is not part of `scripts/check`: an eval invokes the skill, which is a model run rather than a check.

## Child Index

None.
