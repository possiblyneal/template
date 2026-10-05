# Retrofit: the unmet bar

Read from [Step 7 — Dispose the collisions, write both records, meet the bar](retrofit-step-7-bar.md#the-bar) only when the bar is unmet. This continues that step: every step number names a file listed in [`retrofit.md`](retrofit.md), and the pass and the configuration guard named here are [the autofix pass](retrofit-step-7-bar.md#the-autofix-pass).

**The flow prepares that fix rather than handing back a list**, unless the invocation or the operator declines a fix for the debt: then it prepares no worktree and no branch, and the report says the operator declined it. Write it against the destination's pre-retrofit layout, in a second linked worktree branched off `origin/<default-branch>` the way step 2 branched the candidate. Never use the clone's own checkout: step 2 promises it stays untouched and step 1 hard-stops on a dirty one.

- The branch is `retrofit/fix-<first 12 of the payload commit>` and the worktree `tmp/<repository-name>-fix`. Both are derived, not chosen: re-invoking the flow is the resume, and a fresh name would leave it unable to find the first fix. The `retrofit/*` name lets step 2's reporting see it on a resumed run.
- Reuse a branch that already exists: `git -C <clone> worktree add` without `-b`, since `-b` fails on an existing branch.
- One commit per coherent fix, naming the rule it clears. Two sites of one rule in one file are one fix.
- Findings arrive at the candidate's paths; translate each back to the destination's path through step 6's move list. A finding at a path the retrofit itself created has no pre-retrofit home: report it outstanding rather than fixing it here.

**Where a fix was prepared, that worktree comes down on every path out of this step**, not at step 2's sweep, which runs only on a finished flow. Whether the commits were pushed, the gate declined, the gate never answered, or nothing publishable was committed, remove it with the pair step 2's sweep runs:

```bash
# Empty it first, for step 2's reason: `worktree remove` refuses on modified or
# untracked-and-unignored files, and the destination's harnesses run in this tree.
# By hand, unless the destination ships a `scripts/clean` of its own.
git -C <clone> worktree remove <absolute path to this repository>/tmp/<repository-name>-fix
git -C <clone> worktree prune
```

**Removing the harness output by hand is the ordinary case here**, unlike step 2: this worktree holds the pre-retrofit tree, which rarely carries `scripts/clean`. Use the destination's own `scripts/clean` where it ships one; otherwise delete what the harnesses wrote. Never `--force`: a refusal that survives the emptying is a finding, not an obstacle.

Where a fix was prepared, the branch outlives the worktree and is what the gate below offers; wherever the push did not happen, report it under **Left for the operator**, as for a declined merge's branch. A declined fix has no branch to report.

**Verify it twice, because that worktree's own tools see less than the candidate's.**

1. The destination's own harnesses over the files touched, measured as a delta: nothing reported before the commit may be new after it, since that tree carries repository-wide debt and the inverse case below is left alone. Report both outputs rather than a verdict. Where the destination has no harness, report that and rest the fix on the second reading alone.
2. The rule itself, under the target version the candidate's declaration sets:
   - Python: `ruff check --target-version py311` where the candidate's `requires-python` says `>=3.11`. Use the flag rather than the candidate's configuration, because only the destination's files under the retrofit's version are being read.
   - Rust: where the candidate carries `rust-version` in `Cargo.toml` or `msrv` in `clippy.toml`, the ordinary `cargo clippy` run. Where it carries neither, take the reading in the candidate as below; the flow cannot close that case, since `lifecycle.md`'s tool declaration for Rust is `none` and writes no MSRV.
   - eslint, ktlint, `swift format`, and `go vet` (which reads the `go` directive with no override) take no version input. Take the reading in the candidate: apply the same edits there, re-run the capability that failed the bar, and revert them. Verify the revert with `git -C <candidate> status --porcelain`: the candidate stays standing and a resumed run re-enters it, so a leftover edit would let the destination's fix ride along into the next bar.

   Report which reading was used. A finding gated on the declaration does not fire where none is declared, so a clean lint in the destination's tree proves nothing by itself. Report both counts, before and after. **A non-zero after is not publishable**: fix what the second reading still shows or drop that commit; where neither is possible, report the finding outstanding and offer nothing for it.

**Step 7's configuration guard covers this worktree too**, and bites harder: it sits under this repository's `tmp/`, so a tool walking upward finds *this* repository's configuration, and its pre-retrofit layout carries none of the boundaries the tool declaration writes. Read each tool's resolved settings path (`ruff check --show-settings .` and each language's equivalent) before the worktree's first commit, which comes before either reading. Where a path resolves outside this worktree, or is unreadable, the outcome turns on whether the destination's pre-retrofit tree (the files on `origin/<default-branch>`) carries configuration for that tool:

| Resolved path | Destination has its own config for the tool | Outcome |
|---|---|---|
| Outside the worktree | No | Take the reading with the tool's isolation flag instead of stopping, and report that flag as the settings it was read under. |
| Outside the worktree | Yes | Prepare nothing, report the tool and the path, and leave every finding outstanding. |
| Any | Any, but the language has no isolation flag | Prepare nothing, as in the row above. |

A destination with no ruff configuration always lands in the first row, since ruff walks up to this repository's `pyproject.toml`. The flags, each confirmed against the tool's own help or docs:

- Python: `ruff check --isolated`, which ignores every configuration file. It combines with `--target-version py311` for the second reading.
- eslint: `eslint --no-config-lookup`, which disables lookup of `eslint.config.*`.

Go, Rust, Swift and Kotlin keep the stop: no isolation flag is confirmed for `go vet`, `cargo clippy`, `swift format` or ktlint. Never supply the missing boundary, which would commit this flow's configuration choice to the operator's default branch, and never isolate where the destination carries its own configuration, which would override the operator's settings.

**The inverse case is left alone.** A finding that fires in the destination's tree and not under the candidate's target version is not this retrofit's blocker and gets no commit.

**Where a fix was prepared, publishing that branch is a remote action and takes its own gate**: the only remote write a stopped retrofit may make. It is not a hosted write, so it belongs to [Remote action gates](lifecycle.md#remote-action-gates), which holds its two lines, rather than to step 8. Offer the push and the pull request here, by exact command and target. Ungated or declined, the branch stays local and the report names it and its commit. A run stopping here has made no hosted write at all.

**A published fix that reviews clean is merged by this flow, and the retrofit resumes**, without a further question, on the operator's standing instruction. Review the pull request with `/code-review standard`. The merge waits for all of it: every finding corrected or decided, every axis signed off, the `code-reviewed` label and a `Reviewed-Head:` equal to the head, every required check green, and `mergeable`/`mergeStateStatus` reading `MERGEABLE`/`CLEAN`. Then `gh pr merge <n> --merge`, confirm it reads `MERGED`, remove the local fix branch with `git -C <clone> branch -d`, and re-invoke the flow; that is the resume, measuring the bar again over the default branch the fix now sits on. Bring the standing candidate onto it first:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py resume --candidate <candidate> \
  --default-branch <default-branch> --records <records>
```

It removes the decisions record, since the resumed run makes each judgement again, fetches and merges `origin/<default-branch>` into the candidate, and reports `upstream`, `merged` (the merge commit, or null while the merge awaits its commit), `lockfiles_taken` and `conflicts`. **Never hand-merge a lockfile**: `resume` takes the default branch's side of every conflicted one, its deletion included, and the flow regenerates each that remains with its language's lock-only install (`uv lock`, `npm install --package-lock-only`, `cargo generate-lockfile`, or the equivalent for the language) before staging it. Settle every other conflict as step 7 disposes a collision, then commit the merge and measure the bar again. A judgement call the review raises goes to the operator, and the merge waits for the answer. Anything short of clean leaves the pull request open and the run stopped; re-run the retrofit once the fix is on the default branch. Report the measurement either way: what the autofix cleared, what is left, the file and rule for each, and, where a fix was prepared, what its branch does about each one; a declined fix reports no branch.
