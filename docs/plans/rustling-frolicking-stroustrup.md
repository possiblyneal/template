# Standardize the ADR directory as `docs/adrs/`

## Context

PR #19 (branch `refactor/skills-personal-namespace`) relocated two skills and, in the same commit, changed the mattpocock skill docs to call the ADR directory `docs/adrs/` (plural). The user wants that spelling to become the standard everywhere — it reads more accurately and is the more common convention. Right now the skills point at `docs/adrs/` while the *actual* directory, the `adr-index` tooling, the pre-commit hook, CI, the docs, and the `repo-builder` evals all still say `docs/adr/`. That mismatch means the skills instruct agents to write to a directory the index generator and pre-commit hook do not look at.

This repo builds other repos, so the change lands in **two trees**: the live root tree (governs this repo) and the template payload at `apps/github-repository-template/src/base-repo/` (copied into every generated repo). Per `apps/github-repository-template/CLAUDE.md`, a fix at only one leaves the other wrong — both must change in the same commit.

Work continues on the existing branch `refactor/skills-personal-namespace` as a follow-up commit.

## Scope decisions

- **Rename the directory** `docs/adr/` → `docs/adrs/` in both trees. Only `0000-template.md` lives in each; no `index.md` exists yet (it regenerates on next pre-commit).
- The **tool** `scripts/adr-index` keeps its name and the pre-commit **hook id** `adr-index` stays — only the `docs/adr` *path* the tool reads/writes changes.
- **Leave untouched** (frozen historical artifacts): everything under `.openclaude/skills/repo-builder-workspace/`, and `docs/plans/*.md`.
- **Root `docs/adr/0000-template.md` content divergence** from the payload copy is pre-existing and out of scope; this plan only renames its directory and fixes the one confirmed typo in the payload copy.

## Changes

### 1. Directory renames (`git mv`, both trees)
- `docs/adr/` → `docs/adrs/`
- `apps/github-repository-template/src/base-repo/docs/adr/` → `.../docs/adrs/`

### 2. Root tooling
- `scripts/adr-index` — `adr_dir="docs/adr"` (L20) and the header comment (L4).
- `scripts/tests/adr-index-test` — every `docs/adr` path (incl. the nested `apps/billing/docs/adr` example and the awk pattern `# docs\/adr\/index.md` at L266) → `docs/adrs`.
- `.pre-commit-config.yaml` — the `docs/adr/index.md` comment (L43). Hook id/entry unchanged.
- `.github/workflows/ci.yml` — verify each `adr` hit; change only genuine `docs/adr` path references.

### 3. Payload tooling (mirror of §2, verify each copy exists first)
- `.../base-repo/scripts/adr-index`
- `.../base-repo/scripts/tests/adr-index-test`
- `.../base-repo/.pre-commit-config.yaml`
- `.../base-repo/.github/workflows/ci.yml`
- `.../base-repo/scripts/tests/libs/harness.sh` — verify whether it actually references `docs/adr`; change only if real.

### 4. Docs (path references; mirror root + any base-repo copy)
- root `CLAUDE.md` (L49)
- `docs/CLAUDE.md` (L9, 18, 22, 24, 25, 34, 40)
- `scripts/CLAUDE.md` (L14, 40, 42, 70)
- `apps/github-repository-template/docs/github_repository_structure.md` (L123)
- base-repo copies of `docs/CLAUDE.md` and `scripts/CLAUDE.md` if present — mirror the same edits.

### 5. repo-builder evals (these FAIL if not updated — they assert the hardcoded path)
- `.openclaude/skills/repo-builder/evals/setup_fixture.py` (L81)
- `.openclaude/skills/repo-builder/evals/verify_fixture.py` (L75-77)
- `.openclaude/skills/repo-builder/evals/evals.json` (L12)
- `.openclaude/skills/repo-builder/references/lifecycle.md` (L127)

### 6. Other references
- `TODO.md` (L15) — the `docs/adr/0000-template.md` source path → `docs/adrs/`.

### 7. Typo / content fixes (per user direction)
- `domain-modeling/ADR-FORMAT.md` L9 — replace the truncated line `` `docs/adrs/0000-template.` `` with a proper one-line reference to `docs/adrs/0000-template.md` plus the short "scan for the highest number and increment" note. (Do **not** restore the full inline template spec.)
- `setup-matt-pocock-skills/domain.md` L7-9 — move the `**` outside the code spans so `` `**docs/adrs/**` `` etc. render as bold code (**`docs/adrs/`**).
- `apps/github-repository-template/src/base-repo/docs/adrs/0000-template.md` L13 — `superseeds` → `supersedes`.

## Verification

1. `scripts/adr-index` runs clean and writes `docs/adrs/index.md` (not `docs/adr/`).
2. `scripts/tests/adr-index-test` passes (root copy).
3. repo-builder tests: `uv run --with pytest python -m pytest .openclaude/skills/repo-builder/scripts/tests/`.
4. `scripts/check` — full local gate incl. pre-commit across every file; the `adr-index` and `addon-adoption` hooks must pass.
5. Grep guard: `docs/adr/` (singular) must return **zero** hits outside `.openclaude/skills/repo-builder-workspace/` and `docs/plans/`.
6. Documentation pass: the CLAUDE.md files touched in §4 are themselves the doc update for the rename; re-check the chain and refresh any affected Child Index wording.
