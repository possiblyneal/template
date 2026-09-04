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
5. Classify every delta path as `applied`, `preserved`, `renamed/deleted`, or `conflicted`. Do not leave conflict markers.
6. Run the destination's documented checks as [Running the destination's checks](lifecycle.md#running-the-destinations-checks) directs. If they fail, keep the recorded commit unchanged and report the candidate diff for recovery. Then prove the copied files are copies as [Reviewing the pull request](lifecycle.md#reviewing-the-pull-request) directs, and read the authored surface it leaves.

   Then run the reconciled settings check, which reports rather than gates:

   ```bash
   <destination>/scripts/repo-settings check
   ```

   It runs here rather than in step 2 because a settings rule this update delivers arrives as a changed `scripts/repo-settings`, so only the reconciled copy knows it. Record every `optional missing:` line as drift and patch nothing — this reports, step 8 asks. Keep the script's outcomes distinct: a setting that is off, one not offered for the plan, and one that could not be read for want of admin or network are three findings and only the first is drift. Report the check itself as `unavailable` when it could not run, never as a pass. An update whose checks failed above never reaches this, so its settings report is `not checked`, not a pass.
7. After successful checks, update `template.commit` to the exact target, validate the manifest again, and rerun checks affected by that change.
8. Create a feature branch from the current remote default branch. Commit only the bounded lifecycle diff, present the remote gate, push, and open a PR. Do not merge.

   Drift step 6 recorded is its own line on that gate and its own authorization: name each setting with its current value, its proposed value, and the exact `gh api` command, and do not fold them into the push line. Carrying a template delta is not consent to change how the repository merges. Drift the user declines is reported as declined and left alone, not carried forward and not re-raised as a defect next update.
9. Verify PR base/head, changed paths, the recorded target commit, check results, and preserved product paths. Re-read any setting that was patched rather than inferring it from the call returning 200.
