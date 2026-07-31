---
type: Note
---

# GitHub Repository Structure

### GitHub Automation

This section establishes the continuous integration guardrails.

\*\*`.github/workflows/ci.yml`\*\*: Runs tests, linting, formatting checks, type checks, and builds. Acts as the first line of defense against AI-generated syntax errors. Should be kept as simple as possible, the bulk of the code will go in the tools folder, so this can be run independently of pushing to GitHub.

\*\*`.github/workflows/release.yml`\*\*: Publishes packages, tags releases, builds binaries, and creates changelog artifacts. Should be kept as simple as possible, the bulk of the code will go in the tools folder, so this can be run independently of pushing to GitHub.

\*\*`.github/workflows/security.yml`\*\*: Runs dependency audits, plus a secret scan when a scanner is present. Should be kept as simple as possible, the bulk of the code will go in the tools folder, so this can be run independently of pushing to GitHub.

\*\*`.github/actions/setup-toolchains/`\*\*: A composite action that detects which language manifests are present and installs a toolchain for each. `ci.yml` and `release.yml` both need every toolchain the repository uses, because `tools/ci/release` runs `tools/ci/ci` before publishing and that fails when a manifest is present but its toolchain is missing. Held in one place because the same sixty lines in two workflows drift, and the copy that drifts is the release one, which fails at the moment a release is being cut. `security.yml` keeps its own detection: it installs audit tools rather than toolchains, and needs trivy for Swift and Gradle lockfiles.

Rule of thumb:

- **`ci.yml`**: Thinnest. One call to `tools/ci/ci` is often enough.
- **`release.yml`**: Thin wrapper plus GitHub release/package auth.
- **`security.yml`**: Wrapper plus GitHub-native security actions.
- **`codeql.yml`**: No `tools/ci/` counterpart. CodeQL runs on GitHub's infrastructure and reports into the Security tab, so there is nothing to run locally.

Best-practice goal is not "all logic outside YAML." Better goal: portable project logic in `tools/ci/`; provider-specific orchestration in `.github/workflows/`.

\*\*`.github/workflows/codeql.yml`\*\*: Static analysis that traces untrusted input to dangerous sinks across files, which is the class of bug the linters in `tools/ci/ci` cannot see. It runs on pull requests, on `main`, and weekly, because CodeQL adds queries over time and a scheduled run finds problems in code that has not changed.

CodeQL fails when told to analyze a language a repository does not contain, so a fixed language list would break every clone that does not use all of them. A detect job reads the same manifests as `tools/ci/ci` and builds the analysis matrix from what is present. Swift is pinned to a macOS runner because CodeQL does not analyze it on Linux. The matrix always includes `actions`, which analyzes the workflows themselves: it keeps the matrix non-empty on a repository that has no application code yet, and the workflows are worth scanning on their own since they run with repository credentials.

Findings appear in the repository's Security tab. Code scanning is free on public repositories; on private ones it requires GitHub Advanced Security, and without it this workflow fails at the upload step rather than silently reporting success.

\*\*`.github/dependabot.yml`\*\*: Opens weekly pull requests for the action versions used in `.github/workflows/`, grouped into one pull request rather than one per action. Every action is pinned to a major tag so patch and minor releases arrive without a change here, which leaves this file responsible only for major bumps, the ones that need review anyway. Pinning without this would mean tracking versions by hand; floating refs such as `@latest` would avoid that at the cost of letting a third-party action change under every repository cloned from the template. `astral-sh/setup-uv` is the one exception, pinned to an exact release because that project stopped publishing moving major tags after `v7`, so `@v9` resolves to nothing.

\*\*`.github/ISSUE_TEMPLATE/`\*\*: Contains `bug_report.yml`, `feature_request.yml`, and `config.yml`. `bug_report.yml` captures the affected version, expected vs. actual behavior, severity, frequency, reproduction steps, logs, regression history, environment, investigation hints, and reporter safeguards. The affected version is a required field because "latest" names a different commit depending on when it is read, and resolves differently for a package registry than for the repository. The optional checklist item about the latest version answers a separate question, whether the reporter retested there, which a reporter pinned to an older release cannot always answer. Severity and frequency are separate because they answer different triage questions: how much damage each occurrence does, and how often it occurs. `feature_request.yml` captures the problem or user need, desired outcome, use cases, scope boundaries, acceptance criteria, open questions, and supporting context. Acceptance criteria ask for a check someone can run, which is what separates a request that can be built from one that can only be guessed at. Open questions are optional and ask the requester to mark what they have not decided, so the parts that were hand-waved arrive labelled rather than indistinguishable from the parts that were settled. `config.yml` disables blank issues, which would otherwise appear alongside the forms and make every required field in them optional in practice.

