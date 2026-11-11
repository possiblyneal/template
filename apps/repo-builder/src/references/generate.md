# Generate

Rules from [`lifecycle.md`](lifecycle.md) that a generate needs, stated here so the file is never opened whole; a rule only some generates need sits at the step that triggers it. Each links to its section for the reasoning; read that section only when the statement here is not enough. The reasoning behind the fixed steps is in `docs/adrs/0010-run-generates-fixed-steps-as-commands.md`, which a run need not read.

- **Placeholders.** Quote every `<placeholder>` when substituting, and reject a repository or branch name outside `[A-Za-z0-9._/-]+` before it reaches a shell.
- **Manifest** ([`## Manifest`](lifecycle.md#manifest)). The candidate tracks `.repo-template.json`. `template.commit` is the full lowercase 40-character source commit. Record generation choices that change rendered files or repository settings, and no timestamp, visibility, language or package manager, since the disk or the API answers them. `features` records every departure from the defaults, each key optional; `generation.applications` lists the deployable names wayfinding established and nothing else about them. The `ownership` array is the canonical list in `apps/github-repository-template/src/ownership.json`, read at the source commit, never another repository's array; step 8's command writes it.
- **Checks** ([`## Running the destination's checks`](lifecycle.md#running-the-destinations-checks)). Stage first, since `pre-commit run --all-files` reads the index and passes over unstaged work. Run `scripts/check`, which prints only the Result table and writes the whole run to `tmp/check.log`; on a failing exit read that log rather than re-running. Report passed, nothing to do, runner missing and never ran as four outcomes; skipped or unavailable is never a pass.
- **Remote gates** ([`## Remote action gates`](lifecycle.md#remote-action-gates)). Repository creation, settings writes, pushes and pull-request creation are separate actions, confirmed immediately before unless the invocation authorized those exact actions against this exact repository. A generate reaches two gates: step 4 for the empty repository, its settings, the probe and the tracker writes, with no diff; step 11 for the content push and the pull request. Show only the lines a gate asks for, and perform no remote write it did not list. The only merge is the bootstrap pull request at step 12.
- **Failure** ([`## Failure and recovery`](lifecycle.md#failure-and-recovery)). Stop before further remote actions when intent conflicts or verification fails. A failure at steps 5 to 10 leaves a real repository with no published content, its default branch the empty root commit, or the probe commit where step 5's probe was accepted: name the repository, say what it carries, and say whether resuming or deleting it is next. Keep `template.commit` at the previous version. The wayfinding handoff is a stop, not a failure: report `stopped` and keep the candidate. There is no rollback. Re-invoking the same command is the resume ([`### Resuming`](lifecycle.md#resuming)): re-observe live state and skip what is done; the resume record sits beside the candidate, never inside it.
- **Ruleset satisfiability** ([`## A written ruleset is proved satisfiable, not merely present`](lifecycle.md#a-written-ruleset-is-proved-satisfiable-not-merely-present)), at step 12. Once the pull request's required checks report, read `gh pr view <n> --json mergeable,mergeStateStatus --jq '{mergeable,mergeStateStatus}'`. `MERGEABLE` with `CLEAN` is the rule satisfied; `MERGEABLE` with `BLOCKED` on an all-green pull request is an unsatisfiable ruleset. Report the pair verbatim with the required contexts beside it.
- **Architecture records** ([`## Architecture records live at the root documentation path`](lifecycle.md#architecture-records-live-at-the-root-documentation-path)), at step 8. Every record goes in `docs/adrs/` at the repository root, one about a unit naming it in its `scope` frontmatter; never `apps/<name>/docs/adrs/`, which `scripts/adr-index` does not index.
- **Dependabot** ([`## Dependabot entries follow the manifests present`](lifecycle.md#dependabot-entries-follow-the-manifests-present)), at step 8. `.github/dependabot.yml` lands as the payload's file with one language entry appended per manifest `git ls-files` lists, at that manifest's own directory, carrying `interval: weekly`, `cooldown.default-days: 7` and one group. Into an empty destination there are none, since no root manifest is rendered. Verify by parsing the written file, never by a green check run.
- **Code scanning** ([`## Code scanning lands everywhere and decides at run time`](lifecycle.md#code-scanning-lands-everywhere-and-decides-at-run-time)), at step 8. `codeql.yml` lands at every destination and reads visibility at run time, so nothing branches on visibility or records it. Only a destination that deletes the file records `"codeql": "omitted-by-choice"` under `generation.features`, with that exact value.

Step 9 installs hooks by [Working hooks in a candidate](lifecycle.md#working-hooks-in-a-candidate). Every flow ends in the [Final report](reporting.md#final-report). A destination that already has content also follows [`generate-into-content.md`](generate-into-content.md), from step 1.

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
- **Step 13 — Register the repository in Orca**
- **Step 14 — The first prompt**

A generate runs them in order and reads them in order. A reader needing one step alone — `SKILL.md`, `lifecycle.md`, `wayfinding.md` and `reporting.md` each cite one — reads it with `sed -n '/^### Step 12 /,/^### /p'` rather than opening the whole file. The headings are addresses so that a citation does not cost 30 KB to follow.

### Step 1 — Resolve the source commit and preflight

Resolve the requested source to an exact commit and run:

```bash
python3 apps/repo-builder/src/scripts/preflight.py generate \
  --target <ref-or-commit> \
  --subtree apps/github-repository-template/src/base-repo \
  --destination-repository <owner/name> \
  --default-branch main
```

`--template-repo` defaults to the working directory, this checkout; pass a path only for another clone, never the origin URL. `--default-branch` is the destination's; `--template-branch` is this template's own and defaults to `main`. Pass it only where the source genuinely lives on another branch, and expect a refusal for a commit on none of them: the commit recorded here is the base every later update diffs from, so one off the template's branch generates a repository no update can ever reach.

`generate` validates the source only. It takes the destination as a name, never inspects it, and so cannot tell an empty repository from one with content. Establish that yourself before materializing. Where the destination has content, read [`generate-into-content.md`](generate-into-content.md) now: its rules change steps 4 through 10.

### Step 2 — Collect the unresolved decisions

Collect only unresolved decisions: owner/name, visibility, public-repository files, release behavior, and feature availability. The application boundaries are not among them. They are derived rather than collected, and step 7 derives them once the candidate and the repository exist. Neither are the merge settings: step 5 applies all four unconditionally, so there is no choice here for the step 4 gate to name.

The public-repository files are the repository addons, held back rather than shipped and offered against the conditions the answers to this step have established. Adopt the ones taken as the [Addon adoption](addon-adoption.md) section directs, from this same source commit.

### Step 3 — Materialize the candidate

Materialize the subtree from that exact commit into `tmp/<repository-name>/` with one command, run from this repository:

```bash
python3 apps/repo-builder/src/scripts/generate.py materialize \
  --records tmp/<repository-name>.<first 12 of the commit> \
  --target <commit> \
  --subtree apps/github-repository-template/src/base-repo \
  --destination-repository <owner/name> \
  --default-branch main
```

It archives the payload at the pinned commit, never the working tree, into `tmp/<repository-name>/` under this repository, runs `git init -b <default-branch>` there with no remote, and writes `<records>.materialize.json` with the candidate path, the commit, `head`, and the payload path count. `tmp/` is held out of the tree by `tmp/*` in `.gitignore`, so a candidate cannot be committed here, and sits inside the repository, so writing a whole tree stays within the agent's file-access approvals; a fixed path is also what lets a stopped generate resume from the candidate. Step 4 creates the repository the remote points at. `-b` matters because an unborn HEAD on `master` while step 4's `update-ref` writes `refs/heads/main` points at neither, and step 5's probe then commits to the wrong branch. It refuses a candidate directory that already holds files and changes nothing: a resumed generate keeps the candidate it has, so read `git symbolic-ref HEAD` there and point HEAD at the default branch before step 4's `update-ref` if it does not already.

[The payload's mode travels with the payload's content](lifecycle.md#the-payloads-mode-travels-with-the-payloads-content) binds every flow that lands payload content, and generate is the one flow it costs nothing. `git archive` carries each mode out of the pinned tree and the candidate is fresh, so no destination file's bit is there to survive the write. That is why no step below reads a mode or cites the rule — the exemption is in how this flow writes, not in the rule's reach.

The candidate stands while the flow can still be resumed from it, and comes down at the flow's end rather than being handed to the operator as a command: once step 12's verification is read, and, on a bootstrap generate, the default branch after the merge with it. Remove the tree, the `<hooksdir>` made beside it under [Working hooks in a candidate](lifecycle.md#working-hooks-in-a-candidate), and the resume record beside that — `rm -rf` each, and only inside this repository's `tmp/`. There is no branch to delete: the candidate is its own repository and goes with the directory. That is also why removing it does not break the rule against sweeping a branch whose pull request is still open — the work is on the destination's remote, and what comes down is a throwaway tree this flow created, not a worktree of a clone somebody else owns. A generate stopped at the wayfinding handoff sweeps nothing, because that stop resumes from exactly these three; report them left standing, under **Cleanup** in [Final report](reporting.md#final-report).

### Step 4 — Create the destination repository

Create the destination repository, at the [remote action gate](lifecycle.md#remote-action-gates). Present the gate first, and every line of it that applies: the repository name and visibility, the empty root commit, the settings step 5 applies, the ruleset probe step 5 pushes to prove those settings bind, the triage labels step 6 creates, and the map step 7 writes. The payload records the tracker, so both are decided here rather than left open: they are GitHub Issues on this repository. There is no diff and no check result to show yet, which is why this gate is separate from the one at step 11 — that one authorizes publishing content that has been reviewed, and this one authorizes an empty repository so that everything after it has somewhere to live.

Create it without auto-initialization, set it as the candidate's remote, and push one empty root commit to the default branch, so the full generated payload is reviewable as a pull-request diff at step 11 rather than arriving as an initial commit nobody reads. Creation stays a command of its own, since visibility and the description are the gate's answers:

```bash
gh repo create <owner/name> --<visibility> --description "<description>"
git -C tmp/<repository-name> remote add origin "https://github.com/<owner/name>.git"
python3 apps/repo-builder/src/scripts/generate.py bootstrap \
  --records tmp/<repository-name>.<first 12 of the commit> \
  --repository <owner/name>
```

`bootstrap` reads the candidate and its default branch from `<records>.materialize.json` (`--default-branch` overrides the branch), builds a parentless commit on the empty tree with `commit-tree`, points the default branch at it, pushes it to `origin`, and writes `<records>.bootstrap.json` with the commit under `root`. It refuses, changing nothing, a candidate with no `origin`, a default branch already on `origin` (a bootstrap that already ran, or someone else's history), and a candidate default branch that is anything but an empty root. A candidate default branch that is an empty root is a push that failed, so rerunning pushes that same commit.

It uses `commit-tree` rather than checking the default branch out and committing on it, because the candidate's own `no-commit-to-branch` hook refuses such a commit and its `protect-branch` pre-push hook refuses the push, both correctly — neither can distinguish this one-time structural bootstrap from an ordinary disallowed one. Neither hook is installed this early, since step 9 is what installs them, but do not lean on that ordering: a resumed generate reaches this step with them already in place, and the push then needs `--no-verify`, because `protect-branch` blocks by destination ref rather than by commit content and so cannot recognize its one exception. `bootstrap` never passes it, so there its push fails on the hook and leaves the root on the candidate's default branch; get explicit confirmation for that specific bypass before running `git push --no-verify origin <default-branch>` by hand — it defeats the only branch protection this plan has, and every other push and commit in this lifecycle goes through hooks normally.

The repository existing this early is deliberate, and step 7 is the reason. `/wayfinder` infers the repository from `git remote -v` and charts its map on the tracker `generation.features.issue_tracker` names, GitHub Issues where nothing is recorded. Run it against a candidate with no remote and the map — the whole product of an escalated generate — ends up somewhere the repository does not track its work. The same held when step 6 chose the tracker by asking; defaults the skills carry remove the question without removing the ordering it forced. The cost is that a generate abandoned after this point leaves an empty repository behind; say so at the gate.

An invocation that forbids contacting GitHub does not skip this step, it stops at its gate: present the same lines, perform none of them, and record what would have run. Everything after then proceeds against a candidate with no remote — the one state the rest of this section does not otherwise produce. Step 5 has no repository to configure and no branch to probe, step 6 records any departure but has no repository to create the labels on, step 7 cannot chart at all — the repository is resolved from `git remote -v` and there is no remote, so `gh` has nothing to answer — and step 11 stops at its own gate the same way. Say so when reporting the plan: the map has no home until the repository is created, which is the one thing this path cannot establish. Do not fall back to a local-markdown map to have somewhere to write it. The default tracker is GitHub Issues, and charting into `.scratch/` because a remote is missing produces exactly the map nobody finds again that ordering the repository first exists to prevent. Report the result as a plan, never as a generate that reached GitHub.

### Step 5 — Configure the repository settings

Apply every setting the step 4 gate listed with one command, run from this repository:

```bash
python3 apps/repo-builder/src/scripts/generate.py settings \
  --records tmp/<repository-name>.<first 12 of the commit> \
  --repository <owner/name> \
  --default-branch main
```

In order, it sends the four merge settings as one PATCH, turns on Dependabot alerts and security updates, turns on push protection, and creates the `main` ruleset from `apps/github-repository-template/src/ruleset.json`, which requires `CI`, `Security` and `Code scanning enabled`. It writes `<records>.settings.json` with each write's outcome, the required contexts, and the probe, and logs every write's reverse in `<records>.writes.json`. A 403 or 422 on push protection or the ruleset is recorded `not offered`, which the report states as `not offered for the plan`, never as disabled. Only where the ruleset was created does it probe: an empty commit pushed straight to the default branch, which must be refused with `GH013`. An accepted probe push exits non-zero naming the commit, which stays on the remote default branch: that is a failed verification, so stop under [Failure and recovery](lifecycle.md#failure-and-recovery) and leave removing it, a force-push, to a decision at a gate. A probe refused without `GH013`, such as by a hook a resumed generate already installed, also exits non-zero; do not skip the probe to get past it. The command's docstrings and `docs/adrs/0010-run-generates-fixed-steps-as-commands.md` carry the reasons.

Adopting `CODEOWNERS` changes what the ruleset should require. It is the only addon finished by a repository setting rather than by an edit: without a rule requiring code owner review, the file requests a reviewer and nothing waits for the answer. Enabling it is not the safe default it looks like, for the reason its manifest entry gives — ask, and where the answer is yes, set `require_code_owner_review` on the ruleset the command created.

Read the result back with the candidate's own `scripts/repo-settings check` rather than hand-rolling `gh api` calls. It separates the two ways a setting reads as absent, a non-admin and a plan that does not offer the feature, and its output is the evidence for the settings section of the report.

### Step 6 — Configure the repository for the engineering skills

The engineering skills carry their own defaults, so nothing is collected and no file is written for them: GitHub Issues reached with `gh`, the sixteen triage roles unrenamed (`bug`, `enhancement`, `documentation`, `perf`, `refactor`, `style`, `test`, `build`, `ci`, `chore`, `revert`, `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), and pull requests not a request surface. A repository that differs records a departure under `generation.features`, each key optional and an absent one meaning the default:

```json
"features": {
  "issue_tracker": "<free text naming the tracker and how to reach it>",
  "prs_are_requests": true,
  "triage_labels": { "<canonical role>": "<label string>" }
}
```

Record a departure the invocation names. Step 7's `/wayfinder` reads this record and the manifest is not created until step 8, so write `.repo-template.json` here holding only `generation.features` when there is a departure to record; step 8 completes the same file and keeps what is in it. A generate with no departure writes nothing here.

The one write a record cannot do for itself is creating the labels, on the repository step 4 created. This is the write that gate authorized, and nothing else in the lifecycle performs it.

```bash
python3 apps/repo-builder/src/scripts/generate.py labels \
  --records tmp/<repository-name>.<first 12 of the commit> \
  --repository <owner/name>
```

It sends its writes through `retrofit.py`'s `write_labels`, logs each in `<records>.writes.json`, and writes `<records>.labels.json` with the `labels` it ensured and which were `created`, `renamed` (`from`, `to`), `existing`, and `kept` (a case variant left as it is). A refused write stops it naming the label and what was created before it, and leaves no record; rerunning skips what landed.

Run it only where the tracker is the host. A `generation.features.issue_tracker` departure naming a tracker that is not GitHub Issues takes no label creation at all: the labels belong to whatever that names, and creating GitHub labels for a repository tracked elsewhere writes a vocabulary nothing reads. Report the step as `none created` with that as the reason.

Twenty-one labels: the sixteen roles, `wayfinder:map`, and the four `wayfinder:<type>` labels (`research`, `prototype`, `grilling`, `task`). Each role's label is the default string unless `generation.features.triage_labels` in the candidate's `.repo-template.json` maps that role to another, in which case the command creates the mapped string in its place. They are created without descriptions rather than restating the skills' here, where the two would drift. The map label alone is not enough: a map's tickets each carry a type label, so a repository given only `wayfinder:map` runs the wayfinding skill exactly as far as its first map and then fails on the first ticket create. Only what is missing is created. GitHub ships `bug`, `enhancement`, `documentation`, and `wontfix` on a new repository with their own descriptions and colors, and a destination that already has content may carry more; overwriting those is a change nobody asked for.

The match is case-insensitive because the host's is. A destination carrying `Bug` would pass a case-sensitive guard as absent, and the create would then fail on a name GitHub considers taken. A case variant is therefore a rename to the spelling in force, not a skip: a label is one object with a stable id, so the rename carries the id and every issue already wearing it keeps the label under the new name. It is never forced, which is what leaves the host's own description and color intact; only the name changes. The alternative, recording the destination's spelling as a `triage_labels` departure, is the right answer where the destination means its spelling as its vocabulary, and a rename is the right answer where the case variant is an accident; ask which when a destination's own docs do not settle it.

The rename is the default vocabulary deciding, so it happens only where no `triage_labels` departure is in force. Where the destination records one, or carries `docs/agents/triage-labels.md` of its own that [becomes one](generate-into-content.md#into-a-repository-that-already-has-content), its spellings are the correct ones: the command creates what the record names and renames nothing, so record that departure before running it.

The rename has a named cost, and it is not reversible by the step that caused it. Label *search* is case-sensitive even though label *creation* uniqueness is not, so a saved search, a workflow filter, or a skill pinned to `Bug` silently stops matching once the label is `bug`: no error anywhere, just an empty result. Report every rename in the final report with both spellings, so the destination's owner can repoint whatever was pinned to the old string.

Creating the labels is not order-independent: it writes to the repository step 4 created, and step 7 fails without it. That is what keeps this step where it is rather than anywhere before step 4.

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
- keep `docs/adrs/0000-template.md` as the reusable ADR template;
- create `.repo-template.json` with the command below, which keeps the `generation.features` step 6 wrote and adds what it is given;
- append the derived entries to `.github/dependabot.yml`, as [Dependabot entries follow the manifests present](lifecycle.md#dependabot-entries-follow-the-manifests-present) directs. Into an empty destination the derived set is empty and the payload's file lands unchanged, because step 7 renders no root manifest and the first real commit is what brings one. Into a destination that already had content it is whatever that content brought, derived here rather than in the replacement above so there is one place the file is written from destination evidence;
- render feature choices honestly, and record no visibility: it is live-readable and every decision turning on it reads the API, as [Manifest](lifecycle.md#manifest) directs. `codeql.yml` lands whatever the destination's visibility, as [Code scanning lands everywhere and decides at run time](lifecycle.md#code-scanning-lands-everywhere-and-decides-at-run-time) directs, so `generation.features` takes no entry for it.

Then write the manifest and the ADR index, run from this repository:

```bash
python3 apps/repo-builder/src/scripts/generate.py manifest \
  --records tmp/<repository-name>.<first 12 of the commit> \
  --repository <owner/name> \
  --commit <commit> \
  --subtree apps/github-repository-template/src/base-repo \
  --default-branch main \
  --application <name> \
  --feature <key>=<value>
(cd tmp/<repository-name> && scripts/adr-index && git add docs/adrs/index.md)
```

Repeat `--application` per deployable in wayfinding's order and `--feature` per departure; `triage_labels.<role>=<label>` sets one role's label, and `codeql` and `prs_are_requests` take only `omitted-by-choice` and `true`. It writes the canonical ownership list, validates the file as preflight does, refuses a payload path no rule reaches, stages the file, and writes `<records>.manifest.json`; a refusal leaves the file as it was. `scripts/adr-index` regenerates the index from the ADRs above and staging it is what lets step 9's first check run pass, since its `adr-index` hook fails on an unstaged rewrite.

### Step 9 — Run the candidate's checks

Install the candidate's pre-commit hooks with one command, the recipe of [Working hooks in a candidate](lifecycle.md#working-hooks-in-a-candidate) run by retrofit's own installer:

```bash
python3 apps/repo-builder/src/scripts/generate.py hooks \
  --records tmp/<repository-name>.<first 12 of the commit> \
  --tree tmp/<repository-name>
```

It reads the types from the candidate's `pre_commit_hook_types`, writes the shims into the candidate's `.git/hooks`, pins `core.hooksPath` there at local scope, chains any hook a global `core.hooksPath` was running, and writes `<records>.hooks.json`: `hook_types`, `hooks_path`, `prior_hooks`, `moved_aside`, `chained` and `findings`. It exits 1 unless every configured type resolves in the directory git will consult, and records `not-applicable` for a payload with no `.pre-commit-config.yaml`. Do not publish a candidate whose hooks did not install.

Then stage the candidate and run its documented checks as [Running the destination's checks](lifecycle.md#running-the-destinations-checks) directs. Git is already initialized and its remote already set, from steps 3 and 4. Staging matters twice over here: step 10 reads the tracked paths this stage produces.

### Step 10 — Verify the file list

Account for every path with one command, after step 9's stage:

```bash
python3 apps/repo-builder/src/scripts/generate.py filelist \
  --records tmp/<repository-name>.<first 12 of the commit> \
  --tree tmp/<repository-name> \
  --commit <commit>
```

It compares the payload's tracked paths at the source commit with the candidate's, the first application standing where `apps/app-name/` stood, and writes `<records>.filelist.json`:

- `missing` — payload paths the candidate neither tracks nor holds ignored on disk.
- `additions` and `strays` — candidate-only paths. An addition is `.repo-template.json`, an ADR at `docs/adrs/NNNN-<slug>.md`, `docs/adrs/index.md`, every `apps/<name>/` past the first, and `.scratch/` where `generation.features.issue_tracker` is recorded; anything else is a stray.
- `ignored_present` — payload paths the candidate ignores and holds on disk, such as `.env` and the `.claude/` tree.
- `ignored_tracked` — tracked paths the candidate's ignore rules exclude, each a defect. `git rm --cached <path>` is the remedy, `git rm -r --cached <dir>` where a whole tree went in. Report it alongside the account rather than only fixing it: into an empty destination the path was force-added, and into one with content [`generate-into-content.md`](generate-into-content.md) names a second cause.
- `copy` — the copy proof of [Reviewing the pull request](reporting.md#reviewing-the-pull-request), from `update.py`: `identical`, `total` and the `authored` surface, the ignored paths proved against disk inside the one count.

It exits 1 on a missing path, a stray, or an ignored-but-tracked path. Then read the `authored` surface line by line. Do this here rather than after step 11, and read it closely: a bootstrap generate merges its own pull request at step 12, so this is the only reading that personalized surface gets.

### Step 11 — Publish the candidate

Publish the candidate, at the [remote action gate](lifecycle.md#remote-action-gates). Present the local diff, the file-list reconciliation, the check results, the settings state, and the exact pending commands. Then branch from the empty base, add the entire candidate and manifest, commit, push, and open a PR. Supply an explicit PR body, written to a file beside the candidate under this repository's `tmp/` (`tmp/<repository-name>.pr-body.md`, never inside the candidate, where it would enter the diff) and passed with `gh pr create --body-file <file>`; the operator's hooks refuse `--body-file -`. The reason is that this flow already holds the content the body needs — the diff, the reconciliation, the check results — and not that the base lacks a template to render: that is true of a bootstrap generate alone, and reading it as the general reason gets the rule wrong for every flow whose base does carry one. The host renders `PULL_REQUEST_TEMPLATE.md` from the base branch, and an explicit body suppresses it entirely, so fill the body against that template's own sections wherever the base has one.

### Step 12 — Verify the published repository

Verify the remote default branch, PR base/head, URL, settings state, and available checks. Do not merge. This verification is what step 3's sweep waits on: read it, then sweep the candidate before composing the report.

Wait on the pull request's checks with `gh pr checks <n> --watch`, not a hand-written poll. A pull request with no checks means the workflows are unverified, never that they passed. Establish which one it is before reporting:

```bash
gh api repos/<owner>/<name>/commits/<head-sha>/check-suites --jq '[.check_suites[].app.slug]'
```

No GitHub Actions suite means no run was ever dispatched. Check [githubstatus.com](https://www.githubstatus.com/) before treating that as a defect in the generated repository — dispatch and registration are separate services, and an outage suppresses runs while every permissions and workflow API still reports healthy.

Note that `/actions/workflows` lists the default branch only, so it reads zero on a first-generation PR whose default branch has no `.github/` yet. That is expected, not evidence.

Once those checks are green, read `mergeable` and `mergeStateStatus` as a pair, under [A written ruleset is proved satisfiable, not merely present](lifecycle.md#a-written-ruleset-is-proved-satisfiable-not-merely-present). Step 5's probe proved the ruleset binds; this is the separate question of whether it can ever be satisfied, and the two failures look identical from the settings state. A bootstrap generate owes the read before the merge below, not after — `MERGEABLE`/`BLOCKED` is the reason the merge will refuse, and the required contexts step 5 wrote are where it is repaired.

A bootstrap generate is the one case where "do not merge" inverts. The destination's default branch is still the empty root commit, so no worktree can be created against it to review the PR before it merges — `git worktree add` against an empty tree checks out nothing, and a hook that expects the repository's own files (a missing `.pre-commit-config.yaml`, for instance) then fails on an empty checkout that was never the defect. Once checks pass, repo-builder may merge this one pull request itself, gated the same as any other remote action: present it as an explicit action against this exact repository and obtain confirmation before running it. The exception is scoped to this bootstrap PR alone — update, adopt, and a generate into an already-populated destination all have a destination worktree available for ordinary review, so their pull requests are never merged by repo-builder.

Having merged it, verify the default branch. This is the only merge in the lifecycle, and it is the first time the repository's workflows run against `main` with content in it — a green pull request does not carry over, because the PR ran against a merge of an empty base and `main` afterwards is a different commit with a different trigger. Wait on that commit's run with `gh run watch <run-id> --exit-status`, the id from `gh run list --branch <default-branch> --limit 1 --json databaseId --jq '.[0].databaseId'`, then read its check-suites the same way step 12 reads the PR's, keep the same distinction between a failing run and no run dispatched, and report the result. A red default branch immediately after generation is a finding to hand over, not a state to leave unmentioned because the pull request was green.

### Step 13 — Register the repository in Orca

Give the operator a clone of the new repository registered in Orca, with an icon that says what the repository is. Run it once step 12's verification is read, and after the bootstrap merge where there is one, so the clone checks out content rather than the empty root commit. It is local, so it takes no [remote action gate](lifecycle.md#remote-action-gates); a generate that stopped before step 12, at the wayfinding handoff or with no repository created, registers nothing and reports the step not reached.

1. Clone with the command below. A generate into a destination that already had content registers the operator's clone it worked in and clones nothing. Where `~/code/<name>` already exists, reuse it only when its `origin` is this repository; anything else there is not this flow's to overwrite, so leave it and report the step not reached with the path as the reason.

   Clone and record in one command, so the record follows only a clone this command made:

   ```sh
   gh repo clone <owner>/<name> ~/code/<name> && {
     [ -z "$CLAUDE_CODE_SESSION_ID" ] || {
       records="${XDG_CACHE_HOME:-$HOME/.cache}/claude-generated-repos"
       mkdir -p "$records" && realpath ~/code/<name> >> "$records/$CLAUDE_CODE_SESSION_ID"
     }
   }
   ```

   The record names the clone as the generating session's, so the operator's user-level hooks let that session edit, `rm` and `sed -i` in it as in its own checkout rather than prompting on every write. A reused clone and the operator's own are never recorded, a resumed generate included: either may hold work this session did not write, so every write there still asks.
2. Choose one emoji for what the repository *is*: the subject the user described at step 2 and the deployables step 7 derived, never the template, the language, or the tooling. Prefer a concrete object the name or purpose evokes (🎙️ for a podcast app, 🩺 for a medical research tool) over a generic one; 📁, 💻 and 📦 say nothing Orca's default icon does not.
3. Register and set it with `python3 apps/repo-builder/src/scripts/orca_icon.py --repository <clone> --emoji <emoji>`. The script adds the clone where Orca does not know it, keeps an emoji icon someone already chose (`status: kept`), and otherwise replaces whatever icon is there, the owner avatar Orca fills in for a GitHub remote included. The orca CLI has no icon flag, so the script sends the runtime's own `repo.update` request and checks that the icon it stored is the one sent. Exit 3 means Orca's runtime is not reachable: report the icon unset with that reason and the command under Pending action, without stopping the flow. Exit 2 is a refusal, reported with the runtime's error.

The clone is the result, not scratch, so step 3's sweep never reaches it. Report it on the **Orca** line of [Final report](reporting.md#final-report).

### Step 14 — The first prompt

The first prompt is written for a reader this session never speaks to: whoever opens the first working session in a fresh clone of the new repository. Everything this session knows about that repository's initial state dies with it otherwise — which checks are red on purpose, what the tracker holds, what a clone still has to install — and the next session rediscovers each one as a defect. Emit it as a fenced block so it can be copied whole, fill every placeholder from what actually happened rather than from this shape, and drop a line whose condition did not arise rather than shipping it empty. An update and an adopt write none: the destination already has working sessions. On a generate stopped at the wayfinding handoff the resume belongs to the operator of this session, not to a new one, so Pending action carries it and this section is still omitted.

It is the report's last section, **First prompt**, added after **Pending action** at the same heading level as the shape's own sections, and its first line is the instruction to the reader:

Copy this into the first session opened in a clone of the new repository:

```text
Work <owner/repository> in <the clone step 13 registered in Orca | a fresh clone>. Install the
hooks there: `pre-commit install`, or, if that refuses because a `core.hooksPath` is already
set on this machine, `pre-commit init-templatedir` into a directory of its own with
`core.hooksPath` pointed at it. Nothing else installs them, and without them commits land
unattributed and unchecked. Then read the root `CLAUDE.md` before touching anything.

The plan of record is <the issue tracker: generation.features.issue_tracker, or GitHub Issues>, not this
message. Open tickets: <count>. First with no open blocker: <#n — title>. Start there.

Expected initial state, not defects: <the absent root manifest, which scripts/check
reports as "No project manifest found, so there is nothing to check yet. Every check
becomes required as soon as a manifest is added." |
the skipped CodeQL detect and analyze legs on a private destination, per lifecycle.md
"Code scanning lands everywhere and decides at run time" | none>.

The first root manifest owes the checks their tools: <the declarations for the selected
language, from lifecycle.md "Tools the first manifest must declare" | none, <language>
declares no tools>. An undeclared tool reports `unavailable`, which fails the run.

Branch before you commit; a commit made on `main` is refused at the hook.
```

The manifest sentence's lead-in, `The first root manifest owes`, is what the generation eval reads the handover for; rewording it updates the eval in the same change. The expected-state line above it is coupled to the same check in the other direction: `handover_declares_python_tools` scopes itself to the manifest sentence *because* that line already guarantees the word "manifest" appears in the report, which is what would make an unscoped check vacuous. Drop the word from the expected-state line and the scoping loses the reason its docstring gives for existing.

The expected-state line names `scripts/check` rather than `scripts/doctor` because doctor does not fail on this shape. `detect_orphan_manifests` fires only on a manifest nested under a root that has none, so a destination with no manifest anywhere trips nothing and doctor reports `detection pass`. Naming a failure that never arrives is worse than naming none: the reader it is written for cannot ask the session that generated the repository, so they go looking for it, and what they learn is that the block is unreliable.
