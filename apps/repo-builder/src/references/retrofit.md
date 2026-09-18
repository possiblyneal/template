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
- **Step 6 — Reconcile the destination's layout**
- **Step 7 — Write the record, decide the collisions, meet the bar**
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

The absent set is `payload_paths` minus the `path` of every collision, taken from the preflight JSON rather than recomputed.

**The payload's placeholder unit is not in that list, and preflight is what holds it back.** `apps/app-name/` exists for [generate's Step 8 — Personalize the candidate](generate.md#step-8--personalize-the-candidate) to rename into the application's own name; a retrofit reads its units off what the destination already delivers, so there is nothing for it to be. Overlaid, it survives every check the flow runs — it is a well-formed empty unit, so the layout audit, `unit-declaration` and `unit-facts` all pass it — and the retrofitted repository ships a second unit that delivers nothing. Both reference retrofits landed it and both retired it by hand. Do not add it back to the absent set on the reasoning that preflight found it missing: it is missing because the destination was right not to have it.

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

### Step 6 — Reconcile the destination's layout

Step 5 produced the map and moved nothing. This step is where the destination's tree becomes the template's layout, and it has three instruments: **move** a path to where the rules put it, **repair** the configuration a move broke, and **retire** a destination artifact the payload already covers. Retiring is not a fourth thing a retrofit does to be tidy; it is part of what bringing a repository under the template means.

**The complete plan is presented before a single file moves.** Every path, its destination, and which instrument applies, in one list. The operator disposes per path, and a rejection with no correction stops the retrofit exactly as a rejected unit map does: a partial layout is the one state no later run can reason about, since the audit cannot tell a move nobody wanted from a move nobody got to.

**Every root scoped folder the unit map claims moves to its unit.** `libs/`, `tests/`, `scripts/`, `tools/`, `deploy/`, and `assets/` at the root mean repository-wide, and a destination that never had units put everything there by default rather than by decision. This is the only instrument that closes the scope rule, which `scripts/structure` reports `not-applicable` because whether a file sits at its own scope is a judgement about content. The audit cannot make this move and cannot check it; the unit map is what makes it decidable at all.

**Documentation stays repository-wide**, even where there is exactly one unit and every other scoped folder moved under it. `scripts/adr-index` rewrites the index from a root path, so a `docs/` that followed its unit takes the records with it and out of the index, which is the failure [Architecture records live at the root documentation path](lifecycle.md#architecture-records-live-at-the-root-documentation-path) names. The records migration to that path is performed here, with the moves, rather than left to the step that writes the new record.

**A readme below the root is documentation and moves with it.** It lands in the nearest owning `docs/` under a name describing what it is about, because a `README.md` inside a documentation folder is a filename that tells a reader nothing and collides with the next one that moves. The repository's own root readme is not this: it stays at the root, where it is an addon the destination already holds.

**The flow writes no `.structure-allow` entry.** Across the reference repositories nothing was genuinely immovable, so an entry written by the flow would almost always be a move it declined to make, recorded as permission nobody asked for. A path that cannot be moved is reported with the reason; the operator may write the entry themselves afterwards, outside the flow, which keeps the allowlist a record of human decisions rather than of the flow's difficulties.

**Configuration a move broke, the flow repairs, in the same change.** A test path, a build target, a workflow's working directory, a lint or coverage root: these are broken by the move and by nothing else, and the flow is the only party holding the mapping from old path to new. A path reference that is **exactly** a path the flow moved is rewritten. Prose describing the old structure is reported and left alone, because a sentence about where things live is a claim a rewrite cannot make true and a reader has to re-make.

**An artifact is retired only when the payload covers its whole role**, judged by what the thing does in the flow it belongs to rather than by matching features off a list. [Retiring a covered gate script](lifecycle.md#retiring-a-covered-gate-script) governs the gate scripts and this step follows it for every artifact: fully covered is retired, with its callers repointed and `generation.superseded` recording it; partially covered survives as a reported conflict naming the duplicated parts specifically. The flow never leaves a destination with a capability it had before the retrofit and lacks after.

**Two collisions the overlay skipped are settled here**, and both are files a destination always has.

The ignore file is replaced outright, at the payload's mode as well as with the payload's content — [The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content), and this is the path it names, because a destination always has one and rewriting it in place keeps whatever bit it carried. A merged ignore file is the state where nobody can say which rules the repository actually promises, and the payload's is a guarantee in the same sense the automation directory is. Destination rules the payload does not cover are **reported rather than re-added**, with the consequence stated plainly: un-ignoring a generated directory can make the candidate fail its own check surface, and where it does, the flow stops and the operator decides which rule survives. That stop is the point of reporting rather than re-adding, since a rule quietly carried across hides exactly this.

The instruction file is merged, and it is re-established as one of the last steps of the whole retrofit rather than here. `CLAUDE.md` is what the destination's next agent session reads, and everything this run did — the units, the moves, the retirements, the reported rules nobody re-added — is what that session needs. Written now it describes the tree as it stood before the record and the collisions were settled, which makes it a bootstrap for work already done. So this step takes the merge as far as the layout facts and leaves the file's re-establishment to the end.

**What this step promises.** For a checkable destination, `scripts/structure` passes on zero allowlist entries after it. Layout reconciliation is cheap and the check bar is expensive, and they fail for unrelated reasons, so a green audit here says nothing about whether the destination's own checks pass; that is the later step's to report.

### Step 7 — Write the record, decide the collisions, meet the bar

Nothing here reaches the network. This step settles everything that has to be true before the flow is allowed to publish, in the order that makes each part decidable: the collisions, then the record, then the tool declaration, then the bar measured on the result.

**Every remaining collision is proposed and disposed, per file.** Diff the destination's version against the payload's, state what each one says, and let the operator pick payload, destination, or a merge. A disposition the payload wins writes the payload's mode too, under [The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content). No path-matching rule can stand in for this. Across the reference repositories the same payload path was occupied by a copy differing in one word, by a genuinely different document with a stated reason for being different, by one naming five canonical roles where the payload names seven, and by one half again as long: four dispositions for one path, and nothing about the path predicts which.

**Where this run invalidated the destination's own stated reason, propose the payload's version and name the step that invalidated it.** A document explaining that scripts live at the root is no longer describing the repository once step 6 moved them. The proposal is still the operator's to refuse, and naming the invalidating step is what lets them refuse it on the merits rather than on the flow's say-so.

**A chosen destination version at a managed path is an [overridden path](lifecycle.md#overridden-paths)**, recorded with the reason the destination's version won, so the next update does not re-raise a collision settled here. A destination version that wins at a product path is already the destination's by ownership: report it with its reason and record nothing, which is what preflight requires of the record this step writes.

**The record's ownership array is the payload's default, with zero destination-specific entries.** This is only true because the moves came first: layout lifted foreign content out of every managed pattern, [the automation directory](lifecycle.md#the-automation-directory-is-replaced-not-reconciled) was replaced whole, and the ignore file was replaced outright. Every remaining destination file then falls on unmatched, which [Ownership](lifecycle.md#ownership) resolves to product. **A destination path still matching a managed pattern is a layout failure to fix in step 6**, never an ownership exception written here. A bespoke array would also make a retrofitted record distinguishable from a generated one, which is the opposite of what a retrofit is for.

**No field records which flow ran.** Convergence is the whole point: a retrofitted repository and a generated one are the same repository from the moment the record exists, and a field an update can read is a field an update can branch on. Provenance is the pull request, which says everything a field would have said and more.

**Layout moves are absent from the record.** An update inspects only paths the payload delta names, and a moved file is product-owned on both sides, so it never enters that comparison; a list of moves would be a field nothing reads, going stale from the first rename after the retrofit. The pull request is the record of the moves.

**Unit names are recorded and nothing beside them**, as step 5 and [Manifest](lifecycle.md#manifest) both have it: the run and ship facts live in each unit's own declaration.

**The tool declaration adds only what is missing**, at the template's floors, keeping any specifier the destination already declares. [Tools the first manifest must declare](lifecycle.md#tools-the-first-manifest-must-declare) is the list, per language. Tool lines only: making moved code build, import or resolve is configuration a move broke and belongs to step 6. This file is not a payload path, so it is not an overridden path either; its ownership is product, unlisted and unrecorded. Report each line added. Lockfiles the environment step produced are kept, since a resolved environment nobody can reproduce is what step 4 refused to accept. A rival tool is retired only where another fills its exact role in the flow, under [Retiring a covered gate script](lifecycle.md#retiring-a-covered-gate-script). The operator may decline the declaration outright, and the report then says which capability the bar cannot reach and why.

**`.github/dependabot.yml` gains the language entries the destination's manifests earn**, as [Dependabot entries follow the manifests present](lifecycle.md#dependabot-entries-follow-the-manifests-present) directs. It is derived here rather than with the overlay in step 3 because step 6 is what settles where the manifests sit: a module the moves lifted into `apps/<name>/` needs an entry naming that directory, and one derived before the moves would name the path the file no longer occupies. A retrofit is where this matters most — a destination that predates the template is the case most likely to hold a manifest somewhere other than the root.

**The bar is the destination's own check surface passing on the candidate**, run and read by [Running the destination's checks](lifecycle.md#running-the-destinations-checks). A `FAIL` blocks and so does an `unavailable`, for the reason that section already gives: a check whose runner was missing measured nothing, and a report calling it a pass claims a guarantee the run does not hold. A `not-applicable` does not block, because a language that is not present has nothing to prove.

**An unmet bar is a failed retrofit and it stops before the pull request**, naming the capability that could not pass and why. No partial retrofit is published with the gap written into the description: the destination's existing debt is fixed by its operator, on its own default branch, through their own process, and the retrofit is re-run afterwards. The fix does not ride along in the candidate, where it would arrive as this flow's change to code this flow does not own. A run stopping here has performed zero hosted writes, which is what makes re-running it cheap.

### Step 8 — The hosted-write gate

A **hosted write** is a change to the destination's state on the host that no pull request can carry: a repository setting, a branch name, a label, a ruleset. Every one the retrofit makes happens here, at one gate, immediately before publishing and only after step 7's bar passed. The placement is the point: a destination whose bar could not be met has had nothing done to it on the host, so re-running after the operator clears the debt costs nothing and undoes nothing.

This is a deliberate divergence from [generate](generate.md), which reaches [Remote action gates](lifecycle.md#remote-action-gates) early because the repository has to exist before the map and the tracker have anywhere to live. A retrofit has no such forcing: the repository exists, the tracker is the destination's own, and nothing before this step needs the host.

**The gate creates nothing.** It confirms the identity preflight already proved against the origin, and it authorizes each write by naming the exact command that performs it. **No write is performed that the gate did not list**, which is the rule the whole step is built to keep: a write discovered mid-run is a write nobody authorized.

**Generate's ruleset probe is not performed.** It puts a throwaway commit on the live default branch and pushes it directly, and [Step 5 — Configure the repository settings](generate.md#step-5--configure-the-repository-settings) says what happens where the branch does not reject it: the commit becomes the default-branch tip and only a force-push removes it. Against an empty repository that is a contained risk. Against a repository with other people's clones fetching it, it is not. So nothing is pushed at the default branch to prove enforcement here, and the existence read is not what stands in for it: step 9's pull request supplies the proof for free, under [A written ruleset is proved satisfiable, not merely present](lifecycle.md#a-written-ruleset-is-proved-satisfiable-not-merely-present). Enforcement is therefore **not yet proven at this gate** rather than unproven outright, and the report carries step 9's reading rather than this step's.

Four writes, in this order.

**1. Merge settings, in one call.** `allow_merge_commit`, `allow_squash_merge`, `allow_rebase_merge`, and `delete_branch_on_merge` go in a single `PATCH`, for the reason generate's step 5 gives: sent separately the second call can be refused after the first has landed, and a half-applied merge policy is worse than one never started. State the destination's four current values out loud before overwriting them, since this is somebody's deliberate choice being replaced. Declinable, and a refusal is recorded in `generation.features` with its reason.

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

**3. Labels**, with the case-insensitive guard and the payload-spelling rename that [Remote action gates](lifecycle.md#remote-action-gates) already specifies for a generate: a label the destination carries under a different case is renamed to the payload's spelling rather than created beside it, and the rename is its own line, because label search is case-sensitive and anything pinned to the old string stops matching.

**4. Security settings and the branch ruleset** — dependency alerts, security updates, push protection, and the ruleset generate creates. Declinable and recorded. Push protection refused on a private destination on a free plan is reported rather than failed, exactly as `scripts/repo-settings check` already separates the two.

The ruleset's required checks are named by their check runs, not by their workflow job ids — the payload's `ci.yml` has job id `ci` and `name: CI`, so `CI` is the context and `ci` is a context nothing reports. [Step 5 — Configure the repository settings](generate.md#step-5--configure-the-repository-settings) carries the rule and the full set of spellings the payload's workflows report; this gate writes the same ones. A retrofit is where getting it wrong costs most: the destination's default branch carries other people's work, and a context nothing reports never fails, so the rule reads back `active`, every settings check passes, and every pull request stops being mergeable with nothing naming the cause. Enforcement is already reported **unproven** here for want of the probe, which removes the one reading that would have caught it.

A ruleset the destination already had is the same hazard pointed backwards. [The automation directory](lifecycle.md#the-automation-directory-is-replaced-not-reconciled) is replaced whole, so the destination's own workflows are gone and any context its ruleset required by their names is now permanently pending. Read the existing ruleset's required contexts before writing, and name at the gate every one the payload's workflows do not report — like the branch name above, it is repaired in place by rewriting it to the contexts that now exist, and unlike the branch name it is invisible until somebody opens a pull request.

**A refusal carrying the host's upgrade message means the feature is not offered**, so there is nothing to repair and `not offered for the plan` is the whole finding. The same refusal **without** that message is a permissions gap, and that is a finding at the gate rather than a line in the report: it says the credential this run holds cannot do what the gate just authorized.

**Every post-write verification polls rather than reading once.** The rename, the dependency summary, and the protection endpoints were all observed returning the pre-write state immediately after a write the host had accepted. A single read is how a write that succeeded gets reported as a write that did nothing.

**There is no undo mechanism, so the report carries the before-state of every hosted write** and lists the writes in **two separately named sections**: the reversible ones, each with the exact command that reverses it, and the irreversible ones, each with its cost. Never one section. A single copy-pasteable block of commands reads as though the whole gate can be walked back, and a closed pull request's review conversation cannot.

### Step 9 — Publish, prove, and offer the merge

**The head is the candidate's own branch.** Step 2 created it, every step since wrote into it, and nothing is re-materialized at publish time: a tree rebuilt here is a tree nobody checked.

**Every push goes to the candidate's feature branch, with the destination's hooks running.** The push guard the payload installs allows a feature branch and refuses the default branch, so nothing here needs `--no-verify`: the bypass [generate](generate.md#step-3--materialize-the-candidate) confirms for its own bootstrap commit is an exception for pushing straight to the default branch of an empty repository, and a retrofit never does that. A push a hook refuses is a finding to report, never a push to repeat with the hook turned off.

**The base is the default branch**, which step 8's rename has already made correct. A base rename retargets an open pull request, and the hazard that step named — the host closing rather than retargeting — applies to a renamed *head*, which this branch never is.

**The body is always explicit, and it is filled against the pull-request template this same diff introduces.** The host renders a template from the base branch and an explicit body suppresses it entirely, so a body written freehand is the repository's first pull request ignoring the rule the same pull request is installing. Fill the payload template's own sections. [Generate](generate.md#step-11--publish-the-candidate) states the reason for an explicit body in general terms.

The body carries what a reviewer of *this* pull request needs: the per-path dispositions, the layout moves, the per-write reverse commands from step 8, the workflows the pull-request event never exercised, and the fact that code review was skipped and why. It does not carry the session report. That is written for the operator who ran this flow, in the shape [Final report](reporting.md#final-report) fixes, and pasting it into a description aimed at the destination's collaborators serves neither reader.

**Prove it twice before anything merges.** [Reviewing the pull request](reporting.md#reviewing-the-pull-request) runs the copy proof over the overlay set, every payload path written because it was absent, and a retrofit runs the rename-purity proof beside it over the moved set. Report both counts. What is left after the two is the authored surface, read line by line, and **grepping the destination for every path this flow deleted or renamed is not optional here**: it is the single highest-value line of the review, because a live reference in destination-owned prose is exactly what no check reads. Overridden paths are in neither proof, never having been written.

**Every payload workflow except the release workflow runs on this pull request**, so it is a real exercise of the whole gating set rather than a sample. Read the check suites as [Step 12 — Verify the published repository](generate.md#step-12--verify-the-published-repository) reads them, keeping the same distinction between a failing run and no run dispatched and the same caveat about host status, then **state which workflows the pull-request event never ran**, so the green result is read for what it covers.

**With the checks green, read `mergeable` and `mergeStateStatus` as a pair**, under [A written ruleset is proved satisfiable, not merely present](lifecycle.md#a-written-ruleset-is-proved-satisfiable-not-merely-present). This is the reading step 8 deferred: it proves the ruleset that gate wrote both binds and can be satisfied, on the pull request this flow was opening anyway. `MERGEABLE`/`BLOCKED` here means the merge offered below can never be taken, so read it before offering rather than discovering it in the poll — and it is a finding against the ruleset, not against the candidate, whose checks are green.

**Then, optionally, the merge, at a second gate.** The first gate cannot carry it: the checks did not exist yet when it ran, and authorizing a merge against checks nobody has seen authorizes nothing. Poll until every required check is green, then offer exactly the merge and nothing beside it. **Declining is the default**, and it leaves an open pull request for the destination's own people to review and merge their own way. Taking it merges, then reads the default branch's check suites and fills the report's existing line, because a green pull request ran against a merge commit and the branch afterwards is a different commit with a different trigger.

The offer exists because with step 7's bar the pull request only ever opens fully green, and merging is the only thing that verifies the default branch. It is an offer and not a step because the premise [Reviewing the pull request](reporting.md#reviewing-the-pull-request) rests on is false here: most of what it skips review for is already-reviewed template content, and a retrofit's authored surface is repaired configuration, rewritten path references, a merged instruction file and a retired gate script — edits to the destination's own code that nobody has reviewed. A destination also has collaborators with branches in flight that every rename conflicts with, and they are the ones who know when that lands well.

## The retrofit adopts no addon

A retrofit takes no [repository addon](addon-adoption.md), and needs no mechanism to avoid taking one. What preflight reports in `addons_present` is a finding: the addon-shaped paths the destination already holds, named so the operator can see what [adopt](adopt.md) would have offered against a destination that has answered most of it already.

Nothing has to be taught to leave those files alone. The root allowlist holds the addon filenames by name, under the rule that they are additions by occasion, so a destination's own readme, licence or changelog is already permitted where it sits and the structure audit does not flag it. And an addon is not a payload path: addons live in a sibling tree rather than under the payload subtree, so a destination's readme never reaches the collision list in the first place and step 3 never writes over one.

The record the retrofit writes carries no addon entry, for the same reason [generate](generate.md)'s does not: the manifest records what the flow landed, and this flow landed none. A destination that wants one runs adopt afterwards, against the repository that now exists, and that run is what writes the entry.
