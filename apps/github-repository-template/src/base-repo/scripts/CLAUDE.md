# Scripts

## Purpose

Every portable shell script, whether a person runs it or a workflow does. Project logic lives here rather than in YAML so it runs locally exactly as it runs in GitHub Actions.

## Ownership

One flat directory, not a `ci/` and a `scripts/` split. The boundary that split would need does not hold: `check` calls `ci` and `security`, `release` calls `ci`, and every script sources the same detection library, so a file's caller is not a property that stays put.

- `doctor`, `check`, `fix`, `clean`, `run`, `package` — run by a person
- `ci`, `security`, `release`, `detect` — called by `.github/workflows/`
- `repo-settings check` — hosted GitHub state, run explicitly
- `adr-index` — called by pre-commit; regenerates `docs/adrs/index.md`
- `structure` — called by `scripts/check` and by pre-commit; audits where files sit; the script itself holds the rules
- `changelog-check` — called by pre-commit at `pre-push`, and by `ci.yml` over a pull-request range; validates `CHANGELOG.md` structure
- `protect-branch` — called by pre-commit at `pre-push`; refuses a push whose destination ref is `main` or `master`
- `worktree-cleanup` — called by pre-commit at `post-checkout` and `post-merge`, and by the SessionStart hook with `--report`; prunes Git's records for worktrees whose directories are gone
- `libs/detect.sh` — the detection library, sourced by all of the above
- `libs/unit.sh` — which unit an invocation acts on and what that unit declared; sourced by `run`, `package`, and `release`
- `libs/precommit.sh` — which git hooks the config asks for and which this clone lacks; sourced by `doctor` and by `~/.claude/hooks/session-start.sh`
- `libs/result.sh` — how a check reports: the four Result states, the printed layout, findings, and the tally; sourced by `libs/detect.sh`, and so by every command, and by `structure`
- `libs/quadlet.sh` — `quadlet_validate <dir> <label>`, validation of a `quadlet` unit's `deploy/quadlet/` pair, the label naming it in findings; sourced by `package`
- `tests/*-test` — assertions about the wiring itself
- `tests/libs/harness.sh` — the assertion counting those tests share, and the fixture primitives they compose: `scratch_repo`, `fixture`, `declare_unit`, `quadlet_pair`, `stub`, `minimal_path`, `skip`. `fixture <name>` is a fresh scratch repository named as the current case, the default a suite overrides when its cases need more; `minimal_path <tool…>` builds a directory of symlinks to just those tools and echoes it, for a case that runs a command with a named tool absent from `PATH`

A helper that must be built before it runs belongs in `tools/`, not here.

## Local Contracts

**`libs/detect.sh` owns every language-specific decision.** Command scripts name a capability — `lint`, `test`, `audit`, `format-write` — and never a language adapter. `DETECT_LANGUAGES` and `DETECT_PRUNE_DIRS` are the single lists; iterate them rather than keeping a second copy, as `scripts/clean` does through `detect_prune_expr`.

**The orphan rule tests the exact root manifest, not language presence.** `has_go` accepts `go.mod` or `go.work` and `has_kotlin` either Gradle file, so `has_language` would let a single-module manifest count as having wired up a nested one. `detect_orphan_manifests` tests the pair's own `root` filename, excludes a match at the repository root, prints one line per orphan on stdout, and exits 0 either way. `judge_orphan_manifests` records each line as a finding and closes with `verdict detection`; `ci` and `security` stop there when it fails, since the checks after it would run green over a package none of them sees.

**A check that did not run is not a check that passed.** Results are `pass`, `not-applicable`, `unavailable`, or `FAIL`. `unavailable` fails the run whenever the check was expected. `audit:kotlin` and `audit:swift` are `not-applicable` when `gradle.lockfile`/`Package.resolved` is absent: nothing to scan is not a missing tool.

**`libs/result.sh` owns how a check reports, and its printed layout is an interface.** A suite may grep `^<check> +<state>` for a column and `^ +` for a finding.

