# Inventory of the four reference repositories against the payload

Resolves [#106](https://github.com/possiblyneal/template/issues/106), under the map [#104](https://github.com/possiblyneal/template/issues/104).

Every fact below was read from the repository itself or from the GitHub API, never inferred.
The four were cloned into `tmp/refs/` and read there; none of the four was written to.
Each clone is the default branch's tip as of 2026-09-10, so every path named is a tracked
path and gitignored scratch is invisible by construction, the same enumeration
`scripts/structure` uses.

Sources: `apps/github-repository-template/src/base-repo/` (the payload, 78 files),
`scripts/structure`, `scripts/libs/detect.sh`, `scripts/detect probe`, `gh api repos/<slug>`.
`scripts/structure` and `scripts/detect` derive their repository root from their own location,
so each clone got an untracked copy of `scripts/structure`, `scripts/detect`,
`scripts/libs/result.sh`, and `scripts/libs/detect.sh`. Both enumerate with `git ls-files`,
so those copies are invisible to their own audit and add no finding.

## Summary of what the inventory changes

1. **Not four Python repositories, three and a half.** `personal-podcast` tracks
   `frontend/package.json` and `frontend/package-lock.json`, and `libs/detect.sh` reports
   `node=false` there, because `has_node()` tests a root `package.json` only. Its frontend is
   invisible to every check the payload installs.
2. **The conversion bar fails on all four for the same reason, and it is not layout.**
   `_capability_typecheck_python` runs `uv run ty check .`; no reference repository declares
   `ty`, `uv_run` returns `NO_RUNNER`, and `result.sh` exits non-zero on `unavailable` as well
   as on `FAIL`. The payload ships no root `pyproject.toml`, being root-only here by that file's
   own comment, so nothing in the payload adds the dev dependency group. No ticket on the map
   covers who does.
3. **The pilot is ambiguous.** `~/code/knowledge-base` has `origin` set to
   `possiblyneal/knowledge-base-app`, and a separate `possiblyneal/knowledge-base` also exists.
4. **Three of the four root `CLAUDE.md` files are the same document**, a "DOX framework" variant
   of the operator's global documentation rules with a short project section appended. Only
   `media-encoder`'s is genuinely project prose.
5. **The map's Notes are right about shape and wrong in three details**, listed near the end.

## 1. Collision set: tracked paths that also exist in the payload

Exact path matches. The payload path is what conversion would land on top of.

| path | knowledge-base | media-encoder | medical-researcher | personal-podcast |
| --- | --- | --- | --- | --- |
| `CLAUDE.md` | collides | collides | collides | collides |
| `.gitignore` | collides | collides | collides | collides |
| `.github/workflows/ci.yml` | no | collides | no | no |
| `docs/agents/issue-tracker.md` | no | collides | collides | no |
| `docs/agents/domain.md` | no | collides | no | no |
| `docs/agents/triage-labels.md` | no | collides | no | no |

Two files collide in every one of the four, and nothing else collides more than twice. The
file-by-file decision the flow needs is therefore small; the expensive decisions are the
directory collisions below, where no filename repeats but the meaning of the directory does.

**Directory collisions**, meaning a directory the payload fills that the destination already
uses for something else:

- `scripts/`. `knowledge-base` holds `backfill_created.py` and `migrate_okf_v0_2.py`, Python,
  described by its own `CLAUDE.md` as "one-shot maintenance scripts (run manually on the dev box
  or server; not part of the service)". `media-encoder` holds `ci.sh` and `deploy.sh`, shell.
  The payload lands roughly forty files here. No filename collides; the contract does, exactly
  as the map's Notes predicted.
- `docs/`, in all four. `knowledge-base` and `media-encoder` use `docs/adr/`, singular; the
  payload ships `docs/adrs/0000-template.md`. A near miss rather than a collision, and a silent
  one: `scripts/adr-index` would list nothing and the existing records would go unindexed.
- `docs/agents/`, in `media-encoder` (all three files) and `medical-researcher` (one). These are
  the payload's own agent-skill docs, already adopted by hand and now possibly divergent.
