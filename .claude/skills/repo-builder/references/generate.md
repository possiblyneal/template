# Generate

Read [`lifecycle.md`](lifecycle.md) first — the manifest, ownership, check reporting, the remote gates, failure behavior, and the report shape are there and apply throughout.

1. Resolve the requested source to an exact commit and run:

   ```bash
   python3 .claude/skills/repo-builder/scripts/preflight.py generate \
     --template-repo <template-repo> \
     --target <ref-or-commit> \
     --subtree apps/github-repository-template/src/base-repo \
     --destination-repository <owner/name> \
     --default-branch main
   ```

   `generate` validates the source only. It takes the destination as a name, never inspects it, and so cannot tell an empty repository from one with content. Establish that yourself before materializing.

2. Collect only unresolved decisions: owner/name, visibility, public-repository files, release behavior, and feature availability. The application boundaries are not among them. They are derived rather than collected, and step 7 derives them once the candidate and the repository exist. Neither are the merge settings: step 5 applies all four unconditionally, so there is no choice here for the step 4 gate to name.

   The public-repository files are the repository addons, held back rather than shipped and offered against the conditions the answers to this step have established. Adopt the ones taken as the [Addon adoption](addon-adoption.md) section directs, from this same source commit.
3. Materialize the subtree from that exact commit into an isolated local directory. Do not substitute the current working tree. Initialize Git in it with `git init -b <default-branch>` and leave the remote unset; step 4 creates the repository that remote points at. Pass `-b` rather than taking whatever `init.defaultBranch` happens to be: an unborn HEAD on `master` while step 4's `update-ref` writes `refs/heads/main` leaves HEAD pointing at neither, and step 5's probe then commits to the wrong branch, pushes nothing, and reports an unprotected branch as protected. A resumed generate re-running this step gets `warning: re-init: ignored --initial-branch` and exits zero, so the flag repairs nothing on that path; read `git symbolic-ref HEAD` rather than assuming it took, and point HEAD at the default branch before step 4's `update-ref` if it does not already.
4. Create the destination repository, at the [remote action gate](lifecycle.md#remote-action-gates). Present the gate first, and every line of it that applies: the repository name and visibility, the empty root commit, the settings step 5 applies, the ruleset probe step 5 pushes to prove those settings bind, and the triage labels and the map that steps 6 and 7 write. Those last two are the only lines not yet decided here — step 6 is what chooses the tracker — so present them against this repository, which is what `/setup-matt-pocock-skills` proposes from, and return to this gate if step 6 settles on a different hosted tracker. Settling on local markdown needs no return: it makes no remote write, so the authorization taken here simply goes unused. There is no diff and no check result to show yet, which is why this gate is separate from the one at step 11 — that one authorizes publishing content that has been reviewed, and this one authorizes an empty repository so that everything after it has somewhere to live.

   Create it without auto-initialization, set it as the candidate's remote, and push one empty root commit to the default branch, so the full generated payload is reviewable as a pull-request diff at step 11 rather than arriving as an initial commit nobody reads.

   ```bash
   empty_tree=$(git hash-object -t tree /dev/null)
   empty_commit=$(git commit-tree "$empty_tree" -m "chore: initialize empty repository")
   git update-ref refs/heads/<default-branch> "$empty_commit"
   git push origin <default-branch>
   ```

   Build the commit with `commit-tree` rather than by checking the default branch out and committing on it. The candidate's own `no-commit-to-branch` hook refuses such a commit and its `protect-branch` pre-push hook refuses the push, both correctly — neither can distinguish this one-time structural bootstrap from an ordinary disallowed one. Neither hook is installed this early, since step 9 is what installs them, but do not lean on that ordering: a resumed generate reaches this step with them already in place, and the push then needs `--no-verify`, because `protect-branch` blocks by destination ref rather than by commit content and so cannot recognize its one exception. Get explicit confirmation for that specific bypass before running it — it defeats the only branch protection this plan has, and every other push and commit in this lifecycle goes through hooks normally.

   The repository existing this early is deliberate, and the two steps after it are the reason. `/setup-matt-pocock-skills` proposes an issue tracker by reading `git remote -v`, and `/wayfinder` charts its map wherever that answer sends it. Run either against a candidate with no remote and both get the wrong answer for a repository that is about to be on GitHub — and the map, which is the whole product of an escalated generate, ends up somewhere the repository does not track its work. The cost is that a generate abandoned after this point leaves an empty repository behind; say so at the gate.

   An invocation that forbids contacting GitHub does not skip this step, it stops at its gate: present the same lines, perform none of them, and record what would have run. Everything after then proceeds against a candidate with no remote — the one state the rest of this section does not otherwise produce. Step 5 has no repository to configure and no branch to probe, step 6 has no remote for `/setup-matt-pocock-skills` to propose from and will settle on a local tracker, step 7 charts wherever that sends it, and step 11 stops at its own gate the same way. Report the result as a plan, never as a generate that reached GitHub.
5. Configure supported settings after the default branch exists: Dependabot alerts/security updates, push protection where available, the merge commit as the only merge method, automatic head branch deletion, and a branch ruleset appropriate to the repository. Confirm plan/visibility limitations instead of treating API success as proof a feature is active.

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

   Read the result back with the repository's own `scripts/repo-settings check` rather than hand-rolling `gh api` calls. It already separates the two ways a setting reads as absent: `security_and_analysis` is missing both for a non-admin and for a plan that does not offer the feature, and it checks `.permissions.admin` to tell those apart. A hand-rolled check that misses this reports a plan limitation as a disabled setting.

   Its output is the evidence for the settings section of the report, and `not offered for the plan` is a distinct outcome from disabled — do not collapse them.

   Ruleset creation can also be refused outright, and that is a different outcome from a ruleset that does not bind. A repository on a plan that does not offer rulesets returns 403, so there is no 201 to be suspicious of and the refusal is itself the measurement: record `not offered for the plan` and do not probe. Pushing anyway learns nothing the 403 has not already said, and an unprotected branch does not reject it — the probe commit lands on top of step 4's empty root and becomes the default-branch tip, with nothing verified and a commit that only a force-push removes. Probe only where creation returned 201.

   A ruleset that was accepted is not a ruleset that binds. Creation returns 201 either way, so prove enforcement rather than inferring it: put a throwaway commit on the default branch, push it directly, and require the `GH013` rejection. An unprotected branch accepts that push, which is the finding.

   ```bash
   git commit --allow-empty -m "chore: ruleset probe"
   git push origin <default-branch>
   git update-ref refs/heads/<default-branch> origin/<default-branch>
   ```

   The probe is a commit on the default branch and a direct push to it, which is exactly what `no-commit-to-branch` and `protect-branch` exist to refuse. Step 4's note above applies to it unchanged, including the explicit confirmation that bypass needs: a resumed generate reaches this step with both hooks installed. Do not resolve a refusal by skipping the probe, which reports an unverified ruleset as verified.

   Make the probe empty and rewind it with `update-ref` rather than `git reset --hard`. The materialized payload is sitting untracked in this worktree, and a hard reset against an empty base takes the working tree with the probe.

   That rewind is local, and it removes the probe only where the push was rejected. Where the push was accepted, `origin/<default-branch>` is the probe commit, so the rewind syncs to it rather than undoing it and the commit stays on the remote default branch. That is the finding, and it is a failed verification: stop under [Failure and recovery](lifecycle.md#failure-and-recovery), name the repository and say it carries the probe commit, and leave removing it to a decision at a gate. Removing it means force-pushing the default branch, which is not an operation to perform on the way past.

6. Configure the repository for the engineering skills — invoke `/setup-matt-pocock-skills` with the Skill tool. Invoke it; do not answer for the user and do not reproduce what it does by hand. It is the source of truth for its own questions, and a copy of them here goes stale the first time it changes.

   Do not predict what it will ask. It explores first and asks only what exploration leaves open, and what that leaves open depends on the candidate's contents and on which sibling skills are installed on the machine — neither of which this contract can know, and the second of which is not a fact about the repository at all. Answer from the candidate's actual state; the issue-tracker question is the one it reaches on a fresh candidate, and step 4 has already given it a remote to propose from — unless step 4 stopped at its gate, in which case there is none and it will settle on a local tracker.

   It always writes `docs/agents/issue-tracker.md`, `docs/agents/domain.md`, and an `## Agent skills` block in the root `CLAUDE.md`. It writes `docs/agents/triage-labels.md` and that block's `### Triage labels` sub-block only where the `triage` skill is installed beside it, so those two appear together or not at all — do not treat either as guaranteed. Step 8 rewrites that same file's Child Index and must leave the block intact; step 10 accounts for whichever paths it wrote.

   Run it here rather than after generation, because step 7 depends on its output: `/wayfinder` reads `docs/agents/issue-tracker.md` to decide where a map lives, and a handoff reached before this step has nowhere to chart to.
7. Derive the application boundaries — run [Wayfinding](wayfinding.md) here. Two questions settle it for most repositories; against the triggers that section names, hand the decomposition to `/wayfinder` and stop as [Handing off to `/wayfinder`](wayfinding.md#handing-off-to-wayfinder) directs.
   Do not render a root manifest, even for a language wayfinding selected. Wayfinding establishes which constraint binds; it does not establish a package manager, a version, or a project layout, and none of those follow from a choke point. It also reasons rather than measures — the reference is explicit that an unmeasured constraint and an absent one are indistinguishable until something measures — so a rendered manifest asserts more confidence than wayfinding produced. A wrong guess is worse than an absent file, the same reasoning `.github/dependabot.yml` follows in listing only the two manifests the template itself ships. A generated repository with no manifest is reported honestly by `scripts/ci` as nothing to check yet, with every check becoming required the moment one is added. The first real commit brings the manifest.

   Say so in the handover: the root manifest is what makes a package visible to the checks, and a manifest nested under `apps/` instead is invisible to all of them. `scripts/doctor` fails on that shape rather than passing over it.
8. Personalize the candidate:
   - create one `apps/<name>/` per deployable wayfinding established. Move `apps/app-name` to the first (do not copy it) and replicate its skeleton — `src/`, `tests/`, `docs/specs/`, `.unit.json` — for each one after that. Verify `apps/app-name` is absent afterwards and update every reference. One deployable is the ordinary case and needs no replication;
   - leave each `.unit.json` at the shipped `run: none, ships: {kind: none}`. Wayfinding establishes boundaries, not lifecycle: whether a deployable runs until stopped and whether it ships a binary are facts the first real commit brings, the same reasoning that keeps a root manifest unrendered above. A unit missing the file entirely fails `scripts/structure` on the first commit, so the file ships declared and honest rather than absent or guessed;
   - write one ADR per deployable recording its choke point and language, as [Wayfinding](wayfinding.md) directs;
   - replace the root `CLAUDE.md` bootstrap Child Index with repository-specific content, carrying the wayfinding result into it: each deployable, what it is for, and the language it is written in. The ADRs record why that language was chosen; `CLAUDE.md` is where an agent reads what the repository is before touching anything, and a Child Index naming the apps without saying what each one is leaves the boundaries derivable only from a directory listing. Then read the file back and confirm step 6's `## Agent skills` block is still in it. Nothing else verifies that: step 10 compares paths rather than content, and the file exists either way. Clobbering the block silently stops the engineering skills finding the tracker in a repository that otherwise looks correct;
   - initialize `docs/LESSONS.md` metadata and remove generation placeholders while retaining its durable writing guidance. Set `generated.by` to the actual author — the repo-builder agent, not the operator on whose behalf it ran — and capture `generated.at` from the real clock (e.g. `date -u +%Y-%m-%dT%H:%M:%SZ`) at the moment of writing rather than composing a plausible-looking value; a rounded time such as midnight is a placeholder wearing a valid format, not a captured one;
   - keep `docs/adrs/0000-template.md` as the reusable ADR template;
   - create `.repo-template.json`;
   - render visibility and feature choices honestly. Keep `codeql.yml` for a private repository rather than omitting it. Its `scanning` job fails in seconds naming the reason, which is accurate — the repository has no static analysis coverage — and it turns green by itself when the repository goes public, where omitting the file leaves nothing to restore and nothing to say so. Report that red check as an expected initial state when handing the repository over; do not describe it as a passing build. Record an omission under `features` only when deliberately stripping the workflow, which is now a choice rather than the private-repository default.
9. Install the candidate's local pre-commit hook if it requires one, stage the candidate, and run its documented checks as [Running the destination's checks](lifecycle.md#running-the-destinations-checks) directs. Git is already initialized and its remote already set, from steps 3 and 4. Staging matters twice over here: step 10 reads the tracked paths this stage produces.

10. Verify the file list, not only the content. Compare the payload's tracked paths at the source commit against the candidate's, and account for every difference as intended or as a defect. A file the payload ships and the candidate lacks is invisible to every check, because a check reads content and absence has no runner. Compare against the working tree as well as the index: a path the destination ignores is present and untracked rather than missing, and `.env` is the one the payload ships that way. Use `git ls-files` for the tracked comparison and `git ls-files -o -i --exclude-standard` for the untracked one; the flags are the whole point, since an ignored path appears in neither the plain form nor `-o --exclude-standard`, and the two disagree about `.env` in the direction that reads as missing. Do not build either list with the file-discovery tools — `.env` matches a `permissions.deny` rule, so Glob and Grep omit it and a listing built from them reports it missing when it is there.

   The candidate also carries paths the payload does not ship, and each is an intended addition rather than a stray: `docs/agents/issue-tracker.md` and `docs/agents/domain.md` from step 6, `docs/agents/triage-labels.md` from that step too where it was written at all, `.repo-template.json` and the ADR at `docs/adrs/NNNN-<slug>.md` from step 8, `docs/adrs/index.md` regenerated from that ADR by the payload's own `adr-index` hook, and every `apps/<name>/` past the first from step 8. None of them is ignored, so they appear in the tracked comparison as candidate-only paths — the same shape a stray file has, which is why the account names them rather than counting them. `docs/adrs/index.md` is the one no step decides to write: the hook is `always_run`, so step 9's checks regenerate it from whatever ADRs step 8 wrote and fail until it is staged. It appears because a hook produced it, not because a step chose it. A repository whose step 6 answer was local markdown carries its `/wayfinder` map under `.scratch/` too, and that also ships: tracking issues as files in the repository is what that answer chose.
11. Publish the candidate, at the [remote action gate](lifecycle.md#remote-action-gates). Present the local diff, the file-list reconciliation, the check results, the settings state, and the exact pending commands. Then branch from the empty base, add the entire candidate and manifest, commit, push, and open a PR. Supply an explicit PR body, because the empty base does not yet contain the repository's PR template.
12. Verify the remote default branch, PR base/head, URL, settings state, and available checks. Do not merge.

    A pull request with no checks means the workflows are unverified, never that they passed. Establish which one it is before reporting:

    ```bash
    gh api repos/<owner>/<name>/commits/<head-sha>/check-suites --jq '[.check_suites[].app.slug]'
    ```

    No GitHub Actions suite means no run was ever dispatched. Check [githubstatus.com](https://www.githubstatus.com/) before treating that as a defect in the generated repository — dispatch and registration are separate services, and an outage suppresses runs while every permissions and workflow API still reports healthy.

    Note that `/actions/workflows` lists the default branch only, so it reads zero on a first-generation PR whose default branch has no `.github/` yet. That is expected, not evidence.

    A bootstrap generate is the one case where "do not merge" inverts. The destination's default branch is still the empty root commit, so no worktree can be created against it to review the PR before it merges — `git worktree add` against an empty tree checks out nothing, and a hook that expects the repository's own files (a missing `.pre-commit-config.yaml`, for instance) then fails on an empty checkout that was never the defect. Once checks pass, repo-builder may merge this one pull request itself, gated the same as any other remote action: present it as an explicit action against this exact repository and obtain confirmation before running it. The exception is scoped to this bootstrap PR alone — update, adopt, and a generate into an already-populated destination all have a destination worktree available for ordinary review, so their pull requests are never merged by repo-builder.

Having merged it, verify the default branch. This is the only merge in the lifecycle, and it is the first time the repository's workflows run against `main` with content in it — a green pull request does not carry over, because the PR ran against a merge of an empty base and `main` afterwards is a different commit with a different trigger. Read that commit's check-suites the same way step 12 reads the PR's, keep the same distinction between a failing run and no run dispatched, and report the result. A red default branch immediately after generation is a finding to hand over, not a state to leave unmentioned because the pull request was green.

## Into a repository that already has content

The steps above assume an empty destination. A destination with existing content is a generation whose collisions are decided by hand, and it needs its own rules:

Step 4 creates nothing here — the repository is already there. Step 5 splits, and the split is the rule for this whole path: the four merge settings are applied exactly as written, and everything else it configures is reconciled rather than applied, since a setting someone deliberately turned off is destination intent the same way a file is.

The merge settings are not in that category. They are what the payload's commit-message rules and CI provenance rest on — a squash takes its message from the pull request title, which `commit-msg` never sees, and a rebase replays the branch as commits CI never ran — so a destination keeping them is a destination where the payload ships rules that do not bind. Name their current values at the gate rather than folding them into the settings line: this is the one place a generate overwrites a hosted setting someone chose, and the gate is where that gets said out loud. A destination whose owner declines them is not a failure to route around — record it in `generation.features` as the deliberate absence it is, the same as an omitted `codeql.yml`, and report which of the payload's guarantees do not hold there.

Step 6 still runs, but `/setup-matt-pocock-skills` may find its own prior output; let it decide what to do with it rather than deleting `docs/agents/` first.

1. Establish that the destination is a clean worktree, and enumerate every payload path that already exists there before writing anything.
2. Apply non-colliding payload files as ordinary additions.
3. For each collision, decide between the payload version, the destination version, and a merge — then state the decision and the reason per file. Verify afterwards that no destination-only content was dropped, naming what was preserved.
4. Never delete destination content to resolve a collision. A payload path that cannot be reconciled is a conflict to report, not a file to overwrite.
5. Record the collision decisions in `generation`, since they are choices a later update has to respect rather than re-litigate.
6. Do not create the placeholder application when the destination already has its own application boundaries. Record the real ones in `generation.applications`. Wayfinding still runs, but against what is there: it names the choke point each existing deployable already answers to rather than proposing a new decomposition, and it writes an ADR only where the repository has none for that deployable. A generation is not the occasion to re-cut boundaries someone is already shipping against.

Ownership still governs what a later update may touch, and a hand-merged file is managed content whose destination edits are real intent. Classify deliberately: marking a whole tree product to protect it also freezes it.
