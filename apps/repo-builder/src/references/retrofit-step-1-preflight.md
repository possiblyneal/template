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

`--destination` is the operator's own clone and `--destination-repository` is what its origin must name; passing both settles a clone whose directory name and repository name differ. `--default-branch` is the payload's, and a destination on another name is reported rather than refused.

Every check reaches git and nothing else. Six conditions are hard stops: not a git repository, no origin remote, an origin disagreeing with the named repository, uncommitted edits to tracked files, a paused merge, rebase, cherry-pick or revert, and a record already present — that last one means the caller wanted [update](update.md) or [adopt](adopt.md). A rebase stopped at an `edit` step has a clean index, which is why the paused operation is its own check. Four are findings that never stop the run: untracked files, a default branch that is not the payload's, every collision, and every addon-shaped path the destination already holds, in `addons_present`, reported and never acted on under [The retrofit adopts no addon](#the-retrofit-adopts-no-addon).

The record is the ground truth for three lists: `payload_paths` for the delivery check, `collisions` for step 7 to dispose, and `absent_paths`, the difference, for step 3 to write. Never recompute any of them by hand.

A collision is evidence and not a decision. Preflight cannot classify one by ownership, because the ownership rules live in a record a retrofit writes at the end rather than reads at the start.

## The retrofit adopts no addon

A retrofit takes no [repository addon](addon-adoption.md), and needs no mechanism to avoid taking one. `addons_present` is a finding: the addon-shaped paths the destination already holds, named so the operator can see what [adopt](adopt.md) would have offered.

Nothing has to be taught to leave those files alone. The root allowlist holds the addon filenames by name, as additions by occasion, so the structure audit does not flag a destination's own readme, licence or changelog. And addons live in a sibling tree rather than under the payload subtree, so a destination's readme never reaches the collision list and step 3 never writes over one.

The record the retrofit writes carries no addon entry, because the manifest records what the flow landed and this flow landed none. A destination that wants one runs adopt afterwards, against the repository that now exists.
