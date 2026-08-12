---
type: Note
---
# GitHub Repository Structure

### GitHub Automation

`.github/workflows/ci.yml`: Runs tests, linting, formatting checks, type checks, and builds. The first line of defense against AI-generated syntax errors.

`.github/workflows/release.yml`: Validates a tagged release now; packaging, publishing, binaries, and changelog artifacts are wired into `scripts/release` when the project defines them. It has only `contents: read` until then. Publishing belongs in a separate job with `contents: write`, so checkout and the build never receive a token able to modify the repository.

`.github/workflows/security.yml`: Runs dependency audits, plus a secret scan when a scanner is present.

`.github/actions/setup-toolchains/`: Installs a toolchain for each language manifest present, reading `scripts/detect github-output` for the list. `ci.yml` and `release.yml` both need every toolchain the repository uses, since `scripts/release` runs `scripts/ci` before packaging and publishing are configured, which fails when a manifest is present but its toolchain is missing. Shared because sixty duplicated lines drift, and the copy that drifts is the release one — failing just as a release is cut. `security.yml` keeps its own install steps, since it installs audit tools rather than toolchains and needs trivy for Swift and Gradle lockfiles, but it reads the same detection command rather than a copy of it.

Rule of thumb:

- `**ci.yml**`: Thinnest. One call to `scripts/ci` is often enough.
- `**release.yml**`: Thin wrapper plus GitHub release/package auth.
- `**security.yml**`: Wrapper plus GitHub-native security actions.
- `**codeql.yml**`: No `scripts/` counterpart. CodeQL runs on GitHub's infrastructure and reports into the Security tab, so there is nothing to run locally.

The goal is not "all logic outside YAML" but portable project logic in `scripts/` and provider-specific orchestration in `.github/workflows/`.

`.github/workflows/codeql.yml`: Static analysis tracing untrusted input to dangerous sinks across files, the class of bug the linters in `scripts/ci` cannot see. Runs on pull requests, on `main`, and weekly: CodeQL adds queries over time, so a scheduled run finds problems in code that has not changed.

CodeQL fails when told to analyze a language the repository lacks, so a fixed list would break every clone that does not use all of them. A detect job calls `scripts/detect codeql-matrix`, which builds the matrix from the same detection `scripts/ci` runs on, so a language this repository checks is a language CodeQL scans. Swift is pinned to a macOS runner; CodeQL does not analyze it on Linux. A detected language CodeQL has no analyzer for is skipped rather than failing the job. The matrix always includes `actions`, which scans the workflows themselves: it keeps the matrix non-empty on a repository with no application code yet, and workflows running with repository credentials are worth scanning anyway.

Findings appear in the Security tab. Code scanning is free on public repositories; private ones require GitHub Advanced Security, and without it this workflow fails at the upload step rather than silently reporting success.

`.github/dependabot.yml`: Opens one grouped weekly pull request for the action versions in `.github/workflows/` and `.github/actions/`, rather than one per action. Both are listed because `/` covers `.github/workflows/` and a root `action.yml` only, so pins inside a composite action age silently while the workflow copies stay current — which needs `directories`, since `directory` rejects the glob it accepts. A glob matching nothing is harmless here, unlike an absent ecosystem manifest, which fails the run.

GitHub-owned actions use supported major tags, so fixes within a compatible major arrive without a repository change. Third-party actions are pinned to a full commit SHA with the release tag in a comment. A movable tag lets an external repository change what runs in a credentialed workflow without a diff here; the SHA holds the code still until Dependabot proposes a reviewable update pull request. The two policies match their trust boundaries rather than pretending every action has the same one.

A second ecosystem covers the hook revisions in `.pre-commit-config.yaml`. Those pins are exact tags, not major ones: pre-commit resolves a `rev` to a single revision and offers no floating form, so nothing updates without a bump. The scanners are why it matters — they read secret and vulnerability definitions, so a stale one reports a clean tree by recognizing fewer problems, the same failure the floating `govulncheck` and `cargo-audit` installs in the security workflow avoid.

Those two are the only ecosystems listed, and not because application dependencies do not matter. An entry naming a manifest the repository does not have fails with `dependency_file_not_found` rather than being skipped, and a template cannot know which of npm, pip, cargo, gomod, or gradle a clone will use — listing all five guarantees four broken entries in every one of them. Actions and pre-commit are listed because they are the two manifests the template itself ships. The file carries the entry to copy when a real manifest arrives, since nothing otherwise reports that a `package.json` has been added and left unwatched.

What this file governs is version updates: the scheduled bumps for dependencies with nothing wrong with them. Security updates are a separate feature, driven by an alert against the dependency graph rather than by a schedule here, and they need no entry in this file — which is why a repository with no npm entry still gets a fix pull request for a vulnerable npm package. They do need the repository setting described under Repository settings below.

`.github/ISSUE_TEMPLATE/`: Contains `bug_report.yml`, `feature_request.yml`, and `config.yml`.

`bug_report.yml` captures the affected version, expected vs. actual behavior, severity, frequency, reproduction steps, logs, regression history, environment, investigation hints, and reporter safeguards. The affected version is required because "latest" names a different commit depending on when it is read, and resolves differently for a package registry than for the repository; the optional latest-version checklist item answers a separate question — whether the reporter retested there — which a reporter pinned to an older release cannot always answer. Severity and frequency stay separate: how much damage each occurrence does is a different triage question from how often it occurs.

`feature_request.yml` captures the problem or user need, desired outcome, use cases, scope boundaries, acceptance criteria, open questions, and supporting context. Acceptance criteria ask for a check someone can run, which separates a request that can be built from one that can only be guessed at. Open questions are optional and ask the requester to mark what they have not decided, so hand-waved parts arrive labelled rather than indistinguishable from settled ones.

