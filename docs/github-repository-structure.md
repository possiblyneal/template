---
type: Note
---
# Github Repository Structure

### GitHub Automation

This section establishes the continuous integration guardrails.

\*\*`.github/workflows/ci.yml`\*\*: Runs tests, linting, formatting checks, type checks, and builds. Acts as the first line of defense against AI-generated syntax errors. Should be kept as simple as possible, the bulk of the code will go in the tools folder, so this can be run independently of pushing to GitHub.

\*\*`.github/workflows/release.yml`\*\*: Publishes packages, tags releases, builds binaries, and creates changelog artifacts. Should be kept as simple as possible, the bulk of the code will go in the tools folder, so this can be run independently of pushing to GitHub.

\*\*`.github/workflows/security.yml`\*\*: Runs dependency audits, CodeQL, OpenSSF Scorecard, and secret scanning. Should be kept as simple as possible, the bulk of the code will go in the tools folder, so this can be run independently of pushing to GitHub.

\*\*`.github/ISSUE_TEMPLATE/`\*\*: Contains `bug_report.yml` and `feature_request.yml`. These force users—and agents—to provide reproducible inputs \(expected/actual behavior, environment, logs\) rather than vague complaints.

\*\*`.github/PULL_REQUEST_TEMPLATE.md`\*\*: Establishes the required checklist for code merges, ensuring the AI documents its changes thoroughly.

### AI Directives

States the specific operating parameters for the AI agent.

\*\*`.claude/rules/`\*\*: Core behavioral constraints, domain-specific heuristics, and strict formatting requirements the AI must follow during generation.

\*\*`.claude/skills/`\*\*: Reusable, parameterized prompts that you or the AI can invoke by name to execute complex, multi-step actions.

\*\*`.claude/commands/`\*\*: Single-file prompts invoked with a `/name` shortcut for rapid, distinct terminal tasks. Kept strictly separate from skills to maintain clear execution boundaries.

\*\*`.claude/output-styles/`\*\*: Templates dictating the exact format of generated code, logs, or documentation to ensure the AI's output matches your personal conventions.

\*\*`.claude/agents/`\*\*: Specialized subagents equipped with their own scoped context windows for isolated tasks \(e.g., a dedicated refactoring agent\).

\*\*`.claude/workflows/`\*\*: Dynamic workflow scripts that orchestrate multiple subagents in sequence.

\*\*`.claude/agent-memory/`\*\*: Subagent persistent memory, maintaining state across sessions separately from the main session auto-memory.

\*\*`.claude/settings.json`\*\*: Overrides for global `settings.json`. 

\*\*`.mcp.json`\*\*: Configures Model Context Protocol \(MCP\) servers exclusively for this project, granting the AI read/write access to external tools like databases, APIs, or local browsers.

\*\*`CLAUDE.md`\*\*: The project-specific system prompt. Houses your conventions, common commands, and architectural context so the AI operates with the same baseline assumptions as a human developer.

### Source Code, Tests & Infrastructure

The core workspace where development, execution, and testing occur.

\*\*`apps/<domain or deployable service>/src/`\*\*: Project source code is stored here. Each deployable unit inside must be entirely self-contained reguarding its specific dependencies.

\*\*`apps/<domain or deployable service>/tests/`\*\*: Tests for the domain or deployable service that doesn't touch other domains or services.

\*\*`libs/`\*\*: Shared libraries

\*\*`libs/schemas/`\*\*: Shared data structures

\*\*`integration-tests/`\*\*: end-to-end, integration, and benchmark tests that span multiple projects in `src/apps/` or `libs/`.

\*\*`tools/container-files/`\*\*: Holds Dockerfiles, Compose files, and Quadlets for infrastructure-as-code, allowing the AI to spin up local environments or deployments autonomously.

\*\*`tools/scripts/`\*\*: One-off shell or Python scripts for data manipulation, migration, or setup.

\*\*`tools/ci/`\*\*: scripts called by `.github/workflows/`.

\*\*`tmp/`\*\*: Git-ignored scratch space for the AI to write temporary files, download artifacts, or dump logs. Includes a `.gitkeep` to maintain the directory structure.

### Documentation & Knowledge Base

Durable knowledge that grounds the AI in the project's specific reality and operational standards.

\*\*`TODO.md`\*\*: A plain-text todo of backlogged, informal tasks

\*\*`docs/adr/`\*\*: Architectural Decision Records \(e.g., `0001-initial-stack.md`\). Explains \*why\* decisions were made so the AI doesn't attempt to revert or fundamentally alter established systems.

\*\*`docs/specs/`\*\*: Spec Documents detailing feature scopes and acceptance criteria.

\*\*`docs/plans/`\*\*: Documents implementation plans for new features.

### Root Configuration Files

The hidden files that dictate environment variables, Git behavior, and tool integrations.

\*\*`.worktreeinclude`\*\*: Lists git-ignored files to copy into new Git worktrees. Ensures untracked configurations are maintained across multiple branch checkouts.

\*\*`.env`\*\*: The git-ignored config file for storing active sensitive environment variables.

\*\*`.env.example`\*\*: A sanitized template of `.env` showing required variables without exposing actual secrets.

\*\*`.gitignore`\*\*: Specifies intentionally untracked files and directories.

\*\*`.gitattributes`\*\*: Git behavior rules for line endings and language classification.

\*\*`.pre-commit-config.yaml`\*\*: Local guardrails that run formatters and linters automatically before code gets committed, catching AI syntax mistakes early.

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

**Root-level: TBD**

**App-level: TBD**

#### Kotlin

**Root-level: TBD**

**App-level: TBD**
