# Retrofit

Read these sections of [`lifecycle.md`](lifecycle.md) first rather than the whole file, each with the subsections under it — `sed -n '/^## Manifest$/,/^## /p'` and its equivalent per heading. They apply throughout:

- the paragraph on quoting a `<placeholder>`, at the top of the file
- `## Manifest`
- `## Ownership`, with `### Overridden paths` and `### The payload's mode travels with the payload's content`
- `## Dependabot entries follow the manifests present`
- `## Running the destination's checks`, with `### Tools the first manifest must declare`, `### Working hooks in a candidate`, and `### Working hooks in the destination after a merge`
- `## The runner variable is set only where it is safe and answerable`
- `## Remote action gates`
- `## Reviewing and reporting`
- `### Resuming`, only when this run re-enters a stopped one

Every other lifecycle section this file links is read where the link sits, by its heading.

A retrofit brings a repository that was never generated from this template under it: the destination has content and carries no record. Everything a generate builds from nothing, a retrofit has to reconcile against something somebody is already shipping.

The shared mechanics stay in [`generate.md`](generate.md) and are cited by heading rather than restated, so there is one source of truth for each. Follow a citation with `sed -n '/^### Step 3 /,/^### /p'` rather than opening the whole file.

**No language is chosen on this path**, so [`wayfinding.md`](wayfinding.md) and [`choosing_a_language.md`](choosing_a_language.md) are not part of a retrofit and are not read. The destination committed to its languages before this flow existed; step 5 observes them.

## Steps

- **Step 1 — Resolve the source commit and preflight**
- **Step 2 — Build the candidate**
- **Step 3 — Overlay the payload's absent paths**
- **Step 4 — Provision the environment and the hooks**
- **Step 5 — Read the destination's units**
- **Step 6 — Reconcile the destination's layout**
- **Step 7 — Dispose the collisions, write both records, meet the bar**
- **Step 8 — The hosted-write gate**
- **Step 9 — Publish, prove, and offer the merge**

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

Retain the JSON. `payload_paths` is the delivery check's only deterministic ground truth, `collisions` is what step 7 disposes, and `absent_paths` is the difference, which is what step 3 writes; recomputing any of them by hand later is how they come to disagree.

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

Because the name carries the payload commit, a run at a later commit gets a different branch and cannot see the one an earlier run left. List them here — `git -C <clone> branch --list 'retrofit/*'` — and report every branch naming a commit other than this run's under **Left for the operator**, with the state of its pull request. Reporting and not deleting: it exists because a merge was declined, so it is the local counterpart of a pull request nobody closed, which the sweep never touches. What the operator should not have to do is discover it themselves.

`tmp/` is resolved against this repository rather than against the directory the session was invoked from, and `tmp/*` in `.gitignore` is what keeps a candidate from being committed here by accident. The candidate stands for as long as the flow can still be resumed from it, because it is the evidence the report cites. It comes down at the end of the flow rather than being handed to the operator as a command, and the end is reached once the pull request is open, its verification read, and step 9's merge offer settled **either way** — a declined merge is a finished flow, not a stop, so the sweep runs on the default path and not only on the rare one:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py sweep \
  --clone <clone> \
  --candidate <absolute path to this repository>/tmp/<repository-name> \
  --branch retrofit/<first 12 of the payload commit> \
  --default-branch <default-branch> \
  --repository <owner>/<name> \
  --hooks-dir <hooksdir> \
  --resume-record <resume record> \
  --write-log <write log>
