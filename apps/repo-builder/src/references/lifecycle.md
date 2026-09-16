# Repo Builder Lifecycle Contract

This file holds what is true regardless of operation: the manifest, ownership, how checks are run and reported, the remote gates, and failure behavior. Reviewing and reporting are a third sub-contract, held back in [`reporting.md`](reporting.md) and read at the end of a flow. Read this file, then read the one flow being performed.

- [`generate.md`](generate.md) — build a repository from the payload, including into a destination that already has content
- [`update.md`](update.md) — carry a bounded template delta into a repository already generated from it
- [`adopt.md`](adopt.md) — land a held-back repository addon whose condition has arrived

Two sub-contracts are read from inside a flow rather than on their own:

- [`wayfinding.md`](wayfinding.md) — derive the application boundaries, at [`generate.md`](generate.md) step 7
- [`addon-adoption.md`](addon-adoption.md) — finish an addon after copying it, at [`generate.md`](generate.md) step 2 and [`adopt.md`](adopt.md) step 4

[`choosing_a_language.md`](choosing_a_language.md) is the method wayfinding is a short path through.

Every `<placeholder>` in a command in these files stands for a value the user supplied. Quote it when substituting — `git push origin "$branch"`, not a bare interpolation — and reject a repository or branch name outside `[A-Za-z0-9._/-]+` before it reaches a shell. These values come from someone naming their own repository, so the guard is against a stray metacharacter, not against an attacker.

## Manifest

Every built repository tracks `.repo-template.json`:

```json
{
  "schema_version": 1,
  "template": {
    "repository": "https://github.com/possiblyneal/template",
    "subtree": "apps/github-repository-template/src/base-repo",
    "commit": "0123456789abcdef0123456789abcdef01234567"
  },
  "destination": {
    "repository": "owner/repository",
    "default_branch": "main"
  },
  "generation": {
    "applications": ["billing-api"],
    "features": {
      "codeql": "omitted-by-choice"
    },
    "overrides": [
      {"path": "docs/agents/issue-tracker.md", "reason": "destination tracks issues outside GitHub"}
    ],
    "superseded": [
      {"path": ".github/workflows/lint.yml", "did": "ran eslint on push", "by": "ci.yml"},
      {"path": "scripts/lint.sh", "did": "eslint over src/", "by": "scripts/check", "retired": true}
    ]
  },
  "ownership": [
    {"path": ".repo-template.json", "mode": "managed"},
    {"path": "CLAUDE.md", "mode": "managed"},
    {"path": "scripts/**", "mode": "managed"},
    {"path": ".github/**", "mode": "managed"},
    {"path": ".claude/settings.json", "mode": "managed"},
    {"path": ".pre-commit-config.yaml", "mode": "managed"},
    {"path": ".commitlintrc.yaml", "mode": "managed"},
    {"path": ".gitattributes", "mode": "managed"},
    {"path": ".gitignore", "mode": "managed"},
    {"path": ".worktreeinclude", "mode": "managed"},
    {"path": ".mcp.json", "mode": "managed"},
    {"path": "apps/**", "mode": "product"},
    {"path": "libs/**", "mode": "product"},
    {"path": "tests/**", "mode": "product"},
    {"path": "tools/**", "mode": "product"},
    {"path": "docs/**", "mode": "product"},
    {"path": ".claude/hooks/**", "mode": "product"},
    {"path": ".claude/rules/**", "mode": "product"},
    {"path": ".claude/skills/**", "mode": "product"},
    {"path": ".claude/agents/**", "mode": "product"},
    {"path": ".claude/output-styles/**", "mode": "product"},
    {"path": ".claude/workflows/**", "mode": "product"}
  ]
}
```

The `ownership` array above illustrates the shape at the time this contract was written; it is not a canonical list to copy. Build it from the payload's actual top-level structure at the resolved source commit — e.g. `git ls-tree -r --name-only <commit> -- <subtree>` — rather than pasting this example, since the template's real paths can drift from documentation prose without this file being updated to match.

Use a full lowercase 40-character commit. `template.commit` is the last template version successfully applied to the candidate state. Change it only after the candidate passes verification; commit it with the update it describes.

Record generation choices that change rendered files or repository settings. Do not record timestamps, a pending target commit, destination HEAD, or duplicate file contents.

Do not record what the filesystem already answers. Language and package manager are read from the manifests present, so a recorded copy is a second source of truth that only goes stale — `libs/detect.sh` answers the question at any moment and a manifest added later never updates a field. Visibility is live-readable the same way and is recorded by no flow: a repository that goes public leaves the record saying private, and every decision that turns on visibility reads it from the API at the moment it decides. `features` is the exception, because it records which absences were deliberate: an omitted `codeql.yml` and a dropped one look identical on disk.

