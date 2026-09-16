---
type: Note
---
# GitHub Repository Structure

### GitHub Automation

`.github/workflows/ci.yml`: Runs tests, linting, formatting checks, type checks, and builds on every push and pull request.

`.github/workflows/release.yml`: Validates a tagged release and publishes it, both through `scripts/release`.

`.github/workflows/security.yml`: Runs dependency audits and, when a scanner is present, a secret scan.

`.github/workflows/codeql.yml`: Runs GitHub's CodeQL static analysis on pull requests, on `main`, and on a weekly schedule. Its `init` step carries a commented-out `config-file:` line — uncomment it, and add the file it names, to scope which paths are analyzed or run a broader query suite than the default.

`.github/actions/setup-toolchains/action.yml`: Installs a toolchain for each language manifest present in the repository.

`.github/zizmor.yml`: Configuration for zizmor, a GitHub Actions workflow security linter run through pre-commit.

`.github/dependabot.yml`: Opens one grouped weekly pull request updating pinned action versions in `.github/`.

`.github/ISSUE_TEMPLATE/`: Structured issue forms — `bug_report.yml`, `feature_request.yml`, and `config.yml`, which disables blank issues and carries a commented-out `contact_links` block to uncomment once a destination for questions exists.

`.github/PULL_REQUEST_TEMPLATE.md`: Structures a pull request description for review. This is the one a pull request gets by default. It ships a commented-out line of links to the named templates under `.github/PULL_REQUEST_TEMPLATE/`, which are addons: nothing in GitHub's interface offers a named template, so uncommenting that line is what makes them reachable once the directory is adopted.

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

`CLAUDE.md`: The project's system prompt — conventions, commands, and context the AI needs to operate. Ships small: a pointer at `scripts/CLAUDE.md` for the commands, the branch rule, and a Child Index holding the instruction to scan the tree and build the rest of it. The Layout rules live in `scripts/structure` rather than here.

`CLAUDE.local.md`: Personal, per-machine instructions loaded alongside `CLAUDE.md`, excluded by `.gitignore`. Not shipped.

### Source Code, Tests & Infrastructure

`apps/<name>/`: One deployable service or durable domain boundary, owning its own dependencies, tests, and specs.

`apps/<name>/.unit.json`: How that unit runs and what it ships, as two independent facts — `run` (`oneshot`, `longlived`, `none`) and `ships` (`kind` of `executable`, `quadlet`, or `none`, carrying `targets` exactly when the kind is `executable`). Neither fact is detectable from the source, and `scripts/structure` requires the file on every unit and checks each value against a fixed enum. The skeleton ships `run: none, ships: none`, so adopting it is a value to change rather than a file to discover.

`apps/<name>/src/`: Source code for that unit.

`apps/<name>/tests/`: Convention (not a shipped directory) for tests of that unit that don't touch other units.

`apps/<name>/docs/specs/`: Convention (not a shipped directory) for specs describing that unit's own behavior and acceptance criteria.

`libs/`: Convention (not a shipped directory) for shared internal libraries, schemas, and utilities used by several apps. Definitionally empty until a second app exists to share them.

`tests/`: Convention (not a shipped directory) for repo-level tests spanning multiple apps or libraries. Definitionally empty until a second app exists to span.

`scripts/`: Portable shell scripts, run locally or in CI, covering checks, releases, security audits, and branch protection.

`scripts/CLAUDE.md`: The contract for `scripts/` — what each script is for, the four result states, the language-capabilities interface and its test harness, and what adding a language or a check requires. The root copy's counterpart, minus the one paragraph that only applies to the template.

`scripts/libs/`: Shared shell libraries used by the `scripts/` entry points.

`scripts/detect`: Reports which languages are present in the repository and which capability adapters are wired, for use by scripts and workflows.

`scripts/tests/`: Tests for the scripts themselves.

`scripts/summarize`: Runs a check command and prints only its Result table — one line per check, the findings under any that failed — dropping every other thing the command wrote. Exits with that command's status, so it can stand in for the command rather than only report on it. It is the one consumer of the printed layout `scripts/libs/result.sh` documents, which is where a change to the column widths has to be reflected.

`scripts/run`: Starts a unit, dispatching on the `run` fact its `.unit.json` declares — a one-shot runs the program's own entry point, a long-lived one runs the dev server, `none` exits saying there is nothing to run. Names the unit when `apps/` holds several, since a run is one foreground process; everything after `--` reaches the program unchanged.

`scripts/package`: Delivers what a unit declared it ships. For `executable`, builds one binary per declared target into that unit's `dist/`, reporting a target the toolchain cannot reach as `not-applicable` with the reason named. For `quadlet`, validates the unit's `deploy/quadlet/` pair instead — the `.build` names a Containerfile that exists, and the `.container`'s `Image=` is something that `.build` produces — and builds nothing, because systemd and podman build on the deploy host. It never invokes a container runtime, so the full gate still passes on a machine with none. For `none`, says so and exits. Nothing in the gate calls it — packaging is not a check.