`config.yml` disables blank issues, which would otherwise sit alongside the forms and make every required field optional in practice.

`.github/PULL_REQUEST_TEMPLATE.md`: Structures a pull request so a reviewer can approve, reject, or question it without trusting the author's own assessment. Verification asks for a CI run link or raw output rather than a checkbox claiming tests passed, since a self-reported pass is indistinguishable from an unrun one. Risk is factual yes/no questions about migrations, auth, secrets, public interfaces, dependencies, and data loss, each checkable against the diff, rather than a self-assigned severity label. Two sections ask for what a diff cannot show: what was not verified, and which judgment calls a reviewer should examine. A scope section catches unrelated changes.

### AI Directives

The specific operating parameters for the AI agent.

`.claude/rules/`: Core behavioral constraints, domain-specific heuristics, and strict formatting requirements the AI must follow during generation. A rule without `paths:` frontmatter loads at session start at the same priority as `CLAUDE.md`; a rule with it loads only when a matching file enters context, keeping a long contract out of sessions that never touch its subject.

The template ships `documentation.md`, holding the contract governing `CLAUDE.md` files: read the nearest one before editing, update the owning file after meaningful changes, the shape and section order of a child file, and the closeout pass. It carries no `paths:` frontmatter, so it loads in every session. Scoping it to Markdown would be the obvious economy and is the wrong one, because the contract is not about Markdown. Any file or folder the agent writes or edits can warrant a documentation pass — a renamed script, a new module, a changed interface — and the pass is owed on the source change, not on a `.md` file being open. A rule that loads when documentation is already open covers the sessions that were going to update docs anyway and misses every session that should have.

It lives here rather than in `CLAUDE.md` for a different reason: a document describing how `CLAUDE.md` files are written is easier to keep honest when it is not itself one, and a hundred lines of contract crowds out the operational sections a root file exists to carry.

`.claude/skills/`: Reusable, parameterized prompts that you or the AI can invoke by name to execute complex, multi-step actions. Each `<name>/SKILL.md` is also invocable as `/name`, which is why the template ships no `.claude/commands/`: commands are the legacy single-file form of the same shortcut, and one directory holding both roles beats two whose boundary needs explaining.

`.claude/output-styles/`: Templates dictating the exact format of generated code, logs, or documentation, so the AI's output matches your personal conventions.

`.claude/agents/`: Specialized subagents with their own scoped context windows for isolated tasks e.g., a dedicated refactoring agent.

`.claude/workflows/`: Dynamic workflow scripts that orchestrate multiple subagents in sequence.

`.claude/agent-memory/`: Subagent persistent memory, maintaining state across sessions separately from the main session auto-memory. Not shipped; Claude Code creates the directory when a subagent first writes to it.

`.claude/hooks/`: Shell scripts wired to tool events by `.claude/settings.json`. Ships three, each parsing its input with `jq`, which is why `scripts/doctor` requires that tool while any of them is present.

`ask-outside-repo.sh` is a `PreToolUse` hook that prompts before `Edit`, `Write`, or `NotebookEdit` touches a path outside the repository. Claude Code already prompts for those writes in most permission modes, but `bypassPermissions` skips the check, and permission rules cannot cover it: rules evaluate deny, then ask, then allow, first match wins, and the syntax has no negation, so an ask rule broad enough to catch everything outside the repository also catches everything inside it. The hook resolves symlinks and `..` before comparing against `CLAUDE_PROJECT_DIR`, so a path inside the repository cannot reach outside it, and asks rather than allows when the root cannot be determined. Writes under `CLAUDE_JOB_DIR` are allowed when that variable is set: background sessions are told to use `$CLAUDE_JOB_DIR/tmp` as scratch space, and prompting on sanctioned writes trains the operator to approve without reading.

Writes made through Bash redirection are not covered, and no hook can cover them. A `PreToolUse` hook on Bash receives the command as one string with no `file_path` to check, so catching a redirect means parsing shell syntax — which fails on variables, `eval`, heredocs, and subshells, and fails silently. Part of the gap closes elsewhere: `Read` and `Edit` permission rules apply to the file commands Claude Code recognizes in Bash, so `cat .env` prompts. What escapes both is a redirect and a subprocess that opens a file itself, such as a Python script. Enforcing that boundary takes the OS, not a hook — `sandbox` in `.claude/settings.json` confines a command and its children to the working directory, and ships empty here.

`block-config-change.sh` is a `ConfigChange` hook that stops edits to `.claude/settings.json`, `.claude/settings.local.json`, or `.claude/skills/` from hot-reloading into the running session. Without it, a session that edits its own settings gets the new permissions immediately, unwinding the ask gates above from inside; the same mid-session path is how a malicious skill file would take effect. Only the reload is blocked, not the edit: the change stays on disk as an ordinary reviewable diff and applies next session. The matcher deliberately omits `user_settings`, the human's own file outside the repository, and `policy_settings`, which cannot be blocked.

Every pipe in these scripts either ends in a variable or is written as a herestring, because `set -euo pipefail` turns SIGPIPE into a failure. A reader that exits early — `head -20`, `grep -q` — closes the pipe, the writer dies of SIGPIPE, and pipefail reports 141. In a hook that ends the run; in a detection function it reads as "not found", which is the worse case: `gradle_has_task` returned "no formatter" for a project that had one, and exited 0.

`session-start.sh` is a `SessionStart` hook that prints the current branch, uncommitted changes, and recent commits as session context, restates the read-before-edit obligation and names the rule file holding the full documentation contract, and runs `pre-commit install` when the config is present but the hook is not yet in `.git/hooks`. It runs on `startup`, `resume`, `clear`, and `compact`; the last two matter most, since `/clear` and compaction are where an agent loses its orientation and this re-establishes it. The install step exists because a fresh clone has `.pre-commit-config.yaml` and none of the enforcement until someone runs the install, and the agent opening a session is the earliest moment that reliably happens.