- `result <check> <state> <detail>` prints one line, the check padded to 18 columns and the state to 16, and refuses any word outside the four states with exit 1. `result_line` is the layout alone, for a table that is not a set of Results — the capability probe prints `wired` and `absent` through it.
- `record <finding>` collects violations once each; `verdict <check> <summary>` closes the check, `pass` with the summary or `FAIL` with `N violation(s)` and each finding indented 21 spaces.
- `tally` returns non-zero once any check reported `FAIL` or `unavailable`. A command ends with it and its exit status is the run's result.
- `would-run` rides the state column and is not a state: the dry-run marker, counted as neither.
- `language_capabilities run` reports the outcome on the line, not in its return, so its only non-zero return is a usage error. `NO_RUNNER` is an adapter's answer to the dispatcher and goes no further.
- `doctor` speaks the same four states: a required tool absent is `unavailable`, an optional one `not-applicable` with what it would add, a missing hook a finding under `pre-commit`. `security` reports the secret scan `not-applicable` when gitleaks is off PATH, since pre-commit runs its own pinned copy.

**Pipes end in a variable or a `-print -quit` test, never in a reader that exits early.** Under `set -euo pipefail` a `grep -q` or `head` kills the writer with SIGPIPE and pipefail reports 141, which a detection function reads as "absent". `swift_each`, `trivy_each`, and `go_each` read their list on fd 3 for the neighbouring reason: the command they run can consume stdin itself, skipping every entry after the first.

**Four runners contradict the pass/fail rule and are special-cased deliberately.** pytest exits 5 on collecting no tests; `npm init -y` writes a test script that exits 1; `uv run <tool>` exits 2 when the tool is missing; `uv audit` is a subcommand, so a uv predating it exits 2 exactly as a found vulnerability does and support is probed with `--help` first. Do not remove them.

**A capability adapter captures a tool's own exit status, not just its output.** A runner is called as `"$function" || status=$?` rather than under `set -e`, so a tool that fails with nothing on stdout reads as a pass unless its status is captured alongside the output.

**Go capabilities run once per module, not at the repository root.** `./...` matches only packages inside a module and a workspace root is in none. `go_each` names the directories with `go list -m -f '{{.Dir}}'` and runs inside each, treating a listing that fails or comes back empty as a failure. The two gofmt adapters stay at the root, since gofmt walks the filesystem rather than resolving a package pattern. `_go_main_packages` asks the same listing which packages are main: one is the program, none is `NO_RUNNER` because a library is not broken for being a library, and several is refused with the candidates named.

**`scripts/check`'s test-runner glob uses `nullglob`.** Without it an empty `scripts/tests/` leaves the pattern unexpanded and the loop reads the literal string as one missing test script.

**`libs/precommit.sh` owns which git hooks are owed, and parses rather than greps.** `doctor` reports the gap and `~/.claude/hooks/session-start.sh` closes it, from the same answer. It is not part of `libs/detect.sh`: a git hook is present whatever the repository is written in. `default_install_hook_types` is valid as a flow list, a wrapped flow list, or a block list, and a single-line pattern matches only the first, reporting no hooks owed. The config path is a parameter; the clone is the working directory, since `git rev-parse` answers from where it runs.

**`libs/*.sh` and `tests/libs/harness.sh` are sourced, never executed.** No shebang, no executable bit, `.sh` so linters recognize them. Every other script here is extensionless and executable, because pre-commit identifies a shell script by reading the shebang and only reads it on an executable file.

`harness.sh` holds the counting, the tally, and the fixture primitives: `scratch_repo`, a git-initialised `mktemp` directory with the scripts tree copied in and an empty `bin/` at the head of `PATH`, removed by the harness's `EXIT` trap and by the next `scratch_repo`; `declare_unit <name> [run] [kind] [targets…]`, the one place the `.unit.json` literal is written; `quadlet_pair <name>`, a pair `scripts/package` validates for a case to then break; `stub <command>`, body on stdin; `minimal_path <tool…>`, a directory of symlinks to just those tools; `fixture <name>`, `scratch_repo` plus `current="$1"`, which a suite scaffolding a different world overrides; and `skip <reason>`, which is counted. It also owns the ambient isolation — `GIT_CONFIG_*` to `/dev/null`, `GOWORK=off`, `CI_DRY_RUN` unset — so a case wanting the dry run sets it per invocation. No suite changes directory: a command under test runs in a subshell that `cd`s into `$work`.

**`report` fails a suite that passed nothing and skipped something.** A run that verified nothing must not read as green. The tally line is `N passed, M failed, K skipped`; a suite recording neither passes nor skips still exits 0, which `session-start-test` relies on.

