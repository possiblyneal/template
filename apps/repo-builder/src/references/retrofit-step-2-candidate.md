# Step 2 — Build the candidate

Part of [Retrofit](retrofit.md). The candidate is a linked worktree of the operator's own destination clone, checked out into this repository's `tmp/`. It is not [generate's payload-only tree](generate.md#step-3--materialize-the-candidate), and it is not an update's branch in place; `docs/adrs/0005-stage-a-retrofit-locally-and-write-the-host-last.md` records why.

Resolve the default branch from the API rather than from a local ref. Destinations exist with no `origin/HEAD` and with a default branch named `master`, and both read as `main` if the name is assumed:

```bash
default_branch=$(gh repo view <owner/name> --json defaultBranchRef -q .defaultBranchRef.name)
git -C <clone> fetch origin "$default_branch"
git -C <clone> worktree add -b retrofit/<first 12 of the payload commit> \
  <absolute path to this repository>/tmp/<repository-name> "origin/$default_branch"
```

- **The candidate path is absolute.** `git -C` resolves a relative one against the clone, which would put the candidate inside the operator's working directory.
- **The fetch is explicit**, because a stale remote-tracking ref silently retrofits an older tree than the one the pull request will target.
- **Neither name is chosen per session.** The branch is named for the payload commit and the directory for the destination repository, so a resumed run finds both again. A branch already there from a declined merge at the same commit is reused with `git -C <clone> worktree add` without `-b`, since `-b` fails on a branch that exists.

List `git -C <clone> branch --list 'retrofit/*'` and report every branch naming a commit other than this run's under **Left for the operator**, with the state of its pull request. Report it and never delete it: it is the local counterpart of a pull request nobody closed.

**The candidate stands until the flow ends**, because it is the evidence the report cites. The end is reached once the pull request is open, its verification read, and step 9's merge offer settled **either way**. A declined merge is a finished flow, so the sweep runs on the default path:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py sweep \
  --clone <clone> \
  --candidate <absolute path to this repository>/tmp/<repository-name> \
  --branch retrofit/<first 12 of the payload commit> \
  --default-branch <default-branch> \
  --repository <owner>/<name> \
  --hooks-dir <hooksdir> \
  --resume-record <resume record> \
  --write-log <records>.writes.json \
  --records <records>
```

It fetches `origin/<default-branch>`, runs the candidate's own `scripts/clean` where it ships one, removes the worktree and prunes, and removes the hooks directory, the resume record and the write log. It deletes the branch only where `merge-base --is-ancestor` proves `origin/<default-branch>` contains it; `git branch -d` alone compares against the wrong ref. It reports `stages`, `left_for_the_operator` and `findings`; report each entry of `left_for_the_operator` under **Left for the operator**.

Nothing is forced. A `worktree remove` refusal is a finding: it leaves the hooks directory, the resume record and the branch standing with the worktree, and the command still exits 0. `<hooksdir>` is the candidate's own, made under [Working hooks in a candidate](lifecycle.md#working-hooks-in-a-candidate); it is not the hooks surface a taken merge owes the clone, which stays. The resume record is a sibling of the candidate, under [Resuming](lifecycle.md#resuming).

A run that stops before the pull request leaves the whole candidate standing and says so. That is the only case the operator is handed a removal to make.