`.claude/settings.json`: Overrides for global `settings.json`. The template fills `hooks` with the three entries above, `permissions.ask`, `plansDirectory`, `attribution`, `allowedHttpHookUrls`, and `disableClaudeAiConnectors`, and ships the remaining containers empty so a new project sees the available sections without inheriting rules: `permissions.allow`, `permissions.deny`, `permissions.additionalDirectories`, `env`, `sandbox`, `enabledPlugins`, `modelOverrides`, and `skillOverrides`. The `$schema` key points editors and agents at the schemastore definition, so an invalid key or misshapen value is flagged at edit time rather than discovered as a silently rejected settings file.

Each hook entry sets `"args": []`, which switches Claude Code from passing the command string to a shell to spawning the executable directly. With no shell in the path, a repository path containing spaces or shell metacharacters cannot break the invocation, and nothing a shell profile prints can contaminate a hook's JSON output.

`allowedHttpHookUrls: []` blocks HTTP hooks entirely. The template's hooks are all local scripts, so all an HTTP hook endpoint could add here is an exfiltration channel for hook payloads, which carry file paths and tool inputs. `disableClaudeAiConnectors: true` keeps claude.ai MCP connectors from auto-connecting into sessions; the template ships `.mcp.json` empty on the same principle, that a tool surface should appear in the diff before it appears in a session.

`permissions.ask` covers three groups. First, operations that are hard to undo or visible outside the repository: `git push`, `git reset --hard`, `git clean`, `git rebase`, and the `gh` commands that create or merge pull requests, cut releases, or delete the repository. Rules merge across scopes and a matching ask rule prompts in every permission mode, `bypassPermissions` included, so these hold for a clone however the session was started.

Second, the secrets `.gitignore` already excludes: environment files, private keys, PKCS#12 bundles, service account files, `.npmrc`, `.pypirc`, and Terraform state. These ask rather than deny, so a session that needs one can be granted it in the moment instead of by editing this file — the tradeoff being that a denied path could not be reached at all, while an asked one is reachable by approving the prompt. A `Read` rule also covers the `Edit` tool and the file-reading Bash commands Claude Code recognizes, `cat` and `sed` among them, but not `Write` or `NotebookEdit`, so each path is listed twice, once for `Read` and once for `Edit`. A `Write` path rule would be ignored with a warning. The environment entries name each file rather than matching `.env.*`, which would also cover `.env.example`, the one environment file meant to be read.

Third, edits to any dotfile or dot directory, which is where configuration that changes how the repository behaves tends to live — `.github/workflows/`, `.pre-commit-config.yaml`, `.gitignore`, and `.claude/` itself included. Four patterns are needed because gitignore semantics differ by shape: `.*` matches dotfiles, `.*/**` reaches into dot directories, and the `**/` forms cover the nesting a single-segment pattern misses. Only `Edit` rules are written; they apply to every file-editing tool.

`attribution` sets `commit` and `pr` to empty strings and `sessionUrl` to `false`, which is what it takes to remove all three: the `Co-Authored-By` trailer on commits, the generated-with line in pull request descriptions, and the `Claude-Session` trailer cloud and Remote Control sessions add. Authorship stays with the person who ran the session, the same claim the commit author field already makes.

Only rules that restrict belong in a committed settings file. Permission rules merge across scopes and a deny rule cannot be lifted downstream, so a rule here binds every clone. Granting capability from a repository-controlled file is the shape behind past trust-dialog bypasses, which is why Claude Code ignores `autoMode` and `permissions.defaultMode: "auto"` from project settings.

Keys are omitted rather than blanked when an empty value would be invalid, because a settings file that fails validation is rejected whole rather than partially applied. Three kinds must stay absent until they hold a real value: enum strings such as `permissions.defaultMode` and `editorMode`, where `""` is not a permitted member; strings with a minimum length such as `outputStyle` and `apiKeyHelper`; and objects with required sub-fields such as `statusLine` and `policyHelper`, which need `type` and `command` or `path`. `model` is also omitted because its empty-string behavior is undefined.

`.mcp.json`: Configures Model Context Protocol MCP servers for this project only, granting the AI read/write access to external tools like databases, APIs, or local browsers.

`CLAUDE.md`: The project-specific system prompt. Houses your conventions, common commands, and architectural context so the AI operates with the same baseline assumptions as a human developer. The template ships four sections.

Commands names the `scripts/` entry points, since an agent that does not know `check` exists reaches for `npm run lint` instead. Git states what the repository enforces rather than suggests: that pre-commit refuses a commit on `main` or `master`, which operations stop for approval, and that a plan lands in the diff — each one otherwise learned by hitting it. Placeholders stops the agent before it writes code into `apps/app-name/`, described under Source Code below. Child Index is filled in as the project grows, and points at `.claude/rules/documentation.md` so the pass that builds the tree reads the contract governing it first.

Claude Code also reads a section named `Compact instructions` when it summarizes a conversation, and the template ships none: the default pass already keeps the current task, the decisions behind it, and the files changed, and a section restating that loads in every session to say nothing new. Add one when a project has a specific thing worth preserving that the default drops.

`CLAUDE.local.md`: Personal, per-machine instructions loaded alongside `CLAUDE.md` and excluded by `.gitignore`. Not shipped; the entry exists so local preferences have a home that is not a diff.

### Source Code, Tests &amp; Infrastructure

The core workspace where development, execution, and testing occur.

