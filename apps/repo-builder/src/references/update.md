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

   The command validates the manifest, repository identities, clean worktree, old and target subtrees, full commits, ancestry, and ownership classification. It also marks each delta path it leaves to reconcile `unmodified`, `modified`, or `absent` against the destination, which is what step 3 reads instead of opening the files. A non-descendant target is a hard stop.

   It reads local state only, and hosted settings are not files — they never enter the delta, so no reconciliation in step 4 can reach them. A settings rule added to the template after a repository was generated arrives as a changed `scripts/repo-settings`, which is a check nobody runs. Step 6 runs it, once reconciliation has put that changed script in the destination. Do not run it here: the copy sitting in the destination during this read-only pass is the one this update is replacing, and it is the only copy that cannot know the rule the update carries.
3. Read the recorded generation decisions, then read file content only where step 4 needs it. Preflight marks every delta path it leaves to reconcile `unmodified`, `modified`, or `absent` in `destination_state` — an overridden path takes none of the four rules and carries no such field — comparing the destination's blob against the old payload's at the name the destination holds. Only `modified` earns reading the three versions the rules weigh — old payload at the recorded commit, destination, new payload at the target commit. An `unmodified` path is settled by the first rule in step 4 without opening anything, and on a routine update that is every path; reading them anyway is three file reads per path to rediscover what the field already said. An `absent` path earns the new payload's version alone: where the payload adds the path there is nothing else to read, and where it changes or renames one the destination no longer holds, the absence is the fourth rule's deletion conflict and the old and destination versions cannot be read anyway.

   Paths under `.github/` are read for none of it whatever their state, since the prefix is replaced whole by the rule below rather than reconciled. The one exception is `dependabot.yml`, whose destination copy is read for the ecosystems the derivation cannot rebuild.
4. Reconcile only paths in the preflight delta:
   - template changed, destination matches old: apply the new template version;
   - destination changed, template did not: preserve the destination;
   - both changed in non-overlapping ways: combine both intents and verify;
   - both changed the same behavior, a changed file was deleted/renamed, or a new template path collides with product content: report the conflict and request the specific policy decision.

   A delta path listed in `generation.overrides` takes none of the four, and every entry is read for expiry whether or not its path is in the delta. Preflight has already done that reading, in both halves: a delta path whose entry the destination no longer holds arrives marked `override_expired` rather than overridden, and `unmatched_overrides` names every entry the delta does not reach, marking each `expired` or `unreached`. So an expired entry is dropped in this pull request rather than found by re-reading the record by hand. Both rules and the reasons behind them are at [Overridden paths](lifecycle.md#overridden-paths); this step does what that section says and adds nothing.

   A path listed in `generation.superseded` was replaced or retired by an earlier flow, not lost. Its absence is not a deletion to reconcile and not a conflict to raise: the entry names what the path did and what carries it now, and re-raising it is the re-litigation the record exists to stop. Paths under `.github/` take the payload's version outright, as [The automation directory is replaced, not reconciled](lifecycle.md#the-automation-directory-is-replaced-not-reconciled) directs: the destination cannot have hand-merged a tree this skill replaces whole, so none of the four rules applies there. One path inside that prefix is an exception, decided by a rule below rather than by flat replacement: `dependabot.yml`.

   `.github/dependabot.yml` is replaced like the rest and then gains the language entries the destination's manifests earn, as [Dependabot entries follow the manifests present](lifecycle.md#dependabot-entries-follow-the-manifests-present) directs. That is a derivation rather than a fifth reconciliation rule: the entries are recomputed from what the destination holds at this commit, so a destination whose manifests moved or went away since the last update gets the current set without anyone diffing the old one. An entry the destination had added by hand for one of the mapped ecosystems is not preserved and does not need to be — where its manifest is still there the derivation writes it again, and where it is not, the entry was the thing that would have failed the run.

   An entry for an ecosystem the mapping does not cover is the case this does destroy. Dependabot supports far more than the six languages this template detects — `docker`, `terraform`, `nuget`, `bundler`, `composer` and the rest — and the derivation cannot rebuild what it cannot recognize, so an entry a destination added for one of them is replaced away with its manifest still sitting there. Read the destination's own copy of the file before replacing it, and report every `package-ecosystem` in it that the mapping does not cover, by name, on the gate in step 8 alongside the settings drift: the entry is the destination's decision and reinstating it is the destination's to authorize, not this flow's to infer. Losing one silently is the same class of gap this rule was written to close, pointed the other way.

   `codeql.yml` is replaced like the rest of the prefix, whatever the destination's visibility: the workflow decides per run, as [Code scanning lands everywhere and decides at run time](lifecycle.md#code-scanning-lands-everywhere-and-decides-at-run-time) sets out. The one destination it does not land at is one whose `generation.features` records `"codeql": "omitted-by-choice"`, where its absence is that record's subject rather than a deletion to reconcile. Restoring it there is a policy decision for the conflict gate, not something an update does quietly.
   A path this step writes from the payload takes the payload's mode with it, under [The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content). An update is the flow most exposed to it: every path it touches already exists in the destination, so every write is a rewrite in place and keeps whatever bit the destination set.

5. Classify every delta path as `applied`, `preserved`, `renamed/deleted`, `overridden`, `superseded`, or `conflicted`. Do not leave conflict markers. Report an `overridden` path as [Overridden paths](lifecycle.md#overridden-paths) directs. A path whose override expired above is `applied`. A `superseded` path is one an earlier flow replaced or retired: it is absent from the destination by an earlier decision rather than by this update, so report it by name with what it did and what carries it now, and reconcile nothing.
6. Install the destination's hooks by the shared recipe at [Working hooks in a candidate](lifecycle.md#working-hooks-in-a-candidate), which names update's scope and what an already-hooked clone owes before the key is pinned. Then run the destination's documented checks as [Running the destination's checks](lifecycle.md#running-the-destinations-checks) directs. If they fail, keep the recorded commit unchanged and report the candidate diff for recovery. Then prove the copied files are copies as [Reviewing the pull request](reporting.md#reviewing-the-pull-request) directs, and read the authored surface it leaves.

   Then run the reconciled settings check, which reports rather than gates:

   ```bash
   <destination>/scripts/repo-settings check
   ```

   It runs here rather than in step 2 because a settings rule this update delivers arrives as a changed `scripts/repo-settings`, so only the reconciled copy knows it. Record every `optional missing:` line as drift and patch nothing — this reports, step 8 asks. Keep the script's outcomes distinct: a setting that is off, one not offered for the plan, and one that could not be read for want of admin or network are three findings and only the first is drift. Report the check itself as `unavailable` when it could not run, never as a pass. An update whose checks failed above never reaches this, so its settings report is `not checked`, not a pass.
7. After successful checks, update `template.commit` to the exact target, validate the manifest again, and rerun checks affected by that change.
8. Create a feature branch from the current remote default branch. Commit only the bounded lifecycle diff, present the remote gate, push, and open a PR. Do not merge.

   Drift step 6 recorded is its own line on that gate and its own authorization: name each setting with its current value, its proposed value, and the exact `gh api` command, and do not fold them into the push line. Carrying a template delta is not consent to change how the repository merges. Drift the user declines is reported as declined and left alone, not carried forward and not re-raised as a defect next update.
9. Verify PR base/head, changed paths, the recorded target commit, check results, and preserved product paths. Re-read any setting that was patched rather than inferring it from the call returning 200.