`scripts/release`: Validates a version tag against the changelog, packages every unit under `apps/`, and cuts a GitHub release with whatever those units produced attached. Packaging runs before the tag, so a build that cannot be made publishes nothing; a repository where no unit ships a file still releases.

`scripts/structure`: Audits where files sit against the Layout rules in the root `CLAUDE.md` — the root folder and file allowlists, the `apps/` unit-and-domain shape, the closed folder vocabulary under a domain, `src/` placement, the leaf rule, and the Markdown-only rule for `docs/`. Called by `scripts/check` and by pre-commit on every commit. It reads the contents of exactly one file, a unit's `.unit.json`, whose whole purpose is to state what a tree cannot show; the three rules that turn on what any other file contains are reported `not-applicable` rather than guessed. Reading a declaration needs `jq`, and its absence is reported `unavailable` rather than passed over.

`scripts/github-parity`: Refuses a divergence between a repository's own `.github/` and the copy a template payload ships to generated repositories, reading both which paths exist and what each one holds from the Git index, since it runs at pre-commit and the index is the tree being committed. `dependabot.yml` is the one named content exception, since a payload copy must not carry an ecosystem entry for a manifest it does not ship; a payload file the root deliberately dropped is excused only where `generation.features` in `.repo-template.json` records the omission, which needs `jq` and is reported `unavailable` without it; a divergence the record cannot excuse is still named on a host without `jq`. Reports `not-applicable` in a repository with no payload, which is every repository generated from one. Called by `scripts/check` and by pre-commit on every commit.

`.structure-allow`: Convention (not a shipped file) for the permission the Layout rules refer to — one path per line to allow a named exception, a trailing `/` to stop the audit descending into a vendored or fixture tree, save for one lookup that keeps a prefix over a domain's `src/` from failing the domain it defines. Absent until a repository needs one.

`tools/`: Convention (not a shipped directory) for helpers that must be built before they run, one directory per program.

`deploy/`: Convention (not a shipped directory) for deployment definitions, holding only `compose/`, `containerfile/`, `env/`, `quadlet/`, and `systemd/`. Valid at the repository root and beside a unit's `src/`.

`assets/`: Convention (not a shipped directory) for static assets — images, fonts, fixtures — at the root or scoped to the unit that uses them.

`tmp/`: Git-ignored scratch space for temporary files, holding a `.gitkeep` so it survives being empty.

### Documentation & Knowledge Base

`docs/adrs/`: Architectural Decision Records — why past decisions were made.

`docs/specs/`: Convention (not a shipped directory) for specs of contracts spanning multiple apps. The shipped `docs/agents/issue-tracker.md` puts specs on the issue tracker instead, so a repository keeping them as files creates this directory itself.

`docs/LESSONS.md`: Repository-specific knowledge that prevents recurring mistakes.

`docs/plans/`: Plans written in plan mode, tracked so they land in the diff with the code they describe.

`docs/agents/`: How the engineering skills read the repository — `issue-tracker.md` names where issues live and how to work them, `triage-labels.md` the label vocabulary, `domain.md` the glossary and ADR layout. Shipped rather than collected, for the reasons `docs/adrs/0002-ship-agent-skill-configuration-in-the-payload.md` records; `apps/repo-builder/src/references/generate.md` step 6 confirms these files instead of running `/setup-matt-pocock-skills`, and creates the labels they name. Editable by hand afterwards. Reached through `CLAUDE.md`'s `## Agent skills` block rather than by path, which is why deleting that block silently disables all three.

### Root Configuration Files

`.worktreeinclude`: Lists git-ignored files to copy into new Claude Code worktrees.

`.env`: Git-ignored file for local secrets and environment variables.

`.gitignore`: Specifies intentionally untracked files and directories.

`.gitattributes`: Git behavior for line endings, diffs, and language classification.

`.pre-commit-config.yaml`: Local checks that run automatically before a commit.

`.commitlintrc.yaml`: Commit message rules (Conventional Commits), plus a required `Generated-By:` trailer naming the model that wrote the commit. `scripts/attribute-commit` writes that trailer at `prepare-commit-msg` by rewriting an agent's `Co-Authored-By` line; the rule is what makes a commit fail when the hook is not installed rather than land unattributed, and a commit written by hand adds the trailer itself or is refused.

### Additions by Occasion

These live in `src/repository-addons/` and are never copied during generation — added by hand when the occasion arrives. `src/addon-adoption.json` lists what must be edited in each before it's safe to ship.

#### When someone else will use it

`README.md`: The public orientation page — what the project does, how to install it, and how to use it.

`CHANGELOG.md`: A per-version record of what changed, in Keep a Changelog format.

`.claude/rules/changelog.md`: Teaches the agent when a changelog entry is owed and how to write one, loading only when `CHANGELOG.md` enters context. Adopted together with `CHANGELOG.md` — one without the other is a defect, not a lighter choice.

`LICENSE`: The terms under which others may use, modify, and distribute the work. Ships as GNU GPL-3.0-or-later.