An `apps/` entry is one deployable service or one durable domain boundary: the unit that owns its own dependencies, tests, and specs. The template ships one, `apps/app-name/`, as a placeholder. `CLAUDE.md` carries a Placeholders section telling the agent to ask what the unit is called before writing code into it, convert the answer to kebab-case, rename with `git mv`, update references, and then delete the section. The prompt has to state what an `apps/` entry is, since the question is unanswerable without it — and a placeholder that only looks like a convention gets kept rather than replaced.

`apps/<domain or deployable service>/src/`: Project source code. Each deployable unit inside must be entirely self-contained regarding its specific dependencies.

`apps/<domain or deployable service>/tests/`: Tests for the domain or deployable service that don't touch other domains or services.

`apps/<domain or deployable service>/docs/specs/`: Specs describing that unit's own behavior and acceptance criteria. They change in the same commit as the code they describe.

`libs/`: Shared internal libraries, schemas, utilities, and reusable modules used by apps. They do not have to be publishable packages.

`tests/`: Repo-level tests spanning multiple apps or libraries: integration, end-to-end, contract, benchmark, and shared fixtures. App-local tests stay under `apps/<domain or deployable service>/tests/`.

`scripts/`: Every portable shell script, whether a person runs it or a workflow does. `doctor` checks local tools and clone configuration, `repo-settings check` inspects hosted GitHub administration state, `check` runs the full local gate, `fix` repairs formatting, `clean` removes generated files wherever they sit, `dev` starts the local dev command, `ci`, `security`, `release`, and `detect` are the ones `.github/workflows/` calls, and `adr-index` is called by pre-commit to regenerate `docs/adr/index.md`. One folder rather than a `ci/` and a `scripts/`, because the split it would need does not hold: `check` calls `ci` and `security`, `release` calls `ci`, and every script here sources the same detection, so a file's caller is not a property that stays put. At the root rather than under `tools/`, which holds helpers that have to be built; see `tools/` below. Scripts, not YAML, because they should run locally the same way they run in GitHub Actions.

`check` runs `doctor`, every `scripts/tests/*-test`, `scripts/ci`, `scripts/security`, then the pre-commit hooks across every file. The security workflow blocks a pull request the same way the CI workflow does, so a local check that skipped it would move a dependency finding from before the commit to after the push, the wrong end of the loop to learn about it. Hosted repository settings stay outside this gate so `check` and the `dev` command that calls `doctor` remain usable offline.

The sweep at the end exists because the commit hooks see staged files only, so a file stays unchecked until something touches it: a hook added today never reaches files already committed, and a rename that changes a file's detected type stops its checks with nothing reporting the gap. `no-commit-to-branch` is skipped there through `SKIP`, since it reads the current branch rather than any file and would otherwise fail the whole sweep on `main` over a commit that is not being made.

`clean` searches for build output rather than removing it from the repository root, because in this layout it lands under `apps/<name>/` and `libs/<name>/`, so a root-only removal finds nothing in the ordinary case and reports success for it. The search skips `.git`, `node_modules`, and `.build`, each holding directories named `build` or `dist` that belong to a dependency or to git, where deleting them cleans nothing this repository produced and forces a re-fetch.

`fix` is the write half of the format check in `scripts/ci`, which only reports: it runs the same formatters for the same languages, so it repairs exactly what that check fails on. Without it the repair step is guesswork per language, and the guess is made by whoever hit the failure. Lint autofixes stay out even where offered, because they rewrite code rather than whitespace, and a formatting diff is one a reviewer can skim while a rewritten-logic diff is one they have to read.

`doctor` checks a toolchain for every language `scripts/ci` knows how to run, Swift and Kotlin among them. Any language it omits inverts its purpose: it reports a healthy environment and the failure arrives later from `ci`, the report `doctor` runs first to prevent. It therefore fails on a language detection knows about and it has no `toolchain_<language>` function for, rather than passing over it. Gradle adds the wrapper to that list, since `ci` drives Gradle through `./gradlew` and a manifest with no wrapper leaves those checks with no runner.

`dev` refuses to guess when several stacks are present, exiting non-zero with the detected stacks and the `apps/` entries that can be named. A dev server is one foreground process, so with two stacks there is no correct one to start and starting either silently runs the wrong one, reported as a success. With exactly one stack it runs it. A name matching no `apps/` directory fails as well, rather than being ignored and starting the root server instead.

`doctor` requires `jq` whenever `.claude/hooks/ask-outside-repo.sh` is present, because that hook parses its input with it. A hook that exits non-zero for any reason other than a deliberate block is treated as a non-blocking error, so a missing `jq` lets writes outside the repository through with no prompt — the failure the hook exists to prevent. Deleting the hook drops the requirement.

`doctor` treats an uninstalled pre-commit hook as a missing tool. `.pre-commit-config.yaml` is tracked, but the hook it describes lives in `.git/hooks/`, local to a clone and never committed, so a fresh clone has the config and none of the enforcement. Nothing surfaces that on its own: commits succeed exactly as before while the configured hooks, the secret scan among them, never run. `doctor` therefore fails when the config is present but either the tool or the installed hook is missing, and stays silent when there is no config to honor.

`repo-settings check` reports the two settings under Repository settings that a clone cannot enforce for itself: push protection and an active branch ruleset. Both are remote state, so nothing in the tree reveals whether they are on, and both back a guarantee made here — the pre-commit hook keeping commits off `main` is absent in a fresh clone, and the CI secret scan runs after a push rather than before it. Keeping this inspection out of `doctor` makes `doctor`, `check`, and `dev` fast and usable offline rather than coupling ordinary local work to GitHub authentication and API availability.

It reports and never changes settings. Enabling either writes to state the whole repository sees, and a ruleset write replaces rather than merges, so an automatic correction could silently revert a deliberate loosening. The command names the fix instead, the way `doctor` does for the pre-commit hook and Gradle wrapper.