```

It fetches `origin/<default-branch>` for the containment test, runs the candidate's own `scripts/clean` where it ships one, removes the worktree and prunes, removes the hooks directory, the resume record and step 8's write log, and deletes the branch only where `merge-base --is-ancestor` proves `origin/<default-branch>` contains it. It reports:

- `stages` — each stage's outcome: `fetch`, `clean`, `worktree` and `prune` are `done` or `refused`, `clean` is `not shipped` where the destination has none, `hooks_dir`, `resume_record` and `write_log` are `removed`, `absent` or `skipped`, and `branch` is `deleted`, `kept`, `skipped`, `refused` or `absent`
- `left_for_the_operator` — every `retrofit/*` branch still standing, with why and its pull requests read from GitHub
- `findings` — every refusal, and every pull-request lookup that failed

Nothing is forced. `worktree remove` refuses on a file some step wrote and no step committed, and ignored output does not block it; a refusal that survives the clean is a finding, not an obstacle, and it leaves the hooks directory, the record and the branch standing with the worktree, since the run can still be resumed from it. The command exits 0 with the refusal in `findings`.

`<hooksdir>` is the candidate's own, made for it under [Working hooks in a candidate](lifecycle.md#working-hooks-in-a-candidate) and pinned by nothing once the worktree is gone — the `core.hooksPath` naming it was set at `--worktree` scope and leaves with the worktree. It is not the hooks surface a taken merge owes the destination clone, which is a different directory and stays. The resume record is a sibling of the candidate rather than a file inside it, under [Resuming](lifecycle.md#resuming), so removing the worktree does not take it.

**`-d` is not the containment guard, which is why `merge-base --is-ancestor` runs ahead of it.** `git branch -d` compares the branch against its upstream where one is set and against HEAD otherwise — never against the remote-tracking ref of the default branch. Both readings are wrong here. With no upstream it compares against a local default branch this flow deliberately never moved, so it refuses a branch the merge *did* carry; with an upstream set by a push it compares against that same branch on the remote, which trivially contains it, so it deletes a branch merged nowhere with only a warning. The sweep's own fetch is what makes the ancestry test read the merge, and the test is what makes the delete safe; `-d` rather than `-D` stays as the second line of defence. A failed test deletes nothing and reports the branch `kept`.

Where the merge was declined the branch stays, because it is the local counterpart of a pull request the destination's own people still have open; report each entry of `left_for_the_operator` under **Left for the operator**. A branch left that way outlives its worktree, so a later run at the same payload commit reuses it — `git -C <clone> worktree add` without `-b`, since `-b` fails on a branch that already exists.

A run that stops before the pull request leaves the whole candidate standing and says so. That is the only case the operator is handed a removal to make.

### Step 3 — Overlay the payload's absent paths

Write the payload paths preflight found absent, and write no colliding path at all. Every colliding path stays in the collision list for the per-file decision the flow reaches later. This satisfies the rule against deleting destination content to resolve a collision by construction; copy everything and restore afterwards is rejected, because it breaks that rule in the window between the two steps.

The absent set is `absent_paths` in the preflight JSON — `payload_paths` minus every collision, derived there so the overlay and the copy proof cannot count different lists. Write its entries as given; do not recompute the set. `<absent-paths>` below is that JSON array written out one path per line, which is what `xargs -d '\n'` reads.

**The payload's placeholder unit is in neither list, and preflight is what holds it back.** `apps/app-name/` exists for [generate's Step 8 — Personalize the candidate](generate.md#step-8--personalize-the-candidate) to rename into the application's own name; a retrofit reads its units off what the destination already delivers, so there is nothing for it to be. Both reference retrofits landed it and both retired it by hand. Do not add it back on the reasoning that it is genuinely absent: `preflight.py`'s comment on `PLACEHOLDER_UNIT_PREFIX` has what it survives and why nothing downstream catches it.

```bash
xargs -r -a <absent-paths> -d '\n' \
  git -C <template-repo> archive --format=tar "<commit>:<subtree>" -- |
  tar -x -i -C <candidate>
```

`-r` on `xargs` is what makes an empty absent set write nothing. Without it `xargs` still runs once, and `git archive <tree> --` with no pathspec after it archives the whole payload over every collision the flow has yet to decide. `git archive` is what carries the file mode across, so `scripts/check` lands executable; [The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content) is the rule that holds for the colliding paths this step skips, where the destination's own mode is what a later write would otherwise keep. `-i` on tar is for the batching: a long path list makes `xargs` call `git archive` more than once, and without it tar stops at the first archive's end marker having silently extracted a prefix of the overlay. Count the extracted paths against the absent set before moving on, and read that count rather than the pipeline's exit status: an empty absent set leaves `tar` reading empty stdin, which exits non-zero on a run that correctly wrote nothing.

Untracked state in the operator's clone is deliberately left behind. A worktree is a fresh checkout, and step 4 rebuilds what the destination's tracked manifests describe. A tracked scratch directory comes along like any other tracked path.

### Step 4 — Provision the environment and the hooks

Provision the candidate's environment from its tracked manifests — the lockfiles and manifests the destination commits, resolved by the destination's own toolchain. An environment that cannot be rebuilt from tracked files is a finding to report against the destination, never something to copy across from the operator's clone: a check surface that passes only against an environment nobody can reproduce measures nothing.

Then install the hooks by the shared recipe at [Working hooks in a candidate](lifecycle.md#working-hooks-in-a-candidate), which names retrofit's scope, where the hooks directory sits, what an already-hooked clone owes before the key is pinned, and how the result is verified. Retrofit's candidate is the only one borrowing a hooks directory it does not own, so read that section's scope list rather than assuming another flow's.

### Step 5 — Read the destination's units

Units are derived from what the destination already delivers, never interviewed out of the operator. A repository that ships something has already decided where its boundaries are, in its build files and its delivery path, and asking the question again invites an answer that contradicts the evidence sitting in the tree.

**A unit is what the repository delivers on its own**: separately built, or separately installed by the repository's own delivery path. Neither half alone is the test. A directory with its own build target that nothing delivers is a build artifact of one unit; a directory the delivery path installs that nothing builds separately is content. Name the evidence for each side per candidate unit, from the destination's own files: build targets and workspace members in its manifests, image or artifact names in its container and packaging files, the services its deployment descriptors install, and the entry points its scripts invoke.

**The name comes from the first source that exists**, in this order: the directory the unit occupies, the built artifact or image name, the package name, the repository name. Kebab-case it, and cite which source it came from. A name whose source is not stated is a name from nowhere, and the operator has nothing to judge it against. The operator renames anything, and a rename is the confirmed name from that point on.

**The run and ship facts are not on disk and are never inferred silently.** `run` and `ships` are the two facts each unit's `.unit.json` carries, and no file in the destination states either: a single `main` package is a CLI, a TUI, or a service, and nothing in the tree tells them apart. So the flow names the evidence it found per unit, proposes a pair from it, and the operator confirms or corrects each one. Both the evidence and the confirmation reach the report and the architecture record, so a later reader can tell a fact that was observed from a fact that was accepted.

**Read what grades the pair before proposing it**, because a declaration the check surface refuses is worse than the shape of the tree suggests. Three payload files decide it, and all three are in the candidate already:

- `scripts/libs/quadlet.sh` refuses `ships: quadlet` unless the unit's `deploy/quadlet/` holds a `.build` unit naming an `ImageTag` that every sibling `.container`'s `Image=` resolves to.
- `scripts/libs/detect.sh` holds one `_capability_package_<language>` per language that can ship an executable. A language with none is the gap the paragraph below covers.
- `scripts/run` detects languages only after entering `apps/<unit>/`, so a `run` other than `none` needs a manifest at that path rather than at the root.

Where the confirmed pair and the check surface disagree, the disagreement is a finding for the report, not a value to soften.

**A language with no packaging adapter declares that it ships nothing, and the gap is reported.** `ships.kind` is `none` there, and the report names the unit, its language, and the adapter that does not exist. A declaration guessing at a kind the check surface cannot serve turns `scripts/package` into a command that fails against the unit it was pointed at, which is worse than a declaration that says nothing and a report that says why.

**Domains are drawn only where the destination already draws an internal boundary under one delivery.** A unit that builds and installs as one thing and holds no internal boundary of its own is one unit with no domains, however many directories it has. Drawing a domain the destination does not draw invents a boundary and then moves files to satisfy it.

**A deployable the destination declares but does not build is not a unit.** A third-party image a compose file pulls, a service a descriptor installs from a registry, is somebody else's work the destination happens to run. It lands under the unit that owns the descriptor naming it, and is reported as a deployable the unit model does not describe. That is a finding rather than a stop: the unit model is about what this repository delivers, and saying so out loud is what keeps the omission from reading as an oversight.

**The map is the operator's to confirm.** Present every proposed unit with its name, the source the name came from, the evidence for each half of the delivery test, the proposed run and ship pair with its evidence, any domains and the boundary the destination draws for each, and every declared-but-not-built deployable. A rejected map with no correction stops the flow and is reported: the steps after this one are undecidable without it, and proceeding on a map the operator refused would reconcile a layout against boundaries nobody agreed to.

**This step moves nothing.** Every layout rule is undecidable until units are known, so it produces the map and the confirmed facts and nothing else: no `apps/<name>/` created, no tree relocated, no `.unit.json` written. Layout owns every move, and the architecture record and the unit declarations are written after it, against settled paths.

#### What the decomposition record will say

Written by [Step 7 — Dispose the collisions, write both records, meet the bar](#step-7--dispose-the-collisions-write-both-records-meet-the-bar), which owns every write that waits on settled paths. Its content is decided here, because this step is where the unit map is.

**One record covers the whole decomposition**, not one per unit. This is the deliberate divergence from [generate's Step 7 — Derive the application boundaries](generate.md#step-7--derive-the-application-boundaries), which writes one record per deployable because each one argues a choke point. A retrofit argues nothing of the kind: it decides where boundaries fall, and it *observes* the languages the destination already committed to. A record per unit there would be deliberation theatre, one document each restating a choice nobody made.

**The choke point is stated as observed rather than chosen**, per unit, and *none of these bind* is recorded as the finding it is rather than left out. An absent constraint and an unmeasured one are indistinguishable in a record that reports neither, and the next reader re-runs the whole question to find out which it was.

**Existing architecture records are normalized to the payload's frontmatter**, carrying the destination's own fields across wherever they correspond to one of the payload's. The `generated` field is left empty: filling it would claim the retrofit authored a decision it only relocated, and the retrofit's own authorship is recorded in the record it writes. Records already at the payload's path are normalized the same way; the location is a separate question, settled by [Architecture records live at the root documentation path](lifecycle.md#architecture-records-live-at-the-root-documentation-path), which binds every flow and is where a record under a unit is refused.

**The manifest records unit names and nothing else**, as [Manifest](lifecycle.md#manifest) directs. The run and ship facts live in the unit declarations and the evidence lives in this record; no new field is added for either.

### Step 6 — Reconcile the destination's layout

Step 5 produced the map and moved nothing. This step is where the destination's tree becomes the template's layout, and it has three instruments: **move** a path to where the rules put it, **repair** the configuration a move broke, and **retire** a destination artifact the payload already covers. Retiring is not a fourth thing a retrofit does to be tidy; it is part of what bringing a repository under the template means.

**The complete plan is presented before a single file moves.** Every path, its destination, and which instrument applies, in one list. The operator disposes per path, and a rejection with no correction stops the retrofit exactly as a rejected unit map does: a partial layout is the one state no later run can reason about, since the audit cannot tell a move nobody wanted from a move nobody got to.

**Every root scoped folder the unit map claims moves to its unit.** `libs/`, `tests/`, `scripts/`, `tools/`, `deploy/`, and `assets/` at the root mean repository-wide, and a destination that never had units put everything there by default rather than by decision. This is the only instrument that closes the scope rule, which `scripts/structure` reports `not-applicable` because whether a file sits at its own scope is a judgement about content. The audit cannot make this move and cannot check it; the unit map is what makes it decidable at all.

**Data splits by whether the program writes it.** A destination that runs from its own clone tends to keep one data folder holding both what the program reads and what it saves. What it only reads, including a file the operator edits by hand, moves to the owning `assets/`. A file it writes moves to `apps/<unit>/state/` at the unit's root, which the payload's `.gitignore` excludes as `/apps/*/state/`, with the path the program resolves rewritten and the tracked copy removed. A written file that also holds a record the program will not write again, such as a finished season, can keep that record as a read-only snapshot under `assets/` that the program falls back to, so neither a fresh clone nor a harness starts from nothing; that fallback is new code rather than a moved path, so the plan proposes it and the flow writes it only once the operator confirms. A harness that saved a backup into the tree follows the file it backs up. The plan names each data file as one or the other, since only reading the code that opens it can tell them apart. The candidate never touches the operator's clone, so the live copy of each moved file is the operator's to carry: the report tells them to move it out of its tracked path before pulling the merge — copy it into `apps/<unit>/state/`, then `git restore` the old path — because the pull refuses to remove a tracked file they changed and silently removes one they did not.

**Documentation stays repository-wide**, even where there is exactly one unit and every other scoped folder moved under it. `scripts/adr-index` rewrites the index from a root path, so a `docs/` that followed its unit takes the records with it and out of the index, which is the failure [Architecture records live at the root documentation path](lifecycle.md#architecture-records-live-at-the-root-documentation-path) names. The records migration to that path is performed here, with the moves, rather than left to [Step 7 — Dispose the collisions, write both records, meet the bar](#step-7--dispose-the-collisions-write-both-records-meet-the-bar), which writes the new record into the path these moves have already cleared.

**A readme below the root is documentation and moves with it.** It lands in the nearest owning `docs/` under a name describing what it is about, because a `README.md` inside a documentation folder is a filename that tells a reader nothing and collides with the next one that moves. The repository's own root readme is not this: it stays at the root, where it is an addon the destination already holds.

**A move that empties a directory can leave it standing in the operator's own clone.** Two facts hide it and neither is the other's reason. Git tracks no directories, so nothing in the candidate's diff names the emptied path and `scripts/structure` cannot raise it either — it enumerates with `git ls-files`, which is the enumeration it should use. And the residue is never in the candidate at all: step 2 checks that worktree out fresh from `origin/<default-branch>`, so a `__pycache__` or a build directory sitting in the operator's clone has no copy there. After the merge the clone drops the tracked file and keeps the residue, at the path the rules just emptied, ignored and so unseen by `git status` too.

Read it from the clone, then, which is the only place it exists: `git -C <clone> status --ignored --porcelain -- <each path the plan empties>`, read-only and at this step, while the tracked file is still there to name the directory. Report every directory a move empties and what the operator will find still standing in it, and remove none of it — a file the destination's own ignore rules cover is theirs to delete.

**The flow writes no `.structure-allow` entry.** Across the reference repositories nothing was genuinely immovable, so an entry written by the flow would almost always be a move it declined to make, recorded as permission nobody asked for. A path that cannot be moved is reported with the reason; the operator may write the entry themselves afterwards, outside the flow, which keeps the allowlist a record of human decisions rather than of the flow's difficulties.

**Configuration a move broke, the flow repairs, in the same change.** A test path, a build target, a workflow's working directory, a lint or coverage root: these are broken by the move and by nothing else, and the flow is the only party holding the mapping from old path to new. A path reference that is **exactly** a path the flow moved is rewritten. Prose describing the old structure is reported and left alone, because a sentence about where things live is a claim a rewrite cannot make true and a reader has to re-make.

**An artifact is retired only when the payload covers its whole role**, judged by what the thing does in the flow it belongs to rather than by matching features off a list. [Retiring a covered gate script](lifecycle.md#retiring-a-covered-gate-script) governs the gate scripts and this step follows it for every artifact: fully covered is retired, with its callers repointed and `generation.superseded` recording it; partially covered survives as a reported conflict naming the duplicated parts specifically. The flow never leaves a destination with a capability it had before the retrofit and lacks after.

**Two collisions the overlay skipped are settled here**, and both are files a destination always has.

The ignore file is replaced outright, at the payload's mode as well as with the payload's content — [The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content), and this is the path it names, because a destination always has one and rewriting it in place keeps whatever bit it carried. A merged ignore file is the state where nobody can say which rules the repository actually promises, and the payload's is a guarantee in the same sense the automation directory is. Destination rules the payload does not cover are **reported rather than re-added**, with the consequence stated plainly: un-ignoring a generated directory can make the candidate fail its own check surface, and where it does, the flow stops and the operator decides which rule survives. That stop is the point of reporting rather than re-adding, since a rule quietly carried across hides exactly this.

**A rule the operator restores gets no [overridden path](lifecycle.md#overridden-paths) entry**, under the rule that a path the flows replace outright can never be one: the entry would make an update skip the ignore file and drop every later payload change to it on the strength of a collision nobody had. The restored rule surfaces as a collision at the next update instead, which is where it is weighed again. Report it, and report that the ignore file is no longer byte-identical to the payload's.

The instruction file is merged, and it is re-established as one of the last steps of the whole retrofit rather than here. `CLAUDE.md` is what the destination's next agent session reads, and everything this run did — the units, the moves, the retirements, the reported rules nobody re-added — is what that session needs. Written now it describes the tree as it stood before the record and the collisions were settled, which makes it a bootstrap for work already done. So this step takes the merge as far as the layout facts and leaves the file's re-establishment to the end.

**What this step promises.** For a checkable destination, `scripts/structure` passes on zero allowlist entries after it. Layout reconciliation is cheap and the check bar is expensive, and they fail for unrelated reasons, so a green audit here says nothing about whether the destination's own checks pass; that is the later step's to report.

### Step 7 — Dispose the collisions, write both records, meet the bar

Nothing here reaches the network. This step settles everything that has to be true before the flow is allowed to publish, in the order that makes each part decidable: the collisions, then the two records, then the tool declaration, then the bar measured on the result.

**Two records are written here and both are this step's**: the decomposition architecture record, whose content [What the decomposition record will say](#what-the-decomposition-record-will-say) decided at step 5, and the manifest. They are written together because both wait on the same thing — step 6's moves settling where every path is — and because a step owning one of them and deferring the other is how the deferred one stops being written at all.

**Write the decomposition record first, at the root documentation path**, under [Architecture records live at the root documentation path](lifecycle.md#architecture-records-live-at-the-root-documentation-path). It carries the confirmed unit map: each unit's name and the source that name came from, the evidence for each half of the delivery test, the run and ship pair with its evidence and whether it was observed or accepted, the domains and the boundary the destination draws for each, the choke point observed per unit with *none of these bind* recorded where none does, and every declared-but-not-built deployable.

**Every path inside it is repository-relative**, because the record is: it lands at the root, it covers every unit at once, and a reader of `docs/adrs/` has no unit to resolve a bare `src/` against. A path written as the unit sees it resolves nowhere from where the record sits, which is the mistake the record's own shape invites rather than one a run happens to make.

Then the manifest.

**Every remaining collision is proposed and disposed, per file.** Diff the destination's version against the payload's, state what each one says, and let the operator pick payload, destination, or a merge. A disposition the payload wins writes the payload's mode too, under [The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content). No path-matching rule can stand in for this: across the reference repositories one payload path drew four different dispositions, and nothing about the path predicted which.

**Where this run invalidated the destination's own stated reason, propose the payload's version and name the step that invalidated it.** A document explaining that scripts live at the root is no longer describing the repository once step 6 moved them. The proposal is still the operator's to refuse, and naming the invalidating step is what lets them refuse it on the merits rather than on the flow's say-so.

**A chosen destination version at a managed path is an [overridden path](lifecycle.md#overridden-paths)**, recorded with the reason the destination's version won, so the next update does not re-raise a collision settled here. A destination version that wins at a product path is already the destination's by ownership: report it with its reason and record nothing, which is what preflight requires of the record this step writes.

The array is the payload's default, and that is only true because the moves came first: layout lifted foreign content out of every managed pattern, [the automation directory](lifecycle.md#the-automation-directory-is-replaced-not-reconciled) was replaced whole, and the ignore file was replaced outright, so every remaining destination file falls on unmatched and [Ownership](lifecycle.md#ownership) resolves it to product. **A destination path still matching a managed pattern is a layout failure to fix in step 6**, never an ownership exception written here.

**Four things the record does not carry, all for one reason: a field an update can read is a field an update can branch on, and convergence is the point.** No field records which flow ran — provenance is the pull request. No list of layout moves — a moved file is product-owned on both sides, so it never enters an update's comparison, and the list would go stale at the first rename. No run or ship facts beside the unit names, as [Manifest](lifecycle.md#manifest) directs: those live in each unit's own declaration. And no destination-specific ownership entry.

**The tool declaration adds only what is missing**, at the template's floors, keeping any specifier the destination already declares. [Tools the first manifest must declare](lifecycle.md#tools-the-first-manifest-must-declare) is the list, per language. Tool lines and every configuration boundary that list names, and nothing else: making moved code build, import or resolve is configuration a move broke and belongs to step 6. Writing the boundary here is what lets the pass below run at all, for the reason the guard below gives. A destination that already declares its own settings keeps them: ruff takes the closest configuration and ignores every parent, so the declaration only ever supplies the boundary a destination was missing. The list names one boundary, the `tool.ruff` table, so a destination carrying JavaScript or Kotlin brings tools that walk upward with none written for them, and the guard below is what covers that until one is. This file is not a payload path, so it is not an overridden path either; its ownership is product, unlisted and unrecorded. Report each line added. Lockfiles the environment step produced are kept, since a resolved environment nobody can reproduce is what step 4 refused to accept. A rival tool is retired only where another fills its exact role in the flow, under [Retiring a covered gate script](lifecycle.md#retiring-a-covered-gate-script). The operator may decline the declaration outright, and the report then says which capability the bar cannot reach and why.

**`.github/dependabot.yml` gains every entry the destination earns**, as [Dependabot entries follow the manifests present](lifecycle.md#dependabot-entries-follow-the-manifests-present) directs. It is derived here rather than with the overlay in step 3 because step 6 is what settles where the manifests sit: a module the moves lifted into `apps/<name>/` needs an entry naming that directory, and one derived before the moves would name the path the file no longer occupies. A retrofit is where this matters most — a destination that predates the template is the case most likely to hold a manifest somewhere other than the root.

**Check what this step and step 6 wrote against this list before the bar runs.** Each item is drift a review of a retrofit's authored surface has found:

- The decomposition record carries `scope: [global]`, an `## Alternatives Considered` section covering the run fact, the ship fact and the unit split the operator rejected, and one statement per fact of where it came from: observed, forced by the check surface, or confirmed by the operator.
- Each rationale this flow writes has one home, the unit's `CLAUDE.md`; the root `CLAUDE.md` and the root manifest point to it rather than restating it.
- A table of the destination's harnesses quotes each harness's literal summary line, so an expected result can be checked against a run by eye.
- A manifest comment says what its setting does, never how the retrofit arrived at it.
- The pull-request body names only paths that are in the diff.

