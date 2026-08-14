---
type: Note
---
# GitHub Repository Structure

### GitHub Automation

`.github/workflows/ci.yml`: Runs tests, linting, formatting checks, type checks, and builds. The first line of defense against AI-generated syntax errors.

`.github/workflows/release.yml`: Validates a tagged release now; packaging, publishing, binaries, and changelog artifacts are wired into `scripts/release` when the project defines them. It has only `contents: read` until then. Publishing belongs in a separate job with `contents: write`, so checkout and the build never receive a token able to modify the repository.

`.github/workflows/security.yml`: Runs dependency audits, plus a secret scan when a scanner is present.

**`.github/workflows/release.yml`**: Verifies a tagged release and publishes it, both through `scripts/release`. Artifacts and binaries are wired into that script when the project defines them. It holds `contents: write` because it creates the release.

**`.github/workflows/security.yml`**: Runs dependency audits, plus a secret scan when a scanner is present.

**`.github/actions/setup-toolchains/`**: Installs a toolchain for each language manifest present, reading `scripts/detect github-output` for the list.

Rule of thumb:

- **`ci.yml`**: Thinnest. One call to `scripts/ci` is often enough.
- **`release.yml`**: Thin wrapper plus GitHub release/package auth.
- **`security.yml`**: Wrapper plus GitHub-native security actions.
- **`codeql.yml`**: No `scripts/` counterpart. CodeQL runs on GitHub's infrastructure and reports into the Security tab, so there is nothing to run locally.

The goal is not "all logic outside YAML" but portable project logic in `scripts/` and provider-specific orchestration in `.github/workflows/`.

`.github/workflows/codeql.yml`: Static analysis tracing untrusted input to dangerous sinks across files, the class of bug the linters in `scripts/ci` cannot see. Runs on pull requests, on `main`, and weekly: CodeQL adds queries over time, so a scheduled run finds problems in code that has not changed.

Analysis is gated on the repository being public. Code scanning accepts uploaded results from a public repository, or from a private one with GitHub Advanced Security; without it the analysis completes and then fails at the upload step on every run, and a check that can only ever be red teaches people to ignore the ones that can tell them something. The `detect` job reads visibility and `analyze` is skipped unless it is `public`, with the reason written to the run summary rather than leaving a bare skip to interpret. A private repository that does have Advanced Security removes the `if:` on `analyze`.

Visibility is read from the API rather than from `github.event.repository.visibility`, whose payload GitHub documents as "Not applicable" for `schedule`. Taken from the event, the weekly run would compare a null against `public` and skip itself on a repository that should be scanned — the silent no-op the gate exists to prevent, arriving through the gate. A failed lookup fails the step rather than defaulting either way, so it cannot be mistaken for a repository that should not be scanned.

`.github/dependabot.yml`: Opens one grouped weekly pull request for the action versions in `.github/workflows/` and `.github/actions/`, rather than one per action.

`.github/ISSUE_TEMPLATE/`: Contains `bug_report.yml`, `feature_request.yml`, and `config.yml`.

`bug_report.yml` captures the affected version, expected vs. actual behavior, severity, frequency, reproduction steps, logs, regression history, environment, investigation hints, and reporter safeguards.

`feature_request.yml` captures the problem or user need, desired outcome, use cases, scope boundaries, acceptance criteria, open questions, and supporting context.

`config.yml` disables blank issues, which would otherwise sit alongside the forms and make every required field optional in practice.

`.github/PULL_REQUEST_TEMPLATE.md`: Structures a pull request so a reviewer can approve, reject, or question it without trusting the author's own assessment.

### AI Directives

The specific operating parameters for the AI agent.

`.openclaude/rules/`: Core behavioral constraints, domain-specific heuristics, and strict formatting requirements the AI must follow during generation. A rule without `paths:` frontmatter loads at session start at the same priority as `CLAUDE.md`; a rule with it loads only when a matching file enters context, keeping a long contract out of sessions that never touch its subject.

The template ships `documentation.md`, holding the contract governing `CLAUDE.md` files:

`.openclaude/skills/`: Reusable, parameterized prompts that you or the AI can invoke by name to execute complex, multi-step actions. Each `<name>/SKILL.md` is also invocable as `/name`, which is why the template ships no `.openclaude/commands/`: commands are the legacy single-file form of the same shortcut, and one directory holding both roles beats two whose boundary needs explaining.

`.openclaude/output-styles/`: Templates dictating the exact format of generated code, logs, or documentation, so the AI's output matches your personal conventions.

`.openclaude/agents/`: Specialized subagents with their own scoped context windows for isolated tasks e.g., a dedicated refactoring agent.

