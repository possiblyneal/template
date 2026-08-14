# GitHub Repository Template

## Purpose

Owns the payload copied into every repository generated from this template, and the reference documentation explaining why the payload is shaped the way it is.

## Ownership

- `src/base-repo/` — the payload. Every file here is destined for other repositories.
- `docs/github_repository_structure.md` — Structure and bill of materials for this repo, and briefly what each file/folder is for.
- `docs/choosing_a_language.md` — evidence on language choice for AI-assisted work.

The `repo-builder` skill reads `src/base-repo` at a specific commit, never the working tree, so an uncommitted payload edit does not reach a generated repository.

## Local Contracts

**A file under `src/base-repo/` is not this repository's configuration. It is data.** `src/base-repo/scripts/check` never runs here; the root `scripts/check` does.

**Payload and root are separate edits.** When a change should apply to both, make it in both places in the same commit. A fix at the root only leaves the template shipping the bug to every repository generated afterward.

**Payload paths lose the `src/base-repo/` prefix when generated**, so a relative reference written inside the payload must be relative to the generated repository's root, not to this one.

**Deliberate placeholders, not omissions:**

- `src/base-repo/apps/app-name/` is renamed during generation. The root `CLAUDE.md` of the payload carries the Placeholders section instructing that rename; a placeholder that only looks like a convention gets kept rather than replaced.
- `src/base-repo/.env` is an intentionally empty tracked file giving a generated repository somewhere to put local variables. Do not add content. It is tracked only because the root `.gitignore` pattern does not reach into the payload; at a destination root the same pattern matches it, so it copies across like any other file and can never be committed there. A generated repository has it locally and a clone of that repository does not.
- `.mcp.json` ships empty, and `.openclaude/` ships empty `agents/`, `output-styles/`, `skills/`, and `workflows/`, so a new project sees the available surfaces without inheriting rules.

**`.github/dependabot.yml` lists only actions and pre-commit**, and that is not an oversight. An entry naming a manifest the repository does not have fails with `dependency_file_not_found` rather than being skipped, and a template cannot know which ecosystem a clone will use — listing five guarantees four broken entries in every one. The file carries the entry to copy when a real manifest arrives.

**The payload is what is useful on day one.** `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CODEOWNERS`, and the rest are absent because each answers a condition the template cannot know has arrived — not because the baseline is private. The structure doc's "Additions by Occasion" groups them by that condition. Adding one to the payload asserts its condition holds for every generated repository, which is the test to apply before doing so.

## Work Guidance

Editing under `src/` prompts for approval, per `.openclaude/settings.json`. Treat that prompt as the question: is this a payload change or a root change?

A payload change ships to repositories that cannot be inspected from here, so prefer changes that fail loudly in a generated repository over changes that silently do nothing. The payload's scripts distinguish `pass`, `not-applicable`, `unavailable`, and `FAIL` for exactly that reason.

When the structure doc and the payload disagree, one of them is wrong — fix both in the same commit rather than leaving the rationale describing a file that no longer behaves that way.

## Verification

No checks run against the payload as source. The root `scripts/check` runs shellcheck and actionlint over these files through pre-commit, which is syntax-level only.

The payload's behavior is verified where it lands: by `src/base-repo/scripts/tests/*-test` once a repository is generated, and by the `repo-builder` evals under `.openclaude/skills/repo-builder/evals/`.

## Child Index

None. `src/base-repo/CLAUDE.md` is payload content addressed to a generated repository, not a child contract for this one.
