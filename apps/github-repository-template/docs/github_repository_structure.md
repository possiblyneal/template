---
type: Note
---
# GitHub Repository Structure

### GitHub Automation

`.github/workflows/ci.yml`: Runs tests, linting, formatting checks, type checks, and builds on every push and pull request.

`.github/workflows/release.yml`: Validates a tagged release and publishes it, both through `scripts/release`.

`.github/workflows/security.yml`: Runs dependency audits and, when a scanner is present, a secret scan.

`.github/workflows/codeql.yml`: Runs GitHub's CodeQL static analysis on pull requests, on `main`, and on a weekly schedule.

`.github/actions/setup-toolchains/`: Installs a toolchain for each language manifest present in the repository.

`zizmor.yml`: Configuration for zizmor, a GitHub Actions workflow security linter run through pre-commit.

`.github/dependabot.yml`: Opens one grouped weekly pull request updating pinned action versions in `.github/`.

`.github/ISSUE_TEMPLATE/`: Structured issue forms — `bug_report.yml`, `feature_request.yml`, and `config.yml` (disables blank issues).

`.github/PULL_REQUEST_TEMPLATE.md`: Structures a pull request description for review.

### AI Directives

The specific operating parameters for the AI agent.

`.claude/rules/`: Behavioral rules the AI follows — loaded at session start, or only when a matching file enters context if scoped with `paths:` frontmatter. Ships empty.

`.claude/skills/`: Reusable, multi-step prompts invocable by name as `/name`. Ships empty.

`.claude/output-styles/`: Templates controlling the format of the AI's output. Ships empty.

`.claude/agents/`: Specialized subagents with their own scoped context for isolated tasks.

`.claude/workflows/`: Scripts that orchestrate multiple subagents in sequence.

`.claude/agent-memory/`: Subagent persistent memory across sessions. Not shipped; created automatically on first use.

`.claude/hooks/`: Shell scripts wired to tool events by `.claude/settings.json`. Ships empty.

`.claude/settings.json`: Permission and tool configuration for this project. Ships with empty policy sections.

`.mcp.json`: Configures Model Context Protocol servers for this project. Ships empty.

`CLAUDE.md`: The project's system prompt — conventions, commands, and context the AI needs to operate.

`CLAUDE.local.md`: Personal, per-machine instructions loaded alongside `CLAUDE.md`, excluded by `.gitignore`. Not shipped.

### Source Code, Tests & Infrastructure

`apps/<name>/`: One deployable service or durable domain boundary, owning its own dependencies, tests, and specs.

`apps/<name>/src/`: Source code for that unit.

`apps/<name>/tests/`: Tests for that unit that don't touch other units.

`apps/<name>/docs/specs/`: Specs describing that unit's own behavior and acceptance criteria.

`libs/`: Shared internal libraries, schemas, and utilities used by apps.

`tests/`: Repo-level tests spanning multiple apps or libraries.

`scripts/`: Portable shell scripts, run locally or in CI, covering checks, releases, security audits, and branch protection.

`scripts/libs/`: Shared shell libraries used by the `scripts/` entry points.

`scripts/detect`: Reports which languages are present in the repository, for use by scripts and workflows.

`scripts/tests/`: Tests for the scripts themselves.

`scripts/release`: Validates a version tag against the changelog and cuts a GitHub release.

`tools/`: Convention (not a shipped directory) for helpers that must be built before they run, one directory per program.

`tmp/`: Git-ignored scratch space for temporary files, holding a `.gitkeep` so it survives being empty.

### Documentation & Knowledge Base

`TODO.md`: A plain-text backlog of informal tasks.

`docs/adrs/`: Architectural Decision Records — why past decisions were made.

`docs/specs/`: Specs for contracts spanning multiple apps.

`docs/LESSONS.md`: Repository-specific knowledge that prevents recurring mistakes.

`docs/plans/`: Plans written in plan mode, tracked so they land in the diff with the code they describe.

### Root Configuration Files

`.worktreeinclude`: Lists git-ignored files to copy into new Claude Code worktrees.

`.env`: Git-ignored file for local secrets and environment variables.

`.gitignore`: Specifies intentionally untracked files and directories.

`.gitattributes`: Git behavior for line endings, diffs, and language classification.

`.pre-commit-config.yaml`: Local checks that run automatically before a commit.

`.commitlintrc.yaml`: Commit message rules (Conventional Commits).

### Additions by Occasion

These live in `src/repository-addons/` and are never copied during generation — added by hand when the occasion arrives. `src/addon-adoption.json` lists what must be edited in each before it's safe to ship.

