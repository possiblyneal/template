## Commands

Located at `./scripts` Use these instead of per-language tools; each detects the languages present and fails when an expected check cannot run. `./scripts/CLAUDE.md` documents all of them.

## CI

Every job in `.github/workflows/` takes its runner from a `RUNNER` repository variable and falls back to `ubuntu-latest`, so this repository redirects its own CI with `gh variable set RUNNER --body self-hosted` rather than by editing a workflow the template owns. Leave it unset while the repository is public: a self-hosted runner there lets any fork's pull request run arbitrary code on the host. A machine named by `RUNNER` must carry what the hosted image gave for free — `git`, `gh`, `jq`, `pipx`, and every toolchain the languages present need. `pipx` is needed whatever the languages are, since `ci.yml` installs pre-commit with it before any toolchain is set up.

## Git

- Pre-commit blocks direct commits to `main` and `master`. Branch before making changes.

## Child Index

- `scripts/CLAUDE.md` — the language-capabilities interface, the result states, the test harness, and what adding a language or check requires

The rest of this project is not yet indexed. Before continuing you must read `~/.claude/rules/documentation.md`, scan the project, build the `CLAUDE.md` tree and replace this message with the actual child index as a bulleted list, keeping the entry above. Go deep and scan files recursively to properly evaluate complexity and create nested `CLAUDE.md` files where needed. Do not create `CLAUDE.md` files in dot folders.
