# Update

Read [`lifecycle.md`](lifecycle.md) first — the manifest, ownership, check reporting, the remote gates, failure behavior, and the report shape are there and apply throughout.

1. Require a clean destination clone and identify its origin/default branch. Do not stash or discard the user's work.
2. Run the read-only preflight before editing:

   ```bash
   python3 <template-repo>/apps/repo-builder/src/scripts/preflight.py update \
     --template-repo <template-repo> \
     --target <ref-or-commit> \
     --destination <destination>
   ```

   The command validates the manifest, repository identities, clean worktree, old and target subtrees, full commits, ancestry, and ownership classification. A non-descendant target is a hard stop.

   It reads local state only, and hosted settings are not files — they never enter the delta, so no reconciliation in step 4 can reach them. A settings rule added to the template after a repository was generated arrives as a changed `scripts/repo-settings`, which is a check nobody runs. Step 6 runs it, once reconciliation has put that changed script in the destination. Do not run it here: the copy sitting in the destination during this read-only pass is the one this update is replacing, and it is the only copy that cannot know the rule the update carries.
3. Inspect four sources of intent:
   - old payload at the recorded commit;
   - current destination;
   - new payload at the target commit;
   - recorded generation decisions.
4. Reconcile only paths in the preflight delta:
   - template changed, destination matches old: apply the new template version;
   - destination changed, template did not: preserve the destination;
   - both changed in non-overlapping ways: combine both intents and verify;
   - both changed the same behavior, a changed file was deleted/renamed, or a new template path collides with product content: report the conflict and request the specific policy decision.

   A delta path listed in `generation.overrides` is settled already and takes none of the four. Skip it, and do not raise it as a conflict — the decision it records was made once and re-asking is the defect the record exists to stop. Read the entry's reason before skipping: it is what a later reader has to judge the override by.

   Check each such path for expiry in the same pass, as [Overridden paths](lifecycle.md#overridden-paths) directs. Where the destination no longer holds its own version, the override has nothing left to protect: land the payload's copy and delete the entry from `generation.overrides`, both in this update's pull request. An override kept past the file it was protecting keeps the payload's version out for a reason nobody holds any more.
   A path listed in `generation.superseded` was replaced or retired by an earlier flow, not lost. Its absence is not a deletion to reconcile and not a conflict to raise: the entry names what the path did and what carries it now, and re-raising it is the re-litigation the record exists to stop. Paths under `.github/` take the payload's version outright, as [The automation directory is replaced, not reconciled](lifecycle.md#the-automation-directory-is-replaced-not-reconciled) directs: the destination cannot have hand-merged a tree this skill replaces whole, so none of the four rules applies there. `codeql.yml` is the one exception inside that prefix, decided by the paragraph below instead.

   `codeql.yml` in the delta is decided by [Code scanning follows visibility](lifecycle.md#code-scanning-follows-visibility) rather than by the four rules above, and the visibility is read live. A destination that has gone public since it was built takes the workflow now and drops the `features` record; one that is still private keeps it stripped and keeps the record. Its absence from a private destination is the record's subject, never a deletion to reconcile.
5. Classify every delta path as `applied`, `preserved`, `renamed/deleted`, `overridden`, `superseded`, or `conflicted`. Do not leave conflict markers. An `overridden` path was never written, so it is absent from step 6's copy proof and belongs to neither the copied set nor the authored surface; report it by name with its reason. A path whose override expired above is `applied`. A `superseded` path is one an earlier flow replaced or retired: it is absent from the destination by an earlier decision rather than by this update, so report it by name with what it did and what carries it now, and reconcile nothing.
6. Run the destination's documented checks as [Running the destination's checks](lifecycle.md#running-the-destinations-checks) directs. If they fail, keep the recorded commit unchanged and report the candidate diff for recovery. Then prove the copied files are copies as [Reviewing the pull request](reporting.md#reviewing-the-pull-request) directs, and read the authored surface it leaves.

   Then run the reconciled settings check, which reports rather than gates:

   ```bash
   <destination>/scripts/repo-settings check
   ```

   It runs here rather than in step 2 because a settings rule this update delivers arrives as a changed `scripts/repo-settings`, so only the reconciled copy knows it. Record every `optional missing:` line as drift and patch nothing — this reports, step 8 asks. Keep the script's outcomes distinct: a setting that is off, one not offered for the plan, and one that could not be read for want of admin or network are three findings and only the first is drift. Report the check itself as `unavailable` when it could not run, never as a pass. An update whose checks failed above never reaches this, so its settings report is `not checked`, not a pass.
7. After successful checks, update `template.commit` to the exact target, validate the manifest again, and rerun checks affected by that change.
8. Create a feature branch from the current remote default branch. Commit only the bounded lifecycle diff, present the remote gate, push, and open a PR. Do not merge.

   Drift step 6 recorded is its own line on that gate and its own authorization: name each setting with its current value, its proposed value, and the exact `gh api` command, and do not fold them into the push line. Carrying a template delta is not consent to change how the repository merges. Drift the user declines is reported as declined and left alone, not carried forward and not re-raised as a defect next update.
9. Verify PR base/head, changed paths, the recorded target commit, check results, and preserved product paths. Re-read any setting that was patched rather than inferring it from the call returning 200.
