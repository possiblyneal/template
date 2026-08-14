# Scripts

## Purpose

Every portable shell script, whether a person runs it or a workflow does. Project logic lives here rather than in YAML so it runs locally exactly as it runs in GitHub Actions.

## Ownership

One flat directory, not a `ci/` and a `scripts/` split. The boundary that split would need does not hold: `check` calls `ci` and `security`, `release` calls `ci`, and every script sources the same detection library, so a file's caller is not a property that stays put.

- `doctor`, `check`, `fix`, `clean`, `dev` — run by a person
- `ci`, `security`, `release`, `detect` — called by `.github/workflows/`
- `repo-settings check` — hosted GitHub state, run explicitly
- `adr-index` — called by pre-commit; regenerates `docs/adr/index.md`
- `libs/detect.sh` — the detection library, sourced by all of the above
- `libs/precommit.sh` — which git hooks the config asks for and which this clone lacks; sourced by `doctor` and by `.openclaude/hooks/session-start.sh`
- `tests/*-test` — assertions about the wiring itself
- `tests/libs/harness.sh` — the assertion counting those tests share

A helper that must be built before it runs belongs in `tools/`, not here.

## Local Contracts

**`libs/detect.sh` owns every language-specific decision.** Command scripts name a capability — `lint`, `test`, `audit`, `format-write` — and never name a language adapter. `DETECT_LANGUAGES` is the single list of supported languages; iterate it rather than keeping a second copy. Detection was once duplicated across eight files and the copies disagreed, which is the failure this module exists to remove: a language wired into some checks and not others produces a green run over work nothing looked at.

**A check that did not run is not a check that passed.** Results are `pass`, `not-applicable`, `unavailable`, or `FAIL`. `unavailable` fails the run whenever the check was expected, because a present manifest with a missing toolchain must not report success for work it did not do.

**Pipes end in a variable or a `-print -quit` test, never in a reader that exits early.** Under `set -euo pipefail` a `grep -q` or `head` closes the pipe, the writer dies of SIGPIPE, and pipefail reports 141 — which a detection function reads as "absent". That is a wrong answer that is silent rather than loud.

**Three runners contradict the pass/fail rule and are special-cased deliberately.** pytest exits 5 on collecting no tests; `npm init -y` writes a placeholder test script that exits 1; `uv run <tool>` exits 2 when the tool is not installed. Each is translated to "no runner" or success rather than being reported as a failing suite. Do not remove these without reading why they are there.

**`libs/precommit.sh` owns the question of which git hooks are owed, and parses rather than greps.** `doctor` reports the gap and `.openclaude/hooks/session-start.sh` closes it; both need the same answer, and the two copies that preceded this module had already drifted apart in how they tested for a hook file. It is not part of `libs/detect.sh`, which owns language-specific decisions — a git hook is present whatever the repository is written in.

`default_install_hook_types` is valid as a flow list, as a flow list wrapped across lines, and as a block list, and a single-line pattern matches only the first. Against the others it finds nothing or half a list, reports no hooks owed, and both callers agree a clone with no commit-msg hook is correctly set up — a check that did not run reading as a check that passed, with no output to say so. `tests/precommit-hooks-test` covers all three, plus the scalar that must not be read as an unterminated list.

The config path is a parameter to both functions; the clone is the working directory, since `git rev-parse` answers from where it runs and is not a path a caller chooses.

**`libs/detect.sh` and `tests/libs/harness.sh` are sourced, never executed.** No shebang, no executable bit, `.sh` extension so linters recognize it. Every other script here is extensionless and executable — pre-commit identifies them as shell by reading the shebang, and only reads it on an executable file, so a script committed without that bit is skipped in silence. `harness.sh` holds the assertion counting, the tally, and `cleanup` with the `work` directory it removes; each suite keeps its own `fixture`, since they scaffold different worlds and only the counting and the teardown are common. `capabilities-test` overrides `cleanup` because it cd's into the directory being removed.

**`adr-index` is a pre-commit hook, not a capability.** It does not source `libs/detect.sh` and is not dispatched by `language_capabilities`, because ADRs are prose present in every repository whatever it is written in — there is no language to detect.