Three answers are possible and the difference matters: enabled, disabled, or not offered for the repository's plan and visibility. Push protection needs GitHub Advanced Security on a private repository and rulesets need Pro, while both are free on a public one — and the API is unhelpful about it, returning success for a request to enable push protection on a plan without it while leaving the setting off. Reporting that as disabled would send someone to a settings page with no such switch on it. Each of these is optional rather than required, since a clone with no remote yet, no `gh`, or no admin on the repository is an ordinary state and not a broken environment.

`ci` and `security` distinguish a check that ran and passed from one that never ran, and treat the second as a failure whenever the check was expected. If a project manifest is present but its toolchain is missing, the run fails rather than reporting success for work it did not do. The workflows install only the toolchains a repository actually uses, detected from its manifests.

Every check runs for every language present, not for the first one detected. `ci` defines one function per check and language — `lint_python`, `test_node`, and so on — and dispatches by name over the detected list; `security` does the same with `audit_<language>`, and `fix` with `format_<language>`. A repository is expected to gain a language at any time, and a chain that stopped at its first match meant a Python CLI adding a JavaScript UI had pytest, ruff, and mypy silently stop running while CI stayed green. Each check reports every outcome it produced rather than the worst one, so a language that passed stays visible next to one with no runner.

Three runners contradict the pass/fail rule and are special-cased rather than passed through. pytest exits 5 when it collected no tests, where every other runner here exits 0, so a Python project fails its first run before a test is written; `test_python` matches that code, says so, and returns 0, while a real failure (1) and a collection error (2) still fail. `npm init -y` writes a placeholder test script that prints an error and exits 1, so `has_npm_script` compares against that exact string and treats it as no script at all — the check then reports no runner, which is true, instead of a failing suite, which is not. `uv run <tool>` exits 2 when the tool is not installed, the same shape as a tool that ran and found problems, so `uv_run` looks the tool up first and reports its absence as no runner rather than blaming the code for a missing dependency.

That failure names its own fix, because two different problems produce it: a language nobody has wired up yet, and a wired-up language whose tool is missing from the machine. The message separates them, names the `<check>_<language>` function to add, and lists every file a new language has to reach — the list lives in `scripts/libs/detect.sh` beside the detection it describes, so it cannot age separately from it. The second case is sent to `doctor`, which names the tool and how to install it. The message also states that a check with nothing to do returns 0 with a comment saying why, the way `build_python` does; without that, the fix for an interpreted language's build step is to invent one.

`scripts/security` runs a dependency audit and, when a scanner is installed, a secret scan. Secret prevention belongs to GitHub push protection rather than CI: push protection rejects a secret before it reaches the remote, while a CI scan reports one already published and only rotatable. The workflow therefore installs no scanner, since doing so meant downloading an unverified binary inside the job responsible for supply-chain safety; gitleaks runs from `.pre-commit-config.yaml` instead, where it sees a secret while it is still an unstaged edit. The CI secret scan stays as a backstop that runs when a scanner happens to be present and never blocks on its absence.

Checks GitHub already provides are left to GitHub. Dependabot security updates open the pull request that fixes a vulnerable dependency rather than only reporting it, and push protection blocks secrets outright, so neither is reimplemented here. Both are repository settings rather than tracked files, and both have to be switched on for that division of labor to hold — see Repository settings below. Left off, `security` fails a pull request over a CVE and nothing opens the upgrade that clears it. Code scanning, license policy, and container image scanning are deliberately absent: each answers a question this repository does not currently have, and a check that cannot fail meaningfully teaches people to ignore the ones that can.

Manifest detection has to list every language the repository supports, because an unrecognized manifest reads as no project at all and exits successfully with nothing checked, indistinguishable from a passing run. `Package.swift`, `settings.gradle.kts`, and `build.gradle.kts` therefore count as manifests alongside the others.

`scripts/libs/`: Shared shell libraries private to the `scripts/` entry points. Its plural name matches root `libs/`: each file is a library, while the directory holds the collection. Nothing here is a command, so files have no shebang or executable bit; callers source them by an absolute path rooted at the repository.

`scripts/libs/detect.sh`: The detection library, defined once. Detection was previously copied across eight files and the copies answered the same question differently — one pruned `.build/` and another did not. A language wired into some of them is worse than one wired into none: the checks that know about it pass, and the ones that do not report a clean run over work they never looked at. `DETECT_LANGUAGES` is the single list of supported languages, and every caller iterates it instead of keeping its own.

`scripts/detect`: The same detection over a command line, because a workflow cannot source a bash library. `github-output` writes `language=true|false` flags for a step's `if:`, `codeql-matrix` writes the matrix JSON, and `check-orphans` reports the failure below. `setup-toolchains`, `security.yml`, and `codeql.yml` call it rather than each carrying detection of their own.

Every check runs from the repository root against a root workspace manifest, so a package nested under `apps/` or `libs/` whose language has no root manifest is invisible: nothing lints it, tests it, or audits it, and the run is green because no check ever looked. That fails loudly instead, naming the file and the root manifest to add — `go work init` for a Go module, an `include()` entry for a Gradle project, a root manifest for the rest. It catches "no root manifest at all", not "root manifest that omits this package"; reading membership out of npm workspaces, uv sources, or Cargo members needs a parser per tool and is out of scope.

Swift is detected by searching rather than by checking the repository root, being the one supported language with no root manifest: SwiftPM has no workspace file, so packages sit at `apps/<name>/` and `libs/<name>/` and nothing at the root names them. A root-only check finds no manifest in a Swift repository and reports the silent pass described above. It is exempt from the orphan rule for the same reason — nested packages are what a Swift repository is supposed to look like. The search skips `.build/`, which holds checked-out dependencies carrying manifests of their own, along with `node_modules`, `target`, `.venv`, `venv`, and `vendor`. For the same reason the Swift commands run once per package directory instead of once at the root, and every package runs even after one fails, so a single broken package does not hide the state of the rest.

