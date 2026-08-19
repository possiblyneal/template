# Standalone addon adoption for `repo-builder` (Gap 2)

> **Historical record — read `.openclaude/` as `.claude/`.** This plan predates the rename. The `.openclaude` → `.claude` compatibility symlink has since been removed, so paths and commands written here fail as typed. The text is left as approved rather than corrected, because a plan records what was agreed to, not what the tree looks like now.

## Context

The `repo-builder` skill offers repository addons — the public-repository files
held back from generation (`README.md`, `LICENSE`, `SECURITY.md`, `CODEOWNERS`,
the two pairs, and the rest in `apps/github-repository-template/src/repository-addons/`)
— **only during generation**. A repository already carrying `.repo-template.json`
has no supported way to adopt a held-back addon after the fact. The user wants the
skill to walk them through adopting an addon into an already-generated repo, ending
in a pull request.

The prerequisite is already shipped: PR #20 factored the adoption walkthrough out of
Generate step 2 into a reusable `## Addon adoption` section in `references/lifecycle.md`,
so a second flow can now reference it by name. This plan adds that second flow.

Two design decisions are settled with the user:

- **Preflight:** add an `adopt` subcommand to `preflight.py` (deterministic gate,
  consistent with generate/update), not agent-by-hand validation.
- **Source commit:** copy the addon from the `.repo-template.json` recorded commit
  only. Adopt never moves the template pin; to get a newer addon, run update first.

## Operation semantics

`adopt` = destination already has `.repo-template.json` (like update), but instead of
advancing the pin to carry a managed-file delta, it adds a sibling repository-addon at
the **recorded** commit. It does **not** advance `template.commit` and does **not**
record the adopted addon in the manifest — consistent with generate, and safe because
the Ownership section already treats a later-seen adopted file as destination-added,
not as a template deletion.

## Changes (5 files)

### 1. `.openclaude/skills/repo-builder/scripts/preflight.py` — new `adopt` subcommand
Mirror `update_preflight()` but drop target/ancestry/delta. Args:
`adopt --destination <path> --template <repo> --addon <path> [--addon ...]`.
Reuse existing helpers: `require_git_repository`, `ensure_clean`, `validate_manifest`,
`repository_identity`/`origin_identity`/`normalize_repository_identity`,
`resolve_commit`, `classify_path`.
Validations:
1. Clean destination worktree; manifest present and schema-valid.
2. Destination identity matches manifest `destination.repository`.
3. Resolve the manifest's recorded commit in `--template`; verify
   `src/repository-addons/<addon>` blob exists there and `src/addon-adoption.json`
   has a `files` entry for it (new helper `require_addon(repo, commit, addon)`).
4. **Pair completeness:** `CONTRIBUTORS.md`⇄`.all-contributorsrc` and
   `CHANGELOG.md`⇄`.openclaude/rules/changelog.md` must be adopted together — fail
   if only one half is requested.
5. **Not already present:** fail if the addon path already exists in the destination.
Emit JSON shaped like update's, with `operation: "adopt"`, `template` (repository,
subtree, recorded_commit), `destination`, and an `addons[]` array carrying each
addon's ownership (`classify_path`), `already_present: false`, and its inline
`addon-adoption.json` entry (slots/reviews/external or `authored_on_adoption`).
`remote_actions_performed: false`.

### 2. `.openclaude/skills/repo-builder/evals/setup_fixture.py` — `adopt` fixture
Add `build_adopt(root)` and an `"adopt"` scenario key. Seed the fixture **template**
repo's recorded commit with `src/repository-addons/` (a couple of real addon files
incl. one pair) and a minimal `src/addon-adoption.json`; seed the **destination**
with a valid manifest pinned at that commit and no addon yet. This is the fiddliest
part — the existing harness payloads only `base-repo/`, so addons + manifest are new.

### 3. `.openclaude/skills/repo-builder/scripts/tests/test_preflight.py` — adopt tests
Mirror the existing subprocess-against-fixture style: one happy path (JSON carries the
addon's adoption entry, destination untouched) and one negative (half a pair, or dirty
worktree via a reused helper). Keep proportional to existing coverage.

### 4. `.openclaude/skills/repo-builder/references/lifecycle.md` — `## Adopt` flow
New section after `## Update`, before `## Remote action gates`. Numbered steps mirror
update:
1. Confirm `.repo-template.json` present (else it is a generate); clean worktree;
   identify origin/default branch.
2. Run `preflight.py adopt …`; retain JSON.
3. Copy each addon from the recorded commit (from `repository-addons/`, sibling of the
   subtree) into the candidate; enforce the two pairs.
4. Run the **`## Addon adoption`** walkthrough for each addon — the reuse Gap 1
   enabled: ask each `value_key` once, fill slots, surface reviews, list external,
   handle `authored_on_adoption`, report done/OUTSTANDING.
5. State that `template.commit` is not advanced and the addon is not recorded, with the
   one-line reason (Ownership handles a later update).
6. Stage candidate; run destination checks (pass | no-checks | unavailable | never-ran).
7. Feature branch, commit the bounded diff (only adopted addon paths), remote gate,
   push, open PR — never merge.
8. Verify PR base/head, that only addon paths changed, checks, preserved product.
Also: add `- [Adopt](#adopt)` to the Contents list; extend the Final report
`Operation:` enum to `generate | update | adopt | stopped` and note that on an adopt
the Template line shows the recorded commit unchanged and the Addon adoption block
carries the weight.

### 5. `.openclaude/skills/repo-builder/SKILL.md` — expose the operation
Add an **Adopt** bullet to `## Choose the operation` (destination has the manifest and
the request is to add a held-back addon, not carry a template delta; read from the
recorded commit, do not advance it) and one line disambiguating it from Update. Add an
`adopt` bullet to `## Preflight before editing`. Extend the report skeleton's
`Operation:` enum to include `adopt`.

## Scope notes

- **Single-tree:** `.openclaude/skills/` is product and ships empty in the payload, so
  every edit is root-only — no payload mirroring.
- **No manifest schema change:** adopt records nothing new in `.repo-template.json`.
- `apps/github-repository-template/docs/github_repository_structure.md` (the addon
  bill-of-materials) is unchanged — adopt adds a flow, not an addon.
- An `evals/evals.json` entry for adopt is an optional follow-up, not required for the
  unit test to pass.

## Verification

1. `uv run --with pytest python -m pytest .openclaude/skills/repo-builder/scripts/tests/`
   — new adopt tests pass, existing 9 stay green.
2. Manually build the adopt fixture and run `preflight.py adopt …`; confirm the JSON
   carries the addon's adoption entry and a pair-completeness failure when half a pair
   is passed.
3. `scripts/check` — pre-commit clean, incl. the addon-adoption manifest hook and
   `check json`.
4. Independent `verification` subagent (5-file change): content, no broken anchors,
   tests, single-tree correctness.
5. Doc-contract closeout: skill self-documents via SKILL.md + lifecycle.md; confirm no
   parent `CLAUDE.md` needs updating.