\*\*`.github/PULL_REQUEST_TEMPLATE.md`\*\*: Structures a pull request so a reviewer can approve, reject, or question it without trusting the author's own assessment. Verification asks for a CI run link or raw output rather than a checkbox claiming tests passed, since a self-reported pass is indistinguishable from an unrun one. Risk is a set of factual yes/no questions about migrations, auth, secrets, public interfaces, dependencies, and data loss, each of which can be checked against the diff, rather than a self-assigned severity label. Two sections ask for what a diff cannot show: what was not verified, and which judgment calls a reviewer should examine. A scope section catches unrelated changes.

### AI Directives

States the specific operating parameters for the AI agent.

\*\*`.claude/rules/`\*\*: Core behavioral constraints, domain-specific heuristics, and strict formatting requirements the AI must follow during generation.

\*\*`.claude/skills/`\*\*: Reusable, parameterized prompts that you or the AI can invoke by name to execute complex, multi-step actions.

\*\*`.claude/commands/`\*\*: Single-file prompts invoked with a `/name` shortcut for rapid, distinct terminal tasks. Kept strictly separate from skills to maintain clear execution boundaries.

\*\*`.claude/output-styles/`\*\*: Templates dictating the exact format of generated code, logs, or documentation to ensure the AI's output matches your personal conventions.

\*\*`.claude/agents/`\*\*: Specialized subagents equipped with their own scoped context windows for isolated tasks \(e.g., a dedicated refactoring agent\).

\*\*`.claude/workflows/`\*\*: Dynamic workflow scripts that orchestrate multiple subagents in sequence.

\*\*`.claude/agent-memory/`\*\*: Subagent persistent memory, maintaining state across sessions separately from the main session auto-memory.

\*\*`.claude/settings.json`\*\*: Overrides for global `settings.json`. The template ships the empty containers only, so a new project sees the available sections without inheriting rules: `permissions` \(`allow`, `ask`, `deny`, `additionalDirectories`\), `env`, `hooks`, `sandbox`, `attribution`, `enabledPlugins`, `modelOverrides`, and `skillOverrides`.

Keys are omitted rather than blanked when an empty value would be invalid, because a settings file that fails validation is rejected as a whole rather than partially applied. Three kinds must stay absent until they hold a real value: enum strings such as `permissions.defaultMode` and `editorMode`, where `""` is not a permitted member; strings with a minimum length such as `outputStyle` and `apiKeyHelper`; and objects with required sub-fields such as `statusLine` and `policyHelper`, which need `type` and `command` or `path`. `model` is also omitted because its empty-string behavior is undefined.

\*\*`.mcp.json`\*\*: Configures Model Context Protocol \(MCP\) servers exclusively for this project, granting the AI read/write access to external tools like databases, APIs, or local browsers.

\*\*`CLAUDE.md`\*\*: The project-specific system prompt. Houses your conventions, common commands, and architectural context so the AI operates with the same baseline assumptions as a human developer.

### Source Code, Tests & Infrastructure

The core workspace where development, execution, and testing occur.

\*\*`apps/<domain or deployable service>/src/`\*\*: Project source code is stored here. Each deployable unit inside must be entirely self-contained regarding its specific dependencies.

\*\*`apps/<domain or deployable service>/tests/`\*\*: Tests for the domain or deployable service that doesn't touch other domains or services.

\*\*`apps/<domain or deployable service>/docs/specs/`\*\*: Specs describing that unit's own behavior and acceptance criteria. They change in the same commit as the code they describe.

\*\*`apps/<domain or deployable service>/docs/plans/`\*\*: Implementation plans for in-flight work on that unit. Plans spanning several units live in `docs/plans/`. Short-lived; remove them once the work lands.