Detection reads through pipes that end in a variable or a `-print -quit` test, never into a reader that exits early. Under `set -euo pipefail` a `grep -q` or `head` closing the pipe kills the writer with SIGPIPE and `pipefail` reports 141, which a detection function reads as "absent" — a wrong answer that is silent rather than loud, and the one failure mode this whole file exists to remove.

`scripts/tests/`: `capabilities-test` asserts that every language present is dispatched to every check. It is the one property nothing else reports on: a language dropped from dispatch produces a shorter green run, not a failure. Fixtures are scaffolded into temp directories and asserted against `CI_DRY_RUN=1`, which prints the check and language pairs `ci` would run and runs none of them, so the result comes from wiring alone and is identical on any machine with no toolchain installed. `health-checks-test` stubs `gh` to prove that `doctor` and `dev` stay offline and that hosted inspection happens only through `repo-settings check`. `adr-index-test` asserts that the generated ADR index converges and that pre-commit actually invokes the hook, including on a deletion — the script passing while nothing runs it is the failure a script-level test cannot see. `libs/harness.sh` holds the assertion counting the three share; it is sourced rather than executed, like `scripts/libs/detect.sh` and for the same reason. These live beside the scripts they test rather than in the root `tests/`, which is reserved for the project's own cross-app tests. Every `*-test` runs from `scripts/check` and directly from `ci.yml` before toolchain setup.

`scripts/release` runs `scripts/ci` before packaging and publishing are configured, so the release workflow installs the same toolchains as the CI workflow; without them the pre-release check fails on every tagged release for exactly the reason it is there. It refuses to report success while packaging is unconfigured, rather than printing that nothing is configured and exiting 0, so a green release always means an artifact was produced. The workflow therefore has only `contents: read` today. When the project adds a publisher, it goes in a separate job with `contents: write`, after this validation job succeeds, leaving checkout and the build unable to modify the repository. The tag comes from an explicit argument before `GITHUB_REF_NAME`: a `workflow_dispatch` run is dispatched against a branch and its ref is not the tag being released. The workflow passes that input through the environment rather than `${{ }}` interpolation, which would place a user-supplied string directly into a shell command.

Swift and Kotlin differ from the rest in two ways. Neither has a first-party dependency audit, so `scripts/security` audits both through trivy reading their lockfiles; because Gradle locking is opt-in, a repository with no `gradle.lockfile` has no resolved versions to audit and reports no runner rather than scanning declared version ranges, which would report findings for versions the build may never select. Gradle also exposes lint and format tasks only when the matching plugin is applied, so `scripts/ci` queries the task list and runs `ktlintCheck` or `detekt` if present rather than assuming either exists.

`tools/`: Empty but for a `.gitkeep`, and the counterpart to `scripts/`. A helper that has to be built before it runs — a Go linter, a code generator, a protobuf plugin — goes here as `tools/<name>/`, one directory per program, carrying its own manifest and source. A helper that is a shell file goes in `scripts/`. The split is by artifact, not by caller: a program here can be invoked from a workflow and a script there can be run by hand, and both happen. Splitting on caller instead is the arrangement that decays, since a script written for CI is the first thing someone runs locally to reproduce a failure.

A program added here brings a manifest, and the orphan rule described above fires on it until the root workspace covers it — `go work init ./tools/<name>` for a Go helper, an equivalent entry for the rest. That is the rule working rather than misfiring: a helper that lints this repository is code, and a copy of it sitting outside every check is the one place a bug hides from the tooling it belongs to.

The distinction is worth the empty directory because the two folders age differently. `scripts/` stays flat, extensionless, and readable without a build step, and a compiled program dropped into it arrives with a manifest that the root-level checks then have to be told to ignore. A shell script filed under `tools/` costs less, but it removes the reason `tools/` exists and leaves a repository where neither name predicts what a file is.

`tmp/`: Git-ignored scratch space for the AI to write temporary files, download artifacts, or dump logs. Includes a `.gitkeep` to maintain the directory structure.

### Documentation &amp; Knowledge Base

Durable knowledge that grounds the AI in the project's specific reality and operational standards.

`TODO.md`: A plain-text to-do of backlogged, informal tasks

`docs/adr/`: Architectural Decision Records e.g., `0001-initial-stack.md`. Explains why decisions were made so the AI doesn't try to revert or fundamentally alter established systems. Keep one repo-wide numbered sequence here so decisions stay discoverable without knowing which app to look in. An app may keep its own `docs/adr/` once local decisions would drown the repo-wide ones; when it does, link it from this folder's index and never reuse numbers across scopes. `0000-template.md` is the template: copy it for each new decision, replace every frontmatter line and placeholder, and number from `0001`. `index.md` here is generated by `scripts/adr-index` from each record's frontmatter and is never hand-edited, so the roll-up of which decisions are still live cannot drift from the records it summarizes. The hook that rebuilds it runs on every commit rather than on a path filter: pre-commit's staged-file list excludes deletions, and removing a record is precisely when the index goes stale, so a filter would skip the one commit that needed it. It writes nothing until a real record exists, so a freshly generated repository does not carry an index of nothing.

`docs/specs/`: Specs for contracts that span apps, such as service-to-service APIs and shared schemas. Specs for a single unit stay under `apps/<domain or deployable service>/docs/specs/`.

`docs/lessons.md`: Hard-won knowledge about this repository specifically: the provider quirks and recurring mistakes an agent would otherwise rediscover. Ships as a template — frontmatter, the rules for writing a lesson, and one worked example — and `.claude/rules/documentation.md` points at it. It ships rather than being created on demand because a rule naming a file that does not exist makes writing one the first documentation pass's job, in a session that started out doing something else. It ships with a format because an empty file leaves the first agent to write into it inventing one. Replace the frontmatter and placeholders on first use; keep the "How to add a lesson" section and drop the example once real lessons replace it.

