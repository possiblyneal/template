# Addon adoption: ship Contributor Covenant 3.0, and make the skill walk every addon's fill-in regions

> **Historical record — read `.openclaude/` as `.claude/`.** This plan predates the rename. The `.openclaude` → `.claude` compatibility symlink has since been removed, so paths and commands written here fail as typed. The text is left as approved rather than corrected, because a plan records what was agreed to, not what the tree looks like now.

## Context

`src/repository-addons/CODE_OF_CONDUCT.md` is a 0-byte placeholder. Populating it is the request; the
Contributor Covenant is genuinely standard copy, so unlike `CONTRIBUTING.md` or `GOVERNANCE.md` there is a
correct text to ship.

The larger problem surfaced while sizing that edit. Every populated addon carries regions someone must edit
before the file is safe to ship, and today that knowledge is recorded five different ways in three different
places:

| File | Marker | Guidance lives |
|---|---|---|
| `CITATION.cff` | `REPLACE-PROJECT-TITLE`, `REPO-OWNER/REPO-NAME`; `license:` ships commented out | inside, 22-line header |
| `.all-contributorsrc` | `"projectOwner": "REPO-OWNER"` | **outside only**, structure doc |
| `CHANGELOG.md` | `<owner>/<repo>` + an HTML note to delete | inside |
| `CONTRIBUTORS.md` | load-bearing `<!-- ALL-CONTRIBUTORS-LIST:START -->` | inside |
| `LICENSE` | GPL appendix `<year>  <name of author>` — verbatim GPL, not ours to re-mark | outside only |
| `.github/FUNDING.yml` | prose comments, no tokens | inside |
| 7 files | 0 bytes | structure doc |

So the skill cannot walk an operator through adoption, because nothing enumerates the regions. `lifecycle.md`
step 2 knows which addons travel in **pairs** but nothing about what is *inside* them. Adding a Code of Conduct
with an unfilled reporting contact makes this concrete and costly: the document renders perfectly and silently
promises a reporting channel that does not exist.

Intended outcome: one machine-readable index of adoption regions, a check that keeps it honest, and a
`lifecycle.md` step that turns it into a walkthrough — covering every addon, not just the new file.

## Decisions taken

- **Ship CC 3.0, not 2.1.** Current stable since July 2025; 2.1 is no longer what the stewards point adopters at.
- **Keep upstream's visible `[NOTE: ...]` markers.** They render in the published document, so an unadopted CoC
  announces itself. That is strictly better than a silent `REPLACE-` token, and it is the exact failure
  `CITATION.cff`'s header warns about. Do not normalize them.
- **Do not normalize in-file tokens generally.** The manifest indexes them; the literals stay. Adopted files get
  copied into repositories that will never have the manifest, so in-file guidance still serves the human reading
  it eighteen months later. Two audiences, two artifacts.
- **Manifest lives at `src/addon-adoption.json`** — a sibling of `base-repo/` and `repository-addons/`. Not
  inside `repository-addons/`, where it would look like an addon to copy. Not in the skill, so a new addon and
  its entry land in one directory in one commit.
- **Root-only change.** Generated repositories have no `repository-addons/`, so the manifest and its hook must
  *not* be mirrored into the payload. This is a deliberate exception to the usual payload/root symmetry.

## Files

### 1. `apps/github-repository-template/src/repository-addons/CODE_OF_CONDUCT.md` (new)

Contributor Covenant 3.0 verbatim from
`https://raw.githubusercontent.com/ethicalsource/contributor_covenant/main/content/version/3/0/code_of_conduct.md`.
Fetch at implementation; do not reconstruct from memory. Strip Jekyll front matter if present. Retain the
Attribution section — CC BY-SA 4.0 requires it. Keep both bracketed NOTEs.

### 2. `apps/github-repository-template/src/addon-adoption.json` (new)

One entry per file under `repository-addons/`. Three region kinds, because they demand different things of a
person:

```json
{
  "CODE_OF_CONDUCT.md": {
    "slots": [
      { "token": "[NOTE: describe your means of reporting here.]",
        "value_key": "conduct-contact",
        "what": "The reporting channel. Renders visibly until replaced, and until then the document promises a channel that does not exist." }
    ],
    "reviews": [
      { "section": "Addressing and Repairing Harm",
        "decision": "Upstream ships suggested remedies and invites replacement. Confirm they match how this project actually responds, or rewrite them." }
    ],
    "external": []
  },
  "CONTRIBUTORS.md": {
    "slots": [],
    "reviews": [],
    "external": [
      { "step": "Install the All Contributors app from https://github.com/apps/allcontributors",
        "consequence": "Without it the marker comments do nothing and nothing reports that." }
    ]
  }
}
```

- `slots` — replace a token with a value. `value_key` groups the same answer across files: the repository owner
  is spelled `REPO-OWNER` in `CITATION.cff`, `"projectOwner"` in `.all-contributorsrc`, and `<owner>` in
  `CHANGELOG.md`. Without it the walkthrough asks one question three times in three vocabularies.
- `reviews` — read a section and decide. No token to grep for.
- `external` — steps outside the repository, each with the consequence of skipping it.
- Files shipping empty carry `"authored_on_adoption": true` and empty region lists.

Does **not** duplicate occasion (structure doc) or pairs (`lifecycle.md`); both are well covered there.

### 3. `.openclaude/skills/repo-builder/scripts/tests/test_addon_adoption.py` (new)

Bidirectional completeness: every file under `repository-addons/` (recursive, excluding `.gitkeep`) has an
entry, and every entry names a file that exists. Also asserts each declared `slots` token is actually present
in its file — that catches an entry describing a token that was edited away.