`.openclaude/workflows/`: Dynamic workflow scripts that orchestrate multiple subagents in sequence.

`.openclaude/agent-memory/`: Subagent persistent memory, maintaining state across sessions separately from the main session auto-memory. Not shipped; Claude Code creates the directory when a subagent first writes to it.

`.openclaude/hooks/`: Shell scripts wired to tool events by `.openclaude/settings.json`. Ships three, each parsing its input with `jq`, which is why `scripts/doctor` requires that tool while any of them is present.

`ask-outside-repo.sh` is a `PreToolUse` hook that prompts before `Edit`, `Write`, or `NotebookEdit` touches a path outside the repository.

`block-config-change.sh` is a `ConfigChange` hook that stops edits to `.openclaude/settings.json`, `.openclaude/settings.local.json`, or `.openclaude/skills/` from hot-reloading into the running session. Without it, a session that edits its own settings gets the new permissions immediately, unwinding the ask gates above from inside; the same mid-session path is how a malicious skill file would take effect.

`session-start.sh` is a `SessionStart` hook that prints the current branch, uncommitted changes, and recent commits as session context, restates the read-before-edit obligation and names the rule file holding the full documentation contract, and runs `pre-commit install` when the config is present but a hook it asks for is not yet installed.

`.openclaude/settings.json`: Overrides for global `settings.json`. The template fills `hooks` with the three entries above, `permissions.ask`, `plansDirectory`, `attribution`, `allowedHttpHookUrls`, and `disableClaudeAiConnectors`, and ships the remaining containers empty so a new project sees the available sections without inheriting rules: `permissions.allow`, `permissions.deny`, `permissions.additionalDirectories`, `env`, `sandbox`, `enabledPlugins`, `modelOverrides`, and `skillOverrides`.

`.mcp.json`: Configures Model Context Protocol MCP servers for this project only, granting the AI read/write access to external tools like databases, APIs, or local browsers.

`CLAUDE.md`: The project-specific system prompt. Houses your conventions, common commands, and architectural context so the AI operates with the same baseline assumptions as a human developer. The template ships four sections.

`CLAUDE.local.md`: Personal, per-machine instructions loaded alongside `CLAUDE.md` and excluded by `.gitignore`. Not shipped; the entry exists so local preferences have a home that is not a diff.

### Source Code, Tests & Infrastructure

The core workspace where development, execution, and testing occur.

An `apps/` entry is one deployable service or one durable domain boundary: the unit that owns its own dependencies, tests, and specs.

`apps/<domain or deployable service>/src/`: Project source code. Each deployable unit inside must be entirely self-contained regarding its specific dependencies.

`apps/<domain or deployable service>/tests/`: Tests for the domain or deployable service that don't touch other domains or services.

`apps/<domain or deployable service>/docs/specs/`: Specs describing that unit's own behavior and acceptance criteria. They change in the same commit as the code they describe.

`libs/`: Shared internal libraries, schemas, utilities, and reusable modules used by apps. They do not have to be publishable packages.

`tests/`: Repo-level tests spanning multiple apps or libraries: integration, end-to-end, contract, benchmark, and shared fixtures. App-local tests stay under `apps/<domain or deployable service>/tests/`.

`scripts/`: Every portable shell script, whether a person runs it or a workflow does. `scripts/security` runs a dependency audit and, when a scanner is installed, a secret scan.

`scripts/libs/`: Shared shell libraries private to the `scripts/` entry points. Its plural name matches root `libs/`: each file is a library, while the directory holds the collection. Nothing here is a command, so files have no shebang or executable bit; callers source them by an absolute path rooted at the repository.

`scripts/libs/detect.sh`: The detection library, defined once. 

**`scripts/libs/precommit.sh`**: Which git hooks `.pre-commit-config.yaml` asks for, and which of them a clone lacks.

**`scripts/detect`**: The same detection over a command line, because a workflow cannot source a bash library. `github-output` writes `language=true|false` flags for a step's `if:`, `codeql-matrix` writes the matrix JSON, and `check-orphans` reports the failure below. `setup-toolchains`, `security.yml`, and `codeql.yml` call it rather than each carrying detection of their own.

**`scripts/tests/`**: `capabilities-test` asserts that every language present is dispatched to every check.

`scripts/release` does the one part of publishing a template can know: it checks the tag against `vX.Y.Z`, runs `scripts/ci`, and creates the GitHub release. The body is the matching `## [x.y.z]` section of `CHANGELOG.md` when the project keeps one — and the run stops when that section is missing, since a version absent from the changelog has not been cut. A project with no `CHANGELOG.md` releases with GitHub-generated notes instead.

