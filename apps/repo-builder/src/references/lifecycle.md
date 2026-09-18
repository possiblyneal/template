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
      {"path": "CLAUDE.md", "reason": "destination keeps its own instruction file"}
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
    {"path": "tmp/.gitkeep", "mode": "managed"},
    {"path": ".env", "mode": "product"},
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

Do not record what the filesystem already answers. Language and package manager are read from the manifests present, so a recorded copy is a second source of truth that only goes stale; `libs/detect.sh` answers the question at any moment and a manifest added later never updates a field. Visibility is live-readable the same way and is recorded by no flow: a repository that goes public leaves the record saying private, and every decision that turns on visibility reads it from the API at the moment it decides. `features` is the exception, because it records which absences were deliberate: an omitted `codeql.yml` and a dropped one look identical on disk.

`generation.applications` lists the deployable names [Wayfinding](wayfinding.md) established, and nothing else about them. It is recorded because an update has to know that `apps/app-name` was renamed rather than deleted, which the destination tree can no longer say. The choke point and the language behind each name are not recorded here: the language is answered by the manifests present under the rule above, and the choke point is an argument rather than a fact, so it belongs in the ADR that makes it. A manifest still recording the earlier single `application_name` is left as it is — it records what that generation chose, and an update rewriting it would claim a decision the update did not make.

A retrofit writes the same field from the unit names the operator confirmed, and writes no field beside it. The run and ship facts belong to each unit's own `.unit.json`, and the evidence they were proposed from belongs to the architecture record; a copy of either here would be a third source of truth for a value the tree already answers. Units read out of a destination's own evidence and deployables established by wayfinding land in one field on purpose: an update reads unit names to tell a rename from a deletion, and that question is the same however the names were arrived at.

## Ownership

Ownership answers whether a path participates in template updates:

- `managed`: inspect changes from the template, but reconcile them with destination intent. It never means blind overwrite.
- `product`: preserve automatically. If a new template path collides with product content, report the collision and stop.
- unmatched: product-owned by default.

