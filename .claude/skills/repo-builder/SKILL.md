---
name: repo-builder
description: Build or update a repository from this template's base-repo payload. Use only when the user explicitly invokes /repo-builder to generate a GitHub repository or semantically carry template changes between full template commits into an existing generated repository, ending in a pull request. Do not use for ordinary repository edits, generic Git/GitHub operations, or unrelated project scaffolding.
compatibility: Requires Python 3, Git, and gh for authorized GitHub repository and pull-request operations.
---

# Repo Builder

Read `references/lifecycle.md` before acting. It defines the manifest, ownership rules, the wayfinding step and its handoffs to `/setup-matt-pocock-skills` and `/wayfinder`, generation/update flows, remote confirmation gates, failure behavior, and final report. `references/choosing_a_language.md` is the method behind both.

## Choose the operation

- **Generate:** The destination has no `.repo-template.json`; build it from `apps/github-repository-template/src/base-repo` at the requested template commit.
- **Update:** The destination has `.repo-template.json`; reconcile its recorded template commit with a requested descendant commit.
- **Adopt:** The destination has `.repo-template.json` and the request is to add a held-back repository addon whose condition has arrived, not to carry a template delta. Read the addon from the recorded commit and do not advance the pin. Distinct from update: it adds a sibling file rather than reconciling a delta, and it moves no commit.
- If the requested operation and destination state disagree, stop and explain the mismatch.

Generation into a destination that already has content is still a generate, but its collisions are decided by hand and it never resolves one by deleting. `references/lifecycle.md` carries those rules; read them before writing to a non-empty destination.

A generate derives its application boundaries rather than collecting them. How many `apps/<name>/` directories the repository gets, what each is called, and what each is written in come out of wayfinding, run with the user once the candidate is materialized, the destination repository exists, and `/setup-matt-pocock-skills` has recorded where that repository tracks its issues — and before the candidate is personalized. It is two questions asked in one structured prompt — what ships separately, and what binds first for each — with your reading of the request as the options. Skip it entirely when the invocation already names every deployable and its language, and report that it was skipped.

Invoke `/setup-matt-pocock-skills` with the Skill tool at the step `references/lifecycle.md` gives it, before wayfinding. Invoke it rather than answering its questions yourself or reproducing what it writes.

When those two questions do not settle it, the rest is the full method in `references/choosing_a_language.md`, and that is `/wayfinder`'s job rather than this skill's. Against the triggers `references/lifecycle.md` names, invoke `/wayfinder` with the destination and notes that section specifies, and stop once the map is charted — leaving the candidate and the repository in place to resume against. Name no effort directory: `/wayfinder` charts wherever `docs/agents/issue-tracker.md` sends it, which is the reason the repository and its tracker exist before wayfinding runs. Do not work a ticket and do not answer the six steps yourself: charting hand-resolves nothing by design, and a generate that pushed on through its own map would return the decomposition it had already guessed.

## Preflight before editing

Use `scripts/preflight.py` for deterministic validation and retain its JSON in the work record. `scripts/tests/test_preflight.py` and `scripts/tests/test_addon_adoption.py` cover them; run them after editing `preflight.py` or `addon-adoption.json`.

- `generate` resolves the exact source commit and verifies its payload subtree. It never inspects the destination, so an occupied destination looks identical to an empty one; establish that yourself.
- `update` validates provenance, repository identities, a clean destination, strict ancestry, and the bounded template delta.
- `adopt` validates provenance, repository identities, a clean destination, and each requested addon at the recorded commit: it exists in `repository-addons/`, carries an `addon-adoption.json` entry, completes its pair, and is absent from the destination.

The helper is read-only and only authorizes the next stage. Claude owns personalization and semantic reconciliation; do not replace judgment with a blind copy, overlay, or text merge. Keep provenance, ancestry, ownership, validation, and remote-action gates even when simplifying the work. Unless preflight rejects the operation or reconciliation finds a real conflict, continue through materialization, local edits, manifest advancement, and verification. A preflight report alone is not a completed build or update.

## Publish an empty base, build locally, then publish content

1. Materialize an isolated local candidate from the exact source commit, then create the destination repository and its empty base at its own gate before configuring or personalizing that candidate. On a generate the repository exists that early so the issue tracker and the wayfinding map have somewhere real to live; everything after it is built and checked locally before any content is published. For updates, read the old and new blobs for every preflight delta, compare them with the destination blob, and edit the destination candidate; do not stop at a proposed classification.
2. Preserve product-owned content and reconcile managed content against destination intent. Apply every conflict-free managed delta to disk. When the template renames an unchanged managed file, move the destination file to the new path rather than retaining both names. If the destination also changed the file non-overlappingly, move it and carry those edits into the new template version.
3. Verify the candidate files contain the intended new template behavior and preserved destination behavior. Stage the candidate before running checks, since `pre-commit run --all-files` reads the Git index and passes trivially over unstaged work. Run documented checks and report unavailable checks as unavailable, not passed.
4. Verify the file list against the payload's tracked paths, not only the content of the files present. Absence has no runner, so a dropped file produces a green run.
5. Show the candidate diff, reconciliation summary, file-list account, addon adoption account, repository settings, and exact remote operations. Copying an addon does not adopt it: `apps/github-repository-template/src/addon-adoption.json` names the regions of each one that are wrong until edited, and none of them fail a check. Walk that entry for every addon taken and report each region as done or outstanding.
6. Obtain confirmation immediately before repository creation, settings changes, pushes, or PR creation unless those exact actions and target were explicitly authorized in the invocation.
7. Open the pull request and verify it. Never merge it. An empty check list means the workflows are unverified, not that they passed; check the commit's check-suites and [githubstatus.com](https://www.githubstatus.com/) before calling it a defect.

On update, advance `.repo-template.json` only after the candidate validates, and include that advance in the same pull request. On conflict or failure, keep the recorded commit unchanged and stop with the evidence and decision needed.

`references/lifecycle.md` is authoritative for this complete output shape:

```md
## Repo Builder Result

- Operation: generate | update | adopt | stopped
- Pull request: <URL or "not created">
- Template: <old full commit, or "not previously generated"> -> <target full commit>
- Destination: <owner/repository>

### Reconciliation
- Applied: <paths or none>
- Preserved: <paths or none>
- Renamed/deleted: <paths or none>
- Conflicted: <paths and competing intents, or none>

### Application boundaries
- <deployable>: choke point <constraint, or "none bound; time-to-working-code"> -> <language>, <selected from list | reasoned from the seam contract | measured against it>
- Wayfinding: short form settled it | handed off to `/wayfinder` (<which trigger>), map at <URL or path> | skipped, supplied in the invocation
- ADRs written: <paths, or none>

### File list
- <payload paths accounted for, and every difference named as intended or as a defect>

### Addon adoption
- <addon taken>: <slot token, review section, or external step>: filled | reviewed | done | OUTSTANDING (<what remains>)
- <addons offered and not taken, on one line>

### Repository settings
- <setting>: enabled | unavailable (<reason>) | not requested
- Issue tracker: <GitHub | GitLab | local markdown | other>, recorded in `docs/agents/issue-tracker.md`; triage labels: default | overridden | not configured

### Verification
- `<exact command>`: pass | fail | unavailable (<reason>)
- Default branch after merge: <check-suite result> | n/a (nothing merged)

### Pending action
<none, or the exact decision/authorization needed>
```