**`tools/`**: The counterpart to `scripts/`, and a convention rather than a shipped directory. A helper that has to be built before it runs — a Go linter, a code generator, a protobuf plugin — goes here as `tools/<name>/`, one directory per program, carrying its own manifest and source. A helper that is a shell file goes in `scripts/`. T

**`tmp/`**: Git-ignored scratch space for temporary files, downloaded artifacts, and dumped logs, holding a `.gitkeep` so the directory survives being empty.

### Documentation & Knowledge Base

Durable knowledge that grounds the AI in the project's specific reality and operational standards.

`TODO.md`: A plain-text to-do of backlogged, informal tasks

**`docs/adr/`**: Architectural Decision Records (e.g., `0001-initial-stack.md`). Explains *why* decisions were made so the AI doesn't try to revert or fundamentally alter established systems.

`docs/specs/`: Specs for contracts that span apps, such as service-to-service APIs and shared schemas. Specs for a single unit stay under `apps/<domain or deployable service>/docs/specs/`.

`docs/lessons.md`: Hard-won knowledge about this repository specifically: the provider quirks and recurring mistakes an agent would otherwise rediscover.

`docs/plans/`: Plans written in plan mode, pointed here by `plansDirectory` in `.openclaude/settings.json`. The default is `~/.openclaude/plans`, outside the repository, where a plan is invisible to review and disappears with the machine. Under `docs/` it arrives in the diff alongside the code it describes — the point when a human approves the plan before the work starts.

### Root Configuration Files

The hidden files that dictate environment variables, Git behavior, and tool integrations.

`.worktreeinclude`: Lists git-ignored files to copy into new Claude worktrees, which are otherwise fresh checkouts holding tracked files only.

`.env`: The git-ignored config file for storing active sensitive environment variables.

`.gitignore`: Specifies intentionally untracked files and directories. 

`.gitattributes`: Git behavior rules for line endings, diffs, and GitHub Linguist classification.

`.pre-commit-config.yaml`: Local guardrails that run automatically before code gets committed, catching AI syntax mistakes early. **`.commitlintrc.yaml`**: The commit message rules. Messages follow Conventional Commits — `type(optional scope): subject`, a blank line, then the body.

### Additions by Occasion

#### When someone else will use it

Someone who is not the author has to get the thing running, and has to know whether they are allowed to.

`README.md`: The public orientation page: what the project does, how to install it, and how to use it.

**`CHANGELOG.md`**: A per-version record of what changed, in Keep a Changelog 2.0.0 format, pinned by the link in the file's own header so the convention it follows cannot drift as that page changes. Written for someone deciding whether to upgrade, so it arrives with the first reader rather than the first commit. Adopting it brings `.openclaude/rules/changelog.md` with it, which is what teaches an agent when an entry is owed. `scripts/release` then publishes the section matching the tag instead of GitHub-generated notes.

**`LICENSE`**: The terms under which others may use, modify, and distribute the work. Ships as the GNU General Public License v3.0, byte-identical to the text published at gnu.org — reciprocal copyleft, so a derivative carries the same license rather than being absorbed into something closed. Keep it verbatim. An explanatory comment or a filled-in copyright line breaks the license's own terms and can drop GitHub's detection, which matches against the whole text; the project's own copyright notice belongs in source file headers and the README, which is what the appendix at the end of the file gives instructions for.

CC BY-SA 4.0 asks for the same reciprocity and does not survive contact with software: it licenses no patent rights, §2(b)(2) excluding them in as many words; it defines no source-code obligation, so a minified bundle satisfies ShareAlike; and it says nothing about linking, which is the question copyleft exists to answer. Creative Commons declared GPLv3 one-way compatible with BY-SA 4.0 in 2015 for that reason, making GPLv3 their own answer to what BY-SA means for code. AGPL-3.0 closes the one gap GPL leaves — a hosted service is never distributed and so never triggers share-alike — and is deliberately not the default, because the network clause is not wanted here.

A permissive default was weighed and declined. MIT or Apache-2.0 would grow adoption faster, and Apache-2.0 in particular is the better permissive license because it grants patent rights where MIT leaves the same gap CC BY-SA does. Reciprocity was ranked above adoption deliberately: the point of the default is that a derivative stays open, and a permissive license buys reach by giving that up. Treat this as settled rather than reopening it per repository — the case for permissive is real and already known.

The version is **GPL-3.0-or-later**, not version 3 only. That choice is not expressible in `LICENSE`, whose text is identical either way; it lives in the per-file notice, and the SPDX identifier `GPL-3.0-or-later` is what records it in a form tooling reads. Mark source files with the one-line form rather than the full paragraph block:

