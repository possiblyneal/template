# Repo Builder Lifecycle Contract

This file holds what is true regardless of operation: the manifest, ownership, how checks are run and reported, the remote gates, failure behavior, and the report shape. Read it, then read the one flow being performed.

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
    "visibility": "private",
    "features": {
      "codeql": "omitted-by-choice"
    }
  },
  "ownership": [
    {"path": ".repo-template.json", "mode": "managed"},
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

Do not record what the filesystem already answers. Language and package manager are read from the manifests present, so a recorded copy is a second source of truth that only goes stale — `libs/detect.sh` answers the question at any moment and a manifest added later never updates a field. `visibility` is recorded despite being live-readable because it is an argument to repository creation, and `features` because it records which absences were deliberate: an omitted `codeql.yml` and a dropped one look identical on disk.

`generation.applications` lists the deployable names [Wayfinding](wayfinding.md) established, and nothing else about them. It is recorded because an update has to know that `apps/app-name` was renamed rather than deleted, which the destination tree can no longer say. The choke point and the language behind each name are not recorded here: the language is answered by the manifests present under the rule above, and the choke point is an argument rather than a fact, so it belongs in the ADR that makes it. A manifest still recording the earlier single `application_name` is left as it is — it records what that generation chose, and an update rewriting it would claim a decision the update did not make.

## Ownership

Ownership answers whether a path participates in template updates:

- `managed`: inspect changes from the template, but reconcile them with destination intent. It never means blind overwrite.
- `product`: preserve automatically. If a new template path collides with product content, report the collision and stop.
- unmatched: product-owned by default.

The longest matching path wins; equal patterns are invalid. The old-to-new template delta bounds update scope. Do not edit an unrelated destination path merely because a broad ownership rule matches it.

Unmatched defaulting to product is the safe direction for a path the template does not ship, and the wrong one for a path it does. A file at the repository root matches no directory pattern, so `.pre-commit-config.yaml`, `.commitlintrc.yaml`, `.gitattributes`, and `.gitignore` fall through to product unless named individually — and those files carry the pinned hook revisions behind the secret scanner, the commit-message rules, and the merge policy keeping a lockfile from being line-merged. The list grows: every root file the payload adds needs a line here, or a payload fix to it lands nowhere while the update reports success. Every path the template ships needs an ownership rule that reaches it; verify with `classify_path` rather than assuming a directory pattern covers a file at the root.

A rename or delete of a destination-modified managed file needs semantic review. Product-created files under managed directories remain untouched unless the new template introduces the same path.

An adopted addon is one of those files. `CHANGELOG.md` matches no pattern and defaults to product; `.claude/rules/changelog.md` falls under the product-owned `.claude/rules/**`. Neither is a deletion to reconcile. The template never having shipped a path is not the template having removed it, and an update that reads it that way deletes a record the destination chose to keep.

## Running the destination's checks

Every flow runs the candidate's or the destination's own documented checks before it publishes anything. Three rules hold across all of them.

Stage the work first. A bare `pre-commit run --all-files` enumerates through the Git index, so unstaged work is checked as the empty set and reports a pass over nothing. The repository's own `scripts/check` sweeps untracked files by path after that command, but only if the payload it was built from carries that second pass — verify rather than assume it.

Report a check by what it did, and keep the four outcomes distinct: a check that passed, one that reported nothing to do, one whose runner was missing, and one that never ran. Report a skipped or unavailable check as skipped or unavailable; do not call it a pass. The repository's own scripts make that distinction, and collapsing it in the report discards the thing they were built to preserve. A run reporting no project manifest checked nothing; a green pull request with no workflow runs verified nothing; a file that was never written cannot fail. Tools a script looks up on `PATH` may also run inside pre-commit's pinned environments, so a tool reported unavailable by a script and passing under pre-commit in the same run was not skipped; report what each surface actually did.

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
- labels: created by step 6 — the roles `docs/agents/triage-labels.md` records plus `wayfinder:map`, and only those the repository does not already carry
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

## Reviewing the pull request

A pull request this skill opens is not code-reviewed. Almost all of it is the payload at the target commit, copied byte for byte, and that content was reviewed in the template repository before it merged there; reviewing it again in every generated repository re-reviews the same lines once per destination and reports the template's own judgments as findings against a repository that did not make them. Where a hook or a reviewer asks for a review of this pull request, this section is the answer to give, and the final report says the review was skipped so that a green result is not read as a review that passed.

What replaces it is the check the copies actually need, which no reviewer was doing anyway: prove they are copies. Each flow runs it before its publish gate, because a check that runs once the pull request is open can no longer stop anything.

For every path in the candidate diff, compare the candidate blob against the blob it was copied from and collect the paths that differ:

```bash
for path in $(git -C <destination> diff --name-only --diff-filter=d <base>...HEAD); do
  git -C <template> cat-file -p <commit>:<prefix>/"$path" 2> /dev/null |
    diff -q - <destination>/"$path" > /dev/null || echo "$path"
done
```

`<commit>` and `<prefix>` are each flow's own. Generate and update read the payload subtree at the target commit; adopt reads `repository-addons/` at the recorded commit, which is a sibling of the subtree rather than inside it. Where the template renamed a file its two names are two paths, so read the destination path against the payload's new one. A path `cat-file` cannot find was never a copy, and belongs to the authored surface instead.

What matches is the template's, already reviewed, and closed. What is left is the authored surface, short enough to read line by line. Read it that way, because it is where this skill's own mistakes land: a merge that keeps both intents can still leave a document asserting something the merge just made false, and a file the payload deletes can leave a live reference behind in destination-owned prose that no check reads. Grep the destination for every path the flow deletes or renames before calling the candidate verified.

Which files make up that surface differs by flow:

- **Update** — every managed file the destination had also changed and this skill hand-merged, plus `.repo-template.json`.
- **Generate** — everything step 8 personalized: the root `CLAUDE.md` Child Index, each `apps/<name>/` and its `.unit.json`, the ADRs, and `.repo-template.json`. This surface is larger than update's and it gets no second look, because a bootstrap generate merges its own pull request under [Generate](generate.md) step 12. Read it before that merge rather than after.
- **Adopt** — every region `addon-adoption.json` names for the addons taken. Here differing paths are the expected result rather than the exception: an addon is adopted by editing it, so byte-identity would mean the adoption never happened. Confirm that what differs is the named regions and nothing besides.

Report the authored surface in **File list**, so the reader sees which lines were the template's and which were this run's.

## Final report

Use this stable shape. On a generate the Reconciliation lines are empty or trivially everything, and File list carries the weight — it is the only section reporting a file the payload ships and the candidate lacks, which no check can fail on. On an adopt the Template line shows the recorded commit on both sides because the pin does not move, and the Addon adoption block carries the weight. On a generate stopped at the wayfinding handoff there are no Application boundaries to report — that absence is the result; the Wayfinding line names the trigger and the map, Repository settings still reports the repository that exists, and Pending action carries the resume.

```md
## Repo Builder Result

- Operation: generate | update | adopt | stopped
- Pull request: <URL or "not created">
- Template: <old full commit, or "not previously generated"> -> <target full commit>
- Destination: <owner/repository>

### Reconciliation
- Applied: <paths or none>
- Preserved: <paths or none>
- Renamed/deleted: <paths or none>
- Conflicted: <paths and competing intents, or none>

### Application boundaries
- <deployable>: choke point <constraint, or "none bound; time-to-working-code"> -> <language>, <selected from list | reasoned from the seam contract | measured against it>
- Wayfinding: short form settled it | handed off to `/wayfinder` (<which trigger>), map at <URL or path> | skipped, supplied in the invocation
- ADRs written: <paths, or none>

### File list
- <payload paths accounted for, and every difference named as intended or as a defect>
- Authored surface: <paths whose candidate blob differs from the blob it was copied from, or none>

### Addon adoption
- <addon taken>: <slot token, review section, or external step>: filled | reviewed | done | OUTSTANDING (<what remains>)
- <addons offered and not taken, on one line>

### Repository settings
- <setting>: enabled | unavailable (<reason>) | not requested
- Drift (update and adopt): <setting>: <current> -> <proposed>: patched | declined by user | none found | not checked (<reason>)
- Merge settings overwritten (generate into existing content only): <setting>: <prior value> -> <applied value> | declined by user, recorded in `generation.features`
- Issue tracker: <GitHub | GitLab | local markdown | other>, recorded in `docs/agents/issue-tracker.md`, shipped by the payload | written by `/setup-matt-pocock-skills` | kept from the destination; triage labels: created (<names>) | already present | none created (<reason>)

### Verification
- `<exact command>`: pass | fail | unavailable (<reason>)
- Copied paths byte-identical to their source: <count>/<count>; the rest are the authored surface, under File list
- Code review: skipped, as [Reviewing the pull request](#reviewing-the-pull-request) directs
- Default branch after merge: <check-suite result> | n/a (nothing merged)

### Pending action
<none, or the exact decision/authorization needed>
```