`docs/plans/`: Plans written in plan mode, pointed here by `plansDirectory` in `.claude/settings.json`. The default is `~/.claude/plans`, outside the repository, where a plan is invisible to review and disappears with the machine. Under `docs/` it arrives in the diff alongside the code it describes — the point when a human approves the plan before the work starts.

### Root Configuration Files

The hidden files that dictate environment variables, Git behavior, and tool integrations.

`.worktreeinclude`: Lists git-ignored files to copy into new Claude worktrees, which are otherwise fresh checkouts holding tracked files only. Uses `.gitignore` syntax; a file is copied only if it both matches a pattern here and is git-ignored, so tracked files are never duplicated. Scoped to local configuration — private keys and Terraform state are deliberately excluded, because worktrees are created and removed casually and copying key material into each one multiplies the places a credential sits on disk.

`.env`: The git-ignored config file for storing active sensitive environment variables.

`.gitignore`: Specifies intentionally untracked files and directories. Ignores local secrets (`.env` while keeping `.env.example`), private keys and credential files, Terraform state, scratch files, logs, OS/editor files, dependency folders, language caches/build outputs, container runtime state, local database files, and generated artifacts while preserving `tmp/.gitkeep`. Also excludes the per-machine Claude overrides, `.claude/settings.local.json` and `CLAUDE.local.md`: Claude Code only adds the former to git excludes when it writes the file itself, so a hand-created one would land in a commit, and in a public repository both files carry local paths and personal preferences.

Build output directories whose names also occur in source trees are anchored with a leading slash, so `/bin/` ignores a root build directory without swallowing the `src/bin/` and `cmd/*/bin/` source layouts Rust and Go use. Patterns that nest legitimately, such as `node_modules/` and `coverage/`, stay unanchored.

`.gitattributes`: Git behavior rules for line endings, diffs, and GitHub Linguist classification. A single `* text=auto eol=lf` rule normalizes every text file to LF in both the repo and the working tree on all platforms, so per-extension rules exist only where they override it: Windows scripts stay CRLF, SVG is pinned as text, and Markdown gets a diff driver naming the enclosing heading in hunk headers. Binary files need no rules; Git's auto-detection already handles them. Language diff drivers name the enclosing function in hunk headers, so a diff shows which routine changed rather than only the surrounding class; only Git's built-in drivers take effect and an unrecognized driver name is ignored without warning.

Lockfiles carry `merge=binary` alongside `linguist-generated`. Line-wise merging of a generated file can combine two branches into a dependency set no resolver ever produced and no branch ever tested, and that result appears as a clean merge; `merge=binary` turns it into a conflict so the resolution is to take one side and regenerate. `linguist-generated` separately collapses lockfiles in GitHub pull requests while leaving local diffs and blame intact. `docs/`, `generated/`, and `vendor/` are classified for cleaner GitHub language stats.

`.pre-commit-config.yaml`: Local guardrails that run automatically before code gets committed, catching AI syntax mistakes early. Ships gitleaks, the primary secret control in the template because it fires while a credential is still an uncommitted edit, plus hooks catching mistakes a diff review tends to miss: merge conflict markers, oversized files, malformed YAML, JSON, or TOML, a private key committed under a name the ignore rules do not cover, a submodule pulling in code that arrives without review here, a path colliding with another on a case-insensitive filesystem, and line endings contradicting `.gitattributes`. Hooks run only after `pre-commit install` in a clone, so the file alone guarantees nothing.

shellcheck and actionlint are the only static analysis the shell scripts under `scripts/` and the workflows under `.github/workflows/` receive; nothing else in the repository reads either for correctness, so a quoting bug in a branch no run exercises would otherwise reach `main` unexamined.

The two shebang hooks keep shellcheck honest rather than enforcing tidiness. Every script under `scripts/` is extensionless, so pre-commit identifies it as shell by reading its shebang, and it only reads the shebang of an executable file. A script committed without its executable bit is therefore skipped in silence rather than reported, the same failure mode as an uninstalled hook. `check-shebang-scripts-are-executable` fails that file instead, and `scripts/check` depends on the same bit, since it exits early when a script it calls is not executable.

shellcheck runs with `-x`, which follows `source` into `scripts/`. Without it every script sourcing the detection library fails on SC1091 rather than being analyzed against what it sourced. `scripts/libs/detect.sh` is the exception to the shebang rule above: it is sourced, never run, so it carries no shebang and no executable bit, and its `.sh` extension is what identifies it as shell.

`check-added-large-files` keeps its 500KB default, which is the number to argue with rather than the presence of the hook. It weighs only newly added files, so nothing already tracked is constrained as it grows, and a file matched by a git-lfs filter in `.gitattributes` is exempt at any size — the limit bounds one commit, not the repository, and a project built from this template is free to become as large as it needs to.

What it stops is the file nobody meant to add: a build artifact, a database dump, a recording dropped into the working tree. That mistake is worth a gate because it is the one that cannot be undone by deleting the file — the blob stays in history, and removing it means a rewrite every clone has to be told about. Every other hook here catches something a later commit can fix.

Raising the number is the wrong response to a single large file, since it widens the gate for everything to admit one thing. `exclude` names that file instead, where the exception is visible and reviewable in the diff that adds it. Raise `--maxkb` only when the floor for the whole repository has genuinely moved.

