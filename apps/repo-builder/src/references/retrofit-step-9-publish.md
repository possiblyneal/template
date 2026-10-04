# Step 9 — Publish, prove, and offer the merge

Part of [Retrofit](retrofit.md).

**The head is the candidate's own branch**, at the head step 7 reviewed. Nothing is re-materialized.

**Every push goes to that feature branch, with the destination's hooks running.** The payload's push guard allows a feature branch, so nothing needs `--no-verify`. A push a hook refuses is a finding to report, never a push to repeat with the hook off.

**The base is the default branch**, already correct after step 8's rename.

**The body is always explicit, filled against the pull-request template this same diff introduces**, for the reason [Generate](generate.md#step-11--publish-the-candidate) gives. Render it, fill its slots, and open the pull request with it:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py pr-body \
  --repository <owner>/<repository> --records <records>
gh pr create --repo <owner>/<repository> --base <default-branch> \
  --head retrofit/<first 12 of the payload commit> --title "<title>" \
  --body-file <records>.pr-body.md
```

`pr-body` fills the template's sections from the records — check summary, both proofs, `normalize`, `facts`, `autofix`, workflows the event never runs, deletions, and the write log's reverse commands — leaves every judgement as `[[FILL: …]]`, and reports `path` and `slots`. Fill each slot: Summary, Decisions and Scope carry the per-path dispositions, layout moves and what the review found. Name only paths in the diff. The finished body holds no `[[FILL:` and never carries the session report.

**The proofs are not taken again.** Their counts come from the proofs record step 7 measured. What is left after the two is the authored surface step 7 reviewed.

**Sign the review off once the pull request is open.** Opening it makes the PR-open hook (`~/.claude/hooks/review-new-pr.sh`) ask for a review scan and `/code-review`. **Step 7's review is the answer to that request**, since the pull request opened at the head it reviewed; no second review runs. Where every finding was corrected or recorded as incorrectly identified, apply the `code-reviewed` label and post one comment stating the axes that ran and what they found, whose last line is `Reviewed-Head: <full 40-character sha>` naming the head the pull request opened at. Write both through the REST routes in [Writing to the pull request](reporting.md#writing-to-the-pull-request) and read both back. Where a finding stands unresolved, write no sign-off and say so in the report.

**The file-list account is rendered** from the proofs record, by [Step 10 — Verify the file list](generate.md#step-10--verify-the-file-list). Its three expected differences: the placeholder unit preflight held back, every overridden path, and the destination's own tracked files.

**Every payload workflow except the release workflow runs on this pull request.** Read the check suites as [Step 12 — Verify the published repository](generate.md#step-12--verify-the-published-repository) does, keeping the distinction between a failing run and no run dispatched. Wait with `gh pr checks <n> --watch` as a background command, never a foreground `sleep`.

**A destination that meters Actions minutes stops every workflow before it starts**: each required check fails within seconds with the host's billing message. Report it as workflows the event never ran and the whole gating set unexercised, not as a failing check.

**With the checks green, read `mergeable` and `mergeStateStatus` as a pair**, under [A written ruleset is proved satisfiable, not merely present](lifecycle.md#a-written-ruleset-is-proved-satisfiable-not-merely-present). `MERGEABLE`/`BLOCKED` means the merge can never be taken: a finding against the ruleset, not the candidate.

**Then, optionally, the merge, at a second gate**, offered only once every required check is green, and nothing beside it. Where no check can run for the billing reason, say so in place of the poll. **Declining is the default**, leaving the pull request to the destination's own people, who have unreviewed code in it and branches in flight. Taking it merges, then reads the default branch's check suites, fills the report's line for them, and owes the clone a working hook surface under [Working hooks in the destination after a merge](lifecycle.md#working-hooks-in-the-destination-after-a-merge), except that a default branch carrying no `.pre-commit-config.yaml` makes `retrofit.py hooks` record not-applicable and install nothing.

Then run step 2's sweep and render the report under [Report additions](retrofit-report.md#report-additions).
