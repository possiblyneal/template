# Repo Builder Lifecycle Contract

## Contents

- [Manifest](#manifest)
- [Ownership](#ownership)
- [Addon adoption](#addon-adoption)
- [Wayfinding](#wayfinding)
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
    "applications": ["billing-api"],
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

`generation.applications` lists the deployable names [Wayfinding](#wayfinding) established, and nothing else about them. It is recorded because an update has to know that `apps/app-name` was renamed rather than deleted, which the destination tree can no longer say. The choke point and the language behind each name are not recorded here: the language is answered by the manifests present under the rule above, and the choke point is an argument rather than a fact, so it belongs in the ADR that makes it. A manifest still recording the earlier single `application_name` is left as it is — it records what that generation chose, and an update rewriting it would claim a decision the update did not make.

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

## Wayfinding

Generation has to know how many applications the repository holds, what each is called, and what each is written in. Those are not preferences to collect. They follow from the decomposition in [`choosing_a_language.md`](choosing_a_language.md), and wayfinding derives them with the user.

It is short by default — two questions asked once — and hands the decomposition to `/wayfinder` only where the short form fails to settle something. That handoff ends the generate and turns a build into a planning effort, which is a real cost to put in front of someone who asked for a repository, and most repositories do not need it.

Run it at [Generate](#generate) step 7 — after the candidate is materialized, the destination repository exists, and step 6 has configured where that repository tracks its issues, and before the candidate is personalized. Step 8 is the first thing that reads the result and nothing before it depends on the answer, so this is the last position where the question can still be asked. Asking it there means an escalation stops a generate that has already banked its deterministic work: the repository, its settings, its tracker, and the materialized candidate all survive the handoff, and the resumed session re-enters at personalization instead of rebuilding the tree. Skip wayfinding only when the invocation already names every deployable and its language, and say so in the final report — a supplied name and a derived one are identical on disk, and only the derived one has an ADR behind it.

### The short form

Do not open a full Event Storming workshop to create a directory. Ask the two questions that decide `apps/`, in one structured prompt, with your own reading of the request as the options:

1. **What ships separately?** Offer the candidate decompositions the request supports — one service; a client and a server; an API and a worker — and name what each would be called. This answers how many `apps/<name>/` directories exist and what each is.
2. **What binds first, for each of those?** Offer the five constraints from the reference — browser or device execution, deployment glue, an ecosystem only one language has, many long-lived connections with per-connection flow control, a hard memory or hardware limit — plus *none of these bind*. This answers the language.

Propose, and let the user dispose. That is the reason for putting your reading into the options rather than asking open questions: a proposal the user can see and reject has been tested, and an assumption you made silently has not. But the options are a shortcut, not the answer — *Other* is the load-bearing choice here, and a split nobody picked off the list is the ordinary outcome for anything the request did not already spell out.

Two answers close the session for most repositories. Take the names from the decomposition, confirm them as kebab-case, and go.

### When to hand off

The short form is a path through [`choosing_a_language.md`](choosing_a_language.md), not a replacement for it. It works when the user can already say what ships. When it does not, the remaining work is the full method — Steps 1 through 6, one step per exchange, applying each test as the reference gives it — and that is `/wayfinder`'s job rather than this skill's. Stop the generate and hand off when any of these holds:

- the user rejects every offered split and describes one the request does not obviously support, which means the boundary is the open question rather than the naming;
- more than one constraint is selected for a single deployable and which one is tightest is not settled by what that deployable promised at its seam;
- two proposed deployables turn out to need the same concept under different meanings — the reference's Speaker case, where the boundary is what is actually in dispute;
- the repository is being designed rather than described: the user can say what the software should do but not what ships.

The value of that session is concentrated in the places where the first answer was wrong — a UI event mistaken for a domain event, a noun that turned out to be a field on an aggregate rather than an aggregate, two aggregates that looked like one until asked whether either could change alone. Only the user can produce those corrections, which is why the method is worth a separate effort rather than a longer prompt.

### Handing off to `/wayfinder`

`/wayfinder` charts the open decisions as a map of tickets and then works them one at a time, with the user answering each. Invoke it with the Skill tool to chart, supplying:

- **Destination** — for every deployable a kebab-case name, its choke point, and the language that constraint selects. That is `/wayfinder`'s destination in its own sense: what reaching the end of the map looks like, and the edge past which further decomposition is out of scope for this generate rather than fog still ahead of it.
- **Notes** — [`choosing_a_language.md`](choosing_a_language.md) as the method every ticket session runs on, one step per exchange; the short-form answers already given; and which of them came apart, since that is where the map starts.
- **Nothing about where the map lives.** `/wayfinder` reads `docs/agents/issue-tracker.md` and charts against whatever that file records; [Generate](#generate) step 6 wrote it, against a destination repository that already exists. Do not name an effort directory and do not override the choice. A map charted somewhere other than where the repository tracks its issues is a map nobody finds again, and on the ordinary GitHub answer the map's native blocking edges are what render the frontier in GitHub's own UI — the thing `/wayfinder` calls essential and the thing a directory of markdown files cannot do. Ordering the repository and its tracker ahead of wayfinding is what buys this; a handoff before either has nowhere durable to chart to.

Charting is where the generate ends. `/wayfinder` resolves nothing while charting and never works more than one ticket per session, and that rule is the whole reason to reach for it: the value of the full method is in the answers only the user can give, so a generate that pushed on through its own map would hand back the decomposition it had already guessed, wearing an ADR that claims it was deliberated. Do not work a ticket, and do not answer any of the six steps yourself.

So report `stopped` with the pull request not created, leave the materialized candidate and the created repository in place, and hand back two things: the map, and the resume. The user works the map with `/wayfinder` across as many sessions as it takes, then re-invokes `/repo-builder` against the same candidate. It re-enters at [Generate](#generate) step 8 and reads the decomposition out of the map's Decisions so far.

### What wayfinding must produce

For every deployable, whether the short form settled it or a map did: a kebab-case name, the constraint identified as its choke point, and the language that constraint selects.

A map additionally produces the context each deployable belongs to, and for every seam the two contexts and the contract between them. The short form does not, and must not invent them — a context named without the aggregates under it is a label, and a seam contract asserted without asking is the preference-justified-after-the-fact this section exists to prevent.

The number of deployables is the number of `apps/<name>/` directories to create. It is not the number of contexts. The reference names collapsing context, deployable, and language choice as the most common way the method gets misapplied, and this is the step where that collapse would happen.

### Recording the outcome

Write one ADR per deployable under `docs/adrs/`, copied from `0000-template.md` and numbered from `0001`. Set `scope` to `apps/<name>` and the `lang:<language>` tag, state the choke point in **Context** — with the seam contract behind it when a map established one — and record in **Alternatives Considered** the constraints that were checked and did not bind.

Set `status: accepted`, not the template's `status: proposed`. Generation acted on this decision: the directory exists and the language is chosen. Shipping it as a proposal describes a deliberation that already concluded, and leaves every generated repository with a decision log nobody appears to have agreed to.

That last part is the reason for writing any of this down. A constraint checked and found not to bind and a constraint nobody looked at are indistinguishable a year later, and the ADR is the only thing that can tell them apart. The short form's *none of these bind* is exactly such a finding, and it reaches the ADR as one.

Say in **Context** how the choke point was established: chosen from the short form's list, reasoned from the seam contract, or measured against it. The reference's one reversal turned on that difference, and the weaker the footing the sooner the decision is worth revisiting.

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

2. Collect only unresolved decisions: owner/name, visibility, public-repository files, release behavior, feature availability, and automatic head branch deletion. The application boundaries are not among them. They are derived rather than collected, and step 7 derives them once the candidate and the repository exist.

   Automatic head branch deletion is collected here rather than at step 5, where it is applied, because the remote action gate at step 4 lists it among the settings it authorizes. A gate cannot name a choice that has not been made yet — asking after it would take authorization for one plan and then write a setting under another.

   The public-repository files are the repository addons, held back rather than shipped and offered against the conditions the answers to this step have established. Adopt the ones taken as the [Addon adoption](#addon-adoption) section directs, from this same source commit.
3. Materialize the subtree from that exact commit into an isolated local directory. Do not substitute the current working tree. Initialize Git in it and leave the remote unset; step 4 creates the repository that remote points at.
4. Create the destination repository, at the [remote action gate](#remote-action-gates). Present the gate first: the repository name and visibility, the empty root commit, and the settings plan step 2 collected. There is no diff and no check result to show yet, which is why this gate is separate from the one at step 11 — that one authorizes publishing content that has been reviewed, and this one authorizes an empty repository so that everything after it has somewhere to live.

   Create it without auto-initialization, set it as the candidate's remote, and push one empty root commit to the default branch, so the full generated payload is reviewable as a pull-request diff at step 11 rather than arriving as an initial commit nobody reads.

   ```bash
   empty_tree=$(git hash-object -t tree /dev/null)
   empty_commit=$(git commit-tree "$empty_tree" -m "chore: initialize empty repository")
   git update-ref refs/heads/<default-branch> "$empty_commit"
   git push origin <default-branch>
   ```

   Build the commit with `commit-tree` rather than by checking the default branch out and committing on it. The candidate's own `no-commit-to-branch` hook refuses such a commit and its `protect-branch` pre-push hook refuses the push, both correctly — neither can distinguish this one-time structural bootstrap from an ordinary disallowed one. Neither hook is installed this early, since step 9 is what installs them, but do not lean on that ordering: a resumed generate reaches this step with them already in place, and the push then needs `--no-verify`, because `protect-branch` blocks by destination ref rather than by commit content and so cannot recognize its one exception. Every other push and commit in this lifecycle goes through hooks normally.

   The repository existing this early is deliberate, and the two steps after it are the reason. `/setup-matt-pocock-skills` proposes an issue tracker by reading `git remote -v`, and `/wayfinder` charts its map wherever that answer sends it. Run either against a candidate with no remote and both get the wrong answer for a repository that is about to be on GitHub — and the map, which is the whole product of an escalated generate, ends up somewhere the repository does not track its work. The cost is that a generate abandoned after this point leaves an empty repository behind; say so at the gate.
5. Configure supported settings after the default branch exists: Dependabot alerts/security updates, push protection where available, squash merging disabled, and a branch ruleset appropriate to the repository. Confirm plan/visibility limitations instead of treating API success as proof a feature is active.

   Adopting `CODEOWNERS` changes what "appropriate" means here. It is the only addon finished by a repository setting rather than by an edit: without a rule requiring code owner review, the file requests a reviewer and nothing waits for the answer. Enabling it is not the safe default it looks like, for the reason its manifest entry gives — ask.

   Squash merging is turned off unconditionally here, not collected as a preference in step 2. `CLAUDE.md` documents Conventional Commit messages checked by a `commit-msg` hook; a squashed merge takes its message from the pull request title instead, written in GitHub's web interface where no local hook can reach it, so leaving it on lets one click bypass every rule in `.commitlintrc.yaml`. Unlike push protection and rulesets, it is offered on every plan, so it needs no plan/visibility check before applying it.

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

   A ruleset that was accepted is not a ruleset that binds. Creation returns 201 either way, so prove enforcement rather than inferring it: put a throwaway commit on the default branch, push it directly, and require the `GH013` rejection. An unprotected branch accepts that push, which is the finding.

   ```bash
   git commit --allow-empty -m "chore: ruleset probe"
   git push origin <default-branch>
   git update-ref refs/heads/<default-branch> origin/<default-branch>
   ```

   Make the probe empty and undo it with `update-ref` rather than `git reset --hard`. The materialized payload is sitting untracked in this worktree, and a hard reset against an empty base takes the working tree with the probe.

6. Configure the repository for the engineering skills — invoke `/setup-matt-pocock-skills` with the Skill tool. Invoke it; do not answer for the user and do not reproduce what it does by hand. It is the source of truth for its own questions, and a copy of them here goes stale the first time it changes.

   It asks two questions of this candidate. Which issue tracker, proposed from the remote step 4 created; and whether to keep the default triage labels, asked only because the `triage` skill is installed. Its third section, the domain-doc layout, settles itself — it asks only where it finds monorepo signals, and the payload ships none.

   It writes `docs/agents/issue-tracker.md`, `docs/agents/domain.md`, `docs/agents/triage-labels.md`, and an `## Agent skills` block in the root `CLAUDE.md`. Step 8 rewrites that same file's Child Index and must leave the block intact; step 10 accounts for the three new paths.

   Run it here rather than after generation, because step 7 depends on its output: `/wayfinder` reads `docs/agents/issue-tracker.md` to decide where a map lives, and a handoff reached before this step has nowhere to chart to.
7. Derive the application boundaries — run [Wayfinding](#wayfinding) here. Two questions settle it for most repositories; against the triggers that section names, hand the decomposition to `/wayfinder` as that section directs and stop once the map is charted, leaving this candidate and this repository in place for the resumed session.
   Do not render a root manifest, even for a language wayfinding selected. Wayfinding establishes which constraint binds; it does not establish a package manager, a version, or a project layout, and none of those follow from a choke point. It also reasons rather than measures — the reference is explicit that an unmeasured constraint and an absent one are indistinguishable until something measures — so a rendered manifest asserts more confidence than wayfinding produced. A wrong guess is worse than an absent file, the same reasoning `.github/dependabot.yml` follows in listing only the two manifests the template itself ships. A generated repository with no manifest is reported honestly by `scripts/ci` as nothing to check yet, with every check becoming required the moment one is added. The first real commit brings the manifest.

   Say so in the handover: the root manifest is what makes a package visible to the checks, and a manifest nested under `apps/` instead is invisible to all of them. `scripts/doctor` fails on that shape rather than passing over it.
8. Personalize the candidate:
   - create one `apps/<name>/` per deployable wayfinding established. Move `apps/app-name` to the first (do not copy it) and replicate its skeleton — `src/`, `tests/`, `docs/specs/` — for each one after that. Verify `apps/app-name` is absent afterwards and update every reference. One deployable is the ordinary case and needs no replication;
   - write one ADR per deployable recording its choke point and language, as [Wayfinding](#wayfinding) directs;
   - replace the root `CLAUDE.md` bootstrap Child Index with repository-specific content, carrying the wayfinding result into it: each deployable, what it is for, and the language it is written in. The ADRs record why that language was chosen; `CLAUDE.md` is where an agent reads what the repository is before touching anything, and a Child Index naming the apps without saying what each one is leaves the boundaries derivable only from a directory listing;
   - initialize `docs/LESSONS.md` metadata and remove generation placeholders while retaining its durable writing guidance. Set `generated.by` to the actual author — the repo-builder agent, not the operator on whose behalf it ran — and capture `generated.at` from the real clock (e.g. `date -u +%Y-%m-%dT%H:%M:%SZ`) at the moment of writing rather than composing a plausible-looking value; a rounded time such as midnight is a placeholder wearing a valid format, not a captured one;
   - keep `docs/adrs/0000-template.md` as the reusable ADR template;
   - create `.repo-template.json`;
   - render visibility and feature choices honestly. Keep `codeql.yml` for a private repository rather than omitting it. Its `scanning` job fails in seconds naming the reason, which is accurate — the repository has no static analysis coverage — and it turns green by itself when the repository goes public, where omitting the file leaves nothing to restore and nothing to say so. Report that red check as an expected initial state when handing the repository over; do not describe it as a passing build. Record an omission under `features` only when deliberately stripping the workflow, which is now a choice rather than the private-repository default.
9. Install the candidate's local pre-commit hook if it requires one, and run its documented checks. Git is already initialized and its remote already set, from steps 3 and 4. Report skipped or unavailable checks; do not call them passes.

   Stage the candidate before running the checks. Step 10 compares tracked paths, and a bare `pre-commit run --all-files` enumerates through the Git index, so an unstaged candidate is checked as the empty set and reports a pass over nothing. The candidate's own `scripts/check` sweeps untracked files by path after that command, but only if the payload it was built from carries that second pass — verify rather than assume it.

   Tools the candidate's scripts look up on `PATH` may also run inside pre-commit's pinned environments. A tool reported unavailable by a script and passing under pre-commit in the same run was not skipped; report what each surface actually did.

   A machine-wide `core.hooksPath` set for an unrelated purpose (an editor's own git integration, another agent's attribution hook) makes `pre-commit install` refuse outright, and breaks it again inside any throwaway fixture repository the candidate's own tests spin up to exercise hook installation — fixtures inherit the same global config. Check `git config --global core.hooksPath` before treating either failure as a candidate defect; a control run of the same checks against the template repository's own current HEAD reproduces an identical failure when this is the cause.

10. Verify the file list, not only the content. Compare the payload's tracked paths at the source commit against the candidate's, and account for every difference as intended or as a defect. A file the payload ships and the candidate lacks is invisible to every check, because a check reads content and absence has no runner. Compare against the working tree as well as the index: a path the destination ignores is present and untracked rather than missing, and `.env` is the one the payload ships that way. Use `git ls-files` for the tracked comparison and `git ls-files -o -i --exclude-standard` for the untracked one; the flags are the whole point, since an ignored path appears in neither the plain form nor `-o --exclude-standard`, and the two disagree about `.env` in the direction that reads as missing. Do not build either list with the file-discovery tools — `.env` matches a `permissions.deny` rule, so Glob and Grep omit it and a listing built from them reports it missing when it is there.

   The candidate also carries paths the payload does not ship, and each is an intended addition rather than a stray: `docs/agents/issue-tracker.md`, `docs/agents/domain.md`, and `docs/agents/triage-labels.md` from step 6, and every `apps/<name>/` past the first from step 8. None of them is ignored, so they appear in the tracked comparison as candidate-only paths — the same shape a stray file has, which is why the account names them rather than counting them. A repository whose step 6 answer was local markdown carries its `/wayfinder` map under `.scratch/` too, and that also ships: tracking issues as files in the repository is what that answer chose.
11. Publish the candidate, at the [remote action gate](#remote-action-gates). Present the local diff, the file-list reconciliation, the check results, the settings state, and the exact pending commands. Then branch from the empty base, add the entire candidate and manifest, commit, push, and open a PR. Supply an explicit PR body, because the empty base does not yet contain the repository's PR template.
12. Verify the remote default branch, PR base/head, URL, settings state, and available checks. Do not merge.

    A pull request with no checks means the workflows are unverified, never that they passed. Establish which one it is before reporting:

    ```bash
    gh api repos/<owner>/<name>/commits/<head-sha>/check-suites --jq '[.check_suites[].app.slug]'
    ```

    No GitHub Actions suite means no run was ever dispatched. Check [githubstatus.com](https://www.githubstatus.com/) before treating that as a defect in the generated repository — dispatch and registration are separate services, and an outage suppresses runs while every permissions and workflow API still reports healthy.

    Note that `/actions/workflows` lists the default branch only, so it reads zero on a first-generation PR whose default branch has no `.github/` yet. That is expected, not evidence.

    A bootstrap generate is the one case where "do not merge" inverts. The destination's default branch is still the empty root commit, so no worktree can be created against it to review the PR before it merges — `git worktree add` against an empty tree checks out nothing, and a hook that expects the repository's own files (a missing `.pre-commit-config.yaml`, for instance) then fails on an empty checkout that was never the defect. Once checks pass, repo-builder may merge this one pull request itself, gated the same as any other remote action: present it as an explicit action against this exact repository and obtain confirmation before running it. The exception is scoped to this bootstrap PR alone — update, adopt, and a generate into an already-populated destination all have a destination worktree available for ordinary review, so their pull requests are never merged by repo-builder.

Having merged it, verify the default branch. This is the only merge in the lifecycle, and it is the first time the repository's workflows run against `main` with content in it — a green pull request does not carry over, because the PR ran against a merge of an empty base and `main` afterwards is a different commit with a different trigger. Read that commit's check-suites the same way step 12 reads the PR's, keep the same distinction between a failing run and no run dispatched, and report the result. A red default branch immediately after generation is a finding to hand over, not a state to leave unmentioned because the pull request was green.

## Generate into a repository that already has content

The steps above assume an empty destination. A destination with existing content is a generation whose collisions are decided by hand, and it needs its own rules:

Steps 4 and 5 create nothing here — the repository is already there, and its settings are reconciled rather than applied, since a setting someone deliberately turned off is destination intent the same way a file is. Step 6 still runs, but `/setup-matt-pocock-skills` may find its own prior output; let it decide what to do with it rather than deleting `docs/agents/` first.

1. Establish that the destination is a clean worktree, and enumerate every payload path that already exists there before writing anything.
2. Apply non-colliding payload files as ordinary additions.
3. For each collision, decide between the payload version, the destination version, and a merge — then state the decision and the reason per file. Verify afterwards that no destination-only content was dropped, naming what was preserved.
4. Never delete destination content to resolve a collision. A payload path that cannot be reconciled is a conflict to report, not a file to overwrite.
5. Record the collision decisions in `generation`, since they are choices a later update has to respect rather than re-litigate.
6. Do not create the placeholder application when the destination already has its own application boundaries. Record the real ones in `generation.applications`. Wayfinding still runs, but against what is there: it names the choke point each existing deployable already answers to rather than proposing a new decomposition, and it writes an ADR only where the repository has none for that deployable. A generation is not the occasion to re-cut boundaries someone is already shipping against.

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
6. Run the destination's documented checks. If they fail, keep the recorded commit unchanged and report the candidate diff for recovery. The `core.hooksPath` gotcha noted under Generate step 9 applies equally here if the destination's hook is not yet installed.
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
6. Stage the candidate and run the destination's documented checks, keeping the four outcomes distinct: pass, nothing to do, runner unavailable, never ran. The `core.hooksPath` gotcha noted under Generate step 9 applies equally here if the destination's hook is not yet installed.
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
- merge: repo-builder/<short-target> -> main (bootstrap generate only, see Generate step 12)
```

A generate reaches this twice, and the two gates authorize different things. The first, at [Generate](#generate) step 4, covers the first three lines: an empty repository and its settings, with no diff and no check result to show, because nothing has been built yet. The second, at step 11, covers the rest against a candidate that has been personalized, checked, and file-list reconciled. Show only the lines the gate is actually asking for. Presenting the whole block at step 4 takes authorization for a content push that does not exist yet.

Ask for confirmation unless the invocation already authorizes these exact actions against this exact repository. Authorization for repository creation does not imply settings changes or a later merge. Never merge as part of this skill, except the bootstrap-generate case documented under Generate step 12: that PR may be merged, gated the same as every other remote action here.

## Failure and recovery

Stop before editing when:

- the manifest is absent, malformed, or records a non-full commit;
- the destination is dirty or origin differs from the manifest;
- either payload subtree is unavailable;
- the recorded commit is not an ancestor of the target;
- ownership is ambiguous.

The [Wayfinding](#wayfinding) handoff is also a stop, and the one that is not a failure: nothing is wrong, the decomposition is simply not this skill's to settle. Report it as `stopped` like any other, but do not report it as a defect in the candidate or the request, and do not discard the materialized candidate — it is what the resumed session re-enters at. By this point the destination repository exists, configured, with its default branch still the empty root commit and its map on its tracker. That is the state to leave and to describe, not a half-finished generate to roll back; the repository is where the map lives, so deleting it discards the only thing the stop produced.

Stop before remote actions when semantic intent conflicts or verification fails. Keep `template.commit` at the previous version. Report exact paths, Git evidence, checks, and a recoverable next action. Do not approximate a missing old version, rebase unrelated template histories, reset/clean the destination, or claim a partial update succeeded.

Report a check by what it did, and keep the four outcomes distinct: a check that passed, one that reported nothing to do, one whose runner was missing, and one that never ran. The candidate's own scripts make that distinction, and collapsing it in the report discards the thing they were built to preserve. A run reporting no project manifest checked nothing; a green pull request with no workflow runs verified nothing; a file that was never written cannot fail.

## Final report

Use this stable shape. On a generate the Reconciliation lines are empty or trivially everything, and File list carries the weight — it is the only section reporting a file the payload ships and the candidate lacks, which no check can fail on. On an adopt the Template line shows the recorded commit on both sides because the pin does not move, and the Addon adoption block carries the weight. On a generate stopped at the wayfinding handoff there are no Application boundaries to report — that absence is the result; the Wayfinding line names the trigger and the map, Repository settings still reports the repository that exists, and Pending action carries the resume.

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