\*\*`libs/`\*\*: Shared internal libraries, schemas, utilities, and reusable modules used by apps. They do not have to be publishable packages.

\*\*`tests/`\*\*: Repo-level tests that span multiple apps or libraries, such as integration, end-to-end, contract, benchmark, and shared fixtures. App-local tests stay under `apps/<domain or deployable service>/tests/`.

\*\*`tools/scripts/`\*\*: Portable helper scripts for local development and repo hygiene. Default scripts: `doctor` checks required tools, `check` runs local pre-commit checks, `clean` removes common generated/cache files, and `dev` starts the local dev command when configured.

`doctor` treats an uninstalled pre-commit hook as a missing tool. `.pre-commit-config.yaml` is tracked, but the hook it describes lives in `.git/hooks/`, which is local to a clone and never committed, so a fresh clone has the config and none of the enforcement. Nothing surfaces that on its own: commits succeed exactly as before while the configured hooks, the secret scan among them, never run. `doctor` therefore fails when the config is present but either the tool or the installed hook is missing, and stays silent when there is no config to honor.

\*\*`tools/ci/`\*\*: Portable shell scripts called by `.github/workflows/`. Keep this folder small: `ci`, `release`, and `security`. These are scripts, not YAML, because they should run locally the same way they run in GitHub Actions.

Both scripts distinguish a check that ran and passed from one that never ran, and treat the second as a failure whenever the check was expected. If a project manifest is present but its toolchain is missing, the run fails rather than reporting success for work it did not do. The workflows install only the toolchains a repository actually uses, detected from its manifests.

`tools/ci/security` runs a dependency audit and, when a scanner is installed, a secret scan. Secret prevention belongs to GitHub push protection rather than to CI: push protection rejects a secret before it reaches the remote, while a CI scan reports one that is already published and can only be rotated. The workflow therefore installs no scanner, since doing so meant downloading an unverified binary inside the job responsible for supply-chain safety, and gitleaks runs from `.pre-commit-config.yaml` instead, where it sees a secret while it is still an unstaged edit. The CI secret scan stays as a backstop that runs when a scanner happens to be present and never blocks on its absence.

Checks that GitHub already provides are left to GitHub. Dependabot opens upgrade pull requests rather than only reporting findings, and push protection blocks secrets outright, so neither is reimplemented here. Code scanning, license policy, and container image scanning are deliberately absent: each answers a question this repository does not currently have, and a check that cannot fail meaningfully teaches people to ignore the ones that can.

Manifest detection has to list every language the repository supports, because a manifest the scripts do not recognize reads as no project at all and exits successfully with nothing checked, which is indistinguishable from a passing run. `Package.swift`, `settings.gradle.kts`, and `build.gradle.kts` therefore count as manifests alongside the others.

Swift is detected by searching rather than by checking the repository root, because it is the one supported language with no root manifest: SwiftPM has no workspace file, so packages sit at `apps/<name>/` and `libs/<name>/` and nothing at the root names them. A root-only check finds no manifest in a Swift repository and reports the silent pass described above. The search skips `.build/`, which holds checked-out dependencies that carry manifests of their own. For the same reason the Swift commands run once per package directory instead of once at the root, and every package runs even after one fails, so a single broken package does not hide the state of the rest.

`tools/ci/release` runs `tools/ci/ci` before publishing, so the release workflow installs the same toolchains as the CI workflow; without them the pre-release check fails on every tagged release for exactly the reason it is there. It refuses to publish while packaging is unconfigured, rather than printing that nothing is configured and exiting successfully, so a green release always means an artifact was produced. The tag comes from an explicit argument before `GITHUB_REF_NAME`, because a `workflow_dispatch` run is dispatched against a branch and its ref is not the tag being released; the workflow passes that input through the environment rather than `${{ }}` interpolation, which would place a user-supplied string directly into a shell command.