**A suite never consumes its caller's stdin.** Several fixtures stub a command that drains stdin on purpose, which is what proves `swift_each`, `trivy_each`, and `go_each` read their list on fd 3. Without a redirect the stub blocks on the suite's own stdin, so each command that might reach one is invoked with `</dev/null`.

**`adr-index` and `structure` are pre-commit hooks, not capabilities.** Prose and shape are present whatever a repository is written in, so neither sources `libs/detect.sh` nor is dispatched by `language_capabilities`. Both run `always_run` with no `files:` filter, because that filter reads staged paths and staged paths exclude deletions — `git rm` is exactly when an index or a directory shape goes stale. `adr-index` also self-reports its rewrite with a non-zero exit, since pre-commit's modified-files detection does not fire while the index is still untracked.

**`structure` judges where a file sits, and reads the contents of exactly one file.** That file is a unit's `.unit.json`, which exists precisely to state what a tree cannot show. The rules themselves live in the script, as literal arrays beside the checks that enforce them, and every failure names the rule and the remedy. Four of its decisions are worth knowing before editing it.

- Every rule that reads depth stops at the first `src/`, recorded as `src_limit`; below one the arrangement is the language's. `scope_start` is its mirror, `2` under `apps/` and `0` elsewhere, because the segment directly under `apps/` is a unit name rather than a scoped folder. Without it a unit named `docs` or `tests` collects findings across four checks that `.structure-allow` cannot clear.
- A domain is recognized by its own `src/`, never by name. A parent with no `src/` is reported once, by `apps-layout` alone; `domain-folders` skips it rather than asserting the parent is a domain. `apps-layout` asserts a path is present, so it is the only check a `.structure-allow` prefix could turn stricter, and it looks that `src/` up again in the unpruned list — permission must never turn a passing tree into a failing one.
- It enumerates with `git ls-files`, so gitignored scratch is invisible by construction and no prune list is needed. The declaration is read with `jq`, for the reason `libs/precommit.sh` exists; without `jq` the audit reports `unit-facts` `unavailable` and fails, so `doctor` requires `jq` unconditionally.
- Three rules are about content and report `not-applicable`: whether `libs/` is shared, whether `tests/` spans apps, and whether a file sits at its own scope. Do not improve them into a guess. Likewise the audit checks `run` and `ships` values and never the pairing, since every combination is legal by design, per ADR 0001.

**`run` and `package` take their context as globals, not parameters.** `libs/unit.sh` resolves which unit an invocation acts on and declares `unit_run`, `unit_targets`, and `unit_args`; adapters read them and take no parameters, since a signature for two capabilities would be one the other nine ignore. `package` is not in the gate — packaging is not a check, and `check` must not need a cross toolchain. It shells out to no container runtime: a `quadlet` unit is validated by reading its pair through `quadlet_validate <dir> <label>`.

**Packaging clears the unit's `dist/` before it dispatches, and only for a language that packages there.** `scripts/release` aborts when a unit declaring `ships: executable` produced no file, and a binary left by an earlier build satisfies that guard without having been built from the tagged commit. Clearing happens in `scripts/package`, once before the dispatch rather than inside a target loop, and never on a dry run. `packaging_writes_dist` answers which present languages package there and lives beside the adapters in `libs/detect.sh`; keying it on the declaration instead made `package` purely destructive for the four languages whose `dist/` holds whatever their own build wrote.

**No function stands in for an absent adapter.** `language_capabilities probe` prints `wired` or `absent` per capability and language from the function table alone, so a gap reads as `absent` rather than as a stub answering `NO_RUNNER`. The dispatch then reports `unavailable` and fails the run, since a unit that promised an executable got none.

**The Node `run` adapter refuses a `bin` that is not on disk.** A TypeScript `bin` conventionally names build output a fresh clone lacks, and Node's own failure for that is a module-not-found trace. The adapter tests the path first and names `npm run build` when the package has a build script, guarded on `npm` being installed so the answer is about the tool rather than about `package.json`. The condition is a missing file, so a plain JavaScript unit never reaches it.

**`changelog-check` validates only the paths it is given, and runs at `pre-push`.** It is a structural check on Keep a Changelog form, not a judgment about whether a change owed an entry. A repository with no `CHANGELOG.md` never invokes it, which is what lets the hook ship to a generated repository that has not adopted the addon. CI re-runs it across the whole pull-request range so a fixup commit cannot hide a bad entry.

