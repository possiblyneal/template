---
name: repo-builder
description: Build or update a repository from this template's base-repo payload. Use only when the user explicitly invokes /repo-builder to generate a GitHub repository or semantically carry template changes between full template commits into an existing generated repository, ending in a pull request. Do not use for ordinary repository edits, generic Git/GitHub operations, or unrelated project scaffolding.
compatibility: Requires Python 3, Git, and gh for authorized GitHub repository and pull-request operations.
---

# Repo Builder

Read `references/lifecycle.md` before acting. It defines the manifest, ownership rules, how checks are run and reported, remote confirmation gates, and failure behavior, and it routes to the one flow being performed:

- `references/generate.md` — build a repository from the payload, including into a destination that already has content
- `references/update.md` — carry a bounded template delta into a repository already generated from it
- `references/adopt.md` — land a held-back repository addon whose condition has arrived
- `references/retrofit.md` — bring a repository that was never generated from the payload under it
- `references/wayfinding.md` — derive the application boundaries, read from `generate.md` step 7
- `references/addon-adoption.md` — finish an addon after copying it, read from `generate.md` step 2 and `adopt.md` step 4
- `references/reporting.md` — how the pull request is reviewed and the shape every flow ends in, read when a flow reaches its review

`references/choosing_a_language.md` is the method wayfinding is a short path through.

## Choose the operation

- **Generate:** The destination has no `.repo-template.json` and no content; build it from `apps/github-repository-template/src/base-repo` at the requested template commit.
- **Retrofit:** The destination has content and no `.repo-template.json`. It is a repository that grew without the template, so the payload is landed over work somebody is already shipping rather than into an empty tree. The flow runs end to end: the candidate and its working hooks, the unit map the operator confirms, the moves that follow from it, the record, the collisions, the bar, one hosted-write gate, then the pull request and a second gate that offers the merge and is declined by default.
- **Update:** The destination has `.repo-template.json`; reconcile its recorded template commit with a requested descendant commit.
- **Adopt:** The destination has `.repo-template.json` and the request is to add a held-back repository addon whose condition has arrived, not to carry a template delta. Read the addon from the recorded commit and do not advance the pin. Distinct from update: it adds a sibling file rather than reconciling a delta, and it moves no commit.
- If the requested operation and destination state disagree, stop and explain the mismatch.

A generate whose destination holds content is still a generate, but its collisions are decided by hand and it never resolves one by deleting. `references/generate.md` carries those rules; read them before writing to a non-empty destination. What separates it from the retrofit above is the record the destination is headed for: a generate writes the payload's own tree and its manifest as the repository's first template state, where a retrofit reconciles a tree somebody else laid out and writes the record at the end, around what it found.

A generate derives its application boundaries rather than collecting them. How many `apps/<name>/` directories the repository gets, what each is called, and what each is written in come out of wayfinding, run with the user once the candidate is materialized and the destination repository exists — the repository being what the payload's `docs/agents/issue-tracker.md` resolves against — and before the candidate is personalized. It is two questions asked in one structured prompt — what ships separately, and what binds first for each — with your reading of the request as the options. Skip it entirely when the invocation already names every deployable and its language, and report that it was skipped.

The payload ships `docs/agents/`, read by path rather than through any index, so `/setup-matt-pocock-skills` is skipped by default and step 6 creates the labels those files name instead; `references/generate.md` step 6 gives the cases where the skill still runs and the ordering that holds either way. Where it does run, invoke it with the Skill tool rather than answering its questions yourself or reproducing what it writes.

When those two questions do not settle it, the rest is the full method in `references/choosing_a_language.md`, and that is `/wayfinder`'s job rather than this skill's. Against the triggers `references/wayfinding.md` names, invoke `/wayfinder` with the destination and notes it specifies, and stop once the map is charted — leaving the candidate and the repository in place to resume against. Name no effort directory, do not work a ticket, and do not answer the six steps yourself. `docs/adrs/0003-order-the-repository-ahead-of-wayfinding.md` records why the repository exists before wayfinding runs and why charting ends the generate.

## Preflight before editing