`no-commit-to-branch` blocks direct commits to `main` and `master`, so work reaches the branch through a pull request, where `PULL_REQUEST_TEMPLATE.md` applies — and `CODEOWNERS` too on a public repository, which is the only place the template ships one. Without it the template is a convention that holds only while every commit remembers it. The hook is local to a clone, so it stops an accident rather than a decision; a branch protection rule is what enforces review on the remote.

### Repository Settings

Nothing in this section is a file. Each is a switch in the repository's Settings tab, and each one carries part of a guarantee the tracked files make on their own behalf — which means a clone of this template is not finished when the files land. A setting left off does not fail anything; it removes the half of a pair that fixes what the other half reports.

Dependabot security updates: The feature that opens the pull request upgrading a vulnerable dependency. `scripts/security` fails a pull request that introduces a CVE, and this is what resolves it — the reason the audit does not also try to write an upgrade. Unlike version updates it reads the dependency graph rather than `.github/dependabot.yml`, so it covers npm, pip, cargo, and the rest with no entry added for them, and it is the answer to why that file lists only actions and pre-commit. Off, the audit blocks and no fix arrives, which reads as the audit being the problem.

Dependabot alerts: The prerequisite for the above; security updates fire on an alert. Worth enabling alone even if the update pull requests are unwanted, since it is the only mechanism that reports a CVE disclosed against a dependency already committed. `scripts/security` catches those only on the next run of a workflow that had no reason to trigger.

Push protection: Rejects a push containing a recognized secret, for the timing reason given under `scripts/security` above. `repo-settings check` reports whether it is on. It is the only one of the three secret defenses that survives a clone without the pre-commit hook installed and a workflow that installs no scanner, which is what the other two are.

Branch protection on `main`: `no-commit-to-branch` blocks a direct commit locally, but the hook lives in `.git/hooks/` and a fresh clone does not have it. `repo-settings check` reports whether a ruleset covers the gap. A rule on the remote is what makes the pull request path the only path, and what makes `CODEOWNERS` load-bearing rather than advisory.

Secret scanning and code scanning are free on public repositories and require GitHub Advanced Security on private ones. `codeql.yml` fails at its upload step without code scanning enabled rather than reporting a silent success, so on a private repository that workflow is either paid for or removed.

### Public / Open Source Additions

These files govern community interaction and legal usage. They are only necessary if the repository is public and accepting external contributions. GitHub reads most of them from the repository root, `.github/`, or `docs/`, and shows the same file in the same places wherever it sits; `CODEOWNERS`, `FUNDING.yml`, and `CITATION.cff` are the exceptions noted below. None of them ship with the template, which is a private-repository baseline; this section is the checklist for the day one goes public.

`README.md`: The public orientation page: what the project does, how to install it, and how to use it.

`.github/FUNDING.yml`: Displays a sponsor button in your repository, raising the visibility of funding options for your open source project. Unlike the rest of this section it is read only from `.github/`; a copy at the repository root is ignored, and the missing button is the only symptom.

`CONTRIBUTING.md`: Guidelines for external developers on submitting pull requests, running tests, and adhering to code style.

`SECURITY.md`: The project's security policy, supported versions, and the private channel for reporting vulnerabilities.

`LICENSE`: The legal document outlining the usage, modification, and distribution rights of the code.

`CODE_OF_CONDUCT.md`: The baseline rules for community behavior and expectations for professional interaction.

`SUPPORT.md`: Routes users to help, filtering general troubleshooting out of the core issue tracker.

`CONTRIBUTORS.md`: A public ledger crediting individuals who have contributed code or documentation. GitHub also recognizes `AUTHORS`, which is a narrower list: the people whose contributions are legally significant for copyright. The two only need to be separate files under a contributor licence agreement or copyright assignment, where who holds the copyright is a different question from who to thank.

`CODEOWNERS`: The definitive list of core team members with write access and merge authority. Read from the repository root, `.github/`, or `docs/`, and nowhere else. On its own it only requests reviewers; a branch protection rule requiring code owner review is what makes that request binding.

`CHANGELOG.md`: A per-version record of what changed. GitHub Releases already is one — each release carries a tag, a date, and notes — so the question is not whether to keep a changelog but whether to keep a second copy of it in the tree. It is not a question of what the entries can say: a release body can be hand-written and a file can be generated, so both surfaces hold whatever the project is willing to write.

What differs is when the entry gets written. A file is edited inside the pull request that makes the change, by the author, while the reason is still in their head, and the reviewer reads the entry against the diff and can say that the return type changed and the entry does not mention it. A release note is written at tag time, by whoever cuts the release, reconstructing weeks of merged pull requests after the fact. A draft release can be edited ahead of the tag, but it is not part of the diff, so nobody reviews the entry next to the change it describes. The mechanism the file gives you is the `## [Unreleased]` section: entries accumulate there one pull request at a time and are cut into a version when the tag is made.

That argument needs a reviewer who is not the author, so it buys nothing on a solo repository and grows as the project takes outside contributions. A smaller point in the file's favour is that it lives in git, while release notes live in GitHub's database and do not survive a move to another host. Against both, a hand-maintained file drifts from the tags the moment a release is cut without updating it, and a changelog that disagrees with the releases page is worse than neither.

So pick one and let the other point at it. Publishing from the file is the common resolution: the release step reads the section for the tag and posts it as the release body, so one edit produces both and they cannot disagree. `scripts/release` currently refuses to publish while packaging is unconfigured, and that is where the wiring goes; `release.yml` already fetches full history so a generator can reach the previous tag.

`CITATION.cff`: Machine-readable citation metadata, which GitHub surfaces as a "Cite this repository" button. Root only. Worth adding for research software and academic work, and nothing otherwise.

`GOVERNANCE.md`: The political structure of the repository: how decisions are made, how maintainers are elected, and how disputes are resolved.

`.env.example`: A sanitized template of `.env` showing required variables without exposing actual secrets.

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
