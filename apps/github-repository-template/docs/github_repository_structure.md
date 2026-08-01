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

\*\*`.github/dependabot.yml`\*\*: Opens weekly pull requests for the action versions used in `.github/workflows/` and `.github/actions/`, grouped into one pull request rather than one per action. Both locations are listed because `/` covers `.github/workflows/` and a root `action.yml` only, so pins inside a composite action age silently while the workflow copies stay current. Covering them needs `directories`, since the glob it accepts is unsupported by `directory`. A glob matching nothing is harmless here, unlike an ecosystem whose manifest is absent, which fails the run. Every action is pinned to a major tag so patch and minor releases arrive without a change here, which leaves this file responsible only for major bumps, the ones that need review anyway. Pinning without this would mean tracking versions by hand; floating refs such as `@latest` would avoid that at the cost of letting a third-party action change under every repository cloned from the template. `astral-sh/setup-uv` is the one exception, pinned to an exact release because that project stopped publishing moving major tags after `v7`, so `@v9` resolves to nothing.

A second ecosystem covers the hook revisions in `.pre-commit-config.yaml`. Those pins are exact tags rather than major ones, because pre-commit resolves a `rev` to a single revision and offers no floating form, so nothing there updates without a bump. The scanners are why it matters: they read secret and vulnerability definitions, so a stale one reports a clean tree by recognizing fewer problems, which is the same failure the `govulncheck` and `cargo-audit` installs in the security workflow float to avoid.

\*\*`.github/ISSUE_TEMPLATE/`\*\*: Contains `bug_report.yml`, `feature_request.yml`, and `config.yml`. `bug_report.yml` captures the affected version, expected vs. actual behavior, severity, frequency, reproduction steps, logs, regression history, environment, investigation hints, and reporter safeguards. The affected version is a required field because "latest" names a different commit depending on when it is read, and resolves differently for a package registry than for the repository. The optional checklist item about the latest version answers a separate question, whether the reporter retested there, which a reporter pinned to an older release cannot always answer. Severity and frequency are separate because they answer different triage questions: how much damage each occurrence does, and how often it occurs. `feature_request.yml` captures the problem or user need, desired outcome, use cases, scope boundaries, acceptance criteria, open questions, and supporting context. Acceptance criteria ask for a check someone can run, which is what separates a request that can be built from one that can only be guessed at. Open questions are optional and ask the requester to mark what they have not decided, so the parts that were hand-waved arrive labelled rather than indistinguishable from the parts that were settled. `config.yml` disables blank issues, which would otherwise appear alongside the forms and make every required field in them optional in practice.

\*\*`.github/PULL_REQUEST_TEMPLATE.md`\*\*: Structures a pull request so a reviewer can approve, reject, or question it without trusting the author's own assessment. Verification asks for a CI run link or raw output rather than a checkbox claiming tests passed, since a self-reported pass is indistinguishable from an unrun one. Risk is a set of factual yes/no questions about migrations, auth, secrets, public interfaces, dependencies, and data loss, each of which can be checked against the diff, rather than a self-assigned severity label. Two sections ask for what a diff cannot show: what was not verified, and which judgment calls a reviewer should examine. A scope section catches unrelated changes.

### AI Directives

States the specific operating parameters for the AI agent.

\*\*`.claude/rules/`\*\*: Core behavioral constraints, domain-specific heuristics, and strict formatting requirements the AI must follow during generation.

\*\*`.claude/skills/`\*\*: Reusable, parameterized prompts that you or the AI can invoke by name to execute complex, multi-step actions. Each `<name>/SKILL.md` is also invocable as `/name`, which is why the template ships no `.claude/commands/`: commands are the legacy single-file form of the same shortcut, and one directory holding both roles beats two directories whose boundary needs explaining.

\*\*`.claude/output-styles/`\*\*: Templates dictating the exact format of generated code, logs, or documentation to ensure the AI's output matches your personal conventions.

\*\*`.claude/agents/`\*\*: Specialized subagents equipped with their own scoped context windows for isolated tasks \(e.g., a dedicated refactoring agent\).

\*\*`.claude/workflows/`\*\*: Dynamic workflow scripts that orchestrate multiple subagents in sequence.

\*\*`.claude/agent-memory/`\*\*: Subagent persistent memory, maintaining state across sessions separately from the main session auto-memory.

\*\*`.claude/hooks/`\*\*: Shell scripts wired to tool events by `.claude/settings.json`. Ships three, each parsing its input with `jq`, which is why `tools/scripts/doctor` requires that tool while any of them is present.

