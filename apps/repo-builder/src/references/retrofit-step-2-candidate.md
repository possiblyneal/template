# Step 2 — Build the candidate

Part of [Retrofit](retrofit.md). The candidate is a linked worktree of the operator's destination clone, checked out into this repository's `tmp/`. It is neither [generate's payload-only tree](generate.md#step-3--materialize-the-candidate) nor an update's in-place branch; `docs/adrs/0005-stage-a-retrofit-locally-and-write-the-host-last.md` records why.

Resolve the default branch from the API, never a local ref: a destination may lack `origin/HEAD` or use `master`.

```bash
default_branch=$(gh repo view <owner/name> --json defaultBranchRef -q .defaultBranchRef.name)
git -C <clone> fetch origin "$default_branch"
git -C <clone> worktree add -b retrofit/<first 12 of the payload commit> \
  <absolute path to this repository>/tmp/<repository-name> "origin/$default_branch"
```

- **The candidate path is absolute.** `git -C` resolves a relative one inside the clone.
- **The fetch is explicit**, so a stale remote-tracking ref cannot retrofit an older tree than the pull request targets.
- **Neither name is chosen per session**, so a resumed run finds both. A branch left from a declined merge at the same commit is reused with `git -C <clone> worktree add` without `-b`, which fails on an existing branch.

List `git -C <clone> branch --list 'retrofit/*'` and report every branch naming a commit other than this run's under **Left for the operator**, with its pull request's state. Never delete it: it is the local counterpart of a pull request nobody closed.

**The candidate stands until the flow ends**, since the report cites it. The end is the pull request open, its verification read, and step 9's merge offer settled **either way**. A declined merge is a finished flow, so the sweep runs on the default path:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py sweep \
  --clone <clone> \
  --candidate <absolute path to this repository>/tmp/<repository-name> \
  --branch retrofit/<first 12 of the payload commit> \
  --default-branch <default-branch> \
  --repository <owner>/<name> \
  --hooks-dir <hooksdir> \
  --resume-record <resume record> \
  --records <records>
```

It fetches `origin/<default-branch>`, runs the candidate's `scripts/clean` where one ships, removes and prunes the worktree, and removes the hooks directory, the resume record and the write log. It deletes the branch only where `merge-base --is-ancestor` proves `origin/<default-branch>` contains it (`git branch -d` compares the wrong ref). It reports `stages`, `left_for_the_operator` and `findings`; report each `left_for_the_operator` entry under **Left for the operator**.

Nothing is forced. A `worktree remove` refusal is a finding: the hooks directory, resume record and branch stay with the worktree, and the command still exits 0. `<hooksdir>` is the candidate's own, from [Working hooks in a candidate](lifecycle.md#working-hooks-in-a-candidate), not the hooks surface a taken merge owes the clone, which stays. The resume record sits beside the candidate, under [Resuming](lifecycle.md#resuming).

A run that stops before the pull request leaves the whole candidate standing and says so; that is the only removal handed to the operator.
