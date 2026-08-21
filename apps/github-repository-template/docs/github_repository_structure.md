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

A `scanning` job runs first and fails when code scanning cannot accept results. Code scanning takes them from a public repository, or from a private one with GitHub Advanced Security; without it CodeQL analyzes the code and then dies at the upload step, so checking first turns an hour of work into a failure that arrives in seconds and names what is wrong.

It fails rather than skips, and that is the load-bearing choice. A skipped job renders the workflow green, so a repository with no scanning coverage would sit on the checks list looking exactly like one that scanned clean — the same false green that `continue-on-error` around the upload would produce, reached by a different route. Absent coverage is a real finding about the repository, and it stays red until someone deletes the workflow deliberately and records that under `features` in `.repo-template.json`. It is a separate job so the red check reads `Code scanning enabled` instead of a language-detection failure that would misdescribe the problem.

Visibility is read from the API rather than from `github.event.repository.visibility`, whose payload GitHub documents as "Not applicable" for `schedule`. Taken from the event, the weekly run would compare a null against `public` and fail a public repository every Tuesday. A failed lookup fails the job rather than defaulting either way, so a token or network problem cannot be mistaken for a repository that should not be scanned.

`zizmor.yml`: Configuration for zizmor, which runs through pre-commit beside actionlint rather than as a workflow. It audits the workflows for security defects — template injection reaching a `run:` block, credential persistence, an unpinned third-party action, permissions wider than the job needs. actionlint asks whether a workflow is valid; zizmor asks whether a valid workflow is unsafe. Neither reports the other's findings. It is a hook rather than a workflow because the finding is about a file in the diff, and because a workflow auditing workflows reports a problem with `ci.yml` as a failure of `ci.yml`.

The file sets one thing: the `unpinned-uses` policy. Since v1.20.0 zizmor requires hash pins on every action, while this repository ref-pins first-party actions and hash-pins third-party ones. That split is a trust boundary rather than an inconsistency — a first-party action moving under its tag is a compromise of the platform the workflow already runs on, while a third-party action is a different repository with different owners, which is how tj-actions/changed-files was compromised. The hook runs at `--min-severity medium` with nothing suppressed to reach it, so the threshold stays one visible line instead of a list nobody revisits.

`.github/dependabot.yml`: Opens one grouped weekly pull request for the action versions in `.github/workflows/` and `.github/actions/`, rather than one per action.

`.github/ISSUE_TEMPLATE/`: Contains `bug_report.yml`, `feature_request.yml`, and `config.yml`.

`bug_report.yml` captures the affected version, expected vs. actual behavior, severity, frequency, reproduction steps, logs, regression history, environment, investigation hints, and reporter safeguards.

`feature_request.yml` captures the problem or user need, desired outcome, use cases, scope boundaries, acceptance criteria, open questions, and supporting context.

`config.yml` disables blank issues, which would otherwise sit alongside the forms and make every required field optional in practice.

`.github/PULL_REQUEST_TEMPLATE.md`: Structures a pull request so a reviewer can approve, reject, or question it without trusting the author's own assessment.

### AI Directives

The specific operating parameters for the AI agent.

`.claude/rules/`: Core behavioral constraints, domain-specific heuristics, and strict formatting requirements the AI must follow during generation. A rule without `paths:` frontmatter loads at session start at the same priority as `AGENTS.md`; a rule with it loads only when a matching file enters context, keeping a long contract out of sessions that never touch its subject. Ships empty.

`.claude/skills/`: Reusable, parameterized prompts that you or the AI can invoke by name to execute complex, multi-step actions. Each `<name>/SKILL.md` is also invocable as `/name`, which is why the template ships no `.claude/commands/`: commands are the legacy single-file form of the same shortcut, and one directory holding both roles beats two whose boundary needs explaining. Ships empty.

`.claude/output-styles/`: Templates dictating the exact format of generated code, logs, or documentation, so the AI's output matches your personal conventions. Ships empty.

`.claude/agents/`: Specialized subagents with their own scoped context windows for isolated tasks e.g., a dedicated refactoring agent.

`.claude/workflows/`: Dynamic workflow scripts that orchestrate multiple subagents in sequence.