`ask-outside-repo.sh` is a `PreToolUse` hook that prompts before `Edit`, `Write`, or `NotebookEdit` touches a path outside the repository. Claude Code already prompts for those writes in most permission modes, but `bypassPermissions` skips the check, and permission rules cannot cover it: rules are evaluated deny, then ask, then allow, first match wins, and the syntax has no negation, so an ask rule broad enough to catch everything outside the repository also catches everything inside it. The hook resolves symlinks and `..` before comparing against `CLAUDE_PROJECT_DIR`, so a path inside the repository cannot be used to reach outside it, and asks rather than allowing when the root cannot be determined. Writes under `CLAUDE_JOB_DIR` are allowed when that variable is set, because background sessions are told to use `$CLAUDE_JOB_DIR/tmp` as scratch space, and a prompt on sanctioned writes trains the operator to approve the prompt without reading it. Writes made through Bash redirection are not covered.

`block-config-change.sh` is a `ConfigChange` hook that blocks edits to `.claude/settings.json`, `.claude/settings.local.json`, or `.claude/skills/` from hot-reloading into the running session. Without it, a session that edits its own settings gets the new permissions immediately, which unwinds the ask gates above from inside; the same mid-session path is how a malicious skill file would take effect. The edit itself is not prevented, only the reload: the change stays on disk as an ordinary reviewable diff and applies on the next session. The matcher deliberately omits `user_settings`, which is the human's own file outside the repository, and `policy_settings`, which cannot be blocked.

`session-start.sh` is a `SessionStart` hook that prints the current branch, uncommitted changes, and recent commits as session context, restates the DocSync read-before-edit obligation, and runs `pre-commit install` when the config is present but the hook is not yet in `.git/hooks`. It runs on `startup`, `resume`, `clear`, and `compact`, which matters for the last two: `/clear` and compaction are where an agent loses its orientation, and this is what re-establishes it. The install step exists because a fresh clone has `.pre-commit-config.yaml` and none of the enforcement until someone runs the install, and the agent opening a session is the earliest moment that reliably happens.

\*\*`.claude/settings.json`\*\*: Overrides for global `settings.json`. The template fills `hooks` with the three entries above, `permissions.ask`, `permissions.deny`, `plansDirectory`, `attribution`, `allowedHttpHookUrls`, and `disableClaudeAiConnectors`, and ships the remaining containers empty so a new project sees the available sections without inheriting rules: `permissions.allow`, `permissions.additionalDirectories`, `env`, `sandbox`, `enabledPlugins`, `modelOverrides`, and `skillOverrides`. The `$schema` key points editors and agents at the schemastore definition, so an invalid key or misshapen value is flagged at edit time rather than discovered as a silently rejected settings file.

Each hook entry sets `"args": []`, which switches Claude Code from passing the command string to a shell to spawning the executable directly. With no shell in the path, a repository path containing spaces or shell metacharacters cannot break the invocation, and nothing a shell profile prints can contaminate a hook's JSON output.

`allowedHttpHookUrls: []` blocks HTTP hooks entirely. The template's hooks are all local scripts, so the only thing an HTTP hook endpoint could add here is an exfiltration channel for hook payloads, which carry file paths and tool inputs. `disableClaudeAiConnectors: true` keeps claude.ai MCP connectors from auto-connecting into sessions; the template ships `.mcp.json` empty on the same principle, that a tool surface should appear in the diff before it appears in a session.

`permissions.ask` covers the operations that are hard to undo or visible outside the repository: `git push`, `git reset --hard`, `git clean`, `git rebase`, and the `gh` commands that create or merge pull requests, cut releases, or delete the repository. Rules merge across scopes and a matching ask rule prompts in every permission mode, `bypassPermissions` included, so these hold for a clone regardless of how the session was started.

`permissions.deny` covers the secrets `.gitignore` already excludes: environment files, private keys, PKCS#12 bundles, service account files, `.npmrc`, `.pypirc`, and Terraform state. A `Read` deny also blocks the `Edit` tool and the file-reading Bash commands Claude Code recognizes, `cat` and `sed` among them, but not `Write` or `NotebookEdit`, so each path is denied twice, once for `Read` and once for `Edit`. A `Write` rule would be accepted and never consulted. The environment entries name each file rather than matching `.env.*`, which would also cover `.env.example`, the one environment file that exists to be read.

`attribution` sets `commit` and `pr` to empty strings and `sessionUrl` to `false`, which is what it takes to remove all three: the `Co-Authored-By` trailer on commits, the generated-with line in pull request descriptions, and the `Claude-Session` trailer that cloud and Remote Control sessions add. Authorship stays with the person who ran the session, which is the same claim the commit author field already makes.

Only rules that restrict belong in a committed settings file. Permission rules merge across scopes and a deny rule cannot be lifted downstream, so a rule here binds every clone. Granting capability from a repository-controlled file is the shape behind past trust-dialog bypasses, which is why Claude Code ignores `autoMode` and `permissions.defaultMode: "auto"` when they come from project settings.