**The candidate carries no untracked file when the bar is measured.** Read `git status --porcelain` for `??` entries *before* staging and before the first run, rather than after a failure. Staging is what [Running the destination's checks](lifecycle.md#running-the-destinations-checks) directs ahead of the run and it turns every `??` into an `A`, so the one reading that names the file is only available beforehand. The check surface sweeps untracked files through the commit hooks, so a formatter rewrites generated build output, the run exits non-zero from outside its own Result table, and the second run passes having already fixed what it found — which is what makes a re-run the worst way to diagnose it. Step 6's ignore-file replacement is the usual cause: a directory the destination ignored and the payload does not is untracked from the moment step 4 builds the environment. Dispose it there, as that step's ignore rule directs, rather than here.

**The destination's own autofix runs before the bar, and nothing else does.** `scripts/fix` is the write half of the surface the bar reads — each linter's own fix pass, then the formatter, for every language present — so what it rewrites is by construction what the bar was about to demand. Run it in the candidate after the tool declaration, which is what puts those tools on the resolved environment's path. `--unsafe-fixes` and its equivalents are never passed and no finding is fixed by hand here: that is the line between a rewrite the tool stands behind and a judgment about code this flow does not own, and a flag crossing it turns every later retrofit into one that edits a destination's logic unattended. Run it again only while a pass still changes something, and at most twice: the order is lint then format, so a layout change can expose a finding the linter never saw, and a finding a second pass does not clear is destination debt under the unmet-bar rule below. **Its exit status is not the bar.** `scripts/fix` exits non-zero whenever findings remain, which is the ordinary case on a destination that has never run these tools, and the bar is the separate run below. Where the payload ships no `scripts/fix` — a target commit predating it, or a collision the operator settled the destination's way — report the bar as measured without a pass, the way the declared facts below are reported written and unexecuted.

**The pass is refused where a tool resolves its configuration from outside the candidate.** Every command `scripts/fix` runs takes the candidate as its working directory, and a tool that discovers settings by walking upward finds *this* repository's configuration instead, because the candidate sits under `tmp/` and a gitignored directory is no configuration boundary. Read under those settings the bar measures the wrong rule set; written under them the pass rewrites a destination's files to this repository's style and applies fixes for rules that destination switched off, which is the one outcome this whole paragraph exists to prevent. So before the pass, read each language's resolved settings path — `ruff check --show-settings .` prints it as `Settings path:`, and each tool has its equivalent — and run the pass only where every path falls inside the candidate. A path that cannot be read counts as outside the candidate, because the skip is only fail-safe where the read succeeds. Where any tool fails that test, skip the pass entirely, report the tool and the path it resolved or that no path could be read for it, and measure the bar as it stood, saying in the report which settings it was measured under: a stop costs a re-run, and a destination reformatted under the wrong rules costs the operator their own tree. Verify rather than assume even though the tool declaration above anchors the languages it names, because an anchor nobody reads is the same silent failure one commit later.

**Both proofs are measured before the pass, and this flow's own work is committed before it.** [Reviewing the pull request](reporting.md#reviewing-the-pull-request) reads the copy proof and the rename-purity proof from the index rather than from a commit range, so both are measured here, at the end of this step while nothing is committed yet, and their counts are carried into step 9 rather than re-measured there. Measure both with one command, from this repository, and keep its JSON for the report:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py proofs --template-repo . \
  --target "<commit>" --subtree apps/github-repository-template/src/base-repo \
  --candidate "<candidate>" --base "<base-commit>"
```

`copy` carries the identical count over the total, each payload path that `differing` names as `merged` (the destination held it) or `extended` (the overlay wrote it and this flow edited it) with whether the destination's ignore rules exclude it, and `missing`, every payload path absent from disk. `rename_purity` carries each move with its similarity, whether it is byte-identical, and its line delta. `authored` is every staged path neither proof covers, and `deleted` every staged deletion — a move edited past git's rename threshold, as normalizing a record's frontmatter can do, is one of these, with its new path under `authored` rather than a move under `rename_purity`. `candidate.pre_commit_config` records whether the candidate carries a `.pre-commit-config.yaml`, which is what the report's Hooks line reads. It refuses an empty index and a candidate already past `<base-commit>`, which are the two moments the proofs would report a clean count over nothing. Then commit everything this flow wrote, run the pass, and commit the pass by itself. That order is forced from both ends: a commit is the only thing that separates the rewrite from the edits this flow authored, and it cannot separate them while those edits are still only staged — while measuring the proofs after any of it is committed empties the `--cached` read they both depend on.

Write every commit message this flow makes to a file beside the candidate and pass it with `git commit -F <file>`: a message passed by process substitution has landed empty. Where the first commit fails because the `adr-index` hook rewrote `docs/adrs/index.md`, stage that file again and repeat the commit; the hook regenerates the index the decomposition record changed and exits non-zero for it, which is expected rather than a finding.

**The formatter is the part that costs something.** It meets a layout somebody chose and rewrites nearly every line of it, which is the second thing the separate commit above is worth having for: the operator reverts that alone without losing the retrofit. Report the finding count before, the count after, every file rewritten, and — where the destination's test capability collects anything — that capability's result on both sides of the pass. Where it collects nothing, say so: the rewrite is then the tool's own word and this flow has not checked it against this codebase. A pass that cleared everything still reports all of it, because a retrofit that now lands unattended leaves the report as the only record of the rewrite.

**A payload path the pass rewrites is a payload defect**, and reporting it is not a disposition. The payload ships files its own gate formats, so a rewrite there means the template shipped one it would reject. **Revert the rewrite at that path before committing the pass**, then report the path and the rule or formatter that reached it. The copy proof is already measured by the time the pass runs, so it never sees the rewrite — which is exactly the problem: left in, the rewrite rides into the published diff as a copy the reported count says is byte-identical, and nothing downstream reads it again. Reverting is what keeps that count true of the branch, and it leaves the defect where it belongs, in this repository.

**The bar is the destination's own check surface passing on the candidate**, run and read by [Running the destination's checks](lifecycle.md#running-the-destinations-checks). A `FAIL` blocks and so does an `unavailable`, for the reason that section already gives: a check whose runner was missing measured nothing, and a report calling it a pass claims a guarantee the run does not hold. A `not-applicable` does not block, because a language that is not present has nothing to prove. Stage with `git add -A` immediately before every run, re-runs included: `scripts/structure` enumerates the index, so a `.unit.json` written and not staged fails the unit-declaration rule as missing.

**The facts step 5 confirmed are executed here, not merely written.** Once each `.unit.json` is on disk, run `scripts/package <unit>` once per unit, and `scripts/run <unit>` once per unit with `CI_DRY_RUN` set, and report both results. `CI_DRY_RUN` is the one variable both read, so setting it for the pair would dry-run the package too and prove nothing about the descriptor. Neither command is in the check surface — packaging is not a check and a run is a foreground process — so a declaration that contradicts the tree passes every capability in the bar and fails the first time somebody uses it: a `ships` kind whose descriptor is half-present fails only under `scripts/package`, and a `longlived` unit whose manifest sits outside the unit directory exits zero having started nothing, because `scripts/run` detects languages after entering `apps/<unit>/`. Read the output rather than the status for that second one: `scripts/run` says `No project manifest found here` and exits zero, so a unit that starts nothing is a pass by status and a failure only to a reader. Package for real and run dry: packaging a quadlet unit builds nothing anyway, and a real run of a longlived unit does not return. A failure here is a wrong fact or a missing descriptor, so fix it and re-read it with the operator where the fix changes a fact they confirmed. Both commands arrive with step 3's overlay; where the payload ships neither, report that the facts are written and unexecuted. This is not a check capability and takes no result state.

**An unmet bar is a failed retrofit and it stops before the pull request**, naming the capability that could not pass and why. No partial retrofit is published with the gap written into the description, and the fix does not ride along in the candidate, where it would arrive as this flow's judgment about code this flow does not own — the same reason the pass above is bounded to what a tool will do on its own.

**The rest of the unmet-bar path is in [`retrofit-unmet-bar.md`](retrofit-unmet-bar.md)**: preparing the destination's own fix, verifying it, and the gate that offers it. Read it when the bar is unmet; a run that meets the bar never needs it.

**A met bar is followed by the review of the authored surface, here and before step 8 asks anything.** [Reviewing the pull request](reporting.md#reviewing-the-pull-request) names the surface and the three axes. Its fixed point is `origin/<default-branch>` at the commit step 2 fetched, which is the base the pull request will diff against, so the review reads the candidate branch's committed head exactly as the pull request will show it. **Grepping the destination for every path this flow deleted or renamed — the proofs' `deleted` and each move's `from` — is not optional here**: it is the single highest-value line of the review, because a live reference in destination-owned prose is exactly what no check reads. Commit the corrections as their own commit, with the message written to a file as above, then stage and run the bar again over that head, since a correction is an edit the bar has not read; repeat until every finding is corrected or recorded as incorrectly identified. The order is the point: a review that runs once the pull request is open can no longer stop anything, and a correction pushed after it moves the head the gate, the checks and the merge offer were all read against. Step 8's question is asked about this head, and step 9 publishes it unchanged.

### Step 8 — The hosted-write gate

A **hosted write** is a change to the destination's state on the host that no pull request can carry: a repository setting, a branch rename, a label, a ruleset. Every one the retrofit makes happens here, at one gate, immediately before publishing and only after step 7's bar passed and its review's corrections were committed. The placement is the point: a destination whose bar could not be met has had none of its state on the host changed, so re-running after the debt is cleared costs nothing and undoes nothing. That holds through step 7's unmet-bar path, which offers a push and a pull request: those are remote actions gated under [Remote action gates](lifecycle.md#remote-action-gates), and a branch and a pull request are exactly what this definition excludes.

This is a deliberate divergence from [generate](generate.md), which reaches [Remote action gates](lifecycle.md#remote-action-gates) early because the repository has to exist before the map and the tracker have anywhere to live. A retrofit has no such forcing: the repository exists, the tracker is the destination's own, and nothing before this step needs the host.

**The gate creates nothing.** It confirms the identity preflight already proved against the origin, and it authorizes each write by naming the exact command that performs it. **No write is performed that the gate did not list**, which is the rule the whole step is built to keep: a write discovered mid-run is a write nobody authorized.

**Generate's ruleset probe is not performed.** It puts a throwaway commit on the live default branch and pushes it directly, and [Step 5 — Configure the repository settings](generate.md#step-5--configure-the-repository-settings) says what happens where the branch does not reject it: the commit becomes the default-branch tip and only a force-push removes it. Against an empty repository that is a contained risk. Against a repository with other people's clones fetching it, it is not. So nothing is pushed at the default branch to prove enforcement here, and the existence read is not what stands in for it: step 9's pull request supplies the proof for free, under [A written ruleset is proved satisfiable, not merely present](lifecycle.md#a-written-ruleset-is-proved-satisfiable-not-merely-present). Enforcement is therefore **not yet proven at this gate** rather than unproven outright, and the report carries step 9's reading rather than this step's.

Five writes, in this order, the last of them conditional.

Read the gate's question in one call and perform what it approved in a second; the rename under 2 is the one write neither touches, because it stays a step the flow runs itself:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py hosted read --repository <owner>/<repository>

python3 apps/repo-builder/src/scripts/retrofit.py hosted apply \
  --repository <owner>/<repository> \
  --write-log <absolute path to this repository>/tmp/<repository-name>.writes.json \
  --approve <write> [--approve <write> ...] \
  [--label <name> ...] [--keep-case-variants] \
  [--ruleset <body.json> [--replace-ruleset <id>]]
```

`read` reports `visibility`, `admin`, `default_branch`, `merge_settings` (REST's four field names), `labels`, `dependabot` (`alerts`, `security_updates`), `push_protection`, `rulesets` and `runner` (the `dev-<repository>` runner's status). A reading the host refused carries `refused` in its place: `not offered` for the upgrade message, `permissions gap` for any other 403.

`apply` takes `--approve` once per write the gate approved — `merge-settings`, `labels`, `dependabot-alerts`, `security-updates`, `push-protection`, `ruleset`, `runner-variable` — performs them in that order and nothing else, and reports:

- `writes` — each approved write's outcome: `done`, `already set`, `logged` (performed by an earlier run, so not repeated), `not offered`, `permissions gap` or `refused`; `labels` reports `created`, `renamed` and `skipped` per label instead, and `runner-variable` reports `not offered` when either of its two conditions fails
- `reasons` — why, for each write that was `not offered` for a reason other than the plan, or refused other than as `not offered`: the runner variable's failed condition, or the host's refusal text
- `write_log` — its path and every entry: `{write, before, after, reverse_command}`, one per write performed, where `reverse_command` is the argument list that puts `before` back
- `findings` — every refusal other than `not offered`

The write log is a sibling of the candidate, like the resume record and for its reason. `--label` names the labels in force, given under 3; `--keep-case-variants` is for a destination whose own `triage-labels.md` is in force. `--ruleset` is the body composed under 4, and `--replace-ruleset` names the destination's own ruleset it repairs in place, whose before-state is saved beside the log because restoring it needs the whole document.

**1. Merge settings, in one call.** `allow_merge_commit`, `allow_squash_merge`, `allow_rebase_merge`, and `delete_branch_on_merge` go in a single `PATCH`, for the reason generate's step 5 gives: sent separately the second call can be refused after the first has landed, and a half-applied merge policy is worse than one never started. State the destination's four current values out loud before overwriting them, since this is somebody's deliberate choice being replaced. `merge_settings` in the snapshot is that reading, taken from the same endpoint the write goes to so the two name the fields the same way. The other route to these four is `gh repo view --json mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed,deleteBranchOnMerge`, and its names are not interchangeable with these: [Step 5 — Configure the repository settings](generate.md#step-5--configure-the-repository-settings) has the rule, which is that the wrong field set returns `null` for every field rather than erroring. All four reading `null` here is the signature of the wrong spelling, not of a destination with every merge method disabled — GitHub does not permit that state. Declinable, and a refusal is recorded in `generation.features` with its reason.

**2. The default-branch rename.** **Declining is a hard stop.** The payload's workflows pin the branch name literally and [the automation directory](lifecycle.md#the-automation-directory-is-replaced-not-reconciled) is replaced whole, so a destination left on the old name receives CI that never fires: green by absence, which is the one failure mode the check surface cannot report. The bar cannot be met that way, so there is nothing to publish.

**An open pull request whose head is the branch being renamed is a hard stop before any write at all.** The host closes such a pull request rather than retargeting it, and the head ref is gone afterwards. Enumerate **by head ref as well as by base ref** — a list filtered on base alone misses exactly these. The stop names the real remedies and no others: merge it, close it deliberately, or copy the branch and open a fresh pull request, where the commits survive and the review conversation does not. Retargeting is not among them, because a base can be changed and a head cannot.

A ruleset naming the old branch literally is **repaired in place**, rewriting the name to the new one. Switching it to a dynamic condition such as the default-branch target is rejected: it substitutes a rule the owner did not write for the one they did, under cover of fixing it.

Every existing clone needs repairing too, and the gate presents the four commands rather than leaving each collaborator to work them out:

```bash
git branch -m <old> <new>
git fetch origin
git branch -u "origin/<new>" <new>
git remote set-head origin -a
```

**3. Labels**, with the case-insensitive guard and the payload-spelling rename that [Remote action gates](lifecycle.md#remote-action-gates) already specifies for a generate: a label the destination carries under a different case is renamed to the payload's spelling rather than created beside it, and the rename is its own line, because label search is case-sensitive and anything pinned to the old string stops matching. List `code-reviewed` among them where the destination has no such label: step 9 applies it to the pull request, and the host creates a label it is asked to apply that does not exist, so leaving it off this list is a write the gate never named.

**4. Security settings and the branch ruleset** — dependency alerts, security updates, push protection, and the ruleset generate creates. Declinable and recorded. Push protection refused on a private destination on a free plan is reported rather than failed, exactly as `scripts/repo-settings check` already separates the two.

The ruleset's required checks are named by their check runs, not by their workflow job ids — the payload's `ci.yml` has job id `ci` and `name: CI`, so `CI` is the context and `ci` is a context nothing reports. [Step 5 — Configure the repository settings](generate.md#step-5--configure-the-repository-settings) carries the rule and the full set of spellings the payload's workflows report; this gate writes the same ones. A retrofit is where getting it wrong costs most: the destination's default branch carries other people's work, and a context nothing reports never fails, so the rule reads back `active`, every settings check passes, and every pull request stops being mergeable with nothing naming the cause. The probe that would have caught it at this gate is not performed here, so the misspelling survives every reading this step makes; step 9's `mergeable`/`mergeStateStatus` pair is what catches it, which is why enforcement is reported **not yet proven at this gate** rather than proven by anything written above.

A ruleset the destination already had is the same hazard pointed backwards. [The automation directory](lifecycle.md#the-automation-directory-is-replaced-not-reconciled) is replaced whole, so the destination's own workflows are gone and any context its ruleset required by their names is now permanently pending. Read the existing ruleset's required contexts before writing, and name at the gate every one the payload's workflows do not report — like the branch name above, it is repaired in place by rewriting it to the contexts that now exist, and unlike the branch name it is invisible until somebody opens a pull request.

**5. The runner variable**, and only where both conditions in [The runner variable is set only where it is safe and answerable](lifecycle.md#the-runner-variable-is-set-only-where-it-is-safe-and-answerable) hold: the destination reads `PRIVATE` and a `dev-<repository>` runner reads `online`. Read both at this gate rather than trusting what an earlier step saw, and where either fails, say which and offer nothing — a public destination is not a decision the operator gets to make here. Declinable, and the only write in this step whose proof comes later: step 9's pull request is what supplies the green run, and `runner_name` on its jobs is what says the variable took.

**A refusal carrying the host's upgrade message means the feature is not offered**, so there is nothing to repair and `not offered for the plan` is the whole finding. The same refusal **without** that message is a permissions gap, and that is a finding at the gate rather than a line in the report: it says the credential this run holds cannot do what the gate just authorized.

**Every post-write verification polls rather than reading once.** The rename, the dependency summary, and the protection endpoints were all observed returning the pre-write state immediately after a write the host had accepted. A single read is how a write that succeeded gets reported as a write that did nothing.

**There is no undo mechanism, so the report carries the before-state of every hosted write** and lists the writes in **two separately named sections**: the reversible ones, each with the exact command that reverses it, and the irreversible ones, each with its cost. Never one section. A single copy-pasteable block of commands reads as though the whole gate can be walked back, and a closed pull request's review conversation cannot.

### Step 9 — Publish, prove, and offer the merge

**The head is the candidate's own branch.** Step 2 created it, every step since wrote into it, and nothing is re-materialized at publish time: a tree rebuilt here is a tree nobody checked.

**Every push goes to the candidate's feature branch, with the destination's hooks running.** The push guard the payload installs allows a feature branch and refuses the default branch, so nothing here needs `--no-verify`: the bypass [generate](generate.md#step-3--materialize-the-candidate) confirms for its own bootstrap commit is an exception for pushing straight to the default branch of an empty repository, and a retrofit never does that. A push a hook refuses is a finding to report, never a push to repeat with the hook turned off.

**The base is the default branch**, which step 8's rename has already made correct. A base rename retargets an open pull request, and the hazard that step named — the host closing rather than retargeting — applies to a renamed *head*, which this branch never is.

**The body is always explicit, and it is filled against the pull-request template this same diff introduces.** The host renders a template from the base branch and an explicit body suppresses it entirely, so a body written freehand is the repository's first pull request ignoring the rule the same pull request is installing. Fill the payload template's own sections. [Generate](generate.md#step-11--publish-the-candidate) states the reason for an explicit body in general terms.

The body carries what a reviewer of *this* pull request needs: the per-path dispositions, the layout moves, the per-write reverse commands from step 8, the workflows the pull-request event never exercised, and what the review of the authored surface found. It does not carry the session report. That is written for the operator who ran this flow, in the shape [Final report](reporting.md#final-report) fixes, and pasting it into a description aimed at the destination's collaborators serves neither reader.

**Prove it twice before anything merges.** [Reviewing the pull request](reporting.md#reviewing-the-pull-request) runs the copy proof over the overlay set, every payload path written because it was absent, and a retrofit runs the rename-purity proof beside it over the moved set. Both were measured at the end of step 7, before the autofix pass and before anything was committed, under [the autofix pass's ordering](#step-7--dispose-the-collisions-write-both-records-meet-the-bar); report those counts here rather than taking them again, because the index this step reads no longer holds what they read. What is left after the two is the authored surface, and it was reviewed at the end of step 7, before the gate, so this step carries that review's findings rather than taking it again. Overridden paths are in neither proof, never having been written.

**Sign the review off once the pull request is open**, because the label and the comment need a pull request to land on. Where every finding was corrected or recorded as incorrectly identified, apply the `code-reviewed` label and post one comment stating the axes that ran and what they found, whose last line is `Reviewed-Head: <full 40-character sha>` naming the head the pull request opened at, which is the head step 7 reviewed. Write both through the REST routes in [Writing to the pull request](reporting.md#writing-to-the-pull-request) and read both back. Where a finding stands unresolved there is no sign-off to write, and the report says so.

**Account for the file list as well as the content**, by [Step 10 — Verify the file list](generate.md#step-10--verify-the-file-list). A retrofit's account differs from a generate's in three places, and each is an expected difference rather than a defect to explain: the payload's placeholder unit is absent because preflight never put it in the absent set, under [Step 3 — Overlay the payload's absent paths](#step-3--overlay-the-payloads-absent-paths), every overridden path is absent because it was never written, and the destination's own tracked files outnumber the payload's and belong to no payload path at all. Derive the numbers from the two commands that step names rather than by hand — absence has no runner, and a count assembled by reading is a count nobody can reproduce at the next update.

**Every payload workflow except the release workflow runs on this pull request**, so it is a real exercise of the whole gating set rather than a sample. Read the check suites as [Step 12 — Verify the published repository](generate.md#step-12--verify-the-published-repository) reads them, keeping the same distinction between a failing run and no run dispatched and the same caveat about host status, then **state which workflows the pull-request event never ran**, so the green result is read for what it covers. Wait on the checks with `gh pr checks <n> --watch` run as a background command, never a foreground `sleep` between reads, which the session refuses.

**A destination that meters Actions minutes stops every workflow before it starts.** A private repository on a plan that bills them fails each required check within seconds, carrying the host's billing message, with no job dispatched. That is a condition of the destination: not a defect in the candidate, not a permissions gap, and not something a retry clears. Report it as workflows the event never ran, say that the whole gating set is therefore unexercised, and do not read the red as a failing check.

**With the checks green, read `mergeable` and `mergeStateStatus` as a pair**, under [A written ruleset is proved satisfiable, not merely present](lifecycle.md#a-written-ruleset-is-proved-satisfiable-not-merely-present). This is the reading step 8 deferred: it proves the ruleset that gate wrote both binds and can be satisfied, on the pull request this flow was opening anyway. `MERGEABLE`/`BLOCKED` here means the merge offered below can never be taken, so read it before offering rather than discovering it in the poll — and it is a finding against the ruleset, not against the candidate, whose checks are green.

**Then, optionally, the merge, at a second gate.** The first gate cannot carry it: the checks did not exist yet when it ran, and authorizing a merge against checks nobody has seen authorizes nothing. Poll until every required check is green, then offer exactly the merge and nothing beside it. Where no check can run at all, for the billing reason above, say so in place of the poll: there is no green coming, and an offer made with the gap named is better than a poll that cannot end. **Declining is the default**, and it leaves an open pull request for the destination's own people to review and merge their own way. Taking it merges, then reads the default branch's check suites and fills the report's existing line, because a green pull request ran against a merge commit and the branch afterwards is a different commit with a different trigger. Taking it also owes the destination clone a working hook surface, under [Working hooks in the destination after a merge](lifecycle.md#working-hooks-in-the-destination-after-a-merge): this diff is what gave that clone a `.pre-commit-config.yaml` and an instruction file promising the hooks run, and the candidate that had them is about to be removed.

The offer exists because with step 7's bar the pull request only ever opens fully green, and merging is the only thing that verifies the default branch. It is an offer and not a step because the premise [Reviewing the pull request](reporting.md#reviewing-the-pull-request) rests on is false here: most of what it skips review for is already-reviewed template content, and a retrofit's authored surface is repaired configuration, rewritten path references, a merged instruction file and a retired gate script — edits to the destination's own code that none of the destination's own people have reviewed. A destination also has collaborators with branches in flight that every rename conflicts with, and they are the ones who know when that lands well.

## The retrofit adopts no addon

A retrofit takes no [repository addon](addon-adoption.md), and needs no mechanism to avoid taking one. What preflight reports in `addons_present` is a finding: the addon-shaped paths the destination already holds, named so the operator can see what [adopt](adopt.md) would have offered against a destination that has answered most of it already.

Nothing has to be taught to leave those files alone. The root allowlist holds the addon filenames by name, under the rule that they are additions by occasion, so a destination's own readme, licence or changelog is already permitted where it sits and the structure audit does not flag it. And an addon is not a payload path: addons live in a sibling tree rather than under the payload subtree, so a destination's readme never reaches the collision list in the first place and step 3 never writes over one.

The record the retrofit writes carries no addon entry, for the same reason [generate](generate.md)'s does not: the manifest records what the flow landed, and this flow landed none. A destination that wants one runs adopt afterwards, against the repository that now exists, and that run is what writes the entry.

## Report additions

**Run the renderer, then fill its slots.** It writes the shape [Final report](reporting.md#final-report) fixes with the lines below in place, every count, setting, hosted write and undo command, check result and cleanup outcome read from the JSON the other subcommands printed, each saved to a file as it ran:

```bash
python3 apps/repo-builder/src/scripts/retrofit.py report \
  --repository <owner>/<repository> \
  --output <absolute path to this repository>/tmp/<repository-name>-report.md \
  --proofs <proofs JSON> \
  --summary "scripts/check" <its scripts/summarize output> \
  [--hooks <hooks JSON>] [--sweep <sweep JSON>] \
  [--hosted-read <hosted read JSON>] [--hosted-apply <hosted apply JSON>] \
  [--pull-request <URL>] [--stopped "<what remains>"] [--resumed]
```

Leave out the JSON of a subcommand that did not run: `--hooks` where the merge was declined, `--sweep` and both `--hosted-*` on a run stopped at the bar. It reports `path` and `slots`, the judgement lines left as `[[FILL: <what goes here>]]`: the unit map, the review findings, and each decision. Fill every slot from what this run decided, delete the ones marked optional that do not apply, and change no rendered line; a rendered line that reads wrong is a defect in the JSON it came from. The finished report holds no `[[FILL:`.

A retrofit fills the shape [Final report](reporting.md#final-report) fixes, and adds the lines below to it. They live here rather than there because every one of them is a retrofit's alone, and a generate, an update and an adopt would each read them only to establish that none applies.

Three of the shape's own lines also read differently here. The **Code review** line does not read `skipped`: a retrofit's authored surface is reviewed, as [Reviewing the pull request](reporting.md#reviewing-the-pull-request) names it the one flow that is, so the line carries the axes that ran, the findings corrected, any recorded as incorrectly identified, and the `Reviewed-Head:` sha step 9 signed off, or that no sign-off was written and why. The choke-point and Wayfinding lines under **Application boundaries** are absent: a retrofit observes languages the destination already committed to rather than choosing one, and derives units from that destination's own evidence rather than wayfinding them. A unit map the operator rejected with no correction is reported as the proposal and the rejection, with **Pending action** carrying the correction the flow is stopped for.

Added under **Reconciliation**:

- Layout plan: <old path> -> <new path>: moved | corrected by the operator to <path> | declined | none
- Unmovable: <path>: <why it could not move>; no allowlist entry written | none
- Data split: <file>: read, to `assets/` | written, to `state/`, and the operator copies their live file there and restores the old path before pulling the merge | written, to `state/`, with its finished record snapshotted to `assets/` and a fallback the operator confirmed, and the operator copies their live file there and restores the old path before pulling the merge | none
- References repaired: <file>: <the moved path rewritten> | none
- References reported, not rewritten: <file>: <the prose describing the old structure> | none
- Ignore rules the payload does not cover: <rule>: <what it ignored>, reported and not re-added | restored by the operator (<reason>), so the ignore file is authored and no override entry is recorded | none

Added under **Application boundaries**:

- Unit map: <unit>: name from <the source it came from>, built by <evidence>, installed by <evidence>; run <value> and ships <value>, each <proposed from <evidence>, confirmed | corrected by the operator>; domains <names and the boundary the destination draws for each, or none>
- Ships nothing for want of an adapter: <unit>: <language> has no packaging adapter | none
- Declared but not built: <deployable>: declared by <the descriptor naming it>, filed under <the owning unit> | none

Added under **Addon adoption**, and the whole of that block here, since a retrofit takes none:

- Already held: <addon-shaped paths the destination brought with it, on one line> | none

Added under **Repository settings**, as the first line of that block, because a retrofit is the flow that never asks — [Step 2 — Collect the unresolved decisions](generate.md#step-2--collect-the-unresolved-decisions) collects visibility for a generate, and a retrofit finds whatever the destination has been for years:

- Destination visibility: public | private, either way read from the API at report time and recorded nowhere, under [Manifest](lifecycle.md#manifest)

One fact decides four things the operator otherwise meets separately: push protection standing down, the branch ruleset unavailable where the plan offers it on a public repository only, every required check failing before a job starts where the plan bills Actions minutes, and CodeQL's `detect` and `analyze` legs skipping — which has no line of its own anywhere in the report, so on a private destination it is reported here or not at all.

Added under **Verification**:

- Moved paths byte-identical to their pre-move blob: <count>/<count>
- Directories emptied by a move: <path>: gone after the merge | held open by <the ignored residue>, which is the destination's own and is left in place, named under **Left for the operator** | none
- Untracked at the bar: none | <paths>: <the ignore rule step 6 replaced>, disposed by <the operator's decision>
- Declared facts executed: <unit>: `scripts/package` <result>, `scripts/run` <result under CI_DRY_RUN> | the payload ships neither command, so both facts are written and unexecuted
- Tool declaration: <manifest>: added <tool at the template's floor> | kept <the specifier the destination already declared> | declined by the operator, so <capability> cannot reach the bar | nothing missing
- Configuration boundary: one row per language — <manifest> carries <the boundary the list names> | already declared by the destination, kept | the list names none for <language>, whose tools walk upward
- Autofix: `scripts/fix` cleared <count> of <count> findings and rewrote <files>, in <commit> | nothing to fix | a second pass reached <count> more; the test capability reported <result> before and <result> after | the destination's check surface collects no tests, so the rewrite is the tools' own word here | the payload ships no `scripts/fix`, so the bar was measured without a pass
- Autofix settings resolution: every tool resolved inside the candidate | SKIPPED: <tool> resolved `<path>`, outside the candidate — or no settings path could be read for <tool> — so no pass ran and the bar was measured as it stood, under those settings rather than the destination's own
- Payload paths the autofix rewrote: <path>: <the rule or the formatter that rewrote it>, reverted in the candidate and reported as a payload defect | none
- Bar: met | UNMET: <capability>: fail | unavailable (<reason>); stopped before the pull request, zero hosted writes performed
- Destination fix prepared (unmet bar only): branch <name> in <clone>, <commit> clearing <rule> at <paths>, worktree removed; <the rule count before and after under the candidate's target version>, read <by flag | in the candidate, revert verified clean>, <the harness delta | no harness exists in the destination> | partly prepared: <the same>, and left outstanding: <file and rule for each>, because <what the second reading still showed | the path exists only in the candidate> | nothing to prepare: <the capability was unavailable rather than failing, so no rule is there to clear> | nothing prepared: <tool> resolved `<path>`, outside the fix worktree — or no path could be read for it — so every finding is left outstanding, worktree removed
- Destination fix published (unmet bar only): push and pull request offered and awaiting the gate | authorized and performed, at <URL> | declined or never answered, branch left local | not reached, because nothing was prepared
- Destination hooks after merge: shims in <path>, `core.hooksPath` pinned local to it, prior hooks: <path> (<the scope that set it | default>), moved aside: <each hook and where it went, or none>, chained: <each prior hook linked or a duplicate, or none>, verified by <the refusals observed> | n/a (merge declined) | n/a (stopped before the merge was offered), under [Working hooks in the destination after a merge](lifecycle.md#working-hooks-in-the-destination-after-a-merge)

Two whole sections are added after **Repository settings**, and they are named apart from each other because a single block of reversal commands reads as though the whole gate can be walked back:

### Hosted writes, reversible

One line per write log entry, with its `before`, its `after`, and its `reverse_command`.

- <write>: was <before-state> -> <applied value>; reverse with `<exact command>` | declined by the operator (<reason>), recorded in `generation.features`

### Hosted writes, irreversible

- <write>: was <before-state> -> <applied value>; no command reverses it, and <the cost of having made it>
- Ruleset enforcement: <step 9's `mergeable`/`mergeStateStatus` reading of the pull request> | not yet proven at the gate, and no pull request opened to prove it | n/a (no ruleset written)
- Permissions gap: <write>: refused without the host's upgrade message, so the credential and not the plan is the limit | none
