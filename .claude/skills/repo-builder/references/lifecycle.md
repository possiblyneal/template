# Repo Builder Lifecycle Contract

## Contents

- [Manifest](#manifest)
- [Ownership](#ownership)
- [Addon adoption](#addon-adoption)
- [Generate](#generate)
- [Update](#update)
- [Adopt](#adopt)
- [Remote action gates](#remote-action-gates)
- [Failure and recovery](#failure-and-recovery)
- [Final report](#final-report)

## Manifest

Every built repository tracks `.repo-template.json`:

```json
{
  "schema_version": 1,
  "template": {
    "repository": "https://github.com/possiblyneal/template",
    "subtree": "apps/github-repository-template/src/base-repo",
    "commit": "0123456789abcdef0123456789abcdef01234567"
  },
  "destination": {
    "repository": "owner/repository",
    "default_branch": "main"
  },
  "generation": {
    "application_name": "billing-api",
    "visibility": "private",
    "features": {
      "codeql": "omitted-by-choice"
    }
  },
  "ownership": [
    {"path": ".repo-template.json", "mode": "managed"},
    {"path": "scripts/**", "mode": "managed"},
    {"path": ".github/**", "mode": "managed"},
    {"path": ".claude/settings.json", "mode": "managed"},
    {"path": ".pre-commit-config.yaml", "mode": "managed"},
    {"path": ".commitlintrc.yaml", "mode": "managed"},
    {"path": "zizmor.yml", "mode": "managed"},
    {"path": ".gitattributes", "mode": "managed"},
    {"path": ".gitignore", "mode": "managed"},
    {"path": ".worktreeinclude", "mode": "managed"},
    {"path": ".mcp.json", "mode": "managed"},
    {"path": "apps/**", "mode": "product"},
    {"path": "libs/**", "mode": "product"},
    {"path": "tests/**", "mode": "product"},
    {"path": "tools/**", "mode": "product"},
    {"path": "docs/**", "mode": "product"},
    {"path": ".claude/hooks/**", "mode": "product"},
    {"path": ".claude/rules/**", "mode": "product"},
    {"path": ".claude/skills/**", "mode": "product"},
    {"path": ".claude/agents/**", "mode": "product"},
    {"path": ".claude/output-styles/**", "mode": "product"},
    {"path": ".claude/workflows/**", "mode": "product"}
  ]
}
```

The `ownership` array above illustrates the shape at the time this contract was written; it is not a canonical list to copy. Build it from the payload's actual top-level structure at the resolved source commit — e.g. `git ls-tree -r --name-only <commit> -- <subtree>` — rather than pasting this example, since the template's real paths can drift from documentation prose without this file being updated to match.

Use a full lowercase 40-character commit. `template.commit` is the last template version successfully applied to the candidate state. Change it only after the candidate passes verification; commit it with the update it describes.

Record generation choices that change rendered files or repository settings. Do not record timestamps, a pending target commit, destination HEAD, or duplicate file contents.

Do not record what the filesystem already answers. Language and package manager are read from the manifests present, so a recorded copy is a second source of truth that only goes stale — `libs/detect.sh` answers the question at any moment and a manifest added later never updates a field. `visibility` is recorded despite being live-readable because it is an argument to repository creation, and `features` because it records which absences were deliberate: an omitted `codeql.yml` and a dropped one look identical on disk.

## Ownership

Ownership answers whether a path participates in template updates:

- `managed`: inspect changes from the template, but reconcile them with destination intent. It never means blind overwrite.
- `product`: preserve automatically. If a new template path collides with product content, report the collision and stop.
- unmatched: product-owned by default.

The longest matching path wins; equal patterns are invalid. The old-to-new template delta bounds update scope. Do not edit an unrelated destination path merely because a broad ownership rule matches it.

Unmatched defaulting to product is the safe direction for a path the template does not ship, and the wrong one for a path it does. A file at the repository root matches no directory pattern, so `.pre-commit-config.yaml`, `.commitlintrc.yaml`, `.gitattributes`, `.gitignore`, and `zizmor.yml` fall through to product unless named individually — and those files carry the pinned hook revisions behind the secret scanner, the commit-message rules, the merge policy keeping a lockfile from being line-merged, and the action-pinning policy. The list grows: every root file the payload adds needs a line here, and the omission is invisible until a payload fix silently fails to land. A payload fix to any of them would land nowhere while the update reported success. Every path the template ships needs an ownership rule that reaches it; verify with `classify_path` rather than assuming a directory pattern covers a file at the root.

A rename or delete of a destination-modified managed file needs semantic review. Product-created files under managed directories remain untouched unless the new template introduces the same path.

An adopted addon is one of those files. `CHANGELOG.md` matches no pattern and defaults to product; `.claude/rules/changelog.md` falls under the product-owned `.claude/rules/**`. Neither is a deletion to reconcile. The template never having shipped a path is not the template having removed it, and an update that reads it that way deletes a record the destination chose to keep.

## Addon adoption

The repository addons are the public-repository files a generation holds back: `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CODEOWNERS`, `SECURITY.md`, `CHANGELOG.md`, and the rest. They sit in `apps/github-repository-template/src/repository-addons/`, a sibling of the subtree rather than inside it, so no flow materializes them by copying the subtree. Each answers a condition the template cannot know has arrived, which is why it is held back rather than shipped. Adopt one by copying it from the source commit and finishing the regions below; offer it only against a condition that has actually arrived.

Four of them travel as two pairs. `CONTRIBUTORS.md` and `.all-contributorsrc` are one record split across two files: the contributor table is generated from the config's `contributors` array and never parsed back out of the Markdown, so taking the Markdown alone leaves a table nothing can update, and taking the config alone leaves it writing to a file that is not there.

The other pair is `CHANGELOG.md` and `.claude/rules/changelog.md`. The rule instructs an agent to maintain the file, so adopting the rule without the file states a contract that cannot be satisfied, and adopting the file without the rule leaves nothing keeping it current. `scripts/release` reads whichever world it lands in and says which one it took, so neither is required — but half of the pair is a defect rather than a lighter choice.

Copying an addon is not adopting it. Most arrive with regions that are wrong until someone edits them, and the failure mode is silent — a Code of Conduct promising a reporting channel that does not exist, a funding button pointing at a stranger's donation page, a citation crediting `REPLACE-FAMILY-NAME`. None of these are errors to any tool; they render, validate, and publish. `apps/github-repository-template/src/addon-adoption.json` is the index of those regions, a sibling of the addons directory rather than a file inside it, and is read rather than copied — a generated repository has no `repository-addons/` for it to describe.

Walk its entry for every addon taken, and for nothing else. It sorts each region by what the operator has to do:

- `slots` — a literal token to replace with a value. Grep for the token; if it is absent the file was already edited or the manifest has drifted, and either is worth stopping over.
- `reviews` — a section to read and a judgement to make, with no token to find. These are the ones a search cannot surface, which is the only reason they are written down.
- `external` — a step outside the repository entirely, such as installing a GitHub App. Nothing in the tree reports these undone.

Ask each distinct `value_key` once, not once per file. The repository owner is spelled `REPO-OWNER` in two addons and `<owner>` in a third; asking in each file's own vocabulary asks the same question three times and invites three answers. An entry flagged `authored_on_adoption` has no regions because the file ships empty — it is written, not filled, and the occasion for it is in `docs/github_repository_structure.md`.

Report every region as done or as outstanding. An addon left with an unfilled slot is worse than one not taken, because the repository now carries a document that reads as finished.

## Generate

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

2. Collect only unresolved decisions: owner/name, visibility, application boundary/name, public-repository files, release behavior, feature availability, and automatic head branch deletion.

   Automatic head branch deletion is collected here rather than at step 9, where it is applied, because the remote action gate in step 7 lists it among the settings it authorizes. A gate cannot name a choice that has not been made yet — asking after it would take authorization for one plan and then write a setting under another.

   The public-repository files are the repository addons, held back rather than shipped and offered against the conditions the answers to this step have established. Adopt the ones taken as the [Addon adoption](#addon-adoption) section directs, from this same source commit.

   Do not collect stacks or package managers, and do not render a root manifest. A template cannot know the ecosystem a repository will use, and a wrong guess is worse than an absent file — the same reasoning `.github/dependabot.yml` follows in listing only the two manifests the template itself ships. A generated repository with no manifest is reported honestly by `scripts/ci` as nothing to check yet, with every check becoming required the moment one is added. The first real commit brings the manifest.

   Say so in the handover: the root manifest is what makes a package visible to the checks, and a manifest nested under `apps/` instead is invisible to all of them. `scripts/doctor` fails on that shape rather than passing over it.
3. Materialize the subtree from that exact commit into an isolated local directory. Do not substitute the current working tree.
4. Personalize the candidate:
   - move `apps/app-name` to the kebab-case application name (do not copy it), verify the old path is absent, and update every reference;
   - replace the root `AGENTS.md` placeholder section and bootstrap Child Index with repository-specific content;
   - initialize `docs/LESSONS.md` metadata and remove generation placeholders while retaining its durable writing guidance. Set `generated.by` to the actual author — the repo-builder agent, not the operator on whose behalf it ran — and capture `generated.at` from the real clock (e.g. `date -u +%Y-%m-%dT%H:%M:%SZ`) at the moment of writing rather than composing a plausible-looking value; a rounded time such as midnight is a placeholder wearing a valid format, not a captured one;
   - keep `docs/adrs/0000-template.md` as the reusable ADR template;
   - create `.repo-template.json`;
   - render visibility and feature choices honestly. Keep `codeql.yml` for a private repository rather than omitting it. Its `scanning` job fails in seconds naming the reason, which is accurate — the repository has no static analysis coverage — and it turns green by itself when the repository goes public, where omitting the file leaves nothing to restore and nothing to say so. Report that red check as an expected initial state when handing the repository over; do not describe it as a passing build. Record an omission under `features` only when deliberately stripping the workflow, which is now a choice rather than the private-repository default.
5. Initialize Git locally with no remote and run the candidate's documented checks. Install the local pre-commit hook if the candidate requires it. Report skipped or unavailable checks; do not call them passes.

   Stage the candidate before running the checks. Step 6 compares tracked paths, and a bare `pre-commit run --all-files` enumerates through the Git index, so an unstaged candidate is checked as the empty set and reports a pass over nothing. The candidate's own `scripts/check` sweeps untracked files by path after that command, but only if the payload it was built from carries that second pass — verify rather than assume it.

   Tools the candidate's scripts look up on `PATH` may also run inside pre-commit's pinned environments. A tool reported unavailable by a script and passing under pre-commit in the same run was not skipped; report what each surface actually did.

   A machine-wide `core.hooksPath` set for an unrelated purpose (an editor's own git integration, another agent's attribution hook) makes `pre-commit install` refuse outright, and breaks it again inside any throwaway fixture repository the candidate's own tests spin up to exercise hook installation — fixtures inherit the same global config. Check `git config --global core.hooksPath` before treating either failure as a candidate defect; a control run of the same checks against the template repository's own current HEAD reproduces an identical failure when this is the cause.

6. Verify the file list, not only the content. Compare the payload's tracked paths at the source commit against the candidate's, and account for every difference as intended or as a defect. A file the payload ships and the candidate lacks is invisible to every check, because a check reads content and absence has no runner. Compare against the working tree as well as the index: a path the destination ignores is present and untracked rather than missing, and `.env` is the one the payload ships that way. Use `git ls-files` for the tracked comparison and `git ls-files -o -i --exclude-standard` for the untracked one; the flags are the whole point, since an ignored path appears in neither the plain form nor `-o --exclude-standard`, and the two disagree about `.env` in the direction that reads as missing. Do not build either list with the file-discovery tools — `.env` matches a `permissions.deny` rule, so Glob and Grep omit it and a listing built from them reports it missing when it is there.
7. Present the local diff, the file-list reconciliation, checks, repository settings, and exact pending remote commands at the remote action gate.
8. Create the GitHub repository without auto-initialization. Create and push one empty root commit to the default branch so the full generated payload can be reviewed in a PR.

   The candidate's own `no-commit-to-branch` hook refuses this commit while HEAD is the default branch, and its `protect-branch` pre-push hook refuses to push anything there — both correctly, since neither can distinguish this one-time structural bootstrap from an ordinary disallowed commit. Build the empty commit directly, without checking the default branch out to make it, so the commit hook never fires:

   ```bash
   empty_tree=$(git hash-object -t tree /dev/null)
   empty_commit=$(git commit-tree "$empty_tree" -m "chore: initialize empty repository")
   git update-ref refs/heads/<default-branch> "$empty_commit"
   ```

   The push still needs `--no-verify`: `protect-branch` blocks by destination ref, not by commit content, so it cannot recognize this bootstrap push as the one exception. Get explicit confirmation for this specific exception before running it — every other push and commit in this lifecycle goes through hooks normally.

   ```bash
   git push --no-verify origin <default-branch>
   ```
9. Configure supported settings after the default branch exists: Dependabot alerts/security updates, push protection where available, squash merging disabled, and a branch ruleset appropriate to the repository. Confirm plan/visibility limitations instead of treating API success as proof a feature is active.

    Adopting `CODEOWNERS` changes what "appropriate" means here. It is the only addon finished by a repository setting rather than by an edit: without a rule requiring code owner review, the file requests a reviewer and nothing waits for the answer. Enabling it is not the safe default it looks like, for the reason its manifest entry gives — ask.

    Squash merging is turned off unconditionally here, not collected as a preference in step 2. `AGENTS.md` documents Conventional Commit messages checked by a `commit-msg` hook; a squashed merge takes its message from the pull request title instead, written in GitHub's web interface where no local hook can reach it, so leaving it on lets one click bypass every rule in `.commitlintrc.yaml`. Unlike push protection and rulesets, it is offered on every plan, so it needs no plan/visibility check before applying it.

    ```bash
    gh api -X PATCH repos/<owner>/<name> -f allow_squash_merge=false
    ```

    Automatic head branch deletion is applied here from the answer step 2 already collected, not asked about here. Unlike everything else in this step it is a preference about branch hygiene rather than a guarantee the payload depends on, which is why it is the one setting a person chooses rather than one the payload requires. Left off, merged branches accumulate until someone prunes them by hand; nothing breaks and nothing reports it. Turned on, GitHub deletes the head ref at merge and the remote branch list stays the set of work in flight.

    ```bash
    gh api -X PATCH repos/<owner>/<name> -f delete_branch_on_merge=true
    ```

    It is a checkbox rather than a workflow on purpose — deleting the head ref from Actions means a `pull_request: closed` job holding `contents: write` to reimplement something GitHub already offers.

    Read the result back with the repository's own `scripts/repo-settings check` rather than hand-rolling `gh api` calls. It already separates the two ways a setting reads as absent: `security_and_analysis` is missing both for a non-admin and for a plan that does not offer the feature, and it checks `.permissions.admin` to tell those apart. A hand-rolled check that misses this reports a plan limitation as a disabled setting.

    Its output is the evidence for the settings section of the report, and `not offered for the plan` is a distinct outcome from disabled — do not collapse them.

    A ruleset that was accepted is not a ruleset that binds. Creation returns 201 either way, so prove enforcement rather than inferring it: commit locally, attempt a direct push to the default branch, and require the `GH013` rejection. Reset the probe commit with `git reset --hard origin/<branch>` afterwards. An unprotected branch accepts that push, which is the finding.

10. Branch from the empty base, add the entire candidate and manifest, commit, push, and open a PR. Supply an explicit PR body because the empty base does not yet contain the repository's PR template.
11. Verify the remote default branch, PR base/head, URL, settings state, and available checks. Do not merge.

    A pull request with no checks means the workflows are unverified, never that they passed. Establish which one it is before reporting:

    ```bash
    gh api repos/<owner>/<name>/commits/<head-sha>/check-suites --jq '[.check_suites[].app.slug]'
    ```

    No GitHub Actions suite means no run was ever dispatched. Check [githubstatus.com](https://www.githubstatus.com/) before treating that as a defect in the generated repository — dispatch and registration are separate services, and an outage suppresses runs while every permissions and workflow API still reports healthy.

    Note that `/actions/workflows` lists the default branch only, so it reads zero on a first-generation PR whose default branch has no `.github/` yet. That is expected, not evidence.

    A bootstrap generate is the one case where "do not merge" inverts. The destination's default branch is still the empty root commit, so no worktree can be created against it to review the PR before it merges — `git worktree add` against an empty tree checks out nothing, and a hook that expects the repository's own files (a missing `.pre-commit-config.yaml`, for instance) then fails on an empty checkout that was never the defect. Once checks pass, repo-builder may merge this one pull request itself, gated the same as any other remote action: present it as an explicit action against this exact repository and obtain confirmation before running it. The exception is scoped to this bootstrap PR alone — update, adopt, and a generate into an already-populated destination all have a destination worktree available for ordinary review, so their pull requests are never merged by repo-builder.

## Generate into a repository that already has content

The steps above assume an empty destination. A destination with existing content is a generation whose collisions are decided by hand, and it needs its own rules:

1. Establish that the destination is a clean worktree, and enumerate every payload path that already exists there before writing anything.
2. Apply non-colliding payload files as ordinary additions.
3. For each collision, decide between the payload version, the destination version, and a merge — then state the decision and the reason per file. Verify afterwards that no destination-only content was dropped, naming what was preserved.
4. Never delete destination content to resolve a collision. A payload path that cannot be reconciled is a conflict to report, not a file to overwrite.
5. Record the collision decisions in `generation`, since they are choices a later update has to respect rather than re-litigate.
6. Do not create the placeholder application when the destination already has its own application boundary. Record the real boundary in `generation.application_name` and drop the payload's Placeholders section.

Ownership still governs what a later update may touch, and a hand-merged file is managed content whose destination edits are real intent. Classify deliberately: marking a whole tree product to protect it also freezes it.

## Update

1. Require a clean destination clone and identify its origin/default branch. Do not stash or discard the user's work.
2. Run the read-only preflight before editing:

   ```bash
   python3 <template-repo>/.claude/skills/repo-builder/scripts/preflight.py update \
     --template-repo <template-repo> \
     --target <ref-or-commit> \
     --destination <destination>
   ```

   The command validates the manifest, repository identities, clean worktree, old and target subtrees, full commits, ancestry, and ownership classification. A non-descendant target is a hard stop.
3. Inspect four sources of intent:
   - old payload at the recorded commit;
   - current destination;
   - new payload at the target commit;
   - recorded generation decisions.
4. Reconcile only paths in the preflight delta:
   - template changed, destination matches old: apply the new template version;
   - destination changed, template did not: preserve the destination;
   - both changed in non-overlapping ways: combine both intents and verify;
   - both changed the same behavior, a changed file was deleted/renamed, or a new template path collides with product content: report the conflict and request the specific policy decision.
5. Classify every delta path as `applied`, `preserved`, `renamed/deleted`, or `conflicted`. Do not leave conflict markers.
6. Run the destination's documented checks. If they fail, keep the recorded commit unchanged and report the candidate diff for recovery. The `core.hooksPath` gotcha noted under Generate step 5 applies equally here if the destination's hook is not yet installed.
7. After successful checks, update `template.commit` to the exact target, validate the manifest again, and rerun checks affected by that change.
8. Create a feature branch from the current remote default branch. Commit only the bounded lifecycle diff, present the remote gate, push, and open a PR. Do not merge.
9. Verify PR base/head, changed paths, the recorded target commit, check results, and preserved product paths.

## Adopt

Adopt lands a held-back repository addon into a repository that already carries `.repo-template.json`, once its condition has arrived. It reads the addon from the **recorded** commit and never advances the pin: a newer addon is an update first, then an adopt. Use it instead of update when the request adds an addon rather than carrying a template delta.

1. Confirm `.repo-template.json` is present — its absence makes this a generate, not an adopt. Require a clean destination worktree and identify its origin/default branch. Do not stash or discard the user's work.
2. Run the read-only preflight before editing:

   ```bash
   python3 <template-repo>/.claude/skills/repo-builder/scripts/preflight.py adopt \
     --template-repo <template-repo> \
     --destination <destination> \
     --addon <destination-relative path> [--addon ...]
   ```

   It validates the manifest, both repository identities, a clean worktree, and the recorded commit, then for each addon confirms the blob exists in `repository-addons/` at that commit, carries an `addon-adoption.json` entry, completes its pair, and is absent from the destination. A half pair or an already-present addon is a hard stop. Retain the JSON.
3. Copy each addon from the recorded commit out of `repository-addons/` — a sibling of the subtree, not inside it — into the candidate at its destination-relative path. Adopt the two pairs whole: `CONTRIBUTORS.md` with `.all-contributorsrc`, and `CHANGELOG.md` with `.claude/rules/changelog.md`.
4. Run the [Addon adoption](#addon-adoption) walkthrough for every addon taken: ask each distinct `value_key` once, fill every slot, surface each review judgement, list each external step, and write any `authored_on_adoption` file. Report each region as done or outstanding.
5. Do not advance `template.commit` and do not record the addon in the manifest. Ownership already treats a later-seen adopted file as destination-added rather than a template deletion, so a subsequent update leaves it alone.
6. Stage the candidate and run the destination's documented checks, keeping the four outcomes distinct: pass, nothing to do, runner unavailable, never ran. The `core.hooksPath` gotcha noted under Generate step 5 applies equally here if the destination's hook is not yet installed.
7. Create a feature branch from the current remote default branch. Commit only the adopted addon paths, present the remote gate, push, and open a PR. Never merge.
8. Verify PR base/head, that only addon paths changed, check results, and that product content is preserved.

## Remote action gates

Repository creation, settings writes, pushes, and pull-request creation are separate outward-facing actions. Plan and validate locally first. Immediately before them, show:

```text
Remote execution
- create: owner/repository (private, uninitialized)
- push: empty root commit -> main
- settings: Dependabot alerts/updates; push protection if available; squash merging disabled; main ruleset; automatic head branch deletion if chosen
- push: repo-builder/<short-target> -> generated content or template update
- open PR: repo-builder/<short-target> -> main
```

Ask for confirmation unless the invocation already authorizes these exact actions against this exact repository. Authorization for repository creation does not imply settings changes or a later merge. Never merge as part of this skill.

## Failure and recovery

Stop before editing when:

- the manifest is absent, malformed, or records a non-full commit;
- the destination is dirty or origin differs from the manifest;
- either payload subtree is unavailable;
- the recorded commit is not an ancestor of the target;
- ownership is ambiguous.

Stop before remote actions when semantic intent conflicts or verification fails. Keep `template.commit` at the previous version. Report exact paths, Git evidence, checks, and a recoverable next action. Do not approximate a missing old version, rebase unrelated template histories, reset/clean the destination, or claim a partial update succeeded.

Report a check by what it did, and keep the four outcomes distinct: a check that passed, one that reported nothing to do, one whose runner was missing, and one that never ran. The candidate's own scripts make that distinction, and collapsing it in the report discards the thing they were built to preserve. A run reporting no project manifest checked nothing; a green pull request with no workflow runs verified nothing; a file that was never written cannot fail.

## Final report

Use this stable shape. On a generate the Reconciliation lines are empty or trivially everything, and File list carries the weight — it is the only section reporting a file the payload ships and the candidate lacks, which no check can fail on. On an adopt the Template line shows the recorded commit on both sides because the pin does not move, and the Addon adoption block carries the weight.

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

### File list
- <payload paths accounted for, and every difference named as intended or as a defect>

### Addon adoption
- <addon taken>: <slot token, review section, or external step>: filled | reviewed | done | OUTSTANDING (<what remains>)
- <addons offered and not taken, on one line>

### Repository settings
- <setting>: enabled | unavailable (<reason>) | not requested

### Verification
- `<exact command>`: pass | fail | unavailable (<reason>)

### Pending action
<none, or the exact decision/authorization needed>
```