#### When someone else will use it

`README.md`: The public orientation page — what the project does, how to install it, and how to use it.

`CHANGELOG.md`: A per-version record of what changed, in Keep a Changelog format.

`.claude/rules/changelog.md`: Teaches the agent when a changelog entry is owed and how to write one, loading only when `CHANGELOG.md` enters context. Adopted together with `CHANGELOG.md` — one without the other is a defect, not a lighter choice.

`LICENSE`: The terms under which others may use, modify, and distribute the work. Ships as GNU GPL-3.0-or-later.

`SECURITY.md`: The private channel for reporting a vulnerability, and what to expect after.

`SUPPORT.md`: Routes users to help, separate from the issue tracker.

`.env.example`: A sanitized template of `.env` listing required variables without exposing secrets. Ships empty.

#### When someone else will contribute code

`CONTRIBUTING.md`: How a change reaches the default branch — reporting a bug, proposing an enhancement, and opening a pull request.

`CODE_OF_CONDUCT.md`: Baseline rules for community behavior. Ships as Contributor Covenant 3.0.

`CODEOWNERS`: Which accounts GitHub requests for review when a pull request touches a given path.

#### When the project outlives a single maintainer

`GOVERNANCE.md`: Who has final say, how routine decisions get made, and how disputes are resolved. Ships as a single-maintainer template.

`CONTRIBUTORS.md`: A public ledger crediting contributors, maintained by the All Contributors bot.

`.all-contributorsrc`: The All Contributors bot's configuration and contributor state.

#### When the work is academically valuable

`CITATION.cff`: Machine-readable citation metadata, which GitHub surfaces as a "Cite this repository" button. Root only.

#### When the project has gained traction

`.github/FUNDING.yml`: Displays a sponsor button on the repository. Read only from `.github/`.

#### When a helper needs to be built before it runs

`tools/`: Ships as an empty placeholder in `repository-addons/`, copied in only when the project needs a helper that must be built before it runs — a linter, a code generator, a protobuf plugin. Each gets its own `tools/<name>/` with its own manifest and source; a helper that's just a shell script belongs in `scripts/` instead.

### Written During Generation

Not part of the payload. `/repo-builder` writes these into the generated repository, so they appear in a generated tree and never in this inventory.

`docs/agents/`: Written by invoking `/setup-matt-pocock-skills`, which records where the repository tracks its issues, its triage label vocabulary, and its domain-doc layout. The engineering skills read it; `/wayfinder` reads `issue-tracker.md` to decide where a map lives.

### Program Language Metadata

These languages have built-in or universally accepted package managers, meaning they have strict, required root-level files and app-level files

#### Python

**Root-level:** `pyproject.toml` workspace config via uv

**App-level:** `pyproject.toml`

#### Go

**Root-level:** `go.work`: Go will automatically create the lockfile, `go.work.sum`

**App-level:** `go.mod`: Go will automatically create the lockfile, `go.sum`

#### Typescript

**Root-level:** `tsconfig.json`. Defines workspaces `package.json`

**App-level:** `tsconfig.json`. `package.json` extends root config

#### Rust

**Root-level:** `Cargo.toml` contains [workspace] Rust will automatically create the lockfile, `Cargo.lock`

**App-level:** `Cargo.toml` contains [package] Rust will automatically create the lockfile, `Cargo.lock`

#### Swift

**Root-level:** None. Swift Package Manager has no workspace manifest; multi-package repository support has been an open request since 2017, so no root file enumerates members or produces a shared lockfile. Apps reach each other with `.package(path: "../../libs/<name>")` instead. An `.xcworkspace` can group packages for Xcode, but it is an IDE convenience, not a build contract, and command-line builds ignore it.

**App-level:** `Package.swift`: Swift will automatically create the lockfile, `Package.resolved`. Because there is no workspace, every app resolves independently and versions can drift between apps; pin shared dependencies deliberately.

#### Kotlin

**Root-level:** `settings.gradle.kts` defines the workspace via `include(":app")`, and each path must match a real directory. `build.gradle.kts` shared plugin and config applied to subprojects. `gradle/libs.versions.toml` version catalog holding the single source of dependency versions. `gradle/wrapper/` and `gradlew` pin the Gradle version itself; commit them.

**App-level:** `build.gradle.kts`

Unlike the package managers above, Gradle writes no lockfile by default. Dependency locking is opt-in and produces `gradle.lockfile` per project only after it is enabled and written. Without it, builds are not reproducible across time.