- `deploy/`, in `knowledge-base`, `media-encoder`, and `personal-podcast`.
- `.claude/`. `personal-podcast` tracks `.claude/skills/simplify-code/SKILL.md`; the payload
  ships `.claude/skills/.gitkeep`. The only destination-owned `.claude/` content in the four.
- `.github/workflows/`, in `media-encoder` only.

## 2. Root files and folders against the payload's root allowlist

Classified against `scripts/structure`'s `root_files` and `root_folders` arrays, which are the
`CLAUDE.md` **Layout** allowlist held as code.

### knowledge-base

- Permitted by name: `CLAUDE.md`, `CONTEXT.md`, `.gitignore`, `deploy/`, `docs/`, `scripts/`, `tests/`
- Permitted as a workspace manifest: `pyproject.toml`
- Needs permission: `src/` (root folder)

### media-encoder

- Permitted by name: `CLAUDE.md`, `CONTEXT.md`, `README.md`, `.gitignore`, `deploy/`, `docs/`, `.github/`, `scripts/`, `tests/`
- Permitted as a workspace manifest: `pyproject.toml`
- Needs permission: `Dockerfile`, `.dockerignore`, `justfile` (root files); `media_encoder/`, `server/` (root folders)

### medical-researcher

- Permitted by name: `CLAUDE.md`, `CONTEXT.md`, `README.md`, `.gitignore`, `docs/`, `tests/`
- Permitted as a workspace manifest: `pyproject.toml`
- Needs permission: `.scratch/`, `src/` (root folders)

### personal-podcast

- Permitted by name: `CLAUDE.md`, `CONTEXT.md`, `README.md`, `.gitignore`, `.claude/`, `deploy/`, `docs/`
- Permitted as a workspace manifest: `pyproject.toml`
- Needs permission: `PRD.md`, `.containerignore` (root files); `backend/`, `config/`, `data/`, `frontend/` (root folders)

Root `README.md` is permitted, being on the additions-by-occasion list, so three of the four
carry one legally. Root `tests/`, `docs/`, `scripts/`, and `deploy/` are all permitted by name in
every case, and in every case they are app-scoped rather than repo-wide. `scripts/structure`
cannot see that: `tests-are-crossapp` and `scope-matching` are two of its three deliberate
`not-applicable` verdicts. The audit passes those folders and is wrong, quietly, for all four.

## 3. What `scripts/structure` reports today

Every one of the four exits 1. `unit-declaration` and `unit-facts` are `not-applicable` in all
four, since none has an `apps/`, so `jq` is never reached.

| repository | failing rules | violations |
| --- | --- | --- |
| knowledge-base | `root-folders`, `deploy-folders` | 1 + 3 = 4 |
| media-encoder | `root-files`, `root-folders`, `deploy-folders` | 3 + 2 + 1 = 6 |
| medical-researcher | `root-folders`, `docs-content` | 2 + 1 = 3 |
| personal-podcast | `root-files`, `root-folders`, `deploy-folders` | 2 + 4 + 9 = 15 |

Verbatim findings:

- **knowledge-base**. `src/`: root folder needs permission. `deploy/Containerfile`,
  `deploy/README.md`, `deploy/kb-web.container`: `deploy/` holds one folder per technology, not
  loose files.
- **media-encoder**. `.dockerignore`, `Dockerfile`, `justfile`: root file needs permission.
  `media_encoder/`, `server/`: root folder needs permission. `deploy/README.md`: a loose file
  under `deploy/`.
- **medical-researcher**. `.scratch/`, `src/`: root folder needs permission.
  `docs/prompt1.txt`: `docs/` takes Markdown freely, anything else needs permission.
- **personal-podcast**. `PRD.md`, `.containerignore`: root file needs permission. `backend/`,
  `config/`, `data/`, `frontend/`: root folder needs permission. All nine entries directly in
  `deploy/` are loose-file violations, including `deploy/CLAUDE.md` and `deploy/README.md`.

`deploy-folders` is the surprise. The map's Notes name layout, boundaries and CI as the hard
parts and never mention `deploy/`, yet it produces 13 of the 28 total violations. Three of the
four keep Containerfiles and `.container` units directly in `deploy/`, and `media-encoder`, which
does use `deploy/quadlet/`, `deploy/env/`, and `deploy/systemd/`, still fails on a single
`deploy/README.md`. The rule admits only five technology folders and no loose files at all, so a
`README.md` explaining the deployment has nowhere legal to sit. No ticket on the map covers it.

