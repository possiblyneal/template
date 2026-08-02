---
type: Note
---

# GitHub Repository Structure — Summary

Rationale-stripped index of the template's files. For *why* each rule exists, see [`github_repository_structure.md`](./github_repository_structure.md); this file only says what is there.

## GitHub Automation

Workflows stay thin; portable logic lives in `tools/ci/`, provider-specific orchestration in `.github/workflows/`.

| Path | Purpose |
| --- | --- |
| `.github/workflows/ci.yml` | Tests, lint, format check, type check, build. One call to `tools/ci/ci`. |
| `.github/workflows/release.yml` | Publishes packages, tags, binaries, changelog. Wrapper plus release/package auth. |
| `.github/workflows/security.yml` | Dependency audit, plus secret scan when a scanner is present. Wrapper plus GitHub-native security actions. |
| `.github/workflows/codeql.yml` | CodeQL static analysis. No `tools/ci/` counterpart; runs on GitHub, reports to the Security tab. |
| `.github/actions/setup-toolchains/` | Composite action: detects language manifests, installs a toolchain for each. Used by `ci.yml` and `release.yml`. |

**`codeql.yml`**: a detect job builds the language matrix from present manifests. Swift runs on a macOS runner. The matrix always includes `actions`. Requires GitHub Advanced Security on private repositories.

**`.github/dependabot.yml`**: weekly grouped pull requests for two ecosystems.

- GitHub Actions in `.github/workflows/` and `.github/actions/`, listed via `directories`. Pinned to major tags; `astral-sh/setup-uv` pinned to an exact release.
- Pre-commit hook `rev`s in `.pre-commit-config.yaml`, pinned to exact tags.

**`.github/ISSUE_TEMPLATE/`**

- `bug_report.yml` — affected version (required), expected vs. actual, severity, frequency, repro steps, logs, regression history, environment, investigation hints, reporter safeguards.
- `feature_request.yml` — problem/user need, desired outcome, use cases, scope boundaries, acceptance criteria, open questions, supporting context.
- `config.yml` — blank issues disabled.

**`.github/PULL_REQUEST_TEMPLATE.md`**: verification (CI link or raw output), risk as yes/no questions (migrations, auth, secrets, public interfaces, dependencies, data loss), what was not verified, judgment calls to examine, scope.

## AI Directives

| Path | Purpose |
| --- | --- |
| `.claude/rules/` | Behavioral constraints and formatting requirements. `paths:` frontmatter scopes a rule to matching files; without it a rule loads at session start. Ships `documentation.md`, scoped to `*.md` and `**/*.md`. |
| `.claude/skills/` | Named multi-step prompts. Each `<name>/SKILL.md` is invocable as `/name`. No `.claude/commands/`. |
| `.claude/output-styles/` | Output format templates for code, logs, and documentation. |
| `.claude/agents/` | Subagents with their own scoped context windows. |
| `.claude/workflows/` | Scripts orchestrating multiple subagents in sequence. |
| `.claude/agent-memory/` | Subagent state across sessions, separate from main-session auto-memory. |
| `.claude/hooks/` | Three shell scripts wired to tool events. All parse input with `jq`. |
| `.mcp.json` | Project-scoped MCP servers. Shipped empty. |
| `CLAUDE.md` | Project system prompt. Ships Commands, Documentation, Child Index, and `# Compact instructions`. |
| `CLAUDE.local.md` | Per-machine instructions, git-ignored. Not shipped. |

**Hooks**

- `ask-outside-repo.sh` (`PreToolUse`) — prompts before `Edit`, `Write`, or `NotebookEdit` touches a path outside `CLAUDE_PROJECT_DIR`. Resolves symlinks and `..` first; asks when the root is unknown; allows writes under `CLAUDE_JOB_DIR`. Bash redirection is not covered.
- `block-config-change.sh` (`ConfigChange`) — blocks hot-reload of `.claude/settings.json`, `.claude/settings.local.json`, and `.claude/skills/`. The edit still lands on disk and applies next session. Omits `user_settings` and `policy_settings`.
- `session-start.sh` (`SessionStart`, on `startup`/`resume`/`clear`/`compact`) — prints branch, uncommitted changes, recent commits; restates read-before-edit and names the documentation rule file; runs `pre-commit install` when needed.

