# Generate

Read [`lifecycle.md`](lifecycle.md) first — the manifest, ownership, check reporting, the remote gates, failure behavior, and the report shape are there and apply throughout.

## Steps

- **Step 1 — Resolve the source commit and preflight**
- **Step 2 — Collect the unresolved decisions**
- **Step 3 — Materialize the candidate**
- **Step 4 — Create the destination repository**
- **Step 5 — Configure the repository settings**
- **Step 6 — Configure the repository for the engineering skills**
- **Step 7 — Derive the application boundaries**
- **Step 8 — Personalize the candidate**
- **Step 9 — Run the candidate's checks**
- **Step 10 — Verify the file list**
- **Step 11 — Publish the candidate**
- **Step 12 — Verify the published repository**
- **Step 13 — The first prompt**

A generate runs them in order and reads them in order. A reader needing one step alone — `SKILL.md`, `lifecycle.md`, `wayfinding.md` and `reporting.md` each cite one — reads it with `sed -n '/^### Step 12 /,/^### /p'` rather than opening the whole file. The headings are addresses so that a citation does not cost 30 KB to follow.

### Step 1 — Resolve the source commit and preflight

Resolve the requested source to an exact commit and run:

```bash
python3 apps/repo-builder/src/scripts/preflight.py generate \
  --template-repo <template-repo> \
  --target <ref-or-commit> \
  --subtree apps/github-repository-template/src/base-repo \
  --destination-repository <owner/name> \
  --default-branch main
```

`--default-branch` is the destination's; `--template-branch` is this template's own and defaults to `main`. Pass it only where the source genuinely lives on another branch, and expect a refusal for a commit on none of them: the commit recorded here is the base every later update diffs from, so one off the template's branch generates a repository no update can ever reach.

`generate` validates the source only. It takes the destination as a name, never inspects it, and so cannot tell an empty repository from one with content. Establish that yourself before materializing.

### Step 2 — Collect the unresolved decisions

Collect only unresolved decisions: owner/name, visibility, public-repository files, release behavior, and feature availability. The application boundaries are not among them. They are derived rather than collected, and step 7 derives them once the candidate and the repository exist. Neither are the merge settings: step 5 applies all four unconditionally, so there is no choice here for the step 4 gate to name.

The public-repository files are the repository addons, held back rather than shipped and offered against the conditions the answers to this step have established. Adopt the ones taken as the [Addon adoption](addon-adoption.md) section directs, from this same source commit.

### Step 3 — Materialize the candidate

Materialize the subtree from that exact commit into `tmp/<repository-name>/`, resolved against this repository rather than against the directory the session was invoked from. Do not substitute the current working tree, and do not pick a location outside the repository: `tmp/` is what this repository ships for the purpose, held out of the tree by `tmp/*` in `.gitignore` so a candidate cannot be committed here by accident, and inside the repository so writing a whole tree into it stays within the boundary an agent's file-access approvals are drawn on. Naming it also makes the resume real, since a stop leaves the candidate in place for the next session to re-enter at and a directory chosen freshly each time is one nobody finds again. Initialize Git in it with `git init -b <default-branch>` and leave the remote unset; step 4 creates the repository that remote points at. Pass `-b` rather than taking whatever `init.defaultBranch` happens to be: an unborn HEAD on `master` while step 4's `update-ref` writes `refs/heads/main` leaves HEAD pointing at neither, and step 5's probe then commits to the wrong branch, pushes nothing, and reports an unprotected branch as protected. A resumed generate re-running this step gets `warning: re-init: ignored --initial-branch` and exits zero, so the flag repairs nothing on that path; read `git symbolic-ref HEAD` rather than assuming it took, and point HEAD at the default branch before step 4's `update-ref` if it does not already.

[The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content) binds every flow that lands payload content, and generate is the one flow it costs nothing. `git archive` carries each mode out of the pinned tree and the candidate is fresh, so no destination file's bit is there to survive the write. That is why no step below reads a mode or cites the rule — the exemption is in how this flow writes, not in the rule's reach.

### Step 4 — Create the destination repository

