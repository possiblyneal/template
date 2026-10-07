# Update

Rules from [`lifecycle.md`](lifecycle.md) that apply throughout, stated here so the file is never opened whole. Each links to its section for the reasoning; read that section only when the statement here is not enough.

- **Placeholders.** Quote every `<placeholder>` when substituting, and reject a repository or branch name outside `[A-Za-z0-9._/-]+` before it reaches a shell.
- **Manifest** ([`## Manifest`](lifecycle.md#manifest)). `template.commit` is the last template version applied; change it only after the candidate passes verification, in the same pull request. Record no timestamp, pending target, destination HEAD, or file contents. `features` records deliberate absences, `generation.applications` lets an update tell a rename from a delete, and an old `application_name` is left as it is.
- **Ownership** ([`## Ownership`](lifecycle.md#ownership)). `managed` paths are reconciled with the destination's intent, never overwritten blind; `product` paths are preserved, and a payload path colliding with product content is reported and stops the run. Unmatched is product; the longest matching rule wins; a root file is owned only where named individually. Only the old-to-new delta is in scope. The root `CLAUDE.md` is managed and `merged`, not overwritten, and a payload path the template never shipped (an adopted addon) is not a deletion.
- **Overridden paths** ([`### Overridden paths`](lifecycle.md#overridden-paths)). A delta path in `generation.overrides` takes none of the four rules and is reported as overridden with its reason. An entry whose path the destination no longer holds is expired: the payload lands and the entry is dropped in this pull request. Preflight marks both (`override_expired`, `unmatched_overrides`). Never an entry on a product path or on `.gitignore`.
- **The ignore file** ([`### The ignore file keeps the destination's rules`](lifecycle.md#the-ignore-file-keeps-the-destinations-rules)). `.gitignore` takes the four rules like any managed path; a destination-only rule survives.
- **The automation directory** ([`## The automation directory is replaced, not reconciled`](lifecycle.md#the-automation-directory-is-replaced-not-reconciled)). `.github/` takes the payload's version whole and is not declinable; name a lost destination `PULL_REQUEST_TEMPLATE.md` or `ISSUE_TEMPLATE/` in the report. A path in `generation.superseded` was replaced or retired by an earlier flow: its absence is not a deletion or a conflict, so report it with what it did and what carries it now.
- **Modes** ([`### The payload's mode travels with the payload's content`](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content)). A payload path written over an existing file ends at the payload's mode, read from `git ls-tree <commit> -- <subtree>/<path>`; update.py apply does this for what it lands, and a path reconciled by hand needs it set explicitly.
- **Code scanning** ([`## Code scanning lands everywhere and decides at run time`](lifecycle.md#code-scanning-lands-everywhere-and-decides-at-run-time)). `codeql.yml` lands whatever the visibility and decides per run. Only a record of `"codeql": "omitted-by-choice"` excuses its absence; restoring it there is a policy decision for the conflict gate.
- **Dependabot** ([`## Dependabot entries follow the manifests present`](lifecycle.md#dependabot-entries-follow-the-manifests-present)). `dependabot.yml` is replaced, then its language entries are re-derived from the destination's tracked manifests, never preserved; verify by parsing the written file.
- **Checks** ([`## Running the destination's checks`](lifecycle.md#running-the-destinations-checks)). Stage first, read the run through `scripts/summarize scripts/check`, and report passed, nothing to do, runner missing and never ran as four outcomes; skipped or unavailable is never a pass.
- **Hooks** ([`### Working hooks in a candidate`](lifecycle.md#working-hooks-in-a-candidate)). Update runs in the operator's own clone at `--local` scope. Link any hook the clone already had under `<type>.legacy` before pinning `core.hooksPath`, verify with `git -C <tree> rev-parse --git-path hooks`, never unset the operator's global key, report a global `core.hooksPath` and leave the local one pinned.
- **Runner variable** ([`## The runner variable is set only where it is safe and answerable`](lifecycle.md#the-runner-variable-is-set-only-where-it-is-safe-and-answerable)). Offer `gh variable set RUNNER --body self-hosted -R <owner>/<repository>` only on a private repository whose `dev-<repository>` runner reads `online`; otherwise say which condition failed and offer nothing. After it is set, prove it by `runner_name` on the jobs.
- **Remote gates** ([`## Remote action gates`](lifecycle.md#remote-action-gates)). Pushes, pull-request creation, and settings writes are separate gates, confirmed immediately before unless the invocation authorized those exact actions; settings drift is its own line. Never merge.
- **Failure** ([`## Failure and recovery`](lifecycle.md#failure-and-recovery)). Stop before editing on an absent or malformed manifest or a non-full commit, a dirty destination, an origin differing from the manifest, an unavailable subtree, a recorded commit that is not an ancestor of the target, or ambiguous ownership. On a failed verification keep `template.commit` unchanged and report the diff. There is no rollback; do not reset or clean the destination.
- **Resuming** ([`### Resuming`](lifecycle.md#resuming)), only when this run re-enters a stopped one. Re-invoking the command is the resume: re-observe live state and skip what is done.

Every flow ends in the [Final report](reporting.md#final-report).

1. Require a clean destination clone and identify its origin/default branch. Do not stash or discard the user's work. A destination with no clone is cloned with `gh repo clone <owner>/<repo> <path>` under this repository's `tmp/`, since an SSH `git clone` can be denied.
2. Run the read-only preflight before editing:

   ```bash
   python3 <template-repo>/apps/repo-builder/src/scripts/preflight.py update \
     --template-repo <template-repo> \
     --target <ref-or-commit> \
     --destination <destination>
   ```

   It validates the manifest, repository identities, clean worktree, subtrees, full commits, ancestry, and ownership, and marks each delta path `unmodified`, `modified`, or `absent` against the destination. A non-descendant target is a hard stop. Do not run `scripts/repo-settings check` here: the destination's copy predates the update and cannot know a rule the update carries. Step 5 runs it.
3. Land what needs no judgment:

   ```bash
   python3 <template-repo>/apps/repo-builder/src/scripts/update.py apply \
     --template-repo <template-repo> \
     --target <ref-or-commit> \
     --destination <destination>
   ```

   It stages at the payload's mode every unmodified path, absent add, expired override, deletion the destination already made, and every `.github/` path in the delta. It skips overridden paths, and returns the rest under `left` with a `reason`. Read `left`, `unmatched_overrides`, and `overridden` (each `{path, reason}`); `applied` is counts by action, so read no file it applied. `discarded` names each `.github/` path it overwrote or deleted over destination edits: carry those into the loss report the automation-directory rule asks for.
4. Read the recorded generation decisions (`generation.overrides`, `superseded`, `features`), then reconcile only the `left` paths, reading the three versions (old payload at the recorded commit, destination, new payload at the target) for `modified` and the new payload's alone for `absent`:
   - template changed, destination matches old: apply the new template version;
   - destination changed, template did not: preserve the destination;
   - both changed in non-overlapping ways: combine both intents and verify;
   - both changed the same behavior, a changed file was deleted/renamed, or a new template path collides with product content: report the conflict and request the specific policy decision. An `absent` path the payload changes or renames is this deletion conflict; a `product-owned` one is the collision.

   Reasons `derive` and `codeql-omitted-by-choice` are the Dependabot and code-scanning rules above. Before `derive` replaces the file, read the destination's `dependabot.yml` and report every `package-ecosystem` the derivation does not cover, and every entry under a covered one whose directory it did not produce, by name on the step 8 gate; reinstating one is the destination's to authorize.

   Classify every delta path as `applied`, `preserved`, `renamed/deleted`, `merged`, `overridden`, `superseded`, or `conflicted`, with no conflict markers. `merged` carries both the payload's change and the destination's text, records no override, and stays managed. `overridden` is only a payload path the flow did not land; an expired one is `applied`.
5. Install the hooks, run the destination's checks, and run the reconciled settings check, which reports rather than gates:

   ```bash
   <destination>/scripts/repo-settings check
   ```

   If the checks fail, keep the recorded commit unchanged and report the candidate diff. Record every `optional missing:` line as drift and patch nothing; a setting that is off, one not offered for the plan, and one unreadable for want of admin or network are three findings and only the first is drift. Report the check `unavailable` when it could not run, and `not checked` where the checks failed first.
6. Prove the copies, before step 7 advances the recorded commit:

   ```bash
   python3 <template-repo>/apps/repo-builder/src/scripts/update.py proof \
     --template-repo <template-repo> \
     --target <ref-or-commit> \
     --destination <destination>
   ```

   Read its `authored` list line by line, per [Reviewing the pull request](reporting.md#reviewing-the-pull-request), and grep the destination for every path the update deleted or renamed.
7. After successful checks, run `update.py advance` with the same three arguments to set `template.commit` to the exact target, then rerun the checks the change affects.
8. Create a feature branch from the current remote default branch. Commit only the bounded lifecycle diff, present the remote gate, push, and open a PR. Do not merge.

   Settings drift from step 5 is its own gate line: each setting with its current value, its proposed value, and the exact `gh api` command, never folded into the push line. Drift the user declines is reported as declined, not carried forward or re-raised next update. An update that changes the four workflows also offers the runner variable, on its own line and not as drift.
9. Verify PR base/head, changed paths, the recorded target commit, check results, and preserved product paths. Re-read any patched setting rather than trusting a 200, and where `RUNNER` was set read `runner_name` off the jobs. When the PR's branch falls behind the default branch, update it with `gh api -X PUT repos/<owner>/<repo>/pulls/<n>/update-branch`; `gh pr update-branch` does not exist.

## Several destinations

List the eligible destinations in one call first: `gh repo list <owner> --json nameWithOwner`, then per repository `gh api repos/<r>/contents/.repo-template.json` to read the recorded commit, keeping those whose commit is a strict ancestor of the target.

An update over several repositories runs one subagent per destination, each running this flow and returning only the [Final report](reporting.md#final-report) block. A subagent cannot ask the user, so it stops at each remote gate and returns what it would do. The parent assembles the reports and owns every gate's confirmation.
