## Commands

Located at `./scripts` Use these instead of per-language tools; each detects the languages present and fails when an expected check cannot run. `./scripts/CLAUDE.md` documents all of them.

## Git

- Pre-commit blocks direct commits to `main` and `master`. Branch before making changes.
- Run `scripts/check` before committing. It runs the same checks CI does, plus pre-commit across every file rather than the staged ones.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/#specification).
- This repo adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
- Pull requests merge; they are neither squashed nor rebased.
- Plan mode writes to `docs/plans/`, which is tracked. A plan lands in the diff alongside the code it describes.

## Child Index

- `scripts/CLAUDE.md` — the language-capabilities interface, the result states, the test harness, and what adding a language or check requires

The rest of this project is not yet indexed. Before continuing you must read `~/.claude/rules/documentation.md`, scan the project, build the `CLAUDE.md` tree and replace this message with the actual child index, keeping the entry above. Go deep and scan files recursively to properly evaluate complexity and create nested `CLAUDE.md` files where needed. Do not create `CLAUDE.md` files in dot folders.