`generation.applications` lists the deployable names [Wayfinding](wayfinding.md) established, and nothing else about them. It is recorded because an update has to know that `apps/app-name` was renamed rather than deleted, which the destination tree can no longer say. The choke point and the language behind each name are not recorded here: the language is answered by the manifests present under the rule above, and the choke point is an argument rather than a fact, so it belongs in the ADR that makes it. A manifest still recording the earlier single `application_name` is left as it is — it records what that generation chose, and an update rewriting it would claim a decision the update did not make.

## Ownership

Ownership answers whether a path participates in template updates:

- `managed`: inspect changes from the template, but reconcile them with destination intent. It never means blind overwrite.
- `product`: preserve automatically. If a new template path collides with product content, report the collision and stop.
- unmatched: product-owned by default.

The longest matching path wins; equal patterns are invalid. The old-to-new template delta bounds update scope. Do not edit an unrelated destination path merely because a broad ownership rule matches it.

Unmatched defaulting to product is the safe direction for a path the template does not ship, and the wrong one for a path it does. A file at the repository root matches no directory pattern, so `CLAUDE.md`, `.pre-commit-config.yaml`, `.commitlintrc.yaml`, `.gitattributes`, and `.gitignore` fall through to product unless named individually — and those files carry the instructions every agent session in the destination reads, the pinned hook revisions behind the secret scanner, the commit-message rules, and the merge policy keeping a lockfile from being line-merged. The list grows: every root file the payload adds needs a line here, or a payload fix to it lands nowhere while the update reports success. Every path the template ships needs an ownership rule that reaches it; verify with `classify_path` rather than assuming a directory pattern covers a file at the root.

The root `CLAUDE.md` is managed for that reason and merged rather than overwritten, which is what `managed` already means: the destination writes its own project instructions into the same file the template ships, so an update reconciles the template's change with what the destination wrote and stops only where the two say different things about the same rule.

A rename or delete of a destination-modified managed file needs semantic review. Product-created files under managed directories remain untouched unless the new template introduces the same path.

An adopted addon is one of those files. `CHANGELOG.md` matches no pattern and defaults to product; `.claude/rules/changelog.md` falls under the product-owned `.claude/rules/**`. Neither is a deletion to reconcile. The template never having shipped a path is not the template having removed it, and an update that reads it that way deletes a record the destination chose to keep.

### Overridden paths

An **overridden path** is a payload path a flow did not land, because the destination's own version was chosen over it. Ownership says whether a path participates in updates at all; an override says this particular managed path was settled once, against the payload, and the answer stands. Every flow that resolves a collision records it, in `generation.overrides`:

```json
"overrides": [
  {"path": "docs/agents/issue-tracker.md", "reason": "destination tracks issues outside GitHub"}
]
```

