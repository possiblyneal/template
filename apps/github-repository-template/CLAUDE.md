# GitHub Repository Template

## Purpose

Owns the payload copied into every repository generated from this template, and the reference documentation explaining why the payload is shaped the way it is.

## Ownership

- `src/base-repo/` — the payload. Every file here is destined for other repositories.
- `src/repository-addons/` — files held back from the payload because each answers a condition the template cannot know has arrived. Not copied during generation; added by hand when the occasion does arrive. `docs/github_repository_structure.md` groups them under "Additions by Occasion" and names the condition for each.
- `src/addon-adoption.json` — which regions of each addon must be edited before that addon is safe to ship: `slots` (a token to replace), `reviews` (a section demanding a judgement, with no token to grep for), `external` (a step outside the repository). Read by the `repo-builder` skill's Addon adoption walkthrough in `.claude/skills/repo-builder/references/lifecycle.md`.
- `docs/github_repository_structure.md` — Structure and bill of materials for this repo, and briefly what each file/folder is for.

The `repo-builder` skill reads `src/base-repo` at a specific commit, never the working tree, so an uncommitted payload edit does not reach a generated repository.

## Local Contracts

**A file under `src/base-repo/` is not this repository's configuration. It is data.** `src/base-repo/scripts/check` never runs here; the root `scripts/check` does.

**Payload and root are separate edits.** When a change should apply to both, make it in both places in the same commit. A fix at the root only leaves the template shipping the bug to every repository generated afterward.

**Dependabot only ever bumps the root.** `.github/dependabot.yml` scans `/` and `/.github/actions/*`, and nothing it lists reaches `apps/`, so a bot pull request bumping a pinned action updates the root copy and leaves the payload pinned to the old revision. Mirror the bump into `src/base-repo/.github/` on the bot's own branch before merging it. Nothing reports the divergence afterward: both trees are valid YAML, both pass actionlint, and the stale pin only surfaces in a repository generated later.

**`src/addon-adoption.json` is root-only and stays that way**, the one deliberate exception to the rule above. It describes `src/repository-addons/`, which never reaches a generated repository, so mirroring it into the payload ships an index of files that are not there. It is also a sibling of that directory rather than a file inside it, because anything inside is an addon to copy. The in-file guidance carried by the addons themselves is not deduplicated against it: that guidance serves someone adopting a file by hand, in a repository that has no manifest to read.

**Payload paths lose the `src/base-repo/` prefix when generated**, so a relative reference written inside the payload must be relative to the generated repository's root, not to this one.

**Deliberate placeholders, not omissions:**

- `src/base-repo/apps/app-name/` is replaced during generation, and the payload says nothing about it. `.claude/skills/repo-builder/references/lifecycle.md` step 4 owns the rename: the placeholder is moved to the first derived deployable rather than copied, so it cannot survive generation.
- `src/base-repo/.env` is an intentionally empty tracked file giving a generated repository somewhere to put local variables. Do not add content. It is tracked only because the root `.gitignore` pattern does not reach into the payload; at a destination root the same pattern matches it, so it copies across like any other file and can never be committed there. A generated repository has it locally and a clone of that repository does not.
- `.mcp.json` and every `.claude/` subdirectory ship empty, so a new project sees the available surfaces without inheriting rules. Hooks, rules, output styles, and skills are personal tooling, not project configuration — an operator's own global `~/.claude` covers them instead of the payload vendoring copies. The whole `.claude/` tree is gitignored in a generated repository, so — like `.env` — it arrives in its working tree but not its history, and is force-tracked here to ship at all. `CLAUDE.md` is not gitignored there: it carries the repository's actual contract now, not a disposable shim, so it is committed like any other payload file, at the root and at every nested location.

**`.github/dependabot.yml` lists only actions and pre-commit**, and that is not an oversight. An entry naming a manifest the repository does not have fails with `dependency_file_not_found` rather than being skipped, and a template cannot know which ecosystem a clone will use — listing five guarantees four broken entries in every one. The file carries the entry to copy when a real manifest arrives.

**The payload is what is useful on day one.** `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CODEOWNERS`, and the rest are absent because each answers a condition the template cannot know has arrived — not because the baseline is private. The structure doc's "Additions by Occasion" groups them by that condition. Adding one to the payload asserts its condition holds for every generated repository, which is the test to apply before doing so.

## Work Guidance

Editing under `src/` prompts for approval, per `.claude/settings.json`. Treat that prompt as the question: is this a payload change or a root change?

A payload change ships to repositories that cannot be inspected from here, so prefer changes that fail loudly in a generated repository over changes that silently do nothing. The payload's scripts distinguish `pass`, `not-applicable`, `unavailable`, and `FAIL` for exactly that reason.

When the structure doc and the payload disagree, one of them is wrong — fix both in the same commit rather than leaving the rationale describing a file that no longer behaves that way.

## Verification

The root `scripts/check` runs shellcheck and actionlint over these files through pre-commit, which is syntax-level only.

One check reads this directory semantically: the `addon-adoption` pre-commit hook runs `.claude/skills/repo-builder/scripts/tests/test_addon_adoption.py`, which fails when `src/addon-adoption.json` and `src/repository-addons/` disagree about which files exist, when an entry declares a slot token no longer present in its file, or when a file flagged `authored_on_adoption` ships content. It runs on every commit rather than on a path filter, because `git rm` of an addon is the case a filter cannot see. It does not check that a described region is described *well* — only that it exists.

The payload's behavior is verified where it lands: by `src/base-repo/scripts/tests/*-test` once a repository is generated, and by the `repo-builder` evals under `.claude/skills/repo-builder/evals/`.

## Child Index

None. `src/base-repo/CLAUDE.md` is payload content addressed to a generated repository, not a child contract for this one.