Swift and Kotlin differ from the rest in two ways. Neither has a first-party dependency audit, so `tools/ci/security` audits both through trivy reading their lockfiles; because Gradle locking is opt-in, a repository with no `gradle.lockfile` has no resolved versions to audit and reports no runner rather than scanning declared version ranges, which would report findings for versions the build may never select. Gradle also exposes lint and format tasks only when the matching plugin is applied, so `tools/ci/ci` queries the task list and runs `ktlintCheck` or `detekt` if present rather than assuming either exists.

\*\*`tmp/`\*\*: Git-ignored scratch space for the AI to write temporary files, download artifacts, or dump logs. Includes a `.gitkeep` to maintain the directory structure.

### Documentation & Knowledge Base

Durable knowledge that grounds the AI in the project's specific reality and operational standards.

\*\*`TODO.md`\*\*: A plain-text to-do of backlogged, informal tasks

\*\*`docs/adr/`\*\*: Architectural Decision Records \(e.g., `0001-initial-stack.md`\). Explains \*why\* decisions were made so the AI doesn't attempt to revert or fundamentally alter established systems. Keep one repo-wide numbered sequence here so decisions stay discoverable without knowing which app to look in. An app may keep its own `docs/adr/` once local decisions would drown the repo-wide ones; when it does, link it from this folder's index and never reuse numbers across scopes.

\*\*`docs/specs/`\*\*: Specs for contracts that span apps, such as service-to-service APIs and shared schemas. Specs for a single unit stay under `apps/<domain or deployable service>/docs/specs/`.

\*\*`docs/plans/`\*\*: Implementation plans for the cross-app specs above. A plan lives at the same level as the spec driving it, so plans for a single unit stay under `apps/<domain or deployable service>/docs/plans/`. Cross-app plans own the sequencing across units; when the work is large enough to need per-app detail, keep the ordering and rollout here and link out to per-app slices. Delete a plan once its work lands so stale designs cannot mislead later readers.

### Root Configuration Files

The hidden files that dictate environment variables, Git behavior, and tool integrations.

\*\*`.worktreeinclude`\*\*: Lists git-ignored files to copy into new Claude worktrees, which are otherwise fresh checkouts holding tracked files only. Uses `.gitignore` syntax, and a file is copied only if it both matches a pattern here and is git-ignored, so tracked files are never duplicated. Scoped to local configuration; private keys and Terraform state are deliberately excluded, because worktrees are created and removed casually and copying key material into each one multiplies the places a credential sits on disk.

\*\*`.env`\*\*: The git-ignored config file for storing active sensitive environment variables.

\*\*`.gitignore`\*\*: Specifies intentionally untracked files and directories. Ignores local secrets (`.env` while keeping `.env.example`), private keys and credential files, Terraform state, scratch files, logs, OS/editor files, dependency folders, language caches/build outputs, container runtime state, local database files, and generated artifacts while preserving `tmp/.gitkeep`.

Build output directories whose names also occur in source trees are anchored with a leading slash, so `/bin/` ignores a root build directory without swallowing the `src/bin/` and `cmd/*/bin/` source layouts that Rust and Go use. Patterns that nest legitimately, such as `node_modules/` and `coverage/`, stay unanchored.

\*\*`.gitattributes`\*\*: Git behavior rules for line endings, diffs, and GitHub Linguist classification. A single `* text=auto eol=lf` rule normalizes every text file to LF in both the repo and the working tree on all platforms, so per-extension rules exist only where they override it: Windows scripts stay CRLF, SVG is pinned as text, and Markdown gets a diff driver that names the enclosing heading in hunk headers. Binary files need no rules because Git's auto-detection already handles them. Language diff drivers name the enclosing function in hunk headers, so a diff shows which routine changed rather than only the surrounding class; only Git's built-in drivers take effect and an unrecognized driver name is ignored without warning.

Lockfiles carry `merge=binary` alongside `linguist-generated`. Line-wise merging of a generated file can combine two branches into a dependency set that no resolver ever produced and no branch ever tested, and that result appears as a clean merge; `merge=binary` turns it into a conflict so the resolution is to take one side and regenerate. `linguist-generated` separately collapses lockfiles in GitHub pull requests while leaving local diffs and blame intact. `docs/`, `generated/`, and `vendor/` are classified for cleaner GitHub language stats.

