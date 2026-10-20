# Update

Rules from [`lifecycle.md`](lifecycle.md) that every update needs, stated here so the file is never opened whole; a rule only some updates need sits at the step whose output triggers it. Each links to its section for the reasoning; read that section only when the statement here is not enough.

- **Placeholders.** Quote every `<placeholder>` when substituting, and reject a repository or branch name outside `[A-Za-z0-9._/-]+` before it reaches a shell.
- **Manifest** ([`## Manifest`](lifecycle.md#manifest)). `template.commit` is the last template version applied; change it only after the candidate passes verification, in the same pull request. Record no timestamp, pending target, destination HEAD, or file contents. `features` records every departure from the defaults, `generation.applications` lets an update tell a rename from a delete, and an old `application_name` is left as it is.
- **Ownership** ([`## Ownership`](lifecycle.md#ownership)). `managed` paths are reconciled with the destination's intent, never overwritten blind; `product` paths are preserved, and a payload path colliding with product content is reported and stops the run. Unmatched is product; the longest matching rule wins; a root file is owned only where named individually. Only the old-to-new delta is in scope. The root `CLAUDE.md` is managed and `merged`, not overwritten, and a payload path the template never shipped (an adopted addon) is not a deletion.
- **The ignore file** ([`### The ignore file keeps the destination's rules`](lifecycle.md#the-ignore-file-keeps-the-destinations-rules)). `.gitignore` takes the four rules like any managed path; a destination-only rule survives.
- **The automation directory** ([`## The automation directory is replaced, not reconciled`](lifecycle.md#the-automation-directory-is-replaced-not-reconciled)). `.github/` takes the payload's version whole and is not declinable; name a lost destination `PULL_REQUEST_TEMPLATE.md` or `ISSUE_TEMPLATE/` in the report.
- **Modes** ([`### The payload's mode travels with the payload's content`](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content)). A payload path written over an existing file ends at the payload's mode, read from `git ls-tree <commit> -- <subtree>/<path>`; update.py apply does this for what it lands, and a path reconciled by hand needs it set explicitly.
- **Dependabot** ([`## Dependabot entries follow the manifests present`](lifecycle.md#dependabot-entries-follow-the-manifests-present)). `dependabot.yml` is replaced and its language entries re-derived from the destination's tracked manifests, never preserved; step 3's apply does both and reports the parse of the written file.
- **Checks** ([`## Running the destination's checks`](lifecycle.md#running-the-destinations-checks)). Stage first, run `scripts/check`, which prints only the Result table, and report passed, nothing to do, runner missing and never ran as four outcomes; skipped or unavailable is never a pass.
- **Remote gates** ([`## Remote action gates`](lifecycle.md#remote-action-gates)). Pushes, pull-request creation, and settings writes are separate gates, confirmed immediately before unless the invocation authorized those exact actions; settings drift is its own line. Never merge.
- **Failure** ([`## Failure and recovery`](lifecycle.md#failure-and-recovery)). Stop before editing on an absent or malformed manifest or a non-full commit, a dirty destination, an origin differing from the manifest, an unavailable subtree, a recorded commit that is not an ancestor of the target, or ambiguous ownership. On a failed verification keep `template.commit` unchanged and report the diff. There is no rollback; do not reset or clean the destination.
- **Resuming** ([`### Resuming`](lifecycle.md#resuming)), only when this run re-enters a stopped one. Re-invoking the command is the resume: re-observe live state and skip what is done.

Every flow ends in the [Final report](reporting.md#final-report).

1. Require a clean destination clone and identify its origin/default branch. Do not stash or discard the user's work. A destination with no clone is cloned with `gh repo clone <owner>/<repo> tmp/update/<repo>` in this repository, since an SSH `git clone` can be denied. Create an empty `tmp/update/pytest.ini` first: pytest searches upward for its configuration, and a destination declaring none would otherwise run under this repository's `pyproject.toml` and fail on its xdist `addopts`.
2. Run the read-only preflight before editing:

   ```bash
   python3 <template-repo>/apps/repo-builder/src/scripts/preflight.py update \
     --template-repo <template-repo> \
     --target <ref-or-commit> \
     --destination <destination>
   ```

   It validates the manifest, repository identities, clean worktree, subtrees, full commits, ancestry, and ownership, and marks each delta path `unmodified`, `modified`, `absent`, or `current` (a changed path whose destination file already equals the new payload version) against the destination. A non-descendant target is a hard stop. Do not run `scripts/repo-settings check` here: the destination's copy predates the update and cannot know a rule the update carries. Step 5 runs it.
3. Land what needs no judgment:

   ```bash
   python3 <template-repo>/apps/repo-builder/src/scripts/update.py apply \
     --template-repo <template-repo> \
     --target <ref-or-commit> \
     --destination <destination> | tee <destination>.apply.json
   ```

   Records sit beside the clone, named by appending to the destination path, so none enters the diff or the copy proof; write `<destination>` with no trailing slash and never as `.`, or the record lands inside the clone. It stages at the payload's mode every unmodified path, every `current` path (counted under `already-current`, not `write`, and never in `removed`), absent add, expired override, deletion the destination already made, and every `.github/` path in the delta. It skips overridden paths, and returns the rest under `left` with a `reason`. Read `left`, `dependabot`, `unmatched_overrides`, `overridden`, and `refused_overrides` (each `{path, reason}`); `applied` is counts by action, so read no file it applied. `removed` names each path the payload deleted or moved away from, `already-absent` included since a reference to it is stale either way (`old_path` the name a move left), and `discarded` each `.github/` path it overwrote, deleted, or moved over destination edits or a refused override: carry those into the loss report the automation-directory rule asks for. It also writes `dependabot.yml` itself when the delta holds it, deriving the ecosystem entries from the destination's tracked manifests, and returns `dependabot` (null otherwise): `watched` the `[ecosystem, directory]` pairs parsed from the written file, and `dropped` every pair the destination's old file watched that the new one does not.
   Overridden paths ([`### Overridden paths`](lifecycle.md#overridden-paths)): a delta path in `generation.overrides` takes none of the four rules and is reported as overridden with its reason. An entry whose path the destination no longer holds is expired: the payload lands and the entry is dropped in this pull request. Preflight marks both (`override_expired`, `unmatched_overrides`). Never an entry on a product path or on `.gitignore`; an entry on a `.github/` path is not honored, so `update.py apply` lands the payload, returns the entry under `refused_overrides`, and it is dropped in this pull request.
4. Read the recorded generation decisions (`generation.overrides`, `superseded`, `features`), then reconcile only the `left` paths, reading the three versions (old payload at the recorded commit, destination, new payload at the target) for `modified` and the new payload's alone for `absent`:
   - template changed, destination matches old: apply the new template version;
   - destination changed, template did not: preserve the destination;
   - both changed in non-overlapping ways: combine both intents and verify;
   - both changed the same behavior, a changed file was deleted/renamed, or a new template path collides with product content: report the conflict and request the specific policy decision. An `absent` path the payload changes or renames is this deletion conflict; a `product-owned` one is the collision.

   Code scanning ([`## Code scanning lands everywhere and decides at run time`](lifecycle.md#code-scanning-lands-everywhere-and-decides-at-run-time)): `codeql.yml` lands whatever the visibility and decides per run. Reason `codeql-omitted-by-choice` excuses absence only for a record of `"codeql": "omitted-by-choice"`; restoring it there is a policy decision for the conflict gate.

   A path in `generation.superseded` ([`## The automation directory is replaced, not reconciled`](lifecycle.md#the-automation-directory-is-replaced-not-reconciled)) was replaced or retired by an earlier flow: its absence is not a deletion or a conflict, so report it with what it did and what carries it now.

   Carry `dependabot.dropped` to the step 8 gate by ecosystem and directory; reinstating one is the destination's to authorize, and `watched` is the parse evidence.

   Classify every delta path as `applied`, `preserved`, `renamed/deleted`, `merged`, `overridden`, `superseded`, or `conflicted`, with no conflict markers. `merged` carries both the payload's change and the destination's text, records no override, and stays managed. `overridden` is only a payload path the flow did not land; an expired one is `applied`.
5. Install the hooks ([`### Working hooks in a candidate`](lifecycle.md#working-hooks-in-a-candidate)): update runs in the operator's own clone at `--local` scope. Link any hook the clone already had under `<type>.legacy` before pinning `core.hooksPath`, verify with `git -C <tree> rev-parse --git-path hooks`, never unset the operator's global key, report a global `core.hooksPath` and leave the local one pinned. Then install the destination's dependencies: where it has a root `package-lock.json`, run `npm ci` in it first, since the Node adapters call `npm run` against an installed `node_modules` while uv (`uv run`), cargo, go, SwiftPM and Gradle resolve dependencies on first use. Then run the destination's checks, and run the reconciled settings check, which reports rather than gates:

   ```bash
   <destination>/scripts/check > <destination>.check.txt; echo "exit $?"
   <destination>/scripts/repo-settings check | tee <destination>.settings.txt
   ```

   If the checks fail, keep the recorded commit unchanged and report the candidate diff. Record every `FAIL` row as drift and patch nothing; a setting that is off (`FAIL`), one not offered for the plan (`not-applicable`), and one unreadable for want of admin or network (`unavailable`) are three findings and only the first is drift. Report the check `unavailable` when it could not run, and `not checked` where the checks failed first.
6. Prove the copies, before step 7 advances the recorded commit:

   ```bash
   python3 <template-repo>/apps/repo-builder/src/scripts/update.py proof \
     --template-repo <template-repo> \
     --target <ref-or-commit> \
     --destination <destination> | tee <destination>.proof.json
   ```

   Read its `authored` list line by line, per [Reviewing the pull request](reporting.md#reviewing-the-pull-request), and grep the destination for every path the update deleted or renamed: step 3's `removed` (the `old_path` of a move) and every `left` path reconciled as a deletion or rename.
7. After successful checks, run `update.py advance` with the same three arguments to set `template.commit` to the exact target, then rerun the checks the change affects.
8. Create a feature branch from the current remote default branch. Commit only the bounded lifecycle diff. Render the body from the four records with `update.py pr-body` (the same three arguments), which writes `<destination>.pr-body.md` with the destination template's headings and lists any unfilled `[[FILL: <name>]]` slots under `slots`; fill them, then present the remote gate, push, and open the PR with `--body-file <destination>.pr-body.md`. Do not merge.

   Settings drift from step 5 is its own gate line: each setting with its current value, its proposed value, and the exact `gh api` command, never folded into the push line. Drift the user declines is reported as declined, not carried forward or re-raised next update, except head branch deletion: every repository requires it, so it is offered again while it stays off. An update that changes the four workflows also offers the runner variable ([`## The runner variable is set only where it is safe and answerable`](lifecycle.md#the-runner-variable-is-set-only-where-it-is-safe-and-answerable)), on its own line and not as drift: `gh variable set RUNNER --body self-hosted -R <owner>/<repository>`, only on a private repository whose `dev-<repository>` runner reads `online`; otherwise say which condition failed and offer nothing.
9. Verify PR base/head, changed paths, the recorded target commit, check results, and preserved product paths. Re-read any patched setting rather than trusting a 200, and where `RUNNER` was set read `runner_name` off the jobs. `update.py verify --destination <destination> [<destination> ...]` does the PR read for a published destination: it waits on `gh pr checks`, then records base, head, changed-file count, the head's `template.commit` and a count by check conclusion in `<destination>.verify.json`; a destination with no `published` record is `not-published`. When the PR's branch falls behind the default branch, update it with `gh api -X PUT repos/<owner>/<repo>/pulls/<n>/update-branch`; `gh pr update-branch` does not exist.

## Several destinations

List and clone the eligible destinations in one call first: it lists `<owner>`'s non-archived repositories (an archived one refuses the push), reads each recorded commit, and gives a verdict of `current`, `eligible` (a strict ancestor of the target) or `not-ancestor`; a repository without a record (a 404) is omitted, and any other read failure stops the listing. With `--clone` it writes the empty `tmp/update/pytest.ini` of step 1 and clones each `eligible` one to `tmp/update/<repo>`, skipping a directory that exists, and adds `cloned` to its entry:

```bash
python3 <template-repo>/apps/repo-builder/src/scripts/update.py eligible \
  --owner <owner> \
  --template-repo <template-repo> \
  --target <ref-or-commit> \
  --clone tmp/update
```

Then run the mechanical steps over all of them with scripts, not a subagent each:

1. Pass each `cloned` path as a `--destination`.
2. Run them in one call; it applies, installs dependencies and hooks, proves, advances, checks, reads the settings, branches `repo-builder/<first 12 of target>`, commits with the `Generated-By` trailer and renders the body, for each destination in turn, writing the records beside each clone:

   ```bash
   python3 <template-repo>/apps/repo-builder/src/scripts/update.py run \
     --template-repo <template-repo> \
     --target <ref-or-commit> \
     --destination <destination> [<destination> ...] \
     --generated-by <model>
   ```

   The output is `{ok, operation, schema_version, destinations: [...]}`, each entry `{destination, status, detail, drift, settings_unavailable}`, `drift` the settings check's `FAIL` rows and `settings_unavailable` its `unavailable` rows or why it could not run, `status` one of `ready`, `reconcile` (`detail` the paths left), `install-failed`, `check-failed` (`detail` the `scripts/check` log) or `stopped` (`detail` the error). One destination's stop does not stop the rest.
3. Present the remote gate: a push and pull request per `ready` destination, and each `drift` line as its own settings gate with its `gh api` command, as step 8 describes. Then publish the confirmed ones, which pushes each branch and opens its pull request with `<destination>.pr-body.md`, refusing one off a `repo-builder/` branch, with nothing ahead of the origin default branch, or with a `[[FILL:` slot left:

   ```bash
   python3 <template-repo>/apps/repo-builder/src/scripts/update.py publish \
     --destination <destination> [<destination> ...]
   ```

   Each result lands in `<destination>.publish.json`, whose `detail` is the pull request URL when `published`. A rerun keeps a `published` record and does not push that destination again.
4. Verify the published pull requests, which waits for their checks and reads each back (step 9 of the single flow, for the rest of its list):

   ```bash
   python3 <template-repo>/apps/repo-builder/src/scripts/update.py verify \
     --destination <destination> [<destination> ...]
   ```

   Each entry is `{destination, status, pull_request, base, head, files, template_commit, checks}`, `status` `verified` or `not-published` (`detail` why).

5. Render the Final report from the six records beside each clone (`.apply.json`, `.proof.json`, `.check.txt`, `.settings.txt`, `.publish.json`, `.verify.json`); a missing one fails naming it. It writes `report.md` in the first destination's parent directory and returns `{operation, path, slots}`, each slot a line the records cannot settle:

   ```bash
   python3 <template-repo>/apps/repo-builder/src/scripts/update.py report \
     --template-repo <template-repo> \
     --target <ref-or-commit> \
     --destination <destination> [<destination> ...]
   ```

Spawn one subagent per destination only for a `reconcile`, `install-failed`, `check-failed` or `stopped` status. It continues that destination's flow from its records (from step 4 for `reconcile`, whose apply is already done) and returns only the [Final report](reporting.md#final-report) block. A subagent cannot ask the user, so it stops at each remote gate and returns what it would do. The parent owns every gate's confirmation. The parent's Final report is the `report` output of step 5, with each `[[FILL: <name>]]` slot it lists decided.
