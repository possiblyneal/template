# Repo Builder Lifecycle Contract

This file holds what is true regardless of operation: the manifest, ownership, how checks are run and reported, the remote gates, and failure behavior. Reviewing and reporting are in [`reporting.md`](reporting.md), read at the end of a flow. Read this file, then the one flow being performed.

- [`generate.md`](generate.md) — build a repository from the payload, including into a destination that already has content
- [`update.md`](update.md) — carry a bounded template delta into a repository already generated from it
- [`adopt.md`](adopt.md) — land a held-back repository addon whose condition has arrived

Two sub-contracts are read from inside a flow:

- [`wayfinding.md`](wayfinding.md) — derive the application boundaries, at [`generate.md`](generate.md) step 7
- [`addon-adoption.md`](addon-adoption.md) — finish an addon after copying it, at [`generate.md`](generate.md) step 2 and [`adopt.md`](adopt.md) step 4

[`choosing_a_language.md`](choosing_a_language.md) is the method wayfinding is a short path through.

Every `<placeholder>` in a command stands for a user-supplied value. Quote it when substituting (`git push origin "$branch"`), and reject a repository or branch name outside `[A-Za-z0-9._/-]+` before it reaches a shell; the guard is against stray metacharacters.

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

The `ownership` array illustrates the shape; do not copy it. Build a manifest's list from the payload's actual top-level structure at the resolved source commit (e.g. `git ls-tree -r --name-only <commit> -- <subtree>`), since real paths drift from prose. The example is still kept complete: `test_every_shipped_path_is_reached_by_an_ownership_rule` in `scripts/tests/test_reference_assertions.py` fails the commit on a payload path no rule here reaches.

Use a full lowercase 40-character commit. `template.commit` is the last template version successfully applied to the candidate. Change it only after the candidate passes verification, and commit it with the update it describes.

Record generation choices that change rendered files or repository settings. Do not record timestamps, a pending target commit, destination HEAD, or duplicate file contents.

Do not record what the filesystem or API already answers; a copy only goes stale. Language and package manager come from the manifests present (`libs/detect.sh`). Visibility is recorded by no flow: every decision that turns on it reads it from the API at that moment. `features` is the exception, because it records which absences were deliberate: an omitted `codeql.yml` and a dropped one look identical on disk.

`generation.applications` lists the deployable names [Wayfinding](wayfinding.md) established, and nothing else about them. It exists so an update can tell `apps/app-name` was renamed rather than deleted. Do not record each name's language (the manifests answer it) or choke point (an argument, so it belongs in the ADR). Leave a manifest still recording the earlier single `application_name` as it is; rewriting it would claim a decision the update did not make.

A retrofit writes the same field from the unit names the operator confirmed, and no field beside it. Run and ship facts belong to each unit's `.unit.json`, and their evidence to the architecture record. Names from a destination's own evidence and from wayfinding share the one field because an update asks the same rename-or-delete question of both.

## Ownership

Ownership answers whether a path participates in template updates:

- `managed`: inspect changes from the template, but reconcile them with destination intent. It never means blind overwrite.
- `product`: preserve automatically. If a new template path collides with product content, report the collision and stop.
- unmatched: product-owned by default.