Create the destination repository, at the [remote action gate](lifecycle.md#remote-action-gates). Present the gate first, and every line of it that applies: the repository name and visibility, the empty root commit, the settings step 5 applies, the ruleset probe step 5 pushes to prove those settings bind, the triage labels step 6 creates, and the map step 7 writes. The payload records the tracker, so both are decided here rather than left open: they are GitHub Issues on this repository. Return to this gate only if step 6 runs `/setup-matt-pocock-skills` after all and it settles on a different hosted tracker. Settling on local markdown needs no return: it makes no remote write, so the authorization taken here simply goes unused. There is no diff and no check result to show yet, which is why this gate is separate from the one at step 11 — that one authorizes publishing content that has been reviewed, and this one authorizes an empty repository so that everything after it has somewhere to live.

Create it without auto-initialization, set it as the candidate's remote, and push one empty root commit to the default branch, so the full generated payload is reviewable as a pull-request diff at step 11 rather than arriving as an initial commit nobody reads.

```bash
empty_tree=$(git hash-object -t tree /dev/null)
empty_commit=$(git commit-tree "$empty_tree" -m "chore: initialize empty repository")
git update-ref refs/heads/<default-branch> "$empty_commit"
git push origin <default-branch>
```

Build the commit with `commit-tree` rather than by checking the default branch out and committing on it. The candidate's own `no-commit-to-branch` hook refuses such a commit and its `protect-branch` pre-push hook refuses the push, both correctly — neither can distinguish this one-time structural bootstrap from an ordinary disallowed one. Neither hook is installed this early, since step 9 is what installs them, but do not lean on that ordering: a resumed generate reaches this step with them already in place, and the push then needs `--no-verify`, because `protect-branch` blocks by destination ref rather than by commit content and so cannot recognize its one exception. Get explicit confirmation for that specific bypass before running it — it defeats the only branch protection this plan has, and every other push and commit in this lifecycle goes through hooks normally.

The repository existing this early is deliberate, and step 7 is the reason. The payload's `docs/agents/issue-tracker.md` infers the repository from `git remote -v`, and `/wayfinder` charts its map wherever that file sends it. Run it against a candidate with no remote and the map — the whole product of an escalated generate — ends up somewhere the repository does not track its work. The same held when step 6 chose the tracker by asking; shipping the answer in the payload removes the question without removing the ordering it forced. The cost is that a generate abandoned after this point leaves an empty repository behind; say so at the gate.

An invocation that forbids contacting GitHub does not skip this step, it stops at its gate: present the same lines, perform none of them, and record what would have run. Everything after then proceeds against a candidate with no remote — the one state the rest of this section does not otherwise produce. Step 5 has no repository to configure and no branch to probe, step 6 finds the payload's `docs/agents/` present and skips as it always does but has no repository to create the labels on, step 7 cannot chart at all — the tracker doc resolves the repository from `git remote -v` and there is no remote, so `gh` has nothing to answer — and step 11 stops at its own gate the same way. Say so when reporting the plan: the map has no home until the repository is created, which is the one thing this path cannot establish. Do not fall back to a local-markdown map to have somewhere to write it. The payload records GitHub Issues, and charting into `.scratch/` because a remote is missing produces exactly the map nobody finds again that ordering the repository first exists to prevent. Report the result as a plan, never as a generate that reached GitHub.

### Step 5 — Configure the repository settings

Configure supported settings after the default branch exists: Dependabot alerts/security updates, push protection where available, the merge commit as the only merge method, automatic head branch deletion, and a branch ruleset appropriate to the repository. Confirm plan/visibility limitations instead of treating API success as proof a feature is active.

Adopting `CODEOWNERS` changes what "appropriate" means here. It is the only addon finished by a repository setting rather than by an edit: without a rule requiring code owner review, the file requests a reviewer and nothing waits for the answer. Enabling it is not the safe default it looks like, for the reason its manifest entry gives — ask.

All four merge settings are applied unconditionally here, not collected as preferences in step 2, leaving the merge commit as the only method. Each is offered on every plan, so none needs a plan/visibility check first. `scripts/repo-settings` carries the reason for each.

```bash
gh api -X PATCH repos/<owner>/<name> \
  -f allow_merge_commit=true \
  -f allow_squash_merge=false \
  -f allow_rebase_merge=false \
  -f delete_branch_on_merge=true
```

One call, not four. GitHub refuses to leave a repository with no merge method enabled, so turning squash and rebase off against a destination that already has the merge commit off is rejected when the three are sent separately and accepted when they arrive together. `allow_merge_commit=true` is therefore not a no-op on a repository that looks fine — it is what makes the other two writable.

**Each of the two routes to these settings has its own field names, and neither route rejects the other's.** REST — `gh api repos/<owner>/<name>` and the `PATCH` above — names them `allow_merge_commit`, `allow_squash_merge`, `allow_rebase_merge`, `delete_branch_on_merge`. The GraphQL-backed `gh repo view --json` names the same four `mergeCommitAllowed`, `squashMergeAllowed`, `rebaseMergeAllowed`, `deleteBranchOnMerge`. Ask either route for the other's names and every field comes back `null` rather than an error, which reads exactly like a repository with all four settings off — so the wrong spelling produces a confident wrong answer that survives being checked. The underscored spelling is REST's and the camel-cased one is `gh repo view`'s; name the endpoint and its field set together wherever either is written down.

Read the result back with the repository's own `scripts/repo-settings check` rather than hand-rolling `gh api` calls. It already separates the two ways a setting reads as absent: `security_and_analysis` is missing both for a non-admin and for a plan that does not offer the feature, and it checks `.permissions.admin` to tell those apart. A hand-rolled check that misses this reports a plan limitation as a disabled setting.

Its output is the evidence for the settings section of the report, and `not offered for the plan` is a distinct outcome from disabled — do not collapse them.

**A required status check is named by its check run, not by its workflow job id.** GitHub matches every `required_status_checks[].context` the ruleset names against the name a check run reports, which is the job's `name:` where the workflow sets one and the job id only where it does not. The payload sets both on every job, so the two always differ, and the contexts to require are what the runs report:

| Workflow | Contexts its runs report |
| --- | --- |
| `ci.yml` | `CI` |
| `security.yml` | `Security` |
| `codeql.yml` | `Code scanning enabled`, `Detect languages`, and `Analyze <language>` once per detected language. On a destination that is not public the first passes and the other two are skipped |
| `release.yml` | `Release` |

Require `ci` rather than `CI` and nothing ever reports that context, so it stays pending for the life of the repository. That failure is invisible from every angle the flow otherwise checks: creation returns 201, the ruleset reads back `active`, `scripts/repo-settings check` passes it, the probe above is rejected exactly as it should be — and the default branch is simply never mergeable, with nothing anywhere naming the misspelling as the cause. Require only contexts a run on this repository has actually reported: `codeql.yml`'s analyze leg is one context per language and `release.yml` does not run on a pull request, so neither belongs in a rule gating one. A gated `codeql.yml` leg is not that trap: on a destination that is not public `Detect languages` reports a completed check run with conclusion `skipped` under the same name it reports when it runs, rather than never reporting. The analyze leg reports its name unexpanded when skipped, which is a second reason it does not belong in a rule.

Ruleset creation can also be refused outright, and that is a different outcome from a ruleset that does not bind. A repository on a plan that does not offer rulesets returns 403, so there is no 201 to be suspicious of and the refusal is itself the measurement: record `not offered for the plan` and do not probe. Pushing anyway learns nothing the 403 has not already said, and an unprotected branch does not reject it — the probe commit lands on top of step 4's empty root and becomes the default-branch tip, with nothing verified and a commit that only a force-push removes. Probe only where creation returned 201.

A ruleset that was accepted is not a ruleset that binds. Creation returns 201 either way, so prove enforcement rather than inferring it: put a throwaway commit on the default branch, push it directly, and require the `GH013` rejection. An unprotected branch accepts that push, which is the finding.

```bash
git commit --allow-empty -m "chore: ruleset probe"
git push origin <default-branch>
git update-ref refs/heads/<default-branch> origin/<default-branch>
```

The probe is a commit on the default branch and a direct push to it, which is exactly what `no-commit-to-branch` and `protect-branch` exist to refuse. Step 4's note above applies to it unchanged, including the explicit confirmation that bypass needs: a resumed generate reaches this step with both hooks installed. Do not resolve a refusal by skipping the probe, which reports an unverified ruleset as verified.

Make the probe empty and rewind it with `update-ref` rather than `git reset --hard`. The materialized payload is sitting untracked in the candidate's own worktree, and a hard reset against an empty base takes the working tree with the probe.

That rewind is local, and it removes the probe only where the push was rejected. Where the push was accepted, `origin/<default-branch>` is the probe commit, so the rewind syncs to it rather than undoing it and the commit stays on the remote default branch. That is the finding, and it is a failed verification: stop under [Failure and recovery](lifecycle.md#failure-and-recovery), name the repository and say it carries the probe commit, and leave removing it to a decision at a gate. Removing it means force-pushing the default branch, which is not an operation to perform on the way past.

### Step 6 — Configure the repository for the engineering skills

Configure the repository for the engineering skills. The payload ships `docs/agents/issue-tracker.md`, `docs/agents/domain.md`, and `docs/agents/triage-labels.md`, so the candidate materialized at step 3 already carries what this step used to collect. Confirm all three are present, skip `/setup-matt-pocock-skills`, and report the step as skipped for the collecting and file-writing it used to do.

What remains is the one thing a shipped file cannot do for itself: create the labels it names, on the repository step 4 created. This is the write that gate authorized, and nothing else in the lifecycle performs it — `/setup-matt-pocock-skills` never created a label either, it only ever wrote the file recording their names.

```bash
existing=$(gh label list --limit 1000 --json name --jq '.[].name')
for label in bug enhancement needs-triage needs-info ready-for-agent ready-for-human wontfix \
             wayfinder:map wayfinder:research wayfinder:prototype wayfinder:grilling wayfinder:task; do
  present=$(grep -ixF -- "$label" <<< "$existing" | head -n 1 || true)
  if [[ -z "$present" ]]; then
    gh label create "$label"
  elif [[ "$present" != "$label" ]]; then
    gh label edit "$present" --name "$label"
  fi
done
```

Run the loop only where the tracker is the host. `docs/agents/issue-tracker.md` is what says which it is, and a destination recording a tracker that is not GitHub takes no label creation at all: the labels belong to whatever that file names, and creating GitHub labels for a repository tracked elsewhere writes a vocabulary nothing reads. Report the step as `none created` with that as the reason.

Twelve labels: the seven roles `docs/agents/triage-labels.md` records, `wayfinder:map`, and the four `wayfinder:<type>` labels `docs/agents/issue-tracker.md` names. Create them without descriptions rather than restating either file's here, where the two would drift. The map label alone is not enough: a map's tickets each carry a type label, so a repository given only `wayfinder:map` runs the wayfinding skill exactly as far as its first map and then fails on the first ticket create. Create only what is missing. GitHub ships `bug`, `enhancement`, and `wontfix` on a new repository with their own descriptions and colors, and a destination that already has content may carry more; overwriting those is a change nobody asked for.

The guard matches case-insensitively because the host does. A destination carrying `Bug` passes a `grep -qxF` guard as absent, the create then fails on a name GitHub considers taken, and under `set -e` the step aborts with every later role silently uncreated. A case variant is therefore a rename to the payload's spelling, not a skip: a label is one object with a stable id, so the rename carries the id and every issue already wearing it keeps the label under the new name. It is never forced, which is what leaves the host's own description and color intact; only the name changes. The alternative, keeping the destination's spelling and rewriting `docs/agents/triage-labels.md` to match, is rejected: that file ships identical to every repository built from this payload, and editing it per destination is how a retrofitted repository's tracker vocabulary comes to differ from a generated one's.

The rename is the payload's file deciding, so it happens only where the payload's file is the one in force. Where the destination kept a `triage-labels.md` of its own under the collision rules, that file names the vocabulary and its spellings are the correct ones: create what it names and rename nothing.

The rename has a named cost, and it is not reversible by the step that caused it. Label *search* is case-sensitive even though label *creation* uniqueness is not, so a saved search, a workflow filter, or a skill pinned to `Bug` silently stops matching once the label is `bug`: no error anywhere, just an empty result. Report every rename in the final report with both spellings, so the destination's owner can repoint whatever was pinned to the old string.

Invoke `/setup-matt-pocock-skills` with the Skill tool only when a file is genuinely missing, or when the invocation asks for something the payload does not record — a tracker other than GitHub Issues, or a label vocabulary the destination already uses. Invoke it; do not answer for the user and do not reproduce what it does by hand. It is the source of truth for its own questions, and a copy of them here goes stale the first time it changes. Do not predict what it will ask: it explores first and asks only what exploration leaves open, and what that leaves open depends on the candidate's contents and on which sibling skills are installed on the machine — neither of which this contract can know, and the second of which is not a fact about the repository at all.

Running it overwrites what the payload shipped, and that is the requested outcome rather than damage — but it is also why the default is to skip. Where the `triage` skill is installed on the machine it rewrites `docs/agents/triage-labels.md` with five canonical roles, against the seven the payload's file records; where it is not installed it writes no label file at all. It may also write a summary of what it just chose into the root `CLAUDE.md`. The payload ships no section there pointing at `docs/agents/` — every consumer reads those files by path — so whatever appears is that skill's own addition. Where it runs, step 8 rewrites that same file's Child Index and must leave that addition intact, and step 10 accounts for whichever paths it wrote.

Confirming the files is order-independent — it reads the candidate on disk and depends on nothing steps 4 and 5 did. Creating the labels is not: it writes to the repository step 4 created, and step 7 fails without it. That is what keeps this step where it is rather than anywhere before step 4.

### Step 7 — Derive the application boundaries

Derive the application boundaries — run [Wayfinding](wayfinding.md) here. Two questions settle it for most repositories; against the triggers that section names, hand the decomposition to `/wayfinder` and stop as [Handing off to `/wayfinder`](wayfinding.md#handing-off-to-wayfinder) directs.
Do not render a root manifest, even for a language wayfinding selected. Wayfinding establishes which constraint binds; it does not establish a package manager, a version, or a project layout, and none of those follow from a choke point. It also reasons rather than measures — the reference is explicit that an unmeasured constraint and an absent one are indistinguishable until something measures — so a rendered manifest asserts more confidence than wayfinding produced. A wrong guess is worse than an absent file, the same reasoning `.github/dependabot.yml` follows in listing only the two manifests the template itself ships. A generated repository with no manifest is reported honestly by `scripts/ci` as nothing to check yet, with every check becoming required the moment one is added. The first real commit brings the manifest.

Say so in the handover: the root manifest is what makes a package visible to the checks, and a manifest nested under `apps/` instead is invisible to all of them. `scripts/doctor` fails on that shape rather than passing over it.

Name in the same handover what that manifest owes, from [Tools the first manifest must declare](lifecycle.md#tools-the-first-manifest-must-declare) — the tools the adapters dispatch for the language wayfinding selected, and the three languages that owe nothing. An undeclared tool is not a quieter check: it reports `unavailable`, which fails the run the way a real failure does.

### Step 8 — Personalize the candidate

Personalize the candidate:
- create one `apps/<name>/` per deployable wayfinding established. Move `apps/app-name` to the first (do not copy it) and replicate its skeleton — `src/` and `.unit.json` — for each one after that. Verify `apps/app-name` is absent afterwards and update every reference. One deployable is the ordinary case and needs no replication;
- leave each `.unit.json` at the shipped `run: none, ships: {kind: none}`. Wayfinding establishes boundaries, not lifecycle: whether a deployable runs until stopped and whether it ships a binary are facts the first real commit brings, the same reasoning that keeps a root manifest unrendered above. A unit missing the file entirely fails `scripts/structure` on the first commit, so the file ships declared and honest rather than absent or guessed;
- write one ADR per deployable recording its choke point and language, as [Wayfinding](wayfinding.md) directs;
- replace the root `CLAUDE.md` bootstrap Child Index with repository-specific content, carrying the wayfinding result into it: each deployable, what it is for, and the language it is written in. The ADRs record why that language was chosen; `CLAUDE.md` is where an agent reads what the repository is before touching anything, and a Child Index naming the apps without saying what each one is leaves the boundaries derivable only from a directory listing. The shipped index already lists `scripts/CLAUDE.md`, which the payload carries; that entry stays in the rewritten index. Read the file back afterwards and confirm it survived. Nothing else verifies that: step 10 compares paths rather than content, and the file exists either way. Where step 6 ran `/setup-matt-pocock-skills`, that skill may have added a section of its own to the file; replacing the Child Index must leave it intact, and the same read-back check applies;
- initialize `docs/LESSONS.md` metadata and remove generation placeholders while retaining its durable writing guidance. Set `generated.by` to the actual author — the repo-builder agent, not the operator on whose behalf it ran — and capture `generated.at` from the real clock (e.g. `date -u +%Y-%m-%dT%H:%M:%SZ`) at the moment of writing rather than composing a plausible-looking value; a rounded time such as midnight is a placeholder wearing a valid format, not a captured one;
- keep `docs/adrs/0000-template.md` as the reusable ADR template;
- create `.repo-template.json`;
- append the derived language entries to `.github/dependabot.yml`, as [Dependabot entries follow the manifests present](lifecycle.md#dependabot-entries-follow-the-manifests-present) directs. Into an empty destination the derived set is empty and the payload's file lands unchanged, because step 7 renders no root manifest and the first real commit is what brings one. Into a destination that already had content it is whatever that content brought, derived here rather than in the replacement above so there is one place the file is written from destination evidence;
- render feature choices honestly, and record no visibility: it is live-readable and every decision turning on it reads the API, as [Manifest](lifecycle.md#manifest) directs. `codeql.yml` lands whatever the destination's visibility, as [Code scanning lands everywhere and decides at run time](lifecycle.md#code-scanning-lands-everywhere-and-decides-at-run-time) directs, so `generation.features` takes no entry for it.

### Step 9 — Run the candidate's checks

Install the candidate's pre-commit hooks by the shared recipe at [Working hooks in a candidate](lifecycle.md#working-hooks-in-a-candidate), which names generate's scope and verifies the install by its outcome. Then stage the candidate and run its documented checks as [Running the destination's checks](lifecycle.md#running-the-destinations-checks) directs. Git is already initialized and its remote already set, from steps 3 and 4. Staging matters twice over here: step 10 reads the tracked paths this stage produces.

What makes that outcome check worth the line here is what a missed install costs on this flow specifically: the candidate ships with no hooks, no secret scan, and no branch protection, and every later check still passes anyway, because each of them is a command this step runs directly rather than a hook git fires. `scripts/doctor` is what distinguishes the two: it reports `pre-commit pass` only when every hook type the config asks for is present in the directory git will actually consult. A `FAIL` naming missing hooks here is this step's failure, not the candidate's, and [Running the destination's checks](lifecycle.md#running-the-destinations-checks) carries the remedy. Do not publish a candidate whose hooks did not install.

### Step 10 — Verify the file list

Verify the file list, not only the content. Compare the payload's tracked paths at the source commit against the candidate's, and account for every difference as intended or as a defect. A file the payload ships and the candidate lacks is invisible to every check, because a check reads content and absence has no runner. Compare against the working tree as well as the index: a path the destination ignores is present and untracked rather than missing, and `.env` is the one the payload ships that way. Use `git ls-files` for the tracked comparison and `git ls-files -o -i --exclude-standard` for the untracked one; the flags are the whole point, since an ignored path appears in neither the plain form nor `-o --exclude-standard`, and the two disagree about `.env` in the direction that reads as missing. Do not build either list with the file-discovery tools — `.env` matches a `permissions.deny` rule, so Glob and Grep omit it and a listing built from them reports it missing when it is there.

The candidate also carries paths the payload does not ship, and each is an intended addition rather than a stray: `.repo-template.json` and the ADR at `docs/adrs/NNNN-<slug>.md` from step 8, `docs/adrs/index.md` regenerated from that ADR by the payload's own `adr-index` hook, and every `apps/<name>/` past the first from step 8. None of them is ignored, so they appear in the tracked comparison as candidate-only paths — the same shape a stray file has, which is why the account names them rather than counting them. `docs/adrs/index.md` is the one no step decides to write: the hook is `always_run`, so step 9's checks regenerate it from whatever ADRs step 8 wrote and fail until it is staged. It appears because a hook produced it, not because a step chose it. `docs/agents/` is not on this list: the payload ships all three files, so they arrive as payload paths and match. A repository where step 6 did run and settled on local markdown carries its `/wayfinder` map under `.scratch/` too, and that also ships: tracking issues as files in the repository is what that answer chose.

Then prove the copied files are copies as [Reviewing the pull request](reporting.md#reviewing-the-pull-request) directs, and read the authored surface it leaves. Do this here rather than after step 11, and read it closely: a bootstrap generate merges its own pull request at step 12, so this is the only reading that personalized surface gets.

### Step 11 — Publish the candidate

Publish the candidate, at the [remote action gate](lifecycle.md#remote-action-gates). Present the local diff, the file-list reconciliation, the check results, the settings state, and the exact pending commands. Then branch from the empty base, add the entire candidate and manifest, commit, push, and open a PR. Supply an explicit PR body. The reason is that this flow already holds the content the body needs — the diff, the reconciliation, the check results — and not that the base lacks a template to render: that is true of a bootstrap generate alone, and reading it as the general reason gets the rule wrong for every flow whose base does carry one. The host renders `PULL_REQUEST_TEMPLATE.md` from the base branch, and an explicit body suppresses it entirely, so fill the body against that template's own sections wherever the base has one.

### Step 12 — Verify the published repository

Verify the remote default branch, PR base/head, URL, settings state, and available checks. Do not merge.

A pull request with no checks means the workflows are unverified, never that they passed. Establish which one it is before reporting:

```bash
gh api repos/<owner>/<name>/commits/<head-sha>/check-suites --jq '[.check_suites[].app.slug]'
```

No GitHub Actions suite means no run was ever dispatched. Check [githubstatus.com](https://www.githubstatus.com/) before treating that as a defect in the generated repository — dispatch and registration are separate services, and an outage suppresses runs while every permissions and workflow API still reports healthy.

Note that `/actions/workflows` lists the default branch only, so it reads zero on a first-generation PR whose default branch has no `.github/` yet. That is expected, not evidence.

Once those checks are green, read `mergeable` and `mergeStateStatus` as a pair, under [A written ruleset is proved satisfiable, not merely present](lifecycle.md#a-written-ruleset-is-proved-satisfiable-not-merely-present). Step 5's probe proved the ruleset binds; this is the separate question of whether it can ever be satisfied, and the two failures look identical from the settings state. A bootstrap generate owes the read before the merge below, not after — `MERGEABLE`/`BLOCKED` is the reason the merge will refuse, and the required contexts step 5 wrote are where it is repaired.

A bootstrap generate is the one case where "do not merge" inverts. The destination's default branch is still the empty root commit, so no worktree can be created against it to review the PR before it merges — `git worktree add` against an empty tree checks out nothing, and a hook that expects the repository's own files (a missing `.pre-commit-config.yaml`, for instance) then fails on an empty checkout that was never the defect. Once checks pass, repo-builder may merge this one pull request itself, gated the same as any other remote action: present it as an explicit action against this exact repository and obtain confirmation before running it. The exception is scoped to this bootstrap PR alone — update, adopt, and a generate into an already-populated destination all have a destination worktree available for ordinary review, so their pull requests are never merged by repo-builder.

Having merged it, verify the default branch. This is the only merge in the lifecycle, and it is the first time the repository's workflows run against `main` with content in it — a green pull request does not carry over, because the PR ran against a merge of an empty base and `main` afterwards is a different commit with a different trigger. Read that commit's check-suites the same way step 12 reads the PR's, keep the same distinction between a failing run and no run dispatched, and report the result. A red default branch immediately after generation is a finding to hand over, not a state to leave unmentioned because the pull request was green.

## Into a repository that already has content

The steps above assume an empty destination. A destination with existing content is a generation whose collisions are decided by hand, and it needs its own rules:

Step 4 creates nothing here — the repository is already there. Step 5 splits, and the split is the rule for this whole path: the four merge settings are applied exactly as written, and everything else it configures is reconciled rather than applied, since a setting someone deliberately turned off is destination intent the same way a file is.

The merge settings are not in that category. They are what the payload's commit-message rules and CI provenance rest on — a squash takes its message from the pull request title, which `commit-msg` never sees, and a rebase replays the branch as commits CI never ran — so a destination keeping them is a destination where the payload ships rules that do not bind. Name their current values at the gate rather than folding them into the settings line: this is the one place a generate overwrites a hosted setting someone chose, and the gate is where that gets said out loud. A destination whose owner declines them is not a failure to route around — record it in `generation.features` as the deliberate absence it is, the same as an omitted `codeql.yml`, and report which of the payload's guarantees do not hold there.

Step 6 is where a destination's own `docs/agents/` is a collision like any other, decided per file under rule 3 below rather than for the directory as a whole — a destination may carry `issue-tracker.md` and not `domain.md`, and the two collide independently. A destination file recording a tracker or a label vocabulary is destination intent and is kept; the payload's copy of that one file is then what does not land. Do not run `/setup-matt-pocock-skills` to break the tie and do not delete either copy to make room. Where the destination keeps its own `issue-tracker.md`, the labels step 6 creates are the ones that file names rather than the payload's, and a destination recording a tracker that is not GitHub takes no label creation at all.

1. Establish that the destination is a clean worktree, and enumerate every payload path that already exists there before writing anything.
2. Apply non-colliding payload files as ordinary additions.
3. For each collision, decide between the payload version, the destination version, and a merge — then state the decision and the reason per file. Verify afterwards that no destination-only content was dropped, naming what was preserved.
4. Never delete destination content to resolve a collision. A payload path that cannot be reconciled is a conflict to report, not a file to overwrite. The two exemptions are stated by path in rules 6 and 7 below, and they are exemptions because nothing there is resolved as a collision at all; for every other path this rule is absolute.
5. Record every collision a *managed* destination path won in `generation.overrides`, one `{path, reason}` entry each, as [Overridden paths](lifecycle.md#overridden-paths) specifies. A collision won by a path the ownership array makes product takes no entry and is reported instead, by name and with the reason: ownership already grants the destination that path, and an entry on one is refused at preflight. A collision the payload's version won landed the payload file and is an ordinary copy; it takes no entry.
6. Replace `.github/` whole rather than deciding it per file, as [The automation directory is replaced, not reconciled](lifecycle.md#the-automation-directory-is-replaced-not-reconciled) directs, which names the paths and why none of it is declinable. Record every superseded path in `generation.superseded` with what it did, and name them all in the report. Rules 3, 4, and 5 do not reach inside this prefix; they govern every path outside it unchanged, `docs/agents/` included.

   The replacement lands the payload's `.github/dependabot.yml`; step 8's derivation then appends the entries the destination's own manifests earn, which on this path is the only way it gets any.
7. Retire a destination gate script the payload's check surface fully covers, repointing its callers and recording it in `generation.superseded` with `"retired": true`; report the script and each repointed caller by path. A partially-covered script survives as a reported conflict naming the duplicated parts. [Retiring a covered gate script](lifecycle.md#retiring-a-covered-gate-script) has the split and why the second half is not this skill's to cut.
8. Do not create the placeholder application when the destination already has its own application boundaries. Record the real ones in `generation.applications`. Wayfinding still runs, but against what is there: it names the choke point each existing deployable already answers to rather than proposing a new decomposition, and it writes an ADR only where the repository has none for that deployable. A generation is not the occasion to re-cut boundaries someone is already shipping against.

Ownership still governs what a later update may touch, and a hand-merged file is managed content whose destination edits are real intent. Classify deliberately: marking a whole tree product to protect it also freezes it.

### Step 13 — The first prompt

The first prompt is written for a reader this session never speaks to: whoever opens the first working session in a fresh clone of the new repository. Everything this session knows about that repository's initial state dies with it otherwise — which checks are red on purpose, what the tracker holds, what a clone still has to install — and the next session rediscovers each one as a defect. Emit it as a fenced block so it can be copied whole, fill every placeholder from what actually happened rather than from this shape, and drop a line whose condition did not arise rather than shipping it empty. An update and an adopt write none: the destination already has working sessions. On a generate stopped at the wayfinding handoff the resume belongs to the operator of this session, not to a new one, so Pending action carries it and this section is still omitted.

It is the report's last section, **First prompt**, added after **Pending action** at the same heading level as the shape's own sections, and its first line is the instruction to the reader:

Copy this into the first session opened in a clone of the new repository:

```text
Work <owner/repository>. Clone it and install the hooks: `pre-commit install`, or, if that
refuses because a `core.hooksPath` is already set on this machine, `pre-commit
init-templatedir` into a directory of its own with `core.hooksPath` pointed at it. Nothing
else installs them, and without them commits land unattributed and unchecked. Then read the
root `CLAUDE.md` before touching anything.

The plan of record is <the issue tracker named in docs/agents/issue-tracker.md>, not this
message. Open tickets: <count>. First with no open blocker: <#n — title>. Start there.

Expected initial state, not defects: <the absent root manifest scripts/doctor fails on |
the skipped CodeQL detect and analyze legs on a private destination, per lifecycle.md
"Code scanning lands everywhere and decides at run time" | none>.

The first root manifest owes the checks their tools: <the declarations for the selected
language, from lifecycle.md "Tools the first manifest must declare" | none, <language>
declares no tools>. An undeclared tool reports `unavailable`, which fails the run.

Branch before you commit; a commit made on `main` is refused at the hook.
```

The manifest sentence's lead-in, `The first root manifest owes`, is what the generation eval reads the handover for; rewording it updates the eval in the same change.