**`.claude/settings.json`** — populated: `hooks`, `permissions.ask`, `permissions.deny`, `plansDirectory`, `attribution`, `allowedHttpHookUrls`, `disableClaudeAiConnectors`, `$schema`. Shipped empty: `permissions.allow`, `permissions.additionalDirectories`, `env`, `sandbox`, `enabledPlugins`, `modelOverrides`, `skillOverrides`.

- Every hook entry sets `"args": []` (direct spawn, no shell).
- `allowedHttpHookUrls: []`, `disableClaudeAiConnectors: true`.
- `permissions.ask`: `git push`, `git reset --hard`, `git clean`, `git rebase`, and the `gh` commands that create or merge pull requests, cut releases, or delete the repository.
- `permissions.deny`: environment files (named individually, not `.env.*`), private keys, PKCS#12 bundles, service account files, `.npmrc`, `.pypirc`, Terraform state. Each path denied twice, once for `Read` and once for `Edit`.
- `attribution`: `commit: ""`, `pr: ""`, `sessionUrl: false`.
- Only restricting rules belong here. Omit — never blank — enum strings (`permissions.defaultMode`, `editorMode`), min-length strings (`outputStyle`, `apiKeyHelper`), objects with required sub-fields (`statusLine`, `policyHelper`), and `model`.

## Source Code, Tests & Infrastructure

| Path | Purpose |
| --- | --- |
| `apps/<domain or deployable service>/src/` | Source. Each deployable unit self-contained for its own dependencies. |
| `apps/<domain or deployable service>/tests/` | Tests confined to that domain or service. |
| `apps/<domain or deployable service>/docs/specs/` | That unit's behavior and acceptance criteria. Change in the same commit as the code. |
| `libs/` | Shared internal libraries, schemas, utilities. Need not be publishable. |
| `tests/` | Repo-level integration, end-to-end, contract, benchmark, shared fixtures. |
| `tools/scripts/` | `doctor`, `check`, `fix`, `clean`, `dev`. |
| `tools/ci/` | `ci`, `release`, `security`. Shell scripts, run locally and in Actions. |
| `tmp/` | Git-ignored scratch space. Holds `.gitkeep`. |

**`tools/scripts/`**

- `check` — runs `doctor`, `tools/ci/ci`, `tools/ci/security`, then pre-commit across every file. `no-commit-to-branch` skipped via `SKIP`.
- `fix` — write half of the `tools/ci/ci` format check: same formatters, same order. No lint autofixes.
- `clean` — searches `apps/<name>/` and `libs/<name>/` for build output. Skips `.git`, `node_modules`, `.build`.
- `doctor` — a toolchain per language `tools/ci/ci` runs, Swift and Kotlin included, plus the Gradle wrapper. Requires `jq` while `ask-outside-repo.sh` exists. Fails when `.pre-commit-config.yaml` is present but the tool or the `.git/hooks/` install is missing.

**`tools/ci/`**

- A check that never ran counts as a failure whenever it was expected. Manifest present, toolchain missing → the run fails.
- Manifest detection lists every supported language, `Package.swift`, `settings.gradle.kts`, and `build.gradle.kts` included.
- Swift is found by search, not at the root; the search skips `.build/`. Commands run once per package directory, and every package runs even after one fails.
- `security` — dependency audit, plus a secret scan only when a scanner is already installed. Installs no scanner. gitleaks runs from `.pre-commit-config.yaml`. No code scanning, license policy, or container image scanning.
- `release` — runs `tools/ci/ci` first, refuses to publish while packaging is unconfigured, and takes the tag from an explicit argument before `GITHUB_REF_NAME`, passed through the environment rather than `${{ }}`.
- Swift and Kotlin are audited through trivy against their lockfiles; no `gradle.lockfile` means no runner. Gradle lint and format run as `ktlintCheck` or `detekt` only when the task list shows them.

## Documentation & Knowledge Base

