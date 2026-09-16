# Retrofit

Read [`lifecycle.md`](lifecycle.md) first — the manifest, ownership, check reporting, the remote gates, failure behavior, and the report shape are there and apply throughout.

A retrofit brings a repository that was never generated from this template under it: the destination has content and carries no record. Everything a generate builds from nothing, a retrofit has to reconcile against something somebody is already shipping.

The shared mechanics stay in [`generate.md`](generate.md) and are cited by heading rather than restated, so there is one source of truth for each. Follow a citation with `sed -n '/^### Step 3 /,/^### /p'` rather than opening the whole file.

## Steps

- **Step 1 — Resolve the source commit and preflight**
- **Step 2 — Build the candidate**
- **Step 3 — Overlay the payload's absent paths**
- **Step 4 — Provision the environment and the hooks**
- **Step 5 — Read the destination's units**

The steps after these — reconciling the destination's layout, writing the record and deciding the collisions, the hosted-write gate, and publishing — are not written yet. A run that reaches the end of step 5 stops there and reports the candidate it built and the unit map the operator confirmed, rather than improvising the rest against a real repository.

### Step 1 — Resolve the source commit and preflight

Resolve the requested source to an exact commit and run:

```bash
python3 apps/repo-builder/src/scripts/preflight.py retrofit \
  --template-repo <template-repo> \
  --target <ref-or-commit> \
  --subtree apps/github-repository-template/src/base-repo \
  --destination <path-to-destination-clone> \
  --destination-repository <owner/name> \
  --default-branch main
```

`--destination` is the operator's own clone and `--destination-repository` is what its origin must name; passing both is what settles a clone whose directory name and repository name differ. `--default-branch` is the payload's, and a destination on another name is reported rather than refused.

Every check reaches git and nothing else, so the report is about the destination as it sits on disk. Six conditions are hard stops: not a git repository, no origin remote, an origin disagreeing with the named repository, uncommitted edits to tracked files, a paused merge, rebase, cherry-pick or revert, and a record already present — that last one means the caller wanted [update](update.md) or [adopt](adopt.md). A rebase stopped at an `edit` step has a clean index, which is why the paused operation is its own check rather than something the clean-tree check would catch. Four are findings that never stop the run: untracked files, a default branch that is not the payload's, every collision, and every addon-shaped path the destination already holds, in `addons_present`. That last one is reported and never acted on, as [The retrofit adopts no addon](#the-retrofit-adopts-no-addon) gives the reasons for.

Retain the JSON. `payload_paths` is the delivery check's only deterministic ground truth and `collisions` is what step 3 writes against; recomputing either by hand later is how the two come to disagree.

A collision is evidence and not a decision. Preflight cannot classify one by ownership, because the ownership rules live in a record a retrofit writes at the end rather than reads at the start.

### Step 2 — Build the candidate