The longest matching path wins; equal patterns are invalid. The old-to-new template delta bounds update scope. Do not edit an unrelated destination path merely because a broad ownership rule matches it. An expired override is the one write outside that bound, settled under [Overridden paths](#overridden-paths).

A root file matches no directory pattern, so `CLAUDE.md`, `.pre-commit-config.yaml`, `.commitlintrc.yaml`, `.gitattributes`, and `.gitignore` fall through to product unless named individually, and a payload fix to them would land nowhere while the update reports success. Every root file the payload adds needs a line. Every path the template ships needs an ownership rule that reaches it; verify with `classify_path` rather than assuming a directory pattern covers a root file. In this repository `test_reference_assertions.py` checks every payload path against both this repository's manifest and the example above.

Reaching a path is not managing it. `.env` is named and **product**: the payload ships an empty one so the file exists, and a destination's copy is the destination's. Naming it makes that a decision rather than the default an added payload path would inherit.

The root `CLAUDE.md` is managed and merged, not overwritten: the destination writes its own instructions into the same file, so an update reconciles the template's change with them and stops only where both say different things about the same rule.

A rename or delete of a destination-modified managed file needs semantic review. Product-created files under managed directories remain untouched unless the new template introduces the same path.

An adopted addon is one of those files. `CHANGELOG.md` matches no pattern and defaults to product; `.claude/rules/changelog.md` falls under the product-owned `.claude/rules/**`. Neither is a deletion to reconcile: the template never having shipped a path is not the template having removed it.

### Overridden paths

An **overridden path** is a managed payload path a flow did not land because the destination's own version was chosen over it; the answer stands for later updates. Every flow that resolves a collision records it in `generation.overrides`:

```json
"overrides": [
  {"path": "CLAUDE.md", "reason": "destination keeps its own instruction file"}
]
```

- One entry per path, with the reason the destination's version was chosen; without a reason the next update has nothing to weigh. `preflight.py` refuses a malformed record before a flow acts: a non-list, a non-object entry, a missing or empty `path` or `reason`, or two entries naming one path.
- **An entry is only ever about a managed path.** An entry on a product-owned path asserts nothing and drops the path from the product tally, so the delta summary under-reports. `preflight.py` refuses it, naming the path and the ownership rule that made it product-owned, resolving ownership as the delta does (unmatched included). A collision a product-owned destination file won is still reported by name with its reason under Reconciliation, with no entry recorded.
- **A path the flows replace outright can never be an entry.** `.gitignore` is the one: [retrofit's Step 6 — Reconcile the destination's layout](retrofit-step-6-layout.md#step-6--reconcile-the-destinations-layout) states the rule (the payload's version lands; a destination rule the payload does not cover is reported for the operator, not re-added), and [The payload's mode travels with the payload's content](#the-payloads-mode-travels-with-the-payloads-content) carries it to every other flow. `preflight.py` refuses such an entry by name at the next update or adopt, not at the retrofit that wrote it, so a retrofit must not write it. Otherwise every later payload change to the ignore file is silently skipped.
- An update skips a delta path listed here rather than reporting it as a conflict, so a settled collision is not re-raised. A delta renaming the path is still that path: match a rename under its source name as well as its destination one.
- **An entry expires with the thing it records.** Where the destination has deleted its own version, the update lands the payload's copy and drops the entry, in the same pull request. Expiry is read from the entries against the destination, not from the delta, so an expired entry may sit inside or outside the delta. `preflight.py update` settles both from the destination's tracked paths: a delta path whose entry the destination no longer holds is marked `override_expired` and applied as an ordinary managed change; every entry the delta does not reach is listed in `unmatched_overrides`, `expired` where the destination no longer holds the path and `unreached` where it does. Only expiry ends an entry.
- Adopt neither writes nor reads an entry; it resolves no collision. Generate, retrofit, and update are bound by this section.
- An overridden path was never written, so it is absent from the copy proof [Reviewing the pull request](reporting.md#reviewing-the-pull-request) runs and belongs to neither the copied set nor the authored surface. Name it as overridden in the report, with its reason.

### The payload's mode travels with the payload's content

Wherever a flow lands a payload path, the file ends at the mode the payload declares. `git archive` handles this for a path the destination lacks; rewriting an existing file in place keeps the destination's mode, so that case must be set explicitly. Example: `.gitignore` at `100755` in a destination and `100644` in the payload lands executable and fails `check-executables-have-shebangs` at the next commit with no visible cause.

Bound: the overlay of an absent path, a collision disposed to the payload, the ignore file and the automation directory replaced whole, and an update applying a managed delta. Set the mode from the payload at the resolved source commit — `git ls-tree <commit> -- <subtree>/<path>`, first field — not from the file on disk, the template clone's index, or its working tree, since a clone checked out elsewhere answers for a different payload.

## The automation directory is replaced, not reconciled

`.github/` is replaced whole (`workflows/`, `actions/`, `dependabot.yml`, `zizmor.yml`, `ISSUE_TEMPLATE/`, and `PULL_REQUEST_TEMPLATE.md`), and the destination's version does not survive the flow. It is a template guarantee, not a per-file collision: half-merged CI is a state no later update can reason about.

`dependabot.yml` is replaced like the rest and then gains the entries [Dependabot entries follow the manifests present](#dependabot-entries-follow-the-manifests-present) derives from the destination's manifests; the destination supplies evidence, not content. `codeql.yml` lands like any other path and decides per run, per [Code scanning lands everywhere and decides at run time](#code-scanning-lands-everywhere-and-decides-at-run-time).

The replacement is not declinable and has no `features` entry. A refusal is a refusal of the flow, not of one directory.

**The carve-out is exactly that path prefix.** Rule 4 of [Into a repository that already has content](generate.md#into-a-repository-that-already-has-content), never delete destination content to resolve a collision, still binds everywhere else. `docs/agents/` is decided per file under the collision rules, and a destination's `issue-tracker.md` still wins.

A destination's own `PULL_REQUEST_TEMPLATE.md` and `ISSUE_TEMPLATE/` go too, since they are inside the prefix. Name them in the report as a loss. Where the destination had its own `.github/PULL_REQUEST_TEMPLATE/` directory, [addon adoption](addon-adoption.md) offers the payload's `release.md` and `hotfix.md` back afterwards; say so in the same report line.

Superseded content is reported, never silently dropped. Name every superseded path with what it did, and record it in `generation.superseded` as `{path, did, by}`:

- `path` — the destination path that no longer exists.
- `did` — what it did, in the report reader's words, so a later reader can tell a duplicate of `ci.yml` from a deploy job nobody replaced.
- `by` — the payload path that now carries it, or the check that does.

An update reads this list before treating an absent destination path as a deletion to reconcile.

### Retiring a covered gate script

A destination's gate scripts are outside `.github/`, so they are not replaced, but they often duplicate the payload's `scripts/check` and its six per-language capabilities.

- **Fully covered** — everything the script does is a capability the payload's check surface already dispatches. Retire it: delete the script, repoint every caller at the payload command, and record it in `generation.superseded` with `"retired": true`. The behaviour survives under another name, which exempts it from rule 4. Report the callers by path with the retirement; a caller left on the old path is a broken retirement.
- **Partially covered** — the script does something the check surface does not (a deploy step, a repository-specific probe). It survives; report the overlap as a conflict naming the duplicated parts, and do not cut them here. That policy decision is escalated, not made.

## Code scanning lands everywhere and decides at run time

`codeql.yml` lands at every destination. Its `scanning` job calls `gh api "repos/<owner>/<repository>" --jq .visibility` on every run and, where the repository is not public, writes a warning annotation and run summary and skips `detect` and `analyze`; the run is green. The test is visibility alone, so a private destination with Advanced Security also stands down; the workflow's own comment states that limit and the fix.

So no flow branches on visibility here and none records it; a generation-time decision would go stale the day the repository goes public.

A destination that wants no scanning deletes `codeql.yml` itself and records `"codeql": "omitted-by-choice"` under `generation.features`, which tells a later flow the file was omitted rather than lost.

The value is exactly `omitted-by-choice` with no reason: `scripts/github-parity` selects on `.value == "omitted-by-choice"`, so a reason in the value silently un-excuses the omission. Put the reason in the report.

`scripts/github-parity` reads the record only in this repository, the one place it compares against a payload. In a generated repository it reports `not-applicable`.

## Dependabot entries follow the manifests present

`.github/dependabot.yml` is [replaced, not reconciled](#the-automation-directory-is-replaced-not-reconciled), and the payload's copy lists only `github-actions` and `pre-commit`. It cannot list language ecosystems ahead of their manifests: an entry naming a missing manifest fails the whole run with `dependency_file_not_found`.

So every flow that writes the file **derives the language entries from the manifests the destination actually holds** and appends them to the payload's two. The file's header documents the mapping for humans; it is not the mechanism.

**The list is re-derived every run, never preserved.** A hand-added entry does not survive an update (this repository's own `pip` entry says so). Rebuilding from disk is why this is not an [override](#overridden-paths), not one of update's four reconciliation rules, and not a per-destination exception. A manifest deleted since the last run loses its entry, which matters because a stale entry fails the run.

**One entry per manifest, at the manifest's own directory.** `directory` is the directory holding the manifest (`/apps/glydr`, not `/`), so an entry cannot be derived from the ecosystem name alone. Where one ecosystem has manifests in several directories, use the plural `directories` list, as the payload's `github-actions` entry does; repeating the ecosystem is accepted but splits its cooldown and group into two places that drift.

| Manifest | `package-ecosystem` |
|---|---|
| `package.json` | `npm` |
| `pyproject.toml` | `pip` |
| `go.mod` | `gomod` |
| `Cargo.toml` | `cargo` |
| `build.gradle.kts` | `gradle` |
| `Package.swift` | `swift` |

**A workspace file is not a manifest.** `go.work` and `settings.gradle.kts` are not what Dependabot reads. A destination with a root `go.work` and one `apps/<name>/go.mod` takes a single `gomod` entry at `/apps/<name>` and none at `/`. Whether an entry at `/` would also reach the module is Dependabot discovery behaviour that moves (`go.work` discovery: `dependabot/dependabot-core#14909`, 2026-05-05); derive from the manifests regardless, which stays correct because the set is rebuilt every run. **A cargo workspace is one manifest set, not one per member.** A root `Cargo.toml` holding `[workspace]` earns the single `cargo` entry at the workspace root, and a member listed in its `members` earns none, although both files are `Cargo.toml`. The root entry already bumps the members and moves the root `Cargo.lock`; a member entry opens a duplicate pull request, and where the member declares its own versions rather than `{ workspace = true }` that pull request carries no lockfile (`dependabot/dependabot-core#12766`). Revisit only when a member inherits a dependency with `{ workspace = true }`; until then, one entry at the workspace root.

`scripts/doctor` reports every such member as unwatched regardless, because `dependabot_unwatched_manifests` compares literal directories. It reports rather than fails, and is not a reason to add the entry; its advisory names the exception.

**Read the manifests from the tracked files, with `git ls-files`.** Not from `has_<lang>` in `scripts/libs/detect.sh`, which answers only whether a *root* manifest exists, and not from a working-tree search pruned by `DETECT_PRUNE_DIRS` (`.git node_modules .build target .venv venv vendor tmp`), which does not prune `.claude/worktrees/` and here returns two `pyproject.toml` not in the repository. Dependabot reads the pushed tree, so the tracked set is the right answer. Exclude the payload under `apps/github-repository-template/src/base-repo/`: an entry derived from it would name a path no destination has.

**A destination that tracks a copy of the payload earns a second `pre-commit` directory.** `template.subtree` names where a payload sits. Where the destination tracks a `.pre-commit-config.yaml` at that path inside itself, the `pre-commit` entry names that directory alongside `/`, and its group takes `group-by: dependency-name`. Add the key only with the second directory; a destination without one keeps the payload's group. The key is required: without it Dependabot splits the group by directory and opens one pull request per copy, which leaves later generated repositories on older hook revisions (`scripts/github-parity` compares only the two `.github/` trees). Derive it from the tracked path, not a `generation` flag, so it is rebuilt each run and disappears when the payload copy does.

That is not an exception to the exclusion above: the exclusion stops *language* entries from payload manifests; this names the directory of a file the destination itself pins and is failed by.

**An ecosystem outside the table is not derived, and not silently dropped either.** A destination may hold an entry for `docker`, `terraform`, `nuget`, `bundler`, or another the table does not cover, and replacing the file would delete it. So read the destination's copy before replacing it and report every uncovered `package-ecosystem` by name on the flow's own gate; reinstating it is the destination's to authorize.

The table points the other way too. A tracked manifest whose filename it does not list — a Groovy `build.gradle`, a `requirements.txt` or `setup.py` — earns no entry. Do not widen the table: the six match the template's language vocabulary and `scripts/libs/detect.sh`. Report it on the same gate, by path, as a manifest Dependabot is not watching and why, for a person to decide whether the repository should carry that shape.

**A derived entry carries the policy the payload's own entries carry** — `interval: weekly`, `cooldown.default-days: 7`, and one group matching `*` named for the ecosystem — so only its origin differs from a shipped one.

**The file's own check run is not required, is usually absent, and green does not mean the entries are right.** GitHub sometimes posts a check named for `.github/dependabot.yml` on the commit whose push changed the file, so it is often missing from a pull request's rollup (a later head commit, or a byte-identical re-derived file), and is unreliable even on a changing commit (on `possiblyneal/template`, `57152c8` carried it; `148b113` did not). Never add it to the required set a flow polls; waiting for a check GitHub never posts waits forever. Where present it is only a schema check: it never opens the entries' directories, and `dependency_file_not_found` surfaces days later against a green check.

So verify by parsing the file that was written — one entry per tracked manifest, each `directory` one that manifest is actually in — and report that parse as the evidence, naming the check run's result only where one was posted. Do not report a green check as evidence the entries work.

The rule binds [generate](generate.md), [update](update.md), and retrofit. [Adopt](adopt.md) writes no `.github/` path.

## Architecture records live at the root documentation path

Every architecture record the payload governs sits in `docs/adrs/` at the repository root, in every flow, whatever its scope. A record about one unit says so in its `scope` frontmatter field; `apps/<name>/docs/adrs/` is never where one goes.

`scripts/adr-index` hardcodes the directory it indexes, and `scripts/structure` accepts Markdown anywhere under `docs/`, so a misplaced record is silently missing from the index. Whether the audit should enforce the location is a question for the audit, not these flows.

The rule binds [generate](generate.md), [update](update.md), [adopt](adopt.md), and retrofit. It lives here, not in retrofit (the only flow that meets records written elsewhere), so it reads as repository-wide placement.

## Running the destination's checks

Every flow runs the candidate's or the destination's own documented checks before it publishes anything, under three rules.

Stage the work first. `pre-commit run --all-files` enumerates through the Git index, so unstaged work is checked as the empty set and passes. The repository's `scripts/check` sweeps untracked files by path afterwards only if its payload carries that second pass; verify rather than assume.

Read the run through the repository's own `scripts/summarize` (`scripts/summarize scripts/check`), which prints only the Result table. Do not hand-build a filter: `grep -iE "FAIL|error"` misses `unavailable`, which is equally failing. `scripts/summarize` exits with the command's status, and when a failing exit came from outside the table it writes the whole run to `tmp/summarize-failure.log` and names it. Read that log rather than re-running: the commonest cause is a pre-commit fixer hook that repaired a file and exited non-zero, so a second run passes. Read raw output only where the payload is too old to ship `scripts/summarize`; check before assuming.

Report each check by what it did, keeping four outcomes distinct: passed, nothing to do, runner missing, never ran. Report skipped or unavailable as such, never as a pass. A run reporting no project manifest checked nothing; a green pull request with no workflow runs verified nothing; an unwritten file cannot fail. A tool a script reports unavailable on `PATH` may still pass inside pre-commit's pinned environment in the same run; report what each surface actually did, and that tool as run, not skipped.

### Tools the first manifest must declare

The check surface dispatches per language, reads no record, and holds no exemption list beyond the template-wide one it ships, so a manifest field cannot silence a check. A manifest that does not declare the tool an adapter reaches for produces `NO_RUNNER`, reported `unavailable` and failed like a real failure. The first real commit brings the root manifest and owes these declarations. Name them in the flow's handover, per language, including the empty ones:

- **python** — `ruff`, `ty`, and `pytest`, as dependencies in `pyproject.toml`, since each runs through `uv run`. The file also carries a `tool.ruff` table, empty unless the repository wants settings; ruff ignores a `pyproject.toml` without one and keeps walking upward past the repository. Any subtable (`[tool.ruff.lint]`, `[tool.ruff.format]`) creates it, so no bare header is then needed.
- **node** — six `package.json` scripts rather than tools: `lint`, `format:check`, `typecheck`, `test`, `build`, `format`. The adapter checks the script name, not what it invokes.
- **kotlin** — a `ktlint` or `detekt` Gradle plugin in the build file, for lint and formatting. `test` and `build` need only the wrapper.
- **go** — none. `go vet`, `gofmt`, `go test`, and `go build` ship with the toolchain.
- **rust** — none. `cargo clippy`, `cargo fmt`, `cargo test`, and `cargo build` come from the toolchain and its rustup components.
- **swift** — none. `swift format`, `swift test`, and `swift build` are the compiler's own subcommands.

The empty three are stated so they do not read as an oversight.

The adapters under `scripts/libs/` are the source of truth and nothing checks this list against them; it is kept because its reader has no repository to read the adapters in yet. Read the adapter for the language before trusting a name, and correct this list when the two disagree.

The security scanners and toolchain probes are `PATH` lookups, so declaring them in a manifest does nothing: `govulncheck`, `cargo-audit`, `trivy`, `gitleaks`, `uv` itself, and `npm`/`pnpm`/`yarn`. Absent, they report `unavailable`.

An update owes nothing here; the root manifest is product-owned and never enters an update's delta.

### Working hooks in a candidate

The check surface's first gate fails when the hooks git will consult are missing, so every flow installs them first, by this recipe.

A machine-wide `core.hooksPath` makes `pre-commit install` refuse, and breaks it again inside throwaway fixture repositories the repository's tests create, since fixtures inherit global config. Check `git config --global core.hooksPath` before treating either failure as a repository defect; a control run against the template repository's current HEAD reproduces the same failure when this is the cause.

Never unset the operator's key. A fixture is fixed by isolation, which `scripts/tests/libs/harness.sh` already applies. A working tree is fixed with `pre-commit init-templatedir`, which does not refuse while `core.hooksPath` is set at any scope and writes repository-independent shims:

```sh
# --worktree only, and before the rest: the scope is refused without it.
# <clone> is the main clone the candidate worktree belongs to, because git
# offers the key nowhere else. Every other line below acts on <tree>, the
# candidate itself.
git -C <clone> config extensions.worktreeConfig true

pre-commit init-templatedir -t <each configured type> <hooksdir>

# Any hook the tree already had, chained under the shim. init-templatedir
# installs with overwrite, so re-link after every run of it -- including the
# re-runs a resume makes, not only the first. Generate's candidate has none:
# step 3 created it.
ln -sf <existing hook> "<hooksdir>/hooks/<type>.legacy"

git -C <tree> config <scope> core.hooksPath "<hooksdir>/hooks"

# Verify by outcome, never by the exit statuses above: this must resolve
# inside <hooksdir>, and every configured type must be present there.
git -C <tree> rev-parse --git-path hooks
```

`<hooksdir>` is a sibling of the tree in the scratch tree, beside the resume record, for the reason [Resuming](#resuming) gives: inside the tree it would enter the diff, the copy proof, and the structure audit.

Read the hook types from `pre_commit_hook_types` in `scripts/libs/precommit.sh`, against the tree's own `.pre-commit-config.yaml`. `pre_commit_hooks_missing` grades against the same helper, so setup and check agree; a hand-written list breaks when `default_install_hook_types` changes.

`<scope>` varies by flow:

- **Retrofit** — `--worktree`. Its candidate is a linked worktree, so local scope is the main clone's config and would repoint the operator's own clone.
- **Generate** — `--local`. The candidate is a dedicated clone.
- **Update and adopt** — `--local`. They run in the operator's own clone, where installed hooks are the intended outcome.

Setting the key changes a tree somebody else owns in every flow but generate, and two changes outlive the flow; report both by name. `extensions.worktreeConfig` stays set at local scope on the operator's main clone, since clearing it strips per-worktree config from every other worktree. `core.hooksPath` is never unset at the end, since for update and adopt a working hook surface is the outcome.

While the key is set git stops reading `.git/hooks`, so an existing hook there silently stops firing. The shims chain only `<hooksdir>/hooks/<type>.legacy`, and a fresh `init-templatedir` writes none, so in any tree that had its own hooks, link each in under that name before pinning the key. Generate's candidate is exempt: step 3 created it.

Run the verify line before the bar is measured. A flow whose hooks are not working stops there and reports it as its own defect; carrying on would hand a destination this skill's failures as debt.

Report a global `core.hooksPath` with its key and value; it is not a stop. Do not remove and restore the operator's global key around an install: every other process on the machine reads the wrong config meanwhile.

### Working hooks in the destination after a merge

For retrofit the candidate and the operator's clone differ: its key is set at `--worktree` scope on a candidate removed at the flow's end, so the hooks go with it.

**A retrofit merges a `.pre-commit-config.yaml` into a clone that did not have one**, with an instruction file promising linted, attributed commits refused on the default branch. Nothing else installs it, which would leave a promised hook surface that does not exist.

So where the operator takes the merge at retrofit's second gate, install the hooks in the destination clone before the final report, and report the result in it. Declining the merge installs nothing: the recipe moves aside existing hooks and pins `core.hooksPath` at local scope, durable changes not worth making for a config that never landed.

The recipe is [Working hooks in a candidate](#working-hooks-in-a-candidate)'s, with `<hooksdir>` the clone's own `.git` and `<scope>` `--local`, and the retrofit helper runs it:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py hooks \
  --clone <path-to-destination-clone> \
  --default-branch <default-branch> \
  --scratch <absolute path to this repository>/tmp/<repository-name>-hooks \
  --resume-record <resume record> \
  --records <records>
```

It fetches the default branch and refuses, exiting 2, where that branch carries no `.pre-commit-config.yaml` (the merge has not landed). Otherwise it prints:

- `hook_types` — read through the branch's own `pre_commit_hook_types`.
- `hooks_path` — the shims' directory, now `core.hooksPath` at local scope.
- `prior_hooks` — the directory git ran the clone's hooks from before the pin, with `scope`: the scope that set `core.hooksPath`, as `git config --show-scope` names it, or `default` for the clone's own `.git/hooks`. Read once and kept in the resume record, because after the pin a later run would read the shims' directory back.
- `moved_aside` — each hook in `.git/hooks` the pin would otherwise change, with where it was and where it is now: `<type>.legacy`, chained, where git was running it, or `<name>.dormant` where git was not.
- `chained` — each hook in a prior directory other than `.git/hooks`, `linked` with the path it was linked as, or `duplicate`.
- `checks` — the three outcome checks below, each `true` where the hooks did what the destination's documentation promises.
- `worktree_removed` and `findings` — a refusal anywhere, including a throwaway worktree git would not remove, is a finding and nothing is forced.

What differs from the candidate's version:

- **The hooks directory is the clone's own `.git/hooks`, not a sibling in the scratch tree**, because it outlives the flow. Pin the key to it absolutely, because a relative value resolves per worktree and the clone has more than one.
- **The clone is not on the merged branch**, and need not be. `init-templatedir` writes repository-independent shims and reads no config, and the shims resolve `--config=.pre-commit-config.yaml` relative to whichever tree invokes them.
- **Branches in flight predate the config.** `init-templatedir` allows a missing config by default (`Skipping pre-commit`, exit zero), so those branches pass untouched. Do not pass `--no-allow-missing-config`.

Writing into `.git/hooks` is the one place this recipe can destroy something: `init-templatedir` installs with overwrite and deletes `<type>.legacy`, so moving a hook to `.legacy` before installing loses it. The helper holds each one under another name across the install and puts it at `<type>.legacy` afterwards. That applies only where `.git/hooks` is what git was running. Where a local or global `core.hooksPath` pointed elsewhere, each hook there is linked in instead unless it duplicates the payload's, and hooks in `.git/hooks` (which git was not running) are renamed `<name>.dormant`. Chain what git was running, and nothing it was not. A message hook is a duplicate when it rewrites a probe message exactly as the payload's stage does; any other is linked, since a redundant run is cheaper than a lost check.

The checks verify by outcome in a throwaway worktree the helper removes: a commit on the default branch is refused, a malformed subject fails commitlint, and a `Co-Authored-By` trailer comes back rewritten. The test file goes under `docs/`, since the structure audit refuses an unpermitted root file, and the default branch is stood in for by a per-worktree ref of the same name, so a hook that failed to refuse advances only that ref.

## The runner variable is set only where it is safe and answerable

`docs/adrs/0004-select-the-runner-through-a-repository-variable.md` gives every shipped workflow `runs-on: ${{ vars.RUNNER || 'ubuntu-latest' }}`. A flow may offer to set that variable only when both hold:

- **The repository is private.** A self-hosted runner on a public repository lets any fork's pull request run code on the host. Read visibility with `gh repo view <owner>/<repository> --json visibility`; on `PUBLIC`, do not offer the write at all, not even as a gate question.
- **A runner is online for it.** `gh api repos/<owner>/<repository>/actions/runners --jq '.runners[] | select(.name == "dev-<repository>") | .status'` must read `online`. Without one every job queues silently until `timeout-minutes`. Registering the runner belongs to the host's owner, not this skill.

Both true: an ordinary gate line and `gh variable set RUNNER --body self-hosted -R <owner>/<repository>`. Either false: report which one and offer nothing.

A repository that sets it owes one green run of every workflow before the variable is trusted, proved by `runner_name` on the jobs, since a job that fell back to `ubuntu-latest` is also green.

```bash
gh run list -R <owner>/<repository> --limit 5 --json name,conclusion,databaseId
gh api repos/<owner>/<repository>/actions/runs/<id>/jobs --jq '.jobs[] | {name, runner_name, conclusion}'
```

A Swift CodeQL job naming a hosted macOS runner is correct, for the reason the ADR gives.

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
- variable: `RUNNER=self-hosted`, offered only on a private destination whose `dev-<repository>` runner reads online, per [The runner variable is set only where it is safe and answerable](#the-runner-variable-is-set-only-where-it-is-safe-and-answerable) — authorized on its own line, never folded into the settings one
- push: repo-builder/<short-target> -> generated content or template update
- open PR: repo-builder/<short-target> -> main
- merge: repo-builder/<short-target> -> main (bootstrap generate only, see Generate step 12)
- merge: retrofit/<short-target> -> <default branch> (retrofit's second gate, offered once every required check polls green; declining is the default and leaves the pull request open)
- push: retrofit/fix-<short-target> -> origin (retrofit's unmet bar only, per [`retrofit-unmet-bar.md`](retrofit-unmet-bar.md); the destination's own debt, prepared and verified)
- open PR: retrofit/fix-<short-target> -> <default branch> (base, not target; same gate as the push above, and the only remote write a stopped retrofit makes)
- merge: retrofit/fix-<short-target> -> <default branch> (no gate of its own; [`retrofit-unmet-bar.md`](retrofit-unmet-bar.md) holds the conditions)
```

The block is a menu, not a sequence; show only the lines a gate is actually asking for. Settings drift is raised by update and adopt, never by generate. A generate into a repository that already has content applies the merge settings rather than reporting drift, and states their current values on the gate, since it overwrites hosted settings someone chose.

A generate reaches this twice. The first gate, at [Generate](generate.md) step 4, covers every line through `issues` except settings drift: the empty repository, its settings, the probe, and the tracker writes of steps 6 and 7, shown together although steps 5 through 7 perform them, with no diff or check result. The labels and issues lines keep their conditions in their text, since what is missing is not known until steps 6 and 7 run; a destination whose tracker doc records local markdown makes neither write. The gate may not perform a remote write it did not list. The second gate, at step 11, covers the rest against a personalized, checked, file-list-reconciled candidate. Do not show the whole block at step 4; that authorizes a content push that does not exist yet.

Ask for confirmation unless the invocation already authorizes these exact actions against this exact repository. Authorization for repository creation does not imply settings changes or a later merge. Never merge as part of this skill, except: the bootstrap generate under [Generate](generate.md) step 12; the offer at retrofit's second gate under [Step 9 — Publish, prove, and offer the merge](retrofit-step-9-publish.md#step-9--publish-prove-and-offer-the-merge), each gated like every other remote action; and an unmet bar's fix pull request, on the operator's standing authorization, under the conditions in [`retrofit-unmet-bar.md`](retrofit-unmet-bar.md). The retrofit merge is an offer, declined by default, and asked only there; whether a generate into a populated destination owes the same offer is unestablished, so it is not offered.

## A written ruleset is proved satisfiable, not merely present

A ruleset can exist, read back `active`, pass `scripts/repo-settings check`, reject the probe, and still never let anything merge. A required context nothing reports is the usual cause — see [Step 5 — Configure the repository settings](generate.md#step-5--configure-the-repository-settings) — and the pull request simply never becomes mergeable.

Once the pull request's required checks have reported, read:

```bash
gh pr view <n> --json mergeable,mergeStateStatus --jq '{mergeable,mergeStateStatus}'
```

`MERGEABLE` with `CLEAN` is the rule satisfied. `MERGEABLE` with `BLOCKED`, on an all-green pull request against a ruleset requiring no approving review, is an active, unsatisfiable ruleset. Report the pair verbatim rather than a derived verdict, and name the required contexts beside it, since a misspelling is what the operator must fix.

The read is **two** findings: the satisfiability proof, and enforcement evidence (`BLOCKED` on a green pull request is the rule binding), observed on the pull request the flow opened anyway; never push a throwaway commit at a shared branch to manufacture it. A flow holding this read does not also owe the existence check.

## Failure and recovery

Stop before editing when:

- the manifest is absent, malformed, or records a non-full commit;
- the destination is dirty or origin differs from the manifest;
- either payload subtree is unavailable;
- the recorded commit is not an ancestor of the target;
- ownership is ambiguous.

The [Wayfinding](wayfinding.md) handoff is also a stop, and not a failure. Report it as `stopped`, not as a defect in the candidate or the request, and do not discard the materialized candidate; the resumed session re-enters at it. The destination repository then exists, configured, with its default branch still the empty root commit and its map on its tracker. Leave and describe that state; do not roll it back or delete the repository, which holds the map.

A stop is not an undo. There is no rollback and none is to be added; a half-reversed set of hosted writes is a state nobody can describe. A stop leaves a state to resume from, per [Resuming](#resuming).

Stop before further remote actions when semantic intent conflicts or verification fails. On a [generate](generate.md), steps 4 and 5 have already created the repository and applied its settings, so a failure at any step from 5 to 10 leaves a real repository with no published content. Its default branch is the empty root commit, except after a failure at step 5 where the probe ran and was not rejected: its commit stays there. Name the repository, say what it carries, and say whether resuming against it or deleting it is the next action. Keep `template.commit` at the previous version. Report exact paths, Git evidence, checks, and a recoverable next action. Do not approximate a missing old version, rebase unrelated template histories, reset/clean the destination, or claim a partial update succeeded.

### Resuming

**Re-invoking the same command is the resume.** There is no second command and no `--resume` flag; a separate path would duplicate every step. This binds all four flows, local and hosted writes alike.

A resumed run **re-observes** rather than replays. Read live state — the repository exists or not, settings values, the branch pushed or absent, the pull request open, the candidate's files on disk, the labels present — and skip what is done, rather than trusting a record that may be stale.

**The resume record holds only what cannot be observed back**, plus operator decisions that would otherwise be asked again. Issues force it to exist: an issue has no natural key, so a second pass without a record duplicates the map and every ticket. The record maps each intended creation to what it became:

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

`source_commit` is recorded because a named branch may have moved since the candidate was materialized. Read the record's commit and resolve nothing.

A retrofit's post-merge hooks also record `prior_hooks`, the directory git ran the destination clone's hooks from before [Working hooks in the destination after a merge](#working-hooks-in-the-destination-after-a-merge) pinned `core.hooksPath`, because the pin overwrites the only live answer.

A retrofit's hosted writes lose their before-state once they land, so a resumed run reads it from the write log `retrofit.py hosted apply` keeps, under [Step 8 — The hosted-write gate](retrofit-step-8-hosted-writes.md#step-8--the-hosted-write-gate), and `apply` reports a write already in the log as `logged` rather than performing it again.

Do not journal every step; a record duplicating state the API answers will eventually be believed over it.

**The record lives beside the candidate, never inside it** — a sibling of the candidate directory. Inside, it would enter the candidate diff, the copy proof, and the structure audit as defects the destination did not cause.

**Order the hosted writes so the unobservable ones come first**, wherever the ordering is free (e.g. issues before the content push). Where it is not free — a repository must exist before its settings — leave it.

**Retry is bounded and fires on transient classes only**: a network failure, an HTTP 5xx, a 403 or a 429 that is a rate limit. Not a 409: on a fresh destination it is the empty-repository answer generate step 4 creates. Three attempts with exponential backoff, then stop and report. Nothing else retries; a 404, a 422, a permissions refusal, and a validation failure are answers.

## Reviewing and reporting

Both are in [`reporting.md`](reporting.md): [Reviewing the pull request](reporting.md#reviewing-the-pull-request), how a candidate is proved a copy rather than code-reviewed, and [Final report](reporting.md#final-report), the shape every flow ends in. Read it when a flow reaches its review, not before. Lines only a generate or a retrofit fills are in those flows' own files.