**`protect-branch` reads the push destination, not the current branch.** `no-commit-to-branch` fires only while HEAD is the protected branch, so `git push origin HEAD:main` from a feature branch never reaches it, and a permission rule cannot cover it either — an ask rule matches a command prefix and the destination is an argument. Two limits come from pre-commit's own pre-push parser and are left to the server: only the first qualifying ref of a multi-ref push is exported, and nothing at all when the local sha is all zeros, which is every `git push --delete`. So the script exits 0 and prints nothing when `PRE_COMMIT_REMOTE_BRANCH` is unset; a guard that fires on ordinary work gets bypassed with `--no-verify`.

**`worktree-cleanup` prunes metadata and never deletes a directory.** `git worktree prune` drops Git's record for a directory that has already disappeared, so a live worktree is untouched by construction. It exits early when the dry run reports nothing, and ignores its positional arguments on purpose — `post-checkout` passes three and `post-merge` one. Only `--report` is interpreted, which is what SessionStart uses.

**`check`'s pre-commit sweep covers untracked files, in a second pass by path.** `--all-files` enumerates through git and cannot see an unstaged file, which makes the gate blindest to the files most likely to be new. `--files` takes a path whether or not git tracks it, and `git ls-files --others --exclude-standard` supplies the list, so an ignored path stays ignored.

**Local commands stay off hosted GitHub state.** `doctor`, `check`, `run`, and `package` must not read or write repository settings, branches, or releases; hosted inspection happens only through `repo-settings check`, and `tests/health-checks-test` enforces it by stubbing `gh`. The boundary is hosted state, not connectivity — pre-commit downloads a hook environment on first use.

**`release` is the only script here that writes to GitHub.** With a `CHANGELOG.md` it publishes the section matching the tag and refuses when that section is missing or empty; without the file it releases with GitHub-generated notes. An uncut version and an absent changelog must never be treated as the same thing. It packages every unit before the tag is cut and attaches what landed in each `dist/`, and because packaging exits 0 when every declared target is unreachable from this host, the walk separately checks that a unit declaring `ships: executable` produced a file and aborts naming the unit. It reads that declaration through `libs/unit.sh` and runs `scripts/ci` itself rather than trusting an earlier job. Nothing else should call it.

**`repo-settings` reports and never changes.** Enabling a setting writes state the whole repository sees and a ruleset write replaces rather than merges, so an automatic correction could silently revert a deliberate loosening. It fetches once and judges after: `fetch_settings` leaves one JSON document, a key per endpoint that answered and, under `errors`, the status and message for each that did not. That is the seam `tests/repo-settings-test` stubs `gh` at.

- The preflight — `gh`, its login, `jq`, a remote — reports each absence `not-applicable` and stops green, since nothing after it could be read.
- Past it, a 403 carrying GitHub's upgrade message is `not-applicable` naming the plan; any other refusal is `unavailable` with the message and status, and fails the tally. An optional setting that is off is `not-applicable` with the remediation.
- Merge commits, squash merging, rebase merging, and automatic head branch deletion go through `boolean_setting <field> <want> <check> <remediation>`. Merge commits are read first: with all three off a repository has no way to merge a pull request, and GitHub refuses to write that state rather than reporting it.
- Push protection and rulesets each have three answers: `pass`, `not-applicable` naming where to turn it on, and `not-applicable` naming the plan.

**The CODEOWNERS judgment runs above the admin gate, and has a fourth outcome.** Every way a CODEOWNERS file fails is silent, `codeowners/errors` needs only read access, and a non-admin is exactly who benefits from being told the file is broken. It sits below the read-access check, which is what makes a 404 from that endpoint mean "no CODEOWNERS file" rather than "no access to look". The requirement that makes the file binding can come from a ruleset or from classic branch protection and `rules/branches` reports only the first, so `judge_owner_review` reports `owner-review unavailable` rather than "not required" — a file wrongly reported as binding leaves someone trusting a review gate that does not exist. A plan offering neither reads `not-applicable` naming the plan. A rejected line is a finding under `codeowners`; an absent CODEOWNERS file is `pass`, since it is an addition by occasion.

## Work Guidance

