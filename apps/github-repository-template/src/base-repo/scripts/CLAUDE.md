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

**`libs/detect.sh` owns every language-specific decision.** Commands name a capability — `lint`, `test`, `audit`, `format-write` — never a language adapter. `DETECT_LANGUAGES` and `DETECT_PRUNE_DIRS` are the single lists; iterate them, never copy them.

**The orphan rule tests the exact root manifest, not language presence.** `has_go` and `has_kotlin` each accept two filenames and only one of the two wires up a nested package. `detect_orphan_manifests` prints one line per orphan and exits 0 either way; `judge_orphan_manifests` turns them into findings, and `ci` and `security` stop there when it fails.

**A check that did not run is not a check that passed.** The states are `pass`, `not-applicable`, `unavailable`, `FAIL`, and `unavailable` fails the run whenever the check was expected. `audit:kotlin` and `audit:swift` are `not-applicable` without a lockfile: nothing to scan is not a missing tool.

**`libs/result.sh` owns how a check reports, and its printed layout is an interface.** Suites grep `^<check> +<state>` for a column and `^ +` for a finding.

- `result <check> <state> <detail>` pads the check to 18 columns and the state to 16, and refuses any word outside the four states. `result_line` is the layout alone, for a table that is not a set of Results.
- `record` collects findings once each, `verdict` closes a check, and `tally` returns non-zero on any `FAIL` or `unavailable`. A command ends with `tally` and its status is the run's.
- `would-run` rides the state column and is not a state.
- `language_capabilities run` reports on the line, so its only non-zero return is a usage error. `NO_RUNNER` never leaves the dispatcher.
- `doctor`, `fix`, `run`, `package`, `security`, `structure`, `changelog-check`, `protect-branch`, and `repo-settings` all report through these states. `security` calls the secret scan `not-applicable` without gitleaks, since pre-commit runs its own pinned copy.

**Pipes end in a variable or a `-print -quit` test, never a reader that exits early.** SIGPIPE under `pipefail` reports 141, which a detection function reads as "absent". `swift_each`, `trivy_each`, and `go_each` read their list on fd 3 so the command they run cannot consume it.

**Four runners contradict the pass/fail rule and are special-cased deliberately.** pytest exits 5 on no tests, npm's placeholder test script exits 1, `uv run` exits 2 on a missing tool, and `uv audit` exits 2 on a uv predating the subcommand. Do not remove them.

**A capability adapter captures a tool's own exit status, not just its output.** A runner is called `|| status=$?`, so a failure with empty stdout otherwise reads as a pass.

**Go capabilities run once per module, not at the repository root.** `./...` matches nothing at a workspace root. `go_each` enumerates with `go list -m` and fails on an empty or failed listing; the two gofmt adapters stay at the root, since gofmt walks the filesystem. `_go_main_packages` dispatches on the count: one is the program, none is `NO_RUNNER`, several is refused with the candidates named.

**`scripts/check`'s test-runner glob uses `nullglob`**, or an empty `tests/` reads as one missing test script.

**`libs/precommit.sh` owns which git hooks are owed, and parses rather than greps.** `default_install_hook_types` has three valid YAML forms and a single-line pattern matches one, reporting no hooks owed. The config path is a parameter; the clone is the working directory.

**`libs/*.sh` and `tests/libs/harness.sh` are sourced, never executed.** No shebang, no executable bit, `.sh` so linters recognize them. Every other script here is extensionless and executable, since pre-commit reads a shebang only on an executable file.

`harness.sh` holds the counting and the fixture primitives: `scratch_repo`, `fixture`, `declare_unit`, `quadlet_pair`, `stub`, `minimal_path`, and `skip`, which is counted. It also owns the ambient isolation — `GIT_CONFIG_*` to `/dev/null`, `GOWORK=off`, `CI_DRY_RUN` unset. No suite changes directory; a command under test runs in a subshell that `cd`s into `$work`.

**`report` fails a suite that passed nothing and skipped something.** A run that verified nothing must not read as green.

**A suite never consumes its caller's stdin.** Fixtures stub commands that drain stdin on purpose, so every invocation that might reach one gets `</dev/null`.

**`adr-index` and `structure` are pre-commit hooks, not capabilities.** Both run `always_run` with no `files:` filter, because that filter reads staged paths and staged paths exclude deletions. `adr-index` also self-reports its rewrite with a non-zero exit, since pre-commit sees no change while the index is still untracked.

**`structure` holds the layout rules as code** and reads the contents of exactly one file, a unit's `.unit.json`. Depth rules stop at the first `src/` and start at `scope_start`, `2` under `apps/` because a unit name is not a scoped folder. A domain is recognized by its own `src/`, never by name. It enumerates with `git ls-files`, so gitignored scratch needs no prune list, and it requires `jq`. Three rules are about content and report `not-applicable` — do not improve them into a guess. It checks declared values and never a `run`-and-`ships` pairing, per ADR 0001.

**`run` and `package` take their context as globals, not parameters**, from `libs/unit.sh`. `package` is not in the gate and shells out to no container runtime; a `quadlet` unit is validated by reading its pair.

**Packaging clears the unit's `dist/` before it dispatches**, only for a language that packages there per `packaging_writes_dist`, and never on a dry run. `release` aborts on a unit that shipped nothing, and a stale binary would satisfy that guard without having been built from the tagged commit.

**No function stands in for an absent adapter.** `language_capabilities probe` reads `absent` off the function table, and the dispatch reports `unavailable` rather than a stub answering `NO_RUNNER`.

