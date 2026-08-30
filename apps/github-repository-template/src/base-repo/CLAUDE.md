## Commands

Located at `./scripts` Use these instead of per-language tools; each detects the languages present and fails when an expected check cannot run.

- `scripts/structure` — audit where files sit against the Layout rules below; called by `scripts/check` and by pre-commit on every commit

## Layout

Where a new file goes. `scripts/structure` enforces everything here that is a question about placement, plus the values in a unit's declaration, and reports the three rules that are neither. Its failure messages point back at this section.

**Root holds only these, and everything at root is repo-wide in scope.** `libs/`, `tests/`, `scripts/`, `tools/`, `deploy/`, and `assets/` here hold only what is shared across apps or operates on the whole repository; anything scoped to one app belongs under that app.

`.claude/`, `.devcontainer/`, `.github/`, `apps/`, `assets/`, `deploy/`, `docs/`, `gradle/`, `libs/`, `scripts/`, `tests/`, `tmp/`, `tools/`.

Root *files* are permitted by name rather than by pattern: the eight this template ships, `.repo-template.json`, `.structure-allow`, `CONTEXT.md` and `CONTEXT-MAP.md`, every repository addon, and the root workspace manifests and lockfiles of the supported languages. `.gitkeep` is permitted anywhere. Anything else needs permission, recorded in `.structure-allow`.

**`apps/` breaks the project into its smallest deployable units.** There may be only one.

- Each unit is one folder under `apps/`: the smallest piece of this repository delivered on its own — deployed, installed, published, or copied. A file sitting directly in `apps/` belongs to no unit.
- Split a unit into domains only when it spans distinct business areas that benefit from isolation. Each domain is one folder under its unit.
- `src/` sits under the unit when there are no domains, and under each domain when there are. Never both, and never `apps/src/`.
- A unit or domain may hold its own `libs/`, `tests/`, `scripts/`, `docs/`, `tools/`, `deploy/`, or `assets/`, scoped strictly to it.

**Every unit declares how it runs and what it ships**, in a `.unit.json` at the unit's root — never at a domain's. Neither fact is on disk: a Go module with one `main` package is a CLI, a TUI, or a service, and the compiler cannot tell them apart.

```json
{ "schema_version": 1, "run": "oneshot", "ships": { "kind": "executable", "targets": ["linux-amd64"] } }
```

- `run` — `oneshot` for a process that exits on its own, `longlived` for one that runs until stopped, `none` for a unit with nothing to run.
- `ships.kind` — `executable`, `quadlet`, or `none`.
- `ships.targets` — required exactly when the kind is `executable`, rejected on every other kind: `linux-amd64`, `macos-arm64`.

The two facts vary independently, so every pairing is legal and the audit checks values alone. A scheduled job runs `oneshot` and ships a `quadlet`; a library runs `none` and still ships.

Reading the file needs `jq`, which is why `scripts/doctor` requires it once a unit declares. Without it the audit reports `unavailable` and fails rather than passing over a file it never opened.

**Scoped folders are leaves for their own kind.** `libs/`, `tests/`, `scripts/`, `tools/`, `assets/`, `docs/`, and `deploy/` may nest a different kind — `scripts/tests/libs/` is fine — but never another of the same kind at any depth, and never a `src/`.

**`apps/` is not a scope holder.** The scope holders are the root, a unit, and a domain, so the segment directly under `apps/` is a unit name and is never read as a scoped folder however it is spelled. `apps/docs/`, `apps/tests/`, `apps/scripts/`, and `apps/deploy/` are ordinary units. The rules resume at the unit: `apps/docs/docs/notes.yaml` still needs permission and `apps/api/docs/src/` is still a `src/` under a scope holder.

**Every rule that reads depth stops at the first `src/`.** Below one, the arrangement belongs to the language rather than to this repository: a Go package named `docs/`, a Python `scripts/` module, a generated or vendored tree whose shape nobody here chose. `apps/api/src/internal/docs/swagger.json` is fine; `apps/api/docs/swagger.json` is not.

**`deploy/` holds one folder per technology** — `quadlet/`, `containerfile/`, `compose/`, `systemd/`, `env/` — and no loose files beside them. It sits at the root or beside a unit's `src/`.

**`docs/` takes Markdown freely at every scope**; anything else needs permission.

**`.structure-allow` is where permission is recorded.** A bare path allows that one file. A path ending in `/` names a prefix the audit stops descending into, which is how a vendored dependency or a tracked test fixture keeps a shape that is not this repository's to decide.

Three rules are about content rather than placement and no script can settle them: whether `libs/` really holds what several apps share, whether `tests/` really spans them, and whether a file sits at the scope it belongs to. `scripts/structure` reports all three `not-applicable` rather than inferring them from paths.

## Git

- Pre-commit blocks direct commits to `main` and `master`. Branch before making changes.
- Run `scripts/check` before committing. It runs the same checks CI does, plus pre-commit across every file rather than the staged ones.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/#specification).
- This repo adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
- Pull requests merge; they are neither squashed nor rebased.

## Child Index

This project is not yet indexed. Before continuing you must read `~/.claude/rules/documentation.md`, scan the project, build the `CLAUDE.md` tree and replace this message with the actual child index. Go deep and scan files recursively to properly evaluate complexity and create nested `CLAUDE.md` files where needed. Do not create `CLAUDE.md` files in dot folders.