`.claude/agent-memory/`: Subagent persistent memory, maintaining state across sessions separately from the main session auto-memory. Not shipped; Claude Code creates the directory when a subagent first writes to it.

`.claude/hooks/`: Shell scripts wired to tool events by `.claude/settings.json`. Ships empty.

`.claude/settings.json`: Overrides for global `settings.json`. The template fills `permissions.ask`, `permissions.deny`, `plansDirectory`, `attribution`, `allowedHttpHookUrls`, `disableClaudeAiConnectors`, `env` (CLI environment defaults carried over from the author's global settings), and `skipDangerousModePermissionPrompt`, and ships the remaining containers empty so a new project sees the available sections without inheriting rules: `hooks`, `permissions.allow`, `permissions.additionalDirectories`, `sandbox`, `enabledPlugins`, `modelOverrides`, and `skillOverrides`.

`permissions.deny` carries the secret paths, each pattern written twice — once as `Read` and once as `Edit`. A `Read` deny already blocks the Edit and Write tools, but not `NotebookEdit`, and the Write half requires Claude Code v2.1.228 or later; the `Edit` twin closes both gaps rather than assuming a floor version in a repository the template cannot inspect. `permissions.allow` ships empty and should stay that way: allow rules have no effect under `bypassPermissions`, so a rule added there buys nothing for anyone running that mode while still granting capability to every clone that accepts the trust dialog.

`permissions.ask` carries the irreversible git and `gh` commands, plus three path families a session should not touch on its own initiative: any dotfile or dot-folder, anything under a `src/` directory, and anything directly in the repository root. Those path rules cover creating and modifying, which go through `Edit`, `Write`, or `NotebookEdit`. They cannot cover deleting, which goes through the shell — a Bash rule matches a command prefix and cannot read the path in its argument — so `Bash(rm:*)` and `Bash(git rm:*)` sit alongside them and prompt on every removal rather than only on a gated path. `.npmrc` and `.pypirc` are here rather than in `deny` deliberately: both are ordinary package-manager configuration a session has real reason to read, and the credential in one is a line rather than the whole file.

`.mcp.json`: Configures Model Context Protocol MCP servers for this project only, granting the AI read/write access to external tools like databases, APIs, or local browsers.

`AGENTS.md`: The project-specific system prompt. Houses your conventions, common commands, and architectural context so the AI operates with the same baseline assumptions as a human developer. The template ships four sections.

`CLAUDE.local.md`: Personal, per-machine instructions loaded alongside `AGENTS.md` and excluded by `.gitignore`. Not shipped; the entry exists so local preferences have a home that is not a diff.

### Source Code, Tests & Infrastructure

The core workspace where development, execution, and testing occur.

An `apps/` entry is one deployable service or one durable domain boundary: the unit that owns its own dependencies, tests, and specs.

`apps/<domain or deployable service>/src/`: Project source code. Each deployable unit inside must be entirely self-contained regarding its specific dependencies.

`apps/<domain or deployable service>/tests/`: Tests for the domain or deployable service that don't touch other domains or services.

`apps/<domain or deployable service>/docs/specs/`: Specs describing that unit's own behavior and acceptance criteria. They change in the same commit as the code they describe.

`libs/`: Shared internal libraries, schemas, utilities, and reusable modules used by apps. They do not have to be publishable packages.

`tests/`: Repo-level tests spanning multiple apps or libraries: integration, end-to-end, contract, benchmark, and shared fixtures. App-local tests stay under `apps/<domain or deployable service>/tests/`.

`scripts/`: Every portable shell script, whether a person runs it or a workflow does. `scripts/security` runs a dependency audit and, when a scanner is installed, a secret scan. `scripts/changelog-check` validates the deterministic structure of a changed changelog; pre-commit calls it at `pre-push`, where the changed-file range is known. `scripts/protect-branch` refuses a push whose destination ref is `main` or `master`; pre-commit calls it at `pre-push`, the only stage where the destination is visible. It is not redundant with `no-commit-to-branch`, which fires only while HEAD *is* the protected branch and so never sees `git push origin HEAD:main` from a feature branch — the case that matters most in a private repository, where push protection and branch rulesets are not offered by the plan. `scripts/worktree-cleanup` prunes Git's records for linked worktrees whose directories are already gone; pre-commit calls it at `post-checkout` and `post-merge`.

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

**`docs/adrs/`**: Architectural Decision Records (e.g., `0001-initial-stack.md`). Explains *why* decisions were made so the AI doesn't try to revert or fundamentally alter established systems.

`docs/specs/`: Specs for contracts that span apps, such as service-to-service APIs and shared schemas. Specs for a single unit stay under `apps/<domain or deployable service>/docs/specs/`.

`docs/LESSONS.md`: Hard-won knowledge about this repository specifically: the provider quirks and recurring mistakes an agent would otherwise rediscover.

`docs/plans/`: Plans written in plan mode, pointed here by `plansDirectory` in `.claude/settings.json`. The default is `~/.claude/plans`, outside the repository, where a plan is invisible to review and disappears with the machine. Under `docs/` it arrives in the diff alongside the code it describes — the point when a human approves the plan before the work starts.

### Root Configuration Files

The hidden files that dictate environment variables, Git behavior, and tool integrations.

YAML files use `.yml` except where a tool fixes the name, which is why `.pre-commit-config.yaml` sits beside `zizmor.yml` and a Node repository adds `pnpm-lock.yaml`. Neither spelling is universally correct: yaml.org prefers `.yaml`, GitHub's metadata reference prefers `action.yml`, and every file this template ships is free to use either. `.yml` is the majority and matches GitHub's own examples, so the two forced `.yaml` names are the exception rather than drift. Rename nothing to make them agree — `pre-commit` reads only `.pre-commit-config.yaml` and `pre-commit install` bakes that default into the hook it writes, so a rename yields a hook that silently does nothing.

`.worktreeinclude`: Lists git-ignored files to copy into new Claude worktrees, which are otherwise fresh checkouts holding tracked files only.

`.env`: The git-ignored config file for storing active sensitive environment variables.

`.gitignore`: Specifies intentionally untracked files and directories. Ignores `.claude/` and the root `CLAUDE.md` so a generated repository carries them in its working tree without committing them. The `CLAUDE.md` pattern is anchored: a nested `CLAUDE.md` is the `@AGENTS.md` shim that loads its folder's contract, and must be committable.
`.gitattributes`: Git behavior rules for line endings, diffs, and GitHub Linguist classification.

`.pre-commit-config.yaml`: Local guardrails that run automatically before code gets committed, catching AI syntax mistakes early. **`.commitlintrc.yaml`**: The commit message rules. Messages follow Conventional Commits — `type(optional scope): subject`, a blank line, then the body.

### Additions by Occasion

These live in `src/repository-addons/` and are never copied during generation. This section names the occasion for each — the condition that makes it worth having — and why it is shaped the way it is. What must be *edited* before one is safe to ship is a separate question, answered by `src/addon-adoption.json`, which lists per addon the tokens to replace, the sections demanding a judgement, and the steps that happen outside the repository. Two files because they are read at different moments and by different readers: this one when deciding whether to take an addon, that one while adopting it.

One of them ships empty and is written rather than filled — `.env.example`. The manifest flags it `authored_on_adoption` and the occasion below is the whole of the guidance.

#### When someone else will use it

Someone who is not the author has to get the thing running, and has to know whether they are allowed to.

`README.md`: The public orientation page — what the project does, how to install it, and how to use it. GitHub renders it on the repository's front page, so for most readers it is the project.

Ships as a scaffold rather than empty, and the distinction from the mostly-true prose of `SECURITY.md` or `GOVERNANCE.md` is the point. A README's *content* is almost entirely project-specific — a governance model can be stated truthfully sight unseen, a feature list cannot — so the template ships no prose it would be lying to keep. What it ships instead is the *shape*, which is one of the most standardized in open source: the centered header, the badge row, the nav line, the About / Features / Install / Usage / License order that `standard-readme` codifies and the strongest examples all follow. An operator handed a blank file re-derives that structure every time and usually lands thinner than the references worth copying. The scaffold also lays out a wide palette of Markdown elements — HTML-centered blocks, badges, GitHub alerts, a table, a task list, `<details>`, `<kbd>`, footnotes, clickable image-links — on purpose, so the operator adapts rather than remembers what a README can contain.

It ships as a scaffold rather than authored-on-adoption for the reason `CONTRIBUTORS.md` does the opposite: a README's failure modes are *loud*. An unfilled title renders as a giant `[REPLACE: project name]` heading, a missing image as a broken-image icon, an unbacked badge as red or malformed — the fail-loudly property the payload wants everywhere, and the one a credit ledger lacks, since a wrong contributor entry renders as a clean-looking dead link. That loudness is what makes shipping content safe here where it is dangerous there. Placeholders are visible `[REPLACE: ...]` brackets, not silent `REPLACE-` tokens, because nothing validates a README and the render is the only check.

The manifest lists four slots — the project title (shared with CONTRIBUTING and CITATION), a new one-line tagline, and the owner and repo names that appear in badge and clone URLs — and six reviews, because most of what a README needs is judgement, not substitution: which visuals to keep, which badges are backed by something real, the actual features and usage, the install commands that do not exist until the first language manifest does, the companion-file links that are dead unless that addon was adopted, and the table of contents that must track the headings kept. The one external step is adding the header and hero images the scaffold references, or deleting the blocks that point at them; nothing but the render reports them missing. Each region carries an invisible `<!-- ADOPT: ... -->` comment for someone adopting the file by hand with no manifest to read.

**`CHANGELOG.md`**: A per-version record of what changed, in Keep a Changelog 2.0.0 format, pinned by the link in the file's own header so the convention it follows cannot drift as that page changes. Written for someone deciding whether to upgrade, so it arrives with the first reader rather than the first commit. Adopting it brings `.claude/rules/changelog.md` with it, which is what teaches an agent when an entry is owed. `scripts/release` then publishes the section matching the tag instead of GitHub-generated notes.

**`LICENSE`**: The terms under which others may use, modify, and distribute the work. Ships as the GNU General Public License v3.0, byte-identical to the text published at gnu.org — reciprocal copyleft, so a derivative carries the same license rather than being absorbed into something closed. Keep it verbatim. An explanatory comment or a filled-in copyright line breaks the license's own terms and can drop GitHub's detection, which matches against the whole text; the project's own copyright notice belongs in source file headers and the README, which is what the appendix at the end of the file gives instructions for.

CC BY-SA 4.0 asks for the same reciprocity and does not survive contact with software: it licenses no patent rights, §2(b)(2) excluding them in as many words; it defines no source-code obligation, so a minified bundle satisfies ShareAlike; and it says nothing about linking, which is the question copyleft exists to answer. Creative Commons declared GPLv3 one-way compatible with BY-SA 4.0 in 2015 for that reason, making GPLv3 their own answer to what BY-SA means for code. AGPL-3.0 closes the one gap GPL leaves — a hosted service is never distributed and so never triggers share-alike — and is deliberately not the default, because the network clause is not wanted here.

A permissive default was weighed and declined. MIT or Apache-2.0 would grow adoption faster, and Apache-2.0 in particular is the better permissive license because it grants patent rights where MIT leaves the same gap CC BY-SA does. Reciprocity was ranked above adoption deliberately: the point of the default is that a derivative stays open, and a permissive license buys reach by giving that up. Treat this as settled rather than reopening it per repository — the case for permissive is real and already known.

The version is **GPL-3.0-or-later**, not version 3 only. That choice is not expressible in `LICENSE`, whose text is identical either way; it lives in the per-file notice, and the SPDX identifier `GPL-3.0-or-later` is what records it in a form tooling reads. Mark source files with the one-line form rather than the full paragraph block:

```
# SPDX-License-Identifier: GPL-3.0-or-later
```

The long-form notice this abbreviates is the appendix at the end of `LICENSE`, already worded for "or later" — use it in the README or a program's `--version` output where a reader needs prose. "Or later" is chosen because relicensing to a future GPLv4 otherwise requires every contributor's individual consent, which is unobtainable in practice once a project has any history.

**`SECURITY.md`**: The project's security policy — the private channel for reporting a vulnerability, what to expect after reporting, the supported versions, and the coordinated-disclosure norm. GitHub links it from the Security tab and the new-issue banner, reading it from `.github/`, the root, or `docs/` in that order.

Ships as a template rather than empty, for the reason `CODE_OF_CONDUCT.md` does: the document has one region whose failure mode is being *trusted*, and a visible marker there is the safer failure than a silent blank. A security policy that routes a report to an unwatched channel, or promises a response window nobody keeps, is worse than none — a reporter relies on it at the one moment it matters and discloses publicly instead. The template supplies the shape and the parts that are universal (do not report in public, what to include, coordinated disclosure) and marks the parts it cannot know.

The one slot is the reporting address, `[REPLACE: the private security address you monitor]`, kept as a visible bracket rather than a silent `REPLACE-` token so an unadopted copy announces itself in the rendered policy. The judgement regions are why `src/addon-adoption.json` lists this file: the channel choice between that email and GitHub's Private Vulnerability Reporting — a Security-tab button that needs enabling and is unavailable on a private free-plan repository, the same plan boundary that gates push protection and rulesets; the acknowledgement window, honest only if it is a commitment the project will keep; and the Supported versions table, which ships a plausible guess that renders as fact and has to be made true or deleted. Enabling PVR is the one external step, and nothing in the repository reports it undone. Each region is mirrored by an invisible `<!-- ADOPT: ... -->` comment in the file for someone adopting it by hand with no manifest to read.

`SUPPORT.md`: Routes users to help, filtering general troubleshooting out of the core issue tracker.

**`.env.example`**: A sanitized template of `.env` showing required variables without exposing actual secrets. Ships empty, like `.env` itself: the variables are whatever the application reads, and a template that guessed them would ship a list every generated repository has to delete. The `.example` suffix is load-bearing — `.gitignore` ignores `.env` and `.env.*`, then re-includes `.env.example` and `.env.*.example` by negation, so a file named `.env.sample` or `.env.local` is ignored and never reaches the repository.

#### When someone else will contribute code

The trigger is a second person with commit ambitions, not a public repository. Two engineers on a private repository are already here.

**`CONTRIBUTING.md`**: How a change reaches the default branch — reporting a bug, proposing an enhancement, setting up locally, and opening a pull request.

Ships as a template rather than empty, for the reason `CODEOWNERS` does but through the opposite mechanism. `CODEOWNERS` is filled because its rules are unguessable; this file is filled because most of its rules are already *known* — the payload ships and enforces the whole contribution workflow it describes. Conventional Commits are checked by commitlint at commit time, `no-commit-to-branch` blocks `main`, pull requests merge rather than squash, `scripts/doctor` and `scripts/check` are the setup and the gate, and `.github/` already carries the issue forms and pull request template the guide points at. An empty file would ask an operator to re-derive that process from scratch and document it correctly — the workflow their repository already runs — which is exactly the re-derivation an authored-on-adoption file is right to demand only when the template knows nothing.

What the template cannot supply is marked, not guessed. The project name is the one slot, `REPLACE-PROJECT-TITLE`, shared with `CITATION.cff` and rendered visibly so an unfilled copy announces itself. The judgement regions carry no token and are the reason `src/addon-adoption.json` lists this file: the intro's one-line description of what the project is; the Code of Conduct and security links, each valid only if that addon was also taken and a dead link otherwise; the Ways-to-contribute list, to be trimmed to the paths a maintainer can actually shepherd; and the setup section, whose concrete build and test commands do not exist until the repository's first language manifest does. Each is mirrored by an invisible `<!-- ADOPT: ... -->` comment in the file itself, which serves someone adopting it by hand with no manifest to read and is deleted on adoption.

**`CODE_OF_CONDUCT.md`**: The baseline rules for community behavior and expectations for professional interaction. Its value depends on being adopted before it is needed; written in response to an incident it is a ruling rather than a rule, and reads as one.

Ships as [Contributor Covenant 3.0](https://www.contributor-covenant.org/version/3/0/), verbatim apart from the site's own front matter. Version 2.1 is the more widely deployed text and was declined: 3.0 has been the stable release since July 2025, and its enforcement ladder is the part worth having — 2.1 lists four consequences with no stated process for reaching one, which is the gap a maintainer discovers while trying to apply it. Keep the Attribution section; CC BY-SA 4.0 requires it and removing it is a licence violation.

Upstream ships two visible `[NOTE: ...]` markers rather than silent placeholders, and they are kept that way. A Code of Conduct is the one document whose failure mode is being *trusted*: an unfilled reporting line published silently promises a channel that does not exist, and someone finds that out at the worst possible moment. A marker that renders in the published document is the safer failure. Both regions are in the adoption manifest.

**`CODEOWNERS`**: Which accounts GitHub requests for review when a pull request touches a path. Read from `.github/`, then the repository root, then `docs/` — in that order, first one found wins, and nowhere else, so a second copy is not a fallback but a file that is never read. On its own it only requests reviewers; a branch protection rule or ruleset requiring code owner review is what makes the request binding.

Ships as a template rather than empty, because almost nothing about the file is guessable from looking at it and every one of its failure modes is silent. An invalid line is skipped while the rest of the file still applies; an owner without write access is dropped; a team must be visible and hold write access in its own right even when all its members already have it; over 3 MB the file is ignored entirely; draft pull requests request nobody. The pattern rules are gitignore's minus `!`, `[ ]`, and `\#`, which GitHub documents as not working without saying what happens instead, and a `!` line has been reported both highlighted as invalid and accepted as valid. The last matching pattern wins rather than the most specific, which is backwards from how the same syntax reads everywhere else and is the one mistake here that reports nothing at all.

The default owner ships as an active `* @REPLACE-CODE-OWNER` line rather than commented out, the opposite of `.github/FUNDING.yml`, and for the reason that distinguishes them: GitHub validates this file. An unfilled line is highlighted on the file's page and returned by `gh api repos/<owner>/<repo>/codeowners/errors`, so the placeholder announces itself, while a commented-out file is indistinguishable from a finished one. `scripts/repo-settings check` calls that endpoint, and in the same run reports whether any rule actually requires code owner review — the difference between a file that binds and one that requests reviewers nothing waits for. It reports *not readable from here* as its own outcome rather than as "not required", because that answer can live in classic branch protection, which needs admin to read.

The trap worth knowing before adopting it: GitHub does not let the author of a pull request approve it. A solo maintainer with `* @me` who also requires code-owner review needs an approval that only they can give and that GitHub will not let them give; an administrator can merge past it, unless the rule is set to apply to administrators too.

#### When the project outlives a single maintainer

These two answer the same question — who decides, and who is owed credit for what — but part ways on whether a template can say anything true in advance. Credit cannot be: a contributor ledger is worth nothing until there are contributors to name, so `CONTRIBUTORS.md` is authored when they arrive. Who decides can be, because one answer fits most projects at the start — a single accountable person — and `GOVERNANCE.md` ships stating exactly that.

`GOVERNANCE.md`: The political structure of the repository — who has final say, how routine decisions get made without invoking it, and how disputes are resolved. Ships as a single-authority template: one maintainer, named in the one slot the file carries, holds final authority, with day-to-day work running on lazy consensus in the open. This is the model most projects start with and many keep — a benevolent-dictator arrangement — and it is the one governance model a template can state truthfully sight unseen, which is why it ships as content rather than being authored on adoption like the credit ledger beside it. CNCF, by contrast, declines to ship a single default and offers a chooser over several divergent shapes, because every model past this one turns on decisions a template cannot make — the reviews that earn a commit bit, the cadence of meetings, the body that resolves a tie.

Nothing validates this file the way GitHub validates CODEOWNERS, so its single slot is a visible `[REPLACE: ...]` bracket rather than a silent token: an unfilled maintainer handle renders in the published document and no tool reports it, leaving a human as the only check. The manifest carries that slot and two reviews — the Code of Conduct link, kept only if that addon was adopted, and the confirmation that a single authority actually describes this project rather than a shared arrangement the template would misstate. The file names its own retirement condition: the closing section on one maintainer becoming several is the instruction to replace this template with a multi-maintainer model, for which CNCF publishes the common shapes. That is the honest handling of the case this occasion is named for — a single accountable person is stated plainly while it is true, rather than a committee that does not meet.

**`CONTRIBUTORS.md`**: A public ledger crediting individuals who have contributed code or documentation. GitHub also recognizes `AUTHORS`, which is a narrower list: the people whose contributions are legally significant for copyright. The two only need to be separate files under a contributor licence agreement or copyright assignment, where who holds the copyright is a different question from who to thank.

Ships in the [All Contributors](https://allcontributors.org) format, carrying the marker comments, the badge, and all thirty-three contribution keys. The format is the point rather than the file: a hand-maintained credit list drifts, and an omission from a list of people you are thanking reads worse than having no list, so the value is in the bot maintaining it. It travels with `.all-contributorsrc`, which is the second half of one record rather than a separate file: the table is generated from the `contributors` array in the config and is never parsed back out of the Markdown, so the config alone is the state. It ships pointing `files` at `CONTRIBUTORS.md`, because the default is `README.md` and the table otherwise lands there while this file stays empty.

The adoption manifest carries what to do; what is worth knowing here is the shape of the failures. `projectOwner` and `projectName` are required, so an empty value throws — but they build the profile and commit links, so a *wrong* value gives a table of dead links and no error at all. Installing the bot is the step nothing reports undone: without it the `@allcontributors` comment syntax simply sits there and no pull request appears. The marker comments in the Markdown are matched as literal strings, so reformatting them produces the same silence.

**`.all-contributorsrc`**: The All Contributors configuration and contributor state. Named without a `.json` suffix because both the CLI and the bot look for that exact filename, which also means the `check-json` hook does not match it and nothing local validates it — the CLI reads it through `json-fixer`, which silently repairs and rewrites malformed JSON rather than failing. `commit` is `false` so the CLI proposes changes instead of writing a commit, which would otherwise hit `no-commit-to-branch`; `commitConvention` is `angular` so the message it does generate satisfies commitlint.

#### When the work is academically valuable

**`CITATION.cff`**: Machine-readable citation metadata, which GitHub surfaces as a "Cite this repository" button. Root only. The occasion is the work being the kind that gets cited — research software, a dataset, a method — not a citation request arriving, which nothing would announce. On an academic repository that is true on day one; on everything else it never becomes true.

Detection is narrower than it looks: only the repository root of the default branch is read, and only under this exact name. `CITATION.md`, `CITATION.bib`, and `CITATIONS` get a link in the same sidebar and no parsing, so a wrong name looks like it worked. No release and no DOI are required — the button appears on the next push to the default branch. Parsing is ruby-cff against the formal schema, so a file that fails validation renders an error in the sidebar instead of a citation; `uvx cffconvert --validate` catches that before pushing, and nothing in `scripts/check` does.

The failure worth planning for is the one that validates. Every `REPLACE-` placeholder the file ships with is a nonempty string, which is all the schema asks for, so a half-filled file passes validation and hands out a BibTeX entry crediting `REPLACE-FAMILY-NAME` with no warning anywhere. That is unlike `.all-contributorsrc`, where unreplaced values at least produce visibly dead links. Fill the file in at the moment it is added, not when someone cites it. `license` is the lone field where that cannot happen, and it ships commented out rather than filled: it is a closed enum of SPDX identifiers, so a placeholder fails validation and the sidebar renders an error instead of a citation. Naming a concrete license here would also make the file assert something about a `LICENSE` that may not be the one this repository ships — `GPL-3.0-or-later` and `GPL-3.0-only` are distinct SPDX values and the license text is identical either way, so this line and the per-file SPDX headers are the only places that choice is recorded. `version`, `date-released`, and `doi` ship commented out for the same reason inverted — a template cannot keep them true, and a stale version here cites a release that never happened. On DOIs, Zenodo mints two and the concept DOI is the one that belongs here; the version DOI pins a single release and sends readers to an old version forever. `preferred-citation` is commented out because it *replaces* the software citation rather than supplementing it: GitHub, Zotero, and ruby-cff all honor it by default, so uncommenting it stops the sidebar citing the software at all.

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