Constraints, both load-bearing:
- **stdlib only** (`json`, `pathlib`, `unittest`). It must run under the documented
  `uv run --with pytest python -m pytest .openclaude/skills/repo-builder/scripts/tests/` *and* standalone in
  the hook with no dependency resolution. A pytest-only idiom added later breaks the hook silently. Say so in
  the module docstring.
- Executable, `#!/usr/bin/env python3` shebang, `unittest.main()` under `__main__`, so `language: script` works.

Region-level completeness is *not* checked, and the reason belongs in a comment: `CONTRIBUTORS.md` contains the
literal strings `REPO-OWNER` and `ALL-CONTRIBUTORS-LIST:START` inside prose *describing* them, so a
"scan for unregistered placeholder-shaped tokens" check fires on documentation about tokens. File granularity
is the honest ceiling.

### 4. `.pre-commit-config.yaml` (edit)

New local hook mirroring `adr-index` (lines 43-61) line for line, including its reasoning:

```yaml
  - repo: local
    hooks:
      - id: addon-adoption
        name: check the addon adoption manifest covers every addon
        entry: .openclaude/skills/repo-builder/scripts/tests/test_addon_adoption.py
        language: script
        always_run: true
        pass_filenames: false
```

`always_run` with no `files:` filter for the documented reason: pre-commit's staged-file list excludes
deletions, and `git rm` of an addon is exactly when the manifest goes stale. `check-json` (line 92) carries no
`exclude`, so the manifest gets syntax validation free.

### 5. `.openclaude/skills/repo-builder/references/lifecycle.md` (edit, step 2 ~line 101)

After the existing paragraph on pairs: adopting an addon is not finished when the file is copied. Read its entry
in `src/addon-adoption.json`, fill every slot, put every review and external step to the operator, and carry
what remains into the handover. Group slots by `value_key` and ask once. An addon copied with slots unfilled is
a defect, not a lighter choice — the same standard step 2 already applies to half a pair.

Add an `### Addon adoption` section to the report block (lifecycle.md and the mirrored block in `SKILL.md`):
addons taken, slots filled, and regions left outstanding. Outstanding is a legitimate outcome; silent is not.

### 6. `apps/github-repository-template/docs/github_repository_structure.md` (edit)

- `CODE_OF_CONDUCT.md` entry (~line 179): note it now ships CC 3.0 and why the visible NOTEs are kept.
- Move actionable fill-in steps for `.all-contributorsrc` (~lines 191-195) to the manifest, leaving the
  reasoning. Only this file is deduplicated — it is never copied into a generated repository. **Leave in-file
  guidance in the addons themselves intact.**
- Name `src/addon-adoption.json` where the section introduces the addons.

### 7. `apps/github-repository-template/CLAUDE.md` (edit)

Ownership: add `src/addon-adoption.json`. Local Contracts: the manifest is root-only and must not be mirrored
into the payload. Verification: its "No checks run against the payload as source" claim becomes false — one now
does.

## Verification

1. `uv run --with pytest python -m pytest .openclaude/skills/repo-builder/scripts/tests/` — new test passes
   alongside the existing 4.
2. Negative test, by hand and reverted: add a scratch file to `repository-addons/`, confirm the check fails
   naming it; delete an addon, confirm it fails on the orphaned entry. A check that has never been seen red is
   not known to work.
3. `.openclaude/skills/repo-builder/scripts/tests/test_addon_adoption.py` runs directly, exit 0.
4. `scripts/check` — full local gate.
5. Confirm `git show HEAD:...CODE_OF_CONDUCT.md | diff - <upstream fetch>` is empty, so the shipped text is
   byte-identical to upstream.

## Out of scope

- Giving *this* repository a `CODE_OF_CONDUCT.md`. Its occasion — a second contributor — has not obviously
  arrived, and the structure doc's own reasoning applies. Flag it, do not do it.
- Writing *content* for the other 6 empty addons (`README.md`, `SECURITY.md`, `GOVERNANCE.md`,
  `CONTRIBUTING.md`, `CODEOWNERS`, `.env.example`). They still get manifest entries — every addon does, which is
  what the completeness check enforces — but they keep shipping empty.

## Resolved: the plan-location premise was wrong, and nothing needs changing

This section originally claimed root `CLAUDE.md` line 37 — "Plan mode writes to `docs/plans/`, which is
tracked" — was false, because plan mode wrote this document to `~/.openclaude/plans/` instead. The inference was
wrong. It is corrected here rather than deleted, because the wrong version is what was approved.

What is actually true:

- `plansDirectory` is a real, supported `settings.json` key, and it is **already set correctly** to
  `./docs/plans` at `.openclaude/settings.json:60`.
- It has worked before: `docs/plans/eager-prancing-peacock.md` and `ticklish-crafting-fairy.md` have been
  tracked since `f4096ee`.
- `docs/CLAUDE.md` documents it twice — under Ownership, and as a Local Contract noting `plans/` is tracked
  "unlike the `~/.openclaude/plans` default."
- `.openclaude/settings.local.json` was ruled out as an override; it carries `permissions` only.

So line 37 describes real, configured, previously-working behavior. **Do not reword it, and change no
settings.** Both edits this section originally called for would have made the repository worse — one of them by
writing a guessed key into a settings file that is rejected whole when invalid.

The harness ignored a correctly-set project-scope `plansDirectory` for this one session. That is an anomaly, not
a misconfiguration, and no repository file can assert against it. The only action taken was copying this plan
into `docs/plans/` by hand.

A `PostToolUse` hook on `ExitPlanMode` was considered and rejected on evidence: no hook event fires on plan
write or plan-mode exit, and `PostToolUse` receives only `tool_name`, `tool_input`, and `tool_use_id` — never
the plan path. A hook would have to guess the newest file in the plans directory, which is exactly the
silent-failure shape `.openclaude/CLAUDE.md` warns against.