Adding a language means: add it to `DETECT_LANGUAGES`, add its `has_<lang>` detector, add a `_capability_<check>_<lang>` function for each capability it can answer — a capability with no honest adapter is left absent, not stubbed — add a `_codeql_entry` row, add its toolchain to `.github/actions/setup-toolchains/action.yml`, and add its column to the table `tests/capabilities-test` holds against `language_capabilities probe`, naming which cells are deliberately `absent`. That suite fails when a present language is not dispatched to every check and when the probe's table differs from the one it holds — the one property nothing else reports on, since a dropped language produces a shorter green run rather than a failure.

Adding a check means adding it to `DETECT_CAPABILITIES` and writing an adapter per language, or declaring it not-applicable in `_capability_is_not_applicable`.

## Verification

Each suite is `scripts/tests/<name>-test` and reports through the harness.

- `capabilities-test` — the full ten-by-six table against `language_capabilities probe`, naming the ten cells deliberately `absent`; dispatch under `CI_DRY_RUN=1`, so the result comes from wiring alone; and real runs of `ci`, `security`, `run`, and `package` against stubbed toolchains that record what they were asked. No private name of `libs/detect.sh` appears in it — a case needing an adapter's answer asks the command that dispatches to it
- `result-gate-test` — the result library's own contract, that a word outside the four states is refused and a finding recorded twice is reported once, then one case per command ending in `tally` that an `unavailable` line and a recorded orphan each fail the exit status
- `harness-test` — the harness itself, which no other suite can check: each case writes a small suite, runs it as a process, and asserts the tally line and exit status for all-pass, one-fail, all-skip, and skip-beside-pass, plus each fixture primitive and that the scratch directory is gone afterwards
- `clean-test` — `clean` prunes the same directories `libs/detect.sh` names, rather than a second drifted list
- `unit-commands-test` — unit resolution, `run: none` and `ships: none`, an undeclared unit named rather than assumed, quadlet validation without a container runtime, arguments after `--`, and that packaging empties `dist/` only for a language that packages there. `run_real` unsets `CI_DRY_RUN` for the cases a dry run cannot show. Skips without `jq`
- `health-checks-test` — the offline boundary, with `gh` stubbed
- `repo-settings-test` — `gh` stubbed per endpoint, a file for an answer and a `.error` file for a refusal: each preflight absence stops green, unreadable settings are `unavailable`, every boolean at both values, push protection and rulesets in each of their three answers, the review requirement in each of its four, and the two orderings. Skips without `jq`
- `release-test` — what `release` hands to `gh release create`, and each way the walk aborts before the tag is cut. `gh` is a stub and `CI_DRY_RUN=1` makes `ci` a no-op, so no release is created; `release_real` covers the one case that needs the clearing to actually happen
- `adr-index-test` — the generated index converges, and pre-commit actually invokes the hook
- `commitlint-test` — the `commit-msg` hook is installed by a bare `pre-commit install`, and commitlint rejects a malformed message and tolerates a generated merge subject. The only suite here needing the network
- `worktree-cleanup-test` — pruning removes stale records, leaves a live worktree, is idempotent, and tolerates the arguments each hook stage passes
- `session-start-test` — the operator's global `~/.claude/hooks/session-start.sh`, and `not-applicable` when that hook is absent, as it is on any CI runner
- `changelog-check-test` — each structural rule rejects what it should, the shipped addon changelog passes, and a missing file, a missing awk, and an unrelated path each get their own outcome
- `precommit-hooks-test` — `libs/precommit.sh` against each YAML list form and the scalar, and the hooks a clone lacks. Needs neither `pre-commit` nor the network, which is the point: this is the half of the wiring that fails silently
- `structure-test` — each rule in both directions, `.structure-allow` at a path and at a prefix including one over a domain's own `src/`, a parent that is no domain reported once, every legal `run`/`ships` pairing accepted and each illegal value named, and `jq` off the PATH reporting `unavailable`. Each fixture is a real repository with the script copied in, since the script resolves its own root from `BASH_SOURCE`
- `protect-branch-test` — bare and qualified destinations, a branch merely containing `main`, and an unset destination

`scripts/check` runs all sixteen before the checks they guard, then `structure` before `ci`. `ci.yml` runs the suites before toolchain setup and installs `pre-commit` ahead of them, since both hook-wiring suites skip every case without it and a suite that verified nothing is a failure. shellcheck runs via pre-commit with `-x`, so it follows `source` into the libraries.
