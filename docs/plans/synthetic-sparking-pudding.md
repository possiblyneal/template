# Plan: ship `README.md` as a rich scaffold addon

> **Historical record — read `.openclaude/` as `.claude/`.** This plan predates the rename. The `.openclaude` → `.claude` compatibility symlink has since been removed, so paths and commands written here fail as typed. The text is left as approved rather than corrected, because a plan records what was agreed to, not what the tree looks like now.

## Context

`README.md` currently ships empty, flagged `authored_on_adoption: true` in
`src/addon-adoption.json`. That flag says the template knows nothing worth
shipping and the operator writes the file from scratch. For a README that is the
wrong call, and it is the same call we already reversed for `SECURITY.md`,
`CODE_OF_CONDUCT.md`, `GOVERNANCE.md`, and `CONTRIBUTING.md`.

A README is ~100% project-specific in its *content*, but its *shape* is one of
the most standardized documents in open source — the section order, the header
block, the badge row, the install/usage split are near-universal (RichardLitt's
`standard-readme`, 6.3k★, is the canonical ordering; makeareadme.com and
GitHub's own "About READMEs" agree). An operator handed a blank file re-derives
that structure every time and usually gets it thinner than the references the
user pointed at (orca, notecharts, electron-markdownify).

The failure mode a scaffold has to avoid — shipping a plausible-looking lie that
renders as fact — is *loud* for a README, not silent. An unfilled title renders
as a giant placeholder; a missing image renders as a broken-image icon; a badge
pointing at nothing renders red. That loudness is exactly the "fail loudly in a
generated repository" property the payload wants, and it is why a scaffold is
correct here where it was rejected for a credit ledger (`CONTRIBUTORS.md`, whose
wrong content renders as dead links that look fine). So `README.md` moves from
`authored_on_adoption` to a scaffold with visible slots, judgement reviews, and
external image steps — the established three-file addon change.

The intended outcome: a generated repository that adopts the README gets a
structure matching the best examples, a full palette of Markdown elements to
adapt, and placeholders loud enough that an unfinished one cannot pass for done.

## Approach

A **scaffold**, not mostly-true prose. It ships the structure and the widest
reasonable Markdown palette with visible placeholder tokens, because unlike
`SECURITY.md`/`GOVERNANCE.md` (whose prose is largely true sight-unseen) nearly
every line of README *content* is project-specific. Placeholders are visible
`[REPLACE: ...]` brackets, matching the token-style rule already applied to
`SECURITY.md`/`GOVERNANCE.md`/`CODE_OF_CONDUCT.md`: silent `REPLACE-` tokens only
where GitHub validates the file, visible brackets where it renders to humans and
nothing validates — which is a README exactly.

### File 1 — create `src/repository-addons/README.md`

Section order (from `standard-readme` + the three reference READMEs):

1. **Centered header** — `<div align="center">` wrapping: logo `<img src="docs/assets/logo.svg">`, `# [REPLACE: project name]` as H1, an italic one-line `[REPLACE: one-line tagline]`, a **badge row** (build / license / version shields.io badges), and a **nav line** with `•` separators (`About • Features • Install • Usage • Contributing • License`). The user's rule: lead with logo + name; only spell the name in text if the logo doesn't already carry it — the H1 covers that.
2. **Hero image** — a full-width `<img src="docs/assets/hero.png">` (the user's "desktop background with the app window inside it" shot), wrapped in the centered div.
3. **About** — the long description: what it does, who it's for, why it exists. A `> [!NOTE]` alert for a one-line "what makes this different."
4. **Table of contents** — a bulleted list of anchor links (GitHub auto-anchors headings; the list must track the headings actually kept).
5. **Features** — per-feature `###` subsections with a screenshot each (orca's shape), plus a compact feature **table** (notecharts' shape) to exercise a table element.
6. **Installation** — per-platform fenced `bash` blocks; a `<details><summary>` collapsible for "build from source."
7. **Usage** — fenced example(s), a `> [!IMPORTANT]` alert, and `<kbd>` key hints for a keyboard-driven app.
8. **Roadmap** — a `- [ ]` task list.
9. **Contributing** — short prose linking `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`.
10. **Security** — one line linking `SECURITY.md`.
11. **License** — one line linking `LICENSE`, with an SPDX mention.
12. **Acknowledgements** — link bullets (electron-markdownify's Credits), and a footnote `[^1]`.
13. **Footer** — centered, a `---` rule then a small "built by [REPLACE: ...]" line.

Markdown palette deliberately exercised (user: "very good READMEs use almost all
of the different elements"): `<div align="center">`, `<img>`, H1–H4, italic/bold,
shields.io badges, clickable image-link `[![alt](img)](url)`, nav with `•`,
`> [!NOTE]`/`> [!IMPORTANT]` alerts, blockquote, fenced code, a table, task list,
`<details>`/`<summary>`, `<kbd>`, nested list, `---` rules, emoji, footnote,
relative image paths. Each `[REPLACE: ...]` slot is mirrored by an invisible
`<!-- ADOPT: ... -->` comment, the same convention every other addon uses so a
hand-adopter with no manifest still sees the judgement.

Slots in the file (visible brackets):
- `[REPLACE: project name]` → value_key `project-title` (shared with CONTRIBUTING/CITATION)
- `[REPLACE: one-line tagline]` → **new** value_key `project-tagline`
- badge/link URLs use `[REPLACE: owner]` and `[REPLACE: repo]` → value_keys `repo-owner`, `repo-name`

### File 2 — edit `src/addon-adoption.json`

- Remove `README.md` from the `authored_on_adoption` pair on line 12 (leaving only `.env.example`).
- Add a full `README.md` entry with:
  - **slots**: `project-title` (note: shared answer, renders huge so it announces itself), `project-tagline` (new value_key, one line under the title), `repo-owner` + `repo-name` (badge/clone/link URLs; a wrong value gives dead links, an empty one a broken badge).
  - **reviews** (judgement, no token):
    - the logo + hero images — keep visuals or cut the header/hero blocks entirely; a referenced-but-absent image renders as a broken icon (paired with the external step).
    - the badge row — keep only badges backed by something real; a build badge for a workflow that doesn't exist, or a hardcoded version, renders as fact and is a silent lie of the kind this file exists to prevent.
    - the Features / About / Usage content — replace placeholder bullets and examples with the project's real ones; the shipped text is scaffold, not truth.
    - the Installation/Usage command blocks — stack-specific, and (like CONTRIBUTING's setup section) they do not exist until the repo's first language manifest does; fill them when it lands.
    - the Contributing / Security / License links — each valid only if that addon was adopted; keep the link and drop it otherwise, so the README does not point at a file that is not there.
    - the table of contents — must track the headings actually kept; renaming or cutting a section leaves a dead anchor.
  - **external**: add `docs/assets/logo.<ext>` and `docs/assets/hero.<ext>` (or delete their references) — GitHub renders relative image paths from the repo, so until the files are committed the header shows broken icons; nothing else reports them missing.

### File 3 — edit `docs/github_repository_structure.md`

- Line 149: drop `README.md` from the authored-empty list (leaving `.env.example` only).
- Line 155: replace the one-line README description with a fuller writeup in the
  shape of the `SECURITY.md`/`GOVERNANCE.md` entries below it: it now ships as a
  scaffold rather than empty; why a scaffold and not mostly-true prose (README
  content is almost entirely project-specific, its structure almost entirely
  standard); why a scaffold and not authored-on-adoption (its failure modes are
  loud — placeholder title, broken image, red badge — the fail-loudly property
  the payload wants, unlike the credit ledger beside it whose wrong content
  renders clean); the slots it carries and the reviews/external steps the
  manifest lists; that it uses a wide Markdown palette on purpose.

## Critical files

- `apps/github-repository-template/src/repository-addons/README.md` (create)
- `apps/github-repository-template/src/addon-adoption.json` (edit: line 12 + new entry)
- `apps/github-repository-template/docs/github_repository_structure.md` (edit: line 149 + line 155)

## Reuse

- Token-style rule and the visible-`[REPLACE: ...]` + invisible-`<!-- ADOPT: -->`
  pairing from `SECURITY.md`/`GOVERNANCE.md`/`CODE_OF_CONDUCT.md`.
- Conditional-link review wording from CONTRIBUTING's Code-of-Conduct/security
  reviews and GOVERNANCE's CoC review.
- Stack-specific-until-a-manifest-exists review wording from CONTRIBUTING's
  "Setting up your environment" review.
- value_keys already defined: `project-title`, `repo-owner`, `repo-name`. Only
  `project-tagline` is new.

## Verification

1. Addon-adoption tests (they enforce: every addon has an entry, every entry
   names a real file, every declared slot token is present verbatim in its file,
   and no `authored_on_adoption` file ships content):
   `uv run --with pytest python -m pytest .openclaude/skills/repo-builder/scripts/tests/test_addon_adoption.py -q`
   — expect the previously-failing-if-empty README to now pass as a slotted
   entry, and `test_authored_on_adoption_files_ship_empty` to still pass (README
   no longer in that set).
2. Adversarial probe: temporarily corrupt one declared README token in the file
   and confirm `test_declared_slot_tokens_are_present_in_their_file` fails — proves
   the check is non-vacuous — then restore.
3. `scripts/check json` (or the addon-adoption pre-commit hook) validates
   `settings.json`/JSON; confirm `src/addon-adoption.json` still parses.
4. Render check: paste the scaffold into a GitHub Markdown preview (or a local
   renderer) to confirm every element renders and the placeholder tokens are
   visibly loud, not silently absorbed.
5. Structure-doc/payload agreement: confirm line 149 and line 155 match the new
   manifest state (the repo's own rule — when the structure doc and payload
   disagree, one is wrong).
6. Run the `verification` subagent on the completed three-file change before
   reporting done (payload change, ≥3 files).

## Not in scope / do not do

- Do not add real image files to the payload; `docs/assets/` is the adopter's
  external step, not the template's.
- Do not commit. SECURITY.md + GOVERNANCE.md are already staged-but-uncommitted
  from prior work; the README joins them, and all three wait for explicit user
  confirmation before any branch/commit/PR.
