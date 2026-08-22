## Commands

Located at `./scripts` Use these instead of per-language tools; each detects the languages present and fails when an expected check cannot run.

## Git

- Pre-commit blocks direct commits to `main` and `master`. Branch before making changes.
- Run `scripts/check` before committing. It runs the same checks CI does, plus pre-commit across every file rather than the staged ones.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/latest/).
- This repo adheres to [Semantic Versioning](https://semver.org/).
- Pull requests merge; they are not squashed.

## Apps

An `apps/` entry is one deployable service or one durable domain boundary, the unit that owns its own dependencies, tests, and specs.

`apps/app-name/` is a placeholder, not a real unit. Right before writing any code into it and not sooner, name it appropriately. Offer the user the name you would pick from what the repository already shows. Entries must be kebab-case. Delete this paragraph once no placeholder remains.

## Child Index

This project is not yet indexed. Before continuing you must read `~/.claude/rules/documentation.md` scan the project, build the `CLAUDE.md` tree and replace this message with the actual child index. Go deep and scan files recursively to properly evaluate complexity and create nested `CLAUDE.md` files where needed.
