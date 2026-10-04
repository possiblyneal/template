# Step 1 — Resolve the source commit and preflight

Part of [Retrofit](retrofit.md). Resolve the requested source to an exact commit and run:

```bash
python3 apps/repo-builder/src/scripts/preflight.py retrofit \
  --template-repo <template-repo> \
  --target <ref-or-commit> \
  --subtree apps/github-repository-template/src/base-repo \
  --destination <path-to-destination-clone> \
  --destination-repository <owner/name> \
  --default-branch main > <records>.preflight.json
```

`--destination` is the operator's clone; `--destination-repository` is what its origin must name, so a clone whose directory and repository names differ still resolves. `--default-branch` is the payload's; a destination on another name is reported, not refused.

Every check reads git only.

- **Hard stops:** not a git repository; no origin remote; an origin disagreeing with the named repository; uncommitted edits to tracked files; a paused merge, rebase, cherry-pick or revert (its own check, since a rebase stopped at `edit` has a clean index); a record already present, meaning the caller wanted [update](update.md) or [adopt](adopt.md).
- **Findings, never stops:** untracked files; a default branch other than the payload's; every collision; every addon-shaped path the destination holds, in `addons_present`, reported and never acted on under [The retrofit adopts no addon](#the-retrofit-adopts-no-addon).

The record is the ground truth for `payload_paths` (the delivery check), `collisions` (step 7 disposes them) and `absent_paths`, the difference (step 3 writes them). Never recompute any of them by hand.

A collision is evidence, not a decision. Preflight cannot classify one by ownership, since the ownership rules live in the record a retrofit writes last.

## The retrofit adopts no addon

A retrofit takes no [repository addon](addon-adoption.md). `addons_present` only names the addon-shaped paths the destination already holds, so the operator sees what [adopt](adopt.md) would have offered.

No mechanism is needed to leave them alone: the root allowlist names the addon files, so the structure audit does not flag them, and addons live outside the payload subtree, so they never reach the collision list or step 3.

The record the retrofit writes carries no addon entry, since this flow landed none. A destination that wants one runs adopt afterwards.