```
# SPDX-License-Identifier: GPL-3.0-or-later
```

The long-form notice this abbreviates is the appendix at the end of `LICENSE`, already worded for "or later" — use it in the README or a program's `--version` output where a reader needs prose. "Or later" is chosen because relicensing to a future GPLv4 otherwise requires every contributor's individual consent, which is unobtainable in practice once a project has any history.

**`SECURITY.md`**: The project's security policy, supported versions, and the private channel for reporting vulnerabilities. `SUPPORT.md`: Routes users to help, filtering general troubleshooting out of the core issue tracker.

**`.env.example`**: A sanitized template of `.env` showing required variables without exposing actual secrets. Ships empty, like `.env` itself: the variables are whatever the application reads, and a template that guessed them would ship a list every generated repository has to delete. The `.example` suffix is load-bearing — `.gitignore` ignores `.env` and `.env.*`, then re-includes `.env.example` and `.env.*.example` by negation, so a file named `.env.sample` or `.env.local` is ignored and never reaches the repository.

#### When someone else will contribute code

The trigger is a second person with commit ambitions, not a public repository. Two engineers on a private repository are already here.

**`CONTRIBUTING.md`**: Guidelines for external developers on submitting pull requests, running tests, and adhering to code style.

**`CODE_OF_CONDUCT.md`**: The baseline rules for community behavior and expectations for professional interaction. Its value depends on being adopted before it is needed; written in response to an incident it is a ruling rather than a rule, and reads as one.

`CODEOWNERS`: The definitive list of core team members with write access and merge authority. Read from the repository root, `.github/`, or `docs/`, and nowhere else. On its own it only requests reviewers; a branch protection rule requiring code owner review is what makes that request binding.

#### When the project outlives a single maintainer

Both files answer the same question — who decides, and who is owed credit for what — and neither is worth writing while the answer is obviously the author.

`GOVERNANCE.md`: The political structure of the repository: how decisions are made, how maintainers are elected, and how disputes are resolved.

**`CONTRIBUTORS.md`**: A public ledger crediting individuals who have contributed code or documentation. GitHub also recognizes `AUTHORS`, which is a narrower list: the people whose contributions are legally significant for copyright. The two only need to be separate files under a contributor licence agreement or copyright assignment, where who holds the copyright is a different question from who to thank.

Ships in the [All Contributors](https://allcontributors.org) format, carrying the marker comments, the badge, and all thirty-three contribution keys. The format is the point rather than the file: a hand-maintained credit list drifts, and an omission from a list of people you are thanking reads worse than having no list, so the value is in the bot maintaining it. It travels with `.all-contributorsrc`, which is the second half of one record rather than a separate file: the table is generated from the `contributors` array in the config and is never parsed back out of the Markdown, so the config alone is the state. It ships pointing `files` at `CONTRIBUTORS.md`, because the default is `README.md` and the table otherwise lands there while this file stays empty.

Two things remain on adoption. `projectOwner` and `projectName` ship as `REPO-OWNER` and `REPO-NAME` and must be replaced — both are required, so the CLI throws rather than guessing, but they build the profile and commit links, and wrong values give a table of dead links rather than an error. The bot must also be installed from <https://github.com/apps/allcontributors>; the comment syntax does nothing on a repository without it and nothing reports that. The marker comments in the Markdown are matched as literal strings, so reformatting them leaves the bot with nowhere to write and no pull request appears.

**`.all-contributorsrc`**: The All Contributors configuration and contributor state. Named without a `.json` suffix because both the CLI and the bot look for that exact filename, which also means the `check-json` hook does not match it and nothing local validates it — the CLI reads it through `json-fixer`, which silently repairs and rewrites malformed JSON rather than failing. `commit` is `false` so the CLI proposes changes instead of writing a commit, which would otherwise hit `no-commit-to-branch`; `commitConvention` is `angular` so the message it does generate satisfies commitlint.

#### When the work is academically valuable

**`CITATION.cff`**: Machine-readable citation metadata, which GitHub surfaces as a "Cite this repository" button. Root only. The occasion is the work being the kind that gets cited — research software, a dataset, a method — not a citation request arriving, which nothing would announce. On an academic repository that is true on day one; on everything else it never becomes true.

#### When the project has gained traction

**`.github/FUNDING.yml`**: Displays a sponsor button in your repository, raising the visibility of funding options for your open source project. Unlike the rest of this section it is read only from `.github/`; a copy at the repository root is ignored, and the missing button is the only symptom. Opening a sponsors account takes minutes, so the condition worth waiting on is the audience rather than the account — the button is dead weight on a repository nobody has found, and no star count is the number that means one has been found.

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