`AUTHORS`: The copyright holders — not the contributor list, which is `CONTRIBUTORS.md`. It exists so notices in the source tree can read `Copyright (C) <year> The <project> Authors` and be updated in one place instead of file by file. Adopted only with `LICENSE`, and only when copyright is held by more than one party; it does not change `LICENSE`, which ships verbatim.

`SECURITY.md`: The private channel for reporting a vulnerability, and what to expect after.

`SUPPORT.md`: Routes users to help, separate from the issue tracker. Uncomment the `contact_links` block in the payload's `.github/ISSUE_TEMPLATE/config.yml` to name the same destination on the template chooser.

`.env.example`: A sanitized template of `.env` listing required variables without exposing secrets. Ships as a commented scaffold — what the file is for, why every value in it is published, and example shapes to replace with this project's own variables.

#### When someone else will contribute code

`CONTRIBUTING.md`: How a change reaches the default branch — reporting a bug, proposing an enhancement, and opening a pull request.

`.github/PULL_REQUEST_TEMPLATE/release.md`: A pull request form for cutting a release — the version and range, what is shipping, breaking changes, migrations, and what publishing cannot undo.

`.github/PULL_REQUEST_TEMPLATE/hotfix.md`: A pull request form for a production emergency. Shorter than the default on purpose, and the shortening is the point: it asks what is broken, why it cannot wait, and — the section the default does not have — which parts of the normal process were skipped. Both are reachable only through a `?expand=1&template=<name>.md` URL, so adopting either means uncommenting the line of links the payload's `.github/PULL_REQUEST_TEMPLATE.md` already carries.

`CODE_OF_CONDUCT.md`: Baseline rules for community behavior. Ships as Contributor Covenant 3.0.

`CODEOWNERS`: Which accounts GitHub requests for review when a pull request touches a given path.

#### When the project outlives a single maintainer

`GOVERNANCE.md`: Who has final say, how routine decisions get made, and how disputes are resolved. Ships as a single-maintainer template.

`CONTRIBUTORS.md`: A public ledger crediting contributors, maintained by the All Contributors bot.

`.all-contributorsrc`: The All Contributors bot's configuration and contributor state.

#### When the repository has Discussions

`.github/DISCUSSION_TEMPLATE/<category-slug>.yml`: A discussion form, one file per category. The file name has to be the slug of a real category or the form is silently never shown. Two ship:

`.github/DISCUSSION_TEMPLATE/general.yml`: For the question documentation could not have anticipated — whether the project handles a situation, which of two approaches fits. It routes anything the documentation *should* have answered to the issue tracker as a defect, which is a decision about this project rather than a neutral default.

`.github/DISCUSSION_TEMPLATE/ideas.yml`: For working out whether something is worth building before anyone builds it. Asks for the problem before the solution, and sits upstream of the payload's `feature_request.yml` rather than duplicating it.

#### When releases are published from GitHub

`.github/release.yml`: Groups and filters the pull requests in GitHub's generated release notes. Read whenever those notes are generated — from the web UI, from the API, and from `scripts/release`, which generates them only for a repository with no `CHANGELOG.md`. A repository publishing from its changelog still reaches this file by the first two routes.

#### When the project publishes a site

`_config.yml`: Jekyll's configuration, read when the Pages source is "Deploy from a branch".

`404.html`: The page GitHub Pages serves for any path under the site that does not exist. Served by the Pages web server rather than built, so it works whichever way the site is published — Jekyll or not. One self-contained file with nothing linked out: every stylesheet or script an error page references is another path that can fail.

`.nojekyll`: Turns Jekyll off, for a site that is already built HTML or has a path starting with an underscore. Exactly one of these two is adopted: `.nojekyll` disables the processor `_config.yml` configures. It ships carrying a note explaining that choice, which is safe because Pages reads only whether the file exists and never what is in it.

#### When the development environment ships with the repository

`.devcontainer/devcontainer.json`: The container Codespaces and the editors' dev-container support build for this repository. Ships as a bare Debian image with no features, because the toolchains are what the template cannot know. Written as JSON with comments, which the dev container schema allows and `check-json` does not — both `.pre-commit-config.yaml` copies exclude the path for that reason.

#### When the work is academically valuable

`CITATION.cff`: Machine-readable citation metadata, which GitHub surfaces as a "Cite this repository" button. Root only.

#### When the project has gained traction

`.github/FUNDING.yml`: Displays a sponsor button on the repository. Read only from `.github/`.

#### When a helper needs to be built before it runs

`tools/CLAUDE.md`: Creates `tools/` and owns it as a documented boundary — each helper gets its own `tools/<name>/` with its own manifest and source, and a helper that's just a shell script belongs in `scripts/` instead. Copied in only when the project needs a helper that must be built before it runs: a linter, a code generator, a protobuf plugin. Its sections ship seeded with what the template can know, including the trap: `scripts/check` reads the manifests at the repository root, so a tool whose language has no root manifest is built and tested by nobody. Being a child document, it has to be added to the root `CLAUDE.md`'s Child Index when adopted, or nothing walking the tree reaches it.

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
