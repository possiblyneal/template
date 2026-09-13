# Prototype: retrofitting knowledge-base's layout by hand

Resolves [#111](https://github.com/possiblyneal/template/issues/111), under the map
[#104](https://github.com/possiblyneal/template/issues/104).

Every number below was produced by running the thing, not estimated. The candidate is a clone of
`~/code/knowledge-base` at `3afdebe`, worked in `tmp/proto111/kb-candidate` on branch
`retrofit/candidate`, commit `ba1fe29`. None of the four reference repositories was written to.

## What the prototype did

The payload was overlaid absent-paths-only, per [#108](https://github.com/possiblyneal/template/issues/108)'s
rule. Two paths collided and were skipped: `CLAUDE.md` and `.gitignore`.

Then the moves, with `knowledge-base` read as one unit named `kb` per
[#110](https://github.com/possiblyneal/template/issues/110)'s evidence precedence (package name,
no occupied unit directory):

| from | to |
| --- | --- |
| `src/` | `apps/kb/src/` |
| `tests/` | `apps/kb/tests/` |
| `scripts/backfill_created.py`, `scripts/migrate_okf_v0_2.py` | `apps/kb/scripts/` |
| `deploy/Containerfile` | `apps/kb/deploy/containerfile/Containerfile` |
| `deploy/kb-web.container` | `apps/kb/deploy/quadlet/kb-web.container` |
| `deploy/README.md` | `apps/kb/docs/deployment.md` |
| `docs/adr/` | `docs/adrs/` |

Plus `apps/kb/.unit.json` — `{"schema_version": 1, "run": "longlived", "ships": {"kind": "quadlet"}}` —
and three lines in `pyproject.toml`.

## Result

`scripts/structure`: **passes, all thirteen decidable rules, with zero `.structure-allow` entries.**
The three `not-applicable` verdicts (`libs-are-shared`, `tests-are-crossapp`, `scope-matching`) are
the audit's deliberate ones.

Diff against the destination's tip: **77 payload files added, 55 destination files renamed, exactly
one destination file modified** (`pyproject.toml`), zero deleted.

`pytest`: **113 passed.** No import path needed rewriting. `import kb` is package-relative, so the
package moved intact; and both one-shot scripts bootstrap with
`Path(__file__).resolve().parent.parent / "src"`, which still resolves after the move because
`apps/kb/scripts/` sits a sibling of `apps/kb/src/`. The single required edit was
`[tool.setuptools.packages.find] where = ["src"]` → `["apps/kb/src"]`, without which the package
does not build and nothing imports.

## What the bar actually fails on, and it is not layout

With structure passing and tests green, `scripts/check` still fails:

| check | result |
| --- | --- |
| `uv run ruff check .` | 28 errors, 24 auto-fixable |
| `uv run ruff format --check .` | 21 of 27 files would be reformatted |
| `uv run ty check .` | 4 diagnostics |
| `pytest` | 113 passed |

All pre-existing code debt in the destination. Not one of the 28 was caused by a move. The
prototype's central finding is that **layout reconciliation is cheap and the retrofit bar is
expensive, and they fail for unrelated reasons.**

## Three things the ticket did not predict

**1. `scripts/doctor` fails on missing pre-commit hooks, and it is the first gate of `scripts/check`.**

```
pre-commit          FAIL    5 violation(s)
                      no pre-commit hook in this clone; run: pre-commit install
                      ... commit-msg, pre-push, post-checkout, post-merge
```

[#109](https://github.com/possiblyneal/template/issues/109) decided the retrofit never runs
`pre-commit install`, because a worktree shares `.git/hooks` with the operator's clone. Both cannot
stand: doctor is the bar's first gate. Separately, a global `core.hooksPath` on this machine makes
`pre-commit install` refuse outright — *"Cowardly refusing to install hooks with `core.hooksPath`
set"* — so even choosing to install is not straightforwardly available. Ticketed separately.

**2. `deploy/README.md` had nowhere legal.** `deploy-folders` admits five technology folders and no
loose file at any scope, so a README explaining a deployment cannot sit beside it. It is a server
runbook — mount points, a `tar | ssh` update procedure, an index-rebuild command — not a project
overview, and `knowledge-base` has no root `README.md` at all.

**3. Twelve stale path references** survive in destination-owned Markdown, which no test catches:
`CLAUDE.md:88,90,91,99`; `docs/PLAN.md:3`; `docs/BACKLOG.md:4`; `docs/specs/okf-v0.2.md:3,151,171,178,184,188,190`;
`docs/specs/created-updated-split.md:4`; `docs/specs/moc.md:164,173,182,183`. Plus one inside the
relocated runbook itself, pointing at `deploy/Containerfile`.

## Where the other three diverge

Read from clones at their tips. Nothing here was immovable.

**media-encoder.** `justfile` cannot move — `just` resolves it by searching upward from cwd — but it
is not immovable so much as **duplicative**: 9 of its 12 recipes (`test`, `lint`, `fmt`, `fmt-check`,
`fix`, `clean`, `ci`, `check`, `dev-api`) are what `scripts/check`, `scripts/fix`, `scripts/clean`
and `scripts/run` already do, and `scripts/ci.sh` is literally `scripts/check`'s job. `just deploy`
wrapping `scripts/deploy.sh` has no template equivalent, so the payload does not fully cover it.
`.github/workflows/ci.yml` collides, and the destination's job is a strict subset of the payload's
gate. `Dockerfile` and `.dockerignore` relocate with the build context. Two units.

**medical-researcher.** `.scratch/` is 83 tracked Markdown files — a local issue tracker of the kind
these skills install when no hosted tracker exists. `docs/prompt1.txt` fails `docs-content`. Default
branch `master`.

**personal-podcast.** `config/` is five files of real application input, not inert assets:
`config.yaml` and its `.example` carry schedule, sources, internal endpoints and personas, and
`config/prompts/{summary,keypoints,opinion}.txt` are the LLM prompts. It is code-referenced at
`backend/app/config.py:8` (`PODCAST_CONFIG_DIR`, defaulting to `_REPO_ROOT / "config"`), built into
the image at `deploy/backend.Containerfile:15` (`COPY config /app/defaults`), mounted over by
`deploy/personal-podcast-backend.container:12`, and printed into every briefing's provenance header
at `briefing.py:1105,1419`.

`data/` is 131 tracked generated briefings plus `data/audio/.gitkeep`, and the decisive fact is that
the destination's own `.gitignore:26` is `data/briefings/*`. These files are tracked **against the
repository's stated intent** — they predate the rule or were force-added. `backend/app/briefing.py:37`
is `DATA_DIR = _REPO_ROOT / "data"`. All nine entries directly in `deploy/` are loose-file
violations, splitting into `containerfile/`, `quadlet/` and `env/`, with `deploy/CLAUDE.md` and
`deploy/README.md` left over.

## The collisions, measured

What a wholesale `.gitignore` replace drops, since the payload's 95 lines are security hygiene and
the destinations' are app noise. Payload has `.venv/`, `.DS_Store`, `.claude/`, `*.sqlite*`, `tmp/*`,
`apps/*/dist/`. Payload lacks:

| destination | dropped by a replace |
| --- | --- |
| knowledge-base | `*.egg-info/`, `.orca/` |
| medical-researcher | `*.egg-info/`, `.mypy_cache/`, **`data/`** |
| media-encoder | `*.backup.*`, `.pi/`, `.claude/settings.local.json`, `.claude/scheduled_tasks.lock`, `.claude/worktrees/` |
| personal-podcast | `data/briefings/*`, `data/audio/*`, and the `backend/` variants of both |

Two of those dropped rules are the `data/` rule itself, so a replace un-ignores exactly the generated
output that should stop being tracked.

`.claude/` is a direct disagreement rather than a gap: media-encoder's `.gitignore` says *"shared
config under `.claude/` stays tracked"* and ignores three specific paths, while the payload ignores
`.claude/` wholesale; personal-podcast tracks `.claude/skills/simplify-code/SKILL.md`. Already-tracked
files are unaffected by an ignore rule, so nothing breaks today.

The payload's `CLAUDE.md` is 32 lines of template facts — Commands, Git, Agent skills, Child Index —
closing with an instruction to scan the project, build the `CLAUDE.md` tree, and replace that message
with a real child index.