**The Node `run` adapter refuses a `bin` that is not on disk**, naming `npm run build` when the package has one, rather than letting Node emit a module-not-found trace.

**`changelog-check` validates only the paths it is given, at `pre-push`.** It judges Keep a Changelog form, not whether a change owed an entry, so a repository with no `CHANGELOG.md` never invokes it. CI re-runs it over the whole pull-request range.

**`protect-branch` reads the push destination, not the current branch** — the case `no-commit-to-branch` cannot see. It is silent when `PRE_COMMIT_REMOTE_BRANCH` is unset, leaving multi-ref and delete pushes to the server, because a guard that fires on ordinary work gets bypassed.

**`worktree-cleanup` prunes metadata and never deletes a directory.** It ignores its positional arguments, which differ per hook stage, and reads only `--report`.

**`check`'s pre-commit sweep covers untracked files, in a second pass by path**, since `--all-files` enumerates through git and cannot see the files most likely to be new.

**Local commands stay off hosted GitHub state.** `doctor`, `check`, `run`, and `package` read no repository settings, branches, or releases; only `repo-settings check` does. The boundary is hosted state, not connectivity.

**`release` is the only script here that writes to GitHub.** It publishes the changelog section matching the tag, or GitHub-generated notes when there is no changelog, and must never treat an uncut version and an absent changelog as the same thing. It packages every unit before the tag is cut, checks separately that a unit declaring `ships: executable` produced a file, and runs `scripts/ci` itself. Nothing else should call it.

**`repo-settings` reports and never changes**, because a ruleset write replaces rather than merges and could silently revert a deliberate loosening. It fetches once into one JSON document and judges after, which is the seam its suite stubs `gh` at. Preflight absences are `not-applicable` and stop green; a 403 carrying GitHub's upgrade message is `not-applicable` naming the plan and any other refusal is `unavailable`. Merge commits are read before squash and rebase, since GitHub refuses to write a repository with no way to merge.

**The CODEOWNERS judgment runs above the admin gate and below the read-access check**, so a broken file is reported to a non-admin and a 404 means no file rather than no access. `judge_owner_review` has a fourth outcome, `unavailable`: the requirement can come from classic branch protection, which needs admin to read, and a file wrongly reported as binding leaves someone trusting a review gate that does not exist.

## Work Guidance

Adding a language means: add it to `DETECT_LANGUAGES`, add its `has_<lang>` detector, add a `_capability_<check>_<lang>` function for each capability it can answer — a capability with no honest adapter is left absent, not stubbed — add a `_codeql_entry` row, add its toolchain to `.github/actions/setup-toolchains/action.yml`, and add its column to the table `tests/capabilities-test` holds against `language_capabilities probe`, naming which cells are deliberately `absent`. That suite fails when a present language is not dispatched to every check and when the probe's table differs from the one it holds — the one property nothing else reports on, since a dropped language produces a shorter green run rather than a failure.

Adding a check means adding it to `DETECT_CAPABILITIES` and writing an adapter per language, or declaring it not-applicable in `_capability_is_not_applicable`.

## Verification

Each suite is `scripts/tests/<name>-test`, reports through the harness, and asserts through the public surface.

- `capabilities-test` — the ten-by-six probe table, dispatch under `CI_DRY_RUN=1`, and real runs of `ci`, `security`, `run`, and `package` against stubbed toolchains
- `result-gate-test` — the four states are enforced and findings deduped, and every command ending in `tally` fails on an `unavailable` line or a recorded orphan
- `harness-test` — the harness itself, run as a process: the tally line and exit status for all-pass, one-fail, all-skip, and skip-beside-pass, plus each fixture primitive
- `clean-test` — `clean` prunes the directories `libs/detect.sh` names
- `unit-commands-test` — unit resolution, `run: none` and `ships: none`, quadlet validation with no container runtime, arguments after `--`, and `dist/` cleared only where a language packages there. Skips without `jq`
- `health-checks-test` — the offline boundary, with `gh` stubbed
- `repo-settings-test` — every preflight absence, every judgment in each of its answers, and the two orderings, with `gh` stubbed per endpoint. Skips without `jq`
- `release-test` — what `release` hands to `gh release create`, and each way the walk aborts before the tag is cut
- `adr-index-test` — the index converges and pre-commit invokes the hook
- `commitlint-test` — the `commit-msg` hook installs and commitlint judges a message. The only suite needing the network
- `worktree-cleanup-test` — pruning is correct and idempotent and tolerates each hook stage's arguments
- `session-start-test` — the operator's global `session-start.sh`, `not-applicable` where it is absent
- `changelog-check-test` — each structural rule, the shipped addon changelog, a missing file, a missing awk, an unrelated path
- `precommit-hooks-test` — `libs/precommit.sh` against each YAML form. Needs no network, which is the point: this wiring fails silently
- `structure-test` — each layout rule in both directions, `.structure-allow` at a path and at a prefix, every declaration value, and `jq` absent. Each fixture is a real repository with the script copied in, since it resolves its own root from `BASH_SOURCE`
- `protect-branch-test` — bare, qualified, near-miss, and unset destinations

`scripts/check` runs all sixteen before the checks they guard, then `structure` before `ci`. `ci.yml` runs them before toolchain setup and installs `pre-commit` first, so the two hook-wiring suites do not skip every case. shellcheck runs via pre-commit with `-x`.