Keys are omitted rather than blanked when an empty value would be invalid, because a settings file that fails validation is rejected as a whole rather than partially applied. Three kinds must stay absent until they hold a real value: enum strings such as `permissions.defaultMode` and `editorMode`, where `""` is not a permitted member; strings with a minimum length such as `outputStyle` and `apiKeyHelper`; and objects with required sub-fields such as `statusLine` and `policyHelper`, which need `type` and `command` or `path`. `model` is also omitted because its empty-string behavior is undefined.

\*\*`.mcp.json`\*\*: Configures Model Context Protocol \(MCP\) servers exclusively for this project, granting the AI read/write access to external tools like databases, APIs, or local browsers.

\*\*`CLAUDE.md`\*\*: The project-specific system prompt. Houses your conventions, common commands, and architectural context so the AI operates with the same baseline assumptions as a human developer. The template ships it with a Commands section naming the `tools/scripts/` entry points, since an agent that does not know `check` exists reaches for `npm run lint` instead; the DocSync framework, including a Delegation rule that the built-in Explore and Plan subagents never load this file, so DocSync obligations must be restated in prompts delegated to them; and a `# Compact instructions` section, which Claude Code reads during compaction to decide what survives into the summarized context.

\*\*`CLAUDE.local.md`\*\*: Personal, per-machine instructions loaded alongside `CLAUDE.md` and excluded by `.gitignore`. Not shipped; the entry exists so local preferences have a home that is not a diff.

### Source Code, Tests & Infrastructure

The core workspace where development, execution, and testing occur.

\*\*`apps/<domain or deployable service>/src/`\*\*: Project source code is stored here. Each deployable unit inside must be entirely self-contained regarding its specific dependencies.

\*\*`apps/<domain or deployable service>/tests/`\*\*: Tests for the domain or deployable service that doesn't touch other domains or services.

\*\*`apps/<domain or deployable service>/docs/specs/`\*\*: Specs describing that unit's own behavior and acceptance criteria. They change in the same commit as the code they describe.

\*\*`libs/`\*\*: Shared internal libraries, schemas, utilities, and reusable modules used by apps. They do not have to be publishable packages.

\*\*`tests/`\*\*: Repo-level tests that span multiple apps or libraries, such as integration, end-to-end, contract, benchmark, and shared fixtures. App-local tests stay under `apps/<domain or deployable service>/tests/`.

\*\*`tools/scripts/`\*\*: Portable helper scripts for local development and repo hygiene. Default scripts: `doctor` checks required tools, `check` runs local pre-commit checks, `fix` repairs formatting, `clean` removes common generated/cache files wherever they sit, and `dev` starts the local dev command when configured.

`check` runs `doctor`, then `tools/ci/ci`, then `tools/ci/security`, then the pre-commit hooks across every file. The security workflow blocks a pull request the same way the CI workflow does, so a local check that skipped it would move a dependency finding from before the commit to after the push, which is the wrong end of the loop to learn about it.

The sweep at the end exists because the commit hooks see staged files only, so a file stays unchecked until something touches it: a hook added today never reaches the files already committed, and a rename that changes a file's detected type stops its checks with nothing reporting the gap. `no-commit-to-branch` is skipped there through `SKIP`, since it reads the current branch rather than any file and would otherwise fail the whole sweep on `main` over a commit that is not being made.

`clean` searches for build output rather than removing it from the repository root, because in this layout it lands under `apps/<name>/` and `libs/<name>/`, so a root-only removal finds nothing in the ordinary case and reports success for it. The search skips `.git`, `node_modules`, and `.build`, each of which holds directories named `build` or `dist` that belong to a dependency or to git, where deleting them cleans nothing this repository produced and forces a re-fetch.

`fix` is the write half of the format check in `tools/ci/ci`, which only reports: it runs the same formatters in the same order, so it repairs exactly what that check fails on. Without it the repair step is guesswork per language, and the guess is made by whoever hit the failure. Lint autofixes stay out even where the tool offers them, because they rewrite code rather than whitespace, and a formatting diff is one a reviewer can skim while a rewritten-logic diff is one they have to read.

`doctor` checks a toolchain for every language `tools/ci/ci` knows how to run, Swift and Kotlin among them. Any language it omits inverts its purpose: it reports a healthy environment and the failure arrives later from `ci`, which is the report `doctor` runs first to prevent. Gradle adds the wrapper to that list, since `ci` drives Gradle through `./gradlew` and a manifest with no wrapper leaves those checks with no runner.

