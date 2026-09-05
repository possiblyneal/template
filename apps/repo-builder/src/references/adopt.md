# Adopt

Adopt lands a held-back repository addon into a repository that already carries `.repo-template.json`, once its condition has arrived. It reads the addon from the **recorded** commit and never advances the pin: a newer addon is an update first, then an adopt. Use it instead of update when the request adds an addon rather than carrying a template delta.

Read [`lifecycle.md`](lifecycle.md) first — the manifest, ownership, check reporting, the remote gates, failure behavior, and the report shape are there and apply throughout.

1. Confirm `.repo-template.json` is present — its absence makes this a generate, not an adopt. Require a clean destination worktree and identify its origin/default branch. Do not stash or discard the user's work.
2. Run the read-only preflight before editing:

   ```bash
   python3 <template-repo>/apps/repo-builder/src/scripts/preflight.py adopt \
     --template-repo <template-repo> \
     --destination <destination> \
     --addon <destination-relative path> [--addon ...]
   ```

   It validates the manifest, both repository identities, a clean worktree, and the recorded commit, then for each addon confirms the blob exists in `repository-addons/` at that commit, carries an `addon-adoption.json` entry, completes its pair, and is absent from the destination. A half pair or an already-present addon is a hard stop. Retain the JSON.
3. Copy each addon from the recorded commit out of `repository-addons/` — a sibling of the subtree, not inside it — into the candidate at its destination-relative path. Every pair is satisfied the same way, alongside the addon or already in the destination: `CONTRIBUTORS.md` with `.all-contributorsrc`, `CHANGELOG.md` with `.claude/rules/changelog.md`, and `AUTHORS` with `LICENSE`. The first two are two-way, so either half asks for the other; `AUTHORS` asks for `LICENSE` and not the reverse.
4. Run the [Addon adoption](addon-adoption.md) walkthrough for every addon taken: ask each distinct `value_key` once, fill every slot, surface each review judgement, and list each external step. Report each region as done or outstanding.
5. Do not advance `template.commit` and do not record the addon in the manifest. Ownership already treats a later-seen adopted file as destination-added rather than a template deletion, so a subsequent update leaves it alone.
6. Stage the candidate and run the destination's documented checks as [Running the destination's checks](lifecycle.md#running-the-destinations-checks) directs. Then prove the copied files are copies as [Reviewing the pull request](lifecycle.md#reviewing-the-pull-request) directs, and read the authored surface it leaves.

   Then run the settings check, which reports rather than gates:

   ```bash
   <destination>/scripts/repo-settings check
   ```

   Adopt reconciles nothing, so this is the destination's own copy at whatever version the last generate or update left — it reports the rules that copy knows, which can be behind the template's current ones. Say so when reporting: an adopt that finds no drift has established less than an update that finds none. Record every `optional missing:` line as drift and patch nothing here; step 7 asks.
7. Create a feature branch from the current remote default branch. Commit only the adopted addon paths, present the remote gate, push, and open a PR. Never merge.

   Drift step 6 recorded is its own line on that gate and its own authorization, the same as on an update: current value, proposed value, exact `gh api` command, never folded into the push line. Adopting an addon is not consent to change how the repository merges. Drift the user declines is reported as declined and left alone.
8. Verify PR base/head, that only addon paths changed, check results, and that product content is preserved.
