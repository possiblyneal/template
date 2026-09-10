# What GitHub does for the hosted writes conversion needs

Research for [issue #107](https://github.com/possiblyneal/template/issues/107), under the map at
[#104](https://github.com/possiblyneal/template/issues/104). Facts only; the decisions that consume
them are separate tickets.

Every behaviour below was confirmed twice: against GitHub's own REST documentation, and against a
throwaway repository under `possiblyneal`. Where the two disagree, or where the documentation is
silent, that is called out — several of the facts this ticket turns on are **not documented anywhere**
and exist only as probe output.

**Probe environment.** Account `possiblyneal`, a personal account on the **free** plan
(`gh api user --jq .plan` → `{"name":"free","collaborators":0}`). Token is a classic OAuth token
carrying `repo`, `delete_repo`, `workflow`, `admin:org`. `gh` 2.46.0. Probes ran on
`possiblyneal/conversion-probe-rename` (private) and `possiblyneal/conversion-probe-public` (public);
both were deleted after the run. Neither `possiblyneal/template` nor any of the four reference
repositories was written to.

The plan matters for every answer below, and **visibility matters as much as the plan**. Several
features read as "unavailable" on a private free repository and work normally on a public one.

---

## 1. Renaming a default branch from `master` to `main`

### The command

There is no `gh` porcelain for this. `gh repo rename` renames the *repository*. The only route is the
REST endpoint:

```bash
gh api -X POST repos/<owner>/<name>/branches/master/rename -f new_name=main
```

### Permissions

Per the [REST reference for Rename a branch](https://docs.github.com/en/rest/branches/branches?apiVersion=2022-11-28#rename-a-branch):

- push access to the branch is the baseline;
- **the default branch additionally requires admin or owner permission**;
- a fine-grained token additionally needs `administration:write`.

Per [Renaming a branch](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-branches-in-your-repository/renaming-a-branch),
any branch covered by branch protection or a repository-level ruleset also requires admin, and a
branch covered by an *organization* or *enterprise* ruleset typically requires an org or enterprise
admin. **This is the first place conversion can be refused for a reason no local check can see**: a
destination inside an org whose rulesets cover `master` cannot be renamed by a repository admin
unless the org has opted into allowing it.

The classic `repo` scope on an owned repository is sufficient. Probe confirmed.

### What GitHub retargets automatically

Confirmed by probe on `conversion-probe-public`, which was set up with default branch `master`, an
active ruleset, classic branch protection, and two open pull requests:

| thing | before | after `master` → `main` | verdict |
| --- | --- | --- | --- |
| `repos/{o}/{r}.default_branch` | `master` | `main` | retargeted |
| open PR with **base** `master` | `base: master`, OPEN | `base: main`, **still OPEN** | retargeted |
| open PR with **head** `master` | `base: target`, OPEN | `base: target`, **CLOSED** | **destroyed** |
| classic branch protection rule | pattern `trunk` | pattern `main` | retargeted |
| ruleset condition `~DEFAULT_BRANCH` | binds `master` | binds `main` | retargeted |
| ruleset condition `refs/heads/main` (literal) | binds `main` | **still `refs/heads/main`**, binds nothing | **silently orphaned** |
| `.github/workflows/*.yml` content pinned to `master` | `branches: [master]` | `branches: [master]` | **not rewritten** |
| `refs/heads/master` on the remote | exists | 404, gone from `git ls-remote` | deleted, no redirect |

Two of those rows are the findings.

**A pull request whose *head* is the renamed branch is closed, not retargeted.** The docs state this
plainly ("If the renamed branch is the head branch of an open pull request, this pull request is
closed") and the probe reproduced it: PR #2 went to `CLOSED`, and its `headRefName` still reads
`master` for a ref that no longer exists. That pull request is not recoverable by reopening — its
head ref is gone. For `medical-researcher`, the reference repository whose default branch is
`master`, conversion must enumerate open pull requests **by head ref, not only by base ref**, before
renaming. A PR from `master` into a long-lived integration branch is an unusual but entirely legal
shape, and conversion would destroy it without a word.

**A ruleset that names the branch literally does not follow the rename.** The documentation's claim
that "Branch protection policies are also updated" is true for *classic* branch protection — the
probe watched a rule's pattern rewrite itself from `trunk` to `main` — and is **false for rulesets
with a literal `refs/heads/<name>` condition**. Those keep pointing at a name that no longer exists,
`rules/branches/<new>` returns `[]` for them, and nothing reports the breakage. A destination
protected that way emerges from conversion *less* protected than it went in, with a ruleset that
still shows as active in the UI. Only `~DEFAULT_BRANCH` follows, because it is resolved dynamically
rather than stored.

### What breaks

- **Existing clones.** The docs are explicit: "GitHub does not perform any redirects if users perform
  a `git pull` for the previous branch name." Probe confirmed — `git ls-remote` after the rename shows
  `refs/heads/main` and no `refs/heads/master`, so a collaborator's `git pull` fails with
  `couldn't find remote ref master`. The documented repair is four commands the collaborator runs
  themselves (`git branch -m`, `git fetch origin`, `git branch -u`, `git remote set-head origin -a`).
  Nothing conversion does can perform this for them.
- **Workflow files.** "GitHub Actions workflows do not follow renames." Probe confirmed the file
  content is untouched. Every `on.push.branches: [master]`, `on.pull_request.branches: [master]`, and
  every `github.ref == 'refs/heads/master'` comparison in the destination's own CI is dead after the
  rename and must be edited as part of the conversion diff. This matters directly for
  `media-encoder`, which carries `.github/workflows/ci.yml` and `scripts/ci.sh`.
- **Raw file URLs.** Web URLs redirect; `raw.githubusercontent.com` URLs do not. A README badge or a
  documentation link pinned to `master` breaks silently.
- **Anything consuming the branch as an action reference.** `uses: owner/repo@master` breaks for every
  downstream consumer.

### The rename is asynchronous and reads are eventually consistent

The REST reference warns that "the branch rename process might take some extra time to complete in
the background." The probe hit this three separate times:

- immediately after renaming `main` → `trunk`, `repos/{o}/{r}.default_branch` still read `main`, and
  `rules/branches/trunk` returned `[]`; both were correct a few seconds later;
- immediately after the rename, `branches/trunk/protection` returned a full protection body for a
  branch that no longer existed; it returned 404 shortly after.

**A conversion step that renames and then verifies in the same breath will read a stale answer and
may report a correct rename as a failure, or an orphaned ruleset as intact.** Verification after a
rename must poll, not read once. Nothing in `generate.md` or `lifecycle.md` currently says so.

---

## 2. Merge settings on a repository that already has content

`generate.md:84` records that the four settings have to be sent in one call because GitHub refuses to
leave a repository with no merge method enabled. **The constraint is real and reproduces exactly on an
existing repository with content, non-default settings, an open pull request, and issues.** The
prose is slightly wrong about the failure mode in a way that matters.

### The constraint

It is **not documented**. The [REST reference for Update a repository](https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28)
describes `allow_merge_commit`, `allow_squash_merge`, and `allow_rebase_merge` as independent booleans
with no interaction, and [Configuring commit merging for pull requests](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/configuring-commit-merging-for-pull-requests)
never mentions it either. The only source is the API's own rejection:

```
HTTP 422 Validation Failed
{"resource":"Repository","field":"merge_commit_allowed","code":"invalid",
 "message":"Sorry, you need to allow at least one merge strategy. (no_merge_method)"}
```

The rule is: **any `PATCH` whose resulting state would leave zero merge methods enabled is rejected**.
It is evaluated on the whole resulting state, not on the fields in the request, which is exactly why
one call works.

### The correction to `generate.md:84`

The reference says the three "sent separately" are rejected. Probe sequence, starting from
`{merge_commit: false, squash: true, rebase: true}` — a destination that has deliberately turned the
merge commit off, which is the realistic starting state:

| call | result | state after |
| --- | --- | --- |
| `PATCH allow_squash_merge=false` | **200 OK** | `{m:false, s:false, r:true}` |
| `PATCH allow_rebase_merge=false` | **422 `no_merge_method`** | `{m:false, s:false, r:true}` — unchanged |

**The first of the two separate calls succeeds.** It is only the last one, the one that would empty
the set, that is refused. So a step that sends them one at a time and stops on the first failure does
not leave the destination untouched — it leaves it **half-applied**, with squash disabled and rebase
still enabled, which is a state nobody chose and which the payload's commit-message rules do not hold
under. That is a worse outcome than the reference's prose implies, and it strengthens rather than
weakens the one-call rule.

The failed `PATCH` itself is atomic — the read after the 422 showed the pre-call state exactly. GitHub
does not partially apply a rejected request.

### What works

Both of these succeed, on an existing repository, in any starting state:

```bash
# one call, as generate.md directs
gh api -X PATCH repos/<owner>/<name> \
  -F allow_merge_commit=true -F allow_squash_merge=false \
  -F allow_rebase_merge=false -F delete_branch_on_merge=true
```

```bash
# or two calls, merge commit first
gh api -X PATCH repos/<owner>/<name> -F allow_merge_commit=true
gh api -X PATCH repos/<owner>/<name> -F allow_squash_merge=false -F allow_rebase_merge=false
```

`allow_merge_commit=true` really is what makes the other two writable, exactly as the reference says.

### Other order dependence

- `delete_branch_on_merge` and `allow_auto_merge` carry no constraint and can be sent in any call.
- `default_branch` can only be set to a branch that already exists. Probed: `PATCH default_branch=does-not-exist`
  returns 422 `"The branch does-not-exist was not found. Please push that ref first or create it via
  the Git Data API."` This is order-dependent for conversion — the branch must exist before it can be
  made default — and it is why the rename endpoint exists rather than a `PATCH default_branch=main`
  standing in for it.
- Nothing else in the merge block is order-dependent. Note that the settings are writable on a private
  free repository — none of them is plan-gated, which the reference already states and the probe
  confirmed.
- Both `-f` and `-F` work. `-f` sends the value as a string; probed `-f allow_squash_merge=true` and
  `-f allow_squash_merge=false` and both were applied correctly, so `generate.md`'s `-f` form is
  sound. `-F` sends a real JSON boolean and is the more literal reading of the endpoint.

---

## 3. Creating labels against a repository that already carries its own

### GitHub ships ten default labels, on every repository, including one created without auto-init

A repository created with `gh repo create --private` and no auto-initialization still arrived carrying:

`accessibility`, `bug`, `documentation`, `duplicate`, `enhancement`, `good first issue`,
`help wanted`, `invalid`, `question`, `wontfix`

— each with GitHub's own description and colour. Note `accessibility` is now on that list; the
default set is not the nine most references assume.

Of the eight names `generate.md` step 6 creates, **three collide**: `bug`, `enhancement`, `wontfix`.
The other five (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wayfinder:map`)
are new on any stock repository.

### The two collision behaviours

```
$ gh label create bug
label with name "bug" already exists; use `--force` to update its color and description
$ echo $?
1
```

```
$ gh api -X POST repos/<o>/<n>/labels -f name=bug -f color=ededed
HTTP 422 {"resource":"Label","code":"already_exists","field":"name"}
```

Neither overwrites. `gh label create --force` would, and `generate.md` correctly does not use it —
overwriting GitHub's descriptions and colours is "a change nobody asked for," as the reference says.

### The defect: GitHub's collision check is case-insensitive, `generate.md`'s guard is not

This is the finding for this question.

`generate.md` step 6 guards with `grep -qxF -- "$label" <<< "$existing"`, an exact, case-**sensitive**
match. GitHub's uniqueness check on label names is case-**insensitive**: creating `Bug` on a
repository that has `bug` returns the same 422 `already_exists`.

Probed by renaming the probe repository's `wontfix` to `WontFix` and running step 6's loop verbatim:

```
  -> bug exit=0
  -> enhancement exit=0
  -> needs-triage exit=0
  -> needs-info exit=0
  -> ready-for-agent exit=0
  -> ready-for-human exit=0
label with name "wontfix" already exists; use `--force` to update its color and description
  -> wontfix exit=1
  -> wayfinder:map exit=0
```

The guard did not match `WontFix`, so the loop tried to create `wontfix`, GitHub refused it, and the
label **was not created**. Two consequences:

- As written the loop has no `set -e`, so it prints an error into a wall of output and continues. The
  destination ends up missing one of the seven triage roles, and `/triage` — which per
  `docs/agents/triage-labels.md` creates a missing label rather than substituting the nearest one —
  will hit the same 422 every time it runs.
- Every script under `scripts/` in this repository runs `set -euo pipefail`. If this loop is ever
  lifted into one, that exit 1 aborts the step, and step 7's `gh issue create --label wayfinder:map`
  never runs.

The fix is a case-insensitive guard (`grep -qixF`), and it is cheap. But **a case-insensitive guard
is not the whole answer**, and this is the part no ticket on the map covers: if the destination
carries `WontFix`, the payload's vocabulary and the destination's vocabulary are now two spellings of
one role. `docs/agents/triage-labels.md` already has an answer for this — its "To run under a
vocabulary the tracker already has" section says to replace the role's label string in that file and
say which role it stands for — but nothing in the conversion flow reads that section, and skipping
the create silently leaves the payload's file naming a label that does not exist. **A conversion
against a destination with its own label vocabulary needs a decision about which spelling wins, and
the answer has to be written into the destination's `triage-labels.md`, not just into the label set.**

### A smaller inconsistency, noted rather than resolved

`docs/agents/triage-labels.md:25` shows `gh label create needs-triage --description "Maintainer needs
to evaluate this issue"`. `generate.md` step 6 deliberately creates the labels *without* descriptions,
"rather than restating that file's here, where the two would drift." The two files already disagree
about whether a created label carries a description. Not in this ticket's scope to fix.

### Pagination

The loop reads `gh label list --limit 200`. A destination carrying more than 200 labels would truncate
the guard list and produce the same failure for any label past the cut. None of the four reference
repositories is anywhere near that, so this is a note, not a finding.

---

## 4. Sub-issues and native issue dependencies on a private repository on this plan

**Both are available. Both work. No plan gate, no visibility gate.** Probed on the private free-plan
repository.

### Sub-issues

```bash
gh api -X POST repos/<o>/<n>/issues/<parent>/sub_issues -F sub_issue_id=<child-db-id>
```

Returned 200 with the parent issue body. `repos/<o>/<n>/issues/<parent>/sub_issues` then listed the
child, and the parent's `sub_issues_summary` read `{"completed":0,"percent_completed":0,"total":1}`.
The `sub_issue_id` is the child's numeric **database id**, not its `#number` — as
`docs/agents/issue-tracker.md` already records.

### Native issue dependencies

```bash
gh api -X POST repos/<o>/<n>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>
```

Returned 200. The child's `issue_dependencies_summary` then read
`{"blocked_by":1,"blocking":0,"total_blocked_by":1,"total_blocking":0}`.

The `blocked_by` / `total_blocked_by` split is exactly what `issue-tracker.md` claims: after closing
the blocker, `blocked_by` went to `0` while `total_blocked_by` stayed at `1`, and
`dependencies/blocked_by` still listed the blocker with `"state":"closed"`. **`blocked_by` counts
open blockers and is the live gate; `total_blocked_by` counts all edges ever added.** The frontier
query documented in `issue-tracker.md` is correct as written.

### One caveat for the frontier query

The summary is **eventually consistent**. Read immediately after `gh issue close <blocker>`,
`blocked_by` still returned `1`; a moment later it returned `0`. A frontier query that runs straight
after a resolve — which is exactly what `/wayfinder` does at the end of a session — can see a stale
`blocked_by` and skip a ticket that just became available. It is a missed opportunity rather than a
correctness failure, but it explains a class of "why did it pick nothing" that would otherwise look
like a bug in the query.

### What this means for conversion

Nothing blocks the wayfinding operations on a private destination. This removes the fallbacks
`issue-tracker.md` describes ("Where sub-issues aren't enabled…", "Where dependencies aren't
available…") from consideration for any destination under this account. They remain necessary for a
destination on a different host or under an org with these features disabled.

---

## 5. What `scripts/repo-settings check` can and cannot observe on a private repository

### What it reads

`scripts/repo-settings` fetches exactly five endpoints (`fetch_settings`, lines 44–50) and every
judgment reads that one document:

| key | endpoint | on a **private free** repo | on a **public free** repo |
| --- | --- | --- | --- |
| `repo` | `repos/{o}/{r}` | 200, `security_and_analysis: null` | 200, `security_and_analysis` populated |
| `codeowners_errors` | `repos/{o}/{r}/codeowners/errors?ref={branch}` | 404 (no file) | 404 (no file) |
| `branch_rules` | `repos/{o}/{r}/rules/branches/{branch}` | **403 "Upgrade to GitHub Pro or make this repository public…"** | 200 |
| `protection` | `repos/{o}/{r}/branches/{branch}/protection` | **403, same message** | 200 / 404 |
| `rulesets` | `repos/{o}/{r}/rulesets` | **403, same message** | 200 |

All five confirmed by probe against `conversion-probe-rename` with an **admin** token, so the 403s are
a plan-and-visibility limit and not a permission one.

The `not_offered()` predicate requires status 403 **and** a message starting `"Upgrade to GitHub"`.
The real message is `Upgrade to GitHub Pro or make this repository public to enable this feature.` —
the prefix matches, and the three `not-applicable` verdicts the script produces are correct rather
than accidental.

### Confirming the claims in this repository's `CLAUDE.md`, "Repository settings"

Actual output of `scripts/repo-settings check` against `possiblyneal/template` today:

```
codeowners         pass             no CODEOWNERS file on main, nothing to validate
merge-commits      pass             allow_merge_commit is true on possiblyneal/template
squash-merging     pass             allow_squash_merge is false on possiblyneal/template
rebase-merging     pass             allow_rebase_merge is false on possiblyneal/template
delete-branches    pass             delete_branch_on_merge is true on possiblyneal/template
push-protection    not-applicable   not offered for possiblyneal/template's plan and visibility …
rulesets           not-applicable   not offered for possiblyneal/template's plan and visibility …
```

Where the documented claims **hold**:

- **"Push protection and branch rulesets: unavailable on this plan."** Holds, and the probe sharpens
  it: it is unavailable on a private repository on this plan, and **available on a public one**.
  Rulesets created, bound, and enforced normally on `conversion-probe-public`; classic branch
  protection did too; enabling `secret_scanning_push_protection` succeeded there and returned 422
  `"Secret scanning is not available for this repository."` on the private one. The script's own
  wording ("plan and visibility") is more accurate than `CLAUDE.md`'s ("this plan").
- **"Automatic head branch deletion: enabled."** Holds and is observed — `delete-branches pass`.
- **The merge settings.** Observed, and the four `pass` lines are real reads of the repository.
- **`generate.md`'s note that `security_and_analysis` is missing both for a non-admin and for a plan
  that does not offer the feature.** Holds. Confirmed `null` on the private probe *with* admin, and
  the script's `.permissions.admin` gate (line 224) returns before `judge_push_protection` for a
  non-admin, so the two never collapse into one verdict.

Where they **fail, or are unobserved**:

- **"Dependabot alerts and security updates: enabled" is not observed by anything.**
  `scripts/repo-settings` never reads `repos/{o}/{r}/vulnerability-alerts` or
  `.../automated-security-fixes`, and no other script does either (`grep -rn "dependabot" scripts/`
  returns only `github-parity`'s content exception for `dependabot.yml`). The claim is prose that
  nothing checks. Both endpoints are readable and writable on a private free repository — the probe
  got 204 from `GET /vulnerability-alerts` (already on by default) and 204 from both `PUT`s — so this
  is an unclaimed capability rather than a limitation. On a public repository `security_and_analysis`
  even carries `dependabot_security_updates.status` directly in the repository body the script
  already fetches.
- **"Code scanning: unavailable" is not observed either.** No script reads `code-scanning/alerts`.
  The record lives in `.repo-template.json` under `generation.features` and `scripts/github-parity`
  enforces only that the `codeql.yml` omission is *recorded*, not that code scanning is actually off.
  Probe: `code-scanning/alerts` returns 403 `"Code scanning is not enabled for this repository"` on
  the private repo and 404 `"no analysis found"` on the public one — two different statuses for two
  different meanings, and neither is read.
- **`owner-review` reports nothing at all when there is no `CODEOWNERS` file.** `judge_owner_review`
  opens with `fetched codeowners_errors || return 0` (line 111), so on this repository the check is
  simply absent from the tally rather than reported `not-applicable`. Defensible, but it means the
  check list is not fixed-length: **a destination that already carries a `CODEOWNERS` file produces a
  check that this repository has never emitted.** Three of the four reference repositories should be
  inspected for one before conversion assumes the output shape.

### What this means for an *existing* repository rather than a newly created one

`scripts/repo-settings check` has no notion of a newly created repository. It resolves the repository
from `gh repo view` in the working tree (line 210) and reads live state, so it works identically on a
converted destination. Three things do change:

1. **`not-applicable` stops meaning "we chose not to."** On a generated repository, `squash-merging
   not-applicable` means generation did not run. On a converted destination it may mean the owner
   deliberately enabled squash merging, which `generate.md`'s "into a repository that already has
   content" section already identifies as the one place a generate overwrites a hosted setting
   someone chose. The check reports the same word for both, so the report has to carry the
   before-state, not just the verdict.
2. **The `codeowners` and `owner-review` checks become live.** They are inert here because there is no
   `CODEOWNERS` file. A destination with one gets real findings — including, on a private free
   repository, `owner-review not-applicable` explaining that nothing waits for the requested reviewer,
   which is a genuine downgrade the destination's owner may not know about.
3. **A public destination flips five verdicts at once.** Push protection, rulesets, branch rules,
   classic protection, and code scanning all become available. If any of the four reference
   repositories is public, its conversion report looks nothing like this repository's, and the two
   should not be compared verdict-for-verdict.

---

## Loose ends this research exposed and no ticket covers

1. **A pull request whose head is the destination's `master` is destroyed by the rename.** Conversion
   needs a pre-rename enumeration by head ref, and a decision about what to do when it finds one.
2. **A ruleset with a literal branch condition silently stops binding after a rename.** Conversion
   leaves the destination less protected than it found it, and the current verification would not
   notice. Only `~DEFAULT_BRANCH` conditions survive.
3. **A label vocabulary that differs only in case** needs a decision about which spelling wins and a
   corresponding edit to the destination's `triage-labels.md`. The `grep -qixF` fix alone hides the
   question rather than answering it.
4. **Every post-write verification against GitHub needs to poll rather than read once.** The rename in
   particular is documented as asynchronous, and three separate stale reads were observed. Neither
   `generate.md` nor `lifecycle.md` says so.
5. **The half-applied merge state.** `generate.md`'s prose implies the separate-calls path fails
   harmlessly. It does not — the first call lands.

---

## Probe repositories

Both created for this ticket under `possiblyneal`, both deleted after it:

- `possiblyneal/conversion-probe-rename` — private, default branch `master`, one open PR, GitHub's
  stock labels, three issues, a workflow pinned to `master`.
- `possiblyneal/conversion-probe-public` — public, default branch `master`, an active ruleset, classic
  branch protection, two open PRs (one by base, one by head).