`doctor` requires `jq` whenever `.claude/hooks/ask-outside-repo.sh` is present, because that hook parses its input with it. A hook that exits non-zero for any reason other than a deliberate block is treated as a non-blocking error, so a missing `jq` lets writes outside the repository through with no prompt, which is the failure the hook exists to prevent. Deleting the hook drops the requirement.

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

\*\*`docs/plans/`\*\*: Plans written in plan mode, pointed here by `plansDirectory` in `.claude/settings.json`. The default is `~/.claude/plans`, outside the repository, where a plan is invisible to review and disappears with the machine. Under `docs/` it arrives in the diff alongside the code it describes, which is the point when a human approves the plan before the work starts.

### Root Configuration Files

The hidden files that dictate environment variables, Git behavior, and tool integrations.

\*\*`.worktreeinclude`\*\*: Lists git-ignored files to copy into new Claude worktrees, which are otherwise fresh checkouts holding tracked files only. Uses `.gitignore` syntax, and a file is copied only if it both matches a pattern here and is git-ignored, so tracked files are never duplicated. Scoped to local configuration; private keys and Terraform state are deliberately excluded, because worktrees are created and removed casually and copying key material into each one multiplies the places a credential sits on disk.

\*\*`.env`\*\*: The git-ignored config file for storing active sensitive environment variables.

\*\*`.gitignore`\*\*: Specifies intentionally untracked files and directories. Ignores local secrets (`.env` while keeping `.env.example`), private keys and credential files, Terraform state, scratch files, logs, OS/editor files, dependency folders, language caches/build outputs, container runtime state, local database files, and generated artifacts while preserving `tmp/.gitkeep`. Also excludes the per-machine Claude overrides, `.claude/settings.local.json` and `CLAUDE.local.md`: Claude Code only adds the former to git excludes when it writes the file itself, so a hand-created one would land in a commit, and in a public repository both files carry local paths and personal preferences.

Build output directories whose names also occur in source trees are anchored with a leading slash, so `/bin/` ignores a root build directory without swallowing the `src/bin/` and `cmd/*/bin/` source layouts that Rust and Go use. Patterns that nest legitimately, such as `node_modules/` and `coverage/`, stay unanchored.

\*\*`.gitattributes`\*\*: Git behavior rules for line endings, diffs, and GitHub Linguist classification. A single `* text=auto eol=lf` rule normalizes every text file to LF in both the repo and the working tree on all platforms, so per-extension rules exist only where they override it: Windows scripts stay CRLF, SVG is pinned as text, and Markdown gets a diff driver that names the enclosing heading in hunk headers. Binary files need no rules because Git's auto-detection already handles them. Language diff drivers name the enclosing function in hunk headers, so a diff shows which routine changed rather than only the surrounding class; only Git's built-in drivers take effect and an unrecognized driver name is ignored without warning.

Lockfiles carry `merge=binary` alongside `linguist-generated`. Line-wise merging of a generated file can combine two branches into a dependency set that no resolver ever produced and no branch ever tested, and that result appears as a clean merge; `merge=binary` turns it into a conflict so the resolution is to take one side and regenerate. `linguist-generated` separately collapses lockfiles in GitHub pull requests while leaving local diffs and blame intact. `docs/`, `generated/`, and `vendor/` are classified for cleaner GitHub language stats.

\*\*`.pre-commit-config.yaml`\*\*: Local guardrails that run automatically before code gets committed, catching AI syntax mistakes early. Ships gitleaks, which is the primary secret control in the template because it fires while a credential is still an uncommitted edit, and a set of hooks that catch mistakes a diff review tends to miss: merge conflict markers, oversized files, malformed YAML, JSON, or TOML, a private key committed under a name the ignore rules do not cover, a submodule pulling in code that arrives without review here, a path that collides with another on a case-insensitive filesystem, and line endings that contradict `.gitattributes`. Hooks run only after `pre-commit install` in a clone, so the file alone guarantees nothing.

shellcheck and actionlint are the only static analysis the shell scripts under `tools/` and the workflows under `.github/workflows/` receive; nothing else in the repository reads either for correctness, so a quoting bug in a branch no run exercises would otherwise reach `main` unexamined.

The two shebang hooks are what keep shellcheck honest rather than a tidiness rule. Every script under `tools/` is extensionless, so pre-commit identifies it as shell by reading its shebang, and it only reads the shebang of a file that is executable. A script committed without its executable bit is therefore skipped in silence rather than reported, which is the same failure mode as an uninstalled hook. `check-shebang-scripts-are-executable` fails that file instead, and `tools/scripts/check` depends on the same bit, since it exits early when a script it calls is not executable.

`no-commit-to-branch` blocks direct commits to `main` and `master`, so work reaches the branch through a pull request, where `PULL_REQUEST_TEMPLATE.md` and `CODEOWNERS` apply. Without it both are conventions that hold only while every commit remembers them.

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