The longest matching path wins; equal patterns are invalid. The old-to-new template delta bounds update scope. Do not edit an unrelated destination path merely because a broad ownership rule matches it. An expired override is the one write outside that bound, and [Overridden paths](#overridden-paths) is where it is settled.

Unmatched defaulting to product is the safe direction for a path the template does not ship, and the wrong one for a path it does. A file at the repository root matches no directory pattern, so `CLAUDE.md`, `.pre-commit-config.yaml`, `.commitlintrc.yaml`, `.gitattributes`, and `.gitignore` fall through to product unless named individually, and those files carry the instructions every agent session in the destination reads, the pinned hook revisions behind the secret scanner, the commit-message rules, and the merge policy keeping a lockfile from being line-merged. The list grows: every root file the payload adds needs a line here, or a payload fix to it lands nowhere while the update reports success. Every path the template ships needs an ownership rule that reaches it; verify with `classify_path` rather than assuming a directory pattern covers a file at the root. In this repository that claim is settled mechanically — `test_reference_assertions.py` matches every payload path against both this manifest's list and the example above, so a payload path added without a rule fails the commit rather than quietly leaving the template's later fix nowhere to land.

Reaching a path is not the same as managing it. `.env` is reached and **product**: the payload ships an empty one so the file exists, and everything in a destination's copy is the destination's. Naming it is what makes that a decision rather than the default falling the same way by accident — and the default is what an added payload path would inherit next time.

The root `CLAUDE.md` is managed for that reason and merged rather than overwritten, which is what `managed` already means: the destination writes its own project instructions into the same file the template ships, so an update reconciles the template's change with what the destination wrote and stops only where the two say different things about the same rule.

A rename or delete of a destination-modified managed file needs semantic review. Product-created files under managed directories remain untouched unless the new template introduces the same path.

An adopted addon is one of those files. `CHANGELOG.md` matches no pattern and defaults to product; `.claude/rules/changelog.md` falls under the product-owned `.claude/rules/**`. Neither is a deletion to reconcile. The template never having shipped a path is not the template having removed it, and an update that reads it that way deletes a record the destination chose to keep.

### Overridden paths

An **overridden path** is a payload path a flow did not land, because the destination's own version was chosen over it. Ownership says whether a path participates in updates at all; an override says this particular managed path was settled once, against the payload, and the answer stands. Every flow that resolves a collision records it, in `generation.overrides`:

```json
"overrides": [
  {"path": "CLAUDE.md", "reason": "destination keeps its own instruction file"}
]
```

- One entry per path, with the reason the destination's version was chosen. A path with no reason is not a decision anyone can review later, and the next update has nothing to weigh the entry against. `preflight.py` refuses a malformed record before a flow acts on it: a non-list, an entry that is not an object, a missing or empty `path` or `reason`, and two entries naming one path.
- **An entry is only ever about a managed path.** Ownership already grants the destination every product-owned path, so an entry on one asserts nothing, and it is not merely redundant: an overridden path leaves the product tally as well as the managed one, so the delta summary under-reports the destination's own files. `preflight.py` refuses it, naming the path and the ownership rule that made it product-owned, and resolving ownership exactly as the delta does, an unmatched path included. A collision a product-owned destination file won is still reported by name with the reason it won, under Reconciliation: ownership is what makes that version stand, so there is a line to write and no entry to record.
- An update skips a delta path listed here rather than reporting it as a conflict. That is the whole point: without the record every update re-raises the same collision and asks for a policy decision that was made once already. A delta renaming the path is still that path: the entry names what the destination held, so a rename is matched under its source name as well as its destination one.
- **An entry expires with the thing it records.** Where the destination has deleted its own version of an overridden path, the override has nothing left to protect: the update lands the payload's copy and drops the entry, both in the same pull request. A record outliving its subject is how the payload's file stays permanently absent for a reason nobody holds any more. Expiry is read from the entries against the destination rather than from the update's delta: a destination deleting its own version changes nothing on the template's side, so an expired entry sits inside the delta as readily as outside it. `preflight.py update` settles both halves from the destination's tracked paths alone. A delta path whose entry the destination no longer holds is marked `override_expired` rather than overridden, so it stays an ordinary managed change to apply. Every entry the delta does not reach is listed in `unmatched_overrides`, `expired` where the destination no longer holds the path and `unreached` where it still does and this delta simply passed it by. Only expiry ends the entry.
- Adopt neither writes nor reads an entry. It lands an addon the destination does not have, at the recorded commit, and resolves no collision, so it never meets an override. Generate, retrofit, and update are the flows this section binds.
- An overridden path was never written, so it is absent from the copy proof [Reviewing the pull request](reporting.md#reviewing-the-pull-request) runs, and belongs to neither the copied set nor the authored surface. Name it as overridden in the report instead, with its reason.

### The payload's mode travels with the payload's content

Wherever a flow lands a payload path, the file ends at the mode the payload declares. This is free for a path the destination does not have — `git archive` carries the mode out of the tree it reads — and it is the part that has to be said for a path the destination does have, because rewriting a file in place keeps the mode it already had. A payload file arrives with the destination's bit set, and the destination's bit was set for the destination's version.

`.gitignore` is the one both reference retrofits hit: `100755` in the destination, `100644` in the payload, landed executable. It fails at `check-executables-have-shebangs` in the commit after the write, which names the file and not the step that wrote it, so the operator reads a pre-commit refusal with no visible cause.

Every flow that lands payload content is bound: the overlay of an absent path, a collision disposed to the payload, the ignore file and the automation directory replaced whole, and an update applying a managed delta. Set the mode from the payload at the resolved source commit rather than from what the file on disk already carries — `git ls-tree <commit> -- <subtree>/<path>` prints it in the first field. Read it from the pinned tree and not from the template clone's index or working tree, for the reason every other payload read here is pinned: a clone checked out somewhere other than the target commit answers for a payload the flow is not landing.

## The automation directory is replaced, not reconciled

The payload's automation is a guarantee the template makes about every repository built from it, so it is not a collision to decide per file. `.github/` is replaced whole (`workflows/`, `actions/`, `dependabot.yml`, `zizmor.yml`, `ISSUE_TEMPLATE/`, and `PULL_REQUEST_TEMPLATE.md`), and the destination's version of that tree does not survive the flow. Reconciling it per file produces a repository whose CI is half the template's and half something else, which is the one state no later update can reason about: the template's guarantee is that these files are the payload's, and a merged `ci.yml` satisfies nothing.

Two paths inside the prefix this does not settle on its own, and each is decided by a rule rather than by flat replacement. `codeql.yml`: whether it lands at all is decided by [Code scanning follows visibility](#code-scanning-follows-visibility), and only then is it replaced like the rest. `dependabot.yml`: it is replaced like the rest and then gains the entries [Dependabot entries follow the manifests present](#dependabot-entries-follow-the-manifests-present) derives from the destination's manifests. Neither is a merge of the destination's version, which is what the guarantee above is protecting — the file is still written whole from template-owned logic, and the destination supplies evidence rather than content.

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

## Dependabot entries follow the manifests present

`.github/dependabot.yml` sits inside the directory [replaced, not reconciled](#the-automation-directory-is-replaced-not-reconciled), and the payload's copy lists only the two ecosystems whose manifests the template itself ships: `github-actions` and `pre-commit`. It cannot list any of the language ecosystems ahead of the manifest that would justify one, because an entry naming a manifest that is not there fails the whole run with `dependency_file_not_found` rather than being skipped — the second entry does not get its bump.

So every flow that writes the file **derives the language entries from the manifests the destination actually holds** and appends them to the two the payload ships. The file's header states the mapping for a human reader, and that is not the mechanism: an instruction addressed to nobody is how a destination ends up with a manifest Dependabot never watches, which is a whole class of silent gap rather than one repository's missing line.

**The list is re-derived every run, never preserved.** The file is managed and replaced whole, so an entry added by hand does not survive the next update — this repository's own `pip` entry carries a comment saying exactly that. Recomputing from what is on disk makes the entry survive by being rebuilt rather than by being carried, which is why this is not an [override](#overridden-paths), not one of update's four reconciliation rules, and not a per-destination exception anybody has to remember. It runs in the other direction too: a manifest deleted since the last run loses its entry without anyone removing it, and that removal is not cosmetic — the stale entry is what would fail the run.

**One entry per manifest, at the manifest's own directory.** `directory` takes the directory holding the manifest — `/apps/glydr`, not `/` — so an entry cannot be derived from the ecosystem name alone, and a repository whose only module sits under `apps/` is the ordinary case rather than the exotic one. Where one ecosystem has manifests in several directories, put them in the plural `directories` list, the form the payload's `github-actions` entry already uses; repeating the ecosystem is also accepted, and splits one ecosystem's cooldown and group across two places that then drift.

| Manifest | `package-ecosystem` |
|---|---|
| `package.json` | `npm` |
| `pyproject.toml` | `pip` |
| `go.mod` | `gomod` |
| `Cargo.toml` | `cargo` |
| `build.gradle.kts` | `gradle` |
| `Package.swift` | `swift` |

**A workspace file is not a manifest.** `go.work` and `settings.gradle.kts` say where the modules are; they are not what Dependabot reads. A destination with a root `go.work` and one `apps/<name>/go.mod` takes a single `gomod` entry at `/apps/<name>` and none at `/`. Whether an entry at `/` would *also* reach that module is Dependabot's own discovery behaviour rather than a fixed rule, and it moves: `go.work` discovery was merged into `dependabot-core` in `dependabot/dependabot-core#14909` on 2026-05-05, which dates the change to the engine rather than its rollout to every repository, and a root holding a `go.work` and no `go.mod` is the narrow case where an entry at `/` had nothing to read before it. Derive from the manifests regardless — that is the form this rule can state without tracking a per-ecosystem feature it does not control. It is also the hand-enumerated per-module list that upstream change was written to retire, and the reason it is still right here is that the whole set is rebuilt every run: what made the enumeration fragile was keeping it in step by hand. **Read the manifests from the tracked files, with `git ls-files`.** Not from `has_<lang>` in `scripts/libs/detect.sh`, which answers only whether a *root* manifest is present, and not from a search of the working tree pruned by `DETECT_PRUNE_DIRS` — that list is `.git node_modules .build target .venv venv vendor tmp`, written for root-manifest detection rather than for a walk, and it does not name `.claude/worktrees/`, where this repository keeps gitignored checkouts of itself. A pruned search run here today returns two `pyproject.toml` that are not in the repository, and an entry naming one of them fails the whole run with the error this rule exists to prevent. What Dependabot reads is the pushed tree, so the tracked set is not an approximation of the right answer — it is the right answer. Exclude the payload under `apps/github-repository-template/src/base-repo/`, which is data destined for other repositories rather than a manifest of this one; it ships none today, and an entry derived from one it later ships would name a path no destination has.

**An ecosystem outside the table is not derived, and not silently dropped either.** Dependabot watches far more than the six languages this template detects, so a destination may hold an entry for `docker`, `terraform`, `nuget`, `bundler` or another the mapping does not cover. The derivation cannot rebuild what it cannot recognize, and replacing the file whole would delete such an entry with its manifest still in place. So read the destination's copy of the file before replacing it and report every `package-ecosystem` in it the table does not cover, by name, on the flow's own gate — the entry is a decision the destination made and reinstating it is the destination's to authorize. This is the one thing the derivation makes worse rather than better, and naming it on the gate is what keeps it from being the silent loss this rule was written against.

The table points the other way too. A tracked manifest whose filename it does not list — a Groovy `build.gradle`, a `requirements.txt` or `setup.py` where the template expects `pyproject.toml` — earns no entry, and a destination that predates the template is the likeliest place to find one. Do not widen the table to cover it: the six are the template's own language vocabulary, `scripts/libs/detect.sh` keys on the same six, and a seventh recognized here and nowhere else is a shape the rest of the checks cannot see. Report it on the same gate instead, by path, as a manifest Dependabot is not watching and why. That leaves a person to decide, which is what the rest of this rule exists to avoid — the difference is that here the decision is whether the repository should be carrying that manifest shape at all, and no flow can answer it.

**A derived entry carries the policy the payload's own entries carry** — `interval: weekly`, `cooldown.default-days: 7`, and one group matching `*` named for the ecosystem — so where it came from is the only thing about it that differs from a shipped one. The cooldown in particular is the reason a bump is reviewed rather than noise: a derived entry without it is the one difference a reader would have to account for.

**The file's own check run is not required, is usually absent, and green does not mean the entries are right.** GitHub sometimes validates `.github/dependabot.yml` and posts a check named for the path, and the check belongs to the commit whose push changed the file rather than to the pull request. So it is missing from the rollup whenever the head is a later commit that left the file alone — a follow-up commit, or an update whose re-derived set is byte-identical to what the destination already had, which is the ordinary case for an update about something else. It is not even reliable on a commit that does change the file: on `possiblyneal/template`, `57152c8` carried the check and `148b113` changed the same two copies and carried none. Never add it to the required set a flow polls: a candidate that waits for a check GitHub did not post waits forever, which is a worse failure than the one this paragraph is about. Read it where it happens to be there, as the schema check it is — it answers whether the YAML is valid and every key is one Dependabot knows, and it never opens the directories the entries name. `dependency_file_not_found` is a failure of the update run rather than of the config, so it is reported days later against a green check.

That is the failure this rule exists to prevent, so the check run does not verify it, and its absence verifies nothing either way. Parse the file that was written instead — one entry per tracked manifest, each `directory` a directory that manifest is actually in — and report that parse as the reason to believe the entries resolve, naming the check run's result only where one was posted. A flow reporting a green check has reported that the file is well-formed and called it evidence that the entries work.

The rule binds [generate](generate.md), [update](update.md), and retrofit alike. [Adopt](adopt.md) is absent because it writes no `.github/` path at all.

## Architecture records live at the root documentation path

Every architecture record the payload governs sits in `docs/adrs/` at the repository root, in every flow, whatever scope the decision has. A record about one unit is still a root record; its `scope` frontmatter field is what says which unit it is about, and `apps/<name>/docs/adrs/` is never where one goes.

Two facts make this a rule rather than a convention. `scripts/adr-index` hardcodes the directory it rewrites the index from, so a record anywhere else is absent from the index the repository publishes. And `scripts/structure` has no rule for records at all: `docs/` takes Markdown freely at every scope, so a record under a unit passes the audit. The two together are what makes a misplaced record invisible instead of loud, which is the failure this rule is against. Whether the audit should enforce the location is a question for the audit and not for these flows.

The rule binds [generate](generate.md), [update](update.md), [adopt](adopt.md), and retrofit alike. It is stated once here because only retrofit meets records already written somewhere else, and a rule stated only there would read as retrofit's own preference rather than as the repository-wide placement every flow writes to.

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

The adapters under `scripts/libs/` are the source of truth and this list follows them; nothing checks that it still does. A renamed tool drifts here silently, so read the adapter for the language before trusting a name, and correct this list when the two disagree. It is written out anyway because the reader it is for has no repository to read the adapters in yet.

Separately, the security scanners and toolchain probes are `PATH` lookups and open no manifest, so declaring them there does nothing: `govulncheck`, `cargo-audit`, `trivy`, `gitleaks`, `uv` itself, and `npm`/`pnpm`/`yarn`. Absent, they report `unavailable` whatever a manifest says.

An update owes nothing here. The root manifest is product-owned and never enters an update's delta.

### Working hooks in a candidate

Every flow measures a tree against the check surface, and the surface's first gate fails when the hooks git will consult are missing. So every flow installs them first, by one recipe.

A machine-wide `core.hooksPath` set for an unrelated purpose (an editor's own git integration, another agent's attribution hook) makes `pre-commit install` refuse outright, and breaks it again inside any throwaway fixture repository the repository's own tests spin up to exercise hook installation — fixtures inherit the same global config. Check `git config --global core.hooksPath` before treating either failure as a defect in the repository under test; a control run of the same checks against the template repository's own current HEAD reproduces an identical failure when this is the cause.

The two halves have different remedies and neither is to unset the operator's key. A fixture is fixed by isolation, which the repository's own `scripts/tests/libs/harness.sh` already applies. A working tree is fixed by writing the shims into a directory of its own and pointing git at that directory, which is what `pre-commit init-templatedir` is for. Unlike `pre-commit install` it does not refuse while `core.hooksPath` is set at any scope, and the shims it writes are repository-independent, so the same directory serves whatever tree points at it:

```sh
pre-commit init-templatedir -t <each configured type> <hooksdir>
git -C <tree> config <scope> core.hooksPath "<hooksdir>/hooks"
```

`<hooksdir>` is a sibling of the tree in the scratch tree, beside the resume record, for the reason [Resuming](#resuming) gives for that record: inside the tree it enters the diff, the copy proof, and the structure audit as a directory the payload does not ship.

Read the hook types from `pre_commit_hook_types` in `scripts/libs/precommit.sh`, against the `.pre-commit-config.yaml` the tree actually carries. That is the same helper `pre_commit_hooks_missing` grades against, so setting up from it is what makes setup and the check agree; a hand-written list of types passes the setup and fails the grade the first time `default_install_hook_types` changes.

`<scope>` is the one thing that varies by flow, and only retrofit needs the unusual one:

- **Retrofit** — `--worktree`, with `git -C <clone> config extensions.worktreeConfig true` set first. Its candidate is a linked worktree, so `core.hooksPath` at local scope is the main clone's config and setting it there repoints the operator's own clone at a directory this flow created. The per-worktree scope is retrofit's alone because retrofit's candidate is the only one borrowing a hooks directory it does not own.
- **Generate** — `--local`. The candidate is a dedicated clone with no parent to protect.
- **Update and adopt** — `--local`. They run in the operator's own clone, where installing the hooks is the correct outcome rather than a side effect to contain.

Setting the key is itself a change to a tree somebody else owns, in every scope but generate's, and two of those changes outlive the flow. Report both by name. `extensions.worktreeConfig` is written at local scope on the operator's main clone, because git offers `--worktree` nowhere else, and it stays: clearing it would strip per-worktree config from every other worktree of that clone, not just this one. And `core.hooksPath` is never unset at the end, because for update and adopt a working hook surface is the outcome the flow was for.

What that key costs is that git stops reading `.git/hooks` entirely while it is set, so a hook the operator already had there silently stops firing. `pre-commit`'s shims chain only `<hooksdir>/hooks/<type>.legacy`, and `init-templatedir` into a fresh directory writes none, so in any tree that had its own hooks, link each of them in under that name before pinning the key. Generate's candidate is the one tree exempt: step 3 created it, so there is nothing there to chain.

Re-running the recipe is what a resume does, and it is not free here: `init-templatedir` installs with overwrite, which removes a `<type>.legacy` already sitting beside the shims. Re-link them after every run of it, not only the first.

Verify by outcome before measuring the bar, never by the commands' exit status: `git -C <tree> rev-parse --git-path hooks` resolves inside `<hooksdir>` and every configured type is present there. A flow whose hooks are not working stops here and reports it as its own defect. Carrying on measures a destination against a check surface that cannot run and writes the result up as debt the destination owes, which is the worst available outcome: a real repository given a list of failures that are this skill's.

A global `core.hooksPath` is reported with its key and its value, and it is not a stop. The recipe above works while it is set; naming it is what stops the next reader treating an unrelated editor integration as a defect. Removing and restoring the operator's global key around an install is not the shortcut it looks like: every other process on the machine reads the wrong config for the duration.

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
- merge: retrofit/<short-target> -> <default branch> (retrofit's second gate, offered once every required check polls green; declining is the default and leaves the pull request open)
```

Read the block as a menu rather than a sequence — no gate shows every line. Settings drift is raised by an update and an adopt and never by a generate, since a generate applies the settings it just listed and nothing has drifted from anything. A generate into a repository that already has content is still a generate here: it applies the merge settings rather than reporting them as drift, and states their current values on the gate, because it is the one flow that overwrites a hosted setting someone deliberately chose.

A generate reaches this twice, and the two gates authorize different things. The first, at [Generate](generate.md) step 4, covers every line through `issues` except settings drift: an empty repository, its settings, the probe that proves those settings bind, and the tracker writes steps 6 and 7 make against it — with no diff and no check result to show, because nothing has been built yet. Present them together even though steps 5 through 7 perform them later, since returning for a second authorization between each is noise; what the gate may not do is perform a remote write it did not list. The labels and issues lines carry their condition in their own text rather than being dropped, because which labels are missing and which tickets the map holds are not known until steps 6 and 7 run; a destination whose own tracker doc records local markdown makes neither write, and that authorization simply goes unused. The second, at step 11, covers the rest against a candidate that has been personalized, checked, and file-list reconciled. Show only the lines the gate is actually asking for. Presenting the whole block at step 4 takes authorization for a content push that does not exist yet.

Ask for confirmation unless the invocation already authorizes these exact actions against this exact repository. Authorization for repository creation does not imply settings changes or a later merge. Never merge as part of this skill, except two cases, each gated the same as every other remote action here: the bootstrap-generate case documented under [Generate](generate.md) step 12, and the offer a retrofit makes at its own second gate, under [Step 9 — Publish, prove, and offer the merge](retrofit.md#step-9--publish-prove-and-offer-the-merge). The retrofit case is an offer rather than a step, declined by default, and it is asked only there: a generate into a populated destination arguably owes the same one, and nothing has established that, so it is not asserted.

## A written ruleset is proved satisfiable, not merely present

A ruleset that exists, binds, and can never be satisfied reads as a success from every angle a flow otherwise looks: creation returned 201, the rule reads back `active`, `scripts/repo-settings check` passes it, and a probe pushed at the default branch is rejected exactly as it should be. What none of those asks is whether the rule just written will ever let anything merge. A required context nothing reports is the usual way in — see [Step 5 — Configure the repository settings](generate.md#step-5--configure-the-repository-settings) for how the spelling goes wrong — and its symptom is a pull request that is simply never mergeable, with nothing anywhere naming the cause.

The proof costs nothing and the flow is already holding it. Once the pull request's required checks have reported, read the two fields together:

```bash
gh pr view <n> --json mergeable,mergeStateStatus --jq '{mergeable,mergeStateStatus}'
```

`MERGEABLE` with `CLEAN` is the rule satisfied. `MERGEABLE` with `BLOCKED`, on an all-green pull request against a ruleset requiring no approving review, is the signature of a ruleset that is active and unsatisfiable: mergeable says no conflict, blocked says a rule is refusing, and with the checks green and no review owed there is nothing left for it to be refusing but a requirement nothing can meet. Report the pair verbatim rather than a verdict derived from it, and name the required contexts beside it, since the misspelling is what the operator has to fix.

Read it as **two** findings at once. It is the satisfiability proof, and it is also the enforcement evidence — `BLOCKED` on a green pull request is a rule binding, observed on a pull request the flow opened anyway rather than manufactured by pushing a throwaway commit at a branch other people fetch. A flow that has this read does not owe the existence check beside it: a ruleset that is refusing is a ruleset that is there.

## Failure and recovery

Stop before editing when:

- the manifest is absent, malformed, or records a non-full commit;
- the destination is dirty or origin differs from the manifest;
- either payload subtree is unavailable;
- the recorded commit is not an ancestor of the target;
- ownership is ambiguous.

The [Wayfinding](wayfinding.md) handoff is also a stop, and the one that is not a failure: nothing is wrong, the decomposition is simply not this skill's to settle. Report it as `stopped` like any other, but do not report it as a defect in the candidate or the request, and do not discard the materialized candidate — it is what the resumed session re-enters at. By this point the destination repository exists, configured, with its default branch still the empty root commit and its map on its tracker. That is the state to leave and to describe, not a half-finished generate to roll back; the repository is where the map lives, so deleting it discards the only thing the stop produced.

A stop is not an undo. There is no rollback here and none is being added: automated undo is rollback under another name, and a flow that half-reverses its own hosted writes leaves a state neither it nor the operator can describe. What a stop leaves is a state to resume from, and the rules for resuming are below.

Stop before further remote actions when semantic intent conflicts or verification fails. On a [generate](generate.md) that no longer means before any remote action at all: steps 4 and 5 have already created the repository and applied its settings, so a failure at any step from 5 to 10 leaves a real repository whose content was never published. Its default branch is the empty root commit, except after a failure at step 5 where the probe ran and was not rejected: its commit stays there. Name it, say what it already carries, and say whether resuming against it or deleting it is the next action — a stop reported as though nothing was created sends the user looking for a repository they already own. Keep `template.commit` at the previous version. Report exact paths, Git evidence, checks, and a recoverable next action. Do not approximate a missing old version, rebase unrelated template histories, reset/clean the destination, or claim a partial update succeeded.

### Resuming

**Re-invoking the same command is the resume.** There is no second command and no `--resume` flag: a flow that stopped is re-entered by running the invocation that stopped, against the same destination. A separate resume path is a second implementation of every step, kept in step with the first by nobody. This binds all four flows and both halves of each: a local write and a hosted one are re-entered the same way, by reading what is there rather than by replaying what a record says was done.

A resumed run **re-observes** rather than replays. Almost everything a flow does is readable back from live state at the moment the resume starts: the repository exists or it does not, the settings hold the values they hold, the branch is pushed or absent, the pull request is open, the candidate's files are on disk, the labels are on the repository. Read those and skip what is already done, rather than trusting a record of having done it — a record can be stale in a way the API cannot.

**The resume record holds only what cannot be observed back**, plus decisions the operator made that would otherwise be asked again. Issue creation is the case that forces it to exist: an issue has no natural key, so a second pass with nothing recorded creates a duplicate map and a duplicate ticket for every one it already created, and there is no query that distinguishes them afterwards. The record maps each thing the flow meant to create to what it became:

```json
{
  "invocation": "generate possiblyneal/example",
  "source_commit": "0123456789abcdef0123456789abcdef01234567",
  "issues": [
    {"intent": "map: converting a repository", "created": 104},
    {"intent": "ticket: name the destination", "created": 105}
  ],
  "decisions": [
    {"question": "merge settings overwritten", "answer": "declined"}
  ]
}
```

`source_commit` is in the record for the same reason, though it looks derivable. The invocation may have named a branch, and re-resolving that branch on the resume gives whatever it points at now, which is a different commit from the one already materialized as the candidate on disk. Read the record's commit and resolve nothing.

It is not a journal of everything the flow did. A record that grows a line per step is a second source of truth about state the API already answers, and the first time the two disagree the flow believes the wrong one.

**The record lives beside the candidate, never inside it** — a sibling of the candidate directory, not a file within the tree. Inside, it would enter the candidate diff, reach the copy proof as an authored path, and fail the structure audit as a root file nobody permitted, and each of those is a defect reported against a destination that did not cause it.

**Order the hosted writes so the unobservable ones come first**, wherever the ordering is free. Issues created before the content push means a run that dies at the push re-observes the push and reads the issues from its record; the reverse loses nothing but makes the record carry more. Where an ordering is not free — a repository must exist before its settings — leave it as it is.

**Retry is bounded and fires on transient classes only**: a network failure, an HTTP 5xx, a 403 or a 429 that is a rate limit. A 409 is not on the list: on a fresh destination it is the empty-repository answer, which is a state generate step 4 deliberately creates and no amount of waiting changes. Three attempts with exponential backoff, then stop and report. Nothing else retries — a 404, a 422, a permissions refusal, and a validation failure are all answers rather than noise, and repeating them turns one clear failure into three and a delay.

## Reviewing and reporting

Both belong to the end of a flow and both are in [`reporting.md`](reporting.md): [Reviewing the pull request](reporting.md#reviewing-the-pull-request), which is how a candidate is proved to be a copy rather than code-reviewed, and [Final report](reporting.md#final-report), the shape every flow ends in. Read that file when a flow reaches its review, not before — it is a third of this contract by size and none of it bears on anything earlier.