The candidate is a linked worktree of the operator's own destination clone, checked out into this repository's `tmp/`. Not [generate's payload-only tree](generate.md#step-3--materialize-the-candidate) and not an update's branch in place: the worktree carries the destination's history so the pull-request diff is real, shares its objects so a large history costs disk once, and leaves the operator's working directory untouched for the whole run.

Resolve the default branch from the API rather than from a local ref. Destinations exist with no `origin/HEAD` and with a default branch named `master`, and both read as `main` if the name is assumed:

```bash
default_branch=$(gh repo view <owner/name> --json defaultBranchRef -q .defaultBranchRef.name)
git -C <clone> fetch origin "$default_branch"
git -C <clone> worktree add -b retrofit/<first 12 of the payload commit> \
  <absolute path to this repository>/tmp/<repository-name> "origin/$default_branch"
```

The candidate path is absolute. `git -C` resolves a relative one against the clone, which would put the candidate inside the operator's working directory — the one thing this step promises to leave alone.

The fetch is explicit because the worktree branches from `origin/<default-branch>`, and a stale remote-tracking ref silently retrofits an older tree than the one the pull request will target.

The branch is named for the payload commit and the directory for the destination repository, using the identity preflight verified. Both names are addresses a resumed run has to find again, so neither is chosen freshly per session.

`tmp/` is resolved against this repository rather than against the directory the session was invoked from, and `tmp/*` in `.gitignore` is what keeps a candidate from being committed here by accident. The candidate is never torn down: it is the evidence the report cites. The report hands the operator the command that removes it, `git -C <clone> worktree remove <candidate path>`, rather than running it.

### Step 3 — Overlay the payload's absent paths

Write the payload paths preflight found absent, and write no colliding path at all. Every colliding path stays in the collision list for the per-file decision the flow reaches later. This satisfies the rule against deleting destination content to resolve a collision by construction; copy everything and restore afterwards is rejected, because it breaks that rule in the window between the two steps.

The absent set is `payload_paths` minus the `path` of every collision, taken from the preflight JSON rather than recomputed:

```bash
xargs -r -a <absent-paths> -d '\n' \
  git -C <template-repo> archive --format=tar "<commit>:<subtree>" -- |
  tar -x -i -C <candidate>
```

`-r` on `xargs` is what makes an empty absent set write nothing. Without it `xargs` still runs once, and `git archive <tree> --` with no pathspec after it archives the whole payload over every collision the flow has yet to decide. `git archive` is what carries the file mode across, so `scripts/check` lands executable. `-i` on tar is for the batching: a long path list makes `xargs` call `git archive` more than once, and without it tar stops at the first archive's end marker having silently extracted a prefix of the overlay. Count the extracted paths against the absent set before moving on, and read that count rather than the pipeline's exit status: an empty absent set leaves `tar` reading empty stdin, which exits non-zero on a run that correctly wrote nothing.

Untracked state in the operator's clone is deliberately left behind. A worktree is a fresh checkout, and step 4 rebuilds what the destination's tracked manifests describe. A tracked scratch directory comes along like any other tracked path.

### Step 4 — Provision the environment and the hooks

Provision the candidate's environment from its tracked manifests — the lockfiles and manifests the destination commits, resolved by the destination's own toolchain. An environment that cannot be rebuilt from tracked files is a finding to report against the destination, never something to copy across from the operator's clone: a check surface that passes only against an environment nobody can reproduce measures nothing.

Then install the hooks by the shared recipe at [Working hooks in a candidate](lifecycle.md#working-hooks-in-a-candidate), which names retrofit's scope, where the hooks directory sits, what an already-hooked clone owes before the key is pinned, and how the result is verified. Retrofit's candidate is the only one borrowing a hooks directory it does not own, so read that section's scope list rather than assuming another flow's.

### Step 5 — Read the destination's units

Units are derived from what the destination already delivers, never interviewed out of the operator. A repository that ships something has already decided where its boundaries are, in its build files and its delivery path, and asking the question again invites an answer that contradicts the evidence sitting in the tree.

**A unit is what the repository delivers on its own**: separately built, or separately installed by the repository's own delivery path. Neither half alone is the test. A directory with its own build target that nothing delivers is a build artifact of one unit; a directory the delivery path installs that nothing builds separately is content. Name the evidence for each side per candidate unit, from the destination's own files: build targets and workspace members in its manifests, image or artifact names in its container and packaging files, the services its deployment descriptors install, and the entry points its scripts invoke.

**The name comes from the first source that exists**, in this order: the directory the unit occupies, the built artifact or image name, the package name, the repository name. Kebab-case it, and cite which source it came from. A name whose source is not stated is a name from nowhere, and the operator has nothing to judge it against. The operator renames anything, and a rename is the confirmed name from that point on.

**The run and ship facts are not on disk and are never inferred silently.** `run` and `ships` are the two facts each unit's `.unit.json` carries, and no file in the destination states either: a single `main` package is a CLI, a TUI, or a service, and nothing in the tree tells them apart. So the flow names the evidence it found per unit, proposes a pair from it, and the operator confirms or corrects each one. Both the evidence and the confirmation reach the report and the architecture record, so a later reader can tell a fact that was observed from a fact that was accepted.

**A language with no packaging adapter declares that it ships nothing, and the gap is reported.** `ships.kind` is `none` there, and the report names the unit, its language, and the adapter that does not exist. A declaration guessing at a kind the check surface cannot serve turns `scripts/package` into a command that fails against the unit it was pointed at, which is worse than a declaration that says nothing and a report that says why.

**Domains are drawn only where the destination already draws an internal boundary under one delivery.** A unit that builds and installs as one thing and holds no internal boundary of its own is one unit with no domains, however many directories it has. Drawing a domain the destination does not draw invents a boundary and then moves files to satisfy it.

**A deployable the destination declares but does not build is not a unit.** A third-party image a compose file pulls, a service a descriptor installs from a registry, is somebody else's work the destination happens to run. It lands under the unit that owns the descriptor naming it, and is reported as a deployable the unit model does not describe. That is a finding rather than a stop: the unit model is about what this repository delivers, and saying so out loud is what keeps the omission from reading as an oversight.

**The map is the operator's to confirm.** Present every proposed unit with its name, the source the name came from, the evidence for each half of the delivery test, the proposed run and ship pair with its evidence, any domains and the boundary the destination draws for each, and every declared-but-not-built deployable. A rejected map with no correction stops the flow and is reported: the steps after this one are undecidable without it, and proceeding on a map the operator refused would reconcile a layout against boundaries nobody agreed to.

**This step moves nothing.** Every layout rule is undecidable until units are known, so it produces the map and the confirmed facts and nothing else: no `apps/<name>/` created, no tree relocated, no `.unit.json` written. Layout owns every move, and the architecture record and the unit declarations are written after it, against settled paths.

#### What the decomposition record will say

Written after layout settles the paths, not here, but specified here because this step is where its content is decided.

**One record covers the whole decomposition**, not one per unit. This is the deliberate divergence from [generate's Step 7 — Derive the application boundaries](generate.md#step-7--derive-the-application-boundaries), which writes one record per deployable because each one argues a choke point. A retrofit argues nothing of the kind: it decides where boundaries fall, and it *observes* the languages the destination already committed to. A record per unit there would be deliberation theatre, one document each restating a choice nobody made.

**The choke point is stated as observed rather than chosen**, per unit, and *none of these bind* is recorded as the finding it is rather than left out. An absent constraint and an unmeasured one are indistinguishable in a record that reports neither, and the next reader re-runs the whole question to find out which it was.

**Existing architecture records are normalized to the payload's frontmatter**, carrying the destination's own fields across wherever they correspond to one of the payload's. The `generated` field is left empty: filling it would claim the retrofit authored a decision it only relocated, and the retrofit's own authorship is recorded in the record it writes. Records already at the payload's path are normalized the same way; the location is a separate question, settled by [Architecture records live at the root documentation path](lifecycle.md#architecture-records-live-at-the-root-documentation-path), which binds every flow and is where a record under a unit is refused.

**The manifest records unit names and nothing else**, as [Manifest](lifecycle.md#manifest) directs. The run and ship facts live in the unit declarations and the evidence lives in this record; no new field is added for either.

## The retrofit adopts no addon

A retrofit takes no [repository addon](addon-adoption.md), and needs no mechanism to avoid taking one. What preflight reports in `addons_present` is a finding: the addon-shaped paths the destination already holds, named so the operator can see what [adopt](adopt.md) would have offered against a destination that has answered most of it already.

Nothing has to be taught to leave those files alone. The root allowlist holds the addon filenames by name, under the rule that they are additions by occasion, so a destination's own readme, licence or changelog is already permitted where it sits and the structure audit does not flag it. And an addon is not a payload path: addons live in a sibling tree rather than under the payload subtree, so a destination's readme never reaches the collision list in the first place and step 3 never writes over one.

The record the retrofit writes carries no addon entry, for the same reason [generate](generate.md)'s does not: the manifest records what the flow landed, and this flow landed none. A destination that wants one runs adopt afterwards, against the repository that now exists, and that run is what writes the entry.