| Path | Purpose |
| --- | --- |
| `TODO.md` | Backlogged informal tasks. |
| `docs/adr/` | Architectural Decision Records, one repo-wide numbered sequence. An app may add its own; link it from this index and never reuse numbers. |
| `docs/specs/` | Contracts spanning apps: service-to-service APIs, shared schemas. |
| `docs/plans/` | Plan-mode output, via `plansDirectory` in `.claude/settings.json`. |

## Root Configuration Files

| Path | Purpose |
| --- | --- |
| `.worktreeinclude` | Git-ignored files to copy into new Claude worktrees. `.gitignore` syntax; copied only if both matched here and git-ignored. Local config only — no private keys or Terraform state. |
| `.env` | Git-ignored active environment variables. |
| `.gitignore` | Untracked paths. |
| `.gitattributes` | Line endings, diff drivers, Linguist classification. |
| `.pre-commit-config.yaml` | Local pre-commit guardrails. |

**`.gitignore`** covers local secrets (`.env`, keeping `.env.example`), private keys and credential files, Terraform state, scratch files, logs, OS/editor files, dependency folders, language caches and build output, container runtime state, local databases, and generated artifacts, while preserving `tmp/.gitkeep`. Also excludes `.claude/settings.local.json` and `CLAUDE.local.md`. Build output names that also occur in source trees are anchored (`/bin/`); names that nest legitimately (`node_modules/`, `coverage/`) are not.

**`.gitattributes`**: `* text=auto eol=lf` for everything, overridden only for Windows scripts (CRLF) and SVG (text). Markdown gets a heading-aware diff driver; language drivers name the enclosing function. Lockfiles carry `merge=binary` and `linguist-generated`. `docs/`, `generated/`, and `vendor/` are classified for language stats.

**`.pre-commit-config.yaml`** ships gitleaks plus hooks for merge conflict markers, oversized files, malformed YAML/JSON/TOML, private keys, submodules, case-insensitive path collisions, and line endings contradicting `.gitattributes`. Also shellcheck and actionlint, the two shebang hooks (`tools/` scripts are extensionless, so the executable bit decides whether shellcheck sees them), and `no-commit-to-branch` for `main` and `master`. Nothing runs until `pre-commit install`.

## Public / Open Source Additions

Only needed on a public repository accepting external contributions.

| Path | Purpose |
| --- | --- |
| `README.md` | What the project does, how to install, how to use. |
| `FUNDING.yml` | Sponsor button. |
| `CONTRIBUTING.md` | Pull requests, tests, code style. |
| `SECURITY.md` | Security policy, supported versions, private reporting channel. |
| `LICENSE` | Usage, modification, distribution rights. |
| `CODE_OF_CONDUCT.md` | Community behavior baseline. |
| `SUPPORT.md` | Routes help requests away from the issue tracker. |
| `CONTRIBUTORS.md` | Credit ledger. |
| `CODEOWNERS` | Write access and merge authority. |
| `GOVERNANCE.md` | Decisions, maintainer election, dispute resolution. |
| `.env.example` | Sanitized `.env` template. |

## Program Language Metadata

| Language | Root-level | App-level | Lockfile |
| --- | --- | --- | --- |
| Python | `pyproject.toml` (uv workspace) | `pyproject.toml` | — |
| Go | `go.work` | `go.mod` | `go.work.sum`, `go.sum` (automatic) |
| TypeScript | `tsconfig.json` (workspaces), `package.json` | `tsconfig.json`, `package.json` (extends root) | — |
| Rust | `Cargo.toml` (`[workspace]`) | `Cargo.toml` (`[package]`) | `Cargo.lock` (automatic) |
| Swift | None | `Package.swift` | `Package.resolved` (automatic, per package) |
| Kotlin | `settings.gradle.kts`, `build.gradle.kts`, `gradle/libs.versions.toml`, `gradle/wrapper/`, `gradlew` | `build.gradle.kts` | `gradle.lockfile` (opt-in only) |

**Swift**: SwiftPM has no workspace manifest, so there is no root file and no shared lockfile. Apps reach each other with `.package(path: "../../libs/<name>")`. An `.xcworkspace` is an IDE convenience; command-line builds ignore it. Every app resolves independently, so pin shared dependencies deliberately.

**Kotlin**: each `include(":app")` path must match a real directory, and the wrapper is committed. Dependency locking is opt-in; without it builds are not reproducible across time.