Two things about its wiring are load-bearing and were each a bug first. It self-reports the rewrite with a non-zero exit rather than relying on pre-commit's modified-files detection, which does not fire the first time the index is created: the file is untracked then, so pre-commit sees no change and the commit lands without it. And it runs with `always_run` and no `files:` filter, because that filter reads the staged paths, which exclude deletions — `git rm` of a record would skip the hook on the one commit that made the index stale. `tests/adr-index-test` drives a real repository through pre-commit for both.

**`check`'s pre-commit sweep covers untracked files, in a second pass by path.** `--all-files` enumerates through git and cannot see a file that has not been staged, which makes the gate blindest to the files most likely to be new. A new script would pass `check` and then fail the hook at commit time, having never been read. `--files` takes a path whether or not git tracks it; `git ls-files --others --exclude-standard` supplies the list, so an ignored path stays ignored.

**Local commands stay off hosted GitHub state.** `doctor`, `check`, and `dev` must not read or write repository settings, branches, or releases. Hosted inspection happens only through `repo-settings check`, so ordinary local work is not coupled to `gh` authentication. `tests/health-checks-test` enforces this by stubbing `gh`.

This is not a promise that nothing reaches the network. pre-commit downloads a hook environment the first time each hook runs, which `check` has always triggered, and `tests/commitlint-test` needs one for commitlint specifically. The boundary is hosted repository state, not connectivity.

**`release` is the only script here that writes to GitHub.** A changelog is an addition by occasion, so the script handles both cases and announces which one it took. With a `CHANGELOG.md` it publishes the section matching the tag and refuses when that section is missing or empty, so a version cannot be published before it has been cut. Without the file it releases with GitHub-generated notes, because a project that has not reached a changelog still has versions to tag. What it must never do is treat an uncut version and an absent changelog as the same thing — the first is a mistake and the second is not. It runs `scripts/ci` itself rather than trusting an earlier job to have done it, which is why the release workflow holds `contents: write` while the gate runs. Nothing else should call it.

**`repo-settings` reports and never changes.** Enabling a setting writes state the whole repository sees, and a ruleset write replaces rather than merges, so an automatic correction could silently revert a deliberate loosening. Three outcomes are distinct and the difference matters: enabled, disabled, and not offered for the plan and visibility.

## Work Guidance

Adding a language means: add it to `DETECT_LANGUAGES`, add its `has_<lang>` detector, add a `_capability_<check>_<lang>` function for each capability, add a `_codeql_entry` row, and add its toolchain to `.github/actions/setup-toolchains/action.yml`. `tests/capabilities-test` fails when a present language is not dispatched to every check — that is the one property nothing else reports on, since a dropped language produces a shorter green run rather than a failure.

Adding a check means adding it to `_capability_is_supported` and writing an adapter per language, or declaring it not-applicable in `_capability_is_not_applicable`.

Changes here almost always belong in `apps/github-repository-template/src/base-repo/scripts/` too. Decide explicitly; a fix in one tree only is how the two drift.

## Verification

- `scripts/tests/capabilities-test` — dispatch coverage, using `CI_DRY_RUN=1` so the result comes from wiring alone and is identical on a machine with no toolchains
- `scripts/tests/health-checks-test` — the offline boundary
- `scripts/tests/adr-index-test` — the generated index converges, and pre-commit actually invokes the hook
- `scripts/tests/commitlint-test` — the `commit-msg` hook is installed by a bare `pre-commit install`, and commitlint rejects a malformed message and tolerates a generated merge subject. The only suite here that needs the network, since proving a JavaScript linter rejects anything means installing and running it
- `scripts/tests/precommit-hooks-test` — `libs/precommit.sh` reads the hook list out of each YAML list form, and reports exactly the hooks a clone lacks. Needs neither `pre-commit` nor the network, so it always runs — which is the point, since this is the half of the wiring that fails silently
- `scripts/check` runs all five before the checks they guard; `ci.yml` runs them before toolchain setup
- Both hook-wiring suites skip their cases when `pre-commit` is absent, so `ci.yml` installs `pre-commit` ahead of them. Without that install they report a smaller green run in CI than they do locally, and the assertions covering the wiring above are the ones lost
- shellcheck via pre-commit, with `-x` so it follows `source` into `libs/detect.sh`