## 4. What `libs/detect.sh` detects, and adapter coverage

`scripts/detect languages` reports **python and nothing else** in all four. `has_python()` is
`[[ -s pyproject.toml ]]`, and all four have a root one.

`detect_orphan_manifests` fires once, on `personal-podcast`:

> `frontend/package.json` has no root `package.json`, so no check sees this package; add a root
> `package.json` covering `frontend`, or move it under an existing workspace

`personal-podcast` also tracks `backend/requirements.txt`, which no detection function reads. Its
Python is found only because a root `pyproject.toml` happens to exist for pytest and ruff
configuration.

Adapter coverage for python, from `scripts/detect probe`: `lint`, `format-check`, `typecheck`,
`test`, `audit`, `toolchain`, `format-write`, and `run` are **wired**; `build` and `package` are
**absent**. Absent `build` and `package` are by design for Python and are not a conversion
problem, since `scripts/package` leaves `dist/` alone where a language has no packaging adapter.

Wired is not the same as available, and this is where the conversion bar actually breaks:

| adapter | command | state in all four |
| --- | --- | --- |
| `lint` | `uv run ruff check .` | resolves; `uv` creates a venv and fetches ruff |
| `format-check` | `uv run ruff format --check .` | resolves |
| `typecheck` | `uv run ty check .` | **`ty` not resolvable, `NO_RUNNER`, so `unavailable`** |
| `test` | pytest under `uv run` | not declared by any of the four |

`result.sh` line 38 treats `unavailable` exactly as it treats `FAIL`: "a check that did not run
is not a check that passed." So `scripts/check` fails on all four at `typecheck`, on a missing
dependency rather than on any property of the code. Verified empirically in the
`personal-podcast` clone: `uv run ruff --version` prints `ruff 0.15.11`; `uv run --quiet ty
--version` fails with `Failed to spawn: ty`.

What each destination already declares, which is the other half of the map's open question about
the root Python manifest:

| repository | `[project]` | build backend | ruff | pytest | type checker | lockfile |
| --- | --- | --- | --- | --- | --- | --- |
| knowledge-base | yes | setuptools | none | none | none | none |
| media-encoder | yes | none (`[dependency-groups]`) | configured | none | none | none |
| medical-researcher | yes | setuptools | configured | configured | **mypy** | none |
| personal-podcast | **no `[project]` at all** | none | configured | configured | none | none |

None has a lockfile. `medical-researcher` declares mypy where the payload's adapter runs `ty`,
two type checkers, and the payload's is the one that decides the gate. `personal-podcast`'s
`pyproject.toml` is pure tool configuration with no `[project]` table; `uv run` copes, so this is
survivable, but it means `has_python()` is true there for a file that declares no package.