\*\*`.pre-commit-config.yaml`\*\*: Local guardrails that run automatically before code gets committed, catching AI syntax mistakes early. Ships gitleaks, which is the primary secret control in the template because it fires while a credential is still an uncommitted edit, and a handful of hooks that catch mistakes a diff review tends to miss: merge conflict markers, oversized files, and malformed YAML or JSON. Hooks run only after `pre-commit install` in a clone, so the file alone guarantees nothing.

### Public / Open Source Additions

These files govern community interaction and legal usage. They are only necessary if the repository is public and accepting external contributions.

\*\*`README.md`\*\*: The public orientation page explaining what the project does, how to install it, and how to use it.

\*\*`FUNDING.yml`\*\*: Displays a sponsor button in your repository to increase the visibility of funding options for your open source project. 

\*\*`CONTRIBUTING.md`\*\*: Guidelines for external developers on how to submit pull requests, run tests, and adhere to code style.

\*\*`SECURITY.md`\*\*: Outlines the project's security policy, supported versions, and the private channel for reporting vulnerabilities.

\*\*`LICENSE`\*\*: The legal document outlining the usage, modification, and distribution rights of the code.

\*\*`CODE_OF_CONDUCT.md`\*\*: The baseline rules for community behavior and expectations for professional interaction.

\*\*`SUPPORT.md`\*\*: A routing document directing users where to get help, filtering general troubleshooting out of the core issue tracker.

\*\*`CONTRIBUTORS.md`\*\*: A public ledger crediting individuals who have contributed code or documentation.

\*\*`CODEOWNERS`\*\*: The definitive list of core team members with write access and merge authority.

\*\*`GOVERNANCE.md`\*\*: The political structure of the repository, defining how decisions are made, how maintainers are elected, and how disputes are resolved.

\*\*`.env.example`\*\*: A sanitized template of `.env` showing required variables without exposing actual secrets.

### Program Language Metadata

These languages have built-in or universally accepted package managers, meaning they have strict, required root-level files and app-level files

#### Python

**Root-level:** \*\*`pyproject.toml`\*\* \(workspace config via uv\)

**App-level:** \*\*`pyproject.toml`\*\*

#### Go

**Root-level:** \*\*`go.work`\*\*: Go will automatically create the lockfile, `go.work.sum`

**App-level:** \*\*`go.mod`\*\*: Go will automatically create the lockfile, `go.sum`

#### Typescript

**Root-level:** \*\*`tsconfig.json`\*\*. \(Defines workspaces\) \*\*`package.json`\*\*

**App-level:** \*\*`tsconfig.json`\*\*. \*\*`package.json`\*\* \(extends root config\)

#### Rust

**Root-level:** \*\*`Cargo.toml`\*\* \(contains [workspace]\) Rust will automatically create the lockfile, `Cargo.lock`

**App-level:** \*\*`Cargo.toml`\*\* \(contains [package]\) Rust will automatically create the lockfile, `Cargo.lock`

#### Swift

**Root-level:** None. Swift Package Manager has no workspace manifest; multi-package repository support has been an open request since 2017, so there is no root file that enumerates members or produces a shared lockfile. Apps reach each other with `.package(path: "../../libs/<name>")` instead. An `.xcworkspace` can group packages for Xcode, but it is an IDE convenience, not a build contract, and command-line builds ignore it.

**App-level:** \*\*`Package.swift`\*\*: Swift will automatically create the lockfile, `Package.resolved`. Because there is no workspace, every app resolves independently and versions can drift between apps; pin shared dependencies deliberately.

#### Kotlin

**Root-level:** \*\*`settings.gradle.kts`\*\* \(defines the workspace via `include(":app")`, and each path must match a real directory\). \*\*`build.gradle.kts`\*\* \(shared plugin and config applied to subprojects\). \*\*`gradle/libs.versions.toml`\*\* \(version catalog holding the single source of dependency versions\). \*\*`gradle/wrapper/`\*\* and \*\*`gradlew`\*\* \(pin the Gradle version itself; commit them\).

**App-level:** \*\*`build.gradle.kts`\*\*

Unlike the package managers above, Gradle writes no lockfile by default. Dependency locking is opt-in and produces `gradle.lockfile` per project only after it is enabled and written. Without it, builds are not reproducible across time.