Use `scripts/preflight.py` for deterministic validation and retain its JSON in the work record. `scripts/tests/test_preflight.py` and `scripts/tests/test_addon_adoption.py` cover them; run them after editing `preflight.py` or `addon-adoption.json`.

- `generate` resolves the exact source commit, verifies its payload subtree, and requires that commit to be on the template's own branch — the commit it records is the base every later update diffs from. It never inspects the destination, so an occupied destination looks identical to an empty one; establish that yourself.
- `update` validates provenance, repository identities, a clean destination, strict ancestry, and the bounded template delta. Each delta path carries a `destination_state` of `unmodified`, `modified`, or `absent`, so reconciliation reads content only for the paths the destination also holds a changed copy of. A delta path the record overrides comes back marked `overridden` with its recorded reason, and out of the managed tally, so the flow does not reconcile a collision that was settled once already.
- `adopt` validates provenance, repository identities, a clean destination, and each requested addon at the recorded commit: it exists in `repository-addons/`, carries an `addon-adoption.json` entry, completes its pair, is not requested alongside the addon it excludes, and the destination holds neither it nor that addon.
- `retrofit` validates the source commit, the destination's identity against its origin, tracked cleanliness, and the absence of a record, then reports the payload path list, every collision, and every addon-shaped path the destination already holds. That last list is a finding and never a stop: a retrofit adopts no addon. It reaches git and nothing else, so its collisions are evidence for a decision the flow makes later rather than a classification.

The helper is read-only and only authorizes the next stage. Claude owns personalization and semantic reconciliation; do not replace judgment with a blind copy, overlay, or text merge. Keep provenance, ancestry, ownership, validation, and remote-action gates even when simplifying the work. Unless preflight rejects the operation or reconciliation finds a real conflict, continue through materialization, local edits, manifest advancement, and verification. A preflight report alone is not a completed build or update.

## Publish an empty base, build locally, then publish content

1. Materialize a generate's candidate at `tmp/<repository-name>/` in this repository from the exact source commit, then create the destination repository and its empty base at its own gate before configuring or personalizing that candidate. On a generate the repository exists that early so the issue tracker and the wayfinding map have somewhere real to live; everything after it is built and checked locally before any content is published. For updates, read the old and new blobs for every preflight delta, compare them with the destination blob, and edit the destination candidate; do not stop at a proposed classification.
2. Preserve product-owned content and reconcile managed content against destination intent. Apply every conflict-free managed delta to disk. When the template renames an unchanged managed file, move the destination file to the new path rather than retaining both names. If the destination also changed the file non-overlappingly, move it and carry those edits into the new template version.
3. Verify the candidate files contain the intended new template behavior and preserved destination behavior. Stage the candidate before running checks, since `pre-commit run --all-files` reads the Git index and passes trivially over unstaged work. Run documented checks and report unavailable checks as unavailable, not passed. Do not code-review the candidate or the pull request it becomes; prove the copied files are copies instead, as [Reviewing the pull request](references/reporting.md#reviewing-the-pull-request) directs, and read the authored surface it leaves.
4. Verify the file list against the payload's tracked paths, not only the content of the files present. Absence has no runner, so a dropped file produces a green run.
5. Show the candidate diff, reconciliation summary, file-list account, addon adoption account, repository settings, and exact remote operations. Copying an addon does not adopt it: `apps/github-repository-template/src/addon-adoption.json` names the regions of each one that are wrong until edited, and none of them fail a check. Walk that entry for every addon taken and report each region as done or outstanding.
6. Obtain confirmation immediately before repository creation, settings changes, pushes, or PR creation unless those exact actions and target were explicitly authorized in the invocation.
7. Open the pull request and verify it. Never merge it, except the bootstrap-generate case `references/generate.md` step 12 documents. An empty check list means the workflows are unverified, not that they passed; check the commit's check-suites and [githubstatus.com](https://www.githubstatus.com/) before calling it a defect.

On update, advance `.repo-template.json` only after the candidate validates, and include that advance in the same pull request. On conflict or failure, keep the recorded commit unchanged and stop with the evidence and decision needed.

Report the result in the shape [`references/reporting.md`](references/reporting.md) gives under **Final report**. It is authoritative and carries lines this file does not — reproduce it from there rather than from memory.