The template's own root `pyproject.toml` carries `dev = ["pytest>=8", "ruff>=0.14",
"ty>=0.0.1a21"]` and `[tool.uv] package = false`, and its header states it is root-only and must
never be mirrored into the payload. So the payload cannot supply the dependency group, and
conversion must edit the destination's existing `pyproject.toml`, a file the destination owns and
has already configured for a different tool set. That edit is unowned by any ticket on the map.

## 5. Remote state

All four remotes exist. All four are **private**, none archived.

| repository | remote | default branch | visibility | merge / squash / rebase | delete branch on merge | workflows |
| --- | --- | --- | --- | --- | --- | --- |
| knowledge-base | `possiblyneal/knowledge-base-app` | `main` | private | all three enabled | off | Dependency Graph only (dynamic) |
| media-encoder | `possiblyneal/media-encoder` | `main` | private | all three enabled | off | `.github/workflows/ci.yml` plus Dependency Graph |
| medical-researcher | `possiblyneal/medical-researcher` | **`master`** | private | all three enabled | off | Dependency Graph only (dynamic) |
| personal-podcast | `possiblyneal/personal-podcast` | `main` | private | all three enabled | off | Dependabot Updates and Dependency Graph (both dynamic) |

Branch protection returns HTTP 403 on all four, "Upgrade to GitHub Pro or make this repository
public", the same plan limit the root `CLAUDE.md` records for this repository. Every remote has
exactly one branch except `personal-podcast`, which also carries
`dependabot/npm_and_yarn/frontend/npm_and_yarn-a6ab454cc1`, opened against the very frontend that
`libs/detect.sh` cannot see.

Labels. Only `media-encoder` carries the canonical triage roles, and only partly: it has
`needs-info`, `needs-triage`, `ready-for-agent`, and `ready-for-human` alongside the GitHub
defaults. `personal-podcast` has `ready-for-agent` alone, plus `dependencies` and `javascript`.
`knowledge-base` is the nine GitHub defaults untouched. `medical-researcher` is the defaults plus
`accessibility`, and it does not use GitHub Issues at all: its `.scratch/CLAUDE.md` is described
in its own root `CLAUDE.md` as a "local-markdown issue tracker: wayfinder maps, tickets, and
planning assets." Conversion landing `docs/agents/issue-tracker.md`, which names GitHub Issues,
contradicts a tracker that repository actively uses. That is the same `.scratch/` the audit flags
as a root folder needing permission.

**The pilot's identity is ambiguous.** `~/code/knowledge-base` points at
`possiblyneal/knowledge-base-app`, but `possiblyneal/knowledge-base` also exists, is also
private, also defaults to `main`, and was last pushed 2026-09-02. Which one the map means by
"the pilot" is not settled by the local checkout's name.

## 6. Where the deployables are, in each repository's own words

Quoted from the repository's own `CLAUDE.md` and `CONTEXT.md`, not inferred from directories.
Quotations keep their original punctuation.

**knowledge-base**, one deployable. `CLAUDE.md`: "AI-managed personal knowledge management
service; v1 complete and deployed. Production: podman quadlet `kb-web` on the server
(10.10.10.10:8123)". `deploy/` holds `Containerfile`, `kb-web.container`, and `README.md`. `src/`
is the service; `scripts/` is explicitly "not part of the service"; tests run by
".venv/bin/python -m pytest tests/". One unit, `run: longlived`, `ships: quadlet`.

**media-encoder**, four programs, two containers, two host units. `CLAUDE.md`: "`media_encoder/`
is the package"; `api.py` is "the encode queue API", `dashboard.py` "the dashboard", `encoder.py`
"the encoder, run as a subprocess, one job at a time", `shared.py` "helpers common to all four
programs". `server/bin/encode-reconcile.py` is "the nightly reconciler, installed on the host
rather than run in a container, so it stays outside the package", and
`server/bin/cpu-turbo-schedule.sh` "holds the host at base clock overnight". `server/arr/` holds
"the shell scripts Radarr and Sonarr invoke", whose live copies sit on the host under
`~/.local/share/{radarr,sonarr}/scripts`. Deployment is one command: "`just deploy` is the whole
deployment ... Never deploy by hand." `deploy/` already matches the payload's technology-folder
shape, with `quadlet/` (two `.container`), `env/` (two), and `systemd/` (two `.service` and two
`.timer`).

This is the hardest mapping of the four. `media_encoder/` and `server/` are one shipped thing to
`just deploy` but three delivery mechanisms: two quadlets, host systemd units, and shell scripts
copied into two other applications' container volumes. The template's ship vocabulary is
`executable`, `quadlet`, or `none`, and none of them names "installed onto the host by another
repository's deploy script."

**medical-researcher**, no deployable at all. No `deploy/`, no container, no service. Its
`pyproject.toml` declares `[project.scripts] medical-researcher = "medical_researcher.cli:main"`,
so it is a CLI. Its `CLAUDE.md` Child Index names `src/CLAUDE.md` as "application/source
implementation for the medical research agent" and never mentions deployment. One unit,
`run: oneshot`, `ships: executable`, and `ships.targets` is required for `executable`, a value
nothing in that repository states.

**personal-podcast**, two deployables plus a third-party sidecar. `CLAUDE.md`: "Article
aggregation/summarization should use `backend/app/briefing.py` as the main CLI"; "RSSHub runs on
the server via Podman quadlet"; "All code lives on `dev`. The server runs images only — never a
source checkout. Build on `dev`, ship with `podman save` → `sudo podman load`." Its Child Index
names `deploy/CLAUDE.md` as "deployment artifacts and server-side infrastructure contracts".
`deploy/` holds `backend.Containerfile`, `frontend.Containerfile`,
`personal-podcast-backend.container`, `personal-podcast-frontend.container`, `rsshub.container`,
and two `.env.example` files, all directly in `deploy/`, all nine entries flagged.

Three quadlets for two units, one of them (`rsshub`) not this repository's software at all. The
`.unit.json` shape is one declaration per unit, and nothing in it names a dependency container a
unit needs but does not build.

## Where this contradicts the map's Notes

The Notes' four-row table is accurate on shape. Three details are wrong or incomplete:

1. **`medical-researcher`: "root `src/`, `data/`, `.scratch/`".** `data/` exists on disk but is
   **untracked**, so `scripts/structure` never sees it and it produces no finding. `src/` and
   `.scratch/` are the only two root-folder violations. A conversion reasoning from the working
   tree rather than the index would decide about a directory that is not in the repository.
2. **`personal-podcast`: "`backend/`, `frontend/`, root `config/`, `data/`, `PRD.md`".** It also
   has a tracked `deploy/`, nine violations and the largest single finding in the four, and a
   tracked `.claude/skills/simplify-code/SKILL.md`, the only destination-owned `.claude/` content
   anywhere in the four and directly in the payload's path.
3. **"Four real destinations, all Python."** `personal-podcast` is Python and Node, and the Node
   half is undetectable to `libs/detect.sh` as written. The map's own open question asks whether
   `detect.sh` "reads a foreign tree correctly across a `justfile`, a `Dockerfile`, a committed
   `.venv`, and vendored caches", none of which turned out to matter: no reference repository
   tracks a `.venv` or a vendored tree, and `detect.sh` ignores a `justfile` and a `Dockerfile`
   entirely. The real failure is a root-manifest test that a subdirectory frontend defeats.

Two further items are sharpened rather than contradicted:

- The Notes call `media-encoder`'s `scripts/ci.sh` "a `scripts/ci.sh` doing `scripts/check`'s
  job". It is worse than that. Its `justfile` defines a `check:` recipe aliasing `ci`, so the
  destination already has a command literally named `check` that means something narrower:
  `ruff check`, `ruff format --check`, and `python3 -m unittest discover -s tests/unit`. Its
  workflow pins `ruff==0.15.11` so "CI and a developer's local run apply identical rules", a
  guarantee the payload's floating `ruff>=0.14` does not make.
- `medical-researcher`'s rename to `main` is real and it is the only one. The other three already
  default to `main`.

## Decisions exposed that no ticket on the map covers

1. **Who adds `ty` and `pytest` to the destination's `pyproject.toml`.** The payload ships no root
   Python manifest and is forbidden from doing so. Without the edit, `scripts/check` fails at
   `typecheck` on all four, and the map's stated conversion bar is unreachable. This is adjacent
   to the map's existing open question about the root Python manifest, but that question is about
   conflict with an existing configuration; this one is about an absence the payload cannot fill.
2. **The `deploy/` five-folder rule versus a real deployment.** Thirteen of twenty-eight
   violations, including a `README.md` and a `CLAUDE.md` that document the deployment and have no
   legal location under the rule.
3. **A destination whose issue tracker is not GitHub Issues.** `medical-researcher` runs a
   markdown tracker in `.scratch/`, which is also a root-folder violation. Landing
   `docs/agents/issue-tracker.md` asserts a tracker it does not use.
4. **`ships.targets` for a unit that never stated a platform.** Required whenever `kind` is
   `executable`, and `medical-researcher` is a CLI with no such statement anywhere.
5. **A unit that ships a container it does not build**, namely `personal-podcast`'s
   `rsshub.container`.
6. **`docs/adr/` versus `docs/adrs/`.** Two destinations have real ADRs in the singular
   directory. `scripts/adr-index` would index none of them and report nothing wrong.
7. **Which repository is the pilot**, given that `knowledge-base` and `knowledge-base-app` both
   exist.