- One entry per path, with the reason the destination's version was chosen. A path with no reason is not a decision anyone can review later, and the next update has nothing to weigh the entry against.
- An update skips a delta path listed here rather than reporting it as a conflict. That is the whole point: without the record every update re-raises the same collision and asks for a policy decision that was made once already.
- **An entry expires with the thing it records.** Where the destination has deleted its own version of an overridden path, the override has nothing left to protect: the update lands the payload's copy and drops the entry, both in the same pull request. A record outliving its subject is how the payload's file stays permanently absent for a reason nobody holds any more.
- An overridden path was never written, so it is absent from the copy proof [Reviewing the pull request](reporting.md#reviewing-the-pull-request) runs, and belongs to neither the copied set nor the authored surface. Name it as overridden in the report instead, with its reason.

## The automation directory is replaced, not reconciled

The payload's automation is a guarantee the template makes about every repository built from it, so it is not a collision to decide per file. `.github/` is replaced whole (`workflows/`, `actions/`, `dependabot.yml`, `zizmor.yml`, `ISSUE_TEMPLATE/`, and `PULL_REQUEST_TEMPLATE.md`), and the destination's version of that tree does not survive the flow. Reconciling it per file produces a repository whose CI is half the template's and half something else, which is the one state no later update can reason about: the template's guarantee is that these files are the payload's, and a merged `ci.yml` satisfies nothing.

`codeql.yml` is the one path inside the prefix that this does not settle: whether it lands at all is decided by [Code scanning follows visibility](#code-scanning-follows-visibility), and only then is it replaced like the rest.

It follows that the replacement is not declinable, and there is no `features` entry for an owner who says no. A refusal is a refusal of the flow, not of one directory, and a record of it would describe a repository this skill did not build.

**The carve-out is exactly that path prefix.** Rule 4 of [Into a repository that already has content](generate.md#into-a-repository-that-already-has-content), never delete destination content to resolve a collision, still binds absolutely everywhere else, because nothing here is resolved as a collision. `docs/agents/` in particular is untouched by this: a destination's own agent documentation is decided per file under the collision rules the same as before, and a destination's `issue-tracker.md` still wins.

The deliberate consequence, stated because it is wider than the guarantee motivating it: a destination's own `PULL_REQUEST_TEMPLATE.md` and `ISSUE_TEMPLATE/` go too. They are not CI and nothing about provenance requires replacing them; they are inside the directory the rule names, and a rule that stopped short of them would need a second exception list nobody would keep current. Name them in the report as the loss they are. Where the destination had a `.github/PULL_REQUEST_TEMPLATE/` directory of its own, [addon adoption](addon-adoption.md) offers the payload's `release.md` and `hotfix.md` back afterwards; say so in the same report line, so the loss and the offer are read together rather than as two unrelated events.

Superseded content is reported, never silently dropped. Every superseded path is named with what it did, and recorded in `generation.superseded` as `{path, did, by}`:

- `path` — the destination path that no longer exists.
- `did` — what it did, in the words of whoever reads the report, so a later reader can tell a duplicate of `ci.yml` from the deploy job nobody replaced.
- `by` — the payload path that now carries it, or the check that does.

An update reads this list before treating an absent destination path as a deletion to reconcile, which is what stops it re-litigating the replacement on the next run.

### Retiring a covered gate script

A destination's gate scripts are not in `.github/`, so they are not replaced. They are still where duplication collects: the payload ships `scripts/check` and the six per-language capabilities behind it, and a destination that had CI has scripts doing some of the same work.

- **Fully covered** — everything the script does is a capability the payload's check surface already dispatches. Retire it: delete the script, repoint every caller at the payload command, and record it in `generation.superseded` with `"retired": true`. It is a retirement rather than a deletion because the behaviour survives under a different name, which is what makes it exempt from rule 4; a caller left pointing at the old path is a broken retirement, so report the callers by path with the retirement.
- **Partially covered** — the script does something the check surface does not, a deploy step or a repository-specific probe. It survives, and the overlap is a conflict to report: name the duplicated parts specifically, so whoever owns the script can cut them, and do not cut them here. Deciding which half of somebody's script is redundant is the policy decision this skill escalates rather than makes.

## Code scanning follows visibility

Code scanning is free on a public repository and unavailable on a private one. `codeql.yml` is therefore the one payload workflow whose landing is conditional, and the condition is the destination's visibility read live with `gh api "repos/<owner>/<repository>" --jq .visibility` at the moment the flow decides. No record answers this: a repository that went public after it was built has a record still saying private, and a flow reading that record strips a workflow the repository can now run.

- **Public destination**: `codeql.yml` lands with the other three workflows and its run goes green. Nothing is recorded; the payload's default needs no note.
- **Private destination**: `codeql.yml` is stripped, so the destination takes one workflow file fewer than the payload ships, and `generation.features` records `"codeql": "omitted-by-choice"`. An omitted file and a deleted one look identical on disk; the record is the only thing that can say which it was, and it is what a later flow reads before concluding the destination dropped a workflow the template ships.

The value is exactly the string `omitted-by-choice` and carries no reason: `scripts/github-parity` selects on `.value == "omitted-by-choice"`, so a reason folded into the value fails that match silently and the omission stops being excused. The reason goes in the report instead.

Every flow that writes workflows follows this: [generate](generate.md), [update](update.md), and retrofit alike, each citing this section rather than restating the branch. [Adopt](adopt.md) is absent because it writes no workflow at all, landing only the addons `addon-adoption.json` names.

`scripts/github-parity` reads the record the same way in this repository, which is the one place it runs against a payload: a payload-only workflow is excused exactly where `generation.features` records the omission, and a repository that simply lost `codeql.yml` is not. In a generated repository there is no payload tree to compare against and the check reports `not-applicable`, so nothing there enforces this and the record is read by the flows alone.

## Running the destination's checks

Every flow runs the candidate's or the destination's own documented checks before it publishes anything. Three rules hold across all of them.

Stage the work first. A bare `pre-commit run --all-files` enumerates through the Git index, so unstaged work is checked as the empty set and reports a pass over nothing. The repository's own `scripts/check` sweeps untracked files by path after that command, but only if the payload it was built from carries that second pass — verify rather than assume it.

Read the run through the repository's own `scripts/summarize`, which takes the command and prints only its Result table — `scripts/summarize scripts/check`. A filter built by hand for the occasion answers a different question than "what did every check do": `grep -iE "FAIL|error"` is the usual improvisation and it misses `unavailable`, which is equally a failing state and the one most often written into a report as a pass. It exits with the command's own status and says so when a failing exit came from something outside the table, so it stands in for the command rather than only summarizing it. A payload old enough not to ship it is the case for reading the raw output; check before assuming.

Report a check by what it did, and keep the four outcomes distinct: a check that passed, one that reported nothing to do, one whose runner was missing, and one that never ran. Report a skipped or unavailable check as skipped or unavailable; do not call it a pass. The repository's own scripts make that distinction, and collapsing it in the report discards the thing they were built to preserve. A run reporting no project manifest checked nothing; a green pull request with no workflow runs verified nothing; a file that was never written cannot fail. Tools a script looks up on `PATH` may also run inside pre-commit's pinned environments, so a tool reported unavailable by a script and passing under pre-commit in the same run was not skipped; report what each surface actually did.

### Tools the first manifest must declare

The check surface names capabilities and dispatches per language; it reads no record and holds no exemption list beyond the template-wide one it already ships, so a repository cannot silence a check by editing a manifest field. What it does mean is that a manifest which does not declare the tool an adapter reaches for produces `NO_RUNNER`, reported as `unavailable` and failed exactly as a real failure is. The first real commit brings the root manifest and owes these declarations with it. Name them in the flow's handover, per language, including the empty ones:

- **python** — `ruff`, `ty`, and `pytest`, as dependencies in `pyproject.toml`. Every one of them runs through `uv run`, so an undeclared tool is not on the resolved environment's path.
- **node** — six `package.json` scripts rather than tools: `lint`, `format:check`, `typecheck`, `test`, `build`, `format`. The adapter checks for the script name, not for what it invokes, so the choice of linter is the repository's.
- **kotlin** — a `ktlint` or `detekt` Gradle plugin in the build file, for lint and formatting. `test` and `build` need only the wrapper.
- **go** — none. `go vet`, `gofmt`, `go test`, and `go build` ship with the toolchain.
- **rust** — none. `cargo clippy`, `cargo fmt`, `cargo test`, and `cargo build` come from the toolchain and its rustup components.
- **swift** — none. `swift format`, `swift test`, and `swift build` are the compiler's own subcommands.

The empty three are stated rather than omitted: a language missing from the list reads as an oversight, and the next reader re-derives it from `libs/detect.sh`.

Separately, the security scanners and toolchain probes are `PATH` lookups and open no manifest, so declaring them there does nothing: `govulncheck`, `cargo-audit`, `trivy`, `gitleaks`, `uv` itself, and `npm`/`pnpm`/`yarn`. Absent, they report `unavailable` whatever a manifest says.

An update owes nothing here. The root manifest is product-owned and never enters an update's delta.

A machine-wide `core.hooksPath` set for an unrelated purpose (an editor's own git integration, another agent's attribution hook) makes `pre-commit install` refuse outright, and breaks it again inside any throwaway fixture repository the repository's own tests spin up to exercise hook installation — fixtures inherit the same global config. Check `git config --global core.hooksPath` before treating either failure as a defect in the repository under test; a control run of the same checks against the template repository's own current HEAD reproduces an identical failure when this is the cause.

The two halves have different remedies and neither is to unset the operator's key. A fixture is fixed by isolation, which the repository's own `scripts/tests/libs/harness.sh` already applies. A destination clone is fixed by installing under a neutralized global config and then pinning the key locally, so the hooks land in the clone and git is looking where they landed:

```sh
GIT_CONFIG_GLOBAL=/dev/null pre-commit install
git config --local core.hooksPath "$(git rev-parse --path-format=absolute --git-common-dir)/hooks"
```

Both lines are needed and neither suffices alone. The first installs the files; without the second git keeps reading the shared directory and every installed hook is a silent no-op, which is why `scripts/doctor` asks `git rev-parse --git-path hooks` rather than looking in `.git/hooks`. The pin then shadows whatever the shared directory held, so link each of those hooks back into the clone before pinning: as `<type>.legacy` where pre-commit installed a hook of its own, since `pre-commit hook-impl` runs that file first, and under its own name where pre-commit installed nothing there to chain from. Removing and restoring the operator's global key around the install is not the shortcut it looks like: every other process on the machine reads the wrong config for the duration.

## Remote action gates

Repository creation, settings writes, pushes, and pull-request creation are separate outward-facing actions. Plan and validate locally first. Immediately before them, show:

```text
Remote execution
- create: owner/repository (private, uninitialized)
- push: empty root commit -> main
- settings: Dependabot alerts/updates; push protection if available; the merge commit as the only merge method; automatic head branch deletion; main ruleset
- settings drift: on an update or an adopt, one line per setting `scripts/repo-settings check` reported missing — current value, proposed value, exact `gh api` command — authorized separately from the push below
- push: throwaway ruleset probe -> main, only where ruleset creation returned 201; rejection is what proves the ruleset binds, so a ruleset that was accepted without binding leaves that commit on the remote default branch
- labels: created by step 6 — the twelve `docs/agents/` names, being the roles `docs/agents/triage-labels.md` records plus `wayfinder:map` and the four `wayfinder:<type>` labels, and only those the repository does not already carry; where the payload's file is the one in force, a label the repository carries under a different case is renamed to the payload's spelling rather than created, and the rename is its own line
- issues: map and tickets from `/wayfinder`, if the tracker doc records a hosted tracker
- push: repo-builder/<short-target> -> generated content or template update
- open PR: repo-builder/<short-target> -> main
- merge: repo-builder/<short-target> -> main (bootstrap generate only, see Generate step 12)
```

Read the block as a menu rather than a sequence — no gate shows every line. Settings drift is raised by an update and an adopt and never by a generate, since a generate applies the settings it just listed and nothing has drifted from anything. A generate into a repository that already has content is still a generate here: it applies the merge settings rather than reporting them as drift, and states their current values on the gate, because it is the one flow that overwrites a hosted setting someone deliberately chose.

A generate reaches this twice, and the two gates authorize different things. The first, at [Generate](generate.md) step 4, covers every line through `issues` except settings drift: an empty repository, its settings, the probe that proves those settings bind, and the tracker writes steps 6 and 7 make against it — with no diff and no check result to show, because nothing has been built yet. Present them together even though steps 5 through 7 perform them later, since returning for a second authorization between each is noise; what the gate may not do is perform a remote write it did not list. The labels and issues lines carry their condition in their own text rather than being dropped, because which labels are missing and which tickets the map holds are not known until steps 6 and 7 run; a destination whose own tracker doc records local markdown makes neither write, and that authorization simply goes unused. The second, at step 11, covers the rest against a candidate that has been personalized, checked, and file-list reconciled. Show only the lines the gate is actually asking for. Presenting the whole block at step 4 takes authorization for a content push that does not exist yet.

Ask for confirmation unless the invocation already authorizes these exact actions against this exact repository. Authorization for repository creation does not imply settings changes or a later merge. Never merge as part of this skill, except the bootstrap-generate case documented under [Generate](generate.md) step 12: that PR may be merged, gated the same as every other remote action here.

## Failure and recovery

Stop before editing when:

- the manifest is absent, malformed, or records a non-full commit;
- the destination is dirty or origin differs from the manifest;
- either payload subtree is unavailable;
- the recorded commit is not an ancestor of the target;
- ownership is ambiguous.

The [Wayfinding](wayfinding.md) handoff is also a stop, and the one that is not a failure: nothing is wrong, the decomposition is simply not this skill's to settle. Report it as `stopped` like any other, but do not report it as a defect in the candidate or the request, and do not discard the materialized candidate — it is what the resumed session re-enters at. By this point the destination repository exists, configured, with its default branch still the empty root commit and its map on its tracker. That is the state to leave and to describe, not a half-finished generate to roll back; the repository is where the map lives, so deleting it discards the only thing the stop produced.

Stop before further remote actions when semantic intent conflicts or verification fails. On a [generate](generate.md) that no longer means before any remote action at all: steps 4 and 5 have already created the repository and applied its settings, so a failure at any step from 5 to 10 leaves a real repository whose content was never published. Its default branch is the empty root commit, except after a failure at step 5 where the probe ran and was not rejected: its commit stays there. Name it, say what it already carries, and say whether resuming against it or deleting it is the next action — a stop reported as though nothing was created sends the user looking for a repository they already own. Keep `template.commit` at the previous version. Report exact paths, Git evidence, checks, and a recoverable next action. Do not approximate a missing old version, rebase unrelated template histories, reset/clean the destination, or claim a partial update succeeded.

## Reviewing and reporting

Both belong to the end of a flow and both are in [`reporting.md`](reporting.md): [Reviewing the pull request](reporting.md#reviewing-the-pull-request), which is how a candidate is proved to be a copy rather than code-reviewed, and [Final report](reporting.md#final-report), the shape every flow ends in. Read that file when a flow reaches its review, not before — it is a third of this contract by size and none of it bears on anything earlier.
